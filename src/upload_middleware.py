"""
FastAPI Upload Middleware and Endpoints
Integrates the enhanced upload service with FastAPI endpoints for chunked uploads,
progress tracking, and robust error handling.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, status, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from enhanced_upload_service import EnhancedUploadService, UploadConfiguration

logger = logging.getLogger(__name__)

# Global upload service instance
upload_service: Optional[EnhancedUploadService] = None


class ChunkedUploadRequest(BaseModel):
    """Request model for chunked upload initiation"""
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., gt=0, description="Total file size in bytes")
    content_type: str = Field(default="video/mp4", description="MIME type of the file")
    metadata: Optional[Dict] = Field(default=None, description="Optional metadata")


class ChunkUploadRequest(BaseModel):
    """Request model for individual chunk upload"""
    upload_id: str = Field(..., description="Upload session ID")
    chunk_number: int = Field(..., ge=0, description="Chunk sequence number")
    chunk_hash: Optional[str] = Field(default=None, description="Chunk hash for integrity check")
    hash_algorithm: str = Field(default="md5", description="Hash algorithm used")


class UploadResponse(BaseModel):
    """Standard upload response model"""
    success: bool
    upload_id: str
    message: str
    data: Optional[Dict] = None


class ProgressResponse(BaseModel):
    """Progress tracking response model"""
    upload_id: str
    progress_percentage: float
    uploaded_size: int
    total_size: int
    upload_speed_bps: Optional[float] = None
    estimated_time_remaining: Optional[float] = None


async def get_upload_service() -> EnhancedUploadService:
    """Dependency to get upload service instance"""
    global upload_service
    if upload_service is None:
        config = UploadConfiguration(
            max_file_size=500 * 1024 * 1024,  # 500MB
            chunk_size=5 * 1024 * 1024,      # 5MB chunks
            max_concurrent_chunks=3,
            upload_timeout=3600,              # 1 hour
            enable_integrity_check=True
        )
        upload_service = EnhancedUploadService(config)
    return upload_service


def create_upload_router() -> APIRouter:
    """Create FastAPI router with upload endpoints"""
    router = APIRouter(prefix="/api/uploads", tags=["Enhanced Uploads"])

    @router.post("/initiate", response_model=UploadResponse)
    async def initiate_chunked_upload(
        request: ChunkedUploadRequest,
        service: EnhancedUploadService = Depends(get_upload_service)
    ):
        """Initiate a new chunked upload session"""
        try:
            result = await service.initiate_upload(
                filename=request.filename,
                file_size=request.file_size,
                content_type=request.content_type,
                metadata=request.metadata
            )
            
            return UploadResponse(
                success=True,
                upload_id=result["upload_id"],
                message=f"Upload session initiated for {request.filename}",
                data=result
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error initiating upload: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initiate upload session"
            )

    @router.post("/chunk", response_model=UploadResponse)
    async def upload_chunk(
        upload_id: str = Form(...),
        chunk_number: int = Form(...),
        chunk_hash: Optional[str] = Form(default=None),
        hash_algorithm: str = Form(default="md5"),
        chunk_file: UploadFile = File(...),
        service: EnhancedUploadService = Depends(get_upload_service)
    ):
        """Upload a single chunk"""
        try:
            # Read chunk data
            chunk_data = await chunk_file.read()
            
            # Validate chunk file
            if not chunk_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Empty chunk data"
                )
            
            result = await service.upload_chunk(
                upload_id=upload_id,
                chunk_number=chunk_number,
                chunk_data=chunk_data,
                chunk_hash=chunk_hash,
                hash_algorithm=hash_algorithm
            )
            
            return UploadResponse(
                success=True,
                upload_id=upload_id,
                message=f"Chunk {chunk_number} uploaded successfully",
                data=result
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading chunk: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload chunk"
            )

    @router.get("/status/{upload_id}")
    async def get_upload_status(
        upload_id: str,
        service: EnhancedUploadService = Depends(get_upload_service)
    ):
        """Get upload status and progress"""
        status_data = await service.get_upload_status(upload_id)
        
        if not status_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Upload session {upload_id} not found"
            )
        
        return status_data

    @router.get("/progress/{upload_id}", response_model=ProgressResponse)
    async def get_upload_progress(
        upload_id: str,
        service: EnhancedUploadService = Depends(get_upload_service)
    ):
        """Get simplified progress information"""
        status_data = await service.get_upload_status(upload_id)
        
        if not status_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Upload session {upload_id} not found"
            )
        
        # Calculate estimated time remaining
        estimated_time_remaining = None
        if status_data["upload_speed_bps"] and status_data["uploaded_size"] < status_data["total_size"]:
            remaining_bytes = status_data["total_size"] - status_data["uploaded_size"]
            estimated_time_remaining = remaining_bytes / status_data["upload_speed_bps"]
        
        return ProgressResponse(
            upload_id=upload_id,
            progress_percentage=status_data["progress_percentage"],
            uploaded_size=status_data["uploaded_size"],
            total_size=status_data["total_size"],
            upload_speed_bps=status_data["upload_speed_bps"],
            estimated_time_remaining=estimated_time_remaining
        )

    @router.post("/retry/{upload_id}")
    async def retry_failed_chunks(
        upload_id: str,
        service: EnhancedUploadService = Depends(get_upload_service)
    ):
        """Retry failed chunks for an upload session"""
        try:
            result = await service.retry_failed_chunks(upload_id)
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrying chunks: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retry chunks"
            )

    @router.delete("/cancel/{upload_id}")
    async def cancel_upload(
        upload_id: str,
        service: EnhancedUploadService = Depends(get_upload_service)
    ):
        """Cancel an active upload"""
        success = await service.cancel_upload(upload_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Upload session {upload_id} not found"
            )
        
        return {
            "success": True,
            "upload_id": upload_id,
            "message": "Upload cancelled successfully"
        }

    @router.get("/statistics")
    async def get_upload_statistics(
        service: EnhancedUploadService = Depends(get_upload_service)
    ):
        """Get upload service statistics"""
        return await service.get_upload_statistics()

    # Legacy compatibility endpoints for existing system

    @router.post("/legacy/video", description="Legacy single-file upload endpoint")
    async def legacy_video_upload(
        file: UploadFile = File(...),
        project_id: Optional[str] = Form(default=None),
        background_tasks: BackgroundTasks = BackgroundTasks(),
        service: EnhancedUploadService = Depends(get_upload_service)
    ):
        """Legacy single-file upload with automatic chunking for large files"""
        try:
            # Read file size
            content = await file.read()
            file_size = len(content)
            
            # Reset file position
            await file.seek(0)
            
            # For small files, handle directly
            if file_size <= service.config.chunk_size:
                return await _handle_small_file_upload(file, content, project_id)
            
            # For large files, use chunked upload
            return await _handle_large_file_upload(file, content, file_size, project_id, service, background_tasks)
            
        except Exception as e:
            logger.error(f"Error in legacy upload: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {str(e)}"
            )

    async def _handle_small_file_upload(file: UploadFile, content: bytes, project_id: Optional[str]):
        """Handle small file upload directly"""
        # This would integrate with existing database storage
        # For now, return a compatible response
        return {
            "id": "legacy-upload-id",
            "filename": file.filename,
            "size": len(content),
            "status": "uploaded",
            "project_id": project_id,
            "message": "Small file uploaded successfully"
        }

    async def _handle_large_file_upload(
        file: UploadFile, 
        content: bytes, 
        file_size: int, 
        project_id: Optional[str], 
        service: EnhancedUploadService,
        background_tasks: BackgroundTasks
    ):
        """Handle large file upload using chunked upload"""
        try:
            # Initiate chunked upload
            init_result = await service.initiate_upload(
                filename=file.filename,
                file_size=file_size,
                content_type=file.content_type or "video/mp4"
            )
            
            upload_id = init_result["upload_id"]
            chunk_size = init_result["chunk_size"]
            
            # Upload chunks in background
            background_tasks.add_task(
                _upload_chunks_background,
                service, upload_id, content, chunk_size
            )
            
            return {
                "id": upload_id,
                "filename": file.filename,
                "size": file_size,
                "status": "uploading",
                "project_id": project_id,
                "message": "Large file upload started",
                "chunked_upload": True,
                "upload_id": upload_id
            }
            
        except Exception as e:
            logger.error(f"Error handling large file upload: {e}")
            raise

    async def _upload_chunks_background(
        service: EnhancedUploadService,
        upload_id: str,
        content: bytes,
        chunk_size: int
    ):
        """Background task to upload chunks"""
        try:
            total_size = len(content)
            chunk_number = 0
            offset = 0
            
            while offset < total_size:
                chunk_data = content[offset:offset + chunk_size]
                
                await service.upload_chunk(
                    upload_id=upload_id,
                    chunk_number=chunk_number,
                    chunk_data=chunk_data
                )
                
                offset += len(chunk_data)
                chunk_number += 1
                
            logger.info(f"Background upload completed for {upload_id}")
            
        except Exception as e:
            logger.error(f"Error in background upload for {upload_id}: {e}")

    return router


class UploadProgressTracker:
    """Track upload progress for WebSocket updates"""
    
    def __init__(self):
        self.subscribers: Dict[str, List] = {}
    
    def subscribe(self, upload_id: str, websocket):
        """Subscribe to upload progress updates"""
        if upload_id not in self.subscribers:
            self.subscribers[upload_id] = []
        self.subscribers[upload_id].append(websocket)
    
    def unsubscribe(self, upload_id: str, websocket):
        """Unsubscribe from upload progress updates"""
        if upload_id in self.subscribers:
            if websocket in self.subscribers[upload_id]:
                self.subscribers[upload_id].remove(websocket)
            if not self.subscribers[upload_id]:
                del self.subscribers[upload_id]
    
    async def broadcast_progress(self, upload_id: str, progress_data: Dict):
        """Broadcast progress update to subscribers"""
        if upload_id not in self.subscribers:
            return
        
        disconnected = []
        for websocket in self.subscribers[upload_id]:
            try:
                await websocket.send_json({
                    "type": "upload_progress",
                    "upload_id": upload_id,
                    "data": progress_data
                })
            except Exception:
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        for ws in disconnected:
            self.unsubscribe(upload_id, ws)


def create_websocket_router() -> APIRouter:
    """Create WebSocket router for real-time progress updates"""
    router = APIRouter()
    progress_tracker = UploadProgressTracker()
    
    @router.websocket("/ws/upload/{upload_id}")
    async def upload_progress_websocket(websocket, upload_id: str):
        """WebSocket endpoint for real-time upload progress"""
        await websocket.accept()
        progress_tracker.subscribe(upload_id, websocket)
        
        try:
            # Send initial status
            service = await get_upload_service()
            status_data = await service.get_upload_status(upload_id)
            if status_data:
                await websocket.send_json({
                    "type": "initial_status",
                    "upload_id": upload_id,
                    "data": status_data
                })
            
            # Keep connection alive and send periodic updates
            while True:
                await asyncio.sleep(1)  # Send updates every second
                
                status_data = await service.get_upload_status(upload_id)
                if status_data:
                    await websocket.send_json({
                        "type": "status_update",
                        "upload_id": upload_id,
                        "data": status_data
                    })
                    
                    # Close connection if upload is complete or failed
                    if status_data["status"] in ["completed", "failed", "cancelled"]:
                        break
                else:
                    break
                    
        except Exception as e:
            logger.error(f"WebSocket error for upload {upload_id}: {e}")
        finally:
            progress_tracker.unsubscribe(upload_id, websocket)
    
    return router