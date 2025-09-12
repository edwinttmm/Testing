#!/usr/bin/env python3
"""
LabJack Bridge Client Example
Demonstrates how to use the LabJack Bridge Service from Python
"""

import asyncio
import json
import requests
import websockets
from typing import Dict, List, Any
import time

class LabJackBridgeClient:
    """Client for interacting with LabJack Bridge Service"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.ws_url = base_url.replace("http", "ws") + "/ws/stream"
        
    def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        response = requests.get(f"{self.api_url}/health")
        response.raise_for_status()
        return response.json()
    
    def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover available LabJack devices"""
        response = requests.get(f"{self.api_url}/devices")
        response.raise_for_status()
        return response.json()["devices"]
    
    def connect_device(self, device_id: str) -> Dict[str, Any]:
        """Connect to a LabJack device"""
        response = requests.post(f"{self.api_url}/devices/{device_id}/connect")
        response.raise_for_status()
        return response.json()
    
    def disconnect_device(self, device_id: str) -> Dict[str, Any]:
        """Disconnect from a LabJack device"""
        response = requests.delete(f"{self.api_url}/devices/{device_id}/disconnect")
        response.raise_for_status()
        return response.json()
    
    def read_analog(self, device_id: str, channels: List[int], 
                   resolution_index: int = 0, settling_time: float = 0) -> Dict[str, Any]:
        """Read analog input channels"""
        data = {
            "device_id": device_id,
            "channels": channels,
            "resolution_index": resolution_index,
            "settling_time": settling_time
        }
        response = requests.post(f"{self.api_url}/analog/read", json=data)
        response.raise_for_status()
        return response.json()
    
    def write_analog(self, device_id: str, channel: int, voltage: float) -> Dict[str, Any]:
        """Write analog output channel"""
        data = {
            "device_id": device_id,
            "channel": channel,
            "voltage": voltage
        }
        response = requests.post(f"{self.api_url}/analog/write", json=data)
        response.raise_for_status()
        return response.json()
    
    def read_digital(self, device_id: str, channels: List[int]) -> Dict[str, Any]:
        """Read digital input channels"""
        data = {
            "device_id": device_id,
            "channels": channels
        }
        response = requests.post(f"{self.api_url}/digital/read", json=data)
        response.raise_for_status()
        return response.json()
    
    def write_digital(self, device_id: str, channel: int, state: bool) -> Dict[str, Any]:
        """Write digital output channel"""
        data = {
            "device_id": device_id,
            "channel": channel,
            "state": state
        }
        response = requests.post(f"{self.api_url}/digital/write", json=data)
        response.raise_for_status()
        return response.json()
    
    def start_streaming(self, device_id: str, channels: List[int], 
                       scan_rate: float = 1000.0, scans_per_read: int = 100) -> Dict[str, Any]:
        """Start streaming data from device"""
        data = {
            "device_id": device_id,
            "channels": channels,
            "scan_rate": scan_rate,
            "scans_per_read": scans_per_read
        }
        response = requests.post(f"{self.api_url}/streaming/start", json=data)
        response.raise_for_status()
        return response.json()
    
    def stop_streaming(self, device_id: str) -> Dict[str, Any]:
        """Stop streaming data from device"""
        response = requests.post(f"{self.api_url}/streaming/stop/{device_id}")
        response.raise_for_status()
        return response.json()
    
    async def websocket_stream_listener(self, callback=None, duration=None):
        """Listen to WebSocket stream data"""
        try:
            async with websockets.connect(self.ws_url) as websocket:
                print(f"Connected to WebSocket: {self.ws_url}")
                
                start_time = time.time()
                while True:
                    if duration and (time.time() - start_time) > duration:
                        break
                    
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        if callback:
                            callback(data)
                        else:
                            print(f"Received data: {data}")
                            
                    except websockets.exceptions.ConnectionClosed:
                        print("WebSocket connection closed")
                        break
                    except Exception as e:
                        print(f"Error receiving WebSocket data: {e}")
                        break
                        
        except Exception as e:
            print(f"Error connecting to WebSocket: {e}")

def stream_data_callback(data):
    """Example callback for processing stream data"""
    device_id = data.get("device_id", "unknown")
    channels = data.get("channels", [])
    values = data.get("data", [])
    timestamp = data.get("timestamp", "")
    
    # Process values per channel
    if values and channels:
        num_channels = len(channels)
        scans = len(values) // num_channels
        
        print(f"\nDevice: {device_id}, Time: {timestamp}")
        print(f"Channels: {channels}, Scans: {scans}")
        
        # Show first few values for each channel
        for i, channel in enumerate(channels):
            channel_values = values[i::num_channels][:5]  # First 5 values
            avg_value = sum(channel_values) / len(channel_values)
            print(f"  CH{channel}: {avg_value:.4f}V (avg of {len(channel_values)} samples)")

async def main():
    """Example usage of LabJack Bridge Client"""
    client = LabJackBridgeClient()
    
    try:
        # Check service health
        print("=== Health Check ===")
        health = client.health_check()
        print(f"Service Status: {health['status']}")
        print(f"LabJack Available: {health['labjack_available']}")
        print(f"Connected Devices: {health['devices_connected']}")
        
        # Discover devices
        print("\n=== Device Discovery ===")
        devices = client.discover_devices()
        print(f"Found {len(devices)} devices:")
        for device in devices:
            print(f"  - {device['device_type']} ({device['connection_type']}) - {device['identifier']}")
        
        if not devices:
            print("No devices found. Make sure LabJack hardware is connected.")
            return
        
        # Connect to first device
        device_id = devices[0]['identifier']
        print(f"\n=== Connecting to Device: {device_id} ===")
        connect_result = client.connect_device(device_id)
        print(f"Connection Status: {connect_result['status']}")
        
        # Read analog inputs
        print(f"\n=== Reading Analog Inputs ===")
        analog_data = client.read_analog(device_id, [0, 1, 2, 3])
        print(f"Analog Values: {analog_data['values']}")
        
        # Read digital inputs
        print(f"\n=== Reading Digital Inputs ===")
        digital_data = client.read_digital(device_id, [0, 1, 2, 3])
        print(f"Digital Values: {digital_data['values']}")
        
        # Write digital output
        print(f"\n=== Writing Digital Output ===")
        write_result = client.write_digital(device_id, 0, True)
        print(f"Write Result: {write_result}")
        
        # Start streaming
        print(f"\n=== Starting Streaming ===")
        stream_result = client.start_streaming(device_id, [0, 1], scan_rate=1000, scans_per_read=100)
        print(f"Streaming Status: {stream_result['status']}")
        
        # Listen to WebSocket stream for 10 seconds
        print(f"\n=== WebSocket Stream (10 seconds) ===")
        await client.websocket_stream_listener(callback=stream_data_callback, duration=10)
        
        # Stop streaming
        print(f"\n=== Stopping Streaming ===")
        stop_result = client.stop_streaming(device_id)
        print(f"Stop Status: {stop_result['status']}")
        
        # Disconnect device
        print(f"\n=== Disconnecting Device ===")
        disconnect_result = client.disconnect_device(device_id)
        print(f"Disconnect Status: {disconnect_result['status']}")
        
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to LabJack Bridge Service.")
        print("Make sure the service is running on http://localhost:8080")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())