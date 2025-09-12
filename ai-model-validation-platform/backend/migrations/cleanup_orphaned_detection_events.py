#!/usr/bin/env python3
"""
Database Cleanup: Remove orphaned detection_events
This script removes detection_events that reference non-existent test_sessions
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import get_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_orphaned_detection_events():
    """Remove orphaned detection_events and update remaining records"""
    
    db = next(get_db())
    
    try:
        logger.info("🧹 Starting cleanup: Remove orphaned detection_events")
        
        # Step 1: Count orphaned records
        orphaned_count = db.execute(text("""
            SELECT COUNT(*) as count
            FROM detection_events de
            LEFT JOIN test_sessions ts ON de.test_session_id = ts.id
            WHERE ts.id IS NULL
        """)).fetchone().count
        
        logger.info(f"📊 Found {orphaned_count} orphaned detection_events")
        
        if orphaned_count == 0:
            logger.info("✅ No orphaned records found")
            return True
        
        # Step 2: Delete orphaned records
        logger.info("🗑️  Deleting orphaned detection_events...")
        result = db.execute(text("""
            DELETE FROM detection_events
            WHERE id IN (
                SELECT de.id 
                FROM detection_events de
                LEFT JOIN test_sessions ts ON de.test_session_id = ts.id
                WHERE ts.id IS NULL
            )
        """))
        
        deleted_count = result.rowcount
        logger.info(f"🗑️  Deleted {deleted_count} orphaned detection_events")
        
        # Step 3: Update remaining records with video_id
        logger.info("🔄 Updating remaining detection_events with video_id...")
        result = db.execute(text("""
            UPDATE detection_events 
            SET video_id = (
                SELECT test_sessions.video_id 
                FROM test_sessions 
                WHERE test_sessions.id = detection_events.test_session_id
            )
            WHERE video_id IS NULL
        """))
        
        updated_count = result.rowcount
        logger.info(f"✅ Updated {updated_count} detection_events with video_id")
        
        db.commit()
        
        # Step 4: Verify cleanup
        logger.info("📝 Verifying cleanup...")
        
        # Check for remaining NULL video_id
        remaining_null = db.execute(text("""
            SELECT COUNT(*) as count FROM detection_events WHERE video_id IS NULL
        """)).fetchone().count
        
        # Check for remaining orphaned records
        remaining_orphaned = db.execute(text("""
            SELECT COUNT(*) as count
            FROM detection_events de
            LEFT JOIN test_sessions ts ON de.test_session_id = ts.id
            WHERE ts.id IS NULL
        """)).fetchone().count
        
        # Get final count
        total_remaining = db.execute(text("""
            SELECT COUNT(*) as count FROM detection_events
        """)).fetchone().count
        
        logger.info("✅ Cleanup complete:")
        logger.info(f"   - Deleted orphaned records: {deleted_count}")
        logger.info(f"   - Updated with video_id: {updated_count}")
        logger.info(f"   - Total remaining detection_events: {total_remaining}")
        logger.info(f"   - Remaining NULL video_id: {remaining_null}")
        logger.info(f"   - Remaining orphaned: {remaining_orphaned}")
        
        if remaining_null > 0 or remaining_orphaned > 0:
            logger.warning(f"⚠️ Still have issues: {remaining_null} NULL video_id, {remaining_orphaned} orphaned")
        else:
            logger.info("🎉 All detection_events now have valid video_id relationships!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = cleanup_orphaned_detection_events()
    exit(0 if success else 1)