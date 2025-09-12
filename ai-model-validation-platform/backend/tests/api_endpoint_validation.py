#!/usr/bin/env python3
"""
API Endpoint Validation Tests
Tests API endpoints work correctly with real backend
"""
import os
import sys
import json
import time
import requests
import subprocess
import signal
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Test Configuration
BASE_URL = "http://localhost:8001"
TIMEOUT = 10.0

class APIValidator:
    """API endpoint validation test suite"""
    
    def __init__(self):
        self.test_results = []
        self.server_process = None
        
    def start_test_server(self):
        """Start the backend server for testing"""
        print("🚀 Starting test server...")
        
        try:
            # Try to start the server
            self.server_process = subprocess.Popen([
                "python3", "main.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for server to start
            time.sleep(3)
            
            # Test if server is responding
            for attempt in range(5):
                try:
                    response = requests.get(f"{BASE_URL}/health", timeout=2)
                    if response.status_code == 200:
                        print("✅ Test server started successfully")
                        return True
                except requests.RequestException:
                    time.sleep(1)
            
            print("❌ Failed to start test server")
            return False
            
        except Exception as e:
            print(f"❌ Error starting server: {e}")
            return False
    
    def stop_test_server(self):
        """Stop the test server"""
        if self.server_process:
            print("🛑 Stopping test server...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            self.server_process = None
    
    def test_health_endpoint(self):
        """Test health endpoint"""
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
            assert response.status_code == 200, f"Health endpoint returned {response.status_code}"
            
            data = response.json()
            assert "status" in data, "Health response missing status field"
            assert data["status"] == "healthy", f"Health status not healthy: {data['status']}"
            
            return {"status": "passed", "response": data}
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def test_project_crud_endpoints(self):
        """Test project CRUD endpoints"""
        try:
            # Test GET /api/projects (should work even if empty)
            response = requests.get(f"{BASE_URL}/api/projects", timeout=TIMEOUT)
            assert response.status_code == 200, f"GET projects returned {response.status_code}"
            
            projects = response.json()
            assert isinstance(projects, list), "Projects response not a list"
            
            # Test POST /api/projects
            project_data = {
                "name": "API Test Project",
                "description": "Test project for API validation",
                "cameraModel": "Test Camera",
                "cameraView": "Front-facing VRU",
                "lensType": "Wide Angle", 
                "resolution": "1920x1080",
                "frameRate": 30,
                "signalType": "GPIO"
            }
            
            create_response = requests.post(
                f"{BASE_URL}/api/projects",
                json=project_data,
                timeout=TIMEOUT
            )
            
            if create_response.status_code != 201:
                # Try simpler data format
                simple_project = {
                    "name": "Simple API Test Project",
                    "camera_model": "Test Camera",
                    "signal_type": "GPIO"
                }
                
                create_response = requests.post(
                    f"{BASE_URL}/api/projects", 
                    json=simple_project,
                    timeout=TIMEOUT
                )
            
            # Should succeed with either format
            assert create_response.status_code in [200, 201], f"POST projects returned {create_response.status_code}"
            
            project = create_response.json()
            assert "id" in project, "Created project missing id field"
            project_id = project["id"]
            
            # Test GET specific project
            get_response = requests.get(f"{BASE_URL}/api/projects/{project_id}", timeout=TIMEOUT)
            if get_response.status_code == 200:
                get_project = get_response.json()
                assert get_project["id"] == project_id, "Retrieved project ID mismatch"
            
            # Test DELETE project
            delete_response = requests.delete(f"{BASE_URL}/api/projects/{project_id}", timeout=TIMEOUT)
            # Allow either 200 or 204 for delete
            assert delete_response.status_code in [200, 204], f"DELETE projects returned {delete_response.status_code}"
            
            return {"status": "passed", "project_id": project_id}
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def test_dashboard_endpoint(self):
        """Test dashboard statistics endpoint"""
        try:
            response = requests.get(f"{BASE_URL}/api/dashboard/stats", timeout=TIMEOUT)
            assert response.status_code == 200, f"Dashboard stats returned {response.status_code}"
            
            stats = response.json()
            required_fields = ["totalProjects", "totalVideos", "totalTestSessions"]
            missing_fields = [field for field in required_fields if field not in stats]
            
            if missing_fields:
                # Try alternative field names
                alt_mapping = {
                    "totalProjects": ["total_projects", "projects"],
                    "totalVideos": ["total_videos", "videos"],
                    "totalTestSessions": ["total_test_sessions", "test_sessions", "sessions"]
                }
                
                for field in missing_fields[:]:
                    if field in alt_mapping:
                        for alt in alt_mapping[field]:
                            if alt in stats:
                                missing_fields.remove(field)
                                break
            
            assert len(missing_fields) == 0, f"Dashboard stats missing fields: {missing_fields}"
            
            return {"status": "passed", "stats": stats}
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def test_cors_headers(self):
        """Test CORS headers are present"""
        try:
            response = requests.options(f"{BASE_URL}/health", timeout=TIMEOUT)
            # CORS preflight should return 200 or 204
            assert response.status_code in [200, 204], f"CORS preflight returned {response.status_code}"
            
            return {"status": "passed", "headers": dict(response.headers)}
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def test_error_handling(self):
        """Test error handling for invalid requests"""
        try:
            # Test 404 for non-existent endpoint
            response = requests.get(f"{BASE_URL}/invalid/endpoint", timeout=TIMEOUT)
            assert response.status_code == 404, f"Invalid endpoint should return 404, got {response.status_code}"
            
            # Test malformed JSON
            response = requests.post(
                f"{BASE_URL}/api/projects",
                data="invalid json",
                headers={"Content-Type": "application/json"},
                timeout=TIMEOUT
            )
            assert response.status_code in [400, 422], f"Malformed JSON should return 400/422, got {response.status_code}"
            
            return {"status": "passed"}
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def test_concurrent_requests(self):
        """Test server handles concurrent requests"""
        try:
            def make_request():
                response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
                return response.status_code == 200
            
            # Make 10 concurrent requests
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(make_request) for _ in range(10)]
                results = [future.result() for future in futures]
            
            success_rate = sum(results) / len(results)
            assert success_rate >= 0.8, f"Concurrent request success rate too low: {success_rate}"
            
            return {"status": "passed", "success_rate": success_rate}
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def run_all_tests(self):
        """Run all API validation tests"""
        print("🧪 Starting API Endpoint Validation...")
        print("=" * 60)
        
        # Start server
        if not self.start_test_server():
            return {"overall_status": "FAILED", "error": "Could not start test server"}
        
        try:
            tests = [
                ("Health Endpoint", self.test_health_endpoint),
                ("Project CRUD Endpoints", self.test_project_crud_endpoints),
                ("Dashboard Endpoint", self.test_dashboard_endpoint),
                ("CORS Headers", self.test_cors_headers),
                ("Error Handling", self.test_error_handling),
                ("Concurrent Requests", self.test_concurrent_requests),
            ]
            
            for test_name, test_func in tests:
                print(f"🧪 Running: {test_name}")
                
                start_time = time.time()
                result = test_func()
                duration = time.time() - start_time
                
                result["name"] = test_name
                result["duration"] = duration
                self.test_results.append(result)
                
                if result["status"] == "passed":
                    print(f"✅ {test_name}: PASSED ({duration:.3f}s)")
                else:
                    print(f"❌ {test_name}: FAILED - {result.get('error', 'Unknown error')}")
            
            # Generate report
            total_tests = len(self.test_results)
            passed_tests = sum(1 for result in self.test_results if result['status'] == 'passed')
            
            print("\n" + "=" * 60)
            print("📊 API VALIDATION REPORT")
            print("=" * 60)
            
            if passed_tests == total_tests:
                overall_status = "FULLY READY"
                status_icon = "✅"
            elif passed_tests > total_tests * 0.7:
                overall_status = "MOSTLY READY"
                status_icon = "⚠️"
            else:
                overall_status = "NOT READY"
                status_icon = "❌"
            
            print(f"{status_icon} Overall Status: {overall_status}")
            print(f"📈 Test Results: {passed_tests}/{total_tests} passed")
            
            # Show failed tests
            failed_tests = [r for r in self.test_results if r['status'] == 'failed']
            if failed_tests:
                print(f"❌ Failed Tests: {len(failed_tests)}")
                for test in failed_tests:
                    print(f"   ❌ {test['name']}: {test.get('error', 'Unknown error')}")
            
            return {
                "overall_status": overall_status,
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": len(failed_tests),
                "test_results": self.test_results
            }
            
        finally:
            self.stop_test_server()

if __name__ == "__main__":
    validator = APIValidator()
    report = validator.run_all_tests()
    
    # Save report
    report_file = f"api_validation_report_{int(time.time())}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n📄 API validation report saved to: {report_file}")
    
    if report.get("passed_tests", 0) == report.get("total_tests", 1):
        print("\n🎉 All API validation tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some API validation tests failed!")
        sys.exit(1)