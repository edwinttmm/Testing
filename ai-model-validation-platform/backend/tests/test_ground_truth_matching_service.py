"""
Unit tests for Ground Truth Matching Service

This test suite verifies the comprehensive ground truth matching functionality
including temporal matching algorithms, detection classification, and metrics calculation.
"""

import pytest
import unittest
from unittest.mock import Mock, MagicMock, patch, create_autospec
from datetime import datetime
from typing import List

from services.ground_truth_matching_service import (
    GroundTruthMatchingService, 
    MatchResult, 
    SessionMetrics
)
from models import (
    TestSession, DetectionEvent, GroundTruthObject, DetectionComparison,
    PerformanceMetrics, ValidationResult as ValidationResultEnum
)
from schemas_annotation import VRUTypeEnum


class TestGroundTruthMatchingService(unittest.TestCase):
    """Test cases for GroundTruthMatchingService"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = GroundTruthMatchingService(default_tolerance_ms=100)
        self.session_id = "test-session-123"
        self.video_id = "test-video-456"
        
        # Mock database session
        self.mock_db = Mock()
        
        # Create sample test session
        self.test_session = TestSession(
            id=self.session_id,
            video_id=self.video_id,
            tolerance_ms=100,
            name="Test Session"
        )
        
        # Create sample ground truth objects (24 objects from requirements)
        self.ground_truth_objects = self._create_sample_ground_truth()
        
        # Create sample detection events
        self.detection_events = self._create_sample_detections()
    
    def _create_sample_ground_truth(self) -> List[GroundTruthObject]:
        """Create sample ground truth objects matching the requirements"""
        timestamps = [
            0.208, 0.417, 0.625, 0.833, 1.042, 1.250, 1.458, 1.667,
            1.875, 2.083, 2.292, 2.500, 2.708, 2.917, 3.125, 3.333,
            3.542, 3.750, 3.958, 4.167, 4.375, 4.583, 4.792, 5.000
        ]
        
        ground_truth = []
        for i, timestamp in enumerate(timestamps):
            gt_obj = GroundTruthObject(
                id=f"gt-{i+1}",
                video_id=self.video_id,
                timestamp=timestamp,
                class_label=VRUTypeEnum.PEDESTRIAN,
                confidence=0.95,
                frame_number=int(timestamp * 30)  # Assuming 30 FPS
            )
            ground_truth.append(gt_obj)
        
        return ground_truth
    
    def _create_sample_detections(self) -> List[DetectionEvent]:
        """Create sample detection events with realistic latencies"""
        # Simulate 22 detections with varying latencies
        detection_data = [
            (0.231, 0.89),  # +23ms latency from GT at 0.208s
            (0.442, 0.92),  # +25ms latency from GT at 0.417s
            (0.648, 0.87),  # +23ms latency from GT at 0.625s
            (0.856, 0.94),  # +23ms latency from GT at 0.833s
            (1.065, 0.91),  # +23ms latency from GT at 1.042s (example from requirements)
            (1.273, 0.88),  # +23ms latency from GT at 1.250s
            (1.481, 0.93),  # +23ms latency from GT at 1.458s
            (1.690, 0.89),  # +23ms latency from GT at 1.667s
            (1.898, 0.85),  # +23ms latency from GT at 1.875s
            (2.106, 0.90),  # +23ms latency from GT at 2.083s
            (2.315, 0.92),  # +23ms latency from GT at 2.292s
            (2.523, 0.87),  # +23ms latency from GT at 2.500s
            (2.731, 0.89),  # +23ms latency from GT at 2.708s
            (2.940, 0.91),  # +23ms latency from GT at 2.917s
            (3.148, 0.88),  # +23ms latency from GT at 3.125s
            (3.356, 0.90),  # +23ms latency from GT at 3.333s
            (3.565, 0.93),  # +23ms latency from GT at 3.542s
            (3.773, 0.86),  # +23ms latency from GT at 3.750s
            (5.567, 0.84),  # False positive - no nearby GT
            (6.123, 0.82),  # False positive - no nearby GT
            (7.890, 0.88),  # False positive - no nearby GT
            (8.456, 0.90),  # False positive - no nearby GT
        ]
        
        detection_events = []
        for i, (timestamp, confidence) in enumerate(detection_data):
            detection = DetectionEvent(
                id=f"detection-{i+1}",
                test_session_id=self.session_id,
                timestamp=timestamp,
                confidence=confidence,
                class_label=VRUTypeEnum.PEDESTRIAN,
                validation_result=ValidationResultEnum.PENDING,
                frame_number=int(timestamp * 30)
            )
            detection_events.append(detection)
        
        return detection_events
    
    @patch('services.ground_truth_matching_service.SessionLocal')
    def test_match_detections_basic_functionality(self, mock_session_local):
        """Test basic matching functionality"""
        # Setup mock database
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = self.test_session
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = [
            self.detection_events,  # detection events query
            self.ground_truth_objects  # ground truth objects query
        ]
        mock_db.query.return_value.filter.return_value.count.return_value = 0  # no existing comparisons
        
        # Execute matching
        result = self.service.match_detections_to_ground_truth(self.session_id)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SessionMetrics)
        
        # Expected results based on sample data:
        # 18 TP (matched detections), 4 FP (unmatched detections), 6 FN (unmatched GT)
        self.assertEqual(result.true_positives, 18)
        self.assertEqual(result.false_positives, 4)
        self.assertEqual(result.false_negatives, 6)
        self.assertEqual(result.total_ground_truth, 24)
        self.assertEqual(result.total_detections, 22)
        
        # Verify database operations were called
        mock_db.add.assert_called()
        mock_db.commit.assert_called()
    
    def test_perform_temporal_matching_algorithm(self):
        """Test the core temporal matching algorithm"""
        tolerance_ms = 100
        
        # Execute matching algorithm
        match_results = self.service._perform_temporal_matching(
            self.detection_events, self.ground_truth_objects, tolerance_ms
        )
        
        # Verify match results
        self.assertEqual(len(match_results), 28)  # 18 TP + 4 FP + 6 FN = 28
        
        # Count match types
        tp_count = sum(1 for mr in match_results if mr.match_type == 'TP')
        fp_count = sum(1 for mr in match_results if mr.match_type == 'FP')
        fn_count = sum(1 for mr in match_results if mr.match_type == 'FN')
        
        self.assertEqual(tp_count, 18)
        self.assertEqual(fp_count, 4)
        self.assertEqual(fn_count, 6)
        
        # Verify specific match - GT at 1.042s should match detection at 1.065s
        gt_1042_matches = [mr for mr in match_results 
                          if mr.ground_truth_id == "gt-5" and mr.match_type == 'TP']
        self.assertEqual(len(gt_1042_matches), 1)
        
        match = gt_1042_matches[0]
        self.assertAlmostEqual(match.temporal_offset, 23.0, delta=1.0)  # +23ms latency
    
    def test_temporal_iou_calculation(self):
        """Test temporal IoU score calculation"""
        tolerance_seconds = 0.1  # 100ms
        
        # Perfect match (0 difference)
        iou_perfect = self.service._calculate_temporal_iou(1.0, 1.0, tolerance_seconds)
        self.assertEqual(iou_perfect, 1.0)
        
        # Half tolerance difference
        iou_half = self.service._calculate_temporal_iou(1.0, 1.05, tolerance_seconds)
        self.assertAlmostEqual(iou_half, 0.75, delta=0.1)
        
        # At tolerance boundary
        iou_boundary = self.service._calculate_temporal_iou(1.0, 1.1, tolerance_seconds)
        self.assertAlmostEqual(iou_boundary, 0.5, delta=0.1)
        
        # Outside tolerance
        iou_outside = self.service._calculate_temporal_iou(1.0, 1.2, tolerance_seconds)
        self.assertEqual(iou_outside, 0.0)
    
    def test_metrics_calculation(self):
        """Test metrics calculation from match results"""
        # Create sample match results
        match_results = [
            MatchResult("gt-1", "det-1", "TP", 23.0, 0.89, 0.9, 23.0),
            MatchResult("gt-2", "det-2", "TP", 25.0, 0.92, 0.85, 25.0),
            MatchResult("gt-3", "det-3", "TP", 21.0, 0.87, 0.88, 21.0),
            MatchResult("gt-4", None, "FN", 0.0, None, 0.0, None),
            MatchResult(None, "det-4", "FP", 0.0, 0.84, 0.0, None),
        ]
        
        metrics = self.service._calculate_metrics_from_results(match_results)
        
        # Verify basic counts
        self.assertEqual(metrics.true_positives, 3)
        self.assertEqual(metrics.false_positives, 1)
        self.assertEqual(metrics.false_negatives, 1)
        
        # Verify calculated metrics
        expected_precision = 3 / (3 + 1)  # 0.75
        expected_recall = 3 / (3 + 1)     # 0.75
        expected_f1 = 2 * (0.75 * 0.75) / (0.75 + 0.75)  # 0.75
        
        self.assertAlmostEqual(metrics.precision, expected_precision, places=3)
        self.assertAlmostEqual(metrics.recall, expected_recall, places=3)
        self.assertAlmostEqual(metrics.f1_score, expected_f1, places=3)
        
        # Verify latency metrics
        expected_mean_latency = (23.0 + 25.0 + 21.0) / 3  # 23.0
        self.assertAlmostEqual(metrics.mean_latency_ms, expected_mean_latency, places=1)
    
    def test_tolerance_window_variations(self):
        """Test matching with different tolerance windows"""
        # Test with strict tolerance (50ms)
        match_results_strict = self.service._perform_temporal_matching(
            self.detection_events, self.ground_truth_objects, 50
        )
        
        # Test with relaxed tolerance (200ms)
        match_results_relaxed = self.service._perform_temporal_matching(
            self.detection_events, self.ground_truth_objects, 200
        )
        
        # Count true positives for each
        tp_strict = sum(1 for mr in match_results_strict if mr.match_type == 'TP')
        tp_relaxed = sum(1 for mr in match_results_relaxed if mr.match_type == 'TP')
        
        # Relaxed tolerance should have same or more matches
        self.assertGreaterEqual(tp_relaxed, tp_strict)
        
        # With our sample data (23ms average latency), strict tolerance should match most
        self.assertGreater(tp_strict, 15)  # Most detections within 50ms
    
    def test_empty_ground_truth_handling(self):
        """Test handling when no ground truth objects exist"""
        empty_gt = []
        
        match_results = self.service._perform_temporal_matching(
            self.detection_events, empty_gt, 100
        )
        
        # All detections should be false positives
        fp_count = sum(1 for mr in match_results if mr.match_type == 'FP')
        self.assertEqual(fp_count, len(self.detection_events))
        
        # No true positives or false negatives
        tp_count = sum(1 for mr in match_results if mr.match_type == 'TP')
        fn_count = sum(1 for mr in match_results if mr.match_type == 'FN')
        self.assertEqual(tp_count, 0)
        self.assertEqual(fn_count, 0)
    
    def test_empty_detections_handling(self):
        """Test handling when no detection events exist"""
        empty_detections = []
        
        match_results = self.service._perform_temporal_matching(
            empty_detections, self.ground_truth_objects, 100
        )
        
        # All ground truth should be false negatives
        fn_count = sum(1 for mr in match_results if mr.match_type == 'FN')
        self.assertEqual(fn_count, len(self.ground_truth_objects))
        
        # No true positives or false positives
        tp_count = sum(1 for mr in match_results if mr.match_type == 'TP')
        fp_count = sum(1 for mr in match_results if mr.match_type == 'FP')
        self.assertEqual(tp_count, 0)
        self.assertEqual(fp_count, 0)
    
    @patch('services.ground_truth_matching_service.SessionLocal')
    def test_detailed_analysis_generation(self, mock_session_local):
        """Test detailed analysis generation"""
        # Setup mock database with sample comparisons
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        # Mock comparison results
        mock_comparisons = [
            Mock(
                match_type='TP', temporal_offset=23.0, iou_score=0.9,
                ground_truth_id='gt-1', detection_event_id='det-1'
            ),
            Mock(
                match_type='TP', temporal_offset=25.0, iou_score=0.85,
                ground_truth_id='gt-2', detection_event_id='det-2'
            ),
            Mock(
                match_type='FP', temporal_offset=0.0, iou_score=0.0,
                ground_truth_id=None, detection_event_id='det-3'
            ),
            Mock(
                match_type='FN', temporal_offset=0.0, iou_score=0.0,
                ground_truth_id='gt-3', detection_event_id=None
            ),
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = mock_comparisons
        
        # Execute analysis
        analysis = self.service.get_detailed_analysis(self.session_id)
        
        # Verify analysis structure
        self.assertIsNotNone(analysis)
        self.assertIn('summary', analysis)
        self.assertIn('temporal_analysis', analysis)
        self.assertIn('quality_analysis', analysis)
        self.assertIn('recommendations', analysis)
        
        # Verify summary counts
        self.assertEqual(analysis['summary']['true_positives'], 2)
        self.assertEqual(analysis['summary']['false_positives'], 1)
        self.assertEqual(analysis['summary']['false_negatives'], 1)
        
        # Verify temporal analysis
        self.assertAlmostEqual(analysis['temporal_analysis']['mean_offset_ms'], 24.0, delta=1.0)
    
    def test_recommendations_generation(self):
        """Test recommendation generation logic"""
        # Create mock comparisons for different scenarios
        
        # Scenario 1: Low recall (many false negatives)
        low_recall_comparisons = [
            Mock(match_type='TP'), Mock(match_type='TP'),  # 2 TP
            Mock(match_type='FN'), Mock(match_type='FN'),  # 2 FN
            Mock(match_type='FN'), Mock(match_type='FN'),  # 2 more FN
            Mock(match_type='FP')  # 1 FP
        ]
        
        recommendations = self.service._generate_recommendations(low_recall_comparisons)
        self.assertTrue(any('sensitivity' in rec.lower() for rec in recommendations))
        
        # Scenario 2: Low precision (many false positives)
        low_precision_comparisons = [
            Mock(match_type='TP'), Mock(match_type='TP'),  # 2 TP
            Mock(match_type='FP'), Mock(match_type='FP'),  # 2 FP
            Mock(match_type='FP'), Mock(match_type='FP'),  # 2 more FP
            Mock(match_type='FN')  # 1 FN
        ]
        
        recommendations = self.service._generate_recommendations(low_precision_comparisons)
        self.assertTrue(any('specificity' in rec.lower() for rec in recommendations))
    
    def test_error_handling(self):
        """Test error handling in various scenarios"""
        # Test with invalid session ID
        with patch('services.ground_truth_matching_service.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None
            
            result = self.service.match_detections_to_ground_truth("invalid-session")
            self.assertIsNone(result)
        
        # Test with database exception
        with patch('services.ground_truth_matching_service.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mock_db.query.side_effect = Exception("Database error")
            
            result = self.service.match_detections_to_ground_truth(self.session_id)
            self.assertIsNone(result)
    
    def test_force_rematch_functionality(self):
        """Test force rematch functionality"""
        with patch('services.ground_truth_matching_service.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            
            # Setup existing comparisons
            mock_db.query.return_value.filter.return_value.first.return_value = self.test_session
            mock_db.query.return_value.filter.return_value.count.return_value = 5  # existing comparisons
            mock_db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = [
                self.detection_events,
                self.ground_truth_objects
            ]
            
            # Test with force_rematch=True
            result = self.service.match_detections_to_ground_truth(
                self.session_id, force_rematch=True
            )
            
            # Verify deletion was called for existing comparisons
            mock_db.query.return_value.filter.return_value.delete.assert_called()
            self.assertIsNotNone(result)


class TestSessionMetricsDataClass(unittest.TestCase):
    """Test SessionMetrics data class"""
    
    def test_session_metrics_creation(self):
        """Test SessionMetrics data class creation and attributes"""
        metrics = SessionMetrics(
            true_positives=18,
            false_positives=4,
            false_negatives=6,
            precision=0.818,
            recall=0.750,
            f1_score=0.783,
            accuracy=0.750,
            mean_latency_ms=23.5,
            std_latency_ms=2.1,
            max_latency_ms=28.0,
            min_latency_ms=20.0,
            within_tolerance_percentage=100.0,
            total_ground_truth=24,
            total_detections=22,
            matched_detections=18
        )
        
        self.assertEqual(metrics.true_positives, 18)
        self.assertEqual(metrics.false_positives, 4)
        self.assertEqual(metrics.false_negatives, 6)
        self.assertAlmostEqual(metrics.precision, 0.818, places=3)
        self.assertAlmostEqual(metrics.recall, 0.750, places=3)
        self.assertAlmostEqual(metrics.f1_score, 0.783, places=3)


class TestMatchResultDataClass(unittest.TestCase):
    """Test MatchResult data class"""
    
    def test_match_result_creation(self):
        """Test MatchResult data class creation"""
        # True Positive match
        tp_match = MatchResult(
            ground_truth_id="gt-1",
            detection_event_id="det-1",
            match_type="TP",
            temporal_offset=23.0,
            confidence=0.89,
            iou_score=0.9,
            latency_ms=23.0
        )
        
        self.assertEqual(tp_match.match_type, "TP")
        self.assertEqual(tp_match.temporal_offset, 23.0)
        self.assertEqual(tp_match.latency_ms, 23.0)
        
        # False Negative match
        fn_match = MatchResult(
            ground_truth_id="gt-2",
            detection_event_id=None,
            match_type="FN",
            temporal_offset=0.0,
            confidence=None,
            iou_score=0.0,
            latency_ms=None
        )
        
        self.assertEqual(fn_match.match_type, "FN")
        self.assertIsNone(fn_match.detection_event_id)
        self.assertIsNone(fn_match.latency_ms)


if __name__ == '__main__':
    # Configure logging for tests
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Run tests
    unittest.main(verbosity=2)