"""
Monitoring Service Management Endpoints
=====================================

API endpoints for managing the dedicated monitoring service lifecycle,
health checks, and status monitoring.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging

from services.monitoring_process_manager import monitoring_process_manager
from services.monitoring_service_client import monitoring_service_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitoring", tags=["Monitoring Service"])

# ============================================================================
# SERVICE LIFECYCLE MANAGEMENT
# ============================================================================

@router.post("/service/start")
async def start_monitoring_service(
    auto_restart: bool = Query(True, description="Enable automatic restart on failure")
):
    """Start the dedicated monitoring service process"""
    try:
        logger.info("🚀 Starting monitoring service via API...")
        result = await monitoring_process_manager.start_service(auto_restart=auto_restart)
        
        if result.get("success"):
            return {
                "status": "started",
                "message": result.get("message"),
                "pid": result.get("pid"),
                "auto_restart": auto_restart,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to start monitoring service: {result.get('error')}"
            )
            
    except Exception as e:
        logger.error(f"❌ Error starting monitoring service: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/service/stop")
async def stop_monitoring_service(
    timeout: float = Query(10.0, description="Graceful shutdown timeout in seconds")
):
    """Stop the dedicated monitoring service process"""
    try:
        logger.info("⏹️ Stopping monitoring service via API...")
        result = await monitoring_process_manager.stop_service(timeout=timeout)
        
        return {
            "status": "stopped",
            "message": result.get("message"),
            "success": result.get("success"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error stopping monitoring service: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/service/restart")
async def restart_monitoring_service():
    """Restart the dedicated monitoring service process"""
    try:
        logger.info("🔄 Restarting monitoring service via API...")
        result = await monitoring_process_manager.restart_service()
        
        if result.get("success"):
            return {
                "status": "restarted",
                "message": result.get("message"),
                "pid": result.get("pid"),
                "restart_count": monitoring_process_manager._restart_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to restart monitoring service: {result.get('error')}"
            )
            
    except Exception as e:
        logger.error(f"❌ Error restarting monitoring service: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# SERVICE STATUS AND HEALTH
# ============================================================================

@router.get("/service/status")
async def get_monitoring_service_status():
    """Get comprehensive status of the monitoring service and process"""
    try:
        # Get process status
        process_status = await monitoring_process_manager.get_service_status()
        
        # Get service status if available
        service_status = None
        if process_status.get("process_running"):
            try:
                service_status = await monitoring_service_manager.get_monitoring_status()
            except Exception as e:
                service_status = {"error": str(e), "available": False}
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "process": process_status,
            "service": service_status,
            "overall_status": _determine_overall_status(process_status, service_status)
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting monitoring service status: {e}")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
            "overall_status": "error"
        }

@router.get("/service/health")
async def monitoring_service_health_check():
    """Comprehensive health check for monitoring service"""
    try:
        health_result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "dedicated_monitoring_service",
            "checks": {}
        }
        
        # Check if process is running
        process_running = monitoring_process_manager.is_process_running()
        health_result["checks"]["process_running"] = {
            "status": "pass" if process_running else "fail",
            "message": "Process is running" if process_running else "Process is not running"
        }
        
        # Check service responsiveness
        if process_running:
            try:
                service_health = await monitoring_service_manager.client.health_check()
                health_result["checks"]["service_responsive"] = {
                    "status": "pass" if service_health.get("service_status") == "healthy" else "warn",
                    "message": f"Service status: {service_health.get('service_status', 'unknown')}",
                    "details": service_health
                }
            except Exception as e:
                health_result["checks"]["service_responsive"] = {
                    "status": "fail",
                    "message": f"Service not responsive: {e}"
                }
        else:
            health_result["checks"]["service_responsive"] = {
                "status": "fail",
                "message": "Cannot check responsiveness - process not running"
            }
        
        # Check IPC communication
        try:
            ipc_test = await monitoring_service_manager.client._send_command({"command": "get_status"})
            health_result["checks"]["ipc_communication"] = {
                "status": "pass" if not ipc_test.get("error") else "fail",
                "message": "IPC communication working" if not ipc_test.get("error") else f"IPC error: {ipc_test.get('error')}"
            }
        except Exception as e:
            health_result["checks"]["ipc_communication"] = {
                "status": "fail", 
                "message": f"IPC communication failed: {e}"
            }
        
        # Determine overall health
        failed_checks = [check for check in health_result["checks"].values() if check["status"] == "fail"]
        warning_checks = [check for check in health_result["checks"].values() if check["status"] == "warn"]
        
        if failed_checks:
            health_result["overall_status"] = "unhealthy"
            health_result["issues"] = len(failed_checks)
        elif warning_checks:
            health_result["overall_status"] = "degraded"
            health_result["warnings"] = len(warning_checks)
        else:
            health_result["overall_status"] = "healthy"
        
        return health_result
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "dedicated_monitoring_service",
            "overall_status": "error",
            "error": str(e)
        }

@router.post("/service/ensure-available")
async def ensure_monitoring_service_available():
    """Ensure monitoring service is available, starting it if necessary"""
    try:
        logger.info("🔧 Ensuring monitoring service is available...")
        
        available = await monitoring_process_manager.ensure_service_available(start_if_needed=True)
        
        if available:
            status = await monitoring_service_manager.get_monitoring_status()
            return {
                "status": "available",
                "message": "Monitoring service is available and responsive",
                "service_status": status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            raise HTTPException(
                status_code=503,
                detail="Could not ensure monitoring service availability"
            )
            
    except Exception as e:
        logger.error(f"❌ Error ensuring service availability: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# MONITORING OPERATIONS
# ============================================================================

@router.post("/sessions/{session_id}/start")
async def start_session_monitoring(
    session_id: str,
    sample_rate: int = Query(10, description="Sampling rate in Hz"),
    wait_for_service: bool = Query(True, description="Wait for service to be available")
):
    """Start monitoring for a specific test session"""
    try:
        logger.info(f"📊 Starting monitoring for session {session_id}...")
        
        # Ensure service is available if requested
        if wait_for_service:
            service_available = await monitoring_process_manager.ensure_service_available()
            if not service_available:
                raise HTTPException(
                    status_code=503,
                    detail="Monitoring service is not available and could not be started"
                )
        
        # Start session monitoring
        result = await monitoring_service_manager.start_session_monitoring(
            session_id=session_id,
            sample_rate=sample_rate,
            wait_for_service=wait_for_service
        )
        
        if result.get("success"):
            return {
                "status": "monitoring_started",
                "session_id": session_id,
                "sample_rate": sample_rate,
                "message": result.get("message"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start session monitoring: {result.get('error')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error starting session monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/stop")
async def stop_session_monitoring():
    """Stop current session monitoring"""
    try:
        logger.info("⏹️ Stopping session monitoring...")
        
        result = await monitoring_service_manager.stop_session_monitoring()
        
        return {
            "status": "monitoring_stopped",
            "session_id": result.get("session_id"),
            "detection_count": result.get("detection_count", 0),
            "message": result.get("message"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error stopping session monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/current")
async def get_current_monitoring_session():
    """Get information about the currently monitored session"""
    try:
        status = await monitoring_service_manager.get_monitoring_status()
        
        return {
            "monitoring_active": status.get("monitoring_active", False),
            "session_id": status.get("session_id"),
            "detection_count": status.get("detection_count", 0),
            "service_available": status.get("service_available", False),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting current monitoring session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def _determine_overall_status(process_status: Dict[str, Any], service_status: Optional[Dict[str, Any]]) -> str:
    """Determine overall monitoring service status"""
    
    if not process_status.get("process_running"):
        return "stopped"
    
    if process_status.get("error"):
        return "error"
    
    if service_status is None:
        return "starting"
    
    if service_status.get("error") or not service_status.get("service_available"):
        return "unhealthy"
    
    health_status = service_status.get("health_status", "unknown")
    
    if health_status == "healthy":
        return "healthy"
    elif health_status == "degraded":
        return "degraded"
    else:
        return "unknown"

# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@router.get("/health")
async def monitoring_endpoints_health():
    """Health check for monitoring service endpoints"""
    return {
        "status": "healthy",
        "service": "Monitoring Service Endpoints",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints": [
            "POST /api/monitoring/service/start - Start monitoring service",
            "POST /api/monitoring/service/stop - Stop monitoring service", 
            "POST /api/monitoring/service/restart - Restart monitoring service",
            "GET /api/monitoring/service/status - Get service status",
            "GET /api/monitoring/service/health - Health check",
            "POST /api/monitoring/service/ensure-available - Ensure service availability",
            "POST /api/monitoring/sessions/{id}/start - Start session monitoring",
            "POST /api/monitoring/sessions/stop - Stop session monitoring",
            "GET /api/monitoring/sessions/current - Get current session info"
        ]
    }