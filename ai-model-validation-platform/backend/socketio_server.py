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

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=['http://localhost:3001', 'http://127.0.0.1:3001'],
    logger=True,
    engineio_logger=True
)

# Store active test sessions
active_sessions: Dict[str, Any] = {}

@sio.event
async def connect(sid, environ, auth):
    """Handle client connections"""
    logger.info(f"Client {sid} connected")
    
    # In development, allow all connections
    # In production, validate auth token here
    if auth and 'token' in auth:
        logger.info(f"Client {sid} authenticated with token")
    
    await sio.emit('connection_status', {
        'status': 'connected',
        'message': 'Connected to real-time server'
    }, room=sid)
    
    return True

@sio.event
async def disconnect(sid):
    """Handle client disconnections"""
    logger.info(f"Client {sid} disconnected")
    
    # Clean up any active sessions for this client
    sessions_to_remove = []
    for session_id, session_data in active_sessions.items():
        if session_data.get('client_id') == sid:
            sessions_to_remove.append(session_id)
    
    for session_id in sessions_to_remove:
        del active_sessions[session_id]
        logger.info(f"Cleaned up session {session_id} for disconnected client {sid}")

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
    """Background task to simulate test session execution"""
    try:
        if session_id not in active_sessions:
            return
        
        session_data = active_sessions[session_id]
        room = f"test_session_{session_id}"
        
        # Simulate test execution with periodic updates
        for i in range(10):  # Simulate 10 detection events
            if session_data['status'] != 'running':
                break
            
            # Wait between events
            await asyncio.sleep(2)
            
            # Emit detection event
            await sio.emit('detection_event', {
                'session_id': session_id,
                'event_id': f"event_{i+1}",
                'timestamp': asyncio.get_event_loop().time(),
                'detection_type': 'person' if i % 2 == 0 else 'vehicle',
                'confidence': 0.85 + (i * 0.01),
                'validation_result': 'TP' if i % 3 != 0 else 'FP',
                'progress': (i + 1) / 10 * 100
            }, room=room)
        
        # Complete the session
        if session_data['status'] == 'running':
            session_data['status'] = 'completed'
            await sio.emit('test_session_update', {
                'session_id': session_id,
                'status': 'completed',
                'message': 'Test session completed successfully',
                'total_events': 10,
                'completion_time': asyncio.get_event_loop().time()
            }, room=room)
            
    except Exception as e:
        logger.error(f"Error in test session {session_id}: {str(e)}")
        await sio.emit('error', {
            'session_id': session_id,
            'message': f'Test session error: {str(e)}'
        }, room=f"test_session_{session_id}")

def create_socketio_app(fastapi_app: FastAPI):
    """Integrate Socket.IO with FastAPI"""
    socketio_asgi_app = socketio.ASGIApp(sio, fastapi_app)
    return socketio_asgi_app

# Export the Socket.IO server for use in main.py
__all__ = ['sio', 'create_socketio_app']