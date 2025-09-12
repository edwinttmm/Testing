"""
Project-Based Session Management Service

Resolves the "random sessions" issue by ensuring all sessions are properly linked to projects
with meaningful names and proper lifecycle management.

Author: System Architecture Designer
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
import uuid
import logging

from database import SessionLocal
from models import TestSession, Project, Video, VideoProjectLink, DetectionEvent, TestResult

logger = logging.getLogger(__name__)

class ProjectSessionManager:
    """Enhanced session management with proper project context"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def create_project_session(
        self,
        project_id: str,
        session_name: Optional[str] = None,
        video_id: Optional[str] = None,
        tolerance_ms: int = 100,
        session_type: str = "user_created",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create a new test session properly linked to a project with meaningful naming.
        
        Args:
            project_id: Target project ID (must exist)
            session_name: Custom session name (if None, auto-generated from project)
            video_id: Primary video ID for the session
            tolerance_ms: Detection tolerance in milliseconds
            session_type: Type of session ('user_created', 'auto_generated', 'system_test')
            metadata: Additional session metadata
            
        Returns:
            Dictionary with session details and creation status
        """
        db = SessionLocal()
        try:
            # Validate project exists
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project not found: {project_id}")
            
            # Generate meaningful session name if not provided
            if not session_name:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                session_name = f"{project.name} Test Session - {timestamp}"
            
            # Validate or auto-select video
            video = None
            if video_id:
                video = db.query(Video).filter(Video.id == video_id).first()
                if not video:
                    raise ValueError(f"Video not found: {video_id}")
                
                # Ensure video is linked to the project
                video_link = db.query(VideoProjectLink).filter(
                    and_(
                        VideoProjectLink.project_id == project_id,
                        VideoProjectLink.video_id == video_id
                    )
                ).first()
                
                if not video_link and video.project_id != project_id:
                    # Auto-link video to project if not already linked
                    self.logger.info(f"Auto-linking video {video_id} to project {project_id}")
                    video_link = VideoProjectLink(
                        id=str(uuid.uuid4()),
                        video_id=video_id,
                        project_id=project_id,
                        assignment_reason="Auto-linked during session creation",
                        intelligent_match=False,
                        confidence_score=1.0
                    )
                    db.add(video_link)
            else:
                # Auto-select first available video from project if none provided
                # Check direct project videos first
                video = db.query(Video).filter(Video.project_id == project_id).first()
                
                if not video:
                    # Check linked videos if no direct videos
                    video_link = db.query(VideoProjectLink).filter(
                        VideoProjectLink.project_id == project_id
                    ).first()
                    
                    if video_link:
                        video = db.query(Video).filter(Video.id == video_link.video_id).first()
                
                if video:
                    video_id = video.id
                    self.logger.info(f"Auto-selected video {video.filename} (ID: {video_id}) for session")
                else:
                    raise ValueError(f"No videos found in project {project_id}. Sessions require at least one video.")
            
            # Create the test session with proper project context
            session_id = str(uuid.uuid4())
            test_session = TestSession(
                id=session_id,
                name=session_name,
                project_id=project_id,
                video_id=video_id,
                tolerance_ms=tolerance_ms,
                status="created",
                session_type=session_type,
                started_at=None,  # Will be set when session actually starts
                created_at=datetime.now(timezone.utc)
            )
            
            db.add(test_session)
            db.commit()
            
            # Prepare session details
            session_details = {
                "session_id": session_id,
                "session_name": session_name,
                "project_id": project_id,
                "project_name": project.name,
                "video_id": video_id,
                "video_filename": video.filename if video else None,
                "tolerance_ms": tolerance_ms,
                "session_type": session_type,
                "status": "created",
                "created_at": test_session.created_at.isoformat(),
                "metadata": metadata or {}
            }
            
            self.logger.info(
                f"Created project session: {session_name} "
                f"(ID: {session_id[:8]}...) for project: {project.name}"
            )
            
            return {
                "success": True,
                "message": f"Session created successfully for project '{project.name}'",
                "session": session_details
            }
            
        except ValueError as e:
            db.rollback()
            self.logger.error(f"Session creation validation error: {e}")
            return {
                "success": False,
                "error": "validation_error",
                "message": str(e),
                "session": None
            }
        except Exception as e:
            db.rollback()
            self.logger.error(f"Session creation failed: {e}")
            return {
                "success": False,
                "error": "creation_failed",
                "message": f"Failed to create session: {str(e)}",
                "session": None
            }
        finally:
            db.close()
    
    def get_project_sessions(
        self,
        project_id: str,
        limit: int = 50,
        offset: int = 0,
        status_filter: Optional[str] = None,
        session_type_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get all sessions for a specific project with filtering options.
        
        Args:
            project_id: Target project ID
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip (for pagination)
            status_filter: Filter by session status (optional)
            session_type_filter: Filter by session type (optional)
            
        Returns:
            Dictionary with project sessions and metadata
        """
        db = SessionLocal()
        try:
            # Validate project exists
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return {
                    "success": False,
                    "error": "project_not_found",
                    "message": f"Project not found: {project_id}",
                    "sessions": []
                }
            
            # Build query with filters
            query = db.query(TestSession).filter(TestSession.project_id == project_id)
            
            if status_filter:
                query = query.filter(TestSession.status == status_filter)
            
            if session_type_filter:
                query = query.filter(TestSession.session_type == session_type_filter)
            
            # Get total count for pagination
            total_count = query.count()
            
            # Get sessions with pagination
            sessions = query.order_by(desc(TestSession.created_at)).offset(offset).limit(limit).all()
            
            # Format session data
            session_list = []
            for session in sessions:
                # Get video info if linked
                video_info = None
                if session.video_id:
                    video = db.query(Video).filter(Video.id == session.video_id).first()
                    if video:
                        video_info = {
                            "id": video.id,
                            "filename": video.filename,
                            "duration": video.duration,
                            "status": video.status
                        }
                
                # Get session statistics
                detection_count = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == session.id
                ).count()
                
                result_count = db.query(TestResult).filter(
                    TestResult.test_session_id == session.id
                ).count()
                
                session_data = {
                    "id": session.id,
                    "name": session.name,
                    "status": session.status,
                    "session_type": session.session_type,
                    "tolerance_ms": session.tolerance_ms,
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "started_at": session.started_at.isoformat() if session.started_at else None,
                    "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                    "video": video_info,
                    "statistics": {
                        "detection_events": detection_count,
                        "test_results": result_count
                    }
                }
                session_list.append(session_data)
            
            return {
                "success": True,
                "project": {
                    "id": project.id,
                    "name": project.name,
                    "status": project.status
                },
                "sessions": session_list,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total_count
                },
                "filters": {
                    "status": status_filter,
                    "session_type": session_type_filter
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get project sessions: {e}")
            return {
                "success": False,
                "error": "query_failed",
                "message": f"Failed to retrieve sessions: {str(e)}",
                "sessions": []
            }
        finally:
            db.close()
    
    def update_session_status(
        self,
        session_id: str,
        new_status: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Update session status with proper lifecycle management.
        
        Args:
            session_id: Target session ID
            new_status: New status ('created', 'running', 'completed', 'failed', 'cancelled')
            metadata: Additional metadata to store
            
        Returns:
            Dictionary with update status and session details
        """
        db = SessionLocal()
        try:
            session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if not session:
                return {
                    "success": False,
                    "error": "session_not_found",
                    "message": f"Session not found: {session_id}"
                }
            
            old_status = session.status
            session.status = new_status
            session.updated_at = datetime.now(timezone.utc)
            
            # Update lifecycle timestamps
            if new_status == "running" and not session.started_at:
                session.started_at = datetime.now(timezone.utc)
            elif new_status in ["completed", "failed", "cancelled"] and not session.completed_at:
                session.completed_at = datetime.now(timezone.utc)
            
            db.commit()
            
            self.logger.info(f"Updated session {session_id[:8]}... status: {old_status} -> {new_status}")
            
            return {
                "success": True,
                "message": f"Session status updated from {old_status} to {new_status}",
                "session": {
                    "id": session.id,
                    "name": session.name,
                    "old_status": old_status,
                    "new_status": new_status,
                    "updated_at": session.updated_at.isoformat()
                }
            }
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to update session status: {e}")
            return {
                "success": False,
                "error": "update_failed",
                "message": f"Failed to update session: {str(e)}"
            }
        finally:
            db.close()
    
    def cleanup_phantom_sessions(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Clean up phantom/orphaned sessions that don't belong to valid projects.
        
        Args:
            dry_run: If True, only report what would be cleaned up
            
        Returns:
            Dictionary with cleanup results
        """
        db = SessionLocal()
        try:
            # Find phantom sessions
            phantom_sessions = db.query(TestSession).filter(
                or_(
                    TestSession.name.like("Detection Session - %"),
                    TestSession.name.like("Detection Session%"),
                    TestSession.project_id == "00000000-0000-0000-0000-000000000000",
                    and_(
                        TestSession.name.contains("Detection"),
                        TestSession.name.contains("Session"),
                        TestSession.status.in_(["completed", "failed"])
                    )
                )
            ).all()
            
            phantom_count = len(phantom_sessions)
            
            if dry_run:
                phantom_list = []
                for session in phantom_sessions[:10]:  # Show first 10
                    phantom_list.append({
                        "id": session.id,
                        "name": session.name,
                        "project_id": session.project_id,
                        "status": session.status,
                        "created_at": session.created_at.isoformat() if session.created_at else None
                    })
                
                return {
                    "success": True,
                    "dry_run": True,
                    "phantom_sessions_found": phantom_count,
                    "sample_sessions": phantom_list,
                    "message": f"Found {phantom_count} phantom sessions to clean up"
                }
            else:
                # Actually delete phantom sessions
                deleted_count = 0
                for session in phantom_sessions:
                    try:
                        db.delete(session)
                        deleted_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to delete phantom session {session.id}: {e}")
                        continue
                
                db.commit()
                
                self.logger.info(f"Deleted {deleted_count} phantom sessions")
                
                return {
                    "success": True,
                    "dry_run": False,
                    "phantom_sessions_found": phantom_count,
                    "deleted_count": deleted_count,
                    "message": f"Successfully deleted {deleted_count} phantom sessions"
                }
        
        except Exception as e:
            db.rollback()
            self.logger.error(f"Phantom session cleanup failed: {e}")
            return {
                "success": False,
                "error": "cleanup_failed",
                "message": f"Failed to cleanup phantom sessions: {str(e)}"
            }
        finally:
            db.close()
    
    def get_session_details(self, session_id: str) -> Dict[str, Any]:
        """
        Get comprehensive details for a specific session.
        
        Args:
            session_id: Target session ID
            
        Returns:
            Dictionary with complete session information
        """
        db = SessionLocal()
        try:
            session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if not session:
                return {
                    "success": False,
                    "error": "session_not_found",
                    "message": f"Session not found: {session_id}"
                }
            
            # Get project info
            project = db.query(Project).filter(Project.id == session.project_id).first()
            
            # Get video info
            video = None
            if session.video_id:
                video = db.query(Video).filter(Video.id == session.video_id).first()
            
            # Get session statistics
            detection_events = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).all()
            
            test_results = db.query(TestResult).filter(
                TestResult.test_session_id == session.id
            ).all()
            
            # Build comprehensive response
            session_details = {
                "success": True,
                "session": {
                    "id": session.id,
                    "name": session.name,
                    "status": session.status,
                    "session_type": session.session_type,
                    "tolerance_ms": session.tolerance_ms,
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "started_at": session.started_at.isoformat() if session.started_at else None,
                    "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                    "updated_at": session.updated_at.isoformat() if session.updated_at else None
                },
                "project": {
                    "id": project.id,
                    "name": project.name,
                    "status": project.status
                } if project else None,
                "video": {
                    "id": video.id,
                    "filename": video.filename,
                    "duration": video.duration,
                    "status": video.status,
                    "file_path": video.file_path
                } if video else None,
                "statistics": {
                    "detection_events": len(detection_events),
                    "test_results": len(test_results),
                    "duration_seconds": None
                }
            }
            
            # Calculate session duration if completed
            if session.started_at and session.completed_at:
                duration = (session.completed_at - session.started_at).total_seconds()
                session_details["statistics"]["duration_seconds"] = duration
            
            return session_details
            
        except Exception as e:
            self.logger.error(f"Failed to get session details: {e}")
            return {
                "success": False,
                "error": "query_failed",
                "message": f"Failed to retrieve session details: {str(e)}"
            }
        finally:
            db.close()

# Global session manager instance
session_manager = ProjectSessionManager()