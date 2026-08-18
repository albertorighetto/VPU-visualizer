"""
AWJ TCP Client for VPU Visualizer 2.0
Handles TCP connection and communication with Aquilon devices.

All preconfig paths are built against a selectable resource tree:
  - "current" -> DeviceObject/preconfig/resources/current/...  (running config)
  - "new"     -> DeviceObject/preconfig/resources/new/...      (pending config)
"""

import json
import socket
import threading
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal


EOT_CHAR = '\u0004'  # End of transmission character

RESOURCE_CURRENT = "current"
RESOURCE_NEW = "new"

# hardware/$card/@items always exposes exactly PROC_1..PROC_4 in the device's
# own object schema, for every device slot regardless of chassis size or
# type - this is a protocol-wide ceiling on addressable PROC slots, not a
# per-device-type VPU count guess. It only bounds the availability-polling
# chain in MainWindow; which of those slots actually exist is always
# determined by polling, never assumed.
MAX_PROC_SLOTS = 4


class AWJClient(QObject):
    """TCP Client for AWJ protocol communication."""

    # Signals for async communication
    connecting = pyqtSignal(str, int)
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    error = pyqtSignal(str)
    data_received = pyqtSignal(dict)
    debug_message = pyqtSignal(str)
    live_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.socket: Optional[socket.socket] = None
        self.ip = "127.0.0.1"
        self.port = 10606
        self.is_connected = False
        self.is_live = False
        self.resource = RESOURCE_NEW
        self.receive_thread: Optional[threading.Thread] = None
        self.running = False
        self.buffer = ""

    def set_resource(self, resource: str):
        """Select which configuration tree to address ('current' or 'new')."""
        self.resource = resource

    def _res_base(self) -> str:
        return f"DeviceObject/preconfig/resources/{self.resource}"

    def connect_to_device(self, ip: str, port: int):
        """Connect to the AWJ device (async - result arrives via signals)."""
        self.ip = ip
        self.port = port

        if self.socket:
            self.disconnect()

        self.connecting.emit(ip, port)
        thread = threading.Thread(target=self._connect_worker, args=(ip, port), daemon=True)
        thread.start()

    def _connect_worker(self, ip: str, port: int):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((ip, port))
            sock.settimeout(None)
        except socket.error as e:
            self.error.emit(f"Connection failed: {e}")
            self.debug_message.emit(f"[ERROR] Connection failed: {e}")
            self.disconnected.emit()
            return

        self.socket = sock
        self.is_connected = True
        self.running = True
        self.buffer = ""

        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()

        self.debug_message.emit(f"[CONNECTION] Connected to {ip}:{port}")
        self.connected.emit()

    def disconnect(self):
        """Disconnect from the device."""
        self.running = False
        self.is_connected = False
        if self.is_live:
            self.is_live = False
            self.live_changed.emit(False)

        if self.socket:
            try:
                self.socket.close()
            except OSError:
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
            self.error.emit(f"Send failed: {e}")
            self.debug_message.emit(f"[ERROR] Send failed: {e}")
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
                    self.error.emit(f"Receive error: {e}")
                    self.debug_message.emit(f"[ERROR] Receive error: {e}")
                break

        if self.running:
            self.disconnect()

    # ========== API Request Methods ==========

    def subscribe_to_updates(self):
        """Subscribe to device updates for the active resource tree."""
        subscriptions = [
            f"{self._res_base()}/$screen/@items/",
            f"{self._res_base()}/status/mapping/$device/@items/",
        ]
        self.send_replace("Subscriptions", subscriptions)
        self.debug_message.emit(f"[INFO] Subscribed to device updates ({self.resource} config)")
        self.is_live = True
        self.live_changed.emit(True)

    def get_device_type(self, device_id: int):
        """Get device type for a specific device slot."""
        path = f"DeviceObject/system/$device/@items/{device_id}/@props/dev"
        self.send_get(path)

    def get_screen_mode(self, screen_id: int):
        """Get screen mode (active/disabled)."""
        self.send_get(f"{self._res_base()}/$screen/@items/S{screen_id}/status/@props/mode")

    def get_screen_label(self, screen_id: int):
        """Get screen name/label. Lives outside the preconfig resource tree."""
        self.send_get(f"DeviceObject/$screen/@items/S{screen_id}/control/@props/label")

    def get_screen_layer_count(self, screen_id: int):
        """Get number of layers for a screen."""
        self.send_get(f"{self._res_base()}/$screen/@items/S{screen_id}/status/@props/layerCount")

    def get_screen_optimized(self, screen_id: int):
        """Get screen optimization status."""
        self.send_get(f"{self._res_base()}/$screen/@items/S{screen_id}/status/@props/isOptimized")

    def get_screen_stereo3d(self, screen_id: int):
        """Get screen stereoscopic 3D status."""
        self.send_get(f"{self._res_base()}/$screen/@items/S{screen_id}/status/@props/isStereo3d")

    def get_screen_region_validity(self, screen_id: int):
        """Get the number of valid/active regions for a screen."""
        self.send_get(f"{self._res_base()}/$screen/@items/S{screen_id}/status/@props/regionValidity")

    def get_layer_capability(self, screen_id: int, layer_id: int):
        """Get layer capability."""
        self.send_get(f"{self._res_base()}/$screen/@items/S{screen_id}/$layer/@items/{layer_id}/status/@props/capability")

    def get_layer_regions(self, screen_id: int, layer_id: int):
        """Get layer regions."""
        self.send_get(f"{self._res_base()}/$screen/@items/S{screen_id}/$layer/@items/{layer_id}/status/@props/usedInRegions")

    def get_layer_mask(self, screen_id: int, layer_id: int):
        """Get layer mask status."""
        self.send_get(f"{self._res_base()}/$screen/@items/S{screen_id}/$layer/@items/{layer_id}/status/@props/canUseMask")

    def _mixer_base(self, device_id: int, vpu_id: int, mixer_id: int) -> str:
        # Live AWJ protocol node name is $vpuMixer, not the web UI's $vpuLayer
        return (f"{self._res_base()}/status/mapping/$device/@items/{device_id}"
                f"/$vpuMixer/@items/PROC_{vpu_id}_MIXER_{mixer_id}")

    def get_vpu_layer_enabled(self, device_id: int, vpu_id: int, mixer_id: int):
        self.send_get(f"{self._mixer_base(device_id, vpu_id, mixer_id)}/@props/isEnabled")

    def get_vpu_layer_available(self, device_id: int, vpu_id: int, mixer_id: int):
        self.send_get(f"{self._mixer_base(device_id, vpu_id, mixer_id)}/@props/isAvailable")

    def get_vpu_layer_capability(self, device_id: int, vpu_id: int, mixer_id: int):
        self.send_get(f"{self._mixer_base(device_id, vpu_id, mixer_id)}/@props/capability")

    def get_vpu_layer_screen(self, device_id: int, vpu_id: int, mixer_id: int):
        self.send_get(f"{self._mixer_base(device_id, vpu_id, mixer_id)}/@props/usedInScreen")

    def get_vpu_layer_layer(self, device_id: int, vpu_id: int, mixer_id: int):
        self.send_get(f"{self._mixer_base(device_id, vpu_id, mixer_id)}/@props/usedInLayer")

    def get_vpu_mixer_cutnfill_capa(self, device_id: int, vpu_id: int, mixer_id: int):
        self.send_get(f"{self._mixer_base(device_id, vpu_id, mixer_id)}/@props/cutnfillCapa")

    def get_vpu_mixer_seamless_capa(self, device_id: int, vpu_id: int, mixer_id: int):
        self.send_get(f"{self._mixer_base(device_id, vpu_id, mixer_id)}/@props/seamlessCapa")

    def get_vpu_mixer_channel(self, device_id: int, vpu_id: int, mixer_id: int):
        self.send_get(f"{self._mixer_base(device_id, vpu_id, mixer_id)}/@props/channel")

    def get_vpu_mixer_slice(self, device_id: int, vpu_id: int, mixer_id: int):
        self.send_get(f"{self._mixer_base(device_id, vpu_id, mixer_id)}/@props/slice")

    def get_scaler_pipe_usage(self, device_id: int, vpu_id: int, mixer_id: int, pipe_id: int):
        # Live AWJ protocol node name is mixerAllocation, not the web UI's scalerAllocation
        self.send_get(f"{self._mixer_base(device_id, vpu_id, mixer_id)}/mixerAllocation/@props/usedOnOutPipe{pipe_id}")

    def check_hardware_card_available(self, device_id: int, vpu_id: int):
        """Ask whether a VPU's hardware card (PROC_1, PROC_2, ...) is present.
        Gates fetch_vpu_data - MainWindow only fetches the (expensive) full
        VPU data set once this comes back true, instead of blindly requesting
        16 mixers' worth of properties for VPU slots that may not exist."""
        path = f"DeviceObject/system/$device/@items/{device_id}/hardware/$card/@items/PROC_{vpu_id}/@props/isAvailable"
        self.send_get(path)

    def fetch_vpu_data(self, device_id: int, vpu_id: int):
        """Actively fetch all mixer data for a single VPU."""
        self.debug_message.emit(f"[INFO] Fetching VPU data for Device {device_id}, VPU {vpu_id}")

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
        """Initialize connection and fetch all device data for the active resource."""
        self.debug_message.emit(f"[INFO] Initializing - fetching data ({self.resource} config)...")

        # Step 1: Get all screens status
        for screen_id in range(1, 25):
            self.get_screen_mode(screen_id)

        # Step 2: Subscribe to updates for real-time changes
        self.subscribe_to_updates()

        # Step 3: Get device types. Once a type (and thus VPU count) is known,
        # MainWindow checks hardware availability per VPU slot and only then
        # fetches that VPU's mixer data - see MainWindow.request_vpu_data_for_device.
        for device_id in range(1, 5):
            self.get_device_type(device_id)
