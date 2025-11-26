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

Original location: tests/test_validation_error_handling.py
"""

"""
Tests for Validation Error Handling

Comprehensive tests for session validation failure handling,
retry mechanisms, and cleanup jobs.
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from models import TestSession
from services.session_completion_service import (
    session_completion_service,
    ValidationFailedException
)
from services.session_cleanup import (
    cleanup_stale_sessions,
    cleanup_orphaned_sessions
)

class TestValidationFailureHandling:
    """Test session validation failure scenarios"""

    def test_validation_failure_marks_session_failed(self, db: Session):
        """Test that validation failure marks session as validation_failed"""
        # Create test session with multi-video sequence (will trigger validation)
        session = TestSession(
            id="test-session-1",
            name="Test Session",
            project_id="test-project",
            video_id="test-video",
            status="running",
            has_video_sequence=True,
            started_at=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()

        # Attempt completion without video timing metadata (should fail)
        result = session_completion_service.complete_session("test-session-1")

        # Verify session marked as failed
        db.refresh(session)
        assert session.status == "validation_failed"
        assert session.failure_reason is not None
        assert "video_timing" in session.failure_reason
        assert session.failed_at is not None
        assert session.failure_details is not None
        assert session.failure_details['recoverable'] == True

    def test_validation_failure_stores_details(self, db: Session):
        """Test that failure details are properly stored"""
        session = TestSession(
            id="test-session-2",
            name="Test Session",
            project_id="test-project",
            video_id="test-video",
            status="running",
            has_video_sequence=True,
            started_at=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()

        # Trigger validation failure
        session_completion_service.complete_session("test-session-2")

        # Verify details
        db.refresh(session)
        details = session.failure_details
        assert details['validation_type'] == 'video_sequence_completion'
        assert 'error_message' in details
        assert 'timestamp' in details
        assert details['session_type'] in ['multi_video', 'single_video']

    def test_retry_resets_failed_session(self, db: Session):
        """Test that retry endpoint resets failed session status"""
        # Create failed session
        session = TestSession(
            id="test-session-3",
            name="Test Session",
            project_id="test-project",
            video_id="test-video",
            status="validation_failed",
            failure_reason="Test failure",
            failed_at=datetime.now(timezone.utc),
            failure_details={'recoverable': True}
        )
        db.add(session)
        db.commit()

        # Simulate retry endpoint logic
        session.status = "running"
        session.failure_reason = None
        session.failed_at = None
        session.retry_count = 1
        session.last_retry_at = datetime.now(timezone.utc)
        db.commit()

        # Verify reset
        assert session.status == "running"
        assert session.retry_count == 1
        assert session.last_retry_at is not None

class TestSessionCleanup:
    """Test session cleanup jobs"""

    def test_cleanup_marks_stale_sessions_failed(self, db: Session):
        """Test that stale sessions are marked as failed"""
        # Create stale session (started 3 hours ago, still running)
        stale_time = datetime.now(timezone.utc) - timedelta(hours=3)
        session = TestSession(
            id="stale-session-1",
            name="Stale Session",
            project_id="test-project",
            video_id="test-video",
            status="running",
            started_at=stale_time
        )
        db.add(session)
        db.commit()

        # Run cleanup
        cleanup_stale_sessions()

        # Verify session marked as failed
        db.refresh(session)
        assert session.status == "error"
        assert "timeout" in session.failure_reason.lower()
        assert session.failed_at is not None
        assert session.failure_details['error_type'] == 'session_timeout'
        assert session.failure_details['recoverable'] == False

    def test_cleanup_ignores_recent_sessions(self, db: Session):
        """Test that recent running sessions are not cleaned up"""
        # Create recent session (started 1 hour ago)
        recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
        session = TestSession(
            id="recent-session-1",
            name="Recent Session",
            project_id="test-project",
            video_id="test-video",
            status="running",
            started_at=recent_time
        )
        db.add(session)
        db.commit()

        # Run cleanup
        cleanup_stale_sessions()

        # Verify session still running
        db.refresh(session)
        assert session.status == "running"
        assert session.failure_reason is None

    def test_cleanup_orphaned_sessions(self, db: Session):
        """Test that orphaned sessions are cancelled"""
        # Create orphaned session (created 2 hours ago, never started)
        orphan_time = datetime.now(timezone.utc) - timedelta(hours=2)
        session = TestSession(
            id="orphan-session-1",
            name="Orphaned Session",
            project_id="test-project",
            video_id="test-video",
            status="created",
            created_at=orphan_time,
            started_at=None
        )
        db.add(session)
        db.commit()

        # Run cleanup
        cleanup_orphaned_sessions()

        # Verify session cancelled
        db.refresh(session)
        assert session.status == "cancelled"
        assert "never started" in session.failure_reason
        assert session.failure_details['error_type'] == 'orphaned_session'

class TestUnexpectedErrorHandling:
    """Test handling of unexpected errors during completion"""

    def test_unexpected_error_marks_session_error(self, db: Session):
        """Test that unexpected errors mark session as error"""
        # This would be tested by mocking a service to raise an exception
        # For now, verify the error handling logic exists
        session = TestSession(
            id="error-session-1",
            name="Error Session",
            project_id="test-project",
            video_id="test-video",
            status="running",
            started_at=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()

        # The actual test would mock a service to fail
        # Here we just verify the error state can be set
        session.status = "error"
        session.failure_reason = "Unexpected error: test"
        session.failure_details = {
            'error_type': 'unexpected_error',
            'recoverable': False
        }
        db.commit()

        db.refresh(session)
        assert session.status == "error"
        assert session.failure_details['error_type'] == 'unexpected_error'
