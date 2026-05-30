"""
TrayIcon — 系统托盘图标和右键菜单

5 种状态：灰(未连接) / 蓝(已连接) / 绿(共享中) / 黄(重连中) / 红(错误)
"""
import os
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QAction
from PySide6.QtCore import QObject, Signal

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets")


def _make_icon(color: str) -> QIcon:
    """生成纯色圆点图标"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))  # 透明背景
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)
    painter.setBrush(c)
    painter.setPen(c)
    painter.drawEllipse(4, 4, 24, 24)
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QSystemTrayIcon):
    open_requested = Signal()
    suspend_toggled = Signal()
    reconnect_requested = Signal()
    exit_requested = Signal()

    STATE_ICONS = {
        "disconnected": "#888888",   # 灰色
        "connected": "#0066CC",      # 蓝色
        "hosting": "#00AA00",        # 绿色
        "recovering": "#FFAA00",     # 黄色
        "error": "#CC0000",          # 红色
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suspended = False
        self._init_menu()
        self.set_icon_state("disconnected")
        self.setToolTip("MouseShare — 未连接")

        self.activated.connect(self._on_activated)
        self.show()

    def _init_menu(self):
        self.menu = QMenu()

        self.action_open = QAction("打开 MouseShare")
        self.action_open.triggered.connect(self.open_requested.emit)
        self.menu.addAction(self.action_open)

        self.menu.addSeparator()

        self.action_suspend = QAction("暂停共享")
        self.action_suspend.triggered.connect(self._on_suspend_toggle)
        self.menu.addAction(self.action_suspend)

        self.action_reconnect = QAction("重新连接")
        self.action_reconnect.triggered.connect(self.reconnect_requested.emit)
        self.menu.addAction(self.action_reconnect)

        self.menu.addSeparator()

        self.action_exit = QAction("退出")
        self.action_exit.triggered.connect(self.exit_requested.emit)
        self.menu.addAction(self.action_exit)

        self.setContextMenu(self.menu)

    def set_icon_state(self, state: str):
        color = self.STATE_ICONS.get(state, "#888888")
        self.setIcon(_make_icon(color))

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.open_requested.emit()

    def _on_suspend_toggle(self):
        self._suspended = not self._suspended
        if self._suspended:
            self.action_suspend.setText("恢复共享")
        else:
            self.action_suspend.setText("暂停共享")
        self.suspend_toggled.emit()

    def show_notification(self, title: str, message: str):
        self.showMessage(title, message, QSystemTrayIcon.Information, 3000)
