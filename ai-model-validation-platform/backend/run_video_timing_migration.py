#!/usr/bin/env python3
"""
Run Video Timing Synchronization Migration

This script adds the video timing synchronization columns to the database
for HIL (Hardware-in-the-Loop) validation tests.
"""

import sys
import os
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

# Add current directory to path to import local modules
sys.path.insert(0, os.path.dirname(__file__))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment or use default"""
    return os.getenv('DATABASE_URL', 'sqlite:///dev_database.db')

def run_migration():
    """Run the video timing synchronization migration"""
    try:
        # Connect to database
        database_url = get_database_url()
        engine = create_engine(database_url)
        
        logger.info(f"Connected to database: {database_url}")
        
        with engine.connect() as conn:
            # Get table inspector
            inspector = inspect(conn)
            
            # Check if test_sessions table exists
            if 'test_sessions' not in inspector.get_table_names():
                logger.error("test_sessions table not found!")
                return False
            
            # Check if detection_events table exists
            if 'detection_events' not in inspector.get_table_names():
                logger.error("detection_events table not found!")
                return False
            
            # Get existing columns
            ts_columns = {col['name'] for col in inspector.get_columns('test_sessions')}
            de_columns = {col['name'] for col in inspector.get_columns('detection_events')}
            
            logger.info(f"Found {len(ts_columns)} columns in test_sessions table")
            logger.info(f"Found {len(de_columns)} columns in detection_events table")
            
            # Add columns to test_sessions table
            logger.info("Adding video timing columns to test_sessions table...")
            
            ts_columns_to_add = [
                ("video_playback_start_time", "REAL"),
                ("video_playback_start_time_ns", "TEXT"),
                ("hil_timing_enabled", "BOOLEAN DEFAULT 1"),
                ("video_timing_sync_status", "TEXT DEFAULT 'pending'")
            ]
            
            for column_name, column_type in ts_columns_to_add:
                if column_name not in ts_columns:
                    try:
                        sql = f"ALTER TABLE test_sessions ADD COLUMN {column_name} {column_type}"
                        conn.execute(text(sql))
                        logger.info(f"✅ Added column: test_sessions.{column_name}")
                    except SQLAlchemyError as e:
                        logger.warning(f"⚠️ Failed to add column {column_name}: {e}")
                else:
                    logger.info(f"⏭️ Column already exists: test_sessions.{column_name}")
            
            # Add columns to detection_events table
            logger.info("Adding video timing columns to detection_events table...")
            
            de_columns_to_add = [
                ("video_relative_timestamp", "REAL"),
                ("video_relative_timestamp_ns", "TEXT"),
                ("actual_latency_ms", "REAL"),
                ("video_frame_number", "INTEGER"),
                ("timing_sync_quality", "TEXT DEFAULT 'unknown'")
            ]
            
            for column_name, column_type in de_columns_to_add:
                if column_name not in de_columns:
                    try:
                        sql = f"ALTER TABLE detection_events ADD COLUMN {column_name} {column_type}"
                        conn.execute(text(sql))
                        logger.info(f"✅ Added column: detection_events.{column_name}")
                    except SQLAlchemyError as e:
                        logger.warning(f"⚠️ Failed to add column {column_name}: {e}")
                else:
                    logger.info(f"⏭️ Column already exists: detection_events.{column_name}")
            
            # Commit changes
            conn.commit()
            logger.info("✅ Video timing synchronization migration completed successfully!")
            
            # Verify columns were added
            ts_columns_after = {col['name'] for col in inspector.get_columns('test_sessions')}
            de_columns_after = {col['name'] for col in inspector.get_columns('detection_events')}
            
            logger.info(f"test_sessions now has {len(ts_columns_after)} columns")
            logger.info(f"detection_events now has {len(de_columns_after)} columns")
            
            return True
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting video timing synchronization migration...")
    success = run_migration()
    
    if success:
        logger.info("🎉 Migration completed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Migration failed!")
        sys.exit(1)