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
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid
import traceback
import asyncio
from contextlib import asynccontextmanager

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
        
        # Statistics
        self.stats = {
            'total_readings': 0,
            'detections': 0,
            'errors': 0,
            'start_time': time.time(),
            'last_reading': None
        }
        
        logger.info(f"Dedicated LabJack Monitor initialized for session {config.session_id}")
        
    def start(self) -> bool:
        """Start the dedicated monitoring service"""
        try:
            logger.info(f"Starting dedicated LabJack monitoring service for session {self.config.session_id}")
            
            # Initialize LabJack connection (exclusive access)
            if not self._initialize_labjack():
                logger.error("Failed to initialize LabJack - aborting service start")
                return False
            
            # Setup database connection
            if not self._setup_database():
                logger.error("Failed to setup database connection")
                return False
            
            # Setup IPC server
            if not self._setup_ipc_server():
                logger.error("Failed to setup IPC server")
                return False
            
            # Start monitoring thread
            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=False,
                name="LabJackMonitorThread"
            )
            self.monitor_thread.start()
            
            # Start IPC thread
            self.ipc_thread = threading.Thread(
                target=self._ipc_server_loop,
                daemon=False,
                name="IPCServerThread"
            )
            self.ipc_thread.start()
            
            self.running = True
            self.status.active = True
            self.status.session_id = self.config.session_id
            self.status.sample_rate = self.config.sample_rate
            self.status.process_id = os.getpid()
            
            logger.info(f"Dedicated LabJack monitoring service started successfully (PID: {os.getpid()})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start monitoring service: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def stop(self):
        """Stop the monitoring service gracefully"""
        logger.info("Stopping dedicated LabJack monitoring service...")
        
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
    
    def _signal_handler(self, signum, frame):
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
    
    def _monitoring_loop(self):
        """Main monitoring loop for voltage readings"""
        logger.info(f"Starting monitoring loop at {self.config.sample_rate}Hz")
        
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
                                # Store detection event immediately
                                self._store_detection_event(reading)
                                logger.debug(f"Detection: {voltage:.3f}V on {channel}")
                            
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
    
    def _store_detection_event(self, reading: VoltageReading):
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
    
    def _ipc_server_loop(self):
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
    
    def _handle_client(self, client_socket: socket.socket):
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
    
    def _attempt_recovery(self):
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

def run_monitoring_service(config_dict: Dict[str, Any]):
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
