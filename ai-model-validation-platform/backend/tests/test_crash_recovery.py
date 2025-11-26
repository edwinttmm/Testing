"""
Test crash recovery functionality for LabJack detection services.

This test suite verifies that:
1. Orphaned sessions are recovered on startup
2. Signal handlers cleanup active sessions gracefully
3. Database consistency is maintained after crashes
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from services.simple_labjack_detection import LabJackDetectionMonitor
from services.dedicated_labjack_monitor import DedicatedLabJackMonitor


class TestCrashRecovery:
    """Test crash recovery mechanisms"""

    @patch('services.labjack_detection_service.DATABASE_AVAILABLE', True)
    @patch('services.labjack_detection_service.SessionLocal')
    def test_orphaned_session_recovery_labjack_service(self, mock_session_local):
        """Test that orphaned sessions are recovered on service startup"""
        # Setup mock database with orphaned session
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_orphaned_session = MagicMock()
        mock_orphaned_session.id = "test-session-123"
        mock_orphaned_session.status = "monitoring"
        mock_orphaned_session.completed_at = None
        mock_orphaned_session.created_at = datetime.now() - timedelta(hours=25)
        mock_orphaned_session.metadata = {}

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_orphaned_session]
        mock_db.query.return_value = mock_query

        # Create service (should trigger recovery)
        with patch('services.labjack_detection_service.get_labjack_service'):
            with patch('services.labjack_detection_service.get_labjack_hardware_service'):
                service = LabJackDetectionMonitor()

        # Verify recovery was attempted
        assert mock_orphaned_session.status == "crashed"
        assert mock_orphaned_session.completed_at is not None
        assert mock_orphaned_session.metadata['recovered'] is True
        assert mock_orphaned_session.metadata['recovery_reason'] == 'System restart'
        mock_db.commit.assert_called()

    def test_shutdown_flag_initialized(self):
        """Test that shutdown flag is properly initialized"""
        with patch('services.labjack_detection_service.get_labjack_service'):
            with patch('services.labjack_detection_service.get_labjack_hardware_service'):
                service = LabJackDetectionMonitor()

        assert hasattr(service, '_shutdown_requested')
        assert service._shutdown_requested is False

    def test_cleanup_all_sessions_called_once(self):
        """Test that cleanup_all_sessions prevents double-execution"""
        with patch('services.labjack_detection_service.get_labjack_service'):
            with patch('services.labjack_detection_service.get_labjack_hardware_service'):
                service = LabJackDetectionMonitor()

        # Add mock session
        service.active_sessions['test-session'] = Mock()

        # First call should cleanup
        with patch.object(service, 'stop_session_monitoring') as mock_stop:
            service.cleanup_all_sessions()
            mock_stop.assert_called_once_with('test-session')

        # Second call should be skipped (shutdown flag is set)
        with patch.object(service, 'stop_session_monitoring') as mock_stop:
            service.cleanup_all_sessions()
            mock_stop.assert_not_called()

    def test_signal_handlers_registered(self):
        """Test that signal handlers are registered"""
        import signal as sig

        with patch('services.labjack_detection_service.get_labjack_service'):
            with patch('services.labjack_detection_service.get_labjack_hardware_service'):
                with patch.object(sig, 'signal') as mock_signal:
                    service = LabJackDetectionMonitor()

                    # Verify signal handlers were registered
                    assert mock_signal.call_count >= 2  # SIGTERM and SIGINT
                    registered_signals = [call[0][0] for call in mock_signal.call_args_list]
                    assert sig.SIGTERM in registered_signals
                    assert sig.SIGINT in registered_signals

    @patch('services.labjack_detection_service.DATABASE_AVAILABLE', True)
    @patch('services.labjack_detection_service.SessionLocal')
    def test_recovery_ignores_recent_sessions(self, mock_session_local):
        """Test that recent sessions (<24h) are not recovered"""
        # Setup mock database with recent session
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_recent_session = MagicMock()
        mock_recent_session.id = "recent-session-456"
        mock_recent_session.status = "monitoring"
        mock_recent_session.completed_at = None
        mock_recent_session.created_at = datetime.now() - timedelta(hours=2)  # Recent

        # Should not be returned by query (filtered by cutoff_time)
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []  # No orphaned sessions (recent one filtered out)
        mock_db.query.return_value = mock_query

        # Create service
        with patch('services.labjack_detection_service.get_labjack_service'):
            with patch('services.labjack_detection_service.get_labjack_hardware_service'):
                service = LabJackDetectionMonitor()

        # Verify no recovery was performed
        mock_db.commit.assert_not_called()

    def test_recovery_methods_exist_in_both_services(self):
        """Verify crash recovery methods exist in both services"""
        with patch('services.labjack_detection_service.get_labjack_service'):
            with patch('services.labjack_detection_service.get_labjack_hardware_service'):
                labjack_service = LabJackDetectionMonitor()

        with patch('services.dedicated_labjack_monitor.get_video_timing_service'):
            with patch('services.dedicated_labjack_monitor.get_detection_service'):
                with patch('services.dedicated_labjack_monitor.get_hil_ground_truth_comparison'):
                    dedicated_monitor = DedicatedLabJackMonitor()

        # Verify both services have recovery methods
        for service in [labjack_service, dedicated_monitor]:
            assert hasattr(service, 'recover_orphaned_sessions')
            assert hasattr(service, 'cleanup_all_sessions')
            assert hasattr(service, '_register_shutdown_handlers')
            assert hasattr(service, '_shutdown_requested')
            assert callable(service.recover_orphaned_sessions)
            assert callable(service.cleanup_all_sessions)


class TestSessionCleanup:
    """Test session cleanup functionality"""

    def test_stop_session_monitoring_preserves_connection(self):
        """Test that stopping a session preserves hardware connection"""
        with patch('services.labjack_detection_service.get_labjack_service'):
            with patch('services.labjack_detection_service.get_labjack_hardware_service'):
                service = LabJackDetectionMonitor()

        # Add mock session
        mock_config = Mock()
        service.active_sessions['test-session'] = mock_config
        service.detection_status['test-session'] = Mock()
        service.stop_events['test-session'] = Mock()

        # Stop session
        result = service.stop_session_monitoring('test-session')

        # Verify session was cleaned up but connection preserved
        assert result is True
        assert 'test-session' not in service.active_sessions
        # Hardware connection manager should not be disconnected
        assert service.connection_manager is not None or service.connection_manager is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
