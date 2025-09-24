"""
Validation Criteria Router
=========================

Simple admin API to get/set video validation criteria per project.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
import logging
from datetime import datetime

from database import SessionLocal
from models import VideoValidationCriteria
from schemas_video_validation import ValidationCriteriaRequest, ValidationCriteriaResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/validation", tags=["Validation Criteria"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/criteria", response_model=ValidationCriteriaResponse)
async def get_criteria(projectId: str | None = Query(None), db: Session = Depends(get_db)):
    try:
        if projectId:
            crit = db.query(VideoValidationCriteria).filter(VideoValidationCriteria.project_id == projectId).first()
            if not crit:
                raise HTTPException(status_code=404, detail="No criteria for project")
        else:
            crit = db.query(VideoValidationCriteria).filter(VideoValidationCriteria.project_id.is_(None)).first()
            if not crit:
                # Create a default criteria if none exists
                crit = VideoValidationCriteria(
                    project_id=None,
                    min_detection_count=5,
                    min_confidence_threshold=0.7,
                    min_frame_coverage_percent=80.0,
                    min_duration_seconds=10.0,
                    max_duration_seconds=300.0,
                    required_resolution_min="640x480",
                    min_fps=24.0,
                    required_vru_types=["pedestrian", "cyclist", "motorcyclist"],
                    min_scene_complexity_score=0.5,
                    created_at=datetime.utcnow(),
                )
                db.add(crit)
                db.commit()
                db.refresh(crit)

        return ValidationCriteriaResponse(
            id=getattr(crit, 'id'),
            project_id=crit.project_id,
            min_detection_count=crit.min_detection_count,
            min_confidence_threshold=crit.min_confidence_threshold,
            min_frame_coverage_percent=crit.min_frame_coverage_percent,
            min_duration_seconds=crit.min_duration_seconds,
            max_duration_seconds=crit.max_duration_seconds,
            required_resolution_min=crit.required_resolution_min,
            min_fps=crit.min_fps,
            required_vru_types=crit.required_vru_types,
            min_scene_complexity_score=crit.min_scene_complexity_score,
            created_at=crit.created_at,
            updated_at=crit.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get criteria: {e}")
        raise HTTPException(status_code=500, detail="Failed to get criteria")

@router.post("/criteria", response_model=ValidationCriteriaResponse)
async def upsert_criteria(payload: ValidationCriteriaRequest, db: Session = Depends(get_db)):
    try:
        project_id = payload.project_id
        crit = None
        if project_id:
            crit = db.query(VideoValidationCriteria).filter(VideoValidationCriteria.project_id == project_id).first()
        else:
            crit = db.query(VideoValidationCriteria).filter(VideoValidationCriteria.project_id.is_(None)).first()

        fields = payload.model_dump()

        if crit:
            for k, v in fields.items():
                if k != 'project_id' and v is not None:
                    setattr(crit, k, v)
            crit.updated_at = datetime.utcnow()
        else:
            crit = VideoValidationCriteria(
                project_id=project_id,
                **{k: v for k, v in fields.items() if k != 'project_id'},
                created_at=datetime.utcnow(),
            )
            db.add(crit)
        db.commit()
        db.refresh(crit)

        return ValidationCriteriaResponse(
            id=getattr(crit, 'id'),
            project_id=crit.project_id,
            min_detection_count=crit.min_detection_count,
            min_confidence_threshold=crit.min_confidence_threshold,
            min_frame_coverage_percent=crit.min_frame_coverage_percent,
            min_duration_seconds=crit.min_duration_seconds,
            max_duration_seconds=crit.max_duration_seconds,
            required_resolution_min=crit.required_resolution_min,
            min_fps=crit.min_fps,
            required_vru_types=crit.required_vru_types,
            min_scene_complexity_score=crit.min_scene_complexity_score,
            created_at=crit.created_at,
            updated_at=crit.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upsert criteria: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert criteria")

