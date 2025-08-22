from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

# ============================================================================
# ENUMS FOR VALIDATION
# ============================================================================

class VRUTypeEnum(str, Enum):
    """Vulnerable Road User types"""
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"
    MOTORCYCLIST = "motorcyclist"
    WHEELCHAIR = "wheelchair"
    SCOOTER = "scooter"
    ANIMAL = "animal"
    OTHER = "other"

class AnnotationStatusEnum(str, Enum):
    """Annotation validation status"""
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"

class ExportFormatEnum(str, Enum):
    """Supported export formats"""
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    COCO = "coco"
    YOLO = "yolo"
    PASCAL_VOC = "pascal_voc"

class SignalTypeEnum(str, Enum):
    """Camera signal types"""
    GPIO = "GPIO"
    NETWORK_PACKET = "Network Packet"
    SERIAL = "Serial"
    CAN_BUS = "CAN Bus"

# Alias for backward compatibility
CameraSignalType = SignalTypeEnum

# ============================================================================
# BOUNDING BOX SCHEMAS
# ============================================================================

class BoundingBox(BaseModel):
    """Bounding box coordinates"""
    x: float = Field(..., ge=0, description="X coordinate (top-left)")
    y: float = Field(..., ge=0, description="Y coordinate (top-left)")
    width: float = Field(..., gt=0, description="Width of bounding box")
    height: float = Field(..., gt=0, description="Height of bounding box")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Detection confidence")

    @validator('x', 'y', 'width', 'height')
    def validate_coordinates(cls, v):
        if v < 0:
            raise ValueError('Coordinates must be non-negative')
        return v

# ============================================================================
# ANNOTATION SCHEMAS
# ============================================================================

class AnnotationCreate(BaseModel):
    """Schema for creating new annotations"""
    detection_id: Optional[str] = Field(None, description="Detection ID for tracking")
    frame_number: int = Field(..., ge=0, description="Frame number in video")
    timestamp: float = Field(..., ge=0, description="Timestamp in seconds")
    end_timestamp: Optional[float] = Field(None, ge=0, description="End timestamp for temporal annotations")
    vru_type: VRUTypeEnum = Field(..., description="Type of vulnerable road user")
    bounding_box: BoundingBox = Field(..., description="Bounding box coordinates")
    occluded: bool = Field(False, description="Whether object is occluded")
    truncated: bool = Field(False, description="Whether object is truncated")
    difficult: bool = Field(False, description="Whether detection is difficult")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    annotator: Optional[str] = Field(None, description="Annotator identifier")
    validated: bool = Field(False, description="Whether annotation is validated")

    @validator('end_timestamp')
    def validate_end_timestamp(cls, v, values):
        if v is not None and 'timestamp' in values and v <= values['timestamp']:
            raise ValueError('End timestamp must be greater than start timestamp')
        return v

class AnnotationUpdate(BaseModel):
    """Schema for updating existing annotations"""
    detection_id: Optional[str] = None
    frame_number: Optional[int] = Field(None, ge=0)
    timestamp: Optional[float] = Field(None, ge=0)
    end_timestamp: Optional[float] = Field(None, ge=0)
    vru_type: Optional[VRUTypeEnum] = None
    bounding_box: Optional[BoundingBox] = None
    occluded: Optional[bool] = None
    truncated: Optional[bool] = None
    difficult: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)
    annotator: Optional[str] = None
    validated: Optional[bool] = None

class AnnotationResponse(BaseModel):
    """Schema for annotation responses"""
    id: str
    video_id: str
    detection_id: Optional[str]
    frame_number: int
    timestamp: float
    end_timestamp: Optional[float]
    vru_type: str
    bounding_box: Dict[str, Any]
    occluded: bool
    truncated: bool
    difficult: bool
    notes: Optional[str]
    annotator: Optional[str]
    validated: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class AnnotationBulkCreate(BaseModel):
    """Schema for bulk annotation creation"""
    annotations: List[AnnotationCreate] = Field(..., min_items=1, max_items=1000)
    
    @validator('annotations')
    def validate_annotations(cls, v):
        if len(v) == 0:
            raise ValueError('At least one annotation is required')
        return v

# ============================================================================
# ANNOTATION SESSION SCHEMAS
# ============================================================================

class AnnotationSessionCreate(BaseModel):
    """Schema for creating annotation sessions"""
    video_id: str = Field(..., description="Video ID to annotate")
    annotator_id: Optional[str] = Field(None, description="Annotator identifier")

class AnnotationSessionResponse(BaseModel):
    """Schema for annotation session responses"""
    id: str
    video_id: str
    project_id: str
    annotator_id: Optional[str]
    status: str
    total_detections: int
    validated_detections: int
    current_frame: int
    total_frames: Optional[int]
    progress_percentage: Optional[float]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# ============================================================================
# EXPORT AND STATISTICS SCHEMAS
# ============================================================================

class AnnotationExportRequest(BaseModel):
    """Schema for annotation export requests"""
    format: ExportFormatEnum = Field(..., description="Export format")
    include_metadata: bool = Field(True, description="Include annotation metadata")
    validated_only: bool = Field(False, description="Export only validated annotations")
    frame_range: Optional[Dict[str, int]] = Field(None, description="Frame range filter")

class VideoAnnotationStats(BaseModel):
    """Schema for video annotation statistics"""
    video_id: str
    total_annotations: int
    validated_annotations: int
    validation_percentage: float
    vru_type_distribution: Dict[str, int]
    annotation_density: float  # annotations per second
    difficulty_distribution: Optional[Dict[str, int]] = None
    temporal_distribution: Optional[Dict[str, int]] = None

# ============================================================================
# CAMERA VALIDATION SCHEMAS
# ============================================================================

class AnnotationValidationRequest(BaseModel):
    """Schema for real-time validation requests"""
    video_id: str = Field(..., description="Video ID")
    timestamp: float = Field(..., ge=0, description="Detection timestamp")
    tolerance_ms: int = Field(100, ge=0, le=1000, description="Tolerance in milliseconds")
    detection_data: Dict[str, Any] = Field(..., description="Detection data to validate")
    expected_result: Optional[str] = Field(None, description="Expected validation result")

class ValidationResult(BaseModel):
    """Schema for validation results"""
    video_id: str
    timestamp: float
    validation_status: str  # 'PASS', 'FAIL', 'UNCERTAIN'
    match_found: bool
    confidence_score: float
    timing_offset: Optional[float]  # in milliseconds
    spatial_error: Optional[float]  # IoU or distance metric
    details: Dict[str, Any]
    created_at: datetime

class SignalDetectionRequest(BaseModel):
    """Schema for signal detection requests"""
    video_id: str = Field(..., description="Video ID")
    signal_type: SignalTypeEnum = Field(..., description="Type of signal to detect")
    detection_config: Optional[Dict[str, Any]] = Field(None, description="Detection configuration")
    start_time: Optional[float] = Field(None, ge=0, description="Start time for detection")
    end_time: Optional[float] = Field(None, ge=0, description="End time for detection")

class SignalDetectionResult(BaseModel):
    """Schema for signal detection results"""
    video_id: str
    signal_type: str
    detected_signals: List[Dict[str, Any]]
    total_detections: int
    processing_time: float
    confidence_distribution: Dict[str, int]
    temporal_analysis: Dict[str, Any]
    created_at: datetime

# ============================================================================
# TIMING COMPARISON SCHEMAS
# ============================================================================

class TimingComparisonRequest(BaseModel):
    """Schema for timing comparison requests"""
    reference_timestamps: List[float] = Field(..., min_items=1, description="Reference timestamps")
    detected_timestamps: List[float] = Field(..., min_items=1, description="Detected timestamps")
    tolerance_ms: int = Field(100, ge=0, le=1000, description="Tolerance in milliseconds")
    comparison_method: str = Field("nearest", description="Comparison method")

class TimingComparisonResult(BaseModel):
    """Schema for timing comparison results"""
    total_reference: int
    total_detected: int
    matched_pairs: int
    unmatched_reference: int
    unmatched_detected: int
    accuracy: float  # percentage
    precision: float
    recall: float
    average_delay: float  # in milliseconds
    timing_distribution: Dict[str, int]
    statistical_analysis: Dict[str, Any]

# ============================================================================
# PASS/FAIL VALIDATION SCHEMAS
# ============================================================================

class PassFailCriteria(BaseModel):
    """Schema for pass/fail criteria"""
    min_detection_rate: float = Field(0.95, ge=0, le=1, description="Minimum detection rate")
    max_false_positive_rate: float = Field(0.05, ge=0, le=1, description="Maximum false positive rate")
    max_latency_ms: int = Field(100, ge=0, description="Maximum allowed latency")
    min_spatial_accuracy: float = Field(0.8, ge=0, le=1, description="Minimum spatial accuracy (IoU)")
    required_confidence: float = Field(0.7, ge=0, le=1, description="Required confidence threshold")

class PassFailResult(BaseModel):
    """Schema for pass/fail results"""
    test_session_id: str
    overall_result: str  # 'PASS', 'FAIL'
    criteria_results: Dict[str, bool]
    metrics: Dict[str, float]
    detailed_analysis: Dict[str, Any]
    recommendations: List[str]
    created_at: datetime

# ============================================================================
# PRE-ANNOTATION SCHEMAS
# ============================================================================

class PreAnnotationConfig(BaseModel):
    """Schema for pre-annotation configuration"""
    model_name: str = Field("yolov8n", description="ML model to use")
    confidence_threshold: float = Field(0.5, ge=0, le=1, description="Confidence threshold")
    nms_threshold: float = Field(0.45, ge=0, le=1, description="NMS threshold")
    target_classes: Optional[List[str]] = Field(None, description="Target object classes")
    batch_size: int = Field(1, ge=1, le=32, description="Processing batch size")
    max_detections: int = Field(100, ge=1, description="Maximum detections per frame")

class PreAnnotationStatus(BaseModel):
    """Schema for pre-annotation status"""
    video_id: str
    task_id: str
    status: str  # 'pending', 'processing', 'completed', 'failed'
    progress_percentage: float
    processed_frames: int
    total_frames: int
    detections_found: int
    processing_time: Optional[float]
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

class PreAnnotationResult(BaseModel):
    """Schema for pre-annotation results"""
    video_id: str
    task_id: str
    total_detections: int
    processing_time: float
    model_used: str
    confidence_distribution: Dict[str, int]
    class_distribution: Dict[str, int]
    frame_coverage: float  # percentage of frames with detections
    annotations_created: int
    created_at: datetime

# ============================================================================
# WEBSOCKET MESSAGE SCHEMAS
# ============================================================================

class WebSocketMessage(BaseModel):
    """Base schema for WebSocket messages"""
    type: str = Field(..., description="Message type")
    data: Dict[str, Any] = Field(..., description="Message data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AnnotationProgressMessage(WebSocketMessage):
    """Schema for annotation progress messages"""
    type: str = "annotation_progress"
    session_id: str
    progress_percentage: float
    current_frame: int
    total_frames: int

class ValidationResultMessage(WebSocketMessage):
    """Schema for real-time validation messages"""
    type: str = "validation_result"
    test_session_id: str
    detection_id: str
    validation_result: str
    confidence_score: float
