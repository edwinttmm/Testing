"""
Comprehensive Test Suite for Dual-Evaluation Architecture

Tests cover:
1. Accuracy evaluated independently from latency
2. Correct combination logic for overall result
3. Edge cases (no TP detections, perfect accuracy with slow latency)
4. Detailed metrics storage
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import json

from models import (
    TestSession,
    Video,
    DetectionEvent,
    GroundTruthObject,
    Project,
    EvaluationResult
)


class TestDualEvaluationArchitecture:
    """Test dual-evaluation: accuracy vs latency separation"""

    @pytest.fixture
    def setup_evaluation_data(self, test_db: Session):
        """Create test data for evaluation testing"""
        project = Project(
            name="Dual Evaluation Test",
            description="Testing accuracy vs latency separation",
            created_at=datetime.now(timezone.utc)
        )
        test_db.add(project)
        test_db.flush()

        session = TestSession(
            project_id=project.id,
            session_id="dual-eval-test",
            test_type="HIL",
            status="in_progress",
            accuracy_threshold=0.75,  # F1 >= 0.75 to pass
            latency_threshold_ms=100,  # <= 100ms to pass
            created_at=datetime.now(timezone.utc)
        )
        test_db.add(session)
        test_db.flush()

        video = Video(
            filename="test_video.mp4",
            original_name="test_video.mp4",
            session_id=session.id,
            sequence_number=1,
            duration=10.0,
            start_time=100.0,
            sequence_elapsed_time=1.0
        )
        test_db.add(video)
        test_db.flush()

        return {"project": project, "session": session, "video": video}

    def create_ground_truth_objects(self, test_db: Session, video_id: str, count: int):
        """Helper to create ground truth objects"""
        gt_objects = []
        for i in range(count):
            gt = GroundTruthObject(
                video_id=video_id,
                frame_number=i * 30,  # One per second at 30fps
                timestamp=100.0 + (i * 1.0),
                object_class="person",
                bounding_box={"x": 100 + i * 10, "y": 100, "width": 50, "height": 50},
                confidence=1.0
            )
            test_db.add(gt)
            gt_objects.append(gt)
        test_db.flush()
        return gt_objects

    def create_detection_events(self, test_db: Session, session_id: str, video_id: str,
                               ground_truth_objects: list, tp_count: int, fp_count: int,
                               avg_latency_ms: float):
        """Helper to create detection events with specified metrics"""
        detections = []

        # Create True Positives
        for i in range(min(tp_count, len(ground_truth_objects))):
            gt = ground_truth_objects[i]
            detection = DetectionEvent(
                session_id=session_id,
                video_id=video_id,
                timestamp=gt.timestamp + (avg_latency_ms / 1000.0),
                video_relative_timestamp=(gt.timestamp - 100.0),
                sequence_elapsed_time=1.0 + (gt.timestamp - 100.0),
                object_class=gt.object_class,
                confidence=0.95,
                bounding_box=gt.bounding_box,
                ground_truth_id=gt.id,
                latency_ms=avg_latency_ms,
                is_true_positive=True
            )
            test_db.add(detection)
            detections.append(detection)

        # Create False Positives
        for i in range(fp_count):
            detection = DetectionEvent(
                session_id=session_id,
                video_id=video_id,
                timestamp=105.0 + i,
                video_relative_timestamp=5.0 + i,
                sequence_elapsed_time=6.0 + i,
                object_class="person",
                confidence=0.85,
                bounding_box={"x": 200 + i * 10, "y": 200, "width": 50, "height": 50},
                ground_truth_id=None,
                is_true_positive=False
            )
            test_db.add(detection)
            detections.append(detection)

        test_db.flush()
        return detections

    def calculate_metrics(self, tp: int, fp: int, fn: int):
        """Calculate precision, recall, F1"""
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        return {"precision": precision, "recall": recall, "f1": f1}

    def evaluate_dual_metrics(self, f1: float, avg_latency_ms: float,
                             accuracy_threshold: float, latency_threshold_ms: float):
        """Dual evaluation logic"""
        # Accuracy evaluation (independent)
        if f1 >= accuracy_threshold:
            accuracy_result = "PASS"
        elif f1 >= accuracy_threshold * 0.9:  # 90% of threshold
            accuracy_result = "CONDITIONAL_PASS"
        else:
            accuracy_result = "FAIL"

        # Latency evaluation (independent)
        if avg_latency_ms == -1:  # No TP detections
            latency_result = "N/A"
        elif avg_latency_ms <= latency_threshold_ms:
            latency_result = "PASS"
        elif avg_latency_ms <= latency_threshold_ms * 1.5:  # 150% of threshold
            latency_result = "CONDITIONAL_PASS"
        else:
            latency_result = "FAIL"

        # Overall result (both must pass)
        if accuracy_result == "PASS" and latency_result == "PASS":
            overall_result = "PASS"
        elif accuracy_result == "FAIL" or latency_result == "FAIL":
            overall_result = "FAIL"
        else:
            overall_result = "CONDITIONAL_PASS"

        return {
            "accuracy_result": accuracy_result,
            "latency_result": latency_result,
            "overall_result": overall_result
        }

    def test_high_accuracy_good_latency_both_pass(self, test_db: Session, setup_evaluation_data):
        """F1=0.85, latency=80ms → accuracy PASS, latency PASS, overall PASS"""
        data = setup_evaluation_data
        session = data["session"]
        video = data["video"]

        # Create ground truth (10 objects)
        gt_objects = self.create_ground_truth_objects(test_db, video.id, 10)

        # Create detections: 9 TP, 1 FP → F1 = 0.85, latency = 80ms
        detections = self.create_detection_events(
            test_db, session.id, video.id, gt_objects,
            tp_count=9, fp_count=1, avg_latency_ms=80.0
        )
        test_db.commit()

        # Calculate metrics
        tp = 9
        fp = 1
        fn = 1  # 10 GT - 9 TP
        metrics = self.calculate_metrics(tp, fp, fn)

        assert abs(metrics["f1"] - 0.85) < 0.01, f"F1 should be ~0.85, got {metrics['f1']}"

        # Evaluate dual metrics
        results = self.evaluate_dual_metrics(
            metrics["f1"], 80.0,
            session.accuracy_threshold, session.latency_threshold_ms
        )

        assert results["accuracy_result"] == "PASS", \
            f"Accuracy should PASS (F1={metrics['f1']} >= {session.accuracy_threshold})"
        assert results["latency_result"] == "PASS", \
            f"Latency should PASS (80ms <= {session.latency_threshold_ms}ms)"
        assert results["overall_result"] == "PASS", "Overall should PASS"

    def test_high_accuracy_slow_latency_overall_fail(self, test_db: Session, setup_evaluation_data):
        """F1=0.85, latency=250ms → accuracy PASS, latency FAIL, overall FAIL"""
        data = setup_evaluation_data
        session = data["session"]
        video = data["video"]

        gt_objects = self.create_ground_truth_objects(test_db, video.id, 10)
        detections = self.create_detection_events(
            test_db, session.id, video.id, gt_objects,
            tp_count=9, fp_count=1, avg_latency_ms=250.0
        )
        test_db.commit()

        metrics = self.calculate_metrics(9, 1, 1)
        results = self.evaluate_dual_metrics(
            metrics["f1"], 250.0,
            session.accuracy_threshold, session.latency_threshold_ms
        )

        assert results["accuracy_result"] == "PASS"
        assert results["latency_result"] == "FAIL", \
            f"Latency should FAIL (250ms > {session.latency_threshold_ms}ms)"
        assert results["overall_result"] == "FAIL", "Overall should FAIL (latency failed)"

    def test_low_accuracy_good_latency_overall_fail(self, test_db: Session, setup_evaluation_data):
        """F1=0.50, latency=80ms → accuracy FAIL, latency PASS, overall FAIL"""
        data = setup_evaluation_data
        session = data["session"]
        video = data["video"]

        gt_objects = self.create_ground_truth_objects(test_db, video.id, 10)

        # Create detections: 5 TP, 5 FP → F1 = 0.50, latency = 80ms
        detections = self.create_detection_events(
            test_db, session.id, video.id, gt_objects,
            tp_count=5, fp_count=5, avg_latency_ms=80.0
        )
        test_db.commit()

        metrics = self.calculate_metrics(5, 5, 5)

        assert abs(metrics["f1"] - 0.50) < 0.01, f"F1 should be ~0.50, got {metrics['f1']}"

        results = self.evaluate_dual_metrics(
            metrics["f1"], 80.0,
            session.accuracy_threshold, session.latency_threshold_ms
        )

        assert results["accuracy_result"] == "FAIL", \
            f"Accuracy should FAIL (F1={metrics['f1']} < {session.accuracy_threshold})"
        assert results["latency_result"] == "PASS"
        assert results["overall_result"] == "FAIL", "Overall should FAIL (accuracy failed)"

    def test_no_tp_detections_latency_na(self, test_db: Session, setup_evaluation_data):
        """0 TP detections → latency result should be N/A"""
        data = setup_evaluation_data
        session = data["session"]
        video = data["video"]

        gt_objects = self.create_ground_truth_objects(test_db, video.id, 10)

        # Only false positives, no TPs
        detections = self.create_detection_events(
            test_db, session.id, video.id, gt_objects,
            tp_count=0, fp_count=5, avg_latency_ms=-1.0  # -1 indicates no latency data
        )
        test_db.commit()

        metrics = self.calculate_metrics(0, 5, 10)
        results = self.evaluate_dual_metrics(
            metrics["f1"], -1.0,
            session.accuracy_threshold, session.latency_threshold_ms
        )

        assert results["latency_result"] == "N/A", \
            "Latency should be N/A when there are no TP detections"
        assert results["accuracy_result"] == "FAIL", "Accuracy should FAIL (F1=0)"
        assert results["overall_result"] == "FAIL"

    def test_conditional_pass_combination(self, test_db: Session, setup_evaluation_data):
        """F1=0.70, latency=150ms → both CONDITIONAL_PASS, overall CONDITIONAL_PASS"""
        data = setup_evaluation_data
        session = data["session"]
        video = data["video"]

        # Set thresholds: accuracy=0.75, latency=100ms
        # F1=0.70 is 93% of threshold (>90% = CONDITIONAL_PASS)
        # Latency=150ms is 150% of threshold (<=150% = CONDITIONAL_PASS)

        gt_objects = self.create_ground_truth_objects(test_db, video.id, 10)

        # 7 TP, 3 FP, 3 FN → F1 = 0.70
        detections = self.create_detection_events(
            test_db, session.id, video.id, gt_objects,
            tp_count=7, fp_count=3, avg_latency_ms=150.0
        )
        test_db.commit()

        metrics = self.calculate_metrics(7, 3, 3)
        assert abs(metrics["f1"] - 0.70) < 0.01

        results = self.evaluate_dual_metrics(
            metrics["f1"], 150.0,
            session.accuracy_threshold, session.latency_threshold_ms
        )

        assert results["accuracy_result"] == "CONDITIONAL_PASS", \
            f"Accuracy should be CONDITIONAL_PASS (F1=0.70 is 93% of 0.75)"
        assert results["latency_result"] == "CONDITIONAL_PASS", \
            "Latency should be CONDITIONAL_PASS (150ms is 150% of 100ms)"
        assert results["overall_result"] == "CONDITIONAL_PASS"

    def test_evaluation_details_stored(self, test_db: Session, setup_evaluation_data):
        """Detailed metrics should be stored in evaluation_details JSON field"""
        data = setup_evaluation_data
        session = data["session"]
        video = data["video"]

        gt_objects = self.create_ground_truth_objects(test_db, video.id, 10)
        detections = self.create_detection_events(
            test_db, session.id, video.id, gt_objects,
            tp_count=8, fp_count=2, avg_latency_ms=90.0
        )
        test_db.commit()

        # Calculate metrics
        metrics = self.calculate_metrics(8, 2, 2)
        results = self.evaluate_dual_metrics(
            metrics["f1"], 90.0,
            session.accuracy_threshold, session.latency_threshold_ms
        )

        # Create evaluation result with detailed metrics
        evaluation = EvaluationResult(
            session_id=session.id,
            video_id=video.id,
            accuracy_score=metrics["f1"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            avg_latency_ms=90.0,
            true_positives=8,
            false_positives=2,
            false_negatives=2,
            accuracy_result=results["accuracy_result"],
            latency_result=results["latency_result"],
            overall_result=results["overall_result"],
            evaluation_details=json.dumps({
                "accuracy_evaluation": {
                    "f1_score": metrics["f1"],
                    "threshold": session.accuracy_threshold,
                    "result": results["accuracy_result"],
                    "reason": f"F1 {metrics['f1']:.2f} vs threshold {session.accuracy_threshold}"
                },
                "latency_evaluation": {
                    "avg_latency_ms": 90.0,
                    "threshold_ms": session.latency_threshold_ms,
                    "result": results["latency_result"],
                    "reason": f"Latency 90ms vs threshold {session.latency_threshold_ms}ms"
                },
                "combined_evaluation": {
                    "overall_result": results["overall_result"],
                    "reason": "Both metrics passed"
                }
            }),
            evaluated_at=datetime.now(timezone.utc)
        )
        test_db.add(evaluation)
        test_db.commit()

        # Verify stored data
        stored_eval = test_db.query(EvaluationResult).filter_by(session_id=session.id).first()
        assert stored_eval is not None
        assert stored_eval.accuracy_result == "PASS"
        assert stored_eval.latency_result == "PASS"
        assert stored_eval.overall_result == "PASS"

        # Verify JSON details
        details = json.loads(stored_eval.evaluation_details)
        assert "accuracy_evaluation" in details
        assert "latency_evaluation" in details
        assert "combined_evaluation" in details
        assert details["accuracy_evaluation"]["f1_score"] == metrics["f1"]
        assert details["latency_evaluation"]["avg_latency_ms"] == 90.0

    def test_edge_case_perfect_accuracy_zero_latency(self, test_db: Session, setup_evaluation_data):
        """Edge case: perfect accuracy (F1=1.0) with theoretical zero latency"""
        data = setup_evaluation_data
        session = data["session"]
        video = data["video"]

        gt_objects = self.create_ground_truth_objects(test_db, video.id, 10)
        detections = self.create_detection_events(
            test_db, session.id, video.id, gt_objects,
            tp_count=10, fp_count=0, avg_latency_ms=0.0
        )
        test_db.commit()

        metrics = self.calculate_metrics(10, 0, 0)
        assert metrics["f1"] == 1.0

        results = self.evaluate_dual_metrics(
            metrics["f1"], 0.0,
            session.accuracy_threshold, session.latency_threshold_ms
        )

        assert results["accuracy_result"] == "PASS"
        assert results["latency_result"] == "PASS"
        assert results["overall_result"] == "PASS"

    def test_edge_case_all_false_positives(self, test_db: Session, setup_evaluation_data):
        """Edge case: all detections are false positives"""
        data = setup_evaluation_data
        session = data["session"]
        video = data["video"]

        gt_objects = self.create_ground_truth_objects(test_db, video.id, 10)

        # All FPs, no TPs
        detections = self.create_detection_events(
            test_db, session.id, video.id, gt_objects,
            tp_count=0, fp_count=10, avg_latency_ms=-1.0
        )
        test_db.commit()

        metrics = self.calculate_metrics(0, 10, 10)
        assert metrics["f1"] == 0.0

        results = self.evaluate_dual_metrics(
            metrics["f1"], -1.0,
            session.accuracy_threshold, session.latency_threshold_ms
        )

        assert results["accuracy_result"] == "FAIL"
        assert results["latency_result"] == "N/A"
        assert results["overall_result"] == "FAIL"
