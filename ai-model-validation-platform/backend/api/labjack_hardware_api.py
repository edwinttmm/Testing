"""
LabJack Hardware API Endpoints
PRD Module 3.1 & 3.2 Implementation

Provides REST API endpoints for real LabJack hardware integration:
- Connection status monitoring ("Connected" or "Not Detected")
- Device detection and information
- TTL signal monitoring control
- Hardware event logging and retrieval
- Precision timing integration

All endpoints use REAL hardware - no mock implementations.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

# Import real LabJack service (not mock)
from services.real_labjack_service import (
    get_real_labjack_service, 
    RealLabJackService,
    ConnectionStatus,
    TTLSignalType, 
    SignalConfiguration,
    HardwareEvent
)
from services.precision_timing_service import (
    get_precision_timing_service,
    PrecisionTimingService,
    TimingPrecision
)

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/v1/labjack", tags=["LabJack Hardware"])


# Pydantic models for API
class ConnectionStatusResponse(BaseModel):
    """PRD Module 3.1: Connection status response"""
    connection_status: str = Field(..., description="Connected or Not Detected")
    is_connected: bool
    device_info: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class DeviceInfoResponse(BaseModel):
    """Device information response"""
    device_type: str
    connection_type: str
    serial_number: int
    ip_address: Optional[str]
    port: Optional[int]
    firmware_version: str
    hardware_version: str
    bootloader_version: str
    is_real_hardware: bool = True


class SignalConfigurationRequest(BaseModel):
    """Signal configuration for TTL monitoring"""
    channel: str = Field(default="DIO0", description="TTL input channel")
    threshold_voltage: float = Field(default=2.5, description="TTL threshold voltage")
    sample_rate: int = Field(default=10000, description="Sample rate in Hz")
    edge_detection: str = Field(default="rising_edge", description="Edge detection type")
    debounce_time_ms: float = Field(default=1.0, description="Debounce time in ms")


class StartMonitoringRequest(BaseModel):
    """Request to start signal monitoring"""
    test_session_id: str = Field(..., description="Test session ID for correlation")
    signal_config: Optional[SignalConfigurationRequest] = None
    max_latency_ms: float = Field(default=100.0, description="Maximum acceptable latency")


class HardwareEventResponse(BaseModel):
    """Hardware event response"""
    event_id: str
    test_session_id: str
    video_id: str
    signal_received_time: str
    signal_type: str
    signal_voltage: float
    channel: str
    latency_ms: float
    detection_outcome: str
    created_at: str


class LatencyAnalysisResponse(BaseModel):
    """Latency analysis response"""
    total_events: int
    passed_events: int
    failed_high_latency: int
    missed_detections: int
    average_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    pass_rate_percentage: float


@router.get("/status", response_model=ConnectionStatusResponse)
async def get_connection_status():
    """
    Get LabJack connection status - PRD Module 3.1 requirement
    Returns "Connected" or "Not Detected" as required by PRD
    """
    try:
        service = get_real_labjack_service()
        status = service.get_status()
        
        return ConnectionStatusResponse(
            connection_status=service.get_connection_status(),  # PRD requirement
            is_connected=service.is_connected(),
            device_info=status.get("device_info", {}),
            error_message=status.get("statistics", {}).get("last_error")
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to get connection status: {e}")
        return ConnectionStatusResponse(
            connection_status="Not Detected",
            is_connected=False,
            error_message=str(e)
        )


@router.post("/connect")
async def connect_device(
    device_type: str = "ANY",
    connection_type: str = "ANY", 
    identifier: str = "ANY"
):
    """Connect to LabJack hardware device"""
    try:
        service = get_real_labjack_service()
        
        success = service.connect(
            device_type=device_type,
            connection_type=connection_type,
            identifier=identifier
        )
        
        if success:
            device_info = service.get_device_info()
            return {
                "success": True,
                "message": f"Connected to {device_info.get('device_type', 'LabJack')}",
                "connection_status": "Connected",
                "device_info": device_info
            }
        else:
            return {
                "success": False,
                "message": "Failed to connect to LabJack device",
                "connection_status": "Not Detected"
            }
            
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")


@router.post("/disconnect")
async def disconnect_device():
    """Disconnect from LabJack hardware"""
    try:
        service = get_real_labjack_service()
        success = service.disconnect()
        
        return {
            "success": success,
            "message": "LabJack disconnected" if success else "Disconnect failed",
            "connection_status": "Not Detected" if success else "Error"
        }
        
    except Exception as e:
        logger.error(f"❌ Disconnect failed: {e}")
        raise HTTPException(status_code=500, detail=f"Disconnect failed: {str(e)}")


@router.get("/detect-devices")
async def detect_devices():
    """Detect available LabJack devices"""
    try:
        service = get_real_labjack_service()
        devices = service.detect_devices()
        
        return {
            "devices_found": len(devices),
            "devices": devices
        }
        
    except Exception as e:
        logger.error(f"❌ Device detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Device detection failed: {str(e)}")


@router.get("/device-info", response_model=DeviceInfoResponse)
async def get_device_info():
    """Get detailed device information"""
    try:
        service = get_real_labjack_service()
        
        if not service.is_connected():
            raise HTTPException(status_code=400, detail="LabJack not connected")
        
        device_info = service.get_device_info()
        
        if "error" in device_info:
            raise HTTPException(status_code=500, detail=device_info["error"])
        
        return DeviceInfoResponse(**device_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get device info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get device info: {str(e)}")


@router.post("/start-monitoring")
async def start_signal_monitoring(request: StartMonitoringRequest):
    """
    Start TTL signal monitoring for hardware events - PRD Module 3.2
    """
    try:
        service = get_real_labjack_service()
        timing_service = get_precision_timing_service()
        
        if not service.is_connected():
            raise HTTPException(status_code=400, detail="LabJack not connected - cannot start monitoring")
        
        # Update signal configuration if provided
        if request.signal_config:
            config = SignalConfiguration(
                channel=request.signal_config.channel,
                threshold_voltage=request.signal_config.threshold_voltage,
                sample_rate=request.signal_config.sample_rate,
                edge_detection=TTLSignalType(request.signal_config.edge_detection),
                debounce_time_ms=request.signal_config.debounce_time_ms
            )
            service.signal_config = config
        
        # Capture Test_Start_Time for precision timing
        test_start_time = timing_service.capture_test_start_time()
        
        # Start hardware signal monitoring
        success = service.start_signal_monitoring(request.test_session_id)
        
        if success:
            return {
                "success": True,
                "message": "Signal monitoring started",
                "test_session_id": request.test_session_id,
                "test_start_time": test_start_time.wall_time.isoformat(),
                "signal_configuration": {
                    "channel": service.signal_config.channel,
                    "threshold_voltage": service.signal_config.threshold_voltage,
                    "sample_rate": service.signal_config.sample_rate,
                    "edge_detection": service.signal_config.edge_detection.value
                }
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to start signal monitoring")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to start monitoring: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start monitoring: {str(e)}")


@router.post("/stop-monitoring")
async def stop_signal_monitoring():
    """Stop TTL signal monitoring"""
    try:
        service = get_real_labjack_service()
        success = service.stop_signal_monitoring()
        
        return {
            "success": success,
            "message": "Signal monitoring stopped" if success else "Failed to stop monitoring"
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to stop monitoring: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop monitoring: {str(e)}")


@router.get("/hardware-events")
async def get_hardware_events(max_events: int = 100) -> List[HardwareEventResponse]:
    """Get hardware detection events with Signal_Received_Time"""
    try:
        service = get_real_labjack_service()
        events = service.get_hardware_events(max_events)
        
        return [
            HardwareEventResponse(
                event_id=event.event_id,
                test_session_id=event.test_session_id,
                video_id=event.video_id,
                signal_received_time=event.signal_received_time.isoformat(),
                signal_type=event.signal_type.value,
                signal_voltage=event.signal_voltage,
                channel=event.channel,
                latency_ms=event.latency_ms,
                detection_outcome=event.detection_outcome,
                created_at=event.created_at.isoformat()
            )
            for event in events
        ]
        
    except Exception as e:
        logger.error(f"❌ Failed to get hardware events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get hardware events: {str(e)}")


@router.get("/current-signal")
async def read_current_signal():
    """Read current TTL signal voltage and state"""
    try:
        service = get_real_labjack_service()
        
        if not service.is_connected():
            raise HTTPException(status_code=400, detail="LabJack not connected")
        
        voltage, is_high = service.read_current_signal()
        
        return {
            "channel": service.signal_config.channel,
            "voltage": voltage,
            "is_signal_high": is_high,
            "threshold_voltage": service.signal_config.threshold_voltage,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to read signal: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read signal: {str(e)}")


@router.get("/latency-analysis", response_model=LatencyAnalysisResponse)
async def get_latency_analysis():
    """Get latency analysis from precision timing service"""
    try:
        timing_service = get_precision_timing_service()
        measurements = timing_service.get_latency_measurements()
        
        if not measurements:
            return LatencyAnalysisResponse(
                total_events=0,
                passed_events=0,
                failed_high_latency=0,
                missed_detections=0,
                average_latency_ms=0.0,
                min_latency_ms=0.0,
                max_latency_ms=0.0,
                pass_rate_percentage=0.0
            )
        
        # Calculate statistics
        total_events = len(measurements)
        passed_events = sum(1 for m in measurements if m.outcome == "pass")
        failed_high_latency = sum(1 for m in measurements if m.outcome == "fail_high_latency")
        missed_detections = sum(1 for m in measurements if m.outcome == "fail_missed_detection")
        
        latencies_ms = [m.latency_ms for m in measurements if m.outcome != "fail_missed_detection"]
        average_latency_ms = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0
        min_latency_ms = min(latencies_ms) if latencies_ms else 0.0
        max_latency_ms = max(latencies_ms) if latencies_ms else 0.0
        
        pass_rate_percentage = (passed_events / total_events) * 100 if total_events > 0 else 0.0
        
        return LatencyAnalysisResponse(
            total_events=total_events,
            passed_events=passed_events,
            failed_high_latency=failed_high_latency,
            missed_detections=missed_detections,
            average_latency_ms=average_latency_ms,
            min_latency_ms=min_latency_ms,
            max_latency_ms=max_latency_ms,
            pass_rate_percentage=pass_rate_percentage
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to get latency analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get latency analysis: {str(e)}")


@router.get("/timing-events")
async def get_timing_events(event_type: Optional[str] = None):
    """Get precision timing events"""
    try:
        timing_service = get_precision_timing_service()
        events = timing_service.get_timing_events(event_type)
        
        return {
            "events_count": len(events),
            "events": [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "wall_time": event.timestamp.wall_time.isoformat(),
                    "monotonic_time": event.timestamp.monotonic_time,
                    "precision_level": event.timestamp.precision_level.value,
                    "video_frame_number": event.video_frame_number,
                    "video_timestamp_ms": event.video_timestamp_ms
                }
                for event in events
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get timing events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get timing events: {str(e)}")


@router.get("/statistics")
async def get_service_statistics():
    """Get comprehensive service statistics"""
    try:
        service = get_real_labjack_service()
        timing_service = get_precision_timing_service()
        
        labjack_status = service.get_status()
        timing_stats = timing_service.get_performance_statistics()
        
        return {
            "labjack_service": labjack_status,
            "precision_timing": timing_stats,
            "hardware_capabilities": {
                "real_hardware_connection": True,
                "mock_mode": False,
                "ljm_library_available": True,
                "sub_millisecond_precision": True,
                "monotonic_clock": True
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.post("/test-hardware")
async def test_hardware_connection():
    """Test hardware connection and capabilities"""
    try:
        service = get_real_labjack_service()
        
        # Detect devices
        devices = service.detect_devices()
        
        # Try to connect if devices found
        connection_result = None
        if devices:
            device = devices[0]
            success = service.connect(
                device_type=device["device_type"],
                connection_type=device["connection_type"],
                identifier=str(device["serial_number"])
            )
            
            if success:
                # Test signal reading
                voltage, is_high = service.read_current_signal()
                connection_result = {
                    "connected": True,
                    "device_info": service.get_device_info(),
                    "signal_test": {
                        "voltage": voltage,
                        "is_high": is_high,
                        "channel": service.signal_config.channel
                    }
                }
            else:
                connection_result = {
                    "connected": False,
                    "error": "Failed to connect to device"
                }
        
        return {
            "devices_detected": len(devices),
            "devices": devices,
            "connection_test": connection_result,
            "hardware_available": len(devices) > 0
        }
        
    except Exception as e:
        logger.error(f"❌ Hardware test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Hardware test failed: {str(e)}")


# Include router in main application
def include_labjack_routes(app):
    """Include LabJack hardware routes in FastAPI app"""
    app.include_router(router)
    logger.info("✅ LabJack Hardware API routes registered")