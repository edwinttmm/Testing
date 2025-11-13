"""
Background job to reassign video_id to detections based on timing analysis.

This service fixes detections that were stored with NULL video_id due to race conditions
where detection events arrived before video lifecycle events (onPlay) were processed.

The fix retrospectively assigns video_id to detections using:
1. Video timing boundaries from SequenceVideoResult records
2. Detection timestamp analysis to determine which video was playing
3. Per-video time ranges calculated from video_start_time and duration

Architecture:
- Uses video_start_time and actual_duration_ms from SequenceVideoResult
- Matches detection timestamps to video time windows
- Handles multi-video sequences correctly
- Provides detailed logging for debugging
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database import SessionLocal
from models import (
    TestSession,
    DetectionEvent,
    SequenceVideoResult,
    VideoTestSequence,
    Video
)

logger = logging.getLogger(__name__)


class DetectionVideoReassignmentService:
    """Service for reassigning video_id to detections based on timing analysis."""

    def __init__(self):
        """Initialize the reassignment service."""
        self.logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def _select_first_value(*candidates):
        """Return the first non-None value from candidates."""
        for value in candidates:
            if value is not None:
                return value
        return None

    @staticmethod
    def _to_timestamp(value: Optional[Any]) -> Optional[float]:
        """Convert datetime or numeric values to float timestamp."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, datetime):
            return value.timestamp()
        if hasattr(value, "timestamp"):
            try:
                return float(value.timestamp())
            except Exception:
                return None
        return None

    async def reassign_null_video_ids(
        self,
        session_id: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Reassign video_id to detections that were stored with NULL.

        Uses video timing boundaries to determine correct video_id.

        Args:
            session_id: Test session ID to process
            dry_run: If True, only report what would be changed without modifying database

        Returns:
            Dict containing:
                - success: bool
                - reassigned_count: int (detections that previously had NULL video_id)
                - corrected_existing: int (detections whose video_id changed)
                - relative_time_updates: int (detections with updated relative timestamps)
                - total_detections: int
                - errors: List[str]
                - video_assignments: Dict[str, int] (video_id -> count)
        """
        db = SessionLocal()
        try:
            self.logger.info(f"Starting video_id reassignment for session {session_id} (dry_run={dry_run})")

            # Get test session with sequence information
            session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if not session:
                error_msg = f"Session {session_id} not found"
                self.logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "reassigned_count": 0,
                    "corrected_existing": 0,
                    "relative_time_updates": 0,
                    "total_detections": 0,
                    "video_assignments": {},
                    "errors": []
                }

            # Check if this is a multi-video sequence session
            if not session.has_video_sequence or not session.sequence_id:
                self.logger.info(f"Session {session_id} is not a multi-video sequence - no reassignment needed")
                return {
                    "success": True,
                    "message": "Not a multi-video sequence session",
                    "reassigned_count": 0,
                    "corrected_existing": 0,
                    "relative_time_updates": 0,
                    "total_detections": 0,
                    "video_assignments": {},
                    "errors": []
                }

            # Get video sequence
            video_sequence = db.query(VideoTestSequence).filter(
                VideoTestSequence.id == session.sequence_id
            ).first()

            if not video_sequence:
                error_msg = f"Video sequence {session.sequence_id} not found"
                self.logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "reassigned_count": 0,
                    "corrected_existing": 0,
                    "relative_time_updates": 0,
                    "total_detections": 0,
                    "video_assignments": {},
                    "errors": []
                }

            # Get video timing boundaries from SequenceVideoResult
            video_results = db.query(SequenceVideoResult).filter(
                SequenceVideoResult.video_sequence_id == video_sequence.id
            ).order_by(SequenceVideoResult.sequence_order).all()

            if not video_results:
                error_msg = f"No video results found for sequence {video_sequence.id}"
                self.logger.warning(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "reassigned_count": 0,
                    "corrected_existing": 0,
                    "relative_time_updates": 0,
                    "total_detections": 0,
                    "video_assignments": {},
                    "errors": []
                }

            # Build video timing map
            video_timing_map = self._build_video_timing_map(session, video_results, db)

            self.logger.info(f"Built video timing map for {len(video_timing_map)} videos:")
            for video_id, timing in video_timing_map.items():
                self.logger.info(
                    f"  Video {video_id}: {timing['start_time']:.3f}s - {timing['end_time']:.3f}s "
                    f"(duration: {timing['duration_s']:.2f}s, filename: {timing['filename']})"
                )

            if not video_timing_map:
                error_msg = "Unable to build video timing map - missing timing data"
                self.logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "reassigned_count": 0,
                    "total_detections": 0
                }

            # Build lookup data
            sequence_start_time = min(
                (timing["start_time"] for timing in video_timing_map.values() if timing["start_time"] is not None),
                default=None
            )

            video_result_lookup = {
                vr.video_id: vr.id for vr in video_results
            }

            detections = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id
            ).order_by(DetectionEvent.timestamp).all()

            total_detections = len(detections)
            self.logger.info(f"Processing {total_detections} detections for reassignment")

            # Analyse detection timestamps to correct inaccurate timing metadata
            earliest_overall: Optional[float] = None
            earliest_by_video: Dict[str, float] = {}
            for detection in detections:
                det_ts = self._to_timestamp(getattr(detection, "timestamp", None))
                det_vid = getattr(detection, "video_id", None)
                if det_ts is None or det_vid is None:
                    continue
                if earliest_overall is None or det_ts < earliest_overall:
                    earliest_overall = det_ts
                if det_vid not in earliest_by_video or det_ts < earliest_by_video[det_vid]:
                    earliest_by_video[det_vid] = det_ts

            if earliest_overall is not None:
                if sequence_start_time is None or sequence_start_time > earliest_overall:
                    self.logger.info(
                        f"Adjusting sequence_start_time from {sequence_start_time} to earliest detection {earliest_overall}"
                    )
                    sequence_start_time = earliest_overall

            # Tolerance window (0.5s) to detect obviously wrong start times
            start_time_tolerance = 0.5
            for video_id, timing in video_timing_map.items():
                earliest_ts = earliest_by_video.get(video_id)
                if earliest_ts is None:
                    continue
                start_time = timing.get("start_time")
                if start_time is None or start_time - earliest_ts > start_time_tolerance:
                    self.logger.info(
                        f"Adjusting start_time for video {video_id}: "
                        f"{start_time} -> {earliest_ts} based on earliest detection"
                    )
                    timing["start_time"] = earliest_ts
                # Recompute video_play_offset_ms when sequence_start_time is known
                if sequence_start_time is not None:
                    timing["video_play_offset_ms"] = max(
                        0.0, (timing["start_time"] - sequence_start_time) * 1000.0
                    )

            reassigned_null = 0
            corrected_existing = 0
            relative_time_updates = 0
            video_assignments: Dict[str, int] = {}
            errors: List[str] = []
            unmatched_detections: List[Dict[str, Any]] = []

            for detection in detections:
                try:
                    assigned_video_id = self._determine_video_from_timestamp(
                        detection=detection,
                        video_timing_map=video_timing_map
                    )

                    if not assigned_video_id:
                        unmatched_msg = (
                            f"Could not determine video for detection {detection.id} "
                            f"(timestamp: {detection.timestamp:.3f}s)"
                        )
                        self.logger.warning(unmatched_msg)
                        errors.append(unmatched_msg)
                        unmatched_detections.append({
                            "detection_id": detection.id,
                            "timestamp": detection.timestamp,
                            "video_relative_timestamp": detection.video_relative_timestamp
                        })
                        continue

                    timing_info = video_timing_map[assigned_video_id]
                    start_time = timing_info["start_time"]
                    video_offset_ms = timing_info.get("video_play_offset_ms")
                    if video_offset_ms is not None and detection.video_play_offset_ms != video_offset_ms and not dry_run:
                        detection.video_play_offset_ms = video_offset_ms

                    # Update relative timestamp fields where possible
                    if start_time is not None and detection.timestamp is not None:
                        new_relative = max(0.0, detection.timestamp - start_time)
                        if detection.video_relative_timestamp != new_relative:
                            relative_time_updates += 1
                            if not dry_run:
                                detection.video_relative_timestamp = new_relative
                                detection.video_relative_timestamp_ns = str(int(new_relative * 1e9))
                    elif video_offset_ms is not None and detection.sequence_timestamp is not None:
                        new_relative = max(0.0, detection.sequence_timestamp - (video_offset_ms or 0.0) / 1000.0)
                        if detection.video_relative_timestamp != new_relative:
                            relative_time_updates += 1
                            if not dry_run:
                                detection.video_relative_timestamp = new_relative
                                detection.video_relative_timestamp_ns = str(int(new_relative * 1e9))

                    # Update sequence timestamp relative to first video start
                    if sequence_start_time is not None and detection.timestamp is not None:
                        new_sequence_ts = max(0.0, detection.timestamp - sequence_start_time)
                        if detection.sequence_timestamp != new_sequence_ts and not dry_run:
                            detection.sequence_timestamp = new_sequence_ts

                    # Update sequence_video_result_id mapping
                    sequence_video_result_id = (
                        timing_info.get("sequence_video_result_id") or video_result_lookup.get(assigned_video_id)
                    )
                    if sequence_video_result_id and detection.sequence_video_result_id != sequence_video_result_id and not dry_run:
                        detection.sequence_video_result_id = sequence_video_result_id

                    # Update video assignment if needed
                    if detection.video_id != assigned_video_id:
                        if detection.video_id is None:
                            reassigned_null += 1
                        else:
                            corrected_existing += 1

                        if not dry_run:
                            detection.video_id = assigned_video_id

                    video_assignments[assigned_video_id] = video_assignments.get(assigned_video_id, 0) + 1

                except Exception as e:
                    error_msg = f"Error processing detection {detection.id}: {e}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)

            if not dry_run and (reassigned_null > 0 or corrected_existing > 0 or relative_time_updates > 0):
                db.commit()
                self.logger.info(
                    f"✅ Reassignment complete: reassigned_null={reassigned_null}, "
                    f"corrected_existing={corrected_existing}, relative_updates={relative_time_updates}"
                )
            elif dry_run:
                self.logger.info(
                    f"[DRY RUN] Would reassign {reassigned_null} null detections and correct "
                    f"{corrected_existing} existing assignments"
                )

            return {
                "success": True,
                "reassigned_count": reassigned_null,
                "corrected_existing": corrected_existing,
                "relative_time_updates": relative_time_updates,
                "total_detections": total_detections,
                "video_assignments": video_assignments,
                "errors": errors,
                "unmatched_detections": unmatched_detections,
                "session_id": session_id,
                "dry_run": dry_run
            }

        except SQLAlchemyError as e:
            db.rollback()
            error_msg = f"Database error during video_id reassignment: {e}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "reassigned_count": 0,
                "corrected_existing": 0,
                "relative_time_updates": 0,
                "total_detections": 0,
                "video_assignments": {},
                "errors": [error_msg]
            }

        except Exception as e:
            db.rollback()
            error_msg = f"Unexpected error during video_id reassignment: {e}"
            self.logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "reassigned_count": 0,
                "corrected_existing": 0,
                "relative_time_updates": 0,
                "total_detections": 0,
                "video_assignments": {},
                "errors": [error_msg]
            }

        finally:
            db.close()

    def _build_video_timing_map(
        self,
        session: TestSession,
        video_results: List[SequenceVideoResult],
        db: Session
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build a map of video_id -> timing boundaries.

        Args:
            session: Parent test session (provides sequence_metadata fallback)
            video_results: List of SequenceVideoResult records
            db: Database session for fetching video metadata

        Returns:
            Dict mapping video_id to timing information:
                - start_time: Unix timestamp when video started
                - end_time: Unix timestamp when video ended
                - duration_s: Video duration in seconds
                - filename: Video filename for logging
        """
        video_timing_map: Dict[str, Dict[str, Any]] = {}

        # Parse sequence_metadata for supplemental timing information
        metadata: Dict[str, Any] = {}
        if session and session.sequence_metadata:
            raw = session.sequence_metadata
            if isinstance(raw, str):
                try:
                    metadata = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            elif isinstance(raw, dict):
                metadata = dict(raw)

        metadata_video_timing: Dict[str, Any] = metadata.get("video_timing", {})

        # Determine best available sequence start reference
        sequence_base_start: Optional[float] = None
        if video_results:
            try:
                sequence_record = video_results[0].video_sequence
                if sequence_record and getattr(sequence_record, "sequence_start_time", None) is not None:
                    sequence_base_start = float(sequence_record.sequence_start_time)
            except Exception:
                sequence_base_start = None

        if sequence_base_start is None and session:
            sequence_base_start = self._to_timestamp(getattr(session, "video_start_timestamp", None))
            if sequence_base_start is None:
                sequence_base_start = self._to_timestamp(getattr(session, "started_at", None))

        if sequence_base_start is None:
            sequence_base_start = self._to_timestamp(
                metadata.get("sequence_started_at") or metadata.get("sequence_start_time")
            )

        # Helper to resolve filename once per video
        def _get_filename(video_id: str) -> str:
            video = db.query(Video).filter(Video.id == video_id).first()
            return video.filename if video and getattr(video, "filename", None) else video_id

        ordered_results = sorted(
            video_results,
            key=lambda vr: vr.sequence_order if vr.sequence_order is not None else 0
        )
        cumulative_offset_ms = 0.0

        for vr in ordered_results:
            timing_meta = metadata_video_timing.get(vr.video_id, {}) if metadata_video_timing else {}

            raw_offset_ms = self._select_first_value(
                vr.video_play_offset_ms,
                timing_meta.get("video_play_offset_ms"),
                timing_meta.get("offset_ms"),
                timing_meta.get("sequence_offset_ms"),
            )
            offset_ms = None
            if isinstance(raw_offset_ms, (int, float, str, Decimal)):
                try:
                    offset_ms = float(raw_offset_ms)
                except (TypeError, ValueError):
                    offset_ms = None
            # Fallback: use accumulated offset when explicit value missing
            if offset_ms is None and sequence_base_start is not None:
                offset_ms = cumulative_offset_ms

            gap_ms = None
            raw_gap = self._select_first_value(
                timing_meta.get("gap_duration_ms"),
                timing_meta.get("gap_ms"),
                timing_meta.get("gap_duration")
            )
            if isinstance(raw_gap, (int, float, str, Decimal)):
                try:
                    gap_ms = float(raw_gap)
                except (TypeError, ValueError):
                    gap_ms = None

            start_time = self._select_first_value(
                vr.video_start_time,
                timing_meta.get("started_at"),
                timing_meta.get("start_time")
            )

            if start_time is None and sequence_base_start is not None and offset_ms is not None:
                start_time = sequence_base_start + (offset_ms / 1000.0)

            if start_time is None:
                self.logger.warning(
                    f"Video {vr.video_id} (sequence order {vr.sequence_order}) has no start time - skipping"
                )
                continue

            end_time = self._select_first_value(
                vr.video_end_time,
                timing_meta.get("ended_at"),
                timing_meta.get("end_time")
            )

            if end_time is None:
                duration_s = None
                if vr.actual_duration_ms:
                    duration_s = vr.actual_duration_ms / 1000.0
                elif timing_meta.get("actual_duration") is not None:
                    try:
                        duration_s = float(timing_meta["actual_duration"])
                    except (TypeError, ValueError):
                        duration_s = None
                else:
                    video = db.query(Video).filter(Video.id == vr.video_id).first()
                    if video and getattr(video, "duration", None):
                        duration_s = float(video.duration)

                if duration_s is not None:
                    end_time = start_time + duration_s
                else:
                    self.logger.warning(
                        f"Video {vr.video_id} has no end time or duration - cannot build timing boundary"
                    )
                    continue

            duration_s = end_time - start_time

            effective_offset_ms = None
            if offset_ms is not None:
                effective_offset_ms = offset_ms
            elif sequence_base_start is not None:
                effective_offset_ms = max(0.0, (start_time - sequence_base_start) * 1000.0)

            if duration_s is not None:
                advance_ms = duration_s * 1000.0
                if effective_offset_ms is not None:
                    cumulative_offset_ms = max(cumulative_offset_ms, effective_offset_ms + advance_ms)
                else:
                    cumulative_offset_ms += advance_ms
            if gap_ms is not None:
                cumulative_offset_ms += gap_ms

            video_timing_map[vr.video_id] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration_s": duration_s,
                "filename": _get_filename(vr.video_id),
                "sequence_order": vr.sequence_order,
                "sequence_video_result_id": vr.id,
                "frame_rate": timing_meta.get("fps"),
                "actual_duration": timing_meta.get("actual_duration"),
                "video_play_offset_ms": offset_ms,
                "gap_duration_ms": gap_ms
            }

        # Include videos present only in metadata (if any)
        for video_id, timing_meta in metadata_video_timing.items():
            if video_id in video_timing_map:
                continue

            raw_offset_ms = self._select_first_value(
                timing_meta.get("video_play_offset_ms"),
                timing_meta.get("offset_ms"),
                timing_meta.get("sequence_offset_ms")
            )
            offset_ms = None
            if isinstance(raw_offset_ms, (int, float, str, Decimal)):
                try:
                    offset_ms = float(raw_offset_ms)
                except (TypeError, ValueError):
                    offset_ms = None

            start_time = self._select_first_value(
                timing_meta.get("started_at"),
                timing_meta.get("start_time")
            )
            if start_time is None and sequence_base_start is not None and offset_ms is not None:
                start_time = sequence_base_start + (offset_ms / 1000.0)

            if start_time is None:
                continue

            end_time = self._select_first_value(
                timing_meta.get("ended_at"),
                timing_meta.get("end_time")
            )

            duration_s = None
            if end_time is not None:
                duration_s = end_time - start_time
            elif timing_meta.get("actual_duration") is not None:
                try:
                    duration_s = float(timing_meta["actual_duration"])
                    end_time = start_time + duration_s
                except (TypeError, ValueError):
                    duration_s = None

            if end_time is None:
                self.logger.warning(
                    f"Metadata-only video {video_id} missing end time - skipping"
                )
                continue

            if offset_ms is None and sequence_base_start is not None:
                offset_ms = max(0.0, (start_time - sequence_base_start) * 1000.0)

            raw_gap = self._select_first_value(
                timing_meta.get("gap_duration_ms"),
                timing_meta.get("gap_ms"),
                timing_meta.get("gap_duration")
            )
            gap_ms = None
            if isinstance(raw_gap, (int, float, str, Decimal)):
                try:
                    gap_ms = float(raw_gap)
                except (TypeError, ValueError):
                    gap_ms = None

            video_timing_map[video_id] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration_s": duration_s,
                "filename": _get_filename(video_id),
                "sequence_order": timing_meta.get("sequence_order"),
                "sequence_video_result_id": None,
                "frame_rate": timing_meta.get("fps"),
                "actual_duration": timing_meta.get("actual_duration"),
                "video_play_offset_ms": offset_ms,
                "gap_duration_ms": gap_ms
            }

        return video_timing_map

    def _determine_video_from_timestamp(
        self,
        detection: DetectionEvent,
        video_timing_map: Dict[str, Dict[str, Any]]
    ) -> Optional[str]:
        """
        Determine which video a detection belongs to based on timestamp.

        Checks if detection timestamp falls within any video's time range.

        Args:
            detection: DetectionEvent to analyze
            video_timing_map: Map of video_id -> timing boundaries

        Returns:
            video_id if match found, None otherwise
        """
        if not detection.timestamp:
            self.logger.warning(f"Detection {detection.id} has no timestamp")
            return None

        detection_timestamp = detection.timestamp

        # Build ordered list of videos for deterministic fallbacks
        video_ranges = [
            (
                video_id,
                timing["start_time"],
                timing.get("end_time")
            )
            for video_id, timing in video_timing_map.items()
        ]
        video_ranges.sort(key=lambda item: item[1] if item[1] is not None else float("inf"))

        # Check each video's time range
        for video_id, start_time, end_time in video_ranges:
            if start_time is None:
                continue

            # Add small buffer (100ms) to account for timing precision
            buffer_s = 0.1

            if end_time is None:
                if detection_timestamp >= (start_time - buffer_s):
                    self.logger.debug(
                        f"Detection {detection.id} (timestamp: {detection_timestamp:.3f}s) "
                        f"matches video {video_id} (start: {start_time:.3f}s, no end time)"
                    )
                    return video_id
            else:
                # Check if detection falls within this video's time range
                if (start_time - buffer_s) <= detection_timestamp <= (end_time + buffer_s):
                    self.logger.debug(
                        f"Detection {detection.id} (timestamp: {detection_timestamp:.3f}s) "
                        f"matches video {video_id} (range: {start_time:.3f}s - {end_time:.3f}s)"
                    )
                    return video_id

        # Provide graceful fallback for detections slightly outside timing windows.
        if video_ranges:
            first_video = video_ranges[0]
            last_video = video_ranges[-1]
            fallback_window_s = 10.0

            first_start = first_video[1]
            if first_start is not None and detection_timestamp < first_start and (first_start - detection_timestamp) <= fallback_window_s:
                self.logger.info(
                    f"⚠️ Detection {detection.id} ({detection_timestamp:.3f}s) occurs before first video start. "
                    f"Assigning to first video {first_video[0]} within {fallback_window_s}s pre-roll window."
                )
                return first_video[0]

            last_end = last_video[2]
            if last_end is not None and detection_timestamp > last_end and (detection_timestamp - last_end) <= fallback_window_s:
                self.logger.info(
                    f"⚠️ Detection {detection.id} ({detection_timestamp:.3f}s) occurs after last video end. "
                    f"Assigning to last video {last_video[0]} within {fallback_window_s}s post-roll window."
                )
                return last_video[0]

        # No match found
        self.logger.warning(
            f"Detection {detection.id} (timestamp: {detection_timestamp:.3f}s) "
            f"does not match any video time range"
        )

        # Log available time ranges for debugging
        for video_id, start_time, end_time in video_ranges:
            self.logger.debug(
                f"  Video {video_id}: {start_time:.3f}s - {end_time:.3f}s"
            )

        return None


# Global service instance
_reassignment_service = None


def get_detection_video_reassignment_service() -> DetectionVideoReassignmentService:
    """Get global reassignment service instance (singleton)."""
    global _reassignment_service

    if _reassignment_service is None:
        _reassignment_service = DetectionVideoReassignmentService()

    return _reassignment_service


# Convenience function for direct usage
async def reassign_null_video_ids(
    session_id: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to normalize detection video assignments for a session.

    Args:
        session_id: Test session ID to process
        dry_run: If True, only report what would be changed without modifying database

    Returns:
        Dict containing reassignment results
    """
    service = get_detection_video_reassignment_service()
    return await service.reassign_null_video_ids(session_id, dry_run)
