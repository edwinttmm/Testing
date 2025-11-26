"""
Video Lifecycle API Routes - Production-Grade REST Endpoints
==============================================================

FastAPI routes for per-video monitoring lifecycle control.

Features:
- Comprehensive error handling
- Rate limiting
- Structured JSON logging
- Health checks
- Transaction management

Author: Backend API Developer Agent
Date: 2025-11-20
Status: Production-Ready
"""

import logging
import time
from typing import Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from database import get_db
from src.models.video_lifecycle_models import (
    VideoStartedRequest,
    VideoEndedRequest,
    VideoErrorRequest,
    VideoStartedResponse,
    VideoEndedResponse,
    VideoLifecycleStatus,
    DriftStatisticsResponse,
    ErrorResponse,
    HealthCheckResponse
)
from src.services.video_lifecycle_orchestrator import VideoLifecycleOrchestrator
from src.services.clock_sync_service_v2 import ClockSyncService
from src.services.drift_measurement_service import DriftMeasurementService
from src.services.drift_monitoring_service import DriftMonitoringService
from src.services.dedicated_labjack_monitor import DedicatedLabJackMonitor

# Configure logging
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(
    prefix="/api/video-lifecycle",
    tags=["video-lifecycle"],
    responses={
        503: {"model": ErrorResponse, "description": "Service Unavailable"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
        429: {"model": ErrorResponse, "description": "Too Many Requests"}
    }
)

# ==================== DEPENDENCY INJECTION ====================

# Global orchestrator instance (initialized at startup)
_orchestrator: VideoLifecycleOrchestrator = None


def get_orchestrator() -> VideoLifecycleOrchestrator:
    """Dependency to get orchestrator instance."""
    if _orchestrator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Video lifecycle orchestrator not initialized. Service starting up."
        )
    return _orchestrator


def initialize_orchestrator(
    clock_sync: ClockSyncService,
    drift_measurement: DriftMeasurementService,
    drift_monitoring: DriftMonitoringService,
    labjack_monitor: DedicatedLabJackMonitor,
    db_session_factory
):
    """Initialize the global orchestrator instance (called at app startup)."""
    global _orchestrator
    _orchestrator = VideoLifecycleOrchestrator(
        clock_sync_service=clock_sync,
        drift_measurement_service=drift_measurement,
        drift_monitoring_service=drift_monitoring,
        labjack_monitor=labjack_monitor,
        db_session_factory=db_session_factory
    )
    logger.info("✅ Video lifecycle orchestrator initialized")


# ==================== MIDDLEWARE ====================

@router.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware to log all requests with timing information.
    """
    start_time = time.time()
    request_id = f"req_{int(start_time * 1000)}"

    # Log request
    logger.info(
        f"[{request_id}] → {request.method} {request.url.path}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else "unknown"
        }
    )

    try:
        response = await call_next(request)

        # Log response
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"[{request_id}] ← {response.status_code} ({duration_ms:.2f}ms)",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "duration_ms": duration_ms
            }
        )

        return response

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[{request_id}] ✗ Error ({duration_ms:.2f}ms): {str(e)}",
            exc_info=True,
            extra={
                "request_id": request_id,
                "error": str(e),
                "duration_ms": duration_ms
            }
        )
        raise


# ==================== EXCEPTION HANDLERS ====================

@router.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors (400 Bad Request)."""
    logger.warning(f"Validation error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error_code": "VALIDATION_ERROR",
            "error_message": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@router.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    """Handle runtime errors (503 Service Unavailable)."""
    logger.error(f"Runtime error: {str(exc)}")

    # Check if it's a LabJack error
    if "LabJack" in str(exc):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "error_code": "LABJACK_NOT_RESPONDING",
                "error_message": str(exc),
                "retry_after_seconds": 30,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    # Generic runtime error
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_code": "INTERNAL_ERROR",
            "error_message": "An internal error occurred. Please try again.",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# ==================== API ENDPOINTS ====================

@router.post(
    "/{session_id}/video-started",
    response_model=VideoStartedResponse,
    status_code=status.HTTP_200_OK,
    summary="Start video monitoring",
    description=(
        "Notifies backend that a video has started playing. "
        "Initiates LabJack monitoring and records timing for drift compensation."
    ),
    responses={
        200: {"description": "Video monitoring started successfully"},
        400: {"description": "Invalid request or validation error"},
        409: {"description": "Session already has active video"},
        503: {"description": "LabJack not responding"}
    }
)
@limiter.limit("30/minute")  # Rate limit: 30 requests per minute
async def video_started(
    session_id: str,
    request_body: VideoStartedRequest,
    request: Request,
    db: Session = Depends(get_db),
    orchestrator: VideoLifecycleOrchestrator = Depends(get_orchestrator)
) -> VideoStartedResponse:
    """
    Handle video-started event.

    Process:
    1. Validate session doesn't have active video
    2. Start LabJack monitoring
    3. Calculate drift
    4. Store timing in database
    5. Return sync information

    Args:
        session_id: Test session identifier
        request_body: Video started event payload
        request: FastAPI request object (for rate limiting)
        db: Database session
        orchestrator: Video lifecycle orchestrator

    Returns:
        VideoStartedResponse with timing information

    Raises:
        HTTPException 409: If session already has active video
        HTTPException 503: If LabJack is not responding
    """
    try:
        logger.info(
            f"📹 Video started request: session={session_id}, video={request_body.video_id}",
            extra={
                "session_id": session_id,
                "video_id": request_body.video_id,
                "video_url": request_body.video_url
            }
        )

        # Handle request
        response = await orchestrator.handle_video_started(
            session_id=session_id,
            request=request_body,
            db=db
        )

        # Log success
        logger.info(
            f"✅ Video started successfully: drift={response.timing.drift_ms:.2f}ms",
            extra={
                "session_id": session_id,
                "video_id": request_body.video_id,
                "drift_ms": response.timing.drift_ms
            }
        )

        return response

    except ValueError as e:
        # Video already active - return 409 Conflict
        logger.warning(f"Conflict: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

    except RuntimeError as e:
        # LabJack error - return 503 Service Unavailable
        logger.error(f"Service error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
            headers={"Retry-After": "30"}
        )

    except Exception as e:
        # Unexpected error - return 500 Internal Server Error
        logger.error(f"Unexpected error in video-started: {e}", exc_info=True)
        db.rollback()  # Rollback any database changes
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again."
        )


@router.post(
    "/{session_id}/video-ended",
    response_model=VideoEndedResponse,
    status_code=status.HTTP_200_OK,
    summary="Stop video monitoring",
    description=(
        "Notifies backend that a video has ended. "
        "Stops LabJack monitoring and records final statistics."
    ),
    responses={
        200: {"description": "Video monitoring stopped successfully"},
        400: {"description": "Invalid request or validation error"},
        404: {"description": "No active video for session"},
        503: {"description": "LabJack not responding"}
    }
)
@limiter.limit("30/minute")
async def video_ended(
    session_id: str,
    request_body: VideoEndedRequest,
    request: Request,
    db: Session = Depends(get_db),
    orchestrator: VideoLifecycleOrchestrator = Depends(get_orchestrator)
) -> VideoEndedResponse:
    """
    Handle video-ended event.

    Process:
    1. Validate session has active video
    2. Stop LabJack monitoring
    3. Record final statistics
    4. Clean up session state

    Args:
        session_id: Test session identifier
        request_body: Video ended event payload
        request: FastAPI request object
        db: Database session
        orchestrator: Video lifecycle orchestrator

    Returns:
        VideoEndedResponse with final statistics

    Raises:
        HTTPException 404: If no active video for session
        HTTPException 503: If LabJack is not responding
    """
    try:
        logger.info(
            f"🛑 Video ended request: session={session_id}, video={request_body.video_id}",
            extra={
                "session_id": session_id,
                "video_id": request_body.video_id,
                "detection_count": request_body.detection_count
            }
        )

        # Handle request
        response = await orchestrator.handle_video_ended(
            session_id=session_id,
            request=request_body,
            db=db
        )

        # Log success
        logger.info(
            f"✅ Video ended successfully: detections={response.detections_recorded}",
            extra={
                "session_id": session_id,
                "video_id": request_body.video_id,
                "detections_recorded": response.detections_recorded
            }
        )

        return response

    except ValueError as e:
        # No active video - return 404 Not Found
        logger.warning(f"Not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except RuntimeError as e:
        # LabJack error - return 503 Service Unavailable
        logger.error(f"Service error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
            headers={"Retry-After": "30"}
        )

    except Exception as e:
        # Unexpected error - return 500 Internal Server Error
        logger.error(f"Unexpected error in video-ended: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again."
        )


@router.post(
    "/{session_id}/video-error",
    status_code=status.HTTP_200_OK,
    summary="Report video error",
    description=(
        "Notifies backend that a video encountered an error. "
        "Performs cleanup and stops monitoring if active."
    )
)
@limiter.limit("30/minute")
async def video_error(
    session_id: str,
    request_body: VideoErrorRequest,
    request: Request,
    db: Session = Depends(get_db),
    orchestrator: VideoLifecycleOrchestrator = Depends(get_orchestrator)
) -> Dict[str, Any]:
    """
    Handle video-error event.

    Process:
    1. Log error details
    2. Stop monitoring if active
    3. Clean up session state
    4. Store error in database

    Args:
        session_id: Test session identifier
        request_body: Video error event payload
        request: FastAPI request object
        db: Database session
        orchestrator: Video lifecycle orchestrator

    Returns:
        Success confirmation
    """
    try:
        logger.error(
            f"❌ Video error: session={session_id}, video={request_body.video_id}, "
            f"error={request_body.error_code}",
            extra={
                "session_id": session_id,
                "video_id": request_body.video_id,
                "error_code": request_body.error_code,
                "error_message": request_body.error_message
            }
        )

        # Handle request
        response = await orchestrator.handle_video_error(
            session_id=session_id,
            request=request_body,
            db=db
        )

        logger.info(f"✅ Video error handled and cleaned up: session={session_id}")

        return response

    except Exception as e:
        # Log but don't fail - error handling should be resilient
        logger.error(f"Error handling video-error: {e}", exc_info=True)
        db.rollback()
        return {
            "success": False,
            "message": "Failed to handle video error",
            "error": str(e)
        }


@router.get(
    "/{session_id}/status",
    response_model=VideoLifecycleStatus,
    summary="Get session status",
    description="Get current video lifecycle and monitoring status for a session"
)
@limiter.limit("60/minute")
async def get_status(
    session_id: str,
    request: Request,
    orchestrator: VideoLifecycleOrchestrator = Depends(get_orchestrator)
) -> VideoLifecycleStatus:
    """
    Get current status of video lifecycle for a session.

    Args:
        session_id: Test session identifier
        request: FastAPI request object
        orchestrator: Video lifecycle orchestrator

    Returns:
        VideoLifecycleStatus with current state
    """
    try:
        status_info = orchestrator.get_session_status(session_id)
        return status_info

    except Exception as e:
        logger.error(f"Error getting session status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session status"
        )


@router.get(
    "/{session_id}/drift-stats",
    response_model=DriftStatisticsResponse,
    summary="Get drift statistics",
    description="Get drift measurement statistics for a session"
)
@limiter.limit("60/minute")
async def get_drift_stats(
    session_id: str,
    request: Request,
    orchestrator: VideoLifecycleOrchestrator = Depends(get_orchestrator)
) -> DriftStatisticsResponse:
    """
    Get drift statistics for a session.

    Args:
        session_id: Test session identifier
        request: FastAPI request object
        orchestrator: Video lifecycle orchestrator

    Returns:
        DriftStatisticsResponse with statistics
    """
    try:
        stats = orchestrator.get_drift_statistics(session_id)
        return stats

    except Exception as e:
        logger.error(f"Error getting drift statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve drift statistics"
        )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check",
    description="Check health status of video lifecycle system"
)
async def health_check(
    orchestrator: VideoLifecycleOrchestrator = Depends(get_orchestrator)
) -> HealthCheckResponse:
    """
    Health check endpoint for video lifecycle system.

    Returns:
        HealthCheckResponse with system health information
    """
    try:
        health = orchestrator.get_health()

        return HealthCheckResponse(
            status=health['status'],
            version=health['version'],
            components=health['components'],
            active_sessions=health['active_sessions'],
            monitoring_active=health['monitoring_active'],
            last_error=None,
            uptime_seconds=health['uptime_seconds'],
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return HealthCheckResponse(
            status="unhealthy",
            version="1.0.0",
            components={
                "orchestrator": "error"
            },
            active_sessions=0,
            monitoring_active=False,
            last_error=str(e),
            uptime_seconds=0,
            timestamp=datetime.utcnow()
        )


# ==================== STARTUP INITIALIZATION ====================

async def setup_video_lifecycle_routes(app):
    """
    Setup video lifecycle routes at application startup.

    This function should be called from main.py startup event.
    """
    try:
        # Initialize services
        from database import SessionLocal

        clock_sync = ClockSyncService()
        drift_measurement = DriftMeasurementService()
        drift_monitoring = DriftMonitoringService()
        labjack_monitor = DedicatedLabJackMonitor()

        # Initialize orchestrator
        initialize_orchestrator(
            clock_sync=clock_sync,
            drift_measurement=drift_measurement,
            drift_monitoring=drift_monitoring,
            labjack_monitor=labjack_monitor,
            db_session_factory=SessionLocal
        )

        logger.info("✅ Video lifecycle routes initialized successfully")

    except Exception as e:
        logger.error(f"❌ Failed to initialize video lifecycle routes: {e}", exc_info=True)
        raise
