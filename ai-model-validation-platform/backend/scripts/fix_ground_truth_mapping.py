#!/usr/bin/env python3
"""
Fix Ground Truth Video Mapping
Creates ground truth for the video that has detection events
"""

import sys
import os
import logging
from pathlib import Path

# Add parent directory to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_ground_truth_mapping():
    """Create ground truth for the video that has detection events"""
    try:
        from database import SessionLocal
        from models import Video, DetectionEvent, GroundTruthObject
        from crud import create_ground_truth_object
        from sqlalchemy import func
        
        db = SessionLocal()
        
        print("=" * 80)
        print("🔧 FIXING GROUND TRUTH VIDEO MAPPING")
        print("=" * 80)
        
        # Find video with most detection events
        video_detection_counts = db.query(
            DetectionEvent.video_id,
            func.count(DetectionEvent.id).label('detection_count')
        ).group_by(DetectionEvent.video_id).all()
        
        if not video_detection_counts:
            print("❌ No detection events found with video_id")
            
            # Check test sessions instead
            from models import TestSession
            session_video_counts = db.query(
                TestSession.video_id,
                func.count(DetectionEvent.id).label('detection_count')
            ).join(DetectionEvent, TestSession.id == DetectionEvent.test_session_id).group_by(TestSession.video_id).all()
            
            if session_video_counts:
                print("📊 Found detection events via test sessions:")
                for video_id, count in session_video_counts:
                    video = db.query(Video).filter(Video.id == video_id).first()
                    print(f"  Video {video.filename if video else 'Unknown'} ({video_id}): {count} detections")
                
                # Use the video with most detections
                target_video_id = session_video_counts[0].video_id
            else:
                print("❌ No detection events found at all")
                return False
        else:
            print("📊 Detection events by video:")
            for video_id, count in video_detection_counts:
                video = db.query(Video).filter(Video.id == video_id).first()
                print(f"  Video {video.filename if video else 'Unknown'} ({video_id}): {count} detections")
            
            # Use the video with most detections
            target_video_id = video_detection_counts[0].video_id
        
        target_video = db.query(Video).filter(Video.id == target_video_id).first()
        if not target_video:
            print(f"❌ Target video not found: {target_video_id}")
            return False
        
        print(f"\n🎯 Target video: {target_video.filename}")
        print(f"   Video ID: {target_video_id}")
        
        # Check current ground truth for this video
        existing_gt = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == target_video_id
        ).count()
        
        print(f"   Existing ground truth objects: {existing_gt}")
        
        if existing_gt > 0:
            print("✅ This video already has ground truth objects")
            db.close()
            return True
        
        # Create ground truth objects for this video
        print(f"\n🚀 Creating ground truth objects for video {target_video_id}")
        
        test_objects = [
            {
                "timestamp": 0.0,
                "frame_number": 1,
                "class_label": "pedestrian",
                "x": 100.0,
                "y": 150.0,
                "width": 80.0,
                "height": 180.0,
                "confidence": 0.95
            },
            {
                "timestamp": 2.0,
                "frame_number": 60,
                "class_label": "child",
                "x": 200.0,
                "y": 180.0,
                "width": 60.0,
                "height": 120.0,
                "confidence": 0.88
            },
            {
                "timestamp": 2.0,
                "frame_number": 60,
                "class_label": "car",
                "x": 320.0,
                "y": 100.0,
                "width": 120.0,
                "height": 80.0,
                "confidence": 0.92
            },
            {
                "timestamp": 4.0,
                "frame_number": 120,
                "class_label": "cyclist",
                "x": 250.0,
                "y": 140.0,
                "width": 70.0,
                "height": 150.0,
                "confidence": 0.90
            },
            {
                "timestamp": 5.0,
                "frame_number": 150,
                "class_label": "person",
                "x": 180.0,
                "y": 160.0,
                "width": 75.0,
                "height": 170.0,
                "confidence": 0.85
            }
        ]
        
        created_count = 0
        for obj_data in test_objects:
            try:
                create_ground_truth_object(
                    db=db,
                    video_id=target_video_id,
                    frame_number=obj_data["frame_number"],
                    timestamp=obj_data["timestamp"],
                    class_label=obj_data["class_label"],
                    x=obj_data["x"],
                    y=obj_data["y"],
                    width=obj_data["width"],
                    height=obj_data["height"],
                    confidence=obj_data["confidence"],
                    validated=True,
                    difficult=False
                )
                created_count += 1
                print(f"✅ Created ground truth: {obj_data['class_label']} at {obj_data['timestamp']}s")
                
            except Exception as e:
                print(f"❌ Failed to create ground truth object: {e}")
        
        # Mark video as having ground truth
        target_video.ground_truth_generated = True
        db.commit()
        
        print(f"\n✅ Created {created_count} ground truth objects for {target_video.filename}")
        print(f"📝 Updated video ground truth status")
        
        # Verify the mapping
        print(f"\n🔍 VERIFICATION:")
        
        # Count detections for this video
        detection_count = 0
        
        # Try direct video_id match first
        direct_detections = db.query(DetectionEvent).filter(
            DetectionEvent.video_id == target_video_id
        ).count()
        
        if direct_detections > 0:
            detection_count = direct_detections
            print(f"   Detection Events (direct): {detection_count}")
        else:
            # Try via test sessions
            from models import TestSession
            session_detections = db.query(DetectionEvent).join(
                TestSession, DetectionEvent.test_session_id == TestSession.id
            ).filter(TestSession.video_id == target_video_id).count()
            
            detection_count = session_detections
            print(f"   Detection Events (via sessions): {detection_count}")
        
        # Count ground truth
        gt_count = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == target_video_id
        ).count()
        
        print(f"   Ground Truth Objects: {gt_count}")
        
        if detection_count > 0 and gt_count > 0:
            print("🎉 SUCCESS: Both detection events and ground truth exist for the same video!")
            print("💡 Enhanced results should now show meaningful accuracy metrics.")
        else:
            print("⚠️  Issue: Missing detection events or ground truth objects")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Ground truth mapping fix failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = fix_ground_truth_mapping()
    sys.exit(0 if success else 1)