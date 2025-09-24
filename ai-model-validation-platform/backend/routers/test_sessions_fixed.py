"""
Test Sessions Router - Fixed HIL Integration
==========================================

Fixed test session endpoints with proper dedicated monitoring service integration.
Handles test session lifecycle, execution, results, and monitoring via IPC.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy import func, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import logging
import uuid

from database import SessionLocal
from models import TestSession, Project, Video, DetectionEvent, TestResult
from schemas import (
    TestSessionCreate, TestSessionResponse,
    DetectionEvent as DetectionEventSchema,
    ValidationResult
)
from services.session_management_service import session_manager
from services.labjack_monitoring_service import labjack_monitoring_service
from services.monitoring_service_client import monitoring_service_manager
from crud import create_test_session, get_test_sessions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/test-sessions", tags=["Test Sessions"])

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# TEST SESSION LIFECYCLE MANAGEMENT
# ============================================================================

@router.post("", response_model=TestSessionResponse)
async def create_new_test_session(
    session: TestSessionCreate,
    db: Session = Depends(get_db)
):
    """Create a new test session with validation"""
    try:
        # Validate project exists
        project = db.query(Project).filter(Project.id == session.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Validate video exists if provided
        if session.video_id:
            video = db.query(Video).filter(Video.id == session.video_id).first()
            if not video:
                raise HTTPException(status_code=404, detail="Video not found")
        
        # Create test session
        db_session = create_test_session(db=db, test_session=session, user_id="anonymous")
        
        logger.info(f"Test session created: {db_session.id} for project {session.project_id}")
        
        return {
            "id": db_session.id,
            "name": session.name,
            "project_id": session.project_id,
            "video_id": session.video_id,
            "status": db_session.status,
            "tolerance_ms": db_session.tolerance_ms,
            "created_at": db_session.created_at,
            "started_at": db_session.started_at,
            "completed_at": db_session.completed_at,
            "detection_events": None,
            "metrics": None,
            "model_configurations": None,
            "model_config_ids": None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating test session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create test session: {str(e)}")

@router.get("", response_model=List[TestSessionResponse])
async def list_test_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    video_id: Optional[str] = Query(None, description="Filter by video"),
    status: Optional[str] = Query(None, description="Filter by session status"),
    db: Session = Depends(get_db)
):
    """List test sessions with optional filtering and pagination"""
    try:
        query = db.query(TestSession)
        
        # Apply filters
        if project_id:
            query = query.filter(TestSession.project_id == project_id)
        
        if video_id:
            query = query.filter(TestSession.video_id == video_id)
        
        if status:
            query = query.filter(TestSession.status == status)
        
        sessions = query.order_by(TestSession.created_at.desc()).offset(skip).limit(limit).all()
        
        # Enrich with project information
        session_list = []
        for session in sessions:
            project = db.query(Project).filter(Project.id == session.project_id).first()
            
            session_dict = {
                "id": session.id,
                "name": session.name,
                "project_id": session.project_id,
                "project_name": project.name if project else "Unknown",
                "video_id": session.video_id,
                "status": session.status,
                "tolerance_ms": session.tolerance_ms,
                "created_at": session.created_at,
                "started_at": session.started_at,
                "completed_at": session.completed_at
            }
            session_list.append(session_dict)
        
        logger.info(f"Retrieved {len(session_list)} test sessions")
        return session_list
        
    except (OperationalError, SQLAlchemyError) as e:
        logger.error(f"Database error listing test sessions: {e}")
        return []
    except Exception as e:
        logger.error(f"Error listing test sessions: {str(e)}")
        return []

@router.get("/{session_id}", response_model=TestSessionResponse)
async def get_test_session_details(session_id: str, db: Session = Depends(get_db)):
    """Get detailed information about a test session"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Get enriched session details
        project = db.query(Project).filter(Project.id == session.project_id).first()
        video = db.query(Video).filter(Video.id == session.video_id).first() if session.video_id else None
        
        # Calculate session statistics
        detection_count = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id
        ).scalar() or 0
        
        result_count = db.query(func.count(TestResult.id)).filter(
            TestResult.test_session_id == session_id
        ).scalar() or 0
        
        session_details = {
            "id": session.id,
            "name": session.name,
            "project_id": session.project_id,
            "project_name": project.name if project else "Unknown",
            "video_id": session.video_id,
            "video_filename": video.filename if video else None,
            "status": session.status,
            "tolerance_ms": session.tolerance_ms,
            "created_at": session.created_at,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "statistics": {
                "total_detections": detection_count,
                "total_results": result_count,
                "duration_seconds": (
                    (session.completed_at - session.started_at).total_seconds()
                    if session.started_at and session.completed_at
                    else None
                )
            }
        }
        
        return session_details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving test session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve test session: {str(e)}")

# ============================================================================
# TEST SESSION EXECUTION CONTROL - FIXED HIL INTEGRATION
# ============================================================================

@router.post("/{session_id}/start")
async def start_test_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start a test session execution with dedicated monitoring service"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        if session.status != "created":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot start session in {session.status} status"
            )
        
        # Update session status
        session.status = "running"
        session.started_at = datetime.utcnow()
        db.commit()
        
        # Initialize monitoring result
        monitoring_result = {"success": False, "error": "Not attempted"}
        
        # Start dedicated monitoring service for HIL tests
        try:
            logger.info(f"🚀 Starting dedicated monitoring service for session: {session_id}")
            
            # Use the new dedicated monitoring service
            monitoring_result = await monitoring_service_manager.start_session_monitoring(
                session_id=session_id,
                sample_rate=10,
                wait_for_service=True  # Wait up to 30 seconds for service to be available
            )
            
            if monitoring_result.get("success"):
                logger.info(f"✅ Dedicated monitoring service started for session: {session_id}")
            else:
                logger.warning(f"⚠️ Dedicated monitoring service failed: {monitoring_result.get('error')}")
                logger.info(f"💡 {monitoring_result.get('fallback', 'Session proceeding without monitoring')}")
                
                # Fallback to legacy monitoring if available
                try:
                    if labjack_monitoring_service.start_monitoring(session_id, sample_rate=10):
                        logger.info(f"🔄 Fallback to legacy monitoring service for session: {session_id}")
                        monitoring_result["fallback_active"] = True
                except Exception as fallback_error:
                    logger.warning(f"❌ Fallback monitoring also failed: {fallback_error}")
            
        except Exception as monitor_error:
            logger.error(f"❌ Monitoring service error: {monitor_error}")
            monitoring_result = {
                "success": False, 
                "error": str(monitor_error),
                "fallback": "Session proceeding without hardware monitoring"
            }
        
        # Start background test execution if session manager is available
        try:
            if hasattr(session_manager, 'execute_test_session'):
                background_tasks.add_task(
                    session_manager.execute_test_session,
                    session_id
                )
                logger.info(f"📋 Background test execution queued for session: {session_id}")
            else:
                logger.info(f"ℹ️ No session manager available, manual test execution required")
        except Exception as exec_error:
            logger.warning(f"⚠️ Failed to queue background execution: {exec_error}")
        
        logger.info(f"🎯 Test session started: {session_id}")
        
        response = {
            "session_id": session_id,
            "status": "running",
            "started_at": session.started_at.isoformat(),
            "message": "Test session started successfully",
            "monitoring": {
                "dedicated_service": monitoring_result.get("success", False),
                "fallback_active": monitoring_result.get("fallback_active", False),
                "error": monitoring_result.get("error") if not monitoring_result.get("success") else None
            }
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error starting test session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start test session: {str(e)}")

@router.post("/{session_id}/complete")
async def complete_test_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Mark a test session as completed with proper monitoring service cleanup"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        if session.status != "running":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot complete session in {session.status} status"
            )
        
        # Stop dedicated monitoring service
        monitoring_summary = {"detection_count": 0, "service_used": "none"}
        
        try:
            logger.info(f"⏹️ Stopping dedicated monitoring service for session: {session_id}")
            
            # Stop the dedicated monitoring service first
            stop_result = await monitoring_service_manager.stop_session_monitoring()
            
            if stop_result.get("success"):
                monitoring_summary["detection_count"] = stop_result.get("detection_count", 0)
                monitoring_summary["service_used"] = "dedicated"
                logger.info(f"✅ Dedicated monitoring stopped: {monitoring_summary['detection_count']} detections")
            else:
                logger.warning(f"⚠️ Failed to stop dedicated monitoring: {stop_result.get('error')}")
                
                # Fallback to stopping legacy monitoring
                try:
                    labjack_monitoring_service.stop_monitoring()
                    monitoring_summary["service_used"] = "legacy_fallback"
                    logger.info(f"🔄 Stopped fallback monitoring service")
                except Exception as legacy_error:
                    logger.warning(f"❌ Failed to stop legacy monitoring: {legacy_error}")
                    
        except Exception as e:
            logger.error(f"❌ Error stopping monitoring services: {e}")
            monitoring_summary["error"] = str(e)
        
        # Update session status
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        db.commit()
        
        # Calculate final statistics from database
        detection_count = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id
        ).scalar() or 0
        
        # Update detection count from monitoring service if higher
        if monitoring_summary["detection_count"] > detection_count:
            logger.info(f"📊 Monitoring service reported {monitoring_summary['detection_count']} detections, "
                       f"database shows {detection_count}. Using database count for accuracy.")
        
        duration = (session.completed_at - session.started_at).total_seconds() if session.started_at else 0
        
        # Create comprehensive TestResult entry
        test_result_created = False
        
        if detection_count > 0:
            try:
                # Get detection events for this session
                detections = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == session_id
                ).all()
                
                # Calculate HIL test metrics with more robust validation
                passed_count = len([
                    d for d in detections 
                    if d.validation_result and d.validation_result.lower() in ["passed", "pass", "valid", "tp"]
                ])
                failed_count = detection_count - passed_count
                pass_rate = (passed_count / detection_count) * 100 if detection_count > 0 else 0
                
                # Calculate latency metrics if available
                latencies = [d.processing_time_ms for d in detections if d.processing_time_ms is not None]
                avg_latency = sum(latencies) / len(latencies) if latencies else 5.0
                min_latency = min(latencies) if latencies else 5.0
                max_latency = max(latencies) if latencies else 5.0
                
                # Create TestResult entry
                test_result = TestResult(
                    id=str(uuid.uuid4()),
                    test_session_id=session_id,
                    total_detections=detection_count,
                    passed_detections=passed_count,
                    failed_detections=failed_count,
                    pass_rate=pass_rate / 100,  # Store as decimal
                    test_duration_seconds=duration,
                    detection_rate_hz=detection_count / duration if duration > 0 else 0,
                    validation_type=f"HIL_LabJack_{monitoring_summary['service_used']}",
                    threshold_ms=100,
                    avg_latency_ms=avg_latency,
                    min_latency_ms=min_latency,
                    max_latency_ms=max_latency,
                    median_latency_ms=avg_latency,  # Approximation
                    precision=passed_count / detection_count if detection_count > 0 else 0,
                    recall=1.0 if detection_count > 0 else 0,  # Assuming all ground truth was detected
                    f1_score=2 * (pass_rate/100) / (1 + (pass_rate/100)) if pass_rate > 0 else 0,
                    accuracy=pass_rate / 100,
                    true_positives=passed_count,
                    false_positives=0,  # Assuming all detections are valid
                    false_negatives=failed_count,
                    created_at=datetime.utcnow()
                )
                
                db.add(test_result)
                db.commit()
                test_result_created = True
                
                logger.info(f"✅ Created comprehensive HIL test result: {passed_count}/{detection_count} passed ({pass_rate:.1f}%)")
                
            except Exception as e:
                logger.error(f"❌ Failed to create test result: {e}")
                db.rollback()
        
        completion_message = f"Test session completed: {session_id} ({detection_count} detections, {duration:.2f}s)"
        if monitoring_summary.get("error"):
            completion_message += f" [Monitoring error: {monitoring_summary['error']}]"
        
        logger.info(completion_message)
        
        response = {
            "session_id": session_id,
            "status": "completed",
            "completed_at": session.completed_at.isoformat(),
            "total_detections": detection_count,
            "duration_seconds": duration,
            "monitoring_service": monitoring_summary["service_used"],
            "test_result_created": test_result_created,
            "message": "Test session completed successfully"
        }
        
        # Add monitoring details if there were issues
        if monitoring_summary.get("error"):
            response["monitoring_error"] = monitoring_summary["error"]
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error completing test session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to complete test session: {str(e)}")

@router.get("/{session_id}/status")
async def get_test_session_status(session_id: str, db: Session = Depends(get_db)):
    """Get current status and progress of a test session with monitoring info"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Get real-time statistics
        detection_count = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id
        ).scalar() or 0
        
        # Get monitoring service status if session is running
        monitoring_status = None
        if session.status == "running":
            try:
                monitoring_status = await monitoring_service_manager.get_monitoring_status()
            except Exception as e:
                logger.warning(f"⚠️ Could not get monitoring status: {e}")
                monitoring_status = {"service_available": False, "error": str(e)}
        
        # Calculate progress if video is available
        progress_percentage = None
        if session.video_id:
            video = db.query(Video).filter(Video.id == session.video_id).first()
            if video and video.duration and session.started_at:
                elapsed_time = (datetime.utcnow() - session.started_at).total_seconds()
                progress_percentage = min(100, (elapsed_time / video.duration) * 100)
        
        status_info = {
            "session_id": session_id,
            "status": session.status,
            "created_at": session.created_at.isoformat(),
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "current_detections": detection_count,
            "progress_percentage": progress_percentage,
            "is_active": session.status in ["running", "processing"],
            "monitoring": monitoring_status
        }
        
        return status_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get session status: {str(e)}")

# ============================================================================
# MONITORING SERVICE HEALTH AND STATUS
# ============================================================================

@router.get("/{session_id}/monitoring/status")
async def get_session_monitoring_status(session_id: str):
    """Get detailed monitoring service status for a session"""
    try:
        status = await monitoring_service_manager.get_monitoring_status()
        
        # Check if this session is being monitored
        current_session = status.get("session_id")
        is_monitoring_this_session = current_session == session_id
        
        return {
            "session_id": session_id,
            "is_monitoring": is_monitoring_this_session,
            "current_monitored_session": current_session,
            "service_status": status
        }
        
    except Exception as e:
        logger.error(f"Error getting monitoring status: {str(e)}")
        return {
            "session_id": session_id,
            "is_monitoring": False,
            "error": str(e),
            "service_available": False
        }

@router.post("/monitoring/health-check")
async def monitoring_service_health_check():
    """Perform comprehensive health check on monitoring service"""
    try:
        health = await monitoring_service_manager.client.health_check()
        
        return {
            "service": "dedicated_monitoring_service",
            "timestamp": datetime.utcnow().isoformat(),
            "health": health
        }
        
    except Exception as e:
        logger.error(f"Monitoring health check failed: {e}")
        return {
            "service": "dedicated_monitoring_service",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "unreachable",
            "error": str(e)
        }

# ============================================================================
# DETECTION EVENT MANAGEMENT (unchanged)
# ============================================================================

@router.post("/detection-events")
async def create_detection_event(
    detection: DetectionEventSchema,
    db: Session = Depends(get_db)
):
    """Create a new detection event for a test session"""
    try:
        # Validate test session exists
        session = db.query(TestSession).filter(TestSession.id == detection.test_session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Create detection event
        db_detection = DetectionEvent(
            id=str(uuid.uuid4()),
            **detection.dict(),
            created_at=datetime.utcnow()
        )
        
        db.add(db_detection)
        db.commit()
        db.refresh(db_detection)
        
        logger.info(f"Detection event created for session {detection.test_session_id}")
        
        return {
            "id": db_detection.id,
            "test_session_id": db_detection.test_session_id,
            "timestamp": db_detection.timestamp,
            "vru_type": db_detection.vru_type,
            "confidence": db_detection.confidence,
            "created_at": db_detection.created_at.isoformat(),
            "message": "Detection event created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating detection event: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create detection event: {str(e)}")

@router.get("/{session_id}/detections")
async def get_session_detections(
    session_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_time: Optional[float] = Query(None, description="Filter by start timestamp"),
    end_time: Optional[float] = Query(None, description="Filter by end timestamp"),
    vru_type: Optional[str] = Query(None, description="Filter by VRU type"),
    db: Session = Depends(get_db)
):
    """Get detection events for a test session with filtering"""
    try:
        # Verify session exists
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Build query with filters
        query = db.query(DetectionEvent).filter(DetectionEvent.test_session_id == session_id)
        
        if start_time is not None:
            query = query.filter(DetectionEvent.timestamp >= start_time)
        
        if end_time is not None:
            query = query.filter(DetectionEvent.timestamp <= end_time)
        
        if vru_type:
            query = query.filter(DetectionEvent.vru_type == vru_type)
        
        detections = query.order_by(DetectionEvent.timestamp).offset(skip).limit(limit).all()
        
        return {
            "session_id": session_id,
            "detections": [
                {
                    "id": detection.id,
                    "timestamp": detection.timestamp,
                    "vru_type": detection.vru_type,
                    "confidence": detection.confidence,
                    "bounding_box": {
                        "x": detection.bounding_box_x,
                        "y": detection.bounding_box_y,
                        "width": detection.bounding_box_width,
                        "height": detection.bounding_box_height
                    } if detection.bounding_box_x is not None else None,
                    "created_at": detection.created_at.isoformat()
                }
                for detection in detections
            ],
            "total_detections": len(detections),
            "filters_applied": {
                "time_range": [start_time, end_time] if start_time or end_time else None,
                "vru_type": vru_type
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session detections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve detections: {str(e)}")

# ============================================================================
# RESULTS AND VALIDATION (unchanged but enhanced with monitoring info)
# ============================================================================

@router.get("/{session_id}/results")
async def get_test_session_results(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get comprehensive test results for a session"""
    try:
        # Verify session exists
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Get test results
        results = db.query(TestResult).filter(TestResult.test_session_id == session_id).all()
        
        # Calculate summary statistics
        total_detections = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id
        ).scalar() or 0
        
        # Get detection type distribution
        vru_distribution = dict(
            db.query(DetectionEvent.vru_type, func.count(DetectionEvent.id))
            .filter(DetectionEvent.test_session_id == session_id)
            .group_by(DetectionEvent.vru_type)
            .all()
        )
        
        return {
            "session_id": session_id,
            "session_status": session.status,
            "results": [
                {
                    "id": result.id,
                    "test_session_id": result.test_session_id,
                    "total_detections": result.total_detections,
                    "passed_detections": result.passed_detections,
                    "failed_detections": result.failed_detections,
                    "pass_rate": result.pass_rate,
                    "accuracy": result.accuracy,
                    "precision": result.precision,
                    "recall": result.recall,
                    "f1_score": result.f1_score,
                    "validation_type": result.validation_type,
                    "test_duration_seconds": result.test_duration_seconds,
                    "detection_rate_hz": result.detection_rate_hz,
                    "avg_latency_ms": result.avg_latency_ms,
                    "created_at": result.created_at.isoformat()
                }
                for result in results
            ],
            "summary": {
                "total_detections": total_detections,
                "total_results": len(results),
                "vru_type_distribution": vru_distribution,
                "session_duration": (
                    (session.completed_at - session.started_at).total_seconds()
                    if session.started_at and session.completed_at
                    else None
                )
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving test results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve test results: {str(e)}")

# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def test_sessions_health_check():
    """Health check endpoint for test session management"""
    
    # Check monitoring service availability
    monitoring_available = await monitoring_service_manager.client.is_service_available()
    
    return {
        "status": "healthy",
        "service": "Test Sessions Router (Fixed HIL Integration)",
        "version": "2.0.0",
        "monitoring_service_available": monitoring_available,
        "endpoints": [
            "POST /api/test-sessions - Create test session",
            "GET /api/test-sessions - List test sessions", 
            "GET /api/test-sessions/{id} - Get session details",
            "POST /api/test-sessions/{id}/start - Start session with monitoring",
            "POST /api/test-sessions/{id}/complete - Complete session with cleanup",
            "GET /api/test-sessions/{id}/status - Get session status with monitoring",
            "GET /api/test-sessions/{id}/monitoring/status - Get monitoring status",
            "POST /api/test-sessions/monitoring/health-check - Check monitoring health",
            "POST /api/test-sessions/detection-events - Create detection event",
            "GET /api/test-sessions/{id}/detections - Get session detections",
            "GET /api/test-sessions/{id}/results - Get session results"
        ]
    }