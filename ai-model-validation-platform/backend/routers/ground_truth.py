"""
Ground Truth Router - REST API Endpoints
Handles ground truth video availability and annotation data
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

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
        gt_counts = db.query(
            GroundTruthObject.video_id,
            func.count(GroundTruthObject.id).label('gt_count')
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
            gt_count = db.query(func.count(GroundTruthObject.id)).filter(
                GroundTruthObject.video_id == video.id
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
        from sqlalchemy import func
        stats = db.query(
            func.count(GroundTruthObject.id).label('total_detections'),
            func.count(func.distinct(GroundTruthObject.class_label)).label('unique_classes'),
            func.avg(GroundTruthObject.confidence).label('avg_confidence'),
            func.min(GroundTruthObject.timestamp).label('first_detection'),
            func.max(GroundTruthObject.timestamp).label('last_detection')
        ).filter(GroundTruthObject.video_id == video_id).first()
        
        # Get class distribution
        class_distribution = db.query(
            GroundTruthObject.class_label,
            func.count(GroundTruthObject.id).label('count')
        ).filter(
            GroundTruthObject.video_id == video_id
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
            "/api/annotations/{annotation_id}"
        ]
    }

@router.delete("/annotations/{annotation_id}")
async def delete_ground_truth_annotation(
    annotation_id: str,
    db: Session = Depends(get_db)
):
    """Delete a ground truth annotation/object"""
    try:
        # Check if it's a ground truth object
        ground_truth_obj = db.query(GroundTruthObject).filter(
            GroundTruthObject.id == annotation_id
        ).first()
        
        if ground_truth_obj:
            db.delete(ground_truth_obj)
            db.commit()
            logger.info(f"Deleted ground truth object: {annotation_id}")
            return {"success": True, "message": "Ground truth object deleted successfully"}
        
        # If not found, return 404
        logger.warning(f"Annotation not found: {annotation_id}")
        raise HTTPException(status_code=404, detail="Annotation not found")
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting annotation {annotation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))