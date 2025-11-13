"""
T3 Detection API Endpoints for HIL Testing
Phase 2: Real-time YOLO detection streaming and management API

This module provides REST API endpoints for:
- Real-time T3 YOLO detection event streaming
- T3 detection statistics and monitoring
- T3-T4 timing pipeline coordination management
- HIL video frame monitoring control

API Endpoints:
- POST /api/t3/start/{session_id} - Start T3 detection for HIL session
- POST /api/t3/stop/{session_id} - Stop T3 detection and get results
- GET /api/t3/events/{session_id} - Get T3 detection events
- GET /api/t3/stats/{session_id} - Get T3 detection statistics
- WebSocket /api/t3/stream/{session_id} - Real-time T3 event streaming
- GET /api/t3/pipeline/{session_id} - Get complete T3-T4 timing pipeline

Author: AI Model Validation Platform Team
Version: 1.0.0 - Phase 2 Implementation
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import logging
import asyncio
import json
from datetime import datetime
import time
from pathlib import Path

# Local imports
from database import get_db
from models import TestSession, DetectionEvent, Video
from src.hil_t3_yolo_pipeline import (
    get_t3_yolo_pipeline, 
    start_t3_detection_for_hil_session,
    stop_t3_detection_for_hil_session,
    get_t3_detection_statistics,
    get_t3_database_service
)
from src.hil_video_frame_monitor import (
    get_hil_video_monitor,
    start_hil_video_monitoring,
    stop_hil_video_monitoring,
    get_hil_monitoring_stats
)
from src.t3_t4_coordination_service import (
    get_t3_t4_coordination_service,
    start_t3_t4_coordination,
    stop_t3_t4_coordination
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/t3", tags=["T3 YOLO Detection"])

# WebSocket connection manager for real-time streaming
class T3WebSocketManager:
    """Manages WebSocket connections for real-time T3 detection streaming"""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.session_callbacks: Dict[str, List] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Add new WebSocket connection for session"""
        await websocket.accept()
        
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
            self.session_callbacks[session_id] = []
        
        self.active_connections[session_id].append(websocket)
        logger.info(f"T3 WebSocket connected for session {session_id}")
        
        # Set up detection event callback for this session
        await self._setup_detection_callback(session_id)
    
    def disconnect(self, websocket: WebSocket, session_id: str):
        """Remove WebSocket connection"""
        if session_id in self.active_connections:
            try:
                self.active_connections[session_id].remove(websocket)
                if not self.active_connections[session_id]:
                    del self.active_connections[session_id]
                    # Clean up callbacks
                    if session_id in self.session_callbacks:
                        del self.session_callbacks[session_id]
            except ValueError:
                pass
        
        logger.info(f"T3 WebSocket disconnected for session {session_id}")
    
    async def broadcast_to_session(self, session_id: str, data: dict):
        """Broadcast data to all WebSocket connections for session"""
        if session_id in self.active_connections:
            disconnected_connections = []
            
            for websocket in self.active_connections[session_id]:
                try:
                    await websocket.send_json(data)
                except:
                    disconnected_connections.append(websocket)
            
            # Remove disconnected connections
            for websocket in disconnected_connections:
                self.disconnect(websocket, session_id)
    
    async def _setup_detection_callback(self, session_id: str):
        """Set up detection event callback for real-time streaming"""
        try:
            # Get T3 pipeline and add callback
            t3_pipeline = await get_t3_yolo_pipeline()
            
            async def detection_callback(t3_events):
                if t3_events:
                    # Format events for WebSocket streaming
                    event_data = {
                        'type': 't3_detection_events',
                        'timestamp': datetime.now().isoformat(),
                        'session_id': session_id,
                        'events': [
                            {
                                'detection_id': event.detection_id,
                                't3_timestamp': event.t3_detection_timestamp,
                                't3_timestamp_ns': event.t3_detection_timestamp_ns,
                                'frame_number': event.frame_number,
                                'video_timestamp': event.video_relative_timestamp,
                                'vru_type': event.vru_type,
                                'confidence': event.yolo_confidence,
                                'bounding_box': event.bounding_box,
                                'processing_time_ms': event.processing_time_ms,
                                'timing_quality': event.timing_sync_quality
                            }
                            for event in t3_events
                        ],
                        'event_count': len(t3_events)
                    }
                    
                    await self.broadcast_to_session(session_id, event_data)
            
            # Add callback to T3 pipeline
            t3_pipeline.add_event_callback(detection_callback)
            self.session_callbacks[session_id].append(detection_callback)
            
        except Exception as e:
            logger.error(f"Error setting up detection callback for session {session_id}: {e}")

# Global WebSocket manager
websocket_manager = T3WebSocketManager()
_monitor_tasks: Dict[str, asyncio.Task] = {}

@router.post("/{session_id}/start")
async def start_t3_detection_for_session(
    session_id: str,
    video_path: str = Query(..., description="Path to video file for HIL testing"),
    video_id: Optional[str] = Query(None, description="Video ID for tracking"),
    start_frame: int = Query(0, description="Starting frame number"),
    enable_coordination: bool = Query(True, description="Enable T3-T4 coordination"),
    latency_threshold_ms: float = Query(100.0, description="Latency threshold for validation"),
    db: Session = Depends(get_db)
):
    """
    Start T3 YOLO detection for HIL test session with video monitoring.
    
    This endpoint initializes:
    - T3 YOLO detection pipeline
    - Video frame monitoring with real-time processing
    - T3-T4 coordination service (if enabled)
    - Real-time WebSocket streaming setup
    
    Returns:
        Session initialization status and configuration
    """
    try:
        # Verify test session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail=f"Test session {session_id} not found")
        
        # Verify video file exists
        video_file_path = Path(video_path)
        if not video_file_path.exists():
            raise HTTPException(status_code=404, detail=f"Video file not found: {video_path}")
        
        # Get video info from database if video_id provided
        video_record = None
        if video_id:
            video_record = db.query(Video).filter(Video.id == video_id).first()
        
        logger.info(f"Starting T3 detection for HIL session {session_id}")
        
        # Start T3 YOLO detection pipeline
        t3_success = await start_t3_detection_for_hil_session(
            session_id, 
            video_id or session_id, 
            time.time()
        )
        
        if not t3_success:
            raise HTTPException(status_code=500, detail="Failed to start T3 YOLO detection pipeline")
        
        # Start HIL video frame monitoring
        monitor_success = await start_hil_video_monitoring(
            session_id, 
            str(video_file_path), 
            video_id, 
            start_frame
        )
        
        if not monitor_success:
            # Clean up T3 pipeline if monitor failed
            await stop_t3_detection_for_hil_session()
            raise HTTPException(status_code=500, detail="Failed to start HIL video monitoring")
        
        # Start continuous monitoring in background
        try:
            monitor = await get_hil_video_monitor()
            # Cancel any existing task for this session
            if session_id in _monitor_tasks and not _monitor_tasks[session_id].done():
                _monitor_tasks[session_id].cancel()
            _monitor_tasks[session_id] = asyncio.create_task(monitor.run_continuous_monitoring())
        except Exception as e:
            logger.warning(f"Failed to start background monitoring task: {e}")

        # Start T3-T4 coordination if enabled
        coordination_success = True
        if enable_coordination:
            coordination_success = await start_t3_t4_coordination(
                session_id, 
                latency_threshold_ms
            )
            
            if not coordination_success:
                logger.warning(f"T3-T4 coordination failed to start for session {session_id}")
        
        # Update test session status
        test_session.status = "running"
        test_session.started_at = datetime.utcnow()
        db.commit()
        
        # Prepare response
        response = {
            'session_id': session_id,
            'status': 'started',
            'video_path': str(video_file_path),
            'video_id': video_id,
            'start_frame': start_frame,
            'services': {
                't3_detection': t3_success,
                'video_monitoring': monitor_success,
                't3_t4_coordination': coordination_success and enable_coordination
            },
            'configuration': {
                'latency_threshold_ms': latency_threshold_ms,
                'enable_coordination': enable_coordination,
                'websocket_streaming': True
            },
            'video_info': {
                'filename': video_file_path.name,
                'database_record': bool(video_record),
                'duration': video_record.duration if video_record else None,
                'fps': video_record.fps if video_record else None,
                'resolution': video_record.resolution if video_record else None
            },
            'started_at': datetime.utcnow().isoformat(),
            'websocket_url': f"/api/t3/stream/{session_id}"
        }
        
        logger.info(f"T3 detection started successfully for session {session_id}")
        return JSONResponse(content=response, status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting T3 detection for session {session_id}: {e}")
        # Clean up any partially started services
        try:
            await stop_t3_detection_for_hil_session()
            await stop_hil_video_monitoring()
            await stop_t3_t4_coordination()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to start T3 detection: {str(e)}")


@router.post("/{session_id}/stop")
async def stop_t3_detection_for_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Stop T3 YOLO detection for HIL test session and return comprehensive results.
    
    Returns:
        Complete session results including:
        - T3 detection statistics
        - Video monitoring results
        - T3-T4 coordination metrics
        - Database storage summary
    """
    try:
        # Verify test session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail=f"Test session {session_id} not found")
        
        logger.info(f"Stopping T3 detection for HIL session {session_id}")
        
        # Stop all services and collect results
        t3_results = await stop_t3_detection_for_hil_session()
        monitor_results = await stop_hil_video_monitoring()
        coordination_results = await stop_t3_t4_coordination()

        # Cancel and cleanup background task if running
        try:
            task = _monitor_tasks.get(session_id)
            if task and not task.done():
                task.cancel()
        except Exception:
            pass
        
        # Get final statistics
        t3_stats = await get_t3_detection_statistics()
        monitor_stats = await get_hil_monitoring_stats()
        
        # Update test session status
        test_session.status = "completed"
        test_session.completed_at = datetime.utcnow()
        db.commit()
        
        # Get T3 detection events from database
        db_service = get_t3_database_service()
        stored_events = await db_service.get_t3_events_for_session(session_id)
        
        # Prepare comprehensive results
        # Include DB stats
        db_service = get_t3_database_service()
        db_stats = getattr(db_service, 'get_stats', lambda: {})()

        response = {
            'session_id': session_id,
            'status': 'stopped',
            'completed_at': datetime.utcnow().isoformat(),
            
            # Service Results
            'results': {
                't3_pipeline': t3_results,
                'video_monitoring': monitor_results,
                't3_t4_coordination': coordination_results
            },
            
            # Final Statistics
            'statistics': {
                't3_detection': t3_stats,
                'video_monitoring': monitor_stats,
            },
            
            # Database Storage Summary
            'database': {
                'stored_events_count': len(stored_events),
                'events_with_t4_correlation': len([e for e in stored_events if e.get('t4_labjack_timestamp')]),
                'average_t4_t3_latency_ms': coordination_results.get('average_t4_t3_latency_ms'),
                'validation_pass_rate': coordination_results.get('correlation_success_rate_percent')
            },
            
            # Performance Summary
            'performance': {
                'total_frames_processed': monitor_results.get('frames_processed', 0),
                'total_t3_detections': t3_results.get('total_detections', 0),
                'processing_fps': monitor_results.get('processing_fps', 0),
                'detection_rate_hz': t3_results.get('detection_rate_hz', 0),
                'average_processing_time_ms': t3_stats.get('average_processing_time_ms', 0)
            },
            'software_delays': {
                't3_pipeline_alerts': t3_stats.get('alerts', []),
                'video_monitor_alerts': monitor_stats.get('alerts', []) if 'video_monitoring' in locals() else [],
                'database_alerts': db_stats.get('alerts', [])
            }
        }
        
        logger.info(f"T3 detection stopped successfully for session {session_id}")
        return JSONResponse(content=response, status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping T3 detection for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop T3 detection: {str(e)}")


@router.get("/{session_id}/events")
async def get_t3_detection_events(
    session_id: str,
    limit: int = Query(100, description="Maximum number of events to return"),
    include_t4_correlation: bool = Query(True, description="Include T4 LabJack correlation data"),
    min_confidence: float = Query(0.0, description="Minimum detection confidence filter"),
    vru_type: Optional[str] = Query(None, description="Filter by VRU type"),
    db: Session = Depends(get_db)
):
    """
    Get T3 YOLO detection events for HIL test session with optional filtering.
    
    Returns:
        List of T3 detection events with timing data and optional T4 correlations
    """
    try:
        # Verify test session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail=f"Test session {session_id} not found")
        
        # Get events from database service
        db_service = get_t3_database_service()
        all_events = await db_service.get_t3_events_for_session(session_id)
        
        # Apply filters
        filtered_events = []
        for event in all_events:
            # Confidence filter
            if event.get('confidence', 0) < min_confidence:
                continue
                
            # VRU type filter
            if vru_type and event.get('vru_type') != vru_type:
                continue
            
            # Include/exclude T4 correlation data
            if not include_t4_correlation:
                # Remove T4 fields
                for key in list(event.keys()):
                    if key.startswith('t4_'):
                        del event[key]
            
            filtered_events.append(event)
        
        # Apply limit
        filtered_events = filtered_events[:limit]
        
        # Calculate summary statistics
        total_events = len(all_events)
        filtered_count = len(filtered_events)
        events_with_t4 = len([e for e in filtered_events if e.get('t4_labjack_timestamp')])
        
        vru_type_counts = {}
        confidence_sum = 0
        for event in filtered_events:
            vru_type_name = event.get('vru_type', 'unknown')
            vru_type_counts[vru_type_name] = vru_type_counts.get(vru_type_name, 0) + 1
            confidence_sum += event.get('confidence', 0)
        
        average_confidence = confidence_sum / len(filtered_events) if filtered_events else 0
        
        response = {
            'session_id': session_id,
            'events': filtered_events,
            'summary': {
                'total_events_in_session': total_events,
                'filtered_events_returned': filtered_count,
                'events_with_t4_correlation': events_with_t4,
                'vru_type_distribution': vru_type_counts,
                'average_confidence': round(average_confidence, 3),
                'filters_applied': {
                    'min_confidence': min_confidence,
                    'vru_type': vru_type,
                    'include_t4_correlation': include_t4_correlation,
                    'limit': limit
                }
            }
        }
        
        return JSONResponse(content=response, status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting T3 events for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get T3 detection events: {str(e)}")


@router.get("/{session_id}/stats")
async def get_t3_detection_statistics_endpoint(
    session_id: str,
    include_coordination: bool = Query(True, description="Include T3-T4 coordination statistics"),
    include_monitoring: bool = Query(True, description="Include video monitoring statistics"),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive T3 detection statistics for HIL test session.
    
    Returns:
        Complete statistics including T3 pipeline, video monitoring, and coordination metrics
    """
    try:
        # Verify test session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail=f"Test session {session_id} not found")
        
        # Get statistics from all services
        t3_stats = await get_t3_detection_statistics()
        
        # Include DB stats
        db_service = get_t3_database_service()
        db_stats = getattr(db_service, 'get_stats', lambda: {})()

        response = {
            'session_id': session_id,
            'session_info': {
                'name': test_session.name,
                'status': test_session.status,
                'started_at': test_session.started_at.isoformat() if test_session.started_at else None,
                'completed_at': test_session.completed_at.isoformat() if test_session.completed_at else None
            },
            't3_pipeline_stats': t3_stats,
            'database_stats': db_stats,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Include video monitoring statistics if requested
        if include_monitoring:
            try:
                monitor_stats = await get_hil_monitoring_stats()
                response['video_monitoring_stats'] = monitor_stats
                # Bubble up alerts for convenience
                response['alerts'] = {
                    't3_pipeline': t3_stats.get('alerts', []),
                    'video_monitor': monitor_stats.get('alerts', []),
                    'database': db_stats.get('alerts', [])
                }
            except Exception as e:
                logger.warning(f"Could not get monitoring stats: {e}")
                response['video_monitoring_stats'] = {'error': str(e)}
        
        # Include T3-T4 coordination statistics if requested
        if include_coordination:
            try:
                coordination_service = await get_t3_t4_coordination_service()
                coordination_stats = coordination_service.get_coordination_statistics()
                response['t3_t4_coordination_stats'] = coordination_stats
            except Exception as e:
                logger.warning(f"Could not get coordination stats: {e}")
                response['t3_t4_coordination_stats'] = {'error': str(e)}
        
        return JSONResponse(content=response, status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting T3 statistics for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get T3 statistics: {str(e)}")


@router.get("/{session_id}/alerts")
async def get_t3_software_alerts(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get aggregated software-delay alerts for the current T3/HIL session.
    Includes T3 pipeline, video monitor, and database write alerts.
    """
    try:
        # Verify session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail=f"Test session {session_id} not found")

        t3_stats = await get_t3_detection_statistics()
        monitor_stats = await get_hil_monitoring_stats()
        db_service = get_t3_database_service()
        db_stats = getattr(db_service, 'get_stats', lambda: {})()

        content = {
            'session_id': session_id,
            'alerts': {
                't3_pipeline': t3_stats.get('alerts', []),
                'video_monitor': monitor_stats.get('alerts', []),
                'database': db_stats.get('alerts', [])
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        return JSONResponse(content=content, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alerts for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {str(e)}")


@router.get("/{session_id}/pipeline")
async def get_t3_t4_timing_pipeline(
    session_id: str,
    limit: int = Query(2000, description="Maximum number of pipeline events to return"),
    validation_result: Optional[str] = Query(None, description="Filter by validation result (pass/fail)"),
    db: Session = Depends(get_db)
):
    """
    Get complete T3-T4 timing pipeline events with full timing correlation.
    
    Returns:
        Complete timing pipeline events showing T0->T1->T3->T4 correlation
    """
    try:
        # Verify test session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail=f"Test session {session_id} not found")
        
        # Get timing pipeline events from coordination service
        coordination_service = await get_t3_t4_coordination_service()
        pipeline_events = await coordination_service.get_correlated_events(limit=limit)
        
        # Convert to API format and apply filters
        formatted_events = []
        for event in pipeline_events:
            event_dict = event.to_dict()
            
            # Apply validation result filter
            if validation_result and event_dict.get('validation_result') != validation_result:
                continue
            
            formatted_events.append(event_dict)
        
        # Calculate pipeline statistics
        total_correlations = len(formatted_events)
        passed_validations = len([e for e in formatted_events if e.get('validation_result') == 'pass'])
        failed_validations = len([e for e in formatted_events if e.get('validation_result') == 'fail'])
        
        # Calculate average latencies
        t4_t3_latencies = [e.get('t4_t3_signal_delay_ms') for e in formatted_events if e.get('t4_t3_signal_delay_ms') is not None]
        avg_t4_t3_latency = sum(t4_t3_latencies) / len(t4_t3_latencies) if t4_t3_latencies else 0
        
        response = {
            'session_id': session_id,
            'timing_pipeline_events': formatted_events,
            'pipeline_statistics': {
                'total_correlations': total_correlations,
                'passed_validations': passed_validations,
                'failed_validations': failed_validations,
                'validation_pass_rate_percent': (passed_validations / total_correlations * 100) if total_correlations > 0 else 0,
                'average_t4_t3_latency_ms': round(avg_t4_t3_latency, 2),
                'min_t4_t3_latency_ms': round(min(t4_t3_latencies), 2) if t4_t3_latencies else 0,
                'max_t4_t3_latency_ms': round(max(t4_t3_latencies), 2) if t4_t3_latencies else 0
            },
            'filters_applied': {
                'limit': limit,
                'validation_result': validation_result
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return JSONResponse(content=response, status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting T3-T4 pipeline for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get timing pipeline: {str(e)}")


@router.websocket("/{session_id}/stream")
async def websocket_t3_detection_stream(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time T3 detection event streaming.
    
    Streams real-time T3 detection events, statistics updates, and T3-T4 correlations
    """
    try:
        # Connect WebSocket
        await websocket_manager.connect(websocket, session_id)
        
        # Send initial connection confirmation
        await websocket.send_json({
            'type': 'connection_established',
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'message': 'T3 detection stream connected'
        })
        
        # Keep connection alive and handle messages
        try:
            while True:
                # Wait for client messages (ping/pong, control messages)
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    # Handle client control messages
                    if message.get('type') == 'ping':
                        await websocket.send_json({
                            'type': 'pong',
                            'timestamp': datetime.now().isoformat()
                        })
                    
                    elif message.get('type') == 'get_stats':
                        # Send current statistics
                        stats = await get_t3_detection_statistics()
                        await websocket.send_json({
                            'type': 'stats_update',
                            'session_id': session_id,
                            'timestamp': datetime.now().isoformat(),
                            'statistics': stats
                        })
                    
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"WebSocket message handling error: {e}")
                    break
                
        except WebSocketDisconnect:
            pass
        
    except Exception as e:
        logger.error(f"WebSocket T3 stream error for session {session_id}: {e}")
        try:
            await websocket.send_json({
                'type': 'error',
                'message': f'Stream error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
        except:
            pass
    
    finally:
        # Clean up connection
        websocket_manager.disconnect(websocket, session_id)
        logger.info(f"T3 detection stream closed for session {session_id}")


# Health check endpoint
@router.get("/health")
async def t3_detection_health_check():
    """
    Health check for T3 detection services.
    
    Returns:
        Health status of all T3 detection components
    """
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {}
        }
        
        # Check T3 pipeline
        try:
            t3_pipeline = await get_t3_yolo_pipeline()
            health_status['components']['t3_pipeline'] = 'healthy' if t3_pipeline else 'unavailable'
        except Exception as e:
            health_status['components']['t3_pipeline'] = f'error: {str(e)}'
            health_status['status'] = 'degraded'
        
        # Check video monitor
        try:
            video_monitor = await get_hil_video_monitor()
            health_status['components']['video_monitor'] = 'healthy' if video_monitor else 'unavailable'
        except Exception as e:
            health_status['components']['video_monitor'] = f'error: {str(e)}'
            health_status['status'] = 'degraded'
        
        # Check coordination service
        try:
            coordination_service = await get_t3_t4_coordination_service()
            health_status['components']['coordination_service'] = 'healthy' if coordination_service else 'unavailable'
        except Exception as e:
            health_status['components']['coordination_service'] = f'error: {str(e)}'
            health_status['status'] = 'degraded'
        
        # Check database service
        try:
            db_service = get_t3_database_service()
            health_status['components']['database_service'] = 'healthy' if db_service.db_available else 'unavailable'
        except Exception as e:
            health_status['components']['database_service'] = f'error: {str(e)}'
            health_status['status'] = 'degraded'
        
        return JSONResponse(content=health_status, status_code=200)
        
    except Exception as e:
        return JSONResponse(
            content={
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            },
            status_code=500
        )


# Export router
__all__ = ["router"]
