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

# Import appropriate signal validation service based on environment
import platform
if platform.system() == "Linux" and "microsoft" in platform.uname().release.lower():
    # WSL environment - use WSL-enhanced service
    from services.signal_validation_wsl import signal_validation_service
else:
    # Native environment - use standard service
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
    """Initialize LabJack connection with graceful hardware fallback
    
    This endpoint will attempt to connect to LabJack hardware but will
    automatically fall back to mock mode if hardware is not available.
    
    Config parameters:
    - device_type: Device type (T4, T7, etc.) or "ANY"
    - connection_type: Connection type (USB, Ethernet, WiFi) or "ANY"
    - identifier: Device serial number, IP address, or "ANY"
    - voltage_threshold: Detection threshold in volts (default: 2.5V)
    - channels: List of analog input channels (default: ["AIN0", "AIN1"])
    - force_mock_mode: Force mock mode regardless of hardware availability
    """
    try:
        # Initialize with graceful fallback
        success = await signal_validation_service.initialize_labjack(config)
        
        if success:
            # Get current status to determine if we're in mock mode
            status = await signal_validation_service.check_labjack_connection()
            
            response = {
                "status": "connected",
                "message": "LabJack initialized successfully",
                "mock_mode": status.get("mock_mode", False),
                "config": config or {},
                "connection_details": {
                    "voltage_threshold": status.get("voltage_threshold"),
                    "sample_rate": status.get("sample_rate"),
                    "channels": status.get("channels"),
                    "current_voltages": status.get("current_voltages", {})
                }
            }
            
            if status.get("mock_mode"):
                response["message"] += " (using mock mode - no hardware required)"
                response["warning"] = "Running in simulation mode. No actual LabJack hardware detected."
            else:
                response["message"] += " (hardware mode)"
                response["info"] = "Connected to actual LabJack hardware."
            
            return response
        else:
            # Initialization failed completely
            return {
                "status": "failed",
                "message": "LabJack initialization failed",
                "error": "Unable to initialize either hardware or mock mode",
                "config": config or {}
            }
    except Exception as e:
        logger.error(f"LabJack initialization error: {e}")
        return {
            "status": "error",
            "message": "LabJack initialization error",
            "error": str(e),
            "config": config or {},
            "suggestion": "Try running with mock mode or check hardware connections"
        }


@router.get("/labjack/status")
async def get_labjack_status():
    """Check LabJack connection status with comprehensive information"""
    try:
        # Use the appropriate service method based on environment
        if hasattr(signal_validation_service, 'get_labjack_status'):
            # WSL service - synchronous method
            status = signal_validation_service.get_labjack_status()
        else:
            # Standard service - async method
            status = await signal_validation_service.check_labjack_connection()
        
        # Enhance status with additional information if needed
        if "timestamp" not in status:
            status["timestamp"] = datetime.utcnow().isoformat()
        
        enhanced_status = status
        
        # Add recommendations based on status
        recommendations = []
        if not status.get("connected"):
            recommendations.append("Check hardware connections or use mock mode for development")
        if status.get("mock_mode"):
            recommendations.append("Running in mock mode - install LabJack hardware for real signal acquisition")
        if status.get("error"):
            recommendations.append("Check logs for detailed error information")
        
        enhanced_status["recommendations"] = recommendations
        
        return enhanced_status
        
    except Exception as e:
        logger.error(f"Error checking LabJack status: {e}")
        return {
            "connected": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "recommendations": [
                "Check system configuration",
                "Verify LabJack installation", 
                "Try restarting the service"
            ]
        }


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


@router.get("/labjack/read-voltage/{channel}")
async def read_voltage_signal(channel: str = "AIN0"):
    """Read current voltage from LabJack channel
    
    Args:
        channel: Analog input channel (e.g., "AIN0", "AIN1", "AIN2")
        
    Returns:
        Current voltage reading with timestamp and status
    """
    try:
        # Check if service has read_voltage_signal method (WSL service)
        if hasattr(signal_validation_service, 'read_voltage_signal'):
            result = signal_validation_service.read_voltage_signal(channel)
        else:
            # Fallback to TTL signal reading
            result = signal_validation_service.read_ttl_signal(channel)
        
        return result
        
    except Exception as e:
        logger.error(f"Voltage read error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/labjack/read-ttl/{channel}")
async def read_ttl_signal(channel: str = "FIO0"):
    """Read TTL digital signal from LabJack channel
    
    Args:
        channel: Digital I/O channel (e.g., "FIO0", "FIO1", "FIO2")
        
    Returns:
        Digital signal state (0 or 1) with voltage and timestamp
    """
    try:
        result = signal_validation_service.read_ttl_signal(channel)
        return result
        
    except Exception as e:
        logger.error(f"TTL read error: {e}")
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
    """Comprehensive health check for signal validation service
    
    This endpoint provides a complete health check including:
    - LabJack connection status (hardware or mock)
    - Service health and configuration
    - System dependencies
    - Available features
    """
    try:
        # Check LabJack
        labjack_status = await signal_validation_service.check_labjack_connection()
        
        # Determine overall health
        is_healthy = True
        health_issues = []
        
        if not labjack_status.get("connected"):
            # Not necessarily unhealthy if we have mock mode
            if not labjack_status.get("mock_mode"):
                health_issues.append("LabJack not connected and mock mode unavailable")
        
        # Service capabilities
        capabilities = [
            "voltage_signal_detection",
            "real_time_monitoring", 
            "signal_statistics",
            "batch_validation"
        ]
        
        if labjack_status.get("mock_mode"):
            capabilities.extend([
                "mock_signal_simulation",
                "development_mode"
            ])
        else:
            capabilities.extend([
                "hardware_voltage_acquisition",
                "production_mode"
            ])
        
        health_status = {
            "status": "healthy" if is_healthy else "degraded",
            "service": "signal_validation",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "labjack": labjack_status,
            "capabilities": capabilities,
            "health_issues": health_issues,
            "configuration": {
                "mock_mode_available": True,
                "hardware_mode_available": labjack_status.get("ljm_library_available", False),
                "auto_fallback": True
            }
        }
        
        # Add system status if available
        try:
            from config.labjack_env_config import get_environment_status
            env_status = get_environment_status()
            health_status["environment"] = env_status
        except Exception as env_e:
            logger.debug(f"Could not get environment status: {env_e}")
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "service": "signal_validation",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "capabilities": ["error_reporting"],
            "recommendations": [
                "Check service logs",
                "Verify system configuration",
                "Restart the service if necessary"
            ]
        }


import numpy as np

# Enhanced logging for LabJack operations
logging.basicConfig(level=logging.INFO)
logger.addHandler(logging.StreamHandler())

# Add startup diagnostic
@router.on_event("startup")
async def startup_diagnostics():
    """Run startup diagnostics for LabJack integration"""
    logger.info("🚀 Signal Validation Service Starting Up...")
    
    try:
        # Check LabJack availability
        status = await signal_validation_service.check_labjack_connection()
        if status.get("connected"):
            mode = "Mock" if status.get("mock_mode") else "Hardware"
            logger.info(f"✅ LabJack interface ready ({mode} mode)")
        else:
            logger.warning("⚠️ LabJack interface not connected, manual initialization may be required")
        
        # Log available endpoints
        logger.info("📋 Available Signal Validation Endpoints:")
        logger.info("   - POST /api/signal-validation/labjack/initialize")
        logger.info("   - GET  /api/signal-validation/labjack/status")
        logger.info("   - GET  /api/signal-validation/test-connection")
        logger.info("   - POST /api/signal-validation/monitoring/start/{test_session_id}")
        logger.info("   - POST /api/signal-validation/signal/process")
        
    except Exception as e:
        logger.error(f"❌ Startup diagnostics failed: {e}")

# Fix import paths for compatibility
try:
    from security_middleware import get_current_user
except ImportError:
    # Fallback to main auth system
    try:
        from main_formatted import get_current_user
    except ImportError:
        logger.warning("Security middleware not available, endpoints will run without authentication")
        get_current_user = None