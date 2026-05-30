"""
DeviceListWidget — 已配对蓝牙设备列表
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QLabel
)
from PySide6.QtCore import Qt, Signal
from src.shared.config import Config
import socket


class DeviceListWidget(QWidget):
    device_selected = Signal(dict)

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
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
        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self._load_devices)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_refresh)
        layout.addLayout(btn_layout)

    def _load_devices(self):
        self.list_widget.clear()
        devices = self._get_paired_devices()
        for dev in devices:
            item = QListWidgetItem(f"{dev['name']}\n{dev['address']}")
            item.setData(Qt.UserRole, dev)
            self.list_widget.addItem(item)

    def _get_paired_devices(self):
        """获取 Windows 已配对蓝牙设备"""
        devices = []
        try:
            # 尝试使用 PyBluez
            import bluetooth
            nearby = bluetooth.discover_devices(duration=3, lookup_names=True)
            for addr, name in nearby:
                devices.append({"name": name, "address": addr})
        except ImportError:
            # 备用方案：从配置中读取已知设备
            pass

        # 从配置加载已信任设备
        for dev in self.config.trusted_devices:
            if not any(d.get("address") == dev.get("address") for d in devices):
                devices.append(dev)

        return devices

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
        self.list_widget.addItem(f"{name}\n{address}")
        # 持久化
        if dev not in self.config.trusted_devices:
            self.config.trusted_devices.append(dev)
