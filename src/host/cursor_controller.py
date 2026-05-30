"""
CursorController — Host 端光标锁定/解锁 + 紧急快捷键

进入远端控制时锁定本地光标在屏幕边缘，
退出时解锁。提供紧急解锁快捷键 (Ctrl+Alt+Shift+M)。
"""
import ctypes
import threading
import logging
from ctypes import wintypes

logger = logging.getLogger(__name__)

EMERGENCY_KEYS = {"ctrl", "alt", "shift", "m"}
EMERGENCY_MODS = {0x11: "ctrl", 0x12: "alt", 0x10: "shift"}  # VK codes


class CursorController:
    def __init__(self):
        self._locked = False
        self._lock_rect = None  # (left, top, right, bottom)
        self._emergency_thread = None
        self._emergency_running = False
        self._on_emergency_cb = None
        self._pressed_keys = set()

    def set_emergency_callback(self, cb):
        self._on_emergency_cb = cb

    def lock_at_edge(self, direction: str):
        """在屏幕边缘锁定光标"""
        try:
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)

            if direction == "right":
                rect = (w - 4, 0, w, h)
            elif direction == "left":
                rect = (0, 0, 4, h)
            elif direction == "down":
                rect = (0, h - 4, w, h)
            elif direction == "up":
                rect = (0, 0, w, 4)
            else:
                rect = (w - 4, 0, w, h)

            self._lock_rect = rect
            ct_rect = wintypes.RECT(*rect)
            ctypes.windll.user32.ClipCursor(ctypes.byref(ct_rect))
            self._locked = True
            logger.info(f"Cursor locked at {direction} edge")
        except Exception as e:
            logger.error(f"Cursor lock failed: {e}")

    def unlock(self):
        """解锁光标"""
        if not self._locked:
            return
        try:
            ctypes.windll.user32.ClipCursor(None)
            self._locked = False
            self._lock_rect = None
            logger.info("Cursor unlocked")
        except Exception as e:
            logger.error(f"Cursor unlock failed: {e}")

    @property
    def is_locked(self) -> bool:
        return self._locked

    def start_emergency_listener(self):
        """启动紧急快捷键监听线程"""
        if self._emergency_running:
            return
        self._emergency_running = True
        self._emergency_thread = threading.Thread(
            target=self._emergency_loop, daemon=True, name="EmergencyHotkey"
        )
        self._emergency_thread.start()
        logger.info("Emergency hotkey listener started (Ctrl+Alt+Shift+M)")

    def stop_emergency_listener(self):
        self._emergency_running = False

    def _emergency_loop(self):
        """使用 GetAsyncKeyState 轮询检测快捷键"""
        import time
        while self._emergency_running:
            try:
                keys_active = set()
                if ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000:  # Ctrl
                    keys_active.add("ctrl")
                if ctypes.windll.user32.GetAsyncKeyState(0x12) & 0x8000:  # Alt
                    keys_active.add("alt")
                if ctypes.windll.user32.GetAsyncKeyState(0x10) & 0x8000:  # Shift
                    keys_active.add("shift")
                if ctypes.windll.user32.GetAsyncKeyState(0x4D) & 0x8000:  # M
                    keys_active.add("m")

                if keys_active == EMERGENCY_KEYS:
                    logger.warning("EMERGENCY UNLOCK TRIGGERED")
                    self.unlock()
                    if self._on_emergency_cb:
                        self._on_emergency_cb()
                    time.sleep(0.5)  # 防抖

                time.sleep(0.05)
            except Exception:
                time.sleep(0.1)

    def cleanup(self):
        """清理资源"""
        self.stop_emergency_listener()
        self.unlock()
