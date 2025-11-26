from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import re
from config.timing_config import MATCHING_TOLERANCE_MS
# Using str for UUID compatibility with SQLite

def snake_to_camel(snake_str: str) -> str:
    """Convert snake_case to camelCase"""
    if not snake_str or snake_str.startswith('_'):
        return snake_str
    
    # Split by underscores and join, capitalizing all but the first word
    components = snake_str.split('_')
    return components[0] + ''.join(word.capitalize() for word in components[1:])

class CamelCaseModel(BaseModel):
    """Base model that automatically converts snake_case fields to camelCase aliases for API serialization

    ISSUE #2 FIX: All Pydantic schemas now automatically convert snake_case to camelCase
    This solves the type field mismatch between backend (snake_case) and frontend (camelCase)
    """

    model_config = ConfigDict(
        # Generate camelCase aliases for all fields - CRITICAL FIX
        alias_generator=snake_to_camel,
        # Allow both snake_case and camelCase field names when parsing
        populate_by_name=True,
        # Enable serialization by alias (camelCase for frontend) - CRITICAL FIX
        by_alias=True,
        # Enable SQLAlchemy integration
        from_attributes=True
    )

# Architecture-compliant enums
class CameraTypeEnum(str, Enum):
    FRONT_FACING_VRU = "Front-facing VRU"
    REAR_FACING_VRU = "Rear-facing VRU"
    IN_CAB_DRIVER_BEHAVIOR = "In-Cab Driver Behavior"
    MULTI_ANGLE_SCENARIOS = "Multi-angle"

# PRD Module 1.1 & 1.2: Video Status Workflow
class VideoStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    VALIDATED = "validated"
    ERROR = "error"
    PENDING_ANNOTATION = "pending_annotation"
    PENDING_VALIDATION = "pending_validation"

# PRD Module 1.2: VRU Types for YOLO Detection - Frontend Compatible
class VRUType(str, Enum):
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"
    MOTORCYCLIST = "motorcyclist"
    WHEELCHAIR = "wheelchair_user"  # Match frontend expectation
    SCOOTER = "scooter_rider"  # Match frontend expectation

# Validation status enums matching frontend
class ValidationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PENDING_VALIDATION = "pending_validation"
    VALIDATING = "validating"
    VALIDATED = "validated"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"

class ValidationType(str, Enum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    HYBRID = "hybrid"

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


# Project schemas - Frontend compatible with camelCase aliases
class ProjectBase(CamelCaseModel):
    name: str
    description: Optional[str] = None
    camera_model: str = Field(alias="cameraModel")
    camera_view: CameraTypeEnum = Field(alias="cameraView")
    lens_type: Optional[str] = Field(None, alias="lensType")
    resolution: Optional[str] = None
    frame_rate: Optional[int] = Field(None, alias="frameRate")
    signal_type: SignalTypeEnum = Field(alias="signalType")

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(CamelCaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    camera_model: Optional[str] = None
    camera_view: Optional[CameraTypeEnum] = None
    lens_type: Optional[str] = None
    resolution: Optional[str] = None
    frame_rate: Optional[int] = None
    signal_type: Optional[SignalTypeEnum] = None
    status: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: str  # Note: 'id' should not be aliased to avoid conflicts, frontend expects 'id' 
    status: ProjectStatusEnum
    owner_id: str = Field(alias="ownerId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    # Additional fields expected by frontend
    tests_count: Optional[int] = Field(None, alias="testsCount")
    video_count: Optional[int] = Field(None, alias="videoCount")
    total_annotations: Optional[int] = Field(None, alias="totalAnnotations")
    average_accuracy: Optional[float] = Field(None, alias="averageAccuracy")

    # Normalize database status values like 'Active' -> 'active' before enum validation
    @field_validator('status', mode='before')
    @classmethod
    def normalize_status(cls, v):
        if isinstance(v, str):
            return v.strip().lower()
        return v

# Video schemas - Frontend-compatible with comprehensive field mapping
class VideoBase(CamelCaseModel):
    filename: str
    file_size: Optional[int] = None
    duration: Optional[float] = None
    fps: Optional[float] = Field(None, alias="frameRate")
    resolution: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

class VideoResponse(VideoBase):
    id: str
    project_id: str = Field(alias="projectId")
    status: VideoStatus = Field(alias="status")
    # Unified validation status system
    validation_status: ValidationStatus = Field(default=ValidationStatus.PENDING, alias="validationStatus")
    validation_type: Optional[ValidationType] = Field(None, alias="validationType")
    validated_at: Optional[datetime] = Field(None, alias="validatedAt")
    validated_by: Optional[str] = Field(None, alias="validatedBy")
    
    # HIL testing readiness
    hil_testing_ready: bool = Field(default=False, alias="hilTestingReady")
    hil_testing_approved_by: Optional[str] = Field(None, alias="hilTestingApprovedBy")
    hil_testing_approved_at: Optional[datetime] = Field(None, alias="hilTestingApprovedAt")
    
    # Ground truth information
    ground_truth_generated: bool = Field(alias="groundTruthGenerated")
    ground_truth_count: int = Field(default=0, alias="groundTruthCount")
    ground_truth_quality_score: Optional[float] = Field(None, alias="groundTruthQualityScore")
    ground_truth_completed_at: Optional[datetime] = Field(None, alias="groundTruthCompletedAt")
    
    # Detection and annotation counts
    detection_count: int = Field(default=0, alias="detectionCount")
    annotation_count: int = Field(default=0, alias="annotationCount")
    
    # URLs and paths
    url: Optional[str] = None  # Full URL to access the video file
    file_path: Optional[str] = Field(None, alias="filePath")
    
    # Timestamps
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    uploaded_at: Optional[datetime] = Field(None, alias="uploadedAt")
    
    # Legacy compatibility fields
    original_name: Optional[str] = Field(None, alias="originalName")
    name: Optional[str] = None
    size: Optional[int] = None
    frame_rate: Optional[float] = Field(None, alias="frameRate")
    frame_count: Optional[int] = Field(None, alias="frameCount")
    bitrate: Optional[int] = None
    format: Optional[str] = None
    codec: Optional[str] = None
    mime_type: Optional[str] = Field(None, alias="mimeType")
    thumbnail_url: Optional[str] = Field(None, alias="thumbnailUrl")
    metadata: Optional[Dict[str, Any]] = None

class VideoUploadResponse(CamelCaseModel):
    id: str
    project_id: str = Field(alias="projectId")
    filename: str
    original_name: str = Field(alias="originalName")
    size: int
    file_size: int = Field(alias="fileSize")
    duration: Optional[float] = None
    uploaded_at: str = Field(alias="uploadedAt")
    created_at: str = Field(alias="createdAt")
    status: VideoStatus
    ground_truth_generated: bool = Field(alias="groundTruthGenerated")
    processing_status: str = Field(alias="processingStatus")  # Fixed: Use actual model field
    detection_count: int = Field(alias="detectionCount")
    message: str

# Lightweight upload response used by simplified upload endpoints
class SimpleUploadResponse(CamelCaseModel):
    id: str
    project_id: str = Field(alias="projectId")
    filename: str
    status: str
    message: str

# VideoFile schema for ground truth videos API
class VideoFile(CamelCaseModel):
    """Video file schema for frontend compatibility - matches TypeScript interface"""
    id: str
    filename: str
    project_id: Optional[str] = Field(None, alias="projectId")  # Always None for shared videos
    duration: Optional[float] = None
    size: Optional[int] = None
    status: Optional[str] = None
    created_at: Optional[str] = Field(None, alias="createdAt")
    url: Optional[str] = None
    # Additional ground truth specific fields
    ground_truth_count: Optional[int] = Field(None, alias="groundTruthCount")
    ground_truth_generated: Optional[bool] = Field(None, alias="groundTruthGenerated")
    validation_status: Optional[str] = Field(None, alias="validationStatus")
    
    # Shared video architecture fields
    is_shared: Optional[bool] = Field(None, alias="isShared")  # Video linked to multiple projects
    linked_project_count: Optional[int] = Field(None, alias="linkedProjectCount")  # Number of projects linked

# Ground Truth schemas
class GroundTruthObject(CamelCaseModel):
    id: str
    timestamp: float
    class_label: str
    bounding_box: Dict[str, Any]
    confidence: float

class GroundTruthResponse(CamelCaseModel):
    video_id: str
    objects: List[GroundTruthObject]
    total_detections: int
    status: str

# Test Session schemas - Frontend compatible
class TestSessionBase(CamelCaseModel):
    name: Optional[str] = Field(default=None)
    project_id: str = Field(alias="projectId")
    video_id: Optional[str] = Field(None, alias="videoId")
    video_ids: Optional[List[str]] = Field(None, alias="videoIds")
    tolerance_ms: Optional[int] = Field(MATCHING_TOLERANCE_MS, alias="toleranceMs")
    description: Optional[str] = None
    session_type: Optional[str] = Field(None, alias="sessionType")
    has_video_sequence: Optional[bool] = Field(None, alias="hasVideoSequence")
    sequence_id: Optional[str] = Field(None, alias="sequenceId")
    sequence_metadata: Optional[Dict[str, Any]] = Field(None, alias="sequenceMetadata")
    max_latency_threshold_ms: Optional[float] = Field(None, alias="maxLatencyThresholdMs")
    test_configuration: Optional[Dict[str, Any]] = Field(None, alias="testConfiguration")
    expected_detections: Optional[int] = Field(None, alias="expectedDetections")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> str:
        if v is None:
            return "HIL Test Session"
        if not isinstance(v, str):
            raise ValueError('Test session name must be a string')
        trimmed = v.strip()
        return trimmed or "HIL Test Session"

class TestSessionCreate(TestSessionBase):
    session_id: Optional[str] = Field(None, alias="sessionId", description="Optional pre-generated session ID for proactive room join")
    config: Optional[Dict[str, Any]] = None

    @field_validator('session_id')
    @classmethod
    def validate_session_id_format(cls, v):
        """Validate session_id format if provided (must start with 'session_')"""
        if v is not None and not v.startswith('session_'):
            raise ValueError("session_id must start with 'session_' prefix")
        return v

class TestSessionResponse(TestSessionBase):
    id: str
    status: str  # 'created' | 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
    started_at: Optional[datetime] = Field(None, alias="startedAt")
    completed_at: Optional[datetime] = Field(None, alias="completedAt")
    created_at: datetime = Field(alias="createdAt")
    project_name: Optional[str] = Field(None, alias="projectName")
    video_filename: Optional[str] = Field(None, alias="videoFilename")
    actual_detections: Optional[int] = Field(None, alias="actualDetections")
    pass_fail_result: Optional[str] = Field(None, alias="passFailResult")
    overall_score: Optional[float] = Field(None, alias="overallScore")
    accuracy_result: Optional[str] = Field(None, alias="accuracyResult")
    latency_result: Optional[str] = Field(None, alias="latencyResult")
    overall_test_result: Optional[str] = Field(None, alias="overallTestResult")
    accuracy_f1_score: Optional[float] = Field(None, alias="accuracyF1Score")
    accuracy_precision: Optional[float] = Field(None, alias="accuracyPrecision")
    accuracy_recall: Optional[float] = Field(None, alias="accuracyRecall")
    latency_mean_ms: Optional[float] = Field(None, alias="latencyMeanMs")
    latency_max_ms: Optional[float] = Field(None, alias="latencyMaxMs")
    latency_percent_within_threshold: Optional[float] = Field(None, alias="latencyPercentWithinThreshold")
    tp_count: Optional[int] = Field(None, alias="truePositives")
    fp_count: Optional[int] = Field(None, alias="falsePositives")
    fn_count: Optional[int] = Field(None, alias="falseNegatives")
    accuracy_details: Optional[Dict[str, Any]] = Field(None, alias="accuracyDetails")
    latency_details: Optional[Dict[str, Any]] = Field(None, alias="latencyDetails")
    overall_details: Optional[Dict[str, Any]] = Field(None, alias="overallDetails")
    # Additional fields for enhanced test sessions
    detection_events: Optional[List[Dict[str, Any]]] = Field(None, alias="detectionEvents")
    metrics: Optional[Dict[str, Any]] = None
    model_configurations: Optional[List[Dict[str, Any]]] = Field(None, alias="modelConfigurations")
    model_config_ids: Optional[List[str]] = Field(None, alias="modelConfigIds")
    # Approval workflow fields
    approval_status: Optional[str] = Field(None, alias="approvalStatus")  # 'pending' | 'approved' | 'rejected'
    approved_by: Optional[str] = Field(None, alias="approvedBy")
    approved_at: Optional[datetime] = Field(None, alias="approvedAt")
    approval_comments: Optional[str] = Field(None, alias="approvalComments")
    rejection_reason: Optional[str] = Field(None, alias="rejectionReason")

# Detection Event schemas - Frontend compatible
class DetectionEvent(CamelCaseModel):
    test_session_id: str = Field(alias="testSessionId")
    video_id: Optional[str] = Field(None, alias="videoId")
    timestamp: float
    frame_number: Optional[int] = Field(None, alias="frameNumber")
    confidence: Optional[float] = None
    class_label: Optional[str] = Field(None, alias="classLabel")
    class_name: Optional[str] = Field(None, alias="className")
    vru_type: Optional[VRUType] = Field(None, alias="vruType")
    bounding_box: Optional[Dict[str, Any]] = Field(None, alias="boundingBox")
    validation_result: Optional[str] = Field(None, alias="validationResult")
    is_ground_truth: bool = Field(default=False, alias="isGroundTruth")
    validated: bool = Field(default=False)

class DetectionEventResponse(DetectionEvent):
    id: str
    validation_result: Optional[str] = Field(None, alias="validationResult")
    ground_truth_match_id: Optional[str] = Field(None, alias="groundTruthMatchId")
    created_at: datetime = Field(alias="createdAt")
    # Additional fields for enhanced compatibility
    detection_id: Optional[str] = Field(None, alias="detectionId")
    inference_session_id: Optional[str] = Field(None, alias="inferenceSessionId")
    detection_score: Optional[float] = Field(None, alias="detectionScore")
    nms_score: Optional[float] = Field(None, alias="nmsScore")
    tracking_id: Optional[str] = Field(None, alias="trackingId")
    validation_status: str = Field(default="pending", alias="validationStatus")
    iou_with_ground_truth: Optional[float] = Field(None, alias="iouWithGroundTruth")

    # CRITICAL FIX: Add missing fields expected by frontend
    video_relative_timestamp: Optional[float] = Field(None, alias="videoRelativeTimestamp")
    video_frame_number: Optional[int] = Field(None, alias="videoFrameNumber")

    # LATENCY FIELDS - actual_latency_ms is the canonical field
    # PRIMARY: Always use this field for latency measurements
    actual_latency_ms: Optional[float] = Field(
        None,
        alias="actualLatencyMs",
        description="CANONICAL: Actual measured latency in milliseconds from video event to hardware detection. "
                   "This is the single source of truth for latency. Use this field only. "
                   "For False Positives, stores REAL latency, not 10000ms sentinel."
    )

    # FALSE POSITIVE TRACKING - Added 2025-11-25 to replace 10000ms sentinel
    is_false_positive: bool = Field(
        default=False,
        alias="isFalsePositive",
        description="TRUE if detection is a False Positive. Replaces 10000ms sentinel value in actual_latency_ms."
    )

    # DEPRECATED: Legacy fields maintained for backward compatibility
    latency_ms: Optional[float] = Field(
        None,
        alias="latencyMs",
        deprecated=True,
        description="DEPRECATED: Use actual_latency_ms instead. Kept for backward compatibility only."
    )
    processing_time_ms: Optional[float] = Field(
        None,
        deprecated=True,
        description="DEPRECATED: This is processing time, not latency. Use actual_latency_ms instead."
    )

# Validation Result schemas
class ValidationMetrics(CamelCaseModel):
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float

class ValidationResult(CamelCaseModel):
    session_id: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    total_detections: int
    true_positives: int
    false_positives: int
    false_negatives: int
    status: str

# Audit Log schemas
class AuditLogCreate(CamelCaseModel):
    event_type: str
    event_data: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class AuditLogResponse(AuditLogCreate):
    id: str
    user_id: Optional[str]
    created_at: datetime


# Dashboard schemas - Frontend compatible with camelCase aliases
class DashboardStats(CamelCaseModel):
    project_count: int = Field(alias="projectCount")
    video_count: int = Field(alias="videoCount")
    test_session_count: int = Field(alias="testSessionCount")
    detection_event_count: int = Field(alias="detectionEventCount")
    average_accuracy: float = Field(alias="averageAccuracy")
    active_tests: int = Field(alias="activeTests")
    # Additional fields to match frontend expectations
    total_detections: int = Field(default=0, alias="totalDetections")

# Enhanced schemas for new architectural services
class PassFailCriteriaSchema(CamelCaseModel):
    min_precision: float = Field(default=0.90, ge=0, le=1)
    min_recall: float = Field(default=0.85, ge=0, le=1)
    min_f1_score: float = Field(default=0.87, ge=0, le=1)
    max_latency_ms: float = Field(default=100.0, gt=0)

class PassFailCriteriaResponse(PassFailCriteriaSchema):
    id: str
    project_id: str
    created_at: datetime

class VideoAssignmentSchema(CamelCaseModel):
    project_id: str
    video_id: str
    assignment_reason: str
    intelligent_match: bool = True

class VideoAssignmentResponse(VideoAssignmentSchema):
    id: str
    created_at: datetime

class SignalProcessingSchema(CamelCaseModel):
    signal_type: SignalTypeEnum
    signal_data: Dict[str, Any]
    processing_config: Optional[Dict[str, Any]] = None

class SignalProcessingResponse(CamelCaseModel):
    id: str
    signal_type: SignalTypeEnum
    processing_time: float
    success: bool
    metadata: Dict[str, Any]
    created_at: datetime

class StatisticalValidationSchema(CamelCaseModel):
    test_session_id: str
    confidence_level: float = Field(default=0.95, ge=0.5, le=0.99)

class StatisticalValidationResponse(CamelCaseModel):
    id: str
    test_session_id: str
    confidence_interval: float
    p_value: float
    statistical_significance: bool
    trend_analysis: Dict[str, Any]
    created_at: datetime

class VideoLibraryOrganizeResponse(CamelCaseModel):
    organized_folders: List[str]
    total_videos: int
    organization_strategy: str
    metadata_extracted: bool

class VideoQualityAssessmentResponse(CamelCaseModel):
    video_id: str
    quality_score: float
    resolution_quality: str
    frame_rate_quality: str
    brightness_analysis: Dict[str, Any]
    noise_analysis: Dict[str, Any]
    
class DetectionPipelineConfigSchema(CamelCaseModel):
    video_id: str = Field(..., description="Video ID to process")
    confidence_threshold: float = Field(default=0.7, ge=0, le=1)
    nms_threshold: float = Field(default=0.45, ge=0, le=1)
    model_name: str = "yolov8n"
    target_classes: List[str] = ["pedestrian", "cyclist", "motorcyclist"]

    model_config = {'protected_namespaces': ()}


class DetectionPipelineResponse(CamelCaseModel):
    video_id: str
    detections: List[Dict[str, Any]]
    processing_time: float
    model_used: str
    total_detections: int
    confidence_distribution: Dict[str, int]

    model_config = {'protected_namespaces': ()}


class EnhancedDashboardStats(DashboardStats):
    confidence_intervals: Dict[str, List[float]] = Field(alias="confidenceIntervals")
    trend_analysis: Dict[str, str] = Field(alias="trendAnalysis")
    signal_processing_metrics: Dict[str, Any] = Field(alias="signalProcessingMetrics")
    # Inherited fields are already properly aliased in parent class

# PRD Module 4.2 - Report Generation Schemas
class ReportGenerationRequest(CamelCaseModel):
    """Request schema for generating test reports"""
    test_session_id: str = Field(..., description="Test session ID to generate report for")
    report_type: str = Field(default="comprehensive", description="Type of report to generate")
    formats: List[str] = Field(default=["html", "json"], description="Output formats")
    include_snapshots: bool = Field(default=True, description="Include failure snapshots")
    report_name: Optional[str] = Field(None, description="Custom report name")

class TestReportMetrics(CamelCaseModel):
    """Test report metrics following PRD Module 4.1 analysis requirements"""
    total_events: int = Field(description="Total detection events")
    passed_events: int = Field(description="Events that passed latency threshold")
    failed_events: int = Field(description="Events that failed latency threshold") 
    high_latency_failures: int = Field(description="Events with high latency")
    missed_detections: int = Field(description="Events with no signal received")
    pass_rate_percent: float = Field(description="Percentage of events that passed")
    fail_rate_percent: float = Field(description="Percentage of events that failed")
    average_latency_ms: float = Field(description="Average latency across all events")
    min_latency_ms: float = Field(description="Minimum latency recorded")
    max_latency_ms: float = Field(description="Maximum latency recorded")
    latency_threshold_ms: int = Field(description="Latency threshold used for pass/fail")
    latency_distribution: Dict[str, int] = Field(description="Latency histogram distribution")
    test_outcome: str = Field(description="Overall test outcome: PASS/FAIL/NO_DATA")

class FailureEventDetail(CamelCaseModel):
    """Detailed information about a failure event"""
    event_id: str
    video_id: Optional[str]
    timestamp: float = Field(description="Timestamp in seconds when failure occurred")
    failure_type: str = Field(description="HIGH_LATENCY or MISSED_DETECTION")
    latency_ms: Optional[float] = Field(description="Actual latency if signal received")
    threshold_ms: int = Field(description="Latency threshold for pass/fail")
    labjack_timestamp: Optional[float]
    frame_number: Optional[int]
    vru_type: Optional[str]
    detection_channel: Optional[str]
    voltage_level: Optional[float]
    created_at: str

class FailureSnapshotDetail(CamelCaseModel):
    """Failure snapshot information for PRD Module 4.2 visual evidence"""
    event_id: str
    video_id: Optional[str]
    video_filename: Optional[str]
    timestamp_ms: float = Field(description="Exact timestamp of failure in milliseconds")
    failure_type: str = Field(description="Type of failure that occurred")
    snapshot_path: str = Field(description="File path to snapshot image")
    snapshot_base64: Optional[str] = Field(description="Base64 encoded image for HTML reports")
    frame_number: Optional[int]
    generated_at: str
    error: Optional[str] = Field(description="Error message if snapshot failed")

class SuccessSummary(CamelCaseModel):
    """Success summary following PRD requirement for text-only passed events"""
    summary_text: str = Field(description="Text summary of successful detections")
    passed_count: int = Field(description="Number of successful detections")
    total_count: int = Field(description="Total number of detection events")
    average_success_latency_ms: float = Field(description="Average latency of successful detections")
    vru_breakdown: Dict[str, int] = Field(description="Breakdown of success by VRU type")
    success_rate_percent: float = Field(description="Success rate as percentage")

class TestReportResponse(CamelCaseModel):
    """Complete test report response following PRD Module 4.2 requirements"""
    report_id: str
    test_session_id: str
    generated_at: str
    test_session: Dict[str, Any] = Field(description="Test session metadata")
    metrics: TestReportMetrics = Field(description="Pass/fail metrics and latency analysis")
    success_summary: SuccessSummary = Field(description="Text summary of successful passes")
    failure_events: List[FailureEventDetail] = Field(description="Detailed failure event information")
    failure_snapshots: List[FailureSnapshotDetail] = Field(description="Video snapshots for every failure")
    videos_tested: int
    total_events: int

class TestReportFileResponse(CamelCaseModel):
    """Response with generated report file information"""
    report_data: TestReportResponse
    report_files: Dict[str, str] = Field(description="Generated report file paths by format")
    metrics: TestReportMetrics

class ReportListItem(CamelCaseModel):
    """Report list item for browsing generated reports"""
    id: str
    test_session_id: str
    report_name: str
    report_type: str
    formats_generated: List[str]
    pass_rate_percent: float
    test_outcome: str
    generated_at: str
    generated_by: str
    failure_snapshots_count: int

class ReportListResponse(CamelCaseModel):
    """Response for listing reports"""
    reports: List[ReportListItem]
    total_count: int
    page: int = 1
    page_size: int = 20

# Detection Outcome Enum for PRD Module 4.1 Analysis
class DetectionOutcomeEnum(str, Enum):
    """PRD Module 4.1 - Detection outcome categories"""
    PASS = "pass"  # Signal received within latency threshold
    FAIL_HIGH_LATENCY = "fail_high_latency"  # Signal received but too slow
    FAIL_MISSED_DETECTION = "fail_missed_detection"  # No signal received

# Standard Error Response Schema - Frontend Compatible
class ErrorResponse(CamelCaseModel):
    """Standardized error response format matching frontend expectations"""
    message: str = Field(description="Human-readable error message")
    status: int = Field(description="HTTP status code")
    code: Optional[str] = Field(None, description="Error code identifier")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
class ApiResponse(CamelCaseModel):
    """Generic API response wrapper"""
    data: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[str] = None
    status: Optional[int] = None
    success: bool = Field(default=True)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# WebSocket Message Schema - Frontend Compatible
class WebSocketMessage(CamelCaseModel):
    """WebSocket message format matching frontend expectations"""
    type: str = Field(description="Message type identifier")
    payload: Dict[str, Any] = Field(description="Message payload data")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id: Optional[str] = Field(None, description="Optional message ID")


# Multi-Video Sequential Testing Schemas

class VideoSequenceOrderItem(CamelCaseModel):
    """Individual video in sequence order"""
    video_id: str = Field(alias="videoId")
    order: int = Field(ge=0, description="Position in sequence (0-indexed)")
    duration_ms: Optional[float] = Field(None, alias="durationMs", description="Expected video duration")


class VideoTestSequenceCreate(CamelCaseModel):
    """Create new video test sequence"""
    name: str = Field(min_length=1, description="Sequence name")
    video_ids: List[str] = Field(alias="videoIds", min_length=1, description="Ordered list of video IDs")
    max_latency_ms: int = Field(default=100, alias="maxLatencyMs", ge=1, description="Latency threshold")
    sequence_order: Optional[List[Dict[str, Any]]] = Field(None, alias="sequenceOrder", description="Detailed order config")


class VideoTestSequenceUpdate(CamelCaseModel):
    """Update existing video test sequence"""
    name: Optional[str] = None
    status: Optional[str] = None
    current_video_index: Optional[int] = Field(None, alias="currentVideoIndex")
    completed_videos: Optional[int] = Field(None, alias="completedVideos")


class VideoTestSequenceResponse(CamelCaseModel):
    """Video test sequence response

    ISSUE #3 FIX: Added perVideoResults field to response
    """
    id: str
    test_session_id: str = Field(alias="testSessionId")
    name: str
    video_ids: List[str] = Field(alias="videoIds")
    sequence_order: List[Dict[str, Any]] = Field(alias="sequenceOrder")
    status: str
    max_latency_ms: int = Field(alias="maxLatencyMs")

    # Progress
    current_video_index: int = Field(alias="currentVideoIndex")
    total_videos: int = Field(alias="totalVideos")
    completed_videos: int = Field(alias="completedVideos")

    # Timing
    sequence_start_time: Optional[float] = Field(None, alias="sequenceStartTime")
    sequence_start_time_ns: Optional[str] = Field(None, alias="sequenceStartTimeNs")
    sequence_end_time: Optional[float] = Field(None, alias="sequenceEndTime")
    sequence_end_time_ns: Optional[str] = Field(None, alias="sequenceEndTimeNs")
    total_duration_ms: Optional[float] = Field(None, alias="totalDurationMs")

    # ISSUE #6 FIX: Add sequenceElapsedTime to schema
    sequence_elapsed_time_ms: Optional[float] = Field(None, alias="sequenceElapsedTimeMs")

    # ISSUE #3 FIX: Per-video results array
    per_video_results: Optional[List[Dict[str, Any]]] = Field(None, alias="perVideoResults")

    # Timestamps
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")


class SequenceVideoResultCreate(CamelCaseModel):
    """Create sequence video result"""
    video_sequence_id: str = Field(alias="videoSequenceId")
    video_id: str = Field(alias="videoId")
    sequence_order: int = Field(alias="sequenceOrder", ge=0)
    latency_threshold_ms: Optional[int] = Field(100, alias="latencyThresholdMs")


class SequenceVideoResultUpdate(CamelCaseModel):
    """Update sequence video result"""
    video_status: Optional[str] = Field(None, alias="videoStatus")
    validation_result: Optional[str] = Field(None, alias="validationResult")
    actual_detection_count: Optional[int] = Field(None, alias="actualDetectionCount")
    passed_detections: Optional[int] = Field(None, alias="passedDetections")
    failed_detections: Optional[int] = Field(None, alias="failedDetections")
    avg_latency_ms: Optional[float] = Field(None, alias="avgLatencyMs")
    max_latency_ms: Optional[float] = Field(None, alias="maxLatencyMs")
    min_latency_ms: Optional[float] = Field(None, alias="minLatencyMs")
    pass_rate_percent: Optional[float] = Field(None, alias="passRatePercent")


class GroundTruthMetrics(CamelCaseModel):
    """Per-video ground truth validation metrics"""
    total_ground_truth: int = Field(alias="totalGroundTruth", description="Total ground truth objects for this video")
    true_positives: int = Field(alias="truePositives", description="Detections correctly matched to ground truth")
    false_positives: int = Field(alias="falsePositives", description="Detections without ground truth match")
    false_negatives: int = Field(alias="falseNegatives", description="Ground truth objects without detection match")
    precision: float = Field(description="Precision percentage (TP / (TP + FP))")
    recall: float = Field(description="Recall percentage (TP / (TP + FN))")
    f1_score: float = Field(alias="f1Score", description="F1 score percentage (harmonic mean of precision and recall)")


class SequenceVideoResultResponse(CamelCaseModel):
    """Sequence video result response"""
    id: str
    video_sequence_id: str = Field(alias="videoSequenceId")
    video_id: str = Field(alias="videoId")
    sequence_order: int = Field(alias="sequenceOrder")

    # Timing
    video_start_time: Optional[float] = Field(None, alias="videoStartTime")
    video_start_time_ns: Optional[str] = Field(None, alias="videoStartTimeNs")
    video_end_time: Optional[float] = Field(None, alias="videoEndTime")
    video_end_time_ns: Optional[str] = Field(None, alias="videoEndTimeNs")
    actual_duration_ms: Optional[float] = Field(None, alias="actualDurationMs")
    video_play_offset_ms: Optional[float] = Field(None, alias="videoPlayOffsetMs")

    # Status
    video_status: str = Field(alias="videoStatus")
    validation_result: Optional[str] = Field(None, alias="validationResult")

    # Detection metrics
    expected_detection_count: int = Field(alias="expectedDetectionCount")
    actual_detection_count: int = Field(alias="actualDetectionCount")
    passed_detections: int = Field(alias="passedDetections")
    failed_detections: int = Field(alias="failedDetections")

    # Latency statistics
    avg_latency_ms: Optional[float] = Field(None, alias="avgLatencyMs")
    max_latency_ms: Optional[float] = Field(None, alias="maxLatencyMs")
    min_latency_ms: Optional[float] = Field(None, alias="minLatencyMs")
    pass_rate_percent: Optional[float] = Field(None, alias="passRatePercent")
    latency_threshold_ms: Optional[int] = Field(None, alias="latencyThresholdMs")

    # Metadata
    processing_time_ms: Optional[float] = Field(None, alias="processingTimeMs")
    error_message: Optional[str] = Field(None, alias="errorMessage")

    # Timestamps
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")


class SequenceDetectionEventCreate(CamelCaseModel):
    """Detection event within sequence"""
    sequence_video_result_id: str = Field(alias="sequenceVideoResultId")
    video_id: str = Field(alias="videoId")
    timestamp: float
    video_relative_timestamp: Optional[float] = Field(None, alias="videoRelativeTimestamp")
    sequence_timestamp: Optional[float] = Field(None, alias="sequenceTimestamp")
    video_play_offset_ms: Optional[float] = Field(None, alias="videoPlayOffsetMs")
    correlation_method: str = Field(default="timestamp", alias="correlationMethod")
    labjack_timestamp: Optional[float] = Field(None, alias="labjackTimestamp")
    actual_latency_ms: Optional[float] = Field(None, alias="actualLatencyMs")
    validation_result: Optional[str] = Field(None, alias="validationResult")


class SequenceDetectionEventResponse(CamelCaseModel):
    """Detection event response for sequence"""
    id: str
    test_session_id: str = Field(alias="testSessionId")
    video_id: str = Field(alias="videoId")
    sequence_video_result_id: Optional[str] = Field(None, alias="sequenceVideoResultId")

    # Timestamps
    timestamp: float
    video_relative_timestamp: Optional[float] = Field(None, alias="videoRelativeTimestamp")
    video_relative_timestamp_ns: Optional[str] = Field(None, alias="videoRelativeTimestampNs")
    sequence_timestamp: Optional[float] = Field(None, alias="sequenceTimestamp")
    sequence_timestamp_ns: Optional[str] = Field(None, alias="sequenceTimestampNs")
    video_play_offset_ms: Optional[float] = Field(None, alias="videoPlayOffsetMs")

    # LabJack timing
    labjack_timestamp: Optional[float] = Field(None, alias="labjackTimestamp")
    labjack_timestamp_ns: Optional[str] = Field(None, alias="labjackTimestampNs")
    actual_latency_ms: Optional[float] = Field(None, alias="actualLatencyMs")

    # Validation
    validation_result: Optional[str] = Field(None, alias="validationResult")
    correlation_method: str = Field(alias="correlationMethod")

    # Metadata
    frame_number: Optional[int] = Field(None, alias="frameNumber")
    created_at: datetime = Field(alias="createdAt")


class VideoSequenceProgressResponse(CamelCaseModel):
    """Real-time sequence progress"""
    sequence_id: str = Field(alias="sequenceId")
    current_video_index: int = Field(alias="currentVideoIndex")
    current_video_id: Optional[str] = Field(None, alias="currentVideoId")
    total_videos: int = Field(alias="totalVideos")
    completed_videos: int = Field(alias="completedVideos")
    status: str
    progress_percent: float = Field(alias="progressPercent", ge=0, le=100)
    elapsed_time_ms: Optional[float] = Field(None, alias="elapsedTimeMs")
    estimated_remaining_ms: Optional[float] = Field(None, alias="estimatedRemainingMs")


class VideoSequenceStatistics(CamelCaseModel):
    """Aggregated statistics for sequence"""
    sequence_id: str = Field(alias="sequenceId")
    total_videos: int = Field(alias="totalVideos")
    completed_videos: int = Field(alias="completedVideos")
    total_detections: int = Field(alias="totalDetections")
    passed_detections: int = Field(alias="passedDetections")
    failed_detections: int = Field(alias="failedDetections")
    overall_pass_rate: float = Field(alias="overallPassRate", ge=0, le=100)
    avg_latency_ms: Optional[float] = Field(None, alias="avgLatencyMs")
    max_latency_ms: Optional[float] = Field(None, alias="maxLatencyMs")
    min_latency_ms: Optional[float] = Field(None, alias="minLatencyMs")
    per_video_results: List[Dict[str, Any]] = Field(alias="perVideoResults")


# Ground Truth Validation Schemas - Issue #3 Backend
class GTValidationRequest(CamelCaseModel):
    """Request schema for pre-session ground truth validation"""
    video_ids: List[str] = Field(alias="videoIds", min_length=1, description="List of video IDs to validate")


# Approval Workflow Schemas
class ApprovalRequest(CamelCaseModel):
    """Request schema for approving or rejecting test session results"""
    approver_id: str = Field(alias="approverId", description="User ID or email of approver")
    action: str = Field(description="Action to take: 'approve' or 'reject'")
    comments: Optional[str] = Field(None, description="Optional comments from approver")
    rejection_reason: Optional[str] = Field(None, alias="rejectionReason", description="Required reason if rejecting")

    @field_validator('action')
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ['approve', 'reject']:
            raise ValueError("Action must be either 'approve' or 'reject'")
        return v

    @field_validator('rejection_reason')
    @classmethod
    def validate_rejection_reason(cls, v: Optional[str], info) -> Optional[str]:
        # Access action from values using info.data
        if info.data.get('action') == 'reject' and not v:
            raise ValueError("Rejection reason is required when rejecting")
        return v

class ApprovalResponse(CamelCaseModel):
    """Response schema for approval actions"""
    approval_status: str = Field(alias="approvalStatus", description="Current approval status")
    approved_by: Optional[str] = Field(None, alias="approvedBy", description="User who approved/rejected")
    approved_at: Optional[datetime] = Field(None, alias="approvedAt", description="Timestamp of approval/rejection")
    approval_comments: Optional[str] = Field(None, alias="approvalComments")
    rejection_reason: Optional[str] = Field(None, alias="rejectionReason")
    message: str = Field(description="Success message")

class VideoGTStatus(CamelCaseModel):
    """Ground truth status for a single video"""
    video_id: str = Field(alias="videoId")
    gt_count: int = Field(alias="gtCount", description="Number of ground truth objects")
    has_ground_truth: bool = Field(alias="hasGroundTruth", description="Whether video has any ground truth")
    status: str = Field(description="Status: 'ready', 'missing_gt', 'insufficient_gt'")


class GTValidationResponse(CamelCaseModel):
    """Response schema for ground truth validation"""
    has_issues: bool = Field(alias="hasIssues", description="Whether any videos have ground truth issues")
    videos_without_gt: List[str] = Field(alias="videosWithoutGt", description="Video IDs with zero ground truth")
    gt_counts: Dict[str, int] = Field(alias="gtCounts", description="Ground truth count per video ID")
    video_details: List[VideoGTStatus] = Field(alias="videoDetails", description="Detailed status per video")
    total_videos: int = Field(alias="totalVideos", description="Total videos validated")
    ready_videos: int = Field(alias="readyVideos", description="Videos ready for testing")
    validation_timestamp: str = Field(alias="validationTimestamp", description="When validation was performed")
