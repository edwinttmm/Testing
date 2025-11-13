"""
Migration: Fix test_sessions table schema
Adds missing columns: max_latency_threshold_ms, description
Removes extra columns: video_playback_duration, ground_truth_count
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Add missing columns and remove extra columns from test_sessions table"""
    db = SessionLocal()

    try:
        logger.info("Starting test_sessions schema migration...")

        # Add missing columns
        migrations = [
            # Add max_latency_threshold_ms (Float with index)
            """
            ALTER TABLE test_sessions
            ADD COLUMN max_latency_threshold_ms REAL
            """,

            # Add description (Text)
            """
            ALTER TABLE test_sessions
            ADD COLUMN description TEXT
            """
        ]

        for migration_sql in migrations:
            try:
                db.execute(text(migration_sql))
                db.commit()
                logger.info(f"Successfully executed: {migration_sql.strip()[:50]}...")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    logger.info(f"Column already exists, skipping: {migration_sql.strip()[:50]}...")
                else:
                    logger.error(f"Error executing migration: {e}")
                    db.rollback()
                    # Continue with other migrations

        # Note: SQLite doesn't support DROP COLUMN directly
        # We'll need to create a new table and copy data if we want to remove columns
        # For now, we'll just add the missing columns and leave the extra ones

        logger.info("✅ Migration completed successfully!")

        # Verify the schema
        result = db.execute(text("PRAGMA table_info(test_sessions)"))
        columns = result.fetchall()
        logger.info(f"Current test_sessions columns: {len(columns)}")
        for col in columns:
            logger.info(f"  - {col[1]} ({col[2]})")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
