"""
DeviceListWidget — 已配对蓝牙设备列表
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QLabel
)
from PySide6.QtCore import Qt, Signal, QThread
from src.shared.config import Config
from src.shared.bluetooth_scanner import get_windows_bluetooth_devices

class ScannerThread(QThread):
    devices_found = Signal(list)

    def run(self):
        devices = []
        try:
            # 优先尝试使用 PyBluez
            import bluetooth
            nearby = bluetooth.discover_devices(duration=3, lookup_names=True)
            for addr, name in nearby:
                devices.append({"name": name, "address": addr})
        except ImportError:
            # 备用方案：Windows 原生 API
            devices = get_windows_bluetooth_devices()
        
        self.devices_found.emit(devices)


class DeviceListWidget(QWidget):
    device_selected = Signal(dict)

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self._scanner_thread = None
        self._init_ui()
        self._load_devices()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        label = QLabel("已配对蓝牙设备")
        label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(label)

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
        
        # 先加载已知设备
        self._populate_list([])
        
        # 启动扫描线程
        self._scanner_thread = ScannerThread()
        self._scanner_thread.devices_found.connect(self._on_scan_finished)
        self._scanner_thread.start()

    def _on_scan_finished(self, found_devices):
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("刷新")
        self._populate_list(found_devices)

    def _populate_list(self, scanned_devices):
        self.list_widget.clear()
        
        devices = list(scanned_devices)
        
        # 合并配置中的信任设备
        for dev in self.config.trusted_devices:
            if not any(d.get("address") == dev.get("address") for d in devices):
                devices.append(dev)

        for dev in devices:
            name = dev.get('name')
            if not name:
                name = "未知设备"
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
        # 持久化
        if not any(d.get("address") == address for d in self.config.trusted_devices):
            self.config.trusted_devices.append(dev)
            self.list_widget.addItem(f"{name}\n{address}")
