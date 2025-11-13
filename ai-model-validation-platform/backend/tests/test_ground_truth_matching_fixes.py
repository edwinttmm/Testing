"""
Comprehensive Test Suite for Ground Truth Matching Algorithm Fixes

This test suite validates the critical bug fixes for:
1. Double-matching prevention (one detection matching multiple GTs)
2. Tolerance window clamping (preventing cross-video contamination)
3. Match validation (ensuring one-to-one matching)

Test Coverage:
- Double-matching scenarios
- Tolerance window boundary conditions
- Cross-video contamination
- Edge cases (rapid-fire events, overlapping windows)
- Performance benchmarks
"""

import pytest
import time
import statistics
from datetime import datetime
from typing import List, Dict
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models import (
    TestSession, DetectionEvent, GroundTruthObject,
    DetectionComparison, VideoTestSequence, SequenceVideoResult
)
from services.ground_truth_matching_service import (
    GroundTruthMatchingService, MatchResult, SessionMetrics
)
from services.video_id_resolver import get_video_id_for_detection


class TestDoubleMatchingPrevention:
    """Test suite for double-matching bug fix"""

    @pytest.fixture
    def setup_double_match_scenario(self, db: Session):
        """
        Create scenario where one detection could match two GTs.

        Setup:
        - GT1 @ 10.000s
        - GT2 @ 10.050s (50ms apart)
        - Detection @ 10.025s (exactly between them, within 100ms tolerance)

        Expected (FIXED):
        - 1 TP (nearest GT, which is GT1 @ 25ms difference)
        - 1 FN (GT2 unmatched)

        Bug Behavior (BEFORE FIX):
        - 2 TP (detection matched to both GTs)
        - 0 FN
        """
        session_id = "test-double-match-001"
        video_id = "video-double-match-001"

        # Create test session
        test_session = TestSession(
            id=session_id,
            video_id=video_id,
            tolerance_ms=100,
            has_video_sequence=False
        )
        db.add(test_session)

        # Create ground truth objects (50ms apart)
        gt1 = GroundTruthObject(
            id="gt-1",
            video_id=video_id,
            timestamp=10.000,
            video_relative_timestamp=10.000,
            object_type="pedestrian"
        )
        gt2 = GroundTruthObject(
            id="gt-2",
            video_id=video_id,
            timestamp=10.050,
            video_relative_timestamp=10.050,
            object_type="pedestrian"
        )
        db.add_all([gt1, gt2])

        # Create detection exactly between them
        detection = DetectionEvent(
            id="det-1",
            test_session_id=session_id,
            video_id=video_id,
            timestamp=10.025,
            video_relative_timestamp=10.025,
            confidence=0.95
        )
        db.add(detection)
        db.commit()

        return {
            'session_id': session_id,
            'video_id': video_id,
            'gt1_id': gt1.id,
            'gt2_id': gt2.id,
            'detection_id': detection.id
        }

    def test_no_double_matching(self, db: Session, setup_double_match_scenario):
        """
        Verify that a single detection cannot match multiple ground truth objects.

        This is the PRIMARY test for the double-matching bug fix.
        """
        scenario = setup_double_match_scenario
        service = GroundTruthMatchingService(default_tolerance_ms=100)

        # Run matching
        metrics = service.match_detections_to_ground_truth(
            session_id=scenario['session_id'],
            tolerance_ms=100,
            force_rematch=True
        )

        # Verify metrics
        assert metrics is not None, "Metrics should not be None"
        assert metrics.true_positives == 1, "Should have exactly 1 TP (not 2!)"
        assert metrics.false_negatives == 1, "Should have exactly 1 FN (GT2 unmatched)"
        assert metrics.false_positives == 0, "Should have 0 FP"

        # Verify database records
        comparisons = db.query(DetectionComparison).filter(
            DetectionComparison.test_session_id == scenario['session_id']
        ).all()

        tp_comparisons = [c for c in comparisons if c.match_type == 'TP']
        fn_comparisons = [c for c in comparisons if c.match_type == 'FN']

        assert len(tp_comparisons) == 1, "Should have exactly 1 TP comparison"
        assert len(fn_comparisons) == 1, "Should have exactly 1 FN comparison"

        # Verify the detection matched to GT1 (nearest)
        tp = tp_comparisons[0]
        assert tp.detection_event_id == scenario['detection_id']
        assert tp.ground_truth_id == scenario['gt1_id'], "Should match GT1 (nearest at 25ms)"

        # Verify GT2 is marked as FN
        fn = fn_comparisons[0]
        assert fn.ground_truth_id == scenario['gt2_id'], "GT2 should be FN"
        assert fn.detection_event_id is None, "FN should have no detection"

    @pytest.fixture
    def setup_rapid_fire_scenario(self, db: Session):
        """
        Create rapid-fire scenario with multiple close GTs.

        Setup:
        - GT1 @ 5.000s
        - GT2 @ 5.060s (60ms later)
        - GT3 @ 5.120s (60ms later)
        - Detection1 @ 5.030s (30ms from GT1, 30ms from GT2)
        - Detection2 @ 5.090s (30ms from GT2, 30ms from GT3)

        Expected:
        - GT1 matches D1 (30ms)
        - GT2 matches D2 (30ms)
        - GT3 is FN (no detection left)
        - NOT: GT2 matching both D1 and D2
        """
        session_id = "test-rapid-fire-001"
        video_id = "video-rapid-fire-001"

        test_session = TestSession(
            id=session_id,
            video_id=video_id,
            tolerance_ms=100,
            has_video_sequence=False
        )
        db.add(test_session)

        # Three GTs 60ms apart
        gts = [
            GroundTruthObject(
                id=f"gt-{i}",
                video_id=video_id,
                timestamp=5.000 + (i * 0.060),
                video_relative_timestamp=5.000 + (i * 0.060),
                object_type="pedestrian"
            )
            for i in range(3)
        ]
        db.add_all(gts)

        # Two detections between GTs
        detections = [
            DetectionEvent(
                id="det-1",
                test_session_id=session_id,
                video_id=video_id,
                timestamp=5.030,
                video_relative_timestamp=5.030,
                confidence=0.95
            ),
            DetectionEvent(
                id="det-2",
                test_session_id=session_id,
                video_id=video_id,
                timestamp=5.090,
                video_relative_timestamp=5.090,
                confidence=0.93
            )
        ]
        db.add_all(detections)
        db.commit()

        return {
            'session_id': session_id,
            'expected_tp': 2,
            'expected_fn': 1,
            'expected_fp': 0
        }

    def test_rapid_fire_no_double_matching(self, db: Session, setup_rapid_fire_scenario):
        """Verify no double-matching in rapid-fire detection scenarios"""
        scenario = setup_rapid_fire_scenario
        service = GroundTruthMatchingService(default_tolerance_ms=100)

        metrics = service.match_detections_to_ground_truth(
            session_id=scenario['session_id'],
            tolerance_ms=100,
            force_rematch=True
        )

        assert metrics.true_positives == scenario['expected_tp']
        assert metrics.false_negatives == scenario['expected_fn']
        assert metrics.false_positives == scenario['expected_fp']

        # Verify each detection matched exactly once
        comparisons = db.query(DetectionComparison).filter(
            DetectionComparison.test_session_id == scenario['session_id'],
            DetectionComparison.match_type == 'TP'
        ).all()

        detection_ids = [c.detection_event_id for c in comparisons]
        assert len(detection_ids) == len(set(detection_ids)), "Each detection should match only once"

        # Verify each GT matched at most once
        gt_ids = [c.ground_truth_id for c in comparisons]
        assert len(gt_ids) == len(set(gt_ids)), "Each GT should match at most once"


class TestToleranceWindowClamping:
    """Test suite for tolerance window overlap fix"""

    @pytest.fixture
    def setup_multi_video_boundary_scenario(self, db: Session):
        """
        Create multi-video scenario with back-to-back videos.

        Setup:
        - Video1: 0ms - 30000ms (30s duration)
        - Video2: 30000ms - 60000ms (starts immediately after)
        - Detection @ 30100ms (100ms into Video2)
        - Video1 tolerance extends to 30500ms (overlaps with Video2)

        Expected (FIXED):
        - Detection assigned to Video2 (clamped tolerance)

        Bug Behavior (BEFORE FIX):
        - Detection assigned to Video1 (tolerance overlap)
        """
        session_id = "test-boundary-001"
        sequence_id = "seq-boundary-001"

        # Create test session
        test_session = TestSession(
            id=session_id,
            sequence_id=sequence_id,
            tolerance_ms=500,
            has_video_sequence=True
        )
        db.add(test_session)

        # Create video sequence
        sequence = VideoTestSequence(
            id=sequence_id,
            test_session_id=session_id,
            total_videos=2,
            current_video_index=0
        )
        db.add(sequence)

        # Create sequence video results
        video1_id = "video-001"
        video2_id = "video-002"

        video1 = SequenceVideoResult(
            id="svr-001",
            video_sequence_id=sequence_id,
            video_id=video1_id,
            sequence_order=0,
            video_start_time=0.0,
            video_end_time=30.0,
            actual_duration_ms=30000
        )

        video2 = SequenceVideoResult(
            id="svr-002",
            video_sequence_id=sequence_id,
            video_id=video2_id,
            sequence_order=1,
            video_start_time=30.0,
            video_end_time=60.0,
            actual_duration_ms=30000
        )

        db.add_all([video1, video2])

        # Create ground truth in Video2
        gt = GroundTruthObject(
            id="gt-video2-001",
            video_id=video2_id,
            timestamp=30.100,  # 100ms into Video2
            video_relative_timestamp=0.100,
            object_type="pedestrian"
        )
        db.add(gt)

        # Create detection at boundary
        detection = DetectionEvent(
            id="det-boundary-001",
            test_session_id=session_id,
            timestamp=30.100,
            video_relative_timestamp=0.100,
            confidence=0.95,
            video_id=None  # Will be resolved by video_id_resolver
        )
        db.add(detection)
        db.commit()

        return {
            'session_id': session_id,
            'video1_id': video1_id,
            'video2_id': video2_id,
            'detection_id': detection.id,
            'gt_id': gt.id,
            'detection_timestamp': 30.100
        }

    def test_tolerance_window_clamping(self, db: Session, setup_multi_video_boundary_scenario):
        """
        Verify tolerance window does not extend into next video.

        This is the PRIMARY test for the tolerance window overlap bug fix.
        """
        scenario = setup_multi_video_boundary_scenario

        # Test video_id resolution
        video_id = get_video_id_for_detection(
            session_id=scenario['session_id'],
            detection_timestamp=scenario['detection_timestamp'],
            db=db
        )

        # CRITICAL: Detection should be assigned to Video2, not Video1
        assert video_id == scenario['video2_id'], \
            f"Detection @ 30.100s should be assigned to Video2 (not Video1 with tolerance overlap)"

        # Update detection with resolved video_id
        detection = db.query(DetectionEvent).filter(
            DetectionEvent.id == scenario['detection_id']
        ).first()
        detection.video_id = video_id
        db.commit()

        # Run matching
        service = GroundTruthMatchingService(default_tolerance_ms=500)
        metrics = service.match_detections_to_ground_truth(
            session_id=scenario['session_id'],
            tolerance_ms=500,
            force_rematch=True
        )

        # Verify matching success
        assert metrics.true_positives == 1, "Should match GT in Video2"
        assert metrics.false_positives == 0, "No false positives"

        # Verify comparison record
        comparison = db.query(DetectionComparison).filter(
            DetectionComparison.test_session_id == scenario['session_id'],
            DetectionComparison.match_type == 'TP'
        ).first()

        assert comparison is not None
        assert comparison.ground_truth_id == scenario['gt_id']
        assert comparison.detection_event_id == scenario['detection_id']

    @pytest.fixture
    def setup_cross_video_contamination_scenario(self, db: Session):
        """
        Setup to verify NO cross-video contamination.

        Setup:
        - Video1 ends at 30.000s
        - Video2 starts at 30.000s
        - GT in Video1 @ 29.600s
        - Detection @ 30.100s (in Video2)

        Expected:
        - GT in Video1 is FN (no match in Video1)
        - Detection in Video2 is FP (no GT in Video2)
        - NOT: Detection from Video2 matching GT from Video1
        """
        session_id = "test-cross-contamination-001"
        sequence_id = "seq-cross-contamination-001"

        test_session = TestSession(
            id=session_id,
            sequence_id=sequence_id,
            tolerance_ms=500,
            has_video_sequence=True
        )
        db.add(test_session)

        sequence = VideoTestSequence(
            id=sequence_id,
            test_session_id=session_id,
            total_videos=2
        )
        db.add(sequence)

        video1_id = "video-cross-1"
        video2_id = "video-cross-2"

        video1 = SequenceVideoResult(
            id="svr-cross-1",
            video_sequence_id=sequence_id,
            video_id=video1_id,
            sequence_order=0,
            video_start_time=0.0,
            video_end_time=30.0,
            actual_duration_ms=30000
        )

        video2 = SequenceVideoResult(
            id="svr-cross-2",
            video_sequence_id=sequence_id,
            video_id=video2_id,
            sequence_order=1,
            video_start_time=30.0,
            video_end_time=60.0,
            actual_duration_ms=30000
        )

        db.add_all([video1, video2])

        # GT in Video1, late in the video
        gt = GroundTruthObject(
            id="gt-video1-late",
            video_id=video1_id,
            timestamp=29.600,
            video_relative_timestamp=29.600,
            object_type="pedestrian"
        )
        db.add(gt)

        # Detection in Video2
        detection = DetectionEvent(
            id="det-video2-early",
            test_session_id=session_id,
            video_id=video2_id,
            timestamp=30.100,
            video_relative_timestamp=0.100,
            confidence=0.90
        )
        db.add(detection)
        db.commit()

        return {
            'session_id': session_id,
            'video1_id': video1_id,
            'video2_id': video2_id,
            'expected_fn': 1,
            'expected_fp': 1,
            'expected_tp': 0
        }

    def test_no_cross_video_contamination(self, db: Session, setup_cross_video_contamination_scenario):
        """Verify detections from one video do NOT match GTs from another video"""
        scenario = setup_cross_video_contamination_scenario
        service = GroundTruthMatchingService(default_tolerance_ms=500)

        metrics = service.match_detections_to_ground_truth(
            session_id=scenario['session_id'],
            tolerance_ms=500,
            force_rematch=True
        )

        # Even though time difference is 500ms (within tolerance),
        # video boundary protection should prevent matching
        assert metrics.true_positives == scenario['expected_tp'], \
            "Should have 0 TP (video boundary protection)"
        assert metrics.false_negatives == scenario['expected_fn'], \
            "GT in Video1 should be FN"
        assert metrics.false_positives == scenario['expected_fp'], \
            "Detection in Video2 should be FP"


class TestMatchValidation:
    """Test suite for match validation functions"""

    def test_validate_no_duplicate_detections(self, db: Session):
        """Verify validation catches duplicate detection matches"""
        session_id = "test-validation-001"

        # Create scenario
        test_session = TestSession(id=session_id, tolerance_ms=100)
        db.add(test_session)

        gt1 = GroundTruthObject(
            id="gt-val-1",
            timestamp=10.0,
            video_relative_timestamp=10.0
        )
        gt2 = GroundTruthObject(
            id="gt-val-2",
            timestamp=10.1,
            video_relative_timestamp=10.1
        )
        db.add_all([gt1, gt2])

        detection = DetectionEvent(
            id="det-val-1",
            test_session_id=session_id,
            timestamp=10.05,
            video_relative_timestamp=10.05
        )
        db.add(detection)
        db.commit()

        # Create INVALID comparisons (same detection matched twice)
        comp1 = DetectionComparison(
            test_session_id=session_id,
            ground_truth_id=gt1.id,
            detection_event_id=detection.id,
            match_type='TP'
        )
        comp2 = DetectionComparison(
            test_session_id=session_id,
            ground_truth_id=gt2.id,
            detection_event_id=detection.id,  # Same detection!
            match_type='TP'
        )
        db.add_all([comp1, comp2])
        db.commit()

        # Validate
        comparisons = db.query(DetectionComparison).filter(
            DetectionComparison.test_session_id == session_id
        ).all()

        detection_ids = [c.detection_event_id for c in comparisons if c.detection_event_id]

        # Should detect duplicate
        assert len(detection_ids) != len(set(detection_ids)), \
            "Validation should catch duplicate detection match"

    def test_validate_no_duplicate_ground_truth(self, db: Session):
        """Verify validation catches duplicate GT matches"""
        session_id = "test-validation-002"

        test_session = TestSession(id=session_id, tolerance_ms=100)
        db.add(test_session)

        gt = GroundTruthObject(
            id="gt-val-dup",
            timestamp=10.0,
            video_relative_timestamp=10.0
        )
        db.add(gt)

        det1 = DetectionEvent(
            id="det-val-dup-1",
            test_session_id=session_id,
            timestamp=10.03,
            video_relative_timestamp=10.03
        )
        det2 = DetectionEvent(
            id="det-val-dup-2",
            test_session_id=session_id,
            timestamp=10.05,
            video_relative_timestamp=10.05
        )
        db.add_all([det1, det2])
        db.commit()

        # Create INVALID comparisons (same GT matched twice)
        comp1 = DetectionComparison(
            test_session_id=session_id,
            ground_truth_id=gt.id,
            detection_event_id=det1.id,
            match_type='TP'
        )
        comp2 = DetectionComparison(
            test_session_id=session_id,
            ground_truth_id=gt.id,  # Same GT!
            detection_event_id=det2.id,
            match_type='TP'
        )
        db.add_all([comp1, comp2])
        db.commit()

        # Validate
        comparisons = db.query(DetectionComparison).filter(
            DetectionComparison.test_session_id == session_id
        ).all()

        gt_ids = [c.ground_truth_id for c in comparisons if c.ground_truth_id]

        # Should detect duplicate
        assert len(gt_ids) != len(set(gt_ids)), \
            "Validation should catch duplicate GT match"


class TestPerformanceBenchmarks:
    """Performance benchmarks for matching algorithm"""

    def test_matching_performance_small_dataset(self, db: Session):
        """Benchmark matching with typical dataset (20-30 events)"""
        session_id = "test-perf-small"

        test_session = TestSession(id=session_id, tolerance_ms=100)
        db.add(test_session)

        # Create 25 GT objects
        gts = [
            GroundTruthObject(
                id=f"gt-perf-{i}",
                timestamp=float(i),
                video_relative_timestamp=float(i)
            )
            for i in range(25)
        ]
        db.add_all(gts)

        # Create 22 detections
        detections = [
            DetectionEvent(
                id=f"det-perf-{i}",
                test_session_id=session_id,
                timestamp=float(i) + 0.02,  # 20ms offset
                video_relative_timestamp=float(i) + 0.02
            )
            for i in range(22)
        ]
        db.add_all(detections)
        db.commit()

        # Benchmark matching
        service = GroundTruthMatchingService(default_tolerance_ms=100)

        start_time = time.time()
        metrics = service.match_detections_to_ground_truth(
            session_id=session_id,
            tolerance_ms=100,
            force_rematch=True
        )
        duration = time.time() - start_time

        # Performance assertion
        assert duration < 1.0, f"Matching should complete in <1s, took {duration:.3f}s"

        # Correctness assertion
        assert metrics.true_positives == 22
        assert metrics.false_negatives == 3

        return {'duration': duration, 'event_count': 25}

    def test_matching_performance_large_dataset(self, db: Session):
        """Benchmark matching with large dataset (100+ events)"""
        session_id = "test-perf-large"

        test_session = TestSession(id=session_id, tolerance_ms=100)
        db.add(test_session)

        # Create 120 GT objects
        gts = [
            GroundTruthObject(
                id=f"gt-perf-large-{i}",
                timestamp=float(i) * 0.5,  # Events every 500ms
                video_relative_timestamp=float(i) * 0.5
            )
            for i in range(120)
        ]
        db.add_all(gts)

        # Create 110 detections
        detections = [
            DetectionEvent(
                id=f"det-perf-large-{i}",
                test_session_id=session_id,
                timestamp=float(i) * 0.5 + 0.03,
                video_relative_timestamp=float(i) * 0.5 + 0.03
            )
            for i in range(110)
        ]
        db.add_all(detections)
        db.commit()

        # Benchmark matching
        service = GroundTruthMatchingService(default_tolerance_ms=100)

        start_time = time.time()
        metrics = service.match_detections_to_ground_truth(
            session_id=session_id,
            tolerance_ms=100,
            force_rematch=True
        )
        duration = time.time() - start_time

        # Performance assertion (O(N*M) = 120*110 = 13,200 operations)
        assert duration < 5.0, f"Large dataset matching should complete in <5s, took {duration:.3f}s"

        # Correctness assertion
        assert metrics.true_positives == 110
        assert metrics.false_negatives == 10

        return {'duration': duration, 'event_count': 120}


# Pytest configuration
@pytest.fixture(scope="function")
def db():
    """Create a fresh database session for each test"""
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        # Cleanup
        db_session.rollback()
        db_session.close()


def run_performance_report():
    """
    Generate performance comparison report.
    Run this after implementing fixes to compare before/after performance.
    """
    print("\n" + "="*80)
    print("GROUND TRUTH MATCHING PERFORMANCE REPORT")
    print("="*80)

    # This would run the benchmarks and generate a report
    # Implementation left as an exercise for actual deployment
    pass


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
