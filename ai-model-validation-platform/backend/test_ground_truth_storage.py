#!/usr/bin/env python3
"""
Ground Truth Storage Test
Specifically tests the functionality that was failing for YOLOv8 detections
"""
import os
import sys
import logging
import uuid
from typing import List, Dict, Any
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def simulate_yolo_detections(num_detections: int = 126) -> List[Dict[str, Any]]:
    """Simulate YOLOv8 detection results like the ones that were failing to save"""
    detections = []
    
    for i in range(num_detections):
        detection = {
            "detection_id": f"DET_PER_{i:04d}",
            "timestamp": i * 0.5,  # Every 0.5 seconds
            "class_label": "person",
            "x": 100 + (i % 50) * 10,
            "y": 50 + (i % 30) * 15,
            "width": 80 + (i % 20),
            "height": 120 + (i % 30),
            "confidence": 0.85 + (i % 10) * 0.01,
            "frame_number": i,
        }
        detections.append(detection)
    
    return detections

def test_ground_truth_storage():
    """Test storing ground truth objects like YOLOv8 detection results"""
    try:
        from database import SessionLocal, get_database_health, safe_create_indexes_and_tables
        from models import Project, Video, GroundTruthObject
        
        # Check database health first
        health = get_database_health()
        logger.info(f"Database health: {health}")
        
        if health.get('status') != 'healthy':
            logger.error("Database is not healthy, cannot proceed")
            return False
        
        # Ensure tables exist
        safe_create_indexes_and_tables()
        logger.info("✅ Database schema verified")
        
        db = SessionLocal()
        
        try:
            # Create test project (simulating the project that YOLOv8 detections belong to)
            project = Project(
                id=str(uuid.uuid4()),
                name="YOLOv8 Detection Test Project",
                description="Testing storage of YOLOv8 person detections",
                camera_model="YOLOv8-Compatible-Camera",
                camera_view="Front-facing VRU",  # Valid enum value
                signal_type="GPIO",  # Valid enum value
                status="Active"
            )
            db.add(project)
            db.commit()
            logger.info(f"✅ Created test project: {project.id}")
            
            # Create test video (simulating the video being processed)
            video = Video(
                id=str(uuid.uuid4()),
                filename="person_detection_test.mp4",
                file_path="/test/videos/person_detection_test.mp4",
                project_id=project.id,
                file_size=50 * 1024 * 1024,  # 50MB
                duration=63.0,  # 63 seconds (126 detections * 0.5s interval)
                fps=25.0,
                resolution="1920x1080",
                status="processed",
                processing_status="completed",
                ground_truth_generated=True
            )
            db.add(video)
            db.commit()
            logger.info(f"✅ Created test video: {video.id}")
            
            # Generate simulated YOLOv8 detections
            detections = simulate_yolo_detections(126)  # Same count as the failing case
            logger.info(f"📊 Generated {len(detections)} simulated YOLOv8 detections")
            
            # Store ground truth objects (this is what was failing before)
            stored_count = 0
            for detection in detections:
                ground_truth = GroundTruthObject(
                    id=str(uuid.uuid4()),
                    video_id=video.id,
                    timestamp=detection["timestamp"],
                    frame_number=detection["frame_number"],
                    class_label=detection["class_label"],
                    x=detection["x"],
                    y=detection["y"],
                    width=detection["width"],
                    height=detection["height"],
                    confidence=detection["confidence"],
                    validated=False,  # Fresh detections not yet validated
                    difficult=False
                )
                db.add(ground_truth)
                stored_count += 1
                
                # Commit in batches to avoid memory issues
                if stored_count % 25 == 0:
                    db.commit()
                    logger.info(f"💾 Stored {stored_count}/{len(detections)} detections...")
            
            # Final commit
            db.commit()
            logger.info(f"✅ Successfully stored all {stored_count} ground truth objects")
            
            # Verify storage by querying back
            verification_count = db.query(GroundTruthObject).filter_by(video_id=video.id).count()
            logger.info(f"🔍 Verification: Found {verification_count} stored objects")
            
            if verification_count == len(detections):
                logger.info("✅ Storage verification passed - all detections saved correctly")
                success = True
            else:
                logger.error(f"❌ Storage verification failed - expected {len(detections)}, found {verification_count}")
                success = False
            
            # Get some statistics
            stats = db.query(GroundTruthObject).filter_by(video_id=video.id).all()
            if stats:
                confidences = [obj.confidence for obj in stats]
                avg_confidence = sum(confidences) / len(confidences)
                logger.info(f"📈 Detection statistics:")
                logger.info(f"   - Count: {len(stats)}")
                logger.info(f"   - Avg confidence: {avg_confidence:.3f}")
                logger.info(f"   - Time range: {stats[0].timestamp:.1f}s - {stats[-1].timestamp:.1f}s")
            
            # Clean up test data
            db.query(GroundTruthObject).filter_by(video_id=video.id).delete()
            db.delete(video)
            db.delete(project)
            db.commit()
            logger.info("🧹 Cleaned up test data")
            
            return success
            
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            db.rollback()
            raise
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Ground truth storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_connectivity_diagnostics():
    """Run test with full connectivity diagnostics"""
    logger.info("🔍 Running connectivity diagnostics...")
    
    try:
        from database_connectivity_helper import diagnose_database_connectivity
        diagnosis = diagnose_database_connectivity()
        
        logger.info("📊 Connectivity Diagnosis:")
        logger.info(f"   Environment: {diagnosis['environment']}")
        logger.info(f"   Connectivity: {diagnosis['connectivity']}")
        logger.info(f"   Database: {diagnosis['database']}")
        
        if diagnosis['recommendations']:
            logger.info("💡 Recommendations:")
            for rec in diagnosis['recommendations']:
                logger.info(f"   - {rec}")
    
    except ImportError:
        logger.warning("Connectivity helper not available")
    except Exception as e:
        logger.error(f"Diagnostics failed: {e}")

def main():
    """Main test entry point"""
    print("🧪 Ground Truth Storage Test")
    print("=" * 50)
    print("This test simulates the YOLOv8 detection storage that was failing")
    print("Expected: 126 person detections should be stored successfully")
    print()
    
    # Run diagnostics first
    test_with_connectivity_diagnostics()
    print()
    
    # Run the main test
    success = test_ground_truth_storage()
    
    print("=" * 50)
    if success:
        print("🎉 Ground truth storage test PASSED!")
        print("✅ YOLOv8 detection storage should now work correctly")
    else:
        print("❌ Ground truth storage test FAILED!")
        print("⚠️  YOLOv8 detection storage may still have issues")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)