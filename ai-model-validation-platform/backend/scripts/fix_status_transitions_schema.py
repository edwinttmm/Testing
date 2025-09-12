#!/usr/bin/env python3
"""
Fix video_status_transitions table schema mismatch

The SQLAlchemy model expects 'triggered_by' column but the table has
'triggered_by_user_id' and 'triggered_by_system' columns.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_status_transitions_schema():
    """Fix schema mismatch in video_status_transitions table"""
    
    with engine.connect() as conn:
        # Add the missing triggered_by column
        try:
            logger.info("Adding triggered_by column to video_status_transitions...")
            conn.execute(text("ALTER TABLE video_status_transitions ADD COLUMN triggered_by VARCHAR(36);"))
            conn.commit()
            logger.info("✅ Added triggered_by column")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                logger.info("triggered_by column already exists")
            else:
                logger.error(f"Failed to add triggered_by column: {e}")
                return False
        
        # Update triggered_by based on existing data
        try:
            logger.info("Updating triggered_by column with existing data...")
            # If triggered_by_system is true, set triggered_by to 'system'
            # Otherwise, use triggered_by_user_id value
            conn.execute(text("""
                UPDATE video_status_transitions 
                SET triggered_by = CASE 
                    WHEN triggered_by_system = 1 THEN 'system'
                    WHEN triggered_by_user_id IS NOT NULL THEN triggered_by_user_id
                    ELSE 'system'
                END
            """))
            conn.commit()
            logger.info("✅ Updated triggered_by column values")
        except Exception as e:
            logger.error(f"Failed to update triggered_by values: {e}")
            return False
        
        logger.info("✅ video_status_transitions schema fixed successfully")
        return True

if __name__ == "__main__":
    print("🔧 Fixing video_status_transitions Schema Mismatch")
    print("=" * 50)
    
    if fix_status_transitions_schema():
        print("✅ Schema fix completed successfully")
    else:
        print("❌ Schema fix failed")
        exit(1)