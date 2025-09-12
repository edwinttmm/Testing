"""
Video Validation API Endpoints
Provides manual video validation capabilities for the video status workflow
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime

from database import get_db
from models import Video
from schemas import CamelCaseModel, VideoResponse
from crud import get_video, get_videos
from services.ground_truth_service import GroundTruthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos", tags=["Video Validation"])

# Initialize ground truth service
ground_truth_service = GroundTruthService()

class VideoValidationRequest(CamelCaseModel):
    """Request schema for manual video validation"""
    notes: Optional[str] = None
    force: bool = False  # Force validation even without ground truth

class VideoValidationResponse(CamelCaseModel):
    """Response schema for video validation"""
    video_id: str
    status: str
    previous_status: str
    validated_at: str
    message: str

class BulkValidationRequest(CamelCaseModel):
    """Request schema for bulk video validation"""
    video_ids: List[str]
    notes: Optional[str] = None
    force: bool = False

class BulkValidationResponse(CamelCaseModel):
    """Response schema for bulk video validation"""
    successful: List[str]
    failed: List[dict]
    total_processed: int
    message: str

@router.post("/{video_id}/validate", response_model=VideoValidationResponse)
async def validate_video(
    video_id: str,
    request: VideoValidationRequest,
    db: Session = Depends(get_db)
):
    """
    Manually validate a video and update its status to 'validated'
    """
    try:
        # Get video
        video = get_video(db, video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {video_id} not found"
            )
        
        # Store previous status
        previous_status = video.status
        
        # Validate transition rules
        if not _can_transition_to_validated(video.status) and not request.force:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot validate video with status '{video.status}'. Use force=true to override."
            )
        
        # Check if ground truth exists (unless forced)
        if not video.ground_truth_generated and not request.force:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video must have ground truth generated before validation. Use force=true to override."
            )
        
        # Update video status
        video.status = "validated"
        video.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"✅ Video {video_id} manually validated: {previous_status} → validated")
        
        return VideoValidationResponse(
            video_id=video_id,
            status="validated",
            previous_status=previous_status,
            validated_at=datetime.utcnow().isoformat(),
            message=f"Video successfully validated from '{previous_status}' status"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to validate video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate video: {str(e)}"
        )

@router.post("/{video_id}/invalidate", response_model=VideoValidationResponse)
async def invalidate_video(
    video_id: str,
    request: VideoValidationRequest,
    db: Session = Depends(get_db)
):
    """
    Invalidate a video and revert its status to 'completed'
    """
    try:
        # Get video
        video = get_video(db, video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {video_id} not found"
            )
        
        # Store previous status
        previous_status = video.status
        
        # Only validated videos can be invalidated
        if video.status != "validated" and not request.force:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only validated videos can be invalidated. Current status: '{video.status}'"
            )
        
        # Update video status
        video.status = "completed"
        video.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"⚠️ Video {video_id} invalidated: {previous_status} → completed")
        
        return VideoValidationResponse(
            video_id=video_id,
            status="completed",
            previous_status=previous_status,
            validated_at=datetime.utcnow().isoformat(),
            message=f"Video invalidated and reverted to 'completed' status"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to invalidate video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invalidate video: {str(e)}"
        )

@router.post("/bulk-validate", response_model=BulkValidationResponse)
async def bulk_validate_videos(
    request: BulkValidationRequest,
    db: Session = Depends(get_db)
):
    """
    Bulk validate multiple videos
    """
    successful = []
    failed = []
    
    try:
        for video_id in request.video_ids:
            try:
                # Get video
                video = get_video(db, video_id)
                if not video:
                    failed.append({
                        "video_id": video_id,
                        "error": "Video not found"
                    })
                    continue
                
                # Check transition rules
                if not _can_transition_to_validated(video.status) and not request.force:
                    failed.append({
                        "video_id": video_id,
                        "error": f"Cannot validate video with status '{video.status}'"
                    })
                    continue
                
                # Check ground truth
                if not video.ground_truth_generated and not request.force:
                    failed.append({
                        "video_id": video_id,
                        "error": "No ground truth generated"
                    })
                    continue
                
                # Update video
                video.status = "validated"
                video.updated_at = datetime.utcnow()
                successful.append(video_id)
                
            except Exception as e:
                failed.append({
                    "video_id": video_id,
                    "error": str(e)
                })
        
        # Commit all successful updates
        db.commit()
        
        logger.info(f"📊 Bulk validation: {len(successful)} successful, {len(failed)} failed")
        
        return BulkValidationResponse(
            successful=successful,
            failed=failed,
            total_processed=len(request.video_ids),
            message=f"Bulk validation completed: {len(successful)} successful, {len(failed)} failed"
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Bulk validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk validation failed: {str(e)}"
        )

@router.get("/validation-status")
async def get_validation_status(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get validation status summary for videos
    """
    try:
        # Build query
        query = db.query(Video)
        
        if project_id:
            query = query.filter(Video.project_id == project_id)
        
        if status:
            query = query.filter(Video.status == status)
        
        videos = query.all()
        
        # Calculate status counts
        status_counts = {}
        for video in videos:
            status_counts[video.status] = status_counts.get(video.status, 0) + 1
        
        # Calculate validation metrics
        total_videos = len(videos)
        validated_videos = status_counts.get('validated', 0)
        completed_videos = status_counts.get('completed', 0)
        processing_videos = status_counts.get('processing', 0)
        error_videos = status_counts.get('error', 0)
        
        validation_rate = (validated_videos / total_videos * 100) if total_videos > 0 else 0
        
        return {
            "total_videos": total_videos,
            "status_counts": status_counts,
            "validation_metrics": {
                "validated_count": validated_videos,
                "completed_count": completed_videos,
                "processing_count": processing_videos,
                "error_count": error_videos,
                "validation_rate_percent": round(validation_rate, 2)
            },
            "ready_for_validation": completed_videos,
            "validation_backlog": completed_videos + processing_videos
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get validation status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get validation status: {str(e)}"
        )

def _can_transition_to_validated(current_status: str) -> bool:
    """
    Check if a video can transition to 'validated' status
    """
    valid_transitions = ['completed', 'uploaded', 'processing']
    return current_status in valid_transitions

def _validate_status_transition(from_status: str, to_status: str) -> bool:
    """
    Validate status transitions according to business rules
    """
    # Define valid status transitions
    valid_transitions = {
        'uploaded': ['processing', 'validated', 'error'],
        'processing': ['completed', 'validated', 'error'],
        'completed': ['validated', 'error'],
        'validated': ['completed'],  # Can be invalidated back to completed
        'error': ['processing', 'uploaded']  # Can retry processing
    }
    
    return to_status in valid_transitions.get(from_status, [])