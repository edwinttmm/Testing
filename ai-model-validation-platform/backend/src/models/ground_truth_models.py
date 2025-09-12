"""
Ground Truth Management Models
SPARC Implementation - Database models for ground truth validation workflow
"""

from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, ForeignKey, JSON, Index, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import uuid
from enum import Enum as PyEnum

class ValidationStatus(PyEnum):
    """Ground truth validation status enumeration"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_REVIEW = "in_review"
    REQUIRES_REVISION = "requires_revision"

class GenerationMethod(PyEnum):
    """Ground truth generation method enumeration"""
    MANUAL = "manual"
    AUTOMATED_ML = "automated_ml"
    SEMI_AUTOMATIC = "semi_automatic"
    IMPORTED = "imported"

class QualityLevel(PyEnum):
    """Ground truth quality level enumeration"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"

class GroundTruthValidationWorkflow(Base):
    """
    Enhanced ground truth validation workflow model
    Manages validation states, approval processes, and quality control
    """
    __tablename__ = "ground_truth_validation_workflows"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ground_truth_id = Column(String(36), ForeignKey("ground_truth_objects.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Validation workflow fields
    validation_status = Column(Enum(ValidationStatus), default=ValidationStatus.PENDING, nullable=False, index=True)
    generation_method = Column(Enum(GenerationMethod), nullable=False, index=True)
    quality_level = Column(Enum(QualityLevel), default=QualityLevel.UNCERTAIN, index=True)
    
    # Reviewer information
    assigned_reviewer = Column(String(36), index=True)  # User ID of assigned reviewer
    reviewed_by = Column(String(36), index=True)  # User ID who completed review
    review_notes = Column(Text)
    review_timestamp = Column(DateTime(timezone=True), index=True)
    
    # Quality metrics
    confidence_score = Column(Float, index=True)  # Confidence in the ground truth
    agreement_score = Column(Float, index=True)   # Inter-annotator agreement if applicable
    complexity_score = Column(Float, index=True)  # Object detection complexity
    
    # Revision tracking
    revision_count = Column(Integer, default=0)
    original_ground_truth_id = Column(String(36), index=True)  # Reference to original if this is a revision
    
    # Workflow metadata
    workflow_metadata = Column(JSON)  # Additional workflow metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), index=True)
    
    # Relationships
    ground_truth = relationship("GroundTruthObject")
    video = relationship("Video")
    validation_history = relationship("ValidationHistory", back_populates="workflow", cascade="all, delete-orphan")
    
    # Enhanced composite indexes for workflow queries
    __table_args__ = (
        Index('idx_validation_status_method', 'validation_status', 'generation_method'),
        Index('idx_validation_video_status', 'video_id', 'validation_status'),
        Index('idx_validation_reviewer_status', 'assigned_reviewer', 'validation_status'),
        Index('idx_validation_quality_confidence', 'quality_level', 'confidence_score'),
        Index('idx_validation_created_status', 'created_at', 'validation_status'),
        Index('idx_validation_video_method_status', 'video_id', 'generation_method', 'validation_status'),
    )

class ValidationHistory(Base):
    """
    Tracks validation history and state changes
    Provides audit trail for ground truth validation workflow
    """
    __tablename__ = "validation_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String(36), ForeignKey("ground_truth_validation_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # State change information
    previous_status = Column(Enum(ValidationStatus), index=True)
    new_status = Column(Enum(ValidationStatus), index=True)
    changed_by = Column(String(36), index=True)  # User ID who made the change
    change_reason = Column(Text)
    
    # Change metadata
    change_data = Column(JSON)  # Additional change data
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    workflow = relationship("GroundTruthValidationWorkflow", back_populates="validation_history")
    
    # Indexes for history tracking
    __table_args__ = (
        Index('idx_history_workflow_timestamp', 'workflow_id', 'timestamp'),
        Index('idx_history_user_timestamp', 'changed_by', 'timestamp'),
        Index('idx_history_status_change', 'previous_status', 'new_status'),
    )

class GroundTruthBatch(Base):
    """
    Batch processing tracking for ground truth generation
    Manages bulk operations and batch processing workflows
    """
    __tablename__ = "ground_truth_batches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Batch information
    batch_name = Column(String, nullable=False, index=True)
    description = Column(Text)
    processing_method = Column(Enum(GenerationMethod), nullable=False, index=True)
    
    # Processing status
    total_videos = Column(Integer, default=0)
    processed_videos = Column(Integer, default=0)
    successful_videos = Column(Integer, default=0)
    failed_videos = Column(Integer, default=0)
    
    # Batch metadata
    batch_config = Column(JSON)  # Configuration used for batch processing
    error_log = Column(JSON)     # Errors encountered during processing
    performance_metrics = Column(JSON)  # Processing performance data
    
    # Status tracking
    status = Column(String, default="created", index=True)  # created, processing, completed, failed
    started_at = Column(DateTime(timezone=True), index=True)
    completed_at = Column(DateTime(timezone=True), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # User tracking
    created_by = Column(String(36), index=True)
    
    # Relationships
    batch_items = relationship("GroundTruthBatchItem", back_populates="batch", cascade="all, delete-orphan")
    
    # Indexes for batch management
    __table_args__ = (
        Index('idx_batch_status_created', 'status', 'created_at'),
        Index('idx_batch_method_status', 'processing_method', 'status'),
        Index('idx_batch_user_created', 'created_by', 'created_at'),
    )

class GroundTruthBatchItem(Base):
    """
    Individual items within a ground truth batch
    Tracks processing status of each video in a batch
    """
    __tablename__ = "ground_truth_batch_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id = Column(String(36), ForeignKey("ground_truth_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Item processing status
    status = Column(String, default="pending", index=True)  # pending, processing, completed, failed
    detections_generated = Column(Integer, default=0)
    processing_time_seconds = Column(Float)
    error_message = Column(Text)
    
    # Processing metadata
    processing_config = Column(JSON)
    processing_metrics = Column(JSON)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), index=True)
    completed_at = Column(DateTime(timezone=True), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    batch = relationship("GroundTruthBatch", back_populates="batch_items")
    video = relationship("Video")
    
    # Indexes for batch item tracking
    __table_args__ = (
        Index('idx_batch_item_batch_status', 'batch_id', 'status'),
        Index('idx_batch_item_video_batch', 'video_id', 'batch_id'),
        Index('idx_batch_item_status_time', 'status', 'processing_time_seconds'),
    )

class GroundTruthExport(Base):
    """
    Ground truth export tracking for ML training datasets
    Manages export operations and dataset generation
    """
    __tablename__ = "ground_truth_exports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Export information
    export_name = Column(String, nullable=False, index=True)
    description = Column(Text)
    format_type = Column(String, nullable=False, index=True)  # json, coco, yolo, pascal_voc
    
    # Export criteria
    video_filter = Column(JSON)      # Filter criteria for videos
    quality_filter = Column(JSON)    # Quality criteria for ground truth
    validation_filter = Column(JSON) # Validation status criteria
    
    # Export statistics
    total_videos = Column(Integer, default=0)
    total_objects = Column(Integer, default=0)
    class_distribution = Column(JSON)
    
    # File information
    file_path = Column(String)
    file_size_bytes = Column(Integer)
    checksum = Column(String)
    
    # Status tracking
    status = Column(String, default="created", index=True)  # created, processing, completed, failed
    error_message = Column(Text)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), index=True)
    completed_at = Column(DateTime(timezone=True), index=True)
    expires_at = Column(DateTime(timezone=True), index=True)  # Export expiration
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # User tracking
    created_by = Column(String(36), index=True)
    
    # Indexes for export management
    __table_args__ = (
        Index('idx_export_status_created', 'status', 'created_at'),
        Index('idx_export_format_status', 'format_type', 'status'),
        Index('idx_export_user_created', 'created_by', 'created_at'),
        Index('idx_export_expires', 'expires_at'),
    )

class GroundTruthQualityMetrics(Base):
    """
    Quality metrics and analytics for ground truth objects
    Provides detailed quality assessment and statistics
    """
    __tablename__ = "ground_truth_quality_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ground_truth_id = Column(String(36), ForeignKey("ground_truth_objects.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Quality scores
    annotation_quality_score = Column(Float, index=True)   # 0.0 - 1.0 annotation quality
    detection_confidence = Column(Float, index=True)       # Model confidence if auto-generated
    spatial_accuracy = Column(Float, index=True)           # Bounding box accuracy
    temporal_consistency = Column(Float, index=True)       # Consistency across frames
    
    # Complexity metrics
    object_size_score = Column(Float, index=True)          # Size-based difficulty
    occlusion_level = Column(Float, index=True)            # Level of occlusion
    motion_complexity = Column(Float, index=True)          # Motion complexity
    background_complexity = Column(Float, index=True)      # Background complexity
    
    # Validation metrics
    inter_annotator_agreement = Column(Float, index=True)  # Agreement between annotators
    validation_confidence = Column(Float, index=True)      # Reviewer confidence
    revision_count = Column(Integer, default=0)            # Number of revisions
    
    # Additional metrics
    metrics_data = Column(JSON)  # Additional quality metrics
    
    # Timestamps
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), index=True)
    
    # Relationships
    ground_truth = relationship("GroundTruthObject")
    video = relationship("Video")
    
    # Indexes for quality analysis
    __table_args__ = (
        Index('idx_quality_video_annotation_score', 'video_id', 'annotation_quality_score'),
        Index('idx_quality_confidence_spatial', 'detection_confidence', 'spatial_accuracy'),
        Index('idx_quality_temporal_consistency', 'temporal_consistency'),
        Index('idx_quality_complexity_combined', 'object_size_score', 'occlusion_level', 'motion_complexity'),
        Index('idx_quality_agreement_validation', 'inter_annotator_agreement', 'validation_confidence'),
    )