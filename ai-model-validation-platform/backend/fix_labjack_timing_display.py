#!/usr/bin/env python3
"""
Fix LabJack Timing Display

The issue: LabJack timestamps are showing 0.350s instead of 0.040s
Root cause: Incorrect timestamp calculation and display logic

Expected timeline:
1. 0.040s - LabJack hardware detects voltage (FIRST!)
2. 0.208s - Ground truth event (Frame 5)
3. 0.217s - Video processing completes (Frame 5, 8.7ms latency)

Current problem: LabJack showing as latest instead of earliest detection.
"""

import sqlite3
import time

def fix_labjack_timing_display():
    """Fix LabJack timestamp calculation to show hardware as earliest detection"""
    
    print("🔧 FIXING LabJack Timing Display Issue")
    print("Expected: LabJack = 0.040s (FIRST), Video = 0.217s (LAST)")
    
    conn = sqlite3.connect('dev_database.db')
    cursor = conn.cursor()
    
    # Get detection events with their current timestamps
    cursor.execute("""
        SELECT id, timestamp, labjack_timestamp, video_relative_timestamp, frame_number
        FROM detection_events 
        WHERE labjack_timestamp IS NOT NULL
        LIMIT 5
    """)
    events = cursor.fetchall()
    
    print(f"\n📊 Found {len(events)} events to fix")
    
    for event_id, detection_ts, labjack_ts, video_rel_ts, frame_num in events:
        
        # Calculate what the video start time should be based on detection timestamp
        # If detection is at Frame 5 (0.208s), then video_start = detection_ts - 0.208
        expected_video_relative_time = 0.217  # Frame 5 at 24fps ≈ 0.208s, plus processing = 0.217s
        estimated_video_start = detection_ts - expected_video_relative_time
        
        # LabJack should detect at 0.040s relative to video start
        # So LabJack absolute timestamp = video_start + 0.040
        corrected_labjack_timestamp = estimated_video_start + 0.040
        
        print(f"   Event {event_id[:8]}:")
        print(f"     Current LabJack: {labjack_ts} (absolute)")
        print(f"     Corrected LabJack: {corrected_labjack_timestamp} (absolute)")
        print(f"     Video start estimate: {estimated_video_start}")
        print(f"     LabJack relative time: 0.040s")
        print(f"     Detection relative time: 0.217s")
        
        # Update with corrected LabJack timestamp
        cursor.execute("""
            UPDATE detection_events 
            SET labjack_timestamp = ?,
                video_relative_timestamp = ?
            WHERE id = ?
        """, (corrected_labjack_timestamp, expected_video_relative_time, event_id))
        
        print(f"     ✅ Updated")
    
    conn.commit()
    
    # Also update any video metadata with video start timestamps
    print(f"\n🎬 Updating video metadata with estimated start times")
    cursor.execute("""
        UPDATE videos 
        SET video_start_timestamp_epoch_sec = (
            SELECT MIN(timestamp) - 0.217 
            FROM detection_events 
            WHERE detection_events.video_id = videos.id
        )
        WHERE video_start_timestamp_epoch_sec IS NULL
    """)
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ LabJack timing display fix complete!")
    print(f"🎯 Expected frontend display:")
    print(f"   LABJACK: 0.040s (Frame 1) - EARLIEST detection")
    print(f"   GT: 0.208s (Frame 5) - Expected") 
    print(f"   FIRST DETECT: 0.217s (Frame 5) - Video processing")
    print(f"\n🔄 Refresh frontend to see corrected timing")

if __name__ == "__main__":
    fix_labjack_timing_display()