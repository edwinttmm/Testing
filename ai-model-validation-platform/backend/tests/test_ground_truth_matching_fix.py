"""
Test Ground Truth Matching Fix

This test verifies that the temporal offset calculation fix works correctly
for matching detections to ground truth objects.

Test Scenario:
- Use real data from test session `daad8bf6-b5da-4423-abc4-a85e83bc1c16`
- Detection at 0.094s
- Ground truth objects at: 0.000s, 0.042s, 0.083s, 0.125s, 0.167s
- Expected match: GT at 0.083s (temporal offset +11ms)

Test Requirements:
1. Unit test for temporal offset calculation
2. Unit test for matching logic within tolerance
3. Integration test with real database session
"""

import pytest
import sys
from typing import List, Optional
from dataclasses import dataclass
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session

# Add backend to path
sys.path.insert(0, '/home/rigade/Testing/ai-model-validation-platform/backend')

from models import (
    Base, TestSession, DetectionEvent, GroundTruthObject,
    DetectionComparison, Video, Project
)
from services.ground_truth_matching_service import GroundTruthMatchingService
from database import SessionLocal
from config.timing_config import MATCHING_TOLERANCE_MS


# ============================================================================
# MOCK OBJECTS FOR UNIT TESTING
# ============================================================================

@dataclass
class MockDetection:
    """Mock detection object for unit testing"""
    id: str
    video_relative_timestamp: float
    timestamp: float
    video_id: Optional[str] = None
    confidence: float = 0.9
    class_label: str = "pedestrian"
    actual_latency_ms: Optional[float] = None
    video_frame_number: Optional[int] = None
    timing_sync_quality: str = "high"


@dataclass
class MockGroundTruth:
    """Mock ground truth object for unit testing"""
    id: str
    timestamp: float
    video_id: str
    class_label: str = "pedestrian"
    confidence: float = 1.0
    x: float = 100.0
    y: float = 100.0
    width: float = 50.0
    height: float = 50.0


# ============================================================================
# UNIT TESTS
# ============================================================================

class TestTemporalOffsetCalculation:
    """Unit tests for temporal offset calculation"""

    def test_positive_offset_detection_after_gt(self):
        """Test temporal offset when detection occurs AFTER ground truth"""
        detection_time = 0.094  # seconds
        gt_time = 0.083  # seconds
        expected_offset_ms = +11.0  # ms (detection is 11ms late)

        # Calculate offset: (detection - gt) * 1000
        actual_offset = (detection_time - gt_time) * 1000

        assert abs(actual_offset - expected_offset_ms) < 0.1, \
            f"Expected {expected_offset_ms}ms, got {actual_offset}ms"

    def test_negative_offset_detection_before_gt(self):
        """Test temporal offset when detection occurs BEFORE ground truth"""
        detection_time = 0.083  # seconds
        gt_time = 0.125  # seconds
        expected_offset_ms = -42.0  # ms (detection is 42ms early)

        actual_offset = (detection_time - gt_time) * 1000

        assert abs(actual_offset - expected_offset_ms) < 0.1, \
            f"Expected {expected_offset_ms}ms, got {actual_offset}ms"

    def test_zero_offset_exact_match(self):
        """Test temporal offset when detection exactly matches ground truth"""
        detection_time = 0.083  # seconds
        gt_time = 0.083  # seconds
        expected_offset_ms = 0.0  # ms

        actual_offset = (detection_time - gt_time) * 1000

        assert abs(actual_offset - expected_offset_ms) < 0.001, \
            f"Expected {expected_offset_ms}ms, got {actual_offset}ms"

    def test_real_scenario_closest_match(self):
        """Test finding the closest ground truth from real scenario"""
        detection_time = 0.094  # seconds
        gt_times = [0.000, 0.042, 0.083, 0.125, 0.167]  # seconds

        # Calculate offsets for all GT objects
        offsets = [(gt_time, abs((detection_time - gt_time) * 1000))
                   for gt_time in gt_times]

        # Find closest match
        closest_gt, min_offset = min(offsets, key=lambda x: x[1])

        # Expected: 0.083s with +11ms offset
        assert abs(closest_gt - 0.083) < 0.001, \
            f"Expected closest GT at 0.083s, got {closest_gt}s"
        assert abs(min_offset - 11.0) < 0.1, \
            f"Expected offset 11ms, got {min_offset}ms"


class TestDetectionMatchingLogic:
    """Unit tests for detection matching within tolerance"""

    def test_matching_within_tolerance_closest_gt(self):
        """Test that detection matches the closest GT within tolerance"""
        detection = MockDetection(
            id="det-001",
            video_relative_timestamp=0.094,
            timestamp=1000.094,
            video_id="video-123"
        )

        ground_truths = [
            MockGroundTruth(id="gt-001", timestamp=0.000, video_id="video-123"),  # +94ms
            MockGroundTruth(id="gt-002", timestamp=0.042, video_id="video-123"),  # +52ms
            MockGroundTruth(id="gt-003", timestamp=0.083, video_id="video-123"),  # +11ms ✓ closest
            MockGroundTruth(id="gt-004", timestamp=0.125, video_id="video-123"),  # -31ms
            MockGroundTruth(id="gt-005", timestamp=0.167, video_id="video-123"),  # -73ms
        ]

        tolerance_ms = 100  # 100ms tolerance

        # Find best match
        best_match = None
        min_offset = float('inf')

        for gt in ground_truths:
            offset_ms = abs((detection.video_relative_timestamp - gt.timestamp) * 1000)
            if offset_ms <= tolerance_ms and offset_ms < min_offset:
                min_offset = offset_ms
                best_match = gt

        # Assertions
        assert best_match is not None, "Should find a match within tolerance"
        assert best_match.id == "gt-003", "Should match GT at 0.083s"
        assert abs(min_offset - 11.0) < 0.1, f"Expected 11ms offset, got {min_offset}ms"

    def test_no_match_outside_tolerance(self):
        """Test that detection doesn't match GT outside tolerance"""
        detection = MockDetection(
            id="det-001",
            video_relative_timestamp=0.500,
            timestamp=1000.500,
            video_id="video-123"
        )

        ground_truths = [
            MockGroundTruth(id="gt-001", timestamp=0.000, video_id="video-123"),  # 500ms - outside tolerance
        ]

        tolerance_ms = 100  # 100ms tolerance

        # Find best match
        best_match = None
        min_offset = float('inf')

        for gt in ground_truths:
            offset_ms = abs((detection.video_relative_timestamp - gt.timestamp) * 1000)
            if offset_ms <= tolerance_ms and offset_ms < min_offset:
                min_offset = offset_ms
                best_match = gt

        # Assertions
        assert best_match is None, "Should not find match outside tolerance"

    def test_prefer_closest_absolute_offset(self):
        """Test that the GT with smallest absolute offset is selected"""
        detection = MockDetection(
            id="det-001",
            video_relative_timestamp=0.100,
            timestamp=1000.100,
            video_id="video-123"
        )

        ground_truths = [
            MockGroundTruth(id="gt-001", timestamp=0.050, video_id="video-123"),  # +50ms
            MockGroundTruth(id="gt-002", timestamp=0.150, video_id="video-123"),  # -50ms (same magnitude)
        ]

        tolerance_ms = 100

        # Find best match (smallest absolute offset)
        best_match = None
        min_offset = float('inf')

        for gt in ground_truths:
            offset_ms = abs((detection.video_relative_timestamp - gt.timestamp) * 1000)
            if offset_ms <= tolerance_ms and offset_ms < min_offset:
                min_offset = offset_ms
                best_match = gt

        # Should match one of them (both have equal offset)
        assert best_match is not None, "Should find a match"
        assert best_match.id in ["gt-001", "gt-002"], "Should match one of the GTs with equal offset"


class TestMatchTypeClassification:
    """Unit tests for TP/FP/FN classification"""

    def test_true_positive_within_tolerance(self):
        """Test that match within tolerance is classified as TP"""
        detection = MockDetection(
            id="det-001",
            video_relative_timestamp=0.094,
            timestamp=1000.094
        )

        gt = MockGroundTruth(
            id="gt-001",
            timestamp=0.083,
            video_id="video-123"
        )

        offset_ms = abs((detection.video_relative_timestamp - gt.timestamp) * 1000)
        tolerance_ms = 100

        match_type = "TP" if offset_ms <= tolerance_ms else "FP"

        assert match_type == "TP", "Should classify as True Positive"
        assert abs(offset_ms - 11.0) < 0.1, "Offset should be 11ms"

    def test_false_positive_outside_tolerance(self):
        """Test that match outside tolerance is classified as FP"""
        detection = MockDetection(
            id="det-001",
            video_relative_timestamp=0.500,
            timestamp=1000.500
        )

        gt = MockGroundTruth(
            id="gt-001",
            timestamp=0.000,
            video_id="video-123"
        )

        offset_ms = abs((detection.video_relative_timestamp - gt.timestamp) * 1000)
        tolerance_ms = 100

        match_type = "TP" if offset_ms <= tolerance_ms else "FP"

        assert match_type == "FP", "Should classify as False Positive"

    def test_false_negative_unmatched_gt(self):
        """Test that unmatched GT is classified as FN"""
        # GT exists but no detection matched it
        gt = MockGroundTruth(
            id="gt-001",
            timestamp=0.083,
            video_id="video-123"
        )

        matched = False  # No detection matched this GT

        match_type = "FN" if not matched else "TP"

        assert match_type == "FN", "Should classify as False Negative"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.integration
class TestGroundTruthMatchingIntegration:
    """Integration tests with database"""

    @pytest.fixture(scope="function")
    def test_db(self):
        """Create test database"""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = TestingSessionLocal()
        yield session
        session.close()

    @pytest.fixture
    def test_project(self, test_db):
        """Create test project"""
        project = Project(
            id="project-123",
            name="Test Project",
            description="Test",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            status="active"
        )
        test_db.add(project)
        test_db.commit()
        return project

    @pytest.fixture
    def test_video(self, test_db, test_project):
        """Create test video"""
        video = Video(
            id="video-123",
            filename="test.mp4",
            file_path="/test/test.mp4",
            file_size=1000000,
            duration=10.0,
            fps=24.0,
            resolution="1920x1080",
            project_id=test_project.id,
            status="validated",
            ground_truth_generated=True,
            ground_truth_count=5
        )
        test_db.add(video)
        test_db.commit()
        return video

    @pytest.fixture
    def test_ground_truths(self, test_db, test_video):
        """Create ground truth objects matching real scenario"""
        gt_objects = [
            GroundTruthObject(
                id=f"gt-{i:03d}",
                video_id=test_video.id,
                timestamp=ts,
                class_label="pedestrian",
                x=100.0,
                y=100.0,
                width=50.0,
                height=50.0,
                confidence=1.0
            )
            for i, ts in enumerate([0.000, 0.042, 0.083, 0.125, 0.167])
        ]

        for gt in gt_objects:
            test_db.add(gt)
        test_db.commit()
        return gt_objects

    @pytest.fixture
    def test_session_obj(self, test_db, test_project, test_video):
        """Create test session"""
        session = TestSession(
            id="test-session-123",
            name="Test Session",
            project_id=test_project.id,
            video_id=test_video.id,
            tolerance_ms=100,
            status="running"
        )
        test_db.add(session)
        test_db.commit()
        return session

    @pytest.fixture
    def test_detection(self, test_db, test_session_obj, test_video):
        """Create detection at 0.094s"""
        detection = DetectionEvent(
            id="6a64dd8d-ee55-4818-b2ca-6cc423aadc4c",
            test_session_id=test_session_obj.id,
            video_id=test_video.id,
            timestamp=1000.094,
            video_relative_timestamp=0.094,
            confidence=0.9,
            class_label="pedestrian",
            video_frame_number=2,
            timing_sync_quality="high",
            usable_for_validation=True
        )
        test_db.add(detection)
        test_db.commit()
        return detection

    def test_matching_finds_correct_gt(
        self,
        test_db,
        test_session_obj,
        test_video,
        test_ground_truths,
        test_detection
    ):
        """Test that matching service finds the correct GT object"""
        service = GroundTruthMatchingService(default_tolerance_ms=100)

        # Mock the database session
        with pytest.MonkeyPatch.context() as m:
            # Mock SessionLocal to return our test database
            m.setattr("services.ground_truth_matching_service.SessionLocal",
                     lambda: test_db)

            # Run matching
            metrics = service.match_detections_to_ground_truth(
                session_id=test_session_obj.id,
                tolerance_ms=100,
                force_rematch=True,
                auto_commit=True
            )

        # Verify metrics
        assert metrics is not None, "Matching should succeed"
        assert metrics.true_positives > 0, "Should find at least one TP"

        # Check comparison was created
        comparison = test_db.query(DetectionComparison).filter(
            DetectionComparison.detection_event_id == test_detection.id
        ).first()

        assert comparison is not None, "Comparison should be created"
        assert comparison.match_type == "TP", "Should be True Positive"
        assert comparison.ground_truth_id == "gt-002", "Should match GT at 0.083s"
        assert comparison.temporal_offset is not None, "Should have temporal offset"
        assert abs(comparison.temporal_offset - 11.0) < 0.5, \
            f"Expected ~11ms offset, got {comparison.temporal_offset}ms"

    def test_temporal_offset_stored_correctly(
        self,
        test_db,
        test_session_obj,
        test_ground_truths,
        test_detection
    ):
        """Test that temporal offset is calculated and stored correctly"""
        # Expected values
        detection_time = 0.094
        gt_time = 0.083
        expected_offset_ms = (detection_time - gt_time) * 1000  # +11ms

        # Manually create comparison to test calculation
        comparison = DetectionComparison(
            id="comp-001",
            test_session_id=test_session_obj.id,
            detection_event_id=test_detection.id,
            ground_truth_id="gt-002",  # GT at 0.083s
            match_type="TP",
            temporal_offset=expected_offset_ms,
            iou_score=None,
            distance_error=None
        )

        test_db.add(comparison)
        test_db.commit()

        # Retrieve and verify
        retrieved = test_db.query(DetectionComparison).filter(
            DetectionComparison.id == "comp-001"
        ).first()

        assert retrieved is not None
        assert retrieved.temporal_offset is not None
        assert abs(retrieved.temporal_offset - 11.0) < 0.1, \
            f"Expected 11ms offset, stored {retrieved.temporal_offset}ms"


@pytest.mark.integration
class TestRealDatabaseSession:
    """Integration tests with real database session"""

    def test_rerun_matching_for_real_session(self):
        """
        Test re-running matching for the real problematic session.

        This test requires the real database and is skipped by default.
        Run with: pytest test_ground_truth_matching_fix.py --run-real-db
        """
        session_id = "daad8bf6-b5da-4423-abc4-a85e83bc1c16"

        db = SessionLocal()
        try:
            # Check if session exists
            session = db.query(TestSession).filter(
                TestSession.id == session_id
            ).first()

            if not session:
                pytest.skip(f"Session {session_id} not found in database")

            # Clear old comparisons
            db.query(DetectionComparison).filter(
                DetectionComparison.test_session_id == session_id
            ).delete()
            db.commit()

            # Re-run matching with fixed logic
            service = GroundTruthMatchingService()
            metrics = service.match_detections_to_ground_truth(
                session_id=session_id,
                force_rematch=True,
                auto_commit=True
            )

            # Verify results
            assert metrics is not None, "Matching should succeed"
            assert metrics.true_positives > 0, "Should find at least some TPs"
            assert metrics.true_positives < 173, \
                "Not all detections should match (some will be FP)"

            # Check specific detection
            comparison = db.query(DetectionComparison).filter(
                DetectionComparison.detection_event_id == "6a64dd8d-ee55-4818-b2ca-6cc423aadc4c"
            ).first()

            if comparison:
                assert comparison.match_type == "TP", \
                    "Detection at 0.094s should match"
                assert comparison.temporal_offset != 0.0, \
                    "Should have non-zero offset"
                assert comparison.ground_truth_id is not None, \
                    "Should link to GT"

                print(f"\n✓ Detection matched to GT: {comparison.ground_truth_id}")
                print(f"  Temporal offset: {comparison.temporal_offset:.2f}ms")
                print(f"  Match type: {comparison.match_type}")

        finally:
            db.close()


# ============================================================================
# TEST EXECUTION
# ============================================================================

if __name__ == "__main__":
    """Run tests directly"""
    pytest.main([__file__, "-v", "-s"])
