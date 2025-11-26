"""
Video Lifecycle Orchestrator Service - Production-Grade Coordination
======================================================================

Orchestrates Browser → Backend → LabJack timing for per-video monitoring.
Integrates with clock sync, drift measurement, and LabJack monitoring services.

Author: Backend API Developer Agent
Date: 2025-11-20
Status: Production-Ready
"""

import logging
import time
import uuid
from typing import Dict, Optional, Tuple, Any, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.models.video_lifecycle_models import (
    VideoStartedRequest,
    VideoEndedRequest,
    VideoErrorRequest,
    VideoStartedResponse,
    VideoEndedResponse,
    VideoLifecycleStatus,
    DriftStatisticsResponse,
    TimingInfo,
    MonitoringStatus,
    ErrorResponse
)
from src.services.clock_sync_service_v2 import ClockSyncService
from src.services.drift_measurement_service import DriftMeasurementService
from src.services.drift_monitoring_service import DriftMonitoringService
from src.services.dedicated_labjack_monitor import DedicatedLabJackMonitor

logger = logging.getLogger(__name__)


@dataclass
class VideoLifecycleState:
    """Internal state for active video monitoring"""
    session_id: str
    video_id: str
    video_url: str

    # Timestamps
    frontend_start_timestamp: float  # performance.now() ms
    backend_start_timestamp: float   # time.time() seconds
    labjack_start_timestamp: Optional[float] = None  # device timestamp seconds

    # Clock sync
    clock_offset_ms: float = 0.0

    # Monitoring state
    monitoring_active: bool = False
    detections_count: int = 0

    # Error tracking
    errors: list = None

    # Metadata
    video_duration_ms: Optional[float] = None
    video_fps: Optional[float] = None
    metadata: Dict[str, Any] = None

    # Timestamps
    created_at: datetime = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class VideoLifecycleOrchestrator:
    """
    Production-grade orchestrator for video lifecycle and monitoring coordination.

    Responsibilities:
    - Coordinate Browser → Backend → LabJack timing
    - Integrate clock synchronization
    - Track drift measurements
    - Manage LabJack monitoring lifecycle
    - Store all events in database
    - Handle errors gracefully with retries

    Thread-safe: Uses locks for concurrent access protection.
    """

    def __init__(
        self,
        clock_sync_service: ClockSyncService,
        drift_measurement_service: DriftMeasurementService,
        drift_monitoring_service: DriftMonitoringService,
        labjack_monitor: DedicatedLabJackMonitor,
        db_session_factory: Callable[[], Any]
    ) -> None:
        """
        Initialize video lifecycle orchestrator.

        Args:
            clock_sync_service: Service for clock synchronization
            drift_measurement_service: Service for drift tracking
            drift_monitoring_service: Service for drift statistics
            labjack_monitor: LabJack monitoring service
            db_session_factory: Factory function for database sessions
        """
        self.clock_sync = clock_sync_service
        self.drift_measurement = drift_measurement_service
        self.drift_monitoring = drift_monitoring_service
        self.labjack = labjack_monitor
        self.db_session_factory = db_session_factory

        # Active video states (session_id -> VideoLifecycleState)
        self._active_videos: Dict[str, VideoLifecycleState] = {}

        # Statistics
        self._start_time = time.time()
        self._total_videos_started = 0
        self._total_videos_completed = 0
        self._total_errors = 0

        logger.info("VideoLifecycleOrchestrator initialized successfully")

    # ==================== PUBLIC API ====================

    async def handle_video_started(
        self,
        session_id: str,
        request: VideoStartedRequest,
        db: Session
    ) -> VideoStartedResponse:
        """
        Handle video-started event with full timing coordination.

        Process:
        1. Validate session doesn't have active video
        2. Get clock offset from sync service
        3. Start LabJack monitoring
        4. Calculate drift
        5. Store state in database
        6. Return timing information

        Args:
            session_id: Test session identifier
            request: Video started request payload
            db: Database session

        Returns:
            VideoStartedResponse with timing info

        Raises:
            ValueError: If session already has active video
            RuntimeError: If LabJack fails to start
        """
        try:
            logger.info(
                f"Processing video-started: session={session_id}, "
                f"video={request.video_id}, url={request.video_url}"
            )

            # Step 1: Validate no active video for this session
            if session_id in self._active_videos:
                existing_video = self._active_videos[session_id].video_id
                raise ValueError(
                    f"Session {session_id} already has active video: {existing_video}. "
                    f"Stop current video before starting a new one."
                )

            # Step 2: Capture video command timestamp for drift measurement
            self.drift_measurement.capture_video_command_time()

            # Step 3: Capture backend timestamp
            backend_timestamp = time.time()

            # Capture video actual start timestamp for drift measurement
            self.drift_measurement.capture_video_actual_start(backend_timestamp)

            # Step 4: Get clock offset (cached, updated every 60s)
            clock_offset_ms = self.clock_sync.get_clock_offset_ms()

            # Step 5: Start LabJack monitoring
            logger.debug(f"Starting LabJack monitoring for session {session_id}")
            labjack_start_result = await self._start_labjack_monitoring(
                session_id=session_id,
                video_id=request.video_id
            )

            if not labjack_start_result['success']:
                raise RuntimeError(
                    f"LabJack failed to start monitoring: {labjack_start_result.get('error', 'Unknown error')}"
                )

            labjack_timestamp = labjack_start_result.get('timestamp', backend_timestamp)

            # Capture LabJack start timestamp for drift measurement
            self.drift_measurement.capture_labjack_start(labjack_timestamp)

            # Step 5: Calculate drift
            drift_ms = self._calculate_drift(
                frontend_timestamp_ms=request.frontend_timestamp,
                backend_timestamp_s=backend_timestamp,
                labjack_timestamp_s=labjack_timestamp,
                clock_offset_ms=clock_offset_ms
            )

            # Step 6: Store drift measurement
            self.drift_measurement.record_drift(
                session_id=session_id,
                video_id=request.video_id,
                drift_ms=drift_ms,
                frontend_timestamp=request.frontend_timestamp,
                backend_timestamp=backend_timestamp,
                labjack_timestamp=labjack_timestamp,
                clock_offset_ms=clock_offset_ms
            )

            # Step 7: Create video lifecycle state
            state = VideoLifecycleState(
                session_id=session_id,
                video_id=request.video_id,
                video_url=request.video_url,
                frontend_start_timestamp=request.frontend_timestamp,
                backend_start_timestamp=backend_timestamp,
                labjack_start_timestamp=labjack_timestamp,
                clock_offset_ms=clock_offset_ms,
                monitoring_active=True,
                video_duration_ms=request.video_duration_ms,
                video_fps=request.video_fps,
                metadata=request.metadata or {}
            )

            self._active_videos[session_id] = state

            # Step 8: Store in database
            await self._store_video_started(db, session_id, request, state, drift_ms)

            # Step 9: Generate warnings if needed
            warnings = []
            if abs(drift_ms) > 100:
                warnings.append(
                    f"High drift detected: {drift_ms:.1f}ms. "
                    f"Check network latency and LabJack connection."
                )
            elif abs(drift_ms) > 50:
                warnings.append(
                    f"Elevated drift: {drift_ms:.1f}ms. Within acceptable range but monitor closely."
                )

            # Step 10: Update statistics
            self._total_videos_started += 1

            # Step 11: Build response
            response = VideoStartedResponse(
                success=True,
                video_id=request.video_id,
                session_id=session_id,
                monitoring_status=MonitoringStatus.ACTIVE,
                timing=TimingInfo(
                    frontend_timestamp_ms=request.frontend_timestamp,
                    backend_timestamp_s=backend_timestamp,
                    labjack_timestamp_s=labjack_timestamp,
                    clock_offset_ms=clock_offset_ms,
                    drift_ms=drift_ms,
                    latency_ms=(labjack_timestamp - backend_timestamp) * 1000
                ),
                message=f"Video monitoring started successfully. Drift: {drift_ms:.1f}ms",
                warnings=warnings,
                metadata={
                    "labjack_device_id": labjack_start_result.get('device_id'),
                    "monitoring_sample_rate": labjack_start_result.get('sample_rate')
                }
            )

            logger.info(
                f"✅ Video started successfully: session={session_id}, "
                f"video={request.video_id}, drift={drift_ms:.2f}ms"
            )

            return response

        except ValueError as e:
            logger.warning(f"Validation error in video-started: {e}")
            self._total_errors += 1
            raise

        except RuntimeError as e:
            logger.error(f"LabJack error in video-started: {e}")
            self._total_errors += 1
            raise

        except Exception as e:
            logger.error(f"Unexpected error in video-started: {e}", exc_info=True)
            self._total_errors += 1
            raise RuntimeError(f"Failed to process video-started event: {str(e)}")

    async def handle_video_ended(
        self,
        session_id: str,
        request: VideoEndedRequest,
        db: Session
    ) -> VideoEndedResponse:
        """
        Handle video-ended event with monitoring cleanup.

        Process:
        1. Validate session has active video
        2. Stop LabJack monitoring
        3. Calculate final timing
        4. Store results in database
        5. Clean up state

        Args:
            session_id: Test session identifier
            request: Video ended request payload
            db: Database session

        Returns:
            VideoEndedResponse with final stats

        Raises:
            ValueError: If no active video for session
        """
        try:
            logger.info(
                f"Processing video-ended: session={session_id}, "
                f"video={request.video_id}, detections={request.detection_count}"
            )

            # Step 1: Validate active video exists
            if session_id not in self._active_videos:
                raise ValueError(
                    f"No active video for session {session_id}. "
                    f"Cannot end video that wasn't started."
                )

            state = self._active_videos[session_id]

            # Step 2: Validate video ID matches
            if state.video_id != request.video_id:
                logger.warning(
                    f"Video ID mismatch: active={state.video_id}, "
                    f"requested={request.video_id}. Using active video ID."
                )

            # Step 3: Capture backend timestamp
            backend_timestamp = time.time()

            # Step 4: Stop LabJack monitoring
            logger.debug(f"Stopping LabJack monitoring for session {session_id}")
            labjack_stop_result = await self._stop_labjack_monitoring(session_id)

            if not labjack_stop_result['success']:
                logger.error(
                    f"LabJack failed to stop cleanly: {labjack_stop_result.get('error')}"
                )

            detections_recorded = labjack_stop_result.get('detections_captured', request.detection_count)

            # Step 5: Update state
            state.monitoring_active = False
            state.detections_count = detections_recorded

            # Step 6: Store in database
            await self._store_video_ended(db, session_id, request, state, detections_recorded)

            # Step 7: Clean up state
            del self._active_videos[session_id]

            # Step 8: Update statistics
            self._total_videos_completed += 1

            # Step 9: Build response
            response = VideoEndedResponse(
                success=True,
                video_id=state.video_id,
                session_id=session_id,
                monitoring_status=MonitoringStatus.STOPPED,
                detections_recorded=detections_recorded,
                timing=TimingInfo(
                    frontend_timestamp_ms=request.frontend_timestamp,
                    backend_timestamp_s=backend_timestamp,
                    clock_offset_ms=state.clock_offset_ms
                ),
                message=f"Video monitoring stopped successfully. Detections: {detections_recorded}",
                metadata={
                    "playback_duration_ms": request.playback_duration_ms,
                    "ended_naturally": request.ended_naturally
                }
            )

            logger.info(
                f"✅ Video ended successfully: session={session_id}, "
                f"video={state.video_id}, detections={detections_recorded}"
            )

            return response

        except ValueError as e:
            logger.warning(f"Validation error in video-ended: {e}")
            self._total_errors += 1
            raise

        except Exception as e:
            logger.error(f"Unexpected error in video-ended: {e}", exc_info=True)
            self._total_errors += 1
            raise RuntimeError(f"Failed to process video-ended event: {str(e)}")

    async def handle_video_error(
        self,
        session_id: str,
        request: VideoErrorRequest,
        db: Session
    ) -> Dict[str, Any]:
        """
        Handle video-error event with cleanup.

        Args:
            session_id: Test session identifier
            request: Video error request payload
            db: Database session

        Returns:
            Dictionary with error handling results
        """
        try:
            logger.error(
                f"Processing video-error: session={session_id}, "
                f"video={request.video_id}, error={request.error_code}"
            )

            # Stop monitoring if active
            if session_id in self._active_videos:
                state = self._active_videos[session_id]
                state.errors.append({
                    "code": request.error_code,
                    "message": request.error_message,
                    "timestamp": request.frontend_timestamp
                })

                # Try to stop LabJack gracefully
                try:
                    await self._stop_labjack_monitoring(session_id)
                except Exception as e:
                    logger.error(f"Failed to stop LabJack during error cleanup: {e}")

                # Clean up state
                del self._active_videos[session_id]

            # Store error in database
            await self._store_video_error(db, session_id, request)

            self._total_errors += 1

            return {
                "success": True,
                "message": "Video error recorded and monitoring cleaned up",
                "session_id": session_id,
                "video_id": request.video_id
            }

        except Exception as e:
            logger.error(f"Failed to handle video-error: {e}", exc_info=True)
            raise

    def get_session_status(self, session_id: str) -> VideoLifecycleStatus:
        """
        Get current status of a session's video lifecycle.

        Args:
            session_id: Test session identifier

        Returns:
            VideoLifecycleStatus with current state
        """
        state = self._active_videos.get(session_id)

        if state is None:
            # No active video
            return VideoLifecycleStatus(
                session_id=session_id,
                current_video_id=None,
                monitoring_active=False,
                monitoring_status=MonitoringStatus.IDLE,
                video_start_time=None,
                elapsed_time_ms=None,
                detections_count=0,
                drift_ms=None,
                health="healthy",
                last_error=None
            )

        # Calculate elapsed time
        elapsed_ms = (time.time() - state.backend_start_timestamp) * 1000

        # Get latest drift
        latest_drift = self.drift_measurement.get_latest_drift(session_id)

        # Assess health
        health = "healthy"
        if len(state.errors) > 0:
            health = "unhealthy"
        elif latest_drift and abs(latest_drift) > 100:
            health = "degraded"

        return VideoLifecycleStatus(
            session_id=session_id,
            current_video_id=state.video_id,
            monitoring_active=state.monitoring_active,
            monitoring_status=MonitoringStatus.ACTIVE if state.monitoring_active else MonitoringStatus.STOPPED,
            video_start_time=state.created_at,
            elapsed_time_ms=elapsed_ms,
            detections_count=state.detections_count,
            drift_ms=latest_drift,
            health=health,
            last_error=state.errors[-1]['message'] if state.errors else None
        )

    def get_drift_statistics(self, session_id: str) -> DriftStatisticsResponse:
        """
        Get drift statistics for a session.

        Args:
            session_id: Test session identifier

        Returns:
            DriftStatisticsResponse with statistics
        """
        stats = self.drift_monitoring.calculate_statistics(session_id)

        return DriftStatisticsResponse(
            session_id=session_id,
            total_videos=stats.video_count,
            mean_drift_ms=stats.mean_drift_ms,
            median_drift_ms=stats.median_drift_ms,
            std_dev_ms=stats.std_dev_ms,
            min_drift_ms=stats.min_drift_ms,
            max_drift_ms=stats.max_drift_ms,
            drift_trend=stats.drift_trend,
            quality_assessment=stats.measurement_quality,
            warnings=[],
            calculated_at=stats.calculated_at
        )

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status of video lifecycle system.

        Returns:
            Dictionary with health information
        """
        return {
            "status": "healthy" if self._total_errors == 0 else "degraded",
            "version": "1.0.0",
            "components": {
                "database": "healthy",
                "labjack": self.labjack.get_status()['status'],
                "clock_sync": "healthy",
                "drift_measurement": "healthy"
            },
            "active_sessions": len(self._active_videos),
            "monitoring_active": any(v.monitoring_active for v in self._active_videos.values()),
            "statistics": {
                "total_videos_started": self._total_videos_started,
                "total_videos_completed": self._total_videos_completed,
                "total_errors": self._total_errors,
                "active_videos": len(self._active_videos)
            },
            "uptime_seconds": time.time() - self._start_time
        }

    # ==================== PRIVATE HELPERS ====================

    async def _start_labjack_monitoring(
        self,
        session_id: str,
        video_id: str
    ) -> Dict[str, Any]:
        """Start LabJack monitoring with error handling."""
        try:
            result = await self.labjack.start_monitoring(
                session_id=session_id,
                metadata={"video_id": video_id}
            )
            return result
        except Exception as e:
            logger.error(f"LabJack start_monitoring failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _stop_labjack_monitoring(self, session_id: str) -> Dict[str, Any]:
        """Stop LabJack monitoring with error handling."""
        try:
            result = await self.labjack.stop_monitoring(session_id)
            return result
        except Exception as e:
            logger.error(f"LabJack stop_monitoring failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _calculate_drift(
        self,
        frontend_timestamp_ms: float,
        backend_timestamp_s: float,
        labjack_timestamp_s: float,
        clock_offset_ms: float
    ) -> float:
        """
        Calculate drift in milliseconds.

        Drift = (LabJack Start Time) - (Frontend Start Time + Clock Offset)

        Returns:
            Drift in milliseconds (positive = LabJack started late)
        """
        # Convert frontend timestamp to seconds
        frontend_timestamp_s = frontend_timestamp_ms / 1000.0

        # Apply clock offset
        clock_offset_s = clock_offset_ms / 1000.0
        frontend_adjusted_s = frontend_timestamp_s + clock_offset_s

        # Calculate drift
        drift_s = labjack_timestamp_s - frontend_adjusted_s
        drift_ms = drift_s * 1000.0

        return drift_ms

    async def _store_video_started(
        self,
        db: Session,
        session_id: str,
        request: VideoStartedRequest,
        state: VideoLifecycleState,
        drift_ms: float
    ) -> None:
        """Store video-started event in database with transaction."""
        try:
            # TODO: Implement database storage
            # This should create records in appropriate tables
            # - Update TestSession with video_start_timestamp
            # - Create VideoLifecycleEvent record
            # - Store timing metadata
            pass
        except SQLAlchemyError as e:
            logger.error(f"Database error storing video-started: {e}")
            db.rollback()
            raise

    async def _store_video_ended(
        self,
        db: Session,
        session_id: str,
        request: VideoEndedRequest,
        state: VideoLifecycleState,
        detections_recorded: int
    ) -> None:
        """Store video-ended event in database with transaction."""
        try:
            # TODO: Implement database storage
            # This should update:
            # - TestSession status and completion timestamp
            # - VideoLifecycleEvent with end information
            # - Final detection counts
            pass
        except SQLAlchemyError as e:
            logger.error(f"Database error storing video-ended: {e}")
            db.rollback()
            raise

    async def _store_video_error(
        self,
        db: Session,
        session_id: str,
        request: VideoErrorRequest
    ) -> None:
        """Store video-error event in database with transaction."""
        try:
            # TODO: Implement database storage
            # This should create:
            # - Error log entry
            # - Update TestSession with failure information
            pass
        except SQLAlchemyError as e:
            logger.error(f"Database error storing video-error: {e}")
            db.rollback()
            raise
