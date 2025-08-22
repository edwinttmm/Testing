#!/usr/bin/env python3
"""
End-to-End Detection Storage Test
Verifies that detection results are properly stored in database with screenshots
"""
import asyncio
import aiohttp
import json
import logging
import sys
import os
from pathlib import Path
from datetime import datetime

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from database import SessionLocal, get_db
from models import DetectionEvent, TestSession, Video

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DetectionStorageTest:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.test_video_id = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_available_video(self):
        """Get first available video for testing"""
        try:
            async with self.session.get(f"{self.base_url}/api/videos") as response:
                if response.status != 200:
                    logger.error(f"❌ Cannot get video list: {response.status}")
                    return None
                
                videos = await response.json()
                if not videos:
                    logger.error("❌ No videos available for testing")
                    return None
                
                test_video = videos[0]
                self.test_video_id = test_video["id"]
                logger.info(f"📹 Using test video: {test_video.get('filename', 'unknown')} (ID: {self.test_video_id})")
                return test_video
                
        except Exception as e:
            logger.error(f"❌ Error getting videos: {e}")
            return None
    
    async def run_detection_pipeline(self, video_id):
        """Run detection pipeline on video"""
        try:
            payload = {
                "video_id": video_id,
                "confidence_threshold": 0.4,
                "nms_threshold": 0.5,
                "target_classes": ["pedestrian", "cyclist", "motorcyclist"],
                "model_name": "yolo11l"
            }
            
            logger.info("🚀 Running detection pipeline...")
            async with self.session.post(
                f"{self.base_url}/api/detection/pipeline/run",
                json=payload,
                timeout=120
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"✅ Detection completed: {result.get('total_detections', 0)} detections")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Detection failed: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Detection pipeline error: {e}")
            return None
    
    async def check_database_storage(self, video_id):
        """Check if detections were stored in database"""
        logger.info("🔍 Checking database storage...")
        
        db = SessionLocal()
        try:
            # Check for test sessions
            test_sessions = db.query(TestSession).filter(
                TestSession.video_id == video_id
            ).all()
            
            if not test_sessions:
                logger.error("❌ No test sessions found in database")
                return False
            
            logger.info(f"✅ Found {len(test_sessions)} test session(s)")
            
            # Check for detection events
            detection_count = 0
            screenshot_count = 0
            bbox_count = 0
            
            for session in test_sessions:
                detections = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == session.id
                ).all()
                
                detection_count += len(detections)
                
                for detection in detections:
                    # Check for screenshot paths
                    if detection.screenshot_path:
                        screenshot_count += 1
                    
                    # Check for bounding box data
                    if (detection.bounding_box_x is not None and 
                        detection.bounding_box_y is not None):
                        bbox_count += 1
            
            logger.info(f"📊 Database storage results:")
            logger.info(f"   - Detection events: {detection_count}")
            logger.info(f"   - With screenshots: {screenshot_count}")
            logger.info(f"   - With bounding boxes: {bbox_count}")
            
            if detection_count == 0:
                logger.error("❌ No detection events found in database!")
                return False
            
            if screenshot_count == 0:
                logger.warning("⚠️  No screenshots captured")
            
            if bbox_count == 0:
                logger.error("❌ No bounding box data stored!")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Database check error: {e}")
            return False
        finally:
            db.close()
    
    async def check_api_retrieval(self, video_id):
        """Check if detections can be retrieved via API"""
        try:
            logger.info("🔍 Testing API retrieval...")
            
            async with self.session.get(f"{self.base_url}/api/videos/{video_id}/detections") as response:
                if response.status != 200:
                    logger.error(f"❌ API retrieval failed: {response.status}")
                    return False
                
                result = await response.json()
                total_detections = result.get('total_detections', 0)
                detections = result.get('detections', [])
                
                if total_detections == 0:
                    logger.error("❌ API returned no detections")
                    return False
                
                logger.info(f"✅ API retrieved {total_detections} detections")
                
                # Check detection data completeness
                complete_detections = 0
                for detection in detections[:3]:  # Check first 3
                    has_bbox = detection.get('bounding_box') is not None
                    has_screenshot = detection.get('has_visual_evidence', False)
                    has_frame = detection.get('frame_number') is not None
                    
                    if has_bbox and has_frame:
                        complete_detections += 1
                    
                    logger.info(f"   Detection {detection.get('detection_id', 'unknown')}:")
                    logger.info(f"     - Confidence: {detection.get('confidence', 0):.3f}")
                    logger.info(f"     - Frame: {detection.get('frame_number', 'none')}")
                    logger.info(f"     - Bounding box: {'✅' if has_bbox else '❌'}")
                    logger.info(f"     - Screenshot: {'✅' if has_screenshot else '❌'}")
                
                success_rate = (complete_detections / min(len(detections), 3)) * 100
                logger.info(f"📈 Detection completeness: {success_rate:.1f}%")
                
                return success_rate >= 50  # At least 50% complete
                
        except Exception as e:
            logger.error(f"❌ API retrieval error: {e}")
            return False
    
    async def check_screenshot_files(self):
        """Check if screenshot files exist on disk"""
        try:
            logger.info("📸 Checking screenshot files...")
            
            screenshots_dir = Path("/app/screenshots")
            if not screenshots_dir.exists():
                logger.error("❌ Screenshots directory does not exist!")
                return False
            
            # Count screenshot files
            screenshot_files = list(screenshots_dir.glob("detection_*.jpg"))
            zoom_files = list(screenshots_dir.glob("detection_*_zoom.jpg"))
            
            logger.info(f"📁 Screenshot files found:")
            logger.info(f"   - Full screenshots: {len(screenshot_files)}")
            logger.info(f"   - Zoomed screenshots: {len(zoom_files)}")
            
            if len(screenshot_files) == 0:
                logger.warning("⚠️  No screenshot files found on disk")
                return False
            
            # Check file sizes
            valid_files = 0
            for file_path in screenshot_files[:3]:  # Check first 3
                if file_path.stat().st_size > 1000:  # At least 1KB
                    valid_files += 1
                    logger.info(f"   ✅ {file_path.name}: {file_path.stat().st_size} bytes")
                else:
                    logger.warning(f"   ⚠️  {file_path.name}: {file_path.stat().st_size} bytes (too small)")
            
            return valid_files > 0
            
        except Exception as e:
            logger.error(f"❌ Screenshot check error: {e}")
            return False
    
    async def run_comprehensive_test(self):
        """Run complete detection storage test"""
        logger.info("🧪 Starting comprehensive detection storage test...")
        
        # Get test video
        video = await self.get_available_video()
        if not video:
            return False
        
        # Run detection pipeline
        detection_result = await self.run_detection_pipeline(self.test_video_id)
        if not detection_result:
            return False
        
        # Allow some time for storage operations to complete
        await asyncio.sleep(2)
        
        # Check database storage
        db_check = await self.check_database_storage(self.test_video_id)
        
        # Check API retrieval
        api_check = await self.check_api_retrieval(self.test_video_id)
        
        # Check screenshot files
        file_check = await self.check_screenshot_files()
        
        # Summary
        logger.info("📊 TEST RESULTS SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Database Storage:  {'✅ PASS' if db_check else '❌ FAIL'}")
        logger.info(f"API Retrieval:     {'✅ PASS' if api_check else '❌ FAIL'}")
        logger.info(f"Screenshot Files:  {'✅ PASS' if file_check else '❌ FAIL'}")
        
        overall_success = db_check and api_check and file_check
        logger.info(f"Overall Result:    {'🎉 SUCCESS' if overall_success else '💥 FAILED'}")
        
        if overall_success:
            logger.info("\n🎯 Detection storage is working correctly!")
            logger.info("Users should now see:")
            logger.info("- Detection records in datasets")
            logger.info("- Bounding box coordinates")
            logger.info("- Screenshot evidence files")
            logger.info("- Complete annotation data")
        else:
            logger.error("\n❌ Detection storage has issues that need to be resolved.")
        
        return overall_success

async def main():
    """Run the detection storage test"""
    print("🔬 Detection Storage End-to-End Test")
    print("=" * 50)
    
    async with DetectionStorageTest() as test:
        # Test backend connectivity first
        try:
            async with test.session.get(f"{test.base_url}/") as response:
                if response.status != 200:
                    logger.error(f"❌ Backend not available (status: {response.status})")
                    return False
        except Exception as e:
            logger.error(f"❌ Backend connection failed: {e}")
            return False
        
        logger.info("✅ Backend connected")
        
        # Run comprehensive test
        success = await test.run_comprehensive_test()
        return success

if __name__ == "__main__":
    print("Testing detection result storage and visual evidence capture...")
    print(f"Started at: {datetime.now()}")
    print()
    
    success = asyncio.run(main())
    
    if success:
        print("\n🎉 All tests passed! Detection storage is working correctly.")
        print("\nNext steps:")
        print("1. Run migration script if tables need updating")
        print("2. Test with real videos in production")
        print("3. Verify frontend displays detection data correctly")
    else:
        print("\n❌ Tests failed. Check logs above for specific issues.")
        print("\nPossible fixes:")
        print("1. Run database migration: python migrate_detection_events.py")
        print("2. Check screenshot directory permissions")
        print("3. Verify ML models are working correctly")
    
    exit(0 if success else 1)