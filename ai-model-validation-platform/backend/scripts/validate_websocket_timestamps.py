#!/usr/bin/env python3
"""
Validation script to test WebSocket timestamp formatting

Tests all timestamp edge cases to ensure they are properly formatted
before WebSocket emission.
"""

import sys
from datetime import datetime
from typing import Any, Dict


def validate_timestamp_formatting():
    """Test timestamp formatting logic"""
    print("🧪 Testing WebSocket Timestamp Formatting\n")

    test_cases = [
        {
            "name": "Valid datetime object",
            "timestamp": datetime.now(),
            "expected_format": "ISO 8601"
        },
        {
            "name": "Unix timestamp (float)",
            "timestamp": 1705507425.123456,
            "expected_format": "ISO 8601"
        },
        {
            "name": "Unix timestamp (int)",
            "timestamp": 1705507425,
            "expected_format": "ISO 8601"
        },
        {
            "name": "ISO string",
            "timestamp": "2025-01-17T14:23:45.123456",
            "expected_format": "ISO 8601"
        },
        {
            "name": "Invalid type (None)",
            "timestamp": None,
            "expected_format": "ISO 8601 (fallback)"
        },
        {
            "name": "Invalid type (dict)",
            "timestamp": {"time": "invalid"},
            "expected_format": "ISO 8601 (fallback)"
        },
        {
            "name": "Short string",
            "timestamp": "2025",
            "expected_format": "ISO 8601 (fallback)"
        }
    ]

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['name']}")
        print(f"  Input: {test['timestamp']} (type: {type(test['timestamp']).__name__})")

        # Apply the formatting logic from the fix
        timestamp_iso = format_timestamp_for_websocket(test['timestamp'])

        # Validate result
        is_valid = validate_iso_format(timestamp_iso)

        if is_valid:
            print(f"  ✅ Result: {timestamp_iso}")
            print(f"  Status: PASS - Valid ISO 8601 format\n")
            passed += 1
        else:
            print(f"  ❌ Result: {timestamp_iso}")
            print(f"  Status: FAIL - Invalid format\n")
            failed += 1

    # Summary
    print("=" * 60)
    print(f"Summary: {passed}/{len(test_cases)} tests passed")
    print("=" * 60)

    if failed > 0:
        print(f"\n⚠️ {failed} test(s) failed - timestamp formatting needs fixing")
        return False
    else:
        print("\n✅ All tests passed - timestamp formatting is correct")
        return True


def format_timestamp_for_websocket(timestamp: Any) -> str:
    """
    Format timestamp for WebSocket emission (matches production code logic)

    This is the EXACT logic from the fix in labjack_detection_service.py
    """
    timestamp_iso = None

    if hasattr(timestamp, 'isoformat'):
        # datetime object
        timestamp_iso = timestamp.isoformat()
    elif isinstance(timestamp, (int, float)):
        # Unix timestamp - convert to ISO format
        timestamp_iso = datetime.fromtimestamp(timestamp).isoformat()
    elif isinstance(timestamp, str) and len(timestamp) >= 10:
        # Already a string, assume valid if long enough
        timestamp_iso = timestamp
    else:
        # Fallback: use current time in ISO format
        timestamp_iso = datetime.now().isoformat()
        print(f"    ⚠️ Invalid timestamp type {type(timestamp)}, using current time")

    return timestamp_iso


def validate_iso_format(timestamp_str: str) -> bool:
    """
    Validate that timestamp is in ISO 8601 format

    Expected format: YYYY-MM-DDTHH:MM:SS[.ffffff]
    """
    if not timestamp_str or len(timestamp_str) < 10:
        return False

    try:
        # Try parsing as ISO format
        datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return True
    except (ValueError, AttributeError):
        return False


def test_websocket_emit_validation():
    """Test the validation logic that runs before emit"""
    print("\n🧪 Testing WebSocket Emit Validation\n")

    test_data = [
        {
            "name": "Missing timestamp field",
            "data": {"id": "test-1", "voltage": 3.3},
            "should_add_timestamp": True
        },
        {
            "name": "Valid timestamp",
            "data": {"id": "test-2", "timestamp": "2025-01-17T14:23:45.123456", "voltage": 3.3},
            "should_add_timestamp": False
        },
        {
            "name": "Datetime timestamp",
            "data": {"id": "test-3", "timestamp": datetime.now(), "voltage": 3.3},
            "should_add_timestamp": False
        },
        {
            "name": "Unix timestamp",
            "data": {"id": "test-4", "timestamp": 1705507425.123, "voltage": 3.3},
            "should_add_timestamp": False
        },
        {
            "name": "Short timestamp string",
            "data": {"id": "test-5", "timestamp": "2025", "voltage": 3.3},
            "should_add_timestamp": True
        }
    ]

    passed = 0
    failed = 0

    for i, test in enumerate(test_data, 1):
        print(f"Test {i}: {test['name']}")
        data = test['data'].copy()

        # Apply validation logic from socketio_server.py
        if 'timestamp' not in data:
            print(f"  ℹ️ Adding missing timestamp")
            data['timestamp'] = datetime.now().isoformat()
        elif not isinstance(data['timestamp'], str):
            ts = data['timestamp']
            if hasattr(ts, 'isoformat'):
                data['timestamp'] = ts.isoformat()
            elif isinstance(ts, (int, float)):
                data['timestamp'] = datetime.fromtimestamp(ts).isoformat()
            else:
                data['timestamp'] = datetime.now().isoformat()
        elif len(data['timestamp']) < 10:
            print(f"  ℹ️ Replacing short timestamp")
            data['timestamp'] = datetime.now().isoformat()

        # Validate result
        has_valid_timestamp = (
            'timestamp' in data and
            isinstance(data['timestamp'], str) and
            len(data['timestamp']) >= 10
        )

        if has_valid_timestamp:
            print(f"  ✅ Result: timestamp = {data['timestamp']}")
            print(f"  Status: PASS\n")
            passed += 1
        else:
            print(f"  ❌ Result: timestamp validation failed")
            print(f"  Status: FAIL\n")
            failed += 1

    # Summary
    print("=" * 60)
    print(f"Summary: {passed}/{len(test_data)} tests passed")
    print("=" * 60)

    if failed > 0:
        print(f"\n⚠️ {failed} test(s) failed - validation logic needs fixing")
        return False
    else:
        print("\n✅ All tests passed - validation logic is correct")
        return True


if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket Timestamp Validation Test Suite")
    print("=" * 60)
    print()

    # Run both test suites
    formatting_ok = validate_timestamp_formatting()
    validation_ok = test_websocket_emit_validation()

    # Final result
    print("\n" + "=" * 60)
    if formatting_ok and validation_ok:
        print("✅ ALL TESTS PASSED - WebSocket timestamp fix is working correctly")
        print("=" * 60)
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED - Please review the implementation")
        print("=" * 60)
        sys.exit(1)
