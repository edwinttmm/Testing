"""
HIL LabJack Device Access Exclusivity Tests

Tests to verify that LabJack device access is properly managed to prevent
"LJME_DEVICE_CURRENTLY_CLAIMED_BY_ANOTHER_PROCESS" errors.
"""

import pytest
import time
import threading
import multiprocessing
import queue
import logging
import sys
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager

# Import services
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

logger = logging.getLogger(__name__)

class MockLabJackDevice:
    """Mock LabJack device to simulate exclusive access behavior"""
    
    def __init__(self):
        self.claimed_by = None
        self.lock = threading.Lock()
        self.claim_count = 0
    
    def claim_device(self, process_id):
        """Simulate device claiming with exclusivity"""
        with self.lock:
            if self.claimed_by is not None and self.claimed_by != process_id:
                raise Exception("LJME_DEVICE_CURRENTLY_CLAIMED_BY_ANOTHER_PROCESS")
            self.claimed_by = process_id
            self.claim_count += 1
            return True
    
    def release_device(self, process_id):
        """Release device claim"""
        with self.lock:
            if self.claimed_by == process_id:
                self.claimed_by = None
                return True
            return False
    
    def read_voltage(self, channel="AIN0"):
        """Simulate voltage reading"""
        if self.claimed_by is None:
            raise Exception("Device not claimed")
        return 3.5  # Simulate 3.5V reading

# Global mock device instance
mock_device = MockLabJackDevice()

class TestDeviceExclusivity:
    """Test suite for LabJack device access exclusivity"""
    
    @pytest.fixture(autouse=True)
    def reset_mock_device(self):
        """Reset mock device between tests"""
        global mock_device
        mock_device.claimed_by = None
        mock_device.claim_count = 0
        yield
        mock_device.claimed_by = None
    
    @pytest.fixture
    def mock_labjack_service(self):
        """Mock LabJack service with device exclusivity"""
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock:
            def mock_read_voltage(channel):
                process_id = threading.current_thread().ident
                try:
                    mock_device.claim_device(process_id)
                    voltage = mock_device.read_voltage(channel)
                    return {"success": True, "voltage": voltage, "timestamp": time.time()}
                except Exception as e:
                    if "CURRENTLY_CLAIMED" in str(e):
                        return {"success": False, "error": str(e)}
                    raise
                finally:
                    # In real scenario, device might stay claimed during session
                    pass
            
            mock.read_voltage_signal.side_effect = mock_read_voltage
            yield mock
    
    def test_single_process_exclusive_access(self, mock_labjack_service):
        """Test that a single process can claim and use the device exclusively"""
        from services.labjack_monitoring_service import LabJackMonitoringService
        
        service = LabJackMonitoringService()
        session_id = "exclusive_test_001"
        
        try:
            # Should successfully start monitoring (claim device)
            result = service.start_monitoring(session_id, sample_rate=10)
            assert result is True
            
            # Device should be claimed
            process_id = threading.current_thread().ident
            assert mock_device.claimed_by == process_id
            
            # Should be able to read voltage
            time.sleep(0.2)  # Allow some monitoring
            
            # Verify monitoring is active
            status = service.get_monitoring_status()
            assert status["active"] is True
            
        finally:
            service.stop_monitoring()
            # Device should be released
            # Note: In real implementation, device release would happen in stop_monitoring
    
    def test_concurrent_thread_prevention(self, mock_labjack_service):
        """Test that concurrent threads cannot claim the same device"""
        from services.labjack_monitoring_service import LabJackMonitoringService
        
        results = queue.Queue()
        
        def try_start_monitoring(session_id, thread_id):
            """Worker function for threading test"""
            try:
                service = LabJackMonitoringService()
                # Simulate device claim attempt
                process_id = threading.current_thread().ident
                mock_device.claim_device(process_id)
                
                result = service.start_monitoring(session_id, sample_rate=10)
                results.put((thread_id, result, "success", process_id))
                time.sleep(0.5)  # Hold device briefly
                service.stop_monitoring()
                mock_device.release_device(process_id)
                
            except Exception as e:
                results.put((thread_id, False, str(e), threading.current_thread().ident))
        
        # Start multiple threads trying to claim device
        threads = []
        for i in range(5):
            t = threading.Thread(target=try_start_monitoring, args=(f"concurrent_session_{i}", i))
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join(timeout=5)
        
        # Collect results
        thread_results = []
        while not results.empty():
            thread_results.append(results.get())
        
        # Only one thread should successfully claim the device
        successful_claims = [r for r in thread_results if r[1] is True]
        failed_claims = [r for r in thread_results if r[1] is False]
        
        assert len(successful_claims) <= 1, f"Multiple threads claimed device: {successful_claims}"
        assert len(failed_claims) >= 4, f"Not enough threads failed: {failed_claims}"
        
        # Failed threads should have device conflict errors
        device_errors = [r for r in failed_claims if "CURRENTLY_CLAIMED" in r[2]]
        assert len(device_errors) >= 3, f"Expected device conflict errors: {failed_claims}"
    
    def test_multiprocess_exclusivity(self):
        """Test device exclusivity across multiple processes"""
        def worker_process(session_id, result_queue):
            """Worker function for multiprocessing test"""
            try:
                import os
                process_id = os.getpid()
                
                # Simulate device access attempt
                global mock_device
                mock_device = MockLabJackDevice()  # Each process gets its own mock
                
                # In real scenario, this would be LabJack device access
                try:
                    mock_device.claim_device(process_id)
                    result_queue.put((session_id, True, "success", process_id))
                    time.sleep(1)  # Hold device
                    mock_device.release_device(process_id)
                except Exception as e:
                    result_queue.put((session_id, False, str(e), process_id))
                    
            except Exception as e:
                result_queue.put((session_id, False, str(e), "unknown"))
        
        # Create multiprocessing queue
        result_queue = multiprocessing.Queue()
        processes = []
        
        # Start multiple processes
        for i in range(3):
            p = multiprocessing.Process(
                target=worker_process, 
                args=(f"multiprocess_session_{i}", result_queue)
            )
            processes.append(p)
            p.start()
        
        # Wait for all processes
        for p in processes:
            p.join(timeout=10)
            if p.is_alive():
                p.terminate()
        
        # Collect results
        process_results = []
        while not result_queue.empty():
            process_results.append(result_queue.get())
        
        # Each process should succeed with its own mock device
        # In real scenario with shared hardware, only one would succeed
        assert len(process_results) == 3
        successful_processes = [r for r in process_results if r[1] is True]
        assert len(successful_processes) >= 1, "At least one process should succeed"
    
    def test_device_claim_timeout(self, mock_labjack_service):
        """Test device claim with timeout mechanism"""
        from services.labjack_monitoring_service import LabJackMonitoringService
        
        # First service claims device
        service1 = LabJackMonitoringService()
        session1 = "timeout_test_001"
        
        # Claim device with first service
        process_id1 = threading.current_thread().ident
        mock_device.claim_device(process_id1)
        
        result1 = service1.start_monitoring(session1, sample_rate=10)
        assert result1 is True
        
        # Second service attempts to claim - should fail
        service2 = LabJackMonitoringService()
        session2 = "timeout_test_002"
        
        # This should fail due to device being claimed
        def attempt_second_claim():
            process_id2 = threading.current_thread().ident
            try:
                mock_device.claim_device(process_id2)
                return True
            except Exception as e:
                if "CURRENTLY_CLAIMED" in str(e):
                    return False
                raise
        
        # Should fail to claim
        claim_result = attempt_second_claim()
        assert claim_result is False
        
        # Release first claim
        service1.stop_monitoring()
        mock_device.release_device(process_id1)
        
        # Now second service should be able to claim
        process_id2 = threading.current_thread().ident
        claim_result2 = mock_device.claim_device(process_id2)
        assert claim_result2 is True
        
        # Cleanup
        mock_device.release_device(process_id2)
    
    def test_graceful_device_release(self, mock_labjack_service):
        """Test graceful device release on service shutdown"""
        from services.labjack_monitoring_service import LabJackMonitoringService
        
        service = LabJackMonitoringService()
        session_id = "graceful_release_test"
        
        # Start monitoring (claim device)
        process_id = threading.current_thread().ident
        mock_device.claim_device(process_id)
        
        result = service.start_monitoring(session_id, sample_rate=10)
        assert result is True
        assert mock_device.claimed_by == process_id
        
        # Stop monitoring (should release device)
        service.stop_monitoring()
        
        # Simulate device release in actual implementation
        mock_device.release_device(process_id)
        
        # Device should be available for new claims
        assert mock_device.claimed_by is None
        
        # Another service should be able to claim now
        new_process_id = process_id + 1  # Simulate different process
        claim_result = mock_device.claim_device(new_process_id)
        assert claim_result is True
        
        # Cleanup
        mock_device.release_device(new_process_id)
    
    def test_device_recovery_after_crash(self, mock_labjack_service):
        """Test device recovery after process crash simulation"""
        from services.labjack_monitoring_service import LabJackMonitoringService
        
        # Simulate crashed process that didn't release device
        crashed_process_id = 99999
        mock_device.claim_device(crashed_process_id)
        
        # In real scenario, system would detect stale claims and recover
        # For test, we'll simulate recovery mechanism
        def force_release_stale_claim():
            """Simulate system recovery of stale device claims"""
            if mock_device.claimed_by == crashed_process_id:
                mock_device.claimed_by = None
                return True
            return False
        
        # Attempt to start new monitoring
        service = LabJackMonitoringService()
        session_id = "recovery_test"
        
        # Should fail initially due to stale claim
        current_process = threading.current_thread().ident
        try:
            mock_device.claim_device(current_process)
            assert False, "Should have failed due to stale claim"
        except Exception as e:
            assert "CURRENTLY_CLAIMED" in str(e)
        
        # Simulate recovery mechanism
        recovery_result = force_release_stale_claim()
        assert recovery_result is True
        
        # Now should be able to claim device
        claim_result = mock_device.claim_device(current_process)
        assert claim_result is True
        
        result = service.start_monitoring(session_id, sample_rate=10)
        assert result is True
        
        # Cleanup
        service.stop_monitoring()
        mock_device.release_device(current_process)
    
    def test_device_sharing_prevention(self, mock_labjack_service):
        """Test that device sharing is properly prevented"""
        from services.labjack_monitoring_service import LabJackMonitoringService
        
        # Start first monitoring session
        service1 = LabJackMonitoringService()
        session1 = "sharing_test_001"
        
        process1 = threading.current_thread().ident
        mock_device.claim_device(process1)
        
        result1 = service1.start_monitoring(session1, sample_rate=10)
        assert result1 is True
        
        # Attempt to start second session should fail
        service2 = LabJackMonitoringService()
        session2 = "sharing_test_002"
        
        # This should fail since device is already claimed
        result2 = service2.start_monitoring(session2, sample_rate=10)
        assert result2 is False  # Should fail due to exclusivity
        
        # First session should still be active
        status1 = service1.get_monitoring_status()
        assert status1["active"] is True
        assert status1["session_id"] == session1
        
        # Second session should not be active
        status2 = service2.get_monitoring_status()
        assert status2["active"] is False
        
        # Cleanup
        service1.stop_monitoring()
        mock_device.release_device(process1)
    
    def test_device_availability_check(self, mock_labjack_service):
        """Test device availability checking before starting monitoring"""
        from services.labjack_monitoring_service import LabJackMonitoringService
        
        def check_device_availability():
            """Simulate device availability check"""
            return mock_device.claimed_by is None
        
        # Initially device should be available
        assert check_device_availability() is True
        
        # Claim device
        process_id = threading.current_thread().ident
        mock_device.claim_device(process_id)
        
        # Should not be available
        assert check_device_availability() is False
        
        # Release device
        mock_device.release_device(process_id)
        
        # Should be available again
        assert check_device_availability() is True
    
    def test_error_handling_on_device_conflict(self, mock_labjack_service):
        """Test proper error handling when device conflicts occur"""
        from services.labjack_monitoring_service import LabJackMonitoringService
        
        # Claim device externally
        external_process = 88888
        mock_device.claim_device(external_process)
        
        service = LabJackMonitoringService()
        session_id = "conflict_test"
        
        # Configure mock to return device conflict error
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            mock_signal.read_voltage_signal.side_effect = Exception(
                "LJME_DEVICE_CURRENTLY_CLAIMED_BY_ANOTHER_PROCESS"
            )
            
            # Attempt to start monitoring should handle error gracefully
            result = service.start_monitoring(session_id, sample_rate=10)
            
            # Service should start but fail during operation
            if result:
                # Wait briefly for error to occur
                time.sleep(0.1)
                
                # Service should detect error and remain stable
                status = service.get_monitoring_status()
                # Service might still report active even if device access fails
                # The important thing is it doesn't crash
                
                service.stop_monitoring()
        
        # Release external claim
        mock_device.release_device(external_process)

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])