"""
Raw LabJack Logging Service with Smart Compression Integration

This service provides high-frequency raw LabJack data capture at 1000Hz with real-time
smart compression, microsecond precision timing, and seamless integration with existing
LabJack detection systems.

Key Features:
- 1000Hz raw data capture without frame synchronization delays
- Real-time smart compression with adaptive algorithm selection
- Microsecond precision timestamps with monotonic clock support
- Buffer management for high-throughput data processing
- Integration with existing detection event system
- Performance monitoring and health diagnostics
- Error recovery and hardware resilience
"""

import asyncio
import logging
import time
import threading
import queue
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import uuid
import os
import signal
import psutil

# Database imports
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database import get_db

# Local imports
from services.labjack_service import get_labjack_service, LabJackService
from services.raw_labjack_compression import get_compressor, RawLabJackCompressor, CompressionResult
from src.models.raw_labjack_models import (
    RawLabJackSession, RawLabJackBuffer, CompressionStatistics, RawLabJackIndex,
    CompressionAlgorithm, DataQuality, BufferStatus
)

logger = logging.getLogger(__name__)


@dataclass
class BufferConfig:
    """Configuration for data buffering"""
    buffer_size_samples: int = 10000  # Samples per buffer (10 seconds at 1000Hz)
    max_buffers_memory: int = 100  # Maximum buffers in memory
    compression_batch_size: int = 5  # Buffers to compress in batch
    flush_interval_seconds: int = 30  # Database flush interval
    overflow_action: str = "drop_oldest"  # "drop_oldest", "block", "expand"


@dataclass
class TimingConfig:
    """Configuration for precision timing"""
    use_monotonic_clock: bool = True
    timing_precision_ns: int = 1000  # Nanosecond precision target
    drift_compensation: bool = True
    hardware_timestamp_sync: bool = True
    timing_calibration_interval: int = 3600  # Calibration interval in seconds


@dataclass
class PerformanceMetrics:
    """Real-time performance metrics"""
    samples_captured: int = 0
    samples_lost: int = 0
    buffers_processed: int = 0
    buffers_compressed: int = 0
    compression_errors: int = 0
    average_compression_ratio: float = 0.0
    average_compression_time_ms: float = 0.0
    actual_sample_rate: float = 0.0
    buffer_utilization: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RawLabJackBuffer:
    """In-memory buffer for raw LabJack data before compression"""
    
    def __init__(self, buffer_id: str, channels: List[str], sample_rate: int):
        self.buffer_id = buffer_id
        self.channels = channels
        self.sample_rate = sample_rate
        self.channel_count = len(channels)
        
        # Data storage
        self.voltage_data = []
        self.timestamps_ns = []
        self.monotonic_times = []
        
        # Buffer state
        self.start_time_ns = None
        self.end_time_ns = None
        self.samples_count = 0
        self.is_full = False
        self.status = BufferStatus.FILLING
        
        # Performance tracking
        self.created_at = time.time()
        self.compression_result: Optional[CompressionResult] = None
        
        self.lock = threading.RLock()
    
    def add_sample(self, voltages: List[float], timestamp_ns: int, monotonic_time: float) -> bool:
        """Add voltage sample to buffer"""
        with self.lock:
            if self.status != BufferStatus.FILLING:
                return False
            
            self.voltage_data.append(voltages)
            self.timestamps_ns.append(timestamp_ns)
            self.monotonic_times.append(monotonic_time)
            
            if self.start_time_ns is None:
                self.start_time_ns = timestamp_ns
            
            self.end_time_ns = timestamp_ns
            self.samples_count += 1
            
            return True
    
    def mark_full(self) -> None:
        """Mark buffer as full and ready for compression"""
        with self.lock:
            self.is_full = True
            self.status = BufferStatus.READY
    
    def get_numpy_data(self) -> np.ndarray:
        """Get voltage data as numpy array"""
        with self.lock:
            if not self.voltage_data:
                return np.array([])
            return np.array(self.voltage_data, dtype=np.float32)


class RawLabJackLogger:
    """
    High-performance raw LabJack data logger with smart compression
    
    Captures raw voltage data at 1000Hz, applies intelligent compression,
    and stores data with microsecond precision timing.
    """
    
    def __init__(self, 
                 buffer_config: Optional[BufferConfig] = None,
                 timing_config: Optional[TimingConfig] = None):
        
        # Configuration
        self.buffer_config = buffer_config or BufferConfig()
        self.timing_config = timing_config or TimingConfig()
        
        # Services
        self.labjack_service = get_labjack_service()
        self.compressor = get_compressor()
        
        # State management
        self.active_sessions: Dict[str, RawLabJackSession] = {}
        self.session_buffers: Dict[str, List[RawLabJackBuffer]] = {}
        self.session_configs: Dict[str, Dict[str, Any]] = {}
        
        # Threading
        self.capture_threads: Dict[str, threading.Thread] = {}
        self.compression_thread: Optional[threading.Thread] = None
        self.flush_thread: Optional[threading.Thread] = None
        self.monitoring_thread: Optional[threading.Thread] = None
        
        # Synchronization
        self.shutdown_event = threading.Event()
        self.buffer_queue = queue.Queue(maxsize=1000)
        self.compression_queue = queue.Queue(maxsize=100)
        self.flush_queue = queue.Queue(maxsize=50)
        
        # Thread pool for async operations
        self.thread_pool = ThreadPoolExecutor(max_workers=8)
        
        # Performance tracking
        self.performance_metrics = PerformanceMetrics()
        self.session_metrics: Dict[str, PerformanceMetrics] = {}
        
        # Callbacks
        self.detection_callbacks: List[Callable] = []
        
        # Start background threads
        self._start_background_threads()
        
        logger.info("Raw LabJack Logger initialized with 1000Hz capture capability")
        
    def start_session(self,
                     session_name: str,
                     channels: List[str],
                     sample_rate: int = 1000,
                     test_session_id: Optional[str] = None,
                     compression_algorithm: CompressionAlgorithm = CompressionAlgorithm.ADAPTIVE,
                     **kwargs) -> Optional[str]:
        """
        Start raw LabJack data logging session
        
        Args:
            session_name: Unique session name
            channels: List of LabJack channels to capture
            sample_rate: Sampling rate in Hz (default 1000)
            test_session_id: Optional test session ID for integration
            compression_algorithm: Compression algorithm to use
            **kwargs: Additional configuration options
            
        Returns:
            Session ID if successful, None otherwise
        """
        try:
            # Ensure LabJack is connected
            if not await self._ensure_labjack_connection():
                logger.error("LabJack connection failed - cannot start raw logging session")
                return None
            
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # Get device info
            device_info = await self.labjack_service.get_device_info()
            device_id = device_info.get('serial_number', 'unknown')
            device_serial = str(device_info.get('serial_number', ''))
            
            # Create database session record
            db = next(get_db())
            try:
                db_session = RawLabJackSession(
                    id=session_id,
                    session_name=session_name,
                    test_session_id=test_session_id,
                    device_id=device_id,
                    device_serial=device_serial,
                    channels=channels,
                    sample_rate_hz=sample_rate,
                    resolution_bits=kwargs.get('resolution_bits', 16),
                    voltage_range=kwargs.get('voltage_range', {"min": -10.0, "max": 10.0}),
                    timing_precision_ns=self.timing_config.timing_precision_ns,
                    monotonic_clock_enabled=self.timing_config.use_monotonic_clock,
                    hardware_timestamp_enabled=self.timing_config.hardware_timestamp_sync,
                    drift_compensation_enabled=self.timing_config.drift_compensation,
                    compression_algorithm=compression_algorithm,
                    compression_level=kwargs.get('compression_level', 6),
                    buffer_size_samples=self.buffer_config.buffer_size_samples,
                    compression_threshold=kwargs.get('compression_threshold', 0.1),
                    quantization_bits=kwargs.get('quantization_bits', 12),
                    target_compression_ratio=kwargs.get('target_compression_ratio', 5.0),
                    max_latency_ms=kwargs.get('max_latency_ms', 100),
                    buffer_overflow_action=self.buffer_config.overflow_action,
                    is_active=True,
                    started_at=datetime.now(timezone.utc),
                    configuration=kwargs
                )
                
                db.add(db_session)
                db.commit()
                
                # Store session
                self.active_sessions[session_id] = db_session
                self.session_buffers[session_id] = []
                self.session_configs[session_id] = {
                    'channels': channels,
                    'sample_rate': sample_rate,
                    'compression_algorithm': compression_algorithm,
                    'device_info': device_info,
                    'detection_threshold': kwargs.get('detection_threshold', 3.3),
                    'constant_voltage_mode': kwargs.get('constant_voltage_mode', False),
                    'debounce_ms': kwargs.get('debounce_ms', 20 if not kwargs.get('constant_voltage_mode', False) else 0)  # FIXED: Changed from 100ms to 20ms for 24 FPS video (41.67ms frame period)
                }
                self.session_metrics[session_id] = PerformanceMetrics()
                
                # Start data capture
                if await self._start_data_capture(session_id):
                    logger.info(f"✅ Raw LabJack logging session started: {session_name} (ID: {session_id})")
                    logger.info(f"📊 Configuration: {len(channels)} channels @ {sample_rate}Hz, compression: {compression_algorithm.value}")
                    return session_id
                else:
                    # Cleanup on failure
                    self._cleanup_session(session_id)
                    return None
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to start raw logging session: {e}")
            return None
    
    def stop_session(self, session_id: str) -> Dict[str, Any]:
        """
        Stop raw LabJack data logging session
        
        Args:
            session_id: Session ID to stop
            
        Returns:
            Session statistics and summary
        """
        try:
            if session_id not in self.active_sessions:
                logger.warning(f"Session not found: {session_id}")
                return {'error': 'Session not found'}
            
            # Stop data capture
            self._stop_data_capture(session_id)
            
            # Flush remaining buffers
            self._flush_session_buffers(session_id)
            
            # Update database session
            db = next(get_db())
            try:
                db_session = db.query(RawLabJackSession).filter_by(id=session_id).first()
                if db_session:
                    db_session.is_active = False
                    db_session.stopped_at = datetime.now(timezone.utc)
                    
                    # Update performance metrics
                    metrics = self.session_metrics.get(session_id, PerformanceMetrics())
                    db_session.total_samples_captured = metrics.samples_captured
                    db_session.actual_sample_rate_hz = metrics.actual_sample_rate
                    db_session.average_compression_ratio = metrics.average_compression_ratio
                    db_session.buffer_overflows = metrics.samples_lost
                    db_session.compression_errors = metrics.compression_errors
                    
                    db.commit()
                    
                # Generate session statistics
                statistics = self._generate_session_statistics(session_id)
                
                # Cleanup
                self._cleanup_session(session_id)
                
                logger.info(f"⏹️ Raw LabJack logging session stopped: {session_id}")
                return statistics
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error stopping session {session_id}: {e}")
            return {'error': str(e)}
    
    async def _ensure_labjack_connection(self) -> bool:
        """Ensure LabJack is connected and ready"""
        try:
            # Check if already connected
            status = self.labjack_service.get_status()
            if status.connected:
                return True
            
            # Attempt connection (no mock fallback for raw logging)
            success = await self.labjack_service.connect(allow_mock=False)
            if not success:
                logger.error("Failed to connect to LabJack hardware - mock mode not allowed for raw logging")
                return False
            
            # Verify hardware capabilities
            device_info = await self.labjack_service.get_device_info()
            if device_info.get('is_mock', False):
                logger.error("Mock LabJack detected - raw logging requires real hardware")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"LabJack connection verification failed: {e}")
            return False
    
    async def _start_data_capture(self, session_id: str) -> bool:
        """Start high-frequency data capture for session"""
        try:
            config = self.session_configs[session_id]
            channels = config['channels']
            sample_rate = config['sample_rate']
            
            # Configure LabJack streaming
            actual_rate = await self.labjack_service.configure_stream(channels, sample_rate)
            if actual_rate <= 0:
                logger.error(f"Failed to configure LabJack streaming for session {session_id}")
                return False
            
            # Update actual sample rate
            config['actual_sample_rate'] = actual_rate
            
            # Start streaming
            if not await self.labjack_service.start_stream(channels, sample_rate):
                logger.error(f"Failed to start LabJack streaming for session {session_id}")
                return False
            
            # Start capture thread
            capture_thread = threading.Thread(
                target=self._capture_loop,
                args=(session_id,),
                daemon=True,
                name=f"RawCapture-{session_id[:8]}"
            )
            capture_thread.start()
            self.capture_threads[session_id] = capture_thread
            
            logger.info(f"🎯 Data capture started for session {session_id} @ {actual_rate}Hz")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start data capture: {e}")
            return False
    
    def _capture_loop(self, session_id: str) -> None:
        """High-frequency data capture loop"""
        try:
            config = self.session_configs[session_id]
            channels = config['channels']
            sample_rate = config['actual_sample_rate']
            metrics = self.session_metrics[session_id]
            
            # Initialize timing
            last_sample_time = time.time()
            sample_interval = 1.0 / sample_rate
            
            # Create first buffer
            current_buffer = self._create_new_buffer(session_id)
            
            logger.info(f"🔄 Starting capture loop for session {session_id}")
            
            while session_id in self.active_sessions and not self.shutdown_event.is_set():
                try:
                    # Get streaming data from LabJack
                    stream_data = self.labjack_service.get_stream_data(max_samples=sample_rate)
                    
                    if not stream_data:
                        # No data available, small sleep to prevent CPU spinning
                        time.sleep(0.001)  # 1ms sleep
                        continue
                    
                    # Process streaming data
                    current_time = time.time()
                    monotonic_time = time.monotonic()
                    
                    # Convert stream data to per-channel samples
                    channel_count = len(channels)
                    if len(stream_data) % channel_count != 0:
                        logger.warning(f"Stream data length {len(stream_data)} not divisible by channel count {channel_count}")
                        stream_data = stream_data[:len(stream_data) - (len(stream_data) % channel_count)]
                    
                    samples_received = len(stream_data) // channel_count
                    
                    for i in range(samples_received):
                        # Extract voltages for this sample
                        sample_start = i * channel_count
                        voltages = stream_data[sample_start:sample_start + channel_count]
                        
                        # Calculate precise timestamp
                        sample_offset = (i / sample_rate) if sample_rate > 0 else 0
                        timestamp_s = current_time + sample_offset
                        timestamp_ns = int(timestamp_s * 1_000_000_000)
                        
                        # Add to current buffer
                        if current_buffer.add_sample(voltages, timestamp_ns, monotonic_time + sample_offset):
                            metrics.samples_captured += 1
                            
                            # Check if buffer is full
                            if current_buffer.samples_count >= self.buffer_config.buffer_size_samples:
                                current_buffer.mark_full()
                                
                                # Queue buffer for compression
                                try:
                                    self.buffer_queue.put_nowait((session_id, current_buffer))
                                    metrics.buffers_processed += 1
                                except queue.Full:
                                    logger.warning(f"Buffer queue full for session {session_id} - dropping buffer")
                                    metrics.samples_lost += current_buffer.samples_count
                                
                                # Create new buffer
                                current_buffer = self._create_new_buffer(session_id)
                        else:
                            metrics.samples_lost += 1
                    
                    # Update metrics
                    time_delta = current_time - last_sample_time
                    if time_delta > 0:
                        metrics.actual_sample_rate = samples_received / time_delta
                    last_sample_time = current_time
                    
                    # Detection callback integration
                    if samples_received > 0 and self.detection_callbacks:
                        self._check_detection_thresholds(session_id, voltages, timestamp_ns)
                    
                except Exception as e:
                    logger.error(f"Error in capture loop for session {session_id}: {e}")
                    time.sleep(0.01)  # Brief pause on error
            
            # Final buffer handling
            if current_buffer.samples_count > 0:
                current_buffer.mark_full()
                try:
                    self.buffer_queue.put_nowait((session_id, current_buffer))
                except queue.Full:
                    logger.warning("Final buffer dropped due to full queue")
            
            logger.info(f"🛑 Capture loop ended for session {session_id}")
            
        except Exception as e:
            logger.error(f"Capture loop failed for session {session_id}: {e}")
    
    def _create_new_buffer(self, session_id: str) -> RawLabJackBuffer:
        """Create new buffer for session"""
        config = self.session_configs[session_id]
        buffer_id = f"{session_id}_{int(time.time() * 1000000)}"  # Microsecond precision ID
        
        buffer = RawLabJackBuffer(
            buffer_id=buffer_id,
            channels=config['channels'],
            sample_rate=int(config['actual_sample_rate'])
        )
        
        # Add to session buffers
        if session_id not in self.session_buffers:
            self.session_buffers[session_id] = []
        
        self.session_buffers[session_id].append(buffer)
        
        # Manage buffer memory
        self._manage_buffer_memory(session_id)
        
        return buffer
    
    def _manage_buffer_memory(self, session_id: str) -> None:
        """Manage buffer memory usage"""
        buffers = self.session_buffers.get(session_id, [])
        
        # Remove processed buffers if too many in memory
        if len(buffers) > self.buffer_config.max_buffers_memory:
            # Keep only recent unprocessed buffers
            processed_buffers = [b for b in buffers if b.status in [BufferStatus.COMPRESSED, BufferStatus.FLUSHED]]
            
            if len(processed_buffers) > 10:  # Keep some for reference
                buffers_to_remove = processed_buffers[:-10]
                for buffer in buffers_to_remove:
                    try:
                        buffers.remove(buffer)
                    except ValueError:
                        pass
    
    def _check_detection_thresholds(self, session_id: str, voltages: List[float], timestamp_ns: int) -> None:
        """Check for detection thresholds and trigger callbacks with debounce protection"""
        try:
            # Simple threshold detection (can be enhanced with more sophisticated algorithms)
            config = self.session_configs.get(session_id, {})
            threshold = config.get('detection_threshold', 3.3)  # Default 3.3V threshold (matches dedicated_labjack_monitor.py)

            # CRITICAL FIX: Add constant_voltage_mode support to disable debounce
            constant_voltage_mode = config.get('constant_voltage_mode', False)
            if constant_voltage_mode:
                debounce_ms = 0  # Disable debounce for continuous detection
                logger.info(f"Constant voltage mode enabled for session {session_id} - debounce disabled")
            else:
                debounce_ms = config.get('debounce_ms', 20)  # FIXED: Changed from 100ms to 20ms for 24 FPS video (41.67ms frame period)
                logger.debug(f"Normal mode for session {session_id} - debounce set to {debounce_ms}ms")

            # Get last detection timestamp for this session
            if not hasattr(self, '_last_detection_time'):
                self._last_detection_time = {}

            for i, voltage in enumerate(voltages):
                if voltage > threshold:
                    # Check debounce - prevent duplicate detections within debounce window
                    session_key = f"{session_id}_{i}"
                    last_detection_ns = self._last_detection_time.get(session_key, 0)
                    time_since_last_ms = (timestamp_ns - last_detection_ns) / 1_000_000

                    if debounce_ms > 0 and time_since_last_ms < debounce_ms:
                        logger.debug(f"Debouncing detection: {time_since_last_ms:.1f}ms since last (threshold: {debounce_ms}ms)")
                        break  # Skip this detection - too close to previous one

                    # Record this detection timestamp
                    self._last_detection_time[session_key] = timestamp_ns

                    # Create detection event
                    detection_data = {
                        'session_id': session_id,
                        'channel': i,
                        'voltage': voltage,
                        'timestamp_ns': timestamp_ns,
                        'timestamp': datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=timezone.utc)
                    }

                    logger.info(f"✅ Detection triggered: {voltage:.2f}V on channel {i} (threshold: {threshold}V, debounce: {debounce_ms}ms)")

                    # Notify callbacks
                    for callback in self.detection_callbacks:
                        try:
                            callback(detection_data)
                        except Exception as e:
                            logger.error(f"Detection callback error: {e}")

                    break  # Only one detection per sample

        except Exception as e:
            logger.error(f"Detection threshold check failed: {e}")
    
    def add_detection_callback(self, callback: Callable) -> None:
        """Add detection threshold callback"""
        self.detection_callbacks.append(callback)
        logger.info(f"Detection callback added - total callbacks: {len(self.detection_callbacks)}")
    
    def remove_detection_callback(self, callback: Callable) -> None:
        """Remove detection threshold callback"""
        if callback in self.detection_callbacks:
            self.detection_callbacks.remove(callback)
            logger.info(f"Detection callback removed - remaining callbacks: {len(self.detection_callbacks)}")
    
    def _start_background_threads(self) -> None:
        """Start background processing threads"""
        # Compression thread
        self.compression_thread = threading.Thread(
            target=self._compression_loop,
            daemon=True,
            name="RawCompression"
        )
        self.compression_thread.start()
        
        # Database flush thread
        self.flush_thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="RawFlush"
        )
        self.flush_thread.start()
        
        # Performance monitoring thread
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="RawMonitoring"
        )
        self.monitoring_thread.start()
        
        logger.info("Background threads started for raw LabJack logging")
    
    def _compression_loop(self) -> None:
        """Background compression processing loop"""
        logger.info("🗜️ Compression loop started")
        
        while not self.shutdown_event.is_set():
            try:
                # Get buffer from queue
                try:
                    session_id, buffer = self.buffer_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                if session_id not in self.active_sessions:
                    continue
                
                # Compress buffer
                start_time = time.time()
                buffer.status = BufferStatus.COMPRESSING
                
                # Get voltage data as numpy array
                voltage_data = buffer.get_numpy_data()
                if voltage_data.size == 0:
                    logger.warning(f"Empty buffer for session {session_id}")
                    continue
                
                # Get session configuration
                config = self.session_configs[session_id]
                compression_algorithm = config.get('compression_algorithm', CompressionAlgorithm.ADAPTIVE)
                
                # Compress data
                compression_result = await self.compressor.compress_buffer_async(
                    voltage_data=voltage_data,
                    channels=config['channels'],
                    sample_rate=config['actual_sample_rate'],
                    timestamp_ns=buffer.start_time_ns,
                    algorithm=compression_algorithm
                )
                
                if compression_result.error:
                    logger.error(f"Compression failed: {compression_result.error}")
                    self.session_metrics[session_id].compression_errors += 1
                    continue
                
                buffer.compression_result = compression_result
                buffer.status = BufferStatus.COMPRESSED
                
                # Update metrics
                compression_time = (time.time() - start_time) * 1000  # ms
                metrics = self.session_metrics[session_id]
                metrics.buffers_compressed += 1
                metrics.average_compression_ratio = (
                    (metrics.average_compression_ratio * (metrics.buffers_compressed - 1) + 
                     compression_result.compression_ratio) / metrics.buffers_compressed
                )
                metrics.average_compression_time_ms = (
                    (metrics.average_compression_time_ms * (metrics.buffers_compressed - 1) + 
                     compression_time) / metrics.buffers_compressed
                )
                
                # Queue for database flush
                try:
                    self.compression_queue.put_nowait((session_id, buffer))
                except queue.Full:
                    logger.warning("Compression queue full - dropping compressed buffer")
                
                # Mark task done
                self.buffer_queue.task_done()
                
            except Exception as e:
                logger.error(f"Compression loop error: {e}")
                time.sleep(0.1)
        
        logger.info("🛑 Compression loop ended")
    
    def _flush_loop(self) -> None:
        """Background database flush loop"""
        logger.info("💾 Database flush loop started")
        
        batch_buffers = []
        last_flush = time.time()
        
        while not self.shutdown_event.is_set():
            try:
                # Collect buffers for batch processing
                try:
                    session_id, buffer = self.compression_queue.get(timeout=1.0)
                    batch_buffers.append((session_id, buffer))
                except queue.Empty:
                    pass
                
                # Flush conditions: batch full or time interval reached
                current_time = time.time()
                should_flush = (
                    len(batch_buffers) >= self.buffer_config.compression_batch_size or
                    (batch_buffers and (current_time - last_flush) >= self.buffer_config.flush_interval_seconds)
                )
                
                if should_flush and batch_buffers:
                    self._flush_buffers_to_database(batch_buffers)
                    batch_buffers.clear()
                    last_flush = current_time
                
            except Exception as e:
                logger.error(f"Flush loop error: {e}")
                time.sleep(1.0)
        
        # Final flush
        if batch_buffers:
            self._flush_buffers_to_database(batch_buffers)
        
        logger.info("🛑 Database flush loop ended")
    
    def _flush_buffers_to_database(self, batch_buffers: List[Tuple[str, RawLabJackBuffer]]) -> None:
        """Flush compressed buffers to database"""
        try:
            db = next(get_db())
            try:
                for session_id, buffer in batch_buffers:
                    if not buffer.compression_result:
                        continue
                    
                    compression_result = buffer.compression_result
                    
                    # Calculate signal statistics
                    voltage_data = buffer.get_numpy_data()
                    signal_stats = {}
                    
                    if voltage_data.size > 0:
                        signal_stats = {
                            'min_voltage': float(np.min(voltage_data)),
                            'max_voltage': float(np.max(voltage_data)),
                            'mean_voltage': float(np.mean(voltage_data)),
                            'std_voltage': float(np.std(voltage_data)),
                            'rms_voltage': float(np.sqrt(np.mean(voltage_data ** 2)))
                        }
                    
                    # Create database buffer record
                    db_buffer = RawLabJackBuffer(
                        session_id=session_id,
                        buffer_sequence=len(self.session_buffers.get(session_id, [])),
                        start_timestamp=datetime.fromtimestamp(buffer.start_time_ns / 1_000_000_000, tz=timezone.utc),
                        start_timestamp_ns=buffer.start_time_ns,
                        end_timestamp=datetime.fromtimestamp(buffer.end_time_ns / 1_000_000_000, tz=timezone.utc),
                        end_timestamp_ns=buffer.end_time_ns,
                        sample_count=buffer.samples_count,
                        channel_count=buffer.channel_count,
                        actual_sample_rate_hz=buffer.sample_rate,
                        channels=buffer.channels,
                        signal_statistics=signal_stats,
                        data_quality=compression_result.metadata.get('signal_analysis', {}).get('data_quality', DataQuality.GOOD),
                        compression_algorithm=compression_result.algorithm_used,
                        compression_level=6,  # Default level
                        raw_data_size_bytes=compression_result.original_size,
                        compressed_data_size_bytes=compression_result.compressed_size,
                        compression_ratio=compression_result.compression_ratio,
                        compression_time_ms=compression_result.compression_time_ms,
                        compressed_data=compression_result.compressed_data,
                        compression_metadata=compression_result.metadata,
                        checksum=compression_result.checksum,
                        buffer_status=BufferStatus.FLUSHED,
                        data_integrity_verified=True,
                        processed_at=datetime.now(timezone.utc)
                    )
                    
                    db.add(db_buffer)
                    buffer.status = BufferStatus.FLUSHED
                
                db.commit()
                logger.debug(f"Flushed {len(batch_buffers)} buffers to database")
                
            except SQLAlchemyError as e:
                db.rollback()
                logger.error(f"Database flush failed: {e}")
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Buffer flush error: {e}")
    
    def _monitoring_loop(self) -> None:
        """Background performance monitoring loop"""
        logger.info("📊 Monitoring loop started")
        
        while not self.shutdown_event.is_set():
            try:
                # Update system performance metrics
                process = psutil.Process()
                memory_info = process.memory_info()
                
                self.performance_metrics.memory_usage_mb = memory_info.rss / (1024 * 1024)
                self.performance_metrics.cpu_usage_percent = process.cpu_percent()
                self.performance_metrics.last_update = datetime.now(timezone.utc)
                
                # Update buffer utilization
                total_buffers = sum(len(buffers) for buffers in self.session_buffers.values())
                max_buffers = len(self.active_sessions) * self.buffer_config.max_buffers_memory
                if max_buffers > 0:
                    self.performance_metrics.buffer_utilization = (total_buffers / max_buffers) * 100
                
                time.sleep(5.0)  # Update every 5 seconds
                
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                time.sleep(5.0)
        
        logger.info("🛑 Monitoring loop ended")
    
    def _stop_data_capture(self, session_id: str) -> None:
        """Stop data capture for session"""
        try:
            # Stop LabJack streaming
            asyncio.run(self.labjack_service.stop_stream())
            
            # Wait for capture thread to finish
            capture_thread = self.capture_threads.get(session_id)
            if capture_thread and capture_thread.is_alive():
                capture_thread.join(timeout=5.0)
                if capture_thread.is_alive():
                    logger.warning(f"Capture thread for session {session_id} did not terminate gracefully")
            
            # Remove from active threads
            self.capture_threads.pop(session_id, None)
            
        except Exception as e:
            logger.error(f"Error stopping data capture for session {session_id}: {e}")
    
    def _flush_session_buffers(self, session_id: str) -> None:
        """Flush all remaining buffers for session"""
        try:
            buffers = self.session_buffers.get(session_id, [])
            pending_buffers = [
                (session_id, buffer) for buffer in buffers 
                if buffer.status in [BufferStatus.READY, BufferStatus.COMPRESSED]
            ]
            
            if pending_buffers:
                logger.info(f"Flushing {len(pending_buffers)} remaining buffers for session {session_id}")
                self._flush_buffers_to_database(pending_buffers)
            
        except Exception as e:
            logger.error(f"Error flushing session buffers: {e}")
    
    def _cleanup_session(self, session_id: str) -> None:
        """Clean up session resources"""
        try:
            # Remove from active sessions
            self.active_sessions.pop(session_id, None)
            self.session_configs.pop(session_id, None)
            self.session_metrics.pop(session_id, None)
            
            # Clear buffers (keep compressed ones briefly for reference)
            buffers = self.session_buffers.get(session_id, [])
            uncompressed_buffers = [b for b in buffers if b.status != BufferStatus.FLUSHED]
            for buffer in uncompressed_buffers:
                try:
                    buffers.remove(buffer)
                except ValueError:
                    pass
            
            logger.info(f"Session cleanup completed: {session_id}")
            
        except Exception as e:
            logger.error(f"Session cleanup error: {e}")
    
    def _generate_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """Generate comprehensive session statistics"""
        try:
            session = self.active_sessions.get(session_id)
            metrics = self.session_metrics.get(session_id, PerformanceMetrics())
            buffers = self.session_buffers.get(session_id, [])
            
            duration_seconds = 0
            if session and session.started_at:
                end_time = session.stopped_at or datetime.now(timezone.utc)
                duration_seconds = (end_time - session.started_at).total_seconds()
            
            statistics = {
                'session_id': session_id,
                'duration_seconds': duration_seconds,
                'samples_captured': metrics.samples_captured,
                'samples_lost': metrics.samples_lost,
                'buffers_processed': metrics.buffers_processed,
                'buffers_compressed': metrics.buffers_compressed,
                'compression_errors': metrics.compression_errors,
                'average_compression_ratio': metrics.average_compression_ratio,
                'average_compression_time_ms': metrics.average_compression_time_ms,
                'actual_sample_rate': metrics.actual_sample_rate,
                'data_loss_rate': (metrics.samples_lost / max(metrics.samples_captured + metrics.samples_lost, 1)) * 100,
                'compression_success_rate': ((metrics.buffers_compressed / max(metrics.buffers_processed, 1)) * 100) if metrics.buffers_processed > 0 else 100,
                'total_buffers': len(buffers),
                'flushed_buffers': len([b for b in buffers if b.status == BufferStatus.FLUSHED])
            }
            
            return statistics
            
        except Exception as e:
            logger.error(f"Error generating session statistics: {e}")
            return {'error': str(e)}
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of logging session"""
        try:
            if session_id not in self.active_sessions:
                return None
            
            session = self.active_sessions[session_id]
            metrics = self.session_metrics[session_id]
            config = self.session_configs[session_id]
            
            return {
                'session_id': session_id,
                'session_name': session.session_name,
                'is_active': session.is_active,
                'started_at': session.started_at.isoformat() if session.started_at else None,
                'channels': config['channels'],
                'sample_rate': config['actual_sample_rate'],
                'compression_algorithm': config['compression_algorithm'].value,
                'samples_captured': metrics.samples_captured,
                'samples_lost': metrics.samples_lost,
                'buffers_processed': metrics.buffers_processed,
                'buffers_compressed': metrics.buffers_compressed,
                'actual_sample_rate': metrics.actual_sample_rate,
                'average_compression_ratio': metrics.average_compression_ratio,
                'buffer_utilization': metrics.buffer_utilization
            }
            
        except Exception as e:
            logger.error(f"Error getting session status: {e}")
            return None
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get list of all active sessions"""
        try:
            sessions = []
            for session_id in self.active_sessions.keys():
                status = self.get_session_status(session_id)
                if status:
                    sessions.append(status)
            return sessions
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get overall performance metrics"""
        try:
            return {
                'system_metrics': {
                    'memory_usage_mb': self.performance_metrics.memory_usage_mb,
                    'cpu_usage_percent': self.performance_metrics.cpu_usage_percent,
                    'buffer_utilization': self.performance_metrics.buffer_utilization,
                    'last_update': self.performance_metrics.last_update.isoformat()
                },
                'compression_stats': self.compressor.get_compression_stats(),
                'active_sessions': len(self.active_sessions),
                'total_buffers_in_memory': sum(len(buffers) for buffers in self.session_buffers.values()),
                'queue_sizes': {
                    'buffer_queue': self.buffer_queue.qsize(),
                    'compression_queue': self.compression_queue.qsize(),
                    'flush_queue': self.flush_queue.qsize()
                }
            }
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}
    
    def shutdown(self) -> None:
        """Shutdown the raw LabJack logger"""
        try:
            logger.info("🛑 Shutting down raw LabJack logger...")
            
            # Signal shutdown
            self.shutdown_event.set()
            
            # Stop all active sessions
            active_session_ids = list(self.active_sessions.keys())
            for session_id in active_session_ids:
                self.stop_session(session_id)
            
            # Wait for background threads
            threads = [self.compression_thread, self.flush_thread, self.monitoring_thread]
            for thread in threads:
                if thread and thread.is_alive():
                    thread.join(timeout=5.0)
            
            # Shutdown thread pool
            self.thread_pool.shutdown(wait=True, timeout=10)
            
            logger.info("✅ Raw LabJack logger shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def __del__(self):
        """Cleanup on destruction"""
        try:
            if hasattr(self, 'shutdown_event') and not self.shutdown_event.is_set():
                self.shutdown()
        except:
            pass


# Global logger instance
_raw_logger: Optional[RawLabJackLogger] = None


def get_raw_labjack_logger() -> RawLabJackLogger:
    """Get global raw LabJack logger instance"""
    global _raw_logger
    if _raw_logger is None:
        _raw_logger = RawLabJackLogger()
    return _raw_logger


# Export key components
__all__ = [
    'RawLabJackLogger',
    'BufferConfig',
    'TimingConfig',
    'PerformanceMetrics',
    'get_raw_labjack_logger'
]