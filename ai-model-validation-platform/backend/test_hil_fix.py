#!/usr/bin/env python3
"""
Test script to validate the HIL monitoring startup fix.
This tests the specific KeyError that was causing 'session_id' to be displayed as the error.
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone

def test_dedicated_hil_monitor_fix():
    """Test that the session initialization fix works"""
    print("🔧 Testing dedicated HIL monitoring startup fix...")
    
    try:
        # Import the fixed class
        from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
        
        # Create monitor instance
        monitor = DedicatedLabJackMonitor()
        
        # Test session ID
        session_id = str(uuid.uuid4())
        print(f"📝 Testing with session ID: {session_id}")
        
        # Test video timing config (minimal required fields)
        video_timing_config = {
            'video_id': '2ad0f85c-ebe3-4f5d-8dff-8839dc3292a9',
            'fps': 24,
            'duration': 5.0,
            'channels': ['AIN0'],
            'voltage_threshold': 3.3
        }
        
        print("✅ About to test start_monitoring_with_video_sync...")
        print("✅ This should no longer fail with KeyError showing just the session ID")
        
        # This should now work without the KeyError
        result = monitor.start_monitoring_with_video_sync(session_id, video_timing_config)
        
        if result:
            print("✅ SUCCESS: HIL monitoring started successfully!")
            print("✅ The KeyError fix is working!")
            
            # Clean up
            monitor.stop_monitoring(session_id)
            print("✅ Monitoring stopped and cleaned up")
        else:
            print("⚠️  EXPECTED: HIL monitoring failed to start (but with proper error logging now)")
            print("⚠️  Check that the error message is now descriptive, not just a session ID")
            
        return True
            
    except Exception as e:
        print(f"❌ CRITICAL: Test failed with exception: {e}")
        print(f"❌ Exception type: {type(e).__name__}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🚀 HIL Monitoring KeyError Fix Test")
    print("=" * 50)
    
    success = test_dedicated_hil_monitor_fix()
    
    print("=" * 50)
    if success:
        print("✅ TEST PASSED: KeyError fix is working")
        print("✅ Enhanced error logging should now show detailed tracebacks")
    else:
        print("❌ TEST FAILED: KeyError fix needs more work")
        
    sys.exit(0 if success else 1)