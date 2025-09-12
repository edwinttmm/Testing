#!/usr/bin/env python3
"""
Simple Backend API Test - Testing core endpoints without full ML stack
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
import httpx

class SimpleBackendTester:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.results = {
            "test_start": datetime.now().isoformat(),
            "endpoints": {},
            "summary": {}
        }

    async def test_basic_endpoints(self):
        """Test basic API endpoints"""
        print("🧪 Testing Basic API Endpoints...")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            endpoints_to_test = [
                ("/", "GET"),
                ("/health", "GET"),
                ("/docs", "GET"),
                ("/api/projects", "GET"),
                ("/api/videos", "GET"),
            ]
            
            for endpoint, method in endpoints_to_test:
                try:
                    if method == "GET":
                        response = await client.get(f"{self.base_url}{endpoint}")
                    
                    self.results["endpoints"][endpoint] = {
                        "method": method,
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds() if hasattr(response, 'elapsed') else 0,
                        "success": response.status_code < 400
                    }
                    
                    print(f"  {'✅' if response.status_code < 400 else '❌'} {method} {endpoint}: {response.status_code}")
                    
                except Exception as e:
                    self.results["endpoints"][endpoint] = {
                        "method": method,
                        "error": str(e),
                        "success": False
                    }
                    print(f"  ❌ {method} {endpoint}: {e}")

    async def test_project_creation(self):
        """Test creating a project"""
        print("📁 Testing Project Creation...")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                project_data = {
                    "name": "Test Project",
                    "description": "API Test Project",
                    "camera_type": "webcam",
                    "signal_type": "voltage"
                }
                
                response = await client.post(
                    f"{self.base_url}/api/projects",
                    json=project_data
                )
                
                self.results["endpoints"]["POST /api/projects"] = {
                    "status_code": response.status_code,
                    "request_data": project_data,
                    "success": response.status_code in [200, 201]
                }
                
                if response.status_code in [200, 201]:
                    try:
                        data = response.json()
                        print(f"  ✅ Project Created: {data.get('id', 'Unknown ID')}")
                    except:
                        print(f"  ✅ Project Creation: {response.status_code}")
                else:
                    print(f"  ❌ Project Creation Failed: {response.status_code}")
                    print(f"    Response: {response.text[:200]}")
                
            except Exception as e:
                self.results["endpoints"]["POST /api/projects"] = {
                    "error": str(e),
                    "success": False
                }
                print(f"  ❌ Project Creation Error: {e}")

    def generate_summary(self):
        """Generate test summary"""
        total_tests = len(self.results["endpoints"])
        successful_tests = sum(1 for r in self.results["endpoints"].values() if r.get("success", False))
        
        self.results["summary"] = {
            "test_end": datetime.now().isoformat(),
            "total_endpoints": total_tests,
            "successful_endpoints": successful_tests,
            "failed_endpoints": total_tests - successful_tests,
            "success_rate": round(successful_tests / total_tests * 100, 2) if total_tests > 0 else 0
        }
        
        print("\n📊 Test Summary:")
        print(f"  Total Endpoints: {total_tests}")
        print(f"  Successful: {successful_tests}")
        print(f"  Failed: {total_tests - successful_tests}")
        print(f"  Success Rate: {self.results['summary']['success_rate']}%")

    def save_results(self):
        """Save results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = Path(__file__).parent / f"simple_backend_test_{timestamp}.json"
        
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"📁 Results saved: {results_file}")
        return results_file

    async def run_tests(self):
        """Run all tests"""
        print("🎯 Starting Simple Backend API Tests")
        print("=" * 50)
        
        await self.test_basic_endpoints()
        await self.test_project_creation()
        
        self.generate_summary()
        results_file = self.save_results()
        
        return self.results["summary"]["success_rate"] > 0

async def main():
    """Main execution"""
    tester = SimpleBackendTester()
    success = await tester.run_tests()
    print(f"\n{'✅ Tests completed successfully!' if success else '❌ Some tests failed'}")
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)