"""
Enhanced Video Processing Workflow Service
Handles the complete video processing pipeline with real-time updates
"""
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from models import Video, GroundTruthObject
from schemas_enhanced import ProcessingStatusEnum, RealTimeNotification
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class VideoProcessingWorkflow:
    """Enhanced video processing workflow with real-time updates"""
    
    def __init__(self, db: Session, socketio_instance=None):
        self.db = db
        self.socketio = socketio_instance
    
    async def update_processing_status(
        self,
        video_id: str,
        status: ProcessingStatusEnum,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        error_details: Optional[str] = None
    ) -> bool:
        """Update video processing status with real-time notifications"""
        try:
            # Update database
            video = self.db.query(Video).filter(Video.id == video_id).first()
            if not video:
                logger.error(f"Video {video_id} not found")
                return False
            
            video.processing_status = status.value
            
            # Handle completion
            if status == ProcessingStatusEnum.COMPLETED:
                video.ground_truth_generated = True
                video.status = "completed"
            elif status == ProcessingStatusEnum.FAILED:
                video.status = "failed"
            
            self.db.commit()
            
            # Send real-time notification
            if self.socketio:
                notification = RealTimeNotification(
                    event_type="processing_status_update",
                    video_id=video_id,
                    project_id=video.project_id,
                    processing_status=status,
                    progress=progress,
                    message=message or f"Status updated to {status.value}"
                )
                
                await self.socketio.emit(
                    "video_processing_update",
                    notification.dict(),
                    room=f"project_{video.project_id}"
                )
            
            logger.info(f"Updated video {video_id} status to {status.value}")
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error updating video status: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating video status: {e}")
            return False
    
    async def start_processing(self, video_id: str) -> bool:
        """Start video processing workflow"""
        try:
            # Update status to processing
            await self.update_processing_status(
                video_id,
                ProcessingStatusEnum.PROCESSING,
                progress=0.0,
                message="Starting video processing..."
            )
            
            # Simulate processing steps
            processing_steps = [
                (10.0, "Extracting video metadata..."),
                (30.0, "Generating ground truth annotations..."),
                (60.0, "Processing object detection..."),
                (80.0, "Validating results..."),
                (100.0, "Processing completed!")
            ]
            
            for progress, message in processing_steps:
                await asyncio.sleep(1)  # Simulate processing time
                await self.update_processing_status(
                    video_id,
                    ProcessingStatusEnum.PROCESSING,
                    progress=progress,
                    message=message
                )
            
            # Mark as completed
            await self.update_processing_status(
                video_id,
                ProcessingStatusEnum.COMPLETED,
                progress=100.0,
                message="Video processing completed successfully!"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing video {video_id}: {e}")
            await self.update_processing_status(
                video_id,
                ProcessingStatusEnum.FAILED,
                message="Processing failed",
                error_details=str(e)
            )
            return False
    
    def get_processing_status(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get current processing status"""
        try:
            video = self.db.query(Video).filter(Video.id == video_id).first()
            if not video:
                return None
            
            return {
                "video_id": video_id,
                "status": video.status,
                "processing_status": video.processing_status,
                "ground_truth_generated": video.ground_truth_generated,
                "created_at": video.created_at,
                "updated_at": video.updated_at
            }
            
        except Exception as e:
            logger.error(f"Error getting processing status for {video_id}: {e}")
            return None
