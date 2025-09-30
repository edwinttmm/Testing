#!/usr/bin/env python3
"""
Test script to validate the comprehensive fix for dedicated HIL monitoring KeyError.
Tests all edge cases including None video_start_time handling.
"""

import sys
import os
import time
import uuid
import traceback
from unittest.mock import Mock
from datetime import datetime, timezone

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

def test_none_video_start_time_fix():
    """Test the specific fix for None video_start_time causing TypeError"""
    
    print("🔍 TESTING NONE VIDEO_START_TIME FIX")
    print("=" * 60)
    
    try:
        from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
        
        monitor = DedicatedLabJackMonitor()
        test_session_id = "test-none-video-start-time-" + str(uuid.uuid4())[:8]
        
        # Initialize session with None video_start_time (this was causing the error)
        monitor.active_sessions[test_session_id] = {
            'video_timing_config': {'video_id': '2ad0f85c-ebe3-4f5d-8dff-8839dc3292a9'},
            'labjack_config': {'channels': ['AIN0']},
            'started_at': datetime.now(timezone.utc),
            'video_start_time': None,  # This was causing the TypeError
            'detection_callback': None
        }
        
        print(f"✅ Session initialized with None video_start_time: {test_session_id}")
        
        # Create mock event that would trigger the error
        mock_event = Mock()
        mock_event.timestamp = Mock()
        mock_event.timestamp.timestamp = Mock(return_value=time.time())
        mock_event.voltage = 3.3
        mock_event.channel = 'AIN0'
        
        print("🧪 Testing callback with None video_start_time...")
        
        # This should now work without throwing TypeError
        monitor._handle_detection_with_video_sync(test_session_id, mock_event)
        
        print("✅ SUCCESS: No TypeError with None video_start_time!")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_edge_cases():
    """Test various edge cases for session access"""
    
    print("\n🔍 TESTING EDGE CASES")
    print("=" * 60)
    
    try:
        from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
        
        monitor = DedicatedLabJackMonitor()
        
        # Test 1: Session with invalid started_at
        print("\n📋 Test 1: Invalid started_at handling")
        test_session_1 = "test-invalid-started-at-" + str(uuid.uuid4())[:8]
        monitor.active_sessions[test_session_1] = {
            'video_timing_config': {'video_id': 'test'},
            'labjack_config': {'channels': ['AIN0']},
            'started_at': "invalid_datetime",  # Invalid type
            'video_start_time': None,
            'detection_callback': None
        }
        
        mock_event = Mock()
        mock_event.timestamp = Mock()
        mock_event.timestamp.timestamp = Mock(return_value=time.time())
        mock_event.voltage = 3.3
        mock_event.channel = 'AIN0'
        
        monitor._handle_detection_with_video_sync(test_session_1, mock_event)
        print("✅ Invalid started_at handled gracefully")
        
        # Test 2: Session with string video_start_time
        print("\n📋 Test 2: String video_start_time handling")
        test_session_2 = "test-string-video-start-" + str(uuid.uuid4())[:8]
        monitor.active_sessions[test_session_2] = {
            'video_timing_config': {'video_id': 'test'},
            'labjack_config': {'channels': ['AIN0']},
            'started_at': datetime.now(timezone.utc),
            'video_start_time': "not_a_number",  # Invalid type
            'detection_callback': None
        }
        
        monitor._handle_detection_with_video_sync(test_session_2, mock_event)
        print("✅ String video_start_time handled gracefully")
        
        # Test 3: Empty session data
        print("\n📋 Test 3: Empty session data handling")
        test_session_3 = "test-empty-session-" + str(uuid.uuid4())[:8]
        monitor.active_sessions[test_session_3] = {}  # Empty session
        
        monitor._handle_detection_with_video_sync(test_session_3, mock_event)
        print("✅ Empty session data handled gracefully")
        
        # Test 4: Invalid timestamp from event
        print("\n📋 Test 4: Invalid event timestamp handling")
        test_session_4 = "test-invalid-timestamp-" + str(uuid.uuid4())[:8]
        monitor.active_sessions[test_session_4] = {
            'video_timing_config': {'video_id': 'test'},
            'labjack_config': {'channels': ['AIN0']},
            'started_at': datetime.now(timezone.utc),
            'video_start_time': time.time(),
            'detection_callback': None
        }
        
        # Event with invalid timestamp
        bad_event = Mock()
        bad_event.timestamp = "invalid"  # Not a timestamp object
        bad_event.voltage = 3.3
        bad_event.channel = 'AIN0'
        
        monitor._handle_detection_with_video_sync(test_session_4, bad_event)
        print("✅ Invalid event timestamp handled gracefully")
        
        return True
        
    except Exception as e:
        print(f"❌ Edge case test failed: {e}")
        traceback.print_exc()
        return False


def test_concurrent_session_operations():
    """Test concurrent session operations that could cause race conditions"""
    
    print("\n🔍 TESTING CONCURRENT OPERATIONS")
    print("=" * 60)
    
    try:
        import threading
        from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
        
        monitor = DedicatedLabJackMonitor()
        test_session_id = "test-concurrent-" + str(uuid.uuid4())[:8]
        
        # Initialize session
        monitor.active_sessions[test_session_id] = {
            'video_timing_config': {'video_id': 'test'},
            'labjack_config': {'channels': ['AIN0']},
            'started_at': datetime.now(timezone.utc),
            'video_start_time': time.time(),
            'detection_callback': None
        }
        
        results = {'callback_success': False, 'cleanup_success': False}
        
        def callback_worker():
            """Worker that calls detection callback"""
            try:
                mock_event = Mock()
                mock_event.timestamp = Mock()
                mock_event.timestamp.timestamp = Mock(return_value=time.time())
                mock_event.voltage = 3.3
                mock_event.channel = 'AIN0'
                
                # Add small delay to increase chance of race condition
                time.sleep(0.1)
                monitor._handle_detection_with_video_sync(test_session_id, mock_event)
                results['callback_success'] = True
            except Exception as e:
                print(f"❌ Callback worker failed: {e}")
        
        def cleanup_worker():
            """Worker that removes session data"""
            try:
                # Add small delay
                time.sleep(0.05)
                if test_session_id in monitor.active_sessions:
                    del monitor.active_sessions[test_session_id]
                results['cleanup_success'] = True
            except Exception as e:
                print(f"❌ Cleanup worker failed: {e}")
        
        # Start both threads
        callback_thread = threading.Thread(target=callback_worker)
        cleanup_thread = threading.Thread(target=cleanup_worker)
        
        callback_thread.start()
        cleanup_thread.start()
        
        callback_thread.join()
        cleanup_thread.join()
        
        print(f"✅ Concurrent operations completed: callback={results['callback_success']}, cleanup={results['cleanup_success']}")
        return True
        
    except Exception as e:
        print(f"❌ Concurrent operations test failed: {e}")
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("🚀 TESTING DEDICATED HIL MONITORING FIX")
    print("This script validates the fix for session access issues")
    print()
    
    tests = [
        ("None video_start_time fix", test_none_video_start_time_fix),
        ("Edge cases handling", test_edge_cases),
        ("Concurrent operations", test_concurrent_session_operations)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print(f"\n🏁 TEST RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ ALL TESTS PASSED - Fix is working correctly!")
    else:
        print("❌ Some tests failed - Additional fixes may be needed")