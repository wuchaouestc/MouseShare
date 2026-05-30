"""
BoundaryEngine — 屏幕边界检测引擎

检测鼠标是否到达屏幕设定的目标边缘，
触发进入/离开远端控制模式。
"""
import ctypes
import logging
from ctypes import wintypes
from enum import Enum

logger = logging.getLogger(__name__)

class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"

# 边缘检测阈值 (像素)
BOUNDARY_THRESHOLD = 2

class BoundaryEngine:
    def __init__(self, direction: Direction = Direction.RIGHT, dead_zone: int = 8):
        self.direction = direction
        self.dead_zone = dead_zone
        self._screen_w = 0
        self._screen_h = 0
        self._entered = False
        self._on_enter_cb = None
        self._on_leave_cb = None

    def set_direction(self, direction: Direction):
        self.direction = direction
        self._entered = False
        logger.info(f"Layout direction set to: {direction.value}")

    def set_callbacks(self, on_enter, on_leave):
        self._on_enter_cb = on_enter
        self._on_leave_cb = on_leave

    def _get_screen_size(self) -> tuple:
        """获取主显示器尺寸"""
        try:
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            return w, h
        except Exception:
            return self._screen_w or 1920, self._screen_h or 1080

    def _get_cursor_pos(self) -> tuple:
        """获取当前光标位置"""
        try:
            user32 = ctypes.windll.user32
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            return pt.x, pt.y
        except Exception:
            return 0, 0

    def is_in_dead_zone(self, x: int, y: int, w: int, h: int) -> bool:
        """检测是否在死角区域（四角）"""
        dz = self.dead_zone
        corners = [
            (0 <= x <= dz and 0 <= y <= dz),                    # 左上
            (w - dz <= x <= w and 0 <= y <= dz),                # 右上
            (0 <= x <= dz and h - dz <= y <= h),                # 左下
            (w - dz <= x <= w and h - dz <= y <= h),            # 右下
        ]
        return any(corners)

    def check(self) -> bool:
        """检查光标是否到达边界。返回 True 表示进入远端控制区域。"""
        w, h = self._get_screen_size()
        x, y = self._get_cursor_pos()

        # 检测死角
        if self.is_in_dead_zone(x, y, w, h):
            if self._entered:
                self._entered = False
                if self._on_leave_cb:
                    self._on_leave_cb()
            return False

        at_edge = False
        if self.direction == Direction.RIGHT and x >= w - BOUNDARY_THRESHOLD:
            at_edge = True
        elif self.direction == Direction.LEFT and x <= BOUNDARY_THRESHOLD:
            at_edge = True
        elif self.direction == Direction.DOWN and y >= h - BOUNDARY_THRESHOLD:
            at_edge = True
        elif self.direction == Direction.UP and y <= BOUNDARY_THRESHOLD:
            at_edge = True

        if at_edge and not self._entered:
            self._entered = True
            if self._on_enter_cb:
                self._on_enter_cb(self.direction)
            return True

        if not at_edge and self._entered:
            self._entered = False
            if self._on_leave_cb:
                self._on_leave_cb()

        return at_edge

    @property
    def entered(self) -> bool:
        return self._entered

    def reset(self):
        self._entered = False
