from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from database import Base

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