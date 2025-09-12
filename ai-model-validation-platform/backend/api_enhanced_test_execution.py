"""
Enhanced Test Execution API - REST endpoints for the enhanced test workflow orchestrator
Provides endpoints to start, monitor, and control enhanced test workflows
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
from typing import Optional, Dict, Any
import logging
from pydantic import BaseModel, Field

from src.enhanced_test_workflow_orchestrator import (
    enhanced_test_orchestrator,
    WorkflowConfiguration,
    WorkflowStatus
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enhanced-test-execution", tags=["Enhanced Test Execution"])

# Pydantic models for request/response

class WorkflowConfigurationRequest(BaseModel):
    """Request model for starting an enhanced test workflow"""
    project_id: str = Field(..., description="ID of the project to test")
    test_session_name: str = Field(..., description="Name for the test session")
    tolerance_ms: int = Field(default=100, description="Tolerance in milliseconds for detection matching")
    parallel_processing: bool = Field(default=False, description="Enable parallel video processing")
    max_parallel_videos: int = Field(default=3, description="Maximum number of videos to process in parallel")
    retry_failed_videos: bool = Field(default=True, description="Retry failed videos")
    max_retries: int = Field(default=2, description="Maximum number of retries for failed videos")
    timeout_per_video: int = Field(default=300, description="Timeout per video in seconds")
    generate_individual_reports: bool = Field(default=True, description="Generate individual video reports")
    generate_aggregate_report: bool = Field(default=True, description="Generate aggregate report")
    include_visual_evidence: bool = Field(default=True, description="Include visual evidence in reports")
    continue_on_error: bool = Field(default=True, description="Continue processing other videos on error")
    fail_fast: bool = Field(default=False, description="Stop processing on first error")

class WorkflowStartResponse(BaseModel):
    """Response model for workflow start"""
    status: str
    workflow_id: str
    message: str

class WorkflowStatusResponse(BaseModel):
    """Response model for workflow status"""
    workflow_id: str
    status: str
    progress: Dict[str, Any]
    start_time: str
    video_count: int
    current_video: Optional[str]
    error_count: int

class WorkflowListResponse(BaseModel):
    """Response model for listing active workflows"""
    status: str
    active_workflows: list

@router.post("/start-workflow", response_model=WorkflowStartResponse)
async def start_enhanced_test_workflow(
    config: WorkflowConfigurationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start a new enhanced test workflow
    
    This endpoint initiates a comprehensive test workflow that will:
    - Load all videos from the specified project
    - Process each video through the detection pipeline
    - Compare results with ground truth data
    - Generate detailed reports and analytics
    """
    try:
        # Convert Pydantic model to WorkflowConfiguration
        workflow_config = WorkflowConfiguration(
            project_id=config.project_id,
            test_session_name=config.test_session_name,
            tolerance_ms=config.tolerance_ms,
            parallel_processing=config.parallel_processing,
            max_parallel_videos=config.max_parallel_videos,
            retry_failed_videos=config.retry_failed_videos,
            max_retries=config.max_retries,
            timeout_per_video=config.timeout_per_video,
            generate_individual_reports=config.generate_individual_reports,
            generate_aggregate_report=config.generate_aggregate_report,
            include_visual_evidence=config.include_visual_evidence,
            continue_on_error=config.continue_on_error,
            fail_fast=config.fail_fast
        )
        
        # Start the workflow
        workflow_id = await enhanced_test_orchestrator.start_enhanced_test_workflow(workflow_config)
        
        logger.info(f"Started enhanced test workflow {workflow_id} for project {config.project_id}")
        
        return WorkflowStartResponse(
            status="success",
            workflow_id=workflow_id,
            message=f"Enhanced test workflow started successfully. Track progress with workflow ID: {workflow_id}"
        )
        
    except Exception as e:
        logger.error(f"Failed to start enhanced test workflow: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start enhanced test workflow: {str(e)}"
        )

@router.get("/workflow-status/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str):
    """
    Get the current status and progress of a workflow
    
    Returns detailed information about workflow progress including:
    - Current status (initializing, processing, completed, etc.)
    - Progress percentage and statistics
    - Current video being processed
    - Error count and basic error information
    """
    try:
        workflow_status = enhanced_test_orchestrator.get_workflow_status(workflow_id)
        
        if not workflow_status:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow {workflow_id} not found"
            )
        
        return WorkflowStatusResponse(**workflow_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow status for {workflow_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workflow status: {str(e)}"
        )

@router.post("/workflow-cancel/{workflow_id}")
async def cancel_workflow(workflow_id: str):
    """
    Cancel an active workflow
    
    Attempts to gracefully cancel a running workflow. Videos currently being
    processed will complete, but no new videos will be started.
    """
    try:
        success = enhanced_test_orchestrator.cancel_workflow(workflow_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow {workflow_id} not found or cannot be cancelled"
            )
        
        return {
            "status": "success",
            "workflow_id": workflow_id,
            "message": "Workflow cancellation requested"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel workflow: {str(e)}"
        )

@router.get("/active-workflows", response_model=WorkflowListResponse)
async def list_active_workflows():
    """
    List all currently active workflows
    
    Returns a list of all workflows that are currently running, including
    their basic status information.
    """
    try:
        active_workflows = enhanced_test_orchestrator.list_active_workflows()
        
        return WorkflowListResponse(
            status="success",
            active_workflows=active_workflows
        )
        
    except Exception as e:
        logger.error(f"Error listing active workflows: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list active workflows: {str(e)}"
        )

@router.get("/workflow-results/{workflow_id}")
async def get_workflow_results(workflow_id: str):
    """
    Get the final results of a completed workflow
    
    Returns comprehensive results including:
    - Overall performance metrics
    - Individual video results
    - Error logs and debugging information
    - Generated reports and analysis
    """
    try:
        workflow_status = enhanced_test_orchestrator.get_workflow_status(workflow_id)
        
        if not workflow_status:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow {workflow_id} not found"
            )
        
        # Get the full workflow data
        workflow_data = enhanced_test_orchestrator.active_workflows.get(workflow_id)
        
        if not workflow_data:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow data not found for {workflow_id}"
            )
        
        # Check if workflow is completed
        if workflow_data["status"] not in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
            raise HTTPException(
                status_code=409,
                detail=f"Workflow {workflow_id} is not completed yet. Current status: {workflow_data['status'].value}"
            )
        
        # Return comprehensive results
        results = {
            "status": "success",
            "workflow_id": workflow_id,
            "workflow_status": workflow_data["status"].value,
            "final_results": workflow_data.get("final_results", {}),
            "video_results": {
                video_id: {
                    "video_filename": result.video_filename,
                    "status": result.status.value,
                    "processing_duration": result.processing_duration,
                    "metrics": {
                        "total_detections": result.total_detections,
                        "true_positives": result.true_positives,
                        "false_positives": result.false_positives,
                        "false_negatives": result.false_negatives,
                        "precision": result.precision,
                        "recall": result.recall,
                        "f1_score": result.f1_score
                    },
                    "error_message": result.error_message,
                    "start_time": result.start_time.isoformat() if result.start_time else None,
                    "end_time": result.end_time.isoformat() if result.end_time else None
                }
                for video_id, result in workflow_data["video_results"].items()
            },
            "error_log": workflow_data.get("error_log", []),
            "workflow_duration": workflow_data.get("duration", 0),
            "start_time": workflow_data["start_time"].isoformat(),
            "end_time": workflow_data.get("end_time", "").isoformat() if workflow_data.get("end_time") else None
        }
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow results for {workflow_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workflow results: {str(e)}"
        )

@router.get("/workflow-logs/{workflow_id}")
async def get_workflow_logs(workflow_id: str):
    """
    Get detailed logs and debugging information for a workflow
    
    Returns comprehensive logging information including:
    - Error logs with timestamps
    - Processing logs for each video
    - Performance metrics and timing data
    """
    try:
        workflow_data = enhanced_test_orchestrator.active_workflows.get(workflow_id)
        
        if not workflow_data:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow {workflow_id} not found"
            )
        
        logs_data = {
            "status": "success",
            "workflow_id": workflow_id,
            "error_log": workflow_data.get("error_log", []),
            "workflow_status": workflow_data["status"].value,
            "start_time": workflow_data["start_time"].isoformat(),
            "progress_summary": workflow_data["progress"].__dict__,
            "video_status_summary": {
                video_id: {
                    "filename": result.video_filename,
                    "status": result.status.value,
                    "error_message": result.error_message,
                    "processing_duration": result.processing_duration
                }
                for video_id, result in workflow_data["video_results"].items()
            }
        }
        
        return logs_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow logs for {workflow_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workflow logs: {str(e)}"
        )

@router.get("/health")
async def enhanced_test_execution_health():
    """
    Health check endpoint for the enhanced test execution service
    """
    try:
        active_workflow_count = len(enhanced_test_orchestrator.active_workflows)
        
        return {
            "status": "healthy",
            "service": "enhanced-test-execution",
            "active_workflows": active_workflow_count,
            "orchestrator_initialized": enhanced_test_orchestrator is not None
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "enhanced-test-execution",
            "error": str(e)
        }

# Export the router for main.py to import
enhanced_test_execution_router = router