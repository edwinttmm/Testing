"""
Test video_start_time smart fallback behavior.

This test verifies that:
1. When video_start_time is provided, it's used correctly
2. When video_start_time is None, fallback to labjack_start_time works
3. Proper warnings are logged when using fallback
4. Tests don't crash due to ValueError
"""

import pytest
import logging
from services.timing_synchronization_calculator import (
    TimingSynchronizationCalculator,
    VideoTimingMetadata
)


class TestVideoStartTimeFallback:
    """Test smart fallback behavior for missing video_start_time"""

    def test_with_video_start_time_provided(self, caplog):
        """Test normal path with video_start_time provided"""
        calculator = TimingSynchronizationCalculator()

        labjack_start = 1234567880.0
        video_start = 1234567881.5  # 1.5s after labjack start
        gt_video_time = 3.0  # 3 seconds into video
        detection_time = video_start + gt_video_time + 0.150  # 150ms latency

        with caplog.at_level(logging.DEBUG):
            result = calculator.calculate_corrected_latency(
                session_id="test_session",
                detection_id="test_det_001",
                detection_system_time=detection_time,
                ground_truth_frame=90,
                ground_truth_video_time=gt_video_time,
                video_timing_metadata=VideoTimingMetadata(
                    startup_delay_ms=1500.0,
                    fps=30.0,
                    duration=10.0,
                    timing_sync_status="synced"
                ),
                labjack_start_time=labjack_start,
                video_start_time=video_start  # ✅ Provided
            )

        # Verify no warnings
        assert not any("⚠️" in record.message for record in caplog.records)

        # Verify correct latency (should be ~150ms)
        assert 140 <= result.real_latency_ms <= 160, f"Expected ~150ms, got {result.real_latency_ms}ms"
        print(f"✅ With video_start_time: {result.real_latency_ms:.1f}ms latency")

    def test_without_video_start_time_fallback(self, caplog):
        """Test fallback when video_start_time is None"""
        calculator = TimingSynchronizationCalculator()

        labjack_start = 1234567880.0
        gt_video_time = 3.0
        # Detection occurs 3s + 150ms after labjack_start (no video delay in this case)
        detection_time = labjack_start + gt_video_time + 0.150

        with caplog.at_level(logging.WARNING):
            result = calculator.calculate_corrected_latency(
                session_id="test_session",
                detection_id="test_det_002",
                detection_system_time=detection_time,
                ground_truth_frame=90,
                ground_truth_video_time=gt_video_time,
                video_timing_metadata=VideoTimingMetadata(
                    startup_delay_ms=0.0,  # No startup delay
                    fps=30.0,
                    duration=10.0,
                    timing_sync_status="synced"
                ),
                labjack_start_time=labjack_start,
                video_start_time=None  # ⚠️ Not provided - triggers fallback
            )

        # Verify warning was logged
        warnings = [r for r in caplog.records if "⚠️" in r.message]
        assert len(warnings) > 0, "Should log warning when using fallback"
        assert "labjack_start_time" in warnings[0].message.lower()

        # Verify latency is still calculated (should be ~150ms)
        assert 140 <= result.real_latency_ms <= 160, f"Expected ~150ms, got {result.real_latency_ms}ms"
        print(f"⚠️ Without video_start_time (fallback): {result.real_latency_ms:.1f}ms latency")
        print(f"   Warning logged: {warnings[0].message[:80]}...")

    def test_fallback_with_video_startup_delay_shows_inflation(self, caplog):
        """Test that fallback causes latency inflation when video has startup delay"""
        calculator = TimingSynchronizationCalculator()

        labjack_start = 1234567880.0
        video_startup_delay = 1.5  # 1500ms startup delay
        actual_video_start = labjack_start + video_startup_delay
        gt_video_time = 3.0

        # Detection occurs 150ms after ground truth event
        detection_time = actual_video_start + gt_video_time + 0.150

        with caplog.at_level(logging.WARNING):
            result = calculator.calculate_corrected_latency(
                session_id="test_session",
                detection_id="test_det_003",
                detection_system_time=detection_time,
                ground_truth_frame=90,
                ground_truth_video_time=gt_video_time,
                video_timing_metadata=VideoTimingMetadata(
                    startup_delay_ms=1500.0,
                    fps=30.0,
                    duration=10.0,
                    timing_sync_status="synced"
                ),
                labjack_start_time=labjack_start,
                video_start_time=None  # ⚠️ Missing - causes inflation
            )

        # Verify warning
        warnings = [r for r in caplog.records if "⚠️" in r.message]
        assert len(warnings) > 0

        # With fallback, apparent_latency will include startup delay
        # Real latency calculation will try to correct but may not be perfect
        print(f"⚠️ With startup delay + fallback:")
        print(f"   Apparent latency: {result.apparent_latency_ms:.1f}ms (includes startup delay)")
        print(f"   Real latency: {result.real_latency_ms:.1f}ms (attempted correction)")
        print(f"   Expected: ~150ms, but fallback may cause inflation")

        # Real latency should still try to correct, but warn about potential issues
        assert result.apparent_latency_ms > result.real_latency_ms, \
            "Correction should reduce apparent latency"


if __name__ == "__main__":
    print("Testing video_start_time smart fallback behavior...\n")
    pytest.main([__file__, "-v", "-s"])
