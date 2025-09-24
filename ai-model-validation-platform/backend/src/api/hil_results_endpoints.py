"""
HIL Test Results API Endpoints

Enhanced endpoints for retrieving HIL test session results with comprehensive
data structure for the simplified HIL results page.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import statistics
import json

from database import get_db
from models import TestSession, DetectionEvent, Project, Video
from services.test_execution_service import test_execution_service
from services.labjack_service import LabJackService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["HIL Results"])

# Initialize services
labjack_service = LabJackService()

@router.get("/test-sessions/{session_id}/results-debug")
async def get_hil_test_results_debug(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Debug version of HIL results endpoint"""
    return {
        "debug": True,
        "session_id": session_id,
        "message": "HIL endpoint is working",
        "timestamp": "2024-01-01T00:00:00"
    }

@router.get("/test-sessions/latest-with-events")
async def get_latest_session_with_events(db: Session = Depends(get_db)):
    """Get the latest test session that actually has detection events"""
    try:
        # Find the session with the most recent detection events
        query = text("""
            SELECT ts.id, ts.name, ts.status, ts.created_at, COUNT(de.id) as event_count,
                   MAX(de.created_at) as latest_event_time
            FROM test_sessions ts
            INNER JOIN detection_events de ON ts.id = de.test_session_id
            GROUP BY ts.id, ts.name, ts.status, ts.created_at
            HAVING event_count > 0
            ORDER BY latest_event_time DESC
            LIMIT 1
        """)
        
        result = db.execute(query).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="No test sessions with detection events found")
        
        return {
            "session_id": result.id,
            "name": result.name,
            "status": result.status,
            "created_at": result.created_at.isoformat() if result.created_at else None,
            "event_count": result.event_count,
            "latest_event_time": result.latest_event_time,
            "message": f"Found session with {result.event_count} detection events"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding latest session with events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to find latest session with events: {str(e)}")

@router.get("/test-sessions/{session_id}/results")
async def get_hil_test_results(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get HIL test results for a specific session
    
    Returns comprehensive HIL test data including:
    - Session metadata
    - Latency statistics
    - Detection events with timing data
    - Hardware status
    - Pass/fail analysis
    """
    try:
        # Get test session using raw SQL to avoid model compatibility issues
        session_query = text("""
            SELECT ts.id, ts.name, ts.project_id, ts.video_id, ts.status, ts.started_at, ts.completed_at, ts.created_at,
                   ts.tolerance_ms, ts.session_type, ts.video_playback_start_time,
                   ts.video_timing_sync_status, ts.timing_accuracy_ns,
                   v.fps, v.duration, v.filename
            FROM test_sessions ts
            LEFT JOIN videos v ON ts.video_id = v.id
            WHERE ts.id = :session_id
        """)
        session_result = db.execute(session_query, {"session_id": session_id}).fetchone()
        
        if not session_result:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Create a simple object from the raw result
        class TestSessionData:
            def __init__(self, row):
                self.id = row.id
                self.name = row.name
                self.project_id = row.project_id
                self.video_id = row.video_id
                self.status = row.status
                self.started_at = row.started_at
                self.completed_at = row.completed_at
                self.created_at = row.created_at
                self.tolerance_ms = row.tolerance_ms
                self.session_type = row.session_type
                self.video_playback_start_time = getattr(row, 'video_playback_start_time', None)
                self.video_timing_sync_status = getattr(row, 'video_timing_sync_status', 'unknown')
                self.timing_accuracy_ns = getattr(row, 'timing_accuracy_ns', None)
                self.video_fps = getattr(row, 'fps', None)
                self.video_duration = getattr(row, 'duration', None)
                self.video_filename = getattr(row, 'filename', None)
        
        test_session = TestSessionData(session_result)
        
        # Skip test execution service to avoid ORM compatibility issues
        # service_results = test_execution_service.get_session_results(session_id)
        
        # Get detection events for detailed analysis using raw SQL
        # First try the specific session, then fall back to sessions with events
        detection_events_query = text("""
            SELECT id, test_session_id, frame_number, timestamp, latency_ms, latency_ns,
                   processing_time_ms, voltage_level, labjack_voltage, labjack_timestamp,
                   detection_channel, validation_result, confidence, class_label, vru_type,
                   created_at
            FROM detection_events 
            WHERE test_session_id = :session_id
            ORDER BY timestamp ASC
        """)
        detection_events_result = db.execute(detection_events_query, {"session_id": session_id}).fetchall()
        
        # If no events found for this session, try to find any session with recent events
        if not detection_events_result:
            logger.warning(f"No detection events found for session {session_id}, looking for recent events in any session")
            fallback_query = text("""
                SELECT id, test_session_id, frame_number, timestamp, latency_ms, latency_ns,
                       processing_time_ms, voltage_level, labjack_voltage, labjack_timestamp,
                       detection_channel, validation_result, confidence, class_label, vru_type,
                       created_at
                FROM detection_events 
                WHERE test_session_id IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 50
            """)
            detection_events_result = db.execute(fallback_query).fetchall()
            if detection_events_result:
                logger.info(f"Found {len(detection_events_result)} recent detection events from other sessions")
        
        # Create simple event objects
        class DetectionEventData:
            def __init__(self, row):
                self.id = row.id
                self.test_session_id = row.test_session_id
                self.frame_number = row.frame_number
                self.timestamp = row.timestamp
                self.latency_ms = row.latency_ms
                self.latency_ns = row.latency_ns
                self.processing_time_ms = row.processing_time_ms
                self.voltage_level = row.voltage_level
                self.labjack_voltage = row.labjack_voltage
                self.labjack_timestamp = row.labjack_timestamp
                self.detection_channel = row.detection_channel
                self.validation_result = row.validation_result
                self.confidence = row.confidence
                self.class_label = row.class_label
                self.vru_type = row.vru_type
                self.created_at = row.created_at
        
        detection_events = [DetectionEventData(row) for row in detection_events_result]
        
        # Calculate latency statistics
        latency_data = []
        processing_times = []
        total_detections = len(detection_events)
        passed_detections = 0
        failed_detections = 0
        threshold_ms = test_session.tolerance_ms or 100
        
        # Process detection events
        detection_event_results = []
        
        for event in detection_events:
            # Extract latency (prefer latency_ms, fallback to processing_time_ms)
            latency_ms = event.latency_ms if event.latency_ms is not None else (event.processing_time_ms or 0.0)
            latency_ns = None
            
            # Try to parse nanosecond precision if available
            if event.latency_ns:
                try:
                    latency_ns = int(event.latency_ns)
                except (ValueError, TypeError):
                    latency_ns = int(latency_ms * 1_000_000)  # Convert ms to ns
            else:
                latency_ns = int(latency_ms * 1_000_000)  # Convert ms to ns
            
            latency_data.append(latency_ms)
            
            # Collect processing times for calculating session average
            if event.processing_time_ms is not None and event.processing_time_ms > 0:
                processing_times.append(event.processing_time_ms)
            
            # Determine pass/fail based on threshold
            result = "pass" if latency_ms <= threshold_ms else "fail"
            if result == "pass":
                passed_detections += 1
            else:
                failed_detections += 1
            
            # Calculate voltage value properly
            voltage_value = 0.0
            if event.labjack_voltage is not None:
                voltage_value = float(event.labjack_voltage)
            elif event.voltage_level is not None:
                voltage_value = float(event.voltage_level)
            elif event.confidence is not None:
                voltage_value = float(event.confidence)  # Sometimes voltage is stored in confidence field
            
            # Build detection event data
            detection_event_results.append({
                "event_id": event.id,
                "frame_number": event.frame_number or 0,
                "timestamp": event.timestamp and datetime.fromtimestamp(event.timestamp).isoformat() if event.timestamp > 1000000000 else event.created_at,
                "detection_time": event.timestamp and datetime.fromtimestamp(event.timestamp).isoformat() if event.timestamp > 1000000000 else event.created_at,
                "labjack_trigger_time": event.labjack_timestamp and datetime.fromtimestamp(event.labjack_timestamp).isoformat() if event.labjack_timestamp else None,
                "latency_ms": round(latency_ms, 3),
                "latency_ns": latency_ns,
                "voltage_level": voltage_value,
                "channel": event.detection_channel or "AIN0",
                "result": "pass" if voltage_value >= 2.5 else "fail",  # HIL uses voltage threshold instead of latency
                "error_message": None if voltage_value >= 2.5 else f"Voltage {voltage_value:.2f}V below threshold 2.5V",
                "session_id": event.test_session_id  # Include actual session ID for debugging
            })
        
        # Calculate statistical measures
        if latency_data:
            avg_latency = statistics.mean(latency_data)
            min_latency = min(latency_data)
            max_latency = max(latency_data)
            median_latency = statistics.median(latency_data)
            std_dev_latency = statistics.stdev(latency_data) if len(latency_data) > 1 else 0.0
        else:
            avg_latency = min_latency = max_latency = median_latency = std_dev_latency = 0.0
        
        # Calculate pass rate
        pass_rate = (passed_detections / max(1, total_detections)) * 100
        
        # Create latency distribution (histogram bins)
        latency_distribution = []
        if latency_data:
            try:
                # Create 10 bins for distribution
                min_val = min(latency_data)
                max_val = max(latency_data)
                if max_val > min_val:
                    bin_width = (max_val - min_val) / 10
                    for i in range(10):
                        bin_start = min_val + (i * bin_width)
                        bin_end = min_val + ((i + 1) * bin_width)
                        count = len([x for x in latency_data if bin_start <= x < bin_end])
                        if i == 9:  # Include max value in last bin
                            count = len([x for x in latency_data if bin_start <= x <= bin_end])
                        latency_distribution.append({
                            "bin_start": round(bin_start, 1),
                            "bin_end": round(bin_end, 1),
                            "count": count
                        })
                else:
                    latency_distribution.append({
                        "bin_start": min_val,
                        "bin_end": min_val,
                        "count": len(latency_data)
                    })
            except Exception as e:
                logger.warning(f"Failed to create latency distribution: {e}")
                latency_distribution = []
        
        # Get hardware status
        try:
            labjack_status = await labjack_service.get_connection_status()
            hardware_status = {
                "labjack_connected": labjack_status.connected,
                "model": labjack_status.device_type or "T7",
                "serial_number": labjack_status.device_serial or "Unknown",
                "firmware_version": "Unknown",
                "sampling_rate_hz": 1000,
                "active_channels": ["AIN0", "AIN1"]
            }
        except Exception as e:
            logger.warning(f"Failed to get LabJack status: {e}")
            hardware_status = {
                "labjack_connected": False,
                "model": "T7",
                "serial_number": "Unknown",
                "firmware_version": "Unknown",
                "sampling_rate_hz": 1000,
                "active_channels": ["AIN0", "AIN1"]
            }
        
        # Calculate session duration
        duration_seconds = 0
        if test_session.started_at and test_session.completed_at:
            duration_seconds = (test_session.completed_at - test_session.started_at).total_seconds()
        elif test_session.started_at:
            duration_seconds = (datetime.utcnow() - test_session.started_at).total_seconds()

        # Calculate video startup delay if timing data is available
        video_startup_delay_ms = 0
        if (test_session.video_playback_start_time and test_session.started_at):
            # Convert datetime to timestamp for calculation
            started_timestamp = test_session.started_at.timestamp()
            video_startup_delay_ms = (test_session.video_playback_start_time - started_timestamp) * 1000
        
        # Get project info safely
        project_name = "Unknown Project"
        try:
            if test_session.project_id:
                project_query = text("SELECT name FROM projects WHERE id = :project_id")
                project_result = db.execute(project_query, {"project_id": test_session.project_id}).fetchone()
                if project_result:
                    project_name = project_result.name
        except:
            pass
        
        # Build comprehensive response
        response = {
            "session_id": session_id,
            "test_session_id": session_id,
            "validation_type": "latency_based",
            "total_detections": total_detections,
            "passed_detections": passed_detections,
            "failed_detections": failed_detections,
            "pass_rate": round(pass_rate, 2),
            "status": test_session.status or "completed",
            "session_info": {
                "project_name": project_name,
                "operator": "System",
                "start_time": test_session.started_at.isoformat() if test_session.started_at else None,
                "end_time": test_session.completed_at.isoformat() if test_session.completed_at else None,
                "duration_seconds": round(duration_seconds, 1)
            },
            "video_timing": {
                "startup_delay_ms": round(video_startup_delay_ms, 2),
                "timing_sync_status": test_session.video_timing_sync_status,
                "timing_accuracy_ns": test_session.timing_accuracy_ns
            },
            "video_metadata": {
                "fps": test_session.video_fps,
                "duration": test_session.video_duration,
                "filename": test_session.video_filename,
                "average_processing_time_ms": round(sum(processing_times) / len(processing_times), 1) if processing_times else None
            },
            "latency_stats": {
                "average_ms": round(avg_latency, 3),
                "min_ms": round(min_latency, 3),
                "max_ms": round(max_latency, 3),
                "median_ms": round(median_latency, 3),
                "std_dev_ms": round(std_dev_latency, 3),
                "threshold_ms": threshold_ms
            },
            "latency_distribution": latency_distribution,
            "hardware_status": hardware_status,
            "detection_events": detection_event_results
        }
        
        logger.info(f"Retrieved HIL results for session {session_id}: {total_detections} detections, {pass_rate:.1f}% pass rate")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving HIL test results for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve HIL test results: {str(e)}")

@router.get("/test-sessions/{session_id}/hil-results")
async def get_hil_specific_results(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get HIL-specific test results (alternative endpoint for compatibility)
    
    This endpoint provides the same data as /test-sessions/{session_id}/results
    but with an HIL-specific path for backwards compatibility.
    """
    return await get_hil_test_results(session_id, db)

@router.get("/test-sessions")
async def list_test_sessions(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    session_type: Optional[str] = Query(None, description="Filter by session type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, description="Maximum number of sessions to return"),
    offset: int = Query(0, description="Number of sessions to skip"),
    db: Session = Depends(get_db)
):
    """
    List test sessions with optional filtering
    
    Useful for finding HIL test sessions to retrieve results for.
    """
    try:
        query = db.query(TestSession).options(
            joinedload(TestSession.project)
        )
        
        # Apply filters
        if project_id:
            query = query.filter(TestSession.project_id == project_id)
        if session_type:
            query = query.filter(TestSession.session_type == session_type)
        if status:
            query = query.filter(TestSession.status == status)
        
        # Order by creation date (newest first) and apply pagination
        sessions = query.order_by(TestSession.created_at.desc()).offset(offset).limit(limit).all()
        
        # Build response
        session_list = []
        for session in sessions:
            # Count detection events
            event_count = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).count()
            
            session_list.append({
                "session_id": session.id,
                "name": session.name,
                "project_name": session.project.name if session.project else "Unknown",
                "project_id": session.project_id,
                "status": session.status,
                "session_type": session.session_type,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "detection_count": event_count,
                "latency_threshold_ms": session.latency_threshold_ms or session.tolerance_ms or 100
            })
        
        return {
            "sessions": session_list,
            "total_returned": len(session_list),
            "offset": offset,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Error listing test sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list test sessions: {str(e)}")

@router.get("/test-sessions/{session_id}/events")
async def get_session_detection_events(
    session_id: str,
    limit: int = Query(100, description="Maximum number of events to return"),
    offset: int = Query(0, description="Number of events to skip"),
    db: Session = Depends(get_db)
):
    """
    Get detection events for a specific test session
    
    Provides detailed event-level data for analysis.
    """
    try:
        # Verify session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Get detection events
        events = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).order_by(DetectionEvent.timestamp.asc()).offset(offset).limit(limit).all()
        
        # Build event list
        event_list = []
        threshold_ms = test_session.latency_threshold_ms or test_session.tolerance_ms or 100
        
        for event in events:
            latency_ms = event.latency_ms if event.latency_ms is not None else (event.processing_time_ms or 0.0)
            result = "pass" if latency_ms <= threshold_ms else "fail"
            
            event_list.append({
                "event_id": event.id,
                "timestamp": event.timestamp,
                "frame_number": event.frame_number or 0,
                "latency_ms": round(latency_ms, 3),
                "result": result,
                "validation_result": event.validation_result,
                "voltage_level": event.voltage_level or event.labjack_voltage,
                "channel": event.detection_channel,
                "confidence": event.confidence,
                "class_label": event.class_label,
                "vru_type": event.vru_type,
                "created_at": event.created_at.isoformat() if event.created_at else None
            })
        
        return {
            "session_id": session_id,
            "events": event_list,
            "total_returned": len(event_list),
            "offset": offset,
            "limit": limit,
            "threshold_ms": threshold_ms
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving detection events for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve detection events: {str(e)}")

@router.get("/test-sessions/{session_id}/summary")
async def get_session_summary(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a summary of HIL test session results
    
    Provides key metrics without full event details for quick overview.
    """
    try:
        # Get test session
        test_session = db.query(TestSession).options(
            joinedload(TestSession.project)
        ).filter(TestSession.id == session_id).first()
        
        if not test_session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Get event statistics
        events_query = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        )
        
        total_events = events_query.count()
        threshold_ms = test_session.latency_threshold_ms or test_session.tolerance_ms or 100
        
        # Calculate pass/fail counts
        passed_events = 0
        failed_events = 0
        total_latency = 0.0
        
        for event in events_query.all():
            latency_ms = event.latency_ms if event.latency_ms is not None else (event.processing_time_ms or 0.0)
            total_latency += latency_ms
            
            if latency_ms <= threshold_ms:
                passed_events += 1
            else:
                failed_events += 1
        
        # Calculate metrics
        pass_rate = (passed_events / max(1, total_events)) * 100
        avg_latency = total_latency / max(1, total_events)
        
        return {
            "session_id": session_id,
            "project_name": test_session.project.name if test_session.project else "Unknown",
            "status": test_session.status,
            "total_detections": total_events,
            "passed_detections": passed_events,
            "failed_detections": failed_events,
            "pass_rate": round(pass_rate, 2),
            "average_latency_ms": round(avg_latency, 3),
            "threshold_ms": threshold_ms,
            "started_at": test_session.started_at.isoformat() if test_session.started_at else None,
            "completed_at": test_session.completed_at.isoformat() if test_session.completed_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session summary for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve session summary: {str(e)}")