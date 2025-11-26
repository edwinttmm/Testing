"""
LabJack Detection Monitoring API Endpoints

REST API endpoints for managing LabJack detection monitoring sessions
and retrieving detection events for latency analysis.

Endpoints:
- POST /api/detection/start - Start detection monitoring
- POST /api/detection/stop - Stop detection monitoring  
- GET /api/detection/events - Get detection events
- GET /api/detection/status - Get monitoring status
- GET /api/detection/sessions - List all sessions
- DELETE /api/detection/session - Clean up session data
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from pydantic import BaseModel, Field

# Import detection monitoring service
from services.labjack_detection_service import (
    get_detection_monitor, 
    LabJackDetectionMonitor,
    DetectionConfig,
    DetectionStatus
)

# Import LabJack service for status checks
from services.labjack_service import get_labjack_service

logger = logging.getLogger(__name__)

# Create router for detection endpoints
detection_router = APIRouter(prefix="/api/detection", tags=["detection"])


# Pydantic models for request/response validation
class StartMonitoringRequest(BaseModel):
    """Request model for starting detection monitoring"""
    session_id: str = Field(..., description="Unique session identifier")
    channels: List[str] = Field(default=["AIN0", "AIN1"], description="LabJack channels to monitor")
    voltage_threshold: float = Field(default=2.5, ge=0.0, le=10.0, description="Detection voltage threshold in volts")
    debounce_ms: int = Field(default=100, ge=10, le=5000, description="Debounce time in milliseconds")
    sample_rate: int = Field(default=200, ge=100, le=10000, description="Sampling rate in Hz")
    enable_websocket: bool = Field(default=True, description="Enable WebSocket notifications")
    store_in_db: bool = Field(default=True, description="Store events in database")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional session metadata")
    constant_voltage_mode: bool = Field(default=False, description="Bypass debounce for constant voltage testing (100% detection rate)")


class StopMonitoringRequest(BaseModel):
    """Request model for stopping detection monitoring"""
    session_id: str = Field(..., description="Session identifier to stop")


class DetectionEventsResponse(BaseModel):
    """Response model for detection events"""
    session_id: str
    event_count: int
    events: List[Dict[str, Any]]


class MonitoringStatusResponse(BaseModel):
    """Response model for monitoring status"""
    session_id: str
    status: str
    active: bool
    event_count: int
    config: Optional[Dict[str, Any]] = None
    last_detection_times: Optional[Dict[str, Optional[str]]] = None


class DetectionStatistics(BaseModel):
    """Response model for detection statistics"""
    active_sessions: int
    total_sessions: int
    total_events: int
    labjack_connected: str
    labjack_mode: str


# Dependency for getting detection monitor
def get_monitor() -> LabJackDetectionMonitor:
    """Dependency to get detection monitor instance"""
    return get_detection_monitor()


@detection_router.post("/start", response_model=Dict[str, Any])
async def start_monitoring(
    request: StartMonitoringRequest,
    monitor: LabJackDetectionMonitor = Depends(get_monitor)
):
    """
    Start detection monitoring for a session
    
    This endpoint starts real-time monitoring of LabJack channels for detection events.
    Events are recorded when voltage exceeds the specified threshold.
    """
    try:
        # Check if LabJack service is connected
        labjack_service = get_labjack_service()
        if not labjack_service or labjack_service.status.name != 'CONNECTED':
            raise HTTPException(
                status_code=503,
                detail="LabJack hardware not connected. Please connect LabJack before starting monitoring."
            )
        
        # Start monitoring
        success = monitor.start_monitoring(
            session_id=request.session_id,
            channels=request.channels,
            voltage_threshold=request.voltage_threshold,
            debounce_ms=request.debounce_ms,
            sample_rate=request.sample_rate,
            enable_websocket=request.enable_websocket,
            store_in_db=request.store_in_db,
            metadata=request.metadata,
            constant_voltage_mode=request.constant_voltage_mode
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start monitoring for session {request.session_id}"
            )
        
        # Get session status
        status = monitor.get_session_status(request.session_id)
        
        logger.info(f"✅ Started detection monitoring for session {request.session_id}")
        
        return {
            "success": True,
            "message": f"Detection monitoring started for session {request.session_id}",
            "session_status": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting detection monitoring: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error starting monitoring: {str(e)}"
        )


@detection_router.post("/stop", response_model=Dict[str, Any])
async def stop_monitoring(
    request: StopMonitoringRequest,
    monitor: LabJackDetectionMonitor = Depends(get_monitor)
):
    """
    Stop detection monitoring for a session
    
    This endpoint stops real-time monitoring and preserves detection events
    for analysis and latency calculation.
    """
    try:
        success = monitor.stop_monitoring(request.session_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to stop monitoring for session {request.session_id}"
            )
        
        # Get final event count
        events = monitor.get_detection_events(request.session_id)
        event_count = len(events)
        
        logger.info(f"⏹️ Stopped detection monitoring for session {request.session_id} ({event_count} events)")
        
        return {
            "success": True,
            "message": f"Detection monitoring stopped for session {request.session_id}",
            "event_count": event_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping detection monitoring: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error stopping monitoring: {str(e)}"
        )


@detection_router.get("/events/{session_id}", response_model=DetectionEventsResponse)
async def get_detection_events(
    session_id: str,
    monitor: LabJackDetectionMonitor = Depends(get_monitor)
):
    """
    Get all detection events for a session
    
    Returns all recorded detection events with timestamps for latency analysis.
    Events include voltage readings, channels, and precise timestamps.
    """
    try:
        events = monitor.get_detection_events(session_id)
        
        return DetectionEventsResponse(
            session_id=session_id,
            event_count=len(events),
            events=events
        )
        
    except Exception as e:
        logger.error(f"Error getting detection events: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error retrieving events: {str(e)}"
        )


@detection_router.get("/status/{session_id}", response_model=MonitoringStatusResponse)
async def get_session_status(
    session_id: str,
    monitor: LabJackDetectionMonitor = Depends(get_monitor)
):
    """
    Get monitoring status for a specific session
    
    Returns current monitoring status, configuration, and recent detection information.
    """
    try:
        status_data = monitor.get_session_status(session_id)
        
        return MonitoringStatusResponse(
            session_id=status_data['session_id'],
            status=status_data['status'],
            active=status_data['active'],
            event_count=status_data['event_count'],
            config=status_data.get('config'),
            last_detection_times=status_data.get('last_detection_times')
        )
        
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error retrieving status: {str(e)}"
        )


@detection_router.get("/sessions", response_model=List[MonitoringStatusResponse])
async def get_all_sessions(
    monitor: LabJackDetectionMonitor = Depends(get_monitor)
):
    """
    Get status for all active monitoring sessions
    
    Returns a list of all active and recent monitoring sessions.
    """
    try:
        sessions_data = monitor.get_all_sessions()
        
        return [
            MonitoringStatusResponse(
                session_id=session['session_id'],
                status=session['status'],
                active=session['active'],
                event_count=session['event_count'],
                config=session.get('config'),
                last_detection_times=session.get('last_detection_times')
            )
            for session in sessions_data
        ]
        
    except Exception as e:
        logger.error(f"Error getting all sessions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error retrieving sessions: {str(e)}"
        )


@detection_router.get("/statistics", response_model=DetectionStatistics)
async def get_detection_statistics(
    monitor: LabJackDetectionMonitor = Depends(get_monitor)
):
    """
    Get overall detection monitoring statistics
    
    Returns system-wide statistics including active sessions, total events, 
    and LabJack connection status.
    """
    try:
        stats = monitor.get_statistics()
        
        return DetectionStatistics(
            active_sessions=stats['active_sessions'],
            total_sessions=stats['total_sessions'],
            total_events=stats['total_events'],
            labjack_connected=stats['labjack_connected'],
            labjack_mode=stats['labjack_mode']
        )
        
    except Exception as e:
        logger.error(f"Error getting detection statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error retrieving statistics: {str(e)}"
        )


@detection_router.delete("/session/{session_id}", response_model=Dict[str, Any])
async def cleanup_session_data(
    session_id: str,
    monitor: LabJackDetectionMonitor = Depends(get_monitor)
):
    """
    Clean up all data for a monitoring session
    
    Removes all stored detection events and session data. Use with caution
    as this permanently deletes detection event history.
    """
    try:
        # Stop monitoring if active
        if session_id in monitor.active_sessions:
            monitor.stop_monitoring(session_id)
        
        # Clean up all session data
        monitor.cleanup_session_data(session_id)
        
        logger.info(f"🧹 Cleaned up session data for {session_id}")
        
        return {
            "success": True,
            "message": f"Session data cleaned up for {session_id}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up session data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error cleaning up session: {str(e)}"
        )


@detection_router.get("/health", response_model=Dict[str, Any])
async def detection_health_check():
    """
    Health check endpoint for detection monitoring service
    
    Returns the health status of the detection monitoring system and LabJack connection.
    """
    try:
        # Check LabJack service status
        labjack_service = get_labjack_service()
        labjack_status = "unknown"
        labjack_connected = False
        
        if labjack_service:
            labjack_status = labjack_service.status.name
            labjack_connected = labjack_service.status.name == 'CONNECTED'
        
        # Check detection monitor
        monitor = get_detection_monitor()
        stats = monitor.get_statistics()
        
        return {
            "service": "detection_monitoring",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "labjack": {
                "connected": labjack_connected,
                "status": labjack_status,
                "mode": stats['labjack_mode']
            },
            "monitoring": {
                "active_sessions": stats['active_sessions'],
                "total_events": stats['total_events']
            }
        }
        
    except Exception as e:
        logger.error(f"Detection health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "service": "detection_monitoring",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


# Export the router for inclusion in main app
__all__ = ["detection_router"]