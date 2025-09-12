"""
Pydantic schemas for the unified video validation system.

These schemas provide consistent data validation and serialization
for the video validation API endpoints and ensure type safety.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

class VideoValidationStatus(str, Enum):
    """Unified video validation status enumeration"""
    # Initial states
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSING_FAILED = "processing_failed"
    
    # Annotation states  
    ANNOTATED = "annotated"
    
    # Validation states
    VALIDATING = "validating"
    VALIDATION_FAILED = "validation_failed"
    VALIDATED = "validated"
    
    # Testing readiness
    READY_FOR_TESTING = "ready_for_testing"
    IN_TESTING = "in_testing"
    TESTED = "tested"
    
    # Final states
    ARCHIVED = "archived"
    ERROR = "error"

class ValidationStatus(str, Enum):
    """Validation workflow status"""
    PENDING = "pending"
    PROCESSING = "processing"
    PENDING_VALIDATION = "pending_validation"
    VALIDATING = "validating"
    VALIDATED = "validated"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"

class ValidationType(str, Enum):
    """Type of validation performed"""
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    HYBRID = "hybrid"

class ValidationResultType(str, Enum):
    """Result of validation process"""
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    PROCESSING = "processing"

# Core Response Models

class ValidationScores(BaseModel):
    """Detailed validation scores"""
    ground_truth_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    technical_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    content_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    overall_score: Optional[float] = Field(None, ge=0.0, le=1.0)

class ValidationResultResponse(BaseModel):
    """Response model for validation results"""
    id: str
    video_id: str
    validation_criteria_id: Optional[str] = None
    validation_type: ValidationType
    overall_result: ValidationResultType
    scores: Optional[ValidationScores] = None
    criteria_met: Optional[Dict[str, Any]] = None
    validation_notes: Optional[str] = None
    validated_by: Optional[str] = None
    created_at: datetime
    message: Optional[str] = None  # For async processing responses

    class Config:
        from_attributes = True

class VideoStatusResponse(BaseModel):
    """Comprehensive video status response"""
    video_id: str
    status: VideoValidationStatus
    validation_status: ValidationStatus
    validation_type: Optional[ValidationType] = None
    validated_at: Optional[datetime] = None
    validated_by: Optional[str] = None
    
    # HIL testing readiness
    hil_testing_ready: bool = False
    hil_testing_approved_by: Optional[str] = None
    hil_testing_approved_at: Optional[datetime] = None
    
    # Ground truth information
    ground_truth_count: int = 0
    ground_truth_quality_score: Optional[float] = None
    
    # Latest validation result
    validation_result: Optional[ValidationResultResponse] = None

    class Config:
        from_attributes = True

# Request Models

class VideoStatusUpdate(BaseModel):
    """Request model for updating video status"""
    status: VideoValidationStatus
    reason: str = Field(..., min_length=1, max_length=200)
    metadata: Optional[Dict[str, Any]] = None

    @validator('reason')
    def validate_reason(cls, v):
        if not v or not v.strip():
            raise ValueError('Reason cannot be empty')
        return v.strip()

class ValidationRequest(BaseModel):
    """Request model for video validation"""
    validation_type: ValidationType
    criteria_id: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)
    
    # For manual validation
    manual_result: Optional[ValidationResultType] = None
    scores: Optional[ValidationScores] = None
    
    @validator('manual_result')
    def validate_manual_result(cls, v, values):
        if values.get('validation_type') == ValidationType.MANUAL and not v:
            raise ValueError('Manual result required for manual validation')
        return v

class BatchStatusUpdate(BaseModel):
    """Request model for batch status updates"""
    video_ids: List[str] = Field(..., min_items=1, max_items=100)
    new_status: VideoValidationStatus
    reason: str = Field(..., min_length=1, max_length=200)
    metadata: Optional[Dict[str, Any]] = None

# Validation Criteria Models

class ValidationCriteriaRequest(BaseModel):
    """Request model for creating/updating validation criteria"""
    project_id: Optional[str] = None  # None = global criteria
    
    # Ground truth quality requirements
    min_detection_count: int = Field(5, ge=0, le=1000)
    min_confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)
    min_frame_coverage_percent: float = Field(80.0, ge=0.0, le=100.0)
    
    # Technical requirements
    min_duration_seconds: float = Field(10.0, ge=1.0, le=3600.0)
    max_duration_seconds: float = Field(300.0, ge=10.0, le=7200.0)
    required_resolution_min: str = Field("640x480", pattern=r'^\d+x\d+$')
    min_fps: float = Field(24.0, ge=1.0, le=120.0)
    
    # Content requirements
    required_vru_types: Optional[List[str]] = Field(
        default=["pedestrian", "cyclist", "motorcyclist"],
        max_items=10
    )
    min_scene_complexity_score: float = Field(0.5, ge=0.0, le=1.0)

    @validator('max_duration_seconds')
    def validate_duration_range(cls, v, values):
        min_duration = values.get('min_duration_seconds', 10.0)
        if v <= min_duration:
            raise ValueError('Max duration must be greater than min duration')
        return v

    @validator('required_vru_types')
    def validate_vru_types(cls, v):
        if v:
            valid_types = {"pedestrian", "cyclist", "motorcyclist", "wheelchair", "scooter"}
            invalid_types = set(v) - valid_types
            if invalid_types:
                raise ValueError(f'Invalid VRU types: {invalid_types}')
        return v

class ValidationCriteriaResponse(BaseModel):
    """Response model for validation criteria"""
    id: str
    project_id: Optional[str] = None
    
    # Requirements (same as request)
    min_detection_count: int
    min_confidence_threshold: float
    min_frame_coverage_percent: float
    min_duration_seconds: float
    max_duration_seconds: float
    required_resolution_min: str
    min_fps: float
    required_vru_types: Optional[List[str]]
    min_scene_complexity_score: float
    
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Status Transition Models

class StatusTransitionHistory(BaseModel):
    """Status transition history entry"""
    id: str
    video_id: str
    from_status: str
    to_status: str
    transition_reason: str
    triggered_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

# HIL Testing Models

class HILTestingApproval(BaseModel):
    """Request model for HIL testing approval"""
    notes: Optional[str] = Field(None, max_length=500)

# Queue and Batch Models

class ValidationQueueStatus(BaseModel):
    """Current validation queue status"""
    pending_validation: int = 0
    currently_validating: int = 0
    validation_failed: int = 0
    total_in_queue: int = 0

# Compatibility Models (for legacy frontend support)

class LegacyVideoStatusResponse(BaseModel):
    """Legacy video status response for backward compatibility"""
    id: str
    status: str  # Maps to new status system
    processing_status: str  # Computed from new status
    ground_truth_generated: bool  # Computed from new status
    validation_status: Optional[str] = None
    hil_testing_ready: bool = False

    @validator('processing_status', pre=False, always=True)
    def compute_processing_status(cls, v, values):
        """Compute legacy processing_status from new status"""
        status_map = {
            "uploaded": "pending",
            "processing": "processing", 
            "annotated": "completed",
            "validated": "completed",
            "ready_for_testing": "completed",
            "in_testing": "completed",
            "tested": "completed",
            "processing_failed": "failed",
            "validation_failed": "failed",
            "error": "failed"
        }
        new_status = values.get('status', 'uploaded')
        return status_map.get(new_status, "pending")

    @validator('ground_truth_generated', pre=False, always=True)  
    def compute_ground_truth_generated(cls, v, values):
        """Compute legacy ground_truth_generated from new status"""
        new_status = values.get('status', 'uploaded')
        return new_status in ["annotated", "validated", "ready_for_testing", "in_testing", "tested"]

# Error Models

class ValidationError(BaseModel):
    """Validation error details"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    field: Optional[str] = None

class BatchOperationResult(BaseModel):
    """Result of batch operations"""
    success_count: int = 0
    error_count: int = 0
    errors: List[Dict[str, str]] = []
    total_processed: int = 0

# Utility Models

class StatusTransitionRule(BaseModel):
    """Status transition validation rule"""
    from_status: VideoValidationStatus
    to_status: VideoValidationStatus
    required_conditions: Optional[List[str]] = None
    automatic: bool = False
    manual_override: bool = False

class ValidationWorkflowConfig(BaseModel):
    """Configuration for validation workflow"""
    auto_validate_annotated: bool = True
    require_manual_approval: bool = False
    parallel_validation: bool = True
    max_retry_attempts: int = 3
    notification_enabled: bool = True

# Statistics and Reporting Models

class ValidationStatistics(BaseModel):
    """Validation statistics summary"""
    total_videos: int = 0
    by_status: Dict[str, int] = {}
    by_validation_type: Dict[str, int] = {}
    average_validation_time_seconds: Optional[float] = None
    success_rate_percent: float = 0.0
    last_updated: datetime

class ValidationTrend(BaseModel):
    """Validation trend data"""
    date: datetime
    validated_count: int = 0
    failed_count: int = 0
    success_rate: float = 0.0
    average_score: Optional[float] = None