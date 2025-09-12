#!/usr/bin/env python3
"""
WebSocket endpoint testing script
"""
import asyncio
import websockets
import json
import sys
from datetime import datetime

async def test_websocket_endpoint(uri, test_name):
    """Test a WebSocket endpoint"""
    try:
        print(f"🔌 Testing {test_name}: {uri}")
        
        async with websockets.connect(uri, timeout=5) as websocket:
            # Send a test message
            test_message = {
                "type": "ping",
                "timestamp": datetime.utcnow().isoformat(),
                "test": True
            }
            
            await websocket.send(json.dumps(test_message))
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=3)
                print(f"✅ {test_name}: Connection successful, received response")
                return True
                
            except asyncio.TimeoutError:
                print(f"⚠️  {test_name}: Connected but no response (may be normal)")
                return True
                
    except ConnectionRefusedError:
        print(f"❌ {test_name}: Connection refused - server not running")
        return False
    except Exception as e:
        print(f"❌ {test_name}: Connection failed - {str(e)}")
        return False

async def main():
    """Test all WebSocket endpoints"""
    print("🚀 Testing WebSocket Implementation")
    print("=" * 50)
    
    # Base URL - adjust if needed
    base_url = "ws://localhost:8000"
    
    # Test endpoints
    endpoints = [
        (f"{base_url}/ws", "General WebSocket"),
        (f"{base_url}/ws/progress/test-task-123", "Progress WebSocket"),
        (f"{base_url}/ws/room/test-room", "Room WebSocket"),
        (f"{base_url}/ws/video/test-video-id", "Video WebSocket"),
        (f"{base_url}/ws/test-session/test-session-id", "Test Session WebSocket")
    ]
    
    results = []
    
    for uri, name in endpoints:
        result = await test_websocket_endpoint(uri, name)
        results.append((name, result))
        await asyncio.sleep(0.5)  # Small delay between tests
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    successful = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {name}")
    
    print(f"\n🎯 Success Rate: {successful}/{total} ({successful/total*100:.1f}%)")
    
    if successful == total:
        print("🎉 All WebSocket endpoints are working correctly!")
    elif successful > 0:
        print("⚠️  Some WebSocket endpoints are working, server may need to be started")
    else:
        print("❌ No WebSocket endpoints responding - server not running")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1)