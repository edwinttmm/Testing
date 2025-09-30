"""
Raw LabJack Data Storage Models with Smart Compression

This module defines database models for high-frequency raw LabJack data capture
with intelligent compression, microsecond precision timing, and performance optimization.

Key Features:
- Raw voltage data storage at 1000Hz with smart compression
- Microsecond precision timestamps with monotonic clock support
- Adaptive compression based on voltage patterns and signal characteristics
- Buffer management for high-throughput data ingestion
- Compression ratio tracking and performance monitoring
- Integration with existing detection event system
"""

from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, ForeignKey, JSON, Index, Enum, LargeBinary, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import BYTEA, ARRAY
from datetime import datetime, timezone
from enum import Enum as PyEnum
import uuid
from typing import Optional, Dict, Any, List, Tuple
import json
import struct
import zlib
import numpy as np

from database import Base


class CompressionAlgorithm(PyEnum):
    """Supported compression algorithms"""
    NONE = "none"
    ZLIB = "zlib"
    LZMA = "lzma"
    DELTA_RLE = "delta_rle"  # Delta + Run-length encoding for voltage patterns
    ADAPTIVE = "adaptive"  # Smart selection based on data characteristics
    QUANTIZED = "quantized"  # Quantized compression for reduced precision


class DataQuality(PyEnum):
    """Data quality indicators"""
    EXCELLENT = "excellent"  # Clean signal, low noise
    GOOD = "good"  # Minor noise, good signal integrity
    FAIR = "fair"  # Moderate noise, acceptable quality
    POOR = "poor"  # High noise, degraded quality
    CORRUPT = "corrupt"  # Corrupted or invalid data


class BufferStatus(PyEnum):
    """Buffer processing status"""
    FILLING = "filling"  # Currently accepting data
    READY = "ready"  # Ready for compression
    COMPRESSING = "compressing"  # Being compressed
    COMPRESSED = "compressed"  # Successfully compressed
    FLUSHED = "flushed"  # Flushed to database
    ERROR = "error"  # Error during processing


class RawLabJackSession(Base):
    """
    Raw LabJack data capture session with compression configuration
    
    Manages high-frequency data capture sessions with intelligent compression
    and performance monitoring.
    """
    __tablename__ = "raw_labjack_sessions"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_name = Column(String, nullable=False, index=True)
    test_session_id = Column(String(36), ForeignKey("test_sessions.id"), nullable=True, index=True)
    
    # Hardware configuration
    device_id = Column(String, nullable=False, index=True)
    device_serial = Column(String, nullable=True)
    channels = Column(JSON, nullable=False)  # List of active channels: ["AIN0", "AIN1", ...]
    sample_rate_hz = Column(Integer, nullable=False, default=1000, index=True)
    resolution_bits = Column(Integer, default=16)
    voltage_range = Column(JSON)  # {"min": -10.0, "max": 10.0} per channel
    
    # Timing configuration
    timing_precision_ns = Column(BigInteger, default=1000)  # Timing precision in nanoseconds
    monotonic_clock_enabled = Column(Boolean, default=True)
    hardware_timestamp_enabled = Column(Boolean, default=True)
    drift_compensation_enabled = Column(Boolean, default=True)
    
    # Compression configuration
    compression_algorithm = Column(Enum(CompressionAlgorithm), default=CompressionAlgorithm.ADAPTIVE, index=True)
    compression_level = Column(Integer, default=6)  # 1-9 compression level
    buffer_size_samples = Column(Integer, default=10000)  # Samples per buffer
    compression_threshold = Column(Float, default=0.1)  # Signal variance threshold for compression selection
    quantization_bits = Column(Integer, default=12)  # Bits for quantized compression
    
    # Performance targets
    target_compression_ratio = Column(Float, default=5.0)  # Target compression ratio
    max_latency_ms = Column(Integer, default=100)  # Maximum processing latency
    buffer_overflow_action = Column(String, default="drop_oldest")  # "drop_oldest", "block", "expand"
    
    # Session state
    is_active = Column(Boolean, default=True, index=True)
    started_at = Column(DateTime(timezone=True), index=True)
    stopped_at = Column(DateTime(timezone=True), nullable=True, index=True)
    total_samples_captured = Column(BigInteger, default=0)
    total_bytes_raw = Column(BigInteger, default=0)
    total_bytes_compressed = Column(BigInteger, default=0)
    
    # Performance metrics
    actual_sample_rate_hz = Column(Float, nullable=True)
    average_compression_ratio = Column(Float, nullable=True, index=True)
    buffer_overflows = Column(Integer, default=0)
    compression_errors = Column(Integer, default=0)
    data_quality_score = Column(Float, default=1.0, index=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    configuration = Column(JSON)  # Additional configuration parameters
    metadata = Column(JSON)  # Session metadata and notes
    
    # Relationships
    test_session = relationship("TestSession", backref="raw_labjack_sessions")
    data_buffers = relationship("RawLabJackBuffer", back_populates="session", cascade="all, delete-orphan")
    compression_stats = relationship("CompressionStatistics", back_populates="session", cascade="all, delete-orphan")
    
    # Performance indexes
    __table_args__ = (
        Index('idx_raw_session_active_time', 'is_active', 'started_at'),
        Index('idx_raw_session_device_time', 'device_id', 'started_at'),
        Index('idx_raw_session_sample_rate', 'sample_rate_hz'),
        Index('idx_raw_session_compression', 'compression_algorithm', 'average_compression_ratio'),
        Index('idx_raw_session_quality', 'data_quality_score', 'is_active'),
        Index('idx_raw_session_performance', 'buffer_overflows', 'compression_errors'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        return {
            'id': self.id,
            'session_name': self.session_name,
            'test_session_id': self.test_session_id,
            'device_id': self.device_id,
            'channels': self.channels,
            'sample_rate_hz': self.sample_rate_hz,
            'compression_algorithm': self.compression_algorithm.value if self.compression_algorithm else None,
            'buffer_size_samples': self.buffer_size_samples,
            'is_active': self.is_active,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'total_samples_captured': self.total_samples_captured,
            'average_compression_ratio': self.average_compression_ratio,
            'data_quality_score': self.data_quality_score,
            'metadata': self.metadata
        }


class RawLabJackBuffer(Base):
    """
    Raw LabJack data buffer with smart compression
    
    Stores compressed raw voltage data with timing information and compression metadata.
    Buffers are optimized for high-frequency data capture and intelligent compression.
    """
    __tablename__ = "raw_labjack_buffers"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("raw_labjack_sessions.id"), nullable=False, index=True)
    buffer_sequence = Column(BigInteger, nullable=False, index=True)  # Sequential buffer number
    
    # Timing information (microsecond precision)
    start_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    start_timestamp_ns = Column(BigInteger, nullable=False, index=True)  # Nanosecond precision
    end_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    end_timestamp_ns = Column(BigInteger, nullable=False, index=True)
    monotonic_start_ns = Column(BigInteger, nullable=True)  # Monotonic clock start
    monotonic_end_ns = Column(BigInteger, nullable=True)  # Monotonic clock end
    
    # Data characteristics
    sample_count = Column(Integer, nullable=False)
    channel_count = Column(Integer, nullable=False)
    actual_sample_rate_hz = Column(Float, nullable=False)
    channels = Column(JSON, nullable=False)  # Channel names/numbers
    
    # Signal analysis
    signal_statistics = Column(JSON)  # Per-channel min/max/mean/std/rms
    data_quality = Column(Enum(DataQuality), default=DataQuality.GOOD, index=True)
    noise_level = Column(Float, default=0.0)  # Estimated noise level
    signal_to_noise_ratio = Column(Float, nullable=True)
    outlier_count = Column(Integer, default=0)
    
    # Compression information
    compression_algorithm = Column(Enum(CompressionAlgorithm), nullable=False, index=True)
    compression_level = Column(Integer, default=6)
    raw_data_size_bytes = Column(Integer, nullable=False)
    compressed_data_size_bytes = Column(Integer, nullable=False)
    compression_ratio = Column(Float, nullable=False, index=True)
    compression_time_ms = Column(Float, nullable=True)
    
    # Compressed data storage
    compressed_data = Column(LargeBinary, nullable=False)  # Compressed voltage data
    compression_metadata = Column(JSON)  # Compression parameters and metadata
    checksum = Column(String(64))  # Data integrity checksum
    
    # Processing information
    buffer_status = Column(Enum(BufferStatus), default=BufferStatus.COMPRESSED, index=True)
    processing_time_ms = Column(Float, nullable=True)
    error_count = Column(Integer, default=0)
    error_details = Column(JSON)  # Error information if any
    
    # Quality assurance
    data_integrity_verified = Column(Boolean, default=True)
    decompression_verified = Column(Boolean, default=False)
    data_loss_detected = Column(Boolean, default=False, index=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    metadata = Column(JSON)
    
    # Relationships
    session = relationship("RawLabJackSession", back_populates="data_buffers")
    
    # Performance indexes
    __table_args__ = (
        Index('idx_raw_buffer_session_sequence', 'session_id', 'buffer_sequence'),
        Index('idx_raw_buffer_session_time', 'session_id', 'start_timestamp'),
        Index('idx_raw_buffer_compression', 'compression_algorithm', 'compression_ratio'),
        Index('idx_raw_buffer_quality', 'data_quality', 'signal_to_noise_ratio'),
        Index('idx_raw_buffer_timing', 'start_timestamp_ns', 'end_timestamp_ns'),
        Index('idx_raw_buffer_status', 'buffer_status', 'created_at'),
        Index('idx_raw_buffer_data_loss', 'data_loss_detected', 'session_id'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert buffer to dictionary (excluding binary data)"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'buffer_sequence': self.buffer_sequence,
            'start_timestamp': self.start_timestamp.isoformat() if self.start_timestamp else None,
            'start_timestamp_ns': self.start_timestamp_ns,
            'end_timestamp': self.end_timestamp.isoformat() if self.end_timestamp else None,
            'end_timestamp_ns': self.end_timestamp_ns,
            'sample_count': self.sample_count,
            'channel_count': self.channel_count,
            'actual_sample_rate_hz': self.actual_sample_rate_hz,
            'channels': self.channels,
            'signal_statistics': self.signal_statistics,
            'data_quality': self.data_quality.value if self.data_quality else None,
            'compression_algorithm': self.compression_algorithm.value if self.compression_algorithm else None,
            'compression_ratio': self.compression_ratio,
            'raw_data_size_bytes': self.raw_data_size_bytes,
            'compressed_data_size_bytes': self.compressed_data_size_bytes,
            'buffer_status': self.buffer_status.value if self.buffer_status else None,
            'data_integrity_verified': self.data_integrity_verified,
            'data_loss_detected': self.data_loss_detected,
            'metadata': self.metadata
        }
    
    def get_decompressed_data(self) -> Optional[np.ndarray]:
        """Decompress and return raw voltage data"""
        from services.raw_labjack_compression import RawLabJackCompressor
        compressor = RawLabJackCompressor()
        
        try:
            return compressor.decompress_buffer(
                self.compressed_data,
                self.compression_algorithm,
                {
                    'sample_count': self.sample_count,
                    'channel_count': self.channel_count,
                    'compression_metadata': self.compression_metadata
                }
            )
        except Exception as e:
            print(f"Error decompressing buffer {self.id}: {e}")
            return None


class CompressionStatistics(Base):
    """
    Compression performance statistics and analytics
    
    Tracks compression performance, algorithm effectiveness, and system health
    for raw LabJack data capture sessions.
    """
    __tablename__ = "compression_statistics"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("raw_labjack_sessions.id"), nullable=False, index=True)
    
    # Time window
    window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    window_end = Column(DateTime(timezone=True), nullable=False, index=True)
    window_duration_seconds = Column(Float, nullable=False)
    
    # Compression performance by algorithm
    algorithms_used = Column(JSON)  # Dict of algorithm -> usage_count
    average_compression_ratios = Column(JSON)  # Dict of algorithm -> avg_ratio
    compression_times_ms = Column(JSON)  # Dict of algorithm -> avg_time_ms
    
    # Data characteristics
    total_buffers_processed = Column(Integer, default=0)
    total_samples_processed = Column(BigInteger, default=0)
    total_raw_bytes = Column(BigInteger, default=0)
    total_compressed_bytes = Column(BigInteger, default=0)
    overall_compression_ratio = Column(Float, nullable=False, index=True)
    
    # Quality metrics
    signal_quality_distribution = Column(JSON)  # Distribution of quality levels
    average_signal_to_noise_ratio = Column(Float, nullable=True)
    data_loss_events = Column(Integer, default=0)
    compression_errors = Column(Integer, default=0)
    
    # Performance metrics
    throughput_samples_per_second = Column(Float, nullable=True)
    throughput_megabytes_per_second = Column(Float, nullable=True)
    buffer_utilization_percent = Column(Float, default=0.0)
    memory_usage_mb = Column(Float, nullable=True)
    
    # Algorithm effectiveness
    adaptive_algorithm_selections = Column(JSON)  # Algorithm selection statistics
    compression_efficiency_score = Column(Float, default=1.0, index=True)
    processing_efficiency_score = Column(Float, default=1.0)
    
    # System health indicators
    buffer_overflow_count = Column(Integer, default=0)
    processing_delays_ms = Column(JSON)  # Histogram of processing delays
    error_rates = Column(JSON)  # Error rates by type
    
    # Metadata
    computed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    computation_time_ms = Column(Float, nullable=True)
    metadata = Column(JSON)
    
    # Relationships
    session = relationship("RawLabJackSession", back_populates="compression_stats")
    
    # Performance indexes
    __table_args__ = (
        Index('idx_comp_stats_session_window', 'session_id', 'window_start', 'window_end'),
        Index('idx_comp_stats_compression_ratio', 'overall_compression_ratio'),
        Index('idx_comp_stats_efficiency', 'compression_efficiency_score', 'processing_efficiency_score'),
        Index('idx_comp_stats_throughput', 'throughput_samples_per_second'),
        Index('idx_comp_stats_computed', 'computed_at'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'window_start': self.window_start.isoformat() if self.window_start else None,
            'window_end': self.window_end.isoformat() if self.window_end else None,
            'window_duration_seconds': self.window_duration_seconds,
            'total_buffers_processed': self.total_buffers_processed,
            'total_samples_processed': self.total_samples_processed,
            'overall_compression_ratio': self.overall_compression_ratio,
            'throughput_samples_per_second': self.throughput_samples_per_second,
            'buffer_utilization_percent': self.buffer_utilization_percent,
            'compression_efficiency_score': self.compression_efficiency_score,
            'buffer_overflow_count': self.buffer_overflow_count,
            'data_loss_events': self.data_loss_events,
            'algorithms_used': self.algorithms_used,
            'average_compression_ratios': self.average_compression_ratios,
            'metadata': self.metadata
        }


class RawLabJackIndex(Base):
    """
    Time-series index for efficient raw data queries
    
    Provides fast access to raw data buffers by time ranges and other criteria.
    Optimized for high-frequency data analysis and retrieval.
    """
    __tablename__ = "raw_labjack_index"
    
    # Primary identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("raw_labjack_sessions.id"), nullable=False, index=True)
    
    # Time indexing (optimized for range queries)
    start_timestamp_ns = Column(BigInteger, nullable=False, index=True)
    end_timestamp_ns = Column(BigInteger, nullable=False, index=True)
    duration_ns = Column(BigInteger, nullable=False)
    
    # Data location
    buffer_ids = Column(JSON, nullable=False)  # List of buffer IDs in time range
    sample_count_total = Column(BigInteger, nullable=False)
    
    # Quick statistics for filtering
    min_voltage = Column(Float, nullable=True)
    max_voltage = Column(Float, nullable=True)
    avg_voltage = Column(Float, nullable=True)
    has_detections = Column(Boolean, default=False, index=True)
    
    # Data quality indicators
    data_quality = Column(Enum(DataQuality), nullable=False, index=True)
    compression_ratio_avg = Column(Float, nullable=True, index=True)
    data_completeness_percent = Column(Float, default=100.0, index=True)
    
    # Metadata
    channels = Column(JSON, nullable=False)  # Channel information
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    metadata = Column(JSON)
    
    # Performance indexes for time-series queries
    __table_args__ = (
        Index('idx_raw_index_session_time_range', 'session_id', 'start_timestamp_ns', 'end_timestamp_ns'),
        Index('idx_raw_index_voltage_range', 'min_voltage', 'max_voltage'),
        Index('idx_raw_index_detections_quality', 'has_detections', 'data_quality'),
        Index('idx_raw_index_completeness', 'data_completeness_percent', 'session_id'),
        Index('idx_raw_index_time_duration', 'start_timestamp_ns', 'duration_ns'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert index to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'start_timestamp_ns': self.start_timestamp_ns,
            'end_timestamp_ns': self.end_timestamp_ns,
            'duration_ns': self.duration_ns,
            'buffer_ids': self.buffer_ids,
            'sample_count_total': self.sample_count_total,
            'min_voltage': self.min_voltage,
            'max_voltage': self.max_voltage,
            'avg_voltage': self.avg_voltage,
            'has_detections': self.has_detections,
            'data_quality': self.data_quality.value if self.data_quality else None,
            'compression_ratio_avg': self.compression_ratio_avg,
            'data_completeness_percent': self.data_completeness_percent,
            'channels': self.channels,
            'metadata': self.metadata
        }


# Export all models
__all__ = [
    'CompressionAlgorithm',
    'DataQuality', 
    'BufferStatus',
    'RawLabJackSession',
    'RawLabJackBuffer',
    'CompressionStatistics',
    'RawLabJackIndex'
]