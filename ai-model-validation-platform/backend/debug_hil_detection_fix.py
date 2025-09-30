#!/usr/bin/env python3
"""
CRITICAL HIL Detection Debug Script

This script tests the HIL detection pipeline to identify why
detection events are not being captured after the fallback prevention fix.

Issues to investigate:
1. LabJack service connection status
2. HIL validation service blocking real hardware
3. Detection event callback registration
4. Database storage pipeline
5. Voltage threshold configuration
"""

import sys
import asyncio
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_labjack_connection():
    """Test LabJack service connection without strict validation"""
    try:
        from services.labjack_service import get_labjack_service
        
        logger.info("🔌 Testing LabJack service connection...")
        
        labjack_service = get_labjack_service()
        
        # Test normal connection (not the strict allow_mock=False)
        logger.info("Attempting normal connection...")
        success = asyncio.run(labjack_service.connect())
        
        if success:
            status = labjack_service.get_status()
            device_info = status.device_info
            
            logger.info(f"✅ LabJack connected successfully")
            logger.info(f"   Mode: {status.mode.value}")
            logger.info(f"   Status: {status.status.value}")
            logger.info(f"   Device: {device_info.get('device_type', 'Unknown')}")
            logger.info(f"   Serial: {device_info.get('serial_number', 'Unknown')}")
            logger.info(f"   Connection: {device_info.get('connection_type', 'Unknown')}")
            logger.info(f"   Is Mock: {device_info.get('is_mock', False)}")
            
            # Test voltage reading
            try:
                voltage = asyncio.run(labjack_service.read_voltage('AIN0'))
                logger.info(f"   AIN0 Voltage: {voltage:.3f}V")
            except Exception as e:
                logger.error(f"   Voltage read failed: {e}")
            
            return True, status
        else:
            logger.error("❌ LabJack connection failed")
            return False, None
            
    except Exception as e:
        logger.error(f"❌ LabJack connection test failed: {e}")
        return False, None

def test_hil_validation():
    """Test HIL validation service"""
    try:
        from services.hil_validation_service import get_hil_validation_service
        from services.labjack_service import get_labjack_service
        
        logger.info("🛡️ Testing HIL validation service...")
        
        labjack_service = get_labjack_service()
        hil_validation = get_hil_validation_service(labjack_service)
        
        # Test hardware status
        hardware_status = hil_validation.get_hardware_status_for_ui()
        logger.info(f"Hardware Status:")
        for key, value in hardware_status.items():
            logger.info(f"   {key}: {value}")
        
        # Test validation
        try:
            validation_result = hil_validation.validate_hardware_for_hil()
            logger.info(f"✅ HIL validation passed: {validation_result.status_message}")
            return True, validation_result
        except Exception as e:
            logger.error(f"❌ HIL validation failed: {e}")
            return False, None
            
    except Exception as e:
        logger.error(f"❌ HIL validation test failed: {e}")
        return False, None

def test_detection_service():
    """Test LabJack detection monitoring service"""
    try:
        from services.labjack_detection_service import get_detection_service
        
        logger.info("🎯 Testing LabJack detection service...")
        
        detection_service = get_detection_service()
        
        # Test basic service availability
        logger.info(f"Detection service initialized: {detection_service is not None}")
        
        # Test session startup
        test_session_id = "test_debug_session"
        
        logger.info(f"Starting detection monitoring for session: {test_session_id}")
        
        config = {
            'channels': ['AIN0'],
            'voltage_threshold': 2.5,
            'debounce_ms': 50,
            'sample_rate': 10,
            'store_in_db': False
        }
        
        success = detection_service.start_monitoring(test_session_id, **config)
        
        if success:
            logger.info("✅ Detection monitoring started successfully")
            
            # Wait for a few seconds to see if any events are captured
            import time
            logger.info("Waiting 5 seconds for detection events...")
            time.sleep(5)
            
            # Stop monitoring
            detection_service.stop_monitoring(test_session_id)
            logger.info("Detection monitoring stopped")
            
            return True
        else:
            logger.error("❌ Detection monitoring failed to start")
            return False
            
    except Exception as e:
        logger.error(f"❌ Detection service test failed: {e}")
        return False

def test_dedicated_hil_monitor():
    """Test the dedicated HIL monitor service"""
    try:
        from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
        
        logger.info("🎮 Testing dedicated HIL monitor...")
        
        monitor = get_dedicated_labjack_monitor()
        
        # Test session startup
        test_session_id = "test_hil_debug_session"
        
        video_timing_config = {
            'video_id': 'test_video',
            'fps': 30,
            'duration': 10.0,
            'channels': ['AIN0'],
            'voltage_threshold': 2.5,
            'debounce_ms': 50,
            'sample_rate': 10,
            'enable_websocket': True
        }
        
        logger.info(f"Starting HIL monitoring for session: {test_session_id}")
        
        success = monitor.start_monitoring_with_video_sync(test_session_id, video_timing_config)
        
        if success:
            logger.info("✅ HIL monitoring started successfully")
            
            # Wait for monitoring
            import time
            logger.info("Waiting 8 seconds for HIL detection events...")
            time.sleep(8)
            
            # Check for events
            events = monitor.get_session_events(test_session_id)
            logger.info(f"Captured {len(events)} HIL events")
            
            for event in events:
                logger.info(f"   Event: {event['labjack_voltage']:.3f}V @ {event['video_relative_timestamp']:.3f}s")
            
            # Stop monitoring
            stats = monitor.stop_monitoring(test_session_id)
            logger.info(f"HIL monitoring stopped: {stats}")
            
            return True, len(events)
        else:
            logger.error("❌ HIL monitoring failed to start")
            return False, 0
            
    except Exception as e:
        logger.error(f"❌ HIL monitor test failed: {e}")
        return False, 0

def main():
    """Run comprehensive HIL detection debugging"""
    logger.info("🚨 CRITICAL HIL DETECTION DEBUG SESSION STARTING")
    logger.info("=" * 60)
    
    results = {}
    
    # Test 1: LabJack Connection
    logger.info("\n📋 TEST 1: LabJack Service Connection")
    results['labjack_connection'], labjack_status = test_labjack_connection()
    
    # Test 2: HIL Validation
    logger.info("\n📋 TEST 2: HIL Hardware Validation")
    results['hil_validation'], validation_result = test_hil_validation()
    
    # Test 3: Detection Service
    logger.info("\n📋 TEST 3: LabJack Detection Service")
    results['detection_service'] = test_detection_service()
    
    # Test 4: Dedicated HIL Monitor
    logger.info("\n📋 TEST 4: Dedicated HIL Monitor")
    results['hil_monitor'], event_count = test_dedicated_hil_monitor()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("🏁 HIL DETECTION DEBUG RESULTS:")
    logger.info(f"   ✅ LabJack Connection: {'PASS' if results['labjack_connection'] else 'FAIL'}")
    logger.info(f"   ✅ HIL Validation: {'PASS' if results['hil_validation'] else 'FAIL'}")
    logger.info(f"   ✅ Detection Service: {'PASS' if results['detection_service'] else 'FAIL'}")
    logger.info(f"   ✅ HIL Monitor: {'PASS' if results['hil_monitor'] else 'FAIL'}")
    
    if results['hil_monitor']:
        logger.info(f"   🎯 Detection Events Captured: {event_count}")
    
    # Analysis
    logger.info("\n📊 ANALYSIS:")
    
    if not results['labjack_connection']:
        logger.error("❌ ROOT CAUSE: LabJack service connection failed")
        logger.error("   Fix: Check LabJack hardware connection and drivers")
    elif not results['hil_validation']:
        logger.error("❌ ROOT CAUSE: HIL validation rejected real hardware")
        logger.error("   Fix: Adjust HIL validation logic to accept real hardware")
    elif not results['detection_service']:
        logger.error("❌ ROOT CAUSE: Detection service failed to start monitoring")
        logger.error("   Fix: Check detection service initialization and configuration")
    elif not results['hil_monitor']:
        logger.error("❌ ROOT CAUSE: HIL monitor failed to start")
        logger.error("   Fix: Check HIL monitor service and callback registration")
    elif event_count == 0:
        logger.error("❌ ROOT CAUSE: HIL monitoring started but no events captured")
        logger.error("   Fix: Check voltage threshold, signal generation, or hardware setup")
    else:
        logger.info("✅ ALL TESTS PASSED: HIL detection pipeline is working correctly")
    
    logger.info("=" * 60)

if __name__ == "__main__":
    main()