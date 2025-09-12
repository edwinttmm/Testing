"""
API Endpoints for PRD Module 1.1 & 1.2: Video Ingestion Pipeline
FastAPI router implementing complete video ingestion workflow with real YOLO detection
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import logging
import asyncio
from pathlib import Path

from database import get_db
from services.video_ingestion_service import VideoIngestionService
from schemas import VideoUploadResponse, VideoStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/videos", tags=["Video Ingestion"])

# Initialize service
video_service = VideoIngestionService()

@router.post("/upload", response_model=Dict[str, Any])
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Video file (MP4, MOV, AVI)"),
    project_id: Optional[str] = Form(None, description="Project ID to assign video to"),
    db: Session = Depends(get_db)
):
    """
    PRD Module 1.1: Video Ingestion
    Upload video file with format validation and automatic processing
    
    - Supports MP4, MOV, AVI formats
    - Validates file size and format
    - Assigns "Pending Annotation" status
    - Triggers automated annotation processing
    """
    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in {'.mp4', '.mov', '.avi'}:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format {file_ext}. Supported: MP4, MOV, AVI"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Validate file size (2GB limit)
        max_size = 2048 * 1024 * 1024  # 2GB
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Maximum size: {max_size // (1024*1024)}MB"
            )
        
        # Process upload
        result = await video_service.process_video_upload(
            db=db,
            file_content=file_content,
            filename=file.filename,
            project_id=project_id
        )
        
        logger.info(f"Video upload successful: {file.filename}")
        
        return {
            "success": True,
            "data": result,
            "message": "Video uploaded successfully and queued for automated annotation"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading video: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/{video_id}/process-annotation")
async def process_video_annotation(
    video_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    PRD Module 1.2: Automated Annotation
    Trigger real YOLO-based VRU detection and annotation
    
    - Uses Ultralytics YOLO for VRU detection
    - Assigns persistent VRU IDs
    - Moves video to "Pending Validation" status
    """
    try:
        # Add background task for processing
        background_tasks.add_task(
            video_service.process_automated_annotation,
            db, video_id
        )
        
        return {
            "success": True,
            "message": f"Automated annotation processing started for video {video_id}",
            "video_id": video_id,
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"Error processing annotation for video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@router.get("/library")
async def get_video_library(
    status: Optional[str] = None,
    project_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    PRD Module 1.4: Video Library
    Get video library with filtering and search capabilities
    
    - Filter by status (pending_annotation, pending_validation, validated)
    - Filter by project
    - View annotation status and metadata
    """
    try:
        videos = await video_service.get_video_library(
            db=db,
            status_filter=status,
            project_id=project_id
        )
        
        return {
            "success": True,
            "data": {
                "videos": videos,
                "total_count": len(videos),
                "filters_applied": {
                    "status": status,
                    "project_id": project_id
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting video library: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get video library: {str(e)}")

@router.get("/{video_id}/annotations")
async def get_video_annotations(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Get annotations for a specific video with bounding box data
    
    - Returns all detected VRUs with persistent IDs
    - Includes bounding box coordinates
    - Shows validation status
    """
    try:
        annotations = await video_service.get_video_annotations(db, video_id)
        
        return {
            "success": True,
            "data": annotations
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting annotations for video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get annotations: {str(e)}")

@router.post("/{video_id}/validate")
async def validate_video_annotations(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    PRD Module 1.3: Annotation Validation
    Mark video annotations as validated and lock them
    
    - Moves from "Pending Validation" to "Validated" status
    - Makes video available for testing projects
    - Locks annotations to prevent further changes
    """
    try:
        result = await video_service.validate_video_annotations(db, video_id)
        
        return {
            "success": True,
            "data": result,
            "message": "Video annotations validated successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error validating video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

@router.get("/{video_id}/status")
async def get_video_status(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Get current video processing status and metadata
    
    - Shows current status in PRD workflow
    - Returns processing progress
    - Includes annotation counts and metadata
    """
    try:
        from models import Video, GroundTruthObject
        
        # Get video
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get annotation count
        annotation_count = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == video_id
        ).count()
        
        return {
            "success": True,
            "data": {
                "video_id": video_id,
                "filename": video.filename,
                "status": video.status,
                "processing_status": video.processing_status,
                "ground_truth_generated": video.ground_truth_generated,
                "annotation_count": annotation_count,
                "duration": video.duration,
                "file_size": video.file_size,
                "created_at": video.created_at.isoformat() if video.created_at else None,
                "workflow_stage": {
                    "current": video.status,
                    "next_action": {
                        "pending_annotation": "Wait for automated annotation processing",
                        "pending_validation": "Review and validate annotations",
                        "validated": "Ready for test projects",
                        "error": "Check error logs and retry"
                    }.get(video.status, "Unknown")
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.get("/{video_id}/tracking-stats")
async def get_tracking_statistics(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Get VRU tracking statistics for debugging and analysis
    
    - Shows tracking performance metrics
    - VRU counts by type
    - Track persistence statistics
    """
    try:
        stats = video_service.vru_tracker.get_track_statistics(video_id)
        
        return {
            "success": True,
            "data": {
                "video_id": video_id,
                "tracking_statistics": stats
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting tracking stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get tracking stats: {str(e)}")

@router.delete("/{video_id}")
async def delete_video(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete video and all associated data
    
    - Removes video file from storage
    - Deletes all annotations
    - Removes project associations
    """
    try:
        from models import Video, GroundTruthObject, VideoProjectLink
        import os
        
        # Get video
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Delete physical file
        if video.file_path and os.path.exists(video.file_path):
            try:
                os.remove(video.file_path)
            except OSError as e:
                logger.warning(f"Could not delete file {video.file_path}: {e}")
        
        # Delete database records (cascade will handle related data)
        db.delete(video)
        db.commit()
        
        logger.info(f"Video {video_id} deleted successfully")
        
        return {
            "success": True,
            "message": f"Video {video_id} deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting video {video_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {str(e)}")

# Health check endpoint
@router.get("/health")
async def video_service_health():
    """Check video ingestion service health and YOLO model availability"""
    try:
        model_status = "available" if video_service.yolo_model else "unavailable"
        yolo_available = hasattr(video_service, 'yolo_model') and video_service.yolo_model is not None
        
        return {
            "success": True,
            "data": {
                "service": "video_ingestion",
                "status": "healthy",
                "yolo_model": model_status,
                "real_ai_detection": yolo_available,
                "supported_formats": list(VideoIngestionService.SUPPORTED_FORMATS),
                "max_file_size_mb": VideoIngestionService.MAX_FILE_SIZE // (1024 * 1024)
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "status": "unhealthy"
        }