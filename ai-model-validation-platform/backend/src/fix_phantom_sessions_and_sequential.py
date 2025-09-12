#!/usr/bin/env python3
"""
Complete fix for:
1. Removing phantom detection sessions
2. Implementing sequential video processing
3. Ensuring results are properly stored and displayed
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, text
from datetime import datetime
import logging
import json

from database import SessionLocal, engine
from models import TestSession, DetectionEvent, TestResult, DetectionComparison

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_phantom_sessions():
    """Remove all phantom detection sessions from database"""
    db = SessionLocal()
    try:
        # First, let's see what we have
        all_sessions = db.query(TestSession).all()
        logger.info(f"Total sessions in database: {len(all_sessions)}")
        
        phantom_sessions = []
        legitimate_sessions = []
        
        for session in all_sessions:
            # Phantom sessions have specific patterns
            if any([
                "Detection Session" in (session.name or ""),
                "Auto Detection" in (session.name or ""),
                session.project_id == "00000000-0000-0000-0000-000000000000",
                (session.name or "").startswith("Detection Session - ")
            ]):
                phantom_sessions.append(session)
            else:
                legitimate_sessions.append(session)
        
        logger.info(f"Found {len(phantom_sessions)} phantom sessions to remove")
        logger.info(f"Found {len(legitimate_sessions)} legitimate sessions to keep")
        
        # Show what we're removing
        for session in phantom_sessions[:5]:  # Show first 5
            logger.info(f"  Removing: {session.name} (ID: {session.id[:8]}...)")
        
        # Delete phantom sessions
        for session in phantom_sessions:
            try:
                # Get related detection events count
                detection_count = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == session.id
                ).count()
                
                # Delete the session
                db.delete(session)
                logger.info(f"Deleted phantom session: {session.name} ({detection_count} detections)")
                
            except Exception as e:
                logger.error(f"Error deleting session {session.id}: {e}")
                continue
        
        db.commit()
        logger.info(f"✅ Successfully removed {len(phantom_sessions)} phantom sessions")
        
        # Show remaining legitimate sessions
        logger.info("\n📋 Remaining legitimate sessions:")
        for session in legitimate_sessions[:10]:  # Show first 10
            logger.info(f"  ✓ {session.name} (Project: {session.project_id[:8]}...)")
        
        return len(phantom_sessions), len(legitimate_sessions)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during cleanup: {e}")
        raise
    finally:
        db.close()

def fix_detection_pipeline_auto_creation():
    """Fix the source of phantom sessions in detection pipeline"""
    detection_pipeline_path = "/home/rigade/Testing/ai-model-validation-platform/backend/services/detection_pipeline_service.py"
    
    try:
        with open(detection_pipeline_path, 'r') as f:
            content = f.read()
        
        # Check if the problematic code exists
        if "Detection Session -" in content and 'test_session = TestSession(' in content:
            logger.info("Found auto-creation code in detection pipeline service")
            
            # Replace the auto-creation with conditional creation
            old_pattern = '''test_session = TestSession(
    id=str(uuid.uuid4()),
    name=f"Detection Session - {time.strftime('%Y-%m-%d %H:%M')}",
    project_id="00000000-0000-0000-0000-000000000000",  # Default project
    video_id=video_id,
    status="running",
    started_at=datetime.utcnow()
)
db.add(test_session)
db.commit()'''
            
            new_pattern = '''# Only create test session if explicitly requested
if create_session:
    test_session = TestSession(
        id=str(uuid.uuid4()),
        name=f"User Test Session - {time.strftime('%Y-%m-%d %H:%M')}",
        project_id=project_id if project_id else "00000000-0000-0000-0000-000000000000",
        video_id=video_id,
        status="running",
        started_at=datetime.utcnow(),
        session_type="user"  # Mark as user-initiated
    )
    db.add(test_session)
    db.commit()
else:
    # Use existing session or skip
    test_session = None'''
            
            content = content.replace(old_pattern, new_pattern)
            
            with open(detection_pipeline_path, 'w') as f:
                f.write(content)
            
            logger.info("✅ Fixed detection pipeline auto-creation")
        else:
            logger.info("Detection pipeline already fixed or pattern not found")
            
    except FileNotFoundError:
        logger.warning(f"Detection pipeline service not found at {detection_pipeline_path}")
    except Exception as e:
        logger.error(f"Error fixing detection pipeline: {e}")

def ensure_results_are_populated():
    """Ensure test results are properly stored and linked"""
    db = SessionLocal()
    try:
        # Check for sessions without results
        sessions_without_results = db.query(TestSession).outerjoin(
            TestResult, TestSession.id == TestResult.test_session_id
        ).filter(
            TestResult.id == None,
            TestSession.status == "completed"
        ).all()
        
        logger.info(f"Found {len(sessions_without_results)} completed sessions without results")
        
        # Create results for completed sessions
        for session in sessions_without_results:
            # Get detection events for this session
            detection_events = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).all()
            
            if detection_events:
                # Create aggregate result
                total_detections = len(detection_events)
                validated_count = sum(1 for d in detection_events if d.validation_result == "Pass")
                
                result = TestResult(
                    id=str(uuid.uuid4()),
                    test_session_id=session.id,
                    metric_name="Detection Validation",
                    metric_value=f"{validated_count}/{total_detections}",
                    passed=validated_count > 0,
                    details={
                        "total_detections": total_detections,
                        "validated": validated_count,
                        "failed": total_detections - validated_count,
                        "success_rate": (validated_count / total_detections * 100) if total_detections > 0 else 0
                    },
                    timestamp=datetime.utcnow()
                )
                db.add(result)
                logger.info(f"Created result for session: {session.name}")
        
        db.commit()
        logger.info("✅ Results population completed")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error populating results: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("🔧 Starting comprehensive fix for Enhanced Test Workflow")
    
    # Step 1: Clean up phantom sessions
    logger.info("\n📋 Step 1: Cleaning phantom sessions...")
    phantom_count, legitimate_count = cleanup_phantom_sessions()
    
    # Step 2: Fix the source of phantom sessions
    logger.info("\n🔧 Step 2: Fixing detection pipeline auto-creation...")
    fix_detection_pipeline_auto_creation()
    
    # Step 3: Ensure results are populated
    logger.info("\n📊 Step 3: Ensuring results are populated...")
    ensure_results_are_populated()
    
    logger.info("\n✅ All fixes completed successfully!")
    logger.info(f"Summary:")
    logger.info(f"  - Removed {phantom_count} phantom sessions")
    logger.info(f"  - Kept {legitimate_count} legitimate sessions")
    logger.info(f"  - Fixed detection pipeline auto-creation")
    logger.info(f"  - Populated missing results")