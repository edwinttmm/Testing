#!/usr/bin/env python3
"""
LabJack Connection Diagnostic Script

This script tests the LabJack hardware connection and detection pipeline
to identify where the failure is occurring in the HIL test system.

Critical Issues to Diagnose:
1. LabJack hardware connectivity
2. Voltage reading capability
3. Detection service startup
4. Database integration
5. Service coordination
"""

import time
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_labjack_direct_connection():
    """Test 1: Direct LabJack hardware connection"""
    logger.info("=== TEST 1: Direct LabJack Hardware Connection ===")
    
    try:
        # Import LabJack service
        from services.labjack_service import get_labjack_service
        labjack_service = get_labjack_service()
        
        logger.info(f"LabJack Service Status: {labjack_service.status.name}")
        logger.info(f"LabJack Service Mode: {labjack_service.mode.value}")
        
        # Test connection
        is_connected = labjack_service.is_connected()
        logger.info(f"LabJack Connected: {is_connected}")
        
        if not is_connected:
            # Try to connect
            logger.info("Attempting to connect LabJack...")
            connection_result = labjack_service.connect()
            logger.info(f"Connection Result: {connection_result}")
            
            if connection_result:
                logger.info("✅ LabJack connection SUCCESSFUL")
            else:
                logger.error("❌ LabJack connection FAILED")
                return False
        else:
            logger.info("✅ LabJack already connected")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Direct LabJack connection test failed: {e}")
        return False

def test_labjack_voltage_readings():
    """Test 2: LabJack voltage reading capability"""
    logger.info("=== TEST 2: LabJack Voltage Readings ===")
    
    try:
        # Test connection manager approach
        from services.labjack_connection_manager import get_connection_manager
        connection_manager = get_connection_manager()
        
        logger.info("Testing connection manager...")
        if not connection_manager.is_connected():
            connection_manager.connect()
        
        if not connection_manager.is_connected():
            logger.error("❌ Connection manager failed to connect")
            return False
        
        # Test voltage readings on standard channels
        channels = ["AIN0", "AIN1"]
        logger.info("Reading voltages from channels...")
        
        for channel in channels:
            try:
                voltage = connection_manager.read_voltage(channel)
                logger.info(f"📊 {channel}: {voltage:.4f}V")
                
                if voltage is None:
                    logger.warning(f"⚠️ {channel} returned None voltage")
                    
            except Exception as e:
                logger.error(f"❌ Failed to read {channel}: {e}")
        
        logger.info("✅ Voltage reading test completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Voltage reading test failed: {e}")
        return False

def test_detection_service_startup():
    """Test 3: Detection service startup and monitoring"""
    logger.info("=== TEST 3: Detection Service Startup ===")
    
    try:
        from services.labjack_detection_service import get_detection_service
        detection_service = get_detection_service()
        
        logger.info("Detection service retrieved")
        
        # Test session startup
        test_session_id = f"diagnostic_test_{int(time.time())}"
        
        config = {
            'channels': ['AIN0'],
            'voltage_threshold': 2.5,
            'debounce_ms': 100,
            'sample_rate': 10,  # Low sample rate for testing
            'store_in_db': False,
            'enable_websocket': False
        }
        
        logger.info(f"Starting detection monitoring for session: {test_session_id}")
        success = detection_service.start_monitoring(test_session_id, **config)
        
        if success:
            logger.info("✅ Detection service started successfully")
            
            # Monitor for a few seconds
            logger.info("Monitoring for 5 seconds...")
            time.sleep(5)
            
            # Check for events
            events = detection_service.get_detection_events(test_session_id, from_database=False)
            logger.info(f"📊 Detected {len(events)} events during test")
            
            for event in events:
                logger.info(f"Event: {event}")
            
            # Stop monitoring
            detection_service.stop_monitoring(test_session_id)
            logger.info("✅ Detection service stopped")
            
            return True
        else:
            logger.error("❌ Failed to start detection service")
            return False
            
    except Exception as e:
        logger.error(f"❌ Detection service test failed: {e}")
        return False

def test_database_integration():
    """Test 4: Database integration for DetectionEvent storage"""
    logger.info("=== TEST 4: Database Integration ===")
    
    try:
        from database import get_db
        from models import DetectionEvent, TestSession
        
        db = next(get_db())
        
        try:
            # Check if DetectionEvent table exists
            detection_event_count = db.query(DetectionEvent).count()
            logger.info(f"📊 DetectionEvent table has {detection_event_count} records")
            
            # Check if TestSession table exists
            test_session_count = db.query(TestSession).count()
            logger.info(f"📊 TestSession table has {test_session_count} records")
            
            logger.info("✅ Database integration working")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Database integration test failed: {e}")
        return False

def test_dedicated_monitor_service():
    """Test 5: Dedicated LabJack monitor service"""
    logger.info("=== TEST 5: Dedicated Monitor Service ===")
    
    try:
        from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
        dedicated_monitor = get_dedicated_labjack_monitor()
        
        logger.info("Dedicated monitor service retrieved")
        
        # Test configuration
        test_session_id = f"dedicated_test_{int(time.time())}"
        
        video_timing_config = {
            'video_id': 'test-video-id',
            'fps': 30,
            'duration': 5,  # 5 seconds
            'channels': ['AIN0'],
            'voltage_threshold': 2.5,
            'debounce_ms': 50,
            'sample_rate': 10,
            'enable_websocket': False
        }
        
        logger.info(f"Starting dedicated monitoring for session: {test_session_id}")
        success = dedicated_monitor.start_monitoring_with_video_sync(
            test_session_id, 
            video_timing_config
        )
        
        if success:
            logger.info("✅ Dedicated monitor started successfully")
            
            # Monitor for a few seconds
            logger.info("Monitoring for 7 seconds...")
            time.sleep(7)
            
            # Check statistics
            stats = dedicated_monitor.get_monitoring_statistics()
            logger.info(f"📊 Monitoring Statistics: {stats}")
            
            # Get session events
            events = dedicated_monitor.get_session_events(test_session_id)
            logger.info(f"📊 Session Events: {len(events)} events")
            
            for event in events:
                logger.info(f"Event: voltage={event.get('labjack_voltage')}, timestamp={event.get('unix_timestamp')}")
            
            # Stop monitoring
            stop_result = dedicated_monitor.stop_monitoring(test_session_id)
            logger.info(f"✅ Dedicated monitor stopped: {stop_result}")
            
            return len(events) > 0  # Return True if events were captured
        else:
            logger.error("❌ Failed to start dedicated monitor")
            return False
            
    except Exception as e:
        logger.error(f"❌ Dedicated monitor test failed: {e}")
        return False

def test_signal_generation():
    """Test 6: Manual signal generation test"""
    logger.info("=== TEST 6: Manual Signal Generation ===")
    
    logger.info("This test requires manual intervention:")
    logger.info("1. Connect LED or screen to LabJack output channel")
    logger.info("2. Connect voltage detector to LabJack input channel")
    logger.info("3. Generate test signal manually")
    
    try:
        from services.labjack_connection_manager import get_connection_manager
        connection_manager = get_connection_manager()
        
        if not connection_manager.is_connected():
            connection_manager.connect()
        
        logger.info("Reading baseline voltage...")
        baseline = connection_manager.read_voltage("AIN0")
        logger.info(f"📊 Baseline voltage: {baseline:.4f}V")
        
        logger.info("Please generate a test signal now...")
        logger.info("Reading voltage for 10 seconds...")
        
        max_voltage = baseline
        min_voltage = baseline
        readings = []
        
        for i in range(50):  # 10 seconds at 5Hz
            voltage = connection_manager.read_voltage("AIN0")
            readings.append(voltage)
            
            if voltage > max_voltage:
                max_voltage = voltage
            if voltage < min_voltage:
                min_voltage = voltage
                
            if voltage > (baseline + 0.5):
                logger.info(f"🎯 SIGNAL DETECTED: {voltage:.4f}V at {time.time()}")
            
            time.sleep(0.2)
        
        voltage_range = max_voltage - min_voltage
        logger.info(f"📊 Voltage Range: {min_voltage:.4f}V to {max_voltage:.4f}V (range: {voltage_range:.4f}V)")
        
        if voltage_range > 0.5:
            logger.info("✅ Signal variation detected")
            return True
        else:
            logger.warning("⚠️ No significant signal variation detected")
            return False
            
    except Exception as e:
        logger.error(f"❌ Signal generation test failed: {e}")
        return False

def main():
    """Run all diagnostic tests"""
    logger.info("🚀 Starting LabJack HIL System Diagnostic")
    logger.info("=" * 60)
    
    test_results = {}
    
    # Run all tests
    test_functions = [
        ("Direct Connection", test_labjack_direct_connection),
        ("Voltage Readings", test_labjack_voltage_readings), 
        ("Detection Service", test_detection_service_startup),
        ("Database Integration", test_database_integration),
        ("Dedicated Monitor", test_dedicated_monitor_service),
        ("Signal Generation", test_signal_generation)
    ]
    
    for test_name, test_func in test_functions:
        logger.info(f"\n{'=' * 60}")
        try:
            result = test_func()
            test_results[test_name] = result
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{test_name}: {status}")
        except Exception as e:
            test_results[test_name] = False
            logger.error(f"{test_name}: ❌ FAIL (Exception: {e})")
    
    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info("🔍 DIAGNOSTIC SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(test_results.values())
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name:20}: {status}")
    
    logger.info(f"\nOverall Result: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 ALL TESTS PASSED - HIL system should be working")
    elif passed >= 4:
        logger.warning("⚠️ Most tests passed - Minor issues may exist")
    else:
        logger.error("🚨 CRITICAL FAILURES - HIL system needs attention")
    
    return passed >= 4

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)