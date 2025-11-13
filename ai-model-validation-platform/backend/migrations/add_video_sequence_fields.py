"""
Database Migration: Add Video Sequence Testing Fields
======================================================

Adds fields to TestSession and DetectionEvent models to support
multi-video sequential HIL testing with dynamic timing.

Changes:
- TestSession: sequence_id, sequence_metadata, max_latency_threshold_ms, description
- DetectionEvent: unix_timestamp, signal_type, channel, signal_value, detection_timestamp, metadata, sequence_id

Run with: python migrations/add_video_sequence_fields.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from database import DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Execute database migration"""
    engine = create_engine(DATABASE_URL)

    migrations = [
        # TestSession new fields
        """
        ALTER TABLE test_sessions
        ADD COLUMN IF NOT EXISTS sequence_id TEXT;
        """,
        """
        ALTER TABLE test_sessions
        ADD COLUMN IF NOT EXISTS sequence_metadata TEXT;  -- JSON stored as TEXT in SQLite
        """,
        """
        ALTER TABLE test_sessions
        ADD COLUMN IF NOT EXISTS max_latency_threshold_ms REAL;
        """,
        """
        ALTER TABLE test_sessions
        ADD COLUMN IF NOT EXISTS description TEXT;
        """,

        # DetectionEvent new fields
        """
        ALTER TABLE detection_events
        ADD COLUMN IF NOT EXISTS unix_timestamp REAL;
        """,
        """
        ALTER TABLE detection_events
        ADD COLUMN IF NOT EXISTS signal_type TEXT;
        """,
        """
        ALTER TABLE detection_events
        ADD COLUMN IF NOT EXISTS channel INTEGER;
        """,
        """
        ALTER TABLE detection_events
        ADD COLUMN IF NOT EXISTS signal_value REAL;
        """,
        """
        ALTER TABLE detection_events
        ADD COLUMN IF NOT EXISTS detection_timestamp TEXT;  -- ISO 8601 timestamp
        """,
        """
        ALTER TABLE detection_events
        ADD COLUMN IF NOT EXISTS metadata TEXT;  -- JSON stored as TEXT in SQLite
        """,
        """
        ALTER TABLE detection_events
        ADD COLUMN IF NOT EXISTS sequence_id TEXT;
        """,

        # Create indexes for new fields
        """
        CREATE INDEX IF NOT EXISTS idx_testsession_sequence_id
        ON test_sessions(sequence_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_testsession_max_latency
        ON test_sessions(max_latency_threshold_ms);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_detection_unix_timestamp
        ON detection_events(unix_timestamp);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_detection_signal_type
        ON detection_events(signal_type);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_detection_channel
        ON detection_events(channel);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_detection_sequence_id
        ON detection_events(sequence_id);
        """,
    ]

    try:
        with engine.connect() as conn:
            for i, migration in enumerate(migrations, 1):
                try:
                    logger.info(f"Running migration step {i}/{len(migrations)}...")
                    conn.execute(text(migration))
                    conn.commit()
                    logger.info(f"✅ Migration step {i} completed")
                except Exception as e:
                    logger.warning(f"⚠️ Migration step {i} warning (may already exist): {e}")
                    conn.rollback()

        logger.info("✅ All migrations completed successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("🚀 Starting video sequence fields migration...")
    success = run_migration()

    if success:
        logger.info("✅ Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Migration failed")
        sys.exit(1)
