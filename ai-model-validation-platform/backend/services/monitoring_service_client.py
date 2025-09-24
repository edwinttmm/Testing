"""
Monitoring Service IPC Client
============================

Client for communicating with the dedicated monitoring service process.
Provides a simple interface for the main application to control monitoring
without direct hardware access conflicts.
"""

import logging
import json
import socket
import asyncio
import time
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class MonitoringServiceClient:
    """Client for communicating with dedicated monitoring service"""
    
    def __init__(self, socket_path: str = "/tmp/monitoring_service.sock", timeout: float = 5.0):
        self.socket_path = socket_path
        self.timeout = timeout
        self._connection_retries = 3
        self._retry_delay = 1.0
    
    async def _send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Send command to monitoring service and return response"""
        for attempt in range(self._connection_retries):
            try:
                # Create socket connection
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect(self.socket_path)
                
                # Send command
                command_json = json.dumps(command)
                sock.send(command_json.encode('utf-8'))
                
                # Receive response
                response_data = sock.recv(4096).decode('utf-8')
                sock.close()
                
                response = json.loads(response_data)
                logger.debug(f"📨 Monitoring service response: {response}")
                return response
                
            except socket.error as e:
                logger.warning(f"🔌 Connection attempt {attempt + 1} failed: {e}")
                if attempt < self._connection_retries - 1:
                    await asyncio.sleep(self._retry_delay)
                else:
                    return {"error": f"Failed to connect to monitoring service after {self._connection_retries} attempts: {e}"}
            except json.JSONDecodeError as e:
                return {"error": f"Invalid response from monitoring service: {e}"}
            except Exception as e:
                return {"error": f"Unexpected error communicating with monitoring service: {e}"}
    
    async def start_monitoring(self, session_id: str, sample_rate: int = 10) -> Dict[str, Any]:
        """Start monitoring for a test session"""
        logger.info(f"🚀 Starting monitoring for session {session_id}")
        
        command = {
            "command": "start_monitoring",
            "session_id": session_id,
            "sample_rate": sample_rate
        }
        
        response = await self._send_command(command)
        
        if response.get("status") == "started":
            logger.info(f"✅ Monitoring started successfully for session {session_id}")
        else:
            logger.error(f"❌ Failed to start monitoring: {response.get('error', 'Unknown error')}")
            
        return response
    
    async def stop_monitoring(self) -> Dict[str, Any]:
        """Stop monitoring"""
        logger.info("⏹️ Stopping monitoring")
        
        command = {"command": "stop_monitoring"}
        response = await self._send_command(command)
        
        if response.get("status") == "stopped":
            logger.info(f"✅ Monitoring stopped, captured {response.get('total_detections', 0)} detections")
        else:
            logger.error(f"❌ Failed to stop monitoring: {response.get('error', 'Unknown error')}")
            
        return response
    
    async def get_status(self) -> Dict[str, Any]:
        """Get monitoring service status"""
        command = {"command": "get_status"}
        response = await self._send_command(command)
        
        logger.debug(f"📊 Monitoring status: active={response.get('monitoring_active')}, "
                    f"detections={response.get('detection_count', 0)}")
        
        return response
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on monitoring service"""
        command = {"command": "health_check"}
        response = await self._send_command(command)
        
        status = response.get("service_status", "unknown")
        logger.debug(f"🔍 Health check result: {status}")
        
        return response
    
    async def get_detection_count(self) -> Dict[str, Any]:
        """Get current detection count"""
        command = {"command": "get_detection_count"}
        return await self._send_command(command)
    
    async def is_service_available(self) -> bool:
        """Check if monitoring service is available and responsive"""
        try:
            health = await self.health_check()
            return health.get("service_status") in ["healthy", "degraded"]
        except Exception:
            return False
    
    async def wait_for_service(self, max_wait_time: float = 30.0) -> bool:
        """Wait for monitoring service to become available"""
        logger.info("⏳ Waiting for monitoring service to become available...")
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            if await self.is_service_available():
                logger.info("✅ Monitoring service is available")
                return True
            
            logger.debug("🔄 Monitoring service not yet available, retrying...")
            await asyncio.sleep(2.0)
        
        logger.error(f"❌ Monitoring service did not become available within {max_wait_time} seconds")
        return False

class MonitoringServiceManager:
    """High-level manager for monitoring service operations"""
    
    def __init__(self):
        self.client = MonitoringServiceClient()
        self._current_session_id = None
        self._monitoring_active = False
    
    async def start_session_monitoring(self, session_id: str, sample_rate: int = 10, 
                                     wait_for_service: bool = True) -> Dict[str, Any]:
        """Start monitoring for a test session with service availability checks"""
        try:
            # Check if service is available
            if wait_for_service and not await self.client.is_service_available():
                logger.warning("🔄 Monitoring service not available, attempting to wait...")
                if not await self.client.wait_for_service():
                    return {
                        "success": False,
                        "error": "Monitoring service is not available",
                        "fallback": "Session will proceed without hardware monitoring"
                    }
            
            # Start monitoring
            response = await self.client.start_monitoring(session_id, sample_rate)
            
            if response.get("status") == "started":
                self._current_session_id = session_id
                self._monitoring_active = True
                return {
                    "success": True,
                    "session_id": session_id,
                    "message": "Monitoring started successfully",
                    "details": response
                }
            else:
                return {
                    "success": False,
                    "error": response.get("error", "Failed to start monitoring"),
                    "fallback": "Session will proceed without hardware monitoring"
                }
                
        except Exception as e:
            logger.error(f"❌ Error starting session monitoring: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback": "Session will proceed without hardware monitoring"
            }
    
    async def stop_session_monitoring(self) -> Dict[str, Any]:
        """Stop monitoring and return detection summary"""
        try:
            if not self._monitoring_active:
                return {
                    "success": True,
                    "message": "Monitoring was not active",
                    "detection_count": 0
                }
            
            response = await self.client.stop_monitoring()
            
            self._monitoring_active = False
            detection_count = response.get("total_detections", 0)
            
            return {
                "success": True,
                "session_id": self._current_session_id,
                "detection_count": detection_count,
                "message": f"Monitoring stopped, captured {detection_count} detections",
                "details": response
            }
            
        except Exception as e:
            logger.error(f"❌ Error stopping session monitoring: {e}")
            return {
                "success": False,
                "error": str(e),
                "detection_count": 0
            }
        finally:
            self._current_session_id = None
            self._monitoring_active = False
    
    async def get_monitoring_status(self) -> Dict[str, Any]:
        """Get comprehensive monitoring status"""
        try:
            status_response = await self.client.get_status()
            health_response = await self.client.health_check()
            
            return {
                "service_available": True,
                "monitoring_active": status_response.get("monitoring_active", False),
                "session_id": status_response.get("session_id"),
                "detection_count": status_response.get("detection_count", 0),
                "health_status": health_response.get("service_status", "unknown"),
                "signal_service": health_response.get("signal_service", "unknown"),
                "database": health_response.get("database", "unknown"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting monitoring status: {e}")
            return {
                "service_available": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

# Global monitoring service manager instance
monitoring_service_manager = MonitoringServiceManager()