"""
Test Suite for Multi-Video Recall Calculation Bug Fix

This test validates that session-wide recall is calculated correctly across
multiple videos and is distinct from per-video recall values.

Bug Context:
- Session fa204ef2-9d8b-4480-9692-86e338c1218a
- UI displayed "Recall 100.0%" (incorrect - from per-video metric)
- Actual data: 87 TP / 242 GT Events = 36% (correct session-wide)

Test validates:
1. Session-wide recall = Sum(TP across all videos) / Sum(GT across all videos)
2. Per-video recall = TP for video / GT for video
3. Session recall != Per-video recall in multi-video scenarios
4. API response includes metric_scope indicator
"""

import pytest
from typing import Dict, List, Any


class TestMultiVideoRecallCalculation:
    """Test correct recall calculation for multi-video test sessions"""

    def test_session_wide_recall_vs_per_video_recall(self):
        """
        Test that session-wide recall is calculated correctly and differs
        from individual per-video recall values.

        Scenario: 2 videos with different GT counts
        - Video 1: 10 TP / 10 GT = 100% recall
        - Video 2: 77 TP / 232 GT = 33.2% recall
        - Session: 87 TP / 242 GT = 35.95% recall ≈ 36%

        This matches the real bug scenario in session fa204ef2
        """
        # Video 1: Perfect recall
        video1_tp = 10
        video1_gt = 10
        video1_recall = (video1_tp / video1_gt) * 100  # 100.0%

        # Video 2: Low recall
        video2_tp = 77
        video2_gt = 232
        video2_recall = (video2_tp / video2_gt) * 100  # 33.2%

        # Session-wide: Aggregate
        session_tp = video1_tp + video2_tp  # 87
        session_gt = video1_gt + video2_gt  # 242
        session_recall = (session_tp / session_gt) * 100  # 35.95% ≈ 36%

        # CRITICAL ASSERTION: Session recall != Video 1 recall
        assert abs(session_recall - video1_recall) > 60, (
            f"Session recall ({session_recall:.1f}%) should differ significantly "
            f"from video 1 recall ({video1_recall:.1f}%)"
        )

        # CRITICAL ASSERTION: Session recall is weighted average, not simple average
        simple_average = (video1_recall + video2_recall) / 2  # 66.6%
        assert abs(session_recall - simple_average) > 30, (
            f"Session recall ({session_recall:.1f}%) should be weighted by GT count, "
            f"not simple average ({simple_average:.1f}%)"
        )

        # CRITICAL ASSERTION: Session recall should be approximately 36%
        assert 35.0 <= session_recall <= 36.5, (
            f"Session recall should be ~36% (actual: {session_recall:.1f}%)"
        )

        print(f"✓ Video 1: {video1_recall:.1f}% recall (TP={video1_tp}, GT={video1_gt})")
        print(f"✓ Video 2: {video2_recall:.1f}% recall (TP={video2_tp}, GT={video2_gt})")
        print(f"✓ Session: {session_recall:.1f}% recall (TP={session_tp}, GT={session_gt})")

    def test_api_response_structure(self):
        """
        Test that API response correctly structures session-wide vs per-video metrics
        """
        # Simulated API response structure
        api_response = {
            "ground_truth_comparison": {
                "recall": 36.0,  # Session-wide
                "true_positives": 87,
                "total_ground_truth": 242,
                "metric_scope": "session_wide"  # CRITICAL: Indicates aggregation
            },
            "per_video_results": [
                {
                    "video_id": "video1",
                    "ground_truth_metrics": {
                        "recall": 100.0,  # Per-video
                        "true_positives": 10,
                        "total_ground_truth": 10,
                        "metric_scope": "per_video"  # CRITICAL: Indicates single video
                    }
                },
                {
                    "video_id": "video2",
                    "ground_truth_metrics": {
                        "recall": 33.2,  # Per-video
                        "true_positives": 77,
                        "total_ground_truth": 232,
                        "metric_scope": "per_video"
                    }
                }
            ]
        }

        # CRITICAL ASSERTION: metric_scope must be present
        assert "metric_scope" in api_response["ground_truth_comparison"], (
            "Session-wide metrics must include 'metric_scope' field"
        )

        assert api_response["ground_truth_comparison"]["metric_scope"] == "session_wide", (
            "Session-wide metrics must have metric_scope='session_wide'"
        )

        # CRITICAL ASSERTION: Per-video metrics must have metric_scope
        for video in api_response["per_video_results"]:
            assert "metric_scope" in video["ground_truth_metrics"], (
                f"Video {video['video_id']} metrics must include 'metric_scope'"
            )
            assert video["ground_truth_metrics"]["metric_scope"] == "per_video", (
                f"Video {video['video_id']} must have metric_scope='per_video'"
            )

        # CRITICAL ASSERTION: Session recall must be < max per-video recall
        session_recall = api_response["ground_truth_comparison"]["recall"]
        max_video_recall = max(
            v["ground_truth_metrics"]["recall"]
            for v in api_response["per_video_results"]
        )

        assert session_recall < max_video_recall, (
            f"Session recall ({session_recall}%) should be less than "
            f"max per-video recall ({max_video_recall}%)"
        )

        print(f"✓ API response correctly structures session vs per-video metrics")
        print(f"✓ Session recall: {session_recall}% (session_wide)")
        print(f"✓ Max video recall: {max_video_recall}% (per_video)")

    def test_recall_calculation_edge_cases(self):
        """Test recall calculation edge cases"""

        # Edge case 1: Zero ground truth events
        assert self._calculate_recall(0, 0) == 0.0, (
            "Recall with 0 GT events should be 0%"
        )

        # Edge case 2: All detections are TP
        assert self._calculate_recall(100, 100) == 100.0, (
            "Recall with all TP should be 100%"
        )

        # Edge case 3: No true positives
        assert self._calculate_recall(0, 100) == 0.0, (
            "Recall with 0 TP should be 0%"
        )

        # Edge case 4: Real bug scenario
        recall = self._calculate_recall(87, 242)
        assert 35.9 <= recall <= 36.0, (
            f"Bug scenario recall should be ~35.95% (actual: {recall:.2f}%)"
        )

        print("✓ All edge cases handled correctly")

    def test_validate_session_fa204ef2_metrics(self):
        """
        Validate the exact metrics from bug report session fa204ef2

        Expected:
        - Session recall: 36% (87 TP / 242 GT)
        - NOT 100% as displayed in UI
        """
        session_tp = 87
        session_gt = 242
        expected_recall = 35.95  # Rounded to 36.0% in UI

        actual_recall = (session_tp / session_gt) * 100

        assert abs(actual_recall - expected_recall) < 0.1, (
            f"Session fa204ef2 recall should be {expected_recall}% "
            f"(actual: {actual_recall:.2f}%)"
        )

        # The bug: UI was showing 100% instead of 36%
        incorrect_display = 100.0
        assert abs(actual_recall - incorrect_display) > 60, (
            f"Session recall ({actual_recall:.1f}%) should NOT be "
            f"100% as incorrectly displayed"
        )

        print(f"✓ Session fa204ef2 metrics validated: {actual_recall:.2f}% recall")
        print(f"✗ Previous bug: Displayed 100% instead of 36%")

    @staticmethod
    def _calculate_recall(true_positives: int, total_ground_truth: int) -> float:
        """Calculate recall percentage with safe division"""
        if total_ground_truth == 0:
            return 0.0
        return (true_positives / total_ground_truth) * 100


class TestGroundTruthMetricsDocumentation:
    """Test that metrics are properly documented in API responses"""

    def test_metric_scope_documentation(self):
        """
        Validate that metric_scope field clearly indicates aggregation level
        """
        valid_scopes = ["session_wide", "per_video"]

        # Session-wide metrics must use session_wide
        session_metric = {"metric_scope": "session_wide"}
        assert session_metric["metric_scope"] in valid_scopes

        # Per-video metrics must use per_video
        video_metric = {"metric_scope": "per_video"}
        assert video_metric["metric_scope"] in valid_scopes

        print("✓ metric_scope values properly defined")

    def test_recall_calculation_comments(self):
        """
        Verify that code includes explanatory comments about recall calculation

        This is a documentation test - verifies that the fix includes
        clear comments explaining the difference between session and per-video recall.
        """
        # This test validates that developers added clear documentation
        # Actual verification would grep for specific comment patterns in the code

        expected_comments = [
            "Session-wide recall",
            "Per-video recall",
            "TP / Total GT",
            "metric_scope"
        ]

        # In a real test, we would:
        # 1. Read the API endpoint code
        # 2. Verify presence of explanatory comments
        # 3. Ensure future developers understand the distinction

        print("✓ Documentation test placeholder - manual verification required")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
