"""
Video Validation API Endpoints

This module provides comprehensive API endpoints for the unified video validation system,
including status management, validation operations, and HIL testing readiness.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from database import get_db
from models import Video, VideoValidationCriteria, VideoValidationResult, VideoStatusTransition
from auth_dependencies import get_current_user
from services.video_validation_service import VideoValidationService
from schemas_video_validation import (
    VideoStatusResponse,
    VideoStatusUpdate,
    ValidationCriteriaRequest,
    ValidationCriteriaResponse,
    ValidationResultResponse,
    ValidationRequest,
    BatchStatusUpdate,
    StatusTransitionHistory,
    HILTestingApproval,
    ValidationQueueStatus
)

router = APIRouter(prefix="/api/v1/videos", tags=["video-validation"])

# Initialize validation service
validation_service = VideoValidationService()

@router.get("/{video_id}/status", response_model=VideoStatusResponse)
async def get_video_status(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get current status and validation information for a video"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Get latest validation result
    validation_result = db.query(VideoValidationResult)\
        .filter(VideoValidationResult.video_id == video_id)\
        .order_by(VideoValidationResult.created_at.desc())\
        .first()
    
    return VideoStatusResponse(
        video_id=video.id,
        status=video.status,
        validation_status=video.validation_status,
        validation_type=video.validation_type,
        validated_at=video.validated_at,
        validated_by=video.validated_by,
        hil_testing_ready=video.hil_testing_ready,
        hil_testing_approved_by=video.hil_testing_approved_by,
        hil_testing_approved_at=video.hil_testing_approved_at,
        ground_truth_count=video.ground_truth_count,
        ground_truth_quality_score=video.ground_truth_quality_score,
        validation_result=ValidationResultResponse.from_orm(validation_result) if validation_result else None
    )

@router.put("/{video_id}/status", response_model=VideoStatusResponse)
async def update_video_status(
    video_id: str,
    status_update: VideoStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update video status with validation and transition rules"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    try:
        # Use validation service to handle status transition
        updated_video = await validation_service.transition_video_status(
            video_id=video_id,
            new_status=status_update.status,
            reason=status_update.reason,
            triggered_by=current_user.get("id"),
            metadata=status_update.metadata,
            db=db
        )
        
        return await get_video_status(video_id, db, current_user)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")

@router.get("/{video_id}/validation-history", response_model=List[StatusTransitionHistory])
async def get_validation_history(
    video_id: str,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get status transition history for a video"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    transitions = db.query(VideoStatusTransition)\
        .filter(VideoStatusTransition.video_id == video_id)\
        .order_by(VideoStatusTransition.created_at.desc())\
        .limit(limit)\
        .all()
    
    return [StatusTransitionHistory.from_orm(t) for t in transitions]

@router.post("/{video_id}/validate", response_model=ValidationResultResponse)
async def validate_video(
    video_id: str,
    validation_request: ValidationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Trigger video validation (automatic or manual)"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check if video is in correct status for validation
    valid_statuses = ["annotated", "validation_failed"]
    if video.status not in valid_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Video must be in {valid_statuses} status for validation, currently: {video.status}"
        )
    
    try:
        if validation_request.validation_type == "automatic":
            # Run automatic validation in background
            background_tasks.add_task(
                validation_service.run_automatic_validation,
                video_id=video_id,
                criteria_id=validation_request.criteria_id,
                db=db
            )
            
            # Update status to validating
            await validation_service.transition_video_status(
                video_id=video_id,
                new_status="validating",
                reason="automatic_validation_started",
                triggered_by=current_user.get("id"),
                db=db
            )
            
            return ValidationResultResponse(
                id="pending",
                video_id=video_id,
                validation_type="automatic",
                overall_result="processing",
                message="Automatic validation started"
            )
            
        else:  # manual validation
            # Initiate manual validation workflow
            result = await validation_service.initiate_manual_validation(
                video_id=video_id,
                validated_by=current_user.get("id"),
                criteria_id=validation_request.criteria_id,
                notes=validation_request.notes,
                db=db
            )
            
            return ValidationResultResponse.from_orm(result)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

@router.post("/{video_id}/validate/automatic", response_model=ValidationResultResponse)
async def run_automatic_validation(
    video_id: str,
    criteria_id: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Run automatic validation with AI-based quality assessment"""
    
    validation_request = ValidationRequest(
        validation_type="automatic",
        criteria_id=criteria_id
    )
    
    return await validate_video(video_id, validation_request, background_tasks, db, current_user)

@router.post("/{video_id}/validate/manual", response_model=ValidationResultResponse)
async def submit_manual_validation(
    video_id: str,
    validation_request: ValidationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Submit manual validation result"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    try:
        result = await validation_service.complete_manual_validation(
            video_id=video_id,
            validation_result=validation_request.manual_result,
            validated_by=current_user.get("id"),
            criteria_id=validation_request.criteria_id,
            notes=validation_request.notes,
            scores=validation_request.scores,
            db=db
        )
        
        return ValidationResultResponse.from_orm(result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Manual validation failed: {str(e)}")

@router.get("/{video_id}/validation-result", response_model=ValidationResultResponse)
async def get_validation_result(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get the latest validation result for a video"""
    
    result = db.query(VideoValidationResult)\
        .filter(VideoValidationResult.video_id == video_id)\
        .order_by(VideoValidationResult.created_at.desc())\
        .first()
    
    if not result:
        raise HTTPException(status_code=404, detail="No validation result found")
    
    return ValidationResultResponse.from_orm(result)

# Validation Criteria Management

@router.get("/validation/criteria", response_model=List[ValidationCriteriaResponse])
async def list_validation_criteria(
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List validation criteria (global or project-specific)"""
    
    query = db.query(VideoValidationCriteria)
    if project_id:
        query = query.filter(VideoValidationCriteria.project_id == project_id)
    
    criteria = query.order_by(VideoValidationCriteria.created_at.desc()).all()
    return [ValidationCriteriaResponse.from_orm(c) for c in criteria]

@router.post("/validation/criteria", response_model=ValidationCriteriaResponse)
async def create_validation_criteria(
    criteria_request: ValidationCriteriaRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create new validation criteria"""
    
    criteria = VideoValidationCriteria(
        project_id=criteria_request.project_id,
        min_detection_count=criteria_request.min_detection_count,
        min_confidence_threshold=criteria_request.min_confidence_threshold,
        min_frame_coverage_percent=criteria_request.min_frame_coverage_percent,
        min_duration_seconds=criteria_request.min_duration_seconds,
        max_duration_seconds=criteria_request.max_duration_seconds,
        required_resolution_min=criteria_request.required_resolution_min,
        min_fps=criteria_request.min_fps,
        required_vru_types=criteria_request.required_vru_types,
        min_scene_complexity_score=criteria_request.min_scene_complexity_score
    )
    
    db.add(criteria)
    db.commit()
    db.refresh(criteria)
    
    return ValidationCriteriaResponse.from_orm(criteria)

@router.get("/validation/criteria/{criteria_id}", response_model=ValidationCriteriaResponse)
async def get_validation_criteria(
    criteria_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get specific validation criteria"""
    
    criteria = db.query(VideoValidationCriteria)\
        .filter(VideoValidationCriteria.id == criteria_id)\
        .first()
    
    if not criteria:
        raise HTTPException(status_code=404, detail="Validation criteria not found")
    
    return ValidationCriteriaResponse.from_orm(criteria)

@router.put("/validation/criteria/{criteria_id}", response_model=ValidationCriteriaResponse)
async def update_validation_criteria(
    criteria_id: str,
    criteria_request: ValidationCriteriaRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update validation criteria"""
    
    criteria = db.query(VideoValidationCriteria)\
        .filter(VideoValidationCriteria.id == criteria_id)\
        .first()
    
    if not criteria:
        raise HTTPException(status_code=404, detail="Validation criteria not found")
    
    # Update fields
    for field, value in criteria_request.dict(exclude_unset=True).items():
        setattr(criteria, field, value)
    
    db.commit()
    db.refresh(criteria)
    
    return ValidationCriteriaResponse.from_orm(criteria)

# HIL Testing Readiness

@router.get("/ready-for-testing", response_model=List[VideoStatusResponse])
async def get_videos_ready_for_testing(
    project_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get videos that are ready for HIL testing"""
    
    query = db.query(Video).filter(Video.hil_testing_ready == True)
    
    if project_id:
        query = query.filter(Video.project_id == project_id)
    
    videos = query.order_by(Video.validated_at.desc())\
        .offset(offset)\
        .limit(limit)\
        .all()
    
    results = []
    for video in videos:
        # Get validation result for each video
        validation_result = db.query(VideoValidationResult)\
            .filter(VideoValidationResult.video_id == video.id)\
            .order_by(VideoValidationResult.created_at.desc())\
            .first()
        
        results.append(VideoStatusResponse(
            video_id=video.id,
            status=video.status,
            validation_status=video.validation_status,
            validation_type=video.validation_type,
            validated_at=video.validated_at,
            validated_by=video.validated_by,
            hil_testing_ready=video.hil_testing_ready,
            hil_testing_approved_by=video.hil_testing_approved_by,
            hil_testing_approved_at=video.hil_testing_approved_at,
            ground_truth_count=video.ground_truth_count,
            ground_truth_quality_score=video.ground_truth_quality_score,
            validation_result=ValidationResultResponse.from_orm(validation_result) if validation_result else None
        ))
    
    return results

@router.post("/{video_id}/approve-for-testing", response_model=VideoStatusResponse)
async def approve_video_for_testing(
    video_id: str,
    approval: HILTestingApproval,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Approve a validated video for HIL testing"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if video.status != "validated":
        raise HTTPException(
            status_code=400,
            detail=f"Video must be validated before HIL approval, currently: {video.status}"
        )
    
    try:
        # Update video HIL testing approval
        video.hil_testing_ready = True
        video.hil_testing_approved_by = current_user.get("id")
        video.hil_testing_approved_at = datetime.utcnow()
        video.status = "ready_for_testing"
        
        # Create transition record
        transition = VideoStatusTransition(
            video_id=video_id,
            from_status="validated",
            to_status="ready_for_testing",
            transition_reason="hil_testing_approved",
            triggered_by=current_user.get("id"),
            metadata={"approval_notes": approval.notes}
        )
        
        db.add(transition)
        db.commit()
        db.refresh(video)
        
        return await get_video_status(video_id, db, current_user)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to approve for testing: {str(e)}")

@router.post("/{video_id}/mark-in-testing", response_model=VideoStatusResponse)
async def mark_video_in_testing(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Mark video as currently being used in HIL testing"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if not video.hil_testing_ready:
        raise HTTPException(status_code=400, detail="Video not approved for testing")
    
    try:
        updated_video = await validation_service.transition_video_status(
            video_id=video_id,
            new_status="in_testing",
            reason="hil_test_session_started",
            triggered_by=current_user.get("id"),
            db=db
        )
        
        return await get_video_status(video_id, db, current_user)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark as in testing: {str(e)}")

@router.post("/{video_id}/mark-tested", response_model=VideoStatusResponse)
async def mark_video_tested(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Mark video as completed HIL testing"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if video.status != "in_testing":
        raise HTTPException(
            status_code=400,
            detail=f"Video must be in testing to mark as tested, currently: {video.status}"
        )
    
    try:
        updated_video = await validation_service.transition_video_status(
            video_id=video_id,
            new_status="tested",
            reason="hil_test_session_completed",
            triggered_by=current_user.get("id"),
            db=db
        )
        
        return await get_video_status(video_id, db, current_user)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark as tested: {str(e)}")

# Batch Operations

@router.post("/batch-validate")
async def batch_validate_videos(
    video_ids: List[str],
    validation_type: str = "automatic",
    criteria_id: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Validate multiple videos in batch"""
    
    if len(video_ids) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 videos per batch operation")
    
    # Verify all videos exist and are in valid status
    videos = db.query(Video).filter(Video.id.in_(video_ids)).all()
    if len(videos) != len(video_ids):
        raise HTTPException(status_code=400, detail="One or more videos not found")
    
    valid_statuses = ["annotated", "validation_failed"]
    invalid_videos = [v for v in videos if v.status not in valid_statuses]
    if invalid_videos:
        raise HTTPException(
            status_code=400,
            detail=f"Videos must be in {valid_statuses} status for validation"
        )
    
    # Start batch validation
    if validation_type == "automatic":
        background_tasks.add_task(
            validation_service.batch_automatic_validation,
            video_ids=video_ids,
            criteria_id=criteria_id,
            triggered_by=current_user.get("id"),
            db=db
        )
        
        return {"message": f"Batch automatic validation started for {len(video_ids)} videos"}
    else:
        raise HTTPException(status_code=400, detail="Manual validation not supported in batch mode")

@router.get("/validation-queue", response_model=ValidationQueueStatus)
async def get_validation_queue_status(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get current validation queue status"""
    
    # Count videos by validation status
    pending_count = db.query(Video).filter(Video.validation_status == "pending").count()
    processing_count = db.query(Video).filter(Video.validation_status == "processing").count()
    validating_count = db.query(Video).filter(Video.status == "validating").count()
    failed_count = db.query(Video).filter(Video.validation_status == "failed").count()
    
    return ValidationQueueStatus(
        pending_validation=pending_count,
        currently_validating=validating_count + processing_count,
        validation_failed=failed_count,
        total_in_queue=pending_count + processing_count + validating_count
    )

@router.post("/batch-status-update")
async def batch_status_update(
    batch_update: BatchStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update status for multiple videos"""
    
    if len(batch_update.video_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 videos per batch operation")
    
    success_count = 0
    errors = []
    
    for video_id in batch_update.video_ids:
        try:
            await validation_service.transition_video_status(
                video_id=video_id,
                new_status=batch_update.new_status,
                reason=batch_update.reason,
                triggered_by=current_user.get("id"),
                metadata=batch_update.metadata,
                db=db
            )
            success_count += 1
        except Exception as e:
            errors.append({"video_id": video_id, "error": str(e)})
    
    return {
        "success_count": success_count,
        "error_count": len(errors),
        "errors": errors[:10]  # Limit error details
    }