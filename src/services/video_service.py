"""
Video Library Management Service
Handles video upload, storage, metadata extraction, and organization
"""

import asyncio
import hashlib
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, BinaryIO, AsyncGenerator

import aiofiles
import cv2
import numpy as np
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.models.database import Video, Project, VideoStatus
from src.core.exceptions import VRUDetectionException
from src.utils.file_utils import ensure_directory_exists, get_file_hash, validate_file_extension

logger = logging.getLogger(__name__)


class VideoMetadata:
    """Video metadata container"""
    def __init__(
        self,
        duration: float,
        frame_count: int,
        fps: float,
        resolution: Tuple[int, int],
        codec: str,
        bitrate: int,
        file_size: int,
        creation_time: Optional[datetime] = None
    ):
        self.duration = duration
        self.frame_count = frame_count
        self.fps = fps
        self.resolution = resolution
        self.codec = codec
        self.bitrate = bitrate
        self.file_size = file_size
        self.creation_time = creation_time or datetime.utcnow()


class VideoValidationResult:
    """Video validation result container"""
    def __init__(self, is_valid: bool, errors: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []


class VideoProcessingResult:
    """Video processing result container"""
    def __init__(
        self,
        video_id: uuid.UUID,
        status: str,
        file_path: str,
        metadata: VideoMetadata,
        estimated_completion: Optional[datetime] = None
    ):
        self.video_id = video_id
        self.status = status
        self.file_path = file_path
        self.metadata = metadata
        self.estimated_completion = estimated_completion


class VideoLibraryService:
    """Video library management service"""
    
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.storage_dir = settings.VIDEO_STORAGE_DIR
        self.allowed_formats = settings.ALLOWED_VIDEO_FORMATS
        self.max_file_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024  # Convert to bytes
        
        # Ensure directories exist
        ensure_directory_exists(self.upload_dir)
        ensure_directory_exists(self.storage_dir)
    
    async def upload_video(
        self,
        file: UploadFile,
        project_id: uuid.UUID,
        session: AsyncSession
    ) -> VideoProcessingResult:
        """
        Upload and process a video file
        
        Args:
            file: Uploaded video file
            project_id: Associated project ID
            session: Database session
            
        Returns:
            VideoProcessingResult with processing details
        """
        try:
            # Validate project exists
            project = await self._get_project(project_id, session)
            if not project:
                raise VRUDetectionException(
                    "PROJECT_NOT_FOUND",
                    f"Project {project_id} not found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Validate file
            validation_result = await self._validate_video_file(file)
            if not validation_result.is_valid:
                raise VRUDetectionException(
                    "INVALID_VIDEO_FILE",
                    "Video file validation failed",
                    details={"errors": validation_result.errors},
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate unique filename
            file_extension = Path(file.filename).suffix.lower()
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            
            # Create project-specific storage directory
            project_storage_dir = self.storage_dir / str(project_id)
            ensure_directory_exists(project_storage_dir)
            
            storage_path = project_storage_dir / unique_filename
            
            # Save file to storage
            await self._save_uploaded_file(file, storage_path)
            
            # Extract metadata
            metadata = await self._extract_video_metadata(storage_path)
            
            # Create database record
            video_record = Video(
                filename=file.filename,
                file_path=str(storage_path),
                file_size=metadata.file_size,
                duration=metadata.duration,
                fps=metadata.fps,
                resolution=f"{metadata.resolution[0]}x{metadata.resolution[1]}",
                status=VideoStatus.UPLOADED,
                project_id=project_id
            )
            
            session.add(video_record)
            await session.commit()
            await session.refresh(video_record)
            
            logger.info(f"Video uploaded successfully: {video_record.id}")
            
            # Queue for processing
            await self._queue_video_for_processing(video_record.id)
            
            return VideoProcessingResult(
                video_id=video_record.id,
                status=VideoStatus.UPLOADED.value,
                file_path=str(storage_path),
                metadata=metadata,
                estimated_completion=self._estimate_processing_time(metadata.duration)
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
    
    async def get_video(self, video_id: uuid.UUID, session: AsyncSession) -> Optional[Video]:
        """Get video by ID with project information"""
        try:
            query = select(Video).options(selectinload(Video.project)).where(Video.id == video_id)
            result = await session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get video {video_id}: {e}")
            raise VRUDetectionException(
                "VIDEO_RETRIEVAL_FAILED",
                "Failed to retrieve video",
                details={"video_id": str(video_id), "error": str(e)}
            )
    
    async def list_videos(
        self,
        project_id: Optional[uuid.UUID] = None,
        status_filter: Optional[VideoStatus] = None,
        limit: int = 100,
        offset: int = 0,
        session: AsyncSession = None
    ) -> List[Video]:
        """List videos with optional filtering"""
        try:
            query = select(Video).options(selectinload(Video.project))
            
            # Apply filters
            if project_id:
                query = query.where(Video.project_id == project_id)
            
            if status_filter:
                query = query.where(Video.status == status_filter)
            
            # Apply pagination
            query = query.offset(offset).limit(limit)
            
            # Order by creation date (newest first)
            query = query.order_by(Video.created_at.desc())
            
            result = await session.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to list videos: {e}")
            raise VRUDetectionException(
                "VIDEO_LIST_FAILED",
                "Failed to list videos",
                details={"error": str(e)}
            )
    
    async def delete_video(self, video_id: uuid.UUID, session: AsyncSession) -> bool:
        """Delete video and associated files"""
        try:
            # Get video record
            video = await self.get_video(video_id, session)
            if not video:
                raise VRUDetectionException(
                    "VIDEO_NOT_FOUND",
                    f"Video {video_id} not found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Check if video is being processed
            if video.status == VideoStatus.PROCESSING:
                raise VRUDetectionException(
                    "VIDEO_BEING_PROCESSED",
                    "Cannot delete video while it's being processed",
                    status_code=status.HTTP_409_CONFLICT
                )
            
            # Delete file from storage
            if video.file_path and Path(video.file_path).exists():
                try:
                    os.remove(video.file_path)
                    logger.info(f"Deleted video file: {video.file_path}")
                except OSError as e:
                    logger.warning(f"Failed to delete video file {video.file_path}: {e}")
            
            # Delete database record (cascade will handle related records)
            await session.delete(video)
            await session.commit()
            
            logger.info(f"Video deleted successfully: {video_id}")
            return True
            
        except VRUDetectionException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete video {video_id}: {e}")
            raise VRUDetectionException(
                "VIDEO_DELETION_FAILED",
                "Failed to delete video",
                details={"video_id": str(video_id), "error": str(e)}
            )
    
    async def update_video_status(
        self,
        video_id: uuid.UUID,
        new_status: VideoStatus,
        session: AsyncSession
    ) -> Video:
        """Update video processing status"""
        try:
            query = update(Video).where(Video.id == video_id).values(status=new_status)
            await session.execute(query)
            await session.commit()
            
            # Return updated video
            return await self.get_video(video_id, session)
            
        except Exception as e:
            logger.error(f"Failed to update video status {video_id}: {e}")
            raise VRUDetectionException(
                "VIDEO_STATUS_UPDATE_FAILED",
                "Failed to update video status",
                details={"video_id": str(video_id), "error": str(e)}
            )
    
    async def get_video_stream(self, video_id: uuid.UUID, session: AsyncSession) -> AsyncGenerator[np.ndarray, None]:
        """
        Stream video frames for processing
        
        Args:
            video_id: Video identifier
            session: Database session
            
        Yields:
            Video frames as numpy arrays
        """
        video = await self.get_video(video_id, session)
        if not video:
            raise VRUDetectionException(
                "VIDEO_NOT_FOUND",
                f"Video {video_id} not found"
            )
        
        if not Path(video.file_path).exists():
            raise VRUDetectionException(
                "VIDEO_FILE_NOT_FOUND",
                f"Video file not found: {video.file_path}"
            )
        
        # Open video with OpenCV
        cap = cv2.VideoCapture(video.file_path)
        
        try:
            frame_number = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_number += 1
                yield frame
                
                # Add small delay to prevent overwhelming the system
                if frame_number % 30 == 0:  # Every second at 30fps
                    await asyncio.sleep(0.001)  # 1ms delay
                    
        finally:
            cap.release()
    
    async def _validate_video_file(self, file: UploadFile) -> VideoValidationResult:
        """Validate uploaded video file"""
        errors = []
        
        # Check file extension
        if not validate_file_extension(file.filename, self.allowed_formats):
            errors.append(f"Unsupported file format. Allowed: {', '.join(self.allowed_formats)}")
        
        # Check file size
        if hasattr(file, 'size') and file.size > self.max_file_size:
            errors.append(f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB")
        
        # Check if file is empty
        if hasattr(file, 'size') and file.size == 0:
            errors.append("File is empty")
        
        # Additional validation can be added here (e.g., checking file headers)
        
        return VideoValidationResult(is_valid=len(errors) == 0, errors=errors)
    
    async def _save_uploaded_file(self, file: UploadFile, destination: Path) -> None:
        """Save uploaded file to destination"""
        try:
            # Reset file pointer
            await file.seek(0)
            
            # Save file in chunks to handle large files
            async with aiofiles.open(destination, 'wb') as f:
                chunk_size = 8192  # 8KB chunks
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    await f.write(chunk)
            
            logger.info(f"File saved to: {destination}")
            
        except Exception as e:
            # Clean up partial file on error
            if destination.exists():
                destination.unlink()
            raise e
    
    async def _extract_video_metadata(self, file_path: Path) -> VideoMetadata:
        """Extract metadata from video file using OpenCV"""
        try:
            cap = cv2.VideoCapture(str(file_path))
            
            if not cap.isOpened():
                raise ValueError(f"Cannot open video file: {file_path}")
            
            # Get video properties
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Calculate duration
            duration = frame_count / fps if fps > 0 else 0
            
            # Get file size
            file_size = file_path.stat().st_size
            
            # Estimate bitrate
            bitrate = int((file_size * 8) / duration) if duration > 0 else 0
            
            # Get codec (approximation)
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
            
            cap.release()
            
            return VideoMetadata(
                duration=duration,
                frame_count=frame_count,
                fps=fps,
                resolution=(width, height),
                codec=codec,
                bitrate=bitrate,
                file_size=file_size
            )
            
        except Exception as e:
            logger.error(f"Failed to extract video metadata: {e}")
            raise VRUDetectionException(
                "METADATA_EXTRACTION_FAILED",
                "Failed to extract video metadata",
                details={"file_path": str(file_path), "error": str(e)}
            )
    
    async def _get_project(self, project_id: uuid.UUID, session: AsyncSession) -> Optional[Project]:
        """Get project by ID"""
        query = select(Project).where(Project.id == project_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    async def _queue_video_for_processing(self, video_id: uuid.UUID) -> None:
        """Queue video for background processing"""
        # This would integrate with a task queue (Redis, Celery, etc.)
        # For now, just log the action
        logger.info(f"Video {video_id} queued for processing")
        
        # TODO: Integrate with actual task queue
        # await task_queue.enqueue('process_video', video_id)
    
    def _estimate_processing_time(self, duration: float) -> datetime:
        """Estimate processing completion time based on video duration"""
        # Rough estimate: 2x video duration for processing
        processing_minutes = duration * 2 / 60
        estimated_completion = datetime.utcnow()
        estimated_completion = estimated_completion.replace(
            minute=estimated_completion.minute + int(processing_minutes)
        )
        return estimated_completion
    
    async def get_video_statistics(self, project_id: Optional[uuid.UUID], session: AsyncSession) -> Dict:
        """Get video library statistics"""
        try:
            base_query = select(Video)
            
            if project_id:
                base_query = base_query.where(Video.project_id == project_id)
            
            # Total videos
            total_result = await session.execute(
                select(func.count()).select_from(base_query.subquery())
            )
            total_videos = total_result.scalar()
            
            # Videos by status
            status_result = await session.execute(
                select(Video.status, func.count()).
                select_from(base_query.subquery()).
                group_by(Video.status)
            )
            status_counts = dict(status_result.all())
            
            # Total storage size
            size_result = await session.execute(
                select(func.sum(Video.file_size)).select_from(base_query.subquery())
            )
            total_size = size_result.scalar() or 0
            
            # Average duration
            duration_result = await session.execute(
                select(func.avg(Video.duration)).select_from(base_query.subquery())
            )
            avg_duration = duration_result.scalar() or 0
            
            return {
                "total_videos": total_videos,
                "status_distribution": status_counts,
                "total_storage_bytes": total_size,
                "total_storage_gb": round(total_size / (1024**3), 2),
                "average_duration_seconds": round(avg_duration, 2),
                "average_duration_minutes": round(avg_duration / 60, 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to get video statistics: {e}")
            raise VRUDetectionException(
                "STATISTICS_FAILED",
                "Failed to get video statistics",
                details={"error": str(e)}
            )


# Utility functions
def calculate_video_hash(file_path: Path) -> str:
    """Calculate hash of video file for deduplication"""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


async def cleanup_orphaned_files(storage_dir: Path, session: AsyncSession) -> int:
    """Clean up files that exist on disk but not in database"""
    try:
        # Get all video file paths from database
        result = await session.execute(select(Video.file_path))
        db_files = {Path(file_path) for file_path, in result.all()}
        
        # Get all files in storage directory
        storage_files = set()
        for file_path in storage_dir.rglob("*"):
            if file_path.is_file():
                storage_files.add(file_path)
        
        # Find orphaned files
        orphaned_files = storage_files - db_files
        
        # Remove orphaned files
        removed_count = 0
        for orphaned_file in orphaned_files:
            try:
                orphaned_file.unlink()
                removed_count += 1
                logger.info(f"Removed orphaned file: {orphaned_file}")
            except OSError as e:
                logger.warning(f"Failed to remove orphaned file {orphaned_file}: {e}")
        
        return removed_count
        
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned files: {e}")
        return 0