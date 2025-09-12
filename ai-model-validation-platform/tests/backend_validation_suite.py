#!/usr/bin/env python3
"""
Comprehensive Backend Validation Suite
Tests all backend services, endpoints, and integrations
"""

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

def run_comprehensive_backend_validation():
    """Run comprehensive backend validation suite"""
    base_url = "http://localhost:8000"
    results = []
    
    print("🚀 Comprehensive Backend Validation Suite")
    print("=" * 50)
    
    # Test 1: Health check
    print("\n📋 Testing Health Endpoints...")
    health_tests = [
        f"{base_url}/health",
        f"{base_url}/",
    ]
    
    for url in health_tests:
        result = test_endpoint(url)
        results.append(result)
        status = "✅" if result["success"] else "❌"
        response_info = result.get("response", {})
        if isinstance(response_info, dict):
            status_info = response_info.get("status", result["status_code"])
        else:
            status_info = result["status_code"]
        print(f"{status} {url}: {status_info}")
    
    # Test 2: Database operations
    print("\n📊 Testing Database Operations...")
    db_tests = [
        (f"{base_url}/api/projects", "GET"),
        (f"{base_url}/api/videos", "GET"),
        (f"{base_url}/api/dashboard/stats", "GET"),
    ]
    
    for url, method in db_tests:
        result = test_endpoint(url, method)
        results.append(result)
        status = "✅" if result["success"] else "❌"
        print(f"{status} {method} {url}: Status {result['status_code']}")
    
    # Test 3: Create project
    print("\n🏗️ Testing Project Creation...")
    project_data = {
        "name": "API Validation Test Project",
        "description": "Testing project creation via API",
        "status": "active"
    }
    
    result = test_endpoint(f"{base_url}/api/projects", "POST", project_data)
    results.append(result)
    status = "✅" if result["success"] else "❌"
    print(f"{status} POST projects: {result.get('response', {})}")
    
    # Test 4: ML/Detection endpoints
    print("\n🤖 Testing ML/Detection Endpoints...")
    ml_tests = [
        f"{base_url}/api/detection/models",
        f"{base_url}/api/validation/status",
    ]
    
    for url in ml_tests:
        result = test_endpoint(url)
        results.append(result)
        status = "✅" if result["success"] else "❌"
        response_info = result.get("response", {})
        if isinstance(response_info, dict):
            status_info = response_info.get("status", result["status_code"])
        else:
            status_info = result["status_code"]
        print(f"{status} {url}: {status_info}")
    
    # Test 5: File upload simulation
    print("\n📁 Testing File Upload Endpoint...")
    try:
        # Create a small test file
        test_content = b"fake video content for testing"
        files = {"file": ("test.mp4", test_content, "video/mp4")}
        result = test_endpoint(f"{base_url}/api/videos/upload", "POST", {"project_id": 1}, files)
        results.append(result)
        status = "✅" if result["success"] else "❌"
        print(f"{status} POST upload: {result.get('response', {})}")
    except Exception as e:
        print(f"❌ Upload test error: {e}")
    
    # Generate summary
    print("\n📈 Test Summary")
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
        print("\n🔍 Failed Tests Details:")
        for result in results:
            if not result["success"]:
                error_info = result.get("error", result["status_code"])
                print(f"❌ {result['url']}: {error_info}")
    
    return results

def test_system_resources():
    """Test system resource availability"""
    print("\n🖥️ System Resources Check")
    print("=" * 30)
    
    # Check ports
    import socket
    
    ports_to_check = [8000, 5432, 6379]
    for port in ports_to_check:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            print(f"✅ Port {port}: OPEN")
        else:
            print(f"❌ Port {port}: CLOSED")

def validate_file_system():
    """Validate file system structure"""
    print("\n📁 File System Validation")
    print("=" * 30)
    
    critical_files = [
        "backend/main.py",
        "backend/database.py", 
        "backend/models.py",
        "backend/schemas.py",
        "backend/crud.py",
        "docker-compose.yml"
    ]
    
    for file_path in critical_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}: EXISTS")
        else:
            print(f"❌ {file_path}: MISSING")

if __name__ == "__main__":
    # Wait for server to start
    print("⏳ Waiting for server startup...")
    time.sleep(3)
    
    # Run all validation tests
    validate_file_system()
    test_system_resources()
    results = run_comprehensive_backend_validation()
    
    # Save results to file
    results_file = "backend_validation_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to {results_file}")
    
    # Return appropriate exit code
    failed_tests = len([r for r in results if not r["success"]])
    if failed_tests == 0:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {failed_tests} tests failed")
        sys.exit(1)