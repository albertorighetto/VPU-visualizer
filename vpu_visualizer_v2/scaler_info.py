#!/usr/bin/env python3
"""
VPU Scaler Information Script
Retrieves model name, VPU count, processors, and scaler allocation info.
Displays results in a formatted table with debug messages.

Usage:
    python scaler_info.py [IP] [PORT] [DEVICE_ID]
    
    Defaults: IP=127.0.0.1, PORT=10606, DEVICE_ID=1
"""

import socket
import json
import sys
import time
import re
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

EOT_CHAR = '\u0004'  # End of transmission character

# Device types and their VPU counts
DEVICE_VPU_COUNTS = {
    "NLC_DBG": 1, "NLC_RS1": 1, "NLC_RS2": 2, "NLC_RS3": 2,
    "NLC_RS4": 3, "NLC_RS5": 3, "NLC_RS6": 4, "NLC_RSALPHA": 1,
    "NLC_C": 2, "NLC_CPLUS": 3, "NLC_CMAX": 4, "NLC_CMINI": 1,
    "VDW_W": 2, "VDW_WPLUS": 3, "VDW_WMAX": 4,
}


@dataclass
class ScalerInfo:
    """Information about a single scaler."""
    proc_id: int
    scaler_id: int
    is_enabled: Optional[bool] = None
    is_available: Optional[bool] = None
    capability: Optional[str] = None
    used_in_screen: Optional[int] = None
    used_in_layer: Optional[int] = None
    pipes: Dict[int, str] = field(default_factory=dict)
    
    @property
    def name(self) -> str:
        return f"PROC_{self.proc_id}_MIXER_{self.scaler_id}"
    
    def get_used_pipes(self) -> List[int]:
        """Get list of pipe IDs that are in use."""
        return [p for p, v in self.pipes.items() if v and v != "NONE"]


class AWJConnection:
    """Simple AWJ TCP connection for data retrieval."""
    
    def __init__(self, ip: str, port: int, debug: bool = True):
        self.ip = ip
        self.port = port
        self.debug = debug
        self.socket: Optional[socket.socket] = None
        self.buffer = ""
        
    def log(self, msg: str):
        """Print debug message."""
        if self.debug:
            print(msg)
    
    def connect(self) -> bool:
        """Connect to the AWJ device."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.ip, self.port))
            self.log(f"[DEBUG] Connected to {self.ip}:{self.port}")
            return True
        except socket.error as e:
            self.log(f"[ERROR] Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the device."""
        if self.socket:
            self.socket.close()
            self.socket = None
            self.log("[DEBUG] Disconnected")
    
    def send_get(self, path: str) -> None:
        """Send a GET request."""
        message = {"op": "get", "path": path}
        self._send_message(message)
    
    def _send_message(self, message: dict) -> None:
        """Send a JSON message."""
        if not self.socket:
            self.log("[ERROR] Not connected")
            return
        
        try:
            json_str = json.dumps(message) + EOT_CHAR
            self.socket.send(json_str.encode('utf-8'))
            self.log(f"[SEND] {json.dumps(message)}")
        except socket.error as e:
            self.log(f"[ERROR] Send failed: {e}")
    
    def receive_messages(self, timeout: float = 2.0) -> List[dict]:
        """Receive and parse all messages within timeout period."""
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
                            json_obj = json.loads(message)
                            self.log(f"[RECV] {json.dumps(json_obj)}")
                            messages.append(json_obj)
                        except json.JSONDecodeError as e:
                            self.log(f"[ERROR] JSON parse error: {e}")
        except socket.timeout:
            pass
        except socket.error as e:
            self.log(f"[ERROR] Receive error: {e}")
        
        return messages
    
    def send_and_receive(self, path: str, timeout: float = 1.0) -> List[dict]:
        """Send a GET request and return responses."""
        self.send_get(path)
        return self.receive_messages(timeout)


def parse_path_value(response: dict) -> tuple:
    """Extract path and value from a response message."""
    path = response.get("path", "")
    value = response.get("value")
    return path, value


def get_device_type(conn: AWJConnection, device_id: int) -> Optional[str]:
    """Get the device type (model name)."""
    path = f"DeviceObject/system/$device/@items/{device_id}/@props/dev"
    responses = conn.send_and_receive(path)
    
    for resp in responses:
        p, v = parse_path_value(resp)
        if "/@props/dev" in p and v:
            return v
    return None


def get_processor_available(conn: AWJConnection, device_id: int, proc_id: int) -> Optional[bool]:
    """Check if a processor (PROC_#) is available."""
    path = f"DeviceObject/system/$device/@items/{device_id}/hardware/$card/@items/PROC_{proc_id}/@props/isAvailable"
    responses = conn.send_and_receive(path)
    
    for resp in responses:
        p, v = parse_path_value(resp)
        if f"PROC_{proc_id}/@props/isAvailable" in p:
            return v
    return None


def get_scaler_properties(conn: AWJConnection, device_id: int, proc_id: int, scaler_id: int) -> ScalerInfo:
    """Get all properties for a scaler (mixer)."""
    scaler = ScalerInfo(proc_id=proc_id, scaler_id=scaler_id)
    # Live AWJ protocol node name is $vpuMixer, not the web UI's $vpuLayer
    base_path = f"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpuMixer/@items/PROC_{proc_id}_MIXER_{scaler_id}"

    # Request all properties at once
    properties = ["isEnabled", "isAvailable", "capability", "usedInScreen", "usedInLayer"]
    for prop in properties:
        conn.send_get(f"{base_path}/@props/{prop}")

    # Request pipe usage - mixerAllocation
    for pipe_id in range(1, 9):
        conn.send_get(f"{base_path}/mixerAllocation/@props/usedOnOutPipe{pipe_id}")

    # Wait a bit for all responses
    time.sleep(0.1)

    # Collect responses
    responses = conn.receive_messages(timeout=2.0)

    scaler_name = f"PROC_{proc_id}_MIXER_{scaler_id}"

    for resp in responses:
        p, v = parse_path_value(resp)
        if scaler_name not in p:
            continue

        if "/@props/isEnabled" in p:
            scaler.is_enabled = v
        elif "/@props/isAvailable" in p:
            scaler.is_available = v
        elif "/@props/capability" in p:
            scaler.capability = v
        elif "/@props/usedInScreen" in p:
            scaler.used_in_screen = v
        elif "/@props/usedInLayer" in p:
            scaler.used_in_layer = v
        elif "/mixerAllocation/@props/usedOnOutPipe" in p:
            match = re.search(r'usedOnOutPipe(\d+)', p)
            if match:
                pipe_id = int(match.group(1))
                scaler.pipes[pipe_id] = v

    return scaler


def get_all_scalers(conn: AWJConnection, device_id: int, vpu_count: int) -> List[ScalerInfo]:
    """Get all scaler (mixer) information for a device."""
    scalers = []

    for proc_id in range(1, vpu_count + 1):
        conn.log(f"[INFO] Fetching mixers for PROC_{proc_id}...")
        for scaler_id in range(1, 17):
            scaler = get_scaler_properties(conn, device_id, proc_id, scaler_id)
            scalers.append(scaler)

    return scalers


def print_header(title: str, width: int = 80):
    """Print a formatted header."""
    print("=" * width)
    print(f" {title}")
    print("=" * width)


def print_device_info(device_type: str, vpu_count: int, processors: Dict[int, bool]):
    """Print device information."""
    print_header("DEVICE INFORMATION")
    print(f"  Model Name:    {device_type}")
    print(f"  VPU Count:     {vpu_count}")
    print(f"  Processors:")
    for proc_id, available in processors.items():
        status = "Available" if available else "Not Available"
        print(f"    PROC_{proc_id}:     {status}")
    print()


def print_scaler_table(scalers: List[ScalerInfo]):
    """Print scaler information in a formatted table."""
    print_header("SCALER ALLOCATION TABLE")
    
    # Table header
    header = f"{'Scaler Name':<20} {'Enabled':<8} {'Avail':<8} {'Capability':<12} {'Screen':<8} {'Layer':<8} {'Used Pipes':<20}"
    print(header)
    print("-" * len(header))
    
    current_proc = 0
    for scaler in scalers:
        # Add separator between processors
        if scaler.proc_id != current_proc:
            if current_proc > 0:
                print("-" * len(header))
            current_proc = scaler.proc_id
        
        enabled_str = "Yes" if scaler.is_enabled else ("No" if scaler.is_enabled is False else "?")
        avail_str = "Yes" if scaler.is_available else ("No" if scaler.is_available is False else "?")
        cap_str = scaler.capability or "?"
        screen_str = str(scaler.used_in_screen) if scaler.used_in_screen else "-"
        layer_str = str(scaler.used_in_layer) if scaler.used_in_layer else "-"
        
        used_pipes = scaler.get_used_pipes()
        pipes_str = ", ".join(map(str, used_pipes)) if used_pipes else "None"
        
        row = f"{scaler.name:<20} {enabled_str:<8} {avail_str:<8} {cap_str:<12} {screen_str:<8} {layer_str:<8} {pipes_str:<20}"
        print(row)
    
    print("=" * len(header))


def print_scaler_allocation_details(scalers: List[ScalerInfo]):
    """Print detailed scaler allocation per pipe."""
    print()
    print_header("SCALER ALLOCATION DETAILS (Pipe Usage)")
    
    for scaler in scalers:
        if any(v and v != "NONE" for v in scaler.pipes.values()):
            print(f"\n  {scaler.name}:")
            for pipe_id in range(1, 9):
                value = scaler.pipes.get(pipe_id, "?")
                if value and value != "NONE":
                    print(f"    Pipe {pipe_id}: {value}")


def print_summary(scalers: List[ScalerInfo]):
    """Print a summary of scaler usage."""
    print()
    print_header("SUMMARY")
    
    total_scalers = len(scalers)
    enabled_scalers = sum(1 for s in scalers if s.is_enabled)
    available_scalers = sum(1 for s in scalers if s.is_available)
    
    print(f"  Total Scalers:     {total_scalers}")
    print(f"  Enabled Scalers:   {enabled_scalers}")
    print(f"  Available Scalers: {available_scalers}")
    print(f"  Utilization:       {enabled_scalers}/{total_scalers} ({100*enabled_scalers/total_scalers:.1f}%)" if total_scalers > 0 else "N/A")
    
    # Group by processor
    print("\n  Per Processor Usage:")
    proc_ids = sorted(set(s.proc_id for s in scalers))
    for proc_id in proc_ids:
        proc_scalers = [s for s in scalers if s.proc_id == proc_id]
        proc_enabled = sum(1 for s in proc_scalers if s.is_enabled)
        print(f"    PROC_{proc_id}: {proc_enabled}/16 scalers enabled")


def main():
    """Main function."""
    # Parse command line arguments
    ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 10606
    device_id = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    
    print()
    print_header("VPU SCALER INFORMATION TOOL")
    print(f"  Target:    {ip}:{port}")
    print(f"  Device ID: {device_id}")
    print()
    
    # Create connection
    conn = AWJConnection(ip, port, debug=True)
    
    if not conn.connect():
        print("[ERROR] Failed to connect to device")
        return 1
    
    try:
        # Step 1: Get device type
        print()
        print_header("STEP 1: Getting Device Type")
        device_type = get_device_type(conn, device_id)
        
        if not device_type:
            print("[ERROR] Failed to get device type")
            return 1
        
        vpu_count = DEVICE_VPU_COUNTS.get(device_type, 0)
        print(f"[INFO] Device Type: {device_type}")
        print(f"[INFO] VPU Count: {vpu_count}")
        
        if vpu_count == 0:
            print(f"[WARNING] Unknown device type or VPU count for: {device_type}")
            vpu_count = 1  # Default to 1 VPU
        
        # Step 2: Check processor availability
        print()
        print_header("STEP 2: Checking Processor Availability")
        processors = {}
        for proc_id in range(1, vpu_count + 1):
            available = get_processor_available(conn, device_id, proc_id)
            processors[proc_id] = available
            status = "Available" if available else "Not Available"
            print(f"[INFO] PROC_{proc_id}: {status}")
        
        # Step 3: Get all scaler information
        print()
        print_header("STEP 3: Fetching Scaler Information")
        scalers = get_all_scalers(conn, device_id, vpu_count)
        
        # Display results
        print()
        print()
        print("#" * 80)
        print("#  RESULTS")
        print("#" * 80)
        print()
        
        print_device_info(device_type, vpu_count, processors)
        print_scaler_table(scalers)
        print_scaler_allocation_details(scalers)
        print_summary(scalers)
        
        print()
        print_header("COMPLETE")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        conn.disconnect()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
