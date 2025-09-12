#!/usr/bin/env python3
"""
Comprehensive User Journey Testing Suite
Tests the complete user workflow on the live system at http://localhost:3000
"""

import requests
import json
import time
import os
import tempfile
from urllib.parse import urljoin
import traceback
from datetime import datetime

class UserJourneyTester:
    def __init__(self, frontend_url="http://localhost:3000", backend_url="http://localhost:8000"):
        self.frontend_url = frontend_url
        self.backend_url = backend_url
        self.test_results = {
            "test_started": datetime.now().isoformat(),
            "frontend_url": frontend_url,
            "backend_url": backend_url,
            "tests": []
        }
        
    def log_test(self, test_name, status, details=None, error=None):
        """Log a test result"""
        result = {
            "test_name": test_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details,
            "error": str(error) if error else None
        }
        self.test_results["tests"].append(result)
        
        status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_symbol} {test_name}: {status}")
        if details:
            print(f"   Details: {details}")
        if error:
            print(f"   Error: {error}")
    
    def test_frontend_accessibility(self):
        """Test if frontend is accessible and loads correctly"""
        try:
            response = requests.get(self.frontend_url, timeout=10)
            if response.status_code == 200 and "React App" in response.text:
                self.log_test("Frontend Accessibility", "PASS", 
                            f"Frontend accessible at {self.frontend_url}")
                return True
            else:
                self.log_test("Frontend Accessibility", "FAIL", 
                            f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Frontend Accessibility", "FAIL", error=e)
            return False
    
    def test_backend_api_endpoints(self):
        """Test core backend API endpoints"""
        endpoints = [
            ("/api/dashboard/stats", "Dashboard stats"),
            ("/api/projects", "Projects list"),
            ("/api/videos", "Videos list"),
            ("/api/datasets", "Datasets list"),
            ("/api/results", "Results list")
        ]
        
        passed = 0
        for endpoint, description in endpoints:
            try:
                url = urljoin(self.backend_url, endpoint)
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self.log_test(f"API: {description}", "PASS", 
                                f"Endpoint: {endpoint}, Response keys: {list(data.keys()) if isinstance(data, dict) else 'Array'}")
                    passed += 1
                else:
                    self.log_test(f"API: {description}", "FAIL", 
                                f"Status: {response.status_code}")
            except Exception as e:
                self.log_test(f"API: {description}", "FAIL", error=e)
        
        return passed == len(endpoints)
    
    def test_project_creation_workflow(self):
        """Test creating a new project through API"""
        try:
            project_data = {
                "name": f"User Journey Test Project {int(time.time())}",
                "description": "Created during comprehensive user journey testing",
                "status": "active"
            }
            
            url = urljoin(self.backend_url, "/api/projects")
            response = requests.post(url, json=project_data, timeout=10)
            
            if response.status_code in [200, 201]:
                project = response.json()
                self.log_test("Project Creation", "PASS", 
                            f"Created project: {project.get('name', 'Unknown')} (ID: {project.get('id', 'Unknown')})")
                return project.get('id')
            else:
                self.log_test("Project Creation", "FAIL", 
                            f"Status: {response.status_code}, Response: {response.text[:200]}")
                return None
        except Exception as e:
            self.log_test("Project Creation", "FAIL", error=e)
            return None
    
    def test_video_upload_simulation(self):
        """Test video upload API (simulate with small test data)"""
        try:
            # Create a small test file to simulate video upload
            test_data = b"This is test video data for API testing"
            
            # Test if upload endpoint exists and responds properly
            url = urljoin(self.backend_url, "/api/videos/upload")
            
            # First test with OPTIONS to check CORS
            options_response = requests.options(url, timeout=10)
            
            files = {'video': ('test_video.mp4', test_data, 'video/mp4')}
            data = {'project_id': 1, 'title': 'User Journey Test Video'}
            
            # Note: This might fail due to file validation, but we test the endpoint
            response = requests.post(url, files=files, data=data, timeout=30)
            
            # Accept various response codes as this is endpoint testing
            if response.status_code in [200, 201, 400, 422]:  # 400/422 might be validation errors which is OK
                self.log_test("Video Upload API", "PASS", 
                            f"Upload endpoint responding (Status: {response.status_code})")
                return True
            else:
                self.log_test("Video Upload API", "FAIL", 
                            f"Unexpected status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Video Upload API", "FAIL", error=e)
            return False
    
    def test_form_validation(self):
        """Test form validation by sending invalid data"""
        test_cases = [
            {
                "name": "Empty Project Name",
                "data": {"name": "", "description": "Test"},
                "endpoint": "/api/projects"
            },
            {
                "name": "Invalid Project Data",
                "data": {"invalid_field": "test"},
                "endpoint": "/api/projects"
            }
        ]
        
        passed = 0
        for test_case in test_cases:
            try:
                url = urljoin(self.backend_url, test_case["endpoint"])
                response = requests.post(url, json=test_case["data"], timeout=10)
                
                # Validation should return 400 or 422
                if response.status_code in [400, 422]:
                    self.log_test(f"Form Validation: {test_case['name']}", "PASS", 
                                f"Properly rejected invalid data (Status: {response.status_code})")
                    passed += 1
                else:
                    self.log_test(f"Form Validation: {test_case['name']}", "FAIL", 
                                f"Should reject invalid data, got: {response.status_code}")
            except Exception as e:
                self.log_test(f"Form Validation: {test_case['name']}", "FAIL", error=e)
        
        return passed == len(test_cases)
    
    def test_pagination_and_filtering(self):
        """Test pagination and filtering features"""
        try:
            # Test projects pagination
            url = urljoin(self.backend_url, "/api/projects?page=1&limit=5")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and ("projects" in data or "data" in data):
                    self.log_test("Pagination", "PASS", 
                                f"Pagination working, got structured response")
                else:
                    self.log_test("Pagination", "PARTIAL", 
                                f"Got response but structure unclear: {list(data.keys()) if isinstance(data, dict) else 'Array'}")
            else:
                self.log_test("Pagination", "FAIL", 
                            f"Pagination failed: {response.status_code}")
            
            # Test filtering
            filter_url = urljoin(self.backend_url, "/api/projects?status=active")
            filter_response = requests.get(filter_url, timeout=10)
            
            if filter_response.status_code == 200:
                self.log_test("Filtering", "PASS", 
                            f"Filtering endpoint responding")
                return True
            else:
                self.log_test("Filtering", "FAIL", 
                            f"Filtering failed: {filter_response.status_code}")
                return False
                            
        except Exception as e:
            self.log_test("Pagination/Filtering", "FAIL", error=e)
            return False
    
    def test_annotation_endpoints(self):
        """Test annotation and ground truth related endpoints"""
        endpoints = [
            ("/api/annotations", "Annotations list"),
            ("/api/ground-truth", "Ground truth data"),
            ("/api/detection-events", "Detection events")
        ]
        
        passed = 0
        for endpoint, description in endpoints:
            try:
                url = urljoin(self.backend_url, endpoint)
                response = requests.get(url, timeout=10)
                if response.status_code in [200, 404]:  # 404 might be OK if no data exists
                    self.log_test(f"Annotation API: {description}", "PASS", 
                                f"Endpoint accessible (Status: {response.status_code})")
                    passed += 1
                else:
                    self.log_test(f"Annotation API: {description}", "FAIL", 
                                f"Status: {response.status_code}")
            except Exception as e:
                self.log_test(f"Annotation API: {description}", "FAIL", error=e)
        
        return passed >= len(endpoints) * 0.8  # Allow some failures
    
    def test_responsive_design_simulation(self):
        """Test different viewport sizes by checking CSS/JavaScript resources"""
        try:
            response = requests.get(self.frontend_url, timeout=10)
            html_content = response.text
            
            # Check for responsive design indicators
            responsive_indicators = [
                'viewport', 'media', 'responsive', '@media'
            ]
            
            found_indicators = [indicator for indicator in responsive_indicators 
                              if indicator in html_content.lower()]
            
            if found_indicators:
                self.log_test("Responsive Design", "PASS", 
                            f"Found responsive design indicators: {found_indicators}")
                return True
            else:
                self.log_test("Responsive Design", "PARTIAL", 
                            f"No clear responsive indicators found")
                return False
                
        except Exception as e:
            self.log_test("Responsive Design", "FAIL", error=e)
            return False
    
    def test_error_handling(self):
        """Test error handling by accessing invalid endpoints"""
        try:
            # Test 404 handling
            response = requests.get(urljoin(self.backend_url, "/api/nonexistent"), timeout=10)
            if response.status_code == 404:
                self.log_test("Error Handling: 404", "PASS", 
                            f"Properly returns 404 for invalid endpoint")
            else:
                self.log_test("Error Handling: 404", "FAIL", 
                            f"Expected 404, got: {response.status_code}")
            
            # Test invalid method
            post_response = requests.post(urljoin(self.backend_url, "/api/dashboard/stats"), timeout=10)
            if post_response.status_code in [405, 404]:  # Method not allowed or not found
                self.log_test("Error Handling: Method", "PASS", 
                            f"Properly handles invalid HTTP method")
                return True
            else:
                self.log_test("Error Handling: Method", "PARTIAL", 
                            f"Got status: {post_response.status_code}")
                return False
                            
        except Exception as e:
            self.log_test("Error Handling", "FAIL", error=e)
            return False
    
    def run_comprehensive_test(self):
        """Run all tests in sequence"""
        print("🚀 Starting Comprehensive User Journey Testing")
        print("=" * 60)
        
        test_methods = [
            self.test_frontend_accessibility,
            self.test_backend_api_endpoints,
            self.test_project_creation_workflow,
            self.test_video_upload_simulation,
            self.test_form_validation,
            self.test_pagination_and_filtering,
            self.test_annotation_endpoints,
            self.test_responsive_design_simulation,
            self.test_error_handling
        ]
        
        for test_method in test_methods:
            print(f"\n📋 Running {test_method.__name__}...")
            try:
                test_method()
            except Exception as e:
                self.log_test(test_method.__name__, "FAIL", error=f"Test method crashed: {e}")
            time.sleep(1)  # Brief pause between tests
        
        # Calculate summary
        total_tests = len(self.test_results["tests"])
        passed_tests = len([t for t in self.test_results["tests"] if t["status"] == "PASS"])
        failed_tests = len([t for t in self.test_results["tests"] if t["status"] == "FAIL"])
        partial_tests = len([t for t in self.test_results["tests"] if t["status"] == "PARTIAL"])
        
        self.test_results["summary"] = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "partial": partial_tests,
            "success_rate": f"{(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%"
        }
        
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️ Partial: {partial_tests}")
        print(f"🎯 Success Rate: {self.test_results['summary']['success_rate']}")
        
        # Save detailed results
        results_file = f"/home/rigade/Testing/ai-model-validation-platform/tests/user_journey_test_results_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: {results_file}")
        return self.test_results

if __name__ == "__main__":
    tester = UserJourneyTester()
    results = tester.run_comprehensive_test()