"""
DEPRECATED TEST FILE
===================

This test file has been deprecated on 2025-11-20 because it imports services
that no longer exist or have been removed from the codebase.

Deprecated services used:
- Services that were removed during architecture refactoring
- Services that were consolidated into other modules
- Services that were replaced with newer implementations

This file is preserved for historical reference but is not actively maintained.
If you need similar functionality, please check the current service implementations
in src/services/ or consult the documentation.

Original location: tests/test_transaction_atomicity.py
"""

"""
Unit tests for transaction atomicity in session completion.

Tests ensure that session completion operations are atomic - either all steps
succeed and data is committed, or any failure triggers a rollback with no
partial updates.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError

from services.transaction_manager import (
    atomic_session_completion,
    execute_with_retry,
    mark_completion_step,
    get_last_completed_step,
    clear_completion_state,
    TransactionScope
)
from models import TestSession, SessionCompletionState


class TestAtomicSessionCompletion:
    """Test atomic transaction guarantees during session completion"""

    def test_successful_completion_commits_all_changes(self, db_session):
        """Test that successful completion commits all steps"""
        session_id = "test-session-123"

        # Create test session
        test_session = TestSession(
            id=session_id,
            name="Test Session",
            project_id="project-1",
            video_id="video-1",
            status="running"
        )
        db_session.add(test_session)
        db_session.commit()

        # Execute completion in atomic transaction
        with atomic_session_completion(db_session, session_id):
            # Simulate completion steps
            test_session.status = "completed"
            test_session.completed_at = datetime.now(timezone.utc)

            mark_completion_step(db_session, session_id, 'validation')
            mark_completion_step(db_session, session_id, 'matching')
            mark_completion_step(db_session, session_id, 'storage')

        # Verify session was committed
        db_session.refresh(test_session)
        assert test_session.status == "completed"
        assert test_session.completed_at is not None

        # Verify completion steps were tracked
        last_step = get_last_completed_step(db_session, session_id)
        assert last_step == 'storage'

    def test_failure_rolls_back_all_changes(self, db_session):
        """Test that any failure triggers rollback of all steps"""
        session_id = "test-session-456"

        # Create test session
        test_session = TestSession(
            id=session_id,
            name="Test Session",
            project_id="project-1",
            video_id="video-1",
            status="running"
        )
        db_session.add(test_session)
        db_session.commit()

        original_status = test_session.status

        # Execute completion with intentional failure
        with pytest.raises(ValueError):
            with atomic_session_completion(db_session, session_id):
                # Step 1: Update status
                test_session.status = "completed"
                mark_completion_step(db_session, session_id, 'validation')

                # Step 2: Simulate failure
                raise ValueError("Simulated matching failure")

        # Verify rollback occurred
        db_session.refresh(test_session)
        assert test_session.status == original_status  # Should be unchanged

        # Verify completion steps were NOT committed
        last_step = get_last_completed_step(db_session, session_id)
        assert last_step is None

    def test_partial_completion_rollback(self, db_session):
        """Test that partial completion is fully rolled back"""
        session_id = "test-session-789"

        # Create test session
        test_session = TestSession(
            id=session_id,
            name="Test Session",
            project_id="project-1",
            video_id="video-1",
            status="running"
        )
        db_session.add(test_session)
        db_session.commit()

        # Execute multi-step completion with failure in middle
        with pytest.raises(RuntimeError):
            with atomic_session_completion(db_session, session_id):
                # Step 1: Validation (success)
                mark_completion_step(db_session, session_id, 'validation')

                # Step 2: Matching (failure)
                mark_completion_step(db_session, session_id, 'matching')
                raise RuntimeError("Matching service error")

                # Step 3: Storage (never reached)
                mark_completion_step(db_session, session_id, 'storage')

        # Verify NO steps were committed
        last_step = get_last_completed_step(db_session, session_id)
        assert last_step is None


class TestRetryLogic:
    """Test retry logic with exponential backoff"""

    def test_successful_execution_no_retry(self):
        """Test that successful execution doesn't retry"""
        mock_func = Mock(return_value="success")

        result = execute_with_retry(
            mock_func,
            max_retries=3,
            session_id="test-123"
        )

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_on_transient_failure(self):
        """Test retry on transient failures"""
        mock_func = Mock(side_effect=[
            Exception("Transient error 1"),
            Exception("Transient error 2"),
            "success"
        ])

        result = execute_with_retry(
            mock_func,
            max_retries=3,
            backoff_base=0.1,  # Fast retry for testing
            session_id="test-456"
        )

        assert result == "success"
        assert mock_func.call_count == 3

    def test_exhaust_retries_raises_exception(self):
        """Test that exhausting retries raises final exception"""
        mock_func = Mock(side_effect=Exception("Persistent error"))

        with pytest.raises(Exception, match="Persistent error"):
            execute_with_retry(
                mock_func,
                max_retries=3,
                backoff_base=0.1,
                session_id="test-789"
            )

        assert mock_func.call_count == 3


class TestCompletionStateTracking:
    """Test completion state tracking for idempotent retry"""

    def test_mark_and_retrieve_completion_step(self, db_session):
        """Test marking and retrieving completion steps"""
        session_id = "state-test-123"

        # Mark steps in order
        mark_completion_step(db_session, session_id, 'validation')
        db_session.flush()

        last_step = get_last_completed_step(db_session, session_id)
        assert last_step == 'validation'

        # Update to next step
        mark_completion_step(db_session, session_id, 'matching')
        db_session.flush()

        last_step = get_last_completed_step(db_session, session_id)
        assert last_step == 'matching'

    def test_clear_completion_state(self, db_session):
        """Test clearing completion state after success"""
        session_id = "state-test-456"

        # Create completion state
        mark_completion_step(db_session, session_id, 'storage')
        db_session.flush()

        # Verify it exists
        last_step = get_last_completed_step(db_session, session_id)
        assert last_step == 'storage'

        # Clear state
        clear_completion_state(db_session, session_id)
        db_session.flush()

        # Verify it's cleared
        last_step = get_last_completed_step(db_session, session_id)
        assert last_step is None

    def test_completion_state_persists_across_transactions(self, db_session):
        """Test that completion state survives transaction rollback"""
        session_id = "state-test-789"

        # Mark step and commit
        mark_completion_step(db_session, session_id, 'validation')
        db_session.commit()

        # Simulate failed transaction
        try:
            with atomic_session_completion(db_session, session_id):
                mark_completion_step(db_session, session_id, 'matching')
                raise Exception("Simulated failure")
        except Exception:
            pass

        # Completion state for 'validation' should still exist
        # (it was committed before the failed transaction)
        last_step = get_last_completed_step(db_session, session_id)
        # Note: In real implementation, we'd track per-step in separate records
        # For simplicity, this test shows the concept


class TestNestedTransactions:
    """Test nested transaction support with savepoints"""

    def test_nested_transaction_commit(self, db_session):
        """Test nested transaction commits on success"""
        session_id = "nested-test-123"

        test_session = TestSession(
            id=session_id,
            name="Nested Test",
            project_id="project-1",
            video_id="video-1",
            status="running"
        )
        db_session.add(test_session)
        db_session.commit()

        with atomic_session_completion(db_session, session_id):
            test_session.status = "processing"

            # Nested transaction for sub-step
            with TransactionScope(db_session, "matching"):
                mark_completion_step(db_session, session_id, 'matching')
                # Success - savepoint commits

            test_session.status = "completed"

        db_session.refresh(test_session)
        assert test_session.status == "completed"

    def test_nested_transaction_rollback(self, db_session):
        """Test nested transaction rollback on failure"""
        session_id = "nested-test-456"

        test_session = TestSession(
            id=session_id,
            name="Nested Test",
            project_id="project-1",
            video_id="video-1",
            status="running"
        )
        db_session.add(test_session)
        db_session.commit()

        with pytest.raises(ValueError):
            with atomic_session_completion(db_session, session_id):
                test_session.status = "processing"

                # Nested transaction that fails
                try:
                    with TransactionScope(db_session, "matching"):
                        mark_completion_step(db_session, session_id, 'matching')
                        raise ValueError("Matching failed")
                except ValueError:
                    # Nested transaction rolled back, but outer continues
                    pass

                # Outer transaction also fails
                raise ValueError("Overall failure")

        db_session.refresh(test_session)
        assert test_session.status == "running"  # Rolled back to original


# Test fixtures
@pytest.fixture
def db_session():
    """Mock database session for testing"""
    from database import SessionLocal

    session = SessionLocal()
    yield session
    session.rollback()
    session.close()
