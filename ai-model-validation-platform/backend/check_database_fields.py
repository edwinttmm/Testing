#!/usr/bin/env python3
"""
Check Database Fields
This script checks what fields are available in the detection_events table.
"""

import sqlite3
import sys

def check_database_fields():
    """Check what fields exist in the detection_events table"""
    print("🔍 Checking Database Fields...")
    
    try:
        # Connect to database
        conn = sqlite3.connect('dev_database.db')
        cursor = conn.cursor()
        
        # Get table schema
        cursor.execute("PRAGMA table_info(detection_events)")
        columns = cursor.fetchall()
        
        print(f"📊 detection_events table has {len(columns)} columns:")
        for col in columns:
            col_id, name, col_type, not_null, default, pk = col
            print(f"   {name}: {col_type} (nullable: {not not_null})")
        
        # Check for video timing fields specifically
        video_fields = ['video_relative_timestamp', 'video_frame_number']
        existing_video_fields = []
        
        for col in columns:
            if col[1] in video_fields:
                existing_video_fields.append(col[1])
        
        print(f"\n📹 Video timing fields found: {existing_video_fields}")
        
        # Check a sample detection event for our test session
        session_id = "b7481a7d-b4d2-4425-afe1-235c7b29a8b5"
        cursor.execute("SELECT * FROM detection_events WHERE test_session_id = ? LIMIT 1", (session_id,))
        row = cursor.fetchone()
        
        if row:
            column_names = [desc[0] for desc in cursor.description]
            print(f"\n🔬 Sample detection event fields for session {session_id}:")
            for i, (name, value) in enumerate(zip(column_names, row)):
                if 'video' in name.lower() or 'timestamp' in name.lower() or 'frame' in name.lower():
                    print(f"   {name}: {value}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"💥 Error: {e}")
        return False

def main():
    print("🚀 Database Field Checker")
    print("=" * 50)
    
    check_database_fields()

if __name__ == "__main__":
    main()