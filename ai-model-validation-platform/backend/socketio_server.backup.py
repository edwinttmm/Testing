import socketio
import asyncio
from fastapi import FastAPI
from typing import Dict, Any
import logging
import json
from sqlalchemy.orm import Session
from database import SessionLocal
from crud import get_test_session, create_test_session
from schemas import TestSessionCreate

# Setup logging
logger = logging.getLogger(__name__)

# Import WebSocket message formatting utilities
try:
    from websocket_formatter import WebSocketFormatter, WebSocketMessageType
    WEBSOCKET_FORMATTER_AVAILABLE = True
    logger.info("✅ WebSocket formatter available")
except ImportError:
    WEBSOCKET_FORMATTER_AVAILABLE = False
    logger.warning("⚠️ WebSocket formatter not available, using basic formatting")

# Create Socket.IO server with secure CORS configuration and enhanced settings
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[
        # Development origins
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        
        # Production HTTP origins
        'http://155.138.239.131:3000',
        'http://155.138.239.131:8000',
        'http://155.138.239.131:8080',
        
        # Production HTTPS origins (secure)
        'https://155.138.239.131:3000',
        'https://155.138.239.131:8000',
        'https://155.138.239.131:8080',
        'https://155.138.239.131:8443',
        
        # Cloud Workstations
        'https://3000-firebase-testinggit-1755382041749.cluster-lu4mup47g5gm4rtyvhzpwbfadi.cloudworkstations.dev'
    ],
    logger=True,
    engineio_logger=True,
    # Enhanced configuration for reliability
    ping_timeout=60,  # 60 seconds before considering client disconnected
    ping_interval=25,  # Send ping every 25 seconds
    cors_credentials=True,  # Allow credentials for authentication
    transports=['websocket', 'polling'],  # Support both transports
    always_connect=True,  # Always allow connections
    cookie=False  # Don't use cookies for session management
)

# Store active test sessions
active_sessions: Dict[str, Any] = {}

# WebSocket message formatting helper functions
async def emit_formatted_message(
    event: str,
    message_type: str,
    payload: Dict[str, Any],
    room: str = None,
    sid: str = None
):
    """Emit a properly formatted WebSocket message"""
    if WEBSOCKET_FORMATTER_AVAILABLE:
        formatted_message = WebSocketFormatter.create_message(message_type, payload)
    else:
        # Fallback formatting
        formatted_message = {
            "type": message_type,
            "payload": payload,
            "timestamp": json.dumps({"$date": int(asyncio.get_event_loop().time() * 1000)})
        }
    
    if room:
        await sio.emit(event, formatted_message, room=room)
    elif sid:
        await sio.emit(event, formatted_message, to=sid)
    else:
        await sio.emit(event, formatted_message)

async def emit_detection_update(video_id: str, detection_data: Dict[str, Any], room: str = None):
    """Emit a detection update message"""
    if WEBSOCKET_FORMATTER_AVAILABLE:
        message = WebSocketFormatter.create_detection_message(
            WebSocketMessageType.DETECTION_UPDATE,
            video_id=video_id,
            **detection_data
        )
    else:
        message = {
            "type": "detection_update",
            "payload": {"videoId": video_id, **detection_data},
            "timestamp": json.dumps({"$date": int(asyncio.get_event_loop().time() * 1000)})
        }
    
    if room:
        await sio.emit('message', message, room=room)
    else:
        await sio.emit('message', message)

async def emit_test_session_progress(session_id: str, progress_data: Dict[str, Any], room: str = None):
    """Emit a test session progress message"""
    if WEBSOCKET_FORMATTER_AVAILABLE:
        message = WebSocketFormatter.create_test_session_message(
            WebSocketMessageType.TEST_SESSION_PROGRESS,
            session_id=session_id,
            **progress_data
        )
    else:
        message = {
            "type": "test_session_progress",
            "payload": {"sessionId": session_id, **progress_data},
            "timestamp": json.dumps({"$date": int(asyncio.get_event_loop().time() * 1000)})
        }
    
    if room:
        await sio.emit('message', message, room=room)
    else:
        await sio.emit('message', message)

@sio.event
async def connect(sid, environ, auth):
    """Handle client connections with enhanced authentication and setup"""
    logger.info(f"Client {sid} connected from {environ.get('HTTP_ORIGIN', 'unknown origin')}")
    
    try:
        # Enhanced authentication check
        client_info = {
            'sid': sid,
            'connected_at': asyncio.get_event_loop().time(),
            'origin': environ.get('HTTP_ORIGIN'),
            'user_agent': environ.get('HTTP_USER_AGENT', 'unknown'),
            'authenticated': False
        }
        
        # Authentication validation (for production)
        if auth and isinstance(auth, dict) and 'token' in auth:
            # TODO: Implement proper JWT token validation
            logger.info(f"Client {sid} provided authentication token")
            client_info['authenticated'] = True
            client_info['auth_method'] = 'token'
        
        # Store client info for session management
        active_sessions[f"client_{sid}"] = client_info
        
        # Join general room for broadcasts
        await sio.enter_room(sid, 'general')
        
        # Send enhanced connection confirmation
        await sio.emit('connection_status', {
            'status': 'connected',
            'message': 'Connected to real-time server',
            'sid': sid,
            'server_time': asyncio.get_event_loop().time(),
            'features': {
                'heartbeat': True,
                'rooms': True,
                'authentication': client_info['authenticated'],
                'broadcast': True
            }
        }, room=sid)
        
        # Start heartbeat for this connection
        asyncio.create_task(heartbeat_connection(sid))
        
        logger.info(f"Client {sid} successfully connected and configured")
        return True
        
    except Exception as e:
        logger.error(f"Error during client {sid} connection: {str(e)}")
        return False

@sio.event
async def disconnect(sid):
    """Handle client disconnections with comprehensive cleanup"""
    logger.info(f"Client {sid} disconnected")
    
    try:
        # Clean up any active sessions for this client
        sessions_to_remove = []
        for session_id, session_data in active_sessions.items():
            if (session_data.get('client_id') == sid or 
                session_id == f"client_{sid}" or 
                session_data.get('sid') == sid):
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del active_sessions[session_id]
            logger.info(f"Cleaned up session {session_id} for disconnected client {sid}")
        
        # Leave all rooms
        await sio.leave_room(sid, 'general')
        
        # Notify other clients in relevant rooms about disconnection
        await sio.emit('client_disconnected', {
            'sid': sid,
            'timestamp': asyncio.get_event_loop().time()
        }, room='general', skip_sid=sid)
        
    except Exception as e:
        logger.error(f"Error during client {sid} disconnection cleanup: {str(e)}")

@sio.event
async def start_test_session(sid, data):
    """Handle test session start requests"""
    try:
        logger.info(f"Starting test session for client {sid}: {data}")
        
        session_id = data.get('session_id')
        project_id = data.get('project_id')
        
        if not session_id or not project_id:
            await sio.emit('error', {
                'message': 'Missing required fields: session_id and project_id'
            }, room=sid)
            return
        
        # Join room for this test session
        await sio.enter_room(sid, f"test_session_{session_id}")
        
        # Store session data
        active_sessions[session_id] = {
            'client_id': sid,
            'project_id': project_id,
            'status': 'running',
            'start_time': asyncio.get_event_loop().time()
        }
        
        # Emit session started event
        await sio.emit('test_session_update', {
            'session_id': session_id,
            'status': 'running',
            'message': 'Test session started successfully'
        }, room=f"test_session_{session_id}")
        
        # Start background task for this session
        asyncio.create_task(run_test_session(session_id))
        
    except Exception as e:
        logger.error(f"Error starting test session: {str(e)}")
        await sio.emit('error', {
            'message': f'Failed to start test session: {str(e)}'
        }, room=sid)

@sio.event
async def stop_test_session(sid, data):
    """Handle test session stop requests"""
    try:
        session_id = data.get('session_id')
        
        if session_id in active_sessions:
            active_sessions[session_id]['status'] = 'stopped'
            
            await sio.emit('test_session_update', {
                'session_id': session_id,
                'status': 'stopped',
                'message': 'Test session stopped by user'
            }, room=f"test_session_{session_id}")
            
            # Leave room
            await sio.leave_room(sid, f"test_session_{session_id}")
            
        logger.info(f"Stopped test session {session_id} for client {sid}")
        
    except Exception as e:
        logger.error(f"Error stopping test session: {str(e)}")
        await sio.emit('error', {
            'message': f'Failed to stop test session: {str(e)}'
        }, room=sid)

@sio.event
async def join_room(sid, data):
    """Allow clients to join specific rooms"""
    room = data.get('room')
    if room:
        await sio.enter_room(sid, room)
        logger.info(f"Client {sid} joined room {room}")

async def run_test_session(session_id: str):
    """Enhanced background task for test session execution with real-time HIL updates"""
    try:
        if session_id not in active_sessions:
            logger.warning(f"Session {session_id} not found in active sessions")
            return
        
        session_data = active_sessions[session_id]
        room = f"test_session_{session_id}"
        
        logger.info(f"Starting test session execution: {session_id}")
        
        # Enhanced simulation for HIL testing with more realistic timing
        total_events = 20  # Increased for more comprehensive testing
        
        for i in range(total_events):
            if session_data.get('status') != 'running':
                logger.info(f"Session {session_id} stopped, breaking execution loop")
                break
            
            # Variable wait times to simulate real detection patterns
            wait_time = 0.5 + (i % 3) * 0.5  # 0.5 to 2 seconds
            await asyncio.sleep(wait_time)
            
            # Enhanced detection event with HIL-specific data
            current_time = asyncio.get_event_loop().time()
            detection_data = {
                'session_id': session_id,
                'event_id': f"hil_event_{i+1}",
                'timestamp': current_time,
                'server_timestamp': current_time,
                'detection_type': ['person', 'vehicle', 'bicycle', 'traffic_light'][i % 4],
                'confidence': round(0.75 + (i * 0.01) + (0.1 * (i % 3)), 3),
                'validation_result': ['TP', 'TN', 'FP', 'FN'][i % 4],
                'progress': round((i + 1) / total_events * 100, 1),
                'frame_number': i + 1,
                'processing_time_ms': round(50 + (i % 10) * 5, 2),
                'hardware_latency_ms': round(10 + (i % 5) * 2, 2),
                'bounding_box': {
                    'x': 100 + (i * 15) % 400,
                    'y': 150 + (i * 20) % 300,
                    'width': 80 + (i % 5) * 10,
                    'height': 120 + (i % 4) * 15
                },
                'hardware_status': {
                    'labjack_connected': True,
                    'signal_strength': 0.8 + (i % 5) * 0.04,
                    'temperature': 22.5 + (i % 10) * 0.3
                },
                'metrics': {
                    'fps': round(30 - (i % 8), 1),
                    'memory_usage_mb': 150 + (i % 20) * 5,
                    'cpu_usage_percent': 25 + (i % 15) * 2
                }
            }
            
            # Emit to session room
            await sio.emit('detection_event', detection_data, room=room)
            
            # Emit to monitoring rooms
            await sio.emit('detection_event', detection_data, room='detections')
            await sio.emit('hil_update', detection_data, room='general')
            
            # Emit progress update every 5 events
            if (i + 1) % 5 == 0:
                progress_data = {
                    'session_id': session_id,
                    'progress_percentage': detection_data['progress'],
                    'events_processed': i + 1,
                    'total_events': total_events,
                    'average_confidence': sum([0.75 + (j * 0.01) for j in range(i + 1)]) / (i + 1),
                    'timestamp': current_time
                }
                await sio.emit('progress_update', progress_data, room=room)
            
        # Complete the session
        if session_data.get('status') == 'running':
            session_data['status'] = 'completed'
            completion_data = {
                'session_id': session_id,
                'status': 'completed',
                'message': 'HIL test session completed successfully',
                'total_events': total_events,
                'completion_time': asyncio.get_event_loop().time(),
                'duration_seconds': asyncio.get_event_loop().time() - session_data['start_time'],
                'summary': {
                    'events_processed': total_events,
                    'success_rate': 0.85,
                    'average_latency_ms': 15.5,
                    'hardware_performance': 'optimal'
                }
            }
            await sio.emit('test_session_update', completion_data, room=room)
            await sio.emit('session_completed', completion_data, room='general')
            
            logger.info(f"Test session {session_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error in test session {session_id}: {str(e)}")
        error_data = {
            'session_id': session_id,
            'error_type': 'execution_error',
            'message': f'Test session error: {str(e)}',
            'timestamp': asyncio.get_event_loop().time()
        }
        await sio.emit('error', error_data, room=f"test_session_{session_id}")
        await sio.emit('session_error', error_data, room='general')

def create_socketio_app(fastapi_app: FastAPI):
    """Integrate Socket.IO with FastAPI"""
    socketio_asgi_app = socketio.ASGIApp(sio, fastapi_app)
    return socketio_asgi_app

# Utility functions for real-time detection events
async def emit_detection_event(detection_data: dict, test_session_id: str):
    """Emit real-time detection event to all connected clients"""
    try:
        # Emit to test session room
        room = f"test_session_{test_session_id}"
        await sio.emit('detection_event', detection_data, room=room)
        
        # Emit to general detections room for monitoring
        await sio.emit('detection_event', detection_data, room='detections')
        
        logger.debug(f"Emitted detection event to room {room}")
        
    except Exception as e:
        logger.error(f"Failed to emit detection event: {str(e)}")

async def emit_processing_status(status_data: dict, session_id: str):
    """Emit processing status update"""
    try:
        room = f"test_session_{session_id}"
        await sio.emit('processing_status', status_data, room=room)
        logger.debug(f"Emitted processing status to room {room}")
        
    except Exception as e:
        logger.error(f"Failed to emit processing status: {str(e)}")

# Export the Socket.IO server for use in main.py
# Heartbeat functionality for connection keepalive\nasync def heartbeat_connection(sid: str):\n    \"\"\"Send periodic heartbeat to maintain connection\"\"\"\n    heartbeat_interval = 30  # seconds\n    max_missed_heartbeats = 3\n    missed_count = 0\n    \n    while sid in [s.get('sid') for s in active_sessions.values() if isinstance(s, dict)]:\n        try:\n            await asyncio.sleep(heartbeat_interval)\n            \n            # Send heartbeat ping\n            heartbeat_data = {\n                'type': 'heartbeat',\n                'timestamp': asyncio.get_event_loop().time(),\n                'sid': sid\n            }\n            \n            await sio.emit('heartbeat_ping', heartbeat_data, room=sid)\n            logger.debug(f\"Sent heartbeat to client {sid}\")\n            missed_count = 0\n            \n        except Exception as e:\n            missed_count += 1\n            logger.warning(f\"Heartbeat failed for client {sid}: {str(e)} (missed: {missed_count})\")\n            \n            if missed_count >= max_missed_heartbeats:\n                logger.info(f\"Client {sid} missed {missed_count} heartbeats, considering disconnected\")\n                # Clean up the client session\n                client_session_key = f\"client_{sid}\"\n                if client_session_key in active_sessions:\n                    del active_sessions[client_session_key]\n                break\n\n@sio.event\nasync def heartbeat_pong(sid, data):\n    \"\"\"Handle heartbeat response from client\"\"\"\n    logger.debug(f\"Received heartbeat pong from client {sid}\")\n    \n    # Update client activity\n    client_session_key = f\"client_{sid}\"\n    if client_session_key in active_sessions:\n        active_sessions[client_session_key]['last_heartbeat'] = asyncio.get_event_loop().time()\n\n@sio.event\nasync def ping(sid, data):\n    \"\"\"Handle ping from client - respond with pong\"\"\"\n    pong_data = {\n        'type': 'pong',\n        'timestamp': asyncio.get_event_loop().time(),\n        'original_timestamp': data.get('timestamp') if isinstance(data, dict) else None\n    }\n    await sio.emit('pong', pong_data, room=sid)\n\n@sio.event\nasync def subscribe_to_updates(sid, data):\n    \"\"\"Handle subscription requests for different update types\"\"\"\n    try:\n        subscription_type = data.get('type')\n        target_id = data.get('target_id')\n        \n        if subscription_type == 'session' and target_id:\n            room = f\"test_session_{target_id}\"\n            await sio.enter_room(sid, room)\n            await sio.emit('subscription_confirmed', {\n                'type': subscription_type,\n                'target_id': target_id,\n                'room': room\n            }, room=sid)\n            \n        elif subscription_type == 'detections':\n            await sio.enter_room(sid, 'detections')\n            await sio.emit('subscription_confirmed', {\n                'type': 'detections',\n                'room': 'detections'\n            }, room=sid)\n            \n        elif subscription_type == 'general':\n            await sio.enter_room(sid, 'general')\n            await sio.emit('subscription_confirmed', {\n                'type': 'general',\n                'room': 'general'\n            }, room=sid)\n            \n        else:\n            await sio.emit('subscription_error', {\n                'message': f'Unknown subscription type: {subscription_type}'\n            }, room=sid)\n            \n    except Exception as e:\n        logger.error(f\"Error handling subscription for {sid}: {str(e)}\")\n        await sio.emit('subscription_error', {\n            'message': f'Subscription failed: {str(e)}'\n        }, room=sid)\n\n# Enhanced utility functions\nasync def emit_hil_status_update(session_id: str, status_data: dict):\n    \"\"\"Emit HIL-specific status updates\"\"\"\n    try:\n        enhanced_data = {\n            **status_data,\n            'session_id': session_id,\n            'timestamp': asyncio.get_event_loop().time(),\n            'update_type': 'hil_status'\n        }\n        \n        room = f\"test_session_{session_id}\"\n        await sio.emit('hil_status_update', enhanced_data, room=room)\n        await sio.emit('hil_status_update', enhanced_data, room='general')\n        \n        logger.debug(f\"Emitted HIL status update for session {session_id}\")\n        \n    except Exception as e:\n        logger.error(f\"Failed to emit HIL status update: {str(e)}\")\n\nasync def emit_system_notification(notification_type: str, message: str, data: dict = None):\n    \"\"\"Emit system-wide notifications\"\"\"\n    try:\n        notification_data = {\n            'type': notification_type,\n            'message': message,\n            'timestamp': asyncio.get_event_loop().time(),\n            'data': data or {}\n        }\n        \n        await sio.emit('system_notification', notification_data, room='general')\n        logger.info(f\"Emitted system notification: {notification_type} - {message}\")\n        \n    except Exception as e:\n        logger.error(f\"Failed to emit system notification: {str(e)}\")\n\n__all__ = [\n    'sio', 'create_socketio_app', 'emit_detection_event', 'emit_processing_status',\n    'emit_hil_status_update', 'emit_system_notification', 'heartbeat_connection'\n]