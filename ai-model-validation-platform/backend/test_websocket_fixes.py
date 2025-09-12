#!/usr/bin/env python3
"""
WebSocket Connection Fix Testing Suite
Tests the improved WebSocket implementation for timing and connection reliability
"""

import asyncio
import json
import websockets
import time
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketConnectionTester:
    """Test suite for WebSocket connection reliability"""
    
    def __init__(self, ws_url="ws://localhost:8000/ws/labjack/stream"):
        self.ws_url = ws_url
        self.test_results = []
        
    async def test_single_connection(self, test_name="Basic Connection"):
        """Test a single WebSocket connection"""
        start_time = time.time()
        connection_established = False
        first_message_time = None
        
        try:
            logger.info(f"Starting {test_name}")
            
            # Connect with timeout  
            async with websockets.connect(self.ws_url) as websocket:
                connect_time = (time.time() - start_time) * 1000
                logger.info(f"Connection established in {connect_time:.2f}ms")
                
                # Wait for first message
                message_start = time.time()
                try:
                    first_message = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    first_message_time = (time.time() - message_start) * 1000
                    
                    data = json.loads(first_message)
                    logger.info(f"First message received in {first_message_time:.2f}ms: {data.get('type')}")
                    
                    if data.get('type') == 'connection_established':
                        connection_established = True
                        logger.info(f"✅ Connection establishment confirmed: {data.get('connection_id')}")
                    
                    # Test ping-pong
                    ping_time = time.time()
                    await websocket.send(json.dumps({
                        "type": "ping", 
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }))
                    
                    pong_response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    pong_time = (time.time() - ping_time) * 1000
                    pong_data = json.loads(pong_response)
                    
                    logger.info(f"Ping-pong completed in {pong_time:.2f}ms: {pong_data.get('type')}")
                    
                    # Keep connection alive for stability test
                    await asyncio.sleep(1.0)
                    
                    test_result = {
                        "test_name": test_name,
                        "success": True,
                        "connect_time_ms": connect_time,
                        "first_message_time_ms": first_message_time,
                        "ping_pong_time_ms": pong_time,
                        "connection_established": connection_established,
                        "total_duration_ms": (time.time() - start_time) * 1000
                    }
                    
                except asyncio.TimeoutError as e:
                    logger.error(f"❌ Timeout waiting for messages: {e}")
                    test_result = {
                        "test_name": test_name,
                        "success": False,
                        "error": "Message timeout",
                        "connect_time_ms": connect_time,
                        "connection_established": connection_established
                    }
                
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            test_result = {
                "test_name": test_name,
                "success": False,
                "error": str(e),
                "connect_time_ms": (time.time() - start_time) * 1000
            }
        
        self.test_results.append(test_result)
        return test_result
    
    async def test_rapid_connections(self, num_connections=5):
        """Test multiple rapid connections to detect race conditions"""
        logger.info(f"Testing {num_connections} rapid connections...")
        
        tasks = []
        for i in range(num_connections):
            task = asyncio.create_task(
                self.test_single_connection(f"Rapid Connection {i+1}")
            )
            tasks.append(task)
            await asyncio.sleep(0.1)  # Small delay between connections
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
        logger.info(f"✅ {successful}/{num_connections} rapid connections successful")
        
        return results
    
    async def test_connection_persistence(self, duration_seconds=10):
        """Test long-running connection stability"""
        logger.info(f"Testing connection persistence for {duration_seconds} seconds...")
        
        start_time = time.time()
        messages_received = 0
        
        try:
            async with websockets.connect(self.ws_url) as websocket:
                logger.info("Long-running connection established")
                
                while time.time() - start_time < duration_seconds:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        messages_received += 1
                        
                        if messages_received % 10 == 0:
                            logger.info(f"Received {messages_received} messages...")
                            
                    except asyncio.TimeoutError:
                        # Send ping to keep connection alive
                        await websocket.send(json.dumps({
                            "type": "ping",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }))
                
                test_result = {
                    "test_name": "Connection Persistence",
                    "success": True,
                    "duration_seconds": duration_seconds,
                    "messages_received": messages_received,
                    "message_rate": messages_received / duration_seconds
                }
                
        except Exception as e:
            logger.error(f"❌ Persistence test failed: {e}")
            test_result = {
                "test_name": "Connection Persistence",
                "success": False,
                "error": str(e),
                "messages_received": messages_received,
                "duration_seconds": time.time() - start_time
            }
        
        self.test_results.append(test_result)
        return test_result
    
    def print_summary(self):
        """Print comprehensive test summary"""
        print("\n" + "="*70)
        print("🔍 WEBSOCKET CONNECTION TEST SUMMARY")
        print("="*70)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.get('success'))
        
        print(f"📊 Overall Results: {successful_tests}/{total_tests} tests passed")
        print(f"✅ Success Rate: {(successful_tests/total_tests)*100:.1f}%")
        
        # Connection timing analysis
        connect_times = [r.get('connect_time_ms', 0) for r in self.test_results 
                        if r.get('success') and r.get('connect_time_ms')]
        
        if connect_times:
            print(f"⚡ Average Connection Time: {sum(connect_times)/len(connect_times):.2f}ms")
            print(f"📈 Max Connection Time: {max(connect_times):.2f}ms")
            print(f"📉 Min Connection Time: {min(connect_times):.2f}ms")
        
        # Message timing analysis  
        message_times = [r.get('first_message_time_ms', 0) for r in self.test_results
                        if r.get('success') and r.get('first_message_time_ms')]
        
        if message_times:
            print(f"💬 Average First Message Time: {sum(message_times)/len(message_times):.2f}ms")
        
        print("\n📋 Detailed Results:")
        for result in self.test_results:
            status = "✅ PASS" if result.get('success') else "❌ FAIL"
            print(f"  {status} {result['test_name']}")
            
            if result.get('success'):
                if result.get('connect_time_ms'):
                    print(f"       Connection: {result['connect_time_ms']:.2f}ms")
                if result.get('first_message_time_ms'):
                    print(f"       First Message: {result['first_message_time_ms']:.2f}ms")
                if result.get('messages_received'):
                    print(f"       Messages: {result['messages_received']}")
            else:
                print(f"       Error: {result.get('error', 'Unknown')}")
        
        print("\n" + "="*70)
        
        # Performance assessment
        if successful_tests / total_tests >= 0.95:
            print("🎉 EXCELLENT: WebSocket connections are highly reliable!")
        elif successful_tests / total_tests >= 0.80:
            print("👍 GOOD: WebSocket connections are mostly stable")
        else:
            print("⚠️  NEEDS IMPROVEMENT: WebSocket connection reliability issues detected")
        
        print("="*70)

async def main():
    """Run comprehensive WebSocket connection tests"""
    tester = WebSocketConnectionTester()
    
    print("🚀 Starting WebSocket Connection Tests...")
    print("📝 Testing improved connection management and timing fixes")
    
    # Test 1: Basic single connection
    await tester.test_single_connection("Basic Connection Test")
    
    # Test 2: Rapid multiple connections
    await tester.test_rapid_connections(3)
    
    # Test 3: Connection persistence
    await tester.test_connection_persistence(5)
    
    # Print comprehensive summary
    tester.print_summary()

if __name__ == "__main__":
    asyncio.run(main())