"""
Test Sessions Router - Organized API Endpoints
============================================

Consolidated test session endpoints following FastAPI best practices.
Handles test session lifecycle, execution, results, and monitoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
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
        db_session = create_test_session(db=db, session=session)
        
        logger.info(f"Test session created: {db_session.id} for project {session.project_id}")
        return db_session
        
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
        
    except Exception as e:
        logger.error(f"Error listing test sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list test sessions: {str(e)}")

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
# TEST SESSION EXECUTION CONTROL
# ============================================================================

@router.post("/{session_id}/start")
async def start_test_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start a test session execution"""
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
        
        # Start session execution in background
        background_tasks.add_task(
            session_manager.execute_test_session,
            session_id
        )
        
        logger.info(f"Test session started: {session_id}")
        
        return {
            "session_id": session_id,
            "status": "running",
            "started_at": session.started_at.isoformat(),
            "message": "Test session started successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting test session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start test session: {str(e)}")

@router.post("/{session_id}/complete")
async def complete_test_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Mark a test session as completed"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        if session.status != "running":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot complete session in {session.status} status"
            )
        
        # Update session status
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        db.commit()
        
        # Calculate final statistics
        detection_count = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id
        ).scalar() or 0
        
        duration = (session.completed_at - session.started_at).total_seconds() if session.started_at else 0
        
        logger.info(f"Test session completed: {session_id} ({detection_count} detections, {duration:.2f}s)")
        
        return {
            "session_id": session_id,
            "status": "completed",
            "completed_at": session.completed_at.isoformat(),
            "total_detections": detection_count,
            "duration_seconds": duration,
            "message": "Test session completed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing test session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to complete test session: {str(e)}")

@router.get("/{session_id}/status")
async def get_test_session_status(session_id: str, db: Session = Depends(get_db)):
    """Get current status and progress of a test session"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Get real-time statistics
        detection_count = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id
        ).scalar() or 0
        
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
            "is_active": session.status in ["running", "processing"]
        }
        
        return status_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get session status: {str(e)}")

# ============================================================================
# DETECTION EVENT MANAGEMENT
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
# RESULTS AND VALIDATION
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
                    "detection_id": result.detection_id,
                    "ground_truth_id": result.ground_truth_id,
                    "is_match": result.is_match,
                    "distance": result.distance,
                    "confidence_diff": result.confidence_diff,
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

@router.get("/{session_id}/latency-metrics")
async def get_session_latency_metrics(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get latency and performance metrics for a test session"""
    try:
        # Verify session exists
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Get detection events ordered by timestamp
        detections = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).order_by(DetectionEvent.timestamp).all()
        
        if not detections:
            return {
                "session_id": session_id,
                "metrics": {
                    "total_detections": 0,
                    "detection_rate": 0,
                    "average_confidence": 0,
                    "latency_stats": None
                }
            }
        
        # Calculate metrics
        total_detections = len(detections)
        average_confidence = sum(d.confidence for d in detections) / total_detections
        
        # Calculate detection intervals (as proxy for latency)
        intervals = []
        for i in range(1, len(detections)):
            interval = detections[i].timestamp - detections[i-1].timestamp
            intervals.append(interval)
        
        latency_stats = None
        if intervals:
            latency_stats = {
                "min_interval": min(intervals),
                "max_interval": max(intervals),
                "avg_interval": sum(intervals) / len(intervals),
                "median_interval": sorted(intervals)[len(intervals) // 2]
            }
        
        # Calculate detection rate
        session_duration = (
            (session.completed_at - session.started_at).total_seconds()
            if session.started_at and session.completed_at
            else None
        )
        
        detection_rate = (
            total_detections / session_duration
            if session_duration and session_duration > 0
            else 0
        )
        
        return {
            "session_id": session_id,
            "metrics": {
                "total_detections": total_detections,
                "detection_rate": detection_rate,
                "average_confidence": average_confidence,
                "latency_stats": latency_stats,
                "session_duration": session_duration
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating latency metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate metrics: {str(e)}")

# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def test_sessions_health_check():
    """Health check endpoint for test session management"""
    return {
        "status": "healthy",
        "service": "Test Sessions Router",
        "version": "1.0.0",
        "endpoints": [
            "POST /api/test-sessions - Create test session",
            "GET /api/test-sessions - List test sessions",
            "GET /api/test-sessions/{id} - Get session details",
            "POST /api/test-sessions/{id}/start - Start session",
            "POST /api/test-sessions/{id}/complete - Complete session",
            "GET /api/test-sessions/{id}/status - Get session status",
            "POST /api/test-sessions/detection-events - Create detection event",
            "GET /api/test-sessions/{id}/detections - Get session detections",
            "GET /api/test-sessions/{id}/results - Get session results"
        ]
    }