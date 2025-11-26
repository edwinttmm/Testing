"""
Video ID Resolver - Single Source of Truth for Detection Video Assignment

This module provides a simple, fast, database-backed video_id resolver that eliminates
the three uncoordinated sources of truth:
1. video_sequence_orchestrator._active_sequences (in-memory cache) - REPLACED
2. socketio_server in-memory state tracking - REPLACED
3. labjack_detection_service metadata extraction - REPLACED

Algorithm:
1. Query SequenceVideoResult for all videos in the session's sequence
2. Find video where: video_start_time <= timestamp < video_end_time
3. Return video_id (or None if no match)

Performance: <5ms with proper indexes
Complexity: ~50 lines
"""

import logging
import json
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import TestSession, SequenceVideoResult, VideoTestSequence, Video

logger = logging.getLogger(__name__)


def get_video_id_for_detection(
    session_id: str,
    detection_timestamp: float,
    db: Session
) -> Optional[str]:
    """
    Single source of truth for video_id assignment based on timestamp ranges.

    This function queries the database to find which video was active when
    the detection occurred, based on video_start_time and video_end_time.

    Args:
        session_id: Test session ID containing the detection
        detection_timestamp: Unix timestamp of the detection event
        db: SQLAlchemy database session

    Returns:
        video_id: ID of the video that was active at detection_timestamp
        None: If no video was active at that timestamp

    Performance:
        - <5ms query time with proper indexes
        - Single database query using composite index
        - No in-memory cache or state required

    Example:
        >>> video_id = get_video_id_for_detection(
        ...     session_id="abc123",
        ...     detection_timestamp=1699123456.789,
        ...     db=db_session
        ... )
        >>> if video_id:
        ...     print(f"Detection belongs to video: {video_id}")
    """

    def _coerce_timestamp(value: Optional[float]) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    try:
        # Get the test session to find the sequence
        session = db.query(TestSession).filter(
            TestSession.id == session_id
        ).first()

        if not session:
            logger.error(f"Session {session_id} not found")
            return None

        # If not a multi-video sequence, return the session's single video_id
        if not session.sequence_id:
            logger.debug(f"Single video session {session_id}, using video_id={session.video_id}")
            return session.video_id

        metadata_video_timing = {}
        ordered_video_ids = []
        raw_metadata = session.sequence_metadata or {}
        if raw_metadata:
            if isinstance(raw_metadata, str):
                try:
                    metadata = json.loads(raw_metadata)
                except json.JSONDecodeError:
                    metadata = {}
            elif isinstance(raw_metadata, dict):
                metadata = dict(raw_metadata)
            else:
                metadata = {}
            metadata_video_timing = metadata.get("video_timing", {}) or {}
            ordered_video_ids = metadata.get("video_ids", []) or []

        sequence_query = db.query(SequenceVideoResult).join(
            VideoTestSequence,
            SequenceVideoResult.video_sequence_id == VideoTestSequence.id
        ).filter(
            VideoTestSequence.test_session_id == session_id
        )

        sequence_results = sequence_query.order_by(SequenceVideoResult.sequence_order).all()
        results_by_video = {result.video_id: result for result in sequence_results}

        if ordered_video_ids:
            all_videos = [results_by_video.get(video_id) for video_id in ordered_video_ids]
        else:
            all_videos = sequence_results

        if not all_videos:
            logger.warning(f"No videos found in sequence for session {session_id}")
            return None

        # CRITICAL FIX #2: Implement tolerance window clamping
        # Each video gets a tolerance window AFTER its end time, but clamped
        # to not exceed the start of the next video
        tolerance_ms = 500  # Default tolerance window in milliseconds
        tolerance_seconds = tolerance_ms / 1000.0

        for idx, video_result in enumerate(all_videos):
            if video_result is None:
                # No DB row yet (likely planned video). Use metadata timing directly.
                video_id = ordered_video_ids[idx] if idx < len(ordered_video_ids) else None
                meta_entry = metadata_video_timing.get(video_id, {}) if video_id else {}
                start_time = meta_entry.get("started_at")
                end_time = meta_entry.get("ended_at")
                if start_time is None or end_time is None:
                    continue
                duration_s = (end_time - start_time) if end_time and start_time else None
                video_result = SequenceVideoResult(
                    video_id=video_id,
                    video_start_time=start_time,
                    video_end_time=end_time,
                    planned_duration_ms=int(duration_s * 1000) if duration_s else None,
                    actual_duration_ms=int(duration_s * 1000) if duration_s else None
                )
                all_videos[idx] = video_result
            else:
                video_id = video_result.video_id
            meta_entry = metadata_video_timing.get(video_id, {}) if video_id else {}
            start_time = _coerce_timestamp(video_result.video_start_time)
            end_time = _coerce_timestamp(video_result.video_end_time)
            if meta_entry:
                if start_time is None:
                    start_time = _coerce_timestamp(meta_entry.get("started_at"))
                if end_time is None:
                    end_time = _coerce_timestamp(meta_entry.get("ended_at"))

            if start_time is None or end_time is None:
                logger.warning(
                    "⚠️ Sequence video %s missing timing (start=%s, end=%s) - skipping resolver entry",
                    video_result.video_id,
                    start_time,
                    end_time
                )
                continue

            # Calculate max_end with clamping
            if idx < len(all_videos) - 1:
                # Not the last video: clamp tolerance to next video start
                next_video_obj = all_videos[idx + 1]
                next_video_id = getattr(next_video_obj, "video_id", None) if next_video_obj else None
                if not next_video_id and ordered_video_ids and idx + 1 < len(ordered_video_ids):
                    next_video_id = ordered_video_ids[idx + 1]
                next_video_start = _coerce_timestamp(
                    getattr(next_video_obj, "video_start_time", None)
                ) if next_video_obj else None
                if next_video_start is None and metadata_video_timing and next_video_id:
                    next_meta = metadata_video_timing.get(next_video_id)
                    if next_meta:
                        next_video_start = _coerce_timestamp(next_meta.get("started_at"))

                # CRITICAL: Tolerance window cannot extend into next video
                if next_video_start is not None:
                    max_end = min(end_time + tolerance_seconds, next_video_start)
                else:
                    max_end = end_time + tolerance_seconds

                logger.debug(
                    "Video %s clamped: original_end=%s, tolerance_end=%s, next_start=%s, clamped_end=%s",
                    idx,
                    f"{end_time:.3f}s" if end_time is not None else "None",
                    f"{(end_time + tolerance_seconds):.3f}s" if end_time is not None else "None",
                    f"{next_video_start:.3f}s" if next_video_start is not None else "None",
                    f"{max_end:.3f}s" if max_end is not None else "None",
                )
            else:
                # Last video: no clamping needed
                max_end = end_time + tolerance_seconds

            # Check if detection falls within [start, max_end)
            if start_time <= detection_timestamp < max_end:
                logger.debug(
                    f"Detection at {detection_timestamp:.3f}s matched video_id={video_result.video_id} "
                    f"(range: {start_time:.3f}s - {max_end:.3f}s, "
                    f"original_end: {end_time:.3f}s)"
                )
                return video_result.video_id

        # FALLBACK: If detection is after all videos, assign to last video
        # This handles detections that occur slightly after the sequence ends
        last_video_obj = all_videos[-1]
        last_video_id = getattr(last_video_obj, "video_id", None)
        last_video_end = _coerce_timestamp(
            getattr(last_video_obj, "video_end_time", None)
        ) if last_video_obj else None
        if last_video_end is None and metadata_video_timing and last_video_id:
            meta_last = metadata_video_timing.get(last_video_id)
            if meta_last:
                last_video_end = _coerce_timestamp(meta_last.get("ended_at"))

        if last_video_end and detection_timestamp >= last_video_end:
            fallback_video_id = last_video_id
            logger.warning(
                f"Detection at {detection_timestamp:.3f}s is after all videos, "
                f"assigning to last video: {fallback_video_id}"
            )
            return fallback_video_id

        # No video found for this timestamp
        logger.warning(
            f"No video found for detection at timestamp {detection_timestamp:.3f} "
            f"in session {session_id}"
        )
        return None

    except Exception as e:
        logger.error(f"Error resolving video_id for detection: {e}", exc_info=True)
        return None


def get_sequence_video_result_id(
    session_id: str,
    video_id: str,
    db: Session
) -> Optional[str]:
    """
    Get the SequenceVideoResult ID for a specific video in a session.

    This is used to link DetectionEvents to the correct SequenceVideoResult.

    Args:
        session_id: Test session ID
        video_id: Video ID within the sequence
        db: SQLAlchemy database session

    Returns:
        sequence_video_result_id: ID of the SequenceVideoResult record
        None: If not found or not a multi-video sequence
    """

    try:
        session = db.query(TestSession).filter(
            TestSession.id == session_id
        ).first()

        if not session or not session.sequence_id:
            return None

        video_result = db.query(SequenceVideoResult).join(
            VideoTestSequence,
            SequenceVideoResult.video_sequence_id == VideoTestSequence.id
        ).filter(
            and_(
                VideoTestSequence.test_session_id == session_id,
                SequenceVideoResult.video_id == video_id
            )
        ).first()

        return video_result.id if video_result else None

    except Exception as e:
        logger.error(f"Error getting sequence_video_result_id: {e}", exc_info=True)
        return None
