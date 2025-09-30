"""
Video Project Links Router - VideoProjectLink Management API
===========================================================

Provides endpoints for managing many-to-many relationships between videos and projects
in the new shared video architecture where videos have project_id=null.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from database import SessionLocal
from models import Video, Project, VideoProjectLink
from schemas import ProjectResponse, VideoFile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/video-project-links", tags=["Video Project Links"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/videos/{video_id}/projects", response_model=List[ProjectResponse])
async def get_video_projects(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Get all projects that a video is linked to.
    Returns empty list if video has no project assignments.
    """
    try:
        logger.info(f"Getting projects for video {video_id}")
        
        # Check if video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get all projects linked to this video
        projects = db.query(Project).join(
            VideoProjectLink, VideoProjectLink.project_id == Project.id
        ).filter(
            VideoProjectLink.video_id == video_id
        ).order_by(Project.name).all()
        
        logger.info(f"Found {len(projects)} projects for video {video_id}")
        
        # Convert to response format using automatic field mapping
        result = []
        for project in projects:
            # Count linked videos for this project
            video_count = db.query(func.count(VideoProjectLink.video_id)).filter(
                VideoProjectLink.project_id == project.id
            ).scalar() or 0
            
            # Use model_validate to properly handle snake_case to camelCase conversion
            project_response = ProjectResponse.model_validate({
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "camera_model": project.camera_model,
                "camera_view": project.camera_view,
                "lens_type": project.lens_type,
                "resolution": project.resolution,
                "frame_rate": project.frame_rate,
                "signal_type": project.signal_type,
                "status": project.status,
                "owner_id": project.owner_id,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
                "video_count": video_count
            })
            result.append(project_response)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting projects for video {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get projects: {str(e)}")

@router.get("/projects/{project_id}/videos", response_model=List[VideoFile])
async def get_project_videos(
    project_id: str,
    db: Session = Depends(get_db),
    include_shared: bool = Query(True, description="Include videos shared across projects")
):
    """
    Get all videos linked to a project.
    """
    try:
        logger.info(f"Getting videos for project {project_id}")
        
        # Check if project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get all videos linked to this project
        videos = db.query(Video).join(
            VideoProjectLink, VideoProjectLink.video_id == Video.id
        ).filter(
            VideoProjectLink.project_id == project_id
        ).order_by(desc(Video.created_at)).all()
        
        logger.info(f"Found {len(videos)} videos for project {project_id}")
        
        # Convert to VideoFile format
        video_files = []
        for video in videos:
            # Get all projects this video is linked to (for shared status)
            linked_projects = db.query(func.count(VideoProjectLink.project_id)).filter(
                VideoProjectLink.video_id == video.id
            ).scalar() or 0
            
            video_file = VideoFile(
                id=video.id,
                filename=video.filename,
                projectId=None,  # Videos are now project-independent
                duration=video.duration,
                size=video.file_size,
                status=video.status,
                createdAt=video.created_at.isoformat() if video.created_at else None,
                # Additional metadata
                isShared=linked_projects > 1,
                linkedProjectCount=linked_projects,
                ground_truth_generated=video.ground_truth_generated,
                validation_status=video.validation_status
            )
            video_files.append(video_file)
        
        return video_files
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting videos for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get videos: {str(e)}")

@router.post("/videos/{video_id}/projects/{project_id}")
async def assign_video_to_project(
    video_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    reason: str = Query("Manual assignment", description="Reason for assignment")
):
    """
    Link a video to a project (many-to-many relationship).
    """
    try:
        logger.info(f"Assigning video {video_id} to project {project_id}")
        
        # Check if video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Check if project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check if assignment already exists
        existing_link = db.query(VideoProjectLink).filter(
            VideoProjectLink.video_id == video_id,
            VideoProjectLink.project_id == project_id
        ).first()
        
        if existing_link:
            return {"message": "Video is already linked to this project", "existing": True}
        
        # Create new assignment
        from crud import assign_video_to_project as crud_assign
        link = crud_assign(db, video_id, project_id, reason)
        
        db.commit()
        
        logger.info(f"Successfully assigned video {video_id} to project {project_id}")
        return {
            "message": "Video successfully linked to project",
            "link_id": link.id,
            "created_at": link.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error assigning video {video_id} to project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to assign video: {str(e)}")

@router.delete("/videos/{video_id}/projects/{project_id}")
async def unassign_video_from_project(
    video_id: str,
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    Remove the link between a video and project.
    """
    try:
        logger.info(f"Unassigning video {video_id} from project {project_id}")
        
        # Find the link
        link = db.query(VideoProjectLink).filter(
            VideoProjectLink.video_id == video_id,
            VideoProjectLink.project_id == project_id
        ).first()
        
        if not link:
            raise HTTPException(status_code=404, detail="Video is not linked to this project")
        
        # Delete the link
        db.delete(link)
        db.commit()
        
        logger.info(f"Successfully unassigned video {video_id} from project {project_id}")
        return {"message": "Video successfully unlinked from project"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error unassigning video {video_id} from project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to unassign video: {str(e)}")

@router.get("/videos/{video_id}/projects/count")
async def get_video_project_count(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the number of projects a video is linked to.
    """
    try:
        # Check if video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Count linked projects
        count = db.query(func.count(VideoProjectLink.project_id)).filter(
            VideoProjectLink.video_id == video_id
        ).scalar() or 0
        
        return {
            "video_id": video_id,
            "linked_project_count": count,
            "is_shared": count > 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project count for video {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get project count: {str(e)}")

@router.get("/health")
async def video_project_links_health_check():
    """Health check for video-project links endpoints"""
    return {
        "status": "healthy",
        "service": "Video Project Links API",
        "version": "1.0.0",
        "endpoints": [
            "GET /api/video-project-links/videos/{video_id}/projects - Get video's projects",
            "GET /api/video-project-links/projects/{project_id}/videos - Get project's videos",
            "POST /api/video-project-links/videos/{video_id}/projects/{project_id} - Link video to project",
            "DELETE /api/video-project-links/videos/{video_id}/projects/{project_id} - Unlink video from project",
            "GET /api/video-project-links/videos/{video_id}/projects/count - Get video's project count"
        ]
    }