"""
Dedicated LabJack Monitoring Service Process
=========================================

This service runs as a separate process to handle LabJack monitoring
independently from the main application, preventing device conflicts
and ensuring reliable signal acquisition during HIL tests.

Key Features:
- Independent process lifecycle
- IPC communication with main application  
- Device conflict prevention
- Real-time detection event storage
- Health monitoring and recovery
- Graceful shutdown handling
"""

import logging
import asyncio
import json
import time
import threading
import signal
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pathlib import Path
import sqlite3
import uuid
import socket
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('monitoring_service.log')
    ]
)
logger = logging.getLogger(__name__)

class MonitoringServiceIPC:
    """Inter-Process Communication handler for monitoring service"""
    
    def __init__(self, socket_path: str = "/tmp/monitoring_service.sock"):
        self.socket_path = socket_path
        self.server_socket = None
        self.running = False
        
    async def start_server(self, message_handler):
        """Start IPC server to handle commands from main application"""
        try:
            # Remove existing socket file
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
                
            self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server_socket.bind(self.socket_path)
            self.server_socket.listen(5)
            self.running = True
            
            logger.info(f"IPC server started at {self.socket_path}")
            
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    asyncio.create_task(self._handle_client(conn, message_handler))
                except OSError:
                    if self.running:
                        logger.error("Socket error in IPC server")
                        break
                        
        except Exception as e:
            logger.error(f"Failed to start IPC server: {e}")
            
    async def _handle_client(self, conn, message_handler):
        """Handle individual client connections"""
        try:
            data = conn.recv(4096).decode('utf-8')
            if data:
                try:
                    message = json.loads(data)
                    response = await message_handler(message)
                    conn.send(json.dumps(response).encode('utf-8'))
                except json.JSONDecodeError:
                    conn.send(json.dumps({"error": "Invalid JSON"}).encode('utf-8'))
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            conn.close()
            
    def stop_server(self):
        """Stop IPC server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

class DedicatedMonitoringService:
    """Main monitoring service class"""
    
    def __init__(self, db_path: str = "dev_database.db"):
        self.db_path = db_path
        self.monitoring_active = False
        self.current_session_id = None
        self.sample_rate = 10  # Hz
        self.detection_count = 0
        self.monitor_thread = None
        self._stop_event = threading.Event()
        self.ipc = MonitoringServiceIPC()
        self.health_status = {"status": "healthy", "last_check": None}
        
        # Import signal validation service
        self._init_signal_service()
        
    def _init_signal_service(self):
        """Initialize appropriate signal validation service"""
        try:
            import platform
            if platform.system() == "Linux" and "microsoft" in platform.uname().release.lower():
                from services.signal_validation_wsl import signal_validation_service
            else:
                from services.signal_validation_service import signal_validation_service
            
            self.signal_service = signal_validation_service
            logger.info("✅ Signal validation service initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize signal service: {e}")
            self.signal_service = None
    
    async def handle_ipc_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle IPC messages from main application"""
        try:
            command = message.get("command")
            logger.info(f"📨 Received IPC command: {command}")
            
            if command == "start_monitoring":
                session_id = message.get("session_id")
                sample_rate = message.get("sample_rate", 10)
                return self._start_monitoring(session_id, sample_rate)
                
            elif command == "stop_monitoring":
                return self._stop_monitoring()
                
            elif command == "get_status":
                return self._get_status()
                
            elif command == "health_check":
                return self._health_check()
                
            elif command == "get_detection_count":
                return {"detection_count": self.detection_count, "session_id": self.current_session_id}
                
            elif command == "shutdown":
                logger.info("🔄 Shutdown command received")
                asyncio.create_task(self._shutdown())
                return {"status": "shutting_down"}
                
            else:
                return {"error": f"Unknown command: {command}"}
                
        except Exception as e:
            logger.error(f"❌ Error handling IPC message: {e}")
            return {"error": str(e)}
    
    def _start_monitoring(self, session_id: str, sample_rate: int = 10) -> Dict[str, Any]:
        """Start LabJack monitoring for a session"""
        try:
            if self.monitoring_active:
                return {"error": f"Monitoring already active for session {self.current_session_id}"}
            
            self.current_session_id = session_id
            self.sample_rate = sample_rate
            self.detection_count = 0
            self.monitoring_active = True
            self._stop_event.clear()
            
            # Start monitoring thread
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(session_id,),
                daemon=False  # Don't make daemon to ensure proper cleanup
            )
            self.monitor_thread.start()
            
            logger.info(f"📊 Started monitoring for session {session_id} at {sample_rate}Hz")
            
            return {
                "status": "started",
                "session_id": session_id,
                "sample_rate": sample_rate,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to start monitoring: {e}")
            return {"error": str(e)}
    
    def _stop_monitoring(self) -> Dict[str, Any]:
        """Stop LabJack monitoring"""
        try:
            if not self.monitoring_active:
                return {"status": "not_active"}
            
            logger.info(f"⏹️ Stopping monitoring for session {self.current_session_id}")
            
            self.monitoring_active = False
            self._stop_event.set()
            
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5)
                
            session_id = self.current_session_id
            detection_count = self.detection_count
            
            self.current_session_id = None
            self.detection_count = 0
            
            return {
                "status": "stopped",
                "session_id": session_id,
                "total_detections": detection_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to stop monitoring: {e}")
            return {"error": str(e)}
    
    def _get_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            "monitoring_active": self.monitoring_active,
            "session_id": self.current_session_id,
            "detection_count": self.detection_count,
            "sample_rate": self.sample_rate,
            "health": self.health_status,
            "signal_service_available": self.signal_service is not None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        try:
            health = {
                "service_status": "healthy",
                "monitoring_active": self.monitoring_active,
                "signal_service": "unavailable",
                "database": "unknown",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Check signal service
            if self.signal_service:
                try:
                    # Test reading a voltage to verify hardware connection
                    result = self.signal_service.read_voltage_signal("AIN0")
                    if result.get("success"):
                        health["signal_service"] = "connected"
                    else:
                        health["signal_service"] = "mock_mode"
                except Exception:
                    health["signal_service"] = "error"
            
            # Check database connectivity
            try:
                conn = sqlite3.connect(self.db_path, timeout=5)
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                conn.close()
                health["database"] = "connected"
            except Exception:
                health["database"] = "error"
                health["service_status"] = "degraded"
            
            self.health_status = health
            return health
            
        except Exception as e:
            error_health = {
                "service_status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self.health_status = error_health
            return error_health
    
    def _monitor_loop(self, session_id: str):
        """Main monitoring loop that reads LabJack signals"""
        logger.info(f"📊 Starting monitoring loop for session {session_id}")
        
        if not self.signal_service:
            logger.error("❌ Signal service not available, monitoring cannot proceed")
            return
        
        sample_interval = 1.0 / self.sample_rate
        
        try:
            while self.monitoring_active and not self._stop_event.is_set():
                try:
                    # Read voltage from LabJack
                    result = self.signal_service.read_voltage_signal("AIN0")
                    
                    if result.get("success") and result.get("voltage") is not None:
                        voltage = result["voltage"]
                        timestamp = time.time()
                        
                        # Store as detection event if voltage exceeds threshold (e.g., 3.0V)
                        if voltage > 3.0:  # TTL high threshold
                            self._store_detection_event(
                                session_id=session_id,
                                voltage=voltage,
                                timestamp=timestamp,
                                channel="AIN0"
                            )
                            self.detection_count += 1
                            
                            # Log every detection during first 10, then every 10th
                            if self.detection_count <= 10 or self.detection_count % 10 == 0:
                                logger.info(f"📈 Captured {self.detection_count} detections, latest: {voltage:.3f}V")
                        else:
                            # Log low voltage readings occasionally for debugging
                            if self.detection_count == 0 and self.detection_count % 100 == 0:
                                logger.debug(f"🔽 Low voltage reading: {voltage:.3f}V")
                    else:
                        logger.warning(f"❌ Failed to read voltage: {result}")
                    
                    # Sleep for sample interval
                    time.sleep(sample_interval)
                    
                except Exception as e:
                    logger.error(f"❌ Error in monitoring loop: {e}")
                    time.sleep(1)  # Back off on error
                    
        except Exception as e:
            logger.error(f"💥 Fatal error in monitoring thread: {e}")
        finally:
            self.monitoring_active = False
            logger.info(f"🏁 Monitoring thread ended for session {session_id}, captured {self.detection_count} detections")
    
    def _store_detection_event(self, session_id: str, voltage: float, timestamp: float, channel: str):
        """Store a detection event in the database"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            cursor = conn.cursor()
            
            # Generate unique ID
            event_id = str(uuid.uuid4())
            
            # Calculate latency (assuming minimal hardware latency)
            latency_ms = 5.0  # Typical LabJack response time
            
            # Insert detection event using existing schema
            cursor.execute("""
                INSERT INTO detection_events (
                    id, test_session_id, timestamp, 
                    confidence, class_label, validation_result,
                    created_at, vru_type, processing_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                session_id,
                timestamp,
                voltage,  # Use confidence field to store voltage
                f"LabJack_{channel}",  # Use class_label to store channel info
                "passed" if voltage > 3.0 else "failed",
                datetime.now(timezone.utc).isoformat(),
                f"LabJack_{voltage:.3f}V",  # Store voltage info in vru_type
                latency_ms  # Processing time
            ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"✅ Stored detection event: {voltage:.3f}V at {timestamp:.3f}")
            
        except Exception as e:
            logger.error(f"❌ Failed to store detection event: {e}")
    
    async def _shutdown(self):
        """Graceful shutdown of monitoring service"""
        logger.info("🔄 Starting graceful shutdown...")
        
        # Stop monitoring if active
        if self.monitoring_active:
            self._stop_monitoring()
        
        # Stop IPC server
        self.ipc.stop_server()
        
        logger.info("👋 Monitoring service shutdown complete")
        sys.exit(0)
    
    async def run(self):
        """Main service loop"""
        logger.info("🚀 Starting Dedicated LabJack Monitoring Service")
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"📡 Received signal {signum}, shutting down...")
            asyncio.create_task(self._shutdown())
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Perform initial health check
        health = self._health_check()
        logger.info(f"🔍 Initial health check: {health['service_status']}")
        
        # Start IPC server
        try:
            await self.ipc.start_server(self.handle_ipc_message)
        except Exception as e:
            logger.error(f"❌ Failed to start IPC server: {e}")
            sys.exit(1)

# Entry point for standalone service
async def main():
    """Main entry point for the monitoring service"""
    service = DedicatedMonitoringService()
    
    try:
        await service.run()
    except KeyboardInterrupt:
        logger.info("🔄 Service interrupted by user")
    except Exception as e:
        logger.error(f"❌ Service error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())