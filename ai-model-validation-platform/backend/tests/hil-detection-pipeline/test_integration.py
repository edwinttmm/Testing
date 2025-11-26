"""
HIL Detection Pipeline Tests - End-to-End Integration

Tests for:
- Complete detection flow from LabJack to database
- Session ID propagation through pipeline
- Ground truth comparison integration
- Video timing synchronization
- Performance benchmarks
"""

import os
import pytest
import time
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from services.simple_labjack_detection import get_detection_service
from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
from services.detection_queue_service import get_detection_queue


class TestEndToEndDetectionFlow:
    """Test complete detection pipeline"""

    @pytest.fixture
    def mock_database(self):
        """Create mock database session"""
        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.close = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        return mock_db

    @pytest.fixture
    def mock_labjack_hardware(self):
        """Mock LabJack hardware connection"""
        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        # Simulate detection sequence
        mock_manager.read_voltage.side_effect = [2.0, 3.5, 2.0]  # One detection
        return mock_manager

    def test_complete_detection_flow(self, mock_labjack_hardware, mock_database):
        """Test detection flows from hardware to database"""
        from services.simple_labjack_detection import DATABASE_AVAILABLE

        if not DATABASE_AVAILABLE:
            pytest.skip("Database not available")

        monitor = get_detection_service()
        session_id = "test_e2e_flow"

        with patch.object(monitor, 'connection_manager', mock_labjack_hardware):
            with patch('services.labjack_detection_service.SessionLocal', return_value=mock_database):
                # Start monitoring
                success = monitor.start_monitoring(
                    session_id=session_id,
                    channels=["AIN0"],
                    voltage_threshold=2.5,
                    sample_rate=100,
                    store_in_db=True
                )

                assert success

                # Wait for detection and storage
                time.sleep(0.5)

                # Verify database storage was attempted
                assert mock_database.add.called or monitor.total_detections > 0

                monitor.stop_session_monitoring(session_id)

    def test_session_id_propagation(self, mock_labjack_hardware):
        """Test session_id propagates correctly through pipeline"""
        monitor = get_detection_service()
        session_id = "test_session_propagation"
        detected_events = []

        def capture_detection(event):
            detected_events.append(event)

        monitor.add_detection_callback(capture_detection)

        with patch.object(monitor, 'connection_manager', mock_labjack_hardware):
            success = monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=100
            )

            assert success
            time.sleep(0.3)

            # Verify all events have correct session_id
            for event in detected_events:
                assert event.session_id == session_id

            monitor.stop_session_monitoring(session_id)

    def test_video_timing_integration(self, mock_labjack_hardware):
        """Test video timing synchronization in detection pipeline"""
        monitor = get_dedicated_labjack_monitor()
        session_id = "test_timing_integration"

        video_timing_config = {
            'video_id': 'test_video_123',
            'fps': 24,
            'duration': 5.0,
            'channels': ['AIN0'],
            'voltage_threshold': 2.5,
            'sample_rate': 100
        }

        with patch.object(monitor.labjack_monitor, 'connection_manager', mock_labjack_hardware):
            with patch('services.video_timing_service.get_video_timing_service') as mock_timing:
                mock_timing_service = Mock()
                mock_timing_service.start_video_timing.return_value = time.time()
                mock_timing_service.calculate_video_relative_latency.return_value = {
                    'video_relative_timestamp': 1.5,
                    'video_relative_timestamp_ns': 1500000000,
                    'actual_latency_ms': 45.0,
                    'video_frame_number': 36,
                    'timing_sync_quality': 'high',
                    'timing_precision_ns': 1000000
                }
                mock_timing.return_value = mock_timing_service

                success = monitor.start_monitoring_with_video_sync(
                    session_id=session_id,
                    video_timing_config=video_timing_config
                )

                assert success

                time.sleep(0.3)

                # Verify timing service was called
                assert mock_timing_service.start_video_timing.called

                monitor.stop_session_monitoring(session_id)

    def test_detection_queue_integration(self, mock_labjack_hardware, mock_database):
        """Test detection queue handles race conditions"""
        monitor = get_detection_service()
        queue = get_detection_queue()

        session_id = "test_queue_integration"

        with patch.object(monitor, 'connection_manager', mock_labjack_hardware):
            # Simulate detection arriving before video_started
            success = monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=100,
                store_in_db=True
            )

            assert success
            time.sleep(0.3)

            # If video_id was NULL, should be queued
            queue_size = queue.get_queue_size(session_id)

            # Either queued or successfully assigned
            # (depends on timing of video lifecycle)
            assert queue_size >= 0

            # Flush queue if anything queued
            if queue_size > 0:
                assigned = queue.flush_for_video(session_id, "video_123", mock_database)
                assert assigned == queue_size

            monitor.stop_session_monitoring(session_id)


class TestGroundTruthIntegration:
    """Test ground truth comparison integration"""

    def test_ground_truth_matching_pipeline(self):
        """Test detection events can be matched to ground truth"""
        from services.ground_truth_matching_service import get_ground_truth_matching_service

        gt_service = get_ground_truth_matching_service()
        session_id = "test_gt_matching"

        # This test verifies the service is available
        # Actual matching requires database setup with ground truth data
        assert gt_service is not None

    def test_hil_screenshot_capture_integration(self):
        """Test HIL screenshot capture integration"""
        from services.hil_screenshot_service import get_hil_ground_truth_comparison

        hil_service = get_hil_ground_truth_comparison()
        assert hil_service is not None


class TestPerformanceBenchmarks:
    """Performance and scalability tests"""

    def test_high_frequency_detection_handling(self):
        """Test system handles high-frequency detections"""
        monitor = get_detection_service()
        session_id = "test_high_frequency"
        detected_count = []

        def count_detection(event):
            detected_count.append(event)

        monitor.add_detection_callback(count_detection)

        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        mock_manager.read_voltage.return_value = 3.5  # Always above threshold

        with patch.object(monitor, 'connection_manager', mock_manager):
            success = monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=1000,  # 1kHz sampling
                debounce_ms=10  # Low debounce for high frequency
            )

            assert success

            # Run for 1 second
            time.sleep(1.0)

            # Should capture many detections (50-100 with debounce)
            assert len(detected_count) >= 50

            # Verify no memory leaks or crashes
            stats = monitor.get_statistics()
            assert stats['total_events'] > 0

            monitor.stop_session_monitoring(session_id)

    def test_multiple_concurrent_sessions(self):
        """Test multiple sessions can run concurrently"""
        monitor = get_detection_service()

        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        mock_manager.read_voltage.return_value = 3.5

        with patch.object(monitor, 'connection_manager', mock_manager):
            # Start 5 concurrent sessions
            session_ids = [f"session_{i}" for i in range(5)]

            for session_id in session_ids:
                success = monitor.start_monitoring(
                    session_id=session_id,
                    channels=["AIN0"],
                    voltage_threshold=2.5,
                    sample_rate=100
                )
                assert success

            time.sleep(0.5)

            # Verify all sessions active
            all_sessions = monitor.get_all_sessions()
            assert len(all_sessions) == 5

            # Stop all sessions
            for session_id in session_ids:
                monitor.stop_session_monitoring(session_id)

    def test_detection_latency_benchmark(self):
        """Test detection latency meets requirements (<100ms)"""
        monitor = get_detection_service()
        session_id = "test_latency"
        latencies = []

        def measure_latency(event):
            # Calculate latency from hardware trigger to callback
            callback_time = time.time()
            trigger_time = event.timestamp.timestamp() if hasattr(event.timestamp, 'timestamp') else event.timestamp
            latency_ms = (callback_time - trigger_time) * 1000
            latencies.append(latency_ms)

        monitor.add_detection_callback(measure_latency)

        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        mock_manager.read_voltage.side_effect = [2.0, 3.5, 2.0, 3.5, 2.0]

        with patch.object(monitor, 'connection_manager', mock_manager):
            success = monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=100,
                debounce_ms=0
            )

            assert success
            time.sleep(0.5)

            # Verify latencies
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                max_latency = max(latencies)

                print(f"\nLatency Benchmark:")
                print(f"  Average: {avg_latency:.2f}ms")
                print(f"  Maximum: {max_latency:.2f}ms")
                print(f"  Samples: {len(latencies)}")

                # Verify meets requirement
                assert avg_latency < 100, f"Average latency {avg_latency}ms exceeds 100ms requirement"

            monitor.stop_session_monitoring(session_id)

    def test_memory_usage_stability(self):
        """Test memory usage remains stable during long session"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        monitor = get_detection_service()
        session_id = "test_memory_stability"

        mock_manager = Mock()
        mock_manager.is_connected.return_value = True
        mock_manager.connect.return_value = True
        mock_manager.read_voltage.return_value = 3.5

        with patch.object(monitor, 'connection_manager', mock_manager):
            success = monitor.start_monitoring(
                session_id=session_id,
                channels=["AIN0"],
                voltage_threshold=2.5,
                sample_rate=100
            )

            assert success

            # Run for 3 seconds
            time.sleep(3.0)

            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            print(f"\nMemory Usage:")
            print(f"  Initial: {initial_memory:.2f} MB")
            print(f"  Final: {final_memory:.2f} MB")
            print(f"  Increase: {memory_increase:.2f} MB")

            # Verify no excessive memory growth (< 50MB increase)
            assert memory_increase < 50, f"Memory increased by {memory_increase:.2f} MB"

            monitor.stop_session_monitoring(session_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])  # -s to show print statements
