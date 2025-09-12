#!/usr/bin/env python3
"""
Performance and Load Testing for AI Model Validation Platform
"""
import asyncio
import httpx
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
import pytest

BASE_URL = "http://localhost:8001"
TIMEOUT = 30.0

class PerformanceValidator:
    """Performance validation test suite"""
    
    @pytest.mark.asyncio
    async def test_concurrent_load(self):
        """Test server performance under concurrent load"""
        async def make_request():
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                start_time = time.time()
                response = await client.get(f"{BASE_URL}/health")
                end_time = time.time()
                return {
                    'status_code': response.status_code,
                    'response_time': end_time - start_time,
                    'success': response.status_code == 200
                }
        
        # Test with 20 concurrent requests
        tasks = [make_request() for _ in range(20)]
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        success_count = sum(1 for r in results if r['success'])
        response_times = [r['response_time'] for r in results if r['success']]
        
        assert success_count >= 18, f"Only {success_count}/20 requests succeeded"
        
        if response_times:
            avg_time = statistics.mean(response_times)
            max_time = max(response_times)
            
            assert avg_time < 1.0, f"Average response time {avg_time:.3f}s too slow"
            assert max_time < 2.0, f"Max response time {max_time:.3f}s too slow"
        
        print(f"✅ Concurrent load test: {success_count}/20 success, avg: {avg_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_api_endpoint_performance(self):
        """Test performance of various API endpoints"""
        endpoints = [
            ("/health", "GET"),
            ("/api/projects", "GET"), 
            ("/api/videos", "GET"),
            ("/api/dashboard/stats", "GET")
        ]
        
        results = {}
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            for endpoint, method in endpoints:
                times = []
                
                # Test each endpoint 5 times
                for _ in range(5):
                    start_time = time.time()
                    
                    if method == "GET":
                        response = await client.get(f"{BASE_URL}{endpoint}")
                    
                    end_time = time.time()
                    
                    if response.status_code == 200:
                        times.append(end_time - start_time)
                
                if times:
                    results[endpoint] = {
                        'avg_time': statistics.mean(times),
                        'max_time': max(times),
                        'min_time': min(times)
                    }
        
        # Validate performance requirements
        for endpoint, metrics in results.items():
            avg_time = metrics['avg_time']
            assert avg_time < 1.0, f"{endpoint} avg time {avg_time:.3f}s too slow"
            print(f"✅ {endpoint}: avg {avg_time:.3f}s, max {metrics['max_time']:.3f}s")
    
    @pytest.mark.asyncio
    async def test_database_performance(self):
        """Test database operation performance"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Test project creation performance
            create_times = []
            project_ids = []
            
            for i in range(5):
                project_data = {
                    "name": f"Performance Test Project {i}",
                    "cameraModel": "Perf Test Camera",
                    "signalType": "GPIO"
                }
                
                start_time = time.time()
                response = await client.post(
                    f"{BASE_URL}/api/projects",
                    json=project_data
                )
                end_time = time.time()
                
                if response.status_code == 201:
                    create_times.append(end_time - start_time)
                    project_ids.append(response.json()["id"])
            
            # Test read performance
            read_times = []
            for _ in range(5):
                start_time = time.time()
                response = await client.get(f"{BASE_URL}/api/projects")
                end_time = time.time()
                
                if response.status_code == 200:
                    read_times.append(end_time - start_time)
            
            # Cleanup
            for project_id in project_ids:
                await client.delete(f"{BASE_URL}/api/projects/{project_id}")
        
        # Validate performance
        if create_times:
            avg_create = statistics.mean(create_times)
            assert avg_create < 0.5, f"Database create too slow: {avg_create:.3f}s"
            print(f"✅ DB Create avg: {avg_create:.3f}s")
        
        if read_times:
            avg_read = statistics.mean(read_times)
            assert avg_read < 0.5, f"Database read too slow: {avg_read:.3f}s"
            print(f"✅ DB Read avg: {avg_read:.3f}s")

if __name__ == "__main__":
    print("🚀 Running Performance and Load Tests")
    print("=" * 50)
    
    import subprocess
    result = subprocess.run([
        "python", "-m", "pytest", __file__, 
        "-v", "--tb=short", "-s"
    ])
    
    exit_code = result.returncode
    if exit_code == 0:
        print("\n✅ All performance tests passed!")
    else:
        print(f"\n⚠️ Some performance tests failed (exit code: {exit_code})")