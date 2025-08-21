#!/usr/bin/env python3
"""
Test script to verify the frame_detections undefined variable fix.
This will trigger the detection pipeline to process a video and verify
that the NameError: name 'frame_detections' is not defined is resolved.
"""

import asyncio
import sys
import os
import logging
import tempfile
import numpy as np
import cv2

# Add parent directory to path to import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.detection_pipeline_service import DetectionPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_detection_fix():
    """Test the detection pipeline with a minimal video to trigger the fix."""
    logger.info("🧪 Testing detection pipeline fix...")
    
    try:
        # Create a minimal test video
        logger.info("📹 Creating test video...")
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video_path = temp_video.name
            
            # Create a simple test video with OpenCV
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(temp_video_path, fourcc, 24.0, (640, 480))
            
            # Generate 10 frames of a simple blue video (no objects to detect)
            for i in range(10):
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                frame[:, :] = [255, 0, 0]  # Blue frame
                out.write(frame)
            
            out.release()
            logger.info(f"✅ Created test video: {temp_video_path}")
        
        # Initialize detection pipeline
        logger.info("🔧 Initializing detection pipeline...")
        pipeline = DetectionPipeline()
        await pipeline.initialize()
        
        # Process the video - this should trigger the area where frame_detections was undefined
        logger.info("🎬 Processing test video...")
        detections = await pipeline.process_video(
            temp_video_path,
            config={'confidence_threshold': 0.4}
        )
        
        # The key test: if we get here without NameError, the fix worked!
        logger.info(f"✅ SUCCESS: Detection completed with {len(detections)} detections")
        logger.info("🎉 Fix verified: No 'frame_detections' undefined error!")
        
        # Clean up
        os.unlink(temp_video_path)
        
        return True
        
    except NameError as e:
        if "frame_detections" in str(e):
            logger.error(f"❌ FAILED: frame_detections undefined error still exists: {e}")
            return False
        else:
            raise
    except Exception as e:
        logger.error(f"⚠️ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_detection_fix())
    if result:
        print("🟢 Test PASSED: frame_detections fix is working!")
        sys.exit(0)
    else:
        print("🔴 Test FAILED: frame_detections fix is not working!")
        sys.exit(1)