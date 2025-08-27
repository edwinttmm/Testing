#!/usr/bin/env python3
"""
VRU Validation Engine API Endpoints

This module provides REST API endpoints for the VRU validation engine,
enabling integration with the existing AI model validation platform.

Key Features:
- RESTful API endpoints for validation operations
- Asynchronous validation processing
- Real-time status monitoring and progress tracking
- Comprehensive error handling and logging
- Integration with existing FastAPI application
- Authentication and authorization support

API Endpoints:
- POST /api/validation/sessions/{session_id}/validate - Start validation
- GET /api/validation/sessions/{session_id}/status - Get validation status
- GET /api/validation/sessions/{session_id}/report - Get validation report
- POST /api/validation/config - Update validation configuration
- GET /api/validation/config/profiles - List configuration profiles
- GET /api/validation/statistics - Get validation statistics
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path
import json

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

# Import validation engine components
from validation_engine import (
    VRUValidationEngine, ValidationReport, ValidationStatus,
    AlignmentMethod, LatencyCategory, ValidationCriteria,
    create_validation_engine, create_default_criteria
)
from validation_config import (
    ConfigurationManager, ValidationEngineConfiguration,
    ConfigurationProfile, ValidationMode
)

# Import existing platform components
from database import get_db
from models import TestSession

logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses

class ValidationRequest(BaseModel):
    """Request model for validation operation"""
    session_id: str = Field(..., description="Test session ID to validate")
    alignment_method: Optional[str] = Field(AlignmentMethod.ADAPTIVE.value, description="Temporal alignment method")
    enable_camera_validation: bool = Field(True, description="Enable camera validation integration")
    custom_criteria: Optional[Dict[str, Any]] = Field(None, description="Custom validation criteria")
    configuration_profile: Optional[str] = Field(None, description="Configuration profile to use")
    
    @validator('alignment_method')
    def validate_alignment_method(cls, v):
        try:
            AlignmentMethod(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid alignment method: {v}")
    
    @validator('configuration_profile')
    def validate_configuration_profile(cls, v):
        if v is not None:
            try:
                ConfigurationProfile(v)
                return v
            except ValueError:
                raise ValueError(f"Invalid configuration profile: {v}")
        return v

class ValidationStatusResponse(BaseModel):
    """Response model for validation status"""
    session_id: str
    status: str
    progress_percentage: float
    current_phase: Optional[str]
    estimated_completion: Optional[datetime]
    error_message: Optional[str]
    started_at: datetime
    updated_at: datetime

class ValidationReportResponse(BaseModel):
    """Response model for validation report"""
    session_id: str
    validation_status: str
    overall_score: float
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    mean_latency_ms: float
    latency_category: str
    true_positives: int
    false_positives: int
    false_negatives: int
    total_ground_truth: int
    total_detections: int
    report_generated_at: datetime
    export_formats: List[str] = Field(default=["json", "csv", "html"])

class ConfigurationUpdateRequest(BaseModel):
    """Request model for configuration updates"""
    profile: Optional[str] = Field(None, description="Configuration profile")
    updates: Dict[str, Any] = Field(..., description="Configuration updates")
    
    @validator('profile')
    def validate_profile(cls, v):
        if v is not None:
            try:
                ConfigurationProfile(v)
                return v
            except ValueError:
                raise ValueError(f"Invalid configuration profile: {v}")
        return v

class ValidationStatisticsResponse(BaseModel):
    """Response model for validation statistics"""
    total_validations: int
    success_rate: float
    average_score: float
    average_latency_ms: float
    most_common_issues: List[str]
    performance_trends: Dict[str, Any]
    period_start: datetime
    period_end: datetime

# Global validation engine and configuration manager
validation_engine: Optional[VRUValidationEngine] = None
config_manager: Optional[ConfigurationManager] = None
validation_tasks: Dict[str, Dict[str, Any]] = {}

def get_validation_engine() -> VRUValidationEngine:
    """Get or create validation engine instance"""
    global validation_engine, config_manager
    
    if validation_engine is None:
        try:
            config_manager = ConfigurationManager()
            config = config_manager.get_environment_configuration()
            
            validation_engine = create_validation_engine(
                tolerance_ms=config.temporal_config.default_tolerance_ms,
                criteria=config.validation_criteria
            )
            
            logger.info("Validation engine initialized for API")
        except Exception as e:
            logger.error(f"Failed to initialize validation engine: {e}")
            raise HTTPException(status_code=500, detail="Failed to initialize validation engine")
    
    return validation_engine

def get_config_manager() -> ConfigurationManager:
    """Get configuration manager instance"""
    global config_manager
    
    if config_manager is None:
        config_manager = ConfigurationManager()
    
    return config_manager

# Create FastAPI router
router = APIRouter(prefix="/api/validation", tags=["validation"])

@router.post("/sessions/{session_id}/validate")
async def start_validation(
    session_id: str,
    request: ValidationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Start validation for a test session
    
    This endpoint initiates the validation process for a given test session,
    comparing detection events against ground truth data using advanced
    temporal alignment and latency analysis.
    """
    try:
        logger.info(f"Starting validation for session: {session_id}")
        
        # Verify session exists
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"Test session {session_id} not found")
        
        # Check if validation is already running
        if session_id in validation_tasks and validation_tasks[session_id]['status'] != 'completed':
            return JSONResponse(
                status_code=202,
                content={
                    "message": "Validation already in progress",
                    "session_id": session_id,
                    "status": validation_tasks[session_id]['status']
                }
            )
        
        # Get validation engine and configuration
        engine = get_validation_engine()
        config_mgr = get_config_manager()
        
        # Apply configuration profile if specified
        if request.configuration_profile:
            profile = ConfigurationProfile(request.configuration_profile)
            config = config_mgr.get_configuration(profile)
        else:
            config = config_mgr.get_environment_configuration()
        
        # Parse custom criteria if provided
        custom_criteria = None
        if request.custom_criteria:
            try:
                custom_criteria = ValidationCriteria(**request.custom_criteria)
            except Exception as e:
                logger.warning(f"Invalid custom criteria: {e}")
                custom_criteria = config.validation_criteria
        else:
            custom_criteria = config.validation_criteria
        
        # Initialize validation task tracking
        validation_tasks[session_id] = {
            'status': 'started',
            'progress': 0.0,
            'phase': 'initialization',
            'started_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc),
            'error': None,
            'result': None
        }
        
        # Start validation in background
        alignment_method = AlignmentMethod(request.alignment_method)
        background_tasks.add_task(
            run_validation_task,
            engine,
            session_id,
            custom_criteria,
            alignment_method,
            request.enable_camera_validation
        )
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Validation started successfully",
                "session_id": session_id,
                "status": "started",
                "estimated_duration_minutes": 2.0
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start validation for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Validation startup failed: {str(e)}")

async def run_validation_task(
    engine: VRUValidationEngine,
    session_id: str,
    criteria: ValidationCriteria,
    alignment_method: AlignmentMethod,
    enable_camera_validation: bool
) -> None:
    """Background task to run validation"""
    try:
        logger.info(f"Running validation task for session: {session_id}")
        
        # Update progress
        validation_tasks[session_id].update({
            'status': 'running',
            'phase': 'data_loading',
            'progress': 10.0,
            'updated_at': datetime.now(timezone.utc)
        })
        
        # Perform validation
        validation_tasks[session_id].update({
            'phase': 'temporal_alignment',
            'progress': 30.0,
            'updated_at': datetime.now(timezone.utc)
        })
        
        validation_tasks[session_id].update({
            'phase': 'latency_analysis',
            'progress': 60.0,
            'updated_at': datetime.now(timezone.utc)
        })
        
        validation_tasks[session_id].update({
            'phase': 'criteria_evaluation',
            'progress': 80.0,
            'updated_at': datetime.now(timezone.utc)
        })
        
        # Run the actual validation
        report = await engine.validate_test_session(
            session_id=session_id,
            custom_criteria=criteria,
            alignment_method=alignment_method,
            enable_camera_validation=enable_camera_validation
        )
        
        # Update completion
        validation_tasks[session_id].update({
            'status': 'completed',
            'phase': 'completed',
            'progress': 100.0,
            'updated_at': datetime.now(timezone.utc),
            'result': report
        })
        
        logger.info(f"Validation completed for session {session_id}: {report.validation_status.value}")
        
    except Exception as e:
        logger.error(f"Validation task failed for session {session_id}: {e}")
        validation_tasks[session_id].update({
            'status': 'failed',
            'phase': 'error',
            'progress': 0.0,
            'updated_at': datetime.now(timezone.utc),
            'error': str(e)
        })

@router.get("/sessions/{session_id}/status")
async def get_validation_status(session_id: str) -> ValidationStatusResponse:
    """Get validation status for a test session"""
    try:
        if session_id not in validation_tasks:
            raise HTTPException(status_code=404, detail=f"No validation found for session {session_id}")
        
        task_info = validation_tasks[session_id]
        
        # Estimate completion time based on progress
        estimated_completion = None
        if task_info['status'] == 'running' and task_info['progress'] > 0:
            elapsed = datetime.now(timezone.utc) - task_info['started_at']
            remaining_ratio = (100.0 - task_info['progress']) / task_info['progress']
            estimated_remaining = elapsed * remaining_ratio
            estimated_completion = datetime.now(timezone.utc) + estimated_remaining
        
        return ValidationStatusResponse(
            session_id=session_id,
            status=task_info['status'],
            progress_percentage=task_info['progress'],
            current_phase=task_info['phase'],
            estimated_completion=estimated_completion,
            error_message=task_info.get('error'),
            started_at=task_info['started_at'],
            updated_at=task_info['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get validation status for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Status retrieval failed: {str(e)}")

@router.get("/sessions/{session_id}/report")
async def get_validation_report(
    session_id: str,
    export_format: str = Query("json", description="Export format: json, csv, html")
) -> Any:
    """Get validation report for a test session"""
    try:
        if session_id not in validation_tasks:
            raise HTTPException(status_code=404, detail=f"No validation found for session {session_id}")
        
        task_info = validation_tasks[session_id]
        
        if task_info['status'] != 'completed':
            raise HTTPException(
                status_code=409, 
                detail=f"Validation not completed for session {session_id}. Status: {task_info['status']}"
            )
        
        report: ValidationReport = task_info['result']
        if not report:
            raise HTTPException(status_code=404, detail=f"Validation report not found for session {session_id}")
        
        # Return JSON response by default
        if export_format.lower() == "json":
            return ValidationReportResponse(
                session_id=report.session_id,
                validation_status=report.validation_status.value,
                overall_score=report.overall_score,
                precision=report.precision,
                recall=report.recall,
                f1_score=report.f1_score,
                accuracy=report.accuracy,
                mean_latency_ms=report.latency_metrics.mean_latency_ms,
                latency_category=report.latency_metrics.latency_category.value,
                true_positives=report.true_positives,
                false_positives=report.false_positives,
                false_negatives=report.false_negatives,
                total_ground_truth=report.total_ground_truth,
                total_detections=report.total_detections,
                report_generated_at=report.timestamp
            )
        
        # Export to file for other formats
        else:
            engine = get_validation_engine()
            try:
                export_path = engine.export_report(report, export_format)
                return FileResponse(
                    path=export_path,
                    filename=f"validation_report_{session_id}.{export_format}",
                    media_type="application/octet-stream"
                )
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=str(ve))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get validation report for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Report retrieval failed: {str(e)}")

@router.post("/config")
async def update_validation_configuration(request: ConfigurationUpdateRequest) -> JSONResponse:
    """Update validation engine configuration"""
    try:
        config_mgr = get_config_manager()
        
        # Get profile if specified
        profile = ConfigurationProfile(request.profile) if request.profile else None
        
        # Update configuration
        updated_config = config_mgr.update_configuration(request.updates, profile)
        
        # Validate updated configuration
        issues = config_mgr.validate_configuration(updated_config)
        if issues:
            logger.warning(f"Configuration validation issues: {issues}")
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "Configuration updated successfully",
                "profile": updated_config.profile.value,
                "validation_issues": issues,
                "updated_at": updated_config.updated_at.isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to update validation configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Configuration update failed: {str(e)}")

@router.get("/config/profiles")
async def list_configuration_profiles() -> JSONResponse:
    """List available configuration profiles"""
    try:
        config_mgr = get_config_manager()
        profiles = config_mgr.list_available_profiles()
        
        # Get current configuration info
        current_config = config_mgr.get_environment_configuration()
        
        return JSONResponse(
            status_code=200,
            content={
                "available_profiles": profiles,
                "current_profile": current_config.profile.value,
                "current_environment": current_config.environment,
                "profile_descriptions": {
                    "default": "Standard validation settings",
                    "strict": "High precision requirements",
                    "performance": "Optimized for speed",
                    "safety_critical": "Maximum safety requirements",
                    "development": "Development and debugging",
                    "testing": "Testing and simulation",
                    "production": "Production deployment"
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to list configuration profiles: {e}")
        raise HTTPException(status_code=500, detail=f"Profile listing failed: {str(e)}")

@router.get("/statistics")
async def get_validation_statistics(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    days_back: int = Query(30, description="Number of days to look back")
) -> ValidationStatisticsResponse:
    """Get validation statistics and performance metrics"""
    try:
        engine = get_validation_engine()
        stats = engine.get_validation_statistics(project_id, days_back)
        
        if not stats:
            raise HTTPException(status_code=404, detail="No validation statistics found")
        
        # Calculate additional metrics from validation tasks
        completed_tasks = [
            task for task in validation_tasks.values() 
            if task['status'] == 'completed' and task.get('result')
        ]
        
        if completed_tasks:
            reports = [task['result'] for task in completed_tasks]
            avg_score = sum(r.overall_score for r in reports) / len(reports)
            avg_latency = sum(r.latency_metrics.mean_latency_ms for r in reports) / len(reports)
            
            # Collect common issues
            all_reasons = []
            for report in reports:
                all_reasons.extend(report.pass_fail_reasons)
            
            # Count reason frequency
            reason_counts = {}
            for reason in all_reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            
            # Get top 5 most common issues
            most_common = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            common_issues = [reason for reason, count in most_common]
        else:
            avg_score = 0.0
            avg_latency = 0.0
            common_issues = []
        
        return ValidationStatisticsResponse(
            total_validations=stats.get('completed_sessions', 0),
            success_rate=stats.get('completion_rate', 0.0),
            average_score=avg_score,
            average_latency_ms=avg_latency,
            most_common_issues=common_issues,
            performance_trends={
                "validation_count_trend": "stable",  # Would be calculated from historical data
                "success_rate_trend": "improving",
                "latency_trend": "stable"
            },
            period_start=datetime.now(timezone.utc) - timedelta(days=days_back),
            period_end=datetime.now(timezone.utc)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get validation statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Statistics retrieval failed: {str(e)}")

@router.delete("/sessions/{session_id}/validation")
async def cancel_validation(session_id: str) -> JSONResponse:
    """Cancel ongoing validation for a test session"""
    try:
        if session_id not in validation_tasks:
            raise HTTPException(status_code=404, detail=f"No validation found for session {session_id}")
        
        task_info = validation_tasks[session_id]
        
        if task_info['status'] in ['completed', 'failed']:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot cancel validation with status: {task_info['status']}"
            )
        
        # Update task status to cancelled
        validation_tasks[session_id].update({
            'status': 'cancelled',
            'phase': 'cancelled',
            'updated_at': datetime.now(timezone.utc),
            'error': 'Validation cancelled by user request'
        })
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "Validation cancelled successfully",
                "session_id": session_id,
                "cancelled_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel validation for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Validation cancellation failed: {str(e)}")

@router.get("/health")
async def get_validation_engine_health() -> JSONResponse:
    """Get validation engine health status"""
    try:
        engine = get_validation_engine()
        config_mgr = get_config_manager()
        
        # Get current configuration
        config = config_mgr.get_environment_configuration()
        
        # Count active validations
        active_validations = sum(
            1 for task in validation_tasks.values() 
            if task['status'] in ['started', 'running']
        )
        
        # Get recent validation results
        recent_completions = sum(
            1 for task in validation_tasks.values()
            if task['status'] == 'completed' and 
            (datetime.now(timezone.utc) - task['updated_at']).total_seconds() < 3600  # Last hour
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "engine_initialized": engine is not None,
                "configuration_profile": config.profile.value,
                "active_validations": active_validations,
                "recent_completions": recent_completions,
                "total_tracked_sessions": len(validation_tasks),
                "uptime_minutes": 0,  # Would track actual uptime
                "memory_usage_mb": 0,  # Would track actual memory usage
                "last_health_check": datetime.now(timezone.utc).isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "last_health_check": datetime.now(timezone.utc).isoformat()
            }
        )

# Initialize validation engine on module import
try:
    get_validation_engine()
    logger.info("Validation API initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize validation API: {e}")