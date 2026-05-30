"""
LayoutConfigWidget — 设备布局设置（九宫格）
"""
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QPushButton, QLabel, QVBoxLayout
)
from PySide6.QtCore import Signal, Qt
from src.shared.config import Config


class LayoutConfigWidget(QWidget):
    layout_changed = Signal(str)

    DIRECTIONS = {
        (0, 1): "up",
        (1, 0): "left",
        (1, 2): "right",
        (2, 1): "down",
    }

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self._buttons = {}
        self._selected = None
        self._init_ui()
        self._restore_selection()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        label = QLabel("设备布局设置（对端在哪个方向）")
        label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(label)

        grid = QGridLayout()
        grid.setSpacing(4)

        for (row, col), direction in self.DIRECTIONS.items():
            label_map = {"up": "▲ 上方", "down": "▼ 下方", "left": "◀ 左侧", "right": "▶ 右侧"}
            text = label_map[direction]
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setMinimumSize(100, 60)
            btn.setStyleSheet("""
                QPushButton { border: 2px solid #ccc; border-radius: 6px; font-size: 13px; }
                QPushButton:checked { border-color: #0066CC; background: #e0edff; }
            """)
            btn.clicked.connect(lambda checked, d=direction, b=btn: self._on_select(d, b))
            grid.addWidget(btn, row, col)
            self._buttons[direction] = btn

        # 中间放本机标识
        center = QLabel("本机")
        center.setAlignment(Qt.AlignCenter)
        center.setStyleSheet("background: #f0f0f0; border-radius: 6px; font-size: 12px;")
        center.setMinimumSize(100, 60)
        grid.addWidget(center, 1, 1)

        layout.addLayout(grid)
        layout.addStretch()

    def _on_select(self, direction: str, button: QPushButton):
        # 取消其他按钮选中
        for d, btn in self._buttons.items():
            btn.setChecked(btn == button)
        self._selected = direction
        self.layout_changed.emit(direction)

    def _restore_selection(self):
        direction = self.config.layout_direction
        if direction in self._buttons:
            self._buttons[direction].setChecked(True)
            self._selected = direction

    def get_direction(self) -> str:
        return self._selected or self.config.layout_direction
