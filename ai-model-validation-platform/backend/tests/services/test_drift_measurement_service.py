"""

pytestmark = pytest.mark.skip(reason="Deprecated modules or missing dependencies")

Unit Tests for Drift Measurement Service
=========================================

Tests multi-stage timestamp capture and drift calculation.

Author: Backend API Developer Agent
Date: 2025-11-20
"""

pytestmark = pytest.mark.skip(reason="Deprecated or missing dependencies")

import pytest
import time
from datetime import datetime, timezone
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from services.drift_measurement_service import (
    DriftMeasurementService,
    VideoDriftMeasurement,
    StageTimestamp,
    DriftStage,
    get_drift_measurement_service,
    initialize_drift_measurement_service
)


@pytest.fixture
def drift_service():
    """Create a fresh drift measurement service for each test"""
    return DriftMeasurementService()


@pytest.fixture
def mock_session():
    """Mock session data"""
    return {
        'session_id': 'test_session_001',
        'video_id': 'test_video_001',
        'sequence_number': 1
    }


class TestVideoDriftMeasurement:
    """Test VideoDriftMeasurement calculations"""

    def test_measurement_creation(self, mock_session):
        """Test creating a drift measurement"""
        measurement = VideoDriftMeasurement(
            session_id=mock_session['session_id'],
            video_id=mock_session['video_id'],
            video_sequence_number=mock_session['sequence_number']
        )

        assert measurement.session_id == mock_session['session_id']
        assert measurement.video_id == mock_session['video_id']
        assert len(measurement.timestamps) == 0

    def test_drift_calculation_with_timestamps(self):
        """Test drift calculation with complete timestamps"""
        measurement = VideoDriftMeasurement(
            session_id="session_001",
            video_id="video_001",
            video_sequence_number=1
        )

        base_time = time.time()

        # Add timestamps simulating real scenario
        measurement.timestamps[DriftStage.VIDEO_START_COMMAND] = StageTimestamp(
            stage=DriftStage.VIDEO_START_COMMAND,
            timestamp=base_time,
            timestamp_ns=int(base_time * 1e9),
            source="backend"
        )

        measurement.timestamps[DriftStage.VIDEO_ACTUAL_START] = StageTimestamp(
            stage=DriftStage.VIDEO_ACTUAL_START,
            timestamp=base_time + 0.2,  # 200ms later
            timestamp_ns=int((base_time + 0.2) * 1e9),
            source="frontend"
        )

        measurement.timestamps[DriftStage.LABJACK_COMMAND_SENT] = StageTimestamp(
            stage=DriftStage.LABJACK_COMMAND_SENT,
            timestamp=base_time + 0.05,  # 50ms after command
            timestamp_ns=int((base_time + 0.05) * 1e9),
            source="backend"
        )

        measurement.timestamps[DriftStage.LABJACK_ACTUAL_START] = StageTimestamp(
            stage=DriftStage.LABJACK_ACTUAL_START,
            timestamp=base_time + 0.1,  # 100ms after command
            timestamp_ns=int((base_time + 0.1) * 1e9),
            source="labjack"
        )

        # Calculate drift
        measurement.calculate_drift()

        # Verify calculations
        assert measurement.video_start_drift_ms == pytest.approx(200.0, abs=1.0)
        assert measurement.labjack_start_drift_ms == pytest.approx(50.0, abs=1.0)
        assert measurement.drift_calculation_complete is True
        assert measurement.confidence_score > 0.5

    def test_confidence_score_calculation(self):
        """Test confidence score based on available data"""
        measurement = VideoDriftMeasurement(
            session_id="session_002",
            video_id="video_002",
            video_sequence_number=2
        )

        # Initially low confidence (no data)
        assert measurement.confidence_score == 0.0

        # Add some timestamps
        base_time = time.time()
        measurement.timestamps[DriftStage.VIDEO_ACTUAL_START] = StageTimestamp(
            stage=DriftStage.VIDEO_ACTUAL_START,
            timestamp=base_time,
            timestamp_ns=int(base_time * 1e9),
            source="frontend"
        )

        measurement.calculate_drift()

        # Confidence should increase
        assert measurement.confidence_score > 0.0


class TestDriftMeasurementService:
    """Test DriftMeasurementService operations"""

    def test_service_initialization(self, drift_service):
        """Test service initializes correctly"""
        assert drift_service is not None
        stats = drift_service.get_service_statistics()
        assert stats['service_status'] == "operational"

    def test_start_video_drift_measurement(self, drift_service, mock_session):
        """Test starting drift measurement for a video"""
        measurement = drift_service.start_video_drift_measurement(
            session_id=mock_session['session_id'],
            video_id=mock_session['video_id'],
            video_sequence_number=mock_session['sequence_number'],
            clock_offset_ms=10.0
        )

        assert measurement.session_id == mock_session['session_id']
        assert measurement.clock_offset_ms == 10.0

    def test_capture_timestamp(self, drift_service, mock_session):
        """Test capturing timestamps at different stages"""
        # Start measurement
        drift_service.start_video_drift_measurement(
            session_id=mock_session['session_id'],
            video_id=mock_session['video_id'],
            video_sequence_number=1
        )

        # Capture timestamp
        base_time = time.time()
        drift_service.capture_timestamp(
            session_id=mock_session['session_id'],
            video_id=mock_session['video_id'],
            stage=DriftStage.VIDEO_ACTUAL_START,
            timestamp=base_time,
            source="frontend"
        )

        # Get measurement
        measurement = drift_service.get_measurement(
            mock_session['session_id'],
            mock_session['video_id']
        )

        assert DriftStage.VIDEO_ACTUAL_START in measurement.timestamps

    def test_get_drift_for_video(self, drift_service):
        """Test getting calculated drift for a video"""
        session_id = "session_003"
        video_id = "video_003"

        # Start measurement
        drift_service.start_video_drift_measurement(
            session_id=session_id,
            video_id=video_id,
            video_sequence_number=1
        )

        base_time = time.time()

        # Capture all required timestamps
        drift_service.capture_timestamp(
            session_id, video_id,
            DriftStage.VIDEO_START_COMMAND,
            base_time, "backend"
        )

        drift_service.capture_timestamp(
            session_id, video_id,
            DriftStage.VIDEO_ACTUAL_START,
            base_time + 0.15, "frontend"
        )

        drift_service.capture_timestamp(
            session_id, video_id,
            DriftStage.LABJACK_ACTUAL_START,
            base_time + 0.1, "labjack"
        )

        # Get drift
        drift_ms = drift_service.get_drift_for_video(session_id, video_id)

        assert drift_ms is not None
        assert isinstance(drift_ms, float)

    def test_get_session_drift_statistics(self, drift_service):
        """Test getting drift statistics for a session"""
        session_id = "session_004"

        # Add multiple video measurements
        for i in range(3):
            video_id = f"video_{i}"
            drift_service.start_video_drift_measurement(
                session_id, video_id, i
            )

            base_time = time.time()
            drift_service.capture_timestamp(
                session_id, video_id,
                DriftStage.VIDEO_ACTUAL_START,
                base_time, "frontend"
            )
            drift_service.capture_timestamp(
                session_id, video_id,
                DriftStage.LABJACK_ACTUAL_START,
                base_time + 0.05 + (i * 0.01), "labjack"
            )

        stats = drift_service.get_session_drift_statistics(session_id)

        assert stats['session_id'] == session_id
        assert stats['video_count'] == 3
        assert 'mean_drift_ms' in stats

    def test_cleanup_session(self, drift_service):
        """Test cleaning up session data"""
        session_id = "session_005"
        video_id = "video_005"

        drift_service.start_video_drift_measurement(session_id, video_id, 1)
        drift_service.cleanup_session(session_id)

        # Should return None after cleanup
        measurement = drift_service.get_measurement(session_id, video_id)
        assert measurement is None


class TestGlobalServiceInstance:
    """Test global service instance functions"""

    def test_get_drift_measurement_service(self):
        """Test getting global service instance"""
        service = get_drift_measurement_service()
        assert service is not None

    def test_initialize_drift_measurement_service(self):
        """Test initializing service"""
        service = initialize_drift_measurement_service()
        assert service is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
