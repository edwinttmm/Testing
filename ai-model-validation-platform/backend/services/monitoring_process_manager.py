"""
Monitoring Service Process Manager
=================================

Manages the lifecycle of the dedicated monitoring service process.
Handles startup, health monitoring, recovery, and graceful shutdown.
"""

import logging
import asyncio
import subprocess
import psutil
import signal
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from .monitoring_service_client import MonitoringServiceClient

logger = logging.getLogger(__name__)

class MonitoringProcessManager:
    """Manager for the dedicated monitoring service process"""
    
    def __init__(self, script_path: str = None):
        self.script_path = script_path or str(Path(__file__).parent / "dedicated_monitoring_service.py")
        self.process: Optional[subprocess.Popen] = None
        self.client = MonitoringServiceClient()
        self._health_check_interval = 10.0  # seconds
        self._max_restart_attempts = 3
        self._restart_delay = 5.0  # seconds
        self._health_check_task = None
        self._restart_count = 0
        self._last_restart_time = None
        
    async def start_service(self, auto_restart: bool = True) -> Dict[str, Any]:
        """Start the monitoring service process"""
        try:
            if self.is_process_running():
                logger.info("📊 Monitoring service is already running")
                return {"success": True, "message": "Service already running", "pid": self.process.pid}
            
            logger.info("🚀 Starting monitoring service process...")
            
            # Start the monitoring service as a subprocess
            self.process = subprocess.Popen(
                ["python", self.script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create new process group for clean shutdown
            )
            
            # Wait a moment for the process to initialize
            await asyncio.sleep(2.0)
            
            # Verify the process started successfully
            if self.process.poll() is not None:
                # Process has already terminated
                stdout, stderr = self.process.communicate()
                error_msg = f"Monitoring service failed to start: {stderr.decode()}"
                logger.error(f"❌ {error_msg}")
                return {"success": False, "error": error_msg}
            
            # Wait for service to become available
            service_available = await self.client.wait_for_service(max_wait_time=30.0)
            
            if service_available:
                logger.info(f"✅ Monitoring service started successfully (PID: {self.process.pid})")
                
                # Start health monitoring if auto-restart is enabled
                if auto_restart and self._health_check_task is None:
                    self._health_check_task = asyncio.create_task(self._health_monitor_loop())
                
                self._restart_count = 0  # Reset restart count on successful start
                
                return {
                    "success": True,
                    "message": "Monitoring service started successfully",
                    "pid": self.process.pid,
                    "auto_restart": auto_restart
                }
            else:
                # Service process is running but not responding
                logger.error("❌ Monitoring service process started but is not responding")
                await self.stop_service()
                return {"success": False, "error": "Service not responding after startup"}
                
        except Exception as e:
            logger.error(f"❌ Failed to start monitoring service: {e}")
            return {"success": False, "error": str(e)}
    
    async def stop_service(self, timeout: float = 10.0) -> Dict[str, Any]:
        """Stop the monitoring service process gracefully"""
        try:
            if not self.is_process_running():
                logger.info("ℹ️ Monitoring service is not running")
                return {"success": True, "message": "Service was not running"}
            
            logger.info(f"⏹️ Stopping monitoring service (PID: {self.process.pid})...")
            
            # Stop health monitoring
            if self._health_check_task:
                self._health_check_task.cancel()
                self._health_check_task = None
            
            # Try to send shutdown command via IPC first
            try:
                await self.client._send_command({"command": "shutdown"})
                logger.info("📨 Sent shutdown command via IPC")
            except Exception as e:
                logger.warning(f"⚠️ Could not send shutdown command: {e}")
            
            # Wait for graceful shutdown
            try:
                self.process.wait(timeout=timeout)
                logger.info("✅ Monitoring service shut down gracefully")
                return {"success": True, "message": "Service stopped gracefully"}
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Graceful shutdown timed out, forcing termination")
                
                # Force termination
                try:
                    # Terminate the entire process group
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                    self.process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    # Last resort: SIGKILL
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    self.process.wait()
                
                logger.info("🔨 Monitoring service terminated forcefully")
                return {"success": True, "message": "Service stopped forcefully"}
                
        except Exception as e:
            logger.error(f"❌ Error stopping monitoring service: {e}")
            return {"success": False, "error": str(e)}
        finally:
            self.process = None
    
    def is_process_running(self) -> bool:
        """Check if the monitoring service process is running"""
        if self.process is None:
            return False
        
        # Check if process is still alive
        return self.process.poll() is None
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the monitoring service"""
        try:
            status = {
                "process_running": self.is_process_running(),
                "pid": self.process.pid if self.process else None,
                "restart_count": self._restart_count,
                "last_restart": self._last_restart_time.isoformat() if self._last_restart_time else None,
                "health_monitoring": self._health_check_task is not None,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Get process details if running
            if self.is_process_running():
                try:
                    proc = psutil.Process(self.process.pid)
                    status.update({
                        "memory_mb": proc.memory_info().rss / 1024 / 1024,
                        "cpu_percent": proc.cpu_percent(),
                        "create_time": datetime.fromtimestamp(proc.create_time()).isoformat(),
                        "status": proc.status()
                    })
                except psutil.NoSuchProcess:
                    status["process_running"] = False
            
            # Get service health if available
            if status["process_running"]:
                try:
                    health = await self.client.health_check()
                    status["service_health"] = health
                except Exception as e:
                    status["service_health"] = {"error": str(e)}
            
            return status
            
        except Exception as e:
            logger.error(f"❌ Error getting service status: {e}")
            return {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
    
    async def restart_service(self) -> Dict[str, Any]:
        """Restart the monitoring service"""
        logger.info("🔄 Restarting monitoring service...")
        
        # Increment restart count and track timing
        self._restart_count += 1
        self._last_restart_time = datetime.now(timezone.utc)
        
        # Check restart limits
        if self._restart_count > self._max_restart_attempts:
            error_msg = f"Maximum restart attempts ({self._max_restart_attempts}) exceeded"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}
        
        # Stop current service
        stop_result = await self.stop_service()
        if not stop_result.get("success"):
            logger.warning(f"⚠️ Stop failed during restart: {stop_result.get('error')}")
        
        # Wait before restarting
        await asyncio.sleep(self._restart_delay)
        
        # Start service again
        start_result = await self.start_service()
        
        if start_result.get("success"):
            logger.info(f"✅ Monitoring service restarted successfully (attempt {self._restart_count})")
        else:
            logger.error(f"❌ Restart failed (attempt {self._restart_count}): {start_result.get('error')}")
        
        return start_result
    
    async def _health_monitor_loop(self):
        """Background health monitoring with auto-restart"""
        logger.info("🔍 Starting health monitoring loop")
        
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        try:
            while True:
                await asyncio.sleep(self._health_check_interval)
                
                # Check if process is still running
                if not self.is_process_running():
                    logger.warning("⚠️ Monitoring service process died, attempting restart...")
                    await self.restart_service()
                    consecutive_failures = 0  # Reset counter after restart attempt
                    continue
                
                # Check service health
                try:
                    health = await self.client.health_check()
                    
                    if health.get("service_status") in ["healthy", "degraded"]:
                        consecutive_failures = 0  # Reset counter on successful health check
                        logger.debug("💚 Health check passed")
                    else:
                        consecutive_failures += 1
                        logger.warning(f"💛 Health check failed ({consecutive_failures}/{max_consecutive_failures}): {health}")
                        
                except Exception as e:
                    consecutive_failures += 1
                    logger.warning(f"💔 Health check error ({consecutive_failures}/{max_consecutive_failures}): {e}")
                
                # Restart if too many consecutive failures
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(f"❌ Too many consecutive health check failures, restarting service...")
                    await self.restart_service()
                    consecutive_failures = 0
                    
        except asyncio.CancelledError:
            logger.info("🛑 Health monitoring loop cancelled")
        except Exception as e:
            logger.error(f"❌ Health monitoring loop error: {e}")
    
    async def ensure_service_available(self, start_if_needed: bool = True) -> bool:
        """Ensure monitoring service is available and healthy"""
        try:
            # Check if already available
            if await self.client.is_service_available():
                return True
            
            # Start service if needed and allowed
            if start_if_needed:
                logger.info("🔧 Monitoring service not available, starting...")
                result = await self.start_service()
                return result.get("success", False)
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error ensuring service availability: {e}")
            return False
    
    async def cleanup(self):
        """Clean up resources and stop service"""
        logger.info("🧹 Cleaning up monitoring process manager...")
        
        # Cancel health monitoring
        if self._health_check_task:
            self._health_check_task.cancel()
        
        # Stop service
        await self.stop_service()
        
        logger.info("✅ Monitoring process manager cleanup complete")

# Global instance
monitoring_process_manager = MonitoringProcessManager()