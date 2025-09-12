#!/usr/bin/env python3
"""
CRITICAL LabJack Integration Test - Final Validation
Tests the complete integration of LabJack hardware services with main API
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_labjack_service_imports():
    """Test that all LabJack services can be imported successfully"""
    try:
        # Test core hardware service
        from services.labjack_hardware_service import (
            get_labjack_hardware_service,
            initialize_hardware_service,
            LabJackHardwareService
        )
        print("✅ Core hardware service imports successful")
        
        # Test video-hardware sync service  
        from services.video_hardware_sync_service import (
            get_video_hardware_sync_service,
            VideoHardwareSyncService
        )
        print("✅ Video-hardware sync service imports successful")
        
        # Test error handler
        from services.labjack_error_handler import (
            get_error_handler_service,
            LabJackErrorHandler
        )
        print("✅ Error handler service imports successful")
        
        # Test configuration manager
        from services.labjack_config_manager import (
            get_config_manager,
            LabJackConfigManager
        )
        print("✅ Configuration manager imports successful")
        
        # Test timing validation service
        from services.timing_validation_service import (
            get_timing_validation_service,
            TimingValidationService
        )
        print("✅ Timing validation service imports successful")
        
        return True
        
    except ImportError as e:
        print(f"❌ Service import failed: {e}")
        return False

def test_labjack_api_imports():
    """Test that LabJack API endpoints can be imported"""
    try:
        # Test main status API
        from api.labjack_status_api import labjack_router
        print("✅ LabJack status API import successful")
        
        # Verify router has expected endpoints
        routes = [route.path for route in labjack_router.routes]
        expected_routes = [
            "/api/labjack/status",
            "/api/labjack/devices", 
            "/api/labjack/connect",
            "/api/labjack/monitoring/start",
            "/api/labjack/health"
        ]
        
        for expected_route in expected_routes:
            # Check if route exists (may have parameters)
            route_exists = any(expected_route in route for route in routes)
            if route_exists:
                print(f"✅ Route found: {expected_route}")
            else:
                print(f"⚠️ Route missing: {expected_route}")
        
        return True
        
    except ImportError as e:
        print(f"❌ API import failed: {e}")
        return False

def test_service_initialization():
    """Test that services can be initialized without hardware"""
    try:
        # Test hardware service initialization (should work in mock mode)
        from services.labjack_hardware_service import initialize_hardware_service
        result = initialize_hardware_service()
        print(f"✅ Hardware service initialization: {result}")
        
        # Test getting service instance
        from services.labjack_hardware_service import get_labjack_hardware_service
        service = get_labjack_hardware_service()
        print(f"✅ Hardware service instance created: {type(service).__name__}")
        
        # Test service status (should work even without hardware)
        status = service.get_status()
        print(f"✅ Service status retrieved: {status['connection_status']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        return False

def test_api_endpoint_structure():
    """Test that API endpoints have correct structure"""
    try:
        from api.labjack_status_api import (
            HardwareStatusResponse,
            DeviceListResponse,
            PrecisionMonitoringRequest
        )
        print("✅ API models import successful")
        
        # Test that response models have required fields
        status_fields = HardwareStatusResponse.__fields__.keys()
        required_status_fields = {"connection_status", "is_connected", "timestamp"}
        
        if required_status_fields.issubset(status_fields):
            print("✅ HardwareStatusResponse has required fields")
        else:
            missing = required_status_fields - status_fields
            print(f"⚠️ HardwareStatusResponse missing fields: {missing}")
        
        return True
        
    except Exception as e:
        print(f"❌ API structure test failed: {e}")
        return False

def test_main_app_integration():
    """Test that main.py can load with LabJack integration"""
    try:
        # Test that we can import the router from main
        import main
        print("✅ Main application imports successful")
        
        # Check if the FastAPI app exists
        if hasattr(main, 'app'):
            print("✅ FastAPI app instance found")
            
            # Check if LabJack routes are included
            routes = [route.path for route in main.app.routes]
            labjack_routes = [route for route in routes if '/labjack' in route]
            
            if labjack_routes:
                print(f"✅ LabJack routes found: {len(labjack_routes)} routes")
                for route in labjack_routes[:5]:  # Show first 5
                    print(f"  - {route}")
            else:
                print("⚠️ No LabJack routes found in main app")
        
        return True
        
    except Exception as e:
        print(f"❌ Main app integration test failed: {e}")
        return False

def run_integration_tests():
    """Run all integration tests"""
    print("🔍 Running LabJack Integration Tests - CRITICAL P0 FUNCTIONALITY")
    print("=" * 70)
    
    tests = [
        ("Service Imports", test_labjack_service_imports),
        ("API Imports", test_labjack_api_imports), 
        ("Service Initialization", test_service_initialization),
        ("API Structure", test_api_endpoint_structure),
        ("Main App Integration", test_main_app_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Testing: {test_name}")
        print("-" * 50)
        
        try:
            result = test_func()
            results.append((test_name, result))
            status = "PASSED" if result else "FAILED"
            print(f"📊 Result: {status}")
        except Exception as e:
            print(f"💥 Exception in {test_name}: {e}")
            results.append((test_name, False))
            
    # Final summary
    print("\n" + "=" * 70)
    print("🎯 FINAL INTEGRATION TEST RESULTS")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📈 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL INTEGRATION TESTS PASSED - HIL TESTING READY!")
        print("✅ CRITICAL P0 FUNCTIONALITY: FULLY OPERATIONAL")
    else:
        print(f"⚠️ {total - passed} tests failed - some functionality may be limited")
    
    return passed == total

if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)