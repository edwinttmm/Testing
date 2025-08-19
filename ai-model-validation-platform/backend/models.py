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