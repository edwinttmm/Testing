"""
LabJack Timing API Integration Examples

This module demonstrates how to integrate with the LabJack timing validation API
for comprehensive timing validation workflows.

Usage Examples:
1. Basic timing session workflow
2. Real-time WebSocket monitoring  
3. Advanced latency analysis
4. Error handling patterns
"""

import asyncio
import aiohttp
import websockets
import json
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TimingSession:
    """Timing session configuration"""
    session_id: str
    video_id: str
    latency_threshold_ms: float
    voltage_threshold: float
    detection_channels: List[int]
    api_base_url: str

class LabJackTimingClient:
    """Client for LabJack timing validation API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def start_timing_session(self, session_config: TimingSession) -> Dict[str, Any]:
        """Start a new timing validation session"""
        url = f"{self.base_url}/api/test-sessions/{session_config.session_id}/start-timing"
        
        payload = {
            "video_id": session_config.video_id,
            "latency_threshold_ms": session_config.latency_threshold_ms,
            "voltage_threshold": session_config.voltage_threshold,
            "detection_channels": session_config.detection_channels,
            "sampling_rate_hz": 1000.0,
            "metadata": {
                "test_type": "timing_validation",
                "created_by": "integration_example"
            }
        }
        
        async with self.session.post(url, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                logger.info(f"Started timing session {session_config.session_id}")
                return result
            else:
                error_text = await response.text()
                raise Exception(f"Failed to start session: {response.status} - {error_text}")
    
    async def send_detection_event(self, session_id: str, timestamp: float, 
                                 voltage: float, channel: int) -> Dict[str, Any]:
        """Send a detection event to the API"""
        url = f"{self.base_url}/api/labjack/detection-event"
        
        payload = {
            "session_id": session_id,
            "timestamp": timestamp,
            "voltage": voltage,
            "channel": channel,
            "pin_state": voltage > 2.5,  # Simple digital logic
            "metadata": {
                "source": "integration_example",
                "raw_data": {"voltage": voltage, "channel": channel}
            }
        }
        
        async with self.session.post(url, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                logger.info(f"Detection event processed: {result['validation_result']} "
                          f"(latency: {result['latency_ms']:.2f}ms)")
                return result
            else:
                error_text = await response.text()
                raise Exception(f"Failed to send detection event: {response.status} - {error_text}")
    
    async def get_latency_results(self, session_id: str) -> Dict[str, Any]:
        """Get current latency results for session"""
        url = f"{self.base_url}/api/test-sessions/{session_id}/latency-results"
        
        async with self.session.get(url) as response:
            if response.status == 200:
                result = await response.json()
                logger.info(f"Session {session_id} results: {result['pass_rate']:.1f}% pass rate, "
                          f"avg latency: {result['average_latency_ms']:.2f}ms")
                return result
            else:
                error_text = await response.text()
                raise Exception(f"Failed to get results: {response.status} - {error_text}")
    
    async def stop_timing_session(self, session_id: str) -> Dict[str, Any]:
        """Stop timing session and get final results"""
        url = f"{self.base_url}/api/test-sessions/{session_id}/stop-timing"
        
        async with self.session.post(url) as response:
            if response.status == 200:
                result = await response.json()
                logger.info(f"Stopped timing session {session_id} after "
                          f"{result['session_duration_ms']:.0f}ms")
                return result
            else:
                error_text = await response.text()
                raise Exception(f"Failed to stop session: {response.status} - {error_text}")
    
    async def get_detection_events(self, session_id: str, limit: int = 100) -> Dict[str, Any]:
        """Get detection events for detailed analysis"""
        url = f"{self.base_url}/api/test-sessions/{session_id}/detection-events"
        params = {"limit": limit}
        
        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                result = await response.json()
                logger.info(f"Retrieved {len(result['events'])} detection events for session {session_id}")
                return result
            else:
                error_text = await response.text()
                raise Exception(f"Failed to get events: {response.status} - {error_text}")

class WebSocketMonitor:
    """Real-time WebSocket monitoring for timing sessions"""
    
    def __init__(self, base_url: str = "ws://localhost:8000"):
        self.base_url = base_url
        self.callbacks = {
            'detection_event': [],
            'latency_calculated': [],
            'session_completed': []
        }
        
    def on_detection_event(self, callback):
        """Register callback for detection events"""
        self.callbacks['detection_event'].append(callback)
        
    def on_latency_calculated(self, callback):
        """Register callback for latency calculations"""
        self.callbacks['latency_calculated'].append(callback)
        
    def on_session_completed(self, callback):
        """Register callback for session completion"""
        self.callbacks['session_completed'].append(callback)
        
    async def monitor_session(self, session_id: str):
        """Start monitoring a timing session via WebSocket"""
        uri = f"{self.base_url}/api/test-sessions/{session_id}/ws"
        
        try:
            async with websockets.connect(uri) as websocket:
                logger.info(f"Started monitoring session {session_id}")
                
                # Send periodic ping to keep connection alive
                ping_task = asyncio.create_task(self._send_ping(websocket))
                
                try:
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            await self._handle_message(data)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON received: {message}")
                except websockets.exceptions.ConnectionClosed:
                    logger.info(f"WebSocket connection closed for session {session_id}")
                finally:
                    ping_task.cancel()
                    
        except Exception as e:
            logger.error(f"WebSocket monitoring error: {e}")
            
    async def _send_ping(self, websocket):
        """Send periodic ping messages"""
        while True:
            try:
                await asyncio.sleep(30)  # Ping every 30 seconds
                await websocket.send("ping")
            except:
                break
                
    async def _handle_message(self, data: Dict[str, Any]):
        """Handle incoming WebSocket messages"""
        event_type = data.get('event')
        event_data = data.get('data', {})
        
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    await callback(event_data)
                except Exception as e:
                    logger.error(f"Callback error for {event_type}: {e}")

# Example usage functions

async def basic_timing_workflow():
    """Example: Basic timing validation workflow"""
    print("\\n=== Basic Timing Validation Workflow ===")
    
    session_config = TimingSession(
        session_id="example_session_001",
        video_id="test_video_1",
        latency_threshold_ms=50.0,
        voltage_threshold=3.0,
        detection_channels=[0, 1],
        api_base_url="http://localhost:8000"
    )
    
    async with LabJackTimingClient() as client:
        try:
            # 1. Start timing session
            start_result = await client.start_timing_session(session_config)
            print(f"Session started: {start_result['message']}")
            
            # 2. Simulate detection events
            video_start_time = start_result['video_start_timestamp']
            
            # Simulate some detection events with varying latencies
            detection_events = [
                (video_start_time + 0.025, 3.2, 0),  # 25ms latency - PASS
                (video_start_time + 0.045, 3.5, 1),  # 45ms latency - PASS  
                (video_start_time + 0.075, 3.1, 0),  # 75ms latency - FAIL
                (video_start_time + 0.030, 3.4, 1),  # 30ms latency - PASS
            ]
            
            for timestamp, voltage, channel in detection_events:
                await asyncio.sleep(0.1)  # Small delay between events
                event_result = await client.send_detection_event(
                    session_config.session_id, timestamp, voltage, channel
                )
                print(f"Event {event_result['event_id']}: {event_result['validation_result']} "
                      f"({event_result['latency_ms']:.1f}ms)")
            
            # 3. Get intermediate results
            results = await client.get_latency_results(session_config.session_id)
            print(f"\\nIntermediate results:")
            print(f"  Pass rate: {results['pass_rate']:.1f}%")
            print(f"  Average latency: {results['average_latency_ms']:.2f}ms")
            print(f"  Events: {results['pass_count']} pass, {results['fail_count']} fail")
            
            # 4. Stop session and get final results
            await asyncio.sleep(1)  # Wait a bit before stopping
            stop_result = await client.stop_timing_session(session_config.session_id)
            print(f"\\nSession stopped: {stop_result['message']}")
            print(f"Duration: {stop_result['session_duration_ms']:.0f}ms")
            
            final_results = stop_result['final_results']
            print(f"\\nFinal Results:")
            print(f"  Total events: {final_results['total_events']}")
            print(f"  Pass rate: {final_results['pass_rate']:.1f}%")
            print(f"  Average latency: {final_results['average_latency_ms']:.2f}ms")
            print(f"  Latency distribution: {final_results['latency_distribution']}")
            
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            print(f"Error: {e}")

async def websocket_monitoring_example():
    """Example: Real-time WebSocket monitoring"""
    print("\\n=== Real-time WebSocket Monitoring ===")
    
    session_id = "websocket_session_001"
    monitor = WebSocketMonitor()
    
    # Set up event handlers
    async def on_detection(data):
        print(f"🔍 Detection Event: Channel {data['channel']}, "
              f"Result: {data['validation_result']}")
    
    async def on_latency(data): 
        print(f"⏱️  Latency: {data['latency_ms']:.2f}ms, "
              f"Pass Rate: {data['pass_rate']:.1f}%")
    
    async def on_completion(data):
        print(f"✅ Session Complete: {data['total_events']} events, "
              f"{data['pass_rate']:.1f}% pass rate")
    
    monitor.on_detection_event(on_detection)
    monitor.on_latency_calculated(on_latency)
    monitor.on_session_completed(on_completion)
    
    # Start monitoring (this would run alongside your main application)
    print("Starting WebSocket monitoring... (Press Ctrl+C to stop)")
    try:
        await monitor.monitor_session(session_id)
    except KeyboardInterrupt:
        print("\\nMonitoring stopped by user")

async def advanced_analysis_example():
    """Example: Advanced latency analysis"""
    print("\\n=== Advanced Latency Analysis ===")
    
    session_id = "analysis_session_001"
    
    async with LabJackTimingClient() as client:
        try:
            # Get detailed detection events
            events_result = await client.get_detection_events(session_id, limit=1000)
            events = events_result['events']
            
            if not events:
                print("No events found for analysis")
                return
            
            # Analyze latency patterns
            latencies = [e['latency_ms'] for e in events if e['latency_ms'] is not None]
            
            if latencies:
                print(f"Latency Analysis for {len(events)} events:")
                print(f"  Min latency: {min(latencies):.2f}ms")
                print(f"  Max latency: {max(latencies):.2f}ms")
                print(f"  Average latency: {sum(latencies)/len(latencies):.2f}ms")
                print(f"  Median latency: {sorted(latencies)[len(latencies)//2]:.2f}ms")
                
                # Performance analysis
                fast_events = [l for l in latencies if l <= 25]
                medium_events = [l for l in latencies if 25 < l <= 100]
                slow_events = [l for l in latencies if l > 100]
                
                print(f"\\nPerformance Categories:")
                print(f"  Fast (≤25ms): {len(fast_events)} events ({len(fast_events)/len(latencies)*100:.1f}%)")
                print(f"  Medium (25-100ms): {len(medium_events)} events ({len(medium_events)/len(latencies)*100:.1f}%)")
                print(f"  Slow (>100ms): {len(slow_events)} events ({len(slow_events)/len(latencies)*100:.1f}%)")
                
                # Channel analysis
                channel_data = {}
                for event in events:
                    channel = event['channel']
                    if channel not in channel_data:
                        channel_data[channel] = []
                    if event['latency_ms']:
                        channel_data[channel].append(event['latency_ms'])
                
                print(f"\\nPer-Channel Analysis:")
                for channel, ch_latencies in channel_data.items():
                    if ch_latencies:
                        avg_latency = sum(ch_latencies) / len(ch_latencies)
                        print(f"  Channel {channel}: {len(ch_latencies)} events, "
                              f"avg: {avg_latency:.2f}ms")
                
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            print(f"Error: {e}")

async def error_handling_example():
    """Example: Comprehensive error handling"""
    print("\\n=== Error Handling Examples ===")
    
    async with LabJackTimingClient() as client:
        # Example 1: Invalid session ID
        try:
            await client.get_latency_results("nonexistent_session")
        except Exception as e:
            print(f"✅ Handled invalid session error: {e}")
        
        # Example 2: Invalid detection event
        try:
            await client.send_detection_event("invalid_session", time.time(), -1.0, 99)
        except Exception as e:
            print(f"✅ Handled invalid detection event: {e}")
        
        # Example 3: Service unavailable scenarios
        print("\\n⚠️  Note: In production, implement retry logic and circuit breakers")
        print("for handling temporary service unavailability.")

# Health check utility
async def check_api_health():
    """Check API health status"""
    print("\\n=== API Health Check ===")
    
    async with LabJackTimingClient() as client:
        try:
            url = f"{client.base_url}/api/labjack-timing/health"
            async with client.session.get(url) as response:
                if response.status == 200:
                    health = await response.json()
                    print(f"✅ API Status: {health['status']}")
                    print(f"   Active sessions: {health['active_sessions']}")
                    print(f"   Services available: {health['services']}")
                    print(f"   API version: {health['api_version']}")
                else:
                    print(f"❌ API unhealthy: {response.status}")
        except Exception as e:
            print(f"❌ API health check failed: {e}")

# Main example runner
async def main():
    """Run all examples"""
    print("LabJack Timing API Integration Examples")
    print("=" * 50)
    
    # Check API health first
    await check_api_health()
    
    # Run examples
    await basic_timing_workflow()
    
    # Note: WebSocket and analysis examples require active sessions
    print("\\n📝 Note: WebSocket monitoring and analysis examples require")
    print("   active sessions. Run them separately with real data.")
    
    await error_handling_example()
    
    print("\\n✅ All examples completed!")

if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())