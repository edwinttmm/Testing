#!/usr/bin/env python3
"""
Test the improved VRU detection strategy.
This will verify that our optimizations work properly.
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

async def create_realistic_test_video():
    """Create a more realistic test video with clear person-like objects"""
    logger.info("🎬 Creating realistic test video...")
    
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
        temp_video_path = temp_video.name
        
        # Create higher quality video
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_video_path, fourcc, 24.0, (1280, 720))  # Higher resolution
        
        # Generate frames with more realistic people
        for frame_idx in range(20):
            # Create realistic outdoor scene
            frame = np.random.randint(80, 120, (720, 1280, 3), dtype=np.uint8)  # Realistic background
            
            # Add ground/pavement area
            frame[500:, :] = [90, 90, 85]  # Pavement color
            
            # Add more realistic people with proper proportions
            people = [
                {"x": 200 + frame_idx * 3, "y": 350, "w": 80, "h": 180, "type": "adult"},
                {"x": 600, "y": 380, "w": 60, "h": 140, "type": "child"},
                {"x": 900 - frame_idx * 2, "y": 360, "w": 85, "h": 190, "type": "adult"},
            ]
            
            for person in people:
                # More realistic person colors and shapes
                if person["type"] == "adult":
                    body_color = [70, 100, 150]  # Clothing colors
                    head_color = [200, 180, 160]  # Skin tone
                else:  # child
                    body_color = [180, 80, 90]   # Bright clothing
                    head_color = [210, 190, 170]  # Lighter skin
                
                # Draw body (rectangle)
                cv2.rectangle(frame,
                            (person["x"], person["y"]),
                            (person["x"] + person["w"], person["y"] + person["h"]),
                            body_color, -1)
                
                # Draw head (oval/circle)
                head_radius = person["w"] // 4
                cv2.circle(frame,
                         (person["x"] + person["w"]//2, person["y"] - head_radius),
                         head_radius, head_color, -1)
                
                # Add some detail - arms
                arm_width = 15
                cv2.rectangle(frame,
                            (person["x"] - arm_width, person["y"] + 20),
                            (person["x"], person["y"] + person["h"]//2),
                            body_color, -1)
                cv2.rectangle(frame,
                            (person["x"] + person["w"], person["y"] + 20),
                            (person["x"] + person["w"] + arm_width, person["y"] + person["h"]//2),
                            body_color, -1)
                
                # Add shadows for realism
                shadow_color = [60, 60, 55]
                cv2.ellipse(frame,
                          (person["x"] + person["w"]//2, person["y"] + person["h"] + 10),
                          (person["w"]//2, 15), 0, 0, 180, shadow_color, -1)
            
            # Add some noise for realism
            noise = np.random.normal(0, 5, frame.shape).astype(np.int16)
            frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            
            out.write(frame)
        
        out.release()
        logger.info(f"✅ Created realistic test video: {temp_video_path}")
        return temp_video_path

async def test_improved_detection():
    """Test the improved detection pipeline"""
    logger.info("🔧 Testing improved VRU detection...")
    
    # Create test video
    video_path = await create_realistic_test_video()
    
    try:
        # Test with improved pipeline
        pipeline = DetectionPipeline()
        await pipeline.initialize()
        
        logger.info("🎬 Processing video with improved detection...")
        detections = await pipeline.process_video(
            video_path,
            config={'confidence_threshold': 0.25}  # Use our new lower threshold
        )
        
        logger.info(f"📊 RESULTS: Found {len(detections)} detections")
        
        if len(detections) > 0:
            logger.info("✅ SUCCESS: Improved detection pipeline is working!")
            
            # Show detection details
            for i, detection in enumerate(detections[:5]):  # Show first 5
                logger.info(f"  Detection {i+1}: "
                           f"{detection.get('class_label', 'unknown')} "
                           f"confidence={detection.get('confidence', 0):.3f} "
                           f"frame={detection.get('frame_number', 0)}")
        else:
            logger.warning("⚠️ Still no detections found. Further optimization needed.")
            
        return len(detections)
        
    finally:
        # Clean up
        os.unlink(video_path)

async def test_confidence_thresholds():
    """Test different confidence thresholds to find optimal settings"""
    logger.info("🎯 Testing optimal confidence thresholds...")
    
    video_path = await create_realistic_test_video()
    
    try:
        thresholds = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3]
        results = {}
        
        for threshold in thresholds:
            logger.info(f"Testing threshold: {threshold}")
            
            pipeline = DetectionPipeline()
            await pipeline.initialize()
            
            detections = await pipeline.process_video(
                video_path,
                config={'confidence_threshold': threshold}
            )
            
            results[threshold] = len(detections)
            logger.info(f"  Threshold {threshold}: {len(detections)} detections")
        
        # Find optimal threshold
        best_threshold = max(results, key=results.get)
        logger.info(f"🏆 Best threshold: {best_threshold} with {results[best_threshold]} detections")
        
        return results
        
    finally:
        os.unlink(video_path)

async def main():
    """Main test function"""
    logger.info("🚀 Starting Improved VRU Detection Tests...")
    
    try:
        # Test basic functionality
        detection_count = await test_improved_detection()
        
        # Test threshold optimization
        threshold_results = await test_confidence_thresholds()
        
        # Summary
        logger.info("\n📋 TEST SUMMARY:")
        logger.info(f"  Detection Count: {detection_count}")
        logger.info(f"  Threshold Results: {threshold_results}")
        
        if detection_count > 0:
            logger.info("🎉 SUCCESS: Improved VRU detection is working!")
        else:
            logger.warning("⚠️ ISSUE: Still need further optimization")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())