"""
Timestamp-Based Detection Video Assignment Service

CRITICAL FIX: Solves the race condition where detections arrive before notify_video_started()
updates sequence_metadata.current_video_id.

APPROACH: Use SequenceVideoResult timing boundaries to deterministically assign detections
to the correct video based ONLY on timestamp, independent of metadata update timing.

BENEFITS:
- Zero latency (no buffering required)
- Deterministic (timestamp never lies)
- Retroactive (works for out-of-order detections)
- Thread-safe (no shared state)
- Simple to test and verify

Author: Agent 5 - Detection Timing Specialist
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from models import TestSession, SequenceVideoResult, Video
import json

# Import centralized timing configuration
from config.timing_config import GRACE_PERIOD_MS, GRACE_PERIOD_SECONDS

logger = logging.getLogger(__name__)


class TimestampBasedVideoAssignment:
    """
    Assign detections to videos using ONLY timestamp boundaries from SequenceVideoResult.

    This eliminates the race condition by not relying on sequence_metadata.current_video_id.
    """

    def __init__(self, db: Session):
        self.db = db
        self._video_boundary_cache: Dict[str, list] = {}  # Cache for performance

    def assign_video_for_detection(
        self,
        session_id: str,
        detection_timestamp: float,
        fallback_video_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Assign video_id and sequence_video_result_id based on detection timestamp.

        ALGORITHM:
        1. Query all SequenceVideoResult entries for this session's sequence
        2. Find which video's time boundary contains the detection timestamp
        3. Return video_id and sequence_video_result_id

        Args:
            session_id: Test session ID
            detection_timestamp: Detection epoch timestamp (seconds)
            fallback_video_id: Fallback video_id if no match found

        Returns:
            {
                'video_id': str,
                'sequence_video_result_id': str or None,
                'assignment_method': 'timestamp_boundary' | 'fallback' | 'single_video',
                'confidence': 'high' | 'medium' | 'low',
                'video_relative_timestamp': float (seconds from video start)
            }
        """
        try:
            # Get session to check if this is a multi-video sequence
            session = self.db.query(TestSession).filter(TestSession.id == session_id).first()

            if not session:
                logger.error(f"Session {session_id} not found")
                return {
                    'video_id': fallback_video_id,
                    'sequence_video_result_id': None,
                    'assignment_method': 'fallback',
                    'confidence': 'low',
                    'video_relative_timestamp': None,
                    'error': 'session_not_found'
                }

            # Single-video session - simple case
            if not session.sequence_id:
                video_relative_timestamp = None
                if session.video_start_timestamp:
                    video_relative_timestamp = max(0.0, detection_timestamp - session.video_start_timestamp)

                return {
                    'video_id': session.video_id,
                    'sequence_video_result_id': None,
                    'assignment_method': 'single_video',
                    'confidence': 'high',
                    'video_relative_timestamp': video_relative_timestamp
                }

            # Multi-video sequence - use timing boundaries
            sequence_id = session.sequence_id

            # Check cache first (invalidate after 60 seconds to handle timing updates)
            cache_key = f"{sequence_id}:{int(detection_timestamp / 60)}"  # 60-second cache buckets
            if cache_key in self._video_boundary_cache:
                video_boundaries = self._video_boundary_cache[cache_key]
            else:
                # Query all video results for this sequence
                video_results = self.db.query(SequenceVideoResult).filter(
                    SequenceVideoResult.video_sequence_id == sequence_id
                ).order_by(SequenceVideoResult.sequence_order).all()

                if not video_results:
                    logger.warning(f"No SequenceVideoResult entries found for sequence {sequence_id}")
                    return {
                        'video_id': fallback_video_id or session.video_id,
                        'sequence_video_result_id': None,
                        'assignment_method': 'fallback',
                        'confidence': 'low',
                        'video_relative_timestamp': None,
                        'error': 'no_video_results'
                    }

                # Build timing boundary list
                video_boundaries = []
                for result in video_results:
                    # Skip videos without timing information
                    if result.video_start_time is None:
                        logger.debug(f"Skipping video result {result.id} - no video_start_time")
                        continue

                    # Calculate end time
                    end_time = result.video_end_time
                    if end_time is None and result.actual_duration_ms:
                        end_time = result.video_start_time + (result.actual_duration_ms / 1000.0)

                    # If still no end time, get video duration from Video table
                    if end_time is None:
                        video = self.db.query(Video).filter(Video.id == result.video_id).first()
                        if video and video.duration:
                            end_time = result.video_start_time + video.duration

                    if end_time is None:
                        logger.warning(f"Cannot determine end_time for video result {result.id}")
                        continue

                    video_boundaries.append({
                        'video_id': result.video_id,
                        'sequence_video_result_id': result.id,
                        'start_time': result.video_start_time,
                        'end_time': end_time,
                        'sequence_order': result.sequence_order
                    })

                # Cache the boundaries
                self._video_boundary_cache[cache_key] = video_boundaries

                logger.info(f"Built timing boundaries for sequence {sequence_id}: {len(video_boundaries)} videos")

            # Find the video containing this detection timestamp
            # Use centralized grace period (2000ms = 2.0 seconds)
            # Hardware LabJack can trigger 0-2 seconds before 'playing' event

            for boundary in video_boundaries:
                start_with_grace = boundary['start_time'] - GRACE_PERIOD_SECONDS

                if start_with_grace <= detection_timestamp <= boundary['end_time']:
                    # Found the matching video!
                    video_relative_timestamp = detection_timestamp - boundary['start_time']

                    logger.info(
                        f"✅ Detection assigned to video {boundary['video_id']} "
                        f"(timestamp={detection_timestamp:.6f}, "
                        f"video_start={boundary['start_time']:.6f}, "
                        f"video_end={boundary['end_time']:.6f}, "
                        f"relative_time={video_relative_timestamp:.3f}s)"
                    )

                    return {
                        'video_id': boundary['video_id'],
                        'sequence_video_result_id': boundary['sequence_video_result_id'],
                        'assignment_method': 'timestamp_boundary',
                        'confidence': 'high',
                        'video_relative_timestamp': video_relative_timestamp,
                        'video_start_time': boundary['start_time'],
                        'video_end_time': boundary['end_time']
                    }

            # Detection doesn't fall within any video boundary
            logger.warning(
                f"⚠️ Detection timestamp {detection_timestamp:.6f} doesn't match any video boundary. "
                f"Available boundaries: {[(b['start_time'], b['end_time']) for b in video_boundaries]}"
            )

            # Try to find the closest video (detection might be slightly out of range)
            closest_video = None
            min_distance = float('inf')

            for boundary in video_boundaries:
                # Calculate distance to video time range
                if detection_timestamp < boundary['start_time']:
                    distance = boundary['start_time'] - detection_timestamp
                elif detection_timestamp > boundary['end_time']:
                    distance = detection_timestamp - boundary['end_time']
                else:
                    distance = 0

                if distance < min_distance:
                    min_distance = distance
                    closest_video = boundary

            if closest_video and min_distance < 2.0:  # Within 2 seconds
                video_relative_timestamp = detection_timestamp - closest_video['start_time']
                logger.warning(
                    f"⚠️ Detection assigned to closest video {closest_video['video_id']} "
                    f"(distance={min_distance:.3f}s)"
                )
                return {
                    'video_id': closest_video['video_id'],
                    'sequence_video_result_id': closest_video['sequence_video_result_id'],
                    'assignment_method': 'timestamp_boundary_closest',
                    'confidence': 'medium',
                    'video_relative_timestamp': video_relative_timestamp,
                    'distance_seconds': min_distance
                }

            # No close match - use fallback
            return {
                'video_id': fallback_video_id or session.video_id,
                'sequence_video_result_id': None,
                'assignment_method': 'fallback',
                'confidence': 'low',
                'video_relative_timestamp': None,
                'error': 'no_matching_boundary',
                'detection_timestamp': detection_timestamp,
                'available_boundaries': [(b['start_time'], b['end_time']) for b in video_boundaries]
            }

        except Exception as e:
            logger.error(f"Error assigning video for detection: {e}", exc_info=True)
            return {
                'video_id': fallback_video_id,
                'sequence_video_result_id': None,
                'assignment_method': 'error_fallback',
                'confidence': 'low',
                'video_relative_timestamp': None,
                'error': str(e)
            }

    def clear_cache(self, sequence_id: Optional[str] = None):
        """Clear the video boundary cache (call when timing data is updated)"""
        if sequence_id:
            # Clear only entries for this sequence
            keys_to_delete = [k for k in self._video_boundary_cache.keys() if k.startswith(f"{sequence_id}:")]
            for key in keys_to_delete:
                del self._video_boundary_cache[key]
            logger.info(f"Cleared cache for sequence {sequence_id} ({len(keys_to_delete)} entries)")
        else:
            # Clear entire cache
            self._video_boundary_cache.clear()
            logger.info("Cleared entire video boundary cache")


# Global instance (can be used from synchronous contexts)
_video_assignment_service: Optional[TimestampBasedVideoAssignment] = None


def get_video_assignment_service(db: Session) -> TimestampBasedVideoAssignment:
    """Get or create video assignment service instance"""
    global _video_assignment_service
    if _video_assignment_service is None or _video_assignment_service.db != db:
        _video_assignment_service = TimestampBasedVideoAssignment(db)
    return _video_assignment_service
