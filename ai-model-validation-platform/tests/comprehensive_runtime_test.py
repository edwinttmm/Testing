#!/usr/bin/env python3
"""
Comprehensive Runtime Analysis and Testing Suite
Tests all system components, APIs, and integrations
"""

import asyncio
import aiohttp
import json
import time
import sys
from pathlib import Path

class RuntimeTester:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.results = {
            "api_tests": {},
            "performance_metrics": {},
            "errors": [],
            "warnings": [],
            "system_status": "unknown"
        }
    
    async def test_health_endpoints(self):
        """Test all health and status endpoints"""
        endpoints = [
            "/health",
            "/api/health", 
            "/api/dashboard/stats"
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    start_time = time.time()
                    async with session.get(f"{self.base_url}{endpoint}") as response:
                        response_time = time.time() - start_time
                        data = await response.json()
                        self.results["api_tests"][endpoint] = {
                            "status": response.status,
                            "response_time_ms": round(response_time * 1000, 2),
                            "data": data
                        }
                        print(f"✅ {endpoint}: {response.status} ({response_time*1000:.2f}ms)")
                except Exception as e:
                    self.results["errors"].append(f"{endpoint}: {str(e)}")
                    print(f"❌ {endpoint}: {str(e)}")
    
    async def test_crud_operations(self):
        """Test Create, Read, Update, Delete operations"""
        async with aiohttp.ClientSession() as session:
            # Test project creation
            try:
                project_data = {
                    "name": "Runtime Test Project",
                    "description": "Created during runtime testing"
                }
                async with session.post(f"{self.base_url}/api/projects", json=project_data) as response:
                    result = await response.json()
                    project_id = result.get("id")
                    self.results["api_tests"]["create_project"] = {
                        "status": response.status,
                        "project_id": project_id
                    }
                    print(f"✅ Created project ID: {project_id}")
            except Exception as e:
                self.results["errors"].append(f"Project creation: {str(e)}")
                print(f"❌ Project creation failed: {str(e)}")
            
            # Test video listing
            try:
                async with session.get(f"{self.base_url}/api/videos") as response:
                    data = await response.json()
                    video_count = data.get("count", 0)
                    self.results["api_tests"]["list_videos"] = {
                        "status": response.status,
                        "count": video_count
                    }
                    print(f"✅ Listed {video_count} videos")
            except Exception as e:
                self.results["errors"].append(f"Video listing: {str(e)}")
                print(f"❌ Video listing failed: {str(e)}")
    
    async def test_ml_endpoints(self):
        """Test ML and detection endpoints"""
        endpoints = [
            "/api/detection/models",
            "/api/detection/status"
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    async with session.get(f"{self.base_url}{endpoint}") as response:
                        if response.status == 200:
                            data = await response.json()
                            self.results["api_tests"][endpoint] = {
                                "status": response.status,
                                "data": data
                            }
                            print(f"✅ {endpoint}: Available")
                        else:
                            print(f"⚠️  {endpoint}: Status {response.status}")
                except Exception as e:
                    self.results["warnings"].append(f"{endpoint}: {str(e)}")
                    print(f"⚠️  {endpoint}: {str(e)}")
    
    async def test_performance_metrics(self):
        """Test system performance and response times"""
        test_endpoints = ["/health", "/api/projects", "/api/videos"]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in test_endpoints:
                times = []
                for i in range(5):
                    try:
                        start_time = time.time()
                        async with session.get(f"{self.base_url}{endpoint}") as response:
                            response_time = time.time() - start_time
                            times.append(response_time * 1000)  # Convert to ms
                    except:
                        pass
                
                if times:
                    avg_time = sum(times) / len(times)
                    max_time = max(times)
                    self.results["performance_metrics"][endpoint] = {
                        "avg_response_time_ms": round(avg_time, 2),
                        "max_response_time_ms": round(max_time, 2),
                        "samples": len(times)
                    }
                    
                    if avg_time < 100:
                        print(f"✅ {endpoint}: Avg {avg_time:.2f}ms (Good)")
                    elif avg_time < 500:
                        print(f"⚠️  {endpoint}: Avg {avg_time:.2f}ms (Acceptable)")
                    else:
                        print(f"❌ {endpoint}: Avg {avg_time:.2f}ms (Slow)")
    
    def generate_report(self):
        """Generate comprehensive runtime analysis report"""
        total_tests = len(self.results["api_tests"])
        successful_tests = sum(1 for test in self.results["api_tests"].values() 
                              if test.get("status") == 200)
        
        self.results["system_status"] = "healthy" if len(self.results["errors"]) == 0 else "issues_detected"
        
        report = f"""
🔍 COMPREHENSIVE RUNTIME ANALYSIS REPORT
========================================
Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}

📊 SUMMARY
---------
System Status: {self.results["system_status"].upper()}
Total API Tests: {total_tests}
Successful Tests: {successful_tests}
Failed Tests: {len(self.results["errors"])}
Warnings: {len(self.results["warnings"])}

🚀 API ENDPOINTS STATUS
---------------------"""
        
        for endpoint, data in self.results["api_tests"].items():
            status = data.get("status", "unknown")
            response_time = data.get("response_time_ms", "N/A")
            report += f"\n{endpoint}: {status} ({response_time}ms)"
        
        if self.results["performance_metrics"]:
            report += f"\n\n⚡ PERFORMANCE METRICS\n--------------------"
            for endpoint, metrics in self.results["performance_metrics"].items():
                avg_time = metrics["avg_response_time_ms"]
                max_time = metrics["max_response_time_ms"]
                report += f"\n{endpoint}: Avg {avg_time}ms, Max {max_time}ms"
        
        if self.results["errors"]:
            report += f"\n\n❌ ERRORS DETECTED\n-----------------"
            for error in self.results["errors"]:
                report += f"\n• {error}"
        
        if self.results["warnings"]:
            report += f"\n\n⚠️  WARNINGS\n-----------"
            for warning in self.results["warnings"]:
                report += f"\n• {warning}"
        
        report += f"\n\n📋 RECOMMENDATIONS\n-----------------"
        if len(self.results["errors"]) == 0:
            report += "\n✅ All critical systems are operational"
        else:
            report += "\n🔧 Address the errors listed above"
            
        if any(m["avg_response_time_ms"] > 500 for m in self.results["performance_metrics"].values()):
            report += "\n🚀 Consider performance optimization for slow endpoints"
        
        return report
    
    async def run_comprehensive_tests(self):
        """Run all tests and generate report"""
        print("🔍 Starting Comprehensive Runtime Analysis...")
        print("=" * 50)
        
        await self.test_health_endpoints()
        print()
        
        await self.test_crud_operations()
        print()
        
        await self.test_ml_endpoints()
        print()
        
        await self.test_performance_metrics()
        print()
        
        report = self.generate_report()
        print(report)
        
        # Save detailed results
        with open("/home/rigade/Testing/ai-model-validation-platform/tests/runtime_analysis_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        return self.results

async def main():
    tester = RuntimeTester()
    results = await tester.run_comprehensive_tests()
    
    # Return appropriate exit code
    if results["system_status"] == "healthy":
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())