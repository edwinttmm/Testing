"""
Enhanced Video Upload Router with Chunked Upload Support

Provides comprehensive video upload endpoints with:
- Traditional single-request uploads (up to 100MB)
- Chunked uploads for large files (up to 1GB)
- Progress tracking and resume functionality
- Retry mechanisms with exponential backoff
- File integrity verification
"""

import os
import uuid
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, UploadFile, File, HTTPException, status, BackgroundTasks, Query, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime

# Import our enhanced upload service
from ..services.enhanced_upload_service import upload_service, UploadConfig, UploadProgress

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v2/videos", tags=["Enhanced Video Uploads"])

# Pydantic models for requests/responses
class ChunkedUploadInitRequest(BaseModel):
    """Request to initialize chunked upload"""
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., gt=0, description="Total file size in bytes")
    chunk_size: Optional[int] = Field(None, description="Preferred chunk size (optional)")

class ChunkedUploadInitResponse(BaseModel):
    """Response for chunked upload initialization"""
    upload_session_id: str
    total_chunks: int
    chunk_size: int
    expires_at: datetime
    upload_url: str

class ChunkUploadResponse(BaseModel):
    """Response for chunk upload"""
    status: str
    chunk_index: int
    progress: Dict[str, Any]
    next_chunk: Optional[int] = None

class UploadStatusResponse(BaseModel):
    """Upload status response"""
    status: str
    filename: str
    progress: Dict[str, Any]
    missing_chunks: List[int] = []

class UploadCompletionResponse(BaseModel):
    """Upload completion response"""
    status: str
    upload_session_id: str
    video_id: str
    filename: str
    secure_filename: str
    file_size: int
    checksum: str
    upload_time_seconds: float

@router.post("/upload/init", response_model=ChunkedUploadInitResponse)
async def init_chunked_upload(request: ChunkedUploadInitRequest):
    """
    Initialize a chunked upload session for large files
    
    This endpoint should be called first to set up a chunked upload.
    Returns an upload session ID and chunk information.
    """
    try:
        # Override chunk size if specified
        if request.chunk_size:
            upload_service.config.chunk_size = min(request.chunk_size, 1024 * 1024)  # Max 1MB chunks
        
        # Initialize upload session
        upload_session_id = await upload_service.start_chunked_upload(
            filename=request.filename,
            file_size=request.file_size
        )
        
        # Calculate total chunks
        total_chunks = (request.file_size + upload_service.config.chunk_size - 1) // upload_service.config.chunk_size
        
        # Set expiration (24 hours from now)
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        return ChunkedUploadInitResponse(
            upload_session_id=upload_session_id,
            total_chunks=total_chunks,
            chunk_size=upload_service.config.chunk_size,
            expires_at=expires_at,
            upload_url=f"/api/v2/videos/upload/chunk/{upload_session_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initialize chunked upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize upload: {str(e)}"
        )

@router.post("/upload/chunk/{upload_session_id}", response_model=ChunkUploadResponse)
async def upload_chunk(
    upload_session_id: str,
    chunk_index: int = Form(..., description="Chunk index (0-based)"),
    checksum: Optional[str] = Form(None, description="MD5 checksum for verification"),
    chunk: UploadFile = File(..., description="Chunk data")
):
    """
    Upload a single chunk for a chunked upload session
    
    Args:
        upload_session_id: Upload session identifier
        chunk_index: Index of the chunk (0-based)
        checksum: Optional MD5 checksum for integrity verification
        chunk: Chunk file data
        
    Returns:
        Upload status and progress information
    """
    try:
        # Read chunk data
        chunk_data = await chunk.read()
        
        # Upload the chunk
        result = await upload_service.upload_chunk(
            upload_session_id=upload_session_id,
            chunk_index=chunk_index,
            chunk_data=chunk_data,
            checksum=checksum
        )
        
        response = ChunkUploadResponse(
            status=result['status'],
            chunk_index=chunk_index,
            progress=result.get('progress', {}),
            next_chunk=chunk_index + 1 if result['status'] == 'chunk_uploaded' else None
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload chunk {chunk_index} for session {upload_session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload chunk: {str(e)}"
        )

@router.get("/upload/status/{upload_session_id}", response_model=UploadStatusResponse)
async def get_upload_status(upload_session_id: str):
    """
    Get the current status of an upload session
    
    Args:
        upload_session_id: Upload session identifier
        
    Returns:
        Current upload status and progress
    """
    try:
        status_info = upload_service.get_upload_status(upload_session_id)
        
        if status_info['status'] == 'not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload session not found"
            )
        
        return UploadStatusResponse(
            status=status_info['status'],
            filename=status_info['filename'],
            progress=status_info['progress'],
            missing_chunks=status_info.get('missing_chunks', [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get upload status for {upload_session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get upload status: {str(e)}"
        )

@router.delete("/upload/{upload_session_id}")
async def cancel_upload(upload_session_id: str):
    """
    Cancel an active upload session
    
    Args:
        upload_session_id: Upload session identifier
        
    Returns:
        Cancellation confirmation
    """
    try:
        result = upload_service.cancel_upload(upload_session_id)
        
        if result['status'] == 'not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload session not found"
            )
        
        return {"message": "Upload cancelled successfully", "status": result['status']}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel upload {upload_session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel upload: {str(e)}"
        )

@router.post("/upload/traditional")
async def upload_video_traditional(
    file: UploadFile = File(..., description="Video file to upload"),
    project_id: Optional[str] = Form(None, description="Optional project ID")
):
    """
    Traditional single-request video upload
    
    Recommended for files under 100MB. For larger files, use chunked upload.
    
    Args:
        file: Video file to upload
        project_id: Optional project ID to associate video with
        
    Returns:
        Upload completion details
    """
    try:
        # Track progress with a simple callback
        progress_updates = []
        
        def progress_callback(progress: UploadProgress):
            progress_updates.append({
                'percentage': progress.percentage,
                'bytes_uploaded': progress.bytes_uploaded,
                'upload_speed_mbps': progress.upload_speed_mbps,
                'eta_seconds': progress.eta_seconds
            })
        
        # Upload file using traditional method
        result = await upload_service.upload_file_traditional(
            file=file,
            progress_callback=progress_callback
        )
        
        # TODO: Integrate with database to create video record
        # For now, return upload details
        video_id = str(uuid.uuid4())  # Generate temporary ID
        
        response_data = {
            'video_id': video_id,
            'project_id': project_id,
            'filename': result['filename'],
            'secure_filename': result['secure_filename'],
            'file_size': result['file_size'],
            'checksum': result['checksum'],
            'upload_time_seconds': result['upload_time_seconds'],
            'status': 'completed',
            'progress_updates': len(progress_updates),
            'url': f"/uploads/{result['secure_filename']}",
            'created_at': datetime.utcnow().isoformat(),
            'message': 'Video uploaded successfully'
        }
        
        logger.info(f"Traditional upload completed: {result['filename']} ({result['file_size']} bytes)")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Traditional upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )

@router.post("/upload/resume/{upload_session_id}")
async def resume_upload(upload_session_id: str):
    """
    Resume a paused or interrupted chunked upload
    
    Args:
        upload_session_id: Upload session identifier
        
    Returns:
        Resume status and missing chunks
    """
    try:
        status_info = upload_service.get_upload_status(upload_session_id)
        
        if status_info['status'] == 'not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload session not found"
            )
        
        if status_info['status'] == 'completed':
            return {
                'message': 'Upload already completed',
                'status': 'completed'
            }
        
        missing_chunks = status_info.get('missing_chunks', [])
        
        return {
            'message': 'Upload ready to resume',
            'status': 'ready_to_resume',
            'missing_chunks': missing_chunks,
            'total_missing': len(missing_chunks),
            'progress': status_info['progress']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume upload {upload_session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume upload: {str(e)}"
        )

@router.get("/upload/config")
async def get_upload_config():
    """
    Get current upload configuration limits and settings
    
    Returns:
        Upload configuration information
    """
    config = upload_service.config
    
    return {
        'max_file_size_bytes': config.max_file_size,
        'max_file_size_mb': config.max_file_size / (1024 * 1024),
        'chunk_size_bytes': config.chunk_size,
        'chunk_size_kb': config.chunk_size / 1024,
        'max_retries': config.max_retries,
        'timeout_seconds': config.timeout_seconds,
        'allowed_extensions': config.allowed_extensions,
        'resumable_uploads_enabled': config.enable_resume,
        'progress_tracking_enabled': config.enable_progress_callback
    }

@router.post("/upload/cleanup")
async def cleanup_expired_sessions(
    max_age_hours: int = Query(24, description="Maximum age in hours for cleanup")
):
    """
    Clean up expired upload sessions
    
    Args:
        max_age_hours: Maximum age in hours before cleanup (default: 24)
        
    Returns:
        Number of sessions cleaned up
    """
    try:
        cleaned_count = upload_service.cleanup_expired_sessions(max_age_hours)
        
        return {
            'message': f'Cleaned up {cleaned_count} expired upload sessions',
            'cleaned_sessions': cleaned_count,
            'max_age_hours': max_age_hours
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup sessions: {str(e)}"
        )

# Error handlers for specific upload errors
@router.exception_handler(HTTPException)
async def upload_exception_handler(request, exc: HTTPException):
    """Enhanced error handling for upload operations"""
    
    # Map common upload errors to user-friendly messages
    error_mappings = {
        413: "File too large. Please use chunked upload for files over 100MB.",
        415: "Unsupported file type. Only video files are allowed.",
        408: "Upload timeout. Please try again or use chunked upload for large files.",
        400: "Invalid upload request. Please check your file and try again.",
        500: "Server error during upload. Please try again later."
    }
    
    user_message = error_mappings.get(exc.status_code, exc.detail)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            'error': True,
            'message': user_message,
            'detail': exc.detail,
            'status_code': exc.status_code,
            'type': 'upload_error',
            'recommendations': get_upload_recommendations(exc.status_code),
            'timestamp': datetime.utcnow().isoformat()
        }
    )

def get_upload_recommendations(status_code: int) -> List[str]:
    """Get recommendations based on error type"""
    recommendations = {
        413: [
            "Use chunked upload for files larger than 100MB",
            "Compress your video file if possible",
            "Split large files into smaller segments"
        ],
        415: [
            "Ensure your file has a video extension (.mp4, .avi, .mov, .mkv, .webm)",
            "Convert your file to a supported video format"
        ],
        408: [
            "Use chunked upload for better reliability",
            "Check your internet connection",
            "Try uploading during off-peak hours"
        ],
        400: [
            "Verify your file is not corrupted",
            "Check that the filename doesn't contain special characters",
            "Ensure the file size is accurate"
        ],
        500: [
            "Wait a moment and try again",
            "Use chunked upload for better error recovery",
            "Contact support if the problem persists"
        ]
    }
    
    return recommendations.get(status_code, ["Please try again later"])

# Add router to main app
# This should be imported and included in the main FastAPI app