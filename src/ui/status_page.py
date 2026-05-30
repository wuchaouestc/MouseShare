"""
StatusPageWidget — 连接状态与诊断信息
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout, QTextEdit
)
from PySide6.QtCore import Qt


class StatusPageWidget(QWidget):
    def __init__(self, agent=None, parent=None):
        super().__init__(parent)
        self.agent = agent
        self._address = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 连接信息
        group = QGroupBox("连接信息")
        form = QFormLayout()

        self.lbl_state = QLabel("未连接")
        self.lbl_state.setStyleSheet("font-weight: bold;")
        self.lbl_address = QLabel("—")
        self.lbl_latency = QLabel("—")
        self.lbl_role = QLabel("—")

        state_label = QLabel("状态:")
        state_label.setStyleSheet("font-weight: bold;")
        form.addRow(state_label, self.lbl_state)
        form.addRow("对端地址:", self.lbl_address)
        form.addRow("延迟:", self.lbl_latency)
        form.addRow("角色:", self.lbl_role)
        group.setLayout(form)
        layout.addWidget(group)

        # 日志
        group2 = QGroupBox("事件日志")
        log_layout = QVBoxLayout()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        log_layout.addWidget(self.log_view)
        group2.setLayout(log_layout)
        layout.addWidget(group2)

        layout.addStretch()

    def set_address(self, address: str):
        self._address = address
        self.lbl_address.setText(address)

    def set_agent(self, agent):
        self.agent = agent

    def update_state(self, state_name: str, role: str = ""):
        self.lbl_state.setText(state_name)
        if role:
            self.lbl_role.setText(role)

    def update_latency(self, p50: float, p95: float):
        self.lbl_latency.setText(f"P50={p50:.0f}ms  P95={p95:.0f}ms")

    def append_log(self, message: str):
        self.log_view.append(message)
        # 保持最近 500 行
        if self.log_view.document().blockCount() > 500:
            cursor = self.log_view.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor, 1)
            cursor.removeSelectedText()
