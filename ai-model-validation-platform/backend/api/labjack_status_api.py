"""
LabJack Hardware Status API Endpoints
PRD Module 3.1 & 3.2 Implementation

REST API endpoints for monitoring LabJack hardware status, device information,
and precision timing capabilities for HIL testing.

Endpoints:
- GET /api/labjack/status - Get hardware status ("Connected" or "Not Detected")
- GET /api/labjack/devices - Detect and list available devices
- POST /api/labjack/connect - Connect to specific device
- POST /api/labjack/disconnect - Disconnect from device
- GET /api/labjack/device-info - Get detailed device information
- GET /api/labjack/channels - Get channel configuration
- POST /api/labjack/channels/configure - Configure channels
- GET /api/labjack/health - Health check endpoint
- GET /api/labjack/statistics - Get hardware statistics
- POST /api/labjack/monitoring/start - Start precision monitoring
- POST /api/labjack/monitoring/stop - Stop precision monitoring
- GET /api/labjack/events - Get hardware events
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from pydantic import BaseModel, Field

# Import LabJack hardware service
from services.labjack_hardware_service import (
    get_labjack_hardware_service,
    LabJackHardwareService,
    HardwareConnectionStatus,
    ChannelConfiguration,
    initialize_hardware_service
)

# Import video-hardware sync service
from services.video_hardware_sync_service import (
    get_video_hardware_sync_service,
    SyncConfiguration
)

logger = logging.getLogger(__name__)

# Create router for LabJack status endpoints
labjack_router = APIRouter(prefix="/api/labjack", tags=["labjack", "hardware"])


# Pydantic models for request/response validation
class DeviceConnectionRequest(BaseModel):
    """Request model for device connection"""
    device_type: str = Field(default="ANY", description="Device type (T7, U6, T4, ANY)")
    connection_type: str = Field(default="ANY", description="Connection type (USB, ETHERNET, WIFI, ANY)")
    identifier: str = Field(default="ANY", description="Device identifier (serial number, IP, or ANY)")


class ChannelConfigRequest(BaseModel):
    """Request model for channel configuration"""
    channels: Dict[str, Dict[str, Any]] = Field(
        ..., 
        description="Channel configurations (channel_name -> config dict)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "channels": {
                    "AIN0": {
                        "voltage_range": 10.0,
                        "resolution_index": 0,
                        "settling_time_us": 0,
                        "threshold_voltage": 2.5,
                        "enabled": True
                    },
                    "DIO0": {
                        "threshold_voltage": 3.3,
                        "enabled": True
                    }
                }
            }
        }


class PrecisionMonitoringRequest(BaseModel):
    """Request model for precision monitoring"""
    session_id: str = Field(..., description="Test session identifier")
    channels: List[str] = Field(default=["AIN0"], description="Channels to monitor")
    threshold_voltage: float = Field(default=2.5, ge=0.0, le=10.0, description="Detection threshold in volts")
    sample_rate: int = Field(default=10000, ge=100, le=50000, description="Sample rate in Hz")
    enable_sync: bool = Field(default=False, description="Enable video-hardware synchronization")
    video_source: Optional[str] = Field(default=None, description="Video source for synchronization")


class HardwareStatusResponse(BaseModel):
    """Response model for hardware status"""
    connection_status: str  # "Connected" or "Not Detected" - PRD requirement
    is_connected: bool
    status_details: Dict[str, Any]
    device_info: Dict[str, Any]
    timestamp: str


class DeviceListResponse(BaseModel):
    """Response model for device list"""
    devices_found: int
    devices: List[Dict[str, Any]]
    timestamp: str


class StatisticsResponse(BaseModel):
    """Response model for hardware statistics"""
    connection_stats: Dict[str, Any]
    monitoring_stats: Dict[str, Any] 
    performance_stats: Dict[str, Any]
    timestamp: str


@labjack_router.get("/status", response_model=HardwareStatusResponse)
async def get_hardware_status():
    """
    Get LabJack hardware status - PRD Module 3.1 requirement
    
    Returns connection status as "Connected" or "Not Detected"
    along with detailed device information and monitoring status.
    """
    try:
        service = get_labjack_hardware_service()
        status = service.get_status()
        
        return HardwareStatusResponse(
            connection_status=status["connection_status"],  # PRD requirement
            is_connected=status["is_connected"],
            status_details=status["connection_details"],
            device_info=status["device_info"],
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting hardware status: {e}")
        return HardwareStatusResponse(
            connection_status="Not Detected",
            is_connected=False,
            status_details={"error": str(e)},
            device_info={},
            timestamp=datetime.now().isoformat()
        )


@labjack_router.get("/devices", response_model=DeviceListResponse) 
async def detect_devices():
    """
    Detect available LabJack devices
    
    Scans for connected LabJack hardware and returns device information
    including device type, connection method, and serial numbers.
    """
    try:
        service = get_labjack_hardware_service()
        devices = service.detect_devices()
        
        logger.info(f"🔍 Device detection completed: {len(devices)} device(s) found")
        
        return DeviceListResponse(
            devices_found=len(devices),
            devices=devices,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error detecting devices: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Device detection failed: {str(e)}"
        )


@labjack_router.post("/connect", response_model=Dict[str, Any])
async def connect_device(request: DeviceConnectionRequest):
    """
    Connect to specific LabJack device
    
    Establishes connection to LabJack hardware using specified parameters.
    Updates connection status and initializes device for HIL testing.
    """
    try:
        service = get_labjack_hardware_service()
        
        success = service.connect(
            device_type=request.device_type,
            connection_type=request.connection_type,
            identifier=request.identifier
        )
        
        if success:
            status = service.get_status()
            logger.info(f"✅ Successfully connected to LabJack device")
            
            return {
                "success": True,
                "message": "Successfully connected to LabJack device",
                "connection_status": status["connection_status"],
                "device_info": status["device_info"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=503,
                detail="Failed to connect to LabJack device"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Connection error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Connection failed: {str(e)}"
        )


@labjack_router.post("/disconnect", response_model=Dict[str, Any])
async def disconnect_device():
    """
    Disconnect from LabJack device
    
    Safely disconnects from LabJack hardware, stops any active monitoring,
    and cleans up resources.
    """
    try:
        service = get_labjack_hardware_service()
        success = service.disconnect()
        
        if success:
            logger.info("🔌 LabJack device disconnected")
            return {
                "success": True,
                "message": "LabJack device disconnected successfully",
                "connection_status": "Not Detected",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to disconnect LabJack device"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Disconnect error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Disconnect failed: {str(e)}"
        )


@labjack_router.get("/device-info", response_model=Dict[str, Any])
async def get_device_info():
    """
    Get detailed device information
    
    Returns comprehensive information about connected LabJack device
    including firmware versions, capabilities, and hardware specifications.
    """
    try:
        service = get_labjack_hardware_service()
        
        if not service.is_connected():
            raise HTTPException(
                status_code=503,
                detail="No LabJack device connected"
            )
        
        device_info = service.get_device_info()
        
        return {
            "device_info": device_info,
            "capabilities": {
                "precision_timing": True,
                "hil_testing": True,
                "multi_channel": True,
                "high_speed_sampling": True
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting device info: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get device info: {str(e)}"
        )


@labjack_router.get("/channels", response_model=Dict[str, Any])
async def get_channel_configuration():
    """
    Get current channel configuration
    
    Returns configuration for all channels including voltage ranges,
    resolution settings, and threshold values.
    """
    try:
        service = get_labjack_hardware_service()
        status = service.get_status()
        
        return {
            "channels": status["channels"],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting channel config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get channel configuration: {str(e)}"
        )


@labjack_router.post("/channels/configure", response_model=Dict[str, Any])
async def configure_channels(request: ChannelConfigRequest):
    """
    Configure channel settings
    
    Updates channel configuration including voltage ranges, resolution,
    settling times, and detection thresholds.
    """
    try:
        service = get_labjack_hardware_service()
        
        if not service.is_connected():
            raise HTTPException(
                status_code=503,
                detail="No LabJack device connected"
            )
        
        # Update channel configurations
        for channel_name, config_dict in request.channels.items():
            if channel_name in service.channels:
                channel_config = service.channels[channel_name]
                
                # Update configuration fields
                for key, value in config_dict.items():
                    if hasattr(channel_config, key):
                        setattr(channel_config, key, value)
        
        # Apply hardware configuration
        service._configure_hardware_channels()
        
        logger.info(f"✅ Configured {len(request.channels)} channels")
        
        return {
            "success": True,
            "message": f"Successfully configured {len(request.channels)} channels",
            "configured_channels": list(request.channels.keys()),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Channel configuration error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Channel configuration failed: {str(e)}"
        )


@labjack_router.post("/monitoring/start", response_model=Dict[str, Any])
async def start_precision_monitoring(request: PrecisionMonitoringRequest):
    """
    Start precision signal monitoring - PRD Module 3.2
    
    Starts high-precision signal monitoring for HIL testing with
    millisecond timing accuracy and optional video synchronization.
    """
    try:
        service = get_labjack_hardware_service()
        
        if not service.is_connected():
            raise HTTPException(
                status_code=503,
                detail="No LabJack device connected"
            )
        
        # Start hardware monitoring
        success = service.start_precision_monitoring(
            session_id=request.session_id,
            channels=request.channels,
            threshold_voltage=request.threshold_voltage,
            sample_rate=request.sample_rate
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to start precision monitoring"
            )
        
        # Start video synchronization if requested
        sync_started = False
        if request.enable_sync and request.video_source:
            try:
                sync_service = get_video_hardware_sync_service()
                sync_config = SyncConfiguration(
                    session_id=request.session_id,
                    video_source=request.video_source,
                    hardware_channels=request.channels,
                    frame_rate=30.0
                )
                sync_started = sync_service.start_synchronization(sync_config)
            except Exception as sync_error:
                logger.warning(f"Video sync failed to start: {sync_error}")
        
        logger.info(f"✅ Precision monitoring started for session {request.session_id}")
        
        return {
            "success": True,
            "message": f"Precision monitoring started for session {request.session_id}",
            "session_id": request.session_id,
            "monitoring_config": {
                "channels": request.channels,
                "threshold_voltage": request.threshold_voltage,
                "sample_rate": request.sample_rate
            },
            "synchronization": {
                "enabled": request.enable_sync,
                "started": sync_started,
                "video_source": request.video_source
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Monitoring start error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start monitoring: {str(e)}"
        )


@labjack_router.post("/monitoring/stop", response_model=Dict[str, Any])
async def stop_precision_monitoring(session_id: str):
    """
    Stop precision signal monitoring
    
    Stops hardware monitoring and video synchronization for the specified session.
    """
    try:
        service = get_labjack_hardware_service()
        
        # Stop hardware monitoring
        success = service.stop_precision_monitoring()
        
        # Stop video synchronization
        try:
            sync_service = get_video_hardware_sync_service()
            sync_service.stop_synchronization(session_id)
        except Exception as sync_error:
            logger.warning(f"Video sync stop failed: {sync_error}")
        
        logger.info(f"⏹️ Precision monitoring stopped for session {session_id}")
        
        return {
            "success": success,
            "message": f"Precision monitoring stopped for session {session_id}",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Monitoring stop error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop monitoring: {str(e)}"
        )


@labjack_router.get("/events", response_model=Dict[str, Any])
async def get_hardware_events(max_events: int = Query(default=100, le=1000)):
    """
    Get hardware detection events
    
    Returns hardware detection events with precision timing data
    for latency analysis and test validation.
    """
    try:
        service = get_labjack_hardware_service()
        events = service.get_hardware_events(max_events=max_events)
        
        return {
            "event_count": len(events),
            "events": events,
            "max_events": max_events,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting hardware events: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get hardware events: {str(e)}"
        )


@labjack_router.get("/statistics", response_model=StatisticsResponse)
async def get_hardware_statistics():
    """
    Get hardware statistics and performance metrics
    
    Returns comprehensive statistics about hardware performance,
    connection reliability, and monitoring accuracy.
    """
    try:
        service = get_labjack_hardware_service()
        status = service.get_status()
        
        # Get video sync statistics if available
        sync_stats = {}
        try:
            sync_service = get_video_hardware_sync_service()
            sync_stats = sync_service.get_statistics()
        except Exception:
            pass
        
        return StatisticsResponse(
            connection_stats={
                "connection_attempts": service.statistics["connection_attempts"],
                "successful_connections": service.statistics["successful_connections"],
                "errors_count": service.statistics["errors_count"],
                "ljm_type": service.statistics["ljm_type"]
            },
            monitoring_stats={
                "monitoring_active": status["monitoring"]["active"],
                "total_signals_detected": service.statistics["total_signals_detected"],
                "monitoring_duration_seconds": service.statistics["monitoring_duration_seconds"],
                "events_in_queue": status["health"]["events_in_queue"]
            },
            performance_stats={
                "sync_statistics": sync_stats,
                "last_signal_time": service.statistics["last_signal_time"],
                "health_monitoring_active": status["health"]["health_monitoring_active"]
            },
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )


@labjack_router.get("/health", response_model=Dict[str, Any])
async def hardware_health_check():
    """
    Hardware health check endpoint
    
    Returns health status of LabJack hardware connection and services.
    Used for monitoring and alerting in production deployments.
    """
    try:
        service = get_labjack_hardware_service()
        status = service.get_status()
        
        is_healthy = (
            status["is_connected"] and 
            status["connection_details"]["status"] == "CONNECTED" and
            not status["health"]["events_in_queue"] > 45000  # Queue not full
        )
        
        health_status = "healthy" if is_healthy else "unhealthy"
        
        return {
            "service": "labjack_hardware",
            "status": health_status,
            "timestamp": datetime.now().isoformat(),
            "connection": {
                "status": status["connection_status"],
                "connected": status["is_connected"],
                "device_type": status["device_info"].get("device_type", "unknown"),
                "ljm_type": status["capabilities"]["ljm_available"]
            },
            "monitoring": {
                "active": status["monitoring"]["active"],
                "events_queued": status["health"]["events_in_queue"],
                "health_monitoring": status["health"]["health_monitoring_active"]
            },
            "capabilities": status["capabilities"],
            "last_error": service.statistics.get("last_error"),
            "checks": {
                "hardware_connected": status["is_connected"],
                "queue_not_full": status["health"]["events_in_queue"] < 45000,
                "no_recent_errors": service.statistics["last_error"] is None
            }
        }
        
    except Exception as e:
        logger.error(f"Hardware health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "service": "labjack_hardware",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@labjack_router.post("/initialize", response_model=Dict[str, Any])
async def initialize_hardware_service_endpoint(background_tasks: BackgroundTasks):
    """
    Initialize LabJack hardware service
    
    Performs hardware detection and initialization. This endpoint can be called
    at startup or when hardware connections need to be re-established.
    """
    try:
        def initialize_background():
            try:
                success = initialize_hardware_service()
                if success:
                    logger.info("✅ LabJack hardware service initialized successfully")
                else:
                    logger.warning("⚠️ LabJack hardware service initialization failed")
            except Exception as e:
                logger.error(f"❌ Hardware initialization error: {e}")
        
        background_tasks.add_task(initialize_background)
        
        return {
            "success": True,
            "message": "LabJack hardware initialization started in background",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize hardware service: {str(e)}"
        )


# Export the router for inclusion in main app
__all__ = ["labjack_router"]