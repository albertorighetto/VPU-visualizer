"""
VPU Visualizer 2.0 Main Window

Layout:
- Header bar: app title, Pending/Current config switch, connection status pill,
  quick connect/disconnect, refresh, connection settings (gear).
- Tabs: VPU Map (responsive card grid), Screens & Layers (merged view with
  summary strip), Log (searchable/filterable).
"""

from PyQt6.QtCore import Qt, QTimer, QSettings, pyqtSlot
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QStatusBar, QTabWidget, QButtonGroup
)

from awj_client import AWJClient, RESOURCE_NEW, RESOURCE_CURRENT, MAX_PROC_SLOTS
from vpu_model import VPUModel
from vpu_widget import VPUWidget, HOVER_GRACE_MS
from screens_panel import ScreensPanel
from log_panel import LogPanel
from connection_dialog import ConnectionDialog
from flow_layout import FlowLayout
from theme import PALETTE

# How long to wait for a hardware-availability response before retrying the
# check for that VPU slot.
HW_CHECK_TIMEOUT_MS = 3000


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("VPU Visualizer")
        self.setMinimumSize(900, 600)
        self.resize(1400, 900)

        # Initialize client and model (both default to the pending "new" config)
        self.client = AWJClient(self)
        self.model = VPUModel(resource=RESOURCE_NEW)

        # Connect signals
        self.client.connecting.connect(self.on_connecting)
        self.client.connected.connect(self.on_connected)
        self.client.disconnected.connect(self.on_disconnected)
        self.client.error.connect(self.on_error)
        self.client.data_received.connect(self.on_data_received)
        self.client.debug_message.connect(self.on_debug_message)
        self.client.live_changed.connect(self.on_live_changed)

        self.vpu_widgets = {}
        self._vpu_seen_version = -1

        # Hardware-availability gating for VPU data fetches: (device_id, vpu_id) ->
        # retry timer while a check is outstanding, and the set of VPUs we've
        # already triggered a full data fetch for (avoids re-fetching on
        # duplicate availability responses).
        self._hw_check_timers = {}
        self._vpu_fetch_requested = set()

        self.setup_ui()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self._update_status_pill()

        # Update timer for UI refresh (only repaints when the model changed)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.refresh_display)
        self.update_timer.start(400)

        # Debounced clear for the pipe-cell dim/border hover state, mirroring
        # the pipe cell tooltip's own grace period (see vpu_widget.HOVER_GRACE_MS)
        # so crossing the thin gap between adjacent cells doesn't flash the
        # dim/highlight off and back on.
        self._hover_clear_timer = QTimer(self)
        self._hover_clear_timer.setSingleShot(True)
        self._hover_clear_timer.timeout.connect(self._clear_hover_state)

    # ------------------------------------------------------------------ UI

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 12, 16, 8)
        main_layout.setSpacing(8)

        main_layout.addWidget(self._build_header())

        # --- Tabs ---
        self.tab_widget = QTabWidget()

        # VPU Map tab: responsive flow of VPU cards
        vpu_tab = QWidget()
        vpu_layout = QVBoxLayout(vpu_tab)
        vpu_layout.setContentsMargins(0, 8, 0, 0)

        self.vpu_scroll = QScrollArea()
        self.vpu_scroll.setWidgetResizable(True)

        self.vpu_container = QWidget()
        self.vpu_flow = FlowLayout(self.vpu_container, margin=2, h_spacing=12, v_spacing=12)

        self.vpu_empty_label = QLabel("Not connected — open connection settings (⚙) to get started")
        self.vpu_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vpu_empty_label.setStyleSheet(f"color: {PALETTE['muted']}; padding: 60px;")
        self.vpu_flow.addWidget(self.vpu_empty_label)

        self.vpu_scroll.setWidget(self.vpu_container)
        vpu_layout.addWidget(self.vpu_scroll)

        self.tab_widget.addTab(vpu_tab, "VPU Map")

        # Screens & Layers tab (includes the summary strip)
        self.screens_panel = ScreensPanel(self.model)
        self.tab_widget.addTab(self.screens_panel, "Screens && Layers")

        # Log tab
        self.log_panel = LogPanel()
        self.tab_widget.addTab(self.log_panel, "Log")

        main_layout.addWidget(self.tab_widget)

    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title = QLabel("VPU Visualizer")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {PALETTE['text']};")
        layout.addWidget(title)

        layout.addStretch()

        # Config selector: pending ("new") vs current configuration
        segment_box = QFrame()
        segment_box.setObjectName("segmentBox")
        segment_layout = QHBoxLayout(segment_box)
        segment_layout.setContentsMargins(3, 3, 3, 3)
        segment_layout.setSpacing(2)

        self.btn_pending = QPushButton("Pending")
        self.btn_pending.setObjectName("segment")
        self.btn_pending.setCheckable(True)
        self.btn_pending.setChecked(True)
        self.btn_pending.setToolTip("Show the pending configuration (API: 'new')")

        self.btn_current = QPushButton("Current")
        self.btn_current.setObjectName("segment")
        self.btn_current.setCheckable(True)
        self.btn_current.setToolTip("Show the running configuration (API: 'current')")

        self.config_group = QButtonGroup(self)
        self.config_group.setExclusive(True)
        self.config_group.addButton(self.btn_pending)
        self.config_group.addButton(self.btn_current)
        self.config_group.buttonClicked.connect(self.on_config_switched)

        segment_layout.addWidget(self.btn_pending)
        segment_layout.addWidget(self.btn_current)
        layout.addWidget(segment_box)

        # Status pill
        self.status_pill = QFrame()
        self.status_pill.setStyleSheet(f"""
            QFrame {{
                background-color: {PALETTE['surface']};
                border: 1px solid {PALETTE['border_soft']};
                border-radius: 13px;
            }}
        """)
        pill_layout = QHBoxLayout(self.status_pill)
        pill_layout.setContentsMargins(12, 4, 12, 4)
        pill_layout.setSpacing(6)

        self.status_dot = QLabel("●")
        pill_layout.addWidget(self.status_dot)
        self.status_text = QLabel()
        self.status_text.setStyleSheet(
            f"color: {PALETTE['text_dim']}; font-size: 12px; border: none; background: transparent;")
        pill_layout.addWidget(self.status_text)

        layout.addWidget(self.status_pill)

        # Quick connect / disconnect with the saved address
        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("accent")
        self.connect_button.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_button)

        self.refresh_button = QPushButton("⟳")
        self.refresh_button.setObjectName("ghost")
        self.refresh_button.setToolTip("Refresh all data from the device")
        self.refresh_button.setEnabled(False)
        self.refresh_button.clicked.connect(self.refresh_data)
        layout.addWidget(self.refresh_button)

        settings_button = QPushButton("⚙")
        settings_button.setObjectName("ghost")
        settings_button.setToolTip("Connection settings")
        settings_button.clicked.connect(self.open_connection_settings)
        layout.addWidget(settings_button)

        return header

    # ------------------------------------------------------- Connection

    def open_connection_settings(self):
        dialog = ConnectionDialog(self.client, self)
        dialog.exec()

    def toggle_connection(self):
        if self.client.is_connected:
            self.client.disconnect()
        else:
            settings = QSettings()
            ip = settings.value("connection/ip", "127.0.0.1")
            port = int(settings.value("connection/port", 10606))
            self.start_connection(ip, port)

    def start_connection(self, ip: str, port: int):
        """Connect to a device (also called from the connection dialog)."""
        self.connect_button.setEnabled(False)
        self.client.connect_to_device(ip, port)

    def on_config_switched(self):
        """Switch between pending ('new') and current configuration trees."""
        resource = RESOURCE_NEW if self.btn_pending.isChecked() else RESOURCE_CURRENT
        if resource == self.model.resource:
            return

        self.client.set_resource(resource)
        self.model.set_resource(resource)
        self._update_status_pill()

        label = "pending" if resource == RESOURCE_NEW else "current"
        self.log_panel.append(f"[INFO] Switched to {label} configuration")

        if self.client.is_connected:
            self.reset_session()
            self.client.initialize_connection()
        else:
            self.reset_session()

    def refresh_data(self):
        """Refresh all data from the device."""
        if self.client.is_connected:
            self.log_panel.append("[INFO] Manual refresh - fetching all data...")
            self.reset_session()
            self.client.initialize_connection()

    def reset_session(self):
        """Clear all cached device/VPU/screen state and widgets ahead of a fresh fetch."""
        self.model.reset()

        for widget in self.vpu_widgets.values():
            widget.setParent(None)
            widget.deleteLater()
        self.vpu_widgets.clear()
        self._vpu_seen_version = -1

        for timer in self._hw_check_timers.values():
            timer.stop()
        self._hw_check_timers.clear()
        self._vpu_fetch_requested.clear()

    # ------------------------------------------------------- Status pill

    def _update_status_pill(self, state: str = None):
        """state: None (derive), 'connecting'."""
        if state == "connecting":
            color = PALETTE['amber']
            text = f"Connecting to {self.client.ip}:{self.client.port}…"
        elif self.client.is_connected:
            color = PALETTE['green']
            config = "pending" if self.model.resource == RESOURCE_NEW else "current"
            live = " · live" if self.client.is_live else ""
            text = f"{self.client.ip}:{self.client.port} · {config} config{live}"
        else:
            color = PALETTE['red']
            text = "Disconnected"

        self.status_dot.setStyleSheet(
            f"color: {color}; font-size: 11px; border: none; background: transparent;")
        self.status_text.setText(text)

    # ------------------------------------------------------- Client slots

    @pyqtSlot(str, int)
    def on_connecting(self, ip: str, port: int):
        self._update_status_pill("connecting")
        self.status_bar.showMessage(f"Connecting to {ip}:{port}…")

    def _repolish(self, widget):
        """Re-apply the app stylesheet after an objectName change."""
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    @pyqtSlot()
    def on_connected(self):
        self.connect_button.setText("Connected")
        self.connect_button.setObjectName("success")
        self.connect_button.setToolTip("Click to disconnect")
        self._repolish(self.connect_button)
        self.connect_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self._update_status_pill()
        self.status_bar.showMessage("Connected")
        self.reset_session()
        QTimer.singleShot(300, self.client.initialize_connection)

    @pyqtSlot()
    def on_disconnected(self):
        self.connect_button.setText("Connect")
        self.connect_button.setObjectName("accent")
        self.connect_button.setToolTip("")
        self._repolish(self.connect_button)
        self.connect_button.setEnabled(True)
        self.refresh_button.setEnabled(False)
        self._update_status_pill()
        self.status_bar.showMessage("Disconnected")
        # Leave the last known state visible until the next connect/refresh.

    @pyqtSlot(bool)
    def on_live_changed(self, live: bool):
        self._update_status_pill()

    @pyqtSlot(str)
    def on_error(self, message: str):
        self.status_bar.showMessage(f"Error: {message}")
        self.log_panel.append(f"[ERROR] {message}")
        self.connect_button.setEnabled(True)

    @pyqtSlot(dict)
    def on_data_received(self, data: dict):
        result = self.model.process_message(data)
        self.log_panel.append(f"[PARSED] {result}")

        # After receiving device type, check hardware availability for each
        # of its VPU slots (data is only fetched for slots that report available)
        if "[DEVICE]" in result and "vpus=" in result:
            self.request_vpu_data_for_device(data)

        if "[HARDWARE]" in result:
            self.on_hardware_availability(data)

        # After receiving screen layer count, request layer details
        if "[SCREEN]" in result and "layers=" in result:
            self.request_screen_layer_details(data)

        # After receiving screen active, request more details
        if "SCREEN" in result and "active=True" in result:
            self.request_screen_details(data)

    def request_vpu_data_for_device(self, data: dict):
        """Once a device's type is known, start a hardware availability check
        chain for its VPU slots - there's no static per-type VPU count table,
        so PROC_1 is always checked first and the real count is whatever
        polling finds. PROC cards populate a chassis contiguously from slot 1
        up, so slots are checked one at a time in order (on_hardware_availability
        requests the next slot once the current one comes back) instead of
        bashing every slot at once, and the chain stops at the first slot
        that isn't available."""
        path = data.get("path", "")
        match = self.model.REGEX_DEVICE_TYPE.match(path)
        if match:
            device_id = int(match.group(1))
            device = self.model.get_device(device_id)
            if device and device.device_type:
                self.log_panel.append(
                    f"[INFO] Device {device_id} ({device.device_type}) - polling "
                    f"hardware availability")
                self._maybe_request_hardware_check(device_id, 1)

    def on_hardware_availability(self, data: dict):
        """Handle a hardware/$card isAvailable response: fetch that VPU's data
        if available and move on to check the next slot in order; otherwise
        stop the chain for this device, since a missing slot means no higher
        slot can be populated either. Cancels its retry timer either way."""
        path = data.get("path", "")
        match = self.model.REGEX_VPU_HARDWARE_AVAILABLE.match(path)
        if not match:
            return
        device_id = int(match.group(1))
        vpu_id = int(match.group(2))

        timer = self._hw_check_timers.pop((device_id, vpu_id), None)
        if timer:
            timer.stop()

        device = self.model.get_device(device_id)
        if not device:
            return

        if device.hardware_available.get(vpu_id):
            if (device_id, vpu_id) not in self._vpu_fetch_requested:
                self._vpu_fetch_requested.add((device_id, vpu_id))
                self.client.fetch_vpu_data(device_id, vpu_id)
            if vpu_id < MAX_PROC_SLOTS:
                self._maybe_request_hardware_check(device_id, vpu_id + 1)
        else:
            self.log_panel.append(
                f"[INFO] Device {device_id}, VPU {vpu_id}: hardware not available, "
                f"stopping availability check for remaining slot(s)")

    def _maybe_request_hardware_check(self, device_id: int, vpu_id: int):
        """Send a hardware-availability check for one VPU slot, unless one is
        already outstanding or the answer is already known."""
        key = (device_id, vpu_id)
        if key in self._hw_check_timers:
            return
        device = self.model.get_device(device_id)
        if device and device.hardware_available.get(vpu_id) is not None:
            return
        self._request_hardware_check(device_id, vpu_id)

    def _request_hardware_check(self, device_id: int, vpu_id: int):
        self.client.check_hardware_card_available(device_id, vpu_id)

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(
            lambda d=device_id, v=vpu_id: self._on_hardware_check_timeout(d, v))
        self._hw_check_timers[(device_id, vpu_id)] = timer
        timer.start(HW_CHECK_TIMEOUT_MS)

    def _on_hardware_check_timeout(self, device_id: int, vpu_id: int):
        """No isAvailable response within HW_CHECK_TIMEOUT_MS - ask again."""
        self._hw_check_timers.pop((device_id, vpu_id), None)

        if not self.client.is_connected:
            return
        device = self.model.get_device(device_id)
        if device and device.hardware_available.get(vpu_id) is not None:
            return  # answered just as the timer fired

        self.log_panel.append(
            f"[INFO] Device {device_id}, VPU {vpu_id}: no availability response "
            f"after {HW_CHECK_TIMEOUT_MS // 1000}s, retrying")
        self._request_hardware_check(device_id, vpu_id)

    def request_screen_layer_details(self, data: dict):
        """Request layer details after screen layer count is received."""
        path = data.get("path", "")
        match = self.model.REGEX_SCREEN_LAYER_COUNT.match(path)
        if match:
            screen_id = int(match.group(1))
            screen = self.model.get_screen(screen_id)
            if screen and len(screen.layers) > 0:
                self.client.fetch_screen_details(screen_id, len(screen.layers))

    def request_screen_details(self, data: dict):
        """Request additional screen details after screen is found active.
        isOptimized/isStereo3d/regionValidity are screen-level properties,
        independent of whether the screen has any layers, so they're
        requested here rather than gated behind the layer-count fetch below."""
        path = data.get("path", "")
        match = self.model.REGEX_SCREEN_MODE.match(path)
        if match:
            screen_id = int(match.group(1))
            self.client.get_screen_layer_count(screen_id)
            self.client.get_screen_optimized(screen_id)
            self.client.get_screen_stereo3d(screen_id)
            self.client.get_screen_region_validity(screen_id)

    @pyqtSlot(str)
    def on_debug_message(self, message: str):
        self.log_panel.append(message)

    # ------------------------------------------------------- Display refresh

    def refresh_display(self):
        """Refresh panels, but only when the model actually changed."""
        self.screens_panel.refresh()

        if self.model.version == self._vpu_seen_version:
            return
        self._vpu_seen_version = self.model.version
        self.refresh_vpu_widgets()

    def refresh_vpu_widgets(self):
        """Refresh VPU visualization widgets."""
        for device in self.model.active_devices():
            for vpu in device.vpus:
                key = (device.id, vpu.vpu_id)

                # Hardware confirmed this VPU slot isn't populated - don't show a card for it.
                if device.hardware_available.get(vpu.vpu_id) is False:
                    stale = self.vpu_widgets.pop(key, None)
                    if stale:
                        stale.setParent(None)
                        stale.deleteLater()
                    continue

                if key not in self.vpu_widgets:
                    widget = VPUWidget(device, vpu, self.model)
                    self.vpu_widgets[key] = widget
                    self.vpu_flow.addWidget(widget)

                    # Connect hover signals (forwarded from whichever pipe cell is
                    # hovered - the grid can rebuild and replace individual cells)
                    widget.cell_hovered.connect(self.on_scaler_hovered)
                    widget.cell_left.connect(self.on_scaler_left)
                    widget.device_hovered.connect(self.on_device_hovered)
                    widget.device_left.connect(self.on_device_left)

                self.vpu_widgets[key].update_display()

        # Enforce device-then-VPU order in the card grid regardless of the
        # order API messages arrived in (e.g. a device whose type arrives
        # late would otherwise get its cards appended after later devices').
        ordered_widgets = [self.vpu_widgets[key] for key in self.model.ordered_vpu_keys()
                            if key in self.vpu_widgets]
        self.vpu_flow.reorder(ordered_widgets)

        self.vpu_empty_label.setVisible(not self.vpu_widgets)

    def on_scaler_hovered(self, scaler):
        """Dim every non-matching layer and border the exact screen+layer+slice
        match, across all VPU cards. Cancels any pending clear from a just-left
        cell, so crossing the gap into this one reads as continuous."""
        self._hover_clear_timer.stop()
        for vpu_widget in self.vpu_widgets.values():
            vpu_widget.set_hover_state(scaler)

    def on_scaler_left(self):
        """Clear dim/border state after a short grace period (see HOVER_GRACE_MS),
        so briefly crossing the gap between two cells doesn't flicker it off."""
        self._hover_clear_timer.start(HOVER_GRACE_MS)

    def _clear_hover_state(self):
        for vpu_widget in self.vpu_widgets.values():
            vpu_widget.set_hover_state(None)

    def on_device_hovered(self, device_id: int):
        """Subtly highlight all VPU cards belonging to the hovered device."""
        for (dev_id, _), widget in self.vpu_widgets.items():
            widget.set_device_highlight(dev_id == device_id)

    def on_device_left(self, device_id: int):
        for widget in self.vpu_widgets.values():
            widget.set_device_highlight(False)

    def closeEvent(self, event):
        if self.client.is_connected:
            self.client.disconnect()
        event.accept()
