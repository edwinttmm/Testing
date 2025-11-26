#!/usr/bin/env python3
"""
Analyze video_id mismatches in detections.

This script identifies which video_ids are assigned to detections
and determines if they are correct based on the session configuration.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, distinct
from database import SessionLocal
from models import DetectionEvent, TestSession

def analyze_session_video_ids(session_id: str):
    """Analyze video_id distribution for a session."""

    db = SessionLocal()
    try:
        # Get session info
        session = db.query(TestSession).filter(TestSession.id == session_id).first()

        if not session:
            print(f"❌ Session not found: {session_id}")
            return

        print(f"\n{'='*70}")
        print(f"Session Analysis: {session_id}")
        print(f"{'='*70}")
        print(f"Session video_id: {session.video_id}")
        print(f"Has video sequence: {session.has_video_sequence}")
        print(f"Session status: {session.status}")

        # Get all unique video_ids in detections
        video_id_counts = db.query(
            DetectionEvent.video_id,
            func.count(DetectionEvent.id).label('count')
        ).filter(
            DetectionEvent.test_session_id == session_id
        ).group_by(
            DetectionEvent.video_id
        ).all()

        print(f"\n📊 Video ID Distribution:")
        print("-" * 70)

        total = 0
        for video_id, count in video_id_counts:
            is_correct = (video_id == session.video_id)
            status = "✅" if is_correct else "❌"
            null_marker = " (NULL)" if video_id is None else ""

            print(f"{status} {video_id}{null_marker}: {count} detections")
            total += count

        print(f"\nTotal detections: {total}")

        # Check if this is a multi-video session
        if session.has_video_sequence:
            print(f"\n⚠️ This is a MULTI-VIDEO session!")
            print("Detections may legitimately have different video_ids based on timing.")

            # Try to find the sequence
            from models import VideoTestSequence, SequenceVideoResult

            sequence = db.query(VideoTestSequence).filter(
                VideoTestSequence.test_session_id == session_id
            ).first()

            if sequence:
                print(f"\n📹 Video Sequence Found:")
                print(f"   Sequence ID: {sequence.id}")

                # Query sequence video results - using correct model and field names
                results = db.query(SequenceVideoResult).filter(
                    SequenceVideoResult.video_sequence_id == sequence.id
                ).order_by(SequenceVideoResult.sequence_order).all()

                print(f"   Total videos: {len(results)}")
                print(f"\n   Videos in sequence:")
                for result in results:
                    det_count = db.query(func.count(DetectionEvent.id)).filter(
                        DetectionEvent.test_session_id == session_id,
                        DetectionEvent.video_id == result.video_id
                    ).scalar()

                    is_session_video = (result.video_id == session.video_id)
                    marker = " ⭐ (session video_id)" if is_session_video else ""

                    print(f"     Position {result.sequence_order}: {result.video_id} ({det_count} detections){marker}")

        # Sample some detections to see their timestamps
        print(f"\n📋 Sample Detections (first 5):")
        print("-" * 70)

        samples = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).order_by(DetectionEvent.timestamp).limit(5).all()

        for det in samples:
            is_correct = (det.video_id == session.video_id)
            status = "✅" if is_correct else "❌"
            print(f"{status} Detection {det.id[:8]}...")
            print(f"   video_id: {det.video_id}")
            print(f"   timestamp: {det.timestamp}")
            print(f"   validation_result: {det.validation_result}")
            print()

    finally:
        db.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Analyze video_id mismatches')
    parser.add_argument(
        '--session-id',
        default='daad8bf6-b5da-4423-abc4-a85e83bc1c16',
        help='Session ID to analyze'
    )

    args = parser.parse_args()

    analyze_session_video_ids(args.session_id)
