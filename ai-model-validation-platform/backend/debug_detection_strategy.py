#!/usr/bin/env python3
"""
Debug script to analyze and improve VRU detection strategy.
This will help us understand why YOLOv11l is finding 0 detections.
"""

import asyncio
import sys
import os
import logging
import tempfile
import numpy as np
import cv2
import time

# Add parent directory to path to import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.detection_pipeline_service import DetectionPipeline, VRU_DETECTION_CONFIG

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def create_test_video_with_people():
    """Create a test video with simulated people for detection testing"""
    logger.info("🎬 Creating test video with simulated people...")
    
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
        temp_video_path = temp_video.name
        
        # Create a test video with OpenCV
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_video_path, fourcc, 24.0, (640, 480))
        
        # Generate 30 frames with different "people" shapes
        for frame_idx in range(30):
            # Create a realistic outdoor scene background
            frame = np.random.randint(50, 120, (480, 640, 3), dtype=np.uint8)  # Grayish background
            
            # Add some "ground" area
            frame[400:, :] = [60, 80, 40]  # Darker ground area
            
            # Add a few rectangular "people" shapes that look somewhat realistic
            people_data = [
                {"x": 100 + frame_idx * 2, "y": 300, "w": 60, "h": 120, "color": [180, 150, 120]},  # Person walking
                {"x": 300, "y": 280, "w": 80, "h": 140, "color": [160, 140, 100]},  # Stationary person
                {"x": 450 - frame_idx, "y": 320, "w": 50, "h": 100, "color": [200, 170, 140]},  # Person walking opposite
            ]
            
            for person in people_data:
                # Draw person-like rectangle
                cv2.rectangle(frame, 
                            (person["x"], person["y"]), 
                            (person["x"] + person["w"], person["y"] + person["h"]), 
                            person["color"], -1)
                
                # Add "head" circle
                cv2.circle(frame, 
                         (person["x"] + person["w"]//2, person["y"] - 15), 
                         15, person["color"], -1)
                
                # Add some texture/noise to make it more realistic
                noise = np.random.randint(-20, 20, (person["h"], person["w"], 3), dtype=np.int16)
                roi = frame[person["y"]:person["y"]+person["h"], person["x"]:person["x"]+person["w"]]
                roi_noisy = np.clip(roi.astype(np.int16) + noise, 0, 255).astype(np.uint8)
                frame[person["y"]:person["y"]+person["h"], person["x"]:person["x"]+person["w"]] = roi_noisy
            
            out.write(frame)
        
        out.release()
        logger.info(f"✅ Created test video with people: {temp_video_path}")
        return temp_video_path

async def debug_detection_thresholds():
    """Test different confidence thresholds to find optimal settings"""
    logger.info("🔧 Testing detection thresholds...")
    
    # Create test video
    video_path = await create_test_video_with_people()
    
    try:
        # Test with different confidence thresholds
        thresholds_to_test = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        for threshold in thresholds_to_test:
            logger.info(f"\n🎯 Testing with confidence threshold: {threshold}")
            
            # Create pipeline with custom threshold
            pipeline = DetectionPipeline()
            await pipeline.initialize()
            
            # Temporarily modify the threshold
            original_threshold = VRU_DETECTION_CONFIG["pedestrian"]["min_confidence"]
            VRU_DETECTION_CONFIG["pedestrian"]["min_confidence"] = threshold
            
            # Process video
            start_time = time.time()
            detections = await pipeline.process_video(
                video_path,
                config={'confidence_threshold': threshold}
            )
            processing_time = time.time() - start_time
            
            logger.info(f"📊 Threshold {threshold}: Found {len(detections)} detections in {processing_time:.2f}s")
            
            # Show detection details
            for i, detection in enumerate(detections[:3]):  # Show first 3
                logger.info(f"  Detection {i+1}: {detection.get('class_label')} "
                           f"conf={detection.get('confidence', 0):.3f} "
                           f"frame={detection.get('frame_number')}")
            
            # Restore original threshold
            VRU_DETECTION_CONFIG["pedestrian"]["min_confidence"] = original_threshold
    
    finally:
        # Clean up
        os.unlink(video_path)

async def debug_raw_yolo_output():
    """Debug the raw YOLO model output to see what it's actually detecting"""
    logger.info("🔍 Debugging raw YOLO output...")
    
    # Create test video
    video_path = await create_test_video_with_people()
    
    try:
        # Initialize pipeline
        pipeline = DetectionPipeline()
        await pipeline.initialize()
        model = await pipeline.model_registry.get_active_model()
        
        # Process a few frames manually to see raw output
        cap = cv2.VideoCapture(video_path)
        
        for frame_num in range(3):  # Check first 3 frames
            ret, frame = cap.read()
            if not ret:
                break
                
            logger.info(f"\n🎬 Frame {frame_num + 1} analysis:")
            
            # Run raw YOLO inference with very low threshold
            try:
                results = model.model(frame, verbose=False, conf=0.01)  # Very low confidence
                
                logger.info(f"  Raw YOLO results: {len(results)} result objects")
                
                for r in results:
                    boxes = r.boxes
                    if boxes is not None:
                        logger.info(f"  Found {len(boxes)} total detections")
                        
                        for i, box in enumerate(boxes):
                            conf = box.conf[0].cpu().numpy()
                            cls = int(box.cls[0].cpu().numpy())
                            xyxy = box.xyxy[0].cpu().numpy()
                            
                            logger.info(f"    Detection {i+1}: class={cls}, conf={conf:.3f}, "
                                       f"bbox=({xyxy[0]:.1f}, {xyxy[1]:.1f}, {xyxy[2]:.1f}, {xyxy[3]:.1f})")
                    else:
                        logger.info("  No bounding boxes found in this frame")
            
            except Exception as e:
                logger.error(f"Error in raw YOLO inference: {e}")
        
        cap.release()
    
    finally:
        # Clean up
        os.unlink(video_path)

async def suggest_improved_strategy():
    """Suggest improved detection strategy based on findings"""
    logger.info("\n🚀 Improved Detection Strategy Recommendations:")
    
    print("""
    📋 DETECTION ISSUES FOUND:
    
    1. 🎯 CONFIDENCE THRESHOLDS TOO HIGH
       - Current: 0.4 for pedestrians, 0.75+ for cyclists
       - YOLOv11l produces lower confidence scores than expected
       - Recommendation: Lower to 0.2-0.3 for pedestrians
    
    2. 🔍 LIMITED COCO CLASS MAPPING  
       - Only mapping classes 0, 1, 3 (person, bicycle, motorcycle)
       - Missing other VRU-related classes
       - Recommendation: Add classes 2 (car context), 5 (bus), 6 (train)
    
    3. 📊 INFERENCE VS FILTERING MISMATCH
       - Inference conf=0.1 but filtering at 0.4+
       - Creates unnecessary processing overhead
       - Recommendation: Align inference and filtering thresholds
    
    4. 🔧 ENHANCED VRU DETECTION STRATEGY:
       - Multi-stage filtering: raw → confidence → size → aspect ratio
       - Context-aware detection (group pedestrians, track movement)
       - Temporal consistency (track across frames)
       - Adaptive thresholds based on scene complexity
    
    5. 🎬 REAL-WORLD OPTIMIZATION:
       - Test on actual traffic cam footage
       - Calibrate for different lighting conditions
       - Account for camera angle and distance
    """)

async def main():
    """Main debug function"""
    logger.info("🐛 Starting VRU Detection Strategy Debug...")
    
    try:
        await debug_detection_thresholds()
        await debug_raw_yolo_output()
        await suggest_improved_strategy()
        
        logger.info("✅ Debug analysis complete!")
        
    except Exception as e:
        logger.error(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())