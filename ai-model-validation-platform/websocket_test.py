#\!/usr/bin/env python3
import websockets
import asyncio
import json
import time

async def test_websocket_connection():
    """Test WebSocket connection"""
    try:
        uri = "ws://localhost:8000/ws"
        print(f"🔌 Testing WebSocket connection to {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connected successfully")
            
            # Send test message
            test_message = {"type": "ping", "timestamp": time.time()}
            await websocket.send(json.dumps(test_message))
            print("📤 Sent ping message")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 Received: {response}")
                return True
            except asyncio.TimeoutError:
                print("⏰ WebSocket response timeout")
                return False
                
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        return False

def test_websocket_sync():
    """Synchronous wrapper for WebSocket test"""
    return asyncio.run(test_websocket_connection())

if __name__ == "__main__":
    success = test_websocket_sync()
    print(f"WebSocket test result: {\"✅ SUCCESS\" if success else \"❌ FAILED\"}")

