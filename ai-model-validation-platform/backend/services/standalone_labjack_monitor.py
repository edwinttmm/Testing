#!/usr/bin/env python3
"""
Standalone LabJack Monitoring Service

This service runs as a separate process with exclusive LabJack access and provides:
- Continuous monitoring at configurable sample rates (default 10Hz)
- IPC command interface for start/stop/status operations  
- Direct SQLite database storage for detection events
- Health monitoring and error recovery
- Signal handling for graceful shutdown
- Comprehensive logging and configuration management

Author: AI Model Validation Platform Team
Version: 1.0.0
"""

import asyncio
import logging
import signal
import sqlite3
import sys
import threading
import time
import json
import uuid
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import queue
import socket
import struct
import traceback

# Configure logging
def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Setup comprehensive logging configuration"""
    logger = logging.getLogger("labjack_monitor")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [PID:%(process)d] - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger

@dataclass
class MonitoringConfig:
    """Configuration for LabJack monitoring"""
    sample_rate_hz: float = 20.0  # Increased for better coverage
    voltage_threshold: float = 3.3  # TTL HIGH threshold - anything above this is recorded
    labjack_channel: str = "AIN0"
    database_path: str = "dev_database.db"
    ipc_port: int = 8765
    ipc_host: str = "localhost"
    max_detection_rate: float = 100.0  # Max detections per second
    health_check_interval: float = 30.0  # Health check every 30 seconds
    log_level: str = "INFO"
    log_file: Optional[str] = None
    recovery_retry_count: int = 3
    recovery_delay_seconds: float = 1.0

@dataclass
class DetectionEvent:
    """LabJack detection event data structure"""
    id: str
    test_session_id: str
    timestamp: float
    voltage: float
    channel: str
    latency_ms: float
    created_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class MonitoringStatus:
    """Current monitoring status"""
    active: bool
    session_id: Optional[str]
    sample_rate_hz: float
    total_detections: int
    detection_rate: float
    last_detection_time: Optional[float]
    uptime_seconds: float
    health_status: str
    last_error: Optional[str]
    error_count: int

@dataclass
class HealthMetrics:
    """Health monitoring metrics"""
    cpu_usage: float
    memory_usage_mb: float
    disk_space_mb: float
    network_latency_ms: float
    labjack_connection_ok: bool
    database_connection_ok: bool
    last_successful_sample: Optional[float]
    errors_per_minute: float

class LabJackInterface:
    """Interface for LabJack hardware with error handling and recovery"""
    
    def __init__(self, config: MonitoringConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.ljm = None
        self.handle = None
        self.connected = False
        self.retry_count = 0
        
    def connect(self) -> bool:
        """Connect to LabJack device with retry logic"""
        try:
            # Try to import LabJack LJM library
            try:
                import labjack.ljm as ljm
                self.ljm = ljm
            except ImportError:
                self.logger.error("LabJack LJM library not available - running in simulation mode")
                return self._setup_simulation_mode()
            
            # Attempt connection
            for attempt in range(self.config.recovery_retry_count):
                try:
                    self.handle = self.ljm.openS("ANY", "ANY", "ANY")
                    device_type = self.ljm.eReadName(self.handle, "DEVICE_NAME_DEFAULT")
                    self.logger.info(f"✅ Connected to LabJack device: {device_type}")
                    self.connected = True
                    self.retry_count = 0
                    return True
                    
                except Exception as e:
                    self.logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                    if attempt < self.config.recovery_retry_count - 1:
                        time.sleep(self.config.recovery_delay_seconds)
                    
            self.logger.error("Failed to connect to LabJack after all retries - using simulation mode")
            return self._setup_simulation_mode()
            
        except Exception as e:
            self.logger.error(f"Critical error in LabJack connection: {e}")
            return False
    
    def _setup_simulation_mode(self) -> bool:
        """Setup simulation mode when real hardware unavailable"""
        self.logger.info("🔄 Setting up LabJack simulation mode")
        self.connected = True
        self.simulation_mode = True
        return True
        
    def read_voltage(self, channel: str) -> Optional[float]:
        """Read voltage from specified channel"""
        try:
            if hasattr(self, 'simulation_mode'):
                # Simulation: return random voltage with occasional high values
                import random
                base_voltage = 0.1 + random.random() * 0.5
                if random.random() < 0.05:  # 5% chance of detection signal
                    return 3.5 + random.random() * 1.0  # 3.5-4.5V
                return base_voltage
                
            if not self.connected or not self.handle:
                return None
                
            voltage = self.ljm.eReadName(self.handle, channel)
            return float(voltage)
            
        except Exception as e:
            self.logger.error(f"Error reading voltage from {channel}: {e}")
            self.retry_count += 1
            if self.retry_count > self.config.recovery_retry_count:
                self.connected = False
            return None
    
    def disconnect(self):
        """Safely disconnect from LabJack"""
        try:
            if self.handle and self.ljm:
                self.ljm.close(self.handle)
                self.logger.info("🔌 LabJack disconnected")
        except Exception as e:
            self.logger.error(f"Error disconnecting LabJack: {e}")
        finally:
            self.connected = False
            self.handle = None

class DatabaseManager:
    """Database operations for detection events"""
    
    def __init__(self, config: MonitoringConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.connection_pool = []
        self._lock = threading.Lock()
        
    @contextmanager
    def get_connection(self):
        """Thread-safe database connection context manager"""
        conn = None
        try:
            conn = sqlite3.connect(
                self.config.database_path,
                timeout=30.0,
                check_same_thread=False
            )
            conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode for better concurrency
            yield conn
        except Exception as e:
            self.logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def store_detection_event(self, event: DetectionEvent) -> bool:
        """Store detection event in database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Insert into detection_events table with proper schema
                cursor.execute("""
                    INSERT INTO detection_events (
                        id, test_session_id, timestamp, 
                        confidence, class_label, validation_result,
                        created_at, vru_type, processing_time_ms,
                        latency_ms, labjack_timestamp, labjack_voltage
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.id,
                    event.test_session_id,
                    event.timestamp,
                    event.voltage,  # Store voltage in confidence field
                    f"LabJack_{event.channel}",  # Channel info in class_label
                    "passed" if event.voltage > self.config.voltage_threshold else "failed",
                    event.created_at,
                    f"LabJack_{event.voltage:.3f}V",  # Voltage info in vru_type
                    event.latency_ms,
                    event.latency_ms,  # Also store in latency_ms field
                    event.timestamp,   # Store in labjack_timestamp
                    event.voltage      # Store in labjack_voltage field
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to store detection event: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test database connectivity"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                return True
        except Exception as e:
            self.logger.error(f"Database connection test failed: {e}")
            return False

class IPCServer:
    """IPC server for command interface"""
    
    def __init__(self, config: MonitoringConfig, logger: logging.Logger, monitor_service):
        self.config = config
        self.logger = logger
        self.monitor_service = monitor_service
        self.server_socket = None
        self.running = False
        
    async def start_server(self):
        """Start IPC server for command interface"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.config.ipc_host, self.config.ipc_port))
            self.server_socket.listen(5)
            self.running = True
            
            self.logger.info(f"🌐 IPC Server listening on {self.config.ipc_host}:{self.config.ipc_port}")
            
            while self.running:
                try:
                    # Use asyncio to handle socket accept
                    client_socket, address = await asyncio.get_event_loop().run_in_executor(
                        None, self.server_socket.accept
                    )
                    
                    # Handle client in background task
                    asyncio.create_task(self.handle_client(client_socket, address))
                    
                except Exception as e:
                    if self.running:
                        self.logger.error(f"Error accepting client connection: {e}")
                        
        except Exception as e:
            self.logger.error(f"Failed to start IPC server: {e}")
    
    async def handle_client(self, client_socket: socket.socket, address):
        """Handle individual client connection"""
        try:
            self.logger.debug(f"Client connected from {address}")
            
            # Receive command
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                return
                
            try:
                command = json.loads(data)
                response = await self.process_command(command)
            except json.JSONDecodeError:
                response = {"error": "Invalid JSON command"}
            
            # Send response
            response_data = json.dumps(response).encode('utf-8')
            client_socket.send(response_data)
            
        except Exception as e:
            self.logger.error(f"Error handling client {address}: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
    
    async def process_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Process IPC command and return response"""
        try:
            cmd_type = command.get("command")
            
            if cmd_type == "start_monitoring":
                session_id = command.get("session_id")
                sample_rate = command.get("sample_rate", self.config.sample_rate_hz)
                
                if not session_id:
                    return {"success": False, "error": "session_id required"}
                
                success = self.monitor_service.start_monitoring(session_id, sample_rate)
                return {"success": success}
                
            elif cmd_type == "stop_monitoring":
                self.monitor_service.stop_monitoring()
                return {"success": True}
                
            elif cmd_type == "get_status":
                status = self.monitor_service.get_status()
                return {"success": True, "status": asdict(status)}
                
            elif cmd_type == "get_health":
                health = self.monitor_service.get_health_metrics()
                return {"success": True, "health": asdict(health)}
                
            elif cmd_type == "shutdown":
                asyncio.create_task(self.monitor_service.shutdown())
                return {"success": True, "message": "Shutdown initiated"}
                
            else:
                return {"success": False, "error": f"Unknown command: {cmd_type}"}
                
        except Exception as e:
            self.logger.error(f"Error processing command: {e}")
            return {"success": False, "error": str(e)}
    
    def stop_server(self):
        """Stop IPC server"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

class StandaloneLabJackMonitor:
    """Main standalone LabJack monitoring service"""
    
    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.logger = setup_logging(config.log_level, config.log_file)
        
        # Core components
        self.labjack = LabJackInterface(config, self.logger)
        self.database = DatabaseManager(config, self.logger)
        self.ipc_server = IPCServer(config, self.logger, self)
        
        # Monitoring state
        self.monitoring_active = False
        self.current_session_id = None
        self.sample_rate_hz = config.sample_rate_hz
        self.total_detections = 0
        self.start_time = time.time()
        self.last_detection_time = None
        self.error_count = 0
        self.last_error = None
        self.detection_times = []  # For rate calculation
        
        # Threading
        self.monitor_thread = None
        self.health_thread = None
        self.stop_event = threading.Event()
        self.shutdown_requested = False
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("🚀 Standalone LabJack Monitor initialized")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"📡 Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        asyncio.create_task(self.shutdown())
    
    async def start(self):
        """Start the monitoring service"""
        try:
            self.logger.info("🎬 Starting Standalone LabJack Monitoring Service")
            
            # Initialize LabJack connection
            if not self.labjack.connect():
                self.logger.error("❌ Failed to initialize LabJack interface")
                return False
            
            # Test database connection
            if not self.database.test_connection():
                self.logger.error("❌ Failed to connect to database")
                return False
            
            # Start health monitoring thread
            self.health_thread = threading.Thread(
                target=self._health_monitor_loop,
                daemon=True
            )
            self.health_thread.start()
            
            # Start IPC server
            await self.ipc_server.start_server()
            
            return True
            
        except Exception as e:
            self.logger.error(f"💥 Failed to start monitoring service: {e}")
            return False
    
    def start_monitoring(self, session_id: str, sample_rate: float = None) -> bool:
        """Start monitoring for a specific session"""
        try:
            if self.monitoring_active:
                self.logger.warning(f"⚠️ Monitoring already active for session {self.current_session_id}")
                return False
            
            self.current_session_id = session_id
            self.sample_rate_hz = sample_rate or self.config.sample_rate_hz
            self.total_detections = 0
            self.detection_times.clear()
            self.monitoring_active = True
            self.stop_event.clear()
            
            # Start monitoring thread
            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                args=(session_id,),
                daemon=True
            )
            self.monitor_thread.start()
            
            self.logger.info(f"📊 Started monitoring for session {session_id} at {self.sample_rate_hz}Hz")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start monitoring: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return False
    
    def stop_monitoring(self):
        """Stop current monitoring session"""
        if not self.monitoring_active:
            return
        
        session_id = self.current_session_id
        self.logger.info(f"⏹️ Stopping monitoring for session {session_id}")
        
        self.monitoring_active = False
        self.stop_event.set()
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        self.logger.info(f"✅ Monitoring stopped for session {session_id}, total detections: {self.total_detections}")
        self.current_session_id = None
    
    def _monitoring_loop(self, session_id: str):
        """Main monitoring loop - runs in separate thread"""
        sample_interval = 1.0 / self.sample_rate_hz
        consecutive_errors = 0
        
        self.logger.info(f"🔄 Starting monitoring loop for session {session_id}")
        
        try:
            while self.monitoring_active and not self.stop_event.is_set():
                loop_start = time.time()
                
                try:
                    # Read voltage from LabJack
                    voltage = self.labjack.read_voltage(self.config.labjack_channel)
                    
                    if voltage is not None:
                        consecutive_errors = 0  # Reset error counter
                        
                        # Check for detection threshold
                        if voltage > self.config.voltage_threshold:
                            detection_time = time.time()
                            
                            # Rate limiting check
                            if self._check_detection_rate_limit():
                                # Create detection event
                                event = DetectionEvent(
                                    id=str(uuid.uuid4()),
                                    test_session_id=session_id,
                                    timestamp=detection_time,
                                    voltage=voltage,
                                    channel=self.config.labjack_channel,
                                    latency_ms=5.0,  # Estimated LabJack latency
                                    created_at=datetime.now(timezone.utc).isoformat()
                                )
                                
                                # Store in database
                                if self.database.store_detection_event(event):
                                    self.total_detections += 1
                                    self.last_detection_time = detection_time
                                    self.detection_times.append(detection_time)
                                    
                                    # Log detection (throttled)
                                    if self.total_detections <= 10 or self.total_detections % 10 == 0:
                                        self.logger.info(f"📈 Detection #{self.total_detections}: {voltage:.3f}V")
                                else:
                                    self.logger.error("❌ Failed to store detection event")
                            else:
                                self.logger.warning(f"⚠️ Detection rate limit exceeded, dropping detection")
                    else:
                        consecutive_errors += 1
                        if consecutive_errors > 5:
                            self.logger.error("❌ Too many consecutive read errors, attempting recovery")
                            if not self.labjack.connect():
                                self.logger.error("💥 Failed to recover LabJack connection")
                                break
                            consecutive_errors = 0
                    
                    # Precise timing control
                    elapsed = time.time() - loop_start
                    sleep_time = max(0, sample_interval - elapsed)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    
                except Exception as e:
                    self.logger.error(f"❌ Error in monitoring loop: {e}")
                    self.error_count += 1
                    self.last_error = str(e)
                    time.sleep(1)  # Back off on error
                    
        except Exception as e:
            self.logger.error(f"💥 Fatal error in monitoring loop: {e}")
            self.last_error = str(e)
            self.error_count += 1
        finally:
            self.monitoring_active = False
            self.logger.info(f"🏁 Monitoring loop ended for session {session_id}")
    
    def _check_detection_rate_limit(self) -> bool:
        """Check if detection rate is within limits"""
        current_time = time.time()
        
        # Remove detections older than 1 second
        self.detection_times = [t for t in self.detection_times if current_time - t <= 1.0]
        
        # Check rate limit
        return len(self.detection_times) < self.config.max_detection_rate
    
    def _health_monitor_loop(self):
        """Health monitoring loop"""
        while not self.shutdown_requested:
            try:
                # Perform health checks
                labjack_ok = self.labjack.connected
                database_ok = self.database.test_connection()
                
                if not labjack_ok:
                    self.logger.warning("⚠️ LabJack connection lost, attempting recovery")
                    labjack_ok = self.labjack.connect()
                
                if not database_ok:
                    self.logger.warning("⚠️ Database connection lost")
                
                # Log health status periodically
                if self.monitoring_active:
                    detection_rate = len([t for t in self.detection_times if time.time() - t <= 60]) / 60.0
                    self.logger.debug(f"💚 Health: LabJack={labjack_ok}, DB={database_ok}, Rate={detection_rate:.1f}/min")
                
                time.sleep(self.config.health_check_interval)
                
            except Exception as e:
                self.logger.error(f"❌ Health monitor error: {e}")
                time.sleep(10)
    
    def get_status(self) -> MonitoringStatus:
        """Get current monitoring status"""
        current_time = time.time()
        uptime = current_time - self.start_time
        
        # Calculate detection rate (detections per second over last minute)
        recent_detections = [t for t in self.detection_times if current_time - t <= 60.0]
        detection_rate = len(recent_detections) / 60.0
        
        # Determine health status
        health_status = "healthy"
        if not self.labjack.connected:
            health_status = "labjack_disconnected"
        elif not self.database.test_connection():
            health_status = "database_error"
        elif self.error_count > 10:
            health_status = "error_threshold_exceeded"
        
        return MonitoringStatus(
            active=self.monitoring_active,
            session_id=self.current_session_id,
            sample_rate_hz=self.sample_rate_hz,
            total_detections=self.total_detections,
            detection_rate=detection_rate,
            last_detection_time=self.last_detection_time,
            uptime_seconds=uptime,
            health_status=health_status,
            last_error=self.last_error,
            error_count=self.error_count
        )
    
    def get_health_metrics(self) -> HealthMetrics:
        """Get detailed health metrics"""
        try:
            import psutil
            process = psutil.Process()
            cpu_usage = process.cpu_percent()
            memory_usage = process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            cpu_usage = 0.0
            memory_usage = 0.0
        
        # Calculate errors per minute
        current_time = time.time()
        recent_errors = self.error_count if self.start_time > current_time - 60 else 0
        
        return HealthMetrics(
            cpu_usage=cpu_usage,
            memory_usage_mb=memory_usage,
            disk_space_mb=0.0,  # TODO: Implement disk space check
            network_latency_ms=0.0,  # TODO: Implement network latency check
            labjack_connection_ok=self.labjack.connected,
            database_connection_ok=self.database.test_connection(),
            last_successful_sample=self.last_detection_time,
            errors_per_minute=recent_errors
        )
    
    async def shutdown(self):
        """Graceful shutdown of the monitoring service"""
        self.logger.info("🔄 Initiating graceful shutdown...")
        
        # Stop monitoring if active
        if self.monitoring_active:
            self.stop_monitoring()
        
        # Stop IPC server
        self.ipc_server.stop_server()
        
        # Disconnect LabJack
        self.labjack.disconnect()
        
        # Set shutdown flag
        self.shutdown_requested = True
        
        self.logger.info("✅ Graceful shutdown completed")

# IPC Client for testing
class IPCClient:
    """Client for communicating with monitoring service"""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
    
    def send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Send command to monitoring service"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            sock.connect((self.host, self.port))
            
            # Send command
            command_data = json.dumps(command).encode('utf-8')
            sock.send(command_data)
            
            # Receive response
            response_data = sock.recv(4096).decode('utf-8')
            response = json.loads(response_data)
            
            sock.close()
            return response
            
        except Exception as e:
            return {"success": False, "error": str(e)}

# Main entry point
async def main():
    """Main entry point for standalone service"""
    parser = argparse.ArgumentParser(description="Standalone LabJack Monitoring Service")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--sample-rate", type=float, default=10.0, help="Sample rate in Hz")
    parser.add_argument("--threshold", type=float, default=3.0, help="Voltage threshold")
    parser.add_argument("--database", default="dev_database.db", help="Database path")
    parser.add_argument("--port", type=int, default=8765, help="IPC port")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    parser.add_argument("--log-file", help="Log file path")
    parser.add_argument("--test", action="store_true", help="Run in test mode")
    
    args = parser.parse_args()
    
    # Create configuration
    config = MonitoringConfig(
        sample_rate_hz=args.sample_rate,
        voltage_threshold=args.threshold,
        database_path=args.database,
        ipc_port=args.port,
        log_level=args.log_level,
        log_file=args.log_file
    )
    
    # Create and start monitoring service
    monitor = StandaloneLabJackMonitor(config)
    
    if args.test:
        # Test mode - run some basic tests
        print("🧪 Running in test mode")
        success = await monitor.start()
        if success:
            print("✅ Service started successfully")
            
            # Test monitoring for 10 seconds
            monitor.start_monitoring("test_session_001", 10.0)
            await asyncio.sleep(10)
            monitor.stop_monitoring()
            
            await monitor.shutdown()
            print("✅ Test completed")
        else:
            print("❌ Service failed to start")
        return
    
    # Normal operation
    try:
        success = await monitor.start()
        if not success:
            sys.exit(1)
        
        # Keep service running
        while not monitor.shutdown_requested:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        traceback.print_exc()
    finally:
        await monitor.shutdown()

if __name__ == "__main__":
    asyncio.run(main())