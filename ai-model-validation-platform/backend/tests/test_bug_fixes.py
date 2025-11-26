"""
Unit tests for bug fixes identified in the code review.

This test suite verifies that the critical bug fixes have been applied
correctly and protects against future regressions.
"""

import pytest
from datetime import datetime, timezone

# Import the services and classes to be tested
from services.timing_synchronization_calculator import TimingSynchronizationCalculator, VideoTimingMetadata
from services.latency_decomposition_service import LatencyDecompositionService
from services.ground_truth_matching_service import GroundTruthMatchingService
from services.optimal_matching_service import optimal_detection_matching

# Mock data for testing
DETECTION_METADATA = {
    'detection_algorithm': 'YOLO',
    'image_resolution': '1920x1080',
    'communication_method': 'local',
    'sync_method': 'software',
    'multi_threaded': True,
    'preprocessing_enabled': True,
    'session_id': 'test_session',
    'detection_id': 'test_detection',
}

# --- Test Suite ---

class TestBugFixes:
    """
    Test suite for verifying critical bug fixes.
    Each test corresponds to a bug identified in the code review.
    """

    def test_bug2_invalid_input_returns_error_status(self):
        """
        Bug #2: Verifies that decompose_latency returns an INVALID status
        for unrealistic input latencies instead of clamping values.
        """
        # Arrange
        service = LatencyDecompositionService()
        
        # Act
        # Test with a latency value that is too high
        result = service.decompose_latency(
            session_id="test",
            detection_id="det1",
            total_latency_ms=1500.0,  # Unrealistic latency > 1000ms
            detection_metadata=DETECTION_METADATA
        )
        
        # Assert
        assert result.validation_status == "INVALID"
        assert result.is_valid is False
        assert result.unknown_overhead_ms == 1500.0
        assert result.camera_latency_ms == 0.0

    def test_bug4_quality_assessment_with_hardware_camera_thresholds(self):
        """
        Bug #4: Verifies that the quality assessment uses the corrected
        thresholds for hardware cameras.
        """
        # Arrange
        calc = TimingSynchronizationCalculator()
        
        # Act: Use values that would have failed before but should now be acceptable
        quality, _ = calc._assess_timing_quality(
            detection_latency_ms=450.0,   # Was "poor" (>100), now "acceptable" (<=500)
            startup_delay_ms=450.0,       # Was "poor" (>500), now "good" (<=500)
            timing_accuracy_ns=500_000
        )
        
        # Assert
        assert quality in ["good", "acceptable"]

    def test_bug4_quality_assessment_failure_scenario(self):
        """
        Bug #4: Verifies that the quality assessment still fails for values
        outside the new, corrected thresholds.
        """
        # Arrange
        calc = TimingSynchronizationCalculator()
        
        # Act: Use values that should fail even with the new thresholds
        quality, _ = calc._assess_timing_quality(
            detection_latency_ms=600.0,    # Fails latency > 500ms
            startup_delay_ms=1200.0,       # Fails startup > 1000ms (new acceptable max)
            timing_accuracy_ns=500_000
        )
        
        # Assert
        assert quality == "poor"
        
    def test_bug5_tolerance_window_is_100ms(self):
        """
        Bug #5: Verifies that the ground truth matching tolerance is 100ms.
        This test checks the core matching function.
        """
        # Arrange
        # gt_times, det_times, tolerance_seconds
        gt_times = [1.0]
        tolerance_seconds = 0.100  # 100ms
        
        # Act & Assert
        
        # 1. Test a match just within the tolerance (100ms diff)
        det_times_match = [1.100]
        match_result = optimal_detection_matching(gt_times, det_times_match, tolerance_seconds)
        assert len(match_result['true_positives']) == 1, "Should match at exactly 100ms difference"

        # 2. Test a match just outside the tolerance (100.1ms diff)
        det_times_no_match = [1.1001]
        no_match_result = optimal_detection_matching(gt_times, det_times_no_match, tolerance_seconds)
        assert len(no_match_result['true_positives']) == 0, "Should not match beyond 100ms difference"
        assert len(no_match_result['false_positives']) == 1
        assert len(no_match_result['false_negatives']) == 1

    def test_bug6_negative_latency_is_invalid(self):
        """
        Bug #6: Verifies that a significantly negative latency is correctly
        identified as invalid.
        """
        # Arrange
        calc = TimingSynchronizationCalculator()
        
        # Act
        is_valid = calc.validate_latency(latency_ms=-60.0, detection_id="det_negative")
        
        # Assert
        assert is_valid is False

    def test_bug6_small_negative_latency_is_valid_for_jitter(self):
        """
        Bug #6: Verifies that a small negative latency (within jitter tolerance)
        is considered valid.
        """
        # Arrange
        calc = TimingSynchronizationCalculator()
        
        # Act
        is_valid = calc.validate_latency(latency_ms=-40.0, detection_id="det_jitter")
        
        # Assert
        assert is_valid is True
