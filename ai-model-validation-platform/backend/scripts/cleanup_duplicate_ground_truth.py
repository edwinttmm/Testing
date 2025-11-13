#!/usr/bin/env python3
"""
Ground Truth Duplicate Cleanup Script

ISSUE #8 FIX: Removes duplicate ground truth objects caused by enum vs string class_label formats

ROOT CAUSE: Import process created duplicates:
- 'VRUTypeEnum.CYCLIST' vs 'cyclist'
- 'VRUTypeEnum.PEDESTRIAN' vs 'pedestrian'

This script:
1. Identifies duplicates (same video_id, timestamp, bbox, but different class_label format)
2. Keeps the normalized (lowercase string) version
3. Soft-deletes the enum format version
4. Reports cleanup statistics
"""

import sys
import os

# Add parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import SessionLocal
from models import GroundTruthObject
from sqlalchemy import func, and_
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_class_label(label: str) -> str:
    """Normalize class_label to consistent format"""
    if '.' in label:
        # Handle 'VRUTypeEnum.CYCLIST' -> 'cyclist'
        label = label.split('.')[-1]
    return label.lower()


def find_and_cleanup_duplicates(db, dry_run=True):
    """
    Find and cleanup duplicate ground truth objects

    Args:
        db: Database session
        dry_run: If True, only report duplicates without deleting

    Returns:
        dict with cleanup statistics
    """
    stats = {
        'total_objects': 0,
        'duplicate_groups': 0,
        'objects_to_delete': 0,
        'objects_kept': 0
    }

    # Get total count
    stats['total_objects'] = db.query(func.count(GroundTruthObject.id)).filter(
        GroundTruthObject.deleted_at.is_(None)
    ).scalar()

    logger.info(f"Total active ground truth objects: {stats['total_objects']}")

    # Find all ground truth objects grouped by potential duplicates
    # (same video_id, timestamp, bbox coordinates)
    all_objects = db.query(GroundTruthObject).filter(
        GroundTruthObject.deleted_at.is_(None)
    ).order_by(
        GroundTruthObject.video_id,
        GroundTruthObject.timestamp,
        GroundTruthObject.x,
        GroundTruthObject.y
    ).all()

    # Group objects by (video_id, timestamp, bbox)
    groups = {}
    for obj in all_objects:
        key = (
            obj.video_id,
            round(obj.timestamp, 3),  # Round to 3 decimal places for fuzzy matching
            round(obj.x, 2),
            round(obj.y, 2),
            round(obj.width, 2),
            round(obj.height, 2)
        )

        if key not in groups:
            groups[key] = []
        groups[key].append(obj)

    # Find groups with duplicates (different class_label formats)
    duplicate_groups = []
    for key, objects in groups.items():
        if len(objects) > 1:
            # Check if duplicates are due to class_label format differences
            normalized_labels = set(normalize_class_label(obj.class_label) for obj in objects)
            if len(normalized_labels) == 1:
                # These are real duplicates - same normalized class_label
                duplicate_groups.append(objects)
                logger.debug(f"Duplicate group: {key}, objects: {len(objects)}, "
                           f"labels: {[obj.class_label for obj in objects]}")

    stats['duplicate_groups'] = len(duplicate_groups)
    logger.info(f"Found {stats['duplicate_groups']} duplicate groups")

    # ALTERNATE STRATEGY: Since no exact spatial duplicates found,
    # look for objects with enum format that could be duplicates
    # by checking for matching normalized objects
    logger.info("Checking for enum format duplicates...")

    enum_objects = [obj for obj in all_objects if '.' in obj.class_label]
    logger.info(f"Found {len(enum_objects)} objects with enum format class_label")

    objects_to_delete = []
    for enum_obj in enum_objects:
        # Look for matching string format object
        normalized_label = normalize_class_label(enum_obj.class_label)

        # Find potential duplicate with string format
        potential_dup = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == enum_obj.video_id,
            GroundTruthObject.class_label == normalized_label,
            GroundTruthObject.deleted_at.is_(None),
            # Fuzzy match on timestamp (within 0.01s)
            GroundTruthObject.timestamp.between(enum_obj.timestamp - 0.01, enum_obj.timestamp + 0.01),
            # Fuzzy match on bbox (within 1 pixel)
            GroundTruthObject.x.between(enum_obj.x - 1, enum_obj.x + 1),
            GroundTruthObject.y.between(enum_obj.y - 1, enum_obj.y + 1),
            GroundTruthObject.width.between(enum_obj.width - 1, enum_obj.width + 1),
            GroundTruthObject.height.between(enum_obj.height - 1, enum_obj.height + 1)
        ).first()

        if potential_dup:
            # Found a duplicate - delete the enum format version
            objects_to_delete.append(enum_obj)
            stats['objects_kept'] += 1
            logger.info(
                f"Duplicate detected: Video {enum_obj.video_id[:8]}, "
                f"timestamp {enum_obj.timestamp:.3f}s, "
                f"enum '{enum_obj.class_label}' (will keep string '{potential_dup.class_label}')"
            )
        elif not potential_dup:
            # No matching string format - this enum object is unique
            # We should normalize it instead of deleting
            pass

    # Process duplicate groups from exact matches (if any)
    for group in duplicate_groups:
        # Sort by class_label format preference:
        # 1. Prefer lowercase string ('cyclist')
        # 2. Delete enum format ('VRUTypeEnum.CYCLIST')
        group_sorted = sorted(group, key=lambda obj: (
            '.' in obj.class_label,  # Enum format first (True sorts after False)
            obj.created_at  # Keep older record
        ))

        # Keep the first (preferred) object
        keep_obj = group_sorted[0]
        if keep_obj not in [obj for obj in objects_to_delete]:
            stats['objects_kept'] += 1

        # Mark others for deletion
        for obj in group_sorted[1:]:
            if obj not in objects_to_delete:
                objects_to_delete.append(obj)
                logger.info(
                    f"Exact duplicate: Video {obj.video_id[:8]}, "
                    f"timestamp {obj.timestamp:.3f}s, "
                    f"class '{obj.class_label}' (will keep '{keep_obj.class_label}')"
                )

    stats['objects_to_delete'] = len(objects_to_delete)

    # Perform soft delete if not dry run
    if not dry_run and objects_to_delete:
        logger.info(f"Soft-deleting {len(objects_to_delete)} duplicate objects...")
        for obj in objects_to_delete:
            obj.deleted_at = datetime.utcnow()
            obj.deleted_by = "cleanup_script"

        db.commit()
        logger.info("Cleanup completed successfully")
    elif dry_run and objects_to_delete:
        logger.info(f"DRY RUN: Would soft-delete {len(objects_to_delete)} duplicate objects")
    else:
        logger.info("No duplicates found to delete")

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Clean up duplicate ground truth objects')
    parser.add_argument('--execute', action='store_true',
                       help='Execute cleanup (default is dry-run)')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        logger.info("="*60)
        logger.info("Ground Truth Duplicate Cleanup Script")
        logger.info("Issue #8 Fix: Enum vs String class_label duplicates")
        logger.info("="*60)

        mode = "DRY RUN" if not args.execute else "EXECUTION"
        logger.info(f"Mode: {mode}")
        logger.info("")

        stats = find_and_cleanup_duplicates(db, dry_run=not args.execute)

        logger.info("")
        logger.info("="*60)
        logger.info("Cleanup Statistics:")
        logger.info(f"  Total objects before: {stats['total_objects']}")
        logger.info(f"  Duplicate groups found: {stats['duplicate_groups']}")
        logger.info(f"  Objects to delete: {stats['objects_to_delete']}")
        logger.info(f"  Objects kept: {stats['objects_kept']}")
        logger.info(f"  Expected total after cleanup: {stats['total_objects'] - stats['objects_to_delete']}")
        logger.info("="*60)

        if not args.execute and stats['objects_to_delete'] > 0:
            logger.info("")
            logger.info("Run with --execute to perform cleanup:")
            logger.info(f"  python {__file__} --execute")

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 1
    finally:
        db.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
