#!/usr/bin/env python3
"""
Debug script to locate and reproduce the persistent KeyError in dedicated HIL monitoring.
Reproduces the exact error scenario reported: 'c34ef2ce-2bc9-4c99-8e24-44e7ca6d5197'
"""

import sys
import os
import time
import asyncio
import threading
import uuid
import traceback
from typing import Dict, Any
from unittest.mock import Mock

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

def test_session_access_order():
    """Test session dictionary access order to find KeyError source"""
    
    print("🔍 DEBUGGING SESSION ACCESS KEYERROR")
    print("=" * 60)
    
    try:
        # Import the services
        from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
        from services.timing_synchronization_service import timing_sync_service
        
        print("✅ Services imported successfully")
        
        # Create monitor instance
        monitor = DedicatedLabJackMonitor()
        print(f"✅ Monitor created. Initial sessions: {len(monitor.active_sessions)}")
        
        # Test session ID (similar to the error case)
        test_session_id = "c34ef2ce-2bc9-4c99-8e24-44e7ca6d5197"
        
        print(f"\n🧪 Testing session: {test_session_id}")
        
        # Test 1: Direct session access before initialization
        print("\n📋 Test 1: Direct session access before initialization")
        try:
            if test_session_id in monitor.active_sessions:
                print("❌ Session found when it shouldn't exist")
            else:
                print("✅ Session correctly not found before initialization")
        except Exception as e:
            print(f"❌ Error accessing session dict: {e}")
            traceback.print_exc()
        
        # Test 2: Lambda callback creation and session access
        print("\n📋 Test 2: Lambda callback creation and session access")
        try:
            # Mock the callback approach from start_monitoring_with_video_sync
            detection_callback = lambda event: test_callback_session_access(monitor, test_session_id, event)
            print("✅ Lambda callback created successfully")
            
            # Test the callback with a mock event
            mock_event = Mock()
            mock_event.timestamp = Mock()
            mock_event.timestamp.timestamp = Mock(return_value=time.time())
            mock_event.voltage = 3.3
            mock_event.channel = 'AIN0'
            
            print("🧪 Calling lambda callback with mock event...")
            detection_callback(mock_event)
            
        except Exception as e:
            print(f"❌ Error in lambda callback test: {e}")
            traceback.print_exc()
        
        # Test 3: Timing sync service session access
        print("\n📋 Test 3: Timing sync service session access")
        try:
            # Test async timing sync preparation
            print("🧪 Testing timing_sync_service.prepare_monitoring()")
            
            def run_async_test():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        sync_data = loop.run_until_complete(timing_sync_service.prepare_monitoring(test_session_id))
                        print(f"✅ Timing sync prepared: {sync_data}")
                        
                        # Test confirm monitoring ready
                        ready_time = timing_sync_service.confirm_monitoring_ready(test_session_id)
                        print(f"✅ Monitoring confirmed ready: {ready_time}")
                        
                    finally:
                        loop.close()
                        asyncio.set_event_loop(None)
                except Exception as e:
                    print(f"❌ Async timing sync error: {e}")
                    traceback.print_exc()
            
            run_async_test()
            
        except Exception as e:
            print(f"❌ Error in timing sync test: {e}")
            traceback.print_exc()
        
        # Test 4: Session initialization order simulation
        print("\n📋 Test 4: Session initialization order simulation")
        try:
            # Simulate the EXACT order from start_monitoring_with_video_sync
            
            # Step 1: Initialize session entry (line 135 in dedicated_labjack_monitor.py)
            print("🔧 Step 1: Initialize session entry")
            monitor.active_sessions[test_session_id] = {
                'video_timing_config': {'video_id': '2ad0f85c-ebe3-4f5d-8dff-8839dc3292a9'},
                'labjack_config': {'channels': ['AIN0']},
                'started_at': time.time(),
                'video_start_time': None,
                'detection_callback': None
            }
            print(f"✅ Session initialized: {test_session_id}")
            
            # Step 2: Create callback and store reference (line 144-147)
            print("🔧 Step 2: Create and store callback")
            detection_callback = lambda event: monitor._handle_detection_with_video_sync(test_session_id, event)
            monitor.active_sessions[test_session_id]['detection_callback'] = detection_callback
            print("✅ Callback stored in session")
            
            # Step 3: Test callback execution
            print("🔧 Step 3: Test callback execution")
            mock_event = Mock()
            mock_event.timestamp = Mock()
            mock_event.timestamp.timestamp = Mock(return_value=time.time())
            mock_event.voltage = 3.3
            mock_event.channel = 'AIN0'
            
            detection_callback(mock_event)
            print("✅ Callback executed successfully")
            
        except Exception as e:
            print(f"❌ Error in session initialization test: {e}")
            traceback.print_exc()
        
        # Test 5: Concurrent access simulation
        print("\n📋 Test 5: Concurrent session access simulation")
        try:
            def concurrent_access_test():
                """Simulate concurrent access from different threads"""
                try:
                    # Access session from another thread (like async callback)
                    session_info = monitor.active_sessions.get(test_session_id)
                    if session_info:
                        print(f"✅ Concurrent access successful: {len(session_info)} keys")
                    else:
                        print("❌ Concurrent access failed - session not found")
                except Exception as e:
                    print(f"❌ Concurrent access error: {e}")
                    traceback.print_exc()
            
            # Run in separate thread
            thread = threading.Thread(target=concurrent_access_test)
            thread.start()
            thread.join()
            
        except Exception as e:
            print(f"❌ Error in concurrent access test: {e}")
            traceback.print_exc()
            
        # Test 6: Session cleanup and edge cases
        print("\n📋 Test 6: Session cleanup and edge cases")
        try:
            # Test session removal during callback
            print("🔧 Testing session removal during callback execution")
            
            def cleanup_during_callback():
                # Remove session while callback might be executing
                if test_session_id in monitor.active_sessions:
                    del monitor.active_sessions[test_session_id]
                    print("✅ Session removed during cleanup")
            
            cleanup_thread = threading.Thread(target=cleanup_during_callback)
            cleanup_thread.start()
            cleanup_thread.join()
            
            # Now try to access the session
            session_info = monitor.active_sessions.get(test_session_id)
            if not session_info:
                print("✅ Session correctly removed")
            else:
                print("❌ Session still present after removal")
            
        except Exception as e:
            print(f"❌ Error in cleanup test: {e}")
            traceback.print_exc()
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        traceback.print_exc()


def test_callback_session_access(monitor, session_id, event):
    """Test callback function that replicates _handle_detection_with_video_sync logic"""
    try:
        print(f"🔍 Callback called for session: {session_id}")
        
        # CRITICAL: Check session existence (line 332 in _handle_detection_with_video_sync)
        if session_id not in monitor.active_sessions:
            print(f"🚫 Session {session_id} not in active_sessions - returning early")
            return
        
        # CRITICAL: Get session info (line 339 in _handle_detection_with_video_sync)  
        session_info = monitor.active_sessions.get(session_id)
        if not session_info:
            print(f"⚠️ Session {session_id} no longer active, skipping detection")
            return
            
        print(f"✅ Session access successful: {session_info.keys()}")
        
        # Test fallback timing access (line 360)
        session_start_time = monitor.active_sessions.get(session_id, {}).get('video_start_time', time.time())
        print(f"✅ Fallback timing access successful: {session_start_time}")
        
    except KeyError as ke:
        print(f"🚨 KEYERROR FOUND IN CALLBACK: {ke}")
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Error in callback session access: {e}")
        traceback.print_exc()


def analyze_actual_error_location():
    """Analyze the exact error location based on code review"""
    
    print("\n🔍 ANALYZING POTENTIAL ERROR LOCATIONS")
    print("=" * 60)
    
    potential_locations = [
        {
            'location': 'Line 144: detection_callback = lambda event: self._handle_detection_with_video_sync(session_id, event)',
            'issue': 'Lambda closure - session_id captured by reference, could change',
            'likelihood': 'HIGH'
        },
        {
            'location': 'Line 161: sync_data = loop.run_until_complete(timing_sync_service.prepare_monitoring(session_id))',
            'issue': 'Async/await context - timing_sync_service might access session data',
            'likelihood': 'MEDIUM'
        },
        {
            'location': 'Line 339: session_info = self.active_sessions.get(session_id)',
            'issue': 'Session might be deleted between line 332 check and line 339 access',
            'likelihood': 'LOW'
        },
        {
            'location': 'Line 360: session_start_time = self.active_sessions.get(session_id, {}).get(...)',
            'issue': 'Nested .get() on potentially None value if session was deleted',
            'likelihood': 'HIGH'
        }
    ]
    
    for i, location in enumerate(potential_locations, 1):
        print(f"\n🎯 Potential Issue #{i}:")
        print(f"   Location: {location['location']}")
        print(f"   Issue: {location['issue']}")
        print(f"   Likelihood: {location['likelihood']}")


if __name__ == '__main__':
    print("🚀 STARTING DEDICATED HIL MONITORING KEYERROR DEBUG")
    print("This script reproduces the session access timing issues")
    print()
    
    test_session_access_order()
    analyze_actual_error_location()
    
    print("\n✅ DEBUG ANALYSIS COMPLETE")
    print("Check output above for KeyError reproduction and analysis")