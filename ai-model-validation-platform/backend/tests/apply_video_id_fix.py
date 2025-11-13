#!/usr/bin/env python3
"""
Apply Video ID Fix for Session 0846e476
Assigns video_id based on video_relative_timestamp
"""

import sqlite3
from datetime import datetime

SESSION_ID = '0846e476-2e21-499c-bfc8-0b2218081c77'
VIDEO_1_ID = '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5'
VIDEO_2_ID = '550e3cf8-2755-42df-8c3c-041300735f93'
VIDEO_SPLIT_TIME = 5.0  # seconds

def main():
    conn = sqlite3.connect('dev_database.db')
    cursor = conn.cursor()

    print("="*80)
    print("VIDEO ID ASSIGNMENT FIX")
    print(f"Session: {SESSION_ID}")
    print(f"Date: {datetime.now().isoformat()}")
    print("="*80)

    # Check current state
    print("\n1. CURRENT STATE:")
    cursor.execute("""
        SELECT
            CASE WHEN video_id IS NULL THEN 'NULL' ELSE video_id END as vid,
            COUNT(*) as count
        FROM detection_events
        WHERE test_session_id = ?
        GROUP BY video_id
        ORDER BY vid
    """, (SESSION_ID,))

    for row in cursor.fetchall():
        print(f"   Video {row[0]}: {row[1]} detections")

    # Get NULL count
    cursor.execute("""
        SELECT COUNT(*) FROM detection_events
        WHERE test_session_id = ? AND video_id IS NULL
    """, (SESSION_ID,))
    null_count = cursor.fetchone()[0]

    if null_count == 0:
        print("\n✓ No NULL video_ids found - already fixed!")
        conn.close()
        return

    print(f"\n   → {null_count} detections need video_id assignment")

    # Create backup
    print("\n2. CREATING BACKUP:")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detection_events_backup_20251104 AS
        SELECT * FROM detection_events
        WHERE test_session_id = ?
    """, (SESSION_ID,))

    cursor.execute("SELECT COUNT(*) FROM detection_events_backup_20251104")
    backup_count = cursor.fetchone()[0]
    print(f"   ✓ Backed up {backup_count} detections")

    # Apply fix for Video 1
    print("\n3. ASSIGNING VIDEO IDS:")
    print(f"   Assigning Video 1 (0 - {VIDEO_SPLIT_TIME}s)...")
    cursor.execute("""
        UPDATE detection_events
        SET video_id = ?
        WHERE test_session_id = ?
          AND video_id IS NULL
          AND video_relative_timestamp < ?
    """, (VIDEO_1_ID, SESSION_ID, VIDEO_SPLIT_TIME))

    video1_count = cursor.rowcount
    print(f"   ✓ Assigned {video1_count} detections to Video 1")

    # Apply fix for Video 2
    print(f"   Assigning Video 2 ({VIDEO_SPLIT_TIME}s - 10s)...")
    cursor.execute("""
        UPDATE detection_events
        SET video_id = ?
        WHERE test_session_id = ?
          AND video_id IS NULL
          AND video_relative_timestamp >= ?
    """, (VIDEO_2_ID, SESSION_ID, VIDEO_SPLIT_TIME))

    video2_count = cursor.rowcount
    print(f"   ✓ Assigned {video2_count} detections to Video 2")

    # Commit changes
    conn.commit()

    # Verify results
    print("\n4. VERIFICATION:")
    cursor.execute("""
        SELECT
            video_id,
            COUNT(*) as count,
            MIN(video_relative_timestamp) as min_ts,
            MAX(video_relative_timestamp) as max_ts,
            ROUND(AVG(video_relative_timestamp), 3) as avg_ts
        FROM detection_events
        WHERE test_session_id = ?
        GROUP BY video_id
        ORDER BY video_id
    """, (SESSION_ID,))

    print("\n   Detection Distribution:")
    print("   " + "-"*76)
    print(f"   {'Video ID':<42} {'Count':<8} {'Timestamp Range':<20}")
    print("   " + "-"*76)

    for row in cursor.fetchall():
        vid_short = row[0][-12:] if row[0] else 'NULL'
        print(f"   ...{vid_short:<39} {row[1]:<8} {row[2]:.3f}s - {row[3]:.3f}s")

    # Check for remaining NULLs
    cursor.execute("""
        SELECT COUNT(*) FROM detection_events
        WHERE test_session_id = ? AND video_id IS NULL
    """, (SESSION_ID,))
    remaining_null = cursor.fetchone()[0]

    print("\n5. FINAL STATUS:")
    if remaining_null == 0:
        print("   ✓ SUCCESS: All detections have video_id assigned!")
        print(f"   ✓ Video 1: {video1_count} detections")
        print(f"   ✓ Video 2: {video2_count} detections")
        print(f"   ✓ Total: {video1_count + video2_count} detections")
    else:
        print(f"   ⚠ WARNING: {remaining_null} detections still have NULL video_id")

    conn.close()

    print("\n" + "="*80)
    print("FIX COMPLETED")
    print("="*80)
    print("\nNext steps:")
    print("1. Test API: curl http://localhost:8000/api/test-sessions/0846e476.../events")
    print("2. Verify frontend: http://localhost:3000/results/0846e476...")
    print("3. Check per-video filtering works")
    print("\nBackup table: detection_events_backup_20251104")
    print("="*80)

if __name__ == "__main__":
    main()
