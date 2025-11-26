"""
Simple Detection API Endpoints

Clean, simple API for background LabJack detection:
- Start detection before video
- Stop detection after video 
- Get status during video
- Analyze results post-video

NO WebSocket complexity - just simple REST endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import logging
import time
import json
from datetime import datetime

from database import get_db
# DEPRECATED 2025-11-21: simple_labjack_detection disabled to eliminate duplicate writes
# Entire endpoint file disabled - use dedicated_labjack_monitor directly
# from src.services.simple_labjack_detection import (
#     start_simple_detection,
#     stop_simple_detection,
#     get_detection_status,
#     analyze_detection_results
# )
from src.models.detection_session import DetectionSession, VideoEvent, StoredDetectionEvent
from models import Project, Video

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simple-detection", tags=["Simple Detection"])

# Pydantic models for API
class StartDetectionRequest(BaseModel):
    session_id: str = Field(..., description="Unique session identifier")
    tolerance_ms: int = Field(100, description="Detection tolerance in milliseconds", ge=1, le=1000)
    project_id: Optional[str] = Field(None, description="Associated project ID")
    video_id: Optional[str] = Field(None, description="Associated video ID")

class StartDetectionResponse(BaseModel):
    success: bool
    session_id: str
    tolerance_ms: int
    start_time: float
    message: str
    database_session_id: Optional[str] = None

class StopDetectionResponse(BaseModel):
    success: bool
    session_id: Optional[str]
    start_time: Optional[float]
    end_time: Optional[float] 
    duration_seconds: Optional[float]
    total_detections: int
    detection_events: List[Dict[str, Any]]
    message: str
    database_session_id: Optional[str] = None

class DetectionStatusResponse(BaseModel):
    running: bool
    session_id: Optional[str]
    start_time: Optional[float]
    current_time: Optional[float]
    duration_seconds: Optional[float]
    events_collected: Optional[int]
    tolerance_ms: Optional[int]
    message: str

class VideoEventRequest(BaseModel):
    timestamp: float = Field(..., description="Video timeline position in seconds")
    event_type: str = Field(..., description="Event type (VRU detection, ground truth, etc.)")
    class_label: Optional[str] = Field(None, description="Object class (pedestrian, cyclist, etc.)")
    confidence: Optional[float] = Field(None, description="Confidence score", ge=0, le=1)
    bbox_x: Optional[float] = Field(None, description="Bounding box X coordinate")
    bbox_y: Optional[float] = Field(None, description="Bounding box Y coordinate") 
    bbox_width: Optional[float] = Field(None, description="Bounding box width")
    bbox_height: Optional[float] = Field(None, description="Bounding box height")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class AnalyzeDetectionRequest(BaseModel):
    video_events: List[VideoEventRequest] = Field(..., description="Video events for correlation")
    save_to_database: bool = Field(True, description="Save analysis to database")

@router.post("/start", response_model=StartDetectionResponse)
async def start_detection_session(
    request: StartDetectionRequest,
    db: Session = Depends(get_db)
) -> StartDetectionResponse:
    """
    Start background LabJack detection session
    
    This starts the detection service running silently in the background.
    Video playback can proceed without any interference.
    """
    try:
        # Validate project/video existence if provided
        if request.project_id:
            project = db.query(Project).filter(Project.id == request.project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
        
        if request.video_id:
            video = db.query(Video).filter(Video.id == request.video_id).first()
            if not video:
                raise HTTPException(status_code=404, detail="Video not found")
        
        # Check if session ID already exists
        existing_session = db.query(DetectionSession).filter(
            DetectionSession.session_id == request.session_id
        ).first()
        
        if existing_session and existing_session.status == "active":
            raise HTTPException(
                status_code=400, 
                detail=f"Detection session '{request.session_id}' is already active"
            )
        
        # Start detection service
        result = start_simple_detection(request.session_id, request.tolerance_ms)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        # Create database record
        db_session = DetectionSession(
            session_id=request.session_id,
            project_id=request.project_id,
            video_id=request.video_id,
            start_time=result["start_time"],
            tolerance_ms=request.tolerance_ms,
            status="active",
            metadata={
                "api_version": "simple_v1",
                "started_via": "rest_api"
            }
        )
        
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        
        logger.info(f"Started detection session: {request.session_id}")
        
        return StartDetectionResponse(
            success=True,
            session_id=result["session_id"],
            tolerance_ms=result["tolerance_ms"],
            start_time=result["start_time"],
            message=result["message"],
            database_session_id=db_session.id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting detection session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop", response_model=StopDetectionResponse) 
async def stop_detection_session(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> StopDetectionResponse:
    """
    Stop background detection session and return all collected data
    
    This stops the detection service and returns all detection events
    that were collected during the session.
    """
    try:
        # Stop detection service
        result = stop_simple_detection()
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        # Update database record
        db_session = db.query(DetectionSession).filter(
            DetectionSession.session_id == result["session_id"]
        ).first()
        
        if db_session:
            db_session.end_time = result["end_time"]
            db_session.duration_seconds = result["duration_seconds"]
            db_session.total_detections = result["total_detections"]
            db_session.status = "completed"
            
            # Store detection events in database (background task)
            background_tasks.add_task(
                _store_detection_events,
                db_session.id,
                result["detection_events"]
            )
            
            db.commit()
            logger.info(f"Completed detection session: {result['session_id']} - {result['total_detections']} events")
        
        return StopDetectionResponse(
            success=result["success"],
            session_id=result["session_id"],
            start_time=result["start_time"],
            end_time=result["end_time"],
            duration_seconds=result["duration_seconds"],
            total_detections=result["total_detections"],
            detection_events=result["detection_events"],
            message=result["message"],
            database_session_id=db_session.id if db_session else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping detection session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", response_model=DetectionStatusResponse)
async def get_detection_session_status() -> DetectionStatusResponse:
    """
    Get current detection session status
    
    This can be called during video playback to check detection status
    without interfering with the video or detection process.
    """
    try:
        result = get_detection_status()
        
        return DetectionStatusResponse(
            running=result["running"],
            session_id=result.get("session_id"),
            start_time=result.get("start_time"),
            current_time=result.get("current_time"),
            duration_seconds=result.get("duration_seconds"),
            events_collected=result.get("events_collected"),
            tolerance_ms=result.get("tolerance_ms"),
            message=result["message"]
        )
        
    except Exception as e:
        logger.error(f"Error getting detection status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/{session_id}")
async def analyze_detection_session(
    session_id: str,
    request: AnalyzeDetectionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Analyze completed detection session against video events
    
    This performs post-processing analysis to correlate detection events
    with video events and calculate accuracy metrics.
    """
    try:
        # Get session from database
        db_session = db.query(DetectionSession).filter(
            DetectionSession.session_id == session_id
        ).first()
        
        if not db_session:
            raise HTTPException(status_code=404, detail="Detection session not found")
        
        if db_session.status != "completed":
            raise HTTPException(status_code=400, detail="Session must be completed before analysis")
        
        # Reconstruct session results for analysis
        session_data = {
            "session_id": session_id,
            "start_time": db_session.start_time,
            "end_time": db_session.end_time,
            "duration_seconds": db_session.duration_seconds,
            "detection_events": []
        }
        
        # Get detection events from database
        detection_events = db.query(StoredDetectionEvent).filter(
            StoredDetectionEvent.session_id == db_session.id
        ).order_by(StoredDetectionEvent.timestamp).all()
        
        for event in detection_events:
            session_data["detection_events"].append({
                "detection_id": event.detection_id,
                "timestamp": event.timestamp,
                "pin_state": event.pin_state,
                "metadata": event.metadata or {}
            })
        
        # Convert video events to analysis format
        video_events = [event.dict() for event in request.video_events]
        
        # Perform analysis
        analysis_result = analyze_detection_results(session_data, video_events)
        
        if not analysis_result["success"]:
            raise HTTPException(status_code=400, detail=analysis_result.get("message", "Analysis failed"))
        
        # Update database with analysis results
        if request.save_to_database:
            db_session.matched_detections = analysis_result["matched_detections"]
            db_session.accuracy_percentage = analysis_result["accuracy_percentage"]
            
            # Store video events and correlation data (background task)
            background_tasks.add_task(
                _store_analysis_results,
                db_session.id,
                video_events,
                analysis_result["video_correlations"]
            )
            
            db.commit()
        
        logger.info(f"Analysis completed for session: {session_id} - {analysis_result['accuracy_percentage']:.1f}% accuracy")
        
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing detection session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions")
async def list_detection_sessions(
    project_id: Optional[str] = None,
    video_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """List detection sessions with optional filtering"""
    try:
        query = db.query(DetectionSession)
        
        if project_id:
            query = query.filter(DetectionSession.project_id == project_id)
        
        if video_id:
            query = query.filter(DetectionSession.video_id == video_id)
            
        if status:
            query = query.filter(DetectionSession.status == status)
        
        total = query.count()
        sessions = query.offset(offset).limit(limit).all()
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "sessions": [
                {
                    "id": session.id,
                    "session_id": session.session_id,
                    "project_id": session.project_id,
                    "video_id": session.video_id,
                    "start_time": session.start_time,
                    "end_time": session.end_time,
                    "duration_seconds": session.duration_seconds,
                    "tolerance_ms": session.tolerance_ms,
                    "status": session.status,
                    "total_detections": session.total_detections,
                    "matched_detections": session.matched_detections,
                    "accuracy_percentage": session.accuracy_percentage,
                    "created_at": session.created_at.isoformat() if session.created_at else None
                }
                for session in sessions
            ]
        }
        
    except Exception as e:
        logger.error(f"Error listing detection sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}")
async def get_detection_session_details(
    session_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get detailed information about a specific detection session"""
    try:
        db_session = db.query(DetectionSession).filter(
            DetectionSession.session_id == session_id
        ).first()
        
        if not db_session:
            raise HTTPException(status_code=404, detail="Detection session not found")
        
        # Get detection events
        detection_events = db.query(StoredDetectionEvent).filter(
            StoredDetectionEvent.session_id == db_session.id
        ).order_by(StoredDetectionEvent.timestamp).all()
        
        # Get video events if any
        video_events = []
        if db_session.video_id:
            video_events_query = db.query(VideoEvent).filter(
                VideoEvent.video_id == db_session.video_id
            ).order_by(VideoEvent.timestamp).all()
            
            video_events = [
                {
                    "id": event.id,
                    "timestamp": event.timestamp,
                    "event_type": event.event_type,
                    "class_label": event.class_label,
                    "confidence": event.confidence,
                    "bbox_x": event.bbox_x,
                    "bbox_y": event.bbox_y,
                    "bbox_width": event.bbox_width,
                    "bbox_height": event.bbox_height,
                    "source": event.source,
                    "metadata": event.metadata
                }
                for event in video_events_query
            ]
        
        return {
            "session": {
                "id": db_session.id,
                "session_id": db_session.session_id,
                "project_id": db_session.project_id,
                "video_id": db_session.video_id,
                "start_time": db_session.start_time,
                "end_time": db_session.end_time,
                "duration_seconds": db_session.duration_seconds,
                "tolerance_ms": db_session.tolerance_ms,
                "status": db_session.status,
                "total_detections": db_session.total_detections,
                "matched_detections": db_session.matched_detections,
                "accuracy_percentage": db_session.accuracy_percentage,
                "metadata": db_session.metadata,
                "created_at": db_session.created_at.isoformat() if db_session.created_at else None,
                "updated_at": db_session.updated_at.isoformat() if db_session.updated_at else None
            },
            "detection_events": [
                {
                    "detection_id": event.detection_id,
                    "timestamp": event.timestamp,
                    "pin_state": event.pin_state,
                    "session_start_offset": event.session_start_offset,
                    "detection_sequence": event.detection_sequence,
                    "video_offset_seconds": event.video_offset_seconds,
                    "match_count": event.match_count,
                    "within_tolerance": event.within_tolerance,
                    "metadata": event.metadata
                }
                for event in detection_events
            ],
            "video_events": video_events
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detection session details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task functions
async def _store_detection_events(session_id: str, detection_events: List[Dict[str, Any]]) -> None:
    """Background task to store detection events in database"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        
        try:
            for event_data in detection_events:
                db_event = StoredDetectionEvent(
                    session_id=session_id,
                    detection_id=event_data["detection_id"],
                    timestamp=event_data["timestamp"],
                    pin_state=event_data["pin_state"],
                    session_start_offset=event_data.get("metadata", {}).get("session_start_offset"),
                    detection_sequence=event_data.get("metadata", {}).get("detection_sequence"),
                    metadata=event_data.get("metadata")
                )
                db.add(db_event)
            
            db.commit()
            logger.info(f"Stored {len(detection_events)} detection events for session {session_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error storing detection events: {e}")

async def _store_analysis_results(
    session_id: str,
    video_events: List[Dict[str, Any]], 
    correlations: List[Dict[str, Any]]
) -> None:
    """Background task to store analysis results"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        
        try:
            # Get session to get video_id
            session = db.query(DetectionSession).filter(DetectionSession.id == session_id).first()
            if not session or not session.video_id:
                return
            
            # Store video events
            for event_data in video_events:
                # Check if event already exists
                existing_event = db.query(VideoEvent).filter(
                    VideoEvent.video_id == session.video_id,
                    VideoEvent.timestamp == event_data["timestamp"],
                    VideoEvent.event_type == event_data["event_type"]
                ).first()
                
                if not existing_event:
                    db_event = VideoEvent(
                        video_id=session.video_id,
                        timestamp=event_data["timestamp"],
                        event_type=event_data["event_type"],
                        class_label=event_data.get("class_label"),
                        confidence=event_data.get("confidence"),
                        bbox_x=event_data.get("bbox_x"),
                        bbox_y=event_data.get("bbox_y"),
                        bbox_width=event_data.get("bbox_width"),
                        bbox_height=event_data.get("bbox_height"),
                        metadata=event_data.get("metadata"),
                        source="api_analysis"
                    )
                    db.add(db_event)
            
            # Update detection events with correlation data
            for correlation in correlations:
                detection_event = db.query(StoredDetectionEvent).filter(
                    StoredDetectionEvent.session_id == session_id,
                    StoredDetectionEvent.detection_id == correlation["detection_id"]
                ).first()
                
                if detection_event:
                    detection_event.video_offset_seconds = correlation["video_offset_seconds"]
                    detection_event.match_count = correlation["match_count"]
                    detection_event.within_tolerance = correlation["match_count"] > 0
                    detection_event.matched_video_events = correlation["matches"]
            
            db.commit()
            logger.info(f"Stored analysis results for session {session_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error storing analysis results: {e}")