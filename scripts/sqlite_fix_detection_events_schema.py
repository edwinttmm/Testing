#!/usr/bin/env python3
"""
SQLite migration helper: ensure detection_events table has all columns
expected by the HIL Python services (e.g., latency_ns, labjack timestamps, etc.).

Usage:
  python Testing/scripts/sqlite_fix_detection_events_schema.py /path/to/database.sqlite

This script is idempotent: it checks PRAGMA table_info and only adds missing
columns via ALTER TABLE ... ADD COLUMN with safe types/defaults.
"""

import sqlite3
import sys
from typing import Dict, Tuple


# Column name -> (sqlite type, default SQL or None)
COLUMNS: Dict[str, Tuple[str, str]] = {
    # Core identifiers
    "test_session_id": ("TEXT", "NULL"),
    "video_id": ("TEXT", "NULL"),
    # Timestamps (epoch seconds as REAL; *_ns as INTEGER)
    "timestamp": ("REAL", "NULL"),
    "validation_result": ("TEXT", "NULL"),
    "ground_truth_match_id": ("TEXT", "NULL"),
    "latency_ns": ("INTEGER", "NULL"),
    "labjack_timestamp": ("REAL", "NULL"),
    "labjack_timestamp_ns": ("INTEGER", "NULL"),
    "video_start_time": ("REAL", "NULL"),
    "video_start_time_ns": ("INTEGER", "NULL"),
    "timing_accuracy_ns": ("INTEGER", "NULL"),
    "frame_accurate_timestamp": ("REAL", "NULL"),
    # Signal values
    "labjack_voltage": ("REAL", "NULL"),
    "latency_threshold_ms": ("REAL", "NULL"),
    "latency_result": ("TEXT", "NULL"),
    "voltage_level": ("REAL", "NULL"),
    "detection_channel": ("TEXT", "NULL"),
    # Monotonic time and sync
    "monotonic_timestamp_ns": ("INTEGER", "NULL"),
    "sync_point_reference": ("TEXT", "NULL"),
    "drift_compensated": ("INTEGER", "0"),  # boolean as 0/1
    "timing_interpolated": ("INTEGER", "0"), # boolean as 0/1
    # Video-relative timing
    "video_relative_timestamp": ("REAL", "NULL"),
    "video_relative_timestamp_ns": ("INTEGER", "NULL"),
    "actual_latency_ms": ("REAL", "NULL"),
    "video_frame_number": ("INTEGER", "NULL"),
    "timing_sync_quality": ("TEXT", "NULL"),
    # Classification/meta
    "confidence": ("REAL", "NULL"),
    "class_label": ("TEXT", "NULL"),
    "detection_id": ("TEXT", "NULL"),
    "frame_number": ("INTEGER", "NULL"),
    "vru_type": ("TEXT", "NULL"),
    # Bounding box
    "bounding_box_x": ("REAL", "NULL"),
    "bounding_box_y": ("REAL", "NULL"),
    "bounding_box_width": ("REAL", "NULL"),
    "bounding_box_height": ("REAL", "NULL"),
    # Artifacts
    "screenshot_path": ("TEXT", "NULL"),
    "screenshot_zoom_path": ("TEXT", "NULL"),
    # Processing details
    "processing_time_ms": ("REAL", "NULL"),
    "model_version": ("TEXT", "NULL"),
    "source": ("TEXT", "NULL"),
    "detection_type": ("TEXT", "NULL"),
    # Created timestamp (used by RETURNING created_at in inserts)
    "created_at": ("TEXT", "(datetime('now'))"),
}


def get_existing_columns(cur) -> set:
    cur.execute("PRAGMA table_info(detection_events)")
    rows = cur.fetchall()
    return {row[1] for row in rows}  # row[1] = name


def add_column(cur, name: str, col_type: str, default_sql: str):
    if default_sql is None or default_sql.upper() == "NULL":
        ddl = f"ALTER TABLE detection_events ADD COLUMN {name} {col_type}"
    else:
        ddl = f"ALTER TABLE detection_events ADD COLUMN {name} {col_type} DEFAULT {default_sql}"
    cur.execute(ddl)


def main(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        conn.isolation_level = None  # autocommit mode for DDL
        cur = conn.cursor()

        # Ensure table exists
        cur.execute(
            """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='detection_events'
            """
        )
        if cur.fetchone() is None:
            print("ERROR: detection_events table does not exist in this database.")
            return 2

        existing = get_existing_columns(cur)
        missing = [name for name in COLUMNS.keys() if name not in existing]

        if not missing:
            print("✅ detection_events schema already up to date.")
            return 0

        print(f"Adding missing columns: {', '.join(missing)}")
        for name in missing:
            col_type, default_sql = COLUMNS[name]
            add_column(cur, name, col_type, default_sql)
        print("✅ detection_events schema updated successfully.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python Testing/scripts/sqlite_fix_detection_events_schema.py /path/to/database.sqlite")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))

