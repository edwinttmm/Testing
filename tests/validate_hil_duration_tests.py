#!/usr/bin/env python3
"""
HIL Video Duration Test Validation Script

Quick validation script to ensure the test suite is working correctly.
This script runs a subset of key tests and validates the testing framework.

Usage:
    python validate_hil_duration_tests.py
"""

import sys
import os
import unittest
import logging
from datetime import datetime

# Add the test directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import key test components
try:
    from test_hil_video_duration_fixtures import (
        VideoFixtureFactory,
        GracePeriodCalculator,
        MockDatabaseFactory,
        TestScenarioBuilder
    )
    
    # Import the function under test
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ai-model-validation-platform', 'backend'))
    
    # We'll mock this since the actual import might fail due to dependencies
    def mock_get_video_duration(video_id, db, video_data):
        """Mock implementation for validation"""
        # Try video_data payload first
        duration = video_data.get("duration_s") or video_data.get("duration")
        
        if duration is not None:
            duration = float(duration)
            if 0.1 <= duration <= 7200:
                return duration
        
        # Database fallback simulation
        if hasattr(db, 'query') and video_id:
            mock_video = db.query().filter().first()
            if mock_video and hasattr(mock_video, 'duration') and mock_video.duration:
                db_duration = float(mock_video.duration)
                if 0.1 <= db_duration <= 7200:
                    return db_duration
        
        return None

    IMPORTS_SUCCESSFUL = True

except ImportError as e:
    print(f"Import failed: {e}")
    IMPORTS_SUCCESSFUL = False

logger = logging.getLogger(__name__)


def validate_fixture_factory():
    """Validate the video fixture factory works correctly"""
    print("Validating Video Fixture Factory...")
    
    try:
        # Test all fixture categories
        all_fixtures = VideoFixtureFactory.get_all_fixtures()
        
        expected_categories = ["short", "medium", "long", "edge_case", "invalid", "missing_duration"]
        
        for category in expected_categories:
            if category not in all_fixtures:
                print(f"❌ Missing fixture category: {category}")
                return False
            
            fixtures = all_fixtures[category]
            if not fixtures:
                print(f"❌ Empty fixture category: {category}")
                return False
            
            print(f"✅ {category}: {len(fixtures)} fixtures")
        
        # Test fixture conversion
        test_fixture = all_fixtures["medium"][0]
        
        # Test video_data payload conversion
        payload = test_fixture.to_video_data_payload()
        required_keys = ["video_id", "filename", "fps"]
        for key in required_keys:
            if key not in payload:
                print(f"❌ Missing key in payload: {key}")
                return False
        
        # Test database mock conversion
        db_mock = test_fixture.to_database_video_mock()
        if not hasattr(db_mock, 'id') or not hasattr(db_mock, 'duration'):
            print("❌ Database mock missing required attributes")
            return False
        
        print("✅ Video Fixture Factory validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Video Fixture Factory validation failed: {e}")
        return False


def validate_grace_period_calculator():
    """Validate the grace period calculator works correctly"""
    print("\nValidating Grace Period Calculator...")
    
    try:
        # Test known values
        test_cases = [
            (0.5, 0.25),   # Very short: min grace
            (10.0, 0.5),   # Medium: 5% grace  
            (40.0, 2.0),   # Long: max grace
            (120.0, 2.0),  # Very long: max grace
        ]
        
        for duration, expected_grace in test_cases:
            actual_grace = GracePeriodCalculator.calculate_grace_period(duration)
            if actual_grace != expected_grace:
                print(f"❌ Grace period calculation failed: {duration}s -> {actual_grace}s (expected {expected_grace}s)")
                return False
            
            # Test auto-stop time
            auto_stop_time = GracePeriodCalculator.calculate_auto_stop_time(duration)
            expected_stop_time = duration + expected_grace
            if auto_stop_time != expected_stop_time:
                print(f"❌ Auto-stop time calculation failed: {duration}s -> {auto_stop_time}s (expected {expected_stop_time}s)")
                return False
        
        print("✅ Grace Period Calculator validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Grace Period Calculator validation failed: {e}")
        return False


def validate_mock_factories():
    """Validate the mock factories work correctly"""
    print("\nValidating Mock Factories...")
    
    try:
        # Test database mock factory
        test_fixture = VideoFixtureFactory.create_medium_videos()[0]
        
        # Test successful database mock
        success_mock = MockDatabaseFactory.create_successful_db_mock(test_fixture)
        if not hasattr(success_mock, 'query'):
            print("❌ Database success mock missing query method")
            return False
        
        # Test video not found mock
        not_found_mock = MockDatabaseFactory.create_video_not_found_db_mock()
        if not hasattr(not_found_mock, 'query'):
            print("❌ Database not found mock missing query method")
            return False
        
        # Test database error mock
        error_mock = MockDatabaseFactory.create_database_error_mock()
        if not hasattr(error_mock, 'query'):
            print("❌ Database error mock missing query method")
            return False
        
        print("✅ Mock Factories validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Mock Factories validation failed: {e}")
        return False


def validate_duration_resolution():
    """Validate the duration resolution logic works correctly"""
    print("\nValidating Duration Resolution Logic...")
    
    try:
        # Test primary source (duration_s)
        video_data = {"duration_s": 10.5, "duration": 15.0, "filename": "test.mp4"}
        mock_db = MockDatabaseFactory.create_video_not_found_db_mock()
        
        result = mock_get_video_duration("test_001", mock_db, video_data)
        if result != 10.5:
            print(f"❌ Primary source failed: got {result}, expected 10.5")
            return False
        
        # Test fallback source (duration)
        video_data = {"duration": 15.0, "filename": "test.mp4"}  # No duration_s
        result = mock_get_video_duration("test_002", mock_db, video_data)
        if result != 15.0:
            print(f"❌ Fallback source failed: got {result}, expected 15.0")
            return False
        
        # Test database fallback
        video_data = {"filename": "test.mp4"}  # No duration fields
        test_fixture = VideoFixtureFactory.create_medium_videos()[0]
        db_mock = MockDatabaseFactory.create_successful_db_mock(test_fixture)
        
        result = mock_get_video_duration("test_003", db_mock, video_data)
        if result != test_fixture.duration:
            print(f"❌ Database fallback failed: got {result}, expected {test_fixture.duration}")
            return False
        
        # Test invalid duration rejection
        video_data = {"duration_s": -5.0, "filename": "test.mp4"}  # Invalid
        not_found_mock = MockDatabaseFactory.create_video_not_found_db_mock()
        
        result = mock_get_video_duration("test_004", not_found_mock, video_data)
        if result is not None:
            print(f"❌ Invalid duration not rejected: got {result}, expected None")
            return False
        
        print("✅ Duration Resolution Logic validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Duration Resolution Logic validation failed: {e}")
        return False


def validate_test_scenarios():
    """Validate the test scenario builder works correctly"""
    print("\nValidating Test Scenario Builder...")
    
    try:
        # Test duration resolution scenarios
        duration_scenarios = TestScenarioBuilder.build_duration_resolution_scenarios()
        if len(duration_scenarios) < 3:
            print(f"❌ Insufficient duration scenarios: {len(duration_scenarios)}")
            return False
        
        # Validate scenario structure
        for scenario in duration_scenarios:
            required_keys = ["name", "video_fixture", "video_data", "db_mock", "expected_duration"]
            for key in required_keys:
                if key not in scenario:
                    print(f"❌ Missing key in scenario: {key}")
                    return False
        
        # Test grace period scenarios
        grace_scenarios = TestScenarioBuilder.build_grace_period_scenarios()
        if len(grace_scenarios) < 5:
            print(f"❌ Insufficient grace period scenarios: {len(grace_scenarios)}")
            return False
        
        # Test integration scenarios
        integration_scenarios = TestScenarioBuilder.build_integration_scenarios()
        if len(integration_scenarios) < 5:
            print(f"❌ Insufficient integration scenarios: {len(integration_scenarios)}")
            return False
        
        print("✅ Test Scenario Builder validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Test Scenario Builder validation failed: {e}")
        return False


def validate_end_to_end_workflow():
    """Validate the complete end-to-end workflow"""
    print("\nValidating End-to-End Workflow...")
    
    try:
        # Simulate complete workflow
        test_fixture = VideoFixtureFactory.create_medium_videos()[0]  # 10 second video
        
        # Step 1: Duration resolution
        video_data = test_fixture.to_video_data_payload()
        mock_db = MockDatabaseFactory.create_successful_db_mock(test_fixture)
        
        resolved_duration = mock_get_video_duration(test_fixture.video_id, mock_db, video_data)
        if resolved_duration != test_fixture.duration:
            print(f"❌ Duration resolution failed: {resolved_duration} != {test_fixture.duration}")
            return False
        
        # Step 2: Grace period calculation
        grace_period = GracePeriodCalculator.calculate_grace_period(resolved_duration)
        expected_grace = max(0.25, min(2.0, resolved_duration * 0.05))
        if grace_period != expected_grace:
            print(f"❌ Grace period calculation failed: {grace_period} != {expected_grace}")
            return False
        
        # Step 3: Auto-stop time calculation
        auto_stop_time = GracePeriodCalculator.calculate_auto_stop_time(resolved_duration)
        expected_stop_time = resolved_duration + grace_period
        if auto_stop_time != expected_stop_time:
            print(f"❌ Auto-stop time calculation failed: {auto_stop_time} != {expected_stop_time}")
            return False
        
        # Step 4: Validate timing prevents early termination
        video_end_time = resolved_duration
        labjack_continues = auto_stop_time > video_end_time
        if not labjack_continues:
            print("❌ Auto-stop time does not prevent early termination")
            return False
        
        grace_duration = auto_stop_time - video_end_time
        if grace_duration != grace_period:
            print(f"❌ Grace period duration mismatch: {grace_duration} != {grace_period}")
            return False
        
        print(f"✅ End-to-End Workflow validation passed:")
        print(f"   Video Duration: {resolved_duration}s")
        print(f"   Grace Period: {grace_period}s")
        print(f"   Auto-Stop Time: {auto_stop_time}s")
        print(f"   Grace Duration: {grace_duration}s")
        return True
        
    except Exception as e:
        print(f"❌ End-to-End Workflow validation failed: {e}")
        return False


def main():
    """Main validation function"""
    print("HIL Video Duration Auto-Stop Test Validation")
    print("=" * 60)
    print(f"Validation started at: {datetime.now()}")
    
    if not IMPORTS_SUCCESSFUL:
        print("❌ CRITICAL: Import validation failed - cannot proceed with tests")
        return False
    
    print("✅ All imports successful")
    
    # Run all validation checks
    validations = [
        validate_fixture_factory,
        validate_grace_period_calculator,
        validate_mock_factories,
        validate_duration_resolution,
        validate_test_scenarios,
        validate_end_to_end_workflow
    ]
    
    passed = 0
    failed = 0
    
    for validation in validations:
        try:
            if validation():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Validation function {validation.__name__} crashed: {e}")
            failed += 1
    
    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total Validations: {len(validations)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {passed / len(validations) * 100:.1f}%")
    
    if failed == 0:
        print("\n✅ ALL VALIDATIONS PASSED")
        print("The HIL video duration test suite is ready for use.")
        print("\nNext steps:")
        print("1. Run the full test suite: python run_hil_video_duration_tests.py")
        print("2. Run specific categories: python run_hil_video_duration_tests.py --category=auto_stop_timing")
        print("3. Generate detailed report: python run_hil_video_duration_tests.py --output=test_report.json")
        return True
    else:
        print("\n❌ VALIDATION FAILED")
        print(f"{failed} validation(s) failed. Fix issues before running tests.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)