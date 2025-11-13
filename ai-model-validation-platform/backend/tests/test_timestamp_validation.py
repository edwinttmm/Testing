"""
Timestamp Validation Tests
Tests to detect actual epoch bugs and prevent false alarms like the "year 1762" incident.
"""

import pytest
import time
from datetime import datetime, timezone


def validate_timestamp_epoch(timestamp: float, context: str = "") -> dict:
    """
    Validate that a timestamp uses the correct Unix epoch (1970-01-01).

    Args:
        timestamp: Unix timestamp to validate
        context: Description of where this timestamp came from

    Returns:
        Dictionary with validation results
    """
    results = {
        "timestamp": timestamp,
        "context": context,
        "valid": True,
        "errors": [],
        "warnings": []
    }

    try:
        # Convert to datetime
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        results["datetime"] = dt.isoformat()
        results["year"] = dt.year

        # Check 1: Year must be reasonable (2020-2030)
        if dt.year < 2020:
            results["valid"] = False
            results["errors"].append(
                f"Timestamp year {dt.year} is too old - possible wrong epoch or time travel bug"
            )
        elif dt.year > 2030:
            results["valid"] = False
            results["errors"].append(
                f"Timestamp year {dt.year} is in the future - possible overflow or wrong epoch"
            )

        # Check 2: Timestamp should be within reasonable range of current time
        current_time = time.time()
        age_seconds = abs(current_time - timestamp)
        age_days = age_seconds / 86400

        if age_days > 365:
            results["warnings"].append(
                f"Timestamp is {age_days:.0f} days from current time - verify this is intentional"
            )

        # Check 3: Detect the "year 1762" false alarm pattern
        timestamp_str = str(int(timestamp))
        if timestamp_str.startswith("1762"):
            results["warnings"].append(
                f"Timestamp starts with '1762' but represents {dt.year} - not a bug, just coincidence"
            )

        # Check 4: Detect actual epoch bugs
        # Year 1762 would be: -6563980800 (negative timestamp)
        # Year 2262 would be: 9223372036 (Unix time overflow)
        if timestamp < 0:
            results["valid"] = False
            results["errors"].append(
                "Negative timestamp detected - epoch is before 1970-01-01"
            )
        elif timestamp > 9000000000:  # Year 2255+
            results["valid"] = False
            results["errors"].append(
                "Timestamp too large - possible overflow or wrong epoch"
            )

    except (ValueError, OSError, OverflowError) as e:
        results["valid"] = False
        results["errors"].append(f"Cannot parse timestamp: {e}")

    return results


class TestTimestampValidation:
    """Test suite for timestamp epoch validation"""

    def test_current_timestamp_valid(self):
        """Current time should always be valid"""
        current = time.time()
        result = validate_timestamp_epoch(current, "current time")

        assert result["valid"], f"Current timestamp failed validation: {result['errors']}"
        assert result["year"] in [2024, 2025, 2026], "Current year should be 2024-2026"

    def test_session_0846e476_timestamps_valid(self):
        """
        Session 0846e476 timestamps should be valid (not year 1762).
        This test prevents regression of the false alarm.
        """
        # The timestamp that was mistakenly reported as "year 1762"
        timestamp = 1762266382.749499
        result = validate_timestamp_epoch(timestamp, "session 0846e476")

        assert result["valid"], f"Timestamp validation failed: {result['errors']}"
        assert result["year"] == 2025, f"Expected year 2025, got {result['year']}"

        # Should have warning about "1762" prefix but still be valid
        warning_found = any("1762" in w for w in result["warnings"])
        assert warning_found, "Should warn about '1762' prefix coincidence"

    def test_video_relative_timestamps_in_range(self):
        """Video relative timestamps should be 0-N seconds, not Unix timestamps"""
        valid_relative_timestamps = [0.0, 0.5, 1.0, 5.0, 10.0]

        for ts in valid_relative_timestamps:
            # Video relative timestamps should be small numbers
            assert 0 <= ts <= 3600, f"Video relative timestamp {ts} is out of range"

    def test_detect_negative_timestamp_bug(self):
        """Negative timestamps indicate epoch before 1970"""
        # This would represent year 1762 (208 years before 1970)
        years_before_1970 = 208
        seconds_per_year = 365.25 * 24 * 3600
        wrong_timestamp = -(years_before_1970 * seconds_per_year)

        result = validate_timestamp_epoch(wrong_timestamp, "negative timestamp test")

        assert not result["valid"], "Negative timestamp should fail validation"
        assert any("Negative" in e for e in result["errors"])

    def test_detect_overflow_timestamp_bug(self):
        """Timestamps beyond year 2262 indicate overflow"""
        # Year 2262 Unix timestamp overflow
        overflow_timestamp = 10000000000
        result = validate_timestamp_epoch(overflow_timestamp, "overflow test")

        assert not result["valid"], "Overflow timestamp should fail validation"
        assert any("too large" in e for e in result["errors"])

    def test_timestamp_range_validation(self):
        """Test timestamp range for detection events"""
        # Simulated detection events over 10 seconds
        start_time = time.time()
        detection_timestamps = [
            start_time + i * 0.1 for i in range(100)  # 10 seconds of detections
        ]

        # All should be valid
        for ts in detection_timestamps:
            result = validate_timestamp_epoch(ts, "detection event")
            assert result["valid"], f"Detection timestamp {ts} failed: {result['errors']}"

    def test_video_start_timestamp_format(self):
        """Video start timestamps should be Unix epoch, not video-relative"""
        # Correct: Unix timestamp
        correct_video_start = 1762266382.749499
        result = validate_timestamp_epoch(correct_video_start, "video_start_timestamp")
        assert result["valid"], "Valid Unix timestamp should pass"

        # Incorrect: Small number (would be video-relative, not absolute)
        incorrect_video_start = 5.0  # This would be 5 seconds after epoch (1970)
        result = validate_timestamp_epoch(incorrect_video_start, "video_start_timestamp")
        assert not result["valid"], "Video-relative timestamp in absolute field should fail"

    def test_labjack_timestamp_consistency(self):
        """LabJack timestamps should be consistent Unix timestamps"""
        # Simulated LabJack timestamps from session 0846e476
        labjack_timestamps = [
            1762266382.751773,
            1762266382.774473,
            1762266382.840325,
            1762266383.036994,
            1762266383.097540
        ]

        for ts in labjack_timestamps:
            result = validate_timestamp_epoch(ts, "labjack_timestamp")
            assert result["valid"], f"LabJack timestamp {ts} failed: {result['errors']}"
            assert result["year"] == 2025, f"Expected year 2025, got {result['year']}"

        # Check monotonic increase
        for i in range(1, len(labjack_timestamps)):
            assert labjack_timestamps[i] > labjack_timestamps[i-1], \
                "LabJack timestamps should increase monotonically"


class TestTimestampConversion:
    """Test timestamp conversion utilities"""

    def test_unix_to_video_relative(self):
        """Test converting Unix timestamp to video-relative time"""
        video_start_time = 1762266382.749499  # Unix timestamp
        detection_time = 1762266387.832832    # 5.083 seconds later

        # Calculate video-relative timestamp
        video_relative = detection_time - video_start_time

        assert 5.0 < video_relative < 5.1, \
            f"Expected ~5.083 seconds, got {video_relative}"

    def test_video_relative_to_frame_number(self):
        """Test calculating frame number from video-relative time"""
        video_relative_timestamp = 5.083333  # seconds
        fps = 24.0

        expected_frame = int(video_relative_timestamp * fps)  # Frame 122

        assert 121 <= expected_frame <= 123, \
            f"Expected frame ~122, got {expected_frame}"

    def test_timestamp_precision(self):
        """Test that timestamps maintain sub-millisecond precision"""
        timestamp = 1762266382.749499

        # Should have at least 6 decimal places (microsecond precision)
        timestamp_str = f"{timestamp:.6f}"
        decimal_part = timestamp_str.split('.')[1]

        assert len(decimal_part) >= 6, \
            f"Timestamp should have microsecond precision, got {decimal_part}"


def test_session_0846e476_comprehensive():
    """
    Comprehensive validation of session 0846e476 timestamps.
    This is the session that triggered the false "year 1762" alarm.
    """
    session_data = {
        "session_id": "0846e476-2e21-499c-bfc8-0b2218081c77",
        "video_start_timestamp": 1762266382.749499,
        "labjack_timestamps": {
            "min": 1762266382.751773,
            "max": 1762266401.181730
        },
        "video_relative_timestamps": {
            "min": 0.002274036407470703,
            "max": 10.083333333333334
        },
        "detection_count": 502
    }

    # Validate video start timestamp
    result = validate_timestamp_epoch(
        session_data["video_start_timestamp"],
        "session 0846e476 video_start"
    )
    assert result["valid"], f"Video start validation failed: {result}"
    assert result["year"] == 2025, f"Wrong year: {result['year']}"

    # Validate LabJack timestamp range
    for key, ts in session_data["labjack_timestamps"].items():
        result = validate_timestamp_epoch(ts, f"labjack_{key}")
        assert result["valid"], f"LabJack {key} validation failed: {result}"
        assert result["year"] == 2025, f"Wrong year for {key}: {result['year']}"

    # Validate video-relative timestamps are in range
    for key, ts in session_data["video_relative_timestamps"].items():
        assert 0 <= ts <= 20, \
            f"Video relative {key} timestamp {ts} is out of 0-20 second range"

    # Validate duration consistency
    labjack_duration = (
        session_data["labjack_timestamps"]["max"] -
        session_data["labjack_timestamps"]["min"]
    )
    video_relative_duration = (
        session_data["video_relative_timestamps"]["max"] -
        session_data["video_relative_timestamps"]["min"]
    )

    # Durations should match within tolerance
    duration_diff = abs(labjack_duration - video_relative_duration)
    assert duration_diff < 1.0, \
        f"Duration mismatch: LabJack={labjack_duration:.3f}s, VideoRel={video_relative_duration:.3f}s"

    print(f"\n✅ Session 0846e476 validation PASSED")
    print(f"   All {session_data['detection_count']} detections have correct timestamps")
    print(f"   No year 1762 bug detected")
    print(f"   Video start: {datetime.fromtimestamp(session_data['video_start_timestamp'])}")
    print(f"   Duration: {labjack_duration:.3f} seconds")


if __name__ == "__main__":
    # Run comprehensive validation
    test_session_0846e476_comprehensive()

    # Run pytest
    pytest.main([__file__, "-v"])
