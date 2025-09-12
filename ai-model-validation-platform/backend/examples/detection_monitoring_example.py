"""
LabJack Detection Monitoring Usage Examples

This file demonstrates how to use the LabJack Detection Monitoring Service
for event-based detection and latency analysis.

Examples:
1. Basic detection monitoring setup
2. Custom threshold and debounce configuration
3. Event retrieval and analysis
4. WebSocket integration for real-time notifications
5. Latency calculation from detection events
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Import detection monitoring services
from services.labjack_detection_service import (
    get_detection_monitor,
    DetectionEvent,
    DetectionConfig,
    setup_websocket_integration
)

# Import LabJack service
from services.labjack_service import get_labjack_service, initialize_labjack_service


async def basic_detection_example():
    """
    Example 1: Basic Detection Monitoring
    
    Demonstrates basic setup of detection monitoring with default settings.
    """
    print("🔍 Example 1: Basic Detection Monitoring")
    print("=" * 50)
    
    # Initialize LabJack service
    print("Initializing LabJack service...")
    labjack_connected = await initialize_labjack_service()
    if not labjack_connected:
        print("❌ LabJack not connected. Using mock mode for demonstration.")
    else:
        print("✅ LabJack connected successfully")
    
    # Get detection monitor
    monitor = get_detection_monitor()
    
    # Start monitoring with default settings
    session_id = f"basic_example_{int(time.time())}"
    success = monitor.start_monitoring(
        session_id=session_id,
        channels=["AIN0", "AIN1"],
        voltage_threshold=2.5,  # 2.5V threshold
        debounce_ms=100         # 100ms debounce
    )
    
    if success:
        print(f"✅ Started monitoring session: {session_id}")
        print("   - Channels: AIN0, AIN1")
        print("   - Threshold: 2.5V")
        print("   - Debounce: 100ms")
    else:
        print("❌ Failed to start monitoring")
        return
    
    # Monitor for 10 seconds
    print("\n⏳ Monitoring for 10 seconds...")
    await asyncio.sleep(10)
    
    # Get detection events
    events = monitor.get_detection_events(session_id)
    print(f"\n📊 Detection Results:")
    print(f"   - Total events: {len(events)}")
    
    for i, event in enumerate(events[:3]):  # Show first 3 events
        print(f"   - Event {i+1}: {event['channel']} = {event['voltage']:.3f}V @ {event['timestamp']}")
    
    if len(events) > 3:
        print(f"   - ... and {len(events) - 3} more events")
    
    # Stop monitoring
    monitor.stop_monitoring(session_id)
    print(f"\n⏹️ Stopped monitoring session: {session_id}")
    
    return events


async def advanced_detection_example():
    """
    Example 2: Advanced Detection Configuration
    
    Demonstrates custom threshold, debounce, and high-speed monitoring.
    """
    print("\n🎯 Example 2: Advanced Detection Configuration")
    print("=" * 50)
    
    monitor = get_detection_monitor()
    
    # Advanced configuration for sensitive detection
    session_id = f"advanced_example_{int(time.time())}"
    success = monitor.start_monitoring(
        session_id=session_id,
        channels=["AIN0"],           # Single channel
        voltage_threshold=1.0,       # Lower threshold for sensitivity
        debounce_ms=50,             # Faster response
        sample_rate=2000,           # Higher sample rate
        metadata={
            "experiment_type": "high_sensitivity",
            "operator": "test_user",
            "setup_notes": "Low threshold detection test"
        }
    )
    
    if success:
        print(f"✅ Started advanced monitoring: {session_id}")
        print("   - Channel: AIN0 only")
        print("   - Threshold: 1.0V (sensitive)")
        print("   - Debounce: 50ms (fast)")
        print("   - Sample rate: 2000Hz")
    
    # Monitor for 5 seconds
    print("\n⏳ High-speed monitoring for 5 seconds...")
    await asyncio.sleep(5)
    
    # Get session status
    status = monitor.get_session_status(session_id)
    print(f"\n📈 Session Status:")
    print(f"   - Status: {status['status']}")
    print(f"   - Active: {status['active']}")
    print(f"   - Events: {status['event_count']}")
    
    # Stop monitoring
    monitor.stop_monitoring(session_id)
    
    return monitor.get_detection_events(session_id)


async def latency_analysis_example(events: List[Dict[str, Any]]):
    """
    Example 3: Latency Analysis
    
    Demonstrates how to analyze detection events for latency calculation.
    """
    print("\n📊 Example 3: Latency Analysis")
    print("=" * 50)
    
    if not events:
        print("❌ No events available for analysis")
        return
    
    print(f"Analyzing {len(events)} detection events...")
    
    # Group events by channel
    channel_events = {}
    for event in events:
        channel = event['channel']
        if channel not in channel_events:
            channel_events[channel] = []
        channel_events[channel].append(event)
    
    # Analyze each channel
    for channel, ch_events in channel_events.items():
        print(f"\n📡 Channel {channel} Analysis:")
        print(f"   - Total events: {len(ch_events)}")
        
        if len(ch_events) < 2:
            print("   - Need at least 2 events for latency analysis")
            continue
        
        # Calculate time intervals between events
        timestamps = [datetime.fromisoformat(e['timestamp']) for e in ch_events]
        intervals = []
        
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i-1]).total_seconds() * 1000  # ms
            intervals.append(interval)
        
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            min_interval = min(intervals)
            max_interval = max(intervals)
            
            print(f"   - Average interval: {avg_interval:.1f}ms")
            print(f"   - Min interval: {min_interval:.1f}ms")
            print(f"   - Max interval: {max_interval:.1f}ms")
        
        # Voltage statistics
        voltages = [e['voltage'] for e in ch_events]
        avg_voltage = sum(voltages) / len(voltages)
        min_voltage = min(voltages)
        max_voltage = max(voltages)
        
        print(f"   - Average voltage: {avg_voltage:.3f}V")
        print(f"   - Min voltage: {min_voltage:.3f}V") 
        print(f"   - Max voltage: {max_voltage:.3f}V")


async def websocket_integration_example():
    """
    Example 4: WebSocket Integration
    
    Demonstrates real-time WebSocket notifications for detection events.
    """
    print("\n🔌 Example 4: WebSocket Integration")
    print("=" * 50)
    
    monitor = get_detection_monitor()
    
    # Mock WebSocket manager for demonstration
    class MockWebSocketManager:
        def __init__(self):
            self.messages = []
        
        async def broadcast_to_session(self, session_id: str, message: Dict[str, Any]):
            self.messages.append({
                'session_id': session_id,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
            print(f"📡 WebSocket message: {message['type']} for session {session_id}")
    
    # Setup WebSocket integration
    websocket_manager = MockWebSocketManager()
    
    async def websocket_callback(session_id: str, message: Dict[str, Any]):
        await websocket_manager.broadcast_to_session(session_id, message)
    
    monitor.add_websocket_callback(websocket_callback)
    print("✅ WebSocket integration configured")
    
    # Start monitoring with WebSocket enabled
    session_id = f"websocket_example_{int(time.time())}"
    monitor.start_monitoring(
        session_id=session_id,
        channels=["AIN0"],
        voltage_threshold=2.0,
        enable_websocket=True
    )
    
    print(f"✅ Started monitoring with WebSocket: {session_id}")
    print("⏳ Monitoring for WebSocket messages...")
    
    # Monitor for a short time
    await asyncio.sleep(3)
    
    # Stop monitoring
    monitor.stop_monitoring(session_id)
    
    print(f"\n📱 WebSocket Messages Received: {len(websocket_manager.messages)}")
    for msg in websocket_manager.messages[:3]:  # Show first 3
        print(f"   - {msg['message']['type']} @ {msg['timestamp']}")


async def multiple_sessions_example():
    """
    Example 5: Multiple Monitoring Sessions
    
    Demonstrates managing multiple concurrent monitoring sessions.
    """
    print("\n🔢 Example 5: Multiple Monitoring Sessions")
    print("=" * 50)
    
    monitor = get_detection_monitor()
    
    # Start multiple sessions with different configurations
    sessions = [
        {
            'id': f"session_1_{int(time.time())}",
            'channels': ['AIN0'],
            'threshold': 2.5,
            'debounce': 100
        },
        {
            'id': f"session_2_{int(time.time())}",
            'channels': ['AIN1'],
            'threshold': 1.5,
            'debounce': 150
        },
        {
            'id': f"session_3_{int(time.time())}",
            'channels': ['AIN0', 'AIN1'],
            'threshold': 3.0,
            'debounce': 75
        }
    ]
    
    # Start all sessions
    for session in sessions:
        success = monitor.start_monitoring(
            session_id=session['id'],
            channels=session['channels'],
            voltage_threshold=session['threshold'],
            debounce_ms=session['debounce']
        )
        if success:
            print(f"✅ Started session: {session['id']}")
        else:
            print(f"❌ Failed to start session: {session['id']}")
    
    # Get all sessions status
    all_sessions = monitor.get_all_sessions()
    print(f"\n📊 Active Sessions: {len(all_sessions)}")
    
    for session_status in all_sessions:
        print(f"   - {session_status['session_id']}: {session_status['status']} ({session_status['event_count']} events)")
    
    # Monitor for a short time
    print("\n⏳ All sessions monitoring for 3 seconds...")
    await asyncio.sleep(3)
    
    # Stop all sessions
    for session in sessions:
        monitor.stop_monitoring(session['id'])
        print(f"⏹️ Stopped session: {session['id']}")
    
    # Get final statistics
    stats = monitor.get_statistics()
    print(f"\n📈 Final Statistics:")
    print(f"   - Total events across all sessions: {stats['total_events']}")
    print(f"   - Active sessions: {stats['active_sessions']}")


async def detection_callback_example():
    """
    Example 6: Detection Event Callbacks
    
    Demonstrates custom callbacks for real-time event processing.
    """
    print("\n🔔 Example 6: Detection Event Callbacks")
    print("=" * 50)
    
    monitor = get_detection_monitor()
    
    # Custom detection callback
    detected_events = []
    
    def detection_callback(event: DetectionEvent):
        """Custom callback for processing detection events"""
        detected_events.append(event)
        print(f"🎯 Callback triggered: {event.channel} = {event.voltage:.3f}V @ {event.timestamp.strftime('%H:%M:%S.%f')[:-3]}")
        
        # Example: Trigger action if voltage is very high
        if event.voltage > 5.0:
            print(f"   ⚠️ HIGH VOLTAGE ALERT: {event.voltage:.3f}V on {event.channel}")
    
    # Add callback
    monitor.add_detection_callback(detection_callback)
    print("✅ Detection callback registered")
    
    # Start monitoring
    session_id = f"callback_example_{int(time.time())}"
    monitor.start_monitoring(
        session_id=session_id,
        channels=["AIN0"],
        voltage_threshold=1.0,  # Low threshold to trigger more events
        debounce_ms=50
    )
    
    print(f"✅ Started monitoring with callback: {session_id}")
    print("⏳ Monitoring for callback events...")
    
    # Monitor for events
    await asyncio.sleep(5)
    
    # Stop monitoring
    monitor.stop_monitoring(session_id)
    
    print(f"\n📊 Callback Results:")
    print(f"   - Events processed by callback: {len(detected_events)}")
    print(f"   - Total events in session: {len(monitor.get_detection_events(session_id))}")


async def run_all_examples():
    """Run all detection monitoring examples"""
    print("🚀 LabJack Detection Monitoring Examples")
    print("=" * 60)
    
    try:
        # Example 1: Basic detection
        events1 = await basic_detection_example()
        
        # Example 2: Advanced configuration
        events2 = await advanced_detection_example()
        
        # Example 3: Latency analysis
        all_events = events1 + events2
        await latency_analysis_example(all_events)
        
        # Example 4: WebSocket integration
        await websocket_integration_example()
        
        # Example 5: Multiple sessions
        await multiple_sessions_example()
        
        # Example 6: Detection callbacks
        await detection_callback_example()
        
        print("\n✅ All examples completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    """Run examples when script is executed directly"""
    asyncio.run(run_all_examples())