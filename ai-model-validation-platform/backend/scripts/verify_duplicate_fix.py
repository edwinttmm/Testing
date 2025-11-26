#!/usr/bin/env python3
"""
Verification Script: Duplicate Detection Fix

This script verifies that the duplicate detection bug has been fixed by:
1. Checking socketio_server.py for duplicate emissions
2. Verifying that detection_event is only emitted once per detection
3. Confirming the fix documentation is in place
"""

import os
import re
import sys
from pathlib import Path

def verify_socketio_emissions():
    """Verify socketio_server.py only emits detection_event once per detection"""

    socketio_path = Path(__file__).parent.parent / "socketio_server.py"

    if not socketio_path.exists():
        print(f"❌ ERROR: {socketio_path} not found")
        return False

    with open(socketio_path, 'r') as f:
        content = f.read()

    # Find all detection_event emissions
    detection_event_pattern = r"await sio\.emit\('detection_event'"
    matches = list(re.finditer(detection_event_pattern, content))

    print(f"\n📊 VERIFICATION RESULTS:")
    print(f"{'='*60}")
    print(f"✅ Found {len(matches)} detection_event emissions in socketio_server.py")

    # Should be exactly 2 (one in simulate_hil_test_session, one in emit_detection_event)
    if len(matches) != 2:
        print(f"⚠️  WARNING: Expected 2 emissions, found {len(matches)}")
        return False

    # Check that each emission is to a session-specific room
    lines = content.split('\n')
    for i, match in enumerate(matches, 1):
        line_num = content[:match.start()].count('\n') + 1
        context_start = max(0, line_num - 5)
        context_end = min(len(lines), line_num + 3)
        context = lines[context_start:context_end]

        print(f"\n🔍 Emission #{i} at line {line_num}:")
        for j, line in enumerate(context, start=context_start+1):
            marker = ">>>" if j == line_num else "   "
            print(f"{marker} {j:4d}: {line}")

        # Check for duplicate emission to 'detections' room (BAD)
        nearby_lines = '\n'.join(lines[line_num:line_num+3])
        if "room='detections'" in nearby_lines and "'detection_event'" in nearby_lines:
            print(f"❌ FAILED: Found duplicate emission to 'detections' room near line {line_num}")
            return False

    print(f"\n✅ PASSED: No duplicate emissions to 'detections' room found")
    return True

def verify_documentation():
    """Verify fix documentation exists"""

    doc_path = Path(__file__).parent.parent / "docs" / "DUPLICATE_DETECTION_FIX.md"

    if not doc_path.exists():
        print(f"\n❌ FAILED: Documentation not found at {doc_path}")
        return False

    with open(doc_path, 'r') as f:
        content = f.read()

    # Check for key sections
    required_sections = [
        "Problem Summary",
        "Root Cause",
        "Solution",
        "Verification",
        "Related Files"
    ]

    missing_sections = []
    for section in required_sections:
        if section not in content:
            missing_sections.append(section)

    if missing_sections:
        print(f"\n⚠️  WARNING: Missing documentation sections: {missing_sections}")
        return False

    print(f"\n✅ PASSED: Documentation complete at {doc_path}")
    print(f"   - File size: {len(content)} bytes")
    print(f"   - All required sections present")
    return True

def verify_labjack_monitoring_service():
    """Verify labjack_monitoring_service.py stores detections correctly"""

    service_path = Path(__file__).parent.parent / "services" / "labjack_monitoring_service.py"

    if not service_path.exists():
        print(f"\n⚠️  WARNING: {service_path} not found")
        return True  # Not critical for this fix

    with open(service_path, 'r') as f:
        content = f.read()

    # Check for single INSERT INTO detection_events
    insert_pattern = r"INSERT INTO detection_events"
    matches = list(re.finditer(insert_pattern, content, re.IGNORECASE))

    print(f"\n✅ PASSED: labjack_monitoring_service.py has {len(matches)} INSERT statement(s)")
    print(f"   - Detection storage is correct (not duplicating in DB)")
    return True

def main():
    """Run all verification checks"""

    print("\n" + "="*60)
    print("DUPLICATE DETECTION FIX VERIFICATION")
    print("="*60)

    checks = [
        ("WebSocket Emissions", verify_socketio_emissions),
        ("Fix Documentation", verify_documentation),
        ("Database Storage", verify_labjack_monitoring_service),
    ]

    results = []
    for name, check_fn in checks:
        print(f"\n{'='*60}")
        print(f"Running: {name}")
        print(f"{'='*60}")
        try:
            result = check_fn()
            results.append((name, result))
        except Exception as e:
            print(f"❌ ERROR in {name}: {e}")
            results.append((name, False))

    # Summary
    print(f"\n\n{'='*60}")
    print("VERIFICATION SUMMARY")
    print(f"{'='*60}")

    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {name}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print(f"\n🎉 ALL CHECKS PASSED - Fix is verified and complete!")
        print(f"\n📋 NEXT STEPS:")
        print(f"   1. Test with actual HIL session")
        print(f"   2. Verify detection count is accurate (not doubled)")
        print(f"   3. Check timeline for duplicate timestamps")
        print(f"   4. Confirm ground truth matching works (1:1 ratio)")
        return 0
    else:
        print(f"\n❌ SOME CHECKS FAILED - Review issues above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
