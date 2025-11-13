#!/usr/bin/env python3
"""
Backfill Script: Reassign Video 2 Detections

This script fixes detection assignments for multi-video sessions where Video 2
detections were incorrectly assigned to Video 1 due to cache invalidation bug.

Usage:
    python backfill_video_2_detections.py [--session-id SESSION_ID] [--dry-run]

Options:
    --session-id: Specific session ID to backfill (optional, processes all if not provided)
    --dry-run: Preview changes without committing to database
"""

import sys
import json
import argparse
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database import Base
from models import TestSession, DetectionEvent
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_session():
    """Create database session"""
    engine = create_engine('sqlite:///dev_database.db')
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def analyze_session(db, session_id: str):
    """Analyze detection distribution for a session"""
    logger.info(f"\n{'='*80}")
    logger.info(f"Analyzing session: {session_id}")
    logger.info(f"{'='*80}")

    # Get session metadata
    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if not session:
        logger.error(f"Session {session_id} not found")
        return None

    # Parse sequence metadata
    metadata = session.sequence_metadata
    if isinstance(metadata, str):
        metadata = json.loads(metadata)

    video_timing = metadata.get('video_timing', {})
    if not video_timing:
        logger.warning(f"No video timing data found for session {session_id}")
        return None

    logger.info(f"\nVideo timing windows:")
    video_list = []
    for video_id, timing in video_timing.items():
        start = timing.get('started_at')
        end = timing.get('ended_at')
        logger.info(f"  Video {video_id[:8]}...{video_id[-8:]}")
        logger.info(f"    Start: {start}")
        logger.info(f"    End: {end}")
        video_list.append((video_id, start, end))

    # Check detection counts
    logger.info(f"\nDetection analysis:")
    corrections = []

    for video_id, start, end in video_list:
        # Count currently assigned
        assigned_count = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.video_id == video_id
        ).count()

        # Count by timestamp range
        if start and end:
            query = text("""
                SELECT COUNT(*) as count
                FROM detection_events
                WHERE test_session_id = :session_id
                  AND labjack_timestamp >= :start
                  AND labjack_timestamp < :end
            """)
            result = db.execute(query, {'session_id': session_id, 'start': start, 'end': end})
            in_range_count = result.fetchone()[0]
        else:
            in_range_count = 0

        logger.info(f"  Video {video_id[:8]}...{video_id[-8:]}")
        logger.info(f"    Assigned: {assigned_count}")
        logger.info(f"    In time range: {in_range_count}")

        if assigned_count != in_range_count:
            diff = in_range_count - assigned_count
            logger.warning(f"    ⚠️  MISMATCH: {diff:+d} detections need correction")
            corrections.append({
                'video_id': video_id,
                'start': start,
                'end': end,
                'assigned': assigned_count,
                'should_be': in_range_count,
                'diff': diff
            })

    return corrections


def backfill_detections(db, session_id: str, corrections: list, dry_run: bool = False):
    """Reassign detections based on timestamp ranges"""
    logger.info(f"\n{'='*80}")
    logger.info(f"{'DRY RUN: ' if dry_run else ''}Backfilling detections for session {session_id}")
    logger.info(f"{'='*80}")

    total_updated = 0

    for correction in corrections:
        video_id = correction['video_id']
        start = correction['start']
        end = correction['end']

        if not start or not end:
            logger.warning(f"Skipping video {video_id[:8]}... (missing timing data)")
            continue

        # Find detections in this time range that are NOT assigned to this video
        query = text("""
            UPDATE detection_events
            SET video_id = :new_video_id
            WHERE test_session_id = :session_id
              AND labjack_timestamp >= :start
              AND labjack_timestamp < :end
              AND (video_id != :new_video_id OR video_id IS NULL)
        """)

        if dry_run:
            # Count how many would be updated
            count_query = text("""
                SELECT COUNT(*) as count
                FROM detection_events
                WHERE test_session_id = :session_id
                  AND labjack_timestamp >= :start
                  AND labjack_timestamp < :end
                  AND (video_id != :new_video_id OR video_id IS NULL)
            """)
            result = db.execute(count_query, {
                'session_id': session_id,
                'start': start,
                'end': end,
                'new_video_id': video_id
            })
            count = result.fetchone()[0]
            logger.info(f"Would update {count} detections for video {video_id[:8]}...{video_id[-8:]}")
            total_updated += count
        else:
            # Actually update
            result = db.execute(query, {
                'session_id': session_id,
                'start': start,
                'end': end,
                'new_video_id': video_id
            })
            count = result.rowcount
            logger.info(f"✅ Updated {count} detections for video {video_id[:8]}...{video_id[-8:]}")
            total_updated += count

    if not dry_run and total_updated > 0:
        db.commit()
        logger.info(f"\n✅ Backfill complete: {total_updated} detections reassigned")
    elif dry_run:
        logger.info(f"\n📋 Dry run complete: {total_updated} detections would be reassigned")
    else:
        logger.info(f"\n✅ No corrections needed")

    return total_updated


def verify_backfill(db, session_id: str):
    """Verify backfill was successful"""
    logger.info(f"\n{'='*80}")
    logger.info(f"Verifying backfill for session {session_id}")
    logger.info(f"{'='*80}")

    corrections = analyze_session(db, session_id)

    if not corrections:
        logger.info("✅ All detections correctly assigned")
        return True

    has_issues = False
    for correction in corrections:
        if correction['diff'] != 0:
            logger.error(f"❌ Video {correction['video_id'][:8]}... still has {correction['diff']:+d} mismatched detections")
            has_issues = True

    return not has_issues


def main():
    parser = argparse.ArgumentParser(description='Backfill Video 2 detection assignments')
    parser.add_argument('--session-id', type=str, help='Specific session ID to process')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without committing')
    parser.add_argument('--verify-only', action='store_true', help='Only verify, do not backfill')

    args = parser.parse_args()

    db = get_db_session()

    try:
        if args.session_id:
            # Process specific session
            session_ids = [args.session_id]
        else:
            # Find all multi-video sessions
            sessions = db.query(TestSession).filter(
                TestSession.has_video_sequence == True
            ).all()
            session_ids = [s.id for s in sessions]
            logger.info(f"Found {len(session_ids)} multi-video sessions to process")

        for session_id in session_ids:
            corrections = analyze_session(db, session_id)

            if not corrections:
                logger.info(f"✅ Session {session_id[:8]}... has no corrections needed")
                continue

            if args.verify_only:
                logger.info(f"📋 Verification complete for session {session_id[:8]}...")
                continue

            # Perform backfill
            updated_count = backfill_detections(db, session_id, corrections, dry_run=args.dry_run)

            # Verify if not dry run
            if not args.dry_run and updated_count > 0:
                verify_backfill(db, session_id)

    except Exception as e:
        logger.error(f"❌ Error during backfill: {e}", exc_info=True)
        db.rollback()
        return 1
    finally:
        db.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
