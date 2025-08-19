from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from database import Base

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
    status = Column(String, default="uploaded", index=True)  # Index for status filtering
    processing_status = Column(String, default="pending", index=True)  # Ground truth processing status
    ground_truth_generated = Column(Boolean, default=False, index=True)  # Index for filtering
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    project = relationship("Project", back_populates="videos")
    ground_truth_objects = relationship("GroundTruthObject", back_populates="video", cascade="all, delete-orphan")
    annotations = relationship("Annotation", back_populates="video", cascade="all, delete-orphan")
    annotation_sessions = relationship("AnnotationSession", back_populates="video", cascade="all, delete-orphan")
    project_links = relationship("VideoProjectLink", back_populates="video", cascade="all, delete-orphan")

    # Composite index for common queries
    __table_args__ = (
        Index('idx_video_project_status', 'project_id', 'status'),
        Index('idx_video_project_created', 'project_id', 'created_at'),
    )

class GroundTruthObject(Base):
    __tablename__ = "ground_truth_objects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
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

    # Composite index for common queries
    __table_args__ = (
        Index('idx_gt_video_timestamp', 'video_id', 'timestamp'),
        Index('idx_gt_video_class', 'video_id', 'class_label'),
    )

class TestSession(Base):
    __tablename__ = "test_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)  # Index for search
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    tolerance_ms = Column(Integer, default=100)
    status = Column(String, default="created", index=True)  # Index for status filtering
    started_at = Column(DateTime(timezone=True), index=True)  # Index for time-based queries
    completed_at = Column(DateTime(timezone=True), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    project = relationship("Project", back_populates="test_sessions")
    detection_events = relationship("DetectionEvent", back_populates="test_session", cascade="all, delete-orphan")
    results = relationship("TestResult", back_populates="test_session", cascade="all, delete-orphan")
    detection_comparisons = relationship("DetectionComparison", back_populates="test_session", cascade="all, delete-orphan")

    # Composite index for common queries
    __table_args__ = (
        Index('idx_testsession_project_status', 'project_id', 'status'),
        Index('idx_testsession_project_created', 'project_id', 'created_at'),
    )

class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)  # Index for temporal queries
    confidence = Column(Float, index=True)  # Index for confidence-based filtering
    class_label = Column(String, index=True)  # Index for filtering by detection type
    validation_result = Column(String, index=True)  # Index for filtering by validation result ('TP', 'FP', 'FN')
    ground_truth_match_id = Column(String(36), ForeignKey("ground_truth_objects.id", ondelete="SET NULL"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    test_session = relationship("TestSession", back_populates="detection_events")

    # Composite index for performance-critical queries
    __table_args__ = (
        Index('idx_detection_session_timestamp', 'test_session_id', 'timestamp'),
        Index('idx_detection_session_validation', 'test_session_id', 'validation_result'),
        Index('idx_detection_timestamp_confidence', 'timestamp', 'confidence'),
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
    
    # Composite indexes for performance
    __table_args__ = (
        Index('idx_annotation_video_frame', 'video_id', 'frame_number'),
        Index('idx_annotation_video_timestamp', 'video_id', 'timestamp'),
        Index('idx_annotation_video_validated', 'video_id', 'validated'),
        Index('idx_annotation_detection_id', 'detection_id'),
        Index('idx_annotation_vru_validated', 'vru_type', 'validated'),
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
    
    # Composite indexes
    __table_args__ = (
        Index('idx_video_project_unique', 'video_id', 'project_id', unique=True),
    )

class TestResult(Base):
    """Enhanced test results with detailed metrics"""
    __tablename__ = "test_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    true_positives = Column(Integer)
    false_positives = Column(Integer)
    false_negatives = Column(Integer)
    statistical_analysis = Column(JSON)
    confidence_intervals = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    test_session = relationship("TestSession", back_populates="results")

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
    
    # Relationships
    test_session = relationship("TestSession", back_populates="detection_comparisons")
    ground_truth = relationship("Annotation")
    detection_event = relationship("DetectionEvent")
    
    # Composite indexes
    __table_args__ = (
        Index('idx_comparison_session_match', 'test_session_id', 'match_type'),
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

    # Composite index for audit queries
    __table_args__ = (
        Index('idx_audit_user_event', 'user_id', 'event_type'),
        Index('idx_audit_created_event', 'created_at', 'event_type'),
    )