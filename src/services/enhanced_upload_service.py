"""
Enhanced File Upload Service with Chunked Upload Support

This service provides robust file upload capabilities with:
- Chunked uploads for large files (up to 1GB)
- Progress tracking and resume functionality
- Memory optimization
- Retry mechanisms
- Comprehensive error handling
"""

import os
import uuid
import hashlib
import tempfile
import asyncio
import aiofiles
from typing import Optional, Dict, Callable, Any, List
from dataclasses import dataclass
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
import logging

logger = logging.getLogger(__name__)

@dataclass
class UploadConfig:
    """Configuration for upload operations"""
    max_file_size: int = 1024 * 1024 * 1024  # 1GB default
    chunk_size: int = 64 * 1024  # 64KB chunks for optimal memory usage
    max_retries: int = 3
    timeout_seconds: int = 300  # 5 minutes timeout
    allowed_extensions: List[str] = None
    upload_directory: str = "uploads"
    temp_directory: str = None
    enable_resume: bool = True
    enable_progress_callback: bool = True

    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        if self.temp_directory is None:
            self.temp_directory = os.path.join(self.upload_directory, '.tmp')

@dataclass
class UploadProgress:
    """Upload progress information"""
    bytes_uploaded: int
    total_bytes: int
    percentage: float
    chunks_completed: int
    total_chunks: int
    upload_speed_mbps: float
    eta_seconds: int
    status: str  # 'uploading', 'paused', 'completed', 'failed', 'resuming'

@dataclass
class ChunkInfo:
    """Information about a file chunk"""
    chunk_id: str
    start_byte: int
    end_byte: int
    size: int
    checksum: str
    uploaded: bool = False
    retry_count: int = 0

class EnhancedUploadService:
    """Enhanced file upload service with chunked upload support"""
    
    def __init__(self, config: UploadConfig = None):
        self.config = config or UploadConfig()
        self._active_uploads: Dict[str, Dict] = {}
        self._setup_directories()
        
    def _setup_directories(self):
        """Create necessary directories"""
        os.makedirs(self.config.upload_directory, exist_ok=True)
        os.makedirs(self.config.temp_directory, exist_ok=True)
        logger.info(f"Upload directories configured: {self.config.upload_directory}, {self.config.temp_directory}")
    
    def _validate_file(self, filename: str, file_size: int) -> None:
        """Validate file before upload"""
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename cannot be empty"
            )
        
        # Validate file extension
        file_extension = Path(filename).suffix.lower()
        if file_extension not in self.config.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Supported: {', '.join(self.config.allowed_extensions)}"
            )
        
        # Validate file size
        if file_size > self.config.max_file_size:
            max_size_mb = self.config.max_file_size / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {max_size_mb:.1f}MB"
            )
        
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file not allowed"
            )
    
    def _generate_secure_filename(self, original_filename: str) -> str:
        """Generate secure UUID-based filename"""
        file_extension = Path(original_filename).suffix.lower()
        return f"{uuid.uuid4()}{file_extension}"
    
    def _calculate_chunks(self, file_size: int) -> List[ChunkInfo]:
        """Calculate chunk information for a file"""
        chunks = []
        total_chunks = (file_size + self.config.chunk_size - 1) // self.config.chunk_size
        
        for i in range(total_chunks):
            start_byte = i * self.config.chunk_size
            end_byte = min(start_byte + self.config.chunk_size, file_size)
            chunk_size = end_byte - start_byte
            
            chunk = ChunkInfo(
                chunk_id=f"{i:06d}",
                start_byte=start_byte,
                end_byte=end_byte,
                size=chunk_size,
                checksum=""  # Will be calculated during upload
            )
            chunks.append(chunk)
        
        return chunks
    
    def _calculate_chunk_checksum(self, chunk_data: bytes) -> str:
        """Calculate MD5 checksum for chunk integrity"""
        return hashlib.md5(chunk_data).hexdigest()
    
    async def _write_chunk_async(self, temp_file_path: str, chunk_data: bytes, start_pos: int) -> None:
        """Asynchronously write chunk to temporary file"""
        async with aiofiles.open(temp_file_path, 'r+b') as f:
            await f.seek(start_pos)
            await f.write(chunk_data)
            await f.flush()
    
    async def start_chunked_upload(
        self,
        filename: str,
        file_size: int,
        progress_callback: Optional[Callable[[UploadProgress], None]] = None
    ) -> str:
        """
        Initialize a chunked upload session
        
        Args:
            filename: Original filename
            file_size: Total file size in bytes
            progress_callback: Optional callback for progress updates
            
        Returns:
            upload_session_id: Unique identifier for the upload session
        """
        self._validate_file(filename, file_size)
        
        upload_session_id = str(uuid.uuid4())
        secure_filename = self._generate_secure_filename(filename)
        temp_file_path = os.path.join(self.config.temp_directory, f"{upload_session_id}.tmp")
        final_file_path = os.path.join(self.config.upload_directory, secure_filename)
        
        # Calculate chunks
        chunks = self._calculate_chunks(file_size)
        
        # Create temporary file with correct size
        with open(temp_file_path, 'wb') as f:
            f.seek(file_size - 1)
            f.write(b'\0')
        
        # Store upload session info
        self._active_uploads[upload_session_id] = {
            'filename': filename,
            'secure_filename': secure_filename,
            'file_size': file_size,
            'temp_file_path': temp_file_path,
            'final_file_path': final_file_path,
            'chunks': chunks,
            'progress_callback': progress_callback,
            'bytes_uploaded': 0,
            'start_time': asyncio.get_event_loop().time(),
            'status': 'ready'
        }
        
        logger.info(f"Started chunked upload session {upload_session_id}: {filename} ({file_size} bytes, {len(chunks)} chunks)")
        return upload_session_id
    
    async def upload_chunk(
        self,
        upload_session_id: str,
        chunk_index: int,
        chunk_data: bytes,
        checksum: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a single chunk
        
        Args:
            upload_session_id: Upload session identifier
            chunk_index: Index of the chunk (0-based)
            chunk_data: Chunk data bytes
            checksum: Optional MD5 checksum for verification
            
        Returns:
            Dictionary with upload status and progress
        """
        if upload_session_id not in self._active_uploads:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload session not found"
            )
        
        session = self._active_uploads[upload_session_id]
        chunks = session['chunks']
        
        if chunk_index >= len(chunks):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid chunk index"
            )
        
        chunk = chunks[chunk_index]
        
        # Verify chunk data size
        if len(chunk_data) != chunk.size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chunk size mismatch. Expected: {chunk.size}, got: {len(chunk_data)}"
            )
        
        # Verify checksum if provided
        calculated_checksum = self._calculate_chunk_checksum(chunk_data)
        if checksum and checksum != calculated_checksum:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chunk checksum verification failed"
            )
        
        chunk.checksum = calculated_checksum
        
        # Write chunk to temporary file
        try:
            await self._write_chunk_async(session['temp_file_path'], chunk_data, chunk.start_byte)
            chunk.uploaded = True
            session['bytes_uploaded'] += chunk.size
            session['status'] = 'uploading'
            
            logger.debug(f"Uploaded chunk {chunk_index} for session {upload_session_id}")
            
        except Exception as e:
            chunk.retry_count += 1
            logger.error(f"Failed to upload chunk {chunk_index} for session {upload_session_id}: {e}")
            
            if chunk.retry_count >= self.config.max_retries:
                session['status'] = 'failed'
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload chunk after {self.config.max_retries} retries"
                )
            
            return {
                'status': 'retry_required',
                'chunk_index': chunk_index,
                'retry_count': chunk.retry_count,
                'max_retries': self.config.max_retries
            }
        
        # Calculate progress
        progress = self._calculate_progress(session)
        
        # Call progress callback if provided
        if session['progress_callback']:
            try:
                session['progress_callback'](progress)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
        
        # Check if upload is complete
        if all(chunk.uploaded for chunk in chunks):
            return await self._finalize_upload(upload_session_id)
        
        return {
            'status': 'chunk_uploaded',
            'chunk_index': chunk_index,
            'progress': {
                'percentage': progress.percentage,
                'bytes_uploaded': progress.bytes_uploaded,
                'total_bytes': progress.total_bytes,
                'chunks_completed': progress.chunks_completed,
                'total_chunks': progress.total_chunks,
                'upload_speed_mbps': progress.upload_speed_mbps,
                'eta_seconds': progress.eta_seconds
            }
        }
    
    def _calculate_progress(self, session: Dict) -> UploadProgress:
        """Calculate upload progress"""
        chunks = session['chunks']
        completed_chunks = sum(1 for chunk in chunks if chunk.uploaded)
        total_chunks = len(chunks)
        bytes_uploaded = session['bytes_uploaded']
        total_bytes = session['file_size']
        
        percentage = (bytes_uploaded / total_bytes) * 100 if total_bytes > 0 else 0
        
        # Calculate upload speed
        elapsed_time = asyncio.get_event_loop().time() - session['start_time']
        upload_speed_bps = bytes_uploaded / elapsed_time if elapsed_time > 0 else 0
        upload_speed_mbps = upload_speed_bps / (1024 * 1024)
        
        # Calculate ETA
        remaining_bytes = total_bytes - bytes_uploaded
        eta_seconds = remaining_bytes / upload_speed_bps if upload_speed_bps > 0 else 0
        
        return UploadProgress(
            bytes_uploaded=bytes_uploaded,
            total_bytes=total_bytes,
            percentage=percentage,
            chunks_completed=completed_chunks,
            total_chunks=total_chunks,
            upload_speed_mbps=upload_speed_mbps,
            eta_seconds=int(eta_seconds),
            status=session['status']
        )
    
    async def _finalize_upload(self, upload_session_id: str) -> Dict[str, Any]:
        """Finalize upload by moving temp file to final location"""
        session = self._active_uploads[upload_session_id]
        
        try:
            # Move temp file to final location atomically
            os.rename(session['temp_file_path'], session['final_file_path'])
            
            session['status'] = 'completed'
            
            # Calculate final file checksum for integrity
            file_checksum = await self._calculate_file_checksum(session['final_file_path'])
            
            result = {
                'status': 'upload_completed',
                'upload_session_id': upload_session_id,
                'filename': session['filename'],
                'secure_filename': session['secure_filename'],
                'file_path': session['final_file_path'],
                'file_size': session['file_size'],
                'checksum': file_checksum,
                'chunks_uploaded': len(session['chunks']),
                'upload_time_seconds': asyncio.get_event_loop().time() - session['start_time']
            }
            
            logger.info(f"Upload completed: {upload_session_id} -> {session['final_file_path']}")
            
            # Clean up session after successful completion
            del self._active_uploads[upload_session_id]
            
            return result
            
        except Exception as e:
            session['status'] = 'failed'
            logger.error(f"Failed to finalize upload {upload_session_id}: {e}")
            
            # Clean up temp file on error
            try:
                if os.path.exists(session['temp_file_path']):
                    os.unlink(session['temp_file_path'])
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temp file: {cleanup_error}")
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to finalize upload: {str(e)}"
            )
    
    async def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate MD5 checksum of final file"""
        hasher = hashlib.md5()
        async with aiofiles.open(file_path, 'rb') as f:
            while True:
                chunk = await f.read(self.config.chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    
    async def upload_file_traditional(
        self,
        file: UploadFile,
        progress_callback: Optional[Callable[[UploadProgress], None]] = None
    ) -> Dict[str, Any]:
        """
        Traditional single-request file upload with progress tracking
        
        Args:
            file: FastAPI UploadFile object
            progress_callback: Optional progress callback
            
        Returns:
            Upload result dictionary
        """
        # Get file size
        file_size = 0
        if hasattr(file, 'size') and file.size:
            file_size = file.size
        else:
            # Calculate size by reading file
            current_pos = await file.seek(0, 2)  # Seek to end
            file_size = await file.tell()
            await file.seek(0)  # Reset to beginning
        
        self._validate_file(file.filename, file_size)
        
        secure_filename = self._generate_secure_filename(file.filename)
        temp_file_path = os.path.join(self.config.temp_directory, f"{uuid.uuid4()}.tmp")
        final_file_path = os.path.join(self.config.upload_directory, secure_filename)
        
        bytes_written = 0
        start_time = asyncio.get_event_loop().time()
        
        try:
            async with aiofiles.open(temp_file_path, 'wb') as temp_file:
                while True:
                    # Read chunk from uploaded file
                    chunk = await file.read(self.config.chunk_size)
                    if not chunk:
                        break
                    
                    # Check size limit during upload
                    bytes_written += len(chunk)
                    if bytes_written > self.config.max_file_size:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File exceeds maximum size limit"
                        )
                    
                    # Write chunk to temp file
                    await temp_file.write(chunk)
                    
                    # Update progress
                    if progress_callback:
                        elapsed_time = asyncio.get_event_loop().time() - start_time
                        upload_speed_bps = bytes_written / elapsed_time if elapsed_time > 0 else 0
                        upload_speed_mbps = upload_speed_bps / (1024 * 1024)
                        remaining_bytes = file_size - bytes_written if file_size > 0 else 0
                        eta_seconds = remaining_bytes / upload_speed_bps if upload_speed_bps > 0 else 0
                        
                        progress = UploadProgress(
                            bytes_uploaded=bytes_written,
                            total_bytes=file_size,
                            percentage=(bytes_written / file_size) * 100 if file_size > 0 else 0,
                            chunks_completed=bytes_written // self.config.chunk_size,
                            total_chunks=(file_size + self.config.chunk_size - 1) // self.config.chunk_size if file_size > 0 else 1,
                            upload_speed_mbps=upload_speed_mbps,
                            eta_seconds=int(eta_seconds),
                            status='uploading'
                        )
                        
                        try:
                            progress_callback(progress)
                        except Exception as e:
                            logger.warning(f"Progress callback failed: {e}")
                
                # Ensure all data is written to disk
                await temp_file.flush()
            
            # Validate minimum file size
            if bytes_written == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Empty file not allowed"
                )
            
            # Move temp file to final location atomically
            os.rename(temp_file_path, final_file_path)
            
            # Calculate file checksum
            file_checksum = await self._calculate_file_checksum(final_file_path)
            
            upload_time = asyncio.get_event_loop().time() - start_time
            
            result = {
                'status': 'upload_completed',
                'filename': file.filename,
                'secure_filename': secure_filename,
                'file_path': final_file_path,
                'file_size': bytes_written,
                'checksum': file_checksum,
                'upload_time_seconds': upload_time
            }
            
            logger.info(f"Traditional upload completed: {file.filename} -> {final_file_path} ({bytes_written} bytes)")
            return result
            
        except HTTPException:
            # Clean up temp file on HTTP exceptions
            if os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
            raise
            
        except Exception as e:
            # Clean up temp file on unexpected errors
            if os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
            
            logger.error(f"Traditional upload failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {str(e)}"
            )
    
    def get_upload_status(self, upload_session_id: str) -> Dict[str, Any]:
        """Get status of an active upload session"""
        if upload_session_id not in self._active_uploads:
            return {'status': 'not_found'}
        
        session = self._active_uploads[upload_session_id]
        progress = self._calculate_progress(session)
        
        return {
            'status': session['status'],
            'filename': session['filename'],
            'progress': {
                'percentage': progress.percentage,
                'bytes_uploaded': progress.bytes_uploaded,
                'total_bytes': progress.total_bytes,
                'chunks_completed': progress.chunks_completed,
                'total_chunks': progress.total_chunks,
                'upload_speed_mbps': progress.upload_speed_mbps,
                'eta_seconds': progress.eta_seconds
            },
            'missing_chunks': [
                i for i, chunk in enumerate(session['chunks'])
                if not chunk.uploaded
            ]
        }
    
    def cancel_upload(self, upload_session_id: str) -> Dict[str, str]:
        """Cancel an active upload session"""
        if upload_session_id not in self._active_uploads:
            return {'status': 'not_found'}
        
        session = self._active_uploads[upload_session_id]
        
        # Clean up temp file
        try:
            if os.path.exists(session['temp_file_path']):
                os.unlink(session['temp_file_path'])
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file during cancellation: {e}")
        
        # Remove from active uploads
        del self._active_uploads[upload_session_id]
        
        logger.info(f"Upload session cancelled: {upload_session_id}")
        return {'status': 'cancelled'}
    
    def cleanup_expired_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up expired upload sessions"""
        current_time = asyncio.get_event_loop().time()
        max_age_seconds = max_age_hours * 3600
        
        expired_sessions = []
        for session_id, session in self._active_uploads.items():
            if current_time - session['start_time'] > max_age_seconds:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            try:
                self.cancel_upload(session_id)
            except Exception as e:
                logger.error(f"Failed to cleanup expired session {session_id}: {e}")
        
        logger.info(f"Cleaned up {len(expired_sessions)} expired upload sessions")
        return len(expired_sessions)

# Global instance
upload_service = EnhancedUploadService()