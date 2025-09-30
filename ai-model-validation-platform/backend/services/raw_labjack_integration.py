"""
Raw LabJack Integration Service

This service provides seamless integration between the raw LabJack logging system
and the existing detection event system, ensuring compatibility and data flow.

Key Features:
- Bridge between raw logging and detection systems
- Real-time detection threshold monitoring
- Automatic session coordination
- Performance optimization for concurrent operations
- Error recovery and resilience mechanisms
"""

import asyncio
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import uuid

# Database imports
from sqlalchemy.orm import Session
from database import get_db
from models import TestSession, DetectionEvent

# Service imports
from services.raw_labjack_logger import get_raw_labjack_logger, RawLabJackLogger
from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor, DedicatedLabJackMonitor
from services.labjack_detection_service import get_detection_service, LabJackDetectionMonitor
from services.raw_labjack_compression import CompressionAlgorithm

logger = logging.getLogger(__name__)


@dataclass
class IntegrationConfig:
    """Configuration for raw LabJack integration"""
    enable_detection_callbacks: bool = True
    detection_threshold_volts: float = 2.5
    debounce_time_ms: int = 50
    auto_session_coordination: bool = True
    performance_monitoring: bool = True
    error_recovery_enabled: bool = True


@dataclass
class SessionMapping:
    """Mapping between different session types"""
    raw_session_id: str
    test_session_id: Optional[str]
    hil_session_active: bool
    detection_session_active: bool
    created_at: datetime
    last_activity: datetime


class RawLabJackIntegrationService:
    """
    Integration service for coordinating raw LabJack logging with detection systems
    
    This service acts as a bridge between the high-frequency raw data logging
    and the existing detection event processing systems.
    """
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        self.config = config or IntegrationConfig()
        
        # Service references
        self.raw_logger = get_raw_labjack_logger()
        self.dedicated_monitor = get_dedicated_labjack_monitor()
        self.detection_service = get_detection_service()
        
        # Session coordination
        self.session_mappings: Dict[str, SessionMapping] = {}
        self.active_integrations: Dict[str, Dict[str, Any]] = {}
        
        # Performance tracking
        self.detection_callbacks_count = 0
        self.integration_errors = 0
        self.last_error_time: Optional[datetime] = None
        
        # Threading
        self.lock = threading.RLock()
        self.monitoring_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()
        
        # Start monitoring if enabled
        if self.config.performance_monitoring:
            self._start_monitoring()
        
        logger.info("Raw LabJack integration service initialized")
    
    async def start_integrated_session(
        self,
        session_name: str,
        test_session_id: str,
        channels: List[str],
        sample_rate: int = 1000,
        video_config: Optional[Dict[str, Any]] = None,
        raw_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Start integrated session with both raw logging and detection monitoring
        
        Args:
            session_name: Unique session name
            test_session_id: Test session ID for coordination
            channels: LabJack channels to monitor
            sample_rate: Sampling rate for raw logging
            video_config: Video timing configuration for HIL
            raw_config: Raw logging configuration options
            
        Returns:
            Dictionary with session IDs for different services
        """
        try:
            with self.lock:
                # Validate test session exists
                db = next(get_db())
                try:
                    test_session = db.query(TestSession).filter_by(id=test_session_id).first()
                    if not test_session:
                        raise ValueError(f"Test session not found: {test_session_id}")
                finally:
                    db.close()
                
                # Prepare configurations
                raw_logging_config = {
                    'channels': channels,
                    'sample_rate': sample_rate,
                    'compression_algorithm': CompressionAlgorithm.ADAPTIVE,
                    'detection_threshold': self.config.detection_threshold_volts,
                    **(raw_config or {})
                }
                
                video_timing_config = {
                    'channels': channels,
                    'voltage_threshold': self.config.detection_threshold_volts,
                    'debounce_ms': self.config.debounce_time_ms,
                    'sample_rate': 10,  # Lower rate for detection
                    'enable_websocket': True,
                    **(video_config or {})
                }
                
                # Start raw logging session
                raw_session_id = await self.raw_logger.start_session(
                    session_name=f"RAW_{session_name}",
                    test_session_id=test_session_id,
                    **raw_logging_config
                )
                
                if not raw_session_id:
                    raise RuntimeError("Failed to start raw logging session")
                
                # Start HIL monitoring session if video config provided
                hil_session_active = False
                if video_config:
                    try:
                        hil_success = self.dedicated_monitor.start_monitoring_with_video_sync(
                            test_session_id, video_timing_config
                        )
                        hil_session_active = hil_success
                        
                        if hil_success:
                            logger.info(f"✅ HIL monitoring started for session {test_session_id}")
                        else:
                            logger.warning(f"⚠️ HIL monitoring failed for session {test_session_id}")
                    except Exception as e:
                        logger.error(f"HIL monitoring startup error: {e}")
                
                # Start basic detection monitoring
                detection_session_active = False
                try:
                    detection_success = self.detection_service.start_monitoring(
                        test_session_id,
                        channels=channels,
                        voltage_threshold=self.config.detection_threshold_volts,
                        debounce_ms=self.config.debounce_time_ms,
                        sample_rate=10,  # Standard detection rate
                        store_in_db=True,
                        enable_websocket=True
                    )
                    detection_session_active = detection_success
                    
                    if detection_success:
                        logger.info(f"✅ Detection monitoring started for session {test_session_id}")
                    else:
                        logger.warning(f"⚠️ Detection monitoring failed for session {test_session_id}")
                except Exception as e:
                    logger.error(f"Detection monitoring startup error: {e}")
                
                # Create session mapping
                session_mapping = SessionMapping(
                    raw_session_id=raw_session_id,
                    test_session_id=test_session_id,
                    hil_session_active=hil_session_active,
                    detection_session_active=detection_session_active,
                    created_at=datetime.now(timezone.utc),
                    last_activity=datetime.now(timezone.utc)
                )
                
                self.session_mappings[raw_session_id] = session_mapping
                
                # Setup detection callback integration
                if self.config.enable_detection_callbacks:
                    await self._setup_detection_callbacks(raw_session_id, test_session_id)
                
                # Store integration configuration
                self.active_integrations[raw_session_id] = {
                    'session_name': session_name,
                    'test_session_id': test_session_id,
                    'raw_config': raw_logging_config,
                    'video_config': video_timing_config,
                    'hil_active': hil_session_active,
                    'detection_active': detection_session_active,
                    'started_at': datetime.now(timezone.utc)
                }
                
                session_ids = {
                    'raw_session_id': raw_session_id,
                    'test_session_id': test_session_id,
                    'hil_session_active': str(hil_session_active),
                    'detection_session_active': str(detection_session_active)
                }
                
                logger.info(f"🚀 Integrated session started: {session_name}")
                logger.info(f"   Raw Session: {raw_session_id}")
                logger.info(f"   Test Session: {test_session_id}")
                logger.info(f"   HIL Active: {hil_session_active}")
                logger.info(f"   Detection Active: {detection_session_active}")
                
                return session_ids
                
        except Exception as e:
            logger.error(f"Failed to start integrated session: {e}")
            
            # Cleanup on failure
            if 'raw_session_id' in locals():
                try:
                    self.raw_logger.stop_session(raw_session_id)
                except:
                    pass
            
            raise
    
    async def stop_integrated_session(self, raw_session_id: str) -> Dict[str, Any]:
        """
        Stop integrated session and all associated monitoring
        
        Args:
            raw_session_id: Raw logging session ID
            
        Returns:
            Dictionary with stop results and statistics
        """
        try:
            with self.lock:
                # Get session mapping
                session_mapping = self.session_mappings.get(raw_session_id)
                if not session_mapping:
                    raise ValueError(f"Session mapping not found: {raw_session_id}")
                
                test_session_id = session_mapping.test_session_id
                
                # Stop raw logging
                raw_stats = self.raw_logger.stop_session(raw_session_id)
                
                # Stop HIL monitoring if active
                hil_stats = None
                if session_mapping.hil_session_active:
                    try:
                        hil_stats = self.dedicated_monitor.stop_monitoring(test_session_id)
                        logger.info(f"⏹️ HIL monitoring stopped for {test_session_id}")
                    except Exception as e:
                        logger.error(f"Error stopping HIL monitoring: {e}")
                
                # Stop detection monitoring if active
                detection_stats = None
                if session_mapping.detection_session_active:
                    try:
                        detection_success = self.detection_service.stop_monitoring(test_session_id)
                        detection_stats = {'success': detection_success}
                        logger.info(f"⏹️ Detection monitoring stopped for {test_session_id}")
                    except Exception as e:
                        logger.error(f"Error stopping detection monitoring: {e}")
                
                # Remove integration
                integration_config = self.active_integrations.pop(raw_session_id, {})
                session_mapping = self.session_mappings.pop(raw_session_id, None)
                
                # Compile results
                results = {
                    'raw_session_id': raw_session_id,
                    'test_session_id': test_session_id,
                    'raw_logging_stats': raw_stats,
                    'hil_stats': hil_stats,
                    'detection_stats': detection_stats,
                    'integration_duration_seconds': 0,
                    'callbacks_processed': self.detection_callbacks_count
                }
                
                # Calculate integration duration
                if integration_config.get('started_at'):
                    duration = datetime.now(timezone.utc) - integration_config['started_at']
                    results['integration_duration_seconds'] = duration.total_seconds()
                
                logger.info(f"🛑 Integrated session stopped: {raw_session_id}")
                
                return results
                
        except Exception as e:
            logger.error(f"Error stopping integrated session: {e}")
            raise
    
    async def _setup_detection_callbacks(self, raw_session_id: str, test_session_id: str) -> None:
        """Setup detection callbacks from raw logging to detection systems"""
        try:
            def detection_callback(detection_data: Dict[str, Any]) -> None:
                """Handle detection events from raw logging"""
                try:
                    # Update activity timestamp
                    if raw_session_id in self.session_mappings:
                        self.session_mappings[raw_session_id].last_activity = datetime.now(timezone.utc)
                    
                    self.detection_callbacks_count += 1
                    
                    # Convert raw detection to LabJack event format
                    voltage = detection_data.get('voltage', 0.0)
                    channel = detection_data.get('channel', 0)
                    timestamp = detection_data.get('timestamp', datetime.now(timezone.utc))
                    
                    # Create mock LabJack event for compatibility
                    class MockLabJackEvent:
                        def __init__(self, voltage: float, channel: int, timestamp: datetime):
                            self.voltage = voltage
                            self.channel = f"AIN{channel}"
                            self.timestamp = timestamp
                    
                    mock_event = MockLabJackEvent(voltage, channel, timestamp)
                    
                    # Forward to dedicated HIL monitor if active
                    session_mapping = self.session_mappings.get(raw_session_id)
                    if session_mapping and session_mapping.hil_session_active:
                        try:
                            self.dedicated_monitor._handle_detection_with_video_sync(
                                test_session_id, mock_event
                            )
                        except Exception as e:
                            logger.error(f"HIL callback forwarding error: {e}")
                            self.integration_errors += 1
                    
                    # Create detection event for database storage
                    if session_mapping and session_mapping.detection_session_active:
                        try:
                            self._create_detection_event(
                                test_session_id, 
                                detection_data, 
                                raw_session_id
                            )
                        except Exception as e:
                            logger.error(f"Detection event creation error: {e}")
                            self.integration_errors += 1
                    
                    logger.debug(f"🎯 Detection callback processed: {voltage:.3f}V on channel {channel}")
                    
                except Exception as e:
                    logger.error(f"Detection callback error: {e}")
                    self.integration_errors += 1
                    self.last_error_time = datetime.now(timezone.utc)
            
            # Add callback to raw logger
            self.raw_logger.add_detection_callback(detection_callback)
            
            logger.info(f"✅ Detection callbacks configured for session {raw_session_id}")
            
        except Exception as e:
            logger.error(f"Error setting up detection callbacks: {e}")
            raise
    
    def _create_detection_event(
        self, 
        test_session_id: str, 
        detection_data: Dict[str, Any],
        raw_session_id: str
    ) -> None:
        """Create detection event in database from raw detection"""
        try:
            db = next(get_db())
            try:
                # Create detection event
                detection_event = DetectionEvent(
                    id=str(uuid.uuid4()),
                    test_session_id=test_session_id,
                    timestamp=detection_data.get('timestamp_ns', time.time() * 1e9) / 1e9,
                    validation_result="PENDING",
                    labjack_timestamp=detection_data.get('timestamp_ns', time.time() * 1e9) / 1e9,
                    labjack_voltage=detection_data.get('voltage', 0.0),
                    detection_channel=f"AIN{detection_data.get('channel', 0)}",
                    processing_time_ms=1.0,  # Raw detection processing time
                    source="raw_labjack_integration",
                    detection_type="labjack_voltage",
                    
                    # Integration metadata
                    metadata={
                        'raw_session_id': raw_session_id,
                        'integration_source': 'raw_labjack_logger',
                        'detection_threshold': self.config.detection_threshold_volts,
                        'callback_processed_at': datetime.now(timezone.utc).isoformat()
                    }
                )
                
                db.add(detection_event)
                db.commit()
                
                logger.debug(f"💾 Detection event created: {detection_event.id}")
                
            except Exception as e:
                db.rollback()
                logger.error(f"Database error creating detection event: {e}")
                raise
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error creating detection event: {e}")
            raise
    
    def _start_monitoring(self) -> None:
        """Start performance monitoring thread"""
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="RawIntegrationMonitoring"
        )
        self.monitoring_thread.start()
        logger.info("📊 Integration monitoring started")
    
    def _monitoring_loop(self) -> None:
        """Performance monitoring loop"""
        while not self.shutdown_event.is_set():
            try:
                # Update session activity
                current_time = datetime.now(timezone.utc)
                
                for session_id, mapping in list(self.session_mappings.items()):
                    # Check for inactive sessions (no activity for 5 minutes)
                    if (current_time - mapping.last_activity).total_seconds() > 300:
                        logger.warning(f"Inactive integration session detected: {session_id}")
                    
                    # Health checks could go here
                    
                # Error rate monitoring
                if self.integration_errors > 0 and self.last_error_time:
                    error_age = (current_time - self.last_error_time).total_seconds()
                    if error_age > 3600:  # Reset error count after 1 hour
                        self.integration_errors = 0
                        self.last_error_time = None
                
                time.sleep(30)  # Monitor every 30 seconds
                
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                time.sleep(30)
    
    def get_integration_status(self, raw_session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of specific integration session"""
        try:
            with self.lock:
                if raw_session_id not in self.session_mappings:
                    return None
                
                session_mapping = self.session_mappings[raw_session_id]
                integration_config = self.active_integrations.get(raw_session_id, {})
                
                # Get raw session status
                raw_status = self.raw_logger.get_session_status(raw_session_id)
                
                return {
                    'raw_session_id': raw_session_id,
                    'test_session_id': session_mapping.test_session_id,
                    'hil_session_active': session_mapping.hil_session_active,
                    'detection_session_active': session_mapping.detection_session_active,
                    'created_at': session_mapping.created_at.isoformat(),
                    'last_activity': session_mapping.last_activity.isoformat(),
                    'raw_session_status': raw_status,
                    'callbacks_processed': self.detection_callbacks_count,
                    'integration_errors': self.integration_errors,
                    'session_name': integration_config.get('session_name'),
                    'configuration': {
                        'detection_threshold': self.config.detection_threshold_volts,
                        'debounce_time_ms': self.config.debounce_time_ms,
                        'callbacks_enabled': self.config.enable_detection_callbacks
                    }
                }
                
        except Exception as e:
            logger.error(f"Error getting integration status: {e}")
            return None
    
    def get_all_integrations_status(self) -> List[Dict[str, Any]]:
        """Get status of all active integration sessions"""
        try:
            statuses = []
            for raw_session_id in list(self.session_mappings.keys()):
                status = self.get_integration_status(raw_session_id)
                if status:
                    statuses.append(status)
            return statuses
        except Exception as e:
            logger.error(f"Error getting all integration statuses: {e}")
            return []
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get integration performance metrics"""
        try:
            with self.lock:
                active_sessions = len(self.session_mappings)
                current_time = datetime.now(timezone.utc)
                
                # Calculate average session duration
                total_duration = 0
                for integration in self.active_integrations.values():
                    if 'started_at' in integration:
                        duration = current_time - integration['started_at']
                        total_duration += duration.total_seconds()
                
                avg_duration = total_duration / max(active_sessions, 1)
                
                return {
                    'active_integrations': active_sessions,
                    'total_callbacks_processed': self.detection_callbacks_count,
                    'integration_errors': self.integration_errors,
                    'average_session_duration_seconds': avg_duration,
                    'error_rate_percent': (self.integration_errors / max(self.detection_callbacks_count, 1)) * 100,
                    'last_error_time': self.last_error_time.isoformat() if self.last_error_time else None,
                    'config': {
                        'detection_threshold': self.config.detection_threshold_volts,
                        'debounce_time_ms': self.config.debounce_time_ms,
                        'callbacks_enabled': self.config.enable_detection_callbacks,
                        'performance_monitoring': self.config.performance_monitoring
                    }
                }
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}
    
    def update_configuration(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update integration configuration"""
        try:
            with self.lock:
                # Update configuration
                if 'detection_threshold_volts' in config_updates:
                    self.config.detection_threshold_volts = config_updates['detection_threshold_volts']
                
                if 'debounce_time_ms' in config_updates:
                    self.config.debounce_time_ms = config_updates['debounce_time_ms']
                
                if 'enable_detection_callbacks' in config_updates:
                    self.config.enable_detection_callbacks = config_updates['enable_detection_callbacks']
                
                if 'performance_monitoring' in config_updates:
                    self.config.performance_monitoring = config_updates['performance_monitoring']
                
                # Apply configuration to active sessions
                for raw_session_id in self.session_mappings.keys():
                    try:
                        if hasattr(self.raw_logger, 'session_configs') and raw_session_id in self.raw_logger.session_configs:
                            self.raw_logger.session_configs[raw_session_id]['detection_threshold'] = self.config.detection_threshold_volts
                    except Exception as e:
                        logger.error(f"Error updating session config: {e}")
                
                logger.info(f"✅ Integration configuration updated: {config_updates}")
                
                return {
                    'success': True,
                    'message': 'Configuration updated successfully',
                    'updated_fields': list(config_updates.keys()),
                    'current_config': {
                        'detection_threshold_volts': self.config.detection_threshold_volts,
                        'debounce_time_ms': self.config.debounce_time_ms,
                        'enable_detection_callbacks': self.config.enable_detection_callbacks,
                        'performance_monitoring': self.config.performance_monitoring
                    }
                }
                
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def shutdown(self) -> None:
        """Shutdown integration service"""
        try:
            logger.info("🛑 Shutting down raw LabJack integration service...")
            
            # Signal shutdown
            self.shutdown_event.set()
            
            # Stop all active integrations
            active_sessions = list(self.session_mappings.keys())
            for raw_session_id in active_sessions:
                try:
                    asyncio.run(self.stop_integrated_session(raw_session_id))
                except Exception as e:
                    logger.error(f"Error stopping integration session {raw_session_id}: {e}")
            
            # Wait for monitoring thread
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5.0)
            
            logger.info("✅ Raw LabJack integration service shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during integration service shutdown: {e}")


# Global integration service instance
_integration_service: Optional[RawLabJackIntegrationService] = None


def get_raw_labjack_integration() -> RawLabJackIntegrationService:
    """Get global raw LabJack integration service instance"""
    global _integration_service
    if _integration_service is None:
        _integration_service = RawLabJackIntegrationService()
    return _integration_service


# Export key components
__all__ = [
    'RawLabJackIntegrationService',
    'IntegrationConfig',
    'SessionMapping',
    'get_raw_labjack_integration'
]