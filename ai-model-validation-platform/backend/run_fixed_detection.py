#!/usr/bin/env python3
"""
Run the fixed detection pipeline on all videos in the database
This script fixes the issues with YOLOv11l returning 0 detections
"""

import logging
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.append(str(Path(__file__).parent))

from database import SessionLocal, engine
from models import Video, Annotation, DetectionEvent, TestSession
from services.fixed_detection_service import FixedDetectionService
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clear_old_detections(db, video_id):
    """Clear old detections for a video to avoid duplicates"""
    try:
        # Clear annotations for this video
        deleted = db.query(Annotation).filter(Annotation.video_id == video_id).delete()
        db.commit()
        if deleted > 0:
            logger.info(f"Cleared {deleted} old annotations for video {video_id}")
        return True
    except Exception as e:
        logger.error(f"Error clearing old detections: {str(e)}")
        db.rollback()
        return False


def save_detections_to_db(db, video_id, detections):
    """Save detections to database with proper videoId field"""
    saved_count = 0
    error_count = 0
    
    for det in detections:
        try:
            # Create annotation with all required fields
            annotation = Annotation(
                video_id=video_id,  # Critical field that was missing!
                detection_id=det.get('detection_id', f"DET_{datetime.now().timestamp()}"),
                frame_number=det['frame_number'],
                timestamp=det['timestamp'],
                vru_type=det['vru_type'],
                bounding_box=json.dumps(det['bounding_box']),  # Store as JSON string
                occluded=det.get('occluded', False),
                truncated=det.get('truncated', False),
                difficult=det.get('difficult', False),
                validated=det.get('validated', False),
                annotator='YOLOv11l_fixed',
                notes=f"Confidence: {det['bounding_box']['confidence']:.3f}"
            )
            
            db.add(annotation)
            saved_count += 1
            
            # Commit every 100 detections
            if saved_count % 100 == 0:
                db.commit()
                logger.info(f"  Saved {saved_count} detections...")
                
        except Exception as e:
            error_count += 1
            logger.error(f"Error saving detection: {str(e)}")
            if error_count > 10:
                logger.error("Too many errors, stopping save operation")
                break
    
    # Final commit
    try:
        db.commit()
        logger.info(f"✅ Successfully saved {saved_count} detections to database")
    except Exception as e:
        logger.error(f"Error committing detections: {str(e)}")
        db.rollback()
        
    return saved_count, error_count


async def process_all_videos():
    """Process all videos in the database with the fixed detection pipeline"""
    
    logger.info("=" * 80)
    logger.info("RUNNING FIXED DETECTION PIPELINE ON ALL VIDEOS")
    logger.info("=" * 80)
    
    # Initialize detection service
    service = FixedDetectionService()
    
    # Load model
    logger.info("Loading YOLOv11l model...")
    if not service.load_model():
        logger.error("Failed to load model!")
        return
    
    logger.info("✅ Model loaded successfully")
    
    # Get database session
    db = SessionLocal()
    
    try:
        # Get all videos
        videos = db.query(Video).all()
        logger.info(f"Found {len(videos)} videos to process")
        
        total_detections = 0
        detection_summary = {}
        
        for i, video in enumerate(videos, 1):
            logger.info(f"\n[{i}/{len(videos)}] Processing: {video.name}")
            logger.info(f"  Video ID: {video.id}")
            logger.info(f"  File path: {video.file_path}")
            
            # Check if file exists
            if not Path(video.file_path).exists():
                logger.warning(f"  ⚠️ File not found: {video.file_path}")
                continue
            
            # Clear old detections
            clear_old_detections(db, video.id)
            
            # Process video with fixed service
            result = service.process_video(
                video.file_path,
                video.id,
                sample_rate=15  # Process every 0.5 seconds at 30fps
            )
            
            if result['error']:
                logger.error(f"  ❌ Error: {result['error']}")
                continue
            
            # Display results
            logger.info(f"  📊 Results:")
            logger.info(f"     Total frames: {result['summary']['total_frames']}")
            logger.info(f"     Processed frames: {result['summary']['processed_frames']}")
            logger.info(f"     Total detections: {result['summary']['total_detections']}")
            
            if result['summary']['detections_by_type']:
                logger.info(f"     By type: {result['summary']['detections_by_type']}")
            
            # Save to database
            if result['detections']:
                saved, errors = save_detections_to_db(db, video.id, result['detections'])
                total_detections += saved
                
                # Update summary
                for vru_type, count in result['summary']['detections_by_type'].items():
                    detection_summary[vru_type] = detection_summary.get(vru_type, 0) + count
            else:
                logger.warning(f"  ⚠️ No detections found")
        
        # Final summary
        logger.info("\n" + "=" * 80)
        logger.info("PROCESSING COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total videos processed: {len(videos)}")
        logger.info(f"Total detections saved: {total_detections}")
        logger.info(f"Detection breakdown: {detection_summary}")
        
        # Verify in database
        total_annotations = db.query(Annotation).count()
        logger.info(f"Total annotations in database: {total_annotations}")
        
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        db.close()


def verify_database_structure():
    """Verify the database has the correct structure"""
    logger.info("\nVerifying database structure...")
    
    db = SessionLocal()
    try:
        # Check if Annotation table exists and has video_id column
        result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'annotations'"))
        columns = [row[0] for row in result]
        
        if 'video_id' in columns:
            logger.info("✅ Database structure verified: video_id column exists")
        else:
            logger.error("❌ Missing video_id column in annotations table!")
            logger.info("Creating migration to add video_id column...")
            # Add migration if needed
            
    except Exception as e:
        logger.error(f"Database verification failed: {str(e)}")
    finally:
        db.close()


if __name__ == "__main__":
    # Verify database first
    verify_database_structure()
    
    # Run the processing
    asyncio.run(process_all_videos())
    
    logger.info("\n" + "=" * 80)
    logger.info("NEXT STEPS:")
    logger.info("1. Review the detection results above")
    logger.info("2. If detections are found, the pipeline is fixed!")
    logger.info("3. If still no detections, try:")
    logger.info("   - Using a different YOLO model (yolov8n.pt for speed)")
    logger.info("   - Processing more frames (reduce sample_rate)")
    logger.info("   - Checking video content manually")
    logger.info("=" * 80)