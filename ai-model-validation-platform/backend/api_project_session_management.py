"""
Project-Based Session Management API Endpoints

Provides REST API for proper project-based session management, 
replacing the random session generation with meaningful, project-linked sessions.

Author: System Architecture Designer
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
import logging

from database import get_db
from services.session_management_service import session_manager
from models import Project, Video

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/project-sessions", tags=["Project Session Management"])

# Pydantic models for API requests/responses
class CreateSessionRequest(BaseModel):
    """Request to create a new project-based test session"""
    project_id: str = Field(..., description="Target project ID")
    session_name: Optional[str] = Field(None, description="Custom session name (auto-generated if not provided)")
    video_id: Optional[str] = Field(None, description="Primary video ID for the session")
    tolerance_ms: int = Field(100, description="Detection tolerance in milliseconds")
    session_type: str = Field("user_created", description="Session type")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional session metadata")

class SessionResponse(BaseModel):
    """Session information response"""
    id: str
    name: str
    project_id: str
    project_name: str
    status: str
    session_type: str
    tolerance_ms: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    video: Optional[Dict] = None
    statistics: Optional[Dict] = None

class ProjectSessionsResponse(BaseModel):
    """Project sessions list response"""
    success: bool
    project: Dict[str, Any]
    sessions: List[Dict[str, Any]]
    pagination: Dict[str, Any]
    filters: Dict[str, Any]

class UpdateSessionStatusRequest(BaseModel):
    """Request to update session status"""
    status: str = Field(..., description="New status (created, running, completed, failed, cancelled)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

@router.post("/create", response_model=Dict[str, Any])
async def create_project_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new test session properly linked to a project.
    This replaces random session generation with meaningful, project-based sessions.
    """
    try:
        # Validate project exists
        project = db.query(Project).filter(Project.id == request.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {request.project_id}")
        
        # Use the session management service
        result = session_manager.create_project_session(
            project_id=request.project_id,
            session_name=request.session_name,
            video_id=request.video_id,
            tolerance_ms=request.tolerance_ms,
            session_type=request.session_type,
            metadata=request.metadata
        )
        
        if not result["success"]:
            if result["error"] == "validation_error":
                raise HTTPException(status_code=400, detail=result["message"])
            else:
                raise HTTPException(status_code=500, detail=result["message"])
        
        logger.info(f"Created project session for project: {project.name} (ID: {request.project_id})")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create project session: {e}")
        raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")

@router.get("/project/{project_id}", response_model=Dict[str, Any])
async def get_project_sessions(
    project_id: str,
    limit: int = Query(50, description="Maximum sessions to return"),
    offset: int = Query(0, description="Offset for pagination"),
    status: Optional[str] = Query(None, description="Filter by session status"),
    session_type: Optional[str] = Query(None, description="Filter by session type"),
    db: Session = Depends(get_db)
):
    """
    Get all sessions for a specific project with filtering and pagination.
    This ensures users see only their project-specific sessions, not random ones.
    """
    try:
        result = session_manager.get_project_sessions(
            project_id=project_id,
            limit=limit,
            offset=offset,
            status_filter=status,
            session_type_filter=session_type
        )
        
        if not result["success"]:
            if result["error"] == "project_not_found":
                raise HTTPException(status_code=404, detail=result["message"])
            else:
                raise HTTPException(status_code=500, detail=result["message"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve sessions: {str(e)}")

@router.get("/session/{session_id}", response_model=Dict[str, Any])
async def get_session_details(session_id: str):
    """
    Get comprehensive details for a specific session including project context.
    """
    try:
        result = session_manager.get_session_details(session_id)
        
        if not result["success"]:
            if result["error"] == "session_not_found":
                raise HTTPException(status_code=404, detail=result["message"])
            else:
                raise HTTPException(status_code=500, detail=result["message"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve session: {str(e)}")

@router.put("/session/{session_id}/status")
async def update_session_status(
    session_id: str,
    request: UpdateSessionStatusRequest
):
    """
    Update session status with proper lifecycle management.
    """
    try:
        result = session_manager.update_session_status(
            session_id=session_id,
            new_status=request.status,
            metadata=request.metadata
        )
        
        if not result["success"]:
            if result["error"] == "session_not_found":
                raise HTTPException(status_code=404, detail=result["message"])
            else:
                raise HTTPException(status_code=500, detail=result["message"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update session status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update session: {str(e)}")

@router.get("/projects/all", response_model=List[Dict[str, Any]])
async def get_all_projects_with_session_counts(db: Session = Depends(get_db)):
    """
    Get all projects with their session counts for the UI project selector.
    This helps users understand which projects have active sessions.
    OPTIMIZED: Single query with joins to prevent N+1 performance issues.
    """
    try:
        from models import TestSession, VideoProjectLink
        from sqlalchemy import func, case
        
        # Single optimized query with all counts calculated in one go
        projects_query = db.query(
            Project.id,
            Project.name,
            Project.description,
            Project.status,
            Project.camera_model,
            Project.camera_view,
            Project.signal_type,
            Project.created_at,
            func.count(func.distinct(TestSession.id)).label('session_count'),
            func.count(func.distinct(Video.id)).label('direct_video_count'),
            func.count(func.distinct(VideoProjectLink.id)).label('linked_video_count')
        ).outerjoin(
            TestSession, TestSession.project_id == Project.id
        ).outerjoin(
            Video, Video.project_id == Project.id
        ).outerjoin(
            VideoProjectLink, VideoProjectLink.project_id == Project.id
        ).group_by(
            Project.id,
            Project.name,
            Project.description,
            Project.status,
            Project.camera_model,
            Project.camera_view,
            Project.signal_type,
            Project.created_at
        ).all()
        
        projects_data = []
        for row in projects_query:
            # Calculate total video count from the joined results
            total_video_count = max(row.direct_video_count or 0, row.linked_video_count or 0)
            
            projects_data.append({
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "status": row.status,
                "camera_model": row.camera_model,
                "camera_view": row.camera_view,
                "signal_type": row.signal_type,
                "session_count": row.session_count or 0,
                "video_count": total_video_count,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "is_active_project": row.status == "Active"  # Mark active projects instead of hardcoded ID
            })
        
        # Sort by active projects first, then by name
        projects_data.sort(key=lambda p: (not p["is_active_project"], p["name"]))
        
        logger.info(f"Retrieved {len(projects_data)} projects with session counts using optimized single query")
        return projects_data
        
    except Exception as e:
        logger.error(f"Failed to get projects with session counts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve projects: {str(e)}")

@router.post("/cleanup-phantom")
async def cleanup_phantom_sessions(
    execute: bool = Query(False, description="Actually delete phantom sessions (default: dry run)")
):
    """
    Clean up phantom/random sessions that don't belong to proper projects.
    This helps resolve the "sessions is projects sessions not random" issue.
    """
    try:
        result = session_manager.cleanup_phantom_sessions(dry_run=not execute)
        
        if execute:
            logger.info(f"Phantom session cleanup executed: {result.get('deleted_count', 0)} sessions deleted")
        else:
            logger.info(f"Phantom session cleanup dry run: {result.get('phantom_sessions_found', 0)} sessions found")
        
        return result
        
    except Exception as e:
        logger.error(f"Phantom session cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@router.get("/statistics/summary")
async def get_session_statistics(db: Session = Depends(get_db)):
    """
    Get overall session statistics across all projects.
    FIXED: Using proper dependency injection to prevent connection leaks.
    """
    try:
        from models import TestSession
        from sqlalchemy import func, case
        
        # Single optimized query for all statistics
        statistics_query = db.query(
            func.count(TestSession.id).label('total_sessions'),
            func.sum(case((TestSession.status == 'running', 1), else_=0)).label('active_sessions'),
            func.sum(case((TestSession.status == 'completed', 1), else_=0)).label('completed_sessions'),
            func.sum(case((TestSession.status == 'failed', 1), else_=0)).label('failed_sessions')
        ).first()
        
        # Get session statistics by project in single query
        project_stats = db.query(
            TestSession.project_id,
            Project.name.label('project_name'),
            func.count(TestSession.id).label('session_count')
        ).join(
            Project, TestSession.project_id == Project.id
        ).group_by(
            TestSession.project_id, Project.name
        ).all()
        
        # Extract statistics safely
        total_sessions = statistics_query.total_sessions or 0
        active_sessions = statistics_query.active_sessions or 0
        completed_sessions = statistics_query.completed_sessions or 0
        failed_sessions = statistics_query.failed_sessions or 0
        
        # Format response
        statistics = {
            "overall": {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "completed_sessions": completed_sessions,
                "failed_sessions": failed_sessions,
                "success_rate": (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
            },
            "by_project": [
                {
                    "project_id": stats.project_id,
                    "project_name": stats.project_name,
                    "session_count": stats.session_count,
                    "is_active_project": True  # All stats are for active projects
                }
                for stats in project_stats
            ]
        }
        
        logger.info(f"Retrieved session statistics using optimized queries and proper dependency injection")
        return statistics
        
    except Exception as e:
        logger.error(f"Failed to get session statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve statistics: {str(e)}")

# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check for project session management system"""
    try:
        return {
            "status": "healthy",
            "service": "Project Session Management",
            "version": "1.0.0",
            "features": [
                "Project-based session creation",
                "Meaningful session naming",
                "Session lifecycle management",
                "Phantom session cleanup",
                "Project context preservation"
            ]
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

# Export router for main FastAPI app
project_session_router = router
__all__ = ["router", "project_session_router"]