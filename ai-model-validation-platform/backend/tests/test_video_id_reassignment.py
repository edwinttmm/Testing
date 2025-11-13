"""
Test Suite: Video ID Reassignment for NULL Detection Events

Tests the detection_video_reassignment service that fixes race condition
where detection events arrive before video lifecycle events.

Edge cases tested:
1. Detection at exact video boundary time (start_time == detection_time)
2. Detection at exact video end boundary (end_time == detection_time)
3. Detection slightly before video start (within buffer)
4. Detection slightly after video end (within buffer)
5. Detection in gap between videos
6. Multi-video sequence with overlapping buffers
7. Session with no video timing metadata
8. Session with only one video having timing data
"""

import pytest
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock

from services.detection_video_reassignment import (
    DetectionVideoReassignmentService,
    get_detection_video_reassignment_service
)
from models import (
    TestSession,
    DetectionEvent,
    SequenceVideoResult,
    VideoTestSequence,
    Video
)


class TestVideoIDReassignmentEdgeCases:
    """Test edge cases for video_id reassignment logic."""

    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return DetectionVideoReassignmentService()

    @pytest.fixture
    def mock_video_timing_map(self) -> Dict[str, Dict[str, Any]]:
        """Create mock video timing map for multi-video sequence."""
        return {
            "video-1-id": {
                "start_time": 1000.0,  # Video 1: 1000.0s - 1010.0s (10s duration)
                "end_time": 1010.0,
                "duration_s": 10.0,
                "filename": "video1.mp4",
                "sequence_order": 0
            },
            "video-2-id": {
                "start_time": 1010.0,  # Video 2: 1010.0s - 1020.0s (10s duration)
                "end_time": 1020.0,
                "duration_s": 10.0,
                "filename": "video2.mp4",
                "sequence_order": 1
            }
        }

    def test_detection_at_exact_video_start_boundary(self, service, mock_video_timing_map):
        """Test detection at exact video start time (boundary case)."""
        # Detection at exact start of video 2
        detection = Mock(spec=DetectionEvent)
        detection.id = "det-boundary-start"
        detection.timestamp = 1010.0  # Exact start of video 2
        detection.video_id = None

        assigned_video = service._determine_video_from_timestamp(
            detection, mock_video_timing_map
        )

        assert assigned_video == "video-2-id", "Detection at exact start should be assigned to that video"

    def test_detection_at_exact_video_end_boundary(self, service, mock_video_timing_map):
        """Test detection at exact video end time (boundary case)."""
        # Detection at exact end of video 1
        detection = Mock(spec=DetectionEvent)
        detection.id = "det-boundary-end"
        detection.timestamp = 1010.0  # Exact end of video 1 (also start of video 2)
        detection.video_id = None

        assigned_video = service._determine_video_from_timestamp(
            detection, mock_video_timing_map
        )

        # Should prefer video 2 (videos are ordered, later video wins at boundary)
        assert assigned_video == "video-2-id", "Detection at boundary should prefer later video"

    def test_detection_slightly_before_video_start(self, service, mock_video_timing_map):
        """Test detection slightly before video start (within buffer)."""
        # Detection 50ms before video 1 start
        detection = Mock(spec=DetectionEvent)
        detection.id = "det-before-start"
        detection.timestamp = 999.95  # 50ms before video 1 start
        detection.video_id = None

        assigned_video = service._determine_video_from_timestamp(
            detection, mock_video_timing_map
        )

        # Should be assigned to video 1 (within 100ms buffer)
        assert assigned_video == "video-1-id", "Detection within buffer before start should be assigned"

    def test_detection_slightly_after_video_end(self, service, mock_video_timing_map):
        """Test detection slightly after video end (within buffer)."""
        # Detection 80ms after video 2 end
        detection = Mock(spec=DetectionEvent)
        detection.id = "det-after-end"
        detection.timestamp = 1020.08  # 80ms after video 2 end
        detection.video_id = None

        assigned_video = service._determine_video_from_timestamp(
            detection, mock_video_timing_map
        )

        # Should be assigned to video 2 (within 100ms buffer)
        assert assigned_video == "video-2-id", "Detection within buffer after end should be assigned"

    def test_detection_far_before_first_video(self, service, mock_video_timing_map):
        """Test detection far before first video start (outside fallback window)."""
        # Detection 15 seconds before video 1 start (outside 10s fallback window)
        detection = Mock(spec=DetectionEvent)
        detection.id = "det-far-before"
        detection.timestamp = 985.0  # 15s before video 1 start
        detection.video_id = None

        assigned_video = service._determine_video_from_timestamp(
            detection, mock_video_timing_map
        )

        # Should not be assigned (outside fallback window)
        assert assigned_video is None, "Detection far before videos should not be assigned"

    def test_detection_within_fallback_window_before_first_video(self, service, mock_video_timing_map):
        """Test detection within fallback window before first video."""
        # Detection 5 seconds before video 1 start (within 10s fallback window)
        detection = Mock(spec=DetectionEvent)
        detection.id = "det-fallback-before"
        detection.timestamp = 995.0  # 5s before video 1 start
        detection.video_id = None

        assigned_video = service._determine_video_from_timestamp(
            detection, mock_video_timing_map
        )

        # Should be assigned to first video (fallback logic)
        assert assigned_video == "video-1-id", "Detection in fallback window should be assigned to first video"

    def test_detection_in_gap_between_videos(self, service):
        """Test detection in gap between two videos."""
        # Videos with 5 second gap
        video_timing_map = {
            "video-1-id": {
                "start_time": 1000.0,
                "end_time": 1010.0,
                "duration_s": 10.0,
                "filename": "video1.mp4",
                "sequence_order": 0
            },
            "video-2-id": {
                "start_time": 1015.0,  # 5 second gap
                "end_time": 1025.0,
                "duration_s": 10.0,
                "filename": "video2.mp4",
                "sequence_order": 1
            }
        }

        # Detection in the gap (1012.5s)
        detection = Mock(spec=DetectionEvent)
        detection.id = "det-gap"
        detection.timestamp = 1012.5  # In 5s gap between videos
        detection.video_id = None

        assigned_video = service._determine_video_from_timestamp(
            detection, video_timing_map
        )

        # Should not be assigned (outside both video ranges and buffer)
        assert assigned_video is None, "Detection in gap between videos should not be assigned"

    def test_detection_with_no_timing_metadata(self, service):
        """Test detection when video timing metadata is missing."""
        # Empty timing map
        video_timing_map = {}

        detection = Mock(spec=DetectionEvent)
        detection.id = "det-no-timing"
        detection.timestamp = 1005.0
        detection.video_id = None

        assigned_video = service._determine_video_from_timestamp(
            detection, video_timing_map
        )

        assert assigned_video is None, "Detection should not be assigned when no timing data exists"

    def test_detection_with_null_timestamp(self, service, mock_video_timing_map):
        """Test detection with NULL timestamp."""
        detection = Mock(spec=DetectionEvent)
        detection.id = "det-null-timestamp"
        detection.timestamp = None
        detection.video_id = None

        assigned_video = service._determine_video_from_timestamp(
            detection, mock_video_timing_map
        )

        assert assigned_video is None, "Detection with NULL timestamp should not be assigned"

    def test_video_with_null_start_time(self, service):
        """Test video with NULL start_time in timing map."""
        video_timing_map = {
            "video-1-id": {
                "start_time": None,  # NULL start time
                "end_time": 1010.0,
                "duration_s": 10.0,
                "filename": "video1.mp4",
                "sequence_order": 0
            }
        }

        detection = Mock(spec=DetectionEvent)
        detection.id = "det-null-start"
        detection.timestamp = 1005.0
        detection.video_id = None

        assigned_video = service._determine_video_from_timestamp(
            detection, video_timing_map
        )

        assert assigned_video is None, "Video with NULL start_time should not be matched"

    def test_overlapping_buffer_zones(self, service):
        """Test detections in overlapping buffer zones between adjacent videos."""
        video_timing_map = {
            "video-1-id": {
                "start_time": 1000.0,
                "end_time": 1010.0,
                "duration_s": 10.0,
                "filename": "video1.mp4",
                "sequence_order": 0
            },
            "video-2-id": {
                "start_time": 1010.0,  # Adjacent (no gap)
                "end_time": 1020.0,
                "duration_s": 10.0,
                "filename": "video2.mp4",
                "sequence_order": 1
            }
        }

        # Detection exactly at boundary (within buffer of both videos)
        detection = Mock(spec=DetectionEvent)
        detection.id = "det-overlap"
        detection.timestamp = 1010.05  # 50ms after boundary
        detection.video_id = None

        assigned_video = service._determine_video_from_timestamp(
            detection, video_timing_map
        )

        # Should be assigned to video 2 (later video preferred in overlaps)
        assert assigned_video == "video-2-id", "Detection in overlap should prefer later video"

    @pytest.mark.asyncio
    async def test_reassignment_with_mixed_null_and_valid_video_ids(self, service):
        """Test reassignment when some detections have valid video_ids and others are NULL."""
        # Mock database and models
        with patch('services.detection_video_reassignment.SessionLocal') as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value = mock_db

            # Mock session with video sequence
            mock_session = Mock(spec=TestSession)
            mock_session.id = "test-session"
            mock_session.has_video_sequence = True
            mock_session.sequence_id = "seq-123"
            mock_session.sequence_metadata = {
                "video_timing": {
                    "video-1-id": {
                        "started_at": 1000.0,
                        "ended_at": 1010.0,
                        "fps": 30,
                        "actual_duration": 10.0
                    }
                }
            }

            # Mock video sequence
            mock_video_seq = Mock(spec=VideoTestSequence)
            mock_video_seq.id = "seq-123"

            # Mock video result
            mock_video_result = Mock(spec=SequenceVideoResult)
            mock_video_result.video_id = "video-1-id"
            mock_video_result.video_start_time = 1000.0
            mock_video_result.video_end_time = 1010.0
            mock_video_result.actual_duration_ms = 10000.0
            mock_video_result.sequence_order = 0
            mock_video_result.id = "vr-1"

            # Mock video
            mock_video = Mock(spec=Video)
            mock_video.id = "video-1-id"
            mock_video.filename = "video1.mp4"
            mock_video.duration = 10.0

            # Mock detections: some with NULL, some with valid video_id
            mock_detections = [
                Mock(
                    spec=DetectionEvent,
                    id="det-1",
                    timestamp=1005.0,
                    video_id=None,  # NULL - should be reassigned
                    video_relative_timestamp=None,
                    sequence_video_result_id=None
                ),
                Mock(
                    spec=DetectionEvent,
                    id="det-2",
                    timestamp=1006.0,
                    video_id="video-1-id",  # Already correct
                    video_relative_timestamp=6.0,
                    sequence_video_result_id="vr-1"
                ),
                Mock(
                    spec=DetectionEvent,
                    id="det-3",
                    timestamp=1007.0,
                    video_id="wrong-video-id",  # Wrong - should be corrected
                    video_relative_timestamp=None,
                    sequence_video_result_id=None
                )
            ]

            # Setup mock query chain
            mock_db.query.return_value.filter.return_value.first.side_effect = [
                mock_session,  # First query: get session
                mock_video_seq,  # Second query: get video sequence
            ]

            mock_db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = [
                [mock_video_result],  # Query for video results
                mock_detections  # Query for detections
            ]

            mock_db.query.return_value.filter.return_value.first.return_value = mock_video

            # Run reassignment
            result = await service.reassign_null_video_ids("test-session", dry_run=False)

            # Verify results
            assert result["success"] is True
            assert result["reassigned_count"] == 1  # det-1 reassigned from NULL
            assert result["corrected_existing"] == 1  # det-3 corrected from wrong-video-id
            assert result["total_detections"] == 3


class TestVideoIDReassignmentIntegration:
    """Integration tests for video_id reassignment."""

    @pytest.mark.asyncio
    async def test_session_completion_triggers_reassignment(self):
        """Test that session completion automatically triggers video_id reassignment."""
        with patch('services.session_completion_service.reassign_null_video_ids') as mock_reassign:
            mock_reassign.return_value = {
                "success": True,
                "reassigned_count": 50,
                "corrected_existing": 5,
                "total_detections": 100,
                "video_assignments": {"video-1": 60, "video-2": 40}
            }

            # Import after patching
            from services.session_completion_service import session_completion_service

            # Mock database
            with patch('services.session_completion_service.SessionLocal') as mock_session_local:
                mock_db = MagicMock()
                mock_session_local.return_value = mock_db

                # Mock session
                mock_session = Mock(spec=TestSession)
                mock_session.id = "test-session"
                mock_session.status = "running"
                mock_session.has_video_sequence = True
                mock_session.sequence_metadata = {"video_timing": {}}

                mock_db.query.return_value.filter.return_value.first.return_value = mock_session
                mock_db.query.return_value.filter.return_value.count.return_value = 100

                # Complete session
                success = await session_completion_service.complete_session("test-session")

                # Verify reassignment was called
                assert success is True
                mock_reassign.assert_called_once_with("test-session", dry_run=False)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
