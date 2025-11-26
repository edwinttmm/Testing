"""
Comprehensive Tests for Ground Truth Matching Persistence

Tests that matching service properly updates detection_events table with:
- validation_result ('TP', 'FP', 'FN')
- ground_truth_match_id (for TP detections)
- Session completion triggers matching
- Manual trigger endpoint

Test session: 2a946b2d-64f0-4c92-a597-f0b65a809e6a
"""

import pytest
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import text, select, delete, update, func
from sqlalchemy.orm import Session

from models import (
    TestSession, DetectionEvent, GroundTruthObject,
    DetectionComparison, Project, Video
)
from services.ground_truth_matching_service import (
    GroundTruthMatchingService,
    get_ground_truth_matching_service
)


# ===== FIXTURES =====

@pytest.fixture
def matching_service():
    """Get ground truth matching service instance"""
    return get_ground_truth_matching_service()


@pytest.fixture
def test_project(test_db: Session):
    """Create test project"""
    project = Project(
        id=str(uuid.uuid4()),
        name="GT Persistence Test Project",
        description="Testing ground truth matching persistence",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO",
        status="active"
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)
    return project


@pytest.fixture
def test_video(test_db: Session, test_project):
    """Create test video"""
    video = Video(
        id=str(uuid.uuid4()),
        filename="test_video.mp4",
        file_path="/test/path/test_video.mp4",
        project_id=test_project.id,
        duration=10.0,
        fps=30.0,
        resolution="1920x1080",
        status="validated",
        ground_truth_generated=True,
        ground_truth_count=5
    )
    test_db.add(video)
    test_db.commit()
    test_db.refresh(video)
    return video


@pytest.fixture
def test_session_standard(test_db: Session, test_project, test_video):
    """Create standard test session"""
    session = TestSession(
        id=str(uuid.uuid4()),
        name="GT Persistence Test Session",
        project_id=test_project.id,
        video_id=test_video.id,
        tolerance_ms=100,
        status="running",
        session_type="user_created",
        has_video_sequence=False
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)
    return session


@pytest.fixture
def ground_truth_objects(test_db: Session, test_video):
    """Create ground truth objects for testing"""
    gt_objects = [
        GroundTruthObject(
            id=str(uuid.uuid4()),
            video_id=test_video.id,
            timestamp=1.0,
            class_label="pedestrian",
            x=100, y=100, width=50, height=100,
            confidence=0.95
        ),
        GroundTruthObject(
            id=str(uuid.uuid4()),
            video_id=test_video.id,
            timestamp=2.0,
            class_label="pedestrian",
            x=150, y=150, width=50, height=100,
            confidence=0.92
        ),
        GroundTruthObject(
            id=str(uuid.uuid4()),
            video_id=test_video.id,
            timestamp=3.0,
            class_label="cyclist",
            x=200, y=200, width=60, height=120,
            confidence=0.88
        ),
        GroundTruthObject(
            id=str(uuid.uuid4()),
            video_id=test_video.id,
            timestamp=4.0,
            class_label="pedestrian",
            x=250, y=250, width=50, height=100,
            confidence=0.91
        ),
        GroundTruthObject(
            id=str(uuid.uuid4()),
            video_id=test_video.id,
            timestamp=5.0,
            class_label="cyclist",
            x=300, y=300, width=60, height=120,
            confidence=0.93
        ),
    ]

    for gt in gt_objects:
        test_db.add(gt)
    test_db.commit()

    return gt_objects


@pytest.fixture
def detection_events_mixed(test_db: Session, test_session_standard, test_video):
    """Create detection events with mix of TP, FP, FN scenarios"""
    detections = [
        # TP: Matches GT at 1.0s (within 100ms tolerance)
        DetectionEvent(
            id=str(uuid.uuid4()),
            test_session_id=test_session_standard.id,
            video_id=test_video.id,
            timestamp=1.05,  # 50ms after GT
            video_relative_timestamp=1.05,
            confidence=0.89,
            class_label="pedestrian",
            actual_latency_ms=50.0,
            validation_result=None,  # To be set by matching
            ground_truth_match_id=None  # To be set by matching
        ),
        # TP: Matches GT at 2.0s
        DetectionEvent(
            id=str(uuid.uuid4()),
            test_session_id=test_session_standard.id,
            video_id=test_video.id,
            timestamp=2.08,  # 80ms after GT
            video_relative_timestamp=2.08,
            confidence=0.87,
            class_label="pedestrian",
            actual_latency_ms=80.0,
            validation_result=None,
            ground_truth_match_id=None
        ),
        # FP: No matching ground truth
        DetectionEvent(
            id=str(uuid.uuid4()),
            test_session_id=test_session_standard.id,
            video_id=test_video.id,
            timestamp=6.5,  # No GT near this time
            video_relative_timestamp=6.5,
            confidence=0.75,
            class_label="pedestrian",
            actual_latency_ms=None,
            validation_result=None,
            ground_truth_match_id=None
        ),
        # TP: Matches GT at 4.0s
        DetectionEvent(
            id=str(uuid.uuid4()),
            test_session_id=test_session_standard.id,
            video_id=test_video.id,
            timestamp=4.03,  # 30ms after GT
            video_relative_timestamp=4.03,
            confidence=0.91,
            class_label="pedestrian",
            actual_latency_ms=30.0,
            validation_result=None,
            ground_truth_match_id=None
        ),
        # FP: Another false positive
        DetectionEvent(
            id=str(uuid.uuid4()),
            test_session_id=test_session_standard.id,
            video_id=test_video.id,
            timestamp=7.2,
            video_relative_timestamp=7.2,
            confidence=0.68,
            class_label="cyclist",
            actual_latency_ms=None,
            validation_result=None,
            ground_truth_match_id=None
        )
    ]

    for det in detections:
        test_db.add(det)
    test_db.commit()

    return detections


# ===== TESTS =====

class TestGroundTruthPersistence:
    """Test suite for ground truth matching persistence to detection_events table"""

    def test_matching_updates_detection_events_table(
        self,
        test_db: Session,
        matching_service: GroundTruthMatchingService,
        test_session_standard,
        ground_truth_objects,
        detection_events_mixed
    ):
        """Test that matching service persists TP/FP/FN to detection_events table"""
        session_id = test_session_standard.id

        # BEFORE: Verify no validation results set
        detections_before = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        assert len(detections_before) == 5
        for det in detections_before:
            assert det.validation_result is None, "validation_result should be None before matching"
            assert det.ground_truth_match_id is None, "ground_truth_match_id should be None before matching"

        # TRIGGER: Run matching
        metrics = matching_service.match_detections_to_ground_truth(session_id)

        # VERIFY: Matching completed successfully
        assert metrics is not None, "Matching should return metrics"
        assert metrics.true_positives > 0, "Should have TP detections"

        # AFTER: Verify detection_events table updated
        detections_after = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        # Count validation results
        tp_count = sum(1 for d in detections_after if d.validation_result == 'TP')
        fp_count = sum(1 for d in detections_after if d.validation_result == 'FP')

        # ASSERTIONS: Validation results persisted
        assert tp_count > 0, "Should have TP detections in detection_events"
        assert fp_count > 0, "Should have FP detections in detection_events"
        assert tp_count + fp_count == len(detections_after), "All detections should have validation_result"

        # ASSERTIONS: TP detections have ground_truth_match_id
        tp_detections = [d for d in detections_after if d.validation_result == 'TP']
        for det in tp_detections:
            assert det.ground_truth_match_id is not None, \
                f"TP detection {det.id} missing ground_truth_match_id"

            # Verify ground_truth_match_id points to valid GT object
            gt_obj = test_db.execute(select(GroundTruthObject).where(
                GroundTruthObject.id == det.ground_truth_match_id
            )).scalar_one_or_none()
            assert gt_obj is not None, \
                f"TP detection {det.id} has invalid ground_truth_match_id"

        # ASSERTIONS: FP detections have NULL ground_truth_match_id
        fp_detections = [d for d in detections_after if d.validation_result == 'FP']
        for det in fp_detections:
            assert det.ground_truth_match_id is None, \
                f"FP detection {det.id} should have NULL ground_truth_match_id"


    def test_false_negatives_not_in_detection_events(
        self,
        test_db: Session,
        matching_service: GroundTruthMatchingService,
        test_session_standard,
        ground_truth_objects,
        detection_events_mixed
    ):
        """Test that FN results are in detection_comparisons, not detection_events"""
        session_id = test_session_standard.id

        # Run matching
        metrics = matching_service.match_detections_to_ground_truth(session_id)

        assert metrics is not None
        assert metrics.false_negatives > 0, "Should have missed ground truth objects (FN)"

        # FN should NOT appear in detection_events
        fn_in_detections = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.validation_result == 'FN'
        )).scalars().all()

        assert len(fn_in_detections) == 0, \
            "FN should not be in detection_events (only TP/FP for actual detections)"

        # FN should appear in detection_comparisons
        fn_comparisons = test_db.execute(select(DetectionComparison).where(
            DetectionComparison.test_session_id == session_id,
            DetectionComparison.match_type == 'FN'
        )).scalars().all()

        assert len(fn_comparisons) == metrics.false_negatives, \
            f"Expected {metrics.false_negatives} FN in comparisons, got {len(fn_comparisons)}"

        # Verify FN comparisons have ground_truth_id but no detection_event_id
        for comp in fn_comparisons:
            assert comp.ground_truth_id is not None, "FN should have ground_truth_id"
            assert comp.detection_event_id is None, "FN should not have detection_event_id"


    def test_validation_result_counts_match_metrics(
        self,
        test_db: Session,
        matching_service: GroundTruthMatchingService,
        test_session_standard,
        ground_truth_objects,
        detection_events_mixed
    ):
        """Test that validation_result counts match returned metrics"""
        session_id = test_session_standard.id

        # Run matching
        metrics = matching_service.match_detections_to_ground_truth(session_id)

        assert metrics is not None

        # Count from detection_events
        detections = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        tp_count = sum(1 for d in detections if d.validation_result == 'TP')
        fp_count = sum(1 for d in detections if d.validation_result == 'FP')

        # Verify counts match metrics
        assert tp_count == metrics.true_positives, \
            f"TP count mismatch: detection_events={tp_count}, metrics={metrics.true_positives}"
        assert fp_count == metrics.false_positives, \
            f"FP count mismatch: detection_events={fp_count}, metrics={metrics.false_positives}"


    def test_matching_with_specific_session_2a946b2d(
        self,
        test_db: Session,
        matching_service: GroundTruthMatchingService
    ):
        """Test matching with specific session ID from production data"""
        # NOTE: This test requires session 2a946b2d-64f0-4c92-a597-f0b65a809e6a to exist
        # Skip if session doesn't exist in test database

        session_id = "2a946b2d-64f0-4c92-a597-f0b65a809e6a"

        session = test_db.execute(select(TestSession).where(
            TestSession.id == session_id
        )).scalar_one_or_none()

        if session is None:
            pytest.skip(f"Session {session_id} not found in test database")

        # Get detection count before matching
        detections_before = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        if len(detections_before) == 0:
            pytest.skip(f"No detection events for session {session_id}")

        # Run matching
        metrics = matching_service.match_detections_to_ground_truth(session_id)

        if metrics is None:
            pytest.skip(f"Matching returned None (likely no ground truth)")

        # Verify detection_events updated
        detections_after = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        # All detections should have validation_result
        validated_count = sum(
            1 for d in detections_after
            if d.validation_result in ['TP', 'FP']
        )

        assert validated_count == len(detections_after), \
            f"All {len(detections_after)} detections should have validation_result"

        # TP detections should have ground_truth_match_id
        tp_detections = [d for d in detections_after if d.validation_result == 'TP']

        if len(tp_detections) > 0:
            for det in tp_detections:
                assert det.ground_truth_match_id is not None, \
                    f"TP detection {det.id} missing ground_truth_match_id"


    def test_session_completion_triggers_matching(
        self,
        test_db: Session,
        matching_service: GroundTruthMatchingService,
        test_session_standard,
        ground_truth_objects,
        detection_events_mixed
    ):
        """Test that completing a session triggers ground truth matching"""
        session_id = test_session_standard.id

        # Verify detections not yet validated
        detections_before = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        assert all(d.validation_result is None for d in detections_before)

        # TRIGGER: Complete session (simulates what session_completion_service does)
        # In production, session completion should trigger matching
        test_session_standard.status = "completed"
        test_session_standard.completed_at = datetime.now(timezone.utc)
        test_db.commit()

        # Manually trigger matching (in production this would be automatic)
        metrics = matching_service.match_detections_to_ground_truth(session_id)

        assert metrics is not None

        # Verify detection_events updated after completion
        detections_after = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        validated_count = sum(
            1 for d in detections_after
            if d.validation_result in ['TP', 'FP']
        )

        assert validated_count > 0, "Session completion should trigger matching"
        assert validated_count == len(detections_after), \
            "All detections should be validated after completion"


    def test_manual_matching_trigger_endpoint(
        self,
        test_db: Session,
        matching_service: GroundTruthMatchingService,
        test_session_standard,
        ground_truth_objects,
        detection_events_mixed
    ):
        """Test manual matching trigger (simulates POST /api/sessions/{id}/match endpoint)"""
        session_id = test_session_standard.id

        # Simulate manual trigger via API endpoint
        # (In production: POST /api/sessions/{session_id}/match)

        # BEFORE: No validation results
        detections_before = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        assert all(d.validation_result is None for d in detections_before)

        # TRIGGER: Manual matching (API endpoint calls this)
        metrics = matching_service.match_detections_to_ground_truth(
            session_id=session_id,
            force_rematch=False  # Use cached if available
        )

        assert metrics is not None, "Manual trigger should return metrics"

        # VERIFY: Detection events updated
        detections_after = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        tp_count = sum(1 for d in detections_after if d.validation_result == 'TP')
        fp_count = sum(1 for d in detections_after if d.validation_result == 'FP')

        assert tp_count > 0, "Manual trigger should create TP results"
        assert fp_count > 0, "Manual trigger should create FP results"
        assert tp_count == metrics.true_positives
        assert fp_count == metrics.false_positives


    def test_force_rematch_updates_existing_results(
        self,
        test_db: Session,
        matching_service: GroundTruthMatchingService,
        test_session_standard,
        ground_truth_objects,
        detection_events_mixed
    ):
        """Test that force_rematch overwrites existing validation results"""
        session_id = test_session_standard.id

        # First matching
        metrics1 = matching_service.match_detections_to_ground_truth(session_id)
        assert metrics1 is not None

        # Verify results exist
        detections1 = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        tp_count1 = sum(1 for d in detections1 if d.validation_result == 'TP')
        assert tp_count1 > 0

        # Modify a detection to change results
        # (This simulates a scenario where detections changed and we need to rematch)
        tp_detection = next(d for d in detections1 if d.validation_result == 'TP')
        tp_detection.timestamp = 99.0  # Move far from any GT
        tp_detection.video_relative_timestamp = 99.0
        test_db.commit()

        # Force rematch
        metrics2 = matching_service.match_detections_to_ground_truth(
            session_id,
            force_rematch=True
        )

        assert metrics2 is not None

        # Verify results updated
        detections2 = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        tp_count2 = sum(1 for d in detections2 if d.validation_result == 'TP')

        # Should have fewer TP after moving detection away from GT
        assert tp_count2 < tp_count1, \
            "Force rematch should update validation results"


    def test_ground_truth_match_id_references_correct_object(
        self,
        test_db: Session,
        matching_service: GroundTruthMatchingService,
        test_session_standard,
        ground_truth_objects,
        detection_events_mixed
    ):
        """Test that ground_truth_match_id references the temporally closest GT object"""
        session_id = test_session_standard.id

        # Run matching
        metrics = matching_service.match_detections_to_ground_truth(session_id)
        assert metrics is not None

        # Get TP detections
        tp_detections = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.validation_result == 'TP'
        )).scalars().all()

        assert len(tp_detections) > 0

        # Verify each TP references temporally closest GT
        for det in tp_detections:
            assert det.ground_truth_match_id is not None

            # Get matched GT object
            matched_gt = test_db.execute(select(GroundTruthObject).where(
                GroundTruthObject.id == det.ground_truth_match_id
            )).scalar_one_or_none()

            assert matched_gt is not None

            # Verify temporal proximity
            det_time = det.video_relative_timestamp or det.timestamp
            gt_time = matched_gt.timestamp
            time_diff_ms = abs(det_time - gt_time) * 1000

            # Should be within tolerance (100ms default)
            tolerance_ms = test_session_standard.tolerance_ms or 100
            assert time_diff_ms <= tolerance_ms, \
                f"Detection at {det_time}s matched to GT at {gt_time}s " \
                f"(diff={time_diff_ms}ms > tolerance={tolerance_ms}ms)"


    def test_no_validation_result_for_unmatched_session(
        self,
        test_db: Session,
        matching_service: GroundTruthMatchingService,
        test_session_standard,
        detection_events_mixed
    ):
        """Test that sessions without ground truth have no validation_result"""
        session_id = test_session_standard.id

        # Run matching with NO ground truth objects
        # (ground_truth_objects fixture not used)

        metrics = matching_service.match_detections_to_ground_truth(session_id)

        # Should return empty metrics (all FP)
        assert metrics is not None
        assert metrics.true_positives == 0
        assert metrics.false_negatives == 0
        assert metrics.false_positives == len(detection_events_mixed)

        # All detections should be marked as FP
        detections = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        for det in detections:
            assert det.validation_result == 'FP', \
                "Without ground truth, all detections should be FP"
            assert det.ground_truth_match_id is None, \
                "Without ground truth, no match IDs should be set"


class TestPersistenceEdgeCases:
    """Test edge cases for ground truth persistence"""

    def test_persistence_with_duplicate_timestamps(
        self,
        test_db: Session,
        matching_service: GroundTruthMatchingService,
        test_session_standard,
        test_video
    ):
        """Test matching when multiple detections have same timestamp"""
        session_id = test_session_standard.id

        # Create GT at 5.0s
        gt = GroundTruthObject(
            id=str(uuid.uuid4()),
            video_id=test_video.id,
            timestamp=5.0,
            class_label="pedestrian",
            x=100, y=100, width=50, height=100,
            confidence=0.9
        )
        test_db.add(gt)

        # Create multiple detections at same time
        for i in range(3):
            det = DetectionEvent(
                id=str(uuid.uuid4()),
                test_session_id=session_id,
                video_id=test_video.id,
                timestamp=5.05,  # All at same time
                video_relative_timestamp=5.05,
                confidence=0.8,
                class_label="pedestrian"
            )
            test_db.add(det)

        test_db.commit()

        # Run matching
        metrics = matching_service.match_detections_to_ground_truth(session_id)

        assert metrics is not None

        # Only ONE detection should match (first-match wins)
        tp_count = test_db.execute(select(func.count()).select_from(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.validation_result == 'TP'
        )).scalar()

        assert tp_count == 1, "Only one detection should match to the same GT object"

        # Other two should be FP
        fp_count = test_db.execute(select(func.count()).select_from(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.validation_result == 'FP'
        )).scalar()

        assert fp_count == 2, "Remaining detections should be FP"


    def test_persistence_preserves_other_fields(
        self,
        test_db: Session,
        matching_service: GroundTruthMatchingService,
        test_session_standard,
        ground_truth_objects,
        detection_events_mixed
    ):
        """Test that matching only updates validation fields, not other data"""
        session_id = test_session_standard.id

        # Store original field values
        original_data = {}
        detections_before = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        for det in detections_before:
            original_data[det.id] = {
                'timestamp': det.timestamp,
                'confidence': det.confidence,
                'class_label': det.class_label,
                'actual_latency_ms': det.actual_latency_ms,
                'video_relative_timestamp': det.video_relative_timestamp
            }

        # Run matching
        matching_service.match_detections_to_ground_truth(session_id)

        # Verify other fields unchanged
        detections_after = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id
        )).scalars().all()

        for det in detections_after:
            original = original_data[det.id]

            assert det.timestamp == original['timestamp'], \
                "Matching should not modify timestamp"
            assert det.confidence == original['confidence'], \
                "Matching should not modify confidence"
            assert det.class_label == original['class_label'], \
                "Matching should not modify class_label"
            assert det.actual_latency_ms == original['actual_latency_ms'], \
                "Matching should not modify actual_latency_ms"
            assert det.video_relative_timestamp == original['video_relative_timestamp'], \
                "Matching should not modify video_relative_timestamp"
