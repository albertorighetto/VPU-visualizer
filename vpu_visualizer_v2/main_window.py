"""
VPU Visualizer 2.0 Main Window
Main application window with connection controls and VPU display.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox, QScrollArea,
    QTextEdit, QStatusBar, QSpinBox, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont

from awj_client import AWJClient
from vpu_model import VPUModel
from vpu_widget import VPUWidget, ScreenWidget, LayersTableWidget


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("VPU Visualizer 2.0")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # Initialize client and model
        self.client = AWJClient(self)
        self.model = VPUModel()
        
        # Connect signals
        self.client.connected.connect(self.on_connected)
        self.client.disconnected.connect(self.on_disconnected)
        self.client.error.connect(self.on_error)
        self.client.data_received.connect(self.on_data_received)
        self.client.debug_message.connect(self.on_debug_message)
        
        # Model update callback
        self.model.add_update_callback(self.on_model_updated)
        
        # Setup UI
        self.setup_ui()
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Not connected")
        
        # Update timer for UI refresh
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh_display)
        self.update_timer.start(500)  # Refresh every 500ms
    
    def setup_ui(self):
        """Setup the main UI layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Single top-level tab widget for the whole app
        self.tab_widget = QTabWidget()

        # Connection Tab
        self.connection_tab = self.create_connection_tab()
        self.tab_widget.addTab(self.connection_tab, "Connection")

        # VPU Tab
        self.vpu_tab = QWidget()
        vpu_tab = self.vpu_tab
        vpu_layout = QVBoxLayout(vpu_tab)

        self.vpu_scroll = QScrollArea()
        self.vpu_scroll.setWidgetResizable(True)
        self.vpu_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.vpu_container = QWidget()
        self.vpu_grid = QGridLayout(self.vpu_container)
        self.vpu_grid.setSpacing(15)
        self.vpu_grid.setContentsMargins(10, 10, 10, 10)

        self.vpu_scroll.setWidget(self.vpu_container)
        vpu_layout.addWidget(self.vpu_scroll)

        self.tab_widget.addTab(vpu_tab, "VPU Usage")

        # Screens Tab
        screens_tab = QWidget()
        screens_layout = QVBoxLayout(screens_tab)

        self.screens_scroll = QScrollArea()
        self.screens_scroll.setWidgetResizable(True)

        self.screens_container = QWidget()
        self.screens_grid = QGridLayout(self.screens_container)
        self.screens_grid.setSpacing(10)
        self.screens_grid.setContentsMargins(10, 10, 10, 10)

        self.screens_scroll.setWidget(self.screens_container)
        screens_layout.addWidget(self.screens_scroll)

        self.tab_widget.addTab(screens_tab, "Screens")

        # Layers Tab
        layers_tab = QWidget()
        layers_layout = QVBoxLayout(layers_tab)

        self.layers_table = LayersTableWidget(self.model)
        layers_layout.addWidget(self.layers_table)

        self.tab_widget.addTab(layers_tab, "Layers")

        # Summary Tab
        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setFont(QFont("Consolas", 10))
        summary_layout.addWidget(self.summary_text)

        self.tab_widget.addTab(summary_tab, "Summary")

        # Debug Log Tab
        debug_tab = self.create_debug_tab()
        self.tab_widget.addTab(debug_tab, "Debug Log")

        main_layout.addWidget(self.tab_widget)

        # VPU widgets storage
        self.vpu_widgets = {}
        self.screen_widgets = {}

        # Focus the Connection tab at opening
        self.tab_widget.setCurrentWidget(self.connection_tab)

    def create_connection_tab(self) -> QWidget:
        """Create the connection settings tab."""
        tab = QWidget()
        outer_layout = QVBoxLayout(tab)

        header = QGroupBox("Connection")
        layout = QHBoxLayout(header)

        # Title
        title_label = QLabel("VPU Visualizer")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #826bff;")
        layout.addWidget(title_label)

        layout.addStretch()

        # IP Address
        layout.addWidget(QLabel("IP:"))
        self.ip_input = QLineEdit("127.0.0.1")
        self.ip_input.setFixedWidth(150)
        self.ip_input.setPlaceholderText("IP Address")
        layout.addWidget(self.ip_input)

        # Port
        layout.addWidget(QLabel("Port:"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(10606)
        self.port_input.setFixedWidth(80)
        layout.addWidget(self.port_input)

        # Connect button
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_button)

        # Refresh button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_data)
        self.refresh_button.setEnabled(False)
        layout.addWidget(self.refresh_button)

        # Connection status indicator
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: #cc2e60; font-size: 20px;")
        layout.addWidget(self.status_indicator)

        outer_layout.addWidget(header)
        outer_layout.addStretch()

        return tab

    def create_debug_tab(self) -> QWidget:
        """Create the debug/log tab."""
        panel = QGroupBox("Debug Log")
        layout = QVBoxLayout(panel)

        # Debug text area
        self.debug_text = QTextEdit()
        self.debug_text.setReadOnly(True)
        self.debug_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.debug_text)

        # Clear button
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.debug_text.clear)
        layout.addWidget(clear_btn)

        return panel
    
    def toggle_connection(self):
        """Toggle connection state."""
        if self.client.is_connected:
            self.client.disconnect()
        else:
            ip = self.ip_input.text().strip()
            port = self.port_input.value()
            
            if not ip:
                self.on_error("Please enter an IP address")
                return
            
            self.status_bar.showMessage(f"Connecting to {ip}:{port}...")
            self.connect_button.setEnabled(False)
            
            if self.client.connect_to_device(ip, port):
                # Initialize after connection
                QTimer.singleShot(500, self.client.initialize_connection)
    
    def refresh_data(self):
        """Refresh all data from the device."""
        if self.client.is_connected:
            self.add_debug("[INFO] ========================================")
            self.add_debug("[INFO] MANUAL REFRESH - Fetching all data...")
            self.add_debug("[INFO] ========================================")
            self.reset_session()
            self.client.initialize_connection()

            # Request VPU data for all devices that have been initialized
            for device in self.model.devices:
                if device.device_type and device.vpu_count > 0:
                    self.client.fetch_all_vpu_data(device.id, device.vpu_count)

    def reset_session(self):
        """Clear all cached device/VPU/screen state and widgets ahead of a fresh fetch."""
        self.model.reset()

        for widget in self.vpu_widgets.values():
            widget.setParent(None)
            widget.deleteLater()
        self.vpu_widgets.clear()

        for widget in self.screen_widgets.values():
            widget.setParent(None)
            widget.deleteLater()
        self.screen_widgets.clear()

        self.layers_table.populate_from_model()
        self.summary_text.clear()
    
    @pyqtSlot()
    def on_connected(self):
        """Handle successful connection."""
        self.connect_button.setText("Disconnect")
        self.connect_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.status_indicator.setStyleSheet("color: #8bb650; font-size: 20px;")
        self.status_bar.showMessage("Connected")
        self.ip_input.setEnabled(False)
        self.port_input.setEnabled(False)
        self.reset_session()
        self.tab_widget.setCurrentWidget(self.vpu_tab)

    @pyqtSlot()
    def on_disconnected(self):
        """Handle disconnection."""
        self.connect_button.setText("Connect")
        self.connect_button.setEnabled(True)
        self.refresh_button.setEnabled(False)
        self.status_indicator.setStyleSheet("color: #cc2e60; font-size: 20px;")
        self.status_bar.showMessage("Disconnected")
        self.ip_input.setEnabled(True)
        self.port_input.setEnabled(True)
        # Go back to the Connection tab, but leave the VPU/screen tables as-is
        # so the last known state stays visible until the next connect/refresh.
        self.tab_widget.setCurrentWidget(self.connection_tab)
    
    @pyqtSlot(str)
    def on_error(self, message: str):
        """Handle error."""
        self.status_bar.showMessage(f"Error: {message}")
        self.add_debug(f"[ERROR] {message}")
        self.connect_button.setEnabled(True)
    
    @pyqtSlot(dict)
    def on_data_received(self, data: dict):
        """Handle received data."""
        result = self.model.process_message(data)
        self.add_debug(f"[PARSED] {result}")
        
        # After receiving device type, immediately fetch all VPU data for that device
        if "[DEVICE]" in result and "vpus=" in result:
            self.request_vpu_data_for_device(data)
        
        # After receiving screen layer count, request layer details
        if "[SCREEN]" in result and "layers=" in result:
            self.request_screen_layer_details(data)
        
        # After receiving screen active, request more details
        if "SCREEN" in result and "active=True" in result:
            self.request_screen_details(data)
    
    def request_vpu_data_for_device(self, data: dict):
        """Request VPU data after device type is received."""
        path = data.get("path", "")
        match = self.model.REGEX_DEVICE_TYPE.match(path)
        if match:
            device_id = int(match.group(1))
            device = self.model.get_device(device_id)
            if device and device.vpu_count > 0:
                self.add_debug(f"[INFO] *** Fetching VPU data for Device {device_id} ({device.device_type}) - {device.vpu_count} VPUs ***")
                # Use the consolidated fetch method
                self.client.fetch_all_vpu_data(device_id, device.vpu_count)
    
    def request_screen_layer_details(self, data: dict):
        """Request layer details after screen layer count is received."""
        path = data.get("path", "")
        match = self.model.REGEX_SCREEN_LAYER_COUNT.match(path)
        if match:
            screen_id = int(match.group(1))
            screen = self.model.get_screen(screen_id)
            if screen and len(screen.layers) > 0:
                self.add_debug(f"[INFO] Fetching layer details for Screen {screen_id} ({len(screen.layers)} layers)")
                self.client.fetch_screen_details(screen_id, len(screen.layers))
    
    def request_screen_details(self, data: dict):
        """Request additional screen details after screen is found active."""
        path = data.get("path", "")
        match = self.model.REGEX_SCREEN_MODE.match(path)
        if match:
            screen_id = int(match.group(1))
            self.client.get_screen_layer_count(screen_id)
            self.client.get_screen_optimized(screen_id)
    
    @pyqtSlot(str)
    def on_debug_message(self, message: str):
        """Handle debug message."""
        self.add_debug(message)
    
    def add_debug(self, message: str):
        """Add message to debug log."""
        self.debug_text.append(message)
        # Auto-scroll to bottom
        scrollbar = self.debug_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def on_model_updated(self):
        """Handle model data update - schedule UI refresh."""
        pass  # Timer will handle periodic refresh
    
    def refresh_display(self):
        """Refresh the VPU display widgets."""
        self.refresh_vpu_widgets()
        self.refresh_screen_widgets()
        self.refresh_layers_table()
        self.refresh_summary()

    def refresh_layers_table(self):
        """Refresh the layers table."""
        self.layers_table.populate_from_model()
    
    def refresh_vpu_widgets(self):
        """Refresh VPU visualization widgets."""
        col = 0
        row = 0

        for device in self.model.devices:
            # NLC_DBG means the device is not connected/not in the system - hide its VPUs
            if device.device_type and device.device_type != "NLC_DBG" and device.vpu_count > 0:
                for vpu in device.vpus:
                    key = (device.id, vpu.vpu_id)

                    if key not in self.vpu_widgets:
                        widget = VPUWidget(device, vpu)
                        self.vpu_widgets[key] = widget
                        self.vpu_grid.addWidget(widget, row, col)
                        col += 1
                        if col >= 4:  # 4 VPUs per row (mixer/pipe matrix is narrow and tall)
                            col = 0
                            row += 1

                        # Connect hover signals (forwarded from whichever pipe cell is
                        # hovered - the grid can rebuild and replace individual cells)
                        widget.cell_hovered.connect(self.on_scaler_hovered)
                        widget.cell_left.connect(self.on_scaler_left)
                    else:
                        self.vpu_widgets[key].update_display()
    
    def refresh_screen_widgets(self):
        """Refresh screen widgets."""
        col = 0
        row = 0
        
        for screen in self.model.screens:
            if screen.active:
                if screen.id not in self.screen_widgets:
                    widget = ScreenWidget(screen)
                    self.screen_widgets[screen.id] = widget
                    self.screens_grid.addWidget(widget, row, col)
                    col += 1
                    if col >= 6:  # 6 screens per row
                        col = 0
                        row += 1
                else:
                    self.screen_widgets[screen.id].update_display()
    
    def refresh_summary(self):
        """Refresh the summary text."""
        summary = self.model.get_summary()
        if self.summary_text.toPlainText() != summary:
            self.summary_text.setPlainText(summary)

    def on_scaler_hovered(self, scaler):
        """Handle scaler hover event - highlight matching scalers."""
        for vpu_widget in self.vpu_widgets.values():
            vpu_widget.highlight_matching(scaler, True)

    def on_scaler_left(self):
        """Handle scaler leave event - clear highlights."""
        for vpu_widget in self.vpu_widgets.values():
            for pipe_widget in vpu_widget.pipe_widgets:
                pipe_widget.set_highlighted(False)

    def closeEvent(self, event):
        """Handle window close."""
        if self.client.is_connected:
            self.client.disconnect()
        event.accept()
