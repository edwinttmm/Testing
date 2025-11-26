"""
Test for Bug #1 Fix: Latency Correction Calculation

This test verifies that the calculate_latency_correction() method
now correctly returns only the startup_delay_ms instead of adding
video position to the correction.

Bug Description:
- OLD BEHAVIOR: correction = (detection_time - video_start) - (detection_time - gt_time)
                           = 5.2s - 0.2s = 5.0s (video position!)
- NEW BEHAVIOR: correction = startup_delay_ms (e.g., 200ms)

Expected Results:
- Correction should equal startup_delay_ms (50-300ms typical)
- No more 5000-9000ms corrections
- Real latency should be 50-500ms for successful detections
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.timing_synchronization_calculator import (
    TimingSynchronizationCalculator,
    VideoTimingMetadata
)


def test_calculate_latency_correction_bug_fix():
    """Test that Bug #1 is fixed: correction equals startup_delay_ms only"""

    calc = TimingSynchronizationCalculator()

    # Test case: GT event at 5s, detection at 5.2s, startup delay 200ms
    detection_time = 1000.0 + 5.2
    gt_time = 1000.0 + 5.0
    video_start = 1000.0
    startup_delay = 200.0

    correction = calc.calculate_latency_correction(
        detection_system_time=detection_time,
        gt_system_time=gt_time,
        video_start_system_time=video_start,
        startup_delay_ms=startup_delay
    )

    # OLD BUGGY: Would return ~5000ms (video position)
    # NEW FIXED: Should return 200ms (startup delay only)
    assert abs(correction - startup_delay) < 0.1, \
        f"Expected correction={startup_delay}ms, got {correction}ms"

    print(f"✅ Bug #1 Fixed: correction={correction:.1f}ms equals startup_delay={startup_delay}ms")


def test_latency_correction_edge_cases():
    """Test edge cases for latency correction"""

    calc = TimingSynchronizationCalculator()

    test_cases = [
        (50.0, "Minimal startup delay"),
        (200.0, "Typical camera startup"),
        (300.0, "High startup delay"),
        (0.0, "Zero startup delay"),
    ]

    for startup, desc in test_cases:
        correction = calc.calculate_latency_correction(
            detection_system_time=1000.0,
            gt_system_time=999.0,
            video_start_system_time=995.0,
            startup_delay_ms=startup
        )

        assert abs(correction - startup) < 0.01, \
            f"{desc}: Expected {startup}ms, got {correction}ms"

        print(f"✅ {desc}: correction={correction:.1f}ms")


def test_end_to_end_latency_calculation():
    """Test full latency calculation with the fix applied"""

    calc = TimingSynchronizationCalculator()

    # Simulate a detection scenario
    session_id = "test_session"
    detection_id = "test_detection"

    # GT event at 5 seconds into video
    labjack_start_time = 1000.0
    video_start_time = 1000.0
    gt_video_time = 5.0

    # Detection happens 200ms after GT event
    detection_system_time = 1000.0 + 5.0 + 0.2

    # Video metadata
    video_metadata = VideoTimingMetadata(
        startup_delay_ms=200.0,
        fps=30.0,
        duration=10.0,
        timing_sync_status="synchronized"
    )

    # Calculate corrected latency
    result = calc.calculate_corrected_latency(
        session_id=session_id,
        detection_id=detection_id,
        detection_system_time=detection_system_time,
        ground_truth_frame=150,  # 5s * 30fps
        ground_truth_video_time=gt_video_time,
        video_timing_metadata=video_metadata,
        labjack_start_time=labjack_start_time,
        video_start_time=video_start_time
    )

    # Verify the results
    assert result is not None, "Result should not be None"

    # Correction should equal startup delay
    assert abs(result.latency_correction_ms - 200.0) < 1.0, \
        f"Correction should be ~200ms, got {result.latency_correction_ms:.1f}ms"

    # Real latency should be ~200ms (detection delay from GT event)
    assert 100 <= result.detection_latency_ms <= 300, \
        f"Detection latency should be 100-300ms, got {result.detection_latency_ms:.1f}ms"

    print(f"✅ End-to-end test passed:")
    print(f"   Time since session start: {result.time_since_session_start_ms:.1f}ms")
    print(f"   Detection latency: {result.detection_latency_ms:.1f}ms")
    print(f"   Correction: {result.latency_correction_ms:.1f}ms")
    print(f"   Camera-only latency: {result.camera_only_latency_ms:.1f}ms")


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Bug #1 Fix: Latency Correction Calculation")
    print("=" * 70)
    print()

    try:
        test_calculate_latency_correction_bug_fix()
        print()

        test_latency_correction_edge_cases()
        print()

        test_end_to_end_latency_calculation()
        print()

        print("=" * 70)
        print("🎉 ALL TESTS PASSED! Bug #1 is fully fixed.")
        print("=" * 70)
        print()
        print("Key improvements:")
        print("  ✓ Correction = startup_delay_ms only (not video position)")
        print("  ✓ Typical range: 50-300ms (realistic camera initialization)")
        print("  ✓ No more 5000-9000ms corrections")
        print("  ✓ Detection latency properly calculated")

    except AssertionError as e:
        print()
        print("=" * 70)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 70)
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ ERROR: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)
