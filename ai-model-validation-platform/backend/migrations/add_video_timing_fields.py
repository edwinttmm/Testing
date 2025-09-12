"""
Database Migration: Add Video Timing Fields

This migration adds fields necessary for precise video timing synchronization
and latency measurement with LabJack detection events.

Fields Added:
- video_start_timestamp: High-precision video start time for latency calculation
- video_timing_metadata: JSON field for additional timing information

Run with: python migrations/add_video_timing_fields.py
"""

import sqlite3
import logging
import os
import json
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def get_database_path() -> str:
    """Get the database file path"""
    # Check common database locations
    possible_paths = [
        'test_database.db',
        'backend/test_database.db', 
        '../test_database.db',
        '/home/rigade/Testing/ai-model-validation-platform/backend/test_database.db'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Default to current directory
    return 'test_database.db'


def check_column_exists(cursor, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        return column_name in column_names
    except Exception as e:
        logger.error(f"Error checking column {column_name} in {table_name}: {e}")
        return False


def add_video_timing_fields():
    """Add video timing fields to test_sessions table"""
    
    db_path = get_database_path()
    logger.info(f"Using database: {db_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if fields already exist
        video_timestamp_exists = check_column_exists(cursor, 'test_sessions', 'video_start_timestamp')
        timing_metadata_exists = check_column_exists(cursor, 'test_sessions', 'video_timing_metadata')
        
        migrations_applied = []
        
        # Add video_start_timestamp if it doesn't exist
        if not video_timestamp_exists:
            logger.info("Adding video_start_timestamp column to test_sessions table")
            cursor.execute("""
                ALTER TABLE test_sessions 
                ADD COLUMN video_start_timestamp REAL
            """)
            
            # Create index for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_testsession_video_timing 
                ON test_sessions(video_start_timestamp)
            """)
            
            migrations_applied.append("video_start_timestamp")
        else:
            logger.info("video_start_timestamp column already exists")
        
        # Add video_timing_metadata if it doesn't exist
        if not timing_metadata_exists:
            logger.info("Adding video_timing_metadata column to test_sessions table")
            cursor.execute("""
                ALTER TABLE test_sessions 
                ADD COLUMN video_timing_metadata TEXT
            """)
            migrations_applied.append("video_timing_metadata")
        else:
            logger.info("video_timing_metadata column already exists")
        
        # Add composite index for video timing queries
        logger.info("Creating composite index for video timing queries")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_testsession_timing_status 
            ON test_sessions(video_start_timestamp, status)
        """)
        
        # Commit changes
        conn.commit()
        
        # Verify the changes
        cursor.execute("PRAGMA table_info(test_sessions)")
        columns = cursor.fetchall()
        
        timing_columns = [col for col in columns if 'timing' in col[1] or 'video_start' in col[1]]
        
        logger.info("Video timing fields in test_sessions table:")
        for col in timing_columns:
            logger.info(f"  - {col[1]} ({col[2]})")
        
        # Record migration in database
        migration_record = {
            "timestamp": datetime.now().isoformat(),
            "migration": "add_video_timing_fields",
            "fields_added": migrations_applied,
            "database_path": db_path
        }
        
        logger.info(f"Migration completed successfully: {migration_record}")
        
        return True
        
    except sqlite3.Error as e:
        logger.error(f"SQLite error during migration: {e}")
        if conn:
            conn.rollback()
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error during migration: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if conn:
            conn.close()


def verify_migration():
    """Verify that the migration was successful"""
    
    db_path = get_database_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check table structure
        cursor.execute("PRAGMA table_info(test_sessions)")
        columns = cursor.fetchall()
        
        required_fields = ['video_start_timestamp', 'video_timing_metadata']
        existing_fields = [col[1] for col in columns]
        
        verification_results = {}
        
        for field in required_fields:
            exists = field in existing_fields
            verification_results[field] = exists
            
            if exists:
                logger.info(f"✓ Field {field} exists in test_sessions table")
            else:
                logger.error(f"✗ Field {field} missing from test_sessions table")
        
        # Check indexes
        cursor.execute("PRAGMA index_list(test_sessions)")
        indexes = cursor.fetchall()
        
        timing_indexes = [idx for idx in indexes if 'timing' in idx[1]]
        logger.info(f"Video timing indexes: {[idx[1] for idx in timing_indexes]}")
        
        all_fields_exist = all(verification_results.values())
        
        if all_fields_exist:
            logger.info("✓ All video timing fields migration verified successfully")
        else:
            logger.error("✗ Video timing fields migration verification failed")
        
        return all_fields_exist
        
    except Exception as e:
        logger.error(f"Error verifying migration: {e}")
        return False
        
    finally:
        if conn:
            conn.close()


def rollback_migration():
    """Rollback the video timing fields migration"""
    
    db_path = get_database_path()
    logger.warning("Rolling back video timing fields migration")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Note: SQLite doesn't support DROP COLUMN directly
        # We would need to recreate the table without these columns
        # For now, we'll just log the rollback request
        
        logger.warning("SQLite doesn't support DROP COLUMN. Manual rollback required:")
        logger.warning("1. Create new table without video timing fields")
        logger.warning("2. Copy data from old table to new table")
        logger.warning("3. Drop old table and rename new table")
        
        return False
        
    except Exception as e:
        logger.error(f"Error during rollback: {e}")
        return False
        
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("Video Timing Fields Migration")
    print("=" * 40)
    
    # Run migration
    success = add_video_timing_fields()
    
    if success:
        print("\n✓ Migration completed successfully")
        
        # Verify migration
        print("\nVerifying migration...")
        verified = verify_migration()
        
        if verified:
            print("✓ Migration verification passed")
        else:
            print("✗ Migration verification failed")
            
    else:
        print("\n✗ Migration failed")
        print("Check logs for details")