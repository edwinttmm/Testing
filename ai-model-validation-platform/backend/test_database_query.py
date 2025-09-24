#!/usr/bin/env python3
"""
Test Database Query
This script tests the actual database query to see what fields are returned.
"""

import sqlite3
from sqlalchemy import create_engine, text
import sys

def test_database_query():
    """Test the actual database query used by the enhanced HIL endpoint"""
    print("🔍 Testing Database Query...")
    
    try:
        # Create SQLAlchemy engine
        engine = create_engine('sqlite:///dev_database.db')
        
        # Run the same query as the enhanced HIL endpoint
        session_id = "b7481a7d-b4d2-4425-afe1-235c7b29a8b5"
        detection_events_query = text("""
            SELECT id, test_session_id, frame_number, timestamp, actual_latency_ms, latency_ns,
                   processing_time_ms, voltage_level, labjack_voltage, labjack_timestamp,
                   detection_channel, validation_result, confidence, class_label, vru_type,
                   created_at, video_relative_timestamp, video_frame_number
            FROM detection_events 
            WHERE test_session_id = :session_id
            ORDER BY timestamp ASC
        """)
        
        with engine.connect() as conn:
            result = conn.execute(detection_events_query, {"session_id": session_id})
            rows = result.fetchall()
            
            print(f"📊 Found {len(rows)} rows")
            
            if rows:
                first_row = rows[0]
                print(f"\n🔬 First row attributes:")
                
                # Check if it has video timing fields
                video_rel_ts = getattr(first_row, 'video_relative_timestamp', 'NOT_FOUND')
                video_frame_num = getattr(first_row, 'video_frame_number', 'NOT_FOUND')
                
                print(f"   video_relative_timestamp: {video_rel_ts}")
                print(f"   video_frame_number: {video_frame_num}")
                
                # Try accessing as attributes vs dict-style
                print(f"\n🔍 Access methods:")
                try:
                    print(f"   first_row.video_relative_timestamp: {first_row.video_relative_timestamp}")
                except Exception as e:
                    print(f"   first_row.video_relative_timestamp: FAILED - {e}")
                
                try:
                    print(f"   first_row['video_relative_timestamp']: {first_row['video_relative_timestamp']}")
                except Exception as e:
                    print(f"   first_row['video_relative_timestamp']: FAILED - {e}")
                    
                # Check all available attributes
                print(f"\n📋 All available attributes/keys:")
                if hasattr(first_row, '_fields'):
                    print(f"   _fields: {first_row._fields}")
                if hasattr(first_row, 'keys'):
                    print(f"   keys(): {list(first_row.keys())}")
        
        return True
        
    except Exception as e:
        print(f"💥 Error: {e}")
        return False

def main():
    print("🚀 Database Query Test")
    print("=" * 50)
    
    test_database_query()

if __name__ == "__main__":
    main()