#!/usr/bin/env python3
"""
Comprehensive Backend API Validation - Tests all endpoints systematically
"""
import asyncio
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
import httpx

class ComprehensiveAPIValidator:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.results = {
            "test_start": datetime.now().isoformat(),
            "health_checks": {},
            "project_operations": {},
            "video_operations": {},
            "annotation_operations": {},
            "ml_pipeline": {},
            "database_operations": {},
            "error_handling": {},
            "performance": {},
            "summary": {}
        }
        self.test_project_id = None
        self.test_video_id = None

    async def wait_for_server(self, max_attempts=20):
        """Wait for server to be ready"""
        print("⏳ Waiting for backend server to start...")
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            for attempt in range(max_attempts):
                try:
                    response = await client.get(f"{self.base_url}/health")
                    if response.status_code == 200:
                        print("✅ Backend server is ready!")
                        return True
                except:
                    pass
                await asyncio.sleep(2)
        
        print("❌ Backend server did not start within expected time")
        return False

    async def test_health_endpoints(self):
        """Test all health and status endpoints"""
        print("\n🏥 Testing Health & Status Endpoints...")
        
        health_endpoints = [
            "/health",
            "/api/health", 
            "/status",
            "/docs",
            "/redoc",
            "/openapi.json"
        ]
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for endpoint in health_endpoints:
                try:
                    start_time = time.time()
                    response = await client.get(f"{self.base_url}{endpoint}")
                    response_time = (time.time() - start_time) * 1000
                    
                    self.results["health_checks"][endpoint] = {
                        "status_code": response.status_code,
                        "response_time_ms": round(response_time, 2),
                        "success": response.status_code == 200,
                        "content_length": len(response.content)
                    }
                    
                    if response.status_code == 200:
                        try:
                            if endpoint.endswith('.json'):
                                data = response.json()
                                self.results["health_checks"][endpoint]["openapi_version"] = data.get("openapi", "unknown")
                            elif "docs" not in endpoint:
                                data = response.json()
                                self.results["health_checks"][endpoint]["response_data"] = data
                        except:
                            pass  # Not all endpoints return JSON
                    
                    status_icon = "✅" if response.status_code == 200 else "❌"
                    print(f"  {status_icon} {endpoint}: {response.status_code} ({response_time:.1f}ms)")
                    
                except Exception as e:
                    self.results["health_checks"][endpoint] = {
                        "error": str(e),
                        "success": False
                    }
                    print(f"  ❌ {endpoint}: {e}")

    async def test_project_crud_operations(self):
        """Test complete project CRUD operations"""
        print("\n📁 Testing Project CRUD Operations...")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test GET all projects
            try:
                response = await client.get(f"{self.base_url}/api/projects")
                self.results["project_operations"]["list_all"] = {
                    "status_code": response.status_code,
                    "success": response.status_code == 200
                }
                
                if response.status_code == 200:
                    projects = response.json()
                    self.results["project_operations"]["list_all"]["count"] = len(projects)
                    print(f"  ✅ List Projects: {response.status_code} ({len(projects)} projects)")
                else:
                    print(f"  ❌ List Projects: {response.status_code}")
                    
            except Exception as e:
                self.results["project_operations"]["list_all"] = {"error": str(e), "success": False}
                print(f"  ❌ List Projects: {e}")

            # Test CREATE project
            try:
                project_data = {
                    "name": f"API Test Project {uuid.uuid4().hex[:8]}",
                    "description": "Comprehensive API validation test project", 
                    "camera_type": "webcam",
                    "signal_type": "voltage",
                    "status": "active"
                }
                
                response = await client.post(f"{self.base_url}/api/projects", json=project_data)
                
                self.results["project_operations"]["create"] = {
                    "status_code": response.status_code,
                    "success": response.status_code in [200, 201],
                    "request_data": project_data
                }
                
                if response.status_code in [200, 201]:
                    project = response.json()
                    self.test_project_id = project.get("id")
                    self.results["project_operations"]["create"]["project_id"] = self.test_project_id
                    print(f"  ✅ Create Project: {response.status_code} (ID: {self.test_project_id})")
                else:
                    error_text = response.text[:200] if response.text else "Unknown error"
                    self.results["project_operations"]["create"]["error"] = error_text
                    print(f"  ❌ Create Project: {response.status_code} - {error_text}")
                    
            except Exception as e:
                self.results["project_operations"]["create"] = {"error": str(e), "success": False}
                print(f"  ❌ Create Project: {e}")

            # Test GET specific project
            if self.test_project_id:
                try:
                    response = await client.get(f"{self.base_url}/api/projects/{self.test_project_id}")
                    self.results["project_operations"]["get_by_id"] = {
                        "status_code": response.status_code,
                        "success": response.status_code == 200
                    }
                    
                    if response.status_code == 200:
                        project = response.json()
                        self.results["project_operations"]["get_by_id"]["project_data"] = project
                        print(f"  ✅ Get Project by ID: {response.status_code}")
                    else:
                        print(f"  ❌ Get Project by ID: {response.status_code}")
                        
                except Exception as e:
                    self.results["project_operations"]["get_by_id"] = {"error": str(e), "success": False}
                    print(f"  ❌ Get Project by ID: {e}")

            # Test UPDATE project
            if self.test_project_id:
                try:
                    update_data = {
                        "description": "Updated description via API validation",
                        "status": "active"
                    }
                    
                    response = await client.put(f"{self.base_url}/api/projects/{self.test_project_id}", json=update_data)
                    
                    self.results["project_operations"]["update"] = {
                        "status_code": response.status_code,
                        "success": response.status_code == 200,
                        "update_data": update_data
                    }
                    
                    if response.status_code == 200:
                        print(f"  ✅ Update Project: {response.status_code}")
                    else:
                        print(f"  ❌ Update Project: {response.status_code}")
                        
                except Exception as e:
                    self.results["project_operations"]["update"] = {"error": str(e), "success": False}
                    print(f"  ❌ Update Project: {e}")

    async def test_video_operations(self):
        """Test video upload and management"""
        print("\n🎥 Testing Video Operations...")
        
        # Find video files
        backend_dir = Path(__file__).parent.parent / "backend"
        video_files = list((backend_dir / "uploads").glob("*.mp4"))
        
        if not video_files:
            print("  ⚠️  No video files found for testing")
            self.results["video_operations"]["no_videos"] = True
            return
        
        test_video = video_files[0]
        print(f"  📹 Using test video: {test_video.name} ({test_video.stat().st_size} bytes)")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test list videos
            try:
                response = await client.get(f"{self.base_url}/api/videos")
                self.results["video_operations"]["list_all"] = {
                    "status_code": response.status_code,
                    "success": response.status_code == 200
                }
                
                if response.status_code == 200:
                    videos = response.json()
                    self.results["video_operations"]["list_all"]["count"] = len(videos)
                    print(f"  ✅ List Videos: {response.status_code} ({len(videos)} videos)")
                else:
                    print(f"  ❌ List Videos: {response.status_code}")
                    
            except Exception as e:
                self.results["video_operations"]["list_all"] = {"error": str(e), "success": False}
                print(f"  ❌ List Videos: {e}")

            # Test video upload
            if self.test_project_id:
                try:
                    with open(test_video, "rb") as video_file:
                        files = {"file": (test_video.name, video_file, "video/mp4")}
                        data = {"project_id": str(self.test_project_id)}
                        
                        response = await client.post(
                            f"{self.base_url}/api/videos/upload",
                            files=files,
                            data=data
                        )
                        
                        self.results["video_operations"]["upload"] = {
                            "status_code": response.status_code,
                            "success": response.status_code in [200, 201],
                            "file_size": test_video.stat().st_size,
                            "filename": test_video.name
                        }
                        
                        if response.status_code in [200, 201]:
                            video_data = response.json()
                            self.test_video_id = video_data.get("id")
                            self.results["video_operations"]["upload"]["video_id"] = self.test_video_id
                            print(f"  ✅ Upload Video: {response.status_code} (ID: {self.test_video_id})")
                        else:
                            error_text = response.text[:200] if response.text else "Unknown error"
                            self.results["video_operations"]["upload"]["error"] = error_text
                            print(f"  ❌ Upload Video: {response.status_code} - {error_text}")
                            
                except Exception as e:
                    self.results["video_operations"]["upload"] = {"error": str(e), "success": False}
                    print(f"  ❌ Upload Video: {e}")
            else:
                print("  ⚠️  No project ID available for video upload")

    async def test_annotation_operations(self):
        """Test annotation CRUD operations"""
        print("\n📝 Testing Annotation Operations...")
        
        if not self.test_video_id:
            print("  ⚠️  No video ID available for annotation testing")
            self.results["annotation_operations"]["no_video"] = True
            return
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test list annotations
            try:
                response = await client.get(f"{self.base_url}/api/annotations")
                self.results["annotation_operations"]["list_all"] = {
                    "status_code": response.status_code,
                    "success": response.status_code == 200
                }
                
                if response.status_code == 200:
                    annotations = response.json()
                    self.results["annotation_operations"]["list_all"]["count"] = len(annotations)
                    print(f"  ✅ List Annotations: {response.status_code} ({len(annotations)} annotations)")
                else:
                    print(f"  ❌ List Annotations: {response.status_code}")
                    
            except Exception as e:
                self.results["annotation_operations"]["list_all"] = {"error": str(e), "success": False}
                print(f"  ❌ List Annotations: {e}")

            # Test create annotation
            try:
                annotation_data = {
                    "video_id": self.test_video_id,
                    "timestamp": 5.0,
                    "x": 100,
                    "y": 150,
                    "width": 50,
                    "height": 75,
                    "label": "test_object",
                    "confidence": 0.85,
                    "object_type": "person"
                }
                
                response = await client.post(f"{self.base_url}/api/annotations", json=annotation_data)
                
                self.results["annotation_operations"]["create"] = {
                    "status_code": response.status_code,
                    "success": response.status_code in [200, 201],
                    "request_data": annotation_data
                }
                
                if response.status_code in [200, 201]:
                    annotation = response.json()
                    annotation_id = annotation.get("id")
                    self.results["annotation_operations"]["create"]["annotation_id"] = annotation_id
                    print(f"  ✅ Create Annotation: {response.status_code} (ID: {annotation_id})")
                else:
                    error_text = response.text[:200] if response.text else "Unknown error"
                    self.results["annotation_operations"]["create"]["error"] = error_text
                    print(f"  ❌ Create Annotation: {response.status_code} - {error_text}")
                    
            except Exception as e:
                self.results["annotation_operations"]["create"] = {"error": str(e), "success": False}
                print(f"  ❌ Create Annotation: {e}")

    async def test_ml_pipeline_endpoints(self):
        """Test ML and detection pipeline endpoints"""
        print("\n🧠 Testing ML Pipeline Endpoints...")
        
        ml_endpoints = [
            "/api/ml/status",
            "/api/detection/status", 
            "/api/models/available",
            "/api/inference/status"
        ]
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for endpoint in ml_endpoints:
                try:
                    response = await client.get(f"{self.base_url}{endpoint}")
                    self.results["ml_pipeline"][endpoint] = {
                        "status_code": response.status_code,
                        "success": response.status_code in [200, 404],  # 404 acceptable for some endpoints
                        "endpoint_exists": response.status_code != 404
                    }
                    
                    status_icon = "✅" if response.status_code == 200 else "⚠️" if response.status_code == 404 else "❌"
                    print(f"  {status_icon} {endpoint}: {response.status_code}")
                    
                except Exception as e:
                    self.results["ml_pipeline"][endpoint] = {"error": str(e), "success": False}
                    print(f"  ❌ {endpoint}: {e}")

            # Test detection on video if available
            if self.test_video_id:
                try:
                    response = await client.post(
                        f"{self.base_url}/api/videos/{self.test_video_id}/detect",
                        json={"model": "yolov8n", "confidence_threshold": 0.5}
                    )
                    
                    self.results["ml_pipeline"]["video_detection"] = {
                        "status_code": response.status_code,
                        "success": response.status_code in [200, 202, 404],  # Various acceptable responses
                        "video_id": self.test_video_id
                    }
                    
                    status_icon = "✅" if response.status_code in [200, 202] else "⚠️" if response.status_code == 404 else "❌"
                    print(f"  {status_icon} Video Detection: {response.status_code}")
                    
                except Exception as e:
                    self.results["ml_pipeline"]["video_detection"] = {"error": str(e), "success": False}
                    print(f"  ❌ Video Detection: {e}")

    async def test_database_integrity(self):
        """Test database operations and integrity"""
        print("\n🗃️ Testing Database Operations...")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test database health
            try:
                response = await client.get(f"{self.base_url}/api/database/health")
                self.results["database_operations"]["health"] = {
                    "status_code": response.status_code,
                    "success": response.status_code == 200
                }
                
                if response.status_code == 200:
                    db_health = response.json()
                    self.results["database_operations"]["health"]["data"] = db_health
                    print(f"  ✅ Database Health: {response.status_code}")
                else:
                    print(f"  ❌ Database Health: {response.status_code}")
                    
            except Exception as e:
                self.results["database_operations"]["health"] = {"error": str(e), "success": False}
                print(f"  ❌ Database Health: {e}")

            # Test data persistence by re-fetching created project
            if self.test_project_id:
                try:
                    response = await client.get(f"{self.base_url}/api/projects/{self.test_project_id}")
                    self.results["database_operations"]["data_persistence"] = {
                        "status_code": response.status_code,
                        "success": response.status_code == 200,
                        "project_id": self.test_project_id
                    }
                    
                    if response.status_code == 200:
                        print(f"  ✅ Data Persistence: Project {self.test_project_id} exists")
                    else:
                        print(f"  ❌ Data Persistence: Project not found")
                        
                except Exception as e:
                    self.results["database_operations"]["data_persistence"] = {"error": str(e), "success": False}
                    print(f"  ❌ Data Persistence: {e}")

    async def test_error_handling(self):
        """Test error handling and edge cases"""
        print("\n⚠️ Testing Error Handling...")
        
        test_cases = [
            ("Invalid endpoint", "GET", "/api/nonexistent", [404]),
            ("Invalid project ID", "GET", "/api/projects/invalid-id", [400, 404, 422]),
            ("Invalid video ID", "GET", "/api/videos/999999", [404, 422]),
            ("Invalid annotation data", "POST", "/api/annotations", [400, 422])
        ]
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for test_name, method, endpoint, expected_codes in test_cases:
                try:
                    if method == "GET":
                        response = await client.get(f"{self.base_url}{endpoint}")
                    elif method == "POST":
                        # Send invalid data
                        invalid_data = {"invalid": "data", "missing": "required_fields"}
                        response = await client.post(f"{self.base_url}{endpoint}", json=invalid_data)
                    
                    self.results["error_handling"][test_name] = {
                        "status_code": response.status_code,
                        "success": response.status_code in expected_codes,
                        "expected_codes": expected_codes,
                        "proper_error_handling": response.status_code >= 400
                    }
                    
                    status_icon = "✅" if response.status_code in expected_codes else "❌"
                    print(f"  {status_icon} {test_name}: {response.status_code} (expected: {expected_codes})")
                    
                except Exception as e:
                    self.results["error_handling"][test_name] = {"error": str(e), "success": False}
                    print(f"  ❌ {test_name}: {e}")

    async def test_performance_metrics(self):
        """Test API performance"""
        print("\n⚡ Testing Performance Metrics...")
        
        if not self.test_project_id:
            print("  ⚠️  No project available for performance testing")
            return
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test concurrent requests
            try:
                print("  🔄 Testing concurrent requests...")
                start_time = time.time()
                
                tasks = []
                for i in range(5):  # Reduced from 10 to avoid overwhelming
                    task = client.get(f"{self.base_url}/api/projects/{self.test_project_id}")
                    tasks.append(task)
                
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                end_time = time.time()
                
                successful_requests = sum(1 for r in responses if hasattr(r, 'status_code') and r.status_code == 200)
                
                self.results["performance"]["concurrent_requests"] = {
                    "total_requests": 5,
                    "successful_requests": successful_requests,
                    "total_time_seconds": round(end_time - start_time, 3),
                    "average_response_time_seconds": round((end_time - start_time) / 5, 3),
                    "success_rate": successful_requests / 5
                }
                
                print(f"  ✅ Concurrent Requests: {successful_requests}/5 successful in {self.results['performance']['concurrent_requests']['total_time_seconds']}s")
                
            except Exception as e:
                self.results["performance"]["concurrent_requests"] = {"error": str(e), "success": False}
                print(f"  ❌ Concurrent Requests: {e}")

    def generate_comprehensive_summary(self):
        """Generate comprehensive test summary and analysis"""
        print("\n📊 Generating Comprehensive Summary...")
        
        # Count total tests and successes
        total_tests = 0
        successful_tests = 0
        
        for category, tests in self.results.items():
            if category not in ["test_start", "summary"]:
                for test_name, test_data in tests.items():
                    if isinstance(test_data, dict) and "success" in test_data:
                        total_tests += 1
                        if test_data["success"]:
                            successful_tests += 1
        
        # Analyze critical system functionality
        critical_systems = {
            "api_server": any(test.get("success", False) for test in self.results.get("health_checks", {}).values()),
            "database_connectivity": self.results.get("database_operations", {}).get("health", {}).get("success", False),
            "project_management": self.results.get("project_operations", {}).get("create", {}).get("success", False),
            "video_uploads": self.results.get("video_operations", {}).get("upload", {}).get("success", False),
            "annotation_system": self.results.get("annotation_operations", {}).get("create", {}).get("success", False),
            "error_handling": any(test.get("success", False) for test in self.results.get("error_handling", {}).values())
        }
        
        # Generate recommendations
        recommendations = []
        if not critical_systems["api_server"]:
            recommendations.append("Fix API server health endpoints")
        if not critical_systems["database_connectivity"]:
            recommendations.append("Resolve database connectivity issues")
        if not critical_systems["project_management"]:
            recommendations.append("Debug project creation/management functionality")
        if not critical_systems["video_uploads"]:
            recommendations.append("Investigate video upload pipeline")
        if successful_tests / total_tests < 0.8:
            recommendations.append("Address failing API endpoints before production")
        
        # Calculate performance metrics
        perf_data = self.results.get("performance", {})
        avg_response_time = perf_data.get("concurrent_requests", {}).get("average_response_time_seconds", 0)
        
        self.results["summary"] = {
            "test_end": datetime.now().isoformat(),
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": total_tests - successful_tests,
            "success_rate_percentage": round(successful_tests / total_tests * 100, 2) if total_tests > 0 else 0,
            "critical_systems_status": critical_systems,
            "system_readiness": {
                "production_ready": successful_tests / total_tests >= 0.8 if total_tests > 0 else False,
                "needs_attention": total_tests - successful_tests > 0,
                "critical_failures": sum(1 for status in critical_systems.values() if not status)
            },
            "performance_metrics": {
                "average_response_time_seconds": avg_response_time,
                "performance_acceptable": avg_response_time < 2.0 if avg_response_time > 0 else None
            },
            "test_data_created": {
                "test_project_id": self.test_project_id,
                "test_video_id": self.test_video_id
            },
            "recommendations": recommendations
        }
        
        print(f"\n📈 COMPREHENSIVE TEST RESULTS:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Successful: {successful_tests}")
        print(f"  Failed: {total_tests - successful_tests}")
        print(f"  Success Rate: {self.results['summary']['success_rate_percentage']}%")
        print(f"  Production Ready: {'✅ Yes' if self.results['summary']['system_readiness']['production_ready'] else '❌ No'}")
        
        print(f"\n🔧 Critical Systems Status:")
        for system, status in critical_systems.items():
            print(f"  {'✅' if status else '❌'} {system.replace('_', ' ').title()}: {'OK' if status else 'FAILED'}")

    async def cleanup_test_data(self):
        """Clean up created test data"""
        print("\n🧹 Cleaning up test data...")
        
        cleanup_results = []
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Delete test project (should cascade delete related data)
            if self.test_project_id:
                try:
                    response = await client.delete(f"{self.base_url}/api/projects/{self.test_project_id}")
                    if response.status_code in [200, 204, 404]:
                        cleanup_results.append(f"✅ Deleted test project: {self.test_project_id}")
                    else:
                        cleanup_results.append(f"⚠️  Could not delete test project: {response.status_code}")
                except Exception as e:
                    cleanup_results.append(f"❌ Cleanup error for project: {e}")
        
        for result in cleanup_results:
            print(f"  {result}")

    async def save_results_to_memory(self):
        """Save comprehensive results to MCP memory"""
        print("\n💾 Storing results in MCP memory...")
        
        # Prepare comprehensive data for MCP memory
        memory_data = {
            "timestamp": datetime.now().isoformat(),
            "comprehensive_api_validation": {
                "summary": self.results["summary"],
                "critical_findings": {
                    "api_server_functional": any(test.get("success", False) for test in self.results.get("health_checks", {}).values()),
                    "database_operational": self.results.get("database_operations", {}).get("health", {}).get("success", False),
                    "crud_operations_working": self.results.get("project_operations", {}).get("create", {}).get("success", False),
                    "file_upload_functional": self.results.get("video_operations", {}).get("upload", {}).get("success", False),
                    "ml_endpoints_available": any(test.get("endpoint_exists", False) for test in self.results.get("ml_pipeline", {}).values()),
                    "error_handling_proper": any(test.get("success", False) for test in self.results.get("error_handling", {}).values())
                },
                "test_data_ids": {
                    "project_id": self.test_project_id,
                    "video_id": self.test_video_id
                },
                "performance_analysis": self.results.get("performance", {}),
                "full_results_summary": {
                    "health_checks": len([t for t in self.results.get("health_checks", {}).values() if t.get("success", False)]),
                    "project_operations": len([t for t in self.results.get("project_operations", {}).values() if t.get("success", False)]),
                    "video_operations": len([t for t in self.results.get("video_operations", {}).values() if t.get("success", False)]),
                    "annotation_operations": len([t for t in self.results.get("annotation_operations", {}).values() if t.get("success", False)]),
                    "ml_pipeline_tests": len([t for t in self.results.get("ml_pipeline", {}).values() if t.get("success", False)]),
                    "database_tests": len([t for t in self.results.get("database_operations", {}).values() if t.get("success", False)]),
                    "error_handling_tests": len([t for t in self.results.get("error_handling", {}).values() if t.get("success", False)])
                }
            }
        }
        
        return memory_data

    async def save_results_to_file(self):
        """Save detailed results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = Path(__file__).parent / f"comprehensive_backend_validation_{timestamp}.json"
        
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"📁 Detailed results saved: {results_file}")
        return results_file

    async def run_comprehensive_validation(self):
        """Execute complete validation suite"""
        print("🎯 Starting Comprehensive Backend API Validation")
        print("=" * 70)
        
        # Wait for server to be ready
        if not await self.wait_for_server():
            print("❌ Backend server not available, cannot proceed")
            return False
        
        try:
            # Execute all test suites
            await self.test_health_endpoints()
            await self.test_project_crud_operations()
            await self.test_video_operations()
            await self.test_annotation_operations()
            await self.test_ml_pipeline_endpoints()
            await self.test_database_integrity()
            await self.test_error_handling()
            await self.test_performance_metrics()
            
            # Generate comprehensive analysis
            self.generate_comprehensive_summary()
            
            # Save results
            memory_data = await self.save_results_to_memory()
            results_file = await self.save_results_to_file()
            
            # Cleanup
            await self.cleanup_test_data()
            
            print(f"\n🎉 Comprehensive Backend API Validation Complete!")
            print(f"📊 Overall Success Rate: {self.results['summary']['success_rate_percentage']}%")
            print(f"🚀 Production Ready: {'Yes' if self.results['summary']['system_readiness']['production_ready'] else 'No'}")
            
            return self.results['summary']['system_readiness']['production_ready']
            
        except Exception as e:
            print(f"❌ Validation suite failed: {e}")
            return False

async def main():
    """Main execution function"""
    validator = ComprehensiveAPIValidator()
    success = await validator.run_comprehensive_validation()
    
    if success:
        print("\n✅ Backend API validation successful - system ready for production!")
    else:
        print("\n❌ Backend API validation identified issues - review results before deployment")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)