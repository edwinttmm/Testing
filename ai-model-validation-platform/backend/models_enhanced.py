from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, ForeignKey, JSON, Index, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from database import Base

# Enums for better type safety and architecture compliance
class ProjectStatus(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    TESTING = "testing"
    ANALYSIS = "analysis"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class CameraView(enum.Enum):
    FRONT_FACING_VRU = "Front-facing VRU"
    REAR_FACING_VRU = "Rear-facing VRU"
    IN_CAB_DRIVER_BEHAVIOR = "In-Cab Driver Behavior"
    MULTI_ANGLE = "Multi-angle"

class SignalType(enum.Enum):
    GPIO = "GPIO"
    NETWORK_PACKET = "Network Packet"
    SERIAL = "Serial"
    CAN_BUS = "CAN Bus"
    ETHERNET = "Ethernet"

class VideoStatus(enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"

class VRUClass(enum.Enum):
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"
    MOTORCYCLIST = "motorcyclist"
    WHEELCHAIR_USER = "wheelchair_user"
    SCOOTER_RIDER = "scooter_rider"
    CHILD_WITH_STROLLER = "child_with_stroller"

class TestSessionStatus(enum.Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ValidationResult(enum.Enum):
    TRUE_POSITIVE = "TP"
    FALSE_POSITIVE = "FP"
    FALSE_NEGATIVE = "FN"
    PENDING = "PENDING"
    ERROR = "ERROR"

class Project(Base):
    """Enhanced Project model following architecture specifications"""
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    description = Column(Text)
    camera_model = Column(String, nullable=False)
    camera_view = Column(Enum(CameraView), nullable=False)
    lens_type = Column(String)
    resolution = Column(String)
    frame_rate = Column(Integer)
    signal_type = Column(Enum(SignalType), nullable=False)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.ACTIVE, index=True)
    owner_id = Column(String(36), nullable=True, default="anonymous", index=True)
    
    # New architecture fields
    pass_fail_criteria = Column(JSON)  # Store PassFailCriteria as JSON
    max_videos = Column(Integer, default=100)
    tolerance_ms = Column(Integer, default=100)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    videos = relationship("Video", back_populates="project", cascade="all, delete-orphan")
    test_sessions = relationship("TestSession", back_populates="project", cascade="all, delete-orphan")

class Video(Base):
    """Enhanced Video model with library management features"""
    __tablename__ = "videos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    duration = Column(Float)  # in seconds
    fps = Column(Float)
    resolution = Column(String)
    status = Column(Enum(VideoStatus), default=VideoStatus.UPLOADED, index=True)
    ground_truth_generated = Column(Boolean, default=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # New architecture fields
    thumbnail_path = Column(String)  # Path to video thumbnail
    preview_frames = Column(JSON)  # Array of preview frame paths
    video_metadata = Column(JSON)  # Extended metadata (codec, bitrate, etc.)
    quality_score = Column(Float)  # Video quality assessment score
    category = Column(String)  # Video category for organization
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    project = relationship("Project", back_populates="videos")
    ground_truth_objects = relationship("GroundTruthObject", back_populates="video", cascade="all, delete-orphan")
    test_sessions = relationship("TestSession", back_populates="video")

    # Composite index for common queries
    __table_args__ = (
        Index('idx_video_project_status', 'project_id', 'status'),
        Index('idx_video_project_created', 'project_id', 'created_at'),
        Index('idx_video_category_status', 'category', 'status'),
    )

class GroundTruthObject(Base):
    """Enhanced Ground Truth model with VRU classification"""
    __tablename__ = "ground_truth_objects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    class_label = Column(Enum(VRUClass), nullable=False, index=True)
    bounding_box = Column(JSON)  # {"x": 0, "y": 0, "width": 100, "height": 100}
    confidence = Column(Float, index=True)
    
    # New architecture fields
    frame_number = Column(Integer, index=True)  # Frame number in video
    occlusion_level = Column(Float)  # 0.0 = no occlusion, 1.0 = fully occluded
    difficulty_level = Column(String)  # easy, medium, hard
    annotation_source = Column(String)  # manual, automatic, verified
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="ground_truth_objects")

    # Composite index for common queries
    __table_args__ = (
        Index('idx_gt_video_timestamp', 'video_id', 'timestamp'),
        Index('idx_gt_video_class', 'video_id', 'class_label'),
        Index('idx_gt_frame_class', 'frame_number', 'class_label'),
    )

class TestSession(Base):
    """Enhanced Test Session model with detailed configuration"""
    __tablename__ = "test_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    tolerance_ms = Column(Integer, default=100)
    status = Column(Enum(TestSessionStatus), default=TestSessionStatus.CREATED, index=True)
    
    # New architecture fields
    test_configuration = Column(JSON)  # Test parameters and settings
    expected_detections = Column(Integer)  # Expected number of detections
    actual_detections = Column(Integer)  # Actual detections found
    pass_fail_result = Column(String)  # PASS, FAIL, CONDITIONAL_PASS
    overall_score = Column(Float)  # Overall performance score (0-100)
    
    started_at = Column(DateTime(timezone=True), index=True)
    completed_at = Column(DateTime(timezone=True), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    project = relationship("Project", back_populates="test_sessions")
    video = relationship("Video", back_populates="test_sessions")
    detection_events = relationship("DetectionEvent", back_populates="test_session", cascade="all, delete-orphan")
    signal_events = relationship("SignalEvent", back_populates="test_session", cascade="all, delete-orphan")

    # Composite index for common queries
    __table_args__ = (
        Index('idx_testsession_project_status', 'project_id', 'status'),
        Index('idx_testsession_project_created', 'project_id', 'created_at'),
    )

class DetectionEvent(Base):
    """Enhanced Detection Event model with ML pipeline data"""
    __tablename__ = "detection_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    confidence = Column(Float, index=True)
    class_label = Column(Enum(VRUClass), index=True)
    validation_result = Column(Enum(ValidationResult), default=ValidationResult.PENDING, index=True)
    ground_truth_match_id = Column(String(36), ForeignKey("ground_truth_objects.id", ondelete="SET NULL"), index=True)
    
    # New architecture fields
    bounding_box = Column(JSON)  # Detection bounding box
    frame_number = Column(Integer, index=True)  # Frame number in video
    processing_time_ms = Column(Float)  # Time taken to process this detection
    screenshot_path = Column(String)  # Path to detection screenshot
    model_version = Column(String)  # Version of ML model used
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    test_session = relationship("TestSession", back_populates="detection_events")
    ground_truth_object = relationship("GroundTruthObject")

    # Composite index for performance-critical queries
    __table_args__ = (
        Index('idx_detection_session_timestamp', 'test_session_id', 'timestamp'),
        Index('idx_detection_session_validation', 'test_session_id', 'validation_result'),
        Index('idx_detection_timestamp_confidence', 'timestamp', 'confidence'),
        Index('idx_detection_frame_class', 'frame_number', 'class_label'),
    )

class SignalEvent(Base):
    """Signal events from external sources (GPIO, Network, Serial, CAN)"""
    __tablename__ = "signal_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    signal_type = Column(Enum(SignalType), nullable=False, index=True)
    signal_data = Column(JSON)  # Signal payload
    source_identifier = Column(String, index=True)  # GPIO pin, IP:port, device path
    precision_us = Column(Float, default=0.0)  # Timing precision in microseconds
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    test_session = relationship("TestSession", back_populates="signal_events")

    __table_args__ = (
        Index('idx_signal_session_timestamp', 'test_session_id', 'timestamp'),
        Index('idx_signal_type_timestamp', 'signal_type', 'timestamp'),
    )

class PerformanceMetrics(Base):
    """Performance metrics for test sessions"""
    __tablename__ = "performance_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Core metrics
    precision = Column(Float, nullable=False)
    recall = Column(Float, nullable=False)
    f1_score = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=False)
    
    # Timing metrics
    mean_latency_ms = Column(Float)
    std_latency_ms = Column(Float)
    max_latency_ms = Column(Float)
    within_tolerance_percentage = Column(Float)
    
    # Detection counts
    true_positives = Column(Integer, default=0)
    false_positives = Column(Integer, default=0)
    false_negatives = Column(Integer, default=0)
    
    # Additional metrics
    overall_score = Column(Float)  # 0-100 score
    statistical_data = Column(JSON)  # Statistical analysis results
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class VideoAssignment(Base):
    """Track video assignments to projects with compatibility scores"""
    __tablename__ = "video_assignments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    compatibility_score = Column(Float, nullable=False)
    assignment_reason = Column(Text)
    assigned_by = Column(String(36), default="system")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index('idx_assignment_project_score', 'project_id', 'compatibility_score'),
    )

class AuditLog(Base):
    """Enhanced audit logging with resource tracking"""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, default="anonymous", index=True)
    event_type = Column(String, nullable=False, index=True)
    event_data = Column(JSON)  # additional event details
    ip_address = Column(String, index=True)
    user_agent = Column(String)
    
    # New architecture fields
    session_id = Column(String(36), index=True)  # Session tracking
    resource_type = Column(String, index=True)  # Type of resource accessed
    resource_id = Column(String(36), index=True)  # ID of resource accessed
    action = Column(String, index=True)  # CREATE, READ, UPDATE, DELETE
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Composite index for audit queries
    __table_args__ = (
        Index('idx_audit_user_event', 'user_id', 'event_type'),
        Index('idx_audit_created_event', 'created_at', 'event_type'),
        Index('idx_audit_resource_action', 'resource_type', 'action'),
    )

class ModelRegistry(Base):
    """Registry for ML models used in detection"""
    __tablename__ = "model_registry"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    version = Column(String, nullable=False)
    model_type = Column(String, nullable=False)  # yolov8, yolov5, custom
    file_path = Column(String, nullable=False)
    configuration = Column(JSON)  # Model-specific configuration
    performance_metrics = Column(JSON)  # Benchmark performance data
    is_active = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_model_name_version', 'name', 'version'),
    )

class Screenshot(Base):
    """Screenshot captures from detection events"""
    __tablename__ = "screenshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    detection_event_id = Column(String(36), ForeignKey("detection_events.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String, nullable=False)
    screenshot_type = Column(String, default="annotated")  # raw, annotated, zoomed
    file_size = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SystemConfiguration(Base):
    """System-wide configuration settings"""
    __tablename__ = "system_configuration"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String, nullable=False, unique=True, index=True)
    value = Column(JSON, nullable=False)
    description = Column(Text)
    category = Column(String, index=True)  # detection, validation, performance
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())