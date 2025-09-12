"""
Results Integration API - Fixed endpoints for detection results storage and display
Addresses monitoring failures and empty results page issues
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
import logging
import json
from datetime import datetime

from database import get_db
from models import TestSession, DetectionEvent, DetectionComparison, TestResult, Project, Video
from services.results_storage_pipeline_service import results_storage_service
from services.websocket_service import websocket_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/results", tags=["results"])

# Initialize results service with database dependency
def get_results_service(db: Session = Depends(get_db)):
    """Get initialized results service"""
    results_storage_service.set_db(db)
    return results_storage_service

@router.post("/test-sessions/start")
async def start_test_session(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    service = Depends(get_results_service)
):
    """Start a new test session with monitoring"""
    try:
        project_id = request.get("project_id")
        video_id = request.get("video_id")
        session_name = request.get("session_name")
        tolerance_ms = request.get("tolerance_ms", 100)
        
        if not project_id or not video_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="project_id and video_id are required"
            )
        
        result = await service.start_test_session_monitoring(
            project_id=project_id,
            video_id=video_id,
            test_session_name=session_name,
            tolerance_ms=tolerance_ms
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to start test session")
            )
        
        return {
            "success": True,
            "test_session_id": result["test_session_id"],
            "monitoring_active": result["monitoring_active"],
            "message": "Test session started successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting test session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start test session: {str(e)}"
        )

@router.post("/test-sessions/{test_session_id}/detections")
async def record_detection_event(
    test_session_id: str,
    detection_data: Dict[str, Any],
    service = Depends(get_results_service)
):
    """Record a detection event during video processing"""
    try:
        # Extract detection parameters
        video_timestamp = detection_data.get("timestamp", 0.0)
        frame_number = detection_data.get("frame_number")
        
        result = await service.process_detection_event(
            test_session_id=test_session_id,
            detection_data=detection_data,
            video_timestamp=video_timestamp,
            frame_number=frame_number
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to process detection event")
            )
        
        return {
            "success": True,
            "detection_event_id": result["detection_event_id"],
            "timestamp": result["timestamp"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording detection event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record detection event: {str(e)}"
        )

@router.post("/test-sessions/{test_session_id}/finalize")
async def finalize_test_session(
    test_session_id: str,
    request: Optional[Dict[str, Any]] = None,
    service = Depends(get_results_service)
):
    """Finalize test session and generate results"""
    try:
        force_completion = False
        if request:
            force_completion = request.get("force_completion", False)
        
        result = await service.finalize_test_session(
            test_session_id=test_session_id,
            force_completion=force_completion
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to finalize test session")
            )
        
        return {
            "success": True,
            "test_session_id": result["test_session_id"],
            "test_results": result["test_results"],
            "message": "Test session finalized successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finalizing test session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to finalize test session: {str(e)}"
        )

@router.get("/test-sessions/{test_session_id}")
async def get_test_session_results(
    test_session_id: str,
    service = Depends(get_results_service)
):
    """Get comprehensive results for a test session"""
    try:
        results = await service.get_test_session_results(test_session_id)
        
        if "error" in results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=results["error"]
            )
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting test session results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get test session results: {str(e)}"
        )

@router.get("/projects/{project_id}/summary")
async def get_project_results_summary(
    project_id: str,
    service = Depends(get_results_service)
):
    """Get results summary for all sessions in a project"""
    try:
        summary = await service.get_project_results_summary(project_id)
        
        if "error" in summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=summary["error"]
            )
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project results summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project results summary: {str(e)}"
        )

@router.get("/test-sessions")
async def list_test_sessions(
    project_id: Optional[str] = None,
    video_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List test sessions with filtering"""
    try:
        query = db.query(TestSession)
        
        # Apply filters
        if project_id:
            query = query.filter(TestSession.project_id == project_id)
        if video_id:
            query = query.filter(TestSession.video_id == video_id)
        if status_filter:
            query = query.filter(TestSession.status == status_filter)
        
        # Only show user-created sessions (filter out phantom detection sessions)
        query = query.filter(TestSession.session_type == "user_created")
        
        sessions = query.offset(skip).limit(limit).all()
        
        # Format response with additional data
        session_list = []
        for session in sessions:
            # Get related project and video info
            project = db.query(Project).filter(Project.id == session.project_id).first()
            video = db.query(Video).filter(Video.id == session.video_id).first()
            
            # Get detection and result counts
            detection_count = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).count()
            
            test_result = db.query(TestResult).filter(
                TestResult.test_session_id == session.id
            ).first()
            
            session_data = {
                "id": session.id,
                "name": session.name,
                "project_id": session.project_id,
                "project_name": project.name if project else "Unknown Project",
                "video_id": session.video_id,
                "video_name": video.filename if video else "Unknown Video",
                "status": session.status,
                "tolerance_ms": session.tolerance_ms,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "detection_count": detection_count,
                "has_results": test_result is not None,
                "accuracy": test_result.accuracy if test_result else None
            }
            
            session_list.append(session_data)
        
        return {
            "sessions": session_list,
            "total": len(session_list),
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Error listing test sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list test sessions: {str(e)}"
        )

@router.get("/detection-events/{detection_event_id}")
async def get_detection_event_details(
    detection_event_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific detection event"""
    try:
        detection_event = db.query(DetectionEvent).filter(
            DetectionEvent.id == detection_event_id
        ).first()
        
        if not detection_event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Detection event not found"
            )
        
        # Get related comparison
        comparison = db.query(DetectionComparison).filter(
            DetectionComparison.detection_event_id == detection_event_id
        ).first()
        
        return {
            "detection_event": {
                "id": detection_event.id,
                "test_session_id": detection_event.test_session_id,
                "timestamp": detection_event.timestamp,
                "confidence": detection_event.confidence,
                "class_label": detection_event.class_label,
                "validation_result": detection_event.validation_result,
                "frame_number": detection_event.frame_number,
                "processing_time_ms": detection_event.processing_time_ms,
                "bounding_box": {
                    "x": detection_event.bounding_box_x,
                    "y": detection_event.bounding_box_y,
                    "width": detection_event.bounding_box_width,
                    "height": detection_event.bounding_box_height
                } if detection_event.bounding_box_x is not None else None,
                "visual_evidence": {
                    "screenshot_path": detection_event.screenshot_path,
                    "screenshot_zoom_path": detection_event.screenshot_zoom_path
                } if detection_event.screenshot_path else None,
                "metadata": json.loads(detection_event.metadata) if detection_event.metadata else {}
            },
            "comparison": {
                "id": comparison.id,
                "match_type": comparison.match_type,
                "iou_score": comparison.iou_score,
                "temporal_offset": comparison.temporal_offset,
                "temporal_offset_ms": comparison.temporal_offset * 1000 if comparison.temporal_offset else None,
                "notes": comparison.notes
            } if comparison else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detection event details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get detection event details: {str(e)}"
        )

@router.get("/monitoring/status")
async def get_monitoring_status(service = Depends(get_results_service)):
    """Get current monitoring status"""
    try:
        # Get active monitoring sessions
        active_sessions = list(service.monitoring_sessions.keys())
        
        status_info = {
            "active_sessions": len(active_sessions),
            "sessions": []
        }
        
        for session_id in active_sessions:
            session_info = service.monitoring_sessions[session_id]
            status_info["sessions"].append({
                "test_session_id": session_id,
                "project_id": session_info["project_id"],
                "video_id": session_info["video_id"],
                "started_at": session_info["started_at"].isoformat(),
                "monitoring_active": session_info["monitoring_active"],
                "detection_count": session_info["detection_count"]
            })
        
        return status_info
        
    except Exception as e:
        logger.error(f"Error getting monitoring status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get monitoring status: {str(e)}"
        )

# Legacy compatibility endpoints for existing frontend
@router.get("/test-sessions/{test_session_id}/results")
async def get_legacy_test_results(
    test_session_id: str,
    service = Depends(get_results_service)
):
    """Legacy endpoint for test results (redirects to new format)"""
    return await get_test_session_results(test_session_id, service)

@router.post("/sessions/{test_session_id}/detection-events") 
async def legacy_record_detection(
    test_session_id: str,
    detection_data: Dict[str, Any],
    service = Depends(get_results_service)
):
    """Legacy endpoint for detection recording"""
    return await record_detection_event(test_session_id, detection_data, service)