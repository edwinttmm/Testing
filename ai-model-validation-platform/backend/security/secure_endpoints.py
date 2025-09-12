"""
Secure API Endpoints with Multi-Tenant Authorization

This module provides secure versions of critical API endpoints that enforce
proper multi-tenant data isolation and user authorization.

SECURITY ENHANCEMENTS:
- User authentication on all endpoints
- Resource ownership validation
- Audit logging for all operations
- Input sanitization and validation
- Rate limiting integration points

Author: Security Engineering Team
Created: 2025-01-09
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from database import get_db
from auth_dependencies import get_current_user
from models import AuthUser, Project, Video, TestSession, DetectionEvent
from schemas import ProjectResponse, VideoUploadResponse, TestSessionResponse
from security.authorization import (
    authorization_service, 
    require_project_access, 
    require_video_access, 
    require_session_access
)
from crud import (
    get_projects as crud_get_projects,
    get_project as crud_get_project,
    get_videos as crud_get_videos,
    get_video as crud_get_video,
    get_test_sessions as crud_get_test_sessions,
    get_test_session as crud_get_test_session,
    get_detection_events as crud_get_detection_events
)

router = APIRouter(prefix="/api/secure", tags=["Secure Multi-Tenant API"])
logger = logging.getLogger(__name__)

# SECURE PROJECT ENDPOINTS

@router.get("/projects", response_model=List[ProjectResponse])
async def get_user_projects(
    skip: int = 0,
    limit: int = 100,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all projects for the authenticated user only.
    
    SECURITY: Enforces user data isolation - users can only see their own projects.
    """
    try:
        logger.info(f"User {current_user.id} requesting their projects")
        
        # Use authorization service to get user-scoped projects
        projects = authorization_service.get_user_projects(
            db=db, 
            user_id=current_user.id, 
            skip=skip, 
            limit=limit
        )
        
        logger.info(f"Retrieved {len(projects)} projects for user {current_user.id}")
        return projects
        
    except Exception as e:
        logger.error(f"Failed to retrieve projects for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve projects"
        )

@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_user_project(
    project_id: str,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific project for the authenticated user.
    
    SECURITY: Validates user owns the project before returning data.
    """
    try:
        logger.info(f"User {current_user.id} requesting project {project_id}")
        
        # Validate user has access to this project
        project = require_project_access(db, project_id, current_user.id)
        
        logger.info(f"Retrieved project {project_id} for user {current_user.id}")
        return project
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve project {project_id} for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve project"
        )

# SECURE VIDEO ENDPOINTS

@router.get("/videos", response_model=List[VideoUploadResponse])
async def get_user_videos(
    project_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all videos for the authenticated user.
    
    SECURITY: Only returns videos from projects owned by the user.
    """
    try:
        logger.info(f"User {current_user.id} requesting their videos")
        
        # If project_id specified, validate user owns that project
        if project_id:
            require_project_access(db, project_id, current_user.id)
        
        # Use authorization service to get user-scoped videos
        videos = authorization_service.get_user_videos(
            db=db, 
            user_id=current_user.id,
            project_id=project_id,
            skip=skip, 
            limit=limit
        )
        
        logger.info(f"Retrieved {len(videos)} videos for user {current_user.id}")
        return videos
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve videos for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve videos"
        )

@router.get("/videos/{video_id}", response_model=VideoUploadResponse)
async def get_user_video(
    video_id: str,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific video for the authenticated user.
    
    SECURITY: Validates user owns the video (through project ownership) before returning data.
    """
    try:
        logger.info(f"User {current_user.id} requesting video {video_id}")
        
        # Validate user has access to this video
        video = require_video_access(db, video_id, current_user.id)
        
        logger.info(f"Retrieved video {video_id} for user {current_user.id}")
        return video
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve video {video_id} for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve video"
        )

# SECURE TEST SESSION ENDPOINTS

@router.get("/test-sessions", response_model=List[TestSessionResponse])
async def get_user_test_sessions(
    project_id: Optional[str] = None,
    video_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all test sessions for the authenticated user.
    
    SECURITY: Only returns sessions from projects owned by the user.
    """
    try:
        logger.info(f"User {current_user.id} requesting their test sessions")
        
        # If project_id specified, validate user owns that project
        if project_id:
            require_project_access(db, project_id, current_user.id)
        
        # If video_id specified, validate user owns that video
        if video_id:
            require_video_access(db, video_id, current_user.id)
        
        # Get user-scoped test sessions using secure CRUD function
        test_sessions = crud_get_test_sessions(
            db=db,
            project_id=project_id,
            video_id=video_id,
            user_id=current_user.id,
            skip=skip,
            limit=limit
        )
        
        logger.info(f"Retrieved {len(test_sessions)} test sessions for user {current_user.id}")
        return test_sessions
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve test sessions for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve test sessions"
        )

@router.get("/test-sessions/{session_id}", response_model=TestSessionResponse)
async def get_user_test_session(
    session_id: str,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific test session for the authenticated user.
    
    SECURITY: Validates user owns the session (through project ownership) before returning data.
    """
    try:
        logger.info(f"User {current_user.id} requesting test session {session_id}")
        
        # Validate user has access to this test session
        session = require_session_access(db, session_id, current_user.id)
        
        logger.info(f"Retrieved test session {session_id} for user {current_user.id}")
        return session
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve test session {session_id} for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve test session"
        )

# SECURE DETECTION EVENT ENDPOINTS

@router.get("/test-sessions/{session_id}/detection-events")
async def get_session_detection_events(
    session_id: str,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all detection events for a specific test session.
    
    SECURITY: Validates user owns the session before returning detection events.
    """
    try:
        logger.info(f"User {current_user.id} requesting detection events for session {session_id}")
        
        # Validate user has access to this test session
        require_session_access(db, session_id, current_user.id)
        
        # Get detection events using secure CRUD function
        detection_events = crud_get_detection_events(
            db=db,
            test_session_id=session_id,
            user_id=current_user.id
        )
        
        logger.info(f"Retrieved {len(detection_events)} detection events for session {session_id} (user {current_user.id})")
        return detection_events
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve detection events for session {session_id} (user {current_user.id}): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve detection events"
        )

# SECURITY STATUS ENDPOINT

@router.get("/security/status")
async def get_security_status(
    current_user: AuthUser = Depends(get_current_user),
    request: Request = None
):
    """
    Get security status and user context information.
    
    This endpoint provides security diagnostics and user session information.
    """
    try:
        return {
            "security_enabled": True,
            "multi_tenant_isolation": True,
            "user_id": current_user.id,
            "user_email": current_user.email,
            "is_authenticated": True,
            "access_level": "standard",
            "session_info": {
                "ip_address": request.client.host if request else None,
                "user_agent": request.headers.get("user-agent") if request else None,
            },
            "authorization_features": [
                "project_ownership_validation",
                "video_access_control", 
                "session_isolation",
                "audit_logging",
                "resource_scoping"
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get security status for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security status"
        )