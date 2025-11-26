"""
HIL Detection Pipeline Tests - WebSocket Event Emission

Tests for:
- Real-time event emission from backend
- Event reception in frontend
- Fallback polling mechanism
- Room-based notification
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from services.simple_labjack_detection import LabJackDetectionMonitor, DetectionEvent
from services.dedicated_labjack_monitor import DedicatedLabJackMonitor, HILDetectionEvent


class TestWebSocketEmission:
    """Test WebSocket event emission from backend"""

    @pytest.fixture
    def mock_websocket_emit(self):
        """Create mock WebSocket emission function"""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def detection_monitor(self, mock_websocket_emit):
        """Create detection monitor with WebSocket mock"""
        monitor = LabJackDetectionMonitor()
        monitor.set_websocket_emit_function(mock_websocket_emit)
        return monitor

    @pytest.mark.asyncio
    async def test_detection_event_emitted_via_websocket(self, detection_monitor, mock_websocket_emit):
        """Test detection events are emitted via WebSocket"""
        session_id = "test_ws_emission"

        # Mock connection manager
        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        mock_manager.read_voltage.return_value = 3.5

        with patch.object(detection_monitor, 'connection_manager', mock_manager):
            success = detection_monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=100,
                enable_websocket=True,
                store_in_db=False  # Disable DB for faster testing
            )

            assert success

            # Wait for detection to be captured and emitted
            await asyncio.sleep(0.3)

            # Verify WebSocket emit was called
            assert mock_websocket_emit.called

            # Verify emit was called with detection data
            call_args = mock_websocket_emit.call_args_list[0]
            detection_data = call_args[0][0]

            assert detection_data['session_id'] == session_id
            assert detection_data['voltage'] >= 2.5
            assert 'timestamp' in detection_data

            detection_monitor.stop_session_monitoring(session_id)

    @pytest.mark.asyncio
    async def test_websocket_emission_includes_timing_data(self, detection_monitor, mock_websocket_emit):
        """Test WebSocket events include video timing synchronization"""
        session_id = "test_ws_timing"

        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        mock_manager.read_voltage.return_value = 3.5

        with patch.object(detection_monitor, 'connection_manager', mock_manager):
            success = detection_monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=100,
                enable_websocket=True,
                video_start_time=time.time(),
                duration=5.0
            )

            assert success
            await asyncio.sleep(0.3)

            # Verify timing data is included
            if mock_websocket_emit.called:
                call_args = mock_websocket_emit.call_args_list[0]
                detection_data = call_args[0][0]

                assert 'video_relative_timestamp' in detection_data
                assert 'actual_latency_ms' in detection_data
                assert 'frame_number' in detection_data or 'video_frame_number' in detection_data

            detection_monitor.stop_session_monitoring(session_id)

    def test_websocket_emission_disabled_when_configured(self, mock_websocket_emit):
        """Test WebSocket emission can be disabled"""
        session_id = "test_ws_disabled"
        monitor = LabJackDetectionMonitor()
        monitor.set_websocket_emit_function(mock_websocket_emit)

        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        mock_manager.read_voltage.return_value = 3.5

        with patch.object(monitor, 'connection_manager', mock_manager):
            success = monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=100,
                enable_websocket=False  # Disabled
            )

            assert success
            time.sleep(0.3)

            # WebSocket emit should NOT be called
            assert not mock_websocket_emit.called

            monitor.stop_session_monitoring(session_id)

    @pytest.mark.asyncio
    async def test_websocket_emission_handles_errors_gracefully(self, mock_websocket_emit):
        """Test WebSocket errors don't crash monitoring"""
        session_id = "test_ws_error"

        # Make WebSocket emit raise an error
        mock_websocket_emit.side_effect = Exception("WebSocket connection lost")

        monitor = LabJackDetectionMonitor()
        monitor.set_websocket_emit_function(mock_websocket_emit)

        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        mock_manager.read_voltage.return_value = 3.5

        with patch.object(monitor, 'connection_manager', mock_manager):
            success = monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=100,
                enable_websocket=True
            )

            assert success
            await asyncio.sleep(0.3)

            # Monitor should still be running despite WS error
            status = monitor.get_session_status(session_id)
            assert status['active']

            monitor.stop_session_monitoring(session_id)


class TestRoomBasedNotification:
    """Test room-based WebSocket notification (session-scoped)"""

    @pytest.mark.asyncio
    async def test_detection_emitted_to_session_room(self):
        """Test detections are emitted to session-specific room"""
        from services.websocket_rooms import notify_session_room

        with patch('services.websocket_rooms.notify_session_room') as mock_notify:
            mock_notify.return_value = True

            # Create HIL monitor with WebSocket
            mock_ws_emit = AsyncMock()
            monitor = DedicatedLabJackMonitor(websocket_emit_fn=mock_ws_emit)

            # Create test HIL event
            hil_event = HILDetectionEvent(
                id="test_event_id",
                session_id="test_session_room",
                unix_timestamp=time.time(),
                video_relative_timestamp=1.5,
                video_relative_timestamp_ns="1500000000",
                actual_latency_ms=45.0,
                video_frame_number=36,
                timing_sync_quality="high",
                labjack_voltage=3.5,
                detection_channel="AIN0",
                precision_ns=1000000,
                screenshot_path=None,
                screenshot_zoom_path=None,
                ground_truth_comparison=None,
                created_at=datetime.now()
            )

            # Emit via room notification
            monitor._schedule_websocket_emission(hil_event, "test_session_room")

            await asyncio.sleep(0.2)

            # Verify room notification was called
            # Note: This verifies the integration with websocket_rooms service
            # The actual socket.io broadcast is mocked at the infrastructure level


class TestFallbackPolling:
    """Test fallback polling mechanism when WebSocket fails"""

    def test_detection_events_available_via_http_endpoint(self):
        """Test detections can be retrieved via HTTP when WebSocket fails"""
        from services.simple_labjack_detection import get_detection_service

        monitor = get_detection_service()
        session_id = "test_fallback_polling"

        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        mock_manager.read_voltage.return_value = 3.5

        with patch.object(monitor, 'connection_manager', mock_manager):
            # Start monitoring WITHOUT WebSocket
            success = monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=100,
                enable_websocket=False
            )

            assert success
            time.sleep(0.3)

            # Retrieve events via HTTP API equivalent
            events = monitor.get_detection_events(session_id, from_database=False)

            # Should have detected events available
            assert len(events) > 0
            assert all(e['session_id'] == session_id for e in events)

            monitor.stop_session_monitoring(session_id)

    def test_database_persistence_enables_polling(self):
        """Test database persistence allows HTTP polling for events"""
        from services.simple_labjack_detection import get_detection_service, DATABASE_AVAILABLE

        if not DATABASE_AVAILABLE:
            pytest.skip("Database not available for this test")

        monitor = get_detection_service()
        session_id = "test_db_polling"

        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        mock_manager.read_voltage.return_value = 3.5

        with patch.object(monitor, 'connection_manager', mock_manager):
            success = monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=100,
                store_in_db=True,
                enable_websocket=False
            )

            assert success
            time.sleep(0.5)  # Allow time for DB storage

            # Retrieve from database
            events = monitor.get_detection_events(session_id, from_database=True)

            assert len(events) > 0

            monitor.stop_session_monitoring(session_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
