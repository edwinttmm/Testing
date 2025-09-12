#!/usr/bin/env python3
"""
Basic Results API Endpoints
Provides simple /api/results and /api/results/enhanced endpoints for the Results page
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc, func
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database import get_db
from models import (
    Project, Video, TestSession, DetectionEvent, TestResult, 
    DetectionComparison, GroundTruthObject
)

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/results", tags=["Results"])

class BasicTestSession(BaseModel):
    """Basic test session data"""
    id: str
    name: str
    project_id: Optional[str]
    project_name: Optional[str]
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    results_count: int = 0
    detection_events: int = 0
    has_results: bool = False

class EnhancedSessionResults(BaseModel):
    """Enhanced session results with metrics"""
    session_id: str
    session_name: str
    project_name: Optional[str]
    status: str
    started_at: Optional[str] 
    completed_at: Optional[str]
    metrics: Dict[str, Any]
    detection_summary: Dict[str, Any]
    statistics: Dict[str, Any]

@router.get("/", response_model=List[BasicTestSession])
async def get_test_results(
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None, regex="^(completed|running|failed)$"),
    db: Session = Depends(get_db)
):
    """
    Get basic test session results
    This is the main endpoint that the Results page calls
    """
    try:
        # Build query
        query = db.query(TestSession).options(
            joinedload(TestSession.project)
        )
        
        # Filter by status if provided
        if status:
            query = query.filter(TestSession.status == status)
        
        # Order by most recent first
        sessions = query.order_by(desc(TestSession.started_at)).limit(limit).all()
        
        # Format response
        results = []
        for session in sessions:
            # Count test results and detection events
            test_results_count = db.query(TestResult).filter(
                TestResult.test_session_id == session.id
            ).count()
            
            detection_events_count = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).count()
            
            has_results = test_results_count > 0 or detection_events_count > 0
            
            result = BasicTestSession(
                id=session.id,
                name=session.name,
                project_id=session.project_id,
                project_name=session.project.name if session.project else None,
                status=session.status,
                started_at=session.started_at.isoformat() if session.started_at else None,
                completed_at=session.completed_at.isoformat() if session.completed_at else None,
                results_count=test_results_count,
                detection_events=detection_events_count,
                has_results=has_results
            )
            
            results.append(result)
        
        logger.info(f"Retrieved {len(results)} test sessions")
        return results
        
    except Exception as e:
        logger.error(f"Error retrieving test results: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving test results: {str(e)}"
        )

@router.get("/enhanced", response_model=List[EnhancedSessionResults])
async def get_enhanced_results(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get enhanced test results with detailed metrics
    Provides comprehensive data for the Results page
    """
    try:
        # Get completed sessions with detailed data
        sessions = db.query(TestSession).options(
            joinedload(TestSession.project)
        ).filter(
            TestSession.status == "completed"
        ).order_by(desc(TestSession.completed_at)).limit(limit).all()
        
        enhanced_results = []
        
        for session in sessions:
            # Get test results with metrics
            test_results = db.query(TestResult).filter(
                TestResult.test_session_id == session.id
            ).all()
            
            # Get detection events
            detection_events = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).all()
            
            # Calculate metrics
            total_detections = len(detection_events)
            passed_detections = sum(1 for d in detection_events if d.validation_result == "Pass")
            failed_detections = total_detections - passed_detections
            success_rate = (passed_detections / total_detections * 100) if total_detections > 0 else 0
            
            # Get average metrics from test results
            avg_accuracy = sum(r.accuracy for r in test_results if r.accuracy) / len(test_results) if test_results else 0
            avg_precision = sum(r.precision for r in test_results if r.precision) / len(test_results) if test_results else 0
            avg_recall = sum(r.recall for r in test_results if r.recall) / len(test_results) if test_results else 0
            avg_f1 = sum(r.f1_score for r in test_results if r.f1_score) / len(test_results) if test_results else 0
            
            # Detection type breakdown
            detection_types = {}
            for event in detection_events:
                obj_type = getattr(event, 'class_label', 'Unknown')
                detection_types[obj_type] = detection_types.get(obj_type, 0) + 1
            
            enhanced_result = EnhancedSessionResults(
                session_id=session.id,
                session_name=session.name,
                project_name=session.project.name if session.project else "Unknown Project",
                status=session.status,
                started_at=session.started_at.isoformat() if session.started_at else None,
                completed_at=session.completed_at.isoformat() if session.completed_at else None,
                metrics={
                    "accuracy": round(avg_accuracy * 100, 2) if avg_accuracy else None,
                    "precision": round(avg_precision * 100, 2) if avg_precision else None,
                    "recall": round(avg_recall * 100, 2) if avg_recall else None,
                    "f1_score": round(avg_f1 * 100, 2) if avg_f1 else None,
                    "success_rate": round(success_rate, 2)
                },
                detection_summary={
                    "total_detections": total_detections,
                    "passed_detections": passed_detections,
                    "failed_detections": failed_detections,
                    "detection_types": detection_types
                },
                statistics={
                    "test_results_count": len(test_results),
                    "detection_events_count": total_detections,
                    "processing_time": (
                        (session.completed_at - session.started_at).total_seconds()
                        if session.started_at and session.completed_at else None
                    )
                }
            )
            
            enhanced_results.append(enhanced_result)
        
        logger.info(f"Retrieved {len(enhanced_results)} enhanced test results")
        return enhanced_results
        
    except Exception as e:
        logger.error(f"Error retrieving enhanced results: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving enhanced results: {str(e)}"
        )

@router.get("/{session_id}", response_model=EnhancedSessionResults)
async def get_session_result(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed results for a specific session
    """
    try:
        session = db.query(TestSession).options(
            joinedload(TestSession.project)
        ).filter(TestSession.id == session_id).first()
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        # Get test results
        test_results = db.query(TestResult).filter(
            TestResult.test_session_id == session_id
        ).all()
        
        # Get detection events
        detection_events = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).all()
        
        # Calculate metrics (same as enhanced endpoint)
        total_detections = len(detection_events)
        passed_detections = sum(1 for d in detection_events if d.validation_result == "Pass")
        failed_detections = total_detections - passed_detections
        success_rate = (passed_detections / total_detections * 100) if total_detections > 0 else 0
        
        avg_accuracy = sum(r.accuracy for r in test_results if r.accuracy) / len(test_results) if test_results else 0
        avg_precision = sum(r.precision for r in test_results if r.precision) / len(test_results) if test_results else 0
        avg_recall = sum(r.recall for r in test_results if r.recall) / len(test_results) if test_results else 0
        avg_f1 = sum(r.f1_score for r in test_results if r.f1_score) / len(test_results) if test_results else 0
        
        detection_types = {}
        for event in detection_events:
            obj_type = getattr(event, 'class_label', 'Unknown')
            detection_types[obj_type] = detection_types.get(obj_type, 0) + 1
        
        result = EnhancedSessionResults(
            session_id=session.id,
            session_name=session.name,
            project_name=session.project.name if session.project else "Unknown Project",
            status=session.status,
            started_at=session.started_at.isoformat() if session.started_at else None,
            completed_at=session.completed_at.isoformat() if session.completed_at else None,
            metrics={
                "accuracy": round(avg_accuracy * 100, 2) if avg_accuracy else None,
                "precision": round(avg_precision * 100, 2) if avg_precision else None,
                "recall": round(avg_recall * 100, 2) if avg_recall else None,
                "f1_score": round(avg_f1 * 100, 2) if avg_f1 else None,
                "success_rate": round(success_rate, 2)
            },
            detection_summary={
                "total_detections": total_detections,
                "passed_detections": passed_detections,
                "failed_detections": failed_detections,
                "detection_types": detection_types
            },
            statistics={
                "test_results_count": len(test_results),
                "detection_events_count": total_detections,
                "processing_time": (
                    (session.completed_at - session.started_at).total_seconds()
                    if session.started_at and session.completed_at else None
                )
            }
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session result: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving session result: {str(e)}"
        )

# Health check
@router.get("/health")
async def health_check():
    """Health check for results API"""
    return {
        "status": "healthy",
        "service": "Results API",
        "timestamp": datetime.utcnow().isoformat()
    }

# Export router
__all__ = ["router"]