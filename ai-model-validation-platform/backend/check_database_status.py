#!/usr/bin/env python3
"""
Database Status Check - Quick analysis of detection data quality
"""

import sqlite3
from pathlib import Path

def check_database_status():
    db_path = Path("dev_database.db")
    if not db_path.exists():
        print("Database not found")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print("=== DATABASE STATUS ANALYSIS ===")
    
    # Overall detection statistics
    cursor.execute("""
        SELECT 
            COUNT(*) as total_detections,
            COUNT(labjack_timestamp) as with_labjack,
            COUNT(actual_latency_ms) as with_latency,
            COUNT(video_relative_timestamp) as with_video_relative
        FROM detection_events
    """)
    
    stats = cursor.fetchone()
    print(f"Total detections: {stats[0]}")
    print(f"With LabJack timestamp: {stats[1]} ({stats[1]/stats[0]*100:.1f}%)")
    print(f"With actual latency: {stats[2]} ({stats[2]/stats[0]*100:.1f}%)")
    print(f"With video relative timestamp: {stats[3]} ({stats[3]/stats[0]*100:.1f}%)")
    print()
    
    # Validation results
    cursor.execute("SELECT validation_result, COUNT(*) FROM detection_events GROUP BY validation_result")
    print("Validation results:")
    for result, count in cursor.fetchall():
        print(f"  {result}: {count}")
    print()
    
    # Recent test sessions
    cursor.execute("""
        SELECT name, video_id, status, created_at 
        FROM test_sessions 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    
    print("Recent test sessions:")
    sessions = cursor.fetchall()
    for session in sessions:
        print(f"  {session[0]} | {session[1][:8]}... | {session[2]} | {session[3]}")
    print()
    
    # Video analysis
    cursor.execute("SELECT filename, duration, fps FROM videos ORDER BY created_at DESC LIMIT 5")
    print("Recent videos:")
    for video in cursor.fetchall():
        print(f"  {video[0]} | {video[1]:.2f}s | {video[2]:.1f}fps")
    print()
    
    # Detection timing analysis for latest video
    cursor.execute("""
        SELECT v.filename, COUNT(de.id) as detection_count,
               MIN(de.timestamp) as first_detection,
               MAX(de.timestamp) as last_detection
        FROM videos v
        JOIN detection_events de ON v.id = de.video_id
        WHERE v.filename = 'Child_20250923_163333.mp4'
    """)
    
    video_analysis = cursor.fetchone()
    if video_analysis:
        print(f"Analysis for {video_analysis[0]}:")
        print(f"  Detections: {video_analysis[1]}")
        print(f"  Time range: {video_analysis[2]:.3f}s - {video_analysis[3]:.3f}s")
    
    conn.close()

if __name__ == "__main__":
    check_database_status()