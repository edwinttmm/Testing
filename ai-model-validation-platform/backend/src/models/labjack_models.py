"""
LabJack Detection Storage Models

This module defines the database models for independent LabJack hardware detection 
storage and temporal synchronization with video playback systems.

Key Features:
- Independent detection storage with high-precision timestamps
- Configurable detection windows for temporal matching
- Real-time vs recorded time comparison
- Detection event correlation and synchronization
- Hardware signal validation and integrity checking
"""

from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, ForeignKey, JSON, Index, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from enum import Enum as PyEnum
import uuid
from typing import Optional, Dict, Any, List

from database import Base


class DetectionSourceEnum(PyEnum):
    """Source types for detections"""
    LABJACK_HARDWARE = "labjack_hardware"
    VIDEO_PLAYBACK = "video_playback"
    SIMULATION = "simulation"
    EXTERNAL_TRIGGER = "external_trigger"


class DetectionStatusEnum(PyEnum):
    """Detection processing status"""
    PENDING = "pending"
    PROCESSED = "processed"
    MATCHED = "matched"
    UNMATCHED = "unmatched"
    EXPIRED = "expired"
    ERROR = "error"


class SynchronizationStatusEnum(PyEnum):
    """Synchronization status for detection pairs"""
    SYNCHRONIZED = "synchronized"
    OUT_OF_SYNC = "out_of_sync"
    WITHIN_TOLERANCE = "within_tolerance"
    REQUIRES_REVIEW = "requires_review"


class LabJackDetection(Base):
    """
    Independent LabJack hardware detection storage
    
    This model stores hardware detections with high-precision timestamps
    independently of video playback systems, allowing for later temporal analysis.
    """
    __tablename__ = "labjack_detections"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False, index=True)  # Links to test session
    device_id = Column(String, nullable=False, index=True)  # LabJack device identifier
    
    # Temporal information (high precision)
    hardware_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)  # Hardware-generated timestamp
    system_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)    # System receive timestamp
    monotonic_time = Column(Float, nullable=False)  # Monotonic time for precise intervals
    
    # Detection data
    signal_value = Column(Float, nullable=False)  # Raw signal value
    threshold_value = Column(Float, nullable=False)  # Detection threshold
    channel = Column(Integer, nullable=False, index=True)  # LabJack channel
    detection_confidence = Column(Float, default=1.0)  # Detection confidence score
    
    # Hardware context
    device_config = Column(JSON)  # Device configuration at detection time
    sampling_rate = Column(Float)  # Sampling rate in Hz
    signal_to_noise_ratio = Column(Float)  # Signal quality metric
    
    # Processing status
    status = Column(Enum(DetectionStatusEnum), default=DetectionStatusEnum.PENDING, index=True)
    source = Column(Enum(DetectionSourceEnum), default=DetectionSourceEnum.LABJACK_HARDWARE, index=True)
    
    # Temporal correlation
    correlation_window_ms = Column(Integer, default=100)  # Detection window in milliseconds
    matched_detection_id = Column(String(36), ForeignKey("video_detections.id"), nullable=True, index=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    metadata = Column(JSON)  # Additional detection metadata
    
    # Quality assurance
    is_valid = Column(Boolean, default=True, index=True)
    validation_errors = Column(JSON)  # Validation error details
    
    # Relationships
    matched_detection = relationship("VideoDetection", foreign_keys=[matched_detection_id])
    synchronization_events = relationship("DetectionSynchronization", back_populates="labjack_detection")
    
    # Performance indexes
    __table_args__ = (
        Index('idx_labjack_session_time', 'session_id', 'hardware_timestamp'),
        Index('idx_labjack_device_time', 'device_id', 'hardware_timestamp'),
        Index('idx_labjack_channel_time', 'channel', 'hardware_timestamp'),
        Index('idx_labjack_status_time', 'status', 'hardware_timestamp'),
        Index('idx_labjack_monotonic', 'monotonic_time'),
        Index('idx_labjack_correlation', 'session_id', 'status', 'hardware_timestamp'),
        Index('idx_labjack_matching', 'session_id', 'correlation_window_ms', 'hardware_timestamp'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert detection to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'device_id': self.device_id,
            'hardware_timestamp': self.hardware_timestamp.isoformat() if self.hardware_timestamp else None,
            'system_timestamp': self.system_timestamp.isoformat() if self.system_timestamp else None,
            'monotonic_time': self.monotonic_time,
            'signal_value': self.signal_value,
            'threshold_value': self.threshold_value,
            'channel': self.channel,
            'detection_confidence': self.detection_confidence,
            'status': self.status.value if self.status else None,
            'source': self.source.value if self.source else None,
            'correlation_window_ms': self.correlation_window_ms,
            'is_valid': self.is_valid,
            'metadata': self.metadata
        }


class VideoDetection(Base):
    """
    Video playback detection events for temporal comparison
    
    Stores detection events from video playback timeline for comparison
    with hardware detections.
    """
    __tablename__ = "video_detections"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=False, index=True)
    
    # Video timeline information
    video_timestamp = Column(Float, nullable=False, index=True)  # Video time in seconds
    playback_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)  # Real playback time
    frame_number = Column(Integer, nullable=True, index=True)  # Video frame number
    
    # Detection information
    detection_type = Column(String, nullable=False)  # Type of video detection
    confidence_score = Column(Float, default=0.0)  # Detection confidence
    bounding_box = Column(JSON)  # Bounding box coordinates if applicable
    
    # Processing context
    playback_speed = Column(Float, default=1.0)  # Video playback speed
    processing_delay_ms = Column(Float, default=0.0)  # Processing delay
    
    # Status and correlation
    status = Column(Enum(DetectionStatusEnum), default=DetectionStatusEnum.PENDING, index=True)
    source = Column(Enum(DetectionSourceEnum), default=DetectionSourceEnum.VIDEO_PLAYBACK, index=True)
    correlation_window_ms = Column(Integer, default=100)
    matched_labjack_id = Column(String(36), ForeignKey("labjack_detections.id"), nullable=True, index=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    metadata = Column(JSON)
    
    # Quality assurance
    is_valid = Column(Boolean, default=True, index=True)
    validation_errors = Column(JSON)
    
    # Relationships
    video = relationship("Video")
    matched_labjack = relationship("LabJackDetection", foreign_keys=[matched_labjack_id])
    synchronization_events = relationship("DetectionSynchronization", back_populates="video_detection")
    
    # Performance indexes
    __table_args__ = (
        Index('idx_video_session_time', 'session_id', 'video_timestamp'),
        Index('idx_video_playback_time', 'session_id', 'playback_timestamp'),
        Index('idx_video_frame', 'video_id', 'frame_number'),
        Index('idx_video_correlation', 'session_id', 'status', 'video_timestamp'),
        Index('idx_video_matching', 'session_id', 'correlation_window_ms', 'video_timestamp'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert detection to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'video_id': self.video_id,
            'video_timestamp': self.video_timestamp,
            'playback_timestamp': self.playback_timestamp.isoformat() if self.playback_timestamp else None,
            'frame_number': self.frame_number,
            'detection_type': self.detection_type,
            'confidence_score': self.confidence_score,
            'bounding_box': self.bounding_box,
            'playback_speed': self.playback_speed,
            'processing_delay_ms': self.processing_delay_ms,
            'status': self.status.value if self.status else None,
            'source': self.source.value if self.source else None,
            'is_valid': self.is_valid,
            'metadata': self.metadata
        }


class DetectionSynchronization(Base):
    """
    Detection synchronization and comparison results
    
    Tracks the temporal relationship between LabJack hardware detections
    and video playback detections, including timing analysis.
    """
    __tablename__ = "detection_synchronizations"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False, index=True)
    
    # Detection references
    labjack_detection_id = Column(String(36), ForeignKey("labjack_detections.id"), nullable=False, index=True)
    video_detection_id = Column(String(36), ForeignKey("video_detections.id"), nullable=False, index=True)
    
    # Temporal analysis
    time_difference_ms = Column(Float, nullable=False, index=True)  # Time difference in milliseconds
    synchronization_status = Column(Enum(SynchronizationStatusEnum), nullable=False, index=True)
    tolerance_window_ms = Column(Integer, default=100)  # Acceptable synchronization tolerance
    
    # Analysis metrics
    confidence_score = Column(Float, default=0.0)  # Synchronization confidence
    quality_score = Column(Float, default=0.0)  # Overall synchronization quality
    drift_rate = Column(Float, default=0.0)  # Timing drift rate if applicable
    
    # Context information
    analysis_method = Column(String, default="timestamp_correlation")
    correlation_algorithm = Column(String)  # Algorithm used for correlation
    processing_parameters = Column(JSON)  # Parameters used in analysis
    
    # Validation
    is_valid_match = Column(Boolean, default=True, index=True)
    validation_flags = Column(JSON)  # Validation warnings or flags
    manual_review_required = Column(Boolean, default=False, index=True)
    
    # Metadata
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    analyzed_by = Column(String, default="system")  # System or user ID
    review_notes = Column(Text)
    metadata = Column(JSON)
    
    # Relationships
    labjack_detection = relationship("LabJackDetection", back_populates="synchronization_events")
    video_detection = relationship("VideoDetection", back_populates="synchronization_events")
    
    # Performance indexes
    __table_args__ = (
        Index('idx_sync_session_status', 'session_id', 'synchronization_status'),
        Index('idx_sync_time_diff', 'time_difference_ms'),
        Index('idx_sync_quality', 'quality_score', 'confidence_score'),
        Index('idx_sync_review', 'manual_review_required', 'analyzed_at'),
        Index('idx_sync_validation', 'is_valid_match', 'session_id'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert synchronization to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'labjack_detection_id': self.labjack_detection_id,
            'video_detection_id': self.video_detection_id,
            'time_difference_ms': self.time_difference_ms,
            'synchronization_status': self.synchronization_status.value if self.synchronization_status else None,
            'tolerance_window_ms': self.tolerance_window_ms,
            'confidence_score': self.confidence_score,
            'quality_score': self.quality_score,
            'drift_rate': self.drift_rate,
            'analysis_method': self.analysis_method,
            'is_valid_match': self.is_valid_match,
            'manual_review_required': self.manual_review_required,
            'analyzed_at': self.analyzed_at.isoformat() if self.analyzed_at else None,
            'metadata': self.metadata
        }


class DetectionConfiguration(Base):
    """
    Detection window and synchronization configuration
    
    Stores configuration parameters for detection windows, synchronization
    tolerances, and analysis parameters per session or globally.
    """
    __tablename__ = "detection_configurations"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    session_id = Column(String(36), nullable=True, index=True)  # Null for global configs
    
    # Detection window configuration
    labjack_window_ms = Column(Integer, default=100)  # LabJack detection window
    video_window_ms = Column(Integer, default=100)  # Video detection window
    synchronization_tolerance_ms = Column(Integer, default=50)  # Sync tolerance
    
    # Threshold configuration
    signal_threshold = Column(Float, default=3.0)  # Signal detection threshold
    confidence_threshold = Column(Float, default=0.7)  # Minimum confidence for matching
    quality_threshold = Column(Float, default=0.8)  # Minimum quality score
    
    # Temporal analysis settings
    max_drift_rate = Column(Float, default=0.1)  # Maximum acceptable drift rate
    correlation_method = Column(String, default="pearson")  # Correlation algorithm
    interpolation_method = Column(String, default="linear")  # Time interpolation method
    
    # Processing parameters
    batch_size = Column(Integer, default=1000)  # Processing batch size
    parallel_processing = Column(Boolean, default=True)  # Enable parallel processing
    cache_results = Column(Boolean, default=True)  # Cache analysis results
    
    # Validation settings
    auto_validation = Column(Boolean, default=True)  # Enable automatic validation
    manual_review_threshold = Column(Float, default=0.5)  # Threshold for manual review
    outlier_detection = Column(Boolean, default=True)  # Enable outlier detection
    
    # Status and metadata
    is_active = Column(Boolean, default=True, index=True)
    is_default = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String, default="system")
    metadata = Column(JSON)
    
    # Performance indexes
    __table_args__ = (
        Index('idx_config_session_active', 'session_id', 'is_active'),
        Index('idx_config_name_active', 'name', 'is_active'),
        Index('idx_config_default', 'is_default', 'is_active'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'session_id': self.session_id,
            'labjack_window_ms': self.labjack_window_ms,
            'video_window_ms': self.video_window_ms,
            'synchronization_tolerance_ms': self.synchronization_tolerance_ms,
            'signal_threshold': self.signal_threshold,
            'confidence_threshold': self.confidence_threshold,
            'quality_threshold': self.quality_threshold,
            'correlation_method': self.correlation_method,
            'is_active': self.is_active,
            'is_default': self.is_default,
            'metadata': self.metadata
        }


class TemporalAnalysisResult(Base):
    """
    Comprehensive temporal analysis results for detection sessions
    
    Stores aggregated analysis results for detection sessions including
    timing statistics, synchronization quality, and performance metrics.
    """
    __tablename__ = "temporal_analysis_results"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False, index=True)
    analysis_name = Column(String, nullable=False, index=True)
    
    # Time range analyzed
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_seconds = Column(Float, nullable=False)
    
    # Detection statistics
    total_labjack_detections = Column(Integer, default=0)
    total_video_detections = Column(Integer, default=0)
    matched_detections = Column(Integer, default=0)
    unmatched_labjack = Column(Integer, default=0)
    unmatched_video = Column(Integer, default=0)
    
    # Timing statistics
    mean_time_difference_ms = Column(Float, default=0.0)
    median_time_difference_ms = Column(Float, default=0.0)
    std_time_difference_ms = Column(Float, default=0.0)
    min_time_difference_ms = Column(Float, default=0.0)
    max_time_difference_ms = Column(Float, default=0.0)
    
    # Quality metrics
    synchronization_accuracy = Column(Float, default=0.0)  # Percentage of accurate syncs
    mean_confidence_score = Column(Float, default=0.0)
    mean_quality_score = Column(Float, default=0.0)
    
    # Performance metrics
    detection_rate_hz = Column(Float, default=0.0)  # Detections per second
    processing_time_seconds = Column(Float, default=0.0)
    throughput_detections_per_second = Column(Float, default=0.0)
    
    # Drift and stability analysis
    timing_drift_ms_per_second = Column(Float, default=0.0)
    stability_score = Column(Float, default=1.0)  # 0-1 stability metric
    jitter_ms = Column(Float, default=0.0)  # Timing jitter
    
    # Analysis metadata
    configuration_used = Column(JSON)  # Configuration parameters used
    algorithm_version = Column(String, default="1.0")
    analysis_parameters = Column(JSON)
    warnings = Column(JSON)  # Analysis warnings
    
    # Status
    analysis_status = Column(String, default="completed", index=True)
    is_valid = Column(Boolean, default=True, index=True)
    requires_review = Column(Boolean, default=False, index=True)
    
    # Timestamps
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    analyzed_by = Column(String, default="system")
    metadata = Column(JSON)
    
    # Performance indexes
    __table_args__ = (
        Index('idx_analysis_session_time', 'session_id', 'analyzed_at'),
        Index('idx_analysis_status_time', 'analysis_status', 'analyzed_at'),
        Index('idx_analysis_quality', 'synchronization_accuracy', 'mean_quality_score'),
        Index('idx_analysis_performance', 'detection_rate_hz', 'throughput_detections_per_second'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis result to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'analysis_name': self.analysis_name,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'total_labjack_detections': self.total_labjack_detections,
            'total_video_detections': self.total_video_detections,
            'matched_detections': self.matched_detections,
            'synchronization_accuracy': self.synchronization_accuracy,
            'mean_time_difference_ms': self.mean_time_difference_ms,
            'timing_drift_ms_per_second': self.timing_drift_ms_per_second,
            'stability_score': self.stability_score,
            'analysis_status': self.analysis_status,
            'is_valid': self.is_valid,
            'requires_review': self.requires_review,
            'analyzed_at': self.analyzed_at.isoformat() if self.analyzed_at else None,
            'metadata': self.metadata
        }