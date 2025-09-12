# Backend Pydantic Schemas Documentation

## Overview
This document provides comprehensive documentation of all Pydantic schemas, enums, validation models, and database models in the backend codebase. The backend uses Pydantic v2 with advanced validation, serialization, and automatic camelCase conversion for frontend compatibility.

## Table of Contents
- [Schema Architecture](#schema-architecture)
- [Core Enums](#core-enums)
- [Base Models and Configuration](#base-models-and-configuration)
- [Project Management Schemas](#project-management-schemas)
- [Video Management Schemas](#video-management-schemas)
- [Ground Truth and Annotation Schemas](#ground-truth-and-annotation-schemas)
- [Test Execution Schemas](#test-execution-schemas)
- [Validation System Schemas](#validation-system-schemas)
- [Authentication and Security Schemas](#authentication-and-security-schemas)
- [Report Generation Schemas](#report-generation-schemas)
- [Database Models](#database-models)
- [Validation Rules and Constraints](#validation-rules-and-constraints)

## Schema Architecture

### CamelCase Conversion System
```python
def snake_to_camel(snake_str: str) -> str:
    """Convert snake_case to camelCase"""
    if not snake_str or snake_str.startswith('_'):
        return snake_str
    
    # Split by underscores and join, capitalizing all but the first word
    components = snake_str.split('_')
    return components[0] + ''.join(word.capitalize() for word in components[1:])

class CamelCaseModel(BaseModel):
    """Base model that automatically converts snake_case fields to camelCase aliases"""
    
    model_config = ConfigDict(
        # Generate camelCase aliases for all fields
        alias_generator=snake_to_camel,
        # Allow both snake_case and camelCase field names when parsing
        populate_by_name=True,
        # Enable serialization by alias (camelCase for frontend)
        by_alias=True,
        # Enable SQLAlchemy integration
        from_attributes=True
    )
```
**Purpose**: Automatic snake_case to camelCase conversion for frontend compatibility
**Features**: Bidirectional parsing, SQLAlchemy integration, alias generation

## Core Enums

### Architecture-Compliant Enums

#### CameraTypeEnum
```python
class CameraTypeEnum(str, Enum):
    FRONT_FACING_VRU = "Front-facing VRU"
    REAR_FACING_VRU = "Rear-facing VRU"
    IN_CAB_DRIVER_BEHAVIOR = "In-Cab Driver Behavior"
    MULTI_ANGLE_SCENARIOS = "Multi-angle"
```
**Purpose**: Camera positioning classifications for VRU detection
**Usage**: Project configuration, validation rules
**Frontend Alignment**: Maps to frontend CameraType with conversion

#### VRUType (PRD Module 1.2)
```python
class VRUType(str, Enum):
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"
    MOTORCYCLIST = "motorcyclist"
    WHEELCHAIR = "wheelchair"
    SCOOTER = "scooter"
```
**Purpose**: Vulnerable Road User classifications for YOLO detection
**Usage**: Ground truth annotation, detection validation
**Frontend Alignment**: Exact match with frontend VRUType

#### VideoStatus (PRD Module 1.1 & 1.2)
```python
class VideoStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    VALIDATED = "validated"
    ERROR = "error"
    PENDING_ANNOTATION = "pending_annotation"
    PENDING_VALIDATION = "pending_validation"
```
**Purpose**: Video workflow status management
**Usage**: Video lifecycle tracking
**Frontend Alignment**: Legacy compatibility with VideoValidationStatus

#### SignalTypeEnum
```python
class SignalTypeEnum(str, Enum):
    GPIO = "GPIO"
    NETWORK_PACKET = "Network Packet"
    SERIAL = "Serial"
    CAN_BUS = "CAN Bus"
```
**Purpose**: Hardware signal types for LabJack integration
**Usage**: Project signal configuration
**Frontend Alignment**: Maps to frontend SignalType with case conversion

#### ProjectStatusEnum
```python
class ProjectStatusEnum(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    TESTING = "testing"
    ANALYSIS = "analysis"
    COMPLETED = "completed"
    ARCHIVED = "archived"
```
**Purpose**: Project lifecycle status management
**Usage**: Project workflow tracking
**Frontend Alignment**: Maps to frontend ProjectStatus

## Project Management Schemas

### ProjectBase (Core Schema)
```python
class ProjectBase(CamelCaseModel):
    name: str
    description: Optional[str] = None
    camera_model: str
    camera_view: CameraTypeEnum
    lens_type: Optional[str] = None
    resolution: Optional[str] = None
    frame_rate: Optional[int] = None
    signal_type: SignalTypeEnum
```
**Purpose**: Base project data structure
**Features**: Required core fields, optional technical specifications
**Validation**: Field validation through Pydantic

### ProjectCreate
```python
class ProjectCreate(ProjectBase):
    pass
```
**Purpose**: Project creation request schema
**Inheritance**: Inherits all ProjectBase validation
**Usage**: POST /projects endpoint

### ProjectUpdate
```python
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
```
**Purpose**: Project update request schema
**Features**: All fields optional for partial updates
**Usage**: PUT/PATCH /projects/{id} endpoint

### ProjectResponse
```python
class ProjectResponse(ProjectBase):
    id: str
    status: str
    owner_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
```
**Purpose**: Project response schema with metadata
**Features**: Database fields, timestamps, ownership
**Serialization**: Automatic camelCase conversion for frontend

## Video Management Schemas

### VideoBase
```python
class VideoBase(CamelCaseModel):
    filename: str
    file_size: Optional[int] = None
    duration: Optional[float] = None
    fps: Optional[float] = None
    resolution: Optional[str] = None
```
**Purpose**: Base video metadata structure
**Features**: Core file properties, optional technical specs
**Validation**: File size and duration validation

### VideoResponse (Enhanced)
```python
class VideoResponse(VideoBase):
    id: str
    project_id: str
    status: str
    url: Optional[str] = None  # Full URL to access the video file
    ground_truth_generated: bool
    created_at: datetime
    uploaded_at: Optional[datetime] = Field(None, description="Upload timestamp (mapped from created_at)")
    detection_count: Optional[int] = 0
    original_name: Optional[str] = None
```
**Purpose**: Complete video response with relationships
**Features**: 
- **Project Association**: Links to project
- **Status Tracking**: Current processing status
- **URL Generation**: Direct file access URLs
- **Ground Truth Integration**: Generation status
- **Upload Tracking**: Timestamp management
- **Detection Counting**: Associated detection metrics

### VideoUploadResponse
```python
class VideoUploadResponse(CamelCaseModel):
    id: str
    project_id: str
    filename: str
    original_name: str
    size: int
    file_size: int
    duration: Optional[float] = None
    uploaded_at: str
    created_at: str
    status: str
    ground_truth_generated: bool
    processing_status: str
    detection_count: int
    message: str
```
**Purpose**: Upload operation response
**Features**: Upload confirmation, processing status, immediate feedback
**Validation**: File validation, size limits

## Ground Truth and Annotation Schemas

### GroundTruthObject
```python
class GroundTruthObject(CamelCaseModel):
    id: str
    timestamp: float
    class_label: str
    bounding_box: Dict[str, Any]
    confidence: float
```
**Purpose**: Ground truth detection representation
**Features**: Spatial data, classification, confidence scoring
**Usage**: Ground truth generation, validation reference

### GroundTruthResponse
```python
class GroundTruthResponse(CamelCaseModel):
    video_id: str
    objects: List[GroundTruthObject]
    total_detections: int
    status: str
```
**Purpose**: Ground truth collection response
**Features**: Batch ground truth data, count tracking
**Usage**: Ground truth endpoint responses

### Annotation System Schemas

#### BoundingBox (Enhanced Validation)
```python
class BoundingBox(BaseModel):
    """Bounding box coordinates with validation"""
    x: float = Field(..., ge=0, description="X coordinate (top-left)")
    y: float = Field(..., ge=0, description="Y coordinate (top-left)")
    width: float = Field(..., gt=0, description="Width of bounding box")
    height: float = Field(..., gt=0, description="Height of bounding box")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Detection confidence")
    label: Optional[str] = Field(None, description="Object label")
    
    class Config:
        populate_by_name = True
```
**Purpose**: Spatial coordinate validation
**Features**: 
- **Coordinate Validation**: Non-negative x, y
- **Size Validation**: Positive width, height
- **Confidence Range**: 0-1 confidence scores
- **Optional Metadata**: Labels, additional properties

#### AnnotationCreate
```python
class AnnotationCreate(BaseModel):
    video_id: Optional[str] = Field(None, description="Video ID - will be set from URL parameter")
    detection_id: Optional[str] = None
    frame_number: int = Field(..., ge=0)
    timestamp: float = Field(..., ge=0)
    end_timestamp: Optional[float] = Field(None, ge=0)
    vru_type: VRUTypeEnum
    bounding_box: BoundingBox
    occluded: bool = False
    truncated: bool = False
    difficult: bool = False
    notes: Optional[str] = None
    annotator: Optional[str] = None
    validated: bool = False
```
**Purpose**: Annotation creation with comprehensive validation
**Features**:
- **Temporal Validation**: Frame numbers, timestamps
- **VRU Classification**: Enum validation
- **Quality Flags**: Occlusion, truncation, difficulty
- **Annotation Tracking**: Annotator identification
- **Validation Status**: Manual validation flag

#### AnnotationResponse
```python
class AnnotationResponse(BaseModel):
    id: str
    video_id: str = Field(alias="videoId")
    detection_id: Optional[str] = Field(None, alias="detectionId")
    frame_number: int = Field(alias="frameNumber")
    timestamp: float
    end_timestamp: Optional[float] = Field(None, alias="endTimestamp")
    vru_type: str = Field(alias="vruType")
    bounding_box: Dict[str, Any] = Field(alias="boundingBox")
    occluded: bool
    truncated: bool
    difficult: bool
    notes: Optional[str] = None
    annotator: Optional[str] = None
    validated: bool
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    
    class Config:
        from_attributes = True
        populate_by_name = True
```
**Purpose**: Annotation response with camelCase serialization
**Features**: SQLAlchemy integration, alias generation, timestamp tracking

## Test Execution Schemas

### TestSessionBase
```python
class TestSessionBase(CamelCaseModel):
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
```
**Purpose**: Base test session structure
**Features**: Required associations, tolerance configuration
**Validation**: Custom name validation, whitespace handling

### TestSessionCreate
```python
class TestSessionCreate(TestSessionBase):
    pass
```
**Purpose**: Test session creation request
**Inheritance**: Full validation from TestSessionBase

### TestSessionResponse
```python
class TestSessionResponse(TestSessionBase):
    id: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
```
**Purpose**: Test session with execution metadata
**Features**: Status tracking, execution timestamps

### DetectionEvent (Core)
```python
class DetectionEvent(CamelCaseModel):
    test_session_id: str
    timestamp: float
    confidence: Optional[float] = None
    class_label: Optional[str] = None
    validation_result: Optional[str] = None
```
**Purpose**: Detection event data structure
**Features**: Session association, temporal data, validation results
**Usage**: Test execution tracking

### DetectionEventResponse
```python
class DetectionEventResponse(DetectionEvent):
    id: str
    validation_result: Optional[str]
    ground_truth_match_id: Optional[str]
    created_at: datetime
```
**Purpose**: Detection event with database metadata
**Features**: Ground truth matching, audit trail

## Validation System Schemas

### Video Validation Status System

#### VideoValidationStatus (Unified Enum)
```python
class VideoValidationStatus(str, Enum):
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
```
**Purpose**: Unified video lifecycle status
**Usage**: Video validation workflow management
**Frontend Alignment**: Exact match with frontend enum

#### ValidationScores
```python
class ValidationScores(BaseModel):
    """Detailed validation scores"""
    ground_truth_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    technical_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    content_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    overall_score: Optional[float] = Field(None, ge=0.0, le=1.0)
```
**Purpose**: Structured validation scoring
**Features**: Score range validation (0-1), optional components
**Usage**: Validation result analysis

#### ValidationCriteriaRequest
```python
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

    @field_validator('max_duration_seconds')
    def validate_duration_range(cls, v, values):
        min_duration = values.get('min_duration_seconds', 10.0)
        if v <= min_duration:
            raise ValueError('Max duration must be greater than min duration')
        return v
```
**Purpose**: Configurable validation criteria
**Features**:
- **Range Validation**: Numeric constraints
- **Pattern Validation**: Resolution format validation
- **Cross-Field Validation**: Duration range validation
- **List Constraints**: VRU type validation
- **Project Scope**: Global or project-specific criteria

## Report Generation Schemas (PRD Module 4.2)

### TestReportMetrics
```python
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
```
**Purpose**: Comprehensive test metrics for PRD compliance
**Features**: Latency analysis, pass/fail tracking, distribution data
**Usage**: Test report generation

### FailureEventDetail
```python
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
```
**Purpose**: Detailed failure analysis data
**Features**: LabJack timing data, failure classification, context
**Usage**: Failure report generation

### FailureSnapshotDetail
```python
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
```
**Purpose**: Visual evidence for failure analysis
**Features**: Snapshot management, base64 encoding, error tracking
**Usage**: Visual report generation

### TestReportResponse
```python
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
```
**Purpose**: Complete test report structure
**Features**: Comprehensive test analysis, visual evidence, metrics
**Compliance**: PRD Module 4.2 requirements

## Authentication and Security Schemas

### User Management
```python
class AuthUser(Base):
    """User authentication model for secure access"""
    __tablename__ = "auth_users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    is_superuser = Column(Boolean, default=False, index=True)
    is_verified = Column(Boolean, default=False, index=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```
**Purpose**: User authentication and authorization
**Features**: Role-based access, verification status, audit trail
**Security**: Password hashing, session management

### Session Management
```python
class UserSession(Base):
    """User session tracking for security"""
    __tablename__ = "user_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token = Column(String, nullable=False, unique=True, index=True)
    ip_address = Column(String, index=True)
    user_agent = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    last_activity = Column(DateTime(timezone=True), onupdate=func.now(), index=True)
```
**Purpose**: Session tracking and security
**Features**: Token management, activity tracking, expiration
**Security**: IP tracking, session cleanup

## Database Models

### Enhanced Model Architecture

#### Project Model
```python
class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    description = Column(Text)
    camera_model = Column(String, nullable=False)
    camera_view = Column(String, nullable=False)
    lens_type = Column(String)
    resolution = Column(String)
    frame_rate = Column(Integer)
    signal_type = Column(String, nullable=False)
    status = Column(String, default="Active", index=True)
    owner_id = Column(String(36), nullable=True, default="anonymous", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships with cascade deletes
    videos = relationship("Video", back_populates="project", cascade="all, delete-orphan")
    test_sessions = relationship("TestSession", back_populates="project", cascade="all, delete-orphan")
    annotation_sessions = relationship("AnnotationSession", back_populates="project", cascade="all, delete-orphan")
    video_links = relationship("VideoProjectLink", back_populates="project", cascade="all, delete-orphan")
```
**Purpose**: Core project data model
**Features**: Comprehensive relationships, cascade deletes, indexing
**Performance**: Strategic indexing for common queries

#### Video Model (Enhanced)
```python
class Video(Base):
    __tablename__ = "videos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    duration = Column(Float)
    fps = Column(Float)
    resolution = Column(String)
    
    # UNIFIED STATUS SYSTEM - Primary status field
    status = Column(String, default="uploaded", index=True)
    
    # VALIDATION SPECIFIC FIELDS
    validation_status = Column(String, default="pending", index=True)
    validation_type = Column(String, nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True, index=True)
    validated_by = Column(String(36), nullable=True)
    
    # GROUND TRUTH FIELDS
    ground_truth_generated = Column(Boolean, default=False, index=True)
    ground_truth_count = Column(Integer, default=0)
    ground_truth_quality_score = Column(Float, nullable=True)
    ground_truth_completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # TESTING READINESS FIELDS
    hil_testing_ready = Column(Boolean, default=False, index=True)
    hil_testing_approved_by = Column(String(36), nullable=True)
    hil_testing_approved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Enhanced composite indexes for validation system queries
    __table_args__ = (
        Index('idx_video_status_validation', 'status', 'validation_status'),
        Index('idx_video_hil_ready', 'hil_testing_ready', 'status'),
        Index('idx_video_validation_completed', 'validated_at', 'validation_type'),
        Index('idx_video_ground_truth_quality', 'ground_truth_quality_score', 'ground_truth_count'),
        Index('idx_video_testing_workflow', 'status', 'hil_testing_ready', 'validated_at'),
        # Additional performance indexes...
    )
```
**Purpose**: Comprehensive video data model
**Features**: 
- **Unified Status System**: Primary and validation status tracking
- **HIL Testing Integration**: Testing readiness flags
- **Ground Truth Management**: Quality scoring and completion tracking
- **Performance Optimization**: Extensive indexing strategy

#### DetectionEvent Model (LabJack Enhanced)
```python
class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=True, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    validation_result = Column(String, index=True)
    ground_truth_match_id = Column(String(36), ForeignKey("ground_truth_objects.id", ondelete="SET NULL"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # NEW LABJACK TIMING FIELDS - PRIMARY DATA
    latency_ms = Column(Float, nullable=True, index=True)
    labjack_timestamp = Column(Float, nullable=True, index=True)
    video_start_time = Column(Float, nullable=True, index=True)
    labjack_voltage = Column(Float, nullable=True)
    latency_threshold_ms = Column(Float, nullable=True)
    latency_result = Column(String, nullable=True, index=True)
    voltage_level = Column(Float, nullable=True)
    detection_channel = Column(String, nullable=True)
    
    # SOURCE AND DETECTION TYPE FIELDS
    source = Column(String, nullable=True, index=True, default='ai')
    detection_type = Column(String, nullable=True, index=True, default='automatic')

    # Comprehensive composite indexes for LabJack timing analysis
    __table_args__ = (
        Index('idx_detection_session_timestamp', 'test_session_id', 'timestamp'),
        Index('idx_detection_latency_validation', 'latency_ms', 'validation_result'),
        Index('idx_detection_labjack_timestamp', 'labjack_timestamp'),
        Index('idx_detection_session_latency', 'test_session_id', 'latency_ms'),
        Index('idx_detection_session_labjack_validation', 'test_session_id', 'validation_result', 'latency_ms'),
        # Additional LabJack-specific indexes...
    )
```
**Purpose**: Enhanced detection tracking with LabJack timing
**Features**:
- **LabJack Integration**: Timing, voltage, channel data
- **Latency Analysis**: Pass/fail threshold validation
- **Source Tracking**: AI vs manual detection classification
- **Performance Indexing**: LabJack-specific query optimization

## Validation Rules and Constraints

### Field Validation Examples

#### String Validation
```python
@field_validator('name')
@classmethod
def validate_name(cls, v: str) -> str:
    if not v or not v.strip():
        raise ValueError('Test session name cannot be empty')
    return v.strip()
```

#### Numeric Range Validation
```python
min_confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)
min_detection_count: int = Field(5, ge=0, le=1000)
```

#### Pattern Validation
```python
required_resolution_min: str = Field("640x480", pattern=r'^\d+x\d+$')
```

#### Cross-Field Validation
```python
@field_validator('max_duration_seconds')
def validate_duration_range(cls, v, values):
    min_duration = values.get('min_duration_seconds', 10.0)
    if v <= min_duration:
        raise ValueError('Max duration must be greater than min duration')
    return v
```

#### VRU Type Validation
```python
@field_validator('required_vru_types')
def validate_vru_types(cls, v):
    if v:
        valid_types = {"pedestrian", "cyclist", "motorcyclist", "wheelchair", "scooter"}
        invalid_types = set(v) - valid_types
        if invalid_types:
            raise ValueError(f'Invalid VRU types: {invalid_types}')
    return v
```

### Database Constraints

#### Unique Constraints
```python
email = Column(String, unique=True, nullable=False, index=True)
session_token = Column(String, nullable=False, unique=True, index=True)
```

#### Foreign Key Constraints
```python
user_id = Column(String(36), ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True)
video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=True, index=True)
```

#### Check Constraints (via Pydantic)
```python
confidence: float = Field(..., ge=0.0, le=1.0)
frame_number: int = Field(..., ge=0)
```

## Performance Optimizations

### Indexing Strategy
```python
# Enhanced composite indexes for validation system queries
__table_args__ = (
    Index('idx_video_status_validation', 'status', 'validation_status'),
    Index('idx_video_hil_ready', 'hil_testing_ready', 'status'),
    Index('idx_video_validation_completed', 'validated_at', 'validation_type'),
    Index('idx_video_ground_truth_quality', 'ground_truth_quality_score', 'ground_truth_count'),
    Index('idx_video_testing_workflow', 'status', 'hil_testing_ready', 'validated_at'),
)
```

### Relationship Optimization
```python
# Efficient cascade deletes
videos = relationship("Video", back_populates="project", cascade="all, delete-orphan")
test_sessions = relationship("TestSession", back_populates="project", cascade="all, delete-orphan")
```

### Query Optimization
```python
# Strategic indexing for common query patterns
created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
status = Column(String, default="uploaded", index=True)
validation_status = Column(String, default="pending", index=True)
```

## Schema Migration Support

### Version Compatibility
- **Backward Compatibility**: Legacy field support
- **Forward Compatibility**: Extensible schemas
- **Migration Safety**: Non-breaking schema changes

### Field Evolution
```python
# Legacy field support
processing_status = Column(String, default="pending", index=True)  # Computed from status

@property
def uploaded_at(self):
    """Backward compatibility property - maps to created_at"""
    return self.created_at
```

This comprehensive schema system ensures data integrity, validation, performance, and seamless frontend integration while maintaining backward compatibility and supporting complex business requirements.