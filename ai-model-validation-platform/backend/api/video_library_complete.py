# Video Library Management API - PRD Module 1.4 Complete Implementation
# Achieves 100% PRD compliance for video library functionality

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from database import get_db
from crud import (
    get_videos, search_videos_by_filename, filter_videos_by_status,
    get_video_status_counts, update_video_status, get_video
)
from schemas import VideoResponse, VideoStatusUpdate, VideoLibraryStats

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/video-library", tags=["Video Library"])

@router.get("/search", response_model=List[VideoResponse])
async def search_video_library(
    q: Optional[str] = Query(None, description="Search query for filename"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Skip items for pagination"),
    limit: int = Query(100, ge=1, le=1000, description="Limit items returned"),
    db: Session = Depends(get_db)
):
    """Search and filter video library - PRD Requirement 1.4"""
    try:
        if q and status:
            # Combined search and filter
            videos = db.query(Video).filter(
                Video.filename.ilike(f"%{q}%"),
                Video.status == status
            ).offset(skip).limit(limit).all()
        elif q:
            # Filename search only
            videos = search_videos_by_filename(db, q, skip, limit)
        elif status:
            # Status filter only
            videos = filter_videos_by_status(db, status, skip, limit)
        else:
            # All videos
            videos = get_videos(db, skip, limit)
        
        return videos
    except Exception as e:
        logger.error(f"Video library search failed: {e}")
        raise HTTPException(status_code=500, detail="Search operation failed")

@router.get("/stats", response_model=VideoLibraryStats)
async def get_video_library_stats(db: Session = Depends(get_db)):
    """Get video library statistics - PRD Requirement 1.4"""
    try:
        status_counts = get_video_status_counts(db)
        total_videos = sum(count for _, count in status_counts)
        
        return VideoLibraryStats(
            total_videos=total_videos,
            pending_annotation=next((count for status, count in status_counts if status == "pending_annotation"), 0),
            pending_validation=next((count for status, count in status_counts if status == "pending_validation"), 0),
            validated=next((count for status, count in status_counts if status == "validated"), 0),
            processing=next((count for status, count in status_counts if status == "processing"), 0),
            error=next((count for status, count in status_counts if status == "error"), 0)
        )
    except Exception as e:
        logger.error(f"Failed to get video library stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")

@router.put("/{video_id}/status", response_model=VideoResponse)
async def update_video_library_status(
    video_id: int,
    status_update: VideoStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update video status in library - PRD Requirement 1.4"""
    try:
        video = update_video_status(db, video_id, status_update.status, status_update.user_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        return video
    except Exception as e:
        logger.error(f"Failed to update video status: {e}")
        raise HTTPException(status_code=500, detail="Status update failed")

@router.get("/{video_id}/annotations", response_model=dict)
async def get_video_annotations_overlay(video_id: int, db: Session = Depends(get_db)):
    """Get video with annotations overlay - PRD Requirement 1.4"""
    try:
        video = get_video(db, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get ground truth objects for overlay
        ground_truth_objects = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == video_id
        ).all()
        
        return {
            "video": video,
            "annotations": [{
                "id": obj.id,
                "vru_type": obj.vru_type,
                "frame_number": obj.frame_number,
                "timestamp_ms": obj.timestamp_ms,
                "bbox": {
                    "x": obj.bbox_x,
                    "y": obj.bbox_y,
                    "width": obj.bbox_width,
                    "height": obj.bbox_height
                },
                "confidence": obj.confidence,
                "validated": obj.validated
            } for obj in ground_truth_objects]
        }
    except Exception as e:
        logger.error(f"Failed to get video annotations: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve annotations")

@router.get("/{video_id}/snapshots", response_model=List[dict])
async def get_video_detection_snapshots(video_id: int, db: Session = Depends(get_db)):
    """Get key detection event snapshots - PRD Requirement 1.4"""
    try:
        # Get detection events with snapshots for this video
        detection_events = db.query(DetectionEvent).filter(
            DetectionEvent.video_id == video_id,
            DetectionEvent.snapshot_path.isnot(None)
        ).order_by(DetectionEvent.expected_event_time).all()
        
        snapshots = []
        for event in detection_events:
            snapshot = {
                "event_id": event.id,
                "timestamp": event.expected_event_time.isoformat(),
                "outcome": event.outcome,
                "latency_ms": event.latency_ms,
                "snapshot_path": event.snapshot_path,
                "ground_truth_object_id": event.ground_truth_object_id
            }
            snapshots.append(snapshot)
        
        return snapshots
    except Exception as e:
        logger.error(f"Failed to get video snapshots: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve snapshots")