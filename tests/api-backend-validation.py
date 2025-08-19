#!/usr/bin/env python3
"""
Backend API Validation Script
Validates all API endpoints and data model alignments for production deployment
"""

import json
import requests
import sys
import time
from typing import Dict, Any, Optional

# Configuration
API_BASE_URL = "http://155.138.239.131:8000"
TEST_PROJECT_DATA = {
    "name": "API Validation Test Project",
    "description": "Test project for API validation",
    "cameraModel": "Test Camera v1.0",
    "cameraView": "Front-facing VRU",
    "signalType": "GPIO"
}

class APIValidator:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.test_results = []
        self.created_resources = []

    def log_test(self, test_name: str, success: bool, message: str = "", data: Optional[Dict] = None):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "data": data
        }
        self.test_results.append(result)
        print(f"{status} {test_name}: {message}")
        if data and not success:
            print(f"   Data: {json.dumps(data, indent=2)}")

    def test_cors_configuration(self) -> bool:
        """Test CORS configuration"""
        print("\n🔧 Testing CORS Configuration...")
        
        # Test OPTIONS request with various origins
        origins_to_test = [
            "http://155.138.239.131:3000",
            "https://155.138.239.131:3000",
            "http://localhost:3000",
        ]
        
        all_passed = True
        for origin in origins_to_test:
            try:
                response = self.session.options(
                    f"{self.base_url}/api/projects",
                    headers={
                        'Origin': origin,
                        'Access-Control-Request-Method': 'GET',
                        'Access-Control-Request-Headers': 'Content-Type'
                    }
                )
                
                cors_headers = {
                    'access-control-allow-origin': response.headers.get('access-control-allow-origin'),
                    'access-control-allow-methods': response.headers.get('access-control-allow-methods'),
                    'access-control-allow-headers': response.headers.get('access-control-allow-headers')
                }
                
                success = (
                    response.status_code == 200 and
                    cors_headers['access-control-allow-origin'] is not None
                )
                
                self.log_test(
                    f"CORS for {origin}",
                    success,
                    f"Status: {response.status_code}, Headers: {cors_headers}"
                )
                
                if not success:
                    all_passed = False
                    
            except Exception as e:
                self.log_test(f"CORS for {origin}", False, f"Exception: {str(e)}")
                all_passed = False
        
        return all_passed

    def test_health_check(self) -> bool:
        """Test health check endpoint"""
        print("\n💓 Testing Health Check...")
        
        try:
            response = self.session.get(f"{self.base_url}/health")
            success = response.status_code == 200
            data = response.json() if success else None
            
            self.log_test(
                "Health Check",
                success,
                f"Status: {response.status_code}",
                data
            )
            return success
            
        except Exception as e:
            self.log_test("Health Check", False, f"Exception: {str(e)}")
            return False

    def test_dashboard_stats(self) -> bool:
        """Test dashboard stats endpoint and field format"""
        print("\n📊 Testing Dashboard Stats...")
        
        try:
            response = self.session.get(f"{self.base_url}/api/dashboard/stats")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                expected_fields = [
                    "projectCount", "videoCount", "testCount", 
                    "averageAccuracy", "activeTests", "totalDetections"
                ]
                
                missing_fields = [field for field in expected_fields if field not in data]
                has_correct_format = len(missing_fields) == 0
                
                self.log_test(
                    "Dashboard Stats Format",
                    has_correct_format,
                    f"Missing fields: {missing_fields}" if missing_fields else "All fields present",
                    data
                )
                
                return success and has_correct_format
            else:
                self.log_test("Dashboard Stats", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Dashboard Stats", False, f"Exception: {str(e)}")
            return False

    def test_project_crud(self) -> bool:
        """Test project CRUD operations and field format"""
        print("\n🏗️ Testing Project CRUD Operations...")
        
        project_id = None
        try:
            # Create project
            response = self.session.post(
                f"{self.base_url}/api/projects",
                json=TEST_PROJECT_DATA
            )
            
            create_success = response.status_code == 200
            if create_success:
                project_data = response.json()
                project_id = project_data.get("id")
                
                # Check field format
                expected_fields = ["id", "name", "cameraModel", "cameraView", "signalType", "createdAt"]
                missing_fields = [field for field in expected_fields if field not in project_data]
                
                format_correct = len(missing_fields) == 0
                self.log_test(
                    "Project Create Format",
                    format_correct,
                    f"Missing fields: {missing_fields}" if missing_fields else "All fields present",
                    project_data
                )
                
                if project_id:
                    self.created_resources.append(("project", project_id))
                    
                    # Test get project
                    get_response = self.session.get(f"{self.base_url}/api/projects/{project_id}")
                    get_success = get_response.status_code == 200
                    
                    self.log_test(
                        "Project Get",
                        get_success,
                        f"Status: {get_response.status_code}",
                        get_response.json() if get_success else None
                    )
                    
                    return create_success and format_correct and get_success
            else:
                self.log_test("Project Create", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Project CRUD", False, f"Exception: {str(e)}")
            return False

    def test_video_endpoints(self) -> bool:
        """Test video-related endpoints"""
        print("\n🎥 Testing Video Endpoints...")
        
        # First create a project for testing
        try:
            project_response = self.session.post(
                f"{self.base_url}/api/projects",
                json={**TEST_PROJECT_DATA, "name": "Video Test Project"}
            )
            
            if project_response.status_code != 200:
                self.log_test("Video Test Setup", False, "Could not create test project")
                return False
                
            project_id = project_response.json()["id"]
            self.created_resources.append(("project", project_id))
            
            # Test get videos for project
            videos_response = self.session.get(f"{self.base_url}/api/projects/{project_id}/videos")
            videos_success = videos_response.status_code == 200
            
            if videos_success:
                videos_data = videos_response.json()
                self.log_test(
                    "Get Project Videos",
                    True,
                    f"Found {len(videos_data)} videos",
                    {"count": len(videos_data), "sample": videos_data[:1] if videos_data else []}
                )
            else:
                self.log_test("Get Project Videos", False, f"Status: {videos_response.status_code}")
            
            return videos_success
            
        except Exception as e:
            self.log_test("Video Endpoints", False, f"Exception: {str(e)}")
            return False

    def test_error_handling(self) -> bool:
        """Test error handling and response formats"""
        print("\n🚨 Testing Error Handling...")
        
        try:
            # Test 404 error
            response = self.session.get(f"{self.base_url}/api/projects/nonexistent-id")
            error_404 = response.status_code == 404
            
            error_data = None
            if error_404:
                try:
                    error_data = response.json()
                except:
                    error_data = response.text
            
            self.log_test(
                "404 Error Format",
                error_404,
                f"Status: {response.status_code}",
                error_data
            )
            
            # Test validation error
            validation_response = self.session.post(
                f"{self.base_url}/api/projects",
                json={"invalid": "data"}
            )
            validation_error = validation_response.status_code in [400, 422]
            
            self.log_test(
                "Validation Error",
                validation_error,
                f"Status: {validation_response.status_code}"
            )
            
            return error_404 and validation_error
            
        except Exception as e:
            self.log_test("Error Handling", False, f"Exception: {str(e)}")
            return False

    def cleanup_resources(self):
        """Clean up created test resources"""
        print("\n🧹 Cleaning up test resources...")
        
        for resource_type, resource_id in reversed(self.created_resources):
            try:
                if resource_type == "project":
                    response = self.session.delete(f"{self.base_url}/api/projects/{resource_id}")
                    success = response.status_code in [200, 204]
                    print(f"{'✅' if success else '❌'} Cleaned up {resource_type}: {resource_id}")
            except Exception as e:
                print(f"❌ Failed to clean up {resource_type}: {resource_id} - {str(e)}")

    def run_all_tests(self) -> bool:
        """Run all validation tests"""
        print("🚀 Starting Backend API Validation...")
        print(f"Target API: {self.base_url}")
        print("=" * 60)
        
        test_methods = [
            self.test_health_check,
            self.test_cors_configuration,
            self.test_dashboard_stats,
            self.test_project_crud,
            self.test_video_endpoints,
            self.test_error_handling
        ]
        
        all_passed = True
        for test_method in test_methods:
            try:
                result = test_method()
                if not result:
                    all_passed = False
            except Exception as e:
                print(f"❌ Test {test_method.__name__} failed with exception: {str(e)}")
                all_passed = False
            
            time.sleep(0.5)  # Brief pause between tests
        
        # Generate summary report
        self.generate_summary_report(all_passed)
        
        return all_passed

    def generate_summary_report(self, all_passed: bool):
        """Generate a summary report"""
        print("\n" + "=" * 60)
        print("📋 VALIDATION SUMMARY REPORT")
        print("=" * 60)
        
        passed_tests = sum(1 for result in self.test_results if result["success"])
        total_tests = len(self.test_results)
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if not all_passed:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  • {result['test']}: {result['message']}")
        
        print(f"\n{'🎉 ALL TESTS PASSED - PRODUCTION READY!' if all_passed else '⚠️  SOME TESTS FAILED - NEEDS ATTENTION'}")
        
        # Save detailed results to file
        with open('/home/user/Testing/tests/api-validation-results.json', 'w') as f:
            json.dump({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "base_url": self.base_url,
                "summary": {
                    "total_tests": total_tests,
                    "passed": passed_tests,
                    "failed": total_tests - passed_tests,
                    "success_rate": passed_tests/total_tests*100,
                    "all_passed": all_passed
                },
                "detailed_results": self.test_results
            }, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: /home/user/Testing/tests/api-validation-results.json")

def main():
    """Main execution function"""
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
    else:
        api_url = API_BASE_URL
    
    print(f"🔍 Backend API Validation Script")
    print(f"Target API: {api_url}")
    
    validator = APIValidator(api_url)
    
    try:
        success = validator.run_all_tests()
        
        # Cleanup
        validator.cleanup_resources()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n⚠️  Validation interrupted by user")
        validator.cleanup_resources()
        sys.exit(2)
    except Exception as e:
        print(f"\n💥 Validation failed with unexpected error: {str(e)}")
        validator.cleanup_resources()
        sys.exit(3)

if __name__ == "__main__":
    main()