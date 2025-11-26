"""
LabJack Monitoring API Endpoints

Provides REST API endpoints for controlling the standalone LabJack monitoring service.
Integrates with the monitoring manager to provide process and session control.

Author: AI Model Validation Platform Team
Version: 1.0.0
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

# Import the monitor manager
try:
    from services.labjack_monitor_manager import (
        labjack_monitor_manager,
        start_labjack_monitoring,
        stop_labjack_monitoring,
        get_labjack_monitoring_status,
        ensure_monitor_process_running
    )
    MONITOR_AVAILABLE = True
except ImportError as e:
    MONITOR_AVAILABLE = False
    logging.warning(f"LabJack monitoring not available: {e}")

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/labjack-monitor", tags=["LabJack Monitoring"])

# Pydantic models for API
class StartMonitoringRequest(BaseModel):
    """Request to start monitoring for a session"""
    session_id: str = Field(..., description="Test session ID to monitor")
    sample_rate: float = Field(10.0, ge=0.1, le=1000.0, description="Sample rate in Hz")

class MonitoringResponse(BaseModel):
    """Response for monitoring operations"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class ProcessControlRequest(BaseModel):
    """Request for process control operations"""
    sample_rate: float = Field(10.0, ge=0.1, le=1000.0, description="Sample rate in Hz")
    voltage_threshold: float = Field(3.0, ge=0.1, le=10.0, description="Voltage threshold in V")

def check_monitor_availability():
    """Dependency to check if monitoring is available"""
    if not MONITOR_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="LabJack monitoring service not available"
        )

@router.get("/status", response_model=MonitoringResponse)
async def get_monitoring_status():
    """Get current monitoring status and metrics"""
    try:
        if not MONITOR_AVAILABLE:
            return MonitoringResponse(
                success=False,
                message="LabJack monitoring service not available",
                data={"available": False}
            )
        
        status = await get_labjack_monitoring_status()
        
        return MonitoringResponse(
            success=True,
            message="Status retrieved successfully",
            data=status
        )
        
    except Exception as e:
        logger.error(f"Error getting monitoring status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=MonitoringResponse)
async def get_health_metrics(_: None = Depends(check_monitor_availability)):
    """Get detailed health metrics from monitoring service"""
    try:
        health = await labjack_monitor_manager.get_health_metrics()
        
        return MonitoringResponse(
            success=True,
            message="Health metrics retrieved successfully",
            data=health
        )
        
    except Exception as e:
        logger.error(f"Error getting health metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/start", response_model=MonitoringResponse)
async def start_monitor_process(
    request: ProcessControlRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(check_monitor_availability)
):
    """Start the monitoring process"""
    try:
        logger.info(f"Starting monitor process with sample_rate={request.sample_rate}Hz")
        
        success = await labjack_monitor_manager.start_monitor_process(
            sample_rate=request.sample_rate,
            voltage_threshold=request.voltage_threshold
        )
        
        if success:
            return MonitoringResponse(
                success=True,
                message="Monitor process started successfully"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to start monitor process")
            
    except Exception as e:
        logger.error(f"Error starting monitor process: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/stop", response_model=MonitoringResponse)
async def stop_monitor_process(_: None = Depends(check_monitor_availability)):
    """Stop the monitoring process"""
    try:
        logger.info("Stopping monitor process")
        
        success = await labjack_monitor_manager.stop_monitor_process()
        
        if success:
            return MonitoringResponse(
                success=True,
                message="Monitor process stopped successfully"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to stop monitor process")
            
    except Exception as e:
        logger.error(f"Error stopping monitor process: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/restart", response_model=MonitoringResponse)
async def restart_monitor_process(_: None = Depends(check_monitor_availability)):
    """Restart the monitoring process"""
    try:
        logger.info("Restarting monitor process")
        
        success = await labjack_monitor_manager.restart_monitor_process()
        
        if success:
            return MonitoringResponse(
                success=True,
                message="Monitor process restarted successfully"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to restart monitor process")
            
    except Exception as e:
        logger.error(f"Error restarting monitor process: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/session/start", response_model=MonitoringResponse)
async def start_monitoring_session(
    request: StartMonitoringRequest,
    _: None = Depends(check_monitor_availability)
):
    """Start monitoring for a specific test session"""
    try:
        logger.info(f"Starting monitoring for session {request.session_id}")
        
        # Ensure monitor process is running
        process_running = await ensure_monitor_process_running()
        if not process_running:
            raise HTTPException(status_code=500, detail="Failed to start monitor process")
        
        # Start monitoring session
        success = await start_labjack_monitoring(
            session_id=request.session_id,
            sample_rate=request.sample_rate
        )
        
        if success:
            return MonitoringResponse(
                success=True,
                message=f"Monitoring started for session {request.session_id}",
                data={
                    "session_id": request.session_id,
                    "sample_rate": request.sample_rate
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to start monitoring session")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting monitoring session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/session/stop", response_model=MonitoringResponse)
async def stop_monitoring_session(_: None = Depends(check_monitor_availability)):
    """Stop current monitoring session"""
    try:
        logger.info("Stopping monitoring session")
        
        success = await stop_labjack_monitoring()
        
        if success:
            return MonitoringResponse(
                success=True,
                message="Monitoring session stopped successfully"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to stop monitoring session")
            
    except Exception as e:
        logger.error(f"Error stopping monitoring session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/process/info", response_model=MonitoringResponse)
async def get_process_info(_: None = Depends(check_monitor_availability)):
    """Get information about the monitoring process"""
    try:
        is_running = labjack_monitor_manager.is_process_running()
        process_info = labjack_monitor_manager.process_info
        
        return MonitoringResponse(
            success=True,
            message="Process information retrieved successfully",
            data={
                "running": is_running,
                "pid": process_info.pid,
                "status": process_info.status,
                "start_time": process_info.start_time.isoformat() if process_info.start_time else None,
                "last_heartbeat": process_info.last_heartbeat.isoformat() if process_info.last_heartbeat else None,
                "restart_count": process_info.restart_count,
                "error_message": process_info.error_message
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting process info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config", response_model=MonitoringResponse)
async def get_monitor_config():
    """Get current monitoring configuration"""
    try:
        if not MONITOR_AVAILABLE:
            return MonitoringResponse(
                success=False,
                message="LabJack monitoring service not available",
                data={"available": False}
            )
        
        config = {
            "ipc_host": labjack_monitor_manager.ipc_host,
            "ipc_port": labjack_monitor_manager.ipc_port,
            "database_path": labjack_monitor_manager.database_path,
            "log_level": labjack_monitor_manager.log_level,
            "auto_restart": labjack_monitor_manager.auto_restart,
            "max_restart_attempts": labjack_monitor_manager.max_restart_attempts,
            "restart_delay": labjack_monitor_manager.restart_delay,
            "health_check_interval": labjack_monitor_manager.health_check_interval
        }
        
        return MonitoringResponse(
            success=True,
            message="Configuration retrieved successfully",
            data=config
        )
        
    except Exception as e:
        logger.error(f"Error getting monitor config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint for monitoring systems
@router.get("/ping")
async def ping():
    """Simple ping endpoint for health checks"""
    return {"status": "ok", "service": "labjack-monitor-api"}

# Startup and shutdown hooks for integration with main app
async def startup_monitor_service():
    """Startup hook to initialize monitoring service"""
    if MONITOR_AVAILABLE:
        logger.info("🚀 Initializing LabJack monitoring service on startup")
        try:
            # Clean up any zombie processes from previous runs
            logger.info("🧹 Cleaning up orphaned monitoring processes from previous sessions")
            labjack_monitor_manager.cleanup_zombie_processes()

            # Optionally start monitor process on startup
            # await labjack_monitor_manager.start_monitor_process()
            logger.info("✅ LabJack monitoring service ready")
        except Exception as e:
            logger.error(f"❌ Failed to initialize monitoring service: {e}")
    else:
        logger.warning("⚠️ LabJack monitoring service not available")

async def shutdown_monitor_service():
    """Shutdown hook to cleanup monitoring service"""
    if MONITOR_AVAILABLE:
        logger.info("🔄 Shutting down LabJack monitoring service")
        try:
            await labjack_monitor_manager.shutdown()
            logger.info("✅ LabJack monitoring service shutdown complete")
        except Exception as e:
            logger.error(f"❌ Error during monitoring service shutdown: {e}")

# Export router and hooks
__all__ = ["router", "startup_monitor_service", "shutdown_monitor_service"]