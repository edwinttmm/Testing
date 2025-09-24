"""
Pydantic Schemas for HIL Ground Truth Timing System
==================================================

Enhanced schemas that support video timing synchronization and ground truth matching.
These schemas extend the existing enhanced schemas with HIL-specific fields.

Author: AI Backend Developer
Created: 2025-09-16
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Import base enums
from schemas_enhanced import ProcessingStatusEnum, VideoStatusEnum

class MatchQuality(str, Enum):
    """Quality levels for ground truth matching"""
    EXCELLENT = "excellent"
    GOOD = "good" 
    FAIR = "fair"
    POOR = "poor"

class ValidationResultEnum(str, Enum):
    """Validation result enumeration"""
    TRUE_POSITIVE = "TP"
    FALSE_POSITIVE = "FP"
    FALSE_NEGATIVE = "FN"
    PENDING = "PENDING"
    ERROR = "ERROR"

# Enhanced Test Session Schemas
class TestSessionCreateHIL(BaseModel):
    """Enhanced test session creation with HIL timing fields"""
    name: str = Field(..., min_length=1, max_length=255)
    project_id: str = Field(..., pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    video_id: str = Field(..., pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    tolerance_ms: int = Field(default=100, ge=1, le=10000)
    
    # HIL timing fields
    video_playback_start_time: Optional[float] = Field(None, description="Unix timestamp when video playback started")
    video_playback_duration: Optional[float] = Field(None, ge=0.0, description="Duration of video playback in seconds")
    ground_truth_count: Optional[int] = Field(None, ge=0, description="Number of ground truth objects in the video")
    
    # Test configuration
    test_configuration: Optional[Dict[str, Any]] = Field(default_factory=dict)
    expected_detections: Optional[int] = Field(None, ge=0)

class TestSessionResponseHIL(BaseModel):
    """Enhanced test session response with HIL timing fields"""
    id: str
    name: str
    project_id: str
    video_id: str
    tolerance_ms: int
    status: str
    
    # HIL timing fields
    video_playback_start_time: Optional[float]
    video_playback_duration: Optional[float]
    ground_truth_count: Optional[int]
    
    # Architecture fields
    test_configuration: Optional[Dict[str, Any]]
    expected_detections: Optional[int]
    actual_detections: Optional[int] 
    pass_fail_result: Optional[str]
    overall_score: Optional[float]
    
    # Timestamps
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class TestSessionUpdateHIL(BaseModel):
    """Enhanced test session update with HIL timing fields"""
    status: Optional[str]
    video_playback_start_time: Optional[float] = Field(None, description="Unix timestamp when video playback started")
    video_playback_duration: Optional[float] = Field(None, ge=0.0, description="Duration of video playback in seconds")
    ground_truth_count: Optional[int] = Field(None, ge=0, description="Number of ground truth objects in the video")
    actual_detections: Optional[int] = Field(None, ge=0)
    pass_fail_result: Optional[str]
    overall_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    completed_at: Optional[datetime]

# Enhanced Detection Event Schemas
class DetectionEventCreateHIL(BaseModel):
    """Enhanced detection event creation with HIL timing fields"""
    test_session_id: str = Field(..., pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    timestamp: float = Field(..., description="Unix timestamp of detection")
    confidence: float = Field(..., ge=0.0, le=1.0)
    class_label: str
    
    # HIL timing fields
    video_relative_timestamp: Optional[float] = Field(None, ge=0.0, description="Timestamp relative to video start (seconds)")
    actual_latency_ms: Optional[float] = Field(None, description="Actual measured latency from ground truth to detection")
    
    # Detection data
    bounding_box: Optional[Dict[str, float]] = Field(default_factory=dict)
    frame_number: Optional[int] = Field(None, ge=0)
    processing_time_ms: Optional[float] = Field(None, ge=0.0)
    model_version: Optional[str]
    ground_truth_match_id: Optional[str] = Field(None, pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

class DetectionEventResponseHIL(BaseModel):
    """Enhanced detection event response with HIL timing fields"""
    id: str
    test_session_id: str
    timestamp: float
    confidence: float
    class_label: str
    validation_result: str
    
    # HIL timing fields
    video_relative_timestamp: Optional[float]
    actual_latency_ms: Optional[float]
    ground_truth_match_id: Optional[str]
    
    # Detection data
    bounding_box: Optional[Dict[str, float]]
    frame_number: Optional[int]
    processing_time_ms: Optional[float]
    screenshot_path: Optional[str]
    model_version: Optional[str]
    
    created_at: datetime
    
    class Config:
        from_attributes = True

class DetectionEventUpdateHIL(BaseModel):
    """Enhanced detection event update with HIL timing fields"""
    validation_result: Optional[ValidationResultEnum]
    video_relative_timestamp: Optional[float] = Field(None, ge=0.0)
    actual_latency_ms: Optional[float]
    ground_truth_match_id: Optional[str] = Field(None, pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    processing_time_ms: Optional[float] = Field(None, ge=0.0)
    screenshot_path: Optional[str]

# Detection Comparison Schemas  
class DetectionComparisonCreate(BaseModel):
    """Detection comparison creation schema"""
    test_session_id: str = Field(..., pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    detection_event_id: Optional[str] = Field(None, pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    ground_truth_object_id: Optional[str] = Field(None, pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    
    # Matching results
    is_matched: bool = Field(default=False)
    matching_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score for the match")
    match_quality: Optional[MatchQuality] = Field(None, description="Quality level of the match")
    latency_ms: Optional[float] = Field(None, description="Latency between ground truth and detection")
    validation_result: ValidationResultEnum = Field(default=ValidationResultEnum.PENDING)

class DetectionComparisonResponse(BaseModel):
    """Detection comparison response schema"""
    id: str
    test_session_id: str
    detection_event_id: Optional[str]
    ground_truth_object_id: Optional[str]
    
    # Matching results
    is_matched: bool
    matching_confidence: Optional[float]
    match_quality: Optional[str]
    latency_ms: Optional[float]
    validation_result: str
    
    created_at: datetime
    
    class Config:
        from_attributes = True

class DetectionComparisonUpdate(BaseModel):
    """Detection comparison update schema"""
    is_matched: Optional[bool]
    matching_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    match_quality: Optional[MatchQuality]
    latency_ms: Optional[float]
    validation_result: Optional[ValidationResultEnum]

# Timing Analysis Schemas
class TimingAnalysisRequest(BaseModel):
    """Request schema for timing analysis"""
    test_session_id: str = Field(..., pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    tolerance_ms: Optional[int] = Field(100, ge=1, le=10000, description="Tolerance for timing matching in milliseconds")
    matching_threshold: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="Minimum confidence for automatic matching")

class TimingAnalysisResponse(BaseModel):
    """Response schema for timing analysis results"""
    test_session_id: str
    analysis_timestamp: datetime
    
    # Summary statistics
    total_ground_truth_objects: int
    total_detection_events: int
    matched_pairs: int
    unmatched_detections: int
    missed_ground_truth: int
    
    # Timing statistics
    mean_latency_ms: Optional[float]
    std_latency_ms: Optional[float]
    min_latency_ms: Optional[float]
    max_latency_ms: Optional[float]
    within_tolerance_count: int
    within_tolerance_percentage: float
    
    # Quality distribution
    quality_distribution: Dict[str, int] = Field(default_factory=dict)
    
    # Performance metrics
    precision: Optional[float]
    recall: Optional[float]
    f1_score: Optional[float]
    
    # Detailed results
    comparison_results: List[DetectionComparisonResponse] = Field(default_factory=list)

# Validation Schemas
class VideoTimingValidation(BaseModel):
    """Schema for validating video timing data"""
    video_id: str = Field(..., pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    video_duration: float = Field(..., gt=0.0, description="Total video duration in seconds")
    fps: float = Field(..., gt=0.0, description="Frames per second")
    
    @validator('fps')
    def validate_fps(cls, v):
        """Validate FPS is reasonable"""
        if v < 1.0 or v > 120.0:
            raise ValueError('FPS must be between 1.0 and 120.0')
        return v

class LatencyValidation(BaseModel):
    """Schema for validating latency measurements"""
    latency_ms: float = Field(..., description="Latency in milliseconds")
    tolerance_ms: int = Field(..., ge=1, le=10000, description="Acceptable tolerance")
    
    @validator('latency_ms')
    def validate_latency(cls, v):
        """Validate latency is within reasonable bounds"""
        if v < -1000.0 or v > 10000.0:
            raise ValueError('Latency must be between -1000ms and 10000ms')
        return v
    
    @property
    def is_within_tolerance(self) -> bool:
        """Check if latency is within tolerance"""
        return abs(self.latency_ms) <= self.tolerance_ms

# Bulk Operation Schemas
class BulkDetectionEventCreate(BaseModel):
    """Schema for bulk detection event creation"""
    test_session_id: str = Field(..., pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    detection_events: List[DetectionEventCreateHIL] = Field(..., min_items=1, max_items=1000)

class BulkDetectionComparisonCreate(BaseModel):
    """Schema for bulk detection comparison creation"""
    test_session_id: str = Field(..., pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    comparisons: List[DetectionComparisonCreate] = Field(..., min_items=1, max_items=1000)

# Status and Health Schemas
class HILSystemStatus(BaseModel):
    """HIL system status schema"""
    timestamp: datetime = Field(default_factory=datetime.now)
    database_status: str
    timing_sync_status: str
    active_test_sessions: int
    recent_comparisons: int
    system_health: str

class MigrationStatus(BaseModel):
    """Migration status schema"""
    migration_name: str
    status: str  # running, completed, failed
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str]
    results: Optional[Dict[str, Any]]