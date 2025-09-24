#!/usr/bin/env python3
"""
LabJack Service Manager
======================

Central management service for coordinating LabJack monitoring across test sessions.
Handles service lifecycle, health monitoring, resource allocation, and session coordination.

Key Features:
- Service process lifecycle management
- Health monitoring and auto-recovery
- Session coordination and resource allocation
- Service configuration management
- Logging and diagnostics
- Process isolation and cleanup

Architecture:
- Manages dedicated monitoring processes per session
- Provides unified API for service control
- Handles process health monitoring
- Implements service recovery strategies
- Coordinates with main backend workflow
"""

import asyncio
import logging
import os
import signal
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import threading
import subprocess
import psutil

from .labjack_monitor_client import LabJackMonitorManager, LabJackMonitorClient

logger = logging.getLogger(__name__)

@dataclass
class ServiceInstance:
    """Information about a running service instance"""
    session_id: str
    process_id: int
    socket_path: str
    start_time: float
    config: Dict[str, Any]
    status: str = "starting"  # starting, running, stopping, stopped, failed
    last_health_check: float = 0
    health_status: Optional[Dict[str, Any]] = None
    restart_count: int = 0

class LabJackServiceManager:
    """Central manager for LabJack monitoring services"""
    
    def __init__(self):
        self.services: Dict[str, ServiceInstance] = {}
        self.managers: Dict[str, LabJackMonitorManager] = {}
        self.running = False
        self.health_check_interval = 10.0  # seconds
        self.health_check_thread = None
        self.max_restart_attempts = 3
        self.restart_cooldown = 30.0  # seconds
        
        # Service configuration defaults
        self.default_config = {
            "sample_rate": 10.0,
            "voltage_threshold": 3.0,
            "channels": ["AIN0"],
            "database_path": "dev_database.db",
            "max_buffer_size": 1000,
            "enable_recovery": True,
            "max_retries": 3,
            "retry_delay": 1.0
        }
        
        logger.info("LabJack Service Manager initialized")
    
    def start_manager(self):
        """Start the service manager"""
        if self.running:
            logger.warning("Service manager is already running")
            return
        
        self.running = True
        
        # Start health check thread
        self.health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="LabJackHealthCheck"
        )
        self.health_check_thread.start()
        
        logger.info("LabJack Service Manager started")
    
    def stop_manager(self):
        """Stop the service manager and all services"""
        if not self.running:
            return
        
        logger.info("Stopping LabJack Service Manager...")
        self.running = False
        
        # Stop all services
        asyncio.create_task(self.stop_all_services())
        
        # Wait for health check thread to finish
        if self.health_check_thread and self.health_check_thread.is_alive():
            self.health_check_thread.join(timeout=5)
        
        logger.info("LabJack Service Manager stopped")
    
    async def start_monitoring_for_session(
        self,
        session_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Start monitoring service for a specific test session"""
        
        if session_id in self.services:
            logger.warning(f"Monitoring service already exists for session {session_id}\")\n            return False\n        \n        try:\n            # Prepare configuration\n            service_config = self.default_config.copy()\n            if config:\n                service_config.update(config)\n            \n            # Generate unique socket path\n            socket_path = f\"/tmp/labjack_monitor_{session_id}.sock\"\n            service_config[\"socket_path\"] = socket_path\n            \n            # Create manager instance\n            manager = LabJackMonitorManager(socket_path)\n            \n            # Start the service\n            logger.info(f\"Starting LabJack monitoring service for session {session_id}\")\n            success = await manager.start_monitoring_service(session_id, service_config)\n            \n            if success:\n                # Create service instance record\n                service_instance = ServiceInstance(\n                    session_id=session_id,\n                    process_id=manager.service_process.pid,\n                    socket_path=socket_path,\n                    start_time=time.time(),\n                    config=service_config,\n                    status=\"running\"\n                )\n                \n                self.services[session_id] = service_instance\n                self.managers[session_id] = manager\n                \n                logger.info(f\"LabJack monitoring service started for session {session_id} (PID: {service_instance.process_id})\")\n                return True\n            else:\n                logger.error(f\"Failed to start monitoring service for session {session_id}\")\n                return False\n                \n        except Exception as e:\n            logger.error(f\"Error starting monitoring service for session {session_id}: {e}\")\n            return False\n    \n    async def stop_monitoring_for_session(self, session_id: str) -> bool:\n        \"\"\"Stop monitoring service for a specific test session\"\"\"\n        \n        if session_id not in self.services:\n            logger.warning(f\"No monitoring service found for session {session_id}\")\n            return False\n        \n        try:\n            service = self.services[session_id]\n            manager = self.managers.get(session_id)\n            \n            logger.info(f\"Stopping LabJack monitoring service for session {session_id}\")\n            \n            service.status = \"stopping\"\n            \n            if manager:\n                await manager.stop_monitoring_service()\n            \n            # Clean up\n            del self.services[session_id]\n            if session_id in self.managers:\n                del self.managers[session_id]\n            \n            logger.info(f\"LabJack monitoring service stopped for session {session_id}\")\n            return True\n            \n        except Exception as e:\n            logger.error(f\"Error stopping monitoring service for session {session_id}: {e}\")\n            return False\n    \n    async def stop_all_services(self):\n        \"\"\"Stop all running monitoring services\"\"\"\n        session_ids = list(self.services.keys())\n        \n        for session_id in session_ids:\n            await self.stop_monitoring_for_session(session_id)\n    \n    async def get_service_status(self, session_id: str) -> Optional[Dict[str, Any]]:\n        \"\"\"Get status for a specific service\"\"\"\n        \n        if session_id not in self.services:\n            return None\n        \n        service = self.services[session_id]\n        manager = self.managers.get(session_id)\n        \n        status = {\n            \"session_id\": session_id,\n            \"process_id\": service.process_id,\n            \"socket_path\": service.socket_path,\n            \"start_time\": service.start_time,\n            \"uptime\": time.time() - service.start_time,\n            \"status\": service.status,\n            \"config\": service.config,\n            \"restart_count\": service.restart_count,\n            \"last_health_check\": service.last_health_check,\n            \"health_status\": service.health_status\n        }\n        \n        if manager:\n            try:\n                detailed_status = await manager.get_service_status()\n                status.update(detailed_status)\n            except Exception as e:\n                status[\"health_error\"] = str(e)\n        \n        return status\n    \n    async def get_all_services_status(self) -> List[Dict[str, Any]]:\n        \"\"\"Get status for all services\"\"\"\n        statuses = []\n        \n        for session_id in self.services.keys():\n            status = await self.get_service_status(session_id)\n            if status:\n                statuses.append(status)\n        \n        return statuses\n    \n    async def get_service_statistics(self, session_id: str) -> Optional[Dict[str, Any]]:\n        \"\"\"Get statistics for a specific service\"\"\"\n        \n        if session_id not in self.managers:\n            return None\n        \n        manager = self.managers[session_id]\n        \n        try:\n            return await manager.get_monitoring_statistics()\n        except Exception as e:\n            logger.error(f\"Error getting statistics for session {session_id}: {e}\")\n            return None\n    \n    async def get_recent_detections(self, session_id: str, count: int = 10) -> List[Dict[str, Any]]:\n        \"\"\"Get recent detections for a specific service\"\"\"\n        \n        if session_id not in self.managers:\n            return []\n        \n        manager = self.managers[session_id]\n        \n        try:\n            return await manager.get_recent_detections(count)\n        except Exception as e:\n            logger.error(f\"Error getting detections for session {session_id}: {e}\")\n            return []\n    \n    def _health_check_loop(self):\n        \"\"\"Background health check loop\"\"\"\n        logger.info(\"Started health check loop\")\n        \n        while self.running:\n            try:\n                # Check each service\n                for session_id in list(self.services.keys()):\n                    asyncio.create_task(self._check_service_health(session_id))\n                \n                time.sleep(self.health_check_interval)\n                \n            except Exception as e:\n                logger.error(f\"Health check loop error: {e}\")\n                time.sleep(5)  # Back off on error\n        \n        logger.info(\"Health check loop ended\")\n    \n    async def _check_service_health(self, session_id: str):\n        \"\"\"Check health of a specific service\"\"\"\n        \n        if session_id not in self.services:\n            return\n        \n        service = self.services[session_id]\n        manager = self.managers.get(session_id)\n        \n        try:\n            if manager:\n                health_status = await manager.get_service_status()\n                service.health_status = health_status\n                service.last_health_check = time.time()\n                \n                # Check if service is healthy\n                if not health_status.get(\"service_running\", False):\n                    logger.warning(f\"Service {session_id} is not running\")\n                    service.status = \"failed\"\n                    \n                    # Attempt restart if within limits\n                    if service.restart_count < self.max_restart_attempts:\n                        logger.info(f\"Attempting to restart service {session_id} (attempt {service.restart_count + 1})\")\n                        await self._restart_service(session_id)\n                    else:\n                        logger.error(f\"Service {session_id} exceeded restart attempts, marking as failed\")\n                        service.status = \"failed\"\n                \n                elif not health_status.get(\"monitoring_active\", False):\n                    logger.warning(f\"Service {session_id} is running but not monitoring\")\n                    service.status = \"degraded\"\n                    \n                else:\n                    service.status = \"running\"\n                    \n            else:\n                logger.warning(f\"No manager found for service {session_id}\")\n                service.status = \"failed\"\n                \n        except Exception as e:\n            logger.error(f\"Health check failed for service {session_id}: {e}\")\n            service.status = \"failed\"\n    \n    async def _restart_service(self, session_id: str) -> bool:\n        \"\"\"Attempt to restart a failed service\"\"\"\n        \n        if session_id not in self.services:\n            return False\n        \n        service = self.services[session_id]\n        \n        # Check restart cooldown\n        if time.time() - service.start_time < self.restart_cooldown:\n            logger.info(f\"Service {session_id} in restart cooldown, skipping\")\n            return False\n        \n        try:\n            logger.info(f\"Restarting service {session_id}\")\n            \n            # Stop existing service\n            await self.stop_monitoring_for_session(session_id)\n            \n            # Wait a moment\n            await asyncio.sleep(1)\n            \n            # Start new service with same config\n            success = await self.start_monitoring_for_session(session_id, service.config)\n            \n            if success:\n                # Update restart count\n                new_service = self.services[session_id]\n                new_service.restart_count = service.restart_count + 1\n                logger.info(f\"Service {session_id} restarted successfully\")\n                return True\n            else:\n                logger.error(f\"Failed to restart service {session_id}\")\n                return False\n                \n        except Exception as e:\n            logger.error(f\"Error restarting service {session_id}: {e}\")\n            return False\n    \n    def get_manager_status(self) -> Dict[str, Any]:\n        \"\"\"Get overall manager status\"\"\"\n        return {\n            \"running\": self.running,\n            \"total_services\": len(self.services),\n            \"services\": {\n                session_id: {\n                    \"status\": service.status,\n                    \"uptime\": time.time() - service.start_time,\n                    \"restart_count\": service.restart_count\n                }\n                for session_id, service in self.services.items()\n            },\n            \"health_check_interval\": self.health_check_interval,\n            \"max_restart_attempts\": self.max_restart_attempts\n        }\n    \n    def cleanup_zombie_processes(self):\n        \"\"\"Clean up any zombie LabJack monitoring processes\"\"\"\n        try:\n            # Find processes with LabJack monitor in name\n            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):\n                try:\n                    if proc.info['name'] and 'python' in proc.info['name']:\n                        if proc.info['cmdline'] and any('dedicated_labjack_monitor' in arg for arg in proc.info['cmdline']):\n                            # Check if this process is managed by us\n                            pid = proc.info['pid']\n                            managed = any(service.process_id == pid for service in self.services.values())\n                            \n                            if not managed:\n                                logger.warning(f\"Found unmanaged LabJack monitor process (PID: {pid}), terminating\")\n                                proc.terminate()\n                                \n                except (psutil.NoSuchProcess, psutil.AccessDenied):\n                    continue\n                    \n        except Exception as e:\n            logger.error(f\"Error cleaning up zombie processes: {e}\")\n\n# Global service manager instance\nlabjack_service_manager = LabJackServiceManager()