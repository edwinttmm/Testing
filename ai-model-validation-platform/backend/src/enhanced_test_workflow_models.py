"""
Enhanced database models for automated test workflow system
"""

from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, ForeignKey, JSON, Index, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from enum import Enum

from database import Base

class WorkflowStatus(Enum):
    """Workflow execution status"""
    INITIALIZING = "initializing"
    LOADING_VIDEOS = "loading_videos"
    PROCESSING_VIDEO = "processing_video"
    RUNNING_DETECTION = "running_detection"
    COMPARING_RESULTS = "comparing_results"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class VideoProcessingStatus(Enum):
    """Individual video processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    DETECTION = "detection"
    COMPARISON = "comparison"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class EnhancedTestWorkflow(Base):
    """Enhanced test workflow execution tracking"""
    __tablename__ = "enhanced_test_workflows"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    
    # Workflow configuration
    config = Column(JSON, nullable=False)  # WorkflowConfiguration as JSON
    
    # Status tracking
    status = Column(SQLEnum(WorkflowStatus), default=WorkflowStatus.INITIALIZING, index=True)
    start_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    end_time = Column(DateTime(timezone=True), index=True)
    duration_seconds = Column(Float)
    
    # Progress tracking
    total_videos = Column(Integer, default=0)
    completed_videos = Column(Integer, default=0)
    failed_videos = Column(Integer, default=0)
    current_video_id = Column(String(36), ForeignKey("videos.id", ondelete="SET NULL"))
    current_video_progress = Column(Float, default=0.0)
    overall_progress = Column(Float, default=0.0)
    
    # Results and reporting
    final_results = Column(JSON)  # Final comprehensive results
    error_log = Column(JSON)  # List of errors encountered
    
    # Metadata
    created_by = Column(String(36), default="system", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    project = relationship("Project")
    current_video = relationship("Video")
    video_executions = relationship("VideoWorkflowExecution", back_populates="workflow", cascade="all, delete-orphan")
    test_sessions = relationship("TestSession", back_populates="enhanced_workflow", cascade="all, delete-orphan")
    
    # Enhanced composite indexes
    __table_args__ = (
        Index('idx_workflow_project_status', 'project_id', 'status'),
        Index('idx_workflow_status_created', 'status', 'created_at'),
        Index('idx_workflow_project_progress', 'project_id', 'overall_progress'),
        Index('idx_workflow_duration_analysis', 'duration_seconds', 'completed_videos'),
        Index('idx_workflow_error_tracking', 'failed_videos', 'status'),
        Index('idx_workflow_active_monitoring', 'status', 'current_video_id', 'overall_progress'),
    )

class VideoWorkflowExecution(Base):
    """Individual video execution within workflow"""
    __tablename__ = "video_workflow_executions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String(36), ForeignKey("enhanced_test_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Execution tracking
    execution_order = Column(Integer, nullable=False, index=True)
    status = Column(SQLEnum(VideoProcessingStatus), default=VideoProcessingStatus.PENDING, index=True)
    start_time = Column(DateTime(timezone=True), index=True)
    end_time = Column(DateTime(timezone=True), index=True)
    processing_duration = Column(Float)  # seconds
    
    # Detection and comparison results
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="SET NULL"))
    total_detections = Column(Integer, default=0)
    true_positives = Column(Integer, default=0)
    false_positives = Column(Integer, default=0)
    false_negatives = Column(Integer, default=0)
    
    # Performance metrics
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    accuracy = Column(Float)
    
    # Error handling
    error_message = Column(Text)
    error_details = Column(JSON)  # Detailed error information
    retry_count = Column(Integer, default=0)
    
    # Progress tracking
    current_step = Column(String, index=True)  # Current processing step
    progress_percentage = Column(Float, default=0.0)
    
    # Individual results storage
    individual_report_path = Column(String)  # Path to generated report file
    detection_results = Column(JSON)  # Raw detection results
    comparison_results = Column(JSON)  # Ground truth comparison results
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    workflow = relationship("EnhancedTestWorkflow", back_populates="video_executions")
    video = relationship("Video")
    test_session = relationship("TestSession")
    
    # Enhanced composite indexes
    __table_args__ = (
        Index('idx_video_exec_workflow_order', 'workflow_id', 'execution_order'),
        Index('idx_video_exec_workflow_status', 'workflow_id', 'status'),
        Index('idx_video_exec_video_status', 'video_id', 'status'),
        Index('idx_video_exec_performance', 'precision', 'recall', 'f1_score'),
        Index('idx_video_exec_duration_analysis', 'processing_duration', 'status'),
        Index('idx_video_exec_error_tracking', 'status', 'error_message'),
        Index('idx_video_exec_retry_analysis', 'retry_count', 'status'),
        Index('idx_video_exec_progress_monitoring', 'workflow_id', 'progress_percentage', 'current_step'),
        Index('idx_video_exec_detection_metrics', 'total_detections', 'true_positives', 'false_positives'),
        Index('idx_video_exec_temporal_analysis', 'start_time', 'end_time', 'processing_duration'),
    )

class WorkflowProgressLog(Base):
    """Detailed progress logging for workflows"""
    __tablename__ = "workflow_progress_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String(36), ForeignKey("enhanced_test_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    video_execution_id = Column(String(36), ForeignKey("video_workflow_executions.id", ondelete="CASCADE"))
    
    # Progress details
    log_type = Column(String, nullable=False, index=True)  # 'workflow', 'video', 'step', 'error', 'milestone'
    step_name = Column(String, index=True)
    progress_percentage = Column(Float)
    message = Column(Text)
    
    # Contextual data
    metadata = Column(JSON)  # Additional context data
    duration_ms = Column(Integer)  # Time taken for this step
    
    # Performance tracking
    memory_usage_mb = Column(Float)
    cpu_usage_percent = Column(Float)
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    workflow = relationship("EnhancedTestWorkflow")
    video_execution = relationship("VideoWorkflowExecution")
    
    # Enhanced composite indexes
    __table_args__ = (
        Index('idx_progress_workflow_type', 'workflow_id', 'log_type'),
        Index('idx_progress_workflow_timestamp', 'workflow_id', 'timestamp'),
        Index('idx_progress_video_timestamp', 'video_execution_id', 'timestamp'),
        Index('idx_progress_step_analysis', 'step_name', 'progress_percentage'),
        Index('idx_progress_performance_tracking', 'memory_usage_mb', 'cpu_usage_percent'),
        Index('idx_progress_type_timestamp', 'log_type', 'timestamp'),
        Index('idx_progress_duration_analysis', 'duration_ms', 'step_name'),
    )

class WorkflowReport(Base):
    """Generated workflow reports"""
    __tablename__ = "workflow_reports"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String(36), ForeignKey("enhanced_test_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Report metadata
    report_type = Column(String, nullable=False, index=True)  # 'individual_video', 'final_comprehensive', 'intermediate'
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="SET NULL"))  # For individual video reports
    
    # Report content
    report_data = Column(JSON, nullable=False)  # Complete report data
    file_path = Column(String)  # Path to generated file
    file_format = Column(String, default='json', index=True)  # 'json', 'pdf', 'html', 'csv'
    
    # Report statistics
    total_metrics = Column(JSON)  # Aggregated metrics
    performance_summary = Column(JSON)  # Performance analysis
    error_summary = Column(JSON)  # Error analysis
    
    # Generation metadata
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    generated_by = Column(String(36), default="system")
    generation_duration_ms = Column(Integer)
    
    # Relationships
    workflow = relationship("EnhancedTestWorkflow")
    video = relationship("Video")
    
    # Enhanced composite indexes
    __table_args__ = (
        Index('idx_report_workflow_type', 'workflow_id', 'report_type'),
        Index('idx_report_video_type', 'video_id', 'report_type'),
        Index('idx_report_generated_format', 'generated_at', 'file_format'),
        Index('idx_report_workflow_generated', 'workflow_id', 'generated_at'),
    )

# Add relationship back to existing TestSession model (this would be added to models.py)
"""
Add to TestSession model in models.py:
enhanced_workflow_id = Column(String(36), ForeignKey("enhanced_test_workflows.id", ondelete="SET NULL"))
enhanced_workflow = relationship("EnhancedTestWorkflow", back_populates="test_sessions")
"""