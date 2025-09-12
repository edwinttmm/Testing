#!/usr/bin/env python3
"""
Debug Detection Results Script
Checks database for detection issues and test execution problems
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

def debug_detection_results():
    """Debug and analyze detection results"""
    try:
        from database import SessionLocal
        from models import TestSession, DetectionEvent, Video, GroundTruthObject
        from sqlalchemy import func, text
        
        db = SessionLocal()
        
        print("=" * 80)
        print("🔍 DETECTION RESULTS DEBUG ANALYSIS")
        print("=" * 80)
        
        # 1. Check test sessions
        print("\n📊 Test Sessions Analysis:")
        print("-" * 50)
        
        sessions = db.query(TestSession).order_by(TestSession.created_at.desc()).limit(5).all()
        
        for session in sessions:
            print(f"Session ID: {session.id}")
            print(f"  Name: {session.name}")
            print(f"  Status: {session.status}")
            print(f"  Video ID: {session.video_id}")
            print(f"  Project ID: {session.project_id}")
            print(f"  Created: {session.created_at}")
            
            # Check for detection events
            detection_count = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).count()
            print(f"  Detection Events: {detection_count}")
            
            # If we have detections, show sample metrics
            if detection_count > 0:
                detections = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == session.id
                ).limit(3).all()
                
                for det in detections:
                    print(f"    - Detection: {det.class_label} (conf={det.confidence:.3f})")
                    print(f"      Validation: {det.validation_result}")
                    print(f"      Timestamp: {det.timestamp}")
            print()
        
        # 2. Check detection events summary  
        print("\n🎯 Detection Events Summary:")
        print("-" * 50)
        
        total_detections = db.query(DetectionEvent).count()
        print(f"Total Detection Events: {total_detections}")
        
        if total_detections > 0:
            # Group by class_label
            class_summary = db.query(
                DetectionEvent.class_label,
                func.count(DetectionEvent.id).label('count'),
                func.avg(DetectionEvent.confidence).label('avg_conf')
            ).group_by(DetectionEvent.class_label).all()
            
            print("\nDetection by Class:")
            for cls, count, avg_conf in class_summary:
                print(f"  {cls}: {count} detections (avg conf: {avg_conf:.3f})")
            
            # Group by validation result
            validation_summary = db.query(
                DetectionEvent.validation_result,
                func.count(DetectionEvent.id).label('count')
            ).group_by(DetectionEvent.validation_result).all()
            
            print("\nValidation Results:")
            for result, count in validation_summary:
                print(f"  {result}: {count} detections")
        
        # 3. Check ground truth data
        print("\n📐 Ground Truth Analysis:")
        print("-" * 50)
        
        total_gt = db.query(GroundTruthObject).count()
        print(f"Total Ground Truth Objects: {total_gt}")
        
        if total_gt > 0:
            # Group by video_id
            gt_by_video = db.query(
                GroundTruthObject.video_id,
                func.count(GroundTruthObject.id).label('count')
            ).group_by(GroundTruthObject.video_id).limit(5).all()
            
            print("\nGround Truth by Video:")
            for video_id, count in gt_by_video:
                print(f"  Video {video_id}: {count} ground truth objects")
        
        # 4. Check videos with ground truth
        print("\n📹 Videos Analysis:")
        print("-" * 50)
        
        videos_with_gt = db.query(Video).filter(Video.ground_truth_generated == True).all()
        print(f"Videos with Ground Truth: {len(videos_with_gt)}")
        
        for video in videos_with_gt[:3]:  # Show first 3
            gt_count = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video.id
            ).count()
            
            print(f"  Video: {video.filename}")
            print(f"    ID: {video.id}")
            print(f"    Ground Truth Objects: {gt_count}")
            print(f"    File Path: {video.file_path}")
        
        # 5. Identify the problem
        print("\n🔍 PROBLEM ANALYSIS:")
        print("-" * 50)
        
        if total_detections == 0:
            print("❌ ISSUE: No detection events found in database")
            print("💡 This means:")
            print("   - Either no tests were run that generated detections")
            print("   - Or detections were generated but not stored in database")
            print("   - Check if test execution service is working correctly")
            
            # Check if there are active test sessions
            active_sessions = db.query(TestSession).filter(TestSession.status == "running").count()
            pending_sessions = db.query(TestSession).filter(TestSession.status == "pending").count()
            completed_sessions = db.query(TestSession).filter(TestSession.status == "completed").count()
            
            print(f"\n📊 Session Status:")
            print(f"   Active (running): {active_sessions}")
            print(f"   Pending: {pending_sessions}")
            print(f"   Completed: {completed_sessions}")
            
            if completed_sessions > 0 and total_detections == 0:
                print("⚠️  CRITICAL: Completed sessions exist but no detection events!")
                print("   This suggests the detection pipeline is not storing results")
        
        elif total_gt == 0:
            print("❌ ISSUE: No ground truth data found")
            print("💡 This means:")
            print("   - Ground truth was not generated for videos")
            print("   - Cannot perform validation without ground truth")
            print("   - Need to run ground truth generation first")
        
        else:
            print("✅ Both detection events and ground truth exist")
            print("🔍 Need to check validation logic in enhanced results service")
        
        db.close()
        
        print("\n" + "=" * 80)
        print("DEBUG ANALYSIS COMPLETE")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ Debug analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_detection_results()
    sys.exit(0 if success else 1)