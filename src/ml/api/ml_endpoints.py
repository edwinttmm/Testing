"""
FastAPI endpoints for ML inference and management
"""
import asyncio
import tempfile
import shutil
from typing import List, Dict, Optional, Any
from pathlib import Path
import logging
import time
import json

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
import cv2
import numpy as np

from ..inference.yolo_service import yolo_service, Detection
from ..models.model_manager import model_manager
from ..preprocessing.video_processor import video_processor
from ..monitoring.performance_monitor import performance_monitor
from ..tracking.kalman_tracker import vru_tracker
from ..config import ml_config

logger = logging.getLogger(__name__)

# Pydantic models for API
class DetectionResponse(BaseModel):
    bbox: List[float] = Field(..., description="Bounding box [x1, y1, x2, y2]")
    confidence: float = Field(..., description="Detection confidence")
    class_id: int = Field(..., description="Class ID")
    class_name: str = Field(..., description="Class name")
    track_id: Optional[int] = Field(None, description="Track ID if tracking enabled")
    timestamp: float = Field(..., description="Detection timestamp")

class FrameDetectionResponse(BaseModel):
    detections: List[DetectionResponse]
    processing_time_ms: float
    frame_size: tuple
    model_info: Dict[str, Any]

class VideoProcessingRequest(BaseModel):
    enable_tracking: bool = Field(default=True)
    save_screenshots: bool = Field(default=True)
    frame_skip: int = Field(default=1, ge=1, description="Process every Nth frame")
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)

class VideoProcessingResponse(BaseModel):
    task_id: str
    video_path: str
    status: str
    message: str

class ModelInfo(BaseModel):
    name: str
    version: str
    is_active: bool
    size_mb: float
    device: str
    performance_metrics: Optional[Dict[str, float]]

class SystemStatusResponse(BaseModel):
    ml_service_status: str
    active_model: Optional[str]
    device: str
    cuda_available: bool
    performance_stats: Dict[str, Any]
    system_info: Dict[str, Any]

# Create router
ml_router = APIRouter(prefix="/api/ml", tags=["Machine Learning"])

# Dependency to ensure ML service is initialized
async def get_initialized_yolo_service():
    """Dependency to ensure YOLO service is initialized"""
    if not yolo_service.is_initialized:
        success = await yolo_service.initialize()
        if not success:
            raise HTTPException(
                status_code=503, 
                detail="ML service not available - model initialization failed"
            )
    return yolo_service

@ml_router.post("/detect/frame", response_model=FrameDetectionResponse)
async def detect_frame(
    file: UploadFile = File(...),
    enable_tracking: bool = Query(default=False),
    return_annotated: bool = Query(default=False),
    yolo_svc = Depends(get_initialized_yolo_service)
):
    """
    Detect VRUs in a single image frame
    """
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read image data
        image_data = await file.read()
        
        # Convert to numpy array
        nparr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            raise HTTPException(status_code=400, detail="Invalid image format")
        
        start_time = time.time()
        
        # Run detection
        detections, annotated_frame = await yolo_svc.detect_vru(frame, return_annotated=return_annotated)
        
        # Apply tracking if enabled
        if enable_tracking and detections:
            detections = vru_tracker.update(detections)
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Convert detections to response format
        detection_responses = [
            DetectionResponse(
                bbox=det.bbox,
                confidence=det.confidence,
                class_id=det.class_id,
                class_name=det.class_name,
                track_id=det.track_id,
                timestamp=det.timestamp
            )
            for det in detections
        ]
        
        # Get model info
        model_info = {
            "name": yolo_svc.model.__class__.__name__ if yolo_svc.model else "unknown",
            "device": yolo_svc.device,
            "confidence_threshold": ml_config.confidence_threshold,
            "iou_threshold": ml_config.iou_threshold
        }
        
        response = FrameDetectionResponse(
            detections=detection_responses,
            processing_time_ms=processing_time_ms,
            frame_size=frame.shape[:2],
            model_info=model_info
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Frame detection failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")

@ml_router.post("/detect/video", response_model=VideoProcessingResponse)
async def detect_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    request: VideoProcessingRequest = VideoProcessingRequest(),
    yolo_svc = Depends(get_initialized_yolo_service)
):
    """
    Process video for VRU detection (async processing)
    """
    try:
        # Validate file type
        if not file.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail="File must be a video")
        
        # Generate task ID
        task_id = f"video_{int(time.time())}_{file.filename}"
        
        # Save uploaded file temporarily
        temp_dir = tempfile.mkdtemp(prefix="ml_video_")
        temp_video_path = Path(temp_dir) / file.filename
        
        with open(temp_video_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Add background task for processing
        background_tasks.add_task(
            process_video_background,
            task_id,
            str(temp_video_path),
            request,
            yolo_svc
        )
        
        return VideoProcessingResponse(
            task_id=task_id,
            video_path=str(temp_video_path),
            status="processing",
            message="Video processing started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video processing initialization failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

async def process_video_background(task_id: str, video_path: str, request: VideoProcessingRequest, yolo_svc):
    """Background task for video processing"""
    try:
        logger.info(f"Starting video processing task: {task_id}")
        
        # Update confidence threshold if specified
        if request.confidence_threshold is not None:
            original_threshold = ml_config.confidence_threshold
            ml_config.confidence_threshold = request.confidence_threshold
        
        # Process video
        result = await video_processor.process_video(
            video_path=video_path,
            yolo_service=yolo_svc,
            enable_tracking=request.enable_tracking,
            save_screenshots=request.save_screenshots,
            frame_skip=request.frame_skip
        )
        
        # Restore original threshold
        if request.confidence_threshold is not None:
            ml_config.confidence_threshold = original_threshold
        
        logger.info(f"Video processing task {task_id} completed: {result.total_detections} detections")
        
        # Store result (in production, use database or cache)
        # For now, just log completion
        
    except Exception as e:
        logger.error(f"Video processing task {task_id} failed: {str(e)}", exc_info=True)
    finally:
        # Cleanup temporary files
        try:
            if Path(video_path).exists():
                shutil.rmtree(Path(video_path).parent)
        except Exception as e:
            logger.warning(f"Cleanup failed for {video_path}: {str(e)}")

@ml_router.get("/models", response_model=List[ModelInfo])
async def list_models():
    """List all available models"""
    try:
        models = model_manager.version_manager.list_models()
        
        model_infos = [
            ModelInfo(
                name=model.name,
                version=model.version,
                is_active=model.is_active,
                size_mb=model.size_mb,
                device=model.device,
                performance_metrics=model.performance_metrics
            )
            for model in models
        ]
        
        return model_infos
        
    except Exception as e:
        logger.error(f"Model listing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list models")

@ml_router.post("/models/{name}/activate")
async def activate_model(name: str, version: Optional[str] = None):
    """Activate a specific model version"""
    try:
        success = await model_manager.hot_swap_model(name, version)
        
        if success:
            return {"message": f"Model {name} v{version} activated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Model not found or activation failed")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Model activation failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Model activation failed")

@ml_router.post("/models/{name}/benchmark")
async def benchmark_model(name: str, version: Optional[str] = None, iterations: int = Query(default=100, ge=10, le=1000)):
    """Benchmark model performance"""
    try:
        metrics = await model_manager.benchmark_model(name, version, iterations)
        
        if metrics:
            return {"model": f"{name} v{version}", "benchmark_results": metrics}
        else:
            raise HTTPException(status_code=404, detail="Model not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Model benchmarking failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Benchmarking failed")

@ml_router.get("/status", response_model=SystemStatusResponse)
async def get_ml_status():
    """Get ML service status and performance metrics"""
    try:
        # Get YOLO service status
        ml_status = "ready" if yolo_service.is_initialized else "not_initialized"
        
        # Get active model info
        active_model_info = model_manager.get_active_model_info()
        active_model = f"{active_model_info.name}_v{active_model_info.version}" if active_model_info else None
        
        # Get performance stats
        performance_stats = performance_monitor.get_current_stats()
        yolo_stats = yolo_service.get_performance_stats()
        
        # Get system info
        system_info = model_manager.get_system_info()
        
        response = SystemStatusResponse(
            ml_service_status=ml_status,
            active_model=active_model,
            device=ml_config.get_device(),
            cuda_available=system_info.get("cuda_available", False),
            performance_stats={
                "yolo_service": yolo_stats,
                "system_monitor": performance_stats
            },
            system_info=system_info
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Status retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get ML service status")

@ml_router.get("/performance/metrics")
async def get_performance_metrics(last_n: int = Query(default=100, ge=1, le=1000)):
    """Get detailed performance metrics"""
    try:
        metrics = performance_monitor.get_detailed_metrics(last_n)
        bottlenecks = performance_monitor.detect_bottlenecks()
        
        return {
            "metrics": metrics,
            "bottleneck_analysis": bottlenecks,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Performance metrics retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")

@ml_router.get("/tracking/status")
async def get_tracking_status():
    """Get VRU tracking status"""
    try:
        active_tracks = vru_tracker.get_active_tracks()
        
        return {
            "tracking_enabled": ml_config.tracking_enabled,
            "active_tracks_count": len(active_tracks),
            "active_tracks": active_tracks,
            "tracking_config": {
                "max_age": ml_config.tracking_max_age,
                "min_hits": ml_config.tracking_min_hits,
                "iou_threshold": ml_config.tracking_iou_threshold
            }
        }
        
    except Exception as e:
        logger.error(f"Tracking status retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get tracking status")

@ml_router.post("/tracking/reset")
async def reset_tracking():
    """Reset VRU tracking state"""
    try:
        vru_tracker.reset()
        return {"message": "Tracking state reset successfully"}
        
    except Exception as e:
        logger.error(f"Tracking reset failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset tracking")

@ml_router.get("/config")
async def get_ml_config():
    """Get current ML configuration"""
    try:
        config_dict = {
            "model_name": ml_config.model_name,
            "model_path": ml_config.model_path,
            "confidence_threshold": ml_config.confidence_threshold,
            "iou_threshold": ml_config.iou_threshold,
            "vru_classes": ml_config.vru_classes,
            "max_inference_time_ms": ml_config.max_inference_time_ms,
            "device": ml_config.get_device(),
            "tracking_enabled": ml_config.tracking_enabled,
            "input_size": ml_config.input_size,
            "save_screenshots": ml_config.save_screenshots
        }
        
        return config_dict
        
    except Exception as e:
        logger.error(f"Config retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get ML configuration")

@ml_router.post("/config/update")
async def update_ml_config(config_updates: Dict[str, Any]):
    """Update ML configuration"""
    try:
        updated_fields = []
        
        # Update allowed configuration fields
        allowed_updates = {
            "confidence_threshold": float,
            "iou_threshold": float,
            "max_inference_time_ms": int,
            "tracking_enabled": bool,
            "save_screenshots": bool
        }
        
        for field, value in config_updates.items():
            if field in allowed_updates:
                # Validate type
                expected_type = allowed_updates[field]
                if not isinstance(value, expected_type):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid type for {field}: expected {expected_type.__name__}"
                    )
                
                # Update configuration
                setattr(ml_config, field, value)
                updated_fields.append(field)
        
        if updated_fields:
            logger.info(f"Updated ML configuration: {updated_fields}")
            return {"message": f"Configuration updated: {updated_fields}"}
        else:
            return {"message": "No valid configuration updates provided"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Configuration update failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update configuration")

# Initialize ML services on startup
@ml_router.on_event("startup")
async def startup_ml_services():
    """Initialize ML services"""
    try:
        logger.info("Initializing ML services...")
        
        # Initialize model manager
        await model_manager.initialize_default_model()
        
        # Initialize YOLO service
        await yolo_service.initialize()
        
        # Start performance monitoring
        if ml_config.enable_performance_monitoring:
            performance_monitor.start_monitoring()
        
        logger.info("ML services initialized successfully")
        
    except Exception as e:
        logger.error(f"ML services initialization failed: {str(e)}")

@ml_router.on_event("shutdown")
async def shutdown_ml_services():
    """Cleanup ML services"""
    try:
        logger.info("Shutting down ML services...")
        
        await yolo_service.shutdown()
        await model_manager.shutdown()
        await video_processor.shutdown()
        await performance_monitor.stop_monitoring()
        
        logger.info("ML services shut down successfully")
        
    except Exception as e:
        logger.error(f"ML services shutdown failed: {str(e)}")

# Export router
MLRouter = ml_router