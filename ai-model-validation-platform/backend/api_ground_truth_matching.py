"""
Ground Truth Matching API Endpoints

This module provides RESTful API endpoints for the comprehensive ground truth matching service.
It exposes the temporal matching functionality, detailed analysis, and validation metrics
for integration with the frontend and external systems.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import logging

from services.ground_truth_matching_service import GroundTruthMatchingService, SessionMetrics
from services.validation_service import ValidationService
from database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Initialize services
ground_truth_matcher = GroundTruthMatchingService()
validation_service = ValidationService()

# Create router
router = APIRouter(prefix="/api/v1/ground-truth", tags=["Ground Truth Matching"])


class MatchingRequest(BaseModel):
    """Request model for ground truth matching"""
    session_id: str = Field(..., description="Test session identifier")
    tolerance_ms: Optional[int] = Field(None, ge=1, le=5000, description="Tolerance window in milliseconds")
    force_rematch: bool = Field(False, description="Force re-matching even if results exist")


class MatchingResponse(BaseModel):
    """Response model for ground truth matching results"""
    success: bool
    session_id: str
    metrics: Optional[Dict[str, Any]] = None
    message: str
    processing_time_ms: Optional[float] = None


class DetailedAnalysisResponse(BaseModel):
    """Response model for detailed analysis"""
    success: bool
    session_id: str
    analysis: Optional[Dict[str, Any]] = None
    message: str


class ValidationReportResponse(BaseModel):
    """Response model for comprehensive validation reports"""
    success: bool
    session_id: str
    report: Optional[Dict[str, Any]] = None
    message: str


@router.post("/match", response_model=MatchingResponse)
async def match_detections_to_ground_truth(
    request: MatchingRequest,
    db: Session = Depends(get_db)
):
    """
    Perform comprehensive ground truth matching for a test session.
    
    This endpoint executes the temporal matching algorithm to compare LabJack detections
    against pre-recorded ground truth timing. It handles:
    
    - Temporal matching within configurable tolerance windows
    - Detection classification (TP/FP/FN)
    - Latency calculation and statistical analysis
    - Database population with match results
    - Performance metrics computation
    
    **Expected Results (based on requirements):**
    - Ground truth at 1.042s matches LabJack detection at 1.065s → Latency: +23ms
    - 18/24 ground truth objects matched (75% recall)
    - 22 LabJack detections total → 18 TP + 4 FP (82% precision)
    """
    import time
    start_time = time.time()
    
    try:
        logger.info(f"Starting ground truth matching for session {request.session_id}")
        
        # Perform matching
        session_metrics = ground_truth_matcher.match_detections_to_ground_truth(
            session_id=request.session_id,
            tolerance_ms=request.tolerance_ms,
            force_rematch=request.force_rematch
        )
        
        if not session_metrics:
            raise HTTPException(
                status_code=404,
                detail=f"Could not perform matching for session {request.session_id}. "
                       "Check that the session exists and has detection events."
            )
        
        processing_time = (time.time() - start_time) * 1000
        
        # Convert metrics to response format
        metrics_dict = {
            'classification': {
                'true_positives': session_metrics.true_positives,
                'false_positives': session_metrics.false_positives,
                'false_negatives': session_metrics.false_negatives,
                'total_ground_truth': session_metrics.total_ground_truth,
                'total_detections': session_metrics.total_detections,
                'matched_detections': session_metrics.matched_detections
            },
            'performance': {
                'precision': round(session_metrics.precision, 4),
                'recall': round(session_metrics.recall, 4),
                'f1_score': round(session_metrics.f1_score, 4),
                'accuracy': round(session_metrics.accuracy, 4)
            },
            'latency': {
                'mean_latency_ms': round(session_metrics.mean_latency_ms, 2),
                'std_latency_ms': round(session_metrics.std_latency_ms, 2),
                'min_latency_ms': round(session_metrics.min_latency_ms, 2),
                'max_latency_ms': round(session_metrics.max_latency_ms, 2),
                'within_tolerance_percentage': round(session_metrics.within_tolerance_percentage, 1)
            },
            'summary': {
                'overall_score': round(session_metrics.f1_score * 100, 1),
                'recommendation': 'PASS' if (
                    session_metrics.precision >= 0.8 and 
                    session_metrics.recall >= 0.75 and 
                    session_metrics.mean_latency_ms <= 100
                ) else 'FAIL'
            }
        }
        
        logger.info(
            f"Matching completed for session {request.session_id}: "
            f"{session_metrics.true_positives} TP, {session_metrics.false_positives} FP, "
            f"{session_metrics.false_negatives} FN"
        )
        
        return MatchingResponse(
            success=True,
            session_id=request.session_id,
            metrics=metrics_dict,
            message=f"Ground truth matching completed successfully. "
                   f"Found {session_metrics.matched_detections}/{session_metrics.total_ground_truth} matches "
                   f"with {session_metrics.mean_latency_ms:.1f}ms average latency.",
            processing_time_ms=round(processing_time, 2)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ground truth matching: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during ground truth matching: {str(e)}"
        )


@router.get("/analysis/{session_id}", response_model=DetailedAnalysisResponse)
async def get_detailed_analysis(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed analysis of ground truth matching results.
    
    This endpoint provides comprehensive analysis including:
    - Temporal offset distribution and patterns
    - Quality metrics and IoU scores
    - Detection timing analysis (early/on-time/late)
    - Performance recommendations
    - Statistical breakdowns
    
    The analysis helps identify system performance characteristics and
    provides actionable insights for improving detection accuracy.
    """
    try:
        logger.info(f"Generating detailed analysis for session {session_id}")
        
        analysis = ground_truth_matcher.get_detailed_analysis(session_id)
        
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail=f"No matching results found for session {session_id}. "
                       "Run ground truth matching first."
            )
        
        return DetailedAnalysisResponse(
            success=True,
            session_id=session_id,
            analysis=analysis,
            message="Detailed analysis generated successfully."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating detailed analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error generating analysis: {str(e)}"
        )


@router.get("/validation-report/{session_id}", response_model=ValidationReportResponse)
async def get_comprehensive_validation_report(
    session_id: str,
    force_rematch: bool = Query(False, description="Force re-matching before generating report"),
    include_detailed_analysis: bool = Query(True, description="Include detailed analysis in report"),
    db: Session = Depends(get_db)
):
    """
    Generate a comprehensive validation report with advanced ground truth matching.
    
    This endpoint combines ground truth matching with detailed analysis to provide
    a complete validation report suitable for:
    - Technical documentation
    - Performance assessment
    - Compliance reporting
    - System optimization
    
    The report includes all metrics, analysis, and recommendations in a single response.
    """
    try:
        logger.info(f"Generating comprehensive validation report for session {session_id}")
        
        # Get comprehensive validation report from validation service
        report = validation_service.validate_session_with_advanced_matching(
            session_id=session_id,
            force_rematch=force_rematch
        )
        
        if not report:
            raise HTTPException(
                status_code=404,
                detail=f"Could not generate validation report for session {session_id}. "
                       "Check that the session exists with detection events and ground truth."
            )
        
        # Add detailed analysis if requested
        if include_detailed_analysis:
            detailed_analysis = ground_truth_matcher.get_detailed_analysis(session_id)
            if detailed_analysis:
                report['detailed_analysis'] = detailed_analysis
        
        logger.info(f"Validation report generated for session {session_id}")
        
        return ValidationReportResponse(
            success=True,
            session_id=session_id,
            report=report,
            message="Comprehensive validation report generated successfully."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating validation report: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error generating validation report: {str(e)}"
        )


@router.get("/metrics/{session_id}")
async def get_session_metrics(
    session_id: str,
    force_rematch: bool = Query(False, description="Force re-matching to get fresh metrics"),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive session metrics using advanced ground truth matching.
    
    Returns detailed performance metrics including latency statistics,
    classification results, and quality scores.
    """
    try:
        session_metrics = validation_service.get_comprehensive_session_metrics(
            session_id, force_rematch
        )
        
        if not session_metrics:
            raise HTTPException(
                status_code=404,
                detail=f"No metrics available for session {session_id}"
            )
        
        return {
            'success': True,
            'session_id': session_id,
            'metrics': {
                'true_positives': session_metrics.true_positives,
                'false_positives': session_metrics.false_positives,
                'false_negatives': session_metrics.false_negatives,
                'precision': session_metrics.precision,
                'recall': session_metrics.recall,
                'f1_score': session_metrics.f1_score,
                'accuracy': session_metrics.accuracy,
                'mean_latency_ms': session_metrics.mean_latency_ms,
                'std_latency_ms': session_metrics.std_latency_ms,
                'max_latency_ms': session_metrics.max_latency_ms,
                'min_latency_ms': session_metrics.min_latency_ms,
                'within_tolerance_percentage': session_metrics.within_tolerance_percentage,
                'total_ground_truth': session_metrics.total_ground_truth,
                'total_detections': session_metrics.total_detections,
                'matched_detections': session_metrics.matched_detections
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error getting metrics: {str(e)}"
        )


@router.post("/batch-match")
async def batch_match_sessions(
    session_ids: list[str] = Body(..., description="List of session IDs to match"),
    tolerance_ms: Optional[int] = Body(None, description="Tolerance for all sessions"),
    force_rematch: bool = Body(False, description="Force rematch for all sessions"),
    db: Session = Depends(get_db)
):
    """
    Perform ground truth matching for multiple sessions in batch.
    
    This endpoint allows processing multiple test sessions efficiently,
    useful for batch analysis or system-wide validation.
    """
    try:
        logger.info(f"Starting batch matching for {len(session_ids)} sessions")
        
        results = []
        for session_id in session_ids:
            try:
                session_metrics = ground_truth_matcher.match_detections_to_ground_truth(
                    session_id=session_id,
                    tolerance_ms=tolerance_ms,
                    force_rematch=force_rematch
                )
                
                if session_metrics:
                    results.append({
                        'session_id': session_id,
                        'success': True,
                        'true_positives': session_metrics.true_positives,
                        'false_positives': session_metrics.false_positives,
                        'false_negatives': session_metrics.false_negatives,
                        'precision': round(session_metrics.precision, 4),
                        'recall': round(session_metrics.recall, 4),
                        'f1_score': round(session_metrics.f1_score, 4),
                        'mean_latency_ms': round(session_metrics.mean_latency_ms, 2)
                    })
                else:
                    results.append({
                        'session_id': session_id,
                        'success': False,
                        'error': 'Matching failed'
                    })
                    
            except Exception as e:
                logger.error(f"Error matching session {session_id}: {str(e)}")
                results.append({
                    'session_id': session_id,
                    'success': False,
                    'error': str(e)
                })
        
        successful_matches = sum(1 for r in results if r['success'])
        
        return {
            'success': True,
            'message': f"Batch matching completed: {successful_matches}/{len(session_ids)} successful",
            'results': results,
            'summary': {
                'total_sessions': len(session_ids),
                'successful_matches': successful_matches,
                'failed_matches': len(session_ids) - successful_matches
            }
        }
        
    except Exception as e:
        logger.error(f"Error in batch matching: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error in batch matching: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for the ground truth matching service"""
    try:
        # Test service initialization
        test_service = GroundTruthMatchingService()
        
        return {
            'status': 'healthy',
            'service': 'ground_truth_matching',
            'version': '1.0.0',
            'features': [
                'temporal_matching',
                'detection_classification',
                'latency_analysis',
                'statistical_metrics',
                'detailed_analysis',
                'batch_processing'
            ]
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Service unhealthy: {str(e)}"
        )


# Error handlers removed - APIRouter doesn't support exception_handler
# Exception handling should be done at the app level in main.py