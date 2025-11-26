"""
Drift Measurement Service - Production Grade Timing Drift Analysis
===================================================================

Measures EXACT drift for each video by capturing timestamps at multiple stages
and calculating precise time offsets between video start and hardware monitoring.

Author: Backend API Developer Agent
Date: 2025-11-20
"""

import time
import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import statistics
import threading

logger = logging.getLogger(__name__)


class DriftStage(str, Enum):
    """Stages where timing can drift"""
    VIDEO_START_COMMAND = "video_start_command"
    VIDEO_ACTUAL_START = "video_actual_start"
    EVENT_RECEIVED = "event_received"
    LABJACK_COMMAND_SENT = "labjack_command_sent"
    LABJACK_ACTUAL_START = "labjack_actual_start"


@dataclass
class StageTimestamp:
    """Timestamp captured at a specific stage"""
    stage: DriftStage
    timestamp: float  # Unix timestamp (seconds)
    timestamp_ns: int  # Nanosecond precision
    source: str  # "frontend", "backend", "labjack"
    metadata: Dict = field(default_factory=dict)
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class VideoDriftMeasurement:
    """Complete drift measurement for a video"""
    session_id: str
    video_id: str
    video_sequence_number: int

    # Captured timestamps
    timestamps: Dict[DriftStage, StageTimestamp] = field(default_factory=dict)

    # Calculated drifts (in milliseconds)
    video_start_drift_ms: Optional[float] = None  # Video actual start vs command
    labjack_start_drift_ms: Optional[float] = None  # LabJack actual start vs command
    total_drift_ms: Optional[float] = None  # Total drift from video start to LabJack start
    clock_offset_ms: float = 0.0  # Browser-server clock offset

    # Quality metrics
    drift_calculation_complete: bool = False
    confidence_score: float = 0.0
    warnings: List[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    def calculate_drift(self) -> None:
        """Calculate all drift values from captured timestamps"""
        try:
            # Video start drift: actual start - command time
            if (DriftStage.VIDEO_ACTUAL_START in self.timestamps and
                DriftStage.VIDEO_START_COMMAND in self.timestamps):

                actual = self.timestamps[DriftStage.VIDEO_ACTUAL_START].timestamp
                command = self.timestamps[DriftStage.VIDEO_START_COMMAND].timestamp
                self.video_start_drift_ms = (actual - command) * 1000

            # LabJack start drift: actual start - command time
            if (DriftStage.LABJACK_ACTUAL_START in self.timestamps and
                DriftStage.LABJACK_COMMAND_SENT in self.timestamps):

                actual = self.timestamps[DriftStage.LABJACK_ACTUAL_START].timestamp
                command = self.timestamps[DriftStage.LABJACK_COMMAND_SENT].timestamp
                self.labjack_start_drift_ms = (actual - command) * 1000

            # Total drift: LabJack start - Video start (compensated for clock offset)
            if (DriftStage.LABJACK_ACTUAL_START in self.timestamps and
                DriftStage.VIDEO_ACTUAL_START in self.timestamps):

                labjack_start = self.timestamps[DriftStage.LABJACK_ACTUAL_START].timestamp
                video_start = self.timestamps[DriftStage.VIDEO_ACTUAL_START].timestamp

                # Compensate for clock offset (convert to same time reference)
                video_start_compensated = video_start - (self.clock_offset_ms / 1000)

                self.total_drift_ms = (labjack_start - video_start_compensated) * 1000

            # Calculate confidence score
            self.confidence_score = self._calculate_confidence()

            # Mark as complete if we have minimum required timestamps
            self.drift_calculation_complete = (
                self.video_start_drift_ms is not None and
                self.total_drift_ms is not None
            )

            self.updated_at = datetime.now(timezone.utc)

            logger.info(
                f"Drift calculated for session {self.session_id}, video {self.video_id}: "
                f"video_drift={self.video_start_drift_ms:.2f}ms, "
                f"total_drift={self.total_drift_ms:.2f}ms"
            )

        except Exception as e:
            logger.error(f"Error calculating drift: {e}")
            self.warnings.append(f"Drift calculation error: {str(e)}")

    def _calculate_confidence(self) -> float:
        """Calculate confidence score based on available data"""
        score = 0.0

        # Base score for having timestamps
        if len(self.timestamps) >= 3:
            score += 0.3

        # Score for having actual start times (most important)
        if DriftStage.VIDEO_ACTUAL_START in self.timestamps:
            score += 0.3
        if DriftStage.LABJACK_ACTUAL_START in self.timestamps:
            score += 0.3

        # Score for having clock offset compensation
        if self.clock_offset_ms != 0.0:
            score += 0.1

        return min(1.0, score)


class DriftMeasurementService:
    """
    Production-grade drift measurement service.

    Captures timestamps at each stage of the video->hardware pipeline
    and calculates precise drift measurements for compensation.
    """

    def __init__(self) -> None:
        self._measurements: Dict[str, Dict[str, VideoDriftMeasurement]] = {}  # session_id -> {video_id -> measurement}
        self._lock = threading.RLock()

        # Simple drift tracking for backward compatibility
        self._video_command_time: Optional[float] = None
        self._video_actual_start: Optional[float] = None
        self._labjack_actual_start: Optional[float] = None
        self._measured_drift_ms: float = 0.0

        logger.info("Drift Measurement Service initialized")

    def capture_video_command_time(self) -> None:
        """Call when video playback command is issued"""
        self._video_command_time = time.time()
        logger.info(f"📹 Video command issued at {self._video_command_time:.6f}")

    def capture_video_actual_start(self, timestamp: Optional[float] = None) -> None:
        """Call when video actually starts playing"""
        self._video_actual_start = timestamp or time.time()
        logger.info(f"📹 Video actual start at {self._video_actual_start:.6f}")
        self._calculate_drift()

    def capture_labjack_start(self, timestamp: Optional[float] = None) -> None:
        """Call when LabJack monitoring starts"""
        self._labjack_actual_start = timestamp or time.time()
        logger.info(f"🔌 LabJack start at {self._labjack_actual_start:.6f}")
        self._calculate_drift()

    def _calculate_drift(self) -> None:
        """Calculate drift between video and LabJack start times"""
        if self._video_actual_start and self._labjack_actual_start:
            self._measured_drift_ms = (self._labjack_actual_start - self._video_actual_start) * 1000
            logger.info(f"📊 Calculated drift: {self._measured_drift_ms:.2f}ms")

    def get_drift_ms(self) -> float:
        """Get measured drift in milliseconds"""
        return self._measured_drift_ms

    def start_video_drift_measurement(
        self,
        session_id: str,
        video_id: str,
        video_sequence_number: int,
        clock_offset_ms: float = 0.0
    ) -> VideoDriftMeasurement:
        """
        Start drift measurement for a new video.

        Args:
            session_id: Test session identifier
            video_id: Video identifier
            video_sequence_number: Sequence number of video in test
            clock_offset_ms: Browser-server clock offset from sync service

        Returns:
            VideoDriftMeasurement object
        """
        with self._lock:
            if session_id not in self._measurements:
                self._measurements[session_id] = {}

            measurement = VideoDriftMeasurement(
                session_id=session_id,
                video_id=video_id,
                video_sequence_number=video_sequence_number,
                clock_offset_ms=clock_offset_ms
            )

            self._measurements[session_id][video_id] = measurement

            logger.info(
                f"Started drift measurement for session {session_id}, "
                f"video {video_id} (sequence {video_sequence_number})"
            )

            return measurement

    def capture_timestamp(
        self,
        session_id: str,
        video_id: str,
        stage: DriftStage,
        timestamp: float,
        source: str = "backend",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Capture a timestamp at a specific stage.

        Args:
            session_id: Test session identifier
            video_id: Video identifier
            stage: Stage where timestamp was captured
            timestamp: Unix timestamp (seconds)
            source: Source of timestamp (frontend/backend/labjack)
            metadata: Additional metadata
        """
        with self._lock:
            measurement = self._get_measurement(session_id, video_id)
            if not measurement:
                logger.warning(
                    f"No drift measurement found for session {session_id}, "
                    f"video {video_id}, creating new"
                )
                measurement = self.start_video_drift_measurement(
                    session_id, video_id, 0
                )

            stage_timestamp = StageTimestamp(
                stage=stage,
                timestamp=timestamp,
                timestamp_ns=int(timestamp * 1e9),
                source=source,
                metadata=metadata or {}
            )

            measurement.timestamps[stage] = stage_timestamp

            logger.debug(
                f"Captured {stage.value} timestamp for session {session_id}, "
                f"video {video_id}: {timestamp:.6f} (source: {source})"
            )

            # Auto-calculate drift if we have enough data
            if len(measurement.timestamps) >= 3:
                measurement.calculate_drift()

    def get_drift_for_video(self, session_id: str, video_id: str) -> Optional[float]:
        """
        Get the total drift measurement for a video in milliseconds.

        Args:
            session_id: Test session identifier
            video_id: Video identifier

        Returns:
            Total drift in milliseconds, or None if not calculated
        """
        measurement = self._get_measurement(session_id, video_id)
        if not measurement:
            logger.warning(f"No drift measurement for session {session_id}, video {video_id}")
            return None

        if not measurement.drift_calculation_complete:
            # Try to calculate if we have data
            measurement.calculate_drift()

        return measurement.total_drift_ms

    def get_measurement(self, session_id: str, video_id: str) -> Optional[VideoDriftMeasurement]:
        """Get the complete drift measurement object."""
        return self._get_measurement(session_id, video_id)

    def _get_measurement(self, session_id: str, video_id: str) -> Optional[VideoDriftMeasurement]:
        """Internal method to get measurement (no lock needed - called from locked methods)"""
        if session_id not in self._measurements:
            return None
        return self._measurements[session_id].get(video_id)

    def get_session_drift_statistics(self, session_id: str) -> Dict[str, Any]:
        """
        Get drift statistics for all videos in a session.

        Args:
            session_id: Test session identifier

        Returns:
            Dictionary with drift statistics
        """
        with self._lock:
            if session_id not in self._measurements:
                return {
                    "error": "Session not found",
                    "session_id": session_id
                }

            measurements = self._measurements[session_id].values()
            complete_measurements = [m for m in measurements if m.drift_calculation_complete]

            if not complete_measurements:
                return {
                    "session_id": session_id,
                    "video_count": len(measurements),
                    "complete_count": 0,
                    "status": "no_complete_measurements"
                }

            drifts = [m.total_drift_ms for m in complete_measurements if m.total_drift_ms is not None]

            stats = {
                "session_id": session_id,
                "video_count": len(measurements),
                "complete_count": len(complete_measurements),
                "mean_drift_ms": statistics.mean(drifts) if drifts else 0.0,
                "std_dev_drift_ms": statistics.stdev(drifts) if len(drifts) > 1 else 0.0,
                "min_drift_ms": min(drifts) if drifts else 0.0,
                "max_drift_ms": max(drifts) if drifts else 0.0,
                "drift_values_ms": drifts
            }

            # Add alerts
            if stats["max_drift_ms"] > 500:
                stats["alert"] = "High drift detected (>500ms)"
            elif stats["std_dev_drift_ms"] > 100:
                stats["alert"] = "High drift variance detected (>100ms)"

            return stats

    def cleanup_session(self, session_id: str) -> None:
        """Clean up drift measurements for a completed session."""
        with self._lock:
            if session_id in self._measurements:
                count = len(self._measurements[session_id])
                del self._measurements[session_id]
                logger.info(f"Cleaned up {count} drift measurements for session {session_id}")

    def get_service_statistics(self) -> Dict[str, Any]:
        """Get overall service statistics."""
        with self._lock:
            total_sessions = len(self._measurements)
            total_videos = sum(len(videos) for videos in self._measurements.values())
            complete_measurements = sum(
                sum(1 for m in videos.values() if m.drift_calculation_complete)
                for videos in self._measurements.values()
            )

            return {
                "total_sessions": total_sessions,
                "total_videos": total_videos,
                "complete_measurements": complete_measurements,
                "service_status": "operational"
            }


# Global service instance
_drift_measurement_service: Optional[DriftMeasurementService] = None


def get_drift_measurement_service() -> DriftMeasurementService:
    """Get or create the global drift measurement service instance."""
    global _drift_measurement_service
    if _drift_measurement_service is None:
        _drift_measurement_service = DriftMeasurementService()
    return _drift_measurement_service


def initialize_drift_measurement_service() -> DriftMeasurementService:
    """Initialize the drift measurement service."""
    return get_drift_measurement_service()
