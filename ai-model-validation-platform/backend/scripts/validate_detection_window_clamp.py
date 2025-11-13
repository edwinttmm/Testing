#!/usr/bin/env python3
"""
Validation script for Detection Window Clamp Service
Runs basic tests to verify the implementation works correctly
"""

import sys
import os

# Add parent directory to path to import services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.detection_window_clamp_service import (
    DetectionWindowClampService,
    VideoTiming,
    ClampedWindow,
    clamp_video_windows,
    assign_detection
)


def test_no_overlap():
    """Test when videos have sufficient gaps (no clamping needed)"""
    print("\n=== Test 1: No Overlap Scenario ===")

    videos = [
        VideoTiming("video_1", 0, 100.0, 105.0, 5000, 0),
        VideoTiming("video_2", 1, 110.0, 115.0, 5000, 10000)  # 5s gap
    ]

    service = DetectionWindowClampService(grace_period_ms=2000)
    windows = service.clamp_detection_windows(videos)

    assert len(windows) == 2, f"Expected 2 windows, got {len(windows)}"

    # First video should have full grace period
    assert windows[0].video_id == "video_1"
    assert abs(windows[0].start_time - 98.0) < 0.01, f"Expected 98.0, got {windows[0].start_time}"
    assert not windows[0].is_clamped, "Window should not be clamped"

    # Second video should have full grace period
    assert windows[1].video_id == "video_2"
    assert abs(windows[1].start_time - 108.0) < 0.01, f"Expected 108.0, got {windows[1].start_time}"
    assert not windows[1].is_clamped, "Window should not be clamped"

    print("✅ PASS: No overlap scenario handled correctly")


def test_overlap_gap_splitting():
    """Test overlap detection and gap splitting"""
    print("\n=== Test 2: Overlap with Gap Splitting ===")

    videos = [
        VideoTiming("video_1", 0, 100.0, 105.0, 5000, 0),
        VideoTiming("video_2", 1, 105.5, 110.5, 5000, 5500),  # 500ms gap
        VideoTiming("video_3", 2, 111.0, 116.0, 5000, 11000)   # 500ms gap
    ]

    service = DetectionWindowClampService(grace_period_ms=2000)
    windows = service.clamp_detection_windows(videos)

    assert len(windows) == 3, f"Expected 3 windows, got {len(windows)}"

    # First video - no prior video, full grace start, but may have clamped end
    assert windows[0].video_id == "video_1"
    assert abs(windows[0].start_time - 98.0) < 0.01
    # Note: First window may be clamped if its end time was adjusted for next video

    # Second video - overlap with first, should be clamped
    assert windows[1].video_id == "video_2"
    assert windows[1].is_clamped, "Window should be clamped due to overlap"
    assert windows[1].overlap_detected, "Overlap should be detected"

    # Gap between video_1 START (100.0) and video_2 START (105.5) = 5.5s
    # Midpoint should be 100.0 + (5.5 / 2.0) = 102.75
    expected_midpoint = 102.75
    assert abs(windows[1].start_time - expected_midpoint) < 0.01, \
        f"Expected {expected_midpoint}, got {windows[1].start_time}"

    # Previous window should also be clamped to midpoint
    assert abs(windows[0].end_time - expected_midpoint) < 0.01, \
        f"Expected {expected_midpoint}, got {windows[0].end_time}"

    print("✅ PASS: Overlap gap splitting works correctly")


def test_detection_assignment():
    """Test detection assignment to videos"""
    print("\n=== Test 3: Detection Assignment ===")

    videos = [
        VideoTiming("video_1", 0, 100.0, 105.0, 5000, 0),
        VideoTiming("video_2", 1, 105.5, 110.5, 5000, 5500)
    ]

    service = DetectionWindowClampService(grace_period_ms=2000)
    windows = service.clamp_detection_windows(videos)

    # Detection at 100.5s - should match video_1
    result = service.assign_detection_to_video(100.5, windows)
    assert result is not None, "Detection should be assigned"
    video_id, reason = result
    assert video_id == "video_1", f"Expected video_1, got {video_id}"
    print(f"  Detection at 100.5s → {video_id} ({reason}) ✓")

    # Detection at 99.0s - in grace period of video_1
    result = service.assign_detection_to_video(99.0, windows)
    assert result is not None, "Detection should be assigned"
    video_id, reason = result
    assert video_id == "video_1", f"Expected video_1, got {video_id}"
    print(f"  Detection at 99.0s → {video_id} ({reason}) ✓")

    # Detection at 106.0s - should match video_2
    result = service.assign_detection_to_video(106.0, windows)
    assert result is not None, "Detection should be assigned"
    video_id, reason = result
    assert video_id == "video_2", f"Expected video_2, got {video_id}"
    print(f"  Detection at 106.0s → {video_id} ({reason}) ✓")

    # Detection way before first video
    result = service.assign_detection_to_video(50.0, windows)
    assert result is None, "Detection should not be assigned"
    print(f"  Detection at 50.0s → None (out of range) ✓")

    print("✅ PASS: Detection assignment works correctly")


def test_statistics():
    """Test window statistics"""
    print("\n=== Test 4: Window Statistics ===")

    videos = [
        VideoTiming("video_1", 0, 100.0, 105.0, 5000, 0),
        VideoTiming("video_2", 1, 105.5, 110.5, 5000, 5500),
        VideoTiming("video_3", 2, 111.0, 116.0, 5000, 11000)
    ]

    service = DetectionWindowClampService(grace_period_ms=2000)
    windows = service.clamp_detection_windows(videos)

    stats = service.get_window_statistics(windows)

    assert stats['total_windows'] == 3, f"Expected 3 windows, got {stats['total_windows']}"
    assert stats['clamped_windows'] >= 1, "At least one window should be clamped"
    assert stats['average_grace_period_ms'] > 0, "Average grace should be positive"

    print(f"  Total windows: {stats['total_windows']}")
    print(f"  Clamped windows: {stats['clamped_windows']}")
    print(f"  Overlap detections: {stats['overlap_detections']}")
    print(f"  Average grace: {stats['average_grace_period_ms']:.0f}ms")
    print(f"  Clamp percentage: {stats['clamp_percentage']:.1f}%")
    print("✅ PASS: Statistics calculation works correctly")


def test_convenience_functions():
    """Test convenience wrapper functions"""
    print("\n=== Test 5: Convenience Functions ===")

    videos = [
        VideoTiming("video_1", 0, 100.0, 105.0, 5000, 0),
        VideoTiming("video_2", 1, 105.5, 110.5, 5000, 5500)
    ]

    # Test clamp_video_windows function
    windows = clamp_video_windows(videos)
    assert len(windows) == 2, f"Expected 2 windows, got {len(windows)}"
    assert all(isinstance(w, ClampedWindow) for w in windows), "All should be ClampedWindow instances"
    print("  clamp_video_windows() ✓")

    # Test assign_detection function
    result = assign_detection(100.5, windows)
    assert result is not None, "Detection should be assigned"
    video_id, reason = result
    assert video_id == "video_1", f"Expected video_1, got {video_id}"
    print("  assign_detection() ✓")

    print("✅ PASS: Convenience functions work correctly")


def main():
    """Run all validation tests"""
    print("=" * 60)
    print("Detection Window Clamp Service - Validation Tests")
    print("=" * 60)

    try:
        test_no_overlap()
        test_overlap_gap_splitting()
        test_detection_assignment()
        test_statistics()
        test_convenience_functions()

        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED! Service is working correctly.")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
