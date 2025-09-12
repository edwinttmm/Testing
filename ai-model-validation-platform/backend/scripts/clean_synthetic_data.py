#!/usr/bin/env python3
"""
Clean Synthetic Test Data Script
Remove all synthetic/mock data and keep only real LabJack-based test results
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from database import SessionLocal
from models import TestSession, DetectionEvent, TestResult, GroundTruthObject
from sqlalchemy import func, desc
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_synthetic_data():
    """Remove all synthetic/mock test data from database"""
    try:
        db = SessionLocal()
        
        print("=" * 80)
        print("🧹 CLEANING SYNTHETIC TEST DATA")
        print("=" * 80)
        
        # Get current counts
        session_count = db.query(TestSession).count()
        detection_count = db.query(DetectionEvent).count()
        result_count = db.query(TestResult).count()
        gt_count = db.query(GroundTruthObject).count()
        
        print(f"\n📊 BEFORE CLEANUP:")
        print(f"   Test Sessions: {session_count}")
        print(f"   Detection Events: {detection_count}")
        print(f"   Test Results: {result_count}")
        print(f"   Ground Truth Objects: {gt_count}")
        
        # Identify synthetic sessions (those not from real LabJack tests)
        print(f"\n🔍 IDENTIFYING SYNTHETIC DATA:")
        
        # Look for sessions with suspicious names or synthetic data patterns
        synthetic_sessions = db.query(TestSession).filter(
            TestSession.name.like('%Enhanced%')
        ).all()
        
        # Also check for sessions with unrealistic detection counts
        suspicious_sessions = []
        for session in db.query(TestSession).all():
            # Get detection count directly from DetectionEvent using test_session_id
            detection_count = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).count()
            
            # If session has a lot of detection events (likely synthetic)
            if detection_count > 50:  # Real tests typically have fewer detections
                suspicious_sessions.append(session)
                
        all_synthetic_sessions = list(set(synthetic_sessions + suspicious_sessions))
        
        print(f"   Found {len(all_synthetic_sessions)} synthetic sessions:")
        for session in all_synthetic_sessions:
            detections = db.query(DetectionEvent).filter(
                DetectionEvent.session_id == session.id
            ).count()
            print(f"   - {session.name} ({session.id}): {detections} detections")
        
        # Clean up synthetic data
        deleted_detections = 0
        deleted_results = 0
        deleted_sessions = 0
        
        print(f"\n🗑️  REMOVING SYNTHETIC DATA:")
        
        for session in all_synthetic_sessions:
            # Delete detection events directly using test_session_id
            detections = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).delete()
            deleted_detections += detections
            
            # Delete test results for this session (using test_session_id field)
            results = db.query(TestResult).filter(
                TestResult.test_session_id == session.id
            ).delete()
            deleted_results += results
            
            # Delete the session itself
            db.delete(session)
            deleted_sessions += 1
            
            print(f"   ✅ Deleted session: {session.name}")
        
        # Remove unrealistic ground truth data (synthetic ground truth)
        # Keep only ground truth that seems realistic for object detection
        synthetic_gt = db.query(GroundTruthObject).filter(
            # Remove ground truth with suspicious confidence scores
            GroundTruthObject.confidence > 0.99  # Perfect confidence is usually synthetic
        ).all()
        
        deleted_gt = len(synthetic_gt)
        for gt in synthetic_gt:
            db.delete(gt)
            
        # Commit all deletions
        db.commit()
        
        # Get final counts
        final_session_count = db.query(TestSession).count()
        final_detection_count = db.query(DetectionEvent).count()
        final_result_count = db.query(TestResult).count()
        final_gt_count = db.query(GroundTruthObject).count()
        
        print(f"\n📊 AFTER CLEANUP:")
        print(f"   Test Sessions: {final_session_count}")
        print(f"   Detection Events: {final_detection_count}")
        print(f"   Test Results: {final_result_count}")
        print(f"   Ground Truth Objects: {final_gt_count}")
        
        print(f"\n🗑️  CLEANUP SUMMARY:")
        print(f"   Deleted Sessions: {deleted_sessions}")
        print(f"   Deleted Detection Events: {deleted_detections}")
        print(f"   Deleted Test Results: {deleted_results}")
        print(f"   Deleted Ground Truth Objects: {deleted_gt}")
        
        if final_session_count == 0:
            print(f"\n✅ DATABASE CLEAN: No test sessions remain")
            print(f"   Enhanced results will now show 'No tests run' correctly")
        else:
            print(f"\n⚠️  REMAINING SESSIONS:")
            remaining = db.query(TestSession).all()
            for session in remaining:
                detections = db.query(DetectionEvent).filter(
                    DetectionEvent.session_id == session.id
                ).count()
                print(f"   - {session.name} ({session.id}): {detections} detections")
        
        db.close()
        
        print(f"\n" + "=" * 80)
        print(f"🎉 SYNTHETIC DATA CLEANUP COMPLETE")
        print(f"=" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = clean_synthetic_data()
    
    print("\n💡 NEXT STEPS:")
    print("1. Verify enhanced results now show 'No tests run' state")
    print("2. Run actual LabJack-based enhanced test to generate real data")
    print("3. Confirm only real test metrics are displayed")
    
    sys.exit(0 if success else 1)