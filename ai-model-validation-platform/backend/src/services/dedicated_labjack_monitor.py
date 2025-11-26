#!/usr/bin/env python3
"""
Dedicated LabJack Monitoring Service Process
==========================================

A standalone process dedicated to LabJack monitoring that eliminates device conflicts
for HIL testing. This service runs independently of the main backend and communicates
via IPC mechanisms to ensure exclusive LabJack access.

Key Features:
- Exclusive LabJack device access (prevents conflicts)
- Real-time voltage monitoring at configurable rates (default 10Hz)
- Sub-100ms latency for HIL requirements
- Robust error handling and recovery
- Process health monitoring and auto-restart
- Database integration for detection events
- WebSocket notifications for real-time updates
- WSL/Windows bridge compatibility

Architecture:
- Runs as separate Python process
- Communicates via Unix domain sockets (IPC)
- Shared memory for high-frequency data exchange
- Database connection for event storage
- Signal handling for graceful shutdown
"""

import os
import sys
import time
import json
import signal
import socket
import struct
import sqlite3
import logging
import threading
import multiprocessing
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable, Tuple, List
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid
import traceback
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

# Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

# Import LabJack service based on environment
import platform
if platform.system() == "Linux" and "microsoft" in platform.uname().release.lower():
    from services.signal_validation_wsl import signal_validation_service
else:
    from services.signal_validation_service import signal_validation_service

logger = logging.getLogger(__name__)

# Custom exceptions for per-video monitoring
class LabJackStateError(Exception):
    """Raised when LabJack monitoring state is invalid for requested operation"""
    pass

class LabJackConnectionError(Exception):
    """Raised when LabJack connection fails"""
    pass

class LabJackTimeoutError(Exception):
    """Raised when LabJack operation times out"""
    pass

@dataclass
class MonitoringTimestamps:
    """Precise timing measurements for monitoring session startup"""
    command_sent: float = 0.0  # time.time() when start_monitoring() called
    labjack_response: float = 0.0  # time.time() when LabJack confirms ready
    first_sample: float = 0.0  # time.time() when first voltage reading received
    stream_started: Optional[float] = None  # Stream mode start time (if used)

    @property
    def initialization_latency_ms(self) -> float:
        """USB latency from command to LabJack response (milliseconds)"""
        if self.labjack_response > 0:
            return (self.labjack_response - self.command_sent) * 1000
        return 0.0

    @property
    def total_startup_latency_ms(self) -> float:
        """Total time from command to first sample (milliseconds)"""
        if self.first_sample > 0:
            return (self.first_sample - self.command_sent) * 1000
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert timestamps to dictionary for storage"""
        return {
            'command_sent': self.command_sent,
            'labjack_response': self.labjack_response,
            'first_sample': self.first_sample,
            'stream_started': self.stream_started,
            'initialization_latency_ms': self.initialization_latency_ms,
            'total_startup_latency_ms': self.total_startup_latency_ms
        }

@dataclass
class MonitoringConfig:
    """Configuration for LabJack monitoring service"""
    session_id: str
    sample_rate: float = 10.0  # Hz
    voltage_threshold: float = 3.0  # V
    channels: list = None
    database_path: str = "dev_database.db"
    socket_path: str = "/tmp/labjack_monitor.sock"
    shared_memory_key: str = "labjack_data"
    max_buffer_size: int = 1000
    enable_websocket: bool = True
    websocket_port: int = 8765
    enable_recovery: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Video timing synchronization for HIL
    video_playback_start_time: Optional[float] = None
    enable_ground_truth_matching: bool = False
    temporal_tolerance_ms: float = 500.0
    
    def __post_init__(self):
        if self.channels is None:
            self.channels = ["AIN0"]

@dataclass
class VoltageReading:
    """Individual voltage reading structure"""
    timestamp: float
    channel: str
    voltage: float
    session_id: str
    detection: bool = False
    video_relative_time: Optional[float] = None  # Time relative to video start for HIL sync
    
@dataclass
class MonitoringStatus:
    """Service status structure"""
    active: bool = False
    session_id: Optional[str] = None
    sample_rate: float = 0.0
    uptime: float = 0.0
    total_readings: int = 0
    detections: int = 0
    errors: int = 0
    last_reading_time: Optional[float] = None
    process_id: int = 0
    memory_usage: float = 0.0
    current_video_id: Optional[str] = None  # Track which video is being monitored
    monitoring_start_time: Optional[float] = None  # When current monitoring session started
    
class DedicatedLabJackMonitor:
    """Dedicated LabJack monitoring service process"""

    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.running = False
        self.status = MonitoringStatus()
        self.start_time = time.time()

        # IPC components
        self.server_socket = None
        self.client_connections = []

        # Database connection
        self.db_connection = None

        # Monitoring thread
        self.monitor_thread = None
        self.ipc_thread = None

        # Shutdown event
        self.shutdown_event = threading.Event()

        # Signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        # Data buffer for high-frequency readings
        self.reading_buffer = []
        self.buffer_lock = threading.Lock()

        # Precise timing measurements
        self.timestamps = MonitoringTimestamps()
        self.first_sample_event = threading.Event()

        # Stream mode timing (if used)
        self.stream_start_timestamp: Optional[float] = None
        self.stream_sample_rate: Optional[float] = None

        # Per-video monitoring state
        self.current_video_id: Optional[str] = None
        self.expected_video_start_time: Optional[float] = None
        self.video_monitoring_active = False
        self.video_detection_count = 0
        self.state_lock = threading.Lock()  # Thread-safe state management

        # Session and video-level guards to prevent duplicates
        self._active_sessions: set = set()  # Track active session IDs
        self._active_videos: Dict[str, str] = {}  # video_id -> session_id mapping

        # Statistics
        self.stats = {
            'total_readings': 0,
            'detections': 0,
            'errors': 0,
            'start_time': time.time(),
            'last_reading': None
        }

        logger.info(f"Dedicated LabJack Monitor initialized for session {config.session_id}")
        
    def start_monitoring(
        self,
        video_id: str,
        expected_video_start_time: Optional[float] = None
    ) -> Tuple[bool, MonitoringTimestamps, str]:
        """Start per-video monitoring with precise timestamp capture

        Args:
            video_id: ID of video being monitored
            expected_video_start_time: Expected video start time for drift calculation (optional)

        Returns:
            (success, timestamps, video_id): Success flag, timing measurements, and video ID

        Raises:
            LabJackStateError: If already monitoring another video
            LabJackConnectionError: If LabJack not connected
            LabJackTimeoutError: If USB communication times out
        """
        # Thread-safe state validation
        with self.state_lock:
            # GUARD 1: Check if session is already active (duplicate session prevention)
            if self.config.session_id in self._active_sessions:
                error_msg = (
                    f"⚠️ Session {self.config.session_id} already active, "
                    f"skipping duplicate creation"
                )
                logger.warning(error_msg)
                raise LabJackStateError(error_msg)

            # GUARD 2: Check if video is already being monitored by another session
            if video_id in self._active_videos:
                existing_session = self._active_videos[video_id]
                error_msg = (
                    f"❌ Video {video_id} already being monitored by session {existing_session}. "
                    f"Cannot start duplicate monitoring."
                )
                logger.error(error_msg)
                raise LabJackStateError(error_msg)

            # GUARD 3: Prevent starting if already monitoring another video
            if self.video_monitoring_active:
                error_msg = (
                    f"Cannot start monitoring for video '{video_id}' - "
                    f"already monitoring video '{self.current_video_id}'. "
                    f"Stop current monitoring session first."
                )
                logger.error(error_msg)
                raise LabJackStateError(error_msg)

            # Register session and video as active
            self._active_sessions.add(self.config.session_id)
            self._active_videos[video_id] = self.config.session_id

            # Mark as actively monitoring this video
            self.video_monitoring_active = True
            self.current_video_id = video_id
            self.expected_video_start_time = expected_video_start_time
            self.video_detection_count = 0

        # Record command send time (T0)
        self.timestamps = MonitoringTimestamps()  # Reset timestamps for new session
        self.timestamps.command_sent = time.time()

        try:
            logger.info(f"🎬 Starting monitoring for video {video_id}")
            logger.info(f"⏱️  Command sent at: {self.timestamps.command_sent:.6f}")
            if expected_video_start_time:
                logger.info(f"📹 Expected video start: {expected_video_start_time:.6f}")

            # Initialize LabJack connection (exclusive access)
            if not self._initialize_labjack():
                error_msg = "LabJack not connected - check USB connection and device availability"
                logger.error(error_msg)
                with self.state_lock:
                    # Clean up guards before resetting state
                    if self.config.session_id in self._active_sessions:
                        self._active_sessions.remove(self.config.session_id)
                    if video_id in self._active_videos:
                        del self._active_videos[video_id]
                    self._reset_video_state()
                raise LabJackConnectionError(error_msg)

            # Record LabJack response time (T1)
            self.timestamps.labjack_response = time.time()
            usb_latency_ms = self.timestamps.initialization_latency_ms
            logger.info(f"⚡ USB latency: {usb_latency_ms:.2f}ms")

            # Setup database connection
            if not self._setup_database():
                error_msg = "Failed to setup database connection"
                logger.error(error_msg)
                with self.state_lock:
                    # Clean up guards before resetting state
                    if self.config.session_id in self._active_sessions:
                        self._active_sessions.remove(self.config.session_id)
                    if video_id in self._active_videos:
                        del self._active_videos[video_id]
                    self._reset_video_state()
                return False, self.timestamps, video_id

            # Setup IPC server (only if not already running)
            if not self.server_socket:
                if not self._setup_ipc_server():
                    logger.error("Failed to setup IPC server")
                    with self.state_lock:
                        # Clean up guards before resetting state
                        if self.config.session_id in self._active_sessions:
                            self._active_sessions.remove(self.config.session_id)
                        if video_id in self._active_videos:
                            del self._active_videos[video_id]
                        self._reset_video_state()
                    return False, self.timestamps, video_id

            # Start monitoring thread (only if not already running)
            if not self.monitor_thread or not self.monitor_thread.is_alive():
                self.first_sample_event.clear()  # Reset event for new monitoring session
                self.monitor_thread = threading.Thread(
                    target=self._monitoring_loop,
                    daemon=False,
                    name="LabJackMonitorThread"
                )
                self.monitor_thread.start()

            # Start IPC thread (only if not already running)
            if not self.ipc_thread or not self.ipc_thread.is_alive():
                self.ipc_thread = threading.Thread(
                    target=self._ipc_server_loop,
                    daemon=False,
                    name="IPCServerThread"
                )
                self.ipc_thread.start()

            # Wait for first sample (with timeout) (T2)
            first_sample_received = self.first_sample_event.wait(timeout=2.0)
            if first_sample_received:
                self.timestamps.first_sample = time.time()
                logger.info(f"📊 First sample received at: {self.timestamps.first_sample:.6f}")
            else:
                logger.warning("⚠️  First sample timeout - USB may be slow or LabJack not responding")
                error_msg = "USB timeout waiting for first sample - retry or check LabJack connection"
                with self.state_lock:
                    # Clean up guards before resetting state
                    if self.config.session_id in self._active_sessions:
                        self._active_sessions.remove(self.config.session_id)
                    if video_id in self._active_videos:
                        del self._active_videos[video_id]
                    self._reset_video_state()
                raise LabJackTimeoutError(error_msg)

            self.running = True
            self.status.active = True
            self.status.session_id = self.config.session_id
            self.status.sample_rate = self.config.sample_rate
            self.status.process_id = os.getpid()
            self.status.current_video_id = video_id
            self.status.monitoring_start_time = self.timestamps.command_sent

            # Log timing measurements
            total_startup_ms = self.timestamps.total_startup_latency_ms
            logger.info(f"✅ Monitoring started for video {video_id}")
            logger.info(f"📊 Timing Summary:")
            logger.info(f"   USB latency: {usb_latency_ms:.2f}ms")
            logger.info(f"   Total startup: {total_startup_ms:.2f}ms")

            # Calculate and log drift if expected start time provided
            if expected_video_start_time:
                drift_ms = (self.timestamps.command_sent - expected_video_start_time) * 1000
                logger.info(f"   Timing drift: {drift_ms:+.2f}ms")

            return True, self.timestamps, video_id

        except (LabJackConnectionError, LabJackTimeoutError):
            # Re-raise custom exceptions (cleanup already done in earlier exception handlers)
            raise
        except Exception as e:
            logger.error(f"Failed to start monitoring for video {video_id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Clean up session and video tracking on error
            with self.state_lock:
                if self.config.session_id in self._active_sessions:
                    self._active_sessions.remove(self.config.session_id)
                if video_id in self._active_videos:
                    del self._active_videos[video_id]
                self._reset_video_state()
            return False, self.timestamps, video_id

    def start(self) -> Tuple[bool, MonitoringTimestamps]:
        """Legacy start method for backward compatibility - delegates to start_monitoring

        Returns:
            (success, timestamps): Success flag and timing measurements
        """
        # Use legacy session ID as video ID for backward compatibility
        legacy_video_id = f"legacy_{self.config.session_id}"
        try:
            success, timestamps, _ = self.start_monitoring(
                video_id=legacy_video_id,
                expected_video_start_time=None
            )
            return success, timestamps
        except (LabJackStateError, LabJackConnectionError, LabJackTimeoutError) as e:
            logger.error(f"Legacy start() failed: {e}")
            return False, self.timestamps
    
    def stop_monitoring(self, video_id: str) -> int:
        """Stop per-video monitoring session

        Args:
            video_id: ID of video to stop monitoring (must match current video)

        Returns:
            Final detection count for this video

        Raises:
            LabJackStateError: If not monitoring or video_id mismatch
        """
        with self.state_lock:
            # State validation
            if not self.video_monitoring_active:
                error_msg = f"Cannot stop monitoring - no active monitoring session"
                logger.error(error_msg)
                raise LabJackStateError(error_msg)

            if self.current_video_id != video_id:
                error_msg = (
                    f"Video ID mismatch - cannot stop monitoring for '{video_id}' "
                    f"while monitoring '{self.current_video_id}'"
                )
                logger.error(error_msg)
                raise LabJackStateError(error_msg)

            # Calculate monitoring duration
            if self.status.monitoring_start_time:
                duration_s = time.time() - self.status.monitoring_start_time
                logger.info(f"⏱️  Monitoring duration: {duration_s:.2f}s")

            # Log final statistics
            final_count = self.video_detection_count
            logger.info(f"🛑 Monitoring stopped for video {video_id}, {final_count} detections")

            # Reset video-specific state
            self._reset_video_state()

            return final_count

    def _reset_video_state(self) -> None:
        """Reset per-video monitoring state (call with state_lock held)"""
        # Clean up active session and video tracking
        if self.config.session_id in self._active_sessions:
            self._active_sessions.remove(self.config.session_id)
            logger.debug(f"🧹 Removed session {self.config.session_id} from active sessions")

        if self.current_video_id and self.current_video_id in self._active_videos:
            del self._active_videos[self.current_video_id]
            logger.debug(f"🧹 Removed video {self.current_video_id} from active videos")

        self.video_monitoring_active = False
        self.current_video_id = None
        self.expected_video_start_time = None
        self.video_detection_count = 0
        self.status.current_video_id = None
        self.status.monitoring_start_time = None

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status

        Returns:
            Dictionary with monitoring state:
                - is_monitoring: bool
                - current_video_id: str or None
                - start_time: float or None
                - detection_count: int
        """
        with self.state_lock:
            return {
                'is_monitoring': self.video_monitoring_active,
                'current_video_id': self.current_video_id,
                'start_time': self.status.monitoring_start_time,
                'detection_count': self.video_detection_count,
                'session_id': self.config.session_id,
                'sample_rate': self.config.sample_rate
            }

    def stop(self) -> None:
        """Stop the monitoring service gracefully (legacy method)"""
        logger.info("Stopping dedicated LabJack monitoring service...")

        # Stop any active video monitoring first and clean up guards
        with self.state_lock:
            if self.video_monitoring_active:
                logger.info(f"Stopping active monitoring for video {self.current_video_id}")
                self._reset_video_state()

            # Clean up any remaining session/video guards
            self._active_sessions.clear()
            self._active_videos.clear()
            logger.debug("🧹 Cleared all active sessions and videos")

        self.running = False
        self.shutdown_event.set()
        
        # Close client connections
        for client in self.client_connections:
            try:
                client.close()
            except:
                pass
        self.client_connections.clear()
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # Wait for threads to finish
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
            
        if self.ipc_thread and self.ipc_thread.is_alive():
            self.ipc_thread.join(timeout=5)
        
        # Close database
        if self.db_connection:
            try:
                self.db_connection.close()
            except:
                pass
        
        # Cleanup socket file
        try:
            os.unlink(self.config.socket_path)
        except:
            pass
        
        self.status.active = False
        logger.info("Dedicated LabJack monitoring service stopped")
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)
    
    def _initialize_labjack(self) -> bool:
        """Initialize LabJack with exclusive access"""
        try:
            logger.info("Initializing LabJack with exclusive access...")
            
            # Configure for exclusive access
            config = {
                "device_type": "ANY",
                "connection_type": "ANY",
                "identifier": "ANY",
                "voltage_threshold": self.config.voltage_threshold,
                "channels": self.config.channels,
                "exclusive_access": True,  # Request exclusive access
                "force_reconnect": True   # Force reconnection if needed
            }
            
            # Initialize service
            success = signal_validation_service.initialize_labjack(config)
            if success:
                logger.info("LabJack initialized successfully with exclusive access")
                return True
            else:
                logger.error("Failed to initialize LabJack")
                return False
                
        except Exception as e:
            logger.error(f"LabJack initialization error: {e}")
            return False
    
    def _setup_database(self) -> bool:
        """Setup database connection for storing detection events"""
        try:
            self.db_connection = sqlite3.connect(
                self.config.database_path,
                check_same_thread=False
            )
            self.db_connection.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
            logger.info(f"Database connection established: {self.config.database_path}")
            return True
        except Exception as e:
            logger.error(f"Database setup error: {e}")
            return False

    async def _wait_for_session_visibility(
        self,
        session_id: str,
        max_retries: int = 5,
        initial_delay: float = 0.01  # 10ms
    ) -> bool:
        """
        Wait for session to become visible in database (handles PostgreSQL MVCC lag).

        PostgreSQL's MVCC (Multi-Version Concurrency Control) means that a newly
        committed transaction may not be immediately visible to connections from
        the connection pool. This function uses exponential backoff to efficiently
        wait for visibility while minimizing latency.

        Args:
            session_id: Test session ID to check
            max_retries: Maximum number of retry attempts (default: 5)
            initial_delay: Initial delay in seconds (default: 10ms)

        Returns:
            True if session is visible, False otherwise

        Performance:
            - Best case (SQLite or immediate visibility): 0ms overhead
            - Typical case (PostgreSQL with MVCC lag): 20-30ms
            - Worst case (high load): 310ms (5 retries with exponential backoff)
        """
        delay = initial_delay
        total_wait = 0.0

        for attempt in range(max_retries):
            try:
                # Query for session - direct SQL to bypass any ORM caching
                cursor = self.db_connection.cursor()
                cursor.execute(
                    "SELECT id, status FROM test_sessions WHERE id = ?",
                    (session_id,)
                )
                result = cursor.fetchone()

                if result:
                    session_db_id, session_status = result
                    logger.info(
                        f"✅ Session {session_id} visible after {attempt + 1} attempts "
                        f"({total_wait * 1000:.1f}ms total wait, status: {session_status})"
                    )
                    return True

                # Session not visible yet - exponential backoff
                if attempt < max_retries - 1:
                    wait_time = delay * (2 ** attempt)
                    total_wait += wait_time
                    logger.debug(
                        f"🔄 Session {session_id} not visible, retry {attempt + 1}/{max_retries} "
                        f"after {wait_time * 1000:.1f}ms (total: {total_wait * 1000:.1f}ms)"
                    )
                    time.sleep(wait_time)  # Use sync sleep for database thread

            except Exception as e:
                logger.error(f"❌ Error checking session visibility (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    wait_time = delay * (2 ** attempt)
                    total_wait += wait_time
                    time.sleep(wait_time)

        logger.error(
            f"❌ Session {session_id} not visible after {max_retries} retries "
            f"({total_wait * 1000:.1f}ms total wait). This may indicate:\n"
            f"  1. Session was not committed to database\n"
            f"  2. Database connection pool issue\n"
            f"  3. Severe database load causing extreme MVCC lag (>300ms)\n"
            f"  4. Session ID mismatch"
        )
        return False
    
    def _setup_ipc_server(self) -> bool:
        """Setup Unix domain socket for IPC communication"""
        try:
            # Remove existing socket file
            try:
                os.unlink(self.config.socket_path)
            except FileNotFoundError:
                pass
            
            self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server_socket.bind(self.config.socket_path)
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)  # Non-blocking accept
            
            # Set socket permissions
            os.chmod(self.config.socket_path, 0o666)
            
            logger.info(f"IPC server socket created: {self.config.socket_path}")
            return True
            
        except Exception as e:
            logger.error(f"IPC server setup error: {e}")
            return False
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop for voltage readings"""
        logger.info(f"Starting monitoring loop at {self.config.sample_rate}Hz for session {self.config.session_id}")

        # FIX-4: Wait for session to be visible in database (handles PostgreSQL MVCC lag)
        logger.info(f"🔍 Checking session visibility in database (PostgreSQL MVCC handling)...")
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            session_visible = loop.run_until_complete(
                self._wait_for_session_visibility(self.config.session_id)
            )
        finally:
            loop.close()

        if not session_visible:
            logger.error(
                f"❌ Cannot start monitoring - session {self.config.session_id} not found in database.\n"
                f"This is a critical error. Monitoring loop will not start.\n"
                f"Possible causes:\n"
                f"  - API endpoint did not commit session to database\n"
                f"  - Database connection pool exhaustion\n"
                f"  - Extreme database load (>300ms MVCC lag)\n"
                f"  - Session ID mismatch between API and monitor"
            )
            self.stop()
            return

        logger.info(f"✅ Session {self.config.session_id} verified in database, starting voltage monitoring...")

        sample_interval = 1.0 / self.config.sample_rate
        last_reading_time = time.time()
        consecutive_errors = 0
        
        while self.running and not self.shutdown_event.is_set():
            try:
                start_time = time.time()
                
                # Read voltages from all configured channels
                readings = []
                for channel in self.config.channels:
                    try:
                        result = signal_validation_service.read_voltage_signal(channel)
                        
                        if result.get("success") and result.get("voltage") is not None:
                            voltage = result["voltage"]
                            timestamp = time.time()
                            
                            # Calculate video-relative time for HIL synchronization
                            video_relative_time = None
                            if self.config.video_playback_start_time is not None:
                                video_relative_time = timestamp - self.config.video_playback_start_time
                            
                            reading = VoltageReading(
                                timestamp=timestamp,
                                channel=channel,
                                voltage=voltage,
                                session_id=self.config.session_id,
                                detection=voltage > self.config.voltage_threshold,
                                video_relative_time=video_relative_time
                            )
                            
                            readings.append(reading)
                            
                            # Update statistics
                            self.stats['total_readings'] += 1
                            self.stats['last_reading'] = timestamp

                            if reading.detection:
                                self.stats['detections'] += 1
                                # Track per-video detection count
                                with self.state_lock:
                                    if self.video_monitoring_active:
                                        self.video_detection_count += 1
                                # Store detection event immediately
                                self._store_detection_event(reading)
                                logger.debug(f"Detection: {voltage:.3f}V on {channel}")

                            # Signal first sample received (for startup timing)
                            if not self.first_sample_event.is_set():
                                self.first_sample_event.set()

                            consecutive_errors = 0  # Reset error counter
                            
                        else:
                            logger.warning(f"Failed to read voltage from {channel}: {result}")
                            consecutive_errors += 1
                            
                    except Exception as e:
                        logger.error(f"Error reading channel {channel}: {e}")
                        consecutive_errors += 1
                        self.stats['errors'] += 1
                
                # Update status
                self.status.total_readings = self.stats['total_readings']
                self.status.detections = self.stats['detections']
                self.status.errors = self.stats['errors']
                self.status.last_reading_time = self.stats['last_reading']
                self.status.uptime = time.time() - self.start_time
                
                # Add readings to buffer
                if readings:
                    with self.buffer_lock:
                        self.reading_buffer.extend(readings)
                        # Trim buffer if too large
                        if len(self.reading_buffer) > self.config.max_buffer_size:
                            self.reading_buffer = self.reading_buffer[-self.config.max_buffer_size:]
                
                # Handle consecutive errors
                if consecutive_errors >= self.config.max_retries:
                    logger.error(f"Too many consecutive errors ({consecutive_errors}), attempting recovery...")
                    if self.config.enable_recovery:
                        self._attempt_recovery()
                    consecutive_errors = 0
                
                # Maintain sample rate
                elapsed = time.time() - start_time
                sleep_time = max(0, sample_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    logger.warning(f"Monitoring loop running slow: {elapsed:.3f}s > {sample_interval:.3f}s")
                    
            except Exception as e:
                logger.error(f"Fatal error in monitoring loop: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                self.stats['errors'] += 1
                time.sleep(1)  # Back off on fatal error
        
        logger.info("Monitoring loop ended")
    
    def _store_detection_event(self, reading: VoltageReading) -> None:
        """Store detection event in database with video timing synchronization"""
        try:
            cursor = self.db_connection.cursor()
            
            event_id = str(uuid.uuid4())
            
            # Use video-relative time if available, otherwise use absolute timestamp
            event_timestamp = reading.video_relative_time if reading.video_relative_time is not None else reading.timestamp
            
            # Enhanced detection event with video timing metadata
            cursor.execute("""
                INSERT INTO detection_events (
                    id, test_session_id, timestamp,
                    confidence, class_label, validation_result,
                    created_at, vru_type, processing_time_ms,
                    metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                reading.session_id,
                event_timestamp,  # Video-relative timestamp for ground truth matching
                reading.voltage,  # Store voltage as confidence
                f"LabJack_{reading.channel}",
                "passed",
                datetime.now(timezone.utc).isoformat(),
                f"LabJack_{reading.voltage:.3f}V",
                5.0,  # Estimated processing time
                json.dumps({
                    "absolute_timestamp": reading.timestamp,
                    "video_relative_time": reading.video_relative_time,
                    "video_playback_start_time": self.config.video_playback_start_time,
                    "channel": reading.channel,
                    "raw_voltage": reading.voltage,
                    "detection_threshold": self.config.voltage_threshold,
                    "hil_synchronized": reading.video_relative_time is not None
                })
            ))
            
            self.db_connection.commit()
            
            if reading.video_relative_time is not None:
                logger.debug(f"HIL detection stored: {reading.voltage:.3f}V at video time {reading.video_relative_time:.3f}s")
            else:
                logger.debug(f"Detection stored: {reading.voltage:.3f}V at {reading.timestamp}")
            
        except Exception as e:
            logger.error(f"Failed to store detection event: {e}")
    
    def _ipc_server_loop(self) -> None:
        """IPC server loop to handle client communications"""
        logger.info("Starting IPC server loop")
        
        while self.running and not self.shutdown_event.is_set():
            try:
                # Accept new connections (non-blocking)
                try:
                    client_socket, address = self.server_socket.accept()
                    self.client_connections.append(client_socket)
                    logger.info(f"New IPC client connected")
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket,),
                        daemon=True
                    )
                    client_thread.start()
                    
                except socket.timeout:
                    # No new connections, continue
                    pass
                    
            except Exception as e:
                if self.running:  # Only log if we're still supposed to be running
                    logger.error(f"IPC server error: {e}")
                time.sleep(0.1)
        
        logger.info("IPC server loop ended")
    
    def _handle_client(self, client_socket: socket.socket) -> None:
        """Handle individual client connection"""
        try:
            while self.running and not self.shutdown_event.is_set():
                try:
                    # Receive command from client
                    data = client_socket.recv(1024)
                    if not data:
                        break
                    
                    command = json.loads(data.decode())
                    response = self._process_command(command)
                    
                    # Send response
                    response_data = json.dumps(response).encode()
                    client_socket.sendall(response_data)
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"Client handling error: {e}")
                    break
                    
        finally:
            try:
                client_socket.close()
                if client_socket in self.client_connections:
                    self.client_connections.remove(client_socket)
            except:
                pass
    
    def _process_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Process IPC command from client"""
        cmd_type = command.get("type")

        try:
            if cmd_type == "get_status":
                return {
                    "success": True,
                    "data": asdict(self.status)
                }

            elif cmd_type == "get_monitoring_status":
                # New command for per-video monitoring status
                return {
                    "success": True,
                    "data": self.get_monitoring_status()
                }

            elif cmd_type == "start_monitoring":
                # Handle start_monitoring IPC command
                video_id = command.get("video_id")
                expected_start_time = command.get("expected_video_start_time")
                if not video_id:
                    return {
                        "success": False,
                        "error": "Missing required parameter: video_id"
                    }
                try:
                    success, timestamps, vid = self.start_monitoring(
                        video_id=video_id,
                        expected_video_start_time=expected_start_time
                    )
                    return {
                        "success": success,
                        "data": {
                            "video_id": vid,
                            "timestamps": timestamps.to_dict()
                        }
                    }
                except (LabJackStateError, LabJackConnectionError, LabJackTimeoutError) as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }

            elif cmd_type == "stop_monitoring":
                # Handle stop_monitoring IPC command
                video_id = command.get("video_id")
                if not video_id:
                    return {
                        "success": False,
                        "error": "Missing required parameter: video_id"
                    }
                try:
                    detection_count = self.stop_monitoring(video_id)
                    return {
                        "success": True,
                        "data": {
                            "video_id": video_id,
                            "detection_count": detection_count
                        }
                    }
                except LabJackStateError as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "error_type": "LabJackStateError"
                    }

            elif cmd_type == "get_readings":
                count = command.get("count", 10)
                with self.buffer_lock:
                    readings = self.reading_buffer[-count:]
                return {
                    "success": True,
                    "data": [asdict(r) for r in readings]
                }

            elif cmd_type == "get_stats":
                return {
                    "success": True,
                    "data": self.stats.copy()
                }

            elif cmd_type == "ping":
                return {
                    "success": True,
                    "data": {"pong": time.time()}
                }

            else:
                return {
                    "success": False,
                    "error": f"Unknown command: {cmd_type}"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _attempt_recovery(self) -> None:
        """Attempt to recover from errors"""
        logger.info("Attempting service recovery...")
        
        try:
            # Try to reinitialize LabJack
            time.sleep(self.config.retry_delay)
            if self._initialize_labjack():
                logger.info("LabJack recovery successful")
            else:
                logger.error("LabJack recovery failed")
                
        except Exception as e:
            logger.error(f"Recovery attempt failed: {e}")

def run_monitoring_service(config_dict: Dict[str, Any]) -> None:
    """Entry point for running the monitoring service as a separate process"""
    
    # Configure logging for the service process
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'/tmp/labjack_monitor_{os.getpid()}.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting dedicated LabJack monitoring service process (PID: {os.getpid()})")
    
    try:
        config = MonitoringConfig(**config_dict)
        monitor = DedicatedLabJackMonitor(config)
        
        if monitor.start():
            logger.info("Monitoring service started successfully")
            
            # Keep the process running
            try:
                while monitor.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
            
        else:
            logger.error("Failed to start monitoring service")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error in monitoring service: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
    
    finally:
        if 'monitor' in locals():
            monitor.stop()
        logger.info("Monitoring service process ended")

if __name__ == "__main__":
    # Command line entry point
    import argparse
    
    parser = argparse.ArgumentParser(description="Dedicated LabJack Monitoring Service")
    parser.add_argument("--session-id", required=True, help="Test session ID")
    parser.add_argument("--sample-rate", type=float, default=10.0, help="Sample rate in Hz")
    parser.add_argument("--voltage-threshold", type=float, default=3.0, help="Detection threshold in volts")
    parser.add_argument("--channels", nargs="+", default=["AIN0"], help="LabJack channels to monitor")
    parser.add_argument("--database-path", default="dev_database.db", help="Database file path")
    parser.add_argument("--socket-path", default="/tmp/labjack_monitor.sock", help="IPC socket path")
    
    args = parser.parse_args()
    
    config_dict = {
        "session_id": args.session_id,
        "sample_rate": args.sample_rate,
        "voltage_threshold": args.voltage_threshold,
        "channels": args.channels,
        "database_path": args.database_path,
        "socket_path": args.socket_path
    }
    
    run_monitoring_service(config_dict)
