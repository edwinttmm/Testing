#!/usr/bin/env python3
"""
Apply missing quality tracking columns to detection_events table.

This migration adds the following columns:
- quality_category: Overall quality classification
- quality_validation_suitability: Validation suitability assessment
- quality_confidence_score: Quality assessment confidence
- quality_notes: Human-readable quality notes
- timing_clamped: Flag for clamped timing
- original_video_relative: Original unclamped timestamp

Run with: python scripts/apply_quality_columns_migration.py
"""
import sqlite3
import os
import sys

# Find the database
DB_PATHS = [
    'dev_database.db',
    '../dev_database.db',
    'backend/dev_database.db',
    '/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db',
    '/home/rigade/Testing/ai-model-validation-platform/dev_database.db',
]

def find_database():
    for path in DB_PATHS:
        if os.path.exists(path):
            return path
    return None

def get_existing_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}

def apply_migration(db_path):
    print(f"Applying migration to: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        existing_columns = get_existing_columns(cursor, 'detection_events')
        print(f"Existing columns count: {len(existing_columns)}")

        columns_to_add = [
            ('quality_category', 'TEXT'),
            ('quality_validation_suitability', 'TEXT'),
            ('quality_confidence_score', 'REAL'),
            ('quality_notes', 'TEXT'),
            ('timing_clamped', 'INTEGER DEFAULT 0'),
            ('original_video_relative', 'REAL'),
        ]

        added = 0
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE detection_events ADD COLUMN {col_name} {col_type}")
                    print(f"  Added column: {col_name}")
                    added += 1
                except sqlite3.OperationalError as e:
                    if "duplicate column" in str(e).lower():
                        print(f"  Column already exists: {col_name}")
                    else:
                        raise
            else:
                print(f"  Column already exists: {col_name}")

        # Create indexes (safe - IF NOT EXISTS)
        indexes = [
            ('idx_detection_quality_category', 'quality_category'),
            ('idx_detection_quality_suitability', 'quality_validation_suitability'),
            ('idx_detection_timing_clamped', 'timing_clamped'),
        ]

        for idx_name, col_name in indexes:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON detection_events({col_name})")
                print(f"  Created/verified index: {idx_name}")
            except sqlite3.OperationalError as e:
                print(f"  Index error (non-fatal): {e}")

        conn.commit()
        print(f"\n Migration complete! Added {added} new columns.")

        # Verify
        final_columns = get_existing_columns(cursor, 'detection_events')
        quality_cols = [c for c in final_columns if 'quality' in c or 'timing_clamped' in c or 'original_video' in c]
        print(f"Quality-related columns now present: {quality_cols}")

        return True

    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    db_path = find_database()
    if not db_path:
        print("ERROR: Could not find database file!")
        print("Searched paths:", DB_PATHS)
        sys.exit(1)

    success = apply_migration(db_path)
    sys.exit(0 if success else 1)
