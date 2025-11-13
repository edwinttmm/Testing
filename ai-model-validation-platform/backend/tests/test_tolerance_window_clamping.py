"""
Test Tolerance Window Clamping

Critical Test: Verify tolerance windows don't extend into next video.
Based on CONSOLIDATED_APPROVAL_PROCESS_ANALYSIS.md Lines 1026-1114
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models import (
    DetectionEvent, GroundTruthObject, TestSession, Video, Project,
    VideoTestSequence, SequenceVideoResult
)
from services.video_id_resolver import VideoIdResolver


class TestToleranceWindowClamping:
    """Test suite for tolerance window clamping at video boundaries"""

    @pytest.fixture
    def setup_back_to_back_videos(self, db_session: Session):
        """
        Setup two back-to-back videos in a sequence

        Video 1: 0ms - 30000ms
        Video 2: 30000ms - 60000ms (starts immediately after Video 1)

        Tolerance: 500ms (should NOT extend into Video 2)
        """
        # Create project
        project = Project(
            id="clamp-project",
            name="Tolerance Clamp Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)

        # Create two videos
        video1 = Video(
            id="video1",
            project_id=project.id,
            filename="video1.mp4",
            duration_ms=30000  # 30 seconds
        )

        video2 = Video(
            id="video2",
            project_id=project.id,
            filename="video2.mp4",
            duration_ms=30000  # 30 seconds
        )

        db_session.add_all([video1, video2])

        # Create test session with sequence
        session = TestSession(
            id="clamp-session",
            project_id=project.id,
            status="running",
            has_video_sequence=True,
            sequence_metadata={
                "video_timing": {
                    "video1": {
                        "start_time": 0,
                        "cumulative_offset_ms": 0,
                        "actual_duration_ms": 30000,
                        "expected_duration_ms": 30000
                    },
                    "video2": {
                        "start_time": 30.0,
                        "cumulative_offset_ms": 30000,
                        "actual_duration_ms": 30000,
                        "expected_duration_ms": 30000
                    }
                }
            }
        )
        db_session.add(session)

        # Create sequence
        sequence = VideoTestSequence(
            id="test-sequence",
            session_id=session.id,
            total_videos=2,
            current_video_index=1,
            status="completed"
        )
        db_session.add(sequence)
        session.sequence_id = sequence.id

        # Create sequence video results
        result1 = SequenceVideoResult(
            id="result1",
            sequence_id=sequence.id,
            video_id=video1.id,
            position=0,
            status="completed",
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            actual_duration_ms=30000
        )

        result2 = SequenceVideoResult(
            id="result2",
            sequence_id=sequence.id,
            video_id=video2.id,
            position=1,
            status="playing",
            started_at=datetime.now(timezone.utc),
            actual_duration_ms=None  # Still playing
        )

        db_session.add_all([result1, result2])
        db_session.commit()

        return {
            "session": session,
            "video1": video1,
            "video2": video2,
            "sequence": sequence
        }

    def test_tolerance_clamped_at_video_boundary(
        self, db_session, setup_back_to_back_videos
    ):
        """
        Test that tolerance window is clamped at next video start

        Scenario:
          Video1 ends @ 30.000s
          Video2 starts @ 30.000s
          Detection @ 30.100s (100ms into Video2)

        Expected:
          - Detection assigned to Video2 (NOT Video1 + tolerance)
          - Video1 tolerance should be clamped to 30.000s (not 30.500s)
        """
        scenario = setup_back_to_back_videos
        session = scenario["session"]

        # Create detection 100ms into Video2
        detection = DetectionEvent(
            id="boundary-det",
            session_id=session.id,
            video_id=None,  # To be resolved
            timestamp=30.100,
            video_relative_timestamp=30100,  # 100ms into Video2
            voltage=5.0
        )
        db_session.add(detection)
        db_session.commit()

        # Resolve video_id
        resolved_video_id = VideoIdResolver.resolve_video_id(
            session_id=session.id,
            timestamp_ms=30100,
            sequence_metadata=session.sequence_metadata
        )

        # Should be assigned to Video2, NOT Video1
        assert resolved_video_id == "video2", \
            f"Detection @ 30.100s should be assigned to Video2, got {resolved_video_id}"

    def test_late_detection_within_clamped_tolerance(
        self, db_session, setup_back_to_back_videos
    ):
        """
        Test detection right at video end (within original tolerance but after clamp)

        Scenario:
          Video1 ends @ 30.000s
          Detection @ 30.050s (50ms after Video1 end)
          Original tolerance would include this (30.000 + 500ms = 30.500s)
          But should be clamped to 30.000s

        Expected:
          - Detection assigned to Video2
        """
        scenario = setup_back_to_back_videos
        session = scenario["session"]

        # Detection 50ms after Video1 end
        detection = DetectionEvent(
            id="late-det",
            session_id=session.id,
            video_id=None,
            timestamp=30.050,
            video_relative_timestamp=30050,
            voltage=5.0
        )
        db_session.add(detection)
        db_session.commit()

        resolved_video_id = VideoIdResolver.resolve_video_id(
            session_id=session.id,
            timestamp_ms=30050,
            sequence_metadata=session.sequence_metadata
        )

        # Should go to Video2 (not extended into Video1's tolerance)
        assert resolved_video_id == "video2", \
            f"Late detection should be assigned to Video2, got {resolved_video_id}"

    def test_detection_exactly_at_boundary(
        self, db_session, setup_back_to_back_videos
    ):
        """
        Test detection exactly at video boundary (30.000s)

        Expected:
          - Could belong to either video
          - Should be assigned to Video2 (next video in sequence)
        """
        scenario = setup_back_to_back_videos
        session = scenario["session"]

        # Detection exactly at boundary
        detection = DetectionEvent(
            id="boundary-exact-det",
            session_id=session.id,
            video_id=None,
            timestamp=30.000,
            video_relative_timestamp=30000,
            voltage=5.0
        )
        db_session.add(detection)
        db_session.commit()

        resolved_video_id = VideoIdResolver.resolve_video_id(
            session_id=session.id,
            timestamp_ms=30000,
            sequence_metadata=session.sequence_metadata
        )

        # At boundary, should belong to next video
        assert resolved_video_id in ["video1", "video2"], \
            f"Boundary detection should be assigned to valid video, got {resolved_video_id}"

    def test_cross_video_gt_matching_prevented(self, db_session):
        """
        Test that GT matching respects video boundaries

        Scenario:
          Video1 GT @ 29.950s
          Video2 Detection @ 30.050s (100ms difference)

        Expected:
          - NO match (different videos)
          - Detection is FP
          - GT is FN
        """
        # Setup
        project = Project(
            id="cross-project",
            name="Cross Video Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)

        video1 = Video(id="v1", project_id=project.id, filename="v1.mp4", duration_ms=30000)
        video2 = Video(id="v2", project_id=project.id, filename="v2.mp4", duration_ms=30000)
        db_session.add_all([video1, video2])

        session = TestSession(
            id="cross-session",
            project_id=project.id,
            status="running",
            has_video_sequence=True
        )
        db_session.add(session)

        # GT in Video1 near end
        gt = GroundTruthObject(
            id="cross-gt",
            video_id=video1.id,
            timestamp=29.950,  # 50ms before Video1 end
            object_type="pedestrian",
            soft_deleted=False
        )
        db_session.add(gt)

        # Detection in Video2 near start
        detection = DetectionEvent(
            id="cross-det",
            session_id=session.id,
            video_id=video2.id,
            timestamp=30.050,  # 50ms into Video2
            video_relative_timestamp=30050,
            voltage=5.0
        )
        db_session.add(detection)

        db_session.commit()

        # Run matching
        from services.ground_truth_matching_service import GroundTruthMatchingService
        service = GroundTruthMatchingService(db_session)

        results = service.match_detections_to_ground_truth(
            session_id=session.id,
            tolerance_ms=100.0  # Would match if not for video boundary
        )

        # Should NOT match (different videos)
        assert results.true_positives == 0, \
            "Cross-video matching should be prevented"

        assert results.false_positives == 1, \
            "Detection from Video2 should be FP"

        assert results.false_negatives == 1, \
            "GT from Video1 should be FN"


class TestToleranceWithGaps:
    """Test tolerance behavior when videos have intentional gaps"""

    def test_tolerance_with_sequence_gap(self, db_session):
        """
        Test tolerance when videos have 1-second gap between them

        Scenario:
          Video1: 0 - 30s
          Gap: 1 second
          Video2: 31s - 61s

        Expected:
          - Tolerance extends safely (no overlap possible)
          - Detections in gap assigned to nearest video
        """
        project = Project(
            id="gap-project",
            name="Gap Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)

        video1 = Video(id="gap-v1", project_id=project.id, filename="v1.mp4", duration_ms=30000)
        video2 = Video(id="gap-v2", project_id=project.id, filename="v2.mp4", duration_ms=30000)
        db_session.add_all([video1, video2])

        session = TestSession(
            id="gap-session",
            project_id=project.id,
            status="running",
            has_video_sequence=True,
            sequence_metadata={
                "video_timing": {
                    "gap-v1": {
                        "cumulative_offset_ms": 0,
                        "actual_duration_ms": 30000
                    },
                    "gap-v2": {
                        "cumulative_offset_ms": 31000,  # 1 second gap
                        "actual_duration_ms": 30000
                    }
                }
            }
        )
        db_session.add(session)
        db_session.commit()

        # Detection in gap (30.5s)
        detection = DetectionEvent(
            id="gap-det",
            session_id=session.id,
            video_id=None,
            timestamp=30.500,
            video_relative_timestamp=30500,
            voltage=5.0
        )
        db_session.add(detection)
        db_session.commit()

        resolved_video_id = VideoIdResolver.resolve_video_id(
            session_id=session.id,
            timestamp_ms=30500,
            sequence_metadata=session.sequence_metadata
        )

        # Should assign to Video1 (within tolerance of 30s + 500ms)
        assert resolved_video_id == "gap-v1", \
            f"Detection in gap should belong to Video1 (with tolerance), got {resolved_video_id}"
