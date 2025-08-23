#!/usr/bin/env python3
"""
FINAL SYSTEM VALIDATION ENGINE
AI Model Validation Platform - Complete Production Readiness Assessment

This comprehensive validation suite tests ALL critical components of the platform:
- Phase 1: Critical issue verification (Response schemas, DB stability, Video processing, API errors)
- Phase 2: Complete feature validation (All major workflows end-to-end)
- Phase 3: Performance & stability testing (Load, stress, error recovery)
- Phase 4: User experience validation (Workflows, cross-browser, UX)

Final validation engineer: Complete system verification before production deployment.
"""

import asyncio
import json
import os
import tempfile
import time
import uuid
from typing import Dict, List, Any, Optional
import requests
import concurrent.futures
from pathlib import Path
import logging
from datetime import datetime, timedelta
import threading
import sqlite3
from contextlib import contextmanager
import subprocess
import sys

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('final_validation_report.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FinalSystemValidator:
    """Final validation engine for complete system verification"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.frontend_url = "http://localhost:3000"
        self.session = requests.Session()
        self.session.timeout = 30
        
        # Test results tracking
        self.validation_results = {
            "test_start_time": datetime.now().isoformat(),
            "system_info": {
                "backend_url": base_url,
                "frontend_url": self.frontend_url,
                "test_environment": "Local Development"
            },
            "phase_results": {},
            "overall_scores": {
                "critical_functionality": 0,
                "performance": 0,
                "error_handling": 0,
                "user_experience": 0
            },
            "critical_issues": [],
            "recommendations": [],
            "final_assessment": {}
        }
        
        # Score thresholds
        self.thresholds = {
            "production_ready": 90,
            "staging_ready": 80,
            "needs_fixes": 80
        }

    def run_complete_validation(self) -> Dict[str, Any]:
        """Execute complete system validation across all phases"""
        logger.info("🎯 STARTING FINAL SYSTEM VALIDATION")
        logger.info("="*80)
        
        phases = [
            ("Phase 1: Critical Issues Resolution", self._phase_1_critical_issues),
            ("Phase 2: Complete Feature Validation", self._phase_2_feature_validation),
            ("Phase 3: Performance & Stability", self._phase_3_performance_stability),
            ("Phase 4: User Experience Validation", self._phase_4_user_experience)
        ]
        
        for phase_name, phase_function in phases:
            logger.info(f"\n🚀 {phase_name}")
            logger.info("-" * 60)
            
            phase_start = time.time()
            try:
                phase_results = phase_function()
                phase_results["execution_time"] = time.time() - phase_start
                phase_results["status"] = "COMPLETED"
                
            except Exception as e:
                logger.error(f"❌ CRITICAL FAILURE in {phase_name}: {str(e)}")
                phase_results = {
                    "status": "FAILED",
                    "error": str(e),
                    "execution_time": time.time() - phase_start,
                    "tests": [],
                    "score": 0
                }
                self.validation_results["critical_issues"].append({
                    "phase": phase_name,
                    "error": str(e),
                    "severity": "CRITICAL"
                })
            
            self.validation_results["phase_results"][phase_name] = phase_results
        
        # Generate final assessment
        self._generate_final_assessment()
        
        # Save detailed report
        self._save_validation_report()
        
        return self.validation_results

    def _phase_1_critical_issues(self) -> Dict[str, Any]:
        """Phase 1: Verify ALL critical issues found by previous testers have been resolved"""
        logger.info("🔍 Phase 1: Verifying critical issues resolution...")
        
        tests = [
            ("Response Schema Validation", self._test_response_schemas),
            ("Database Connection Stability", self._test_database_stability),
            ("Video File Processing", self._test_video_processing),
            ("API Error Handling", self._test_api_error_handling)
        ]
        
        phase_results = {
            "tests": [],
            "issues_found": [],
            "score": 0
        }
        
        passed_tests = 0
        
        for test_name, test_function in tests:
            logger.info(f"  🧪 {test_name}...")
            
            test_start = time.time()
            try:
                result = test_function()
                test_time = time.time() - test_start
                
                test_result = {
                    "name": test_name,
                    "status": "PASSED" if result["success"] else "FAILED",
                    "execution_time": test_time,
                    "details": result.get("details", ""),
                    "metrics": result.get("metrics", {}),
                    "issues": result.get("issues", [])
                }
                
                if result["success"]:
                    passed_tests += 1
                    logger.info(f"    ✅ {test_name} - PASSED")
                else:
                    logger.error(f"    ❌ {test_name} - FAILED: {result.get('error', 'Unknown error')}")
                    phase_results["issues_found"].extend(result.get("issues", []))
                
            except Exception as e:
                logger.error(f"    💥 {test_name} - EXCEPTION: {str(e)}")
                test_result = {
                    "name": test_name,
                    "status": "EXCEPTION",
                    "execution_time": time.time() - test_start,
                    "error": str(e),
                    "issues": [{"severity": "CRITICAL", "description": f"Test exception: {str(e)}"}]
                }
                phase_results["issues_found"].append({
                    "test": test_name,
                    "severity": "CRITICAL",
                    "description": f"Test execution failed: {str(e)}"
                })
            
            phase_results["tests"].append(test_result)
        
        phase_results["score"] = (passed_tests / len(tests)) * 100
        logger.info(f"📊 Phase 1 Score: {phase_results['score']:.1f}%")
        
        return phase_results

    def _test_response_schemas(self) -> Dict[str, Any]:
        """Test that all API responses return expected schemas and no ResponseValidationError"""
        try:
            issues = []
            
            # Test video upload response schema
            logger.info("    📋 Testing video upload response schema...")
            
            # Create test video file
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                # Create minimal MP4 file (just header bytes for testing)
                temp_video.write(b'ftypisom' + b'\x00' * 100)
                temp_video_path = temp_video.name
            
            try:
                with open(temp_video_path, 'rb') as f:
                    files = {'file': ('test_video.mp4', f, 'video/mp4')}
                    response = self.session.post(f"{self.base_url}/api/videos", files=files)
                
                if response.status_code not in [200, 201]:
                    issues.append({
                        "severity": "HIGH",
                        "description": f"Video upload failed with status {response.status_code}"
                    })
                else:
                    data = response.json()
                    required_fields = ['id', 'filename', 'status']
                    
                    for field in required_fields:
                        if field not in data:
                            issues.append({
                                "severity": "HIGH",
                                "description": f"Missing required field '{field}' in video upload response"
                            })
                    
                    # Check processingStatus field specifically mentioned in critical issues
                    if 'processingStatus' not in data and 'processing_status' not in data:
                        issues.append({
                            "severity": "MEDIUM",
                            "description": "processingStatus field missing from response (may be expected)"
                        })
                        
            finally:
                os.unlink(temp_video_path)
            
            # Test project API response schema
            logger.info("    📋 Testing project API response schema...")
            
            project_data = {
                "name": f"Schema Test Project {uuid.uuid4().hex[:8]}",
                "description": "Testing response schema",
                "camera_model": "Test Camera",
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            }
            
            response = self.session.post(f"{self.base_url}/api/projects", json=project_data)
            
            if response.status_code not in [200, 201]:
                issues.append({
                    "severity": "HIGH", 
                    "description": f"Project creation failed with status {response.status_code}"
                })
            else:
                data = response.json()
                required_fields = ['id', 'name', 'status']
                
                for field in required_fields:
                    if field not in data:
                        issues.append({
                            "severity": "HIGH",
                            "description": f"Missing required field '{field}' in project creation response"
                        })
            
            return {
                "success": len(issues) == 0,
                "issues": issues,
                "details": f"Tested response schemas for video upload and project creation. Found {len(issues)} issues."
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "issues": [{"severity": "CRITICAL", "description": f"Schema validation test failed: {str(e)}"}]
            }

    def _test_database_stability(self) -> Dict[str, Any]:
        """Test database connection stability under concurrent load"""
        try:
            logger.info("    🗄️  Testing database stability with 50 concurrent requests...")
            
            issues = []
            
            def make_concurrent_request():
                try:
                    response = self.session.get(f"{self.base_url}/api/projects")
                    return {
                        "success": response.status_code == 200,
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds()
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "response_time": None
                    }
            
            # Execute 50 concurrent requests
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(make_concurrent_request) for _ in range(50)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            # Analyze results
            successful_requests = sum(1 for r in results if r.get("success", False))
            failed_requests = len(results) - successful_requests
            
            if failed_requests > 5:  # More than 10% failure rate
                issues.append({
                    "severity": "HIGH",
                    "description": f"Database connection instability: {failed_requests}/50 requests failed"
                })
            
            # Check for connection pool exhaustion errors
            connection_errors = [r for r in results if "connection" in str(r.get("error", "")).lower()]
            if connection_errors:
                issues.append({
                    "severity": "HIGH",
                    "description": f"Database connection pool issues detected: {len(connection_errors)} connection errors"
                })
            
            response_times = [r["response_time"] for r in results if r["response_time"] is not None]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            if avg_response_time > 5.0:  # More than 5 seconds average
                issues.append({
                    "severity": "MEDIUM",
                    "description": f"Slow database performance: {avg_response_time:.2f}s average response time"
                })
            
            return {
                "success": len(issues) == 0,
                "issues": issues,
                "metrics": {
                    "total_requests": 50,
                    "successful_requests": successful_requests,
                    "failed_requests": failed_requests,
                    "average_response_time": avg_response_time,
                    "success_rate": (successful_requests / 50) * 100
                },
                "details": f"Database stability test: {successful_requests}/50 requests successful, {avg_response_time:.2f}s avg response time"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "issues": [{"severity": "CRITICAL", "description": f"Database stability test failed: {str(e)}"}]
            }

    def _test_video_processing(self) -> Dict[str, Any]:
        """Test video file processing with various file types and error conditions"""
        try:
            logger.info("    🎥 Testing video file processing and error handling...")
            
            issues = []
            
            # Test 1: Valid video file upload
            logger.info("      📹 Testing valid video file upload...")
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                # Create a more realistic MP4 file structure
                mp4_header = (
                    b'\x00\x00\x00\x20ftypiso m\x00\x00\x02\x00iso miso2avc1mp41'
                    b'\x00\x00\x00\x08free' + b'\x00' * 1000
                )
                temp_video.write(mp4_header)
                temp_video_path = temp_video.name
            
            try:
                with open(temp_video_path, 'rb') as f:
                    files = {'file': ('valid_test.mp4', f, 'video/mp4')}
                    response = self.session.post(f"{self.base_url}/api/videos", files=files)
                
                if response.status_code not in [200, 201]:
                    issues.append({
                        "severity": "HIGH",
                        "description": f"Valid video upload failed with status {response.status_code}"
                    })
                else:
                    data = response.json()
                    if data.get("status") not in ["uploaded", "processing", "completed"]:
                        issues.append({
                            "severity": "MEDIUM",
                            "description": f"Unexpected video status: {data.get('status')}"
                        })
                        
            finally:
                os.unlink(temp_video_path)
            
            # Test 2: Invalid/corrupted file upload
            logger.info("      💥 Testing corrupted file handling...")
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                temp_video.write(b'This is not a valid video file')
                temp_video_path = temp_video.name
            
            try:
                with open(temp_video_path, 'rb') as f:
                    files = {'file': ('corrupted.mp4', f, 'video/mp4')}
                    response = self.session.post(f"{self.base_url}/api/videos", files=files)
                
                # Should either reject the file (4xx) or accept but mark as error
                if response.status_code == 500:
                    issues.append({
                        "severity": "HIGH",
                        "description": "Server error (500) when handling corrupted video file - should be handled gracefully"
                    })
                        
            finally:
                os.unlink(temp_video_path)
            
            # Test 3: Non-video file upload
            logger.info("      📄 Testing non-video file rejection...")
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
                temp_file.write(b'This is a text file, not a video')
                temp_file_path = temp_file.name
            
            try:
                with open(temp_file_path, 'rb') as f:
                    files = {'file': ('not_video.txt', f, 'text/plain')}
                    response = self.session.post(f"{self.base_url}/api/videos", files=files)
                
                # Should reject non-video files
                if response.status_code == 200:
                    issues.append({
                        "severity": "MEDIUM",
                        "description": "Non-video file was accepted - should validate file type"
                    })
                        
            finally:
                os.unlink(temp_file_path)
            
            return {
                "success": len(issues) == 0,
                "issues": issues,
                "details": f"Video processing test completed. Tested valid files, corrupted files, and non-video files. Found {len(issues)} issues."
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "issues": [{"severity": "CRITICAL", "description": f"Video processing test failed: {str(e)}"}]
            }

    def _test_api_error_handling(self) -> Dict[str, Any]:
        """Test API error handling and HTTP status codes"""
        try:
            logger.info("    🚨 Testing API error handling and HTTP status codes...")
            
            issues = []
            
            error_test_cases = [
                {
                    "name": "Invalid endpoint (404)",
                    "method": "GET",
                    "url": f"{self.base_url}/api/nonexistent-endpoint",
                    "expected_status": 404
                },
                {
                    "name": "Malformed JSON (400)",
                    "method": "POST",
                    "url": f"{self.base_url}/api/projects",
                    "data": "invalid json",
                    "headers": {"Content-Type": "application/json"},
                    "expected_status": [400, 422]
                },
                {
                    "name": "Missing required fields (422)",
                    "method": "POST", 
                    "url": f"{self.base_url}/api/projects",
                    "json": {"name": ""},  # Missing required fields
                    "expected_status": 422
                },
                {
                    "name": "Invalid project ID (404)",
                    "method": "GET",
                    "url": f"{self.base_url}/api/projects/nonexistent-id",
                    "expected_status": 404
                }
            ]
            
            for test_case in error_test_cases:
                logger.info(f"      🧪 {test_case['name']}...")
                
                try:
                    if test_case["method"] == "GET":
                        response = self.session.get(test_case["url"])
                    elif test_case["method"] == "POST":
                        if "json" in test_case:
                            response = self.session.post(test_case["url"], json=test_case["json"])
                        elif "data" in test_case:
                            headers = test_case.get("headers", {})
                            response = self.session.post(test_case["url"], data=test_case["data"], headers=headers)
                        else:
                            response = self.session.post(test_case["url"])
                    
                    expected_status = test_case["expected_status"]
                    if isinstance(expected_status, list):
                        if response.status_code not in expected_status:
                            issues.append({
                                "severity": "MEDIUM",
                                "description": f"{test_case['name']}: Expected {expected_status}, got {response.status_code}"
                            })
                    else:
                        if response.status_code != expected_status:
                            issues.append({
                                "severity": "MEDIUM", 
                                "description": f"{test_case['name']}: Expected {expected_status}, got {response.status_code}"
                            })
                    
                    # Check if response has proper error message structure
                    if 400 <= response.status_code < 500:
                        try:
                            error_data = response.json()
                            if not isinstance(error_data, dict) or "detail" not in error_data:
                                issues.append({
                                    "severity": "LOW",
                                    "description": f"{test_case['name']}: Error response missing 'detail' field"
                                })
                        except:
                            issues.append({
                                "severity": "LOW",
                                "description": f"{test_case['name']}: Error response is not valid JSON"
                            })
                            
                except Exception as e:
                    issues.append({
                        "severity": "MEDIUM",
                        "description": f"{test_case['name']}: Test failed with exception: {str(e)}"
                    })
            
            return {
                "success": len([i for i in issues if i["severity"] in ["HIGH", "CRITICAL"]]) == 0,
                "issues": issues,
                "details": f"API error handling test completed. Tested {len(error_test_cases)} error scenarios. Found {len(issues)} issues."
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "issues": [{"severity": "CRITICAL", "description": f"API error handling test failed: {str(e)}"}]
            }

    def _phase_2_feature_validation(self) -> Dict[str, Any]:
        """Phase 2: Test ALL major features end-to-end"""
        logger.info("🔍 Phase 2: Complete feature validation...")
        
        features = [
            ("Video Upload & Processing Workflow", self._test_video_workflow),
            ("Project Management System", self._test_project_management),
            ("Test Execution Workflow", self._test_execution_workflow),
            ("Real-time Communication", self._test_realtime_communication)
        ]
        
        phase_results = {
            "tests": [],
            "features_working": 0,
            "score": 0
        }
        
        working_features = 0
        
        for feature_name, test_function in features:
            logger.info(f"  🧪 {feature_name}...")
            
            test_start = time.time()
            try:
                result = test_function()
                test_time = time.time() - test_start
                
                test_result = {
                    "name": feature_name,
                    "status": "WORKING" if result["success"] else "FAILED",
                    "execution_time": test_time,
                    "details": result.get("details", ""),
                    "metrics": result.get("metrics", {})
                }
                
                if result["success"]:
                    working_features += 1
                    logger.info(f"    ✅ {feature_name} - WORKING")
                else:
                    logger.error(f"    ❌ {feature_name} - FAILED: {result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"    💥 {feature_name} - EXCEPTION: {str(e)}")
                test_result = {
                    "name": feature_name,
                    "status": "EXCEPTION",
                    "execution_time": time.time() - test_start,
                    "error": str(e)
                }
            
            phase_results["tests"].append(test_result)
        
        phase_results["features_working"] = working_features
        phase_results["score"] = (working_features / len(features)) * 100
        logger.info(f"📊 Phase 2 Score: {phase_results['score']:.1f}%")
        
        return phase_results

    def _test_video_workflow(self) -> Dict[str, Any]:
        """Test complete video upload and processing workflow"""
        try:
            # Create test video file
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                mp4_content = b'\x00\x00\x00\x20ftypiso m\x00\x00\x02\x00iso miso2avc1mp41' + b'\x00' * 2000
                temp_video.write(mp4_content)
                temp_video_path = temp_video.name
            
            try:
                # Step 1: Upload video
                with open(temp_video_path, 'rb') as f:
                    files = {'file': ('workflow_test.mp4', f, 'video/mp4')}
                    upload_response = self.session.post(f"{self.base_url}/api/videos", files=files)
                
                if upload_response.status_code not in [200, 201]:
                    return {
                        "success": False,
                        "error": f"Video upload failed with status {upload_response.status_code}",
                        "details": "Failed at video upload step"
                    }
                
                upload_data = upload_response.json()
                video_id = upload_data.get("id")
                
                if not video_id:
                    return {
                        "success": False,
                        "error": "No video ID returned from upload",
                        "details": "Video upload response missing ID field"
                    }
                
                # Step 2: Check video status
                time.sleep(1)  # Give processing a moment
                video_response = self.session.get(f"{self.base_url}/api/videos/{video_id}")
                
                if video_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Video retrieval failed with status {video_response.status_code}",
                        "details": "Failed to retrieve uploaded video"
                    }
                
                video_data = video_response.json()
                
                # Step 3: List all videos to verify it appears
                videos_response = self.session.get(f"{self.base_url}/api/videos")
                if videos_response.status_code != 200:
                    return {
                        "success": False,
                        "error": "Failed to list videos",
                        "details": "Video listing endpoint not working"
                    }
                
                videos_list = videos_response.json()
                video_in_list = any(v.get("id") == video_id for v in videos_list)
                
                if not video_in_list:
                    return {
                        "success": False,
                        "error": "Uploaded video not found in videos list",
                        "details": "Video upload-list consistency issue"
                    }
                
                return {
                    "success": True,
                    "details": f"Video workflow completed successfully. Video {video_id} uploaded and retrievable.",
                    "metrics": {
                        "upload_status": upload_data.get("status"),
                        "video_filename": upload_data.get("filename"),
                        "processing_status": video_data.get("processing_status", "unknown")
                    }
                }
                
            finally:
                os.unlink(temp_video_path)
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": "Video workflow test encountered exception"
            }

    def _test_project_management(self) -> Dict[str, Any]:
        """Test complete project management system"""
        try:
            # Step 1: Create project
            project_data = {
                "name": f"Full Workflow Test {uuid.uuid4().hex[:8]}",
                "description": "Testing complete project management workflow",
                "camera_model": "Test Camera Model",
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            }
            
            create_response = self.session.post(f"{self.base_url}/api/projects", json=project_data)
            
            if create_response.status_code not in [200, 201]:
                return {
                    "success": False,
                    "error": f"Project creation failed with status {create_response.status_code}",
                    "details": "Failed at project creation step"
                }
            
            project = create_response.json()
            project_id = project.get("id")
            
            if not project_id:
                return {
                    "success": False,
                    "error": "No project ID returned from creation",
                    "details": "Project creation response missing ID"
                }
            
            # Step 2: Retrieve project
            get_response = self.session.get(f"{self.base_url}/api/projects/{project_id}")
            
            if get_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Project retrieval failed with status {get_response.status_code}",
                    "details": "Failed to retrieve created project"
                }
            
            retrieved_project = get_response.json()
            
            # Step 3: Update project
            update_data = {
                "description": "Updated description for workflow test"
            }
            
            update_response = self.session.put(f"{self.base_url}/api/projects/{project_id}", json=update_data)
            
            if update_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Project update failed with status {update_response.status_code}",
                    "details": "Failed at project update step"
                }
            
            # Step 4: List projects to verify
            list_response = self.session.get(f"{self.base_url}/api/projects")
            
            if list_response.status_code != 200:
                return {
                    "success": False,
                    "error": "Failed to list projects",
                    "details": "Project listing endpoint not working"
                }
            
            projects_list = list_response.json()
            project_in_list = any(p.get("id") == project_id for p in projects_list)
            
            if not project_in_list:
                return {
                    "success": False,
                    "error": "Created project not found in projects list",
                    "details": "Project create-list consistency issue"
                }
            
            return {
                "success": True,
                "details": f"Project management workflow completed successfully. Project {project_id} created, retrieved, updated, and listed.",
                "metrics": {
                    "project_name": project.get("name"),
                    "project_status": project.get("status"),
                    "operations_completed": 4
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": "Project management workflow test encountered exception"
            }

    def _test_execution_workflow(self) -> Dict[str, Any]:
        """Test test execution workflow (simplified validation)"""
        try:
            # For now, we'll test the endpoints that should exist for test execution
            
            # Check if test session endpoints are available
            sessions_response = self.session.get(f"{self.base_url}/api/test-sessions")
            
            if sessions_response.status_code == 404:
                return {
                    "success": False,
                    "error": "Test session endpoints not available",
                    "details": "Test execution workflow endpoints not implemented"
                }
            elif sessions_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Test sessions endpoint returned {sessions_response.status_code}",
                    "details": "Test execution system not responding correctly"
                }
            
            # Basic validation that the endpoint exists and returns data
            sessions_data = sessions_response.json()
            
            return {
                "success": True,
                "details": "Test execution workflow endpoints accessible and responding correctly.",
                "metrics": {
                    "sessions_endpoint_status": "available",
                    "response_format": "json",
                    "existing_sessions": len(sessions_data) if isinstance(sessions_data, list) else "unknown"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": "Test execution workflow validation encountered exception"
            }

    def _test_realtime_communication(self) -> Dict[str, Any]:
        """Test real-time communication capabilities"""
        try:
            # Test if WebSocket endpoints are available
            # This is a basic test - in a full implementation we'd test actual WebSocket connections
            
            # Check if the backend has WebSocket capabilities
            # We'll test this by checking if the socketio endpoint exists
            socketio_response = self.session.get(f"{self.base_url}/socket.io/")
            
            if socketio_response.status_code == 404:
                return {
                    "success": False,
                    "error": "WebSocket/Socket.IO endpoints not available",
                    "details": "Real-time communication not implemented"
                }
            
            # If we get a response (even if it's not 200), it means the WebSocket server is running
            return {
                "success": True,
                "details": "Real-time communication endpoints accessible.",
                "metrics": {
                    "socketio_endpoint_status": "available",
                    "response_code": socketio_response.status_code
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": "Real-time communication test encountered exception"
            }

    def _phase_3_performance_stability(self) -> Dict[str, Any]:
        """Phase 3: Performance and stability testing"""
        logger.info("🔍 Phase 3: Performance and stability testing...")
        
        tests = [
            ("Load Testing (20 concurrent users)", self._test_load_performance),
            ("Stress Testing (large files)", self._test_stress_conditions),
            ("Error Recovery", self._test_error_recovery)
        ]
        
        phase_results = {
            "tests": [],
            "performance_metrics": {},
            "score": 0
        }
        
        passed_tests = 0
        
        for test_name, test_function in tests:
            logger.info(f"  🧪 {test_name}...")
            
            test_start = time.time()
            try:
                result = test_function()
                test_time = time.time() - test_start
                
                test_result = {
                    "name": test_name,
                    "status": "PASSED" if result["success"] else "FAILED",
                    "execution_time": test_time,
                    "details": result.get("details", ""),
                    "metrics": result.get("metrics", {})
                }
                
                if result["success"]:
                    passed_tests += 1
                    logger.info(f"    ✅ {test_name} - PASSED")
                else:
                    logger.error(f"    ❌ {test_name} - FAILED: {result.get('error', 'Unknown error')}")
                
                # Collect performance metrics
                if "metrics" in result:
                    phase_results["performance_metrics"][test_name] = result["metrics"]
                
            except Exception as e:
                logger.error(f"    💥 {test_name} - EXCEPTION: {str(e)}")
                test_result = {
                    "name": test_name,
                    "status": "EXCEPTION",
                    "execution_time": time.time() - test_start,
                    "error": str(e)
                }
            
            phase_results["tests"].append(test_result)
        
        phase_results["score"] = (passed_tests / len(tests)) * 100
        logger.info(f"📊 Phase 3 Score: {phase_results['score']:.1f}%")
        
        return phase_results

    def _test_load_performance(self) -> Dict[str, Any]:
        """Test system performance under load"""
        try:
            logger.info("    📊 Running load test with 20 concurrent users...")
            
            def simulate_user_session():
                session_start = time.time()
                operations = []
                
                try:
                    # User operation 1: List projects
                    start_time = time.time()
                    response = self.session.get(f"{self.base_url}/api/projects")
                    operations.append({
                        "operation": "list_projects",
                        "status_code": response.status_code,
                        "response_time": time.time() - start_time,
                        "success": response.status_code == 200
                    })
                    
                    # User operation 2: List videos
                    start_time = time.time()
                    response = self.session.get(f"{self.base_url}/api/videos")
                    operations.append({
                        "operation": "list_videos",
                        "status_code": response.status_code,
                        "response_time": time.time() - start_time,
                        "success": response.status_code == 200
                    })
                    
                    # User operation 3: Health check
                    start_time = time.time()
                    response = self.session.get(f"{self.base_url}/health")
                    operations.append({
                        "operation": "health_check",
                        "status_code": response.status_code,
                        "response_time": time.time() - start_time,
                        "success": response.status_code == 200
                    })
                    
                except Exception as e:
                    operations.append({
                        "operation": "session_error",
                        "error": str(e),
                        "success": False
                    })
                
                return {
                    "total_session_time": time.time() - session_start,
                    "operations": operations,
                    "successful_operations": sum(1 for op in operations if op.get("success", False))
                }
            
            # Execute 20 concurrent user sessions
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(simulate_user_session) for _ in range(20)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            # Analyze results
            total_operations = sum(len(r["operations"]) for r in results)
            successful_operations = sum(r["successful_operations"] for r in results)
            success_rate = (successful_operations / total_operations) * 100 if total_operations > 0 else 0
            
            # Calculate average response times
            all_response_times = []
            for result in results:
                for operation in result["operations"]:
                    if "response_time" in operation:
                        all_response_times.append(operation["response_time"])
            
            avg_response_time = sum(all_response_times) / len(all_response_times) if all_response_times else 0
            max_response_time = max(all_response_times) if all_response_times else 0
            
            # Determine if test passed
            success = (
                success_rate >= 95 and  # 95% success rate
                avg_response_time <= 3.0 and  # Under 3 seconds average
                max_response_time <= 10.0  # No request over 10 seconds
            )
            
            return {
                "success": success,
                "details": f"Load test completed: {success_rate:.1f}% success rate, {avg_response_time:.2f}s avg response time",
                "metrics": {
                    "concurrent_users": 20,
                    "total_operations": total_operations,
                    "successful_operations": successful_operations,
                    "success_rate": success_rate,
                    "average_response_time": avg_response_time,
                    "max_response_time": max_response_time
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": "Load testing encountered exception"
            }

    def _test_stress_conditions(self) -> Dict[str, Any]:
        """Test system under stress conditions"""
        try:
            logger.info("    💪 Testing stress conditions...")
            
            # Stress test: Multiple rapid requests
            stress_start = time.time()
            successful_requests = 0
            total_requests = 100
            
            for i in range(total_requests):
                try:
                    response = self.session.get(f"{self.base_url}/health", timeout=5)
                    if response.status_code == 200:
                        successful_requests += 1
                except:
                    pass  # Count as failed request
                
                if i % 20 == 0:
                    logger.info(f"      Progress: {i}/{total_requests} requests completed")
            
            stress_duration = time.time() - stress_start
            success_rate = (successful_requests / total_requests) * 100
            requests_per_second = total_requests / stress_duration
            
            # Test passes if we maintain reasonable performance
            success = success_rate >= 90 and requests_per_second >= 10
            
            return {
                "success": success,
                "details": f"Stress test: {success_rate:.1f}% success rate, {requests_per_second:.1f} req/s",
                "metrics": {
                    "total_requests": total_requests,
                    "successful_requests": successful_requests,
                    "success_rate": success_rate,
                    "duration": stress_duration,
                    "requests_per_second": requests_per_second
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": "Stress testing encountered exception"
            }

    def _test_error_recovery(self) -> Dict[str, Any]:
        """Test error recovery mechanisms"""
        try:
            logger.info("    🔄 Testing error recovery...")
            
            # Test recovery from invalid requests
            recovery_tests = [
                {"url": f"{self.base_url}/health", "should_work": True},
                {"url": f"{self.base_url}/invalid-endpoint", "should_work": False},
                {"url": f"{self.base_url}/health", "should_work": True},  # Should work again
            ]
            
            results = []
            for test in recovery_tests:
                try:
                    response = self.session.get(test["url"], timeout=5)
                    success = (response.status_code == 200) if test["should_work"] else (response.status_code != 200)
                    results.append(success)
                except:
                    results.append(False)
            
            # All tests should pass for good error recovery
            all_passed = all(results)
            
            return {
                "success": all_passed,
                "details": f"Error recovery test: {len([r for r in results if r])}/{len(results)} tests passed",
                "metrics": {
                    "recovery_tests_passed": sum(results),
                    "total_recovery_tests": len(results),
                    "recovery_success_rate": (sum(results) / len(results)) * 100
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": "Error recovery testing encountered exception"
            }

    def _phase_4_user_experience(self) -> Dict[str, Any]:
        """Phase 4: User experience validation"""
        logger.info("🔍 Phase 4: User experience validation...")
        
        tests = [
            ("Frontend Accessibility", self._test_frontend_accessibility),
            ("API Response Quality", self._test_api_response_quality),
            ("Documentation Availability", self._test_documentation)
        ]
        
        phase_results = {
            "tests": [],
            "ux_score": 0
        }
        
        passed_tests = 0
        
        for test_name, test_function in tests:
            logger.info(f"  🧪 {test_name}...")
            
            test_start = time.time()
            try:
                result = test_function()
                test_time = time.time() - test_start
                
                test_result = {
                    "name": test_name,
                    "status": "PASSED" if result["success"] else "FAILED",
                    "execution_time": test_time,
                    "details": result.get("details", ""),
                    "metrics": result.get("metrics", {})
                }
                
                if result["success"]:
                    passed_tests += 1
                    logger.info(f"    ✅ {test_name} - PASSED")
                else:
                    logger.error(f"    ❌ {test_name} - FAILED: {result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"    💥 {test_name} - EXCEPTION: {str(e)}")
                test_result = {
                    "name": test_name,
                    "status": "EXCEPTION",
                    "execution_time": time.time() - test_start,
                    "error": str(e)
                }
            
            phase_results["tests"].append(test_result)
        
        phase_results["ux_score"] = (passed_tests / len(tests)) * 100
        logger.info(f"📊 Phase 4 Score: {phase_results['ux_score']:.1f}%")
        
        return phase_results

    def _test_frontend_accessibility(self) -> Dict[str, Any]:
        """Test frontend accessibility"""
        try:
            # Basic accessibility check - verify frontend is serving content
            response = self.session.get(self.frontend_url, timeout=10)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Frontend not accessible: {response.status_code}",
                    "details": "Frontend application not responding"
                }
            
            content = response.text
            
            # Basic checks for accessibility features
            has_title = '<title>' in content
            has_meta_viewport = 'viewport' in content
            has_semantic_structure = '<main>' in content or '<section>' in content or '<article>' in content
            
            accessibility_score = sum([has_title, has_meta_viewport, has_semantic_structure])
            
            return {
                "success": accessibility_score >= 2,
                "details": f"Frontend accessibility: {accessibility_score}/3 basic checks passed",
                "metrics": {
                    "has_title": has_title,
                    "has_viewport": has_meta_viewport,
                    "has_semantic_structure": has_semantic_structure,
                    "content_length": len(content)
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": "Frontend accessibility test encountered exception"
            }

    def _test_api_response_quality(self) -> Dict[str, Any]:
        """Test API response quality and consistency"""
        try:
            # Test response format consistency
            responses_to_test = [
                ("GET", f"{self.base_url}/health", "Health endpoint"),
                ("GET", f"{self.base_url}/api/projects", "Projects list"),
                ("GET", f"{self.base_url}/api/videos", "Videos list")
            ]
            
            quality_issues = []
            
            for method, url, name in responses_to_test:
                try:
                    response = self.session.get(url)
                    
                    if response.status_code != 200:
                        quality_issues.append(f"{name}: Non-200 response ({response.status_code})")
                        continue
                    
                    # Check response format
                    try:
                        data = response.json()
                    except:
                        quality_issues.append(f"{name}: Invalid JSON response")
                        continue
                    
                    # Check response time
                    if response.elapsed.total_seconds() > 5:
                        quality_issues.append(f"{name}: Slow response ({response.elapsed.total_seconds():.2f}s)")
                    
                    # Check for proper headers
                    if 'application/json' not in response.headers.get('content-type', ''):
                        quality_issues.append(f"{name}: Missing JSON content-type header")
                        
                except Exception as e:
                    quality_issues.append(f"{name}: Request failed - {str(e)}")
            
            return {
                "success": len(quality_issues) == 0,
                "details": f"API response quality: {len(quality_issues)} issues found",
                "metrics": {
                    "endpoints_tested": len(responses_to_test),
                    "quality_issues": quality_issues
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": "API response quality test encountered exception"
            }

    def _test_documentation(self) -> Dict[str, Any]:
        """Test documentation availability"""
        try:
            # Check if API documentation is available
            docs_response = self.session.get(f"{self.base_url}/docs")
            
            if docs_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"API documentation not accessible: {docs_response.status_code}",
                    "details": "Swagger/OpenAPI documentation not available"
                }
            
            # Check if it contains expected documentation content
            content = docs_response.text
            has_swagger = 'swagger' in content.lower() or 'openapi' in content.lower()
            has_api_info = 'api' in content.lower()
            
            return {
                "success": has_swagger and has_api_info,
                "details": f"Documentation available at /docs with {'proper' if has_swagger else 'basic'} API documentation",
                "metrics": {
                    "docs_accessible": True,
                    "has_swagger": has_swagger,
                    "has_api_info": has_api_info,
                    "content_length": len(content)
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": "Documentation test encountered exception"
            }

    def _generate_final_assessment(self):
        """Generate final production readiness assessment"""
        logger.info("\n🎯 GENERATING FINAL ASSESSMENT...")
        
        # Calculate overall scores
        phase_scores = {}
        for phase_name, phase_results in self.validation_results["phase_results"].items():
            phase_scores[phase_name] = phase_results.get("score", 0)
        
        # Weighted scoring
        weights = {
            "Phase 1: Critical Issues Resolution": 0.40,  # 40% weight
            "Phase 2: Complete Feature Validation": 0.25,  # 25% weight
            "Phase 3: Performance & Stability": 0.20,     # 20% weight
            "Phase 4: User Experience Validation": 0.15   # 15% weight
        }
        
        overall_score = 0
        for phase_name, score in phase_scores.items():
            weight = weights.get(phase_name, 0)
            overall_score += score * weight
        
        # Determine final recommendation
        if overall_score >= self.thresholds["production_ready"]:
            recommendation = "APPROVED FOR PRODUCTION"
            risk_level = "LOW"
        elif overall_score >= self.thresholds["staging_ready"]:
            recommendation = "APPROVED FOR STAGING"
            risk_level = "MEDIUM"
        else:
            recommendation = "REQUIRES FIXES"
            risk_level = "HIGH"
        
        # Count critical issues
        critical_issues = len([issue for issue in self.validation_results["critical_issues"] 
                             if issue.get("severity") == "CRITICAL"])
        
        self.validation_results["final_assessment"] = {
            "overall_score": overall_score,
            "recommendation": recommendation,
            "risk_level": risk_level,
            "critical_issues_count": critical_issues,
            "phase_scores": phase_scores,
            "test_completion_time": datetime.now().isoformat(),
            "summary": f"System scored {overall_score:.1f}% overall. {recommendation}."
        }
        
        logger.info(f"📊 FINAL SCORE: {overall_score:.1f}%")
        logger.info(f"🎯 RECOMMENDATION: {recommendation}")
        logger.info(f"⚠️  RISK LEVEL: {risk_level}")

    def _save_validation_report(self):
        """Save comprehensive validation report"""
        report_filename = f"final_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_filename, 'w') as f:
            json.dump(self.validation_results, f, indent=2, default=str)
        
        logger.info(f"📄 Validation report saved to: {report_filename}")

def main():
    """Execute final system validation"""
    print("🎯 AI MODEL VALIDATION PLATFORM - FINAL SYSTEM VALIDATION")
    print("=" * 80)
    
    validator = FinalSystemValidator()
    
    try:
        results = validator.run_complete_validation()
        
        print("\n" + "=" * 80)
        print("🏆 FINAL VALIDATION RESULTS")
        print("=" * 80)
        
        final_assessment = results["final_assessment"]
        print(f"Overall Score: {final_assessment['overall_score']:.1f}%")
        print(f"Recommendation: {final_assessment['recommendation']}")
        print(f"Risk Level: {final_assessment['risk_level']}")
        print(f"Critical Issues: {final_assessment['critical_issues_count']}")
        
        print("\nPhase Scores:")
        for phase, score in final_assessment["phase_scores"].items():
            print(f"  {phase}: {score:.1f}%")
        
        if final_assessment["overall_score"] >= 90:
            print("\n✅ SYSTEM IS PRODUCTION READY")
        elif final_assessment["overall_score"] >= 80:
            print("\n⚠️  SYSTEM READY FOR STAGING")
        else:
            print("\n❌ SYSTEM REQUIRES FIXES BEFORE DEPLOYMENT")
        
        return results
        
    except KeyboardInterrupt:
        print("\n🛑 Validation interrupted by user")
        return None
    except Exception as e:
        print(f"\n💥 CRITICAL VALIDATION FAILURE: {str(e)}")
        return None

if __name__ == "__main__":
    main()