"""
Ground Truth Router - REST API Endpoints
Handles ground truth video availability and annotation data
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import json
import csv
from io import StringIO

from database import get_db
from models import Video, GroundTruthObject, DetectionEvent
from schemas import VideoFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ground-truth", tags=["ground-truth"])

@router.get("/videos/available", response_model=List[VideoFile])
async def get_available_videos(
    db: Session = Depends(get_db),
    project_id: Optional[str] = None,
    min_detections: int = 1
):
    """
    Get all videos that have ground truth annotations available
    
    This endpoint returns videos that have been processed and contain ground truth objects,
    making them suitable for use in the Datasets page for annotation and validation work.
    
    Args:
        project_id: Optional filter by project ID
        min_detections: Minimum number of ground truth detections required (default: 1)
    
    Returns:
        List of VideoFile objects with ground truth data available
    """
    try:
        logger.info(f"🔍 Fetching videos with ground truth data (project_id={project_id}, min_detections={min_detections})")
        
        # Build comprehensive query for videos with ground truth objects OR detection events
        from sqlalchemy import func, or_, exists
        
        # Apply project filter if specified
        base_query = db.query(Video).filter(
            Video.status.in_(["validated", "completed", "processing", "uploaded"])
        )
        
        if project_id:
            # Check both direct assignment and VideoProjectLink relationships
            from models import VideoProjectLink
            base_query = base_query.filter(
                or_(
                    Video.project_id == project_id,
                    Video.id.in_(
                        db.query(VideoProjectLink.video_id).filter(
                            VideoProjectLink.project_id == project_id
                        )
                    )
                )
            )
        
        # Count ground truth objects per video
        # Issue #6: Exclude soft-deleted records
        gt_counts = db.query(
            GroundTruthObject.video_id,
            func.count(GroundTruthObject.id).label('gt_count')
        ).filter(
            GroundTruthObject.deleted_at.is_(None)  # Only count active records
        ).group_by(GroundTruthObject.video_id).subquery()
        
        # Count detection events per video  
        de_counts = db.query(
            DetectionEvent.video_id,
            func.count(DetectionEvent.id).label('de_count')
        ).group_by(DetectionEvent.video_id).subquery()
        
        # Count annotations per video (from annotations table)
        from models import Annotation
        ann_counts = db.query(
            Annotation.video_id,
            func.count(Annotation.id).label('ann_count')
        ).group_by(Annotation.video_id).subquery()
        
        # Build query that includes videos with ground truth, detection events, OR annotations
        # and calculates total detection count
        query = base_query.outerjoin(
            gt_counts, Video.id == gt_counts.c.video_id
        ).outerjoin(
            de_counts, Video.id == de_counts.c.video_id
        ).outerjoin(
            ann_counts, Video.id == ann_counts.c.video_id
        ).filter(
            or_(
                gt_counts.c.gt_count != None,
                de_counts.c.de_count != None,
                ann_counts.c.ann_count != None
            )
        )
        
        # Filter by minimum detections using WHERE clause instead of HAVING
        # This avoids the SQLite HAVING error on non-aggregate queries
        if min_detections > 0:
            query = query.filter(
                (func.coalesce(gt_counts.c.gt_count, 0) + func.coalesce(de_counts.c.de_count, 0) + func.coalesce(ann_counts.c.ann_count, 0)) >= min_detections
            )
        
        # Execute query and get distinct videos
        videos = query.distinct().all()
        
        logger.info(f"✅ Found {len(videos)} videos with ground truth data")
        
        # Convert to VideoFile response format
        video_files = []
        for video in videos:
            # Get total ground truth count for this video from all sources
            # Issue #6: Exclude soft-deleted records
            gt_count = db.query(func.count(GroundTruthObject.id)).filter(
                GroundTruthObject.video_id == video.id,
                GroundTruthObject.deleted_at.is_(None)  # Only count active records
            ).scalar() or 0
            
            ann_count = db.query(func.count(Annotation.id)).filter(
                Annotation.video_id == video.id
            ).scalar() or 0
            
            total_gt_count = gt_count + ann_count
            
            video_file = VideoFile(
                id=video.id,
                filename=video.filename,
                projectId=None,  # Videos are now project-independent
                duration=video.duration,
                size=video.file_size,
                status=video.status,
                createdAt=video.created_at.isoformat() if video.created_at else None,
                # Additional ground truth specific metadata
                ground_truth_count=total_gt_count,
                ground_truth_generated=video.ground_truth_generated,
                validation_status=video.validation_status
            )
            video_files.append(video_file)
        
        # Sort by creation date (newest first)
        video_files.sort(key=lambda x: x.created_at or "", reverse=True)
        
        logger.info(f"📋 Returning {len(video_files)} videos with ground truth annotations")
        return video_files
        
    except Exception as e:
        logger.error(f"❌ Error fetching videos with ground truth: {str(e)}")
        logger.exception("Full error details:")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch videos with ground truth data: {str(e)}"
        )

@router.get("/videos/{video_id}/stats")
async def get_video_ground_truth_stats(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed ground truth statistics for a specific video
    
    Args:
        video_id: The video ID to get stats for
        
    Returns:
        Detailed ground truth statistics and metadata
    """
    try:
        # Check if video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get ground truth statistics
        # Issue #6: Exclude soft-deleted records
        from sqlalchemy import func
        stats = db.query(
            func.count(GroundTruthObject.id).label('total_detections'),
            func.count(func.distinct(GroundTruthObject.class_label)).label('unique_classes'),
            func.avg(GroundTruthObject.confidence).label('avg_confidence'),
            func.min(GroundTruthObject.timestamp).label('first_detection'),
            func.max(GroundTruthObject.timestamp).label('last_detection')
        ).filter(
            GroundTruthObject.video_id == video_id,
            GroundTruthObject.deleted_at.is_(None)  # Only include active records
        ).first()
        
        # Get class distribution
        # Issue #6: Exclude soft-deleted records
        class_distribution = db.query(
            GroundTruthObject.class_label,
            func.count(GroundTruthObject.id).label('count')
        ).filter(
            GroundTruthObject.video_id == video_id,
            GroundTruthObject.deleted_at.is_(None)  # Only include active records
        ).group_by(GroundTruthObject.class_label).all()
        
        return {
            "video_id": video_id,
            "filename": video.filename,
            "ground_truth_generated": video.ground_truth_generated,
            "validation_status": video.validation_status,
            "status": video.status,
            "statistics": {
                "total_detections": stats.total_detections or 0,
                "unique_classes": stats.unique_classes or 0,
                "average_confidence": float(stats.avg_confidence or 0),
                "first_detection_time": float(stats.first_detection or 0),
                "last_detection_time": float(stats.last_detection or 0),
                "temporal_coverage": float((stats.last_detection or 0) - (stats.first_detection or 0))
            },
            "class_distribution": {
                row.class_label: row.count for row in class_distribution
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching ground truth stats for video {video_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch ground truth statistics: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """Health check endpoint for ground truth router"""
    return {
        "status": "healthy",
        "service": "ground-truth-router",
        "endpoints": [
            "/api/ground-truth/videos/available",
            "/api/ground-truth/videos/{video_id}/stats",
            "/api/ground-truth/health",
            "/api/ground-truth",
            "/api/videos/{video_id}/ground-truth/validate",
            "/api/annotations/{annotation_id}"
        ]
    }

@router.post("")
async def upload_ground_truth(
    video_id: str = Query(..., description="Video ID to upload ground truth for"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload ground truth objects for a video.

    Accepts JSON or CSV files with ground truth annotations.
    Creates GroundTruthObject records linked to the specified video.

    Args:
        video_id: The video ID to associate ground truth with
        file: JSON or CSV file with ground truth data

    Returns:
        Upload result with objects created count
    """
    try:
        logger.info(f"📤 Uploading ground truth for video: {video_id}, filename: {file.filename}")

        # Validate video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error(f"❌ Video not found: {video_id}")
            raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

        # Parse file based on extension
        content = await file.read()

        if file.filename.endswith('.json'):
            try:
                gt_data = json.loads(content.decode('utf-8'))
                gt_objects = gt_data.get('objects', gt_data if isinstance(gt_data, list) else [])
            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid JSON file: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Invalid JSON file: {str(e)}")
        elif file.filename.endswith('.csv'):
            try:
                csv_data = StringIO(content.decode('utf-8'))
                reader = csv.DictReader(csv_data)
                gt_objects = list(reader)
            except Exception as e:
                logger.error(f"❌ Invalid CSV file: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Invalid CSV file: {str(e)}")
        else:
            logger.error(f"❌ Unsupported file format: {file.filename}")
            raise HTTPException(status_code=400, detail="File must be .json or .csv")

        # Create GroundTruthObject records
        created_objects = []
        skipped_count = 0

        for obj in gt_objects:
            # Extract timestamp (flexible format)
            timestamp = None
            if 'video_time_seconds' in obj:
                timestamp = float(obj['video_time_seconds'])
            elif 'timestamp' in obj:
                timestamp = float(obj['timestamp'])
            elif 'frame_number' in obj and video.fps:
                timestamp = float(obj['frame_number']) / video.fps

            if timestamp is None:
                logger.warning(f"⚠️  Skipping object without timestamp: {obj}")
                skipped_count += 1
                continue

            # Extract bounding box coordinates (support multiple field name formats)
            x = float(obj.get('bbox_x', obj.get('x', 0)))
            y = float(obj.get('bbox_y', obj.get('y', 0)))
            width = float(obj.get('bbox_width', obj.get('width', 0)))
            height = float(obj.get('bbox_height', obj.get('height', 0)))

            # Create GT object using exact model field names
            gt_obj = GroundTruthObject(
                video_id=video_id,
                timestamp=timestamp,
                class_label=obj.get('class_label', obj.get('vru_type', obj.get('class', 'unknown'))),
                frame_number=int(obj.get('frame_number', 0)) if obj.get('frame_number') else None,
                tracking_id=obj.get('tracking_id'),
                confidence=float(obj.get('confidence', 1.0)),
                x=x,
                y=y,
                width=width,
                height=height,
                validated=bool(obj.get('validated', False)),
                difficult=bool(obj.get('difficult', False))
            )

            db.add(gt_obj)
            created_objects.append(gt_obj)

        # Commit all objects
        db.commit()

        logger.info(f"✅ Created {len(created_objects)} ground truth objects for video {video_id}")
        if skipped_count > 0:
            logger.warning(f"⚠️  Skipped {skipped_count} objects without timestamps")

        return {
            'video_id': video_id,
            'objects_created': len(created_objects),
            'objects_skipped': skipped_count,
            'filename': file.filename,
            'status': 'success'
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error uploading ground truth: {str(e)}")
        logger.exception("Full error details:")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload ground truth: {str(e)}"
        )

@router.get("/videos/{video_id}/ground-truth/validate")
async def validate_ground_truth(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Validate ground truth availability for a video.

    Checks if ground truth data exists for the specified video.
    Returns count of active (non-soft-deleted) ground truth objects.

    Args:
        video_id: The video ID to validate

    Returns:
        Validation result with ground truth count and status
    """
    try:
        # Check if video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error(f"❌ Video not found for validation: {video_id}")
            raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

        # Count GT objects (excluding soft-deleted)
        from sqlalchemy import func
        gt_count = db.query(func.count(GroundTruthObject.id)).filter(
            GroundTruthObject.video_id == video_id,
            GroundTruthObject.deleted_at.is_(None)  # Only count active records
        ).scalar() or 0

        logger.info(f"✅ Ground truth validation for video {video_id}: {gt_count} objects")

        return {
            'video_id': video_id,
            'ground_truth_count': gt_count,
            'has_ground_truth': gt_count > 0,
            'status': 'valid' if gt_count > 0 else 'no_ground_truth'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error validating ground truth for video {video_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate ground truth: {str(e)}"
        )

@router.delete("/annotations/{annotation_id}")
async def delete_ground_truth_annotation(
    annotation_id: str,
    db: Session = Depends(get_db),
    user_id: str = "anonymous"  # TODO: Get from auth context
):
    """
    Soft delete a ground truth annotation/object - Issue #6

    This performs a soft delete by setting deleted_at timestamp.
    The record remains in the database but is excluded from queries.
    """
    try:
        # Use soft delete service helper
        from services.ground_truth_service import soft_delete_ground_truth

        result = soft_delete_ground_truth(
            db=db,
            ground_truth_id=annotation_id,
            deleted_by=user_id
        )

        if result["success"]:
            logger.info(f"Soft deleted ground truth object: {annotation_id} by user: {user_id}")
            return result
        else:
            logger.warning(f"Failed to soft delete annotation {annotation_id}: {result.get('error')}")
            raise HTTPException(status_code=400, detail=result.get("error", "Delete failed"))

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error soft deleting annotation {annotation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))