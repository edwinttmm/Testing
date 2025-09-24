"""
LabJack Monitor Manager

Manages the standalone LabJack monitoring service from the main FastAPI backend.
Provides process management, IPC communication, and health monitoring.

Author: AI Model Validation Platform Team
Version: 1.0.0
"""

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
import json
import socket
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class MonitorProcessInfo:
    """Information about monitoring process"""
    pid: Optional[int]
    status: str  # "running", "stopped", "error", "starting"
    start_time: Optional[datetime]
    last_heartbeat: Optional[datetime]
    restart_count: int
    error_message: Optional[str]

class LabJackMonitorManager:
    """Manager for the standalone LabJack monitoring service"""
    
    def __init__(self, 
                 monitor_script_path: Optional[str] = None,
                 ipc_host: str = "localhost",
                 ipc_port: int = 8765,
                 database_path: str = "dev_database.db",
                 log_level: str = "INFO"):
        
        self.ipc_host = ipc_host
        self.ipc_port = ipc_port
        self.database_path = database_path
        self.log_level = log_level
        
        # Determine monitor script path
        if monitor_script_path is None:
            current_dir = Path(__file__).parent
            self.monitor_script_path = current_dir / "standalone_labjack_monitor.py"
        else:
            self.monitor_script_path = Path(monitor_script_path)
        
        # Process management
        self.process: Optional[subprocess.Popen] = None
        self.process_info = MonitorProcessInfo(
            pid=None,
            status="stopped",
            start_time=None,
            last_heartbeat=None,
            restart_count=0,
            error_message=None
        )
        
        # Configuration
        self.auto_restart = True
        self.max_restart_attempts = 3
        self.restart_delay = 5.0
        self.health_check_interval = 30.0
        
        # Monitoring task
        self._health_check_task: Optional[asyncio.Task] = None
        self._shutdown_requested = False
        
        logger.info(f"🎛️ LabJack Monitor Manager initialized")
        logger.info(f"📄 Monitor script: {self.monitor_script_path}")
        logger.info(f"🌐 IPC endpoint: {self.ipc_host}:{self.ipc_port}")
    
    async def start_monitor_process(self, 
                                  sample_rate: float = 10.0,
                                  voltage_threshold: float = 3.0) -> bool:
        """Start the standalone monitoring process"""
        try:
            if self.is_process_running():
                logger.warning("⚠️ Monitor process already running")
                return True
            
            # Prepare command arguments
            cmd = [
                sys.executable,
                str(self.monitor_script_path),
                "--sample-rate", str(sample_rate),
                "--threshold", str(voltage_threshold),
                "--database", self.database_path,
                "--port", str(self.ipc_port),
                "--log-level", self.log_level
            ]
            
            logger.info(f"🚀 Starting monitor process: {' '.join(cmd)}")
            
            # Start process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Update process info
            self.process_info.pid = self.process.pid
            self.process_info.status = "starting"
            self.process_info.start_time = datetime.now()
            self.process_info.error_message = None
            
            logger.info(f"✅ Monitor process started with PID {self.process.pid}")
            
            # Wait for service to be ready
            ready = await self._wait_for_service_ready()
            if ready:
                self.process_info.status = "running"
                self.process_info.last_heartbeat = datetime.now()
                
                # Start health monitoring
                if self._health_check_task is None or self._health_check_task.done():
                    self._health_check_task = asyncio.create_task(self._health_monitor_loop())
                
                logger.info("🎯 Monitor process ready and health monitoring started")
                return True
            else:
                logger.error("❌ Monitor process failed to become ready")
                await self.stop_monitor_process()
                return False
                
        except Exception as e:
            logger.error(f"💥 Failed to start monitor process: {e}")
            self.process_info.status = "error"
            self.process_info.error_message = str(e)
            return False
    
    async def stop_monitor_process(self) -> bool:
        """Stop the monitoring process gracefully"""
        try:
            if not self.is_process_running():
                logger.info("📴 Monitor process not running")
                return True
            
            logger.info(f"🛑 Stopping monitor process PID {self.process.pid}")
            
            # Try graceful shutdown via IPC first
            try:
                response = await self._send_ipc_command({"command": "shutdown"})
                if response.get("success"):
                    logger.info("📨 Graceful shutdown command sent")
                    
                    # Wait for process to terminate
                    for i in range(10):  # Wait up to 10 seconds
                        if self.process.poll() is not None:
                            break
                        await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"⚠️ IPC shutdown failed: {e}")
            
            # Force termination if still running
            if self.process.poll() is None:
                logger.warning("⚠️ Forcing process termination")
                self.process.terminate()
                
                # Wait for termination
                try:
                    await asyncio.wait_for(
                        asyncio.create_task(self._wait_for_process_exit()),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Process didn't terminate, killing")
                    self.process.kill()
                    await asyncio.create_task(self._wait_for_process_exit())
            
            # Clean up
            self.process = None
            self.process_info.pid = None
            self.process_info.status = "stopped"
            
            # Stop health monitoring
            if self._health_check_task and not self._health_check_task.done():
                self._health_check_task.cancel()
            
            logger.info("✅ Monitor process stopped")
            return True
            
        except Exception as e:
            logger.error(f"💥 Error stopping monitor process: {e}")
            return False
    
    async def restart_monitor_process(self) -> bool:
        """Restart the monitoring process"""
        logger.info("🔄 Restarting monitor process")
        
        success = await self.stop_monitor_process()
        if not success:
            logger.error("❌ Failed to stop process for restart")
            return False
        
        # Wait before restart
        await asyncio.sleep(self.restart_delay)
        
        success = await self.start_monitor_process()
        if success:
            self.process_info.restart_count += 1
            logger.info(f"✅ Monitor process restarted (restart #{self.process_info.restart_count})")
        else:
            logger.error("❌ Failed to restart monitor process")
        
        return success
    
    def is_process_running(self) -> bool:
        """Check if monitoring process is running"""
        if self.process is None:
            return False
        
        return self.process.poll() is None
    
    async def start_monitoring_session(self, 
                                     session_id: str, 
                                     sample_rate: float = 10.0) -> bool:
        """Start monitoring for a specific session"""
        try:
            # Ensure process is running
            if not self.is_process_running():
                logger.warning("⚠️ Monitor process not running, starting it")
                success = await self.start_monitor_process()
                if not success:
                    return False
            
            # Send start monitoring command
            command = {
                "command": "start_monitoring",
                "session_id": session_id,
                "sample_rate": sample_rate
            }
            
            response = await self._send_ipc_command(command)
            
            if response.get("success"):
                logger.info(f"📊 Started monitoring for session {session_id}")
                return True
            else:
                error = response.get("error", "Unknown error")
                logger.error(f"❌ Failed to start monitoring: {error}")
                return False
                
        except Exception as e:
            logger.error(f"💥 Error starting monitoring session: {e}")
            return False
    
    async def stop_monitoring_session(self) -> bool:
        """Stop current monitoring session"""
        try:
            if not self.is_process_running():
                logger.warning("⚠️ Monitor process not running")
                return True
            
            command = {"command": "stop_monitoring"}
            response = await self._send_ipc_command(command)
            
            if response.get("success"):
                logger.info("⏹️ Stopped monitoring session")
                return True
            else:
                error = response.get("error", "Unknown error")
                logger.error(f"❌ Failed to stop monitoring: {error}")
                return False
                
        except Exception as e:
            logger.error(f"💥 Error stopping monitoring session: {e}")
            return False
    
    async def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        try:
            if not self.is_process_running():
                return {
                    "process_running": False,
                    "monitoring_active": False,
                    "process_info": {
                        "status": self.process_info.status,
                        "pid": self.process_info.pid,
                        "restart_count": self.process_info.restart_count,
                        "error_message": self.process_info.error_message
                    }
                }
            
            # Get status from monitoring service
            command = {"command": "get_status"}
            response = await self._send_ipc_command(command)
            
            if response.get("success"):
                status = response.get("status", {})
                return {
                    "process_running": True,
                    "monitoring_active": status.get("active", False),
                    "session_id": status.get("session_id"),
                    "sample_rate_hz": status.get("sample_rate_hz"),
                    "total_detections": status.get("total_detections"),
                    "detection_rate": status.get("detection_rate"),
                    "uptime_seconds": status.get("uptime_seconds"),
                    "health_status": status.get("health_status"),
                    "process_info": {
                        "status": self.process_info.status,
                        "pid": self.process_info.pid,
                        "restart_count": self.process_info.restart_count,
                        "last_heartbeat": self.process_info.last_heartbeat.isoformat() if self.process_info.last_heartbeat else None
                    }
                }
            else:
                return {
                    "process_running": True,
                    "monitoring_active": False,
                    "error": response.get("error", "IPC communication failed")
                }
                
        except Exception as e:
            logger.error(f"💥 Error getting monitoring status: {e}")
            return {
                "process_running": self.is_process_running(),
                "monitoring_active": False,
                "error": str(e)
            }
    
    async def get_health_metrics(self) -> Dict[str, Any]:
        """Get detailed health metrics"""
        try:
            if not self.is_process_running():
                return {"process_running": False}
            
            command = {"command": "get_health"}
            response = await self._send_ipc_command(command)
            
            if response.get("success"):
                return {
                    "process_running": True,
                    "health": response.get("health", {})
                }
            else:
                return {
                    "process_running": True,
                    "error": response.get("error", "Failed to get health metrics")
                }
                
        except Exception as e:
            logger.error(f"💥 Error getting health metrics: {e}")
            return {"process_running": False, "error": str(e)}
    
    async def shutdown(self):
        """Shutdown the manager and stop monitoring process"""
        logger.info("🔄 Shutting down LabJack Monitor Manager")
        
        self._shutdown_requested = True
        
        # Stop health monitoring
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Stop monitoring process
        await self.stop_monitor_process()
        
        logger.info("✅ LabJack Monitor Manager shutdown complete")
    
    async def _send_ipc_command(self, command: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        """Send IPC command to monitoring service"""
        try:
            # Create socket connection
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.ipc_host, self.ipc_port),
                timeout=timeout
            )
            
            try:
                # Send command
                command_data = json.dumps(command).encode('utf-8')
                writer.write(command_data)
                await writer.drain()
                
                # Receive response
                response_data = await asyncio.wait_for(
                    reader.read(4096),
                    timeout=timeout
                )
                
                response = json.loads(response_data.decode('utf-8'))
                return response
                
            finally:
                writer.close()
                await writer.wait_closed()
                
        except asyncio.TimeoutError:
            logger.error(f"⏰ IPC command timeout after {timeout}s")
            return {"success": False, "error": "IPC timeout"}
        except Exception as e:
            logger.error(f"❌ IPC command failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _wait_for_service_ready(self, max_wait: float = 30.0) -> bool:
        """Wait for monitoring service to be ready"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                # Check if process is still running
                if not self.is_process_running():
                    logger.error("❌ Monitor process died during startup")
                    return False
                
                # Try to get status
                response = await self._send_ipc_command({"command": "get_status"}, timeout=2.0)
                if response.get("success"):
                    logger.info("✅ Monitor service is ready")
                    return True
                
            except Exception:
                pass  # Continue waiting
            
            await asyncio.sleep(1.0)
        
        logger.error(f"⏰ Service not ready after {max_wait}s")
        return False
    
    async def _wait_for_process_exit(self):
        """Wait for process to exit (async wrapper)"""
        if self.process:
            while self.process.poll() is None:
                await asyncio.sleep(0.1)
    
    async def _health_monitor_loop(self):
        """Health monitoring loop"""
        logger.info("💚 Starting health monitoring")
        
        try:
            while not self._shutdown_requested:
                try:
                    # Check if process is still running
                    if not self.is_process_running():
                        logger.warning("⚠️ Monitor process died unexpectedly")
                        self.process_info.status = "error"
                        self.process_info.error_message = "Process died unexpectedly"
                        
                        # Auto-restart if enabled
                        if (self.auto_restart and 
                            self.process_info.restart_count < self.max_restart_attempts):
                            logger.info("🔄 Attempting auto-restart")
                            success = await self.restart_monitor_process()
                            if not success:
                                logger.error("❌ Auto-restart failed")
                        else:
                            logger.error("❌ Auto-restart disabled or max attempts reached")
                        
                        await asyncio.sleep(self.health_check_interval)
                        continue
                    
                    # Check service health via IPC
                    try:
                        response = await self._send_ipc_command({"command": "get_status"}, timeout=5.0)
                        if response.get("success"):
                            self.process_info.last_heartbeat = datetime.now()
                            self.process_info.status = "running"
                            
                            # Log health status periodically
                            status = response.get("status", {})
                            health = status.get("health_status", "unknown")
                            active = status.get("active", False)
                            detections = status.get("total_detections", 0)
                            
                            logger.debug(f"💚 Health check: {health}, active={active}, detections={detections}")
                        else:
                            logger.warning("⚠️ Health check failed - service not responding properly")
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Health check IPC error: {e}")
                    
                    await asyncio.sleep(self.health_check_interval)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"❌ Health monitor error: {e}")
                    await asyncio.sleep(self.health_check_interval)
                    
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("💚 Health monitoring stopped")

# Global manager instance
labjack_monitor_manager = LabJackMonitorManager()

# Convenience functions for backward compatibility
async def start_labjack_monitoring(session_id: str, sample_rate: float = 10.0) -> bool:
    """Start LabJack monitoring for a session"""
    return await labjack_monitor_manager.start_monitoring_session(session_id, sample_rate)

async def stop_labjack_monitoring() -> bool:
    """Stop LabJack monitoring"""
    return await labjack_monitor_manager.stop_monitoring_session()

async def get_labjack_monitoring_status() -> Dict[str, Any]:
    """Get LabJack monitoring status"""
    return await labjack_monitor_manager.get_monitoring_status()

async def ensure_monitor_process_running() -> bool:
    """Ensure monitoring process is running"""
    if not labjack_monitor_manager.is_process_running():
        return await labjack_monitor_manager.start_monitor_process()
    return True