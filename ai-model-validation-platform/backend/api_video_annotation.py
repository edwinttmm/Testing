from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import logging
import json

from database import get_db
from models import (
    Video, Annotation, AnnotationSession, DetectionEvent, 
    GroundTruthObject, Project, TestSession
)
from schemas_video_annotation import (
    AnnotationCreate, AnnotationUpdate, AnnotationResponse,
    AnnotationSessionCreate, AnnotationSessionResponse,
    AnnotationExportRequest, AnnotationBulkCreate,
    VideoAnnotationStats, AnnotationValidationRequest
)
from services.video_annotation_service import VideoAnnotationService
from services.pre_annotation_service import PreAnnotationService
from services.camera_validation_service import CameraValidationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/annotations", tags=["Video Annotations"])

# Initialize services
video_annotation_service = VideoAnnotationService()
pre_annotation_service = PreAnnotationService()
camera_validation_service = CameraValidationService()

# ============================================================================
# VIDEO UPLOAD AND STORAGE ENDPOINTS
# ============================================================================

@router.post("/videos/{video_id}/annotations", response_model=AnnotationResponse)
async def create_video_annotation(
    video_id: str,
    annotation: AnnotationCreate,
    db: Session = Depends(get_db)
):
    """Create a new annotation for a video with validation"""
    try:
        # Verify video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Create annotation with validation
        created_annotation = await video_annotation_service.create_annotation(
            db, video_id, annotation
        )
        
        logger.info(f"Created annotation {created_annotation.id} for video {video_id}")
        return created_annotation
        
    except Exception as e:
        logger.error(f"Error creating annotation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create annotation: {str(e)}")

@router.post("/videos/{video_id}/annotations/bulk", response_model=List[AnnotationResponse])
async def create_bulk_annotations(
    video_id: str,
    annotations: AnnotationBulkCreate,
    db: Session = Depends(get_db)
):
    """Create multiple annotations for a video in a single transaction"""
    try:
        # Verify video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Create annotations in bulk
        created_annotations = await video_annotation_service.create_bulk_annotations(
            db, video_id, annotations.annotations
        )
        
        logger.info(f"Created {len(created_annotations)} annotations for video {video_id}")
        return created_annotations
        
    except Exception as e:
        logger.error(f"Error creating bulk annotations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create bulk annotations: {str(e)}")

# ============================================================================
# AI PRE-ANNOTATION SERVICE INTEGRATION
# ============================================================================

@router.post("/videos/{video_id}/pre-annotate")
async def trigger_pre_annotation(
    video_id: str,
    background_tasks: BackgroundTasks,
    model_name: str = Query("yolov8n", description="ML model to use for pre-annotation"),
    confidence_threshold: float = Query(0.5, description="Minimum confidence threshold"),
    db: Session = Depends(get_db)
):
    """Trigger AI pre-annotation for a video"""
    try:
        # Verify video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Start pre-annotation in background
        task_id = str(uuid.uuid4())
        background_tasks.add_task(
            pre_annotation_service.process_video,
            video_id, video.file_path, model_name, confidence_threshold, task_id
        )
        
        return {
            "task_id": task_id,
            "video_id": video_id,
            "status": "started",
            "message": "Pre-annotation started in background",
            "model": model_name,
            "confidence_threshold": confidence_threshold
        }
        
    except Exception as e:
        logger.error(f"Error starting pre-annotation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start pre-annotation: {str(e)}")

@router.get("/videos/{video_id}/pre-annotation/status")
async def get_pre_annotation_status(
    video_id: str,
    db: Session = Depends(get_db)
):
    """Get pre-annotation status for a video"""
    try:
        status = await pre_annotation_service.get_processing_status(video_id)
        return status
        
    except Exception as e:
        logger.error(f"Error getting pre-annotation status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get pre-annotation status: {str(e)}")

# ============================================================================
# ANNOTATION CRUD OPERATIONS
# ============================================================================

@router.get("/videos/{video_id}/annotations", response_model=List[AnnotationResponse])
async def get_video_annotations(
    video_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    validated_only: bool = Query(False),
    vru_type: Optional[str] = Query(None),
    frame_start: Optional[int] = Query(None),
    frame_end: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Get annotations for a video with filtering options"""
    try:
        # Build query with filters
        query = db.query(Annotation).filter(Annotation.video_id == video_id)
        
        if validated_only:
            query = query.filter(Annotation.validated == True)
        
        if vru_type:
            query = query.filter(Annotation.vru_type == vru_type)
        
        if frame_start is not None:
            query = query.filter(Annotation.frame_number >= frame_start)
        
        if frame_end is not None:
            query = query.filter(Annotation.frame_number <= frame_end)
        
        annotations = query.order_by(Annotation.frame_number).offset(skip).limit(limit).all()
        
        logger.info(f"Retrieved {len(annotations)} annotations for video {video_id}")
        return annotations
        
    except Exception as e:
        logger.error(f"Error getting video annotations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get annotations: {str(e)}")

@router.put("/annotations/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation(
    annotation_id: str,
    annotation_update: AnnotationUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing annotation"""
    try:
        updated_annotation = await video_annotation_service.update_annotation(
            db, annotation_id, annotation_update
        )
        
        if not updated_annotation:
            raise HTTPException(status_code=404, detail="Annotation not found")
        
        logger.info(f"Updated annotation {annotation_id}")
        return updated_annotation
        
    except Exception as e:
        logger.error(f"Error updating annotation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update annotation: {str(e)}")

@router.delete("/annotations/{annotation_id}")
async def delete_annotation(
    annotation_id: str,
    db: Session = Depends(get_db)
):
    """Delete an annotation"""
    try:
        deleted = await video_annotation_service.delete_annotation(db, annotation_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Annotation not found")
        
        logger.info(f"Deleted annotation {annotation_id}")
        return {"message": "Annotation deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting annotation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete annotation: {str(e)}")

# ============================================================================
# PROJECT MANAGEMENT WITH VIDEO SELECTION
# ============================================================================

@router.get("/projects/{project_id}/annotation-sessions", response_model=List[AnnotationSessionResponse])
async def get_project_annotation_sessions(
    project_id: str,
    db: Session = Depends(get_db)
):
    """Get all annotation sessions for a project"""
    try:
        sessions = db.query(AnnotationSession).filter(
            AnnotationSession.project_id == project_id
        ).order_by(AnnotationSession.created_at.desc()).all()
        
        return sessions
        
    except Exception as e:
        logger.error(f"Error getting annotation sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get annotation sessions: {str(e)}")

@router.post("/projects/{project_id}/annotation-sessions", response_model=AnnotationSessionResponse)
async def create_annotation_session(
    project_id: str,
    session_data: AnnotationSessionCreate,
    db: Session = Depends(get_db)
):
    """Create a new annotation session for a project"""
    try:
        # Verify project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Verify video exists
        video = db.query(Video).filter(Video.id == session_data.video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Create annotation session
        session = AnnotationSession(
            id=str(uuid.uuid4()),
            video_id=session_data.video_id,
            project_id=project_id,
            annotator_id=session_data.annotator_id,
            status="active",
            total_frames=video.duration * video.fps if video.duration and video.fps else 0,
            created_at=datetime.utcnow()
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        logger.info(f"Created annotation session {session.id} for project {project_id}")
        return session
        
    except Exception as e:
        logger.error(f"Error creating annotation session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create annotation session: {str(e)}")

# ============================================================================
# CAMERA SIGNAL DETECTION ENDPOINTS
# ============================================================================

@router.post("/camera/signals/detect")
async def detect_camera_signals(
    video_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    signal_type: str = Query(..., description="Type of signal to detect (GPIO, Network, Serial)")
):
    """Detect camera signals in video for validation"""
    try:
        # Verify video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Start signal detection in background
        task_id = str(uuid.uuid4())
        background_tasks.add_task(
            camera_validation_service.detect_signals,
            video_id, video.file_path, signal_type, task_id
        )
        
        return {
            "task_id": task_id,
            "video_id": video_id,
            "signal_type": signal_type,
            "status": "started",
            "message": "Signal detection started in background"
        }
        
    except Exception as e:
        logger.error(f"Error starting signal detection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start signal detection: {str(e)}")

@router.get("/camera/signals/{video_id}/results")
async def get_signal_detection_results(
    video_id: str,
    db: Session = Depends(get_db)
):
    """Get signal detection results for a video"""
    try:
        results = await camera_validation_service.get_detection_results(video_id)
        return results
        
    except Exception as e:
        logger.error(f"Error getting signal detection results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get signal detection results: {str(e)}")

# ============================================================================
# REAL-TIME VALIDATION SYSTEM
# ============================================================================

@router.post("/validation/real-time")
async def validate_real_time_detection(
    validation_request: AnnotationValidationRequest,
    db: Session = Depends(get_db)
):
    """Validate detection against ground truth in real-time"""
    try:
        # Get ground truth for comparison
        ground_truth = db.query(GroundTruthObject).filter(
            and_(
                GroundTruthObject.video_id == validation_request.video_id,
                GroundTruthObject.timestamp.between(
                    validation_request.timestamp - validation_request.tolerance_ms / 1000,
                    validation_request.timestamp + validation_request.tolerance_ms / 1000
                )
            )
        ).first()
        
        # Perform validation
        validation_result = await camera_validation_service.validate_detection(
            validation_request, ground_truth
        )
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Error validating real-time detection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to validate detection: {str(e)}")

@router.get("/validation/pass-fail/{test_session_id}")
async def get_pass_fail_results(
    test_session_id: str,
    db: Session = Depends(get_db)
):
    """Get pass/fail validation results for a test session"""
    try:
        # Get test session
        test_session = db.query(TestSession).filter(TestSession.id == test_session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Calculate pass/fail metrics
        results = await camera_validation_service.calculate_pass_fail_metrics(test_session_id)
        
        return results
        
    except Exception as e:
        logger.error(f"Error getting pass/fail results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get pass/fail results: {str(e)}")

# ============================================================================
# SIGNAL TIMING COMPARISON AND VALIDATION
# ============================================================================

@router.post("/timing/compare")
async def compare_signal_timing(
    video_id: str,
    reference_timestamps: List[float],
    detected_timestamps: List[float],
    tolerance_ms: int = Query(100, description="Tolerance in milliseconds"),
    db: Session = Depends(get_db)
):
    """Compare signal timing between reference and detected events"""
    try:
        # Perform timing comparison
        comparison_results = await camera_validation_service.compare_timing(
            reference_timestamps, detected_timestamps, tolerance_ms
        )
        
        return {
            "video_id": video_id,
            "tolerance_ms": tolerance_ms,
            "comparison_results": comparison_results,
            "total_reference": len(reference_timestamps),
            "total_detected": len(detected_timestamps),
            "timing_accuracy": comparison_results.get("accuracy", 0),
            "average_delay": comparison_results.get("average_delay", 0)
        }
        
    except Exception as e:
        logger.error(f"Error comparing signal timing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to compare signal timing: {str(e)}")

# ============================================================================
# ANNOTATION STATISTICS AND EXPORT
# ============================================================================

@router.get("/videos/{video_id}/stats", response_model=VideoAnnotationStats)
async def get_video_annotation_stats(
    video_id: str,
    db: Session = Depends(get_db)
):
    """Get annotation statistics for a video"""
    try:
        # Get video
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Calculate statistics
        total_annotations = db.query(func.count(Annotation.id)).filter(
            Annotation.video_id == video_id
        ).scalar() or 0
        
        validated_annotations = db.query(func.count(Annotation.id)).filter(
            and_(Annotation.video_id == video_id, Annotation.validated == True)
        ).scalar() or 0
        
        vru_type_distribution = dict(
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
            vru_type_distribution=vru_type_distribution,
            annotation_density=(
                total_annotations / video.duration 
                if video.duration and video.duration > 0 else 0
            )
        )
        
    except Exception as e:
        logger.error(f"Error getting annotation stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get annotation stats: {str(e)}")

@router.post("/videos/{video_id}/export")
async def export_annotations(
    video_id: str,
    export_request: AnnotationExportRequest,
    db: Session = Depends(get_db)
):
    """Export annotations in various formats"""
    try:
        # Verify video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Export annotations
        export_result = await video_annotation_service.export_annotations(
            db, video_id, export_request.format, export_request.include_metadata
        )
        
        return {
            "video_id": video_id,
            "format": export_request.format,
            "export_url": export_result.get("url"),
            "file_size": export_result.get("file_size"),
            "annotation_count": export_result.get("annotation_count"),
            "created_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error exporting annotations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export annotations: {str(e)}")
