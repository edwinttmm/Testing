"""
LabJack Monitor Client
=====================

Client interface for communicating with the dedicated LabJack monitoring service.
This allows the main FastAPI backend to control monitoring without device conflicts.
"""

import asyncio
import json
import logging
import socket
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class LabJackMonitorClient:
    """Client for communicating with dedicated LabJack monitoring service"""
    
    def __init__(self, socket_path: str = "/tmp/labjack_monitor.sock"):
        self.socket_path = socket_path
        self.timeout = 30.0  # 30 second timeout
        
    async def _send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Send command to monitoring service and get response"""
        try:
            # Connect to Unix socket
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.socket_path),
                timeout=5.0
            )
            
            try:
                # Send command
                command_data = json.dumps(command).encode()
                writer.write(command_data)
                await writer.drain()
                
                # Read response with shorter timeout
                response_data = await asyncio.wait_for(
                    reader.read(8192),
                    timeout=5.0
                )
                
                if not response_data:
                    return {"success": False, "error": "No response from monitoring service"}
                
                response = json.loads(response_data.decode())
                return response
                
            finally:
                writer.close()
                await writer.wait_closed()
                
        except asyncio.TimeoutError:
            logger.error("⏰ Timeout connecting to monitoring service")
            return {"success": False, "error": "Timeout connecting to monitoring service"}
        except FileNotFoundError:
            logger.error("📁 Monitoring service socket not found")
            return {"success": False, "error": "Monitoring service not running"}
        except Exception as e:
            logger.error(f"❌ Error communicating with monitoring service: {e}")
            return {"success": False, "error": str(e)}
    
    async def start_monitoring(self, session_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start monitoring for a test session"""
        if config is None:
            config = {}
            
        command = {
            "action": "start_monitoring",
            "session_id": session_id,
            "config": config,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"🚀 Starting monitoring for session {session_id}")
        result = await self._send_command(command)
        
        if result.get("success"):
            logger.info(f"✅ Monitoring started for session {session_id}")
        else:
            logger.error(f"❌ Failed to start monitoring for {session_id}: {result.get('error')}")
            
        return result
    
    async def stop_monitoring(self, session_id: str) -> Dict[str, Any]:
        """Stop monitoring for a test session"""
        command = {
            "action": "stop_monitoring",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"⏹️ Stopping monitoring for session {session_id}")
        result = await self._send_command(command)
        
        if result.get("success"):
            logger.info(f"✅ Monitoring stopped for session {session_id}")
        else:
            logger.error(f"❌ Failed to stop monitoring for {session_id}: {result.get('error')}")
            
        return result
    
    async def get_status(self) -> Dict[str, Any]:
        """Get monitoring service status"""
        command = {
            "action": "get_status",
            "timestamp": datetime.now().isoformat()
        }
        
        result = await self._send_command(command)
        return result
    
    async def ping(self) -> Dict[str, Any]:
        """Ping the monitoring service to check if it's alive"""
        command = {
            "action": "ping",
            "timestamp": datetime.now().isoformat()
        }
        
        result = await self._send_command(command)
        return result
    
    async def is_monitoring_service_available(self) -> bool:
        """Check if the monitoring service is available"""
        try:
            result = await self.ping()
            return result.get("success", False)
        except Exception:
            return False

# Global client instance
labjack_monitor_client = LabJackMonitorClient()

# Convenience functions for backward compatibility
async def start_monitoring_for_session(session_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start monitoring for a test session"""
    return await labjack_monitor_client.start_monitoring(session_id, config)

async def stop_monitoring_for_session(session_id: str) -> Dict[str, Any]:
    """Stop monitoring for a test session"""
    return await labjack_monitor_client.stop_monitoring(session_id)

async def get_monitoring_service_status() -> Dict[str, Any]:
    """Get monitoring service status"""
    return await labjack_monitor_client.get_status()

async def is_monitoring_service_healthy() -> bool:
    """Check if monitoring service is healthy"""
    return await labjack_monitor_client.is_monitoring_service_available()