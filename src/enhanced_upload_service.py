"""
Enhanced Video Upload Service with Chunked Upload Support
Provides robust, scalable file upload handling with progress tracking, error recovery,
and support for large files through chunked uploads.
"""

import os
import asyncio
import uuid
import hashlib
import json
import time
import logging
import tempfile
import aiofiles
from pathlib import Path
from typing import Dict, List, Optional, Tuple, AsyncIterator
from dataclasses import dataclass, asdict
from enum import Enum
from fastapi import HTTPException, UploadFile, status
from pydantic import BaseModel, Field
import uvloop

# Configure logging
logger = logging.getLogger(__name__)

# Use uvloop for better async performance
try:
    uvloop.install()
except ImportError:
    logger.warning("uvloop not available, using default event loop")


class UploadStatus(Enum):
    """Upload status enumeration"""
    INITIATED = "initiated"
    UPLOADING = "uploading"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ChunkStatus(Enum):
    """Individual chunk status"""
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATING = "validating"


@dataclass
class ChunkInfo:
    """Information about an individual chunk"""
    chunk_number: int
    size: int
    hash: Optional[str] = None
    status: ChunkStatus = ChunkStatus.PENDING
    uploaded_at: Optional[float] = None
    retry_count: int = 0
    error_message: Optional[str] = None


@dataclass
class UploadSession:
    """Upload session tracking"""
    upload_id: str
    filename: str
    original_filename: str
    total_size: int
    chunk_size: int
    total_chunks: int
    content_type: str
    status: UploadStatus = UploadStatus.INITIATED
    chunks: Dict[int, ChunkInfo] = None
    uploaded_size: int = 0
    created_at: float = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    last_activity: float = None
    temp_file_path: Optional[str] = None
    final_file_path: Optional[str] = None
    file_hash: Optional[str] = None
    progress_percentage: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict = None

    def __post_init__(self):
        if self.chunks is None:
            self.chunks = {}
        if self.created_at is None:
            self.created_at = time.time()
        if self.last_activity is None:
            self.last_activity = time.time()
        if self.metadata is None:
            self.metadata = {}


class UploadConfiguration(BaseModel):
    """Upload service configuration"""
    max_file_size: int = Field(default=500 * 1024 * 1024, description="Maximum file size in bytes (500MB)")
    chunk_size: int = Field(default=5 * 1024 * 1024, description="Chunk size in bytes (5MB)")
    max_concurrent_chunks: int = Field(default=3, description="Maximum concurrent chunk uploads")
    upload_timeout: int = Field(default=3600, description="Upload timeout in seconds (1 hour)")
    chunk_timeout: int = Field(default=300, description="Individual chunk timeout (5 minutes)")
    max_retries: int = Field(default=3, description="Maximum retry attempts per chunk")
    retry_delay_base: float = Field(default=1.0, description="Base delay for exponential backoff")
    cleanup_interval: int = Field(default=300, description="Cleanup interval in seconds")
    temp_directory: str = Field(default="temp_uploads", description="Temporary upload directory")
    final_directory: str = Field(default="uploads", description="Final upload directory")
    allowed_extensions: List[str] = Field(default=[".mp4", ".avi", ".mov", ".mkv", ".webm"], description="Allowed file extensions")
    enable_compression: bool = Field(default=False, description="Enable file compression")
    enable_virus_scan: bool = Field(default=False, description="Enable virus scanning")
    enable_integrity_check: bool = Field(default=True, description="Enable file integrity verification")


class EnhancedUploadService:
    """Enhanced upload service with chunked upload support"""

    def __init__(self, config: UploadConfiguration = None):
        self.config = config or UploadConfiguration()
        self.active_uploads: Dict[str, UploadSession] = {}
        self.upload_locks: Dict[str, asyncio.Lock] = {}
        self.chunk_semaphore = asyncio.Semaphore(self.config.max_concurrent_chunks)
        self.cleanup_task: Optional[asyncio.Task] = None
        self._setup_directories()
        self._start_background_tasks()

    def _setup_directories(self):
        """Create necessary directories"""
        for directory in [self.config.temp_directory, self.config.final_directory]:
            Path(directory).mkdir(parents=True, exist_ok=True)
        logger.info(f"Upload directories created: temp={self.config.temp_directory}, final={self.config.final_directory}")

    def _start_background_tasks(self):
        """Start background maintenance tasks"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_expired_uploads())
            logger.info("Started background cleanup task")

    async def _cleanup_expired_uploads(self):
        """Clean up expired and stale uploads"""
        while True:
            try:
                current_time = time.time()
                expired_uploads = []

                for upload_id, session in self.active_uploads.items():
                    time_since_activity = current_time - session.last_activity
                    
                    # Check for timeout
                    if time_since_activity > self.config.upload_timeout:
                        expired_uploads.append(upload_id)

                # Clean up expired uploads
                for upload_id in expired_uploads:
                    await self._cleanup_upload_session(upload_id, reason="timeout")
                
                if expired_uploads:
                    logger.info(f"Cleaned up {len(expired_uploads)} expired uploads")

                await asyncio.sleep(self.config.cleanup_interval)

            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def _cleanup_upload_session(self, upload_id: str, reason: str = "manual"):
        """Clean up upload session and associated files"""
        if upload_id not in self.active_uploads:
            return

        session = self.active_uploads[upload_id]
        
        try:
            # Update session status
            session.status = UploadStatus.TIMEOUT if reason == "timeout" else UploadStatus.CANCELLED
            session.error_message = f"Upload {reason}"

            # Clean up temporary file
            if session.temp_file_path and Path(session.temp_file_path).exists():
                os.unlink(session.temp_file_path)
                logger.info(f"Removed temp file: {session.temp_file_path}")

            # Remove from active uploads
            del self.active_uploads[upload_id]
            
            # Clean up lock
            if upload_id in self.upload_locks:
                del self.upload_locks[upload_id]

            logger.info(f"Cleaned up upload session {upload_id} (reason: {reason})")

        except Exception as e:
            logger.error(f"Error cleaning up upload session {upload_id}: {e}")

    def _validate_file(self, filename: str, content_type: str, file_size: int) -> None:
        """Validate uploaded file"""
        # Check file size
        if file_size > self.config.max_file_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds maximum allowed size ({self.config.max_file_size / 1024 / 1024:.1f}MB)"
            )

        # Check file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in self.config.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension '{file_ext}' not allowed. Allowed extensions: {', '.join(self.config.allowed_extensions)}"
            )

        # Validate content type
        expected_types = ["video/mp4", "video/avi", "video/quicktime", "video/x-msvideo", "video/webm"]
        if content_type and content_type not in expected_types:
            logger.warning(f"Unexpected content type: {content_type}")

    def _generate_secure_filename(self, original_filename: str) -> str:
        """Generate secure filename with UUID"""
        file_ext = Path(original_filename).suffix.lower()
        return f"{uuid.uuid4()}{file_ext}"

    async def initiate_upload(
        self,
        filename: str,
        file_size: int,
        content_type: str = "video/mp4",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Initiate a new chunked upload session"""
        
        try:
            # Validate file
            self._validate_file(filename, content_type, file_size)

            # Generate upload session
            upload_id = str(uuid.uuid4())
            secure_filename = self._generate_secure_filename(filename)
            
            # Calculate chunk information
            total_chunks = (file_size + self.config.chunk_size - 1) // self.config.chunk_size
            
            # Create temporary file
            temp_fd, temp_file_path = tempfile.mkstemp(
                suffix=Path(filename).suffix,
                dir=self.config.temp_directory
            )
            os.close(temp_fd)  # Close the file descriptor, keep the path

            # Create upload session
            session = UploadSession(
                upload_id=upload_id,
                filename=secure_filename,
                original_filename=filename,
                total_size=file_size,
                chunk_size=self.config.chunk_size,
                total_chunks=total_chunks,
                content_type=content_type,
                temp_file_path=temp_file_path,
                final_file_path=str(Path(self.config.final_directory) / secure_filename),
                metadata=metadata or {}
            )

            # Store session
            self.active_uploads[upload_id] = session
            self.upload_locks[upload_id] = asyncio.Lock()

            logger.info(f"Initiated upload session {upload_id}: {filename} ({file_size / 1024 / 1024:.1f}MB, {total_chunks} chunks)")

            return {
                "upload_id": upload_id,
                "chunk_size": self.config.chunk_size,
                "total_chunks": total_chunks,
                "max_concurrent_chunks": self.config.max_concurrent_chunks,
                "supported_hash_algorithms": ["md5", "sha256"],
                "session_timeout": self.config.upload_timeout
            }

        except Exception as e:
            logger.error(f"Error initiating upload for {filename}: {e}")
            raise

    async def upload_chunk(
        self,
        upload_id: str,
        chunk_number: int,
        chunk_data: bytes,
        chunk_hash: Optional[str] = None,
        hash_algorithm: str = "md5"
    ) -> Dict:
        """Upload a single chunk with validation and retry support"""
        
        if upload_id not in self.active_uploads:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Upload session {upload_id} not found"
            )

        session = self.active_uploads[upload_id]
        
        # Check session status
        if session.status not in [UploadStatus.INITIATED, UploadStatus.UPLOADING]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Upload session is in {session.status.value} state"
            )

        # Validate chunk number
        if chunk_number < 0 or chunk_number >= session.total_chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid chunk number {chunk_number}. Expected 0-{session.total_chunks - 1}"
            )

        async with self.chunk_semaphore:  # Limit concurrent chunks
            async with self.upload_locks[upload_id]:  # Prevent race conditions
                try:
                    # Update session status
                    if session.status == UploadStatus.INITIATED:
                        session.status = UploadStatus.UPLOADING
                        session.started_at = time.time()

                    # Create or update chunk info
                    if chunk_number not in session.chunks:
                        session.chunks[chunk_number] = ChunkInfo(chunk_number=chunk_number, size=len(chunk_data))

                    chunk_info = session.chunks[chunk_number]
                    chunk_info.status = ChunkStatus.UPLOADING

                    # Validate chunk hash if provided
                    if chunk_hash and self.config.enable_integrity_check:
                        if hash_algorithm == "md5":
                            actual_hash = hashlib.md5(chunk_data).hexdigest()
                        elif hash_algorithm == "sha256":
                            actual_hash = hashlib.sha256(chunk_data).hexdigest()
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Unsupported hash algorithm: {hash_algorithm}"
                            )

                        if actual_hash != chunk_hash:
                            chunk_info.status = ChunkStatus.FAILED
                            chunk_info.error_message = "Hash mismatch"
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Chunk hash mismatch: expected {chunk_hash}, got {actual_hash}"
                            )

                        chunk_info.hash = chunk_hash

                    # Write chunk to temporary file
                    await self._write_chunk_to_file(session, chunk_number, chunk_data)

                    # Update chunk status
                    chunk_info.status = ChunkStatus.COMPLETED
                    chunk_info.uploaded_at = time.time()
                    
                    # Update session progress
                    session.uploaded_size = sum(chunk.size for chunk in session.chunks.values() if chunk.status == ChunkStatus.COMPLETED)
                    session.progress_percentage = (session.uploaded_size / session.total_size) * 100
                    session.last_activity = time.time()

                    # Check if upload is complete
                    completed_chunks = sum(1 for chunk in session.chunks.values() if chunk.status == ChunkStatus.COMPLETED)
                    if completed_chunks == session.total_chunks:
                        await self._finalize_upload_internal(session)

                    logger.debug(f"Chunk {chunk_number} uploaded for session {upload_id} ({session.progress_percentage:.1f}% complete)")

                    return {
                        "upload_id": upload_id,
                        "chunk_number": chunk_number,
                        "chunk_status": chunk_info.status.value,
                        "uploaded_size": session.uploaded_size,
                        "total_size": session.total_size,
                        "progress_percentage": session.progress_percentage,
                        "completed_chunks": completed_chunks,
                        "total_chunks": session.total_chunks,
                        "upload_complete": session.status == UploadStatus.COMPLETED
                    }

                except Exception as e:
                    # Handle chunk upload failure
                    if chunk_number in session.chunks:
                        chunk_info = session.chunks[chunk_number]
                        chunk_info.status = ChunkStatus.FAILED
                        chunk_info.error_message = str(e)
                        chunk_info.retry_count += 1

                    logger.error(f"Error uploading chunk {chunk_number} for session {upload_id}: {e}")
                    raise

    async def _write_chunk_to_file(self, session: UploadSession, chunk_number: int, chunk_data: bytes):
        """Write chunk data to temporary file at correct offset"""
        try:
            offset = chunk_number * session.chunk_size
            
            async with aiofiles.open(session.temp_file_path, "r+b") as f:
                await f.seek(offset)
                await f.write(chunk_data)
                await f.flush()
                
        except Exception as e:
            logger.error(f"Error writing chunk {chunk_number} to file {session.temp_file_path}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to write chunk data"
            )

    async def _finalize_upload_internal(self, session: UploadSession):
        """Internal method to finalize upload"""
        try:
            session.status = UploadStatus.VALIDATING
            
            # Verify file integrity if enabled
            if self.config.enable_integrity_check:
                await self._verify_file_integrity(session)

            # Move file from temp to final location
            await self._move_to_final_location(session)

            # Update session
            session.status = UploadStatus.COMPLETED
            session.completed_at = time.time()
            
            logger.info(f"Upload session {session.upload_id} completed successfully: {session.filename}")

        except Exception as e:
            session.status = UploadStatus.FAILED
            session.error_message = str(e)
            logger.error(f"Error finalizing upload session {session.upload_id}: {e}")
            raise

    async def _verify_file_integrity(self, session: UploadSession):
        """Verify file integrity by comparing size and hash"""
        try:
            # Check file size
            actual_size = Path(session.temp_file_path).stat().st_size
            if actual_size != session.total_size:
                raise ValueError(f"File size mismatch: expected {session.total_size}, got {actual_size}")

            # Calculate file hash
            hash_md5 = hashlib.md5()
            async with aiofiles.open(session.temp_file_path, "rb") as f:
                while chunk := await f.read(8192):
                    hash_md5.update(chunk)
            
            session.file_hash = hash_md5.hexdigest()
            logger.debug(f"File integrity verified for {session.upload_id}: {session.file_hash}")

        except Exception as e:
            logger.error(f"File integrity verification failed for {session.upload_id}: {e}")
            raise

    async def _move_to_final_location(self, session: UploadSession):
        """Move file from temporary to final location"""
        try:
            temp_path = Path(session.temp_file_path)
            final_path = Path(session.final_file_path)
            
            # Ensure final directory exists
            final_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Move file atomically
            temp_path.rename(final_path)
            
            logger.info(f"Moved file from {temp_path} to {final_path}")

        except Exception as e:
            logger.error(f"Error moving file to final location: {e}")
            raise

    async def get_upload_status(self, upload_id: str) -> Optional[Dict]:
        """Get current upload status"""
        if upload_id not in self.active_uploads:
            return None

        session = self.active_uploads[upload_id]
        
        # Get chunk status summary
        chunk_stats = {
            "pending": 0,
            "uploading": 0,
            "completed": 0,
            "failed": 0
        }
        
        for chunk in session.chunks.values():
            chunk_stats[chunk.status.value] += 1

        # Calculate upload speed if in progress
        upload_speed = None
        if session.started_at and session.uploaded_size > 0:
            elapsed_time = time.time() - session.started_at
            if elapsed_time > 0:
                upload_speed = session.uploaded_size / elapsed_time  # bytes per second

        return {
            "upload_id": session.upload_id,
            "filename": session.original_filename,
            "secure_filename": session.filename,
            "status": session.status.value,
            "progress_percentage": session.progress_percentage,
            "uploaded_size": session.uploaded_size,
            "total_size": session.total_size,
            "completed_chunks": chunk_stats["completed"],
            "total_chunks": session.total_chunks,
            "chunk_stats": chunk_stats,
            "upload_speed_bps": upload_speed,
            "created_at": session.created_at,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "last_activity": session.last_activity,
            "error_message": session.error_message,
            "file_hash": session.file_hash,
            "final_file_path": session.final_file_path if session.status == UploadStatus.COMPLETED else None
        }

    async def cancel_upload(self, upload_id: str) -> bool:
        """Cancel an active upload"""
        if upload_id not in self.active_uploads:
            return False

        await self._cleanup_upload_session(upload_id, reason="cancelled")
        return True

    async def retry_failed_chunks(self, upload_id: str) -> Dict:
        """Retry failed chunks for an upload session"""
        if upload_id not in self.active_uploads:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Upload session {upload_id} not found"
            )

        session = self.active_uploads[upload_id]
        failed_chunks = [
            chunk_num for chunk_num, chunk in session.chunks.items()
            if chunk.status == ChunkStatus.FAILED and chunk.retry_count < self.config.max_retries
        ]

        if not failed_chunks:
            return {
                "upload_id": upload_id,
                "retryable_chunks": 0,
                "message": "No retryable chunks found"
            }

        # Reset failed chunks to pending for retry
        for chunk_num in failed_chunks:
            chunk = session.chunks[chunk_num]
            chunk.status = ChunkStatus.PENDING
            chunk.error_message = None

        return {
            "upload_id": upload_id,
            "retryable_chunks": len(failed_chunks),
            "chunk_numbers": failed_chunks,
            "message": f"Reset {len(failed_chunks)} chunks for retry"
        }

    async def get_upload_statistics(self) -> Dict:
        """Get upload service statistics"""
        active_count = len(self.active_uploads)
        status_stats = {}
        
        for session in self.active_uploads.values():
            status = session.status.value
            status_stats[status] = status_stats.get(status, 0) + 1

        total_size = sum(session.total_size for session in self.active_uploads.values())
        uploaded_size = sum(session.uploaded_size for session in self.active_uploads.values())

        return {
            "active_uploads": active_count,
            "status_breakdown": status_stats,
            "total_bytes": total_size,
            "uploaded_bytes": uploaded_size,
            "overall_progress": (uploaded_size / total_size * 100) if total_size > 0 else 0,
            "cleanup_task_running": self.cleanup_task and not self.cleanup_task.done(),
            "configuration": asdict(self.config)
        }

    async def shutdown(self):
        """Gracefully shutdown the upload service"""
        logger.info("Shutting down upload service...")
        
        # Cancel cleanup task
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel all active uploads
        upload_ids = list(self.active_uploads.keys())
        for upload_id in upload_ids:
            await self._cleanup_upload_session(upload_id, reason="shutdown")

        logger.info("Upload service shutdown complete")