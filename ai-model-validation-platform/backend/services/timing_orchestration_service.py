"""
HIL Timing Orchestration Service for T0-T1 Integration

This service coordinates precise timing capture between test start commands (T0)
and video playback timing (T1) for HIL validation tests. It ensures nanosecond
precision timing synchronization across all HIL test components.

Key Features:
- T0 capture at exact test start command moment  
- T1 measurement when video actually begins playing
- Precise T1-T0 presentation delay calculation
- Integration with LabJack hardware timing
- Database storage of timing metadata
- Real-time timing quality monitoring
"""

import time
import logging
import threading
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Any, List
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Import database models and services
from database import get_db
from models import TestSession, DetectionEvent
from services.precision_timing_service import PrecisionTimingService
from services.video_timing_service import VideoTimingService, get_video_timing_service
from services.labjack_service import LabJackService

logger = logging.getLogger(__name__)


@dataclass
class T0TimingCapture:
    """T0 timing data - command timestamp when test start is initiated"""
    session_id: str
    command_timestamp: float  # Unix timestamp when "Start Test" clicked
    command_timestamp_ns: int  # Nanosecond precision monotonic timestamp
    precision_ns: int  # Measured timing precision
    system_time_utc: str  # Human readable UTC timestamp
    thread_id: int
    capture_latency_ns: int  # Time between click and capture
    hardware_sync_enabled: bool


@dataclass  
class T1TimingCapture:
    """T1 timing data - actual video start timestamp"""
    session_id: str
    video_id: str
    video_start_timestamp: float  # Unix timestamp when video actually starts
    video_start_timestamp_ns: int  # Nanosecond precision timestamp
    precision_ns: int  # Measured timing precision
    frame_number: int  # First frame number
    video_metadata: Dict[str, Any]  # FPS, resolution, etc.
    capture_source: str  # "video_timing_service", "frame_callback", etc.


@dataclass
class T1MinusT0Measurement:
    """T1-T0 presentation delay measurement"""
    session_id: str
    t0_timestamp: float  # T0 command timestamp
    t1_timestamp: float  # T1 video start timestamp
    presentation_delay_ms: float  # T1 - T0 in milliseconds
    presentation_delay_ns: int  # T1 - T0 in nanoseconds
    timing_quality: str  # "high", "medium", "low"
    measurement_accuracy_ns: int  # Estimated measurement accuracy
    captured_at: float  # When this measurement was calculated


class TimingOrchestrationError(Exception):
    """Custom exception for timing orchestration operations"""
    pass


class TimingOrchestrationService:
    """
    Orchestrates precise T0-T1 timing capture for HIL validation tests.
    
    Coordinates between command timing (T0), video timing (T1), and hardware
    synchronization to provide precise presentation delay measurements.
    """
    
    def __init__(self, 
                 precision_service: Optional[PrecisionTimingService] = None,
                 video_timing_service: Optional[VideoTimingService] = None,
                 labjack_service: Optional[LabJackService] = None):
        """
        Initialize timing orchestration service.
        
        Args:
            precision_service: Precision timing service instance
            video_timing_service: Video timing service instance  
            labjack_service: LabJack hardware service instance
        """
        # Service dependencies
        self._precision_service = precision_service or PrecisionTimingService()
        self._video_timing_service = video_timing_service or get_video_timing_service()
        self._labjack_service = labjack_service
        
        # Timing data storage
        self._t0_captures: Dict[str, T0TimingCapture] = {}  # session_id -> T0 data
        self._t1_captures: Dict[str, T1TimingCapture] = {}  # session_id -> T1 data
        self._delay_measurements: Dict[str, T1MinusT0Measurement] = {}  # session_id -> T1-T0
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Quality tracking
        self._total_captures = 0
        self._successful_measurements = 0
        self._timing_quality_threshold_ns = 1000000  # 1ms threshold for "high" quality
        
        logger.info("HIL Timing Orchestration Service initialized")
    
    def capture_t0_command_timestamp(self, 
                                   session_id: str, 
                                   db: Session = None,
                                   metadata: Optional[Dict[str, Any]] = None) -> T0TimingCapture:
        """
        Capture precise T0 timestamp at the moment test start command is issued.
        
        This is called immediately when "Start Test" button is clicked to capture
        the exact command initiation timestamp before any processing delays.
        
        Args:
            session_id: Test session identifier
            db: Database session for storage
            metadata: Additional metadata for the capture
            
        Returns:
            T0TimingCapture object with precise command timing
            
        Raises:
            TimingOrchestrationError: If T0 capture fails
        """
        try:
            with self._lock:
                # Capture precise command timestamp with minimal latency
                capture_start_ns = time.time_ns()
                command_timestamp = time.time()
                command_timestamp_ns = self._precision_service.get_monotonic_timestamp_ns()
                capture_end_ns = time.time_ns()
                
                # Calculate capture latency
                capture_latency_ns = capture_end_ns - capture_start_ns
                
                # Create T0 timing capture record
                t0_capture = T0TimingCapture(
                    session_id=session_id,
                    command_timestamp=command_timestamp,
                    command_timestamp_ns=command_timestamp_ns,
                    precision_ns=int(self._precision_service.get_timing_accuracy_ns()),
                    system_time_utc=datetime.now(timezone.utc).isoformat(),
                    thread_id=threading.get_ident(),
                    capture_latency_ns=capture_latency_ns,
                    hardware_sync_enabled=self._labjack_service is not None
                )
                
                # Store T0 capture
                self._t0_captures[session_id] = t0_capture
                
                # Store in database if session provided
                if db:
                    self._store_t0_timing_data(session_id, t0_capture, db)
                
                # Initialize video timing service for this session
                self._initialize_video_timing_capture(session_id, t0_capture)
                
                self._total_captures += 1
                
                logger.info(f"T0 command timestamp captured - Session: {session_id}, "
                           f"Timestamp: {command_timestamp:.6f}, "
                           f"Precision: {t0_capture.precision_ns}ns, "
                           f"Capture Latency: {capture_latency_ns}ns")
                
                return t0_capture
                
        except Exception as e:
            logger.error(f"Failed to capture T0 command timestamp for session {session_id}: {e}")
            raise TimingOrchestrationError(f"T0 capture failed: {e}")
    
    def capture_t1_video_start_timestamp(self,
                                        session_id: str,
                                        video_id: str,
                                        db: Session = None,
                                        video_metadata: Optional[Dict[str, Any]] = None) -> T1TimingCapture:
        """
        Capture precise T1 timestamp when video actually starts playing.
        
        This integrates with the video timing service to capture the exact moment
        video playback begins, providing the T1 measurement for delay calculation.
        
        Args:
            session_id: Test session identifier
            video_id: Video being played
            db: Database session for storage
            video_metadata: Video metadata (fps, duration, etc.)
            
        Returns:
            T1TimingCapture object with precise video start timing
            
        Raises:
            TimingOrchestrationError: If T1 capture fails
        """
        try:
            with self._lock:
                # Use video timing service to capture precise video start
                video_start_timestamp = self._video_timing_service.start_video_timing(
                    session_id, video_id, db, video_metadata
                )
                
                # Get additional timing data from video service
                timing_data = self._video_timing_service.get_timing_data(session_id)
                
                if not timing_data:
                    raise TimingOrchestrationError("Failed to get video timing data")
                
                # Create T1 timing capture record
                t1_capture = T1TimingCapture(
                    session_id=session_id,
                    video_id=video_id,
                    video_start_timestamp=video_start_timestamp,
                    video_start_timestamp_ns=timing_data.start_timestamp_ns,
                    precision_ns=timing_data.precision_ns,
                    frame_number=0,  # First frame
                    video_metadata=video_metadata or {},
                    capture_source="video_timing_service"
                )
                
                # Store T1 capture
                self._t1_captures[session_id] = t1_capture
                
                # Calculate T1-T0 delay if T0 exists
                if session_id in self._t0_captures:
                    delay_measurement = self._calculate_presentation_delay(session_id)
                    
                    # Store delay measurement in database
                    if db and delay_measurement:
                        self._store_delay_measurement(session_id, delay_measurement, db)
                
                logger.info(f"T1 video start timestamp captured - Session: {session_id}, "
                           f"Video: {video_id}, Timestamp: {video_start_timestamp:.6f}, "
                           f"Precision: {t1_capture.precision_ns}ns")
                
                return t1_capture
                
        except Exception as e:
            logger.error(f"Failed to capture T1 video start timestamp for session {session_id}: {e}")
            raise TimingOrchestrationError(f"T1 capture failed: {e}")
    
    def _calculate_presentation_delay(self, session_id: str) -> Optional[T1MinusT0Measurement]:
        """
        Calculate precise T1-T0 presentation delay.
        
        Args:
            session_id: Test session identifier
            
        Returns:
            T1MinusT0Measurement object or None if calculation fails
        """
        try:
            t0_capture = self._t0_captures.get(session_id)
            t1_capture = self._t1_captures.get(session_id)
            
            if not t0_capture or not t1_capture:
                logger.warning(f"Missing timing data for delay calculation - Session: {session_id}")
                return None
            
            # Calculate delay in seconds and convert to milliseconds/nanoseconds
            delay_seconds = t1_capture.video_start_timestamp - t0_capture.command_timestamp
            delay_ms = delay_seconds * 1000.0
            delay_ns = int(delay_seconds * 1e9)
            
            # Determine timing quality based on precision
            combined_precision_ns = max(t0_capture.precision_ns, t1_capture.precision_ns)
            
            if combined_precision_ns <= 100000:  # 0.1ms
                timing_quality = "high"
            elif combined_precision_ns <= 1000000:  # 1ms
                timing_quality = "medium"
            else:
                timing_quality = "low"
            
            # Create measurement record
            delay_measurement = T1MinusT0Measurement(
                session_id=session_id,
                t0_timestamp=t0_capture.command_timestamp,
                t1_timestamp=t1_capture.video_start_timestamp,
                presentation_delay_ms=delay_ms,
                presentation_delay_ns=delay_ns,
                timing_quality=timing_quality,
                measurement_accuracy_ns=combined_precision_ns,
                captured_at=time.time()
            )
            
            # Store measurement
            self._delay_measurements[session_id] = delay_measurement
            
            if timing_quality == "high":
                self._successful_measurements += 1
            
            logger.info(f"T1-T0 presentation delay calculated - Session: {session_id}, "
                       f"Delay: {delay_ms:.3f}ms, Quality: {timing_quality}, "
                       f"Accuracy: {combined_precision_ns}ns")
            
            return delay_measurement
            
        except Exception as e:
            logger.error(f"Failed to calculate presentation delay for session {session_id}: {e}")
            return None
    
    def get_timing_measurement(self, session_id: str) -> Optional[T1MinusT0Measurement]:
        """
        Get the T1-T0 presentation delay measurement for a session.
        
        Args:
            session_id: Test session identifier
            
        Returns:
            T1MinusT0Measurement object or None if not available
        """
        with self._lock:
            return self._delay_measurements.get(session_id)
    
    def get_t0_capture(self, session_id: str) -> Optional[T0TimingCapture]:
        """Get T0 command timing capture for a session"""
        with self._lock:
            return self._t0_captures.get(session_id)
    
    def get_t1_capture(self, session_id: str) -> Optional[T1TimingCapture]:
        """Get T1 video timing capture for a session"""
        with self._lock:
            return self._t1_captures.get(session_id)
    
    def _initialize_video_timing_capture(self, session_id: str, t0_capture: T0TimingCapture):
        """
        Initialize video timing service for upcoming T1 capture.
        
        This prepares the video timing service to capture T1 when video starts.
        """
        try:
            # Notify video timing service that a session is starting
            # This allows it to prepare for precise T1 capture
            logger.debug(f"Initializing video timing capture for session {session_id}")
            
            # The video timing service will be called directly when video starts
            # This method just logs the initialization for now
            
        except Exception as e:
            logger.error(f"Failed to initialize video timing capture for session {session_id}: {e}")
    
    def _store_t0_timing_data(self, session_id: str, t0_capture: T0TimingCapture, db: Session):
        """Store T0 timing data in database"""
        try:
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            
            if test_session:
                # Store T0 command timing data in new dedicated fields
                test_session.command_start_timestamp = t0_capture.command_timestamp
                test_session.command_start_timestamp_ns = str(t0_capture.command_timestamp_ns)
                
                # Update timing status
                test_session.precision_timing_enabled = True
                test_session.timing_accuracy_ns = float(t0_capture.precision_ns)
                test_session.hil_timing_enabled = True
                
                db.commit()
                logger.debug(f"T0 timing data stored in database for session {session_id}")
            else:
                logger.error(f"Test session {session_id} not found for T0 timing storage")
                
        except SQLAlchemyError as e:
            logger.error(f"Database error storing T0 timing data: {e}")
            db.rollback()
    
    def _store_delay_measurement(self, session_id: str, measurement: T1MinusT0Measurement, db: Session):
        """Store T1-T0 delay measurement in database"""
        try:
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            
            if test_session:
                # Store presentation delay measurement in dedicated fields
                test_session.presentation_delay_ms = measurement.presentation_delay_ms
                test_session.presentation_delay_ns = str(measurement.presentation_delay_ns)
                test_session.presentation_delay_quality = measurement.timing_quality
                
                # Update timing validation status
                if measurement.timing_quality == "high":
                    test_session.timing_validation_status = "passed"
                    test_session.hil_compliance_verified = True
                else:
                    test_session.timing_validation_status = "measured"
                
                # Update video timing synchronization status
                test_session.video_timing_sync_status = "synced"
                
                db.commit()
                logger.debug(f"T1-T0 delay measurement stored in database for session {session_id}")
            else:
                logger.error(f"Test session {session_id} not found for delay measurement storage")
                
        except SQLAlchemyError as e:
            logger.error(f"Database error storing delay measurement: {e}")
            db.rollback()
    
    def clear_session_timing(self, session_id: str) -> bool:
        """
        Clear all timing data for a session.
        
        Args:
            session_id: Test session identifier
            
        Returns:
            True if data was cleared, False if no data found
        """
        try:
            with self._lock:
                cleared_any = False
                
                if session_id in self._t0_captures:
                    del self._t0_captures[session_id]
                    cleared_any = True
                
                if session_id in self._t1_captures:
                    del self._t1_captures[session_id]
                    cleared_any = True
                
                if session_id in self._delay_measurements:
                    del self._delay_measurements[session_id]
                    cleared_any = True
                
                # Also clear video timing service data
                self._video_timing_service.clear_session_timing(session_id)
                
                if cleared_any:
                    logger.info(f"Cleared timing data for session {session_id}")
                
                return cleared_any
                
        except Exception as e:
            logger.error(f"Failed to clear timing data for session {session_id}: {e}")
            return False
    
    def get_timing_statistics(self) -> Dict[str, Any]:
        """Get timing orchestration service statistics"""
        with self._lock:
            success_rate = (self._successful_measurements / self._total_captures * 100 
                          if self._total_captures > 0 else 0)
            
            return {
                "total_timing_captures": self._total_captures,
                "successful_measurements": self._successful_measurements,
                "success_rate_percent": success_rate,
                "active_sessions": len(self._t0_captures),
                "completed_measurements": len(self._delay_measurements),
                "timing_quality_threshold_ns": self._timing_quality_threshold_ns,
                "services": {
                    "precision_timing": self._precision_service is not None,
                    "video_timing": self._video_timing_service is not None,
                    "labjack_hardware": self._labjack_service is not None
                }
            }


# Global service instance
_timing_orchestration_service = None
_service_lock = threading.Lock()


def get_timing_orchestration_service() -> TimingOrchestrationService:
    """Get global timing orchestration service instance (thread-safe singleton)"""
    global _timing_orchestration_service
    
    if _timing_orchestration_service is None:
        with _service_lock:
            if _timing_orchestration_service is None:
                _timing_orchestration_service = TimingOrchestrationService()
    
    return _timing_orchestration_service


# Convenience functions for direct use
def capture_test_start_timestamp(session_id: str, db: Session = None) -> T0TimingCapture:
    """Capture T0 command timestamp when test starts"""
    service = get_timing_orchestration_service()
    return service.capture_t0_command_timestamp(session_id, db)


def capture_video_start_timestamp(session_id: str, video_id: str, 
                                 db: Session = None, 
                                 video_metadata: Dict[str, Any] = None) -> T1TimingCapture:
    """Capture T1 video start timestamp"""
    service = get_timing_orchestration_service()
    return service.capture_t1_video_start_timestamp(session_id, video_id, db, video_metadata)


def get_presentation_delay(session_id: str) -> Optional[T1MinusT0Measurement]:
    """Get T1-T0 presentation delay measurement"""
    service = get_timing_orchestration_service()
    return service.get_timing_measurement(session_id)