"""
AWJ TCP Client for VPU Visualizer 2.0
Handles TCP connection and communication with Aquilon devices.
"""

import json
import socket
import threading
from typing import Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal


EOT_CHAR = '\u0004'  # End of transmission character


class AWJClient(QObject):
    """TCP Client for AWJ protocol communication."""
    
    # Signals for async communication
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    error = pyqtSignal(str)
    data_received = pyqtSignal(dict)
    debug_message = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.socket: Optional[socket.socket] = None
        self.ip = "127.0.0.1"
        self.port = 10606
        self.is_connected = False
        self.receive_thread: Optional[threading.Thread] = None
        self.running = False
        self.buffer = ""
    
    def connect_to_device(self, ip: str, port: int) -> bool:
        """Connect to the AWJ device."""
        self.ip = ip
        self.port = port
        
        if self.socket:
            self.disconnect()
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)  # 5 second timeout for connection
            self.socket.connect((self.ip, self.port))
            self.socket.settimeout(None)  # Remove timeout for normal operation
            
            self.is_connected = True
            self.running = True
            
            # Start receive thread
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            
            self.connected.emit()
            self.debug_message.emit(f"[CONNECTION] Connected to {ip}:{port}")
            
            return True
            
        except socket.error as e:
            self.error.emit(f"Connection failed: {str(e)}")
            self.debug_message.emit(f"[ERROR] Connection failed: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from the device."""
        self.running = False
        self.is_connected = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        self.disconnected.emit()
        self.debug_message.emit("[CONNECTION] Disconnected")
    
    def send_message(self, message: dict):
        """Send a JSON message to the device."""
        if not self.is_connected or not self.socket:
            self.error.emit("Not connected")
            return
        
        try:
            json_str = json.dumps(message) + EOT_CHAR
            self.socket.send(json_str.encode('utf-8'))
            self.debug_message.emit(f"[SEND] {json.dumps(message)}")
        except socket.error as e:
            self.error.emit(f"Send failed: {str(e)}")
            self.debug_message.emit(f"[ERROR] Send failed: {str(e)}")
            self.disconnect()
    
    def send_get(self, path: str):
        """Send a GET request."""
        self.send_message({"op": "get", "path": path})
    
    def send_replace(self, path: str, value):
        """Send a REPLACE request."""
        self.send_message({"op": "replace", "path": path, "value": value})
    
    def _receive_loop(self):
        """Background thread for receiving data."""
        while self.running and self.socket:
            try:
                data = self.socket.recv(65536)
                if not data:
                    break
                
                self.buffer += data.decode('utf-8')
                
                # Process complete messages (separated by EOT)
                while EOT_CHAR in self.buffer:
                    message, self.buffer = self.buffer.split(EOT_CHAR, 1)
                    if message.strip():
                        try:
                            json_obj = json.loads(message)
                            self.debug_message.emit(f"[RECV] {json.dumps(json_obj)}")
                            self.data_received.emit(json_obj)
                        except json.JSONDecodeError as e:
                            self.debug_message.emit(f"[ERROR] JSON parse error: {e}")
                            
            except socket.timeout:
                continue
            except socket.error as e:
                if self.running:
                    self.error.emit(f"Receive error: {str(e)}")
                    self.debug_message.emit(f"[ERROR] Receive error: {str(e)}")
                break
        
        if self.running:
            self.disconnect()
    
    # ========== API Request Methods ==========
    
    def subscribe_to_updates(self):
        """Subscribe to device updates."""
        subscriptions = [
            "DeviceObject/preconfig/resources/new/$screen/@items/",
            "DeviceObject/preconfig/resources/new/status/mapping/$device/@items/"
        ]
        self.send_replace("Subscriptions", subscriptions)
        self.debug_message.emit("[INFO] Subscribed to device updates")
    
    def get_device_type(self, device_id: int):
        """Get device type for a specific device slot."""
        # Updated path based on app source analysis
        path = f"DeviceObject/system/$device/@items/{device_id}/@props/dev"
        self.send_get(path)
    
    def get_screen_mode(self, screen_id: int):
        """Get screen mode (active/disabled)."""
        path = f"DeviceObject/preconfig/resources/new/$screen/@items/S{screen_id}/status/@props/mode"
        self.send_get(path)
    
    def get_screen_layer_count(self, screen_id: int):
        """Get number of layers for a screen."""
        path = f"DeviceObject/preconfig/resources/new/$screen/@items/S{screen_id}/status/@props/layerCount"
        self.send_get(path)
    
    def get_screen_optimized(self, screen_id: int):
        """Get screen optimization status."""
        path = f"DeviceObject/preconfig/resources/new/$screen/@items/S{screen_id}/status/@props/isOptimized"
        self.send_get(path)
    
    def get_layer_capability(self, screen_id: int, layer_id: int):
        """Get layer capability."""
        path = f"DeviceObject/preconfig/resources/new/$screen/@items/S{screen_id}/$layer/@items/{layer_id}/status/@props/capability"
        self.send_get(path)
    
    def get_layer_regions(self, screen_id: int, layer_id: int):
        """Get layer regions."""
        path = f"DeviceObject/preconfig/resources/new/$screen/@items/S{screen_id}/$layer/@items/{layer_id}/status/@props/usedInRegions"
        self.send_get(path)
    
    def get_layer_mask(self, screen_id: int, layer_id: int):
        """Get layer mask status."""
        path = f"DeviceObject/preconfig/resources/new/$screen/@items/S{screen_id}/$layer/@items/{layer_id}/status/@props/canUseMask"
        self.send_get(path)
    
    def get_vpu_layer_enabled(self, device_id: int, vpu_id: int, mixer_id: int):
        """Get VPU mixer enabled status."""
        # Multi-device firmware: $vpuMixer (not $vpu-layer), MIXER (not SCALER)
        path = f"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpuMixer/@items/PROC_{vpu_id}_MIXER_{mixer_id}/@props/isEnabled"
        self.send_get(path)

    def get_vpu_layer_available(self, device_id: int, vpu_id: int, mixer_id: int):
        """Get VPU mixer availability status."""
        path = f"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpuMixer/@items/PROC_{vpu_id}_MIXER_{mixer_id}/@props/isAvailable"
        self.send_get(path)

    def get_vpu_layer_capability(self, device_id: int, vpu_id: int, mixer_id: int):
        """Get VPU mixer capability."""
        path = f"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpuMixer/@items/PROC_{vpu_id}_MIXER_{mixer_id}/@props/capability"
        self.send_get(path)

    def get_vpu_layer_screen(self, device_id: int, vpu_id: int, mixer_id: int):
        """Get which screen is using this VPU mixer."""
        path = f"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpuMixer/@items/PROC_{vpu_id}_MIXER_{mixer_id}/@props/usedInScreen"
        self.send_get(path)

    def get_vpu_layer_layer(self, device_id: int, vpu_id: int, mixer_id: int):
        """Get which layer is using this VPU mixer."""
        path = f"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpuMixer/@items/PROC_{vpu_id}_MIXER_{mixer_id}/@props/usedInLayer"
        self.send_get(path)

    def get_vpu_mixer_cutnfill_capa(self, device_id: int, vpu_id: int, mixer_id: int):
        """Get VPU mixer cut-and-fill capacity."""
        path = f"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpuMixer/@items/PROC_{vpu_id}_MIXER_{mixer_id}/@props/cutnfillCapa"
        self.send_get(path)

    def get_vpu_mixer_seamless_capa(self, device_id: int, vpu_id: int, mixer_id: int):
        """Get VPU mixer seamless capacity."""
        path = f"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpuMixer/@items/PROC_{vpu_id}_MIXER_{mixer_id}/@props/seamlessCapa"
        self.send_get(path)

    def get_vpu_mixer_channel(self, device_id: int, vpu_id: int, mixer_id: int):
        """Get VPU mixer channel."""
        path = f"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpuMixer/@items/PROC_{vpu_id}_MIXER_{mixer_id}/@props/channel"
        self.send_get(path)

    def get_vpu_mixer_slice(self, device_id: int, vpu_id: int, mixer_id: int):
        """Get VPU mixer slice."""
        path = f"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpuMixer/@items/PROC_{vpu_id}_MIXER_{mixer_id}/@props/slice"
        self.send_get(path)

    def get_scaler_pipe_usage(self, device_id: int, vpu_id: int, mixer_id: int, pipe_id: int):
        """Get mixer pipe usage for output pipe."""
        # Multi-device firmware: mixerAllocation (not scaler-allocation)
        path = f"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpuMixer/@items/PROC_{vpu_id}_MIXER_{mixer_id}/mixerAllocation/@props/usedOnOutPipe{pipe_id}"
        self.send_get(path)

    def get_hardware_card_available(self, device_id: int, card_name: str):
        """Check if a hardware card (PROC_1, PROC_2, etc.) is available."""
        path = f"DeviceObject/system/$device/@items/{device_id}/hardware/$card/@items/{card_name}/@props/isAvailable"
        self.send_get(path)
    
    def fetch_all_vpu_data(self, device_id: int, vpu_count: int):
        """Actively fetch all VPU data for a device."""
        self.debug_message.emit(f"[INFO] Fetching VPU data for Device {device_id} ({vpu_count} VPUs)")
        
        for vpu_id in range(1, vpu_count + 1):
            for mixer_id in range(1, 17):
                # Get all mixer properties (16 mixers per VPU on multi-device firmware)
                self.get_vpu_layer_enabled(device_id, vpu_id, mixer_id)
                self.get_vpu_layer_available(device_id, vpu_id, mixer_id)
                self.get_vpu_layer_capability(device_id, vpu_id, mixer_id)
                self.get_vpu_layer_screen(device_id, vpu_id, mixer_id)
                self.get_vpu_layer_layer(device_id, vpu_id, mixer_id)
                self.get_vpu_mixer_cutnfill_capa(device_id, vpu_id, mixer_id)
                self.get_vpu_mixer_seamless_capa(device_id, vpu_id, mixer_id)
                self.get_vpu_mixer_channel(device_id, vpu_id, mixer_id)
                self.get_vpu_mixer_slice(device_id, vpu_id, mixer_id)

                # Get pipe usage for each mixer (8 pipes per mixer)
                for pipe_id in range(1, 9):
                    self.get_scaler_pipe_usage(device_id, vpu_id, mixer_id, pipe_id)
    
    def fetch_screen_details(self, screen_id: int, layer_count: int):
        """Fetch detailed screen layer information."""
        self.debug_message.emit(f"[INFO] Fetching layer details for Screen {screen_id} ({layer_count} layers)")
        
        self.get_screen_optimized(screen_id)
        for layer_id in range(1, layer_count + 1):
            self.get_layer_capability(screen_id, layer_id)
            self.get_layer_regions(screen_id, layer_id)
            self.get_layer_mask(screen_id, layer_id)
    
    def initialize_connection(self):
        """Initialize connection and fetch all device data."""
        self.debug_message.emit("[INFO] ========================================")
        self.debug_message.emit("[INFO] Initializing connection and fetching data...")
        self.debug_message.emit("[INFO] ========================================")
        
        # Step 1: Get all screens status
        self.debug_message.emit("[INFO] Step 1: Fetching screen status...")
        for screen_id in range(1, 25):
            self.get_screen_mode(screen_id)
        
        # Step 2: Subscribe to updates for real-time changes
        self.debug_message.emit("[INFO] Step 2: Subscribing to updates...")
        self.subscribe_to_updates()
        
        # Step 3: Get device types (this triggers VPU data fetch in on_data_received)
        self.debug_message.emit("[INFO] Step 3: Fetching device types...")
        for device_id in range(1, 5):
            self.get_device_type(device_id)
        
        # Step 4: Check hardware card availability
        self.debug_message.emit("[INFO] Step 4: Checking hardware cards...")
        for device_id in range(1, 5):
            for proc_id in range(1, 5):
                self.get_hardware_card_available(device_id, f"PROC_{proc_id}")
