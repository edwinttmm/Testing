"""
Pydantic schemas for Project management
"""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator

from src.models.database import ProjectStatus, CameraView, SignalType


class ProjectBase(BaseModel):
    """Base project schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=1000, description="Project description")
    camera_model: str = Field(..., min_length=1, max_length=100, description="Camera model")
    camera_view: CameraView = Field(..., description="Camera view type")
    lens_type: Optional[str] = Field(None, max_length=50, description="Lens type")
    resolution: Optional[str] = Field(None, max_length=20, description="Video resolution")
    frame_rate: Optional[int] = Field(None, ge=1, le=120, description="Frame rate in FPS")
    signal_type: SignalType = Field(..., description="Signal input type")


class ProjectCreate(ProjectBase):
    """Schema for creating a new project"""
    status: Optional[ProjectStatus] = Field(ProjectStatus.ACTIVE, description="Project status")
    owner_id: Optional[uuid.UUID] = Field(None, description="Project owner ID")


class ProjectUpdate(BaseModel):
    """Schema for updating a project"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=1000, description="Project description")
    camera_model: Optional[str] = Field(None, min_length=1, max_length=100, description="Camera model")
    camera_view: Optional[CameraView] = Field(None, description="Camera view type")
    lens_type: Optional[str] = Field(None, max_length=50, description="Lens type")
    resolution: Optional[str] = Field(None, max_length=20, description="Video resolution")
    frame_rate: Optional[int] = Field(None, ge=1, le=120, description="Frame rate in FPS")
    signal_type: Optional[SignalType] = Field(None, description="Signal input type")
    status: Optional[ProjectStatus] = Field(None, description="Project status")
    owner_id: Optional[uuid.UUID] = Field(None, description="Project owner ID")


class OwnerInfo(BaseModel):
    """Owner information schema"""
    id: uuid.UUID
    email: str
    full_name: str
    
    class Config:
        from_attributes = True


class ProjectResponse(ProjectBase):
    """Schema for project response"""
    id: uuid.UUID = Field(..., description="Project ID")
    status: ProjectStatus = Field(..., description="Project status")
    owner_id: Optional[uuid.UUID] = Field(None, description="Project owner ID")
    owner: Optional[OwnerInfo] = Field(None, description="Owner information")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    # Computed fields
    total_videos: Optional[int] = Field(None, description="Total number of videos")
    total_test_sessions: Optional[int] = Field(None, description="Total number of test sessions")
    
    class Config:
        from_attributes = True


class ProjectList(BaseModel):
    """Schema for paginated project list"""
    projects: List[ProjectResponse] = Field(..., description="List of projects")
    total: int = Field(..., ge=0, description="Total number of projects")
    limit: int = Field(..., ge=1, description="Items per page")
    offset: int = Field(..., ge=0, description="Number of items skipped")
    
    @property
    def has_more(self) -> bool:
        """Check if there are more items available"""
        return self.offset + len(self.projects) < self.total


class ProjectStatistics(BaseModel):
    """Detailed project statistics"""
    project_id: uuid.UUID = Field(..., description="Project ID")
    total_videos: int = Field(..., ge=0, description="Total number of videos")
    total_storage_bytes: int = Field(..., ge=0, description="Total storage used in bytes")
    average_video_duration: float = Field(..., ge=0, description="Average video duration in seconds")
    total_test_sessions: int = Field(..., ge=0, description="Total number of test sessions")
    completed_sessions: int = Field(..., ge=0, description="Number of completed sessions")
    running_sessions: int = Field(..., ge=0, description="Number of running sessions")
    failed_sessions: int = Field(..., ge=0, description="Number of failed sessions")
    average_precision: float = Field(..., ge=0, le=1, description="Average precision across sessions")
    average_recall: float = Field(..., ge=0, le=1, description="Average recall across sessions")
    average_f1_score: float = Field(..., ge=0, le=1, description="Average F1 score across sessions")
    average_latency_ms: float = Field(..., ge=0, description="Average detection latency in milliseconds")
    
    @property
    def total_storage_gb(self) -> float:
        """Total storage in GB"""
        return round(self.total_storage_bytes / (1024**3), 2)
    
    @property
    def average_video_duration_minutes(self) -> float:
        """Average video duration in minutes"""
        return round(self.average_video_duration / 60, 2)
    
    @property
    def success_rate(self) -> float:
        """Test session success rate"""
        if self.total_test_sessions == 0:
            return 0.0
        return round(self.completed_sessions / self.total_test_sessions, 3)


class ProjectSummary(BaseModel):
    """Lightweight project summary for listings"""
    id: uuid.UUID
    name: str
    status: ProjectStatus
    camera_view: CameraView
    signal_type: SignalType
    total_videos: int
    created_at: datetime
    
    class Config:
        from_attributes = True