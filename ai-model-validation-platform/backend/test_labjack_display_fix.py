#!/usr/bin/env python3
"""
Test LabJack Display Fix

This script creates test data to verify the frontend correctly displays:
1. Video detection time (0.217s at Frame 5) - FIXED display bug
2. LabJack hardware detection time (0.040s) - NOW DISPLAYED

The key issue was that the 0.040s LabJack hardware detection time wasn't 
being shown in the frontend, even though the detection system was working correctly.
"""

import sqlite3
from datetime import datetime, timezone
import time

def create_test_data_with_labjack_timestamps():
    """Create test data that includes LabJack hardware detection timestamps"""
    
    print("🧪 Creating Test Data with LabJack Hardware Detection Times")
    
    # Connect to database
    conn = sqlite3.connect('dev_database.db')
    cursor = conn.cursor()
    
    # Get current time as base
    current_time = time.time()
    video_start_time = current_time
    
    print(f"   Video Start Time: {video_start_time}")
    print(f"   Ground Truth Event: {video_start_time + 0.208:.3f}s (Frame 5 @ 24fps)")
    print(f"   LabJack Detection: {video_start_time + 0.040:.3f}s (Hardware)")
    print(f"   Video Detection: {video_start_time + 0.217:.3f}s (Frame 5)")
    
    # Create project first
    project_id = "test-project-1"
    cursor.execute("""
        INSERT OR REPLACE INTO projects 
        (id, name, created_at)
        VALUES (?, ?, ?)
    """, (project_id, "Test Project", datetime.now()))
    
    # Create video
    video_id = "test-video-1" 
    cursor.execute("""
        INSERT OR REPLACE INTO videos (
            id, filename, file_path, fps,
            video_start_timestamp_epoch_sec,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (video_id, "test_video.mp4", "/path/to/video.mp4", 24, video_start_time, datetime.now()))
    
    # Insert test session
    session_id = "test-labjack-display-fix"
    cursor.execute("""
        INSERT OR REPLACE INTO test_sessions 
        (id, name, project_id, video_id, status, started_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session_id, "LabJack Display Fix Test", project_id, video_id, "completed", datetime.now(), datetime.now()))
    
    # Insert ground truth event at Frame 5 (0.208s)
    cursor.execute("""
        INSERT OR REPLACE INTO ground_truth_events 
        (id, session_id, timestamp, event_type, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("gt-1", session_id, 0.208, "detection", "Ground truth at Frame 5", datetime.now()))
    
    # Insert detection event with BOTH video detection time AND LabJack hardware detection time
    detection_event_id = "detection-with-labjack-1"
    cursor.execute("""
        INSERT OR REPLACE INTO detection_events (
            id, test_session_id, 
            timestamp, video_time_sec, frame_number, video_frame,
            labjack_timestamp,
            latency_ms, actual_latency_ms,
            confidence, class_label,
            processing_time_ms,
            voltage_level, labjack_voltage,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        detection_event_id, session_id,
        video_start_time + 0.217,  # Video detection timestamp 
        0.217,                     # Video relative time (Frame 5)
        5, 5,                      # Frame numbers
        video_start_time + 0.040,  # ⭐ LabJack hardware detection at 0.040s
        8.7,                       # 217ms - 208ms = 8.7ms latency (excellent!)
        8.7,
        0.95, "vehicle",
        12.5,                      # Processing time
        3.2, 3.2,                  # Voltage levels
        datetime.now()
    ))
    
    # Video metadata already inserted above
    
    conn.commit()
    conn.close()
    
    print("\n✅ Test data created successfully!")
    print("\n🎯 Expected Frontend Display:")
    print(f"   First Detection (Video): 0.217s (F5)")
    print(f"   Hardware: 0.040s")  # This should now be displayed!
    print(f"   Latency: 8.7ms (GT F5 @ 0.208s → Detection @ 0.217s)")
    
    return session_id

if __name__ == "__main__":
    session_id = create_test_data_with_labjack_timestamps()
    print(f"\n🌐 Test URL: http://localhost:3000/hil-results/{session_id}")
    print("📊 Check browser console for timing debug logs")
    print("👀 Look for 'Hardware: 0.040s' in the UI")