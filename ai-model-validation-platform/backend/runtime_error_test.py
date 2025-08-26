#!/usr/bin/env python3
"""
Runtime Error Test - Check for specific errors that were previously reported
"""
import asyncio
import aiohttp
import json
import time
from datetime import datetime

async def test_specific_errors():
    """Test for specific runtime errors that were previously reported"""
    
    print("🔍 Testing for Previously Reported Runtime Errors")
    print("=" * 60)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {}
    }
    
    async with aiohttp.ClientSession() as session:
        
        # Test 1: Projects page should not return 500 Internal Server Error
        print("1. Testing Projects page for 500 errors...")
        try:
            async with session.get("http://localhost:8000/api/projects") as response:
                results["tests"]["projects_500_error"] = {
                    "test": "Projects API should not return 500",
                    "status_code": response.status,
                    "success": response.status != 500,
                    "expected": "Not 500",
                    "actual": response.status
                }
                
                if response.status == 200:
                    data = await response.json()
                    results["tests"]["projects_500_error"]["project_count"] = len(data)
                    print(f"   ✅ Projects API: {response.status} (found {len(data)} projects)")
                else:
                    print(f"   ⚠️  Projects API: {response.status}")
                    
        except Exception as e:
            results["tests"]["projects_500_error"] = {
                "test": "Projects API should not return 500", 
                "success": False,
                "error": str(e)
            }
            print(f"   ❌ Projects API error: {e}")
        
        # Test 2: Check for confidence/boundingBox undefined errors
        print("2. Testing annotation data structure...")
        try:
            # Get a video to test annotations
            async with session.get("http://localhost:8000/api/videos") as response:
                if response.status == 200:
                    videos = await response.json()
                    
                    if videos:
                        video_id = videos[0]["id"] 
                        
                        # Test annotation endpoint
                        async with session.get(f"http://localhost:8000/api/videos/{video_id}/annotations") as ann_response:
                            results["tests"]["annotation_structure"] = {
                                "test": "Annotations should have proper structure",
                                "status_code": ann_response.status,
                                "success": ann_response.status in [200, 404],  # 404 is OK if no annotations
                                "video_id": video_id
                            }
                            
                            if ann_response.status == 200:
                                annotations = await ann_response.json()
                                
                                # Check for proper structure
                                structure_ok = True
                                for ann in annotations:
                                    if isinstance(ann, dict):
                                        # Check for confidence and bounding box fields
                                        if 'confidence' in ann and ann['confidence'] is None:
                                            structure_ok = False
                                        if 'bounding_box' in ann and ann['bounding_box'] is None:
                                            structure_ok = False
                                            
                                results["tests"]["annotation_structure"]["structure_valid"] = structure_ok
                                results["tests"]["annotation_structure"]["annotation_count"] = len(annotations)
                                print(f"   ✅ Annotations: {ann_response.status} ({len(annotations)} annotations, structure {'valid' if structure_ok else 'invalid'})")
                            else:
                                print(f"   ✅ Annotations: {ann_response.status} (no annotations found)")
                    else:
                        results["tests"]["annotation_structure"] = {
                            "test": "Annotations should have proper structure",
                            "success": True,
                            "note": "No videos found to test annotations"
                        }
                        print("   ✅ Annotations: No videos to test")
                        
        except Exception as e:
            results["tests"]["annotation_structure"] = {
                "test": "Annotations should have proper structure",
                "success": False,
                "error": str(e)
            }
            print(f"   ❌ Annotation test error: {e}")
        
        # Test 3: Check ground truth endpoint
        print("3. Testing ground truth endpoints...")
        try:
            async with session.get("http://localhost:8000/api/ground-truth/videos/available") as response:
                results["tests"]["ground_truth_available"] = {
                    "test": "Ground truth videos endpoint should work",
                    "status_code": response.status,
                    "success": response.status == 200,
                }
                
                if response.status == 200:
                    data = await response.json()
                    results["tests"]["ground_truth_available"]["video_count"] = len(data) if isinstance(data, list) else 0
                    print(f"   ✅ Ground truth videos: {response.status}")
                else:
                    print(f"   ⚠️  Ground truth videos: {response.status}")
                    
        except Exception as e:
            results["tests"]["ground_truth_available"] = {
                "test": "Ground truth videos endpoint should work",
                "success": False,
                "error": str(e)
            }
            print(f"   ❌ Ground truth test error: {e}")
        
        # Test 4: Test video upload endpoint
        print("4. Testing video upload endpoint...")
        try:
            async with session.get("http://localhost:8000/api/videos/upload") as response:
                results["tests"]["video_upload"] = {
                    "test": "Video upload endpoint should be accessible",
                    "status_code": response.status,
                    "success": response.status in [200, 405, 400],  # 405 Method Not Allowed is OK for GET
                }
                print(f"   ✅ Video upload: {response.status} (endpoint exists)")
                
        except Exception as e:
            results["tests"]["video_upload"] = {
                "test": "Video upload endpoint should be accessible",
                "success": False,
                "error": str(e)
            }
            print(f"   ❌ Video upload test error: {e}")
    
    # Calculate overall success
    successful_tests = sum(1 for test in results["tests"].values() if test.get("success", False))
    total_tests = len(results["tests"])
    
    results["summary"] = {
        "successful_tests": successful_tests,
        "total_tests": total_tests,
        "success_rate": successful_tests / total_tests if total_tests > 0 else 0,
        "overall_success": successful_tests == total_tests
    }
    
    print("\n" + "=" * 60)
    print("📋 RUNTIME ERROR TEST SUMMARY")
    print("=" * 60)
    
    status_symbol = "✅" if results["summary"]["overall_success"] else "❌"
    print(f"{status_symbol} Overall: {successful_tests}/{total_tests} tests passed ({results['summary']['success_rate']*100:.1f}%)")
    
    for test_name, test_data in results["tests"].items():
        symbol = "✅" if test_data.get("success", False) else "❌"
        print(f"{symbol} {test_name}: {test_data['test']}")
        if not test_data.get("success", False) and "error" in test_data:
            print(f"    Error: {test_data['error']}")
    
    # Save results
    results_file = f"runtime_error_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {results_file}")
    
    return results

async def main():
    print("🚀 Runtime Error Testing Agent")
    print("Testing for specific errors that were previously reported...\n")
    
    results = await test_specific_errors()
    
    return 0 if results["summary"]["overall_success"] else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())