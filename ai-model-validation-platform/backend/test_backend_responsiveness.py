#!/usr/bin/env python3
"""
Backend Responsiveness Test Script
Tests if the backend remains responsive during detection pipeline processing
"""
import asyncio
import aiohttp
import time
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BackendResponsivenessTest:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def ping_endpoint(self, endpoint="/", timeout=5):
        """Test if endpoint responds within timeout"""
        try:
            start_time = time.time()
            async with self.session.get(f"{self.base_url}{endpoint}", timeout=timeout) as response:
                response_time = (time.time() - start_time) * 1000
                return response.status, response_time
        except asyncio.TimeoutError:
            return 408, timeout * 1000
        except Exception as e:
            logger.error(f"Error pinging {endpoint}: {e}")
            return 500, timeout * 1000
    
    async def start_detection_processing(self, video_id):
        """Start detection pipeline processing (non-blocking)"""
        try:
            payload = {
                "video_id": video_id,
                "confidence_threshold": 0.4,
                "nms_threshold": 0.5,
                "target_classes": ["pedestrian", "cyclist", "motorcyclist"],
                "model_name": "yolo11l"
            }
            
            async with self.session.post(
                f"{self.base_url}/api/detection/pipeline/run",
                json=payload,
                timeout=60  # Long timeout for detection
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return True, result
                else:
                    text = await response.text()
                    return False, f"Status {response.status}: {text}"
                    
        except Exception as e:
            return False, f"Detection request failed: {e}"
    
    async def monitor_responsiveness(self, duration_seconds=30, check_interval=1):
        """Monitor backend responsiveness during detection"""
        logger.info(f"🔍 Monitoring backend responsiveness for {duration_seconds}s")
        
        endpoints_to_test = [
            "/",
            "/api/projects",
            "/dashboard/stats",
        ]
        
        results = []
        start_time = time.time()
        
        while (time.time() - start_time) < duration_seconds:
            timestamp = time.time()
            
            for endpoint in endpoints_to_test:
                status, response_time = await self.ping_endpoint(endpoint, timeout=3)
                
                results.append({
                    "timestamp": timestamp,
                    "endpoint": endpoint,
                    "status_code": status,
                    "response_time_ms": response_time,
                    "responsive": status == 200 and response_time < 3000
                })
                
                if status == 200:
                    logger.info(f"✅ {endpoint}: {response_time:.0f}ms")
                else:
                    logger.warning(f"❌ {endpoint}: {status} ({response_time:.0f}ms)")
            
            await asyncio.sleep(check_interval)
        
        return results
    
    async def test_concurrent_responsiveness(self):
        """Test responsiveness while detection is running concurrently"""
        logger.info("🚀 Starting concurrent responsiveness test")
        
        # First, get available videos
        try:
            async with self.session.get(f"{self.base_url}/api/videos") as response:
                if response.status != 200:
                    logger.error("❌ Cannot get video list")
                    return False
                    
                videos = await response.json()
                if not videos:
                    logger.error("❌ No videos available for testing")
                    return False
                
                test_video = videos[0]
                logger.info(f"🎬 Using test video: {test_video.get('filename', 'unknown')}")
                
        except Exception as e:
            logger.error(f"❌ Failed to get video list: {e}")
            return False
        
        # Start concurrent tasks
        detection_task = asyncio.create_task(
            self.start_detection_processing(test_video["id"])
        )
        
        monitoring_task = asyncio.create_task(
            self.monitor_responsiveness(duration_seconds=20)
        )
        
        # Wait for both tasks
        try:
            detection_result, monitoring_results = await asyncio.gather(
                detection_task, monitoring_task, return_exceptions=True
            )
            
            # Analyze results
            self.analyze_results(detection_result, monitoring_results)
            return True
            
        except Exception as e:
            logger.error(f"❌ Concurrent test failed: {e}")
            return False
    
    def analyze_results(self, detection_result, monitoring_results):
        """Analyze test results and report findings"""
        logger.info("📊 RESPONSIVENESS TEST RESULTS")
        logger.info("=" * 50)
        
        # Detection results
        detection_success, detection_data = detection_result
        if detection_success:
            logger.info(f"✅ Detection completed successfully")
            if isinstance(detection_data, dict):
                total_detections = detection_data.get('total_detections', 0)
                logger.info(f"   - Total detections: {total_detections}")
        else:
            logger.error(f"❌ Detection failed: {detection_data}")
        
        # Responsiveness results
        if isinstance(monitoring_results, list):
            total_checks = len(monitoring_results)
            responsive_checks = sum(1 for r in monitoring_results if r['responsive'])
            responsiveness_rate = (responsive_checks / total_checks) * 100
            
            avg_response_time = sum(r['response_time_ms'] for r in monitoring_results) / total_checks
            max_response_time = max(r['response_time_ms'] for r in monitoring_results)
            
            logger.info(f"📈 Responsiveness Metrics:")
            logger.info(f"   - Total checks: {total_checks}")
            logger.info(f"   - Responsive checks: {responsive_checks} ({responsiveness_rate:.1f}%)")
            logger.info(f"   - Average response time: {avg_response_time:.0f}ms")
            logger.info(f"   - Maximum response time: {max_response_time:.0f}ms")
            
            # Success criteria
            if responsiveness_rate >= 90 and avg_response_time <= 1000:
                logger.info("🎉 PASS: Backend remained responsive during detection!")
            else:
                logger.warning("⚠️  FAIL: Backend responsiveness degraded during detection")
        else:
            logger.error(f"❌ Monitoring failed: {monitoring_results}")

async def main():
    """Run the responsiveness test"""
    async with BackendResponsivenessTest() as test:
        # Test basic connectivity first
        status, response_time = await test.ping_endpoint("/")
        if status != 200:
            logger.error(f"❌ Backend not available (status: {status})")
            return False
        
        logger.info(f"✅ Backend available ({response_time:.0f}ms)")
        
        # Run the concurrent test
        success = await test.test_concurrent_responsiveness()
        return success

if __name__ == "__main__":
    print("🧪 Backend Responsiveness Test")
    print("Testing if backend stays responsive during ML detection processing...")
    print()
    
    success = asyncio.run(main())
    
    if success:
        print("\n✅ Test completed successfully")
    else:
        print("\n❌ Test failed")
    
    exit(0 if success else 1)