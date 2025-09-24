#!/usr/bin/env python3
"""
LabJack Monitoring Service API Endpoints
========================================

REST API endpoints for managing and monitoring the dedicated LabJack monitoring service.
Provides comprehensive control and status information for HIL test monitoring.

Features:
- Service lifecycle management
- Real-time monitoring status
- Service health checks
- Statistics and metrics
- Recent detection data
- Service configuration management
- Error handling and recovery
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

# Import the service manager
from ..services.labjack_service_manager import labjack_service_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/labjack-monitoring", tags=["LabJack Monitoring"])

@router.get("/status")
async def get_monitoring_status():
    """Get overall monitoring service manager status"""
    try:
        status = labjack_service_manager.get_manager_status()
        return {
            "success": True,
            "data": status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting monitoring status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/services")
async def list_monitoring_services():
    """List all active monitoring services"""
    try:
        services = await labjack_service_manager.get_all_services_status()
        return {
            "success": True,
            "data": {
                "services": services,
                "total_services": len(services)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error listing monitoring services: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/services/{session_id}")
async def get_service_status(session_id: str):
    """Get status for a specific monitoring service"""
    try:
        status = await labjack_service_manager.get_service_status(session_id)
        
        if status is None:
            raise HTTPException(
                status_code=404,
                detail=f"No monitoring service found for session {session_id}"
            )
        
        return {
            "success": True,
            "data": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting service status for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/services/{session_id}/start")
async def start_monitoring_service(
    session_id: str,
    config: Optional[Dict[str, Any]] = None
):
    """Start monitoring service for a test session"""
    try:
        # Initialize service manager if not running
        if not labjack_service_manager.running:
            labjack_service_manager.start_manager()
        
        # Default configuration for HIL testing
        default_config = {
            "sample_rate": 10.0,  # 10Hz for HIL requirements
            "voltage_threshold": 3.0,  # TTL high threshold
            "channels": ["AIN0"],
            "database_path": "dev_database.db",
            "enable_recovery": True,
            "max_retries": 3
        }
        
        if config:
            default_config.update(config)
        
        success = await labjack_service_manager.start_monitoring_for_session(
            session_id,
            default_config
        )
        
        if success:
            # Get service status to return details
            status = await labjack_service_manager.get_service_status(session_id)
            
            return {
                "success": True,
                "message": f"Monitoring service started for session {session_id}",
                "data": {
                    "session_id": session_id,
                    "config": default_config,
                    "status": status
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start monitoring service for session {session_id}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting monitoring service for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/services/{session_id}/stop")
async def stop_monitoring_service(session_id: str):
    """Stop monitoring service for a test session"""
    try:
        success = await labjack_service_manager.stop_monitoring_for_session(session_id)
        
        if success:
            return {
                "success": True,
                "message": f"Monitoring service stopped for session {session_id}",
                "data": {
                    "session_id": session_id,
                    "stopped_at": datetime.utcnow().isoformat()
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No monitoring service found for session {session_id}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping monitoring service for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/services/{session_id}/statistics")
async def get_service_statistics(session_id: str):
    """Get detailed statistics for a monitoring service"""
    try:
        stats = await labjack_service_manager.get_service_statistics(session_id)
        
        if stats is None:
            raise HTTPException(
                status_code=404,
                detail=f"No monitoring service found for session {session_id}"
            )
        
        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "statistics": stats
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting statistics for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/services/{session_id}/detections")
async def get_recent_detections(
    session_id: str,
    count: int = Query(10, ge=1, le=1000, description="Number of recent detections to return")
):
    """Get recent detection events for a monitoring service"""
    try:
        detections = await labjack_service_manager.get_recent_detections(session_id, count)
        
        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "detections": detections,
                "count": len(detections)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting detections for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/manager/start")
async def start_service_manager():
    """Start the monitoring service manager"""
    try:
        if labjack_service_manager.running:
            return {
                "success": True,
                "message": "Service manager is already running",
                "data": labjack_service_manager.get_manager_status(),
                "timestamp": datetime.utcnow().isoformat()
            }
        
        labjack_service_manager.start_manager()
        
        return {
            "success": True,
            "message": "Monitoring service manager started",
            "data": labjack_service_manager.get_manager_status(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting service manager: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/manager/stop")
async def stop_service_manager():
    """Stop the monitoring service manager and all services"""
    try:
        if not labjack_service_manager.running:
            return {
                "success": True,
                "message": "Service manager is already stopped",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        labjack_service_manager.stop_manager()
        
        return {
            "success": True,
            "message": "Monitoring service manager stopped",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error stopping service manager: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup")
async def cleanup_zombie_processes():
    """Clean up any orphaned LabJack monitoring processes"""
    try:
        labjack_service_manager.cleanup_zombie_processes()
        
        return {
            "success": True,
            "message": "Zombie process cleanup completed",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up processes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Health check endpoint for the monitoring service"""
    try:
        manager_status = labjack_service_manager.get_manager_status()
        
        # Determine overall health
        healthy = manager_status.get("running", False)
        total_services = manager_status.get("total_services", 0)
        
        # Count healthy services
        healthy_services = 0
        for service_info in manager_status.get("services", {}).values():
            if service_info.get("status") == "running":
                healthy_services += 1
        
        health_status = "healthy" if healthy and (total_services == 0 or healthy_services > 0) else "unhealthy"
        
        return {
            "success": True,
            "data": {
                "status": health_status,
                "manager_running": healthy,
                "total_services": total_services,
                "healthy_services": healthy_services,
                "details": manager_status
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "success": False,
            "data": {
                "status": "unhealthy",
                "error": str(e)
            },
            "timestamp": datetime.utcnow().isoformat()
        }