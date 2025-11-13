#!/usr/bin/env python3
"""
Run Multi-Video Schema Migration
=================================
Adds video_count, video_sequences, current_video_index, video_start_time, completed_videos
to test_sessions table for multi-video support.
"""

import sys
import os
import sqlite3
import json
import logging
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migration():
    """Execute migration to add multi-video fields to test_sessions"""

    db_path = backend_dir / "dev_database.db"

    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return False

    logger.info("="*80)
    logger.info("🚀 Starting Multi-Video Schema Migration")
    logger.info("="*80)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    migrations = [
        # Add video_count
        ("video_count", "ALTER TABLE test_sessions ADD COLUMN video_count INTEGER DEFAULT 1"),

        # Add video_sequences (JSON stored as TEXT in SQLite)
        ("video_sequences", "ALTER TABLE test_sessions ADD COLUMN video_sequences TEXT"),

        # Add current_video_index
        ("current_video_index", "ALTER TABLE test_sessions ADD COLUMN current_video_index INTEGER DEFAULT 0"),

        # Add video_start_time
        ("video_start_time", "ALTER TABLE test_sessions ADD COLUMN video_start_time FLOAT"),

        # Add completed_videos (JSON array as TEXT)
        ("completed_videos", "ALTER TABLE test_sessions ADD COLUMN completed_videos TEXT"),
    ]

    indexes = [
        ("idx_test_sessions_video_count", "CREATE INDEX IF NOT EXISTS idx_test_sessions_video_count ON test_sessions(video_count)"),
        ("idx_test_sessions_current_video", "CREATE INDEX IF NOT EXISTS idx_test_sessions_current_video ON test_sessions(current_video_index)"),
    ]

    try:
        # Add columns
        for column_name, sql in migrations:
            try:
                logger.info(f"Adding column: {column_name}")
                cursor.execute(sql)
                conn.commit()
                logger.info(f"✅ Added column: {column_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.info(f"⚠️  Column {column_name} already exists, skipping")
                else:
                    raise

        # Create indexes
        for index_name, sql in indexes:
            try:
                logger.info(f"Creating index: {index_name}")
                cursor.execute(sql)
                conn.commit()
                logger.info(f"✅ Created index: {index_name}")
            except sqlite3.OperationalError as e:
                logger.warning(f"⚠️  Index {index_name}: {e}")

        # Verify columns exist
        logger.info("\n" + "="*80)
        logger.info("🔍 Verifying Migration")
        logger.info("="*80)

        cursor.execute("PRAGMA table_info(test_sessions)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        required_columns = {
            'video_count': 'INTEGER',
            'video_sequences': 'TEXT',
            'current_video_index': 'INTEGER',
            'video_start_time': 'FLOAT',
            'completed_videos': 'TEXT'
        }

        all_present = True
        for col_name, expected_type in required_columns.items():
            if col_name in columns:
                logger.info(f"✅ {col_name:<25} {columns[col_name]}")
            else:
                logger.error(f"❌ {col_name:<25} MISSING")
                all_present = False

        conn.close()

        logger.info("\n" + "="*80)
        if all_present:
            logger.info("✅ Multi-Video Schema Migration Completed Successfully")
        else:
            logger.error("❌ Migration Incomplete - Some Columns Missing")
        logger.info("="*80)

        return all_present

    except Exception as e:
        conn.rollback()
        conn.close()
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
