"""
Project Management API Router
Handles CRUD operations for VRU detection projects
"""

import logging
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.models.database import Project, User, ProjectStatus, CameraView, SignalType
from src.core.exceptions import VRUDetectionException
from src.schemas.project_schemas import (
    ProjectCreate, 
    ProjectUpdate, 
    ProjectResponse,
    ProjectList,
    ProjectStatistics
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    session: AsyncSession = Depends(get_db)
) -> ProjectResponse:
    """
    Create a new VRU detection project
    
    Args:
        project_data: Project creation data
        session: Database session
        
    Returns:
        Created project details
    """
    try:
        # Validate owner exists (if provided)
        if project_data.owner_id:
            owner_query = select(User).where(User.id == project_data.owner_id)
            owner_result = await session.execute(owner_query)
            owner = owner_result.scalar_one_or_none()
            
            if not owner:
                raise VRUDetectionException(
                    "OWNER_NOT_FOUND",
                    f"User {project_data.owner_id} not found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
        
        # Create new project
        new_project = Project(
            name=project_data.name,
            description=project_data.description,
            camera_model=project_data.camera_model,
            camera_view=project_data.camera_view,
            lens_type=project_data.lens_type,
            resolution=project_data.resolution,
            frame_rate=project_data.frame_rate,
            signal_type=project_data.signal_type,
            status=project_data.status or ProjectStatus.ACTIVE,
            owner_id=project_data.owner_id
        )
        
        session.add(new_project)
        await session.commit()
        await session.refresh(new_project)
        
        # Load with owner relationship
        project_query = select(Project).options(selectinload(Project.owner)).where(Project.id == new_project.id)
        result = await session.execute(project_query)
        project_with_owner = result.scalar_one()
        
        logger.info(f"Project created successfully: {new_project.id}")
        
        return ProjectResponse.from_orm(project_with_owner)
        
    except VRUDetectionException:
        raise
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise VRUDetectionException(
            "PROJECT_CREATION_FAILED",
            "Failed to create project",
            details={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/", response_model=ProjectList)
async def list_projects(
    owner_id: Optional[uuid.UUID] = Query(None, description="Filter by owner ID"),
    status_filter: Optional[ProjectStatus] = Query(None, description="Filter by project status"),
    camera_view: Optional[CameraView] = Query(None, description="Filter by camera view"),
    limit: int = Query(50, ge=1, le=100, description="Number of projects to return"),
    offset: int = Query(0, ge=0, description="Number of projects to skip"),
    session: AsyncSession = Depends(get_db)
) -> ProjectList:
    """
    List projects with optional filtering and pagination
    
    Args:
        owner_id: Optional owner ID filter
        status_filter: Optional status filter
        camera_view: Optional camera view filter
        limit: Maximum number of projects to return
        offset: Number of projects to skip
        session: Database session
        
    Returns:
        List of projects with metadata
    """
    try:
        # Build query with filters
        query = select(Project).options(selectinload(Project.owner))
        
        if owner_id:
            query = query.where(Project.owner_id == owner_id)
        
        if status_filter:
            query = query.where(Project.status == status_filter)
            
        if camera_view:
            query = query.where(Project.camera_view == camera_view)
        
        # Get total count before pagination
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await session.execute(count_query)
        total_count = count_result.scalar()
        
        # Apply pagination and ordering
        query = query.order_by(Project.created_at.desc()).offset(offset).limit(limit)
        
        result = await session.execute(query)
        projects = result.scalars().all()
        
        return ProjectList(
            projects=[ProjectResponse.from_orm(p) for p in projects],
            total=total_count,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise VRUDetectionException(
            "PROJECT_LIST_FAILED",
            "Failed to list projects",
            details={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db)
) -> ProjectResponse:
    """
    Get project by ID with detailed information
    
    Args:
        project_id: Project identifier
        session: Database session
        
    Returns:
        Project details
    """
    try:
        query = (
            select(Project)
            .options(
                selectinload(Project.owner),
                selectinload(Project.videos),
                selectinload(Project.test_sessions)
            )
            .where(Project.id == project_id)
        )
        
        result = await session.execute(query)
        project = result.scalar_one_or_none()
        
        if not project:
            raise VRUDetectionException(
                "PROJECT_NOT_FOUND",
                f"Project {project_id} not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        return ProjectResponse.from_orm(project)
        
    except VRUDetectionException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project {project_id}: {e}")
        raise VRUDetectionException(
            "PROJECT_RETRIEVAL_FAILED",
            "Failed to retrieve project",
            details={"project_id": str(project_id), "error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    project_data: ProjectUpdate,
    session: AsyncSession = Depends(get_db)
) -> ProjectResponse:
    """
    Update project information
    
    Args:
        project_id: Project identifier
        project_data: Updated project data
        session: Database session
        
    Returns:
        Updated project details
    """
    try:
        # Check if project exists
        project_query = select(Project).where(Project.id == project_id)
        result = await session.execute(project_query)
        project = result.scalar_one_or_none()
        
        if not project:
            raise VRUDetectionException(
                "PROJECT_NOT_FOUND",
                f"Project {project_id} not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Prepare update data
        update_data = project_data.dict(exclude_unset=True, exclude_none=True)
        update_data["updated_at"] = datetime.utcnow()
        
        # Validate owner if being updated
        if "owner_id" in update_data and update_data["owner_id"]:
            owner_query = select(User).where(User.id == update_data["owner_id"])
            owner_result = await session.execute(owner_query)
            owner = owner_result.scalar_one_or_none()
            
            if not owner:
                raise VRUDetectionException(
                    "OWNER_NOT_FOUND",
                    f"User {update_data['owner_id']} not found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
        
        # Update project
        query = update(Project).where(Project.id == project_id).values(**update_data)
        await session.execute(query)
        await session.commit()
        
        # Return updated project
        updated_project = await get_project(project_id, session)
        
        logger.info(f"Project updated successfully: {project_id}")
        return updated_project
        
    except VRUDetectionException:
        raise
    except Exception as e:
        logger.error(f"Failed to update project {project_id}: {e}")
        raise VRUDetectionException(
            "PROJECT_UPDATE_FAILED",
            "Failed to update project",
            details={"project_id": str(project_id), "error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete project and all associated data
    
    Args:
        project_id: Project identifier
        session: Database session
    """
    try:
        # Check if project exists
        project_query = select(Project).where(Project.id == project_id)
        result = await session.execute(project_query)
        project = result.scalar_one_or_none()
        
        if not project:
            raise VRUDetectionException(
                "PROJECT_NOT_FOUND",
                f"Project {project_id} not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Check if project has active test sessions
        active_sessions_query = select(func.count()).select_from(
            select(TestSession).where(
                and_(
                    TestSession.project_id == project_id,
                    TestSession.status == TestSessionStatus.RUNNING
                )
            ).subquery()
        )
        active_count_result = await session.execute(active_sessions_query)
        active_sessions = active_count_result.scalar()
        
        if active_sessions > 0:
            raise VRUDetectionException(
                "PROJECT_HAS_ACTIVE_SESSIONS",
                "Cannot delete project with active test sessions",
                details={"active_sessions": active_sessions},
                status_code=status.HTTP_409_CONFLICT
            )
        
        # Delete project (cascade will handle related records)
        delete_query = delete(Project).where(Project.id == project_id)
        await session.execute(delete_query)
        await session.commit()
        
        logger.info(f"Project deleted successfully: {project_id}")
        
    except VRUDetectionException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        raise VRUDetectionException(
            "PROJECT_DELETION_FAILED",
            "Failed to delete project",
            details={"project_id": str(project_id), "error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/{project_id}/statistics", response_model=ProjectStatistics)
async def get_project_statistics(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db)
) -> ProjectStatistics:
    """
    Get detailed statistics for a project
    
    Args:
        project_id: Project identifier
        session: Database session
        
    Returns:
        Project statistics including videos, sessions, and performance metrics
    """
    try:
        # Verify project exists
        project_query = select(Project).where(Project.id == project_id)
        result = await session.execute(project_query)
        project = result.scalar_one_or_none()
        
        if not project:
            raise VRUDetectionException(
                "PROJECT_NOT_FOUND",
                f"Project {project_id} not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Get video statistics
        video_stats_query = select(
            func.count(Video.id).label("total_videos"),
            func.sum(Video.file_size).label("total_storage"),
            func.avg(Video.duration).label("avg_duration")
        ).where(Video.project_id == project_id)
        
        video_result = await session.execute(video_stats_query)
        video_stats = video_result.one()
        
        # Get test session statistics
        session_stats_query = select(
            func.count(TestSession.id).label("total_sessions"),
            func.count().filter(TestSession.status == "completed").label("completed_sessions"),
            func.count().filter(TestSession.status == "running").label("running_sessions"),
            func.count().filter(TestSession.status == "failed").label("failed_sessions")
        ).where(TestSession.project_id == project_id)
        
        session_result = await session.execute(session_stats_query)
        session_stats = session_result.one()
        
        # Get performance metrics from validation results
        performance_query = select(
            func.avg(ValidationResults.precision).label("avg_precision"),
            func.avg(ValidationResults.recall).label("avg_recall"),
            func.avg(ValidationResults.f1_score).label("avg_f1_score"),
            func.avg(ValidationResults.avg_latency_ms).label("avg_latency")
        ).select_from(
            TestSession.__table__.join(ValidationResults.__table__)
        ).where(TestSession.project_id == project_id)
        
        performance_result = await session.execute(performance_query)
        performance_stats = performance_result.one()
        
        return ProjectStatistics(
            project_id=project_id,
            total_videos=video_stats.total_videos or 0,
            total_storage_bytes=video_stats.total_storage or 0,
            average_video_duration=video_stats.avg_duration or 0,
            total_test_sessions=session_stats.total_sessions or 0,
            completed_sessions=session_stats.completed_sessions or 0,
            running_sessions=session_stats.running_sessions or 0,
            failed_sessions=session_stats.failed_sessions or 0,
            average_precision=performance_stats.avg_precision or 0,
            average_recall=performance_stats.avg_recall or 0,
            average_f1_score=performance_stats.avg_f1_score or 0,
            average_latency_ms=performance_stats.avg_latency or 0
        )
        
    except VRUDetectionException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project statistics {project_id}: {e}")
        raise VRUDetectionException(
            "PROJECT_STATISTICS_FAILED",
            "Failed to get project statistics",
            details={"project_id": str(project_id), "error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )