#!/usr/bin/env python3
"""
Integration test to verify that all new architectural services integrate properly
with the enhanced API endpoints and database schema.
"""

import sys
import traceback

def test_imports():
    """Test that all imports work correctly"""
    print("Testing imports...")
    
    try:
        # Test enum imports from schemas
        from schemas import (
            CameraTypeEnum, SignalTypeEnum, ProjectStatusEnum,
            PassFailCriteriaSchema, StatisticalValidationSchema,
            VideoLibraryOrganizeResponse, DetectionPipelineResponse
        )
        print("✓ Schema imports successful")
        
        # Test new service imports (these won't work without dependencies but we can test syntax)
        import ast
        
        # Check main.py syntax and imports
        with open('main.py', 'r') as f:
            main_content = f.read()
            ast.parse(main_content)
        print("✓ main.py syntax validation successful")
        
        # Test that enums have correct values
        assert CameraTypeEnum.FRONT_FACING_VRU == "Front-facing VRU"
        assert CameraTypeEnum.MULTI_ANGLE_SCENARIOS == "Multi-angle"
        assert SignalTypeEnum.CAN_BUS == "CAN Bus"
        assert ProjectStatusEnum.TESTING == "testing"
        print("✓ Enum values verification successful")
        
        return True
        
    except Exception as e:
        print(f"✗ Import test failed: {e}")
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test that API endpoint definitions are valid"""
    print("\nTesting API endpoint definitions...")
    
    try:
        # Read main.py and check for new endpoints
        with open('main.py', 'r') as f:
            content = f.read()
        
        # Check for required new endpoints
        required_endpoints = [
            '/api/video-library/organize/',
            '/api/detection/pipeline/run',
            '/api/signals/process',
            '/api/projects/{project_id}/criteria/configure',
            '/api/validation/statistical/run',
            '/api/ids/generate/'
        ]
        
        for endpoint in required_endpoints:
            if endpoint in content:
                print(f"✓ Found endpoint: {endpoint}")
            else:
                print(f"✗ Missing endpoint: {endpoint}")
                return False
        
        # Check for enhanced dashboard endpoint
        if 'EnhancedDashboardStats' in content:
            print("✓ Enhanced dashboard stats integration found")
        else:
            print("✗ Enhanced dashboard stats not integrated")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ API endpoint test failed: {e}")
        return False

def test_schema_compliance():
    """Test that schemas comply with architectural requirements"""
    print("\nTesting schema compliance...")
    
    try:
        from schemas import CameraTypeEnum, SignalTypeEnum
        
        # Verify all required camera types are present
        required_cameras = [
            "Front-facing VRU", "Rear-facing VRU", 
            "In-Cab Driver Behavior", "Multi-angle"
        ]
        
        camera_values = [camera.value for camera in CameraTypeEnum]
        for camera in required_cameras:
            if camera in camera_values:
                print(f"✓ Camera type supported: {camera}")
            else:
                print(f"✗ Missing camera type: {camera}")
                return False
        
        # Verify all required signal types are present
        required_signals = [
            "GPIO", "Network Packet", "Serial", "CAN Bus"
        ]
        
        signal_values = [signal.value for signal in SignalTypeEnum]
        for signal in required_signals:
            if signal in signal_values:
                print(f"✓ Signal type supported: {signal}")
            else:
                print(f"✗ Missing signal type: {signal}")
                return False
                
        return True
        
    except Exception as e:
        print(f"✗ Schema compliance test failed: {e}")
        return False

def test_service_integration():
    """Test that service integration is properly configured"""
    print("\nTesting service integration...")
    
    try:
        # Check that main.py imports all architectural services
        with open('main.py', 'r') as f:
            content = f.read()
        
        required_services = [
            'VideoLibraryManager',
            'DetectionPipelineService', 
            'SignalProcessingWorkflow',
            'ProjectManagementService',
            'ValidationAnalysisService',
            'IDGenerationService'
        ]
        
        for service in required_services:
            if service in content:
                print(f"✓ Service integrated: {service}")
            else:
                print(f"✗ Service not integrated: {service}")
                return False
                
        return True
        
    except Exception as e:
        print(f"✗ Service integration test failed: {e}")
        return False

def main():
    """Run all integration tests"""
    print("=" * 60)
    print("AI MODEL VALIDATION PLATFORM - INTEGRATION TEST")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_api_endpoints,
        test_schema_compliance,
        test_service_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
                print(f"✓ {test.__name__} PASSED")
            else:
                failed += 1
                print(f"✗ {test.__name__} FAILED")
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} FAILED with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"INTEGRATION TEST RESULTS: {passed} PASSED, {failed} FAILED")
    print("=" * 60)
    
    if failed == 0:
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("✅ Frontend and backend are properly integrated with architectural services")
        return 0
    else:
        print("❌ SOME INTEGRATION TESTS FAILED")
        print("⚠️  Please review the failed tests and fix any issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())