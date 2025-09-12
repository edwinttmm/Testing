#!/usr/bin/env python3
"""
Migration script to add source and detection_type fields to DetectionEvent table
This fixes the "Manual" vs "AI" display issue in the frontend.
"""

import sqlite3
import sys
import os

def migrate_detection_events_table():
    """Add source and detection_type columns to detection_events table"""
    
    # Database path
    db_path = "./test_database.db"
    
    if not os.path.exists(db_path):
        print("❌ Database file not found at: " + db_path)
        return False
    
    print("🔄 Starting migration to add source and detection_type fields...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(detection_events)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add source column if it doesn't exist
        if 'source' not in columns:
            cursor.execute("""
                ALTER TABLE detection_events 
                ADD COLUMN source TEXT DEFAULT 'ai'
            """)
            print("✅ Added 'source' column with default value 'ai'")
        else:
            print("ℹ️  'source' column already exists")
        
        # Add detection_type column if it doesn't exist  
        if 'detection_type' not in columns:
            cursor.execute("""
                ALTER TABLE detection_events 
                ADD COLUMN detection_type TEXT DEFAULT 'automatic'
            """)
            print("✅ Added 'detection_type' column with default value 'automatic'")
        else:
            print("ℹ️  'detection_type' column already exists")
        
        # Update existing records to have proper values
        cursor.execute("""
            UPDATE detection_events 
            SET source = 'ai', detection_type = 'automatic'
            WHERE source IS NULL OR detection_type IS NULL
        """)
        
        affected_rows = cursor.rowcount
        print(f"✅ Updated {affected_rows} existing records with default values")
        
        # Create indexes for the new columns
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_detection_events_source ON detection_events(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_detection_events_detection_type ON detection_events(detection_type)")
            print("✅ Created indexes for new columns")
        except Exception as e:
            print(f"⚠️  Index creation warning (may already exist): {e}")
        
        # Commit changes
        conn.commit()
        print("✅ Migration completed successfully!")
        
        # Verify the changes
        cursor.execute("SELECT COUNT(*) FROM detection_events WHERE source = 'ai'")
        ai_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM detection_events")
        total_count = cursor.fetchone()[0]
        
        print(f"📊 Verification: {ai_count}/{total_count} detection events now have source='ai'")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    success = migrate_detection_events_table()
    sys.exit(0 if success else 1)