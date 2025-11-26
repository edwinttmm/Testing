"""
Enhanced LabJack Monitoring Service with Continuous Detection Algorithm
Implements rate-limited continuous detection during sustained high voltage periods
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional, Dict, Any
import sqlite3
import uuid

logger = logging.getLogger(__name__)

class LabJackMonitoringServiceEnhanced:
    """
    Enhanced service to monitor LabJack signals with continuous detection support.

    Detection Algorithm:
    - Rising edge: Immediate detection when voltage crosses threshold
    - Sustained high: Continuous detections at MIN_INTERVAL_MS rate
    - Falling edge: Reset state for next pulse

    Configuration:
    - MIN_INTERVAL_MS: Minimum milliseconds between detections (default: 40ms = ~24fps)
    - Uses time.monotonic() for accurate timing immune to system clock changes
    """

    # Configuration constants
    DEFAULT_MIN_INTERVAL_MS = 40  # 40ms = 1 frame at 24fps
    DEFAULT_SAMPLE_RATE = 100     # Hz (100 samples/sec for sub-millisecond timing)
    DEFAULT_THRESHOLD_V = 2.5     # Volts

    def __init__(self,
                 min_interval_ms: float = DEFAULT_MIN_INTERVAL_MS,
                 enable_continuous_detection: bool = False):
        """
        Initialize enhanced monitoring service.

        Args:
            min_interval_ms: Minimum milliseconds between continuous detections (default: 40ms)
            enable_continuous_detection: Enable continuous detection mode (default: False for backwards compatibility)
        """
        # Backwards compatibility: Default to original rising-edge-only behavior
        self.enable_continuous_detection = enable_continuous_detection

        # State management
        self.monitoring_active = False
        self.current_session_id = None
        self.monitor_thread = None
        self.sample_rate = self.DEFAULT_SAMPLE_RATE
        self._stop_event = threading.Event()

        # Edge-detection state
        self.threshold_v = self.DEFAULT_THRESHOLD_V
        self._was_high = False

        # Continuous detection state (new)
        self._last_emit_time = 0.0  # monotonic time of last detection emission
        self.min_interval_s = self._validate_interval(min_interval_ms / 1000.0)

        # Performance metrics
        self._total_detections = 0
        self._continuous_detections = 0
        self._rising_edge_detections = 0

        logger.info(
            f"Initialized LabJackMonitoringServiceEnhanced: "
            f"continuous_mode={enable_continuous_detection}, "
            f"min_interval={min_interval_ms}ms"
        )

    def _validate_interval(self, interval_s: float) -> float:
        """
        Validate and clamp MIN_INTERVAL to safe bounds.

        Args:
            interval_s: Proposed interval in seconds

        Returns:
            Validated interval in seconds

        Raises:
            ValueError: If interval is negative
        """
        if interval_s < 0:
            raise ValueError(f"MIN_INTERVAL cannot be negative: {interval_s}")

        # Clamp to reasonable bounds (1ms to 10s)
        MIN_BOUND = 0.001  # 1ms
        MAX_BOUND = 10.0   # 10s

        if interval_s < MIN_BOUND:
            logger.warning(f"MIN_INTERVAL {interval_s}s too small, clamping to {MIN_BOUND}s")
            return MIN_BOUND
        elif interval_s > MAX_BOUND:
            logger.warning(f"MIN_INTERVAL {interval_s}s too large, clamping to {MAX_BOUND}s")
            return MAX_BOUND

        return interval_s

    def configure_detection(self,
                           min_interval_ms: Optional[float] = None,
                           enable_continuous: Optional[bool] = None,
                           threshold_v: Optional[float] = None):
        """
        Dynamically reconfigure detection parameters (must be called when not monitoring).

        Args:
            min_interval_ms: New minimum interval in milliseconds
            enable_continuous: Enable/disable continuous detection mode
            threshold_v: New voltage threshold

        Raises:
            RuntimeError: If called while monitoring is active
        """
        if self.monitoring_active:
            raise RuntimeError("Cannot reconfigure while monitoring is active")

        if min_interval_ms is not None:
            self.min_interval_s = self._validate_interval(min_interval_ms / 1000.0)
            logger.info(f"Updated MIN_INTERVAL to {min_interval_ms}ms")

        if enable_continuous is not None:
            self.enable_continuous_detection = enable_continuous
            logger.info(f"Continuous detection mode: {enable_continuous}")

        if threshold_v is not None:
            if threshold_v <= 0:
                raise ValueError(f"Threshold voltage must be positive: {threshold_v}")
            self.threshold_v = threshold_v
            logger.info(f"Updated threshold to {threshold_v}V")

    def start_monitoring(self, session_id: str, sample_rate: int = None):
        """Start monitoring LabJack signals for a test session"""
        if self.monitoring_active:
            logger.warning(f"Monitoring already active for session {self.current_session_id}")
            return False

        self.current_session_id = session_id
        self.sample_rate = sample_rate or self.DEFAULT_SAMPLE_RATE
        self.monitoring_active = True
        self._stop_event.clear()

        # Reset detection state
        self._was_high = False
        self._last_emit_time = 0.0
        self._total_detections = 0
        self._continuous_detections = 0
        self._rising_edge_detections = 0

        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(session_id,),
            daemon=True,
            name=f"LabJackMonitor-{session_id[:8]}"
        )
        self.monitor_thread.start()

        logger.info(
            f"Started monitoring session {session_id}: "
            f"rate={self.sample_rate}Hz, "
            f"continuous={self.enable_continuous_detection}, "
            f"interval={self.min_interval_s*1000:.1f}ms"
        )
        return True

    def stop_monitoring(self):
        """Stop monitoring and wait for thread to finish"""
        if not self.monitoring_active:
            logger.warning("Monitoring is not active")
            return False

        logger.info(f"Stopping monitoring for session {self.current_session_id}")
        self.monitoring_active = False
        self._stop_event.set()

        # Wait for thread to finish
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
            if self.monitor_thread.is_alive():
                logger.error("Monitoring thread did not stop cleanly")

        # Log performance metrics
        logger.info(
            f"Monitoring stopped. Total detections: {self._total_detections} "
            f"(rising_edge={self._rising_edge_detections}, "
            f"continuous={self._continuous_detections})"
        )

        self.current_session_id = None
        return True

    def _monitor_loop(self, session_id: str):
        """Enhanced background loop with continuous detection support"""
        logger.info(f"Starting monitoring loop for session {session_id}")

        try:
            # Import signal validation service
            from api_signal_validation import signal_validation_service
            logger.info("Successfully imported signal validation service")

            sample_interval = 1.0 / self.sample_rate

            while self.monitoring_active and not self._stop_event.is_set():
                try:
                    # Safety check
                    if not self.monitoring_active or self._stop_event.is_set():
                        logger.debug("Stop signal detected, breaking monitoring loop")
                        break

                    # Read voltage from LabJack
                    result = signal_validation_service.read_voltage_signal("AIN0")

                    if result.get("success") and result.get("voltage") is not None:
                        voltage = result["voltage"]
                        current_time = time.monotonic()  # Use monotonic for timing
                        wall_time = time.time()          # Use wall time for timestamps

                        # Detection state machine
                        if voltage > self.threshold_v:
                            self._handle_high_voltage(
                                session_id=session_id,
                                voltage=voltage,
                                current_time=current_time,
                                wall_time=wall_time
                            )
                        else:
                            # Falling edge or staying low
                            self._handle_low_voltage()
                    else:
                        logger.warning(f"Failed to read voltage: {result}")

                    # Sleep for sample interval
                    time.sleep(sample_interval)

                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                    time.sleep(1)  # Back off on error

        except Exception as e:
            logger.error(f"Fatal error in monitoring thread: {e}", exc_info=True)
        finally:
            self.monitoring_active = False
            self.current_session_id = None
            logger.info(f"Monitoring loop terminated for session {session_id}")

    def _handle_high_voltage(self, session_id: str, voltage: float,
                            current_time: float, wall_time: float):
        """
        Handle voltage above threshold.

        Logic:
        - If first detection (rising edge): Emit immediately
        - If sustained high + continuous mode enabled: Emit if MIN_INTERVAL elapsed
        - Otherwise: Do nothing (original behavior)
        """
        should_emit = False
        detection_type = "unknown"

        if not self._was_high:
            # CASE 1: Rising edge (first detection)
            should_emit = True
            detection_type = "rising_edge"
            self._was_high = True
            self._last_emit_time = current_time
            self._rising_edge_detections += 1

        elif self.enable_continuous_detection:
            # CASE 2: Sustained high with continuous detection enabled
            elapsed = current_time - self._last_emit_time

            if elapsed >= self.min_interval_s:
                should_emit = True
                detection_type = "continuous"
                self._last_emit_time = current_time
                self._continuous_detections += 1

        # Emit detection if conditions met
        if should_emit:
            self._store_detection_event(
                session_id=session_id,
                voltage=voltage,
                timestamp=wall_time,
                channel="AIN0",
                detection_type=detection_type
            )
            self._total_detections += 1

            # Periodic logging
            if self._total_detections <= 10 or self._total_detections % 10 == 0:
                logger.info(
                    f"Captured {self._total_detections} detections "
                    f"({detection_type} @ {voltage:.3f}V)"
                )

    def _handle_low_voltage(self):
        """Handle voltage below threshold (falling edge)"""
        if self._was_high:
            logger.debug("Falling edge detected; arming for next detection")
        self._was_high = False

    def _store_detection_event(self, session_id: str, voltage: float,
                               timestamp: float, channel: str,
                               detection_type: str = "rising_edge"):
        """
        Store detection event to database.

        Args:
            session_id: HIL test session ID
            voltage: Measured voltage
            timestamp: Wall clock timestamp
            channel: LabJack channel name
            detection_type: Type of detection (rising_edge or continuous)
        """
        try:
            # Connect to database
            conn = sqlite3.connect('hil_testing.db')
            cursor = conn.cursor()

            # Generate unique ID
            event_id = str(uuid.uuid4())

            # Insert detection event
            cursor.execute('''
                INSERT INTO detection_events
                (id, session_id, timestamp, voltage, channel, detection_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                event_id,
                session_id,
                timestamp,
                voltage,
                channel,
                detection_type,
                datetime.utcnow().isoformat()
            ))

            conn.commit()
            conn.close()

            logger.debug(
                f"Stored {detection_type} detection: "
                f"session={session_id}, voltage={voltage:.3f}V"
            )

        except Exception as e:
            logger.error(f"Failed to store detection event: {e}", exc_info=True)

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current detection metrics.

        Returns:
            Dictionary with performance metrics
        """
        return {
            "monitoring_active": self.monitoring_active,
            "session_id": self.current_session_id,
            "continuous_mode": self.enable_continuous_detection,
            "min_interval_ms": self.min_interval_s * 1000,
            "total_detections": self._total_detections,
            "rising_edge_detections": self._rising_edge_detections,
            "continuous_detections": self._continuous_detections,
            "threshold_v": self.threshold_v,
            "sample_rate": self.sample_rate
        }


# Singleton instance for backwards compatibility
labjack_monitoring_service = LabJackMonitoringServiceEnhanced(
    enable_continuous_detection=False  # Default to original behavior
)
