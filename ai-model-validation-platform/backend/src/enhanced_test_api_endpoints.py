"""
FastAPI endpoints for Enhanced Test Workflow system
Provides REST API for automated test execution with real-time WebSocket updates
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import json
import logging

from database import SessionLocal
from models import Project, Video
from src.enhanced_test_workflow_orchestrator import (
    enhanced_test_orchestrator,
    WorkflowConfiguration,
    WorkflowStatus,
    VideoStatus
)
from services.websocket_service import websocket_manager, handle_websocket_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/enhanced-test", tags=["Enhanced Test Workflow"])

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models for API requests/responses
class StartWorkflowRequest(BaseModel):
    """Request to start enhanced test workflow"""
    project_id: str = Field(..., description="Project ID to test")
    test_session_name: str = Field(..., description="Name for the test session")
    tolerance_ms: int = Field(100, description="Detection tolerance in milliseconds")
    
    # Processing options
    parallel_processing: bool = Field(False, description="Enable parallel video processing")
    max_parallel_videos: int = Field(3, description="Maximum parallel videos")
    retry_failed_videos: bool = Field(True, description="Retry failed videos")
    max_retries: int = Field(2, description="Maximum retry attempts")
    timeout_per_video: int = Field(300, description="Timeout per video in seconds")
    
    # Report options
    generate_individual_reports: bool = Field(True, description="Generate individual video reports")
    generate_aggregate_report: bool = Field(True, description="Generate aggregate report")
    include_visual_evidence: bool = Field(True, description="Include visual evidence")
    
    # Error handling
    continue_on_error: bool = Field(True, description="Continue processing on video errors")
    fail_fast: bool = Field(False, description="Fail entire workflow on first error")

class WorkflowResponse(BaseModel):
    """Workflow status response"""
    workflow_id: str
    status: str
    progress: Dict[str, Any]
    start_time: str
    video_count: int
    current_video: Optional[str] = None
    error_count: int

class VideoResultResponse(BaseModel):
    """Individual video test result"""
    video_id: str
    video_filename: str
    status: str
    processing_duration: Optional[float]
    total_detections: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: Optional[float]
    recall: Optional[float]
    f1_score: Optional[float]
    error_message: Optional[str]

class FinalReportResponse(BaseModel):
    """Final comprehensive test report"""
    workflow_id: str
    project_id: str
    test_session_name: str
    start_time: str
    end_time: str
    total_duration_seconds: float
    
    # Video summary
    total_videos: int
    completed_videos: int
    failed_videos: int
    success_rate: float
    
    # Overall metrics
    total_detections: int
    overall_precision: float
    overall_recall: float
    overall_f1_score: float
    overall_accuracy: float
    
    # Individual results
    individual_video_results: Dict[str, VideoResultResponse]
    error_log: List[Dict]

@router.post("/start-workflow", response_model=Dict[str, str])
async def start_enhanced_test_workflow(
    request: StartWorkflowRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start the complete enhanced test workflow
    Returns workflow_id for tracking progress
    """
    try:
        # Validate project exists
        project = db.query(Project).filter(Project.id == request.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check if project has videos
        video_count = db.query(Video).filter(
            Video.project_id == request.project_id,
            Video.status != "deleted"
        ).count()
        
        if video_count == 0:
            raise HTTPException(status_code=400, detail="No videos found in project")
        
        # Create workflow configuration
        config = WorkflowConfiguration(
            project_id=request.project_id,
            test_session_name=request.test_session_name,
            tolerance_ms=request.tolerance_ms,
            parallel_processing=request.parallel_processing,
            max_parallel_videos=request.max_parallel_videos,
            retry_failed_videos=request.retry_failed_videos,
            max_retries=request.max_retries,
            timeout_per_video=request.timeout_per_video,
            generate_individual_reports=request.generate_individual_reports,
            generate_aggregate_report=request.generate_aggregate_report,
            include_visual_evidence=request.include_visual_evidence,
            continue_on_error=request.continue_on_error,
            fail_fast=request.fail_fast
        )
        
        # Start the workflow
        workflow_id = await enhanced_test_orchestrator.start_enhanced_test_workflow(config)
        
        logger.info(f"Started enhanced test workflow {workflow_id} for project {request.project_id}")
        
        return {
            "workflow_id": workflow_id,
            "message": "Enhanced test workflow started successfully",
            "status": "started",
            "project_id": request.project_id,
            "estimated_videos": video_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start enhanced test workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")

@router.get("/workflow/{workflow_id}/status", response_model=WorkflowResponse)
async def get_workflow_status(workflow_id: str):
    """Get current status of a workflow"""
    try:
        status = enhanced_test_orchestrator.get_workflow_status(workflow_id)
        if not status:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        return WorkflowResponse(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.get("/workflow/{workflow_id}/results")
async def get_workflow_results(workflow_id: str):
    """Get detailed results for a completed workflow"""
    try:
        workflow_data = enhanced_test_orchestrator.active_workflows.get(workflow_id)
        if not workflow_data:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        if workflow_data["status"] not in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
            return {
                "workflow_id": workflow_id,
                "status": workflow_data["status"].value,
                "message": "Workflow not yet completed",
                "current_results": {
                    "completed_videos": len([
                        r for r in workflow_data["video_results"].values() 
                        if r.status == VideoStatus.COMPLETED
                    ]),
                    "total_videos": workflow_data["progress"].total_videos
                }
            }
        
        # Return final results if available
        if "final_results" in workflow_data:
            return workflow_data["final_results"]
        
        # Return current state if final results not generated yet
        return {
            "workflow_id": workflow_id,
            "status": workflow_data["status"].value,
            "video_results": {
                video_id: {
                    "video_filename": result.video_filename,
                    "status": result.status.value,
                    "metrics": {
                        "precision": result.precision,
                        "recall": result.recall,
                        "f1_score": result.f1_score,
                        "total_detections": result.total_detections
                    },
                    "error_message": result.error_message
                }
                for video_id, result in workflow_data["video_results"].items()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get results: {str(e)}")

@router.post("/workflow/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancel an active workflow"""
    try:
        success = enhanced_test_orchestrator.cancel_workflow(workflow_id)
        if not success:
            raise HTTPException(status_code=404, detail="Workflow not found or not cancellable")
        
        return {
            "workflow_id": workflow_id,
            "message": "Workflow cancelled successfully",
            "cancelled_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel: {str(e)}")

@router.get("/workflows", response_model=List[Dict])
async def list_workflows():
    """List all active workflows"""
    try:
        workflows = enhanced_test_orchestrator.list_active_workflows()
        return workflows
        
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list workflows: {str(e)}")

@router.get("/workflow/{workflow_id}/report/download")
async def download_workflow_report(
    workflow_id: str,
    report_type: str = Query("final", description="Report type: 'final' or video_id for individual")
):
    """Download generated workflow report"""
    try:
        workflow_data = enhanced_test_orchestrator.active_workflows.get(workflow_id)
        if not workflow_data:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        if report_type == "final":
            # Return final comprehensive report
            if workflow_data["status"] != WorkflowStatus.COMPLETED:
                raise HTTPException(status_code=400, detail="Workflow not completed")
            
            report_path = f"reports/final_reports/enhanced_test_workflow_{workflow_id}_final_report.json"
            
        else:
            # Return individual video report
            report_path = f"reports/individual_videos/video_{report_type}_test_report.json"
        
        # Check if file exists
        from pathlib import Path
        if not Path(report_path).exists():
            raise HTTPException(status_code=404, detail="Report file not found")
        
        return FileResponse(
            path=report_path,
            filename=Path(report_path).name,
            media_type='application/json'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download report: {str(e)}")

@router.get("/project/{project_id}/test-history")
async def get_project_test_history(
    project_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(50, description="Limit number of results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Get test history for a project"""
    try:
        # Validate project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get workflows from active memory (limited to current session)
        project_workflows = [
            {
                "workflow_id": workflow_id,
                "name": data["config"].test_session_name,
                "status": data["status"].value,
                "start_time": data["start_time"].isoformat(),
                "total_videos": data["progress"].total_videos,
                "completed_videos": data["progress"].completed_videos,
                "failed_videos": data["progress"].failed_videos
            }
            for workflow_id, data in enhanced_test_orchestrator.active_workflows.items()
            if data["config"].project_id == project_id
        ]
        
        # Sort by start time (most recent first)
        project_workflows.sort(key=lambda x: x["start_time"], reverse=True)
        
        return {
            "project_id": project_id,
            "project_name": project.name,
            "workflows": project_workflows[offset:offset+limit],
            "total_count": len(project_workflows)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project test history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")

# WebSocket endpoints for real-time updates
@router.websocket("/workflow/{workflow_id}/ws")
async def workflow_websocket_endpoint(websocket: WebSocket, workflow_id: str):
    """WebSocket endpoint for real-time workflow updates"""
    try:
        # Handle WebSocket connection with room subscription
        await handle_websocket_connection(
            websocket=websocket,
            connection_type="workflow_monitoring",
            room_id=f"workflow_{workflow_id}"
        )
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected from workflow {workflow_id}")
    except Exception as e:
        logger.error(f"WebSocket error for workflow {workflow_id}: {e}")

@router.websocket("/ws/general")
async def general_websocket_endpoint(websocket: WebSocket):
    """General WebSocket endpoint for system-wide updates"""
    try:
        await handle_websocket_connection(
            websocket=websocket,
            connection_type="general_monitoring"
        )
        
    except WebSocketDisconnect:
        logger.info("General WebSocket disconnected")
    except Exception as e:
        logger.error(f"General WebSocket error: {e}")

# Testing endpoints for development
@router.post("/test/mock-workflow")
async def create_mock_workflow(project_id: str, video_count: int = 3):
    """Create a mock workflow for testing (development only)"""
    try:
        from unittest.mock import MagicMock
        
        # Create mock configuration
        config = WorkflowConfiguration(
            project_id=project_id,
            test_session_name=f"Mock Test {datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            tolerance_ms=100
        )
        
        # Start mock workflow
        workflow_id = await enhanced_test_orchestrator.start_enhanced_test_workflow(config)
        
        return {
            "workflow_id": workflow_id,
            "message": "Mock workflow created for testing",
            "project_id": project_id,
            "mock_video_count": video_count
        }
        
    except Exception as e:
        logger.error(f"Failed to create mock workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create mock: {str(e)}")

# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check for enhanced test workflow system"""
    try:
        active_workflow_count = len(enhanced_test_orchestrator.active_workflows)
        
        return {
            "status": "healthy",
            "service": "Enhanced Test Workflow",
            "timestamp": datetime.utcnow().isoformat(),
            "active_workflows": active_workflow_count,
            "websocket_connections": websocket_manager.get_connection_count(),
            "version": "1.0.0"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")