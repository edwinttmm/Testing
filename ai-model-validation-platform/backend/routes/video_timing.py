"""
Video Timing API Routes

Provides REST API endpoints for precise video timing synchronization and latency measurement.
These endpoints support the video timing service for accurate LabJack detection latency calculation.

Endpoints:
- POST /api/sessions/{id}/start-video - Start video timing
- GET /api/sessions/{id}/video-timing - Get timing data
- POST /api/sessions/{id}/calculate-latency - Calculate latency
- POST /api/sessions/{id}/sync-labjack - Synchronize with LabJack
- DELETE /api/sessions/{id}/clear-timing - Clear timing data
- GET /api/sessions/{id}/timing-stats - Get timing statistics
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

# Import database and models
from database import get_db
from models import TestSession, Video

# Import video timing service
from services.video_timing_service import (
    get_video_timing_service, 
    VideoTimingService,
    VideoTimingData,
    LatencyMeasurement,
    VideoTimingError
)

# Import LabJack service for synchronization
from services.labjack_service import get_labjack_service

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/sessions",
    tags=["video-timing"],
    responses={404: {"description": "Session not found"}},
)


# Request/Response Models
class StartVideoTimingRequest(BaseModel):
    """Request model for starting video timing"""
    video_id: str = Field(..., description="ID of the video being played")
    sync_labjack: bool = Field(default=True, description="Whether to synchronize with LabJack")


class VideoTimingResponse(BaseModel):
    """Response model for video timing data"""
    session_id: str
    video_id: str
    start_timestamp: float
    precision_ns: int
    system_time_utc: str
    monotonic_time: float
    thread_id: int
    process_id: int


class LatencyCalculationRequest(BaseModel):
    """Request model for latency calculation"""
    detection_timestamp: float = Field(..., description="LabJack detection timestamp")


class LatencyCalculationResponse(BaseModel):
    """Response model for latency calculation"""
    session_id: str
    video_start_time: float
    detection_timestamp: float
    latency_ms: float
    precision_indicator: str
    calculation_timestamp: float


class TimingStatsResponse(BaseModel):
    """Response model for timing statistics"""
    active_sessions: int
    total_videos: int
    timer_precision_ns: int
    precision_class: str
    cache_size_bytes: int


class SyncLabJackRequest(BaseModel):
    """Request model for LabJack synchronization"""
    start_monitoring: bool = Field(default=True, description="Start LabJack monitoring")


class APIResponse(BaseModel):
    """Standard API response wrapper"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


# Dependency to validate session exists
def get_test_session(session_id: str, db: Session = Depends(get_db)) -> TestSession:
    """Validate that test session exists"""
    test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if not test_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test session {session_id} not found"
        )
    return test_session


@router.post("/{session_id}/start-video")
async def start_video_timing(
    session_id: str,
    request: StartVideoTimingRequest,
    db: Session = Depends(get_db),
    test_session: TestSession = Depends(get_test_session)
) -> APIResponse:
    """
    Start precise video timing for latency measurement.
    
    This endpoint records a high-precision timestamp when video playback begins,
    enabling accurate latency calculation with LabJack detection events.
    
    Args:
        session_id: Test session identifier
        request: Video timing configuration
        db: Database session
        test_session: Validated test session
        
    Returns:
        API response with video start timestamp
        
    Raises:
        HTTPException: If timing start fails
    """
    try:
        logger.info(f"Starting video timing for session {session_id}, video {request.video_id}")
        
        # Get video timing service
        timing_service = get_video_timing_service()
        
        # Validate video exists
        video = db.query(Video).filter(Video.id == request.video_id).first()
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {request.video_id} not found"
            )
        
        # Start video timing
        start_timestamp = timing_service.start_video_timing(session_id, request.video_id, db)
        
        # Synchronize with LabJack if requested
        sync_success = True
        if request.sync_labjack:
            try:
                labjack_service = get_labjack_service()
                sync_success = timing_service.synchronize_with_labjack(session_id, labjack_service)
                if not sync_success:
                    logger.warning(f"LabJack synchronization failed for session {session_id}")
            except Exception as e:
                logger.error(f"LabJack synchronization error: {e}")
                sync_success = False
        
        # Get timing data for response
        timing_data = timing_service.get_timing_data(session_id)
        
        response_data = {
            "start_timestamp": start_timestamp,
            "video_id": request.video_id,
            "sync_labjack": sync_success,
            "precision_ns": timing_data.precision_ns if timing_data else None,
            "system_time_utc": timing_data.system_time_utc if timing_data else None
        }
        
        return APIResponse(
            success=True,
            message=f"Video timing started successfully for session {session_id}",
            data=response_data
        )
        
    except VideoTimingError as e:
        logger.error(f"Video timing error for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start video timing: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error starting video timing for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error starting video timing"
        )


@router.get("/{session_id}/video-timing")
async def get_video_timing(
    session_id: str,
    db: Session = Depends(get_db),
    test_session: TestSession = Depends(get_test_session)
) -> APIResponse:
    """
    Get video timing data for latency calculation.
    
    Retrieves the precise video start timestamp and associated timing data
    for the specified test session.
    
    Args:
        session_id: Test session identifier
        db: Database session
        test_session: Validated test session
        
    Returns:
        API response with timing data
        
    Raises:
        HTTPException: If timing data not found
    """
    try:
        logger.info(f"Getting video timing data for session {session_id}")
        
        # Get video timing service
        timing_service = get_video_timing_service()
        
        # Get timing data
        timing_data = timing_service.get_timing_data(session_id)
        
        if not timing_data:
            # Try database fallback
            start_time = timing_service.get_video_start_time(session_id, db)
            if start_time is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No video timing data found for session {session_id}"
                )
            
            response_data = {
                "start_timestamp": start_time,
                "source": "database"
            }
        else:
            response_data = {
                "session_id": timing_data.session_id,
                "video_id": timing_data.video_id,
                "start_timestamp": timing_data.start_timestamp,
                "precision_ns": timing_data.precision_ns,
                "system_time_utc": timing_data.system_time_utc,
                "monotonic_time": timing_data.monotonic_time,
                "thread_id": timing_data.thread_id,
                "process_id": timing_data.process_id,
                "source": "cache"
            }
        
        return APIResponse(
            success=True,
            message=f"Video timing data retrieved for session {session_id}",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting video timing for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving video timing data"
        )


@router.post("/{session_id}/calculate-latency")
async def calculate_latency(
    session_id: str,
    request: LatencyCalculationRequest,
    db: Session = Depends(get_db),
    test_session: TestSession = Depends(get_test_session)
) -> APIResponse:
    """
    Calculate latency between video start and detection event.
    
    Uses the video start timestamp and provided detection timestamp
    to calculate the latency in milliseconds.
    
    Args:
        session_id: Test session identifier
        request: Latency calculation parameters
        db: Database session
        test_session: Validated test session
        
    Returns:
        API response with latency measurement
        
    Raises:
        HTTPException: If calculation fails
    """
    try:
        logger.info(f"Calculating latency for session {session_id}, "
                   f"detection timestamp: {request.detection_timestamp}")
        
        # Get video timing service
        timing_service = get_video_timing_service()
        
        # Calculate latency
        measurement = timing_service.calculate_latency(
            session_id, 
            request.detection_timestamp, 
            db
        )
        
        if not measurement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cannot calculate latency - no video start time for session {session_id}"
            )
        
        response_data = {
            "session_id": measurement.session_id,
            "video_start_time": measurement.video_start_time,
            "detection_timestamp": measurement.detection_timestamp,
            "latency_ms": measurement.latency_ms,
            "precision_indicator": measurement.precision_indicator,
            "calculation_timestamp": measurement.calculation_timestamp
        }
        
        return APIResponse(
            success=True,
            message=f"Latency calculated: {measurement.latency_ms:.3f}ms",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error calculating latency for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error calculating latency"
        )


@router.post("/{session_id}/sync-labjack")
async def sync_labjack(
    session_id: str,
    request: SyncLabJackRequest,
    test_session: TestSession = Depends(get_test_session)
) -> APIResponse:
    """
    Synchronize video timing with LabJack monitoring.
    
    Coordinates timing between video playback and LabJack detection
    monitoring for accurate latency measurement.
    
    Args:
        session_id: Test session identifier
        request: Synchronization parameters
        test_session: Validated test session
        
    Returns:
        API response with synchronization result
        
    Raises:
        HTTPException: If synchronization fails
    """
    try:
        logger.info(f"Synchronizing LabJack for session {session_id}")
        
        # Get services
        timing_service = get_video_timing_service()
        labjack_service = get_labjack_service()
        
        # Synchronize
        sync_result = timing_service.synchronize_with_labjack(session_id, labjack_service)
        
        if not sync_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to synchronize LabJack for session {session_id}"
            )
        
        response_data = {
            "session_id": session_id,
            "synchronized": sync_result,
            "monitoring_started": request.start_monitoring
        }
        
        return APIResponse(
            success=True,
            message=f"LabJack synchronized successfully for session {session_id}",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error synchronizing LabJack for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error synchronizing LabJack"
        )


@router.delete("/{session_id}/clear-timing")
async def clear_timing_data(
    session_id: str,
    test_session: TestSession = Depends(get_test_session)
) -> APIResponse:
    """
    Clear cached timing data for a session.
    
    Removes timing data from memory cache while preserving
    database records.
    
    Args:
        session_id: Test session identifier
        test_session: Validated test session
        
    Returns:
        API response with clearing result
    """
    try:
        logger.info(f"Clearing timing data for session {session_id}")
        
        # Get video timing service
        timing_service = get_video_timing_service()
        
        # Clear timing data
        cleared = timing_service.clear_session_timing(session_id)
        
        response_data = {
            "session_id": session_id,
            "cleared": cleared
        }
        
        message = f"Timing data cleared for session {session_id}" if cleared else \
                 f"No timing data found to clear for session {session_id}"
        
        return APIResponse(
            success=True,
            message=message,
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Unexpected error clearing timing data for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error clearing timing data"
        )


@router.get("/{session_id}/timing-stats")
async def get_timing_statistics(
    session_id: str,
    test_session: TestSession = Depends(get_test_session)
) -> APIResponse:
    """
    Get timing statistics for debugging and monitoring.
    
    Provides information about timing precision, active sessions,
    and service performance metrics.
    
    Args:
        session_id: Test session identifier (for validation)
        test_session: Validated test session
        
    Returns:
        API response with timing statistics
    """
    try:
        logger.info(f"Getting timing statistics (requested for session {session_id})")
        
        # Get video timing service
        timing_service = get_video_timing_service()
        
        # Get statistics
        stats = timing_service.get_timing_statistics()
        
        # Add session-specific information
        session_videos = timing_service.get_session_videos(session_id)
        session_timing = timing_service.get_timing_data(session_id)
        
        stats.update({
            "requested_session_id": session_id,
            "session_has_timing": session_timing is not None,
            "session_video_count": len(session_videos),
            "session_videos": session_videos
        })
        
        return APIResponse(
            success=True,
            message="Timing statistics retrieved successfully",
            data=stats
        )
        
    except Exception as e:
        logger.error(f"Unexpected error getting timing statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving timing statistics"
        )


# Health check endpoint
@router.get("/timing-service/health")
async def timing_service_health() -> APIResponse:
    """
    Check video timing service health.
    
    Returns:
        API response with service health status
    """
    try:
        # Get video timing service
        timing_service = get_video_timing_service()
        
        # Get basic statistics
        stats = timing_service.get_timing_statistics()
        
        health_data = {
            "service": "VideoTimingService",
            "status": "healthy",
            "active_sessions": stats["active_sessions"],
            "timer_precision_class": stats["precision_class"],
            "timer_precision_ns": stats["timer_precision_ns"]
        }
        
        return APIResponse(
            success=True,
            message="Video timing service is healthy",
            data=health_data
        )
        
    except Exception as e:
        logger.error(f"Video timing service health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Video timing service is unavailable"
        )