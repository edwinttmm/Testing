#!/usr/bin/env python3
"""
Test script for annotation API fixes

This tests:
1. POST /api/videos/{id}/annotations endpoint
2. Schema validation with proper videoId handling
3. Error handling and validation
4. Database connectivity
"""

import requests
import json
import sys
import uuid
from datetime import datetime
import time

# Test configuration
BASE_URL = "http://localhost:8001"
TEST_VIDEO_ID = str(uuid.uuid4())

def test_annotation_creation():
    """Test annotation creation with various scenarios"""
    
    print("🧪 TESTING ANNOTATION CREATION API")
    print("=" * 50)
    
    # Test data - CORRECT format with proper fields
    test_annotations = [
        {
            "name": "Valid pedestrian annotation",
            "data": {
                "detectionId": "DET_PED_001",
                "frameNumber": 30,
                "timestamp": 1.0,
                "vruType": "pedestrian",
                "boundingBox": {
                    "x": 100,
                    "y": 150,
                    "width": 80,
                    "height": 120,
                    "confidence": 0.85
                },
                "occluded": False,
                "truncated": False,
                "difficult": False,
                "validated": False
            },
            "should_pass": True
        },
        {
            "name": "Missing required field (frameNumber)",
            "data": {
                "detectionId": "DET_PED_002",
                "timestamp": 2.0,
                "vruType": "pedestrian",
                "boundingBox": {
                    "x": 200,
                    "y": 250,
                    "width": 90,
                    "height": 130,
                    "confidence": 0.9
                }
            },
            "should_pass": False
        },
        {
            "name": "Invalid VRU type",
            "data": {
                "detectionId": "DET_INV_001",
                "frameNumber": 45,
                "timestamp": 3.0,
                "vruType": "invalid_type",
                "boundingBox": {
                    "x": 150,
                    "y": 200,
                    "width": 70,
                    "height": 110,
                    "confidence": 0.8
                }
            },
            "should_pass": False
        },
        {
            "name": "Invalid bounding box (negative coordinates)",
            "data": {
                "detectionId": "DET_PED_003",
                "frameNumber": 60,
                "timestamp": 4.0,
                "vruType": "pedestrian",
                "boundingBox": {
                    "x": -10,
                    "y": 150,
                    "width": 80,
                    "height": 120,
                    "confidence": 0.7
                }
            },
            "should_pass": False
        },
        {
            "name": "Valid cyclist annotation without detectionId (auto-generated)",
            "data": {
                "frameNumber": 75,
                "timestamp": 5.0,
                "vruType": "cyclist",
                "boundingBox": {
                    "x": 300,
                    "y": 100,
                    "width": 60,
                    "height": 140,
                    "confidence": 0.95
                },
                "validated": True
            },
            "should_pass": True
        }
    ]
    
    # Test each annotation scenario
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_annotations, 1):
        print(f"\n📝 Test {i}: {test_case['name']}")
        print("-" * 40)
        
        try:
            # Send POST request to annotation endpoint
            response = requests.post(
                f"{BASE_URL}/api/videos/{TEST_VIDEO_ID}/annotations",
                json=test_case["data"],
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            print(f"Status Code: {response.status_code}")
            
            if test_case["should_pass"]:
                if response.status_code == 201 or response.status_code == 200:
                    print("✅ PASSED - Annotation created successfully")
                    try:
                        result = response.json()
                        print(f"   Created annotation ID: {result.get('id', 'N/A')}")
                        print(f"   Detection ID: {result.get('detection_id', 'N/A')}")
                        passed += 1
                    except:
                        print("   Response is not JSON")
                else:
                    print(f"❌ FAILED - Expected success but got {response.status_code}")
                    print(f"   Response: {response.text[:200]}...")
                    failed += 1
            else:
                if response.status_code >= 400:
                    print("✅ PASSED - Correctly rejected invalid data")
                    try:
                        error = response.json()
                        print(f"   Error: {error.get('detail', 'No detail')}")
                    except:
                        print(f"   Error response: {response.text[:100]}...")
                    passed += 1
                else:
                    print(f"❌ FAILED - Should have been rejected but got {response.status_code}")
                    failed += 1
            
        except requests.exceptions.ConnectionError:
            print("❌ CONNECTION ERROR - Server not running")
            print("   Start server with: python main.py")
            failed += 1
            
        except requests.exceptions.Timeout:
            print("❌ TIMEOUT ERROR - Request took too long")
            failed += 1
            
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR: {str(e)}")
            failed += 1
    
    # Test results summary
    print(f"\n📊 TEST RESULTS SUMMARY")
    print("=" * 30)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(passed/(passed+failed)*100):.1f}%" if (passed+failed) > 0 else "N/A")
    
    return passed, failed

def test_health_check():
    """Test health check endpoint"""
    print(f"\n🏥 TESTING HEALTH CHECK")
    print("-" * 30)
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/videos/{TEST_VIDEO_ID}/annotations/health",
            timeout=5
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            health_data = response.json()
            print("✅ Health check passed")
            print(f"   Status: {health_data.get('status', 'unknown')}")
            print(f"   Database Connected: {health_data.get('database_connected', False)}")
            print(f"   Video Exists: {health_data.get('video_exists', False)}")
            return True
        else:
            print("❌ Health check failed")
            return False
            
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False

def test_schema_validation():
    """Test schema validation endpoint"""
    print(f"\n🔍 TESTING SCHEMA VALIDATION")
    print("-" * 35)
    
    test_data = {
        "frameNumber": 30,
        "timestamp": 1.0,
        "vruType": "pedestrian",
        "boundingBox": {
            "x": 100,
            "y": 150,
            "width": 80,
            "height": 120,
            "confidence": 0.85
        }
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/videos/{TEST_VIDEO_ID}/annotations/validate-schema",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            validation_result = response.json()
            print("✅ Schema validation completed")
            print(f"   Valid: {validation_result.get('valid', False)}")
            print(f"   VRU Type Valid: {validation_result.get('vru_type_valid', False)}")
            return validation_result.get('valid', False)
        else:
            print("❌ Schema validation failed")
            return False
            
    except Exception as e:
        print(f"❌ Schema validation error: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🚀 ANNOTATION API FIX VALIDATION")
    print("=" * 40)
    print(f"Test Video ID: {TEST_VIDEO_ID}")
    print(f"Base URL: {BASE_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Run tests
    health_ok = test_health_check()
    schema_ok = test_schema_validation()
    passed, failed = test_annotation_creation()
    
    # Final summary
    print(f"\n🎯 FINAL TEST SUMMARY")
    print("=" * 25)
    print(f"Health Check: {'✅ PASS' if health_ok else '❌ FAIL'}")
    print(f"Schema Validation: {'✅ PASS' if schema_ok else '❌ FAIL'}")
    print(f"Annotation Tests: {passed} passed, {failed} failed")
    
    total_tests = passed + failed + (1 if health_ok else 0) + (1 if schema_ok else 0)
    total_passed = passed + (1 if health_ok else 0) + (1 if schema_ok else 0)
    
    print(f"\n🏆 OVERALL: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("🎉 ALL TESTS PASSED - API fixes are working!")
        return 0
    else:
        print("⚠️  Some tests failed - review the issues above")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)