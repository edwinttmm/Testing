"""
Test Ground Truth Matching - Double-Matching Prevention

Critical Test: Verify one detection cannot match multiple ground truth objects.
Based on CONSOLIDATED_APPROVAL_PROCESS_ANALYSIS.md Lines 907-987
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models import DetectionEvent, GroundTruthObject, TestSession, Video, Project
from services.ground_truth_matching_service import GroundTruthMatchingService


class TestDoubleMatchingPrevention:
    """Test suite for double-matching prevention in GT algorithm"""

    @pytest.fixture
    def setup_double_matching_scenario(self, db_session: Session):
        """
        Setup scenario where detection falls between two GT objects

        Scenario:
          GT1 @ 10.000s
          GT2 @ 10.050s (50ms apart)
          Detection @ 10.025s (exactly between)

        Expected:
          - Detection matches nearest GT (either GT1 or GT2)
          - Other GT is marked as FN (missed)
          - NOT both GT1 and GT2 matched to same detection
        """
        # Create project and video
        project = Project(
            id="test-project",
            name="Double Match Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)

        video = Video(
            id="test-video",
            project_id=project.id,
            filename="test.mp4",
            duration_ms=30000
        )
        db_session.add(video)

        # Create test session
        session = TestSession(
            id="test-session",
            project_id=project.id,
            video_id=video.id,
            status="running",
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(session)

        # Create two GT objects 50ms apart
        gt1 = GroundTruthObject(
            id="gt1",
            video_id=video.id,
            timestamp=10.000,  # 10.000s
            object_type="pedestrian",
            soft_deleted=False
        )

        gt2 = GroundTruthObject(
            id="gt2",
            video_id=video.id,
            timestamp=10.050,  # 10.050s (50ms after GT1)
            object_type="pedestrian",
            soft_deleted=False
        )

        db_session.add_all([gt1, gt2])

        # Create detection exactly between them
        detection = DetectionEvent(
            id="det1",
            session_id=session.id,
            video_id=video.id,
            timestamp=10.025,  # Exactly between GT1 and GT2
            video_relative_timestamp=10025,
            voltage=5.0,
            classification=None,
            latency_ms=None
        )
        db_session.add(detection)

        db_session.commit()

        return {
            "session": session,
            "video": video,
            "gt1": gt1,
            "gt2": gt2,
            "detection": detection
        }

    def test_no_double_matching(self, db_session, setup_double_matching_scenario):
        """
        Test that one detection cannot match two GT objects

        Expected behavior:
          - Detection matches nearest GT (25ms to either)
          - Only ONE TP created
          - One FN for unmatched GT
          - Total: 1 TP, 0 FP, 1 FN
        """
        scenario = setup_double_matching_scenario

        service = GroundTruthMatchingService(db_session)

        # Match with 100ms tolerance (allows matching to both GTs)
        results = service.match_detections_to_ground_truth(
            session_id=scenario["session"].id,
            tolerance_ms=100.0
        )

        # Verify counts
        assert results.true_positives == 1, \
            f"Expected 1 TP, got {results.true_positives} (detection matched multiple GTs!)"

        assert results.false_positives == 0, \
            f"Expected 0 FP, got {results.false_positives}"

        assert results.false_negatives == 1, \
            f"Expected 1 FN, got {results.false_negatives} (both GTs matched!)"

        # Verify detection classified correctly
        detection = db_session.execute(select(DetectionEvent).filter_by(
            id=scenario["detection"].id
        )).scalar_one_or_none()

        assert detection.classification == "TP", \
            f"Detection should be TP, got {detection.classification}"

        assert detection.latency_ms is not None, \
            "TP detection should have latency_ms set"

        # Verify latency is 25ms (distance to either GT)
        assert abs(detection.latency_ms) == 25.0, \
            f"Expected latency 25ms, got {detection.latency_ms}"

    def test_rapid_fire_scenario(self, db_session):
        """
        Test rapid-fire GT events (high event rate)

        Scenario:
          GT @ 10.00s, 10.05s, 10.10s, 10.15s, 10.20s (50ms intervals)
          Detections @ 10.025s, 10.075s, 10.125s (between each pair)

        Expected:
          - Each detection matches ONE GT
          - No double-matching
          - Remaining GTs marked as FN
        """
        # Create project/video/session
        project = Project(
            id="rapid-project",
            name="Rapid Fire Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)

        video = Video(
            id="rapid-video",
            project_id=project.id,
            filename="rapid.mp4",
            duration_ms=30000
        )
        db_session.add(video)

        session = TestSession(
            id="rapid-session",
            project_id=project.id,
            video_id=video.id,
            status="running"
        )
        db_session.add(session)

        # Create 5 GT objects at 50ms intervals
        gt_timestamps = [10.00, 10.05, 10.10, 10.15, 10.20]
        for i, ts in enumerate(gt_timestamps):
            gt = GroundTruthObject(
                id=f"gt-{i}",
                video_id=video.id,
                timestamp=ts,
                object_type="pedestrian",
                soft_deleted=False
            )
            db_session.add(gt)

        # Create 3 detections between GTs
        detection_timestamps = [10.025, 10.075, 10.125]
        for i, ts in enumerate(detection_timestamps):
            det = DetectionEvent(
                id=f"det-{i}",
                session_id=session.id,
                video_id=video.id,
                timestamp=ts,
                video_relative_timestamp=ts * 1000,
                voltage=5.0
            )
            db_session.add(det)

        db_session.commit()

        # Run matching
        service = GroundTruthMatchingService(db_session)
        results = service.match_detections_to_ground_truth(
            session_id=session.id,
            tolerance_ms=100.0
        )

        # Expected: 3 TP (one per detection), 0 FP, 2 FN (2 unmatched GTs)
        assert results.true_positives == 3, \
            f"Expected 3 TP, got {results.true_positives}"

        assert results.false_positives == 0, \
            f"Expected 0 FP, got {results.false_positives}"

        assert results.false_negatives == 2, \
            f"Expected 2 FN (2 GTs missed), got {results.false_negatives}"

        # Verify each detection matched exactly once
        detections = db_session.execute(select(DetectionEvent).filter_by(
            session_id=session.id
        )).scalars().all()

        tp_count = sum(1 for d in detections if d.classification == "TP")
        assert tp_count == 3, f"Expected 3 TP detections, got {tp_count}"

    def test_tolerance_edge_case(self, db_session):
        """
        Test edge case where GT objects are exactly 2×tolerance apart

        Scenario:
          Tolerance = 100ms
          GT1 @ 10.000s
          GT2 @ 10.200s (200ms = 2×tolerance)
          Detection @ 10.100s (exactly in middle)

        Expected:
          - Detection matches ONE GT (whichever is processed first)
          - Other GT is FN
        """
        project = Project(
            id="edge-project",
            name="Edge Case Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)

        video = Video(
            id="edge-video",
            project_id=project.id,
            filename="edge.mp4",
            duration_ms=30000
        )
        db_session.add(video)

        session = TestSession(
            id="edge-session",
            project_id=project.id,
            video_id=video.id,
            status="running"
        )
        db_session.add(session)

        # GT objects 200ms apart
        gt1 = GroundTruthObject(
            id="edge-gt1",
            video_id=video.id,
            timestamp=10.000,
            object_type="pedestrian",
            soft_deleted=False
        )

        gt2 = GroundTruthObject(
            id="edge-gt2",
            video_id=video.id,
            timestamp=10.200,  # 200ms after GT1
            object_type="pedestrian",
            soft_deleted=False
        )

        db_session.add_all([gt1, gt2])

        # Detection in exact middle
        detection = DetectionEvent(
            id="edge-det",
            session_id=session.id,
            video_id=video.id,
            timestamp=10.100,  # 100ms from both
            video_relative_timestamp=10100,
            voltage=5.0
        )
        db_session.add(detection)

        db_session.commit()

        # Run matching with 100ms tolerance
        service = GroundTruthMatchingService(db_session)
        results = service.match_detections_to_ground_truth(
            session_id=session.id,
            tolerance_ms=100.0
        )

        # Both GTs are within tolerance, but only one should match
        assert results.true_positives == 1, \
            f"Expected 1 TP (detection matched once), got {results.true_positives}"

        assert results.false_negatives == 1, \
            f"Expected 1 FN (one GT unmatched), got {results.false_negatives}"


class TestMatchedDetectionTracking:
    """Test that matched_detection_ids set is properly maintained"""

    def test_matched_ids_prevent_reuse(self, db_session):
        """
        Test that matched_detection_ids set prevents same detection from being reused

        This tests the FIX recommended in the analysis document.
        """
        # Setup similar to double_matching scenario
        project = Project(
            id="tracking-project",
            name="ID Tracking Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)

        video = Video(
            id="tracking-video",
            project_id=project.id,
            filename="tracking.mp4",
            duration_ms=30000
        )
        db_session.add(video)

        session = TestSession(
            id="tracking-session",
            project_id=project.id,
            video_id=video.id,
            status="running"
        )
        db_session.add(session)

        # Three GT objects
        for i, ts in enumerate([10.0, 10.05, 10.1]):
            gt = GroundTruthObject(
                id=f"track-gt-{i}",
                video_id=video.id,
                timestamp=ts,
                object_type="pedestrian",
                soft_deleted=False
            )
            db_session.add(gt)

        # Single detection that could match multiple GTs
        detection = DetectionEvent(
            id="track-det",
            session_id=session.id,
            video_id=video.id,
            timestamp=10.05,  # Matches middle GT exactly
            video_relative_timestamp=10050,
            voltage=5.0
        )
        db_session.add(detection)

        db_session.commit()

        # Run matching
        service = GroundTruthMatchingService(db_session)
        results = service.match_detections_to_ground_truth(
            session_id=session.id,
            tolerance_ms=100.0
        )

        # Only one TP despite 3 GTs
        assert results.true_positives == 1, \
            "Detection should match exactly once"

        assert results.false_negatives == 2, \
            "Two GTs should be unmatched (FN)"

        # Verify detection classification
        det = db_session.execute(select(DetectionEvent).filter_by(
            id="track-det"
        )).scalar_one_or_none()

        assert det.classification == "TP"
        assert det.latency_ms == 0.0  # Exact match to GT2
