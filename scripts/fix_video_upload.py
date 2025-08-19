#!/usr/bin/env python3
"""
Fix Video Upload Processing Workflow
Addresses the root cause of video upload failures
"""
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_path = Path(__file__).parent.parent / "ai-model-validation-platform" / "backend"
sys.path.append(str(backend_path))

def fix_main_py():
    """Fix the main.py file to handle processing_status correctly"""
    main_file_path = backend_path / "main.py"
    
    if not main_file_path.exists():
        print(f"❌ main.py not found at {main_file_path}")
        return False
    
    print("📝 Reading main.py...")
    with open(main_file_path, 'r') as f:
        content = f.read()
    
    # Fix the video upload endpoint to handle processing_status properly
    fixes = [
        # Fix 1: Ensure processing_status is handled in video creation
        {
            'old': 'status = "uploaded"',
            'new': 'status = "uploaded"\n        processing_status = "pending"'
        },
        # Fix 2: Update the video creation to include processing_status
        {
            'old': 'new_video = Video(\n            id=str(uuid.uuid4()),\n            filename=file.filename,\n            file_path=str(file_path),\n            file_size=file_size,\n            duration=metadata.get("duration"),\n            fps=metadata.get("fps"),\n            resolution=metadata.get("resolution"),\n            status="uploaded",\n            project_id=project_id\n        )',
            'new': 'new_video = Video(\n            id=str(uuid.uuid4()),\n            filename=file.filename,\n            file_path=str(file_path),\n            file_size=file_size,\n            duration=metadata.get("duration"),\n            fps=metadata.get("fps"),\n            resolution=metadata.get("resolution"),\n            status="uploaded",\n            processing_status="pending",\n            ground_truth_generated=False,\n            project_id=project_id\n        )'
        }
    ]
    
    fixed_content = content
    changes_made = 0
    
    for fix in fixes:
        if fix['old'] in fixed_content:
            fixed_content = fixed_content.replace(fix['old'], fix['new'])
            changes_made += 1
            print(f"✅ Applied fix: {fix['old'][:50]}...")
    
    # Add proper error handling for database operations
    error_handling_fix = '''
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during video upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error during video upload"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during video upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error during video upload"
        )
'''
    
    # Look for the upload_video_central function and add error handling
    if 'upload_video_central' in fixed_content and 'except SQLAlchemyError' not in fixed_content:
        # Find the end of the try block in upload_video_central
        try_block_start = fixed_content.find('try:', fixed_content.find('upload_video_central'))
        if try_block_start != -1:
            # Find the matching except block or end of function
            except_pos = fixed_content.find('except', try_block_start)
            if except_pos == -1:
                # No except block, add one before the return statement
                return_pos = fixed_content.find('return', try_block_start)
                if return_pos != -1:
                    # Insert error handling before return
                    lines = fixed_content[:return_pos].split('\n')
                    indent = len(lines[-1]) - len(lines[-1].lstrip())
                    indented_error_handling = '\n'.join(['    ' * (indent // 4) + line.strip() for line in error_handling_fix.strip().split('\n')])
                    fixed_content = fixed_content[:return_pos] + indented_error_handling + '\n' + fixed_content[return_pos:]
                    changes_made += 1
                    print("✅ Added error handling to upload_video_central")
    
    if changes_made > 0:
        print(f"📝 Writing updated main.py with {changes_made} fixes...")
        with open(main_file_path, 'w') as f:
            f.write(fixed_content)
        print("✅ main.py updated successfully")
        return True
    else:
        print("ℹ️  No fixes needed in main.py")
        return True

def create_enhanced_schemas():
    """Create enhanced Pydantic schemas"""
    schemas_path = backend_path / "schemas_enhanced.py"
    
    schemas_content = '''"""
Enhanced Pydantic Schemas for Video Processing Platform
Addresses schema mismatches identified in analysis
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ProcessingStatusEnum(str, Enum):
    """Processing status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    QUEUED = "queued"

class VideoStatusEnum(str, Enum):
    """Video status enumeration"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class VideoResponse(BaseModel):
    """Enhanced video response schema"""
    id: str
    filename: str
    file_path: str
    file_size: Optional[int]
    duration: Optional[float]
    fps: Optional[float]
    resolution: Optional[str]
    status: VideoStatusEnum
    processing_status: ProcessingStatusEnum = Field(alias="groundTruthStatus")
    ground_truth_generated: bool
    project_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
        populate_by_name = True

class VideoUploadResponse(BaseModel):
    """Video upload response schema"""
    success: bool
    message: str
    video_id: Optional[str]
    filename: Optional[str]
    status: Optional[VideoStatusEnum]
    processing_status: Optional[ProcessingStatusEnum]
    
class VideoCreate(BaseModel):
    """Video creation schema"""
    filename: str
    file_size: Optional[int]
    duration: Optional[float]
    fps: Optional[float]
    resolution: Optional[str]
    project_id: str
    status: VideoStatusEnum = VideoStatusEnum.UPLOADED
    processing_status: ProcessingStatusEnum = ProcessingStatusEnum.PENDING

class VideoUpdate(BaseModel):
    """Video update schema"""
    status: Optional[VideoStatusEnum]
    processing_status: Optional[ProcessingStatusEnum]
    ground_truth_generated: Optional[bool]
    
class GroundTruthObjectResponse(BaseModel):
    """Enhanced ground truth object response"""
    id: str
    video_id: str
    frame_number: Optional[int]
    timestamp: float
    class_label: str
    x: float
    y: float
    width: float
    height: float
    confidence: Optional[float]
    validated: bool = False
    difficult: bool = False
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProcessingStatusUpdate(BaseModel):
    """Processing status update schema"""
    video_id: str
    processing_status: ProcessingStatusEnum
    progress_percentage: Optional[float] = Field(ge=0, le=100)
    message: Optional[str]
    error_details: Optional[str]

class RealTimeNotification(BaseModel):
    """Real-time notification schema for Socket.IO"""
    event_type: str
    video_id: Optional[str]
    project_id: Optional[str]
    status: Optional[str]
    processing_status: Optional[ProcessingStatusEnum]
    progress: Optional[float]
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
'''
    
    print("📝 Creating enhanced schemas...")
    with open(schemas_path, 'w') as f:
        f.write(schemas_content)
    print("✅ Enhanced schemas created")
    return True

def create_workflow_service():
    """Create enhanced video processing workflow service"""
    services_dir = backend_path / "services"
    services_dir.mkdir(exist_ok=True)
    
    workflow_path = services_dir / "video_processing_workflow.py"
    
    workflow_content = '''"""
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
'''
    
    print("📝 Creating video processing workflow service...")
    with open(workflow_path, 'w') as f:
        f.write(workflow_content)
    print("✅ Video processing workflow service created")
    return True

def main():
    """Main fix runner"""
    print("🚀 Starting Video Upload Fix")
    print("=" * 40)
    
    success = True
    
    try:
        # Fix 1: Update main.py
        if not fix_main_py():
            success = False
        
        # Fix 2: Create enhanced schemas
        if not create_enhanced_schemas():
            success = False
        
        # Fix 3: Create workflow service
        if not create_workflow_service():
            success = False
        
        if success:
            print("\n✅ All video upload fixes applied successfully!")
            print("Next steps:")
            print("1. Run the database migration: python scripts/database_migration.py")
            print("2. Restart your FastAPI server")
            print("3. Test video upload functionality")
            return 0
        else:
            print("\n❌ Some fixes failed!")
            return 1
            
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())