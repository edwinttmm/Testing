#!/usr/bin/env python3
"""
Verification script for multi-video latency calculation fix.

This script verifies that the fix correctly:
1. Disables calibration offset for multi-video sequences
2. Uses the current video's start time (not session's first video)
3. Produces correct latency values for video 2 detections
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import TestSession, DetectionEvent as DBDetectionEvent
from datetime import datetime
from services.labjack_detection_service import get_detection_service
import json

def test_multi_video_latency_fix():
    """Test that multi-video sequences disable calibration and use correct video start times"""

    print("=" * 80)
    print("MULTI-VIDEO LATENCY CALCULATION FIX VERIFICATION")
    print("=" * 80)

    db = SessionLocal()
    try:
        # Find a multi-video session with detections
        sessions = db.query(TestSession).filter(
            TestSession.sequence_id.isnot(None)
        ).all()

        test_session = None
        for session in sessions:
            det_count = db.query(DBDetectionEvent).filter(
                DBDetectionEvent.test_session_id == session.id
            ).count()

            if det_count > 0:
                metadata = session.sequence_metadata
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)

                if metadata and metadata.get('video_timing') and len(metadata['video_timing']) >= 2:
                    test_session = session
                    break

        if not test_session:
            print("❌ No suitable multi-video session found for testing")
            return False

        print(f"\n✅ Testing with session: {test_session.id}")

        # Parse metadata
        metadata = test_session.sequence_metadata
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        video_timing = metadata['video_timing']
        video_ids = list(video_timing.keys())

        print(f"Videos in sequence: {len(video_ids)}")
        for i, vid in enumerate(video_ids):
            print(f"  Video {i+1} ({vid}): start={video_timing[vid]['started_at']}")

        # Create a test detection event for video 2
        detection_service = get_detection_service()

        # Simulate a detection for video 2
        video_2_id = video_ids[1]
        video_2_start = video_timing[video_2_id]['started_at']

        # Create a detection 4.5 seconds after video 2 starts
        detection_timestamp = datetime.fromtimestamp(video_2_start + 4.5)

        print(f"\n📊 Simulating detection for Video 2:")
        print(f"  Video 2 start time: {video_2_start}")
        print(f"  Detection timestamp: {detection_timestamp.timestamp()}")
        print(f"  Expected video-relative time: 4.500s")
        print(f"  Expected latency: 4550ms (4500ms + 50ms system latency)")

        # Create detection event
        event = detection_service._create_detection_event(
            session_id=test_session.id,
            channel="AIN0",
            voltage=3.3,
            threshold=2.5,
            timestamp=detection_timestamp
        )

        print(f"\n✅ Detection event created:")
        print(f"  video_relative_timestamp: {event.video_relative_timestamp:.6f}s")
        print(f"  actual_latency_ms: {event.actual_latency_ms:.1f}ms")
        print(f"  calibration_offset_ms: {event.metadata.get('calibration_offset_ms', 'N/A')}")

        # Verify results
        expected_relative = 4.5
        expected_latency = 4550.0  # 4500ms + 50ms system latency

        relative_error = abs(event.video_relative_timestamp - expected_relative)
        latency_error = abs(event.actual_latency_ms - expected_latency)

        print(f"\n📈 Verification Results:")
        print(f"  Relative timestamp error: {relative_error:.6f}s")
        print(f"  Latency error: {latency_error:.1f}ms")
        print(f"  Calibration disabled: {event.metadata.get('calibration_offset_ms') == 0.0}")

        # Success criteria
        success = (
            relative_error < 0.001 and  # Less than 1ms error
            latency_error < 10.0 and  # Less than 10ms error
            event.metadata.get('calibration_offset_ms') == 0.0  # Calibration disabled
        )

        if success:
            print(f"\n✅ TEST PASSED: Multi-video latency calculation is correct!")
            print(f"   - Calibration offset correctly disabled for multi-video sequence")
            print(f"   - Video-relative timestamp within tolerance")
            print(f"   - Latency calculation accurate")
            return True
        else:
            print(f"\n❌ TEST FAILED:")
            if relative_error >= 0.001:
                print(f"   - Video-relative timestamp error too high: {relative_error:.6f}s")
            if latency_error >= 10.0:
                print(f"   - Latency calculation error too high: {latency_error:.1f}ms")
            if event.metadata.get('calibration_offset_ms') != 0.0:
                print(f"   - Calibration not disabled: {event.metadata.get('calibration_offset_ms')}")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_multi_video_latency_fix()
    sys.exit(0 if success else 1)
