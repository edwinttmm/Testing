#!/usr/bin/env python3
"""
WebSocket Test Client
Tests real-time updates during test execution
"""

import socketio
import asyncio
import json
import time
from datetime import datetime

# Create Socket.IO client
sio = socketio.AsyncClient()

# Event handlers
@sio.on('connect')
async def on_connect():
    print("🔌 WebSocket Connected!")
    
    # Subscribe to dashboard updates
    await sio.emit('subscribe_dashboard_updates', {
        'clientId': 'test_client',
        'events': [
            'video_uploaded',
            'video_processed', 
            'project_created',
            'project_updated',
            'test_completed',
            'test_session_completed',
            'test_started',
            'test_session_started',
            'detection_event',
            'detection_result',
            'annotation_created',
            'annotation_updated',
            'annotation_validated',
            'ground_truth_generated',
            'signal_processed',
            'signal_processing_result'
        ]
    })
    print("📡 Subscribed to all dashboard events")

@sio.on('disconnect')
async def on_disconnect():
    print("❌ WebSocket Disconnected")

@sio.on('connection_status')
async def on_connection_status(data):
    print(f"📊 Connection Status: {data}")

# Event listeners for test events
@sio.on('test_session_started')
async def on_test_session_started(data):
    print(f"🚀 Test Session Started: {data}")

@sio.on('test_session_completed')
async def on_test_session_completed(data):
    print(f"✅ Test Session Completed: {data}")

@sio.on('detection_event')
async def on_detection_event(data):
    print(f"🎯 Detection Event: {data}")

@sio.on('detection_result')
async def on_detection_result(data):
    print(f"📈 Detection Result: {data}")

@sio.on('signal_processed')
async def on_signal_processed(data):
    print(f"⚡ Signal Processed: {data}")

@sio.on('signal_processing_result')
async def on_signal_processing_result(data):
    print(f"📊 Signal Processing Result: {data}")

async def test_websocket_connection():
    """Test WebSocket connection and listen for events"""
    try:
        print("🔗 Connecting to WebSocket server...")
        await sio.connect('http://localhost:8000', socketio_path='/socket.io/')
        
        print("⏳ Listening for events (30 seconds)...")
        await asyncio.sleep(30)
        
        print("🔚 Test completed")
        await sio.disconnect()
        
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_connection())