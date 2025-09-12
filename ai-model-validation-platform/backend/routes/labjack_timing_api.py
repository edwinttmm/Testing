"""
LabJack Timing Validation API Endpoints

This module provides comprehensive REST API endpoints for LabJack timing validation system,
including video timing synchronization, detection event processing, and latency analysis.

Features:
- Video timing start/stop with LabJack monitoring
- Real-time detection event processing with latency calculation
- Latency-based validation and Pass/Fail determination
- WebSocket events for real-time updates
- Comprehensive session management
- Detection event storage and retrieval
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, validator
import uuid
import logging
import json
import asyncio
from decimal import Decimal

from database import SessionLocal
from src.models.labjack_models import (
    LabJackDetection, VideoDetection, DetectionSynchronization,
    DetectionConfiguration, TemporalAnalysisResult,
    DetectionSourceEnum, DetectionStatusEnum, SynchronizationStatusEnum
)

# Import timing services
try:
    from src.services.video_timing_service import VideoTimingService
    from src.services.labjack_detection_service import LabJackDetectionService
    from src.services.latency_validation_service import LatencyValidationService
except ImportError:
    # Fallback imports if services are in different locations
    from src.services.simple_labjack_detection import SimpleLabJackDetector as LabJackDetectionService
    VideoTimingService = None
    LatencyValidationService = None

logger = logging.getLogger(__name__)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create router
router = APIRouter(prefix="/api", tags=["LabJack Timing Validation"])

# WebSocket connection manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)
        
    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
                
    async def send_event(self, session_id: str, event_type: str, data: Dict[str, Any]):
        if session_id in self.active_connections:
            message = {"event": event_type, "data": data, "timestamp": datetime.utcnow().isoformat()}
            disconnected = []
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    disconnected.append(connection)
            # Remove disconnected connections
            for conn in disconnected:
                self.active_connections[session_id].remove(conn)

manager = ConnectionManager()

# Pydantic models for API requests/responses

class StartTimingRequest(BaseModel):
    """Request model for starting timing session"""
    video_id: str = Field(..., description="Video identifier for timing synchronization")
    latency_threshold_ms: float = Field(100.0, ge=1.0, le=10000.0, description="Maximum acceptable latency in milliseconds")
    voltage_threshold: float = Field(2.5, ge=0.1, le=10.0, description="Voltage threshold for detection events")
    detection_channels: Optional[List[int]] = Field([0], description="LabJack channels to monitor")
    sampling_rate_hz: Optional[float] = Field(1000.0, description="Sampling rate in Hz")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional session metadata")

class DetectionEventRequest(BaseModel):
    """Request model for detection events from LabJack"""
    session_id: str = Field(..., description="Test session identifier")
    timestamp: float = Field(..., description="High-precision timestamp of detection event")
    voltage: float = Field(..., description="Voltage level at detection")
    channel: int = Field(..., ge=0, le=15, description="LabJack channel number")
    pin_state: Optional[bool] = Field(None, description="Digital pin state if applicable")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional event metadata")

class StartTimingResponse(BaseModel):
    """Response model for timing session start"""
    session_id: str
    video_start_timestamp: float
    monitoring_status: str
    labjack_status: str
    configuration: Dict[str, Any]
    message: str

class DetectionEventResponse(BaseModel):
    """Response model for detection event processing"""
    event_id: str
    session_id: str
    latency_ms: Optional[float]
    validation_result: str  # "PASS", "FAIL", "PENDING"
    timestamp_processed: float
    message: str

class LatencyResultsResponse(BaseModel):
    """Response model for latency results"""
    session_id: str
    total_events: int
    pass_count: int
    fail_count: int
    pass_rate: float
    average_latency_ms: Optional[float]
    min_latency_ms: Optional[float]
    max_latency_ms: Optional[float]
    latency_distribution: Dict[str, int]  # Histogram bins
    threshold_ms: float
    session_status: str

class StopTimingResponse(BaseModel):
    """Response model for timing session stop"""
    session_id: str
    session_duration_ms: float
    total_events: int
    final_results: LatencyResultsResponse
    message: str

class DetectionEvent(BaseModel):
    """Detection event details"""
    event_id: str
    timestamp: float
    voltage: float
    channel: int
    latency_ms: Optional[float]
    validation_result: str
    video_timestamp: Optional[float]
    metadata: Optional[Dict[str, Any]]

class DetectionEventsResponse(BaseModel):
    """Response model for detection events list"""
    session_id: str
    events: List[DetectionEvent]
    total_count: int
    filtered_count: int
    session_status: str

# Active timing sessions storage
active_sessions: Dict[str, Dict[str, Any]] = {}

# Helper functions

def calculate_latency_ms(video_start_timestamp: float, detection_timestamp: float) -> float:
    """Calculate latency between video start and detection event"""
    return (detection_timestamp - video_start_timestamp) * 1000

def validate_latency(latency_ms: float, threshold_ms: float) -> str:
    """Validate if latency meets threshold criteria"""
    if latency_ms <= threshold_ms:
        return "PASS"
    else:
        return "FAIL"

def create_latency_distribution(latencies: List[float]) -> Dict[str, int]:
    """Create latency distribution histogram"""
    if not latencies:
        return {}
    
    # Create bins for histogram (0-10ms, 10-25ms, 25-50ms, 50-100ms, 100-500ms, 500+ms)
    bins = {
        "0-10ms": 0,
        "10-25ms": 0,
        "25-50ms": 0,
        "50-100ms": 0,
        "100-500ms": 0,
        "500ms+": 0
    }
    
    for latency in latencies:
        if latency <= 10:
            bins["0-10ms"] += 1
        elif latency <= 25:
            bins["10-25ms"] += 1
        elif latency <= 50:
            bins["25-50ms"] += 1
        elif latency <= 100:
            bins["50-100ms"] += 1
        elif latency <= 500:
            bins["100-500ms"] += 1
        else:
            bins["500ms+"] += 1
    
    return bins

# API Endpoints

@router.post("/test-sessions/{session_id}/start-timing", response_model=StartTimingResponse)
async def start_timing_session(
    session_id: str,
    request: StartTimingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start video timing and LabJack monitoring for a test session.
    
    This endpoint initializes the timing validation system by:
    1. Starting video timing service
    2. Configuring LabJack detection monitoring
    3. Setting up real-time event processing
    4. Storing session configuration
    """
    try:
        logger.info(f"Starting timing session {session_id} with video {request.video_id}")
        
        # Check if session is already active
        if session_id in active_sessions:
            raise HTTPException(status_code=400, detail="Session already active")
        
        # Get current timestamp as video start time
        video_start_timestamp = time.time()
        
        # Initialize timing services
        labjack_service = None
        video_service = None
        
        try:
            # Initialize LabJack detection service
            if LabJackDetectionService:
                labjack_service = LabJackDetectionService()
                if hasattr(labjack_service, 'configure'):
                    labjack_service.configure(
                        channels=request.detection_channels or [0],
                        voltage_threshold=request.voltage_threshold,
                        sampling_rate=request.sampling_rate_hz or 1000.0
                    )
                
                # Start monitoring
                if hasattr(labjack_service, 'start_monitoring'):
                    labjack_service.start_monitoring()
                    labjack_status = "MONITORING"
                else:
                    labjack_status = "CONFIGURED"
            else:
                labjack_status = "SERVICE_UNAVAILABLE"
            
            # Initialize video timing service
            if VideoTimingService:
                video_service = VideoTimingService()
                if hasattr(video_service, 'start_timing'):
                    video_service.start_timing(request.video_id, video_start_timestamp)
            
        except Exception as service_error:
            logger.warning(f"Service initialization warning: {service_error}")
            labjack_status = "FALLBACK_MODE"
        
        # Store session configuration
        session_config = {
            "session_id": session_id,
            "video_id": request.video_id,
            "video_start_timestamp": video_start_timestamp,
            "latency_threshold_ms": request.latency_threshold_ms,
            "voltage_threshold": request.voltage_threshold,
            "detection_channels": request.detection_channels or [0],
            "sampling_rate_hz": request.sampling_rate_hz or 1000.0,
            "metadata": request.metadata or {},
            "labjack_service": labjack_service,
            "video_service": video_service,
            "detection_events": [],
            "status": "ACTIVE",
            "created_at": datetime.utcnow().isoformat()
        }
        
        active_sessions[session_id] = session_config
        
        # Store configuration in database
        db_config = DetectionConfiguration(
            id=str(uuid.uuid4()),
            session_id=session_id,
            detection_window_ms=request.latency_threshold_ms,
            voltage_threshold=request.voltage_threshold,
            channels_config={"channels": request.detection_channels or [0]},
            metadata_config=request.metadata or {},
            created_at=datetime.utcnow()
        )
        db.add(db_config)
        db.commit()
        
        logger.info(f"Successfully started timing session {session_id}")
        
        return StartTimingResponse(
            session_id=session_id,
            video_start_timestamp=video_start_timestamp,
            monitoring_status="ACTIVE",
            labjack_status=labjack_status,
            configuration={
                "video_id": request.video_id,
                "latency_threshold_ms": request.latency_threshold_ms,
                "voltage_threshold": request.voltage_threshold,
                "detection_channels": request.detection_channels or [0],
                "sampling_rate_hz": request.sampling_rate_hz or 1000.0
            },
            message="Timing session started successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting timing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start timing session: {str(e)}")

@router.post("/labjack/detection-event", response_model=DetectionEventResponse)
async def process_detection_event(
    request: DetectionEventRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Process detection event from LabJack hardware.
    
    This endpoint:
    1. Receives detection event from LabJack
    2. Calculates latency from video start
    3. Validates Pass/Fail based on threshold
    4. Stores event in database
    5. Sends real-time WebSocket updates
    """
    try:
        session_id = request.session_id
        
        # Check if session exists and is active
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found or not active")
        
        session_config = active_sessions[session_id]
        
        if session_config.get("status") != "ACTIVE":
            raise HTTPException(status_code=400, detail="Session is not active")
        
        # Calculate latency
        video_start_timestamp = session_config["video_start_timestamp"]
        latency_ms = calculate_latency_ms(video_start_timestamp, request.timestamp)
        
        # Validate latency
        threshold_ms = session_config["latency_threshold_ms"]
        validation_result = validate_latency(latency_ms, threshold_ms)
        
        # Generate event ID
        event_id = str(uuid.uuid4())
        
        # Create detection event record
        detection_event = LabJackDetection(
            id=event_id,
            session_id=session_id,
            detection_timestamp=datetime.fromtimestamp(request.timestamp, tz=timezone.utc),
            voltage_level=request.voltage,
            channel_number=request.channel,
            pin_state=request.pin_state,
            source_type=DetectionSourceEnum.LABJACK_HARDWARE,
            detection_status=DetectionStatusEnum.VALIDATED if validation_result == "PASS" else DetectionStatusEnum.INVALID,
            metadata_json=request.metadata or {},
            created_at=datetime.utcnow()
        )
        
        # Add to database
        db.add(detection_event)
        
        # Store event in session
        event_data = {
            "event_id": event_id,
            "timestamp": request.timestamp,
            "voltage": request.voltage,
            "channel": request.channel,
            "latency_ms": latency_ms,
            "validation_result": validation_result,
            "metadata": request.metadata
        }
        
        session_config["detection_events"].append(event_data)
        
        db.commit()
        
        # Send real-time WebSocket event
        await manager.send_event(session_id, "detection_event", {
            "event_id": event_id,
            "timestamp": request.timestamp,
            "voltage": request.voltage,
            "channel": request.channel,
            "validation_result": validation_result
        })
        
        # Send latency calculation event
        await manager.send_event(session_id, "latency_calculated", {
            "event_id": event_id,
            "latency_ms": latency_ms,
            "threshold_ms": threshold_ms,
            "validation_result": validation_result,
            "pass_rate": calculate_current_pass_rate(session_config["detection_events"])
        })
        
        logger.info(f"Processed detection event {event_id} for session {session_id}: {validation_result} (latency: {latency_ms:.2f}ms)")
        
        return DetectionEventResponse(
            event_id=event_id,
            session_id=session_id,
            latency_ms=latency_ms,
            validation_result=validation_result,
            timestamp_processed=time.time(),
            message=f"Detection event processed: {validation_result} (latency: {latency_ms:.2f}ms)"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing detection event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process detection event: {str(e)}")

@router.get("/test-sessions/{session_id}/latency-results", response_model=LatencyResultsResponse)
async def get_latency_results(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get latency-based results for a test session.
    
    This endpoint replaces the current results endpoint with latency-focused metrics:
    - Pass rate based on latency thresholds
    - Average, min, max latency statistics
    - Latency distribution histogram
    - Detailed validation results
    """
    try:
        # Check if session exists
        if session_id not in active_sessions:
            # Try to load from database
            db_detections = db.query(LabJackDetection).filter(
                LabJackDetection.session_id == session_id
            ).all()
            
            if not db_detections:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Reconstruct session data from database
            session_config = {
                "detection_events": [],
                "latency_threshold_ms": 100.0  # Default if not found
            }
            
            # Get configuration from database
            db_config = db.query(DetectionConfiguration).filter(
                DetectionConfiguration.session_id == session_id
            ).first()
            
            if db_config:
                session_config["latency_threshold_ms"] = db_config.detection_window_ms
            
            # Convert database records to event format
            for detection in db_detections:
                # Calculate latency if possible (requires video start timestamp)
                latency_ms = None
                validation_result = "UNKNOWN"
                
                if detection.detection_status == DetectionStatusEnum.VALIDATED:
                    validation_result = "PASS"
                elif detection.detection_status == DetectionStatusEnum.INVALID:
                    validation_result = "FAIL"
                
                event_data = {
                    "event_id": detection.id,
                    "timestamp": detection.detection_timestamp.timestamp(),
                    "voltage": detection.voltage_level,
                    "channel": detection.channel_number,
                    "latency_ms": latency_ms,
                    "validation_result": validation_result,
                    "metadata": detection.metadata_json
                }
                session_config["detection_events"].append(event_data)
        else:
            session_config = active_sessions[session_id]
        
        # Calculate results
        events = session_config["detection_events"]
        total_events = len(events)
        
        if total_events == 0:
            return LatencyResultsResponse(
                session_id=session_id,
                total_events=0,
                pass_count=0,
                fail_count=0,
                pass_rate=0.0,
                average_latency_ms=None,
                min_latency_ms=None,
                max_latency_ms=None,
                latency_distribution={},
                threshold_ms=session_config.get("latency_threshold_ms", 100.0),
                session_status=session_config.get("status", "UNKNOWN")
            )
        
        # Count pass/fail
        pass_count = sum(1 for event in events if event.get("validation_result") == "PASS")
        fail_count = sum(1 for event in events if event.get("validation_result") == "FAIL")
        pass_rate = (pass_count / total_events) * 100 if total_events > 0 else 0.0
        
        # Calculate latency statistics
        latencies = [event["latency_ms"] for event in events if event.get("latency_ms") is not None]
        
        average_latency_ms = sum(latencies) / len(latencies) if latencies else None
        min_latency_ms = min(latencies) if latencies else None
        max_latency_ms = max(latencies) if latencies else None
        
        # Create latency distribution
        latency_distribution = create_latency_distribution(latencies)
        
        return LatencyResultsResponse(
            session_id=session_id,
            total_events=total_events,
            pass_count=pass_count,
            fail_count=fail_count,
            pass_rate=pass_rate,
            average_latency_ms=average_latency_ms,
            min_latency_ms=min_latency_ms,
            max_latency_ms=max_latency_ms,
            latency_distribution=latency_distribution,
            threshold_ms=session_config.get("latency_threshold_ms", 100.0),
            session_status=session_config.get("status", "UNKNOWN")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latency results for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get latency results: {str(e)}")

@router.post("/test-sessions/{session_id}/stop-timing", response_model=StopTimingResponse)
async def stop_timing_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Stop video timing and LabJack monitoring, finalize session results.
    
    This endpoint:
    1. Stops LabJack monitoring
    2. Stops video timing
    3. Finalizes all detection events
    4. Calculates final session statistics
    5. Sends session completion WebSocket event
    """
    try:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found or not active")
        
        session_config = active_sessions[session_id]
        
        # Calculate session duration
        start_time = datetime.fromisoformat(session_config["created_at"])
        end_time = datetime.utcnow()
        session_duration_ms = (end_time - start_time).total_seconds() * 1000
        
        # Stop services
        try:
            labjack_service = session_config.get("labjack_service")
            if labjack_service and hasattr(labjack_service, 'stop_monitoring'):
                labjack_service.stop_monitoring()
            
            video_service = session_config.get("video_service")
            if video_service and hasattr(video_service, 'stop_timing'):
                video_service.stop_timing()
        except Exception as service_error:
            logger.warning(f"Service cleanup warning: {service_error}")
        
        # Update session status
        session_config["status"] = "COMPLETED"
        session_config["ended_at"] = end_time.isoformat()
        
        # Get final results
        final_results = await get_latency_results(session_id, db)
        
        # Send session completed WebSocket event
        await manager.send_event(session_id, "session_completed", {
            "session_id": session_id,
            "session_duration_ms": session_duration_ms,
            "total_events": final_results.total_events,
            "pass_rate": final_results.pass_rate,
            "average_latency_ms": final_results.average_latency_ms
        })
        
        logger.info(f"Successfully stopped timing session {session_id} after {session_duration_ms:.2f}ms")
        
        return StopTimingResponse(
            session_id=session_id,
            session_duration_ms=session_duration_ms,
            total_events=len(session_config["detection_events"]),
            final_results=final_results,
            message="Timing session stopped successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping timing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop timing session: {str(e)}")

@router.get("/test-sessions/{session_id}/detection-events", response_model=DetectionEventsResponse)
async def get_detection_events(
    session_id: str,
    skip: int = Query(0, ge=0, description="Number of events to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of events to return"),
    validation_result: Optional[str] = Query(None, regex="^(PASS|FAIL|PENDING)$", description="Filter by validation result"),
    channel: Optional[int] = Query(None, ge=0, le=15, description="Filter by channel number"),
    db: Session = Depends(get_db)
):
    """
    Get all detection events with latencies for a session.
    
    This endpoint provides detailed detection event data for:
    - Debugging timing issues
    - Detailed latency analysis
    - Event-by-event inspection
    - Performance monitoring
    """
    try:
        events_data = []
        total_count = 0
        
        # Check active session first
        if session_id in active_sessions:
            session_config = active_sessions[session_id]
            session_events = session_config["detection_events"]
            
            # Apply filters
            filtered_events = session_events
            if validation_result:
                filtered_events = [e for e in filtered_events if e.get("validation_result") == validation_result]
            if channel is not None:
                filtered_events = [e for e in filtered_events if e.get("channel") == channel]
            
            total_count = len(session_events)
            
            # Apply pagination
            paginated_events = filtered_events[skip:skip + limit]
            
            # Convert to response format
            for event in paginated_events:
                events_data.append(DetectionEvent(
                    event_id=event["event_id"],
                    timestamp=event["timestamp"],
                    voltage=event["voltage"],
                    channel=event["channel"],
                    latency_ms=event.get("latency_ms"),
                    validation_result=event["validation_result"],
                    video_timestamp=None,  # Could be calculated if needed
                    metadata=event.get("metadata")
                ))
            
            session_status = session_config.get("status", "ACTIVE")
        else:
            # Load from database
            query = db.query(LabJackDetection).filter(
                LabJackDetection.session_id == session_id
            )
            
            # Apply filters
            if validation_result:
                status_map = {
                    "PASS": DetectionStatusEnum.VALIDATED,
                    "FAIL": DetectionStatusEnum.INVALID,
                    "PENDING": DetectionStatusEnum.PENDING
                }
                if validation_result in status_map:
                    query = query.filter(LabJackDetection.detection_status == status_map[validation_result])
            
            if channel is not None:
                query = query.filter(LabJackDetection.channel_number == channel)
            
            # Get total count
            total_count = db.query(LabJackDetection).filter(
                LabJackDetection.session_id == session_id
            ).count()
            
            if total_count == 0:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Apply pagination and ordering
            db_events = query.order_by(desc(LabJackDetection.detection_timestamp)).offset(skip).limit(limit).all()
            
            # Convert database records to response format
            for detection in db_events:
                validation_result_str = "UNKNOWN"
                if detection.detection_status == DetectionStatusEnum.VALIDATED:
                    validation_result_str = "PASS"
                elif detection.detection_status == DetectionStatusEnum.INVALID:
                    validation_result_str = "FAIL"
                elif detection.detection_status == DetectionStatusEnum.PENDING:
                    validation_result_str = "PENDING"
                
                events_data.append(DetectionEvent(
                    event_id=detection.id,
                    timestamp=detection.detection_timestamp.timestamp(),
                    voltage=detection.voltage_level,
                    channel=detection.channel_number,
                    latency_ms=None,  # Would need video start timestamp to calculate
                    validation_result=validation_result_str,
                    video_timestamp=None,
                    metadata=detection.metadata_json
                ))
            
            session_status = "STORED"
        
        return DetectionEventsResponse(
            session_id=session_id,
            events=events_data,
            total_count=total_count,
            filtered_count=len(events_data),
            session_status=session_status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detection events for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get detection events: {str(e)}")

# WebSocket endpoint for real-time updates
@router.websocket("/test-sessions/{session_id}/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time timing validation updates.
    
    Events sent:
    - detection_event: New detection event received
    - latency_calculated: Latency calculation completed
    - session_completed: Session finalized
    """
    await manager.connect(websocket, session_id)
    try:
        while True:
            # Keep connection alive and handle incoming messages if needed
            data = await websocket.receive_text()
            # Echo back for connection health check
            if data == "ping":
                await websocket.send_text(json.dumps({"event": "pong", "timestamp": datetime.utcnow().isoformat()}))
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        manager.disconnect(websocket, session_id)

# Helper functions

def calculate_current_pass_rate(events: List[Dict[str, Any]]) -> float:
    """Calculate current pass rate from events list"""
    if not events:
        return 0.0
    
    pass_count = sum(1 for event in events if event.get("validation_result") == "PASS")
    return (pass_count / len(events)) * 100

# Health check endpoint
@router.get("/labjack-timing/health")
async def health_check():
    """Health check for LabJack timing API"""
    active_session_count = len(active_sessions)
    
    # Check service availability
    services_status = {
        "labjack_detection_service": LabJackDetectionService is not None,
        "video_timing_service": VideoTimingService is not None,
        "latency_validation_service": LatencyValidationService is not None
    }
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_sessions": active_session_count,
        "services": services_status,
        "api_version": "1.0.0"
    }

# Session cleanup endpoint (for maintenance)
@router.delete("/test-sessions/{session_id}/cleanup")
async def cleanup_session(
    session_id: str,
    force: bool = Query(False, description="Force cleanup even if session is active")
):
    """Cleanup session data and resources"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_config = active_sessions[session_id]
    
    if session_config.get("status") == "ACTIVE" and not force:
        raise HTTPException(status_code=400, detail="Cannot cleanup active session. Use force=true to override.")
    
    # Cleanup services
    try:
        labjack_service = session_config.get("labjack_service")
        if labjack_service and hasattr(labjack_service, 'cleanup'):
            labjack_service.cleanup()
        
        video_service = session_config.get("video_service")
        if video_service and hasattr(video_service, 'cleanup'):
            video_service.cleanup()
    except Exception as service_error:
        logger.warning(f"Service cleanup warning: {service_error}")
    
    # Remove from active sessions
    del active_sessions[session_id]
    
    # Cleanup WebSocket connections
    if session_id in manager.active_connections:
        connections = manager.active_connections[session_id][:]
        for conn in connections:
            try:
                await conn.close()
            except:
                pass
        del manager.active_connections[session_id]
    
    logger.info(f"Successfully cleaned up session {session_id}")
    
    return {
        "message": "Session cleaned up successfully",
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat()
    }
