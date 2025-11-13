"""
Video Sequence Testing Router - Multi-Video Sequential HIL Testing
===================================================================

Comprehensive API for managing multi-video sequential Hardware-in-Loop testing with:
- Dynamic video playlist management
- Real-time LabjJack monitoring integration
- Per-video timing synchronization and evaluation
- Sequence-level aggregated results
- Production-ready error handling

Endpoints:
- POST /api/video-sequences/start - Start multi-video test sequence
- POST /api/video-sequences/{sequence_id}/video-started - Record video start
- POST /api/video-sequences/{sequence_id}/video-ended - Record video end
- GET /api/video-sequences/{sequence_id}/status - Get sequence status
- GET /api/video-sequences/{sequence_id}/results - Get complete results
- POST /api/video-sequences/{sequence_id}/detection - Record detection event
- POST /api/video-sequences/{sequence_id}/stop - Stop sequence early
"""

import os
from fastapi import APIRouter, HTTPException, Depends, Body, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, validator
import logging
import uuid
import asyncio
import json
from pathlib import Path as FilePath
from collections import defaultdict

from database import SessionLocal
from models import (
    Project,
    Video,
    TestSession,
    DetectionEvent,
    SequenceVideoResult,
    VideoTestSequence,
    GroundTruthObject,
    DetectionComparison,
    Annotation
)
from schemas import CamelCaseModel
import time
from services.websocket_service import websocket_manager
from config import get_settings
from sqlalchemy import func
from services.ground_truth_matching_service import get_ground_truth_matching_service
from services.detection_video_reassignment import DetectionVideoReassignmentService

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/video-sequences", tags=["Video Sequence Testing"])

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Import video sequence orchestrator service
try:
    from services.video_sequence_orchestrator import (
        VideoSequenceOrchestrator,
        get_video_sequence_orchestrator
    )
    VIDEO_SEQUENCE_AVAILABLE = True
    logger.info("✅ Video sequence orchestrator available")
except ImportError as e:
    VIDEO_SEQUENCE_AVAILABLE = False
    logger.warning(f"⚠️ Video sequence orchestrator not available: {e}")

# Import LabjJack monitoring services
try:
    from services.dedicated_labjack_monitor import (
        start_hil_monitoring,
        stop_hil_monitoring,
        get_hil_session_events
    )
    HIL_MONITORING_AVAILABLE = True
    logger.info("✅ HIL monitoring available")
except ImportError as e:
    HIL_MONITORING_AVAILABLE = False
    logger.warning(f"⚠️ HIL monitoring not available: {e}")

settings = get_settings()


def _compute_public_base_url() -> str:
    """Determine the public base URL used for serving uploaded videos."""
    candidate = (settings.api_base_url or "").strip()
    if candidate:
        return candidate.rstrip("/")

    scheme = "https" if getattr(settings, "ssl_enabled", False) else "http"
    host = getattr(settings, "api_host", None) or "localhost"
    port = getattr(settings, "api_port", None) or 8000
    return f"{scheme}://{host}:{port}"


PUBLIC_BASE_URL = _compute_public_base_url()
UPLOADS_SEGMENT = (getattr(settings, "upload_directory", "uploads") or "uploads").strip("/\\") or "uploads"


def resolve_video_public_url(video: Optional[Video]) -> Optional[str]:
    """
    Build a publicly accessible URL for the given video record.

    The database historically stored absolute filesystem paths, relative paths,
    or fully-qualified URLs. This helper normalises those variants into a single,
    client-consumable URL.
    """
    if video is None:
        return None

    url_value = getattr(video, "url", None)
    if isinstance(url_value, str) and url_value.strip():
        trimmed = url_value.strip()
        if trimmed.startswith(("http://", "https://")):
            return trimmed

    def _normalise_path(path_value: Optional[str]) -> Optional[str]:
        if not path_value:
            return None
        normalised = str(path_value).strip().replace("\\", "/")
        if not normalised:
            return None

        if normalised.startswith(("http://", "https://")):
            return normalised

        if "/uploads/" in normalised:
            relative = normalised.split("/uploads/")[-1]
            return f"/uploads/{relative}".replace("//", "/")

        if normalised.startswith("/uploads/"):
            return normalised

        if normalised.startswith("uploads/"):
            return f"/{normalised}".replace("//", "/")

        filename = os.path.basename(normalised)
        if filename:
            return f"/{UPLOADS_SEGMENT}/{filename}".replace("//", "/")

        return None

    candidate_path = (
        _normalise_path(getattr(video, "file_path", None))
        or _normalise_path(getattr(video, "filename", None))
    )

    if not candidate_path:
        return None

    if candidate_path.startswith(("http://", "https://")):
        return candidate_path

    base_url = PUBLIC_BASE_URL or "http://localhost:8000"
    return f"{base_url.rstrip('/')}{candidate_path}"


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class VideoMetadata(CamelCaseModel):
    """Individual video metadata in sequence"""
    video_id: str = Field(..., description="Video UUID")
    video_name: str = Field(..., description="Video filename")
    duration: float = Field(..., description="Video duration in seconds")
    fps: Optional[float] = Field(None, description="Frames per second")
    sequence_index: int = Field(..., description="Position in sequence (0-based)")
    estimated_start_offset: Optional[float] = Field(None, description="Estimated start time offset in seconds")


class VideoSequenceStartRequest(CamelCaseModel):
    """Request to start a video test sequence"""
    project_id: str = Field(..., description="Project UUID")
    video_ids: List[str] = Field(..., min_items=1, description="Ordered array of video UUIDs")
    max_latency_ms: float = Field(300.0, description="Maximum acceptable latency in milliseconds", ge=0)
    test_name: Optional[str] = Field(None, description="Optional test sequence name")
    test_description: Optional[str] = Field(None, description="Optional test description")
    enable_labjack_monitoring: bool = Field(True, description="Enable LabjJack hardware monitoring")

    @validator('video_ids')
    def validate_video_ids(cls, v):
        if len(v) < 1:
            raise ValueError("At least one video is required")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate video IDs are not allowed")
        return v


class VideoSequenceStartResponse(CamelCaseModel):
    """Response from starting a video sequence"""
    sequence_id: str = Field(..., description="Unique sequence identifier")
    project_id: str = Field(..., description="Project UUID")
    test_session_id: str = Field(..., description="Test session UUID")
    total_videos: int = Field(..., description="Total number of videos in sequence")
    estimated_duration: float = Field(..., description="Estimated total duration in seconds")
    max_latency_ms: float = Field(..., description="Maximum acceptable latency")
    video_playlist: List[VideoMetadata] = Field(..., description="Ordered video playlist with metadata")
    labjack_monitoring_enabled: bool = Field(..., description="LabjJack monitoring status")
    sequence_started_at: str = Field(..., description="Sequence start timestamp (ISO 8601)")
    status: str = Field(..., description="Sequence status: 'running', 'completed', 'failed', 'stopped'")


class VideoStartedRequest(CamelCaseModel):
    """Request when a video starts playing"""
    video_id: str = Field(..., description="Video UUID that started")
    started_at: float = Field(..., description="Unix timestamp when video started (seconds)")
    client_timestamp: Optional[str] = Field(None, description="ISO 8601 client timestamp for validation")


class VideoEndedRequest(CamelCaseModel):
    """Request when a video ends playing"""
    video_id: str = Field(..., description="Video UUID that ended")
    ended_at: float = Field(..., description="Unix timestamp when video ended (seconds)")
    actual_duration: Optional[float] = Field(None, description="Actual playback duration in seconds")
    client_timestamp: Optional[str] = Field(None, description="ISO 8601 client timestamp for validation")


class NextVideoInfo(CamelCaseModel):
    """Information about the next video to play"""
    video_id: str = Field(..., description="Next video UUID")
    video_name: str = Field(..., description="Next video filename")
    sequence_index: int = Field(..., description="Position in sequence")


class VideoEndedResponse(CamelCaseModel):
    """Response after video ends"""
    video_id: str = Field(..., description="Completed video UUID")
    video_name: str = Field(..., description="Completed video filename")
    actual_duration: float = Field(..., description="Actual duration in seconds")
    detection_count: int = Field(..., description="Number of detections during video")
    evaluation_result: str = Field(..., description="Pass/fail evaluation result")
    next_video: Optional[NextVideoInfo] = Field(None, description="Next video info or null if sequence complete")
    sequence_complete: bool = Field(..., description="True if this was the last video")


class SequenceStatusResponse(CamelCaseModel):
    """Current sequence status"""
    sequence_id: str
    test_session_id: str
    overall_status: str = Field(..., description="'running', 'completed', 'failed', 'stopped'")
    current_video_index: int = Field(..., description="Current video position (0-based)")
    current_video_id: Optional[str] = Field(None, description="Current video UUID or null if none")
    current_video_name: Optional[str] = Field(None, description="Current video filename or null")
    videos_completed: int = Field(..., description="Number of videos completed")
    videos_remaining: int = Field(..., description="Number of videos remaining")
    total_videos: int = Field(..., description="Total videos in sequence")
    sequence_elapsed_time: float = Field(..., description="Elapsed time in seconds")
    estimated_remaining_time: Optional[float] = Field(None, description="Estimated remaining time in seconds")
    sequence_started_at: str = Field(..., description="ISO 8601 start timestamp")
    current_video_started_at: Optional[str] = Field(None, description="ISO 8601 current video start or null")


class DetectionEventSummary(CamelCaseModel):
    """Detection event summary for frontend"""
    id: str
    timestamp: float
    video_relative_timestamp: Optional[float] = Field(None, description="Timestamp relative to video start")
    signal_type: Optional[str] = Field(None, description="Signal type (GPIO, Network, etc.)")
    channel: Optional[str] = Field(None, description="LabjJack channel identifier")
    signal_value: Optional[float] = Field(None, description="Signal value")
    video_id: Optional[str] = Field(None, description="Video UUID this detection is associated with")
    sequence_video_result_id: Optional[str] = Field(None, description="SequenceVideoResult UUID if available")
    validation_result: Optional[str] = Field(None, description="Ground truth validation result (TP/FP/FN/PASS/FAIL)")
    latency_ms: Optional[float] = Field(None, description="Backend-calculated latency in milliseconds")
    latency_result: Optional[str] = Field(None, description="'pass' if latency within threshold, else 'fail'")


class VideoResultSummary(CamelCaseModel):
    """Per-video result summary"""
    video_id: str
    video_name: str
    sequence_index: int
    video_url: Optional[str] = Field(None, description="Public URL for video playback")
    start_time: Optional[float] = Field(None, description="Unix timestamp start time")
    end_time: Optional[float] = Field(None, description="Unix timestamp end time")
    duration: Optional[float] = Field(None, description="Actual duration in seconds")
    started_at_iso: Optional[str] = Field(None, description="ISO8601 start timestamp")
    ended_at_iso: Optional[str] = Field(None, description="ISO8601 end timestamp")
    video_status: Optional[str] = Field(None, description="Persisted video status (pending, playing, completed, failed)")
    expected_detection_count: Optional[int] = Field(None, description="Expected detection count for the video")
    actual_detection_count: Optional[int] = Field(None, description="Actual detection count recorded")
    passed_detections: Optional[int] = Field(None, description="Detections within latency threshold")
    failed_detections: Optional[int] = Field(None, description="Detections exceeding latency threshold")
    pass_rate_percent: Optional[float] = Field(None, description="Pass rate percentage across detections")
    avg_latency_ms: Optional[float] = Field(None, description="Average latency in milliseconds")
    max_latency_ms: Optional[float] = Field(None, description="Maximum latency in milliseconds")
    min_latency_ms: Optional[float] = Field(None, description="Minimum latency in milliseconds")
    latency_threshold_ms: Optional[float] = Field(None, description="Latency threshold applied during evaluation")
    detection_count: int = Field(..., description="Number of detections")
    detection_events: List[DetectionEventSummary] = Field(default_factory=list, description="List of detection events")
    pass_fail: str = Field(..., description="'pass', 'fail', 'pending', 'error'")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Detailed metrics")
    ground_truth_metrics: Optional[Dict[str, Any]] = Field(
        None, description="Ground truth metrics (TP/FP/FN, precision, recall, etc.)"
    )
    ground_truth_comparison: Optional[Dict[str, Any]] = Field(
        None, description="Normalized ground truth comparison metrics for compatibility"
    )


class SequenceResultsResponse(CamelCaseModel):
    """Complete sequence results"""
    sequence_id: str
    test_session_id: str
    project_id: str
    sequence_status: str = Field(..., description="Overall sequence status")
    total_videos: int
    videos_completed: int
    videos_passed: int
    videos_failed: int
    overall_pass_rate: float = Field(..., description="Percentage of videos passed")
    sequence_started_at: str
    sequence_completed_at: Optional[str] = Field(None, description="ISO 8601 completion timestamp or null")
    total_duration: float = Field(..., description="Total sequence duration in seconds")
    total_detections: int = Field(..., description="Total detections across all videos")
    aggregate_metrics: Dict[str, Any] = Field(default_factory=dict, description="Aggregated metrics")
    per_video_results: List[VideoResultSummary] = Field(..., description="Results for each video")
    ground_truth_comparison: Optional[Dict[str, Any]] = Field(
        None, description="Overall ground truth performance metrics for the sequence"
    )


class DetectionEventRequest(CamelCaseModel):
    """Detection event from LabjJack"""
    detection_id: Optional[str] = Field(None, description="Detection UUID (auto-generated if not provided)")
    unix_timestamp: float = Field(..., description="Unix timestamp of detection (seconds)")
    signal_type: str = Field("GPIO", description="Signal type: GPIO, Network, Serial, etc.")
    channel: Optional[int] = Field(None, description="LabjJack channel number")
    signal_value: Optional[float] = Field(None, description="Signal value")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class DetectionEventResponse(CamelCaseModel):
    """Detection event recorded response"""
    detection_id: str
    sequence_id: str
    active_video_id: Optional[str] = Field(None, description="Video ID detection was correlated to")
    active_video_name: Optional[str] = Field(None, description="Video name detection was correlated to")
    video_relative_timestamp: Optional[float] = Field(None, description="Timestamp relative to video start")
    unix_timestamp: float
    stored: bool = Field(..., description="Whether detection was successfully stored")


class SequenceStopRequest(CamelCaseModel):
    """Request to stop sequence early"""
    reason: Optional[str] = Field(None, description="Reason for stopping")
    force: bool = Field(False, description="Force stop even if errors occur")


class SequenceStopResponse(CamelCaseModel):
    """Response from stopping sequence"""
    sequence_id: str
    stopped: bool
    final_status: str
    videos_completed: int
    message: str


# ============================================================================
# ENDPOINT IMPLEMENTATIONS
# ============================================================================

@router.post("/start", response_model=VideoSequenceStartResponse, status_code=201)
async def start_video_sequence(
    request: VideoSequenceStartRequest,
    db: Session = Depends(get_db)
):
    """
    Start a multi-video sequential HIL test.

    Creates a VideoTestSequence, initializes LabjJack monitoring if available,
    and returns the video playlist with metadata for frontend player.

    **Request Body:**
    - project_id: Project UUID
    - video_ids: Ordered array of video UUIDs to test
    - max_latency_ms: Maximum acceptable detection latency (default: 300ms)
    - test_name: Optional descriptive name for the test sequence
    - enable_labjack_monitoring: Enable hardware monitoring (default: true)

    **Returns:**
    - sequence_id: Unique identifier for this test sequence
    - video_playlist: Ordered list of videos with metadata
    - LabjJack monitoring status
    """
    try:
        # Validate project exists
        project = db.query(Project).filter(Project.id == request.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {request.project_id} not found")

        # Validate all videos exist and belong to project
        videos = []
        for video_id in request.video_ids:
            video = db.query(Video).filter(
                Video.id == video_id,
                Video.project_id == request.project_id
            ).first()

            if not video:
                raise HTTPException(
                    status_code=404,
                    detail=f"Video {video_id} not found or does not belong to project {request.project_id}"
                )
            videos.append(video)

        # Create test session for this sequence
        sequence_id = str(uuid.uuid4())
        test_session_id = str(uuid.uuid4())

        session_started_at = datetime.now(timezone.utc)

        test_session = TestSession(
            id=test_session_id,
            project_id=request.project_id,
            video_id=request.video_ids[0] if request.video_ids else None,  # First video
            name=request.test_name or f"Video Sequence Test - {session_started_at.strftime('%Y-%m-%d %H:%M')}",
            description=request.test_description or f"Multi-video sequence test with {len(videos)} videos",
            status="running",
            max_latency_threshold_ms=request.max_latency_ms,
            has_video_sequence=True,  # CRITICAL: Mark this as a multi-video sequence test
            sequence_id=sequence_id,
            sequence_metadata={
                "video_ids": request.video_ids,
                "total_videos": len(videos),
                "current_video_index": 0,
                "videos_completed": 0,
                "labjack_enabled": request.enable_labjack_monitoring and HIL_MONITORING_AVAILABLE
            },
            started_at=session_started_at,
            created_at=session_started_at
        )

        db.add(test_session)

        # ✅ FIX RACE CONDITION: Flush instead of commit, then refresh and verify
        db.flush()
        db.refresh(test_session)

        # Verify critical fields are set
        assert test_session.id is not None, "test_session ID not set"
        assert test_session.sequence_id is not None, "sequence_id not set"

        logger.info(f"✅ Test session {test_session_id} flushed and verified for sequence {sequence_id}")

        # ✅ FIX: Create VideoTestSequence entry in database
        video_test_sequence = VideoTestSequence(
            id=sequence_id,
            test_session_id=test_session_id,
            name=test_session.name,
            video_ids=request.video_ids,
            sequence_order=[{"video_id": v.id, "order": idx, "duration_ms": (v.duration or 0.0) * 1000}
                          for idx, v in enumerate(videos)],
            max_latency_ms=request.max_latency_ms,
            status="running",
            current_video_index=0,
            total_videos=len(videos),
            completed_videos=0,
            sequence_start_time=time.time()
        )

        db.add(video_test_sequence)

        # Flush and verify VideoTestSequence
        db.flush()
        db.refresh(video_test_sequence)

        assert video_test_sequence.id is not None, "video_test_sequence ID not set"

        logger.info(f"✅ Created VideoTestSequence {sequence_id} with {len(videos)} videos")

        # ✅ FIX: Create SequenceVideoResult entries for each video
        video_playlist = []
        cumulative_duration = 0.0

        for idx, video in enumerate(videos):
            # Get ground truth count for this video
            gt_count = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video.id
            ).count()

            # Create sequence video result entry
            sequence_video_result = SequenceVideoResult(
                id=str(uuid.uuid4()),
                video_sequence_id=sequence_id,
                video_id=video.id,
                sequence_order=idx,
                video_status="pending",
                validation_result="pending",
                expected_detection_count=gt_count,
                actual_detection_count=0,
                passed_detections=0,
                failed_detections=0,
                latency_threshold_ms=request.max_latency_ms,
                video_play_offset_ms=cumulative_duration * 1000  # Convert to ms
            )

            db.add(sequence_video_result)

            # Build metadata for response
            video_metadata = VideoMetadata(
                video_id=video.id,
                video_name=video.filename,
                duration=video.duration or 0.0,
                fps=video.fps,
                sequence_index=idx,
                estimated_start_offset=cumulative_duration
            )
            video_playlist.append(video_metadata)
            cumulative_duration += (video.duration or 0.0)

        # ✅ FIX RACE CONDITION: Commit all session data before starting monitoring
        db.commit()
        logger.info(f"✅ Created {len(videos)} SequenceVideoResult entries and committed all session data")

        # Add small delay to ensure commit is visible to monitoring service
        await asyncio.sleep(0.1)

        # Start LabjJack monitoring if enabled and available (after verified commit)
        labjack_monitoring_enabled = False
        if request.enable_labjack_monitoring and HIL_MONITORING_AVAILABLE:
            try:
                # ✅ CRITICAL FIX: Build proper video_timing_config for monitoring
                # 🔥 FIX FOR MULTI-VIDEO: Use TOTAL sequence duration, not just first video
                first_video = videos[0]
                video_timing_config = {
                    'video_id': request.video_ids[0],
                    'fps': first_video.fps or 24,
                    'duration': cumulative_duration,  # 🔥 FIXED: Use total sequence duration to prevent early monitoring stop
                    'voltage_threshold': 3.3,  # Standard detection threshold
                    'debounce_ms': 0,  # No debounce for continuous capture
                    'channels': ['AIN0'],
                    'sample_rate': 20,
                    'enable_websocket': True,
                    'store_in_db': True
                }

                # Call with correct parameters (NOT async - remove await)
                success = start_hil_monitoring(
                    session_id=test_session_id,
                    video_timing_config=video_timing_config
                )

                if success:
                    labjack_monitoring_enabled = True
                    logger.info(f"✅ LabjJack monitoring started for sequence {sequence_id}, session {test_session_id}")
                else:
                    logger.warning(f"⚠️ LabjJack monitoring failed to start for session {test_session_id}")
            except Exception as e:
                logger.error(f"❌ Failed to start LabjJack monitoring: {e}")
                logger.exception(e)

        return VideoSequenceStartResponse(
            sequence_id=sequence_id,
            project_id=request.project_id,
            test_session_id=test_session_id,
            total_videos=len(videos),
            estimated_duration=cumulative_duration,
            max_latency_ms=request.max_latency_ms,
            video_playlist=video_playlist,
            labjack_monitoring_enabled=labjack_monitoring_enabled,
            sequence_started_at=session_started_at.isoformat(),
            status="running"
        )

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error starting video sequence: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error starting video sequence: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{sequence_id}/video-started", status_code=200)
async def record_video_started(
    sequence_id: str = Path(..., description="Sequence UUID"),
    request: VideoStartedRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Record that a video has started playing in the sequence.

    Updates the sequence timing tracker with the actual video start time,
    which is used for detection correlation and latency calculation.

    **Path Parameters:**
    - sequence_id: The video sequence UUID

    **Request Body:**
    - video_id: Video UUID that started
    - started_at: Unix timestamp when video started (seconds)
    - client_timestamp: Optional ISO 8601 client timestamp

    **Returns:**
    - Confirmation with updated sequence state
    """
    try:
        # Find test session by sequence_id
        test_session = db.query(TestSession).filter(
            TestSession.sequence_id == sequence_id
        ).first()

        if not test_session:
            raise HTTPException(status_code=404, detail=f"Sequence {sequence_id} not found")

        if test_session.status not in ["running", "in_progress"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot record video start for sequence in status: {test_session.status}"
            )

        # Validate video is in the sequence
        sequence_metadata_raw = test_session.sequence_metadata or {}
        if isinstance(sequence_metadata_raw, str):
            try:
                sequence_metadata = json.loads(sequence_metadata_raw)
            except json.JSONDecodeError:
                logger.warning(f"Invalid sequence_metadata JSON for session {test_session.id}; resetting metadata")
                sequence_metadata = {}
        else:
            sequence_metadata = dict(sequence_metadata_raw)
        video_ids = sequence_metadata.get("video_ids", [])

        if request.video_id not in video_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Video {request.video_id} is not part of sequence {sequence_id}"
            )

        # Update sequence metadata with video start time
        video_timing = sequence_metadata.get("video_timing", {})
        video_timing[request.video_id] = {
            "started_at": request.started_at,
            "started_at_iso": datetime.fromtimestamp(request.started_at, timezone.utc).isoformat(),
            "client_timestamp": request.client_timestamp
        }
        sequence_metadata["video_timing"] = video_timing
        sequence_metadata["current_video_id"] = request.video_id
        sequence_metadata["current_video_started_at"] = request.started_at

        # Update current video index
        try:
            current_index = video_ids.index(request.video_id)
            sequence_metadata["current_video_index"] = current_index
        except ValueError:
            pass

        # Persist per-video timing in sequence_video_results for backend resilience
        sequence_video_result = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == sequence_id,
            SequenceVideoResult.video_id == request.video_id
        ).first()
        if sequence_video_result:
            sequence_video_result.video_start_time = request.started_at
            sequence_video_result.video_status = "playing"
        else:
            logger.warning(
                f"SequenceVideoResult not found for sequence {sequence_id}, video {request.video_id}; "
                "unable to persist start timing"
            )

        test_session.sequence_metadata = sequence_metadata

        # ✅ FIX RACE CONDITION: Flush, refresh, verify, then commit
        db.flush()
        db.refresh(test_session)

        # Verify video timing was persisted
        assert test_session.sequence_metadata is not None, "sequence_metadata not persisted"
        assert request.video_id in test_session.sequence_metadata.get("video_timing", {}), "video timing not persisted"

        db.commit()

        # Get video name for response
        video = db.query(Video).filter(Video.id == request.video_id).first()
        video_name = video.filename if video else "Unknown"

        logger.info(f"✅ Recorded video start: {video_name} in sequence {sequence_id}")

        return {
            "sequence_id": sequence_id,
            "video_id": request.video_id,
            "video_name": video_name,
            "started_at": request.started_at,
            "message": "Video start time recorded successfully"
        }

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error recording video start: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error recording video start: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{sequence_id}/video-ended", response_model=VideoEndedResponse)
async def record_video_ended(
    sequence_id: str = Path(..., description="Sequence UUID"),
    request: VideoEndedRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Record that a video has ended and trigger per-video evaluation.

    Calculates video statistics, evaluates pass/fail criteria,
    and returns information about the next video or sequence completion.

    **Path Parameters:**
    - sequence_id: The video sequence UUID

    **Request Body:**
    - video_id: Video UUID that ended
    - ended_at: Unix timestamp when video ended (seconds)
    - actual_duration: Actual playback duration in seconds

    **Returns:**
    - Video evaluation results
    - Next video information or null if sequence complete
    - sequence_complete flag
    """
    try:
        # Find test session by sequence_id
        test_session = db.query(TestSession).filter(
            TestSession.sequence_id == sequence_id
        ).first()

        if not test_session:
            raise HTTPException(status_code=404, detail=f"Sequence {sequence_id} not found")

        # Get video
        video = db.query(Video).filter(Video.id == request.video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail=f"Video {request.video_id} not found")

        # Update sequence metadata with video end time
        raw_sequence_metadata = test_session.sequence_metadata or {}
        if isinstance(raw_sequence_metadata, str):
            try:
                sequence_metadata = json.loads(raw_sequence_metadata)
            except json.JSONDecodeError:
                sequence_metadata = {}
        else:
            sequence_metadata = dict(raw_sequence_metadata)

        video_timing = sequence_metadata.get("video_timing", {})

        if request.video_id not in video_timing:
            video_timing[request.video_id] = {}

        video_timing[request.video_id].update({
            "ended_at": request.ended_at,
            "ended_at_iso": datetime.fromtimestamp(request.ended_at, timezone.utc).isoformat(),
            "actual_duration": request.actual_duration,
            "client_timestamp": request.client_timestamp
        })

        # Calculate video duration
        started_at = video_timing[request.video_id].get("started_at")
        actual_duration = request.actual_duration
        if started_at and not actual_duration:
            actual_duration = request.ended_at - started_at
            video_timing[request.video_id]["actual_duration"] = actual_duration

        sequence_metadata["video_timing"] = video_timing

        # Count detections for this video (fixed: use test_session_id not session_id)
        detection_count = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == test_session.id,
            DetectionEvent.video_id == request.video_id
        ).count()

        video_timing[request.video_id]["detection_count"] = detection_count

        # Per-video evaluation (simplified - can be enhanced with VideoSequenceOrchestrator)
        evaluation_result = "pass" if detection_count > 0 else "pending"
        video_timing[request.video_id]["evaluation_result"] = evaluation_result

        # Update videos completed counter
        videos_completed = sequence_metadata.get("videos_completed", 0) + 1
        sequence_metadata["videos_completed"] = videos_completed

        # Persist timing/statistics for completed video
        sequence_video_result = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == sequence_id,
            SequenceVideoResult.video_id == request.video_id
        ).first()
        if sequence_video_result:
            sequence_video_result.video_end_time = request.ended_at
            if sequence_video_result.video_start_time is not None and request.ended_at:
                derived_duration = max(request.ended_at - sequence_video_result.video_start_time, 0.0)
            else:
                derived_duration = None

            duration_seconds = (
                actual_duration if actual_duration is not None
                else derived_duration
            )
            if duration_seconds is not None:
                sequence_video_result.actual_duration_ms = duration_seconds * 1000.0

            sequence_video_result.video_status = "completed"
            sequence_video_result.validation_result = evaluation_result
            sequence_video_result.actual_detection_count = detection_count
        else:
            logger.warning(
                f"SequenceVideoResult missing for sequence {sequence_id}, video {request.video_id}; "
                "unable to persist end timing"
            )

        # Determine next video
        video_ids = sequence_metadata.get("video_ids", [])
        current_index = sequence_metadata.get("current_video_index", 0)
        next_index = current_index + 1

        sequence_complete = next_index >= len(video_ids)
        next_video_info = None

        if not sequence_complete:
            next_video_id = video_ids[next_index]
            next_video = db.query(Video).filter(Video.id == next_video_id).first()
            if next_video:
                # Fallback: if client skipped /video-started, infer next start immediately
                next_video_timing = video_timing.get(next_video_id, {})
                if not isinstance(next_video_timing, dict):
                    next_video_timing = {}
                if "started_at" not in next_video_timing:
                    inferred_start = request.ended_at
                    next_video_timing.update({
                        "started_at": inferred_start,
                        "started_at_iso": datetime.fromtimestamp(inferred_start, timezone.utc).isoformat(),
                        "client_timestamp": next_video_timing.get("client_timestamp"),
                        "inferred": True
                    })
                    video_timing[next_video_id] = next_video_timing

                    pending_sequence_video_result = db.query(SequenceVideoResult).filter(
                        SequenceVideoResult.video_sequence_id == sequence_id,
                        SequenceVideoResult.video_id == next_video_id
                    ).first()
                    if pending_sequence_video_result and not pending_sequence_video_result.video_start_time:
                        pending_sequence_video_result.video_start_time = inferred_start
                        pending_sequence_video_result.video_status = pending_sequence_video_result.video_status or "pending"

                sequence_metadata["current_video_id"] = next_video_id
                sequence_metadata["current_video_started_at"] = video_timing[next_video_id].get("started_at")

                next_video_info = NextVideoInfo(
                    video_id=next_video_id,
                    video_name=next_video.filename,
                    sequence_index=next_index
                )
                sequence_metadata["current_video_index"] = next_index
        else:
            # Mark sequence as completed
            test_session.status = "completed"
            test_session.completed_at = datetime.now(timezone.utc)
            sequence_metadata["sequence_completed_at"] = test_session.completed_at.isoformat()
            logger.info(f"✅ Sequence {sequence_id} completed")

        test_session.sequence_metadata = sequence_metadata

        # ✅ FIX RACE CONDITION: Flush, refresh, verify, then commit
        db.flush()
        db.refresh(test_session)

        # Verify video end timing was persisted
        assert test_session.sequence_metadata is not None, "sequence_metadata not persisted"
        assert request.video_id in test_session.sequence_metadata.get("video_timing", {}), "video timing not persisted"

        db.commit()

        logger.info(f"✅ Recorded video end: {video.filename} in sequence {sequence_id}")

        # WebSocket Events: P0 Critical Events
        room = f"sequence_{sequence_id}"

        # Event 1: video_completed - Emit video completion stats
        await websocket_manager.send_json_to_room({
            "type": "video_completed",
            "data": {
                "sequence_id": sequence_id,
                "video_id": request.video_id,
                "video_name": video.filename,
                "actual_duration": actual_duration or 0.0,
                "detection_count": detection_count,
                "evaluation_result": evaluation_result,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }, room)

        # Event 2: video_transition or sequence_completed
        if not sequence_complete and next_video_info:
            # Emit video_transition event with next video info
            await websocket_manager.send_json_to_room({
                "type": "video_transition",
                "data": {
                    "sequence_id": sequence_id,
                    "completed_video_id": request.video_id,
                    "completed_video_name": video.filename,
                    "next_video_id": next_video_info.video_id,
                    "next_video_name": next_video_info.video_name,
                    "next_sequence_index": next_video_info.sequence_index,
                    "videos_completed": videos_completed,
                    "total_videos": len(video_ids),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }, room)
        else:
            # Emit sequence_completed event with summary
            await websocket_manager.send_json_to_room({
                "type": "sequence_completed",
                "data": {
                    "sequence_id": sequence_id,
                    "test_session_id": test_session.id,
                    "total_videos": len(video_ids),
                    "videos_completed": videos_completed,
                    "final_video_id": request.video_id,
                    "final_video_name": video.filename,
                    "sequence_status": "completed",
                    "completed_at": test_session.completed_at.isoformat() if test_session.completed_at else None,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }, room)

        return VideoEndedResponse(
            video_id=request.video_id,
            video_name=video.filename,
            actual_duration=actual_duration or 0.0,
            detection_count=detection_count,
            evaluation_result=evaluation_result,
            next_video=next_video_info,
            sequence_complete=sequence_complete
        )

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error recording video end: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error recording video end: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{sequence_id}/status", response_model=SequenceStatusResponse)
async def get_sequence_status(
    sequence_id: str = Path(..., description="Sequence UUID"),
    db: Session = Depends(get_db)
):
    """
    Get current status of a video sequence.

    Returns real-time information about sequence progress,
    current video, timing, and estimated completion.

    **Path Parameters:**
    - sequence_id: The video sequence UUID

    **Returns:**
    - Current sequence status and progress metrics
    """
    try:
        # Find test session by sequence_id
        test_session = db.query(TestSession).filter(
            TestSession.sequence_id == sequence_id
        ).first()

        if not test_session:
            raise HTTPException(status_code=404, detail=f"Sequence {sequence_id} not found")

        sequence_metadata_raw = test_session.sequence_metadata or {}
        if isinstance(sequence_metadata_raw, str):
            try:
                sequence_metadata = json.loads(sequence_metadata_raw)
            except json.JSONDecodeError:
                logger.warning(f"Invalid sequence_metadata JSON for session {test_session.id}; resetting metadata")
                sequence_metadata = {}
        else:
            sequence_metadata = dict(sequence_metadata_raw)

        # Extract status information
        video_ids = sequence_metadata.get("video_ids", [])
        current_video_index = sequence_metadata.get("current_video_index", 0)
        videos_completed = sequence_metadata.get("videos_completed", 0)
        current_video_id = sequence_metadata.get("current_video_id")

        # Get current video name
        current_video_name = None
        current_video_started_at = None
        if current_video_id:
            video = db.query(Video).filter(Video.id == current_video_id).first()
            if video:
                current_video_name = video.filename

            # Get current video start time
            video_timing = sequence_metadata.get("video_timing", {})
            if current_video_id in video_timing:
                started_at = video_timing[current_video_id].get("started_at")
                if started_at:
                    current_video_started_at = datetime.fromtimestamp(started_at, timezone.utc).isoformat()

        # Calculate elapsed time
        raw_started_at = test_session.started_at or test_session.created_at
        # Ensure timezone awareness - add UTC if missing
        sequence_started_at = raw_started_at if raw_started_at.tzinfo else raw_started_at.replace(tzinfo=timezone.utc)
        elapsed_time = (datetime.now(timezone.utc) - sequence_started_at).total_seconds()

        # Estimate remaining time (simple average-based estimation)
        videos_remaining = len(video_ids) - videos_completed
        estimated_remaining_time = None
        if videos_completed > 0 and videos_remaining > 0:
            avg_time_per_video = elapsed_time / videos_completed
            estimated_remaining_time = avg_time_per_video * videos_remaining

        return SequenceStatusResponse(
            sequence_id=sequence_id,
            test_session_id=test_session.id,
            overall_status=test_session.status or "running",
            current_video_index=current_video_index,
            current_video_id=current_video_id,
            current_video_name=current_video_name,
            videos_completed=videos_completed,
            videos_remaining=videos_remaining,
            total_videos=len(video_ids),
            sequence_elapsed_time=elapsed_time,
            estimated_remaining_time=estimated_remaining_time,
            sequence_started_at=sequence_started_at.isoformat(),
            current_video_started_at=current_video_started_at
        )

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error getting sequence status: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting sequence status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{sequence_id}/results", response_model=SequenceResultsResponse)
async def get_sequence_results(
    sequence_id: str = Path(..., description="Sequence UUID"),
    db: Session = Depends(get_db)
):
    """
    Get complete results for a video sequence.

    Returns comprehensive results including:
    - Sequence-level summary and aggregate metrics
    - Per-video results with pass/fail status
    - Detection events for each video
    - Timing and performance metrics

    **Path Parameters:**
    - sequence_id: The video sequence UUID

    **Returns:**
    - Complete sequence results with per-video breakdown
    """
    try:
        # Find test session by sequence_id
        test_session = db.query(TestSession).filter(
            TestSession.sequence_id == sequence_id
        ).first()

        if not test_session:
            raise HTTPException(status_code=404, detail=f"Sequence {sequence_id} not found")

        # Ensure detection events are linked to the correct video before calculating metrics
        if test_session.has_video_sequence and test_session.sequence_id:
            try:
                reassignment_service = DetectionVideoReassignmentService()
                reassignment_result = await reassignment_service.reassign_null_video_ids(
                    session_id=test_session.id,
                    dry_run=False
                )
                if not reassignment_result.get("success", True):
                    logger.warning(
                        "Video reassignment reported issues for session %s: %s",
                        test_session.id,
                        reassignment_result.get("error")
                    )
            except Exception as reassignment_error:
                logger.warning(
                    "Video reassignment failed for session %s: %s",
                    test_session.id,
                    reassignment_error
                )

        # Ensure ground truth comparisons are generated so downstream metrics stay in sync
        session_metrics = None
        try:
            matching_service = get_ground_truth_matching_service()
            session_metrics = matching_service.match_detections_to_ground_truth(
                session_id=test_session.id,
                tolerance_ms=getattr(test_session, "tolerance_ms", None),
                force_rematch=False
            )
        except Exception as matching_error:
            logger.warning(
                "Ground truth matching unavailable for sequence %s: %s",
                sequence_id,
                matching_error
            )
            session_metrics = None

        raw_sequence_metadata = test_session.sequence_metadata or {}
        if isinstance(raw_sequence_metadata, str):
            try:
                sequence_metadata = json.loads(raw_sequence_metadata)
            except json.JSONDecodeError:
                logger.warning("⚠️ Unable to parse sequence metadata JSON for %s", sequence_id)
                sequence_metadata = {}
        else:
            sequence_metadata = dict(raw_sequence_metadata)

        video_ids: List[str] = sequence_metadata.get("video_ids", []) or []
        video_timing = sequence_metadata.get("video_timing", {}) or {}

        # Prefetch reference data to minimise queries
        video_map: Dict[str, Video] = {}
        if video_ids:
            videos = db.query(Video).filter(Video.id.in_(video_ids)).all()
            video_map = {video.id: video for video in videos}

        video_sequence_record = db.query(VideoTestSequence).filter(
            VideoTestSequence.id == sequence_id
        ).first()

        sequence_video_results: List[SequenceVideoResult] = []
        if video_sequence_record:
            sequence_video_results = db.query(SequenceVideoResult).filter(
                SequenceVideoResult.video_sequence_id == sequence_id
            ).order_by(SequenceVideoResult.sequence_order).all()

        sequence_video_lookup: Dict[tuple, SequenceVideoResult] = {
            (result.video_id, result.sequence_order): result for result in sequence_video_results
        }

        # Pre-compute ground truth comparison counts by video to reuse inside the loop
        per_video_match_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"TP": 0, "FP": 0})
        per_video_fn_counts: Dict[str, int] = defaultdict(int)

        try:
            tp_fp_rows = (
                db.query(
                    DetectionEvent.video_id.label("video_id"),
                    DetectionComparison.match_type.label("match_type"),
                    func.count(DetectionComparison.id).label("count")
                )
                .join(
                    DetectionEvent,
                    DetectionComparison.detection_event_id == DetectionEvent.id
                )
                .filter(
                    DetectionComparison.test_session_id == test_session.id,
                    DetectionComparison.match_type.in_(["TP", "FP"])
                )
                .group_by(DetectionEvent.video_id, DetectionComparison.match_type)
                .all()
            )

            for row in tp_fp_rows:
                if row.video_id:
                    per_video_match_counts[row.video_id][row.match_type] = row.count

            fn_rows = (
                db.query(
                    Annotation.video_id.label("video_id"),
                    func.count(DetectionComparison.id).label("count")
                )
                .join(
                    Annotation,
                    DetectionComparison.ground_truth_id == Annotation.id
                )
                .filter(
                    DetectionComparison.test_session_id == test_session.id,
                    DetectionComparison.match_type == "FN"
                )
                .group_by(Annotation.video_id)
                .all()
            )

            for row in fn_rows:
                if row.video_id:
                    per_video_fn_counts[row.video_id] = row.count
        except Exception as aggregation_error:
            logger.warning(
                "Unable to aggregate per-video ground truth metrics for sequence %s: %s",
                sequence_id,
                aggregation_error
            )

        # Build per-video results
        per_video_results = []
        total_detections = 0
        videos_passed = 0
        videos_failed = 0
        videos_completed = 0
        sequence_true_positives = 0
        sequence_false_positives = 0
        sequence_false_negatives = 0

        for idx, video_id in enumerate(video_ids):
            video = video_map.get(video_id)
            if not video:
                continue

            timing_info = video_timing.get(video_id, {}) or {}

            # Get detection events for this video in this specific sequence
            # Filter by test_session_id, video_id, AND sequence_id to ensure
            # we only get events from THIS sequence run, not from other test sessions
            detection_events = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == test_session.id,
                DetectionEvent.video_id == video_id,
                DetectionEvent.sequence_id == sequence_id
            ).order_by(DetectionEvent.timestamp).all()

            # Serialize detection events for response
            detection_events_summary = []
            for event in detection_events:
                detection_events_summary.append(DetectionEventSummary(
                    id=event.id,
                    timestamp=event.unix_timestamp if hasattr(event, 'unix_timestamp') and event.unix_timestamp else event.timestamp,
                    video_relative_timestamp=getattr(event, "video_relative_timestamp", None),
                    signal_type=getattr(event, "signal_type", None),
                    channel=str(event.channel) if getattr(event, "channel", None) is not None else None,
                    signal_value=getattr(event, "signal_value", None),
                    video_id=getattr(event, "video_id", None),
                    sequence_video_result_id=getattr(event, "sequence_video_result_id", None),
                    validation_result=getattr(event, "validation_result", None),
                    latency_ms=getattr(event, "actual_latency_ms", None),
                    latency_result=getattr(event, "latency_result", None)
                ))

            # Retrieve persisted per-video result data when available
            video_result_record = sequence_video_lookup.get((video_id, idx))
            if video_result_record is None:
                video_result_record = next(
                    (record for record in sequence_video_results if record.video_id == video_id),
                    None
                )

            record_detection_count = None
            if video_result_record and video_result_record.actual_detection_count is not None:
                record_detection_count = int(video_result_record.actual_detection_count)

            detection_count = record_detection_count if record_detection_count is not None else len(detection_events)
            if detection_count == 0:
                metadata_detection_count = timing_info.get("detection_count")
                if isinstance(metadata_detection_count, (int, float)):
                    detection_count = int(metadata_detection_count)
            total_detections += detection_count

            # Determine pass/fail status
            evaluation_source = (
                video_result_record.validation_result if video_result_record and video_result_record.validation_result
                else timing_info.get("evaluation_result")
            )
            evaluation_result = (evaluation_source or "pending").lower()
            if evaluation_result == "pass":
                videos_passed += 1
            elif evaluation_result in {"fail", "failed", "error"}:
                videos_failed += 1

            # Get video metadata from Video table
            expected_duration = video.duration if video.duration is not None else 0.0
            video_fps = video.fps if video.fps is not None else 24.0
            video_url = resolve_video_public_url(video)

            start_time = timing_info.get("started_at")
            if start_time is None and video_result_record and video_result_record.video_start_time is not None:
                start_time = video_result_record.video_start_time

            end_time = timing_info.get("ended_at")
            if end_time is None and video_result_record and video_result_record.video_end_time is not None:
                end_time = video_result_record.video_end_time

            duration = timing_info.get("actual_duration")
            if duration is None and video_result_record and video_result_record.actual_duration_ms is not None:
                duration = video_result_record.actual_duration_ms / 1000.0
            if duration is None and start_time is not None and end_time is not None:
                duration = end_time - start_time

            if (
                video_result_record
                and video_result_record.video_status
                and video_result_record.video_status.lower() in {"completed", "failed"}
            ):
                videos_completed += 1
            elif end_time is not None:
                videos_completed += 1

            started_at_iso = timing_info.get("started_at_iso")
            if not started_at_iso and isinstance(start_time, (int, float)):
                started_at_iso = datetime.fromtimestamp(start_time, timezone.utc).isoformat()

            ended_at_iso = timing_info.get("ended_at_iso")
            if not ended_at_iso and isinstance(end_time, (int, float)):
                ended_at_iso = datetime.fromtimestamp(end_time, timezone.utc).isoformat()

            # Determine persisted video status and latency metrics
            video_status = None
            if video_result_record and video_result_record.video_status:
                video_status = video_result_record.video_status.lower()
            elif evaluation_result in {"pass", "fail"}:
                video_status = "completed"
            else:
                video_status = evaluation_result

            expected_detection_count_value = (
                int(video_result_record.expected_detection_count)
                if video_result_record and video_result_record.expected_detection_count is not None else None
            )

            actual_detection_count_value = detection_count

            passed_detections_value = (
                int(video_result_record.passed_detections)
                if video_result_record and video_result_record.passed_detections is not None else None
            )

            failed_detections_value = (
                int(video_result_record.failed_detections)
                if video_result_record and video_result_record.failed_detections is not None else None
            )

            pass_rate_percent_value = (
                float(video_result_record.pass_rate_percent)
                if video_result_record and video_result_record.pass_rate_percent is not None else None
            )

            avg_latency_ms_value = (
                float(video_result_record.avg_latency_ms)
                if video_result_record and video_result_record.avg_latency_ms is not None else None
            )

            max_latency_ms_value = (
                float(video_result_record.max_latency_ms)
                if video_result_record and video_result_record.max_latency_ms is not None else None
            )

            min_latency_ms_value = (
                float(video_result_record.min_latency_ms)
                if video_result_record and video_result_record.min_latency_ms is not None else None
            )

            latency_threshold_ms_value: Optional[float] = None
            if video_result_record and video_result_record.latency_threshold_ms is not None:
                latency_threshold_ms_value = float(video_result_record.latency_threshold_ms)
            else:
                metadata_latency_threshold = sequence_metadata.get("max_latency_ms")
                if isinstance(metadata_latency_threshold, (int, float)):
                    latency_threshold_ms_value = float(metadata_latency_threshold)
                elif test_session.max_latency_threshold_ms is not None:
                    latency_threshold_ms_value = float(test_session.max_latency_threshold_ms)

            if passed_detections_value is None and pass_rate_percent_value is not None:
                passed_detections_value = int(round(detection_count * (pass_rate_percent_value / 100.0)))
            if failed_detections_value is None and passed_detections_value is not None:
                failed_detections_value = max(detection_count - passed_detections_value, 0)
            if pass_rate_percent_value is None and detection_count > 0 and passed_detections_value is not None:
                pass_rate_percent_value = (passed_detections_value / detection_count) * 100.0
            if pass_rate_percent_value is not None:
                pass_rate_percent_value = round(pass_rate_percent_value, 4)

            match_counts_for_video = per_video_match_counts.get(video_id, {"TP": 0, "FP": 0})
            tp_count = match_counts_for_video.get("TP", 0)
            fp_count = match_counts_for_video.get("FP", 0)
            fn_count = per_video_fn_counts.get(video_id, 0)
            total_ground_truth_events = tp_count + fn_count

            precision_ratio = (
                tp_count / (tp_count + fp_count)
                if (tp_count + fp_count) > 0
                else 0.0
            )
            recall_ratio = (
                tp_count / total_ground_truth_events
                if total_ground_truth_events > 0
                else 0.0
            )
            f1_ratio = (
                (2 * precision_ratio * recall_ratio) / (precision_ratio + recall_ratio)
                if (precision_ratio + recall_ratio) > 0
                else 0.0
            )

            ground_truth_metrics = {
                "true_positives": tp_count,
                "false_positives": fp_count,
                "false_negatives": fn_count,
                "total_ground_truth": total_ground_truth_events,
                "precision": round(precision_ratio * 100, 1),
                "recall": round(recall_ratio * 100, 1),
                "f1_score": round(f1_ratio * 100, 1),
                "ground_truth_events_available": total_ground_truth_events
            }

            sequence_true_positives += tp_count
            sequence_false_positives += fp_count
            sequence_false_negatives += fn_count

            # Build video result summary with complete metadata
            video_result = VideoResultSummary(
                video_id=video_id,
                video_name=video.filename,
                sequence_index=idx,
                video_url=video_url,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                started_at_iso=started_at_iso,
                ended_at_iso=ended_at_iso,
                video_status=video_status,
                expected_detection_count=expected_detection_count_value,
                actual_detection_count=actual_detection_count_value,
                passed_detections=passed_detections_value,
                failed_detections=failed_detections_value,
                pass_rate_percent=pass_rate_percent_value,
                avg_latency_ms=avg_latency_ms_value,
                max_latency_ms=max_latency_ms_value,
                min_latency_ms=min_latency_ms_value,
                latency_threshold_ms=latency_threshold_ms_value,
                detection_count=detection_count,
                detection_events=detection_events_summary,
                pass_fail=evaluation_result,
                metrics={
                    "started_at_iso": started_at_iso,
                    "ended_at_iso": ended_at_iso,
                    "expected_duration": expected_duration,
                    "fps": video_fps,
                    "video_url": video_url,
                    "video_file_path": video.file_path,
                    "video_filename": video.filename,
                    "sequence_order": video_result_record.sequence_order if video_result_record else idx,
                    "video_status": video_status,
                    "expected_detection_count": expected_detection_count_value,
                    "actual_detection_count": actual_detection_count_value,
                    "metadata_detection_count": (
                        timing_info.get("detection_count")
                        if isinstance(timing_info.get("detection_count"), (int, float)) else None
                    ),
                    "pass_rate_percent": pass_rate_percent_value,
                    "avg_latency_ms": avg_latency_ms_value,
                    "max_latency_ms": max_latency_ms_value,
                    "min_latency_ms": min_latency_ms_value,
                    "latency_threshold_ms": latency_threshold_ms_value,
                    "passed_detections": passed_detections_value,
                    "failed_detections": failed_detections_value,
                    "ground_truth_metrics": ground_truth_metrics,
                    "ground_truth_comparison": ground_truth_metrics,
                    "ground_truth_events_available": total_ground_truth_events
                },
                ground_truth_metrics=ground_truth_metrics,
                ground_truth_comparison=ground_truth_metrics
            )
            per_video_results.append(video_result)

        # Calculate sequence-level metrics
        total_videos = len(video_ids)
        overall_pass_rate = (videos_passed / total_videos * 100.0) if total_videos else 0.0

        # Calculate total duration
        sequence_started_at_dt: Optional[datetime] = None
        sequence_completed_at_dt: Optional[datetime] = None
        total_duration = 0.0

        if video_sequence_record and video_sequence_record.sequence_start_time is not None:
            sequence_started_at_dt = datetime.fromtimestamp(
                video_sequence_record.sequence_start_time, timezone.utc
            )
        else:
            raw_start = test_session.started_at or test_session.created_at
            if raw_start:
                # Ensure timezone awareness - add UTC if missing
                sequence_started_at_dt = raw_start if raw_start.tzinfo else raw_start.replace(tzinfo=timezone.utc)

        if video_sequence_record and video_sequence_record.sequence_end_time is not None:
            sequence_completed_at_dt = datetime.fromtimestamp(
                video_sequence_record.sequence_end_time, timezone.utc
            )
        else:
            if test_session.completed_at:
                # Ensure timezone awareness - add UTC if missing
                sequence_completed_at_dt = test_session.completed_at if test_session.completed_at.tzinfo else test_session.completed_at.replace(tzinfo=timezone.utc)

        if video_sequence_record and video_sequence_record.total_duration_ms is not None:
            total_duration = video_sequence_record.total_duration_ms / 1000.0
        elif sequence_started_at_dt and sequence_completed_at_dt:
            total_duration = (sequence_completed_at_dt - sequence_started_at_dt).total_seconds()
        elif sequence_started_at_dt:
            total_duration = (datetime.now(timezone.utc) - sequence_started_at_dt).total_seconds()

        # Aggregate metrics
        aggregate_metrics = {
            "max_latency_threshold_ms": test_session.max_latency_threshold_ms,
            "labjack_enabled": sequence_metadata.get("labjack_enabled", False),
            "average_detections_per_video": total_detections / total_videos if total_videos else 0,
            "sequence_efficiency": videos_completed / total_videos if total_videos else 0,
            "sequence_status_recorded": video_sequence_record.status if video_sequence_record else test_session.status,
            "total_detections_recorded": total_detections,
            "videos_with_results": len(per_video_results)
        }

        total_ground_truth_events = sequence_true_positives + sequence_false_negatives
        aggregate_metrics.update({
            "ground_truth_true_positives": sequence_true_positives,
            "ground_truth_false_positives": sequence_false_positives,
            "ground_truth_false_negatives": sequence_false_negatives,
            "ground_truth_total_events": total_ground_truth_events
        })

        ground_truth_comparison: Optional[Dict[str, Any]] = None

        if session_metrics:
            ground_truth_comparison = {
                "ground_truth_events_available": session_metrics.total_ground_truth,
                "total_detections": session_metrics.total_detections,
                "true_positives": session_metrics.true_positives,
                "false_positives": session_metrics.false_positives,
                "false_negatives": session_metrics.false_negatives,
                "precision": round(session_metrics.precision * 100, 1),
                "recall": round(session_metrics.recall * 100, 1),
                "f1_score": round(session_metrics.f1_score * 100, 1),
                "matched_detections": session_metrics.matched_detections
            }
        elif total_ground_truth_events > 0 or sequence_false_positives > 0:
            precision_ratio = (
                sequence_true_positives / (sequence_true_positives + sequence_false_positives)
                if (sequence_true_positives + sequence_false_positives) > 0
                else 0.0
            )
            recall_ratio = (
                sequence_true_positives / total_ground_truth_events
                if total_ground_truth_events > 0
                else 0.0
            )
            f1_ratio = (
                (2 * precision_ratio * recall_ratio) / (precision_ratio + recall_ratio)
                if (precision_ratio + recall_ratio) > 0
                else 0.0
            )
            ground_truth_comparison = {
                "ground_truth_events_available": total_ground_truth_events,
                "total_detections": sequence_true_positives + sequence_false_positives,
                "true_positives": sequence_true_positives,
                "false_positives": sequence_false_positives,
                "false_negatives": sequence_false_negatives,
                "precision": round(precision_ratio * 100, 1),
                "recall": round(recall_ratio * 100, 1),
                "f1_score": round(f1_ratio * 100, 1),
                "matched_detections": sequence_true_positives
            }

        response_payload = SequenceResultsResponse(
            sequence_id=sequence_id,
            test_session_id=test_session.id,
            project_id=test_session.project_id,
            sequence_status=test_session.status or "running",
            total_videos=total_videos,
            videos_completed=videos_completed,
            videos_passed=videos_passed,
            videos_failed=videos_failed,
            overall_pass_rate=overall_pass_rate,
            sequence_started_at=sequence_started_at_dt.isoformat() if sequence_started_at_dt else None,
            sequence_completed_at=sequence_completed_at_dt.isoformat() if sequence_completed_at_dt else None,
            total_duration=total_duration,
            total_detections=total_detections,
            aggregate_metrics=aggregate_metrics,
            per_video_results=per_video_results,
            ground_truth_comparison=ground_truth_comparison
        )

        # Persist a copy of the response for cross-service debugging
        try:
            snapshot_dir = FilePath("logs/sequence_results")
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path = snapshot_dir / f"{sequence_id}.json"
            snapshot_data = response_payload.dict()
            with snapshot_path.open("w", encoding="utf-8") as snapshot_file:
                json.dump(snapshot_data, snapshot_file, indent=2, default=str)
            logger.info("Sequence results snapshot written to %s", snapshot_path)
        except Exception as snapshot_error:
            logger.warning("Unable to write sequence results snapshot: %s", snapshot_error)

        return response_payload

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error getting sequence results: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting sequence results: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{sequence_id}/detection", response_model=DetectionEventResponse, status_code=201)
async def record_detection_event(
    sequence_id: str = Path(..., description="Sequence UUID"),
    request: DetectionEventRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Record a detection event from LabjJack during sequence execution.

    Correlates the detection to the currently active video based on timing,
    calculates video-relative timestamp, and stores the event for analysis.

    **Path Parameters:**
    - sequence_id: The video sequence UUID

    **Request Body:**
    - unix_timestamp: Unix timestamp of detection (seconds)
    - signal_type: Type of signal (GPIO, Network, Serial, etc.)
    - channel: LabjJack channel number (optional)
    - signal_value: Signal value (optional)
    - metadata: Additional metadata (optional)

    **Returns:**
    - Detection event confirmation with correlation info
    """
    try:
        # Find test session by sequence_id
        test_session = db.query(TestSession).filter(
            TestSession.sequence_id == sequence_id
        ).first()

        if not test_session:
            raise HTTPException(status_code=404, detail=f"Sequence {sequence_id} not found")

        if test_session.status not in ["running", "in_progress"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot record detection for sequence in status: {test_session.status}"
            )

        # Determine which video was active at the detection timestamp
        sequence_metadata = test_session.sequence_metadata or {}
        video_timing = sequence_metadata.get("video_timing", {})

        active_video_id = None
        active_video_name = None
        video_relative_timestamp = None

        # Find the video that was playing at this timestamp
        for video_id, timing_info in video_timing.items():
            started_at = timing_info.get("started_at")
            ended_at = timing_info.get("ended_at")

            if started_at:
                # If video has ended, check if detection falls within its time range
                if ended_at:
                    if started_at <= request.unix_timestamp <= ended_at:
                        active_video_id = video_id
                        video_relative_timestamp = request.unix_timestamp - started_at
                        break
                # If video hasn't ended yet, check if it started before detection
                elif request.unix_timestamp >= started_at:
                    active_video_id = video_id
                    video_relative_timestamp = request.unix_timestamp - started_at
                    # Keep checking in case there's a more recent video

        if not active_video_id:
            current_video_id = sequence_metadata.get("current_video_id")
            if current_video_id:
                active_video_id = current_video_id
                timing_info = video_timing.get(current_video_id, {})
                started_at = timing_info.get("started_at") or sequence_metadata.get("current_video_started_at")
                if isinstance(started_at, (int, float)):
                    video_relative_timestamp = request.unix_timestamp - started_at

        if not active_video_id:
            # Last resort: look for the most recent sequence video result marked as playing
            candidate_sequence_video_result = db.query(SequenceVideoResult).filter(
                SequenceVideoResult.video_sequence_id == sequence_id,
                SequenceVideoResult.video_status.in_(["playing", "pending"])
            ).order_by(SequenceVideoResult.sequence_order.desc()).first()
            if candidate_sequence_video_result:
                active_video_id = candidate_sequence_video_result.video_id
                timing_info = video_timing.get(active_video_id, {})
                started_at = timing_info.get("started_at") or sequence_metadata.get("current_video_started_at")
                if isinstance(started_at, (int, float)):
                    video_relative_timestamp = request.unix_timestamp - started_at

        # Get video name if found
        if active_video_id:
            video = db.query(Video).filter(Video.id == active_video_id).first()
            if video:
                active_video_name = video.filename

        # Find or create SequenceVideoResult for this video in this sequence
        sequence_video_result: Optional[SequenceVideoResult] = None
        sequence_video_result_id = None
        if active_video_id:
            # Get the current video index from sequence metadata
            video_ids = sequence_metadata.get("video_ids", [])
            try:
                current_video_index = video_ids.index(active_video_id)
            except ValueError:
                current_video_index = 0

            # Try to find existing SequenceVideoResult
            sequence_video_result = db.query(SequenceVideoResult).filter(
                SequenceVideoResult.video_sequence_id == sequence_id,
                SequenceVideoResult.video_id == active_video_id,
                SequenceVideoResult.sequence_order == current_video_index
            ).first()

            if not sequence_video_result:
                # Create new SequenceVideoResult if it doesn't exist
                sequence_video_result = SequenceVideoResult(
                    id=str(uuid.uuid4()),
                    video_sequence_id=sequence_id,
                    video_id=active_video_id,
                    sequence_order=current_video_index,
                    video_status='playing'
                )
                db.add(sequence_video_result)
                db.flush()  # Get ID without committing
                logger.info(f"Created SequenceVideoResult {sequence_video_result.id} for video {active_video_id}")

            sequence_video_result_id = sequence_video_result.id

        # Create detection event
        detection_id = request.detection_id or str(uuid.uuid4())
        signal_value = float(request.signal_value) if request.signal_value is not None else None
        latency_threshold = (
            test_session.latency_threshold_ms
            or test_session.tolerance_ms
            or sequence_metadata.get("max_latency_ms")
            or 100
        )
        detection_channel = None
        if request.channel is not None:
            detection_channel = str(request.channel)
            if isinstance(request.signal_type, str) and request.signal_type.upper().startswith("AIN"):
                detection_channel = request.signal_type
            elif isinstance(request.channel, str):
                detection_channel = request.channel

        detection_event = DetectionEvent(
            id=detection_id,
            test_session_id=test_session.id,  # Fixed: use test_session_id not session_id
            video_id=active_video_id,
            sequence_video_result_id=sequence_video_result_id,  # ADD: Link to SequenceVideoResult
            detection_timestamp=datetime.fromtimestamp(request.unix_timestamp, timezone.utc),
            unix_timestamp=request.unix_timestamp,
            video_relative_timestamp=video_relative_timestamp,
            signal_type=request.signal_type,
            channel=detection_channel,
            signal_value=request.signal_value,
            detection_metadata=request.metadata or {},  # Fixed: use detection_metadata not metadata
            sequence_id=sequence_id,
            timestamp=request.unix_timestamp,  # Add required timestamp field
            labjack_voltage=signal_value,
            voltage_level=signal_value,
            labjack_timestamp=request.unix_timestamp,
            latency_threshold_ms=latency_threshold,
            detection_channel=detection_channel,
            validation_result="pending"
        )

        db.add(detection_event)

        # ✅ FIX RACE CONDITION: Flush, refresh, verify, then commit
        db.flush()
        db.refresh(detection_event)

        metadata_updated = False
        if sequence_video_result is not None:
            current_count = sequence_video_result.actual_detection_count or 0
            sequence_video_result.actual_detection_count = current_count + 1
            current_passed = sequence_video_result.passed_detections or 0
            sequence_video_result.passed_detections = current_passed + 1
            current_failed = sequence_video_result.failed_detections or 0
            sequence_video_result.failed_detections = max(current_failed, 0)
            if sequence_video_result.actual_detection_count:
                sequence_video_result.pass_rate_percent = round(
                    (sequence_video_result.passed_detections or 0) /
                    max(sequence_video_result.actual_detection_count, 1) * 100.0, 2
                )
            sequence_video_result.validation_result = "pass"
            sequence_video_result.video_status = sequence_video_result.video_status or "playing"
            sequence_video_result.updated_at = datetime.now(timezone.utc)
            metadata_updated = True

            video_progress = sequence_metadata.setdefault("video_progress", {})
            video_entry = video_progress.setdefault(active_video_id, {})
            video_entry["actual_detections"] = sequence_video_result.actual_detection_count
            video_entry["last_detection_timestamp"] = request.unix_timestamp
            if signal_value is not None:
                video_entry["last_signal_value"] = signal_value

        if metadata_updated:
            sequence_metadata["last_detection_timestamp"] = request.unix_timestamp
            test_session.sequence_metadata = sequence_metadata

        # Verify detection event was persisted with session reference
        assert detection_event.id is not None, "detection_event ID not set"
        assert detection_event.test_session_id is not None, "test_session_id not set on detection event"

        def _commit_with_retry(session: Session, retries: int = 5, base_delay: float = 0.05):
            last_exc: Optional[OperationalError] = None
            for attempt in range(retries):
                try:
                    session.commit()
                    return
                except OperationalError as exc:
                    last_exc = exc
                    session.rollback()
                    message = str(exc).lower()
                    if "database is locked" in message or "statements in progress" in message:
                        time.sleep(base_delay * (attempt + 1))
                        continue
                    raise
            if last_exc is not None:
                raise last_exc

        _commit_with_retry(db)

        logger.info(
            f"✅ Recorded detection event {detection_id} "
            f"for sequence {sequence_id} "
            f"(video: {active_video_name or 'unassigned'}, session: {test_session.id})"
        )

        # WebSocket Event: detection_recorded - Emit detection with video context
        room = f"sequence_{sequence_id}"
        await websocket_manager.send_json_to_room({
            "type": "detection_recorded",
            "data": {
                "detection_id": detection_id,
                "sequence_id": sequence_id,
                "active_video_id": active_video_id,
                "active_video_name": active_video_name,
                "video_relative_timestamp": video_relative_timestamp,
                "unix_timestamp": request.unix_timestamp,
                "signal_type": request.signal_type,
                "channel": request.channel,
                "signal_value": request.signal_value,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }, room)

        return DetectionEventResponse(
            detection_id=detection_id,
            sequence_id=sequence_id,
            active_video_id=active_video_id,
            active_video_name=active_video_name,
            video_relative_timestamp=video_relative_timestamp,
            unix_timestamp=request.unix_timestamp,
            stored=True
        )

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error recording detection: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error recording detection: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{sequence_id}/stop", response_model=SequenceStopResponse)
async def stop_sequence(
    sequence_id: str = Path(..., description="Sequence UUID"),
    request: SequenceStopRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Stop a video sequence early.

    Gracefully stops the sequence, marks it as stopped/failed,
    stops LabjJack monitoring, and returns final statistics.

    **Path Parameters:**
    - sequence_id: The video sequence UUID

    **Request Body:**
    - reason: Reason for stopping (optional)
    - force: Force stop even if errors occur (default: false)

    **Returns:**
    - Stop confirmation with final status
    """
    try:
        # Find test session by sequence_id
        test_session = db.query(TestSession).filter(
            TestSession.sequence_id == sequence_id
        ).first()

        if not test_session:
            raise HTTPException(status_code=404, detail=f"Sequence {sequence_id} not found")

        if test_session.status in ["completed", "stopped"]:
            return SequenceStopResponse(
                sequence_id=sequence_id,
                stopped=True,
                final_status=test_session.status,
                videos_completed=test_session.sequence_metadata.get("videos_completed", 0),
                message=f"Sequence already {test_session.status}"
            )

        # Update sequence status
        test_session.status = "stopped"
        test_session.completed_at = datetime.now(timezone.utc)

        sequence_metadata = test_session.sequence_metadata or {}
        sequence_metadata["stopped_reason"] = request.reason
        sequence_metadata["stopped_at"] = test_session.completed_at.isoformat()
        test_session.sequence_metadata = sequence_metadata

        videos_completed = sequence_metadata.get("videos_completed", 0)

        db.commit()

        # Stop LabjJack monitoring if enabled
        if HIL_MONITORING_AVAILABLE:
            try:
                await stop_hil_monitoring(session_id=test_session.id, db=db)
                logger.info(f"✅ Stopped LabjJack monitoring for sequence {sequence_id}")
            except Exception as e:
                if not request.force:
                    raise
                logger.warning(f"⚠️ Error stopping LabjJack monitoring: {e}")

        logger.info(f"✅ Stopped sequence {sequence_id} (reason: {request.reason or 'manual stop'})")

        return SequenceStopResponse(
            sequence_id=sequence_id,
            stopped=True,
            final_status="stopped",
            videos_completed=videos_completed,
            message=f"Sequence stopped successfully. {videos_completed} videos completed."
        )

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error stopping sequence: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error stopping sequence: {e}")
        if request.force:
            # Force stop even on error
            test_session.status = "stopped"
            db.commit()
            return SequenceStopResponse(
                sequence_id=sequence_id,
                stopped=True,
                final_status="stopped",
                videos_completed=0,
                message=f"Force stopped with errors: {str(e)}"
            )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for video sequence testing"""
    return {
        "status": "healthy",
        "service": "video_sequence_testing",
        "features": {
            "video_sequence_orchestrator": VIDEO_SEQUENCE_AVAILABLE,
            "hil_monitoring": HIL_MONITORING_AVAILABLE
        }
    }
