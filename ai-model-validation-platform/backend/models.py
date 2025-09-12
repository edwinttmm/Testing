from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from passlib.context import CryptContext
import uuid

from database import Base

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Auth User Model - CRITICAL FOR DEPLOYMENT
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
    
    # Enhanced composite indexes for authentication performance
    __table_args__ = (
        Index('idx_auth_user_email_active', 'email', 'is_active'),
        Index('idx_auth_user_username_active', 'username', 'is_active'),
        Index('idx_auth_user_active_verified', 'is_active', 'is_verified'),
        Index('idx_auth_user_superuser_active', 'is_superuser', 'is_active'),
        Index('idx_auth_user_created_active', 'created_at', 'is_active'),
        Index('idx_auth_user_last_login', 'last_login'),
    )
    
    def verify_password(self, password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(password, self.hashed_password)
    
    @classmethod
    def get_password_hash(cls, password: str) -> str:
        """Generate password hash"""
        return pwd_context.hash(password)
    
    def set_password(self, password: str) -> None:
        """Set hashed password"""
        self.hashed_password = self.get_password_hash(password)

# User Session Management
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
    
    # Relationships
    user = relationship("AuthUser")
    
    # Enhanced composite indexes for session management
    __table_args__ = (
        Index('idx_session_user_active', 'user_id', 'is_active'),
        Index('idx_session_token_active', 'session_token', 'is_active'),
        Index('idx_session_expires_active', 'expires_at', 'is_active'),
        Index('idx_session_user_activity', 'user_id', 'last_activity'),
        Index('idx_session_ip_activity', 'ip_address', 'last_activity'),
        Index('idx_session_cleanup', 'expires_at', 'is_active'),  # For cleanup jobs
    )

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)  # Index for search
    description = Column(Text)
    camera_model = Column(String, nullable=False)
    camera_view = Column(String, nullable=False)  # 'Front-facing VRU', 'Rear-facing VRU', 'In-Cab Driver Behavior'
    lens_type = Column(String)
    resolution = Column(String)
    frame_rate = Column(Integer)
    signal_type = Column(String, nullable=False)  # 'GPIO', 'Network Packet', 'Serial'
    status = Column(String, default="Active", index=True)  # 'Active', 'Completed', 'Draft' - Index for filtering
    owner_id = Column(String(36), nullable=True, default="anonymous", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)  # Index for time-based queries
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    videos = relationship("Video", back_populates="project", cascade="all, delete-orphan")
    test_sessions = relationship("TestSession", back_populates="project", cascade="all, delete-orphan")
    annotation_sessions = relationship("AnnotationSession", back_populates="project", cascade="all, delete-orphan")
    video_links = relationship("VideoProjectLink", back_populates="project", cascade="all, delete-orphan")

class Video(Base):
    __tablename__ = "videos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False, index=True)  # Index for search
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    duration = Column(Float)  # in seconds
    fps = Column(Float)
    resolution = Column(String)
    
    # UNIFIED STATUS SYSTEM - Primary status field
    status = Column(String, default="uploaded", index=True)  # VideoValidationStatus enum values
    
    # VALIDATION SPECIFIC FIELDS
    validation_status = Column(String, default="pending", index=True)  # Validation workflow status
    validation_type = Column(String, nullable=True)  # 'automatic', 'manual', 'hybrid'
    validated_at = Column(DateTime(timezone=True), nullable=True, index=True)
    validated_by = Column(String(36), nullable=True)  # User ID who validated
    
    # GROUND TRUTH FIELDS
    ground_truth_generated = Column(Boolean, default=False, index=True)  # Legacy compatibility
    ground_truth_count = Column(Integer, default=0)
    ground_truth_quality_score = Column(Float, nullable=True)
    ground_truth_completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # TESTING READINESS FIELDS
    hil_testing_ready = Column(Boolean, default=False, index=True)
    hil_testing_approved_by = Column(String(36), nullable=True)
    hil_testing_approved_at = Column(DateTime(timezone=True), nullable=True)
    
    # LEGACY FIELDS (for backward compatibility)
    processing_status = Column(String, default="pending", index=True)  # Computed from status
    
    # METADATA
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    @property
    def uploaded_at(self):
        """Backward compatibility property - maps to created_at"""
        return self.created_at

    project = relationship("Project", back_populates="videos")
    ground_truth_objects = relationship("GroundTruthObject", back_populates="video", cascade="all, delete-orphan")
    annotations = relationship("Annotation", back_populates="video", cascade="all, delete-orphan")
    annotation_sessions = relationship("AnnotationSession", back_populates="video", cascade="all, delete-orphan")
    project_links = relationship("VideoProjectLink", back_populates="video", cascade="all, delete-orphan")

    # Enhanced composite indexes for validation system queries
    __table_args__ = (
        # New validation system indexes
        Index('idx_video_status_validation', 'status', 'validation_status'),
        Index('idx_video_hil_ready', 'hil_testing_ready', 'status'),
        Index('idx_video_validation_completed', 'validated_at', 'validation_type'),
        Index('idx_video_ground_truth_quality', 'ground_truth_quality_score', 'ground_truth_count'),
        Index('idx_video_testing_workflow', 'status', 'hil_testing_ready', 'validated_at'),
        
        # Legacy indexes (maintained for compatibility)
        Index('idx_video_project_status', 'project_id', 'status'),
        Index('idx_video_project_created', 'project_id', 'created_at'),
        Index('idx_video_ground_truth_status', 'ground_truth_generated', 'processing_status'),
        Index('idx_video_file_path', 'file_path'),  # For file operations
        Index('idx_video_duration_fps', 'duration', 'fps'),  # For metadata queries
        Index('idx_video_project_ground_truth', 'project_id', 'ground_truth_generated'),
        Index('idx_video_size_resolution', 'file_size', 'resolution'),  # For storage analysis
    )

class GroundTruthObject(Base):
    __tablename__ = "ground_truth_objects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    tracking_id = Column(String, nullable=True, index=True)  # Persistent VRU tracking ID across frames
    frame_number = Column(Integer, nullable=True, index=True)  # Frame number for video synchronization
    timestamp = Column(Float, nullable=False, index=True)  # Index for temporal queries
    class_label = Column(String, nullable=False, index=True)  # Index for filtering by type
    x = Column(Float, nullable=False)  # Bounding box x coordinate
    y = Column(Float, nullable=False)  # Bounding box y coordinate
    width = Column(Float, nullable=False)  # Bounding box width
    height = Column(Float, nullable=False)  # Bounding box height
    bounding_box = Column(JSON)  # Deprecated - keeping for backward compatibility
    confidence = Column(Float, index=True)  # Index for confidence-based queries
    validated = Column(Boolean, default=False, index=True)  # Whether this detection has been validated
    difficult = Column(Boolean, default=False)  # Whether this is a difficult detection
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="ground_truth_objects")

    # Enhanced composite indexes for performance-critical queries
    __table_args__ = (
        Index('idx_gt_video_timestamp', 'video_id', 'timestamp'),
        Index('idx_gt_video_class', 'video_id', 'class_label'),
        Index('idx_gt_timestamp_class', 'timestamp', 'class_label'),  # For temporal class queries
        Index('idx_gt_video_frame', 'video_id', 'frame_number'),  # For frame-based queries
        Index('idx_gt_video_confidence', 'video_id', 'confidence'),  # For confidence filtering
        Index('idx_gt_validated_class', 'validated', 'class_label'),  # For validation queries
        Index('idx_gt_spatial_bounds', 'x', 'y', 'width', 'height'),  # For spatial queries
        Index('idx_gt_video_validated_timestamp', 'video_id', 'validated', 'timestamp'),  # Complex filtering
        Index('idx_gt_video_tracking_id', 'video_id', 'tracking_id'),  # For VRU tracking across frames
        Index('idx_gt_tracking_timestamp', 'tracking_id', 'timestamp'),  # For temporal VRU tracking
    )

class TestSession(Base):
    __tablename__ = "test_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)  # Index for search
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    tolerance_ms = Column(Integer, default=100)
    status = Column(String, default="created", index=True)  # Index for status filtering
    session_type = Column(String, default="user_created", index=True)  # "user_created", "auto_generated", "system_test"
    started_at = Column(DateTime(timezone=True), index=True)  # Index for time-based queries
    completed_at = Column(DateTime(timezone=True), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ENHANCED PRECISION TIMING FIELDS FOR HIL VALIDATION
    latency_threshold_ms = Column(Integer, default=100, index=True)  # Pass/Fail threshold for latency
    video_start_timestamp = Column(Float, nullable=True, index=True)  # Session video start time reference
    video_start_timestamp_ns = Column(String, nullable=True, index=True)  # Nanosecond precision timestamp (stored as string)
    precision_timing_enabled = Column(Boolean, default=True, index=True)  # Whether precision timing is active
    timing_accuracy_ns = Column(Float, nullable=True)  # Measured timing accuracy for this session
    drift_compensation_active = Column(Boolean, default=False)  # Whether drift compensation is enabled
    frame_sync_enabled = Column(Boolean, default=False)  # Whether frame synchronization is active
    sync_point_id = Column(String, nullable=True, index=True)  # Reference to precision timing sync point
    calibration_timestamp = Column(Float, nullable=True)  # Timestamp of last timing calibration
    timing_validation_status = Column(String, default="pending", index=True)  # 'pending', 'passed', 'failed'
    hil_compliance_verified = Column(Boolean, default=False, index=True)  # HIL timing requirements verified

    project = relationship("Project", back_populates="test_sessions")
    detection_events = relationship("DetectionEvent", back_populates="test_session", cascade="all, delete-orphan")
    results = relationship("TestResult", back_populates="test_session", cascade="all, delete-orphan")
    detection_comparisons = relationship("DetectionComparison", back_populates="test_session", cascade="all, delete-orphan")

    # Composite index for common queries
    __table_args__ = (
        Index('idx_testsession_project_status', 'project_id', 'status'),
        Index('idx_testsession_project_created', 'project_id', 'created_at'),
        Index('idx_testsession_type_status', 'session_type', 'status'),  # Filter by session type and status
        Index('idx_testsession_type_created', 'session_type', 'created_at'),  # Session type with time
        Index('idx_testsession_user_sessions', 'session_type', 'status', 'created_at'),  # UI filtering
    )

class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=True, index=True)  # FIXED: Added video_id relationship
    timestamp = Column(Float, nullable=False, index=True)  # Index for temporal queries
    validation_result = Column(String, index=True)  # Index for filtering by validation result ('Pass', 'Fail')
    ground_truth_match_id = Column(String(36), ForeignKey("ground_truth_objects.id", ondelete="SET NULL"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # ENHANCED PRECISION TIMING FIELDS - HIL VALIDATION
    latency_ms = Column(Float, nullable=True, index=True)  # Calculated latency between signal and detection
    latency_ns = Column(String, nullable=True)  # Nanosecond precision latency (stored as string for precision)
    labjack_timestamp = Column(Float, nullable=True, index=True)  # LabJack detection timestamp
    labjack_timestamp_ns = Column(String, nullable=True)  # Nanosecond precision LabJack timestamp
    video_start_time = Column(Float, nullable=True, index=True)  # Video start reference time
    video_start_time_ns = Column(String, nullable=True)  # Nanosecond precision video start time
    timing_accuracy_ns = Column(Float, nullable=True)  # Estimated accuracy for this measurement
    frame_accurate_timestamp = Column(Float, nullable=True)  # Frame-accurate timestamp if available
    labjack_voltage = Column(Float, nullable=True)  # LabJack voltage reading if available
    latency_threshold_ms = Column(Float, nullable=True)  # Threshold used for validation
    latency_result = Column(String, nullable=True, index=True)  # 'pass', 'fail', 'error', 'timeout'
    voltage_level = Column(Float, nullable=True)  # LabJack voltage reading that triggered detection
    detection_channel = Column(String, nullable=True)  # LabJack channel used for detection
    
    # PRECISION TIMING METADATA
    monotonic_timestamp_ns = Column(String, nullable=True)  # Monotonic clock timestamp for drift compensation
    sync_point_reference = Column(String, nullable=True)  # Reference to timing sync point
    drift_compensated = Column(Boolean, default=False)  # Whether drift compensation was applied
    timing_interpolated = Column(Boolean, default=False)  # Whether timestamp was interpolated
    
    # LEGACY AI FIELDS (deprecated but kept for backward compatibility)
    confidence = Column(Float, index=True)  # Index for confidence-based filtering (deprecated for LabJack)
    class_label = Column(String, index=True)  # Index for filtering by detection type (deprecated for LabJack)
    
    # NEW FIELDS FOR COMPLETE DETECTION STORAGE
    detection_id = Column(String(36), nullable=True, index=True)  # Unique detection identifier
    frame_number = Column(Integer, nullable=True, index=True)  # Frame correlation
    vru_type = Column(String, nullable=True, index=True)  # VRU classification
    
    # Bounding box coordinates (spatial data) - deprecated for LabJack timing validation
    bounding_box_x = Column(Float, nullable=True)  # X coordinate
    bounding_box_y = Column(Float, nullable=True)  # Y coordinate  
    bounding_box_width = Column(Float, nullable=True)  # Width
    bounding_box_height = Column(Float, nullable=True)  # Height
    
    @property
    def bounding_box(self):
        """Construct bounding_box dict from individual fields for API compatibility."""
        if self.bounding_box_x is not None:
            return {
                "x": self.bounding_box_x,
                "y": self.bounding_box_y,
                "width": self.bounding_box_width,
                "height": self.bounding_box_height
            }
        return None
    
    # Visual evidence paths
    screenshot_path = Column(String, nullable=True)  # Full frame screenshot
    screenshot_zoom_path = Column(String, nullable=True)  # Zoomed region screenshot
    
    # Processing metadata
    processing_time_ms = Column(Float, nullable=True)  # Time taken for detection
    model_version = Column(String, nullable=True)  # ML model version used
    
    # SOURCE AND DETECTION TYPE - CRITICAL FIX for Manual/AI display issue
    source = Column(String, nullable=True, index=True, default='ai')  # 'ai' or 'manual' - fixes frontend display
    detection_type = Column(String, nullable=True, index=True, default='automatic')  # 'automatic' or 'manual'

    # RELATIONSHIPS - FIXED: Added missing video relationship with CASCADE
    test_session = relationship("TestSession", back_populates="detection_events")
    video = relationship("Video")  # Video relationship for data integrity
    ground_truth_match = relationship("GroundTruthObject", foreign_keys=[ground_truth_match_id])

    # Comprehensive composite indexes for performance-critical queries - UPDATED FOR LABJACK
    __table_args__ = (
        Index('idx_detection_session_timestamp', 'test_session_id', 'timestamp'),
        Index('idx_detection_session_validation', 'test_session_id', 'validation_result'),
        Index('idx_detection_video_timestamp', 'video_id', 'timestamp'),  # FIXED: Added video-based queries
        Index('idx_detection_video_validation', 'video_id', 'validation_result'),  # FIXED: Added video validation queries
        
        # LABJACK TIMING SPECIFIC INDEXES
        Index('idx_detection_latency_validation', 'latency_ms', 'validation_result'),  # Latency analysis
        Index('idx_detection_labjack_timestamp', 'labjack_timestamp'),  # LabJack timing queries
        Index('idx_detection_session_latency', 'test_session_id', 'latency_ms'),  # Session latency analysis
        Index('idx_detection_video_start_time', 'video_start_time'),  # Video timing reference
        Index('idx_detection_labjack_voltage', 'labjack_voltage'),  # Voltage analysis
        Index('idx_detection_session_labjack_validation', 'test_session_id', 'validation_result', 'latency_ms'),  # Complex LabJack queries
        
        # LEGACY INDEXES (for backward compatibility)
        Index('idx_detection_timestamp_confidence', 'timestamp', 'confidence'),
        Index('idx_detection_frame_class', 'frame_number', 'class_label'),
        Index('idx_detection_bbox_area', 'bounding_box_width', 'bounding_box_height'),
        Index('idx_detection_session_frame', 'test_session_id', 'frame_number'),  # Frame-based queries
        Index('idx_detection_class_confidence', 'class_label', 'confidence'),  # Class filtering with confidence
        Index('idx_detection_vru_validation', 'vru_type', 'validation_result'),  # VRU analysis
        Index('idx_detection_processing_time', 'processing_time_ms'),  # Performance analysis
        Index('idx_detection_model_version', 'model_version'),  # Model tracking
        Index('idx_detection_spatial_center', 'bounding_box_x', 'bounding_box_y'),  # Spatial center queries
        Index('idx_detection_session_class_timestamp', 'test_session_id', 'class_label', 'timestamp'),  # Complex filtering
        Index('idx_detection_confidence_validation_timestamp', 'confidence', 'validation_result', 'timestamp'),  # Analytics
    )

class Annotation(Base):
    """Ground Truth Annotation Model with detection ID tracking"""
    __tablename__ = "annotations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    detection_id = Column(String(36), nullable=True, index=True)  # DET_PED_0001, etc.
    frame_number = Column(Integer, nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    end_timestamp = Column(Float, nullable=True)  # For temporal annotations
    vru_type = Column(String, nullable=False, index=True)  # pedestrian, cyclist, etc.
    bounding_box = Column(JSON, nullable=False)  # {"x": 0, "y": 0, "width": 100, "height": 100}
    occluded = Column(Boolean, default=False)
    truncated = Column(Boolean, default=False)
    difficult = Column(Boolean, default=False)
    notes = Column(Text)
    annotator = Column(String(36))
    validated = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    video = relationship("Video", back_populates="annotations")
    
    # Comprehensive composite indexes for performance
    __table_args__ = (
        Index('idx_annotation_video_frame', 'video_id', 'frame_number'),
        Index('idx_annotation_video_timestamp', 'video_id', 'timestamp'),
        Index('idx_annotation_video_validated', 'video_id', 'validated'),
        Index('idx_annotation_detection_id', 'detection_id'),
        Index('idx_annotation_vru_validated', 'vru_type', 'validated'),
        Index('idx_annotation_video_vru_frame', 'video_id', 'vru_type', 'frame_number'),  # VRU frame queries
        Index('idx_annotation_annotator_validated', 'annotator', 'validated'),  # Annotator performance
        Index('idx_annotation_temporal_range', 'timestamp', 'end_timestamp'),  # Temporal range queries
        Index('idx_annotation_video_annotator_created', 'video_id', 'annotator', 'created_at'),  # Annotator tracking
        Index('idx_annotation_vru_timestamp_validated', 'vru_type', 'timestamp', 'validated'),  # Complex VRU analysis
        Index('idx_annotation_difficulty_analysis', 'difficult', 'occluded', 'truncated'),  # Quality analysis
        Index('idx_annotation_video_temporal_coverage', 'video_id', 'timestamp', 'end_timestamp'),  # Coverage analysis
    )

class AnnotationSession(Base):
    """Annotation session tracking for collaborative annotation"""
    __tablename__ = "annotation_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    annotator_id = Column(String(36), nullable=True, index=True)
    status = Column(String, default="active", index=True)  # 'active', 'paused', 'completed'
    total_detections = Column(Integer, default=0)
    validated_detections = Column(Integer, default=0)
    current_frame = Column(Integer, default=0)
    total_frames = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    video = relationship("Video", back_populates="annotation_sessions")
    project = relationship("Project", back_populates="annotation_sessions")

class VideoProjectLink(Base):
    """Project-Video linking system for video assignment"""
    __tablename__ = "video_project_links"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_reason = Column(Text)
    intelligent_match = Column(Boolean, default=True)
    confidence_score = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    video = relationship("Video", back_populates="project_links")
    project = relationship("Project", back_populates="video_links")
    
    # Enhanced composite indexes
    __table_args__ = (
        Index('idx_video_project_unique', 'video_id', 'project_id', unique=True),
        Index('idx_video_project_intelligent', 'intelligent_match', 'confidence_score'),  # AI matching
        Index('idx_video_project_link_created', 'project_id', 'created_at'),  # Temporal assignment tracking
        Index('idx_video_assignment_confidence', 'confidence_score'),  # Confidence analysis
    )

class TestResult(Base):
    """Enhanced test results with LabJack timing-based validation metrics"""
    __tablename__ = "test_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # PRIMARY LABJACK TIMING METRICS
    pass_rate = Column(Float, index=True)  # Percentage of detections that passed latency threshold
    avg_latency_ms = Column(Float, index=True)  # Average latency across all detections
    max_latency_ms = Column(Float, index=True)  # Maximum latency detected
    min_latency_ms = Column(Float, index=True)  # Minimum latency detected
    median_latency_ms = Column(Float, index=True)  # Median latency for better distribution understanding
    std_dev_latency_ms = Column(Float, index=True)  # Standard deviation of latency
    total_detections = Column(Integer, index=True)  # Total number of detection events
    passed_detections = Column(Integer, index=True)  # Number of detections that passed threshold
    failed_detections = Column(Integer, index=True)  # Number of detections that failed threshold
    threshold_ms = Column(Integer, index=True)  # Latency threshold used for validation
    latency_distribution = Column(JSON)  # Histogram bins and distribution data
    
    # VALIDATION METADATA
    validation_type = Column(String(50), default="latency_based", index=True)  # Type of validation used
    test_duration_seconds = Column(Float)  # Total test duration
    detection_rate_hz = Column(Float)  # Detections per second
    
    # LEGACY AI METRICS (kept for backward compatibility, mapped from latency metrics)
    accuracy = Column(Float)  # Maps to pass_rate for compatibility
    precision = Column(Float)  # Maps to pass_rate for compatibility  
    recall = Column(Float)  # Maps to pass_rate for compatibility
    f1_score = Column(Float)  # Maps to pass_rate for compatibility
    true_positives = Column(Integer)  # Maps to passed_detections
    false_positives = Column(Integer)  # Maps to failed_detections
    false_negatives = Column(Integer, default=0)  # Not applicable for latency validation
    statistical_analysis = Column(JSON)  # Contains detailed latency metrics and histogram
    confidence_intervals = Column(JSON)  # Statistical confidence data
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships - CASCADE handled by parent TestSession
    test_session = relationship("TestSession", back_populates="results")
    
    # Enhanced composite indexes for LabJack timing analysis
    __table_args__ = (
        Index('idx_testresult_session_pass_rate', 'test_session_id', 'pass_rate'),
        Index('idx_testresult_avg_latency', 'avg_latency_ms'),
        Index('idx_testresult_max_latency', 'max_latency_ms'),
        Index('idx_testresult_total_detections', 'total_detections'),
        Index('idx_testresult_session_created', 'test_session_id', 'created_at'),
        Index('idx_testresult_latency_range', 'min_latency_ms', 'max_latency_ms'),  # Latency range analysis
        Index('idx_testresult_pass_fail_counts', 'passed_detections', 'failed_detections'),  # Pass/fail analysis
    )

class DetectionComparison(Base):
    """Detection comparison for ground truth validation"""
    __tablename__ = "detection_comparisons"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    ground_truth_id = Column(String(36), ForeignKey("annotations.id", ondelete="SET NULL"))
    detection_event_id = Column(String(36), ForeignKey("detection_events.id", ondelete="SET NULL"))
    match_type = Column(String, nullable=False, index=True)  # 'TP', 'FP', 'FN', 'TN'
    iou_score = Column(Float)
    distance_error = Column(Float)
    temporal_offset = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships - CASCADE handled by parent TestSession  
    test_session = relationship("TestSession", back_populates="detection_comparisons")
    ground_truth = relationship("Annotation")
    detection_event = relationship("DetectionEvent")
    
    # Enhanced composite indexes for analysis
    __table_args__ = (
        Index('idx_comparison_session_match', 'test_session_id', 'match_type'),
        Index('idx_comparison_iou_temporal', 'iou_score', 'temporal_offset'),  # Accuracy analysis
        Index('idx_comparison_session_ground_truth', 'test_session_id', 'ground_truth_id'),  # Ground truth tracking
        Index('idx_comparison_session_detection', 'test_session_id', 'detection_event_id'),  # Detection tracking
        Index('idx_comparison_match_iou', 'match_type', 'iou_score'),  # Quality metrics
        Index('idx_comparison_temporal_distance', 'temporal_offset', 'distance_error'),  # Error analysis
    )

# Report Generation Models - PRD Module 4.2
class TestReport(Base):
    """Test report metadata storage for PRD Module 4.2"""
    __tablename__ = "test_reports"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    report_name = Column(String, nullable=False, index=True)
    report_type = Column(String, nullable=False, index=True)  # 'comprehensive', 'summary', 'failure_analysis'
    formats_generated = Column(JSON)  # List of generated formats: ['html', 'pdf', 'json']
    
    # Report metrics snapshot
    total_events = Column(Integer, default=0)
    passed_events = Column(Integer, default=0)
    failed_events = Column(Integer, default=0)
    pass_rate_percent = Column(Float, index=True)
    average_latency_ms = Column(Float, index=True)
    test_outcome = Column(String, index=True)  # 'PASS', 'FAIL', 'NO_DATA'
    
    # File paths for generated reports
    html_report_path = Column(String)
    pdf_report_path = Column(String)
    json_report_path = Column(String)
    csv_summary_path = Column(String)
    
    # Snapshot metadata
    failure_snapshots_count = Column(Integer, default=0)
    snapshots_storage_path = Column(String)
    total_snapshot_size_bytes = Column(Integer, default=0)
    
    # Generation metadata
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    generation_time_ms = Column(Float)  # Time taken to generate report
    generated_by = Column(String(36), default="system")  # User who generated report
    
    # Relationships
    test_session = relationship("TestSession", backref="reports")
    
    # Enhanced composite indexes for report queries
    __table_args__ = (
        Index('idx_report_session_type', 'test_session_id', 'report_type'),
        Index('idx_report_generated_outcome', 'generated_at', 'test_outcome'),
        Index('idx_report_pass_rate', 'pass_rate_percent'),
        Index('idx_report_session_generated', 'test_session_id', 'generated_at'),
        Index('idx_report_type_outcome', 'report_type', 'test_outcome'),
    )

class ReportSnapshot(Base):
    """Failure snapshot metadata for report generation"""
    __tablename__ = "report_snapshots"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String(36), ForeignKey("test_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    detection_event_id = Column(String(36), ForeignKey("detection_events.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Snapshot details
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="SET NULL"), index=True)
    failure_type = Column(String, nullable=False, index=True)  # 'HIGH_LATENCY', 'MISSED_DETECTION'
    timestamp_ms = Column(Float, nullable=False, index=True)
    frame_number = Column(Integer, index=True)
    
    # File information
    snapshot_filename = Column(String, nullable=False)
    snapshot_path = Column(String, nullable=False)
    file_size_bytes = Column(Integer)
    
    # Video properties at capture
    video_fps = Column(Float)
    video_total_frames = Column(Integer)
    
    # Generation metadata
    captured_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    capture_success = Column(Boolean, default=True, index=True)
    error_message = Column(Text)
    
    # Relationships
    report = relationship("TestReport", backref="snapshots")
    detection_event = relationship("DetectionEvent")
    video = relationship("Video")
    
    # Enhanced composite indexes for snapshot queries
    __table_args__ = (
        Index('idx_snapshot_report_failure', 'report_id', 'failure_type'),
        Index('idx_snapshot_event_timestamp', 'detection_event_id', 'timestamp_ms'),
        Index('idx_snapshot_video_frame', 'video_id', 'frame_number'),
        Index('idx_snapshot_failure_captured', 'failure_type', 'captured_at'),
        Index('idx_snapshot_success_type', 'capture_success', 'failure_type'),
        Index('idx_snapshot_report_timestamp', 'report_id', 'timestamp_ms'),
    )

# Import simple detection models
from src.models.detection_session import DetectionSession, StoredDetectionEvent, VideoEvent

# Video Validation System Models

class VideoValidationCriteria(Base):
    """Configurable validation criteria per project or globally"""
    __tablename__ = "video_validation_criteria"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)  # NULL = global
    
    # Ground truth quality requirements
    min_detection_count = Column(Integer, default=5)
    min_confidence_threshold = Column(Float, default=0.7)
    min_frame_coverage_percent = Column(Float, default=80.0)
    
    # Technical requirements
    min_duration_seconds = Column(Float, default=10.0)
    max_duration_seconds = Column(Float, default=300.0)
    required_resolution_min = Column(String, default="640x480")
    min_fps = Column(Float, default=24.0)
    
    # Content requirements
    required_vru_types = Column(JSON)  # ['pedestrian', 'cyclist']
    min_scene_complexity_score = Column(Float, default=0.5)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    project = relationship("Project", backref="validation_criteria")
    
    # Enhanced indexes
    __table_args__ = (
        Index('idx_validation_criteria_project', 'project_id'),
        Index('idx_validation_criteria_created', 'created_at'),
        Index('idx_validation_criteria_thresholds', 'min_detection_count', 'min_confidence_threshold'),
    )

class VideoValidationResult(Base):
    """Results of validation process"""
    __tablename__ = "video_validation_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    validation_criteria_id = Column(String(36), ForeignKey("video_validation_criteria.id"), nullable=False)
    
    # Validation results
    validation_type = Column(String, nullable=False, index=True)  # 'automatic', 'manual'
    overall_result = Column(String, nullable=False, index=True)  # 'passed', 'failed', 'needs_review'
    
    # Detailed results
    ground_truth_score = Column(Float)
    technical_score = Column(Float)
    content_score = Column(Float)
    overall_score = Column(Float, index=True)
    
    # Validation details
    criteria_met = Column(JSON)  # Detailed criteria pass/fail
    validation_notes = Column(Text)
    validated_by = Column(String(36), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    video = relationship("Video", backref="validation_results")
    validation_criteria = relationship("VideoValidationCriteria", backref="validation_results")
    
    # Enhanced indexes for validation queries
    __table_args__ = (
        Index('idx_validation_result_video', 'video_id'),
        Index('idx_validation_result_type', 'validation_type'),
        Index('idx_validation_result_overall', 'overall_result'),
        Index('idx_validation_result_score', 'overall_score'),
        Index('idx_validation_result_created', 'created_at'),
        Index('idx_validation_result_video_created', 'video_id', 'created_at'),
        Index('idx_validation_result_type_result', 'validation_type', 'overall_result'),
    )

class VideoStatusTransition(Base):
    """Audit trail for status changes"""
    __tablename__ = "video_status_transitions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    from_status = Column(String, nullable=False, index=True)
    to_status = Column(String, nullable=False, index=True)
    transition_reason = Column(String, nullable=False)
    
    # Context
    triggered_by = Column(String(36), nullable=True)  # User ID or 'system'
    transition_metadata = Column(JSON)  # Additional context data
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    video = relationship("Video", backref="status_transitions")
    
    # Enhanced indexes for audit queries
    __table_args__ = (
        Index('idx_status_transition_video', 'video_id'),
        Index('idx_status_transition_video_time', 'video_id', 'created_at'),
        Index('idx_status_transition_from_to', 'from_status', 'to_status'),
        Index('idx_status_transition_created', 'created_at'),
        Index('idx_status_transition_reason', 'transition_reason'),
        Index('idx_status_transition_triggered_by', 'triggered_by'),
    )

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, default="anonymous", index=True)
    event_type = Column(String, nullable=False, index=True)  # Index for filtering by event type
    event_data = Column(JSON)  # additional event details
    ip_address = Column(String, index=True)  # Index for security queries
    user_agent = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)  # Index for time-based queries

    # Enhanced composite indexes for comprehensive audit tracking
    __table_args__ = (
        Index('idx_audit_user_event', 'user_id', 'event_type'),
        Index('idx_audit_created_event', 'created_at', 'event_type'),
        Index('idx_audit_ip_event_time', 'ip_address', 'event_type', 'created_at'),  # Security monitoring
        Index('idx_audit_user_time_range', 'user_id', 'created_at'),  # User activity tracking
        Index('idx_audit_event_data_analysis', 'event_type', 'created_at'),  # Event analysis
    )