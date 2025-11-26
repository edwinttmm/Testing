#!/usr/bin/env python3
"""
Analyze Video 2 detection failures - Simplified version
"""

import sqlite3
import json

DB_PATH = '/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db'
SESSION_ID = '9048a1b0-10a7-40b7-b1fc-1c95064cbb5f'

def analyze_session():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=" * 80)
    print("VIDEO 2 FAILURE ANALYSIS")
    print("=" * 80)

    # Get all videos involved in this session
    cursor.execute('''
        SELECT DISTINCT v.id, v.filename, v.duration, v.fps
        FROM videos v
        JOIN detection_events de ON de.video_id = v.id
        WHERE de.test_session_id = ?
        ORDER BY v.filename
    ''', (SESSION_ID,))

    videos = cursor.fetchall()
    print("\n1. VIDEOS IN SESSION")
    print("-" * 80)

    video_map = {}
    for idx, (vid, filename, duration, fps) in enumerate(videos, 1):
        video_map[vid] = {
            'index': idx,
            'filename': filename,
            'duration': duration,
            'fps': fps
        }
        print(f"\nVideo {idx}: {filename}")
        print(f"  ID: {vid}")
        print(f"  Duration: {duration}s")
        print(f"  FPS: {fps}")

    # Get session info
    cursor.execute('''
        SELECT video_start_time, started_at, tolerance_ms
        FROM test_sessions
        WHERE id = ?
    ''', (SESSION_ID,))

    session = cursor.fetchone()
    video_start_time, started_at, tolerance_ms = session

    print("\n\n2. SESSION TIMING INFO")
    print("-" * 80)
    print(f"video_start_time: {video_start_time}")
    print(f"started_at: {started_at}")
    print(f"tolerance_ms: {tolerance_ms}")
    print("\n⚠️  PROBLEM: video_start_time is set ONCE for entire session")
    print("   It doesn't update when switching from video 1 → video 2")

    # Analyze detections per video
    print("\n\n3. DETECTIONS PER VIDEO")
    print("-" * 80)

    for vid, info in video_map.items():
        cursor.execute('''
            SELECT COUNT(*) as total,
                   MIN(actual_latency_ms) as min_lat,
                   MAX(actual_latency_ms) as max_lat,
                   AVG(actual_latency_ms) as avg_lat,
                   SUM(CASE WHEN actual_latency_ms >= 10000 THEN 1 ELSE 0 END) as timeout_count
            FROM detection_events
            WHERE test_session_id = ? AND video_id = ?
        ''', (SESSION_ID, vid))

        total, min_lat, max_lat, avg_lat, timeout_count = cursor.fetchone()

        print(f"\nVideo {info['index']}: {info['filename'][:40]}")
        print(f"  Total detections: {total}")
        print(f"  Latency range: {min_lat:.2f}ms - {max_lat:.2f}ms")
        print(f"  Average: {avg_lat:.2f}ms")
        print(f"  Timeouts (>=10000ms): {timeout_count}")

        if timeout_count > 0:
            print(f"  ❌ {timeout_count} detections timing out!")

    # Show sample detections from each video
    print("\n\n4. SAMPLE DETECTIONS")
    print("-" * 80)

    for vid, info in video_map.items():
        print(f"\nVideo {info['index']}: {info['filename'][:40]}")
        print(f"{'Frame':<8} {'Timestamp':<12} {'Video Rel':<12} {'Latency':<10} {'Status'}")
        print("-" * 60)

        cursor.execute('''
            SELECT frame_number, timestamp, video_relative_timestamp,
                   actual_latency_ms, latency_result
            FROM detection_events
            WHERE test_session_id = ? AND video_id = ?
            ORDER BY timestamp
            LIMIT 5
        ''', (SESSION_ID, vid))

        for row in cursor.fetchall():
            frame, ts, video_rel, latency, result = row
            status = "PASS" if latency < tolerance_ms else "FAIL"
            print(f"{frame or 'N/A':<8} {ts:<12.6f} {video_rel or 0:<12.6f} {latency:<10.2f} {status}")

    # Check detection_events.video_start_time column
    print("\n\n5. DETECTION EVENT VIDEO START TIMES")
    print("-" * 80)

    for vid, info in video_map.items():
        cursor.execute('''
            SELECT DISTINCT video_start_time
            FROM detection_events
            WHERE test_session_id = ? AND video_id = ?
        ''', (SESSION_ID, vid))

        start_times = cursor.fetchall()
        print(f"\nVideo {info['index']}: {info['filename'][:40]}")
        print(f"  video_start_time values in detection_events:")
        for (st,) in start_times:
            print(f"    {st}")

    # Check actual timestamps
    print("\n\n6. TIMESTAMP ANALYSIS")
    print("-" * 80)

    cursor.execute('''
        SELECT video_id,
               MIN(timestamp) as first_detection,
               MAX(timestamp) as last_detection,
               MAX(timestamp) - MIN(timestamp) as span
        FROM detection_events
        WHERE test_session_id = ?
        GROUP BY video_id
    ''', (SESSION_ID,))

    for row in cursor.fetchall():
        vid, first, last, span = row
        info = video_map[vid]
        print(f"\nVideo {info['index']}: {info['filename'][:40]}")
        print(f"  First detection: {first:.6f}")
        print(f"  Last detection: {last:.6f}")
        print(f"  Time span: {span:.6f}s")
        print(f"  Expected duration: {info['duration']}s")

    # DIAGNOSIS
    print("\n\n7. DIAGNOSIS")
    print("=" * 80)

    print("\n❌ ROOT CAUSE: video_start_time not tracked per video")
    print("\nThe problem:")
    print("1. test_sessions.video_start_time stores SINGLE timestamp")
    print("2. detection_events.video_start_time stores same value for ALL videos")
    print("3. When video 2 plays, its detections are compared against video 1 start time")
    print("4. This causes incorrect latency calculations → 10000ms timeouts")

    print("\n\nWhere the bug occurs:")
    print("File: backend/services/detection_event_processor.py")
    print("Issue: When storing detection_event, video_start_time is pulled from session")
    print("       It should be: session_start + sum(durations of previous videos)")

    print("\n\nRECOMMENDED FIX:")
    print("=" * 80)
    print("\nUpdate detection_event_processor.py:")
    print("```python")
    print("# Calculate correct video start time based on sequence position")
    print("video_sequence = json.loads(session.video_sequences)")
    print("current_video_index = video_sequence.index(video_id)")
    print("video_start_time = session.started_at")
    print("for i in range(current_video_index):")
    print("    prev_video = Video.query.get(video_sequence[i])")
    print("    video_start_time += prev_video.duration")
    print("```")

    print("\n\nAlternatively:")
    print("Store video transition events in separate table and query by timestamp")

    conn.close()

if __name__ == '__main__':
    analyze_session()
