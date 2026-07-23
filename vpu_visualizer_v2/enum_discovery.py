#!/usr/bin/env python3
"""
Enum Discovery Script
Connects to a live AWJ device and reads out every enum-valued property this
app parses (device types, mixer/layer capability, pipe usage, etc.), so the
value sets hardcoded in vpu_model.py / vpu_widget.py can be checked against
what the device actually reports - a "fresh list" grounded in a real readout
rather than static app-source analysis.

Usage:
    python enum_discovery.py [IP] [PORT]

    Defaults: IP=127.0.0.1, PORT=10606
"""

import socket
import json
import sys
import time
from collections import defaultdict
from typing import Dict, List, Optional

EOT_CHAR = ''  # End of transmission character

# Device types and their VPU counts (mirrors vpu_model.DEVICE_VPU_COUNTS)
DEVICE_VPU_COUNTS = {
    "NLC_DBG": 1, "NLC_RS1": 1, "NLC_RS2": 2, "NLC_RS3": 2,
    "NLC_RS4": 3, "NLC_RS5": 3, "NLC_RS6": 4, "NLC_RSALPHA": 1,
    "NLC_C": 2, "NLC_CPLUS": 3, "NLC_CMAX": 4, "NLC_CMINI": 1,
    "VDW_W": 2, "VDW_WPLUS": 3, "VDW_WMAX": 4,
}

MAX_DEVICES = 4
MAX_SCREENS = 24
MIXERS_PER_VPU = 16
PIPES_PER_MIXER = 8

# ---------------------------------------------------------------------------
# Enum value sets as currently hardcoded elsewhere in this codebase
# (vpu_model.py DEVICE_VPU_COUNTS/LayerCapability, vpu_widget.py
# get_capability_color/is_truthy_capa). Kept as literal copies here so this
# stays a standalone, runnable diagnostic tool - not imported from the app.
# ---------------------------------------------------------------------------
KNOWN_ENUMS: Dict[str, set] = {
    "device.dev": set(DEVICE_VPU_COUNTS.keys()),
    "screen.mode": {"DISABLED"},  # any other value is treated as "active"
    "mixer.capability": {"OFF", "DUAL", "4K", "3", "5K", "5", "6", "7", "8K"},
    "layer.capability": {"OFF", "DUAL", "4K", "3", "5K", "5", "6", "7", "8K"},
    "mixer.usedInLayer": {"NATIVE"},  # any other value is treated as numeric (layer = value + 1)
    "mixer.pipeUsage": {"NONE"},  # any other value means the pipe is in use
    "mixer.cutnfillCapa": {"NONE", "OFF"},  # falsy set (see is_truthy_capa); anything else counts as set
    "mixer.seamlessCapa": {"NONE", "OFF"},
}

# Fields with no hardcoded expectation in the app - reported for visibility only.
REFERENCE_ONLY_FIELDS = {"mixer.usedInScreen", "mixer.channel", "mixer.slice"}


class AWJConnection:
    """Minimal AWJ TCP connection for read-only discovery."""

    def __init__(self, ip: str, port: int, debug: bool = False):
        self.ip = ip
        self.port = port
        self.debug = debug
        self.socket: Optional[socket.socket] = None
        self.buffer = ""

    def log(self, msg: str):
        if self.debug:
            print(msg)

    def connect(self) -> bool:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.ip, self.port))
            self.log(f"[DEBUG] Connected to {self.ip}:{self.port}")
            return True
        except socket.error as e:
            print(f"[ERROR] Connection failed: {e}")
            return False

    def disconnect(self):
        if self.socket:
            self.socket.close()
            self.socket = None

    def send_get(self, path: str) -> None:
        if not self.socket:
            return
        try:
            self.socket.send((json.dumps({"op": "get", "path": path}) + EOT_CHAR).encode('utf-8'))
        except socket.error as e:
            print(f"[ERROR] Send failed: {e}")

    def receive_messages(self, timeout: float = 1.0) -> List[dict]:
        if not self.socket:
            return []

        self.socket.settimeout(timeout)
        messages = []
        try:
            while True:
                data = self.socket.recv(65536)
                if not data:
                    break
                self.buffer += data.decode('utf-8')
                while EOT_CHAR in self.buffer:
                    message, self.buffer = self.buffer.split(EOT_CHAR, 1)
                    if message.strip():
                        try:
                            messages.append(json.loads(message))
                        except json.JSONDecodeError as e:
                            print(f"[ERROR] JSON parse error: {e}")
        except socket.timeout:
            pass
        except socket.error as e:
            print(f"[ERROR] Receive error: {e}")

        return messages

    def get_batch(self, paths: List[str], timeout: float = 1.0) -> Dict[str, object]:
        """Send GETs for all paths and collect the responses keyed by path."""
        for path in paths:
            self.send_get(path)
        time.sleep(0.05)
        result = {}
        for resp in self.receive_messages(timeout):
            path = resp.get("path")
            if path in paths and "value" in resp:
                result[path] = resp["value"]
        return result

    def get_single(self, path: str, timeout: float = 1.0) -> Optional[object]:
        return self.get_batch([path], timeout).get(path)


def discover(conn: AWJConnection) -> Dict[str, set]:
    """Walk every device/VPU/mixer and screen/layer, collecting the raw value
    seen for each enum-valued property. Returns field name -> set of values."""
    observed: Dict[str, set] = defaultdict(set)

    print("[INFO] Scanning devices and VPU mixers...")
    for device_id in range(1, MAX_DEVICES + 1):
        dev_type = conn.get_single(f"DeviceObject/system/$device/@items/{device_id}/@props/dev")
        if not dev_type:
            continue
        observed["device.dev"].add(str(dev_type))
        print(f"  Device {device_id}: {dev_type}")

        vpu_count = DEVICE_VPU_COUNTS.get(dev_type, 0)
        for vpu_id in range(1, vpu_count + 1):
            for mixer_id in range(1, MIXERS_PER_VPU + 1):
                base = (f"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/"
                        f"{device_id}/$vpuMixer/@items/PROC_{vpu_id}_MIXER_{mixer_id}")

                paths = [
                    f"{base}/@props/capability",
                    f"{base}/@props/usedInLayer",
                    f"{base}/@props/usedInScreen",
                    f"{base}/@props/cutnfillCapa",
                    f"{base}/@props/seamlessCapa",
                    f"{base}/@props/channel",
                    f"{base}/@props/slice",
                ]
                paths += [f"{base}/mixerAllocation/@props/usedOnOutPipe{p}" for p in range(1, PIPES_PER_MIXER + 1)]

                values = conn.get_batch(paths, timeout=1.5)

                for path, value in values.items():
                    if value is None:
                        continue
                    if path.endswith("/@props/capability"):
                        observed["mixer.capability"].add(str(value))
                    elif path.endswith("/@props/usedInLayer"):
                        observed["mixer.usedInLayer"].add(str(value))
                    elif path.endswith("/@props/usedInScreen"):
                        observed["mixer.usedInScreen"].add(str(value))
                    elif path.endswith("/@props/cutnfillCapa"):
                        observed["mixer.cutnfillCapa"].add(str(value))
                    elif path.endswith("/@props/seamlessCapa"):
                        observed["mixer.seamlessCapa"].add(str(value))
                    elif path.endswith("/@props/channel"):
                        observed["mixer.channel"].add(str(value))
                    elif path.endswith("/@props/slice"):
                        observed["mixer.slice"].add(str(value))
                    elif "/mixerAllocation/@props/usedOnOutPipe" in path:
                        observed["mixer.pipeUsage"].add(str(value))

    print("[INFO] Scanning screens and layers...")
    for screen_id in range(1, MAX_SCREENS + 1):
        mode = conn.get_single(
            f"DeviceObject/preconfig/resources/new/$screen/@items/S{screen_id}/status/@props/mode")
        if mode is None:
            continue
        observed["screen.mode"].add(str(mode))
        if mode == "DISABLED":
            continue

        layer_count = conn.get_single(
            f"DeviceObject/preconfig/resources/new/$screen/@items/S{screen_id}/status/@props/layerCount")
        if not layer_count:
            continue

        print(f"  Screen {screen_id}: mode={mode}, layers={layer_count}")
        paths = [
            f"DeviceObject/preconfig/resources/new/$screen/@items/S{screen_id}/$layer/@items/{layer_id}/status/@props/capability"
            for layer_id in range(1, int(layer_count) + 1)
        ]
        values = conn.get_batch(paths, timeout=1.5)
        for value in values.values():
            if value is not None:
                observed["layer.capability"].add(str(value))

    return observed


def print_report(observed: Dict[str, set]):
    print()
    print("=" * 78)
    print(" ENUM DISCOVERY REPORT")
    print("=" * 78)

    all_fields = sorted(set(KNOWN_ENUMS) | set(REFERENCE_ONLY_FIELDS) | set(observed))
    for field in all_fields:
        seen = observed.get(field, set())
        print(f"\n[{field}]")
        print(f"  Observed on device : {sorted(seen) if seen else '(none seen)'}")

        if field in REFERENCE_ONLY_FIELDS:
            print("  (no hardcoded enum for this field in the app - informational only)")
            continue

        known = KNOWN_ENUMS.get(field, set())
        new_values = seen - known
        unused_values = known - seen
        if new_values:
            print(f"  ! NEW values not handled in code: {sorted(new_values)}")
        if unused_values:
            print(f"  Known values not observed here    : {sorted(unused_values)}")
        if not new_values and not unused_values and seen:
            print("  OK - matches the app's known set exactly.")

    print()
    print("=" * 78)


def main():
    ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 10606

    print(f"[INFO] Connecting to {ip}:{port}...")
    conn = AWJConnection(ip, port)
    if not conn.connect():
        return 1

    try:
        observed = discover(conn)
        print_report(observed)
    finally:
        conn.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
