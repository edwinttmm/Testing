"""
Video Management Router - Organized API Endpoints
==============================================

Consolidated video-related endpoints following FastAPI best practices.
Handles video upload, processing, annotations, and ground truth management.
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import os
import uuid
import aiofiles
import tempfile
import asyncio
from pathlib import Path

# Import path management utilities
try:
    from src.utils.path_utils import (
        get_path_manager, resolve_upload_path, migrate_legacy_path, 
        ensure_path_exists, is_safe_path
    )
    PATH_UTILS_AVAILABLE = True
except ImportError:
    PATH_UTILS_AVAILABLE = False
    logger.warning("Path utilities not available - using basic path handling")

from database import SessionLocal
from models import Video, Project, Annotation, GroundTruthObject, DetectionEvent
from schemas import VideoUploadResponse, GroundTruthResponse
from schemas_annotation import (
    AnnotationCreate, AnnotationResponse, AnnotationUpdate,
    VideoAnnotationStats
)
from services.ground_truth_service import GroundTruthService
from services.video_library_service import VideoLibraryManager
from crud import create_video

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/videos", tags=["Video Management"])

# Initialize services
ground_truth_service = GroundTruthService()
video_library_manager = VideoLibraryManager()

# Initialize path manager if available
if PATH_UTILS_AVAILABLE:
    path_manager = get_path_manager()
    logger.info("✅ Path manager initialized for video router")
else:
    path_manager = None
    logger.warning("⚠️ Path manager not available - using basic file handling")

# Error handling wrapper for ground truth processing
async def _process_ground_truth_with_error_handling(video_id: str, video_file_path: str, db_url: str):
    """
    Wrapper function to handle ground truth processing with proper error handling
    and timeout management
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # Create new database session for background task
    engine = create_engine(str(db_url))
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        logger.info(f"🚀 Starting ground truth processing for video {video_id}")
        
        # Set timeout of 10 minutes for processing
        await asyncio.wait_for(
            ground_truth_service.process_video_async(video_id, video_file_path),
            timeout=600  # 10 minutes
        )
        
        logger.info(f"✅ Successfully completed ground truth processing for video {video_id}")
        
    except asyncio.TimeoutError:
        logger.error(f"⏰ Ground truth processing timed out for video {video_id}")
        # Update video status to failed due to timeout
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.status = "failed"
                video.processing_status = "timeout"
                db.commit()
                logger.info(f"📝 Updated video {video_id} status to timeout")
        except Exception as db_error:
            logger.error(f"Failed to update video status on timeout: {str(db_error)}")
            
    except Exception as e:
        logger.error(f"💥 Error in ground truth processing for video {video_id}: {str(e)}")
        logger.exception("Full error details:")
        
        # Update video status to failed
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.status = "failed"
                video.processing_status = "failed"
                db.commit()
                logger.info(f"📝 Updated video {video_id} status to failed")
        except Exception as db_error:
            logger.error(f"Failed to update video status on error: {str(db_error)}")
            
    finally:
        db.close()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# VIDEO UPLOAD AND STORAGE
# ============================================================================

@router.post("", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    project_id: Optional[str] = Query(None, description="Associate with specific project"),
    db: Session = Depends(get_db)
):
    """Upload a new video file with optional project association"""
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('video/'):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Expected video file, got {file.content_type}"
            )
        
        # Handle project_id - either provided or use default
        if project_id:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
        else:
            # Use default project if none provided
            project = db.query(Project).filter(Project.id == "default-test-project").first()
            if not project:
                # Fallback to first available project
                project = db.query(Project).first()
                if not project:
                    raise HTTPException(status_code=400, detail="No projects available. Please create a project first.")
            project_id = project.id
            logger.info(f"Using default project: {project_id}")
            
        # Ensure we have a valid project_id
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID is required for video upload")
        
        # Handle file path with robust path management
        if path_manager and PATH_UTILS_AVAILABLE:
            # Use path manager for robust file handling
            file_extension = Path(file.filename).suffix
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = resolve_upload_path(unique_filename)
            logger.info(f"🗂️ Using managed upload path: {file_path}")
        else:
            # Fallback to basic directory handling
            upload_dir = Path("uploads")
            upload_dir.mkdir(exist_ok=True)
            
            # Generate unique filename
            file_extension = Path(file.filename).suffix
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = upload_dir / unique_filename
            logger.info(f"📁 Using basic upload path: {file_path}")
        
        # Save file to disk
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Create video record with absolute path
        absolute_file_path = str(file_path.resolve()) if hasattr(file_path, 'resolve') else str(Path(file_path).resolve())
        
        # Validate path safety if path manager is available
        if path_manager and PATH_UTILS_AVAILABLE:
            if not is_safe_path(absolute_file_path):
                logger.error(f"❌ Unsafe file path detected: {absolute_file_path}")
                raise HTTPException(status_code=400, detail="Invalid file path")
        
        logger.info(f"💾 Storing video with absolute path: {absolute_file_path}")
        
        # Call create_video with correct parameters matching the function signature
        video = create_video(
            db=db,
            filename=file.filename,
            file_path=absolute_file_path,
            file_size=len(content),
            project_ids=[project_id] if project_id else None
        )
        
        logger.info(f"Video uploaded successfully: {file.filename} -> {video.id}")
        
        return VideoUploadResponse(
            id=video.id,
            project_id=video.project_id,
            filename=video.filename,
            original_name=file.filename,
            size=len(content),
            file_size=video.file_size,
            duration=video.duration,
            uploaded_at=video.created_at.isoformat() if video.created_at else "",
            created_at=video.created_at.isoformat() if video.created_at else "",
            status=video.status or "uploaded",
            ground_truth_generated=video.ground_truth_generated or False,
            processing_status=video.processing_status or "pending",
            detection_count=video.ground_truth_count or 0,
            message="Video uploaded successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload video: {str(e)}")

@router.post("/{project_id}/videos", response_model=VideoUploadResponse)
async def upload_video_to_project(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a video directly to a specific project"""
    try:
        # Verify project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Use main upload endpoint with project_id
        return await upload_video(file=file, project_id=project_id, db=db)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading video to project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload video: {str(e)}")

# ============================================================================
# VIDEO LISTING AND RETRIEVAL
# ============================================================================

@router.get("")
async def list_videos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    has_annotations: Optional[bool] = Query(None, description="Filter by annotation status"),
    db: Session = Depends(get_db)
):
    """List videos with optional filtering and pagination"""
    try:
        query = db.query(Video)
        
        # Apply filters
        if project_id:
            query = query.filter(Video.project_id == project_id)
        
        if has_annotations is not None:
            if has_annotations:
                query = query.join(Annotation).distinct()
            else:
                query = query.outerjoin(Annotation).filter(Annotation.id.is_(None))
        
        videos = query.offset(skip).limit(limit).all()
        
        # Enrich with annotation counts
        video_list = []
        for video in videos:
            annotation_count = db.query(func.count(Annotation.id)).filter(
                Annotation.video_id == video.id
            ).scalar() or 0
            
            video_list.append({
                "id": video.id,
                "filename": video.filename,
                "file_path": video.file_path,
                "file_size": video.file_size,
                "duration": video.duration,
                "fps": video.fps,
                "project_id": video.project_id,
                "uploaded_at": video.created_at.isoformat() if video.created_at else None,
                "annotation_count": annotation_count,
                "has_ground_truth": db.query(GroundTruthObject).filter(
                    GroundTruthObject.video_id == video.id
                ).first() is not None
            })
        
        # Get total count for proper pagination
        total = query.count()
        
        logger.info(f"Retrieved {len(video_list)} videos out of {total} total")
        
        # Return in format expected by frontend: {videos: [...], total: number}
        return {
            "videos": video_list,
            "total": total
        }
        
    except Exception as e:
        logger.error(f"Error listing videos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list videos: {str(e)}")

@router.get("/{project_id}/videos")
async def get_project_videos(
    project_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get all videos associated with a project"""
    try:
        # Verify project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get project videos with enhanced information
        videos = db.query(Video).filter(Video.project_id == project_id).offset(skip).limit(limit).all()
        
        video_details = []
        for video in videos:
            # Get annotation and detection counts
            annotation_count = db.query(func.count(Annotation.id)).filter(
                Annotation.video_id == video.id
            ).scalar() or 0
            
            detection_count = db.query(func.count(DetectionEvent.id)).filter(
                DetectionEvent.video_id == video.id
            ).scalar() or 0
            
            video_details.append({
                "id": video.id,
                "filename": video.filename,
                "file_path": video.file_path,
                "file_size": video.file_size,
                "duration": video.duration,
                "fps": video.fps,
                "uploaded_at": video.created_at.isoformat() if video.created_at else None,
                "annotation_count": annotation_count,
                "detection_count": detection_count,
                "processing_status": video.processing_status or "ready"
            })
        
        return {
            "project_id": project_id,
            "project_name": project.name,
            "videos": video_details,
            "total_videos": len(video_details),
            "pagination": {
                "skip": skip,
                "limit": limit,
                "has_more": len(video_details) == limit
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving project videos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve videos: {str(e)}")

# ============================================================================
# VIDEO PROCESSING AND ANALYSIS
# ============================================================================

@router.post("/{video_id}/process-ground-truth")
async def process_ground_truth(
    video_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Process ground truth data for a video"""
    try:
        # Verify video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Update video status to processing ground truth
        video.status = "processing"
        video.processing_status = "processing_ground_truth"
        db.commit()
        
        # Resolve video path before processing
        video_file_path = video.file_path
        
        # Use path manager to resolve path if available
        if path_manager and PATH_UTILS_AVAILABLE:
            try:
                resolved_path = migrate_legacy_path(video.file_path)
                video_file_path = str(resolved_path)
                logger.info(f"🔗 Resolved video path for processing: {video.file_path} -> {video_file_path}")
            except Exception as e:
                logger.warning(f"Path resolution failed, using original: {e}")
        
        # Start ground truth processing in background with proper error handling
        background_tasks.add_task(
            _process_ground_truth_with_error_handling,
            video_id,
            video_file_path,
            db.get_bind().url
        )
        
        return {
            "video_id": video_id,
            "status": "processing",
            "message": "Ground truth processing started"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting ground truth processing: {str(e)}")
        # Ensure video status is reset on error
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.status = "failed"
                video.processing_status = "failed"
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update video status on error: {str(db_error)}")
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")

@router.get("/{video_id}/ground-truth", response_model=GroundTruthResponse)
async def get_video_ground_truth(video_id: str, db: Session = Depends(get_db)):
    """Get ground truth data for a video"""
    try:
        # Verify video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get ground truth objects
        ground_truth_objects = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == video_id
        ).all()
        
        if not ground_truth_objects:
            raise HTTPException(
                status_code=404,
                detail="No ground truth data found for this video"
            )
        
        # Format response
        ground_truth_data = [
            {
                "id": obj.id,
                "timestamp": obj.timestamp,
                "vru_type": obj.vru_type,
                "bounding_box": obj.bounding_box,
                "confidence": obj.confidence
            }
            for obj in ground_truth_objects
        ]
        
        return GroundTruthResponse(
            video_id=video_id,
            ground_truth_objects=ground_truth_data,
            total_objects=len(ground_truth_data)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving ground truth: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve ground truth: {str(e)}")

# ============================================================================
# VIDEO ANNOTATIONS
# ============================================================================

@router.post("/{video_id}/annotations", response_model=AnnotationResponse)
async def create_video_annotation(
    video_id: str,
    annotation: AnnotationCreate,
    db: Session = Depends(get_db)
):
    """Create a new annotation for a video"""
    try:
        # Verify video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Create annotation - FIXED: Avoid video_id conflict
        annotation_data = annotation.dict()
        annotation_data.pop('video_id', None)  # Remove video_id to avoid duplicate parameter
        
        db_annotation = Annotation(
            id=str(uuid.uuid4()),
            video_id=video_id,  # Use path parameter only
            **annotation_data
        )
        
        db.add(db_annotation)
        db.commit()
        db.refresh(db_annotation)
        
        logger.info(f"Annotation created for video {video_id}")
        return db_annotation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating annotation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create annotation: {str(e)}")

@router.get("/{video_id}/annotations")
async def get_video_annotations(
    video_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    validated_only: bool = Query(False),
    frame_start: Optional[int] = Query(None),
    frame_end: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Get annotations for a video with filtering options"""
    try:
        # Verify video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Build query with filters
        query = db.query(Annotation).filter(Annotation.video_id == video_id)
        
        if validated_only:
            query = query.filter(Annotation.validated == True)
        
        if frame_start is not None:
            query = query.filter(Annotation.frame_number >= frame_start)
        
        if frame_end is not None:
            query = query.filter(Annotation.frame_number <= frame_end)
        
        annotations = query.order_by(Annotation.frame_number).offset(skip).limit(limit).all()
        
        return {
            "video_id": video_id,
            "annotations": annotations,
            "total_annotations": len(annotations),
            "filters_applied": {
                "validated_only": validated_only,
                "frame_range": [frame_start, frame_end] if frame_start or frame_end else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving annotations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve annotations: {str(e)}")

@router.get("/{video_id}/stats", response_model=VideoAnnotationStats)
async def get_video_annotation_stats(video_id: str, db: Session = Depends(get_db)):
    """Get annotation statistics for a video"""
    try:
        # Verify video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Calculate statistics
        total_annotations = db.query(func.count(Annotation.id)).filter(
            Annotation.video_id == video_id
        ).scalar() or 0
        
        validated_annotations = db.query(func.count(Annotation.id)).filter(
            Annotation.video_id == video_id,
            Annotation.validated == True
        ).scalar() or 0
        
        # Get VRU type distribution
        vru_distribution = dict(
            db.query(Annotation.vru_type, func.count(Annotation.id))
            .filter(Annotation.video_id == video_id)
            .group_by(Annotation.vru_type)
            .all()
        )
        
        return VideoAnnotationStats(
            video_id=video_id,
            total_annotations=total_annotations,
            validated_annotations=validated_annotations,
            validation_percentage=(
                (validated_annotations / total_annotations * 100) 
                if total_annotations > 0 else 0
            ),
            vru_type_distribution=vru_distribution,
            annotation_density=(
                total_annotations / video.duration 
                if video.duration and video.duration > 0 else 0
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating annotation stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate stats: {str(e)}")

# ============================================================================
# VIDEO MANAGEMENT AND UTILITIES
# ============================================================================

@router.delete("/{video_id}")
async def delete_video(video_id: str, db: Session = Depends(get_db)):
    """Delete a video and all associated data"""
    try:
        # Find video
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Check for dependent data
        annotation_count = db.query(func.count(Annotation.id)).filter(
            Annotation.video_id == video_id
        ).scalar() or 0
        
        detection_count = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.video_id == video_id
        ).scalar() or 0
        
        # Delete physical file with path resolution
        if video.file_path:
            file_to_delete = None
            
            # Try to resolve the file path
            if path_manager and PATH_UTILS_AVAILABLE:
                try:
                    # Attempt to migrate/resolve legacy path
                    resolved_path = migrate_legacy_path(video.file_path)
                    if resolved_path.exists():
                        file_to_delete = resolved_path
                        logger.info(f"🗂️ Resolved file path for deletion: {resolved_path}")
                except Exception as e:
                    logger.warning(f"Path resolution failed for deletion: {e}")
            
            # Fallback to direct path check
            if file_to_delete is None and os.path.exists(video.file_path):
                file_to_delete = Path(video.file_path)
            
            # Delete the file if found
            if file_to_delete:
                try:
                    if file_to_delete.is_file():
                        file_to_delete.unlink()
                        logger.info(f"🗑️ Deleted video file: {file_to_delete}")
                    else:
                        logger.warning(f"Path is not a file: {file_to_delete}")
                except Exception as e:
                    logger.warning(f"Failed to delete video file {file_to_delete}: {e}")
            else:
                logger.warning(f"Video file not found for deletion: {video.file_path}")
        
        # Delete database record - validation tables now exist, cascade deletes will work properly
        try:
            db.delete(video)
            db.commit()
        except Exception as db_error:
            db.rollback()
            logger.error(f"Database error during video deletion: {db_error}")
            raise HTTPException(status_code=500, detail=f"Database error during deletion: {str(db_error)}")
        
        logger.info(f"Video deleted: {video_id} (had {annotation_count} annotations, {detection_count} detections)")
        
        return {
            "message": "Video deleted successfully",
            "video_id": video_id,
            "deleted_annotations": annotation_count,
            "deleted_detections": detection_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {str(e)}")

@router.get("/{video_id}/detections")
async def get_video_detections(
    video_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get detection events for a video"""
    try:
        # Verify video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get detections
        detections = db.query(DetectionEvent).filter(
            DetectionEvent.video_id == video_id
        ).order_by(DetectionEvent.timestamp).offset(skip).limit(limit).all()
        
        return {
            "video_id": video_id,
            "detections": [
                {
                    "id": detection.id,
                    "timestamp": detection.timestamp,
                    "vru_type": detection.vru_type,
                    "confidence": detection.confidence,
                    "bounding_box": {
                        "x": detection.bounding_box_x,
                        "y": detection.bounding_box_y,
                        "width": detection.bounding_box_width,
                        "height": detection.bounding_box_height
                    } if detection.bounding_box_x is not None else None,
                    "created_at": detection.created_at.isoformat()
                }
                for detection in detections
            ],
            "total_detections": len(detections)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving detections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve detections: {str(e)}")

# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def videos_health_check():
    """Health check endpoint for video management"""
    # Include path management status
    path_status = "enabled" if PATH_UTILS_AVAILABLE and path_manager else "disabled"
    
    return {
        "status": "healthy",
        "service": "Video Management Router",
        "version": "1.0.0",
        "path_management": path_status,
        "endpoints": [
            "POST /api/videos - Upload video",
            "GET /api/videos - List videos",
            "POST /api/videos/{project_id}/videos - Upload to project",
            "GET /api/videos/{project_id}/videos - Get project videos",
            "DELETE /api/videos/{id} - Delete video",
            "POST /api/videos/{id}/annotations - Create annotation",
            "GET /api/videos/{id}/annotations - Get annotations",
            "GET /api/videos/{id}/stats - Get annotation stats",
            "GET /api/videos/{id}/ground-truth - Get ground truth"
        ]
    }