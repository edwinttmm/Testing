"""
Comprehensive Ground Truth Management System
Root cause fixes for missing ground truth CRUD operations
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, and_, or_, desc, asc
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import uuid
import json
from pydantic import BaseModel, Field, validator

from database import SessionLocal
from models import GroundTruthObject, Video, Project, Annotation
from src.form_validation_middleware import ValidationMiddleware

logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/api/ground-truth", tags=["ground-truth"])

# Pydantic models for ground truth management
class BoundingBoxCreate(BaseModel):
    x: float = Field(..., ge=0)
    y: float = Field(..., ge=0) 
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)

class GroundTruthCreate(BaseModel):
    video_id: str = Field(..., alias="videoId")
    frame_number: Optional[int] = Field(None, ge=0, alias="frameNumber")
    timestamp: float = Field(..., ge=0)
    class_label: str = Field(..., alias="classLabel")
    bounding_box: BoundingBoxCreate = Field(..., alias="boundingBox")
    confidence: Optional[float] = Field(None, ge=0, le=1)
    validated: bool = False
    difficult: bool = False
    
    class Config:
        populate_by_name = True
    
    @validator('class_label')
    def validate_class_label(cls, v):
        allowed_classes = ['pedestrian', 'cyclist', 'motorcyclist', 'wheelchair', 'scooter', 'animal', 'other']
        if v.lower() not in allowed_classes:
            raise ValueError(f"Class label must be one of: {', '.join(allowed_classes)}")
        return v.lower()

class GroundTruthUpdate(BaseModel):
    frame_number: Optional[int] = Field(None, ge=0, alias="frameNumber")
    timestamp: Optional[float] = Field(None, ge=0)
    class_label: Optional[str] = Field(None, alias="classLabel")
    bounding_box: Optional[BoundingBoxCreate] = Field(None, alias="boundingBox")
    confidence: Optional[float] = Field(None, ge=0, le=1)
    validated: Optional[bool] = None
    difficult: Optional[bool] = None
    
    class Config:
        populate_by_name = True

class GroundTruthResponse(BaseModel):
    id: str
    video_id: str = Field(alias="videoId")
    frame_number: Optional[int] = Field(None, alias="frameNumber")
    timestamp: float
    class_label: str = Field(alias="classLabel")
    bounding_box: Dict[str, float] = Field(alias="boundingBox")
    confidence: Optional[float] = None
    validated: bool
    difficult: bool
    created_at: datetime = Field(alias="createdAt")
    
    class Config:
        from_attributes = True
        populate_by_name = True

class GroundTruthBulkCreate(BaseModel):
    video_id: str = Field(..., alias="videoId")
    ground_truth_objects: List[Dict[str, Any]] = Field(..., alias="groundTruthObjects")
    
    class Config:
        populate_by_name = True

class GroundTruthStats(BaseModel):
    total_objects: int = Field(alias="totalObjects")
    validated_objects: int = Field(alias="validatedObjects")
    class_distribution: Dict[str, int] = Field(alias="classDistribution")
    confidence_distribution: Dict[str, int] = Field(alias="confidenceDistribution")
    temporal_distribution: Dict[str, int] = Field(alias="temporalDistribution")
    
    class Config:
        populate_by_name = True

# Root cause fix: Complete ground truth CRUD operations
@router.post("/", response_model=GroundTruthResponse, status_code=status.HTTP_201_CREATED)
async def create_ground_truth_object(
    ground_truth: GroundTruthCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new ground truth object with validation
    Fixes: Missing ground truth management endpoints
    """
    try:
        # Validate video exists
        video = db.query(Video).filter(Video.id == ground_truth.video_id).first()
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video with ID {ground_truth.video_id} not found"
            )
        
        # Create new ground truth object
        db_gt = GroundTruthObject(
            id=str(uuid.uuid4()),
            video_id=ground_truth.video_id,
            frame_number=ground_truth.frame_number,
            timestamp=ground_truth.timestamp,
            class_label=ground_truth.class_label,
            x=ground_truth.bounding_box.x,
            y=ground_truth.bounding_box.y,
            width=ground_truth.bounding_box.width,
            height=ground_truth.bounding_box.height,
            confidence=ground_truth.confidence,
            validated=ground_truth.validated,
            difficult=ground_truth.difficult,
            created_at=datetime.utcnow()
        )
        
        db.add(db_gt)
        db.commit()
        db.refresh(db_gt)
        
        logger.info(f"Created ground truth object {db_gt.id} for video {ground_truth.video_id}")
        
        return GroundTruthResponse(
            id=db_gt.id,
            videoId=db_gt.video_id,
            frameNumber=db_gt.frame_number,
            timestamp=db_gt.timestamp,
            classLabel=db_gt.class_label,
            boundingBox={
                "x": db_gt.x,
                "y": db_gt.y,
                "width": db_gt.width,
                "height": db_gt.height
            },
            confidence=db_gt.confidence,
            validated=db_gt.validated,
            difficult=db_gt.difficult,
            createdAt=db_gt.created_at
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating ground truth object: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create ground truth object due to database error"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating ground truth object: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create ground truth object"
        )

@router.get("/", response_model=List[GroundTruthResponse])
async def get_ground_truth_objects(
    video_id: Optional[str] = Query(None, alias="videoId"),
    class_label: Optional[str] = Query(None, alias="classLabel"),
    validated: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Get ground truth objects with filtering and pagination
    """
    try:
        query = db.query(GroundTruthObject).options(joinedload(GroundTruthObject.video))
        
        # Apply filters
        if video_id:
            query = query.filter(GroundTruthObject.video_id == video_id)
        
        if class_label:
            query = query.filter(GroundTruthObject.class_label == class_label.lower())
        
        if validated is not None:
            query = query.filter(GroundTruthObject.validated == validated)
        
        # Apply pagination
        ground_truth_objects = query.order_by(desc(GroundTruthObject.created_at)).offset(offset).limit(limit).all()
        
        # Convert to response format
        result = []
        for gt in ground_truth_objects:
            result.append(GroundTruthResponse(
                id=gt.id,
                videoId=gt.video_id,
                frameNumber=gt.frame_number,
                timestamp=gt.timestamp,
                classLabel=gt.class_label,
                boundingBox={
                    "x": gt.x,
                    "y": gt.y,
                    "width": gt.width,
                    "height": gt.height
                },
                confidence=gt.confidence,
                validated=gt.validated,
                difficult=gt.difficult,
                createdAt=gt.created_at
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching ground truth objects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch ground truth objects"
        )

@router.get("/{ground_truth_id}", response_model=GroundTruthResponse)
async def get_ground_truth_object(ground_truth_id: str, db: Session = Depends(get_db)):
    """
    Get a specific ground truth object by ID
    """
    try:
        ground_truth_id = ValidationMiddleware.validate_id_parameter(ground_truth_id, "Ground Truth ID")
        
        gt = db.query(GroundTruthObject).filter(GroundTruthObject.id == ground_truth_id).first()
        
        if not gt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ground truth object with ID {ground_truth_id} not found"
            )
        
        return GroundTruthResponse(
            id=gt.id,
            videoId=gt.video_id,
            frameNumber=gt.frame_number,
            timestamp=gt.timestamp,
            classLabel=gt.class_label,
            boundingBox={
                "x": gt.x,
                "y": gt.y,
                "width": gt.width,
                "height": gt.height
            },
            confidence=gt.confidence,
            validated=gt.validated,
            difficult=gt.difficult,
            createdAt=gt.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ground truth object {ground_truth_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch ground truth object"
        )

@router.put("/{ground_truth_id}", response_model=GroundTruthResponse)
async def update_ground_truth_object(
    ground_truth_id: str,
    ground_truth_update: GroundTruthUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing ground truth object
    """
    try:
        ground_truth_id = ValidationMiddleware.validate_id_parameter(ground_truth_id, "Ground Truth ID")
        
        # Find existing ground truth object
        db_gt = db.query(GroundTruthObject).filter(GroundTruthObject.id == ground_truth_id).first()
        if not db_gt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ground truth object with ID {ground_truth_id} not found"
            )
        
        # Update fields if provided
        update_data = ground_truth_update.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field == "bounding_box" and value:
                # Update individual bounding box components
                db_gt.x = value.x
                db_gt.y = value.y
                db_gt.width = value.width
                db_gt.height = value.height
            elif field == "class_label" and value:
                # Validate class label
                allowed_classes = ['pedestrian', 'cyclist', 'motorcyclist', 'wheelchair', 'scooter', 'animal', 'other']
                if value.lower() not in allowed_classes:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Invalid class label: {value}"
                    )
                db_gt.class_label = value.lower()
            else:
                setattr(db_gt, field, value)
        
        db.commit()
        db.refresh(db_gt)
        
        logger.info(f"Updated ground truth object {ground_truth_id}")
        
        return GroundTruthResponse(
            id=db_gt.id,
            videoId=db_gt.video_id,
            frameNumber=db_gt.frame_number,
            timestamp=db_gt.timestamp,
            classLabel=db_gt.class_label,
            boundingBox={
                "x": db_gt.x,
                "y": db_gt.y,
                "width": db_gt.width,
                "height": db_gt.height
            },
            confidence=db_gt.confidence,
            validated=db_gt.validated,
            difficult=db_gt.difficult,
            createdAt=db_gt.created_at
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating ground truth object {ground_truth_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update ground truth object due to database error"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating ground truth object {ground_truth_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update ground truth object"
        )

@router.delete("/{ground_truth_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ground_truth_object(ground_truth_id: str, db: Session = Depends(get_db)):
    """
    Delete a ground truth object
    """
    try:
        ground_truth_id = ValidationMiddleware.validate_id_parameter(ground_truth_id, "Ground Truth ID")
        
        gt = db.query(GroundTruthObject).filter(GroundTruthObject.id == ground_truth_id).first()
        if not gt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ground truth object with ID {ground_truth_id} not found"
            )
        
        db.delete(gt)
        db.commit()
        
        logger.info(f"Deleted ground truth object {ground_truth_id}")
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error deleting ground truth object {ground_truth_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete ground truth object due to database error"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting ground truth object {ground_truth_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete ground truth object"
        )

# Bulk operations
@router.post("/bulk", response_model=List[GroundTruthResponse], status_code=status.HTTP_201_CREATED)
async def create_bulk_ground_truth(
    bulk_request: GroundTruthBulkCreate,
    db: Session = Depends(get_db)
):
    """
    Create multiple ground truth objects in a single transaction
    """
    if not bulk_request.ground_truth_objects:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No ground truth objects provided"
        )
    
    if len(bulk_request.ground_truth_objects) > 1000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot create more than 1000 ground truth objects at once"
        )
    
    try:
        # Validate video exists
        video = db.query(Video).filter(Video.id == bulk_request.video_id).first()
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video with ID {bulk_request.video_id} not found"
            )
        
        created_objects = []
        
        for i, gt_data in enumerate(bulk_request.ground_truth_objects):
            try:
                # Validate each ground truth object
                gt_create = GroundTruthCreate(
                    videoId=bulk_request.video_id,
                    **gt_data
                )
                
                db_gt = GroundTruthObject(
                    id=str(uuid.uuid4()),
                    video_id=bulk_request.video_id,
                    frame_number=gt_create.frame_number,
                    timestamp=gt_create.timestamp,
                    class_label=gt_create.class_label,
                    x=gt_create.bounding_box.x,
                    y=gt_create.bounding_box.y,
                    width=gt_create.bounding_box.width,
                    height=gt_create.bounding_box.height,
                    confidence=gt_create.confidence,
                    validated=gt_create.validated,
                    difficult=gt_create.difficult,
                    created_at=datetime.utcnow()
                )
                
                db.add(db_gt)
                created_objects.append(db_gt)
                
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Validation failed for ground truth object {i+1}: {str(e)}"
                )
        
        db.commit()
        
        # Refresh all created objects
        for gt in created_objects:
            db.refresh(gt)
        
        logger.info(f"Created {len(created_objects)} ground truth objects in bulk for video {bulk_request.video_id}")
        
        # Return response format
        result = []
        for gt in created_objects:
            result.append(GroundTruthResponse(
                id=gt.id,
                videoId=gt.video_id,
                frameNumber=gt.frame_number,
                timestamp=gt.timestamp,
                classLabel=gt.class_label,
                boundingBox={
                    "x": gt.x,
                    "y": gt.y,
                    "width": gt.width,
                    "height": gt.height
                },
                confidence=gt.confidence,
                validated=gt.validated,
                difficult=gt.difficult,
                createdAt=gt.created_at
            ))
        
        return result
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating bulk ground truth objects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create bulk ground truth objects due to database error"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating bulk ground truth objects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create bulk ground truth objects"
        )

# Statistics and analysis endpoints
@router.get("/stats/video/{video_id}", response_model=GroundTruthStats)
async def get_ground_truth_stats(video_id: str, db: Session = Depends(get_db)):
    """
    Get ground truth statistics for a specific video
    """
    try:
        video_id = ValidationMiddleware.validate_id_parameter(video_id, "Video ID")
        
        # Validate video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video with ID {video_id} not found"
            )
        
        # Get all ground truth objects for this video
        ground_truth_objects = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == video_id
        ).all()
        
        total_objects = len(ground_truth_objects)
        validated_objects = sum(1 for gt in ground_truth_objects if gt.validated)
        
        # Class distribution
        class_distribution = {}
        confidence_distribution = {}
        temporal_distribution = {}
        
        for gt in ground_truth_objects:
            # Class distribution
            class_distribution[gt.class_label] = class_distribution.get(gt.class_label, 0) + 1
            
            # Confidence distribution
            if gt.confidence is not None:
                confidence_range = f"{int(gt.confidence * 10) * 10}-{int(gt.confidence * 10) * 10 + 10}%"
                confidence_distribution[confidence_range] = confidence_distribution.get(confidence_range, 0) + 1
            
            # Temporal distribution (10-second buckets)
            time_bucket = int(gt.timestamp // 10) * 10
            temporal_key = f"{time_bucket}-{time_bucket+10}s"
            temporal_distribution[temporal_key] = temporal_distribution.get(temporal_key, 0) + 1
        
        return GroundTruthStats(
            totalObjects=total_objects,
            validatedObjects=validated_objects,
            classDistribution=class_distribution,
            confidenceDistribution=confidence_distribution,
            temporalDistribution=temporal_distribution
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ground truth stats for video {video_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get ground truth statistics"
        )

# Export functionality
@router.get("/export/video/{video_id}")
async def export_ground_truth(
    video_id: str,
    format: str = Query("json", pattern="^(json|coco|yolo|pascal_voc)$"),
    validated_only: bool = Query(False, alias="validatedOnly"),
    db: Session = Depends(get_db)
):
    """
    Export ground truth data in various formats
    """
    try:
        video_id = ValidationMiddleware.validate_id_parameter(video_id, "Video ID")
        
        # Validate video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video with ID {video_id} not found"
            )
        
        # Get ground truth objects
        query = db.query(GroundTruthObject).filter(GroundTruthObject.video_id == video_id)
        
        if validated_only:
            query = query.filter(GroundTruthObject.validated == True)
        
        ground_truth_objects = query.all()
        
        if format == "json":
            result = []
            for gt in ground_truth_objects:
                result.append({
                    "id": gt.id,
                    "video_id": gt.video_id,
                    "frame_number": gt.frame_number,
                    "timestamp": gt.timestamp,
                    "class_label": gt.class_label,
                    "bounding_box": {
                        "x": gt.x,
                        "y": gt.y,
                        "width": gt.width,
                        "height": gt.height
                    },
                    "confidence": gt.confidence,
                    "validated": gt.validated,
                    "difficult": gt.difficult,
                    "created_at": gt.created_at.isoformat() if gt.created_at else None
                })
            
            return {
                "format": "json",
                "video_id": video_id,
                "count": len(result),
                "validated_only": validated_only,
                "data": result
            }
        
        # Add support for other formats as needed
        return {
            "format": format,
            "video_id": video_id,
            "count": len(ground_truth_objects),
            "message": f"Export format '{format}' not yet implemented"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting ground truth for video {video_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export ground truth data"
        )