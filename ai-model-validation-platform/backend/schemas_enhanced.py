"""
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
