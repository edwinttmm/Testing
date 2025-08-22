"""
Enhanced Test Execution API
Provides endpoints for sequential video playback, timeline synchronization, and connection monitoring
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any
from datetime import datetime
import json
import logging

from database import get_db
from schemas import TestSessionCreate, TestSessionResponse
from services.test_workflow_service import (
    test_workflow_service, 
    TestConfiguration, 
    PlaybackMode,
    ConnectionStatus
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enhanced-test", tags=["Enhanced Test Execution"])

# Pydantic models for request/response
from pydantic import BaseModel

class EnhancedTestSessionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    project_id: str
    video_ids: List[str]
    configuration: Dict[str, Any]

class PlaybackControlRequest(BaseModel):
    action: str  # "start", "stop", "next", "previous", "pause", "resume"
    session_id: str

class TimeUpdateRequest(BaseModel):
    session_id: str
    current_time: float
    frame_number: int

class SyncRequest(BaseModel):
    session_id: str
    external_time: float

class ConnectionCheckResponse(BaseModel):
    api_connected: bool
    websocket_connected: bool
    latency_ms: int
    last_check: str
    status: str

@router.post("/sessions", response_model=TestSessionResponse)
async def create_enhanced_test_session(
    session_data: EnhancedTestSessionCreate,
    db: Session = Depends(get_db)
):
    """Create a new enhanced test session with sequential playback capabilities"""
    try:
        # Parse configuration
        config_dict = session_data.configuration
        config = TestConfiguration(
            batch_size=config_dict.get('batch_size', 1),
            concurrent=config_dict.get('concurrent', False),
            save_intermediate_results=config_dict.get('save_intermediate_results', True),
            generate_report=config_dict.get('generate_report', True),
            sequential_playback=config_dict.get('sequential_playback', True),
            auto_advance=config_dict.get('auto_advance', True),
            latency_ms=config_dict.get('latency_ms', 100),
            sync_external_signals=config_dict.get('sync_external_signals', False),
            loop_playback=config_dict.get('loop_playback', False),
            random_order=config_dict.get('random_order', False),
            playback_mode=PlaybackMode(config_dict.get('playback_mode', 'sequential')),
            max_sync_drift_ms=config_dict.get('max_sync_drift_ms', 50),
            sync_check_interval_ms=config_dict.get('sync_check_interval_ms', 1000)
        )
        
        # Create base session data
        base_session_data = TestSessionCreate(
            name=session_data.name,
            description=session_data.description,
            project_id=session_data.project_id
        )
        base_session_data.video_ids = session_data.video_ids
        
        # Create session using enhanced service
        session = await test_workflow_service.create_test_session(
            db, base_session_data, config
        )
        
        return session
        
    except Exception as e:
        logger.error(f"Failed to create enhanced test session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/start")
async def start_sequential_playback(
    session_id: str,
    background_tasks: BackgroundTasks
):
    """Start sequential video playback for a test session"""
    try:
        success = await test_workflow_service.start_sequential_playback(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found or failed to start")
        
        return {"message": "Sequential playback started", "session_id": session_id}
        
    except Exception as e:
        logger.error(f"Failed to start sequential playback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/control")
async def control_playback(
    session_id: str,
    control: PlaybackControlRequest
):
    """Control playback (next, previous, pause, etc.)"""
    try:
        action = control.action.lower()
        
        if action == "next":
            success = await test_workflow_service.advance_to_next_video(session_id)
        elif action == "stop":
            success = await test_workflow_service.stop_session(session_id)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found or action failed")
        
        return {"message": f"Action '{action}' executed", "session_id": session_id}
        
    except Exception as e:
        logger.error(f"Playback control error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/time-update")
async def update_playback_time(
    session_id: str,
    time_update: TimeUpdateRequest
):
    """Update current video playback time"""
    try:
        success = await test_workflow_service.update_video_time(
            session_id, 
            time_update.current_time, 
            time_update.frame_number
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {"message": "Time updated", "session_id": session_id}
        
    except Exception as e:
        logger.error(f"Time update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/video-end")
async def handle_video_end(session_id: str):
    """Handle when a video reaches its end"""
    try:
        success = await test_workflow_service.handle_video_end(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {"message": "Video end handled", "session_id": session_id}
        
    except Exception as e:
        logger.error(f"Video end handling error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/sync")
async def sync_external_timeline(
    session_id: str,
    sync_data: SyncRequest
):
    """Synchronize with external timeline signal"""
    try:
        success = await test_workflow_service.sync_external_timeline(
            session_id, 
            sync_data.external_time
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found or sync not enabled")
        
        return {"message": "Timeline synchronized", "session_id": session_id}
        
    except Exception as e:
        logger.error(f"Timeline sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/state")
async def get_session_state(session_id: str):
    """Get current session state"""
    try:
        state = await test_workflow_service.get_session_state(session_id)
        
        if not state:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return state
        
    except Exception as e:
        logger.error(f"Get session state error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/connection-status", response_model=ConnectionCheckResponse)
async def check_connection_status(session_id: str):
    """Check API and WebSocket connection health"""
    try:
        status = await test_workflow_service.check_connection_health(session_id)
        
        return ConnectionCheckResponse(
            api_connected=status.api_connected,
            websocket_connected=status.websocket_connected,
            latency_ms=status.latency_ms,
            last_check=status.last_check.isoformat() if status.last_check else "",
            status="healthy" if status.api_connected and status.websocket_connected else "degraded"
        )
        
    except Exception as e:
        logger.error(f"Connection status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def stop_test_session(session_id: str):
    """Stop and cleanup a test session"""
    try:
        success = await test_workflow_service.stop_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {"message": "Session stopped", "session_id": session_id}
        
    except Exception as e:
        logger.error(f"Stop session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Simple health check endpoint for connection testing"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "enhanced-test-execution"
    }

# WebSocket endpoint for real-time communication
@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket connection for real-time test session updates"""
    await websocket.accept()
    
    try:
        # Register WebSocket with service
        test_workflow_service.websocket_connections[session_id] = websocket
        
        # Send initial state
        state = await test_workflow_service.get_session_state(session_id)
        if state:
            await websocket.send_text(json.dumps({
                'type': 'initial_state',
                'data': state
            }))
        
        # Listen for messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                msg_type = message.get('type')
                
                if msg_type == 'time_update':
                    payload = message.get('data', {})
                    await test_workflow_service.update_video_time(
                        session_id,
                        payload.get('current_time', 0),
                        payload.get('frame_number', 0)
                    )
                
                elif msg_type == 'video_end':
                    await test_workflow_service.handle_video_end(session_id)
                
                elif msg_type == 'sync_request':
                    payload = message.get('data', {})
                    await test_workflow_service.sync_external_timeline(
                        session_id,
                        payload.get('external_time', 0)
                    )
                
                elif msg_type == 'ping':
                    # Respond to ping for connection health
                    await websocket.send_text(json.dumps({
                        'type': 'pong',
                        'timestamp': datetime.utcnow().isoformat()
                    }))
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON format'
                }))
            except Exception as e:
                logger.error(f"WebSocket message handling error: {e}")
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': str(e)
                }))
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        # Cleanup on disconnect
        if session_id in test_workflow_service.websocket_connections:
            del test_workflow_service.websocket_connections[session_id]

# Utility endpoints
@router.get("/sessions")
async def list_active_sessions():
    """List all active test sessions"""
    sessions = []
    for session_id, session_data in test_workflow_service.active_sessions.items():
        sessions.append({
            'session_id': session_id,
            'name': session_data['session'].name,
            'status': session_data['playback_state'].sync_status.value,
            'current_video_index': session_data['playback_state'].current_video_index,
            'total_videos': session_data['playback_state'].total_videos,
            'is_playing': session_data['playback_state'].is_playing,
            'total_progress': session_data['playback_state'].total_progress
        })
    
    return sessions

@router.get("/playback-modes")
async def get_playback_modes():
    """Get available playback modes"""
    return {
        'modes': [mode.value for mode in PlaybackMode],
        'default': PlaybackMode.SEQUENTIAL.value
    }