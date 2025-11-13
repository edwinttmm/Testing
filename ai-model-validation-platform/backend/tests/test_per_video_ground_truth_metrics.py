"""
Test Suite for Per-Video Ground Truth Metrics

Tests the new ground_truth_metrics field in the Enhanced HIL Results API
for multi-video test sessions.
"""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from models import (
    TestSession,
    DetectionEvent,
    GroundTruthObject,
    Video,
    VideoTestSequence,
    SequenceVideoResult
)


class TestPerVideoGroundTruthMetrics:
    """Test per-video ground truth metrics calculation"""

    @pytest.fixture
    def setup_test_data(self, db: Session):
        """Setup test data with multi-video sequence"""

        # Create test session
        session = TestSession(
            id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            session_type="hil_test",
            status="completed",
            has_video_sequence=True,
            tolerance_ms=100
        )
        db.add(session)
        db.flush()

        # Create video sequence
        sequence = VideoTestSequence(
            id=str(uuid.uuid4()),
            test_session_id=session.id,
            name="Test Sequence",
            video_ids=["video-1", "video-2"],
            sequence_order=[],
            status="completed",
            max_latency_ms=100,
            current_video_index=1,
            total_videos=2,
            completed_videos=2
        )
        db.add(sequence)
        db.flush()

        session.sequence_id = sequence.id

        # Create videos
        video1 = Video(
            id="video-1",
            project_id=session.project_id,
            filename="test_video_1.mp4",
            duration=30.0,
            status="completed"
        )
        video2 = Video(
            id="video-2",
            project_id=session.project_id,
            filename="test_video_2.mp4",
            duration=25.0,
            status="completed"
        )
        db.add_all([video1, video2])

        # Create sequence video results
        svr1 = SequenceVideoResult(
            id=str(uuid.uuid4()),
            video_sequence_id=sequence.id,
            video_id="video-1",
            sequence_order=0,
            video_status="completed",
            validation_result="pass"
        )
        svr2 = SequenceVideoResult(
            id=str(uuid.uuid4()),
            video_sequence_id=sequence.id,
            video_id="video-2",
            sequence_order=1,
            video_status="completed",
            validation_result="pass"
        )
        db.add_all([svr1, svr2])

        # Create ground truth for video 1 (10 objects)
        gt_objects_v1 = []
        for i in range(10):
            gt = GroundTruthObject(
                id=f"gt-v1-{i}",
                video_id="video-1",
                timestamp=float(i),
                class_label="pedestrian",
                x=0.5,
                y=0.5,
                width=0.1,
                height=0.1,
                deleted_at=None
            )
            gt_objects_v1.append(gt)
        db.add_all(gt_objects_v1)

        # Create ground truth for video 2 (5 objects)
        gt_objects_v2 = []
        for i in range(5):
            gt = GroundTruthObject(
                id=f"gt-v2-{i}",
                video_id="video-2",
                timestamp=float(i),
                class_label="cyclist",
                x=0.5,
                y=0.5,
                width=0.1,
                height=0.1,
                deleted_at=None
            )
            gt_objects_v2.append(gt)
        db.add_all(gt_objects_v2)

        # Create detections for video 1
        # 8 true positives (matched to ground truth)
        # 0 false positives (no unmatched detections)
        # Result: 2 false negatives (2 ground truth without detections)
        detections_v1 = []
        for i in range(8):
            det = DetectionEvent(
                id=str(uuid.uuid4()),
                test_session_id=session.id,
                video_id="video-1",
                timestamp=float(i),
                ground_truth_match_id=f"gt-v1-{i}",  # Matched
                validation_result="pass"
            )
            detections_v1.append(det)
        db.add_all(detections_v1)

        # Create detections for video 2
        # 5 true positives (matched to ground truth)
        # 1 false positive (unmatched detection)
        # Result: 0 false negatives (all ground truth matched)
        detections_v2 = []
        for i in range(5):
            det = DetectionEvent(
                id=str(uuid.uuid4()),
                test_session_id=session.id,
                video_id="video-2",
                timestamp=float(i),
                ground_truth_match_id=f"gt-v2-{i}",  # Matched
                validation_result="pass"
            )
            detections_v2.append(det)

        # Add 1 false positive
        fp_det = DetectionEvent(
            id=str(uuid.uuid4()),
            test_session_id=session.id,
            video_id="video-2",
            timestamp=10.0,
            ground_truth_match_id=None,  # No match = FP
            validation_result="fail"
        )
        detections_v2.append(fp_det)
        db.add_all(detections_v2)

        db.commit()

        return {
            "session": session,
            "sequence": sequence,
            "video1": video1,
            "video2": video2
        }

    def test_video1_metrics_calculation(self, setup_test_data, db: Session):
        """Test ground truth metrics for video 1"""
        session = setup_test_data["session"]

        # Expected metrics for video 1:
        # Total GT: 10
        # TP: 8 (8 detections with matches)
        # FP: 0 (no detections without matches)
        # FN: 2 (10 - 8 = 2 ground truth without detections)
        # Precision: 8 / (8 + 0) = 100%
        # Recall: 8 / (8 + 2) = 80%
        # F1: 2 * (100 * 80) / (100 + 80) = 88.89%

        # Query ground truth
        gt_count = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == "video-1",
            GroundTruthObject.deleted_at.is_(None)
        ).count()

        # Query detections
        detections = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id,
            DetectionEvent.video_id == "video-1"
        ).all()

        tp = sum(1 for d in detections if d.ground_truth_match_id is not None)
        fp = sum(1 for d in detections if d.ground_truth_match_id is None)
        fn = gt_count - tp

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        assert gt_count == 10
        assert tp == 8
        assert fp == 0
        assert fn == 2
        assert precision == 1.0  # 100%
        assert recall == 0.8  # 80%
        assert round(f1 * 100, 2) == 88.89

    def test_video2_metrics_calculation(self, setup_test_data, db: Session):
        """Test ground truth metrics for video 2"""
        session = setup_test_data["session"]

        # Expected metrics for video 2:
        # Total GT: 5
        # TP: 5 (5 detections with matches)
        # FP: 1 (1 detection without match)
        # FN: 0 (5 - 5 = 0 ground truth without detections)
        # Precision: 5 / (5 + 1) = 83.33%
        # Recall: 5 / (5 + 0) = 100%
        # F1: 2 * (83.33 * 100) / (83.33 + 100) = 90.91%

        gt_count = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == "video-2",
            GroundTruthObject.deleted_at.is_(None)
        ).count()

        detections = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id,
            DetectionEvent.video_id == "video-2"
        ).all()

        tp = sum(1 for d in detections if d.ground_truth_match_id is not None)
        fp = sum(1 for d in detections if d.ground_truth_match_id is None)
        fn = gt_count - tp

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        assert gt_count == 5
        assert tp == 5
        assert fp == 1
        assert fn == 0
        assert round(precision * 100, 2) == 83.33
        assert recall == 1.0  # 100%
        assert round(f1 * 100, 2) == 90.91

    def test_soft_deleted_ground_truth_excluded(self, setup_test_data, db: Session):
        """Test that soft-deleted ground truth is excluded from metrics"""
        session = setup_test_data["session"]

        # Soft delete one ground truth object
        gt_to_delete = db.query(GroundTruthObject).filter(
            GroundTruthObject.id == "gt-v1-0"
        ).first()
        gt_to_delete.deleted_at = datetime.utcnow()
        db.commit()

        # Now total GT should be 9 instead of 10
        gt_count = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == "video-1",
            GroundTruthObject.deleted_at.is_(None)
        ).count()

        assert gt_count == 9

    def test_zero_detections_edge_case(self, db: Session):
        """Test metrics when there are no detections"""
        # Create video with ground truth but no detections
        session = TestSession(
            id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            session_type="hil_test",
            status="completed"
        )
        db.add(session)
        db.flush()

        video = Video(
            id="video-empty",
            project_id=session.project_id,
            filename="empty.mp4",
            status="completed"
        )
        db.add(video)

        # Add ground truth
        gt = GroundTruthObject(
            id="gt-empty-1",
            video_id="video-empty",
            timestamp=1.0,
            class_label="pedestrian",
            x=0.5,
            y=0.5,
            width=0.1,
            height=0.1
        )
        db.add(gt)
        db.commit()

        # Query (no detections)
        gt_count = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == "video-empty",
            GroundTruthObject.deleted_at.is_(None)
        ).count()

        detections = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id,
            DetectionEvent.video_id == "video-empty"
        ).all()

        tp = sum(1 for d in detections if d.ground_truth_match_id is not None)
        fp = sum(1 for d in detections if d.ground_truth_match_id is None)
        fn = gt_count - tp

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

        assert gt_count == 1
        assert tp == 0
        assert fp == 0
        assert fn == 1
        assert precision == 0.0
        assert recall == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
