"""
Post-Test Results Processor
===========================

Coordinates the complete post-test pipeline once the final video in a sequence
finishes playing:

1. Correlates every detection to a video using deterministic timestamp windows
2. Runs ground-truth matching to classify detections (TP/FP/FN) and compute
   latency metrics
3. Generates the consolidated report artifacts consumed by the UI
4. Persists processing status back into the session metadata so the frontend
   can display accurate progress indicators

The processor is intentionally asynchronous so API handlers can trigger it in
the background without blocking responses to the user.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import SessionLocal
from sqlalchemy import func

from models import TestSession, SequenceVideoResult, DetectionEvent
from services.detection_video_reassignment import DetectionVideoReassignmentService
from services.ground_truth_matching_service import get_ground_truth_matching_service
from services.report_generation_service import ReportGenerationService


logger = logging.getLogger(__name__)
START_TIME_MIN_GAP_SECONDS = 0.001


class TestResultsProcessor:
    """Coordinates post-test processing after the final video completes."""

    _locks: Dict[str, asyncio.Lock] = {}

    @classmethod
    def _get_lock(cls, session_id: str) -> asyncio.Lock:
        if session_id not in cls._locks:
            cls._locks[session_id] = asyncio.Lock()
        return cls._locks[session_id]

    @classmethod
    async def process_test_completion(cls, session_id: str) -> Dict[str, Any]:
        """
        Orchestrate the full post-test workflow for a session.

        Returns a summary dict so callers (background jobs or manual endpoints)
        can surface high-level progress information to the UI.
        """
        lock = cls._get_lock(session_id)
        async with lock:
            session_snapshot = cls._load_session_snapshot(session_id)
            if not session_snapshot:
                message = f"Test session {session_id} not found"
                logger.error(message)
                return {"success": False, "error": message}

            cls._set_processing_state(session_id, "in_progress", note="Post-test processing started")

            summary: Dict[str, Any] = {
                "success": True,
                "session_id": session_id,
                "project_id": session_snapshot.get("project_id"),
                "sequence_id": session_snapshot.get("sequence_id"),
            }

            try:
                correlation = await cls._correlate_detections(session_id)
                summary["correlation"] = correlation

                matching = cls._run_ground_truth_matching(
                    session_id,
                    tolerance_ms=session_snapshot.get("tolerance_ms"),
                )
                summary["ground_truth"] = matching

                report = await cls._generate_report(session_id)
                summary["report"] = report

                cls._set_processing_state(
                    session_id,
                    "completed",
                    note="Post-test processing finished",
                    correlation=correlation,
                    matching=matching,
                    report=report,
                )

                return summary

            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Post-test processing failed for %s: %s", session_id, exc)
                cls._set_processing_state(
                    session_id,
                    "failed",
                    note=str(exc),
                )
                return {"success": False, "error": str(exc)}

    @classmethod
    def mark_queued(cls, session_id: str, note: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Expose queued status to callers before async processing begins."""
        return cls._set_processing_state(
            session_id,
            "queued",
            note=note or "Awaiting background processing",
        )

    @classmethod
    def mark_failed(cls, session_id: str, note: str) -> Optional[Dict[str, Any]]:
        """Explicitly set the processing metadata to failed."""
        return cls._set_processing_state(session_id, "failed", note=note)

    # ------------------------------------------------------------------ #
    # Processing steps
    # ------------------------------------------------------------------ #

    @classmethod
    async def _correlate_detections(cls, session_id: str) -> Dict[str, Any]:
        """Assign detections to videos in bulk after the test completes."""
        service = DetectionVideoReassignmentService()
        result = await service.reassign_null_video_ids(session_id=session_id, dry_run=False)

        refreshed_counts = cls._refresh_video_detection_counts(session_id)
        if refreshed_counts:
            result["video_assignments"] = refreshed_counts

        matched = sum(result.get("video_assignments", {}).values())
        unmatched = len(result.get("unmatched_detections", []))

        logger.info(
            "Detection correlation complete for %s: matched=%s unmatched=%s",
            session_id,
            matched,
            unmatched,
        )

        return {
            "success": result.get("success", True),
            "matched": matched,
            "unmatched": unmatched,
            "details": result,
        }

    @classmethod
    def _run_ground_truth_matching(cls, session_id: str, tolerance_ms: Optional[int]) -> Dict[str, Any]:
        """Execute ground truth matching and return normalized metrics."""
        matching_service = get_ground_truth_matching_service()
        metrics = matching_service.match_detections_to_ground_truth(
            session_id=session_id,
            tolerance_ms=tolerance_ms,
            force_rematch=False,
            auto_commit=True,
        )

        if metrics is None:
            logger.warning("Ground truth matching returned no metrics for %s", session_id)
            return {"success": False, "error": "no_metrics"}

        logger.info(
            "Ground truth matching complete for %s: TP=%s FP=%s FN=%s",
            session_id,
            metrics.true_positives,
            metrics.false_positives,
            metrics.false_negatives,
        )

        return {
            "success": True,
            "true_positives": metrics.true_positives,
            "false_positives": metrics.false_positives,
            "false_negatives": metrics.false_negatives,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1_score": metrics.f1_score,
            "mean_latency_ms": metrics.mean_latency_ms,
            "max_latency_ms": metrics.max_latency_ms,
            "min_latency_ms": metrics.min_latency_ms,
            "within_tolerance_percentage": metrics.within_tolerance_percentage,
        }

    @classmethod
    async def _generate_report(cls, session_id: str) -> Dict[str, Any]:
        """Generate the consolidated report artifacts."""
        db = SessionLocal()
        try:
            report_service = ReportGenerationService(db)
            report_result = await report_service.generate_comprehensive_report(
                test_session_id=session_id,
                include_snapshots=False,
                formats=["html", "json"],
            )
            logger.info("Report generation complete for %s", session_id)
            return {
                "success": True,
                "report_files": report_result.get("report_files"),
                "metrics": report_result.get("metrics"),
            }
        except Exception as exc:  # pragma: no cover - I/O heavy path
            logger.error("Report generation failed for %s: %s", session_id, exc)
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    # ------------------------------------------------------------------ #
    # Session helpers
    # ------------------------------------------------------------------ #

    @classmethod
    def _load_session_snapshot(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """Load lightweight session info needed during processing."""
        db = SessionLocal()
        try:
            session: Optional[TestSession] = (
                db.query(TestSession).filter(TestSession.id == session_id).first()
            )
            if not session:
                return None
            return {
                "id": session.id,
                "project_id": session.project_id,
                "sequence_id": session.sequence_id,
                "tolerance_ms": session.tolerance_ms,
            }
        finally:
            db.close()

    @classmethod
    def _set_processing_state(
        cls,
        session_id: str,
        status: str,
        note: Optional[str] = None,
        **extra: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Persist post-processing metadata on the session so the frontend can
        display progress (queued → in_progress → completed/failed).
        """
        db = SessionLocal()
        try:
            session: Optional[TestSession] = (
                db.query(TestSession).filter(TestSession.id == session_id).first()
            )
            if not session:
                return None

            metadata = cls._ensure_metadata_dict(session.sequence_metadata)
            post_meta = metadata.get("post_processing", {})

            timestamp = datetime.now(timezone.utc).isoformat()
            post_meta.update(
                {
                    "status": status,
                    "updated_at": timestamp,
                }
            )
            if note:
                post_meta["note"] = note
            if status == "in_progress":
                post_meta["started_at"] = timestamp
            elif status == "completed":
                post_meta["completed_at"] = timestamp
            elif status == "failed":
                post_meta["error"] = note

            if extra:
                post_meta["details"] = extra

            metadata["post_processing"] = post_meta
            session.sequence_metadata = metadata
            db.commit()
            return post_meta
        except Exception as exc:  # pragma: no cover - defensive logging
            db.rollback()
            logger.error("Failed to update processing metadata for %s: %s", session_id, exc)
            return None
        finally:
            db.close()

    @staticmethod
    def _ensure_metadata_dict(raw_metadata: Any) -> Dict[str, Any]:
        """Normalize stored metadata into a mutable dict."""
        if not raw_metadata:
            return {}
        if isinstance(raw_metadata, dict):
            return dict(raw_metadata)
        if isinstance(raw_metadata, str):
            try:
                parsed = json.loads(raw_metadata)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    @classmethod
    def _refresh_video_detection_counts(cls, session_id: str) -> Dict[str, int]:
        """
        Synchronize per-video detection counts after correlation so the results API
        reflects accurate totals for each SequenceVideoResult and metadata entry.
        """
        db = SessionLocal()
        try:
            session: Optional[TestSession] = (
                db.query(TestSession).filter(TestSession.id == session_id).first()
            )
            if not session or not session.sequence_id:
                return {}

            rows = (
                db.query(DetectionEvent.video_id, func.count(DetectionEvent.id))
                .filter(
                    DetectionEvent.test_session_id == session_id,
                    DetectionEvent.video_id.isnot(None),
                )
                .group_by(DetectionEvent.video_id)
                .all()
            )
            counts = {video_id: count for video_id, count in rows if video_id}
            sequence_results = (
                db.query(SequenceVideoResult)
                .filter(SequenceVideoResult.video_sequence_id == session.sequence_id)
                .all()
            )
            result_map = {record.video_id: record for record in sequence_results if record.video_id}

            metadata = cls._ensure_metadata_dict(session.sequence_metadata)
            video_timing = metadata.get("video_timing", {})
            updated = False

            earliest_detection_row = (
                db.query(DetectionEvent.timestamp)
                .filter(
                    DetectionEvent.test_session_id == session_id,
                    DetectionEvent.timestamp.isnot(None),
                )
                .order_by(DetectionEvent.timestamp.asc())
                .first()
            )
            earliest_detection_ts = (
                float(earliest_detection_row[0]) if earliest_detection_row and earliest_detection_row[0] is not None else None
            )

            # Refresh detection counts
            for video_id, count in counts.items():
                record = result_map.get(video_id)
                if record and (record.actual_detection_count or 0) != count:
                    record.actual_detection_count = count
                    updated = True

                timing_entry = video_timing.get(video_id)
                if isinstance(timing_entry, dict):
                    if timing_entry.get("detection_count") != count:
                        timing_entry["detection_count"] = count
                        updated = True
                else:
                    video_timing[video_id] = {"detection_count": count}
                    updated = True

            # Enforce monotonic start times (covers historic sessions that stored duplicates)
            ordered_results = sorted(
                result_map.values(),
                key=lambda r: r.sequence_order if r.sequence_order is not None else 0
            )
            previous_video_end: Optional[float] = None

            for index, record in enumerate(ordered_results):
                video_id = record.video_id
                timing_entry = video_timing.get(video_id)
                if not isinstance(timing_entry, dict):
                    timing_entry = {}
                    video_timing[video_id] = timing_entry

                start_value: Optional[float] = record.video_start_time
                if start_value is None:
                    raw_start = timing_entry.get("started_at") or timing_entry.get("raw_started_at")
                    if isinstance(raw_start, (int, float)):
                        start_value = float(raw_start)

                # For the very first video, ensure we respect the earliest detection if it predates the stored start
                if (
                    index == 0
                    and earliest_detection_ts is not None
                    and start_value is not None
                    and start_value - earliest_detection_ts > START_TIME_MIN_GAP_SECONDS
                ):
                    timing_entry["raw_started_at"] = start_value
                    start_value = earliest_detection_ts
                    timing_entry["start_adjustment_applied"] = True
                    timing_entry["start_adjustment_reason"] = "post_processing_first_video_backshift"
                    updated = True

                if (
                    previous_video_end is not None
                    and start_value is not None
                    and start_value <= previous_video_end
                ):
                    raw_start = timing_entry.get("raw_started_at") or start_value
                    start_value = previous_video_end + START_TIME_MIN_GAP_SECONDS
                    timing_entry["raw_started_at"] = raw_start
                    timing_entry["start_adjustment_applied"] = True
                    timing_entry["start_adjustment_reason"] = "post_processing_monotonic_fix"
                    updated = True

                if start_value is not None:
                    if record.video_start_time is None or abs(record.video_start_time - start_value) > 1e-9:
                        record.video_start_time = start_value
                        updated = True
                    if timing_entry.get("started_at") != start_value:
                        timing_entry["started_at"] = start_value
                        timing_entry["started_at_iso"] = datetime.fromtimestamp(
                            start_value, timezone.utc
                        ).isoformat()
                        updated = True
                elif "start_adjustment_applied" not in timing_entry:
                    timing_entry["start_adjustment_applied"] = False

                # Compute the best known end time for this video
                candidate_end = timing_entry.get("ended_at")
                if candidate_end is None and record.video_end_time is not None:
                    candidate_end = record.video_end_time
                if candidate_end is None and start_value is not None:
                    duration = cls._compute_duration_seconds(timing_entry, record)
                    if duration:
                        candidate_end = start_value + duration
                if isinstance(candidate_end, (int, float)):
                    previous_video_end = float(candidate_end)

            if updated:
                metadata["video_timing"] = video_timing
                session.sequence_metadata = metadata
                db.commit()
            else:
                db.rollback()

            return counts
        except Exception as exc:  # pragma: no cover - defensive logging
            db.rollback()
            logger.warning("Unable to refresh video detection counts for %s: %s", session_id, exc)
            return {}
        finally:
            db.close()

    @staticmethod
    def _compute_duration_seconds(
        timing_entry: Optional[Dict[str, Any]],
        record: Optional[SequenceVideoResult]
    ) -> Optional[float]:
        """Derive duration in seconds from timing metadata or DB record."""
        if isinstance(timing_entry, dict):
            duration = timing_entry.get("actual_duration")
            if isinstance(duration, (int, float)):
                return float(duration)
        if record and record.actual_duration_ms:
            return float(record.actual_duration_ms) / 1000.0
        return None


_processor_instance: Optional[TestResultsProcessor] = None


def get_test_results_processor() -> TestResultsProcessor:
    """Convenience accessor used by routers."""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = TestResultsProcessor()
    return _processor_instance
