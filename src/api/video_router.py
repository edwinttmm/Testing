"""
Video Management API Router
Handles video upload, storage, processing, and retrieval
"""

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.services.video_service import VideoLibraryService
from src.models.database import VideoStatus
from src.core.exceptions import VRUDetectionException
from src.schemas.video_schemas import (
    VideoResponse,
    VideoList,
    VideoUploadResponse,
    VideoStatistics
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=VideoUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    project_id: uuid.UUID = Query(..., description="Project ID to associate video with"),
    file: UploadFile = File(..., description="Video file to upload"),
    session: AsyncSession = Depends(get_db)
) -> VideoUploadResponse:
    """
    Upload a video file to the specified project
    
    Args:
        project_id: Target project identifier
        file: Video file to upload
        session: Database session
        
    Returns:
        Upload result with video ID and processing status
    """
    try:
        video_service = VideoLibraryService()
        
        # Upload and process video
        result = await video_service.upload_video(file, project_id, session)
        
        return VideoUploadResponse(
            video_id=result.video_id,
            filename=file.filename,
            status=result.status,
            file_size=result.metadata.file_size,
            duration=result.metadata.duration,
            fps=result.metadata.fps,
            resolution=f"{result.metadata.resolution[0]}x{result.metadata.resolution[1]}",
            estimated_completion=result.estimated_completion,
            message="Video uploaded successfully and queued for processing"
        )
        
    except VRUDetectionException:
        raise
    except Exception as e:
        logger.error(f"Video upload failed: {e}")
        raise VRUDetectionException(
            "VIDEO_UPLOAD_FAILED",
            "Failed to upload video",
            details={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/", response_model=VideoList)
async def list_videos(
    project_id: Optional[uuid.UUID] = Query(None, description="Filter by project ID"),
    status_filter: Optional[VideoStatus] = Query(None, description="Filter by video status"),
    limit: int = Query(50, ge=1, le=100, description="Number of videos to return"),
    offset: int = Query(0, ge=0, description="Number of videos to skip"),
    session: AsyncSession = Depends(get_db)
) -> VideoList:
    """
    List videos with optional filtering and pagination
    
    Args:
        project_id: Optional project ID filter
        status_filter: Optional status filter
        limit: Maximum number of videos to return
        offset: Number of videos to skip
        session: Database session
        
    Returns:
        List of videos with metadata
    """
    try:
        video_service = VideoLibraryService()
        
        videos = await video_service.list_videos(
            project_id=project_id,
            status_filter=status_filter,
            limit=limit,
            offset=offset,
            session=session
        )
        
        # Get total count for pagination
        total_videos = await video_service.list_videos(
            project_id=project_id,
            status_filter=status_filter,
            limit=10000,  # Large number to get all
            offset=0,
            session=session
        )
        
        return VideoList(
            videos=[VideoResponse.from_orm(v) for v in videos],
            total=len(total_videos),
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Failed to list videos: {e}")
        raise VRUDetectionException(
            "VIDEO_LIST_FAILED",
            "Failed to list videos",
            details={"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: uuid.UUID,
    session: AsyncSession = Depends(get_db)
) -> VideoResponse:
    """
    Get video details by ID
    
    Args:
        video_id: Video identifier
        session: Database session
        
    Returns:
        Video details with metadata
    """
    try:
        video_service = VideoLibraryService()
        
        video = await video_service.get_video(video_id, session)
        
        if not video:
            raise VRUDetectionException(
                "VIDEO_NOT_FOUND",
                f"Video {video_id} not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        return VideoResponse.from_orm(video)
        
    except VRUDetectionException:
        raise
    except Exception as e:
        logger.error(f"Failed to get video {video_id}: {e}")
        raise VRUDetectionException(
            "VIDEO_RETRIEVAL_FAILED",
            "Failed to retrieve video",
            details={"video_id": str(video_id), "error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: uuid.UUID,
    session: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete video and associated files
    
    Args:
        video_id: Video identifier
        session: Database session
    """
    try:
        video_service = VideoLibraryService()
        
        success = await video_service.delete_video(video_id, session)
        
        if not success:
            raise VRUDetectionException(
                "VIDEO_DELETION_FAILED",
                f"Failed to delete video {video_id}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    except VRUDetectionException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete video {video_id}: {e}")
        raise VRUDetectionException(
            "VIDEO_DELETION_FAILED",
            "Failed to delete video",
            details={"video_id": str(video_id), "error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.put("/{video_id}/status")
async def update_video_status(
    video_id: uuid.UUID,
    new_status: VideoStatus,
    session: AsyncSession = Depends(get_db)
) -> VideoResponse:
    """
    Update video processing status
    
    Args:
        video_id: Video identifier
        new_status: New status to set
        session: Database session
        
    Returns:
        Updated video details
    """
    try:
        video_service = VideoLibraryService()
        
        updated_video = await video_service.update_video_status(
            video_id, new_status, session
        )
        
        return VideoResponse.from_orm(updated_video)
        
    except VRUDetectionException:
        raise
    except Exception as e:
        logger.error(f"Failed to update video status {video_id}: {e}")
        raise VRUDetectionException(
            "VIDEO_STATUS_UPDATE_FAILED",
            "Failed to update video status",
            details={"video_id": str(video_id), "error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/{video_id}/download")
async def download_video(
    video_id: uuid.UUID,
    session: AsyncSession = Depends(get_db)
) -> FileResponse:
    """
    Download video file
    
    Args:
        video_id: Video identifier
        session: Database session
        
    Returns:
        Video file as download
    """
    try:
        video_service = VideoLibraryService()
        
        video = await video_service.get_video(video_id, session)
        
        if not video:
            raise VRUDetectionException(
                "VIDEO_NOT_FOUND",
                f"Video {video_id} not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Check if file exists
        from pathlib import Path
        file_path = Path(video.file_path)
        
        if not file_path.exists():
            raise VRUDetectionException(
                "VIDEO_FILE_NOT_FOUND",
                f"Video file not found: {video.file_path}",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        return FileResponse(
            path=str(file_path),
            filename=video.filename,
            media_type="video/mp4"
        )
        
    except VRUDetectionException:
        raise
    except Exception as e:
        logger.error(f"Failed to download video {video_id}: {e}")
        raise VRUDetectionException(
            "VIDEO_DOWNLOAD_FAILED",
            "Failed to download video",
            details={"video_id": str(video_id), "error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/{video_id}/stream")
async def stream_video(
    video_id: uuid.UUID,
    session: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """
    Stream video file for preview/playback
    
    Args:
        video_id: Video identifier
        session: Database session
        
    Returns:
        Streaming video response
    """
    try:
        video_service = VideoLibraryService()
        
        video = await video_service.get_video(video_id, session)
        
        if not video:
            raise VRUDetectionException(
                "VIDEO_NOT_FOUND",
                f"Video {video_id} not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Check if file exists
        from pathlib import Path
        file_path = Path(video.file_path)
        
        if not file_path.exists():
            raise VRUDetectionException(
                "VIDEO_FILE_NOT_FOUND",
                f"Video file not found: {video.file_path}",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        def generate_chunks():
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    yield chunk
        
        return StreamingResponse(
            generate_chunks(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"inline; filename={video.filename}",
                "Accept-Ranges": "bytes"
            }
        )
        
    except VRUDetectionException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream video {video_id}: {e}")
        raise VRUDetectionException(
            "VIDEO_STREAM_FAILED",
            "Failed to stream video",
            details={"video_id": str(video_id), "error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/{video_id}/statistics", response_model=VideoStatistics)
async def get_video_statistics(
    video_id: uuid.UUID,
    session: AsyncSession = Depends(get_db)
) -> VideoStatistics:
    """
    Get detailed statistics for a video
    
    Args:
        video_id: Video identifier
        session: Database session
        
    Returns:
        Video statistics including detection metrics
    """
    try:
        video_service = VideoLibraryService()
        
        video = await video_service.get_video(video_id, session)
        
        if not video:
            raise VRUDetectionException(
                "VIDEO_NOT_FOUND",
                f"Video {video_id} not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Get detection statistics if ground truth exists
        ground_truth_count = 0
        detection_count = 0
        test_sessions_count = 0
        
        if video.ground_truth_generated:
            from sqlalchemy import func
            from src.models.database import GroundTruthObject, DetectionEvent, TestSession
            
            # Count ground truth objects
            gt_query = select(func.count()).where(GroundTruthObject.video_id == video_id)
            gt_result = await session.execute(gt_query)
            ground_truth_count = gt_result.scalar()
            
            # Count detections across all test sessions for this video
            detection_query = select(func.count()).select_from(
                DetectionEvent.__table__.join(TestSession.__table__)
            ).where(TestSession.video_id == video_id)
            detection_result = await session.execute(detection_query)
            detection_count = detection_result.scalar()
            
            # Count test sessions
            sessions_query = select(func.count()).where(TestSession.video_id == video_id)
            sessions_result = await session.execute(sessions_query)
            test_sessions_count = sessions_result.scalar()
        
        return VideoStatistics(
            video_id=video_id,
            filename=video.filename,
            file_size_bytes=video.file_size,
            file_size_mb=round(video.file_size / (1024 * 1024), 2) if video.file_size else 0,
            duration_seconds=video.duration,
            duration_minutes=round(video.duration / 60, 2) if video.duration else 0,
            fps=video.fps,
            resolution=video.resolution,
            ground_truth_objects=ground_truth_count,
            total_detections=detection_count,
            test_sessions=test_sessions_count,
            processing_status=video.status
        )
        
    except VRUDetectionException:
        raise
    except Exception as e:
        logger.error(f"Failed to get video statistics {video_id}: {e}")
        raise VRUDetectionException(
            "VIDEO_STATISTICS_FAILED",
            "Failed to get video statistics",
            details={"video_id": str(video_id), "error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )