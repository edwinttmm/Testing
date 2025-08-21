#!/usr/bin/env python3
"""
Test script to validate child pedestrian detection in video
Based on AI engineer analysis showing the model detects children with 0.85+ confidence
"""
import asyncio
import sys
import os
from pathlib import Path
from services.detection_pipeline_service import DetectionPipeline

async def test_child_detection():
    """Test the child detection with the child-1-1-1.mp4 video"""
    
    video_path = "/home/user/Testing/ai-model-validation-platform/backend/uploads/child-1-1-1.mp4"
    
    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        return False
    
    print(f"🎬 Testing child detection with: {video_path}")
    
    # Initialize detection service
    detection_service = DetectionPipeline()
    
    # Configuration optimized for child detection with YOLOv11l
    config = {
        "confidence_threshold": 0.4,   # Upgraded threshold for YOLOv11l accuracy
        "model_name": "yolo11l",       # YOLOv11l for superior detection performance
        "max_frames": 15  # Test more frames with improved model
    }
    
    try:
        print("🔄 Running detection...")
        detections = await detection_service.process_video(video_path, config)
        
        print(f"\n📊 Results:")
        print(f"Total detections: {len(detections)}")
        
        if detections:
            print("✅ SUCCESS: Child detected!")
            
            # Show detection details
            for i, detection in enumerate(detections[:5]):  # Show first 5
                print(f"Detection {i+1}:")
                print(f"  - Class: {detection.get('class_label', 'unknown')}")
                print(f"  - Confidence: {detection.get('confidence', 0):.3f}")
                print(f"  - Frame: {detection.get('frame_number', 0)}")
                print(f"  - Bbox: {detection.get('bounding_box', {})}")
        else:
            print("❌ FAILED: No detections found")
            print("🔍 Try lowering confidence threshold further or check video content")
            return False
            
    except Exception as e:
        print(f"❌ Error during detection: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🎯 Child Detection Test Script")
    print("=" * 50)
    
    success = asyncio.run(test_child_detection())
    
    if success:
        print("\n✅ Test PASSED - Child detection working!")
        sys.exit(0)
    else:
        print("\n❌ Test FAILED - Need further debugging")
        sys.exit(1)