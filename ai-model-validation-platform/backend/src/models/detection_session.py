"""
Detection Session Models

Simple database models for storing detection session data
"""

from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from database import Base

class DetectionSession(Base):
    """
    Simple detection session model for background detection storage
    """
    __tablename__ = "detection_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, unique=True, nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Session timing
    start_time = Column(Float, nullable=False, index=True)  # Unix timestamp
    end_time = Column(Float, nullable=True, index=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Detection parameters
    tolerance_ms = Column(Integer, default=100)
    status = Column(String, default="active", index=True)  # active, completed, failed
    
    # Results summary
    total_detections = Column(Integer, default=0)
    matched_detections = Column(Integer, nullable=True)
    accuracy_percentage = Column(Float, nullable=True)
    
    # Metadata
    session_metadata = Column(JSON, nullable=True)
    storage_path = Column(String, nullable=True)  # Path to detailed session data file
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    project = relationship("Project", foreign_keys=[project_id])
    video = relationship("Video", foreign_keys=[video_id])
    detection_events = relationship("StoredDetectionEvent", back_populates="session", cascade="all, delete-orphan")

class StoredDetectionEvent(Base):
    """
    Individual detection events from background detection
    """
    __tablename__ = "stored_detection_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("detection_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Detection data
    detection_id = Column(String, nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)  # Unix timestamp
    pin_state = Column(Boolean, nullable=False)
    
    # Session correlation
    session_start_offset = Column(Float, nullable=True)  # Seconds from session start
    detection_sequence = Column(Integer, nullable=True)  # Order within session
    
    # Video correlation (populated during analysis)
    video_offset_seconds = Column(Float, nullable=True)
    matched_video_events = Column(JSON, nullable=True)
    match_count = Column(Integer, default=0)
    within_tolerance = Column(Boolean, nullable=True)
    
    # Latency validation fields
    latency_ms = Column(Float, nullable=True, index=True)  # LabJack to video start latency
    validation_result = Column(String(10), nullable=True, index=True)  # "Pass" or "Fail"
    threshold_ms = Column(Integer, nullable=True)  # Threshold used for validation
    video_start_time = Column(Float, nullable=True)  # Video start timestamp for reference
    
    # Metadata
    session_metadata = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    session = relationship("DetectionSession", back_populates="detection_events")

class VideoEvent(Base):
    """
    Video events for correlation with detection events
    """
    __tablename__ = "video_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Event timing
    timestamp = Column(Float, nullable=False, index=True)  # Video timeline position in seconds
    frame_number = Column(Integer, nullable=True, index=True)
    
    # Event details
    event_type = Column(String, nullable=False, index=True)  # VRU detection, ground truth, etc.
    class_label = Column(String, nullable=True, index=True)  # pedestrian, cyclist, etc.
    confidence = Column(Float, nullable=True)
    
    # Bounding box (if applicable)
    bbox_x = Column(Float, nullable=True)
    bbox_y = Column(Float, nullable=True) 
    bbox_width = Column(Float, nullable=True)
    bbox_height = Column(Float, nullable=True)
    
    # Correlation tracking
    matched_detection_events = Column(JSON, nullable=True)
    correlation_analysis = Column(JSON, nullable=True)
    
    # Metadata
    session_metadata = Column(JSON, nullable=True)
    source = Column(String, nullable=True)  # ground_truth, ml_detection, manual_annotation
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    video = relationship("Video", foreign_keys=[video_id])