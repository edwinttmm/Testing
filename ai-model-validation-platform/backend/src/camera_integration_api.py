"""
Camera Integration REST API Endpoints
Provides HTTP endpoints for camera integration service management
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from starlette.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR

# Import our camera integration components
from camera_integration_service import camera_service, CameraConfig, ValidationResult
from camera_config_manager import camera_config_manager, CompleteCameraConfig
from camera_websocket_handlers import camera_websocket_router, camera_ws_handler

logger = logging.getLogger(__name__)

# API router
camera_api_router = APIRouter(prefix="/api/v1/camera", tags=["camera-integration"])

# Request/Response Models
class CameraConfigRequest(BaseModel):
    """Request model for camera configuration"""
    camera_id: str = Field(..., description="Unique camera identifier")
    camera_type: str = Field(..., description="Type of camera (webcam, ip_camera, etc.)")
    connection_url: str = Field(..., description="Connection URL or device path")
    format: str = Field(default="mjpeg", description="Video/signal format")
    resolution: tuple = Field(default=(1920, 1080), description="Video resolution")
    fps: int = Field(default=30, description="Frames per second")
    buffer_size: int = Field(default=100, description="Buffer size for frames")
    timeout_ms: int = Field(default=5000, description="Connection timeout in milliseconds")
    external_ip: str = Field(default="155.138.239.131", description="External IP address")
    enabled: bool = Field(default=True, description="Enable/disable camera")
    validation_enabled: bool = Field(default=True, description="Enable/disable validation")
    
    @validator('camera_type')
    def validate_camera_type(cls, v):
        allowed_types = ["webcam", "ip_camera", "usb", "gpio_trigger", "network_packet", "serial", "can_bus"]
        if v not in allowed_types:
            raise ValueError(f"Camera type must be one of: {', '.join(allowed_types)}")
        return v
    
    @validator('fps')
    def validate_fps(cls, v):
        if not (1 <= v <= 120):
            raise ValueError("FPS must be between 1 and 120")
        return v

class CameraConfigResponse(BaseModel):
    """Response model for camera configuration"""
    camera_id: str
    camera_type: str
    connection_url: str
    format: str
    resolution: tuple
    fps: int
    buffer_size: int
    timeout_ms: int
    external_ip: str
    enabled: bool
    validation_enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class CameraStatusResponse(BaseModel):
    """Response model for camera status"""
    camera_id: str
    is_running: bool
    config: CameraConfigResponse
    buffer_stats: Dict[str, Any]
    last_frame: Optional[Dict[str, Any]] = None

class ServiceStatsResponse(BaseModel):
    """Response model for service statistics"""
    total_frames_processed: int
    total_validations: int
    avg_processing_time: float
    active_cameras: int
    websocket_connections: int
    uptime_seconds: float
    buffer_stats: Dict[str, Dict[str, Any]]

class ValidationResultResponse(BaseModel):
    """Response model for validation results"""
    frame_id: str
    camera_id: str
    validation_passed: bool
    confidence_score: float
    detected_objects: List[Dict[str, Any]]
    processing_time_ms: float
    timestamp: float
    errors: Optional[List[str]] = None

class CameraListResponse(BaseModel):
    """Response model for camera list"""
    cameras: List[CameraStatusResponse]
    total_count: int
    enabled_count: int
    timestamp: datetime

# Utility functions
def convert_camera_config_to_legacy(config: CompleteCameraConfig) -> CameraConfig:
    """Convert new config format to legacy format for service compatibility"""
    return CameraConfig(
        camera_id=config.camera_id,
        camera_type=config.hardware.camera_type if config.hardware else "ip_camera",
        connection_url=config.connection.connection_url if config.connection else f"{config.network.external_ip}:8080",
        format=config.processing.format if config.processing else "mjpeg",
        resolution=config.processing.resolution if config.processing else (1920, 1080),
        fps=config.processing.target_fps if config.processing else 30,
        buffer_size=config.processing.buffer_size if config.processing else 100,
        timeout_ms=config.network.timeout_seconds * 1000 if config.network else 5000,
        external_ip=config.network.external_ip if config.network else "155.138.239.131",
        enabled=config.enabled,
        validation_enabled=config.processing.validation_enabled if config.processing else True
    )

def convert_legacy_to_camera_config_response(config: CameraConfig) -> CameraConfigResponse:
    """Convert legacy config to response format"""
    return CameraConfigResponse(
        camera_id=config.camera_id,
        camera_type=config.camera_type,
        connection_url=config.connection_url,
        format=config.format,
        resolution=config.resolution,
        fps=config.fps,
        buffer_size=config.buffer_size,
        timeout_ms=config.timeout_ms,
        external_ip=config.external_ip,
        enabled=config.enabled,
        validation_enabled=config.validation_enabled
    )

# API Endpoints

@camera_api_router.get("/health", response_model=Dict[str, Any])
async def camera_service_health():
    """Get camera service health status"""
    try:
        stats = camera_service.get_service_stats()
        
        health_status = {
            "status": "healthy" if camera_service.running else "stopped",
            "service_running": camera_service.running,
            "active_cameras": stats["active_cameras"],
            "websocket_connections": stats["websocket_connections"],
            "total_frames_processed": stats["total_frames_processed"],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )

@camera_api_router.post("/cameras", response_model=Dict[str, Any], status_code=HTTP_201_CREATED)
async def add_camera(camera_request: CameraConfigRequest):
    """Add new camera configuration"""
    try:
        # Create legacy config for service
        legacy_config = CameraConfig(
            camera_id=camera_request.camera_id,
            camera_type=camera_request.camera_type,
            connection_url=camera_request.connection_url,
            format=camera_request.format,
            resolution=camera_request.resolution,
            fps=camera_request.fps,
            buffer_size=camera_request.buffer_size,
            timeout_ms=camera_request.timeout_ms,
            external_ip=camera_request.external_ip,
            enabled=camera_request.enabled,
            validation_enabled=camera_request.validation_enabled
        )
        
        # Add to service
        success = await camera_service.add_camera(legacy_config)
        
        if not success:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Failed to add camera {camera_request.camera_id}"
            )
        
        # Also create complete config and save it
        complete_config = camera_config_manager.create_default_config(
            camera_request.camera_id, 
            camera_request.camera_type
        )
        
        # Update with request parameters
        if complete_config.network:
            complete_config.network.external_ip = camera_request.external_ip
        if complete_config.connection:
            complete_config.connection.connection_url = camera_request.connection_url
        if complete_config.processing:
            complete_config.processing.format = camera_request.format
            complete_config.processing.resolution = camera_request.resolution
            complete_config.processing.target_fps = camera_request.fps
            complete_config.processing.buffer_size = camera_request.buffer_size
            complete_config.processing.validation_enabled = camera_request.validation_enabled
        
        complete_config.enabled = camera_request.enabled
        
        config_success, errors = camera_config_manager.save_config(
            complete_config, 
            "Added via API"
        )
        
        if not config_success:
            logger.warning(f"Failed to save complete config for {camera_request.camera_id}: {errors}")
        
        return {
            "success": True,
            "camera_id": camera_request.camera_id,
            "message": "Camera added successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add camera: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add camera: {str(e)}"
        )

@camera_api_router.get("/cameras", response_model=CameraListResponse)
async def list_cameras(
    enabled_only: bool = Query(False, description="Return only enabled cameras"),
    include_stats: bool = Query(True, description="Include camera statistics")
):
    """List all cameras"""
    try:
        camera_statuses = []
        total_count = 0
        enabled_count = 0
        
        for camera_id, camera_config in camera_service.cameras.items():
            if enabled_only and not camera_config.enabled:
                continue
            
            total_count += 1
            if camera_config.enabled:
                enabled_count += 1
            
            if include_stats:
                status = await camera_service.get_camera_status(camera_id)
                
                camera_status = CameraStatusResponse(
                    camera_id=camera_id,
                    is_running=status["is_running"],
                    config=convert_legacy_to_camera_config_response(camera_config),
                    buffer_stats=status["buffer_stats"],
                    last_frame=status.get("last_frame")
                )
            else:
                camera_status = CameraStatusResponse(
                    camera_id=camera_id,
                    is_running=f"camera_processor_{camera_id}" in camera_service.processing_tasks,
                    config=convert_legacy_to_camera_config_response(camera_config),
                    buffer_stats={}
                )
            
            camera_statuses.append(camera_status)
        
        return CameraListResponse(
            cameras=camera_statuses,
            total_count=total_count,
            enabled_count=enabled_count,
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Failed to list cameras: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list cameras: {str(e)}"
        )

@camera_api_router.get("/cameras/{camera_id}", response_model=CameraStatusResponse)
async def get_camera_status(camera_id: str = Path(..., description="Camera ID")):
    """Get specific camera status"""
    try:
        if camera_id not in camera_service.cameras:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Camera {camera_id} not found"
            )
        
        status = await camera_service.get_camera_status(camera_id)
        camera_config = camera_service.cameras[camera_id]
        
        return CameraStatusResponse(
            camera_id=camera_id,
            is_running=status["is_running"],
            config=convert_legacy_to_camera_config_response(camera_config),
            buffer_stats=status["buffer_stats"],
            last_frame=status.get("last_frame")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get camera status: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get camera status: {str(e)}"
        )

@camera_api_router.put("/cameras/{camera_id}", response_model=Dict[str, Any])
async def update_camera(camera_id: str = Path(..., description="Camera ID"), camera_request: CameraConfigRequest = None):
    """Update camera configuration"""
    try:
        if camera_id not in camera_service.cameras:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Camera {camera_id} not found"
            )
        
        # Remove old camera
        await camera_service.remove_camera(camera_id)
        
        # Add updated camera
        legacy_config = CameraConfig(
            camera_id=camera_request.camera_id,
            camera_type=camera_request.camera_type,
            connection_url=camera_request.connection_url,
            format=camera_request.format,
            resolution=camera_request.resolution,
            fps=camera_request.fps,
            buffer_size=camera_request.buffer_size,
            timeout_ms=camera_request.timeout_ms,
            external_ip=camera_request.external_ip,
            enabled=camera_request.enabled,
            validation_enabled=camera_request.validation_enabled
        )
        
        success = await camera_service.add_camera(legacy_config)
        
        if not success:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Failed to update camera {camera_id}"
            )
        
        # Update complete config
        complete_config = camera_config_manager.load_config(camera_id)
        if complete_config:
            if complete_config.network:
                complete_config.network.external_ip = camera_request.external_ip
            if complete_config.connection:
                complete_config.connection.connection_url = camera_request.connection_url
            if complete_config.processing:
                complete_config.processing.format = camera_request.format
                complete_config.processing.resolution = camera_request.resolution
                complete_config.processing.target_fps = camera_request.fps
                complete_config.processing.buffer_size = camera_request.buffer_size
                complete_config.processing.validation_enabled = camera_request.validation_enabled
            
            complete_config.enabled = camera_request.enabled
            
            camera_config_manager.save_config(complete_config, "Updated via API")
        
        return {
            "success": True,
            "camera_id": camera_id,
            "message": "Camera updated successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update camera: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update camera: {str(e)}"
        )

@camera_api_router.delete("/cameras/{camera_id}", response_model=Dict[str, Any])
async def remove_camera(camera_id: str = Path(..., description="Camera ID")):
    """Remove camera configuration"""
    try:
        if camera_id not in camera_service.cameras:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Camera {camera_id} not found"
            )
        
        success = await camera_service.remove_camera(camera_id)
        
        if not success:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Failed to remove camera {camera_id}"
            )
        
        # Also remove from config manager
        camera_config_manager.delete_config(camera_id)
        
        return {
            "success": True,
            "camera_id": camera_id,
            "message": "Camera removed successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove camera: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove camera: {str(e)}"
        )

@camera_api_router.post("/cameras/{camera_id}/start", response_model=Dict[str, Any])
async def start_camera(camera_id: str = Path(..., description="Camera ID")):
    """Start camera processing"""
    try:
        if camera_id not in camera_service.cameras:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Camera {camera_id} not found"
            )
        
        camera_config = camera_service.cameras[camera_id]
        camera_config.enabled = True
        
        # Start processing task if not already running
        task_name = f"camera_processor_{camera_id}"
        if task_name not in camera_service.processing_tasks:
            camera_service.processing_tasks[task_name] = asyncio.create_task(
                camera_service._camera_processing_loop(camera_config)
            )
        
        return {
            "success": True,
            "camera_id": camera_id,
            "message": "Camera started successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start camera: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start camera: {str(e)}"
        )

@camera_api_router.post("/cameras/{camera_id}/stop", response_model=Dict[str, Any])
async def stop_camera(camera_id: str = Path(..., description="Camera ID")):
    """Stop camera processing"""
    try:
        if camera_id not in camera_service.cameras:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Camera {camera_id} not found"
            )
        
        camera_config = camera_service.cameras[camera_id]
        camera_config.enabled = False
        
        # Cancel processing task
        task_name = f"camera_processor_{camera_id}"
        if task_name in camera_service.processing_tasks:
            camera_service.processing_tasks[task_name].cancel()
            del camera_service.processing_tasks[task_name]
        
        return {
            "success": True,
            "camera_id": camera_id,
            "message": "Camera stopped successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop camera: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop camera: {str(e)}"
        )

@camera_api_router.get("/stats", response_model=ServiceStatsResponse)
async def get_service_stats():
    """Get service statistics"""
    try:
        stats = camera_service.get_service_stats()
        
        return ServiceStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Failed to get service stats: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service stats: {str(e)}"
        )

@camera_api_router.get("/cameras/{camera_id}/frames/latest", response_model=Dict[str, Any])
async def get_latest_frame(camera_id: str = Path(..., description="Camera ID")):
    """Get latest frame from camera buffer"""
    try:
        if camera_id not in camera_service.cameras:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Camera {camera_id} not found"
            )
        
        if camera_id not in camera_service.buffers:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"No buffer found for camera {camera_id}"
            )
        
        buffer = camera_service.buffers[camera_id]
        latest_frame = buffer.peek_latest()
        
        if not latest_frame:
            return {
                "camera_id": camera_id,
                "frame": None,
                "message": "No frames available",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Convert frame to serializable format
        frame_dict = {
            "camera_id": latest_frame.camera_id,
            "timestamp": latest_frame.timestamp,
            "frame_id": latest_frame.frame_id,
            "metadata": latest_frame.metadata,
            "signal_type": latest_frame.signal_type,
            "confidence": latest_frame.confidence
        }
        
        # Don't include raw data in response (too large)
        if hasattr(latest_frame.data, '__dict__'):
            frame_dict["data"] = str(latest_frame.data)
        else:
            frame_dict["data"] = f"<{type(latest_frame.data).__name__} data>"
        
        return {
            "camera_id": camera_id,
            "frame": frame_dict,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get latest frame: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get latest frame: {str(e)}"
        )

@camera_api_router.get("/config/summary", response_model=Dict[str, Any])
async def get_config_summary():
    """Get configuration summary"""
    try:
        summary = camera_config_manager.get_config_summary()
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get config summary: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get config summary: {str(e)}"
        )

@camera_api_router.post("/config/external-ip", response_model=Dict[str, Any])
async def update_external_ip(new_ip: str = Query(..., description="New external IP address")):
    """Update external IP for all cameras"""
    try:
        # Validate IP address
        import ipaddress
        ipaddress.ip_address(new_ip)
        
        updated_count = camera_config_manager.update_external_ip(new_ip)
        
        return {
            "success": True,
            "updated_cameras": updated_count,
            "new_external_ip": new_ip,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Invalid IP address: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to update external IP: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update external IP: {str(e)}"
        )

# Service lifecycle endpoints
@camera_api_router.post("/service/start", response_model=Dict[str, Any])
async def start_camera_service():
    """Start camera integration service"""
    try:
        if not camera_service.running:
            await camera_service.initialize()
        
        return {
            "success": True,
            "message": "Camera service started",
            "running": camera_service.running,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to start camera service: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start camera service: {str(e)}"
        )

@camera_api_router.post("/service/stop", response_model=Dict[str, Any])
async def stop_camera_service():
    """Stop camera integration service"""
    try:
        await camera_service.shutdown()
        
        return {
            "success": True,
            "message": "Camera service stopped",
            "running": camera_service.running,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to stop camera service: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop camera service: {str(e)}"
        )

# Include WebSocket router
camera_api_router.include_router(camera_websocket_router)

# Export router
__all__ = ["camera_api_router"]