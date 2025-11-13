"""
Tests for Detection Window Clamp Service

Validates the clamping algorithm and detection assignment logic.
"""

import pytest
from services.detection_window_clamp_service import (
    DetectionWindowClampService,
    VideoTiming,
    ClampedWindow,
    get_detection_window_clamp_service,
    clamp_video_windows,
    assign_detection
)


@pytest.fixture
def clamp_service():
    """Create a fresh clamp service for testing"""
    return DetectionWindowClampService(grace_period_ms=2000)


@pytest.fixture
def sample_video_timings():
    """Create sample video timings for testing"""
    return [
        VideoTiming(
            video_id="video_1",
            sequence_position=0,
            start_time=100.0,
            end_time=105.0,
            duration_ms=5000,
            video_play_offset_ms=0
        ),
        VideoTiming(
            video_id="video_2",
            sequence_position=1,
            start_time=105.5,  # 500ms gap
            end_time=110.5,
            duration_ms=5000,
            video_play_offset_ms=5500
        ),
        VideoTiming(
            video_id="video_3",
            sequence_position=2,
            start_time=111.0,  # 500ms gap
            end_time=None,  # Ongoing
            duration_ms=5000,
            video_play_offset_ms=11000
        )
    ]


class TestWindowClamping:
    """Test window clamping algorithm"""

    def test_no_overlap_scenario(self, clamp_service):
        """Test when videos have sufficient gaps (no clamping needed)"""
        # Videos with 5 second gaps - no overlap
        videos = [
            VideoTiming("v1", 0, 100.0, 105.0, 5000, 0),
            VideoTiming("v2", 1, 110.0, 115.0, 5000, 10000)  # 5s gap
        ]

        windows = clamp_service.clamp_detection_windows(videos)

        assert len(windows) == 2

        # First video should have full grace period
        assert windows[0].video_id == "v1"
        assert windows[0].start_time == 98.0  # 100 - 2s grace
        assert windows[0].is_clamped == False
        assert windows[0].grace_period_applied_ms == 2000

        # Second video should have full grace period
        assert windows[1].video_id == "v2"
        assert windows[1].start_time == 108.0  # 110 - 2s grace
        assert windows[1].is_clamped == False
        assert windows[1].grace_period_applied_ms == 2000

    def test_overlap_scenario_gap_splitting(self, clamp_service, sample_video_timings):
        """Test overlap detection and gap splitting"""
        windows = clamp_service.clamp_detection_windows(sample_video_timings)

        assert len(windows) == 3

        # First video - no prior video, full grace
        assert windows[0].video_id == "video_1"
        assert windows[0].start_time == 98.0  # 100 - 2s
        assert windows[0].is_clamped == False

        # Second video - overlap with first, should be clamped
        assert windows[1].video_id == "video_2"
        assert windows[1].is_clamped == True
        assert windows[1].overlap_detected == True

        # Gap between video_1 end (105.0) and video_2 start (105.5) = 0.5s
        # Midpoint should be 105.0 + 0.25 = 105.25
        expected_midpoint = 105.25
        assert abs(windows[1].start_time - expected_midpoint) < 0.01

        # Previous window should also be clamped to midpoint
        assert abs(windows[0].end_time - expected_midpoint) < 0.01

    def test_zero_gap_handling(self, clamp_service):
        """Test handling of videos with zero or negative gaps"""
        videos = [
            VideoTiming("v1", 0, 100.0, 105.0, 5000, 0),
            VideoTiming("v2", 1, 105.0, 110.0, 5000, 5000)  # Zero gap
        ]

        windows = clamp_service.clamp_detection_windows(videos)

        assert len(windows) == 2
        assert windows[1].is_clamped == True
        # Should use minimal separation (100ms)
        assert windows[1].start_time >= windows[0].end_time


class TestDetectionAssignment:
    """Test detection assignment to videos"""

    def test_exact_window_match(self, clamp_service, sample_video_timings):
        """Test detection falling cleanly within one window"""
        windows = clamp_service.clamp_detection_windows(sample_video_timings)

        # Detection at 100.5s - should match video_1
        result = clamp_service.assign_detection_to_video(100.5, windows)

        assert result is not None
        video_id, reason = result
        assert video_id == "video_1"
        assert "exact_window_match" in reason

    def test_grace_period_detection(self, clamp_service, sample_video_timings):
        """Test detection in grace period before video start"""
        windows = clamp_service.clamp_detection_windows(sample_video_timings)

        # Detection at 99.0s - in grace period of video_1 (starts at 100.0)
        result = clamp_service.assign_detection_to_video(99.0, windows)

        assert result is not None
        video_id, reason = result
        assert video_id == "video_1"

    def test_transition_zone_detection(self, clamp_service, sample_video_timings):
        """Test detection in transition zone between videos"""
        windows = clamp_service.clamp_detection_windows(sample_video_timings)

        # Detection at 105.25s - right at the clamped boundary
        # Should be assigned deterministically (not to both)
        result = clamp_service.assign_detection_to_video(105.25, windows)

        assert result is not None
        video_id, reason = result
        # Should match one video (deterministic assignment)
        assert video_id in ["video_1", "video_2"]

    def test_no_match_detection(self, clamp_service, sample_video_timings):
        """Test detection outside all windows"""
        windows = clamp_service.clamp_detection_windows(sample_video_timings)

        # Detection way before first video
        result = clamp_service.assign_detection_to_video(50.0, windows)

        assert result is None


class TestConvenienceFunctions:
    """Test convenience wrapper functions"""

    def test_clamp_video_windows_function(self, sample_video_timings):
        """Test global clamp_video_windows function"""
        windows = clamp_video_windows(sample_video_timings)

        assert len(windows) == 3
        assert all(isinstance(w, ClampedWindow) for w in windows)

    def test_assign_detection_function(self, sample_video_timings):
        """Test global assign_detection function"""
        windows = clamp_video_windows(sample_video_timings)

        result = assign_detection(100.5, windows)

        assert result is not None
        video_id, reason = result
        assert video_id == "video_1"


class TestStatistics:
    """Test window statistics"""

    def test_statistics_generation(self, clamp_service, sample_video_timings):
        """Test statistics calculation"""
        windows = clamp_service.clamp_detection_windows(sample_video_timings)

        stats = clamp_service.get_window_statistics(windows)

        assert stats['total_windows'] == 3
        assert stats['clamped_windows'] >= 1  # At least one clamped
        assert stats['average_grace_period_ms'] > 0
        assert stats['min_grace_period_ms'] <= stats['max_grace_period_ms']

    def test_empty_statistics(self, clamp_service):
        """Test statistics with no windows"""
        stats = clamp_service.get_window_statistics([])

        assert stats['total_windows'] == 0
        assert stats['clamped_windows'] == 0


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_single_video(self, clamp_service):
        """Test clamping with single video"""
        videos = [VideoTiming("v1", 0, 100.0, 105.0, 5000, 0)]

        windows = clamp_service.clamp_detection_windows(videos)

        assert len(windows) == 1
        assert windows[0].is_clamped == False
        assert windows[0].grace_period_applied_ms == 2000

    def test_empty_video_list(self, clamp_service):
        """Test clamping with no videos"""
        windows = clamp_service.clamp_detection_windows([])

        assert len(windows) == 0

    def test_custom_grace_period(self):
        """Test custom grace period"""
        service = DetectionWindowClampService(grace_period_ms=1000)

        videos = [VideoTiming("v1", 0, 100.0, 105.0, 5000, 0)]
        windows = service.clamp_detection_windows(videos)

        assert windows[0].grace_period_applied_ms == 1000
        assert windows[0].start_time == 99.0  # 100 - 1s
