"""
Test Detection Rate Improvement

This test verifies that the frame buffer service fixes the detection rate
bottleneck, improving detection rate from 67% to 95%+.

Test Scenarios:
1. High-frequency detection scenario (simulates constant voltage)
2. Frame buffer prevents drops
3. Backpressure mechanism works
4. Detection rate monitoring alerts
"""

import pytest
import asyncio
import time
import numpy as np
from typing import List, Dict, Any
from unittest.mock import Mock, patch, AsyncMock

from services.frame_buffer_service import (
    FrameBufferService,
    DetectionRateMonitor,
    FrameData,
    get_frame_buffer,
    cleanup_frame_buffer
)


class TestFrameBufferService:
    """Test frame buffer service functionality"""

    @pytest.mark.asyncio
    async def test_frame_buffer_initialization(self):
        """Test that frame buffer initializes correctly"""
        buffer = FrameBufferService(max_buffer_size=100, backpressure_threshold=0.8)
        buffer.initialize()

        assert buffer.is_active is True
        assert buffer.frame_queue is not None
        assert buffer.metrics.frames_received == 0
        assert buffer.metrics.frames_processed == 0

        buffer.stop()

    @pytest.mark.asyncio
    async def test_frame_buffer_adds_frames(self):
        """Test adding frames to buffer"""
        buffer = FrameBufferService(max_buffer_size=10)
        buffer.initialize()

        # Create test frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_data = FrameData(
            frame_number=1,
            timestamp=0.033,
            frame=frame,
            video_timestamp=0.033
        )

        # Add frame
        result = await buffer.add_frame(frame_data, block=False)

        assert result is True
        assert buffer.metrics.frames_received == 1
        assert buffer.metrics.frames_in_buffer == 1

        buffer.stop()

    @pytest.mark.asyncio
    async def test_frame_buffer_detects_drops(self):
        """Test that frame buffer detects dropped frames"""
        buffer = FrameBufferService(max_buffer_size=100)
        buffer.initialize()

        # Add frame 1
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        await buffer.add_frame(FrameData(1, 0.033, frame, 0.033), block=False)

        # Skip frames 2-4, add frame 5 (simulates 3 dropped frames)
        await buffer.add_frame(FrameData(5, 0.167, frame, 0.167), block=False)

        # Check metrics
        assert buffer.metrics.frames_received == 2
        assert buffer.metrics.frames_dropped == 3  # Frames 2, 3, 4
        assert len(buffer.dropped_frame_ranges) == 1
        assert buffer.dropped_frame_ranges[0] == (2, 4)

        buffer.stop()

    @pytest.mark.asyncio
    async def test_frame_buffer_handles_full_buffer(self):
        """Test behavior when buffer is full"""
        buffer = FrameBufferService(max_buffer_size=5)
        buffer.initialize()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Fill buffer
        for i in range(5):
            result = await buffer.add_frame(
                FrameData(i + 1, (i + 1) * 0.033, frame, (i + 1) * 0.033),
                block=False
            )
            assert result is True

        # Try to add one more (should drop)
        result = await buffer.add_frame(
            FrameData(6, 0.200, frame, 0.200),
            block=False
        )

        assert result is False
        assert buffer.metrics.buffer_full_events == 1

        buffer.stop()

    @pytest.mark.asyncio
    async def test_frame_buffer_get_frame(self):
        """Test retrieving frames from buffer"""
        buffer = FrameBufferService(max_buffer_size=10)
        buffer.initialize()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_data = FrameData(1, 0.033, frame, 0.033)

        await buffer.add_frame(frame_data, block=False)

        # Retrieve frame
        retrieved = await buffer.get_frame(timeout=1.0)

        assert retrieved is not None
        assert retrieved.frame_number == 1
        assert buffer.metrics.frames_in_buffer == 0

        buffer.stop()

    @pytest.mark.asyncio
    async def test_backpressure_detection(self):
        """Test backpressure detection when buffer fills up"""
        buffer = FrameBufferService(max_buffer_size=10, backpressure_threshold=0.8)
        buffer.initialize()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Fill buffer to 50% - no backpressure
        for i in range(5):
            await buffer.add_frame(
                FrameData(i + 1, (i + 1) * 0.033, frame, (i + 1) * 0.033),
                block=False
            )

        assert buffer.should_apply_backpressure() is False

        # Fill to 90% - backpressure should trigger
        for i in range(4):
            await buffer.add_frame(
                FrameData(i + 6, (i + 6) * 0.033, frame, (i + 6) * 0.033),
                block=False
            )

        assert buffer.should_apply_backpressure() is True

        buffer.stop()

    @pytest.mark.asyncio
    async def test_processing_time_tracking(self):
        """Test that processing times are tracked correctly"""
        buffer = FrameBufferService(max_buffer_size=10)
        buffer.initialize()

        # Record processing times
        buffer.record_processing_time(50.0)
        buffer.record_processing_time(75.0)
        buffer.record_processing_time(100.0)

        metrics = buffer.get_metrics()

        assert metrics["frames_processed"] == 3
        assert metrics["avg_processing_time_ms"] == 75.0
        assert metrics["max_processing_time_ms"] == 100.0

        buffer.stop()


class TestDetectionRateMonitor:
    """Test detection rate monitoring"""

    def test_monitor_initialization(self):
        """Test monitor initializes correctly"""
        monitor = DetectionRateMonitor(expected_fps=30.0, min_detection_rate=0.95)

        assert monitor.expected_fps == 30.0
        assert monitor.min_detection_rate == 0.95
        assert monitor.detection_count == 0

    def test_monitor_records_detections(self):
        """Test that monitor records detections"""
        monitor = DetectionRateMonitor(expected_fps=30.0, min_detection_rate=0.95)

        # Record some detections
        for _ in range(10):
            monitor.record_detection()

        assert monitor.detection_count == 10

    def test_monitor_detects_low_rate(self):
        """Test that monitor detects low detection rate"""
        monitor = DetectionRateMonitor(expected_fps=10.0, min_detection_rate=0.95)

        # Simulate 1 second elapsed with only 5 detections (50% rate)
        time.sleep(1.1)
        for _ in range(5):
            monitor.record_detection()

        stats = monitor.get_stats()

        assert stats["actual_rate"] < stats["min_rate"]
        assert stats["is_acceptable"] is False
        assert stats["missed_count"] > 0
        assert len(monitor.alerts) > 0

    def test_monitor_stats(self):
        """Test getting monitor statistics"""
        monitor = DetectionRateMonitor(expected_fps=10.0, min_detection_rate=0.95)

        # Simulate perfect detection rate
        time.sleep(0.5)
        for _ in range(5):
            monitor.record_detection()

        stats = monitor.get_stats()

        assert "detection_count" in stats
        assert "expected_count" in stats
        assert "actual_rate" in stats
        assert "missed_count" in stats
        assert stats["detection_count"] == 5


class TestHighFrequencyDetection:
    """Test high-frequency detection scenario (simulates constant voltage test)"""

    @pytest.mark.asyncio
    async def test_constant_voltage_simulation(self):
        """
        Simulate constant voltage test scenario

        This test simulates the scenario from the investigation report:
        - Video with 257 expected detections
        - Constant voltage (all frames should be detected)
        - Verify detection rate > 95%
        """
        buffer = FrameBufferService(max_buffer_size=120)
        buffer.initialize()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        total_frames = 257
        processed_frames = 0

        # Producer: Add frames at 30fps rate
        async def produce_frames():
            for i in range(total_frames):
                frame_data = FrameData(
                    frame_number=i + 1,
                    timestamp=(i + 1) / 30.0,
                    frame=frame,
                    video_timestamp=(i + 1) / 30.0
                )
                await buffer.add_frame(frame_data, block=True)
                await asyncio.sleep(0.001)  # Small delay to simulate video reading

        # Consumer: Process frames (simulate slower inference)
        async def process_frames():
            nonlocal processed_frames
            while processed_frames < total_frames:
                frame_data = await buffer.get_frame(timeout=1.0)
                if frame_data is None:
                    break

                # Simulate model inference (25ms)
                start_time = time.time()
                await asyncio.sleep(0.025)
                processing_time = (time.time() - start_time) * 1000

                buffer.record_processing_time(processing_time)
                processed_frames += 1

        # Run producer and consumer concurrently
        await asyncio.gather(
            produce_frames(),
            process_frames()
        )

        # Check metrics
        metrics = buffer.get_metrics()
        detection_rate = metrics["detection_rate_percent"]

        print(f"\n=== Test Results ===")
        print(f"Total frames: {total_frames}")
        print(f"Frames received: {metrics['frames_received']}")
        print(f"Frames processed: {metrics['frames_processed']}")
        print(f"Frames dropped: {metrics['frames_dropped']}")
        print(f"Detection rate: {detection_rate:.2f}%")
        print(f"Avg processing time: {metrics['avg_processing_time_ms']:.2f}ms")

        # Assert detection rate > 95%
        assert detection_rate >= 95.0, f"Detection rate {detection_rate:.2f}% < 95%"
        assert metrics["frames_dropped"] < 13, f"Too many dropped frames: {metrics['frames_dropped']}"

        buffer.stop()

    @pytest.mark.asyncio
    async def test_buffer_prevents_drops_under_load(self):
        """Test that buffer prevents drops even with variable processing times"""
        buffer = FrameBufferService(max_buffer_size=120)
        buffer.initialize()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        total_frames = 100
        processed_frames = 0

        async def produce_frames():
            for i in range(total_frames):
                frame_data = FrameData(
                    frame_number=i + 1,
                    timestamp=(i + 1) / 30.0,
                    frame=frame,
                    video_timestamp=(i + 1) / 30.0
                )
                await buffer.add_frame(frame_data, block=True)

        async def process_frames_variable_speed():
            nonlocal processed_frames
            while processed_frames < total_frames:
                frame_data = await buffer.get_frame(timeout=1.0)
                if frame_data is None:
                    break

                # Simulate variable processing time (20-50ms)
                processing_time = 20 + (processed_frames % 3) * 10
                await asyncio.sleep(processing_time / 1000.0)

                buffer.record_processing_time(processing_time)
                processed_frames += 1

        await asyncio.gather(
            produce_frames(),
            process_frames_variable_speed()
        )

        metrics = buffer.get_metrics()

        # With buffer, all frames should be processed
        assert metrics["frames_processed"] == total_frames
        assert metrics["frames_dropped"] == 0
        assert metrics["detection_rate_percent"] == 100.0

        buffer.stop()

    @pytest.mark.asyncio
    async def test_detection_rate_monitor_integration(self):
        """Test detection rate monitor with frame buffer"""
        buffer = FrameBufferService(max_buffer_size=120)
        buffer.initialize()

        monitor = DetectionRateMonitor(expected_fps=30.0, min_detection_rate=0.95)

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        total_frames = 90  # 3 seconds at 30fps

        async def produce_and_process():
            for i in range(total_frames):
                frame_data = FrameData(
                    frame_number=i + 1,
                    timestamp=(i + 1) / 30.0,
                    frame=frame,
                    video_timestamp=(i + 1) / 30.0
                )
                await buffer.add_frame(frame_data, block=True)

                # Process immediately
                retrieved = await buffer.get_frame(timeout=0.1)
                if retrieved:
                    buffer.record_processing_time(25.0)
                    monitor.record_detection()

                await asyncio.sleep(0.001)

        await produce_and_process()

        stats = monitor.get_stats()
        metrics = buffer.get_metrics()

        print(f"\n=== Monitor Stats ===")
        print(f"Detection count: {stats['detection_count']}")
        print(f"Expected count: {stats['expected_count']}")
        print(f"Actual rate: {stats['actual_rate_percent']:.2f}%")
        print(f"Is acceptable: {stats['is_acceptable']}")

        assert stats["is_acceptable"] is True
        assert stats["actual_rate"] >= 0.95

        buffer.stop()


class TestBufferSessionManagement:
    """Test buffer session management functions"""

    @pytest.mark.asyncio
    async def test_get_frame_buffer(self):
        """Test getting frame buffer for session"""
        session_id = "test-session-123"

        buffer1 = get_frame_buffer(session_id, max_buffer_size=50)
        buffer2 = get_frame_buffer(session_id)

        # Should return same instance
        assert buffer1 is buffer2
        assert buffer1.max_buffer_size == 50

        cleanup_frame_buffer(session_id)

    @pytest.mark.asyncio
    async def test_cleanup_frame_buffer(self):
        """Test cleaning up frame buffer"""
        session_id = "test-session-456"

        buffer = get_frame_buffer(session_id)
        buffer.initialize()

        assert buffer.is_active is True

        cleanup_frame_buffer(session_id)

        # After cleanup, should get new instance
        new_buffer = get_frame_buffer(session_id)
        assert new_buffer is not buffer


@pytest.mark.integration
class TestIntegrationScenarios:
    """Integration tests for real-world scenarios"""

    @pytest.mark.asyncio
    async def test_video_sequence_detection(self):
        """
        Test detection across multiple videos (from investigation report)

        Simulates:
        - Video 1: 131 frames
        - Video 2: 126 frames
        - Total: 257 frames (constant voltage)
        - Expected: >95% detection rate
        """
        buffer = FrameBufferService(max_buffer_size=120)
        buffer.initialize()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Video 1: 131 frames
        video1_frames = 131
        # Video 2: 126 frames
        video2_frames = 126

        total_frames = video1_frames + video2_frames
        processed_count = 0

        async def process_video_sequence():
            nonlocal processed_count

            # Video 1
            for i in range(video1_frames):
                frame_data = FrameData(
                    frame_number=i + 1,
                    timestamp=(i + 1) / 30.0,
                    frame=frame,
                    video_timestamp=(i + 1) / 30.0,
                    metadata={"video_id": "video1"}
                )
                await buffer.add_frame(frame_data, block=True)

            # Video 2
            for i in range(video2_frames):
                frame_data = FrameData(
                    frame_number=video1_frames + i + 1,
                    timestamp=(video1_frames + i + 1) / 30.0,
                    frame=frame,
                    video_timestamp=(i + 1) / 30.0,  # Reset timestamp for new video
                    metadata={"video_id": "video2"}
                )
                await buffer.add_frame(frame_data, block=True)

        async def process_frames():
            nonlocal processed_count
            while processed_count < total_frames:
                frame_data = await buffer.get_frame(timeout=2.0)
                if frame_data is None:
                    break

                # Simulate inference
                await asyncio.sleep(0.025)
                buffer.record_processing_time(25.0)
                processed_count += 1

        await asyncio.gather(
            process_video_sequence(),
            process_frames()
        )

        metrics = buffer.get_metrics()

        print(f"\n=== Video Sequence Test ===")
        print(f"Video 1 frames: {video1_frames}")
        print(f"Video 2 frames: {video2_frames}")
        print(f"Total frames: {total_frames}")
        print(f"Processed: {metrics['frames_processed']}")
        print(f"Detection rate: {metrics['detection_rate_percent']:.2f}%")

        # From investigation: Video 1 was 56.5%, Video 2 was 78.6%
        # With buffer: should be >95% for both
        assert metrics["detection_rate_percent"] >= 95.0

        buffer.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
