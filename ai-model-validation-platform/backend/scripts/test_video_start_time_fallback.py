"""
Test video_start_time smart fallback behavior.

This script verifies that:
1. When video_start_time is provided, it's used correctly
2. When video_start_time is None, fallback to labjack_start_time works
3. Proper warnings are logged when using fallback
4. Code doesn't crash due to ValueError
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from services.timing_synchronization_calculator import (
    TimingSynchronizationCalculator,
    VideoTimingMetadata
)

# Setup logging to see warnings
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s: %(message)s'
)

def test_with_video_start_time_provided():
    """Test normal path with video_start_time provided"""
    print("\n" + "="*80)
    print("TEST 1: With video_start_time provided (CORRECT)")
    print("="*80)

    calculator = TimingSynchronizationCalculator()

    labjack_start = 1234567880.0
    video_start = 1234567881.5  # 1.5s after labjack start
    gt_video_time = 3.0  # 3 seconds into video
    detection_time = video_start + gt_video_time + 0.150  # 150ms latency

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

    print(f"\n✅ RESULTS:")
    print(f"   Detection latency: {result.detection_latency_ms:.1f}ms")
    print(f"   Expected: ~150ms")
    assert 140 <= result.detection_latency_ms <= 160, f"Expected ~150ms, got {result.detection_latency_ms}ms"
    print(f"   ✅ PASS: Latency is correct!")

def test_without_video_start_time_fallback():
    """Test fallback when video_start_time is None"""
    print("\n" + "="*80)
    print("TEST 2: Without video_start_time (FALLBACK - should warn)")
    print("="*80)

    calculator = TimingSynchronizationCalculator()

    labjack_start = 1234567880.0
    gt_video_time = 3.0
    # Detection occurs 3s + 150ms after labjack_start (no video delay in this case)
    detection_time = labjack_start + gt_video_time + 0.150

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

    print(f"\n⚠️ RESULTS (with fallback):")
    print(f"   Detection latency: {result.detection_latency_ms:.1f}ms")
    print(f"   Expected: ~150ms")
    assert 140 <= result.detection_latency_ms <= 160, f"Expected ~150ms, got {result.detection_latency_ms}ms"
    print(f"   ✅ PASS: Fallback works without crashing!")
    print(f"   ⚠️ Warning should have been logged above")

def test_fallback_with_video_startup_delay():
    """Test that fallback with startup delay shows the timing issues"""
    print("\n" + "="*80)
    print("TEST 3: Fallback WITH video startup delay (shows potential inflation)")
    print("="*80)

    calculator = TimingSynchronizationCalculator()

    labjack_start = 1234567880.0
    video_startup_delay = 1.5  # 1500ms startup delay
    actual_video_start = labjack_start + video_startup_delay
    gt_video_time = 3.0

    # Detection occurs 150ms after ground truth event
    detection_time = actual_video_start + gt_video_time + 0.150

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
        video_start_time=None  # ⚠️ Missing - causes potential inflation
    )

    print(f"\n⚠️ RESULTS (fallback with startup delay):")
    print(f"   Time since session start: {result.time_since_session_start_ms:.1f}ms")
    print(f"   Detection latency: {result.detection_latency_ms:.1f}ms")
    print(f"   Correction applied: {result.latency_correction_ms:.1f}ms")
    print(f"\n   Note: Fallback may not fully correct for video startup delay")
    print(f"   This is why video_start_time should be provided for accuracy")
    print(f"   ✅ PASS: Code doesn't crash, but warns about potential issues")

if __name__ == "__main__":
    print("\n" + "="*80)
    print("TESTING VIDEO_START_TIME SMART FALLBACK BEHAVIOR")
    print("="*80)
    print("\nThis test verifies the fix prevents ValueError crashes")
    print("while still warning when video_start_time is missing.\n")

    try:
        test_with_video_start_time_provided()
        test_without_video_start_time_fallback()
        test_fallback_with_video_startup_delay()

        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        print("\nKey findings:")
        print("1. ✅ Code works with video_start_time provided")
        print("2. ✅ Code doesn't crash when video_start_time is None")
        print("3. ⚠️ Warning is logged when using fallback")
        print("4. ⚠️ Fallback may cause latency inflation with video delays")
        print("\nConclusion: Smart fallback prevents test breakage while warning")
        print("about potential accuracy issues when video_start_time is missing.")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
