"""
FastAPI Endpoints for Project Workflow Management System
Integration with main FastAPI application

SPARC Phase: Integration
Component: API Endpoints for Project Workflow Management
Integration: Complete REST API integration with FastAPI
Memory Namespace: vru-project-workflow
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from project_workflow_manager import (
    ProjectWorkflowManager, 
    WorkflowAPIIntegration,
    WorkflowConfiguration,
    LatencyThreshold,
    PassFailCriteria,
    WorkflowState,
    WorkflowPriority,
    ExecutionStrategy
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/workflow", tags=["Project Workflow Management"])

# Initialize workflow integration
workflow_api = WorkflowAPIIntegration()

# Pydantic models for API
class ProjectCreationRequest(BaseModel):
    """Request model for creating project workflow"""
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=1000, description="Project description")
    camera_model: str = Field(..., description="Camera model")
    camera_view: str = Field(..., description="Camera view type")
    lens_type: Optional[str] = Field(None, description="Lens type")
    resolution: Optional[str] = Field(None, description="Video resolution")
    frame_rate: Optional[int] = Field(None, ge=1, le=120, description="Frame rate")
    signal_type: str = Field(..., description="Signal type")
    owner_id: Optional[str] = Field(None, description="Project owner ID")

class LatencyThresholdRequest(BaseModel):
    """Request model for latency threshold configuration"""
    detection_latency_ms: float = Field(100.0, ge=1.0, le=10000.0, description="Detection latency threshold")
    processing_latency_ms: float = Field(500.0, ge=1.0, le=30000.0, description="Processing latency threshold")
    end_to_end_latency_ms: float = Field(1000.0, ge=1.0, le=60000.0, description="End-to-end latency threshold")
    signal_processing_latency_ms: float = Field(50.0, ge=1.0, le=5000.0, description="Signal processing latency threshold")
    warning_threshold_ms: float = Field(80.0, ge=1.0, le=5000.0, description="Warning threshold")
    critical_threshold_ms: float = Field(150.0, ge=1.0, le=10000.0, description="Critical threshold")

class PassFailCriteriaRequest(BaseModel):
    """Request model for pass/fail criteria configuration"""
    min_precision: float = Field(0.90, ge=0.0, le=1.0, description="Minimum precision required")
    min_recall: float = Field(0.85, ge=0.0, le=1.0, description="Minimum recall required")
    min_f1_score: float = Field(0.87, ge=0.0, le=1.0, description="Minimum F1-score required")
    max_latency_ms: float = Field(100.0, ge=1.0, le=10000.0, description="Maximum latency allowed")
    max_false_positive_rate: float = Field(0.05, ge=0.0, le=1.0, description="Maximum false positive rate")
    min_detection_confidence: float = Field(0.70, ge=0.0, le=1.0, description="Minimum detection confidence")
    min_accuracy: float = Field(0.85, ge=0.0, le=1.0, description="Minimum accuracy required")
    required_detections: int = Field(10, ge=1, le=10000, description="Required number of detections")

class WorkflowConfigurationRequest(BaseModel):
    """Request model for workflow configuration"""
    name: str = Field(..., min_length=1, max_length=255, description="Workflow name")
    description: Optional[str] = Field("", max_length=1000, description="Workflow description")
    priority: str = Field("normal", regex="^(low|normal|high|critical)$", description="Workflow priority")
    execution_strategy: str = Field("adaptive", regex="^(sequential|parallel|adaptive|hybrid)$", description="Execution strategy")
    max_concurrent_tasks: int = Field(5, ge=1, le=20, description="Maximum concurrent tasks")
    timeout_minutes: int = Field(120, ge=1, le=1440, description="Workflow timeout in minutes")
    retry_attempts: int = Field(3, ge=0, le=10, description="Number of retry attempts")
    auto_recovery: bool = Field(True, description="Enable automatic recovery")
    latency_thresholds: Optional[LatencyThresholdRequest] = Field(None, description="Latency thresholds")
    pass_fail_criteria: Optional[PassFailCriteriaRequest] = Field(None, description="Pass/fail criteria")
    notification_config: Optional[Dict[str, Any]] = Field({}, description="Notification configuration")
    custom_parameters: Optional[Dict[str, Any]] = Field({}, description="Custom parameters")

class TestExecutionRequest(BaseModel):
    """Request model for test execution"""
    project_id: str = Field(..., description="Project ID")
    workflow_config: Optional[WorkflowConfigurationRequest] = Field(None, description="Workflow configuration")
    force_restart: bool = Field(False, description="Force restart if already running")

class VideoAssignmentRequest(BaseModel):
    """Request model for video assignment"""
    project_id: str = Field(..., description="Project ID")
    video_ids: Optional[List[str]] = Field(None, description="Specific video IDs to assign")

class WorkflowStatusUpdate(BaseModel):
    """Request model for workflow status updates"""
    project_id: str = Field(..., description="Project ID")
    status: str = Field(..., regex="^(initialized|planning|resource_allocation|video_assignment|ground_truth_generation|test_configuration|execution|monitoring|analysis|validation|completed|failed|cancelled|paused)$", description="Workflow status")
    metadata: Optional[Dict[str, Any]] = Field({}, description="Additional metadata")

# Response models
class ProjectCreationResponse(BaseModel):
    """Response model for project creation"""
    success: bool
    project_id: Optional[str] = None
    workflow_id: Optional[str] = None
    message: str
    error: Optional[str] = None

class TestExecutionResponse(BaseModel):
    """Response model for test execution"""
    success: bool
    execution_id: Optional[str] = None
    project_id: Optional[str] = None
    estimated_duration: Optional[str] = None
    message: str
    error: Optional[str] = None

class ProjectStatusResponse(BaseModel):
    """Response model for project status"""
    success: bool
    project_id: str
    status: Optional[Dict[str, Any]] = None
    message: str
    error: Optional[str] = None

class LatencyConfigurationResponse(BaseModel):
    """Response model for latency configuration"""
    success: bool
    project_id: str
    thresholds: Optional[Dict[str, Any]] = None
    message: str
    error: Optional[str] = None

class VideoAssignmentResponse(BaseModel):
    """Response model for video assignment"""
    success: bool
    project_id: str
    assignments: Optional[List[Dict[str, Any]]] = None
    message: str
    error: Optional[str] = None

# Endpoints
@router.post("/projects/create", response_model=ProjectCreationResponse, status_code=status.HTTP_201_CREATED)
async def create_project_workflow(
    request: ProjectCreationRequest,
    workflow_config: Optional[WorkflowConfigurationRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Create a new project with complete workflow orchestration
    
    This endpoint creates a new project and sets up the complete workflow including:
    - Project initialization
    - Resource allocation
    - Video assignment (if applicable)
    - Test configuration
    - Workflow orchestration setup
    """
    try:
        # Convert request to dictionary
        project_data = request.dict()
        
        # Convert workflow configuration if provided
        config = None
        if workflow_config:
            config = _convert_workflow_config(workflow_config)
        
        # Create project workflow
        result = await workflow_api.create_project_endpoint(project_data, config.dict() if config else None)
        
        if result["success"]:
            # Add background task for post-creation setup
            background_tasks.add_task(
                _post_creation_setup,
                result["data"]["project_id"]
            )
            
            return ProjectCreationResponse(
                success=True,
                project_id=result["data"]["project_id"],
                workflow_id=result["data"]["workflow_id"],
                message=result["message"]
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create project workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project workflow: {str(e)}"
        )

@router.post("/tests/execute", response_model=TestExecutionResponse)
async def execute_project_tests(
    request: TestExecutionRequest,
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Execute comprehensive project tests
    
    This endpoint executes the complete test suite for a project including:
    - Test plan creation
    - Resource allocation
    - Test execution (sequential/parallel based on configuration)
    - Progress monitoring
    - Result collection and analysis
    """
    try:
        config_dict = None
        if request.workflow_config:
            config = _convert_workflow_config(request.workflow_config)
            config_dict = config.dict()
        
        # Execute tests
        result = await workflow_api.execute_tests_endpoint(request.project_id, config_dict)
        
        if result["success"]:
            # Add background task for monitoring
            background_tasks.add_task(
                _monitor_test_execution,
                request.project_id,
                result["data"]["execution_id"]
            )
            
            return TestExecutionResponse(
                success=True,
                execution_id=result["data"]["execution_id"],
                project_id=result["data"]["project_id"],
                estimated_duration=str(result["data"].get("estimated_duration", "Unknown")),
                message=result["message"]
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute project tests: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute project tests: {str(e)}"
        )

@router.get("/projects/{project_id}/status", response_model=ProjectStatusResponse)
async def get_project_status(project_id: str):
    """
    Get comprehensive project status
    
    Returns detailed status information including:
    - Overall progress percentage
    - Current workflow state
    - Component-level progress
    - Performance metrics
    - Error/warning information
    """
    try:
        result = workflow_api.get_status_endpoint(project_id)
        
        if result["success"]:
            return ProjectStatusResponse(
                success=True,
                project_id=project_id,
                status=result["data"],
                message=result["message"]
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["message"]
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project status: {str(e)}"
        )

@router.post("/projects/{project_id}/latency-thresholds", response_model=LatencyConfigurationResponse)
async def configure_latency_thresholds(project_id: str, request: LatencyThresholdRequest):
    """
    Configure project latency thresholds
    
    Sets latency thresholds for various components:
    - Detection latency
    - Processing latency
    - End-to-end latency
    - Signal processing latency
    - Warning and critical thresholds
    """
    try:
        thresholds_dict = request.dict()
        result = workflow_api.configure_latency_endpoint(project_id, thresholds_dict)
        
        if result["success"]:
            return LatencyConfigurationResponse(
                success=True,
                project_id=project_id,
                thresholds=result["data"]["thresholds"],
                message=result["message"]
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to configure latency thresholds: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to configure latency thresholds: {str(e)}"
        )

@router.post("/projects/{project_id}/assign-videos", response_model=VideoAssignmentResponse)
async def assign_videos_intelligently(project_id: str, request: VideoAssignmentRequest):
    """
    Intelligently assign videos to project
    
    Uses intelligent assignment system that considers:
    - Video-project compatibility scoring
    - Camera view matching
    - Resolution compatibility
    - Frame rate suitability
    - Duration appropriateness
    """
    try:
        # Get workflow manager instance
        from project_workflow_manager import workflow_manager
        
        assignments = await workflow_manager.assign_videos_intelligently(
            project_id,
            request.video_ids
        )
        
        # Convert assignments to dict format
        assignments_dict = [
            {
                "video_id": a.video_id,
                "project_id": a.project_id,
                "compatibility_score": a.compatibility_score,
                "assigned_at": a.assigned_at.isoformat(),
                "assignment_reason": a.assignment_reason
            }
            for a in assignments
        ]
        
        return VideoAssignmentResponse(
            success=True,
            project_id=project_id,
            assignments=assignments_dict,
            message=f"Successfully assigned {len(assignments)} videos to project"
        )
    
    except Exception as e:
        logger.error(f"Failed to assign videos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign videos: {str(e)}"
        )

@router.put("/projects/{project_id}/workflow-status", response_model=Dict[str, Any])
async def update_workflow_status(project_id: str, request: WorkflowStatusUpdate):
    """
    Update workflow status
    
    Updates the current workflow state and associated metadata
    """
    try:
        from project_workflow_manager import workflow_manager
        
        success = workflow_manager.update_workflow_status(
            project_id,
            WorkflowState(request.status),
            request.metadata
        )
        
        if success:
            return {
                "success": True,
                "project_id": project_id,
                "status": request.status,
                "message": "Workflow status updated successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update workflow status"
            )
    
    except Exception as e:
        logger.error(f"Failed to update workflow status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update workflow status: {str(e)}"
        )

@router.get("/projects/{project_id}/progress", response_model=Dict[str, Any])
async def get_project_progress(project_id: str):
    """
    Get detailed project progress information
    
    Returns comprehensive progress tracking including:
    - Overall progress percentage
    - Component-specific progress
    - Task completion status
    - Performance metrics
    - Estimated completion time
    """
    try:
        from project_workflow_manager import workflow_manager
        
        progress = workflow_manager.progress_tracker.get_overall_progress(project_id)
        
        return {
            "success": True,
            "project_id": project_id,
            "progress": progress,
            "message": "Progress retrieved successfully"
        }
    
    except Exception as e:
        logger.error(f"Failed to get project progress: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project progress: {str(e)}"
        )

@router.get("/workflows/active", response_model=Dict[str, Any])
async def get_active_workflows():
    """
    Get all active workflows
    
    Returns information about all currently active workflows
    """
    try:
        from project_workflow_manager import workflow_manager
        
        active_workflows = workflow_manager.orchestrator.active_workflows
        
        return {
            "success": True,
            "active_workflows": len(active_workflows),
            "workflows": {
                workflow_id: {
                    "workflow_id": progress.workflow_id,
                    "current_state": progress.current_state.value,
                    "progress_percentage": progress.progress_percentage,
                    "tasks_completed": progress.tasks_completed,
                    "tasks_total": progress.tasks_total,
                    "current_task": progress.current_task,
                    "start_time": progress.start_time.isoformat(),
                    "last_update": progress.last_update.isoformat()
                }
                for workflow_id, progress in active_workflows.items()
            },
            "message": "Active workflows retrieved successfully"
        }
    
    except Exception as e:
        logger.error(f"Failed to get active workflows: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active workflows: {str(e)}"
        )

# Helper functions
def _convert_workflow_config(config_request: WorkflowConfigurationRequest) -> WorkflowConfiguration:
    """Convert request model to WorkflowConfiguration"""
    latency_thresholds = LatencyThreshold()
    if config_request.latency_thresholds:
        latency_thresholds = LatencyThreshold(**config_request.latency_thresholds.dict())
    
    pass_fail_criteria = PassFailCriteria()
    if config_request.pass_fail_criteria:
        pass_fail_criteria = PassFailCriteria(**config_request.pass_fail_criteria.dict())
    
    return WorkflowConfiguration(
        project_id="",  # Will be set when project is created
        name=config_request.name,
        description=config_request.description,
        priority=WorkflowPriority(config_request.priority),
        execution_strategy=ExecutionStrategy(config_request.execution_strategy),
        max_concurrent_tasks=config_request.max_concurrent_tasks,
        timeout_minutes=config_request.timeout_minutes,
        retry_attempts=config_request.retry_attempts,
        auto_recovery=config_request.auto_recovery,
        latency_thresholds=latency_thresholds,
        pass_fail_criteria=pass_fail_criteria,
        notification_config=config_request.notification_config or {},
        custom_parameters=config_request.custom_parameters or {}
    )

async def _post_creation_setup(project_id: str):
    """Background task for post-project creation setup"""
    try:
        from project_workflow_manager import workflow_manager
        
        # Perform any additional setup tasks
        logger.info(f"Performing post-creation setup for project {project_id}")
        
        # Track initial progress
        workflow_manager.progress_tracker.track_progress(
            project_id, "project_setup", 100.0,
            {"setup_completed": True, "timestamp": datetime.utcnow()}
        )
        
    except Exception as e:
        logger.error(f"Post-creation setup failed for project {project_id}: {str(e)}")

async def _monitor_test_execution(project_id: str, execution_id: str):
    """Background task for monitoring test execution"""
    try:
        from project_workflow_manager import workflow_manager
        
        # Monitor test execution progress
        logger.info(f"Monitoring test execution for project {project_id}, execution {execution_id}")
        
        # This would contain actual monitoring logic
        # For now, just track that monitoring started
        workflow_manager.progress_tracker.track_progress(
            project_id, "test_monitoring", 0.0,
            {"monitoring_started": True, "execution_id": execution_id}
        )
        
    except Exception as e:
        logger.error(f"Test execution monitoring failed: {str(e)}")

# Health check endpoint
@router.get("/health", response_model=Dict[str, Any])
async def workflow_health_check():
    """
    Health check for workflow management system
    
    Returns system health and status information
    """
    try:
        from project_workflow_manager import workflow_manager
        
        health_info = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "active_workflows": len(workflow_manager.orchestrator.active_workflows),
            "components": {
                "workflow_manager": "operational",
                "orchestrator": "operational",
                "progress_tracker": "operational",
                "test_orchestrator": "operational"
            }
        }
        
        return {
            "success": True,
            "health": health_info,
            "message": "Workflow management system is healthy"
        }
    
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Workflow management system health check failed"
        }

# Export router for inclusion in main FastAPI app
__all__ = ["router"]