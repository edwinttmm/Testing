#!/usr/bin/env python3
"""
Comprehensive Full Stack User Workflow Test
Tests the system as a real user would use it
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

def test_full_user_workflow():
    """Test complete user workflow from frontend to backend"""
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": [],
        "errors": [],
        "summary": {}
    }
    
    print("=" * 60)
    print("COMPREHENSIVE FULL STACK USER WORKFLOW TEST")
    print("=" * 60)
    
    # Test 1: Frontend Accessibility
    print("\n1. Testing Frontend Accessibility...")
    try:
        response = requests.get(FRONTEND_URL, timeout=5)
        if response.status_code == 200:
            print("   ✅ Frontend is accessible")
            results["tests"].append({"name": "Frontend Access", "status": "PASS"})
        else:
            print(f"   ❌ Frontend returned status: {response.status_code}")
            results["errors"].append(f"Frontend status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Frontend error: {e}")
        results["errors"].append(f"Frontend connection error: {str(e)}")
    
    # Test 2: Backend Health Check
    print("\n2. Testing Backend Health...")
    try:
        response = requests.get(f"{BASE_URL}/health/simple", timeout=5)
        print(f"   Response: {response.text}")
        if response.status_code == 200:
            print("   ✅ Backend health check passed")
            results["tests"].append({"name": "Backend Health", "status": "PASS"})
        else:
            print(f"   ❌ Backend health check failed: {response.status_code}")
            results["errors"].append(f"Backend health: {response.text}")
    except Exception as e:
        print(f"   ❌ Backend error: {e}")
        results["errors"].append(f"Backend connection error: {str(e)}")
    
    # Test 3: API Endpoints
    print("\n3. Testing API Endpoints...")
    
    # Get Projects
    try:
        response = requests.get(f"{BASE_URL}/api/projects", timeout=5)
        print(f"   GET /api/projects: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        if response.status_code == 200:
            results["tests"].append({"name": "GET Projects", "status": "PASS"})
        else:
            results["errors"].append(f"GET Projects: {response.text}")
    except Exception as e:
        print(f"   ❌ GET Projects error: {e}")
        results["errors"].append(f"GET Projects error: {str(e)}")
    
    # Create Project (LabJack Signal Detection Project)
    print("\n4. Testing Project Creation (LabJack Signal Detection)...")
    project_data = {
        "name": "LabJack Signal Test",
        "description": "Testing LabJack time and signal detection",
        "cameraModel": "LabJack-T7",
        "cameraView": "Front-facing VRU",
        "signalType": "GPIO"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/projects",
            json=project_data,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        print(f"   POST /api/projects: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        if response.status_code in [200, 201]:
            results["tests"].append({"name": "Create Project", "status": "PASS"})
            project_id = response.json().get("id")
            print(f"   ✅ Project created with ID: {project_id}")
        else:
            results["errors"].append(f"Create Project: {response.text}")
    except Exception as e:
        print(f"   ❌ Create Project error: {e}")
        results["errors"].append(f"Create Project error: {str(e)}")
    
    # Test 5: WebSocket Connection
    print("\n5. Testing WebSocket Connection...")
    ws_url = "ws://localhost:8000/ws/detection"
    print(f"   WebSocket URL: {ws_url}")
    # Note: Would need websocket-client library for full test
    results["tests"].append({"name": "WebSocket Test", "status": "SKIPPED"})
    
    # Test 6: Database Tables Check
    print("\n6. Checking Database Tables...")
    try:
        response = requests.get(f"{BASE_URL}/api/health/database", timeout=5)
        if response.status_code == 200:
            print("   ✅ Database tables accessible")
            results["tests"].append({"name": "Database Tables", "status": "PASS"})
        else:
            print(f"   ❌ Database issue: {response.text}")
            results["errors"].append(f"Database: {response.text}")
    except Exception as e:
        print(f"   ❌ Database check error: {e}")
        results["errors"].append(f"Database error: {str(e)}")
    
    # Test 7: CVAT Integration
    print("\n7. Testing CVAT Integration...")
    try:
        response = requests.get("http://localhost:8080/api/server/about", timeout=5)
        if response.status_code == 200:
            print("   ✅ CVAT is accessible")
            results["tests"].append({"name": "CVAT Access", "status": "PASS"})
        elif response.status_code == 401:
            print("   ⚠️  CVAT requires authentication (expected)")
            results["tests"].append({"name": "CVAT Access", "status": "AUTH_REQUIRED"})
        else:
            print(f"   ❌ CVAT returned: {response.status_code}")
            results["errors"].append(f"CVAT status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ CVAT error: {e}")
        results["errors"].append(f"CVAT error: {str(e)}")
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    total_tests = len(results["tests"])
    passed = len([t for t in results["tests"] if t["status"] == "PASS"])
    failed = len(results["errors"])
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors Found: {len(results['errors'])}")
    
    if results["errors"]:
        print("\n❌ CRITICAL ERRORS FOUND:")
        for i, error in enumerate(results["errors"], 1):
            print(f"   {i}. {error}")
    
    results["summary"] = {
        "total": total_tests,
        "passed": passed,
        "failed": failed,
        "error_count": len(results["errors"])
    }
    
    # Save results
    with open("user_workflow_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to user_workflow_test_results.json")
    
    return results

if __name__ == "__main__":
    test_full_user_workflow()