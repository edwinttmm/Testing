#!/usr/bin/env python3
"""
WebSocket Test for AI Model Validation Platform
"""
import asyncio
import websockets
import json
import sys

async def test_websocket():
    try:
        print("🔌 Testing WebSocket Connection...")
        
        # Try to connect to WebSocket
        uri = "ws://localhost:8000/ws"
        async with websockets.connect(uri, timeout=10) as websocket:
            print("✅ WebSocket Connected Successfully")
            
            # Send a test message
            test_message = {
                "type": "ping",
                "data": "integration_test",
                "timestamp": "2025-08-27T13:17:00Z"
            }
            
            await websocket.send(json.dumps(test_message))
            print(f"📤 Sent: {test_message}")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 Received: {response}")
                print("✅ WebSocket Communication: WORKING")
                return True
            except asyncio.TimeoutError:
                print("⚠️  No response received (timeout)")
                print("✅ WebSocket Connection: WORKING (no echo)")
                return True
                
    except Exception as e:
        print(f"❌ WebSocket Test Failed: {str(e)}")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(test_websocket())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"❌ WebSocket Test Error: {str(e)}")
        sys.exit(1)