"""
Raw Timing Data API Endpoints
=============================

Provides access to microsecond-precision raw LabJack timing data from the 
hybrid logging system. Shows the actual continuous voltage detection instead
of throttled 18.8Hz events.

Key Features:
- Raw voltage transitions with microsecond precision
- Continuous data stream (1000Hz sampling vs 18.8Hz video sync)
- Compression statistics and data quality metrics
- Timeline correlation between raw and video-synchronized events
- Export functionality for detailed analysis
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_, func, desc

from database import get_db
from models import TestSession, DetectionEvent
from src.services.hybrid_query_service import get_hybrid_query_service, QueryStrategy
from src.models.labjack_raw_compression import (
    LabJackRawSession, VoltageTransition, VoltageRunPeriod,
    DetectionEventCompressed, CompressionStatistics, VoltageTransitionType
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/raw-timing", tags=["Raw Timing Data"])

# Initialize hybrid query service
hybrid_query_service = get_hybrid_query_service()


@router.get("/test-sessions/{session_id}/raw-data")
async def get_raw_timing_data(
    session_id: str,
    include_transitions: bool = Query(True, description="Include voltage transitions"),
    include_run_periods: bool = Query(True, description="Include constant voltage periods"),
    start_time_us: Optional[int] = Query(None, description="Start time in microseconds"),
    end_time_us: Optional[int] = Query(None, description="End time in microseconds"),
    max_transitions: int = Query(1000, description="Maximum transitions to return"),
    min_confidence: float = Query(0.0, description="Minimum detection confidence"),
    db: Session = Depends(get_db)
):
    """
    Get raw timing data with microsecond precision from hybrid logging system.
    
    Returns the actual continuous voltage detection data instead of just
    video-frame-synchronized events, showing sub-millisecond timing precision.
    """
    try:
        # Find the raw session for this test session
        raw_session = db.query(LabJackRawSession).filter(
            LabJackRawSession.session_id == session_id
        ).first()
        
        if not raw_session:
            # Fallback to legacy data if no raw session exists
            return await _get_legacy_timing_data(session_id, db)
        
        # Build response data structure
        response = {
            "session_id": session_id,
            "data_source": "hybrid_raw_compression",
            "timing_precision": "microsecond",
            "sample_rate_actual_hz": raw_session.actual_sample_rate_hz or raw_session.sample_rate_hz,
            "session_info": {
                "start_timestamp_us": raw_session.start_timestamp_us,
                "end_timestamp_us": raw_session.end_timestamp_us,
                "duration_us": raw_session.duration_us,
                "total_samples": raw_session.total_raw_samples,
                "compression_ratio": raw_session.compression_ratio,
                "data_quality_score": raw_session.data_quality_score
            }
        }
        
        # Get voltage transitions (the raw detection events)
        if include_transitions:
            transitions_query = db.query(VoltageTransition).filter(
                VoltageTransition.session_id == raw_session.id
            )
            
            # Apply time filters
            if start_time_us:
                transitions_query = transitions_query.filter(
                    VoltageTransition.timestamp_us >= start_time_us
                )
            if end_time_us:
                transitions_query = transitions_query.filter(
                    VoltageTransition.timestamp_us <= end_time_us
                )
            
            # Apply confidence filter
            if min_confidence > 0.0:
                transitions_query = transitions_query.filter(
                    VoltageTransition.detection_confidence >= min_confidence
                )
            
            # Get transitions
            transitions = transitions_query.order_by(
                VoltageTransition.timestamp_us
            ).limit(max_transitions).all()
            
            # Format transitions with microsecond precision
            response["voltage_transitions"] = []
            for transition in transitions:
                response["voltage_transitions"].append({
                    "id": transition.id,
                    "timestamp_us": transition.timestamp_us,
                    "timestamp_ms": transition.timestamp_us / 1000.0,
                    "channel": transition.channel,
                    "voltage_before_v": float(transition.voltage_before_v),
                    "voltage_after_v": float(transition.voltage_after_v),
                    "voltage_delta_v": float(transition.voltage_delta_v),
                    "transition_type": transition.transition_type.value,
                    "is_detection_event": transition.is_detection_event,
                    "detection_confidence": transition.detection_confidence,
                    "signal_quality_score": transition.signal_quality_score,
                    "transition_duration_us": transition.transition_duration_us,
                    "slope_v_per_s": transition.slope_v_per_s,
                    "sequence_number": transition.sequence_number,
                    "time_since_last_us": transition.time_since_last_transition_us
                })
        
        # Get voltage run periods (constant voltage segments)
        if include_run_periods:
            runs_query = db.query(VoltageRunPeriod).filter(
                VoltageRunPeriod.session_id == raw_session.id
            )
            
            # Apply time filters
            if start_time_us:
                runs_query = runs_query.filter(
                    VoltageRunPeriod.start_timestamp_us >= start_time_us
                )
            if end_time_us:
                runs_query = runs_query.filter(
                    VoltageRunPeriod.end_timestamp_us <= end_time_us
                )
            
            runs = runs_query.order_by(
                VoltageRunPeriod.start_timestamp_us
            ).all()
            
            response["voltage_run_periods"] = []
            for run in runs:
                response["voltage_run_periods"].append({
                    "id": run.id,
                    "start_timestamp_us": run.start_timestamp_us,
                    "end_timestamp_us": run.end_timestamp_us,
                    "duration_us": run.duration_us,
                    "channel": run.channel,
                    "steady_voltage_v": float(run.steady_voltage_v),
                    "voltage_min_v": float(run.voltage_min_v) if run.voltage_min_v else None,
                    "voltage_max_v": float(run.voltage_max_v) if run.voltage_max_v else None,
                    "sample_count": run.sample_count,
                    "sequence_number": run.sequence_number,
                    "confidence_score": run.confidence_score
                })
        
        # Get compression statistics
        compression_stats = db.query(CompressionStatistics).filter(
            CompressionStatistics.session_id == raw_session.id
        ).order_by(desc(CompressionStatistics.calculated_at)).first()
        
        if compression_stats:
            response["compression_statistics"] = {
                "achieved_compression_ratio": compression_stats.achieved_compression_ratio,
                "signal_fidelity_score": compression_stats.signal_fidelity_score,
                "data_loss_estimate": compression_stats.data_loss_estimate,
                "throughput_samples_per_second": compression_stats.throughput_samples_per_second,
                "raw_data_size_bytes": compression_stats.raw_data_size_bytes,
                "compressed_data_size_bytes": compression_stats.compressed_data_size_bytes,
                "storage_efficiency_percent": (
                    compression_stats.compressed_data_size_bytes / 
                    max(1, compression_stats.raw_data_size_bytes) * 100
                )
            }
        
        # Get timing correlation with legacy detection events
        correlation_data = await _get_timing_correlation(session_id, raw_session, db)
        response["timing_correlation"] = correlation_data
        
        logger.info(f"Raw timing data retrieved for session {session_id}: "
                   f"{len(response.get('voltage_transitions', []))} transitions, "
                   f"{len(response.get('voltage_run_periods', []))} runs")
        
        return response
        
    except Exception as e:
        logger.error(f"Error retrieving raw timing data for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve raw timing data: {str(e)}")


async def _get_legacy_timing_data(session_id: str, db: Session) -> Dict[str, Any]:
    """Fallback to legacy detection events when no raw data available"""
    
    detection_events = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id
    ).order_by(DetectionEvent.timestamp).all()
    
    # Convert legacy events to raw timing format
    legacy_transitions = []
    for event in detection_events:
        # Simulate microsecond precision from second-precision timestamps
        timestamp_us = int(event.timestamp * 1_000_000) if event.timestamp else 0
        
        legacy_transitions.append({
            "id": event.id,
            "timestamp_us": timestamp_us,
            "timestamp_ms": timestamp_us / 1000.0,
            "channel": event.detection_channel or "AIN0",
            "voltage_before_v": 0.0,  # Unknown in legacy data
            "voltage_after_v": event.labjack_voltage or event.voltage_level or 5.0,
            "voltage_delta_v": event.labjack_voltage or event.voltage_level or 5.0,
            "transition_type": "rising_edge",  # Assume rising edge for detections
            "is_detection_event": True,
            "detection_confidence": event.confidence or 1.0,
            "signal_quality_score": 1.0,  # Unknown in legacy data
            "transition_duration_us": None,
            "slope_v_per_s": None,
            "sequence_number": 0,
            "time_since_last_us": None,
            "data_source": "legacy_fallback"
        })
    
    return {
        "session_id": session_id,
        "data_source": "legacy_detection_events",
        "timing_precision": "second",
        "sample_rate_actual_hz": 18.8,  # Video frame rate equivalent
        "session_info": {
            "total_samples": len(detection_events),
            "data_quality_score": 0.5  # Medium quality for legacy data
        },
        "voltage_transitions": legacy_transitions,
        "voltage_run_periods": [],
        "compression_statistics": {
            "note": "No compression statistics available for legacy data"
        },
        "timing_correlation": {
            "note": "Legacy data only - no correlation with video timing"
        }
    }


async def _get_timing_correlation(
    session_id: str, 
    raw_session: LabJackRawSession, 
    db: Session
) -> Dict[str, Any]:
    """Get correlation between raw timing data and video-synchronized events"""
    
    try:
        # Get legacy detection events for comparison
        legacy_events = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).order_by(DetectionEvent.timestamp).all()
        
        # Get detection transitions from raw data
        detection_transitions = db.query(VoltageTransition).filter(
            and_(
                VoltageTransition.session_id == raw_session.id,
                VoltageTransition.is_detection_event == True
            )
        ).order_by(VoltageTransition.timestamp_us).all()
        
        correlation = {
            "legacy_events_count": len(legacy_events),
            "raw_detection_transitions_count": len(detection_transitions),
            "timing_comparison": [],
            "frequency_analysis": {}
        }
        
        # Calculate timing differences
        if legacy_events and detection_transitions:
            timing_diffs = []
            
            # Match events by proximity (within 100ms)
            for legacy in legacy_events:
                if not legacy.timestamp:
                    continue
                    
                legacy_us = int(legacy.timestamp * 1_000_000)
                closest_transition = None
                min_diff = float('inf')
                
                for transition in detection_transitions:
                    diff = abs(transition.timestamp_us - legacy_us)
                    if diff < min_diff and diff < 100_000:  # 100ms tolerance
                        min_diff = diff
                        closest_transition = transition
                
                if closest_transition:
                    timing_diffs.append({
                        "legacy_timestamp_us": legacy_us,
                        "raw_timestamp_us": closest_transition.timestamp_us,
                        "difference_us": closest_transition.timestamp_us - legacy_us,
                        "difference_ms": (closest_transition.timestamp_us - legacy_us) / 1000.0,
                        "detection_confidence": closest_transition.detection_confidence
                    })
            
            correlation["timing_comparison"] = timing_diffs
            
            # Frequency analysis
            if timing_diffs:
                raw_intervals = []
                for i in range(1, len(detection_transitions)):
                    interval_ms = (detection_transitions[i].timestamp_us - 
                                  detection_transitions[i-1].timestamp_us) / 1000.0
                    raw_intervals.append(interval_ms)
                
                legacy_intervals = []
                for i in range(1, len(legacy_events)):
                    if legacy_events[i].timestamp and legacy_events[i-1].timestamp:
                        interval_ms = (legacy_events[i].timestamp - 
                                      legacy_events[i-1].timestamp) * 1000.0
                        legacy_intervals.append(interval_ms)
                
                correlation["frequency_analysis"] = {
                    "raw_average_interval_ms": sum(raw_intervals) / len(raw_intervals) if raw_intervals else 0,
                    "legacy_average_interval_ms": sum(legacy_intervals) / len(legacy_intervals) if legacy_intervals else 0,
                    "raw_frequency_hz": 1000.0 / (sum(raw_intervals) / len(raw_intervals)) if raw_intervals else 0,
                    "legacy_frequency_hz": 1000.0 / (sum(legacy_intervals) / len(legacy_intervals)) if legacy_intervals else 0
                }
        
        return correlation
        
    except Exception as e:
        logger.warning(f"Failed to calculate timing correlation: {e}")
        return {
            "error": f"Correlation calculation failed: {str(e)}"
        }


@router.get("/test-sessions/{session_id}/compression-stats")
async def get_compression_statistics(
    session_id: str,
    time_range_hours: int = Query(24, description="Time range for statistics"),
    db: Session = Depends(get_db)
):
    """Get detailed compression performance statistics"""
    
    try:
        # Use hybrid query service for compression statistics
        result = await hybrid_query_service.query_compression_statistics(
            time_range_hours=time_range_hours,
            session_id=session_id,
            db=db
        )
        
        return {
            "session_id": session_id,
            "statistics": result.data,
            "performance_metrics": hybrid_query_service.get_performance_metrics(),
            "data_sources": result.data_sources,
            "execution_time_ms": result.execution_time_ms
        }
        
    except Exception as e:
        logger.error(f"Error retrieving compression statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-sessions/{session_id}/timeline-data")
async def get_timeline_data(
    session_id: str,
    resolution_us: int = Query(1000, description="Timeline resolution in microseconds"),
    include_video_sync: bool = Query(True, description="Include video sync events"),
    db: Session = Depends(get_db)
):
    """
    Get timeline data for visualization showing both raw and video-synchronized events
    """
    
    try:
        # Get raw session
        raw_session = db.query(LabJackRawSession).filter(
            LabJackRawSession.session_id == session_id
        ).first()
        
        if not raw_session:
            raise HTTPException(status_code=404, detail="No raw timing data found for session")
        
        # Build timeline with specified resolution
        start_us = raw_session.start_timestamp_us
        end_us = raw_session.end_timestamp_us or (start_us + (raw_session.duration_us or 0))
        
        # Get voltage transitions in time buckets
        timeline_points = []
        current_us = start_us
        
        while current_us < end_us:
            window_end = min(current_us + resolution_us, end_us)
            
            # Count transitions in this window
            transitions_in_window = db.query(func.count(VoltageTransition.id)).filter(
                and_(
                    VoltageTransition.session_id == raw_session.id,
                    VoltageTransition.timestamp_us >= current_us,
                    VoltageTransition.timestamp_us < window_end
                )
            ).scalar()
            
            # Count detection events in window
            detection_transitions = db.query(func.count(VoltageTransition.id)).filter(
                and_(
                    VoltageTransition.session_id == raw_session.id,
                    VoltageTransition.timestamp_us >= current_us,
                    VoltageTransition.timestamp_us < window_end,
                    VoltageTransition.is_detection_event == True
                )
            ).scalar()
            
            timeline_points.append({
                "timestamp_us": current_us,
                "timestamp_ms": current_us / 1000.0,
                "window_duration_us": resolution_us,
                "total_transitions": transitions_in_window,
                "detection_transitions": detection_transitions,
                "transition_rate_hz": (transitions_in_window / (resolution_us / 1_000_000)) if resolution_us > 0 else 0
            })
            
            current_us += resolution_us
        
        # Get video sync events if requested
        video_sync_events = []
        if include_video_sync:
            legacy_events = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id
            ).order_by(DetectionEvent.timestamp).all()
            
            for event in legacy_events:
                if event.timestamp:
                    video_sync_events.append({
                        "timestamp_us": int(event.timestamp * 1_000_000),
                        "timestamp_ms": event.timestamp * 1000.0,
                        "frame_number": getattr(event, 'frame_number', None),
                        "latency_ms": getattr(event, 'actual_latency_ms', None),
                        "voltage_level": event.voltage_level or event.labjack_voltage
                    })
        
        return {
            "session_id": session_id,
            "resolution_us": resolution_us,
            "timeline_start_us": start_us,
            "timeline_end_us": end_us,
            "duration_us": end_us - start_us,
            "timeline_points": timeline_points,
            "video_sync_events": video_sync_events,
            "summary": {
                "total_timeline_points": len(timeline_points),
                "total_video_sync_events": len(video_sync_events),
                "peak_transition_rate_hz": max([p["transition_rate_hz"] for p in timeline_points]) if timeline_points else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error retrieving timeline data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-sessions/{session_id}/export-raw-data")
async def export_raw_data(
    session_id: str,
    format: str = Query("json", description="Export format: json, csv, binary"),
    include_metadata: bool = Query(True, description="Include metadata and statistics"),
    compress: bool = Query(True, description="Compress exported data"),
    db: Session = Depends(get_db)
):
    """Export raw timing data for detailed analysis"""
    
    try:
        # Get all raw data for the session
        raw_data = await get_raw_timing_data(
            session_id=session_id,
            include_transitions=True,
            include_run_periods=True,
            max_transitions=100000,  # Export all data
            db=db
        )
        
        export_info = {
            "session_id": session_id,
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "format": format,
            "compressed": compress,
            "data": raw_data
        }
        
        # Add metadata if requested
        if include_metadata:
            export_info["export_metadata"] = {
                "total_transitions": len(raw_data.get("voltage_transitions", [])),
                "total_run_periods": len(raw_data.get("voltage_run_periods", [])),
                "timing_precision": "microsecond",
                "data_source": raw_data.get("data_source"),
                "sample_rate_hz": raw_data.get("sample_rate_actual_hz"),
                "export_tool": "ai-model-validation-platform",
                "export_version": "1.0.0"
            }
        
        return export_info
        
    except Exception as e:
        logger.error(f"Error exporting raw data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/service-status")
async def get_raw_timing_service_status():
    """Get status of the raw timing data service"""
    
    try:
        performance_metrics = hybrid_query_service.get_performance_metrics()
        
        return {
            "service": "Raw Timing Data API",
            "status": "operational",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "capabilities": [
                "Microsecond precision timing",
                "Continuous voltage monitoring (1000Hz)",
                "Smart data compression",
                "Timeline visualization",
                "Raw data export",
                "Video sync correlation"
            ],
            "performance_metrics": performance_metrics,
            "data_sources": [
                "LabJack raw compression tables",
                "Legacy detection events (fallback)",
                "Hybrid query optimization"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        raise HTTPException(status_code=500, detail=str(e))