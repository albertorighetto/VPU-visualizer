"""
Connection settings dialog - connection is a setting, not a tab.
Stores the last used address via QSettings.
"""

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QSpinBox, QPushButton
)

from theme import PALETTE


class ConnectionDialog(QDialog):
    """Modal dialog with device address settings and connect/disconnect."""

    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("Connection")
        self.setModal(True)
        self.setMinimumWidth(340)

        settings = QSettings()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Device connection")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.ip_input = QLineEdit(settings.value("connection/ip", "127.0.0.1"))
        self.ip_input.setPlaceholderText("IP address")
        form.addRow("IP address", self.ip_input)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(int(settings.value("connection/port", 10606)))
        form.addRow("Port", self.port_input)

        layout.addLayout(form)

        self.status_label = QLabel()
        self.status_label.setStyleSheet(f"color: {PALETTE['text_dim']}; font-size: 12px;")
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        buttons.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("ghost")
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.close_btn)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setObjectName("danger")
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        buttons.addWidget(self.disconnect_btn)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("accent")
        self.connect_btn.clicked.connect(self._on_connect)
        buttons.addWidget(self.connect_btn)

        layout.addLayout(buttons)

        self._sync_state()

    def _sync_state(self):
        connected = self.client.is_connected
        self.connect_btn.setVisible(not connected)
        self.disconnect_btn.setVisible(connected)
        self.ip_input.setEnabled(not connected)
        self.port_input.setEnabled(not connected)
        if connected:
            self.status_label.setText(f"Connected to {self.client.ip}:{self.client.port}")
        else:
            self.status_label.setText("Not connected")

    def _on_connect(self):
        ip = self.ip_input.text().strip()
        if not ip:
            self.status_label.setText("Please enter an IP address")
            return
        port = self.port_input.value()

        settings = QSettings()
        settings.setValue("connection/ip", ip)
        settings.setValue("connection/port", port)

        self.accept()
        self.parent().start_connection(ip, port)

    def _on_disconnect(self):
        self.client.disconnect()
        self._sync_state()
