"""
Authorization Security Module for Multi-Tenant Data Access Control

This module implements comprehensive authorization checks to prevent
unauthorized access to user data across the ADAS HIL Testing Platform.

CRITICAL SECURITY FEATURES:
- User-scoped data access validation
- Resource ownership verification 
- Multi-tenant data isolation
- Audit trail logging for access attempts

Author: Security Engineering Team
Created: 2025-01-09
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import HTTPException, status
import logging
from datetime import datetime

from models import Project, Video, TestSession, DetectionEvent, GroundTruthObject, AuthUser, AuditLog
from auth_dependencies import get_current_user

logger = logging.getLogger(__name__)

class AuthorizationError(Exception):
    """Custom exception for authorization failures"""
    pass

class ResourceAuthorizationService:
    """Centralized authorization service for resource access control"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_project_access(self, db: Session, project_id: str, user_id: str) -> bool:
        """
        Validate that user has access to the specified project
        
        Args:
            db: Database session
            project_id: Project UUID to validate
            user_id: User UUID requesting access
            
        Returns:
            bool: True if user has access, False otherwise
            
        Raises:
            AuthorizationError: If access is denied
        """
        try:
            project = db.query(Project).filter(
                and_(
                    Project.id == project_id,
                    Project.owner_id == user_id
                )
            ).first()
            
            if not project:
                self.logger.warning(f"Authorization denied: User {user_id} attempted access to project {project_id}")
                self._log_access_attempt(db, user_id, "project", project_id, "denied")
                raise AuthorizationError(f"Access denied to project {project_id}")
            
            self._log_access_attempt(db, user_id, "project", project_id, "granted")
            return True
            
        except Exception as e:
            self.logger.error(f"Project authorization check failed: {e}")
            raise AuthorizationError("Authorization check failed")
    
    def validate_video_access(self, db: Session, video_id: str, user_id: str) -> bool:
        """
        Validate that user has access to the specified video
        
        Args:
            db: Database session
            video_id: Video UUID to validate
            user_id: User UUID requesting access
            
        Returns:
            bool: True if user has access, False otherwise
            
        Raises:
            AuthorizationError: If access is denied
        """
        try:
            video = db.query(Video).join(Project).filter(
                and_(
                    Video.id == video_id,
                    Project.owner_id == user_id
                )
            ).first()
            
            if not video:
                self.logger.warning(f"Authorization denied: User {user_id} attempted access to video {video_id}")
                self._log_access_attempt(db, user_id, "video", video_id, "denied")
                raise AuthorizationError(f"Access denied to video {video_id}")
            
            self._log_access_attempt(db, user_id, "video", video_id, "granted")
            return True
            
        except Exception as e:
            self.logger.error(f"Video authorization check failed: {e}")
            raise AuthorizationError("Authorization check failed")
    
    def validate_session_access(self, db: Session, session_id: str, user_id: str) -> bool:
        """
        Validate that user has access to the specified test session
        
        Args:
            db: Database session
            session_id: Session UUID to validate
            user_id: User UUID requesting access
            
        Returns:
            bool: True if user has access, False otherwise
            
        Raises:
            AuthorizationError: If access is denied
        """
        try:
            session = db.query(TestSession).join(Project).filter(
                and_(
                    TestSession.id == session_id,
                    Project.owner_id == user_id
                )
            ).first()
            
            if not session:
                self.logger.warning(f"Authorization denied: User {user_id} attempted access to session {session_id}")
                self._log_access_attempt(db, user_id, "test_session", session_id, "denied")
                raise AuthorizationError(f"Access denied to test session {session_id}")
            
            self._log_access_attempt(db, user_id, "test_session", session_id, "granted")
            return True
            
        except Exception as e:
            self.logger.error(f"Session authorization check failed: {e}")
            raise AuthorizationError("Authorization check failed")
    
    def get_user_projects(self, db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[Project]:
        """
        Get all projects that belong to the specified user
        
        Args:
            db: Database session
            user_id: User UUID
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List[Project]: Projects owned by the user
        """
        try:
            projects = db.query(Project).filter(
                Project.owner_id == user_id
            ).offset(skip).limit(limit).all()
            
            self.logger.info(f"Retrieved {len(projects)} projects for user {user_id}")
            return projects
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve user projects: {e}")
            raise AuthorizationError("Failed to retrieve projects")
    
    def get_user_videos(self, db: Session, user_id: str, project_id: str = None, 
                       skip: int = 0, limit: int = 100) -> List[Video]:
        """
        Get all videos that belong to the specified user
        
        Args:
            db: Database session
            user_id: User UUID
            project_id: Optional project filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List[Video]: Videos owned by the user
        """
        try:
            query = db.query(Video).join(Project).filter(Project.owner_id == user_id)
            
            if project_id:
                query = query.filter(Video.project_id == project_id)
            
            videos = query.offset(skip).limit(limit).all()
            
            self.logger.info(f"Retrieved {len(videos)} videos for user {user_id}")
            return videos
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve user videos: {e}")
            raise AuthorizationError("Failed to retrieve videos")
    
    def _log_access_attempt(self, db: Session, user_id: str, resource_type: str, 
                           resource_id: str, result: str):
        """
        Log access attempts for audit trail
        
        Args:
            db: Database session
            user_id: User UUID making the request
            resource_type: Type of resource being accessed
            resource_id: UUID of the resource
            result: "granted" or "denied"
        """
        try:
            audit_log = AuditLog(
                user_id=user_id,
                event_type=f"resource_access_{result}",
                event_data={
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "result": result
                }
            )
            db.add(audit_log)
            db.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to log access attempt: {e}")
            # Don't raise exception here as it would break the main flow

# Global authorization service instance
authorization_service = ResourceAuthorizationService()

def require_project_access(db: Session, project_id: str, user_id: str) -> Project:
    """
    Decorator function to require project access
    
    Args:
        db: Database session
        project_id: Project UUID
        user_id: User UUID
        
    Returns:
        Project: The project if access is granted
        
    Raises:
        HTTPException: If access is denied (403 Forbidden)
    """
    try:
        authorization_service.validate_project_access(db, project_id, user_id)
        project = db.query(Project).filter(
            and_(Project.id == project_id, Project.owner_id == user_id)
        ).first()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Project not found or access not authorized"
            )
        
        return project
        
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )

def require_video_access(db: Session, video_id: str, user_id: str) -> Video:
    """
    Decorator function to require video access
    
    Args:
        db: Database session
        video_id: Video UUID
        user_id: User UUID
        
    Returns:
        Video: The video if access is granted
        
    Raises:
        HTTPException: If access is denied (403 Forbidden)
    """
    try:
        authorization_service.validate_video_access(db, video_id, user_id)
        video = db.query(Video).join(Project).filter(
            and_(Video.id == video_id, Project.owner_id == user_id)
        ).first()
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Video not found or access not authorized"
            )
        
        return video
        
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )

def require_session_access(db: Session, session_id: str, user_id: str) -> TestSession:
    """
    Decorator function to require test session access
    
    Args:
        db: Database session
        session_id: Session UUID
        user_id: User UUID
        
    Returns:
        TestSession: The session if access is granted
        
    Raises:
        HTTPException: If access is denied (403 Forbidden)
    """
    try:
        authorization_service.validate_session_access(db, session_id, user_id)
        session = db.query(TestSession).join(Project).filter(
            and_(TestSession.id == session_id, Project.owner_id == user_id)
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Test session not found or access not authorized"
            )
        
        return session
        
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )