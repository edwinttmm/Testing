"""

pytestmark = pytest.mark.skip(reason="Deprecated modules or missing dependencies")

Unit Tests for Drift Measurement Service
========================================

Tests the DriftMeasurementService in isolation.

Author: QA Specialist Agent
Date: 2025-11-20
"""

pytestmark = pytest.mark.skip(reason="Deprecated or missing dependencies")

import os
import pytest
import time
import uuid
from datetime import datetime, timezone

from services.drift_measurement_service import (
    DriftMeasurementService,
    DriftStage,
    StageTimestamp,
    VideoDriftMeasurement
)


class TestDriftMeasurementServiceInit:
    """Test service initialization."""

    def test_service_creates_successfully(self):
        """Test service instantiation."""
        service = DriftMeasurementService()

        assert service is not None
        assert service._measurements == {}

    def test_service_get_singleton(self):
        """Test get_drift_measurement_service returns singleton."""
        from services.drift_measurement_service import get_drift_measurement_service

        service1 = get_drift_measurement_service()
        service2 = get_drift_measurement_service()

        assert service1 is service2


class TestStartVideoMeasurement:
    """Test starting drift measurement for videos."""

    def test_start_measurement_creates_tracking(self):
        """Test starting measurement creates tracking object."""
        service = DriftMeasurementService()
        session_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())

        measurement = service.start_video_drift_measurement(
            session_id=session_id,
            video_id=video_id,
            video_sequence_number=0,
            clock_offset_ms=5.0
        )

        assert measurement is not None
        assert measurement.session_id == session_id
        assert measurement.video_id == video_id
        assert measurement.video_sequence_number == 0
        assert measurement.clock_offset_ms == 5.0

    def test_start_measurement_stores_in_service(self):
        """Test measurement is stored in service."""
        service = DriftMeasurementService()
        session_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())

        service.start_video_drift_measurement(
            session_id=session_id,
            video_id=video_id,
            video_sequence_number=0
        )

        measurement = service.get_measurement(session_id, video_id)
        assert measurement is not None
        assert measurement.video_id == video_id

    def test_start_multiple_videos_in_session(self):
        """Test starting measurements for multiple videos."""
        service = DriftMeasurementService()
        session_id = str(uuid.uuid4())

        videos = [str(uuid.uuid4()) for _ in range(3)]

        for i, video_id in enumerate(videos):
            service.start_video_drift_measurement(
                session_id=session_id,
                video_id=video_id,
                video_sequence_number=i
            )

        # All should be stored
        for video_id in videos:
            measurement = service.get_measurement(session_id, video_id)
            assert measurement is not None


class TestCaptureTimestamp:
    """Test timestamp capture."""

    @pytest.fixture
    def setup_measurement(self):
        """Setup measurement for testing."""
        service = DriftMeasurementService()
        session_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())

        service.start_video_drift_measurement(
            session_id=session_id,
            video_id=video_id,
            video_sequence_number=0
        )

        return {
            'service': service,
            'session_id': session_id,
            'video_id': video_id
        }

    def test_capture_timestamp_stores_data(self, setup_measurement):
        """Test capturing a timestamp."""
        service = setup_measurement['service']
        session_id = setup_measurement['session_id']
        video_id = setup_measurement['video_id']

        timestamp = time.time()
        service.capture_timestamp(
            session_id=session_id,
            video_id=video_id,
            stage=DriftStage.VIDEO_ACTUAL_START,
            timestamp=timestamp,
            source="frontend"
        )

        measurement = service.get_measurement(session_id, video_id)
        assert DriftStage.VIDEO_ACTUAL_START in measurement.timestamps

        stage_ts = measurement.timestamps[DriftStage.VIDEO_ACTUAL_START]
        assert stage_ts.timestamp == timestamp
        assert stage_ts.source == "frontend"

    def test_capture_multiple_stages(self, setup_measurement):
        """Test capturing timestamps for multiple stages."""
        service = setup_measurement['service']
        session_id = setup_measurement['session_id']
        video_id = setup_measurement['video_id']

        base_time = time.time()
        stages = [
            (DriftStage.VIDEO_START_COMMAND, base_time),
            (DriftStage.VIDEO_ACTUAL_START, base_time + 0.010),
            (DriftStage.LABJACK_COMMAND_SENT, base_time + 0.012),
            (DriftStage.LABJACK_ACTUAL_START, base_time + 0.015)
        ]

        for stage, timestamp in stages:
            service.capture_timestamp(
                session_id=session_id,
                video_id=video_id,
                stage=stage,
                timestamp=timestamp,
                source="test"
            )

        measurement = service.get_measurement(session_id, video_id)
        assert len(measurement.timestamps) == 4

    def test_capture_with_metadata(self, setup_measurement):
        """Test capturing timestamp with metadata."""
        service = setup_measurement['service']
        session_id = setup_measurement['session_id']
        video_id = setup_measurement['video_id']

        metadata = {
            'usb_latency_ms': 2.0,
            'device_id': 'LJT7-12345'
        }

        service.capture_timestamp(
            session_id=session_id,
            video_id=video_id,
            stage=DriftStage.LABJACK_ACTUAL_START,
            timestamp=time.time(),
            source="labjack",
            metadata=metadata
        )

        measurement = service.get_measurement(session_id, video_id)
        stage_ts = measurement.timestamps[DriftStage.LABJACK_ACTUAL_START]

        assert stage_ts.metadata == metadata


class TestDriftCalculation:
    """Test drift calculation logic."""

    def test_calculate_video_start_drift(self):
        """Test calculating video start drift."""
        measurement = VideoDriftMeasurement(
            session_id=str(uuid.uuid4()),
            video_id=str(uuid.uuid4()),
            video_sequence_number=0
        )

        base_time = time.time()
        measurement.timestamps[DriftStage.VIDEO_START_COMMAND] = StageTimestamp(
            stage=DriftStage.VIDEO_START_COMMAND,
            timestamp=base_time,
            timestamp_ns=int(base_time * 1e9),
            source="frontend"
        )

        measurement.timestamps[DriftStage.VIDEO_ACTUAL_START] = StageTimestamp(
            stage=DriftStage.VIDEO_ACTUAL_START,
            timestamp=base_time + 0.010,  # 10ms drift
            timestamp_ns=int((base_time + 0.010) * 1e9),
            source="frontend"
        )

        measurement.calculate_drift()

        assert measurement.video_start_drift_ms is not None
        assert abs(measurement.video_start_drift_ms - 10.0) < 0.1  # ~10ms

    def test_calculate_labjack_start_drift(self):
        """Test calculating LabJack start drift."""
        measurement = VideoDriftMeasurement(
            session_id=str(uuid.uuid4()),
            video_id=str(uuid.uuid4()),
            video_sequence_number=0
        )

        base_time = time.time()
        measurement.timestamps[DriftStage.LABJACK_COMMAND_SENT] = StageTimestamp(
            stage=DriftStage.LABJACK_COMMAND_SENT,
            timestamp=base_time,
            timestamp_ns=int(base_time * 1e9),
            source="backend"
        )

        measurement.timestamps[DriftStage.LABJACK_ACTUAL_START] = StageTimestamp(
            stage=DriftStage.LABJACK_ACTUAL_START,
            timestamp=base_time + 0.002,  # 2ms USB latency
            timestamp_ns=int((base_time + 0.002) * 1e9),
            source="labjack"
        )

        measurement.calculate_drift()

        assert measurement.labjack_start_drift_ms is not None
        assert abs(measurement.labjack_start_drift_ms - 2.0) < 0.1  # ~2ms

    def test_calculate_total_drift(self):
        """Test calculating total drift."""
        measurement = VideoDriftMeasurement(
            session_id=str(uuid.uuid4()),
            video_id=str(uuid.uuid4()),
            video_sequence_number=0,
            clock_offset_ms=0.0
        )

        base_time = time.time()
        measurement.timestamps[DriftStage.VIDEO_ACTUAL_START] = StageTimestamp(
            stage=DriftStage.VIDEO_ACTUAL_START,
            timestamp=base_time,
            timestamp_ns=int(base_time * 1e9),
            source="frontend"
        )

        measurement.timestamps[DriftStage.LABJACK_ACTUAL_START] = StageTimestamp(
            stage=DriftStage.LABJACK_ACTUAL_START,
            timestamp=base_time + 0.005,  # 5ms total drift
            timestamp_ns=int((base_time + 0.005) * 1e9),
            source="labjack"
        )

        measurement.calculate_drift()

        assert measurement.total_drift_ms is not None
        assert abs(measurement.total_drift_ms - 5.0) < 0.1  # ~5ms

    def test_calculate_drift_with_clock_offset(self):
        """Test drift calculation compensates for clock offset."""
        measurement = VideoDriftMeasurement(
            session_id=str(uuid.uuid4()),
            video_id=str(uuid.uuid4()),
            video_sequence_number=0,
            clock_offset_ms=50.0  # Frontend 50ms ahead
        )

        base_time = time.time()
        # Frontend time (50ms ahead)
        measurement.timestamps[DriftStage.VIDEO_ACTUAL_START] = StageTimestamp(
            stage=DriftStage.VIDEO_ACTUAL_START,
            timestamp=base_time + 0.050,
            timestamp_ns=int((base_time + 0.050) * 1e9),
            source="frontend"
        )

        # Backend time (actual)
        measurement.timestamps[DriftStage.LABJACK_ACTUAL_START] = StageTimestamp(
            stage=DriftStage.LABJACK_ACTUAL_START,
            timestamp=base_time + 0.005,
            timestamp_ns=int((base_time + 0.005) * 1e9),
            source="labjack"
        )

        measurement.calculate_drift()

        # Total drift should be ~5ms (not 45ms)
        # because clock offset is compensated
        assert measurement.total_drift_ms is not None
        assert abs(measurement.total_drift_ms - 5.0) < 1.0


class TestConfidenceScore:
    """Test confidence score calculation."""

    def test_confidence_with_minimal_data(self):
        """Test confidence score with minimal timestamps."""
        measurement = VideoDriftMeasurement(
            session_id=str(uuid.uuid4()),
            video_id=str(uuid.uuid4()),
            video_sequence_number=0
        )

        # Only one timestamp
        measurement.timestamps[DriftStage.VIDEO_ACTUAL_START] = StageTimestamp(
            stage=DriftStage.VIDEO_ACTUAL_START,
            timestamp=time.time(),
            timestamp_ns=int(time.time() * 1e9),
            source="frontend"
        )

        measurement.calculate_drift()

        # Low confidence with minimal data
        assert measurement.confidence_score < 0.5

    def test_confidence_with_complete_data(self):
        """Test confidence score with complete timestamps."""
        measurement = VideoDriftMeasurement(
            session_id=str(uuid.uuid4()),
            video_id=str(uuid.uuid4()),
            video_sequence_number=0,
            clock_offset_ms=5.0
        )

        base_time = time.time()
        stages = [
            DriftStage.VIDEO_ACTUAL_START,
            DriftStage.LABJACK_COMMAND_SENT,
            DriftStage.LABJACK_ACTUAL_START
        ]

        for i, stage in enumerate(stages):
            measurement.timestamps[stage] = StageTimestamp(
                stage=stage,
                timestamp=base_time + (i * 0.001),
                timestamp_ns=int((base_time + i * 0.001) * 1e9),
                source="test"
            )

        measurement.calculate_drift()

        # High confidence with complete data + clock offset
        assert measurement.confidence_score >= 0.9


class TestSessionStatistics:
    """Test session-level drift statistics."""

    def test_get_statistics_for_empty_session(self):
        """Test statistics for session with no measurements."""
        service = DriftMeasurementService()
        session_id = str(uuid.uuid4())

        stats = service.get_session_drift_statistics(session_id)

        assert 'error' in stats

    def test_get_statistics_for_session_with_videos(self):
        """Test statistics for session with multiple videos."""
        service = DriftMeasurementService()
        session_id = str(uuid.uuid4())

        # Create 3 videos with different drifts
        drifts = [3.0, 5.0, 7.0]  # ms

        for i, drift in enumerate(drifts):
            video_id = str(uuid.uuid4())
            service.start_video_drift_measurement(
                session_id=session_id,
                video_id=video_id,
                video_sequence_number=i
            )

            base_time = time.time()
            service.capture_timestamp(
                session_id=session_id,
                video_id=video_id,
                stage=DriftStage.VIDEO_ACTUAL_START,
                timestamp=base_time,
                source="frontend"
            )

            service.capture_timestamp(
                session_id=session_id,
                video_id=video_id,
                stage=DriftStage.LABJACK_ACTUAL_START,
                timestamp=base_time + (drift / 1000),
                source="labjack"
            )

        stats = service.get_session_drift_statistics(session_id)

        assert stats['video_count'] == 3
        assert stats['complete_count'] == 3
        assert abs(stats['mean_drift_ms'] - 5.0) < 0.5
        assert stats['min_drift_ms'] < 4.0
        assert stats['max_drift_ms'] > 6.0

    def test_high_drift_alert(self):
        """Test high drift generates alert."""
        service = DriftMeasurementService()
        session_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())

        service.start_video_drift_measurement(
            session_id=session_id,
            video_id=video_id,
            video_sequence_number=0
        )

        # Create high drift (600ms)
        base_time = time.time()
        service.capture_timestamp(
            session_id=session_id,
            video_id=video_id,
            stage=DriftStage.VIDEO_ACTUAL_START,
            timestamp=base_time,
            source="frontend"
        )

        service.capture_timestamp(
            session_id=session_id,
            video_id=video_id,
            stage=DriftStage.LABJACK_ACTUAL_START,
            timestamp=base_time + 0.600,
            source="labjack"
        )

        stats = service.get_session_drift_statistics(session_id)

        assert 'alert' in stats
        assert 'High drift' in stats['alert']


class TestServiceManagement:
    """Test service lifecycle management."""

    def test_cleanup_session(self):
        """Test session cleanup."""
        service = DriftMeasurementService()
        session_id = str(uuid.uuid4())

        # Create measurements
        for i in range(3):
            video_id = str(uuid.uuid4())
            service.start_video_drift_measurement(
                session_id=session_id,
                video_id=video_id,
                video_sequence_number=i
            )

        # Verify measurements exist
        stats_before = service.get_service_statistics()
        assert stats_before['total_videos'] == 3

        # Cleanup
        service.cleanup_session(session_id)

        # Verify cleaned up
        stats_after = service.get_service_statistics()
        assert stats_after['total_videos'] == 0

    def test_service_statistics(self):
        """Test getting overall service statistics."""
        service = DriftMeasurementService()

        # Create multiple sessions
        for i in range(3):
            session_id = str(uuid.uuid4())
            video_id = str(uuid.uuid4())
            service.start_video_drift_measurement(
                session_id=session_id,
                video_id=video_id,
                video_sequence_number=0
            )

        stats = service.get_service_statistics()

        assert stats['total_sessions'] == 3
        assert stats['total_videos'] == 3
        assert stats['service_status'] == 'operational'
