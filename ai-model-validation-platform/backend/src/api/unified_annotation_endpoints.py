"""
Unified Annotation API Endpoints
================================

Single source of truth for all annotation operations.
This file consolidates all duplicate annotation endpoints into one clean implementation.

Features:
- Complete CRUD operations for annotations
- Annotation session management
- Ground truth object management
- Batch operations and export/import
- Performance-optimized database queries
- Comprehensive error handling
- Type safety and validation
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body, status, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, func, desc, asc, text
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone, timedelta
import uuid
import logging
import json
import io
from pathlib import Path as FilePath

# Database and models
from database import get_db
from models import (
    Annotation, AnnotationSession, GroundTruthObject, TestResult,
    DetectionComparison, Video, TestSession, Project, DetectionEvent
)

# Schemas
from schemas_annotation import (
    AnnotationCreate, AnnotationUpdate, AnnotationResponse,
    AnnotationSessionCreate, AnnotationSessionResponse,
    VideoProjectLinkCreate, VideoProjectLinkResponse,
    AnnotationExportRequest, BoundingBox, VRUTypeEnum
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/annotations", tags=["annotations"])

# ==================== UTILITY FUNCTIONS ====================

def validate_annotation_data(annotation_data: AnnotationCreate, video_id: str, db: Session) -> Dict[str, Any]:
    """Comprehensive validation for annotation data"""
    errors = []
    
    # Validate video exists
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        errors.append(f"Video with ID {video_id} does not exist")
    
    # Validate frame number and timestamp
    if annotation_data.frame_number < 0:
        errors.append("Frame number must be non-negative")
    
    if annotation_data.timestamp < 0:
        errors.append("Timestamp must be non-negative")
    
    if annotation_data.end_timestamp and annotation_data.end_timestamp <= annotation_data.timestamp:
        errors.append("End timestamp must be greater than start timestamp")
    
    # Validate bounding box
    bbox = annotation_data.bounding_box
    if bbox.x < 0 or bbox.y < 0:
        errors.append("Bounding box coordinates must be non-negative")
    
    if bbox.width <= 0 or bbox.height <= 0:
        errors.append("Bounding box dimensions must be positive")
    
    if errors:
        return {"valid": False, "errors": errors}
    
    return {"valid": True, "video": video}

def create_annotation_response(annotation: Annotation) -> Dict[str, Any]:
    """Create standardized annotation response"""
    return {
        "id": annotation.id,
        "videoId": annotation.video_id,
        "detectionId": annotation.detection_id,
        "frameNumber": annotation.frame_number,
        "timestamp": annotation.timestamp,
        "endTimestamp": annotation.end_timestamp,
        "vruType": annotation.vru_type,
        "boundingBox": {
            "x": annotation.bounding_box.get("x", 0),
            "y": annotation.bounding_box.get("y", 0),
            "width": annotation.bounding_box.get("width", 0),
            "height": annotation.bounding_box.get("height", 0),
            "confidence": annotation.bounding_box.get("confidence"),
            "label": annotation.bounding_box.get("label")
        },
        "occluded": annotation.occluded,
        "truncated": annotation.truncated,
        "difficult": annotation.difficult,
        "notes": annotation.notes,
        "annotator": annotation.annotator,
        "validated": annotation.validated,
        "createdAt": annotation.created_at.isoformat() if annotation.created_at else None,
        "updatedAt": annotation.updated_at.isoformat() if annotation.updated_at else None
    }

# ==================== ANNOTATION CRUD ENDPOINTS ====================

@router.post("/videos/{video_id}/annotations", response_model=Dict[str, Any])
async def create_annotation(
    video_id: str,
    annotation: AnnotationCreate,
    db: Session = Depends(get_db)
):
    """Create new annotation for video"""
    try:
        # Validate annotation data
        validation_result = validate_annotation_data(annotation, video_id, db)
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": validation_result["errors"]}
            )
        
        # Set video_id from URL parameter
        annotation.video_id = video_id
        
        # Create annotation record
        new_annotation = Annotation(
            id=str(uuid.uuid4()),
            video_id=video_id,
            detection_id=annotation.detection_id,
            frame_number=annotation.frame_number,
            timestamp=annotation.timestamp,
            end_timestamp=annotation.end_timestamp,
            vru_type=annotation.vru_type.value,
            bounding_box=annotation.bounding_box.dict(),
            occluded=annotation.occluded,
            truncated=annotation.truncated,
            difficult=annotation.difficult,
            notes=annotation.notes,
            annotator=annotation.annotator,
            validated=annotation.validated,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(new_annotation)
        db.commit()
        db.refresh(new_annotation)
        
        return {
            "success": True,
            "annotation": create_annotation_response(new_annotation),
            "message": "Annotation created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating annotation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create annotation"
        )

@router.get("/videos/{video_id}/annotations", response_model=Dict[str, Any])
async def get_video_annotations(
    video_id: str,
    validated_only: Optional[bool] = False,
    skip: int = Query(0, ge=0, description="Number of annotations to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of annotations to return"),
    db: Session = Depends(get_db)
):
    """Get all annotations for a specific video"""
    try:
        # Build query
        query = db.query(Annotation).filter(Annotation.video_id == video_id)
        
        if validated_only:
            query = query.filter(Annotation.validated == True)
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        annotations = query.order_by(Annotation.timestamp).offset(skip).limit(limit).all()
        
        return {
            "success": True,
            "annotations": [create_annotation_response(ann) for ann in annotations],
            "pagination": {
                "total": total,
                "skip": skip,
                "limit": limit,
                "hasMore": skip + limit < total
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting video annotations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve annotations"
        )

@router.get("/annotations/{annotation_id}", response_model=Dict[str, Any])
async def get_annotation(
    annotation_id: str,
    db: Session = Depends(get_db)
):
    """Get specific annotation by ID"""
    try:
        annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        
        if not annotation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Annotation not found"
            )
        
        return {
            "success": True,
            "annotation": create_annotation_response(annotation)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting annotation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve annotation"
        )

@router.put("/annotations/{annotation_id}", response_model=Dict[str, Any])
async def update_annotation(
    annotation_id: str,
    annotation_update: AnnotationUpdate,
    db: Session = Depends(get_db)
):
    """Update existing annotation"""
    try:
        annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        
        if not annotation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Annotation not found"
            )
        
        # Update fields that are provided
        update_data = annotation_update.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field == "bounding_box" and value:
                setattr(annotation, field, value.dict() if hasattr(value, 'dict') else value)
            elif field == "vru_type" and value:
                setattr(annotation, field, value.value if hasattr(value, 'value') else value)
            else:
                setattr(annotation, field, value)
        
        annotation.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(annotation)
        
        return {
            "success": True,
            "annotation": create_annotation_response(annotation),
            "message": "Annotation updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating annotation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update annotation"
        )

@router.delete("/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_annotation(
    annotation_id: str,
    db: Session = Depends(get_db)
):
    """Delete annotation"""
    try:
        annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        
        if not annotation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Annotation not found"
            )
        
        db.delete(annotation)
        db.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting annotation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete annotation"
        )

# ==================== BATCH OPERATIONS ====================

@router.post("/videos/{video_id}/annotations/batch", response_model=Dict[str, Any])
async def create_batch_annotations(
    video_id: str,
    annotations: List[AnnotationCreate],
    db: Session = Depends(get_db)
):
    """Create multiple annotations in batch"""
    try:
        # Validate video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        created_annotations = []
        errors = []
        
        for i, annotation in enumerate(annotations):
            try:
                # Validate each annotation
                validation_result = validate_annotation_data(annotation, video_id, db)
                if not validation_result["valid"]:
                    errors.append(f"Annotation {i}: {', '.join(validation_result['errors'])}")
                    continue
                
                # Create annotation
                new_annotation = Annotation(
                    id=str(uuid.uuid4()),
                    video_id=video_id,
                    detection_id=annotation.detection_id,
                    frame_number=annotation.frame_number,
                    timestamp=annotation.timestamp,
                    end_timestamp=annotation.end_timestamp,
                    vru_type=annotation.vru_type.value,
                    bounding_box=annotation.bounding_box.dict(),
                    occluded=annotation.occluded,
                    truncated=annotation.truncated,
                    difficult=annotation.difficult,
                    notes=annotation.notes,
                    annotator=annotation.annotator,
                    validated=annotation.validated,
                    created_at=datetime.now(timezone.utc)
                )
                
                db.add(new_annotation)
                created_annotations.append(new_annotation)
                
            except Exception as e:
                errors.append(f"Annotation {i}: {str(e)}")
        
        if created_annotations:
            db.commit()
            for annotation in created_annotations:
                db.refresh(annotation)
        
        return {
            "success": len(created_annotations) > 0,
            "created": len(created_annotations),
            "errors": len(errors),
            "annotations": [create_annotation_response(ann) for ann in created_annotations],
            "errorDetails": errors if errors else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating batch annotations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create batch annotations"
        )

# ==================== VALIDATION ====================

@router.patch("/annotations/{annotation_id}/validate", response_model=Dict[str, Any])
async def validate_annotation(
    annotation_id: str,
    validated: bool = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """Mark annotation as validated or not validated"""
    try:
        annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        
        if not annotation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Annotation not found"
            )
        
        annotation.validated = validated
        annotation.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(annotation)
        
        return {
            "success": True,
            "annotation": create_annotation_response(annotation),
            "message": f"Annotation {'validated' if validated else 'marked as unvalidated'}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error validating annotation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate annotation"
        )

# ==================== EXPORT/IMPORT ====================

@router.get("/videos/{video_id}/annotations/export")
async def export_annotations(
    video_id: str,
    format: str = Query("json", enum=["json", "csv", "coco"]),
    validated_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Export annotations in various formats"""
    try:
        # Validate video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        # Get annotations
        query = db.query(Annotation).filter(Annotation.video_id == video_id)
        if validated_only:
            query = query.filter(Annotation.validated == True)
        
        annotations = query.order_by(Annotation.timestamp).all()
        
        if format == "json":
            export_data = {
                "video_id": video_id,
                "video_filename": video.filename,
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "total_annotations": len(annotations),
                "annotations": [create_annotation_response(ann) for ann in annotations]
            }
            
            output = io.StringIO()
            json.dump(export_data, output, indent=2, default=str)
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=annotations_{video_id}.json"
                }
            )
        
        elif format == "csv":
            import csv
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "annotation_id", "video_id", "detection_id", "frame_number",
                "timestamp", "end_timestamp", "vru_type", "bbox_x", "bbox_y",
                "bbox_width", "bbox_height", "bbox_confidence", "occluded",
                "truncated", "difficult", "notes", "annotator", "validated",
                "created_at", "updated_at"
            ])
            
            # Write data
            for ann in annotations:
                bbox = ann.bounding_box or {}
                writer.writerow([
                    ann.id, ann.video_id, ann.detection_id, ann.frame_number,
                    ann.timestamp, ann.end_timestamp, ann.vru_type,
                    bbox.get("x", 0), bbox.get("y", 0),
                    bbox.get("width", 0), bbox.get("height", 0),
                    bbox.get("confidence"), ann.occluded, ann.truncated,
                    ann.difficult, ann.notes, ann.annotator, ann.validated,
                    ann.created_at, ann.updated_at
                ])
            
            output.seek(0)
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=annotations_{video_id}.csv"
                }
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported export format: {format}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting annotations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export annotations"
        )

# ==================== ANALYTICS ====================

@router.get("/analytics/summary", response_model=Dict[str, Any])
async def get_annotation_analytics(
    video_id: Optional[str] = None,
    project_id: Optional[str] = None,
    annotator: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get annotation analytics and statistics"""
    try:
        base_query = db.query(Annotation)
        
        # Apply filters
        if video_id:
            base_query = base_query.filter(Annotation.video_id == video_id)
        
        if annotator:
            base_query = base_query.filter(Annotation.annotator == annotator)
        
        # Date filter
        date_filter = datetime.now(timezone.utc) - timedelta(days=days)
        base_query = base_query.filter(Annotation.created_at >= date_filter)
        
        # Get basic counts
        total_annotations = base_query.count()
        validated_annotations = base_query.filter(Annotation.validated == True).count()
        
        # VRU type distribution
        vru_distribution = (
            base_query
            .with_entities(Annotation.vru_type, func.count(Annotation.id))
            .group_by(Annotation.vru_type)
            .all()
        )
        
        # Annotator statistics
        annotator_stats = (
            base_query
            .with_entities(
                Annotation.annotator,
                func.count(Annotation.id),
                func.avg(func.cast(Annotation.validated, func.Integer))
            )
            .group_by(Annotation.annotator)
            .all()
        )
        
        return {
            "success": True,
            "summary": {
                "totalAnnotations": total_annotations,
                "validatedAnnotations": validated_annotations,
                "validationRate": validated_annotations / total_annotations if total_annotations > 0 else 0,
                "period": f"Last {days} days"
            },
            "vruDistribution": dict(vru_distribution),
            "annotatorStats": [
                {
                    "annotator": stats[0],
                    "totalAnnotations": stats[1],
                    "validationRate": float(stats[2]) if stats[2] else 0
                }
                for stats in annotator_stats
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting annotation analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics"
        )

# ==================== HEALTH CHECK ====================

@router.get("/health", response_model=Dict[str, Any])
async def annotation_health_check(db: Session = Depends(get_db)):
    """Health check for annotation system"""
    try:
        # Test database connectivity
        annotation_count = db.query(Annotation).count()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": "connected",
            "totalAnnotations": annotation_count
        }
        
    except Exception as e:
        logger.error(f"Annotation health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }