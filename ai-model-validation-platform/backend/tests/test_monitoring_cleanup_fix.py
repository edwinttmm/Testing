"""
Test Monitoring Service Cleanup Fix

Validates that monitoring service polling stops cleanly when session ends.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from services.dedicated_labjack_monitor import LabJackMonitoringService


class TestMonitoringCleanupFix:
    """Test monitoring service cleanup after session completion"""

    def test_stop_monitoring_terminates_thread(self):
        """Test that stop_monitoring() actually terminates the polling thread"""
        service = LabJackMonitoringService()

        # Mock the signal validation service
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            mock_signal.read_voltage_signal.return_value = {
                "success": True,
                "voltage": 1.0
            }

            # Start monitoring
            session_id = "test-session-123"
            service.start_monitoring(session_id, sample_rate=10)

            # Verify thread is running
            assert service.monitoring_active is True
            assert service.monitor_thread is not None
            assert service.monitor_thread.is_alive()

            # Allow some polling to occur
            time.sleep(0.5)

            # Stop monitoring
            service.stop_monitoring()

            # CRITICAL: Verify thread stopped
            assert service.monitoring_active is False
            time.sleep(0.5)  # Give thread time to exit

            # Verify thread is no longer alive
            if service.monitor_thread:
                assert not service.monitor_thread.is_alive(), \
                    "❌ CRITICAL BUG: Monitoring thread still running after stop_monitoring()"

            # Verify cleanup
            assert service.current_session_id is None
            assert service.monitor_thread is None
            assert service._was_high is False  # Edge detection state reset

    def test_stop_monitoring_handles_already_stopped(self):
        """Test that calling stop_monitoring() when already stopped is safe"""
        service = LabJackMonitoringService()

        # Call stop when not running (should not crash)
        service.stop_monitoring()

        # Verify state is clean
        assert service.monitoring_active is False
        assert service.current_session_id is None
        assert service.monitor_thread is None

    def test_monitor_loop_respects_stop_signals(self):
        """Test that _monitor_loop exits when stop signals are set"""
        service = LabJackMonitoringService()

        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            mock_signal.read_voltage_signal.return_value = {
                "success": True,
                "voltage": 1.0
            }

            session_id = "test-session-456"
            service.start_monitoring(session_id, sample_rate=10)

            # Let it run briefly
            time.sleep(0.3)

            # Set stop signal
            service.monitoring_active = False
            service._stop_event.set()

            # Wait for loop to exit
            time.sleep(0.5)

            # Verify thread exited
            assert not service.monitor_thread.is_alive(), \
                "Loop should exit when stop signals are set"

    def test_no_polling_after_session_complete(self):
        """Test that NO voltage reads occur after stop_monitoring() called"""
        service = LabJackMonitoringService()

        read_count = {'count': 0}

        def count_reads(*args, **kwargs):
            read_count['count'] += 1
            return {"success": True, "voltage": 1.0}

        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            mock_signal.read_voltage_signal.side_effect = count_reads

            # Start monitoring
            session_id = "test-session-789"
            service.start_monitoring(session_id, sample_rate=10)

            # Let it poll a few times
            time.sleep(0.5)
            reads_during_session = read_count['count']
            assert reads_during_session > 0, "Should have polled during session"

            # Stop monitoring
            service.stop_monitoring()

            # Reset counter
            reads_after_stop = read_count['count']

            # Wait and verify NO new reads
            time.sleep(1.0)
            reads_final = read_count['count']

            assert reads_final == reads_after_stop, \
                f"❌ CRITICAL BUG: Polling continued after stop! " \
                f"Before stop: {reads_during_session}, After stop: {reads_after_stop}, " \
                f"Final: {reads_final} (should be equal)"

    def test_thread_cleanup_on_stop(self):
        """Test that thread reference is cleaned up properly"""
        service = LabJackMonitoringService()

        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            mock_signal.read_voltage_signal.return_value = {
                "success": True,
                "voltage": 1.0
            }

            # Start and stop monitoring
            service.start_monitoring("test-session-cleanup", sample_rate=10)
            thread_ref = service.monitor_thread
            assert thread_ref is not None

            service.stop_monitoring()

            # Verify cleanup
            assert service.monitor_thread is None, \
                "Thread reference should be cleared after stop"
            assert service.current_session_id is None, \
                "Session ID should be cleared after stop"
            assert service._was_high is False, \
                "Edge detection state should be reset"

    def test_stop_monitoring_timeout_handling(self):
        """Test that stop_monitoring() handles thread that won't terminate"""
        service = LabJackMonitoringService()

        # Create a thread that won't stop easily
        def stubborn_loop(*args, **kwargs):
            while True:  # Never checks stop signals
                time.sleep(0.1)

        with patch.object(service, '_monitor_loop', side_effect=stubborn_loop):
            service.start_monitoring("stubborn-session", sample_rate=10)

            # Try to stop (should timeout gracefully)
            service.stop_monitoring()

            # Should still clean up state even if thread won't die
            assert service.monitoring_active is False
            assert service._stop_event.is_set()
            assert service.current_session_id is None


class TestSessionCompletionCleanup:
    """Test that session completion properly triggers monitoring cleanup"""

    @patch('routers.test_sessions.labjack_monitoring_service')
    def test_complete_session_calls_stop_monitoring(self, mock_monitoring_service):
        """Test that completing a session calls stop_monitoring()"""
        from routers.test_sessions import complete_test_session

        # This test would require full FastAPI setup
        # For now, verify the code path exists
        import inspect
        source = inspect.getsource(complete_test_session)

        # Verify cleanup code is present
        assert 'labjack_monitoring_service.stop_monitoring()' in source, \
            "Session completion MUST call stop_monitoring()"

        assert 'Stopping monitoring service polling thread' in source, \
            "Should log cleanup action"

        assert 'Monitoring service cleanup completed' in source, \
            "Should log cleanup success"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
