"""
Refactored Models: Project as Playlist with Video-Centric Camera Metadata
Following PRD requirements for lightweight project playlists and proper data normalization
"""

from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, ForeignKey, JSON, Index, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from passlib.context import CryptContext
import uuid

from database import Base

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Many-to-many association table for Project-Video relationships
project_videos = Table(
    'project_videos',
    Base.metadata,
    Column('project_id', String(36), ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True),
    Column('video_id', String(36), ForeignKey('videos.id', ondelete='CASCADE'), primary_key=True),
    Column('sequence_order', Integer, nullable=False, default=0, index=True),
    Column('added_by', String(36), nullable=True),
    Column('notes', Text),
    Column('added_at', DateTime(timezone=True), server_default=func.now()),
    
    # Composite indexes for performance
    Index('idx_project_video_order', 'project_id', 'sequence_order'),
    Index('idx_video_project_added', 'video_id', 'added_at'),
    Index('idx_project_video_sequence', 'project_id', 'sequence_order', 'video_id'),  # For ordered playlist queries
)

class Project(Base):
    """
    REFACTORED: Lightweight project model focused on playlist functionality
    per PRD requirements - no longer contains camera-specific metadata
    """
    __tablename__ = "projects"

    # Core playlist identity
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    description = Column(Text)
    
    # Playlist management metadata
    status = Column(String, default="Active", index=True)  # 'Active', 'Completed', 'Draft'
    owner_id = Column(String(36), nullable=True, default="anonymous", index=True)
    
    # Cached playlist statistics (updated via triggers or application logic)
    video_count = Column(Integer, default=0, index=True)
    total_duration = Column(Float, nullable=True)  # Sum of all video durations
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Many-to-many relationship with videos via junction table
    videos = relationship("Video", secondary=project_videos, back_populates="projects")
    
    # Dependent relationships (these remain one-to-many for session management)
    test_sessions = relationship("TestSession", back_populates="project", cascade="all, delete-orphan")
    annotation_sessions = relationship("AnnotationSession", back_populates="project", cascade="all, delete-orphan")
    
    # Composite indexes for playlist operations
    __table_args__ = (
        Index('idx_project_status_created', 'status', 'created_at'),
        Index('idx_project_owner_status', 'owner_id', 'status'),
        Index('idx_project_video_count', 'video_count', 'status'),
        Index('idx_project_duration_count', 'total_duration', 'video_count'),  # For duration-based filtering
    )

class Video(Base):
    """
    ENHANCED: Video model now contains camera-specific metadata 
    moved from Project model for proper data normalization
    """
    __tablename__ = "videos"

    # Core video identity
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False, unique=True)  # Ensure unique file paths
    
    # MOVED FROM PROJECT: Camera hardware specifications
    camera_model = Column(String, nullable=True, index=True)           # e.g., "Sony IMX678"
    camera_view = Column(String, nullable=True, index=True)            # 'Front-facing VRU', 'Rear-facing VRU', 'In-Cab Driver Behavior'
    lens_type = Column(String, nullable=True)                          # e.g., "Wide-angle", "Telephoto"
    camera_resolution = Column(String, nullable=True)                  # Camera's native resolution
    camera_frame_rate = Column(Integer, nullable=True)                 # Camera's capture frame rate
    signal_type = Column(String, nullable=True, index=True)            # 'GPIO', 'Network Packet', 'Serial'
    
    # Video file technical metadata
    file_size = Column(Integer, index=True)
    duration = Column(Float, index=True)  # in seconds
    fps = Column(Float)  # Actual video fps (may differ from camera_frame_rate due to encoding)
    video_resolution = Column(String)  # Actual video resolution (may differ from camera due to processing)
    codec = Column(String)  # Video codec information
    bitrate = Column(Integer)  # Video bitrate
    
    # Processing and validation status
    status = Column(String, default="uploaded", index=True)  # 'uploaded', 'processing', 'validated', 'error'
    processing_status = Column(String, default="pending", index=True)  # Ground truth processing status
    ground_truth_generated = Column(Boolean, default=False, index=True)
    validation_status = Column(String, default="pending", index=True)  # 'pending', 'validated', 'rejected'
    
    # Quality and metadata
    quality_score = Column(Float)  # Video quality assessment
    scene_type = Column(String, index=True)  # 'urban', 'highway', 'parking', 'mixed'
    weather_conditions = Column(String)  # 'clear', 'rain', 'snow', 'fog'
    lighting_conditions = Column(String)  # 'daylight', 'dusk', 'night', 'artificial'
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Many-to-many relationship with projects
    projects = relationship("Project", secondary=project_videos, back_populates="videos")
    
    # One-to-many relationships (unchanged)
    ground_truth_objects = relationship("GroundTruthObject", back_populates="video", cascade="all, delete-orphan")
    annotations = relationship("Annotation", back_populates="video", cascade="all, delete-orphan")
    annotation_sessions = relationship("AnnotationSession", back_populates="video", cascade="all, delete-orphan")

    # Enhanced composite indexes for performance-critical queries
    __table_args__ = (
        # Camera metadata queries
        Index('idx_video_camera_model_view', 'camera_model', 'camera_view'),
        Index('idx_video_camera_specs', 'camera_model', 'camera_resolution', 'camera_frame_rate'),
        Index('idx_video_signal_type', 'signal_type', 'status'),
        
        # Technical metadata queries
        Index('idx_video_duration_fps', 'duration', 'fps'),
        Index('idx_video_resolution_codec', 'video_resolution', 'codec'),
        Index('idx_video_file_size', 'file_size', 'duration'),
        
        # Status and validation queries
        Index('idx_video_status_validation', 'status', 'validation_status'),
        Index('idx_video_ground_truth_status', 'ground_truth_generated', 'processing_status'),
        Index('idx_video_validation_created', 'validation_status', 'created_at'),
        
        # Scene and conditions queries
        Index('idx_video_scene_conditions', 'scene_type', 'weather_conditions', 'lighting_conditions'),
        Index('idx_video_quality_scene', 'quality_score', 'scene_type'),
        
        # Performance queries
        Index('idx_video_camera_duration', 'camera_model', 'duration'),  # For test suite planning
        Index('idx_video_validated_specs', 'validation_status', 'camera_model', 'camera_view'),  # For playlist creation
    )

class TestSession(Base):
    """
    UPDATED: TestSession now references Project for playlist-based testing
    but gets camera specs from individual videos during execution
    """
    __tablename__ = "test_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    
    # Project reference for playlist-based testing
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Current video being tested (can change during session)
    current_video_id = Column(String(36), ForeignKey("videos.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Test configuration
    tolerance_ms = Column(Integer, default=100)
    latency_threshold_ms = Column(Integer, default=100, index=True)
    
    # Session state
    status = Column(String, default="created", index=True)  # 'created', 'running', 'paused', 'completed', 'error'
    session_type = Column(String, default="user_created", index=True)
    playlist_position = Column(Integer, default=0)  # Current position in project playlist
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), index=True)
    completed_at = Column(DateTime(timezone=True), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    video_start_timestamp = Column(Float, nullable=True, index=True)  # Session video start time reference

    # Relationships
    project = relationship("Project", back_populates="test_sessions")
    current_video = relationship("Video", foreign_keys=[current_video_id])
    detection_events = relationship("DetectionEvent", back_populates="test_session", cascade="all, delete-orphan")
    results = relationship("TestResult", back_populates="test_session", cascade="all, delete-orphan")
    detection_comparisons = relationship("DetectionComparison", back_populates="test_session", cascade="all, delete-orphan")

    # Composite indexes for session management
    __table_args__ = (
        Index('idx_testsession_project_status', 'project_id', 'status'),
        Index('idx_testsession_project_created', 'project_id', 'created_at'),
        Index('idx_testsession_current_video', 'current_video_id', 'status'),
        Index('idx_testsession_playlist_position', 'project_id', 'playlist_position'),
        Index('idx_testsession_type_status_created', 'session_type', 'status', 'created_at'),
    )

# Import other models that remain unchanged or have minor updates
class GroundTruthObject(Base):
    """Ground truth objects - relationships updated for new Video model"""
    __tablename__ = "ground_truth_objects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    tracking_id = Column(String, nullable=True, index=True)
    frame_number = Column(Integer, nullable=True, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    class_label = Column(String, nullable=False, index=True)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    bounding_box = Column(JSON)  # Deprecated - keeping for backward compatibility
    confidence = Column(Float, index=True)
    validated = Column(Boolean, default=False, index=True)
    difficult = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="ground_truth_objects")

    __table_args__ = (
        Index('idx_gt_video_timestamp', 'video_id', 'timestamp'),
        Index('idx_gt_video_class', 'video_id', 'class_label'),
        Index('idx_gt_timestamp_class', 'timestamp', 'class_label'),
        Index('idx_gt_video_frame', 'video_id', 'frame_number'),
        Index('idx_gt_video_confidence', 'video_id', 'confidence'),
        Index('idx_gt_validated_class', 'validated', 'class_label'),
        Index('idx_gt_spatial_bounds', 'x', 'y', 'width', 'height'),
        Index('idx_gt_video_validated_timestamp', 'video_id', 'validated', 'timestamp'),
        Index('idx_gt_video_tracking_id', 'video_id', 'tracking_id'),
        Index('idx_gt_tracking_timestamp', 'tracking_id', 'timestamp'),
    )

class DetectionEvent(Base):
    """Detection events - updated to work with new Video-centric architecture"""
    __tablename__ = "detection_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=True, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    validation_result = Column(String, index=True)
    ground_truth_match_id = Column(String(36), ForeignKey("ground_truth_objects.id", ondelete="SET NULL"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # LabJack timing fields
    latency_ms = Column(Float, nullable=True, index=True)
    labjack_timestamp = Column(Float, nullable=True, index=True)
    video_start_time = Column(Float, nullable=True, index=True)
    labjack_voltage = Column(Float, nullable=True)
    latency_threshold_ms = Column(Float, nullable=True)
    latency_result = Column(String, nullable=True, index=True)
    voltage_level = Column(Float, nullable=True)
    detection_channel = Column(String, nullable=True)
    
    # Legacy AI fields (kept for compatibility)
    confidence = Column(Float, index=True)
    class_label = Column(String, index=True)
    detection_id = Column(String(36), nullable=True, index=True)
    frame_number = Column(Integer, nullable=True, index=True)
    vru_type = Column(String, nullable=True, index=True)
    
    # Bounding box coordinates
    bounding_box_x = Column(Float, nullable=True)
    bounding_box_y = Column(Float, nullable=True)
    bounding_box_width = Column(Float, nullable=True)
    bounding_box_height = Column(Float, nullable=True)
    
    # Visual evidence paths
    screenshot_path = Column(String, nullable=True)
    screenshot_zoom_path = Column(String, nullable=True)
    
    # Processing metadata
    processing_time_ms = Column(Float, nullable=True)
    model_version = Column(String, nullable=True)

    # Relationships
    test_session = relationship("TestSession", back_populates="detection_events")
    video = relationship("Video")
    ground_truth_match = relationship("GroundTruthObject", foreign_keys=[ground_truth_match_id])

    __table_args__ = (
        Index('idx_detection_session_timestamp', 'test_session_id', 'timestamp'),
        Index('idx_detection_session_validation', 'test_session_id', 'validation_result'),
        Index('idx_detection_video_timestamp', 'video_id', 'timestamp'),
        Index('idx_detection_video_validation', 'video_id', 'validation_result'),
        Index('idx_detection_latency_validation', 'latency_ms', 'validation_result'),
        Index('idx_detection_labjack_timestamp', 'labjack_timestamp'),
        Index('idx_detection_session_latency', 'test_session_id', 'latency_ms'),
        Index('idx_detection_video_start_time', 'video_start_time'),
        Index('idx_detection_session_labjack_validation', 'test_session_id', 'validation_result', 'latency_ms'),
    )

class Annotation(Base):
    """Ground Truth Annotations - relationships updated for new Video model"""
    __tablename__ = "annotations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    detection_id = Column(String(36), nullable=True, index=True)
    frame_number = Column(Integer, nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    end_timestamp = Column(Float, nullable=True)
    vru_type = Column(String, nullable=False, index=True)
    bounding_box = Column(JSON, nullable=False)
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
    
    __table_args__ = (
        Index('idx_annotation_video_frame', 'video_id', 'frame_number'),
        Index('idx_annotation_video_timestamp', 'video_id', 'timestamp'),
        Index('idx_annotation_video_validated', 'video_id', 'validated'),
        Index('idx_annotation_detection_id', 'detection_id'),
        Index('idx_annotation_vru_validated', 'vru_type', 'validated'),
        Index('idx_annotation_video_vru_frame', 'video_id', 'vru_type', 'frame_number'),
        Index('idx_annotation_annotator_validated', 'annotator', 'validated'),
        Index('idx_annotation_temporal_range', 'timestamp', 'end_timestamp'),
        Index('idx_annotation_video_annotator_created', 'video_id', 'annotator', 'created_at'),
        Index('idx_annotation_vru_timestamp_validated', 'vru_type', 'timestamp', 'validated'),
        Index('idx_annotation_difficulty_analysis', 'difficult', 'occluded', 'truncated'),
        Index('idx_annotation_video_temporal_coverage', 'video_id', 'timestamp', 'end_timestamp'),
    )

class AnnotationSession(Base):
    """Annotation sessions - updated for new Project/Video relationships"""
    __tablename__ = "annotation_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    annotator_id = Column(String(36), nullable=True, index=True)
    status = Column(String, default="active", index=True)
    total_detections = Column(Integer, default=0)
    validated_detections = Column(Integer, default=0)
    current_frame = Column(Integer, default=0)
    total_frames = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    video = relationship("Video", back_populates="annotation_sessions")
    project = relationship("Project", back_populates="annotation_sessions")

# Additional models remain largely unchanged...
class TestResult(Base):
    """Test results model - unchanged functionality"""
    __tablename__ = "test_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # LabJack timing metrics
    pass_rate = Column(Float, index=True)
    avg_latency_ms = Column(Float, index=True)
    max_latency_ms = Column(Float, index=True)
    min_latency_ms = Column(Float, index=True)
    median_latency_ms = Column(Float, index=True)
    std_dev_latency_ms = Column(Float, index=True)
    total_detections = Column(Integer, index=True)
    passed_detections = Column(Integer, index=True)
    failed_detections = Column(Integer, index=True)
    threshold_ms = Column(Integer, index=True)
    latency_distribution = Column(JSON)
    
    validation_type = Column(String(50), default="latency_based", index=True)
    test_duration_seconds = Column(Float)
    detection_rate_hz = Column(Float)
    
    # Legacy AI metrics (compatibility)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    true_positives = Column(Integer)
    false_positives = Column(Integer)
    false_negatives = Column(Integer, default=0)
    statistical_analysis = Column(JSON)
    confidence_intervals = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    test_session = relationship("TestSession", back_populates="results")
    
    __table_args__ = (
        Index('idx_testresult_session_pass_rate', 'test_session_id', 'pass_rate'),
        Index('idx_testresult_avg_latency', 'avg_latency_ms'),
        Index('idx_testresult_max_latency', 'max_latency_ms'),
        Index('idx_testresult_total_detections', 'total_detections'),
        Index('idx_testresult_session_created', 'test_session_id', 'created_at'),
        Index('idx_testresult_latency_range', 'min_latency_ms', 'max_latency_ms'),
        Index('idx_testresult_pass_fail_counts', 'passed_detections', 'failed_detections'),
    )

class DetectionComparison(Base):
    """Detection comparison model - unchanged functionality"""
    __tablename__ = "detection_comparisons"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    ground_truth_id = Column(String(36), ForeignKey("annotations.id", ondelete="SET NULL"))
    detection_event_id = Column(String(36), ForeignKey("detection_events.id", ondelete="SET NULL"))
    match_type = Column(String, nullable=False, index=True)
    iou_score = Column(Float)
    distance_error = Column(Float)
    temporal_offset = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    test_session = relationship("TestSession", back_populates="detection_comparisons")
    ground_truth = relationship("Annotation")
    detection_event = relationship("DetectionEvent")
    
    __table_args__ = (
        Index('idx_comparison_session_match', 'test_session_id', 'match_type'),
        Index('idx_comparison_iou_temporal', 'iou_score', 'temporal_offset'),
        Index('idx_comparison_session_ground_truth', 'test_session_id', 'ground_truth_id'),
        Index('idx_comparison_session_detection', 'test_session_id', 'detection_event_id'),
        Index('idx_comparison_match_iou', 'match_type', 'iou_score'),
        Index('idx_comparison_temporal_distance', 'temporal_offset', 'distance_error'),
    )

# Auth models remain unchanged
class AuthUser(Base):
    """User authentication model - unchanged"""
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
    
    __table_args__ = (
        Index('idx_auth_user_email_active', 'email', 'is_active'),
        Index('idx_auth_user_username_active', 'username', 'is_active'),
        Index('idx_auth_user_active_verified', 'is_active', 'is_verified'),
        Index('idx_auth_user_superuser_active', 'is_superuser', 'is_active'),
        Index('idx_auth_user_created_active', 'created_at', 'is_active'),
        Index('idx_auth_user_last_login', 'last_login'),
    )
    
    def verify_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.hashed_password)
    
    @classmethod
    def get_password_hash(cls, password: str) -> str:
        return pwd_context.hash(password)
    
    def set_password(self, password: str) -> None:
        self.hashed_password = self.get_password_hash(password)

class UserSession(Base):
    """User session model - unchanged"""
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
    
    user = relationship("AuthUser")
    
    __table_args__ = (
        Index('idx_session_user_active', 'user_id', 'is_active'),
        Index('idx_session_token_active', 'session_token', 'is_active'),
        Index('idx_session_expires_active', 'expires_at', 'is_active'),
        Index('idx_session_user_activity', 'user_id', 'last_activity'),
        Index('idx_session_ip_activity', 'ip_address', 'last_activity'),
        Index('idx_session_cleanup', 'expires_at', 'is_active'),
    )

class AuditLog(Base):
    """Audit log model - unchanged"""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, default="anonymous", index=True)
    event_type = Column(String, nullable=False, index=True)
    event_data = Column(JSON)
    ip_address = Column(String, index=True)
    user_agent = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index('idx_audit_user_event', 'user_id', 'event_type'),
        Index('idx_audit_created_event', 'created_at', 'event_type'),
        Index('idx_audit_ip_event_time', 'ip_address', 'event_type', 'created_at'),
        Index('idx_audit_user_time_range', 'user_id', 'created_at'),
        Index('idx_audit_event_data_analysis', 'event_type', 'created_at'),
    )