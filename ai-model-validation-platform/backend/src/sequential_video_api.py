#!/usr/bin/env python3
"""
Sequential Video Processing API Endpoints
Provides the ONE-BUTTON START ALL VIDEOS functionality
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from .sequential_video_processor import sequential_processor
from database import get_db, SessionLocal
from sqlalchemy.orm import Session
from models import Project, Video

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/sequential-video", tags=["Sequential Video Processing"])

# Request/Response Models
class StartAllVideosRequest(BaseModel):
    """Request to start all videos sequentially"""
    project_id: str = Field(..., description="Project ID (e.g., 66f9c296-ee1e-4e81-b0ba-96d03fdc8c90)")
    video_ids: Optional[List[str]] = Field(None, description="Optional specific video IDs, otherwise processes all project videos")
    session_name: Optional[str] = Field(None, description="Optional custom session name")

class VideoProcessingStatus(BaseModel):
    """Video processing status response"""
    success: bool
    session_id: str
    status: str
    progress: float
    current_video_index: int
    total_videos: int
    current_video: str
    elapsed_time_seconds: float
    processed_videos: int
    remaining_videos: int
    project_id: str

class ProcessingResults(BaseModel):
    """Comprehensive processing results"""
    success: bool
    session_id: str
    session_name: str
    project_id: str
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    statistics: Dict[str, Any]
    test_results: List[Dict[str, Any]]
    detection_events: List[Dict[str, Any]]
    detection_comparisons: List[Dict[str, Any]]

@router.post("/start-all-videos", response_model=Dict[str, Any])
async def start_all_videos_sequential(
    request: StartAllVideosRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    🚀 ONE BUTTON: START ALL VIDEOS SEQUENTIALLY
    
    This is THE endpoint the user wants:
    - Click one button
    - ALL videos process automatically (video1 → video2 → video3)
    - Results are stored for each video
    - Project-based session (NO random sessions)
    """
    try:
        logger.info(f"Starting sequential processing for project {request.project_id}")
        
        # Validate project exists and has videos
        project = db.query(Project).filter(Project.id == request.project_id).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {request.project_id} not found"
            )
        
        # Get videos to process
        video_query = db.query(Video).filter(Video.project_id == request.project_id)
        if request.video_ids:
            video_query = video_query.filter(Video.id.in_(request.video_ids))
        
        videos = video_query.all()
        if not videos:
            raise HTTPException(
                status_code=404,
                detail="No videos found for processing in this project"
            )
        
        # Start sequential processing
        result = await sequential_processor.start_all_videos_sequential(
            project_id=request.project_id,
            video_ids=request.video_ids,
            session_name=request.session_name
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Failed to start sequential processing")
            )
        
        logger.info(f"Sequential processing started successfully: session {result['session_id']}")
        
        return {
            "success": True,
            "message": "🎥 Sequential video processing started successfully!",
            "session_id": result["session_id"],
            "project_id": request.project_id,
            "videos_to_process": result["videos_to_process"],
            "processing_order": result["processing_order"],
            "status": "processing_started",
            "instructions": "Videos will process automatically one after another. Check status endpoint for progress."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting sequential processing: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/sessions/{session_id}/status", response_model=VideoProcessingStatus)
async def get_processing_status(session_id: str):
    """
    Get current status of sequential video processing
    Shows progress, current video, and completion status
    """
    try:
        result = sequential_processor.get_session_status(session_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=404,
                detail=result.get("error", "Session not found")
            )
        
        return VideoProcessingStatus(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting processing status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving status: {str(e)}"
        )

@router.get("/sessions/{session_id}/results", response_model=ProcessingResults)
async def get_processing_results(session_id: str):
    """
    Get comprehensive results from completed sequential processing
    This populates the RESULTS PAGE with all detection data
    """
    try:
        result = sequential_processor.get_session_results(session_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=404,
                detail=result.get("error", "Session results not found")
            )
        
        return ProcessingResults(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting processing results: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving results: {str(e)}"
        )

@router.get("/projects/{project_id}/videos", response_model=List[Dict[str, Any]])
async def get_project_videos(project_id: str, db: Session = Depends(get_db)):
    """
    Get all videos available for processing in a project
    Helps frontend show which videos will be processed
    """
    try:
        # Validate project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        # Get all videos for project
        videos = db.query(Video).filter(Video.project_id == project_id).all()
        
        formatted_videos = [
            {
                "id": video.id,
                "filename": video.filename,
                "status": video.status,
                "processing_status": video.processing_status,
                "duration": video.duration,
                "created_at": video.created_at.isoformat() if video.created_at else None,
                "file_size": getattr(video, 'file_size', None)
            }
            for video in videos
        ]
        
        return formatted_videos
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project videos: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving project videos: {str(e)}"
        )

@router.get("/projects/{project_id}/sessions", response_model=List[Dict[str, Any]])
async def get_project_sessions(project_id: str, db: Session = Depends(get_db)):
    """
    Get all processing sessions for a project
    Shows processing history and current sessions
    """
    try:
        from models import TestSession
        
        # Get all sessions for project
        sessions = db.query(TestSession).filter(
            TestSession.project_id == project_id
        ).order_by(TestSession.started_at.desc()).all()
        
        formatted_sessions = [
            {
                "id": session.id,
                "name": session.name,
                "status": session.status,
                "session_type": getattr(session, 'session_type', 'unknown'),
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "configuration": session.configuration,
                "results_summary": session.results_summary
            }
            for session in sessions
        ]
        
        return formatted_sessions
        
    except Exception as e:
        logger.error(f"Error getting project sessions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving project sessions: {str(e)}"
        )

@router.post("/projects/{project_id}/start-specific-videos", response_model=Dict[str, Any])
async def start_specific_videos(
    project_id: str,
    request: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Start sequential processing for specific videos only
    (Alternative to start-all-videos for specific video selection)
    """
    try:
        request = StartAllVideosRequest(
            project_id=project_id,
            video_ids=video_ids,
            session_name=session_name
        )
        
        return await start_all_videos_sequential(request, BackgroundTasks(), db)
        
    except Exception as e:
        logger.error(f"Error starting specific videos: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error starting specific video processing: {str(e)}"
        )

# Health check endpoint
@router.get("/health", response_model=Dict[str, Any])
async def sequential_processing_health():
    """
    Health check for sequential processing service
    """
    return {
        "status": "healthy",
        "service": "Sequential Video Processing",
        "timestamp": datetime.utcnow().isoformat(),
        "active_sessions": len(sequential_processor.processing_sessions),
        "message": "Sequential video processing service is operational"
    }

# Export router for main FastAPI app
sequential_video_router = router
__all__ = ["router", "sequential_video_router"]