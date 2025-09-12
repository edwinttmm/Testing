"""
Project Management Router - Organized API Endpoints
=================================================

Consolidated project-related endpoints following FastAPI best practices.
Handles project CRUD operations, statistics, and project-video relationships.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import uuid

from database import SessionLocal
from models import Project, Video, TestSession, VideoProjectLink
from schemas import (
    ProjectCreate, ProjectResponse, ProjectUpdate,
    VideoAssignmentSchema, VideoAssignmentResponse,
    PassFailCriteriaSchema, PassFailCriteriaResponse
)
from services.video_library_service import VideoLibraryManager
from crud import create_project, get_projects, get_project, update_project, delete_project
from constants import CENTRAL_STORE_PROJECT_ID, CENTRAL_STORE_PROJECT_NAME, CENTRAL_STORE_PROJECT_DESCRIPTION

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["Project Management"])

# Initialize services
video_library_manager = VideoLibraryManager()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# PROJECT CRUD OPERATIONS
# ============================================================================

@router.post("", response_model=ProjectResponse)
async def create_new_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project with validation and default settings"""
    try:
        db_project = create_project(db=db, project=project)
        
        # Log project creation for audit trail
        logger.info(f"Project created: {db_project.name} (ID: {db_project.id})")
        
        return db_project
    except IntegrityError:
        raise HTTPException(
            status_code=400,
            detail="Project with this name already exists"
        )
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None, description="Filter by project status"),
    db: Session = Depends(get_db)
):
    """List all projects with optional filtering and pagination"""
    try:
        query = db.query(Project)
        
        if status:
            query = query.filter(Project.status == status)
            
        projects = query.offset(skip).limit(limit).all()
        
        logger.info(f"Retrieved {len(projects)} projects")
        return projects
    except Exception as e:
        logger.error(f"Error retrieving projects: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve projects: {str(e)}")

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project_details(project_id: str, db: Session = Depends(get_db)):
    """Get detailed information about a specific project"""
    try:
        project = get_project(db=db, project_id=project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return project
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve project: {str(e)}")

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project_details(
    project_id: str,
    project_update: ProjectUpdate,
    db: Session = Depends(get_db)
):
    """Update project information"""
    try:
        # Check if project exists
        existing_project = get_project(db=db, project_id=project_id)
        if not existing_project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Update project
        updated_project = update_project(db=db, project_id=project_id, project=project_update)
        
        logger.info(f"Project updated: {project_id}")
        return updated_project
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")

@router.delete("/{project_id}")
async def delete_project_endpoint(project_id: str, db: Session = Depends(get_db)):
    """Delete a project and all associated data"""
    try:
        # Check if project exists
        project = get_project(db=db, project_id=project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check for associated sessions
        session_count = db.query(TestSession).filter(TestSession.project_id == project_id).count()
        if session_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete project with {session_count} active test sessions"
            )
        
        # Delete project
        success = delete_project(db=db, project_id=project_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete project")
        
        logger.info(f"Project deleted: {project_id}")
        return {"message": "Project deleted successfully", "project_id": project_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")

# ============================================================================
# PROJECT-VIDEO RELATIONSHIP MANAGEMENT
# ============================================================================

@router.post("/{project_id}/videos/link")
async def link_video_to_project(
    project_id: str,
    video_id: str = Query(..., description="Video ID to link"),
    db: Session = Depends(get_db)
):
    """Link an existing video to a project"""
    try:
        # Verify project exists
        project = get_project(db=db, project_id=project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Verify video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Check if link already exists
        existing_link = db.query(VideoProjectLink).filter(
            VideoProjectLink.video_id == video_id,
            VideoProjectLink.project_id == project_id
        ).first()
        
        if existing_link:
            return {
                "success": True,
                "message": "Video already linked to project",
                "link_id": existing_link.id
            }
        
        # Create new link
        link = VideoProjectLink(
            id=str(uuid.uuid4()),
            video_id=video_id,
            project_id=project_id,
            linked_at=datetime.utcnow()
        )
        
        db.add(link)
        db.commit()
        db.refresh(link)
        
        logger.info(f"Video {video_id} linked to project {project_id}")
        return {
            "success": True,
            "message": "Video linked to project successfully",
            "link_id": link.id,
            "video_filename": video.filename,
            "project_name": project.name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking video to project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to link video: {str(e)}")

@router.get("/{project_id}/videos/linked")
async def get_linked_videos(project_id: str, db: Session = Depends(get_db)):
    """Get all videos linked to a project"""
    try:
        # Verify project exists
        project = get_project(db=db, project_id=project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get linked videos with optimized query
        linked_videos = db.query(Video).join(VideoProjectLink).filter(
            VideoProjectLink.project_id == project_id
        ).all()
        
        return {
            "project_id": project_id,
            "project_name": project.name,
            "linked_videos": [
                {
                    "id": video.id,
                    "filename": video.filename,
                    "file_path": video.file_path,
                    "duration": video.duration,
                    "fps": video.fps,
                    "uploaded_at": video.created_at.isoformat() if video.created_at else None
                }
                for video in linked_videos
            ],
            "total_count": len(linked_videos)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving linked videos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve linked videos: {str(e)}")

@router.delete("/{project_id}/videos/{video_id}/unlink")
async def unlink_video_from_project(
    project_id: str,
    video_id: str,
    db: Session = Depends(get_db)
):
    """Unlink a video from a project"""
    try:
        # Find and delete the link
        link = db.query(VideoProjectLink).filter(
            VideoProjectLink.video_id == video_id,
            VideoProjectLink.project_id == project_id
        ).first()
        
        if not link:
            raise HTTPException(
                status_code=404,
                detail="Video is not linked to this project"
            )
        
        db.delete(link)
        db.commit()
        
        logger.info(f"Video {video_id} unlinked from project {project_id}")
        return {
            "success": True,
            "message": "Video unlinked from project successfully",
            "video_id": video_id,
            "project_id": project_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unlinking video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to unlink video: {str(e)}")

# ============================================================================
# PROJECT STATISTICS AND ANALYTICS
# ============================================================================

@router.get("/{project_id}/statistics")
async def get_project_statistics(project_id: str, db: Session = Depends(get_db)):
    """Get comprehensive statistics for a project"""
    try:
        # Verify project exists
        project = get_project(db=db, project_id=project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get video count
        video_count = db.query(Video).filter(Video.project_id == project_id).count()
        linked_video_count = db.query(VideoProjectLink).filter(
            VideoProjectLink.project_id == project_id
        ).count()
        
        # Get session statistics
        total_sessions = db.query(TestSession).filter(TestSession.project_id == project_id).count()
        active_sessions = db.query(TestSession).filter(
            TestSession.project_id == project_id,
            TestSession.status == "running"
        ).count()
        completed_sessions = db.query(TestSession).filter(
            TestSession.project_id == project_id,
            TestSession.status == "completed"
        ).count()
        
        return {
            "project_id": project_id,
            "project_name": project.name,
            "statistics": {
                "videos": {
                    "direct_videos": video_count,
                    "linked_videos": linked_video_count,
                    "total_videos": video_count + linked_video_count
                },
                "sessions": {
                    "total": total_sessions,
                    "active": active_sessions,
                    "completed": completed_sessions,
                    "success_rate": (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
                }
            },
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving project statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve statistics: {str(e)}")

# ============================================================================
# PROJECT CONFIGURATION AND SETTINGS  
# ============================================================================

@router.post("/{project_id}/criteria/configure", response_model=PassFailCriteriaResponse)
async def configure_pass_fail_criteria(
    project_id: str,
    criteria: PassFailCriteriaSchema,
    db: Session = Depends(get_db)
):
    """Configure pass/fail criteria for a project"""
    try:
        # Verify project exists
        project = get_project(db=db, project_id=project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Update project with criteria
        project.pass_fail_criteria = criteria.dict()
        project.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(project)
        
        logger.info(f"Pass/fail criteria configured for project {project_id}")
        return PassFailCriteriaResponse(
            project_id=project_id,
            criteria=criteria,
            configured_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring criteria: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to configure criteria: {str(e)}")

@router.get("/{project_id}/assignments/intelligent", response_model=List[VideoAssignmentResponse])
async def get_intelligent_video_assignments(
    project_id: str,
    db: Session = Depends(get_db)
):
    """Get intelligent video assignments based on project criteria"""
    try:
        # Verify project exists
        project = get_project(db=db, project_id=project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Use video library manager for intelligent assignment
        assignments = await video_library_manager.get_intelligent_assignments(
            project_id=project_id,
            project_criteria=project.pass_fail_criteria or {}
        )
        
        return assignments
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting intelligent assignments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get assignments: {str(e)}")

# ============================================================================
# HEALTH CHECK AND UTILITIES
# ============================================================================

@router.get("/health")
async def projects_health_check():
    """Health check endpoint for project management"""
    return {
        "status": "healthy",
        "service": "Project Management Router",
        "version": "1.0.0",
        "endpoints": [
            "POST /api/projects - Create project",
            "GET /api/projects - List projects", 
            "GET /api/projects/{id} - Get project details",
            "PUT /api/projects/{id} - Update project",
            "DELETE /api/projects/{id} - Delete project",
            "POST /api/projects/{id}/videos/link - Link video",
            "GET /api/projects/{id}/videos/linked - Get linked videos",
            "DELETE /api/projects/{id}/videos/{video_id}/unlink - Unlink video"
        ]
    }