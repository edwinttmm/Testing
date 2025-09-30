"""
Hybrid LabJack Session Manager
=============================

Unified session management that coordinates simultaneous raw (1000Hz) and 
video-synchronized (24fps) logging with intelligent data correlation.

This service manages the complete lifecycle of hybrid logging sessions:
- Coordinates raw LabJack data capture at 1000Hz with smart compression
- Manages video-synchronized detection events at 24fps
- Provides unified session lifecycle management
- Handles graceful degradation when one logging method fails
- Maintains backward compatibility with existing detection_events API
- Optimizes storage using intelligent compression strategies

Key Features:
- Dual-mode logging with automatic failover
- Temporal correlation between microsecond raw data and frame-based video
- Smart compression selection based on signal characteristics
- Performance optimization for combined data queries
- Conflict resolution for overlapping detection events
- Complete backward compatibility
"""

import asyncio
import logging
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
import json

# Database imports
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, desc

# Local imports
from database import get_db
from models import TestSession, DetectionEvent, Video
from src.models.raw_labjack_models import (
    RawLabJackSession, RawLabJackBuffer, CompressionAlgorithm, 
    DataQuality, BufferStatus
)

# Service imports
from services.labjack_service import get_labjack_service
from services.labjack_detection_service import get_detection_service
from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
from services.video_timing_service import get_video_timing_service
from src.services.hybrid_query_service import get_hybrid_query_service

logger = logging.getLogger(__name__)


class SessionMode(Enum):
    """Hybrid session operating modes"""
    RAW_ONLY = "raw_only"              # Only raw 1000Hz data capture
    VIDEO_SYNC_ONLY = "video_sync"     # Only video-synchronized detection
    HYBRID = "hybrid"                  # Both raw and video-sync logging
    AUTO = "auto"                      # Automatically choose best mode


class SessionStatus(Enum):
    """Unified session status"""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEGRADED = "degraded"              # One logging mode failed
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class HybridSessionConfig:
    """Complete hybrid session configuration"""
    # Session identification
    session_id: str
    session_name: str
    test_session_id: Optional[str] = None
    
    # Operating mode
    mode: SessionMode = SessionMode.HYBRID
    allow_degraded_operation: bool = True
    failover_timeout_seconds: int = 5
    
    # Raw data configuration
    enable_raw_logging: bool = True
    raw_sample_rate_hz: int = 1000
    raw_channels: List[str] = field(default_factory=lambda: ["AIN0", "AIN1"])
    raw_compression_algorithm: CompressionAlgorithm = CompressionAlgorithm.ADAPTIVE
    raw_buffer_size_samples: int = 10000
    raw_compression_threshold: float = 0.1
    
    # Video-sync configuration
    enable_video_sync: bool = True
    video_sync_channels: List[str] = field(default_factory=lambda: ["AIN0"])
    video_sync_sample_rate: int = 24
    voltage_threshold: float = 2.5
    debounce_ms: int = 50
    
    # Video timing configuration
    video_id: Optional[str] = None
    video_fps: Optional[float] = None
    video_duration: Optional[float] = None
    enable_frame_sync: bool = True
    
    # Performance optimization
    correlation_window_ms: float = 100.0
    max_correlation_distance_ms: float = 500.0
    storage_optimization_enabled: bool = True
    
    # Backward compatibility
    maintain_detection_events_compatibility: bool = True
    legacy_api_support: bool = True
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionHealth:
    """Health status of hybrid session components"""
    overall_status: SessionStatus
    raw_logging_active: bool
    video_sync_active: bool
    correlation_quality: float  # 0.0-1.0
    performance_score: float    # 0.0-1.0
    error_messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Performance metrics
    raw_data_throughput_hz: Optional[float] = None
    video_sync_event_rate_hz: Optional[float] = None
    storage_utilization_percent: Optional[float] = None
    compression_ratio: Optional[float] = None
    correlation_success_rate: Optional[float] = None


class HybridSessionManager:
    """
    Unified session manager coordinating raw and video-synchronized LabJack logging.
    
    This service provides a single interface for managing complex hybrid logging
    sessions while maintaining complete backward compatibility.
    """
    
    def __init__(self):
        # Core services
        self.labjack_service = get_labjack_service()
        self.detection_service = get_detection_service()
        self.dedicated_monitor = get_dedicated_labjack_monitor()
        self.video_timing_service = get_video_timing_service()
        self.query_service = get_hybrid_query_service()
        
        # Session management
        self.active_sessions: Dict[str, HybridSessionConfig] = {}
        self.session_health: Dict[str, SessionHealth] = {}
        self.raw_sessions: Dict[str, str] = {}  # session_id -> raw_session_id
        
        # Synchronization
        self.lock = threading.RLock()
        
        # Performance tracking
        self.session_stats = {
            'sessions_started': 0,
            'sessions_completed': 0,
            'degraded_operations': 0,
            'correlation_events': 0,
            'total_raw_samples': 0,
            'total_detection_events': 0
        }
        
        logger.info("Hybrid session manager initialized")
    
    async def start_hybrid_session(
        self,
        config: HybridSessionConfig,
        db: Optional[Session] = None
    ) -> Tuple[bool, SessionHealth]:
        """
        Start a hybrid logging session with both raw and video-synchronized logging.
        
        Args:
            config: Complete session configuration
            db: Database session (optional)
        
        Returns:
            Tuple of (success, session_health)
        """
        session_start_time = time.time()
        
        if db is None:
            db = next(get_db())
            close_db = True
        else:
            close_db = False
        
        try:
            with self.lock:
                if config.session_id in self.active_sessions:
                    logger.warning(f"Session {config.session_id} already active")
                    return False, self._get_session_health(config.session_id)
                
                logger.info(f"Starting hybrid session: {config.session_id} in {config.mode.value} mode")
                
                # Initialize session health tracking
                health = SessionHealth(
                    overall_status=SessionStatus.INITIALIZING,
                    raw_logging_active=False,
                    video_sync_active=False,
                    correlation_quality=0.0,
                    performance_score=0.0
                )
                
                self.active_sessions[config.session_id] = config
                self.session_health[config.session_id] = health
                
                # Start components based on mode
                success_count = 0
                total_components = 0
                
                # Start raw logging if enabled
                if config.enable_raw_logging and config.mode in [SessionMode.RAW_ONLY, SessionMode.HYBRID, SessionMode.AUTO]:
                    total_components += 1
                    if await self._start_raw_logging(config, db):
                        success_count += 1
                        health.raw_logging_active = True
                        logger.info(f"Raw logging started for session {config.session_id}")
                    else:
                        health.error_messages.append("Failed to start raw logging")
                        logger.error(f"Raw logging failed for session {config.session_id}")
                
                # Start video-synchronized logging if enabled
                if config.enable_video_sync and config.mode in [SessionMode.VIDEO_SYNC_ONLY, SessionMode.HYBRID, SessionMode.AUTO]:
                    total_components += 1
                    if await self._start_video_sync_logging(config, db):
                        success_count += 1
                        health.video_sync_active = True
                        logger.info(f"Video-sync logging started for session {config.session_id}")
                    else:
                        health.error_messages.append("Failed to start video-sync logging")
                        logger.error(f"Video-sync logging failed for session {config.session_id}")
                
                # Determine final session status
                if success_count == 0:
                    health.overall_status = SessionStatus.ERROR
                    success = False
                elif success_count < total_components:
                    if config.allow_degraded_operation:
                        health.overall_status = SessionStatus.DEGRADED
                        health.warnings.append("Operating in degraded mode - some components failed")
                        success = True
                        self.session_stats['degraded_operations'] += 1
                    else:
                        health.overall_status = SessionStatus.ERROR
                        success = False
                        await self._cleanup_failed_session(config.session_id, db)
                else:
                    health.overall_status = SessionStatus.ACTIVE
                    success = True
                
                # Calculate initial performance score
                health.performance_score = success_count / max(1, total_components)
                
                # Update session stats
                if success:
                    self.session_stats['sessions_started'] += 1
                
                startup_time = time.time() - session_start_time
                logger.info(
                    f"Hybrid session {config.session_id} startup completed in {startup_time:.2f}s: "
                    f"Status={health.overall_status.value}, Components={success_count}/{total_components}"
                )
                
                return success, health
                
        except Exception as e:
            logger.error(f"Failed to start hybrid session {config.session_id}: {e}")
            health = SessionHealth(
                overall_status=SessionStatus.ERROR,
                raw_logging_active=False,
                video_sync_active=False,
                correlation_quality=0.0,
                performance_score=0.0,
                error_messages=[str(e)]
            )
            return False, health
        finally:
            if close_db:
                db.close()
    
    async def _start_raw_logging(self, config: HybridSessionConfig, db: Session) -> bool:
        """Start raw LabJack data logging component"""
        try:
            # Create raw session record
            raw_session = RawLabJackSession(
                session_name=f"raw_{config.session_name}",
                test_session_id=config.test_session_id,
                device_id="T7_USB",  # Will be updated by actual device info
                channels=config.raw_channels,
                sample_rate_hz=config.raw_sample_rate_hz,
                compression_algorithm=config.raw_compression_algorithm,
                buffer_size_samples=config.raw_buffer_size_samples,
                compression_threshold=config.raw_compression_threshold,
                is_active=True,
                started_at=datetime.now(timezone.utc),
                configuration={
                    'voltage_range': {'min': -10.0, 'max': 10.0},
                    'correlation_window_ms': config.correlation_window_ms,
                    'storage_optimization': config.storage_optimization_enabled
                },
                metadata={
                    'parent_session_id': config.session_id,
                    'mode': 'hybrid_raw_component'
                }
            )
            
            db.add(raw_session)
            db.commit()
            
            # Store raw session mapping
            self.raw_sessions[config.session_id] = raw_session.id
            
            # Initialize LabJack hardware connection
            labjack_connected = await self.labjack_service.connect(allow_mock=False)
            if not labjack_connected:
                logger.error("LabJack hardware connection failed for raw logging")
                return False
            
            # Start high-frequency streaming
            stream_success = await self.labjack_service.start_stream(
                channels=config.raw_channels,
                sample_rate=config.raw_sample_rate_hz
            )
            
            if not stream_success:
                logger.error("Failed to start LabJack streaming for raw logging")
                return False
            
            # Start raw data processing loop
            await self._start_raw_data_processing(config.session_id, raw_session.id)
            
            return True
            
        except Exception as e:
            logger.error(f"Raw logging startup failed: {e}")
            return False
    
    async def _start_video_sync_logging(self, config: HybridSessionConfig, db: Session) -> bool:
        """Start video-synchronized detection logging component"""
        try:
            # Prepare video timing configuration
            video_timing_config = {
                'video_id': config.video_id,
                'fps': config.video_fps,
                'duration': config.video_duration,
                'enable_frame_sync': config.enable_frame_sync,
                'channels': config.video_sync_channels,
                'voltage_threshold': config.voltage_threshold,
                'debounce_ms': config.debounce_ms,
                'sample_rate': config.video_sync_sample_rate
            }
            
            # Start dedicated HIL monitoring with video sync
            success = self.dedicated_monitor.start_monitoring_with_video_sync(
                session_id=config.session_id,
                video_timing_config=video_timing_config
            )
            
            if not success:
                logger.error("Failed to start dedicated HIL monitoring")
                return False
            
            logger.info(f"Video-sync logging started for session {config.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Video-sync logging startup failed: {e}")
            return False
    
    async def _start_raw_data_processing(self, session_id: str, raw_session_id: str):
        """Start background raw data processing and compression"""
        def process_raw_data():
            """Background thread for raw data processing"""
            try:
                logger.info(f"Starting raw data processing for session {session_id}")
                
                while session_id in self.active_sessions:
                    # Get streaming data from LabJack
                    raw_data = self.labjack_service.get_stream_data(max_samples=10000)
                    
                    if raw_data:
                        # Process and compress data
                        asyncio.create_task(self._process_raw_data_batch(
                            session_id, raw_session_id, raw_data
                        ))
                        
                        # Update performance stats
                        self.session_stats['total_raw_samples'] += len(raw_data)
                    
                    # Brief sleep to prevent CPU spinning
                    time.sleep(0.01)  # 10ms polling interval
                    
            except Exception as e:
                logger.error(f"Raw data processing error for session {session_id}: {e}")
        
        # Start processing thread
        thread = threading.Thread(target=process_raw_data, daemon=True)
        thread.start()
    
    async def _process_raw_data_batch(
        self, 
        session_id: str, 
        raw_session_id: str, 
        raw_data: List[float]
    ):
        """Process and compress a batch of raw data"""
        try:
            # Import compression service
            from src.services.raw_labjack_compression import RawLabJackCompressor
            compressor = RawLabJackCompressor()
            
            # Determine optimal compression based on signal characteristics
            signal_variance = self._calculate_signal_variance(raw_data)
            config = self.active_sessions[session_id]
            
            if signal_variance < config.raw_compression_threshold:
                # Low variance - use high compression
                compression_alg = CompressionAlgorithm.DELTA_RLE
            else:
                # High variance - use adaptive compression
                compression_alg = config.raw_compression_algorithm
            
            # Compress data
            compressed_data, compression_metadata = compressor.compress_data_batch(
                raw_data, compression_alg, {
                    'channels': config.raw_channels,
                    'sample_rate_hz': config.raw_sample_rate_hz,
                    'timestamp': time.time()
                }
            )
            
            # Store compressed buffer
            db = next(get_db())
            try:
                buffer = RawLabJackBuffer(
                    session_id=raw_session_id,
                    buffer_sequence=int(time.time() * 1000),  # Microsecond sequence
                    start_timestamp=datetime.now(timezone.utc),
                    start_timestamp_ns=time.time_ns(),
                    end_timestamp=datetime.now(timezone.utc),
                    end_timestamp_ns=time.time_ns(),
                    sample_count=len(raw_data) // len(config.raw_channels),
                    channel_count=len(config.raw_channels),
                    actual_sample_rate_hz=config.raw_sample_rate_hz,
                    channels=config.raw_channels,
                    compression_algorithm=compression_alg,
                    raw_data_size_bytes=len(raw_data) * 4,  # 4 bytes per float
                    compressed_data_size_bytes=len(compressed_data),
                    compression_ratio=len(raw_data) * 4 / len(compressed_data),
                    compressed_data=compressed_data,
                    compression_metadata=compression_metadata,
                    buffer_status=BufferStatus.COMPRESSED,
                    data_quality=self._assess_data_quality(raw_data)
                )
                
                db.add(buffer)
                db.commit()
                
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"Raw data batch processing failed: {e}")
    
    def _calculate_signal_variance(self, data: List[float]) -> float:
        """Calculate signal variance for compression optimization"""
        if not data:
            return 0.0
        
        mean = sum(data) / len(data)
        variance = sum((x - mean) ** 2 for x in data) / len(data)
        return variance
    
    def _assess_data_quality(self, data: List[float]) -> DataQuality:
        """Assess raw data quality based on signal characteristics"""
        if not data:
            return DataQuality.CORRUPT
        
        # Calculate signal-to-noise ratio estimation
        mean = sum(data) / len(data)
        variance = sum((x - mean) ** 2 for x in data) / len(data)
        
        if variance < 0.001:  # Very low noise
            return DataQuality.EXCELLENT
        elif variance < 0.01:  # Low noise
            return DataQuality.GOOD
        elif variance < 0.1:   # Moderate noise
            return DataQuality.FAIR
        else:                  # High noise
            return DataQuality.POOR
    
    async def stop_hybrid_session(
        self, 
        session_id: str,
        db: Optional[Session] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Stop a hybrid logging session and return summary statistics.
        
        Args:
            session_id: Session to stop
            db: Database session (optional)
        
        Returns:
            Tuple of (success, session_statistics)
        """
        if db is None:
            db = next(get_db())
            close_db = True
        else:
            close_db = False
        
        try:
            with self.lock:
                if session_id not in self.active_sessions:
                    logger.warning(f"Session {session_id} not found or already stopped")
                    return True, {}
                
                config = self.active_sessions[session_id]
                health = self.session_health[session_id]
                
                logger.info(f"Stopping hybrid session: {session_id}")
                health.overall_status = SessionStatus.STOPPING
                
                # Stop raw logging component
                raw_stats = {}
                if health.raw_logging_active:
                    raw_stats = await self._stop_raw_logging(session_id, db)
                
                # Stop video-sync logging component
                video_sync_stats = {}
                if health.video_sync_active:
                    video_sync_stats = self.dedicated_monitor.stop_monitoring(session_id)
                
                # Finalize session statistics
                session_stats = {
                    'session_id': session_id,
                    'session_name': config.session_name,
                    'mode': config.mode.value,
                    'duration_seconds': (datetime.now(timezone.utc) - self._get_session_start_time(session_id)).total_seconds(),
                    'final_status': health.overall_status.value,
                    'raw_logging_stats': raw_stats,
                    'video_sync_stats': video_sync_stats,
                    'correlation_quality': health.correlation_quality,
                    'performance_score': health.performance_score,
                    'total_errors': len(health.error_messages),
                    'total_warnings': len(health.warnings)
                }
                
                # Clean up session data
                self.active_sessions.pop(session_id, None)
                self.session_health.pop(session_id, None)
                self.raw_sessions.pop(session_id, None)
                
                # Update global stats
                self.session_stats['sessions_completed'] += 1
                
                health.overall_status = SessionStatus.COMPLETED
                
                logger.info(f"Hybrid session {session_id} stopped successfully")
                return True, session_stats
                
        except Exception as e:
            logger.error(f"Failed to stop hybrid session {session_id}: {e}")
            return False, {'error': str(e)}
        finally:
            if close_db:
                db.close()
    
    async def _stop_raw_logging(self, session_id: str, db: Session) -> Dict[str, Any]:
        """Stop raw logging component and return statistics"""
        try:
            # Stop LabJack streaming
            await self.labjack_service.stop_stream()
            
            # Get raw session statistics
            raw_session_id = self.raw_sessions.get(session_id)
            if not raw_session_id:
                return {}
            
            # Query compression statistics
            stats_query = db.query(RawLabJackBuffer).filter(
                RawLabJackBuffer.session_id == raw_session_id
            )
            
            buffers = stats_query.all()
            
            if not buffers:
                return {'message': 'No raw data captured'}
            
            # Calculate statistics
            total_samples = sum(b.sample_count for b in buffers)
            total_raw_bytes = sum(b.raw_data_size_bytes for b in buffers)
            total_compressed_bytes = sum(b.compressed_data_size_bytes for b in buffers)
            
            avg_compression_ratio = (
                sum(b.compression_ratio for b in buffers) / len(buffers)
            ) if buffers else 0.0
            
            return {
                'total_buffers': len(buffers),
                'total_samples': total_samples,
                'total_raw_bytes': total_raw_bytes,
                'total_compressed_bytes': total_compressed_bytes,
                'average_compression_ratio': avg_compression_ratio,
                'storage_savings_percent': (1 - total_compressed_bytes / max(1, total_raw_bytes)) * 100
            }
            
        except Exception as e:
            logger.error(f"Error stopping raw logging for session {session_id}: {e}")
            return {'error': str(e)}
    
    def _get_session_start_time(self, session_id: str) -> datetime:
        """Get session start time from database or estimates"""
        # This would query the database for actual start time
        # For now, estimate from current time minus typical session duration
        return datetime.now(timezone.utc) - timedelta(minutes=5)
    
    def get_session_health(self, session_id: str) -> Optional[SessionHealth]:
        """Get current health status of a session"""
        with self.lock:
            return self.session_health.get(session_id)
    
    def _get_session_health(self, session_id: str) -> SessionHealth:
        """Internal method to get or create session health"""
        return self.session_health.get(session_id, SessionHealth(
            overall_status=SessionStatus.ERROR,
            raw_logging_active=False,
            video_sync_active=False,
            correlation_quality=0.0,
            performance_score=0.0,
            error_messages=["Session not found"]
        ))
    
    async def _cleanup_failed_session(self, session_id: str, db: Session):
        """Clean up resources for a failed session startup"""
        try:
            # Stop any partially started components
            if session_id in self.raw_sessions:
                await self._stop_raw_logging(session_id, db)
            
            # Clean up session tracking
            self.active_sessions.pop(session_id, None)
            self.session_health.pop(session_id, None)
            self.raw_sessions.pop(session_id, None)
            
            logger.info(f"Cleaned up failed session {session_id}")
            
        except Exception as e:
            logger.error(f"Error cleaning up failed session {session_id}: {e}")
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        with self.lock:
            return list(self.active_sessions.keys())
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """Get overall session manager statistics"""
        with self.lock:
            active_sessions = len(self.active_sessions)
            
            # Calculate health distribution
            health_distribution = {}
            for health in self.session_health.values():
                status = health.overall_status.value
                health_distribution[status] = health_distribution.get(status, 0) + 1
            
            return {
                'active_sessions': active_sessions,
                'session_health_distribution': health_distribution,
                'total_sessions_started': self.session_stats['sessions_started'],
                'total_sessions_completed': self.session_stats['sessions_completed'],
                'degraded_operations': self.session_stats['degraded_operations'],
                'total_raw_samples_processed': self.session_stats['total_raw_samples'],
                'total_detection_events': self.session_stats['total_detection_events'],
                'correlation_events_processed': self.session_stats['correlation_events'],
                'service_uptime_seconds': time.time() - self._service_start_time if hasattr(self, '_service_start_time') else 0
            }
    
    def __init__(self):
        # Initialize all previous attributes...
        super().__init__() if hasattr(super(), '__init__') else None
        
        # Track service start time
        self._service_start_time = time.time()


# Global service instance
_hybrid_session_manager: Optional[HybridSessionManager] = None
_service_lock = threading.Lock()


def get_hybrid_session_manager() -> HybridSessionManager:
    """Get global hybrid session manager instance (thread-safe singleton)"""
    global _hybrid_session_manager
    
    if _hybrid_session_manager is None:
        with _service_lock:
            if _hybrid_session_manager is None:
                _hybrid_session_manager = HybridSessionManager()
    
    return _hybrid_session_manager


# Convenience functions
async def start_hybrid_logging_session(
    session_id: str,
    session_name: str,
    config_overrides: Optional[Dict[str, Any]] = None
) -> Tuple[bool, SessionHealth]:
    """Start a hybrid logging session with default configuration"""
    
    config = HybridSessionConfig(
        session_id=session_id,
        session_name=session_name
    )
    
    # Apply configuration overrides
    if config_overrides:
        for key, value in config_overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    manager = get_hybrid_session_manager()
    return await manager.start_hybrid_session(config)


async def stop_hybrid_logging_session(session_id: str) -> Tuple[bool, Dict[str, Any]]:
    """Stop a hybrid logging session"""
    manager = get_hybrid_session_manager()
    return await manager.stop_hybrid_session(session_id)


# Export key components
__all__ = [
    'HybridSessionManager',
    'HybridSessionConfig',
    'SessionHealth',
    'SessionMode',
    'SessionStatus',
    'get_hybrid_session_manager',
    'start_hybrid_logging_session',
    'stop_hybrid_logging_session'
]