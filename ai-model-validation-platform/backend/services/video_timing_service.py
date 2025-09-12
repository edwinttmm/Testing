"""
Enhanced Video Timing Service for HIL Validation

This service provides high-precision video timing synchronized with the precision 
timing service for sub-millisecond accuracy in HIL validation scenarios.

Key Features:
- Integration with PrecisionTimingService for monotonic timing
- Frame-accurate video synchronization
- Sub-millisecond precision video start timing
- Hardware signal synchronization support
- Drift compensation for long-running tests
- Frame-accurate seeking capabilities

HIL Integration:
- Works with LabJack hardware timing systems
- Provides timing references for detection latency analysis
- Supports multiple concurrent video streams
- Maintains timing accuracy across long test sessions
"""

import time
import logging
import threading
import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
import queue
import uuid

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Import database and models
from database import get_db
from models import TestSession, Video, DetectionEvent

# Import precision timing service
from .precision_timing_service import (
    PrecisionTimingService,
    FrameTimestamp,
    PrecisionTimestamp
)

logger = logging.getLogger(__name__)


@dataclass
class EnhancedVideoTimingData:
    """Enhanced container for video timing information with HIL precision"""
    session_id: str
    video_id: str
    start_timestamp: float
    start_timestamp_ns: int  # Nanosecond precision monotonic
    precision_ns: int
    system_time_utc: str
    monotonic_time: float
    sync_point_id: str  # Reference to precision timing sync point
    frame_rate: Optional[float] = None
    duration_s: Optional[float] = None
    frame_count: Optional[int] = None
    thread_id: int = 0
    process_id: int = 0


@dataclass
class VideoLatencyMeasurement:
    """Enhanced latency measurement with frame accuracy"""
    measurement_id: str
    session_id: str
    video_id: str
    video_start_time: float
    detection_timestamp: float
    latency_ms: float
    latency_ns: int
    frame_number: Optional[int] = None
    frame_timestamp: Optional[float] = None
    precision_indicator: str = "high"
    calculation_timestamp: float = 0.0
    accuracy_estimate_ns: float = 0.0


class VideoTimingError(Exception):
    """Custom exception for video timing operations"""
    pass


class VideoTimingService:
    """
    Enhanced video timing service with precision timing integration for HIL validation.
    
    Provides sub-millisecond video timing accuracy integrated with hardware signal
    validation and frame-accurate synchronization capabilities.
    """
    
    def __init__(self, precision_timing_service: Optional[PrecisionTimingService] = None):
        self._timing_cache: Dict[str, EnhancedVideoTimingData] = {}  # session_id -> timing_data
        self._session_videos: Dict[str, List[str]] = {}  # session_id -> [video_ids]
        self._video_frames: Dict[str, List[FrameTimestamp]] = {}  # video_id -> frame timestamps
        self._lock = threading.RLock()
        
        # Integration with precision timing service
        self._precision_service = precision_timing_service or PrecisionTimingService()
        
        # Performance tracking
        self._timing_starts = 0
        self._latency_calculations = 0
        self._synchronizations = 0
        
        # Precision check flag
        self._precision_check_done = False
        
        logger.info(f"Enhanced VideoTimingService initialized with precision timing integration")
    
    def _check_timer_precision(self) -> int:
        """Check system timer precision"""
        if self._precision_check_done:
            return 1000  # Default to 1μs
            
        # Test timer precision
        samples = []
        for _ in range(100):
            t1 = time.time_ns()
            t2 = time.time_ns()
            if t2 > t1:
                samples.append(t2 - t1)
        
        self._precision_check_done = True
        if samples:
            precision = min(samples)
            logger.info(f"System timer precision: {precision}ns")
            return precision
        return 1000  # 1μs default
    
    def start_video_timing(self, session_id: str, video_id: str, db: Session = None, 
                          video_metadata: Optional[Dict[str, Any]] = None) -> float:
        """
        Record precise video start timestamp with frame-accurate synchronization.
        
        Args:
            session_id: Test session identifier
            video_id: Video being played
            db: Database session (optional)
            video_metadata: Video metadata (fps, duration, etc.)
            
        Returns:
            High-precision timestamp (seconds since epoch)
            
        Raises:
            VideoTimingError: If timing recording fails
        """
        try:
            with self._lock:
                # Create precision timing sync point
                sync_point_id = f"video_start_{session_id}_{video_id}"
                sync_point = self._precision_service.create_sync_point(sync_point_id)
                
                # Record high-precision timestamps
                start_timestamp = sync_point.system_time
                start_timestamp_ns = self._precision_service.get_monotonic_timestamp_ns()
                
                # Extract video metadata
                fps = video_metadata.get('fps') if video_metadata else None
                duration_s = video_metadata.get('duration') if video_metadata else None
                
                # Create enhanced timing data
                timing_data = EnhancedVideoTimingData(
                    session_id=session_id,
                    video_id=video_id,
                    start_timestamp=start_timestamp,
                    start_timestamp_ns=start_timestamp_ns,
                    precision_ns=int(self._precision_service.get_timing_accuracy_ns()),
                    system_time_utc=datetime.now(timezone.utc).isoformat(),
                    monotonic_time=sync_point.monotonic_time,
                    sync_point_id=sync_point_id,
                    frame_rate=fps,
                    duration_s=duration_s,
                    frame_count=int(duration_s * fps) if fps and duration_s else None,
                    thread_id=threading.get_ident(),
                    process_id=os.getpid() if 'os' in globals() else 0
                )
                
                # Cache timing data
                self._timing_cache[session_id] = timing_data
                
                # Track videos per session
                if session_id not in self._session_videos:
                    self._session_videos[session_id] = []
                if video_id not in self._session_videos[session_id]:
                    self._session_videos[session_id].append(video_id)
                
                # Generate frame timestamps if video metadata available
                if fps and duration_s:
                    frame_timestamps = self._precision_service.synchronize_video_frames(
                        video_id, fps, duration_s, start_timestamp
                    )
                    self._video_frames[video_id] = frame_timestamps
                
                # Store in database if session provided
                if db:
                    self._store_enhanced_video_timing(session_id, timing_data, db)
                
                self._timing_starts += 1
                
                logger.info(f"Enhanced video timing started - Session: {session_id}, Video: {video_id}, "
                           f"Timestamp: {start_timestamp:.6f}, Precision: {timing_data.precision_ns}ns")
                
                return start_timestamp
                
        except Exception as e:
            logger.error(f"Failed to start enhanced video timing for session {session_id}: {e}")
            raise VideoTimingError(f"Failed to record video start time: {e}")
    
    def get_video_start_time(self, session_id: str, db: Session = None) -> Optional[float]:
        """
        Retrieve video start timestamp for latency calculation.
        
        Args:
            session_id: Test session identifier
            db: Database session (optional)
            
        Returns:
            Video start timestamp or None if not found
        """
        try:
            with self._lock:
                # Check cache first
                if session_id in self._timing_cache:
                    timing_data = self._timing_cache[session_id]
                    logger.debug(f"Retrieved cached video start time for session {session_id}: "
                               f"{timing_data.start_timestamp:.6f}")
                    return timing_data.start_timestamp
                
                # Check database if session provided
                if db:
                    return self._get_video_start_time_from_db(session_id, db)
                
                logger.warning(f"No video start time found for session {session_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get video start time for session {session_id}: {e}")
            return None
    
    def get_timing_data(self, session_id: str) -> Optional[EnhancedVideoTimingData]:
        """Get complete timing data for a session"""
        with self._lock:
            return self._timing_cache.get(session_id)
    
    def calculate_enhanced_latency(self, session_id: str, detection_timestamp: float,
                                  detection_metadata: Optional[Dict[str, Any]] = None,
                                  db: Session = None) -> Optional[VideoLatencyMeasurement]:
        """
        Calculate enhanced latency with frame accuracy and precision timing.
        
        Args:
            session_id: Test session identifier
            detection_timestamp: Detection event timestamp
            detection_metadata: Additional detection information
            db: Database session (optional)
            
        Returns:
            VideoLatencyMeasurement object or None if calculation fails
        """
        try:
            timing_data = self.get_timing_data(session_id)
            
            if timing_data is None:
                logger.error(f"Cannot calculate latency - no timing data for session {session_id}")
                return None
            
            # Use precision timing service for accurate calculation
            measurement_type = "video_to_detection"
            precision_measurement = self._precision_service.measure_latency(
                measurement_type, 
                timing_data.sync_point_id, 
                str(detection_timestamp),
                metadata={'session_id': session_id}
            )
            
            # Calculate frame information if available
            frame_number = None
            frame_timestamp = None
            
            if timing_data.video_id in self._video_frames:
                frame_timestamps = self._video_frames[timing_data.video_id]
                
                # Find closest frame to detection
                for i, frame_ts in enumerate(frame_timestamps):
                    frame_time_s = timing_data.start_timestamp + (frame_ts.video_timestamp_ms / 1000.0)
                    
                    if abs(frame_time_s - detection_timestamp) < 0.1:  # Within 100ms
                        frame_number = frame_ts.frame_number
                        frame_timestamp = frame_time_s
                        break
            
            measurement = VideoLatencyMeasurement(
                measurement_id=str(uuid.uuid4()),
                session_id=session_id,
                video_id=timing_data.video_id,
                video_start_time=timing_data.start_timestamp,
                detection_timestamp=detection_timestamp,
                latency_ms=precision_measurement.latency_ms,
                latency_ns=precision_measurement.latency_ns,
                frame_number=frame_number,
                frame_timestamp=frame_timestamp,
                precision_indicator="high",
                calculation_timestamp=time.time(),
                accuracy_estimate_ns=precision_measurement.accuracy_estimate_ns
            )
            
            self._latency_calculations += 1
            
            logger.info(f"Enhanced latency calculated - Session: {session_id}, "
                       f"Latency: {measurement.latency_ms:.3f}ms, "
                       f"Frame: {frame_number}, Accuracy: {measurement.accuracy_estimate_ns:.1f}ns")
            
            return measurement
            
        except Exception as e:
            logger.error(f"Failed to calculate enhanced latency for session {session_id}: {e}")
            return None
    
    def synchronize_with_labjack(self, session_id: str, labjack_service) -> bool:
        """
        Synchronize video timing with LabJack monitoring.
        
        This method coordinates the timing between video playback start and 
        LabJack detection monitoring to ensure accurate latency measurement.
        
        Args:
            session_id: Test session identifier
            labjack_service: LabJack service instance
            
        Returns:
            True if synchronization successful, False otherwise
        """
        try:
            with self._lock:
                timing_data = self._timing_cache.get(session_id)
                
                if not timing_data:
                    logger.error(f"No timing data found for session {session_id}")
                    return False
                
                # Check if LabJack service has required methods
                if not hasattr(labjack_service, 'start_monitoring'):
                    logger.error("LabJack service missing start_monitoring method")
                    return False
                
                # Synchronize timing reference
                sync_timestamp = time.time()
                
                # Start LabJack monitoring with timing reference
                labjack_result = labjack_service.start_monitoring(
                    session_id=session_id,
                    reference_timestamp=timing_data.start_timestamp,
                    sync_timestamp=sync_timestamp
                )
                
                if labjack_result:
                    logger.info(f"Successfully synchronized video timing with LabJack for session {session_id}")
                    return True
                else:
                    logger.error(f"Failed to start LabJack monitoring for session {session_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to synchronize with LabJack for session {session_id}: {e}")
            return False
    
    def _store_video_start_time(self, session_id: str, start_timestamp: float, db: Session):
        """Store video start time in database"""
        try:
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            
            if test_session:
                # Store as JSON to preserve precision
                timing_info = {
                    "video_start_timestamp": start_timestamp,
                    "precision_ns": self._timer_precision,
                    "system_time_utc": datetime.now(timezone.utc).isoformat(),
                    "recorded_at": time.time()
                }
                
                # Add timing info to session notes or create new field
                if hasattr(test_session, 'video_start_timestamp'):
                    test_session.video_start_timestamp = start_timestamp
                else:
                    # Store in a JSON field or add as metadata
                    logger.info(f"Storing video timing info for session {session_id}: {timing_info}")
                
                db.commit()
                logger.debug(f"Stored video start time in database for session {session_id}")
            else:
                logger.error(f"Test session {session_id} not found in database")
                
        except SQLAlchemyError as e:
            logger.error(f"Database error storing video start time: {e}")
            db.rollback()
    
    def _get_video_start_time_from_db(self, session_id: str, db: Session) -> Optional[float]:
        """Retrieve video start time from database"""
        try:
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            
            if test_session and hasattr(test_session, 'video_start_timestamp'):
                return test_session.video_start_timestamp
            
            return None
            
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving video start time: {e}")
            return None
    
    def clear_session_timing(self, session_id: str) -> bool:
        """Clear cached timing data for a session"""
        try:
            with self._lock:
                removed_timing = self._timing_cache.pop(session_id, None)
                removed_videos = self._session_videos.pop(session_id, None)
                
                if removed_timing:
                    logger.info(f"Cleared timing data for session {session_id}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Failed to clear timing data for session {session_id}: {e}")
            return False
    
    def get_active_sessions(self) -> List[str]:
        """Get list of sessions with active timing data"""
        with self._lock:
            return list(self._timing_cache.keys())
    
    def get_session_videos(self, session_id: str) -> List[str]:
        """Get list of videos for a session"""
        with self._lock:
            return self._session_videos.get(session_id, [])
    
    def get_timing_statistics(self) -> Dict[str, Any]:
        """Get timing service statistics"""
        with self._lock:
            return {
                "active_sessions": len(self._timing_cache),
                "total_videos": sum(len(videos) for videos in self._session_videos.values()),
                "timer_precision_ns": self._timer_precision,
                "precision_class": "high" if self._timer_precision < 10000 else "standard",
                "cache_size_bytes": len(str(self._timing_cache)),
            }


# Global service instance
_video_timing_service = None
_service_lock = threading.Lock()


def get_video_timing_service() -> VideoTimingService:
    """Get global video timing service instance (thread-safe singleton)"""
    global _video_timing_service
    
    if _video_timing_service is None:
        with _service_lock:
            if _video_timing_service is None:
                _video_timing_service = VideoTimingService()
    
    return _video_timing_service


# Convenience functions for direct use
def start_video_timing(session_id: str, video_id: str, db: Session = None) -> float:
    """Start video timing for a session"""
    service = get_video_timing_service()
    return service.start_video_timing(session_id, video_id, db)


def get_video_start_time(session_id: str, db: Session = None) -> Optional[float]:
    """Get video start time for latency calculation"""
    service = get_video_timing_service()
    return service.get_video_start_time(session_id, db)


def calculate_latency(session_id: str, detection_timestamp: float, 
                     db: Session = None) -> Optional[VideoLatencyMeasurement]:
    """Calculate latency between video start and detection"""
    service = get_video_timing_service()
    return service.calculate_latency(session_id, detection_timestamp, db)


def synchronize_with_labjack(session_id: str, labjack_service) -> bool:
    """Synchronize video timing with LabJack service"""
    service = get_video_timing_service()
    return service.synchronize_with_labjack(session_id, labjack_service)


# Import os for process ID
import os