#!/usr/bin/env python3
"""Check database schema"""

import sqlite3

DB_PATH = '/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("Available tables:")
for table in tables:
    print(f"  - {table[0]}")

print("\n" + "=" * 80)

# Check video-related tables
for table_name in ['videos', 'test_sessions', 'detection_events']:
    if any(t[0] == table_name for t in tables):
        print(f"\n{table_name} schema:")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]:<30} {col[2]:<15} {'NOT NULL' if col[3] else ''}")

conn.close()
