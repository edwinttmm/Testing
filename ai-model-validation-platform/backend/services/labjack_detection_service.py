"""
LabJack Detection Monitoring Service

This service provides real-time detection event monitoring for LabJack hardware,
focusing on recording detection events with timestamps for latency analysis.

Features:
- Event-based detection monitoring (not continuous streaming)
- Configurable voltage thresholds per channel
- Debounce logic to prevent duplicate detections
- Optional continuous sampling mode with configurable interval/voltage window
- Thread-safe real-time monitoring
- WebSocket notifications for detection events
- Database integration for event storage
- Latency calculation support
"""

import asyncio
import logging
import threading
import time
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, asdict
from enum import Enum
import queue

# Import centralized timing configuration
from config.timing_config import GRACE_PERIOD_MS, GRACE_PERIOD_SECONDS

# Database imports
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
try:
    from database import SessionLocal, get_db
    from sqlalchemy import text

    def _check_database_connectivity():
        """Validate database is actually connected, not just importable"""
        try:
            db = SessionLocal()
            try:
                db.execute(text("SELECT 1"))
                return True
            finally:
                db.close()
        except Exception as e:
            logging.error(f"Database connectivity check failed: {e}")
            return False

    DATABASE_AVAILABLE = _check_database_connectivity()
    if DATABASE_AVAILABLE:
        logging.info("✅ Database connectivity validated")
    else:
        logging.warning("⚠️ Database not available, detection events will not be persisted")
except ImportError:
    DATABASE_AVAILABLE = False
    logging.warning("Database module not available, detection events will not be persisted")

# LabJack service integration
from services.labjack_service import get_labjack_service, LabJackService
from services.labjack_hardware_service import get_labjack_hardware_service
from services.video_id_resolver import get_video_id_for_detection, get_sequence_video_result_id

logger = logging.getLogger(__name__)

# Export get_detection_service function
def get_detection_service():
    """Get or create detection service instance"""
    global _detection_service_instance
    if _detection_service_instance is None:
        _detection_service_instance = LabJackDetectionMonitor()
    return _detection_service_instance

_detection_service_instance = None


class DetectionStatus(Enum):
    """Detection monitoring status"""
    STOPPED = "stopped"
    STARTING = "starting"
    MONITORING = "monitoring"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class DetectionEvent:
    """Detection event data structure"""
    id: str
    session_id: str
    timestamp: datetime
    channel: str
    voltage: float
    threshold: float
    detected: bool = True
    is_duplicate: bool = False
    metadata: Optional[Dict[str, Any]] = None
    # Timing calibration fields
    video_relative_timestamp: Optional[float] = None
    actual_latency_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'session_id': self.session_id,
            'timestamp': self.timestamp.isoformat(),
            'channel': self.channel,
            'voltage': self.voltage,
            'threshold': self.threshold,
            'detected': self.detected,
            'is_duplicate': self.is_duplicate,
            'metadata': self.metadata or {},
            'video_relative_timestamp': self.video_relative_timestamp,
            'actual_latency_ms': self.actual_latency_ms
        }


@dataclass
class DetectionConfig:
    """Configuration for detection monitoring"""
    session_id: str
    channels: List[str]
    voltage_threshold: float = 2.5
    debounce_ms: int = 100
    sample_rate: int = 1000
    enable_websocket: bool = True
    store_in_db: bool = True
    metadata: Optional[Dict[str, Any]] = None
    continuous_mode: bool = False
    continuous_lower_bound: Optional[float] = None
    continuous_upper_bound: Optional[float] = None
    continuous_interval_ms: int = 20


class LabJackDetectionMonitor:
    """
    LabJack Detection Event Monitor
    
    Monitors LabJack channels for detection events (voltage threshold crossings)
    and records events with precise timestamps for latency analysis.
    """
    
    def __init__(self, labjack_service: Optional[LabJackService] = None):
        self.labjack_service = labjack_service or get_labjack_service()
        # Connect to real hardware service for voltage readings
        self.hardware_service = get_labjack_hardware_service()
        
        # Database service integration - using direct database access
        self.db_service = None  # Direct database integration instead
        
        # Monitoring state
        self.active_sessions: Dict[str, DetectionConfig] = {}
        self.detection_status: Dict[str, DetectionStatus] = {}
        self.monitoring_threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        
        # Detection data
        self.detection_events: Dict[str, List[DetectionEvent]] = {}
        self.last_detection_times: Dict[str, Dict[str, datetime]] = {}  # session_id -> channel -> timestamp
        self.last_continuous_emit_times: Dict[str, Dict[str, datetime]] = {}
        
        # Use shared LabJack connection manager to prevent device conflicts
        try:
            from services.labjack_connection_manager import get_connection_manager
            self.connection_manager = get_connection_manager()
            logger.info("✅ Using shared LabJack connection manager")
        except ImportError:
            self.connection_manager = None
            logger.warning("⚠️ LabJack connection manager not available - may have device conflicts")
        
        # Callbacks and notifications
        self.detection_callbacks: List[Callable[[DetectionEvent], None]] = []
        self.websocket_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

        # WebSocket emission function (async)
        self._websocket_emit_fn: Optional[Callable] = None

        # Thread synchronization
        self.lock = threading.RLock()
        
        db_status = "✅ Connected" if DATABASE_AVAILABLE else "❌ Not available"
        logger.info(f"LabJack Detection Monitor initialized (Database: {db_status})")
    
    def add_detection_callback(self, callback: Callable[[DetectionEvent], None]):
        """Add callback for detection events"""
        with self.lock:
            self.detection_callbacks.append(callback)
            logger.info(f"Detection callback added - total callbacks: {len(self.detection_callbacks)}")
    
    def remove_detection_callback(self, callback: Callable[[DetectionEvent], None]):
        """Remove callback for detection events"""
        with self.lock:
            if callback in self.detection_callbacks:
                self.detection_callbacks.remove(callback)
                logger.info(f"🧹 Detection callback removed - remaining callbacks: {len(self.detection_callbacks)}")
            else:
                logger.warning("Attempted to remove callback that was not registered")
    
    def add_websocket_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add WebSocket notification callback"""
        with self.lock:
            self.websocket_callbacks.append(callback)
            logger.info(f"✅ WebSocket callback registered - total: {len(self.websocket_callbacks)}")

    def set_websocket_emit_function(self, emit_fn: Callable):
        """
        Set the WebSocket emission function from socketio_server.
        This allows real-time detection event broadcasting.
        """
        self._websocket_emit_fn = emit_fn
        logger.info("✅ WebSocket emit function registered for real-time detection broadcasting")
    
    def start_monitoring(self, session_id: str, channels: List[str] = None,
                        voltage_threshold: float = 2.5, debounce_ms: int = 100,
                        sample_rate: int = 1000, **kwargs) -> bool:
        """
        Start detection monitoring for a session

        Args:
            session_id: Unique session identifier
            channels: List of channels to monitor (default: ["AIN0", "AIN1"])
            voltage_threshold: Voltage threshold for detection (default: 2.5V)
            debounce_ms: Debounce time in milliseconds (default: 100ms)
            sample_rate: Sampling rate in Hz (default: 1000Hz)
            **kwargs: Additional configuration options including:
                - duration: Video duration in seconds (for auto-stop)
                - video_start_time: Video start timestamp (for auto-stop)
                - continuous_mode: Emit detections continuously while voltage stays within bounds
                - continuous_lower_bound / continuous_upper_bound: Voltage window for continuous mode
                - continuous_interval_ms: Minimum interval between emitted samples in continuous mode

        Returns:
            bool: True if monitoring started successfully
        """
        channels = channels or ["AIN0", "AIN1"]

        with self.lock:
            if session_id in self.active_sessions:
                logger.warning(f"Monitoring already active for session {session_id}")
                return True

            # CRITICAL FIX: Include video timing metadata for auto-stop
            metadata = kwargs.get('metadata', {})
            if not isinstance(metadata, dict):
                metadata = {}

            # Add video timing info to metadata if provided
            if 'duration' in kwargs:
                metadata['duration'] = kwargs['duration']
            if 'video_start_time' in kwargs:
                metadata['video_start_time'] = kwargs['video_start_time']

            # Create configuration
            config = DetectionConfig(
                session_id=session_id,
                channels=channels,
                voltage_threshold=voltage_threshold,
                debounce_ms=debounce_ms,
                sample_rate=sample_rate,
                enable_websocket=kwargs.get('enable_websocket', True),
                store_in_db=kwargs.get('store_in_db', True),
                metadata=metadata,
                continuous_mode=kwargs.get('continuous_mode', False),
                continuous_lower_bound=kwargs.get('continuous_lower_bound'),
                continuous_upper_bound=kwargs.get('continuous_upper_bound'),
                continuous_interval_ms=kwargs.get('continuous_interval_ms', 20)
            )
            
            # Initialize session state
            self.active_sessions[session_id] = config
            self.detection_status[session_id] = DetectionStatus.STARTING
            self.detection_events[session_id] = []
            self.last_detection_times[session_id] = {ch: datetime.min for ch in channels}
            self.last_continuous_emit_times[session_id] = {ch: datetime.min for ch in channels}
            self.stop_events[session_id] = threading.Event()
            
            # Create database session record
            if DATABASE_AVAILABLE:
                try:
                    # Create session record in database using direct approach
                    logger.info(f"📝 Creating database session record for {session_id}")
                except Exception as e:
                    logger.warning(f"Failed to create session record: {e}")
            
            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                args=(session_id,),
                daemon=True,
                name=f"LabJackMonitor-{session_id}"
            )
            self.monitoring_threads[session_id] = monitor_thread
            monitor_thread.start()
            
            logger.info(f"✅ Started detection monitoring for session {session_id}")
            logger.info(f"📊 Channels: {channels}, Threshold: {voltage_threshold}V, Debounce: {debounce_ms}ms")
            
            return True
    
    def stop_session_monitoring(self, session_id: str) -> bool:
        """
        Stop detection monitoring for a specific session while preserving hardware connection.
        
        CRITICAL FIX: This method provides session-preserving cleanup that:
        1. Only stops monitoring for the specified session
        2. Preserves the LabJack hardware connection for other sessions
        3. Maintains thread safety and proper cleanup
        
        Args:
            session_id: Session identifier to stop monitoring for
        
        Returns:
            bool: True if session monitoring stopped successfully
        """
        with self.lock:
            if session_id not in self.active_sessions:
                logger.warning(f"No active monitoring for session {session_id}")
                return True
            
            logger.info(f"🔄 Stopping session monitoring (preserving connection): {session_id}")
            
            self.detection_status[session_id] = DetectionStatus.STOPPING
            
            # Signal stop to monitoring thread
            if session_id in self.stop_events:
                self.stop_events[session_id].set()
                logger.info(f"🛑 Stop signal sent for session {session_id}")
            
            # Wait for monitoring thread to finish (with timeout)
            if session_id in self.monitoring_threads:
                thread = self.monitoring_threads[session_id]
                if thread.is_alive():
                    logger.info(f"⏳ Waiting for monitoring thread to stop for session {session_id}")
                    thread.join(timeout=5.0)  # Wait up to 5 seconds
                    
                    if thread.is_alive():
                        logger.warning(f"⚠️ Monitoring thread for session {session_id} did not stop within timeout")
                    else:
                        logger.info(f"✅ Monitoring thread stopped for session {session_id}")
                
                # Remove thread reference
                del self.monitoring_threads[session_id]
            
            # End database session record
            if DATABASE_AVAILABLE:
                try:
                    logger.info(f"📝 Ending database session record for {session_id}")
                except Exception as e:
                    logger.warning(f"Failed to end session record: {e}")
            
            # Clean up session-specific state only
            self._cleanup_session_preserving_connection(session_id)
            
            remaining_sessions = len(self.active_sessions)
            logger.info(f"✅ Session monitoring stopped (connection preserved): {session_id}, "
                       f"{remaining_sessions} sessions remaining")
            
            if remaining_sessions == 0:
                logger.info("ℹ️ No active sessions remain - LabJack connection idle but preserved")
            
            return True
    
    def stop_monitoring(self, session_id: str) -> bool:
        """
        Legacy stop monitoring method - now redirects to session-preserving method.
        
        DEPRECATED: Use stop_session_monitoring() for better connection management.
        This method is kept for backward compatibility but now preserves connections.
        
        Args:
            session_id: Session identifier to stop
        
        Returns:
            bool: True if stopped successfully
        """
        logger.warning(f"⚠️ Using legacy stop_monitoring - redirecting to session-preserving method")
        return self.stop_session_monitoring(session_id)
    
    def get_detection_events(self, session_id: str, from_database: bool = True) -> List[Dict[str, Any]]:
        """
        Get all detection events for a session
        
        Args:
            session_id: Session identifier
            from_database: If True, try to get events from database first
        
        Returns:
            List[Dict]: List of detection event dictionaries
        """
        # Try database first if available and requested
        if from_database and DATABASE_AVAILABLE:
            db = SessionLocal()
            try:
                # Direct database query for events
                from models import DetectionEvent as DBDetectionEvent
                events = db.query(DBDetectionEvent).filter(
                    DBDetectionEvent.test_session_id == session_id
                ).order_by(DBDetectionEvent.timestamp).all()

                if events:
                    db_events = [event.to_dict() for event in events if hasattr(event, 'to_dict')]
                    logger.debug(f"Retrieved {len(db_events)} events from database for session {session_id}")
                    return db_events
            except Exception as e:
                logger.warning(f"Failed to get events from database, using memory: {e}")
            finally:
                db.close()
        
        # Fallback to memory storage
        with self.lock:
            if session_id not in self.detection_events:
                return []
            
            events = self.detection_events[session_id]
            return [event.to_dict() for event in events]
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get status information for a session"""
        with self.lock:
            if session_id not in self.active_sessions:
                return {
                    'session_id': session_id,
                    'status': 'not_found',
                    'active': False,
                    'event_count': 0
                }
            
            config = self.active_sessions[session_id]
            status = self.detection_status.get(session_id, DetectionStatus.STOPPED)
            event_count = len(self.detection_events.get(session_id, []))
            
            return {
                'session_id': session_id,
                'status': status.value,
                'active': status == DetectionStatus.MONITORING,
                'config': asdict(config),
                'event_count': event_count,
                'last_detection_times': {
                    ch: ts.isoformat() if ts != datetime.min else None
                    for ch, ts in self.last_detection_times.get(session_id, {}).items()
                }
            }
    
    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get status for all active sessions"""
        with self.lock:
            return [self.get_session_status(sid) for sid in self.active_sessions.keys()]
    
    def _monitoring_loop(self, session_id: str):
        """Main monitoring loop for a session with auto-stop on video end"""
        try:
            config = self.active_sessions[session_id]
            stop_event = self.stop_events[session_id]

            self.detection_status[session_id] = DetectionStatus.MONITORING

            # Calculate polling interval based on sample rate
            poll_interval = 1.0 / config.sample_rate

            # CRITICAL FIX: Get video duration and calculate stop time with buffer
            video_duration = None
            video_start_time = None
            stop_time_with_buffer = None
            multi_video_buffer = 0.5

            # Get video timing metadata
            if config.metadata and isinstance(config.metadata, dict):
                video_duration = config.metadata.get('duration')
                video_start_time = config.metadata.get('video_start_time')

            # CRITICAL FIX #1: Get TOTAL sequence duration for multi-video sessions
            if video_duration is None:
                try:
                    session_timing = self._get_session_timing_info(session_id)
                    if session_timing:
                        video_start_time = session_timing.get('video_start_timestamp')

                        # Check if this is a multi-video sequence
                        if 'sequence_id' in session_timing and session_timing['sequence_id']:
                            from models import TestSession, SequenceVideoResult, Video
                            db = SessionLocal()
                            try:
                                sequence_id = session_timing['sequence_id']

                                session_record = db.query(TestSession).filter(TestSession.id == session_id).first()
                                metadata_video_timing: Dict[str, Any] = {}
                                if session_record and session_record.sequence_metadata:
                                    raw_metadata = session_record.sequence_metadata
                                    if isinstance(raw_metadata, str):
                                        try:
                                            metadata = json.loads(raw_metadata)
                                        except json.JSONDecodeError:
                                            metadata = {}
                                    elif isinstance(raw_metadata, dict):
                                        metadata = dict(raw_metadata)
                                    else:
                                        metadata = {}
                                    metadata_video_timing = metadata.get("video_timing", {})

                                video_results = db.query(SequenceVideoResult).filter(
                                    SequenceVideoResult.video_sequence_id == sequence_id
                                ).all()

                                sequence_video_count = len(video_results)
                                video_start_candidates: List[float] = []
                                video_end_candidates: List[float] = []
                                total_duration = 0.0

                                video_map: Dict[str, Video] = {
                                    video.id: video for video in db.query(Video).filter(
                                        Video.id.in_([vr.video_id for vr in video_results])
                                    ).all()
                                }

                                for result in video_results:
                                    video_entry = video_map.get(result.video_id)
                                    meta_entry = metadata_video_timing.get(result.video_id, {})

                                    start_candidate = result.video_start_time or meta_entry.get("started_at")
                                    if start_candidate is not None:
                                        video_start_candidates.append(start_candidate)

                                    duration_seconds = None
                                    if result.actual_duration_ms:
                                        duration_seconds = result.actual_duration_ms / 1000.0
                                    elif meta_entry.get("actual_duration") is not None:
                                        duration_seconds = meta_entry.get("actual_duration")
                                    elif video_entry and video_entry.duration:
                                        duration_seconds = float(video_entry.duration)

                                    if duration_seconds is not None:
                                        total_duration += duration_seconds

                                    if start_candidate is not None and duration_seconds is not None:
                                        video_end_candidates.append(start_candidate + duration_seconds)

                                if video_start_candidates and video_end_candidates:
                                    sequence_start = min(video_start_candidates)
                                    sequence_end = max(video_end_candidates)
                                    video_start_time = sequence_start
                                    video_duration = max(sequence_end - sequence_start, 0.0)
                                    logger.info(
                                        f"🎬 Multi-video sequence: {sequence_video_count} videos, "
                                        f"start={sequence_start:.3f}, end={sequence_end:.3f}, "
                                        f"duration={video_duration:.2f}s"
                                    )
                                elif total_duration > 0 and video_start_time is not None:
                                    video_duration = total_duration
                                    logger.info(
                                        f"🎬 Multi-video sequence: {sequence_video_count} videos, "
                                        f"aggregated duration {video_duration:.2f}s (start time fallback)"
                                    )
                                else:
                                    logger.warning(
                                        f"⚠️ Multi-video sequence {sequence_id} missing detailed timing; "
                                        f"unable to compute precise stop window"
                                    )

                                if sequence_video_count > 1:
                                    multi_video_buffer = max(multi_video_buffer, 2.0 * sequence_video_count)
                            finally:
                                db.close()
                        elif 'video_duration' in session_timing:
                            # Single video fallback
                            video_duration = session_timing['video_duration']
                            logger.info(f"🎬 Single video: duration {video_duration:.2f}s")
                except Exception as timing_error:
                    logger.warning(f"Failed to get video timing: {timing_error}")

            # CRITICAL FIX: Normalize video_start_time to float epoch timestamp for window validation
            video_start_timestamp_float = None
            if video_start_time is not None:
                if hasattr(video_start_time, 'timestamp'):
                    video_start_timestamp_float = video_start_time.timestamp()
                elif isinstance(video_start_time, (int, float)):
                    video_start_timestamp_float = video_start_time
                else:
                    logger.warning(f"Unexpected video_start_time type: {type(video_start_time)}")

            # Calculate stop time if we have duration
            stop_buffer_seconds = multi_video_buffer  # default buffer (extended for multi-video)
            if video_duration and video_start_timestamp_float:
                stop_time_with_buffer = video_start_timestamp_float + video_duration + stop_buffer_seconds
                logger.info(
                    f"🕐 Window validation enabled: "
                    f"video_start={video_start_timestamp_float:.6f}, "
                    f"video_end={video_start_timestamp_float + video_duration:.6f}, "
                    f"monitor_stop={stop_time_with_buffer:.6f}"
                )

            # CRITICAL FIX: Initialize detection window validation counters
            skipped_early_detections = 0
            skipped_late_detections = 0
            total_valid_detections = 0

            logger.info(f"🔍 Starting monitoring loop for session {session_id}")
            logger.info(f"📊 Poll interval: {poll_interval*1000:.1f}ms")

            while not stop_event.is_set():
                try:
                    # CRITICAL FIX: Check if we've exceeded video duration + buffer
                    if stop_time_with_buffer:
                        current_timestamp = time.time()
                        if current_timestamp > stop_time_with_buffer:
                            logger.info(f"⏹️ Auto-stopping: video ended, buffer expired (current: {current_timestamp:.6f}, stop: {stop_time_with_buffer:.6f})")
                            # Notify orchestrator that video has ended
                            try:
                                from services.video_sequence_orchestrator import get_video_sequence_orchestrator
                                orchestrator = get_video_sequence_orchestrator()
                                db = next(get_db())
                                try:
                                    # Get sequence_id from session
                                    from models import TestSession
                                    session = db.query(TestSession).filter_by(id=session_id).first()
                                    if session and session.sequence_id:
                                        orchestrator.notify_video_ended(
                                            sequence_id=session.sequence_id,
                                            video_id=session.video_id,
                                            actual_end_timestamp=current_timestamp,
                                            db=db
                                        )
                                        logger.info(f"✅ Notified orchestrator that video ended")
                                finally:
                                    db.close()
                            except Exception as notify_error:
                                logger.warning(f"Failed to notify orchestrator: {notify_error}")

                            # Stop monitoring
                            break

                    # Read voltages from all monitored channels using real hardware
                    channel_readings = {}
                    for channel in config.channels:
                        try:
                            # FIXED: Use shared connection manager to prevent device conflicts
                            if self.connection_manager:
                                try:
                                    # Ensure LabJack is connected through the shared manager
                                    if not self.connection_manager.is_connected():
                                        self.connection_manager.connect()

                                    # Use shared connection manager for voltage reading
                                    voltage = self.connection_manager.read_voltage(channel)
                                    if voltage is not None:
                                        logger.debug(f"📊 {channel}: {voltage:.4f}V (threshold: {config.voltage_threshold}V)")
                                    else:
                                        voltage = 0.0

                                except Exception as cm_error:
                                    logger.error(f"Connection manager read failed for {channel}: {cm_error}")
                                    voltage = 0.0
                            else:
                                logger.warning("Connection manager not available")
                                voltage = 0.0

                        except Exception as e:
                            logger.error(f"Error reading voltage from {channel}: {e}")
                            voltage = 0.0
                        channel_readings[channel] = voltage

                    # Check for detection events
                    current_time = datetime.now()
                    current_epoch_time = current_time.timestamp()

                    for channel, voltage in channel_readings.items():
                        if config.continuous_mode:
                            lower_bound = config.continuous_lower_bound
                            if lower_bound is None:
                                lower_bound = config.voltage_threshold
                            upper_bound = config.continuous_upper_bound
                            voltage_in_range = voltage >= lower_bound and (upper_bound is None or voltage <= upper_bound)
                        else:
                            voltage_in_range = voltage >= config.voltage_threshold

                        if voltage_in_range:
                            if config.continuous_mode:
                                logger.debug(
                                    f"📈 CONTINUOUS DETECTION RANGE {channel}: {voltage:.3f}V "
                                    f"(bounds: {lower_bound:.3f}V - {upper_bound if upper_bound is not None else '∞'}V)"
                                )
                            else:
                                logger.info(f"🎯 DETECTION! {channel}: {voltage:.3f}V > {config.voltage_threshold}V threshold")

                            # CRITICAL FIX: WINDOW VALIDATION - Only save if within video playback window
                            if not self._is_detection_within_video_window(
                                session_id, current_epoch_time, video_start_timestamp_float, stop_time_with_buffer
                            ):
                                # Count skipped detections
                                if video_start_timestamp_float and current_epoch_time < video_start_timestamp_float:
                                    skipped_early_detections += 1
                                    logger.debug(
                                        f"⏭️ Skipping early detection {(current_epoch_time - video_start_timestamp_float):.3f}s "
                                        f"before video start (total skipped early: {skipped_early_detections})"
                                    )
                                else:
                                    skipped_late_detections += 1
                                    logger.debug(
                                        f"⏭️ Skipping late detection after video end "
                                        f"(total skipped late: {skipped_late_detections})"
                                    )
                                continue  # Skip this detection - outside video window

                            if self._should_record_detection(session_id, channel, current_time, config):
                                event = self._create_detection_event(
                                    session_id, channel, voltage, config.voltage_threshold, current_time
                                )
                                if config.continuous_mode:
                                    event.metadata = event.metadata or {}
                                    event.metadata.update({
                                        'continuous_mode': True,
                                        'continuous_interval_ms': config.continuous_interval_ms,
                                        'continuous_lower_bound': lower_bound,
                                        'continuous_upper_bound': upper_bound
                                    })
                                self._record_detection_event(session_id, event)
                                total_valid_detections += 1
                                logger.info(
                                    f"📝 Detection event recorded: {voltage:.3f}V at {current_time} "
                                    f"(valid detections: {total_valid_detections})"
                                )
                            else:
                                logger.debug(f"🔄 Detection skipped (debounce): {voltage:.3f}V")

                    # Sleep until next poll
                    time.sleep(poll_interval)

                except Exception as e:
                    logger.error(f"Error in monitoring loop for session {session_id}: {e}")
                    time.sleep(0.1)  # Brief pause before retry

        except Exception as e:
            logger.error(f"Fatal error in monitoring loop for session {session_id}: {e}")
            self.detection_status[session_id] = DetectionStatus.ERROR

        finally:
            if session_id in self.detection_status:
                self.detection_status[session_id] = DetectionStatus.STOPPED

            # CRITICAL FIX: Log window validation statistics
            logger.info(f"🏁 Monitoring loop ended for session {session_id}")
            logger.info(
                f"📊 Detection Window Stats: "
                f"Valid={total_valid_detections}, "
                f"Skipped Early={skipped_early_detections}, "
                f"Skipped Late={skipped_late_detections}, "
                f"Total Captured={total_valid_detections + skipped_early_detections + skipped_late_detections}"
            )
    
    def _should_record_detection(self, session_id: str, channel: str, current_time: datetime, config: DetectionConfig) -> bool:
        """Check if detection should be recorded based on debounce/interval logic"""
        if config.continuous_mode:
            last_emit = self.last_continuous_emit_times.get(session_id, {}).get(channel, datetime.min)
            interval_delta = timedelta(milliseconds=max(1, config.continuous_interval_ms))
            if current_time - last_emit < interval_delta:
                return False
            return True

        last_detection = self.last_detection_times.get(session_id, {}).get(channel, datetime.min)

        debounce_delta = timedelta(milliseconds=config.debounce_ms)
        if current_time - last_detection < debounce_delta:
            return False

        return True

    def _is_detection_within_video_window(
        self,
        session_id: str,
        detection_timestamp: float,
        video_start_time: Optional[float],
        video_end_time: Optional[float]
    ) -> bool:
        """
        CRITICAL FIX: Validate detection is within video playback window.

        This prevents capturing detections that occur before video starts or after it ends,
        which would pollute the dataset with invalid early/late detections.

        Args:
            session_id: Test session ID
            detection_timestamp: Detection epoch timestamp (seconds)
            video_start_time: Video start epoch timestamp (seconds, can be None)
            video_end_time: Video end epoch timestamp with buffer (seconds, can be None)

        Returns:
            True if detection is within valid window, False to skip
        """
        # Use centralized grace period configuration (2000ms)
        # Hardware LabJack can trigger 0-2 seconds before 'playing' event

        # If no timing constraints, allow all detections (fallback)
        if video_start_time is None and video_end_time is None:
            logger.debug(f"No video timing constraints for session {session_id}, accepting all detections")
            return True

        # Check early detection (before video start)
        if video_start_time is not None:
            # Use centralized grace period (2000ms = 2.0 seconds)
            grace_period_seconds = GRACE_PERIOD_SECONDS
            earliest_valid_time = video_start_time - grace_period_seconds

            if detection_timestamp < earliest_valid_time:
                time_before_start = video_start_time - detection_timestamp
                logger.debug(
                    f"❌ Detection {time_before_start:.3f}s before video start "
                    f"(detection={detection_timestamp:.6f}, video_start={video_start_time:.6f}, "
                    f"grace={grace_period_seconds:.3f}s [centralized config])"
                )
                return False

        # Check late detection (after video end + buffer)
        if video_end_time is not None:
            if detection_timestamp > video_end_time:
                time_after_end = detection_timestamp - video_end_time
                logger.debug(
                    f"❌ Detection {time_after_end:.3f}s after video end+buffer "
                    f"(detection={detection_timestamp:.6f}, video_end={video_end_time:.6f})"
                )
                return False

        # Detection is within valid window
        if video_start_time:
            relative_time = detection_timestamp - video_start_time
            logger.debug(
                f"✅ Detection within window at +{relative_time:.3f}s from video start "
                f"(detection={detection_timestamp:.6f}, video_start={video_start_time:.6f})"
            )

        return True
    
    def calculate_calibration_offset(self, session_id: str) -> float:
        """Calculate calibration offset from actual detection timing data.

        Returns:
            Calibration offset in milliseconds
        """
        import statistics

        # Get first 10 detections to calculate baseline offset
        if DATABASE_AVAILABLE:
            try:
                from models import DetectionEvent as DBDetectionEvent
                db = SessionLocal()
                try:
                    detections = db.query(DBDetectionEvent).filter(
                        DBDetectionEvent.test_session_id == session_id
                    ).order_by(DBDetectionEvent.labjack_timestamp).limit(10).all()

                    if not detections:
                        logger.warning("No detections available for calibration - using zero offset")
                        return 0.0

                    # Calculate average offset from ground truth
                    offsets = []
                    for detection in detections:
                        if hasattr(detection, 'matched_ground_truth_id') and detection.matched_ground_truth_id:
                            # Would need to fetch matched GT, simplified here
                            pass

                    if not offsets:
                        logger.warning("No matched detections for calibration - using zero offset")
                        return 0.0

                    # Use median to avoid outliers
                    calibration_offset = statistics.median(offsets)
                    logger.info(f"Calculated calibration offset: {calibration_offset:.2f}ms")

                    return calibration_offset
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Failed to calculate calibration offset: {e}")
                return 0.0

        return 0.0

    def _create_detection_event(self, session_id: str, channel: str, voltage: float,
                              threshold: float, timestamp: datetime) -> DetectionEvent:
        """Create a new detection event with timing calibration"""
        event_id = str(uuid.uuid4())

        # Apply timing calibration if we have session timing data
        video_relative_timestamp = None
        actual_latency_ms = None

        try:
            # CRITICAL FIX: Disable calibration offset for multi-video sequences to avoid cross-video contamination
            session_info = self._get_session_timing_info(session_id)
            if session_info and session_info.get('sequence_id'):
                TIMING_CALIBRATION_OFFSET_MS = 0.0  # No calibration for sequences
                logger.info("Multi-video sequence detected - calibration disabled")
            else:
                # FIX: Calculate dynamic calibration offset from actual measurements (single video only)
                TIMING_CALIBRATION_OFFSET_MS = self.calculate_calibration_offset(session_id)

            if DATABASE_AVAILABLE:
                # Get session info from database to calculate video-relative timestamp
                if not session_info:
                    session_info = self._get_session_timing_info(session_id)

                if session_info and session_info.get('video_start_timestamp'):
                    video_start_time = session_info['video_start_timestamp']

                    # CRITICAL FIX: For multi-video sequences, use current video's start time from sequence_metadata
                    if session_info.get('sequence_id'):
                        try:
                            db = SessionLocal()
                            try:
                                from models import TestSession
                                session = db.query(TestSession).filter(TestSession.id == session_id).first()
                                if session and session.sequence_metadata:
                                    metadata = session.sequence_metadata
                                    if isinstance(metadata, str):
                                        import json
                                        metadata = json.loads(metadata)

                                    # CRITICAL: Use current_video_id from metadata, NOT session.video_id
                                    # session.video_id is the initial video, current_video_id tracks the active video
                                    current_video_id = metadata.get('current_video_id')

                                    if current_video_id:
                                        # Get current video's start time from video_timing
                                        video_timing = metadata.get('video_timing', {})
                                        current_video_timing = video_timing.get(current_video_id)

                                        if current_video_timing and 'started_at' in current_video_timing:
                                            video_start_time = current_video_timing['started_at']
                                            logger.info(f"🎯 Multi-video: Using video {current_video_id} start time: {video_start_time:.6f}")
                            finally:
                                db.close()
                        except Exception as meta_error:
                            logger.warning(f"Failed to get current video timing from sequence_metadata: {meta_error}")

                    # Convert datetime to timestamp if needed
                    if hasattr(video_start_time, 'timestamp'):
                        reference_time = video_start_time.timestamp()
                    elif isinstance(video_start_time, (int, float)):
                        reference_time = video_start_time
                    else:
                        reference_time = time.time()

                    # Apply timing calibration offset (will be 0.0 for multi-video sequences)
                    calibration_offset_seconds = TIMING_CALIBRATION_OFFSET_MS / 1000.0
                    detection_timestamp = timestamp.timestamp() + calibration_offset_seconds

                    # Calculate video-relative timestamp with calibration
                    video_relative_timestamp = max(0.0, detection_timestamp - reference_time)

                    # UNIFIED LATENCY CALCULATION
                    # Actual latency is derived during ground truth matching, so leave unset here.
                    actual_latency_ms = None

                    logger.info(
                        f"🎯 CALIBRATED detection timing: {video_relative_timestamp:.3f}s "
                        "(latency will be assigned during ground truth matching)"
                    )
        except Exception as e:
            logger.warning(f"Failed to apply timing calibration for session {session_id}: {e}")
        
        return DetectionEvent(
            id=event_id,
            session_id=session_id,
            timestamp=timestamp,
            channel=channel,
            voltage=voltage,
            threshold=threshold,
            detected=True,
            is_duplicate=False,
            metadata={
                'labjack_mode': self.labjack_service.mode.value if self.labjack_service else 'unknown',
                'sample_method': 'single_read',
                'timing_calibration_applied': video_relative_timestamp is not None,
                'calibration_offset_ms': TIMING_CALIBRATION_OFFSET_MS if video_relative_timestamp is not None else None
            },
            video_relative_timestamp=video_relative_timestamp,
            actual_latency_ms=actual_latency_ms
        )
    
    def _record_detection_event(self, session_id: str, event: DetectionEvent):
        """Record detection event and notify callbacks"""
        config = self.active_sessions.get(session_id)

        with self.lock:
            # Store event
            if session_id not in self.detection_events:
                self.detection_events[session_id] = []
            
            self.detection_events[session_id].append(event)
            
            # Update last detection time
            if session_id not in self.last_detection_times:
                self.last_detection_times[session_id] = {}
            self.last_detection_times[session_id][event.channel] = event.timestamp
            if config and config.continuous_mode:
                if session_id not in self.last_continuous_emit_times:
                    self.last_continuous_emit_times[session_id] = {}
                self.last_continuous_emit_times[session_id][event.channel] = event.timestamp
            
            logger.info(f"🎯 Detection event: {event.channel} = {event.voltage:.3f}V @ {event.timestamp.isoformat()}")
        
        # Store in database (fixed async handling)
        if config and config.store_in_db and DATABASE_AVAILABLE:
            self._schedule_db_storage(event)
        
        # Notify callbacks
        self._notify_detection_callbacks(event)
        
        # Send WebSocket notification
        if config and config.enable_websocket:
            self._notify_websocket_callbacks(session_id, event)
    
    def _schedule_db_storage(self, event: DetectionEvent):
        """Schedule database storage from synchronous context"""
        # ✅ CRITICAL FIX #9: Use task queue instead of daemon threads
        try:
            # Add to queue for persistent storage
            if not hasattr(self, 'storage_queue'):
                self.storage_queue = queue.Queue()
                # Start worker thread if not already running
                if not hasattr(self, 'storage_worker_running'):
                    self.storage_worker_running = True
                    threading.Thread(
                        target=self._storage_worker,
                        daemon=False,  # Non-daemon to allow graceful shutdown
                        name="DetectionStorageWorker"
                    ).start()

            self.storage_queue.put(event)
            logger.debug(f"Queued detection event for storage: {event.id}")
        except Exception as e:
            logger.error(f"Failed to queue detection event: {e}")
    
    def _store_event_sync_wrapper(self, event: DetectionEvent):
        """Wrapper to run async database storage in new event loop"""
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._store_event_in_db(event))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Failed to store detection event in database (sync wrapper): {e}")
    
    async def _store_event_in_db(self, event: DetectionEvent):
        """Store detection event in database with full timing calibration"""
        try:
            if not DATABASE_AVAILABLE:
                logger.debug(f"Database not available, event not persisted: {event.id}")
                return

            # Store using production database models
            db = SessionLocal()
            try:
                from models import DetectionEvent as DBDetectionEvent, TestSession, SequenceVideoResult as SequenceVideoResultModel

                # ✅ CRITICAL FIX #1: Validate session exists before storage
                session = db.query(TestSession).filter(
                    TestSession.id == event.session_id
                ).first()

                if not session:
                    logger.error(f"❌ Session {event.session_id} not found - rejecting detection")
                    return False

                # ✅ PHASE 4 FIX: Database-backed video_id resolution (single source of truth)
                video_id = get_video_id_for_detection(
                    session_id=session.id,
                    detection_timestamp=event.timestamp,
                    db=db
                )

                if not video_id:
                    logger.warning(
                        f"⚠️ No video found for detection at timestamp {event.timestamp:.3f} "
                        f"in session {session.id}. Detection will be stored without video_id."
                    )

                # Validate video_id exists in database
                if video_id:
                    from models import Video
                    video_exists = db.query(Video).filter(Video.id == video_id).first()
                    if not video_exists:
                        logger.warning(f"Video {video_id} not found for detection event, clearing video_id")
                        video_id = None

                # ✅ PHASE 4 FIX: Get sequence_video_result_id using resolver
                sequence_id = session.sequence_id
                sequence_video_result_id = None

                if sequence_id and video_id:
                    sequence_video_result_id = get_sequence_video_result_id(
                        session_id=session.id,
                        video_id=video_id,
                        db=db
                    )
                    if sequence_video_result_id:
                        logger.debug(f"✅ Linked detection to sequence_video_result: {sequence_video_result_id}")
                    else:
                        logger.warning(f"⚠️ No SequenceVideoResult found for sequence={sequence_id}, video={video_id}")

                # ✅ VALIDATION: Log WARNING if critical fields are NULL
                missing_fields = []
                if not video_id:
                    missing_fields.append("video_id")
                if sequence_id and not sequence_video_result_id:
                    missing_fields.append("sequence_video_result_id")

                if missing_fields:
                    logger.warning(f"⚠️ Detection event {event.id} missing fields: {', '.join(missing_fields)}")
                    logger.warning(f"   Session: {session.id}, Video: {video_id}, Sequence: {sequence_id}")

                # Create database record with complete timing calibration data
                # ✅ FIXED: Use correct column names from DetectionEvent model
                db_event = DBDetectionEvent(
                    id=event.id,
                    test_session_id=session.id,  # ✅ Use validated session ID
                    video_id=video_id,  # ✅ Always include video_id
                    sequence_id=sequence_id,  # ✅ AGENT 2: Add sequence_id
                    sequence_video_result_id=sequence_video_result_id,  # ✅ AGENT 2: Add sequence_video_result_id
                    timestamp=event.timestamp.timestamp() if hasattr(event.timestamp, 'timestamp') else event.timestamp,
                    detection_channel=event.channel,  # ✅ Correct field name
                    labjack_voltage=event.voltage,  # ✅ Correct
                    voltage_level=event.voltage,  # ✅ Trigger voltage level
                    latency_threshold_ms=event.threshold,  # ✅ Correct field name
                    # CRITICAL: Include timing calibration fields
                    video_relative_timestamp=event.video_relative_timestamp,
                    actual_latency_ms=event.actual_latency_ms,
                    frame_number=0,  # FIXED: Frame correlation computed later
                    video_frame_number=0,  # FIXED: Added for consistency
                    # Enhanced metadata with calibration details
                    detection_metadata={  # ✅ Correct: JSON field, not string
                        **(event.metadata or {}),
                        'timing_calibration_applied': event.video_relative_timestamp is not None,
                        'calibration_offset_ms': 166.0 if event.video_relative_timestamp is not None else None,
                        'detection_pipeline': 'labjack_detection_service',
                        'storage_timestamp': datetime.utcnow().isoformat(),
                        'detected': event.detected,
                        'is_duplicate': event.is_duplicate,
                        'sequence_id': sequence_id,  # Add to metadata for debugging
                        'sequence_video_result_id': sequence_video_result_id
                    }
                )

                db.add(db_event)
                db.commit()
                logger.info(f"✅ PRODUCTION: Stored detection event with timing calibration: {event.id} for session={session.id}, video={video_id}")

                # ✅ NEW: Emit detection event via WebSocket after successful storage
                if self._websocket_emit_fn:
                    try:
                        detection_data = {
                            'id': event.id,
                            'session_id': event.session_id,
                            'video_id': video_id,
                            'timestamp': event.timestamp.isoformat() if hasattr(event.timestamp, 'isoformat') else str(event.timestamp),
                            'video_relative_timestamp': event.video_relative_timestamp,
                            'actual_latency_ms': event.actual_latency_ms,
                            'voltage': event.voltage,
                            'channel': event.channel,
                            'detected': event.detected,
                            'metadata': event.metadata
                        }
                        # Call async emit function
                        await self._websocket_emit_fn(detection_data, event.session_id)
                        logger.debug(f"🔔 WebSocket emission triggered for detection {event.id}")
                    except Exception as ws_error:
                        logger.warning(f"WebSocket emission failed: {ws_error}")

                return True

            except Exception as model_error:
                logger.error(f"❌ Model creation failed: {model_error}")
                db.rollback()
                return False
            finally:
                db.close()
                    
        except Exception as e:
            logger.error(f"Failed to store detection event in database: {e}")
            logger.error(f"Event data: {event.to_dict()}")
    
    def _store_event_fallback(self, db_session, event: DetectionEvent):
        """Fallback storage method using direct SQL"""
        try:
            from sqlalchemy import text
            
            # ✅ FIXED: Use correct column names from DetectionEvent model
            sql = text("""
                INSERT INTO detection_events (
                    id, test_session_id, timestamp, detection_channel, labjack_voltage,
                    voltage_level, latency_threshold_ms, video_relative_timestamp,
                    actual_latency_ms, detection_metadata
                ) VALUES (
                    :id, :test_session_id, :timestamp, :channel, :voltage,
                    :voltage_level, :threshold, :video_relative_timestamp,
                    :actual_latency_ms, :metadata
                )
            """)

            db_session.execute(sql, {
                'id': event.id,
                'test_session_id': event.session_id,
                'timestamp': event.timestamp.timestamp() if hasattr(event.timestamp, 'timestamp') else event.timestamp,
                'channel': event.channel,
                'voltage': event.voltage,
                'voltage_level': event.voltage,
                'threshold': event.threshold,
                'video_relative_timestamp': event.video_relative_timestamp,
                'actual_latency_ms': event.actual_latency_ms,
                'metadata': json.dumps({
                    **(event.metadata or {}),
                    'detected': event.detected,
                    'is_duplicate': event.is_duplicate
                })
            })
            db_session.commit()
            logger.info(f"💾 FALLBACK: Stored detection event with timing calibration: {event.id}")
            
        except Exception as fallback_error:
            logger.error(f"Fallback storage also failed: {fallback_error}")
            db_session.rollback()
    
    def _get_session_timing_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session timing information from database for calibration and auto-stop"""
        try:
            if not DATABASE_AVAILABLE:
                return None

            # Use database session to query test_sessions table
            db = SessionLocal()
            try:
                from models import TestSession, Video
                session = db.query(TestSession).filter(TestSession.id == session_id).first()
                if session:
                    # Get video duration for auto-stop calculation
                    video_duration = None
                    if session.video_id:
                        video = db.query(Video).filter(Video.id == session.video_id).first()
                        if video and video.duration:
                            video_duration = video.duration

                    return {
                        'id': session.id,
                        'video_start_timestamp': session.video_start_timestamp,
                        'started_at': session.started_at,
                        'created_at': session.created_at,
                        'video_duration': video_duration,
                        'sequence_id': session.sequence_id  # CRITICAL: Needed for multi-video duration calculation
                    }
                return None
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to get session timing info for {session_id}: {e}")
            return None
    
    def _notify_detection_callbacks(self, event: DetectionEvent):
        """Notify detection callbacks"""
        for callback in self.detection_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in detection callback: {e}")
    
    def _notify_websocket_callbacks(self, session_id: str, event: DetectionEvent):
        """Send WebSocket notification"""
        message = {
            'type': 'detection_event',
            'session_id': session_id,
            'event': event.to_dict()
        }
        
        for callback in self.websocket_callbacks:
            try:
                callback(session_id, message)
            except Exception as e:
                logger.error(f"Error in WebSocket callback: {e}")
    
    def _cleanup_session_preserving_connection(self, session_id: str):
        """Clean up session resources while preserving hardware connection.
        
        CRITICAL FIX: This is the new connection-preserving cleanup method.
        """
        with self.lock:
            # Remove from active sessions
            self.active_sessions.pop(session_id, None)
            self.detection_status.pop(session_id, None)
            self.monitoring_threads.pop(session_id, None)
            self.stop_events.pop(session_id, None)
            
            # CRITICAL: DO NOT close hardware connection - preserve for other sessions
            # The connection manager handles the actual hardware connection lifecycle
            if self.connection_manager:
                remaining_count = len(self.active_sessions)
                logger.info(f"🔌 Connection preserved - {remaining_count} sessions remaining")
                
                # Only log connection status if no sessions remain
                if remaining_count == 0:
                    logger.info("🔌 LabJack connection idle but maintained for future sessions")
            
            # Keep detection events and last detection times for retrieval
            # These can be cleaned up separately if needed via cleanup_session_data()
    
    def _cleanup_session(self, session_id: str):
        """Legacy cleanup method - redirects to connection-preserving cleanup.
        
        DEPRECATED: Use _cleanup_session_preserving_connection() directly.
        """
        logger.debug(f"Using legacy cleanup for session {session_id} - preserving connection")
        self._cleanup_session_preserving_connection(session_id)
    
    def cleanup_session_data(self, session_id: str):
        """Clean up all data for a session"""
        with self.lock:
            self.detection_events.pop(session_id, None)
            self.last_detection_times.pop(session_id, None)
            self.last_continuous_emit_times.pop(session_id, None)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        with self.lock:
            total_events = sum(len(events) for events in self.detection_events.values())
            active_sessions = len([s for s in self.detection_status.values() 
                                 if s == DetectionStatus.MONITORING])
            
            return {
                'active_sessions': active_sessions,
                'total_sessions': len(self.active_sessions),
                'total_events': total_events,
                'labjack_connected': self.labjack_service.status.name if self.labjack_service else 'UNKNOWN',
                'labjack_mode': self.labjack_service.mode.value if self.labjack_service else 'unknown',
                'database_available': DATABASE_AVAILABLE
            }
    
    async def get_session_statistics_from_db(self, session_id: str) -> Dict[str, Any]:
        """Get detailed session statistics from database"""
        if not DATABASE_AVAILABLE:
            return {}

        db = SessionLocal()
        try:
            # Direct database query for session statistics
            from models import DetectionEvent as DBDetectionEvent
            events = db.query(DBDetectionEvent).filter(
                DBDetectionEvent.test_session_id == session_id
            ).all()

            return {
                'session_id': session_id,
                'total_events': len(events),
                'events': [event.to_dict() for event in events if hasattr(event, 'to_dict')]
            }
        except Exception as e:
            logger.error(f"Failed to get session statistics from database: {e}")
            return {}
        finally:
            db.close()
    
    async def cleanup_old_data(self, days_old: int = 7) -> int:
        """Clean up old detection data from database"""
        if not DATABASE_AVAILABLE:
            return 0
        
        db = SessionLocal()
        try:
            # Direct database cleanup
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            from models import DetectionEvent as DBDetectionEvent
            deleted_count = db.query(DBDetectionEvent).filter(
                DBDetectionEvent.timestamp < cutoff_date
            ).count()

            db.query(DBDetectionEvent).filter(
                DBDetectionEvent.timestamp < cutoff_date
            ).delete()

            db.commit()
            logger.info(f"🧹 Cleaned up {deleted_count} old detection events")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return 0
        finally:
            db.close()


# Global detection monitor instance
_detection_monitor: Optional[LabJackDetectionMonitor] = None


def get_detection_monitor() -> LabJackDetectionMonitor:
    """Get global detection monitor instance"""
    global _detection_monitor
    if _detection_monitor is None:
        _detection_monitor = LabJackDetectionMonitor()
    return _detection_monitor


# WebSocket integration function
def setup_websocket_integration(websocket_manager):
    """Setup WebSocket integration for detection events"""
    monitor = get_detection_monitor()
    
    async def websocket_callback(session_id: str, message: Dict[str, Any]):
        """Send detection event via WebSocket"""
        if websocket_manager:
            await websocket_manager.broadcast_to_session(session_id, message)
    
    monitor.add_websocket_callback(websocket_callback)
    logger.info("✅ WebSocket integration configured for detection monitoring")


# Export key classes and functions
__all__ = [
    "LabJackDetectionMonitor",
    "DetectionEvent",
    "DetectionConfig", 
    "DetectionStatus",
    "get_detection_monitor",
    "get_detection_service",
    "setup_websocket_integration"
]
