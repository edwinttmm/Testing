"""
Timestamp-Based Video Assignment Service

Lightweight service that determines video_id from detection timestamp using
video timing boundaries from SequenceVideoResult table.

DESIGN:
- Query SequenceVideoResult for video start/end times
- Find video where: start_time <= detection_timestamp < end_time
- Handle edge cases (before start, after end, transitions)
- Provides validation/fallback for metadata-based assignment

PERFORMANCE TARGET: <5ms query time
DEPLOYMENT: Ready for immediate production use
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import SequenceVideoResult, VideoTestSequence, TestSession, Video

logger = logging.getLogger(__name__)


@dataclass
class VideoTimingWindow:
    """Video timing window with metadata"""
    video_id: str
    video_start_time: float
    video_end_time: Optional[float]
    sequence_order: int
    filename: str
    duration: float


class TimestampVideoResolver:
    """
    Resolves video_id from detection timestamp using timing boundaries.

    This service provides authoritative video assignment based on actual
    timing data, serving as validation for metadata-based approaches.
    """

    # Buffer for video transitions (milliseconds)
    TRANSITION_BUFFER_MS = 100

    def __init__(self):
        logger.info("TimestampVideoResolver initialized")

    def get_video_id_from_timestamp(
        self,
        session_id: str,
        detection_timestamp: float,
        db: Session
    ) -> Optional[str]:
        """
        Determine which video was playing at detection time.

        Algorithm:
        1. Query all videos in sequence with start/end times
        2. Find video where: start_time <= timestamp < end_time
        3. Handle edge cases (before start, after end, during transition)
        4. Return video_id or None

        Args:
            session_id: Test session identifier
            detection_timestamp: Unix timestamp of detection (seconds)
            db: Database session

        Returns:
            video_id if found, None otherwise
        """
        try:
            # Get video timing windows for session
            windows = self._get_video_timing_windows(session_id, db)

            if not windows:
                logger.warning(f"No video timing windows found for session {session_id}")
                return None

            # Find matching video
            video_id = self._find_video_by_timestamp(detection_timestamp, windows)

            if video_id:
                logger.debug(f"✅ Resolved video_id={video_id} for timestamp={detection_timestamp:.6f}")
            else:
                logger.warning(
                    f"❌ No video found for timestamp={detection_timestamp:.6f} "
                    f"(windows: {len(windows)})"
                )

            return video_id

        except Exception as e:
            logger.error(f"Failed to resolve video from timestamp: {e}")
            return None

    def validate_video_assignment(
        self,
        session_id: str,
        detection_timestamp: float,
        metadata_video_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Validate metadata-based video assignment against timestamp-based resolution.

        Args:
            session_id: Test session ID
            detection_timestamp: Detection timestamp
            metadata_video_id: Video ID from metadata
            db: Database session

        Returns:
            Validation result with reconciliation status
        """
        try:
            # Get timestamp-based resolution (authoritative)
            timestamp_video_id = self.get_video_id_from_timestamp(
                session_id, detection_timestamp, db
            )

            # Compare results
            matches = (metadata_video_id == timestamp_video_id)

            result = {
                'matches': matches,
                'metadata_video_id': metadata_video_id,
                'timestamp_video_id': timestamp_video_id,
                'authoritative_video_id': timestamp_video_id,  # Trust timestamp
                'detection_timestamp': detection_timestamp
            }

            if not matches:
                logger.warning(
                    f"⚠️ VIDEO ID MISMATCH: "
                    f"metadata={metadata_video_id}, timestamp={timestamp_video_id} "
                    f"at t={detection_timestamp:.6f}"
                )
            else:
                logger.debug(
                    f"✅ Video ID validated: {metadata_video_id} "
                    f"at t={detection_timestamp:.6f}"
                )

            return result

        except Exception as e:
            logger.error(f"Failed to validate video assignment: {e}")
            return {
                'matches': False,
                'error': str(e),
                'metadata_video_id': metadata_video_id,
                'timestamp_video_id': None,
                'authoritative_video_id': metadata_video_id  # Fallback to metadata
            }

    def _get_video_timing_windows(
        self,
        session_id: str,
        db: Session
    ) -> List[VideoTimingWindow]:
        """
        Query video timing windows from database.

        Returns ordered list of video timing windows with start/end times.
        """
        try:
            # Get test session to find sequence_id
            session = db.query(TestSession).filter(
                TestSession.id == session_id
            ).first()

            if not session:
                logger.error(f"Session {session_id} not found")
                return []

            if not session.sequence_id:
                # Single-video session - use session video_id
                if session.video_id and session.video_start_timestamp:
                    video = db.query(Video).filter(Video.id == session.video_id).first()
                    if video:
                        return [VideoTimingWindow(
                            video_id=session.video_id,
                            video_start_time=session.video_start_timestamp,
                            video_end_time=(
                                session.video_start_timestamp + video.duration
                                if video.duration else None
                            ),
                            sequence_order=0,
                            filename=video.filename,
                            duration=video.duration or 0.0
                        )]

                logger.warning(f"Session {session_id} has no sequence_id or video timing")
                return []

            # Multi-video sequence - query SequenceVideoResult
            video_results = db.query(SequenceVideoResult).filter(
                SequenceVideoResult.video_sequence_id == session.sequence_id
            ).order_by(SequenceVideoResult.sequence_order).all()

            if not video_results:
                logger.warning(f"No video results found for sequence {session.sequence_id}")
                return []

            # Get video metadata
            video_ids = [vr.video_id for vr in video_results]
            videos = {
                v.id: v for v in db.query(Video).filter(Video.id.in_(video_ids)).all()
            }

            # Build timing windows
            windows = []
            for vr in video_results:
                video = videos.get(vr.video_id)
                if not video:
                    continue

                # Skip videos without start time
                if vr.video_start_time is None:
                    logger.debug(f"Skipping video {vr.video_id} - no start time")
                    continue

                windows.append(VideoTimingWindow(
                    video_id=vr.video_id,
                    video_start_time=vr.video_start_time,
                    video_end_time=vr.video_end_time,
                    sequence_order=vr.sequence_order,
                    filename=video.filename,
                    duration=video.duration or 0.0
                ))

            logger.debug(f"Loaded {len(windows)} video timing windows for session {session_id}")
            return windows

        except Exception as e:
            logger.error(f"Failed to load video timing windows: {e}")
            return []

    def _find_video_by_timestamp(
        self,
        timestamp: float,
        windows: List[VideoTimingWindow]
    ) -> Optional[str]:
        """
        Find video whose timing window contains the timestamp.

        Edge cases:
        - Detection before first video: Return first video if within buffer
        - Detection during transition: Use transition buffer
        - Detection after last video: Return last video if within buffer
        """
        if not windows:
            return None

        # Convert buffer to seconds
        buffer_seconds = self.TRANSITION_BUFFER_MS / 1000.0

        # Check each video window
        for window in windows:
            # Determine effective end time
            if window.video_end_time is not None:
                effective_end = window.video_end_time
            else:
                # For currently playing video, use start + duration + buffer
                effective_end = window.video_start_time + window.duration + buffer_seconds

            # Check if timestamp falls within window (with buffer)
            if (window.video_start_time - buffer_seconds) <= timestamp < (effective_end + buffer_seconds):
                return window.video_id

        # Edge case: Detection before first video
        first_window = windows[0]
        if timestamp < first_window.video_start_time:
            # Within grace period before first video?
            if (first_window.video_start_time - timestamp) <= buffer_seconds:
                logger.warning(
                    f"Detection {(first_window.video_start_time - timestamp)*1000:.1f}ms "
                    f"before first video - assigning to first video"
                )
                return first_window.video_id
            else:
                logger.warning(
                    f"Detection {(first_window.video_start_time - timestamp)*1000:.1f}ms "
                    f"before first video (outside buffer)"
                )
                return None

        # Edge case: Detection after last video
        last_window = windows[-1]
        if last_window.video_end_time and timestamp >= last_window.video_end_time:
            # Within grace period after last video?
            if (timestamp - last_window.video_end_time) <= buffer_seconds:
                logger.warning(
                    f"Detection {(timestamp - last_window.video_end_time)*1000:.1f}ms "
                    f"after last video - assigning to last video"
                )
                return last_window.video_id
            else:
                logger.warning(
                    f"Detection {(timestamp - last_window.video_end_time)*1000:.1f}ms "
                    f"after last video (outside buffer)"
                )
                return None

        # No match found
        logger.warning(
            f"No video window contains timestamp {timestamp:.6f} "
            f"(first: {first_window.video_start_time:.6f}, "
            f"last: {last_window.video_end_time or 'N/A'})"
        )
        return None

    def get_diagnostic_info(
        self,
        session_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Get diagnostic information about video timing windows.

        Useful for debugging timing issues.
        """
        try:
            windows = self._get_video_timing_windows(session_id, db)

            return {
                'session_id': session_id,
                'window_count': len(windows),
                'windows': [
                    {
                        'video_id': w.video_id,
                        'filename': w.filename,
                        'sequence_order': w.sequence_order,
                        'video_start_time': w.video_start_time,
                        'video_end_time': w.video_end_time,
                        'duration': w.duration,
                        'time_range': f"[{w.video_start_time:.6f}, {w.video_end_time:.6f})" if w.video_end_time else f"[{w.video_start_time:.6f}, ?)"
                    }
                    for w in windows
                ]
            }

        except Exception as e:
            logger.error(f"Failed to get diagnostic info: {e}")
            return {'error': str(e)}


# Global service instance
_resolver_service: Optional[TimestampVideoResolver] = None


def get_timestamp_video_resolver() -> TimestampVideoResolver:
    """Get global resolver service instance (singleton)"""
    global _resolver_service

    if _resolver_service is None:
        _resolver_service = TimestampVideoResolver()

    return _resolver_service
