#!/usr/bin/env python3
"""Verify database migration and schema"""

import sqlite3
import sys
import json
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def verify_schema():
    """Verify test_sessions table schema"""
    db_path = backend_dir / "dev_database.db"

    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return False

    print(f"✅ Database found at {db_path}\n")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Get table schema
    print("=" * 80)
    print("TEST_SESSIONS TABLE SCHEMA")
    print("=" * 80)
    cursor.execute("PRAGMA table_info(test_sessions)")
    columns = cursor.fetchall()

    expected_columns = [
        'video_count', 'video_sequences', 'current_video_index',
        'video_start_time', 'completed_videos'
    ]

    found_columns = {}
    print(f"\n{'ID':<5} {'Name':<30} {'Type':<15} {'NotNull':<10} {'Default':<15}")
    print("-" * 80)
    for col in columns:
        cid, name, col_type, not_null, default_val, pk = col
        print(f"{cid:<5} {name:<30} {col_type:<15} {not_null:<10} {str(default_val):<15}")
        found_columns[name] = col_type

    # Check for expected columns
    print("\n" + "=" * 80)
    print("MULTI-VIDEO COLUMN VERIFICATION")
    print("=" * 80)

    all_present = True
    for col_name in expected_columns:
        if col_name in found_columns:
            print(f"✅ {col_name:<30} ({found_columns[col_name]})")
        else:
            print(f"❌ {col_name:<30} MISSING")
            all_present = False

    # Check for sample data
    print("\n" + "=" * 80)
    print("SAMPLE DATA CHECK")
    print("=" * 80)

    cursor.execute("""
        SELECT session_id, video_count, current_video_index,
               CASE WHEN video_sequences IS NOT NULL THEN 'YES' ELSE 'NO' END as has_sequences,
               CASE WHEN completed_videos IS NOT NULL THEN 'YES' ELSE 'NO' END as has_completed
        FROM test_sessions
        ORDER BY created_at DESC
        LIMIT 5
    """)

    rows = cursor.fetchall()
    if rows:
        print(f"\n{'Session ID':<40} {'Videos':<10} {'Current':<10} {'Sequences':<12} {'Completed':<12}")
        print("-" * 80)
        for row in rows:
            print(f"{row[0]:<40} {row[1] or 'NULL':<10} {row[2] or 'NULL':<10} {row[3]:<12} {row[4]:<12}")
    else:
        print("No sessions found in database")

    # Check specific session from the test
    print("\n" + "=" * 80)
    print("TEST SESSION DATA (a90187aa-2237-4afe-90d5-3c8176db622f)")
    print("=" * 80)

    cursor.execute("""
        SELECT session_id, video_count, current_video_index,
               video_sequences, completed_videos, video_start_time
        FROM test_sessions
        WHERE session_id = 'a90187aa-2237-4afe-90d5-3c8176db622f'
    """)

    test_row = cursor.fetchone()
    if test_row:
        print(f"\nSession ID: {test_row[0]}")
        print(f"Video Count: {test_row[1]}")
        print(f"Current Video Index: {test_row[2]}")
        print(f"Video Sequences: {test_row[3][:100] + '...' if test_row[3] else 'NULL'}")
        print(f"Completed Videos: {test_row[4][:100] + '...' if test_row[4] else 'NULL'}")
        print(f"Video Start Time: {test_row[5]}")
    else:
        print("❌ Test session not found!")

    conn.close()

    print("\n" + "=" * 80)
    if all_present:
        print("✅ ALL REQUIRED COLUMNS PRESENT")
    else:
        print("❌ SOME COLUMNS MISSING - MIGRATION NEEDED")
    print("=" * 80)

    return all_present

if __name__ == "__main__":
    success = verify_schema()
    sys.exit(0 if success else 1)
