"""
Latency Analysis API Endpoints

Provides endpoints for latency decomposition analysis and camera-specific
latency validation, separating camera performance from system overhead.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import logging

from database import get_db
from services.latency_decomposition_service import get_latency_decomposition_service
from services.timing_synchronization_calculator import get_timing_synchronization_calculator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/decompose/{session_id}")
async def decompose_session_latencies(
    session_id: str,
    force_recalibration: bool = False,
    db: Session = Depends(get_db)
):
    """
    Decompose all latencies for a session to separate camera from system overhead.
    
    Args:
        session_id: Test session identifier
        force_recalibration: Force recalibration of system baseline
        db: Database session
        
    Returns:
        Session latency decomposition results
    """
    try:
        decomposition_service = get_latency_decomposition_service()
        timing_calc = get_timing_synchronization_calculator()
        
        # Calibrate system baseline if needed
        if force_recalibration or not decomposition_service._baseline_calibrated:
            logger.info(f"Calibrating system baseline for session {session_id}")
            baseline_profile = decomposition_service.calibrate_system_baseline(force_recalibration)
            logger.info(f"System baseline calibrated: {baseline_profile.total_baseline_ns/1e6:.3f}ms total overhead")
        
        # Get timing calculations for session
        timing_results = timing_calc.calculations.get(session_id, [])
        
        if not timing_results:
            raise HTTPException(
                status_code=404, 
                detail=f"No timing calculations found for session {session_id}"
            )
        
        # Get decomposition results (should already be available from timing calculations)
        decompositions = decomposition_service.get_session_decompositions(session_id)
        
        # Get session summary
        session_summary = decomposition_service.get_session_summary(session_id)
        
        return {
            "session_id": session_id,
            "decompositions_count": len(decompositions),
            "baseline_profile": decomposition_service.export_baseline_profile(),
            "session_summary": session_summary,
            "timing_results_count": len(timing_results),
            "decomposition_available": len(decompositions) > 0
        }
        
    except Exception as e:
        logger.error(f"Failed to decompose latencies for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Latency decomposition failed: {str(e)}")


@router.get("/decomposition/{session_id}")
async def get_session_decomposition(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get latency decomposition results for a session.
    
    Args:
        session_id: Test session identifier
        db: Database session
        
    Returns:
        Detailed latency decomposition results
    """
    try:
        decomposition_service = get_latency_decomposition_service()
        
        # Get decomposition results
        decompositions = decomposition_service.get_session_decompositions(session_id)
        
        if not decompositions:
            raise HTTPException(
                status_code=404,
                detail=f"No decomposition results found for session {session_id}"
            )
        
        # Get session summary
        session_summary = decomposition_service.get_session_summary(session_id)
        
        # Convert decompositions to dictionaries
        decomposition_data = []
        for decomp in decompositions:
            decomp_dict = {
                "detection_id": decomp.detection_id,
                "total_latency_ms": decomp.total_latency_ms,
                "camera_latency_ms": decomp.camera_latency_ms,
                "system_baseline_ms": decomp.system_baseline_ms,
                "processing_overhead_ms": decomp.processing_overhead_ms,
                "network_overhead_ms": decomp.network_overhead_ms,
                "sync_overhead_ms": decomp.sync_overhead_ms,
                "unknown_overhead_ms": decomp.unknown_overhead_ms,
                "overhead_percentage": decomp.get_overhead_percentage(),
                "pure_camera_latency": decomp.get_pure_camera_latency(),
                "decomposition_confidence": decomp.decomposition_confidence,
                "validation_status": decomp.validation_status,
                "calculation_timestamp": decomp.calculation_timestamp.isoformat()
            }
            decomposition_data.append(decomp_dict)
        
        return {
            "session_id": session_id,
            "session_summary": session_summary,
            "decompositions": decomposition_data,
            "baseline_profile": decomposition_service.export_baseline_profile()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get decomposition for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve decomposition: {str(e)}")


@router.get("/baseline/calibrate")
async def calibrate_system_baseline(
    force_recalibration: bool = False
):
    """
    Calibrate system baseline latency to measure hardware/software overhead.
    
    Args:
        force_recalibration: Force new calibration even if one exists
        
    Returns:
        System baseline calibration results
    """
    try:
        decomposition_service = get_latency_decomposition_service()
        
        logger.info("Starting system baseline calibration...")
        baseline_profile = decomposition_service.calibrate_system_baseline(force_recalibration)
        
        return {
            "calibration_status": "completed",
            "baseline_profile": {
                "total_baseline_ms": baseline_profile.total_baseline_ns / 1e6,
                "os_overhead_ms": baseline_profile.os_overhead_ns / 1e6,
                "hardware_overhead_ms": baseline_profile.hardware_overhead_ns / 1e6,
                "timing_precision_ms": baseline_profile.timing_precision_ns / 1e6,
                "context_switch_ms": baseline_profile.context_switch_ns / 1e6,
                "memory_access_ms": baseline_profile.memory_access_ns / 1e6,
                "measurement_confidence": baseline_profile.measurement_confidence,
                "profile_timestamp": baseline_profile.profile_timestamp.isoformat(),
                "system_info": baseline_profile.system_info
            },
            "calibration_timestamp": baseline_profile.profile_timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to calibrate system baseline: {e}")
        raise HTTPException(status_code=500, detail=f"Baseline calibration failed: {str(e)}")


@router.get("/baseline/status")
async def get_baseline_status():
    """
    Get current system baseline calibration status.
    
    Returns:
        Baseline calibration status and profile information
    """
    try:
        decomposition_service = get_latency_decomposition_service()
        
        return {
            "baseline_calibrated": decomposition_service._baseline_calibrated,
            "current_baseline": (
                decomposition_service.export_baseline_profile() 
                if decomposition_service._baseline_calibrated else None
            ),
            "service_status": decomposition_service.get_service_status()
        }
        
    except Exception as e:
        logger.error(f"Failed to get baseline status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get baseline status: {str(e)}")


@router.get("/analysis/{session_id}/camera-only")
async def get_camera_only_latencies(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get camera-only latencies for a session (excluding system overhead).
    
    Args:
        session_id: Test session identifier
        db: Database session
        
    Returns:
        Camera-only latency analysis results
    """
    try:
        decomposition_service = get_latency_decomposition_service()
        timing_calc = get_timing_synchronization_calculator()
        
        # Get decomposition results
        decompositions = decomposition_service.get_session_decompositions(session_id)
        
        if not decompositions:
            # Try to get from timing calculations
            timing_results = timing_calc.calculations.get(session_id, [])
            if not timing_results:
                raise HTTPException(
                    status_code=404,
                    detail=f"No latency data found for session {session_id}"
                )
            
            # Extract camera latencies from timing results
            camera_latencies = [r.camera_only_latency_ms for r in timing_results]
        else:
            camera_latencies = [d.camera_latency_ms for d in decompositions]
        
        if not camera_latencies:
            raise HTTPException(
                status_code=404,
                detail=f"No camera latency data available for session {session_id}"
            )
        
        # Calculate camera-only statistics
        import statistics
        
        camera_stats = {
            "session_id": session_id,
            "total_measurements": len(camera_latencies),
            "camera_only_latencies": {
                "mean_ms": statistics.mean(camera_latencies),
                "median_ms": statistics.median(camera_latencies),
                "min_ms": min(camera_latencies),
                "max_ms": max(camera_latencies),
                "std_dev_ms": statistics.stdev(camera_latencies) if len(camera_latencies) > 1 else 0.0,
                "range_ms": max(camera_latencies) - min(camera_latencies)
            },
            "camera_performance_analysis": {
                "consistent_performance": statistics.stdev(camera_latencies) < 5.0 if len(camera_latencies) > 1 else True,
                "within_expected_bounds": all(10 <= lat <= 200 for lat in camera_latencies),
                "average_response_quality": "excellent" if statistics.mean(camera_latencies) < 50 else "good" if statistics.mean(camera_latencies) < 100 else "needs_improvement"
            }
        }
        
        return camera_stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get camera-only latencies for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze camera latencies: {str(e)}")


@router.get("/comparison/{session_id}")
async def compare_total_vs_camera_latencies(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Compare total latencies vs camera-only latencies to show system overhead impact.
    
    Args:
        session_id: Test session identifier
        db: Database session
        
    Returns:
        Comparison analysis between total and camera-only latencies
    """
    try:
        timing_calc = get_timing_synchronization_calculator()
        
        # Get timing results
        timing_results = timing_calc.calculations.get(session_id, [])
        
        if not timing_results:
            raise HTTPException(
                status_code=404,
                detail=f"No timing data found for session {session_id}"
            )
        
        # Extract latency data
        total_latencies = [r.real_latency_ms for r in timing_results]
        camera_latencies = [r.camera_only_latency_ms for r in timing_results]
        system_overheads = [r.system_overhead_ms for r in timing_results]
        processing_overheads = [r.processing_overhead_ms for r in timing_results]
        
        # Calculate comparison statistics
        import statistics
        
        comparison_analysis = {
            "session_id": session_id,
            "measurement_count": len(timing_results),
            "latency_comparison": {
                "total_latency": {
                    "mean_ms": statistics.mean(total_latencies),
                    "median_ms": statistics.median(total_latencies),
                    "range_ms": max(total_latencies) - min(total_latencies)
                },
                "camera_only_latency": {
                    "mean_ms": statistics.mean(camera_latencies),
                    "median_ms": statistics.median(camera_latencies),
                    "range_ms": max(camera_latencies) - min(camera_latencies)
                },
                "system_overhead": {
                    "mean_ms": statistics.mean(system_overheads),
                    "median_ms": statistics.median(system_overheads),
                    "percentage_of_total": (statistics.mean(system_overheads) / statistics.mean(total_latencies)) * 100
                },
                "processing_overhead": {
                    "mean_ms": statistics.mean(processing_overheads),
                    "median_ms": statistics.median(processing_overheads),
                    "percentage_of_total": (statistics.mean(processing_overheads) / statistics.mean(total_latencies)) * 100
                }
            },
            "overhead_impact_analysis": {
                "total_overhead_percentage": ((statistics.mean(system_overheads) + statistics.mean(processing_overheads)) / statistics.mean(total_latencies)) * 100,
                "camera_contribution_percentage": (statistics.mean(camera_latencies) / statistics.mean(total_latencies)) * 100,
                "overhead_reduction_achieved_ms": statistics.mean(total_latencies) - statistics.mean(camera_latencies),
                "validation_conclusion": (
                    "Camera performance validated - low system overhead" 
                    if (statistics.mean(camera_latencies) / statistics.mean(total_latencies)) > 0.7 
                    else "High system overhead detected - camera validation adjusted"
                )
            }
        }
        
        return comparison_analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compare latencies for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Latency comparison failed: {str(e)}")


@router.get("/service/status")
async def get_latency_analysis_service_status():
    """
    Get latency analysis service status and configuration.
    
    Returns:
        Service status, configuration, and statistics
    """
    try:
        decomposition_service = get_latency_decomposition_service()
        timing_calc = get_timing_synchronization_calculator()
        
        return {
            "decomposition_service": decomposition_service.get_service_status(),
            "timing_calculator": timing_calc.get_service_status(),
            "integration_status": {
                "services_connected": True,
                "latency_decomposition_enabled": True,
                "baseline_calibration_available": True,
                "camera_isolation_capability": "active"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get service status: {e}")
        raise HTTPException(status_code=500, detail=f"Service status check failed: {str(e)}")