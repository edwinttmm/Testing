"""
Timestamp Conversion Utilities for HIL Video Timing Synchronization

This module provides utilities for converting between different timestamp formats
used in HIL (Hardware-in-the-Loop) validation tests, specifically for converting
between Unix timestamps from LabJack hardware and video-relative timestamps
for ground truth matching.

Key Features:
- Unix timestamp to video-relative time conversion
- Nanosecond precision handling
- Frame number calculation from video timing
- Timing quality assessment
- Comprehensive error handling and logging
"""

import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)


@dataclass
class TimestampConversionResult:
    """Result of timestamp conversion operation"""
    success: bool
    video_relative_timestamp: Optional[float]
    video_relative_timestamp_ns: Optional[str]
    actual_latency_ms: Optional[float]
    video_frame_number: Optional[int]
    timing_sync_quality: str
    error_message: Optional[str] = None
    conversion_accuracy_ns: Optional[float] = None


class TimestampConverter:
    """
    Utility class for converting timestamps between different formats used in HIL tests.
    
    Handles conversion between:
    - Unix timestamps (from LabJack hardware)
    - Video-relative timestamps (for ground truth matching)
    - Frame numbers (for video correlation)
    """
    
    def __init__(self):
        self.conversion_count = 0
        self.successful_conversions = 0
        self.failed_conversions = 0
        
        logger.info("Timestamp conversion utilities initialized")
    
    def unix_to_video_relative(self, unix_timestamp: float, video_start_time: float,
                             precision_ns: Optional[float] = None) -> TimestampConversionResult:
        """
        Convert Unix timestamp to video-relative timestamp.
        
        Args:
            unix_timestamp: Unix timestamp from LabJack or other hardware (seconds since epoch)
            video_start_time: Video playback start time (seconds since epoch)
            precision_ns: Expected timing precision in nanoseconds
            
        Returns:
            TimestampConversionResult with conversion details
        """
        try:
            self.conversion_count += 1
            
            # Validate inputs
            if unix_timestamp <= 0:
                return self._create_error_result("Invalid Unix timestamp")
            
            if video_start_time <= 0:
                return self._create_error_result("Invalid video start time")
            
            if unix_timestamp < video_start_time:
                return self._create_error_result("Unix timestamp is before video start time")
            
            # Calculate video-relative time: offset = unix_timestamp - video_start_time
            video_relative_timestamp = unix_timestamp - video_start_time
            
            # Convert to nanoseconds for high precision
            video_relative_timestamp_ns = int(video_relative_timestamp * 1e9)

            # ✅ CORRECTED: actual_latency_ms should be NULL here
            # This function ONLY converts timestamps - it does NOT calculate latency
            #
            # Processing latency must be calculated from actual detection pipeline timing:
            # - Option 1: Use t3_processing_time_ms from detection event (most accurate)
            # - Option 2: Use processing_time_ms from detection metadata
            # - Option 3: Use calibrated system latency from HILSystemConfig
            #
            # ❌ REMOVED: actual_latency_ms = 50.0  (was incorrect hardcoded value)
            # ❌ REMOVED: actual_latency_ms = video_relative_timestamp * 1000  (was completely wrong - used video position as latency!)
            #
            # The calling code should populate actual_latency_ms from detection metadata,
            # not from this timestamp conversion function.
            actual_latency_ms = None  # Caller must provide actual measured latency
            
            # Determine timing quality based on precision
            timing_quality = self._assess_timing_quality(precision_ns or 1000000)  # Default to 1ms
            
            # Calculate conversion accuracy
            conversion_accuracy_ns = precision_ns or 1000000
            
            self.successful_conversions += 1

            logger.debug(f"Converted Unix {unix_timestamp:.6f} to video-relative {video_relative_timestamp:.6f}s "
                        f"(video position: {video_relative_timestamp*1000:.3f}ms)")
            
            return TimestampConversionResult(
                success=True,
                video_relative_timestamp=video_relative_timestamp,
                video_relative_timestamp_ns=str(video_relative_timestamp_ns),
                actual_latency_ms=actual_latency_ms,
                video_frame_number=None,  # Will be calculated separately if needed
                timing_sync_quality=timing_quality,
                conversion_accuracy_ns=conversion_accuracy_ns
            )
            
        except Exception as e:
            self.failed_conversions += 1
            logger.error(f"Error converting Unix timestamp to video-relative: {e}")
            return self._create_error_result(f"Conversion error: {e}")
    
    def calculate_frame_number(self, video_relative_timestamp: float, fps: float) -> Optional[int]:
        """
        Calculate video frame number from video-relative timestamp.
        
        Args:
            video_relative_timestamp: Video-relative timestamp in seconds
            fps: Video frame rate (frames per second)
            
        Returns:
            Frame number (0-based) or None if calculation fails
        """
        try:
            if video_relative_timestamp < 0:
                logger.warning(f"Negative video-relative timestamp: {video_relative_timestamp}")
                return None
            
            if fps <= 0:
                logger.warning(f"Invalid frame rate: {fps}")
                return None
            
            # Calculate frame number (0-based)
            frame_number = int(video_relative_timestamp * fps)
            
            logger.debug(f"Calculated frame number {frame_number} for time {video_relative_timestamp:.6f}s at {fps}fps")
            return frame_number
            
        except Exception as e:
            logger.error(f"Error calculating frame number: {e}")
            return None
    
    def video_relative_to_unix(self, video_relative_timestamp: float, video_start_time: float) -> Optional[float]:
        """
        Convert video-relative timestamp back to Unix timestamp.
        
        Args:
            video_relative_timestamp: Video-relative timestamp in seconds
            video_start_time: Video playback start time (seconds since epoch)
            
        Returns:
            Unix timestamp or None if conversion fails
        """
        try:
            if video_relative_timestamp < 0:
                logger.warning(f"Negative video-relative timestamp: {video_relative_timestamp}")
                return None
            
            if video_start_time <= 0:
                logger.warning(f"Invalid video start time: {video_start_time}")
                return None
            
            # Convert back: unix_timestamp = video_start_time + video_relative_timestamp
            unix_timestamp = video_start_time + video_relative_timestamp
            
            logger.debug(f"Converted video-relative {video_relative_timestamp:.6f}s back to Unix {unix_timestamp:.6f}")
            return unix_timestamp
            
        except Exception as e:
            logger.error(f"Error converting video-relative to Unix timestamp: {e}")
            return None
    
    def validate_timing_consistency(self, detections: list, tolerance_ms: float = 10.0) -> Dict[str, Any]:
        """
        Validate timing consistency across multiple detection events.
        
        Args:
            detections: List of detection events with timing data
            tolerance_ms: Maximum allowed timing drift in milliseconds
            
        Returns:
            Dictionary with validation results
        """
        try:
            if not detections:
                return {"valid": True, "reason": "No detections to validate"}
            
            # Extract video-relative timestamps
            timestamps = []
            for detection in detections:
                ts = getattr(detection, 'video_relative_timestamp', None)
                if ts is not None:
                    timestamps.append(ts)
            
            if len(timestamps) < 2:
                return {"valid": True, "reason": "Insufficient data for validation"}
            
            # Calculate timing intervals
            intervals = []
            for i in range(1, len(timestamps)):
                interval = timestamps[i] - timestamps[i-1]
                intervals.append(interval)
            
            # Check for consistency
            avg_interval = sum(intervals) / len(intervals)
            max_deviation = max(abs(interval - avg_interval) for interval in intervals)
            max_deviation_ms = max_deviation * 1000
            
            is_valid = max_deviation_ms <= tolerance_ms
            
            result = {
                "valid": is_valid,
                "detection_count": len(detections),
                "timestamp_count": len(timestamps),
                "average_interval_s": avg_interval,
                "max_deviation_ms": max_deviation_ms,
                "tolerance_ms": tolerance_ms,
                "reason": "Timing consistent" if is_valid else f"Timing drift exceeds tolerance ({max_deviation_ms:.1f}ms > {tolerance_ms}ms)"
            }
            
            logger.info(f"Timing validation: {result['reason']}")
            return result
            
        except Exception as e:
            logger.error(f"Error validating timing consistency: {e}")
            return {"valid": False, "reason": f"Validation error: {e}"}
    
    def _assess_timing_quality(self, precision_ns: float) -> str:
        """
        Assess timing synchronization quality based on precision.
        
        Args:
            precision_ns: Timing precision in nanoseconds
            
        Returns:
            Quality assessment: 'high', 'medium', 'low', or 'unknown'
        """
        if precision_ns <= 100000:  # <= 100μs
            return "high"
        elif precision_ns <= 1000000:  # <= 1ms
            return "medium"
        elif precision_ns <= 10000000:  # <= 10ms
            return "low"
        else:
            return "unknown"
    
    def _create_error_result(self, error_message: str) -> TimestampConversionResult:
        """Create error result for failed conversions"""
        self.failed_conversions += 1
        return TimestampConversionResult(
            success=False,
            video_relative_timestamp=None,
            video_relative_timestamp_ns=None,
            actual_latency_ms=None,
            video_frame_number=None,
            timing_sync_quality="unknown",
            error_message=error_message
        )
    
    def get_conversion_statistics(self) -> Dict[str, Any]:
        """Get timestamp conversion statistics"""
        success_rate = (self.successful_conversions / max(1, self.conversion_count)) * 100
        
        return {
            "total_conversions": self.conversion_count,
            "successful_conversions": self.successful_conversions,
            "failed_conversions": self.failed_conversions,
            "success_rate_percent": success_rate,
            "converter_active": True
        }


# Global converter instance
_timestamp_converter: Optional[TimestampConverter] = None


def get_timestamp_converter() -> TimestampConverter:
    """Get global timestamp converter instance (singleton)"""
    global _timestamp_converter
    if _timestamp_converter is None:
        _timestamp_converter = TimestampConverter()
    return _timestamp_converter


# Convenience functions for direct use
def convert_unix_to_video_relative(unix_timestamp: float, video_start_time: float,
                                 precision_ns: Optional[float] = None) -> TimestampConversionResult:
    """Convert Unix timestamp to video-relative timestamp"""
    converter = get_timestamp_converter()
    return converter.unix_to_video_relative(unix_timestamp, video_start_time, precision_ns)


def calculate_frame_number_from_time(video_relative_timestamp: float, fps: float) -> Optional[int]:
    """Calculate frame number from video-relative timestamp"""
    converter = get_timestamp_converter()
    return converter.calculate_frame_number(video_relative_timestamp, fps)


def convert_video_relative_to_unix(video_relative_timestamp: float, video_start_time: float) -> Optional[float]:
    """Convert video-relative timestamp back to Unix timestamp"""
    converter = get_timestamp_converter()
    return converter.video_relative_to_unix(video_relative_timestamp, video_start_time)


def validate_detection_timing_consistency(detections: list, tolerance_ms: float = 10.0) -> Dict[str, Any]:
    """Validate timing consistency across detection events"""
    converter = get_timestamp_converter()
    return converter.validate_timing_consistency(detections, tolerance_ms)


# Additional utility functions
def format_timestamp_for_display(timestamp: float, precision: str = "ms") -> str:
    """
    Format timestamp for display purposes.
    
    Args:
        timestamp: Timestamp in seconds
        precision: Display precision ('ms', 'us', 'ns')
        
    Returns:
        Formatted timestamp string
    """
    try:
        if precision == "ms":
            return f"{timestamp * 1000:.3f}ms"
        elif precision == "us":
            return f"{timestamp * 1000000:.1f}μs"
        elif precision == "ns":
            return f"{timestamp * 1000000000:.0f}ns"
        else:
            return f"{timestamp:.6f}s"
    except Exception:
        return "Invalid timestamp"


def calculate_timing_drift(timestamps: list, expected_interval: float) -> Dict[str, float]:
    """
    Calculate timing drift from expected intervals.
    
    Args:
        timestamps: List of timestamps in seconds
        expected_interval: Expected interval between timestamps in seconds
        
    Returns:
        Dictionary with drift statistics
    """
    try:
        if len(timestamps) < 2:
            return {"drift_ms": 0.0, "max_drift_ms": 0.0, "avg_drift_ms": 0.0}
        
        drifts = []
        for i in range(1, len(timestamps)):
            actual_interval = timestamps[i] - timestamps[i-1]
            drift = actual_interval - expected_interval
            drifts.append(drift)
        
        drift_ms = [d * 1000 for d in drifts]
        
        return {
            "drift_ms": drift_ms[-1] if drift_ms else 0.0,  # Latest drift
            "max_drift_ms": max(abs(d) for d in drift_ms) if drift_ms else 0.0,
            "avg_drift_ms": sum(drift_ms) / len(drift_ms) if drift_ms else 0.0,
            "drift_count": len(drift_ms)
        }
        
    except Exception as e:
        logger.error(f"Error calculating timing drift: {e}")
        return {"drift_ms": 0.0, "max_drift_ms": 0.0, "avg_drift_ms": 0.0}


# Export key components
__all__ = [
    "TimestampConverter",
    "TimestampConversionResult",
    "get_timestamp_converter",
    "convert_unix_to_video_relative",
    "calculate_frame_number_from_time",
    "convert_video_relative_to_unix",
    "validate_detection_timing_consistency",
    "format_timestamp_for_display",
    "calculate_timing_drift"
]