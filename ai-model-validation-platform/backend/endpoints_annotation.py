from fastapi import HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db

# Import models from separate annotation models file
import sys
import os
sys.path.append(os.path.dirname(__file__))
from models_annotation import Annotation, AnnotationSession, VideoProjectLink, TestResult, DetectionComparison
from schemas_annotation import (
    AnnotationCreate, AnnotationUpdate, AnnotationResponse,
    AnnotationSessionCreate, AnnotationSessionResponse,
    VideoProjectLinkCreate, VideoProjectLinkResponse,
    AnnotationExportRequest, TestResultResponse, DetectionComparisonResponse
)

# Annotation CRUD Endpoints

async def create_annotation(
    video_id: str,
    annotation: AnnotationCreate,
    db: Session = Depends(get_db)
):
    """Create new annotation for video"""
    db_annotation = Annotation(
        video_id=video_id,
        detection_id=annotation.detection_id,
        frame_number=annotation.frame_number,
        timestamp=annotation.timestamp,
        end_timestamp=annotation.end_timestamp,
        vru_type=annotation.vru_type,
        bounding_box=annotation.bounding_box,
        occluded=annotation.occluded,
        truncated=annotation.truncated,
        difficult=annotation.difficult,
        notes=annotation.notes,
        annotator=annotation.annotator,
        validated=annotation.validated
    )
    db.add(db_annotation)
    db.commit()
    db.refresh(db_annotation)
    return db_annotation

async def get_annotations(
    video_id: str,
    validated_only: Optional[bool] = False,
    db: Session = Depends(get_db)
):
    """Get all annotations for a video"""
    query = db.query(Annotation).filter(Annotation.video_id == video_id)
    if validated_only:
        query = query.filter(Annotation.validated == True)
    annotations = query.order_by(Annotation.timestamp).all()
    return annotations

async def get_annotation(
    annotation_id: str,
    db: Session = Depends(get_db)
):
    """Get specific annotation by ID"""
    annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return annotation

async def update_annotation(
    annotation_id: str,
    annotation_update: AnnotationUpdate,
    db: Session = Depends(get_db)
):
    """Update existing annotation"""
    db_annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not db_annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    update_data = annotation_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_annotation, field, value)
    
    db.commit()
    db.refresh(db_annotation)
    return db_annotation

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
):
    """Mark annotation as validated/unvalidated"""
    db_annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not db_annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    db_annotation.validated = validated
    db.commit()
    db.refresh(db_annotation)
    return db_annotation

async def get_annotations_by_detection_id(
    detection_id: str,
    db: Session = Depends(get_db)
):
    """Get annotations by detection ID for temporal tracking"""
    annotations = db.query(Annotation).filter(Annotation.detection_id == detection_id).order_by(Annotation.timestamp).all()
    return annotations

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