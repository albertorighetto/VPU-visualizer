#!/usr/bin/env python3
"""
Test script to check VPU 1 PROC 1 SCALER 1 properties
Uses only API paths from app_source.js
"""

import socket
import json
import time

EOT_CHAR = '\u0004'


def send_get(sock, path):
    """Send a GET request."""
    message = {"op": "get", "path": path}
    json_str = json.dumps(message) + EOT_CHAR
    sock.send(json_str.encode('utf-8'))
    print(f"[SEND] {json.dumps(message)}")


def receive_messages(sock, timeout=2.0):
    """Receive and print all messages for a timeout period."""
    sock.settimeout(timeout)
    buffer = ""
    messages = []
    
    try:
        while True:
            data = sock.recv(65536)
            if not data:
                break
            
            buffer += data.decode('utf-8')
            
            # Process complete messages
            while EOT_CHAR in buffer:
                message, buffer = buffer.split(EOT_CHAR, 1)
                if message.strip():
                    try:
                        json_obj = json.loads(message)
                        messages.append(json_obj)
                        print(f"[RECV] {json.dumps(json_obj, indent=2)}")
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] JSON parse error: {e}")
    except socket.timeout:
        pass
    
    return messages


def main():
    """Main test function."""
    IP = "127.0.0.1"
    PORT = 10606
    DEVICE_ID = 1
    VPU_ID = 1
    SCALER_ID = 1
    
    print("=" * 80)
    print("VPU SCALER TEST - Checking PROC_1_MIXER_1 Properties")
    print("=" * 80)
    
    # Connect
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    
    try:
        print(f"\n[INFO] Connecting to {IP}:{PORT}...")
        sock.connect((IP, PORT))
        print("[INFO] Connected successfully!")
        
        # Step 1: Get device type
        print("\n" + "=" * 80)
        print("STEP 1: Get Device Type")
        print("=" * 80)
        send_get(sock, f"DeviceObject/system/$device/@items/{DEVICE_ID}/@props/dev")
        receive_messages(sock, timeout=1.0)
        
        # Step 2: Check hardware card availability
        print("\n" + "=" * 80)
        print("STEP 2: Check Hardware Card (PROC_1) Availability")
        print("=" * 80)
        send_get(sock, f"DeviceObject/system/$device/@items/{DEVICE_ID}/hardware/$card/@items/PROC_{VPU_ID}/@props/isAvailable")
        receive_messages(sock, timeout=1.0)
        
        # Step 3: Get VPU Mixer properties for PROC_1_MIXER_1
        print("\n" + "=" * 80)
        print("STEP 3: Get VPU Mixer Properties (PROC_1_MIXER_1)")
        print("=" * 80)

        # Multi-device firmware: $vpuMixer / MIXER naming
        base_path = f"DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{DEVICE_ID}/$vpuMixer/@items/PROC_{VPU_ID}_MIXER_{SCALER_ID}"
        
        properties = [
            "isEnabled",
            "isAvailable",
            "capability",
            "usedInScreen",
            "usedInLayer"
        ]
        
        for prop in properties:
            print(f"\n[INFO] Requesting: {prop}")
            send_get(sock, f"{base_path}/@props/{prop}")
            time.sleep(0.1)
        
        receive_messages(sock, timeout=2.0)
        
        # Step 4: Get mixer allocation (pipe usage)
        print("\n" + "=" * 80)
        print("STEP 4: Get Mixer Allocation (Pipe Usage)")
        print("=" * 80)

        allocation_path = f"{base_path}/mixerAllocation/@props"
        
        for pipe_id in range(1, 9):
            print(f"\n[INFO] Requesting: usedOnOutPipe{pipe_id}")
            send_get(sock, f"{allocation_path}/usedOnOutPipe{pipe_id}")
            time.sleep(0.1)
        
        receive_messages(sock, timeout=2.0)
        
        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)
        
    except socket.error as e:
        print(f"[ERROR] Connection failed: {e}")
    finally:
        sock.close()
        print("\n[INFO] Connection closed")


if __name__ == "__main__":
    main()
