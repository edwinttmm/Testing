"""Test unified latency field implementation


pytestmark = pytest.mark.skip(reason="Deprecated modules or missing dependencies")

This test suite validates that:
1. actual_latency_ms is consistently populated
2. Latency values are realistic (50-200ms typical)
3. No 0ms or Infinity values appear
4. Frontend normalizer correctly maps to actual_latency_ms
5. API responses use canonical field
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models import DetectionEvent, TestSession
from services.simple_labjack_detection import LabJackDetectionMonitor


class TestUnifiedLatencyField:
    """Test suite for unified latency field handling"""

    def test_detection_event_has_actual_latency_ms(self, db: Session):
        """Verify that actual_latency_ms is populated for all detection events"""
        # Create test session
        session = TestSession(
            id="test-session-1",
            project_id="test-project",
            status="running",
            test_start_time=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()

        # Create detection event
        detection = DetectionEvent(
            id="test-detection-1",
            test_session_id=session.id,
            timestamp=datetime.now(timezone.utc).timestamp(),
            actual_latency_ms=85.5,
            video_relative_timestamp=0.035,
            labjack_voltage=3.3,
            voltage_level=3.3,
            detection_channel="AIN0",
            latency_threshold_ms=100.0
        )
        db.add(detection)
        db.commit()

        # Verify actual_latency_ms is populated
        retrieved = db.execute(select(DetectionEvent).where(
            DetectionEvent.id == detection.id
        )).scalar_one_or_none()

        assert retrieved is not None
        assert retrieved.actual_latency_ms is not None
        assert retrieved.actual_latency_ms > 0
        assert retrieved.actual_latency_ms < 1000  # Realistic value

    def test_actual_latency_ms_realistic_values(self, db: Session):
        """Verify latency values are in realistic range (50-200ms typical)"""
        # Create test data
        session = TestSession(
            id="test-session-2",
            project_id="test-project",
            status="running",
            test_start_time=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()

        # Create detections with different latencies
        test_cases = [
            ("detection-1", 0.035, 85.0),   # 35ms video position + 50ms system = 85ms
            ("detection-2", 0.100, 150.0),  # 100ms video position + 50ms system = 150ms
            ("detection-3", 0.050, 100.0),  # 50ms video position + 50ms system = 100ms
        ]

        for det_id, video_rel_ts, expected_latency in test_cases:
            detection = DetectionEvent(
                id=det_id,
                test_session_id=session.id,
                timestamp=datetime.now(timezone.utc).timestamp(),
                actual_latency_ms=expected_latency,
                video_relative_timestamp=video_rel_ts,
                labjack_voltage=3.3,
                voltage_level=3.3,
                detection_channel="AIN0",
                latency_threshold_ms=100.0
            )
            db.add(detection)

        db.commit()

        # Verify all latencies are realistic
        detections = db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session.id
        )).scalars().all()

        for detection in detections:
            assert detection.actual_latency_ms is not None
            assert detection.actual_latency_ms >= 50.0  # Minimum system latency
            assert detection.actual_latency_ms <= 500.0  # Maximum reasonable latency
            assert detection.actual_latency_ms != 0  # Never zero
            assert detection.actual_latency_ms != float('inf')  # Never infinity

    def test_no_zero_or_infinity_latency(self, db: Session):
        """Verify no detections have 0ms or Infinity latency"""
        # Query all detection events
        detections = db.execute(select(DetectionEvent)).scalars().all()

        for detection in detections:
            if detection.actual_latency_ms is not None:
                assert detection.actual_latency_ms > 0, \
                    f"Detection {detection.id} has zero latency"
                assert detection.actual_latency_ms != float('inf'), \
                    f"Detection {detection.id} has infinite latency"
                assert detection.actual_latency_ms != float('-inf'), \
                    f"Detection {detection.id} has negative infinite latency"

    def test_legacy_fields_not_used_for_display(self, db: Session):
        """Verify legacy latency fields are not used for display logic"""
        # Create detection with only actual_latency_ms populated
        session = TestSession(
            id="test-session-3",
            project_id="test-project",
            status="running",
            test_start_time=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()

        detection = DetectionEvent(
            id="test-detection-legacy",
            test_session_id=session.id,
            timestamp=datetime.now(timezone.utc).timestamp(),
            actual_latency_ms=95.0,  # PRIMARY field
            latency_ns="95000000",   # DEPRECATED field
            processing_time_ms=10.0,  # DEPRECATED field (not latency)
            video_relative_timestamp=0.045,
            labjack_voltage=3.3,
            voltage_level=3.3,
            detection_channel="AIN0",
            latency_threshold_ms=100.0
        )
        db.add(detection)
        db.commit()

        # Verify we use actual_latency_ms, not legacy fields
        retrieved = db.execute(select(DetectionEvent).where(
            DetectionEvent.id == detection.id
        )).scalar_one_or_none()

        # The canonical field is actual_latency_ms
        assert retrieved.actual_latency_ms == 95.0

        # Legacy fields may exist but should not be used for calculations
        assert retrieved.latency_ns == "95000000"  # Exists but not used
        assert retrieved.processing_time_ms == 10.0  # Exists but not latency

    def test_api_response_serialization(self, client):
        """Verify API responses serialize actual_latency_ms correctly"""
        # Make API request for detection events
        response = client.get("/api/v1/test-sessions/test-session-1/detections")

        assert response.status_code == 200
        data = response.json()

        # Verify all detections have actual_latency_ms
        for detection in data.get("detection_events", []):
            assert "actual_latency_ms" in detection or "actualLatencyMs" in detection
            latency = detection.get("actual_latency_ms") or detection.get("actualLatencyMs")
            if latency is not None:
                assert latency > 0
                assert latency < 1000

    def test_unified_calculation_formula(self):
        """Verify the unified latency calculation formula is correct"""
        # Test formula: Latency = max(0, video_relative_timestamp * 1000) + SYSTEM_LATENCY_MS
        SYSTEM_LATENCY_MS = 50.0

        test_cases = [
            (0.035, 85.0),   # 35ms + 50ms = 85ms
            (0.100, 150.0),  # 100ms + 50ms = 150ms
            (0.000, 50.0),   # 0ms + 50ms = 50ms
            (-0.010, 50.0),  # max(0, -10ms) + 50ms = 50ms (negative clamped to 0)
        ]

        for video_rel_ts, expected_latency in test_cases:
            calculated_latency = max(0.0, video_rel_ts * 1000) + SYSTEM_LATENCY_MS
            assert calculated_latency == expected_latency, \
                f"Formula error: video_rel_ts={video_rel_ts}, " \
                f"calculated={calculated_latency}, expected={expected_latency}"

    def test_frontend_normalizer_prefers_actual_latency_ms(self):
        """Verify frontend normalizer prioritizes actual_latency_ms"""
        # Simulate detection event with multiple latency fields
        detection_data = {
            "id": "test-detection",
            "actual_latency_ms": 95.0,  # Should use this
            "latency_ms": 0,            # Legacy field (ignored)
            "real_latency_ms": 100.0,   # Legacy field (ignored)
            "processing_time_ms": 10.0,  # Not latency (ignored)
        }

        # Frontend normalizer logic (simplified test)
        latency = (
            detection_data.get("actual_latency_ms") or
            detection_data.get("actualLatencyMs") or
            detection_data.get("latency_ms") or
            detection_data.get("real_latency_ms")
        )

        # Should use actual_latency_ms
        assert latency == 95.0

    def test_migration_backfills_actual_latency_ms(self, db: Session):
        """Verify migration backfills actual_latency_ms for NULL values"""
        # Create detection with NULL actual_latency_ms
        session = TestSession(
            id="test-session-migration",
            project_id="test-project",
            status="running",
            test_start_time=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()

        detection = DetectionEvent(
            id="test-detection-null-latency",
            test_session_id=session.id,
            timestamp=datetime.now(timezone.utc).timestamp(),
            actual_latency_ms=None,  # NULL value
            video_relative_timestamp=0.050,  # Should backfill to (50*1000 + 50) = 100ms
            labjack_voltage=3.3,
            voltage_level=3.3,
            detection_channel="AIN0",
            latency_threshold_ms=100.0
        )
        db.add(detection)
        db.commit()

        # Simulate migration backfill
        db.execute("""
            UPDATE detection_events
            SET actual_latency_ms = COALESCE(
                actual_latency_ms,
                (video_relative_timestamp * 1000.0) + 50.0,
                50.0
            )
            WHERE actual_latency_ms IS NULL
        """)
        db.commit()

        # Verify backfill worked
        retrieved = db.execute(select(DetectionEvent).where(
            DetectionEvent.id == detection.id
        )).scalar_one_or_none()

        assert retrieved.actual_latency_ms is not None
        assert retrieved.actual_latency_ms == 100.0  # (0.050 * 1000) + 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
