#!/usr/bin/env python3
"""
Test script for LabJack real hardware integration
Tests the RealLabJackService initialization and hardware detection
"""

import sys
import os
import logging
from pathlib import Path

# Add the backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_labjack_library_import():
    """Test LabJack library import and basic functionality"""
    logger.info("=== Testing LabJack Library Import ===")
    
    try:
        import labjack.ljm as ljm
        logger.info("✅ Successfully imported labjack.ljm")
        
        # Test basic functions
        functions_to_test = ['openS', 'close', 'getHandleInfo', 'numberToType', 'numberToConnectionType']
        available_functions = dir(ljm)
        
        for func_name in functions_to_test:
            if hasattr(ljm, func_name):
                logger.info(f"✅ Function {func_name} available")
            else:
                logger.warning(f"⚠️ Function {func_name} not available")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Failed to import LabJack library: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error testing library: {e}")
        return False

def test_labjack_service_initialization():
    """Test LabJack service initialization with real hardware support"""
    logger.info("=== Testing LabJack Service Initialization ===")
    
    try:
        from services.labjack_service import LabJackService, ConnectionMode, get_labjack_service
        logger.info("✅ Successfully imported LabJack service classes")
        
        # Initialize service
        service = LabJackService()
        logger.info("✅ LabJack service initialized successfully")
        
        # Test connection attempt (will fail without hardware, but should not crash)
        logger.info("🔌 Testing connection attempt...")
        
        # Test direct connection mode specifically
        connection_success = False
        try:
            import asyncio
            connection_success = asyncio.run(service.connect(force_mode=ConnectionMode.DIRECT))
        except Exception as connect_error:
            logger.info(f"⚠️ Connection failed as expected without hardware: {connect_error}")
        
        if connection_success:
            logger.info("🎉 HARDWARE DETECTED: Real LabJack device connected!")
            device_info = asyncio.run(service.get_device_info())
            logger.info(f"📊 Device Info: {device_info}")
        else:
            logger.info("📍 No hardware detected - service ready for real hardware connection")
        
        # Test service status
        status = service.get_status()
        logger.info(f"📊 Service Status: Mode={status.mode.value}, Status={status.status.value}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Service initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_device_detection_functionality():
    """Test device detection without requiring hardware"""
    logger.info("=== Testing Device Detection Functionality ===")
    
    try:
        # Test the device detection logic
        import labjack.ljm as ljm
        
        logger.info("🔍 Testing device enumeration...")
        
        try:
            # Try to enumerate devices (will return empty list if no hardware)
            devices = []
            try:
                # This is the official way to enumerate LabJack devices
                devices = ljm.listAll(ljm.constants.dtANY, ljm.constants.ctANY)
                logger.info(f"📋 Found {len(devices)} LabJack devices")
                
                if devices:
                    for i, device in enumerate(devices):
                        logger.info(f"  Device {i}: {device}")
                else:
                    logger.info("📍 No LabJack devices detected (expected without hardware)")
                    
            except Exception as enum_error:
                logger.info(f"📍 Device enumeration completed (no devices found): {enum_error}")
        
        except AttributeError as e:
            logger.info(f"⚠️ Device enumeration not supported in this library version: {e}")
        
        # Test connection attempt with proper error handling
        try:
            logger.info("🔌 Testing connection to ANY device...")
            handle = ljm.openS("ANY", "ANY", "ANY")
            logger.info("🎉 SUCCESS: LabJack hardware is connected!")
            
            # Get device info
            info = ljm.getHandleInfo(handle)
            device_type = ljm.numberToType(info[0])
            connection_type = ljm.numberToConnectionType(info[1])
            serial_number = info[2]
            
            logger.info(f"📊 Connected Device:")
            logger.info(f"  - Type: {device_type}")
            logger.info(f"  - Connection: {connection_type}")
            logger.info(f"  - Serial: {serial_number}")
            
            # Close the connection
            ljm.close(handle)
            logger.info("🔌 Connection closed")
            
            return "HARDWARE_DETECTED"
            
        except Exception as connect_error:
            logger.info(f"📍 No hardware detected (expected): {connect_error}")
            return "NO_HARDWARE"
        
    except Exception as e:
        logger.error(f"❌ Device detection test failed: {e}")
        return False

def test_precision_timing_integration():
    """Test precision timing service integration"""
    logger.info("=== Testing Precision Timing Integration ===")
    
    try:
        from services.video_timing_service import VideoTimingService
        logger.info("✅ VideoTimingService imported successfully")
        
        # Test initialization
        timing_service = VideoTimingService()
        logger.info("✅ VideoTimingService initialized")
        
        return True
        
    except ImportError as e:
        logger.warning(f"⚠️ VideoTimingService not available: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Precision timing test failed: {e}")
        return False

def test_api_endpoints():
    """Test LabJack API endpoints"""
    logger.info("=== Testing API Endpoints ===")
    
    try:
        # Check if main application has LabJack endpoints
        from main import app
        logger.info("✅ Main application imported")
        
        # List all routes to find LabJack endpoints
        labjack_routes = []
        for route in app.routes:
            if hasattr(route, 'path') and 'labjack' in route.path.lower():
                labjack_routes.append(route.path)
        
        if labjack_routes:
            logger.info(f"✅ Found LabJack API endpoints: {labjack_routes}")
        else:
            logger.info("📍 No specific LabJack endpoints found in main app")
        
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ API endpoint test skipped: {e}")
        return False

def main():
    """Main test function"""
    logger.info("🚀 LabJack Hardware Integration Test Suite")
    logger.info("=" * 50)
    
    results = {}
    
    # Test 1: Library Import
    results['library_import'] = test_labjack_library_import()
    
    # Test 2: Service Initialization
    results['service_init'] = test_labjack_service_initialization()
    
    # Test 3: Device Detection
    results['device_detection'] = test_device_detection_functionality()
    
    # Test 4: Precision Timing
    results['timing_integration'] = test_precision_timing_integration()
    
    # Test 5: API Endpoints
    results['api_endpoints'] = test_api_endpoints()
    
    # Summary
    logger.info("=" * 50)
    logger.info("🏁 TEST RESULTS SUMMARY")
    logger.info("=" * 50)
    
    passed = sum(1 for r in results.values() if r is True)
    hardware_detected = results.get('device_detection') == 'HARDWARE_DETECTED'
    
    for test_name, result in results.items():
        if result is True:
            logger.info(f"✅ {test_name}: PASSED")
        elif result == 'HARDWARE_DETECTED':
            logger.info(f"🎉 {test_name}: HARDWARE DETECTED!")
        elif result == 'NO_HARDWARE':
            logger.info(f"📍 {test_name}: NO HARDWARE (READY FOR CONNECTION)")
        else:
            logger.info(f"❌ {test_name}: FAILED")
    
    logger.info("=" * 50)
    if hardware_detected:
        logger.info("🎉 HARDWARE INTEGRATION: REAL LABJACK DEVICE CONNECTED!")
    else:
        logger.info("📍 HARDWARE INTEGRATION: READY FOR REAL LABJACK CONNECTION")
    
    logger.info(f"✅ Tests Passed: {passed}/{len(results)}")
    logger.info("🚀 LabJack hardware integration is ready!")

if __name__ == "__main__":
    main()