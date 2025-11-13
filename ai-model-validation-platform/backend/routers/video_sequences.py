"""
Video Sequences Router - HIL Multi-Video Testing Support

Handles video sequence playback tracking for Hardware-in-the-Loop testing.
Provides endpoints for video transition events and sequence management.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, root_validator
from typing import Optional, Dict, Any
import logging
from datetime import datetime

from database import SessionLocal
from models import VideoTestSequence, SequenceVideoResult
from services.detection_video_reassignment import reassign_null_video_ids

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video-sequences", tags=["Video Sequences"])


# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Request/Response Models
class VideoStartedRequest(BaseModel):
    videoId: str
    timestamp: Optional[float] = Field(default=None, description="Legacy timestamp field (seconds)")
    sequenceElapsedTime: Optional[float] = Field(
        default=None, description="Elapsed sequence time in seconds"
    )
    startedAt: Optional[float] = Field(
        default=None, alias="startedAt", description="Preferred field for video start (seconds)"
    )
    clientTimestamp: Optional[str] = Field(
        default=None,
        alias="clientTimestamp",
        description="Optional ISO timestamp supplied by frontend",
    )

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"

    @root_validator(pre=True)
    def reconcile_timestamp_fields(cls, values):
        # Map modern frontend payload keys onto legacy schema without failing
        if values.get("timestamp") is None:
            started_at = values.get("startedAt") or values.get("started_at")
            if started_at is not None:
                values["timestamp"] = started_at
        if values.get("sequenceElapsedTime") is None:
            elapsed = values.get("sequence_elapsed_time")
            if elapsed is not None:
                values["sequenceElapsedTime"] = elapsed
        if values.get("timestamp") is None:
            raise ValueError("timestamp or startedAt is required")
        if values.get("sequenceElapsedTime") is None:
            values["sequenceElapsedTime"] = 0.0
        return values


class VideoEndedRequest(BaseModel):
    videoId: str
    timestamp: Optional[float] = Field(default=None, description="Legacy timestamp field (seconds)")
    sequenceElapsedTime: Optional[float] = Field(
        default=None, description="Elapsed sequence time in seconds"
    )
    actualDuration: Optional[float] = Field(
        default=None,
        alias="actualDuration",
        description="Actual playback duration in seconds",
    )
    endedAt: Optional[float] = Field(
        default=None, alias="endedAt", description="Preferred end timestamp (seconds)"
    )
    clientTimestamp: Optional[str] = Field(
        default=None,
        alias="clientTimestamp",
        description="Optional ISO timestamp supplied by frontend",
    )

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"

    @root_validator(pre=True)
    def reconcile_end_fields(cls, values):
        if values.get("timestamp") is None:
            ended_at = values.get("endedAt") or values.get("ended_at")
            if ended_at is not None:
                values["timestamp"] = ended_at
        if values.get("sequenceElapsedTime") is None:
            elapsed = values.get("sequence_elapsed_time")
            if elapsed is not None:
                values["sequenceElapsedTime"] = elapsed
        if values.get("actualDuration") is None and values.get("actual_duration") is not None:
            values["actualDuration"] = values["actual_duration"]
        if values.get("timestamp") is None:
            raise ValueError("timestamp or endedAt is required")
        if values.get("sequenceElapsedTime") is None:
            values["sequenceElapsedTime"] = 0.0
        return values


class VideoEventResponse(BaseModel):
    status: str = "acknowledged"
    nextVideoId: Optional[str] = None
    message: Optional[str] = None


@router.post("/{sequence_id}/video-started", response_model=VideoEventResponse)
async def video_started(sequence_id: str, data: VideoStartedRequest, db: Session = Depends(get_db)):
    """
    Track when a video in a sequence starts playing.

    Called by SequentialVideoPlayer when video playback begins.
    Updates SequenceVideoResult with video start time.
    """
    try:
        logger.info(f"📹 Video started in sequence {sequence_id}: {data.videoId} at {data.timestamp}s")

        # Find the video sequence
        sequence = db.query(VideoTestSequence).filter(
            VideoTestSequence.id == sequence_id
        ).first()

        if not sequence:
            raise HTTPException(status_code=404, detail=f"Video sequence {sequence_id} not found")

        # Find the SequenceVideoResult for this video
        video_result = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == sequence_id,
            SequenceVideoResult.video_id == data.videoId
        ).first()

        if not video_result:
            raise HTTPException(
                status_code=404,
                detail=f"Video {data.videoId} not found in sequence {sequence_id}"
            )

        # Update video start time with nanosecond precision
        video_result.video_start_time = data.timestamp
        video_result.video_start_time_ns = str(int(data.timestamp * 1_000_000_000))
        video_result.video_status = "playing"

        # FIX #2: Initialize sequence start time if this is the first video
        # Use sequenceElapsedTime to backtrack to absolute sequence start
        if sequence.sequence_start_time is None and data.sequenceElapsedTime is not None:
            # Calculate absolute sequence start by subtracting elapsed time
            sequence.sequence_start_time = data.timestamp - data.sequenceElapsedTime
            logger.info(
                f"✅ Initialized sequence start time: {sequence.sequence_start_time:.6f} "
                f"(video started at {data.timestamp:.6f}, elapsed {data.sequenceElapsedTime:.3f}s)"
            )

        # FIX #3: Store relative timing for multi-video accuracy
        # Calculate frontend delay (useful for debugging timing issues)
        if data.sequenceElapsedTime is not None:
            # This represents how long the frontend took to fire 'playing' event
            # Store as milliseconds for consistency with other latency fields
            frontend_playing_delay_ms = data.sequenceElapsedTime * 1000.0

            logger.info(
                f"📹 Video {data.videoId} started at {data.timestamp:.6f} "
                f"(sequence elapsed: {data.sequenceElapsedTime:.3f}s, "
                f"frontend delay: {frontend_playing_delay_ms:.1f}ms)"
            )

        # Update sequence current video index
        sequence.current_video_index = video_result.sequence_order
        sequence.status = "playing"

        db.commit()
        db.refresh(video_result)

        # CRITICAL FIX: Invalidate detection assignment cache for multi-video sequences
        # This ensures subsequent detections use the latest video timing data
        try:
            from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
            monitor = DedicatedLabJackMonitor.get_instance()
            if monitor and sequence.test_session_id:
                monitor.invalidate_sequence_cache(sequence.test_session_id)
                logger.info(f"✅ Cache invalidated for session {sequence.test_session_id} after video-started")
        except Exception as cache_error:
            logger.warning(f"⚠️ Cache invalidation failed (non-critical): {cache_error}")

        # CRITICAL FIX: Emit WebSocket event for real-time frontend updates
        try:
            from socketio_server import sio
            await sio.emit('video_started', {
                'sequence_id': sequence_id,
                'video_id': data.videoId,
                'timestamp': data.timestamp,
                'sequence_elapsed': data.sequenceElapsedTime,
                'started_at': data.startedAt,
                'sequence_order': video_result.sequence_order
            }, room=f"test_session_{sequence.test_session_id}")
            logger.debug(f"📡 Emitted video_started event via WebSocket")
        except Exception as ws_error:
            logger.warning(f"⚠️ WebSocket emission failed: {ws_error}")

        logger.info(f"✅ Video start event recorded for {sequence_id}")

        if sequence.test_session_id:
            try:
                reassignment_summary = await reassign_null_video_ids(sequence.test_session_id, dry_run=False)
                logger.info(
                    f"🎯 Detection reassignment after video-start ({sequence.test_session_id}): "
                    f"{reassignment_summary}"
                )
            except Exception as reassignment_error:
                logger.warning(
                    f"⚠️ Video start reassignment failed for session {sequence.test_session_id}: "
                    f"{reassignment_error}"
                )

        return VideoEventResponse(
            status="acknowledged",
            message=f"Video {data.videoId} start recorded"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error recording video start: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record video start: {str(e)}")


@router.post("/{sequence_id}/video-ended", response_model=VideoEventResponse)
async def video_ended(sequence_id: str, data: VideoEndedRequest, db: Session = Depends(get_db)):
    """
    Track when a video in a sequence ends.

    Called by SequentialVideoPlayer when video playback completes.
    Returns next video ID if available.
    """
    try:
        logger.info(f"📹 Video ended in sequence {sequence_id}: {data.videoId} at {data.timestamp}s")
        logger.info(f"   Duration: {data.actualDuration}s, Sequence elapsed: {data.sequenceElapsedTime}s")

        # Find the video sequence
        sequence = db.query(VideoTestSequence).filter(
            VideoTestSequence.id == sequence_id
        ).first()

        if not sequence:
            logger.warning(f"⚠️ Sequence {sequence_id} not found")
            return VideoEventResponse(
                status="acknowledged",
                nextVideoId=None,
                message="Sequence not found, assuming sequence complete"
            )

        # Find the SequenceVideoResult for this video
        video_result = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == sequence_id,
            SequenceVideoResult.video_id == data.videoId
        ).first()

        if not video_result:
            raise HTTPException(
                status_code=404,
                detail=f"Video {data.videoId} not found in sequence {sequence_id}"
            )

        # Update video end time and duration
        video_result.video_end_time = data.timestamp
        video_result.video_end_time_ns = str(int(data.timestamp * 1_000_000_000))
        video_result.actual_duration_ms = data.actualDuration * 1000 if data.actualDuration else None
        video_result.video_status = "completed"

        # Update sequence progress
        sequence.completed_videos = sequence.completed_videos + 1 if sequence.completed_videos else 1

        # Check if this is the last video in the sequence
        if sequence.completed_videos >= sequence.total_videos:
            sequence.status = "completed"
            next_video_id = None
        else:
            # Find next video in sequence
            next_result = db.query(SequenceVideoResult).filter(
                SequenceVideoResult.video_sequence_id == sequence_id,
                SequenceVideoResult.sequence_order == video_result.sequence_order + 1
            ).first()
            next_video_id = next_result.video_id if next_result else None

        db.commit()
        db.refresh(video_result)

        # CRITICAL FIX: Invalidate detection assignment cache for multi-video sequences
        # This ensures the next video's detections use fresh timing data
        try:
            from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
            monitor = DedicatedLabJackMonitor.get_instance()
            if monitor and sequence.test_session_id:
                monitor.invalidate_sequence_cache(sequence.test_session_id)
                logger.info(f"✅ Cache invalidated for session {sequence.test_session_id} after video-ended")
        except Exception as cache_error:
            logger.warning(f"⚠️ Cache invalidation failed (non-critical): {cache_error}")

        # CRITICAL FIX: Emit WebSocket event for real-time frontend updates
        try:
            from socketio_server import sio
            await sio.emit('video_ended', {
                'sequence_id': sequence_id,
                'video_id': data.videoId,
                'timestamp': data.timestamp,
                'duration': data.actualDuration,
                'sequence_elapsed': data.sequenceElapsedTime,
                'next_video_id': next_video_id,
                'sequence_order': video_result.sequence_order,
                'completed_videos': sequence.completed_videos,
                'total_videos': sequence.total_videos
            }, room=f"test_session_{sequence.test_session_id}")
            logger.debug(f"📡 Emitted video_ended event via WebSocket")
        except Exception as ws_error:
            logger.warning(f"⚠️ WebSocket emission failed: {ws_error}")

        logger.info(f"✅ Video end event recorded for {sequence_id}")

        if sequence.test_session_id:
            try:
                reassignment_summary = await reassign_null_video_ids(sequence.test_session_id, dry_run=False)
                logger.info(
                    f"🎯 Detection reassignment after video-end ({sequence.test_session_id}): "
                    f"{reassignment_summary}"
                )
            except Exception as reassignment_error:
                logger.warning(
                    f"⚠️ Video end reassignment failed for session {sequence.test_session_id}: "
                    f"{reassignment_error}"
                )

        return VideoEventResponse(
            status="acknowledged",
            nextVideoId=next_video_id,
            message=f"Video {data.videoId} completion recorded"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error recording video end: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record video end: {str(e)}")


@router.get("/{sequence_id}/status")
async def get_sequence_status(sequence_id: str, db: Session = Depends(get_db)):
    """Get current status of a video sequence"""
    try:
        # Find the video sequence
        sequence = db.query(VideoTestSequence).filter(
            VideoTestSequence.id == sequence_id
        ).first()

        if not sequence:
            raise HTTPException(status_code=404, detail="Sequence not found")

        # Get all video results for this sequence
        video_results = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == sequence_id
        ).order_by(SequenceVideoResult.sequence_order).all()

        # Get current video
        current_video = None
        if sequence.current_video_index is not None and sequence.current_video_index < len(video_results):
            current_video = video_results[sequence.current_video_index].video_id

        return {
            "sequence_id": sequence_id,
            "test_session_id": sequence.test_session_id,
            "status": sequence.status,
            "started_at": sequence.created_at.isoformat() if sequence.created_at else None,
            "current_video": current_video,
            "current_video_index": sequence.current_video_index,
            "videos_completed": sequence.completed_videos or 0,
            "total_videos": sequence.total_videos,
            "video_ids": sequence.video_ids,
            "videos": [
                {
                    "video_id": vr.video_id,
                    "sequence_order": vr.sequence_order,
                    "status": vr.video_status or "pending",
                    "started_at": vr.video_start_time,
                    "ended_at": vr.video_end_time,
                    "duration_ms": vr.actual_duration_ms,
                    "detection_count": vr.actual_detection_count or 0,
                    "passed_detections": vr.passed_detections or 0,
                    "failed_detections": vr.failed_detections or 0,
                    "avg_latency_ms": vr.avg_latency_ms,
                    "pass_rate_percent": vr.pass_rate_percent,
                    "validation_result": vr.validation_result
                }
                for vr in video_results
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting sequence status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{sequence_id}")
async def cleanup_sequence(sequence_id: str, db: Session = Depends(get_db)):
    """Clean up sequence state after completion (soft delete by marking as archived)"""
    try:
        # Find the video sequence
        sequence = db.query(VideoTestSequence).filter(
            VideoTestSequence.id == sequence_id
        ).first()

        if not sequence:
            raise HTTPException(status_code=404, detail="Sequence not found")

        # Mark as archived instead of deleting
        sequence.status = "archived"
        db.commit()

        logger.info(f"🗑️ Archived sequence {sequence_id}")

        return {"status": "archived", "sequence_id": sequence_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error archiving sequence: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
