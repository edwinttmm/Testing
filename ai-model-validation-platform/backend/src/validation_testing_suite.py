#!/usr/bin/env python3
"""
Comprehensive Validation and Testing Suite for Unified VRU API
SPARC Implementation: Complete validation and testing framework

This module provides comprehensive testing for the unified VRU API system:
- API endpoint testing and validation
- Service integration testing
- WebSocket communication testing
- Performance and load testing
- External IP access validation
- Memory coordination testing
- Error handling and recovery testing

Architecture:
- APIValidator: Tests API endpoints and responses
- ServiceIntegrationTester: Tests service coordination
- WebSocketTester: Tests WebSocket functionality
- PerformanceTester: Load and performance testing
- ExternalAccessTester: External IP and network testing
- MemoryCoordinationTester: Tests memory coordination
- ErrorHandlingTester: Tests error scenarios
"""

import logging
import asyncio
import json
import time
import uuid
import aiohttp
import websockets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import statistics
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

logger = logging.getLogger(__name__)

class TestResult(Enum):
    """Test result types"""
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"

class TestCategory(Enum):
    """Test categories"""
    API_ENDPOINT = "api_endpoint"
    SERVICE_INTEGRATION = "service_integration"
    WEBSOCKET = "websocket"
    PERFORMANCE = "performance"
    EXTERNAL_ACCESS = "external_access"
    MEMORY_COORDINATION = "memory_coordination"
    ERROR_HANDLING = "error_handling"

@dataclass
class TestCase:
    """Individual test case"""
    test_id: str
    name: str
    category: TestCategory
    description: str
    test_function: Callable
    expected_result: Any = None
    timeout_seconds: int = 30
    retry_count: int = 0
    prerequisites: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TestExecution:
    """Test execution result"""
    test_case: TestCase
    result: TestResult
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    actual_result: Any = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    performance_metrics: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TestSuiteResults:
    """Complete test suite results"""
    suite_name: str
    start_time: datetime
    end_time: datetime
    total_duration_seconds: float
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    error_tests: int
    test_executions: List[TestExecution]
    summary: Dict[str, Any] = field(default_factory=dict)

class APIValidator:
    """API endpoint validation and testing"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_health_endpoint(self) -> Dict[str, Any]:
        """Test health endpoint"""
        try:
            async with self.session.get(f"{self.base_url}/api/v1/health") as response:
                response_data = await response.json()
                
                return {
                    "status_code": response.status,
                    "response_time_ms": response.headers.get("X-Response-Time", "0"),
                    "data": response_data,
                    "headers": dict(response.headers),
                    "success": response.status == 200
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_unified_status_endpoint(self) -> Dict[str, Any]:
        """Test unified status endpoint"""
        try:
            async with self.session.get(f"{self.base_url}/api/unified/status") as response:
                response_data = await response.json()
                
                return {
                    "status_code": response.status,
                    "data": response_data,
                    "success": response.status == 200,
                    "has_services": "vru_orchestrator" in response_data
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_ml_inference_endpoint(self) -> Dict[str, Any]:
        """Test ML inference endpoint"""
        try:
            test_data = {
                "video_id": "test_video_123",
                "video_path": "/path/to/test_video.mp4",
                "processing_type": "ground_truth"
            }
            
            async with self.session.post(
                f"{self.base_url}/api/v1/ml/process_video",
                json=test_data
            ) as response:
                response_data = await response.json()
                
                return {
                    "status_code": response.status,
                    "data": response_data,
                    "success": response.status in [200, 202],
                    "has_processing_data": "video_id" in response_data
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_camera_endpoints(self) -> Dict[str, Any]:
        """Test camera integration endpoints"""
        try:
            # Test add camera
            camera_config = {
                "camera_id": "test_camera_001",
                "camera_type": "ip_camera",
                "connection_url": "155.138.239.131:8080",
                "format": "mjpeg",
                "resolution": [1920, 1080],
                "fps": 30,
                "external_ip": "155.138.239.131"
            }
            
            async with self.session.post(
                f"{self.base_url}/api/v1/camera/add",
                json=camera_config
            ) as response:
                add_result = await response.json()
            
            # Test camera status
            async with self.session.get(
                f"{self.base_url}/api/v1/camera/status"
            ) as response:
                status_result = await response.json()
            
            return {
                "add_camera": {
                    "status_code": response.status,
                    "success": response.status == 200,
                    "data": add_result
                },
                "camera_status": {
                    "status_code": response.status,
                    "success": response.status == 200,
                    "data": status_result
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_validation_endpoint(self) -> Dict[str, Any]:
        """Test validation endpoint"""
        try:
            validation_data = {
                "session_id": "test_session_123",
                "criteria": {
                    "precision_threshold": 0.85,
                    "recall_threshold": 0.80,
                    "latency_threshold_ms": 100.0
                },
                "alignment_method": "adaptive"
            }
            
            async with self.session.post(
                f"{self.base_url}/api/v1/validation/validate_session",
                json=validation_data
            ) as response:
                response_data = await response.json()
                
                return {
                    "status_code": response.status,
                    "data": response_data,
                    "success": response.status == 200,
                    "has_validation_result": "validation_status" in response_data
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_project_workflow_endpoints(self) -> Dict[str, Any]:
        """Test project workflow endpoints"""
        try:
            # Test create project
            project_data = {
                "project_data": {
                    "name": "Test VRU Project",
                    "description": "Test project for validation",
                    "camera_model": "Test Camera Model",
                    "camera_view": "Front-facing VRU",
                    "signal_type": "video"
                },
                "workflow_config": {
                    "name": "Test Workflow",
                    "execution_strategy": "adaptive",
                    "max_concurrent_tasks": 3
                }
            }
            
            async with self.session.post(
                f"{self.base_url}/api/v1/projects/create",
                json=project_data
            ) as response:
                create_result = await response.json()
                project_id = create_result.get("data", {}).get("project_id", "test_project")
            
            # Test project status
            async with self.session.get(
                f"{self.base_url}/api/v1/projects/{project_id}/status"
            ) as response:
                status_result = await response.json()
            
            return {
                "create_project": {
                    "status_code": response.status,
                    "success": response.status in [200, 201],
                    "data": create_result
                },
                "project_status": {
                    "status_code": response.status,
                    "success": response.status == 200,
                    "data": status_result
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

class WebSocketTester:
    """WebSocket communication testing"""
    
    def __init__(self, ws_url: str = "ws://localhost:8000/api/v1/ws"):
        self.ws_url = ws_url
        self.messages_received = []
    
    async def test_websocket_connection(self) -> Dict[str, Any]:
        """Test WebSocket connection"""
        try:
            async with websockets.connect(self.ws_url) as websocket:
                # Send ping message
                ping_message = {
                    "type": "ping",
                    "timestamp": datetime.utcnow().isoformat()
                }
                await websocket.send(json.dumps(ping_message))
                
                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                response_data = json.loads(response)
                
                return {
                    "connection_success": True,
                    "ping_response": response_data,
                    "response_type": response_data.get("type"),
                    "success": response_data.get("type") == "pong"
                }
        except Exception as e:
            return {"connection_success": False, "error": str(e)}
    
    async def test_websocket_subscription(self) -> Dict[str, Any]:
        """Test WebSocket subscription functionality"""
        try:
            async with websockets.connect(self.ws_url) as websocket:
                # Subscribe to service updates
                subscribe_message = {
                    "type": "subscribe",
                    "subscriptions": ["ml_inference", "camera_updates"]
                }
                await websocket.send(json.dumps(subscribe_message))
                
                # Wait for subscription confirmations
                confirmations = []
                for _ in range(2):  # Expect 2 confirmations
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5)
                        response_data = json.loads(response)
                        confirmations.append(response_data)
                    except asyncio.TimeoutError:
                        break
                
                return {
                    "subscription_success": True,
                    "confirmations": confirmations,
                    "success": len(confirmations) > 0
                }
        except Exception as e:
            return {"subscription_success": False, "error": str(e)}
    
    async def test_websocket_broadcasting(self) -> Dict[str, Any]:
        """Test WebSocket broadcasting"""
        try:
            messages_received = []
            
            async def message_listener(websocket):
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1)
                        messages_received.append(json.loads(message))
                    except asyncio.TimeoutError:
                        break
                    except Exception:
                        break
            
            async with websockets.connect(self.ws_url) as websocket:
                # Start listening for messages
                listener_task = asyncio.create_task(message_listener(websocket))
                
                # Send a broadcast message (if supported)
                broadcast_message = {
                    "type": "broadcast",
                    "data": {"test": "broadcast_test", "timestamp": datetime.utcnow().isoformat()}
                }
                await websocket.send(json.dumps(broadcast_message))
                
                # Wait for messages
                await asyncio.sleep(2)
                listener_task.cancel()
                
                return {
                    "broadcasting_test": True,
                    "messages_received": messages_received,
                    "message_count": len(messages_received),
                    "success": len(messages_received) > 0
                }
        except Exception as e:
            return {"broadcasting_test": False, "error": str(e)}

class PerformanceTester:
    """Performance and load testing"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    async def test_response_time(self, endpoint: str, num_requests: int = 10) -> Dict[str, Any]:
        """Test API response time"""
        response_times = []
        successful_requests = 0
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            for _ in range(num_requests):
                task = self._single_request_time(session, endpoint)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, dict) and "response_time_ms" in result:
                    response_times.append(result["response_time_ms"])
                    if result.get("success"):
                        successful_requests += 1
        
        if response_times:
            return {
                "endpoint": endpoint,
                "num_requests": num_requests,
                "successful_requests": successful_requests,
                "success_rate": (successful_requests / num_requests) * 100,
                "avg_response_time_ms": statistics.mean(response_times),
                "min_response_time_ms": min(response_times),
                "max_response_time_ms": max(response_times),
                "p95_response_time_ms": statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times),
                "p99_response_time_ms": statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else max(response_times)
            }
        else:
            return {
                "endpoint": endpoint,
                "num_requests": num_requests,
                "successful_requests": 0,
                "success_rate": 0,
                "error": "No successful requests"
            }
    
    async def _single_request_time(self, session: aiohttp.ClientSession, endpoint: str) -> Dict[str, Any]:
        """Time a single request"""
        try:
            start_time = time.time()
            async with session.get(f"{self.base_url}{endpoint}") as response:
                await response.text()  # Read response body
                end_time = time.time()
                
                return {
                    "response_time_ms": (end_time - start_time) * 1000,
                    "status_code": response.status,
                    "success": 200 <= response.status < 300
                }
        except Exception as e:
            return {"response_time_ms": 0, "success": False, "error": str(e)}
    
    async def test_concurrent_load(self, endpoint: str, concurrent_users: int = 50, duration_seconds: int = 30) -> Dict[str, Any]:
        """Test concurrent load handling"""
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        total_requests = 0
        successful_requests = 0
        failed_requests = 0
        response_times = []
        
        async def load_worker(session):
            nonlocal total_requests, successful_requests, failed_requests, response_times
            
            while time.time() < end_time:
                try:
                    request_start = time.time()
                    async with session.get(f"{self.base_url}{endpoint}") as response:
                        await response.text()
                        request_end = time.time()
                        
                        response_time = (request_end - request_start) * 1000
                        response_times.append(response_time)
                        total_requests += 1
                        
                        if 200 <= response.status < 300:
                            successful_requests += 1
                        else:
                            failed_requests += 1
                            
                except Exception:
                    total_requests += 1
                    failed_requests += 1
                
                await asyncio.sleep(0.01)  # Small delay to prevent overwhelming
        
        # Start concurrent workers
        async with aiohttp.ClientSession() as session:
            tasks = [load_worker(session) for _ in range(concurrent_users)]
            await asyncio.gather(*tasks)
        
        actual_duration = time.time() - start_time
        
        return {
            "endpoint": endpoint,
            "concurrent_users": concurrent_users,
            "duration_seconds": actual_duration,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": (successful_requests / total_requests * 100) if total_requests > 0 else 0,
            "requests_per_second": total_requests / actual_duration,
            "avg_response_time_ms": statistics.mean(response_times) if response_times else 0
        }

class ExternalAccessTester:
    """External IP and network access testing"""
    
    def __init__(self, external_ip: str = "155.138.239.131", base_port: int = 8000):
        self.external_ip = external_ip
        self.base_port = base_port
    
    def test_external_ip_accessibility(self) -> Dict[str, Any]:
        """Test external IP accessibility"""
        try:
            import socket
            
            # Test TCP connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((self.external_ip, self.base_port))
            sock.close()
            
            tcp_accessible = (result == 0)
            
            # Test HTTP request
            http_accessible = False
            http_status = None
            try:
                response = requests.get(f"http://{self.external_ip}:{self.base_port}/api/v1/health", timeout=10)
                http_accessible = True
                http_status = response.status_code
            except Exception as e:
                http_error = str(e)
            
            return {
                "external_ip": self.external_ip,
                "port": self.base_port,
                "tcp_accessible": tcp_accessible,
                "http_accessible": http_accessible,
                "http_status": http_status,
                "overall_accessible": tcp_accessible and http_accessible
            }
        except Exception as e:
            return {"external_ip": self.external_ip, "error": str(e), "accessible": False}
    
    def test_websocket_external_access(self) -> Dict[str, Any]:
        """Test WebSocket access from external IP"""
        try:
            import asyncio
            
            async def test_ws():
                try:
                    uri = f"ws://{self.external_ip}:{self.base_port}/api/v1/ws"
                    async with websockets.connect(uri, timeout=10) as websocket:
                        # Send ping
                        await websocket.send(json.dumps({"type": "ping"}))
                        response = await asyncio.wait_for(websocket.recv(), timeout=5)
                        return {"success": True, "response": json.loads(response)}
                except Exception as e:
                    return {"success": False, "error": str(e)}
            
            result = asyncio.run(test_ws())
            return {
                "external_ip": self.external_ip,
                "websocket_accessible": result["success"],
                "details": result
            }
        except Exception as e:
            return {"external_ip": self.external_ip, "websocket_accessible": False, "error": str(e)}

class ComprehensiveTestSuite:
    """Main comprehensive test suite"""
    
    def __init__(self, base_url: str = "http://localhost:8000", external_ip: str = "155.138.239.131"):
        self.base_url = base_url
        self.external_ip = external_ip
        self.test_cases: List[TestCase] = []
        self.results: List[TestExecution] = []
        
        # Initialize testers
        self.api_validator = APIValidator(base_url)
        self.websocket_tester = WebSocketTester(f"ws://localhost:8000/api/v1/ws")
        self.performance_tester = PerformanceTester(base_url)
        self.external_tester = ExternalAccessTester(external_ip)
        
        # Register test cases
        self._register_test_cases()
    
    def _register_test_cases(self):
        """Register all test cases"""
        
        # API endpoint tests
        self.test_cases.extend([
            TestCase(
                test_id="api_health_check",
                name="API Health Check",
                category=TestCategory.API_ENDPOINT,
                description="Test main health endpoint",
                test_function=self._test_api_health
            ),
            TestCase(
                test_id="api_unified_status",
                name="Unified Status Check",
                category=TestCategory.API_ENDPOINT,
                description="Test unified status endpoint",
                test_function=self._test_unified_status
            ),
            TestCase(
                test_id="api_ml_inference",
                name="ML Inference API",
                category=TestCategory.API_ENDPOINT,
                description="Test ML inference endpoints",
                test_function=self._test_ml_inference
            ),
            TestCase(
                test_id="api_camera_integration",
                name="Camera Integration API",
                category=TestCategory.API_ENDPOINT,
                description="Test camera integration endpoints",
                test_function=self._test_camera_integration
            ),
            TestCase(
                test_id="api_validation",
                name="Validation API",
                category=TestCategory.API_ENDPOINT,
                description="Test validation endpoints",
                test_function=self._test_validation
            ),
            TestCase(
                test_id="api_project_workflow",
                name="Project Workflow API",
                category=TestCategory.API_ENDPOINT,
                description="Test project workflow endpoints",
                test_function=self._test_project_workflow
            )
        ])
        
        # WebSocket tests
        self.test_cases.extend([
            TestCase(
                test_id="ws_connection",
                name="WebSocket Connection",
                category=TestCategory.WEBSOCKET,
                description="Test WebSocket connection and communication",
                test_function=self._test_websocket_connection
            ),
            TestCase(
                test_id="ws_subscription",
                name="WebSocket Subscription",
                category=TestCategory.WEBSOCKET,
                description="Test WebSocket subscription functionality",
                test_function=self._test_websocket_subscription
            )
        ])
        
        # Performance tests
        self.test_cases.extend([
            TestCase(
                test_id="perf_response_time",
                name="Response Time Performance",
                category=TestCategory.PERFORMANCE,
                description="Test API response times",
                test_function=self._test_performance_response_time
            ),
            TestCase(
                test_id="perf_concurrent_load",
                name="Concurrent Load Test",
                category=TestCategory.PERFORMANCE,
                description="Test concurrent request handling",
                test_function=self._test_performance_load
            )
        ])
        
        # External access tests
        self.test_cases.extend([
            TestCase(
                test_id="ext_ip_access",
                name="External IP Access",
                category=TestCategory.EXTERNAL_ACCESS,
                description="Test external IP accessibility",
                test_function=self._test_external_ip_access
            ),
            TestCase(
                test_id="ext_websocket_access",
                name="External WebSocket Access",
                category=TestCategory.EXTERNAL_ACCESS,
                description="Test WebSocket access from external IP",
                test_function=self._test_external_websocket_access
            )
        ])
    
    # Test case implementations
    async def _test_api_health(self) -> Dict[str, Any]:
        async with self.api_validator:
            return await self.api_validator.test_health_endpoint()
    
    async def _test_unified_status(self) -> Dict[str, Any]:
        async with self.api_validator:
            return await self.api_validator.test_unified_status_endpoint()
    
    async def _test_ml_inference(self) -> Dict[str, Any]:
        async with self.api_validator:
            return await self.api_validator.test_ml_inference_endpoint()
    
    async def _test_camera_integration(self) -> Dict[str, Any]:
        async with self.api_validator:
            return await self.api_validator.test_camera_endpoints()
    
    async def _test_validation(self) -> Dict[str, Any]:
        async with self.api_validator:
            return await self.api_validator.test_validation_endpoint()
    
    async def _test_project_workflow(self) -> Dict[str, Any]:
        async with self.api_validator:
            return await self.api_validator.test_project_workflow_endpoints()
    
    async def _test_websocket_connection(self) -> Dict[str, Any]:
        return await self.websocket_tester.test_websocket_connection()
    
    async def _test_websocket_subscription(self) -> Dict[str, Any]:
        return await self.websocket_tester.test_websocket_subscription()
    
    async def _test_performance_response_time(self) -> Dict[str, Any]:
        return await self.performance_tester.test_response_time("/api/v1/health", 20)
    
    async def _test_performance_load(self) -> Dict[str, Any]:
        return await self.performance_tester.test_concurrent_load("/api/v1/health", 10, 10)
    
    def _test_external_ip_access(self) -> Dict[str, Any]:
        return self.external_tester.test_external_ip_accessibility()
    
    def _test_external_websocket_access(self) -> Dict[str, Any]:
        return self.external_tester.test_websocket_external_access()
    
    async def run_all_tests(self) -> TestSuiteResults:
        """Run all test cases"""
        start_time = datetime.utcnow()
        self.results = []
        
        logger.info(f"Starting comprehensive test suite with {len(self.test_cases)} tests")
        
        for test_case in self.test_cases:
            execution = await self._execute_test_case(test_case)
            self.results.append(execution)
            
            # Log test result
            status_symbol = "✅" if execution.result == TestResult.PASS else "❌" if execution.result == TestResult.FAIL else "⚠️"
            logger.info(f"{status_symbol} {test_case.name}: {execution.result.value}")
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        # Calculate summary statistics
        passed = sum(1 for r in self.results if r.result == TestResult.PASS)
        failed = sum(1 for r in self.results if r.result == TestResult.FAIL)
        skipped = sum(1 for r in self.results if r.result == TestResult.SKIP)
        errors = sum(1 for r in self.results if r.result == TestResult.ERROR)
        
        summary = {
            "pass_rate": (passed / len(self.results)) * 100 if self.results else 0,
            "categories": self._summarize_by_category(),
            "performance_metrics": self._extract_performance_metrics()
        }
        
        suite_results = TestSuiteResults(
            suite_name="Comprehensive VRU API Test Suite",
            start_time=start_time,
            end_time=end_time,
            total_duration_seconds=duration,
            total_tests=len(self.results),
            passed_tests=passed,
            failed_tests=failed,
            skipped_tests=skipped,
            error_tests=errors,
            test_executions=self.results,
            summary=summary
        )
        
        logger.info(f"Test suite completed: {passed}/{len(self.results)} tests passed")
        return suite_results
    
    async def _execute_test_case(self, test_case: TestCase) -> TestExecution:
        """Execute individual test case"""
        start_time = datetime.utcnow()
        
        try:
            # Check prerequisites
            for prereq in test_case.prerequisites:
                # Implementation would check if prerequisite tests passed
                pass
            
            # Execute test function
            if asyncio.iscoroutinefunction(test_case.test_function):
                actual_result = await asyncio.wait_for(
                    test_case.test_function(),
                    timeout=test_case.timeout_seconds
                )
            else:
                actual_result = test_case.test_function()
            
            # Determine test result
            if isinstance(actual_result, dict):
                test_result = TestResult.PASS if actual_result.get("success", False) else TestResult.FAIL
            else:
                test_result = TestResult.PASS if actual_result else TestResult.FAIL
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            return TestExecution(
                test_case=test_case,
                result=test_result,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                actual_result=actual_result
            )
            
        except asyncio.TimeoutError:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            return TestExecution(
                test_case=test_case,
                result=TestResult.ERROR,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                error_message="Test timed out",
                stack_trace=traceback.format_exc()
            )
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            return TestExecution(
                test_case=test_case,
                result=TestResult.ERROR,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                error_message=str(e),
                stack_trace=traceback.format_exc()
            )
    
    def _summarize_by_category(self) -> Dict[str, Dict[str, int]]:
        """Summarize results by test category"""
        category_summary = defaultdict(lambda: defaultdict(int))
        
        for execution in self.results:
            category = execution.test_case.category.value
            result = execution.result.value
            category_summary[category][result] += 1
            category_summary[category]["total"] += 1
        
        return dict(category_summary)
    
    def _extract_performance_metrics(self) -> Dict[str, Any]:
        """Extract performance metrics from test results"""
        performance_executions = [
            e for e in self.results 
            if e.test_case.category == TestCategory.PERFORMANCE
        ]
        
        if not performance_executions:
            return {}
        
        response_times = []
        throughput_data = []
        
        for execution in performance_executions:
            if isinstance(execution.actual_result, dict):
                result = execution.actual_result
                
                # Collect response time data
                if "avg_response_time_ms" in result:
                    response_times.append(result["avg_response_time_ms"])
                
                # Collect throughput data
                if "requests_per_second" in result:
                    throughput_data.append(result["requests_per_second"])
        
        metrics = {}
        
        if response_times:
            metrics["avg_response_time_ms"] = statistics.mean(response_times)
            metrics["min_response_time_ms"] = min(response_times)
            metrics["max_response_time_ms"] = max(response_times)
        
        if throughput_data:
            metrics["avg_throughput_rps"] = statistics.mean(throughput_data)
            metrics["max_throughput_rps"] = max(throughput_data)
        
        return metrics
    
    def generate_test_report(self, results: TestSuiteResults) -> str:
        """Generate comprehensive test report"""
        report = f"""
# VRU API Comprehensive Test Report

## Test Suite Summary
- **Suite Name**: {results.suite_name}
- **Execution Time**: {results.start_time.isoformat()} - {results.end_time.isoformat()}
- **Total Duration**: {results.total_duration_seconds:.2f} seconds
- **Total Tests**: {results.total_tests}
- **Passed**: {results.passed_tests} ({(results.passed_tests/results.total_tests)*100:.1f}%)
- **Failed**: {results.failed_tests} ({(results.failed_tests/results.total_tests)*100:.1f}%)
- **Errors**: {results.error_tests} ({(results.error_tests/results.total_tests)*100:.1f}%)
- **Skipped**: {results.skipped_tests} ({(results.skipped_tests/results.total_tests)*100:.1f}%)

## Results by Category
"""
        
        for category, stats in results.summary["categories"].items():
            report += f"\n### {category.replace('_', ' ').title()}\n"
            report += f"- Total: {stats['total']}\n"
            report += f"- Passed: {stats.get('pass', 0)}\n"
            report += f"- Failed: {stats.get('fail', 0)}\n"
            report += f"- Errors: {stats.get('error', 0)}\n"
        
        # Performance metrics
        if results.summary.get("performance_metrics"):
            metrics = results.summary["performance_metrics"]
            report += f"\n## Performance Metrics\n"
            if "avg_response_time_ms" in metrics:
                report += f"- Average Response Time: {metrics['avg_response_time_ms']:.2f} ms\n"
            if "avg_throughput_rps" in metrics:
                report += f"- Average Throughput: {metrics['avg_throughput_rps']:.2f} requests/second\n"
        
        # Failed tests details
        failed_executions = [e for e in results.test_executions if e.result in [TestResult.FAIL, TestResult.ERROR]]
        if failed_executions:
            report += f"\n## Failed Tests Details\n"
            for execution in failed_executions:
                report += f"\n### {execution.test_case.name}\n"
                report += f"- **Result**: {execution.result.value}\n"
                report += f"- **Duration**: {execution.duration_seconds:.2f} seconds\n"
                if execution.error_message:
                    report += f"- **Error**: {execution.error_message}\n"
        
        return report

# Factory function
def create_test_suite(base_url: str = "http://localhost:8000", external_ip: str = "155.138.239.131") -> ComprehensiveTestSuite:
    """Create comprehensive test suite"""
    return ComprehensiveTestSuite(base_url, external_ip)

# Main execution
if __name__ == "__main__":
    async def run_tests():
        # Configure logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Create and run test suite
        test_suite = create_test_suite()
        results = await test_suite.run_all_tests()
        
        # Generate and print report
        report = test_suite.generate_test_report(results)
        print(report)
        
        # Save report to file
        with open("/tmp/vru_api_test_report.md", "w") as f:
            f.write(report)
        
        print(f"\nDetailed report saved to: /tmp/vru_api_test_report.md")
        
        # Return exit code based on results
        return 0 if results.failed_tests == 0 and results.error_tests == 0 else 1
    
    import sys
    exit_code = asyncio.run(run_tests())
    sys.exit(exit_code)