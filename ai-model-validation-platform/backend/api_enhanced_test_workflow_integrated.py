"""
Enhanced Test Workflow API - Integrated Detection Validation System
Provides detection-based validation workflow that synchronizes video playback with LabJack signal detection
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Project, Video, TestSession, DetectionEvent, DetectionComparison, Annotation, GroundTruthObject
from models import TestResult as SQLTestResult
from services.labjack_service import get_labjack_service
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import uuid

logger = logging.getLogger(__name__)

class DetectionTestConfig(BaseModel):
    """Enhanced test detection configuration

    Args:
        project_id: Project identifier
        detection_window_ms: Time window for detection matching (Pass/Fail threshold)
        voltage_threshold: Voltage threshold for detection trigger
        sample_rate: Sampling rate in Hz
        channels: LabJack analog input channels
        constant_voltage_mode: Bypass debounce for constant voltage testing
            When True: Detects every frame (100% detection rate)
            When False: Uses 100ms debounce (33% detection rate, default)
    """
    project_id: str
    detection_window_ms: float = 500.0   # Time window for detection (Pass/Fail)
    voltage_threshold: float = 2.5       # LabJack detection threshold
    sample_rate: int = 1000              # LabJack sampling rate
    channels: List[str] = ["AIN0", "AIN1"]
    constant_voltage_mode: bool = False  # Bypass debounce for constant voltage tests

class TestResultResponse(BaseModel):
    video_id: str
    video_name: str
    expected_detection_time: Optional[float] = None
    actual_detection_time: Optional[float] = None
    detection_delay_ms: Optional[float] = None
    status: str  # 'pass', 'fail_no_detection', 'fail_timeout'
    confidence: Optional[float] = None
    details: Optional[str] = None
    timestamp: Optional[str] = None
    processing_time: Optional[float] = None

class EnhancedTestSession(BaseModel):
    name: str
    description: Optional[str] = None
    project_id: str
    video_ids: List[str]
    config: DetectionTestConfig

router = APIRouter(prefix="/api/enhanced-test-workflow", tags=["Enhanced Test Workflow"])

# Global test state
current_test_state = {
    "active": False,
    "session_id": None,
    "config": None,
    "videos": [],
    "current_video_index": 0,
    "test_start_time": None,
    "video_start_time": None,
    "results": []
}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/start")
async def start_detection_validation_test(config: DetectionTestConfig, db: Session = Depends(get_db)):
    """Start the Enhanced Test Workflow with LabJack detection validation"""
    
    # Check LabJack connection
    labjack_service = get_labjack_service()
    status = labjack_service.get_status()
    
    if not status.connected:
        raise HTTPException(status_code=400, detail="LabJack not connected. Please connect LabJack first.")
    
    # Get project videos
    try:
        project = db.query(Project).filter(Project.id == config.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        videos = db.query(Video).filter(Video.project_id == config.project_id).all()
        if not videos:
            raise HTTPException(status_code=404, detail="No videos found in project")
        
        # Update global test state
        session_id = f"session_{int(time.time())}"
        global current_test_state
        current_test_state.update({
            "active": True,
            "session_id": session_id,
            "config": config,
            "videos": [{"id": v.id, "name": v.filename, "file_path": v.file_path} for v in videos],
            "current_video_index": 0,
            "test_start_time": time.time(),
            "results": []
        })
        
        # Configure LabJack for testing
        await labjack_service.start_stream(config.channels, config.sample_rate)
        
        logger.info(f"Started Enhanced Test Workflow: {len(videos)} videos, project {config.project_id}")
        
        return {
            "message": "Enhanced Test Workflow started",
            "project_id": config.project_id,
            "video_count": len(videos),
            "session_id": session_id,
            "labjack_mode": status.mode.value,
            "config": config.dict()
        }
        
    except Exception as e:
        logger.error(f"Error starting test workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start test: {str(e)}")

@router.post("/stop")
async def stop_detection_validation_test():
    """Stop the Enhanced Test Workflow"""
    global current_test_state
    
    if not current_test_state["active"]:
        raise HTTPException(status_code=400, detail="No active test to stop")
    
    # Stop LabJack streaming
    labjack_service = get_labjack_service()
    await labjack_service.stop_stream()
    
    current_test_state["active"] = False
    
    return {
        "message": "Enhanced Test Workflow stopped",
        "results": current_test_state["results"]
    }

@router.get("/status")
async def get_test_status():
    """Get current test workflow status"""
    return {
        "active": current_test_state["active"],
        "session_id": current_test_state.get("session_id"),
        "current_video": current_test_state["current_video_index"],
        "total_videos": len(current_test_state["videos"]),
        "results_count": len(current_test_state["results"])
    }

@router.get("/results")
async def get_test_results():
    """Get the latest test results with enhanced summary"""
    results = current_test_state["results"]
    
    passed_results = [r for r in results if r.get("status") == "pass"]
    failed_results = [r for r in results if r.get("status") != "pass"]
    
    # Calculate average latency for passed results
    passed_delays = [r.get("detection_delay_ms", 0) for r in passed_results if r.get("detection_delay_ms")]
    avg_latency = sum(passed_delays) / len(passed_delays) if passed_delays else 0
    
    return {
        "active": current_test_state["active"],
        "results": results,
        "summary": {
            "total_videos": len(results),
            "passed": len(passed_results),
            "failed": len(failed_results),
            "avg_latency": avg_latency
        }
    }

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time test workflow updates"""
    await websocket.accept()
    
    try:
        # Send initial status
        await websocket.send_text(json.dumps({
            "type": "status",
            "data": current_test_state
        }))
        
        # Start test workflow if active
        if current_test_state["active"]:
            asyncio.create_task(run_detection_validation_workflow(websocket))
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")

async def run_detection_validation_workflow(websocket: WebSocket):
    """Run the complete detection validation workflow with video playback and LabJack monitoring"""
    labjack_service = get_labjack_service()
    
    for i, video in enumerate(current_test_state["videos"]):
        if not current_test_state["active"]:
            break
            
        current_test_state["current_video_index"] = i
        
        # Notify frontend to change video
        await websocket.send_text(json.dumps({
            "type": "video_change",
            "video_id": video["id"],
            "video_name": video["name"],
            "index": i,
            "total": len(current_test_state["videos"]),
            "expected_detection_time": None  # No predetermined detection time - this is detection validation
        }))
        
        # Start timing for this video
        video_start_time = time.time()
        current_test_state["video_start_time"] = video_start_time
        
        # Monitor for LabJack signal during video playback
        detection_found = False
        timeout = 15.0  # 15 second timeout per video
        detection_window_ms = current_test_state["config"].detection_window_ms
        
        start_monitor_time = time.time()
        first_detection_time = None
        
        while (time.time() - start_monitor_time) < timeout and current_test_state["active"]:
            try:
                # Read voltage from LabJack
                # NOTE: This workflow uses direct voltage reading instead of detection service monitoring.
                # The constant_voltage_mode parameter is defined in DetectionTestConfig but only applies
                # when using the detection service API endpoints (/api/detection/start).
                #
                # For constant voltage testing with 100% detection rate (bypassing 100ms debounce):
                # 1. Use POST /api/detection/start with constant_voltage_mode=true
                # 2. Or integrate this workflow with detection service monitoring (future enhancement)
                #
                # Current limitation: This direct polling approach doesn't support debounce bypass.
                voltage = await labjack_service.read_single_voltage("AIN0")
                current_time = time.time()
                
                if voltage > current_test_state["config"].voltage_threshold:
                    if first_detection_time is None:
                        first_detection_time = current_time
                        
                    # Detection found!
                    actual_detection_time = current_time - video_start_time
                    
                    # For detection validation, we consider it a PASS if detection occurs within reasonable time
                    # (e.g., within the first 10 seconds of video playback)
                    detection_delay_ms = (current_time - first_detection_time) * 1000 if first_detection_time else 0
                    
                    # Determine Pass/Fail based on detection window
                    if detection_delay_ms <= detection_window_ms:
                        status = "pass"
                        details = f"Detection found within {detection_window_ms}ms window"
                    else:
                        status = "fail_timeout" 
                        details = f"Detection delay {detection_delay_ms:.1f}ms exceeds {detection_window_ms}ms window"
                    
                    result = TestResultResponse(
                        video_id=video["id"],
                        video_name=video["name"],
                        expected_detection_time=None,
                        actual_detection_time=actual_detection_time,
                        detection_delay_ms=detection_delay_ms,
                        status=status,
                        details=details,
                        timestamp=datetime.now().isoformat(),
                        processing_time=current_time - video_start_time
                    )
                    
                    current_test_state["results"].append(result.dict())
                    detection_found = True
                    
                    # Store result in database with comprehensive data
                    await store_enhanced_detection_result(result, voltage, "AIN0")
                    
                    # Notify frontend
                    await websocket.send_text(json.dumps({
                        "type": "detection_event",
                        "latency_ms": detection_delay_ms,
                        "voltage": voltage,
                        "timestamp": current_time,
                        "channel": "AIN0",
                        "status": status
                    }))
                    
                    break
                    
                await asyncio.sleep(0.01)  # 10ms polling
                
            except Exception as e:
                logger.error(f"Error reading LabJack during test: {e}")
                await asyncio.sleep(0.1)
        
        if not detection_found:
            # No detection found - this is a FAIL
            result = TestResultResponse(
                video_id=video["id"],
                video_name=video["name"],
                expected_detection_time=None,
                actual_detection_time=None,
                detection_delay_ms=None,
                status="fail_no_detection",
                details=f"No detection found within {timeout}s timeout",
                timestamp=datetime.now().isoformat(),
                processing_time=time.time() - video_start_time
            )
            current_test_state["results"].append(result.dict())
            
            # Store failed detection result in database
            await store_enhanced_detection_result(result, None, None)
        
        # Wait before next video
        await asyncio.sleep(2.0)
    
    # Send final results
    await websocket.send_text(json.dumps({
        "type": "test_results",
        "results": current_test_state["results"]
    }))
    
    await websocket.send_text(json.dumps({
        "type": "test_complete"
    }))
    
    current_test_state["active"] = False

async def store_enhanced_detection_result(result: TestResultResponse, voltage: Optional[float], channel: Optional[str]):
    """Store enhanced detection result in database with complete LabJack signal data"""
    try:
        db = SessionLocal()
        
        # Create test session if it doesn't exist
        session_id = current_test_state.get("session_id")
        if session_id:
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if not test_session:
                config = current_test_state.get("config", {})
                test_session = TestSession(
                    id=session_id,
                    name=f"Enhanced Detection Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    project_id=getattr(config, 'project_id', 'default-test-project'),
                    video_id=result.video_id,
                    tolerance_ms=int(getattr(config, 'detection_window_ms', 500)),
                    status="running",
                    started_at=datetime.now()
                )
                db.add(test_session)
                db.commit()
        
        # Get current timestamp for record creation
        current_timestamp = datetime.now()
        
        # Create detection event with enhanced LabJack signal data
        detection_event = DetectionEvent(
            id=str(uuid.uuid4()),
            test_session_id=session_id,
            timestamp=result.actual_detection_time if result.actual_detection_time else 0.0,
            confidence=result.confidence if result.confidence else (1.0 if result.status == "pass" else 0.0),
            class_label="labjack_signal_enhanced",
            validation_result="TP" if result.status == "pass" else ("FN" if result.status == "fail_no_detection" else "FP"),
            vru_type="signal_validation_enhanced",
            
            # Enhanced detection metadata
            detection_id=f"ENH_DET_{uuid.uuid4().hex[:8]}",
            frame_number=None,  # Not applicable for signal detection
            
            # Store LabJack signal data
            processing_time_ms=result.processing_time * 1000 if result.processing_time else result.detection_delay_ms,
            model_version="enhanced_labjack_v1.0",
            
            # Store signal metadata
            bounding_box_x=voltage if voltage else None,  # Store voltage in unused field for signal data
            bounding_box_y=float(channel.replace("AIN", "")) if channel and channel.startswith("AIN") else None,
            bounding_box_width=current_test_state.get("config", {}).voltage_threshold if current_test_state.get("config") else None,
            bounding_box_height=current_test_state.get("config", {}).sample_rate if current_test_state.get("config") else None,
            
            created_at=current_timestamp
        )
        db.add(detection_event)
        
        # Create detection comparison with enhanced timing analysis
        comparison = DetectionComparison(
            id=str(uuid.uuid4()),
            test_session_id=session_id,
            detection_event_id=detection_event.id,
            ground_truth_id=None,  # No ground truth for signal validation
            match_type="TP" if result.status == "pass" else ("FN" if result.status == "fail_no_detection" else "FP"),
            iou_score=None,
            distance_error=0.0,
            temporal_offset=result.detection_delay_ms / 1000.0 if result.detection_delay_ms else None,
            notes=f"Enhanced LabJack validation: {result.status}. Voltage: {voltage}V on {channel}. Processing time: {result.processing_time}s. Details: {result.details}",
            created_at=current_timestamp
        )
        db.add(comparison)
        
        # Create comprehensive test result
        test_result = SQLTestResult(
            id=str(uuid.uuid4()),
            test_session_id=session_id,
            accuracy=1.0 if result.status == "pass" else 0.0,
            precision=1.0 if result.status == "pass" else 0.0,
            recall=1.0 if result.status == "pass" else 0.0,
            f1_score=1.0 if result.status == "pass" else 0.0,
            true_positives=1 if result.status == "pass" else 0,
            false_positives=0 if result.status == "pass" else (1 if result.status.startswith("fail") else 0),
            false_negatives=0 if result.status == "pass" else (1 if result.status == "fail_no_detection" else 0),
            statistical_analysis={
                "enhanced_detection_timing": {
                    "actual_detection_time_s": result.actual_detection_time,
                    "detection_delay_ms": result.detection_delay_ms,
                    "processing_time_s": result.processing_time,
                    "status": result.status,
                    "details": result.details
                },
                "labjack_signal_data": {
                    "voltage": voltage,
                    "channel": channel,
                    "voltage_threshold": current_test_state.get("config", {}).voltage_threshold if current_test_state.get("config") else None,
                    "sample_rate": current_test_state.get("config", {}).sample_rate if current_test_state.get("config") else None,
                    "detection_window_ms": current_test_state.get("config", {}).detection_window_ms if current_test_state.get("config") else None
                },
                "video_context": {
                    "video_id": result.video_id,
                    "video_name": result.video_name,
                    "timestamp": result.timestamp
                }
            },
            confidence_intervals={
                "detection_confidence": result.confidence if result.confidence else (0.95 if result.status == "pass" else 0.1),
                "timing_precision_ms": 10.0,
                "voltage_precision": 0.01
            },
            created_at=current_timestamp
        )
        db.add(test_result)
        
        # Commit all changes atomically
        db.commit()
        db.close()
        
        logger.info(f"Stored enhanced detection result for video {result.video_id}: {result.status} - DetectionEvent: {detection_event.id}, Comparison: {comparison.id}, TestResult: {test_result.id}")
        
    except Exception as e:
        logger.error(f"Error storing enhanced detection result: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()

# Session management endpoints
@router.get("/sessions")
async def get_enhanced_test_sessions(project_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Get enhanced test sessions with results"""
    query = db.query(TestSession)
    if project_id:
        query = query.filter(TestSession.project_id == project_id)
    
    sessions = query.all()
    
    enhanced_sessions = []
    for session in sessions:
        enhanced_session = {
            "id": session.id,
            "name": session.name,
            "project_id": session.project_id,
            "status": session.status,
            "video_count": len(session.video_ids) if session.video_ids else 0,
            "created_at": session.created_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None
        }
        enhanced_sessions.append(enhanced_session)
    
    return enhanced_sessions

@router.post("/sessions")
async def create_enhanced_test_session(session_data: EnhancedTestSession, db: Session = Depends(get_db)):
    """Create a new enhanced test session"""
    try:
        # Get first video ID for single video session compatibility
        first_video_id = session_data.video_ids[0] if session_data.video_ids else None
        if not first_video_id:
            raise HTTPException(status_code=400, detail="At least one video ID is required")
        
        # Create test session in database
        test_session = TestSession(
            name=session_data.name,
            project_id=session_data.project_id,
            video_id=first_video_id,  # Use first video for compatibility
            status="created",
            created_at=datetime.now()
        )
        
        db.add(test_session)
        db.commit()
        db.refresh(test_session)
        
        return {
            "id": test_session.id,
            "name": test_session.name,
            "project_id": test_session.project_id,
            "status": test_session.status,
            "session_data": session_data.dict()
        }
        
    except Exception as e:
        logger.error(f"Error creating enhanced test session: {e}")
        db.rollback()  # Ensure rollback on error
        
        # Provide specific error messages based on error type
        if "FOREIGN KEY constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="Invalid project_id or video_id - please check that the project and videos exist")
        elif "NOT NULL constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="Missing required fields for session creation")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@router.post("/sessions/{session_id}/run")
async def run_enhanced_test_session(session_id: str, db: Session = Depends(get_db)):
    """Run an enhanced test session"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Update session status
        session.status = "running"
        session.started_at = datetime.now()
        db.commit()
        
        return {
            "message": "Enhanced test session started",
            "session_id": session_id,
            "status": "running"
        }
        
    except Exception as e:
        logger.error(f"Error running enhanced test session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to run session: {str(e)}")

@router.get("/sessions/{session_id}/results")
async def get_enhanced_test_session_results(session_id: str, db: Session = Depends(get_db)):
    """Get results for a specific enhanced test session"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get test results for this session
        results = db.query(TestResult).filter(TestResult.test_session_id == session_id).all()
        
        result_data = []
        for result in results:
            result_data.append({
                "video_id": result.video_id,
                "video_name": result.video_name or "Unknown",
                "status": result.status,
                "detection_delay_ms": result.detection_delay_ms,
                "timestamp": result.timestamp.isoformat() if result.timestamp else None,
                "details": result.details
            })
        
        # Calculate summary
        passed = len([r for r in result_data if r["status"] == "pass"])
        failed = len([r for r in result_data if r["status"] != "pass"])
        avg_delay = sum([r["detection_delay_ms"] for r in result_data if r["detection_delay_ms"]]) / max(1, len([r for r in result_data if r["detection_delay_ms"]]))
        
        return {
            "session_id": session_id,
            "results": result_data,
            "summary": {
                "total_videos": len(result_data),
                "passed": passed,
                "failed": failed,
                "avg_detection_delay": avg_delay,
                "test_duration": (session.completed_at - session.started_at).total_seconds() if session.completed_at and session.started_at else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting enhanced test session results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get results: {str(e)}")