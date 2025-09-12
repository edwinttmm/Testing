"""
Timing Validation Schemas for HIL Testing

Pydantic schemas for precision timing validation, frame synchronization,
and HIL compliance verification in the AI Model Validation Platform.

Supports:
- Sub-millisecond timing validation
- Frame-accurate synchronization
- Hardware timing integration
- Drift compensation monitoring
- Performance reporting

PRD Compliance:
- Module 3.1: HIL timing requirements
- Module 4.1: Latency analysis schemas
- Module 4.2: Timing accuracy reports
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
import re

from .schemas import CamelCaseModel  # Import base camelCase model

# Timing validation constants
HIL_TIMING_PRECISION_MS = 0.1  # Sub-millisecond requirement
MAX_DRIFT_TOLERANCE_PPM = 100   # Parts per million drift tolerance


class TimingAccuracyLevel(str, Enum):
    """Timing accuracy levels for validation"""
    HIGH_PRECISION = "high_precision"      # < 0.1ms (HIL requirement)
    STANDARD = "standard"                  # 0.1ms - 1ms
    BASIC = "basic"                        # > 1ms


class TimingValidationStatus(str, Enum):
    """Timing validation status values"""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    REQUIRES_CALIBRATION = "requires_calibration"


class DriftCompensationStatus(str, Enum):
    """Drift compensation status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    CALIBRATING = "calibrating"
    ERROR = "error"


# Base timing schemas
class TimingCalibrationSchema(CamelCaseModel):
    """Timing system calibration data"""
    clock_resolution_ns: float = Field(..., description="Clock resolution in nanoseconds")
    drift_rate_ppm: float = Field(..., description="Drift rate in parts per million")
    accuracy_estimate_ns: float = Field(..., description="Accuracy estimate in nanoseconds")
    calibration_timestamp: float = Field(..., description="Calibration timestamp")
    sample_count: int = Field(..., description="Number of calibration samples")
    jitter_std_ns: float = Field(..., description="Jitter standard deviation in nanoseconds")
    monotonic_clock_source: str = Field(..., description="Monotonic clock source identifier")


class TimingSyncPointSchema(CamelCaseModel):
    """Timing synchronization point data"""
    sync_id: str = Field(..., description="Sync point identifier")
    monotonic_time: float = Field(..., description="Monotonic timestamp")
    system_time: float = Field(..., description="System timestamp")
    hardware_time: Optional[float] = Field(None, description="Hardware timestamp if available")
    video_time: Optional[float] = Field(None, description="Video timestamp if available")
    calibration_offset: float = Field(0.0, description="Calibration offset")
    accuracy_ns: float = Field(0.0, description="Timing accuracy estimate")


class FrameTimestampSchema(CamelCaseModel):
    """Frame-accurate timestamp data"""
    frame_number: int = Field(..., description="Video frame number")
    video_timestamp_ms: float = Field(..., description="Video timestamp in milliseconds")
    system_timestamp_ns: int = Field(..., description="System timestamp in nanoseconds")
    monotonic_timestamp_ns: int = Field(..., description="Monotonic timestamp in nanoseconds")
    frame_rate: float = Field(..., description="Video frame rate")
    interpolated: bool = Field(False, description="Whether timestamp was interpolated")
    accuracy_estimate_ns: float = Field(0.0, description="Timestamp accuracy estimate")


class LatencyMeasurementSchema(CamelCaseModel):
    """Precision latency measurement"""
    measurement_id: str = Field(..., description="Unique measurement identifier")
    start_timestamp_ns: int = Field(..., description="Start timestamp in nanoseconds")
    end_timestamp_ns: int = Field(..., description="End timestamp in nanoseconds")
    latency_ns: int = Field(..., description="Latency in nanoseconds")
    latency_ms: float = Field(..., description="Latency in milliseconds")
    accuracy_estimate_ns: float = Field(..., description="Measurement accuracy estimate")
    measurement_type: str = Field(..., description="Type of latency measurement")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# Video timing schemas
class VideoTimingStartRequest(CamelCaseModel):
    """Request to start video timing"""
    session_id: str = Field(..., description="Test session identifier")
    video_id: str = Field(..., description="Video identifier")
    video_metadata: Optional[Dict[str, Any]] = Field(None, description="Video metadata (fps, duration, etc.)")
    enable_frame_sync: bool = Field(True, description="Enable frame synchronization")
    enable_drift_compensation: bool = Field(True, description="Enable drift compensation")


class VideoTimingResponse(CamelCaseModel):
    """Video timing start response"""
    session_id: str = Field(..., description="Test session identifier")
    video_id: str = Field(..., description="Video identifier")
    start_timestamp: float = Field(..., description="Video start timestamp")
    start_timestamp_ns: str = Field(..., description="Nanosecond precision start timestamp")
    sync_point_id: str = Field(..., description="Timing sync point identifier")
    timing_accuracy_ns: float = Field(..., description="Timing accuracy estimate")
    frame_count: Optional[int] = Field(None, description="Total frame count if known")
    frame_sync_enabled: bool = Field(..., description="Frame synchronization status")


class LatencyCalculationRequest(CamelCaseModel):
    """Request for latency calculation"""
    session_id: str = Field(..., description="Test session identifier")
    detection_timestamp: float = Field(..., description="Detection event timestamp")
    detection_metadata: Optional[Dict[str, Any]] = Field(None, description="Detection metadata")
    require_frame_accuracy: bool = Field(False, description="Require frame-accurate calculation")


class LatencyCalculationResponse(CamelCaseModel):
    """Latency calculation response"""
    measurement_id: str = Field(..., description="Measurement identifier")
    session_id: str = Field(..., description="Test session identifier")
    video_id: str = Field(..., description="Video identifier")
    latency_ms: float = Field(..., description="Calculated latency in milliseconds")
    latency_ns: int = Field(..., description="Calculated latency in nanoseconds")
    frame_number: Optional[int] = Field(None, description="Associated frame number")
    frame_timestamp: Optional[float] = Field(None, description="Frame timestamp")
    accuracy_estimate_ns: float = Field(..., description="Accuracy estimate")
    precision_indicator: str = Field(..., description="Precision level indicator")


# Timing validation schemas
class TimingValidationCriteriaSchema(CamelCaseModel):
    """Criteria for timing validation"""
    max_latency_ms: float = Field(100.0, description="Maximum acceptable latency in milliseconds")
    max_accuracy_deviation_ns: float = Field(100000.0, description="Maximum accuracy deviation in nanoseconds")
    max_drift_rate_ppm: float = Field(100.0, description="Maximum drift rate in parts per million")
    min_calibration_validity_hours: float = Field(24.0, description="Minimum calibration validity in hours")
    required_sample_size: int = Field(10, description="Required sample size for validation")
    confidence_level: float = Field(0.95, ge=0.5, le=0.99, description="Statistical confidence level")
    
    @field_validator('max_latency_ms')
    @classmethod
    def validate_max_latency(cls, v):
        if v <= 0:
            raise ValueError('Maximum latency must be positive')
        return v
    
    @field_validator('max_accuracy_deviation_ns')
    @classmethod
    def validate_accuracy_deviation(cls, v):
        if v <= 0:
            raise ValueError('Accuracy deviation must be positive')
        return v


class TimingValidationRequest(CamelCaseModel):
    """Request for timing validation"""
    session_id: str = Field(..., description="Test session identifier")
    validation_criteria: Optional[TimingValidationCriteriaSchema] = Field(None, description="Custom validation criteria")
    include_statistical_analysis: bool = Field(True, description="Include statistical analysis")
    generate_report: bool = Field(False, description="Generate detailed report")


class TimingValidationResultSchema(CamelCaseModel):
    """Result of timing validation"""
    validation_id: str = Field(..., description="Validation identifier")
    session_id: str = Field(..., description="Test session identifier")
    timestamp: str = Field(..., description="Validation timestamp")
    criteria: TimingValidationCriteriaSchema = Field(..., description="Validation criteria used")
    
    # Validation results
    meets_hil_requirements: bool = Field(..., description="Whether HIL requirements are met")
    accuracy_validation_passed: bool = Field(..., description="Accuracy validation result")
    drift_validation_passed: bool = Field(..., description="Drift validation result")
    calibration_validation_passed: bool = Field(..., description="Calibration validation result")
    statistical_validation_passed: bool = Field(..., description="Statistical validation result")
    
    # Detailed metrics
    measured_accuracy_ns: float = Field(..., description="Measured timing accuracy")
    measured_drift_ppm: float = Field(..., description="Measured drift rate")
    sample_count: int = Field(..., description="Number of samples analyzed")
    latency_statistics: Dict[str, float] = Field(default_factory=dict, description="Latency statistics")
    
    # Issues and recommendations
    validation_issues: List[str] = Field(default_factory=list, description="Validation issues found")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for improvement")
    measurement_ids: List[str] = Field(default_factory=list, description="Related measurement IDs")


# Performance reporting schemas
class TimingPerformanceMetricsSchema(CamelCaseModel):
    """Timing performance metrics"""
    total_measurements: int = Field(0, description="Total number of measurements")
    accuracy_violations: int = Field(0, description="Number of accuracy violations")
    drift_corrections: int = Field(0, description="Number of drift corrections applied")
    calibration_age_hours: float = Field(0.0, description="Age of current calibration in hours")
    average_latency_ms: float = Field(0.0, description="Average latency in milliseconds")
    max_latency_ms: float = Field(0.0, description="Maximum latency observed")
    min_latency_ms: float = Field(0.0, description="Minimum latency observed")
    latency_std_dev_ms: float = Field(0.0, description="Latency standard deviation")


class SystemHealthStatusSchema(CamelCaseModel):
    """System health status"""
    overall_health_score: float = Field(..., ge=0.0, le=100.0, description="Overall health score (0-100)")
    timing_accuracy_status: TimingAccuracyLevel = Field(..., description="Timing accuracy level")
    validation_status: TimingValidationStatus = Field(..., description="Validation status")
    drift_compensation_status: DriftCompensationStatus = Field(..., description="Drift compensation status")
    calibration_status: str = Field(..., description="Calibration status")
    hil_compliance: bool = Field(..., description="HIL compliance status")


class TimingPerformanceReportSchema(CamelCaseModel):
    """Comprehensive timing performance report"""
    report_id: str = Field(..., description="Report identifier")
    session_id: str = Field(..., description="Test session identifier")
    generated_at: str = Field(..., description="Report generation timestamp")
    
    # System status
    system_health: SystemHealthStatusSchema = Field(..., description="System health status")
    timing_metrics: TimingPerformanceMetricsSchema = Field(..., description="Performance metrics")
    
    # Calibration information
    calibration_data: Optional[TimingCalibrationSchema] = Field(None, description="Current calibration data")
    calibration_age_hours: float = Field(0.0, description="Calibration age in hours")
    
    # Validation results
    validation_results: List[TimingValidationResultSchema] = Field(default_factory=list, description="Validation results")
    overall_hil_compliance: bool = Field(..., description="Overall HIL compliance status")
    
    # Analysis data
    latency_distribution: Dict[str, Any] = Field(default_factory=dict, description="Latency distribution analysis")
    timing_trends: Dict[str, Any] = Field(default_factory=dict, description="Timing trend analysis")
    
    # Recommendations
    recommended_actions: List[str] = Field(default_factory=list, description="Recommended actions")
    critical_issues: List[str] = Field(default_factory=list, description="Critical issues requiring attention")


# System configuration schemas
class PrecisionTimingConfigSchema(CamelCaseModel):
    """Precision timing system configuration"""
    enable_precision_timing: bool = Field(True, description="Enable precision timing features")
    enable_drift_compensation: bool = Field(True, description="Enable drift compensation")
    enable_frame_synchronization: bool = Field(True, description="Enable frame synchronization")
    calibration_interval_hours: float = Field(24.0, description="Calibration interval in hours")
    drift_check_interval_minutes: float = Field(60.0, description="Drift check interval in minutes")
    accuracy_requirement_ns: float = Field(100000.0, description="Accuracy requirement in nanoseconds")


class TimingSystemStatusSchema(CamelCaseModel):
    """Current timing system status"""
    service_active: bool = Field(..., description="Whether timing service is active")
    precision_timing_available: bool = Field(..., description="Whether precision timing is available")
    current_accuracy_ns: float = Field(..., description="Current timing accuracy in nanoseconds")
    calibration_status: str = Field(..., description="Calibration status")
    drift_compensation_active: bool = Field(..., description="Whether drift compensation is active")
    active_sessions: int = Field(0, description="Number of active timing sessions")
    total_measurements: int = Field(0, description="Total measurements performed")


# API endpoint schemas
class CalibrationRequest(CamelCaseModel):
    """Request for timing system calibration"""
    force_recalibration: bool = Field(False, description="Force recalibration even if recent")
    calibration_sample_size: int = Field(1000, ge=100, le=10000, description="Number of calibration samples")


class CalibrationResponse(CamelCaseModel):
    """Timing calibration response"""
    calibration_id: str = Field(..., description="Calibration identifier")
    calibration_data: TimingCalibrationSchema = Field(..., description="Calibration results")
    meets_hil_requirements: bool = Field(..., description="Whether calibration meets HIL requirements")
    calibration_issues: List[str] = Field(default_factory=list, description="Calibration issues if any")


class DriftCompensationRequest(CamelCaseModel):
    """Request for drift compensation"""
    session_id: str = Field(..., description="Test session identifier")
    force_recalibration: bool = Field(False, description="Force drift recalibration")


class DriftCompensationResponse(CamelCaseModel):
    """Drift compensation response"""
    compensation_applied: bool = Field(..., description="Whether compensation was applied")
    current_drift_ppm: float = Field(..., description="Current drift rate in PPM")
    compensation_offset_ns: float = Field(..., description="Applied compensation offset")
    drift_status: DriftCompensationStatus = Field(..., description="Drift compensation status")


# Frame-accurate seeking schemas
class FrameSeekRequest(CamelCaseModel):
    """Request for frame-accurate seeking"""
    video_id: str = Field(..., description="Video identifier")
    target_frame: Optional[int] = Field(None, description="Target frame number")
    target_timestamp_ms: Optional[float] = Field(None, description="Target timestamp in milliseconds")
    seek_accuracy: TimingAccuracyLevel = Field(TimingAccuracyLevel.HIGH_PRECISION, description="Required seek accuracy")
    
    @field_validator('target_frame')
    @classmethod
    def validate_target_frame(cls, v, info):
        if v is not None and v < 0:
            raise ValueError('Target frame must be non-negative')
        return v
    
    @field_validator('target_timestamp_ms')
    @classmethod
    def validate_target_timestamp(cls, v, info):
        if v is not None and v < 0:
            raise ValueError('Target timestamp must be non-negative')
        return v


class FrameSeekResponse(CamelCaseModel):
    """Frame-accurate seek response"""
    video_id: str = Field(..., description="Video identifier")
    actual_frame: int = Field(..., description="Actual frame reached")
    actual_timestamp_ms: float = Field(..., description="Actual timestamp in milliseconds")
    seek_accuracy_ns: float = Field(..., description="Achieved seek accuracy")
    frame_timestamp: FrameTimestampSchema = Field(..., description="Frame timestamp data")
    seek_successful: bool = Field(..., description="Whether seek was successful")


# Export schemas for API documentation
__all__ = [
    'TimingCalibrationSchema',
    'TimingSyncPointSchema', 
    'FrameTimestampSchema',
    'LatencyMeasurementSchema',
    'VideoTimingStartRequest',
    'VideoTimingResponse',
    'LatencyCalculationRequest',
    'LatencyCalculationResponse',
    'TimingValidationCriteriaSchema',
    'TimingValidationRequest',
    'TimingValidationResultSchema',
    'TimingPerformanceMetricsSchema',
    'SystemHealthStatusSchema',
    'TimingPerformanceReportSchema',
    'PrecisionTimingConfigSchema',
    'TimingSystemStatusSchema',
    'CalibrationRequest',
    'CalibrationResponse',
    'DriftCompensationRequest',
    'DriftCompensationResponse',
    'FrameSeekRequest',
    'FrameSeekResponse',
    'TimingAccuracyLevel',
    'TimingValidationStatus',
    'DriftCompensationStatus'
]