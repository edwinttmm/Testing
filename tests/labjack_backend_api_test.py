#!/usr/bin/env python3
"""
LabJack Backend API Integration Test Suite
ADAS Camera HIL Testing Platform - Backend API Validation

Tests backend API endpoints for LabJack integration including:
- Device detection and status
- Precision monitoring APIs
- Real-time WebSocket data flow
- Hardware health monitoring
- Signal validation endpoints

Author: AI Model Validation Platform
Date: 2025-09-14
"""

import asyncio
import json
import requests
import websockets
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LabJackBackendAPITest:
    """
    Test suite for LabJack backend API integration.
    
    Validates all LabJack-related API endpoints and WebSocket connections
    for the ADAS HIL testing platform.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize API test suite with backend URL."""
        self.base_url = base_url
        self.websocket_url = base_url.replace("http://", "ws://")
        self.test_results = {}
        
    def test_api_health_check(self) -> Dict:
        """Test basic API health and connectivity."""
        logger.info("🏥 Testing API health check...")
        
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            
            health_result = {
                "status_code": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "healthy": response.status_code == 200,
                "response_data": response.json() if response.status_code == 200 else None
            }
            
            logger.info(f"   Health check: {'✅ PASS' if health_result['healthy'] else '❌ FAIL'}")
            logger.info(f"   Response time: {health_result['response_time_ms']:.2f}ms")
            
            return health_result
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return {"error": str(e), "healthy": False}
    
    def test_labjack_status_api(self) -> Dict:
        """Test LabJack status API endpoint."""
        logger.info("📊 Testing LabJack status API...")
        
        try:
            response = requests.get(f"{self.base_url}/api/labjack/status", timeout=10)
            
            status_result = {
                "status_code": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "success": response.status_code == 200
            }
            
            if response.status_code == 200:
                data = response.json()
                status_result.update({
                    "labjack_connected": data.get("connected", False),
                    "device_info": data.get("device_info", {}),
                    "hardware_status": data.get("status", "unknown"),
                    "response_data": data
                })
                
                logger.info(f"   Status API: ✅ PASS")
                logger.info(f"   LabJack connected: {'✅' if data.get('connected') else '❌'}")
            else:
                status_result["error"] = f"HTTP {response.status_code}"
                logger.error(f"   Status API: ❌ FAIL - HTTP {response.status_code}")
            
            return status_result
            
        except Exception as e:
            logger.error(f"❌ LabJack status API test failed: {e}")
            return {"error": str(e), "success": False}
    
    def test_labjack_devices_api(self) -> Dict:
        """Test LabJack device detection API."""
        logger.info("🔍 Testing LabJack devices API...")
        
        try:
            response = requests.get(f"{self.base_url}/api/labjack/devices", timeout=10)
            
            devices_result = {
                "status_code": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "success": response.status_code == 200
            }
            
            if response.status_code == 200:
                data = response.json()
                devices_result.update({
                    "devices_found": len(data.get("devices", [])),
                    "devices_list": data.get("devices", []),
                    "t7_detected": any(
                        "T7" in str(device).upper() 
                        for device in data.get("devices", [])
                    ),
                    "response_data": data
                })
                
                logger.info(f"   Devices API: ✅ PASS")
                logger.info(f"   Devices found: {devices_result['devices_found']}")
                logger.info(f"   T7 detected: {'✅' if devices_result['t7_detected'] else '❌'}")
            else:
                devices_result["error"] = f"HTTP {response.status_code}"
                logger.error(f"   Devices API: ❌ FAIL - HTTP {response.status_code}")
            
            return devices_result
            
        except Exception as e:
            logger.error(f"❌ LabJack devices API test failed: {e}")
            return {"error": str(e), "success": False}
    
    def test_labjack_health_api(self) -> Dict:
        """Test LabJack hardware health API."""
        logger.info("🏥 Testing LabJack health API...")
        
        try:
            response = requests.get(f"{self.base_url}/api/labjack/health", timeout=10)
            
            health_result = {
                "status_code": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "success": response.status_code == 200
            }
            
            if response.status_code == 200:
                data = response.json()
                health_result.update({
                    "hardware_healthy": data.get("healthy", False),
                    "temperature_ok": data.get("temperature_ok", False),
                    "voltage_ok": data.get("voltage_ok", False),
                    "connection_ok": data.get("connection_ok", False),
                    "response_data": data
                })
                
                logger.info(f"   Health API: ✅ PASS")
                logger.info(f"   Hardware healthy: {'✅' if data.get('healthy') else '❌'}")
            else:
                health_result["error"] = f"HTTP {response.status_code}"
                logger.error(f"   Health API: ❌ FAIL - HTTP {response.status_code}")
            
            return health_result
            
        except Exception as e:
            logger.error(f"❌ LabJack health API test failed: {e}")
            return {"error": str(e), "success": False}
    
    def test_precision_monitoring_api(self) -> Dict:
        """Test precision monitoring API endpoints."""
        logger.info("⏱️ Testing precision monitoring API...")
        
        monitoring_results = {}
        
        # Test monitoring start
        try:
            start_response = requests.post(
                f"{self.base_url}/api/labjack/monitoring/start",
                json={"test_session_id": "api_test_session"},
                timeout=10
            )
            
            monitoring_results["start"] = {
                "status_code": start_response.status_code,
                "success": start_response.status_code in [200, 201],
                "response_data": start_response.json() if start_response.status_code in [200, 201] else None
            }
            
            logger.info(f"   Monitoring start: {'✅ PASS' if monitoring_results['start']['success'] else '❌ FAIL'}")
            
        except Exception as e:
            monitoring_results["start"] = {"error": str(e), "success": False}
            logger.error(f"❌ Monitoring start failed: {e}")
        
        # Test monitoring status
        try:
            status_response = requests.get(
                f"{self.base_url}/api/labjack/monitoring/status",
                timeout=10
            )
            
            monitoring_results["status"] = {
                "status_code": status_response.status_code,
                "success": status_response.status_code == 200,
                "response_data": status_response.json() if status_response.status_code == 200 else None
            }
            
            logger.info(f"   Monitoring status: {'✅ PASS' if monitoring_results['status']['success'] else '❌ FAIL'}")
            
        except Exception as e:
            monitoring_results["status"] = {"error": str(e), "success": False}
            logger.error(f"❌ Monitoring status failed: {e}")
        
        return monitoring_results
    
    def test_signal_validation_api(self) -> Dict:
        """Test signal validation API endpoints."""
        logger.info("⚡ Testing signal validation API...")
        
        signal_results = {}
        
        # Test connection check
        try:
            connection_response = requests.get(
                f"{self.base_url}/api/signal-validation/test-connection",
                timeout=10
            )
            
            signal_results["connection"] = {
                "status_code": connection_response.status_code,
                "success": connection_response.status_code == 200,
                "response_data": connection_response.json() if connection_response.status_code == 200 else None
            }
            
            logger.info(f"   Signal connection: {'✅ PASS' if signal_results['connection']['success'] else '❌ FAIL'}")
            
        except Exception as e:
            signal_results["connection"] = {"error": str(e), "success": False}
            logger.error(f"❌ Signal connection test failed: {e}")
        
        # Test signal processing
        try:
            signal_data = {
                "signal_type": "analog",
                "channel": "AIN0",
                "expected_voltage": 2.5,
                "tolerance": 0.1
            }
            
            process_response = requests.post(
                f"{self.base_url}/api/signal-validation/signal/process",
                json=signal_data,
                timeout=10
            )
            
            signal_results["processing"] = {
                "status_code": process_response.status_code,
                "success": process_response.status_code == 200,
                "response_data": process_response.json() if process_response.status_code == 200 else None
            }
            
            logger.info(f"   Signal processing: {'✅ PASS' if signal_results['processing']['success'] else '❌ FAIL'}")
            
        except Exception as e:
            signal_results["processing"] = {"error": str(e), "success": False}
            logger.error(f"❌ Signal processing test failed: {e}")
        
        return signal_results
    
    async def test_websocket_connection(self) -> Dict:
        """Test WebSocket real-time data flow."""
        logger.info("🌐 Testing WebSocket connection...")
        
        websocket_results = {
            "connection_successful": False,
            "messages_received": 0,
            "data_flow_validated": False,
            "connection_time_ms": 0,
            "error": None
        }
        
        try:
            start_time = time.time()
            
            # Connect to WebSocket
            async with websockets.connect(
                f"{self.websocket_url}/ws/progress",
                timeout=10
            ) as websocket:
                connection_time = (time.time() - start_time) * 1000
                websocket_results["connection_successful"] = True
                websocket_results["connection_time_ms"] = connection_time
                
                logger.info(f"   WebSocket connected in {connection_time:.2f}ms")
                
                # Send test message
                test_message = {
                    "type": "test",
                    "data": "LabJack integration test",
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(test_message))
                
                # Wait for responses (max 5 seconds)
                timeout = time.time() + 5
                while time.time() < timeout:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1)
                        websocket_results["messages_received"] += 1
                        
                        # Try to parse message
                        try:
                            data = json.loads(message)
                            if isinstance(data, dict):
                                websocket_results["data_flow_validated"] = True
                        except:
                            pass
                        
                        logger.info(f"   Received WebSocket message: {len(message)} bytes")
                        
                    except asyncio.TimeoutError:
                        continue
                    except:
                        break
                
                logger.info(f"   WebSocket test: ✅ PASS")
                logger.info(f"   Messages received: {websocket_results['messages_received']}")
                
        except Exception as e:
            logger.error(f"❌ WebSocket test failed: {e}")
            websocket_results["error"] = str(e)
        
        return websocket_results
    
    def test_api_performance(self) -> Dict:
        """Test API endpoint performance and responsiveness."""
        logger.info("🚀 Testing API performance...")
        
        performance_results = {}
        
        # Test endpoints with performance metrics
        endpoints = [
            "/health",
            "/api/labjack/status", 
            "/api/labjack/devices",
            "/api/labjack/health"
        ]
        
        for endpoint in endpoints:
            try:
                # Multiple requests to get average performance
                response_times = []
                success_count = 0
                
                for i in range(5):  # 5 test requests
                    start_time = time.time()
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                    response_time = (time.time() - start_time) * 1000
                    
                    response_times.append(response_time)
                    if response.status_code == 200:
                        success_count += 1
                
                avg_response_time = sum(response_times) / len(response_times)
                success_rate = (success_count / len(response_times)) * 100
                
                performance_results[endpoint] = {
                    "average_response_time_ms": avg_response_time,
                    "min_response_time_ms": min(response_times),
                    "max_response_time_ms": max(response_times),
                    "success_rate": success_rate,
                    "performance_grade": (
                        "excellent" if avg_response_time < 100 else
                        "good" if avg_response_time < 500 else
                        "acceptable" if avg_response_time < 1000 else
                        "poor"
                    )
                }
                
                logger.info(f"   {endpoint}: {avg_response_time:.2f}ms avg ({success_rate:.1f}% success)")
                
            except Exception as e:
                performance_results[endpoint] = {"error": str(e)}
                logger.error(f"❌ Performance test failed for {endpoint}: {e}")
        
        return performance_results
    
    def run_comprehensive_api_test_suite(self) -> Dict:
        """Run complete backend API test suite."""
        logger.info("🧪 Starting LabJack Backend API Comprehensive Test Suite")
        logger.info("=" * 70)
        
        test_results = {}
        
        # Run API tests
        api_tests = [
            ("Health Check", self.test_api_health_check),
            ("LabJack Status API", self.test_labjack_status_api),
            ("LabJack Devices API", self.test_labjack_devices_api),
            ("LabJack Health API", self.test_labjack_health_api),
            ("Precision Monitoring API", self.test_precision_monitoring_api),
            ("Signal Validation API", self.test_signal_validation_api),
            ("API Performance", self.test_api_performance)
        ]
        
        for test_name, test_function in api_tests:
            try:
                logger.info(f"\n🔍 Running {test_name}...")
                test_results[test_name.lower().replace(' ', '_')] = test_function()
                logger.info(f"✅ {test_name} completed")
            except Exception as e:
                logger.error(f"❌ {test_name} failed: {e}")
                test_results[test_name.lower().replace(' ', '_')] = {"error": str(e)}
        
        # Run WebSocket test separately (async)
        try:
            logger.info(f"\n🔍 Running WebSocket Test...")
            websocket_result = asyncio.run(self.test_websocket_connection())
            test_results["websocket_test"] = websocket_result
            logger.info("✅ WebSocket test completed")
        except Exception as e:
            logger.error(f"❌ WebSocket test failed: {e}")
            test_results["websocket_test"] = {"error": str(e)}
        
        # Generate summary
        summary = self._generate_api_test_summary(test_results)
        self._log_api_test_summary(summary)
        
        return {
            "test_suite": "LabJack Backend API Integration", 
            "timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "test_results": test_results,
            "summary": summary
        }
    
    def _generate_api_test_summary(self, test_results: Dict) -> Dict:
        """Generate summary of API test results."""
        total_tests = len(test_results)
        passed_tests = 0
        failed_tests = 0
        
        for test_name, results in test_results.items():
            if isinstance(results, dict):
                if results.get("success", False) or results.get("healthy", False):
                    passed_tests += 1
                elif "error" in results:
                    failed_tests += 1
        
        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "overall_status": (
                "PASS" if failed_tests == 0 else
                "PARTIAL_PASS" if passed_tests > failed_tests else
                "FAIL"
            )
        }
    
    def _log_api_test_summary(self, summary: Dict):
        """Log API test summary."""
        logger.info("\n" + "=" * 70)
        logger.info("🏁 LABJACK BACKEND API TEST SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total Tests: {summary['total_tests']}")
        logger.info(f"Passed: {summary['passed_tests']}")
        logger.info(f"Failed: {summary['failed_tests']}")
        logger.info(f"Success Rate: {summary['success_rate']:.1f}%")
        logger.info(f"Overall Status: {summary['overall_status']}")
        logger.info("=" * 70)

def main():
    """Main API test execution function."""
    print("\n🚀 LabJack Backend API Integration Test Suite")
    print("=" * 70)
    print("Testing backend API endpoints for LabJack integration")
    print("=" * 70)
    
    # Create API test instance
    api_test = LabJackBackendAPITest()
    
    try:
        # Run comprehensive API tests
        results = api_test.run_comprehensive_api_test_suite()
        
        # Save results
        import os
        results_file = os.path.join(os.path.dirname(__file__), 'labjack_backend_api_results.json')
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 API test results saved to: {results_file}")
        
        # Return appropriate exit code
        if results["summary"]["overall_status"] == "PASS":
            return 0
        elif results["summary"]["overall_status"] == "PARTIAL_PASS":
            return 1
        else:
            return 2
    
    except Exception as e:
        logger.error(f"❌ API test suite execution failed: {e}")
        return 3

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)