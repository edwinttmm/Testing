#!/usr/bin/env python3
"""
WebSocket Connection Testing
Tests real-time features and WebSocket connectivity
"""

import asyncio
import websockets
import json
import time

async def test_websocket_connection():
    """Test WebSocket connection and real-time features"""
    results = {
        "connection_status": "unknown",
        "response_time_ms": 0,
        "error": None
    }
    
    try:
        start_time = time.time()
        
        # Try to connect to WebSocket
        uri = "ws://localhost:8000/ws"
        async with websockets.connect(uri, timeout=5) as websocket:
            connection_time = (time.time() - start_time) * 1000
            results["connection_status"] = "connected"
            results["response_time_ms"] = round(connection_time, 2)
            
            # Send test message
            test_message = {"type": "ping", "timestamp": time.time()}
            await websocket.send(json.dumps(test_message))
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            response_data = json.loads(response)
            
            print(f"✅ WebSocket connected in {connection_time:.2f}ms")
            print(f"✅ Received response: {response_data}")
            
    except asyncio.TimeoutError:
        results["connection_status"] = "timeout"
        results["error"] = "Connection timeout"
        print("⚠️  WebSocket connection timeout")
    except ConnectionRefusedError:
        results["connection_status"] = "refused"
        results["error"] = "Connection refused - WebSocket server not available"
        print("❌ WebSocket connection refused - server not available")
    except Exception as e:
        results["connection_status"] = "error"
        results["error"] = str(e)
        print(f"❌ WebSocket error: {str(e)}")
    
    return results

async def main():
    print("🔌 Testing WebSocket Connections...")
    print("=" * 40)
    
    results = await test_websocket_connection()
    
    print(f"\nResults: {json.dumps(results, indent=2)}")
    
    # Save results
    with open("/home/rigade/Testing/ai-model-validation-platform/tests/websocket_test_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())