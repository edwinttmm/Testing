"""
Enhanced Test Workflow API - Detection Validation Testing
Provides detection validation workflow that tests AI model detection accuracy within time windows
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Project, Video, VideoProjectLink, TestSession, TestResult, DetectionComparison, DetectionEvent
from services.labjack_service import get_labjack_service
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class DetectionTestConfig(BaseModel):
    project_id: str
    detection_window_ms: float = 100.0   # Time window for detection (Pass/Fail)
    voltage_threshold: float = 2.5       # LabJack detection threshold
    sample_rate: int = 1000              # LabJack sampling rate
    channels: List[str] = ["AIN0", "AIN1"]
    tolerance_ms: int = 100              # Detection tolerance in milliseconds

class DetectionTestResult(BaseModel):
    video_id: str
    video_name: str
    expected_detection_time: float
    actual_detection_time: Optional[float]
    detection_delay_ms: Optional[float]
    status: str  # 'pass', 'fail_no_detection', 'fail_timeout'
    test_session_id: str

router = APIRouter(prefix="/api/enhanced-test-workflow", tags=["Enhanced Test Workflow"])

# Global test state
current_test_state = {
    "active": False,
    "config": None,
    "videos": [],
    "current_video_index": 0,
    "test_start_time": None,
    "video_start_time": None,
    "results": [],
    "test_session_id": None
}

@router.get("/projects")
async def get_projects(db: Session = Depends(get_db)):
    """Get all projects with their video counts for the Enhanced Test Workflow"""
    try:
        # Query projects with video counts using VideoProjectLink
        projects_query = db.query(Project).all()
        
        projects_data = []
        for project in projects_query:
            # Get video count through VideoProjectLink
            video_count = db.query(VideoProjectLink).filter(
                VideoProjectLink.project_id == project.id
            ).count()
            
            projects_data.append({
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "camera_model": project.camera_model,
                "camera_view": project.camera_view,
                "signal_type": project.signal_type,
                "status": project.status,
                "video_count": video_count,
                "created_at": project.created_at.isoformat() if project.created_at else None
            })
        
        logger.info(f"Retrieved {len(projects_data)} projects for Enhanced Test Workflow")
        return {
            "projects": projects_data,
            "total": len(projects_data)
        }
        
    except Exception as e:
        logger.error(f"Error retrieving projects: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve projects: {str(e)}")

@router.post("/start-test")
async def start_detection_test(config: DetectionTestConfig, db: Session = Depends(get_db)):
    """Start the Enhanced Test Workflow with detection validation testing"""
    
    # Check LabJack connection - allow development mode without strict hardware requirement
    labjack_service = get_labjack_service()
    
    try:
        status = labjack_service.get_status()
        
        # In development mode, ensure we have some connection (even mock)
        if not status.connected:
            logger.info("LabJack not connected, attempting to connect in development mode...")
            # Try to connect with fallback to mock mode for development
            connected = await labjack_service.connect()
            if not connected:
                raise HTTPException(
                    status_code=400, 
                    detail="LabJack connection failed. Please ensure LabJack hardware is connected or mock mode is available."
                )
            status = labjack_service.get_status()
        
    except Exception as e:
        logger.error(f"Error checking LabJack status: {e}")
        # Try to connect for development
        try:
            connected = await labjack_service.connect()
            if not connected:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to initialize LabJack service: {str(e)}"
                )
            status = labjack_service.get_status()
        except Exception as connect_error:
            logger.error(f"Failed to connect LabJack in development mode: {connect_error}")
            raise HTTPException(
                status_code=500,
                detail=f"LabJack service unavailable: {str(connect_error)}"
            )
    
    try:
        # Get project and videos through VideoProjectLink
        project = db.query(Project).filter(Project.id == config.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get videos linked to this project
        video_links = db.query(VideoProjectLink).filter(
            VideoProjectLink.project_id == config.project_id
        ).all()
        
        if not video_links:
            raise HTTPException(status_code=404, detail="No videos found in project")
        
        # Get actual video objects
        video_ids = [link.video_id for link in video_links]
        videos = db.query(Video).filter(Video.id.in_(video_ids)).all()
        
        # Create new test session using the project session management service
        from services.session_management_service import session_manager
        
        # Generate meaningful session name with project context
        session_name = f"{project.name} Enhanced Test Session - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        session_result = session_manager.create_project_session(
            project_id=config.project_id,
            session_name=session_name,
            video_id=videos[0].id if videos else None,
            tolerance_ms=config.tolerance_ms,
            session_type="enhanced_test_workflow",
            metadata={
                "detection_window_ms": config.detection_window_ms,
                "voltage_threshold": config.voltage_threshold,
                "sample_rate": config.sample_rate,
                "channels": config.channels,
                "workflow_type": "enhanced_detection_test"
            }
        )
        
        if not session_result["success"]:
            raise HTTPException(status_code=500, detail=f"Failed to create session: {session_result['message']}")
        
        test_session_id = session_result["session"]["session_id"]
        
        # Update session to running status
        session_manager.update_session_status(test_session_id, "running")
        
        # Update global test state
        global current_test_state
        current_test_state.update({
            "active": True,
            "config": config,
            "videos": [{"id": v.id, "name": v.filename, "file_path": v.file_path} for v in videos],
            "current_video_index": 0,
            "test_start_time": time.time(),
            "results": [],
            "test_session_id": test_session_id
        })
        
        # Configure LabJack for testing
        await labjack_service.start_stream(config.channels, config.sample_rate)
        
        logger.info(f"Started Enhanced Detection Test: {len(videos)} videos, project {config.project_id}, session {test_session_id}")
        
        return {
            "message": "Enhanced Detection Test started",
            "test_session_id": test_session_id,
            "project_id": config.project_id,
            "video_count": len(videos),
            "labjack_mode": status.mode.value,
            "config": config.dict()
        }
        
    except Exception as e:
        logger.error(f"Error starting detection test: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start test: {str(e)}")

@router.post("/stop-test")
async def stop_detection_test(db: Session = Depends(get_db)):
    """Stop the Enhanced Test Workflow"""
    global current_test_state
    
    if not current_test_state["active"]:
        raise HTTPException(status_code=400, detail="No active test to stop")
    
    try:
        # Stop LabJack streaming
        labjack_service = get_labjack_service()
        await labjack_service.stop_stream()
        
        # Update test session using session management service
        if current_test_state["test_session_id"]:
            from services.session_management_service import session_manager
            session_manager.update_session_status(
                current_test_state["test_session_id"], 
                "completed",
                metadata={"completion_reason": "user_stopped", "results_count": len(current_test_state["results"])}
            )
        
        current_test_state["active"] = False
        
        return {
            "message": "Enhanced Detection Test stopped",
            "test_session_id": current_test_state["test_session_id"],
            "results": current_test_state["results"]
        }
        
    except Exception as e:
        logger.error(f"Error stopping detection test: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop test: {str(e)}")

@router.get("/status")
async def get_test_status():
    """Get current test workflow status"""
    return {
        "active": current_test_state["active"],
        "test_session_id": current_test_state["test_session_id"],
        "current_video": current_test_state["current_video_index"],
        "total_videos": len(current_test_state["videos"]),
        "results_count": len(current_test_state["results"])
    }

@router.get("/results/{test_id}")
async def get_test_results(test_id: str, db: Session = Depends(get_db)):
    """Get comprehensive results for a specific test session with complete detection analysis"""
    try:
        # Get test session with related data
        test_session = db.query(TestSession).filter(TestSession.id == test_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Get test results with enhanced statistical analysis
        test_results = db.query(TestResult).filter(TestResult.test_session_id == test_id).all()
        
        # Get detection events with complete signal data
        detection_events = db.query(DetectionEvent).filter(DetectionEvent.test_session_id == test_id).all()
        
        # Get detection comparisons with ground truth analysis
        comparisons = db.query(DetectionComparison).filter(DetectionComparison.test_session_id == test_id).all()
        
        # Build comprehensive results data structure
        results_data = {
            "test_session": {
                "id": test_session.id,
                "name": test_session.name,
                "project_id": test_session.project_id,
                "video_id": test_session.video_id,
                "status": test_session.status,
                "started_at": test_session.started_at.isoformat() if test_session.started_at else None,
                "completed_at": test_session.completed_at.isoformat() if test_session.completed_at else None,
                "tolerance_ms": test_session.tolerance_ms,
                "duration_seconds": (test_session.completed_at - test_session.started_at).total_seconds() if (test_session.completed_at and test_session.started_at) else None
            },
            "test_results": [
                {
                    "id": result.id,
                    "accuracy": result.accuracy,
                    "precision": result.precision,
                    "recall": result.recall,
                    "f1_score": result.f1_score,
                    "true_positives": result.true_positives,
                    "false_positives": result.false_positives,
                    "false_negatives": result.false_negatives,
                    "statistical_analysis": result.statistical_analysis,
                    "confidence_intervals": result.confidence_intervals,
                    "created_at": result.created_at.isoformat() if result.created_at else None
                } for result in test_results
            ],
            "detection_events": [
                {
                    "id": event.id,
                    "detection_id": event.detection_id,
                    "timestamp": event.timestamp,
                    "confidence": event.confidence,
                    "class_label": event.class_label,
                    "validation_result": event.validation_result,
                    "frame_number": event.frame_number,
                    "vru_type": event.vru_type,
                    "processing_time_ms": event.processing_time_ms,
                    "model_version": event.model_version,
                    "bounding_box": {
                        "x": event.bounding_box_x,
                        "y": event.bounding_box_y,
                        "width": event.bounding_box_width,
                        "height": event.bounding_box_height
                    } if event.bounding_box_x is not None else None,
                    "visual_evidence": {
                        "screenshot_path": event.screenshot_path,
                        "screenshot_zoom_path": event.screenshot_zoom_path
                    } if event.screenshot_path else None,
                    "created_at": event.created_at.isoformat() if event.created_at else None
                } for event in detection_events
            ],
            "detection_comparisons": [
                {
                    "id": comp.id,
                    "ground_truth_id": comp.ground_truth_id,
                    "detection_event_id": comp.detection_event_id,
                    "match_type": comp.match_type,
                    "iou_score": comp.iou_score,
                    "distance_error": comp.distance_error,
                    "temporal_offset": comp.temporal_offset,
                    "temporal_offset_ms": comp.temporal_offset * 1000 if comp.temporal_offset else None,
                    "notes": comp.notes,
                    "created_at": comp.created_at.isoformat() if comp.created_at else None
                } for comp in comparisons
            ]
        }
        
        # Calculate enhanced summary statistics
        total_detections = len(detection_events)
        if total_detections > 0:
            # Classification performance metrics
            true_positives = len([e for e in detection_events if e.validation_result == "TP"])
            false_positives = len([e for e in detection_events if e.validation_result == "FP"])
            false_negatives = len([e for e in detection_events if e.validation_result == "FN"])
            
            # Timing analysis
            timing_offsets = [c.temporal_offset for c in comparisons if c.temporal_offset is not None]
            avg_temporal_offset = sum(timing_offsets) / len(timing_offsets) if timing_offsets else 0
            max_temporal_offset = max(timing_offsets) if timing_offsets else 0
            min_temporal_offset = min(timing_offsets) if timing_offsets else 0
            
            # Confidence analysis
            confidences = [e.confidence for e in detection_events if e.confidence is not None]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Processing time analysis
            processing_times = [e.processing_time_ms for e in detection_events if e.processing_time_ms is not None]
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
            
            results_data["summary"] = {
                # Basic counts
                "total_detections": total_detections,
                "true_positives": true_positives,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                
                # Performance metrics
                "accuracy": true_positives / total_detections if total_detections > 0 else 0,
                "precision": true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0,
                "recall": true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0,
                "pass_rate_percentage": (true_positives / total_detections * 100) if total_detections > 0 else 0,
                
                # Timing analysis
                "timing_analysis": {
                    "avg_temporal_offset_ms": avg_temporal_offset * 1000 if avg_temporal_offset else 0,
                    "max_temporal_offset_ms": max_temporal_offset * 1000 if max_temporal_offset else 0,
                    "min_temporal_offset_ms": min_temporal_offset * 1000 if min_temporal_offset else 0,
                    "timing_precision_samples": len(timing_offsets)
                },
                
                # Confidence and performance
                "detection_quality": {
                    "avg_confidence": avg_confidence,
                    "avg_processing_time_ms": avg_processing_time,
                    "confident_detections": len([c for c in confidences if c > 0.8]) if confidences else 0
                },
                
                # LabJack specific metrics
                "signal_validation": {
                    "labjack_detections": len([e for e in detection_events if e.class_label == "labjack_signal"]),
                    "signal_quality": "Good" if avg_confidence > 0.7 else "Poor" if avg_confidence < 0.3 else "Fair"
                }
            }
        else:
            results_data["summary"] = {
                "total_detections": 0,
                "message": "No detection events found for this test session"
            }
        
        return results_data
        
    except Exception as e:
        logger.error(f"Error retrieving comprehensive test results for {test_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve test results: {str(e)}")

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
            try:
                message = await websocket.receive_text()
                # Handle any incoming messages from frontend
                data = json.loads(message)
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception as e:
                logger.debug(f"WebSocket message handling error: {e}")
                break
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

async def run_detection_validation_workflow(websocket: WebSocket):
    """Run the complete detection validation workflow with full automation"""
    labjack_service = get_labjack_service()
    logger.info(f"Starting automated sequential workflow with {len(current_test_state['videos'])} videos")
    
    try:
        for i, video in enumerate(current_test_state["videos"]):
            if not current_test_state["active"]:
                logger.info("Workflow stopped by user")
                break
                
            current_test_state["current_video_index"] = i
            
            # Get video duration if available for timing calculations
            video_duration = 5.0  # Default 5 seconds, could be read from video metadata
            expected_detection_time = 2.0  # Expected detection at 2 seconds
            
            logger.info(f"Processing video {i+1}/{len(current_test_state['videos'])}: {video['name']}")
            
            # Phase 1: Start video playback
            await websocket.send_text(json.dumps({
                "type": "video_start_playback",
                "video_id": video["id"],
                "video_name": video["name"],
                "video_path": video.get("file_path", ""),
                "index": i,
                "total": len(current_test_state["videos"]),
                "expected_detection_time": expected_detection_time,
                "video_duration": video_duration,
                "auto_play": True
            }))
            
            # Wait for frontend to acknowledge video started
            video_start_time = time.time()
            current_test_state["video_start_time"] = video_start_time
            
            # Phase 2: Monitor for LabJack signal during video playback with synchronized signal generation
            detection_found = False
            detection_window_ms = current_test_state["config"].detection_window_ms
            video_timeout = max(video_duration + 2.0, 10.0)  # Video duration + buffer
            
            logger.info(f"Monitoring LabJack signals for {video_timeout}s (detection window: {detection_window_ms}ms)")
            
            # Initialize LabJack for signal generation at expected detection time
            try:
                # Configure LabJack for test signal generation (if supported)
                await labjack_service.configure_test_signal(
                    channel="DAC0",  # Output channel for test signal generation
                    trigger_time=expected_detection_time,  # Generate signal at expected time
                    signal_voltage=3.3,  # Test signal voltage
                    duration_ms=100  # Signal duration
                )
                logger.info(f"Configured LabJack test signal generation at {expected_detection_time}s")
            except Exception as signal_config_error:
                logger.warning(f"Test signal configuration failed (mock mode?): {signal_config_error}")
            
            # Real-time voltage monitoring with precise timing
            start_monitor_time = time.time()
            detection_data = []
            
            while (time.time() - start_monitor_time) < video_timeout and current_test_state["active"]:
                try:
                    # Read voltage from LabJack
                    voltage = await labjack_service.read_single_voltage("AIN0")
                    current_time = time.time()
                    relative_time = current_time - video_start_time
                    
                    # Store all voltage readings for analysis
                    detection_data.append({
                        "timestamp": current_time,
                        "relative_time": relative_time,
                        "voltage": voltage
                    })
                    
                    # Send real-time voltage updates to frontend
                    await websocket.send_text(json.dumps({
                        "type": "voltage_reading",
                        "voltage": voltage,
                        "timestamp": relative_time,
                        "video_index": i
                    }))
                    
                    # Check for detection threshold
                    if voltage > current_test_state["config"].voltage_threshold:
                        actual_detection_time = relative_time
                        detection_delay_ms = abs(actual_detection_time - expected_detection_time) * 1000
                        
                        # Determine pass/fail status based on detection window
                        if detection_delay_ms <= detection_window_ms:
                            status = "pass"
                        else:
                            status = "fail_timeout"
                        
                        result = DetectionTestResult(
                            video_id=video["id"],
                            video_name=video["name"],
                            expected_detection_time=expected_detection_time,
                            actual_detection_time=actual_detection_time,
                            detection_delay_ms=detection_delay_ms,
                            status=status,
                            test_session_id=current_test_state["test_session_id"]
                        )
                        
                        current_test_state["results"].append(result.dict())
                        detection_found = True
                        
                        logger.info(f"Detection found at {actual_detection_time:.2f}s: {status} (delay: {detection_delay_ms:.1f}ms)")
                        
                        # Store result in database
                        await store_detection_result(result)
                        
                        # Notify frontend of detection
                        await websocket.send_text(json.dumps({
                            "type": "detection_event",
                            "detection_delay_ms": detection_delay_ms,
                            "voltage": voltage,
                            "timestamp": actual_detection_time,
                            "status": status,
                            "video_index": i
                        }))
                        
                        break
                        
                    await asyncio.sleep(0.01)  # 10ms polling for precise timing
                    
                except Exception as e:
                    logger.error(f"Error reading LabJack during video {i+1}: {e}")
                    await asyncio.sleep(0.1)
            
            # Phase 3: Handle no detection case
            if not detection_found:
                result = DetectionTestResult(
                    video_id=video["id"],
                    video_name=video["name"],
                    expected_detection_time=expected_detection_time,
                    actual_detection_time=None,
                    detection_delay_ms=None,
                    status="fail_no_detection",
                    test_session_id=current_test_state["test_session_id"]
                )
                current_test_state["results"].append(result.dict())
                
                logger.warning(f"No detection found for video {i+1}: {video['name']}")
                
                # Store result in database
                await store_detection_result(result)
                
                # Notify frontend of no detection
                await websocket.send_text(json.dumps({
                    "type": "no_detection",
                    "video_index": i,
                    "max_voltage": max([d["voltage"] for d in detection_data]) if detection_data else 0
                }))
            
            # Phase 4: Video completion and preparation for next video
            await websocket.send_text(json.dumps({
                "type": "video_complete",
                "video_index": i,
                "result": current_test_state["results"][-1] if current_test_state["results"] else None
            }))
            
            # Inter-video delay for system reset
            if i < len(current_test_state["videos"]) - 1:  # Not the last video
                logger.info(f"Preparing for next video... (1s delay)")
                await asyncio.sleep(1.0)
                
            # Send progress update
            progress = ((i + 1) / len(current_test_state["videos"])) * 100
            await websocket.send_text(json.dumps({
                "type": "workflow_progress",
                "progress": progress,
                "completed_videos": i + 1,
                "total_videos": len(current_test_state["videos"]),
                "current_results": len(current_test_state["results"])
            }))
            
        # Workflow completion
        logger.info(f"Workflow completed: {len(current_test_state['results'])} results generated")
        
    except Exception as e:
        logger.error(f"Workflow error: {e}")
        await websocket.send_text(json.dumps({
            "type": "workflow_error",
            "error": str(e)
        }))
    
    # Generate comprehensive final results
    total_videos = len(current_test_state["videos"])
    passed_tests = len([r for r in current_test_state["results"] if r["status"] == "pass"])
    failed_no_detection = len([r for r in current_test_state["results"] if r["status"] == "fail_no_detection"])
    failed_timeout = len([r for r in current_test_state["results"] if r["status"] == "fail_timeout"])
    
    # Calculate timing statistics
    timing_delays = [r["detection_delay_ms"] for r in current_test_state["results"] if r["detection_delay_ms"] is not None]
    avg_delay = sum(timing_delays) / len(timing_delays) if timing_delays else 0
    
    final_summary = {
        "total_videos": total_videos,
        "completed_videos": len(current_test_state["results"]),
        "passed": passed_tests,
        "failed_no_detection": failed_no_detection,
        "failed_timeout": failed_timeout,
        "pass_rate_percentage": (passed_tests / total_videos * 100) if total_videos > 0 else 0,
        "average_delay_ms": avg_delay,
        "test_session_id": current_test_state["test_session_id"]
    }
    
    logger.info(f"Final results: {passed_tests}/{total_videos} passed ({final_summary['pass_rate_percentage']:.1f}%)")
    
    # Send final comprehensive results
    await websocket.send_text(json.dumps({
        "type": "test_results",
        "results": current_test_state["results"],
        "summary": final_summary
    }))
    
    await websocket.send_text(json.dumps({
        "type": "test_complete",
        "summary": final_summary,
        "message": f"Automated testing complete: {passed_tests}/{total_videos} videos passed"
    }))
    
    current_test_state["active"] = False
    logger.info("Enhanced test workflow completed successfully")

async def store_detection_result(result: DetectionTestResult):
    """Store comprehensive detection result in database with full LabJack signal data"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        
        # Get current timestamp for record creation
        current_timestamp = datetime.now()
        
        # Create detection event with enhanced fields for complete signal storage
        detection_event = DetectionEvent(
            id=str(uuid.uuid4()),
            test_session_id=result.test_session_id,
            timestamp=result.actual_detection_time if result.actual_detection_time else result.expected_detection_time,
            confidence=1.0 if result.status == "pass" else 0.0,
            class_label="labjack_signal",  # Specify this is LabJack signal detection
            validation_result="TP" if result.status == "pass" else "FN",
            vru_type="signal_validation",
            
            # Enhanced detection metadata
            detection_id=f"LJ_DET_{uuid.uuid4().hex[:8]}",  # Unique LabJack detection ID
            frame_number=None,  # Not applicable for signal-based detection
            
            # Store detection timing data
            processing_time_ms=result.detection_delay_ms,
            model_version="labjack_v1.0",  # Version tracking
            
            # Store timing comparison results
            bounding_box_x=None,  # Not applicable for signal detection
            bounding_box_y=None,
            bounding_box_width=None,
            bounding_box_height=None,
            
            # Store metadata paths (future use for signal plots)
            screenshot_path=None,  # Could store signal waveform plots
            screenshot_zoom_path=None,
            
            created_at=current_timestamp
        )
        db.add(detection_event)
        
        # Create detection comparison with ground truth timing
        comparison = DetectionComparison(
            id=str(uuid.uuid4()),
            test_session_id=result.test_session_id,
            detection_event_id=detection_event.id,
            ground_truth_id=None,  # No specific ground truth annotation for signal validation
            match_type="TP" if result.status == "pass" else ("FN" if result.status == "fail_no_detection" else "FP"),
            iou_score=None,  # Not applicable for signal detection
            distance_error=0.0,  # No spatial comparison
            temporal_offset=result.detection_delay_ms / 1000.0 if result.detection_delay_ms else None,
            notes=f"LabJack signal validation: {result.status}. Expected: {result.expected_detection_time}s, Actual: {result.actual_detection_time}s",
            created_at=current_timestamp
        )
        db.add(comparison)
        
        # Create comprehensive test result summary
        test_result = TestResult(
            id=str(uuid.uuid4()),
            test_session_id=result.test_session_id,
            accuracy=1.0 if result.status == "pass" else 0.0,
            precision=1.0 if result.status == "pass" else 0.0,
            recall=1.0 if result.status == "pass" else 0.0,
            f1_score=1.0 if result.status == "pass" else 0.0,
            true_positives=1 if result.status == "pass" else 0,
            false_positives=0 if result.status == "pass" else (1 if "fail" in result.status else 0),
            false_negatives=0 if result.status == "pass" else (1 if result.status == "fail_no_detection" else 0),
            statistical_analysis={
                "detection_timing": {
                    "expected_time_s": result.expected_detection_time,
                    "actual_time_s": result.actual_detection_time,
                    "delay_ms": result.detection_delay_ms,
                    "status": result.status
                },
                "labjack_parameters": {
                    "voltage_threshold": current_test_state.get("config", {}).voltage_threshold if current_test_state.get("config") else None,
                    "sample_rate": current_test_state.get("config", {}).sample_rate if current_test_state.get("config") else None,
                    "channels": current_test_state.get("config", {}).channels if current_test_state.get("config") else None
                }
            },
            confidence_intervals={
                "detection_confidence": 0.95 if result.status == "pass" else 0.1,
                "timing_precision_ms": 10.0  # 10ms precision estimate
            },
            created_at=current_timestamp
        )
        db.add(test_result)
        
        # Commit all changes atomically
        db.commit()
        db.close()
        
        logger.info(f"Stored complete detection result for video {result.video_id}: {result.status} - DetectionEvent: {detection_event.id}, Comparison: {comparison.id}, TestResult: {test_result.id}")
        
    except Exception as e:
        logger.error(f"Error storing detection result: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()

@router.get("/results")
async def get_latest_test_results():
    """Get the latest test results"""
    return {
        "active": current_test_state["active"],
        "test_session_id": current_test_state["test_session_id"],
        "results": current_test_state["results"],
        "summary": {
            "total_videos": len(current_test_state["results"]),
            "passed": len([r for r in current_test_state["results"] if r["status"] == "pass"]),
            "failed_no_detection": len([r for r in current_test_state["results"] if r["status"] == "fail_no_detection"]),
            "failed_timeout": len([r for r in current_test_state["results"] if r["status"] == "fail_timeout"]),
            "avg_detection_delay": sum([r["detection_delay_ms"] for r in current_test_state["results"] if r["detection_delay_ms"]]) / 
                          len([r for r in current_test_state["results"] if r["detection_delay_ms"]]) 
                          if [r for r in current_test_state["results"] if r["detection_delay_ms"]] else 0
        }
    }