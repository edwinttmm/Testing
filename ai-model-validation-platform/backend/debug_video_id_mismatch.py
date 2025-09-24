#!/usr/bin/env python3
"""
Debug Video ID Mismatch
This script investigates the video_id mismatch between test sessions and ground truth objects.
"""

import sqlite3
import sys

def debug_video_id_mismatch():
    """Debug the video_id mismatch between test session and ground truth"""
    print("🔍 Debugging Video ID Mismatch...")
    
    try:
        # Connect to database
        conn = sqlite3.connect('dev_database.db')
        cursor = conn.cursor()
        
        session_id = "b7481a7d-b4d2-4425-afe1-235c7b29a8b5"
        
        # Check test session video_id
        cursor.execute("SELECT video_id FROM test_sessions WHERE id = ?", (session_id,))
        session_result = cursor.fetchone()
        
        if session_result:
            test_session_video_id = session_result[0]
            print(f"📊 Test session {session_id} has video_id: {test_session_video_id}")
            
            # Check all ground truth objects to see what video_ids exist
            cursor.execute("SELECT video_id, COUNT(*) FROM ground_truth_objects GROUP BY video_id")
            gt_video_ids = cursor.fetchall()
            
            print(f"🎯 Available ground truth video_ids:")
            for video_id, count in gt_video_ids:
                print(f"   video_id: {video_id} ({count} objects)")
                
            # Check if test session video_id has any ground truth
            cursor.execute("SELECT COUNT(*) FROM ground_truth_objects WHERE video_id = ?", (test_session_video_id,))
            gt_count_for_session = cursor.fetchone()[0]
            print(f"📹 Ground truth objects for test session video_id: {gt_count_for_session}")
            
            # Check what video file is associated with the test session video_id
            cursor.execute("SELECT filename FROM videos WHERE id = ?", (test_session_video_id,))
            video_filename = cursor.fetchone()
            if video_filename:
                print(f"📂 Test session video file: {video_filename[0]}")
            else:
                print(f"❌ No video file found for video_id: {test_session_video_id}")
                
            # Check all videos to see what's available
            cursor.execute("SELECT id, filename FROM videos")
            all_videos = cursor.fetchall()
            print(f"🎬 All available videos:")
            for vid_id, filename in all_videos:
                cursor.execute("SELECT COUNT(*) FROM ground_truth_objects WHERE video_id = ?", (vid_id,))
                gt_count = cursor.fetchone()[0]
                print(f"   {vid_id}: {filename} ({gt_count} GT objects)")
            
        else:
            print(f"❌ Test session {session_id} not found")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"💥 Error: {e}")
        return False

def main():
    print("🚀 Video ID Mismatch Debug")
    print("=" * 50)
    
    debug_video_id_mismatch()

if __name__ == "__main__":
    main()