"""
WebSocket Integration Tests for LabJack Detection Streaming

This module tests the real-time WebSocket streaming functionality for LabJack detections,
ensuring proper message flow, timing accuracy, and integration with the detection pipeline.
"""

import pytest
import asyncio
import json
import time
import websockets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock
import uuid
import threading
import queue

from fastapi.testclient import TestClient
from main import app


class LabJackWebSocketTester:
    """Comprehensive WebSocket testing for LabJack detection streaming"""
    
    def __init__(self):
        self.client = TestClient(app)
        self.base_url = "ws://localhost:8000"
        self.session_id = str(uuid.uuid4())
        self.device_id = "LabJack-WebSocket-Test"
        self.test_results = {}
        
    async def test_websocket_streaming_pipeline(self) -> Dict[str, Any]:
        """Test complete WebSocket streaming pipeline"""
        
        print("🌐 Testing WebSocket Detection Streaming Pipeline...")
        
        test_results = {
            "connection_establishment": False,
            "real_time_streaming": False,
            "message_format_validation": False,
            "detection_event_flow": False,
            "timing_accuracy": False,
            "connection_stability": False,
            "error_handling": False,
            "concurrent_connections": False
        }
        
        try:
            await self._test_basic_connection(test_results)
            await self._test_detection_streaming(test_results)
            await self._test_message_formats(test_results)
            await self._test_timing_accuracy(test_results)
            await self._test_connection_stability(test_results)
            await self._test_error_scenarios(test_results)
            await self._test_concurrent_connections(test_results)
            
        except Exception as e:
            test_results["error"] = str(e)
            print(f"❌ WebSocket testing failed: {e}")
        
        return test_results
    
    async def _test_basic_connection(self, test_results: Dict[str, Any]):
        """Test basic WebSocket connection establishment"""
        try:
            websocket_url = f"{self.base_url}/ws/labjack/stream"
            
            async with websockets.connect(websocket_url, timeout=10) as websocket:
                test_results["connection_establishment"] = True
                
                # Test ping/pong
                await websocket.ping()
                
        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
            test_results["connection_establishment"] = False
    
    async def _test_detection_streaming(self, test_results: Dict[str, Any]):
        """Test real-time detection streaming"""
        try:
            websocket_url = f"{self.base_url}/ws/labjack/stream"
            
            async with websockets.connect(websocket_url) as websocket:
                # Create detection events to trigger streaming
                detection_ids = []
                
                # Create multiple detections in sequence
                for i in range(3):
                    response = self.client.post("/api/labjack-detections/labjack", json={
                        "session_id": self.session_id,
                        "device_id": self.device_id,
                        "hardware_timestamp": datetime.now(timezone.utc).isoformat(),
                        "monotonic_time": time.monotonic(),
                        "signal_value": 3.5 + (i * 0.1),
                        "threshold_value": 3.0,
                        "channel": i,
                        "detection_confidence": 0.9
                    })
                    
                    if response.status_code == 200:
                        detection_ids.append(response.json()["id"])
                    
                    # Small delay between detections
                    await asyncio.sleep(0.1)
                
                # Listen for streaming messages
                messages_received = []
                timeout_count = 0
                max_timeouts = 3
                
                while len(messages_received) < len(detection_ids) and timeout_count < max_timeouts:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        messages_received.append(json.loads(message))
                        print(f"📨 Received WebSocket message: {len(messages_received)}")
                        
                    except asyncio.TimeoutError:
                        timeout_count += 1
                        print(f"⏰ WebSocket timeout {timeout_count}/{max_timeouts}")
                        continue
                
                test_results["real_time_streaming"] = len(messages_received) > 0
                test_results["detection_event_flow"] = len(messages_received) >= len(detection_ids) * 0.5  # At least 50% of messages received
                
        except Exception as e:
            print(f"❌ Detection streaming test failed: {e}")
    
    async def _test_message_formats(self, test_results: Dict[str, Any]):
        """Test WebSocket message format validation"""
        try:
            websocket_url = f"{self.base_url}/ws/labjack/stream"
            
            async with websockets.connect(websocket_url) as websocket:
                # Create a detection to trigger message
                response = self.client.post("/api/labjack-detections/labjack", json={
                    "session_id": self.session_id,
                    "device_id": self.device_id,
                    "hardware_timestamp": datetime.now(timezone.utc).isoformat(),
                    "monotonic_time": time.monotonic(),
                    "signal_value": 4.2,
                    "threshold_value": 3.0,
                    "channel": 0,
                    "detection_confidence": 0.95,
                    "metadata": {"test": "message_format"}
                })
                
                if response.status_code == 200:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        message_data = json.loads(message)
                        
                        # Validate message structure
                        required_fields = ["type", "data", "timestamp"]
                        has_required_fields = all(field in message_data for field in required_fields)
                        
                        # Validate detection data structure
                        detection_data = message_data.get("data", {})
                        detection_fields = ["id", "session_id", "device_id", "signal_value", "hardware_timestamp"]
                        has_detection_fields = all(field in detection_data for field in detection_fields)
                        
                        # Validate data types
                        valid_types = (
                            isinstance(message_data.get("timestamp"), str) and
                            isinstance(detection_data.get("signal_value"), (int, float)) and
                            isinstance(detection_data.get("detection_confidence"), (int, float))
                        )
                        
                        test_results["message_format_validation"] = (
                            has_required_fields and has_detection_fields and valid_types
                        )
                        
                        print(f"📋 Message format validation: {test_results['message_format_validation']}")
                        
                    except asyncio.TimeoutError:
                        print("❌ No message received for format validation")
                        test_results["message_format_validation"] = False
                        
        except Exception as e:
            print(f"❌ Message format test failed: {e}")
    
    async def _test_timing_accuracy(self, test_results: Dict[str, Any]):
        """Test timing accuracy of WebSocket streaming"""
        try:
            websocket_url = f"{self.base_url}/ws/labjack/stream"
            
            async with websockets.connect(websocket_url) as websocket:
                # Record detection creation time
                detection_create_time = time.time()
                
                # Create detection
                response = self.client.post("/api/labjack-detections/labjack", json={
                    "session_id": self.session_id,
                    "device_id": self.device_id,
                    "hardware_timestamp": datetime.now(timezone.utc).isoformat(),
                    "monotonic_time": time.monotonic(),
                    "signal_value": 3.8,
                    "threshold_value": 3.0,
                    "channel": 0
                })
                
                if response.status_code == 200:
                    try:
                        # Wait for WebSocket message
                        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        message_receive_time = time.time()
                        
                        # Calculate latency
                        latency_ms = (message_receive_time - detection_create_time) * 1000
                        
                        print(f"📊 WebSocket streaming latency: {latency_ms:.2f}ms")
                        
                        # Validate latency is reasonable (should be < 1000ms for local testing)
                        test_results["timing_accuracy"] = latency_ms < 1000
                        
                    except asyncio.TimeoutError:
                        print("❌ WebSocket message timeout in timing test")
                        test_results["timing_accuracy"] = False
                        
        except Exception as e:
            print(f"❌ Timing accuracy test failed: {e}")
    
    async def _test_connection_stability(self, test_results: Dict[str, Any]):
        """Test WebSocket connection stability"""
        try:
            websocket_url = f"{self.base_url}/ws/labjack/stream"
            
            async with websockets.connect(websocket_url) as websocket:
                # Test connection stability over time
                stability_tests = []
                
                for i in range(5):
                    try:
                        # Send ping
                        await websocket.ping()
                        
                        # Create detection
                        response = self.client.post("/api/labjack-detections/labjack", json={
                            "session_id": self.session_id,
                            "device_id": self.device_id,
                            "hardware_timestamp": datetime.now(timezone.utc).isoformat(),
                            "monotonic_time": time.monotonic(),
                            "signal_value": 3.0 + (i * 0.1),
                            "threshold_value": 3.0,
                            "channel": 0
                        })
                        
                        stability_tests.append(response.status_code == 200)
                        
                        # Wait between tests
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        print(f"❌ Stability test {i} failed: {e}")
                        stability_tests.append(False)
                
                # Connection is stable if most tests pass
                test_results["connection_stability"] = sum(stability_tests) >= len(stability_tests) * 0.8
                
        except Exception as e:
            print(f"❌ Connection stability test failed: {e}")
    
    async def _test_error_scenarios(self, test_results: Dict[str, Any]):
        """Test WebSocket error handling scenarios"""
        try:
            # Test with invalid WebSocket URL
            invalid_urls = [
                f"{self.base_url}/ws/invalid/endpoint",
                f"{self.base_url}/ws/labjack/invalid"
            ]
            
            error_handling_results = []
            
            for url in invalid_urls:
                try:
                    async with websockets.connect(url, timeout=5) as websocket:
                        # Should not reach here
                        error_handling_results.append(False)
                except Exception:
                    # Expected to fail
                    error_handling_results.append(True)
            
            # Test connection recovery after network interruption
            websocket_url = f"{self.base_url}/ws/labjack/stream"
            
            try:
                async with websockets.connect(websocket_url) as websocket:
                    # Simulate brief network interruption by forcing close and reconnect
                    await websocket.close()
                    
                    # Try to reconnect
                    async with websockets.connect(websocket_url) as new_websocket:
                        await new_websocket.ping()
                        error_handling_results.append(True)
                        
            except Exception:
                error_handling_results.append(False)
            
            test_results["error_handling"] = all(error_handling_results)
            
        except Exception as e:
            print(f"❌ Error scenario test failed: {e}")
            test_results["error_handling"] = False
    
    async def _test_concurrent_connections(self, test_results: Dict[str, Any]):
        """Test multiple concurrent WebSocket connections"""
        try:
            websocket_url = f"{self.base_url}/ws/labjack/stream"
            connection_count = 5
            
            async def create_connection(connection_id):
                """Create a single WebSocket connection and test it"""
                try:
                    async with websockets.connect(websocket_url) as websocket:
                        # Send ping to verify connection
                        await websocket.ping()
                        
                        # Create detection for this connection
                        response = self.client.post("/api/labjack-detections/labjack", json={
                            "session_id": self.session_id,
                            "device_id": f"{self.device_id}-concurrent-{connection_id}",
                            "hardware_timestamp": datetime.now(timezone.utc).isoformat(),
                            "monotonic_time": time.monotonic(),
                            "signal_value": 3.0 + (connection_id * 0.1),
                            "threshold_value": 3.0,
                            "channel": connection_id % 4
                        })
                        
                        # Try to receive message
                        try:
                            await asyncio.wait_for(websocket.recv(), timeout=3.0)
                            return True
                        except asyncio.TimeoutError:
                            return False
                            
                except Exception as e:
                    print(f"❌ Concurrent connection {connection_id} failed: {e}")
                    return False
            
            # Create concurrent connections
            tasks = [create_connection(i) for i in range(connection_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successful connections
            successful_connections = sum(1 for result in results if result is True)
            
            # Consider test passed if at least 80% of connections succeed
            test_results["concurrent_connections"] = successful_connections >= connection_count * 0.8
            
            print(f"📊 Concurrent connections: {successful_connections}/{connection_count} successful")
            
        except Exception as e:
            print(f"❌ Concurrent connections test failed: {e}")
            test_results["concurrent_connections"] = False


@pytest.mark.asyncio
async def test_labjack_websocket_integration():
    """Execute comprehensive WebSocket integration tests"""
    
    tester = LabJackWebSocketTester()
    
    print("\n" + "="*60)
    print("🌐 LABJACK WEBSOCKET INTEGRATION TESTS")
    print("="*60)
    
    results = await tester.test_websocket_streaming_pipeline()
    
    # Print results
    print(f"\n📊 TEST RESULTS:")
    total_tests = len([k for k in results.keys() if k != "error"])
    passed_tests = sum(1 for v in results.values() if v is True)
    
    for test_name, result in results.items():
        if test_name != "error":
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {test_name}: {status}")
    
    success_rate = (passed_tests / max(total_tests, 1)) * 100
    print(f"\n📈 Success Rate: {success_rate:.1f}% ({passed_tests}/{total_tests})")
    
    if "error" in results:
        print(f"❌ Error: {results['error']}")
    
    print("="*60)
    
    # Assert minimum success rate
    assert success_rate >= 70, f"WebSocket tests failed with {success_rate}% success rate"
    
    return results


if __name__ == "__main__":
    # Run the WebSocket tests
    asyncio.run(test_labjack_websocket_integration())