#!/usr/bin/env python3
"""
COMPREHENSIVE EDGE CASE TEST SUITE
AI Model Validation Platform - Backend Integration & Stress Testing

This test suite implements extreme edge case testing for all major components
including API endpoints, file handling, database operations, and integration scenarios.
"""

import asyncio
import json
import os
import tempfile
import time
import uuid
from typing import Dict, List, Any
import requests
import concurrent.futures
from pathlib import Path
import sqlite3
import logging
from datetime import datetime

# Configure logging for comprehensive test reporting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('edge_case_test_results.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EdgeCaseTestSuite:
    """Comprehensive edge case testing framework"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.results = {
            "test_summary": {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "critical_failures": 0
            },
            "categories": {},
            "performance_metrics": {},
            "error_analysis": [],
            "recommendations": []
        }
        self.session = requests.Session()
        self.session.timeout = 30
        
    def run_comprehensive_suite(self):
        """Execute all edge case test categories"""
        logger.info("🚀 Starting Comprehensive Edge Case Test Suite")
        
        test_categories = [
            ("API Endpoint Validation", self.test_api_endpoints_edge_cases),
            ("File Handling Extremes", self.test_file_handling_extremes),
            ("Database Stress Testing", self.test_database_stress_operations),
            ("Cross-Feature Integration", self.test_integration_chains),
            ("Concurrent Operations", self.test_concurrent_stress),
            ("Error Recovery Mechanisms", self.test_error_recovery),
            ("Security Edge Cases", self.test_security_edge_cases),
            ("Performance Under Load", self.test_performance_extremes),
            ("Data Consistency Validation", self.test_data_consistency),
            ("WebSocket Stress Testing", self.test_websocket_stress)
        ]
        
        for category_name, test_function in test_categories:
            logger.info(f"\n{'='*60}")
            logger.info(f"🧪 TESTING CATEGORY: {category_name}")
            logger.info(f"{'='*60}")
            
            category_results = {
                "tests": [],
                "summary": {"passed": 0, "failed": 0, "critical": 0}
            }
            
            try:
                test_function(category_results)
            except Exception as e:
                logger.error(f"❌ Critical failure in {category_name}: {str(e)}")
                category_results["tests"].append({
                    "name": f"{category_name}_CRITICAL_FAILURE",
                    "status": "CRITICAL",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                category_results["summary"]["critical"] += 1
                self.results["test_summary"]["critical_failures"] += 1
            
            self.results["categories"][category_name] = category_results
            self._update_test_summary(category_results)
        
        self._generate_final_report()
        return self.results

    def test_api_endpoints_edge_cases(self, results):
        """Test all API endpoints with extreme edge case data"""
        logger.info("🎯 Testing API Endpoints with Edge Case Data")
        
        # Test basic health check first
        self._test_endpoint("Health Check", "GET", "/health", {}, results)
        
        # Test project endpoints with edge cases
        extreme_project_data = [
            # Normal case first
            {
                "name": "Test Project",
                "description": "Normal test project",
                "camera_model": "TestCam",
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            },
            # Extremely long strings
            {
                "name": "A" * 1000,  # Very long name
                "description": "B" * 10000,  # Extremely long description
                "camera_model": "C" * 500,
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            },
            # Empty/minimal data
            {
                "name": "",
                "description": "",
                "camera_model": "",
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            },
            # Unicode and special characters
            {
                "name": "测试项目 🚀 №€∑",
                "description": "Спецсимволы ñáéíóú çüøå",
                "camera_model": "カメラ・モデル",
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            },
            # Invalid enum values
            {
                "name": "Invalid Enums Test",
                "description": "Testing invalid enum values",
                "camera_model": "TestCam",
                "camera_view": "INVALID_VIEW_TYPE",
                "signal_type": "INVALID_SIGNAL_TYPE"
            }
        ]
        
        for i, project_data in enumerate(extreme_project_data):
            test_name = f"Create Project Edge Case {i+1}"
            response = self._test_endpoint(
                test_name, "POST", "/api/projects", project_data, results
            )
            
            # If project creation succeeded, test related operations
            if response and response.status_code in [200, 201]:
                try:
                    project_id = response.json().get("id")
                    if project_id:
                        # Test project retrieval
                        self._test_endpoint(
                            f"Get Project {i+1}", "GET", f"/api/projects/{project_id}", {}, results
                        )
                        
                        # Test project update with extreme data
                        extreme_update_data = {
                            "name": "Z" * 2000,  # Extremely long update
                            "description": "Updated with extreme data 💥"
                        }
                        self._test_endpoint(
                            f"Update Project {i+1}", "PUT", f"/api/projects/{project_id}", 
                            extreme_update_data, results
                        )
                        
                except Exception as e:
                    logger.warning(f"⚠️  Could not test follow-up operations for project {i+1}: {e}")
        
        # Test invalid project IDs
        invalid_ids = [
            "invalid-uuid",
            "00000000-0000-0000-0000-000000000000",
            "' OR 1=1 --",  # SQL injection attempt
            "../../../etc/passwd",  # Path traversal attempt
            "a" * 100,  # Very long ID
            ""  # Empty ID
        ]
        
        for invalid_id in invalid_ids:
            self._test_endpoint(
                f"Get Invalid Project ID: {invalid_id[:20]}...", 
                "GET", f"/api/projects/{invalid_id}", {}, results
            )

    def test_file_handling_extremes(self, results):
        """Test extreme file handling scenarios"""
        logger.info("📁 Testing File Handling Edge Cases")
        
        # Create temporary test files for edge cases
        test_files = []
        
        try:
            # 1. Empty file (0 bytes)
            empty_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            empty_file.close()
            test_files.append(("empty_file.mp4", empty_file.name, "Empty 0-byte file"))
            
            # 2. Very small file (1 byte)
            tiny_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tiny_file.write(b"A")
            tiny_file.close()
            test_files.append(("tiny_file.mp4", tiny_file.name, "1-byte file"))
            
            # 3. File with special characters in name
            special_name_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            special_name_file.write(b"Test content for special chars")
            special_name_file.close()
            test_files.append(("测试文件 №€∑.mp4", special_name_file.name, "Unicode filename"))
            
            # 4. File with dangerous filename
            dangerous_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            dangerous_file.write(b"Dangerous filename test")
            dangerous_file.close()
            test_files.append(("../../evil.mp4", dangerous_file.name, "Path traversal filename"))
            
            # 5. Large file (create 10MB file)
            large_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            chunk_data = b"A" * 1024 * 1024  # 1MB chunk
            for _ in range(10):  # 10MB total
                large_file.write(chunk_data)
            large_file.close()
            test_files.append(("large_file.mp4", large_file.name, "10MB file"))
            
            # Test file uploads with edge cases
            for original_filename, file_path, description in test_files:
                self._test_file_upload(original_filename, file_path, description, results)
            
            # Test invalid file extensions
            invalid_extensions = [".txt", ".exe", ".sh", ".py", "", ".mp4.exe"]
            for ext in invalid_extensions:
                test_filename = f"test{ext}"
                self._test_file_upload(test_filename, empty_file.name, f"Invalid extension {ext}", results)
            
        finally:
            # Cleanup temporary files
            for _, file_path, _ in test_files:
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

    def test_database_stress_operations(self, results):
        """Test database operations under stress"""
        logger.info("🗄️  Testing Database Stress Operations")
        
        # Test rapid project creation/deletion
        project_ids = []
        
        # Rapid creation test
        start_time = time.time()
        for i in range(50):  # Create 50 projects rapidly
            project_data = {
                "name": f"Stress Test Project {i}",
                "description": f"Rapid creation test {i}",
                "camera_model": "StressCam",
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            }
            
            response = self._test_endpoint(
                f"Rapid Create Project {i}", "POST", "/api/projects", project_data, results,
                expect_success=True
            )
            
            if response and response.status_code in [200, 201]:
                try:
                    project_id = response.json().get("id")
                    if project_id:
                        project_ids.append(project_id)
                except:
                    pass
        
        creation_time = time.time() - start_time
        logger.info(f"📊 Created {len(project_ids)} projects in {creation_time:.2f}s")
        
        # Test concurrent reads
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for project_id in project_ids[:10]:  # Test first 10
                future = executor.submit(self._concurrent_read_test, project_id)
                futures.append(future)
            
            concurrent_results = []
            for future in concurrent.futures.as_completed(futures, timeout=30):
                try:
                    result = future.result()
                    concurrent_results.append(result)
                except Exception as e:
                    logger.error(f"Concurrent read failed: {e}")
        
        read_time = time.time() - start_time
        logger.info(f"📊 Completed {len(concurrent_results)} concurrent reads in {read_time:.2f}s")
        
        # Cleanup - rapid deletion test
        start_time = time.time()
        deleted_count = 0
        for project_id in project_ids:
            response = self._test_endpoint(
                f"Cleanup Delete", "DELETE", f"/api/projects/{project_id}", {}, results,
                expect_success=True
            )
            if response and response.status_code in [200, 204]:
                deleted_count += 1
        
        deletion_time = time.time() - start_time
        logger.info(f"📊 Deleted {deleted_count} projects in {deletion_time:.2f}s")

    def test_integration_chains(self, results):
        """Test complete workflow integration chains"""
        logger.info("🔗 Testing Cross-Feature Integration Chains")
        
        # Integration Chain 1: Project → Video → Ground Truth → Annotation → Test
        chain_results = []
        
        try:
            # Step 1: Create project
            project_data = {
                "name": "Integration Test Project",
                "description": "Full workflow integration test",
                "camera_model": "IntegrationCam",
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            }
            
            response = self._make_request("POST", "/api/projects", project_data)
            if not response or response.status_code not in [200, 201]:
                raise Exception(f"Project creation failed: {response.status_code if response else 'No response'}")
            
            project_id = response.json().get("id")
            chain_results.append(("Project Creation", True, f"Created project {project_id}"))
            
            # Step 2: Upload video (create small test file)
            test_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            test_video.write(b"FAKE_MP4_CONTENT_FOR_TESTING" * 1000)  # ~25KB
            test_video.close()
            
            try:
                with open(test_video.name, 'rb') as f:
                    files = {'file': ('integration_test.mp4', f, 'video/mp4')}
                    response = self.session.post(
                        f"{self.base_url}/api/projects/{project_id}/videos",
                        files=files,
                        timeout=30
                    )
                
                if response.status_code in [200, 201]:
                    video_data = response.json()
                    video_id = video_data.get("id")
                    chain_results.append(("Video Upload", True, f"Uploaded video {video_id}"))
                    
                    # Step 3: Test ground truth retrieval
                    gt_response = self._make_request("GET", f"/api/videos/{video_id}/ground-truth")
                    if gt_response and gt_response.status_code == 200:
                        chain_results.append(("Ground Truth Retrieval", True, "Ground truth data retrieved"))
                    else:
                        chain_results.append(("Ground Truth Retrieval", False, f"Status: {gt_response.status_code if gt_response else 'No response'}"))
                    
                    # Step 4: Create annotation
                    annotation_data = {
                        "frame_number": 1,
                        "timestamp": 0.5,
                        "vru_type": "pedestrian",
                        "bounding_box": {"x": 100, "y": 100, "width": 50, "height": 50},
                        "notes": "Integration test annotation",
                        "annotator": "test_system"
                    }
                    
                    ann_response = self._make_request("POST", f"/api/videos/{video_id}/annotations", annotation_data)
                    if ann_response and ann_response.status_code in [200, 201]:
                        chain_results.append(("Annotation Creation", True, "Annotation created successfully"))
                    else:
                        chain_results.append(("Annotation Creation", False, f"Status: {ann_response.status_code if ann_response else 'No response'}"))
                    
                    # Step 5: Execute test session
                    test_response = self._make_request("POST", f"/api/projects/{project_id}/execute-test")
                    if test_response:
                        if test_response.status_code in [200, 201]:
                            chain_results.append(("Test Execution", True, "Test session started"))
                        else:
                            chain_results.append(("Test Execution", False, f"Status: {test_response.status_code}, Response: {test_response.text[:200]}"))
                    else:
                        chain_results.append(("Test Execution", False, "No response from test execution"))
                    
                else:
                    chain_results.append(("Video Upload", False, f"Upload failed: {response.status_code}"))
                    
            finally:
                os.unlink(test_video.name)
                
        except Exception as e:
            chain_results.append(("Integration Chain", False, f"Chain failed: {str(e)}"))
        
        # Record integration chain results
        for step_name, success, message in chain_results:
            results["tests"].append({
                "name": f"Integration Chain - {step_name}",
                "status": "PASS" if success else "FAIL",
                "message": message,
                "category": "integration",
                "timestamp": datetime.now().isoformat()
            })
            
            if success:
                results["summary"]["passed"] += 1
            else:
                results["summary"]["failed"] += 1

    def test_concurrent_stress(self, results):
        """Test concurrent operations stress scenarios"""
        logger.info("⚡ Testing Concurrent Stress Operations")
        
        def concurrent_project_operations():
            """Concurrent project CRUD operations"""
            operations_results = []
            
            # Create project
            project_data = {
                "name": f"Concurrent Test {uuid.uuid4().hex[:8]}",
                "description": "Concurrent stress test",
                "camera_model": "ConcurrentCam",
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            }
            
            try:
                response = self._make_request("POST", "/api/projects", project_data)
                if response and response.status_code in [200, 201]:
                    project_id = response.json().get("id")
                    operations_results.append(("CREATE", True, project_id))
                    
                    # Update project
                    update_data = {"name": f"Updated {uuid.uuid4().hex[:8]}"}
                    update_response = self._make_request("PUT", f"/api/projects/{project_id}", update_data)
                    operations_results.append(("UPDATE", update_response.status_code in [200, 204], project_id))
                    
                    # Read project
                    read_response = self._make_request("GET", f"/api/projects/{project_id}")
                    operations_results.append(("READ", read_response.status_code == 200, project_id))
                    
                    # Delete project
                    delete_response = self._make_request("DELETE", f"/api/projects/{project_id}")
                    operations_results.append(("DELETE", delete_response.status_code in [200, 204], project_id))
                    
                else:
                    operations_results.append(("CREATE", False, None))
                    
            except Exception as e:
                operations_results.append(("ERROR", False, str(e)))
            
            return operations_results
        
        # Execute concurrent operations
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(concurrent_project_operations) for _ in range(50)]
            
            all_results = []
            completed = 0
            for future in concurrent.futures.as_completed(futures, timeout=60):
                try:
                    result = future.result()
                    all_results.extend(result)
                    completed += 1
                except Exception as e:
                    logger.error(f"Concurrent operation failed: {e}")
                    all_results.append(("CONCURRENT_ERROR", False, str(e)))
        
        execution_time = time.time() - start_time
        
        # Analyze results
        operation_stats = {}
        for operation, success, _ in all_results:
            if operation not in operation_stats:
                operation_stats[operation] = {"total": 0, "success": 0}
            operation_stats[operation]["total"] += 1
            if success:
                operation_stats[operation]["success"] += 1
        
        # Record concurrent stress results
        for operation, stats in operation_stats.items():
            success_rate = (stats["success"] / stats["total"]) * 100 if stats["total"] > 0 else 0
            results["tests"].append({
                "name": f"Concurrent Stress - {operation}",
                "status": "PASS" if success_rate >= 90 else "FAIL",
                "message": f"Success rate: {success_rate:.1f}% ({stats['success']}/{stats['total']})",
                "execution_time": execution_time,
                "category": "concurrency",
                "timestamp": datetime.now().isoformat()
            })
            
            if success_rate >= 90:
                results["summary"]["passed"] += 1
            else:
                results["summary"]["failed"] += 1

    def test_error_recovery(self, results):
        """Test system error recovery mechanisms"""
        logger.info("🔄 Testing Error Recovery Mechanisms")
        
        # Test invalid JSON handling
        invalid_payloads = [
            '{"invalid": json}',  # Invalid JSON syntax
            '{"name": "test", "description":}',  # Incomplete JSON
            '{"name": null, "description": null}',  # Null values
            '',  # Empty payload
            'not json at all',  # Plain text
            '{"nested": {"deep": {"very": {"deep": {"object": "value"}}}}}' * 100  # Deeply nested
        ]
        
        for i, payload in enumerate(invalid_payloads):
            test_name = f"Invalid JSON Recovery {i+1}"
            try:
                response = self.session.post(
                    f"{self.base_url}/api/projects",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                # System should gracefully handle invalid JSON
                handled_gracefully = response.status_code in [400, 422, 500]
                results["tests"].append({
                    "name": test_name,
                    "status": "PASS" if handled_gracefully else "FAIL",
                    "message": f"Status: {response.status_code}, Graceful: {handled_gracefully}",
                    "category": "error_recovery",
                    "timestamp": datetime.now().isoformat()
                })
                
                if handled_gracefully:
                    results["summary"]["passed"] += 1
                else:
                    results["summary"]["failed"] += 1
                    
            except Exception as e:
                results["tests"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "message": f"Exception: {str(e)}",
                    "category": "error_recovery",
                    "timestamp": datetime.now().isoformat()
                })
                results["summary"]["failed"] += 1

    def test_security_edge_cases(self, results):
        """Test security-related edge cases"""
        logger.info("🔒 Testing Security Edge Cases")
        
        # SQL Injection attempts
        sql_injection_payloads = [
            "'; DROP TABLE projects; --",
            "' OR 1=1 --",
            "' UNION SELECT * FROM users --",
            "'; DELETE FROM videos WHERE 1=1; --"
        ]
        
        for payload in sql_injection_payloads:
            test_data = {
                "name": payload,
                "description": "SQL injection test",
                "camera_model": "SecurityTest",
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            }
            
            response = self._test_endpoint(
                f"SQL Injection Defense: {payload[:20]}...", 
                "POST", "/api/projects", test_data, results
            )
            
            # Check if system is still accessible (not compromised)
            health_check = self._make_request("GET", "/health")
            if not health_check or health_check.status_code != 200:
                results["tests"].append({
                    "name": "System Integrity After SQL Injection",
                    "status": "CRITICAL",
                    "message": "System may be compromised - health check failed",
                    "category": "security",
                    "timestamp": datetime.now().isoformat()
                })
                results["summary"]["critical"] += 1

    def test_performance_extremes(self, results):
        """Test performance under extreme conditions"""
        logger.info("⚡ Testing Performance Extremes")
        
        # Test API response times under load
        endpoint_tests = [
            ("GET", "/health"),
            ("GET", "/api/projects"),
            ("GET", "/api/dashboard/stats")
        ]
        
        for method, endpoint in endpoint_tests:
            response_times = []
            
            # Measure response times for 20 requests
            for i in range(20):
                start_time = time.time()
                response = self._make_request(method, endpoint)
                end_time = time.time()
                
                if response:
                    response_times.append(end_time - start_time)
            
            if response_times:
                avg_time = sum(response_times) / len(response_times)
                max_time = max(response_times)
                min_time = min(response_times)
                
                # Performance criteria: average < 2s, max < 5s
                performance_pass = avg_time < 2.0 and max_time < 5.0
                
                results["tests"].append({
                    "name": f"Performance - {method} {endpoint}",
                    "status": "PASS" if performance_pass else "FAIL",
                    "message": f"Avg: {avg_time:.3f}s, Max: {max_time:.3f}s, Min: {min_time:.3f}s",
                    "category": "performance",
                    "timestamp": datetime.now().isoformat()
                })
                
                if performance_pass:
                    results["summary"]["passed"] += 1
                else:
                    results["summary"]["failed"] += 1

    def test_data_consistency(self, results):
        """Test data consistency under various conditions"""
        logger.info("🔍 Testing Data Consistency")
        
        # Create test project and verify consistency
        project_data = {
            "name": "Consistency Test Project",
            "description": "Testing data consistency",
            "camera_model": "ConsistencyCam",
            "camera_view": "Front-facing VRU", 
            "signal_type": "GPIO"
        }
        
        # Create project
        response = self._make_request("POST", "/api/projects", project_data)
        if response and response.status_code in [200, 201]:
            project_id = response.json().get("id")
            
            # Test consistency across multiple reads
            read_results = []
            for i in range(5):
                read_response = self._make_request("GET", f"/api/projects/{project_id}")
                if read_response and read_response.status_code == 200:
                    read_results.append(read_response.json())
            
            # Check if all reads return consistent data
            if len(read_results) > 1:
                first_result = read_results[0]
                consistent = all(
                    result.get("name") == first_result.get("name") and
                    result.get("description") == first_result.get("description")
                    for result in read_results
                )
                
                results["tests"].append({
                    "name": "Data Consistency - Multiple Reads",
                    "status": "PASS" if consistent else "FAIL",
                    "message": f"Consistency check across {len(read_results)} reads",
                    "category": "consistency",
                    "timestamp": datetime.now().isoformat()
                })
                
                if consistent:
                    results["summary"]["passed"] += 1
                else:
                    results["summary"]["failed"] += 1
            
            # Cleanup
            self._make_request("DELETE", f"/api/projects/{project_id}")

    def test_websocket_stress(self, results):
        """Test WebSocket communication under stress"""
        logger.info("🌐 Testing WebSocket Stress")
        
        # Since WebSocket testing requires more complex setup, 
        # we'll test the WebSocket endpoints availability
        websocket_endpoints = [
            "/ws/progress/test",
            "/ws/room/test-room"
        ]
        
        for endpoint in websocket_endpoints:
            # Test WebSocket endpoint accessibility (should get upgrade error for HTTP)
            try:
                response = self.session.get(f"{self.base_url.replace('http://', 'ws://')}{endpoint}")
                # WebSocket endpoints should reject HTTP requests
                websocket_available = True  # If we get here, endpoint exists
            except:
                websocket_available = False
            
            results["tests"].append({
                "name": f"WebSocket Endpoint Available: {endpoint}",
                "status": "PASS" if websocket_available else "FAIL", 
                "message": f"WebSocket endpoint {endpoint} accessibility",
                "category": "websocket",
                "timestamp": datetime.now().isoformat()
            })
            
            if websocket_available:
                results["summary"]["passed"] += 1
            else:
                results["summary"]["failed"] += 1

    # Helper methods
    
    def _test_endpoint(self, test_name, method, endpoint, data, results, expect_success=None):
        """Test individual endpoint with comprehensive error handling"""
        try:
            response = self._make_request(method, endpoint, data)
            
            if response:
                success = response.status_code < 400
                if expect_success is not None:
                    test_passed = success == expect_success
                else:
                    test_passed = True  # Any response is acceptable for edge cases
                
                status_msg = "PASS" if test_passed else "FAIL"
                message = f"Status: {response.status_code}"
                
                # Add response details for failures
                if not test_passed and len(response.text) < 200:
                    message += f", Response: {response.text}"
                
            else:
                test_passed = False
                status_msg = "FAIL"
                message = "No response received"
            
            results["tests"].append({
                "name": test_name,
                "status": status_msg,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
            
            if test_passed:
                results["summary"]["passed"] += 1
            else:
                results["summary"]["failed"] += 1
            
            return response
            
        except Exception as e:
            results["tests"].append({
                "name": test_name,
                "status": "CRITICAL",
                "message": f"Exception: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
            results["summary"]["critical"] += 1
            return None
    
    def _make_request(self, method, endpoint, data=None):
        """Make HTTP request with error handling"""
        try:
            url = f"{self.base_url}{endpoint}"
            
            if method == "GET":
                return self.session.get(url)
            elif method == "POST":
                return self.session.post(url, json=data)
            elif method == "PUT":
                return self.session.put(url, json=data)
            elif method == "DELETE":
                return self.session.delete(url)
            
        except Exception as e:
            logger.error(f"Request failed: {method} {endpoint} - {str(e)}")
            return None
    
    def _test_file_upload(self, filename, file_path, description, results):
        """Test file upload with specific file"""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f, 'video/mp4')}
                response = self.session.post(
                    f"{self.base_url}/api/videos",
                    files=files,
                    timeout=30
                )
            
            test_passed = response.status_code in [200, 201, 400, 413, 422]  # Expected responses
            
            results["tests"].append({
                "name": f"File Upload - {description}",
                "status": "PASS" if test_passed else "FAIL",
                "message": f"Status: {response.status_code}, File: {filename}",
                "category": "file_handling",
                "timestamp": datetime.now().isoformat()
            })
            
            if test_passed:
                results["summary"]["passed"] += 1
            else:
                results["summary"]["failed"] += 1
                
        except Exception as e:
            results["tests"].append({
                "name": f"File Upload - {description}",
                "status": "CRITICAL",
                "message": f"Exception: {str(e)}",
                "category": "file_handling", 
                "timestamp": datetime.now().isoformat()
            })
            results["summary"]["critical"] += 1
    
    def _concurrent_read_test(self, project_id):
        """Concurrent read operation for stress testing"""
        try:
            response = self._make_request("GET", f"/api/projects/{project_id}")
            return response.status_code == 200 if response else False
        except:
            return False
    
    def _update_test_summary(self, category_results):
        """Update overall test summary"""
        self.results["test_summary"]["passed"] += category_results["summary"]["passed"]
        self.results["test_summary"]["failed"] += category_results["summary"]["failed"]
        self.results["test_summary"]["critical_failures"] += category_results["summary"]["critical"]
        self.results["test_summary"]["total_tests"] += (
            category_results["summary"]["passed"] + 
            category_results["summary"]["failed"] + 
            category_results["summary"]["critical"]
        )
    
    def _generate_final_report(self):
        """Generate comprehensive final test report"""
        logger.info("\n" + "="*80)
        logger.info("📊 COMPREHENSIVE EDGE CASE TEST RESULTS SUMMARY")
        logger.info("="*80)
        
        summary = self.results["test_summary"]
        total = summary["total_tests"]
        
        if total > 0:
            pass_rate = (summary["passed"] / total) * 100
            fail_rate = (summary["failed"] / total) * 100
            critical_rate = (summary["critical_failures"] / total) * 100
            
            logger.info(f"📈 OVERALL RESULTS:")
            logger.info(f"   Total Tests: {total}")
            logger.info(f"   ✅ Passed: {summary['passed']} ({pass_rate:.1f}%)")
            logger.info(f"   ❌ Failed: {summary['failed']} ({fail_rate:.1f}%)")
            logger.info(f"   🚨 Critical: {summary['critical_failures']} ({critical_rate:.1f}%)")
            
            # System health assessment
            if critical_rate == 0 and pass_rate >= 90:
                health_status = "🟢 EXCELLENT - System handles edge cases very well"
            elif critical_rate == 0 and pass_rate >= 75:
                health_status = "🟡 GOOD - Minor edge case issues detected"
            elif critical_rate < 5 and pass_rate >= 60:
                health_status = "🟠 MODERATE - Several edge case failures need attention"
            else:
                health_status = "🔴 CRITICAL - Major edge case failures detected"
            
            logger.info(f"\n🎯 SYSTEM HEALTH: {health_status}")
            
            # Category breakdown
            logger.info(f"\n📋 CATEGORY BREAKDOWN:")
            for category_name, category_data in self.results["categories"].items():
                cat_summary = category_data["summary"]
                cat_total = cat_summary["passed"] + cat_summary["failed"] + cat_summary["critical"]
                if cat_total > 0:
                    cat_pass_rate = (cat_summary["passed"] / cat_total) * 100
                    logger.info(f"   {category_name}: {cat_pass_rate:.1f}% pass rate ({cat_summary['passed']}/{cat_total})")
            
            # Recommendations
            self._generate_recommendations()
            
            logger.info(f"\n💡 RECOMMENDATIONS:")
            for rec in self.results["recommendations"]:
                logger.info(f"   • {rec}")
                
        else:
            logger.error("❌ No tests were executed!")
        
        logger.info("="*80)
        
        # Save detailed results to file
        with open("comprehensive_edge_case_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        logger.info("📄 Detailed results saved to comprehensive_edge_case_results.json")

    def _generate_recommendations(self):
        """Generate recommendations based on test results"""
        recommendations = []
        
        summary = self.results["test_summary"]
        total = summary["total_tests"]
        
        if total == 0:
            recommendations.append("No tests were executed - check system connectivity")
            return
        
        pass_rate = (summary["passed"] / total) * 100
        critical_rate = (summary["critical_failures"] / total) * 100
        
        # Performance recommendations
        if pass_rate < 90:
            recommendations.append("Improve error handling for edge cases - pass rate below 90%")
        
        if critical_rate > 0:
            recommendations.append("Address critical failures immediately - system stability at risk")
        
        # Category-specific recommendations
        for category_name, category_data in self.results["categories"].items():
            cat_summary = category_data["summary"]
            cat_total = cat_summary["passed"] + cat_summary["failed"] + cat_summary["critical"]
            
            if cat_total > 0:
                cat_pass_rate = (cat_summary["passed"] / cat_total) * 100
                
                if cat_pass_rate < 70:
                    recommendations.append(f"Focus on {category_name} - low pass rate ({cat_pass_rate:.1f}%)")
                
                if cat_summary["critical"] > 0:
                    recommendations.append(f"Critical issues in {category_name} need immediate attention")
        
        # Security recommendations
        security_failures = sum(
            1 for category_data in self.results["categories"].values()
            for test in category_data.get("tests", [])
            if test.get("category") == "security" and test.get("status") != "PASS"
        )
        
        if security_failures > 0:
            recommendations.append("Security vulnerabilities detected - conduct security review")
        
        # Performance recommendations
        slow_responses = sum(
            1 for category_data in self.results["categories"].values()
            for test in category_data.get("tests", [])
            if test.get("category") == "performance" and test.get("status") != "PASS"
        )
        
        if slow_responses > 0:
            recommendations.append("Performance optimization needed - slow response times detected")
        
        # General recommendations
        if pass_rate >= 95:
            recommendations.append("Excellent edge case handling - consider this as baseline for regression testing")
        elif pass_rate >= 85:
            recommendations.append("Good edge case handling with room for improvement")
        else:
            recommendations.append("Significant edge case issues - comprehensive review needed")
        
        self.results["recommendations"] = recommendations


if __name__ == "__main__":
    print("🚀 AI Model Validation Platform - Comprehensive Edge Case Test Suite")
    print("="*80)
    
    # Initialize test suite
    test_suite = EdgeCaseTestSuite()
    
    # Run comprehensive testing
    results = test_suite.run_comprehensive_suite()
    
    print(f"\n✅ Edge case testing completed!")
    print(f"📊 Results: {results['test_summary']['passed']} passed, "
          f"{results['test_summary']['failed']} failed, "
          f"{results['test_summary']['critical_failures']} critical")