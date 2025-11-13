#!/usr/bin/env python3
"""
Ground Truth Duplicate Cleanup Script
Removes duplicate enum-prefixed ground truth objects (VRUTypeEnum.PEDESTRIAN vs pedestrian)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from sqlalchemy import text
from datetime import datetime

def main():
    db = SessionLocal()
    try:
        # Count duplicates before cleanup
        result = db.execute(text("""
            SELECT COUNT(*) as duplicate_count
            FROM ground_truth_objects
            WHERE class_label LIKE 'VRUTypeEnum.%'
            AND deleted_at IS NULL
        """))
        duplicate_count = result.scalar()

        print(f"Found {duplicate_count} duplicate ground truth objects with enum prefix")

        if duplicate_count == 0:
            print("No duplicates to clean up!")
            return

        # Execute cleanup
        print(f"Soft-deleting {duplicate_count} duplicate records...")
        db.execute(text("""
            UPDATE ground_truth_objects
            SET deleted_at = :now,
                deleted_by = 'system_cleanup_agent7_514bug'
            WHERE class_label LIKE 'VRUTypeEnum.%'
            AND deleted_at IS NULL
        """), {"now": datetime.utcnow()})

        db.commit()
        print(f"✅ Successfully cleaned up {duplicate_count} duplicate records")

        # Verify cleanup
        result = db.execute(text("""
            SELECT video_id, class_label, COUNT(*) as count
            FROM ground_truth_objects
            WHERE deleted_at IS NULL
            AND video_id IN (
                '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5',
                '550e3cf8-2755-42df-8c3c-041300735f93'
            )
            GROUP BY video_id, class_label
            ORDER BY video_id, class_label
        """))

        print("\n📊 Ground Truth Counts After Cleanup:")
        for row in result:
            print(f"  Video {row[0][:8]}...: {row[1]} = {row[2]} objects")

    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
