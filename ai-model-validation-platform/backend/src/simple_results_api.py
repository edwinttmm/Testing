#!/usr/bin/env python3
"""
Simple Results API - Hot-reloadable endpoint for Results page
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
import logging
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models import Project, Video, TestSession, DetectionEvent, TestResult

logger = logging.getLogger(__name__)

# Router for simple results
router = APIRouter(prefix="/api/simple-results", tags=["Simple Results"])

class SimpleSessionResult(BaseModel):
    """Simple session result model"""
    session_id: str
    session_name: str
    project_name: str
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    accuracy: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    f1_score: Optional[float]
    success_rate: float
    total_detections: int
    passed_detections: int
    failed_detections: int

@router.get("/", response_model=List[SimpleSessionResult])
async def get_simple_results(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get simple results for completed test sessions
    This endpoint works independently of project structure issues
    """
    try:
        logger.info("Getting simple results for completed test sessions")
        
        # Get completed sessions
        sessions = db.query(TestSession).filter(
            TestSession.status == "completed"
        ).order_by(desc(TestSession.completed_at)).limit(limit).all()
        
        logger.info(f"Found {len(sessions)} completed sessions")
        
        results = []
        for session in sessions:
            try:
                # Get project name safely
                project_name = "Unknown Project"
                if session.project_id:
                    project = db.query(Project).filter(Project.id == session.project_id).first()
                    if project:
                        project_name = project.name
                
                # Get test results
                test_results = db.query(TestResult).filter(
                    TestResult.test_session_id == session.id
                ).all()
                
                # Calculate average metrics
                avg_accuracy = None
                avg_precision = None
                avg_recall = None
                avg_f1 = None
                
                if test_results:
                    accuracies = [r.accuracy for r in test_results if r.accuracy is not None]
                    precisions = [r.precision for r in test_results if r.precision is not None]
                    recalls = [r.recall for r in test_results if r.recall is not None]
                    f1_scores = [r.f1_score for r in test_results if r.f1_score is not None]
                    
                    avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else None
                    avg_precision = sum(precisions) / len(precisions) if precisions else None
                    avg_recall = sum(recalls) / len(recalls) if recalls else None
                    avg_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else None
                
                # Get detection events
                detection_events = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == session.id
                ).all()
                
                total_detections = len(detection_events)
                passed_detections = sum(1 for d in detection_events if d.validation_result == "Pass")
                failed_detections = total_detections - passed_detections
                success_rate = (passed_detections / total_detections * 100) if total_detections > 0 else 0
                
                result = SimpleSessionResult(
                    session_id=session.id,
                    session_name=session.name,
                    project_name=project_name,
                    status=session.status,
                    started_at=session.started_at.isoformat() if session.started_at else None,
                    completed_at=session.completed_at.isoformat() if session.completed_at else None,
                    accuracy=round(avg_accuracy * 100, 2) if avg_accuracy else None,
                    precision=round(avg_precision * 100, 2) if avg_precision else None,
                    recall=round(avg_recall * 100, 2) if avg_recall else None,
                    f1_score=round(avg_f1 * 100, 2) if avg_f1 else None,
                    success_rate=round(success_rate, 2),
                    total_detections=total_detections,
                    passed_detections=passed_detections,
                    failed_detections=failed_detections
                )
                
                results.append(result)
                
            except Exception as session_error:
                logger.warning(f"Error processing session {session.id}: {session_error}")
                continue
        
        logger.info(f"Successfully processed {len(results)} session results")
        return results
        
    except Exception as e:
        logger.error(f"Error in get_simple_results: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving simple results: {str(e)}"
        )

@router.get("/health")
async def simple_results_health():
    """Health check for simple results API"""
    return {
        "status": "healthy",
        "service": "Simple Results API", 
        "timestamp": datetime.utcnow().isoformat()
    }

# Export router
__all__ = ["router"]