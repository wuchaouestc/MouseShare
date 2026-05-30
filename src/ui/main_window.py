"""
MainWindow — MouseShare 主窗口

Tab 导航：设备列表 | 布局设置 | 状态
"""
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QWidget, QLabel, QMessageBox, QProgressDialog,
    QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QIcon

from src.ui.device_list import DeviceListWidget
from src.ui.layout_config import LayoutConfigWidget
from src.ui.status_page import StatusPageWidget
from src.shared.config import Config, load, save
from src.shared.bluetooth_scanner import pair_device


class PairThread(QThread):
    done = Signal(bool, str)

    def __init__(self, address):
        super().__init__()
        self._address = address

    def run(self):
        ok, msg = pair_device(self._address)
        self.done.emit(ok, msg)


class MainWindow(QMainWindow):
    def __init__(self, agent=None, config: Config = None):
        super().__init__()
        self.agent = agent
        self.config = config or load()
        self._manual_status = ""
        self._manual_status_until = 0
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("MouseShare")
        self.setMinimumSize(500, 420)
        self.resize(500, 420)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        # 顶部工具栏
        top_layout = QHBoxLayout()
        top_layout.addStretch()
        self.btn_settings = QPushButton("设置")
        self.btn_settings.clicked.connect(self._on_settings)
        top_layout.addWidget(self.btn_settings)
        layout.addLayout(top_layout)

        # Tab 导航
        self.tabs = QTabWidget()

        self.device_list = DeviceListWidget(self.config)
        self.layout_config = LayoutConfigWidget(self.config)
        self.status_page = StatusPageWidget(self.agent)

        self.tabs.addTab(self.device_list, "设备")
        self.tabs.addTab(self.layout_config, "布局")
        self.tabs.addTab(self.status_page, "状态")

        layout.addWidget(self.tabs)

        # 底部操作和状态栏
        btn_layout = QHBoxLayout()
        self.btn_connect = QPushButton("连接")
        self.btn_suspend = QPushButton("暂停")

        self.btn_connect.clicked.connect(self._on_connect)
        self.btn_suspend.clicked.connect(self._on_suspend)

        btn_layout.addWidget(self.btn_connect)
        btn_layout.addWidget(self.btn_suspend)
        btn_layout.addStretch(1)

        self.status_label = QLabel("就绪，等待选择设备或对端连接")
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.status_label.setMinimumWidth(280)
        self.status_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.status_label.setStyleSheet("color: #333; padding-left: 12px;")
        btn_layout.addWidget(self.status_label, 3)
        layout.addLayout(btn_layout)

        # 定时刷新状态
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_status)
        self._timer.start(1000)

        # 布局变更同步
        self.layout_config.layout_changed.connect(self._on_layout_changed)

    def _set_status(self, message: str, hold_seconds: float = 4.0):
        import time
        self._manual_status = message
        self._manual_status_until = time.time() + hold_seconds
        self.status_label.setText(message)
        self.status_page.append_log(message)

    def _refresh_status(self):
        import time
        if self._manual_status and time.time() < self._manual_status_until:
            return
        self._manual_status = ""
        if self.agent is None:
            self.status_label.setText("未启动")
            return
        state = getattr(self.agent, 'sm', None)
        if state is None:
            self.status_label.setText("未知")
            return
        s = state.state
        name_map = {
            2: "就绪", 3: "连接中...", 4: "已连接",
            5: "共享中 (主控)", 6: "共享中 (被控)",
            7: "已暂停", 8: "重连中...", 9: "退出"
        }
        role = getattr(self.agent, "role", "")
        role_text = {"peer": "等待连接", "host": "主控端", "target": "被控端"}.get(role, "")
        runtime_status = getattr(self.agent, "status_message", "")
        state_text = name_map.get(s.value, str(s))
        parts = [state_text]
        if role_text:
            parts.append(role_text)
        if runtime_status:
            parts.append(runtime_status)
        self.status_label.setText(" · ".join(parts))
        self.status_page.update_state(" · ".join(parts), role_text)

    def _on_connect(self):
        selected = self.device_list.get_selected_device()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择一个设备")
            return
        mac = selected.get("address", "")
        authenticated = selected.get("authenticated", False)
        if not authenticated:
            self._set_status(f"设备 {mac} 未配对，开始配对流程，请在对端确认", 8.0)
            self._do_pair_then_connect(selected, mac)
        else:
            self._set_status(f"设备 {mac} 已配对，正在连接", 6.0)
            self._do_connect(mac)

    def _do_pair_then_connect(self, device, mac):
        name = device.get("name") or mac
        dlg = QProgressDialog(f"正在与 {name} 配对，请在对端确认...", "取消", 0, 0, self)
        dlg.setWindowTitle("蓝牙配对")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)
        dlg.show()

        self._pair_thread = PairThread(mac)

        def on_done(ok, msg):
            dlg.close()
            if ok:
                device["authenticated"] = True
                self._set_status(f"配对成功：{name}，正在建立连接", 8.0)
                self._do_connect(mac)
            else:
                self._set_status(f"配对失败：{name}，{msg}", 10.0)
                QMessageBox.warning(self, "配对失败", msg)

        self._pair_thread.done.connect(on_done)
        dlg.canceled.connect(self._pair_thread.terminate)
        self._pair_thread.start()

    def _do_connect(self, mac):
        if self.agent:
            self._set_status(f"正在连接 {mac}", 6.0)
            self.agent.set_last_connection(mac)
            ok, err = self.agent.connect(mac)
            if ok:
                self.status_page.set_address(mac)
                role = getattr(self.agent, "role", "")
                role_text = {"host": "主控端", "target": "被控端", "peer": "等待连接"}.get(role, "主控端")
                self._set_status(f"连接成功：{mac}，当前角色：{role_text}", 8.0)
            else:
                self._set_status(f"连接失败：{mac}，{err}", 10.0)
                QMessageBox.warning(self, "连接失败", f"无法连接到 {mac}\n\n{err}")

    def _on_suspend(self):
        if self.agent:
            if self.agent.sm.is_controlling:
                self.agent.suspend()
                self.btn_suspend.setText("恢复")
            else:
                self.agent.resume()
                self.btn_suspend.setText("暂停")

    def _on_settings(self):
        QMessageBox.information(self, "MouseShare",
            f"配置路径: {self.config.__class__.__module__}\n"
            f"布局方向: {self.config.layout_direction}")

    def _on_layout_changed(self, direction: str):
        self.config.layout_direction = direction
        save(self.config)
        if self.agent:
            self.agent.set_direction(direction)

    def closeEvent(self, event):
        # 最小化到托盘，不退出
        event.ignore()
        self.hide()

    def set_agent(self, agent):
        self.agent = agent
        self.status_page.set_agent(agent)
