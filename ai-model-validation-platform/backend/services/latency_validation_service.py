"""
Latency Validation Service

Calculates latency between LabJack detection and video start time.
Provides Pass/Fail validation based on latency thresholds.
Generates comprehensive latency statistics and distribution analysis.
"""

import logging
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math

from services.labjack_detection_service import DetectionEvent
from services.video_timing_service import VideoTimingData, LatencyMeasurement as TimingLatencyMeasurement

logger = logging.getLogger(__name__)


class LatencyResult(Enum):
    """Latency validation results"""
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class LatencyMeasurement:
    """Individual latency measurement"""
    measurement_id: str
    session_id: str
    detection_event: DetectionEvent
    video_start_time: datetime
    video_start_time_unix: float
    detection_time: datetime
    detection_time_unix: float
    latency_ms: float
    threshold_ms: float
    result: LatencyResult
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "measurement_id": self.measurement_id,
            "session_id": self.session_id,
            "detection_event": self.detection_event.to_dict(),
            "video_start_time": self.video_start_time.isoformat(),
            "video_start_time_unix": self.video_start_time_unix,
            "detection_time": self.detection_time.isoformat(),
            "detection_time_unix": self.detection_time_unix,
            "latency_ms": self.latency_ms,
            "threshold_ms": self.threshold_ms,
            "result": self.result.value,
            "metadata": self.metadata
        }


@dataclass
class LatencyStatistics:
    """Comprehensive latency statistics"""
    session_id: str
    total_measurements: int
    pass_count: int
    fail_count: int
    error_count: int
    timeout_count: int
    pass_rate_percent: float
    average_latency_ms: float
    median_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    std_deviation_ms: float
    percentile_95_ms: float
    percentile_99_ms: float
    threshold_ms: float
    measurement_period_seconds: float
    measurements: List[LatencyMeasurement] = field(default_factory=list)
    distribution_histogram: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "session_id": self.session_id,
            "total_measurements": self.total_measurements,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "error_count": self.error_count,
            "timeout_count": self.timeout_count,
            "pass_rate_percent": self.pass_rate_percent,
            "average_latency_ms": self.average_latency_ms,
            "median_latency_ms": self.median_latency_ms,
            "min_latency_ms": self.min_latency_ms,
            "max_latency_ms": self.max_latency_ms,
            "std_deviation_ms": self.std_deviation_ms,
            "percentile_95_ms": self.percentile_95_ms,
            "percentile_99_ms": self.percentile_99_ms,
            "threshold_ms": self.threshold_ms,
            "measurement_period_seconds": self.measurement_period_seconds,
            "distribution_histogram": self.distribution_histogram,
            "measurements_count": len(self.measurements)
        }


class LatencyValidationService:
    """
    Service for validating detection latency against video timing
    """
    
    def __init__(self, default_threshold_ms: float = 50.0):
        self.default_threshold_ms = default_threshold_ms
        
        # Storage for measurements and results
        self.latency_measurements: Dict[str, List[LatencyMeasurement]] = {}
        self.session_statistics: Dict[str, LatencyStatistics] = {}
        
        # Validation configuration
        self.histogram_bin_size_ms = 5.0  # 5ms bins for histogram
        self.timeout_threshold_ms = 5000.0  # 5 second timeout for detections
        
        logger.info(f"Latency Validation Service initialized (threshold: {default_threshold_ms}ms)")
    
    def calculate_latency(self, detection_event: DetectionEvent, 
                         video_start_time: datetime, video_start_time_unix: float,
                         threshold_ms: Optional[float] = None) -> LatencyMeasurement:
        """
        Calculate latency between detection and video start
        
        Args:
            detection_event: LabJack detection event
            video_start_time: Video start datetime
            video_start_time_unix: Video start unix timestamp
            threshold_ms: Optional custom threshold (uses default if None)
            
        Returns:
            LatencyMeasurement object
        """
        try:
            # Use provided threshold or default
            threshold = threshold_ms if threshold_ms is not None else self.default_threshold_ms
            
            # Calculate latency in milliseconds
            latency_seconds = detection_event.timestamp_unix - video_start_time_unix
            latency_ms = latency_seconds * 1000.0
            
            # Determine result based on threshold
            if latency_ms < 0:
                # Detection before video start - error condition
                result = LatencyResult.ERROR
            elif latency_ms > self.timeout_threshold_ms:
                # Detection too late - timeout
                result = LatencyResult.TIMEOUT
            elif latency_ms <= threshold:
                # Within threshold - pass
                result = LatencyResult.PASS
            else:
                # Exceeds threshold - fail
                result = LatencyResult.FAIL
            
            # Create measurement
            measurement_id = f"LAT_{detection_event.session_id}_{detection_event.detection_id}"
            
            measurement = LatencyMeasurement(
                measurement_id=measurement_id,
                session_id=detection_event.session_id or "unknown",
                detection_event=detection_event,
                video_start_time=video_start_time,
                video_start_time_unix=video_start_time_unix,
                detection_time=detection_event.timestamp,
                detection_time_unix=detection_event.timestamp_unix,
                latency_ms=latency_ms,
                threshold_ms=threshold,
                result=result,
                metadata={
                    "latency_seconds": latency_seconds,
                    "calculation_method": "unix_timestamp_difference",
                    "detection_voltage": detection_event.voltage_level,
                    "detection_channel": detection_event.channel,
                    "video_id": detection_event.video_id
                }
            )
            
            logger.debug(f"Calculated latency: {latency_ms:.2f}ms ({result.value}) "
                        f"for detection {detection_event.detection_id}")
            
            return measurement
            
        except Exception as e:
            logger.error(f"Failed to calculate latency for detection {detection_event.detection_id}: {e}")
            
            # Return error measurement
            return LatencyMeasurement(
                measurement_id=f"ERROR_{detection_event.detection_id}",
                session_id=detection_event.session_id or "unknown",
                detection_event=detection_event,
                video_start_time=video_start_time,
                video_start_time_unix=video_start_time_unix,
                detection_time=detection_event.timestamp,
                detection_time_unix=detection_event.timestamp_unix,
                latency_ms=-1.0,
                threshold_ms=threshold_ms or self.default_threshold_ms,
                result=LatencyResult.ERROR,
                metadata={"error": str(e)}
            )
    
    def validate_session_latency(self, session_id: str, detection_events: List[DetectionEvent],
                               video_start_time: datetime, video_start_time_unix: float,
                               threshold_ms: Optional[float] = None) -> LatencyStatistics:
        """
        Validate latency for all detections in a session
        
        Args:
            session_id: Test session identifier
            detection_events: List of detection events from LabJack
            video_start_time: Video start datetime
            video_start_time_unix: Video start unix timestamp  
            threshold_ms: Optional custom threshold
            
        Returns:
            LatencyStatistics object with comprehensive analysis
        """
        try:
            if not detection_events:
                logger.warning(f"No detection events provided for session {session_id}")
                return self._create_empty_statistics(session_id, threshold_ms)
            
            threshold = threshold_ms if threshold_ms is not None else self.default_threshold_ms
            measurements = []
            
            # Calculate latency for each detection
            for detection_event in detection_events:
                measurement = self.calculate_latency(
                    detection_event, video_start_time, video_start_time_unix, threshold
                )
                measurements.append(measurement)
            
            # Store measurements for this session
            self.latency_measurements[session_id] = measurements
            
            # Generate comprehensive statistics
            statistics_obj = self._generate_statistics(session_id, measurements, threshold)
            
            # Store statistics
            self.session_statistics[session_id] = statistics_obj
            
            logger.info(f"Validated latency for session {session_id}: "
                       f"{statistics_obj.pass_count}/{statistics_obj.total_measurements} passed "
                       f"({statistics_obj.pass_rate_percent:.1f}%)")
            
            return statistics_obj
            
        except Exception as e:
            logger.error(f"Failed to validate session latency for {session_id}: {e}")
            return self._create_error_statistics(session_id, threshold_ms, str(e))
    
    def _generate_statistics(self, session_id: str, measurements: List[LatencyMeasurement],
                           threshold_ms: float) -> LatencyStatistics:
        """Generate comprehensive latency statistics"""
        try:
            total_measurements = len(measurements)
            
            if total_measurements == 0:
                return self._create_empty_statistics(session_id, threshold_ms)
            
            # Count results by type
            pass_count = sum(1 for m in measurements if m.result == LatencyResult.PASS)
            fail_count = sum(1 for m in measurements if m.result == LatencyResult.FAIL)
            error_count = sum(1 for m in measurements if m.result == LatencyResult.ERROR)
            timeout_count = sum(1 for m in measurements if m.result == LatencyResult.TIMEOUT)
            
            # Calculate pass rate
            pass_rate_percent = (pass_count / total_measurements) * 100.0
            
            # Extract valid latency values (exclude errors and timeouts for stats)
            valid_latencies = [
                m.latency_ms for m in measurements 
                if m.result in [LatencyResult.PASS, LatencyResult.FAIL] and m.latency_ms >= 0
            ]
            
            if not valid_latencies:
                # No valid measurements
                return LatencyStatistics(
                    session_id=session_id,
                    total_measurements=total_measurements,
                    pass_count=pass_count,
                    fail_count=fail_count,
                    error_count=error_count,
                    timeout_count=timeout_count,
                    pass_rate_percent=pass_rate_percent,
                    average_latency_ms=0.0,
                    median_latency_ms=0.0,
                    min_latency_ms=0.0,
                    max_latency_ms=0.0,
                    std_deviation_ms=0.0,
                    percentile_95_ms=0.0,
                    percentile_99_ms=0.0,
                    threshold_ms=threshold_ms,
                    measurement_period_seconds=0.0,
                    measurements=measurements,
                    distribution_histogram={}
                )
            
            # Calculate statistical measures
            average_latency_ms = statistics.mean(valid_latencies)
            median_latency_ms = statistics.median(valid_latencies)
            min_latency_ms = min(valid_latencies)
            max_latency_ms = max(valid_latencies)
            std_deviation_ms = statistics.stdev(valid_latencies) if len(valid_latencies) > 1 else 0.0
            
            # Calculate percentiles
            sorted_latencies = sorted(valid_latencies)
            percentile_95_ms = self._calculate_percentile(sorted_latencies, 95)
            percentile_99_ms = self._calculate_percentile(sorted_latencies, 99)
            
            # Calculate measurement period
            measurement_period_seconds = 0.0
            if measurements:
                timestamps = [m.detection_time_unix for m in measurements]
                measurement_period_seconds = max(timestamps) - min(timestamps)
            
            # Generate distribution histogram
            distribution_histogram = self._generate_histogram(valid_latencies)
            
            return LatencyStatistics(
                session_id=session_id,
                total_measurements=total_measurements,
                pass_count=pass_count,
                fail_count=fail_count,
                error_count=error_count,
                timeout_count=timeout_count,
                pass_rate_percent=pass_rate_percent,
                average_latency_ms=average_latency_ms,
                median_latency_ms=median_latency_ms,
                min_latency_ms=min_latency_ms,
                max_latency_ms=max_latency_ms,
                std_deviation_ms=std_deviation_ms,
                percentile_95_ms=percentile_95_ms,
                percentile_99_ms=percentile_99_ms,
                threshold_ms=threshold_ms,
                measurement_period_seconds=measurement_period_seconds,
                measurements=measurements,
                distribution_histogram=distribution_histogram
            )
            
        except Exception as e:
            logger.error(f"Failed to generate statistics for session {session_id}: {e}")
            return self._create_error_statistics(session_id, threshold_ms, str(e))
    
    def _calculate_percentile(self, sorted_values: List[float], percentile: float) -> float:
        """Calculate percentile value from sorted list"""
        if not sorted_values:
            return 0.0
        
        if len(sorted_values) == 1:
            return sorted_values[0]
        
        # Calculate index for percentile
        index = (percentile / 100.0) * (len(sorted_values) - 1)
        lower_index = int(math.floor(index))
        upper_index = int(math.ceil(index))
        
        if lower_index == upper_index:
            return sorted_values[lower_index]
        
        # Interpolate between values
        weight = index - lower_index
        return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight
    
    def _generate_histogram(self, latencies: List[float]) -> Dict[str, int]:
        """Generate latency distribution histogram"""
        if not latencies:
            return {}
        
        histogram = {}
        
        # Determine histogram range
        min_val = min(latencies)
        max_val = max(latencies)
        
        # Create bins
        bin_start = math.floor(min_val / self.histogram_bin_size_ms) * self.histogram_bin_size_ms
        bin_end = math.ceil(max_val / self.histogram_bin_size_ms) * self.histogram_bin_size_ms
        
        current_bin = bin_start
        while current_bin <= bin_end:
            bin_label = f"{current_bin:.1f}-{current_bin + self.histogram_bin_size_ms:.1f}ms"
            bin_count = sum(
                1 for latency in latencies 
                if current_bin <= latency < current_bin + self.histogram_bin_size_ms
            )
            if bin_count > 0:
                histogram[bin_label] = bin_count
            current_bin += self.histogram_bin_size_ms
        
        return histogram
    
    def _create_empty_statistics(self, session_id: str, threshold_ms: Optional[float]) -> LatencyStatistics:
        """Create empty statistics object"""
        return LatencyStatistics(
            session_id=session_id,
            total_measurements=0,
            pass_count=0,
            fail_count=0,
            error_count=0,
            timeout_count=0,
            pass_rate_percent=0.0,
            average_latency_ms=0.0,
            median_latency_ms=0.0,
            min_latency_ms=0.0,
            max_latency_ms=0.0,
            std_deviation_ms=0.0,
            percentile_95_ms=0.0,
            percentile_99_ms=0.0,
            threshold_ms=threshold_ms or self.default_threshold_ms,
            measurement_period_seconds=0.0,
            measurements=[],
            distribution_histogram={}
        )
    
    def _create_error_statistics(self, session_id: str, threshold_ms: Optional[float], 
                               error_message: str) -> LatencyStatistics:
        """Create error statistics object"""
        stats = self._create_empty_statistics(session_id, threshold_ms)
        stats.error_count = 1
        # Store error in metadata if we add it
        return stats
    
    def get_session_measurements(self, session_id: str) -> List[LatencyMeasurement]:
        """Get latency measurements for a session"""
        return self.latency_measurements.get(session_id, [])
    
    def get_session_statistics(self, session_id: str) -> Optional[LatencyStatistics]:
        """Get latency statistics for a session"""
        return self.session_statistics.get(session_id)
    
    def export_session_results(self, session_id: str) -> Dict[str, Any]:
        """
        Export comprehensive session results for reporting
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with full session results
        """
        try:
            measurements = self.get_session_measurements(session_id)
            statistics_obj = self.get_session_statistics(session_id)
            
            if not statistics_obj:
                logger.warning(f"No statistics found for session {session_id}")
                return {"error": "Session statistics not found", "session_id": session_id}
            
            return {
                "session_id": session_id,
                "summary": statistics_obj.to_dict(),
                "measurements": [m.to_dict() for m in measurements],
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "validation_service": {
                    "default_threshold_ms": self.default_threshold_ms,
                    "timeout_threshold_ms": self.timeout_threshold_ms,
                    "histogram_bin_size_ms": self.histogram_bin_size_ms
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to export session results for {session_id}: {e}")
            return {"error": str(e), "session_id": session_id}
    
    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session summary for API endpoints
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session results summary or None if not found
        """
        try:
            statistics_obj = self.get_session_statistics(session_id)
            if not statistics_obj:
                logger.warning(f"No statistics found for session {session_id}")
                return None
            
            # Convert LatencyStatistics to API-compatible format
            return {
                "session_id": session_id,
                "validation_type": "latency_based",
                "summary": {
                    "total_detections": statistics_obj.total_measurements,
                    "passed_detections": statistics_obj.pass_count,
                    "failed_detections": statistics_obj.fail_count,
                    "error_count": statistics_obj.error_count,
                    "timeout_count": statistics_obj.timeout_count,
                    "pass_rate": statistics_obj.pass_rate_percent,
                    "threshold_ms": statistics_obj.threshold_ms
                },
                "latency_metrics": {
                    "average_latency_ms": statistics_obj.average_latency_ms,
                    "median_latency_ms": statistics_obj.median_latency_ms,
                    "min_latency_ms": statistics_obj.min_latency_ms,
                    "max_latency_ms": statistics_obj.max_latency_ms,
                    "std_deviation_ms": statistics_obj.std_deviation_ms,
                    "percentile_95_ms": statistics_obj.percentile_95_ms,
                    "percentile_99_ms": statistics_obj.percentile_99_ms
                },
                "distribution": statistics_obj.distribution_histogram,
                "measurement_period_seconds": statistics_obj.measurement_period_seconds,
                
                # Legacy API compatibility fields
                "accuracy": statistics_obj.pass_rate_percent,  # Map pass rate to accuracy
                "precision": statistics_obj.pass_rate_percent,  # Map pass rate to precision  
                "recall": statistics_obj.pass_rate_percent,  # Map pass rate to recall
                "f1Score": statistics_obj.pass_rate_percent,  # Map pass rate to f1Score
                "truePositives": statistics_obj.pass_count,  # Passed detections
                "falsePositives": statistics_obj.fail_count,  # Failed detections
                "falseNegatives": statistics_obj.error_count + statistics_obj.timeout_count,  # Errors/timeouts
                "totalDetections": statistics_obj.total_measurements
            }
            
        except Exception as e:
            logger.error(f"Failed to get session summary for {session_id}: {e}")
            return None
    
    def calculate_session_metrics(self, session_id: str) -> Optional[LatencyStatistics]:
        """
        Calculate comprehensive session metrics
        
        Args:
            session_id: Session identifier
            
        Returns:
            LatencyStatistics object or None if not found
        """
        return self.get_session_statistics(session_id)
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get latency validation service status"""
        return {
            "default_threshold_ms": self.default_threshold_ms,
            "timeout_threshold_ms": self.timeout_threshold_ms,
            "histogram_bin_size_ms": self.histogram_bin_size_ms,
            "active_sessions": len(self.session_statistics),
            "total_measurements": sum(len(measurements) for measurements in self.latency_measurements.values()),
            "sessions_with_data": list(self.session_statistics.keys())
        }
    
    def cleanup_session(self, session_id: str) -> bool:
        """
        Cleanup session data
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if cleaned up successfully
        """
        try:
            removed_measurements = session_id in self.latency_measurements
            removed_statistics = session_id in self.session_statistics
            
            if removed_measurements:
                del self.latency_measurements[session_id]
            
            if removed_statistics:
                del self.session_statistics[session_id]
            
            logger.info(f"Cleaned up latency data for session {session_id}")
            return removed_measurements or removed_statistics
            
        except Exception as e:
            logger.error(f"Failed to cleanup session {session_id}: {e}")
            return False


# Global validation service instance
_validation_service: Optional[LatencyValidationService] = None


def get_validation_service(threshold_ms: float = 50.0) -> LatencyValidationService:
    """Get global latency validation service instance"""
    global _validation_service
    if _validation_service is None:
        _validation_service = LatencyValidationService(threshold_ms)
    return _validation_service


# Create global instance for easy access
latency_validation_service = get_validation_service()


# Export key classes and functions
__all__ = [
    "LatencyValidationService",
    "LatencyMeasurement",
    "LatencyStatistics", 
    "LatencyResult",
    "get_validation_service",
    "latency_validation_service"
]