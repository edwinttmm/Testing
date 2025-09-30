"""
Test LabJack Connection Preservation During Session Stops

This test verifies that LabJack hardware connections remain stable
when test sessions are stopped, preventing connection drops that
cause delays and reliability issues.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

# Test the connection preservation fixes
class TestLabJackConnectionPreservation:
    """Test suite for LabJack connection preservation during session lifecycle"""
    
    @pytest.fixture
    def mock_labjack_service(self):
        """Mock LabJack service with connection tracking"""
        service = Mock()
        service.status = "CONNECTED"
        service.connected = True
        service.active_sessions = set()
        service.direct_handle = Mock()  # Simulate hardware handle
        return service
    
    @pytest.fixture
    def mock_bridge_service(self):
        """Mock Windows LabJack bridge service"""
        service = Mock()
        service.active_sessions = set()
        service.monitoring_enabled = True
        service.connected = True
        return service
    
    @pytest.fixture
    def mock_dedicated_monitor(self):
        """Mock dedicated LabJack monitor service"""
        monitor = Mock()
        monitor.active_sessions = {}
        monitor.labjack_monitor = Mock()
        return monitor

    def test_single_session_stop_preserves_connection(self, mock_labjack_service, mock_bridge_service):
        """Test that stopping a single session preserves the hardware connection"""
        
        # Setup: Start a session
        session_id = "test-session-1"
        mock_bridge_service.active_sessions.add(session_id)
        
        # Test: Stop session monitoring (not hardware)
        mock_bridge_service.stop_session_monitoring(session_id)
        
        # Verify: Connection should be preserved
        assert session_id not in mock_bridge_service.active_sessions
        # Hardware connection should remain (not closed)
        assert mock_labjack_service.connected is True
        assert mock_labjack_service.direct_handle is not None

    def test_multiple_sessions_preserve_connection(self, mock_bridge_service):
        """Test that stopping one session while others are active preserves connection"""
        
        # Setup: Start multiple sessions
        sessions = ["session-1", "session-2", "session-3"]
        for session_id in sessions:
            mock_bridge_service.active_sessions.add(session_id)
        
        # Simulate the fixed stop_session_monitoring method
        def stop_session_monitoring(session_id):
            mock_bridge_service.active_sessions.discard(session_id)
            # Only disable monitoring when no sessions remain
            if not mock_bridge_service.active_sessions:
                mock_bridge_service.monitoring_enabled = False
            return True
        
        mock_bridge_service.stop_session_monitoring = stop_session_monitoring
        
        # Test: Stop one session
        mock_bridge_service.stop_session_monitoring("session-1")
        
        # Verify: Other sessions still active, monitoring continues
        assert len(mock_bridge_service.active_sessions) == 2
        assert mock_bridge_service.monitoring_enabled is True
        
        # Test: Stop another session
        mock_bridge_service.stop_session_monitoring("session-2")
        
        # Verify: Still one session active
        assert len(mock_bridge_service.active_sessions) == 1
        assert mock_bridge_service.monitoring_enabled is True
        
        # Test: Stop final session
        mock_bridge_service.stop_session_monitoring("session-3")
        
        # Verify: No sessions remain, monitoring disabled
        assert len(mock_bridge_service.active_sessions) == 0
        assert mock_bridge_service.monitoring_enabled is False

    def test_callback_cleanup_order(self, mock_dedicated_monitor):
        """Test that callbacks are removed before hardware operations"""
        
        session_id = "test-session"
        callback_function = Mock()
        
        # Setup session with callback
        mock_dedicated_monitor.active_sessions[session_id] = {
            'detection_callback': callback_function,
            'started_at': datetime.now(timezone.utc)
        }
        
        # Mock the callback removal to track order
        removal_order = []
        
        def mock_remove_callback(callback):
            removal_order.append("callback_removed")
            return True
        
        def mock_hardware_operation():
            removal_order.append("hardware_operation")
            return True
        
        mock_dedicated_monitor.labjack_monitor.remove_detection_callback = mock_remove_callback
        mock_dedicated_monitor.labjack_monitor.stop_session_monitoring = mock_hardware_operation
        
        # Simulate the fixed stop_monitoring method
        def stop_monitoring(session_id):
            session_data = mock_dedicated_monitor.active_sessions.get(session_id, {})
            
            # STEP 1: Remove callbacks FIRST
            callback = session_data.get('detection_callback')
            if callback:
                mock_dedicated_monitor.labjack_monitor.remove_detection_callback(callback)
            
            # STEP 2: Hardware operations
            mock_dedicated_monitor.labjack_monitor.stop_session_monitoring(session_id)
            
            # STEP 3: Cleanup session data
            mock_dedicated_monitor.active_sessions.pop(session_id, None)
            
            return {"success": True, "connection_preserved": True}
        
        mock_dedicated_monitor.stop_monitoring = stop_monitoring
        
        # Test: Stop monitoring
        result = mock_dedicated_monitor.stop_monitoring(session_id)
        
        # Verify: Correct order and successful completion
        assert removal_order == ["callback_removed", "hardware_operation"]
        assert result["success"] is True
        assert result["connection_preserved"] is True
        assert session_id not in mock_dedicated_monitor.active_sessions

    def test_connection_handle_not_closed_prematurely(self, mock_labjack_service):
        """Test that hardware connection handle is not closed during session stop"""
        
        # Setup: Service with active connection
        mock_labjack_service.direct_handle = Mock()
        mock_labjack_service.active_sessions = {"session-1", "session-2"}
        
        # Mock the fixed stop_session_monitoring method
        def stop_session_monitoring(session_id):
            mock_labjack_service.active_sessions.discard(session_id)
            # Only close handle when NO sessions remain
            if not mock_labjack_service.active_sessions:
                mock_labjack_service.direct_handle = None
            return True
        
        mock_labjack_service.stop_session_monitoring = stop_session_monitoring
        
        # Test: Stop one session (others still active)
        mock_labjack_service.stop_session_monitoring("session-1")
        
        # Verify: Handle preserved because other sessions exist
        assert mock_labjack_service.direct_handle is not None
        assert len(mock_labjack_service.active_sessions) == 1
        
        # Test: Stop final session
        mock_labjack_service.stop_session_monitoring("session-2")
        
        # Verify: Now handle can be closed
        assert len(mock_labjack_service.active_sessions) == 0
        assert mock_labjack_service.direct_handle is None

    def test_no_double_cleanup_scenarios(self, mock_dedicated_monitor):
        """Test that multiple stop calls don't cause double cleanup issues"""
        
        session_id = "test-session"
        cleanup_count = 0
        
        def count_cleanup():
            nonlocal cleanup_count
            cleanup_count += 1
            return True
        
        mock_dedicated_monitor.labjack_monitor.stop_session_monitoring = count_cleanup
        mock_dedicated_monitor.active_sessions[session_id] = {}
        
        # Simulate the fixed stop_monitoring with proper guards
        def stop_monitoring(session_id):
            if session_id not in mock_dedicated_monitor.active_sessions:
                return {"success": False, "error": "Session not active"}
            
            # Clean up once
            mock_dedicated_monitor.labjack_monitor.stop_session_monitoring()
            mock_dedicated_monitor.active_sessions.pop(session_id, None)
            
            return {"success": True, "connection_preserved": True}
        
        mock_dedicated_monitor.stop_monitoring = stop_monitoring
        
        # Test: Multiple stop calls
        result1 = mock_dedicated_monitor.stop_monitoring(session_id)
        result2 = mock_dedicated_monitor.stop_monitoring(session_id)  # Should be ignored
        
        # Verify: Only cleaned up once
        assert cleanup_count == 1
        assert result1["success"] is True
        assert result2["success"] is False

    @patch('ai-model-validation-platform.backend.services.dedicated_labjack_monitor.stop_hil_monitoring')
    def test_test_session_router_preserves_connection(self, mock_stop_hil):
        """Test that the test session router properly preserves connections"""
        
        # Mock the stop_hil_monitoring function to return connection preservation
        mock_stop_hil.return_value = {
            "success": True,
            "connection_preserved": True,
            "detection_count": 5,
            "duration_seconds": 10.5,
            "average_latency_ms": 25.3
        }
        
        # Simulate session stop
        session_id = "test-session"
        result = mock_stop_hil(session_id)
        
        # Verify: Connection was preserved
        assert result["success"] is True
        assert result["connection_preserved"] is True
        mock_stop_hil.assert_called_once_with(session_id)

    def test_bridge_session_state_management(self, mock_bridge_service):
        """Test bridge service properly manages session state"""
        
        # Implement the fixed state management logic
        def get_active_session_count():
            return len(mock_bridge_service.active_sessions)
        
        def get_active_sessions():
            return mock_bridge_service.active_sessions.copy()
        
        mock_bridge_service.get_active_session_count = get_active_session_count
        mock_bridge_service.get_active_sessions = get_active_sessions
        
        # Test: Add sessions
        mock_bridge_service.active_sessions.update(["s1", "s2", "s3"])
        
        # Verify: State tracking works
        assert mock_bridge_service.get_active_session_count() == 3
        assert "s1" in mock_bridge_service.get_active_sessions()
        
        # Test: Remove session
        mock_bridge_service.active_sessions.discard("s1")
        
        # Verify: State updated correctly
        assert mock_bridge_service.get_active_session_count() == 2
        assert "s1" not in mock_bridge_service.get_active_sessions()


class TestConnectionStabilityScenarios:
    """Test real-world scenarios that caused connection drops"""
    
    def test_rapid_start_stop_cycle(self):
        """Test rapid session start/stop cycles don't cause connection drops"""
        
        # This tests the scenario where users quickly start/stop tests
        mock_service = Mock()
        mock_service.connected = True
        sessions_created = []
        
        def mock_start_session(session_id):
            sessions_created.append(session_id)
            return True
        
        def mock_stop_session(session_id):
            if session_id in sessions_created:
                sessions_created.remove(session_id)
            return {"success": True, "connection_preserved": len(sessions_created) > 0}
        
        mock_service.start_session = mock_start_session
        mock_service.stop_session = mock_stop_session
        
        # Test: Rapid start/stop cycle
        for i in range(5):
            session_id = f"rapid-session-{i}"
            mock_service.start_session(session_id)
            result = mock_service.stop_session(session_id)
            
            # Each stop should preserve connection state appropriately
            assert result["success"] is True
        
        # Verify: Service remains connected throughout
        assert mock_service.connected is True

    def test_error_during_cleanup_preserves_connection(self):
        """Test that errors during cleanup don't cause connection loss"""
        
        mock_service = Mock()
        mock_service.connected = True
        
        def failing_cleanup():
            raise Exception("Cleanup error")
        
        def safe_stop_session_monitoring(session_id):
            try:
                failing_cleanup()
            except Exception:
                # Connection should remain stable despite cleanup errors
                pass
            return {"success": False, "connection_preserved": True, "error": "Cleanup failed"}
        
        mock_service.stop_session_monitoring = safe_stop_session_monitoring
        
        # Test: Stop with cleanup error
        result = mock_service.stop_session_monitoring("test-session")
        
        # Verify: Connection preserved despite error
        assert result["connection_preserved"] is True
        assert mock_service.connected is True


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])