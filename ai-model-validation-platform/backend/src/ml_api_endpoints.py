#!/usr/bin/env python3
"""
ML API Endpoints - Complete RESTful API for VRU Detection Platform
Provides comprehensive endpoints for ML inference operations

SPARC API Implementation:
- Specification: RESTful API design for ML operations
- Pseudocode: Async endpoint patterns with error handling
- Architecture: FastAPI-based microservice architecture
- Refinement: Production-ready with monitoring and validation
- Completion: Ready for 155.138.239.131 deployment

Author: SPARC ML API Development Team
Version: 2.0.0
Target: Production VRU Detection API
"""

import asyncio
import logging
import time
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import traceback

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Depends, Query, Path as FastAPIPath
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
import uvicorn

# Import enhanced ML engine
import sys
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

try:
    from src.enhanced_ml_inference_engine import (
        get_production_ml_engine,
        process_video_for_ground_truth,
        get_video_annotations,
        update_annotation,
        delete_annotation,
        get_ml_engine_health,
        EnhancedVRUDetection,
        EnhancedBoundingBox
    )
    ML_ENGINE_AVAILABLE = True
except ImportError:
    ML_ENGINE_AVAILABLE = False
    logging.warning("Enhanced ML engine not available - using mock responses")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pydantic models for API validation
class BoundingBoxRequest(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0, description="Normalized x coordinate (0-1)")
    y: float = Field(..., ge=0.0, le=1.0, description="Normalized y coordinate (0-1)")
    width: float = Field(..., ge=0.0, le=1.0, description="Normalized width (0-1)")
    height: float = Field(..., ge=0.0, le=1.0, description="Normalized height (0-1)")

class DetectionRequest(BaseModel):
    frame_number: int = Field(..., ge=0, description="Frame number")
    timestamp: float = Field(..., ge=0.0, description="Timestamp in seconds")
    vru_type: str = Field(..., description="VRU type (pedestrian, cyclist, motorcyclist)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    bounding_box: BoundingBoxRequest
    
    @validator('vru_type')
    def validate_vru_type(cls, v):
        valid_types = ['pedestrian', 'cyclist', 'motorcyclist', 'vehicle', 'other']
        if v not in valid_types:
            raise ValueError(f'vru_type must be one of {valid_types}')
        return v

class DetectionUpdateRequest(BaseModel):
    vru_type: Optional[str] = Field(None, description="Updated VRU type")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Updated confidence")
    bounding_box: Optional[BoundingBoxRequest] = Field(None, description="Updated bounding box")
    
    @validator('vru_type')
    def validate_vru_type(cls, v):
        if v is not None:
            valid_types = ['pedestrian', 'cyclist', 'motorcyclist', 'vehicle', 'other']
            if v not in valid_types:
                raise ValueError(f'vru_type must be one of {valid_types}')
        return v

class VideoProcessingRequest(BaseModel):
    video_id: str = Field(..., description="Unique video identifier")
    video_path: str = Field(..., description="Path to video file")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Processing options")

class VideoProcessingResponse(BaseModel):
    video_id: str
    status: str
    message: str
    processing_stats: Optional[Dict[str, Any]] = None
    detection_summary: Optional[Dict[str, Any]] = None

class DetectionResponse(BaseModel):
    detection_id: str
    frame_number: int
    timestamp: float
    vru_type: str
    confidence: float
    bounding_box: BoundingBoxRequest
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    components: Dict[str, str]
    timestamp: str
    uptime: Optional[float] = None

class StatsResponse(BaseModel):
    yolo_stats: Dict[str, Any]
    video_processor_stats: Dict[str, Any]
    cache_stats: Dict[str, Any]
    database_available: bool

# FastAPI app initialization
app = FastAPI(
    title="VRU ML Inference API",
    description="Production-ready API for VRU detection and ML inference operations",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for tracking
_processing_tasks = {}
_app_start_time = time.time()

# Dependency for ML engine
async def get_ml_engine():
    """Dependency to get ML engine instance"""
    if not ML_ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="ML inference engine not available"
        )
    try:
        return await get_production_ml_engine()
    except Exception as e:
        logger.error(f"Failed to get ML engine: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"ML engine initialization failed: {str(e)}"
        )

# API Endpoints

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "VRU ML Inference API",
        "version": "2.0.0",
        "description": "Production-ready API for VRU detection and ML inference",
        "documentation": "/api/docs",
        "health_check": "/api/health"
    }

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check endpoint"""
    try:
        if ML_ENGINE_AVAILABLE:
            health = await get_ml_engine_health()
        else:
            health = {
                "status": "degraded",
                "components": {"ml_engine": "not_available"},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        # Add uptime
        health["uptime"] = time.time() - _app_start_time
        
        return health
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "components": {"api": f"error: {str(e)}"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime": time.time() - _app_start_time
        }

@app.get("/api/stats", response_model=StatsResponse)
async def get_engine_stats(engine=Depends(get_ml_engine)):
    """Get comprehensive ML engine statistics"""
    try:
        stats = engine.get_engine_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.post("/api/videos/{video_id}/process", response_model=VideoProcessingResponse)
async def process_video(
    video_id: str = FastAPIPath(..., description="Video ID to process"),
    request: VideoProcessingRequest = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    engine=Depends(get_ml_engine)
):
    """Process video for ground truth generation"""
    try:
        if video_id in _processing_tasks:
            if _processing_tasks[video_id]["status"] == "processing":
                return VideoProcessingResponse(
                    video_id=video_id,
                    status="already_processing",
                    message="Video is already being processed"
                )
        
        # Get video path from request or construct default
        if request:
            video_path = request.video_path
            options = request.options or {}
        else:
            # Default path construction
            video_path = f"/home/user/Testing/ai-model-validation-platform/backend/uploads/{video_id}.mp4"
            options = {}
        
        # Check if video file exists
        if not Path(video_path).exists():
            raise HTTPException(
                status_code=404,
                detail=f"Video file not found: {video_path}"
            )
        
        # Start processing task
        _processing_tasks[video_id] = {
            "status": "processing",
            "start_time": time.time(),
            "progress": 0.0
        }
        
        async def progress_callback(vid_id: str, progress: float, frames_processed: int):
            """Update progress tracking"""
            if vid_id in _processing_tasks:
                _processing_tasks[vid_id].update({
                    "progress": progress,
                    "frames_processed": frames_processed,
                    "last_update": time.time()
                })
        
        # Add background task
        background_tasks.add_task(
            process_video_background,
            video_id,
            video_path,
            options,
            progress_callback
        )
        
        return VideoProcessingResponse(
            video_id=video_id,
            status="processing",
            message="Video processing started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video processing request failed: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Processing request failed: {str(e)}"
        )

async def process_video_background(video_id: str, video_path: str, 
                                 options: Dict[str, Any],
                                 progress_callback: callable):
    """Background task for video processing"""
    try:
        logger.info(f"Starting background processing for video {video_id}")
        
        result = await process_video_for_ground_truth(
            video_id, video_path, progress_callback
        )
        
        # Update task status
        _processing_tasks[video_id] = {
            "status": "completed",
            "result": result,
            "completion_time": time.time()
        }
        
        logger.info(f"Completed processing for video {video_id}")
        
    except Exception as e:
        logger.error(f"Background processing failed for video {video_id}: {e}")
        _processing_tasks[video_id] = {
            "status": "failed",
            "error": str(e),
            "failure_time": time.time()
        }

@app.get("/api/videos/{video_id}/processing-status")
async def get_processing_status(video_id: str = FastAPIPath(...)):
    """Get video processing status"""
    if video_id not in _processing_tasks:
        raise HTTPException(
            status_code=404,
            detail="Processing task not found"
        )
    
    task_info = _processing_tasks[video_id]
    
    response = {
        "video_id": video_id,
        "status": task_info["status"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if "progress" in task_info:
        response["progress"] = task_info["progress"]
    
    if "frames_processed" in task_info:
        response["frames_processed"] = task_info["frames_processed"]
    
    if "result" in task_info:
        response["result"] = task_info["result"]
    
    if "error" in task_info:
        response["error"] = task_info["error"]
    
    return response

@app.get("/api/videos/{video_id}/detections", response_model=List[DetectionResponse])
async def get_video_detections(
    video_id: str = FastAPIPath(...),
    frame_start: Optional[int] = Query(None, description="Start frame number"),
    frame_end: Optional[int] = Query(None, description="End frame number"),
    vru_type: Optional[str] = Query(None, description="Filter by VRU type"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence"),
    engine=Depends(get_ml_engine)
):
    """Get detections for a video with optional filtering"""
    try:
        detections = await get_video_annotations(video_id)
        
        # Apply filters
        filtered_detections = []
        for det in detections:
            # Frame range filter
            if frame_start is not None and det["frame_number"] < frame_start:
                continue
            if frame_end is not None and det["frame_number"] > frame_end:
                continue
            
            # VRU type filter
            if vru_type is not None and det["vru_type"] != vru_type:
                continue
            
            # Confidence filter
            if min_confidence is not None and det["confidence"] < min_confidence:
                continue
            
            # Convert to response format
            detection_response = DetectionResponse(
                detection_id=det["detection_id"],
                frame_number=det["frame_number"],
                timestamp=det["timestamp"],
                vru_type=det["vru_type"],
                confidence=det["confidence"],
                bounding_box=BoundingBoxRequest(**det["bounding_box"]),
                metadata=det.get("metadata"),
                created_at=det.get("created_at")
            )
            filtered_detections.append(detection_response)
        
        return filtered_detections
        
    except Exception as e:
        logger.error(f"Failed to get video detections: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve detections: {str(e)}"
        )

@app.post("/api/videos/{video_id}/detections", response_model=DetectionResponse)
async def create_detection(
    video_id: str = FastAPIPath(...),
    detection: DetectionRequest = ...,
    engine=Depends(get_ml_engine)
):
    """Create a new detection annotation"""
    try:
        # Convert to enhanced detection format
        enhanced_detection = EnhancedVRUDetection(
            detection_id=str(uuid.uuid4()),
            frame_number=detection.frame_number,
            timestamp=detection.timestamp,
            vru_type=detection.vru_type,
            confidence=detection.confidence,
            bounding_box=EnhancedBoundingBox(
                x=detection.bounding_box.x,
                y=detection.bounding_box.y,
                width=detection.bounding_box.width,
                height=detection.bounding_box.height,
                confidence=detection.confidence
            )
        )
        
        # Save to database
        await engine._save_detections_to_database(video_id, [enhanced_detection], {})
        
        return DetectionResponse(
            detection_id=enhanced_detection.detection_id,
            frame_number=enhanced_detection.frame_number,
            timestamp=enhanced_detection.timestamp,
            vru_type=enhanced_detection.vru_type,
            confidence=enhanced_detection.confidence,
            bounding_box=BoundingBoxRequest(
                x=enhanced_detection.bounding_box.x,
                y=enhanced_detection.bounding_box.y,
                width=enhanced_detection.bounding_box.width,
                height=enhanced_detection.bounding_box.height
            ),
            metadata=enhanced_detection.metadata,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to create detection: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create detection: {str(e)}"
        )

@app.put("/api/detections/{detection_id}", response_model=Dict[str, str])
async def update_detection_endpoint(
    detection_id: str = FastAPIPath(...),
    updates: DetectionUpdateRequest = ...,
    engine=Depends(get_ml_engine)
):
    """Update an existing detection"""
    try:
        # Convert to update dictionary
        update_dict = {}
        if updates.vru_type is not None:
            update_dict["vru_type"] = updates.vru_type
        if updates.confidence is not None:
            update_dict["confidence"] = updates.confidence
        if updates.bounding_box is not None:
            update_dict["bounding_box"] = {
                "x": updates.bounding_box.x,
                "y": updates.bounding_box.y,
                "width": updates.bounding_box.width,
                "height": updates.bounding_box.height
            }
        
        success = await update_annotation(detection_id, update_dict)
        
        if success:
            return {"message": "Detection updated successfully"}
        else:
            raise HTTPException(
                status_code=404,
                detail="Detection not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update detection: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update detection: {str(e)}"
        )

@app.delete("/api/detections/{detection_id}", response_model=Dict[str, str])
async def delete_detection_endpoint(
    detection_id: str = FastAPIPath(...),
    engine=Depends(get_ml_engine)
):
    """Delete a detection"""
    try:
        success = await delete_annotation(detection_id)
        
        if success:
            return {"message": "Detection deleted successfully"}
        else:
            raise HTTPException(
                status_code=404,
                detail="Detection not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete detection: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete detection: {str(e)}"
        )

@app.get("/api/videos/{video_id}/summary")
async def get_video_summary(
    video_id: str = FastAPIPath(...),
    engine=Depends(get_ml_engine)
):
    """Get comprehensive video analysis summary"""
    try:
        detections = await get_video_annotations(video_id)
        
        if not detections:
            return {
                "video_id": video_id,
                "total_detections": 0,
                "by_type": {},
                "by_frame": {},
                "confidence_stats": {},
                "temporal_analysis": {}
            }
        
        # Analyze detections
        by_type = {}
        by_frame = {}
        confidences = []
        timestamps = []
        
        for det in detections:
            vru_type = det["vru_type"]
            frame_num = det["frame_number"]
            confidence = det["confidence"]
            timestamp = det["timestamp"]
            
            # By type analysis
            if vru_type not in by_type:
                by_type[vru_type] = {"count": 0, "confidences": []}
            by_type[vru_type]["count"] += 1
            by_type[vru_type]["confidences"].append(confidence)
            
            # By frame analysis
            if frame_num not in by_frame:
                by_frame[frame_num] = 0
            by_frame[frame_num] += 1
            
            confidences.append(confidence)
            timestamps.append(timestamp)
        
        # Calculate statistics
        for vru_type in by_type:
            confs = by_type[vru_type]["confidences"]
            by_type[vru_type]["avg_confidence"] = sum(confs) / len(confs)
            by_type[vru_type]["min_confidence"] = min(confs)
            by_type[vru_type]["max_confidence"] = max(confs)
            del by_type[vru_type]["confidences"]
        
        confidence_stats = {
            "min": min(confidences),
            "max": max(confidences),
            "avg": sum(confidences) / len(confidences),
            "median": sorted(confidences)[len(confidences) // 2]
        }
        
        temporal_analysis = {
            "duration": max(timestamps) - min(timestamps) if timestamps else 0,
            "detection_density": len(detections) / (max(timestamps) - min(timestamps)) if timestamps and len(set(timestamps)) > 1 else 0,
            "frames_with_detections": len(by_frame),
            "avg_detections_per_frame": sum(by_frame.values()) / len(by_frame) if by_frame else 0
        }
        
        return {
            "video_id": video_id,
            "total_detections": len(detections),
            "by_type": by_type,
            "confidence_stats": confidence_stats,
            "temporal_analysis": temporal_analysis,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get video summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate summary: {str(e)}"
        )

@app.post("/api/inference/single-frame")
async def inference_single_frame(
    frame_data: UploadFile = File(..., description="Image frame for inference"),
    frame_number: int = Query(..., description="Frame number"),
    timestamp: float = Query(..., description="Timestamp"),
    engine=Depends(get_ml_engine)
):
    """Perform inference on a single frame"""
    try:
        # Read frame data
        frame_bytes = await frame_data.read()
        
        # Convert to numpy array
        import cv2
        import numpy as np
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid image format"
            )
        
        # Run inference
        detections = await engine.yolo_engine.detect_vrus_single(
            frame, frame_number, timestamp
        )
        
        # Convert to response format
        response_detections = []
        for det in detections:
            response_detections.append({
                "detection_id": det.detection_id,
                "frame_number": det.frame_number,
                "timestamp": det.timestamp,
                "vru_type": det.vru_type,
                "confidence": det.confidence,
                "bounding_box": {
                    "x": det.bounding_box.x,
                    "y": det.bounding_box.y,
                    "width": det.bounding_box.width,
                    "height": det.bounding_box.height
                },
                "metadata": det.metadata
            })
        
        return {
            "frame_number": frame_number,
            "timestamp": timestamp,
            "detections": response_detections,
            "inference_time": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Single frame inference failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Inference failed: {str(e)}"
        )

# Custom exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": str(request.url)
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    logger.error(traceback.format_exc())
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": str(request.url)
            }
        }
    )

# Application lifecycle events
@app.on_event("startup")
async def startup_event():
    """Initialize ML engine on startup"""
    logger.info("Starting VRU ML Inference API...")
    
    if ML_ENGINE_AVAILABLE:
        try:
            await get_production_ml_engine()
            logger.info("ML Engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ML engine: {e}")
    else:
        logger.warning("ML Engine not available - API will run with limited functionality")
    
    logger.info("API startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down VRU ML Inference API...")
    # Add any cleanup code here
    logger.info("API shutdown complete")

# Main execution
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="VRU ML Inference API")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", default=8001, type=int, help="Port to bind to")
    parser.add_argument("--workers", default=1, type=int, help="Number of workers")
    parser.add_argument("--log-level", default="info", help="Log level")
    
    args = parser.parse_args()
    
    print(f"🚀 Starting VRU ML Inference API on {args.host}:{args.port}")
    print(f"📖 API Documentation: http://{args.host}:{args.port}/api/docs")
    
    uvicorn.run(
        "ml_api_endpoints:app",
        host=args.host,
        port=args.port,
        workers=args.workers,
        log_level=args.log_level,
        reload=False
    )