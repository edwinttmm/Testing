#!/usr/bin/env python3
"""
Database Schema Verification Script

Comprehensive verification of database schema for quality tracking columns,
indexes, and data integrity.

Usage:
  cd /home/rigade/Testing/ai-model-validation-platform/backend
  python3 scripts/verify_schema.py
"""
import sys
import os
import logging
from datetime import datetime
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text
from database import SessionLocal, engine
from models import TestSession, DetectionEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchemaVerifier:
    """Verify database schema and data integrity"""

    def __init__(self):
        self.db = SessionLocal()
        self.inspector = inspect(engine)
        self.errors = []
        self.warnings = []
        self.passed = []

    def run_all_checks(self) -> Dict[str, Any]:
        """Run all verification checks"""

        logger.info("=" * 80)
        logger.info("DATABASE SCHEMA VERIFICATION")
        logger.info("=" * 80)
        logger.info("")

        results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {
                'columns': self.verify_columns(),
                'indexes': self.verify_indexes(),
                'data_integrity': self.verify_data_integrity(),
                'quality_system': self.verify_quality_system(),
            },
            'errors': self.errors,
            'warnings': self.warnings,
            'passed': self.passed
        }

        self.print_summary(results)
        return results

    def verify_columns(self) -> Dict[str, Any]:
        """Verify all required columns exist"""

        logger.info("CHECKING REQUIRED COLUMNS")
        logger.info("-" * 80)

        checks = []

        # Check test_sessions table
        ts_columns = {c['name'] for c in self.inspector.get_columns('test_sessions')}

        required_ts = [
            ('timing_degraded', 'BOOLEAN'),
            ('timing_verified', 'BOOLEAN'),
        ]

        for col_name, col_type in required_ts:
            if col_name in ts_columns:
                self.passed.append(f"test_sessions.{col_name} exists")
                checks.append({'table': 'test_sessions', 'column': col_name, 'status': 'OK'})
                logger.info(f"✅ test_sessions.{col_name} exists")
            else:
                self.errors.append(f"Missing column: test_sessions.{col_name}")
                checks.append({'table': 'test_sessions', 'column': col_name, 'status': 'MISSING'})
                logger.error(f"❌ test_sessions.{col_name} MISSING")

        # Check detection_events table
        de_columns = {c['name'] for c in self.inspector.get_columns('detection_events')}

        required_de = [
            ('usable_for_validation', 'BOOLEAN'),
            ('timing_degraded', 'BOOLEAN'),
        ]

        for col_name, col_type in required_de:
            if col_name in de_columns:
                self.passed.append(f"detection_events.{col_name} exists")
                checks.append({'table': 'detection_events', 'column': col_name, 'status': 'OK'})
                logger.info(f"✅ detection_events.{col_name} exists")
            else:
                self.errors.append(f"Missing column: detection_events.{col_name}")
                checks.append({'table': 'detection_events', 'column': col_name, 'status': 'MISSING'})
                logger.error(f"❌ detection_events.{col_name} MISSING")

        logger.info("")
        return {'checks': checks, 'passed': len([c for c in checks if c['status'] == 'OK'])}

    def verify_indexes(self) -> Dict[str, Any]:
        """Verify all required indexes exist"""

        logger.info("CHECKING REQUIRED INDEXES")
        logger.info("-" * 80)

        checks = []

        # Check test_sessions indexes
        ts_indexes = {idx['name'] for idx in self.inspector.get_indexes('test_sessions')}

        required_ts_indexes = [
            'idx_test_sessions_timing_degraded',
            'idx_test_sessions_timing_verified',
        ]

        for idx_name in required_ts_indexes:
            if idx_name in ts_indexes:
                self.passed.append(f"Index {idx_name} exists")
                checks.append({'index': idx_name, 'status': 'OK'})
                logger.info(f"✅ {idx_name} exists")
            else:
                self.warnings.append(f"Missing index: {idx_name}")
                checks.append({'index': idx_name, 'status': 'MISSING'})
                logger.warning(f"⚠️  {idx_name} MISSING (performance impact)")

        # Check detection_events indexes
        de_indexes = {idx['name'] for idx in self.inspector.get_indexes('detection_events')}

        required_de_indexes = [
            'idx_detection_events_usable',
            'idx_detection_events_timing_degraded',
        ]

        for idx_name in required_de_indexes:
            if idx_name in de_indexes:
                self.passed.append(f"Index {idx_name} exists")
                checks.append({'index': idx_name, 'status': 'OK'})
                logger.info(f"✅ {idx_name} exists")
            else:
                self.warnings.append(f"Missing index: {idx_name}")
                checks.append({'index': idx_name, 'status': 'MISSING'})
                logger.warning(f"⚠️  {idx_name} MISSING (performance impact)")

        logger.info("")
        return {'checks': checks, 'passed': len([c for c in checks if c['status'] == 'OK'])}

    def verify_data_integrity(self) -> Dict[str, Any]:
        """Verify data integrity and existing data"""

        logger.info("CHECKING DATA INTEGRITY")
        logger.info("-" * 80)

        # Count existing records
        session_count = self.db.query(TestSession).count()
        detection_count = self.db.query(DetectionEvent).count()

        logger.info(f"Total test sessions: {session_count}")
        logger.info(f"Total detection events: {detection_count}")
        logger.info("")

        # Check for NULL values in new columns
        null_checks = []

        result = self.db.execute(text("""
            SELECT COUNT(*) as count
            FROM test_sessions
            WHERE timing_degraded IS NULL OR timing_verified IS NULL
        """))
        null_ts = result.scalar()

        if null_ts == 0:
            self.passed.append("No NULL values in test_sessions quality columns")
            logger.info(f"✅ No NULL values in test_sessions quality columns")
        else:
            self.errors.append(f"Found {null_ts} NULL values in test_sessions")
            logger.error(f"❌ Found {null_ts} NULL values in test_sessions")

        null_checks.append({'table': 'test_sessions', 'null_count': null_ts})

        result = self.db.execute(text("""
            SELECT COUNT(*) as count
            FROM detection_events
            WHERE usable_for_validation IS NULL OR timing_degraded IS NULL
        """))
        null_de = result.scalar()

        if null_de == 0:
            self.passed.append("No NULL values in detection_events quality columns")
            logger.info(f"✅ No NULL values in detection_events quality columns")
        else:
            self.errors.append(f"Found {null_de} NULL values in detection_events")
            logger.error(f"❌ Found {null_de} NULL values in detection_events")

        null_checks.append({'table': 'detection_events', 'null_count': null_de})

        logger.info("")

        return {
            'session_count': session_count,
            'detection_count': detection_count,
            'null_checks': null_checks
        }

    def verify_quality_system(self) -> Dict[str, Any]:
        """Verify quality warning system functionality"""

        logger.info("CHECKING QUALITY WARNING SYSTEM")
        logger.info("-" * 80)

        try:
            from services.quality_warnings import QualityWarning

            # Get a sample session
            session = self.db.query(TestSession).first()

            if session:
                # Test quality check
                warnings = QualityWarning.check_session_quality(session.id, self.db)
                self.passed.append("Quality warning system functional")
                logger.info(f"✅ Quality check successful: {len(warnings)} warnings generated")

                # Test statistics
                stats = QualityWarning.get_quality_statistics(session.id, self.db)
                logger.info(f"✅ Quality statistics retrieved successfully")
                logger.info(f"   Quality Level: {stats.get('quality_level', 'UNKNOWN')}")

                return {
                    'functional': True,
                    'sample_session': session.id,
                    'warnings_count': len(warnings),
                    'quality_stats': stats
                }
            else:
                self.warnings.append("No sessions available to test quality system")
                logger.warning("⚠️  No sessions available to test")
                return {'functional': True, 'note': 'No test data'}

        except Exception as e:
            self.errors.append(f"Quality system check failed: {e}")
            logger.error(f"❌ Quality system error: {e}")
            return {'functional': False, 'error': str(e)}

    def print_summary(self, results: Dict[str, Any]):
        """Print verification summary"""

        logger.info("")
        logger.info("=" * 80)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 80)
        logger.info("")

        total_passed = len(self.passed)
        total_warnings = len(self.warnings)
        total_errors = len(self.errors)

        logger.info(f"✅ Passed:   {total_passed}")
        logger.info(f"⚠️  Warnings: {total_warnings}")
        logger.info(f"❌ Errors:   {total_errors}")
        logger.info("")

        if total_errors > 0:
            logger.info("ERRORS:")
            for error in self.errors:
                logger.error(f"  ❌ {error}")
            logger.info("")

        if total_warnings > 0:
            logger.info("WARNINGS:")
            for warning in self.warnings:
                logger.warning(f"  ⚠️  {warning}")
            logger.info("")

        if total_errors == 0 and total_warnings == 0:
            logger.info("🎉 ALL CHECKS PASSED! Database schema is complete and functional.")
        elif total_errors == 0:
            logger.info("✅ Schema verification passed with warnings (non-critical).")
        else:
            logger.info("❌ Schema verification FAILED. Please fix errors above.")

        logger.info("=" * 80)

    def close(self):
        """Close database connection"""
        self.db.close()


def main():
    """Main verification entry point"""

    verifier = SchemaVerifier()

    try:
        results = verifier.run_all_checks()

        # Exit with error code if verification failed
        if verifier.errors:
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        logger.error(f"Verification failed with exception: {e}", exc_info=True)
        sys.exit(2)
    finally:
        verifier.close()


if __name__ == "__main__":
    main()
