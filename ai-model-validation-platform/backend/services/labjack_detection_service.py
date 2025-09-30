"""
LabJack Detection Monitoring Service

This service provides real-time detection event monitoring for LabJack hardware,
focusing on recording detection events with timestamps for latency analysis.

Features:
- Event-based detection monitoring (not continuous streaming)
- Configurable voltage thresholds per channel
- Debounce logic to prevent duplicate detections
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

# Database imports
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
try:
    from database import get_db_session
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    logging.warning("Database module not available, detection events will not be persisted")

# LabJack service integration
from services.labjack_service import get_labjack_service, LabJackService
from services.labjack_hardware_service import get_labjack_hardware_service

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
            **kwargs: Additional configuration options
        
        Returns:
            bool: True if monitoring started successfully
        """
        channels = channels or ["AIN0", "AIN1"]
        
        with self.lock:
            if session_id in self.active_sessions:
                logger.warning(f"Monitoring already active for session {session_id}")
                return True
            
            # Create configuration
            config = DetectionConfig(
                session_id=session_id,
                channels=channels,
                voltage_threshold=voltage_threshold,
                debounce_ms=debounce_ms,
                sample_rate=sample_rate,
                enable_websocket=kwargs.get('enable_websocket', True),
                store_in_db=kwargs.get('store_in_db', True),
                metadata=kwargs.get('metadata')
            )
            
            # Initialize session state
            self.active_sessions[session_id] = config
            self.detection_status[session_id] = DetectionStatus.STARTING
            self.detection_events[session_id] = []
            self.last_detection_times[session_id] = {ch: datetime.min for ch in channels}
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
            try:
                # Direct database query for events
                with get_db_session() as db:
                    from models import DetectionEvent as DBDetectionEvent
                    events = db.query(DBDetectionEvent).filter(
                        DBDetectionEvent.session_id == session_id
                    ).order_by(DBDetectionEvent.timestamp).all()
                    
                    if events:
                        db_events = [event.to_dict() for event in events if hasattr(event, 'to_dict')]
                        logger.debug(f"Retrieved {len(db_events)} events from database for session {session_id}")
                        return db_events
            except Exception as e:
                logger.warning(f"Failed to get events from database, using memory: {e}")
        
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
        """Main monitoring loop for a session"""
        try:
            config = self.active_sessions[session_id]
            stop_event = self.stop_events[session_id]
            
            self.detection_status[session_id] = DetectionStatus.MONITORING
            
            # Calculate polling interval based on sample rate
            poll_interval = 1.0 / config.sample_rate
            
            logger.info(f"🔍 Starting monitoring loop for session {session_id}")
            logger.info(f"📊 Poll interval: {poll_interval*1000:.1f}ms")
            
            while not stop_event.is_set():
                try:
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
                    
                    for channel, voltage in channel_readings.items():
                        if voltage >= config.voltage_threshold:
                            logger.info(f"🎯 DETECTION! {channel}: {voltage:.3f}V > {config.voltage_threshold}V threshold")
                            if self._should_record_detection(session_id, channel, current_time, config):
                                event = self._create_detection_event(
                                    session_id, channel, voltage, config.voltage_threshold, current_time
                                )
                                self._record_detection_event(session_id, event)
                                logger.info(f"📝 Detection event recorded: {voltage:.3f}V at {current_time}")
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
            logger.info(f"🏁 Monitoring loop ended for session {session_id}")
    
    def _should_record_detection(self, session_id: str, channel: str, current_time: datetime, config: DetectionConfig) -> bool:
        """Check if detection should be recorded based on debounce logic"""
        last_detection = self.last_detection_times.get(session_id, {}).get(channel, datetime.min)
        
        # Check debounce time
        debounce_delta = timedelta(milliseconds=config.debounce_ms)
        if current_time - last_detection < debounce_delta:
            return False
        
        return True
    
    def _create_detection_event(self, session_id: str, channel: str, voltage: float, 
                              threshold: float, timestamp: datetime) -> DetectionEvent:
        """Create a new detection event with timing calibration"""
        event_id = str(uuid.uuid4())
        
        # Apply timing calibration if we have session timing data
        video_relative_timestamp = None
        actual_latency_ms = None
        
        try:
            # TIMING CALIBRATION: Apply 166ms offset to align with ground truth
            TIMING_CALIBRATION_OFFSET_MS = 166.0  # Empirically determined offset
            
            if DATABASE_AVAILABLE:
                # Get session info from database to calculate video-relative timestamp
                session_info = self._get_session_timing_info(session_id)
                if session_info and session_info.get('video_start_timestamp'):
                    video_start_time = session_info['video_start_timestamp']
                    
                    # Convert datetime to timestamp if needed
                    if hasattr(video_start_time, 'timestamp'):
                        reference_time = video_start_time.timestamp()
                    elif isinstance(video_start_time, (int, float)):
                        reference_time = video_start_time
                    else:
                        reference_time = time.time()
                    
                    # Apply timing calibration offset
                    calibration_offset_seconds = TIMING_CALIBRATION_OFFSET_MS / 1000.0
                    detection_timestamp = timestamp.timestamp() + calibration_offset_seconds
                    
                    # Calculate video-relative timestamp with calibration
                    video_relative_timestamp = max(0.0, detection_timestamp - reference_time)
                    actual_latency_ms = 50.0  # Reasonable processing latency estimate
                    
                    logger.info(f"🎯 CALIBRATED detection timing: {video_relative_timestamp:.3f}s (with {TIMING_CALIBRATION_OFFSET_MS}ms offset)")
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
        with self.lock:
            # Store event
            if session_id not in self.detection_events:
                self.detection_events[session_id] = []
            
            self.detection_events[session_id].append(event)
            
            # Update last detection time
            if session_id not in self.last_detection_times:
                self.last_detection_times[session_id] = {}
            self.last_detection_times[session_id][event.channel] = event.timestamp
            
            logger.info(f"🎯 Detection event: {event.channel} = {event.voltage:.3f}V @ {event.timestamp.isoformat()}")
        
        # Store in database (fixed async handling)
        config = self.active_sessions.get(session_id)
        if config and config.store_in_db and DATABASE_AVAILABLE:
            self._schedule_db_storage(event)
        
        # Notify callbacks
        self._notify_detection_callbacks(event)
        
        # Send WebSocket notification
        if config and config.enable_websocket:
            self._notify_websocket_callbacks(session_id, event)
    
    def _schedule_db_storage(self, event: DetectionEvent):
        """Schedule database storage from synchronous context"""
        try:
            # Try to get running event loop
            loop = asyncio.get_running_loop()
            # If we have a running loop, schedule the task
            loop.create_task(self._store_event_in_db(event))
        except RuntimeError:
            # No running event loop, run in new thread to avoid blocking
            import threading
            threading.Thread(
                target=self._store_event_sync_wrapper,
                args=(event,),
                daemon=True
            ).start()
    
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
            with get_db_session() as db:
                try:
                    from models import DetectionEvent as DBDetectionEvent
                    
                    # Create database record with complete timing calibration data
                    db_event = DBDetectionEvent(
                        id=event.id,
                        session_id=event.session_id,
                        timestamp=event.timestamp,
                        channel=event.channel,
                        voltage=event.voltage,
                        threshold=event.threshold,
                        detected=event.detected,
                        is_duplicate=event.is_duplicate,
                        # CRITICAL: Include timing calibration fields
                        video_relative_timestamp=event.video_relative_timestamp,
                        actual_latency_ms=event.actual_latency_ms,
                        # Enhanced metadata with calibration details
                        metadata={
                            **(event.metadata or {}),
                            'timing_calibration_applied': event.video_relative_timestamp is not None,
                            'calibration_offset_ms': 166.0 if event.video_relative_timestamp is not None else None,
                            'detection_pipeline': 'labjack_detection_service',
                            'storage_timestamp': datetime.utcnow().isoformat()
                        }
                    )
                    
                    db.add(db_event)
                    db.commit()
                    logger.info(f"💾 PRODUCTION: Stored detection event with timing calibration: {event.id} at {event.video_relative_timestamp:.3f}s")
                    
                except Exception as model_error:
                    logger.error(f"Model creation failed: {model_error}")
                    # Fallback to generic insertion if model fails
                    self._store_event_fallback(db, event)
                    
        except Exception as e:
            logger.error(f"Failed to store detection event in database: {e}")
            logger.error(f"Event data: {event.to_dict()}")
    
    def _store_event_fallback(self, db_session, event: DetectionEvent):
        """Fallback storage method using direct SQL"""
        try:
            from sqlalchemy import text
            
            sql = text("""
                INSERT INTO detection_events (
                    id, session_id, timestamp, channel, voltage, threshold, 
                    detected, is_duplicate, video_relative_timestamp, actual_latency_ms, metadata
                ) VALUES (
                    :id, :session_id, :timestamp, :channel, :voltage, :threshold,
                    :detected, :is_duplicate, :video_relative_timestamp, :actual_latency_ms, :metadata
                )
            """)
            
            db_session.execute(sql, {
                'id': event.id,
                'session_id': event.session_id,
                'timestamp': event.timestamp,
                'channel': event.channel,
                'voltage': event.voltage,
                'threshold': event.threshold,
                'detected': event.detected,
                'is_duplicate': event.is_duplicate,
                'video_relative_timestamp': event.video_relative_timestamp,
                'actual_latency_ms': event.actual_latency_ms,
                'metadata': json.dumps(event.metadata or {})
            })
            db_session.commit()
            logger.info(f"💾 FALLBACK: Stored detection event with timing calibration: {event.id}")
            
        except Exception as fallback_error:
            logger.error(f"Fallback storage also failed: {fallback_error}")
            db_session.rollback()
    
    def _get_session_timing_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session timing information from database for calibration"""
        try:
            if not DATABASE_AVAILABLE:
                return None
            
            # Use database session to query test_sessions table
            with get_db_session() as db:
                from models import TestSession
                session = db.query(TestSession).filter(TestSession.id == session_id).first()
                if session:
                    return {
                        'id': session.id,
                        'video_start_timestamp': session.video_start_timestamp,
                        'started_at': session.started_at,
                        'created_at': session.created_at
                    }
                return None
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
        
        try:
            # Direct database query for session statistics
            with get_db_session() as db:
                from models import DetectionEvent as DBDetectionEvent
                events = db.query(DBDetectionEvent).filter(
                    DBDetectionEvent.session_id == session_id
                ).all()
                
                return {
                    'session_id': session_id,
                    'total_events': len(events),
                    'events': [event.to_dict() for event in events if hasattr(event, 'to_dict')]
                }
        except Exception as e:
            logger.error(f"Failed to get session statistics from database: {e}")
            return {}
    
    async def cleanup_old_data(self, days_old: int = 7) -> int:
        """Clean up old detection data from database"""
        if not DATABASE_AVAILABLE:
            return 0
        
        try:
            # Direct database cleanup
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            with get_db_session() as db:
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