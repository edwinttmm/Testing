"""
Backend Load Testing Script

Tests the critical fixes for:
1. Database connection pool optimization
2. Video upload response validation
3. Enhanced error handling
4. Connection timeout management
"""

import asyncio
import aiohttp
import json
import logging
import time
import tempfile
import os
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BackendLoadTester:
    """Comprehensive backend load testing"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.results = {}
        self.session = None
        
    async def create_session(self):
        """Create HTTP session with connection pooling"""
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=30,  # Per-host connection limit
            keepalive_timeout=60,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(
            total=30,  # Total timeout
            connect=10,  # Connection timeout
            sock_read=10  # Socket read timeout
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )
    
    async def close_session(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
    
    async def test_health_endpoints(self) -> Dict[str, Any]:
        """Test health check endpoints under load"""
        logger.info("Testing health endpoints...")
        
        endpoints = [
            "/health",
            "/health/database", 
            "/health/diagnostics"
        ]
        
        results = {}
        concurrent_requests = 20
        
        for endpoint in endpoints:
            logger.info(f"Testing {endpoint} with {concurrent_requests} concurrent requests")
            
            start_time = time.time()
            tasks = []
            
            for i in range(concurrent_requests):
                task = self.make_request('GET', endpoint)
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            # Analyze results
            successful = 0
            failed = 0
            errors = []
            response_times = []
            
            for response in responses:
                if isinstance(response, Exception):
                    failed += 1
                    errors.append(str(response))
                elif response and response.get('status_code', 0) < 400:
                    successful += 1
                    response_times.append(response.get('response_time', 0))
                else:
                    failed += 1
                    errors.append(f"HTTP {response.get('status_code', 0)}")
            
            results[endpoint] = {
                "concurrent_requests": concurrent_requests,
                "successful": successful,
                "failed": failed,
                "success_rate": (successful / concurrent_requests) * 100,
                "total_time": round(end_time - start_time, 2),
                "avg_response_time": round(sum(response_times) / len(response_times), 3) if response_times else 0,
                "max_response_time": max(response_times) if response_times else 0,
                "errors": errors[:5]  # First 5 errors
            }
            
            logger.info(f"{endpoint}: {successful}/{concurrent_requests} successful ({results[endpoint]['success_rate']:.1f}%)")
        
        return results
    
    async def test_database_stress(self) -> Dict[str, Any]:
        """Test database under connection stress"""
        logger.info("Testing database connection stress...")
        
        # Test with high concurrent load
        concurrent_requests = 50
        test_endpoints = [
            "/api/projects",
            "/api/videos",
            "/api/dashboard/stats"
        ]
        
        results = {}
        
        for endpoint in test_endpoints:
            logger.info(f"Stress testing {endpoint} with {concurrent_requests} concurrent requests")
            
            start_time = time.time()
            tasks = []
            
            for i in range(concurrent_requests):
                task = self.make_request('GET', endpoint)
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            # Analyze for connection pool issues
            successful = 0
            timeouts = 0
            connection_errors = 0
            server_errors = 0
            
            for response in responses:
                if isinstance(response, Exception):
                    error_str = str(response).lower()
                    if "timeout" in error_str:
                        timeouts += 1
                    elif "connection" in error_str:
                        connection_errors += 1
                    else:
                        server_errors += 1
                elif response:
                    status = response.get('status_code', 0)
                    if status == 503:  # Service unavailable (our connection timeout response)
                        timeouts += 1
                    elif 500 <= status < 600:
                        server_errors += 1
                    elif status < 400:
                        successful += 1
                    else:
                        server_errors += 1
            
            results[endpoint] = {
                "concurrent_requests": concurrent_requests,
                "successful": successful,
                "timeouts": timeouts,
                "connection_errors": connection_errors,
                "server_errors": server_errors,
                "total_time": round(end_time - start_time, 2),
                "requests_per_second": round(concurrent_requests / (end_time - start_time), 2)
            }
            
            logger.info(f"{endpoint}: {successful} successful, {timeouts} timeouts, {connection_errors} connection errors")
        
        return results
    
    def create_test_video_file(self) -> str:
        """Create a small test video file for uploads"""
        # Create a minimal valid MP4 file (just headers, not a real video)
        # This is sufficient for API testing
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        
        # Write minimal MP4 headers (simplified)
        mp4_header = b'\x00\x00\x00\x20ftypmp41\x00\x00\x00\x00mp41isom\x00\x00\x00\x08free'
        temp_file.write(mp4_header)
        temp_file.write(b'\x00' * 1000)  # Pad to make file size reasonable
        
        temp_file.close()
        return temp_file.name
    
    async def test_video_upload_stress(self) -> Dict[str, Any]:
        """Test video upload endpoints under stress"""
        logger.info("Testing video upload endpoints...")
        
        # Create test video files
        test_video_paths = []
        for i in range(5):
            video_path = self.create_test_video_file()
            test_video_paths.append(video_path)
        
        try:
            concurrent_uploads = 10
            upload_results = []
            
            logger.info(f"Testing concurrent video uploads: {concurrent_uploads} uploads")
            
            start_time = time.time()
            
            # Create upload tasks
            tasks = []
            for i in range(concurrent_uploads):
                video_path = test_video_paths[i % len(test_video_paths)]
                task = self.upload_video_file(video_path)
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            # Analyze upload results
            successful_uploads = 0
            failed_uploads = 0
            validation_errors = 0
            processing_status_present = 0
            
            for response in responses:
                if isinstance(response, Exception):
                    failed_uploads += 1
                elif response:
                    status = response.get('status_code', 0)
                    if status < 400:
                        successful_uploads += 1
                        # Check if processingStatus field is present
                        data = response.get('data', {})
                        if 'processingStatus' in data:
                            processing_status_present += 1
                    elif status == 400:  # Validation errors
                        validation_errors += 1
                    else:
                        failed_uploads += 1
            
            return {
                "concurrent_uploads": concurrent_uploads,
                "successful_uploads": successful_uploads,
                "failed_uploads": failed_uploads,
                "validation_errors": validation_errors,
                "processing_status_present": processing_status_present,
                "total_time": round(end_time - start_time, 2),
                "success_rate": (successful_uploads / concurrent_uploads) * 100,
                "processing_status_rate": (processing_status_present / max(successful_uploads, 1)) * 100
            }
        
        finally:
            # Clean up test files
            for video_path in test_video_paths:
                try:
                    os.unlink(video_path)
                except:
                    pass
    
    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                response_time = time.time() - start_time
                
                try:
                    data = await response.json()
                except:
                    data = await response.text()
                
                return {
                    "status_code": response.status,
                    "response_time": response_time,
                    "data": data
                }
        
        except Exception as e:
            response_time = time.time() - start_time
            return {
                "status_code": 0,
                "response_time": response_time,
                "error": str(e)
            }
    
    async def upload_video_file(self, video_path: str) -> Dict[str, Any]:
        """Upload a video file to the API"""
        url = f"{self.base_url}/api/videos"
        
        try:
            with open(video_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f, filename=os.path.basename(video_path), content_type='video/mp4')
                
                response_data = await self.make_request('POST', '/api/videos', data=data)
                return response_data
        
        except Exception as e:
            return {
                "status_code": 0,
                "error": str(e)
            }
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive load test"""
        logger.info("Starting comprehensive backend load test...")
        
        await self.create_session()
        
        try:
            test_results = {
                "test_start_time": time.time(),
                "tests": {}
            }
            
            # Test 1: Health endpoints
            test_results["tests"]["health_endpoints"] = await self.test_health_endpoints()
            
            # Test 2: Database stress
            test_results["tests"]["database_stress"] = await self.test_database_stress()
            
            # Test 3: Video upload stress  
            test_results["tests"]["video_upload_stress"] = await self.test_video_upload_stress()
            
            test_results["test_end_time"] = time.time()
            test_results["total_test_time"] = round(test_results["test_end_time"] - test_results["test_start_time"], 2)
            
            return test_results
        
        finally:
            await self.close_session()

async def main():
    """Main test execution"""
    tester = BackendLoadTester()
    
    try:
        results = await tester.run_comprehensive_test()
        
        # Print summary
        print("\n" + "="*80)
        print("BACKEND LOAD TEST RESULTS")
        print("="*80)
        
        for test_name, test_results in results["tests"].items():
            print(f"\n📊 {test_name.upper()}")
            print("-" * 40)
            
            if test_name == "health_endpoints":
                for endpoint, data in test_results.items():
                    print(f"{endpoint}: {data['success_rate']:.1f}% success, avg {data['avg_response_time']:.3f}s")
            
            elif test_name == "database_stress":
                for endpoint, data in test_results.items():
                    print(f"{endpoint}: {data['successful']}/{data['concurrent_requests']} successful, {data['timeouts']} timeouts")
            
            elif test_name == "video_upload_stress":
                print(f"Uploads: {test_results['successful_uploads']}/{test_results['concurrent_uploads']} successful")
                print(f"Processing Status Present: {test_results['processing_status_rate']:.1f}%")
                print(f"Validation Errors: {test_results['validation_errors']}")
        
        print(f"\n⏱️  Total test time: {results['total_test_time']:.2f} seconds")
        print("="*80)
        
        # Save detailed results
        with open("load_test_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        print("📄 Detailed results saved to load_test_results.json")
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())