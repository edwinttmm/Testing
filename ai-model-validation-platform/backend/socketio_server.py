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

logger = logging.getLogger(__name__)

# Import video lifecycle handlers
try:
    from services.video_lifecycle_websocket_handlers import register_video_lifecycle_handlers
    _video_lifecycle_handlers_available = True
except ImportError as e:
    logger.warning(f"Video lifecycle handlers not available: {e}")
    _video_lifecycle_handlers_available = False

# Global sequence counter for lifecycle events
_lifecycle_event_sequence = 0
_sequence_lock = asyncio.Lock()

async def get_next_sequence_number() -> int:
    """Get next sequence number for lifecycle events (thread-safe)."""
    global _lifecycle_event_sequence
    async with _sequence_lock:
        _lifecycle_event_sequence += 1
        return _lifecycle_event_sequence

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

# Track active detection streaming sessions (prevents premature closure)
active_detection_streams: Dict[str, Dict[str, Any]] = {}
connection_heartbeat_tasks: Dict[str, asyncio.Task] = {}

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
                'broadcast': True,
                'keep_alive': True  # Indicate keep-alive support
            }
        }, room=sid)

        # Start heartbeat for this connection with enhanced keep-alive
        heartbeat_task = asyncio.create_task(heartbeat_connection(sid))
        connection_heartbeat_tasks[sid] = heartbeat_task

        logger.info(f"🔌 Client {sid} successfully connected with keep-alive enabled")
        return True
        
    except Exception as e:
        logger.error(f"Error during client {sid} connection: {str(e)}")
        return False

@sio.event
async def disconnect(sid):
    """Handle client disconnections with comprehensive cleanup"""
    logger.info(f"🔌 Client {sid} disconnected")

    try:
        # Cancel heartbeat task for this connection
        if sid in connection_heartbeat_tasks:
            heartbeat_task = connection_heartbeat_tasks[sid]
            if not heartbeat_task.done():
                heartbeat_task.cancel()
            del connection_heartbeat_tasks[sid]
            logger.info(f"Cancelled heartbeat task for {sid}")

        # Clean up active detection streams
        if sid in active_detection_streams:
            stream_info = active_detection_streams[sid]
            logger.info(f"🔌 Detection stream closed: {stream_info.get('session_id')} (sid: {sid})")
            del active_detection_streams[sid]

        # Clean up any active sessions for this client
        sessions_to_remove = []
        for session_id, session_data in active_sessions.items():
            if (session_data.get('client_id') == sid or
                session_id == f"client_{sid}" or
                session_data.get('sid') == sid):
                sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            # Leave session room before deleting
            await sio.leave_room(sid, f"session_{session_id}")
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
async def join_session(sid, data):
    """Client joins room for their test session - enables room-based event isolation"""
    try:
        session_id = data.get('session_id')

        if not session_id:
            await sio.emit('error', {
                'message': 'session_id required to join session room'
            }, room=sid)
            return {'error': 'session_id required'}

        # Validate session exists
        db = SessionLocal()
        try:
            from models import TestSession
            session = db.query(TestSession).filter(TestSession.id == session_id).first()

            if not session:
                await sio.emit('error', {
                    'message': f'Invalid session_id: {session_id}'
                }, room=sid)
                return {'error': 'Invalid session_id'}

            # Join session-specific room
            room_name = f"session_{session_id}"
            await sio.enter_room(sid, room_name)

            logger.info(f"✅ Client {sid} joined session room: {room_name}")

            # Send confirmation with session info
            await sio.emit('joined_session', {
                'session_id': session_id,
                'status': session.status,
                'room': room_name,
                'timestamp': asyncio.get_event_loop().time()
            }, room=sid)

            return {'success': True, 'room': room_name}

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error handling join_session for client {sid}: {str(e)}")
        await sio.emit('error', {
            'message': f'Failed to join session: {str(e)}'
        }, room=sid)
        return {'error': str(e)}

@sio.event
async def subscribe_detections(sid, data):
    """Subscribe to detection events for a test session

    CRITICAL: This registers the client for detection streaming and enables
    keep-alive mechanisms to prevent premature connection closure.
    """
    try:
        session_id = data.get('session_id')

        if not session_id:
            await sio.emit('error', {
                'message': 'session_id required to subscribe to detections'
            }, room=sid)
            return {'error': 'session_id required'}

        # Register detection stream (enables keep-alive)
        active_detection_streams[sid] = {
            'session_id': session_id,
            'subscribed_at': asyncio.get_event_loop().time(),
            'detection_count': 0
        }

        # Join detection monitoring room
        room_name = f"test_session_{session_id}"
        await sio.enter_room(sid, room_name)

        logger.info(
            f"🔌 Detection stream opened: {session_id} (sid: {sid}) - "
            f"Keep-alive enabled"
        )

        # Send confirmation
        await sio.emit('detection_subscription_confirmed', {
            'session_id': session_id,
            'room': room_name,
            'keep_alive_enabled': True,
            'heartbeat_interval_seconds': 5,
            'timestamp': asyncio.get_event_loop().time()
        }, room=sid)

        return {'success': True, 'room': room_name}

    except Exception as e:
        logger.error(f"Error subscribing to detections for {sid}: {str(e)}")
        await sio.emit('error', {
            'message': f'Failed to subscribe to detections: {str(e)}'
        }, room=sid)
        return {'error': str(e)}

@sio.event
async def unsubscribe_detections(sid, data):
    """Unsubscribe from detection events

    This allows graceful cleanup of detection streaming sessions.
    """
    try:
        session_id = data.get('session_id')

        # Remove from active detection streams
        if sid in active_detection_streams:
            stream_info = active_detection_streams[sid]
            logger.info(
                f"🔌 Detection stream closed: {stream_info.get('session_id')} (sid: {sid}) - "
                f"Detections received: {stream_info.get('detection_count', 0)}"
            )
            del active_detection_streams[sid]

        # Leave room if session_id provided
        if session_id:
            room_name = f"test_session_{session_id}"
            await sio.leave_room(sid, room_name)
            logger.info(f"Client {sid} unsubscribed from detections for {session_id}")

        # Send confirmation
        await sio.emit('detection_unsubscription_confirmed', {
            'session_id': session_id,
            'timestamp': asyncio.get_event_loop().time()
        }, room=sid)

        return {'success': True}

    except Exception as e:
        logger.error(f"Error unsubscribing from detections for {sid}: {str(e)}")
        return {'error': str(e)}

@sio.event
async def leave_session(sid, data):
    """Client leaves session room"""
    try:
        session_id = data.get('session_id')

        if not session_id:
            await sio.emit('error', {
                'message': 'session_id required to leave session room'
            }, room=sid)
            return {'error': 'session_id required'}

        room_name = f"session_{session_id}"
        await sio.leave_room(sid, room_name)

        logger.info(f"Client {sid} left session room: {room_name}")

        await sio.emit('left_session', {
            'session_id': session_id,
            'room': room_name,
            'timestamp': asyncio.get_event_loop().time()
        }, room=sid)

        return {'success': True}

    except Exception as e:
        logger.error(f"Error handling leave_session for client {sid}: {str(e)}")
        return {'error': str(e)}

@sio.event
async def join_room(sid, data):
    """Allow clients to join specific rooms (legacy support)"""
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
            
            # FIXED: Emit detection_event only to session room to prevent duplicates
            # Clients should subscribe to the session-specific room, NOT the general 'detections' room
            await sio.emit('detection_event', detection_data, room=room)

            # Emit separate event type for monitoring dashboards (different event name)
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
    # Register video lifecycle handlers if available
    if _video_lifecycle_handlers_available:
        try:
            register_video_lifecycle_handlers(sio, SessionLocal)
            logger.info("✅ Video lifecycle WebSocket handlers registered")
        except Exception as e:
            logger.error(f"Failed to register video lifecycle handlers: {e}")

    socketio_asgi_app = socketio.ASGIApp(sio, fastapi_app)
    return socketio_asgi_app

# Utility functions for real-time detection events
async def emit_detection_event(detection_data: dict, test_session_id: str):
    """Emit real-time detection event to all connected clients

    CRITICAL: This function updates detection counters for keep-alive monitoring.
    """
    try:
        from datetime import datetime

        # CRITICAL FIX: Validate and ensure timestamp field is ALWAYS present and properly formatted
        if 'timestamp' not in detection_data:
            logger.warning(f"⚠️ Detection event missing timestamp, adding current time")
            detection_data['timestamp'] = datetime.now().isoformat()
        elif not isinstance(detection_data['timestamp'], str):
            # Convert non-string timestamps to ISO format
            ts = detection_data['timestamp']
            if hasattr(ts, 'isoformat'):
                detection_data['timestamp'] = ts.isoformat()
            elif isinstance(ts, (int, float)):
                detection_data['timestamp'] = datetime.fromtimestamp(ts).isoformat()
            else:
                logger.warning(f"⚠️ Invalid timestamp type {type(ts)}, using current time")
                detection_data['timestamp'] = datetime.now().isoformat()
        elif len(detection_data['timestamp']) < 10:
            logger.warning(f"⚠️ Timestamp too short: {detection_data['timestamp']}, replacing")
            detection_data['timestamp'] = datetime.now().isoformat()

        # Log timestamp validation
        logger.debug(f"✅ Timestamp validated: {detection_data['timestamp']}")

        # Update detection counter for active streams
        for sid, stream_info in active_detection_streams.items():
            if stream_info.get('session_id') == test_session_id:
                stream_info['detection_count'] = stream_info.get('detection_count', 0) + 1

        # FIXED: Emit to test session room only to prevent duplicates
        # Clients should subscribe to session-specific room, NOT the general 'detections' room
        # CRITICAL FIX: Use "session_" prefix to match client join_session room naming
        room = f"session_{test_session_id}"
        await sio.emit('detection_event', detection_data, room=room)

        logger.debug(f"Emitted detection event to room {room}")

    except Exception as e:
        logger.error(f"❌ Failed to emit detection event: {str(e)}")
        logger.error(f"   Detection data keys: {list(detection_data.keys()) if detection_data else 'None'}")

async def emit_processing_status(status_data: dict, session_id: str):
    """Emit processing status update"""
    try:
        room = f"test_session_{session_id}"
        await sio.emit('processing_status', status_data, room=room)
        logger.debug(f"Emitted processing status to room {room}")
        
    except Exception as e:
        logger.error(f"Failed to emit processing status: {str(e)}")

# Heartbeat functionality for connection keepalive
async def heartbeat_connection(sid: str):
    """Send periodic heartbeat to maintain connection during streaming

    CRITICAL: This prevents premature WebSocket closure during detection streaming
    by maintaining active communication even when no detections are being sent.
    """
    heartbeat_interval = 5  # REDUCED: Send every 5 seconds for active streaming
    max_missed_heartbeats = 3
    missed_count = 0
    heartbeat_count = 0

    logger.info(f"🔌 KEEP-ALIVE: Heartbeat started for client {sid} (interval: {heartbeat_interval}s)")

    try:
        while True:
            await asyncio.sleep(heartbeat_interval)

            # Check if connection is still tracked
            client_session_key = f"client_{sid}"
            is_active_client = client_session_key in active_sessions
            has_detection_stream = sid in active_detection_streams

            # Keep connection alive if either condition is true
            if not (is_active_client or has_detection_stream):
                logger.info(f"🔌 KEEP-ALIVE: Client {sid} no longer active, stopping heartbeat")
                break

            try:
                heartbeat_count += 1

                # Enhanced heartbeat with connection state info
                heartbeat_data = {
                    'type': 'heartbeat',
                    'timestamp': asyncio.get_event_loop().time(),
                    'sid': sid,
                    'count': heartbeat_count,
                    'has_detection_stream': has_detection_stream,
                    'is_active_session': is_active_client
                }

                await sio.emit('heartbeat_ping', heartbeat_data, room=sid)

                # Log heartbeat status (verbose for detection streams)
                if has_detection_stream:
                    stream_info = active_detection_streams[sid]
                    logger.debug(
                        f"🔌 KEEP-ALIVE: Heartbeat #{heartbeat_count} sent to {sid} "
                        f"(detection stream: {stream_info.get('session_id')})"
                    )
                else:
                    logger.debug(f"🔌 KEEP-ALIVE: Heartbeat #{heartbeat_count} sent to {sid}")

                missed_count = 0

            except Exception as heartbeat_error:
                missed_count += 1
                logger.warning(
                    f"⚠️ KEEP-ALIVE: Heartbeat failed for client {sid}: {str(heartbeat_error)} "
                    f"(missed: {missed_count}/{max_missed_heartbeats})"
                )

                if missed_count >= max_missed_heartbeats:
                    logger.warning(
                        f"🔌 KEEP-ALIVE: Client {sid} missed {missed_count} heartbeats, "
                        f"considering disconnected"
                    )

                    # Clean up the client session
                    if client_session_key in active_sessions:
                        del active_sessions[client_session_key]

                    # Clean up detection stream
                    if sid in active_detection_streams:
                        stream_info = active_detection_streams[sid]
                        logger.warning(
                            f"🔌 KEEP-ALIVE: Closing stale detection stream: "
                            f"{stream_info.get('session_id')}"
                        )
                        del active_detection_streams[sid]

                    break

    except asyncio.CancelledError:
        logger.info(f"🔌 KEEP-ALIVE: Heartbeat task cancelled for {sid} (total: {heartbeat_count} heartbeats)")
    except Exception as e:
        logger.error(f"🔌 KEEP-ALIVE: Unexpected error in heartbeat for {sid}: {str(e)}")
    finally:
        # Cleanup on exit
        if sid in connection_heartbeat_tasks:
            del connection_heartbeat_tasks[sid]

@sio.event
async def heartbeat_pong(sid, data):
    """Handle heartbeat response from client"""
    logger.debug(f"Received heartbeat pong from client {sid}")
    
    # Update client activity
    client_session_key = f"client_{sid}"
    if client_session_key in active_sessions:
        active_sessions[client_session_key]['last_heartbeat'] = asyncio.get_event_loop().time()

@sio.event
async def ping(sid, data):
    """Handle ping from client - respond with pong"""
    pong_data = {
        'type': 'pong',
        'timestamp': asyncio.get_event_loop().time(),
        'original_timestamp': data.get('timestamp') if isinstance(data, dict) else None
    }
    await sio.emit('pong', pong_data, room=sid)

@sio.event
async def subscribe_to_updates(sid, data):
    """Handle subscription requests for different update types"""
    try:
        subscription_type = data.get('type')
        target_id = data.get('target_id')

        if subscription_type == 'session' and target_id:
            room = f"test_session_{target_id}"
            await sio.enter_room(sid, room)
            await sio.emit('subscription_confirmed', {
                'type': subscription_type,
                'target_id': target_id,
                'room': room
            }, room=sid)

        elif subscription_type == 'detections':
            await sio.enter_room(sid, 'detections')
            await sio.emit('subscription_confirmed', {
                'type': 'detections',
                'room': 'detections'
            }, room=sid)

        elif subscription_type == 'general':
            await sio.enter_room(sid, 'general')
            await sio.emit('subscription_confirmed', {
                'type': 'general',
                'room': 'general'
            }, room=sid)

        else:
            await sio.emit('subscription_error', {
                'message': f'Unknown subscription type: {subscription_type}'
            }, room=sid)

    except Exception as e:
        logger.error(f"Error handling subscription for {sid}: {str(e)}")
        await sio.emit('subscription_error', {
            'message': f'Subscription failed: {str(e)}'
        }, room=sid)

@sio.event
async def subscribe_sequence(sid, data):
    """Handle video sequence subscription requests for multi-video testing"""
    try:
        sequence_id = data.get('sequence_id')

        if not sequence_id:
            await sio.emit('subscription_error', {
                'message': 'sequence_id is required for sequence subscription',
                'error_type': 'missing_parameter'
            }, room=sid)
            return

        # Validate sequence_id format
        if not isinstance(sequence_id, str) or not sequence_id.strip():
            await sio.emit('subscription_error', {
                'message': 'Invalid sequence_id format',
                'error_type': 'invalid_parameter'
            }, room=sid)
            return

        # Join sequence-specific room
        room = f"sequence_{sequence_id}"
        await sio.enter_room(sid, room)

        logger.info(f"Client {sid} subscribed to sequence {sequence_id}")

        # Send subscription confirmation with metadata
        await sio.emit('subscription_confirmed', {
            'type': 'sequence',
            'sequence_id': sequence_id,
            'room': room,
            'timestamp': asyncio.get_event_loop().time(),
            'events': ['video_transition', 'video_completed', 'sequence_completed']
        }, room=sid)

    except Exception as e:
        logger.error(f"Error handling sequence subscription for {sid}: {str(e)}")
        await sio.emit('subscription_error', {
            'message': f'Sequence subscription failed: {str(e)}',
            'error_type': 'subscription_error',
            'sequence_id': data.get('sequence_id')
        }, room=sid)

@sio.event
async def unsubscribe_sequence(sid, data):
    """Handle video sequence unsubscription requests"""
    try:
        sequence_id = data.get('sequence_id')

        if not sequence_id:
            await sio.emit('subscription_error', {
                'message': 'sequence_id is required for sequence unsubscription',
                'error_type': 'missing_parameter'
            }, room=sid)
            return

        # Leave sequence-specific room
        room = f"sequence_{sequence_id}"
        await sio.leave_room(sid, room)

        logger.info(f"Client {sid} unsubscribed from sequence {sequence_id}")

        # Send unsubscription confirmation
        await sio.emit('unsubscription_confirmed', {
            'type': 'sequence',
            'sequence_id': sequence_id,
            'room': room,
            'timestamp': asyncio.get_event_loop().time()
        }, room=sid)

    except Exception as e:
        logger.error(f"Error handling sequence unsubscription for {sid}: {str(e)}")
        await sio.emit('subscription_error', {
            'message': f'Sequence unsubscription failed: {str(e)}',
            'error_type': 'unsubscription_error',
            'sequence_id': data.get('sequence_id')
        }, room=sid)

# WebSocket event handlers for timing synchronization
@sio.event
async def subscribe_hardware_signals(sid, data):
    """Handle hardware signal subscription requests with timing synchronization"""
    try:
        session_id = data.get('sessionId')
        wait_for_ready = data.get('waitForReady', False)
        
        if not session_id:
            await sio.emit('error', {
                'message': 'sessionId is required for hardware signal subscription'
            }, room=sid)
            return
        
        # Join session-specific room
        room = f"hardware_signals_{session_id}"
        await sio.enter_room(sid, room)
        
        logger.info(f"Client {sid} subscribed to hardware signals for session {session_id}")
        
        # Send subscription confirmation
        await sio.emit('hardware_subscription_confirmed', {
            'session_id': session_id,
            'room': room,
            'timestamp': asyncio.get_event_loop().time(),
            'wait_for_ready': wait_for_ready
        }, room=sid)
        
        # If waiting for ready confirmation, we'll send monitoring_ready event later
        if wait_for_ready:
            logger.info(f"Client {sid} waiting for monitoring ready confirmation for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error handling hardware signal subscription: {str(e)}")
        await sio.emit('error', {
            'message': f'Hardware signal subscription failed: {str(e)}'
        }, room=sid)

@sio.event
async def video_started(sid, data):
    """Handle video started events for timing synchronization AND video_id assignment"""
    try:
        session_id = data.get('sessionId')
        video_id = data.get('videoId')  # CRITICAL: Must include video_id for detection assignment
        sequence_id = data.get('sequenceId')  # For multi-video sequences
        video_start_time = data.get('videoStartTime')
        setup_delay = data.get('setupDelay')

        if not session_id:
            await sio.emit('error', {
                'message': 'sessionId is required for video started event'
            }, room=sid)
            return

        # AGENT #40 FIX: Ensure room exists before emitting
        # This safeguard prevents event loss if session was created but client hasn't joined yet
        room = f"session_{session_id}"

        # Check if room exists in manager
        try:
            # Get all rooms for the default namespace
            namespace_rooms = sio.manager.rooms.get('/', {})

            if room not in namespace_rooms:
                # Room doesn't exist yet - create it by having a "system" client join
                logger.warning(f"⚠️ AGENT #40: Room {room} doesn't exist, auto-creating for early event")
                # The room will be implicitly created when we emit to it
                # No need to explicitly create - Socket.IO handles this
            else:
                logger.debug(f"✅ AGENT #40: Room {room} exists with {len(namespace_rooms[room])} clients")

        except Exception as room_check_error:
            logger.debug(f"Room check skipped (this is normal): {room_check_error}")
            # Continue - room will be created implicitly on emit

        if not video_id:
            logger.warning(f"Video started event missing video_id for session {session_id}")

        # CLOCK SYNC VALIDATION: Verify frontend timestamp synchronization
        if video_start_time:
            try:
                from services.clock_sync_service import validate_clock_sync, ClockSkewError, log_clock_drift_metrics

                # Log drift metrics for monitoring
                drift_metrics = log_clock_drift_metrics(
                    frontend_timestamp=video_start_time,
                    context=f"video_started_{video_id}"
                )

                # Validate clock sync (raises ClockSkewError if drift exceeds tolerance)
                validate_clock_sync(
                    frontend_timestamp=video_start_time,
                    max_frontend_drift_seconds=5.0
                )

                logger.debug(f"✅ Clock sync validated for video_started (drift: {drift_metrics['frontend_drift_abs_ms']:.1f}ms)")

            except ClockSkewError as clock_error:
                logger.error(f"❌ CLOCK SKEW DETECTED on video_started event:")
                logger.error(f"   Drift: {clock_error.drift_seconds:.3f}s exceeds 5.0s tolerance")
                logger.error(f"   Session: {session_id}, Video: {video_id}")

                # Reject the event and notify client
                await sio.emit('error', {
                    'message': f'Clock skew detected: {clock_error.drift_seconds:.3f}s drift exceeds tolerance',
                    'error_type': 'clock_skew',
                    'drift_seconds': clock_error.drift_seconds,
                    'max_tolerance_seconds': 5.0
                }, room=sid)
                return

        logger.info(f"Video started event received from client {sid} for session {session_id}, video {video_id}")

        # ✅ CRITICAL FIX AGENT 2: Update TestSession.video_id for detection assignment
        if session_id and video_id:
            db = SessionLocal()
            try:
                from models import TestSession

                # Update the session's current video_id
                session = db.query(TestSession).filter(
                    TestSession.id == session_id
                ).first()

                if session:
                    session.video_id = video_id
                    db.commit()
                    logger.info(f"✅ AGENT 2: Updated TestSession.video_id={video_id} for session {session_id}")
                else:
                    logger.error(f"❌ AGENT 2: TestSession {session_id} not found")
            except Exception as session_error:
                logger.error(f"❌ AGENT 2: Failed to update TestSession.video_id: {session_error}")
                db.rollback()
            finally:
                db.close()

        # CRITICAL FIX: Notify orchestrator to enable video_id assignment for incoming detections
        if sequence_id and video_id and video_start_time:
            try:
                from services.video_sequence_orchestrator import get_video_sequence_orchestrator
                orchestrator = get_video_sequence_orchestrator()

                # Open database session for orchestrator
                db = SessionLocal()
                try:
                    success = orchestrator.notify_video_started(
                        sequence_id=sequence_id,
                        video_id=video_id,
                        actual_start_timestamp=video_start_time,
                        db=db
                    )
                    if success:
                        logger.info(f"✅ Orchestrator notified: video {video_id} started in sequence {sequence_id}")
                    else:
                        logger.error(f"❌ Orchestrator failed to process video started event")
                finally:
                    db.close()
            except Exception as orch_error:
                logger.error(f"Failed to notify orchestrator of video start: {orch_error}")

        # QUEEN'S PROTOCOL #37: Invalidate cache and pre-generate clamped windows
        if session_id:
            try:
                from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
                labjack_monitor = get_dedicated_labjack_monitor()
                labjack_monitor.invalidate_sequence_cache(session_id)
                logger.info(f"✅ QUEEN #37: Cache invalidated and windows pre-generated for session {session_id}")
            except Exception as cache_error:
                logger.error(f"❌ Failed to invalidate cache on video_started: {cache_error}")

        # Record video timing in synchronization service
        try:
            from services.timing_synchronization_service import timing_sync_service
            timing_sync_service.record_video_event(session_id, 'play_start', video_start_time)

            if setup_delay:
                logger.info(f"Video setup took {setup_delay:.1f}ms for session {session_id}")
        except Exception as timing_error:
            logger.warning(f"Failed to record video timing: {timing_error}")

        # Get sequence number for event ordering
        sequence_number = await get_next_sequence_number()

        # ISSUE #1 FIX: Change event names to match frontend expectations
        # Frontend expects 'video_started' and 'video_ended' NOT 'video_transition'

        # CRITICAL FIX #3: Broadcast with camelCase fields to match frontend
        # PROTOCOL #39: Add sequence_number for frontend event ordering
        room = f"test_session_{session_id}"
        await sio.emit('video_lifecycle', {
            'event': 'video_started',
            'sequence_number': sequence_number,
            'sessionId': session_id,
            'videoId': video_id,
            'sequenceId': sequence_id,
            'videoStartTime': video_start_time,
            'setupDelay': setup_delay,
            'timestamp': asyncio.get_event_loop().time()
        }, room=room)

        # Send confirmation back to sender with camelCase
        await sio.emit('video_started_confirmed', {
            'sessionId': session_id,
            'videoId': video_id,
            'sequenceId': sequence_id,
            'recordedTime': video_start_time,
            'sequence_number': sequence_number,
            'timestamp': asyncio.get_event_loop().time()
        }, room=sid)

    except Exception as e:
        logger.error(f"Error handling video started event: {str(e)}")
        await sio.emit('error', {
            'message': f'Video started event handling failed: {str(e)}'
        }, room=sid)

@sio.event
async def video_ended(sid, data):
    """Handle video ended events for lifecycle management and result evaluation"""
    try:
        session_id = data.get('sessionId')
        video_id = data.get('videoId')
        sequence_id = data.get('sequenceId')
        video_end_time = data.get('videoEndTime')
        actual_duration = data.get('actualDuration')

        if not session_id:
            await sio.emit('error', {
                'message': 'sessionId is required for video ended event'
            }, room=sid)
            return

        # AGENT #40 FIX: Ensure room exists before emitting
        room = f"session_{session_id}"

        try:
            namespace_rooms = sio.manager.rooms.get('/', {})
            if room not in namespace_rooms:
                logger.warning(f"⚠️ AGENT #40: Room {room} doesn't exist for video_ended, auto-creating")
            else:
                logger.debug(f"✅ AGENT #40: Room {room} exists for video_ended event")
        except Exception as room_check_error:
            logger.debug(f"Room check skipped: {room_check_error}")

        logger.info(f"Video ended event received from client {sid} for session {session_id}, video {video_id}")

        # CRITICAL FIX: Persist video_end_time and actual_duration_ms to SequenceVideoResult table IMMEDIATELY
        if sequence_id and video_id and video_end_time:
            db = SessionLocal()
            try:
                from models import VideoTestSequence, SequenceVideoResult

                # Find VideoTestSequence by sequence_id
                video_sequence = db.query(VideoTestSequence).filter(
                    VideoTestSequence.id == sequence_id
                ).first()

                if video_sequence:
                    # Find SequenceVideoResult for this video
                    video_result = db.query(SequenceVideoResult).filter(
                        SequenceVideoResult.video_sequence_id == video_sequence.id,
                        SequenceVideoResult.video_id == video_id
                    ).first()

                    if video_result:
                        # Update video_end_time and calculate actual_duration_ms
                        video_result.video_end_time = video_end_time
                        video_result.video_status = "completed"

                        # Calculate actual_duration_ms if video_start_time exists
                        if video_result.video_start_time:
                            video_result.actual_duration_ms = (video_end_time - video_result.video_start_time) * 1000.0
                            logger.info(f"✅ PERSISTED video_end_time={video_end_time:.6f}, actual_duration_ms={video_result.actual_duration_ms:.2f} for video {video_id}")
                        else:
                            logger.warning(f"⚠️ video_start_time is NULL - cannot calculate actual_duration_ms for video {video_id}")

                        db.commit()
                    else:
                        logger.error(f"❌ ERROR: SequenceVideoResult not found for video {video_id} in sequence {sequence_id}")
                else:
                    logger.error(f"❌ ERROR: VideoTestSequence not found for sequence_id {sequence_id}")
            except Exception as db_error:
                logger.error(f"❌ FAILED to persist video_end_time to database: {db_error}")
                db.rollback()
            finally:
                db.close()

        # CRITICAL FIX: Notify orchestrator to evaluate video results and stop detection assignment
        if sequence_id and video_id and video_end_time:
            try:
                from services.video_sequence_orchestrator import get_video_sequence_orchestrator
                orchestrator = get_video_sequence_orchestrator()

                # Open database session for orchestrator
                db = SessionLocal()
                try:
                    success = orchestrator.notify_video_ended(
                        sequence_id=sequence_id,
                        video_id=video_id,
                        actual_end_timestamp=video_end_time,
                        db=db
                    )
                    if success:
                        logger.info(f"✅ Orchestrator notified: video {video_id} ended in sequence {sequence_id}")
                        logger.info(f"   Actual duration: {actual_duration:.2f}s" if actual_duration else "   Duration not provided")
                    else:
                        logger.error(f"❌ Orchestrator failed to process video ended event")
                finally:
                    db.close()
            except Exception as orch_error:
                logger.error(f"Failed to notify orchestrator of video end: {orch_error}")

        # QUEEN'S PROTOCOL #37: Invalidate cache and pre-generate clamped windows
        if session_id:
            try:
                from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
                labjack_monitor = get_dedicated_labjack_monitor()
                labjack_monitor.invalidate_sequence_cache(session_id)
                logger.info(f"✅ QUEEN #37: Cache invalidated and windows pre-generated for session {session_id}")
            except Exception as cache_error:
                logger.error(f"❌ Failed to invalidate cache on video_ended: {cache_error}")

        # Get sequence number for event ordering
        sequence_number = await get_next_sequence_number()

        # Calculate duration in milliseconds for consistency
        duration_ms = None
        if actual_duration is not None:
            duration_ms = actual_duration * 1000.0

        # CRITICAL FIX #3: Emit 'video_ended' with camelCase to match frontend
        # PROTOCOL #39: Add sequence_number for frontend event ordering

        # Broadcast to session room with camelCase fields
        room = f"test_session_{session_id}"
        await sio.emit('video_lifecycle', {
            'event': 'video_ended',
            'sequence_number': sequence_number,
            'sessionId': session_id,
            'videoId': video_id,
            'sequenceId': sequence_id,
            'videoEndTime': video_end_time,
            'actualDuration': actual_duration,
            'duration_ms': duration_ms,
            'timestamp': asyncio.get_event_loop().time()
        }, room=room)

        # Send confirmation back to sender with camelCase
        await sio.emit('video_ended_confirmed', {
            'sessionId': session_id,
            'videoId': video_id,
            'sequenceId': sequence_id,
            'recordedTime': video_end_time,
            'sequence_number': sequence_number,
            'timestamp': asyncio.get_event_loop().time()
        }, room=sid)

    except Exception as e:
        logger.error(f"Error handling video ended event: {str(e)}")
        await sio.emit('error', {
            'message': f'Video ended event handling failed: {str(e)}'
        }, room=sid)

# Enhanced utility functions
async def emit_hil_status_update(session_id: str, status_data: dict):
    """Emit HIL-specific status updates to session room only"""
    try:
        enhanced_data = {
            **status_data,
            'timestamp': asyncio.get_event_loop().time(),
            'update_type': 'hil_status'
        }

        # Emit to session room only (no session_id in payload - already scoped by room)
        room = f"session_{session_id}"
        await sio.emit('hil_status_update', enhanced_data, room=room)

        logger.debug(f"Emitted HIL status update to session room {room}")

    except Exception as e:
        logger.error(f"Failed to emit HIL status update: {str(e)}")

async def emit_system_notification(notification_type: str, message: str, data: dict = None):
    """Emit system-wide notifications"""
    try:
        notification_data = {
            'type': notification_type,
            'message': message,
            'timestamp': asyncio.get_event_loop().time(),
            'data': data or {}
        }
        
        await sio.emit('system_notification', notification_data, room='general')
        logger.info(f"Emitted system notification: {notification_type} - {message}")
        
    except Exception as e:
        logger.error(f"Failed to emit system notification: {str(e)}")

# Export the Socket.IO server for use in main.py
__all__ = [
    'sio', 'create_socketio_app', 'emit_detection_event', 'emit_processing_status',
    'emit_hil_status_update', 'emit_system_notification', 'heartbeat_connection',
    'active_detection_streams', 'connection_heartbeat_tasks'
]