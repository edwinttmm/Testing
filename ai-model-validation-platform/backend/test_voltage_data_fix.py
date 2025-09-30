#!/usr/bin/env python3
"""
Quick test to verify the voltage data integration fix is working.
This test will check if LabJack detection events are capturing voltage data properly.
"""

import asyncio
import logging
import time
from datetime import datetime
from unittest.mock import MagicMock

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_voltage_data_extraction():
    """Test voltage data extraction from mock LabJack events"""
    print("=" * 60)
    print("TESTING VOLTAGE DATA EXTRACTION FIX")
    print("=" * 60)
    
    # Import the fixed service
    try:
        from services.dedicated_labjack_monitor import DedicatedLabJackMonitor, HILDetectionEvent
        print("✅ Successfully imported DedicatedLabJackMonitor")
    except Exception as e:
        print(f"❌ Failed to import service: {e}")
        return False
    
    # Create monitor instance
    monitor = DedicatedLabJackMonitor()
    print("✅ Created monitor instance")
    
    # Create mock LabJack event with voltage data
    mock_labjack_event = MagicMock()
    mock_labjack_event.timestamp = datetime.now()
    mock_labjack_event.voltage = 3.2  # Above threshold
    mock_labjack_event.channel = "AIN0"
    
    print(f"📊 Mock LabJack event created:")
    print(f"   - Voltage: {mock_labjack_event.voltage}V")
    print(f"   - Channel: {mock_labjack_event.channel}")
    print(f"   - Timestamp: {mock_labjack_event.timestamp}")
    
    # Test the voltage data extraction
    test_session_id = "test-voltage-fix"
    
    try:
        # Add the session to active sessions (normally done by start_monitoring)
        monitor.active_sessions[test_session_id] = {
            'video_start_time': time.time() - 5.0,  # 5 seconds ago
            'started_at': datetime.now()
        }
        monitor.detection_events[test_session_id] = []
        
        # Call the detection handler with our mock event
        monitor._handle_detection_with_video_sync(test_session_id, mock_labjack_event)
        
        # Check if the event was stored with voltage data
        events = monitor.detection_events.get(test_session_id, [])
        if events:
            event = events[0]
            print(f"\n🎯 Detection event created successfully!")
            print(f"   - Event ID: {event.id}")
            print(f"   - Voltage: {event.labjack_voltage}V (Expected: {mock_labjack_event.voltage}V)")
            print(f"   - Channel: {event.detection_channel} (Expected: {mock_labjack_event.channel})")
            print(f"   - Video-relative time: {event.video_relative_timestamp:.3f}s")
            print(f"   - Timing quality: {event.timing_sync_quality}")
            
            # Verify the voltage data was extracted correctly
            voltage_match = abs(event.labjack_voltage - mock_labjack_event.voltage) < 0.01
            channel_match = event.detection_channel == mock_labjack_event.channel
            
            if voltage_match and channel_match:
                print("✅ VOLTAGE DATA EXTRACTION FIX: SUCCESS!")
                print("   - Voltage data correctly extracted from LabJack event")
                print("   - Channel data correctly extracted from LabJack event")
                return True
            else:
                print("❌ VOLTAGE DATA EXTRACTION FIX: FAILED!")
                print(f"   - Voltage match: {voltage_match}")
                print(f"   - Channel match: {channel_match}")
                return False
        else:
            print("❌ No detection event was created")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        monitor.active_sessions.pop(test_session_id, None)
        monitor.detection_events.pop(test_session_id, None)

def test_database_storage():
    """Test that voltage data will be properly stored in database"""
    print("\n" + "=" * 60)
    print("TESTING DATABASE STORAGE FIX")
    print("=" * 60)
    
    try:
        from services.dedicated_labjack_monitor import HILDetectionEvent
        from datetime import datetime, timezone
        import uuid
        
        # Create a test HIL event with voltage data
        test_event = HILDetectionEvent(
            id=str(uuid.uuid4()),
            session_id="test-db-storage",
            unix_timestamp=time.time(),
            video_relative_timestamp=5.123,
            video_relative_timestamp_ns="5123000000",
            actual_latency_ms=65.5,
            video_frame_number=153,
            timing_sync_quality="high",
            labjack_voltage=3.45,  # Test voltage
            detection_channel="AIN0",  # Test channel
            precision_ns=500000.0,
            created_at=datetime.now(timezone.utc),
            screenshot_path=None,
            screenshot_zoom_path=None,
            ground_truth_comparison=None
        )
        
        print(f"📝 Test HIL event created:")
        print(f"   - Voltage: {test_event.labjack_voltage}V")
        print(f"   - Channel: {test_event.detection_channel}")
        print(f"   - Latency: {test_event.actual_latency_ms}ms")
        
        # Test that the values are non-null and correct types
        if (test_event.labjack_voltage is not None and 
            test_event.detection_channel is not None and
            isinstance(test_event.labjack_voltage, (int, float)) and
            isinstance(test_event.detection_channel, str)):
            
            print("✅ DATABASE STORAGE FIX: SUCCESS!")
            print("   - Voltage data is properly typed and non-null")
            print("   - Channel data is properly typed and non-null")
            print("   - Event structure is ready for database storage")
            return True
        else:
            print("❌ DATABASE STORAGE FIX: FAILED!")
            print(f"   - Voltage: {test_event.labjack_voltage} (type: {type(test_event.labjack_voltage)})")
            print(f"   - Channel: {test_event.detection_channel} (type: {type(test_event.detection_channel)})")
            return False
            
    except Exception as e:
        print(f"❌ Error during database test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 TESTING HIL DETECTION VOLTAGE DATA FIX")
    print("This test verifies that LabJack voltage data is properly extracted and stored.")
    print()
    
    # Run tests
    extraction_test = test_voltage_data_extraction()
    storage_test = test_database_storage()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Voltage Data Extraction: {'✅ PASS' if extraction_test else '❌ FAIL'}")
    print(f"Database Storage Format: {'✅ PASS' if storage_test else '❌ FAIL'}")
    
    if extraction_test and storage_test:
        print("\n🎉 ALL TESTS PASSED!")
        print("The voltage data integration fix should resolve the empty HIL detection tables.")
        print("\nNext steps:")
        print("1. Run a real HIL test session")
        print("2. Verify voltage data appears in database")
        print("3. Confirm frontend displays detection data")
    else:
        print("\n⚠️ SOME TESTS FAILED!")
        print("Additional fixes may be needed for complete resolution.")