#!/usr/bin/env python3
"""
Migrate existing sessions to mark their timing quality.

This script should be run AFTER applying the schema migration to add
timing quality tracking columns. It marks existing data with conservative
defaults to ensure data integrity.

Usage:
    python scripts/migrate_existing_sessions.py

Run this script after applying the 20251119_timing_quality migration:
    alembic upgrade head
    python scripts/migrate_existing_sessions.py
"""
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal, engine
from models import TestSession, DetectionEvent
from sqlalchemy import update
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_existing_data():
    """
    Migrate existing sessions to mark their timing quality.

    Conservative approach: Mark all existing sessions as having degraded timing
    and unverified status until proven otherwise. This prevents data corruption
    from using potentially unreliable timing data in ground truth matching.

    Detections are marked as usable by default since they represent actual
    historical data that has already been processed.
    """
    db = SessionLocal()

    try:
        logger.info("Starting data migration for timing quality tracking...")

        # Get counts before migration
        session_count = db.query(TestSession).count()
        detection_count = db.query(DetectionEvent).count()

        logger.info(f"Found {session_count} test sessions")
        logger.info(f"Found {detection_count} detection events")

        if session_count == 0 and detection_count == 0:
            logger.info("No existing data to migrate")
            return

        # Mark all existing sessions as having unknown/degraded timing quality
        # Conservative approach: assume degraded until proven otherwise
        if session_count > 0:
            logger.info("Updating test sessions with timing quality flags...")
            result = db.execute(
                update(TestSession).values(
                    timing_degraded=True,  # Conservative: assume degraded
                    timing_verified=False  # Not yet verified
                )
            )
            logger.info(f"Updated {result.rowcount} test sessions")

        # Mark all existing detections as usable (existing data assumed valid)
        # These detections have already been processed, so they should remain usable
        if detection_count > 0:
            logger.info("Updating detection events with usability flags...")
            result = db.execute(
                update(DetectionEvent).values(
                    usable_for_validation=True  # Existing detections are usable
                )
            )
            logger.info(f"Updated {result.rowcount} detection events")

        # Commit changes
        db.commit()

        logger.info("✅ Migration completed successfully")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Review sessions with timing_degraded=True")
        logger.info("2. Update timing_verified=True for sessions with reliable timing")
        logger.info("3. Mark detections with usable_for_validation=False if timing is suspect")

        return True

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Migration failed: {e}")
        logger.error("Database has been rolled back to previous state")
        raise
    finally:
        db.close()


def verify_migration():
    """Verify the migration was successful"""
    db = SessionLocal()

    try:
        logger.info("")
        logger.info("Verifying migration results...")

        # Check test_sessions
        total_sessions = db.query(TestSession).count()
        degraded_sessions = db.query(TestSession).filter(
            TestSession.timing_degraded == True
        ).count()
        verified_sessions = db.query(TestSession).filter(
            TestSession.timing_verified == True
        ).count()

        logger.info(f"Test Sessions - Total: {total_sessions}, "
                   f"Degraded: {degraded_sessions}, Verified: {verified_sessions}")

        # Check detection_events
        total_detections = db.query(DetectionEvent).count()
        usable_detections = db.query(DetectionEvent).filter(
            DetectionEvent.usable_for_validation == True
        ).count()
        unusable_detections = db.query(DetectionEvent).filter(
            DetectionEvent.usable_for_validation == False
        ).count()

        logger.info(f"Detection Events - Total: {total_detections}, "
                   f"Usable: {usable_detections}, Unusable: {unusable_detections}")

        logger.info("✅ Verification completed")

    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    try:
        migrate_existing_data()
        verify_migration()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Migration script failed: {e}")
        sys.exit(1)
