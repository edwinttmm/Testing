#!/usr/bin/env python3
"""
Fix Video Validation Status - Update videos to validated status
=============================================================

This script fixes the data contract mismatch by updating videos that have
completed ground truth processing to 'validated' status, making them available
for HIL test execution.
"""

import sqlite3
import os
import sys
import logging
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_path))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_video_validation_status(db_path):
    """Fix video validation status in the specified database."""
    logger.info(f"🔍 Checking database: {db_path}")
    
    if not os.path.exists(db_path):
        logger.warning(f"❌ Database not found: {db_path}")
        return False
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check current video statuses
        cursor.execute('''
            SELECT id, filename, status, processing_status, ground_truth_generated 
            FROM videos 
            WHERE processing_status = "completed" AND status != "validated"
        ''')
        
        videos_to_update = cursor.fetchall()
        
        if not videos_to_update:
            logger.info("✅ No videos need status update")
            return True
            
        logger.info(f"📋 Found {len(videos_to_update)} videos with completed processing")
        
        # Update videos to validated status
        updated_count = 0
        for video_id, filename, current_status, processing_status, gt_generated in videos_to_update:
            logger.info(f"📝 Updating {filename[:30]}... from '{current_status}' to 'validated'")
            
            cursor.execute('''
                UPDATE videos 
                SET status = "validated", updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (video_id,))
            
            updated_count += 1
        
        # Commit changes
        conn.commit()
        logger.info(f"✅ Successfully updated {updated_count} videos to 'validated' status")
        
        # Verify the changes
        cursor.execute("SELECT status, COUNT(*) FROM videos GROUP BY status")
        status_counts = cursor.fetchall()
        
        logger.info("📊 Updated video status distribution:")
        for status, count in status_counts:
            logger.info(f"  {status}: {count} videos")
            
        return True
        
    except Exception as e:
        logger.error(f"💥 Error updating video statuses: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def main():
    """Main function to fix video validation status across databases."""
    logger.info("🚀 Starting Video Validation Status Fix")
    
    # Database paths to check
    db_paths = [
        "test_database.db",
        "dev_database.db", 
        "simple_test.db",
        "ai_model_validation.db"
    ]
    
    success_count = 0
    
    for db_path in db_paths:
        if fix_video_validation_status(db_path):
            success_count += 1
    
    logger.info(f"🎉 Fix completed! Updated {success_count}/{len(db_paths)} databases")
    
    # Show final instructions
    logger.info("\n" + "="*60)
    logger.info("📋 Next Steps:")
    logger.info("1. Restart the backend server if it's running")
    logger.info("2. Navigate to the HIL Test Execution page")
    logger.info("3. Videos should now appear as 'validated' and ready for testing")
    logger.info("="*60)

if __name__ == "__main__":
    main()