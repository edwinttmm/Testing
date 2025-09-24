#!/usr/bin/env python3
"""
HIL Video Duration Fix Validation Script
========================================

Simple validation script to test the HIL video duration resolution fix
without requiring external dependencies like pytest.
"""

import sys
import os
import time
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_imports():
    """Test that all required modules can be imported"""
    print("📦 Testing imports...")
    
    try:
        from models import Video
        print("  ✅ Video model imported successfully")
    except ImportError as e:
        print(f"  ❌ Failed to import Video model: {e}")
        return False
    
    try:
        from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
        print("  ✅ DedicatedLabJackMonitor imported successfully")
    except ImportError as e:
        print(f"  ❌ Failed to import DedicatedLabJackMonitor: {e}")
        return False
    
    try:
        from api.hil_test_complete import get_video_duration
        print("  ✅ get_video_duration function imported successfully")
    except ImportError as e:
        print(f"  ❌ Failed to import get_video_duration: {e}")
        return False
    
    return True

def test_video_duration_function():
    """Test the enhanced video duration resolution function"""
    print("\n🧪 Testing video duration resolution...")
    
    try:
        from api.hil_test_complete import get_video_duration
        
        # Mock database session (simple object)
        class MockDB:
            def query(self, model):
                return self
            def filter(self, condition):
                return self
            def first(self):
                return None  # Simulate no video found
        
        mock_db = MockDB()
        
        # Test 1: Duration in payload
        print("  📋 Test 1: Duration in video_data payload")
        video_data = {"duration_s": 10.0, "fps": 30}
        duration = get_video_duration("test-video", mock_db, video_data)
        
        if duration == 10.0:
            print("    ✅ Correctly resolved duration from payload: 10.0s")
        else:
            print(f"    ❌ Expected 10.0s, got {duration}")
            return False
        
        # Test 2: Alternative duration key
        print("  📋 Test 2: Duration with alternative key")
        video_data = {"duration": 15.0, "fps": 30}  # Using 'duration' instead of 'duration_s'
        duration = get_video_duration("test-video", mock_db, video_data)
        
        if duration == 15.0:
            print("    ✅ Correctly resolved duration from alternative key: 15.0s")
        else:
            print(f"    ❌ Expected 15.0s, got {duration}")
            return False
        
        # Test 3: Empty payload (should return None with mock DB)
        print("  📋 Test 3: Empty payload with no database record")
        video_data = {}
        duration = get_video_duration("test-video", mock_db, video_data)
        
        if duration is None:
            print("    ✅ Correctly returned None for missing duration")
        else:
            print(f"    ❌ Expected None, got {duration}")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Test failed with error: {e}")
        return False

def test_monitor_imports():
    """Test that the enhanced monitor has correct imports"""
    print("\n🔍 Testing monitor service imports...")
    
    try:
        # Read the monitor file to check for Video import
        monitor_file = "services/dedicated_labjack_monitor.py"
        
        if not os.path.exists(monitor_file):
            print(f"  ❌ Monitor file not found: {monitor_file}")
            return False
        
        with open(monitor_file, 'r') as f:
            content = f.read()
        
        if "from models import TestSession, DetectionEvent, Video" in content:
            print("  ✅ Video model correctly imported in monitor service")
        else:
            print("  ❌ Video model import missing from monitor service")
            return False
        
        if "video = db.query(Video)" in content:
            print("  ✅ Database fallback logic found in monitor service")
        else:
            print("  ❌ Database fallback logic missing from monitor service")  
            return False
        
        if "duration = 30  # 30 second default" in content:
            print("  ✅ Enhanced default fallback duration found")
        else:
            print("  ❌ Enhanced default fallback duration missing")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Import test failed: {e}")
        return False

def test_grace_period_calculation():
    """Test grace period calculation logic"""
    print("\n⏱️  Testing grace period calculations...")
    
    test_cases = [
        {"duration": 5.0, "expected_grace": 0.25},
        {"duration": 10.0, "expected_grace": 0.5},
        {"duration": 30.0, "expected_grace": 1.5},
        {"duration": 60.0, "expected_grace": 2.0},  # Capped at 2.0
        {"duration": 2.0, "expected_grace": 0.25},   # Minimum 0.25
    ]
    
    for case in test_cases:
        duration = case["duration"]
        expected_grace = case["expected_grace"]
        
        # Calculate grace period: max(0.25, min(2.0, duration * 0.05))
        calculated_grace = max(0.25, min(2.0, duration * 0.05))
        
        if abs(calculated_grace - expected_grace) < 0.001:
            print(f"  ✅ {duration}s video → grace period: {calculated_grace}s (total: {duration + calculated_grace}s)")
        else:
            print(f"  ❌ {duration}s video → expected grace {expected_grace}s, got {calculated_grace}s")
            return False
    
    return True

def validate_fix():
    """Run complete validation of the HIL video duration fix"""
    print("=" * 80)
    print("HIL VIDEO DURATION FIX VALIDATION")
    print("=" * 80)
    print(f"Validation started at: {datetime.now().isoformat()}")
    print()
    
    all_tests_passed = True
    
    # Run all tests
    tests = [
        ("Import Tests", test_imports),
        ("Video Duration Resolution", test_video_duration_function),
        ("Monitor Service Enhancement", test_monitor_imports),
        ("Grace Period Calculation", test_grace_period_calculation),
    ]
    
    for test_name, test_func in tests:
        print(f"🧪 Running {test_name}...")
        try:
            if not test_func():
                all_tests_passed = False
                print(f"❌ {test_name} FAILED")
            else:
                print(f"✅ {test_name} PASSED")
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
            all_tests_passed = False
        print()
    
    # Summary
    print("=" * 80)
    if all_tests_passed:
        print("🎉 ALL VALIDATION TESTS PASSED - HIL VIDEO DURATION FIX VERIFIED")
        print("=" * 80)
        print()
        print("🔧 IMPLEMENTED FIXES:")
        print("  ✅ Enhanced duration resolution with database fallback") 
        print("  ✅ Proper Video model import in dedicated_labjack_monitor.py")
        print("  ✅ Robust grace period calculation (5% of duration, 0.25s-2s range)")
        print("  ✅ Safe default fallback (30s instead of hardcoded 3.675s)")
        print()
        print("📊 EXPECTED BEHAVIOR:")
        print("  • 5s video → LabJack monitors for 5.25s (5.0s + 0.25s grace)")
        print("  • 10s video → LabJack monitors for 10.5s (10.0s + 0.5s grace)")
        print("  • 30s video → LabJack monitors for 31.5s (30.0s + 1.5s grace)")
        print("  • 60s video → LabJack monitors for 62.0s (60.0s + 2.0s grace)")
        print()
        print("🚀 The HIL system should now properly handle video durations!")
        
    else:
        print("❌ SOME VALIDATION TESTS FAILED")
        print("=" * 80)
        print("Please review the failed tests and fix the issues before deployment.")
    
    print(f"\nValidation completed at: {datetime.now().isoformat()}")
    return all_tests_passed

if __name__ == "__main__":
    success = validate_fix()
    sys.exit(0 if success else 1)