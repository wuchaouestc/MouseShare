"""
Host StateMachine 整合 — 管理 Host 端完整生命周期
"""
import time
import logging
import threading
from src.shared.state_machine import AgentState, StateMachine
from src.shared.protocol import (
    Frame, MsgType, encode, decode, build_heartbeat, build_heartbeat_ack,
    build_control_enter, build_control_leave,
    build_mouse_move, build_mouse_button, build_mouse_wheel,
)
from src.host.input_capture import InputCapture, InputEvent, InputEventType
from src.host.boundary_engine import BoundaryEngine, Direction
from src.host.cursor_controller import CursorController
from src.shared.bluetooth_scanner import set_discoverable

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 1.0
HEARTBEAT_TIMEOUT = 3.0  # 3次心跳超时
RECONNECT_BASE_DELAY = 1.0
RECONNECT_MAX_DELAY = 15.0
RECONNECT_MAX_RETRIES = 5


class HostAgent:
    def __init__(self):
        self.sm = StateMachine("HostAgent")
        self.input = InputCapture()
        self.boundary = BoundaryEngine()
        self.cursor = CursorController()
        self._transport = None
        self._seq = 0
        self._recv_buf = bytearray()
        self._running = False
        self._hosting = False
        self._last_heartbeat_sent = 0.0
        self._last_heartbeat_recv = 0.0
        self._heartbeat_missed = 0
        self._lock = threading.Lock()
        self._reconnect_attempts = 0

    def set_transport(self, transport):
        self._transport = transport

    def set_direction(self, direction: str):
        d = Direction(direction)
        self.boundary.set_direction(d)

    def start(self):
        self._running = True
        self.input.start()
        self.cursor.start_emergency_listener()
        self.cursor.set_emergency_callback(self._on_emergency)
        self.boundary.set_callbacks(
            on_enter=self._on_boundary_enter,
            on_leave=self._on_boundary_leave,
        )
        self.sm.transition(AgentState.IDLE)
        set_discoverable(True)
        # 启动事件处理循环
        self._event_thread = threading.Thread(target=self._event_loop, daemon=True)
        self._event_thread.start()
        # 启动心跳线程
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_thread.start()
        logger.info("HostAgent started")

    def stop(self):
        self._running = False
        self._stop_hosting()
        self.cursor.unlock()
        self.cursor.stop_emergency_listener()
        self.input.stop()
        if self._transport:
            try:
                self._transport.close()
            except Exception:
                pass
        self.sm.transition(AgentState.EXITING)
        logger.info("HostAgent stopped")

    def connect(self, address: str, port: int = 0) -> tuple:
        """返回 (success: bool, error_msg: str)"""
        if not self._transport:
            return False, "传输层未初始化"
        self.sm.transition(AgentState.CONNECTING)
        if self._transport.connect(address, port):
            self.sm.transition(AgentState.CONNECTED)
            self._last_heartbeat_recv = time.time()
            self._reconnect_attempts = 0
            set_discoverable(False)
            logger.info(f"Connected to {address}")
            return True, ""
        else:
            self.sm.transition(AgentState.IDLE)
            err = getattr(self._transport, '_last_error', '') or "连接失败（未知原因）"
            logger.error(f"Failed to connect to {address}: {err}")
            return False, err

    def suspend(self):
        self._stop_hosting()
        self.sm.transition(AgentState.SUSPENDED)

    def resume(self):
        if self.sm.state == AgentState.SUSPENDED:
            self.sm.transition(AgentState.IDLE)

    def _event_loop(self):
        """主事件循环 — 处理捕获的鼠标事件"""
        while self._running:
            try:
                evt = self.input.get_event(timeout=0.1)
                if evt is None:
                    continue

                state = self.sm.state

                if state == AgentState.HOSTING and self._hosting:
                    # 远端控制模式：发送事件
                    self._send_input_event(evt)
                elif state == AgentState.IDLE or state == AgentState.CONNECTED:
                    # 本地模式：只检测边界
                    self.boundary.check()
                elif state == AgentState.SUSPENDED:
                    pass  # 暂停
                elif state == AgentState.RECOVERING:
                    self._try_reconnect()
            except Exception as e:
                logger.error(f"Event loop error: {e}")
                time.sleep(0.1)
        self._running = False

    def _send_input_event(self, evt: InputEvent):
        if not self._transport or not self._transport.is_connected:
            self._handle_disconnect()
            return
        try:
            with self._lock:
                self._seq += 1
                seq = self._seq

            if evt.type == InputEventType.MOVE:
                frame = build_mouse_move(evt.dx, evt.dy)
            elif evt.type == InputEventType.BUTTON_PRESS:
                frame = build_mouse_button(evt.button, 1, self.input.buttons_state)
            elif evt.type == InputEventType.BUTTON_RELEASE:
                frame = build_mouse_button(evt.button, 2, self.input.buttons_state)
            elif evt.type == InputEventType.WHEEL:
                frame = build_mouse_wheel(evt.wheel_delta)
            else:
                return

            frame.sequence = seq
            data = encode(frame)
            self._transport.send(data)
        except Exception as e:
            logger.error(f"Send error: {e}")
            self._handle_disconnect()

    def _on_boundary_enter(self, direction: Direction):
        """鼠标到达边界 — 进入远端控制"""
        if self.sm.state not in (AgentState.CONNECTED, AgentState.HOSTING):
            logger.warning(f"Cannot enter hosting from {self.sm.state.name}")
            return
        if self.sm.state == AgentState.HOSTING:
            return

        self.sm.transition(AgentState.HOSTING)
        self._hosting = True
        self.cursor.lock_at_edge(direction.value)

        # 发送 ControlEnter
        try:
            with self._lock:
                self._seq += 1
                frame = build_control_enter()
                frame.sequence = self._seq
            self._transport.send(encode(frame))
        except Exception as e:
            logger.error(f"Failed to send ControlEnter: {e}")

        # 重置输入捕获位置，避免初始跳变
        self._reset_input_position(direction.value)
        logger.info(f"Hosting started, direction={direction.value}")

    def _on_boundary_leave(self):
        """鼠标返回 — 退出远端控制"""
        self._stop_hosting()

    def _stop_hosting(self):
        if not self._hosting:
            return
        self._hosting = False
        self.cursor.unlock()
        # 发送 ControlLeave
        try:
            if self._transport and self._transport.is_connected:
                with self._lock:
                    self._seq += 1
                    frame = build_control_leave()
                    frame.sequence = self._seq
                self._transport.send(encode(frame))
        except Exception:
            pass

        if self.sm.state == AgentState.HOSTING:
            self.sm.transition(AgentState.CONNECTED)
        self.boundary.reset()
        self.input.clear_queue()
        logger.info("Hosting stopped")

    def _on_emergency(self):
        """紧急解锁回调"""
        self._stop_hosting()
        if self.sm.state not in (AgentState.SUSPENDED, AgentState.EXITING):
            self.sm.force_transition(AgentState.IDLE)

    def _handle_disconnect(self):
        """处理断线"""
        if self._hosting:
            self.cursor.unlock()
            self._hosting = False
        self.sm.transition(AgentState.RECOVERING)
        self._reconnect_attempts = 0

    def _try_reconnect(self):
        if not self._transport:
            return
        self._reconnect_attempts += 1
        if self._reconnect_attempts > RECONNECT_MAX_RETRIES:
            logger.error("Max reconnect attempts reached")
            self.sm.transition(AgentState.IDLE)
            return

        delay = min(RECONNECT_BASE_DELAY * (2 ** (self._reconnect_attempts - 1)), RECONNECT_MAX_DELAY)
        logger.info(f"Reconnect attempt {self._reconnect_attempts}/{RECONNECT_MAX_RETRIES}, delay={delay}s")
        time.sleep(delay)

        try:
            if self._transport.connect(self._last_address, self._last_port):
                self.sm.transition(AgentState.CONNECTED)
                self._last_heartbeat_recv = time.time()
                self._reconnect_attempts = 0
        except Exception:
            pass

    def _heartbeat_loop(self):
        while self._running:
            time.sleep(HEARTBEAT_INTERVAL)
            if not self._running:
                break
            if self.sm.state not in (AgentState.CONNECTED, AgentState.HOSTING, AgentState.TARGETING):
                continue

            try:
                # 发送心跳
                if time.time() - self._last_heartbeat_sent >= HEARTBEAT_INTERVAL:
                    if self._transport and self._transport.is_connected:
                        with self._lock:
                            self._seq += 1
                            frame = build_heartbeat()
                            frame.sequence = self._seq
                        self._transport.send(encode(frame))
                        self._last_heartbeat_sent = time.time()

                # 检查超时
                if time.time() - self._last_heartbeat_recv > HEARTBEAT_TIMEOUT:
                    self._heartbeat_missed += 1
                    if self._heartbeat_missed >= 3:
                        logger.warning("Heartbeat timeout, disconnecting")
                        self._handle_disconnect()
                else:
                    self._heartbeat_missed = 0
            except Exception:
                pass

    def _reset_input_position(self, direction: str):
        """重置输入捕获位置"""
        try:
            import ctypes
            from ctypes import wintypes
            pt = wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            self.input.set_current_position(pt.x, pt.y)
        except Exception:
            pass

    _last_address = ""
    _last_port = 0

    def set_last_connection(self, address: str, port: int = 0):
        self._last_address = address
        self._last_port = port
