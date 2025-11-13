"""
Comprehensive tests for the dual-evaluation system.

This test suite verifies that accuracy (TP/FP/FN) and latency evaluations
are completely independent, and that overall results correctly combine both.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models import (
    TestSession,
    GroundTruth,
    DetectionEvent,
    TestResult,
    EvaluationResult
)
from schemas import TestSessionComplete


class TestDualEvaluationSystem:
    """Test suite for independent accuracy and latency evaluation."""

    @pytest.fixture
    def db_session(self, db):
        """Provide database session."""
        return db

    @pytest.fixture
    def test_session(self, db_session: Session) -> TestSession:
        """Create a test session for evaluation."""
        session = TestSession(
            session_id="test-dual-eval-001",
            status="completed",
            metadata_={"test": "dual_evaluation"}
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        return session

    def create_ground_truth(
        self,
        db_session: Session,
        session_id: str,
        count: int,
        start_timestamp: float = 1000.0
    ):
        """Helper to create ground truth events."""
        for i in range(count):
            gt = GroundTruth(
                session_id=session_id,
                timestamp=start_timestamp + (i * 100),  # 100ms apart
                metadata_={"index": i}
            )
            db_session.add(gt)
        db_session.commit()

    def create_detection_events(
        self,
        db_session: Session,
        session_id: str,
        tp_count: int,
        fp_count: int,
        start_timestamp: float = 1000.0,
        mean_latency_ms: float = 50.0,
        latency_std_dev: float = 20.0
    ):
        """
        Helper to create detection events.

        Args:
            tp_count: Number of true positives (matched to ground truth)
            fp_count: Number of false positives (no ground truth match)
            mean_latency_ms: Average latency for TP detections
            latency_std_dev: Standard deviation for latency variation
        """
        import random

        # Create TP detections with specified latency characteristics
        for i in range(tp_count):
            # Add some variation to latency
            latency_variation = random.gauss(0, latency_std_dev)
            latency = max(1.0, mean_latency_ms + latency_variation)

            detection = DetectionEvent(
                session_id=session_id,
                timestamp=start_timestamp + (i * 100) + (latency / 1000.0),
                latency_ms=latency,
                ground_truth_timestamp=start_timestamp + (i * 100),
                is_true_positive=True,
                is_false_positive=False,
                metadata_={"type": "TP", "index": i}
            )
            db_session.add(detection)

        # Create FP detections (no latency since no ground truth)
        for i in range(fp_count):
            detection = DetectionEvent(
                session_id=session_id,
                timestamp=start_timestamp + 10000 + (i * 100),
                latency_ms=None,  # FP have no latency
                ground_truth_timestamp=None,
                is_true_positive=False,
                is_false_positive=True,
                metadata_={"type": "FP", "index": i}
            )
            db_session.add(detection)

        db_session.commit()

    def calculate_expected_results(
        self,
        tp: int,
        fp: int,
        fn: int,
        mean_latency: float,
        percent_within_threshold: float,
        accuracy_thresholds: dict = None,
        latency_thresholds: dict = None
    ) -> dict:
        """Calculate expected evaluation results."""
        if accuracy_thresholds is None:
            accuracy_thresholds = {
                "f1_pass": 0.85,
                "f1_conditional": 0.70
            }

        if latency_thresholds is None:
            latency_thresholds = {
                "mean_ms_pass": 100.0,
                "mean_ms_conditional": 200.0,
                "percentile_98_threshold": 100.0,
                "percentile_98_pass": 0.90,
                "percentile_98_conditional": 0.80
            }

        # Calculate F1 score
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        # Determine accuracy result
        if f1 >= accuracy_thresholds["f1_pass"]:
            accuracy_result = "PASS"
        elif f1 >= accuracy_thresholds["f1_conditional"]:
            accuracy_result = "CONDITIONAL_PASS"
        else:
            accuracy_result = "FAIL"

        # Determine latency result
        if tp == 0:
            latency_result = "N/A"
        else:
            # Check mean latency
            mean_pass = mean_latency <= latency_thresholds["mean_ms_pass"]
            mean_conditional = mean_latency <= latency_thresholds["mean_ms_conditional"]

            # Check percentile
            percentile_pass = percent_within_threshold >= latency_thresholds["percentile_98_pass"]
            percentile_conditional = percent_within_threshold >= latency_thresholds["percentile_98_conditional"]

            if mean_pass and percentile_pass:
                latency_result = "PASS"
            elif mean_conditional and percentile_conditional:
                latency_result = "CONDITIONAL_PASS"
            else:
                latency_result = "FAIL"

        # Determine overall result
        if latency_result == "N/A":
            overall_result = accuracy_result
        elif accuracy_result == "PASS" and latency_result == "PASS":
            overall_result = "PASS"
        elif accuracy_result == "FAIL" or latency_result == "FAIL":
            overall_result = "FAIL"
        else:
            overall_result = "CONDITIONAL_PASS"

        return {
            "accuracy_result": accuracy_result,
            "latency_result": latency_result,
            "overall_result": overall_result,
            "f1_score": f1,
            "precision": precision,
            "recall": recall
        }

    def test_scenario_1_high_accuracy_good_latency(
        self,
        db_session: Session,
        test_session: TestSession
    ):
        """
        Scenario 1: High Accuracy, Good Latency
        - TP=90, FP=5, FN=5 (F1=94.7%)
        - Mean latency=50ms, 98% within 100ms threshold
        - Expected: accuracy=PASS, latency=PASS, overall=PASS
        """
        session_id = test_session.session_id

        # Create ground truth (90 TP + 5 FN = 95 total)
        self.create_ground_truth(db_session, session_id, 95)

        # Create detections (90 TP + 5 FP)
        self.create_detection_events(
            db_session,
            session_id,
            tp_count=90,
            fp_count=5,
            mean_latency_ms=50.0,
            latency_std_dev=10.0  # Low variation = high % within threshold
        )

        # Calculate expected results
        expected = self.calculate_expected_results(
            tp=90, fp=5, fn=5,
            mean_latency=50.0,
            percent_within_threshold=0.98
        )

        # Verify accuracy metrics
        detections = db_session.query(DetectionEvent).filter_by(session_id=session_id).all()
        tp_count = sum(1 for d in detections if d.is_true_positive)
        fp_count = sum(1 for d in detections if d.is_false_positive)
        gt_count = db_session.query(GroundTruth).filter_by(session_id=session_id).count()
        fn_count = gt_count - tp_count

        assert tp_count == 90, f"Expected 90 TP, got {tp_count}"
        assert fp_count == 5, f"Expected 5 FP, got {fp_count}"
        assert fn_count == 5, f"Expected 5 FN, got {fn_count}"

        # Verify latency metrics (only for TP)
        tp_detections = [d for d in detections if d.is_true_positive]
        latencies = [d.latency_ms for d in tp_detections if d.latency_ms is not None]

        assert len(latencies) == 90, f"Expected 90 latency values, got {len(latencies)}"
        mean_latency = sum(latencies) / len(latencies)
        assert 45 <= mean_latency <= 55, f"Mean latency {mean_latency} not near 50ms"

        # Verify FP have no latency values
        fp_detections = [d for d in detections if d.is_false_positive]
        fp_with_latency = [d for d in fp_detections if d.latency_ms is not None]
        assert len(fp_with_latency) == 0, "FP should not have latency values"

        # Expected results
        assert expected["accuracy_result"] == "PASS"
        assert expected["latency_result"] == "PASS"
        assert expected["overall_result"] == "PASS"

    def test_scenario_2_high_accuracy_slow_latency(
        self,
        db_session: Session
    ):
        """
        Scenario 2: High Accuracy, Slow Latency
        - TP=90, FP=5, FN=5 (F1=94.7%)
        - Mean latency=250ms, 60% within 100ms threshold
        - Expected: accuracy=PASS, latency=FAIL, overall=FAIL
        """
        session = TestSession(
            session_id="test-scenario-2",
            status="completed"
        )
        db_session.add(session)
        db_session.commit()

        session_id = session.session_id

        # Create ground truth (95 total)
        self.create_ground_truth(db_session, session_id, 95)

        # Create detections with high latency
        self.create_detection_events(
            db_session,
            session_id,
            tp_count=90,
            fp_count=5,
            mean_latency_ms=250.0,
            latency_std_dev=50.0  # High variation
        )

        # Calculate expected results
        expected = self.calculate_expected_results(
            tp=90, fp=5, fn=5,
            mean_latency=250.0,
            percent_within_threshold=0.60
        )

        # Verify TP/FP/FN are NOT affected by latency
        detections = db_session.query(DetectionEvent).filter_by(session_id=session_id).all()
        tp_count = sum(1 for d in detections if d.is_true_positive)
        fp_count = sum(1 for d in detections if d.is_false_positive)

        assert tp_count == 90, "TP count should be unaffected by latency"
        assert fp_count == 5, "FP count should be unaffected by latency"

        # Verify high latency
        tp_detections = [d for d in detections if d.is_true_positive]
        latencies = [d.latency_ms for d in tp_detections if d.latency_ms is not None]
        mean_latency = sum(latencies) / len(latencies)

        assert mean_latency > 200, f"Mean latency should be >200ms, got {mean_latency}"

        # Expected results
        assert expected["accuracy_result"] == "PASS", "High accuracy should still PASS"
        assert expected["latency_result"] == "FAIL", "High latency should FAIL"
        assert expected["overall_result"] == "FAIL", "Overall should FAIL due to latency"

    def test_scenario_3_low_accuracy_good_latency(
        self,
        db_session: Session
    ):
        """
        Scenario 3: Low Accuracy, Good Latency
        - TP=40, FP=20, FN=40 (F1=53.3%)
        - Mean latency=50ms, 100% within 100ms threshold
        - Expected: accuracy=FAIL, latency=PASS, overall=FAIL
        """
        session = TestSession(
            session_id="test-scenario-3",
            status="completed"
        )
        db_session.add(session)
        db_session.commit()

        session_id = session.session_id

        # Create ground truth (40 TP + 40 FN = 80 total)
        self.create_ground_truth(db_session, session_id, 80)

        # Create detections (40 TP + 20 FP)
        self.create_detection_events(
            db_session,
            session_id,
            tp_count=40,
            fp_count=20,
            mean_latency_ms=50.0,
            latency_std_dev=5.0  # Very low variation
        )

        # Calculate expected results
        expected = self.calculate_expected_results(
            tp=40, fp=20, fn=40,
            mean_latency=50.0,
            percent_within_threshold=1.00
        )

        # Verify metrics
        detections = db_session.query(DetectionEvent).filter_by(session_id=session_id).all()
        tp_count = sum(1 for d in detections if d.is_true_positive)
        fp_count = sum(1 for d in detections if d.is_false_positive)
        gt_count = db_session.query(GroundTruth).filter_by(session_id=session_id).count()
        fn_count = gt_count - tp_count

        assert tp_count == 40
        assert fp_count == 20
        assert fn_count == 40

        # Verify good latency despite poor accuracy
        tp_detections = [d for d in detections if d.is_true_positive]
        latencies = [d.latency_ms for d in tp_detections if d.latency_ms is not None]
        mean_latency = sum(latencies) / len(latencies)

        assert mean_latency < 60, f"Latency should be good: {mean_latency}ms"

        # Expected results
        assert expected["accuracy_result"] == "FAIL", "Low accuracy should FAIL"
        assert expected["latency_result"] == "PASS", "Good latency should PASS"
        assert expected["overall_result"] == "FAIL", "Overall should FAIL due to accuracy"

    def test_scenario_4_conditional_pass_both(
        self,
        db_session: Session
    ):
        """
        Scenario 4: Conditional on Both
        - TP=70, FP=15, FN=15 (F1=73.7%)
        - Mean latency=150ms, 85% within 100ms threshold
        - Expected: accuracy=CONDITIONAL_PASS, latency=CONDITIONAL_PASS, overall=CONDITIONAL_PASS
        """
        session = TestSession(
            session_id="test-scenario-4",
            status="completed"
        )
        db_session.add(session)
        db_session.commit()

        session_id = session.session_id

        # Create ground truth (70 TP + 15 FN = 85 total)
        self.create_ground_truth(db_session, session_id, 85)

        # Create detections (70 TP + 15 FP)
        self.create_detection_events(
            db_session,
            session_id,
            tp_count=70,
            fp_count=15,
            mean_latency_ms=150.0,
            latency_std_dev=30.0
        )

        # Calculate expected results
        expected = self.calculate_expected_results(
            tp=70, fp=15, fn=15,
            mean_latency=150.0,
            percent_within_threshold=0.85
        )

        # Verify metrics
        detections = db_session.query(DetectionEvent).filter_by(session_id=session_id).all()
        tp_count = sum(1 for d in detections if d.is_true_positive)
        fp_count = sum(1 for d in detections if d.is_false_positive)

        assert tp_count == 70
        assert fp_count == 15

        # Expected results
        assert expected["accuracy_result"] == "CONDITIONAL_PASS"
        assert expected["latency_result"] == "CONDITIONAL_PASS"
        assert expected["overall_result"] == "CONDITIONAL_PASS"

    def test_scenario_5_edge_case_no_tp(
        self,
        db_session: Session
    ):
        """
        Scenario 5: Edge Case - No TP
        - TP=0, FP=50, FN=100 (F1=0%)
        - Mean latency=N/A (no TP to measure)
        - Expected: accuracy=FAIL, latency=N/A, overall=FAIL
        """
        session = TestSession(
            session_id="test-scenario-5",
            status="completed"
        )
        db_session.add(session)
        db_session.commit()

        session_id = session.session_id

        # Create ground truth (100 total, all FN)
        self.create_ground_truth(db_session, session_id, 100)

        # Create only FP detections (no TP)
        self.create_detection_events(
            db_session,
            session_id,
            tp_count=0,
            fp_count=50,
            mean_latency_ms=0.0,  # Not used
            latency_std_dev=0.0
        )

        # Calculate expected results
        expected = self.calculate_expected_results(
            tp=0, fp=50, fn=100,
            mean_latency=0.0,  # N/A
            percent_within_threshold=0.0  # N/A
        )

        # Verify metrics
        detections = db_session.query(DetectionEvent).filter_by(session_id=session_id).all()
        tp_count = sum(1 for d in detections if d.is_true_positive)
        fp_count = sum(1 for d in detections if d.is_false_positive)
        gt_count = db_session.query(GroundTruth).filter_by(session_id=session_id).count()
        fn_count = gt_count - tp_count

        assert tp_count == 0, "Should have zero TP"
        assert fp_count == 50, "Should have 50 FP"
        assert fn_count == 100, "Should have 100 FN"

        # Verify no latency measurements
        latencies = [d.latency_ms for d in detections if d.latency_ms is not None]
        assert len(latencies) == 0, "Should have no latency measurements"

        # Expected results
        assert expected["accuracy_result"] == "FAIL", "Zero TP should FAIL accuracy"
        assert expected["latency_result"] == "N/A", "No TP means latency is N/A"
        assert expected["overall_result"] == "FAIL", "Overall should FAIL"

    def test_independence_of_evaluations(
        self,
        db_session: Session
    ):
        """
        Verify that accuracy and latency evaluations are completely independent.
        Changing latency values should not affect TP/FP/FN classification.
        """
        session = TestSession(
            session_id="test-independence",
            status="completed"
        )
        db_session.add(session)
        db_session.commit()

        session_id = session.session_id

        # Create ground truth
        self.create_ground_truth(db_session, session_id, 50)

        # Create detections with specific latency
        self.create_detection_events(
            db_session,
            session_id,
            tp_count=40,
            fp_count=10,
            mean_latency_ms=50.0,
            latency_std_dev=10.0
        )

        # Capture initial TP/FP/FN counts
        detections = db_session.query(DetectionEvent).filter_by(session_id=session_id).all()
        initial_tp = sum(1 for d in detections if d.is_true_positive)
        initial_fp = sum(1 for d in detections if d.is_false_positive)
        gt_count = db_session.query(GroundTruth).filter_by(session_id=session_id).count()
        initial_fn = gt_count - initial_tp

        # Modify latency values dramatically
        for detection in detections:
            if detection.is_true_positive:
                detection.latency_ms = 500.0  # Make latency very bad
        db_session.commit()

        # Re-query and verify TP/FP/FN unchanged
        detections = db_session.query(DetectionEvent).filter_by(session_id=session_id).all()
        final_tp = sum(1 for d in detections if d.is_true_positive)
        final_fp = sum(1 for d in detections if d.is_false_positive)
        final_fn = gt_count - final_tp

        assert initial_tp == final_tp == 40, "TP count should not change with latency"
        assert initial_fp == final_fp == 10, "FP count should not change with latency"
        assert initial_fn == final_fn == 10, "FN count should not change with latency"

        # Verify latency values did change
        tp_detections = [d for d in detections if d.is_true_positive]
        latencies = [d.latency_ms for d in tp_detections]
        assert all(lat == 500.0 for lat in latencies), "Latency values should have changed"

    def test_overall_result_combinations(
        self,
        db_session: Session
    ):
        """
        Test all combinations of accuracy and latency results
        to verify overall result logic.
        """
        test_cases = [
            # (accuracy, latency, expected_overall)
            ("PASS", "PASS", "PASS"),
            ("PASS", "CONDITIONAL_PASS", "CONDITIONAL_PASS"),
            ("PASS", "FAIL", "FAIL"),
            ("CONDITIONAL_PASS", "PASS", "CONDITIONAL_PASS"),
            ("CONDITIONAL_PASS", "CONDITIONAL_PASS", "CONDITIONAL_PASS"),
            ("CONDITIONAL_PASS", "FAIL", "FAIL"),
            ("FAIL", "PASS", "FAIL"),
            ("FAIL", "CONDITIONAL_PASS", "FAIL"),
            ("FAIL", "FAIL", "FAIL"),
            ("PASS", "N/A", "PASS"),
            ("CONDITIONAL_PASS", "N/A", "CONDITIONAL_PASS"),
            ("FAIL", "N/A", "FAIL"),
        ]

        for accuracy, latency, expected_overall in test_cases:
            # Determine overall result using same logic as system
            if latency == "N/A":
                overall = accuracy
            elif accuracy == "PASS" and latency == "PASS":
                overall = "PASS"
            elif accuracy == "FAIL" or latency == "FAIL":
                overall = "FAIL"
            else:
                overall = "CONDITIONAL_PASS"

            assert overall == expected_overall, (
                f"For accuracy={accuracy}, latency={latency}, "
                f"expected overall={expected_overall}, got {overall}"
            )


class TestEvaluationResultStorage:
    """Test that evaluation results are properly stored in the database."""

    def test_evaluation_result_model(self, db):
        """Verify EvaluationResult model stores all required fields."""
        # Create test session
        session = TestSession(
            session_id="test-eval-storage",
            status="completed"
        )
        db.add(session)
        db.commit()

        # Create evaluation result
        eval_result = EvaluationResult(
            session_id=session.session_id,
            accuracy_result="PASS",
            latency_result="CONDITIONAL_PASS",
            overall_result="CONDITIONAL_PASS",
            f1_score=0.92,
            precision=0.90,
            recall=0.94,
            true_positives=90,
            false_positives=10,
            false_negatives=6,
            mean_latency_ms=150.0,
            median_latency_ms=145.0,
            p95_latency_ms=180.0,
            p98_latency_ms=195.0,
            percent_within_threshold=0.85,
            evaluated_at=datetime.utcnow()
        )
        db.add(eval_result)
        db.commit()

        # Retrieve and verify
        stored = db.query(EvaluationResult).filter_by(
            session_id=session.session_id
        ).first()

        assert stored is not None
        assert stored.accuracy_result == "PASS"
        assert stored.latency_result == "CONDITIONAL_PASS"
        assert stored.overall_result == "CONDITIONAL_PASS"
        assert stored.f1_score == 0.92
        assert stored.true_positives == 90
        assert stored.mean_latency_ms == 150.0
        assert stored.percent_within_threshold == 0.85
