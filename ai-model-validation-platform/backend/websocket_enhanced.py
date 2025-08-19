import asyncio
import logging
from typing import Dict, Any
import socketio

logger = logging.getLogger(__name__)

# Enhanced WebSocket Events for Real-time Collaboration and Updates

async def emit_annotation_created(sio: socketio.AsyncServer, video_id: str, annotation_data: Dict[str, Any]):
    """Emit when new annotation created"""
    try:
        await sio.emit('annotation_update', {
            'type': 'created',
            'video_id': video_id,
            'annotation': annotation_data,
            'timestamp': asyncio.get_event_loop().time()
        }, room=f"video_{video_id}")
        
        logger.info(f"Annotation created broadcast for video {video_id}")
    except Exception as e:
        logger.error(f"Error in annotation_created broadcast: {str(e)}")

async def emit_annotation_updated(sio: socketio.AsyncServer, video_id: str, annotation_data: Dict[str, Any]):
    """Emit when annotation updated"""
    try:
        await sio.emit('annotation_update', {
            'type': 'updated',
            'video_id': video_id,
            'annotation': annotation_data,
            'timestamp': asyncio.get_event_loop().time()
        }, room=f"video_{video_id}")
        
        logger.info(f"Annotation updated broadcast for video {video_id}")
    except Exception as e:
        logger.error(f"Error in annotation_updated broadcast: {str(e)}")

async def emit_annotation_validated(sio: socketio.AsyncServer, video_id: str, annotation_id: str, validated: bool):
    """Emit when annotation validation status changes"""
    try:
        await sio.emit('annotation_validation', {
            'video_id': video_id,
            'annotation_id': annotation_id,
            'validated': validated,
            'timestamp': asyncio.get_event_loop().time()
        }, room=f"video_{video_id}")
        
        logger.info(f"Annotation validation broadcast for {annotation_id}")
    except Exception as e:
        logger.error(f"Error in annotation_validation broadcast: {str(e)}")

async def emit_project_created(sio: socketio.AsyncServer, project_id: str, project_name: str):
    """Emit when new project created"""
    try:
        await sio.emit('project_created', {
            'project_id': project_id,
            'name': project_name,
            'timestamp': asyncio.get_event_loop().time()
        }, room="dashboard")
        
        logger.info(f"Project created broadcast for {project_id}")
    except Exception as e:
        logger.error(f"Error in project_created broadcast: {str(e)}")

async def emit_video_uploaded(sio: socketio.AsyncServer, video_id: str, filename: str, project_id: str = None):
    """Emit when video uploaded"""
    try:
        await sio.emit('video_uploaded', {
            'video_id': video_id,
            'filename': filename,
            'project_id': project_id,
            'timestamp': asyncio.get_event_loop().time()
        }, room="dashboard")
        
        if project_id:
            await sio.emit('video_uploaded', {
                'video_id': video_id,
                'filename': filename,
                'project_id': project_id,
                'timestamp': asyncio.get_event_loop().time()
            }, room=f"project_{project_id}")
            
        logger.info(f"Video uploaded broadcast for {video_id}")
    except Exception as e:
        logger.error(f"Error in video_uploaded broadcast: {str(e)}")

async def emit_test_progress(sio: socketio.AsyncServer, session_id: str, progress_data: Dict[str, Any]):
    """Emit test execution progress updates"""
    try:
        await sio.emit('test_progress', {
            'session_id': session_id,
            'progress': progress_data,
            'timestamp': asyncio.get_event_loop().time()
        }, room=f"test_session_{session_id}")
        
        logger.info(f"Test progress broadcast for session {session_id}")
    except Exception as e:
        logger.error(f"Error in test_progress broadcast: {str(e)}")

async def emit_test_completed(sio: socketio.AsyncServer, test_session_id: str, results: Dict[str, Any]):
    """Emit when test session completes"""
    try:
        await sio.emit('test_completed', {
            'test_session_id': test_session_id,
            'results': results,
            'timestamp': asyncio.get_event_loop().time()
        }, room=f"test_session_{test_session_id}")
        
        # Also emit to dashboard for overview updates
        await sio.emit('test_completed', {
            'test_session_id': test_session_id,
            'results': results,
            'timestamp': asyncio.get_event_loop().time()
        }, room="dashboard")
        
        logger.info(f"Test completed broadcast for session {test_session_id}")
    except Exception as e:
        logger.error(f"Error in test_completed broadcast: {str(e)}")

async def emit_dashboard_stats_update(sio: socketio.AsyncServer, stats_data: Dict[str, Any]):
    """Emit dashboard statistics updates"""
    try:
        await sio.emit('stats_update', {
            'stats': stats_data,
            'timestamp': asyncio.get_event_loop().time()
        }, room="dashboard")
        
        logger.info("Dashboard stats update broadcast")
    except Exception as e:
        logger.error(f"Error in dashboard stats broadcast: {str(e)}")

async def emit_detection_event_stream(sio: socketio.AsyncServer, test_session_id: str, detection_data: Dict[str, Any]):
    """Stream detection events in real-time during testing"""
    try:
        await sio.emit('detection_event', {
            'test_session_id': test_session_id,
            'detection': detection_data,
            'timestamp': asyncio.get_event_loop().time()
        }, room=f"test_session_{test_session_id}")
        
    except Exception as e:
        logger.error(f"Error in detection_event stream: {str(e)}")

# Enhanced WebSocket Event Handlers

async def handle_join_annotation_session(sio: socketio.AsyncServer, sid: str, data: Dict[str, Any]):
    """Handle joining annotation session for collaboration"""
    try:
        session_id = data.get('session_id')
        video_id = data.get('video_id')
        user_id = data.get('user_id', 'anonymous')
        
        # Join both video and session rooms
        await sio.enter_room(sid, f"video_{video_id}")
        await sio.enter_room(sid, f"annotation_session_{session_id}")
        
        # Notify other users in session
        await sio.emit('collaborator_joined', {
            'session_id': session_id,
            'user_id': user_id,
            'user_sid': sid
        }, room=f"annotation_session_{session_id}", skip_sid=sid)
        
        logger.info(f"User {user_id} joined annotation session {session_id}")
        
    except Exception as e:
        logger.error(f"Error joining annotation session: {str(e)}")
        await sio.emit('error', {
            'message': f'Failed to join annotation session: {str(e)}'
        }, room=sid)

async def handle_annotation_progress(sio: socketio.AsyncServer, sid: str, data: Dict[str, Any]):
    """Handle real-time annotation progress updates"""
    try:
        video_id = data.get('video_id')
        progress_data = {
            'video_id': video_id,
            'current_frame': data.get('current_frame'),
            'total_frames': data.get('total_frames'),
            'annotations_count': data.get('annotations_count'),
            'validated_count': data.get('validated_count'),
            'annotator': data.get('annotator', 'anonymous')
        }
        
        await sio.emit('annotation_progress_update', progress_data, 
                      room=f"video_{video_id}", skip_sid=sid)
        
        logger.info(f"Annotation progress update for video {video_id}")
        
    except Exception as e:
        logger.error(f"Error in annotation progress update: {str(e)}")

async def handle_join_dashboard(sio: socketio.AsyncServer, sid: str, data: Dict[str, Any]):
    """Handle joining dashboard room for real-time updates"""
    try:
        await sio.enter_room(sid, "dashboard")
        
        await sio.emit('dashboard_joined', {
            'message': 'Successfully joined dashboard updates',
            'timestamp': asyncio.get_event_loop().time()
        }, room=sid)
        
        logger.info(f"User {sid} joined dashboard room")
        
    except Exception as e:
        logger.error(f"Error joining dashboard: {str(e)}")

async def handle_join_test_session(sio: socketio.AsyncServer, sid: str, data: Dict[str, Any]):
    """Handle joining test session room for progress updates"""
    try:
        session_id = data.get('session_id')
        await sio.enter_room(sid, f"test_session_{session_id}")
        
        await sio.emit('test_session_joined', {
            'session_id': session_id,
            'message': 'Successfully joined test session updates'
        }, room=sid)
        
        logger.info(f"User {sid} joined test session {session_id}")
        
    except Exception as e:
        logger.error(f"Error joining test session: {str(e)}")

# Enhanced WebSocket Event Registration
def register_enhanced_websocket_events(sio: socketio.AsyncServer):
    """Register all enhanced WebSocket event handlers"""
    
    @sio.event
    async def join_annotation_session(sid, data):
        await handle_join_annotation_session(sio, sid, data)
    
    @sio.event
    async def annotation_progress(sid, data):
        await handle_annotation_progress(sio, sid, data)
    
    @sio.event
    async def join_dashboard(sid, data):
        await handle_join_dashboard(sio, sid, data)
    
    @sio.event
    async def join_test_session(sid, data):
        await handle_join_test_session(sio, sid, data)
    
    @sio.event
    async def leave_room(sid, data):
        """Handle leaving specific rooms"""
        try:
            room = data.get('room')
            await sio.leave_room(sid, room)
            logger.info(f"User {sid} left room {room}")
        except Exception as e:
            logger.error(f"Error leaving room: {str(e)}")

    logger.info("Enhanced WebSocket events registered successfully")