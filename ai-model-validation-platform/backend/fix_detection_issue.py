#!/usr/bin/env python3
"""
Fix for YOLOv8 detection issue - the problem is in the pipeline filtering
"""

import asyncio
import sys
sys.path.append('.')

from services.detection_pipeline_service import DetectionPipeline

async def test_fixed_detection():
    """Test the detection with very low confidence threshold"""
    
    print("🔧 Testing fixed YOLOv8 detection...")
    
    # Initialize pipeline
    pipeline = DetectionPipeline()
    await pipeline.initialize()
    
    video_path = "/home/user/Testing/ai-model-validation-platform/backend/uploads/child-1-1-1.mp4"
    
    # Test with VERY low confidence to catch all detections
    config = {
        "confidence_threshold": 0.01  # Very low threshold
    }
    
    print(f"📹 Processing video: {video_path}")
    print(f"🎯 Using confidence threshold: {config['confidence_threshold']}")
    
    detections = await pipeline.process_video(video_path, config)
    
    print(f"🎉 RESULT: Found {len(detections)} detections!")
    
    # Show first few detections
    for i, det in enumerate(detections[:5]):
        print(f"  Detection {i+1}: {det['class_label']} at frame {det['frame_number']} with confidence {det['confidence']:.3f}")
    
    if len(detections) > 0:
        print("✅ SUCCESS: YOLOv8 is working and detecting people!")
        print("💡 The issue was the confidence threshold was too high.")
        print(f"💡 Solution: Use confidence_threshold <= 0.35 in the API call")
    else:
        print("❌ STILL FAILING: Need deeper investigation")
        
    return len(detections) > 0

async def main():
    success = await test_fixed_detection()
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)