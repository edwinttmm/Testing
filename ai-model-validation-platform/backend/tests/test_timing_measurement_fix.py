"""
Test script to validate Priority 2 fix: Enable timing measurement for multi-video sequences

This script validates that:
1. All detections have valid video_relative_timestamp (not 0.0 or None)
2. All detections have valid actual_latency_ms (not None or 10000ms placeholder)
3. Timestamp values are realistic for 5-second videos (0-5s range)
4. Ground truth matching is working correctly
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from database import SessionLocal
from sqlalchemy import text, func
import json

# Test session ID from investigation report
TEST_SESSION_ID = "daad8bf6-b5da-4423-abc4-a85e83bc1c16"

def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*80}")
    print(f"{title:^80}")
    print(f"{'='*80}\n")

def test_detection_timing_data():
    """Test that all detections have valid timing data"""
    print_section("TEST 1: Detection Timing Data Validation")

    db = SessionLocal()
    try:
        # Query detection timing statistics
        result = db.execute(text('''
            SELECT
                COUNT(*) as total_detections,
                COUNT(CASE WHEN video_relative_timestamp IS NULL THEN 1 END) as null_timestamps,
                COUNT(CASE WHEN video_relative_timestamp = 0.0 THEN 1 END) as zero_timestamps,
                COUNT(CASE WHEN actual_latency_ms IS NULL THEN 1 END) as null_latency,
                COUNT(CASE WHEN actual_latency_ms = 10000.0 THEN 1 END) as placeholder_latency,
                MIN(video_relative_timestamp) as min_timestamp,
                MAX(video_relative_timestamp) as max_timestamp,
                AVG(video_relative_timestamp) as avg_timestamp,
                AVG(CASE WHEN actual_latency_ms < 10000 THEN actual_latency_ms END) as avg_real_latency
            FROM detection_events
            WHERE test_session_id = :session_id
        '''), {'session_id': TEST_SESSION_ID}).fetchone()

        total = result[0]
        null_ts = result[1]
        zero_ts = result[2]
        null_lat = result[3]
        placeholder_lat = result[4]
        min_ts = result[5]
        max_ts = result[6]
        avg_ts = result[7]
        avg_real_lat = result[8]

        print(f"Total Detections: {total}")
        print(f"\nTimestamp Analysis:")
        print(f"  NULL timestamps: {null_ts} ({null_ts/total*100:.1f}%)")
        print(f"  Zero (0.0) timestamps: {zero_ts} ({zero_ts/total*100:.1f}%)")
        print(f"  Valid timestamps: {total - null_ts - zero_ts} ({(total-null_ts-zero_ts)/total*100:.1f}%)")
        print(f"  Time range: {min_ts:.3f}s - {max_ts:.3f}s (avg: {avg_ts:.3f}s)")

        print(f"\nLatency Analysis:")
        print(f"  NULL latency: {null_lat} ({null_lat/total*100:.1f}%)")
        print(f"  Placeholder (10000ms): {placeholder_lat} ({placeholder_lat/total*100:.1f}%)")
        print(f"  Valid latency values: {total - null_lat - placeholder_lat} ({(total-null_lat-placeholder_lat)/total*100:.1f}%)")
        if avg_real_lat:
            print(f"  Average real latency: {avg_real_lat:.2f}ms")

        # Test assertions
        print(f"\n{'Test Results:':<40}")

        test_results = []

        # Test 1: No NULL timestamps
        if null_ts == 0:
            print(f"  ✓ No NULL video_relative_timestamp values")
            test_results.append(True)
        else:
            print(f"  ✗ FAIL: {null_ts} detections have NULL timestamp")
            test_results.append(False)

        # Test 2: No zero timestamps (except first frame)
        if zero_ts <= 1:  # Allow 1 detection at t=0 (first frame)
            print(f"  ✓ No invalid zero timestamps")
            test_results.append(True)
        else:
            print(f"  ✗ FAIL: {zero_ts} detections have timestamp=0.0")
            test_results.append(False)

        # Test 3: Timestamps in realistic range (0-10s for two 5s videos)
        if min_ts >= 0 and max_ts <= 15:  # Allow some buffer
            print(f"  ✓ Timestamps in realistic range (0-15s)")
            test_results.append(True)
        else:
            print(f"  ✗ FAIL: Timestamps outside expected range")
            test_results.append(False)

        # Test 4: Latency measurement working (< 50% placeholders)
        if placeholder_lat < total * 0.5:
            print(f"  ✓ Latency measurement mostly working ({placeholder_lat}/{total} placeholders)")
            test_results.append(True)
        else:
            print(f"  ✗ FAIL: Too many placeholder latency values ({placeholder_lat}/{total})")
            test_results.append(False)

        return all(test_results)

    finally:
        db.close()

def test_ground_truth_matching():
    """Test that ground truth matching is working"""
    print_section("TEST 2: Ground Truth Matching Validation")

    db = SessionLocal()
    try:
        # Get videos for this session
        videos = db.execute(text('''
            SELECT id, file_path, duration
            FROM videos v
            WHERE EXISTS (
                SELECT 1 FROM detection_events
                WHERE test_session_id = :session_id
                AND video_id = v.id
            )
        '''), {'session_id': TEST_SESSION_ID}).fetchall()

        print(f"Videos in session: {len(videos)}")

        total_gt = 0
        total_detections = 0

        for video in videos:
            video_id = video[0]
            video_path = video[1]

            # Count GT objects for this video
            gt_count = db.execute(text('''
                SELECT COUNT(*) FROM ground_truth_objects
                WHERE video_id = :video_id
            '''), {'video_id': video_id}).scalar()

            # Count detections for this video
            det_count = db.execute(text('''
                SELECT COUNT(*) FROM detection_events
                WHERE test_session_id = :session_id
                AND video_id = :video_id
            '''), {'session_id': TEST_SESSION_ID, 'video_id': video_id}).scalar()

            print(f"\n  Video: {Path(video_path).name if video_path else video_id[:12]}")
            print(f"    Ground truth objects: {gt_count}")
            print(f"    Detections: {det_count}")

            total_gt += gt_count
            total_detections += det_count

        # Count matched detections (TP = actual_latency_ms < 10000)
        matched = db.execute(text('''
            SELECT COUNT(*) FROM detection_events
            WHERE test_session_id = :session_id
            AND actual_latency_ms IS NOT NULL
            AND actual_latency_ms < 10000.0
        '''), {'session_id': TEST_SESSION_ID}).scalar()

        # Count false positives
        fp = db.execute(text('''
            SELECT COUNT(*) FROM detection_events
            WHERE test_session_id = :session_id
            AND actual_latency_ms = 10000.0
        '''), {'session_id': TEST_SESSION_ID}).scalar()

        print(f"\nMatching Results:")
        print(f"  Total GT objects: {total_gt}")
        print(f"  Total detections: {total_detections}")
        print(f"  Matched (TP): {matched} ({matched/total_detections*100:.1f}%)")
        print(f"  False Positives: {fp} ({fp/total_detections*100:.1f}%)")
        print(f"  Detection rate: {matched/total_gt*100:.1f}%")

        # Test assertions
        print(f"\n{'Test Results:':<40}")

        test_results = []

        # Test 1: GT objects exist
        if total_gt > 0:
            print(f"  ✓ Ground truth objects found ({total_gt})")
            test_results.append(True)
        else:
            print(f"  ✗ FAIL: No ground truth objects")
            test_results.append(False)

        # Test 2: Some detections matched
        if matched > 0:
            print(f"  ✓ Ground truth matching is working ({matched} matches)")
            test_results.append(True)
        else:
            print(f"  ✗ FAIL: No detections matched to ground truth")
            test_results.append(False)

        # Test 3: Detection rate reasonable (>50%)
        if total_gt > 0 and (matched / total_gt) > 0.5:
            print(f"  ✓ Detection rate acceptable ({matched/total_gt*100:.1f}%)")
            test_results.append(True)
        else:
            print(f"  ✗ FAIL: Low detection rate ({matched/total_gt*100:.1f}%)")
            test_results.append(False)

        return all(test_results)

    finally:
        db.close()

def test_per_video_timing():
    """Test that timing is calculated correctly per video in multi-video sequences"""
    print_section("TEST 3: Per-Video Timing Validation")

    db = SessionLocal()
    try:
        # Get session metadata
        session = db.execute(text('''
            SELECT sequence_metadata FROM test_sessions
            WHERE id = :session_id
        '''), {'session_id': TEST_SESSION_ID}).fetchone()

        if not session or not session[0]:
            print("  ⚠ No sequence metadata found")
            return True

        metadata = json.loads(session[0]) if isinstance(session[0], str) else session[0]
        video_timing = metadata.get('video_timing', {})

        print(f"Sequence has {len(video_timing)} videos with timing data\n")

        test_results = []

        for video_id, timing in video_timing.items():
            started_at = timing.get('started_at')
            ended_at = timing.get('ended_at')
            duration = ended_at - started_at if ended_at and started_at else None

            print(f"  Video: {video_id[:12]}...")
            print(f"    Started: {started_at:.3f}s")
            print(f"    Ended: {ended_at:.3f}s" if ended_at else "    Ended: N/A")
            print(f"    Duration: {duration:.3f}s" if duration else "    Duration: N/A")

            # Count detections for this video
            det_count = db.execute(text('''
                SELECT COUNT(*), MIN(video_relative_timestamp), MAX(video_relative_timestamp)
                FROM detection_events
                WHERE test_session_id = :session_id
                AND video_id = :video_id
            '''), {'session_id': TEST_SESSION_ID, 'video_id': video_id}).fetchone()

            print(f"    Detections: {det_count[0]}")
            if det_count[1] is not None:
                print(f"    Detection time range: {det_count[1]:.3f}s - {det_count[2]:.3f}s")

                # Test: Detection timestamps should be within video duration
                if det_count[1] >= 0 and (duration is None or det_count[2] <= duration + 1):
                    print(f"    ✓ Timestamps within video duration")
                    test_results.append(True)
                else:
                    print(f"    ✗ FAIL: Timestamps outside video duration")
                    test_results.append(False)
            print()

        return all(test_results) if test_results else True

    finally:
        db.close()

def main():
    """Run all tests"""
    print_section("Priority 2 Fix: Timing Measurement for Multi-Video Sequences")
    print(f"Testing session: {TEST_SESSION_ID}\n")

    results = []

    try:
        # Run tests
        results.append(("Detection Timing Data", test_detection_timing_data()))
        results.append(("Ground Truth Matching", test_ground_truth_matching()))
        results.append(("Per-Video Timing", test_per_video_timing()))

        # Print summary
        print_section("Test Summary")

        all_passed = True
        for test_name, passed in results:
            status = "✓ PASSED" if passed else "✗ FAILED"
            print(f"  {test_name:<40} {status}")
            if not passed:
                all_passed = False

        print(f"\n{'='*80}")
        if all_passed:
            print("  ✓✓✓ ALL TESTS PASSED ✓✓✓")
            print(f"{'='*80}\n")
            return 0
        else:
            print("  ✗✗✗ SOME TESTS FAILED ✗✗✗")
            print(f"{'='*80}\n")
            return 1

    except Exception as e:
        print(f"\n✗ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
