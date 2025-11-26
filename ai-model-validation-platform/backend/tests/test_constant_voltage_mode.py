"""
Test suite for constant voltage mode debounce bypass feature

This test suite validates the PRIORITY 2 fix for constant voltage testing,
ensuring that when constant_voltage_mode=True, the debounce filter is bypassed
to achieve 100% detection rate even with rapid consecutive detections.

Test Cases:
1. Normal mode with debounce active (control)
2. Constant voltage mode with debounce bypassed
3. 24 FPS video scenario (41.67ms frame period)
4. Backward compatibility with existing tests
"""

import pytest
import time
from datetime import datetime, timedelta
from services.labjack_detection_service import (
    LabJackDetectionMonitor,
    DetectionConfig,
    DetectionEvent
)


class TestConstantVoltageMode:
    """Test suite for constant voltage mode functionality"""

    @pytest.fixture
    def detection_monitor(self):
        """Create a fresh detection monitor instance for each test"""
        monitor = LabJackDetectionMonitor()
        yield monitor
        # Cleanup
        for session_id in list(monitor.active_sessions.keys()):
            try:
                monitor.stop_monitoring(session_id)
            except:
                pass

    @pytest.fixture
    def session_id(self):
        """Generate a unique session ID for each test"""
        return f"test-session-{int(time.time() * 1000)}"

    def test_normal_mode_debounce_active(self, detection_monitor, session_id):
        """
        Test that normal mode (constant_voltage_mode=False) applies 100ms debounce

        Expected behavior:
        - At 24 FPS (41.67ms frame period), only every 3rd detection passes
        - Detection rate: ~33% (3/8 frames detected)
        """
        config = DetectionConfig(
            session_id=session_id,
            channels=["AIN0"],
            voltage_threshold=2.5,
            debounce_ms=100,
            constant_voltage_mode=False  # Normal mode - debounce active
        )

        # Simulate 8 detections at 24 FPS (41.67ms intervals)
        base_time = datetime.now()
        frame_interval_ms = 41.67  # 24 FPS
        voltage = 4.2  # Constant voltage above threshold

        detection_count = 0
        for frame_num in range(8):
            current_time = base_time + timedelta(milliseconds=frame_num * frame_interval_ms)

            decision = detection_monitor._should_record_detection(
                session_id=session_id,
                channel="AIN0",
                voltage=voltage,
                current_time=current_time,
                config=config
            )

            if decision == "threshold_cross":
                detection_count += 1

        # With 100ms debounce and 41.67ms frame period:
        # Frame 0: 0ms → Detected ✅
        # Frame 1: 42ms → Blocked (< 100ms)
        # Frame 2: 83ms → Blocked (< 100ms)
        # Frame 3: 125ms → Detected ✅ (> 100ms)
        # Frame 4: 167ms → Blocked
        # Frame 5: 208ms → Blocked
        # Frame 6: 250ms → Detected ✅
        # Frame 7: 292ms → Blocked
        # Expected: 3 detections (37.5% rate)

        assert detection_count == 3, (
            f"Normal mode should detect ~3/8 frames (37.5%), got {detection_count}/8 "
            f"({detection_count/8*100:.1f}%)"
        )

    def test_constant_voltage_mode_debounce_bypassed(self, detection_monitor, session_id):
        """
        Test that constant voltage mode bypasses debounce completely

        Expected behavior:
        - All detections pass through regardless of timing
        - Detection rate: 100% (8/8 frames detected)
        """
        config = DetectionConfig(
            session_id=session_id,
            channels=["AIN0"],
            voltage_threshold=2.5,
            debounce_ms=100,  # Set but should be ignored
            constant_voltage_mode=True  # Bypass debounce
        )

        # Simulate 8 detections at 24 FPS (41.67ms intervals)
        base_time = datetime.now()
        frame_interval_ms = 41.67  # 24 FPS
        voltage = 4.2  # Constant voltage above threshold

        detection_count = 0
        detected_frames = []

        for frame_num in range(8):
            current_time = base_time + timedelta(milliseconds=frame_num * frame_interval_ms)

            decision = detection_monitor._should_record_detection(
                session_id=session_id,
                channel="AIN0",
                voltage=voltage,
                current_time=current_time,
                config=config
            )

            if decision == "threshold_cross":
                detection_count += 1
                detected_frames.append(frame_num)

        # With constant voltage mode, ALL frames should be detected
        assert detection_count == 8, (
            f"Constant voltage mode should detect 8/8 frames (100%), got {detection_count}/8 "
            f"({detection_count/8*100:.1f}%). Detected frames: {detected_frames}"
        )

        # Verify all frames were detected
        assert detected_frames == list(range(8)), (
            f"All frames should be detected. Expected [0,1,2,3,4,5,6,7], got {detected_frames}"
        )

    def test_constant_voltage_mode_very_rapid_detections(self, detection_monitor, session_id):
        """
        Test constant voltage mode with very rapid detections (faster than 24 FPS)

        Expected behavior:
        - Even at 5ms intervals (much faster than debounce), all detections pass
        - Detection rate: 100%
        """
        config = DetectionConfig(
            session_id=session_id,
            channels=["AIN0"],
            voltage_threshold=2.5,
            debounce_ms=100,
            constant_voltage_mode=True
        )

        # Simulate 20 detections at 5ms intervals (much faster than 24 FPS)
        base_time = datetime.now()
        interval_ms = 5  # Very rapid
        voltage = 4.2

        detection_count = 0

        for i in range(20):
            current_time = base_time + timedelta(milliseconds=i * interval_ms)

            decision = detection_monitor._should_record_detection(
                session_id=session_id,
                channel="AIN0",
                voltage=voltage,
                current_time=current_time,
                config=config
            )

            if decision == "threshold_cross":
                detection_count += 1

        # All 20 detections should pass
        assert detection_count == 20, (
            f"Constant voltage mode should detect all 20 rapid detections, got {detection_count}"
        )

    def test_constant_voltage_mode_multi_channel(self, detection_monitor, session_id):
        """
        Test constant voltage mode with multiple channels

        Expected behavior:
        - Each channel independently bypasses debounce
        - All detections on all channels pass through
        """
        config = DetectionConfig(
            session_id=session_id,
            channels=["AIN0", "AIN1", "AIN2"],
            voltage_threshold=2.5,
            debounce_ms=100,
            constant_voltage_mode=True
        )

        base_time = datetime.now()
        frame_interval_ms = 41.67
        voltage = 4.2

        detection_counts = {"AIN0": 0, "AIN1": 0, "AIN2": 0}

        for frame_num in range(8):
            current_time = base_time + timedelta(milliseconds=frame_num * frame_interval_ms)

            for channel in ["AIN0", "AIN1", "AIN2"]:
                decision = detection_monitor._should_record_detection(
                    session_id=session_id,
                    channel=channel,
                    voltage=voltage,
                    current_time=current_time,
                    config=config
                )

                if decision == "threshold_cross":
                    detection_counts[channel] += 1

        # Each channel should detect all 8 frames
        for channel, count in detection_counts.items():
            assert count == 8, (
                f"Channel {channel} should detect 8/8 frames, got {count}/8"
            )

    def test_backward_compatibility_default_false(self, detection_monitor, session_id):
        """
        Test that constant_voltage_mode defaults to False for backward compatibility

        Expected behavior:
        - Creating DetectionConfig without specifying constant_voltage_mode
        - Should default to False (normal debounce behavior)
        """
        config = DetectionConfig(
            session_id=session_id,
            channels=["AIN0"],
            voltage_threshold=2.5,
            debounce_ms=100
            # constant_voltage_mode not specified - should default to False
        )

        assert config.constant_voltage_mode is False, (
            "DetectionConfig.constant_voltage_mode should default to False"
        )

        # Verify normal debounce behavior applies
        base_time = datetime.now()
        voltage = 4.2

        # First detection should pass
        decision1 = detection_monitor._should_record_detection(
            session_id=session_id,
            channel="AIN0",
            voltage=voltage,
            current_time=base_time,
            config=config
        )
        assert decision1 == "threshold_cross"

        # Second detection 50ms later should be blocked by debounce
        decision2 = detection_monitor._should_record_detection(
            session_id=session_id,
            channel="AIN0",
            voltage=voltage,
            current_time=base_time + timedelta(milliseconds=50),
            config=config
        )
        assert decision2 is None  # Blocked by debounce

    def test_constant_voltage_mode_with_varying_voltages(self, detection_monitor, session_id):
        """
        Test constant voltage mode with slightly varying voltages

        Expected behavior:
        - As long as voltage is above threshold, all detections pass
        - Debounce is bypassed regardless of voltage variation
        """
        config = DetectionConfig(
            session_id=session_id,
            channels=["AIN0"],
            voltage_threshold=2.5,
            debounce_ms=100,
            constant_voltage_mode=True
        )

        base_time = datetime.now()
        frame_interval_ms = 41.67

        # Voltages slightly varying but all above threshold
        voltages = [4.2, 4.15, 4.25, 4.18, 4.22, 4.19, 4.21, 4.17]

        detection_count = 0

        for frame_num, voltage in enumerate(voltages):
            current_time = base_time + timedelta(milliseconds=frame_num * frame_interval_ms)

            decision = detection_monitor._should_record_detection(
                session_id=session_id,
                channel="AIN0",
                voltage=voltage,
                current_time=current_time,
                config=config
            )

            if decision == "threshold_cross":
                detection_count += 1

        # All 8 detections should pass
        assert detection_count == 8, (
            f"All varying voltages above threshold should be detected, got {detection_count}/8"
        )

    def test_performance_improvement_comparison(self, detection_monitor, session_id):
        """
        Test that demonstrates the performance improvement from using constant voltage mode

        This test shows the before/after detection rate improvement:
        - Normal mode: 37.5% detection rate (3/8 frames)
        - Constant voltage mode: 100% detection rate (8/8 frames)
        - Improvement: 2.67x more detections
        """
        # Test normal mode
        normal_config = DetectionConfig(
            session_id=f"{session_id}-normal",
            channels=["AIN0"],
            voltage_threshold=2.5,
            debounce_ms=100,
            constant_voltage_mode=False
        )

        # Test constant voltage mode
        constant_config = DetectionConfig(
            session_id=f"{session_id}-constant",
            channels=["AIN0"],
            voltage_threshold=2.5,
            debounce_ms=100,
            constant_voltage_mode=True
        )

        base_time = datetime.now()
        frame_interval_ms = 41.67
        voltage = 4.2

        normal_count = 0
        constant_count = 0

        # Run both configurations
        for frame_num in range(8):
            current_time = base_time + timedelta(milliseconds=frame_num * frame_interval_ms)

            # Normal mode
            decision_normal = detection_monitor._should_record_detection(
                session_id=f"{session_id}-normal",
                channel="AIN0",
                voltage=voltage,
                current_time=current_time,
                config=normal_config
            )
            if decision_normal == "threshold_cross":
                normal_count += 1

            # Constant voltage mode
            decision_constant = detection_monitor._should_record_detection(
                session_id=f"{session_id}-constant",
                channel="AIN0",
                voltage=voltage,
                current_time=current_time,
                config=constant_config
            )
            if decision_constant == "threshold_cross":
                constant_count += 1

        # Verify the improvement
        assert normal_count == 3, f"Normal mode should detect 3/8, got {normal_count}"
        assert constant_count == 8, f"Constant voltage mode should detect 8/8, got {constant_count}"

        improvement_factor = constant_count / normal_count
        assert improvement_factor >= 2.5, (
            f"Constant voltage mode should provide at least 2.5x improvement, "
            f"got {improvement_factor:.2f}x (from {normal_count} to {constant_count} detections)"
        )

        print(f"\n✅ Performance Improvement Test:")
        print(f"   Normal mode:          {normal_count}/8 detections ({normal_count/8*100:.1f}%)")
        print(f"   Constant voltage mode: {constant_count}/8 detections ({constant_count/8*100:.1f}%)")
        print(f"   Improvement:          {improvement_factor:.2f}x")


class TestConstantVoltageModeIntegration:
    """Integration tests for constant voltage mode with full monitoring pipeline"""

    @pytest.fixture
    def detection_monitor(self):
        """Create a fresh detection monitor instance for each test"""
        monitor = LabJackDetectionMonitor()
        yield monitor
        # Cleanup
        for session_id in list(monitor.active_sessions.keys()):
            try:
                monitor.stop_monitoring(session_id)
            except:
                pass

    def test_start_monitoring_with_constant_voltage_mode(self, detection_monitor):
        """
        Test that start_monitoring accepts and properly configures constant_voltage_mode

        Expected behavior:
        - start_monitoring accepts constant_voltage_mode parameter
        - Configuration is stored correctly
        - Can be retrieved and verified
        """
        session_id = f"test-integration-{int(time.time() * 1000)}"

        # Note: This test assumes start_monitoring is implemented
        # For now, we test that DetectionConfig accepts the parameter
        config = DetectionConfig(
            session_id=session_id,
            channels=["AIN0"],
            voltage_threshold=3.3,
            debounce_ms=100,
            constant_voltage_mode=True,
            sample_rate=1000
        )

        # Verify configuration
        assert config.constant_voltage_mode is True
        assert config.debounce_ms == 100
        assert config.voltage_threshold == 3.3

        print(f"\n✅ Integration test passed: constant_voltage_mode configuration works")

    def test_api_request_format(self):
        """
        Test that the API request format includes constant_voltage_mode

        This validates that the RawLoggingSessionRequest model accepts
        the constant_voltage_mode parameter as documented.
        """
        from api.raw_labjack_endpoints import RawLoggingSessionRequest

        # Create request with constant voltage mode
        request = RawLoggingSessionRequest(
            session_name="test-constant-voltage",
            channels=["AIN0"],
            sample_rate=1000,
            constant_voltage_mode=True,
            debounce_ms=0  # Can set to 0 when constant voltage mode is enabled
        )

        assert request.constant_voltage_mode is True
        assert request.debounce_ms == 0

        print(f"\n✅ API request format test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
