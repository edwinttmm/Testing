"""
Video Lifecycle Models - Pydantic Models for Video Start/Stop API
===================================================================

Type-safe request/response models for per-video monitoring lifecycle.

Author: Backend API Developer Agent
Date: 2025-11-20
Status: Production-Ready
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class VideoLifecycleEvent(str, Enum):
    """Video lifecycle event types"""
    VIDEO_STARTED = "video_started"
    VIDEO_ENDED = "video_ended"
    VIDEO_ERROR = "video_error"
    VIDEO_PAUSED = "video_paused"
    VIDEO_RESUMED = "video_resumed"


class MonitoringStatus(str, Enum):
    """LabJack monitoring status"""
    IDLE = "idle"
    STARTING = "starting"
    ACTIVE = "active"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


# ==================== REQUEST MODELS ====================

class VideoStartedRequest(BaseModel):
    """Request payload for video-started event"""

    video_id: str = Field(
        ...,
        description="Unique identifier for the video",
        min_length=1,
        max_length=100
    )

    frontend_timestamp: float = Field(
        ...,
        description="Browser performance.now() timestamp (milliseconds)",
        gt=0
    )

    video_url: str = Field(
        ...,
        description="URL or path of the video being played",
        min_length=1
    )

    # Optional metadata
    video_duration_ms: Optional[float] = Field(
        None,
        description="Video duration in milliseconds",
        gt=0
    )

    video_fps: Optional[float] = Field(
        None,
        description="Video frames per second",
        gt=0
    )

    browser_timezone: Optional[str] = Field(
        None,
        description="Browser timezone (e.g., 'America/New_York')"
    )

    performance_origin: Optional[float] = Field(
        None,
        description="Browser performance.timeOrigin value"
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional video metadata"
    )

    @validator('video_id')
    def validate_video_id(cls, v):
        """Validate video ID format"""
        if not v or v.strip() == "":
            raise ValueError("video_id cannot be empty")
        return v.strip()

    @validator('video_url')
    def validate_video_url(cls, v):
        """Validate video URL"""
        if not v or v.strip() == "":
            raise ValueError("video_url cannot be empty")
        return v.strip()

    class Config:
        schema_extra = {
            "example": {
                "video_id": "video_001",
                "frontend_timestamp": 12345.678,
                "video_url": "/videos/test_video.mp4",
                "video_duration_ms": 30000,
                "video_fps": 30.0,
                "browser_timezone": "America/New_York",
                "metadata": {
                    "test_type": "HIL",
                    "camera_view": "front"
                }
            }
        }


class VideoEndedRequest(BaseModel):
    """Request payload for video-ended event"""

    video_id: str = Field(
        ...,
        description="Video identifier that ended",
        min_length=1
    )

    frontend_timestamp: float = Field(
        ...,
        description="Browser performance.now() timestamp when video ended",
        gt=0
    )

    detection_count: int = Field(
        0,
        description="Number of detections recorded during video playback",
        ge=0
    )

    playback_duration_ms: Optional[float] = Field(
        None,
        description="Actual playback duration (may differ from video duration)",
        ge=0
    )

    ended_naturally: bool = Field(
        True,
        description="True if video ended naturally, False if stopped manually"
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional ending metadata"
    )

    @validator('video_id')
    def validate_video_id(cls, v):
        """Validate video ID format"""
        if not v or v.strip() == "":
            raise ValueError("video_id cannot be empty")
        return v.strip()

    class Config:
        schema_extra = {
            "example": {
                "video_id": "video_001",
                "frontend_timestamp": 42345.678,
                "detection_count": 15,
                "playback_duration_ms": 29850,
                "ended_naturally": True,
                "metadata": {
                    "user_stopped": False
                }
            }
        }


class VideoErrorRequest(BaseModel):
    """Request payload for video-error event"""

    video_id: str = Field(
        ...,
        description="Video identifier that encountered error"
    )

    frontend_timestamp: float = Field(
        ...,
        description="Browser performance.now() timestamp when error occurred",
        gt=0
    )

    error_code: str = Field(
        ...,
        description="Error code (e.g., 'MEDIA_ERR_SRC_NOT_SUPPORTED')"
    )

    error_message: str = Field(
        ...,
        description="Human-readable error message"
    )

    stack_trace: Optional[str] = Field(
        None,
        description="JavaScript stack trace if available"
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional error context"
    )

    class Config:
        schema_extra = {
            "example": {
                "video_id": "video_001",
                "frontend_timestamp": 15000.123,
                "error_code": "MEDIA_ERR_NETWORK",
                "error_message": "Failed to load video due to network error",
                "metadata": {
                    "network_status": "offline"
                }
            }
        }


# ==================== RESPONSE MODELS ====================

class TimingInfo(BaseModel):
    """Timing information for sync analysis"""

    frontend_timestamp_ms: float = Field(
        ...,
        description="Frontend timestamp (performance.now())"
    )

    backend_timestamp_s: float = Field(
        ...,
        description="Backend timestamp (time.time())"
    )

    labjack_timestamp_s: Optional[float] = Field(
        None,
        description="LabJack device timestamp"
    )

    clock_offset_ms: float = Field(
        ...,
        description="Clock offset Frontend -> Backend (milliseconds)"
    )

    drift_ms: Optional[float] = Field(
        None,
        description="Measured drift in milliseconds"
    )

    latency_ms: Optional[float] = Field(
        None,
        description="Command latency (Backend -> LabJack)"
    )


class VideoStartedResponse(BaseModel):
    """Response for video-started event"""

    success: bool = Field(
        ...,
        description="Whether video start was processed successfully"
    )

    video_id: str = Field(
        ...,
        description="Video identifier"
    )

    session_id: str = Field(
        ...,
        description="Test session identifier"
    )

    monitoring_status: MonitoringStatus = Field(
        ...,
        description="Current LabJack monitoring status"
    )

    timing: TimingInfo = Field(
        ...,
        description="Timing information for sync"
    )

    message: str = Field(
        ...,
        description="Human-readable status message"
    )

    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal warnings (e.g., high drift)"
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional response metadata"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "video_id": "video_001",
                "session_id": "session_abc123",
                "monitoring_status": "active",
                "timing": {
                    "frontend_timestamp_ms": 12345.678,
                    "backend_timestamp_s": 1700000000.123,
                    "labjack_timestamp_s": 1700000000.150,
                    "clock_offset_ms": 50.5,
                    "drift_ms": 27.0,
                    "latency_ms": 10.5
                },
                "message": "Video monitoring started successfully",
                "warnings": ["Drift of 27ms detected, within acceptable range"]
            }
        }


class VideoEndedResponse(BaseModel):
    """Response for video-ended event"""

    success: bool = Field(
        ...,
        description="Whether video end was processed successfully"
    )

    video_id: str = Field(
        ...,
        description="Video identifier"
    )

    session_id: str = Field(
        ...,
        description="Test session identifier"
    )

    monitoring_status: MonitoringStatus = Field(
        ...,
        description="LabJack monitoring status after stopping"
    )

    detections_recorded: int = Field(
        ...,
        description="Number of detections captured during video",
        ge=0
    )

    timing: TimingInfo = Field(
        ...,
        description="Final timing information"
    )

    message: str = Field(
        ...,
        description="Human-readable status message"
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional response metadata"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "video_id": "video_001",
                "session_id": "session_abc123",
                "monitoring_status": "stopped",
                "detections_recorded": 15,
                "timing": {
                    "frontend_timestamp_ms": 42345.678,
                    "backend_timestamp_s": 1700000030.123,
                    "clock_offset_ms": 50.5
                },
                "message": "Video monitoring stopped successfully, 15 detections recorded"
            }
        }


class VideoLifecycleStatus(BaseModel):
    """Current status of video lifecycle and monitoring"""

    session_id: str = Field(
        ...,
        description="Test session identifier"
    )

    current_video_id: Optional[str] = Field(
        None,
        description="Currently playing video ID (null if none)"
    )

    monitoring_active: bool = Field(
        ...,
        description="Whether LabJack monitoring is currently active"
    )

    monitoring_status: MonitoringStatus = Field(
        ...,
        description="Detailed monitoring status"
    )

    video_start_time: Optional[datetime] = Field(
        None,
        description="When current video started (ISO 8601)"
    )

    elapsed_time_ms: Optional[float] = Field(
        None,
        description="Elapsed time since video start (milliseconds)"
    )

    detections_count: int = Field(
        0,
        description="Detections captured for current video",
        ge=0
    )

    drift_ms: Optional[float] = Field(
        None,
        description="Current drift measurement (milliseconds)"
    )

    health: str = Field(
        ...,
        description="Overall health status: 'healthy', 'degraded', 'unhealthy'"
    )

    last_error: Optional[str] = Field(
        None,
        description="Last error message if any"
    )

    class Config:
        schema_extra = {
            "example": {
                "session_id": "session_abc123",
                "current_video_id": "video_001",
                "monitoring_active": True,
                "monitoring_status": "active",
                "video_start_time": "2025-11-20T10:30:45.123Z",
                "elapsed_time_ms": 15234.5,
                "detections_count": 8,
                "drift_ms": 25.3,
                "health": "healthy",
                "last_error": None
            }
        }


class DriftStatisticsResponse(BaseModel):
    """Drift statistics for a session"""

    session_id: str = Field(
        ...,
        description="Test session identifier"
    )

    total_videos: int = Field(
        ...,
        description="Total videos processed in session",
        ge=0
    )

    mean_drift_ms: float = Field(
        ...,
        description="Mean drift across all videos (milliseconds)"
    )

    median_drift_ms: float = Field(
        ...,
        description="Median drift (milliseconds)"
    )

    std_dev_ms: float = Field(
        ...,
        description="Standard deviation of drift (milliseconds)",
        ge=0
    )

    min_drift_ms: float = Field(
        ...,
        description="Minimum drift observed (milliseconds)"
    )

    max_drift_ms: float = Field(
        ...,
        description="Maximum drift observed (milliseconds)"
    )

    drift_trend: str = Field(
        ...,
        description="Drift trend: 'stable', 'increasing', 'decreasing', 'erratic'"
    )

    quality_assessment: str = Field(
        ...,
        description="Overall quality: 'excellent', 'good', 'acceptable', 'poor'"
    )

    warnings: List[str] = Field(
        default_factory=list,
        description="Any warnings about drift quality"
    )

    calculated_at: datetime = Field(
        ...,
        description="When statistics were calculated"
    )

    class Config:
        schema_extra = {
            "example": {
                "session_id": "session_abc123",
                "total_videos": 5,
                "mean_drift_ms": 25.5,
                "median_drift_ms": 24.0,
                "std_dev_ms": 8.3,
                "min_drift_ms": 15.2,
                "max_drift_ms": 42.1,
                "drift_trend": "stable",
                "quality_assessment": "excellent",
                "warnings": [],
                "calculated_at": "2025-11-20T10:35:00.000Z"
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""

    success: bool = Field(
        False,
        description="Always False for errors"
    )

    error_code: str = Field(
        ...,
        description="Machine-readable error code"
    )

    error_message: str = Field(
        ...,
        description="Human-readable error message"
    )

    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details"
    )

    retry_after_seconds: Optional[int] = Field(
        None,
        description="Suggested retry delay for recoverable errors"
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error_code": "LABJACK_NOT_RESPONDING",
                "error_message": "LabJack device is not responding to commands",
                "details": {
                    "device_id": "T7_001",
                    "last_successful_ping": "2025-11-20T10:20:00.000Z"
                },
                "retry_after_seconds": 30,
                "timestamp": "2025-11-20T10:30:00.000Z"
            }
        }


class HealthCheckResponse(BaseModel):
    """Health check response for video lifecycle system"""

    status: str = Field(
        ...,
        description="Overall status: 'healthy', 'degraded', 'unhealthy'"
    )

    version: str = Field(
        ...,
        description="API version"
    )

    components: Dict[str, str] = Field(
        ...,
        description="Status of individual components"
    )

    active_sessions: int = Field(
        ...,
        description="Number of active test sessions",
        ge=0
    )

    monitoring_active: bool = Field(
        ...,
        description="Whether any monitoring is currently active"
    )

    last_error: Optional[str] = Field(
        None,
        description="Last system error if any"
    )

    uptime_seconds: float = Field(
        ...,
        description="Service uptime in seconds",
        ge=0
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Health check timestamp"
    )

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "components": {
                    "database": "healthy",
                    "labjack": "healthy",
                    "clock_sync": "healthy",
                    "drift_measurement": "healthy"
                },
                "active_sessions": 2,
                "monitoring_active": True,
                "last_error": None,
                "uptime_seconds": 3600.5,
                "timestamp": "2025-11-20T10:30:00.000Z"
            }
        }
