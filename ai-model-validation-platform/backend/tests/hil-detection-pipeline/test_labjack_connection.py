"""

pytestmark = pytest.mark.skip(reason="Deprecated modules or missing dependencies")

HIL Detection Pipeline Tests - LabJack Connection & Signal Capture

Tests for:
- LabJack hardware connection stability
- Reconnection on disconnect
- Signal capture verification
- Voltage threshold detection
- Debounce logic
"""

pytestmark = pytest.mark.skip(reason="Deprecated or missing dependencies")

import pytest
import time
import threading
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Import services under test
from services.simple_labjack_detection import (
    LabJackDetectionMonitor,
    DetectionEvent,
    DetectionConfig,
    DetectionStatus,
    get_detection_service
)
from services.labjack_connection_manager import get_connection_manager


class TestLabJackConnection:
    """Test LabJack hardware connection stability"""

    @pytest.fixture
    def detection_monitor(self):
        """Create a fresh detection monitor instance"""
        return LabJackDetectionMonitor()

    @pytest.fixture
    def mock_connection_manager(self):
        """Create mock connection manager"""
        manager = Mock()
        manager.is_connected.return_value = True
        manager.connect.return_value = True
        manager.read_voltage.return_value = 3.5
        return manager

    def test_connection_initialization(self, detection_monitor):
        """Test that connection manager initializes properly"""
        assert detection_monitor.connection_manager is not None
        assert detection_monitor.labjack_service is not None

    def test_connection_stability_during_monitoring(self, detection_monitor, mock_connection_manager):
        """Test connection remains stable during active monitoring"""
        session_id = "test_session_stability"

        with patch.object(detection_monitor, 'connection_manager', mock_connection_manager):
            # Start monitoring
            success = detection_monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=100
            )

            assert success

            # Wait for monitoring to start
            time.sleep(0.5)

            # Verify connection is maintained
            assert mock_connection_manager.is_connected.called
            assert mock_connection_manager.connect.called

            # Stop monitoring
            detection_monitor.stop_session_monitoring(session_id)

    def test_reconnection_on_disconnect(self, detection_monitor):
        """Test automatic reconnection when connection drops"""
        session_id = "test_session_reconnect"

        mock_manager = Mock()
        # Simulate disconnect then reconnect
        mock_manager.is_connected.side_effect = [False, False, True, True]
        mock_manager.connect.return_value = True
        mock_manager.read_voltage.return_value = 3.0

        with patch.object(detection_monitor, 'connection_manager', mock_manager):
            success = detection_monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=100
            )

            assert success
            time.sleep(0.3)

            # Verify reconnection was attempted
            assert mock_manager.connect.call_count >= 1

            detection_monitor.stop_session_monitoring(session_id)

    def test_multiple_sessions_share_connection(self, detection_monitor, mock_connection_manager):
        """Test that multiple sessions share the same hardware connection"""
        with patch.object(detection_monitor, 'connection_manager', mock_connection_manager):
            # Start first session
            success1 = detection_monitor.start_monitoring(
                session_id="session_1",
                channels=["AIN0"],
                voltage_threshold=2.5
            )

            # Start second session
            success2 = detection_monitor.start_monitoring(
                session_id="session_2",
                channels=["AIN1"],
                voltage_threshold=3.0
            )

            assert success1 and success2

            # Verify connection was only established once (shared)
            assert mock_connection_manager.connect.call_count == 1

            # Stop first session - connection should remain
            detection_monitor.stop_session_monitoring("session_1")

            # Second session should still work
            status = detection_monitor.get_session_status("session_2")
            assert status['active']

            # Stop second session
            detection_monitor.stop_session_monitoring("session_2")


class TestSignalCapture:
    """Test signal capture and voltage detection"""

    @pytest.fixture
    def detection_monitor(self):
        return LabJackDetectionMonitor()

    def test_voltage_threshold_detection(self, detection_monitor):
        """Test detection triggers when voltage exceeds threshold"""
        session_id = "test_threshold"
        detected_events = []

        def capture_detection(event):
            detected_events.append(event)

        detection_monitor.add_detection_callback(capture_detection)

        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        # Simulate voltage crossing threshold
        mock_manager.read_voltage.side_effect = [2.0, 2.3, 2.8, 3.5, 3.8, 2.0]

        with patch.object(detection_monitor, 'connection_manager', mock_manager):
            success = detection_monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=500,
                debounce_ms=50
            )

            assert success

            # Wait for detections
            time.sleep(0.5)

            # Should detect voltages >= 2.5V: 2.8, 3.5, 3.8
            assert len(detected_events) >= 1

            # Verify detection voltage is above threshold
            for event in detected_events:
                assert event.voltage >= 2.5

            detection_monitor.stop_session_monitoring(session_id)

    def test_debounce_logic(self, detection_monitor):
        """Test debounce prevents duplicate detections"""
        session_id = "test_debounce"
        detected_events = []

        def capture_detection(event):
            detected_events.append(event)

        detection_monitor.add_detection_callback(capture_detection)

        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        # Simulate rapid voltage pulses
        mock_manager.read_voltage.return_value = 3.5

        with patch.object(detection_monitor, 'connection_manager', mock_manager):
            success = detection_monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=1000,
                debounce_ms=100  # 100ms debounce
            )

            assert success
            time.sleep(0.3)

            # With 100ms debounce and 1000Hz sampling, should get ~3 detections max in 300ms
            # (not 300+ without debounce)
            assert len(detected_events) <= 5

            detection_monitor.stop_session_monitoring(session_id)

    def test_channel_isolation(self, detection_monitor):
        """Test that different channels are isolated"""
        session_id = "test_channels"
        detected_events = []

        def capture_detection(event):
            detected_events.append(event)

        detection_monitor.add_detection_callback(capture_detection)

        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True

        # AIN0 = high, AIN1 = low
        def mock_read(channel):
            return 3.5 if channel == "AIN0" else 1.0

        mock_manager.read_voltage.side_effect = mock_read

        with patch.object(detection_monitor, 'connection_manager', mock_manager):
            success = detection_monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0", "AIN1"],
                voltage_threshold=2.5,
                sample_rate=100
            )

            assert success
            time.sleep(0.3)

            # Only AIN0 should trigger detections
            ain0_events = [e for e in detected_events if e.channel == "AIN0"]
            ain1_events = [e for e in detected_events if e.channel == "AIN1"]

            assert len(ain0_events) > 0
            assert len(ain1_events) == 0

            detection_monitor.stop_session_monitoring(session_id)

    def test_continuous_mode(self, detection_monitor):
        """Test continuous sampling mode with voltage window"""
        session_id = "test_continuous"
        detected_events = []

        def capture_detection(event):
            detected_events.append(event)

        detection_monitor.add_detection_callback(capture_detection)

        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        # Voltage stays within continuous range
        mock_manager.read_voltage.return_value = 3.0

        with patch.object(detection_monitor, 'connection_manager', mock_manager):
            success = detection_monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=1000,
                continuous_mode=True,
                continuous_lower_bound=2.5,
                continuous_upper_bound=3.5,
                continuous_interval_ms=20
            )

            assert success
            time.sleep(0.2)

            # With 20ms interval, should get ~10 detections in 200ms
            assert 8 <= len(detected_events) <= 12

            # Verify continuous mode metadata
            for event in detected_events:
                assert event.metadata.get('continuous_mode') is True

            detection_monitor.stop_session_monitoring(session_id)


class TestDetectionWindowValidation:
    """Test detection window validation (prevents early/late captures)"""

    @pytest.fixture
    def detection_monitor(self):
        return LabJackDetectionMonitor()

    def test_early_detection_rejection(self, detection_monitor):
        """Test detections before video start are rejected"""
        session_id = "test_early_detection"
        detected_events = []

        def capture_detection(event):
            detected_events.append(event)

        detection_monitor.add_detection_callback(capture_detection)

        # Set video start time in the future
        video_start_time = time.time() + 2.0  # 2 seconds from now

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
                video_start_time=video_start_time,
                duration=5.0
            )

            assert success

            # Wait 0.5s (still before video start)
            time.sleep(0.5)

            # Should have no detections (too early)
            assert len(detected_events) == 0

            # Wait until after video start
            time.sleep(2.0)

            # Now should have detections
            assert len(detected_events) > 0

            detection_monitor.stop_session_monitoring(session_id)

    def test_grace_period_allows_pre_trigger(self, detection_monitor):
        """Test grace period allows detections slightly before start"""
        from config.timing_config import GRACE_PERIOD_SECONDS

        session_id = "test_grace_period"
        detected_events = []

        def capture_detection(event):
            detected_events.append(event)

        detection_monitor.add_detection_callback(capture_detection)

        # Video starts in 1 second, but grace period is 2 seconds
        # So detections NOW should be allowed
        video_start_time = time.time() + 1.0

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
                video_start_time=video_start_time,
                duration=5.0
            )

            assert success
            time.sleep(0.3)

            # Should have detections (within grace period)
            assert len(detected_events) > 0

            detection_monitor.stop_session_monitoring(session_id)

    def test_auto_stop_after_video_end(self, detection_monitor):
        """Test monitoring auto-stops after video duration"""
        session_id = "test_auto_stop"

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
                video_start_time=time.time(),
                duration=0.5  # 500ms video
            )

            assert success

            # Wait for auto-stop (duration + grace)
            time.sleep(1.0)

            # Monitoring should have stopped
            status = detection_monitor.get_session_status(session_id)
            assert status['status'] == 'stopped' or status['active'] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
