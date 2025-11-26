#!/usr/bin/env python3
"""
Detection Capture Rate Validation Script

This script validates detection capture rate improvements after optimization fixes.
It measures:
- Detection-to-GT frame matching rate
- Frame number calculation success rate
- Overall detection capture percentage

Usage:
    python scripts/validate_detection_rate.py <session_id>
    python scripts/validate_detection_rate.py --all  # Check all sessions

Author: Detection Optimization Specialist
Date: 2025-11-20
"""

import sys
import os
import logging
from typing import Dict, List, Tuple
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import DetectionEvent, GroundTruthObject, TestSession, Video
from sqlalchemy import func, and_, or_

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DetectionRateValidator:
    """Validates detection capture rate and frame number assignment"""

    def __init__(self):
        self.db = SessionLocal()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()

    def validate_session(self, session_id: str) -> Dict:
        """
        Validate detection capture rate for a specific test session.

        Args:
            session_id: Test session ID to validate

        Returns:
            Dictionary containing validation metrics
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"VALIDATING SESSION: {session_id}")
        logger.info(f"{'='*80}\n")

        # Get session info
        session = self.db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            logger.error(f"❌ Session not found: {session_id}")
            return {}

        logger.info(f"Session: {session.id}")
        logger.info(f"Status: {session.status}")
        logger.info(f"Created: {session.created_at}")

        # Get all detection events for this session
        detections = self.db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).all()

        total_detections = len(detections)
        logger.info(f"\n📊 DETECTION EVENTS ANALYSIS")
        logger.info(f"Total Detections: {total_detections}")

        if total_detections == 0:
            logger.warning("⚠️ No detections found for this session")
            return {
                'session_id': session_id,
                'total_detections': 0,
                'frame_number_success_rate': 0,
                'capture_rate': 0
            }

        # Analyze frame number assignment
        detections_with_frame = sum(1 for d in detections if d.frame_number and d.frame_number > 0)
        detections_without_frame = total_detections - detections_with_frame
        frame_success_rate = (detections_with_frame / total_detections * 100) if total_detections > 0 else 0

        logger.info(f"\n📋 FRAME NUMBER ASSIGNMENT:")
        logger.info(f"  ✅ With Frame Numbers: {detections_with_frame} ({frame_success_rate:.1f}%)")
        logger.info(f"  ❌ Missing Frame Numbers: {detections_without_frame} ({100-frame_success_rate:.1f}%)")

        # Analyze video-relative timestamps
        detections_with_video_time = sum(
            1 for d in detections
            if d.video_relative_timestamp is not None
        )
        video_time_rate = (detections_with_video_time / total_detections * 100) if total_detections > 0 else 0

        logger.info(f"\n🕒 VIDEO-RELATIVE TIMESTAMPS:")
        logger.info(f"  ✅ With Video Time: {detections_with_video_time} ({video_time_rate:.1f}%)")
        logger.info(f"  ❌ Missing Video Time: {total_detections - detections_with_video_time}")

        # Get ground truth data
        gt_objects = self.db.query(GroundTruthObject).join(
            Video
        ).filter(
            Video.project_id == session.project_id
        ).all()

        # Get unique GT frames (exclude corrupted frame 0 with multiple timestamps)
        gt_frames_query = self.db.query(
            GroundTruthObject.frame_number
        ).join(Video).filter(
            Video.project_id == session.project_id,
            GroundTruthObject.frame_number > 0  # Exclude potentially corrupted frame 0
        ).group_by(
            GroundTruthObject.frame_number
        ).all()

        total_gt_frames = len(gt_frames_query)
        logger.info(f"\n📍 GROUND TRUTH FRAMES:")
        logger.info(f"Total GT Frames: {total_gt_frames} (excluding frame 0)")
        logger.info(f"Total GT Objects: {len(gt_objects)}")

        if total_gt_frames == 0:
            logger.warning("⚠️ No ground truth frames found")
            return {
                'session_id': session_id,
                'total_detections': total_detections,
                'detections_with_frame': detections_with_frame,
                'frame_number_success_rate': frame_success_rate,
                'capture_rate': 0
            }

        # Match detections to GT frames
        gt_frame_numbers = {row[0] for row in gt_frames_query}
        detection_frame_numbers = {d.frame_number for d in detections if d.frame_number and d.frame_number > 0}

        matched_frames = gt_frame_numbers.intersection(detection_frame_numbers)
        unmatched_frames = gt_frame_numbers.difference(detection_frame_numbers)

        capture_rate = (len(matched_frames) / total_gt_frames * 100) if total_gt_frames > 0 else 0

        logger.info(f"\n🎯 DETECTION-TO-GT MATCHING:")
        logger.info(f"  ✅ GT Frames with Detections: {len(matched_frames)}/{total_gt_frames} ({capture_rate:.1f}%)")
        logger.info(f"  ❌ GT Frames without Detections: {len(unmatched_frames)}")

        # Sample matched frames
        if matched_frames:
            sample_matches = sorted(list(matched_frames))[:10]
            logger.info(f"\n  Sample Matched Frames: {sample_matches}")

        # Sample unmatched frames
        if unmatched_frames:
            sample_unmatched = sorted(list(unmatched_frames))[:10]
            logger.info(f"  Sample Unmatched Frames: {sample_unmatched}")

        # Detection timestamp distribution
        if detections:
            timestamps = [d.timestamp for d in detections if d.timestamp]
            if timestamps:
                min_ts = min(timestamps)
                max_ts = max(timestamps)
                duration = max_ts - min_ts
                logger.info(f"\n⏱️  DETECTION TIMING:")
                logger.info(f"  Time Range: {min_ts:.3f}s - {max_ts:.3f}s")
                logger.info(f"  Duration: {duration:.3f}s")
                logger.info(f"  Detection Rate: {total_detections/duration:.1f} detections/sec")

        # Overall assessment
        logger.info(f"\n{'='*80}")
        logger.info(f"VALIDATION SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Frame Number Assignment: {frame_success_rate:.1f}% (Target: >95%)")
        logger.info(f"Detection Capture Rate: {capture_rate:.1f}% (Target: >95%)")

        status_emoji = "✅" if capture_rate >= 95 and frame_success_rate >= 95 else "⚠️" if capture_rate >= 80 else "❌"
        logger.info(f"\nOverall Status: {status_emoji}")

        if capture_rate >= 95 and frame_success_rate >= 95:
            logger.info("🎉 EXCELLENT: System meeting target performance!")
        elif capture_rate >= 80:
            logger.info("⚠️  ACCEPTABLE: System above 80% but below target")
        else:
            logger.info("❌ NEEDS IMPROVEMENT: System below 80% capture rate")

        return {
            'session_id': session_id,
            'total_detections': total_detections,
            'detections_with_frame': detections_with_frame,
            'detections_without_frame': detections_without_frame,
            'frame_number_success_rate': frame_success_rate,
            'total_gt_frames': total_gt_frames,
            'matched_frames': len(matched_frames),
            'unmatched_frames': len(unmatched_frames),
            'capture_rate': capture_rate,
            'video_time_rate': video_time_rate,
            'timestamp': datetime.utcnow().isoformat()
        }

    def validate_all_sessions(self) -> List[Dict]:
        """Validate all test sessions in the database"""
        sessions = self.db.query(TestSession).filter(
            TestSession.status.in_(['completed', 'running'])
        ).all()

        logger.info(f"\n{'='*80}")
        logger.info(f"VALIDATING ALL SESSIONS ({len(sessions)} total)")
        logger.info(f"{'='*80}\n")

        results = []
        for session in sessions:
            result = self.validate_session(session.id)
            results.append(result)
            logger.info("")  # Blank line between sessions

        # Summary statistics
        if results:
            avg_capture = sum(r.get('capture_rate', 0) for r in results) / len(results)
            avg_frame_success = sum(r.get('frame_number_success_rate', 0) for r in results) / len(results)

            logger.info(f"\n{'='*80}")
            logger.info(f"AGGREGATE STATISTICS")
            logger.info(f"{'='*80}")
            logger.info(f"Total Sessions Analyzed: {len(results)}")
            logger.info(f"Average Capture Rate: {avg_capture:.1f}%")
            logger.info(f"Average Frame Success Rate: {avg_frame_success:.1f}%")

            high_performance = sum(1 for r in results if r.get('capture_rate', 0) >= 95)
            logger.info(f"High Performance Sessions (≥95%): {high_performance}/{len(results)}")

        return results


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_detection_rate.py <session_id>")
        print("       python scripts/validate_detection_rate.py --all")
        sys.exit(1)

    with DetectionRateValidator() as validator:
        if sys.argv[1] == '--all':
            validator.validate_all_sessions()
        else:
            session_id = sys.argv[1]
            validator.validate_session(session_id)


if __name__ == '__main__':
    main()
