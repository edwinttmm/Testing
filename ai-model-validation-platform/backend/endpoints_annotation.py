from fastapi import HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime
import uuid

from database import get_db
from models import Annotation, AnnotationSession, VideoProjectLink, TestResult, DetectionComparison, Video
from schemas_annotation import (
    AnnotationCreate, AnnotationUpdate, AnnotationResponse,
    AnnotationSessionCreate, AnnotationSessionResponse,
    VideoProjectLinkCreate, VideoProjectLinkResponse,
    AnnotationExportRequest, TestResultResponse, DetectionComparisonResponse
)

logger = logging.getLogger(__name__)

# Annotation CRUD Endpoints

async def create_annotation(
    video_id: str,
    annotation: AnnotationCreate,
    db: Session = Depends(get_db)
) -> AnnotationResponse:
    """Create new annotation for video with proper validation"""
    try:
        # Validate video exists
        from models import Video
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail=f"Video with id {video_id} not found")
        
        # Ensure videoId is properly set (Pydantic validation requirement)
        if hasattr(annotation, 'video_id') and annotation.video_id != video_id:
            raise HTTPException(
                status_code=400, 
                detail=f"videoId in body ({annotation.video_id}) does not match URL parameter ({video_id})"
            )
        
        # Create annotation with proper enum handling
        import uuid
        from datetime import datetime
        
        db_annotation = Annotation(
            id=str(uuid.uuid4()),
            video_id=video_id,
            detection_id=annotation.detection_id,
            frame_number=annotation.frame_number,
            timestamp=annotation.timestamp,
            end_timestamp=annotation.end_timestamp,
            vru_type=annotation.vru_type.value if hasattr(annotation.vru_type, 'value') else annotation.vru_type,
            bounding_box=annotation.bounding_box if isinstance(annotation.bounding_box, dict) else annotation.bounding_box.dict(),
            occluded=annotation.occluded,
            truncated=annotation.truncated,
            difficult=annotation.difficult,
            notes=annotation.notes,
            annotator=annotation.annotator,
            validated=annotation.validated,
            created_at=datetime.utcnow()
        )
        
        db.add(db_annotation)
        db.commit()
        db.refresh(db_annotation)
        
        # Convert to proper response schema
        try:
            bounding_box = db_annotation.bounding_box
            if bounding_box is None:
                bounding_box = {"x": 0, "y": 0, "width": 1, "height": 1}
            elif isinstance(bounding_box, str):
                import json
                try:
                    bounding_box = json.loads(bounding_box)
                    # Ensure all required fields exist
                    if not all(field in bounding_box for field in ['x', 'y', 'width', 'height']):
                        bounding_box = {
                            "x": bounding_box.get('x', 0),
                            "y": bounding_box.get('y', 0), 
                            "width": bounding_box.get('width', 1),
                            "height": bounding_box.get('height', 1),
                            **{k: v for k, v in bounding_box.items() if k not in ['x', 'y', 'width', 'height']}
                        }
                except (json.JSONDecodeError, ValueError):
                    bounding_box = {"x": 0, "y": 0, "width": 1, "height": 1}
            elif not isinstance(bounding_box, dict):
                bounding_box = bounding_box.__dict__ if hasattr(bounding_box, '__dict__') else {"x": 0, "y": 0, "width": 1, "height": 1}
            
            # Final validation - ensure all required fields exist in any dict bounding_box
            if isinstance(bounding_box, dict) and not all(field in bounding_box for field in ['x', 'y', 'width', 'height']):
                bounding_box = {
                    "x": bounding_box.get('x', 0),
                    "y": bounding_box.get('y', 0), 
                    "width": bounding_box.get('width', 1),
                    "height": bounding_box.get('height', 1),
                    **{k: v for k, v in bounding_box.items() if k not in ['x', 'y', 'width', 'height']}
                }
                
            return AnnotationResponse(
                id=db_annotation.id,
                videoId=db_annotation.video_id,
                detectionId=db_annotation.detection_id,
                frameNumber=db_annotation.frame_number,
                timestamp=db_annotation.timestamp,
                endTimestamp=db_annotation.end_timestamp,
                vruType=db_annotation.vru_type,
                boundingBox=bounding_box,
                occluded=db_annotation.occluded or False,
                truncated=db_annotation.truncated or False,
                difficult=db_annotation.difficult or False,
                notes=db_annotation.notes,
                annotator=db_annotation.annotator,
                validated=db_annotation.validated or False,
                createdAt=db_annotation.created_at,
                updatedAt=db_annotation.updated_at
            )
        except Exception as e:
            logger.error(f"Error serializing created annotation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to serialize created annotation: {str(e)}")
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create annotation: {str(e)}")

async def get_annotations(
    video_id: str,
    validated_only: Optional[bool] = False,
    db: Session = Depends(get_db)
) -> List[AnnotationResponse]:
    """Get all annotations for a video"""
    query = db.query(Annotation).filter(Annotation.video_id == video_id)
    if validated_only:
        query = query.filter(Annotation.validated == True)
    annotations = query.order_by(Annotation.timestamp).all()
    
    # Convert SQLAlchemy objects to validated Pydantic response schemas
    response_annotations = []
    for annotation in annotations:
        try:
            # Ensure bounding_box is properly serialized as dict
            bounding_box = annotation.bounding_box
            if bounding_box is None:
                bounding_box = {"x": 0, "y": 0, "width": 1, "height": 1}
            elif isinstance(bounding_box, str):
                import json
                try:
                    bounding_box = json.loads(bounding_box)
                    # Ensure all required fields exist
                    if not all(field in bounding_box for field in ['x', 'y', 'width', 'height']):
                        bounding_box = {
                            "x": bounding_box.get('x', 0),
                            "y": bounding_box.get('y', 0), 
                            "width": bounding_box.get('width', 1),
                            "height": bounding_box.get('height', 1),
                            **{k: v for k, v in bounding_box.items() if k not in ['x', 'y', 'width', 'height']}
                        }
                except (json.JSONDecodeError, ValueError):
                    bounding_box = {"x": 0, "y": 0, "width": 1, "height": 1}
            elif not isinstance(bounding_box, dict):
                bounding_box = bounding_box.__dict__ if hasattr(bounding_box, '__dict__') else {"x": 0, "y": 0, "width": 1, "height": 1}
            
            # Final validation - ensure all required fields exist in any dict bounding_box
            if isinstance(bounding_box, dict) and not all(field in bounding_box for field in ['x', 'y', 'width', 'height']):
                bounding_box = {
                    "x": bounding_box.get('x', 0),
                    "y": bounding_box.get('y', 0), 
                    "width": bounding_box.get('width', 1),
                    "height": bounding_box.get('height', 1),
                    **{k: v for k, v in bounding_box.items() if k not in ['x', 'y', 'width', 'height']}
                }
                
            response_annotation = AnnotationResponse(
                id=annotation.id,
                videoId=annotation.video_id,
                detectionId=annotation.detection_id,
                frameNumber=annotation.frame_number,
                timestamp=annotation.timestamp,
                endTimestamp=annotation.end_timestamp,
                vruType=annotation.vru_type,
                boundingBox=bounding_box,
                occluded=annotation.occluded or False,
                truncated=annotation.truncated or False,
                difficult=annotation.difficult or False,
                notes=annotation.notes,
                annotator=annotation.annotator,
                validated=annotation.validated or False,
                createdAt=annotation.created_at,
                updatedAt=annotation.updated_at
            )
            response_annotations.append(response_annotation)
        except Exception as e:
            logger.error(f"Error serializing annotation {annotation.id}: {str(e)}")
            # Skip malformed annotations rather than failing the entire request
            continue
            
    return response_annotations

async def get_annotation(
    annotation_id: str,
    db: Session = Depends(get_db)
) -> AnnotationResponse:
    """Get specific annotation by ID"""
    annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    try:
        # Ensure bounding_box is properly serialized as dict
        bounding_box = annotation.bounding_box
        if bounding_box is None:
            bounding_box = {"x": 0, "y": 0, "width": 1, "height": 1}
        elif isinstance(bounding_box, str):
            import json
            bounding_box = json.loads(bounding_box)
        elif not isinstance(bounding_box, dict):
            bounding_box = bounding_box.__dict__ if hasattr(bounding_box, '__dict__') else {"x": 0, "y": 0, "width": 1, "height": 1}
            
        return AnnotationResponse(
            id=annotation.id,
            videoId=annotation.video_id,
            detectionId=annotation.detection_id,
            frameNumber=annotation.frame_number,
            timestamp=annotation.timestamp,
            endTimestamp=annotation.end_timestamp,
            vruType=annotation.vru_type,
            boundingBox=bounding_box,
            occluded=annotation.occluded or False,
            truncated=annotation.truncated or False,
            difficult=annotation.difficult or False,
            notes=annotation.notes,
            annotator=annotation.annotator,
            validated=annotation.validated or False,
            createdAt=annotation.created_at,
            updatedAt=annotation.updated_at
        )
    except Exception as e:
        logger.error(f"Error serializing annotation {annotation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serialize annotation: {str(e)}")

async def update_annotation(
    annotation_id: str,
    annotation_update: AnnotationUpdate,
    db: Session = Depends(get_db)
) -> AnnotationResponse:
    """Update existing annotation"""
    db_annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not db_annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    update_data = annotation_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_annotation, field, value)
    
    db.commit()
    db.refresh(db_annotation)
    
    # Convert to proper response schema
    try:
        bounding_box = db_annotation.bounding_box
        if bounding_box is None:
            bounding_box = {"x": 0, "y": 0, "width": 1, "height": 1}
        elif isinstance(bounding_box, str):
            import json
            bounding_box = json.loads(bounding_box)
        elif not isinstance(bounding_box, dict):
            bounding_box = bounding_box.__dict__ if hasattr(bounding_box, '__dict__') else {"x": 0, "y": 0, "width": 1, "height": 1}
            
        return AnnotationResponse(
            id=db_annotation.id,
            videoId=db_annotation.video_id,
            detectionId=db_annotation.detection_id,
            frameNumber=db_annotation.frame_number,
            timestamp=db_annotation.timestamp,
            endTimestamp=db_annotation.end_timestamp,
            vruType=db_annotation.vru_type,
            boundingBox=bounding_box,
            occluded=db_annotation.occluded or False,
            truncated=db_annotation.truncated or False,
            difficult=db_annotation.difficult or False,
            notes=db_annotation.notes,
            annotator=db_annotation.annotator,
            validated=db_annotation.validated or False,
            createdAt=db_annotation.created_at,
            updatedAt=db_annotation.updated_at
        )
    except Exception as e:
        logger.error(f"Error serializing updated annotation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serialize updated annotation: {str(e)}")

async def delete_annotation(
    annotation_id: str,
    db: Session = Depends(get_db)
):
    """Delete annotation"""
    db_annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not db_annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    db.delete(db_annotation)
    db.commit()
    return {"message": "Annotation deleted successfully"}

async def validate_annotation(
    annotation_id: str,
    validated: bool,
    db: Session = Depends(get_db)
) -> AnnotationResponse:
    """Mark annotation as validated/unvalidated"""
    db_annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not db_annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    db_annotation.validated = validated
    db.commit()
    db.refresh(db_annotation)
    
    # Convert to proper response schema
    try:
        bounding_box = db_annotation.bounding_box
        if bounding_box is None:
            bounding_box = {"x": 0, "y": 0, "width": 1, "height": 1}
        elif isinstance(bounding_box, str):
            import json
            bounding_box = json.loads(bounding_box)
        elif not isinstance(bounding_box, dict):
            bounding_box = bounding_box.__dict__ if hasattr(bounding_box, '__dict__') else {"x": 0, "y": 0, "width": 1, "height": 1}
            
        return AnnotationResponse(
            id=db_annotation.id,
            videoId=db_annotation.video_id,
            detectionId=db_annotation.detection_id,
            frameNumber=db_annotation.frame_number,
            timestamp=db_annotation.timestamp,
            endTimestamp=db_annotation.end_timestamp,
            vruType=db_annotation.vru_type,
            boundingBox=bounding_box,
            occluded=db_annotation.occluded or False,
            truncated=db_annotation.truncated or False,
            difficult=db_annotation.difficult or False,
            notes=db_annotation.notes,
            annotator=db_annotation.annotator,
            validated=db_annotation.validated or False,
            createdAt=db_annotation.created_at,
            updatedAt=db_annotation.updated_at
        )
    except Exception as e:
        logger.error(f"Error serializing validated annotation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serialize validated annotation: {str(e)}")

async def get_annotations_by_detection_id(
    detection_id: str,
    db: Session = Depends(get_db)
) -> List[AnnotationResponse]:
    """Get annotations by detection ID for temporal tracking"""
    annotations = db.query(Annotation).filter(Annotation.detection_id == detection_id).order_by(Annotation.timestamp).all()
    
    # Convert SQLAlchemy objects to validated Pydantic response schemas
    response_annotations = []
    for annotation in annotations:
        try:
            # Ensure bounding_box is properly serialized as dict
            bounding_box = annotation.bounding_box
            if bounding_box is None:
                bounding_box = {"x": 0, "y": 0, "width": 1, "height": 1}
            elif isinstance(bounding_box, str):
                import json
                try:
                    bounding_box = json.loads(bounding_box)
                    # Ensure all required fields exist
                    if not all(field in bounding_box for field in ['x', 'y', 'width', 'height']):
                        bounding_box = {
                            "x": bounding_box.get('x', 0),
                            "y": bounding_box.get('y', 0), 
                            "width": bounding_box.get('width', 1),
                            "height": bounding_box.get('height', 1),
                            **{k: v for k, v in bounding_box.items() if k not in ['x', 'y', 'width', 'height']}
                        }
                except (json.JSONDecodeError, ValueError):
                    bounding_box = {"x": 0, "y": 0, "width": 1, "height": 1}
            elif not isinstance(bounding_box, dict):
                bounding_box = bounding_box.__dict__ if hasattr(bounding_box, '__dict__') else {"x": 0, "y": 0, "width": 1, "height": 1}
            
            # Final validation - ensure all required fields exist in any dict bounding_box
            if isinstance(bounding_box, dict) and not all(field in bounding_box for field in ['x', 'y', 'width', 'height']):
                bounding_box = {
                    "x": bounding_box.get('x', 0),
                    "y": bounding_box.get('y', 0), 
                    "width": bounding_box.get('width', 1),
                    "height": bounding_box.get('height', 1),
                    **{k: v for k, v in bounding_box.items() if k not in ['x', 'y', 'width', 'height']}
                }
                
            response_annotation = AnnotationResponse(
                id=annotation.id,
                videoId=annotation.video_id,
                detectionId=annotation.detection_id,
                frameNumber=annotation.frame_number,
                timestamp=annotation.timestamp,
                endTimestamp=annotation.end_timestamp,
                vruType=annotation.vru_type,
                boundingBox=bounding_box,
                occluded=annotation.occluded or False,
                truncated=annotation.truncated or False,
                difficult=annotation.difficult or False,
                notes=annotation.notes,
                annotator=annotation.annotator,
                validated=annotation.validated or False,
                createdAt=annotation.created_at,
                updatedAt=annotation.updated_at
            )
            response_annotations.append(response_annotation)
        except Exception as e:
            logger.error(f"Error serializing annotation {annotation.id}: {str(e)}")
            # Skip malformed annotations rather than failing the entire request
            continue
            
    return response_annotations

# Annotation Session Endpoints

async def create_annotation_session(
    session_create: AnnotationSessionCreate,
    db: Session = Depends(get_db)
):
    """Create new annotation session"""
    db_session = AnnotationSession(
        video_id=session_create.video_id,
        project_id=session_create.project_id,
        annotator_id=session_create.annotator_id
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

async def get_annotation_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get annotation session details"""
    session = db.query(AnnotationSession).filter(AnnotationSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Annotation session not found")
    return session

# Project-Video Linking Endpoints

async def get_available_ground_truth_videos(
    db: Session = Depends(get_db)
):
    """Get videos available for linking (not linked to any project)"""
    from models import Video
    # Find videos that are not linked to any project
    linked_video_ids = db.query(VideoProjectLink.video_id).distinct().all()
    linked_video_ids = [vid[0] for vid in linked_video_ids]
    
    available_videos = db.query(Video).filter(~Video.id.in_(linked_video_ids)).all()
    return available_videos

async def link_videos_to_project(
    project_id: str,
    video_link: VideoProjectLinkCreate,
    db: Session = Depends(get_db)
):
    """Link existing ground truth videos to projects"""
    # Check if link already exists
    existing_link = db.query(VideoProjectLink).filter(
        VideoProjectLink.video_id == video_link.video_id,
        VideoProjectLink.project_id == project_id
    ).first()
    
    if existing_link:
        raise HTTPException(status_code=409, detail="Video already linked to project")
    
    db_link = VideoProjectLink(
        video_id=video_link.video_id,
        project_id=project_id,
        assignment_reason=video_link.assignment_reason,
        intelligent_match=True,
        confidence_score=0.95  # Default confidence for manual linking
    )
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link

async def get_linked_videos(
    project_id: str,
    db: Session = Depends(get_db)
):
    """Get videos linked to a specific project"""
    from models import Video
    linked_videos = db.query(Video).join(VideoProjectLink).filter(
        VideoProjectLink.project_id == project_id
    ).all()
    return linked_videos

async def unlink_video_from_project(
    project_id: str,
    video_id: str,
    db: Session = Depends(get_db)
):
    """Remove video link from project"""
    link = db.query(VideoProjectLink).filter(
        VideoProjectLink.project_id == project_id,
        VideoProjectLink.video_id == video_id
    ).first()
    
    if not link:
        raise HTTPException(status_code=404, detail="Video link not found")
    
    db.delete(link)
    db.commit()
    return {"message": "Video unlinked successfully"}

# Export/Import Functions (to be implemented with services)

async def export_annotations(
    video_id: str,
    format: str = Query("json", pattern="^(json|coco|yolo|pascal_voc)$"),
    db: Session = Depends(get_db)
):
    """Export annotations in specified format"""
    annotations = db.query(Annotation).filter(Annotation.video_id == video_id).all()
    
    if format == "json":
        return {"annotations": [
            {
                "id": ann.id,
                "detection_id": ann.detection_id,
                "frame_number": ann.frame_number,
                "timestamp": ann.timestamp,
                "vru_type": ann.vru_type,
                "bounding_box": ann.bounding_box,
                "validated": ann.validated
            } for ann in annotations
        ]}
    
    # TODO: Implement other formats (COCO, YOLO, Pascal VOC) via service layer
    return {"message": f"Export format {format} not yet implemented"}

async def import_annotations(
    video_id: str,
    format: str = Query("json", pattern="^(json|coco|yolo|pascal_voc)$"),
    # file: UploadFile = File(...),  # TODO: Add file upload support
    db: Session = Depends(get_db)
):
    """Import annotations from specified format"""
    # TODO: Implement annotation import functionality
    return {"message": f"Import format {format} not yet implemented"}