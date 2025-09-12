#!/usr/bin/env python3
"""
Quick Backend API Test - Essential endpoint validation
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
import httpx

async def test_backend_apis():
    """Test core backend API endpoints"""
    print("🎯 Quick Backend API Testing")
    print("=" * 40)
    
    base_url = "http://localhost:8000"
    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {},
        "summary": {}
    }
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Test 1: Health check
        try:
            print("🏥 Testing health endpoint...")
            response = await client.get(f"{base_url}/health")
            results["tests"]["health"] = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response": response.json() if response.status_code == 200 else response.text[:200]
            }
            print(f"  Health: {'✅' if response.status_code == 200 else '❌'} {response.status_code}")
        except Exception as e:
            results["tests"]["health"] = {"error": str(e), "success": False}
            print(f"  Health: ❌ {e}")

        # Test 2: List projects
        try:
            print("📁 Testing projects endpoint...")
            response = await client.get(f"{base_url}/api/projects")
            results["tests"]["projects_list"] = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "count": len(response.json()) if response.status_code == 200 else 0
            }
            print(f"  Projects List: {'✅' if response.status_code == 200 else '❌'} {response.status_code}")
        except Exception as e:
            results["tests"]["projects_list"] = {"error": str(e), "success": False}
            print(f"  Projects List: ❌ {e}")

        # Test 3: Create project
        try:
            print("➕ Testing project creation...")
            project_data = {
                "name": "Quick Test Project",
                "description": "Backend validation test",
                "camera_type": "webcam",
                "signal_type": "voltage"
            }
            response = await client.post(f"{base_url}/api/projects", json=project_data)
            results["tests"]["project_create"] = {
                "status_code": response.status_code,
                "success": response.status_code in [200, 201],
                "project_id": response.json().get("id") if response.status_code in [200, 201] else None
            }
            print(f"  Project Create: {'✅' if response.status_code in [200, 201] else '❌'} {response.status_code}")
            
            # Store project ID for cleanup
            if response.status_code in [200, 201]:
                project_id = response.json().get("id")
                results["test_project_id"] = project_id
        except Exception as e:
            results["tests"]["project_create"] = {"error": str(e), "success": False}
            print(f"  Project Create: ❌ {e}")

        # Test 4: List videos
        try:
            print("🎥 Testing videos endpoint...")
            response = await client.get(f"{base_url}/api/videos")
            results["tests"]["videos_list"] = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "count": len(response.json()) if response.status_code == 200 else 0
            }
            print(f"  Videos List: {'✅' if response.status_code == 200 else '❌'} {response.status_code}")
        except Exception as e:
            results["tests"]["videos_list"] = {"error": str(e), "success": False}
            print(f"  Videos List: ❌ {e}")

        # Test 5: Error handling
        try:
            print("⚠️  Testing error handling...")
            response = await client.get(f"{base_url}/api/nonexistent")
            results["tests"]["error_handling"] = {
                "status_code": response.status_code,
                "success": response.status_code == 404,
                "proper_error": response.status_code >= 400
            }
            print(f"  Error Handling: {'✅' if response.status_code == 404 else '❌'} {response.status_code}")
        except Exception as e:
            results["tests"]["error_handling"] = {"error": str(e), "success": False}
            print(f"  Error Handling: ❌ {e}")

        # Test 6: Database health
        try:
            print("🗃️  Testing database...")
            response = await client.get(f"{base_url}/api/database/health")
            results["tests"]["database"] = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response": response.json() if response.status_code == 200 else response.text[:200]
            }
            print(f"  Database: {'✅' if response.status_code == 200 else '❌'} {response.status_code}")
        except Exception as e:
            results["tests"]["database"] = {"error": str(e), "success": False}
            print(f"  Database: ❌ {e}")

        # Cleanup test project
        if results.get("test_project_id"):
            try:
                await client.delete(f"{base_url}/api/projects/{results['test_project_id']}")
                print(f"  🧹 Cleaned up test project: {results['test_project_id']}")
            except:
                pass

    # Generate summary
    total_tests = len(results["tests"])
    successful_tests = sum(1 for test in results["tests"].values() if test.get("success", False))
    
    results["summary"] = {
        "total_tests": total_tests,
        "successful_tests": successful_tests,
        "failed_tests": total_tests - successful_tests,
        "success_rate": round(successful_tests / total_tests * 100, 2) if total_tests > 0 else 0,
        "backend_functional": successful_tests >= 4,
        "critical_systems": {
            "api_server": results["tests"]["health"].get("success", False),
            "database": results["tests"]["database"].get("success", False), 
            "crud_operations": results["tests"]["project_create"].get("success", False),
            "error_handling": results["tests"]["error_handling"].get("success", False)
        }
    }
    
    print(f"\n📊 QUICK TEST SUMMARY:")
    print(f"  Tests Run: {total_tests}")
    print(f"  Successful: {successful_tests}")
    print(f"  Failed: {total_tests - successful_tests}")
    print(f"  Success Rate: {results['summary']['success_rate']}%")
    print(f"  Backend Functional: {'✅ Yes' if results['summary']['backend_functional'] else '❌ No'}")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = Path(__file__).parent / f"quick_backend_test_{timestamp}.json"
    
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📁 Results saved: {results_file}")
    
    return results

async def main():
    results = await test_backend_apis()
    success = results["summary"]["backend_functional"]
    
    if success:
        print("\n✅ Backend API testing successful!")
    else:
        print("\n❌ Backend API testing found issues")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)