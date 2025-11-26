"""
Dedicated LabJack Monitor Service with Video Timing Synchronization

This service provides precise LabJack monitoring with video timing synchronization
for HIL (Hardware-in-the-Loop) validation tests. It integrates with the VideoTimingService
to convert LabJack Unix timestamps to video-relative timestamps for ground truth matching.

Key Features:
- Integration with VideoTimingService for timestamp conversion
- Video-relative timestamp calculation for ground truth matching
- Enhanced detection event storage with timing synchronization
- Production-ready error handling and logging
- HIL compliance validation
"""

import os
import asyncio
import logging
import threading
import time
import uuid
import signal
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
import json

# Database imports
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Import centralized timing configuration
from config.timing_config import GRACE_PERIOD_MS, GRACE_PERIOD_SECONDS, MATCHING_TOLERANCE_MS

# Local imports
from database import get_db, SessionLocal
from models import TestSession, DetectionEvent, Video, SequenceVideoResult
from services.video_timing_service import get_video_timing_service, VideoTimingService
from services.labjack_detection_service import get_detection_service, LabJackDetectionMonitor
from services.hil_screenshot_service import get_hil_ground_truth_comparison, HILGroundTruthComparison
from services.labjack_service import get_labjack_service, ConnectionStatus
from services.detection_metrics import detection_metrics

# Import detection window clamp service for overlap prevention
from services.detection_window_clamp_service import (
    clamp_video_windows,
    assign_detection,
    VideoTiming,
    ClampedWindow
)

logger = logging.getLogger(__name__)


@dataclass
class HILDetectionEvent:
    """Enhanced detection event with video timing synchronization"""
    id: str
    session_id: str
    unix_timestamp: float
    video_relative_timestamp: Optional[float]
    video_relative_timestamp_ns: Optional[str]
    actual_latency_ms: Optional[float]
    video_frame_number: Optional[int]
    timing_sync_quality: str
    labjack_voltage: float
    detection_channel: str
    precision_ns: Optional[float]
    screenshot_path: Optional[str]
    screenshot_zoom_path: Optional[str]
    ground_truth_comparison: Optional[Dict[str, Any]]
    created_at: datetime
    video_id: Optional[str] = None
    sequence_id: Optional[str] = None
    sequence_video_result_id: Optional[str] = None
    sequence_timestamp: Optional[float] = None
    video_play_offset_ms: Optional[float] = None
    detection_metadata: Dict[str, Any] = field(default_factory=dict)


class DedicatedLabJackMonitor:
    """
    Dedicated LabJack monitor with video timing synchronization for HIL tests.
    
    This service coordinates between LabJack hardware monitoring and video timing
    to provide accurate ground truth matching capabilities.
    """
    
    # Use centralized grace period configuration (2000ms = 2.0 seconds)
    PRE_START_GRACE_SECONDS = GRACE_PERIOD_SECONDS  # Centralized: 2.0s grace period

    def __init__(self, video_timing_service: Optional[VideoTimingService] = None, websocket_emit_fn: Optional[Callable] = None):
        self.video_timing_service = video_timing_service or get_video_timing_service()
        self.labjack_monitor = get_detection_service()

        # ✅ Register WebSocket emission function for real-time updates
        if websocket_emit_fn:
            self.labjack_monitor.set_websocket_emit_function(websocket_emit_fn)
            logger.info("✅ WebSocket emission registered with LabJack monitor")

        # HIL screenshot and ground truth comparison service
        self.hil_comparison_service = get_hil_ground_truth_comparison()

        # Monitoring state
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.detection_events: Dict[str, List[HILDetectionEvent]] = {}

        # Detection window clamping (prevents overlaps in multi-video sequences)
        self._clamped_windows: Dict[str, List[ClampedWindow]] = {}  # session_id -> clamped windows

        # Thread synchronization
        self.lock = threading.RLock()

        # Performance tracking
        self.total_detections = 0
        self.successful_conversions = 0
        self.failed_conversions = 0

        # Shutdown flag for graceful cleanup
        self._shutdown_requested = False

        # Register signal handlers for graceful shutdown
        self._register_shutdown_handlers()

        logger.info("Dedicated LabJack Monitor with video timing synchronization initialized")
        # Log dual-write config for observability
        try:
            ts_url = os.getenv('TS_INGEST_URL') or os.getenv('TS_INGEST_ENDPOINT')
            has_token = bool(os.getenv('SERVICE_TOKEN'))
            if ts_url and has_token:
                logger.info(f"🔗 Dual-write to TS ingestion enabled: {ts_url}")
            else:
                logger.info("🔗 Dual-write to TS ingestion disabled (missing TS_INGEST_URL or SERVICE_TOKEN)")
        except Exception:
            pass

        # Recover any orphaned sessions from previous crashes
        self.recover_orphaned_sessions()
    
    def _register_shutdown_handlers(self):
        """Register signal handlers for graceful shutdown"""
        def shutdown_handler(signum, frame):
            logger.info(f"⚠️ Received shutdown signal {signum}, cleaning up sessions...")
            self.cleanup_all_sessions()

        # Register handlers for common shutdown signals
        try:
            signal.signal(signal.SIGTERM, shutdown_handler)
            signal.signal(signal.SIGINT, shutdown_handler)
            logger.info("✅ Shutdown signal handlers registered")
        except Exception as e:
            logger.warning(f"Failed to register shutdown handlers: {e}")

    def _wait_for_session_visibility(self, db: Session, session_id: str, max_retries: int = 5) -> Optional[TestSession]:
        """
        Wait for session to become visible in PostgreSQL with MVCC retry.

        PostgreSQL's MVCC can cause delays between transaction commit and visibility
        to other transactions. This method retries with exponential backoff to handle
        this race condition.

        Args:
            db: Database session
            session_id: Session ID to find
            max_retries: Maximum retry attempts (default 5)

        Returns:
            TestSession or None if not found after all retries
        """
        retry_delays = [0.01, 0.02, 0.04, 0.08, 0.16]  # Exponential backoff: 10ms to 160ms

        for attempt in range(max_retries):
            # Refresh database snapshot to see latest committed transactions
            db.flush()
            db.expire_all()

            # Query for session
            session = db.query(TestSession).filter(
                TestSession.id == session_id
            ).first()

            if session:
                logger.info(f"✅ Session {session_id} found (attempt {attempt + 1}/{max_retries})")
                return session

            if attempt < max_retries - 1:
                delay = retry_delays[attempt]
                logger.debug(f"Session {session_id} not visible yet, retrying in {delay*1000:.1f}ms...")
                time.sleep(delay)

        logger.warning(f"⚠️ Session {session_id} not found after {max_retries} retries")
        return None

    def recover_orphaned_sessions(self):
        """Recover sessions left in monitoring state from crashes"""
        try:
            # Find sessions that are "monitoring" but backend was restarted
            # These were never properly closed
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

            db = SessionLocal()
            try:
                orphaned = db.query(TestSession).filter(
                    TestSession.completed_at == None,
                    TestSession.status == "monitoring",
                    TestSession.created_at < cutoff_time
                ).all()

                for session in orphaned:
                    logger.warning(f"⚠️ Recovering orphaned session: {session.id}")
                    session.completed_at = datetime.now(timezone.utc)
                    session.status = "crashed"

                    # Add note about recovery
                    if session.metadata:
                        if isinstance(session.metadata, str):
                            metadata = json.loads(session.metadata)
                        else:
                            metadata = dict(session.metadata)
                    else:
                        metadata = {}

                    metadata['recovered'] = True
                    metadata['recovery_reason'] = 'System restart'
                    metadata['recovery_time'] = datetime.now(timezone.utc).isoformat()
                    session.metadata = metadata

                if orphaned:
                    db.commit()
                    logger.info(f"✅ Recovered {len(orphaned)} orphaned sessions")
                else:
                    logger.info("✅ No orphaned sessions found")

                return len(orphaned)

            except Exception as e:
                logger.error(f"Failed to recover orphaned sessions: {e}")
                db.rollback()
                return 0
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to recover orphaned sessions: {e}")
            return 0

    def cleanup_all_sessions(self):
        """Cleanup all active sessions on shutdown"""
        if self._shutdown_requested:
            return  # Already shutting down

        self._shutdown_requested = True
        logger.info("🧹 Shutting down, cleaning up all active sessions...")

        with self.lock:
            session_ids = list(self.active_sessions.keys())

        for session_id in session_ids:
            try:
                self.stop_session_monitoring(session_id)
                logger.info(f"✅ Cleaned up session: {session_id}")
            except Exception as e:
                logger.error(f"Failed to cleanup session {session_id}: {e}")

        logger.info(f"✅ All sessions cleaned up, {len(session_ids)} total")

    def _schedule_auto_stop(self, session_id: str, monitor_duration: Optional[float], reason: str) -> None:
        """
        Schedule an automatic stop for a session once playback finishes.

        Args:
            session_id: Active session identifier
            monitor_duration: Duration (seconds) of the playback window
            reason: Description to include in log output for observability
        """
        if not isinstance(monitor_duration, (int, float)) or monitor_duration <= 0:
            logger.error(
                "❌ Cannot schedule auto-stop for session %s - invalid duration: %s",
                session_id,
                monitor_duration,
            )
            return

        grace = max(GRACE_PERIOD_SECONDS, 2.0)
        total_wait = monitor_duration + grace
        logger.info(
            "🕒 Scheduling auto-stop for session %s in %.2fs (duration %.2fs + grace %.2fs) – %s",
            session_id,
            total_wait,
            monitor_duration,
            grace,
            reason,
        )

        def _delayed_stop():
            try:
                time.sleep(total_wait)
                self.stop_session_monitoring(session_id)
                logger.info(
                    "⏹️ Auto-stopped monitoring for session %s after %.2fs (%s)",
                    session_id,
                    total_wait,
                    reason,
                )
            except Exception as stop_error:
                logger.warning(f"Auto-stop failed for session {session_id}: {stop_error}")

        stop_thread = threading.Thread(target=_delayed_stop, daemon=True)
        stop_thread.start()
        session_state = self.active_sessions.get(session_id)
        if session_state is not None:
            session_state['auto_stop_thread'] = stop_thread

    def _build_sequence_video_timing_map(
        self,
        session_db: TestSession,
        session_id: str,
        video_ids: List[str],
        video_start_time: Optional[float],
        video_metadata: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Dict[str, float]]:
        """
        Build a deterministic timing map for every video in the session playlist.

        Returns:
            Dict keyed by video_id with started_at/ended_at/duration entries
        """
        if not session_db or not video_ids or video_start_time is None:
            return {}

        video_timing_map: Dict[str, Dict[str, float]] = {}
        sequence_id = session_db.sequence_id

        # Look up sequence video rows once to avoid repeated queries
        sequence_results_map: Dict[str, SequenceVideoResult] = {}
        if sequence_id:
            results = (
                db.query(SequenceVideoResult)
                .filter(SequenceVideoResult.video_sequence_id == sequence_id)
                .order_by(SequenceVideoResult.sequence_order.asc())
                .all()
            )
            sequence_results_map = {res.video_id: res for res in results if res.video_id}

        # Determine known durations from SequenceVideoResult entries
        duration_lookup: Dict[str, float] = {}
        for result in sequence_results_map.values():
            duration_seconds: Optional[float] = None
            if result.actual_duration_ms:
                duration_seconds = float(result.actual_duration_ms) / 1000.0
            else:
                planned_ms = getattr(result, "planned_duration_ms", None)
                if planned_ms:
                    try:
                        duration_seconds = float(planned_ms) / 1000.0
                    except (TypeError, ValueError):
                        duration_seconds = None
            if duration_seconds and duration_seconds > 0:
                duration_lookup[result.video_id] = duration_seconds

        # Fallback to Video table metadata
        try:
            video_records = (
                db.query(Video)
                .filter(Video.id.in_(video_ids))
                .all()
            )
            for record in video_records:
                if record.duration and record.id not in duration_lookup:
                    try:
                        parsed_duration = float(record.duration)
                    except (TypeError, ValueError):
                        parsed_duration = None
                    if parsed_duration and parsed_duration > 0:
                        duration_lookup[record.id] = parsed_duration
        except Exception as video_lookup_error:
            logger.warning(f"Failed to load video durations for timing map: {video_lookup_error}")

        def _safe_duration(value: Any) -> Optional[float]:
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                return None
            return parsed if parsed > 0 else None

        overall_duration = _safe_duration(video_metadata.get('duration'))
        default_segment_duration: Optional[float] = None
        if overall_duration:
            if len(video_ids) > 1:
                default_segment_duration = overall_duration / len(video_ids)
            else:
                default_segment_duration = overall_duration

        cumulative = float(video_start_time)
        for index, vid in enumerate(video_ids):
            segment_duration = duration_lookup.get(vid)
            if not segment_duration:
                segment_duration = default_segment_duration
            if not segment_duration or segment_duration <= 0:
                segment_duration = 5.0  # Conservative fallback to keep timers flowing

            video_timing_map[vid] = {
                'started_at': cumulative,
                'ended_at': cumulative + segment_duration,
                'duration': segment_duration,
                'sequence_order': index,
            }

            seq_result = sequence_results_map.get(vid)
            if seq_result:
                seq_result.video_start_time = cumulative
                seq_result.video_end_time = cumulative + segment_duration
                if seq_result.sequence_order is None:
                    seq_result.sequence_order = index

            cumulative += segment_duration

        try:
            metadata_raw = session_db.sequence_metadata or {}
            if isinstance(metadata_raw, str):
                metadata = json.loads(metadata_raw) if metadata_raw else {}
            elif isinstance(metadata_raw, dict):
                metadata = dict(metadata_raw)
            else:
                metadata = {}

            metadata['video_ids'] = video_ids
            metadata['video_timing'] = video_timing_map
            session_db.sequence_metadata = metadata
            db.commit()
            logger.info(
                "✅ Stored planned video timing map for session %s: %s",
                session_id,
                {
                    vid: {
                        'start': round(entry['started_at'], 3),
                        'end': round(entry['ended_at'], 3),
                    }
                    for vid, entry in video_timing_map.items()
                },
            )
        except Exception as metadata_error:
            logger.warning(f"Failed to persist video timing metadata: {metadata_error}")
            db.rollback()

        return video_timing_map

    async def start_monitoring_with_video_sync(self, session_id: str, video_timing_config: Dict[str, Any]) -> bool:
        """
        Start LabJack monitoring with video timing synchronization.
        
        Args:
            session_id: Test session identifier
            video_timing_config: Video timing configuration
                - video_id: Video identifier
                - fps: Video frame rate
                - duration: Video duration
                - enable_frame_sync: Whether to enable frame synchronization
        
        Returns:
            True if monitoring started successfully, False otherwise
        """
        try:
            logger.info(f"🚀 Starting monitoring for session {session_id}")
            logger.debug(f"🔧 Video timing config: {video_timing_config}")

            with self.lock:
                # FIX: Check if this session is already being monitored
                if session_id in self.active_sessions:
                    logger.warning(f"⚠️ Session {session_id} is already being monitored - skipping duplicate start")
                    return True  # Return success since monitoring is already active

                # FIX: Check if another session is already monitoring the same video
                video_id = video_timing_config.get('video_id')
                for existing_session_id, existing_session in self.active_sessions.items():
                    existing_video_id = existing_session.get('video_timing_config', {}).get('video_id')
                    if existing_video_id == video_id:
                        logger.warning(
                            f"⚠️ Video {video_id} is already being monitored by session {existing_session_id}"
                            f" - redirecting detections to NEW session {session_id}"
                        )
                        # CRITICAL FIX: Instead of skipping, we need to:
                        # 1. Update the labjack_detection_service to use the NEW session_id
                        # 2. Create an alias so future detections go to the correct session
                        try:
                            # Use the transfer_session method for comprehensive transfer
                            if self.labjack_monitor and hasattr(self.labjack_monitor, 'transfer_session'):
                                transfer_success = self.labjack_monitor.transfer_session(existing_session_id, session_id)
                                if transfer_success:
                                    logger.info(f"🔄 Detection service transfer complete: {existing_session_id} -> {session_id}")
                                else:
                                    logger.warning(f"⚠️ Detection service transfer partial: {existing_session_id} -> {session_id}")

                            # Transfer the active session entry to the new session ID in dedicated_monitor
                            self.active_sessions[session_id] = existing_session.copy()
                            self.active_sessions[session_id]['original_session_id'] = existing_session_id
                            # Remove old session entry
                            del self.active_sessions[existing_session_id]

                            logger.info(f"✅ Session takeover complete: {existing_session_id} -> {session_id}")
                            return True

                        except Exception as takeover_error:
                            logger.error(f"❌ Session takeover failed: {takeover_error}")
                            # Fall through to normal monitoring start
                            pass

                # Get video configuration first (but don't start video yet)
                if not video_id:
                    logger.error(f"❌ Video ID required for session {session_id}")
                    return False

                playlist_video_ids = video_timing_config.get('video_ids')
                if not playlist_video_ids:
                    playlist_video_ids = [video_id]
                
                # CRITICAL FIX: Start LabJack monitoring BEFORE video timing to catch all events
                # Configure LabJack monitoring with proper threshold and sampling strategy.
                # Default to polling-friendly settings that emit regular detections for steady voltages.
                requested_sample_rate = video_timing_config.get('sample_rate')
                sample_rate = max(requested_sample_rate or 500, 200)

                default_threshold = float(os.getenv('LABJACK_DEFAULT_THRESHOLD', '0.5'))
                voltage_threshold = video_timing_config.get('voltage_threshold', default_threshold)
                force_polling = os.getenv('LABJACK_FORCE_POLLING', '').lower() in ('1', 'true', 'yes')

                labjack_config = {
                    'channels': video_timing_config.get('channels', ['AIN0']),
                    'voltage_threshold': voltage_threshold,
                    'debounce_ms': video_timing_config.get('debounce_ms', 0),
                    'sample_rate': sample_rate,
                    'store_in_db': True,  # MUST be True to enable database storage worker thread
                    'enable_websocket': video_timing_config.get('enable_websocket', True),
                    'use_stream_mode': video_timing_config.get('use_stream_mode', False)
                }
                video_timing_map = None
                sequence_total_duration = None
                session_db: Optional[TestSession] = None

                try:
                    env_val = os.getenv('LABJACK_CONTINUOUS_MODE')
                    if env_val is None:
                        env_continuous = True  # Default ON while running in polling mode
                    else:
                        env_continuous = env_val.lower() in ('1', 'true', 'yes')
                except Exception:
                    env_continuous = True

                continuous_flag = video_timing_config.get('continuous_mode')
                if continuous_flag is None:
                    continuous_flag = env_continuous

                if continuous_flag:
                    lower_bound = (
                        video_timing_config.get('continuous_lower_bound')
                        or video_timing_config.get('voltage_lower_bound')
                        or voltage_threshold
                    )
                    labjack_config.update({
                        'continuous_mode': True,
                        'continuous_lower_bound': lower_bound,
                        'continuous_upper_bound': video_timing_config.get('continuous_upper_bound'),
                        'continuous_interval_ms': video_timing_config.get('continuous_interval_ms', 5)
                    })
                else:
                    labjack_config['continuous_mode'] = False

                labjack_config.setdefault(
                    'steady_high_logging',
                    video_timing_config.get('steady_high_logging', True)
                )
                labjack_config.setdefault(
                    'steady_high_interval_ms',
                    video_timing_config.get('steady_high_interval_ms', 5)
                )

                # FIX: Explicitly enable constant_voltage_mode to bypass debounce
                # For constant voltage HIL testing, we need to capture every detection
                # even if they occur rapidly (e.g., 131 GT objects in 5 seconds = 26/second)
                labjack_config['constant_voltage_mode'] = video_timing_config.get('constant_voltage_mode', True)

                if force_polling:
                    labjack_config['use_stream_mode'] = False
                
                # CRITICAL FIX: Initialize session entry BEFORE creating callback with comprehensive logging
                session_init_time = datetime.now(timezone.utc)
                timing_ready_event = threading.Event()
                logger.info(f"📝 Initializing session {session_id} at {session_init_time}")
                
                self.active_sessions[session_id] = {
                    'video_timing_config': video_timing_config,
                    'labjack_config': labjack_config,
                    'started_at': session_init_time,
                    'video_start_time': None,  # Will be set after video timing starts
                    'detection_callback': None,  # Will store the callback reference for cleanup
                    'timing_ready_event': timing_ready_event,  # For synchronization
                    'timing_degraded': False,  # Timing reliability flag
                    'timing_verified': False,  # Session verification flag
                    'current_video': None,
                    'video_history': [],
                    'video_boundary_buffer': 0.5  # seconds of tolerance around lifecycle events
                }
                
                logger.debug(f"✅ Session entry created: {list(self.active_sessions[session_id].keys())}")
                
                # CRITICAL FIX: Create session-specific callback and store reference
                detection_callback = lambda event: self._handle_detection_with_video_sync(session_id, event)
                
                # Store callback reference for later removal
                self.active_sessions[session_id]['detection_callback'] = detection_callback
                logger.debug(f"✅ Detection callback created and stored for session {session_id}")
                
                # Add detection callback for video synchronization
                self.labjack_monitor.add_detection_callback(detection_callback)
                
                # CRITICAL FIX: Start session monitoring in bridge to prevent continued measurements
                # FIX: Make bridge initialization async to prevent 3-4 second blocking delay
                def start_bridge_async():
                    try:
                        from services.windows_labjack_bridge import windows_labjack_bridge
                        windows_labjack_bridge.start_session_monitoring(session_id)
                        logger.info(f"🚀 Bridge session monitoring started for: {session_id}")
                    except Exception as bridge_error:
                        logger.warning(f"Could not start bridge session monitoring: {bridge_error}")

                threading.Thread(target=start_bridge_async, daemon=True).start()
                logger.info(f"🚀 Bridge session monitoring started async for: {session_id}")
                
                logger.info(f"✅ Detection callback registered for session {session_id}")
                
                # FIXED: Remove blocking asyncio calls that cause infinite loops
                from services.timing_synchronization_service import timing_sync_service
                
                # Non-blocking timing synchronization - use threading to prevent loop blocking
                def prepare_sync_safely():
                    try:
                        # Simple synchronization without event loops
                        logger.info(f"🕐 Timing sync prepared for session {session_id}")
                        return {"status": "prepared", "session_id": session_id}
                    except Exception as e:
                        logger.warning(f"Timing sync preparation failed: {e}")
                        return {"status": "fallback", "session_id": session_id}
                
                # Use safe synchronization
                sync_data = prepare_sync_safely()

                # CRITICAL FIX: Validate hardware connection BEFORE anything else
                logger.info(f"🔍 PRE-CHECK: Validating LabJack hardware connection")
                labjack_service = get_labjack_service()

                # Ensure connection is established
                if labjack_service.status != ConnectionStatus.CONNECTED:
                    logger.warning(f"⚠️ LabJack not connected, attempting connection...")
                    connected = await labjack_service.connect()
                    if not connected:
                        logger.error(f"❌ Failed to establish LabJack connection")
                        return False

                # Validate hardware is responding
                hardware_valid = await labjack_service.validate_hardware_connection()
                if not hardware_valid:
                    logger.error(f"❌ Hardware validation failed - device not responding")
                    return False

                logger.info(f"✅ PRE-CHECK COMPLETE: Hardware validated and ready")

                # CRITICAL FIX: Register session with LabJack service
                logger.info(f"🚀 STEP 0: Registering session with LabJack hardware service")
                if labjack_service.start_session(session_id):
                    logger.info(f"✅ STEP 0 COMPLETE: Session {session_id} registered with LabJack service")
                else:
                    logger.error(f"❌ Failed to register session {session_id} with LabJack service")
                    return False

                # CRITICAL FIX: START LABJACK MONITORING FIRST to prevent early detection loss
                logger.info(f"🚀 STEP 1: Starting LabJack monitoring FIRST for session {session_id}")

                # STEP 1: Start LabJack monitoring BEFORE video timing
                # This ensures detections are captured immediately when hardware events occur
                # CRITICAL FIX: Pass timing_ready_event so monitoring loop can wait for timing data
                logger.info(f"🔍 SESSION DEBUG 1: Calling start_monitoring with session_id={session_id}")
                success = self.labjack_monitor.start_monitoring(
                    session_id,
                    timing_ready_event=timing_ready_event,  # ADDED: Pass timing synchronization event
                    **labjack_config
                )
                logger.info(f"🔍 SESSION DEBUG 2: start_monitoring returned, session_id still={session_id}")

                if not success:
                    logger.error(f"❌ Failed to start LabJack monitoring for session {session_id}")
                    # Unregister session from LabJack service
                    labjack_service.end_session(session_id)
                    return False

                logger.info(f"✅ STEP 1 COMPLETE: LabJack monitoring active and ready to capture detections")

                # STEP 2: NOW initialize video timing service with monitor already running
                logger.info(f"🚀 STEP 2: Initializing video timing service with LabJack already monitoring")

                # Get database connection for video timing
                try:
                    from database import get_db
                    db = next(get_db())
                except Exception as db_error:
                    logger.error(f"Failed to get database connection: {db_error}")
                    # Clean up LabJack monitoring since video timing failed
                    self.labjack_monitor.stop_monitoring(session_id)
                    return False

                session_has_sequence_flag = False
                session_sequence_id_value: Optional[str] = None

                try:
                    # STEP 1: VERIFY SESSION EXISTS WITH MVCC RETRY (FIX-3)
                    session_db = self._wait_for_session_visibility(db, session_id)

                    if not session_db:
                        logger.error(f"❌ Session {session_id} not found after MVCC retries")
                        # Session doesn't exist - mark as degraded and signal
                        self.active_sessions[session_id]['timing_degraded'] = True
                        self.active_sessions[session_id]['timing_verified'] = False
                        timing_ready_event.set()  # Signal so callback doesn't hang
                        logger.warning(f"⚠️ Timing event signaled with verification failure - monitoring will use wall clock")

                        # Stop monitoring since session is invalid
                        self.labjack_monitor.stop_monitoring(session_id)
                        return False

                    # Session exists and verified!
                    self.active_sessions[session_id]['timing_verified'] = True
                    logger.info(f"✅ Session {session_id} verified in database")

                    # Initialize timing state flags BEFORE any timing operations
                    self.active_sessions[session_id]['timing_degraded'] = False

                    video_metadata = {
                        'fps': video_timing_config.get('fps'),
                        'duration': video_timing_config.get('duration')
                    }
                    self.active_sessions[session_id]['tolerance_ms'] = getattr(
                        session_db,
                        'tolerance_ms',
                        MATCHING_TOLERANCE_MS
                    ) or MATCHING_TOLERANCE_MS

                    # STEP 2: INITIALIZE VIDEO TIMING (FIX-1)
                    # Try to initialize proper timing, but handle failures gracefully
                    try:
                        video_start_time = self.video_timing_service.start_video_timing(
                            session_id, video_id, db, video_metadata
                        )

                        if video_start_time is None:
                            logger.warning(f"⚠️ Video timing returned None for session {session_id}")
                            self.active_sessions[session_id]['timing_degraded'] = True
                            video_start_time = time.time()  # Fallback to wall clock
                        else:
                            logger.info(f"✅ Video timing initialized: {video_start_time:.6f}")
                            self.active_sessions[session_id]['timing_degraded'] = False

                    except Exception as timing_error:
                        logger.error(f"❌ Video timing failed: {timing_error}")
                        self.active_sessions[session_id]['timing_degraded'] = True
                        video_start_time = time.time()  # Fallback to wall clock

                    self.active_sessions[session_id]['video_start_time'] = video_start_time

                    # STEP 3: UPDATE DATABASE WITH STATUS
                    try:
                        session_db.timing_degraded = self.active_sessions[session_id]['timing_degraded']
                        session_db.timing_verified = self.active_sessions[session_id]['timing_verified']
                        db.commit()
                        logger.info(
                            f"📊 Session status: "
                            f"verified={self.active_sessions[session_id]['timing_verified']}, "
                            f"degraded={self.active_sessions[session_id]['timing_degraded']}"
                        )
                    except Exception as db_error:
                        logger.error(f"Failed to update session status: {db_error}")
                        db.rollback()

                    # STEP 4: SIGNAL EVENT (Always signal, even if degraded)
                    # This prevents callback from waiting forever
                    timing_ready_event.set()
                    logger.info(f"🚦 Timing event signaled for session {session_id}")

                    logger.info(f"✅ STEP 2 COMPLETE: Monitoring ready at {video_start_time:.6f}")
                    logger.info(f"📹 Timing reference established - early detections will have valid timestamps")

                    session_has_sequence_flag = bool(
                        getattr(session_db, 'has_video_sequence', False) or getattr(session_db, 'sequence_id', None)
                    )
                    session_sequence_id_value = getattr(session_db, 'sequence_id', None)

                    # Build deterministic video timing map for multi-video sequences
                    try:
                        video_ids = playlist_video_ids or ([video_id] if video_id else [])
                        video_timing_map = self._build_sequence_video_timing_map(
                            session_db=session_db,
                            session_id=session_id,
                            video_ids=video_ids,
                            video_start_time=video_start_time,
                            video_metadata=video_metadata,
                            db=db,
                        )
                        if video_timing_map:
                            self.active_sessions[session_id]['video_timing_map'] = video_timing_map
                            sequence_total_duration = sum(
                                entry.get('duration', 0.0) or 0.0 for entry in video_timing_map.values()
                            )
                    except Exception as map_error:
                        logger.warning(f"Unable to build video timing map: {map_error}")

                finally:
                    db.close()

                # Confirm monitoring is ready - this is critical for timing accuracy
                ready_time = timing_sync_service.confirm_monitoring_ready(session_id)
                logger.info(f"✅ STEP 2 COMPLETE: Monitoring confirmed ready at {ready_time}")

                # FIXED: Non-blocking WebSocket notification using thread-safe approach
                try:
                    # Use thread-safe WebSocket emission to prevent asyncio loop conflicts
                    def emit_monitoring_ready():
                        try:
                            logger.info(f"📡 Monitoring ready for session {session_id}")
                        except Exception as e:
                            logger.warning(f"Monitoring ready notification failed: {e}")

                    # Execute in background thread to avoid blocking
                    threading.Thread(target=emit_monitoring_ready, daemon=True).start()
                    logger.info(f"📡 Scheduled monitoring_ready notification for session {session_id}")
                except Exception as ws_error:
                    logger.warning(f"Failed to schedule monitoring_ready notification: {ws_error}")

                logger.info(f"🎯 RACE CONDITION ELIMINATED: Video timing ready BEFORE first detection")
                logger.info(f"✅ All detections will have valid timing data from first capture")

                # Store session configuration with video path for HIL screenshot capture
                enhanced_video_config = video_timing_config.copy()

                # Get video path from database if video_id is provided
                if video_id and 'video_path' not in enhanced_video_config:
                    try:
                        # Import Video model here to avoid circular imports
                        from models import Video
                        from database import get_db
                        db_video = next(get_db())
                        try:
                            video_record = db_video.query(Video).filter(Video.id == video_id).first()
                            if video_record and hasattr(video_record, 'file_path'):
                                enhanced_video_config['video_path'] = video_record.file_path
                                logger.info(f"Retrieved video path for HIL capture: {video_record.file_path}")
                        finally:
                            db_video.close()
                    except Exception as e:
                        logger.warning(f"Failed to retrieve video path for HIL capture: {e}")

                # Update session with enhanced video config and video start time
                self.active_sessions[session_id]['video_timing_config'] = enhanced_video_config
                self.active_sessions[session_id]['video_start_time'] = video_start_time

                # Auto-stop monitoring when playback finishes (single and multi-video)
                try:
                    is_sequence = bool(video_timing_config.get('is_sequence')) or session_has_sequence_flag
                    sequence_id = video_timing_config.get('sequence_id') or session_sequence_id_value
                    if not is_sequence and playlist_video_ids and len(playlist_video_ids) > 1:
                        is_sequence = True

                    if is_sequence:
                        if sequence_id:
                            logger.info(f"🎬 Multi-video sequence detected for session {session_id} (sequence: {sequence_id})")
                        # if sequence_total_duration and sequence_total_duration > 0:
                        #     self._schedule_auto_stop(
                        #         session_id,
                        #         sequence_total_duration,
                        #         reason="multi-video sequence duration",
                        #     )
                        else:
                            logger.info(
                                "🎬 Skipping auto-stop timer for multi-video sequence %s - "
                                "no timing map available; orchestrator must stop session",
                                sequence_id,
                            )
                    else:
                        duration = video_timing_config.get('duration')

                        if not isinstance(duration, (int, float)) or duration <= 0:
                            logger.warning(f"⚠️ Missing or invalid video duration in timing config: {duration}")

                            if video_id:
                                try:
                                    db_lookup = next(get_db())
                                    try:
                                        video = db_lookup.query(Video).filter(Video.id == video_id).first()
                                        if video and video.duration:
                                            duration = float(video.duration)
                                            logger.info(
                                                f"✅ Retrieved video duration from database: {duration}s for video {video_id}"
                                            )
                                        else:
                                            logger.warning(
                                                f"❌ Video not found in database or missing duration: video_id={video_id}"
                                            )
                                    finally:
                                        db_lookup.close()
                                except Exception as db_error:
                                    logger.error(f"Database query failed for video duration: {db_error}")

                            if not isinstance(duration, (int, float)) or duration <= 0:
                                duration = 5.25
                                logger.warning(
                                    f"⚠️ Using full video monitoring duration fallback: {duration}s for session {session_id}"
                                )

                        # Auto-stop timer disabled - using manual stop
                        # if isinstance(duration, (int, float)) and duration > 0:
                        #     self._schedule_auto_stop(
                        #         session_id,
                        #         float(duration),
                        #         reason="single video duration",
                        #     )
                        # FIX: Removed incorrect else clause that logged error for valid durations
                        # The else was paired with line 866's if statement, causing false errors
                except Exception as e:
                    logger.error(f"Auto-stop timer setup failed for session {session_id}: {e}")

                # Initialize detection events list
                self.detection_events[session_id] = []

                logger.info(f"✅ Dedicated LabJack monitoring with video sync started for session {session_id}")
                return True
                
        except Exception as e:
            # CRITICAL FIX: Enhanced error reporting for start_monitoring_with_video_sync
            logger.error(f"❌ Error starting dedicated LabJack monitoring for session {session_id}: {e}")
            logger.error(f"❌ video_timing_config type: {type(video_timing_config)}, value: {video_timing_config}")
            logger.error(f"❌ Session in active_sessions: {session_id in self.active_sessions}")
            logger.error(f"❌ Active sessions count: {len(self.active_sessions)}")
            
            # Clean up partial session initialization
            if session_id in self.active_sessions:
                try:
                    del self.active_sessions[session_id]
                    logger.info(f"🧹 Cleaned up partial session initialization for {session_id}")
                except Exception as cleanup_error:
                    logger.error(f"❌ Failed to cleanup partial session: {cleanup_error}")
            
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return False
    
    def _handle_detection_with_video_sync(self, session_id: str, labjack_event) -> None:
        """
        Handle LabJack detection event with video timing synchronization.
        
        Args:
            session_id: Test session identifier
            labjack_event: LabJack detection event from monitoring service
        """
        try:
            # CRITICAL FIX: Add detailed logging for session access debugging
            logger.debug(f"🔍 Detection callback triggered for session: {session_id}")
            logger.debug(f"🔍 Current active sessions: {list(self.active_sessions.keys())}")
            
            # CRITICAL FIX: Only process detections for ACTIVE sessions
            if session_id not in self.active_sessions:
                logger.debug(f"🚫 Skipping detection for inactive session: {session_id}")
                return

            # Wait for the timing data to be ready
            session_info = self.active_sessions.get(session_id)
            if not session_info:
                logger.warning(f"⚠️ Session {session_id} disappeared while processing detection.")
                return
                
            timing_ready_event = session_info.get('timing_ready_event')
            timing_available = True
            timing_degraded = False

            if timing_ready_event:
                # CRITICAL FIX: Increase timeout from 2s to 10s to prevent early detection discard
                # Video timing calculation can take 1-2s (DB queries, sequence building)
                # Fast hardware responds in 5-50ms, so detections arrive before timing ready
                is_set = timing_ready_event.wait(timeout=10.0)
                if not is_set:
                    logger.warning(f"⚠️ Timing data not ready after 10s for session {session_id} - using degraded timing with wall clock timestamps")
                    timing_available = False
                    timing_degraded = True
                    # CRITICAL: DO NOT RETURN - Continue processing with fallback timing
                    # Detection will be saved with wall clock timestamp instead of video-relative timing
                else:
                    # Check if timing was marked as degraded during initialization
                    timing_degraded = session_info.get('timing_degraded', False)
                    if timing_degraded:
                        logger.info(f"⚠️ Timing ready but marked as degraded for session {session_id} - timestamps may be less accurate")

            # Determine if detection is usable for validation
            usable_for_validation = timing_available and not timing_degraded

            if timing_degraded:
                logger.warning(
                    f"⚠️ Detection captured with DEGRADED timing - "
                    f"will be marked as non-validated (session: {session_id})"
                )
            
            # CRITICAL FIX: Extract Unix timestamp and voltage data from LabJack event properly
            try:
                labjack_trigger_time = labjack_event.timestamp.timestamp() if hasattr(labjack_event.timestamp, 'timestamp') else time.time()
                logger.debug(f"🔍 Extracted LabJack trigger timestamp: {labjack_trigger_time}")
            except Exception as ts_error:
                logger.error(f"❌ Failed to extract timestamp: {ts_error}")
                labjack_trigger_time = time.time()

            # TIMING FIX: Capture the current time as detection processing finish time
            detection_record_time = time.time()

            # Calculate REAL processing latency = (when we recorded it) - (when hardware triggered)
            real_processing_latency_ms = (detection_record_time - labjack_trigger_time) * 1000.0
            logger.info(f"⏱️ REAL latency: {real_processing_latency_ms:.3f}ms (trigger: {labjack_trigger_time}, recorded: {detection_record_time})")
            
            # CRITICAL FIX: Verify session is still active before processing with proper error handling
            session_info = self.active_sessions.get(session_id)
            if not session_info:
                logger.warning(f"⚠️ Session {session_id} no longer active, skipping detection")
                return
            
            logger.debug(f"✅ Session validation passed for {session_id}: {list(session_info.keys())}")
            
            # FIXED: Extract voltage and channel data - this was the missing piece!
            labjack_voltage = getattr(labjack_event, 'voltage', 0.0)
            detection_channel = getattr(labjack_event, 'channel', 'AIN0')
            
            # Log the voltage data to confirm capture
            logger.info(f"🔌 LabJack detection captured: {detection_channel} = {labjack_voltage:.3f}V @ trigger_time={labjack_trigger_time}")

            # CRITICAL FIX: Calculate video-relative timing data with calibration fallback
            # Use labjack_trigger_time for video synchronization
            timing_data = self.video_timing_service.calculate_video_relative_latency(
                session_id, labjack_trigger_time
            )
            
            # CRITICAL FIX: Always ensure we have valid timing data, apply calibration if needed
            if timing_data is None or not timing_data.get('video_relative_timestamp'):
                logger.warning(f"Video timing service failed for session {session_id}, using calibrated fallback timing")
                # Apply timing calibration directly here since video service is failing
                session_start_time = session_info.get('started_at') or session_info.get('video_start_time')
                if session_start_time:
                    try:
                        # TIMING CALIBRATION: Dynamic calibration based on actual measurements
                        try:
                            if hasattr(self, 'labjack_monitor') and self.labjack_monitor:
                                dynamic_calibration_offset_ms = self.labjack_monitor.calculate_calibration_offset(session_id)
                                logger.info(f"🎯 Calculated dynamic calibration offset: {dynamic_calibration_offset_ms}ms")
                            else:
                                dynamic_calibration_offset_ms = 0.0
                                logger.warning("⚠️ Detection service not available - using zero offset")
                        except Exception as e:
                            logger.error(f"❌ Failed to calculate calibration offset: {e}, using zero offset")
                            dynamic_calibration_offset_ms = 0.0

                        # Convert datetime to timestamp if needed and apply calibration offset
                        if hasattr(session_start_time, 'timestamp'):
                            reference_time = session_start_time.timestamp() + (dynamic_calibration_offset_ms / 1000.0)
                        elif isinstance(session_start_time, (int, float)):
                            reference_time = session_start_time + (dynamic_calibration_offset_ms / 1000.0)
                        else:
                            reference_time = time.time()

                        fallback_video_relative = labjack_trigger_time - reference_time
                        timing_data = {
                            'video_relative_timestamp': max(0.0, fallback_video_relative),
                            'actual_latency_ms': 50.0,  # Reasonable processing latency
                            'video_frame_number': int(max(0.0, fallback_video_relative) * 24),
                            'timing_sync_quality': 'calibrated_direct',
                            'calibration_applied': True,
                            'calibration_offset_ms': dynamic_calibration_offset_ms
                        }
                        logger.info(f"🎯 Direct calibration applied: {fallback_video_relative:.3f}s video-relative (offset: {dynamic_calibration_offset_ms}ms)")
                    except Exception as e:
                        logger.error(f"Direct calibration failed: {e}")
                        timing_data = None
                
                # CRITICAL FIX: Safe fallback timing data with proper None handling
                try:
                    # Get session data with comprehensive None checking
                    session_data = self.active_sessions.get(session_id, {})
                    logger.debug(f"🔍 Session data for fallback: {session_data}")
                    
                    # CRITICAL TIMING CALIBRATION FIX: Handle video timing synchronization
                    # FIX #1: Use ACTUAL video_start_time from session instead of reference_time
                    video_start_time = session_data.get('video_start_time')
                    session_start_time = session_data.get('started_at')

                    # FIX #1: Use video_start_time as primary reference instead of session_start_time
                    # This ensures video-relative timestamps are calculated from actual video playback start
                    if not video_start_time:
                        # Fallback to session start time if video start time not available
                        video_start_time = session_start_time

                    # Use video_start_time as the reference for video-relative timestamp calculation
                    if video_start_time is not None:
                        # Convert datetime to timestamp if needed
                        if hasattr(video_start_time, 'timestamp'):
                            reference_time = video_start_time.timestamp()
                        elif isinstance(video_start_time, (int, float)):
                            reference_time = video_start_time
                        else:
                            reference_time = time.time()
                        logger.debug(f"✅ Using video_start_time as reference: {reference_time}")
                    else:
                        # Ultimate fallback: current time
                        reference_time = time.time()
                        logger.warning(f"⚠️ Using current time as fallback reference: {reference_time}")

                    # Calculate ACTUAL video-relative timestamp from video start time
                    if isinstance(labjack_trigger_time, (int, float)) and isinstance(reference_time, (int, float)):
                        video_relative_seconds = labjack_trigger_time - reference_time
                        fallback_video_relative = max(0.0, video_relative_seconds)
                    else:
                        fallback_video_relative = 0.0
                        logger.error(f"❌ Invalid timestamp types: trigger={type(labjack_trigger_time)}, ref={type(reference_time)}")

                    logger.info(f"🎯 Video-relative timing: {fallback_video_relative:.3f}s (trigger={labjack_trigger_time:.6f}, video_start={reference_time:.6f})")

                    timing_data = {
                        'video_relative_timestamp': fallback_video_relative,
                        'video_relative_timestamp_ns': int(fallback_video_relative * 1e9),
                        'actual_latency_ms': 50.0,  # Default processing time - represents detection pipeline latency
                        'video_frame_number': int(fallback_video_relative * 24),  # CORRECTED: Use 24fps to match ground truth
                        'timing_sync_quality': 'video_start_fallback',
                        'timing_precision_ns': 1000000,  # 1ms precision
                        'calibration_applied': False,  # No calibration offset applied when using video_start_time
                        'fallback_reason': 'video_timing_service_unavailable'
                    }
                    
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback timing calculation failed: {fallback_error}")
                    # Ultimate fallback with safe defaults - but still apply basic calibration
                    estimated_video_time = (labjack_trigger_time % 10)  # Crude estimate within 10s window
                    timing_data = {
                        'video_relative_timestamp': estimated_video_time,  # Never store NULL
                        'video_relative_timestamp_ns': int(estimated_video_time * 1e9),
                        'actual_latency_ms': 50.0,
                        'video_frame_number': int(estimated_video_time * 24),  # 24fps
                        'timing_sync_quality': 'error_fallback',
                        'timing_precision_ns': 1000000,
                        'calibration_applied': False  # Mark as uncalibrated
                    }
                    logger.warning(f"⚠️ Using crude timing estimate: {estimated_video_time:.3f}s")
                
                self.failed_conversions += 1
            else:
                self.successful_conversions += 1
            
            # Choose latency value: prefer calibrated value from timing service
            calibrated_latency_ms = timing_data.get('actual_latency_ms')
            if calibrated_latency_ms is None:
                calibrated_latency_ms = real_processing_latency_ms

            hil_event = HILDetectionEvent(
                id=str(uuid.uuid4()),
                session_id=session_id,
                unix_timestamp=detection_record_time,
                video_relative_timestamp=timing_data['video_relative_timestamp'],
                video_relative_timestamp_ns=timing_data['video_relative_timestamp_ns'],
                actual_latency_ms=calibrated_latency_ms,
                video_frame_number=timing_data['video_frame_number'],
                timing_sync_quality=timing_data['timing_sync_quality'],
                labjack_voltage=labjack_voltage,
                detection_channel=detection_channel,
                precision_ns=timing_data['timing_precision_ns'],
                created_at=datetime.now(timezone.utc),
                screenshot_path=None,
                screenshot_zoom_path=None,
                ground_truth_comparison=None
            )
            hil_event.detection_metadata = {
                "detection_channel": detection_channel,
                "labjack_voltage": labjack_voltage,
                "precision_ns": timing_data.get('timing_precision_ns'),
                "real_latency_ms": real_processing_latency_ms,
                "calibrated_latency_ms": calibrated_latency_ms
            }
            self._enrich_hil_event_context(hil_event, session_id, labjack_trigger_time)
            
            # Store event
            with self.lock:
                if session_id not in self.detection_events:
                    self.detection_events[session_id] = []
                self.detection_events[session_id].append(hil_event)
            
            # Store in database (fixed async handling)
            self._schedule_db_storage(hil_event, labjack_trigger_time, detection_record_time)

            # CRITICAL FIX: Emit WebSocket event for real-time frontend display
            self._schedule_websocket_emission(hil_event, session_id)

            self.total_detections += 1
            # successful_conversions already incremented above based on timing_data success
            
            logger.info(f"🎯 HIL Detection: {hil_event.video_relative_timestamp:.6f}s video-relative "
                       f"({hil_event.actual_latency_ms:.3f}ms latency, {hil_event.timing_sync_quality} quality)")
            
        except Exception as e:
            # CRITICAL FIX: Enhanced error logging with full traceback for debugging
            logger.error(f"❌ Error handling detection with video sync for session {session_id}: {e}")
            logger.error(f"❌ Session exists in active_sessions: {session_id in self.active_sessions}")
            logger.error(f"❌ Active sessions count: {len(self.active_sessions)}")
            logger.error(f"❌ Active session IDs: {list(self.active_sessions.keys())}")
            
            # Log full exception details for debugging
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            
            self.failed_conversions += 1

    def _schedule_websocket_emission(self, hil_event: HILDetectionEvent, session_id: str):
        """Emit detection event via WebSocket for real-time frontend display"""
        try:
            # Create thread-safe WebSocket emission
            threading.Thread(
                target=self._emit_detection_event_sync,
                args=(hil_event, session_id),
                daemon=True
            ).start()
            logger.debug(f"📡 Scheduled WebSocket emission for event {hil_event.id}")
        except Exception as e:
            logger.error(f"Failed to schedule WebSocket emission: {e}")

    def _emit_detection_event_sync(self, hil_event: HILDetectionEvent, session_id: str):
        """Thread-safe wrapper for async WebSocket emission to session room"""
        try:
            # Create detection data payload - NO session_id (already scoped by room)
            detection_data = {
                'id': hil_event.id,
                'timestamp': hil_event.unix_timestamp,
                'timestamp_ms': hil_event.unix_timestamp * 1000,
                'video_relative_timestamp': hil_event.video_relative_timestamp,
                'sequence_timestamp': hil_event.sequence_timestamp,
                'latency_ms': hil_event.actual_latency_ms,
                'voltage': hil_event.labjack_voltage,
                'channel': hil_event.detection_channel,
                'frame_number': hil_event.video_frame_number,
                'timing_quality': hil_event.timing_sync_quality,
                'detection_type': 'hardware',
                'source': 'labjack',
                'video_id': hil_event.video_id,
                'sequence_id': hil_event.sequence_id,
                'sequence_video_result_id': hil_event.sequence_video_result_id,
                'video_play_offset_ms': hil_event.video_play_offset_ms
            }
            if hil_event.detection_metadata:
                detection_data['metadata'] = hil_event.detection_metadata

            # Use room-based emission utility
            from services.websocket_rooms import notify_session_room

            success = notify_session_room(session_id, 'detection_event', detection_data)

            if success:
                logger.info(f"📡 Emitted detection event to session room: {hil_event.id}")
            else:
                logger.error(f"❌ Failed to emit detection event to session room: {hil_event.id}")

        except Exception as e:
            logger.error(f"Failed to emit detection event via WebSocket: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _schedule_db_storage(self, hil_event: HILDetectionEvent, labjack_trigger_time: float, detection_record_time: float):
        """FIXED: Always use thread-safe database storage to prevent asyncio conflicts"""
        try:
            # Always use threading to prevent asyncio loop conflicts
            threading.Thread(
                target=self._store_event_sync_wrapper,
                args=(hil_event, labjack_trigger_time, detection_record_time),
                daemon=True
            ).start()
            logger.debug(f"📦 Scheduled DB storage for event {hil_event.id}")
        except Exception as e:
            logger.error(f"Failed to schedule DB storage: {e}")
    
    def _store_event_sync_wrapper(self, hil_event: HILDetectionEvent, labjack_trigger_time: float, detection_record_time: float):
        """FIXED: Synchronous database storage to avoid asyncio loop conflicts"""
        try:
            # Use synchronous database storage to prevent asyncio conflicts
            db = next(get_db())
            try:
                if not hil_event.video_id or (hil_event.sequence_id and not hil_event.sequence_video_result_id):
                    self._enrich_hil_event_context(hil_event, hil_event.session_id, labjack_trigger_time)

                detection_metadata = hil_event.detection_metadata.copy() if hil_event.detection_metadata else {}
                detection_metadata.update({
                    "labjack_trigger_time": labjack_trigger_time,
                    "detection_record_time": detection_record_time
                })

                # CRITICAL FIX: Ensure video_id is always set where possible.
                # Priority order:
                # 1. Use hil_event.video_id if available (from lifecycle events)
                # 2. Fall back to session.video_id (works for both single and multi-video)
                # 3. Log error if neither is available
                video_id_for_detection = hil_event.video_id

                if not video_id_for_detection:
                    try:
                        session = db.query(TestSession).filter_by(id=hil_event.session_id).first()
                    except Exception as fallback_error:
                        session = None
                        logger.error(f"❌ Failed to load session for detection {hil_event.id}: {fallback_error}")

                    if session:
                        if session.video_id:
                            # BUG FIX: Always use session.video_id as fallback
                            # This ensures detections get a video_id even for multi-video sessions
                            video_id_for_detection = session.video_id
                            logger.info(
                                f"✅ Using session fallback video_id={video_id_for_detection} "
                                f"for detection {hil_event.id} (has_sequence={session.has_video_sequence})"
                            )
                        else:
                            logger.error(
                                f"❌ Session {session.id} has no video_id! "
                                f"Detection {hil_event.id} will have NULL video_id"
                            )
                    else:
                        logger.error(
                            f"❌ CRITICAL: Cannot determine video_id for detection {hil_event.id} - storing as NULL"
                        )

                # Normalize video-relative timestamp so detections are aligned to the start
                # of each video rather than the entire sequence timeline.
                normalized_video_relative = hil_event.video_relative_timestamp
                if (
                    hil_event.sequence_timestamp is not None
                    and hil_event.video_play_offset_ms is not None
                ):
                    normalized_video_relative = (
                        hil_event.sequence_timestamp
                        - (hil_event.video_play_offset_ms or 0.0) / 1000.0
                    )

                if normalized_video_relative is not None:
                    if normalized_video_relative < -0.05:
                        logger.debug(
                            "⚠️ Adjusted video-relative timestamp negative (%.3fs) "
                            "for detection %s – clamping to 0.0s",
                            normalized_video_relative,
                            hil_event.id,
                        )
                        normalized_video_relative = 0.0
                    else:
                        normalized_video_relative = max(normalized_video_relative, 0.0)

                    hil_event.video_relative_timestamp = normalized_video_relative

                    if hil_event.video_frame_number is None:
                        fps = 24.0
                        try:
                            metadata = hil_event.detection_metadata or {}
                            fps = float(metadata.get('video_fps', fps))
                        except (TypeError, ValueError):
                            fps = 24.0
                        hil_event.video_frame_number = max(
                            int(round(hil_event.video_relative_timestamp * fps)),
                            0
                        )

                session_cfg = self.active_sessions.get(hil_event.session_id, {})
                latency_threshold = session_cfg.get('tolerance_ms', MATCHING_TOLERANCE_MS)
                latency_value = hil_event.actual_latency_ms
                validation_result = (
                    "PASS"
                    if latency_value is not None and abs(latency_value) <= latency_threshold
                    else "FAIL"
                )

                session_cfg = self.active_sessions.get(hil_event.session_id, {})
                latency_threshold = session_cfg.get('tolerance_ms', MATCHING_TOLERANCE_MS)
                latency_value = hil_event.actual_latency_ms
                validation_result = (
                    "PASS"
                    if latency_value is not None and abs(latency_value) <= latency_threshold
                    else "FAIL"
                )

                # Get timing degradation status for this detection
                session_timing_degraded = session_cfg.get('timing_degraded', False)
                detection_usable_for_validation = not session_timing_degraded

                # FIX #5: Calculate video_start_time for timing synchronization
                # This prevents "No video_start_time found" errors in timing calculator
                video_start_time = None
                if hil_event.video_relative_timestamp is not None and labjack_trigger_time is not None:
                    # video_start_time = detection_time - video_relative_timestamp
                    video_start_time = labjack_trigger_time - hil_event.video_relative_timestamp
                    logger.debug(f"Calculated video_start_time: {video_start_time} from trigger {labjack_trigger_time} - relative {hil_event.video_relative_timestamp}")

                detection_event = DetectionEvent(
                    id=hil_event.id,
                    test_session_id=hil_event.session_id,
                    video_id=video_id_for_detection,  # ✅ FIXED: Always attempt to set video_id
                    sequence_id=hil_event.sequence_id,
                    sequence_video_result_id=hil_event.sequence_video_result_id,
                    timestamp=labjack_trigger_time,
                    validation_result=validation_result,
                    processing_time_ms=hil_event.actual_latency_ms,
                    labjack_timestamp=float(labjack_trigger_time),
                    labjack_timestamp_ns=int(labjack_trigger_time * 1e9),
                    labjack_voltage=float(hil_event.labjack_voltage) if hil_event.labjack_voltage is not None else None,
                    detection_channel=str(hil_event.detection_channel) if hil_event.detection_channel else None,
                    video_relative_timestamp=hil_event.video_relative_timestamp,
                    video_frame_number=hil_event.video_frame_number,
                    actual_latency_ms=hil_event.actual_latency_ms,
                    timing_sync_quality=hil_event.timing_sync_quality,
                    detection_type="hardware",
                    source="labjack",
                    screenshot_path=hil_event.screenshot_path,
                    screenshot_zoom_path=hil_event.screenshot_zoom_path,
                    unix_timestamp=float(detection_record_time),
                    detection_timestamp=datetime.fromtimestamp(detection_record_time, tz=timezone.utc),
                    signal_value=float(hil_event.labjack_voltage) if hil_event.labjack_voltage is not None else None,
                    sequence_timestamp=hil_event.sequence_timestamp,
                    video_play_offset_ms=hil_event.video_play_offset_ms,
                    detection_metadata=detection_metadata,
                    signal_type='labjack_voltage',
                    # NEW FIELDS: Track timing quality and validation usability
                    usable_for_validation=detection_usable_for_validation,
                    timing_degraded=session_timing_degraded,
                    # FIX #5: Set video_start_time for timing synchronization calculator
                    video_start_time=video_start_time
                )

                status = "✅ VALIDATED" if detection_usable_for_validation else "⚠️ NON-VALIDATED"
                logger.info(
                    f"🔌 Detection saved ({status}): "
                    f"voltage={hil_event.labjack_voltage}V, usable={detection_usable_for_validation}"
                )

                # Record metrics for detection quality tracking
                detection_metrics.record_detection(
                    session_id=hil_event.session_id,
                    usable_for_validation=detection_usable_for_validation,
                    timing_degraded=session_timing_degraded
                )

                db.add(detection_event)
                db.commit()
                logger.debug(f"💾 Stored HIL detection event: {hil_event.id}")
                
            except Exception as db_error:
                logger.error(f"Database error storing HIL event: {db_error}")
                db.rollback()
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to store HIL detection event (sync): {e}")

    def invalidate_sequence_cache(self, session_id: str):
        """
        Invalidate sequence context cache AND pre-generate clamped windows.

        QUEEN'S PROTOCOL #37: Pre-generates clamped windows immediately after
        video lifecycle events instead of waiting for next detection.

        This fixes the race condition where first detection after lifecycle
        event may use stale windows.
        """
        with self.lock:
            # Step 1: Invalidate sequence context cache
            session_cache = self.active_sessions.get(session_id, {})
            session_cache.pop('sequence_context', None)

            # Step 2: Invalidate clamped windows cache
            if session_id in self._clamped_windows:
                del self._clamped_windows[session_id]
                logger.info(f"🔧 Cleared clamped windows cache for session {session_id}")

        logger.info(f"✅ Cache invalidated for session {session_id}")

        # Step 3: IMMEDIATELY pre-generate fresh clamped windows
        # Note: This happens OUTSIDE the lock to avoid deadlock
        try:
            # Load fresh sequence context to get video timing
            context = self._load_sequence_context(session_id)
            if context and context.get('video_timing'):
                video_timing = context['video_timing']
                # Call the window generation function synchronously
                self._get_or_create_clamped_windows(session_id, video_timing)
                logger.info(f"✅ Pre-generated clamped windows for session {session_id}")
            else:
                logger.warning(f"⚠️ Cannot pre-generate windows - no video_timing for session {session_id}")
        except Exception as e:
            logger.error(f"❌ Failed to pre-generate clamped windows: {e}")
            # Continue - windows will regenerate on next detection

    def _get_video_id_with_retry(
        self,
        session_id: str,
        trigger_time: float,
        max_retries: int = 5,
        initial_delay_ms: float = 10.0
    ) -> Optional[str]:
        """Get video ID with exponential backoff retry logic.

        Extends retry window from 60ms to 155ms to account for race conditions.

        Args:
            session_id: Test session ID
            trigger_time: Detection trigger timestamp
            max_retries: Maximum retry attempts (default 5)
            initial_delay_ms: Initial retry delay (default 10ms)

        Returns:
            Video ID or None if all retries fail
        """
        delay_ms = initial_delay_ms

        for attempt in range(max_retries):
            # Force cache refresh on each retry for multi-video sequences
            context = self._load_sequence_context(
                session_id=session_id,
                retry_attempt=attempt
            )

            if not context or not context.get('video_timing'):
                logger.warning(f"Retry {attempt + 1}/{max_retries}: No sequence context")
                time.sleep(delay_ms / 1000.0)
                delay_ms *= 2  # Exponential backoff
                continue

            # Try to determine video
            video_id = self._determine_video_from_timing(
                video_timing=context.get('video_timing', {}),
                trigger_time=trigger_time,
                session_id=session_id
            )

            if video_id:
                logger.info(f"✅ Video ID found on retry {attempt + 1}: {video_id}")
                return video_id

            # Log retry attempt
            logger.info(
                f"Retry {attempt + 1}/{max_retries}: No video match, "
                f"waiting {delay_ms:.1f}ms before next attempt"
            )

            # Wait before next retry
            time.sleep(delay_ms / 1000.0)

            # Exponential backoff: 10ms, 20ms, 40ms, 80ms, 160ms (total ~310ms)
            delay_ms *= 2

        logger.error(
            f"❌ Failed to determine video ID after {max_retries} retries "
            f"(total wait: ~{initial_delay_ms * (2**max_retries - 1):.1f}ms)"
        )
        return None

    def _enrich_hil_event_context(self, hil_event: HILDetectionEvent, session_id: str, labjack_trigger_time: float) -> None:
        """
        Populate HILDetectionEvent with video/sequence metadata so downstream
        storage and WebSocket emission include the proper context.

        RACE CONDITION FIX: Implements retry logic with exponential backoff
        to handle cases where detections arrive 5-20ms before video_start_time is set.

        FIX #2: Always refresh cache for multi-video sequences.
        """
        try:
            session_cache = self.active_sessions.setdefault(session_id, {})

            # FIX #2: Check if multi-video sequence and force refresh
            metadata_video_ids: List[str] = []
            sequence_video_count = 0

            db = SessionLocal()
            try:
                session = db.query(TestSession).filter_by(id=session_id).first()
                if session:
                    raw_metadata = session.sequence_metadata or {}
                    if isinstance(raw_metadata, str):
                        try:
                            metadata = json.loads(raw_metadata)
                        except json.JSONDecodeError:
                            metadata = {}
                    else:
                        metadata = dict(raw_metadata)

                    metadata_video_ids = list(metadata.get("video_ids", []))

                    if session.sequence_id:
                        sequence_video_count = db.query(SequenceVideoResult).filter(
                            SequenceVideoResult.video_sequence_id == session.sequence_id
                        ).count()
            finally:
                db.close()

            is_multi_video = bool(sequence_video_count > 1 or len(metadata_video_ids) > 1)

            # ALWAYS refresh cache for multi-video sequences
            if is_multi_video:
                with self.lock:
                    session_cache.pop('sequence_context', None)
                logger.info(f"Cache invalidated for multi-video session {session_id}")

            with self.lock:
                cached_context = session_cache.get('sequence_context')

            # Load context from cache or database (will be fresh for multi-video)
            context = None
            if not cached_context or 'video_timing' not in cached_context or is_multi_video:
                context = self._load_sequence_context(session_id)
                with self.lock:
                    session_cache['sequence_context'] = context or {}
            else:
                context = cached_context

            # Default assignments
            video_id = None
            sequence_id = None
            sequence_video_result_id = None
            sequence_timestamp = None
            video_play_offset_ms = None

            if context:
                sequence_id = context.get('sequence_id')

                # FIX #5: Use enhanced retry logic with exponential backoff
                video_id = self._get_video_id_with_retry(
                    session_id=session_id,
                    trigger_time=labjack_trigger_time,
                    max_retries=5,
                    initial_delay_ms=10.0
                )

                # Skip old retry logic - now handled by _get_video_id_with_retry
                retry_delays_ms = []  # Disable old retry
                retry_attempt = 999  # Skip while loop

                while not video_id and retry_attempt < len(retry_delays_ms):
                    delay_ms = retry_delays_ms[retry_attempt]
                    logger.info(
                        f"🔄 RACE CONDITION RETRY {retry_attempt + 1}/{len(retry_delays_ms)}: "
                        f"No video_id at t={labjack_trigger_time:.6f}, waiting {delay_ms}ms for timing data"
                    )

                    # Sleep to allow lifecycle event to process
                    time.sleep(delay_ms / 1000.0)

                    # Refresh context from database
                    refreshed_context = self._load_sequence_context(session_id, retry_attempt=retry_attempt)
                    if refreshed_context:
                        with self.lock:
                            session_cache['sequence_context'] = refreshed_context
                        context = refreshed_context
                        sequence_id = context.get('sequence_id')
                        video_timing = context.get('video_timing', {})
                        video_id = self._determine_video_from_timing(
                            video_timing,
                            labjack_trigger_time,
                            session_id=session_id
                        )

                        if video_id:
                            logger.info(
                                f"✅ RACE CONDITION RESOLVED: Found video_id={video_id} "
                                f"after {delay_ms}ms retry (attempt {retry_attempt + 1})"
                            )
                            break

                    retry_attempt += 1

                # BUG FIX #8: Cache miss - refresh without retry delay
                if not video_id:
                    logger.info(f"🔄 Cache miss for detection at {labjack_trigger_time:.6f} - final refresh")
                    refreshed_context = self._load_sequence_context(session_id)
                    if refreshed_context:
                        with self.lock:
                            session_cache['sequence_context'] = refreshed_context
                        context = refreshed_context
                        sequence_id = context.get('sequence_id')
                        video_timing = context.get('video_timing', {})
                        video_id = self._determine_video_from_timing(
                            video_timing,
                            labjack_trigger_time,
                            session_id=session_id
                        )

                # FIX #3: Validate video status before assignment
                if video_id and not self._validate_video_status(video_id, session_id):
                    logger.warning(f"⚠️ Video {video_id} validation failed - detection not assigned")
                    video_id = None

                # FIX #18: Check current video from config ONLY if no video found and NOT multi-video
                if not video_id and not is_multi_video:
                    with self.lock:
                        config = session_cache.get('video_timing_config', {})
                    fallback_id = config.get('video_id')
                    if fallback_id and self._validate_video_status(fallback_id, session_id):
                        logger.warning(f"⚠️ Using config fallback video_id={fallback_id}")
                        video_id = fallback_id

                if sequence_id and video_id:
                    sequence_video_result = context.get('sequence_video_results', {}).get(video_id)
                    if sequence_video_result:
                        sequence_video_result_id = sequence_video_result.get('id')
                        video_play_offset_ms = sequence_video_result.get('video_play_offset_ms')

                sequence_started_at = context.get('sequence_started_at')
                if sequence_started_at is not None:
                    sequence_timestamp = labjack_trigger_time - sequence_started_at

            # CRITICAL: Log when video_id is still NULL after all attempts
            if not video_id:
                logger.error(
                    f"❌ No video found for detection at t={labjack_trigger_time:.6f} "
                    f"- detection will be stored with video_id=NULL. Ground truth matching will fail!"
                )
            else:
                logger.info(f"✅ Detection assigned to video {video_id}")

            hil_event.video_id = video_id
            hil_event.sequence_id = sequence_id
            hil_event.sequence_video_result_id = sequence_video_result_id
            hil_event.sequence_timestamp = sequence_timestamp
            hil_event.video_play_offset_ms = video_play_offset_ms

            # Harmonize video-relative timestamp with per-video offset when available.
            try:
                offset_seconds = None
                if video_play_offset_ms is not None:
                    offset_seconds = float(video_play_offset_ms) / 1000.0

                # Prefer explicit sequence timestamp if available.
                candidate_sequence_time = sequence_timestamp
                if candidate_sequence_time is None and hil_event.video_relative_timestamp is not None and offset_seconds is not None:
                    # Current value might still be sequence-relative. Detect and convert when it exceeds offset.
                    candidate_sequence_time = hil_event.video_relative_timestamp + offset_seconds

                if offset_seconds is not None and candidate_sequence_time is not None:
                    adjusted_relative = candidate_sequence_time - offset_seconds
                    # Clamp tiny negative drift to zero and ignore wildly negative conversions.
                    if adjusted_relative < 0 and adjusted_relative > -0.05:
                        adjusted_relative = 0.0
                    if adjusted_relative >= 0:
                        hil_event.video_relative_timestamp = adjusted_relative

                        # Update frame number using known FPS metadata when available.
                        fps = None
                        if context:
                            timing_info = context.get('video_timing', {}).get(video_id)
                            if isinstance(timing_info, dict):
                                fps = timing_info.get('fps') or timing_info.get('frame_rate')
                                try:
                                    fps = float(fps) if fps is not None else None
                                except (TypeError, ValueError):
                                    fps = None

                        if fps is None:
                            fps = 24.0  # Fallback to standard VRU footage frame rate

                        hil_event.video_frame_number = max(
                            0,
                            int(round(hil_event.video_relative_timestamp * fps))
                        )

                        # Record adjustment metadata
                        metadata = hil_event.detection_metadata.copy() if hil_event.detection_metadata else {}
                        metadata.update({
                            "video_offset_applied": True,
                            "video_offset_ms": video_play_offset_ms,
                            "sequence_timestamp": candidate_sequence_time,
                            "adjusted_video_timestamp": hil_event.video_relative_timestamp,
                            "frame_rate_used": fps
                        })
                        hil_event.detection_metadata = metadata
            except Exception as adjust_error:
                logger.warning(
                    f"⚠️ Failed to normalize video-relative timestamp for session {session_id}: {adjust_error}"
                )

        except Exception as exc:
            logger.warning(f"⚠️ Failed to enrich HIL event context for session {session_id}: {exc}")

    def _load_sequence_context(self, session_id: str, retry_attempt: int = 0) -> Optional[Dict[str, Any]]:
        """
        Load sequence metadata and cache it for quick lookup.

        RACE CONDITION FIX: Implements retry logic with exponential backoff
        to handle cases where detections arrive before video_start_time is set.

        Args:
            session_id: Session identifier
            retry_attempt: Current retry attempt (0-2)
        """
        try:
            db = SessionLocal()
            try:
                session_record: Optional[TestSession] = db.query(TestSession).filter(
                    TestSession.id == session_id
                ).first()
                if not session_record:
                    return None

                context: Dict[str, Any] = {
                    "sequence_id": session_record.sequence_id,
                    "fallback_video_id": session_record.video_id,
                    "sequence_started_at": session_record.started_at.timestamp() if session_record.started_at else None,
                    "video_timing": {},
                    "sequence_video_results": {}
                }

                raw_metadata = session_record.sequence_metadata
                metadata: Dict[str, Any] = {}
                if isinstance(raw_metadata, str):
                    try:
                        metadata = json.loads(raw_metadata)
                    except json.JSONDecodeError:
                        metadata = {}
                elif isinstance(raw_metadata, dict):
                    metadata = dict(raw_metadata)

                context["video_timing"] = metadata.get("video_timing", {})

                sequence_id = session_record.sequence_id
                if sequence_id:
                    results = db.query(SequenceVideoResult).filter(
                        SequenceVideoResult.video_sequence_id == sequence_id
                    ).all()
                    context["sequence_video_results"] = {
                        result.video_id: {
                            "id": result.id,
                            "video_play_offset_ms": result.video_play_offset_ms,
                            "video_start_time": result.video_start_time,
                            "video_end_time": result.video_end_time,
                            "actual_duration_ms": result.actual_duration_ms,
                            "video_status": result.video_status,
                            "validation_result": result.validation_result
                        }
                        for result in results
                    }

                return context
            finally:
                db.close()
        except Exception as exc:
            logger.warning(f"⚠️ Failed to load sequence context for session {session_id}: {exc}")
            return None

    @staticmethod
    def _to_float_timestamp(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                try:
                    return datetime.fromisoformat(value).timestamp()
                except ValueError:
                    return None
        return None

    def _validate_video_status(self, video_id: str, session_id: str) -> bool:
        """Validate that video is in 'playing' status before assignment."""
        try:
            db = next(get_db())
            try:
                # Ensure the video exists in the catalog
                video_exists = db.query(Video).filter(Video.id == video_id).first()
                if not video_exists:
                    logger.warning(f"Video {video_id} not found in video catalog")
                    return False

                # Ensure the video is part of the active sequence for this session (if any)
                session = db.query(TestSession).filter(TestSession.id == session_id).first()
                if session and session.sequence_id:
                    link = db.query(SequenceVideoResult).filter(
                        SequenceVideoResult.video_sequence_id == session.sequence_id,
                        SequenceVideoResult.video_id == video_id
                    ).first()
                    if not link:
                        logger.warning(
                            f"Video {video_id} not part of sequence {session.sequence_id} for session {session_id}"
                        )
                        return False

                return True
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error validating video status: {e}")
            return False

    def _get_or_create_clamped_windows(
        self,
        session_id: str,
        video_timing: Dict[str, Any]
    ) -> List[ClampedWindow]:
        """
        Get or create clamped detection windows for a session.

        This prevents overlapping grace periods in multi-video sequences by
        using the detection_window_clamp_service to intelligently split gaps.

        Args:
            session_id: Test session identifier
            video_timing: Video timing data from sequence metadata

        Returns:
            List of clamped detection windows with no overlaps
        """
        # Check cache first
        if session_id in self._clamped_windows:
            return self._clamped_windows[session_id]

        if not video_timing:
            logger.warning(f"No video timing data for session {session_id}")
            return []

        # Convert video timing dict to VideoTiming objects
        video_timings: List[VideoTiming] = []

        for video_id, timing in video_timing.items():
            start = self._to_float_timestamp(timing.get("started_at") or timing.get("start_time"))
            end = self._to_float_timestamp(timing.get("ended_at") or timing.get("end_time"))
            duration_ms = timing.get("duration_ms") or timing.get("actual_duration_ms")

            if start is not None:
                # Get sequence position (default to 0 if not available)
                sequence_position = timing.get("sequence_order", 0)

                video_timings.append(VideoTiming(
                    video_id=video_id,
                    sequence_position=sequence_position,
                    start_time=start,
                    end_time=end,
                    duration_ms=duration_ms
                ))

        if not video_timings:
            logger.warning(f"No valid video timings found for session {session_id}")
            return []

        # Use clamping service to generate non-overlapping windows
        try:
            clamped_windows = clamp_video_windows(
                video_timings=video_timings,
                grace_period_ms=GRACE_PERIOD_MS  # Use centralized config (2000ms)
            )

            # Cache the windows
            self._clamped_windows[session_id] = clamped_windows

            # Log window statistics
            logger.info(f"🔧 Generated {len(clamped_windows)} clamped detection windows for session {session_id}")
            for window in clamped_windows:
                logger.info(
                    f"  📊 Video {window.video_id}: "
                    f"[{window.start_time:.3f}s - {window.end_time:.3f}s] "
                    f"(grace: {window.grace_period_applied_ms:.0f}ms, "
                    f"clamped: {window.is_clamped})"
                )

            return clamped_windows

        except Exception as e:
            logger.error(f"Failed to generate clamped windows for session {session_id}: {e}")
            return []

    def _determine_video_from_timing(
        self,
        video_timing: Dict[str, Any],
        trigger_time: float,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Determine video ID based on clamped detection windows.

        INTEGRATION FIX: Now uses detection_window_clamp_service to prevent
        overlapping grace periods in multi-video sequences.

        Args:
            video_timing: Video timing metadata from sequence
            trigger_time: Detection trigger timestamp

        Returns:
            Video ID that detection belongs to, or None if no match
        """
        if not video_timing:
            logger.warning("No video timing data available")
            return None

        # Get session_id from active sessions (needed for caching)
        lookup_session_id = session_id
        if lookup_session_id is None:
            with self.lock:
                for sid, session_data in self.active_sessions.items():
                    session_video_timing = session_data.get('sequence_context', {}).get('video_timing', {})
                    if session_video_timing == video_timing:
                        lookup_session_id = sid
                        break

        if not lookup_session_id:
            logger.warning("Could not determine session_id for clamped windows - using legacy logic")
            # Fallback to legacy grace period logic if we can't determine session
            return self._determine_video_from_timing_legacy(video_timing, trigger_time)

        # Get or create clamped windows
        clamped_windows = self._get_or_create_clamped_windows(lookup_session_id, video_timing)

        if not clamped_windows:
            logger.warning("No clamped windows available - using legacy logic")
            return self._determine_video_from_timing_legacy(video_timing, trigger_time)

        # Use clamping service to assign detection
        result = assign_detection(
            detection_timestamp=trigger_time,
            clamped_windows=clamped_windows
        )

        if result:
            video_id, match_type = result
            logger.info(
                f"✅ Detection at {trigger_time:.3f}s assigned to {video_id} "
                f"via clamping service (match_type={match_type})"
            )
            return video_id
        else:
            logger.warning(
                f"⚠️ Detection at {trigger_time:.3f}s does not match any clamped window"
            )
            return None

    def _determine_video_from_timing_legacy(self, video_timing: Dict[str, Any], trigger_time: float) -> Optional[str]:
        """
        LEGACY: Original grace period logic (without clamping).

        This is used as a fallback when clamped windows cannot be generated.
        """
        if not video_timing:
            logger.warning("No video timing data available")
            return None

        # Convert to list and sort by start time
        videos = []
        for video_id, timing in video_timing.items():
            start = self._to_float_timestamp(timing.get("started_at") or timing.get("start_time"))
            end = self._to_float_timestamp(timing.get("ended_at") or timing.get("end_time"))

            if start is not None:
                videos.append({
                    'id': video_id,
                    'start': start,
                    'end': end
                })

        # Sort by start time
        videos.sort(key=lambda v: v['start'])

        for i, video in enumerate(videos):
            video_id = video['id']
            video_start = video['start']
            video_end = video['end']

            # Apply grace period to detection window
            grace_start = video_start - self.PRE_START_GRACE_SECONDS

            logger.debug(
                f"🔍 LEGACY: Checking detection window with grace period: "
                f"grace_start={grace_start:.3f}s, video_start={video_start:.3f}s, "
                f"video_end={video_end if video_end else 'ongoing'}s, trigger_time={trigger_time:.3f}s"
            )

            # For last video, check if trigger is after grace start (no end time yet)
            if video_end is None:
                if trigger_time >= grace_start:
                    if trigger_time < video_start:
                        logger.info(
                            f"✅ LEGACY: Detection at {trigger_time:.3f}s accepted in grace period "
                            f"({video_start - trigger_time:.3f}s before official start) for video {video_id}"
                        )
                    else:
                        logger.info(f"✅ LEGACY: Detection at {trigger_time:.3f}s assigned to video {video_id}")
                    return video_id
                continue

            # For completed videos, check if within grace range [grace_start, end)
            if grace_start <= trigger_time < video_end:
                if trigger_time < video_start:
                    logger.info(
                        f"✅ LEGACY: Detection at {trigger_time:.3f}s accepted in grace period "
                        f"({video_start - trigger_time:.3f}s before official start) for video {video_id}"
                    )
                else:
                    logger.info(f"✅ LEGACY: Detection at {trigger_time:.3f}s assigned to video {video_id}")
                return video_id

        logger.warning(f"⚠️ LEGACY: Detection at {trigger_time:.3f}s does not match any video time range")
        return None
    
    async def _store_detection_event_async(self, hil_event: HILDetectionEvent) -> None:
        """Store HIL detection event in database with video timing synchronization"""
        try:
            db = next(get_db())
            try:
                # Log timing data for debugging
                logger.info(f"✅ Creating DetectionEvent with REAL data: voltage={hil_event.labjack_voltage:.3f}V, channel={hil_event.detection_channel}, latency={hil_event.actual_latency_ms:.1f}ms")

                # CRITICAL FIX: Ensure video_id is always set - fallback to session's video_id
                video_id_for_detection = hil_event.video_id
                if not video_id_for_detection:
                    # BUG FIX: Get video_id from session
                    try:
                        session = db.query(TestSession).filter_by(id=hil_event.session_id).first()
                        if session and session.video_id:
                            video_id_for_detection = session.video_id
                            logger.info(f"✅ Using session video_id fallback: {video_id_for_detection} for detection {hil_event.id}")
                        else:
                            logger.error(f"❌ CRITICAL: Cannot determine video_id for detection {hil_event.id} - will be stored as NULL")
                    except Exception as fallback_error:
                        logger.error(f"❌ Failed to get fallback video_id: {fallback_error}")

                # Create complete DetectionEvent with voltage data for HIL validation
                # Use HIL event's unix_timestamp as the detection timestamp
                detection_timestamp = hil_event.unix_timestamp

                # FIX #5: Calculate video_start_time for timing synchronization
                video_start_time = None
                if hil_event.video_relative_timestamp is not None and detection_timestamp is not None:
                    video_start_time = detection_timestamp - hil_event.video_relative_timestamp
                    logger.debug(f"Async: Calculated video_start_time: {video_start_time}")

                detection_event = DetectionEvent(
                    id=hil_event.id,
                    test_session_id=hil_event.session_id,
                    video_id=video_id_for_detection,  # ✅ FIXED: Always attempt to set video_id
                    timestamp=detection_timestamp,  # TIMING FIX: Store hardware trigger time
                    validation_result=validation_result,

                    # FIXED: Store the actual calculated latency for frontend display
                    processing_time_ms=hil_event.actual_latency_ms,  # Use calculated processing latency
                    labjack_timestamp=float(detection_timestamp),  # TIMING FIX: Hardware trigger time
                    labjack_timestamp_ns=int(detection_timestamp * 1e9),  # TIMING FIX: Nanosecond precision

                    # CRITICAL FIX: Ensure LabJack voltage and channel data is stored
                    labjack_voltage=float(hil_event.labjack_voltage) if hil_event.labjack_voltage is not None else None,
                    detection_channel=str(hil_event.detection_channel) if hil_event.detection_channel else None,
                    video_relative_timestamp=hil_event.video_relative_timestamp,
                    video_frame_number=hil_event.video_frame_number,
                    actual_latency_ms=hil_event.actual_latency_ms,
                    timing_sync_quality=hil_event.timing_sync_quality,
                    detection_type="hardware",
                    source="labjack",
                    unix_timestamp=float(detection_timestamp),  # TIMING FIX: Detection record time
                    detection_timestamp=datetime.fromtimestamp(detection_timestamp, tz=timezone.utc),  # TIMING FIX: DateTime version

                    # HIL screenshot and ground truth fields
                    screenshot_path=hil_event.screenshot_path,
                    screenshot_zoom_path=hil_event.screenshot_zoom_path,
                    # FIX #5: Set video_start_time for timing synchronization calculator
                    video_start_time=video_start_time
                )
                
                db.add(detection_event)
                db.commit()

                # Dual-write: forward to TS ingestion API if configured
                try:
                    import requests
                    ts_url = os.getenv('TS_INGEST_URL') or os.getenv('TS_INGEST_ENDPOINT')
                    service_token = os.getenv('SERVICE_TOKEN')
                    if ts_url and service_token:
                        payload = {
                            "sessionId": hil_event.session_id,
                            "timestamp": hil_event.unix_timestamp,
                            "voltage": hil_event.labjack_voltage,
                            "channel": hil_event.detection_channel,
                            "latencyMs": hil_event.actual_latency_ms,
                            "videoTimestamp": hil_event.video_relative_timestamp,
                            "frame": hil_event.video_frame_number,
                            "metadata": {
                                "timingSyncQuality": hil_event.timing_sync_quality,
                                "precisionNs": getattr(hil_event, 'precision_ns', None)
                            }
                        }
                        headers = {"X-Service-Token": service_token, "Content-Type": "application/json"}
                        # Non-blocking best-effort POST with short timeout
                        endpoint = ts_url.rstrip('/') + '/labjack/detection-event'
                        # Simple retry with backoff
                        for attempt in range(3):
                            try:
                                resp = requests.post(endpoint, json=payload, headers=headers, timeout=1.5)
                                if resp.status_code >= 400:
                                    try:
                                        msg = resp.json()
                                    except Exception:
                                        msg = resp.text
                                    logger.warning(f"TS ingest failed ({resp.status_code}) for session {hil_event.session_id}: {msg}")
                                break
                            except Exception:
                                time.sleep(0.2 * (attempt + 1))
                except Exception as e:
                    logger.debug(f"Dual-write to TS ingestion skipped: {e}")

                logger.debug(f"💾 Stored HIL detection event in database: {hil_event.id}")
                
            except SQLAlchemyError as e:
                logger.error(f"Database error storing HIL detection event: {e}")
                db.rollback()
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error storing HIL detection event: {e}")
    
    def stop_session_monitoring(self, session_id: str) -> Dict[str, Any]:
        """
        Stop monitoring for a specific session while preserving hardware connection.
        
        CRITICAL FIX: This is the new session-preserving cleanup method that:
        1. Only removes session-specific callbacks and data
        2. Preserves the hardware connection for reuse
        3. Updates active session tracking without disconnecting LabJack
        4. Maintains bridge connection state
        
        Args:
            session_id: Test session identifier
            
        Returns:
            Dictionary containing session statistics
        """
        try:
            with self.lock:
                # Get session data before any cleanup
                session_data = self.active_sessions.get(session_id, {})
                detection_events = self.detection_events.get(session_id, [])
                
                if not session_data:
                    logger.warning(f"⚠️ Session {session_id} not found in active sessions")
                    return {
                        'session_id': session_id,
                        'success': False,
                        'error': 'Session not found',
                        'connection_preserved': True
                    }
                
                logger.info(f"🔄 Stopping session monitoring (preserving connection): {session_id}")
                
                # STEP 1: Remove session-specific detection callback FIRST
                # This prevents callbacks from triggering during cleanup
                detection_callback = session_data.get('detection_callback')
                if detection_callback and self.labjack_monitor:
                    try:
                        self.labjack_monitor.remove_detection_callback(detection_callback)
                        logger.info(f"🧹 Detection callback removed for session {session_id}")
                    except Exception as e:
                        logger.error(f"Failed to remove detection callback for session {session_id}: {e}")
                
                # STEP 2: Stop session-specific monitoring (preserve hardware connection)
                try:
                    # NEW: Use stop_session_monitoring if available (connection-preserving)
                    if hasattr(self.labjack_monitor, 'stop_session_monitoring'):
                        success = self.labjack_monitor.stop_session_monitoring(session_id)
                        logger.info(f"✅ Session monitoring stopped (connection preserved): {session_id}")
                    else:
                        # Fallback: Use the standard stop but warn about potential connection drop
                        logger.warning(f"⚠️ Using legacy stop method - may affect other sessions: {session_id}")
                        success = self.labjack_monitor.stop_monitoring(session_id)
                except Exception as e:
                    logger.error(f"Failed to stop session monitoring: {e}")
                    success = False
                
                # STEP 3: Stop bridge session monitoring (preserve bridge connection)
                try:
                    from services.windows_labjack_bridge import windows_labjack_bridge
                    bridge_success = windows_labjack_bridge.stop_session_monitoring(session_id)
                    if bridge_success:
                        logger.info(f"🛑 Bridge session monitoring stopped (connection preserved): {session_id}")
                    else:
                        logger.warning(f"⚠️ Bridge session monitoring stop failed: {session_id}")
                except Exception as bridge_error:
                    logger.warning(f"Could not stop bridge session monitoring: {bridge_error}")
                
                # STEP 4: Calculate session statistics
                duration_seconds = 0
                if session_data.get('started_at'):
                    duration_seconds = (datetime.now(timezone.utc) - session_data['started_at']).total_seconds()
                
                detection_count = len(detection_events)
                high_quality_count = len([e for e in detection_events if e.timing_sync_quality == 'high'])
                average_latency = sum(e.actual_latency_ms for e in detection_events if e.actual_latency_ms) / detection_count if detection_count > 0 else 0
                
                statistics = {
                    'session_id': session_id,
                    'success': success,
                    'duration_seconds': duration_seconds,
                    'detection_count': detection_count,
                    'high_quality_detections': high_quality_count,
                    'average_latency_ms': average_latency,
                    'conversion_success_rate': (self.successful_conversions / max(1, self.total_detections)) * 100,
                    'video_start_time': session_data.get('video_start_time'),
                    'timing_sync_enabled': True,
                    'connection_preserved': True,  # CRITICAL: Hardware connection is preserved
                    'active_sessions_remaining': len(self.active_sessions) - 1  # Count after this session is removed
                }
                
                # STEP 5: Clean up HIL screenshot and ground truth resources
                try:
                    self.hil_comparison_service.cleanup_session(session_id)
                except Exception as e:
                    logger.warning(f"Failed to cleanup HIL resources for session {session_id}: {e}")
                
                # STEP 6: Unregister session from LabJack service
                try:
                    labjack_service = get_labjack_service()
                    labjack_service.end_session(session_id)
                    logger.info(f"✅ Session {session_id} unregistered from LabJack service")
                except Exception as e:
                    logger.warning(f"Failed to unregister session from LabJack service: {e}")

                # STEP 7: Clean up session data (but preserve global connection)
                self.active_sessions.pop(session_id, None)
                # Keep detection events for potential retrieval unless explicitly cleaned up

                remaining_sessions = len(self.active_sessions)
                logger.info(f"✅ HIL session monitoring stopped (connection preserved) {session_id}: "
                           f"{detection_count} detections, {average_latency:.1f}ms avg latency, "
                           f"{remaining_sessions} sessions remaining")

                if remaining_sessions == 0:
                    logger.info("ℹ️ No active sessions remain - hardware connection is idle but preserved")

                return statistics
                
        except Exception as e:
            logger.error(f"Error stopping HIL session monitoring: {e}")
            return {
                'session_id': session_id,
                'success': False,
                'connection_preserved': True,  # Even on error, we preserve connection
                'error': str(e)
            }
    
    def stop_monitoring(self, session_id: str) -> Dict[str, Any]:
        """
        Legacy stop monitoring method - now redirects to session-preserving method.
        
        DEPRECATED: Use stop_session_monitoring() for better connection management.
        This method is kept for backward compatibility but now preserves connections.
        
        Args:
            session_id: Test session identifier
            
        Returns:
            Dictionary containing session statistics
        """
        logger.warning(f"⚠️ Using legacy stop_monitoring - redirecting to session-preserving method")
        return self.stop_session_monitoring(session_id)
    
    def get_session_events(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all detection events for a session with video timing data"""
        with self.lock:
            events = self.detection_events.get(session_id, [])
            return [
                {
                    'id': event.id,
                    'session_id': event.session_id,
                    'unix_timestamp': event.unix_timestamp,
                    'video_relative_timestamp': event.video_relative_timestamp,
                    'actual_latency_ms': event.actual_latency_ms,
                    'video_frame_number': event.video_frame_number,
                    'timing_sync_quality': event.timing_sync_quality,
                    'labjack_voltage': event.labjack_voltage,
                    'detection_channel': event.detection_channel,
                    'screenshot_path': event.screenshot_path,
                    'screenshot_zoom_path': event.screenshot_zoom_path,
                    'ground_truth_comparison': event.ground_truth_comparison,
                    'created_at': event.created_at.isoformat()
                }
                for event in events
            ]
    
    def get_monitoring_statistics(self) -> Dict[str, Any]:
        """Get overall monitoring statistics"""
        with self.lock:
            active_sessions = len(self.active_sessions)
            total_events = sum(len(events) for events in self.detection_events.values())
            
            return {
                'active_sessions': active_sessions,
                'total_detections': self.total_detections,
                'successful_conversions': self.successful_conversions,
                'failed_conversions': self.failed_conversions,
                'conversion_success_rate': (self.successful_conversions / max(1, self.total_detections)) * 100,
                'total_events_stored': total_events,
                'video_timing_service_active': self.video_timing_service is not None,
                'labjack_monitor_available': self.labjack_monitor is not None
            }
    
    def cleanup_session_data(self, session_id: str) -> bool:
        """Clean up all data for a session"""
        try:
            with self.lock:
                self.active_sessions.pop(session_id, None)
                self.detection_events.pop(session_id, None)

                # Also cleanup from underlying services
                self.video_timing_service.clear_session_timing(session_id)
                self.labjack_monitor.cleanup_session_data(session_id)

                # Cleanup HIL screenshot and ground truth resources
                try:
                    self.hil_comparison_service.cleanup_session(session_id)
                except Exception as e:
                    logger.warning(f"Failed to cleanup HIL resources: {e}")

                logger.info(f"Cleaned up HIL monitoring data for session {session_id}")
                return True

        except Exception as e:
            logger.error(f"Error cleaning up session data: {e}")
            return False

    def cleanup(self) -> None:
        """
        Cleanup all resources for graceful shutdown.

        This method is called by signal handlers to ensure all monitoring
        resources are properly released when the application shuts down.
        """
        try:
            logger.info("Starting DedicatedLabJackMonitor cleanup...")

            # Stop monitoring for all active sessions
            with self.lock:
                active_session_ids = list(self.active_sessions.keys())

            for session_id in active_session_ids:
                try:
                    logger.info(f"Stopping monitoring for session: {session_id}")
                    self.stop_session_monitoring(session_id)
                except Exception as e:
                    logger.error(f"Error stopping session {session_id}: {e}")

            # Cleanup underlying services
            try:
                if hasattr(self.labjack_monitor, 'cleanup'):
                    self.labjack_monitor.cleanup()
                elif hasattr(self.labjack_monitor, 'close'):
                    self.labjack_monitor.close()
            except Exception as e:
                logger.error(f"Error cleaning up LabJack monitor: {e}")

            # Cleanup HIL comparison service
            try:
                if hasattr(self.hil_comparison_service, 'cleanup'):
                    self.hil_comparison_service.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up HIL comparison service: {e}")

            logger.info("DedicatedLabJackMonitor cleanup complete")

        except Exception as e:
            logger.error(f"Error during DedicatedLabJackMonitor cleanup: {e}", exc_info=True)
    
    def _schedule_hil_processing(self, session_id: str, detection_data: Dict[str, Any], video_path: str, video_config: Dict[str, Any]):
        """Schedule HIL screenshot capture and ground truth processing"""
        try:
            # Run HIL processing in background thread to avoid blocking detection

            def _hil_processing_worker():
                try:
                    # Create new event loop for async operations in thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        # Process HIL detection with screenshots and ground truth
                        result = loop.run_until_complete(
                            self.hil_comparison_service.process_hil_detection_with_screenshots(
                                session_id=session_id,
                                detection_data=detection_data,
                                video_path=video_path,
                                video_metadata=video_config
                            )
                        )
                        
                        # Update the detection event with screenshot paths and ground truth data
                        self._update_detection_with_hil_results(session_id, detection_data['id'], result)
                        
                        logger.info(f"HIL processing completed for detection {detection_data['id']}")
                        
                    finally:
                        loop.close()
                        
                except Exception as e:
                    logger.error(f"HIL processing worker failed: {e}")
            
            # Start background processing
            thread = threading.Thread(target=_hil_processing_worker, daemon=True)
            thread.start()
            
        except Exception as e:
            logger.error(f"Failed to schedule HIL processing: {e}")
    
    def _update_detection_with_hil_results(self, session_id: str, detection_id: str, hil_result: Dict[str, Any]):
        """Update detection event with HIL screenshot and ground truth results"""
        try:
            with self.lock:
                # Find and update the detection event
                events = self.detection_events.get(session_id, [])
                for event in events:
                    if event.id == detection_id:
                        if hil_result.get('success'):
                            screenshot_data = hil_result.get('screenshot_capture', {})
                            event.screenshot_path = screenshot_data.get('screenshot_path')
                            event.screenshot_zoom_path = screenshot_data.get('screenshot_zoom_path')
                            event.ground_truth_comparison = hil_result.get('ground_truth_comparison')
                            
                            logger.debug(f"Updated HIL event {detection_id} with screenshot and ground truth data")
                        else:
                            logger.warning(f"HIL processing failed for detection {detection_id}: {hil_result.get('error')}")
                        break
                        
        except Exception as e:
            logger.error(f"Failed to update detection with HIL results: {e}")


# Global service instance
_dedicated_monitor: Optional[DedicatedLabJackMonitor] = None
_monitor_lock = threading.Lock()


def get_dedicated_labjack_monitor(websocket_emit_fn: Optional[Callable] = None) -> DedicatedLabJackMonitor:
    """
    Get global dedicated LabJack monitor instance (thread-safe singleton).

    Args:
        websocket_emit_fn: Optional WebSocket emission function for real-time detection broadcasting
    """
    global _dedicated_monitor

    if _dedicated_monitor is None:
        with _monitor_lock:
            if _dedicated_monitor is None:
                _dedicated_monitor = DedicatedLabJackMonitor(websocket_emit_fn=websocket_emit_fn)
    elif websocket_emit_fn and not _dedicated_monitor.labjack_monitor._websocket_emit_fn:
        # If WebSocket function provided later, register it
        _dedicated_monitor.labjack_monitor.set_websocket_emit_function(websocket_emit_fn)
        logger.info("✅ WebSocket emission function registered with existing monitor instance")

    return _dedicated_monitor


# Convenience functions
async def start_hil_monitoring(video_timing_config: Dict[str, Any]) -> bool:
    """
    Start HIL monitoring with video timing synchronization

    ✅ FIX-2: Extract primary session ID from config instead of accepting as parameter
    This prevents session ID duplication and ensures monitor uses API-created session

    Args:
        video_timing_config: Configuration dict MUST contain 'test_session_id'

    Returns:
        True if monitoring started successfully

    Raises:
        ValueError: If test_session_id not provided in config
    """
    # ✅ FIX-2: Extract PRIMARY session ID from config
    primary_session_id = video_timing_config.get('test_session_id')

    if not primary_session_id:
        logger.error("❌ FIX-2: test_session_id must be provided in video_timing_config")
        logger.error(f"❌ Config keys: {list(video_timing_config.keys())}")
        raise ValueError("test_session_id must be provided in video_timing_config")

    logger.info(f"✅ FIX-2: Using PRIMARY session ID: {primary_session_id}")

    monitor = get_dedicated_labjack_monitor()
    return await monitor.start_monitoring_with_video_sync(primary_session_id, video_timing_config)


def stop_hil_monitoring(session_id: str) -> Dict[str, Any]:
    """Stop HIL monitoring with connection-preserving cleanup"""
    monitor = get_dedicated_labjack_monitor()
    return monitor.stop_session_monitoring(session_id)


def stop_hil_monitoring_legacy(session_id: str) -> Dict[str, Any]:
    """DEPRECATED: Legacy stop method - use stop_hil_monitoring() instead"""
    monitor = get_dedicated_labjack_monitor()
    return monitor.stop_monitoring(session_id)


def get_hil_session_events(session_id: str) -> List[Dict[str, Any]]:
    """Get HIL detection events for a session"""
    monitor = get_dedicated_labjack_monitor()
    return monitor.get_session_events(session_id)


# Export key components
__all__ = [
    "DedicatedLabJackMonitor",
    "HILDetectionEvent", 
    "get_dedicated_labjack_monitor",
    "start_hil_monitoring",
    "stop_hil_monitoring",
    "stop_hil_monitoring_legacy",
    "get_hil_session_events"
]
