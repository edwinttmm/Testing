"""
Ground Truth Management API Routes
SPARC Implementation - Complete REST API for ground truth operations
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query, BackgroundTasks, File, UploadFile
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, and_, or_, desc, asc
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
import logging
import uuid
import json
import asyncio
from pydantic import BaseModel, Field, validator

from database import SessionLocal
from models import GroundTruthObject, Video, Project, Annotation
from src.models.ground_truth_models import (
    GroundTruthValidationWorkflow, ValidationHistory, GroundTruthBatch,
    GroundTruthBatchItem, GroundTruthExport, GroundTruthQualityMetrics,
    ValidationStatus, GenerationMethod, QualityLevel
)
from src.services.ground_truth_service import GroundTruthService
from src.services.ml_generation_service import MLGenerationService
try:
    from src.form_validation_middleware import ValidationMiddleware
except ImportError:
    # Fallback if ValidationMiddleware is not available
    class ValidationMiddleware:
        @staticmethod
        def validate_id_parameter(id_param, param_name):
            if not id_param or not isinstance(id_param, str):
                raise ValueError(f"Invalid {param_name}: must be a non-empty string")
            return id_param.strip()

logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/api/ground-truth", tags=["ground-truth"])

# Initialize services
ground_truth_service = GroundTruthService()
ml_generation_service = MLGenerationService()

# Pydantic models for API contracts
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
    generation_method: GenerationMethod = GenerationMethod.MANUAL
    
    class Config:
        populate_by_name = True
        use_enum_values = True
    
    @validator('class_label')
    def validate_class_label(cls, v):
        allowed_classes = ['pedestrian', 'cyclist', 'motorcyclist', 'wheelchair', 'scooter', 'animal', 'other']
        if v.lower() not in allowed_classes:
            raise ValueError(f"Class label must be one of: {', '.join(allowed_classes)}")
        return v.lower()

class ValidationWorkflowCreate(BaseModel):
    ground_truth_id: str = Field(..., alias="groundTruthId")
    assigned_reviewer: Optional[str] = Field(None, alias="assignedReviewer")
    quality_level: QualityLevel = Field(default=QualityLevel.UNCERTAIN, alias="qualityLevel")
    review_notes: Optional[str] = Field(None, alias="reviewNotes")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, alias="confidenceScore")
    
    class Config:
        populate_by_name = True
        use_enum_values = True

class ValidationDecision(BaseModel):
    validation_status: ValidationStatus = Field(..., alias="validationStatus")
    review_notes: str = Field(..., alias="reviewNotes")
    quality_level: Optional[QualityLevel] = Field(None, alias="qualityLevel")
    reviewer_id: str = Field(..., alias="reviewerId")
    
    class Config:
        populate_by_name = True
        use_enum_values = True

class BatchProcessingRequest(BaseModel):
    batch_name: str = Field(..., alias="batchName")
    video_ids: List[str] = Field(..., alias="videoIds")
    processing_method: GenerationMethod = Field(..., alias="processingMethod")
    description: Optional[str] = None
    batch_config: Optional[Dict[str, Any]] = Field(None, alias="batchConfig")
    
    class Config:
        populate_by_name = True
        use_enum_values = True

class ExportRequest(BaseModel):
    export_name: str = Field(..., alias="exportName")
    format_type: str = Field(..., pattern="^(json|coco|yolo|pascal_voc)$", alias="formatType")
    video_filter: Optional[Dict[str, Any]] = Field(None, alias="videoFilter")
    quality_filter: Optional[Dict[str, Any]] = Field(None, alias="qualityFilter")
    validation_filter: Optional[Dict[str, Any]] = Field(None, alias="validationFilter")
    description: Optional[str] = None
    
    class Config:
        populate_by_name = True

# CRUD Operations
@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_ground_truth_object(
    ground_truth: GroundTruthCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create a new ground truth object with validation workflow
    """
    try:
        # Validate video exists
        video = db.query(Video).filter(Video.id == ground_truth.video_id).first()
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video with ID {ground_truth.video_id} not found"
            )
        
        # Create ground truth object
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
        
        # Create validation workflow
        workflow = GroundTruthValidationWorkflow(
            id=str(uuid.uuid4()),
            ground_truth_id=db_gt.id,
            video_id=ground_truth.video_id,
            generation_method=ground_truth.generation_method,
            validation_status=ValidationStatus.PENDING,
            quality_level=QualityLevel.UNCERTAIN,
            confidence_score=ground_truth.confidence,
            created_at=datetime.utcnow()
        )
        
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        
        # Calculate quality metrics in background
        background_tasks.add_task(
            ground_truth_service.calculate_quality_metrics,
            db_gt.id
        )
        
        logger.info(f"Created ground truth object {db_gt.id} with validation workflow")
        
        return {
            "id": db_gt.id,
            "workflow_id": workflow.id,
            "status": "created",
            "message": "Ground truth object created successfully"
        }
        
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

# Validation Workflow Endpoints
@router.post("/validation-workflow", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_validation_workflow(
    workflow_data: ValidationWorkflowCreate,
    db: Session = Depends(get_db)
):
    """
    Create validation workflow for existing ground truth object
    """
    try:
        # Validate ground truth object exists
        gt = db.query(GroundTruthObject).filter(GroundTruthObject.id == workflow_data.ground_truth_id).first()
        if not gt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ground truth object with ID {workflow_data.ground_truth_id} not found"
            )
        
        # Check if workflow already exists
        existing_workflow = db.query(GroundTruthValidationWorkflow).filter(
            GroundTruthValidationWorkflow.ground_truth_id == workflow_data.ground_truth_id
        ).first()
        
        if existing_workflow:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Validation workflow already exists for this ground truth object"
            )
        
        # Create validation workflow
        workflow = GroundTruthValidationWorkflow(
            id=str(uuid.uuid4()),
            ground_truth_id=workflow_data.ground_truth_id,
            video_id=gt.video_id,
            generation_method=GenerationMethod.MANUAL,
            validation_status=ValidationStatus.PENDING,
            quality_level=workflow_data.quality_level,
            assigned_reviewer=workflow_data.assigned_reviewer,
            review_notes=workflow_data.review_notes,
            confidence_score=workflow_data.confidence_score,
            created_at=datetime.utcnow()
        )
        
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        
        logger.info(f"Created validation workflow {workflow.id} for ground truth {workflow_data.ground_truth_id}")
        
        return {
            "workflow_id": workflow.id,
            "status": "created",
            "message": "Validation workflow created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating validation workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create validation workflow"
        )

@router.put("/validation-workflow/{workflow_id}/review", response_model=dict)
async def submit_validation_decision(
    workflow_id: str,
    decision: ValidationDecision,
    db: Session = Depends(get_db)
):
    """
    Submit validation decision for ground truth object
    """
    try:
        workflow_id = ValidationMiddleware.validate_id_parameter(workflow_id, "Workflow ID")
        
        # Get validation workflow
        workflow = db.query(GroundTruthValidationWorkflow).filter(
            GroundTruthValidationWorkflow.id == workflow_id
        ).first()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Validation workflow with ID {workflow_id} not found"
            )
        
        # Record history
        history = ValidationHistory(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            previous_status=workflow.validation_status,
            new_status=decision.validation_status,
            changed_by=decision.reviewer_id,
            change_reason=decision.review_notes,
            timestamp=datetime.utcnow()
        )
        
        # Update workflow
        workflow.validation_status = decision.validation_status
        workflow.review_notes = decision.review_notes
        workflow.reviewed_by = decision.reviewer_id
        workflow.review_timestamp = datetime.utcnow()
        
        if decision.quality_level:
            workflow.quality_level = decision.quality_level
        
        # Update ground truth object if approved
        if decision.validation_status == ValidationStatus.APPROVED:
            gt = db.query(GroundTruthObject).filter(
                GroundTruthObject.id == workflow.ground_truth_id
            ).first()
            if gt:
                gt.validated = True
        
        db.add(history)
        db.commit()
        
        logger.info(f"Validation decision submitted for workflow {workflow_id}: {decision.validation_status}")
        
        return {
            "workflow_id": workflow_id,
            "status": decision.validation_status.value,
            "message": "Validation decision submitted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error submitting validation decision: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit validation decision"
        )

# Automated Generation Endpoints
@router.post("/generate/video/{video_id}", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def generate_ground_truth_automated(
    video_id: str,
    background_tasks: BackgroundTasks,
    confidence_threshold: float = Query(0.5, ge=0.1, le=1.0),
    processing_method: GenerationMethod = Query(GenerationMethod.AUTOMATED_ML),
    db: Session = Depends(get_db)
):
    """
    Generate ground truth automatically using ML models
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
        
        # Check if already processing
        if video.processing_status == "processing":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Video is already being processed"
            )
        
        # Start automated generation in background
        background_tasks.add_task(
            ml_generation_service.generate_ground_truth,
            video_id,
            confidence_threshold,
            processing_method
        )
        
        # Update video status
        video.processing_status = "processing"
        db.commit()
        
        logger.info(f"Started automated ground truth generation for video {video_id}")
        
        return {
            "video_id": video_id,
            "status": "processing",
            "message": "Automated ground truth generation started",
            "confidence_threshold": confidence_threshold,
            "processing_method": processing_method.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting automated generation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start automated ground truth generation"
        )

# Batch Processing Endpoints
@router.post("/batch", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_batch_processing(
    batch_request: BatchProcessingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create batch processing job for multiple videos
    """
    try:
        # Validate videos exist
        videos = db.query(Video).filter(Video.id.in_(batch_request.video_ids)).all()
        if len(videos) != len(batch_request.video_ids):
            missing_ids = set(batch_request.video_ids) - {v.id for v in videos}
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Videos not found: {list(missing_ids)}"
            )
        
        # Create batch
        batch = GroundTruthBatch(
            id=str(uuid.uuid4()),
            batch_name=batch_request.batch_name,
            description=batch_request.description,
            processing_method=batch_request.processing_method,
            total_videos=len(batch_request.video_ids),
            batch_config=batch_request.batch_config or {},
            status="created",
            created_at=datetime.utcnow()
        )
        
        db.add(batch)
        db.commit()
        db.refresh(batch)
        
        # Create batch items
        batch_items = []
        for video_id in batch_request.video_ids:
            item = GroundTruthBatchItem(
                id=str(uuid.uuid4()),
                batch_id=batch.id,
                video_id=video_id,
                status="pending",
                processing_config=batch_request.batch_config or {},
                created_at=datetime.utcnow()
            )
            batch_items.append(item)
        
        db.add_all(batch_items)
        db.commit()
        
        # Start batch processing in background
        background_tasks.add_task(
            ground_truth_service.process_batch,
            batch.id
        )
        
        logger.info(f"Created batch processing job {batch.id} with {len(batch_items)} videos")
        
        return {
            "batch_id": batch.id,
            "status": "created",
            "total_videos": len(batch_request.video_ids),
            "message": "Batch processing job created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating batch processing job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create batch processing job"
        )

@router.get("/batch/{batch_id}/status", response_model=dict)
async def get_batch_status(
    batch_id: str,
    db: Session = Depends(get_db)
):
    """
    Get batch processing status
    """
    try:
        batch_id = ValidationMiddleware.validate_id_parameter(batch_id, "Batch ID")
        
        batch = db.query(GroundTruthBatch).options(
            joinedload(GroundTruthBatch.batch_items)
        ).filter(GroundTruthBatch.id == batch_id).first()
        
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch with ID {batch_id} not found"
            )
        
        # Calculate progress
        progress_percentage = 0
        if batch.total_videos > 0:
            progress_percentage = (batch.processed_videos / batch.total_videos) * 100
        
        return {
            "batch_id": batch.id,
            "batch_name": batch.batch_name,
            "status": batch.status,
            "total_videos": batch.total_videos,
            "processed_videos": batch.processed_videos,
            "successful_videos": batch.successful_videos,
            "failed_videos": batch.failed_videos,
            "progress_percentage": round(progress_percentage, 2),
            "started_at": batch.started_at,
            "completed_at": batch.completed_at,
            "performance_metrics": batch.performance_metrics,
            "error_log": batch.error_log
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get batch status"
        )

# Export Functionality
@router.post("/export", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def create_export_job(
    export_request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create ground truth export job
    """
    try:
        # Create export record
        export = GroundTruthExport(
            id=str(uuid.uuid4()),
            export_name=export_request.export_name,
            description=export_request.description,
            format_type=export_request.format_type,
            video_filter=export_request.video_filter or {},
            quality_filter=export_request.quality_filter or {},
            validation_filter=export_request.validation_filter or {},
            status="created",
            created_at=datetime.utcnow()
        )
        
        db.add(export)
        db.commit()
        db.refresh(export)
        
        # Start export processing in background
        background_tasks.add_task(
            ground_truth_service.process_export,
            export.id
        )
        
        logger.info(f"Created export job {export.id} with format {export_request.format_type}")
        
        return {
            "export_id": export.id,
            "status": "created",
            "format": export_request.format_type,
            "message": "Export job created successfully"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating export job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create export job"
        )

@router.get("/export/{export_id}/download")
async def download_export(
    export_id: str,
    db: Session = Depends(get_db)
):
    """
    Download completed export file
    """
    try:
        export_id = ValidationMiddleware.validate_id_parameter(export_id, "Export ID")
        
        export = db.query(GroundTruthExport).filter(GroundTruthExport.id == export_id).first()
        if not export:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Export with ID {export_id} not found"
            )
        
        if export.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Export is not completed. Current status: {export.status}"
            )
        
        if not export.file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Export file not found"
            )
        
        from fastapi.responses import FileResponse
        return FileResponse(
            path=export.file_path,
            filename=f"{export.export_name}.{export.format_type}",
            media_type="application/octet-stream"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading export: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download export file"
        )

# Quality Metrics and Statistics
@router.get("/stats/video/{video_id}/quality", response_model=dict)
async def get_quality_metrics(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Get quality metrics for ground truth objects in a video
    """
    try:
        video_id = ValidationMiddleware.validate_id_parameter(video_id, "Video ID")
        
        # Get quality metrics
        metrics = db.query(GroundTruthQualityMetrics).filter(
            GroundTruthQualityMetrics.video_id == video_id
        ).all()
        
        if not metrics:
            return {
                "video_id": video_id,
                "total_objects": 0,
                "quality_metrics": {},
                "message": "No quality metrics available"
            }
        
        # Aggregate metrics
        total_objects = len(metrics)
        avg_annotation_quality = sum(m.annotation_quality_score or 0 for m in metrics) / total_objects
        avg_detection_confidence = sum(m.detection_confidence or 0 for m in metrics) / total_objects
        avg_spatial_accuracy = sum(m.spatial_accuracy or 0 for m in metrics) / total_objects
        avg_temporal_consistency = sum(m.temporal_consistency or 0 for m in metrics) / total_objects
        
        return {
            "video_id": video_id,
            "total_objects": total_objects,
            "quality_metrics": {
                "average_annotation_quality": round(avg_annotation_quality, 3),
                "average_detection_confidence": round(avg_detection_confidence, 3),
                "average_spatial_accuracy": round(avg_spatial_accuracy, 3),
                "average_temporal_consistency": round(avg_temporal_consistency, 3),
                "quality_distribution": ground_truth_service.calculate_quality_distribution(metrics),
                "complexity_metrics": ground_truth_service.calculate_complexity_metrics(metrics)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quality metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get quality metrics"
        )

# Videos with Ground Truth Endpoints
@router.get("/videos/available", response_model=dict)
async def get_videos_with_ground_truth(
    db: Session = Depends(get_db),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    status_filter: Optional[str] = Query(None, description="Filter by video status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of videos to return"),
    offset: int = Query(0, ge=0, description="Number of videos to skip")
):
    """
    Get all videos that have ground truth annotations available
    """
    try:
        logger.info(f"Getting videos with ground truth - project_id: {project_id}, status: {status_filter}")
        
        # Base query for videos with ground truth
        query = db.query(Video).filter(
            Video.ground_truth_generated == True
        ).options(
            joinedload(Video.project)
        )
        
        # Apply project filter if provided
        if project_id:
            query = query.filter(Video.project_id == project_id)
        
        # Apply status filter if provided
        if status_filter:
            if status_filter == "validated":
                query = query.filter(Video.status == "validated")
            elif status_filter == "processing":
                query = query.filter(Video.processing_status == "processing")
            elif status_filter == "completed":
                query = query.filter(Video.status.in_(["completed", "validated"]))
        
        # Get total count before applying pagination
        total_count = query.count()
        
        # Apply pagination
        videos = query.offset(offset).limit(limit).all()
        
        # Format response
        video_list = []
        for video in videos:
            # Get ground truth count for this video
            gt_count = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video.id
            ).count()
            
            video_data = {
                "id": video.id,
                "filename": video.filename,
                "originalName": video.original_name or video.filename,
                "uploadDate": video.upload_date.isoformat() if video.upload_date else None,
                "status": video.status,
                "processingStatus": video.processing_status,
                "groundTruthGenerated": bool(video.ground_truth_generated),
                "groundTruthCount": gt_count,
                "projectId": video.project_id,
                "projectName": video.project.name if video.project else None,
                "filePath": video.file_path,
                "duration": video.duration,
                "fps": video.fps,
                "resolution": video.resolution
            }
            video_list.append(video_data)
        
        return {
            "success": True,
            "videos": video_list,
            "total": total_count,
            "count": len(video_list),
            "offset": offset,
            "limit": limit,
            "hasMore": (offset + len(video_list)) < total_count
        }
        
    except Exception as e:
        logger.error(f"Error getting videos with ground truth: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get videos with ground truth: {str(e)}"
        )

# Integration with Annotation System
@router.post("/integrate/annotation/{annotation_id}", response_model=dict, status_code=status.HTTP_201_CREATED)
async def integrate_with_annotation(
    annotation_id: str,
    db: Session = Depends(get_db)
):
    """
    Create ground truth object from existing annotation
    """
    try:
        annotation_id = ValidationMiddleware.validate_id_parameter(annotation_id, "Annotation ID")
        
        # Get annotation
        annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        if not annotation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Annotation with ID {annotation_id} not found"
            )
        
        # Check if ground truth already exists for this annotation
        existing_gt = db.query(GroundTruthObject).filter(
            and_(
                GroundTruthObject.video_id == annotation.video_id,
                GroundTruthObject.timestamp == annotation.timestamp,
                GroundTruthObject.frame_number == annotation.frame_number
            )
        ).first()
        
        if existing_gt:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ground truth object already exists for this annotation"
            )
        
        # Create ground truth from annotation
        bounding_box = annotation.bounding_box
        gt = GroundTruthObject(
            id=str(uuid.uuid4()),
            video_id=annotation.video_id,
            frame_number=annotation.frame_number,
            timestamp=annotation.timestamp,
            class_label=annotation.vru_type,
            x=getattr(bounding_box, 'x', bounding_box.get("x", 0) if hasattr(bounding_box, 'get') else 0),
            y=getattr(bounding_box, 'y', bounding_box.get("y", 0) if hasattr(bounding_box, 'get') else 0),
            width=getattr(bounding_box, 'width', bounding_box.get("width", 0) if hasattr(bounding_box, 'get') else 0),
            height=getattr(bounding_box, 'height', bounding_box.get("height", 0) if hasattr(bounding_box, 'get') else 0),
            confidence=1.0,  # Manual annotations have full confidence
            validated=annotation.validated,
            difficult=annotation.difficult,
            created_at=datetime.utcnow()
        )
        
        # Create validation workflow
        workflow = GroundTruthValidationWorkflow(
            id=str(uuid.uuid4()),
            ground_truth_id=gt.id,
            video_id=annotation.video_id,
            generation_method=GenerationMethod.MANUAL,
            validation_status=ValidationStatus.APPROVED if annotation.validated else ValidationStatus.PENDING,
            quality_level=QualityLevel.HIGH,
            confidence_score=1.0,
            created_at=datetime.utcnow()
        )
        
        db.add(gt)
        db.add(workflow)
        db.commit()
        
        logger.info(f"Integrated annotation {annotation_id} into ground truth {gt.id}")
        
        return {
            "ground_truth_id": gt.id,
            "annotation_id": annotation_id,
            "workflow_id": workflow.id,
            "status": "integrated",
            "message": "Annotation successfully integrated into ground truth"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error integrating annotation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to integrate annotation into ground truth"
        )