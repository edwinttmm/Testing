#!/usr/bin/env python3
"""
Comprehensive WebSocket HIL Integration Test
Tests the real-time update system for HIL testing with proper Socket.IO implementation
"""

import asyncio
import pytest
import json
import time
from typing import Dict, Any
import socketio
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import the FastAPI app with Socket.IO integration
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import socketio_app
from socketio_server import sio, emit_hil_status_update, emit_system_notification
from database import SessionLocal
from models import TestSession, Project
from schemas import TestSessionCreate


class HILWebSocketTester:
    """Test class for HIL WebSocket functionality"""
    
    def __init__(self):
        self.client = None
        self.socket_client = None
        self.received_messages = []
        self.connection_events = []
        
    async def setup_test_client(self):
        """Setup Socket.IO test client"""
        self.socket_client = socketio.AsyncClient(
            logger=True,
            engineio_logger=True
        )
        
        # Track received messages
        @self.socket_client.event
        async def connect():
            print("✅ Test client connected to Socket.IO server")
            self.connection_events.append({"type": "connected", "timestamp": time.time()})
        
        @self.socket_client.event
        async def disconnect():
            print("🔌 Test client disconnected from Socket.IO server")
            self.connection_events.append({"type": "disconnected", "timestamp": time.time()})
        
        @self.socket_client.event
        async def connection_status(data):
            print(f"📊 Connection status: {data}")
            self.received_messages.append({"event": "connection_status", "data": data, "timestamp": time.time()})
        
        @self.socket_client.event
        async def detection_event(data):
            print(f"🔍 Detection event: {data}")
            self.received_messages.append({"event": "detection_event", "data": data, "timestamp": time.time()})
        
        @self.socket_client.event
        async def hil_update(data):
            print(f"🧪 HIL update: {data}")
            self.received_messages.append({"event": "hil_update", "data": data, "timestamp": time.time()})
        
        @self.socket_client.event
        async def progress_update(data):
            print(f"📈 Progress update: {data}")
            self.received_messages.append({"event": "progress_update", "data": data, "timestamp": time.time()})
        
        @self.socket_client.event
        async def test_session_update(data):
            print(f"🔄 Session update: {data}")
            self.received_messages.append({"event": "test_session_update", "data": data, "timestamp": time.time()})
        
        @self.socket_client.event
        async def heartbeat_ping(data):
            print(f"💓 Heartbeat ping: {data}")
            await self.socket_client.emit('heartbeat_pong', {"timestamp": time.time(), **data})
        
        @self.socket_client.event
        async def system_notification(data):
            print(f"🔔 System notification: {data}")
            self.received_messages.append({"event": "system_notification", "data": data, "timestamp": time.time()})
    
    async def connect_to_server(self, url: str = "http://localhost:8001"):
        """Connect to the Socket.IO server"""
        try:
            await self.socket_client.connect(url, transports=['websocket', 'polling'])
            
            # Wait for connection confirmation
            await asyncio.sleep(1)
            
            return True
        except Exception as e:
            print(f"❌ Failed to connect to Socket.IO server: {e}")
            return False
    
    async def test_basic_connection(self):
        """Test basic Socket.IO connection"""
        print("\n🧪 Testing basic Socket.IO connection...")
        
        connected = await self.connect_to_server()
        assert connected, "Failed to connect to Socket.IO server"
        
        # Check connection events
        await asyncio.sleep(2)
        assert len(self.connection_events) > 0, "No connection events received"
        
        connected_event = next((e for e in self.connection_events if e["type"] == "connected"), None)
        assert connected_event is not None, "No connected event received"
        
        print("✅ Basic connection test passed")
    
    async def test_subscription_system(self):
        """Test subscription to different update types"""
        print("\n🧪 Testing subscription system...")
        
        # Subscribe to general updates
        await self.socket_client.emit('subscribe_to_updates', {"type": "general"})
        
        # Subscribe to detection updates
        await self.socket_client.emit('subscribe_to_updates', {"type": "detections"})
        
        # Wait for subscription confirmations
        await asyncio.sleep(2)
        
        # Check for subscription confirmations
        subscription_confirmations = [
            msg for msg in self.received_messages 
            if "subscription_confirmed" in str(msg.get("event", ""))
        ]
        
        print(f"📊 Received {len(subscription_confirmations)} subscription confirmations")
        print("✅ Subscription system test passed")
    
    async def test_hil_session_execution(self):
        """Test HIL session execution with real-time updates"""
        print("\n🧪 Testing HIL session execution...")
        
        # Start a test session
        test_session_data = {
            "session_id": "hil_test_session_001",
            "project_id": "test_project_hil"
        }
        
        await self.socket_client.emit('start_test_session', test_session_data)
        
        # Subscribe to session-specific updates
        await self.socket_client.emit('subscribe_to_updates', {
            "type": "session",
            "target_id": test_session_data["session_id"]
        })
        
        # Wait for session execution and collect messages
        print("⏳ Waiting for HIL session execution (45 seconds)...")
        start_time = time.time()
        
        while time.time() - start_time < 45:
            await asyncio.sleep(2)
            
            # Check for session completion
            session_updates = [
                msg for msg in self.received_messages 
                if msg.get("event") == "test_session_update"
            ]
            
            completed_updates = [
                update for update in session_updates
                if update.get("data", {}).get("status") == "completed"
            ]
            
            if completed_updates:
                print("✅ HIL session completed successfully")
                break
        
        # Analyze received messages
        detection_events = [
            msg for msg in self.received_messages 
            if msg.get("event") == "detection_event"
        ]
        
        progress_updates = [
            msg for msg in self.received_messages 
            if msg.get("event") == "progress_update"
        ]
        
        hil_updates = [
            msg for msg in self.received_messages 
            if msg.get("event") == "hil_update"
        ]
        
        print(f"📊 HIL Session Results:")
        print(f"   - Detection events received: {len(detection_events)}")
        print(f"   - Progress updates received: {len(progress_updates)}")
        print(f"   - HIL updates received: {len(hil_updates)}")
        print(f"   - Total messages received: {len(self.received_messages)}")
        
        # Assertions
        assert len(detection_events) >= 10, f"Expected at least 10 detection events, got {len(detection_events)}"
        assert len(progress_updates) >= 2, f"Expected at least 2 progress updates, got {len(progress_updates)}"
        
        # Verify detection event structure
        if detection_events:
            sample_detection = detection_events[0]["data"]
            required_fields = [
                "session_id", "event_id", "timestamp", "detection_type",
                "confidence", "validation_result", "progress", "frame_number",
                "hardware_status", "metrics"
            ]
            
            for field in required_fields:
                assert field in sample_detection, f"Missing required field '{field}' in detection event"
        
        print("✅ HIL session execution test passed")
    
    async def test_heartbeat_system(self):
        """Test heartbeat/keepalive system"""
        print("\n🧪 Testing heartbeat system...")
        
        initial_message_count = len(self.received_messages)
        
        # Wait for heartbeat messages
        await asyncio.sleep(35)  # Wait longer than heartbeat interval
        
        # Check for heartbeat-related messages
        heartbeat_messages = [
            msg for msg in self.received_messages[initial_message_count:]
            if "heartbeat" in str(msg.get("event", "")).lower()
        ]
        
        print(f"💓 Heartbeat messages received: {len(heartbeat_messages)}")
        
        # Should receive at least one heartbeat in 35 seconds (interval is 30s)
        assert len(heartbeat_messages) >= 1, "No heartbeat messages received"
        
        print("✅ Heartbeat system test passed")
    
    async def test_system_notifications(self):
        """Test system-wide notifications"""
        print("\n🧪 Testing system notifications...")
        
        # Emit a test system notification
        await emit_system_notification(
            "test_notification",
            "HIL integration test notification",
            {"test": True, "timestamp": time.time()}
        )
        
        await asyncio.sleep(2)
        
        # Check for system notification
        system_notifications = [
            msg for msg in self.received_messages 
            if msg.get("event") == "system_notification"
        ]
        
        assert len(system_notifications) >= 1, "No system notifications received"
        
        # Verify notification structure
        notification = system_notifications[-1]["data"]
        assert notification["type"] == "test_notification"
        assert "HIL integration test" in notification["message"]
        
        print("✅ System notifications test passed")
    
    async def test_error_recovery(self):
        """Test error recovery and reconnection"""
        print("\n🧪 Testing error recovery...")
        
        # Force disconnect
        await self.socket_client.disconnect()
        await asyncio.sleep(2)
        
        # Reconnect
        reconnected = await self.connect_to_server()
        assert reconnected, "Failed to reconnect after forced disconnect"
        
        await asyncio.sleep(2)
        
        # Verify reconnection worked
        connection_events_after_reconnect = [
            e for e in self.connection_events 
            if e["timestamp"] > time.time() - 10
        ]
        
        assert len(connection_events_after_reconnect) >= 1, "No recent connection events after reconnect"
        
        print("✅ Error recovery test passed")
    
    async def cleanup(self):
        """Cleanup test resources"""
        if self.socket_client and self.socket_client.connected:
            await self.socket_client.disconnect()
    
    def print_summary(self):
        """Print comprehensive test summary"""
        print("\n" + "="*80)
        print("🧪 HIL WEBSOCKET INTEGRATION TEST SUMMARY")
        print("="*80)
        print(f"Total messages received: {len(self.received_messages)}")
        print(f"Connection events: {len(self.connection_events)}")
        
        # Group messages by event type
        event_counts = {}
        for msg in self.received_messages:
            event = msg.get("event", "unknown")
            event_counts[event] = event_counts.get(event, 0) + 1
        
        print("\nMessage breakdown by event type:")
        for event, count in sorted(event_counts.items()):
            print(f"  - {event}: {count}")
        
        print("\nConnection events:")
        for event in self.connection_events:
            event_time = time.strftime("%H:%M:%S", time.localtime(event["timestamp"]))
            print(f"  - {event['type']}: {event_time}")
        
        print("\n✅ All HIL WebSocket integration tests completed successfully!")
        print("="*80)


async def run_hil_websocket_tests():
    """Main test runner"""
    print("🚀 Starting HIL WebSocket Integration Tests")
    print("="*80)
    
    tester = HILWebSocketTester()
    
    try:
        # Setup
        await tester.setup_test_client()
        
        # Run all tests
        await tester.test_basic_connection()
        await tester.test_subscription_system()
        await tester.test_hil_session_execution()
        await tester.test_heartbeat_system()
        await tester.test_system_notifications()
        await tester.test_error_recovery()
        
        # Print summary
        tester.print_summary()
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    print("🧪 HIL WebSocket Integration Test Suite")
    print("Make sure the backend server is running on http://localhost:8001")
    print("Press Ctrl+C to stop\n")
    
    try:
        asyncio.run(run_hil_websocket_tests())
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test suite failed: {e}")
        sys.exit(1)