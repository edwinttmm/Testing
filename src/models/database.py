"""
SQLAlchemy database models for VRU Detection System
Based on the PostgreSQL schema specification
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, 
    BigInteger, JSON, ForeignKey, CheckConstraint, Index,
    func, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import expression

Base = declarative_base()


class ProjectStatus(str, Enum):
    """Project status enumeration"""
    ACTIVE = "Active"
    COMPLETED = "Completed"
    DRAFT = "Draft"
    ARCHIVED = "Archived"


class CameraView(str, Enum):
    """Camera view enumeration"""
    FRONT_FACING_VRU = "Front-facing VRU"
    REAR_FACING_VRU = "Rear-facing VRU"
    IN_CAB_DRIVER = "In-Cab Driver Behavior"


class SignalType(str, Enum):
    """Signal type enumeration"""
    GPIO = "GPIO"
    NETWORK_PACKET = "Network Packet"
    SERIAL = "Serial"
    CAN_BUS = "CAN Bus"


class VideoStatus(str, Enum):
    """Video processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"


class TestSessionStatus(str, Enum):
    """Test session status"""
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ValidationResult(str, Enum):
    """Detection validation result"""
    TP = "TP"  # True Positive
    FP = "FP"  # False Positive
    FN = "FN"  # False Negative
    TN = "TN"  # True Negative


class VRUClass(str, Enum):
    """VRU detection classes"""
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"
    MOTORCYCLIST = "motorcyclist"
    WHEELCHAIR_USER = "wheelchair_user"
    SCOOTER_RIDER = "scooter_rider"
    CHILD_WITH_STROLLER = "child_with_stroller"


class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    ENGINEER = "engineer"
    ANALYST = "analyst"
    USER = "user"


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


class User(Base, TimestampMixin):
    """User accounts table"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    projects = relationship("Project", back_populates="owner")
    audit_logs = relationship("AuditLog", back_populates="user")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            role.in_([r.value for r in UserRole]),
            name="check_user_role"
        ),
        Index("idx_users_email", email),
        Index("idx_users_role", role),
        Index("idx_users_active", is_active),
    )


class Project(Base, TimestampMixin):
    """Projects table for organizing VRU detection tests"""
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    camera_model = Column(String(100), nullable=False)
    camera_view = Column(String(50), nullable=False)
    lens_type = Column(String(50), nullable=True)
    resolution = Column(String(20), nullable=True)
    frame_rate = Column(Integer, nullable=True)
    signal_type = Column(String(20), nullable=False)
    status = Column(String(20), default=ProjectStatus.ACTIVE, nullable=False, index=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Relationships
    owner = relationship("User", back_populates="projects")
    videos = relationship("Video", back_populates="project", cascade="all, delete-orphan")
    test_sessions = relationship("TestSession", back_populates="project", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            camera_view.in_([cv.value for cv in CameraView]),
            name="check_camera_view"
        ),
        CheckConstraint(
            signal_type.in_([st.value for st in SignalType]),
            name="check_signal_type"
        ),
        CheckConstraint(
            status.in_([ps.value for ps in ProjectStatus]),
            name="check_project_status"
        ),
        Index("idx_projects_name", name),
        Index("idx_projects_status", status),
        Index("idx_projects_owner", owner_id),
        Index("idx_projects_created", created_at),
        Index("idx_projects_camera_view", camera_view),
    )


class Video(Base, TimestampMixin):
    """Videos table for storing uploaded video files"""
    __tablename__ = "videos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False, index=True)
    file_path = Column(String(512), nullable=False)
    file_size = Column(BigInteger, nullable=True)
    duration = Column(Float, nullable=True)  # seconds
    fps = Column(Float, nullable=True)
    resolution = Column(String(20), nullable=True)
    status = Column(String(20), default=VideoStatus.UPLOADED, nullable=False, index=True)
    ground_truth_generated = Column(Boolean, default=False, nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationships
    project = relationship("Project", back_populates="videos")
    ground_truth_objects = relationship("GroundTruthObject", back_populates="video", cascade="all, delete-orphan")
    test_sessions = relationship("TestSession", back_populates="video", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            status.in_([vs.value for vs in VideoStatus]),
            name="check_video_status"
        ),
        CheckConstraint(file_size > 0, name="check_positive_file_size"),
        CheckConstraint(duration > 0, name="check_positive_duration"),
        CheckConstraint(fps > 0, name="check_positive_fps"),
        Index("idx_videos_filename", filename),
        Index("idx_videos_status", status),
        Index("idx_videos_ground_truth", ground_truth_generated),
        Index("idx_videos_project", project_id),
        Index("idx_videos_created", created_at),
        Index("idx_videos_project_status", project_id, status),
        Index("idx_videos_project_created", project_id, created_at),
    )


class GroundTruthObject(Base):
    """Ground truth objects for validation"""
    __tablename__ = "ground_truth_objects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)  # seconds from video start
    class_label = Column(String(50), nullable=False, index=True)
    bounding_box = Column(JSONB, nullable=False)  # {"x": 0, "y": 0, "width": 100, "height": 100}
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    # Relationships
    video = relationship("Video", back_populates="ground_truth_objects")
    matched_detections = relationship("DetectionEvent", back_populates="ground_truth_match")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            class_label.in_([vc.value for vc in VRUClass]),
            name="check_vru_class"
        ),
        CheckConstraint(
            confidence >= 0.0,
            name="check_confidence_min"
        ),
        CheckConstraint(
            confidence <= 1.0,
            name="check_confidence_max"
        ),
        CheckConstraint(timestamp >= 0, name="check_positive_timestamp"),
        Index("idx_gt_video", video_id),
        Index("idx_gt_timestamp", timestamp),
        Index("idx_gt_class", class_label),
        Index("idx_gt_confidence", confidence),
        Index("idx_gt_video_timestamp", video_id, timestamp),
        Index("idx_gt_video_class", video_id, class_label),
    )
    
    @validates('bounding_box')
    def validate_bounding_box(self, key, bounding_box):
        """Validate bounding box format"""
        required_keys = {'x', 'y', 'width', 'height'}
        if not isinstance(bounding_box, dict) or not required_keys.issubset(bounding_box.keys()):
            raise ValueError("Bounding box must contain x, y, width, height")
        
        for coord in required_keys:
            if not isinstance(bounding_box[coord], (int, float)) or bounding_box[coord] < 0:
                raise ValueError(f"Bounding box {coord} must be a non-negative number")
        
        return bounding_box


class TestSession(Base, TimestampMixin):
    """Test sessions for running detection validation"""
    __tablename__ = "test_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    tolerance_ms = Column(Integer, default=100, nullable=False)
    status = Column(String(20), default=TestSessionStatus.CREATED, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    project = relationship("Project", back_populates="test_sessions")
    video = relationship("Video", back_populates="test_sessions")
    detection_events = relationship("DetectionEvent", back_populates="test_session", cascade="all, delete-orphan")
    signal_events = relationship("SignalEvent", back_populates="test_session", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResults", back_populates="test_session", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(tolerance_ms > 0, name="check_positive_tolerance"),
        CheckConstraint(
            status.in_([tss.value for tss in TestSessionStatus]),
            name="check_session_status"
        ),
        Index("idx_sessions_name", name),
        Index("idx_sessions_project", project_id),
        Index("idx_sessions_video", video_id),
        Index("idx_sessions_status", status),
        Index("idx_sessions_started", started_at),
        Index("idx_sessions_project_status", project_id, status),
        Index("idx_sessions_project_created", project_id, created_at),
    )


class DetectionEvent(Base):
    """Individual detection events during test sessions"""
    __tablename__ = "detection_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_session_id = Column(UUID(as_uuid=True), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)  # seconds from video start
    confidence = Column(Float, nullable=True)
    class_label = Column(String(50), nullable=False, index=True)
    validation_result = Column(String(10), nullable=True, index=True)
    ground_truth_match_id = Column(UUID(as_uuid=True), ForeignKey("ground_truth_objects.id", ondelete="SET NULL"), nullable=True, index=True)
    bounding_box = Column(JSONB, nullable=True)
    screenshot_path = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    # Relationships
    test_session = relationship("TestSession", back_populates="detection_events")
    ground_truth_match = relationship("GroundTruthObject", back_populates="matched_detections")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            confidence >= 0.0,
            name="check_detection_confidence_min"
        ),
        CheckConstraint(
            confidence <= 1.0,
            name="check_detection_confidence_max"
        ),
        CheckConstraint(
            validation_result.in_([vr.value for vr in ValidationResult]),
            name="check_validation_result"
        ),
        CheckConstraint(timestamp >= 0, name="check_detection_positive_timestamp"),
        Index("idx_detection_session", test_session_id),
        Index("idx_detection_timestamp", timestamp),
        Index("idx_detection_confidence", confidence),
        Index("idx_detection_class", class_label),
        Index("idx_detection_validation", validation_result),
        Index("idx_detection_gt_match", ground_truth_match_id),
        Index("idx_detection_session_timestamp", test_session_id, timestamp),
        Index("idx_detection_session_validation", test_session_id, validation_result),
        Index("idx_detection_timestamp_confidence", timestamp, confidence),
    )


class SignalEvent(Base):
    """Signal events from external systems"""
    __tablename__ = "signal_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_session_id = Column(UUID(as_uuid=True), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)  # high-precision timestamp
    signal_type = Column(String(20), nullable=False, index=True)
    signal_data = Column(JSONB, nullable=False)  # signal-specific data structure
    source_identifier = Column(String(100), nullable=True, index=True)  # GPIO pin, IP address, etc.
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    # Relationships
    test_session = relationship("TestSession", back_populates="signal_events")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            signal_type.in_([st.value for st in SignalType]),
            name="check_signal_type_valid"
        ),
        CheckConstraint(timestamp >= 0, name="check_signal_positive_timestamp"),
        Index("idx_signal_session", test_session_id),
        Index("idx_signal_timestamp", timestamp),
        Index("idx_signal_type", signal_type),
        Index("idx_signal_source", source_identifier),
        Index("idx_signal_session_timestamp", test_session_id, timestamp),
    )


class ValidationResults(Base):
    """Aggregated validation results for test sessions"""
    __tablename__ = "validation_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_session_id = Column(UUID(as_uuid=True), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    true_positives = Column(Integer, default=0, nullable=False)
    false_positives = Column(Integer, default=0, nullable=False)
    false_negatives = Column(Integer, default=0, nullable=False)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    avg_latency_ms = Column(Float, nullable=True)
    detailed_metrics = Column(JSONB, nullable=True)  # Additional metrics and analysis
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    # Relationships
    test_session = relationship("TestSession", back_populates="validation_results")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(true_positives >= 0, name="check_positive_tp"),
        CheckConstraint(false_positives >= 0, name="check_positive_fp"),
        CheckConstraint(false_negatives >= 0, name="check_positive_fn"),
        CheckConstraint(precision >= 0.0, name="check_precision_min"),
        CheckConstraint(precision <= 1.0, name="check_precision_max"),
        CheckConstraint(recall >= 0.0, name="check_recall_min"),
        CheckConstraint(recall <= 1.0, name="check_recall_max"),
        CheckConstraint(f1_score >= 0.0, name="check_f1_min"),
        CheckConstraint(f1_score <= 1.0, name="check_f1_max"),
        CheckConstraint(accuracy >= 0.0, name="check_accuracy_min"),
        CheckConstraint(accuracy <= 1.0, name="check_accuracy_max"),
        Index("idx_results_session", test_session_id),
        Index("idx_results_precision", precision),
        Index("idx_results_recall", recall),
        Index("idx_results_f1", f1_score),
        Index("idx_results_latency", avg_latency_ms),
    )


class AuditLog(Base):
    """Audit logs for tracking user actions"""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    event_data = Column(JSONB, nullable=True)
    ip_address = Column(INET, nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    # Constraints
    __table_args__ = (
        Index("idx_audit_user", user_id),
        Index("idx_audit_event", event_type),
        Index("idx_audit_created", created_at),
        Index("idx_audit_ip", ip_address),
        Index("idx_audit_user_event", user_id, event_type),
        Index("idx_audit_created_event", created_at, event_type),
    )


class SystemConfiguration(Base, TimestampMixin):
    """System configuration settings"""
    __tablename__ = "system_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_key = Column(String(255), unique=True, nullable=False, index=True)
    config_value = Column(JSONB, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True, index=True)
    
    # Constraints
    __table_args__ = (
        Index("idx_config_key", config_key),
        Index("idx_config_category", category),
    )