"""
Ground Truth Router - REST API Endpoints
Handles ground truth video availability and annotation data
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from database import get_db
from models import Video, GroundTruthObject
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
        
        # Build base query for videos with ground truth objects
        # More inclusive query - any video that has ground truth objects, regardless of flag
        query = db.query(Video).join(
            GroundTruthObject, Video.id == GroundTruthObject.video_id
        ).filter(
            Video.status.in_(["validated", "completed", "processing", "uploaded"])  # Include more valid states
        )
        
        # Apply project filter if specified
        if project_id:
            query = query.filter(Video.project_id == project_id)
        
        # Group by video and count ground truth objects
        from sqlalchemy import func
        subquery = db.query(
            GroundTruthObject.video_id,
            func.count(GroundTruthObject.id).label('gt_count')
        ).group_by(GroundTruthObject.video_id).subquery()
        
        # Join with the count subquery and filter by minimum detections
        query = query.join(
            subquery, Video.id == subquery.c.video_id
        ).filter(
            subquery.c.gt_count >= min_detections
        )
        
        # Execute query and get distinct videos
        videos = query.distinct().all()
        
        logger.info(f"✅ Found {len(videos)} videos with ground truth data")
        
        # Convert to VideoFile response format
        video_files = []
        for video in videos:
            # Get ground truth count for this video
            gt_count = db.query(func.count(GroundTruthObject.id)).filter(
                GroundTruthObject.video_id == video.id
            ).scalar()
            
            video_file = VideoFile(
                id=video.id,
                filename=video.filename,
                projectId=video.project_id,
                duration=video.duration,
                size=video.file_size,
                status=video.status,
                createdAt=video.created_at.isoformat() if video.created_at else None,
                # Additional ground truth specific metadata
                ground_truth_count=gt_count,
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
            "/api/ground-truth/health"
        ]
    }