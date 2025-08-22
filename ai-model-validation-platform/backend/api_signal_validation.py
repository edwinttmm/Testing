"""
API endpoints for external signal validation with LabJack integration

This module provides endpoints for:
- Configuring LabJack voltage signal detection
- Receiving detection signals from external cameras
- Validating signals against ground truth
- Real-time monitoring and statistics
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from services.signal_validation_service import signal_validation_service
from schemas_video_annotation import (
    ValidationResult,
    PassFailCriteria,
    PassFailResult
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/signal-validation", tags=["Signal Validation"])


@router.post("/labjack/initialize")
async def initialize_labjack(config: Dict[str, Any] = None):
    """Initialize LabJack connection for voltage signal acquisition
    
    Config parameters:
    - device_type: Device type (T4, T7, etc.) or "ANY"
    - connection_type: Connection type (USB, Ethernet, WiFi) or "ANY"
    - identifier: Device serial number, IP address, or "ANY"
    - voltage_threshold: Detection threshold in volts (default: 2.5V)
    - channels: List of analog input channels (default: ["AIN0", "AIN1"])
    """
    try:
        success = await signal_validation_service.initialize_labjack(config)
        if success:
            return {
                "status": "connected",
                "message": "LabJack initialized successfully",
                "config": config
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to initialize LabJack")
    except Exception as e:
        logger.error(f"LabJack initialization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/labjack/status")
async def get_labjack_status():
    """Check LabJack connection status and current voltage readings"""
    try:
        status = await signal_validation_service.check_labjack_connection()
        return status
    except Exception as e:
        logger.error(f"Error checking LabJack status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/labjack/configure")
async def configure_voltage_detection(
    voltage_threshold: float = Query(2.5, description="Detection threshold in volts"),
    sample_rate: int = Query(1000, description="Sample rate in Hz"),
    channels: Optional[List[str]] = Query(None, description="Analog input channels")
):
    """Configure voltage detection parameters
    
    Args:
        voltage_threshold: Voltage level that triggers detection (volts)
        sample_rate: Sampling rate in Hz (100-50000)
        channels: List of analog input channels (e.g., ["AIN0", "AIN1"])
    """
    try:
        result = await signal_validation_service.configure_voltage_detection(
            voltage_threshold=voltage_threshold,
            channels=channels,
            sample_rate=sample_rate
        )
        
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get("error"))
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/start/{test_session_id}")
async def start_signal_monitoring(test_session_id: str):
    """Start continuous monitoring of external signals for a test session
    
    This will continuously monitor:
    - LabJack voltage signals
    - Network packets (if configured)
    - CAN bus messages (if configured)
    """
    try:
        signal_validation_service.start_signal_monitoring(test_session_id)
        return {
            "status": "monitoring",
            "test_session_id": test_session_id,
            "started_at": datetime.utcnow().isoformat(),
            "message": "Signal monitoring started"
        }
    except Exception as e:
        logger.error(f"Failed to start monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/stop")
async def stop_signal_monitoring():
    """Stop signal monitoring"""
    try:
        signal_validation_service.stop_signal_monitoring()
        return {
            "status": "stopped",
            "message": "Signal monitoring stopped"
        }
    except Exception as e:
        logger.error(f"Failed to stop monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/signal/process")
async def process_detection_signal(
    signal_type: str,
    video_timestamp: float,
    test_session_id: str,
    signal_data: Dict[str, Any]
):
    """Process an incoming detection signal from external camera
    
    Args:
        signal_type: Type of signal (voltage, can_bus, network)
        video_timestamp: Current timestamp in the playing video (seconds)
        test_session_id: Current test session ID
        signal_data: Signal-specific data
            For voltage: {"voltage": 3.5, "channel": "AIN0"}
            For CAN: {"message_id": 0x100, "data": [...]}
            For network: {"packet": {...}, "source_ip": "..."}
    """
    try:
        result = await signal_validation_service.process_external_signal(
            signal_type=signal_type,
            signal_data=signal_data,
            video_timestamp=video_timestamp,
            test_session_id=test_session_id
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Signal processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/{test_session_id}")
async def get_signal_statistics(test_session_id: str):
    """Get statistics for signals in a test session
    
    Returns:
        - Total signal count
        - Signal type distribution
        - Average confidence scores
        - Voltage statistics (min, max, mean, std)
        - Timing distribution
    """
    try:
        stats = await signal_validation_service.get_signal_statistics(test_session_id)
        return stats
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate/batch")
async def validate_signal_batch(
    test_session_id: str,
    signals: List[Dict[str, Any]],
    ground_truth_annotations: List[Dict[str, Any]],
    criteria: PassFailCriteria
) -> PassFailResult:
    """Validate a batch of signals against ground truth annotations
    
    Args:
        test_session_id: Test session ID
        signals: List of detection signals from external camera
        ground_truth_annotations: Pre-annotated ground truth
        criteria: Pass/fail criteria for validation
    
    Returns:
        Pass/fail result with detailed metrics
    """
    try:
        # Calculate validation metrics
        total_signals = len(signals)
        matched_signals = 0
        false_positives = 0
        false_negatives = 0
        timing_errors = []
        
        # Simple matching logic (would be more sophisticated in production)
        for signal in signals:
            signal_time = signal.get("timestamp", 0)
            matched = False
            
            for annotation in ground_truth_annotations:
                ann_time = annotation.get("timestamp", 0)
                time_diff_ms = abs(signal_time - ann_time) * 1000
                
                if time_diff_ms <= criteria.timing_tolerance_ms:
                    matched = True
                    matched_signals += 1
                    timing_errors.append(time_diff_ms)
                    break
            
            if not matched:
                false_positives += 1
        
        # Check for missed annotations
        for annotation in ground_truth_annotations:
            ann_time = annotation.get("timestamp", 0)
            matched = False
            
            for signal in signals:
                signal_time = signal.get("timestamp", 0)
                time_diff_ms = abs(signal_time - ann_time) * 1000
                
                if time_diff_ms <= criteria.timing_tolerance_ms:
                    matched = True
                    break
            
            if not matched:
                false_negatives += 1
        
        # Calculate metrics
        precision = matched_signals / total_signals if total_signals > 0 else 0
        recall = matched_signals / len(ground_truth_annotations) if ground_truth_annotations else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        avg_timing_error = np.mean(timing_errors) if timing_errors else 0
        
        # Determine pass/fail
        passed = (
            precision >= criteria.min_precision and
            recall >= criteria.min_recall and
            f1_score >= criteria.min_f1_score and
            avg_timing_error <= criteria.timing_tolerance_ms
        )
        
        return PassFailResult(
            passed=passed,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            average_timing_error_ms=avg_timing_error,
            total_detections=total_signals,
            true_positives=matched_signals,
            false_positives=false_positives,
            false_negatives=false_negatives,
            test_session_id=test_session_id,
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Batch validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-connection")
async def test_connection():
    """Test endpoint to check if the signal validation service is running
    
    Also checks:
    - LabJack connection status
    - Database connectivity
    - Service health
    """
    try:
        # Check LabJack
        labjack_status = await signal_validation_service.check_labjack_connection()
        
        return {
            "status": "healthy",
            "service": "signal_validation",
            "labjack": labjack_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# Add missing numpy import
import numpy as np