#!/usr/bin/env python3
"""
Optimized Detection API Endpoints
Replaces timeout-prone detection endpoints with optimized versions
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import logging
import time
import asyncio
from pathlib import Path

from database import get_db
from schemas import DetectionPipelineConfigSchema, DetectionPipelineResponse
from services.optimized_detection_service import optimized_detection_service
from services.timeout_config import timeout_config, timeout_context, safe_video_processing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/detection", tags=["detection-optimized"])

# Background task tracker
active_tasks: Dict[str, Dict[str, Any]] = {}

@router.post("/pipeline/run-optimized", response_model=DetectionPipelineResponse)
async def run_optimized_detection_pipeline(
    request: DetectionPipelineConfigSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Run optimized ML detection pipeline with timeout handling and graceful degradation
    
    This endpoint addresses the critical timeout issues:
    1. Proper timeout handling at all levels
    2. Fixed TypeError in pipeline processing
    3. Graceful fallback to mock data if processing fails
    4. Performance optimizations (frame skipping, faster model)
    5. Real-time progress tracking
    """
    task_id = f"detection_{request.video_id}_{int(time.time())}"
    
    try:
        # Get video record
        from crud import get_video
        video = get_video(db=db, video_id=request.video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        if not video.file_path or not Path(video.file_path).exists():
            raise HTTPException(status_code=404, detail="Video file not found on disk")
        
        # Track task start
        active_tasks[task_id] = {
            "status": "starting",
            "video_id": request.video_id,
            "started_at": time.time(),
            "progress": 0
        }
        
        logger.info(f"🚀 Starting optimized detection for video {request.video_id}")
        
        # Configure optimized pipeline
        pipeline_config = {
            "confidence_threshold": request.confidence_threshold,
            "nms_threshold": request.nms_threshold,
            "target_classes": request.target_classes,
            "enable_mock_fallback": True,  # Enable graceful degradation
            "frame_skip": timeout_config.frame_skip_ratio
        }
        
        # Update task status
        active_tasks[task_id]["status"] = "processing"
        active_tasks[task_id]["progress"] = 10
        
        # Process video with comprehensive timeout handling
        start_time = time.time()
        
        async with timeout_context(
            timeout_config.max_video_processing_timeout, 
            f"detection pipeline for {request.video_id}"
        ):
            detections = await optimized_detection_service.process_video(
                video.file_path, 
                request.video_id, 
                pipeline_config
            )
        
        processing_time = time.time() - start_time
        
        # Update task completion
        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["progress"] = 100
        active_tasks[task_id]["processing_time"] = processing_time
        active_tasks[task_id]["detections_count"] = len(detections)
        
        logger.info(f"✅ Detection completed for {request.video_id}: {len(detections)} detections in {processing_time:.2f}s")
        
        # Check if we got mock data (fallback scenario)
        is_mock = any(detection.get("_mock", False) for detection in detections)
        
        response = DetectionPipelineResponse(
            video_id=request.video_id,
            detections=detections,
            processing_time=processing_time,
            model_used=request.model_name or "yolov8n-optimized",
            total_detections=len(detections),
            confidence_distribution={
                "high": len([d for d in detections if d.get("confidence", 0) >= 0.8]),
                "medium": len([d for d in detections if 0.5 <= d.get("confidence", 0) < 0.8]),
                "low": len([d for d in detections if d.get("confidence", 0) < 0.5])
            }
        )
        
        # Add metadata about processing
        response_dict = response.dict()
        response_dict["processing_metadata"] = {
            "is_mock_data": is_mock,
            "timeout_used": timeout_config.max_video_processing_timeout,
            "frame_skip_ratio": timeout_config.frame_skip_ratio,
            "task_id": task_id
        }
        
        if is_mock:
            logger.warning(f"⚠️ Returned mock data for {request.video_id} due to processing issues")
            response_dict["warning"] = "Mock data returned due to processing timeout or errors"
        
        return JSONResponse(content=response_dict)
        
    except asyncio.TimeoutError:
        # Handle timeout gracefully
        processing_time = time.time() - start_time if 'start_time' in locals() else 0
        logger.error(f"⏰ Detection pipeline timeout for {request.video_id} after {processing_time:.2f}s")
        
        # Update task status
        active_tasks[task_id]["status"] = "timeout"
        active_tasks[task_id]["progress"] = 50  # Partial progress
        
        # Return mock detections for graceful degradation
        if timeout_config.enable_mock_fallback:
            mock_detections = _create_timeout_fallback_detections(request.video_id)
            
            response_dict = DetectionPipelineResponse(
                video_id=request.video_id,
                detections=mock_detections,
                processing_time=processing_time,
                model_used="mock-fallback",
                total_detections=len(mock_detections),
                confidence_distribution={"medium": len(mock_detections)}
            ).dict()
            
            response_dict["processing_metadata"] = {
                "is_mock_data": True,
                "timeout_reason": "Detection processing exceeded maximum allowed time",
                "timeout_duration": timeout_config.max_video_processing_timeout,
                "task_id": task_id
            }
            response_dict["warning"] = f"Processing timed out after {timeout_config.max_video_processing_timeout}s. Returning mock data."
            
            return JSONResponse(content=response_dict, status_code=206)  # Partial Content
        else:
            raise HTTPException(
                status_code=408, 
                detail=f"Detection processing timeout after {timeout_config.max_video_processing_timeout}s"
            )
    
    except Exception as e:
        # Handle other errors gracefully
        processing_time = time.time() - start_time if 'start_time' in locals() else 0
        logger.error(f"❌ Detection pipeline error for {request.video_id}: {e}")
        
        # Update task status
        active_tasks[task_id]["status"] = "error"
        active_tasks[task_id]["error"] = str(e)
        
        # Return mock data if enabled
        if timeout_config.enable_mock_fallback:
            mock_detections = _create_error_fallback_detections(request.video_id, str(e))
            
            response_dict = DetectionPipelineResponse(
                video_id=request.video_id,
                detections=mock_detections,
                processing_time=processing_time,
                model_used="error-fallback",
                total_detections=len(mock_detections),
                confidence_distribution={"low": len(mock_detections)}
            ).dict()
            
            response_dict["processing_metadata"] = {
                "is_mock_data": True,
                "error_reason": str(e),
                "task_id": task_id
            }
            response_dict["warning"] = f"Processing failed: {str(e)}. Returning mock data."
            
            return JSONResponse(content=response_dict, status_code=206)  # Partial Content
        else:
            raise HTTPException(status_code=500, detail=f"Detection pipeline failed: {str(e)}")

@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Get status of background detection task"""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_info = active_tasks[task_id].copy()
    
    # Calculate elapsed time
    if "started_at" in task_info:
        task_info["elapsed_time"] = time.time() - task_info["started_at"]
    
    return task_info

@router.get("/tasks/active")
async def get_active_tasks():
    """Get all active detection tasks"""
    current_time = time.time()
    
    # Clean up old completed tasks (older than 1 hour)
    to_remove = []
    for task_id, task_info in active_tasks.items():
        if task_info.get("status") in ["completed", "error", "timeout"]:
            if current_time - task_info.get("started_at", 0) > 3600:  # 1 hour
                to_remove.append(task_id)
    
    for task_id in to_remove:
        del active_tasks[task_id]
    
    # Return active tasks with elapsed time
    result = {}
    for task_id, task_info in active_tasks.items():
        task_copy = task_info.copy()
        if "started_at" in task_copy:
            task_copy["elapsed_time"] = current_time - task_copy["started_at"]
        result[task_id] = task_copy
    
    return {
        "active_tasks": result,
        "total_active": len(result),
        "timeout_config": {
            "max_processing_timeout": timeout_config.max_video_processing_timeout,
            "frame_inference_timeout": timeout_config.frame_inference_timeout,
            "frame_skip_ratio": timeout_config.frame_skip_ratio
        }
    }

@router.get("/health")
async def detection_health_check():
    """Health check for optimized detection service"""
    try:
        # Try to initialize pipeline
        pipeline = await optimized_detection_service.get_pipeline()
        
        health_info = {
            "status": "healthy",
            "pipeline_initialized": pipeline.initialized,
            "timeout_config": timeout_config.to_dict(),
            "active_tasks": len(active_tasks),
            "timestamp": time.time()
        }
        
        if pipeline.initialized:
            stats = pipeline.get_performance_stats()
            health_info["performance_stats"] = stats
        
        return health_info
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }

def _create_timeout_fallback_detections(video_id: str) -> list:
    """Create mock detections for timeout scenarios"""
    import uuid
    
    mock_detections = []
    for i in range(timeout_config.mock_detection_count):
        detection = {
            "id": str(uuid.uuid4()),
            "frame_number": 30 + (i * 30),  # Frame 30, 60, 90
            "timestamp": 1.25 + (i * 1.25),  # 1.25s, 2.5s, 3.75s
            "class_label": "pedestrian",
            "confidence": 0.65 + (i * 0.05),
            "bounding_box": {
                "x": 150 + (i * 40),
                "y": 100 + (i * 30),
                "width": 90,
                "height": 180
            },
            "vru_type": "pedestrian",
            "videoId": str(video_id),
            "video_id": str(video_id),
            "_mock": True,
            "_mock_reason": "timeout_fallback"
        }
        mock_detections.append(detection)
    
    return mock_detections

def _create_error_fallback_detections(video_id: str, error_message: str) -> list:
    """Create mock detections for error scenarios"""
    import uuid
    
    mock_detections = []
    # Create fewer detections for error scenarios
    for i in range(max(1, timeout_config.mock_detection_count - 1)):
        detection = {
            "id": str(uuid.uuid4()),
            "frame_number": 45 + (i * 45),
            "timestamp": 1.8 + (i * 1.8),
            "class_label": "pedestrian",
            "confidence": 0.55 + (i * 0.03),
            "bounding_box": {
                "x": 120 + (i * 35),
                "y": 80 + (i * 25),
                "width": 85,
                "height": 170
            },
            "vru_type": "pedestrian",
            "videoId": str(video_id),
            "video_id": str(video_id),
            "_mock": True,
            "_mock_reason": "error_fallback",
            "_error_message": error_message
        }
        mock_detections.append(detection)
    
    return mock_detections