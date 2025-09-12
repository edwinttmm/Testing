"""
Comprehensive Results API - Enhanced endpoint for displaying complete detection results
Provides detailed results page data with analytics, comparisons, and recommendations
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from services.detection_results_service import DetectionResultsService
from services.results_data_population_service import ResultsDataPopulationService
from models import TestSession, DetectionEvent, DetectionComparison, TestResult
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/results", tags=["Comprehensive Results"])

@router.get("/test-session/{session_id}")
async def get_comprehensive_test_session_results(
    session_id: str,
    include_analytics: bool = Query(default=True, description="Include detailed analytics"),
    include_recommendations: bool = Query(default=True, description="Include recommendations"),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive results for a test session with complete detection analysis
    
    This endpoint provides:
    - Complete test session details
    - All detection events with LabJack signal data
    - Detection comparisons with timing analysis
    - Test results with statistical analysis
    - Performance analytics and recommendations
    """
    try:
        results_service = DetectionResultsService(db)
        comprehensive_results = results_service.get_comprehensive_test_results(session_id)
        
        if "error" in comprehensive_results:
            raise HTTPException(status_code=404, detail=comprehensive_results["error"])
        
        # Filter results based on query parameters
        if not include_analytics:
            comprehensive_results.pop("analytics", None)
        
        if not include_recommendations:
            if "analytics" in comprehensive_results:
                comprehensive_results["analytics"].pop("recommendations", None)
        
        return {
            "status": "success",
            "session_id": session_id,
            "data": comprehensive_results,
            "metadata": {
                "generated_at": "2025-01-05T14:30:00Z",
                "includes_analytics": include_analytics,
                "includes_recommendations": include_recommendations
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting comprehensive results for session {session_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve comprehensive results: {str(e)}"
        )

@router.get("/test-sessions")
async def list_test_sessions_with_results(
    project_id: Optional[str] = Query(default=None, description="Filter by project ID"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    limit: int = Query(default=50, description="Maximum number of sessions to return"),
    offset: int = Query(default=0, description="Number of sessions to skip"),
    auto_populate: bool = Query(default=True, description="Auto-populate missing results data"),
    db: Session = Depends(get_db)
):
    """
    List test sessions with summary results data
    
    Provides a paginated list of test sessions with basic result summaries
    """
    try:
        # Auto-populate missing results data if requested
        if auto_populate:
            try:
                population_service = ResultsDataPopulationService(db)
                backfill_status = population_service.get_backfill_status()
                if backfill_status.get("sessions_needing_backfill", 0) > 0:
                    logger.info(f"Auto-populating results data for {backfill_status['sessions_needing_backfill']} sessions")
                    population_service.backfill_all_sessions()
            except Exception as e:
                logger.warning(f"Failed to auto-populate results data: {e}")
        
        # Build query with filters
        query = db.query(TestSession).order_by(TestSession.created_at.desc())
        
        if project_id:
            query = query.filter(TestSession.project_id == project_id)
        
        if status:
            query = query.filter(TestSession.status == status)
        
        # Get total count for pagination
        total_count = query.count()
        
        # Apply pagination
        sessions = query.offset(offset).limit(limit).all()
        
        # Build session summaries with result counts
        session_summaries = []
        for session in sessions:
            # Get quick result counts
            detection_count = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).count()
            
            comparison_count = db.query(DetectionComparison).filter(
                DetectionComparison.test_session_id == session.id
            ).count()
            
            result_count = db.query(TestResult).filter(
                TestResult.test_session_id == session.id
            ).count()
            
            # Get actual metrics from test results if available
            test_result = db.query(TestResult).filter(
                TestResult.test_session_id == session.id
            ).first()
            
            if test_result:
                success_rate = (test_result.precision or 0) * 100
                overall_status = "PASS" if success_rate >= 80 else "FAIL" if success_rate > 0 else "NO_DATA"
                has_data = True
            else:
                # Fall back to detection event analysis
                successful_detections = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == session.id,
                    DetectionEvent.validation_result == "TP"
                ).count()
                
                success_rate = (successful_detections / detection_count * 100) if detection_count > 0 else 0
                overall_status = "NO_DATA" if detection_count == 0 else ("PASS" if success_rate >= 80 else "FAIL")
                has_data = detection_count > 0
            
            session_summary = {
                "id": session.id,
                "name": session.name,
                "project_id": session.project_id,
                "video_id": session.video_id,
                "status": session.status,
                "tolerance_ms": session.tolerance_ms,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "duration_seconds": (
                    (session.completed_at - session.started_at).total_seconds() 
                    if session.completed_at and session.started_at else None
                ),
                "result_summary": {
                    "detection_events": detection_count,
                    "comparisons": comparison_count,
                    "test_results": result_count,
                    "success_rate_percentage": round(success_rate, 1),
                    "overall_status": overall_status,
                    "has_results_data": has_data,
                    "precision": round(test_result.precision * 100, 1) if test_result and test_result.precision else 0,
                    "recall": round(test_result.recall * 100, 1) if test_result and test_result.recall else 0,
                    "f1_score": round(test_result.f1_score * 100, 1) if test_result and test_result.f1_score else 0
                }
            }
            
            session_summaries.append(session_summary)
        
        return {
            "status": "success",
            "data": {
                "sessions": session_summaries,
                "pagination": {
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total_count
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error listing test sessions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve test sessions: {str(e)}"
        )

@router.get("/detection-events/{session_id}")
async def get_detection_events_detailed(
    session_id: str,
    include_signal_data: bool = Query(default=True, description="Include LabJack signal data"),
    validation_result: Optional[str] = Query(default=None, description="Filter by validation result (TP, FP, FN)"),
    db: Session = Depends(get_db)
):
    """
    Get detailed detection events for a specific test session
    
    Provides enhanced detection event data with LabJack signal information
    """
    try:
        # Verify session exists
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Build detection events query
        query = db.query(DetectionEvent).filter(DetectionEvent.test_session_id == session_id)
        
        if validation_result:
            query = query.filter(DetectionEvent.validation_result == validation_result)
        
        detection_events = query.all()
        
        # Format detection events with enhanced data
        results_service = DetectionResultsService(db)
        formatted_events = results_service._format_detection_events(detection_events)
        
        # Filter signal data if not requested
        if not include_signal_data:
            for event in formatted_events:
                event.pop("signal_data", None)
        
        return {
            "status": "success",
            "session_id": session_id,
            "data": {
                "detection_events": formatted_events,
                "summary": {
                    "total_events": len(formatted_events),
                    "by_validation_result": {
                        "TP": len([e for e in formatted_events if e["validation_result"] == "TP"]),
                        "FP": len([e for e in formatted_events if e["validation_result"] == "FP"]),
                        "FN": len([e for e in formatted_events if e["validation_result"] == "FN"])
                    },
                    "by_class_label": {}
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting detection events for session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve detection events: {str(e)}"
        )

@router.get("/comparisons/{session_id}")
async def get_detection_comparisons_detailed(
    session_id: str,
    include_timing_analysis: bool = Query(default=True, description="Include detailed timing analysis"),
    match_type: Optional[str] = Query(default=None, description="Filter by match type (TP, FP, FN)"),
    db: Session = Depends(get_db)
):
    """
    Get detailed detection comparisons for a specific test session
    
    Provides enhanced comparison data with timing and quality analysis
    """
    try:
        # Verify session exists
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Build comparisons query
        query = db.query(DetectionComparison).filter(DetectionComparison.test_session_id == session_id)
        
        if match_type:
            query = query.filter(DetectionComparison.match_type == match_type)
        
        comparisons = query.all()
        
        # Format comparisons with enhanced data
        results_service = DetectionResultsService(db)
        formatted_comparisons = results_service._format_detection_comparisons(comparisons)
        
        # Filter timing analysis if not requested
        if not include_timing_analysis:
            for comp in formatted_comparisons:
                comp.pop("timing_analysis", None)
        
        return {
            "status": "success",
            "session_id": session_id,
            "data": {
                "detection_comparisons": formatted_comparisons,
                "summary": {
                    "total_comparisons": len(formatted_comparisons),
                    "by_match_type": {
                        "TP": len([c for c in formatted_comparisons if c["match_type"] == "TP"]),
                        "FP": len([c for c in formatted_comparisons if c["match_type"] == "FP"]),
                        "FN": len([c for c in formatted_comparisons if c["match_type"] == "FN"])
                    },
                    "timing_statistics": {
                        "average_offset_ms": sum([
                            c["temporal_offset_ms"] for c in formatted_comparisons 
                            if c["temporal_offset_ms"] is not None
                        ]) / len([
                            c for c in formatted_comparisons 
                            if c["temporal_offset_ms"] is not None
                        ]) if any(c["temporal_offset_ms"] is not None for c in formatted_comparisons) else 0,
                        "within_tolerance": len([
                            c for c in formatted_comparisons 
                            if c["timing_analysis"] and c["timing_analysis"]["is_within_tolerance"]
                        ]) if include_timing_analysis else 0
                    }
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting detection comparisons for session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve detection comparisons: {str(e)}"
        )

@router.get("/analytics/{session_id}")
async def get_session_analytics(
    session_id: str,
    include_recommendations: bool = Query(default=True, description="Include recommendations"),
    db: Session = Depends(get_db)
):
    """
    Get detailed analytics for a test session
    
    Provides comprehensive performance analytics and insights
    """
    try:
        results_service = DetectionResultsService(db)
        comprehensive_results = results_service.get_comprehensive_test_results(session_id)
        
        if "error" in comprehensive_results:
            raise HTTPException(status_code=404, detail=comprehensive_results["error"])
        
        analytics = comprehensive_results.get("analytics", {})
        summary = comprehensive_results.get("summary", {})
        
        if not include_recommendations:
            analytics.pop("recommendations", None)
        
        return {
            "status": "success",
            "session_id": session_id,
            "data": {
                "analytics": analytics,
                "executive_summary": summary
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting analytics for session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve analytics: {str(e)}"
        )

@router.get("/export/{session_id}")
async def export_session_results(
    session_id: str,
    format: str = Query(default="json", description="Export format (json, csv)"),
    include_raw_data: bool = Query(default=False, description="Include raw database records"),
    db: Session = Depends(get_db)
):
    """
    Export comprehensive test session results in various formats
    
    Provides data export functionality for reporting and analysis
    """
    try:
        results_service = DetectionResultsService(db)
        comprehensive_results = results_service.get_comprehensive_test_results(session_id)
        
        if "error" in comprehensive_results:
            raise HTTPException(status_code=404, detail=comprehensive_results["error"])
        
        if format.lower() == "json":
            return {
                "status": "success",
                "session_id": session_id,
                "export_format": "json",
                "data": comprehensive_results,
                "metadata": {
                    "exported_at": "2025-01-05T14:30:00Z",
                    "includes_raw_data": include_raw_data
                }
            }
        elif format.lower() == "csv":
            # For CSV export, we would typically return a file response
            # For now, return a structured format that can be converted to CSV
            return {
                "status": "success",
                "session_id": session_id,
                "export_format": "csv",
                "message": "CSV export format not yet implemented",
                "suggestion": "Use JSON format for now"
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported export format: {format}")
        
    except Exception as e:
        logger.error(f"Error exporting results for session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export results: {str(e)}"
        )

@router.post("/backfill/all")
async def backfill_all_results_data(db: Session = Depends(get_db)):
    """
    Backfill missing results data for all sessions
    
    Creates missing DetectionComparison and TestResult records for existing sessions
    """
    try:
        population_service = ResultsDataPopulationService(db)
        results = population_service.backfill_all_sessions()
        
        return {
            "status": "success",
            "message": "Results data backfill completed",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error backfilling results data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to backfill results data: {str(e)}"
        )

@router.post("/backfill/session/{session_id}")
async def backfill_session_results_data(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Backfill missing results data for a specific session
    
    Creates missing DetectionComparison and TestResult records for the specified session
    """
    try:
        population_service = ResultsDataPopulationService(db)
        results = population_service.backfill_session_data(session_id)
        
        return {
            "status": "success",
            "session_id": session_id,
            "message": "Session results data backfill completed",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error backfilling session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to backfill session results: {str(e)}"
        )

@router.get("/backfill/status")
async def get_backfill_status(db: Session = Depends(get_db)):
    """
    Get the status of results data backfill requirements
    
    Shows which sessions need results data populated
    """
    try:
        population_service = ResultsDataPopulationService(db)
        status = population_service.get_backfill_status()
        
        return {
            "status": "success",
            "backfill_status": status
        }
        
    except Exception as e:
        logger.error(f"Error getting backfill status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get backfill status: {str(e)}"
        )