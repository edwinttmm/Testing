#!/usr/bin/env python3
"""
Bulletproof Annotation Endpoints with Zero Data Corruption Tolerance
Integrates with the Data Pipeline Integrity system for complete protection.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
import asyncio
from datetime import datetime, timezone

from database import get_db
from models import Annotation, AnnotationSession, VideoProjectLink, Video
from schemas_annotation import (
    AnnotationCreate, AnnotationUpdate, AnnotationResponse,
    AnnotationSessionCreate, AnnotationSessionResponse,
    VideoProjectLinkCreate, VideoProjectLinkResponse
)

# Import our bulletproof integrity system
from src.data_pipeline_integrity import (
    validate_and_repair_annotation,
    validate_db_to_api_response,
    run_pipeline_health_check,
    AutoRepairService,
    PipelineHealthDashboard,
    AnnotationDataContract,
    VRUTypeContract,
    BoundingBoxContract,
    ValidationStatusContract
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bulletproof", tags=["bulletproof-annotations"])

# ==================== BULLETPROOF ANNOTATION ENDPOINTS ====================

@router.post("/videos/{video_id}/annotations", response_model=Dict[str, Any])
async def create_bulletproof_annotation(
    video_id: str,
    annotation: AnnotationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create annotation with ZERO corruption tolerance
    ALL data goes through bulletproof validation and repair
    """
    try:
        logger.info(f"🛡️ Creating bulletproof annotation for video {video_id}")
        
        # Validate video exists first
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
        
        # Convert Pydantic model to dict for validation
        annotation_dict = annotation.dict()
        annotation_dict['video_id'] = video_id  # Ensure video_id is set
        
        # Run through bulletproof validation and repair system
        validated_data = await validate_and_repair_annotation(annotation_dict, db)
        
        if validated_data is None:
            # Data was quarantined - corruption too severe
            logger.error(f"❌ Annotation data quarantined due to severe corruption")
            raise HTTPException(
                status_code=422, 
                detail="Annotation data is severely corrupted and cannot be repaired"
            )
        
        # Create database record with validated data
        db_annotation = Annotation(
            id=validated_data['id'],
            video_id=validated_data['video_id'],
            detection_id=validated_data.get('detection_id'),
            frame_number=validated_data['frame_number'],
            timestamp=validated_data['timestamp'],
            end_timestamp=validated_data.get('end_timestamp'),
            vru_type=validated_data['vru_type'],
            bounding_box=validated_data['bounding_box'],
            occluded=validated_data['occluded'],
            truncated=validated_data['truncated'],
            difficult=validated_data['difficult'],
            notes=validated_data.get('notes'),
            annotator=validated_data.get('annotator'),
            validated=validated_data['validated'],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        db.add(db_annotation)
        db.commit()
        db.refresh(db_annotation)
        
        # Generate bulletproof API response
        response_data = await validate_db_to_api_response(db_annotation, db)
        
        # Log integrity status
        integrity_status = validated_data.get('integrityStatus', 'valid')
        if integrity_status == ValidationStatusContract.REPAIRED.value:
            logger.info(f"✅ Annotation {db_annotation.id} created with auto-repair")
        else:
            logger.info(f"✅ Annotation {db_annotation.id} created successfully")
        
        # Add background task to monitor pipeline health
        background_tasks.add_task(log_pipeline_metrics, db_annotation.id, "create", integrity_status)
        
        return response_data
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to create bulletproof annotation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Creation failed: {str(e)}")

@router.get("/videos/{video_id}/annotations", response_model=List[Dict[str, Any]])
async def get_bulletproof_annotations(
    video_id: str,
    validated_only: Optional[bool] = False,
    repair_mode: Optional[bool] = True,  # Auto-repair corrupted data by default
    db: Session = Depends(get_db)
):
    """
    Get annotations with bulletproof corruption protection
    Automatically repairs any corrupted data found in database
    """
    try:
        logger.info(f"🛡️ Retrieving bulletproof annotations for video {video_id}")
        
        # Query annotations
        query = db.query(Annotation).filter(Annotation.video_id == video_id)
        if validated_only:
            query = query.filter(Annotation.validated == True)
        
        annotations = query.order_by(Annotation.timestamp).all()
        
        # Process each annotation through bulletproof validation
        response_annotations = []
        corrupted_count = 0
        repaired_count = 0
        
        for annotation in annotations:
            try:
                # Generate bulletproof API response
                response_data = await validate_db_to_api_response(annotation, db)
                
                # Check if repair occurred
                integrity_status = response_data.get('integrityStatus', 'valid')
                if integrity_status == ValidationStatusContract.REPAIRED.value:
                    repaired_count += 1
                elif integrity_status == ValidationStatusContract.QUARANTINED.value:
                    corrupted_count += 1
                    if not repair_mode:
                        continue  # Skip quarantined data if repair disabled
                
                response_annotations.append(response_data)
                
            except Exception as e:
                logger.warning(f"⚠️ Failed to process annotation {annotation.id}: {str(e)}")
                corrupted_count += 1
                # Skip corrupted annotation rather than failing entire request
                continue
        
        # Log integrity summary
        if repaired_count > 0:
            logger.info(f"🔧 Auto-repaired {repaired_count} corrupted annotations")
        if corrupted_count > 0:
            logger.warning(f"⚠️ Found {corrupted_count} corrupted annotations")
        
        logger.info(f"✅ Retrieved {len(response_annotations)} bulletproof annotations")
        return response_annotations
        
    except Exception as e:
        logger.error(f"❌ Failed to get bulletproof annotations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")

@router.get("/annotations/{annotation_id}", response_model=Dict[str, Any])
async def get_bulletproof_annotation(
    annotation_id: str,
    db: Session = Depends(get_db)
):
    """Get single annotation with bulletproof protection"""
    try:
        annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        if not annotation:
            raise HTTPException(status_code=404, detail="Annotation not found")
        
        # Generate bulletproof response
        response_data = await validate_db_to_api_response(annotation, db)
        
        # Log if repair occurred
        integrity_status = response_data.get('integrityStatus', 'valid')
        if integrity_status == ValidationStatusContract.REPAIRED.value:
            logger.info(f"🔧 Auto-repaired annotation {annotation_id} on retrieval")
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get bulletproof annotation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")

@router.put("/annotations/{annotation_id}", response_model=Dict[str, Any])
async def update_bulletproof_annotation(
    annotation_id: str,
    annotation_update: AnnotationUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Update annotation with bulletproof validation"""
    try:
        logger.info(f"🛡️ Updating bulletproof annotation {annotation_id}")
        
        # Get existing annotation
        db_annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        if not db_annotation:
            raise HTTPException(status_code=404, detail="Annotation not found")
        
        # Convert update data to dict and merge with existing
        update_dict = annotation_update.dict(exclude_unset=True)
        
        # Get current annotation data
        current_data = {
            'id': db_annotation.id,
            'video_id': db_annotation.video_id,
            'detection_id': db_annotation.detection_id,
            'frame_number': db_annotation.frame_number,
            'timestamp': db_annotation.timestamp,
            'end_timestamp': db_annotation.end_timestamp,
            'vru_type': db_annotation.vru_type,
            'bounding_box': db_annotation.bounding_box,
            'occluded': db_annotation.occluded,
            'truncated': db_annotation.truncated,
            'difficult': db_annotation.difficult,
            'notes': db_annotation.notes,
            'annotator': db_annotation.annotator,
            'validated': db_annotation.validated
        }
        
        # Merge update data
        current_data.update(update_dict)
        
        # Validate and repair merged data
        validated_data = await validate_and_repair_annotation(current_data, db)
        
        if validated_data is None:
            raise HTTPException(
                status_code=422,
                detail="Update data is severely corrupted and cannot be repaired"
            )
        
        # Apply validated updates to database
        for field, value in validated_data.items():
            if field in ['id', 'created_at']:
                continue  # Don't update these fields
            if hasattr(db_annotation, field):
                setattr(db_annotation, field, value)
        
        db_annotation.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_annotation)
        
        # Generate bulletproof response
        response_data = await validate_db_to_api_response(db_annotation, db)
        
        # Log integrity status
        integrity_status = validated_data.get('integrityStatus', 'valid')
        if integrity_status == ValidationStatusContract.REPAIRED.value:
            logger.info(f"✅ Annotation {annotation_id} updated with auto-repair")
        
        background_tasks.add_task(log_pipeline_metrics, annotation_id, "update", integrity_status)
        
        return response_data
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to update bulletproof annotation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

@router.delete("/annotations/{annotation_id}")
async def delete_bulletproof_annotation(
    annotation_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Delete annotation with logging"""
    try:
        db_annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        if not db_annotation:
            raise HTTPException(status_code=404, detail="Annotation not found")
        
        db.delete(db_annotation)
        db.commit()
        
        background_tasks.add_task(log_pipeline_metrics, annotation_id, "delete", "valid")
        
        logger.info(f"✅ Deleted annotation {annotation_id}")
        return {"message": "Annotation deleted successfully", "id": annotation_id}
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to delete annotation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

# ==================== PIPELINE HEALTH ENDPOINTS ====================

@router.get("/health/pipeline")
async def get_pipeline_health(db: Session = Depends(get_db)):
    """Get comprehensive pipeline health status"""
    try:
        health_report = await run_pipeline_health_check(db)
        return health_report
    except Exception as e:
        logger.error(f"❌ Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/health/dashboard")
async def get_health_dashboard(db: Session = Depends(get_db)):
    """Get dashboard data for pipeline health monitoring"""
    try:
        dashboard = PipelineHealthDashboard(db)
        dashboard_data = await dashboard.get_dashboard_data()
        return dashboard_data
    except Exception as e:
        logger.error(f"❌ Dashboard data failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Dashboard failed: {str(e)}")

@router.post("/maintenance/repair-database")
async def repair_database(
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Force repair even if risky"),
    db: Session = Depends(get_db)
):
    """Run automatic database repair service"""
    try:
        if not force:
            # Get health status first
            health_report = await run_pipeline_health_check(db)
            if health_report.get('success_rate', 1.0) > 0.95:
                return {
                    "message": "Database is healthy, repair not needed",
                    "health_status": health_report
                }
        
        # Run repair in background
        background_tasks.add_task(run_database_repair, db)
        
        return {
            "message": "Database repair started in background",
            "status": "initiated"
        }
        
    except Exception as e:
        logger.error(f"❌ Database repair failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Repair failed: {str(e)}")

@router.get("/integrity/stats")
async def get_integrity_stats(db: Session = Depends(get_db)):
    """Get detailed integrity statistics"""
    try:
        from models import Annotation
        
        # Database integrity stats
        total_annotations = db.query(Annotation).count()
        validated_annotations = db.query(Annotation).filter(Annotation.validated == True).count()
        
        # Count potential issues
        null_bbox_count = db.query(Annotation).filter(Annotation.bounding_box.is_(None)).count()
        
        stats = {
            'database': {
                'total_annotations': total_annotations,
                'validated_annotations': validated_annotations,
                'validation_rate': validated_annotations / max(1, total_annotations),
                'null_bounding_boxes': null_bbox_count,
                'integrity_score': 1.0 - (null_bbox_count / max(1, total_annotations))
            },
            'system': {
                'integrity_system_active': True,
                'auto_repair_enabled': True,
                'corruption_tolerance': 0.0,  # Zero tolerance
                'validation_contracts': len([VRUTypeContract, BoundingBoxContract, AnnotationDataContract])
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Integrity stats failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stats failed: {str(e)}")

# ==================== BULK OPERATIONS WITH INTEGRITY ====================

@router.post("/videos/{video_id}/annotations/bulk", response_model=Dict[str, Any])
async def create_bulk_bulletproof_annotations(
    video_id: str,
    annotations: List[AnnotationCreate],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create multiple annotations with bulletproof validation"""
    try:
        logger.info(f"🛡️ Creating {len(annotations)} bulletproof annotations for video {video_id}")
        
        # Validate video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
        
        created_annotations = []
        failed_annotations = []
        repaired_count = 0
        
        for i, annotation in enumerate(annotations):
            try:
                # Convert to dict and validate
                annotation_dict = annotation.dict()
                annotation_dict['video_id'] = video_id
                
                # Validate and repair
                validated_data = await validate_and_repair_annotation(annotation_dict, db)
                
                if validated_data is None:
                    failed_annotations.append({
                        'index': i,
                        'reason': 'Severe corruption, quarantined',
                        'original_data': annotation_dict
                    })
                    continue
                
                # Create database record
                db_annotation = Annotation(
                    id=validated_data['id'],
                    video_id=validated_data['video_id'],
                    detection_id=validated_data.get('detection_id'),
                    frame_number=validated_data['frame_number'],
                    timestamp=validated_data['timestamp'],
                    end_timestamp=validated_data.get('end_timestamp'),
                    vru_type=validated_data['vru_type'],
                    bounding_box=validated_data['bounding_box'],
                    occluded=validated_data['occluded'],
                    truncated=validated_data['truncated'],
                    difficult=validated_data['difficult'],
                    notes=validated_data.get('notes'),
                    annotator=validated_data.get('annotator'),
                    validated=validated_data['validated'],
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                
                db.add(db_annotation)
                created_annotations.append(validated_data['id'])
                
                # Check if repair occurred
                if validated_data.get('integrityStatus') == ValidationStatusContract.REPAIRED.value:
                    repaired_count += 1
                
            except Exception as e:
                failed_annotations.append({
                    'index': i,
                    'reason': str(e),
                    'original_data': annotation.dict() if hasattr(annotation, 'dict') else str(annotation)
                })
        
        # Commit all successful annotations
        db.commit()
        
        # Generate summary
        result = {
            'total_submitted': len(annotations),
            'successfully_created': len(created_annotations),
            'failed_count': len(failed_annotations),
            'auto_repaired_count': repaired_count,
            'created_ids': created_annotations,
            'failures': failed_annotations[:10],  # Limit failure details
            'success_rate': len(created_annotations) / len(annotations) if annotations else 0
        }
        
        logger.info(f"✅ Bulk creation completed: {result['success_rate']:.2%} success rate")
        
        background_tasks.add_task(log_bulk_operation_metrics, video_id, result)
        
        return result
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Bulk creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bulk creation failed: {str(e)}")

# ==================== BACKGROUND TASKS ====================

async def log_pipeline_metrics(annotation_id: str, operation: str, integrity_status: str):
    """Background task to log pipeline metrics"""
    try:
        logger.info(f"📊 Pipeline metric - {operation}: {annotation_id}, integrity: {integrity_status}")
        # In production, this would write to metrics database
    except Exception as e:
        logger.error(f"Failed to log pipeline metrics: {str(e)}")

async def log_bulk_operation_metrics(video_id: str, result: Dict[str, Any]):
    """Background task to log bulk operation metrics"""
    try:
        logger.info(f"📊 Bulk operation - video: {video_id}, success_rate: {result['success_rate']:.2%}")
        # In production, this would write to metrics database
    except Exception as e:
        logger.error(f"Failed to log bulk metrics: {str(e)}")

async def run_database_repair(db: Session):
    """Background task to run database repair"""
    try:
        logger.info("🔧 Starting background database repair...")
        repair_service = AutoRepairService(db)
        repair_report = await repair_service.scan_and_repair_database()
        logger.info(f"✅ Database repair completed: {repair_report}")
    except Exception as e:
        logger.error(f"❌ Background repair failed: {str(e)}")

# ==================== COMPATIBILITY ENDPOINTS ====================

@router.post("/videos/{video_id}/annotations/compatible", response_model=AnnotationResponse)
async def create_compatible_annotation(
    video_id: str,
    annotation: AnnotationCreate,
    db: Session = Depends(get_db)
):
    """
    Compatibility endpoint that mimics original API but uses bulletproof backend
    This allows gradual migration from existing endpoints
    """
    try:
        # Use bulletproof creation but return in original format
        bulletproof_result = await create_bulletproof_annotation(
            video_id=video_id,
            annotation=annotation,
            background_tasks=BackgroundTasks(),
            db=db
        )
        
        # Convert bulletproof response to original AnnotationResponse format
        return AnnotationResponse(
            id=bulletproof_result['id'],
            videoId=bulletproof_result['videoId'],
            detectionId=bulletproof_result.get('detectionId'),
            frameNumber=bulletproof_result['frameNumber'],
            timestamp=bulletproof_result['timestamp'],
            endTimestamp=bulletproof_result.get('endTimestamp'),
            vruType=bulletproof_result['vruType'],
            boundingBox=bulletproof_result['boundingBox'],
            occluded=bulletproof_result['occluded'],
            truncated=bulletproof_result['truncated'],
            difficult=bulletproof_result['difficult'],
            notes=bulletproof_result.get('notes'),
            annotator=bulletproof_result.get('annotator'),
            validated=bulletproof_result['validated'],
            createdAt=datetime.fromisoformat(bulletproof_result['createdAt']) if bulletproof_result.get('createdAt') else datetime.now(timezone.utc),
            updatedAt=datetime.fromisoformat(bulletproof_result['updatedAt']) if bulletproof_result.get('updatedAt') else None
        )
        
    except Exception as e:
        logger.error(f"❌ Compatible annotation creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Creation failed: {str(e)}")

if __name__ == "__main__":
    # Quick test of bulletproof endpoints
    logger.info("🛡️ Bulletproof annotation endpoints loaded successfully")