"""
Frame Buffer Service - Prevents frame drops during video processing

This service implements an asynchronous frame buffer to decouple video reading
from model inference, preventing frame drops when inference is slower than video FPS.

Key Features:
- Asynchronous frame queue with configurable size
- Dropped frame detection and logging
- Backpressure handling
- Performance metrics tracking
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import threading
import queue

logger = logging.getLogger(__name__)


@dataclass
class FrameData:
    """Container for frame data with metadata"""
    frame_number: int
    timestamp: float
    frame: Any  # numpy array from cv2
    video_timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BufferMetrics:
    """Metrics for frame buffer performance"""
    frames_received: int = 0
    frames_processed: int = 0
    frames_dropped: int = 0
    frames_in_buffer: int = 0
    buffer_full_events: int = 0
    avg_processing_time_ms: float = 0.0
    max_processing_time_ms: float = 0.0
    detection_rate_percent: float = 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "frames_received": self.frames_received,
            "frames_processed": self.frames_processed,
            "frames_dropped": self.frames_dropped,
            "frames_in_buffer": self.frames_in_buffer,
            "buffer_full_events": self.buffer_full_events,
            "avg_processing_time_ms": round(self.avg_processing_time_ms, 2),
            "max_processing_time_ms": round(self.max_processing_time_ms, 2),
            "detection_rate_percent": round(self.detection_rate_percent, 2),
            "missed_frames": self.frames_dropped
        }


class FrameBufferService:
    """
    Asynchronous frame buffer service to prevent frame drops

    This service maintains a queue between video reading and frame processing,
    allowing the video reader to continue even when inference is slow.
    """

    def __init__(self, max_buffer_size: int = 120, backpressure_threshold: float = 0.8):
        """
        Initialize frame buffer service

        Args:
            max_buffer_size: Maximum frames in buffer (default: 120 = 4 seconds at 30fps)
            backpressure_threshold: Buffer fullness ratio to trigger backpressure (0.8 = 80%)
        """
        self.max_buffer_size = max_buffer_size
        self.backpressure_threshold = backpressure_threshold

        # Frame buffer (async queue)
        self.frame_queue: asyncio.Queue = None

        # Metrics
        self.metrics = BufferMetrics()
        self.processing_times: List[float] = []

        # Control flags
        self.is_active = False
        self.stop_requested = False

        # Thread safety
        self.lock = threading.RLock()

        # Last frame tracking for drop detection
        self.last_frame_number = 0
        self.dropped_frame_ranges: List[Tuple[int, int]] = []

        logger.info(f"FrameBufferService initialized: buffer_size={max_buffer_size}, "
                   f"backpressure_threshold={backpressure_threshold}")

    def initialize(self):
        """Initialize the frame buffer (must be called from async context)"""
        self.frame_queue = asyncio.Queue(maxsize=self.max_buffer_size)
        self.is_active = True
        self.stop_requested = False
        self.metrics = BufferMetrics()
        self.processing_times = []
        self.last_frame_number = 0
        self.dropped_frame_ranges = []
        logger.info("Frame buffer initialized and ready")

    async def add_frame(self, frame_data: FrameData, block: bool = True) -> bool:
        """
        Add frame to buffer

        Args:
            frame_data: Frame data to add
            block: Whether to block when buffer is full (default: True)

        Returns:
            True if frame was added, False if dropped
        """
        if not self.is_active:
            logger.warning("Frame buffer not active, dropping frame")
            return False

        # Check for dropped frames
        expected_frame = self.last_frame_number + 1
        if self.last_frame_number > 0 and frame_data.frame_number > expected_frame:
            dropped_count = frame_data.frame_number - expected_frame
            self.metrics.frames_dropped += dropped_count
            self.dropped_frame_ranges.append((expected_frame, frame_data.frame_number - 1))
            logger.warning(f"⚠️ DROPPED FRAMES DETECTED: {dropped_count} frames "
                          f"({expected_frame} to {frame_data.frame_number - 1})")

        self.last_frame_number = frame_data.frame_number
        self.metrics.frames_received += 1

        try:
            if block:
                # Block until space available
                await self.frame_queue.put(frame_data)
                with self.lock:
                    self.metrics.frames_in_buffer = self.frame_queue.qsize()
                return True
            else:
                # Non-blocking: drop frame if buffer full
                try:
                    self.frame_queue.put_nowait(frame_data)
                    with self.lock:
                        self.metrics.frames_in_buffer = self.frame_queue.qsize()
                    return True
                except asyncio.QueueFull:
                    self.metrics.frames_dropped += 1
                    self.metrics.buffer_full_events += 1
                    logger.warning(f"⚠️ Buffer full, dropping frame {frame_data.frame_number}")
                    return False

        except Exception as e:
            logger.error(f"Error adding frame to buffer: {e}")
            self.metrics.frames_dropped += 1
            return False

    async def get_frame(self, timeout: Optional[float] = None) -> Optional[FrameData]:
        """
        Get next frame from buffer

        Args:
            timeout: Optional timeout in seconds

        Returns:
            FrameData or None if timeout or stopped
        """
        if not self.is_active:
            return None

        try:
            if timeout:
                frame_data = await asyncio.wait_for(self.frame_queue.get(), timeout=timeout)
            else:
                frame_data = await self.frame_queue.get()

            with self.lock:
                self.metrics.frames_in_buffer = self.frame_queue.qsize()

            return frame_data

        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Error getting frame from buffer: {e}")
            return None

    def record_processing_time(self, processing_time_ms: float):
        """Record frame processing time for metrics"""
        with self.lock:
            self.processing_times.append(processing_time_ms)
            self.metrics.frames_processed += 1

            # Update max processing time
            if processing_time_ms > self.metrics.max_processing_time_ms:
                self.metrics.max_processing_time_ms = processing_time_ms

            # Calculate average (keep last 100 measurements)
            if len(self.processing_times) > 100:
                self.processing_times = self.processing_times[-100:]

            self.metrics.avg_processing_time_ms = sum(self.processing_times) / len(self.processing_times)

            # Update detection rate
            if self.metrics.frames_received > 0:
                self.metrics.detection_rate_percent = (
                    (self.metrics.frames_processed / self.metrics.frames_received) * 100
                )

    def should_apply_backpressure(self) -> bool:
        """Check if backpressure should be applied"""
        if not self.is_active or self.frame_queue is None:
            return False

        buffer_fullness = self.frame_queue.qsize() / self.max_buffer_size
        return buffer_fullness >= self.backpressure_threshold

    def get_metrics(self) -> Dict[str, Any]:
        """Get current buffer metrics"""
        with self.lock:
            metrics_dict = self.metrics.to_dict()
            metrics_dict["buffer_size"] = self.max_buffer_size
            metrics_dict["buffer_fullness_percent"] = (
                (self.metrics.frames_in_buffer / self.max_buffer_size) * 100
                if self.max_buffer_size > 0 else 0
            )
            metrics_dict["backpressure_active"] = self.should_apply_backpressure()
            metrics_dict["dropped_frame_ranges"] = self.dropped_frame_ranges.copy()
            return metrics_dict

    def get_detection_rate(self) -> float:
        """Get current detection rate percentage"""
        return self.metrics.detection_rate_percent

    def stop(self):
        """Stop the frame buffer"""
        self.stop_requested = True
        self.is_active = False
        logger.info(f"Frame buffer stopped. Final metrics: {self.get_metrics()}")

    def reset(self):
        """Reset buffer and metrics"""
        if self.frame_queue:
            # Clear queue
            while not self.frame_queue.empty():
                try:
                    self.frame_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

        self.metrics = BufferMetrics()
        self.processing_times = []
        self.last_frame_number = 0
        self.dropped_frame_ranges = []
        logger.info("Frame buffer reset")


class DetectionRateMonitor:
    """
    Monitor detection rate and alert when it falls below threshold

    This monitor tracks the detection rate over time and can trigger
    alerts or adjustments when the rate falls below acceptable levels.
    """

    def __init__(self, expected_fps: float, min_detection_rate: float = 0.95):
        """
        Initialize detection rate monitor

        Args:
            expected_fps: Expected video frame rate
            min_detection_rate: Minimum acceptable detection rate (0.95 = 95%)
        """
        self.expected_fps = expected_fps
        self.min_detection_rate = min_detection_rate

        self.detection_count = 0
        self.expected_detection_count = 0
        self.start_time = time.time()

        self.alerts: List[Dict[str, Any]] = []
        self.last_alert_time = 0
        self.alert_cooldown = 5.0  # Seconds between alerts

        logger.info(f"DetectionRateMonitor initialized: fps={expected_fps}, "
                   f"min_rate={min_detection_rate*100}%")

    def record_detection(self):
        """Record a successful detection"""
        self.detection_count += 1
        self._check_rate()

    def _check_rate(self):
        """Check if detection rate is acceptable"""
        elapsed = time.time() - self.start_time
        self.expected_detection_count = int(elapsed * self.expected_fps)

        if self.expected_detection_count > 0:
            actual_rate = self.detection_count / self.expected_detection_count

            # Alert if rate is low and cooldown expired
            if actual_rate < self.min_detection_rate:
                current_time = time.time()
                if current_time - self.last_alert_time >= self.alert_cooldown:
                    missed_count = self.expected_detection_count - self.detection_count
                    alert = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "elapsed": elapsed,
                        "detection_count": self.detection_count,
                        "expected_count": self.expected_detection_count,
                        "actual_rate": actual_rate,
                        "min_rate": self.min_detection_rate,
                        "missed_count": missed_count
                    }
                    self.alerts.append(alert)
                    self.last_alert_time = current_time

                    logger.warning(
                        f"⚠️ LOW DETECTION RATE: {actual_rate*100:.1f}% "
                        f"(expected {self.min_detection_rate*100:.1f}%), "
                        f"missed {missed_count} detections"
                    )

    def get_stats(self) -> Dict[str, Any]:
        """Get detection rate statistics"""
        elapsed = time.time() - self.start_time
        self.expected_detection_count = int(elapsed * self.expected_fps)

        actual_rate = (
            self.detection_count / self.expected_detection_count
            if self.expected_detection_count > 0 else 1.0
        )

        return {
            "elapsed_seconds": elapsed,
            "detection_count": self.detection_count,
            "expected_count": self.expected_detection_count,
            "actual_rate": actual_rate,
            "actual_rate_percent": actual_rate * 100,
            "min_rate": self.min_detection_rate,
            "min_rate_percent": self.min_detection_rate * 100,
            "missed_count": max(0, self.expected_detection_count - self.detection_count),
            "alert_count": len(self.alerts),
            "is_acceptable": actual_rate >= self.min_detection_rate
        }


# Global instance (created per session)
_buffer_instances: Dict[str, FrameBufferService] = {}


def get_frame_buffer(session_id: str, max_buffer_size: int = 120) -> FrameBufferService:
    """Get or create frame buffer for session"""
    if session_id not in _buffer_instances:
        _buffer_instances[session_id] = FrameBufferService(max_buffer_size=max_buffer_size)
    return _buffer_instances[session_id]


def cleanup_frame_buffer(session_id: str):
    """Clean up frame buffer for session"""
    if session_id in _buffer_instances:
        _buffer_instances[session_id].stop()
        del _buffer_instances[session_id]
        logger.info(f"Frame buffer cleaned up for session {session_id}")
