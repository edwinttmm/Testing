from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
# Using str for UUID compatibility with SQLite

# Architecture-compliant enums
class CameraTypeEnum(str, Enum):
    FRONT_FACING_VRU = "Front-facing VRU"
    REAR_FACING_VRU = "Rear-facing VRU"
    IN_CAB_DRIVER_BEHAVIOR = "In-Cab Driver Behavior"
    MULTI_ANGLE_SCENARIOS = "Multi-angle"

class SignalTypeEnum(str, Enum):
    GPIO = "GPIO"
    NETWORK_PACKET = "Network Packet"
    SERIAL = "Serial"
    CAN_BUS = "CAN Bus"

class ProjectStatusEnum(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    TESTING = "testing"
    ANALYSIS = "analysis"
    COMPLETED = "completed"
    ARCHIVED = "archived"


# Project schemas
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    camera_model: str = Field(alias="cameraModel")
    camera_view: CameraTypeEnum = Field(alias="cameraView")
    lens_type: Optional[str] = Field(None, alias="lensType")
    resolution: Optional[str] = None
    frame_rate: Optional[int] = Field(None, alias="frameRate")
    signal_type: SignalTypeEnum = Field(alias="signalType")
    
    class Config:
        populate_by_name = True

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(ProjectBase):
    name: Optional[str] = None
    camera_model: Optional[str] = Field(None, alias="cameraModel")
    camera_view: Optional[CameraTypeEnum] = Field(None, alias="cameraView")
    lens_type: Optional[str] = Field(None, alias="lensType")
    resolution: Optional[str] = None
    frame_rate: Optional[int] = Field(None, alias="frameRate")
    signal_type: Optional[SignalTypeEnum] = Field(None, alias="signalType")
    status: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: str
    status: str
    owner_id: str = Field(alias="ownerId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")

    class Config:
        from_attributes = True
        populate_by_name = True

# Video schemas
class VideoBase(BaseModel):
    filename: str
    file_size: Optional[int] = None
    duration: Optional[float] = None
    fps: Optional[float] = None
    resolution: Optional[str] = None

class VideoResponse(VideoBase):
    id: str
    project_id: str = Field(alias="projectId")
    status: str
    url: Optional[str] = None  # Full URL to access the video file
    ground_truth_generated: bool = Field(alias="groundTruthGenerated")
    created_at: datetime = Field(alias="createdAt")
    uploaded_at: Optional[datetime] = Field(None, alias="uploadedAt")
    detection_count: Optional[int] = Field(0, alias="detectionCount")
    original_name: Optional[str] = Field(None, alias="originalName")

    class Config:
        from_attributes = True
        populate_by_name = True

class VideoUploadResponse(BaseModel):
    id: str
    project_id: str = Field(alias="projectId")
    filename: str
    original_name: str = Field(alias="originalName")
    size: int
    file_size: int = Field(alias="fileSize")
    duration: Optional[float] = None
    uploaded_at: str = Field(alias="uploadedAt")
    created_at: str = Field(alias="createdAt")
    status: str
    ground_truth_generated: bool = Field(alias="groundTruthGenerated")
    processing_status: str = Field(alias="processingStatus")  # Fixed: Use actual model field
    detection_count: int = Field(alias="detectionCount")
    message: str
    
    class Config:
        populate_by_name = True

# Ground Truth schemas
class GroundTruthObject(BaseModel):
    id: str
    timestamp: float
    class_label: str
    bounding_box: Dict[str, Any]
    confidence: float

    class Config:
        from_attributes = True

class GroundTruthResponse(BaseModel):
    video_id: str
    objects: List[GroundTruthObject]
    total_detections: int
    status: str

# Test Session schemas
class TestSessionBase(BaseModel):
    name: str
    project_id: str
    video_id: str
    tolerance_ms: Optional[int] = 100
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Test session name cannot be empty')
        return v.strip()

class TestSessionCreate(TestSessionBase):
    pass

class TestSessionResponse(TestSessionBase):
    id: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

# Detection Event schemas
class DetectionEvent(BaseModel):
    test_session_id: str = Field(alias="testSessionId")
    timestamp: float
    confidence: Optional[float] = None
    class_label: Optional[str] = Field(None, alias="classLabel")
    validation_result: Optional[str] = Field(None, alias="validationResult")
    
    class Config:
        populate_by_name = True

class DetectionEventResponse(DetectionEvent):
    id: str
    validation_result: Optional[str]
    ground_truth_match_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# Validation Result schemas
class ValidationMetrics(BaseModel):
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float

class ValidationResult(BaseModel):
    session_id: str = Field(alias="test_session_id")
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    total_detections: int
    true_positives: int
    false_positives: int
    false_negatives: int
    status: str
    
    class Config:
        populate_by_name = True

# Audit Log schemas
class AuditLogCreate(BaseModel):
    event_type: str
    event_data: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class AuditLogResponse(AuditLogCreate):
    id: str
    user_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Dashboard schemas - Frontend compatible
class DashboardStats(BaseModel):
    project_count: int = Field(alias="projectCount")
    video_count: int = Field(alias="videoCount")
    test_session_count: int = Field(alias="testCount")
    detection_event_count: int = Field(alias="totalDetections")
    average_accuracy: float = Field(alias="averageAccuracy")
    active_tests: int = Field(alias="activeTests")
    
    class Config:
        populate_by_name = True

# Enhanced schemas for new architectural services
class PassFailCriteriaSchema(BaseModel):
    min_precision: float = Field(default=0.90, ge=0, le=1)
    min_recall: float = Field(default=0.85, ge=0, le=1)
    min_f1_score: float = Field(default=0.87, ge=0, le=1)
    max_latency_ms: float = Field(default=100.0, gt=0)

class PassFailCriteriaResponse(PassFailCriteriaSchema):
    id: str
    project_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class VideoAssignmentSchema(BaseModel):
    project_id: str
    video_id: str
    assignment_reason: str
    intelligent_match: bool = True

class VideoAssignmentResponse(VideoAssignmentSchema):
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class SignalProcessingSchema(BaseModel):
    signal_type: SignalTypeEnum
    signal_data: Dict[str, Any]
    processing_config: Optional[Dict[str, Any]] = None

class SignalProcessingResponse(BaseModel):
    id: str
    signal_type: SignalTypeEnum
    processing_time: float
    success: bool
    metadata: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True

class StatisticalValidationSchema(BaseModel):
    test_session_id: str
    confidence_level: float = Field(default=0.95, ge=0.5, le=0.99)

class StatisticalValidationResponse(BaseModel):
    id: str
    test_session_id: str
    confidence_interval: float
    p_value: float
    statistical_significance: bool
    trend_analysis: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True

class VideoLibraryOrganizeResponse(BaseModel):
    organized_folders: List[str]
    total_videos: int
    organization_strategy: str
    metadata_extracted: bool

class VideoQualityAssessmentResponse(BaseModel):
    video_id: str
    quality_score: float
    resolution_quality: str
    frame_rate_quality: str
    brightness_analysis: Dict[str, Any]
    noise_analysis: Dict[str, Any]
    
class DetectionPipelineConfigSchema(BaseModel):
    video_id: str = Field(..., description="Video ID to process")
    confidence_threshold: float = Field(default=0.7, ge=0, le=1)
    nms_threshold: float = Field(default=0.45, ge=0, le=1)
    model_name: str = "yolov8n"
    target_classes: List[str] = ["pedestrian", "cyclist", "motorcyclist"]

    model_config = {'protected_namespaces': ()}


class DetectionPipelineResponse(BaseModel):
    video_id: str
    detections: List[Dict[str, Any]]
    processing_time: float
    model_used: str
    total_detections: int
    confidence_distribution: Dict[str, int]

    model_config = {'protected_namespaces': ()}


class EnhancedDashboardStats(DashboardStats):
    confidence_intervals: Dict[str, List[float]]
    trend_analysis: Dict[str, str]
    signal_processing_metrics: Dict[str, Any]
    average_accuracy: float
    active_tests: int
    total_detections: int