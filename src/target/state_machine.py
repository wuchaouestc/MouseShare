"""
Target StateMachine — Target 端状态管理与事件处理
"""
import time
import logging
import threading
from src.shared.state_machine import AgentState, StateMachine
from src.shared.protocol import (
    Frame, MsgType, encode, decode, find_frame_boundary,
    build_heartbeat_ack, parse_mouse_move, parse_mouse_button, parse_mouse_wheel,
)
from src.target.rfcomm_server import RfcommServer
from src.target.input_injector import InputInjector
from src.shared.bluetooth_scanner import set_discoverable

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 1.0
HEARTBEAT_TIMEOUT = 3.0


class TargetAgent:
    def __init__(self):
        self.sm = StateMachine("TargetAgent")
        self.server = RfcommServer()
        self.injector = InputInjector()
        self._running = False
        self._recv_buf = bytearray()
        self._last_heartbeat_recv = 0.0
        self._last_heartbeat_sent = 0.0
        self._heartbeat_missed = 0
        self._seq = 0
        self._lock = threading.Lock()

    def start(self):
        self._running = True

        # Try PyBluez first, fall back to plain socket
        if not self.server.start_pybluez():
            if not self.server.start():
                logger.error("Failed to start RFCOMM server")
                return

        self.sm.transition(AgentState.IDLE)
        set_discoverable(True)
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_thread.start()
        logger.info("TargetAgent started")

    def stop(self):
        self._running = False
        self.server.stop()
        self.sm.transition(AgentState.EXITING)
        logger.info("TargetAgent stopped")

    def _recv_loop(self):
        """接收和解析帧"""
        while self._running:
            try:
                data = self.server.recv(timeout=0.5)
                if data is None:
                    # 连接断开
                    if self.sm.state != AgentState.IDLE:
                        logger.info("Client disconnected")
                        self.sm.transition(AgentState.IDLE)
                    continue

                if data:
                    self._recv_buf.extend(data)
                    self._process_frames()

                # 心跳超时检测
                if self.sm.is_connected and time.time() - self._last_heartbeat_recv > HEARTBEAT_TIMEOUT:
                    self._heartbeat_missed += 1
                    if self._heartbeat_missed >= 3:
                        logger.warning("Heartbeat timeout")
                        self.sm.transition(AgentState.IDLE)
                else:
                    self._heartbeat_missed = 0

            except Exception as e:
                logger.error(f"Recv loop error: {e}")
                time.sleep(0.5)

    def _process_frames(self):
        """解析缓冲区中的所有完整帧"""
        while True:
            pos = find_frame_boundary(self._recv_buf)
            if pos is None or pos > 0:
                if pos and pos > 0:
                    del self._recv_buf[:pos]
                elif pos is None:
                    self._recv_buf.clear()
                return

            frame = decode(bytes(self._recv_buf))
            if frame is None:
                # 不完整帧，等待更多数据
                return

            frame_size = 14 + 2 + len(frame.payload) + 4
            del self._recv_buf[:frame_size]
            self._handle_frame(frame)

    def _handle_frame(self, frame: Frame):
        self._last_heartbeat_recv = time.time()

        if frame.type == MsgType.HEARTBEAT:
            # 回复心跳 ACK
            try:
                with self._lock:
                    self._seq += 1
                    ack = build_heartbeat_ack()
                    ack.sequence = self._seq
                self.server.send(encode(ack))
            except Exception:
                pass

        elif frame.type == MsgType.CONTROL_ENTER:
            self.sm.transition(AgentState.TARGETING)
            logger.info("Received ControlEnter, entering Targeting mode")

        elif frame.type == MsgType.CONTROL_LEAVE:
            self.sm.transition(AgentState.CONNECTED)
            logger.info("Received ControlLeave, leaving Targeting mode")

        elif frame.type == MsgType.MOUSE_MOVE:
            if self.sm.state == AgentState.TARGETING:
                dx, dy, _ = parse_mouse_move(frame)
                self.injector.move(dx, dy)

        elif frame.type == MsgType.MOUSE_BUTTON:
            if self.sm.state == AgentState.TARGETING:
                btn, action, _ = parse_mouse_button(frame)
                if action == 1:  # PRESS
                    self.injector.button_press(btn)
                elif action == 2:  # RELEASE
                    self.injector.button_release(btn)

        elif frame.type == MsgType.MOUSE_WHEEL:
            if self.sm.state == AgentState.TARGETING:
                delta, horiz = parse_mouse_wheel(frame)
                self.injector.wheel(delta, bool(horiz))

    def _heartbeat_loop(self):
        while self._running:
            time.sleep(HEARTBEAT_INTERVAL)
            if not self._running:
                break

    def set_connected(self):
        if self.server.is_connected:
            self.sm.transition(AgentState.CONNECTED)
            self._last_heartbeat_recv = time.time()
            set_discoverable(False)
