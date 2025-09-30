"""
Smart Compression Database Schema for Raw LabJack Data
======================================================

This module implements a highly efficient compression system for raw LabJack data
at 1000Hz sampling rates, designed to achieve 2-3x storage vs. 50x increase target.

Key Features:
- Run-length encoding for constant voltage periods  
- Transition-only storage with microsecond precision
- Smart compression algorithms
- Hybrid query compatibility with existing detection_events table
- Backward compatibility preservation
- High-frequency query optimization

Architecture:
- Raw samples: 1000Hz → Compressed transitions: ~10-50Hz  
- Storage reduction: 20-100x compression ratio
- Query performance: Optimized indexes for temporal analysis
"""

from sqlalchemy import (
    Column, String, DateTime, Float, Integer, BigInteger, Boolean, Text, 
    ForeignKey, JSON, Index, Enum, DECIMAL, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional, Dict, Any, List, Tuple
import uuid
import time

from database import Base


class CompressionQuality(PyEnum):
    """Compression quality levels"""
    LOSSLESS = "lossless"           # No data loss, maximum precision
    HIGH_PRECISION = "high_precision"  # < 0.1% data loss, high precision
    BALANCED = "balanced"           # < 1% data loss, good compression
    HIGH_COMPRESSION = "high_compression"  # < 5% data loss, maximum compression


class VoltageTransitionType(PyEnum):
    """Types of voltage transitions detected"""
    RISING_EDGE = "rising_edge"     # Low to high transition
    FALLING_EDGE = "falling_edge"   # High to low transition
    SPIKE = "spike"                 # Brief high-low-high or low-high-low
    DRIFT = "drift"                 # Gradual voltage change
    NOISE = "noise"                 # Random noise variation


class CompressionStatus(PyEnum):
    """Compression processing status"""
    PENDING = "pending"             # Awaiting compression
    COMPRESSING = "compressing"     # Currently being compressed
    COMPRESSED = "compressed"       # Successfully compressed
    ERROR = "error"                 # Compression failed
    REPROCESSING = "reprocessing"   # Being recompressed with different settings


# ===== CORE COMPRESSED DATA TABLES =====

class LabJackRawSession(Base):
    """
    Raw LabJack data session with compression metadata
    
    Manages high-frequency sampling sessions with smart compression
    targeting 2-3x storage overhead vs uncompressed (instead of 50x).
    """
    __tablename__ = "labjack_raw_sessions"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), 
                       nullable=False, index=True)
    device_id = Column(String(100), nullable=False, index=True)
    
    # Timing boundaries (microsecond precision)
    start_timestamp_us = Column(BigInteger, nullable=False, index=True)  # Unix microseconds
    end_timestamp_us = Column(BigInteger, nullable=True, index=True)
    duration_us = Column(BigInteger, nullable=True)  # Session duration in microseconds
    
    # Sampling configuration
    sample_rate_hz = Column(Integer, nullable=False)  # Target: 1000 Hz
    actual_sample_rate_hz = Column(Float, nullable=True)  # Measured rate
    channels = Column(JSON, nullable=False)  # ["AIN0", "AIN1", etc.]
    voltage_range_v = Column(Float, default=10.0)  # ±10V typical
    
    # Compression configuration
    compression_quality = Column(Enum(CompressionQuality), default=CompressionQuality.BALANCED)
    transition_threshold_mv = Column(Float, default=10.0)  # 10mV threshold for transitions
    run_length_min_ms = Column(Float, default=5.0)  # Minimum 5ms for run-length encoding
    noise_filter_enabled = Column(Boolean, default=True)
    
    # Performance metrics
    total_raw_samples = Column(BigInteger, default=0)
    total_transitions = Column(Integer, default=0)
    compression_ratio = Column(Float, nullable=True)  # Actual compression achieved
    storage_bytes = Column(BigInteger, nullable=True)
    estimated_uncompressed_bytes = Column(BigInteger, nullable=True)
    
    # Processing status
    compression_status = Column(Enum(CompressionStatus), default=CompressionStatus.PENDING, index=True)
    compression_started_at = Column(DateTime(timezone=True), nullable=True)
    compression_completed_at = Column(DateTime(timezone=True), nullable=True)
    compression_error = Column(Text, nullable=True)
    
    # Quality metrics
    data_quality_score = Column(Float, nullable=True)  # 0.0-1.0 quality score
    signal_to_noise_ratio = Column(Float, nullable=True)
    timing_accuracy_ns = Column(Float, nullable=True)  # Nanosecond timing accuracy
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    test_session = relationship("TestSession", foreign_keys=[session_id])
    voltage_runs = relationship("VoltageRunPeriod", back_populates="session", 
                               cascade="all, delete-orphan")
    transitions = relationship("VoltageTransition", back_populates="session", 
                              cascade="all, delete-orphan")
    
    # Performance indexes for high-frequency queries
    __table_args__ = (
        Index('idx_raw_session_device_time', 'device_id', 'start_timestamp_us'),
        Index('idx_raw_session_status_time', 'compression_status', 'start_timestamp_us'),
        Index('idx_raw_session_timing_range', 'start_timestamp_us', 'end_timestamp_us'),
        Index('idx_raw_session_sample_rate', 'sample_rate_hz', 'actual_sample_rate_hz'),
        Index('idx_raw_session_compression_quality', 'compression_quality', 'compression_ratio'),
        CheckConstraint('sample_rate_hz > 0', name='check_positive_sample_rate'),
        CheckConstraint('compression_ratio >= 0', name='check_positive_compression_ratio'),
        CheckConstraint('start_timestamp_us > 0', name='check_positive_start_time'),
    )
    
    def calculate_compression_stats(self) -> Dict[str, Any]:
        """Calculate comprehensive compression statistics"""
        if not self.estimated_uncompressed_bytes or self.estimated_uncompressed_bytes == 0:
            return {}
        
        return {
            'compression_ratio': self.compression_ratio or 0.0,
            'storage_efficiency': (self.storage_bytes / self.estimated_uncompressed_bytes) * 100,
            'samples_per_transition': (self.total_raw_samples / max(1, self.total_transitions)),
            'data_reduction_factor': (self.estimated_uncompressed_bytes / max(1, self.storage_bytes)),
            'bytes_per_sample': self.storage_bytes / max(1, self.total_raw_samples)
        }


class VoltageRunPeriod(Base):
    """
    Run-length encoded constant voltage periods
    
    Stores periods where voltage remains constant (within threshold)
    for efficient compression of steady-state data.
    """
    __tablename__ = "voltage_run_periods"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("labjack_raw_sessions.id", ondelete="CASCADE"), 
                       nullable=False, index=True)
    channel = Column(String(20), nullable=False, index=True)  # AIN0, AIN1, etc.
    
    # Time boundaries (microsecond precision)
    start_timestamp_us = Column(BigInteger, nullable=False, index=True)
    end_timestamp_us = Column(BigInteger, nullable=False, index=True)
    duration_us = Column(BigInteger, nullable=False)
    
    # Voltage data (high precision for accurate reconstruction)
    steady_voltage_v = Column(DECIMAL(precision=8, scale=6), nullable=False)  # μV precision
    voltage_min_v = Column(DECIMAL(precision=8, scale=6), nullable=True)  # Min during period
    voltage_max_v = Column(DECIMAL(precision=8, scale=6), nullable=True)  # Max during period
    voltage_std_dev_v = Column(Float, nullable=True)  # Standard deviation
    
    # Compression metadata
    sample_count = Column(Integer, nullable=False)  # Original samples compressed
    compression_method = Column(String(50), default="run_length_encoding")
    quality_loss_percent = Column(Float, default=0.0)  # Estimated data loss %
    
    # Sequence information
    sequence_number = Column(Integer, nullable=False)  # Order within session
    previous_run_id = Column(String(36), ForeignKey("voltage_run_periods.id"), nullable=True)
    next_run_id = Column(String(36), ForeignKey("voltage_run_periods.id"), nullable=True)
    
    # Quality indicators
    is_noise_filtered = Column(Boolean, default=False)
    confidence_score = Column(Float, default=1.0)  # 0.0-1.0 confidence in compression
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    session = relationship("LabJackRawSession", back_populates="voltage_runs")
    previous_run = relationship("VoltageRunPeriod", remote_side=[id], foreign_keys=[previous_run_id])
    next_run = relationship("VoltageRunPeriod", remote_side=[id], foreign_keys=[next_run_id])
    
    # Optimized indexes for temporal queries
    __table_args__ = (
        Index('idx_voltage_run_session_channel_time', 'session_id', 'channel', 'start_timestamp_us'),
        Index('idx_voltage_run_timing_range', 'start_timestamp_us', 'end_timestamp_us'),
        Index('idx_voltage_run_duration', 'duration_us', 'sample_count'),
        Index('idx_voltage_run_voltage_range', 'steady_voltage_v', 'voltage_min_v', 'voltage_max_v'),
        Index('idx_voltage_run_sequence', 'session_id', 'sequence_number'),
        CheckConstraint('end_timestamp_us > start_timestamp_us', name='check_valid_time_range'),
        CheckConstraint('duration_us > 0', name='check_positive_duration'),
        CheckConstraint('sample_count > 0', name='check_positive_samples'),
        CheckConstraint('quality_loss_percent >= 0 AND quality_loss_percent <= 100', 
                       name='check_quality_loss_range'),
    )


class VoltageTransition(Base):
    """
    Voltage transitions with microsecond timing precision
    
    Stores voltage changes/edges with precise timing for accurate
    signal reconstruction and detection event correlation.
    """
    __tablename__ = "voltage_transitions"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("labjack_raw_sessions.id", ondelete="CASCADE"), 
                       nullable=False, index=True)
    channel = Column(String(20), nullable=False, index=True)
    
    # Precise timing (microsecond resolution)
    timestamp_us = Column(BigInteger, nullable=False, index=True)
    monotonic_timestamp_ns = Column(String(20), nullable=True)  # Nanosecond monotonic time
    
    # Voltage transition data
    voltage_before_v = Column(DECIMAL(precision=8, scale=6), nullable=False)
    voltage_after_v = Column(DECIMAL(precision=8, scale=6), nullable=False)
    voltage_delta_v = Column(DECIMAL(precision=8, scale=6), nullable=False)
    
    # Transition characteristics
    transition_type = Column(Enum(VoltageTransitionType), nullable=False, index=True)
    transition_duration_us = Column(Integer, nullable=True)  # Rise/fall time
    slope_v_per_s = Column(Float, nullable=True)  # dV/dt
    
    # Detection correlation
    is_detection_event = Column(Boolean, default=False, index=True)
    detection_confidence = Column(Float, nullable=True)  # 0.0-1.0
    threshold_crossed_v = Column(Float, nullable=True)  # Threshold voltage crossed
    
    # Signal quality
    signal_quality_score = Column(Float, default=1.0)
    noise_level_v = Column(Float, nullable=True)
    is_filtered = Column(Boolean, default=False)
    
    # Context information
    sequence_number = Column(Integer, nullable=False)  # Order within session
    samples_since_last_transition = Column(Integer, nullable=True)
    time_since_last_transition_us = Column(BigInteger, nullable=True)
    
    # Processing metadata
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    processing_latency_us = Column(Integer, nullable=True)
    compression_algorithm = Column(String(50), default="transition_detection")
    
    # Related run periods (for linking transitions to steady states)
    previous_run_id = Column(String(36), ForeignKey("voltage_run_periods.id"), nullable=True)
    next_run_id = Column(String(36), ForeignKey("voltage_run_periods.id"), nullable=True)
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    session = relationship("LabJackRawSession", back_populates="transitions")
    previous_run = relationship("VoltageRunPeriod", foreign_keys=[previous_run_id])
    next_run = relationship("VoltageRunPeriod", foreign_keys=[next_run_id])
    
    # High-performance indexes for detection queries
    __table_args__ = (
        Index('idx_voltage_transition_session_channel_time', 'session_id', 'channel', 'timestamp_us'),
        Index('idx_voltage_transition_detection', 'is_detection_event', 'detection_confidence'),
        Index('idx_voltage_transition_type_time', 'transition_type', 'timestamp_us'),
        Index('idx_voltage_transition_voltage_delta', 'voltage_delta_v', 'transition_type'),
        Index('idx_voltage_transition_sequence', 'session_id', 'sequence_number'),
        Index('idx_voltage_transition_threshold', 'threshold_crossed_v', 'is_detection_event'),
        Index('idx_voltage_transition_quality', 'signal_quality_score', 'noise_level_v'),
        CheckConstraint('voltage_delta_v = voltage_after_v - voltage_before_v', 
                       name='check_voltage_delta_calculation'),
        CheckConstraint('detection_confidence >= 0 AND detection_confidence <= 1', 
                       name='check_detection_confidence_range'),
        CheckConstraint('signal_quality_score >= 0 AND signal_quality_score <= 1', 
                       name='check_signal_quality_range'),
    )


# ===== COMPRESSION METADATA AND CONFIGURATION =====

class CompressionConfiguration(Base):
    """
    Compression algorithm configuration and tuning parameters
    
    Stores compression settings optimized for different use cases
    (real-time detection, archival storage, analysis, etc.)
    """
    __tablename__ = "compression_configurations"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    
    # Configuration scope
    is_default = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    use_case = Column(String(50), nullable=True)  # "real_time", "archival", "analysis"
    
    # Compression parameters
    quality_level = Column(Enum(CompressionQuality), default=CompressionQuality.BALANCED)
    transition_threshold_mv = Column(Float, default=10.0)
    run_length_min_samples = Column(Integer, default=5)
    noise_filter_cutoff_hz = Column(Float, nullable=True)
    
    # Performance targets
    target_compression_ratio = Column(Float, default=20.0)  # Target 20x compression
    max_quality_loss_percent = Column(Float, default=1.0)   # Max 1% quality loss
    max_processing_delay_ms = Column(Float, default=100.0)  # Max 100ms processing delay
    
    # Advanced settings
    algorithm_parameters = Column(JSON, nullable=True)
    preprocessing_steps = Column(JSON, nullable=True)
    postprocessing_steps = Column(JSON, nullable=True)
    
    # Performance tracking
    usage_count = Column(Integer, default=0)
    average_compression_ratio = Column(Float, nullable=True)
    average_quality_loss = Column(Float, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(100), default="system")
    
    # Performance indexes
    __table_args__ = (
        Index('idx_compression_config_active', 'is_active', 'is_default'),
        Index('idx_compression_config_quality', 'quality_level', 'target_compression_ratio'),
        Index('idx_compression_config_use_case', 'use_case', 'is_active'),
        CheckConstraint('target_compression_ratio > 1.0', name='check_positive_compression_target'),
        CheckConstraint('max_quality_loss_percent >= 0 AND max_quality_loss_percent <= 100', 
                       name='check_quality_loss_bounds'),
    )


class CompressionStatistics(Base):
    """
    Compression performance statistics and monitoring
    
    Tracks compression effectiveness, performance metrics,
    and optimization opportunities across sessions.
    """
    __tablename__ = "compression_statistics"
    
    # Primary identification  
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("labjack_raw_sessions.id", ondelete="CASCADE"), 
                       nullable=False, index=True)
    
    # Time window for statistics
    window_start_us = Column(BigInteger, nullable=False, index=True)
    window_end_us = Column(BigInteger, nullable=False, index=True)
    window_duration_us = Column(BigInteger, nullable=False)
    
    # Compression effectiveness
    raw_samples_processed = Column(BigInteger, nullable=False)
    transitions_generated = Column(Integer, nullable=False)
    run_periods_generated = Column(Integer, nullable=False)
    achieved_compression_ratio = Column(Float, nullable=False)
    
    # Storage metrics (bytes)
    raw_data_size_bytes = Column(BigInteger, nullable=False)
    compressed_data_size_bytes = Column(BigInteger, nullable=False)
    metadata_overhead_bytes = Column(Integer, default=0)
    total_storage_bytes = Column(BigInteger, nullable=False)
    
    # Quality metrics
    signal_fidelity_score = Column(Float, nullable=True)  # 0.0-1.0
    reconstruction_accuracy = Column(Float, nullable=True)  # % accuracy
    data_loss_estimate = Column(Float, nullable=True)  # % estimated loss
    
    # Performance metrics  
    compression_duration_ms = Column(Float, nullable=True)
    throughput_samples_per_second = Column(Float, nullable=True)
    cpu_usage_percent = Column(Float, nullable=True)
    memory_usage_mb = Column(Float, nullable=True)
    
    # Channel-specific statistics
    channel_statistics = Column(JSON, nullable=True)  # Per-channel breakdowns
    algorithm_performance = Column(JSON, nullable=True)  # Algorithm-specific metrics
    
    # Temporal patterns
    peak_transition_rate_hz = Column(Float, nullable=True)
    average_run_length_ms = Column(Float, nullable=True)
    noise_level_statistics = Column(JSON, nullable=True)
    
    # Metadata
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    calculation_version = Column(String(20), default="1.0")
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    session = relationship("LabJackRawSession", foreign_keys=[session_id])
    
    # Analytics indexes
    __table_args__ = (
        Index('idx_compression_stats_session_time', 'session_id', 'window_start_us'),
        Index('idx_compression_stats_compression_ratio', 'achieved_compression_ratio'),
        Index('idx_compression_stats_performance', 'throughput_samples_per_second', 'compression_duration_ms'),
        Index('idx_compression_stats_quality', 'signal_fidelity_score', 'reconstruction_accuracy'),
        Index('idx_compression_stats_temporal', 'window_start_us', 'window_end_us'),
        CheckConstraint('window_end_us > window_start_us', name='check_valid_window'),
        CheckConstraint('achieved_compression_ratio > 0', name='check_positive_ratio'),
        CheckConstraint('total_storage_bytes >= compressed_data_size_bytes', name='check_storage_consistency'),
    )


# ===== HYBRID QUERY COMPATIBILITY LAYER =====

class DetectionEventCompressed(Base):
    """
    Compressed detection events linked to raw data
    
    Provides compatibility with existing detection_events table while
    linking to compressed raw data for detailed analysis.
    """
    __tablename__ = "detection_events_compressed"
    
    # Primary identification (compatible with existing schema)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), 
                            nullable=False, index=True)
    
    # Compatibility fields (match existing detection_events structure)
    timestamp = Column(Float, nullable=False, index=True)  # Unix timestamp (seconds)
    validation_result = Column(String, index=True)
    ground_truth_match_id = Column(String(36), nullable=True)
    
    # Enhanced timing fields (microsecond precision)
    timestamp_us = Column(BigInteger, nullable=False, index=True)
    labjack_timestamp_ns = Column(String(20), nullable=True)
    timing_precision_ns = Column(Float, nullable=True)
    
    # Raw data links
    raw_session_id = Column(String(36), ForeignKey("labjack_raw_sessions.id"), nullable=True, index=True)
    transition_id = Column(String(36), ForeignKey("voltage_transitions.id"), nullable=True, index=True)
    
    # Detection context from compressed data
    voltage_before_v = Column(Float, nullable=True)
    voltage_after_v = Column(Float, nullable=True)
    transition_type = Column(String(20), nullable=True)
    detection_confidence = Column(Float, nullable=True)
    
    # Backward compatibility fields
    latency_ms = Column(Float, nullable=True, index=True)
    validation_threshold_ms = Column(Float, nullable=True)
    source = Column(String, default='labjack_compressed', index=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    test_session = relationship("TestSession", foreign_keys=[test_session_id])
    raw_session = relationship("LabJackRawSession", foreign_keys=[raw_session_id])
    transition = relationship("VoltageTransition", foreign_keys=[transition_id])
    
    # Hybrid query indexes (support both old and new query patterns)
    __table_args__ = (
        Index('idx_detection_compressed_session_time', 'test_session_id', 'timestamp'),
        Index('idx_detection_compressed_session_time_us', 'test_session_id', 'timestamp_us'),
        Index('idx_detection_compressed_validation', 'validation_result', 'timestamp'),
        Index('idx_detection_compressed_raw_link', 'raw_session_id', 'transition_id'),
        Index('idx_detection_compressed_latency', 'latency_ms', 'validation_result'),
        Index('idx_detection_compressed_source', 'source', 'timestamp'),
    )


# ===== MIGRATION AND COMPATIBILITY VIEWS =====

# Note: These would be implemented as database views, but documented here
# for the migration strategy

class LabJackDataMigrationLog(Base):
    """
    Migration tracking for raw data compression implementation
    
    Tracks the migration of existing detection data to the new
    compressed format and ensures no data loss.
    """
    __tablename__ = "labjack_data_migration_log"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    migration_batch = Column(String(100), nullable=False, index=True)
    
    # Source data identification
    source_table = Column(String(100), nullable=False)  # "detection_events", etc.
    source_record_id = Column(String(36), nullable=True)
    source_session_id = Column(String(36), nullable=True, index=True)
    
    # Target compressed data
    target_raw_session_id = Column(String(36), ForeignKey("labjack_raw_sessions.id"), nullable=True)
    target_transition_id = Column(String(36), ForeignKey("voltage_transitions.id"), nullable=True)
    
    # Migration results
    migration_status = Column(String(20), default="pending", index=True)
    records_migrated = Column(Integer, default=0)
    data_preserved = Column(Boolean, default=True)
    compression_achieved = Column(Float, nullable=True)
    
    # Error handling
    migration_errors = Column(JSON, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Metadata
    migration_tool_version = Column(String(20), default="1.0")
    metadata = Column(JSON, nullable=True)
    
    # Indexes for migration monitoring
    __table_args__ = (
        Index('idx_migration_log_batch_status', 'migration_batch', 'migration_status'),
        Index('idx_migration_log_session', 'source_session_id', 'migration_status'),
        Index('idx_migration_log_timing', 'started_at', 'completed_at'),
    )


# Export all models for import
__all__ = [
    'LabJackRawSession',
    'VoltageRunPeriod', 
    'VoltageTransition',
    'CompressionConfiguration',
    'CompressionStatistics',
    'DetectionEventCompressed',
    'LabJackDataMigrationLog',
    'CompressionQuality',
    'VoltageTransitionType', 
    'CompressionStatus'
]