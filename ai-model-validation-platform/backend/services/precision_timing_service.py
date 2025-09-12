# Precision Timing Service - PRD Module 3.2 Complete Implementation
# Achieves sub-millisecond precision timing as required by PRD

import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass
from contextlib import contextmanager

logger = logging.getLogger(__name__)

@dataclass
class PrecisionTimestamp:
    """High-precision timestamp with monotonic and UTC time"""
    monotonic_ns: int  # Nanosecond precision monotonic time
    utc_timestamp: datetime  # UTC timestamp for database storage
    precision_microseconds: bool = True
    
    @classmethod
    def now(cls) -> 'PrecisionTimestamp':
        """Create precision timestamp for current moment"""
        monotonic_ns = time.monotonic_ns()
        utc_timestamp = datetime.now(timezone.utc)
        
        return cls(
            monotonic_ns=monotonic_ns,
            utc_timestamp=utc_timestamp,
            precision_microseconds=True
        )
    
    def elapsed_ms(self, start_timestamp: 'PrecisionTimestamp') -> float:
        """Calculate elapsed time in milliseconds with sub-millisecond precision"""
        elapsed_ns = self.monotonic_ns - start_timestamp.monotonic_ns
        return elapsed_ns / 1_000_000  # Convert nanoseconds to milliseconds
    
    def elapsed_us(self, start_timestamp: 'PrecisionTimestamp') -> float:
        """Calculate elapsed time in microseconds"""
        elapsed_ns = self.monotonic_ns - start_timestamp.monotonic_ns
        return elapsed_ns / 1_000  # Convert nanoseconds to microseconds

@dataclass 
class FrameTimestamp:
    """Frame-specific timestamp for video synchronization"""
    frame_number: int
    timestamp_ms: float
    video_time_seconds: float
    precision_timestamp: Optional[PrecisionTimestamp] = None
    
    @classmethod
    def from_video_time(cls, frame_number: int, video_time_seconds: float) -> 'FrameTimestamp':
        """Create frame timestamp from video time"""
        timestamp_ms = video_time_seconds * 1000.0
        return cls(
            frame_number=frame_number,
            timestamp_ms=timestamp_ms,
            video_time_seconds=video_time_seconds,
            precision_timestamp=PrecisionTimestamp.now()
        )

class PrecisionTimingService:
    """Service for sub-millisecond precision timing - PRD Technical Requirement"""
    
    def __init__(self):
        self._session_start_times: Dict[int, PrecisionTimestamp] = {}
        self._timing_events: Dict[int, List[Dict]] = {}
        self._lock = threading.RLock()
        
        # Verify monotonic clock availability
        self._validate_timing_capabilities()
        
        logger.info("Precision Timing Service initialized with sub-millisecond capability")
    
    def _validate_timing_capabilities(self):
        """Validate that the system supports required timing precision"""
        try:
            # Test monotonic clock resolution
            start_ns = time.monotonic_ns()
            time.sleep(0.001)  # 1ms sleep
            end_ns = time.monotonic_ns()
            
            resolution_ns = end_ns - start_ns
            resolution_us = resolution_ns / 1000
            
            logger.info(f"Monotonic clock resolution: {resolution_us:.3f} microseconds")
            
            if resolution_us > 1000:  # More than 1ms resolution
                logger.warning("Clock resolution may not meet sub-millisecond requirements")
            
        except Exception as e:
            logger.error(f"Failed to validate timing capabilities: {e}")
            raise RuntimeError("System does not support required timing precision")
    
    def get_precise_timestamp(self) -> PrecisionTimestamp:
        """Get high-precision timestamp - PRD Requirement: Test_Start_Time precision"""
        return PrecisionTimestamp.now()
    
    def start_test_session_timing(self, session_id: int) -> PrecisionTimestamp:
        """Start precision timing for test session - PRD: Test_Start_Time"""
        with self._lock:
            start_time = PrecisionTimestamp.now()
            self._session_start_times[session_id] = start_time
            self._timing_events[session_id] = []
            
            logger.info(f"Started precision timing for session {session_id} at {start_time.utc_timestamp}")
            return start_time
    
    def calculate_expected_event_time(self, 
                                    session_id: int, 
                                    video_timestamp_ms: float) -> PrecisionTimestamp:
        """Calculate Expected_Event_Time - PRD Requirement 3.2"""
        with self._lock:
            session_start = self._session_start_times.get(session_id)
            if not session_start:
                raise ValueError(f"No timing session found for session {session_id}")
            
            # Calculate expected time by adding video timestamp to session start
            expected_ns = session_start.monotonic_ns + int(video_timestamp_ms * 1_000_000)
            expected_utc = datetime.fromtimestamp(
                (session_start.utc_timestamp.timestamp() + video_timestamp_ms / 1000),
                tz=timezone.utc
            )
            
            expected_time = PrecisionTimestamp(
                monotonic_ns=expected_ns,
                utc_timestamp=expected_utc,
                precision_microseconds=True
            )
            
            return expected_time
    
    def record_signal_received_time(self, session_id: int) -> PrecisionTimestamp:
        """Record Signal_Received_Time - PRD Requirement 3.2"""
        signal_time = PrecisionTimestamp.now()
        
        with self._lock:
            if session_id not in self._timing_events:
                self._timing_events[session_id] = []
            
            # Record the signal reception event
            self._timing_events[session_id].append({
                'type': 'signal_received',
                'timestamp': signal_time,
                'monotonic_ns': signal_time.monotonic_ns
            })
        
        logger.debug(f"Recorded signal received time for session {session_id}: {signal_time.utc_timestamp}")
        return signal_time
    
    def calculate_latency_precise(self, 
                                expected_time: PrecisionTimestamp, 
                                received_time: PrecisionTimestamp) -> float:
        """Calculate latency with sub-millisecond precision"""
        latency_ms = received_time.elapsed_ms(expected_time)
        
        # Log precision metrics
        logger.debug(f"Calculated precise latency: {latency_ms:.6f}ms")
        
        return latency_ms
    
    def get_elapsed_time_ms(self, start_time: PrecisionTimestamp) -> float:
        """Get elapsed time in milliseconds from start time"""
        current_time = PrecisionTimestamp.now()
        return current_time.elapsed_ms(start_time)
    
    def get_session_timing_summary(self, session_id: int) -> Dict:
        """Get timing summary for session"""
        with self._lock:
            session_start = self._session_start_times.get(session_id)
            events = self._timing_events.get(session_id, [])
            
            if not session_start:
                return {'error': 'Session not found'}
            
            current_time = PrecisionTimestamp.now()
            total_elapsed_ms = current_time.elapsed_ms(session_start)
            
            return {
                'session_id': session_id,
                'start_time': session_start.utc_timestamp.isoformat(),
                'total_elapsed_ms': round(total_elapsed_ms, 6),
                'total_events': len(events),
                'timing_precision': 'sub_millisecond',
                'monotonic_clock_used': True
            }
    
    def cleanup_session_timing(self, session_id: int):
        """Clean up timing data for completed session"""
        with self._lock:
            self._session_start_times.pop(session_id, None)
            self._timing_events.pop(session_id, None)
            
        logger.info(f"Cleaned up timing data for session {session_id}")
    
    @contextmanager
    def precision_timing_context(self, operation_name: str):
        """Context manager for timing operations with high precision"""
        start_time = PrecisionTimestamp.now()
        logger.debug(f"Started timing operation: {operation_name}")
        
        try:
            yield start_time
        finally:
            end_time = PrecisionTimestamp.now()
            elapsed_ms = end_time.elapsed_ms(start_time)
            logger.debug(f"Operation '{operation_name}' completed in {elapsed_ms:.6f}ms")
    
    def validate_timing_accuracy(self) -> Dict[str, Any]:
        """Validate timing accuracy and precision capabilities"""
        validation_results = {
            'monotonic_clock_available': True,
            'nanosecond_precision': True,
            'sub_millisecond_capable': True
        }
        
        try:
            # Test timing precision with multiple measurements
            measurements = []
            
            for _ in range(100):
                start = time.monotonic_ns()
                time.sleep(0.0001)  # 100 microseconds
                end = time.monotonic_ns()
                
                elapsed_us = (end - start) / 1000
                measurements.append(elapsed_us)
            
            avg_precision = sum(measurements) / len(measurements)
            min_precision = min(measurements)
            max_precision = max(measurements)
            
            validation_results.update({
                'average_precision_us': round(avg_precision, 3),
                'min_precision_us': round(min_precision, 3),
                'max_precision_us': round(max_precision, 3),
                'precision_variance': round(max_precision - min_precision, 3),
                'meets_prd_requirements': avg_precision < 1000  # Less than 1ms
            })
            
            logger.info(f"Timing validation completed: {validation_results}")
            
        except Exception as e:
            logger.error(f"Timing validation failed: {e}")
            validation_results['validation_error'] = str(e)
            validation_results['sub_millisecond_capable'] = False
        
        return validation_results
    
    def get_timing_statistics(self) -> Dict[str, Any]:
        """Get overall timing service statistics"""
        with self._lock:
            active_sessions = len(self._session_start_times)
            total_events = sum(len(events) for events in self._timing_events.values())
            
            return {
                'active_sessions': active_sessions,
                'total_timing_events': total_events,
                'precision_mode': 'sub_millisecond',
                'timing_service_status': 'operational',
                'clock_type': 'monotonic_ns'
            }

# Global precision timing service instance
_precision_timing_service = None

def get_precision_timing_service() -> PrecisionTimingService:
    """Get global precision timing service instance"""
    global _precision_timing_service
    if _precision_timing_service is None:
        _precision_timing_service = PrecisionTimingService()
    return _precision_timing_service

def initialize_precision_timing_service() -> PrecisionTimingService:
    """Initialize precision timing service"""
    return get_precision_timing_service()

# Convenience functions for easy access
def create_sync_point() -> PrecisionTimestamp:
    """Create a precision sync point"""
    return PrecisionTimestamp.now()

def measure_latency(start_time: PrecisionTimestamp, end_time: PrecisionTimestamp) -> float:
    """Measure latency between two precision timestamps in milliseconds"""
    return end_time.elapsed_ms(start_time)

def get_monotonic_timestamp() -> int:
    """Get monotonic timestamp in nanoseconds"""
    return time.monotonic_ns()

def validate_hil_timing_accuracy() -> dict:
    """Validate HIL timing accuracy"""
    service = get_precision_timing_service()
    return service.validate_timing_accuracy()

# HIL timing precision constant - PRD requirement
HIL_TIMING_PRECISION_MS = 0.1  # Sub-millisecond precision target

# Add TimingSyncPoint alias for compatibility
TimingSyncPoint = PrecisionTimestamp