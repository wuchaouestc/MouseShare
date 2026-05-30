"""
InputCapture — 全局鼠标 Hook 捕获模块

使用 pynput 捕获鼠标移动、点击、滚轮事件。
事件放入线程安全队列供消费。
"""
import threading
import queue
import time
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

logger = logging.getLogger(__name__)

class InputEventType(IntEnum):
    MOVE = 1
    BUTTON_PRESS = 2
    BUTTON_RELEASE = 3
    WHEEL = 4

@dataclass
class InputEvent:
    type: InputEventType
    dx: int = 0
    dy: int = 0
    button: int = 0       # 1=左键 2=右键 3=中键
    wheel_delta: int = 0
    timestamp: float = 0.0

class InputCapture:
    """全局鼠标事件捕获器"""
    def __init__(self, max_queue: int = 256):
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue)
        self._running = False
        self._listener = None
        self._thread = None
        self._last_pos = (0, 0)
        self._move_coalesce = True  # 合并连续移动事件
        self._buttons_state = 0  # 按键状态位图

    @property
    def buttons_state(self) -> int:
        return self._buttons_state

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="InputCapture")
        self._thread.start()
        logger.info("InputCapture started")

    def stop(self):
        self._running = False
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("InputCapture stopped")

    def _run(self):
        from pynput import mouse
        self._listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll
        )
        self._listener.start()
        while self._running:
            time.sleep(0.1)
        try:
            self._listener.stop()
        except Exception:
            pass

    def _on_move(self, x: int, y: int):
        if not self._running:
            return False
        dx = x - self._last_pos[0]
        dy = y - self._last_pos[1]
        self._last_pos = (x, y)
        if dx == 0 and dy == 0:
            return True
        evt = InputEvent(
            type=InputEventType.MOVE,
            dx=dx, dy=dy,
            timestamp=time.time()
        )
        self._try_put(evt)
        return True

    def _on_click(self, x: int, y: int, button, pressed: bool):
        if not self._running:
            return False
        btn_map = {
            button.__class__.__name__: 1 if "left" in str(button).lower() else
                                      2 if "right" in str(button).lower() else 3
        }
        # Map button
        btn_name = str(button).lower()
        if "left" in btn_name:
            btn = 1
        elif "right" in btn_name:
            btn = 2
        else:
            btn = 3

        if pressed:
            self._buttons_state |= (1 << (btn - 1))
        else:
            self._buttons_state &= ~(1 << (btn - 1))

        evt = InputEvent(
            type=InputEventType.BUTTON_PRESS if pressed else InputEventType.BUTTON_RELEASE,
            button=btn,
            timestamp=time.time()
        )
        self._try_put(evt)
        return True

    def _on_scroll(self, x: int, y: int, dx: int, dy: int):
        if not self._running:
            return False
        evt = InputEvent(
            type=InputEventType.WHEEL,
            wheel_delta=dy,
            timestamp=time.time()
        )
        self._try_put(evt)
        return True

    def _try_put(self, evt: InputEvent):
        try:
            # 合并连续移动事件
            if evt.type == InputEventType.MOVE and self._move_coalesce:
                while not self._queue.empty():
                    try:
                        item = self._queue.get_nowait()
                        if item.type != InputEventType.MOVE:
                            self._queue.put_nowait(item)  # 放回非移动事件
                            break
                    except queue.Empty:
                        break
            self._queue.put_nowait(evt)
        except queue.Full:
            # 队列满时丢弃旧移动事件
            if evt.type == InputEventType.MOVE:
                try:
                    self._queue.get_nowait()  # 丢弃最旧的
                    self._queue.put_nowait(evt)
                except (queue.Empty, queue.Full):
                    pass

    def get_event(self, timeout: float = 0.01) -> Optional[InputEvent]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_all_events(self) -> list:
        events = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events

    def set_current_position(self, x: int, y: int):
        """初始化/重置当前位置"""
        self._last_pos = (x, y)

    def clear_queue(self):
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
