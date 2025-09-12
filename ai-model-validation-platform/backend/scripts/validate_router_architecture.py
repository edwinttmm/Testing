#!/usr/bin/env python3
"""
Router Architecture Validation Script
====================================

Validates the organized router architecture by testing:
1. All endpoints are accessible
2. Response formats are consistent  
3. Error handling works correctly
4. Authentication flows function properly
5. Database connections are properly managed

Usage:
    python scripts/validate_router_architecture.py
"""

import asyncio
import aiohttp
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List, Any
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RouterValidationSuite:
    """Comprehensive validation suite for the organized router architecture"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.test_results = {
            "passed": 0,
            "failed": 0,
            "errors": []
        }
        self.auth_token = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            headers = kwargs.get('headers', {})
            if self.auth_token and 'Authorization' not in headers:
                headers['Authorization'] = f"Bearer {self.auth_token}"
                kwargs['headers'] = headers
            
            async with self.session.request(method, url, **kwargs) as response:
                response_data = {
                    "status": response.status,
                    "headers": dict(response.headers),
                    "data": None,
                    "error": None
                }
                
                try:
                    response_data["data"] = await response.json()
                except:
                    response_data["data"] = await response.text()
                
                return response_data
                
        except Exception as e:
            return {
                "status": 0,
                "headers": {},
                "data": None,
                "error": str(e)
            }
    
    def assert_response(self, response: Dict[str, Any], expected_status: int, test_name: str):
        """Assert response meets expectations"""
        try:
            assert response["status"] == expected_status, f"Expected status {expected_status}, got {response['status']}"
            assert response["error"] is None, f"Unexpected error: {response['error']}"
            
            self.test_results["passed"] += 1
            logger.info(f"✅ {test_name} - PASSED")
            
        except AssertionError as e:
            self.test_results["failed"] += 1
            self.test_results["errors"].append(f"{test_name}: {str(e)}")
            logger.error(f"❌ {test_name} - FAILED: {str(e)}")
    
    async def test_health_endpoints(self):
        """Test all health check endpoints"""
        logger.info("🏥 Testing health check endpoints...")
        
        health_endpoints = [
            ("/health", "Main health check"),
            ("/health/simple", "Simple health check"),
            ("/api/projects/health", "Projects router health"),
            ("/api/videos/health", "Videos router health"),
            ("/api/test-sessions/health", "Test sessions router health"),
            ("/auth/health", "Auth router health"),
            ("/api/dashboard/health", "Dashboard router health")
        ]
        
        for endpoint, description in health_endpoints:
            response = await self.make_request("GET", endpoint)
            self.assert_response(response, 200, description)
    
    async def test_root_endpoints(self):
        """Test root and info endpoints"""
        logger.info("🏠 Testing root endpoints...")
        
        # Root endpoint
        response = await self.make_request("GET", "/")
        self.assert_response(response, 200, "Root endpoint")
        
        # API info endpoint
        response = await self.make_request("GET", "/api/info")
        self.assert_response(response, 200, "API info endpoint")
    
    async def test_projects_router(self):
        """Test projects router endpoints"""
        logger.info("📁 Testing projects router...")
        
        # List projects
        response = await self.make_request("GET", "/api/projects")
        self.assert_response(response, 200, "List projects")
        
        # Create project test data
        project_data = {
            "name": f"Test Project {int(time.time())}",
            "description": "Validation test project",
            "camera_model": "Test Camera",
            "camera_view": "Front",
            "signal_type": "GPIO"
        }
        
        # Create project (may fail without auth, that's expected)
        response = await self.make_request("POST", "/api/projects", json=project_data)
        if response["status"] in [200, 201, 401, 403]:
            self.test_results["passed"] += 1
            logger.info("✅ Create project endpoint responds correctly")
        else:
            self.test_results["failed"] += 1
            logger.error(f"❌ Create project endpoint failed: {response}")
    
    async def test_videos_router(self):
        """Test videos router endpoints"""
        logger.info("🎥 Testing videos router...")
        
        # List videos
        response = await self.make_request("GET", "/api/videos")
        self.assert_response(response, 200, "List videos")
        
        # Test video upload endpoint exists (without actual file)
        response = await self.make_request("POST", "/api/videos")
        # Should fail with validation error, not 404
        if response["status"] in [400, 422, 401, 403]:
            self.test_results["passed"] += 1
            logger.info("✅ Video upload endpoint exists and validates input")
        else:
            self.test_results["failed"] += 1
            logger.error(f"❌ Video upload endpoint unexpected response: {response}")
    
    async def test_test_sessions_router(self):
        """Test test sessions router endpoints"""
        logger.info("🧪 Testing test sessions router...")
        
        # List test sessions
        response = await self.make_request("GET", "/api/test-sessions")
        self.assert_response(response, 200, "List test sessions")
        
        # Test detection events endpoint
        response = await self.make_request("POST", "/api/test-sessions/detection-events")
        # Should fail with validation error, not 404
        if response["status"] in [400, 422, 401, 403]:
            self.test_results["passed"] += 1
            logger.info("✅ Detection events endpoint exists and validates input")
        else:
            self.test_results["failed"] += 1
            logger.error(f"❌ Detection events endpoint unexpected response: {response}")
    
    async def test_auth_router(self):
        """Test authentication router endpoints"""
        logger.info("🔐 Testing authentication router...")
        
        # Test registration endpoint structure
        response = await self.make_request("POST", "/auth/register")
        if response["status"] in [400, 422]:
            self.test_results["passed"] += 1
            logger.info("✅ Registration endpoint exists and validates input")
        else:
            self.test_results["failed"] += 1
            logger.error(f"❌ Registration endpoint unexpected response: {response}")
        
        # Test login endpoint structure
        response = await self.make_request("POST", "/auth/login")
        if response["status"] in [400, 422, 401]:
            self.test_results["passed"] += 1
            logger.info("✅ Login endpoint exists and validates input")
        else:
            self.test_results["failed"] += 1
            logger.error(f"❌ Login endpoint unexpected response: {response}")
        
        # Test token verification (should fail without token)
        response = await self.make_request("POST", "/auth/verify-token")
        if response["status"] in [401, 403, 422]:
            self.test_results["passed"] += 1
            logger.info("✅ Token verification endpoint exists and requires auth")
        else:
            self.test_results["failed"] += 1
            logger.error(f"❌ Token verification unexpected response: {response}")
    
    async def test_dashboard_router(self):
        """Test dashboard router endpoints"""
        logger.info("📊 Testing dashboard router...")
        
        # Basic dashboard stats
        response = await self.make_request("GET", "/api/dashboard/stats")
        self.assert_response(response, 200, "Dashboard basic stats")
        
        # Enhanced dashboard stats
        response = await self.make_request("GET", "/api/dashboard/stats/enhanced")
        self.assert_response(response, 200, "Dashboard enhanced stats")
        
        # System health
        response = await self.make_request("GET", "/api/dashboard/health/system")
        self.assert_response(response, 200, "Dashboard system health")
        
        # Database health
        response = await self.make_request("GET", "/api/dashboard/health/database")
        self.assert_response(response, 200, "Dashboard database health")
    
    async def test_performance(self):
        """Test API performance"""
        logger.info("⚡ Testing API performance...")
        
        # Test response times for key endpoints
        key_endpoints = [
            "/health",
            "/api/dashboard/stats",
            "/api/projects",
            "/api/videos",
            "/api/test-sessions"
        ]
        
        performance_results = {}
        
        for endpoint in key_endpoints:
            start_time = time.time()
            response = await self.make_request("GET", endpoint)
            end_time = time.time()
            
            response_time = end_time - start_time
            performance_results[endpoint] = response_time
            
            if response_time < 2.0:  # Less than 2 seconds
                self.test_results["passed"] += 1
                logger.info(f"✅ {endpoint} performance OK ({response_time:.3f}s)")
            else:
                self.test_results["failed"] += 1
                self.test_results["errors"].append(f"Slow response: {endpoint} took {response_time:.3f}s")
                logger.warning(f"⚠️ {endpoint} slow response ({response_time:.3f}s)")
        
        return performance_results
    
    async def test_error_handling(self):
        """Test error handling consistency"""
        logger.info("⚠️ Testing error handling...")
        
        # Test 404 errors
        non_existent_endpoints = [
            "/api/projects/non-existent-id",
            "/api/videos/non-existent-id", 
            "/api/test-sessions/non-existent-id"
        ]
        
        for endpoint in non_existent_endpoints:
            response = await self.make_request("GET", endpoint)
            if response["status"] == 404:
                self.test_results["passed"] += 1
                logger.info(f"✅ 404 handling correct for {endpoint}")
            else:
                self.test_results["failed"] += 1
                logger.error(f"❌ Unexpected status for {endpoint}: {response['status']}")
    
    async def run_validation_suite(self):
        """Run the complete validation suite"""
        logger.info("🚀 Starting Router Architecture Validation Suite")
        logger.info(f"Testing against: {self.base_url}")
        
        start_time = time.time()
        
        # Run all test suites
        await self.test_health_endpoints()
        await self.test_root_endpoints()
        await self.test_projects_router()
        await self.test_videos_router()
        await self.test_test_sessions_router()
        await self.test_auth_router()
        await self.test_dashboard_router()
        performance_results = await self.test_performance()
        await self.test_error_handling()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Generate report
        await self.generate_report(performance_results, total_time)
    
    async def generate_report(self, performance_results: Dict[str, float], total_time: float):
        """Generate validation report"""
        total_tests = self.test_results["passed"] + self.test_results["failed"]
        success_rate = (self.test_results["passed"] / total_tests * 100) if total_tests > 0 else 0
        
        report = {
            "validation_summary": {
                "timestamp": datetime.utcnow().isoformat(),
                "base_url": self.base_url,
                "total_tests": total_tests,
                "passed": self.test_results["passed"],
                "failed": self.test_results["failed"],
                "success_rate": f"{success_rate:.1f}%",
                "total_time": f"{total_time:.2f}s"
            },
            "performance_results": performance_results,
            "errors": self.test_results["errors"]
        }
        
        # Save report
        report_filename = f"validation_report_{int(time.time())}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("🎯 ROUTER ARCHITECTURE VALIDATION SUMMARY")
        logger.info("="*60)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {self.test_results['passed']} ✅")
        logger.info(f"Failed: {self.test_results['failed']} ❌")
        logger.info(f"Success Rate: {success_rate:.1f}%")
        logger.info(f"Total Time: {total_time:.2f}s")
        logger.info(f"Report saved: {report_filename}")
        
        if self.test_results["errors"]:
            logger.info("\n🚨 ERRORS:")
            for error in self.test_results["errors"]:
                logger.error(f"  - {error}")
        
        if success_rate >= 90:
            logger.info("\n🎉 Router architecture validation SUCCESSFUL!")
            return True
        else:
            logger.error("\n💥 Router architecture validation FAILED!")
            return False

async def main():
    """Main validation function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate router architecture")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL to test")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    async with RouterValidationSuite(args.url) as validator:
        success = await validator.run_validation_suite()
        
        if success:
            sys.exit(0)
        else:
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())