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

Original location: tests/test_negative_latency_fix.py
"""

"""
Test to verify the negative latency bug fix.

This test demonstrates that the corrected formula now produces positive latency values
by correctly treating startup_delay_ms as a pre-video buffering time, not an offset to add.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.timing_synchronization_calculator import (
    TimingSynchronizationCalculator,
    VideoTimingMetadata
)


def test_negative_latency_fix():
    """
    Test with the exact data from the user's bug report:
    - labjack_start_time = 1762191668.446283
    - detection at 1762191668.642227
    - GT at video time 0.041666s (frame 1 at 24fps)
    - startup_delay_ms = 1733ms

    BEFORE FIX:
    - video_start_system_time = 1762191668.446283 + 1.733 = 1762191670.179283
    - gt_system_time = 1762191670.179283 + 0.041666 = 1762191670.220949
    - real_latency = 1762191668.642227 - 1762191670.220949 = -1578.722ms (NEGATIVE!)

    AFTER FIX:
    - video_start_system_time = 1762191668.446283 (same as labjack)
    - gt_system_time = 1762191668.446283 + 0.041666 = 1762191668.487949
    - real_latency = 1762191668.642227 - 1762191668.487949 = 154.278ms (POSITIVE!)
    """

    calculator = TimingSynchronizationCalculator()

    # Test data from user's bug report
    labjack_start_time = 1762191668.446283
    detection_system_time = 1762191668.642227
    ground_truth_video_time = 0.041666  # ~1 frame at 24fps
    ground_truth_frame = 1
    startup_delay_ms = 1733.0

    # Create video timing metadata
    video_timing = VideoTimingMetadata(
        startup_delay_ms=startup_delay_ms,
        fps=24.0,
        duration=10.0,
        timing_sync_status="synchronized",
        timing_accuracy_ns=1000000  # 1ms accuracy
    )

    print("\n" + "="*80)
    print("NEGATIVE LATENCY BUG FIX VERIFICATION")
    print("="*80)
    print("\nTest Data:")
    print(f"  LabJack start time:     {labjack_start_time}")
    print(f"  Detection system time:  {detection_system_time}")
    print(f"  Ground truth video time: {ground_truth_video_time}s (frame {ground_truth_frame})")
    print(f"  Startup delay:          {startup_delay_ms}ms")
    print()

    # Calculate with CORRECTED formula
    result = calculator.calculate_corrected_latency(
        session_id="test_negative_latency_fix",
        detection_id="detection_001",
        detection_system_time=detection_system_time,
        ground_truth_frame=ground_truth_frame,
        ground_truth_video_time=ground_truth_video_time,
        video_timing_metadata=video_timing,
        labjack_start_time=labjack_start_time
    )

    print("\n" + "-"*80)
    print("CALCULATION RESULTS (with FIX):")
    print("-"*80)
    print(f"  Video start system time: {labjack_start_time} (= labjack_start_time)")
    print(f"  GT system time:          {labjack_start_time + ground_truth_video_time}")
    print(f"  Real latency:            {result.real_latency_ms:.3f}ms")
    print(f"  Apparent latency:        {result.apparent_latency_ms:.3f}ms")
    print(f"  Latency correction:      {result.latency_correction_ms:.3f}ms")
    print()

    # Manual verification
    expected_gt_system_time = labjack_start_time + ground_truth_video_time
    expected_real_latency_ms = (detection_system_time - expected_gt_system_time) * 1000.0

    print(f"  Expected real latency:   {expected_real_latency_ms:.3f}ms")
    print()

    # Verify fix
    print("="*80)
    print("VERIFICATION:")
    print("="*80)

    if result.real_latency_ms > 0:
        print(f"  ✅ PASS: Real latency is POSITIVE ({result.real_latency_ms:.3f}ms)")
    else:
        print(f"  ❌ FAIL: Real latency is still NEGATIVE ({result.real_latency_ms:.3f}ms)")

    if abs(result.real_latency_ms - expected_real_latency_ms) < 1.0:
        print(f"  ✅ PASS: Calculated latency matches expected value")
    else:
        print(f"  ❌ FAIL: Calculated latency differs from expected")
        print(f"         Expected: {expected_real_latency_ms:.3f}ms")
        print(f"         Got:      {result.real_latency_ms:.3f}ms")

    # Verify reasonable latency range (50-500ms for typical detection)
    if 50 <= result.real_latency_ms <= 500:
        print(f"  ✅ PASS: Latency is in reasonable range (50-500ms)")
    else:
        print(f"  ⚠️  WARNING: Latency outside typical range: {result.real_latency_ms:.3f}ms")

    print()
    print("="*80)
    print("EXPLANATION OF FIX:")
    print("="*80)
    print("""
The bug was in line 164 of timing_synchronization_calculator.py:

BEFORE (INCORRECT):
    video_start_system_time = labjack_start_time + (startup_delay_ms / 1000.0)

This formula ADDED the startup delay, which caused:
- Ground truth events to be calculated too late in system time
- Detections to appear BEFORE ground truth events
- Negative latency values (impossible!)

AFTER (CORRECT):
    video_start_system_time = labjack_start_time

Why this is correct:
- labjack_start_time: System time when monitoring begins (Unix epoch)
- startup_delay_ms: Buffering time before first frame appears
- Both timestamps are in the SAME epoch (system time)
- The video timeline (ground_truth_video_time) starts from t=0 at the same
  moment as labjack_start_time, regardless of buffering delay
- The buffering delay is already reflected in when detections arrive

Real latency calculation:
    real_latency = detection_system_time - (video_start_system_time + gt_video_time)
                 = detection_system_time - (labjack_start_time + gt_video_time)

With example data:
    real_latency = 1762191668.642227 - (1762191668.446283 + 0.041666)
                 = 1762191668.642227 - 1762191668.487949
                 = 0.154278 seconds
                 = 154.278ms ✅ POSITIVE!
""")
    print("="*80)

    assert result.real_latency_ms > 0, "Real latency must be positive!"
    assert abs(result.real_latency_ms - expected_real_latency_ms) < 1.0, "Latency calculation mismatch!"

    print("\n✅ ALL TESTS PASSED! Negative latency bug is FIXED.\n")

    return result


if __name__ == "__main__":
    test_negative_latency_fix()
