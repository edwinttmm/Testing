"""
Timestamp Compensation Service - Production Grade Detection Timestamp Adjustment
================================================================================

Compensates all detection timestamps using measured drift values before ground truth matching.
Preserves original timestamps for debugging while applying precise corrections.

Author: Backend API Developer Agent
Date: 2025-11-20
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading

logger = logging.getLogger(__name__)


@dataclass
class DetectionTimestamp:
    """Detection with original and compensated timestamps"""
    detection_id: str
    original_timestamp: float  # Original timestamp from LabJack
    compensated_timestamp: float  # Drift-compensated timestamp
    drift_ms: float  # Applied drift correction
    clock_offset_ms: float  # Applied clock offset correction
    compensation_applied_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict = field(default_factory=dict)


@dataclass
class CompensationResult:
    """Result of timestamp compensation operation"""
    session_id: str
    video_id: str
    detections_processed: int
    detections_compensated: int
    average_drift_correction_ms: float
    compensation_successful: bool
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TimestampCompensationService:
    """
    Production-grade timestamp compensation service.

    Applies measured drift and clock offset corrections to detection timestamps
    to ensure accurate ground truth matching.
    """

    def __init__(self):
        self._compensation_history: Dict[str, List[CompensationResult]] = {}  # session_id -> results
        self._compensated_detections: Dict[str, Dict[str, DetectionTimestamp]] = {}  # session_id -> {detection_id -> timestamp}
        self._lock = threading.RLock()

        logger.info("Timestamp Compensation Service initialized")

    def compensate_detection_timestamp(
        self,
        detection_id: str,
        raw_timestamp: float,
        drift_ms: float,
        clock_offset_ms: float = 0.0,
        metadata: Optional[Dict] = None
    ) -> float:
        """
        Compensate a single detection timestamp.

        Formula: T_compensated = T_raw - (drift_ms + clock_offset_ms) / 1000

        Args:
            detection_id: Detection identifier
            raw_timestamp: Original timestamp from LabJack (Unix time)
            drift_ms: Measured drift in milliseconds
            clock_offset_ms: Clock offset correction in milliseconds
            metadata: Additional metadata

        Returns:
            Compensated timestamp
        """
        # Total correction in seconds
        total_correction_s = (drift_ms + clock_offset_ms) / 1000.0

        # Apply correction
        compensated = raw_timestamp - total_correction_s

        logger.debug(
            f"Compensated detection {detection_id}: "
            f"{raw_timestamp:.6f} -> {compensated:.6f} "
            f"(drift={drift_ms:.2f}ms, offset={clock_offset_ms:.2f}ms)"
        )

        return compensated

    def compensate_detections_batch(
        self,
        session_id: str,
        video_id: str,
        detections: List[Dict[str, Any]],
        drift_ms: float,
        clock_offset_ms: float = 0.0,
        store_history: bool = True
    ) -> CompensationResult:
        """
        Compensate timestamps for a batch of detections.

        Args:
            session_id: Test session identifier
            video_id: Video identifier
            detections: List of detection dictionaries with 'id' and 'timestamp' keys
            drift_ms: Measured drift in milliseconds
            clock_offset_ms: Clock offset correction in milliseconds
            store_history: Whether to store compensation history

        Returns:
            CompensationResult with operation details
        """
        with self._lock:
            result = CompensationResult(
                session_id=session_id,
                video_id=video_id,
                detections_processed=len(detections),
                detections_compensated=0,
                average_drift_correction_ms=drift_ms,
                compensation_successful=True
            )

            if session_id not in self._compensated_detections:
                self._compensated_detections[session_id] = {}

            try:
                for detection in detections:
                    try:
                        detection_id = str(detection.get('id', 'unknown'))
                        raw_timestamp = float(detection.get('timestamp', 0.0))

                        if raw_timestamp == 0.0:
                            result.errors.append(f"Detection {detection_id} has zero timestamp")
                            continue

                        # Compensate timestamp
                        compensated = self.compensate_detection_timestamp(
                            detection_id=detection_id,
                            raw_timestamp=raw_timestamp,
                            drift_ms=drift_ms,
                            clock_offset_ms=clock_offset_ms,
                            metadata=detection.get('metadata', {})
                        )

                        # Store compensated timestamp
                        det_timestamp = DetectionTimestamp(
                            detection_id=detection_id,
                            original_timestamp=raw_timestamp,
                            compensated_timestamp=compensated,
                            drift_ms=drift_ms,
                            clock_offset_ms=clock_offset_ms,
                            metadata=detection.get('metadata', {})
                        )

                        self._compensated_detections[session_id][detection_id] = det_timestamp

                        # Update detection object in place
                        detection['compensated_timestamp'] = compensated
                        detection['original_timestamp'] = raw_timestamp
                        detection['drift_correction_ms'] = drift_ms
                        detection['clock_offset_correction_ms'] = clock_offset_ms

                        result.detections_compensated += 1

                    except Exception as e:
                        error_msg = f"Error compensating detection {detection.get('id')}: {str(e)}"
                        result.errors.append(error_msg)
                        logger.error(error_msg)

                # Store history if requested
                if store_history:
                    if session_id not in self._compensation_history:
                        self._compensation_history[session_id] = []
                    self._compensation_history[session_id].append(result)

                logger.info(
                    f"Compensated {result.detections_compensated}/{result.detections_processed} "
                    f"detections for session {session_id}, video {video_id} "
                    f"with drift={drift_ms:.2f}ms"
                )

            except Exception as e:
                result.compensation_successful = False
                result.errors.append(f"Batch compensation failed: {str(e)}")
                logger.error(f"Batch compensation failed for session {session_id}: {e}")

            return result

    def get_compensated_timestamp(
        self,
        session_id: str,
        detection_id: str
    ) -> Optional[float]:
        """
        Get the compensated timestamp for a detection.

        Args:
            session_id: Test session identifier
            detection_id: Detection identifier

        Returns:
            Compensated timestamp or None if not found
        """
        with self._lock:
            if session_id not in self._compensated_detections:
                return None

            det_timestamp = self._compensated_detections[session_id].get(detection_id)
            if not det_timestamp:
                return None

            return det_timestamp.compensated_timestamp

    def get_detection_compensation_info(
        self,
        session_id: str,
        detection_id: str
    ) -> Optional[Dict]:
        """
        Get full compensation information for a detection.

        Args:
            session_id: Test session identifier
            detection_id: Detection identifier

        Returns:
            Dictionary with compensation details or None
        """
        with self._lock:
            if session_id not in self._compensated_detections:
                return None

            det_timestamp = self._compensated_detections[session_id].get(detection_id)
            if not det_timestamp:
                return None

            return {
                "detection_id": det_timestamp.detection_id,
                "original_timestamp": det_timestamp.original_timestamp,
                "compensated_timestamp": det_timestamp.compensated_timestamp,
                "drift_correction_ms": det_timestamp.drift_ms,
                "clock_offset_correction_ms": det_timestamp.clock_offset_ms,
                "total_correction_ms": det_timestamp.drift_ms + det_timestamp.clock_offset_ms,
                "compensation_applied_at": det_timestamp.compensation_applied_at.isoformat(),
                "metadata": det_timestamp.metadata
            }

    def get_session_compensation_summary(self, session_id: str) -> Dict:
        """
        Get compensation summary for a session.

        Args:
            session_id: Test session identifier

        Returns:
            Dictionary with compensation summary
        """
        with self._lock:
            if session_id not in self._compensation_history:
                return {
                    "error": "No compensation history for session",
                    "session_id": session_id
                }

            results = self._compensation_history[session_id]

            total_processed = sum(r.detections_processed for r in results)
            total_compensated = sum(r.detections_compensated for r in results)
            total_errors = sum(len(r.errors) for r in results)

            avg_drift = (sum(r.average_drift_correction_ms for r in results) /
                        len(results) if results else 0.0)

            return {
                "session_id": session_id,
                "compensation_operations": len(results),
                "total_detections_processed": total_processed,
                "total_detections_compensated": total_compensated,
                "total_errors": total_errors,
                "average_drift_correction_ms": avg_drift,
                "success_rate": (total_compensated / total_processed * 100
                               if total_processed > 0 else 0.0),
                "recent_results": [
                    {
                        "video_id": r.video_id,
                        "processed": r.detections_processed,
                        "compensated": r.detections_compensated,
                        "drift_ms": r.average_drift_correction_ms,
                        "successful": r.compensation_successful,
                        "timestamp": r.timestamp.isoformat()
                    }
                    for r in results[-5:]  # Last 5 operations
                ]
            }

    def cleanup_session(self, session_id: str):
        """Clean up compensation data for a completed session."""
        with self._lock:
            if session_id in self._compensation_history:
                del self._compensation_history[session_id]
            if session_id in self._compensated_detections:
                count = len(self._compensated_detections[session_id])
                del self._compensated_detections[session_id]
                logger.info(
                    f"Cleaned up {count} compensated detections "
                    f"for session {session_id}"
                )

    def get_service_statistics(self) -> Dict:
        """Get overall service statistics."""
        with self._lock:
            total_sessions = len(self._compensation_history)
            total_operations = sum(
                len(results) for results in self._compensation_history.values()
            )
            total_compensated = sum(
                sum(r.detections_compensated for r in results)
                for results in self._compensation_history.values()
            )

            return {
                "total_sessions": total_sessions,
                "total_compensation_operations": total_operations,
                "total_detections_compensated": total_compensated,
                "service_status": "operational"
            }


# Global service instance
_timestamp_compensation_service: Optional[TimestampCompensationService] = None


def get_timestamp_compensation_service() -> TimestampCompensationService:
    """Get or create the global timestamp compensation service instance."""
    global _timestamp_compensation_service
    if _timestamp_compensation_service is None:
        _timestamp_compensation_service = TimestampCompensationService()
    return _timestamp_compensation_service


def initialize_timestamp_compensation_service() -> TimestampCompensationService:
    """Initialize the timestamp compensation service."""
    return get_timestamp_compensation_service()
