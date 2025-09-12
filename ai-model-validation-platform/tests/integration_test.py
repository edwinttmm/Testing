#!/usr/bin/env python3
"""
Integration Test Suite
Tests service-to-service communication and complete workflows
"""

import asyncio
import aiohttp
import json
import time
import subprocess

async def test_service_communication():
    """Test communication between different services"""
    results = {
        "frontend_to_backend": "unknown",
        "backend_to_database": "unknown", 
        "redis_connectivity": "unknown",
        "file_upload_workflow": "unknown",
        "api_consistency": "unknown"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            # Test frontend accessibility
            async with session.get("http://localhost:3000") as response:
                if response.status == 200:
                    results["frontend_to_backend"] = "healthy"
                    print("✅ Frontend accessible and serving content")
        except:
            results["frontend_to_backend"] = "failed"
            print("❌ Frontend not accessible")
        
        try:
            # Test backend to database communication
            async with session.get("http://localhost:8000/api/projects") as response:
                data = await response.json()
                if response.status == 200 and "count" in data:
                    results["backend_to_database"] = "healthy"
                    print(f"✅ Backend-Database communication: {data['count']} projects")
        except:
            results["backend_to_database"] = "failed"
            print("❌ Backend-Database communication failed")
        
        try:
            # Test complete file upload workflow
            test_data = b"test video content for integration testing"
            form_data = aiohttp.FormData()
            form_data.add_field('file', test_data, filename='integration_test.mp4')
            form_data.add_field('project_id', '1')
            
            async with session.post("http://localhost:8000/api/videos/upload", data=form_data) as response:
                if response.status == 200:
                    results["file_upload_workflow"] = "healthy"
                    print("✅ File upload workflow completed successfully")
        except:
            results["file_upload_workflow"] = "failed"
            print("❌ File upload workflow failed")
        
        try:
            # Test API consistency across endpoints
            endpoints = ["/health", "/api/projects", "/api/videos", "/api/dashboard/stats"]
            all_successful = True
            for endpoint in endpoints:
                async with session.get(f"http://localhost:8000{endpoint}") as response:
                    if response.status != 200:
                        all_successful = False
                        break
            
            results["api_consistency"] = "healthy" if all_successful else "inconsistent"
            print(f"✅ API consistency: {'All endpoints responding' if all_successful else 'Some endpoints failed'}")
        except:
            results["api_consistency"] = "failed"
            print("❌ API consistency test failed")
    
    # Test Redis connectivity through Docker
    try:
        result = subprocess.run(
            ["docker", "exec", "ai_validation_redis", "redis-cli", "ping"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip() == "PONG":
            results["redis_connectivity"] = "healthy"
            print("✅ Redis connectivity confirmed")
        else:
            results["redis_connectivity"] = "failed"
            print("❌ Redis ping failed")
    except:
        results["redis_connectivity"] = "failed"
        print("❌ Redis connectivity test failed")
    
    return results

async def main():
    print("🔗 Testing Service Integration...")
    print("=" * 40)
    
    results = await test_service_communication()
    
    print(f"\nIntegration Test Results:")
    for test, status in results.items():
        emoji = "✅" if status == "healthy" else "❌" if status == "failed" else "⚠️"
        print(f"{emoji} {test.replace('_', ' ').title()}: {status}")
    
    # Save results
    with open("/home/rigade/Testing/ai-model-validation-platform/tests/integration_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    return results

if __name__ == "__main__":
    asyncio.run(main())