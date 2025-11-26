#!/usr/bin/env python3
"""
Database schema inspection script for test_sessions table.
This script checks if the evaluation_details column exists.
"""
import sqlite3
import sys
import os

# Database paths to check
db_paths = [
    "/home/rigade/Testing/ai-model-validation-platform/dev_database.db",
    "/home/rigade/Testing/ai-model-validation-platform/test_database.db",
    "/home/rigade/Testing/dev_database.db"
]

def inspect_test_sessions_schema(db_path):
    """Inspect test_sessions table schema"""
    if not os.path.exists(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get table schema
        cursor.execute("PRAGMA table_info(test_sessions)")
        columns = cursor.fetchall()

        conn.close()

        return columns
    except Exception as e:
        print(f"Error inspecting {db_path}: {e}", file=sys.stderr)
        return None

def main():
    print("=" * 80)
    print("DATABASE SCHEMA INSPECTION REPORT")
    print("=" * 80)
    print()

    for db_path in db_paths:
        print(f"Checking: {db_path}")
        if not os.path.exists(db_path):
            print(f"  ❌ File does not exist\n")
            continue

        columns = inspect_test_sessions_schema(db_path)
        if columns is None:
            print(f"  ❌ Could not inspect schema\n")
            continue

        if not columns:
            print(f"  ⚠️  test_sessions table does not exist\n")
            continue

        print(f"  ✅ test_sessions table found with {len(columns)} columns")
        print()
        print("  Column Name                  | Type         | NotNull | Default | PK")
        print("  " + "-" * 76)

        has_evaluation_details = False
        for col in columns:
            cid, name, col_type, not_null, default, pk = col
            print(f"  {name:28} | {col_type:12} | {not_null:7} | {str(default):7} | {pk}")
            if name == "evaluation_details":
                has_evaluation_details = True

        print()
        if has_evaluation_details:
            print("  ✅ evaluation_details column EXISTS")
        else:
            print("  ❌ evaluation_details column MISSING")
        print()

    print("=" * 80)

if __name__ == "__main__":
    main()
