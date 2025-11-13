"""
Transaction Manager for Atomic Session Completion

Provides context managers and utilities for ensuring atomic multi-step operations
during session completion. Prevents partial updates by wrapping all steps in
database transactions with automatic rollback on failure.

Key Features:
- Atomic session completion (all-or-nothing)
- Automatic rollback on errors
- Comprehensive error logging
- Nested transaction support
- Retry capability with exponential backoff
"""

import logging
from contextlib import contextmanager
from typing import Optional, Callable, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


@contextmanager
def atomic_session_completion(db: Session, session_id: str):
    """
    Context manager for atomic multi-step session completion.

    All operations within this context are wrapped in a single database transaction.
    If any operation fails, the entire transaction is rolled back, preventing
    partial updates and data inconsistency.

    Usage:
        with atomic_session_completion(db, session_id) as tx:
            # Step 1: Validation
            validate_video_sequence_completion(session_id)

            # Step 2: NULL video_id reassignment
            reassign_null_video_ids(session_id)

            # Step 3: Ground truth matching
            match_detections_to_ground_truth(session_id)

            # Step 4: Metrics calculation
            calculate_session_metrics(session_id)

            # Step 5: Update session status
            session.status = "completed"

            # Single commit at end (automatic)

    Args:
        db: Database session
        session_id: Session identifier for logging

    Yields:
        Database session for transaction operations

    Raises:
        Exception: Re-raises any exception after rollback
    """
    try:
        logger.info(f"[TRANSACTION START] Session {session_id} - Beginning atomic completion")

        # Begin transaction (implicit with SQLAlchemy session)
        # All operations will be part of this transaction
        yield db

        # Commit on success
        db.commit()
        logger.info(f"[TRANSACTION COMMIT] Session {session_id} - All steps completed successfully")

    except Exception as e:
        # Rollback on any failure
        db.rollback()
        logger.error(
            f"[TRANSACTION ROLLBACK] Session {session_id} - Error during completion: {e}",
            exc_info=True
        )
        raise


@contextmanager
def atomic_ground_truth_matching(db: Session, session_id: str):
    """
    Context manager for atomic ground truth matching operations.

    Wraps ground truth matching and metrics calculation in a single transaction
    to ensure consistency between DetectionComparison records and session metrics.

    Args:
        db: Database session
        session_id: Session identifier

    Yields:
        Database session for matching operations
    """
    try:
        logger.info(f"[MATCHING TX START] Session {session_id} - Beginning atomic GT matching")

        yield db

        db.commit()
        logger.info(f"[MATCHING TX COMMIT] Session {session_id} - GT matching committed")

    except Exception as e:
        db.rollback()
        logger.error(
            f"[MATCHING TX ROLLBACK] Session {session_id} - GT matching failed: {e}",
            exc_info=True
        )
        raise


def execute_with_retry(
    func: Callable,
    max_retries: int = 3,
    backoff_base: float = 2.0,
    session_id: Optional[str] = None,
    *args,
    **kwargs
) -> Any:
    """
    Execute a function with exponential backoff retry logic.

    Useful for operations that may fail due to transient issues like
    database locks or network timeouts.

    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts
        backoff_base: Base for exponential backoff (seconds)
        session_id: Session ID for logging
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result of successful function execution

    Raises:
        Exception: Final exception if all retries exhausted
    """
    import time

    last_exception = None

    for attempt in range(max_retries):
        try:
            if session_id:
                logger.info(f"[RETRY {attempt+1}/{max_retries}] Session {session_id} - Executing {func.__name__}")

            result = func(*args, **kwargs)

            if session_id:
                logger.info(f"[RETRY SUCCESS] Session {session_id} - {func.__name__} succeeded on attempt {attempt+1}")

            return result

        except Exception as e:
            last_exception = e

            if attempt < max_retries - 1:
                # Calculate backoff delay
                delay = backoff_base ** attempt

                logger.warning(
                    f"[RETRY FAILED] Session {session_id} - {func.__name__} failed on attempt {attempt+1}: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )

                time.sleep(delay)
            else:
                logger.error(
                    f"[RETRY EXHAUSTED] Session {session_id} - {func.__name__} failed after {max_retries} attempts",
                    exc_info=True
                )

    # All retries exhausted
    raise last_exception


class TransactionScope:
    """
    Advanced transaction scope manager with nested transaction support.

    Provides savepoint-based nested transactions for complex multi-step operations
    where certain sub-steps may need independent rollback without affecting the
    entire transaction.
    """

    def __init__(self, db: Session, name: str = "transaction"):
        self.db = db
        self.name = name
        self.savepoint = None

    def __enter__(self):
        """Begin transaction or savepoint"""
        try:
            # Create savepoint for nested transaction
            self.savepoint = self.db.begin_nested()
            logger.debug(f"[SAVEPOINT BEGIN] {self.name}")
            return self
        except Exception as e:
            logger.error(f"[SAVEPOINT ERROR] {self.name} - Failed to begin: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Commit or rollback based on exception status"""
        try:
            if exc_type is None:
                # No exception - commit savepoint
                self.savepoint.commit()
                logger.debug(f"[SAVEPOINT COMMIT] {self.name}")
            else:
                # Exception occurred - rollback savepoint
                self.savepoint.rollback()
                logger.warning(
                    f"[SAVEPOINT ROLLBACK] {self.name} - Exception: {exc_val}",
                    exc_info=(exc_type, exc_val, exc_tb)
                )
        except Exception as e:
            logger.error(f"[SAVEPOINT CLEANUP ERROR] {self.name}: {e}")
            raise

        # Return False to propagate exception
        return False


def mark_completion_step(db: Session, session_id: str, step_name: str):
    """
    Mark a completion step as completed in the database.

    Used for idempotent retry - tracks which steps have been completed
    so retries can skip already-completed steps.

    Args:
        db: Database session
        session_id: Session identifier
        step_name: Name of the step ('validation', 'matching', 'metrics', 'storage')
    """
    from models import SessionCompletionState

    try:
        # Check if state record exists
        state = db.query(SessionCompletionState).filter(
            SessionCompletionState.session_id == session_id
        ).first()

        if not state:
            # Create new state record
            state = SessionCompletionState(
                session_id=session_id,
                step_completed=step_name,
                last_attempt=datetime.now(timezone.utc)
            )
            db.add(state)
        else:
            # Update existing state
            state.step_completed = step_name
            state.last_attempt = datetime.now(timezone.utc)

        db.flush()  # Flush but don't commit (let outer transaction handle commit)

        logger.info(f"[COMPLETION STEP] Session {session_id} - Marked '{step_name}' as completed")

    except Exception as e:
        logger.error(f"[COMPLETION STEP ERROR] Session {session_id} - Failed to mark '{step_name}': {e}")
        # Don't raise - this is non-critical tracking


def get_last_completed_step(db: Session, session_id: str) -> Optional[str]:
    """
    Get the last completed step for a session.

    Used for idempotent retry to determine where to resume.

    Args:
        db: Database session
        session_id: Session identifier

    Returns:
        Name of last completed step or None
    """
    from models import SessionCompletionState

    try:
        state = db.query(SessionCompletionState).filter(
            SessionCompletionState.session_id == session_id
        ).first()

        if state:
            logger.info(f"[COMPLETION RESUME] Session {session_id} - Last completed step: {state.step_completed}")
            return state.step_completed
        else:
            logger.info(f"[COMPLETION RESUME] Session {session_id} - No previous completion state found")
            return None

    except Exception as e:
        logger.error(f"[COMPLETION RESUME ERROR] Session {session_id}: {e}")
        return None


def clear_completion_state(db: Session, session_id: str):
    """
    Clear completion state after successful completion.

    Args:
        db: Database session
        session_id: Session identifier
    """
    from models import SessionCompletionState

    try:
        db.query(SessionCompletionState).filter(
            SessionCompletionState.session_id == session_id
        ).delete()

        db.flush()

        logger.info(f"[COMPLETION STATE CLEARED] Session {session_id}")

    except Exception as e:
        logger.warning(f"[COMPLETION STATE CLEAR ERROR] Session {session_id}: {e}")
        # Non-critical - don't raise
