"""
Video Presentation Timing API for HIL Testing

This API measures the actual video start time vs command time to calculate
the true video presentation delay, enabling accurate detection latency measurement.

Timeline Measurement:
1. T0: User clicks "Start Test" (LabJack monitoring begins)
2. T1: Video play command sent to frontend
3. T2: Video actually begins displaying (THIS IS WHAT WE MEASURE)
4. T3: Ground truth event occurs in video timeline
5. T4: LabJack detects signal

True Detection Latency = T4 - T2 (not T4 - T0)
Video Presentation Delay = T2 - T1
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import time
import logging
from typing import Dict, Any

from database import get_db
from models import TestSession
from services.video_timing_service import get_video_timing_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/video-timing", tags=["Video Timing"])


@router.post("/session/{session_id}/video-started")
async def record_actual_video_start(
    session_id: str,
    video_start_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Record the actual video start timestamp when video begins playing
    
    Args:
        session_id: Test session ID
        video_start_data: {
            "client_timestamp": timestamp when video started playing,
            "video_element_ready": true/false if video element is ready,
            "video_duration": duration in seconds,
            "video_metadata": additional metadata
        }
    """
    try:
        # Get the session
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # Record high-precision server timestamp
        server_timestamp = time.time()
        client_timestamp = video_start_data.get("client_timestamp")
        
        # Calculate presentation delay (server command time vs actual video start)
        command_timestamp = session.started_at.timestamp() if session.started_at else server_timestamp
        presentation_delay_ms = (client_timestamp - command_timestamp) * 1000 if client_timestamp else 0
        
        # Use VideoTimingService for precise measurement
        video_timing_service = get_video_timing_service()
        
        # Override the timing service with actual measured video start
        precise_video_start = video_timing_service.start_video_timing(
            session_id=session_id,
            video_id=session.video_id or "unknown",
            db=db,
            video_metadata={
                "actual_start_timestamp": client_timestamp or server_timestamp,
                "presentation_delay_ms": presentation_delay_ms,
                "measurement_source": "frontend_video_element",
                **video_start_data
            }
        )
        
        # Store the actual video start time (not command time)
        if hasattr(session, 'video_playback_start_time'):
            session.video_playback_start_time = client_timestamp or server_timestamp
            session.video_timing_sync_status = "measured_actual_start"
            
        # Store presentation delay measurement
        if hasattr(session, 'configuration') and session.configuration:
            session.configuration.update({
                "video_presentation_delay_ms": presentation_delay_ms,
                "video_command_timestamp": command_timestamp,
                "video_actual_start_timestamp": client_timestamp or server_timestamp,
                "timing_measurement_method": "frontend_video_events"
            })
        
        db.commit()
        
        logger.info(f"✅ Recorded actual video start for session {session_id}: "
                   f"Presentation delay: {presentation_delay_ms:.1f}ms")
        
        return {
            "success": True,
            "session_id": session_id,
            "video_command_timestamp": command_timestamp,
            "video_actual_start_timestamp": client_timestamp or server_timestamp,
            "presentation_delay_ms": presentation_delay_ms,
            "timing_quality": "measured_actual_video_start"
        }
        
    except Exception as e:
        logger.error(f"Failed to record video start timing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record timing: {str(e)}")


@router.get("/session/{session_id}/presentation-delay")
async def get_video_presentation_delay(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get measured video presentation delay for a session"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # Get timing data from VideoTimingService
        video_timing_service = get_video_timing_service()
        timing_data = video_timing_service.get_timing_data(session_id)
        
        if timing_data and hasattr(session, 'configuration') and session.configuration:
            presentation_delay = session.configuration.get("video_presentation_delay_ms", 0)
            return {
                "session_id": session_id,
                "presentation_delay_ms": presentation_delay,
                "video_command_timestamp": session.configuration.get("video_command_timestamp"),
                "video_actual_start_timestamp": session.configuration.get("video_actual_start_timestamp"),
                "measurement_method": session.configuration.get("timing_measurement_method"),
                "timing_data": timing_data.__dict__ if timing_data else None
            }
        else:
            return {
                "session_id": session_id,
                "presentation_delay_ms": None,
                "error": "No presentation delay measurement available"
            }
            
    except Exception as e:
        logger.error(f"Failed to get presentation delay: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get timing: {str(e)}")