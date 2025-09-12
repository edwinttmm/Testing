#!/usr/bin/env python3
"""
Database Migration: Add video_id to detection_events table
This migration adds the missing video_id foreign key to detection_events
and populates it from the related test_session.video_id
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, Column, String, ForeignKey, Index
from database import get_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_add_video_id():
    """Add video_id column to detection_events and populate from test_session"""
    
    db = next(get_db())
    
    try:
        logger.info("🔄 Starting migration: Add video_id to detection_events")
        
        # Step 1: Add the video_id column
        logger.info("📝 Step 1: Adding video_id column...")
        db.execute(text("""
            ALTER TABLE detection_events 
            ADD COLUMN video_id TEXT
        """))
        db.commit()
        logger.info("✅ video_id column added")
        
        # Step 2: Populate video_id from test_session
        logger.info("📝 Step 2: Populating video_id from test_sessions...")
        result = db.execute(text("""
            UPDATE detection_events 
            SET video_id = (
                SELECT test_sessions.video_id 
                FROM test_sessions 
                WHERE test_sessions.id = detection_events.test_session_id
            )
            WHERE video_id IS NULL
        """))
        db.commit()
        logger.info(f"✅ Updated {result.rowcount} detection_events with video_id")
        
        # Step 3: Add foreign key constraint (SQLite limitations - recreate index instead)
        logger.info("📝 Step 3: Adding index for video_id...")
        db.execute(text("""
            CREATE INDEX idx_detection_video_timestamp ON detection_events (video_id, timestamp)
        """))
        db.execute(text("""
            CREATE INDEX idx_detection_video_validation ON detection_events (video_id, validation_result)
        """))
        db.commit()
        logger.info("✅ Added indexes for video_id")
        
        # Step 4: Verify the migration
        logger.info("📝 Step 4: Verifying migration...")
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(video_id) as with_video_id,
                COUNT(CASE WHEN video_id IS NULL THEN 1 END) as null_video_id
            FROM detection_events
        """)).fetchone()
        
        logger.info(f"✅ Migration complete:")
        logger.info(f"   - Total detection_events: {result.total}")
        logger.info(f"   - With video_id: {result.with_video_id}")
        logger.info(f"   - NULL video_id: {result.null_video_id}")
        
        if result.null_video_id > 0:
            logger.warning(f"⚠️ {result.null_video_id} detection_events still have NULL video_id")
            
            # Show sample of records with NULL video_id
            null_records = db.execute(text("""
                SELECT id, test_session_id, timestamp 
                FROM detection_events 
                WHERE video_id IS NULL 
                LIMIT 5
            """)).fetchall()
            
            logger.warning("Sample records with NULL video_id:")
            for record in null_records:
                logger.warning(f"  - detection_event {record.id} -> test_session {record.test_session_id}")
        
        logger.info("🎉 Migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = migrate_add_video_id()
    exit(0 if success else 1)