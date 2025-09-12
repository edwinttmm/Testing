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
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, asdict
from enum import Enum
import json
import queue

# Database imports
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
try:
    from database import get_db_session
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

# LabJack service integration
from services.labjack_service import get_labjack_service, LabJackService

# Database integration
try:
    from services.detection_database_integration import get_detection_db_service
    DATABASE_SERVICE_AVAILABLE = True
except ImportError:
    DATABASE_SERVICE_AVAILABLE = False
    logging.warning("Detection database service not available")

logger = logging.getLogger(__name__)


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
            'metadata': self.metadata or {}
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
        
        # Database service integration
        self.db_service = get_detection_db_service() if DATABASE_SERVICE_AVAILABLE else None
        
        # Monitoring state
        self.active_sessions: Dict[str, DetectionConfig] = {}
        self.detection_status: Dict[str, DetectionStatus] = {}
        self.monitoring_threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        
        # Detection data
        self.detection_events: Dict[str, List[DetectionEvent]] = {}
        self.last_detection_times: Dict[str, Dict[str, datetime]] = {}  # session_id -> channel -> timestamp
        
        # Callbacks and notifications
        self.detection_callbacks: List[Callable[[DetectionEvent], None]] = []
        self.websocket_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # Thread synchronization
        self.lock = threading.RLock()
        
        db_status = "✅ Connected" if self.db_service and self.db_service.database_available else "❌ Not available"
        logger.info(f"LabJack Detection Monitor initialized (Database: {db_status})")
    
    def add_detection_callback(self, callback: Callable[[DetectionEvent], None]):
        """Add callback for detection events"""
        with self.lock:
            self.detection_callbacks.append(callback)
    
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
            if self.db_service:
                asyncio.create_task(self.db_service.create_session(
                    session_id=session_id,
                    channels=channels,
                    voltage_threshold=voltage_threshold,
                    debounce_ms=debounce_ms,
                    sample_rate=sample_rate,
                    metadata=config.metadata
                ))
            
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
    
    def stop_monitoring(self, session_id: str) -> bool:
        """
        Stop detection monitoring for a session
        
        Args:
            session_id: Session identifier to stop
        
        Returns:
            bool: True if stopped successfully
        """
        with self.lock:
            if session_id not in self.active_sessions:
                logger.warning(f"No active monitoring for session {session_id}")
                return True
            
            self.detection_status[session_id] = DetectionStatus.STOPPING
            
            # Signal stop to monitoring thread
            if session_id in self.stop_events:
                self.stop_events[session_id].set()
            
            # Wait for thread to finish
            if session_id in self.monitoring_threads:
                thread = self.monitoring_threads[session_id]
                thread.join(timeout=5)
                if thread.is_alive():
                    logger.warning(f"Monitoring thread for session {session_id} did not stop gracefully")
            
            # End database session record
            if self.db_service:
                asyncio.create_task(self.db_service.end_session(session_id))
            
            # Clean up session state
            self._cleanup_session(session_id)
            
            logger.info(f"⏹️ Stopped detection monitoring for session {session_id}")
            return True
    
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
        if from_database and self.db_service:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    db_events = loop.run_until_complete(
                        self.db_service.get_session_events(session_id)
                    )
                    if db_events:
                        logger.debug(f"Retrieved {len(db_events)} events from database for session {session_id}")
                        return db_events
                finally:
                    loop.close()
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
                    # Read voltages from all monitored channels
                    channel_readings = {}
                    for channel in config.channels:
                        voltage = asyncio.run(self.labjack_service.read_single_voltage(channel))
                        channel_readings[channel] = voltage
                    
                    # Check for detection events
                    current_time = datetime.now()
                    
                    for channel, voltage in channel_readings.items():
                        if voltage >= config.voltage_threshold:
                            if self._should_record_detection(session_id, channel, current_time, config):
                                event = self._create_detection_event(
                                    session_id, channel, voltage, config.voltage_threshold, current_time
                                )
                                self._record_detection_event(session_id, event)
                    
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
        """Create a new detection event"""
        event_id = str(uuid.uuid4())
        
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
                'sample_method': 'single_read'
            }
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
        
        # Store in database (async)
        config = self.active_sessions.get(session_id)
        if config and config.store_in_db:
            asyncio.create_task(self._store_event_in_db(event))
        
        # Notify callbacks
        self._notify_detection_callbacks(event)
        
        # Send WebSocket notification
        if config and config.enable_websocket:
            self._notify_websocket_callbacks(session_id, event)
    
    async def _store_event_in_db(self, event: DetectionEvent):
        """Store detection event in database"""
        try:
            if self.db_service:
                success = await self.db_service.store_detection_event(event)
                if success:
                    logger.debug(f"💾 Stored detection event in database: {event.id}")
                else:
                    logger.warning(f"Failed to store detection event: {event.id}")
            else:
                logger.debug(f"Database service not available, event not persisted: {event.id}")
            
        except Exception as e:
            logger.error(f"Failed to store detection event in database: {e}")
    
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
    
    def _cleanup_session(self, session_id: str):
        """Clean up session resources"""
        with self.lock:
            # Remove from active sessions
            self.active_sessions.pop(session_id, None)
            self.detection_status.pop(session_id, None)
            self.monitoring_threads.pop(session_id, None)
            self.stop_events.pop(session_id, None)
            
            # Keep detection events and last detection times for retrieval
            # These can be cleaned up separately if needed
    
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
                'database_available': self.db_service.database_available if self.db_service else False
            }
    
    async def get_session_statistics_from_db(self, session_id: str) -> Dict[str, Any]:
        """Get detailed session statistics from database"""
        if not self.db_service:
            return {}
        
        try:
            return await self.db_service.get_session_statistics(session_id)
        except Exception as e:
            logger.error(f"Failed to get session statistics from database: {e}")
            return {}
    
    async def cleanup_old_data(self, days_old: int = 7) -> int:
        """Clean up old detection data from database"""
        if not self.db_service:
            return 0
        
        try:
            return await self.db_service.cleanup_old_sessions(days_old)
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
    "setup_websocket_integration"
]