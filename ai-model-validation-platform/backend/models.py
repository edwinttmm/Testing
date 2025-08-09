from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # projects = relationship("Project", back_populates="owner")  # Removed for no-auth mode

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text)
    camera_model = Column(String, nullable=False)
    camera_view = Column(String, nullable=False)  # 'Front-facing VRU', 'Rear-facing VRU', 'In-Cab Driver Behavior'
    lens_type = Column(String)
    resolution = Column(String)
    frame_rate = Column(Integer)
    signal_type = Column(String, nullable=False)  # 'GPIO', 'Network Packet', 'Serial'
    status = Column(String, default="Active")  # 'Active', 'Completed', 'Draft'
    owner_id = Column(String(36), nullable=True, default="anonymous")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # owner = relationship("User", back_populates="projects")  # Removed for no-auth mode
    videos = relationship("Video", back_populates="project")
    test_sessions = relationship("TestSession", back_populates="project")

class Video(Base):
    __tablename__ = "videos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    duration = Column(Float)  # in seconds
    fps = Column(Float)
    resolution = Column(String)
    status = Column(String, default="uploaded")  # 'uploaded', 'processing', 'completed', 'failed'
    ground_truth_generated = Column(Boolean, default=False)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    project = relationship("Project", back_populates="videos")
    ground_truth_objects = relationship("GroundTruthObject", back_populates="video")

class GroundTruthObject(Base):
    __tablename__ = "ground_truth_objects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=False)
    timestamp = Column(Float, nullable=False)  # timestamp in video (seconds)
    class_label = Column(String, nullable=False)  # 'pedestrian', 'cyclist', 'distracted_driver', etc.
    bounding_box = Column(JSON)  # {"x": 0, "y": 0, "width": 100, "height": 100}
    confidence = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="ground_truth_objects")

class TestSession(Base):
    __tablename__ = "test_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=False)
    tolerance_ms = Column(Integer, default=100)  # tolerance for timing comparison
    status = Column(String, default="created")  # 'created', 'running', 'completed', 'failed'
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    project = relationship("Project", back_populates="test_sessions")
    detection_events = relationship("DetectionEvent", back_populates="test_session")

class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id"), nullable=False)
    timestamp = Column(Float, nullable=False)  # timestamp when detection occurred
    confidence = Column(Float)
    class_label = Column(String)  # detected class from camera
    validation_result = Column(String)  # 'TP', 'FP', 'FN'
    ground_truth_match_id = Column(String(36), ForeignKey("ground_truth_objects.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    test_session = relationship("TestSession", back_populates="detection_events")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    event_type = Column(String, nullable=False)  # 'user_login', 'project_create', 'video_upload', etc.
    event_data = Column(JSON)  # additional event details
    ip_address = Column(String)
    user_agent = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())