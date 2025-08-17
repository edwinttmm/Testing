"""
Pydantic schemas for Video management
"""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator

from src.models.database import VideoStatus


class VideoResponse(BaseModel):
    """Schema for video response"""
    id: uuid.UUID = Field(..., description="Video ID")
    filename: str = Field(..., description="Original filename")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    duration: Optional[float] = Field(None, description="Duration in seconds")
    fps: Optional[float] = Field(None, description="Frames per second")
    resolution: Optional[str] = Field(None, description="Video resolution")
    status: VideoStatus = Field(..., description="Processing status")
    ground_truth_generated: bool = Field(False, description="Whether ground truth data exists")
    project_id: uuid.UUID = Field(..., description="Associated project ID")
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    @property
    def file_size_mb(self) -> Optional[float]:
        """File size in MB"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None
    
    @property
    def duration_minutes(self) -> Optional[float]:
        """Duration in minutes"""
        if self.duration:
            return round(self.duration / 60, 2)
        return None
    
    class Config:
        from_attributes = True


class VideoUploadResponse(BaseModel):
    """Schema for video upload response"""
    video_id: uuid.UUID = Field(..., description="Uploaded video ID")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Processing status")
    file_size: int = Field(..., description="File size in bytes")
    duration: float = Field(..., description="Duration in seconds")
    fps: float = Field(..., description="Frames per second")
    resolution: str = Field(..., description="Video resolution")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated processing completion")
    message: str = Field(..., description="Upload status message")
    
    @property
    def file_size_mb(self) -> float:
        """File size in MB"""
        return round(self.file_size / (1024 * 1024), 2)
    
    @property
    def duration_minutes(self) -> float:
        """Duration in minutes"""
        return round(self.duration / 60, 2)


class VideoList(BaseModel):
    """Schema for paginated video list"""
    videos: List[VideoResponse] = Field(..., description="List of videos")
    total: int = Field(..., ge=0, description="Total number of videos")
    limit: int = Field(..., ge=1, description="Items per page")
    offset: int = Field(..., ge=0, description="Number of items skipped")
    
    @property
    def has_more(self) -> bool:
        """Check if there are more items available"""
        return self.offset + len(self.videos) < self.total


class VideoStatistics(BaseModel):
    """Detailed video statistics"""
    video_id: uuid.UUID = Field(..., description="Video ID")
    filename: str = Field(..., description="Video filename")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    file_size_mb: float = Field(..., ge=0, description="File size in MB")
    duration_seconds: float = Field(..., ge=0, description="Duration in seconds")
    duration_minutes: float = Field(..., ge=0, description="Duration in minutes")
    fps: Optional[float] = Field(None, description="Frames per second")
    resolution: Optional[str] = Field(None, description="Video resolution")
    ground_truth_objects: int = Field(..., ge=0, description="Number of ground truth objects")
    total_detections: int = Field(..., ge=0, description="Total detections across all sessions")
    test_sessions: int = Field(..., ge=0, description="Number of test sessions using this video")
    processing_status: VideoStatus = Field(..., description="Current processing status")


class VideoSummary(BaseModel):
    """Lightweight video summary for listings"""
    id: uuid.UUID
    filename: str
    duration: Optional[float]
    status: VideoStatus
    ground_truth_generated: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class VideoMetadataResponse(BaseModel):
    """Video metadata response"""
    duration: float = Field(..., ge=0, description="Duration in seconds")
    frame_count: int = Field(..., ge=0, description="Total number of frames")
    fps: float = Field(..., gt=0, description="Frames per second")
    resolution: tuple[int, int] = Field(..., description="Video resolution (width, height)")
    codec: str = Field(..., description="Video codec")
    bitrate: int = Field(..., ge=0, description="Bitrate in bits per second")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    
    @validator('resolution')
    def validate_resolution(cls, v):
        """Validate resolution tuple"""
        if len(v) != 2 or v[0] <= 0 or v[1] <= 0:
            raise ValueError('Resolution must be a tuple of two positive integers')
        return v


class VideoProcessingProgress(BaseModel):
    """Video processing progress information"""
    video_id: uuid.UUID = Field(..., description="Video ID")
    status: VideoStatus = Field(..., description="Current processing status")
    progress_percentage: float = Field(..., ge=0, le=100, description="Processing progress percentage")
    current_step: str = Field(..., description="Current processing step")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    frames_processed: int = Field(..., ge=0, description="Number of frames processed")
    total_frames: int = Field(..., ge=0, description="Total number of frames")
    processing_speed_fps: float = Field(..., ge=0, description="Processing speed in FPS")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")


class VideoQualityMetrics(BaseModel):
    """Video quality assessment metrics"""
    video_id: uuid.UUID = Field(..., description="Video ID")
    overall_quality_score: float = Field(..., ge=0, le=1, description="Overall quality score (0-1)")
    brightness_score: float = Field(..., ge=0, le=1, description="Brightness quality score")
    contrast_score: float = Field(..., ge=0, le=1, description="Contrast quality score")
    sharpness_score: float = Field(..., ge=0, le=1, description="Sharpness quality score")
    noise_level: float = Field(..., ge=0, le=1, description="Noise level (0=clean, 1=noisy)")
    motion_blur_score: float = Field(..., ge=0, le=1, description="Motion blur assessment")
    compression_artifacts: float = Field(..., ge=0, le=1, description="Compression artifacts level")
    frame_consistency: float = Field(..., ge=0, le=1, description="Frame-to-frame consistency")
    recommendations: List[str] = Field(default_factory=list, description="Quality improvement recommendations")