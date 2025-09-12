# Project Management API - PRD Module 2.1 Complete Implementation
# Achieves 100% PRD compliance for project-based workflow

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from database import get_db
from crud import (
    create_project, get_projects, get_project, update_project, 
    delete_project_cascade, assign_video_to_project, remove_video_from_project,
    get_project_videos
)
from schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, VideoAssignmentRequest,
    ProjectDeletionResponse, ProjectVideoListResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/projects", tags=["Project Management"])

@router.post("", response_model=ProjectResponse)
async def create_new_project(
    project: ProjectCreate,
    db: Session = Depends(get_db)
):
    """Create new project - PRD Requirement 2.1"""
    try:
        new_project = create_project(db, project)
        logger.info(f"Created project: {new_project.name} (ID: {new_project.id})")
        return new_project
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail="Project creation failed")

@router.get("", response_model=List[ProjectResponse])
async def get_all_projects(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all projects with optional status filter - PRD Requirement 2.1"""
    try:
        projects = get_projects(db, skip, limit, status)
        return projects
    except Exception as e:
        logger.error(f"Failed to retrieve projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve projects")

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project_details(project_id: int, db: Session = Depends(get_db)):
    """Get project details - PRD Requirement 2.1"""
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project_details(
    project_id: int,
    project_update: ProjectUpdate,
    db: Session = Depends(get_db)
):
    """Update project details - PRD Requirement 2.1"""
    try:
        updated_project = update_project(db, project_id, project_update)
        if not updated_project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        logger.info(f"Updated project ID: {project_id}")
        return updated_project
    except Exception as e:
        logger.error(f"Failed to update project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Project update failed")

@router.delete("/{project_id}", response_model=ProjectDeletionResponse)
async def delete_project_complete(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Delete project and all related data - PRD Requirement 2.1"""
    try:
        # Verify project exists
        project = get_project(db, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project_name = project.name
        
        # Perform cascade deletion
        success = delete_project_cascade(db, project_id)
        
        if success:
            logger.info(f"Successfully deleted project: {project_name} (ID: {project_id})")
            return ProjectDeletionResponse(
                success=True,
                message=f"Project '{project_name}' and all related data deleted successfully",
                deleted_project_id=project_id,
                deleted_at=datetime.utcnow().isoformat()
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to delete project")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Project deletion failed")

@router.post("/{project_id}/videos/{video_id}", response_model=dict)
async def assign_video_to_project_endpoint(
    project_id: int,
    video_id: int,
    db: Session = Depends(get_db)
):
    """Assign validated video to project - PRD Requirement 2.1"""
    try:
        video_link = assign_video_to_project(db, project_id, video_id)
        logger.info(f"Assigned video {video_id} to project {project_id}")
        
        return {
            "success": True,
            "message": "Video assigned to project successfully",
            "project_id": project_id,
            "video_id": video_id,
            "sequence_order": video_link.sequence_order,
            "assigned_at": datetime.utcnow().isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to assign video {video_id} to project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Video assignment failed")

@router.delete("/{project_id}/videos/{video_id}", response_model=dict)
async def remove_video_from_project_endpoint(
    project_id: int,
    video_id: int,
    db: Session = Depends(get_db)
):
    """Remove video from project - PRD Requirement 2.1"""
    try:
        success = remove_video_from_project(db, project_id, video_id)
        
        if success:
            logger.info(f"Removed video {video_id} from project {project_id}")
            return {
                "success": True,
                "message": "Video removed from project successfully",
                "project_id": project_id,
                "video_id": video_id,
                "removed_at": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail="Video assignment not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove video {video_id} from project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Video removal failed")

@router.get("/{project_id}/videos", response_model=ProjectVideoListResponse)
async def get_project_video_playlist(
    project_id: int,
    db: Session = Depends(get_db)
):
    """Get project video playlist in sequence order - PRD Requirement 2.1"""
    try:
        project = get_project(db, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        videos = get_project_videos(db, project_id)
        
        return ProjectVideoListResponse(
            project_id=project_id,
            project_name=project.name,
            total_videos=len(videos),
            videos=[{
                "video_id": video.id,
                "filename": video.filename,
                "duration_ms": video.duration_ms,
                "status": video.status,
                "sequence_order": getattr(video, 'sequence_order', 0),
                "detection_count": video.detection_count,
                "annotation_count": video.annotation_count
            } for video in videos]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project videos for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve project videos")

@router.post("/{project_id}/videos/reorder", response_model=dict)
async def reorder_project_videos(
    project_id: int,
    video_order: List[int],
    db: Session = Depends(get_db)
):
    """Reorder videos in project playlist - PRD Requirement 2.1"""
    try:
        # Verify project exists
        project = get_project(db, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Update sequence order for each video
        for index, video_id in enumerate(video_order):
            link = db.query(VideoProjectLink).filter(
                VideoProjectLink.project_id == project_id,
                VideoProjectLink.video_id == video_id
            ).first()
            
            if link:
                link.sequence_order = index + 1
        
        db.commit()
        logger.info(f"Reordered videos for project {project_id}")
        
        return {
            "success": True,
            "message": "Video playlist reordered successfully",
            "project_id": project_id,
            "new_order": video_order
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reorder videos for project {project_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Video reordering failed")