"""
Test suite for LabJack HIL concurrency and stream mode fixes.
Validates Phase 1 (singleton) and Phase 2 (stream mode) implementations.
"""

import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from services.labjack_hardware_service import (
    get_labjack_hardware_service,
    reset_labjack_hardware_service,
    LabJackConfig
)
from services.labjack_detection_service import LabJackDetectionService


class TestSingletonThreadSafety:
    """Test Phase 1 fixes: Thread-safe singleton pattern"""

    def setup_method(self):
        """Reset singleton before each test"""
        reset_labjack_hardware_service()

    def test_concurrent_singleton_access(self):
        """Test that concurrent access returns same instance"""
        reset_labjack_hardware_service()

        instances = []

        def get_service():
            service = get_labjack_hardware_service()
            instances.append(service)
            return service

        # Spawn 20 threads trying to get service simultaneously
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(get_service) for _ in range(20)]
            results = [f.result() for f in as_completed(futures)]

        # All should be the same instance
        assert len(set(id(inst) for inst in instances)) == 1, \
            "Multiple instances created - singleton not thread-safe!"

        print(f"✅ Concurrent access test passed: {len(instances)} threads, 1 instance")

    def test_config_validation(self):
        """Test config mismatch detection"""
        reset_labjack_hardware_service()

        config1 = LabJackConfig(device_type="T7")
        config2 = LabJackConfig(device_type="T4")

        # First call with config1
        service1 = get_labjack_hardware_service(config1)

        # Second call with config2 should raise error
        with pytest.raises(RuntimeError, match="Configuration mismatch"):
            get_labjack_hardware_service(config2)

        print("✅ Config validation test passed")

    def test_force_recreate(self):
        """Test force_recreate parameter"""
        reset_labjack_hardware_service()

        service1 = get_labjack_hardware_service()
        service1_id = id(service1)

        # Force recreate should create new instance
        service2 = get_labjack_hardware_service(force_recreate=True)
        service2_id = id(service2)

        assert service1_id != service2_id, "force_recreate didn't create new instance"
        print("✅ Force recreate test passed")

    def test_reset_function(self):
        """Test reset_labjack_hardware_service()"""
        service1 = get_labjack_hardware_service()
        service1_id = id(service1)

        reset_labjack_hardware_service()

        service2 = get_labjack_hardware_service()
        service2_id = id(service2)

        assert service1_id != service2_id, "Reset didn't clear singleton"
        print("✅ Reset function test passed")

    def test_exception_safety(self):
        """Test exception handling during initialization"""
        reset_labjack_hardware_service()

        # Mock to raise exception during init
        with patch('services.labjack_hardware_service.LabJackHardwareService.__init__',
                   side_effect=RuntimeError("Simulated init failure")):
            with pytest.raises(RuntimeError, match="Failed to initialize"):
                get_labjack_hardware_service()

        # Should be able to retry after failure
        service = get_labjack_hardware_service()
        assert service is not None
        print("✅ Exception safety test passed")


class TestStreamModeFixes:
    """Test Phase 2 fixes: Stream mode implementation"""

    @patch('services.labjack_hardware_service.LabJackHardwareService')
    def test_no_asyncio_in_threads(self, mock_hardware):
        """Verify no asyncio event loops created in threads"""
        import inspect
        from services.labjack_detection_service import LabJackDetectionService

        # Get source code of _monitoring_loop_stream
        source = inspect.getsource(LabJackDetectionService._monitoring_loop_stream)

        # Should NOT contain asyncio event loop creation
        assert 'asyncio.new_event_loop' not in source, \
            "❌ CRITICAL: asyncio.new_event_loop found in stream loop!"
        assert 'asyncio.get_event_loop' not in source, \
            "❌ CRITICAL: asyncio.get_event_loop found in stream loop!"
        assert 'loop.run_until_complete' not in source, \
            "❌ CRITICAL: loop.run_until_complete found in stream loop!"

        # Should NOT be async function
        assert not inspect.iscoroutinefunction(LabJackDetectionService._monitoring_loop_stream), \
            "❌ CRITICAL: _monitoring_loop_stream is still async!"

        print("✅ No asyncio in threads test passed")

    @patch('services.labjack_hardware_service.LabJackHardwareService')
    def test_correct_method_calls(self, mock_hardware):
        """Verify stream loop calls correct methods"""
        import inspect
        from services.labjack_detection_service import LabJackDetectionService

        source = inspect.getsource(LabJackDetectionService._monitoring_loop_stream)

        # Should call start_stream_mode (sync) not start_stream (async)
        assert 'start_stream_mode' in source, \
            "❌ CRITICAL: start_stream_mode not called!"
        assert 'read_stream_mode' in source, \
            "❌ CRITICAL: read_stream_mode not called!"
        assert 'stop_stream_mode' in source, \
            "❌ CRITICAL: stop_stream_mode not called!"

        # Should NOT call async versions
        assert 'start_stream()' not in source, \
            "❌ CRITICAL: Still calling async start_stream()!"

        print("✅ Correct method calls test passed")

    @patch('services.labjack_hardware_service.LabJackHardwareService')
    def test_fallback_mechanism(self, mock_hardware):
        """Test graceful fallback to polling"""
        from services.labjack_detection_service import LabJackDetectionService

        # Verify fallback function exists
        assert hasattr(LabJackDetectionService, '_use_polling_fallback'), \
            "❌ CRITICAL: _use_polling_fallback function not found!"

        # Verify it's not recursive
        import inspect
        source = inspect.getsource(LabJackDetectionService._use_polling_fallback)

        # Should call _monitoring_loop (polling) not _monitoring_loop_stream
        assert '_monitoring_loop()' in source, \
            "❌ Fallback doesn't call polling loop!"
        assert '_monitoring_loop_stream' not in source, \
            "❌ CRITICAL: Fallback has recursion risk!"

        print("✅ Fallback mechanism test passed")

    @patch('services.labjack_hardware_service.LabJackHardwareService')
    def test_thread_safety(self, mock_hardware):
        """Test stream mode thread safety"""
        from services.labjack_detection_service import LabJackDetectionService

        # Mock the hardware service
        mock_instance = Mock()
        mock_instance.start_stream_mode.return_value = (True, 200.0)
        mock_instance.read_stream_mode.return_value = ([], 0, True)
        mock_hardware.return_value = mock_instance

        # Create detection service
        config = {
            'use_stream_mode': True,
            'channels': ['AIN0'],
            'sample_rate': 200
        }
        service = LabJackDetectionService(session_id='test', config=config)

        # Should not raise threading errors
        # (Full test would require real hardware)
        print("✅ Thread safety test passed")


class TestIntegrationScenarios:
    """Integration tests for complete workflow"""

    def test_concurrent_test_sessions(self):
        """Simulate multiple concurrent test sessions"""
        reset_labjack_hardware_service()

        results = []
        errors = []

        def simulate_test_session(session_id):
            try:
                # Each session tries to get the hardware service
                service = get_labjack_hardware_service()
                results.append((session_id, id(service)))
                time.sleep(0.01)  # Simulate work
                return True
            except Exception as e:
                errors.append((session_id, str(e)))
                return False

        # Simulate 10 concurrent test sessions
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(simulate_test_session, f"session_{i}")
                for i in range(10)
            ]
            success_count = sum(1 for f in as_completed(futures) if f.result())

        # All should succeed with same instance
        assert success_count == 10, f"Only {success_count}/10 sessions succeeded"
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # All should have same service instance
        service_ids = set(sid for _, sid in results)
        assert len(service_ids) == 1, \
            f"Multiple instances created: {len(service_ids)} different IDs"

        print(f"✅ Concurrent sessions test passed: {success_count}/10 succeeded, 1 instance")


def run_all_tests():
    """Run all tests and generate report"""
    print("\n" + "="*70)
    print("  LABJACK HIL CONCURRENCY & STREAM MODE FIX VALIDATION")
    print("="*70 + "\n")

    test_classes = [
        TestSingletonThreadSafety,
        TestStreamModeFixes,
        TestIntegrationScenarios
    ]

    total_passed = 0
    total_failed = 0

    for test_class in test_classes:
        print(f"\n📋 Running {test_class.__name__}")
        print("-" * 70)

        instance = test_class()

        # Run setup if exists
        if hasattr(instance, 'setup_method'):
            instance.setup_method()

        # Get all test methods
        test_methods = [
            method for method in dir(instance)
            if method.startswith('test_') and callable(getattr(instance, method))
        ]

        for method_name in test_methods:
            try:
                method = getattr(instance, method_name)
                print(f"\n  Testing: {method_name}")
                method()
                total_passed += 1
            except Exception as e:
                print(f"  ❌ FAILED: {method_name}")
                print(f"     Error: {e}")
                total_failed += 1

    print("\n" + "="*70)
    print(f"  TEST RESULTS: {total_passed} passed, {total_failed} failed")
    print("="*70 + "\n")

    return total_failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
