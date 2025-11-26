"""
LabJack Timing API Routes

API endpoints for LabJack-based detection timing validation.
Provides endpoints for starting/stopping timing, detection events, and latency results.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
import asyncio

from database import get_db, SessionLocal
from models import TestSession, DetectionEvent, Video
from services.labjack_detection_service import get_detection_service, DetectionEvent as ServiceDetectionEvent
from services.video_timing_service import get_timing_service
from services.latency_validation_service import get_validation_service
from services.test_execution_service import test_execution_service

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/labjack", tags=["labjack_timing"])


# Request/Response Models
class StartVideoTimingRequest(BaseModel):
    """Request to start video timing"""
    session_id: str = Field(..., description="Test session ID")
    video_id: str = Field(..., description="Video ID")
    video_file_path: Optional[str] = Field(None, description="Video file path")
    detection_threshold: Optional[float] = Field(3.3, description="LabJack detection threshold in volts")
    latency_threshold_ms: Optional[float] = Field(50.0, description="Latency threshold in milliseconds")
    detection_channel: Optional[str] = Field("AIN0", description="LabJack channel for detection")
    enable_t3_yolo: Optional[bool] = Field(False, description="Enable T3 YOLO ML detection (for GT setup only, NOT for HIL validation tests)")


class DetectionEventRequest(BaseModel):
    """Request for manual detection event"""
    session_id: str = Field(..., description="Test session ID")
    timestamp: float = Field(..., description="Detection timestamp (Unix)")
    voltage_level: float = Field(..., description="Voltage level that triggered detection")
    channel: str = Field("AIN0", description="LabJack channel")
    threshold: float = Field(2.5, description="Detection threshold used")


class LatencyResultsResponse(BaseModel):
    """Response with latency validation results"""
    session_id: str
    validation_type: str = "labjack_timing"
    pass_rate_percent: float
    average_latency_ms: float
    median_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    std_deviation_ms: float
    percentile_95_ms: float
    percentile_99_ms: float
    total_measurements: int
    pass_count: int
    fail_count: int
    error_count: int
    timeout_count: int
    threshold_ms: float
    distribution_histogram: Dict[str, int]
    measurement_period_seconds: float


# Route Handlers

@router.post("/test-sessions/{session_id}/start-video-timing")
async def start_video_timing(
    session_id: str,
    request: StartVideoTimingRequest,
    background_tasks: BackgroundTasks,
    db: SessionLocal = Depends(get_db)
):
    """
    Start video timing and LabJack detection monitoring
    
    This endpoint:
    1. Starts precise video timing
    2. Begins LabJack detection monitoring  
    3. Sets up latency validation parameters
    """
    try:
        logger.info(f"Starting video timing for session {session_id}")
        
        # Validate session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail=f"Test session {session_id} not found")
        
        # Get video info
        video = db.query(Video).filter(Video.id == request.video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail=f"Video {request.video_id} not found")
        
        video_file_path = request.video_file_path or video.file_path
        
        # Get services
        detection_service = get_detection_service(request.detection_threshold)
        timing_service = get_timing_service()
        validation_service = get_validation_service(request.latency_threshold_ms)
        
        # Initialize services
        if not await detection_service.initialize():
            raise HTTPException(status_code=500, detail="Failed to initialize LabJack detection service")
        
        # Create timing session
        timing_session = await timing_service.create_timing_session(
            session_id=session_id,
            video_id=request.video_id,
            video_file_path=video_file_path,
            detection_threshold=request.detection_threshold,
            latency_threshold_ms=request.latency_threshold_ms,
            detection_channel=request.detection_channel
        )
        
        # Start video timing (precise timestamp)
        video_start_time, video_start_time_unix = await timing_service.start_video_timing(session_id)

        # Persist timing to test_session using server clock for consistency
        try:
            test_session.started_at = test_session.started_at or datetime.now(timezone.utc)
            # Store as epoch seconds (float)
            test_session.video_playback_start_time = float(video_start_time_unix)
            # Also store ns string for precision consumers
            test_session.video_playback_start_time_ns = str(int(float(video_start_time_unix) * 1_000_000_000))

            # ✅ FIX RACE CONDITION: Flush to persist data without committing transaction
            db.flush()

            # Refresh to ensure data is visible
            db.refresh(test_session)

            # Verify critical fields are set
            assert test_session.video_playback_start_time is not None, "video_playback_start_time not persisted"
            assert test_session.id is not None, "session ID not set"

            # Now safe to commit
            db.commit()
            logger.info(f"✅ Session {session_id} timing persisted and verified: started_at={test_session.started_at}, video_playback_start_time={test_session.video_playback_start_time}")

            # Add small delay to ensure commit is visible to monitoring service
            await asyncio.sleep(0.1)

        except Exception as persist_err:
            logger.error(f"❌ Failed to persist timing fields on session {session_id}: {persist_err}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to persist session timing: {str(persist_err)}")

        # Start LabJack detection monitoring (after verified commit)
        detection_started = await detection_service.start_monitoring(
            session_id=session_id,
            video_id=request.video_id,
            channel=request.detection_channel,
            threshold=request.detection_threshold
        )
        
        if not detection_started:
            raise HTTPException(status_code=500, detail="Failed to start LabJack detection monitoring")
        
        # Update test session status
        test_session.status = "running"
        test_session.started_at = datetime.now(timezone.utc)
        db.commit()
        
        # Optionally start T3 YOLO detection + video monitor + coordination
        # NOTE: T3 YOLO should ONLY be enabled for Ground Truth setup, NOT for HIL validation tests
        # HIL validation tests use LabJack voltage signals as the primary detection source
        t3_started = False
        try:
            if video_file_path and request.enable_t3_yolo:
                from src.hil_video_frame_monitor import start_hil_video_monitoring
                from src.t3_t4_coordination_service import start_t3_t4_coordination
                from src.hil_t3_yolo_pipeline import start_t3_detection_for_hil_session

                # Start T3 pipeline session
                await start_t3_detection_for_hil_session(session_id=session_id, video_id=request.video_id, video_start_time=float(video_start_time_unix))
                # Start video frame monitor (process frames + store detections)
                await start_hil_video_monitoring(session_id=session_id, video_path=video_file_path, video_id=request.video_id, start_frame=0)
                # Start coordination for T3-T4 if desired (use latency threshold provided)
                await start_t3_t4_coordination(session_id=session_id, latency_threshold_ms=request.latency_threshold_ms or 100.0)
                t3_started = True
                logger.info(f"T3 detection + video monitor + coordination started for session {session_id}")
            elif video_file_path:
                logger.info(f"📍 Pure LabJack HIL test mode - T3 YOLO detection DISABLED for session {session_id}")
        except Exception as t3_err:
            logger.warning(f"T3 auto-start skipped for session {session_id}: {t3_err}")

        logger.info(f"Started video timing and detection monitoring for session {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "video_start_time": video_start_time.isoformat(),
            "video_start_time_unix": video_start_time_unix,
            "detection_threshold": request.detection_threshold,
            "latency_threshold_ms": request.latency_threshold_ms,
            "detection_channel": request.detection_channel,
            "timing_session": timing_session.to_dict(),
            "t3": {
                "enabled": request.enable_t3_yolo,
                "started": t3_started,
                "video_path": video_file_path
            },
            "mode": "pure_labjack_hil" if not request.enable_t3_yolo else "t3_yolo_enabled",
            "message": "Video timing and LabJack detection monitoring started successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting video timing for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start video timing: {str(e)}")


@router.post("/test-sessions/{session_id}/stop-video-timing")
async def stop_video_timing(
    session_id: str,
    db: SessionLocal = Depends(get_db)
):
    """
    Stop video timing and LabJack detection monitoring, calculate latency results
    
    This endpoint:
    1. Stops LabJack detection monitoring
    2. Stops video timing
    3. Calculates latency for all detections
    4. Stores results in database
    """
    try:
        logger.info(f"Stopping video timing for session {session_id}")
        
        # Get services
        detection_service = get_detection_service()
        timing_service = get_timing_service()
        validation_service = get_validation_service()
        
        # Stop detection monitoring and get events
        detection_events = await detection_service.stop_monitoring()
        
        # Stop video timing
        timing_session = await timing_service.stop_video_timing(session_id)
        
        if not timing_session:
            raise HTTPException(status_code=404, detail=f"Timing session {session_id} not found")
        
        # Get video start time for latency calculations
        video_timing = timing_service.get_video_start_time(session_id)
        if not video_timing:
            raise HTTPException(status_code=400, detail="Video start time not available for latency calculation")
        
        video_start_time, video_start_time_unix = video_timing
        
        # Calculate latency statistics
        latency_stats = validation_service.validate_session_latency(
            session_id=session_id,
            detection_events=detection_events,
            video_start_time=video_start_time,
            video_start_time_unix=video_start_time_unix
        )
        
        # Store detection events in database with latency data
        await _store_detection_events_with_latency(
            session_id=session_id,
            detection_events=detection_events,
            video_start_time_unix=video_start_time_unix,
            latency_stats=latency_stats,
            db=db
        )
        
        # Update test session status
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if test_session:
            test_session.status = "completed"
            test_session.completed_at = datetime.now(timezone.utc)
            db.commit()
        
        logger.info(f"Completed video timing for session {session_id} with {len(detection_events)} detections")
        
        return {
            "success": True,
            "session_id": session_id,
            "detection_count": len(detection_events),
            "latency_statistics": latency_stats.to_dict(),
            "timing_session": timing_session.to_dict(),
            "message": f"Video timing completed with {latency_stats.pass_count}/{latency_stats.total_measurements} detections passing latency validation"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping video timing for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop video timing: {str(e)}")


@router.get("/test-sessions/{session_id}/latency-results", response_model=LatencyResultsResponse)
async def get_latency_results(
    session_id: str,
    include_measurements: bool = False
):
    """
    Get comprehensive latency validation results for a test session
    
    Returns detailed latency statistics including:
    - Pass/Fail counts and rates
    - Latency distribution statistics
    - Histogram data for visualization
    """
    try:
        validation_service = get_validation_service()
        
        # Get latency statistics
        latency_stats = validation_service.get_session_statistics(session_id)
        if not latency_stats:
            raise HTTPException(status_code=404, detail=f"No latency results found for session {session_id}")
        
        response_data = {
            "session_id": session_id,
            "validation_type": "labjack_timing",
            "pass_rate_percent": latency_stats.pass_rate_percent,
            "average_latency_ms": latency_stats.average_latency_ms,
            "median_latency_ms": latency_stats.median_latency_ms,
            "min_latency_ms": latency_stats.min_latency_ms,
            "max_latency_ms": latency_stats.max_latency_ms,
            "std_deviation_ms": latency_stats.std_deviation_ms,
            "percentile_95_ms": latency_stats.percentile_95_ms,
            "percentile_99_ms": latency_stats.percentile_99_ms,
            "total_measurements": latency_stats.total_measurements,
            "pass_count": latency_stats.pass_count,
            "fail_count": latency_stats.fail_count,
            "error_count": latency_stats.error_count,
            "timeout_count": latency_stats.timeout_count,
            "threshold_ms": latency_stats.threshold_ms,
            "distribution_histogram": latency_stats.distribution_histogram,
            "measurement_period_seconds": latency_stats.measurement_period_seconds
        }
        
        if include_measurements:
            measurements = validation_service.get_session_measurements(session_id)
            response_data["measurements"] = [m.to_dict() for m in measurements]
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latency results for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get latency results: {str(e)}")


@router.post("/detection-event")
async def record_detection_event(
    request: DetectionEventRequest,
    db: SessionLocal = Depends(get_db)
):
    """
    Record a manual detection event (for testing/calibration)
    
    This endpoint allows manual recording of detection events, useful for:
    - Testing the latency validation system
    - Calibrating LabJack thresholds
    - Simulating detection events for development
    """
    try:
        logger.info(f"Recording manual detection event for session {request.session_id}")
        
        # Validate session exists
        test_session = db.query(TestSession).filter(TestSession.id == request.session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail=f"Test session {request.session_id} not found")
        
        # Get timing service to get video start time
        timing_service = get_timing_service()
        video_timing = timing_service.get_video_start_time(request.session_id)
        
        if not video_timing:
            raise HTTPException(status_code=400, detail="Video timing not started for this session")
        
        video_start_time, video_start_time_unix = video_timing
        
        # Create detection event object
        detection_timestamp = datetime.fromtimestamp(request.timestamp, tz=timezone.utc)
        
        service_detection_event = ServiceDetectionEvent(
            detection_id=f"MANUAL_{request.session_id}_{int(request.timestamp * 1000)}",
            timestamp=detection_timestamp,
            timestamp_unix=request.timestamp,
            voltage_level=request.voltage_level,
            channel=request.channel,
            threshold=request.threshold,
            session_id=request.session_id,
            video_id=test_session.video_id,
            metadata={"source": "manual_api_request"}
        )
        
        # Calculate latency
        validation_service = get_validation_service()
        latency_measurement = validation_service.calculate_latency(
            detection_event=service_detection_event,
            video_start_time=video_start_time,
            video_start_time_unix=video_start_time_unix
        )
        
        # Store in database
        detection_event = DetectionEvent(
            test_session_id=request.session_id,
            video_id=test_session.video_id,
            timestamp=request.timestamp,
            detection_id=service_detection_event.detection_id,
            validation_result=None,  # Will be populated by ground truth matching service
            labjack_timestamp=request.timestamp,
            video_start_time=video_start_time_unix,
            latency_ms=latency_measurement.latency_ms,
            latency_threshold_ms=latency_measurement.threshold_ms,
            latency_result=latency_measurement.result.value,
            voltage_level=request.voltage_level,
            detection_channel=request.channel,
            frame_number=0,  # FIXED: Manual detection - frame correlation will be computed later
            video_frame_number=0  # FIXED: Added for consistency with orchestrator
        )
        
        db.add(detection_event)
        db.commit()
        
        logger.info(f"Recorded manual detection event with {latency_measurement.latency_ms:.2f}ms latency ({latency_measurement.result.value})")
        
        return {
            "success": True,
            "detection_event": service_detection_event.to_dict(),
            "latency_measurement": latency_measurement.to_dict(),
            "message": f"Manual detection event recorded with {latency_measurement.latency_ms:.2f}ms latency"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording manual detection event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record detection event: {str(e)}")


@router.get("/test-detection-channel")
async def test_detection_channel(
    channel: str = "AIN0",
    threshold: float = 2.5
):
    """
    Test LabJack detection channel and current voltage reading
    
    Useful for:
    - Verifying LabJack connection
    - Testing detection thresholds
    - Calibrating voltage levels
    """
    try:
        detection_service = get_detection_service(threshold)
        
        # Initialize service if needed
        await detection_service.initialize()
        
        # Test the channel
        test_result = await detection_service.test_detection_channel(channel)
        
        return {
            "success": test_result["success"],
            "channel": channel,
            "threshold": threshold,
            "test_result": test_result,
            "detection_service_status": detection_service.get_status()
        }
        
    except Exception as e:
        logger.error(f"Error testing detection channel {channel}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test detection channel: {str(e)}")


@router.get("/service-status")
async def get_service_status():
    """
    Get status of all LabJack timing services
    
    Returns status information for:
    - LabJack Detection Service
    - Video Timing Service  
    - Latency Validation Service
    """
    try:
        detection_service = get_detection_service()
        timing_service = get_timing_service()
        validation_service = get_validation_service()
        
        return {
            "detection_service": detection_service.get_status(),
            "timing_service": timing_service.get_service_status(),
            "validation_service": validation_service.get_service_status(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get service status: {str(e)}")


# Helper Functions

async def _store_detection_events_with_latency(
    session_id: str,
    detection_events: List[ServiceDetectionEvent],
    video_start_time_unix: float,
    latency_stats,
    db: SessionLocal
):
    """Store detection events in database with latency calculations"""
    try:
        # Get latency measurements
        validation_service = get_validation_service()
        measurements = validation_service.get_session_measurements(session_id)
        measurement_map = {m.detection_event.detection_id: m for m in measurements}
        
        # Store each detection event
        for detection_event in detection_events:
            measurement = measurement_map.get(detection_event.detection_id)
            
            db_detection = DetectionEvent(
                test_session_id=session_id,
                video_id=detection_event.video_id,
                timestamp=detection_event.timestamp_unix,
                detection_id=detection_event.detection_id,
                validation_result=None,  # Will be populated by ground truth matching service
                labjack_timestamp=detection_event.timestamp_unix,
                video_start_time=video_start_time_unix,
                latency_ms=measurement.latency_ms if measurement else None,
                latency_threshold_ms=measurement.threshold_ms if measurement else None,
                latency_result=measurement.result.value if measurement else "error",
                voltage_level=detection_event.voltage_level,
                detection_channel=detection_event.channel,
                frame_number=0,  # FIXED: Batch processing - frame correlation computed later
                video_frame_number=0,  # FIXED: Added for consistency
                # Legacy fields
                confidence=1.0 if measurement and measurement.result.value == "pass" else 0.0,
                class_label="detection",
                vru_type="detection"
            )
            
            db.add(db_detection)
        
        db.commit()
        logger.info(f"Stored {len(detection_events)} detection events with latency data")
        
    except Exception as e:
        logger.error(f"Error storing detection events: {e}")
        db.rollback()
        raise
