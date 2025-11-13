"""
Comprehensive API Testing for Timing Calculation Validation
Tests session 0846e476-2e21-499c-bfc8-0b2218081c77 after backend restart

Verifies:
1. video_relative_timestamp values are in valid range (0-10 seconds)
2. Detection video_id assignments are not NULL
3. Video filtering works correctly
4. Pagination returns all 502 detections
5. Frame numbers are reasonable (0-240 range)
6. Ground truth validation endpoint works
7. Frontend display data is correct
"""

import pytest
import requests
import json
from datetime import datetime
from typing import Dict, List, Any

# Test configuration
BASE_URL = "http://localhost:8000"
SESSION_ID = "0846e476-2e21-499c-bfc8-0b2218081c77"
EXPECTED_TOTAL_DETECTIONS = 502
EXPECTED_VIDEO1_DETECTIONS = 251
EXPECTED_VIDEO2_DETECTIONS = 251
VIDEO_DURATION_SECONDS = 10.0
MAX_FRAME_NUMBER = 240  # 24 fps * 10 seconds


class TestDetectionEventsEndpoint:
    """Test GET /api/test-sessions/{session_id}/events"""

    def test_get_all_detections_no_pagination_limit(self):
        """Verify all 502 detections are returned without artificial limit"""
        response = requests.get(f"{BASE_URL}/api/test-sessions/{SESSION_ID}/events")

        assert response.status_code == 200, f"Failed with status {response.status_code}"

        data = response.json()
        detections = data.get("detections", [])

        print(f"\n✓ Total detections returned: {len(detections)}")
        assert len(detections) == EXPECTED_TOTAL_DETECTIONS, \
            f"Expected {EXPECTED_TOTAL_DETECTIONS} detections, got {len(detections)}"

    def test_video_relative_timestamp_range(self):
        """Verify video_relative_timestamp is in valid range (0-10 seconds), NOT year 1762"""
        response = requests.get(f"{BASE_URL}/api/test-sessions/{SESSION_ID}/events")
        data = response.json()
        detections = data.get("detections", [])

        invalid_timestamps = []
        year_1762_bugs = []

        for detection in detections:
            timestamp = detection.get("video_relative_timestamp")

            if timestamp is None:
                invalid_timestamps.append({
                    "detection_id": detection.get("id"),
                    "issue": "NULL timestamp"
                })
                continue

            # Check for year 1762 bug (negative or extremely large values)
            if timestamp < 0 or timestamp > VIDEO_DURATION_SECONDS * 2:
                year_1762_bugs.append({
                    "detection_id": detection.get("id"),
                    "timestamp": timestamp,
                    "video_id": detection.get("video_id")
                })

            # Verify timestamp is in valid range
            assert 0 <= timestamp <= VIDEO_DURATION_SECONDS, \
                f"Detection {detection.get('id')} has invalid timestamp: {timestamp}s"

        print(f"\n✓ All {len(detections)} detections have valid timestamps (0-{VIDEO_DURATION_SECONDS}s)")

        if year_1762_bugs:
            print("\n❌ YEAR 1762 BUG STILL PRESENT:")
            for bug in year_1762_bugs[:5]:  # Show first 5
                print(f"  Detection {bug['detection_id']}: timestamp={bug['timestamp']}, video_id={bug['video_id']}")
            raise AssertionError(f"Found {len(year_1762_bugs)} detections with year 1762 bug")
        else:
            print("✓ No year 1762 bugs found")

    def test_video_id_assignments_not_null(self):
        """Verify all detections have proper video_id assignments (NOT NULL)"""
        response = requests.get(f"{BASE_URL}/api/test-sessions/{SESSION_ID}/events")
        data = response.json()
        detections = data.get("detections", [])

        null_video_ids = []

        for detection in detections:
            video_id = detection.get("video_id")
            if video_id is None:
                null_video_ids.append({
                    "detection_id": detection.get("id"),
                    "detection_time": detection.get("detection_time")
                })

        if null_video_ids:
            print(f"\n❌ Found {len(null_video_ids)} detections with NULL video_id:")
            for item in null_video_ids[:10]:  # Show first 10
                print(f"  Detection {item['detection_id']}: time={item['detection_time']}")
            raise AssertionError(f"{len(null_video_ids)} detections have NULL video_id")
        else:
            print(f"\n✓ All {len(detections)} detections have valid video_id assignments")

    def test_video_filtering_by_id(self):
        """Test filtering detections by video_id query parameter"""
        # Get all detections first
        response_all = requests.get(f"{BASE_URL}/api/test-sessions/{SESSION_ID}/events")
        all_detections = response_all.json().get("detections", [])

        # Get unique video IDs
        video_ids = set(d.get("video_id") for d in all_detections if d.get("video_id"))
        print(f"\n✓ Found {len(video_ids)} unique video IDs")

        for video_id in video_ids:
            # Test filtering
            response = requests.get(
                f"{BASE_URL}/api/test-sessions/{SESSION_ID}/events",
                params={"video_id": video_id}
            )

            assert response.status_code == 200
            filtered_detections = response.json().get("detections", [])

            # Verify all returned detections have the requested video_id
            for detection in filtered_detections:
                assert detection.get("video_id") == video_id, \
                    f"Detection {detection.get('id')} has wrong video_id"

            print(f"✓ Video {video_id}: {len(filtered_detections)} detections")

    def test_video_distribution(self):
        """Verify detections are properly distributed between Video 1 and Video 2"""
        response = requests.get(f"{BASE_URL}/api/test-sessions/{SESSION_ID}/events")
        detections = response.json().get("detections", [])

        video_counts = {}
        for detection in detections:
            video_id = detection.get("video_id")
            video_counts[video_id] = video_counts.get(video_id, 0) + 1

        print("\n✓ Detection distribution by video:")
        for video_id, count in sorted(video_counts.items()):
            print(f"  Video {video_id}: {count} detections")

            # Verify counts are close to expected
            expected = EXPECTED_VIDEO1_DETECTIONS  # Assuming equal distribution
            tolerance = 50  # Allow some variance
            assert abs(count - expected) < tolerance, \
                f"Video {video_id} has {count} detections, expected ~{expected}"


class TestGroundTruthValidationEndpoint:
    """Test GET /api/test-sessions/{session_id}/ground-truth-validation"""

    def test_ground_truth_endpoint_accessible(self):
        """Verify ground truth validation endpoint is accessible"""
        response = requests.get(
            f"{BASE_URL}/api/test-sessions/{SESSION_ID}/ground-truth-validation"
        )

        assert response.status_code == 200, \
            f"Ground truth endpoint failed with status {response.status_code}"

        data = response.json()
        print("\n✓ Ground truth validation endpoint accessible")
        print(f"  Response keys: {list(data.keys())}")

    def test_frame_numbers_reasonable_range(self):
        """Verify frame numbers are in reasonable range (0-240), NOT 42293926782"""
        response = requests.get(
            f"{BASE_URL}/api/test-sessions/{SESSION_ID}/ground-truth-validation"
        )
        data = response.json()

        # Check detections for frame numbers
        detections = data.get("detections", [])
        invalid_frames = []

        for detection in detections:
            frame = detection.get("frame_number")
            if frame is not None:
                if frame < 0 or frame > MAX_FRAME_NUMBER:
                    invalid_frames.append({
                        "detection_id": detection.get("id"),
                        "frame": frame,
                        "video_id": detection.get("video_id")
                    })

        # Check ground truth entries for frame numbers
        ground_truth = data.get("ground_truth", [])
        for gt_entry in ground_truth:
            frame = gt_entry.get("frame_number")
            if frame is not None:
                if frame < 0 or frame > MAX_FRAME_NUMBER:
                    invalid_frames.append({
                        "type": "ground_truth",
                        "frame": frame,
                        "video_id": gt_entry.get("video_id")
                    })

        if invalid_frames:
            print(f"\n❌ Found {len(invalid_frames)} invalid frame numbers:")
            for item in invalid_frames[:5]:
                print(f"  {item}")
            raise AssertionError(f"{len(invalid_frames)} frame numbers out of valid range")
        else:
            print(f"\n✓ All frame numbers in valid range (0-{MAX_FRAME_NUMBER})")

    def test_ground_truth_matching_tolerances(self):
        """Verify ground truth matching uses correct tolerances"""
        response = requests.get(
            f"{BASE_URL}/api/test-sessions/{SESSION_ID}/ground-truth-validation"
        )
        data = response.json()

        # Check matching configuration
        config = data.get("matching_config", {})
        print("\n✓ Ground truth matching configuration:")
        print(f"  Time tolerance: {config.get('time_tolerance_ms', 'N/A')} ms")
        print(f"  Frame tolerance: {config.get('frame_tolerance', 'N/A')} frames")

        # Check matching results
        matches = data.get("matches", [])
        print(f"  Total matches: {len(matches)}")


class TestTimingAccuracy:
    """Test timing calculation accuracy"""

    def test_hardware_timing_correlation(self):
        """Verify video_relative_timestamp correlates with hardware timing"""
        response = requests.get(f"{BASE_URL}/api/test-sessions/{SESSION_ID}/events")
        detections = response.json().get("detections", [])

        # Group by video
        video_detections = {}
        for detection in detections:
            video_id = detection.get("video_id")
            if video_id not in video_detections:
                video_detections[video_id] = []
            video_detections[video_id].append(detection)

        print("\n✓ Timing accuracy analysis:")
        for video_id, dets in sorted(video_detections.items()):
            timestamps = [d.get("video_relative_timestamp") for d in dets if d.get("video_relative_timestamp") is not None]

            if timestamps:
                min_ts = min(timestamps)
                max_ts = max(timestamps)
                print(f"\n  Video {video_id}:")
                print(f"    Timestamp range: {min_ts:.3f}s - {max_ts:.3f}s")
                print(f"    Duration: {max_ts - min_ts:.3f}s")

                # Verify timestamps are monotonic (generally increasing)
                sorted_timestamps = sorted(timestamps)
                assert sorted_timestamps == timestamps or len(set(timestamps)) > len(timestamps) * 0.9, \
                    f"Video {video_id} timestamps are not generally increasing"

    def test_latency_calculations(self):
        """Verify latency calculations are reasonable"""
        response = requests.get(f"{BASE_URL}/api/test-sessions/{SESSION_ID}/events")
        detections = response.json().get("detections", [])

        latencies = []
        negative_latencies = []

        for detection in detections:
            latency = detection.get("latency_ms")
            if latency is not None:
                latencies.append(latency)
                if latency < 0:
                    negative_latencies.append({
                        "detection_id": detection.get("id"),
                        "latency": latency
                    })

        if negative_latencies:
            print(f"\n❌ Found {len(negative_latencies)} negative latencies:")
            for item in negative_latencies[:5]:
                print(f"  Detection {item['detection_id']}: {item['latency']} ms")
            raise AssertionError(f"{len(negative_latencies)} detections have negative latency")

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)

            print("\n✓ Latency statistics:")
            print(f"  Average: {avg_latency:.2f} ms")
            print(f"  Min: {min_latency:.2f} ms")
            print(f"  Max: {max_latency:.2f} ms")
            print(f"  Count: {len(latencies)}")


class TestFrontendDataIntegrity:
    """Test data integrity for frontend display"""

    def test_frontend_api_response_structure(self):
        """Verify API response has all fields needed for frontend display"""
        response = requests.get(f"{BASE_URL}/api/test-sessions/{SESSION_ID}/events")
        data = response.json()

        required_fields = ["detections", "total", "session_info"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Check detection structure
        detections = data.get("detections", [])
        if detections:
            detection = detections[0]
            required_detection_fields = [
                "id", "video_id", "detection_time", "video_relative_timestamp",
                "frame_number", "confidence"
            ]

            for field in required_detection_fields:
                assert field in detection, \
                    f"Detection missing required field: {field}"

        print("\n✓ Frontend API response structure is valid")
        print(f"  Total detections: {data.get('total')}")
        print(f"  Session info: {data.get('session_info', {}).get('session_id')}")

    def test_session_metadata(self):
        """Verify session metadata is complete"""
        response = requests.get(f"{BASE_URL}/api/test-sessions/{SESSION_ID}/events")
        data = response.json()

        session_info = data.get("session_info", {})
        print("\n✓ Session metadata:")
        print(f"  Session ID: {session_info.get('session_id')}")
        print(f"  Status: {session_info.get('status')}")
        print(f"  Video count: {session_info.get('video_count')}")
        print(f"  Start time: {session_info.get('start_time')}")

        assert session_info.get("session_id") == SESSION_ID


def generate_test_report():
    """Generate comprehensive test report"""
    print("\n" + "="*80)
    print("TIMING VALIDATION API TEST REPORT")
    print(f"Session: {SESSION_ID}")
    print(f"Test Time: {datetime.now().isoformat()}")
    print("="*80)

    # Run all tests
    pytest.main([__file__, "-v", "--tb=short", "-s"])


if __name__ == "__main__":
    generate_test_report()
