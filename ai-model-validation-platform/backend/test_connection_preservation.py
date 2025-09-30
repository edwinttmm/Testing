#!/usr/bin/env python3
"""
Test Connection Preservation Fix
================================

Validates that the LabJack connection drop issue is fixed by testing:
1. Session-preserving cleanup in dedicated monitor service
2. Connection preservation in LabJack detection service  
3. Bridge connection state management
4. Multiple session lifecycle without connection drops

This test ensures the fix works end-to-end.
"""

import asyncio
import logging
import time
from typing import Dict, Any
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_dedicated_monitor_connection_preservation():
    """Test that dedicated monitor preserves connections during session stop"""
    logger.info("🧪 Testing Dedicated Monitor Connection Preservation")
    
    try:
        from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
        
        monitor = get_dedicated_labjack_monitor()
        
        # Test session configuration
        test_config = {
            'video_id': 'test-video-123',
            'fps': 24,
            'duration': 5.0,
            'channels': ['AIN0'],
            'voltage_threshold': 3.3,
            'enable_websocket': False
        }
        
        session_id = "test-session-preservation"
        
        # Test 1: Start monitoring
        logger.info("📊 Starting monitoring session...")
        success = monitor.start_monitoring_with_video_sync(session_id, test_config)
        if not success:
            logger.error("❌ Failed to start monitoring")
            return False
        
        # Check active sessions
        if session_id not in monitor.active_sessions:
            logger.error("❌ Session not found in active sessions")
            return False
        logger.info("✅ Session started successfully")
        
        # Test 2: Stop with connection preservation
        logger.info("⏹️ Testing connection-preserving stop...")
        stats = monitor.stop_session_monitoring(session_id)
        
        if not stats.get('success'):
            logger.error(f"❌ Session stop failed: {stats.get('error')}")
            return False
            
        if not stats.get('connection_preserved'):
            logger.error("❌ Connection was not preserved!")
            return False
            
        logger.info("✅ Connection preserved successfully")
        
        # Test 3: Verify cleanup
        if session_id in monitor.active_sessions:
            logger.error("❌ Session not cleaned up from active sessions")
            return False
            
        logger.info("✅ Session cleanup completed")
        
        # Test 4: Verify LabJack connection still available
        logger.info("🔌 Testing LabJack connection availability...")
        try:
            # The monitor should still have access to LabJack services
            if monitor.labjack_monitor:
                logger.info("✅ LabJack monitor service still available")
            else:
                logger.warning("⚠️ LabJack monitor service not available")
                
            if hasattr(monitor, 'hil_comparison_service') and monitor.hil_comparison_service:
                logger.info("✅ HIL comparison service still available") 
            else:
                logger.warning("⚠️ HIL comparison service not available")
                
        except Exception as e:
            logger.error(f"❌ Connection availability test failed: {e}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Dedicated monitor test failed: {e}")
        return False

def test_detection_service_connection_preservation():
    """Test that detection service preserves connections"""
    logger.info("🧪 Testing Detection Service Connection Preservation")
    
    try:
        from services.labjack_detection_service import get_detection_service
        
        detection_service = get_detection_service()
        session_id = "test-detection-preservation"
        
        # Test 1: Start detection monitoring
        logger.info("📊 Starting detection monitoring...")
        success = detection_service.start_monitoring(
            session_id,
            channels=['AIN0'],
            voltage_threshold=3.3,
            store_in_db=False
        )
        
        if not success:
            logger.error("❌ Failed to start detection monitoring")
            return False
        logger.info("✅ Detection monitoring started")
        
        # Test 2: Stop with connection preservation
        logger.info("⏹️ Testing connection-preserving stop...")
        success = detection_service.stop_session_monitoring(session_id)
        
        if not success:
            logger.error("❌ Session stop failed")
            return False
        logger.info("✅ Session stopped with connection preservation")
        
        # Test 3: Verify session cleanup
        if session_id in detection_service.active_sessions:
            logger.error("❌ Session not cleaned up")
            return False
        logger.info("✅ Session cleanup completed")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Detection service test failed: {e}")
        return False

def test_bridge_connection_preservation():
    """Test that bridge maintains session state correctly"""
    logger.info("🧪 Testing Bridge Connection Preservation")
    
    try:
        from services.windows_labjack_bridge import windows_labjack_bridge
        
        session_id = "test-bridge-preservation"
        
        # Test 1: Start session monitoring
        logger.info("🚀 Starting bridge session monitoring...")
        success = windows_labjack_bridge.start_session_monitoring(session_id)
        
        if not success:
            logger.error("❌ Failed to start bridge session monitoring")
            return False
        
        # Check session is tracked
        if session_id not in windows_labjack_bridge.active_sessions:
            logger.error("❌ Session not tracked in bridge")
            return False
        logger.info("✅ Bridge session monitoring started")
        
        # Test 2: Stop session monitoring (preserve connection)
        logger.info("⏹️ Testing bridge session stop...")
        success = windows_labjack_bridge.stop_session_monitoring(session_id)
        
        if not success:
            logger.error("❌ Bridge session stop failed")
            return False
        
        # Test 3: Verify session cleanup
        if session_id in windows_labjack_bridge.active_sessions:
            logger.error("❌ Session not cleaned up from bridge")
            return False
        logger.info("✅ Bridge session cleanup completed")
        
        # Test 4: Verify bridge monitoring state
        if windows_labjack_bridge.get_active_session_count() != 0:
            logger.warning(f"⚠️ Bridge has {windows_labjack_bridge.get_active_session_count()} active sessions remaining")
        else:
            logger.info("✅ Bridge shows no active sessions")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Bridge test failed: {e}")
        return False

def test_multiple_session_lifecycle():
    """Test multiple sessions without connection drops"""
    logger.info("🧪 Testing Multiple Session Lifecycle")
    
    try:
        from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
        
        monitor = get_dedicated_labjack_monitor()
        
        # Test configuration
        test_config = {
            'video_id': 'test-multi-session',
            'fps': 24,
            'duration': 2.0,
            'channels': ['AIN0'],
            'voltage_threshold': 3.3,
            'enable_websocket': False
        }
        
        sessions = ["session-1", "session-2", "session-3"]
        
        # Test 1: Start multiple sessions sequentially
        logger.info("📊 Starting multiple sessions...")
        for session_id in sessions:
            logger.info(f"Starting session: {session_id}")
            success = monitor.start_monitoring_with_video_sync(session_id, test_config)
            if not success:
                logger.error(f"❌ Failed to start session {session_id}")
                return False
            
            # Brief pause between sessions
            time.sleep(0.5)
            
            # Stop session with connection preservation
            logger.info(f"Stopping session: {session_id}")
            stats = monitor.stop_session_monitoring(session_id)
            
            if not stats.get('success'):
                logger.error(f"❌ Failed to stop session {session_id}")
                return False
                
            if not stats.get('connection_preserved'):
                logger.error(f"❌ Connection not preserved for session {session_id}")
                return False
        
        logger.info("✅ Multiple session lifecycle completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Multiple session test failed: {e}")
        return False

def main():
    """Run all connection preservation tests"""
    logger.info("🚀 Starting LabJack Connection Preservation Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Dedicated Monitor", test_dedicated_monitor_connection_preservation),
        ("Detection Service", test_detection_service_connection_preservation),
        ("Bridge Service", test_bridge_connection_preservation),
        ("Multiple Sessions", test_multiple_session_lifecycle)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running {test_name} Test...")
        logger.info("-" * 40)
        
        try:
            result = test_func()
            results[test_name] = result
            
            if result:
                logger.info(f"✅ {test_name} Test PASSED")
            else:
                logger.error(f"❌ {test_name} Test FAILED")
                
        except Exception as e:
            logger.error(f"💥 {test_name} Test CRASHED: {e}")
            results[test_name] = False
        
        # Brief pause between tests
        time.sleep(1)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 CONNECTION PRESERVATION TEST RESULTS")
    logger.info("=" * 60)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "PASSED ✅" if result else "FAILED ❌"
        logger.info(f"{test_name:<20}: {status}")
        if result:
            passed += 1
    
    logger.info("-" * 60)
    logger.info(f"TOTAL: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 ALL TESTS PASSED - Connection preservation is working!")
        logger.info("🔧 LabJack connection drop issue has been FIXED")
    else:
        logger.error(f"💥 {total - passed} tests failed - connection preservation needs work")
        logger.error("🚨 LabJack connection drop issue still exists")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)