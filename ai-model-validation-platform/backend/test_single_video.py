#!/usr/bin/env python3
"""
Test the fixed detection pipeline on a single video file
"""

import sys
import logging
import json
from pathlib import Path
import cv2

# Add backend to path
sys.path.append(str(Path(__file__).parent))

from services.fixed_detection_service import FixedDetectionService

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_video(video_path: str):
    """Test detection on a single video file"""
    
    logger.info("=" * 80)
    logger.info(f"TESTING FIXED DETECTION ON: {video_path}")
    logger.info("=" * 80)
    
    # Check if file exists
    if not Path(video_path).exists():
        logger.error(f"Video file not found: {video_path}")
        return
    
    # Get video info
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    
    logger.info(f"Video Info:")
    logger.info(f"  - FPS: {fps}")
    logger.info(f"  - Total Frames: {frame_count}")
    logger.info(f"  - Duration: {duration:.2f} seconds")
    
    # Initialize detection service
    service = FixedDetectionService()
    
    # Load model
    logger.info("\nLoading YOLOv11l model...")
    if not service.load_model():
        logger.error("Failed to load model!")
        return
    
    logger.info("✅ Model loaded successfully")
    
    # Process video with different sample rates for thorough testing
    sample_rates = [1, 5, 15]  # Test with different sampling frequencies
    
    for sample_rate in sample_rates:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing with sample_rate={sample_rate} (every {sample_rate} frames)")
        logger.info(f"{'='*60}")
        
        # Process video
        result = service.process_video(
            video_path,
            "test_video_001",
            sample_rate=sample_rate
        )
        
        if result['error']:
            logger.error(f"❌ Error: {result['error']}")
            continue
        
        # Display results
        logger.info(f"\n📊 RESULTS:")
        logger.info(f"  Total frames: {result['summary']['total_frames']}")
        logger.info(f"  Processed frames: {result['summary']['processed_frames']}")
        logger.info(f"  Total detections: {result['summary']['total_detections']}")
        
        if result['summary']['detections_by_type']:
            logger.info(f"\n  Detections by type:")
            for vru_type, count in result['summary']['detections_by_type'].items():
                logger.info(f"    - {vru_type}: {count}")
        
        # Show sample detections
        if result['detections']:
            logger.info(f"\n  Sample detections (first 5):")
            for i, det in enumerate(result['detections'][:5], 1):
                bbox = det['bounding_box']
                logger.info(f"\n  Detection {i}:")
                logger.info(f"    - Type: {det['vru_type']}")
                logger.info(f"    - Frame: {det['frame_number']}")
                logger.info(f"    - Confidence: {bbox['confidence']:.4f}")
                logger.info(f"    - Position: x={bbox['x']:.1f}, y={bbox['y']:.1f}")
                logger.info(f"    - Size: {bbox['width']:.1f}x{bbox['height']:.1f}")
        else:
            logger.warning("  ⚠️ No detections found with current settings")
        
        # If we found detections, no need to test other sample rates
        if result['summary']['total_detections'] > 0:
            logger.info(f"\n✅ SUCCESS! Found {result['summary']['total_detections']} detections")
            
            # Save detailed results to file
            output_file = f"detection_results_{Path(video_path).stem}.json"
            with open(output_file, 'w') as f:
                json.dump({
                    'video_path': video_path,
                    'summary': result['summary'],
                    'sample_detections': result['detections'][:10] if result['detections'] else []
                }, f, indent=2)
            logger.info(f"📁 Detailed results saved to: {output_file}")
            break
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST COMPLETE")
    logger.info("=" * 80)

if __name__ == "__main__":
    # Test the specified video
    video_path = "/home/user/Testing/ai-model-validation-platform/backend/uploads/child-1-1-1.mp4"
    test_video(video_path)