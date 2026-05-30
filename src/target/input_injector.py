"""
InputInjector — Target 端使用 SendInput API 注入鼠标事件
"""
import ctypes
import logging
from ctypes import wintypes

logger = logging.getLogger(__name__)

# Win32 SendInput constants
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000
MOUSEEVENTF_ABSOLUTE = 0x8000
WHEEL_DELTA = 120


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("mi", MOUSEINPUT),
    ]


class InputInjector:
    """使用 SendInput 向当前系统注入鼠标事件"""

    def __init__(self):
        self._send_input = ctypes.windll.user32.SendInput
        self._send_input.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), wintypes.INT]
        self._send_input.restype = wintypes.UINT

    def move(self, dx: int, dy: int):
        """注入相对移动"""
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dx = dx
        inp.mi.dy = dy
        inp.mi.dwFlags = MOUSEEVENTF_MOVE
        result = self._send_input(1, ctypes.byref(inp), ctypes.sizeof(inp))
        if result == 0:
            logger.error(f"SendInput MOVE failed, dx={dx}, dy={dy}")

    def button_press(self, button: int):
        """注入按键按下: 1=左键, 2=右键, 3=中键"""
        flags = {
            1: MOUSEEVENTF_LEFTDOWN,
            2: MOUSEEVENTF_RIGHTDOWN,
            3: MOUSEEVENTF_MIDDLEDOWN,
        }.get(button)
        if flags is None:
            return
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dwFlags = flags
        result = self._send_input(1, ctypes.byref(inp), ctypes.sizeof(inp))
        if result == 0:
            logger.warning(f"SendInput PRESS button={button} failed (UIPI?)")

    def button_release(self, button: int):
        """注入按键释放"""
        flags = {
            1: MOUSEEVENTF_LEFTUP,
            2: MOUSEEVENTF_RIGHTUP,
            3: MOUSEEVENTF_MIDDLEUP,
        }.get(button)
        if flags is None:
            return
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dwFlags = flags
        result = self._send_input(1, ctypes.byref(inp), ctypes.sizeof(inp))
        if result == 0:
            logger.warning(f"SendInput RELEASE button={button} failed (UIPI?)")

    def wheel(self, delta: int, horizontal: bool = False):
        """注入滚轮事件"""
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.mouseData = delta * WHEEL_DELTA
        inp.mi.dwFlags = MOUSEEVENTF_HWHEEL if horizontal else MOUSEEVENTF_WHEEL
        result = self._send_input(1, ctypes.byref(inp), ctypes.sizeof(inp))
        if result == 0:
            logger.warning(f"SendInput WHEEL delta={delta} failed")

    def check_uipi(self) -> bool:
        """检测当前是否有高完整性窗口阻挡注入"""
        try:
            test_inp = INPUT()
            test_inp.type = INPUT_MOUSE
            test_inp.mi.dwFlags = MOUSEEVENTF_MOVE
            test_inp.mi.dx = 0
            test_inp.mi.dy = 0
            result = self._send_input(1, ctypes.byref(test_inp), ctypes.sizeof(test_inp))
            return result > 0
        except Exception:
            return False
