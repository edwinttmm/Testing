"""
Test Video Sequence Completion Validation

Validates that sessions cannot complete without proper video timing data.
Prevents NULL timestamps from corrupted video lifecycle events.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from services.session_completion_service import validate_video_sequence_completion
from models import TestSession, VideoTestSequence, SequenceVideoResult


class TestVideoSequenceCompletionValidation:
    """Test suite for video sequence completion validation"""

    def test_non_sequence_session_passes_validation(self, db: Session):
        """Non-sequence sessions should always pass validation"""
        # Create a regular non-sequence session
        session = TestSession(
            id="test-session-1",
            name="Non-Sequence Test",
            project_id="test-project",
            video_id="test-video",
            has_video_sequence=False,
            status="running"
        )
        db.add(session)
        db.commit()

        # Validate
        is_valid, error_message = validate_video_sequence_completion(db, "test-session-1")

        # Should pass without any timing data
        assert is_valid is True
        assert error_message == ""

    def test_sequence_session_missing_metadata_fails(self, db: Session):
        """Sequence session without sequence_metadata should fail"""
        # Create sequence session with no metadata
        session = TestSession(
            id="test-session-2",
            name="Broken Sequence",
            project_id="test-project",
            video_id="test-video",
            has_video_sequence=True,
            sequence_metadata=None,  # Missing metadata
            status="running"
        )
        db.add(session)
        db.commit()

        # Validate
        is_valid, error_message = validate_video_sequence_completion(db, "test-session-2")

        # Should fail
        assert is_valid is False
        assert "missing sequence_metadata" in error_message.lower()
        assert "video lifecycle events never fired" in error_message.lower()

    def test_sequence_session_missing_video_timing_fails(self, db: Session):
        """Sequence session without video_timing in metadata should fail"""
        # Create sequence session with metadata but no video_timing
        session = TestSession(
            id="test-session-3",
            name="Missing Video Timing",
            project_id="test-project",
            video_id="test-video",
            has_video_sequence=True,
            sequence_metadata={
                "video_ids": ["video-1", "video-2"],
                "max_latency_ms": 100
                # Missing 'video_timing' key
            },
            status="running"
        )
        db.add(session)
        db.commit()

        # Validate
        is_valid, error_message = validate_video_sequence_completion(db, "test-session-3")

        # Should fail
        assert is_valid is False
        assert "missing video_timing" in error_message.lower()
        assert "lifecycle events" in error_message.lower()

    def test_sequence_session_missing_start_time_fails(self, db: Session):
        """Video missing start time should fail validation"""
        # Create sequence session with video_timing missing start time
        session = TestSession(
            id="test-session-4",
            name="Missing Start Time",
            project_id="test-project",
            video_id="test-video",
            has_video_sequence=True,
            sequence_metadata={
                "video_ids": ["video-1", "video-2"],
                "video_timing": {
                    "video-1": {
                        "started_at": 1234567890.5,
                        "ended_at": 1234567920.5
                    },
                    "video-2": {
                        # Missing started_at
                        "ended_at": 1234567950.5
                    }
                }
            },
            status="running"
        )
        db.add(session)
        db.commit()

        # Validate
        is_valid, error_message = validate_video_sequence_completion(db, "test-session-4")

        # Should fail
        assert is_valid is False
        assert "missing start time" in error_message.lower()
        assert "video-2" in error_message

    def test_sequence_session_missing_end_time_fails(self, db: Session):
        """Video missing end time should fail validation"""
        # Create sequence session with video_timing missing end time
        session = TestSession(
            id="test-session-5",
            name="Missing End Time",
            project_id="test-project",
            video_id="test-video",
            has_video_sequence=True,
            sequence_metadata={
                "video_ids": ["video-1"],
                "video_timing": {
                    "video-1": {
                        "started_at": 1234567890.5,
                        # Missing ended_at
                    }
                }
            },
            status="running"
        )
        db.add(session)
        db.commit()

        # Validate
        is_valid, error_message = validate_video_sequence_completion(db, "test-session-5")

        # Should fail
        assert is_valid is False
        assert "missing end time" in error_message.lower()
        assert "video-1" in error_message

    def test_sequence_session_pending_videos_fails(self, db: Session):
        """Videos still in 'pending' status should fail validation"""
        # Create sequence session
        session = TestSession(
            id="test-session-6",
            name="Pending Videos",
            project_id="test-project",
            video_id="test-video",
            has_video_sequence=True,
            sequence_metadata={
                "video_ids": ["video-1", "video-2"],
                "video_timing": {
                    "video-1": {
                        "started_at": 1234567890.5,
                        "ended_at": 1234567920.5
                    },
                    "video-2": {
                        "started_at": 1234567920.5,
                        "ended_at": 1234567950.5
                    }
                }
            },
            status="running"
        )
        db.add(session)
        db.commit()

        # Create VideoTestSequence
        sequence = VideoTestSequence(
            id="seq-1",
            test_session_id="test-session-6",
            name="Test Sequence",
            video_ids=["video-1", "video-2"],
            total_videos=2,
            status="running"
        )
        db.add(sequence)
        db.commit()

        # Create SequenceVideoResults with one pending
        result1 = SequenceVideoResult(
            id="result-1",
            video_id="video-1",
            video_sequence_id="seq-1",
            sequence_order=0,
            video_status="completed"
        )
        result2 = SequenceVideoResult(
            id="result-2",
            video_id="video-2",
            video_sequence_id="seq-1",
            sequence_order=1,
            video_status="pending"  # Still pending!
        )
        db.add_all([result1, result2])
        db.commit()

        # Validate
        is_valid, error_message = validate_video_sequence_completion(db, "test-session-6")

        # Should fail
        assert is_valid is False
        assert "pending" in error_message.lower()
        assert "video-2" in error_message

    def test_sequence_session_complete_timing_passes(self, db: Session):
        """Sequence session with complete timing data should pass"""
        # Create sequence session with complete video_timing
        session = TestSession(
            id="test-session-7",
            name="Complete Timing",
            project_id="test-project",
            video_id="test-video",
            has_video_sequence=True,
            sequence_metadata={
                "video_ids": ["video-1", "video-2"],
                "video_timing": {
                    "video-1": {
                        "started_at": 1234567890.5,
                        "ended_at": 1234567920.5,
                        "video_id": "video-1"
                    },
                    "video-2": {
                        "started_at": 1234567920.5,
                        "ended_at": 1234567950.5,
                        "video_id": "video-2"
                    }
                }
            },
            status="running"
        )
        db.add(session)
        db.commit()

        # Create VideoTestSequence
        sequence = VideoTestSequence(
            id="seq-2",
            test_session_id="test-session-7",
            name="Complete Sequence",
            video_ids=["video-1", "video-2"],
            total_videos=2,
            status="running"
        )
        db.add(sequence)
        db.commit()

        # Create SequenceVideoResults - all completed
        result1 = SequenceVideoResult(
            id="result-3",
            video_id="video-1",
            video_sequence_id="seq-2",
            sequence_order=0,
            video_status="completed",
            video_start_time=1234567890.5,
            video_end_time=1234567920.5
        )
        result2 = SequenceVideoResult(
            id="result-4",
            video_id="video-2",
            video_sequence_id="seq-2",
            sequence_order=1,
            video_status="completed",
            video_start_time=1234567920.5,
            video_end_time=1234567950.5
        )
        db.add_all([result1, result2])
        db.commit()

        # Validate
        is_valid, error_message = validate_video_sequence_completion(db, "test-session-7")

        # Should pass
        assert is_valid is True
        assert error_message == ""

    def test_sequence_session_alternate_field_names_passes(self, db: Session):
        """Validation should accept both 'started_at' and 'start_time' field names"""
        # Create sequence session using alternate field names
        session = TestSession(
            id="test-session-8",
            name="Alternate Field Names",
            project_id="test-project",
            video_id="test-video",
            has_video_sequence=True,
            sequence_metadata={
                "video_ids": ["video-1"],
                "video_timing": {
                    "video-1": {
                        "start_time": 1234567890.5,  # Alternate name
                        "end_time": 1234567920.5     # Alternate name
                    }
                }
            },
            status="running"
        )
        db.add(session)
        db.commit()

        # Validate
        is_valid, error_message = validate_video_sequence_completion(db, "test-session-8")

        # Should pass with alternate field names
        assert is_valid is True
        assert error_message == ""

    def test_sequence_session_empty_video_timing_fails(self, db: Session):
        """Empty video_timing dictionary should fail validation"""
        # Create sequence session with empty video_timing
        session = TestSession(
            id="test-session-9",
            name="Empty Video Timing",
            project_id="test-project",
            video_id="test-video",
            has_video_sequence=True,
            sequence_metadata={
                "video_ids": ["video-1", "video-2"],
                "video_timing": {}  # Empty!
            },
            status="running"
        )
        db.add(session)
        db.commit()

        # Validate
        is_valid, error_message = validate_video_sequence_completion(db, "test-session-9")

        # Should fail
        assert is_valid is False
        assert "empty video_timing" in error_message.lower()
        assert "no videos were started" in error_message.lower()

    def test_nonexistent_session_fails(self, db: Session):
        """Validation of non-existent session should fail gracefully"""
        # Validate session that doesn't exist
        is_valid, error_message = validate_video_sequence_completion(db, "nonexistent-session")

        # Should fail
        assert is_valid is False
        assert "not found" in error_message.lower()


# Integration test for complete flow
class TestSessionCompletionEndpointIntegration:
    """Integration tests for session completion endpoint with validation"""

    def test_completion_endpoint_blocks_invalid_sequence(self, client, db: Session):
        """Session completion endpoint should reject sessions without timing data"""
        # Create broken sequence session
        session = TestSession(
            id="integration-test-1",
            name="Broken Integration Test",
            project_id="test-project",
            video_id="test-video",
            has_video_sequence=True,
            sequence_metadata=None,  # Missing metadata
            status="running"
        )
        db.add(session)
        db.commit()

        # Try to complete session
        response = client.post(f"/api/v1/hil-test/session/integration-test-1/complete")

        # Should return 400 error
        assert response.status_code == 400
        data = response.json()
        assert "validation failed" in data["detail"]["error"].lower()
        assert "missing sequence_metadata" in data["detail"]["message"].lower()

    def test_completion_endpoint_allows_valid_sequence(self, client, db: Session):
        """Session completion endpoint should accept sessions with complete timing"""
        # Create valid sequence session
        session = TestSession(
            id="integration-test-2",
            name="Valid Integration Test",
            project_id="test-project",
            video_id="test-video",
            has_video_sequence=True,
            sequence_metadata={
                "video_ids": ["video-1"],
                "video_timing": {
                    "video-1": {
                        "started_at": 1234567890.5,
                        "ended_at": 1234567920.5
                    }
                }
            },
            status="running"
        )
        db.add(session)
        db.commit()

        # Try to complete session
        response = client.post(f"/api/v1/hil-test/session/integration-test-2/complete")

        # Should succeed (200 or 404 if analysis not implemented)
        assert response.status_code in [200, 404]  # 404 is acceptable if analysis not found
