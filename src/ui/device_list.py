from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QLabel, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QThread
from src.shared.config import Config
from src.shared.bluetooth_scanner import get_combined_bluetooth_devices


SCAN_ATTEMPTS = (6, 10, 12)


class ScannerThread(QThread):
    devices_found = Signal(list)
    scan_progress = Signal(int, int)
    scan_error = Signal(str)

    def __init__(self, only_computers: bool):
        super().__init__()
        self.only_computers = only_computers

    def run(self):
        last_devices = []
        try:
            for idx, timeout in enumerate(SCAN_ATTEMPTS, start=1):
                self.scan_progress.emit(idx, len(SCAN_ATTEMPTS))
                devices = get_combined_bluetooth_devices(
                    only_computers=self.only_computers,
                    issue_inquiry=True,
                    timeout_multiplier=timeout,
                )
                last_devices = devices
                if devices:
                    break
            self.devices_found.emit(last_devices)
        except Exception as e:
            self.scan_error.emit(str(e))
            self.devices_found.emit([])


class DeviceListWidget(QWidget):
    device_selected = Signal(dict)

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self._scanner_thread = None
        self._last_scanned_devices = []
        self._init_ui()
        self._load_devices()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        label = QLabel("周围的蓝牙设备")
        label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.chk_only_computers = QCheckBox("只显示电脑设备")
        self.chk_only_computers.setChecked(True)
        self.chk_only_computers.stateChanged.connect(self._on_filter_changed)
        header_layout.addWidget(label)
        header_layout.addStretch()
        header_layout.addWidget(self.chk_only_computers)
        layout.addLayout(header_layout)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.status_label)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self._load_devices)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_refresh)
        layout.addLayout(btn_layout)

    def _load_devices(self):
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("扫描中...")
        self.status_label.setText("正在扫描周围蓝牙电脑，请稍候...")
        self.list_widget.clear()

        self._scanner_thread = ScannerThread(self.chk_only_computers.isChecked())
        self._scanner_thread.devices_found.connect(self._on_scan_finished)
        self._scanner_thread.scan_progress.connect(self._on_scan_progress)
        self._scanner_thread.scan_error.connect(self._on_scan_error)
        self._scanner_thread.start()

    def _on_scan_progress(self, current: int, total: int):
        if current == 1:
            self.status_label.setText("正在扫描周围蓝牙电脑，请稍候...")
        else:
            self.status_label.setText(
                f"未发现设备，正在重试（{current}/{total}），请保持对端蓝牙处于可发现状态..."
            )

    def _on_scan_error(self, msg: str):
        self.status_label.setText(f"扫描失败: {msg}")

    def _on_scan_finished(self, found_devices):
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("刷新")
        self._last_scanned_devices = list(found_devices)
        self._populate_list(self._last_scanned_devices)

    def _on_filter_changed(self):
        self._populate_list(self._last_scanned_devices)

    def _is_computer_device(self, dev: dict) -> bool:
        major = dev.get("major_class")
        return major in (None, 0, 1, 31)

    def _populate_list(self, scanned_devices):
        self.list_widget.clear()

        only_computers = self.chk_only_computers.isChecked()
        devices = [d for d in scanned_devices if not only_computers or self._is_computer_device(d)]

        for dev in self.config.trusted_devices:
            if only_computers and not self._is_computer_device(dev):
                continue
            if not any(d.get("address") == dev.get("address") for d in devices):
                devices.append(dev)

        if not devices:
            if only_computers:
                self.status_label.setText("未发现周围蓝牙电脑。可取消右上角过滤查看全部设备。")
            else:
                self.status_label.setText("未发现周围蓝牙设备。请确认对端蓝牙已开启且可被发现。")
            return

        self.status_label.setText(f"发现 {len(devices)} 台设备")
        for dev in devices:
            name = dev.get("name") or "未知设备"
            item = QListWidgetItem(f"{name}\n{dev['address']}")
            item.setData(Qt.UserRole, dev)
            self.list_widget.addItem(item)

    def _on_selection_changed(self, current, previous):
        if current:
            dev = current.data(Qt.UserRole)
            self.device_selected.emit(dev)

    def get_selected_device(self) -> dict:
        item = self.list_widget.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return {}

    def add_device(self, name: str, address: str):
        dev = {"name": name, "address": address}
        if not any(d.get("address") == address for d in self.config.trusted_devices):
            self.config.trusted_devices.append(dev)
            item = QListWidgetItem(f"{name}\n{address}")
            item.setData(Qt.UserRole, dev)
            self.list_widget.addItem(item)
