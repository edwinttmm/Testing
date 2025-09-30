"""
Raw LabJack Logging API Endpoints

This module provides REST API endpoints for controlling raw LabJack data logging
with smart compression and high-frequency data capture capabilities.

Key Features:
- Session management (start/stop/status)
- Real-time performance monitoring
- Compression statistics and analytics  
- Data retrieval and export
- Integration with existing test sessions
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import logging
import io
import json
import asyncio

# Database imports
from database import get_db
from models import TestSession

# Service imports
from services.raw_labjack_logger import get_raw_labjack_logger, RawLabJackLogger, BufferConfig, TimingConfig
from services.raw_labjack_compression import CompressionAlgorithm
from src.models.raw_labjack_models import (
    RawLabJackSession, RawLabJackBuffer, CompressionStatistics,
    DataQuality, BufferStatus
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/raw-labjack", tags=["Raw LabJack Logging"])


# Pydantic models for API requests/responses
class RawLoggingSessionRequest(BaseModel):
    """Request model for starting raw logging session"""
    session_name: str = Field(..., description="Unique session name")
    channels: List[str] = Field(default=["AIN0"], description="LabJack channels to capture")
    sample_rate: int = Field(default=1000, ge=1, le=10000, description="Sampling rate in Hz")
    test_session_id: Optional[str] = Field(None, description="Associated test session ID")
    compression_algorithm: str = Field(default="adaptive", description="Compression algorithm")
    compression_level: int = Field(default=6, ge=1, le=9, description="Compression level")
    buffer_size_samples: int = Field(default=10000, ge=1000, le=100000, description="Buffer size in samples")
    detection_threshold: Optional[float] = Field(None, description="Voltage detection threshold")
    
    class Config:
        schema_extra = {
            "example": {
                "session_name": "HIL_Test_Session_001",
                "channels": ["AIN0", "AIN1"],
                "sample_rate": 1000,
                "test_session_id": "test-session-123",
                "compression_algorithm": "adaptive",
                "compression_level": 6,
                "buffer_size_samples": 10000,
                "detection_threshold": 2.5
            }
        }


class RawLoggingSessionResponse(BaseModel):
    """Response model for raw logging session operations"""
    session_id: str
    session_name: str
    is_active: bool
    started_at: Optional[datetime]
    channels: List[str]
    sample_rate: float
    compression_algorithm: str
    samples_captured: int
    samples_lost: int
    buffers_processed: int
    average_compression_ratio: float
    actual_sample_rate: float
    
    class Config:
        from_attributes = True


class CompressionStatisticsResponse(BaseModel):
    """Response model for compression statistics"""
    algorithms_used: Dict[str, int]
    average_compression_ratios: Dict[str, float]
    compression_times_ms: Dict[str, float]
    overall_compression_ratio: float
    throughput_samples_per_second: float
    buffer_utilization_percent: float
    compression_efficiency_score: float
    
    class Config:
        from_attributes = True


class PerformanceMetricsResponse(BaseModel):
    """Response model for performance metrics"""
    memory_usage_mb: float
    cpu_usage_percent: float
    buffer_utilization: float
    active_sessions: int
    total_buffers_in_memory: int
    queue_sizes: Dict[str, int]
    compression_stats: Dict[str, Any]
    
    class Config:
        from_attributes = True


# Helper functions
def _validate_compression_algorithm(algorithm: str) -> CompressionAlgorithm:
    """Validate and convert compression algorithm string"""
    algorithm_map = {
        "none": CompressionAlgorithm.NONE,
        "zlib": CompressionAlgorithm.ZLIB,
        "lzma": CompressionAlgorithm.LZMA,
        "delta_rle": CompressionAlgorithm.DELTA_RLE,
        "quantized": CompressionAlgorithm.QUANTIZED,
        "adaptive": CompressionAlgorithm.ADAPTIVE
    }
    
    if algorithm.lower() not in algorithm_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid compression algorithm: {algorithm}. "
                   f"Valid options: {list(algorithm_map.keys())}"
        )
    
    return algorithm_map[algorithm.lower()]


def _get_logger() -> RawLabJackLogger:
    """Get raw LabJack logger instance"""
    try:
        return get_raw_labjack_logger()
    except Exception as e:
        logger.error(f"Failed to get raw LabJack logger: {e}")
        raise HTTPException(
            status_code=503,
            detail="Raw LabJack logging service unavailable"
        )


# API Endpoints

@router.post("/sessions", response_model=Dict[str, Any])
async def start_raw_logging_session(
    request: RawLoggingSessionRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Start a new raw LabJack data logging session
    
    Creates a new high-frequency data capture session with smart compression
    and begins capturing raw voltage data from specified channels.
    """
    try:
        raw_logger = _get_logger()
        
        # Validate compression algorithm
        compression_algorithm = _validate_compression_algorithm(request.compression_algorithm)
        
        # Validate test session if provided
        if request.test_session_id:
            test_session = db.query(TestSession).filter_by(id=request.test_session_id).first()
            if not test_session:
                raise HTTPException(
                    status_code=404,
                    detail=f"Test session not found: {request.test_session_id}"
                )
        
        # Start logging session
        session_id = raw_logger.start_session(
            session_name=request.session_name,
            channels=request.channels,
            sample_rate=request.sample_rate,
            test_session_id=request.test_session_id,
            compression_algorithm=compression_algorithm,
            compression_level=request.compression_level,
            buffer_size_samples=request.buffer_size_samples,
            detection_threshold=request.detection_threshold
        )
        
        if not session_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to start raw logging session"
            )
        
        # Get session status
        session_status = raw_logger.get_session_status(session_id)
        if not session_status:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve session status"
            )
        
        logger.info(f"✅ Raw logging session started: {request.session_name} (ID: {session_id})")
        
        return {
            "success": True,
            "message": f"Raw logging session started successfully",
            "session_id": session_id,
            "session": session_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting raw logging session: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@router.get("/sessions", response_model=List[RawLoggingSessionResponse])
async def list_active_sessions() -> List[RawLoggingSessionResponse]:
    """
    List all active raw LabJack logging sessions
    
    Returns a list of currently running data capture sessions
    with their current status and performance metrics.
    """
    try:
        raw_logger = _get_logger()
        sessions = raw_logger.get_active_sessions()
        
        return [RawLoggingSessionResponse(**session) for session in sessions]
        
    except Exception as e:
        logger.error(f"Error listing active sessions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=RawLoggingSessionResponse)
async def get_session_status(session_id: str) -> RawLoggingSessionResponse:
    """
    Get status and metrics for specific raw logging session
    
    Returns detailed information about a running or completed
    data capture session including performance metrics.
    """
    try:
        raw_logger = _get_logger()
        session_status = raw_logger.get_session_status(session_id)
        
        if not session_status:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )
        
        return RawLoggingSessionResponse(**session_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@router.post("/sessions/{session_id}/stop", response_model=Dict[str, Any])
async def stop_raw_logging_session(session_id: str) -> Dict[str, Any]:
    """
    Stop raw LabJack data logging session
    
    Stops data capture, flushes remaining buffers to database,
    and returns comprehensive session statistics.
    """
    try:
        raw_logger = _get_logger()
        
        # Check if session exists
        session_status = raw_logger.get_session_status(session_id)
        if not session_status:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )
        
        # Stop session
        statistics = raw_logger.stop_session(session_id)
        
        if 'error' in statistics:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to stop session: {statistics['error']}"
            )
        
        logger.info(f"⏹️ Raw logging session stopped: {session_id}")
        
        return {
            "success": True,
            "message": "Raw logging session stopped successfully",
            "session_id": session_id,
            "statistics": statistics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping session: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@router.get("/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics() -> PerformanceMetricsResponse:
    """
    Get overall system performance metrics
    
    Returns real-time performance metrics including memory usage,
    CPU utilization, compression statistics, and queue status.
    """
    try:
        raw_logger = _get_logger()
        metrics = raw_logger.get_performance_metrics()
        
        # Flatten system metrics
        system_metrics = metrics.get('system_metrics', {})
        
        response_data = {
            "memory_usage_mb": system_metrics.get('memory_usage_mb', 0.0),
            "cpu_usage_percent": system_metrics.get('cpu_usage_percent', 0.0),
            "buffer_utilization": system_metrics.get('buffer_utilization', 0.0),
            "active_sessions": metrics.get('active_sessions', 0),
            "total_buffers_in_memory": metrics.get('total_buffers_in_memory', 0),
            "queue_sizes": metrics.get('queue_sizes', {}),
            "compression_stats": metrics.get('compression_stats', {})
        }
        
        return PerformanceMetricsResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@router.get("/sessions/{session_id}/buffers", response_model=Dict[str, Any])
async def get_session_buffers(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=1000, description="Maximum buffers to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    status_filter: Optional[str] = Query(default=None, description="Filter by buffer status"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get compressed data buffers for session
    
    Returns a list of compressed data buffers with metadata
    for analysis and debugging purposes.
    """
    try:
        # Validate session exists
        session = db.query(RawLabJackSession).filter_by(id=session_id).first()
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )
        
        # Build query
        query = db.query(RawLabJackBuffer).filter_by(session_id=session_id)
        
        # Apply status filter
        if status_filter:
            try:
                status_enum = BufferStatus(status_filter.lower())
                query = query.filter_by(buffer_status=status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid buffer status: {status_filter}"
                )
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination and get buffers
        buffers = query.order_by(RawLabJackBuffer.buffer_sequence).offset(offset).limit(limit).all()
        
        # Convert to dict format (excluding compressed data)
        buffer_list = [buffer.to_dict() for buffer in buffers]
        
        return {
            "session_id": session_id,
            "total_buffers": total_count,
            "returned_buffers": len(buffer_list),
            "offset": offset,
            "limit": limit,
            "buffers": buffer_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session buffers: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@router.get("/sessions/{session_id}/statistics", response_model=Dict[str, Any])
async def get_session_compression_statistics(
    session_id: str,
    time_window_hours: int = Query(default=1, ge=1, le=24, description="Time window in hours"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get detailed compression statistics for session
    
    Returns compression performance analytics including
    algorithm effectiveness and data quality metrics.
    """
    try:
        # Validate session exists
        session = db.query(RawLabJackSession).filter_by(id=session_id).first()
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )
        
        # Calculate time window
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=time_window_hours)
        
        # Get compression statistics
        stats = db.query(CompressionStatistics).filter(
            CompressionStatistics.session_id == session_id,
            CompressionStatistics.window_start >= start_time,
            CompressionStatistics.window_end <= end_time
        ).order_by(CompressionStatistics.computed_at).all()
        
        if not stats:
            # Generate basic statistics from buffers
            buffers = db.query(RawLabJackBuffer).filter(
                RawLabJackBuffer.session_id == session_id,
                RawLabJackBuffer.created_at >= start_time
            ).all()
            
            if buffers:
                total_raw_bytes = sum(b.raw_data_size_bytes for b in buffers)
                total_compressed_bytes = sum(b.compressed_data_size_bytes for b in buffers)
                compression_ratio = total_raw_bytes / max(total_compressed_bytes, 1)
                
                return {
                    "session_id": session_id,
                    "time_window_hours": time_window_hours,
                    "total_buffers": len(buffers),
                    "total_raw_bytes": total_raw_bytes,
                    "total_compressed_bytes": total_compressed_bytes,
                    "overall_compression_ratio": compression_ratio,
                    "detailed_statistics": "Limited statistics - session recently started"
                }
            else:
                return {
                    "session_id": session_id,
                    "time_window_hours": time_window_hours,
                    "message": "No data available for specified time window"
                }
        
        # Aggregate statistics
        latest_stats = stats[-1]  # Most recent statistics
        
        return {
            "session_id": session_id,
            "time_window_hours": time_window_hours,
            "statistics": latest_stats.to_dict(),
            "historical_data": [stat.to_dict() for stat in stats[-10:]]  # Last 10 entries
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting compression statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@router.get("/sessions/{session_id}/data/export")
async def export_session_data(
    session_id: str,
    format: str = Query(default="json", description="Export format: json, csv, binary"),
    start_time: Optional[datetime] = Query(default=None, description="Start time filter"),
    end_time: Optional[datetime] = Query(default=None, description="End time filter"),
    include_raw_data: bool = Query(default=False, description="Include compressed raw data"),
    db: Session = Depends(get_db)
) -> StreamingResponse:
    """
    Export raw LabJack session data
    
    Exports captured data in specified format for analysis.
    Supports JSON metadata export and binary raw data export.
    """
    try:
        # Validate session exists
        session = db.query(RawLabJackSession).filter_by(id=session_id).first()
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )
        
        # Build buffer query
        query = db.query(RawLabJackBuffer).filter_by(session_id=session_id)
        
        if start_time:
            query = query.filter(RawLabJackBuffer.start_timestamp >= start_time)
        if end_time:
            query = query.filter(RawLabJackBuffer.end_timestamp <= end_time)
        
        buffers = query.order_by(RawLabJackBuffer.buffer_sequence).all()
        
        if format.lower() == "json":
            # JSON export with metadata
            export_data = {
                "session": session.to_dict(),
                "export_time": datetime.now(timezone.utc).isoformat(),
                "buffer_count": len(buffers),
                "buffers": [buffer.to_dict() for buffer in buffers]
            }
            
            # Create JSON stream
            json_str = json.dumps(export_data, indent=2, default=str)
            stream = io.StringIO(json_str)
            
            return StreamingResponse(
                io.BytesIO(json_str.encode('utf-8')),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=session_{session_id[:8]}_export.json"}
            )
        
        elif format.lower() == "csv":
            # CSV export with buffer metadata
            import csv
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                'buffer_id', 'sequence', 'start_timestamp', 'end_timestamp',
                'sample_count', 'channels', 'compression_algorithm',
                'compression_ratio', 'data_quality', 'signal_stats'
            ])
            
            # Data rows
            for buffer in buffers:
                writer.writerow([
                    buffer.id, buffer.buffer_sequence,
                    buffer.start_timestamp.isoformat(), buffer.end_timestamp.isoformat(),
                    buffer.sample_count, ','.join(buffer.channels),
                    buffer.compression_algorithm.value,
                    buffer.compression_ratio, buffer.data_quality.value,
                    json.dumps(buffer.signal_statistics) if buffer.signal_statistics else ''
                ])
            
            output.seek(0)
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode('utf-8')),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=session_{session_id[:8]}_export.csv"}
            )
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported export format: {format}. Supported: json, csv"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting session data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@router.get("/health", response_model=Dict[str, Any])
async def get_health_status() -> Dict[str, Any]:
    """
    Get health status of raw LabJack logging service
    
    Returns service health information including hardware
    connectivity, system resources, and service status.
    """
    try:
        raw_logger = _get_logger()
        
        # Get performance metrics
        metrics = raw_logger.get_performance_metrics()
        
        # Check LabJack hardware status
        labjack_status = raw_logger.labjack_service.get_status()
        
        health_status = {
            "service_status": "healthy",
            "labjack_connected": labjack_status.connected,
            "labjack_mode": labjack_status.mode.value,
            "active_sessions": len(raw_logger.active_sessions),
            "system_metrics": metrics.get('system_metrics', {}),
            "service_uptime": "Available",  # Could track actual uptime
            "hardware_info": labjack_status.device_info
        }
        
        # Determine overall health
        if not labjack_status.connected:
            health_status["service_status"] = "degraded"
            health_status["warning"] = "LabJack hardware not connected"
        
        memory_usage = metrics.get('system_metrics', {}).get('memory_usage_mb', 0)
        if memory_usage > 1000:  # > 1GB
            health_status["service_status"] = "warning"
            health_status["warning"] = f"High memory usage: {memory_usage:.1f}MB"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "service_status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Integration endpoint for existing detection system
@router.post("/sessions/{session_id}/integrate-detection", response_model=Dict[str, Any])
async def integrate_with_detection_system(
    session_id: str,
    enable_callbacks: bool = Query(default=True, description="Enable detection callbacks"),
    threshold: float = Query(default=2.5, description="Detection voltage threshold")
) -> Dict[str, Any]:
    """
    Integrate raw logging session with detection event system
    
    Enables real-time detection callbacks from raw voltage data
    to existing detection event processing pipeline.
    """
    try:
        raw_logger = _get_logger()
        
        # Check if session exists
        session_status = raw_logger.get_session_status(session_id)
        if not session_status:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )
        
        # Update session configuration
        raw_logger.session_configs[session_id]['detection_threshold'] = threshold
        
        if enable_callbacks:
            # Add detection callback if not already present
            from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
            
            def detection_callback(detection_data):
                """Forward detection to dedicated monitor"""
                try:
                    # Convert raw detection to format expected by detection system
                    monitor = get_dedicated_labjack_monitor()
                    
                    # Create mock LabJack event for compatibility
                    class MockLabJackEvent:
                        def __init__(self, data):
                            self.timestamp = data['timestamp']
                            self.voltage = data['voltage']
                            self.channel = f"AIN{data['channel']}"
                    
                    mock_event = MockLabJackEvent(detection_data)
                    
                    # Find active HIL session for this raw session
                    test_session_id = raw_logger.session_configs[session_id].get('test_session_id')
                    if test_session_id:
                        monitor._handle_detection_with_video_sync(test_session_id, mock_event)
                        
                except Exception as e:
                    logger.error(f"Detection callback integration error: {e}")
            
            raw_logger.add_detection_callback(detection_callback)
            
            logger.info(f"✅ Detection integration enabled for session {session_id}")
            
            return {
                "success": True,
                "message": "Detection integration enabled",
                "session_id": session_id,
                "threshold": threshold,
                "callbacks_active": True
            }
        else:
            # Remove callbacks
            # Note: This is simplified - in production, might need more sophisticated callback management
            raw_logger.detection_callbacks.clear()
            
            return {
                "success": True,
                "message": "Detection integration disabled",
                "session_id": session_id,
                "callbacks_active": False
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error integrating detection system: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


# Add router to main application
def include_raw_labjack_routes(app):
    """Include raw LabJack routes in main application"""
    app.include_router(router)
    logger.info("✅ Raw LabJack API endpoints registered")


# Export router
__all__ = ["router", "include_raw_labjack_routes"]