"""
Comprehensive test suite for enhanced LabJack monitoring service with continuous detection.
"""

import os
import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from services.dedicated_labjack_monitor import LabJackMonitoringServiceEnhanced


class TestLabJackMonitoringEnhanced:
    """Test suite for enhanced continuous detection algorithm"""

    @pytest.fixture
    def service(self):
        """Create fresh service instance for each test"""
        return LabJackMonitoringServiceEnhanced(
            min_interval_ms=40,
            enable_continuous_detection=True
        )

    @pytest.fixture
    def service_legacy(self):
        """Create service with legacy (rising-edge-only) behavior"""
        return LabJackMonitoringServiceEnhanced(
            enable_continuous_detection=False
        )

    # ========== Configuration Tests ==========

    def test_initialization_defaults(self):
        """Test service initializes with correct defaults"""
        service = LabJackMonitoringServiceEnhanced()

        assert service.enable_continuous_detection is False  # Backwards compatible
        assert service.min_interval_s == 0.040  # 40ms default
        assert service.threshold_v == 2.5
        assert service.sample_rate == 100
        assert not service.monitoring_active

    def test_initialization_custom(self):
        """Test service initializes with custom parameters"""
        service = LabJackMonitoringServiceEnhanced(
            min_interval_ms=20,
            enable_continuous_detection=True
        )

        assert service.enable_continuous_detection is True
        assert service.min_interval_s == 0.020

    def test_validate_interval_negative(self):
        """Test that negative intervals raise ValueError"""
        with pytest.raises(ValueError, match="cannot be negative"):
            LabJackMonitoringServiceEnhanced(min_interval_ms=-10)

    def test_validate_interval_clamping_low(self):
        """Test that intervals below 1ms are clamped"""
        service = LabJackMonitoringServiceEnhanced(min_interval_ms=0.5)
        assert service.min_interval_s == 0.001  # Clamped to 1ms

    def test_validate_interval_clamping_high(self):
        """Test that intervals above 10s are clamped"""
        service = LabJackMonitoringServiceEnhanced(min_interval_ms=15000)
        assert service.min_interval_s == 10.0  # Clamped to 10s

    def test_configure_detection_while_inactive(self, service):
        """Test dynamic reconfiguration when not monitoring"""
        service.configure_detection(
            min_interval_ms=20,
            enable_continuous=False,
            threshold_v=3.0
        )

        assert service.min_interval_s == 0.020
        assert service.enable_continuous_detection is False
        assert service.threshold_v == 3.0

    def test_configure_detection_while_active_raises(self, service):
        """Test that reconfiguration fails when monitoring is active"""
        service.monitoring_active = True

        with pytest.raises(RuntimeError, match="Cannot reconfigure while monitoring"):
            service.configure_detection(min_interval_ms=20)

    # ========== Detection Algorithm Tests ==========

    @patch('services.labjack_monitoring_service_enhanced.signal_validation_service')
    def test_rising_edge_detection(self, mock_signal, service):
        """Test that rising edge triggers immediate detection"""
        mock_signal.read_voltage_signal.return_value = {
            "success": True,
            "voltage": 3.0
        }

        # Simulate rising edge
        service._was_high = False
        service._handle_high_voltage(
            session_id="test-123",
            voltage=3.0,
            current_time=time.monotonic(),
            wall_time=time.time()
        )

        assert service._rising_edge_detections == 1
        assert service._total_detections == 1
        assert service._was_high is True

    @patch('services.labjack_monitoring_service_enhanced.signal_validation_service')
    def test_continuous_detection_with_interval(self, mock_signal, service):
        """Test continuous detections are rate-limited by MIN_INTERVAL"""
        service._was_high = True
        start_time = time.monotonic()
        service._last_emit_time = start_time

        # Simulate sustained high voltage
        # First call (0ms elapsed) - should NOT emit
        service._handle_high_voltage(
            session_id="test-123",
            voltage=3.0,
            current_time=start_time + 0.010,  # 10ms later
            wall_time=time.time()
        )
        assert service._continuous_detections == 0

        # Second call (50ms elapsed) - SHOULD emit
        service._handle_high_voltage(
            session_id="test-123",
            voltage=3.0,
            current_time=start_time + 0.050,  # 50ms later
            wall_time=time.time()
        )
        assert service._continuous_detections == 1
        assert service._total_detections == 1

    @patch('services.labjack_monitoring_service_enhanced.signal_validation_service')
    def test_falling_edge_resets_state(self, mock_signal, service):
        """Test that falling edge resets detection state"""
        service._was_high = True
        service._last_emit_time = time.monotonic()

        service._handle_low_voltage()

        assert service._was_high is False

    @patch('services.labjack_monitoring_service_enhanced.signal_validation_service')
    def test_legacy_mode_no_continuous_detection(self, mock_signal, service_legacy):
        """Test that legacy mode only detects rising edges"""
        service_legacy._was_high = True
        start_time = time.monotonic()
        service_legacy._last_emit_time = start_time

        # Simulate sustained high voltage with sufficient elapsed time
        service_legacy._handle_high_voltage(
            session_id="test-123",
            voltage=3.0,
            current_time=start_time + 1.0,  # 1 second later
            wall_time=time.time()
        )

        # Should NOT emit because continuous detection is disabled
        assert service_legacy._continuous_detections == 0
        assert service_legacy._total_detections == 0

    # ========== Performance & Edge Cases ==========

    def test_short_pulse_single_detection(self, service):
        """Test that short pulse (10ms) generates only 1 detection"""
        detections = []

        def mock_store(session_id, voltage, timestamp, channel, detection_type):
            detections.append(detection_type)

        service._store_detection_event = mock_store
        service._was_high = False
        start_time = time.monotonic()

        # Rising edge
        service._handle_high_voltage("test", 3.0, start_time, time.time())

        # Still high but only 10ms elapsed (below MIN_INTERVAL)
        service._handle_high_voltage("test", 3.0, start_time + 0.010, time.time())

        # Falling edge
        service._handle_low_voltage()

        assert len(detections) == 1
        assert detections[0] == "rising_edge"

    def test_long_pulse_multiple_detections(self, service):
        """Test that long pulse (500ms) generates ~12 detections at 40ms interval"""
        detections = []

        def mock_store(session_id, voltage, timestamp, channel, detection_type):
            detections.append(detection_type)

        service._store_detection_event = mock_store
        service._was_high = False
        start_time = time.monotonic()

        # Simulate 500ms pulse sampled at 10ms intervals
        for i in range(51):  # 0ms to 500ms in 10ms steps
            current_time = start_time + (i * 0.010)
            service._handle_high_voltage("test", 3.0, current_time, time.time())

        # Expected: 1 rising edge + floor(500/40) = 1 + 12 = 13 detections
        assert len(detections) >= 12
        assert len(detections) <= 14  # Allow some timing variance
        assert detections[0] == "rising_edge"
        assert all(d == "continuous" for d in detections[1:])

    def test_rapid_noise_handling(self, service):
        """Test that rapid high/low transitions don't cause issues"""
        detections = []

        def mock_store(session_id, voltage, timestamp, channel, detection_type):
            detections.append(detection_type)

        service._store_detection_event = mock_store
        start_time = time.monotonic()

        # Simulate noisy signal (high-low-high-low pattern)
        for i in range(10):
            current_time = start_time + (i * 0.005)  # 5ms intervals
            if i % 2 == 0:
                service._handle_high_voltage("test", 3.0, current_time, time.time())
            else:
                service._handle_low_voltage()

        # Should only get rising edge detections (no continuous due to resets)
        assert all(d == "rising_edge" for d in detections)
        assert len(detections) == 5  # 5 rising edges

    def test_zero_interval_handling(self):
        """Test that MIN_INTERVAL=0 is clamped to minimum safe value"""
        service = LabJackMonitoringServiceEnhanced(min_interval_ms=0)
        assert service.min_interval_s == 0.001  # Clamped to 1ms

    @patch('services.labjack_monitoring_service_enhanced.time.monotonic')
    def test_monotonic_time_usage(self, mock_monotonic, service):
        """Test that service uses monotonic time for intervals"""
        mock_monotonic.return_value = 1000.0

        service._was_high = True
        service._last_emit_time = 990.0

        # Should use monotonic time for elapsed calculation
        service._handle_high_voltage(
            "test", 3.0,
            current_time=1000.0,  # 10s elapsed
            wall_time=time.time()
        )

        # Should emit because 10s > MIN_INTERVAL
        assert service._continuous_detections == 1

    # ========== Database Integration Tests ==========

    @patch('services.labjack_monitoring_service_enhanced.sqlite3.connect')
    def test_store_detection_event_success(self, mock_connect, service):
        """Test successful database storage"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        service._store_detection_event(
            session_id="test-123",
            voltage=3.0,
            timestamp=time.time(),
            channel="AIN0",
            detection_type="rising_edge"
        )

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('services.labjack_monitoring_service_enhanced.sqlite3.connect')
    def test_store_detection_event_failure(self, mock_connect, service, caplog):
        """Test graceful handling of database errors"""
        mock_connect.side_effect = Exception("Database connection failed")

        # Should not raise exception
        service._store_detection_event(
            session_id="test-123",
            voltage=3.0,
            timestamp=time.time(),
            channel="AIN0",
            detection_type="rising_edge"
        )

        # Should log error
        assert "Failed to store detection event" in caplog.text

    # ========== Metrics Tests ==========

    def test_get_metrics(self, service):
        """Test metrics reporting"""
        service._total_detections = 100
        service._rising_edge_detections = 20
        service._continuous_detections = 80
        service.monitoring_active = True
        service.current_session_id = "test-123"

        metrics = service.get_metrics()

        assert metrics["monitoring_active"] is True
        assert metrics["session_id"] == "test-123"
        assert metrics["continuous_mode"] is True
        assert metrics["min_interval_ms"] == 40.0
        assert metrics["total_detections"] == 100
        assert metrics["rising_edge_detections"] == 20
        assert metrics["continuous_detections"] == 80

    # ========== Threading Tests ==========

    @patch('services.labjack_monitoring_service_enhanced.signal_validation_service')
    def test_start_stop_monitoring(self, mock_signal, service):
        """Test thread lifecycle management"""
        mock_signal.read_voltage_signal.return_value = {
            "success": True,
            "voltage": 1.0  # Below threshold
        }

        # Start monitoring
        success = service.start_monitoring("test-123", sample_rate=10)
        assert success is True
        assert service.monitoring_active is True
        assert service.monitor_thread.is_alive()

        # Wait briefly
        time.sleep(0.1)

        # Stop monitoring
        success = service.stop_monitoring()
        assert success is True
        assert not service.monitoring_active
        assert not service.monitor_thread.is_alive()

    def test_double_start_fails(self, service):
        """Test that starting monitoring twice fails gracefully"""
        service.monitoring_active = True
        service.current_session_id = "existing-session"

        result = service.start_monitoring("new-session")
        assert result is False

    def test_stop_when_not_active(self, service):
        """Test stopping when not monitoring returns False"""
        result = service.stop_monitoring()
        assert result is False


# ========== Integration Tests ==========

class TestLabJackIntegration:
    """Integration tests simulating real-world usage"""

    @patch('services.labjack_monitoring_service_enhanced.signal_validation_service')
    @patch('services.labjack_monitoring_service_enhanced.sqlite3.connect')
    def test_full_pulse_detection_scenario(self, mock_db, mock_signal):
        """
        Integration test: 10-second test with 5 × 500ms pulses
        Expected detections with MIN_INTERVAL=40ms: ~60 total
        """
        # Setup
        service = LabJackMonitoringServiceEnhanced(
            min_interval_ms=40,
            enable_continuous_detection=True
        )

        # Mock database
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate voltage readings
        pulse_pattern = []
        # Generate 10 seconds of data at 100Hz (1000 samples)
        for i in range(1000):
            t = i * 0.010  # 10ms intervals
            # 5 pulses: 0-500ms, 2s-2.5s, 4s-4.5s, 6s-6.5s, 8s-8.5s
            is_pulse = (
                (0 <= t < 0.5) or
                (2.0 <= t < 2.5) or
                (4.0 <= t < 4.5) or
                (6.0 <= t < 6.5) or
                (8.0 <= t < 8.5)
            )
            voltage = 3.0 if is_pulse else 1.0
            pulse_pattern.append(voltage)

        # Run monitoring simulation
        mock_signal.read_voltage_signal.side_effect = [
            {"success": True, "voltage": v} for v in pulse_pattern
        ]

        # Start monitoring (will run in thread)
        service.start_monitoring("integration-test", sample_rate=100)

        # Let it run for 11 seconds
        time.sleep(11)

        # Stop monitoring
        service.stop_monitoring()

        # Verify results
        metrics = service.get_metrics()
        total = metrics["total_detections"]

        # Expected: ~12 detections per 500ms pulse = 12 × 5 = 60 detections
        assert 50 <= total <= 70, f"Expected ~60 detections, got {total}"
        assert metrics["rising_edge_detections"] == 5  # One per pulse
        assert 45 <= metrics["continuous_detections"] <= 65  # Rest are continuous


# ========== Performance Benchmark ==========

class TestPerformanceBenchmark:
    """Performance benchmark tests"""

    @patch('services.labjack_monitoring_service_enhanced.signal_validation_service')
    @patch('services.labjack_monitoring_service_enhanced.sqlite3.connect')
    def test_cpu_overhead_benchmark(self, mock_db, mock_signal):
        """Measure CPU overhead of continuous detection"""
        import psutil
        import os

        # Setup
        service = LabJackMonitoringServiceEnhanced(
            min_interval_ms=40,
            enable_continuous_detection=True
        )

        mock_signal.read_voltage_signal.return_value = {
            "success": True,
            "voltage": 3.0  # Always high
        }
        mock_db.return_value = MagicMock()

        # Measure baseline CPU
        process = psutil.Process(os.getpid())
        baseline_cpu = process.cpu_percent(interval=1.0)

        # Start monitoring
        service.start_monitoring("benchmark", sample_rate=100)

        # Run for 5 seconds
        time.sleep(5)

        # Measure CPU during monitoring
        monitoring_cpu = process.cpu_percent(interval=1.0)

        # Stop monitoring
        service.stop_monitoring()

        # Calculate overhead
        overhead = monitoring_cpu - baseline_cpu

        # Verify overhead is < 5%
        assert overhead < 5.0, f"CPU overhead too high: {overhead}%"

        print(f"\nPerformance Benchmark Results:")
        print(f"  Baseline CPU: {baseline_cpu:.2f}%")
        print(f"  Monitoring CPU: {monitoring_cpu:.2f}%")
        print(f"  Overhead: {overhead:.2f}%")
        print(f"  Total detections: {service._total_detections}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
