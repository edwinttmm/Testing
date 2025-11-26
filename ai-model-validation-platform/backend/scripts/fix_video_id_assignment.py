#!/usr/bin/env python3
"""
Fix video_id Assignment for Detections

This script:
1. Updates existing NULL video_id records for a specific session
2. Can be run standalone or imported as a module

Usage:
    python scripts/fix_video_id_assignment.py --session-id <session_id>
    python scripts/fix_video_id_assignment.py --all
"""

import sys
import os
import logging
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func
from database import SessionLocal
from models import DetectionEvent, TestSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fix_video_id_for_session(session_id: str, db=None) -> dict:
    """
    Fix NULL video_id records for detections in a specific session.

    Args:
        session_id: The test session ID to fix
        db: Optional database session (creates new one if not provided)

    Returns:
        dict with results: {
            'session_id': str,
            'video_id': str,
            'detections_updated': int,
            'total_detections': int
        }
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Get the session to find its video_id
        session = db.query(TestSession).filter(TestSession.id == session_id).first()

        if not session:
            logger.error(f"❌ Session not found: {session_id}")
            return {
                'session_id': session_id,
                'error': 'Session not found',
                'detections_updated': 0,
                'total_detections': 0
            }

        if not session.video_id:
            logger.error(f"❌ Session {session_id} has no video_id!")
            return {
                'session_id': session_id,
                'error': 'Session has no video_id',
                'detections_updated': 0,
                'total_detections': 0
            }

        # Count total detections in this session
        total_detections = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id
        ).scalar()

        # Count detections with NULL video_id
        null_detections = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.video_id.is_(None)
        ).scalar()

        logger.info(f"📊 Session {session_id}:")
        logger.info(f"   Total detections: {total_detections}")
        logger.info(f"   NULL video_id: {null_detections}")
        logger.info(f"   Session video_id: {session.video_id}")

        if null_detections == 0:
            logger.info("✅ No detections need fixing!")
            return {
                'session_id': session_id,
                'video_id': session.video_id,
                'detections_updated': 0,
                'total_detections': total_detections
            }

        # Update NULL video_id records
        updated_count = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.video_id.is_(None)
        ).update(
            {DetectionEvent.video_id: session.video_id},
            synchronize_session=False
        )

        db.commit()

        logger.info(f"✅ Updated {updated_count} detections with video_id: {session.video_id}")

        # Verify the fix
        remaining_null = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.video_id.is_(None)
        ).scalar()

        if remaining_null > 0:
            logger.warning(f"⚠️ Still {remaining_null} detections with NULL video_id")
        else:
            logger.info("✅ All detections now have video_id!")

        return {
            'session_id': session_id,
            'video_id': session.video_id,
            'detections_updated': updated_count,
            'total_detections': total_detections,
            'remaining_null': remaining_null
        }

    except Exception as e:
        logger.error(f"❌ Error fixing video_id: {e}")
        db.rollback()
        raise
    finally:
        if close_db:
            db.close()


def fix_all_sessions(db=None) -> list:
    """
    Fix NULL video_id for all sessions that have detections.

    Returns:
        List of results for each session
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Find all sessions with NULL video_id detections
        sessions_with_null = db.query(
            DetectionEvent.test_session_id,
            func.count(DetectionEvent.id).label('null_count')
        ).filter(
            DetectionEvent.video_id.is_(None)
        ).group_by(
            DetectionEvent.test_session_id
        ).all()

        logger.info(f"🔍 Found {len(sessions_with_null)} sessions with NULL video_id detections")

        results = []
        for session_id, null_count in sessions_with_null:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing session: {session_id} ({null_count} NULL detections)")
            logger.info(f"{'='*60}")

            result = fix_video_id_for_session(session_id, db=db)
            results.append(result)

        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("📊 SUMMARY")
        logger.info(f"{'='*60}")

        total_updated = sum(r.get('detections_updated', 0) for r in results)
        total_detections = sum(r.get('total_detections', 0) for r in results)

        logger.info(f"Sessions processed: {len(results)}")
        logger.info(f"Total detections updated: {total_updated}")
        logger.info(f"Total detections across all sessions: {total_detections}")

        return results

    finally:
        if close_db:
            db.close()


def verify_session_detections(session_id: str, db=None) -> dict:
    """
    Verify detection video_id assignments for a session.

    Returns:
        dict with verification results
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()

        if not session:
            return {'error': 'Session not found'}

        total = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id
        ).scalar()

        with_video_id = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.video_id.is_not(None)
        ).scalar()

        without_video_id = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.video_id.is_(None)
        ).scalar()

        correct_video_id = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.video_id == session.video_id
        ).scalar()

        wrong_video_id = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.video_id.is_not(None),
            DetectionEvent.video_id != session.video_id
        ).scalar()

        logger.info(f"\n📊 Verification for session {session_id}:")
        logger.info(f"   Session video_id: {session.video_id}")
        logger.info(f"   Total detections: {total}")
        logger.info(f"   With video_id: {with_video_id}")
        logger.info(f"   Without video_id (NULL): {without_video_id}")
        logger.info(f"   Correct video_id: {correct_video_id}")
        logger.info(f"   Wrong video_id: {wrong_video_id}")

        if without_video_id == 0 and wrong_video_id == 0:
            logger.info("✅ All detections have correct video_id!")
        else:
            logger.warning(f"⚠️ Issues found: {without_video_id} NULL, {wrong_video_id} wrong")

        return {
            'session_id': session_id,
            'session_video_id': session.video_id,
            'total_detections': total,
            'with_video_id': with_video_id,
            'without_video_id': without_video_id,
            'correct_video_id': correct_video_id,
            'wrong_video_id': wrong_video_id,
            'status': 'OK' if (without_video_id == 0 and wrong_video_id == 0) else 'ISSUES'
        }

    finally:
        if close_db:
            db.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Fix video_id assignment for detections')
    parser.add_argument('--session-id', help='Session ID to fix')
    parser.add_argument('--all', action='store_true', help='Fix all sessions')
    parser.add_argument('--verify', action='store_true', help='Verify without fixing')

    args = parser.parse_args()

    if args.session_id:
        if args.verify:
            result = verify_session_detections(args.session_id)
            print(f"\n✅ Verification complete: {result['status']}")
        else:
            result = fix_video_id_for_session(args.session_id)
            print(f"\n✅ Updated {result.get('detections_updated', 0)} detections")
    elif args.all:
        results = fix_all_sessions()
        total_updated = sum(r.get('detections_updated', 0) for r in results)
        print(f"\n✅ Total updated across all sessions: {total_updated}")
    else:
        # Default: fix the specific session mentioned in the task
        session_id = 'daad8bf6-b5da-4423-abc4-a85e83bc1c16'
        logger.info(f"🎯 Fixing default session: {session_id}")
        result = fix_video_id_for_session(session_id)
        print(f"\n✅ Updated {result.get('detections_updated', 0)} detections")

        # Verify
        verify_result = verify_session_detections(session_id)
        print(f"✅ Verification: {verify_result['status']}")
