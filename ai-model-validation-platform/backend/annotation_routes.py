from fastapi import APIRouter, HTTPException, Depends, Query, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db

from models import Annotation, AnnotationSession, VideoProjectLink
from schemas_annotation import (
    AnnotationCreate, AnnotationUpdate, AnnotationResponse,
    AnnotationSessionCreate, AnnotationSessionResponse,
    VideoProjectLinkCreate, VideoProjectLinkResponse
)

import endpoints_annotation as annotation_endpoints

router = APIRouter(prefix="/api", tags=["annotations"])

# Annotation CRUD Routes
@router.post("/videos/{video_id}/annotations", response_model=AnnotationResponse)
async def create_annotation(
    video_id: str,
    annotation: AnnotationCreate,
    db: Session = Depends(get_db)
):
    """Create new annotation for video"""
    return await annotation_endpoints.create_annotation(video_id, annotation, db)

@router.get("/videos/{video_id}/annotations", response_model=List[AnnotationResponse])
async def get_annotations(
    video_id: str,
    validated_only: Optional[bool] = False,
    db: Session = Depends(get_db)
):
    """Get all annotations for a video"""
    return await annotation_endpoints.get_annotations(video_id, validated_only, db)

@router.get("/annotations/{annotation_id}", response_model=AnnotationResponse)
async def get_annotation(
    annotation_id: str,
    db: Session = Depends(get_db)
):
    """Get specific annotation by ID"""
    return await annotation_endpoints.get_annotation(annotation_id, db)

@router.put("/annotations/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation(
    annotation_id: str,
    annotation_update: AnnotationUpdate,
    db: Session = Depends(get_db)
):
    """Update existing annotation"""
    return await annotation_endpoints.update_annotation(annotation_id, annotation_update, db)

@router.delete("/annotations/{annotation_id}")
async def delete_annotation(
    annotation_id: str,
    db: Session = Depends(get_db)
):
    """Delete annotation"""
    return await annotation_endpoints.delete_annotation(annotation_id, db)

@router.patch("/annotations/{annotation_id}/validate", response_model=AnnotationResponse)
async def validate_annotation(
    annotation_id: str,
    validated: bool = Query(..., description="Set validation status"),
    db: Session = Depends(get_db)
):
    """Mark annotation as validated/unvalidated"""
    return await annotation_endpoints.validate_annotation(annotation_id, validated, db)

@router.get("/annotations/detection/{detection_id}", response_model=List[AnnotationResponse])
async def get_annotations_by_detection_id(
    detection_id: str,
    db: Session = Depends(get_db)
):
    """Get annotations by detection ID for temporal tracking"""
    return await annotation_endpoints.get_annotations_by_detection_id(detection_id, db)

# Annotation Session Routes
@router.post("/annotation-sessions", response_model=AnnotationSessionResponse)
async def create_annotation_session(
    session_create: AnnotationSessionCreate,
    db: Session = Depends(get_db)
):
    """Create new annotation session"""
    return await annotation_endpoints.create_annotation_session(session_create, db)

@router.get("/annotation-sessions/{session_id}", response_model=AnnotationSessionResponse)
async def get_annotation_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get annotation session details"""
    return await annotation_endpoints.get_annotation_session(session_id, db)

# Project-Video Linking Routes
@router.get("/ground-truth/videos/available")
async def get_available_ground_truth_videos(
    db: Session = Depends(get_db)
):
    """Get videos available for linking (not linked to any project)"""
    return await annotation_endpoints.get_available_ground_truth_videos(db)

@router.post("/projects/{project_id}/videos/link", response_model=VideoProjectLinkResponse)
async def link_videos_to_project(
    project_id: str,
    video_link: VideoProjectLinkCreate,
    db: Session = Depends(get_db)
):
    """Link existing ground truth videos to projects"""
    return await annotation_endpoints.link_videos_to_project(project_id, video_link, db)

@router.get("/projects/{project_id}/videos/linked")
async def get_linked_videos(
    project_id: str,
    db: Session = Depends(get_db)
):
    """Get videos linked to a specific project"""
    return await annotation_endpoints.get_linked_videos(project_id, db)

@router.delete("/projects/{project_id}/videos/{video_id}/unlink")
async def unlink_video_from_project(
    project_id: str,
    video_id: str,
    db: Session = Depends(get_db)
):
    """Remove video link from project"""
    return await annotation_endpoints.unlink_video_from_project(project_id, video_id, db)

# Export/Import Routes
@router.get("/videos/{video_id}/annotations/export")
async def export_annotations(
    video_id: str,
    format: str = Query("json", pattern="^(json|coco|yolo|pascal_voc)$"),
    db: Session = Depends(get_db)
):
    """Export annotations in specified format"""
    return await annotation_endpoints.export_annotations(video_id, format, db)

@router.post("/videos/{video_id}/annotations/import")
async def import_annotations(
    video_id: str,
    format: str = Query("json", pattern="^(json|coco|yolo|pascal_voc)$"),
    # file: UploadFile = File(...),  # TODO: Add when import is implemented
    db: Session = Depends(get_db)
):
    """Import annotations from specified format"""
    return await annotation_endpoints.import_annotations(video_id, format, db)