#!/usr/bin/env python3
"""
Direct YOLO ML Detection Test

This script directly tests the YOLO model against the Child.mp4 file 
to verify ML dependencies are working and we can detect objects.
"""

import sys
import os
from pathlib import Path

def test_direct_yolo_detection():
    """Test YOLO detection directly"""
    try:
        # Import YOLO
        from ultralytics import YOLO
        print("✅ ultralytics imported successfully")
        
        # Load YOLO model
        model = YOLO('yolov8n.pt')
        print("✅ YOLOv8 model loaded successfully")
        
        # Find the video file
        video_path = "/home/rigade/Testing/ai-model-validation-platform/backend/uploads/425c1f63-7ea9-4140-b755-b50af7047abb.mp4"
        
        if not Path(video_path).exists():
            print(f"❌ Video file not found: {video_path}")
            return False
        
        print(f"✅ Video file found: {video_path}")
        
        # Run YOLO detection on the video
        print("🔍 Running YOLO detection...")
        results = model(video_path)
        
        detection_count = 0
        frame_count = 0
        
        for frame_result in results:
            frame_count += 1
            if len(frame_result.boxes) > 0:
                detection_count += len(frame_result.boxes)
                print(f"Frame {frame_count}: Found {len(frame_result.boxes)} detections")
                
                # Show first few detections details
                for i, box in enumerate(frame_result.boxes[:3]):  # First 3 detections
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])
                    class_name = model.names[class_id]
                    print(f"  Detection {i+1}: {class_name} (confidence: {confidence:.3f})")
        
        print(f"\n✅ YOLO Detection Results:")
        print(f"   - Total frames processed: {frame_count}")
        print(f"   - Total detections found: {detection_count}")
        
        if detection_count > 0:
            print(f"✅ SUCCESS: ML detection is working! Found {detection_count} detections")
            return True
        else:
            print("❌ FAILURE: No detections found - there might be an issue")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import ultralytics: {e}")
        return False
    except Exception as e:
        print(f"❌ Error during detection: {e}")
        return False

if __name__ == "__main__":
    success = test_direct_yolo_detection()
    sys.exit(0 if success else 1)