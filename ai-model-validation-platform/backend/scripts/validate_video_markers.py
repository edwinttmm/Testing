#!/usr/bin/env python3
"""
Video Markers Validation Script

This script validates the integrity of video_markers table data after migration.
It checks for common data quality issues and provides detailed diagnostics.

Usage:
    python scripts/validate_video_markers.py

Environment:
    Requires DATABASE_URL environment variable or .env file
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_database_url():
    """Get database URL from environment"""
    load_dotenv()
    return (
        os.getenv("VRU_DATABASE_URL") or
        os.getenv("DATABASE_URL") or
        os.getenv("AIVALIDATION_DATABASE_URL")
    )


def validate_table_exists(engine):
    """Check if video_markers table exists"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if 'video_markers' not in tables:
        logger.error("❌ video_markers table does not exist")
        return False

    logger.info("✅ video_markers table exists")
    return True


def validate_indexes(engine):
    """Check if all required indexes exist"""
    inspector = inspect(engine)
    indexes = inspector.get_indexes('video_markers')

    required_indexes = [
        'idx_video_markers_session',
        'idx_video_markers_session_video',
        'idx_video_markers_session_index',
        'idx_video_markers_type',
        'idx_video_markers_timestamp',
        'idx_video_markers_session_timestamp',
        'idx_video_markers_quality',
        'idx_video_markers_unique'
    ]

    existing_index_names = [idx['name'] for idx in indexes]

    missing_indexes = []
    for required_idx in required_indexes:
        if required_idx not in existing_index_names:
            missing_indexes.append(required_idx)

    if missing_indexes:
        logger.warning(f"⚠️  Missing indexes: {', '.join(missing_indexes)}")
        return False

    logger.info(f"✅ All {len(required_indexes)} required indexes exist")
    return True


def validate_constraints(engine):
    """Check if constraints are properly configured"""
    with engine.connect() as conn:
        # Check marker_type constraint
        result = conn.execute(text("""
            SELECT conname, contype, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'video_markers'::regclass
        """))

        constraints = list(result)

        constraint_types = {c[1] for c in constraints}

        if 'f' not in constraint_types:
            logger.warning("⚠️  Missing foreign key constraints")
            return False

        if 'c' not in constraint_types:
            logger.warning("⚠️  Missing check constraints")
            return False

        logger.info(f"✅ Constraints configured correctly ({len(constraints)} total)")
        return True


def validate_trigger(engine):
    """Check if trigger function exists"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT proname
            FROM pg_proc
            WHERE proname = 'check_video_marker_order'
        """))

        if not result.fetchone():
            logger.warning("⚠️  Trigger function check_video_marker_order not found")
            return False

        # Check trigger exists
        result = conn.execute(text("""
            SELECT tgname
            FROM pg_trigger
            WHERE tgname = 'validate_marker_order'
              AND tgrelid = 'video_markers'::regclass
        """))

        if not result.fetchone():
            logger.warning("⚠️  Trigger validate_marker_order not found")
            return False

        logger.info("✅ Trigger function and trigger configured correctly")
        return True


def validate_data_integrity(engine):
    """Validate data integrity of video_markers"""
    with engine.connect() as conn:
        # Check 1: Orphaned markers (invalid test_session_id)
        result = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM video_markers vm
            LEFT JOIN test_sessions ts ON vm.test_session_id = ts.id
            WHERE ts.id IS NULL
        """))
        orphaned_count = result.fetchone()[0]

        if orphaned_count > 0:
            logger.error(f"❌ Found {orphaned_count} orphaned markers (invalid test_session_id)")
            return False
        else:
            logger.info("✅ No orphaned markers")

        # Check 2: Invalid marker order (VIDEO_END before VIDEO_START)
        result = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM (
                SELECT
                    test_session_id,
                    video_index,
                    MAX(CASE WHEN marker_type = 'VIDEO_START' THEN timestamp END) as start_time,
                    MAX(CASE WHEN marker_type = 'VIDEO_END' THEN timestamp END) as end_time
                FROM video_markers
                GROUP BY test_session_id, video_index
            ) bounds
            WHERE end_time IS NOT NULL AND start_time IS NOT NULL AND end_time < start_time
        """))
        invalid_order_count = result.fetchone()[0]

        if invalid_order_count > 0:
            logger.error(f"❌ Found {invalid_order_count} videos with VIDEO_END before VIDEO_START")
            return False
        else:
            logger.info("✅ All markers have valid timestamp order")

        # Check 3: Duplicate markers (should be prevented by unique index)
        result = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM (
                SELECT
                    test_session_id,
                    video_id,
                    video_index,
                    marker_type,
                    COUNT(*) as marker_count
                FROM video_markers
                GROUP BY test_session_id, video_id, video_index, marker_type
                HAVING COUNT(*) > 1
            ) duplicates
        """))
        duplicate_count = result.fetchone()[0]

        if duplicate_count > 0:
            logger.warning(f"⚠️  Found {duplicate_count} duplicate markers")
            return False
        else:
            logger.info("✅ No duplicate markers")

        # Check 4: Videos with only START marker (incomplete sessions)
        result = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM (
                SELECT
                    test_session_id,
                    video_index,
                    COUNT(CASE WHEN marker_type = 'VIDEO_START' THEN 1 END) as start_count,
                    COUNT(CASE WHEN marker_type = 'VIDEO_END' THEN 1 END) as end_count
                FROM video_markers
                GROUP BY test_session_id, video_index
            ) counts
            WHERE start_count > 0 AND end_count = 0
        """))
        incomplete_count = result.fetchone()[0]

        if incomplete_count > 0:
            logger.warning(f"⚠️  Found {incomplete_count} videos with only VIDEO_START (incomplete sessions)")
        else:
            logger.info("✅ All videos have both START and END markers")

        return True


def validate_query_performance(engine):
    """Test query performance with EXPLAIN ANALYZE"""
    with engine.connect() as conn:
        # Get a sample session_id
        result = conn.execute(text("""
            SELECT test_session_id
            FROM video_markers
            LIMIT 1
        """))
        row = result.fetchone()

        if not row:
            logger.warning("⚠️  No markers found, skipping performance test")
            return True

        session_id = row[0]

        # Test query performance
        result = conn.execute(text("""
            EXPLAIN ANALYZE
            SELECT *
            FROM video_markers
            WHERE test_session_id = :session_id
            ORDER BY video_index, marker_type
        """), {"session_id": session_id})

        explain_output = [row[0] for row in result]

        # Check if query uses index
        uses_index = any('Index Scan' in line for line in explain_output)

        if not uses_index:
            logger.warning("⚠️  Query does not use index scan")
            logger.info("Query plan:\n" + "\n".join(explain_output))
            return False

        # Extract execution time
        execution_time = None
        for line in explain_output:
            if 'Execution Time:' in line:
                execution_time = float(line.split(':')[1].strip().split(' ')[0])
                break

        if execution_time:
            if execution_time > 50:  # 50ms threshold
                logger.warning(f"⚠️  Query execution time {execution_time:.2f}ms exceeds 50ms threshold")
            else:
                logger.info(f"✅ Query performance: {execution_time:.2f}ms (using index scan)")

        return True


def print_statistics(engine):
    """Print statistics about video_markers table"""
    with engine.connect() as conn:
        # Total markers
        result = conn.execute(text("SELECT COUNT(*) FROM video_markers"))
        total_markers = result.fetchone()[0]

        # Markers by type
        result = conn.execute(text("""
            SELECT marker_type, COUNT(*) as count
            FROM video_markers
            GROUP BY marker_type
            ORDER BY marker_type
        """))
        markers_by_type = list(result)

        # Markers by quality
        result = conn.execute(text("""
            SELECT timing_quality, COUNT(*) as count
            FROM video_markers
            GROUP BY timing_quality
            ORDER BY
                CASE timing_quality
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                    ELSE 4
                END
        """))
        markers_by_quality = list(result)

        # Average presentation delay
        result = conn.execute(text("""
            SELECT
                AVG(presentation_delay_ms) as avg_delay,
                MIN(presentation_delay_ms) as min_delay,
                MAX(presentation_delay_ms) as max_delay
            FROM video_markers
            WHERE presentation_delay_ms IS NOT NULL
        """))
        delay_stats = result.fetchone()

        # Table size
        result = conn.execute(text("""
            SELECT pg_size_pretty(pg_total_relation_size('video_markers'))
        """))
        table_size = result.fetchone()[0]

        print("\n" + "="*60)
        print("VIDEO MARKERS STATISTICS")
        print("="*60)
        print(f"\nTotal markers: {total_markers:,}")
        print(f"Table size: {table_size}")

        print("\nMarkers by type:")
        for marker_type, count in markers_by_type:
            print(f"  {marker_type}: {count:,}")

        print("\nMarkers by quality:")
        for quality, count in markers_by_quality:
            print(f"  {quality}: {count:,}")

        if delay_stats[0] is not None:
            print("\nPresentation delay statistics:")
            print(f"  Average: {delay_stats[0]:.2f}ms")
            print(f"  Min: {delay_stats[1]:.2f}ms")
            print(f"  Max: {delay_stats[2]:.2f}ms")

        print("="*60 + "\n")


def main():
    """Main validation function"""
    logger.info("Starting video_markers validation...")

    # Get database connection
    database_url = get_database_url()
    if not database_url:
        logger.error("❌ DATABASE_URL not configured")
        sys.exit(1)

    engine = create_engine(database_url)

    # Run validation checks
    checks = [
        ("Table existence", lambda: validate_table_exists(engine)),
        ("Indexes", lambda: validate_indexes(engine)),
        ("Constraints", lambda: validate_constraints(engine)),
        ("Trigger function", lambda: validate_trigger(engine)),
        ("Data integrity", lambda: validate_data_integrity(engine)),
        ("Query performance", lambda: validate_query_performance(engine)),
    ]

    results = []
    for check_name, check_func in checks:
        logger.info(f"\nRunning check: {check_name}")
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            logger.error(f"❌ Check failed with exception: {e}")
            results.append((check_name, False))

    # Print statistics
    print_statistics(engine)

    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")

    print(f"\nTotal: {passed}/{total} checks passed")
    print("="*60 + "\n")

    if passed == total:
        logger.info("🎉 All validation checks passed!")
        return 0
    else:
        logger.error(f"⚠️  {total - passed} validation check(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
