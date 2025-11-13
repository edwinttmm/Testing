"""
Video Sequence Orchestrator Service for Multi-Video Sequential Testing

This service manages sequential video playback with dynamic timing, detection correlation,
and per-video evaluation for HIL validation testing.

Architecture:
- Dynamically tracks video timing based on actual playback events
- Correlates LabjJack detections to the correct video using timing ranges
- Evaluates pass/fail criteria per-video and aggregates sequence-level metrics
- NO hardcoded timing assumptions - all timing is event-driven

Key Responsibilities:
1. Sequence initialization and video metadata loading
2. Dynamic timing management with video start/end tracking
3. Detection event correlation to correct video
4. Per-video pass/fail evaluation
5. Sequence-level metric aggregation
6. Video transition coordination
"""

import logging
import time
import uuid
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select

# Import database models
from database import get_db, SessionLocal
from models import (
    TestSession,
    Video,
    DetectionEvent,
    GroundTruthObject,
    VideoTestSequence as VideoTestSequenceModel,
    SequenceVideoResult as SequenceVideoResultModel,
)

# Import supporting services
from services.video_timing_service import VideoTimingService, get_video_timing_service
from services.clock_sync_service import validate_clock_sync, ClockSkewError, log_clock_drift_metrics
from crud import get_video, get_ground_truth_objects

logger = logging.getLogger(__name__)


class SequenceStatus(str, Enum):
    """Sequence execution status"""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoStatus(str, Enum):
    """Status of individual video in sequence"""
    PENDING = "pending"
    LOADING = "loading"
    PLAYING = "playing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class VideoMetadata:
    """Dynamic video metadata loaded from database"""
    video_id: str
    filename: str
    duration: float  # seconds
    fps: float
    frame_count: int
    ground_truth_count: int

    # Dynamic timing (set during playback)
    video_start_time: Optional[float] = None
    video_end_time: Optional[float] = None
    video_play_offset_ms: Optional[float] = None  # Offset from sequence start


@dataclass
class SequenceVideoResult:
    """Results for a single video in the sequence"""
    video_id: str
    video_index: int
    status: VideoStatus

    # Timing information (dynamically recorded)
    video_start_time: Optional[float] = None
    video_end_time: Optional[float] = None
    video_play_offset_ms: Optional[float] = None

    # Detection metrics
    expected_detections: int = 0
    detected_count: int = 0
    missed_detections: int = 0
    false_positives: int = 0

    # Latency metrics
    avg_latency_ms: Optional[float] = None
    max_latency_ms: Optional[float] = None
    min_latency_ms: Optional[float] = None
    latency_threshold_ms: float = 100.0

    # Pass/fail evaluation
    passed: bool = False
    pass_rate: float = 0.0
    failure_reason: Optional[str] = None

    # Detection events for this video
    detection_events: List[str] = field(default_factory=list)  # Detection event IDs

    # Metadata
    evaluated_at: Optional[str] = None
    evaluation_duration_ms: Optional[float] = None


@dataclass
class VideoTestSequence:
    """Container for multi-video test sequence"""
    sequence_id: str
    project_id: str
    session_id: str

    # Configuration
    video_ids: List[str]
    max_latency_ms: float

    # Status tracking
    status: SequenceStatus
    current_video_index: int = 0

    # Timing (dynamically tracked)
    sequence_start_time: Optional[float] = None
    sequence_end_time: Optional[float] = None

    # Video metadata and results
    video_metadata: Dict[str, VideoMetadata] = field(default_factory=dict)
    video_results: Dict[str, SequenceVideoResult] = field(default_factory=dict)

    # Sequence-level metrics (aggregated)
    total_expected_detections: int = 0
    total_detected: int = 0
    total_missed: int = 0
    sequence_pass_rate: float = 0.0

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class VideoSequenceOrchestratorError(Exception):
    """Custom exception for orchestrator errors"""
    pass


class VideoSequenceOrchestrator:
    """
    Orchestrates multi-video sequential testing with dynamic timing management.

    This service coordinates video playback, timing synchronization, detection correlation,
    and per-video/sequence-level evaluation for HIL validation testing.
    """

    def __init__(self, video_timing_service: Optional[VideoTimingService] = None):
        """Initialize orchestrator with timing service"""
        self._timing_service = video_timing_service or get_video_timing_service()
        self._active_sequences: Dict[str, VideoTestSequence] = {}

        # CRITICAL FIX: Import UnifiedStateService from ADR-005
        try:
            from services.unified_state_service import get_unified_state_service
            self._state_service = get_unified_state_service()
            logger.info("VideoSequenceOrchestrator initialized with UnifiedStateService (ADR-005)")
        except ImportError:
            logger.warning("UnifiedStateService not available - using manual state tracking")
            self._state_service = None

    def start_sequence(
        self,
        project_id: str,
        video_ids: List[str],
        max_latency_ms: float,
        db: Session,
        session_id: Optional[str] = None
    ) -> str:
        """
        Initialize and start a new video test sequence.

        Args:
            project_id: Project identifier
            video_ids: Ordered list of video IDs to test
            max_latency_ms: Maximum acceptable latency threshold
            db: Database session
            session_id: Optional existing test session ID

        Returns:
            Sequence ID

        Raises:
            VideoSequenceOrchestratorError: If initialization fails
        """
        try:
            # Generate sequence and session IDs
            sequence_id = str(uuid.uuid4())
            if session_id is None:
                session_id = str(uuid.uuid4())

            logger.info(f"Starting video sequence: {sequence_id}")
            logger.info(f"  Project: {project_id}")
            logger.info(f"  Videos: {len(video_ids)} videos")
            logger.info(f"  Max Latency: {max_latency_ms}ms")

            # Validate and load video metadata
            video_metadata = {}
            total_expected_detections = 0

            for video_id in video_ids:
                metadata = self._load_video_metadata(video_id, db)
                video_metadata[video_id] = metadata
                total_expected_detections += metadata.ground_truth_count

                logger.info(f"  Video {video_id}: {metadata.filename}")
                logger.info(f"    Duration: {metadata.duration:.2f}s, FPS: {metadata.fps:.2f}")
                logger.info(f"    Frame Count: {metadata.frame_count}, Ground Truth: {metadata.ground_truth_count}")

            # Initialize video results
            video_results = {}
            for idx, video_id in enumerate(video_ids):
                video_results[video_id] = SequenceVideoResult(
                    video_id=video_id,
                    video_index=idx,
                    status=VideoStatus.PENDING,
                    latency_threshold_ms=max_latency_ms
                )

            # Create sequence object
            sequence = VideoTestSequence(
                sequence_id=sequence_id,
                project_id=project_id,
                session_id=session_id,
                video_ids=video_ids,
                max_latency_ms=max_latency_ms,
                status=SequenceStatus.READY,
                video_metadata=video_metadata,
                video_results=video_results,
                total_expected_detections=total_expected_detections
            )

            # Store in active sequences
            self._active_sequences[sequence_id] = sequence

            # Create or update test session in database
            self._create_or_update_session(sequence, db)

            logger.info(f"Sequence {sequence_id} initialized successfully")
            logger.info(f"  Total expected detections: {total_expected_detections}")

            return sequence_id

        except Exception as e:
            logger.error(f"Failed to start sequence: {e}")
            raise VideoSequenceOrchestratorError(f"Failed to start sequence: {e}")

    def notify_video_started(
        self,
        sequence_id: str,
        video_id: str,
        actual_start_timestamp: float,
        db: Session
    ) -> bool:
        """
        Record when a video actually starts playing.

        Args:
            sequence_id: Sequence identifier
            video_id: Video that started
            actual_start_timestamp: Unix timestamp when video started
            db: Database session

        Returns:
            True if successful, False otherwise
        """
        try:
            # CLOCK SYNC VALIDATION: Verify frontend timestamp is synchronized
            try:
                validate_clock_sync(
                    frontend_timestamp=actual_start_timestamp,
                    max_frontend_drift_seconds=5.0
                )
                logger.debug(f"Clock sync validated for video_started event (video: {video_id})")
            except ClockSkewError as clock_error:
                logger.error(f"CLOCK SKEW DETECTED on video_started: {clock_error}")
                logger.error(f"  Drift: {clock_error.drift_seconds:.3f}s exceeds tolerance")
                logger.error(f"  Rejecting video_started event for video {video_id}")
                return False

            sequence = self._get_sequence(sequence_id)

            # Validate video belongs to sequence
            if video_id not in sequence.video_ids:
                raise VideoSequenceOrchestratorError(f"Video {video_id} not in sequence {sequence_id}")

            # Initialize sequence start time on first video with atomic CAS
            if sequence.sequence_start_time is None:
                # RACE CONDITION FIX: Use atomic Compare-And-Swap with database-level locking
                cas_success = self._initialize_sequence_start_atomic(
                    db=db,
                    sequence_id=sequence_id,
                    start_time=actual_start_timestamp
                )

                if cas_success:
                    # Only update in-memory state if we won the race
                    sequence.sequence_start_time = actual_start_timestamp
                    sequence.status = SequenceStatus.RUNNING
                    logger.info(f"✅ ATOMIC CAS: Set sequence_start_time={actual_start_timestamp:.6f}")
                else:
                    # Another thread already set it - reload from database
                    try:
                        video_sequence_db = db.query(VideoTestSequenceModel).filter(
                            VideoTestSequenceModel.id == sequence_id
                        ).first()

                        if video_sequence_db and video_sequence_db.sequence_start_time:
                            sequence.sequence_start_time = video_sequence_db.sequence_start_time
                            sequence.status = SequenceStatus.RUNNING
                            logger.info(f"⚠️ RACE LOST: Using existing sequence_start_time={sequence.sequence_start_time:.6f}")
                        else:
                            logger.error(f"❌ CAS failed but no sequence_start_time in DB - using provided value")
                            sequence.sequence_start_time = actual_start_timestamp
                    except Exception as reload_error:
                        logger.error(f"❌ Failed to reload sequence_start_time after CAS loss: {reload_error}")
                        sequence.sequence_start_time = actual_start_timestamp

            # Calculate video play offset from sequence start
            video_play_offset_ms = (actual_start_timestamp - sequence.sequence_start_time) * 1000.0

            # CRITICAL FIX: Use UnifiedStateService for atomic state updates
            if self._state_service:
                # Update state atomically via UnifiedStateService
                self._state_service.update_video_state(
                    sequence_id=sequence_id,
                    video_id=video_id,
                    state={
                        'video_start_time': actual_start_timestamp,
                        'video_play_offset_ms': video_play_offset_ms,
                        'status': 'playing',
                        'expected_detections': sequence.video_metadata[video_id].ground_truth_count
                    }
                )

            # Update video metadata
            metadata = sequence.video_metadata[video_id]
            metadata.video_start_time = actual_start_timestamp
            metadata.video_play_offset_ms = video_play_offset_ms

            # Update video result
            result = sequence.video_results[video_id]
            result.video_start_time = actual_start_timestamp
            result.video_play_offset_ms = video_play_offset_ms
            result.status = VideoStatus.PLAYING
            result.expected_detections = metadata.ground_truth_count

            # Update current video index
            sequence.current_video_index = sequence.video_ids.index(video_id)

            # Start video timing in timing service
            self._timing_service.start_video_timing(
                session_id=sequence.session_id,
                video_id=video_id,
                db=db,
                video_metadata={
                    'fps': metadata.fps,
                    'duration': metadata.duration,
                    'frame_count': metadata.frame_count
                }
            )

            logger.info(f"Video started: {video_id}")
            logger.info(f"  Start time: {actual_start_timestamp:.6f}")
            logger.info(f"  Play offset: {video_play_offset_ms:.3f}ms")
            logger.info(f"  Expected detections: {metadata.ground_truth_count}")

            return True

        except Exception as e:
            logger.error(f"Failed to notify video started: {e}")
            return False

    def notify_video_ended(
        self,
        sequence_id: str,
        video_id: str,
        actual_end_timestamp: float,
        db: Session
    ) -> bool:
        """
        Record when a video ends and evaluate its results.

        Args:
            sequence_id: Sequence identifier
            video_id: Video that ended
            actual_end_timestamp: Unix timestamp when video ended
            db: Database session

        Returns:
            True if successful, False otherwise
        """
        try:
            sequence = self._get_sequence(sequence_id)

            # Validate video belongs to sequence
            if video_id not in sequence.video_ids:
                raise VideoSequenceOrchestratorError(f"Video {video_id} not in sequence {sequence_id}")

            # Update video metadata and result
            metadata = sequence.video_metadata[video_id]
            metadata.video_end_time = actual_end_timestamp

            result = sequence.video_results[video_id]
            result.video_end_time = actual_end_timestamp
            result.status = VideoStatus.COMPLETED

            # Calculate actual video duration
            if metadata.video_start_time:
                actual_duration = actual_end_timestamp - metadata.video_start_time
                logger.info(f"Video ended: {video_id}")
                logger.info(f"  End time: {actual_end_timestamp:.6f}")
                logger.info(f"  Actual duration: {actual_duration:.2f}s (expected: {metadata.duration:.2f}s)")

            # Evaluate video results
            evaluation_start = time.time()
            self._evaluate_video_results(sequence_id, video_id, db)
            evaluation_duration = (time.time() - evaluation_start) * 1000.0

            result.evaluated_at = datetime.now(timezone.utc).isoformat()
            result.evaluation_duration_ms = evaluation_duration

            logger.info(f"Video evaluation completed in {evaluation_duration:.2f}ms")
            logger.info(f"  Result: {'PASS' if result.passed else 'FAIL'}")
            logger.info(f"  Pass rate: {result.pass_rate:.2%}")

            # Check if this was the last video
            if sequence.current_video_index >= len(sequence.video_ids) - 1:
                logger.info(f"Last video completed - finalizing sequence {sequence_id}")
                self._finalize_sequence(sequence_id, db)
            else:
                logger.info(f"Video {sequence.current_video_index + 1}/{len(sequence.video_ids)} completed")

            return True

        except Exception as e:
            logger.error(f"Failed to notify video ended: {e}")
            return False

    def process_detection_event(
        self,
        sequence_id: str,
        labjack_signal: Dict[str, Any],
        sequence_timestamp: float,
        db: Session
    ) -> Optional[str]:
        """
        Process a LabjJack detection event and correlate to correct video.

        Args:
            sequence_id: Sequence identifier
            labjack_signal: LabjJack signal data
            sequence_timestamp: Unix timestamp of detection
            db: Database session

        Returns:
            Detection event ID if created, None otherwise
        """
        try:
            sequence = self._get_sequence(sequence_id)

            # Determine which video was playing at detection time
            video_id = self._determine_video_for_detection(sequence, sequence_timestamp)

            if video_id is None:
                logger.warning(f"Could not determine video for detection at {sequence_timestamp:.6f}")
                return None

            metadata = sequence.video_metadata[video_id]
            result = sequence.video_results[video_id]

            # Ensure sequence start time is initialized
            if sequence.sequence_start_time is None:
                sequence.sequence_start_time = sequence_timestamp
                sequence.status = SequenceStatus.RUNNING
                logger.debug(
                    "Inferred sequence start time %.6f from first detection",
                    sequence.sequence_start_time,
                )

            # Ensure per-video start information exists
            if metadata.video_start_time is None:
                inferred_offset_ms: Optional[float] = metadata.video_play_offset_ms

                if inferred_offset_ms is None:
                    try:
                        inferred_offset_ms = self.get_video_play_offset_ms(
                            video_id=video_id,
                            session_id=sequence.session_id,
                            db=db,
                        )
                    except Exception as offset_error:
                        logger.debug(
                            "Failed to calculate offset for video %s: %s",
                            video_id,
                            offset_error,
                        )
                        inferred_offset_ms = None

                if (inferred_offset_ms is None or inferred_offset_ms == 0.0) and video_id in sequence.video_ids:
                    try:
                        video_position = sequence.video_ids.index(video_id)
                    except ValueError:
                        video_position = 0

                    if video_position > 0:
                        cumulative_offset = 0.0
                        for prev_id in sequence.video_ids[:video_position]:
                            prev_meta = sequence.video_metadata.get(prev_id)
                            if prev_meta and prev_meta.duration:
                                cumulative_offset += prev_meta.duration * 1000.0

                        if cumulative_offset > 0.0:
                            inferred_offset_ms = cumulative_offset
                            logger.debug(
                                "Approximated offset for %s using metadata durations: %.3fms",
                                video_id,
                                cumulative_offset,
                            )

                if inferred_offset_ms is None:
                    inferred_offset_ms = 0.0

                metadata.video_play_offset_ms = inferred_offset_ms
                result.video_play_offset_ms = inferred_offset_ms

                metadata.video_start_time = sequence.sequence_start_time + (inferred_offset_ms / 1000.0)
                result.video_start_time = metadata.video_start_time
                logger.debug(
                    "Inferred video start for %s at %.6f (offset %.3fms)",
                    video_id,
                    metadata.video_start_time,
                    inferred_offset_ms,
                )

            buffer_seconds = 1.0  # Allow 1 second buffer
            primary_relative: Optional[float] = None
            if metadata.video_start_time is not None:
                primary_relative = sequence_timestamp - metadata.video_start_time

            offset_seconds = (
                (metadata.video_play_offset_ms or 0.0) / 1000.0
                if metadata.video_play_offset_ms is not None
                else None
            )
            fallback_relative: Optional[float] = None
            if sequence.sequence_start_time is not None and offset_seconds is not None:
                fallback_relative = (sequence_timestamp - sequence.sequence_start_time) - offset_seconds

            # Choose the best available relative timestamp
            video_relative_timestamp = primary_relative if primary_relative is not None else fallback_relative

            if video_relative_timestamp is None and fallback_relative is not None:
                video_relative_timestamp = fallback_relative

            if video_relative_timestamp is None:
                logger.warning(f"Unable to compute video-relative timestamp for video {video_id}")
                return None

            # If primary value looks out of range but fallback is reasonable, use fallback
            if (
                fallback_relative is not None
                and (
                    video_relative_timestamp < -buffer_seconds
                    or video_relative_timestamp > (metadata.duration + buffer_seconds)
                )
            ):
                logger.debug(
                    "Resetting video-relative timestamp using sequence offset: %.3fs → %.3fs",
                    video_relative_timestamp,
                    fallback_relative,
                )
                video_relative_timestamp = fallback_relative

            # Clamp very small negative values caused by rounding
            if -0.001 < video_relative_timestamp < 0:
                video_relative_timestamp = 0.0

            # Validate timestamp is within video duration (with buffer)
            if video_relative_timestamp < -buffer_seconds or video_relative_timestamp > (metadata.duration + buffer_seconds):
                logger.warning(
                    f"Detection timestamp {video_relative_timestamp:.3f}s outside video duration {metadata.duration:.2f}s"
                )

            # Calculate video frame number (ensure non-negative)
            frame_number_raw = int(round(video_relative_timestamp * metadata.fps))
            video_frame_number = max(frame_number_raw, 0)

            # Determine sequence-relative timing information
            sequence_identifier = sequence.sequence_id
            sequence_relative_timestamp = None

            if sequence.sequence_start_time is not None:
                sequence_relative_timestamp = sequence_timestamp - sequence.sequence_start_time
            elif metadata.video_play_offset_ms is not None:
                sequence_relative_timestamp = video_relative_timestamp + ((metadata.video_play_offset_ms or 0.0) / 1000.0)

            # Resolve associated SequenceVideoResult record if available
            sequence_video_result_id: Optional[str] = None
            try:
                video_sequence_record = None
                if sequence_identifier:
                    video_sequence_record = db.query(VideoTestSequenceModel).filter(
                        VideoTestSequenceModel.id == sequence_identifier
                    ).first()
                if video_sequence_record is None:
                    video_sequence_record = db.query(VideoTestSequenceModel).filter(
                        VideoTestSequenceModel.test_session_id == sequence.session_id
                    ).first()
                    if video_sequence_record and not sequence_identifier:
                        candidate_identifier = getattr(video_sequence_record, 'id', None)
                        if isinstance(candidate_identifier, str):
                            sequence_identifier = candidate_identifier
                            sequence.sequence_id = sequence_identifier

                if video_sequence_record:
                    sequence_record_id = getattr(video_sequence_record, 'id', None)
                    if isinstance(sequence_record_id, str):
                        video_sequence_record_id = sequence_record_id
                    else:
                        video_sequence_record_id = None
                else:
                    video_sequence_record_id = None

                if video_sequence_record_id:
                    sequence_video_result_record = db.query(SequenceVideoResultModel).filter(
                        SequenceVideoResultModel.video_sequence_id == video_sequence_record_id,
                        SequenceVideoResultModel.video_id == video_id
                    ).first()
                    if sequence_video_result_record:
                        record_id = getattr(sequence_video_result_record, 'id', None)
                        if isinstance(record_id, str):
                            sequence_video_result_id = record_id
                            current_count = sequence_video_result_record.actual_detection_count or 0
                            sequence_video_result_record.actual_detection_count = current_count + 1
            except SQLAlchemyError as query_error:
                logger.warning("Failed to associate detection with sequence video result: %s", query_error)

            # Extract signal metadata
            detection_metadata = labjack_signal.copy() if isinstance(labjack_signal, dict) else {}
            raw_voltage = None
            if isinstance(labjack_signal, dict):
                raw_voltage = (
                    labjack_signal.get('voltage')
                    or labjack_signal.get('signal_value')
                    or labjack_signal.get('value')
                )
            voltage_level = None
            try:
                if raw_voltage is not None:
                    voltage_level = float(raw_voltage)
            except (TypeError, ValueError):
                voltage_level = None

            raw_channel = None
            if isinstance(labjack_signal, dict):
                raw_channel = labjack_signal.get('channel')
            channel_value: Optional[int] = None
            if isinstance(raw_channel, (int, float)):
                channel_value = int(raw_channel)
            elif isinstance(raw_channel, str) and raw_channel.isdigit():
                channel_value = int(raw_channel)

            detection_channel_label = None
            if isinstance(raw_channel, str):
                detection_channel_label = raw_channel
            elif raw_channel is not None:
                detection_channel_label = str(raw_channel)

            signal_type = None
            if isinstance(labjack_signal, dict):
                signal_type = labjack_signal.get('signal_type') or labjack_signal.get('type')

            # Create detection event
            detection_event_kwargs: Dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "test_session_id": sequence.session_id,
                "video_id": video_id,
                "timestamp": sequence_timestamp,
                "labjack_timestamp": sequence_timestamp,
                "video_start_time": metadata.video_start_time,
                "video_relative_timestamp": video_relative_timestamp,
                "video_frame_number": video_frame_number,
                "frame_number": video_frame_number,
                "video_play_offset_ms": metadata.video_play_offset_ms,
                "sequence_id": sequence_identifier,
                "sequence_video_result_id": sequence_video_result_id,
                "sequence_timestamp": sequence_relative_timestamp,
                "voltage_level": voltage_level,
                "labjack_voltage": voltage_level,
                "detection_channel": detection_channel_label,
                "channel": channel_value,
                "signal_type": signal_type,
                "signal_value": voltage_level,
                "detection_metadata": detection_metadata,
                "timing_sync_quality": "high",
                "validation_result": "pending",
                "latency_threshold_ms": sequence.max_latency_ms
            }

            if detection_event_kwargs.get("sequence_timestamp") is None:
                detection_event_kwargs.pop("sequence_timestamp", None)
            if detection_event_kwargs.get("sequence_video_result_id") is None:
                detection_event_kwargs.pop("sequence_video_result_id", None)

            detection_event = DetectionEvent(**detection_event_kwargs)

            db.add(detection_event)
            db.commit()
            db.refresh(detection_event)

            # Add to video results
            result.detection_events.append(detection_event.id)
            result.detected_count += 1
            sequence.total_detected += 1

            logger.info(f"Detection event created: {detection_event.id}")
            logger.info(f"  Video: {video_id}")
            logger.info(f"  Video-relative time: {video_relative_timestamp:.3f}s")
            logger.info(f"  Frame number: {video_frame_number}")

            return detection_event.id

        except Exception as e:
            logger.error(f"Failed to process detection event: {e}")
            db.rollback()
            return None

    def get_sequence_status(self, sequence_id: str) -> Dict[str, Any]:
        """
        Get current status of sequence execution.

        Args:
            sequence_id: Sequence identifier

        Returns:
            Status information dictionary
        """
        try:
            sequence = self._get_sequence(sequence_id)

            current_video_id = None
            if 0 <= sequence.current_video_index < len(sequence.video_ids):
                current_video_id = sequence.video_ids[sequence.current_video_index]

            return {
                "sequence_id": sequence_id,
                "status": sequence.status.value,
                "current_video_index": sequence.current_video_index,
                "total_videos": len(sequence.video_ids),
                "current_video_id": current_video_id,
                "sequence_start_time": sequence.sequence_start_time,
                "total_expected_detections": sequence.total_expected_detections,
                "total_detected": sequence.total_detected,
                "video_statuses": {
                    vid: result.status.value
                    for vid, result in sequence.video_results.items()
                }
            }

        except Exception as e:
            logger.error(f"Failed to get sequence status: {e}")
            return {"error": str(e)}

    def get_sequence_results(self, sequence_id: str, db: Session) -> Dict[str, Any]:
        """
        Get complete results for a sequence.

        Args:
            sequence_id: Sequence identifier
            db: Database session

        Returns:
            Complete results dictionary
        """
        try:
            sequence = self._get_sequence(sequence_id)

            # Build per-video results
            video_results = []
            for video_id in sequence.video_ids:
                result = sequence.video_results[video_id]
                video_results.append({
                    "video_id": video_id,
                    "video_index": result.video_index,
                    "filename": sequence.video_metadata[video_id].filename,
                    "status": result.status.value,
                    "passed": result.passed,
                    "pass_rate": result.pass_rate,
                    "expected_detections": result.expected_detections,
                    "detected_count": result.detected_count,
                    "missed_detections": result.missed_detections,
                    "false_positives": result.false_positives,
                    "avg_latency_ms": result.avg_latency_ms,
                    "max_latency_ms": result.max_latency_ms,
                    "min_latency_ms": result.min_latency_ms,
                    "failure_reason": result.failure_reason,
                    "video_start_time": result.video_start_time,
                    "video_end_time": result.video_end_time,
                    "video_play_offset_ms": result.video_play_offset_ms
                })

            # Sequence-level summary
            return {
                "sequence_id": sequence_id,
                "session_id": sequence.session_id,
                "project_id": sequence.project_id,
                "status": sequence.status.value,
                "video_count": len(sequence.video_ids),
                "max_latency_ms": sequence.max_latency_ms,

                # Timing
                "sequence_start_time": sequence.sequence_start_time,
                "sequence_end_time": sequence.sequence_end_time,
                "total_duration_s": (
                    (sequence.sequence_end_time - sequence.sequence_start_time)
                    if sequence.sequence_end_time and sequence.sequence_start_time
                    else None
                ),

                # Aggregate metrics
                "total_expected_detections": sequence.total_expected_detections,
                "total_detected": sequence.total_detected,
                "total_missed": sequence.total_missed,
                "sequence_pass_rate": sequence.sequence_pass_rate,

                # Per-video results
                "video_results": video_results,

                # Metadata
                "created_at": sequence.created_at,
                "completed_at": sequence.completed_at,
                "error_message": sequence.error_message
            }

        except Exception as e:
            logger.error(f"Failed to get sequence results: {e}")
            return {"error": str(e)}

    # ===== Private Helper Methods =====

    def _get_sequence(self, sequence_id: str) -> VideoTestSequence:
        """Get sequence or raise error"""
        if sequence_id not in self._active_sequences:
            raise VideoSequenceOrchestratorError(f"Sequence {sequence_id} not found")
        return self._active_sequences[sequence_id]

    def _load_video_metadata(self, video_id: str, db: Session) -> VideoMetadata:
        """Load video metadata from database"""
        try:
            video = get_video(db, video_id)
            if not video:
                raise VideoSequenceOrchestratorError(f"Video {video_id} not found")

            # Get ground truth count
            ground_truth_objects = get_ground_truth_objects(db, video_id)
            ground_truth_count = len(ground_truth_objects)

            # Calculate frame count
            frame_count = int(video.duration * video.fps) if video.duration and video.fps else 0

            return VideoMetadata(
                video_id=video_id,
                filename=video.filename,
                duration=video.duration or 0.0,
                fps=video.fps or 30.0,
                frame_count=frame_count,
                ground_truth_count=ground_truth_count
            )

        except Exception as e:
            logger.error(f"Failed to load video metadata for {video_id}: {e}")
            raise VideoSequenceOrchestratorError(f"Failed to load video metadata: {e}")

    def _determine_video_for_detection(
        self,
        sequence: VideoTestSequence,
        detection_timestamp: float
    ) -> Optional[str]:
        """Determine which video was playing at detection time"""

        # Find video whose time range includes the detection
        for video_id in sequence.video_ids:
            metadata = sequence.video_metadata[video_id]

            # Skip videos that haven't started yet
            if metadata.video_start_time is None:
                continue

            # Check if detection falls within video time range
            # Use end time if available, otherwise use start + duration
            video_end = metadata.video_end_time or (metadata.video_start_time + metadata.duration + 1.0)

            if metadata.video_start_time <= detection_timestamp <= video_end:
                return video_id

        return None

    def _evaluate_video_results(self, sequence_id: str, video_id: str, db: Session):
        """Evaluate pass/fail for a completed video"""
        try:
            sequence = self._get_sequence(sequence_id)
            result = sequence.video_results[video_id]

            # Get ground truth for this video
            ground_truth_objects = get_ground_truth_objects(db, video_id)

            # Get detection events for this video
            try:
                detection_events = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == sequence.session_id,
                    DetectionEvent.video_id == video_id
                ).all()
                if detection_events is None:
                    detection_events = []
            except Exception as query_error:
                logger.warning(
                    "Failed to load detection events from DB for video %s: %s",
                    video_id,
                    query_error,
                )
                detection_events = []

            # Calculate metrics
            expected_count = len(ground_truth_objects)
            detected_count = len(detection_events)

            # Calculate latencies
            latencies: List[float] = []
            for event in detection_events:
                if getattr(event, 'actual_latency_ms', None) is not None:
                    latencies.append(event.actual_latency_ms)

            # If DB lookup returned nothing but we have in-memory detections, fall back
            if detected_count == 0 and result.detection_events:
                detected_count = len(result.detection_events)
                latencies = []

            # Update result metrics
            result.expected_detections = expected_count
            result.detected_count = detected_count
            result.missed_detections = max(0, expected_count - detected_count)
            result.false_positives = max(0, detected_count - expected_count)

            if latencies:
                result.avg_latency_ms = sum(latencies) / len(latencies)
                result.max_latency_ms = max(latencies)
                result.min_latency_ms = min(latencies)

            # Determine pass/fail
            if expected_count == 0:
                result.passed = True
                result.pass_rate = 1.0
            else:
                result.pass_rate = detected_count / expected_count

                # Pass criteria: all detections found and within latency threshold
                all_detected = detected_count >= expected_count
                within_threshold = all(lat <= sequence.max_latency_ms for lat in latencies) if latencies else True

                result.passed = all_detected and within_threshold

                if not all_detected:
                    result.failure_reason = f"Missed {result.missed_detections} detections"
                elif not within_threshold:
                    result.failure_reason = f"Max latency {result.max_latency_ms:.1f}ms exceeds threshold"

            logger.info(f"Video {video_id} evaluation:")
            logger.info(f"  Expected: {expected_count}, Detected: {detected_count}")
            logger.info(f"  Pass rate: {result.pass_rate:.2%}")
            logger.info(f"  Result: {'PASS' if result.passed else 'FAIL'}")

        except Exception as e:
            logger.error(f"Failed to evaluate video results: {e}")
            raise

    def _finalize_sequence(self, sequence_id: str, db: Session):
        """Finalize sequence and compute aggregate metrics"""
        try:
            sequence = self._get_sequence(sequence_id)

            sequence.sequence_end_time = time.time()
            sequence.completed_at = datetime.now(timezone.utc).isoformat()

            # Aggregate sequence-level metrics
            total_detected = 0
            total_missed = 0

            for video_id in sequence.video_ids:
                result = sequence.video_results[video_id]
                total_detected += result.detected_count
                total_missed += result.missed_detections

            sequence.total_detected = total_detected
            sequence.total_missed = total_missed

            if sequence.total_expected_detections > 0:
                sequence.sequence_pass_rate = total_detected / sequence.total_expected_detections
            else:
                sequence.sequence_pass_rate = 1.0

            # Update sequence status
            all_passed = all(result.passed for result in sequence.video_results.values())
            sequence.status = SequenceStatus.COMPLETED if all_passed else SequenceStatus.FAILED

            # CRITICAL FIX: Persist sequence_end_time and final status to VideoTestSequence table
            try:
                video_sequence_db = db.query(VideoTestSequenceModel).filter(
                    VideoTestSequenceModel.id == sequence_id
                ).first()

                if video_sequence_db:
                    video_sequence_db.sequence_end_time = sequence.sequence_end_time
                    video_sequence_db.status = sequence.status.value
                    if sequence.sequence_start_time:
                        video_sequence_db.total_duration_ms = (sequence.sequence_end_time - sequence.sequence_start_time) * 1000.0
                    db.commit()
                    logger.info(f"✅ PERSISTED sequence_end_time={sequence.sequence_end_time:.6f} to VideoTestSequence table")
                else:
                    logger.error(f"❌ ERROR: VideoTestSequence not found in database for sequence_id {sequence_id}")
            except Exception as db_error:
                logger.error(f"❌ FAILED to persist sequence_end_time: {db_error}")
                db.rollback()

            logger.info(f"Sequence {sequence_id} finalized")
            logger.info(f"  Total expected: {sequence.total_expected_detections}")
            logger.info(f"  Total detected: {sequence.total_detected}")
            logger.info(f"  Sequence pass rate: {sequence.sequence_pass_rate:.2%}")
            logger.info(f"  Final status: {sequence.status.value}")

            # Stop LabJack monitoring now that sequence is complete
            try:
                from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
                monitor = get_dedicated_labjack_monitor()
                stop_result = monitor.stop_session_monitoring(sequence.session_id)
                if stop_result.get('success'):
                    logger.info(f"✅ Stopped monitoring for completed sequence {sequence_id}")
                else:
                    logger.warning(f"⚠️ Failed to stop monitoring: {stop_result.get('message')}")
            except Exception as monitor_error:
                logger.error(f"Failed to stop monitoring for sequence {sequence_id}: {monitor_error}")

        except Exception as e:
            logger.error(f"Failed to finalize sequence: {e}")
            raise

    def get_video_for_timestamp(
        self,
        session_id: str,
        timestamp: float,
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """Get video information for a given timestamp.

        Args:
            session_id: Test session ID
            timestamp: System timestamp to check
            db: Database session

        Returns:
            Dict with video info (id, start_time, end_time, sequence_index) or None
        """
        from models import VideoProjectLink

        session = db.query(TestSession).filter_by(id=session_id).first()
        if not session:
            logger.error(f"Session {session_id} not found")
            return None

        videos = db.query(VideoProjectLink).filter_by(session_id=session_id).all()
        if not videos:
            logger.warning(f"No videos found for session {session_id}")
            return None

        # Sort by sequence index
        sorted_videos = sorted(videos, key=lambda v: v.sequence_index or 0)

        for video in sorted_videos:
            video_start = video.video_start_time
            video_end = video.video_end_time

            # Skip videos without start time
            if video_start is None:
                continue

            # Check if timestamp falls within this video's time range
            # For last/current video (no end time), check if after start
            if video_end is None:
                if timestamp >= video_start:
                    return {
                        'id': video.id,
                        'start_time': video_start,
                        'end_time': video_end,
                        'sequence_index': video.sequence_index,
                        'duration': video.duration,
                        'status': video.status
                    }
            # For completed videos, check range [start, end)
            elif video_start <= timestamp < video_end:
                return {
                    'id': video.id,
                    'start_time': video_start,
                    'end_time': video_end,
                    'sequence_index': video.sequence_index,
                    'duration': video.duration,
                    'status': video.status
                }

        logger.warning(f"No video found for timestamp {timestamp} in session {session_id}")
        return None

    def get_video_start_time(
        self,
        session_id: str,
        video_id: str,
        db: Session
    ) -> Optional[float]:
        """Get start time for a specific video.

        Args:
            session_id: Test session ID
            video_id: Video ID
            db: Database session

        Returns:
            Video start time (system timestamp) or None
        """
        from models import VideoProjectLink

        video = db.query(VideoProjectLink).filter_by(
            id=video_id,
            session_id=session_id
        ).first()

        if not video:
            logger.error(f"Video {video_id} not found in session {session_id}")
            return None

        if video.video_start_time is None:
            logger.warning(f"Video {video_id} has NULL start time")
            return None

        return video.video_start_time

    def get_video_play_offset_ms(
        self,
        video_id: str,
        session_id: str,
        db: Session
    ) -> float:
        """Calculate cumulative offset for video in sequence.

        Returns milliseconds from sequence start to this video's start.

        Args:
            video_id: Video ID
            session_id: Test session ID
            db: Database session

        Returns:
            Cumulative offset in milliseconds
        """
        # FIXED: Query from SequenceVideoResult instead of VideoProjectLink
        # VideoProjectLink doesn't have session_id or sequence_index columns
        from models import SequenceVideoResult, VideoTestSequence

        # Get test session to find sequence_id
        test_session = db.query(TestSession).filter(
            TestSession.id == session_id
        ).first()

        if not test_session or not test_session.sequence_id:
            logger.error(f"Test session {session_id} has no sequence_id - cannot calculate offset")
            return 0.0

        # Get the video's sequence info from SequenceVideoResult
        video_result = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == test_session.sequence_id,
            SequenceVideoResult.video_id == video_id
        ).first()

        if not video_result:
            logger.error(f"Video {video_id} not found in sequence {test_session.sequence_id}")
            return 0.0

        if video_result.sequence_order == 0:
            return 0.0

        # Get all previous videos from SequenceVideoResult (using video_result.sequence_order)
        previous_videos = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == test_session.sequence_id,
            SequenceVideoResult.sequence_order < video_result.sequence_order
        ).order_by(SequenceVideoResult.sequence_order).all()

        cumulative_offset = 0.0
        for prev_video in previous_videos:
            if prev_video.actual_duration_ms:
                cumulative_offset += prev_video.actual_duration_ms
            else:
                logger.warning(f"Video {prev_video.video_id} missing duration - offset may be incorrect")

        return cumulative_offset

    def _initialize_sequence_start_atomic(
        self,
        db: Session,
        sequence_id: str,
        start_time: float
    ) -> bool:
        """
        Atomically initialize sequence_start_time using Compare-And-Swap pattern.

        This prevents race conditions when multiple videos start simultaneously.
        Uses SELECT FOR UPDATE to lock the row at database level.

        Args:
            db: Database session
            sequence_id: Sequence identifier
            start_time: Proposed start timestamp

        Returns:
            True if this thread won the CAS and set the time, False if another thread already set it
        """
        max_retries = 3
        retry_delay = 0.01  # 10ms

        for attempt in range(max_retries):
            try:
                # CRITICAL: Lock the row for update to prevent concurrent modifications
                stmt = select(VideoTestSequenceModel).where(
                    VideoTestSequenceModel.id == sequence_id
                ).with_for_update()

                video_sequence_db = db.execute(stmt).scalar_one_or_none()

                if not video_sequence_db:
                    logger.error(f"❌ VideoTestSequence {sequence_id} not found in database")
                    return False

                # Atomic check-and-set
                if video_sequence_db.sequence_start_time is None:
                    # We won the race - set the value
                    video_sequence_db.sequence_start_time = start_time
                    video_sequence_db.status = "running"
                    db.commit()
                    logger.info(f"✅ ATOMIC CAS SUCCESS: Set sequence_start_time={start_time:.6f} (attempt {attempt + 1})")
                    return True
                else:
                    # Another thread already set it
                    existing_time = video_sequence_db.sequence_start_time
                    db.rollback()
                    logger.info(f"⚠️ ATOMIC CAS FAILED: sequence_start_time already set to {existing_time:.6f} (attempt {attempt + 1})")
                    return False

            except SQLAlchemyError as e:
                # Handle concurrent update conflicts
                db.rollback()
                logger.warning(f"⚠️ CAS attempt {attempt + 1} failed with error: {e}")

                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"❌ CAS failed after {max_retries} attempts")
                    return False

        return False

    def _create_or_update_session(self, sequence: VideoTestSequence, db: Session):
        """Create or update test session in database"""
        try:
            # Check if session exists
            session = db.query(TestSession).filter(
                TestSession.id == sequence.session_id
            ).first()

            if session:
                # Update existing session
                session.status = "running"
                session.started_at = datetime.now(timezone.utc)
            else:
                # Create new session
                # Use first video as primary video for compatibility
                primary_video_id = sequence.video_ids[0] if sequence.video_ids else None

                session = TestSession(
                    id=sequence.session_id,
                    name=f"Video Sequence Test - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
                    project_id=sequence.project_id,
                    video_id=primary_video_id,
                    tolerance_ms=int(sequence.max_latency_ms),
                    status="running",
                    session_type="sequence_test",
                    started_at=datetime.now(timezone.utc)
                )
                db.add(session)

            db.commit()
            logger.info(f"Test session created/updated: {sequence.session_id}")

        except SQLAlchemyError as e:
            logger.error(f"Database error creating/updating session: {e}")
            db.rollback()
            raise


# Global service instance
_orchestrator_service = None


def get_video_sequence_orchestrator() -> VideoSequenceOrchestrator:
    """Get global orchestrator service instance (singleton)"""
    global _orchestrator_service

    if _orchestrator_service is None:
        _orchestrator_service = VideoSequenceOrchestrator()

    return _orchestrator_service
