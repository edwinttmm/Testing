#!/usr/bin/env python3
import requests
import json
import os
import sys
import time
from pathlib import Path

def test_endpoint(url, method="GET", data=None, files=None):
    """Test an API endpoint and return results"""
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            if files:
                response = requests.post(url, files=files, data=data, timeout=30)
            else:
                headers = {"Content-Type": "application/json"} if data else {}
                response = requests.post(url, json=data, headers=headers, timeout=10)
        
        return {
            "url": url,
            "status_code": response.status_code,
            "success": response.status_code < 400,
            "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text[:200],
            "error": None
        }
    except Exception as e:
        return {
            "url": url,
            "status_code": 0,
            "success": False,
            "response": None,
            "error": str(e)
        }

def run_comprehensive_api_tests():
    """Run comprehensive API testing suite"""
    base_url = "http://localhost:8000"
    results = []
    
    print("🚀 Comprehensive Backend API Testing Suite")
    print("=" * 50)
    
    # Test 1: Health check
    print("\\n📋 Testing Health Endpoints...")
    health_tests = [
        f"{base_url}/health",
        f"{base_url}/",
    ]
    
    for url in health_tests:
        result = test_endpoint(url)
        results.append(result)
        status = "✅" if result["success"] else "❌"
        print(f"{status} {url}: {result.get(\"response\", {}).get(\"status\", result[\"status_code\"])}")
    
    # Test 2: Database operations
    print("\\n📊 Testing Database Operations...")
    db_tests = [
        (f"{base_url}/api/projects", "GET"),
        (f"{base_url}/api/videos", "GET"),
        (f"{base_url}/api/dashboard/stats", "GET"),
    ]
    
    for url, method in db_tests:
        result = test_endpoint(url, method)
        results.append(result)
        status = "✅" if result["success"] else "❌"
        print(f"{status} {method} {url}: Status {result[\"status_code\"]}")
    
    # Test 3: Create project
    print("\\n🏗️  Testing Project Creation...")
    project_data = {
        "name": "API Validation Test Project",
        "description": "Testing project creation via API",
        "status": "active"
    }
    
    result = test_endpoint(f"{base_url}/api/projects", "POST", project_data)
    results.append(result)
    status = "✅" if result["success"] else "❌"
    print(f"{status} POST projects: {result.get(\"response\", {})}")
    
    # Test 4: ML/Detection endpoints
    print("\\n🤖 Testing ML/Detection Endpoints...")
    ml_tests = [
        f"{base_url}/api/detection/models",
        f"{base_url}/api/validation/status",
    ]
    
    for url in ml_tests:
        result = test_endpoint(url)
        results.append(result)
        status = "✅" if result["success"] else "❌"
        print(f"{status} {url}: {result.get(\"response\", {}).get(\"status\", result[\"status_code\"])}")
    
    # Test 5: File upload simulation
    print("\\n📁 Testing File Upload Endpoint...")
    try:
        # Create a small test file
        test_content = b"fake video content for testing"
        files = {"file": ("test.mp4", test_content, "video/mp4")}
        result = test_endpoint(f"{base_url}/api/videos/upload", "POST", {"project_id": 1}, files)
        results.append(result)
        status = "✅" if result["success"] else "❌"
        print(f"{status} POST upload: {result.get(\"response\", {})}")
    except Exception as e:
        print(f"❌ Upload test error: {e}")
    
    # Generate summary
    print("\\n📈 Test Summary")
    print("=" * 30)
    total_tests = len(results)
    successful_tests = len([r for r in results if r["success"]])
    failed_tests = total_tests - successful_tests
    
    print(f"Total Tests: {total_tests}")
    print(f"✅ Successful: {successful_tests}")
    print(f"❌ Failed: {failed_tests}")
    print(f"Success Rate: {(successful_tests/total_tests*100):.1f}%")
    
    # Show failures
    if failed_tests > 0:
        print("\\n🔍 Failed Tests Details:")
        for result in results:
            if not result["success"]:
                print(f"❌ {result[\"url\"]}: {result.get(\"error\", result[\"status_code\"])}")
    
    return results

if __name__ == "__main__":
    # Wait for server to start
    print("⏳ Waiting for server startup...")
    time.sleep(3)
    
    results = run_comprehensive_api_tests()
    
    # Save results to file
    with open("api_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\\n💾 Results saved to api_test_results.json")

