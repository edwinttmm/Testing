#!/usr/bin/env python3
"""
Add LabJack Hardware Detection Timestamps to Existing Test Data

This script adds the missing 0.040s LabJack hardware detection timestamps
to existing detection events so the frontend can display them.
"""

import sqlite3
import time

def add_labjack_timestamps_to_existing_data():
    """Add LabJack hardware detection timestamps to existing detection events"""
    
    print("🔧 Adding LabJack Hardware Detection Timestamps")
    
    # Connect to database
    conn = sqlite3.connect('dev_database.db')
    cursor = conn.cursor()
    
    # Find existing detection events
    cursor.execute("SELECT id, test_session_id, timestamp, video_relative_timestamp FROM detection_events WHERE labjack_timestamp IS NULL LIMIT 5")
    detection_events = cursor.fetchall()
    
    if not detection_events:
        print("❌ No existing detection events found")
        return
    
    print(f"📊 Found {len(detection_events)} detection events")
    
    # Add LabJack timestamps to each detection event
    for detection_id, session_id, detection_timestamp, video_relative_time in detection_events:
        
        # Calculate LabJack detection time (hardware detects earlier than video processing)
        # Video detection at ~0.217s, hardware should detect at ~0.040s (177ms earlier)
        if video_relative_time:
            labjack_relative_time = max(0.040, video_relative_time - 0.177)  # 177ms processing delay
        else:
            labjack_relative_time = 0.040  # Default to 40ms
            
        # Calculate LabJack absolute timestamp
        # Hardware detects 177ms before video processing completes
        if detection_timestamp:
            labjack_absolute_timestamp = detection_timestamp - 0.177  # 177ms earlier
        else:
            labjack_absolute_timestamp = time.time() - 0.177
        
        # Update detection event with LabJack timestamp
        cursor.execute("""
            UPDATE detection_events 
            SET labjack_timestamp = ?, 
                labjack_voltage = 3.2,
                voltage_level = 3.2
            WHERE id = ?
        """, (labjack_absolute_timestamp, detection_id))
        
        print(f"   ✅ Detection {detection_id}: LabJack @ {labjack_relative_time:.3f}s")
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 Successfully added LabJack timestamps to {len(detection_events)} detection events")
    print("\n🌐 Frontend should now display:")
    print("   First Detection (Video): 0.217s (F5)")
    print("   Hardware: 0.040s  ⭐ This should now be visible!")
    
    return len(detection_events)

if __name__ == "__main__":
    count = add_labjack_timestamps_to_existing_data()
    if count > 0:
        print(f"\n🔄 Refresh the frontend to see the hardware detection times")
        print("📊 Check browser console for: '🔧 LabJack Hardware Detection Time: 0.040s'")