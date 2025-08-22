#!/usr/bin/env python3
"""Fix detection_events table schema by adding missing detection_id column"""

from database import engine
from sqlalchemy import text, inspect
import sys

def check_and_fix_detection_events_table():
    """Check and fix the detection_events table schema"""
    
    try:
        # Get inspector
        inspector = inspect(engine)
        
        # Check if table exists
        if 'detection_events' not in inspector.get_table_names():
            print("❌ Error: detection_events table does not exist!")
            return False
            
        # Get current columns
        columns = [col['name'] for col in inspector.get_columns('detection_events')]
        print(f"Current columns in detection_events: {columns}")
        
        # Check if detection_id column exists
        if 'detection_id' not in columns:
            print("⚠️ Missing detection_id column. Adding it now...")
            
            with engine.connect() as conn:
                # Add the missing column
                conn.execute(text("""
                    ALTER TABLE detection_events 
                    ADD COLUMN detection_id VARCHAR(36)
                """))
                conn.commit()
                print("✅ Successfully added detection_id column!")
        else:
            print("✅ detection_id column already exists")
            
        # Verify the fix
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('detection_events')]
        print(f"Updated columns: {columns}")
        
        if 'detection_id' in columns:
            print("✅ Schema fix verified successfully!")
            return True
        else:
            print("❌ Failed to add detection_id column")
            return False
            
    except Exception as e:
        print(f"❌ Error fixing schema: {e}")
        return False

if __name__ == "__main__":
    success = check_and_fix_detection_events_table()
    sys.exit(0 if success else 1)