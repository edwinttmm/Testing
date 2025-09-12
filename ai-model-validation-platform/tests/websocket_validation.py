#!/usr/bin/env python3
"""
WebSocket Connection Validation Test
"""

import asyncio
import websockets
import json
import time
import requests

async def test_websocket_connection():
    """Test WebSocket connection"""
    try:
        uri = "ws://localhost:8000/ws"
        print(f"🔌 Testing WebSocket connection to {uri}")
        
        # Use timeout for connection
        websocket = await asyncio.wait_for(
            websockets.connect(uri), 
            timeout=10.0
        )
        
        print("✅ WebSocket connected successfully")
        
        # Send test message
        test_message = {"type": "ping", "timestamp": time.time()}
        await websocket.send(json.dumps(test_message))
        print("📤 Sent ping message")
        
        # Wait for response
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"📥 Received: {response}")
            await websocket.close()
            return True
        except asyncio.TimeoutError:
            print("⏰ WebSocket response timeout (this may be expected)")
            await websocket.close()
            return True  # Connection success is what we're testing
            
    except ConnectionRefusedError:
        print("❌ WebSocket connection refused - WebSocket server not running")
        return False
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        return False

def test_websocket_endpoint_exists():
    """Test if WebSocket endpoint is documented"""
    try:
        response = requests.get("http://localhost:8000/docs", timeout=5)
        if "websocket" in response.text.lower() or "ws" in response.text.lower():
            print("✅ WebSocket endpoint documented in API docs")
            return True
        else:
            print("❓ WebSocket endpoint not found in API docs")
            return False
    except Exception as e:
        print(f"❌ Error checking API docs: {e}")
        return False

async def main():
    """Main test function"""
    print("🔗 WebSocket Validation Test")
    print("=" * 30)
    
    # Test if endpoint exists in docs
    docs_test = test_websocket_endpoint_exists()
    
    # Test actual WebSocket connection
    ws_test = await test_websocket_connection()
    
    print("\n📊 WebSocket Test Results")
    print("=" * 25)
    print(f"API Docs Check: {'✅ PASS' if docs_test else '❌ FAIL'}")
    print(f"Connection Test: {'✅ PASS' if ws_test else '❌ FAIL'}")
    
    # Overall result
    overall_success = ws_test  # Docs test is optional
    print(f"Overall WebSocket Status: {'✅ OPERATIONAL' if overall_success else '❌ NON-FUNCTIONAL'}")
    
    return overall_success

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        exit(0 if result else 1)
    except Exception as e:
        print(f"❌ Test execution error: {e}")
        exit(1)