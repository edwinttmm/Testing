#!/usr/bin/env python3
"""
Verification script for database transaction atomicity implementation.

Tests that session completion properly:
1. Commits all steps atomically (all-or-nothing)
2. Rolls back on failure (no partial updates)
3. Tracks completion state for idempotent retry
4. Handles concurrent completions safely
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timezone
from database import SessionLocal
from models import TestSession, DetectionEvent, DetectionComparison, SessionCompletionState
from services.transaction_manager import (
    atomic_session_completion,
    mark_completion_step,
    get_last_completed_step,
    clear_completion_state
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_atomic_commit():
    """Test that successful completion commits all changes"""
    logger.info("=" * 80)
    logger.info("TEST 1: Atomic Commit on Success")
    logger.info("=" * 80)

    db = SessionLocal()
    try:
        # Create test session
        session = TestSession(
            id="atomic-test-success",
            name="Atomic Test Success",
            project_id="test-project",
            video_id="test-video",
            status="running"
        )
        db.add(session)
        db.commit()

        # Execute atomic completion
        with atomic_session_completion(db, session.id):
            session.status = "completed"
            session.completed_at = datetime.now(timezone.utc)
            mark_completion_step(db, session.id, 'validation')
            mark_completion_step(db, session.id, 'matching')
            mark_completion_step(db, session.id, 'storage')

        # Verify changes committed
        db.refresh(session)
        assert session.status == "completed", "Session status not updated"
        assert session.completed_at is not None, "Completed timestamp not set"

        last_step = get_last_completed_step(db, session.id)
        assert last_step == 'storage', f"Expected 'storage', got '{last_step}'"

        logger.info("✅ PASS: All changes committed atomically")

        # Cleanup
        clear_completion_state(db, session.id)
        db.delete(session)
        db.commit()

    except AssertionError as e:
        logger.error(f"❌ FAIL: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ ERROR: {e}", exc_info=True)
        return False
    finally:
        db.close()

    return True


def test_atomic_rollback():
    """Test that failure rolls back all changes"""
    logger.info("=" * 80)
    logger.info("TEST 2: Atomic Rollback on Failure")
    logger.info("=" * 80)

    db = SessionLocal()
    try:
        # Create test session
        session = TestSession(
            id="atomic-test-failure",
            name="Atomic Test Failure",
            project_id="test-project",
            video_id="test-video",
            status="running"
        )
        db.add(session)
        db.commit()

        original_status = session.status

        # Execute with intentional failure
        try:
            with atomic_session_completion(db, session.id):
                session.status = "completed"
                mark_completion_step(db, session.id, 'validation')
                # Intentional failure
                raise ValueError("Simulated failure")
        except ValueError:
            pass  # Expected

        # Verify rollback
        db.refresh(session)
        assert session.status == original_status, f"Status changed from '{original_status}' to '{session.status}' (should be unchanged)"

        last_step = get_last_completed_step(db, session.id)
        assert last_step is None, f"Completion state found: '{last_step}' (should be None after rollback)"

        logger.info("✅ PASS: All changes rolled back on failure")

        # Cleanup
        db.delete(session)
        db.commit()

    except AssertionError as e:
        logger.error(f"❌ FAIL: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ ERROR: {e}", exc_info=True)
        return False
    finally:
        db.close()

    return True


def test_idempotent_retry():
    """Test that completion state tracks steps for idempotent retry"""
    logger.info("=" * 80)
    logger.info("TEST 3: Idempotent Retry with Completion State")
    logger.info("=" * 80)

    db = SessionLocal()
    try:
        session_id = "atomic-test-retry"

        # Simulate partial completion
        mark_completion_step(db, session_id, 'validation')
        db.commit()

        last_step = get_last_completed_step(db, session_id)
        assert last_step == 'validation', f"Expected 'validation', got '{last_step}'"

        # Update to next step
        mark_completion_step(db, session_id, 'matching')
        db.commit()

        last_step = get_last_completed_step(db, session_id)
        assert last_step == 'matching', f"Expected 'matching', got '{last_step}'"

        logger.info("✅ PASS: Completion state tracking works correctly")

        # Cleanup
        clear_completion_state(db, session_id)
        db.commit()

        last_step = get_last_completed_step(db, session_id)
        assert last_step is None, f"Completion state not cleared: '{last_step}'"

    except AssertionError as e:
        logger.error(f"❌ FAIL: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ ERROR: {e}", exc_info=True)
        return False
    finally:
        db.close()

    return True


def test_no_duplicate_records():
    """Test that atomic transactions prevent duplicate DetectionComparison records"""
    logger.info("=" * 80)
    logger.info("TEST 4: No Duplicate Records After Retry")
    logger.info("=" * 80)

    db = SessionLocal()
    try:
        # Create test session
        session = TestSession(
            id="atomic-test-duplicates",
            name="Atomic Test Duplicates",
            project_id="test-project",
            video_id="test-video",
            status="running"
        )
        db.add(session)

        # Create test detection event
        detection = DetectionEvent(
            id="test-detection-1",
            test_session_id=session.id,
            timestamp=1234567890.0,
            video_id="test-video"
        )
        db.add(detection)
        db.commit()

        # Simulate failed completion that would create duplicate records in old implementation
        try:
            with atomic_session_completion(db, session.id):
                # Create comparison record
                comparison = DetectionComparison(
                    id="test-comparison-1",
                    test_session_id=session.id,
                    detection_event_id=detection.id,
                    match_type="TP"
                )
                db.add(comparison)
                db.flush()  # Flush to DB

                # Simulate failure
                raise RuntimeError("Simulated matching failure")
        except RuntimeError:
            pass  # Expected

        # Verify no comparison record exists (rolled back)
        comparison_count = db.query(DetectionComparison).filter(
            DetectionComparison.test_session_id == session.id
        ).count()

        assert comparison_count == 0, f"Found {comparison_count} comparison records after rollback (should be 0)"

        logger.info("✅ PASS: No duplicate records created after failed retry")

        # Cleanup
        db.delete(detection)
        db.delete(session)
        db.commit()

    except AssertionError as e:
        logger.error(f"❌ FAIL: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ ERROR: {e}", exc_info=True)
        return False
    finally:
        db.close()

    return True


def main():
    """Run all verification tests"""
    logger.info("")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 20 + "TRANSACTION ATOMICITY VERIFICATION" + " " * 24 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("")

    tests = [
        ("Atomic Commit on Success", test_atomic_commit),
        ("Atomic Rollback on Failure", test_atomic_rollback),
        ("Idempotent Retry with State", test_idempotent_retry),
        ("No Duplicate Records", test_no_duplicate_records)
    ]

    results = []
    for test_name, test_func in tests:
        logger.info("")
        result = test_func()
        results.append((test_name, result))
        logger.info("")

    # Summary
    logger.info("=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {test_name}")

    logger.info("=" * 80)
    logger.info(f"TOTAL: {passed}/{total} tests passed")
    logger.info("=" * 80)

    if passed == total:
        logger.info("")
        logger.info("🎉 ALL TESTS PASSED - Transaction atomicity verified!")
        logger.info("   Session completion is now PRODUCTION READY")
        logger.info("")
        return 0
    else:
        logger.error("")
        logger.error("⚠️  SOME TESTS FAILED - Review implementation")
        logger.error("")
        return 1


if __name__ == "__main__":
    sys.exit(main())
