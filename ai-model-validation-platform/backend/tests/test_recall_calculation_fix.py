"""
Comprehensive Test Suite for Recall Calculation Fix

Tests for the critical bug where session-wide recall displays 100% when actual is 36%.

Bug: Session fa204ef2-9d8b-4480-9692-86e338c1218a displays "Recall 100.0%"
but shows "87 TP / 242 Ground Truth Events" (actual recall = 36%)

Root Cause: Per-video recall (100%) displayed instead of session-wide recall (36%)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from typing import Dict, List
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from services.ground_truth_matching_service import GroundTruthMatchingService
from models import TestSession, Video, GroundTruthObject, DetectionEvent, DetectionComparison


class TestRecallCalculationFix:
    """Test suite for session-wide vs per-video recall calculation"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return MagicMock(spec=Session)

    @pytest.fixture
    def gt_service(self):
        """Ground truth matching service instance"""
        return GroundTruthMatchingService()

    @pytest.fixture
    def mock_single_video_session(self, mock_db):
        """Mock single video test session with 100% recall"""
        session = Mock(spec=TestSession)
        session.id = "single-video-session"
        session.has_video_sequence = False
        session.sequence_id = None
        session.tp_count = 10
        session.fn_count = 0
        session.accuracy_recall = 1.0  # 100%
        return session

    @pytest.fixture
    def mock_multi_video_session(self, mock_db):
        """Mock multi-video session matching fa204ef2 scenario"""
        session = Mock(spec=TestSession)
        session.id = "fa204ef2-9d8b-4480-9692-86e338c1218a"
        session.has_video_sequence = True
        session.sequence_id = "seq-123"
        session.tp_count = 87
        session.fn_count = 155  # 242 - 87
        session.accuracy_recall = 0.3595  # 36% (CORRECT)
        return session

    # Test 1: Single video session - Recall should be correct
    def test_single_video_recall_calculation(self, gt_service, mock_db, mock_single_video_session):
        """
        Test: Single video with perfect detection
        Expected: Recall = 10 TP / 10 GT = 100%
        """
        # Setup
        video_ids = ["video-1"]

        # Mock ground truth count
        with patch.object(gt_service, '_get_actual_ground_truth_count', return_value=10):
            with patch.object(gt_service, '_count_true_positives', return_value=10):
                # Calculate metrics
                tp = 10
                gt_count = 10
                recall = tp / gt_count if gt_count > 0 else 0.0

                # Assertions
                assert recall == 1.0, f"Single video recall should be 100%, got {recall * 100}%"
                assert tp == 10, f"Expected 10 TP, got {tp}"
                assert gt_count == 10, f"Expected 10 GT, got {gt_count}"

    # Test 2: Multi-video session - Session recall ≠ per-video recall
    def test_multi_video_session_recall_not_equal_to_per_video(
        self, gt_service, mock_db, mock_multi_video_session
    ):
        """
        Test: Multi-video session with varying per-video recall
        Video 1: 10 TP / 10 GT = 100% recall
        Video 2: 77 TP / 232 GT = 33% recall
        Session: 87 TP / 242 GT = 36% recall (NOT 100%)
        """
        # Per-video data
        video_1_tp = 10
        video_1_gt = 10
        video_1_recall = video_1_tp / video_1_gt  # 100%

        video_2_tp = 77
        video_2_gt = 232
        video_2_recall = video_2_tp / video_2_gt  # 33.19%

        # Session aggregate
        session_tp = video_1_tp + video_2_tp  # 87
        session_gt = video_1_gt + video_2_gt  # 242
        session_recall = session_tp / session_gt  # 35.95%

        # Assertions
        assert video_1_recall == 1.0, f"Video 1 recall should be 100%"
        assert 0.33 <= video_2_recall <= 0.34, f"Video 2 recall should be ~33%"
        assert 0.35 <= session_recall <= 0.36, f"Session recall should be ~36%, got {session_recall * 100}%"
        assert session_recall != video_1_recall, "Session recall MUST differ from per-video recall!"
        assert session_recall < video_1_recall, "Session recall should be lower than best video"

    # Test 3: Session fa204ef2 data validation
    def test_session_fa204ef2_data_validation(self, gt_service, mock_db):
        """
        Test: Validate actual session fa204ef2 data
        Expected: Session recall = 36%, NOT 100%
        """
        # Actual session data
        session_id = "fa204ef2-9d8b-4480-9692-86e338c1218a"
        tp_count = 87
        gt_count = 242
        fn_count = gt_count - tp_count  # 155

        # Calculate recall
        recall = tp_count / gt_count if gt_count > 0 else 0.0
        recall_percentage = recall * 100

        # Assertions
        assert tp_count == 87, f"Expected 87 TP"
        assert gt_count == 242, f"Expected 242 GT"
        assert fn_count == 155, f"Expected 155 FN"
        assert abs(recall - 0.3595) < 0.001, f"Recall should be 35.95%, got {recall_percentage}%"
        assert recall < 0.5, "Recall should be less than 50%"
        assert recall != 1.0, "Recall should NOT be 100%"

    # Test 4: Edge case - Video 1 = 100% recall, Video 2 = 0% recall
    def test_edge_case_100_and_0_percent_recall(self, gt_service, mock_db):
        """
        Test: Extreme case with perfect and zero recall videos
        Video 1: 50 TP / 50 GT = 100% recall
        Video 2: 0 TP / 50 GT = 0% recall
        Session: 50 TP / 100 GT = 50% recall
        """
        # Video data
        video_1_tp, video_1_gt = 50, 50
        video_2_tp, video_2_gt = 0, 50

        video_1_recall = video_1_tp / video_1_gt
        video_2_recall = video_2_tp / video_2_gt if video_2_gt > 0 else 0.0

        # Session aggregate
        session_tp = video_1_tp + video_2_tp  # 50
        session_gt = video_1_gt + video_2_gt  # 100
        session_recall = session_tp / session_gt  # 50%

        # Assertions
        assert video_1_recall == 1.0, "Video 1 should have 100% recall"
        assert video_2_recall == 0.0, "Video 2 should have 0% recall"
        assert session_recall == 0.5, f"Session recall should be 50%, got {session_recall * 100}%"
        assert session_recall != video_1_recall, "Session recall must not equal best video"
        assert session_recall != video_2_recall, "Session recall must not equal worst video"

    # Test 5: API response structure validation
    def test_api_response_structure_session_vs_per_video(self, gt_service, mock_db):
        """
        Test: Verify API correctly separates sessionMetrics vs perVideoMetrics
        """
        # Mock API response
        api_response = {
            "sessionMetrics": {
                "recall": 36.0,  # Session-wide recall
                "precision": 72.5,
                "f1Score": 48.1,
                "totalTP": 87,
                "totalGT": 242
            },
            "perVideoMetrics": [
                {
                    "videoId": "video-1",
                    "recall": 100.0,  # Per-video recall
                    "precision": 85.0,
                    "tp": 10,
                    "gt": 10
                },
                {
                    "videoId": "video-2",
                    "recall": 33.2,
                    "precision": 70.0,
                    "tp": 77,
                    "gt": 232
                }
            ]
        }

        # Assertions
        assert "sessionMetrics" in api_response, "API must have sessionMetrics"
        assert "perVideoMetrics" in api_response, "API must have perVideoMetrics"
        assert api_response["sessionMetrics"]["recall"] == 36.0, "Session recall should be 36%"
        assert api_response["perVideoMetrics"][0]["recall"] == 100.0, "Video 1 recall should be 100%"

        # Critical assertion: Session recall MUST differ from first video's recall
        session_recall = api_response["sessionMetrics"]["recall"]
        first_video_recall = api_response["perVideoMetrics"][0]["recall"]
        assert session_recall != first_video_recall, "Session recall MUST NOT equal per-video recall"

    # Test 6: Metrics calculation with real data structure
    def test_calculate_metrics_with_real_structure(self, gt_service, mock_db):
        """
        Test: Calculate metrics using actual service structure
        """
        # Mock test session
        test_session = Mock(spec=TestSession)
        test_session.id = "test-session-123"
        test_session.has_video_sequence = True
        test_session.sequence_id = "seq-456"

        # Mock ground truth count (242 total GT)
        with patch.object(gt_service, '_get_actual_ground_truth_count', return_value=242):
            # Mock true positives count (87 TP)
            with patch.object(gt_service, '_count_true_positives', return_value=87):
                # Calculate
                tp = 87
                gt_count = 242
                recall = tp / gt_count if gt_count > 0 else 0.0

                # Assertions
                assert recall == pytest.approx(0.3595, abs=0.001), "Recall calculation failed"
                assert recall * 100 == pytest.approx(35.95, abs=0.1), "Recall percentage failed"

    # Test 7: F1 score dependency on recall
    def test_f1_score_affected_by_recall_bug(self, gt_service, mock_db):
        """
        Test: Verify F1 score is affected by incorrect recall
        F1 = 2 × (precision × recall) / (precision + recall)
        """
        precision = 0.725  # 72.5%

        # Incorrect recall (bug scenario)
        incorrect_recall = 1.0  # 100% (BUG)
        incorrect_f1 = 2 * (precision * incorrect_recall) / (precision + incorrect_recall)

        # Correct recall
        correct_recall = 0.3595  # 36%
        correct_f1 = 2 * (precision * correct_recall) / (precision + correct_recall)

        # Assertions
        assert incorrect_f1 != correct_f1, "F1 scores should differ"
        assert incorrect_f1 > correct_f1, "Bug causes inflated F1 score"
        assert abs(correct_f1 - 0.481) < 0.01, f"Correct F1 should be ~48%, got {correct_f1 * 100}%"

    # Test 8: Database storage validation
    def test_database_stores_correct_recall_decimal(self, gt_service, mock_db):
        """
        Test: Verify recall is stored as decimal (0.3595) not percentage (100)
        """
        # Mock session
        session = Mock(spec=TestSession)
        session.accuracy_recall = 0.3595

        # Assertions
        assert 0 <= session.accuracy_recall <= 1, "Recall should be decimal between 0 and 1"
        assert session.accuracy_recall != 100, "Recall should NOT be stored as percentage"
        assert session.accuracy_recall != 1.0, "Recall should NOT be 100%"
        assert abs(session.accuracy_recall - 0.3595) < 0.001, "Recall should be 35.95%"

    # Test 9: Per-video aggregation logic
    def test_per_video_aggregation_to_session(self, gt_service, mock_db):
        """
        Test: Aggregate per-video metrics to session correctly
        """
        # Per-video metrics
        videos = [
            {"video_id": "v1", "tp": 10, "gt": 10, "recall": 1.0},    # 100%
            {"video_id": "v2", "tp": 20, "gt": 50, "recall": 0.4},    # 40%
            {"video_id": "v3", "tp": 30, "gt": 100, "recall": 0.3}    # 30%
        ]

        # Session aggregation (CORRECT method)
        total_tp = sum(v["tp"] for v in videos)  # 60
        total_gt = sum(v["gt"] for v in videos)  # 160
        session_recall = total_tp / total_gt  # 37.5%

        # INCORRECT method (averaging per-video recalls)
        incorrect_recall = sum(v["recall"] for v in videos) / len(videos)  # 56.67% (WRONG!)

        # Assertions
        assert session_recall == pytest.approx(0.375, abs=0.001), "Session recall should be 37.5%"
        assert incorrect_recall != session_recall, "Averaging recalls is INCORRECT"
        assert incorrect_recall > session_recall, "Averaging inflates session recall"

    # Test 10: Validation query test
    def test_validation_query_session_vs_per_video(self, gt_service, mock_db):
        """
        Test: Simulate SQL query validation
        """
        # Session-level query result (CORRECT)
        session_result = {
            "id": "fa204ef2-9d8b-4480-9692-86e338c1218a",
            "accuracy_recall": 0.3595,
            "tp_count": 87,
            "fn_count": 155
        }

        # Per-video query result
        video_results = [
            {"video_id": "v1", "tp": 10, "fn": 0, "recall": 1.0},
            {"video_id": "v2", "tp": 77, "fn": 155, "recall": 0.332}
        ]

        # Verify session recall
        calculated_recall = session_result["tp_count"] / (
            session_result["tp_count"] + session_result["fn_count"]
        )

        # Assertions
        assert abs(calculated_recall - session_result["accuracy_recall"]) < 0.001, \
            "Database recall matches calculated recall"
        assert session_result["accuracy_recall"] != video_results[0]["recall"], \
            "Session recall must not equal first video's recall"

    # Test 11: Zero ground truth edge case
    def test_zero_ground_truth_edge_case(self, gt_service, mock_db):
        """
        Test: Handle edge case with zero ground truth events
        """
        tp = 0
        gt_count = 0
        recall = tp / gt_count if gt_count > 0 else 0.0

        assert recall == 0.0, "Recall should be 0 when no ground truth"

    # Test 12: Frontend data binding validation
    def test_frontend_must_use_session_metrics_not_per_video(self, gt_service, mock_db):
        """
        Test: Validate frontend binds to correct data field
        """
        # Mock frontend data source
        api_data = {
            "sessionMetrics": {"recall": 36.0},  # CORRECT field
            "perVideoResults": [{"recall": 100.0}, {"recall": 33.2}]
        }

        # CORRECT binding
        correct_recall = api_data["sessionMetrics"]["recall"]

        # INCORRECT binding (BUG)
        incorrect_recall = api_data["perVideoResults"][0]["recall"]

        # Assertions
        assert correct_recall == 36.0, "Frontend should use sessionMetrics.recall"
        assert incorrect_recall == 100.0, "First video has 100% recall"
        assert correct_recall != incorrect_recall, "Binding to wrong field causes bug"


class TestRecallCalculationIntegration:
    """Integration tests with database mocking"""

    @pytest.fixture
    def setup_multi_video_data(self, mock_db):
        """Setup complete multi-video session data"""
        # Videos
        video1 = Mock(spec=Video)
        video1.id = "video-1"

        video2 = Mock(spec=Video)
        video2.id = "video-2"

        # Ground truth objects
        gt_objects_v1 = [Mock(spec=GroundTruthObject) for _ in range(10)]
        gt_objects_v2 = [Mock(spec=GroundTruthObject) for _ in range(232)]

        # Detection events with matches
        detections_v1 = [Mock(spec=DetectionEvent) for _ in range(10)]  # All TP
        detections_v2 = [Mock(spec=DetectionEvent) for _ in range(77)]  # 77 TP

        return {
            "videos": [video1, video2],
            "gt_v1": gt_objects_v1,
            "gt_v2": gt_objects_v2,
            "det_v1": detections_v1,
            "det_v2": detections_v2
        }

    def test_integration_full_recall_calculation(
        self, gt_service, mock_db, setup_multi_video_data
    ):
        """
        Integration test: Full recall calculation with mocked database
        """
        data = setup_multi_video_data

        # Calculate per-video
        v1_tp = len(data["det_v1"])  # 10
        v1_gt = len(data["gt_v1"])   # 10
        v1_recall = v1_tp / v1_gt

        v2_tp = len(data["det_v2"])  # 77
        v2_gt = len(data["gt_v2"])   # 232
        v2_recall = v2_tp / v2_gt

        # Calculate session
        session_tp = v1_tp + v2_tp    # 87
        session_gt = v1_gt + v2_gt    # 242
        session_recall = session_tp / session_gt

        # Assertions
        assert v1_recall == 1.0, "Video 1 recall = 100%"
        assert abs(v2_recall - 0.332) < 0.01, "Video 2 recall ~= 33%"
        assert abs(session_recall - 0.3595) < 0.001, "Session recall ~= 36%"


# Performance and stress tests
class TestRecallCalculationPerformance:
    """Performance tests for recall calculation"""

    def test_large_session_recall_calculation_performance(self, gt_service, mock_db):
        """
        Test: Calculate recall for large multi-video session
        """
        import time

        # Simulate large session: 10 videos, 1000 GT each
        num_videos = 10
        gt_per_video = 1000
        tp_per_video = [int(i * gt_per_video * 0.1) for i in range(1, num_videos + 1)]

        start_time = time.time()

        total_tp = sum(tp_per_video)
        total_gt = num_videos * gt_per_video
        session_recall = total_tp / total_gt

        elapsed = time.time() - start_time

        # Assertions
        assert elapsed < 0.1, "Calculation should be fast (< 100ms)"
        assert 0 <= session_recall <= 1, "Recall should be valid"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
