#!/usr/bin/env python3
"""
Check Ground Truth Data
This script checks what ground truth data is available.
"""

import sqlite3
import sys

def check_ground_truth_data():
    """Check what ground truth data exists"""
    print("🔍 Checking Ground Truth Data...")
    
    try:
        # Connect to database
        conn = sqlite3.connect('dev_database.db')
        cursor = conn.cursor()
        
        session_id = "b7481a7d-b4d2-4425-afe1-235c7b29a8b5"
        
        # Check for test session details
        cursor.execute("SELECT video_id FROM test_sessions WHERE id = ?", (session_id,))
        session_result = cursor.fetchone()
        
        if session_result:
            video_id = session_result[0]
            print(f"📊 Test session {session_id} has video_id: {video_id}")
            
            # Check for ground truth objects for this video
            if video_id:
                cursor.execute("SELECT COUNT(*) FROM ground_truth_objects WHERE video_id = ?", (video_id,))
                gt_count = cursor.fetchone()[0]
                print(f"📹 Found {gt_count} ground truth objects for video {video_id}")
                
                if gt_count > 0:
                    cursor.execute("SELECT frame_number, timestamp, class_label FROM ground_truth_objects WHERE video_id = ? ORDER BY frame_number LIMIT 10", (video_id,))
                    gt_samples = cursor.fetchall()
                    print(f"🎯 Sample ground truth data:")
                    for frame, timestamp, label in gt_samples:
                        print(f"   Frame {frame}: {timestamp}s - {label}")
                else:
                    print(f"❌ No ground truth objects found for video {video_id}")
            else:
                print(f"❌ No video_id associated with session {session_id}")
        else:
            print(f"❌ Test session {session_id} not found")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"💥 Error: {e}")
        return False

def main():
    print("🚀 Ground Truth Data Checker")
    print("=" * 50)
    
    check_ground_truth_data()

if __name__ == "__main__":
    main()