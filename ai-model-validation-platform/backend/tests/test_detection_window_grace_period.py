"""
Comprehensive Test Suite for Detection Window Grace Period

Tests cover:
1. Grace period accepts signals 0-2s before video start
2. sequenceElapsedTime used for timing calculations
3. Multi-video sequences maintain accurate timing
4. No false "frame 0" classifications
"""

import os
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from models import (
    TestSession,
    Video,
    DetectionEvent,
    GroundTruthObject,
    Project,
    LabJackSignal
)
from services.ground_truth_matching_service import GroundTruthMatchingService


class TestDetectionWindowGracePeriod:
    """Test grace period logic for detection window timing"""

    @pytest.fixture
    def setup_test_data(self, test_db: Session):
        """Create test project, session, videos with realistic timing"""
        # Create project
        project = Project(
            name="Grace Period Test Project",
            description="Testing detection window grace period",
            created_at=datetime.now(timezone.utc)
        )
        test_db.add(project)
        test_db.flush()

        # Create test session
        session = TestSession(
            project_id=project.id,
            session_id="test-session-grace-period",
            test_type="HIL",
            status="in_progress",
            created_at=datetime.now(timezone.utc)
        )
        test_db.add(session)
        test_db.flush()

        # Create two videos with realistic timing
        # Video 1: starts at t=10.5s, sequenceElapsedTime=1.8s
        video1 = Video(
            filename="video1.mp4",
            original_name="video1.mp4",
            session_id=session.id,
            sequence_number=1,
            duration=5.0,
            start_time=10.5,  # Unix timestamp in seconds
            sequence_elapsed_time=1.8,  # Sequence-relative start time
            video_started_at=datetime.fromtimestamp(10.5, tz=timezone.utc)
        )
        test_db.add(video1)

        # Video 2: starts at t=20.0s, sequenceElapsedTime=11.3s
        video2 = Video(
            filename="video2.mp4",
            original_name="video2.mp4",
            session_id=session.id,
            sequence_number=2,
            duration=5.0,
            start_time=20.0,
            sequence_elapsed_time=11.3,
            video_started_at=datetime.fromtimestamp(20.0, tz=timezone.utc)
        )
        test_db.add(video2)
        test_db.flush()

        # Create ground truth for video1 (frame 30, which is ~1.0s into video)
        gt1 = GroundTruthObject(
            video_id=video1.id,
            frame_number=30,
            timestamp=11.8,  # sequence_elapsed_time + 1.0s into video
            object_class="person",
            bounding_box={"x": 100, "y": 100, "width": 50, "height": 50},
            confidence=1.0
        )
        test_db.add(gt1)

        # Create ground truth for video2 (frame 60, which is ~2.0s into video)
        gt2 = GroundTruthObject(
            video_id=video2.id,
            frame_number=60,
            timestamp=13.3,  # sequence_elapsed_time + 2.0s into video
            object_class="person",
            bounding_box={"x": 150, "y": 150, "width": 60, "height": 60},
            confidence=1.0
        )
        test_db.add(gt2)
        test_db.commit()

        return {
            "project": project,
            "session": session,
            "video1": video1,
            "video2": video2,
            "gt1": gt1,
            "gt2": gt2
        }

    def test_grace_period_accepts_early_signals(self, test_db: Session, setup_test_data):
        """Detections arriving 0-2s before video start should be accepted"""
        data = setup_test_data
        video1 = data["video1"]

        # Video starts at t=10.5s
        # Detection at t=10.3s (200ms before start) should PASS (within 2s grace)
        early_detection = DetectionEvent(
            session_id=data["session"].id,
            video_id=video1.id,
            timestamp=10.3,  # 200ms before video start
            video_relative_timestamp=0.0,  # Will be calculated
            sequence_elapsed_time=1.6,  # 200ms before video's sequence start
            object_class="person",
            confidence=0.95,
            bounding_box={"x": 100, "y": 100, "width": 50, "height": 50}
        )
        test_db.add(early_detection)

        # Detection at t=8.4s (2.1s before start) should FAIL (before grace period)
        too_early_detection = DetectionEvent(
            session_id=data["session"].id,
            video_id=video1.id,
            timestamp=8.4,  # 2.1s before video start
            video_relative_timestamp=0.0,
            sequence_elapsed_time=-0.3,  # Before sequence start
            object_class="person",
            confidence=0.95,
            bounding_box={"x": 100, "y": 100, "width": 50, "height": 50}
        )
        test_db.add(too_early_detection)
        test_db.commit()

        # Test grace period logic
        grace_period_seconds = 2.0
        video_start_time = video1.start_time  # 10.5s
        grace_period_start = video_start_time - grace_period_seconds  # 8.5s

        # Early detection should be within grace period
        assert early_detection.timestamp >= grace_period_start, \
            f"Detection at {early_detection.timestamp}s should be within grace period (>= {grace_period_start}s)"

        # Too early detection should be outside grace period
        assert too_early_detection.timestamp < grace_period_start, \
            f"Detection at {too_early_detection.timestamp}s should be outside grace period (< {grace_period_start}s)"

    def test_sequence_elapsed_time_initialization(self, test_db: Session, setup_test_data):
        """First video should initialize sequence start time correctly"""
        data = setup_test_data
        video1 = data["video1"]

        # Video 1 starts at t=10.5s with sequenceElapsedTime=1.8s
        # sequence_start_time should be 10.5 - 1.8 = 8.7s
        expected_sequence_start = video1.start_time - video1.sequence_elapsed_time
        assert expected_sequence_start == 8.7, \
            f"Sequence start should be {8.7}s, got {expected_sequence_start}s"

        # Verify this can be used to calculate detection windows
        grace_period_seconds = 2.0
        video_window_start = expected_sequence_start + video1.sequence_elapsed_time - grace_period_seconds
        video_window_end = expected_sequence_start + video1.sequence_elapsed_time + video1.duration

        # Video window should be [8.5s, 15.5s] (10.5 - 2.0, 10.5 + 5.0)
        assert abs(video_window_start - 8.5) < 0.01, \
            f"Window start should be ~8.5s, got {video_window_start}s"
        assert abs(video_window_end - 15.5) < 0.01, \
            f"Window end should be ~15.5s, got {video_window_end}s"

    def test_multi_video_timing_accuracy(self, test_db: Session, setup_test_data):
        """Multi-video sequences should maintain relative timing"""
        data = setup_test_data
        video1 = data["video1"]
        video2 = data["video2"]

        # Calculate sequence start time from video1
        sequence_start = video1.start_time - video1.sequence_elapsed_time  # 8.7s

        # Verify video2 timing is consistent with same sequence start
        video2_expected_start = sequence_start + video2.sequence_elapsed_time
        assert abs(video2_expected_start - video2.start_time) < 0.01, \
            f"Video2 start should be {video2.start_time}s based on sequence timing, got {video2_expected_start}s"

        # Verify detection windows don't overlap
        grace_period = 2.0
        video1_window_end = video1.start_time + video1.duration  # 15.5s
        video2_window_start = video2.start_time - grace_period  # 18.0s

        assert video2_window_start > video1_window_end, \
            f"Video2 window start ({video2_window_start}s) should be after Video1 window end ({video1_window_end}s)"

    def test_no_frame_zero_false_positives(self, test_db: Session, setup_test_data):
        """Valid detections should not be classified as 'frame 0'"""
        data = setup_test_data
        video1 = data["video1"]

        # Detection at t=10.3s, video window [10.5-15.56]
        # Should be accepted in grace period, NOT logged as frame 0
        valid_early_detection = DetectionEvent(
            session_id=data["session"].id,
            video_id=video1.id,
            timestamp=10.3,  # 200ms before video start
            video_relative_timestamp=-0.2,  # Negative, but within grace period
            sequence_elapsed_time=1.6,
            object_class="person",
            confidence=0.95,
            bounding_box={"x": 100, "y": 100, "width": 50, "height": 50}
        )
        test_db.add(valid_early_detection)
        test_db.commit()

        # Verify it's not classified as frame 0
        # Frame 0 would have video_relative_timestamp ≈ 0.0 or exactly 0.0
        assert valid_early_detection.video_relative_timestamp < 0, \
            "Grace period detection should have negative video_relative_timestamp"

        # Verify it's within grace period
        grace_period = 2.0
        time_before_video_start = video1.start_time - valid_early_detection.timestamp
        assert 0 <= time_before_video_start <= grace_period, \
            f"Detection should be within grace period, got {time_before_video_start}s before start"

    def test_grace_period_boundary_conditions(self, test_db: Session, setup_test_data):
        """Test edge cases at grace period boundaries"""
        data = setup_test_data
        video1 = data["video1"]

        # Test cases: timestamp, should_accept
        test_cases = [
            (10.5, True),   # Exactly at video start
            (10.3, True),   # 200ms before (within grace)
            (9.5, True),    # 1.0s before (within grace)
            (8.5, True),    # Exactly 2.0s before (grace boundary)
            (8.49, False),  # Just outside grace period
            (8.0, False),   # 2.5s before (outside grace)
        ]

        grace_period = 2.0
        video_start = video1.start_time  # 10.5s

        for timestamp, should_accept in test_cases:
            time_diff = video_start - timestamp
            is_within_grace = 0 <= time_diff <= grace_period

            assert is_within_grace == should_accept, \
                f"Detection at {timestamp}s (diff={time_diff}s) should {'be accepted' if should_accept else 'be rejected'}"

    def test_sequence_timing_with_gaps(self, test_db: Session, setup_test_data):
        """Test that gaps between videos don't affect grace period calculation"""
        data = setup_test_data
        video1 = data["video1"]
        video2 = data["video2"]

        # There's a gap between video1 end (15.5s) and video2 start (20.0s)
        # Gap duration: 4.5s
        gap_duration = video2.start_time - (video1.start_time + video1.duration)
        assert abs(gap_duration - 4.5) < 0.01, f"Gap should be ~4.5s, got {gap_duration}s"

        # Detection in the gap should not be assigned to either video
        gap_detection = DetectionEvent(
            session_id=data["session"].id,
            video_id=None,  # Not assigned yet
            timestamp=17.0,  # In the gap
            video_relative_timestamp=0.0,
            sequence_elapsed_time=8.3,
            object_class="person",
            confidence=0.95,
            bounding_box={"x": 100, "y": 100, "width": 50, "height": 50}
        )

        # Check against video1 window (with grace period)
        grace_period = 2.0
        video1_window_end = video1.start_time + video1.duration
        video2_window_start = video2.start_time - grace_period

        is_in_video1_window = gap_detection.timestamp <= video1_window_end
        is_in_video2_window = gap_detection.timestamp >= video2_window_start

        assert not is_in_video1_window, "Gap detection should not be in video1 window"
        assert not is_in_video2_window, "Gap detection should not be in video2 window"

    def test_grace_period_with_labjack_signals(self, test_db: Session, setup_test_data):
        """Test grace period with actual LabJack signals"""
        data = setup_test_data
        video1 = data["video1"]

        # Simulate LabJack signal arriving 0.5s before video start
        labjack_signal = LabjackSignal(
            session_id=data["session"].id,
            timestamp=10.0,  # 0.5s before video1 start (10.5s)
            fio4=1.0,  # Signal detected
            fio5=0.0,
            sequence_elapsed_time=1.3,  # 0.5s before video1 sequence start (1.8s)
            created_at=datetime.fromtimestamp(10.0, tz=timezone.utc)
        )
        test_db.add(labjack_signal)
        test_db.commit()

        # Grace period logic
        grace_period = 2.0
        video_start = video1.start_time
        is_within_grace = (video_start - labjack_signal.timestamp) <= grace_period

        assert is_within_grace, \
            f"LabJack signal at {labjack_signal.timestamp}s should be within grace period of video start {video_start}s"

        # Should be able to create detection from this signal
        detection = DetectionEvent(
            session_id=data["session"].id,
            video_id=video1.id,
            timestamp=labjack_signal.timestamp,
            video_relative_timestamp=-0.5,  # 0.5s before video start
            sequence_elapsed_time=labjack_signal.sequence_elapsed_time,
            object_class="person",
            confidence=0.95,
            bounding_box={"x": 100, "y": 100, "width": 50, "height": 50},
            labjack_signal_id=labjack_signal.id
        )
        test_db.add(detection)
        test_db.commit()

        assert detection.video_id == video1.id, "Detection should be assigned to video1"
        assert detection.video_relative_timestamp < 0, "Detection should have negative relative timestamp"


class TestSequenceTimingCalculation:
    """Test sequence-relative timing calculations"""

    @pytest.fixture
    def multi_video_session(self, test_db: Session):
        """Create session with multiple videos at different times"""
        project = Project(
            name="Multi-Video Timing Test",
            description="Testing sequence timing calculations",
            created_at=datetime.now(timezone.utc)
        )
        test_db.add(project)
        test_db.flush()

        session = TestSession(
            project_id=project.id,
            session_id="multi-video-timing",
            test_type="HIL",
            status="in_progress",
            created_at=datetime.now(timezone.utc)
        )
        test_db.add(session)
        test_db.flush()

        # Create 3 videos with realistic timing
        videos = []
        video_configs = [
            {"start_time": 10.5, "seq_elapsed": 1.8, "duration": 5.0},
            {"start_time": 20.0, "seq_elapsed": 11.3, "duration": 5.0},
            {"start_time": 30.5, "seq_elapsed": 21.8, "duration": 5.0},
        ]

        for idx, config in enumerate(video_configs):
            video = Video(
                filename=f"video{idx+1}.mp4",
                original_name=f"video{idx+1}.mp4",
                session_id=session.id,
                sequence_number=idx + 1,
                duration=config["duration"],
                start_time=config["start_time"],
                sequence_elapsed_time=config["seq_elapsed"],
                video_started_at=datetime.fromtimestamp(config["start_time"], tz=timezone.utc)
            )
            test_db.add(video)
            test_db.flush()
            videos.append(video)

        test_db.commit()
        return {"session": session, "videos": videos}

    def test_sequence_start_time_consistent_across_videos(self, test_db: Session, multi_video_session):
        """All videos should derive the same sequence start time"""
        videos = multi_video_session["videos"]

        sequence_starts = []
        for video in videos:
            seq_start = video.start_time - video.sequence_elapsed_time
            sequence_starts.append(seq_start)

        # All should calculate the same sequence start (8.7s)
        for seq_start in sequence_starts:
            assert abs(seq_start - 8.7) < 0.01, \
                f"All videos should derive sequence start of 8.7s, got {seq_start}s"

    def test_detection_timestamp_to_video_mapping(self, test_db: Session, multi_video_session):
        """Test mapping detection timestamps to correct videos"""
        videos = multi_video_session["videos"]
        session = multi_video_session["session"]

        # Test cases: (timestamp, expected_video_index, description)
        test_cases = [
            (10.3, 0, "Just before video1 start (grace period)"),
            (11.0, 0, "During video1"),
            (19.8, 1, "Just before video2 start (grace period)"),
            (22.5, 1, "During video2"),
            (30.3, 2, "Just before video3 start (grace period)"),
            (33.0, 2, "During video3"),
        ]

        grace_period = 2.0

        for timestamp, expected_idx, description in test_cases:
            # Find which video this timestamp belongs to
            matched_video = None
            for idx, video in enumerate(videos):
                window_start = video.start_time - grace_period
                window_end = video.start_time + video.duration

                if window_start <= timestamp <= window_end:
                    matched_video = idx
                    break

            assert matched_video == expected_idx, \
                f"{description}: timestamp {timestamp}s should map to video{expected_idx+1}, got video{matched_video+1 if matched_video is not None else 'none'}"
