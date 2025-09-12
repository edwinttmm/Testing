#!/usr/bin/env python3
"""
Enhanced Results API
Populates the results page with stored detection data from project-based sessions
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
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models import (
    Project, Video, TestSession, DetectionEvent, TestResult, 
    DetectionComparison, GroundTruthObject
)

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/results", tags=["Enhanced Results"])

# Response Models
class VideoDetectionResult(BaseModel):
    """Individual video detection result"""
    video_id: str
    video_filename: str
    total_detections: int
    passed_detections: int
    failed_detections: int
    success_rate: float
    detection_types: List[str]
    average_confidence: float
    processing_time: Optional[str]

class SessionResults(BaseModel):
    """Complete session results"""
    session_id: str
    session_name: str
    project_id: str
    project_name: str
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    total_videos: int
    successful_videos: int
    failed_videos: int
    video_results: List[VideoDetectionResult]
    statistics: Dict[str, Any]

class ProjectResultsSummary(BaseModel):
    """Project-level results summary"""
    project_id: str
    project_name: str
    total_sessions: int
    total_videos_processed: int
    total_detections: int
    overall_success_rate: float
    recent_sessions: List[Dict[str, Any]]
    detection_type_breakdown: Dict[str, int]

@router.get("/projects/{project_id}/sessions", response_model=List[Dict[str, Any]])
async def get_project_results_sessions(
    project_id: str,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all test sessions for a project with results summary
    This is what populates the results page
    """
    try:
        # Validate project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        # Get sessions with results
        sessions = db.query(TestSession).filter(
            TestSession.project_id == project_id
        ).order_by(desc(TestSession.started_at)).limit(limit).all()
        
        session_results = []
        for session in sessions:
            # Get test results for this session
            test_results = db.query(TestResult).filter(
                TestResult.test_session_id == session.id
            ).all()
            
            # Get detection events count
            detection_count = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).count()
            
            # Get comparison results
            comparison_count = db.query(DetectionComparison).filter(
                DetectionComparison.test_session_id == session.id
            ).count()
            
            session_data = {
                "session_id": session.id,
                "session_name": session.name,
                "status": session.status,
                "session_type": getattr(session, 'session_type', 'standard'),
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "results_count": len(test_results),
                "detection_events": detection_count,
                "detection_comparisons": comparison_count,
                "has_results": len(test_results) > 0 or detection_count > 0,
                "results_summary": session.results_summary or {},
                "configuration": session.configuration or {}
            }
            
            session_results.append(session_data)
        
        return session_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project sessions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving project sessions: {str(e)}"
        )

@router.get("/sessions/{session_id}/detailed", response_model=SessionResults)
async def get_detailed_session_results(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive detailed results for a specific session
    This provides all the data needed for the detailed results view
    """
    try:
        # Get session with project info
        session = db.query(TestSession).options(
            joinedload(TestSession.project)
        ).filter(TestSession.id == session_id).first()
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        # Get all test results for this session with test_session relationship loaded
        test_results = db.query(TestResult).options(
            joinedload(TestResult.test_session)
        ).filter(TestResult.test_session_id == session_id).all()
        
        # Get all detection events for this session with proper error handling
        detection_events = db.query(DetectionEvent).options(
            joinedload(DetectionEvent.video)  # ✅ Load video relationship properly
        ).filter(
            DetectionEvent.test_session_id == session_id
        ).all()
        
        # Get all detection comparisons for this session with relationships loaded
        detection_comparisons = db.query(DetectionComparison).options(
            joinedload(DetectionComparison.detection_event)
        ).filter(
            DetectionComparison.test_session_id == session_id
        ).all()
        
        # Group results by video
        video_results = {}
        
        # Process test results
        for result in test_results:
            # FIXED: Get video_id from the test_session relationship since TestResult doesn't have video_id directly
            video_id = result.test_session.video_id if result.test_session else None
            if not video_id:
                continue  # Skip if no video_id available
            if video_id not in video_results:
                # Get video info
                video = db.query(Video).filter(Video.id == video_id).first()
                video_results[video_id] = {
                    "video_id": video_id,
                    "video_filename": video.filename if video else "Unknown",
                    "test_results": [],
                    "detection_events": [],
                    "detection_comparisons": []
                }
            
            # Map TestResult fields to expected format
            test_result_data = {
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
                "created_at": result.created_at.isoformat()
            }
            
            video_results[video_id]["test_results"].append(test_result_data)
        
        # Process detection events with comprehensive error handling
        for event in detection_events:
            try:
                # Use loaded video relationship or fallback to video_id lookup
                video_id = getattr(event, 'video_id', None)
                video_obj = getattr(event, 'video', None) if hasattr(event, 'video') else None
                
                if video_id and video_id not in video_results:
                    # Try to get video filename from loaded relationship first
                    try:
                        if video_obj:
                            video_filename = video_obj.filename
                        else:
                            # Fallback: Get video info directly from database
                            video = db.query(Video).filter(Video.id == video_id).first() if video_id else None
                            video_filename = video.filename if video else "Unknown"
                    except Exception as video_error:
                        logger.warning(f"Could not load video {video_id}: {video_error}")
                        video_filename = "Unknown"
                    
                    video_results[video_id] = {
                        "video_id": video_id,
                        "video_filename": video_filename,
                        "test_results": [],
                        "detection_events": [],
                        "detection_comparisons": []
                    }
                
                if video_id:  # Only process if we have a valid video_id
                    video_results[video_id]["detection_events"].append({
                        "id": getattr(event, 'id', ''),
                        "detection_id": getattr(event, 'detection_id', ''),
                        "object_type": getattr(event, 'class_label', ''),  # FIXED: Use class_label from DetectionEvent model
                        "confidence_score": getattr(event, 'confidence', 0.0),  # FIXED: Use confidence from DetectionEvent model
                        "validation_result": getattr(event, 'validation_result', ''),
                        "bounding_box": {
                            "x": getattr(event, 'bounding_box_x', 0),
                            "y": getattr(event, 'bounding_box_y', 0),
                            "width": getattr(event, 'bounding_box_width', 0),
                            "height": getattr(event, 'bounding_box_height', 0)
                        } if getattr(event, 'bounding_box_x', None) is not None else None,
                        "frame_number": getattr(event, 'frame_number', 0),
                        "timestamp": str(getattr(event, 'timestamp', 0.0))
                    })
            except Exception as event_error:
                logger.warning(f"Error processing detection event {getattr(event, 'id', 'unknown')}: {event_error}")
                continue
        
        # Process detection comparisons with error handling
        for comparison in detection_comparisons:
            try:
                # Get video_id through detection_event relationship with error handling
                detection_event = getattr(comparison, 'detection_event', None)
                if detection_event:
                    video_id = getattr(detection_event, 'video_id', None)
                    if video_id and video_id in video_results:
                        video_results[video_id]["detection_comparisons"].append({
                            "id": getattr(comparison, 'id', ''),
                            "detection_event_id": getattr(comparison, 'detection_event_id', ''),
                            "ground_truth_id": getattr(comparison, 'ground_truth_id', ''),
                            "match_type": getattr(comparison, 'match_type', ''),  # FIXED: Use correct field name
                            "iou_score": getattr(comparison, 'iou_score', 0.0),  # FIXED: Use correct field name
                            "distance_error": getattr(comparison, 'distance_error', 0.0),
                            "temporal_offset": getattr(comparison, 'temporal_offset', 0.0),
                            "notes": getattr(comparison, 'notes', '')  # FIXED: Use correct field name
                        })
            except Exception as comp_error:
                logger.warning(f"Error processing detection comparison {getattr(comparison, 'id', 'unknown')}: {comp_error}")
                continue
        
        # Create video result summaries with ENHANCED TEST METRICS
        formatted_video_results = []
        for video_id, data in video_results.items():
            detection_events = data["detection_events"]
            
            total_detections = len(detection_events)
            passed_detections = sum(1 for d in detection_events if d["validation_result"] == "Pass")
            failed_detections = total_detections - passed_detections
            success_rate = (passed_detections / total_detections * 100) if total_detections > 0 else 0
            
            detection_types = list(set(d["object_type"] for d in detection_events))
            
            # ENHANCED: Calculate average latency for passed tests (timestamp represents latency in enhanced tests)
            passed_latencies = [
                float(d["timestamp"]) * 1000  # Convert to ms for latency display
                for d in detection_events 
                if d["validation_result"] == "Pass" and d["timestamp"]
            ]
            average_latency_ms = sum(passed_latencies) / len(passed_latencies) if passed_latencies else 0
            
            # Use latency as the confidence metric for enhanced tests (more meaningful)
            average_confidence = average_latency_ms
            
            # ENHANCED: Calculate processing time from detection event timestamps
            processing_times = [
                float(d["timestamp"]) for d in detection_events if d["timestamp"]
            ]
            total_processing_time = f"{max(processing_times):.3f}s" if processing_times else None
            
            video_result = VideoDetectionResult(
                video_id=video_id,
                video_filename=data["video_filename"],
                total_detections=total_detections,
                passed_detections=passed_detections,
                failed_detections=failed_detections,
                success_rate=success_rate,
                detection_types=detection_types,
                average_confidence=average_latency_ms,  # Now represents average latency
                processing_time=total_processing_time
            )
            
            formatted_video_results.append(video_result)
        
        # Calculate overall statistics
        total_videos = len(formatted_video_results)
        successful_videos = sum(1 for v in formatted_video_results if v.success_rate > 50)
        failed_videos = total_videos - successful_videos
        
        session_result = SessionResults(
            session_id=session_id,
            session_name=session.name,
            project_id=session.project_id,
            project_name=session.project.name if session.project else "Unknown Project",
            status=session.status,
            started_at=session.started_at.isoformat() if session.started_at else None,
            completed_at=session.completed_at.isoformat() if session.completed_at else None,
            total_videos=total_videos,
            successful_videos=successful_videos,
            failed_videos=failed_videos,
            video_results=formatted_video_results,
            statistics={
                "total_detections": sum(v.total_detections for v in formatted_video_results),
                "total_passed": sum(v.passed_detections for v in formatted_video_results),
                "total_failed": sum(v.failed_detections for v in formatted_video_results),
                "overall_success_rate": (
                    sum(v.success_rate for v in formatted_video_results) / len(formatted_video_results)
                    if formatted_video_results else 0
                ),
                "unique_detection_types": list(set(
                    dt for v in formatted_video_results for dt in v.detection_types
                )),
                "average_confidence_all_videos": (
                    sum(v.average_confidence for v in formatted_video_results) / len(formatted_video_results)
                    if formatted_video_results else 0
                )
            }
        )
        
        return session_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detailed session results: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving detailed results: {str(e)}"
        )

@router.get("/projects/{project_id}/summary", response_model=ProjectResultsSummary)
async def get_project_results_summary(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive project-level results summary
    Shows overall project performance across all sessions
    """
    try:
        # Validate project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        # Get all sessions for project
        sessions = db.query(TestSession).filter(
            TestSession.project_id == project_id
        ).all()
        
        # Get all detection events for project
        all_detection_events = db.query(DetectionEvent).join(
            TestSession, DetectionEvent.test_session_id == TestSession.id
        ).filter(TestSession.project_id == project_id).all()
        
        # Get unique videos processed
        unique_videos = db.query(Video).filter(Video.project_id == project_id).count()
        
        # Calculate statistics
        total_detections = len(all_detection_events)
        passed_detections = sum(1 for d in all_detection_events if d.validation_result == "Pass")
        overall_success_rate = (passed_detections / total_detections * 100) if total_detections > 0 else 0
        
        # Detection type breakdown
        detection_type_counts = {}
        for event in all_detection_events:
            obj_type = event.class_label  # FIXED: Use class_label from DetectionEvent model
            detection_type_counts[obj_type] = detection_type_counts.get(obj_type, 0) + 1
        
        # Recent sessions (last 5)
        recent_sessions = []
        for session in sorted(sessions, key=lambda s: s.started_at or datetime.min, reverse=True)[:5]:
            session_detection_count = sum(
                1 for d in all_detection_events if d.test_session_id == session.id
            )
            
            recent_sessions.append({
                "session_id": session.id,
                "session_name": session.name,
                "status": session.status,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "detection_count": session_detection_count
            })
        
        summary = ProjectResultsSummary(
            project_id=project_id,
            project_name=project.name,
            total_sessions=len(sessions),
            total_videos_processed=unique_videos,
            total_detections=total_detections,
            overall_success_rate=overall_success_rate,
            recent_sessions=recent_sessions,
            detection_type_breakdown=detection_type_counts
        )
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving project summary: {str(e)}"
        )

@router.get("/sessions/{session_id}/export", response_model=Dict[str, Any])
async def export_session_results(
    session_id: str,
    format: str = Query("json", pattern="^(json|csv|excel)$"),
    db: Session = Depends(get_db)
):
    """
    Export session results in various formats
    Useful for downloading and sharing results
    """
    try:
        # Get detailed results
        detailed_results = await get_detailed_session_results(session_id, db)
        
        if format == "json":
            return {
                "success": True,
                "format": "json",
                "data": detailed_results.dict(),
                "export_timestamp": datetime.utcnow().isoformat()
            }
        elif format == "csv":
            # Convert to CSV-friendly format
            csv_data = []
            for video_result in detailed_results.video_results:
                csv_data.append({
                    "session_id": session_id,
                    "session_name": detailed_results.session_name,
                    "video_filename": video_result.video_filename,
                    "total_detections": video_result.total_detections,
                    "passed_detections": video_result.passed_detections,
                    "failed_detections": video_result.failed_detections,
                    "success_rate": video_result.success_rate,
                    "detection_types": ",".join(video_result.detection_types),
                    "average_confidence": video_result.average_confidence
                })
            
            return {
                "success": True,
                "format": "csv",
                "headers": list(csv_data[0].keys()) if csv_data else [],
                "data": csv_data,
                "export_timestamp": datetime.utcnow().isoformat()
            }
        else:
            # Excel format would require additional processing
            return {
                "success": False,
                "error": "Excel export not yet implemented",
                "available_formats": ["json", "csv"]
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting session results: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error exporting results: {str(e)}"
        )

@router.get("/dashboard/project/{project_id}", response_model=Dict[str, Any])
async def get_project_dashboard_data(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    Get dashboard data for a specific project
    Provides charts and metrics for the frontend dashboard
    """
    try:
        # Get project summary
        summary = await get_project_results_summary(project_id, db)
        
        # Get session trend data (last 30 days)
        from datetime import timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        recent_sessions = db.query(TestSession).filter(
            and_(
                TestSession.project_id == project_id,
                TestSession.started_at >= thirty_days_ago
            )
        ).order_by(TestSession.started_at).all()
        
        # Create trend data
        session_trend = []
        for session in recent_sessions:
            detection_count = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).count()
            
            session_trend.append({
                "date": session.started_at.date().isoformat() if session.started_at else None,
                "session_name": session.name,
                "detection_count": detection_count,
                "status": session.status
            })
        
        dashboard_data = {
            "project_summary": summary.dict(),
            "session_trend": session_trend,
            "quick_stats": {
                "active_sessions": sum(1 for s in recent_sessions if s.status == "running"),
                "completed_today": sum(
                    1 for s in recent_sessions 
                    if s.completed_at and s.completed_at.date() == datetime.utcnow().date()
                ),
                "average_detections_per_session": (
                    summary.total_detections / summary.total_sessions
                    if summary.total_sessions > 0 else 0
                )
            },
            "charts_data": {
                "detection_types_pie": [
                    {"name": dtype, "value": count}
                    for dtype, count in summary.detection_type_breakdown.items()
                ],
                "success_rate_gauge": summary.overall_success_rate,
                "sessions_timeline": [
                    {
                        "date": s["started_at"][:10] if s["started_at"] else "Unknown",
                        "count": 1
                    }
                    for s in summary.recent_sessions
                ]
            }
        }
        
        return dashboard_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving dashboard data: {str(e)}"
        )

# Simple endpoint that returns all completed sessions regardless of project
@router.get("/completed", response_model=List[Dict[str, Any]])
async def get_completed_sessions(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all completed test sessions for the Results page
    This is a simpler endpoint that doesn't require project filtering
    """
    try:
        # Get all completed sessions with project info
        sessions = db.query(TestSession).options(
            joinedload(TestSession.project)
        ).filter(
            TestSession.status == "completed"
        ).order_by(desc(TestSession.completed_at)).limit(limit).all()
        
        session_results = []
        for session in sessions:
            # Get test results count
            test_results_count = db.query(TestResult).filter(
                TestResult.test_session_id == session.id
            ).count()
            
            # Get detection events count  
            detection_events_count = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).count()
            
            # Calculate basic metrics from detection events
            detection_events = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).all()
            
            passed_detections = sum(1 for d in detection_events if d.validation_result == "Pass")
            total_detections = len(detection_events)
            success_rate = (passed_detections / total_detections * 100) if total_detections > 0 else 0
            
            # Get test result metrics
            test_results = db.query(TestResult).filter(
                TestResult.test_session_id == session.id
            ).all()
            
            avg_accuracy = sum(r.accuracy for r in test_results if r.accuracy) / len(test_results) if test_results else None
            avg_precision = sum(r.precision for r in test_results if r.precision) / len(test_results) if test_results else None
            avg_recall = sum(r.recall for r in test_results if r.recall) / len(test_results) if test_results else None
            avg_f1 = sum(r.f1_score for r in test_results if r.f1_score) / len(test_results) if test_results else None
            
            session_data = {
                "session_id": session.id,
                "session_name": session.name,
                "project_id": session.project_id,
                "project_name": session.project.name if session.project else "Unknown Project",
                "status": session.status,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "test_results_count": test_results_count,
                "detection_events_count": detection_events_count,
                "has_results": test_results_count > 0 or detection_events_count > 0,
                "metrics": {
                    "success_rate": round(success_rate, 2),
                    "total_detections": total_detections,
                    "passed_detections": passed_detections,
                    "failed_detections": total_detections - passed_detections,
                    "accuracy": round(avg_accuracy * 100, 2) if avg_accuracy else None,
                    "precision": round(avg_precision * 100, 2) if avg_precision else None,
                    "recall": round(avg_recall * 100, 2) if avg_recall else None,
                    "f1_score": round(avg_f1 * 100, 2) if avg_f1 else None
                },
                "processing_time": (
                    (session.completed_at - session.started_at).total_seconds()
                    if session.started_at and session.completed_at else None
                )
            }
            
            session_results.append(session_data)
        
        logger.info(f"Retrieved {len(session_results)} completed test sessions")
        return session_results
        
    except Exception as e:
        logger.error(f"Error retrieving completed sessions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving completed sessions: {str(e)}"
        )

# Health check for results API
@router.get("/health", response_model=Dict[str, Any])
async def results_api_health():
    """Health check for enhanced results API"""
    return {
        "status": "healthy",
        "service": "Enhanced Results API",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Results API is operational and ready to serve detection data"
    }

# Export router
enhanced_results_router = router
__all__ = ["router", "enhanced_results_router"]