"""
Enhanced Test API Router
Provides comprehensive testing and validation endpoints for the AI Model Validation Platform
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, and_
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import uuid

# Database and model imports
from database import SessionLocal
from models import Project, Video, TestSession, DetectionEvent, GroundTruthObject
from schemas import (
    TestSessionCreate, TestSessionResponse,
    DetectionEvent as DetectionEventSchema,
    ValidationResult
)

# Service imports with fallback
try:
    from services.validation_service import ValidationService
    validation_service = ValidationService()
except ImportError:
    validation_service = None

logger = logging.getLogger(__name__)

def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create router
router = APIRouter(prefix="/api/test", tags=["Enhanced Testing"])

@router.get("/health")
async def test_health():
    """Test API health check"""
    return {
        "status": "healthy",
        "api": "enhanced_test",
        "timestamp": datetime.utcnow().isoformat(),
        "validation_service_available": validation_service is not None
    }

@router.post("/sessions", response_model=TestSessionResponse)
async def create_test_session(
    test_session: TestSessionCreate,
    db: Session = Depends(get_db)
):
    """Create a new test session"""
    try:
        # Create test session object
        db_session = TestSession(
            id=str(uuid.uuid4()),
            project_id=test_session.project_id,
            name=test_session.name,
            description=test_session.description,
            created_at=datetime.utcnow(),
            status="pending"
        )
        
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        
        return TestSessionResponse(
            id=db_session.id,
            project_id=db_session.project_id,
            name=db_session.name,
            description=db_session.description,
            created_at=db_session.created_at,
            status=db_session.status
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error creating test session: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create test session")

@router.get("/sessions", response_model=List[TestSessionResponse])
async def list_test_sessions(
    project_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List test sessions"""
    try:
        query = db.query(TestSession)
        if project_id:
            query = query.filter(TestSession.project_id == project_id)
        
        sessions = query.offset(offset).limit(limit).all()
        
        return [
            TestSessionResponse(
                id=session.id,
                project_id=session.project_id,
                name=session.name,
                description=session.description,
                created_at=session.created_at,
                status=session.status
            )
            for session in sessions
        ]
    except SQLAlchemyError as e:
        logger.error(f"Database error listing test sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list test sessions")

@router.get("/sessions/{session_id}", response_model=TestSessionResponse)
async def get_test_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific test session"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        return TestSessionResponse(
            id=session.id,
            project_id=session.project_id,
            name=session.name,
            description=session.description,
            created_at=session.created_at,
            status=session.status
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error getting test session: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test session")

@router.post("/sessions/{session_id}/run")
async def run_test_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Run a test session"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Update session status
        session.status = "running"
        session.started_at = datetime.utcnow()
        db.commit()
        
        # Run validation in background if service is available
        if validation_service:
            background_tasks.add_task(run_validation_task, session_id)
        
        return {
            "message": "Test session started",
            "session_id": session_id,
            "status": "running"
        }
    except SQLAlchemyError as e:
        logger.error(f"Database error running test session: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to run test session")

@router.get("/sessions/{session_id}/results")
async def get_test_results(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get test session results"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Get detection events for this session
        detection_count = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id
        ).scalar() or 0
        
        # Get ground truth objects
        ground_truth_count = db.query(func.count(GroundTruthObject.id)).join(
            Video, Video.id == GroundTruthObject.video_id
        ).join(
            TestSession, TestSession.project_id == Video.project_id
        ).filter(TestSession.id == session_id).scalar() or 0
        
        return {
            "session_id": session_id,
            "status": session.status,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "detection_count": detection_count,
            "ground_truth_count": ground_truth_count,
            "results": {
                "precision": 0.0,  # Calculate if validation service available
                "recall": 0.0,
                "f1_score": 0.0,
                "accuracy": 0.0
            }
        }
    except SQLAlchemyError as e:
        logger.error(f"Database error getting test results: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test results")

async def run_validation_task(session_id: str):
    """Background task to run validation"""
    try:
        if validation_service:
            await validation_service.run_session_validation(session_id)
        logger.info(f"Completed validation for session {session_id}")
    except Exception as e:
        logger.error(f"Error running validation task: {e}")

@router.get("/metrics/summary")
async def get_metrics_summary(
    project_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get testing metrics summary"""
    try:
        query = db.query(TestSession)
        if project_id:
            query = query.filter(TestSession.project_id == project_id)
        
        total_sessions = query.count()
        completed_sessions = query.filter(TestSession.status == "completed").count()
        running_sessions = query.filter(TestSession.status == "running").count()
        failed_sessions = query.filter(TestSession.status == "failed").count()
        
        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "running_sessions": running_sessions,
            "failed_sessions": failed_sessions,
            "success_rate": completed_sessions / total_sessions if total_sessions > 0 else 0.0
        }
    except SQLAlchemyError as e:
        logger.error(f"Database error getting metrics summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get metrics summary")