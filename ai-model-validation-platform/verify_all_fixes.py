#!/usr/bin/env python3
"""
Comprehensive Verification Test for All Root Cause Fixes
Tests all implemented fixes to ensure they work correctly
"""

import requests
import json
import sys
import time
from typing import Dict, List, Any

class FixVerificationTest:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results: List[Dict[str, Any]] = []
        self.passed_tests = 0
        self.failed_tests = 0
    
    def log_test(self, test_name: str, success: bool, message: str, details: Any = None):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "details": details,
            "timestamp": time.time()
        }
        self.test_results.append(result)
        
        if success:
            self.passed_tests += 1
            print(f"✅ {test_name}: {message}")
        else:
            self.failed_tests += 1
            print(f"❌ {test_name}: {message}")
            if details:
                print(f"   Details: {details}")
    
    def test_health_endpoint(self):
        """Test basic health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "Health Endpoint",
                    True,
                    "Health check passed",
                    f"Status: {data.get('status', 'unknown')}"
                )
            else:
                self.log_test(
                    "Health Endpoint",
                    False,
                    f"Health check returned {response.status_code}",
                    response.text
                )
        except Exception as e:
            self.log_test("Health Endpoint", False, "Health check failed", str(e))
    
    def test_system_status(self):
        """Test comprehensive system status"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/system/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                fixes = data.get("fixes_applied", {})
                self.log_test(
                    "System Status",
                    True,
                    f"System status OK, {len(fixes)} fix categories reported",
                    f"Version: {data.get('version', 'unknown')}"
                )
            else:
                self.log_test(
                    "System Status",
                    False,
                    f"System status returned {response.status_code}",
                    response.text
                )
        except Exception as e:
            self.log_test("System Status", False, "System status check failed", str(e))
    
    def test_form_validation(self):
        """Test form validation fixes"""
        # Test empty project name rejection
        try:
            invalid_project = {
                "name": "",  # Empty name should be rejected
                "cameraModel": "Test Camera",
                "cameraView": "Front-facing VRU",
                "signalType": "GPIO"
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/projects/enhanced",
                json=invalid_project,
                timeout=5
            )
            
            if response.status_code == 422:  # Validation error expected
                self.log_test(
                    "Form Validation - Empty Name",
                    True,
                    "Empty project name correctly rejected",
                    "422 Validation Error as expected"
                )
            else:
                self.log_test(
                    "Form Validation - Empty Name",
                    False,
                    f"Empty name not rejected, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("Form Validation - Empty Name", False, "Form validation test failed", str(e))
        
        # Test valid project creation
        try:
            valid_project = {
                "name": "Test Project with Valid Name",
                "description": "Test project for validation",
                "cameraModel": "Test Camera Model",
                "cameraView": "Front-facing VRU",
                "signalType": "GPIO"
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/projects/enhanced",
                json=valid_project,
                timeout=5
            )
            
            if response.status_code == 201:
                data = response.json()
                self.log_test(
                    "Form Validation - Valid Project",
                    True,
                    "Valid project created successfully",
                    f"Project ID: {data.get('id', 'unknown')}"
                )
            else:
                self.log_test(
                    "Form Validation - Valid Project",
                    False,
                    f"Valid project creation failed, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("Form Validation - Valid Project", False, "Valid project test failed", str(e))
    
    def test_annotation_endpoints(self):
        """Test annotation CRUD endpoints"""
        try:
            # Test GET annotations (should work even with empty database)
            response = requests.get(f"{self.base_url}/api/v1/annotations", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "Annotation Endpoints - List",
                    True,
                    "Annotation list endpoint working",
                    f"Returned {len(data)} annotations"
                )
            else:
                self.log_test(
                    "Annotation Endpoints - List",
                    False,
                    f"Annotation list failed, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("Annotation Endpoints - List", False, "Annotation list test failed", str(e))
        
        # Test annotation stats
        try:
            response = requests.get(f"{self.base_url}/api/v1/annotations/stats/summary", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "Annotation Endpoints - Stats",
                    True,
                    "Annotation stats endpoint working",
                    f"Total: {data.get('total_annotations', 0)}"
                )
            else:
                self.log_test(
                    "Annotation Endpoints - Stats",
                    False,
                    f"Annotation stats failed, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("Annotation Endpoints - Stats", False, "Annotation stats test failed", str(e))
    
    def test_datasets_endpoints(self):
        """Test datasets API endpoints"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/datasets", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "Datasets Endpoints",
                    True,
                    "Datasets list endpoint working",
                    f"Returned {len(data)} datasets"
                )
            else:
                self.log_test(
                    "Datasets Endpoints",
                    False,
                    f"Datasets list failed, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("Datasets Endpoints", False, "Datasets test failed", str(e))
    
    def test_results_endpoints(self):
        """Test results API endpoints"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/results", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "Results Endpoints",
                    True,
                    "Results list endpoint working",
                    f"Returned {len(data)} results"
                )
            else:
                self.log_test(
                    "Results Endpoints",
                    False,
                    f"Results list failed, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("Results Endpoints", False, "Results test failed", str(e))
    
    def test_ground_truth_endpoints(self):
        """Test ground truth CRUD endpoints"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/ground-truth", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "Ground Truth Endpoints",
                    True,
                    "Ground truth list endpoint working",
                    f"Returned {len(data)} objects"
                )
            else:
                self.log_test(
                    "Ground Truth Endpoints",
                    False,
                    f"Ground truth list failed, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("Ground Truth Endpoints", False, "Ground truth test failed", str(e))
    
    def test_404_error_handling(self):
        """Test proper 404 error handling"""
        try:
            # Test non-existent annotation
            response = requests.get(
                f"{self.base_url}/api/v1/annotations/non-existent-id",
                timeout=5
            )
            
            if response.status_code == 404:
                data = response.json()
                if "error_code" in data.get("detail", {}):
                    self.log_test(
                        "404 Error Handling",
                        True,
                        "Proper 404 error format returned",
                        f"Error code: {data['detail'].get('error_code', 'unknown')}"
                    )
                else:
                    self.log_test(
                        "404 Error Handling",
                        False,
                        "404 returned but wrong format",
                        data
                    )
            else:
                self.log_test(
                    "404 Error Handling",
                    False,
                    f"Expected 404, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("404 Error Handling", False, "404 error test failed", str(e))
    
    def test_security_headers(self):
        """Test security headers implementation"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            
            security_headers = [
                "X-Content-Type-Options",
                "X-Frame-Options", 
                "X-XSS-Protection",
                "Referrer-Policy"
            ]
            
            found_headers = []
            for header in security_headers:
                if header in response.headers:
                    found_headers.append(header)
            
            if len(found_headers) >= 3:  # At least 3 security headers
                self.log_test(
                    "Security Headers",
                    True,
                    f"Security headers implemented",
                    f"Found: {', '.join(found_headers)}"
                )
            else:
                self.log_test(
                    "Security Headers",
                    False,
                    "Insufficient security headers",
                    f"Found only: {', '.join(found_headers)}"
                )
                
        except Exception as e:
            self.log_test("Security Headers", False, "Security headers test failed", str(e))
    
    def test_api_documentation(self):
        """Test API documentation endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/docs/endpoints", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                endpoints = data.get("endpoints", {})
                self.log_test(
                    "API Documentation",
                    True,
                    "API documentation endpoint working",
                    f"Documented {len(endpoints)} endpoint categories"
                )
            else:
                self.log_test(
                    "API Documentation",
                    False,
                    f"API docs failed, got {response.status_code}",
                    response.text
                )
                
        except Exception as e:
            self.log_test("API Documentation", False, "API documentation test failed", str(e))
    
    def run_all_tests(self):
        """Run all verification tests"""
        print("🚀 Starting comprehensive root cause fixes verification...")
        print(f"Testing against: {self.base_url}")
        print("-" * 60)
        
        # Run all tests
        self.test_health_endpoint()
        self.test_system_status()
        self.test_form_validation()
        self.test_annotation_endpoints()
        self.test_datasets_endpoints()
        self.test_results_endpoints()
        self.test_ground_truth_endpoints()
        self.test_404_error_handling()
        self.test_security_headers()
        self.test_api_documentation()
        
        # Print summary
        print("-" * 60)
        print(f"📊 TEST SUMMARY")
        print(f"Total Tests: {self.passed_tests + self.failed_tests}")
        print(f"✅ Passed: {self.passed_tests}")
        print(f"❌ Failed: {self.failed_tests}")
        
        success_rate = (self.passed_tests / (self.passed_tests + self.failed_tests)) * 100
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if self.failed_tests == 0:
            print("\n🎉 ALL ROOT CAUSE FIXES VERIFIED SUCCESSFULLY!")
            print("✅ Platform is ready for production use")
        else:
            print(f"\n⚠️  {self.failed_tests} tests failed - review implementation")
        
        return self.failed_tests == 0
    
    def save_results(self, filename: str = "verification_results.json"):
        """Save test results to file"""
        with open(filename, 'w') as f:
            json.dump({
                "summary": {
                    "total_tests": self.passed_tests + self.failed_tests,
                    "passed": self.passed_tests,
                    "failed": self.failed_tests,
                    "success_rate": (self.passed_tests / (self.passed_tests + self.failed_tests)) * 100,
                    "timestamp": time.time()
                },
                "test_results": self.test_results
            }, f, indent=2)
        
        print(f"📄 Results saved to: {filename}")

def main():
    """Main function to run verification tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify all root cause fixes")
    parser.add_argument("--url", default="http://localhost:8000", 
                       help="Base URL for testing (default: http://localhost:8000)")
    parser.add_argument("--save-results", action="store_true",
                       help="Save test results to JSON file")
    
    args = parser.parse_args()
    
    # Initialize and run tests
    verifier = FixVerificationTest(args.url)
    success = verifier.run_all_tests()
    
    if args.save_results:
        verifier.save_results()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()