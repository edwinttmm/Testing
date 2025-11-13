"""
Verification Script for Multi-Video Sequential Testing Schema

This script verifies that all schema components are properly implemented:
- Models are defined correctly
- Relationships are established
- Schemas are importable
- Migration script is valid

Run before deploying to production.
"""

import sys
import os
import logging
from typing import List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def verify_models() -> Tuple[bool, List[str]]:
    """Verify all models are defined and relationships exist"""
    logger.info("Verifying models...")
    errors = []

    try:
        from models import (
            VideoTestSequence, SequenceVideoResult,
            DetectionEvent, TestSession
        )

        # Check VideoTestSequence
        required_fields = [
            'id', 'test_session_id', 'name', 'video_ids', 'sequence_order',
            'status', 'max_latency_ms', 'total_videos', 'sequence_start_time'
        ]
        vts_fields = [c.name for c in VideoTestSequence.__table__.columns]
        missing = [f for f in required_fields if f not in vts_fields]
        if missing:
            errors.append(f"VideoTestSequence missing fields: {missing}")

        # Check SequenceVideoResult
        required_fields = [
            'id', 'video_sequence_id', 'video_id', 'sequence_order',
            'video_start_time', 'video_play_offset_ms', 'video_status',
            'expected_detection_count', 'actual_detection_count',
            'avg_latency_ms', 'pass_rate_percent'
        ]
        svr_fields = [c.name for c in SequenceVideoResult.__table__.columns]
        missing = [f for f in required_fields if f not in svr_fields]
        if missing:
            errors.append(f"SequenceVideoResult missing fields: {missing}")

        # Check DetectionEvent enhancements
        required_fields = [
            'sequence_video_result_id', 'sequence_timestamp',
            'video_play_offset_ms', 'correlation_method'
        ]
        de_fields = [c.name for c in DetectionEvent.__table__.columns]
        missing = [f for f in required_fields if f not in de_fields]
        if missing:
            errors.append(f"DetectionEvent missing fields: {missing}")

        # Check TestSession enhancements
        if 'has_video_sequence' not in [c.name for c in TestSession.__table__.columns]:
            errors.append("TestSession missing 'has_video_sequence' field")

        # Check relationships
        if not hasattr(TestSession, 'video_sequences'):
            errors.append("TestSession missing 'video_sequences' relationship")

        if not hasattr(VideoTestSequence, 'video_results'):
            errors.append("VideoTestSequence missing 'video_results' relationship")

        if not hasattr(SequenceVideoResult, 'detection_events'):
            errors.append("SequenceVideoResult missing 'detection_events' relationship")

        if not hasattr(DetectionEvent, 'sequence_video_result'):
            errors.append("DetectionEvent missing 'sequence_video_result' relationship")

        if errors:
            return False, errors

        logger.info("✅ All models verified successfully")
        return True, []

    except Exception as e:
        logger.error(f"Model verification failed: {e}")
        return False, [str(e)]


def verify_schemas() -> Tuple[bool, List[str]]:
    """Verify all Pydantic schemas are importable"""
    logger.info("Verifying schemas...")
    errors = []

    try:
        from schemas import (
            VideoTestSequenceCreate, VideoTestSequenceUpdate,
            VideoTestSequenceResponse, SequenceVideoResultCreate,
            SequenceVideoResultUpdate, SequenceVideoResultResponse,
            SequenceDetectionEventCreate, SequenceDetectionEventResponse,
            VideoSequenceProgressResponse, VideoSequenceStatistics
        )

        # Test schema instantiation
        test_data = {
            "name": "Test Sequence",
            "videoIds": ["vid1", "vid2"],
            "maxLatencyMs": 100
        }

        try:
            schema = VideoTestSequenceCreate(**test_data)
            if not schema.name:
                errors.append("Schema validation failed")
        except Exception as e:
            errors.append(f"Schema instantiation failed: {e}")

        if errors:
            return False, errors

        logger.info("✅ All schemas verified successfully")
        return True, []

    except Exception as e:
        logger.error(f"Schema verification failed: {e}")
        return False, [str(e)]


def verify_migration_script() -> Tuple[bool, List[str]]:
    """Verify migration script is syntactically correct"""
    logger.info("Verifying migration script...")
    errors = []

    try:
        import migrations.add_video_sequence_schema as migration

        # Check required functions exist
        required_functions = [
            'run_migration', 'rollback_migration', 'verify_migration',
            'upgrade_test_sessions', 'upgrade_detection_events',
            'create_video_test_sequences', 'create_sequence_video_results'
        ]

        for func_name in required_functions:
            if not hasattr(migration, func_name):
                errors.append(f"Migration missing function: {func_name}")

        if errors:
            return False, errors

        logger.info("✅ Migration script verified successfully")
        return True, []

    except Exception as e:
        logger.error(f"Migration script verification failed: {e}")
        return False, [str(e)]


def verify_indexes() -> Tuple[bool, List[str]]:
    """Verify critical indexes are defined"""
    logger.info("Verifying indexes...")
    errors = []

    try:
        from models import VideoTestSequence, SequenceVideoResult, DetectionEvent

        # Check VideoTestSequence indexes
        vts_indexes = [idx.name for idx in VideoTestSequence.__table__.indexes]
        required_vts_indexes = [
            'idx_video_seq_session',
            'idx_video_seq_status',
            'idx_video_seq_session_status'
        ]
        missing = [idx for idx in required_vts_indexes if idx not in vts_indexes]
        if missing:
            errors.append(f"VideoTestSequence missing indexes: {missing}")

        # Check SequenceVideoResult indexes
        svr_indexes = [idx.name for idx in SequenceVideoResult.__table__.indexes]
        required_svr_indexes = [
            'idx_seq_video_result_sequence',
            'idx_seq_video_result_order',
            'idx_seq_video_result_latency'
        ]
        missing = [idx for idx in required_svr_indexes if idx not in svr_indexes]
        if missing:
            errors.append(f"SequenceVideoResult missing indexes: {missing}")

        # Check DetectionEvent sequence indexes
        de_indexes = [idx.name for idx in DetectionEvent.__table__.indexes]
        required_de_indexes = [
            'idx_detection_sequence_video_result',
            'idx_detection_sequence_timestamp'
        ]
        missing = [idx for idx in required_de_indexes if idx not in de_indexes]
        if missing:
            errors.append(f"DetectionEvent missing sequence indexes: {missing}")

        if errors:
            return False, errors

        logger.info("✅ All indexes verified successfully")
        return True, []

    except Exception as e:
        logger.error(f"Index verification failed: {e}")
        return False, [str(e)]


def run_all_verifications() -> bool:
    """Run all verification checks"""
    logger.info("="*70)
    logger.info("Starting Multi-Video Sequential Testing Schema Verification")
    logger.info("="*70)

    all_passed = True
    all_errors = []

    # Run all verification checks
    checks = [
        ("Models", verify_models),
        ("Schemas", verify_schemas),
        ("Migration Script", verify_migration_script),
        ("Indexes", verify_indexes)
    ]

    for check_name, check_func in checks:
        passed, errors = check_func()
        if not passed:
            all_passed = False
            all_errors.extend([f"{check_name}: {err}" for err in errors])

    logger.info("="*70)
    if all_passed:
        logger.info("✅ ALL VERIFICATIONS PASSED")
        logger.info("="*70)
        logger.info("Schema is ready for deployment")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Run migration: python3 migrations/add_video_sequence_schema.py")
        logger.info("2. Create API endpoints for sequence management")
        logger.info("3. Implement sequence execution logic")
        logger.info("4. Add frontend components")
        return True
    else:
        logger.error("❌ VERIFICATION FAILED")
        logger.info("="*70)
        logger.error("Errors found:")
        for error in all_errors:
            logger.error(f"  - {error}")
        logger.info("")
        logger.error("Please fix the errors before deploying")
        return False


if __name__ == "__main__":
    success = run_all_verifications()
    sys.exit(0 if success else 1)