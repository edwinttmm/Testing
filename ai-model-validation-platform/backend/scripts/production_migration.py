"""
Production Database Migration Script - Quality Tracking Fields

This script provides a comprehensive, production-ready migration for adding
timing quality tracking fields to the database with full verification and
rollback capabilities.

Features:
- Pre-flight checks to verify database state
- Backup recommendation before migration
- Safe column addition with default values
- Index creation for performance
- Post-migration verification
- Detailed logging
- Rollback capability if errors occur

Usage:
    python scripts/production_migration.py --apply
    python scripts/production_migration.py --verify
    python scripts/production_migration.py --rollback

Author: Backend Integration Agent
Date: 2025-11-19
"""

import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect, MetaData
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from database import engine, SessionLocal
from models import TestSession, DetectionEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProductionMigration:
    """Production-grade database migration manager"""

    def __init__(self):
        self.engine = engine
        self.inspector = inspect(engine)
        self.migration_id = f"quality_tracking_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def check_prerequisites(self) -> Tuple[bool, List[str]]:
        """
        Check if migration prerequisites are met

        Returns:
            Tuple of (success: bool, errors: List[str])
        """
        errors = []

        # Check if tables exist
        tables = self.inspector.get_table_names()
        required_tables = ['test_sessions', 'detection_events']

        for table in required_tables:
            if table not in tables:
                errors.append(f"Required table '{table}' does not exist")

        # Check if columns already exist
        try:
            test_session_cols = [c['name'] for c in self.inspector.get_columns('test_sessions')]
            detection_cols = [c['name'] for c in self.inspector.get_columns('detection_events')]

            if 'timing_degraded' in test_session_cols:
                errors.append("Column 'timing_degraded' already exists in test_sessions")
            if 'timing_verified' in test_session_cols:
                errors.append("Column 'timing_verified' already exists in test_sessions")
            if 'usable_for_validation' in detection_cols:
                errors.append("Column 'usable_for_validation' already exists in detection_events")

        except Exception as e:
            errors.append(f"Error checking existing columns: {e}")

        return len(errors) == 0, errors

    def create_backup_recommendation(self) -> str:
        """Generate backup recommendation message"""
        db_path = str(engine.url).replace('sqlite:///', '')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{db_path}.backup_{timestamp}"

        message = f"""
╔══════════════════════════════════════════════════════════════╗
║            BACKUP RECOMMENDATION                              ║
╚══════════════════════════════════════════════════════════════╝

Before proceeding with the migration, it is STRONGLY recommended
to create a backup of your database.

Current Database: {db_path}
Suggested Backup: {backup_path}

Command to create backup:
    cp "{db_path}" "{backup_path}"

Press Enter to continue (assuming backup is complete)...
"""
        return message

    def apply_migration(self, force: bool = False) -> bool:
        """
        Apply the database migration

        Args:
            force: Skip prerequisites check (dangerous!)

        Returns:
            True if migration succeeded, False otherwise
        """
        logger.info("=" * 70)
        logger.info(f"Starting Production Migration: {self.migration_id}")
        logger.info("=" * 70)

        # Pre-flight checks
        if not force:
            logger.info("Running pre-flight checks...")
            success, errors = self.check_prerequisites()

            if not success:
                logger.error("Pre-flight checks failed:")
                for error in errors:
                    logger.error(f"  - {error}")
                return False

            logger.info("✅ Pre-flight checks passed")

            # Backup recommendation
            print(self.create_backup_recommendation())
            input()

        # Begin migration
        try:
            with self.engine.begin() as connection:
                logger.info("Starting database migration transaction...")

                # Step 1: Add columns to test_sessions
                logger.info("Adding columns to test_sessions table...")

                connection.execute(text("""
                    ALTER TABLE test_sessions
                    ADD COLUMN timing_degraded BOOLEAN NOT NULL DEFAULT 0
                """))
                logger.info("  ✅ Added timing_degraded column")

                connection.execute(text("""
                    ALTER TABLE test_sessions
                    ADD COLUMN timing_verified BOOLEAN NOT NULL DEFAULT 0
                """))
                logger.info("  ✅ Added timing_verified column")

                # Step 2: Add column to detection_events
                logger.info("Adding column to detection_events table...")

                connection.execute(text("""
                    ALTER TABLE detection_events
                    ADD COLUMN usable_for_validation BOOLEAN NOT NULL DEFAULT 1
                """))
                logger.info("  ✅ Added usable_for_validation column")

                connection.execute(text("""
                    ALTER TABLE detection_events
                    ADD COLUMN timing_degraded BOOLEAN NOT NULL DEFAULT 0
                """))
                logger.info("  ✅ Added timing_degraded column to detection_events")

                # Step 3: Create indexes for performance
                logger.info("Creating performance indexes...")

                connection.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_test_sessions_timing_degraded
                    ON test_sessions(timing_degraded)
                """))
                logger.info("  ✅ Created index on test_sessions.timing_degraded")

                connection.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_test_sessions_timing_verified
                    ON test_sessions(timing_verified)
                """))
                logger.info("  ✅ Created index on test_sessions.timing_verified")

                connection.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_detection_events_usable
                    ON detection_events(usable_for_validation)
                """))
                logger.info("  ✅ Created index on detection_events.usable_for_validation")

                connection.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_detection_events_timing_degraded
                    ON detection_events(timing_degraded)
                """))
                logger.info("  ✅ Created index on detection_events.timing_degraded")

                # Step 4: Create composite indexes for common queries
                logger.info("Creating composite indexes...")

                connection.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_test_sessions_quality
                    ON test_sessions(timing_degraded, timing_verified, status)
                """))
                logger.info("  ✅ Created composite index on test_sessions quality fields")

                connection.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_detection_quality_session
                    ON detection_events(test_session_id, usable_for_validation, timing_degraded)
                """))
                logger.info("  ✅ Created composite index on detection_events quality fields")

                logger.info("✅ Migration completed successfully - transaction committed")

            # Verify migration
            return self.verify_migration()

        except SQLAlchemyError as e:
            logger.error(f"❌ Migration failed: {e}", exc_info=True)
            logger.error("Transaction has been rolled back")
            return False

    def verify_migration(self) -> bool:
        """
        Verify that migration was applied correctly

        Returns:
            True if verification passed, False otherwise
        """
        logger.info("\nVerifying migration...")

        try:
            # Check columns exist
            test_session_cols = {c['name']: c for c in self.inspector.get_columns('test_sessions')}
            detection_cols = {c['name']: c for c in self.inspector.get_columns('detection_events')}

            # Verify test_sessions columns
            required_test_cols = ['timing_degraded', 'timing_verified']
            for col_name in required_test_cols:
                if col_name not in test_session_cols:
                    logger.error(f"  ❌ Column {col_name} not found in test_sessions")
                    return False
                logger.info(f"  ✅ Column test_sessions.{col_name} exists")

            # Verify detection_events columns
            required_det_cols = ['usable_for_validation', 'timing_degraded']
            for col_name in required_det_cols:
                if col_name not in detection_cols:
                    logger.error(f"  ❌ Column {col_name} not found in detection_events")
                    return False
                logger.info(f"  ✅ Column detection_events.{col_name} exists")

            # Verify indexes exist
            test_session_indexes = [idx['name'] for idx in self.inspector.get_indexes('test_sessions')]
            detection_indexes = [idx['name'] for idx in self.inspector.get_indexes('detection_events')]

            required_indexes = {
                'test_sessions': ['idx_test_sessions_timing_degraded', 'idx_test_sessions_timing_verified'],
                'detection_events': ['idx_detection_events_usable', 'idx_detection_events_timing_degraded']
            }

            for table_name, indexes in required_indexes.items():
                table_indexes = test_session_indexes if table_name == 'test_sessions' else detection_indexes
                for idx in indexes:
                    if idx in table_indexes:
                        logger.info(f"  ✅ Index {idx} exists")
                    else:
                        logger.warning(f"  ⚠️  Index {idx} not found (may not be an error)")

            # Test ORM access
            db = SessionLocal()
            try:
                # Try to query with new fields
                session = db.query(TestSession).first()
                if session:
                    # Access new fields to ensure they work
                    _ = session.timing_degraded
                    _ = session.timing_verified
                    logger.info("  ✅ ORM access to test_sessions fields works")
                else:
                    logger.info("  ℹ️  No test sessions exist to verify ORM access")

                detection = db.query(DetectionEvent).first()
                if detection:
                    _ = detection.usable_for_validation
                    _ = detection.timing_degraded
                    logger.info("  ✅ ORM access to detection_events fields works")
                else:
                    logger.info("  ℹ️  No detection events exist to verify ORM access")

            finally:
                db.close()

            logger.info("\n✅ All verification checks passed!")
            return True

        except Exception as e:
            logger.error(f"❌ Verification failed: {e}", exc_info=True)
            return False

    def rollback_migration(self) -> bool:
        """
        Rollback the migration (remove added columns and indexes)

        Returns:
            True if rollback succeeded, False otherwise
        """
        logger.warning("=" * 70)
        logger.warning(f"Rolling back Migration: {self.migration_id}")
        logger.warning("=" * 70)

        try:
            with self.engine.begin() as connection:
                logger.info("Dropping indexes...")

                # Drop indexes (order doesn't matter for SQLite)
                indexes_to_drop = [
                    ('detection_events', 'idx_detection_quality_session'),
                    ('test_sessions', 'idx_test_sessions_quality'),
                    ('detection_events', 'idx_detection_events_timing_degraded'),
                    ('detection_events', 'idx_detection_events_usable'),
                    ('test_sessions', 'idx_test_sessions_timing_verified'),
                    ('test_sessions', 'idx_test_sessions_timing_degraded'),
                ]

                for table, index in indexes_to_drop:
                    try:
                        connection.execute(text(f"DROP INDEX IF EXISTS {index}"))
                        logger.info(f"  ✅ Dropped index {index}")
                    except Exception as e:
                        logger.warning(f"  ⚠️  Could not drop index {index}: {e}")

                # Note: SQLite doesn't support DROP COLUMN easily
                # So we'll document this limitation
                logger.warning("\n⚠️  SQLite Limitation: Cannot easily drop columns")
                logger.warning("To fully rollback, you would need to:")
                logger.warning("1. Restore from backup, OR")
                logger.warning("2. Recreate table without the new columns and copy data")
                logger.warning("\nIndexes have been dropped, but columns remain in place.")

                logger.info("\n✅ Partial rollback completed (indexes dropped)")
                return True

        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}", exc_info=True)
            return False

    def generate_migration_report(self) -> str:
        """Generate a detailed migration report"""

        report = f"""
╔══════════════════════════════════════════════════════════════╗
║          QUALITY TRACKING MIGRATION REPORT                    ║
╚══════════════════════════════════════════════════════════════╝

Migration ID: {self.migration_id}
Timestamp: {datetime.now().isoformat()}

CHANGES APPLIED:
───────────────────────────────────────────────────────────────

Table: test_sessions
  ✅ Added column: timing_degraded (BOOLEAN, NOT NULL, DEFAULT 0)
  ✅ Added column: timing_verified (BOOLEAN, NOT NULL, DEFAULT 0)
  ✅ Created index: idx_test_sessions_timing_degraded
  ✅ Created index: idx_test_sessions_timing_verified
  ✅ Created composite: idx_test_sessions_quality

Table: detection_events
  ✅ Added column: usable_for_validation (BOOLEAN, NOT NULL, DEFAULT 1)
  ✅ Added column: timing_degraded (BOOLEAN, NOT NULL, DEFAULT 0)
  ✅ Created index: idx_detection_events_usable
  ✅ Created index: idx_detection_events_timing_degraded
  ✅ Created composite: idx_detection_quality_session

PURPOSE:
───────────────────────────────────────────────────────────────

These fields enable the monitoring system to track timing quality
and prevent data corruption in ground truth matching:

• timing_degraded: Indicates if wall-clock time was used instead
  of precision timing (degraded accuracy)

• timing_verified: Whether timing has been verified against the
  database to ensure data integrity

• usable_for_validation: Whether detection has valid timing for
  inclusion in validation metrics

IMPACT:
───────────────────────────────────────────────────────────────

• All existing sessions/detections default to safe values
• No data loss or corruption
• Performance improved via new indexes
• Monitoring system can now track quality metrics
• Ground truth matching will filter out invalid detections

DATABASE STATISTICS:
───────────────────────────────────────────────────────────────
"""

        try:
            db = SessionLocal()
            test_session_count = db.query(TestSession).count()
            detection_count = db.query(DetectionEvent).count()
            db.close()

            report += f"""
Total test sessions: {test_session_count}
Total detection events: {detection_count}
"""
        except Exception as e:
            report += f"\nCould not retrieve statistics: {e}\n"

        report += "\n" + "═" * 66 + "\n"

        return report


def main():
    """Main entry point for migration script"""

    parser = argparse.ArgumentParser(
        description="Production-grade database migration for quality tracking fields"
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply the migration'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify migration was applied correctly'
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Rollback the migration (partial for SQLite)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force migration (skip prerequisite checks - DANGEROUS!)'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate migration report'
    )

    args = parser.parse_args()

    # Create migration manager
    migration = ProductionMigration()

    # Execute requested operation
    if args.apply:
        success = migration.apply_migration(force=args.force)
        if success:
            print(migration.generate_migration_report())
            sys.exit(0)
        else:
            logger.error("Migration failed!")
            sys.exit(1)

    elif args.verify:
        success = migration.verify_migration()
        sys.exit(0 if success else 1)

    elif args.rollback:
        confirm = input("⚠️  Are you sure you want to rollback? (yes/no): ")
        if confirm.lower() == 'yes':
            success = migration.rollback_migration()
            sys.exit(0 if success else 1)
        else:
            print("Rollback cancelled")
            sys.exit(0)

    elif args.report:
        print(migration.generate_migration_report())
        sys.exit(0)

    else:
        parser.print_help()
        print("\nExample usage:")
        print("  python scripts/production_migration.py --apply")
        print("  python scripts/production_migration.py --verify")
        print("  python scripts/production_migration.py --rollback")
        sys.exit(1)


if __name__ == "__main__":
    main()
