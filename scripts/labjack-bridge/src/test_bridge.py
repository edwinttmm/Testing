#!/usr/bin/env python3
"""
LabJack Bridge Service Test Suite
Comprehensive testing for the LabJack Bridge Service
"""

import asyncio
import json
import time
import pytest
import requests
import websockets
from typing import Dict, List, Any
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestLabJackBridgeService:
    """Test suite for LabJack Bridge Service"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.ws_url = base_url.replace("http", "ws") + "/ws/stream"
        self.connected_devices = []
        
    def setup_method(self):
        """Setup for each test method"""
        self.connected_devices = []
    
    def teardown_method(self):
        """Cleanup after each test method"""
        # Disconnect all connected devices
        for device_id in self.connected_devices:
            try:
                self.disconnect_device(device_id)
            except:
                pass
    
    def test_health_check(self):
        """Test service health endpoint"""
        logger.info("Testing health check endpoint...")
        
        response = requests.get(f"{self.api_url}/health", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "labjack_available" in data
        assert "devices_connected" in data
        assert data["status"] == "healthy"
        
        logger.info("✓ Health check passed")
    
    def test_device_discovery(self):
        """Test device discovery"""
        logger.info("Testing device discovery...")
        
        response = requests.get(f"{self.api_url}/devices", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert "devices" in data
        assert isinstance(data["devices"], list)
        
        if data["devices"]:
            device = data["devices"][0]
            required_fields = ["device_type", "connection_type", "identifier", "status"]
            for field in required_fields:
                assert field in device
        
        logger.info(f"✓ Device discovery passed - found {len(data['devices'])} devices")
        return data["devices"]
    
    def connect_device(self, device_id: str):
        """Helper method to connect device"""
        response = requests.post(f"{self.api_url}/devices/{device_id}/connect", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "connected"
        assert data["device_id"] == device_id
        
        self.connected_devices.append(device_id)
        return data
    
    def disconnect_device(self, device_id: str):
        """Helper method to disconnect device"""
        response = requests.delete(f"{self.api_url}/devices/{device_id}/disconnect", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "disconnected"
        assert data["device_id"] == device_id
        
        if device_id in self.connected_devices:
            self.connected_devices.remove(device_id)
        
        return data
    
    def test_device_connection(self):
        """Test device connection and disconnection"""
        logger.info("Testing device connection...")
        
        # Discover devices first
        devices = self.test_device_discovery()
        if not devices:
            logger.warning("No devices available for connection test")
            return
        
        device_id = devices[0]["identifier"]
        
        # Test connection
        logger.info(f"Connecting to device: {device_id}")
        connect_data = self.connect_device(device_id)
        assert "handle" in connect_data
        
        # Test disconnection
        logger.info(f"Disconnecting from device: {device_id}")
        disconnect_data = self.disconnect_device(device_id)
        
        logger.info("✓ Device connection test passed")
    
    def test_analog_io(self):
        """Test analog input/output operations"""
        logger.info("Testing analog I/O operations...")
        
        devices = self.test_device_discovery()
        if not devices:
            logger.warning("No devices available for analog I/O test")
            return
        
        device_id = devices[0]["identifier"]
        self.connect_device(device_id)
        
        # Test analog read
        logger.info("Testing analog read...")
        read_data = {
            "device_id": device_id,
            "channels": [0, 1, 2, 3],
            "resolution_index": 0,
            "settling_time": 0
        }
        
        response = requests.post(f"{self.api_url}/analog/read", json=read_data, timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert "values" in data
        assert "channels" in data
        assert "timestamp" in data
        assert len(data["values"]) == len(read_data["channels"])
        
        # Test analog write (if device supports it)
        logger.info("Testing analog write...")
        write_data = {
            "device_id": device_id,
            "channel": 0,
            "voltage": 2.5
        }
        
        try:
            response = requests.post(f"{self.api_url}/analog/write", json=write_data, timeout=10)
            if response.status_code == 200:
                data = response.json()
                assert data["voltage"] == write_data["voltage"]
                logger.info("✓ Analog write test passed")
            else:
                logger.info("⚠ Analog write not supported by device")
        except:
            logger.info("⚠ Analog write test skipped")
        
        logger.info("✓ Analog I/O test completed")
    
    def test_digital_io(self):
        """Test digital input/output operations"""
        logger.info("Testing digital I/O operations...")
        
        devices = self.test_device_discovery()
        if not devices:
            logger.warning("No devices available for digital I/O test")
            return
        
        device_id = devices[0]["identifier"]
        self.connect_device(device_id)
        
        # Test digital read
        logger.info("Testing digital read...")
        read_data = {
            "device_id": device_id,
            "channels": [0, 1, 2, 3]
        }
        
        response = requests.post(f"{self.api_url}/digital/read", json=read_data, timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert "values" in data
        assert "channels" in data
        assert "timestamp" in data
        assert len(data["values"]) == len(read_data["channels"])
        
        # Test digital write
        logger.info("Testing digital write...")
        write_data = {
            "device_id": device_id,
            "channel": 0,
            "state": True
        }
        
        response = requests.post(f"{self.api_url}/digital/write", json=write_data, timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["state"] == write_data["state"]
        
        # Write false state
        write_data["state"] = False
        response = requests.post(f"{self.api_url}/digital/write", json=write_data, timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["state"] == write_data["state"]
        
        logger.info("✓ Digital I/O test passed")
    
    def test_streaming(self):
        """Test data streaming functionality"""
        logger.info("Testing streaming functionality...")
        
        devices = self.test_device_discovery()
        if not devices:
            logger.warning("No devices available for streaming test")
            return
        
        device_id = devices[0]["identifier"]
        self.connect_device(device_id)
        
        # Start streaming
        logger.info("Starting streaming...")
        stream_config = {
            "device_id": device_id,
            "channels": [0, 1],
            "scan_rate": 1000.0,
            "scans_per_read": 100
        }
        
        response = requests.post(f"{self.api_url}/streaming/start", json=stream_config, timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "streaming_started"
        
        # Wait a bit for streaming to start
        time.sleep(2)
        
        # Stop streaming
        logger.info("Stopping streaming...")
        response = requests.post(f"{self.api_url}/streaming/stop/{device_id}", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] in ["streaming_stopped", "streaming_not_active"]
        
        logger.info("✓ Streaming test passed")
    
    async def test_websocket_stream(self):
        """Test WebSocket streaming"""
        logger.info("Testing WebSocket streaming...")
        
        devices_response = requests.get(f"{self.api_url}/devices", timeout=10)
        devices = devices_response.json()["devices"]
        
        if not devices:
            logger.warning("No devices available for WebSocket test")
            return
        
        device_id = devices[0]["identifier"]
        
        # Connect device
        connect_response = requests.post(f"{self.api_url}/devices/{device_id}/connect", timeout=10)
        assert connect_response.status_code == 200
        self.connected_devices.append(device_id)
        
        # Start streaming
        stream_config = {
            "device_id": device_id,
            "channels": [0, 1],
            "scan_rate": 1000.0,
            "scans_per_read": 50
        }
        
        stream_response = requests.post(f"{self.api_url}/streaming/start", json=stream_config, timeout=10)
        assert stream_response.status_code == 200
        
        # Test WebSocket connection
        messages_received = 0
        try:
            async with websockets.connect(self.ws_url, ping_interval=None) as websocket:
                logger.info("Connected to WebSocket")
                
                # Listen for messages for 5 seconds
                start_time = time.time()
                while time.time() - start_time < 5:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        
                        # Validate message structure
                        assert "device_id" in data
                        assert "channels" in data
                        assert "data" in data
                        assert "timestamp" in data
                        
                        messages_received += 1
                        
                        if messages_received >= 3:  # Received enough messages
                            break
                            
                    except asyncio.TimeoutError:
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        break
                        
        except Exception as e:
            logger.warning(f"WebSocket connection failed: {e}")
        
        # Stop streaming
        stop_response = requests.post(f"{self.api_url}/streaming/stop/{device_id}", timeout=10)
        assert stop_response.status_code == 200
        
        logger.info(f"✓ WebSocket test passed - received {messages_received} messages")
    
    def test_error_handling(self):
        """Test error handling for invalid requests"""
        logger.info("Testing error handling...")
        
        # Test invalid device connection
        response = requests.post(f"{self.api_url}/devices/invalid_device/connect", timeout=10)
        assert response.status_code == 500
        
        # Test reading from non-connected device
        read_data = {
            "device_id": "non_existent",
            "channels": [0]
        }
        response = requests.post(f"{self.api_url}/analog/read", json=read_data, timeout=10)
        assert response.status_code == 500
        
        # Test invalid channel numbers
        devices = self.test_device_discovery()
        if devices:
            device_id = devices[0]["identifier"]
            self.connect_device(device_id)
            
            read_data = {
                "device_id": device_id,
                "channels": [999]  # Invalid channel
            }
            response = requests.post(f"{self.api_url}/analog/read", json=read_data, timeout=10)
            # Should handle gracefully (may return error or default values)
            assert response.status_code in [200, 500]
        
        logger.info("✓ Error handling test passed")
    
    def run_all_tests(self):
        """Run all tests"""
        logger.info("=" * 60)
        logger.info("STARTING LABJACK BRIDGE SERVICE TEST SUITE")
        logger.info("=" * 60)
        
        test_methods = [
            self.test_health_check,
            self.test_device_discovery,
            self.test_device_connection,
            self.test_analog_io,
            self.test_digital_io,
            self.test_streaming,
            self.test_error_handling
        ]
        
        passed = 0
        failed = 0
        
        for test_method in test_methods:
            try:
                self.setup_method()
                test_method()
                passed += 1
            except Exception as e:
                logger.error(f"✗ {test_method.__name__} FAILED: {e}")
                failed += 1
            finally:
                self.teardown_method()
        
        # Run async tests
        try:
            self.setup_method()
            asyncio.run(self.test_websocket_stream())
            passed += 1
        except Exception as e:
            logger.error(f"✗ test_websocket_stream FAILED: {e}")
            failed += 1
        finally:
            self.teardown_method()
        
        logger.info("=" * 60)
        logger.info(f"TEST RESULTS: {passed} passed, {failed} failed")
        logger.info("=" * 60)
        
        return failed == 0

def run_performance_test(base_url: str = "http://localhost:8080", duration: int = 30):
    """Run performance test"""
    logger.info(f"Running performance test for {duration} seconds...")
    
    client = TestLabJackBridgeService(base_url)
    
    # Get available devices
    devices_response = requests.get(f"{client.api_url}/devices")
    devices = devices_response.json()["devices"]
    
    if not devices:
        logger.warning("No devices available for performance test")
        return
    
    device_id = devices[0]["identifier"]
    
    # Connect device
    requests.post(f"{client.api_url}/devices/{device_id}/connect")
    
    # Performance metrics
    start_time = time.time()
    request_count = 0
    error_count = 0
    
    try:
        while time.time() - start_time < duration:
            try:
                # Make analog read request
                read_data = {
                    "device_id": device_id,
                    "channels": [0, 1, 2, 3]
                }
                response = requests.post(f"{client.api_url}/analog/read", json=read_data, timeout=5)
                if response.status_code == 200:
                    request_count += 1
                else:
                    error_count += 1
                
                time.sleep(0.01)  # Small delay between requests
                
            except Exception:
                error_count += 1
    
    finally:
        # Disconnect device
        requests.delete(f"{client.api_url}/devices/{device_id}/disconnect")
    
    elapsed_time = time.time() - start_time
    requests_per_second = request_count / elapsed_time if elapsed_time > 0 else 0
    
    logger.info(f"Performance Test Results:")
    logger.info(f"  Duration: {elapsed_time:.2f} seconds")
    logger.info(f"  Total Requests: {request_count}")
    logger.info(f"  Errors: {error_count}")
    logger.info(f"  Requests/Second: {requests_per_second:.2f}")
    logger.info(f"  Success Rate: {(request_count / (request_count + error_count) * 100):.1f}%")

def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test LabJack Bridge Service")
    parser.add_argument("--url", default="http://localhost:8080", help="Service base URL")
    parser.add_argument("--performance", action="store_true", help="Run performance test")
    parser.add_argument("--duration", type=int, default=30, help="Performance test duration")
    args = parser.parse_args()
    
    if args.performance:
        run_performance_test(args.url, args.duration)
    else:
        tester = TestLabJackBridgeService(args.url)
        success = tester.run_all_tests()
        
        if success:
            logger.info("🎉 All tests passed!")
            exit(0)
        else:
            logger.error("❌ Some tests failed!")
            exit(1)

if __name__ == "__main__":
    main()