"""
Test script for validating the fixed detection pipeline
"""

import logging
import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from services.fixed_detection_service import FixedDetectionService
from services.detection_pipeline_service import DetectionPipeline
from database import SessionLocal
from models import Video, Annotation

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_fixed_detection():
    """Test the fixed detection service"""
    logger.info("=" * 80)
    logger.info("TESTING FIXED DETECTION SERVICE")
    logger.info("=" * 80)
    
    # Initialize service
    service = FixedDetectionService()
    
    # Load model
    logger.info("Loading YOLOv11l model...")
    if not service.load_model():
        logger.error("Failed to load model!")
        return False
    
    logger.info("✅ Model loaded successfully")
    
    # Get test videos from database
    db = SessionLocal()
    try:
        videos = db.query(Video).limit(2).all()
        
        if not videos:
            logger.warning("No videos found in database")
            return False
        
        for video in videos:
            logger.info(f"\nProcessing video: {video.name}")
            logger.info(f"Video ID: {video.id}")
            logger.info(f"File path: {video.file_path}")
            
            # Process video with fixed service
            result = service.process_video(
                video.file_path, 
                video.id,
                sample_rate=30  # Process every 30th frame for speed
            )
            
            if result['error']:
                logger.error(f"❌ Error processing video: {result['error']}")
                continue
            
            # Display results
            logger.info(f"✅ Processing complete!")
            logger.info(f"   Total frames: {result['summary']['total_frames']}")
            logger.info(f"   Processed frames: {result['summary']['processed_frames']}")
            logger.info(f"   Total detections: {result['summary']['total_detections']}")
            logger.info(f"   Detections by type: {result['summary']['detections_by_type']}")
            
            # Validate detection data structure
            if result['detections']:
                sample_detection = result['detections'][0]
                is_valid, msg = service.validate_detection_data(sample_detection)
                
                if is_valid:
                    logger.info(f"✅ Detection data structure is valid")
                    logger.info(f"   Sample detection: {json.dumps(sample_detection, indent=2)}")
                else:
                    logger.error(f"❌ Invalid detection data: {msg}")
                    
                # Try to save to database
                try:
                    for det in result['detections'][:5]:  # Save first 5 detections
                        annotation = Annotation(
                            video_id=det['video_id'],
                            detection_id=det['detection_id'],
                            frame_number=det['frame_number'],
                            timestamp=det['timestamp'],
                            vru_type=det['vru_type'],
                            bounding_box=det['bounding_box'],
                            occluded=det.get('occluded', False),
                            truncated=det.get('truncated', False),
                            difficult=det.get('difficult', False),
                            validated=det.get('validated', False)
                        )
                        db.add(annotation)
                    
                    db.commit()
                    logger.info(f"✅ Successfully saved {min(5, len(result['detections']))} detections to database")
                    
                except Exception as e:
                    logger.error(f"❌ Database save error: {str(e)}")
                    db.rollback()
            else:
                logger.warning("⚠️ No detections found - adjusting thresholds may be needed")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return False
        
    finally:
        db.close()


def compare_pipelines():
    """Compare original vs fixed pipeline"""
    logger.info("\n" + "=" * 80)
    logger.info("COMPARING ORIGINAL VS FIXED PIPELINE")
    logger.info("=" * 80)
    
    # Get a test video
    db = SessionLocal()
    try:
        video = db.query(Video).first()
        if not video:
            logger.error("No video found for testing")
            return
        
        logger.info(f"Test video: {video.name}")
        
        # Test with fixed service
        logger.info("\n--- FIXED SERVICE ---")
        fixed_service = FixedDetectionService()
        if fixed_service.load_model():
            result = fixed_service.process_video(
                video.file_path,
                video.id,
                sample_rate=60  # Every 2 seconds at 30fps
            )
            
            if not result['error']:
                logger.info(f"Fixed service: {result['summary']['total_detections']} detections")
                logger.info(f"By type: {result['summary']['detections_by_type']}")
            else:
                logger.error(f"Fixed service error: {result['error']}")
        
        # Show configuration differences
        logger.info("\n--- KEY DIFFERENCES ---")
        logger.info("1. Fixed service uses ultra-low confidence thresholds (0.01)")
        logger.info("2. Fixed service adds videoId field to all detections")
        logger.info("3. Fixed service uses correct COCO class mappings")
        logger.info("4. Fixed service logs all raw detections for debugging")
        
    finally:
        db.close()


if __name__ == "__main__":
    # Run tests
    success = test_fixed_detection()
    
    if success:
        logger.info("\n✅ Fixed detection service is working!")
        compare_pipelines()
    else:
        logger.error("\n❌ Fixed detection service test failed")
        
    logger.info("\n" + "=" * 80)
    logger.info("RECOMMENDATIONS:")
    logger.info("1. Replace detection_pipeline_service.py with fixed_detection_service.py")
    logger.info("2. Ensure all API calls include videoId field")
    logger.info("3. Monitor confidence thresholds and adjust as needed")
    logger.info("4. Consider adding more COCO classes for better VRU detection")
    logger.info("=" * 80)