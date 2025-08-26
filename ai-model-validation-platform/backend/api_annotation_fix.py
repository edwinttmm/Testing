#!/usr/bin/env python3
"""
COMPREHENSIVE FIX FOR ANNOTATION API ISSUES

This fixes:
1. POST /api/videos/{id}/annotations 500 errors
2. Missing videoId field validation 
3. Schema validation conflicts
4. Database enum validation errors
5. Proper error handling and logging
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any
import uuid
import json
import logging
from datetime import datetime

from database import get_db
from models import Video, Annotation, AnnotationSession
from schemas_annotation import (
    AnnotationCreate, AnnotationUpdate, AnnotationResponse,
    VRUTypeEnum, BoundingBox
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos", tags=["Video Annotations - Fixed"])

# ============================================================================
# FIXED ANNOTATION ENDPOINTS
# ============================================================================

@router.post("/{video_id}/annotations", response_model=AnnotationResponse)
async def create_annotation_fixed(
    video_id: str,
    annotation: AnnotationCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Create a new annotation for a video - FIXED VERSION
    
    Fixes:
    - 500 Internal Server Error responses  
    - Missing videoId field validation errors
    - Proper Pydantic schema validation
    - Database constraint violations
    - Enum validation errors
    """
    try:
        logger.info(f"🔧 FIXED ENDPOINT: Creating annotation for video {video_id}")
        logger.debug(f"Request body: {await request.body()}")
        
        # 1. VALIDATE VIDEO EXISTS
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(
                status_code=404, 
                detail=f"Video with ID '{video_id}' not found"
            )
        
        # 2. VALIDATE ANNOTATION DATA
        # Set video_id from URL parameter (fixes missing videoId error)
        annotation.video_id = video_id
        
        # Validate required fields
        if not annotation.frame_number and annotation.frame_number != 0:
            raise HTTPException(
                status_code=400,
                detail="frameNumber is required"
            )
        
        if not annotation.timestamp and annotation.timestamp != 0:
            raise HTTPException(
                status_code=400,
                detail="timestamp is required"
            )
        
        if not annotation.vru_type:
            raise HTTPException(
                status_code=400,
                detail="vruType is required"
            )
        
        if not annotation.bounding_box:
            raise HTTPException(
                status_code=400,
                detail="boundingBox is required"
            )
        
        # 3. VALIDATE VRU TYPE ENUM
        valid_vru_types = [e.value for e in VRUTypeEnum]
        vru_type_value = annotation.vru_type.value if hasattr(annotation.vru_type, 'value') else annotation.vru_type
        
        if vru_type_value not in valid_vru_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid vruType '{vru_type_value}'. Valid values: {valid_vru_types}"
            )
        
        # 4. VALIDATE BOUNDING BOX
        bbox = annotation.bounding_box
        if isinstance(bbox, dict):
            # Convert dict to BoundingBox model for validation
            try:
                bbox = BoundingBox(**bbox)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid bounding box format: {str(e)}"
                )
        
        # Validate bounding box values
        if bbox.x < 0 or bbox.y < 0:
            raise HTTPException(
                status_code=400,
                detail="Bounding box coordinates must be non-negative"
            )
        
        if bbox.width <= 0 or bbox.height <= 0:
            raise HTTPException(
                status_code=400,
                detail="Bounding box width and height must be positive"
            )
        
        # 5. GENERATE DETECTION ID IF NOT PROVIDED
        detection_id = annotation.detection_id
        if not detection_id:
            # Generate unique detection ID
            vru_prefix_map = {
                "pedestrian": "PED",
                "cyclist": "CYC", 
                "motorcyclist": "MOT",
                "wheelchair": "WHE",
                "scooter": "SCO",
                "animal": "ANI",
                "other": "OTH"
            }
            prefix = vru_prefix_map.get(vru_type_value, "DET")
            detection_id = f"DET_{prefix}_{annotation.frame_number:06d}_{uuid.uuid4().hex[:8].upper()}"
        
        # 6. CONVERT BOUNDING BOX TO DICT FOR DATABASE STORAGE
        if hasattr(bbox, 'dict'):
            bbox_dict = bbox.dict()
        elif isinstance(bbox, dict):
            bbox_dict = bbox
        else:
            bbox_dict = {
                "x": float(bbox.x),
                "y": float(bbox.y),
                "width": float(bbox.width),
                "height": float(bbox.height),
                "confidence": float(bbox.confidence) if hasattr(bbox, 'confidence') and bbox.confidence is not None else None,
                "label": bbox.label if hasattr(bbox, 'label') else None
            }
        
        # 7. CREATE ANNOTATION RECORD
        db_annotation = Annotation(
            id=str(uuid.uuid4()),
            video_id=video_id,
            detection_id=detection_id,
            frame_number=annotation.frame_number,
            timestamp=annotation.timestamp,
            end_timestamp=annotation.end_timestamp,
            vru_type=vru_type_value,
            bounding_box=bbox_dict,  # Now guaranteed to be a dict
            occluded=annotation.occluded or False,
            truncated=annotation.truncated or False,
            difficult=annotation.difficult or False,
            notes=annotation.notes,
            annotator=annotation.annotator,
            validated=annotation.validated or False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # 8. SAVE TO DATABASE WITH TRANSACTION
        try:
            db.add(db_annotation)
            db.commit()
            db.refresh(db_annotation)
            
            logger.info(f"✅ Successfully created annotation {db_annotation.id} for video {video_id}")
            
            return db_annotation
            
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Database integrity error: {str(e)}")
            raise HTTPException(
                status_code=409,
                detail="Annotation with this detection ID already exists for this video"
            )
        
        except Exception as e:
            db.rollback()
            logger.error(f"Database error creating annotation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Database error: {str(e)}"
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions (already have proper status codes)
        raise
        
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error creating annotation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/{video_id}/annotations", response_model=List[AnnotationResponse])
async def get_video_annotations_fixed(
    video_id: str,
    validated_only: bool = Query(False, description="Return only validated annotations"),
    vru_type: Optional[str] = Query(None, description="Filter by VRU type"),
    skip: int = Query(0, ge=0, description="Number of annotations to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of annotations to return"),
    db: Session = Depends(get_db)
):
    """Get annotations for a video with filtering - FIXED VERSION"""
    try:
        # Validate video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(
                status_code=404, 
                detail=f"Video with ID '{video_id}' not found"
            )
        
        # Build query with filters
        query = db.query(Annotation).filter(Annotation.video_id == video_id)
        
        if validated_only:
            query = query.filter(Annotation.validated == True)
        
        if vru_type:
            # Validate VRU type
            valid_vru_types = [e.value for e in VRUTypeEnum]
            if vru_type not in valid_vru_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid vru_type '{vru_type}'. Valid values: {valid_vru_types}"
                )
            query = query.filter(Annotation.vru_type == vru_type)
        
        # Apply pagination and ordering
        annotations = query.order_by(Annotation.timestamp).offset(skip).limit(limit).all()
        
        logger.info(f"Retrieved {len(annotations)} annotations for video {video_id}")
        return annotations
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving annotations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve annotations: {str(e)}"
        )

# ============================================================================
# HEALTH CHECK AND VALIDATION ENDPOINTS
# ============================================================================

@router.get("/{video_id}/annotations/health")
async def annotation_health_check(
    video_id: str,
    db: Session = Depends(get_db)
):
    """Health check for annotation system"""
    try:
        # Check video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        video_exists = video is not None
        
        # Check annotation count
        annotation_count = db.query(Annotation).filter(Annotation.video_id == video_id).count()
        
        # Check database connectivity
        db_connected = True
        try:
            db.execute("SELECT 1")
        except:
            db_connected = False
        
        return {
            "status": "healthy" if video_exists and db_connected else "unhealthy",
            "video_exists": video_exists,
            "video_id": video_id,
            "annotation_count": annotation_count,
            "database_connected": db_connected,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.post("/{video_id}/annotations/validate-schema")
async def validate_annotation_schema(
    video_id: str,
    annotation_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Validate annotation data against schema without creating"""
    try:
        # Try to create annotation schema object
        annotation = AnnotationCreate(**annotation_data)
        annotation.video_id = video_id
        
        # Validate VRU type
        valid_vru_types = [e.value for e in VRUTypeEnum]
        vru_type_value = annotation.vru_type.value if hasattr(annotation.vru_type, 'value') else annotation.vru_type
        
        return {
            "valid": True,
            "video_id": video_id,
            "processed_data": {
                "detection_id": annotation.detection_id,
                "frame_number": annotation.frame_number,
                "timestamp": annotation.timestamp,
                "vru_type": vru_type_value,
                "bounding_box": annotation.bounding_box.dict() if hasattr(annotation.bounding_box, 'dict') else annotation.bounding_box,
                "validated": annotation.validated
            },
            "vru_type_valid": vru_type_value in valid_vru_types,
            "valid_vru_types": valid_vru_types
        }
        
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "input_data": annotation_data
        }

# ============================================================================
# EXPORT ROUTER
# ============================================================================

# Export this router to be included in main app
annotation_fix_router = router

if __name__ == "__main__":
    print("🔧 Annotation API Fix Module")
    print("=" * 40)
    print("This module provides fixed annotation endpoints:")
    print("• POST /api/videos/{video_id}/annotations - Create annotation (FIXED)")
    print("• GET /api/videos/{video_id}/annotations - Get annotations (FIXED)")  
    print("• GET /api/videos/{video_id}/annotations/health - Health check")
    print("• POST /api/videos/{video_id}/annotations/validate-schema - Schema validation")
    print()
    print("Fixes applied:")
    print("✅ 500 Internal Server Error responses")
    print("✅ Missing videoId field validation")
    print("✅ Pydantic schema validation issues")
    print("✅ Database enum validation errors")
    print("✅ Proper error handling and logging")
    print("✅ Request/response validation")
    print()
    print("To use: Import annotation_fix_router and include in FastAPI app")