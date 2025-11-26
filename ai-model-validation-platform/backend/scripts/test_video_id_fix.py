#!/usr/bin/env python3
"""
Test script to verify video_id fix works correctly.

Tests:
1. Verify session has video_id
2. Check detection counts before fix
3. Apply fix
4. Verify all detections now have correct video_id
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fix_video_id_assignment import (
    fix_video_id_for_session,
    verify_session_detections
)

def test_fix_for_session(session_id: str):
    """Test the fix for a specific session."""

    print(f"\n{'='*70}")
    print(f"Testing video_id fix for session: {session_id}")
    print(f"{'='*70}\n")

    # Step 1: Verify BEFORE
    print("📊 BEFORE FIX:")
    print("-" * 70)
    before = verify_session_detections(session_id)

    if 'error' in before:
        print(f"❌ Error: {before['error']}")
        return False

    # Step 2: Apply fix
    print(f"\n🔧 APPLYING FIX:")
    print("-" * 70)
    result = fix_video_id_for_session(session_id)

    if 'error' in result:
        print(f"❌ Error: {result['error']}")
        return False

    # Step 3: Verify AFTER
    print(f"\n✅ AFTER FIX:")
    print("-" * 70)
    after = verify_session_detections(session_id)

    # Step 4: Summary
    print(f"\n{'='*70}")
    print("📈 SUMMARY")
    print(f"{'='*70}")
    print(f"Session ID: {session_id}")
    print(f"Session video_id: {before['session_video_id']}")
    print(f"Total detections: {before['total_detections']}")
    print(f"\nBEFORE:")
    print(f"  - With video_id: {before['with_video_id']}")
    print(f"  - Without video_id: {before['without_video_id']}")
    print(f"  - Correct video_id: {before['correct_video_id']}")
    print(f"  - Wrong video_id: {before['wrong_video_id']}")
    print(f"\nAFTER:")
    print(f"  - With video_id: {after['with_video_id']}")
    print(f"  - Without video_id: {after['without_video_id']}")
    print(f"  - Correct video_id: {after['correct_video_id']}")
    print(f"  - Wrong video_id: {after['wrong_video_id']}")
    print(f"\nCHANGES:")
    print(f"  - Detections updated: {result['detections_updated']}")
    print(f"  - NULL reduced by: {before['without_video_id'] - after['without_video_id']}")

    success = after['status'] == 'OK'

    if success:
        print(f"\n✅ TEST PASSED: All detections have correct video_id!")
    else:
        print(f"\n❌ TEST FAILED: Still have issues")
        print(f"   - Remaining NULL: {after['without_video_id']}")
        print(f"   - Wrong video_id: {after['wrong_video_id']}")

    print(f"{'='*70}\n")

    return success


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Test video_id fix')
    parser.add_argument(
        '--session-id',
        default='daad8bf6-b5da-4423-abc4-a85e83bc1c16',
        help='Session ID to test (default: daad8bf6-b5da-4423-abc4-a85e83bc1c16)'
    )

    args = parser.parse_args()

    success = test_fix_for_session(args.session_id)

    sys.exit(0 if success else 1)
