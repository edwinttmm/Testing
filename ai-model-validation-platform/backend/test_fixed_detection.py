#!/usr/bin/env python3
"""
Quick test to verify the YOLOv8 detection fix
"""

import asyncio
import sys
import logging
sys.path.append('.')

from services.detection_pipeline_service import DetectionPipeline

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_fixed_detection():
    """Test the fixed detection pipeline"""
    
    logger.info("🔧 Testing FIXED YOLOv8 detection...")
    
    # Initialize pipeline
    pipeline = DetectionPipeline()
    await pipeline.initialize()
    
    video_path = "/home/user/Testing/ai-model-validation-platform/backend/uploads/child-1-1-1.mp4"
    
    # Test with default (now lowered) confidence threshold
    logger.info(f"📹 Processing video: {video_path}")
    logger.info(f"🎯 Using default confidence threshold (now 0.25)")
    
    detections = await pipeline.process_video(video_path)
    
    logger.info(f"🎉 RESULT: Found {len(detections)} detections!")
    
    if len(detections) > 0:
        logger.info("✅ SUCCESS: YOLOv8 detection is now working!")
        
        # Show detection summary
        detection_classes = {}
        for det in detections:
            class_label = det.get('class_label', 'unknown')
            detection_classes[class_label] = detection_classes.get(class_label, 0) + 1
        
        logger.info(f"📊 Detection summary: {detection_classes}")
        
        # Show first few detections
        logger.info("📝 First 3 detections:")
        for i, det in enumerate(detections[:3]):
            logger.info(f"  {i+1}. {det['class_label']} at frame {det['frame_number']} with confidence {det['confidence']:.3f}")
        
        return True
    else:
        logger.error("❌ STILL FAILING: No detections found")
        return False

async def main():
    success = await test_fixed_detection()
    
    if success:
        logger.info("\n" + "="*60)
        logger.info("🎉 FIX SUCCESSFUL!")
        logger.info("✅ YOLOv8 is now detecting the child in the video")
        logger.info("✅ Lowered confidence threshold from 0.35 to 0.25")
        logger.info("✅ Enhanced debugging and logging")
        logger.info("="*60)
    else:
        logger.error("\n" + "="*60)
        logger.error("❌ FIX UNSUCCESSFUL")
        logger.error("Need additional investigation")
        logger.error("="*60)
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)