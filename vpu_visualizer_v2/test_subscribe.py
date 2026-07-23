#!/usr/bin/env python3
"""
Test script to subscribe and see what paths are actually available
"""

import socket
import json
import time

EOT_CHAR = '\u0004'


def send_message(sock, message):
    """Send a JSON message."""
    json_str = json.dumps(message) + EOT_CHAR
    sock.send(json_str.encode('utf-8'))
    print(f"[SEND] {json.dumps(message)}")


def receive_loop(sock, duration=10.0):
    """Receive and print all messages for a duration."""
    sock.settimeout(1.0)
    buffer = ""
    start_time = time.time()
    
    print(f"\n[INFO] Listening for {duration} seconds...\n")
    
    while time.time() - start_time < duration:
        try:
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
                        path = json_obj.get("path", "")
                        
                        # Filter for VPU-related paths
                        if ("$vpu" in path.lower() or "proc_" in path.upper() or 
                            "scaler" in path.lower() or "$device" in path):
                            print(f"[RECV] {json.dumps(json_obj, indent=2)}")
                            print()
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] JSON parse error: {e}")
        except socket.timeout:
            continue
    
    print(f"\n[INFO] Stopped listening after {duration} seconds")


def main():
    """Main test function."""
    IP = "127.0.0.1"
    PORT = 10606
    
    print("=" * 80)
    print("SUBSCRIPTION TEST - Listening for VPU-related path updates")
    print("=" * 80)
    
    # Connect
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    
    try:
        print(f"\n[INFO] Connecting to {IP}:{PORT}...")
        sock.connect((IP, PORT))
        print("[INFO] Connected successfully!")
        
        # Subscribe to device and screen updates
        print("\n" + "=" * 80)
        print("SUBSCRIBING TO PATHS")
        print("=" * 80)
        
        subscriptions = [
            "DeviceObject/preconfig/resources/new/$screen/@items/",
            "DeviceObject/preconfig/resources/new/status/mapping/$device/@items/",
            "DeviceObject/system/$device/@items/"
        ]
        
        send_message(sock, {"op": "replace", "path": "Subscriptions", "value": subscriptions})
        
        # Wait and receive messages
        receive_loop(sock, duration=15.0)
        
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
