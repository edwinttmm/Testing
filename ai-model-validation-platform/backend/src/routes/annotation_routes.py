"""
Annotation API Routes
SPARC Implementation - RESTful API endpoints for annotation management
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
import logging

# Import dependencies
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from database import get_db
from src.services.annotation_service import AnnotationService, AnnotationSessionService
from src.utils.annotation_validators import VRUType

logger = logging.getLogger(__name__)

# Initialize services
annotation_service = AnnotationService()
session_service = AnnotationSessionService()

# Create router
router = APIRouter(prefix="/api/annotations", tags=["annotations"])


# Pydantic Models for Request/Response
class BoundingBoxModel(BaseModel):
    """Bounding box model for validation"""
    x: float = Field(..., ge=0, description="X coordinate (must be non-negative)")
    y: float = Field(..., ge=0, description="Y coordinate (must be non-negative)")
    width: float = Field(..., gt=0, description="Width (must be positive)")
    height: float = Field(..., gt=0, description="Height (must be positive)")


class CreateAnnotationRequest(BaseModel):
    """Request model for creating annotations"""
    video_id: str = Field(..., description="Video ID")
    detection_id: Optional[str] = Field(None, description="Detection ID (auto-generated if not provided)")
    frame_number: int = Field(..., ge=0, description="Frame number")
    timestamp: float = Field(..., ge=0, description="Timestamp in seconds")
    end_timestamp: Optional[float] = Field(None, ge=0, description="End timestamp for temporal annotations")
    vru_type: str = Field(..., description="VRU type (pedestrian, cyclist, etc.)")
    bounding_box: BoundingBoxModel = Field(..., description="Bounding box coordinates")
    occluded: bool = Field(False, description="Whether the VRU is occluded")
    truncated: bool = Field(False, description="Whether the VRU is truncated")
    difficult: bool = Field(False, description="Whether this is a difficult case")
    notes: Optional[str] = Field(None, description="Additional notes")
    annotator: Optional[str] = Field(None, description="Annotator identifier")
    validated: bool = Field(False, description="Whether annotation is validated")
    
    @validator('vru_type')
    def validate_vru_type(cls, v):
        valid_types = {vru.value for vru in VRUType}
        if v not in valid_types:
            raise ValueError(f'Invalid VRU type. Valid types: {list(valid_types)}')
        return v
    
    @validator('end_timestamp')
    def validate_end_timestamp(cls, v, values):
        if v is not None and 'timestamp' in values and v <= values['timestamp']:
            raise ValueError('End timestamp must be greater than start timestamp')
        return v


class UpdateAnnotationRequest(BaseModel):
    """Request model for updating annotations"""
    detection_id: Optional[str] = Field(None, description="Detection ID")
    frame_number: Optional[int] = Field(None, ge=0, description="Frame number")
    timestamp: Optional[float] = Field(None, ge=0, description="Timestamp in seconds")
    end_timestamp: Optional[float] = Field(None, ge=0, description="End timestamp")
    vru_type: Optional[str] = Field(None, description="VRU type")
    bounding_box: Optional[BoundingBoxModel] = Field(None, description="Bounding box coordinates")
    occluded: Optional[bool] = Field(None, description="Whether the VRU is occluded")
    truncated: Optional[bool] = Field(None, description="Whether the VRU is truncated")
    difficult: Optional[bool] = Field(None, description="Whether this is a difficult case")
    notes: Optional[str] = Field(None, description="Additional notes")
    annotator: Optional[str] = Field(None, description="Annotator identifier")
    validated: Optional[bool] = Field(None, description="Whether annotation is validated")
    
    @validator('vru_type')
    def validate_vru_type(cls, v):
        if v is not None:
            valid_types = {vru.value for vru in VRUType}
            if v not in valid_types:
                raise ValueError(f'Invalid VRU type. Valid types: {list(valid_types)}')
        return v


class BulkUpdateRequest(BaseModel):
    """Request model for bulk updates"""
    annotation_ids: List[str] = Field(..., description="List of annotation IDs to update")
    update_data: Dict[str, Any] = Field(..., description="Fields to update")


class AnnotationFilters(BaseModel):
    """Filters for annotation queries"""
    vru_type: Optional[str] = Field(None, description="Filter by VRU type")
    validated: Optional[bool] = Field(None, description="Filter by validation status")
    annotator: Optional[str] = Field(None, description="Filter by annotator")
    frame_start: Optional[int] = Field(None, ge=0, description="Start frame for range filter")
    frame_end: Optional[int] = Field(None, ge=0, description="End frame for range filter")
    timestamp_start: Optional[float] = Field(None, ge=0, description="Start timestamp for range filter")
    timestamp_end: Optional[float] = Field(None, ge=0, description="End timestamp for range filter")
    difficult_only: Optional[bool] = Field(False, description="Show only difficult annotations")
    exclude_validated: Optional[bool] = Field(False, description="Exclude validated annotations")


class CreateAnnotationSessionRequest(BaseModel):
    """Request model for creating annotation sessions"""
    video_id: str = Field(..., description="Video ID")
    project_id: str = Field(..., description="Project ID")
    annotator_id: Optional[str] = Field(None, description="Annotator ID")
    total_frames: Optional[int] = Field(None, ge=0, description="Total frames in video")


class UpdateSessionProgressRequest(BaseModel):
    """Request model for updating session progress"""
    current_frame: Optional[int] = Field(None, ge=0, description="Current frame position")
    total_detections: Optional[int] = Field(None, ge=0, description="Total detections made")
    validated_detections: Optional[int] = Field(None, ge=0, description="Validated detections")
    status: Optional[str] = Field(None, description="Session status")


# API Endpoints
@router.post("/", response_model=Dict[str, Any])
async def create_annotation(
    annotation_data: CreateAnnotationRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new annotation
    
    - **video_id**: ID of the video being annotated
    - **frame_number**: Frame number in the video
    - **timestamp**: Timestamp in seconds
    - **vru_type**: Type of VRU (pedestrian, cyclist, etc.)
    - **bounding_box**: Bounding box coordinates
    """
    try:
        # Convert Pydantic model to dict
        annotation_dict = annotation_data.dict()
        
        # Convert bounding box model to dict
        annotation_dict["bounding_box"] = annotation_dict["bounding_box"]
        
        result = annotation_service.create_annotation(db, annotation_dict)
        
        if not result["success"]:
            if result.get("code") == "VALIDATION_FAILED":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": result["error"],
                        "validation_errors": result.get("validation_errors", []),
                        "validation_warnings": result.get("validation_warnings", [])
                    }
                )
            elif result.get("code") == "VIDEO_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Video not found")
            else:
                raise HTTPException(status_code=500, detail=result["error"])
        
        return JSONResponse(
            status_code=201,
            content={
                "message": "Annotation created successfully",
                "data": result["annotation"],
                "validation_warnings": result.get("validation_warnings", []),
                "validation_metadata": result.get("validation_metadata", {})
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating annotation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{annotation_id}", response_model=Dict[str, Any])
async def get_annotation(
    annotation_id: str = Path(..., description="Annotation ID"),
    db: Session = Depends(get_db)
):
    """Get annotation by ID"""
    try:
        annotation = annotation_service.get_annotation(db, annotation_id)
        
        if not annotation:
            raise HTTPException(status_code=404, detail="Annotation not found")
        
        return {
            "message": "Annotation retrieved successfully",
            "data": annotation
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting annotation {annotation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{annotation_id}", response_model=Dict[str, Any])
async def update_annotation(
    annotation_id: str = Path(..., description="Annotation ID"),
    update_data: UpdateAnnotationRequest = Body(...),
    db: Session = Depends(get_db)
):
    """Update an existing annotation"""
    try:
        # Convert to dict, excluding None values
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        
        result = annotation_service.update_annotation(db, annotation_id, update_dict)
        
        if not result["success"]:
            if result.get("code") == "ANNOTATION_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Annotation not found")
            elif result.get("code") == "VALIDATION_FAILED":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": result["error"],
                        "validation_errors": result.get("validation_errors", []),
                        "validation_warnings": result.get("validation_warnings", [])
                    }
                )
            else:
                raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "message": "Annotation updated successfully",
            "data": result["annotation"],
            "validation_warnings": result.get("validation_warnings", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating annotation {annotation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{annotation_id}", response_model=Dict[str, Any])
async def delete_annotation(
    annotation_id: str = Path(..., description="Annotation ID"),
    db: Session = Depends(get_db)
):
    """Delete an annotation"""
    try:
        result = annotation_service.delete_annotation(db, annotation_id)
        
        if not result["success"]:
            if result.get("code") == "ANNOTATION_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Annotation not found")
            else:
                raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "message": result["message"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting annotation {annotation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/video/{video_id}", response_model=Dict[str, Any])
async def get_video_annotations(
    video_id: str = Path(..., description="Video ID"),
    vru_type: Optional[str] = Query(None, description="Filter by VRU type"),
    validated: Optional[bool] = Query(None, description="Filter by validation status"),
    annotator: Optional[str] = Query(None, description="Filter by annotator"),
    frame_start: Optional[int] = Query(None, ge=0, description="Start frame"),
    frame_end: Optional[int] = Query(None, ge=0, description="End frame"),
    timestamp_start: Optional[float] = Query(None, ge=0, description="Start timestamp"),
    timestamp_end: Optional[float] = Query(None, ge=0, description="End timestamp"),
    difficult_only: bool = Query(False, description="Show only difficult annotations"),
    exclude_validated: bool = Query(False, description="Exclude validated annotations"),
    db: Session = Depends(get_db)
):
    """Get all annotations for a video with optional filtering"""
    try:
        # Build filters
        filters = {}
        if vru_type:
            filters["vru_type"] = vru_type
        if validated is not None:
            filters["validated"] = validated
        if annotator:
            filters["annotator"] = annotator
        if frame_start is not None and frame_end is not None:
            filters["frame_range"] = (frame_start, frame_end)
        if timestamp_start is not None and timestamp_end is not None:
            filters["timestamp_range"] = (timestamp_start, timestamp_end)
        if difficult_only:
            filters["difficult_only"] = True
        if exclude_validated:
            filters["exclude_validated"] = True
        
        result = annotation_service.get_video_annotations(db, video_id, filters)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "message": "Video annotations retrieved successfully",
            "data": result["annotations"],
            "count": result["count"],
            "filters_applied": result["filters_applied"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video annotations {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/video/{video_id}/statistics", response_model=Dict[str, Any])
async def get_annotation_statistics(
    video_id: str = Path(..., description="Video ID"),
    db: Session = Depends(get_db)
):
    """Get comprehensive annotation statistics for a video"""
    try:
        result = annotation_service.get_annotation_statistics(db, video_id)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "message": "Annotation statistics retrieved successfully",
            "data": result["statistics"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting annotation statistics {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/video/{video_id}/validate", response_model=Dict[str, Any])
async def validate_annotation_sequence(
    video_id: str = Path(..., description="Video ID"),
    db: Session = Depends(get_db)
):
    """Validate temporal and geometric consistency of annotation sequence"""
    try:
        result = annotation_service.validate_annotation_sequence(db, video_id)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "message": "Annotation sequence validation completed",
            "data": result["validation"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating annotation sequence {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/bulk-update", response_model=Dict[str, Any])
async def bulk_update_annotations(
    bulk_request: BulkUpdateRequest,
    db: Session = Depends(get_db)
):
    """Bulk update multiple annotations"""
    try:
        result = annotation_service.bulk_update_annotations(
            db, 
            bulk_request.annotation_ids,
            bulk_request.update_data
        )
        
        if not result["success"]:
            if result.get("code") == "ANNOTATIONS_NOT_FOUND":
                raise HTTPException(status_code=404, detail="No annotations found")
            else:
                raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "message": f"Bulk update completed: {result['updated_count']}/{result['total_requested']} annotations updated",
            "data": {
                "updated_count": result["updated_count"],
                "total_requested": result["total_requested"],
                "errors": result["errors"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk updating annotations: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Annotation Session Endpoints
@router.post("/sessions", response_model=Dict[str, Any])
async def create_annotation_session(
    session_data: CreateAnnotationSessionRequest,
    db: Session = Depends(get_db)
):
    """Create a new annotation session"""
    try:
        session_dict = session_data.dict()
        result = session_service.create_session(db, session_dict)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return JSONResponse(
            status_code=201,
            content={
                "message": "Annotation session created successfully",
                "data": result["session"]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating annotation session: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/sessions/{session_id}/progress", response_model=Dict[str, Any])
async def update_session_progress(
    session_id: str = Path(..., description="Session ID"),
    progress_data: UpdateSessionProgressRequest = Body(...),
    db: Session = Depends(get_db)
):
    """Update annotation session progress"""
    try:
        # Convert to dict, excluding None values
        progress_dict = {k: v for k, v in progress_data.dict().items() if v is not None}
        
        result = session_service.update_session_progress(db, session_id, progress_dict)
        
        if not result["success"]:
            if result.get("code") == "SESSION_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Session not found")
            else:
                raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "message": "Session progress updated successfully",
            "data": result["session"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating session progress {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Health check endpoint
@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Health check endpoint for annotation system"""
    return {
        "status": "healthy",
        "service": "annotation_api",
        "version": "1.0.0",
        "timestamp": "2025-08-27T15:30:00Z"
    }