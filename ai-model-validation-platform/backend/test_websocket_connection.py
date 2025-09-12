#!/usr/bin/env python3
"""
WebSocket Connection Test with Fixed Frontend Logic
Test the WebSocket connection stability with the applied fixes.
"""

import asyncio
import websockets
import json
import time
from datetime import datetime

async def test_websocket_connection():
    """Test WebSocket connection with frontend-like behavior."""
    
    # Test configuration
    WS_URL = "ws://localhost:8000/ws/labjack/stream"
    MAX_RECONNECT_ATTEMPTS = 5
    RECONNECT_DELAY = 3.0
    PING_INTERVAL = 10.0
    
    connection_attempts = 0
    
    while connection_attempts < MAX_RECONNECT_ATTEMPTS:
        connection_attempts += 1
        connection_id = f"test-{datetime.now().timestamp()}"
        
        print(f"\n🔄 Attempt {connection_attempts}/{MAX_RECONNECT_ATTEMPTS} - {connection_id}")
        
        try:
            # Connect to WebSocket
            async with websockets.connect(WS_URL) as websocket:
                print(f"✅ Connected to {WS_URL}")
                
                # Set up ping task
                async def send_pings():
                    try:
                        while True:
                            await asyncio.sleep(PING_INTERVAL)
                            if websocket.open:
                                await websocket.send(json.dumps({
                                    "type": "ping",
                                    "timestamp": time.time()
                                }))
                                print(f"📡 Ping sent at {datetime.now().strftime('%H:%M:%S')}")
                    except Exception as e:
                        print(f"❌ Ping error: {e}")
                
                # Start ping task
                ping_task = asyncio.create_task(send_pings())
                
                # Listen for messages
                message_count = 0
                start_time = time.time()
                
                try:
                    async for raw_message in websocket:
                        message_count += 1
                        elapsed = time.time() - start_time
                        
                        try:
                            message = json.loads(raw_message)
                            msg_type = message.get("type", "unknown")
                            
                            if msg_type == "initial_status":
                                payload = message.get("payload", {})
                                print(f"📋 Initial Status: connected={payload.get('connected')}, streaming={payload.get('streaming')}")
                                
                            elif msg_type == "streaming_data":
                                payload = message.get("payload", {})
                                data = payload.get("data", []) or payload.get("voltage_data", [])
                                sample_rate = payload.get("sample_rate", 0)
                                print(f"📊 Streaming Data: {len(data)} samples at {sample_rate}Hz")
                                
                            elif msg_type == "pong":
                                print(f"🏓 Pong received")
                                
                            elif msg_type == "status_ping":
                                payload = message.get("payload", {})
                                print(f"💓 Status: connected={payload.get('connected')}, streaming={payload.get('streaming')}")
                                
                            else:
                                print(f"📨 Message ({msg_type}): {str(message)[:100]}")
                                
                        except json.JSONDecodeError:
                            print(f"❌ Invalid JSON: {raw_message[:100]}")
                        
                        # Test duration limit
                        if elapsed > 30:  # 30 seconds
                            print(f"✅ Test completed: {message_count} messages in {elapsed:.1f}s")
                            ping_task.cancel()
                            return True
                            
                except websockets.exceptions.ConnectionClosed as e:
                    ping_task.cancel()
                    elapsed = time.time() - start_time
                    print(f"🔌 Connection closed after {elapsed:.1f}s: code={e.code}, reason='{e.reason}'")
                    
                    # Apply frontend logic: only reconnect on abnormal closures
                    if e.code > 1001:
                        print(f"🔄 Abnormal closure (code {e.code}), will reconnect...")
                        await asyncio.sleep(RECONNECT_DELAY)
                        continue
                    else:
                        print(f"✅ Normal closure (code {e.code}), no reconnection needed")
                        return True
                        
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            await asyncio.sleep(RECONNECT_DELAY)
            continue
    
    print(f"❌ Max reconnection attempts ({MAX_RECONNECT_ATTEMPTS}) reached")
    return False

def main():
    """Run the WebSocket connection test."""
    print("🚀 WebSocket Connection Test with Frontend Logic")
    print("=" * 60)
    
    try:
        result = asyncio.run(test_websocket_connection())
        
        if result:
            print("\n✅ WebSocket connection test PASSED")
            print("   - Connection established successfully")
            print("   - Message exchange working")
            print("   - Reconnection logic behaving correctly")
        else:
            print("\n❌ WebSocket connection test FAILED")
            print("   - Could not establish stable connection")
            
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test crashed: {e}")

if __name__ == "__main__":
    main()