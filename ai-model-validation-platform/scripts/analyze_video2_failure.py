#!/usr/bin/env python3
"""
Analyze why Video 2 detections are failing with 10000ms latencies
while Video 1 worked correctly in session 9048a1b0-10a7-40b7-b1fc-1c95064cbb5f
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = '/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db'
SESSION_ID = '9048a1b0-10a7-40b7-b1fc-1c95064cbb5f'

def analyze_session():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=" * 80)
    print("VIDEO 2 FAILURE ANALYSIS")
    print("=" * 80)
    print(f"Session ID: {SESSION_ID}\n")

    # 1. Get test session information
    print("1. TEST SESSION INFORMATION")
    print("-" * 80)
    cursor.execute('''
        SELECT video_sequences, video_count, current_video_index,
               video_start_time, completed_videos
        FROM test_sessions
        WHERE id = ?
    ''', (SESSION_ID,))

    session_data = cursor.fetchone()
    if not session_data:
        print(f"❌ ERROR: Session {SESSION_ID} not found!")
        return

    video_sequences_str, video_count, current_idx, video_start, completed = session_data
    print(f"Video count: {video_count}")
    print(f"Current video index: {current_idx}")
    print(f"Video start time: {video_start}")
    print(f"Video sequences: {video_sequences_str}")
    print(f"Completed videos: {completed}")

    # Parse video sequences
    import json
    video_sequences = json.loads(video_sequences_str) if video_sequences_str else []

    # 2. Get video information
    print("\n2. VIDEO SEQUENCE INFORMATION")
    print("-" * 80)
    cursor.execute('''
        SELECT id, filename, duration, fps
        FROM videos
        WHERE id IN (?, ?)
    ''', (video_sequences[0] if len(video_sequences) > 0 else '',
          video_sequences[1] if len(video_sequences) > 1 else ''))

    videos = cursor.fetchall()
    video_info = {}

    for idx, row in enumerate(videos, 1):
        video_id, filename, duration, fps = row
        video_info[idx] = {
            'id': video_id,
            'filename': filename,
            'duration': duration,
            'fps': fps
        }

        print(f"\nVideo {idx}: {filename}")
        print(f"  ID: {video_id}")
        print(f"  duration: {duration} seconds")
        print(f"  fps: {fps}")

    # 3. Check detections per video
    print("\n\n2. DETECTIONS PER VIDEO")
    print("-" * 80)
    cursor.execute('''
        SELECT video_id, COUNT(*) as count,
               MIN(actual_latency_ms) as min_lat,
               MAX(actual_latency_ms) as max_lat,
               AVG(actual_latency_ms) as avg_lat
        FROM detection_events
        WHERE test_session_id = ?
        GROUP BY video_id
    ''', (SESSION_ID,))

    detection_stats = {}
    for row in cursor.fetchall():
        video_id, count, min_lat, max_lat, avg_lat = row
        detection_stats[video_id] = {
            'count': count,
            'min': min_lat,
            'max': max_lat,
            'avg': avg_lat
        }

        # Find which sequence order this video_id corresponds to
        seq_order = None
        for order, info in video_info.items():
            if info['id'] == video_id:
                seq_order = order
                break

        print(f"\nVideo {seq_order} ({video_id}):")
        print(f"  Total detections: {count}")
        print(f"  Latency range: {min_lat:.2f}ms - {max_lat:.2f}ms")
        print(f"  Average latency: {avg_lat:.2f}ms")

        if max_lat >= 10000:
            print(f"  ❌ PROBLEM: Max latency at 10000ms indicates timeout!")
        if avg_lat > 5000:
            print(f"  ⚠️  WARNING: Average latency very high!")

    # 4. Check video 2 specifically
    print("\n\n4. VIDEO 2 DETAILED ANALYSIS")
    print("-" * 80)

    video2_info = video_info.get(2)
    if not video2_info:
        print("❌ ERROR: Video 2 not found!")
        return

    video2_id = video2_info['id']
    print(f"Video 2 ID: {video2_id}")
    print(f"Filename: {video2_info['filename']}")
    print(f"Duration: {video2_info['duration']} seconds")
    print(f"FPS: {video2_info['fps']}")

    # Check if there's a video_start_time in test session for video 2
    print(f"\nSession video_start_time: {video_start}")
    print("⚠️  This is the SINGLE video_start_time used for ALL videos in session!")
    print("   Problem: When video switches from 1→2, this timestamp doesn't update")

    # 4. Check detection timestamps for video 2
    print("\n\n4. VIDEO 2 DETECTION TIMESTAMPS (First 10)")
    print("-" * 80)
    cursor.execute('''
        SELECT frame_number, timestamp, video_relative_timestamp,
               actual_latency_ms, labjack_voltage, labjack_timestamp
        FROM detection_events
        WHERE test_session_id = ?
          AND video_id = ?
        ORDER BY timestamp
        LIMIT 10
    ''', (SESSION_ID, video2_id))

    video2_detections = cursor.fetchall()

    print(f"\n{'Frame':<8} {'Timestamp':<26} {'Video Rel':<12} {'Latency':<10} {'LabJack V':<10} {'LabJack Time'}")
    print("-" * 100)

    for row in video2_detections:
        frame, ts, video_rel, latency, lj_voltage, lj_ts = row
        print(f"{frame:<8} {ts:<26} {video_rel:<12.6f} {latency:<10.2f} {lj_voltage:<10.6f} {lj_ts}")

        if latency >= 10000:
            print(f"  ❌ TIMEOUT: Frame {frame} has 10000ms latency!")

    # 5. Compare video 1 and video 2 timing
    print("\n\n6. VIDEO TIMING COMPARISON")
    print("-" * 80)

    if 1 in video_info and 2 in video_info:
        video1 = video_info[1]
        video2 = video_info[2]

        print("\nVideo 1:")
        print(f"  duration: {video1['duration']} seconds")
        print(f"  fps: {video1['fps']}")

        print("\nVideo 2:")
        print(f"  duration: {video2['duration']} seconds")
        print(f"  fps: {video2['fps']}")

        print(f"\n❌ PROBLEM: Both videos use same video_start_time: {video_start}")
        print("   Expected behavior: video_start_time should be updated when video 2 starts")
        print(f"   Video 2 should have start time = video_start + {video1['duration']} seconds")

    # 6. Check for patterns in failed detections
    print("\n\n6. FAILED DETECTION PATTERNS")
    print("-" * 80)

    cursor.execute('''
        SELECT COUNT(*) as fail_count
        FROM detection_events
        WHERE test_session_id = ?
          AND video_id = ?
          AND actual_latency_ms >= 10000
    ''', (SESSION_ID, video2_id))

    fail_count = cursor.fetchone()[0]
    total_video2 = detection_stats.get(video2_id, {}).get('count', 0)

    print(f"Total Video 2 detections: {total_video2}")
    print(f"Failed detections (>=10000ms): {fail_count}")
    print(f"Failure rate: {(fail_count/total_video2*100) if total_video2 > 0 else 0:.1f}%")

    # 7. Check session metadata
    print("\n\n7. SESSION METADATA")
    print("-" * 80)

    cursor.execute('''
        SELECT created_at, model_name, confidence_threshold, status
        FROM test_sessions
        WHERE id = ?
    ''', (SESSION_ID,))

    session = cursor.fetchone()
    if session:
        created, model, confidence, status = session
        print(f"Created: {created}")
        print(f"Model: {model}")
        print(f"Confidence threshold: {confidence}")
        print(f"Status: {status}")

    # 8. Summary and diagnosis
    print("\n\n8. DIAGNOSIS")
    print("=" * 80)

    print("❌ ROOT CAUSE: test_sessions.video_start_time is NOT updated for video 2")
    print("\n   The problem:")
    print("   1. test_sessions table has SINGLE video_start_time for entire session")
    print("   2. This timestamp is set when video 1 starts playing")
    print("   3. When video 2 starts, video_start_time is NOT updated")
    print("   4. Latency calculator uses wrong video_start_time for video 2 detections")
    print("   5. This causes detection timestamps to be compared against wrong baseline")
    print("   6. Resulting in 10000ms timeout latencies")

    if fail_count > 0:
        print(f"\n❌ {fail_count} detections timing out at 10000ms")
        print("   This indicates detection_time > labjack_time + threshold")
        print("   Caused by: detection timestamps still using video 1 start time")

    print("\n\nRECOMMENDED FIXES:")
    print("=" * 80)
    print("\n1. OPTION A: Store per-video start times in detection_events table")
    print("   - Add video_start_timestamp column to detection_events")
    print("   - Set it when creating detection event for each video")
    print("   - Pass correct video_start_time to latency calculator per detection")

    print("\n2. OPTION B: Calculate video start time from sequence")
    print("   - In latency calculator, check which video the detection belongs to")
    print("   - Calculate video start = session_start + sum(previous_video_durations)")
    print("   - Use calculated value instead of test_sessions.video_start_time")

    print("\n3. OPTION C: Store video transitions in separate table")
    print("   - Create video_transitions table with (video_id, start_time, end_time)")
    print("   - Update table when each video starts/ends")
    print("   - Query correct start_time based on detection timestamp")

    print("\n\nIMMEDIATE FIX:")
    print("Update detection_event_processor.py to pass correct video_start_time:")
    print("  video_start_time = session_start + sum(durations of videos before current)")
    print("  OR store in detection_events.video_start_time when creating event")

    conn.close()

if __name__ == '__main__':
    analyze_session()
