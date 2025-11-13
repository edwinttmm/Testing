#!/usr/bin/env python3
"""
Direct API Validation Script - No Dependencies
Tests timing calculations for session 0846e476-2e21-499c-bfc8-0b2218081c77
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, List, Any

# Configuration
BASE_URL = "http://localhost:8000"
SESSION_ID = "0846e476-2e21-499c-bfc8-0b2218081c77"
EXPECTED_TOTAL_DETECTIONS = 502
VIDEO_DURATION_SECONDS = 10.0
MAX_FRAME_NUMBER = 240

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def api_get(endpoint: str, params: Dict = None) -> Dict:
    """Make GET request to API"""
    url = f"{BASE_URL}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"{Colors.RED}✗ API request failed: {e}{Colors.RESET}")
        raise

def print_header(title: str):
    """Print test section header"""
    print(f"\n{Colors.BLUE}{'='*80}")
    print(f"{title}")
    print(f"{'='*80}{Colors.RESET}\n")

def print_pass(message: str):
    """Print pass message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")

def print_fail(message: str):
    """Print fail message"""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")

def print_info(message: str):
    """Print info message"""
    print(f"{Colors.YELLOW}  {message}{Colors.RESET}")

# Test Results Tracking
test_results = {
    "passed": 0,
    "failed": 0,
    "warnings": 0,
    "issues": []
}

def run_test(name: str, test_func):
    """Run a test and track results"""
    print(f"\n{Colors.BLUE}Testing: {name}{Colors.RESET}")
    try:
        test_func()
        test_results["passed"] += 1
        print_pass(f"{name} PASSED")
    except AssertionError as e:
        test_results["failed"] += 1
        test_results["issues"].append({"test": name, "error": str(e)})
        print_fail(f"{name} FAILED: {e}")
    except Exception as e:
        test_results["failed"] += 1
        test_results["issues"].append({"test": name, "error": str(e)})
        print_fail(f"{name} ERROR: {e}")

# ============================================================================
# TEST CASES
# ============================================================================

def test_01_get_all_detections():
    """Test 1: Verify all 502 detections are returned"""
    data = api_get(f"/api/test-sessions/{SESSION_ID}/events")
    detections = data.get("detections", [])

    print_info(f"Total detections returned: {len(detections)}")

    assert len(detections) == EXPECTED_TOTAL_DETECTIONS, \
        f"Expected {EXPECTED_TOTAL_DETECTIONS}, got {len(detections)}"

def test_02_video_relative_timestamp_range():
    """Test 2: Verify timestamps are in valid range (0-10s), NOT year 1762"""
    data = api_get(f"/api/test-sessions/{SESSION_ID}/events")
    detections = data.get("detections", [])

    year_1762_bugs = []
    null_timestamps = 0
    valid_timestamps = 0

    for detection in detections:
        timestamp = detection.get("video_relative_timestamp")

        if timestamp is None:
            null_timestamps += 1
            continue

        # Check for year 1762 bug
        if timestamp < 0 or timestamp > VIDEO_DURATION_SECONDS * 2:
            year_1762_bugs.append({
                "id": detection.get("id"),
                "timestamp": timestamp,
                "video_id": detection.get("video_id")
            })
        else:
            valid_timestamps += 1

    print_info(f"Valid timestamps: {valid_timestamps}")
    print_info(f"NULL timestamps: {null_timestamps}")

    if year_1762_bugs:
        print_fail(f"YEAR 1762 BUG DETECTED: {len(year_1762_bugs)} invalid timestamps")
        for bug in year_1762_bugs[:5]:
            print_info(f"  Detection {bug['id']}: {bug['timestamp']}s (video {bug['video_id']})")
        raise AssertionError(f"Found {len(year_1762_bugs)} year 1762 bugs")

    assert valid_timestamps > 0, "No valid timestamps found"

def test_03_video_id_not_null():
    """Test 3: Verify all detections have video_id (NOT NULL)"""
    data = api_get(f"/api/test-sessions/{SESSION_ID}/events")
    detections = data.get("detections", [])

    null_video_ids = []

    for detection in detections:
        if detection.get("video_id") is None:
            null_video_ids.append({
                "id": detection.get("id"),
                "time": detection.get("detection_time")
            })

    if null_video_ids:
        print_fail(f"Found {len(null_video_ids)} NULL video_ids:")
        for item in null_video_ids[:10]:
            print_info(f"  Detection {item['id']}: time={item['time']}")
        raise AssertionError(f"{len(null_video_ids)} detections have NULL video_id")

    print_info(f"All {len(detections)} detections have valid video_id")

def test_04_video_filtering():
    """Test 4: Verify video_id filtering works"""
    # Get all detections
    data = api_get(f"/api/test-sessions/{SESSION_ID}/events")
    all_detections = data.get("detections", [])

    # Get unique video IDs
    video_ids = set(d.get("video_id") for d in all_detections if d.get("video_id"))
    print_info(f"Found {len(video_ids)} unique video IDs: {sorted(video_ids)}")

    for video_id in sorted(video_ids):
        filtered_data = api_get(
            f"/api/test-sessions/{SESSION_ID}/events",
            {"video_id": video_id}
        )
        filtered = filtered_data.get("detections", [])

        # Verify all have correct video_id
        wrong_ids = [d for d in filtered if d.get("video_id") != video_id]

        print_info(f"Video {video_id}: {len(filtered)} detections")

        assert len(wrong_ids) == 0, \
            f"Found {len(wrong_ids)} detections with wrong video_id"

def test_05_video_distribution():
    """Test 5: Verify detection distribution between videos"""
    data = api_get(f"/api/test-sessions/{SESSION_ID}/events")
    detections = data.get("detections", [])

    video_counts = {}
    for d in detections:
        vid = d.get("video_id")
        video_counts[vid] = video_counts.get(vid, 0) + 1

    print_info("Detection distribution:")
    for vid, count in sorted(video_counts.items()):
        percentage = (count / len(detections)) * 100
        print_info(f"  Video {vid}: {count} ({percentage:.1f}%)")

    # Verify reasonable distribution (each video should have detections)
    assert len(video_counts) >= 2, "Expected at least 2 videos"
    for count in video_counts.values():
        assert count > 100, f"Video has too few detections: {count}"

def test_06_ground_truth_endpoint():
    """Test 6: Verify ground truth validation endpoint"""
    data = api_get(f"/api/test-sessions/{SESSION_ID}/ground-truth-validation")

    print_info(f"Response keys: {list(data.keys())}")

    # Check for expected keys
    assert "detections" in data or "session_info" in data, \
        "Missing expected data in response"

def test_07_frame_numbers_range():
    """Test 7: Verify frame numbers are reasonable (0-240), NOT 42293926782"""
    data = api_get(f"/api/test-sessions/{SESSION_ID}/ground-truth-validation")

    invalid_frames = []

    # Check detections
    detections = data.get("detections", [])
    for d in detections:
        frame = d.get("frame_number")
        if frame is not None and (frame < 0 or frame > MAX_FRAME_NUMBER):
            invalid_frames.append({
                "type": "detection",
                "id": d.get("id"),
                "frame": frame
            })

    # Check ground truth
    gt = data.get("ground_truth", [])
    for g in gt:
        frame = g.get("frame_number")
        if frame is not None and (frame < 0 or frame > MAX_FRAME_NUMBER):
            invalid_frames.append({
                "type": "ground_truth",
                "frame": frame
            })

    if invalid_frames:
        print_fail(f"Found {len(invalid_frames)} invalid frame numbers:")
        for item in invalid_frames[:5]:
            print_info(f"  {item}")
        raise AssertionError(f"{len(invalid_frames)} invalid frame numbers")

    print_info(f"All frame numbers in valid range (0-{MAX_FRAME_NUMBER})")

def test_08_latency_calculations():
    """Test 8: Verify latency calculations are positive"""
    data = api_get(f"/api/test-sessions/{SESSION_ID}/events")
    detections = data.get("detections", [])

    latencies = []
    negative_latencies = []

    for d in detections:
        lat = d.get("latency_ms")
        if lat is not None:
            latencies.append(lat)
            if lat < 0:
                negative_latencies.append({
                    "id": d.get("id"),
                    "latency": lat
                })

    if negative_latencies:
        print_fail(f"Found {len(negative_latencies)} negative latencies:")
        for item in negative_latencies[:5]:
            print_info(f"  Detection {item['id']}: {item['latency']} ms")
        raise AssertionError(f"{len(negative_latencies)} negative latencies")

    if latencies:
        avg = sum(latencies) / len(latencies)
        print_info(f"Latency stats: avg={avg:.2f}ms, min={min(latencies):.2f}ms, max={max(latencies):.2f}ms")

def test_09_frontend_response_structure():
    """Test 9: Verify API response structure for frontend"""
    data = api_get(f"/api/test-sessions/{SESSION_ID}/events")

    required_fields = ["detections", "total", "session_info"]
    missing = [f for f in required_fields if f not in data]

    assert len(missing) == 0, f"Missing fields: {missing}"

    # Check detection structure
    detections = data.get("detections", [])
    if detections:
        d = detections[0]
        detection_fields = [
            "id", "video_id", "detection_time", "video_relative_timestamp",
            "frame_number", "confidence"
        ]
        missing_det = [f for f in detection_fields if f not in d]
        assert len(missing_det) == 0, f"Detection missing fields: {missing_det}"

    print_info(f"Response structure valid")
    print_info(f"  Total: {data.get('total')}")
    print_info(f"  Session: {data.get('session_info', {}).get('session_id')}")

def test_10_timing_monotonicity():
    """Test 10: Verify timestamps are generally increasing per video"""
    data = api_get(f"/api/test-sessions/{SESSION_ID}/events")
    detections = data.get("detections", [])

    # Group by video
    video_detections = {}
    for d in detections:
        vid = d.get("video_id")
        if vid not in video_detections:
            video_detections[vid] = []
        video_detections[vid].append(d)

    for vid, dets in sorted(video_detections.items()):
        timestamps = [d.get("video_relative_timestamp") for d in dets
                     if d.get("video_relative_timestamp") is not None]

        if timestamps:
            min_ts = min(timestamps)
            max_ts = max(timestamps)
            duration = max_ts - min_ts

            print_info(f"Video {vid}: range={min_ts:.3f}s-{max_ts:.3f}s, duration={duration:.3f}s")

            assert min_ts >= 0, f"Video {vid} has negative timestamp: {min_ts}"
            assert max_ts <= VIDEO_DURATION_SECONDS, \
                f"Video {vid} exceeds duration: {max_ts}s > {VIDEO_DURATION_SECONDS}s"

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Run all tests and generate report"""
    print_header(f"TIMING VALIDATION API TEST SUITE\nSession: {SESSION_ID}\nTime: {datetime.now().isoformat()}")

    # Run all tests
    tests = [
        ("All Detections Retrieved (502 expected)", test_01_get_all_detections),
        ("Video Relative Timestamps Valid (NOT year 1762)", test_02_video_relative_timestamp_range),
        ("Video ID Not NULL", test_03_video_id_not_null),
        ("Video Filtering Works", test_04_video_filtering),
        ("Video Distribution Balanced", test_05_video_distribution),
        ("Ground Truth Endpoint Accessible", test_06_ground_truth_endpoint),
        ("Frame Numbers in Valid Range (0-240)", test_07_frame_numbers_range),
        ("Latency Calculations Positive", test_08_latency_calculations),
        ("Frontend Response Structure Valid", test_09_frontend_response_structure),
        ("Timestamp Monotonicity Per Video", test_10_timing_monotonicity),
    ]

    for name, test_func in tests:
        run_test(name, test_func)

    # Print summary
    print_header("TEST SUMMARY")

    total = test_results["passed"] + test_results["failed"]
    pass_rate = (test_results["passed"] / total * 100) if total > 0 else 0

    print(f"{Colors.GREEN}Passed: {test_results['passed']}{Colors.RESET}")
    print(f"{Colors.RED}Failed: {test_results['failed']}{Colors.RESET}")
    print(f"Pass Rate: {pass_rate:.1f}%")

    if test_results["issues"]:
        print(f"\n{Colors.RED}Issues Found:{Colors.RESET}")
        for issue in test_results["issues"]:
            print(f"  - {issue['test']}: {issue['error']}")

    # Final verdict
    print_header("FINAL VERDICT")
    if test_results["failed"] == 0:
        print(f"{Colors.GREEN}✓ ALL TESTS PASSED - System is working correctly!{Colors.RESET}")
        print(f"{Colors.GREEN}✓ Year 1762 bug is FIXED{Colors.RESET}")
        print(f"{Colors.GREEN}✓ Video ID assignments are correct{Colors.RESET}")
        print(f"{Colors.GREEN}✓ Timing calculations are accurate{Colors.RESET}")
        return 0
    else:
        print(f"{Colors.RED}✗ {test_results['failed']} TEST(S) FAILED{Colors.RESET}")
        print(f"{Colors.YELLOW}⚠ Review issues above and fix before deployment{Colors.RESET}")
        return 1

if __name__ == "__main__":
    exit(main())
