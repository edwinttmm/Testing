#!/usr/bin/env python3
"""
LabJack Monitor Client
=====================

Client interface for communicating with the dedicated LabJack monitoring service.
Provides a simple API for the main backend to control and query the monitoring service
without direct LabJack access, eliminating device conflicts.

Key Features:
- Unix domain socket IPC communication
- Async/await interface for non-blocking operations
- Automatic reconnection and error handling
- Health monitoring and status queries
- Real-time data access
- Service lifecycle management

Usage:
    client = LabJackMonitorClient()
    await client.connect()
    status = await client.get_status()
    readings = await client.get_recent_readings(count=10)
    await client.disconnect()
"""

import asyncio
import json
import socket
import time
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import os

logger = logging.getLogger(__name__)

class LabJackMonitorClient:
    """Client for communicating with dedicated LabJack monitoring service"""
    
    def __init__(self, socket_path: str = "/tmp/labjack_monitor.sock"):
        self.socket_path = socket_path
        self.socket = None
        self.connected = False
        self.last_ping = 0
        
    async def connect(self, timeout: float = 5.0) -> bool:
        """Connect to the monitoring service"""
        try:
            logger.debug(f"Connecting to LabJack monitor service at {self.socket_path}")
            
            # Create socket
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.settimeout(timeout)
            
            # Connect to service
            self.socket.connect(self.socket_path)
            self.connected = True
            
            logger.info("Connected to LabJack monitoring service")
            
            # Test connection with ping
            ping_result = await self._send_command({"type": "ping"})
            if ping_result.get("success"):
                logger.debug("Connection verified with ping")
                return True
            else:
                logger.error(f"Connection test failed: {ping_result}")
                await self.disconnect()
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to monitoring service: {e}")
            await self.disconnect()
            return False
    
    async def disconnect(self):
        """Disconnect from the monitoring service"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        self.connected = False
        logger.debug("Disconnected from LabJack monitoring service")
    
    async def _send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Send command to monitoring service and get response"""
        if not self.connected or not self.socket:
            return {"success": False, "error": "Not connected to service"}
        
        try:
            # Send command
            command_data = json.dumps(command).encode()
            self.socket.sendall(command_data)
            
            # Receive response
            response_data = self.socket.recv(4096)
            if not response_data:
                return {"success": False, "error": "No response from service"}
            
            response = json.loads(response_data.decode())
            return response
            
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current monitoring service status"""
        return await self._send_command({"type": "get_status"})
    
    async def get_recent_readings(self, count: int = 10) -> Dict[str, Any]:
        """Get recent voltage readings from the service"""
        return await self._send_command({
            "type": "get_readings",
            "count": count
        })
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics"""
        return await self._send_command({"type": "get_stats"})
    
    async def ping(self) -> Dict[str, Any]:
        """Ping the service to check connectivity"""
        result = await self._send_command({"type": "ping"})
        if result.get("success"):
            self.last_ping = time.time()
        return result
    
    async def is_service_running(self) -> bool:
        """Check if the monitoring service is running"""
        try:
            # Check if socket file exists
            if not os.path.exists(self.socket_path):
                return False
            
            # Try to connect and ping
            if not self.connected:
                if not await self.connect():
                    return False
            
            ping_result = await self.ping()
            return ping_result.get("success", False)
            
        except Exception as e:
            logger.debug(f"Service check failed: {e}")
            return False
    
    async def wait_for_service(self, timeout: float = 30.0) -> bool:
        """Wait for the monitoring service to become available"""
        logger.info(f"Waiting for LabJack monitoring service (timeout: {timeout}s)")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if await self.is_service_running():
                logger.info("LabJack monitoring service is available")
                return True
            
            await asyncio.sleep(1.0)
        
        logger.error(f"Timeout waiting for LabJack monitoring service ({timeout}s)")
        return False

class LabJackMonitorManager:
    """High-level manager for LabJack monitoring service lifecycle"""
    
    def __init__(self, socket_path: str = "/tmp/labjack_monitor.sock"):
        self.socket_path = socket_path
        self.client = LabJackMonitorClient(socket_path)
        self.service_process = None
        
    async def start_monitoring_service(
        self,
        session_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Start the dedicated monitoring service process"""
        
        try:
            import subprocess
            import multiprocessing
            from .dedicated_labjack_monitor import run_monitoring_service
            
            # Default configuration
            default_config = {
                "session_id": session_id,
                "sample_rate": 10.0,
                "voltage_threshold": 3.0,
                "channels": ["AIN0"],
                "database_path": "dev_database.db",
                "socket_path": self.socket_path,
                "max_buffer_size": 1000,
                "enable_recovery": True,
                "max_retries": 3,
                "retry_delay": 1.0
            }
            
            # Merge with provided config
            if config:
                default_config.update(config)
            
            logger.info(f"Starting dedicated LabJack monitoring service for session {session_id}")
            
            # Start service process
            self.service_process = multiprocessing.Process(
                target=run_monitoring_service,
                args=(default_config,),
                name=f"LabJackMonitor_{session_id}",
                daemon=False
            )
            
            self.service_process.start()
            
            # Wait for service to become available
            if await self.client.wait_for_service(timeout=10.0):
                logger.info(f"LabJack monitoring service started successfully (PID: {self.service_process.pid})")
                return True
            else:
                logger.error("LabJack monitoring service failed to start")
                await self.stop_monitoring_service()
                return False
                
        except Exception as e:
            logger.error(f"Failed to start monitoring service: {e}")
            return False
    
    async def stop_monitoring_service(self):
        """Stop the dedicated monitoring service process"""
        
        try:
            if self.service_process and self.service_process.is_alive():
                logger.info("Stopping LabJack monitoring service...")
                
                # Disconnect client first
                await self.client.disconnect()
                
                # Terminate the process
                self.service_process.terminate()
                
                # Wait for graceful shutdown
                self.service_process.join(timeout=10)
                
                # Force kill if still alive
                if self.service_process.is_alive():
                    logger.warning("Force killing monitoring service process")
                    self.service_process.kill()
                    self.service_process.join()
                
                logger.info("LabJack monitoring service stopped")
                
            self.service_process = None
            
        except Exception as e:
            logger.error(f"Error stopping monitoring service: {e}")
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status"""
        
        status = {
            "service_running": False,
            "process_alive": False,
            "connected": False,
            "monitoring_active": False,
            "process_id": None,
            "error": None
        }
        
        try:
            # Check process status
            if self.service_process:
                status["process_alive"] = self.service_process.is_alive()
                status["process_id"] = self.service_process.pid if status["process_alive"] else None
            
            # Check service connectivity
            if await self.client.is_service_running():
                status["service_running"] = True
                
                # Connect if needed
                if not self.client.connected:
                    await self.client.connect()
                
                if self.client.connected:
                    status["connected"] = True
                    
                    # Get monitoring status
                    monitor_status = await self.client.get_status()
                    if monitor_status.get("success"):
                        data = monitor_status.get("data", {})
                        status["monitoring_active"] = data.get("active", False)
                        status["session_id"] = data.get("session_id")
                        status["sample_rate"] = data.get("sample_rate")
                        status["uptime"] = data.get("uptime")
                        status["total_readings"] = data.get("total_readings")
                        status["detections"] = data.get("detections")
                        status["errors"] = data.get("errors")
            
        except Exception as e:
            status["error"] = str(e)
        
        return status
    
    async def get_recent_detections(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent detection events"""
        
        try:
            if not self.client.connected:
                if not await self.client.connect():
                    return []
            
            result = await self.client.get_recent_readings(count)
            if result.get("success"):
                # Filter for detections only
                readings = result.get("data", [])
                detections = [r for r in readings if r.get("detection", False)]
                return detections
            else:
                logger.error(f"Failed to get recent readings: {result}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting recent detections: {e}")
            return []
    
    async def get_monitoring_statistics(self) -> Dict[str, Any]:
        """Get detailed monitoring statistics"""
        
        try:
            if not self.client.connected:
                if not await self.client.connect():
                    return {}
            
            result = await self.client.get_statistics()
            if result.get("success"):
                return result.get("data", {})
            else:
                logger.error(f"Failed to get statistics: {result}")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

# Global instance for easy access
labjack_monitor_manager = LabJackMonitorManager()