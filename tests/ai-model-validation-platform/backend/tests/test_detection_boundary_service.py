"""
Test suite for Detection Boundary Analysis Service

This test suite validates the detection boundary analysis functionality
that distinguishes missing detections from legitimate video end conditions.
"""

import pytest
from datetime import datetime
from services.detection_boundary_service import DetectionBoundaryAnalyzer

class TestDetectionBoundaryAnalyzer:
    """Test cases for the Detection Boundary Analyzer"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = DetectionBoundaryAnalyzer()
        
        # Sample detection events
        self.sample_detections = [
            {'id': 1, 'timestamp': 10.5, 'detection_time': 10.5, 'video_frame': 315},
            {'id': 2, 'timestamp': 25.2, 'detection_time': 25.2, 'video_frame': 756},
            {'id': 3, 'timestamp': 40.8, 'detection_time': 40.8, 'video_frame': 1224}
        ]
        
        # Sample ground truth events
        self.sample_ground_truth = [
            {'id': 1, 'video_frame': 300, 'frame_number': 300, 'event_type': 'detection'},
            {'id': 2, 'video_frame': 750, 'frame_number': 750, 'event_type': 'detection'},
            {'id': 3, 'video_frame': 1200, 'frame_number': 1200, 'event_type': 'detection'},
            {'id': 4, 'video_frame': 2500, 'frame_number': 2500, 'event_type': 'detection'},  # After monitoring
            {'id': 5, 'video_frame': 3000, 'frame_number': 3000, 'event_type': 'detection'}   # After monitoring
        ]
        
        # Sample video metadata
        self.sample_video_metadata = {
            'duration': 120.0,
            'duration_s': 120.0,
            'fps': 30,
            'frame_rate': 30,
            'total_frames': 3600,
            'filename': 'test_video.mp4'
        }
    
    def test_find_last_detection_time(self):
        """Test extraction of last detection timestamp"""
        last_time = self.analyzer._find_last_detection_time(self.sample_detections)
        assert last_time == 40.8
        
        # Test with empty list
        assert self.analyzer._find_last_detection_time([]) == 0.0
        
        # Test with datetime objects
        datetime_detections = [
            {'timestamp': datetime.fromisoformat('2024-01-01T10:00:10.500')},
            {'timestamp': datetime.fromisoformat('2024-01-01T10:00:25.200')}
        ]
        last_time = self.analyzer._find_last_detection_time(datetime_detections)
        assert last_time > 0  # Should convert datetime to timestamp
    
    def test_categorize_ground_truth_events(self):
        """Test categorization of ground truth events"""
        last_detection_time = 40.8
        monitoring_end_time = 42.8  # 2 second grace period
        
        categorized = self.analyzer._categorize_ground_truth_events(
            self.sample_ground_truth,
            last_detection_time,
            monitoring_end_time,
            self.sample_video_metadata
        )
        
        # Verify categorization
        assert len(categorized['during_monitoring']) == 3  # Frames 300, 750, 1200 (at ~10s, 25s, 40s)
        assert len(categorized['after_monitoring']) == 2   # Frames 2500, 3000 (at ~83s, 100s)
        
        # Verify calculated times are added
        for event in categorized['during_monitoring']:
            assert 'calculated_time' in event
            assert event['calculated_time'] <= monitoring_end_time
            
        for event in categorized['after_monitoring']:
            assert 'calculated_time' in event
            assert event['calculated_time'] > monitoring_end_time
    
    def test_match_detections_to_ground_truth(self):
        """Test matching detections to ground truth events"""
        # Set up categorized events (during monitoring only)
        categorized = {
            'during_monitoring': [
                {'id': 1, 'video_frame': 300, 'calculated_time': 10.0, 'event_type': 'detection'},
                {'id': 2, 'video_frame': 750, 'calculated_time': 25.0, 'event_type': 'detection'},
                {'id': 3, 'video_frame': 1200, 'calculated_time': 40.0, 'event_type': 'detection'},
                {'id': 4, 'video_frame': 1800, 'calculated_time': 60.0, 'event_type': 'detection'}  # No matching detection
            ],
            'after_monitoring': [],
            'unmatched_during': [],
            'expected_after': []
        }
        
        result = self.analyzer._match_detections_to_ground_truth(
            self.sample_detections,
            categorized,
            self.sample_video_metadata
        )
        
        # Should have 1 unmatched ground truth event (the one at 60s)
        assert len(result['unmatched_during']) == 1
        assert result['unmatched_during'][0]['calculated_time'] == 60.0
    
    def test_generate_boundary_analysis(self):
        """Test boundary analysis generation"""
        categorized = {
            'during_monitoring': [{'id': i} for i in range(4)],  # 4 GT events during monitoring
            'after_monitoring': [{'id': i} for i in range(2)],   # 2 GT events after monitoring
            'unmatched_during': [{'id': 1}],  # 1 missing detection
            'expected_after': [{'id': i} for i in range(2)]     # 2 expected after
        }
        
        analysis = self.analyzer._generate_boundary_analysis(
            self.sample_detections,  # 3 detections
            categorized,
            last_detection_time=40.8,
            video_duration=120.0
        )
        
        # Verify analysis components
        assert analysis['total_detection_events'] == 3
        assert analysis['total_gt_events'] == 6
        assert analysis['missing_detection_count'] == 1
        assert analysis['post_video_gt_count'] == 2
        assert analysis['detection_coverage_percent'] == pytest.approx(34.0, rel=1e-2)  # 40.8/120 * 100
        assert analysis['recommended_status'] == 'insufficient_coverage'  # < 50%
    
    def test_full_boundary_analysis(self):
        """Test complete boundary analysis workflow"""
        result = self.analyzer.analyze_detection_boundaries(
            detection_events=self.sample_detections,
            ground_truth_events=self.sample_ground_truth,
            video_metadata=self.sample_video_metadata
        )
        
        # Verify structure
        assert 'last_detection_time' in result
        assert 'video_duration' in result
        assert 'monitoring_end_time' in result
        assert 'categorized_events' in result
        assert 'boundary_analysis' in result
        
        # Verify values
        assert result['last_detection_time'] == 40.8
        assert result['video_duration'] == 120.0
        assert result['monitoring_end_time'] > 40.8  # Should have grace period
        
        # Verify categorized events structure
        categorized = result['categorized_events']
        assert 'during_monitoring' in categorized
        assert 'after_monitoring' in categorized
        assert 'unmatched_during' in categorized
        assert 'expected_after' in categorized
        
        # Verify boundary analysis
        analysis = result['boundary_analysis']
        assert 'detection_coverage_percent' in analysis
        assert 'missing_detection_count' in analysis
        assert 'recommended_status' in analysis
        assert 'monitoring_completeness' in analysis
    
    def test_edge_cases(self):
        """Test edge cases and error conditions"""
        
        # Test with no detection events
        result = self.analyzer.analyze_detection_boundaries(
            detection_events=[],
            ground_truth_events=self.sample_ground_truth,
            video_metadata=self.sample_video_metadata
        )
        assert result['last_detection_time'] == 0.0
        assert result['boundary_analysis']['total_detection_events'] == 0
        
        # Test with no ground truth events
        result = self.analyzer.analyze_detection_boundaries(
            detection_events=self.sample_detections,
            ground_truth_events=[],
            video_metadata=self.sample_video_metadata
        )
        assert result['boundary_analysis']['total_gt_events'] == 0
        
        # Test with zero video duration
        zero_duration_metadata = {**self.sample_video_metadata, 'duration': 0, 'duration_s': 0}
        result = self.analyzer.analyze_detection_boundaries(
            detection_events=self.sample_detections,
            ground_truth_events=self.sample_ground_truth,
            video_metadata=zero_duration_metadata
        )
        assert result['boundary_analysis']['detection_coverage_percent'] == 0.0
    
    def test_coverage_assessment(self):
        """Test coverage assessment logic"""
        
        # Test excellent coverage (95%+, no missing)
        excellent_analysis = {
            'boundary_analysis': {
                'detection_coverage_percent': 98.5,
                'missing_detection_count': 0
            }
        }
        from routers.hil_testing import _assess_coverage
        assert _assess_coverage(excellent_analysis) == "EXCELLENT"
        
        # Test good coverage (80%+, <=2 missing)
        good_analysis = {
            'boundary_analysis': {
                'detection_coverage_percent': 85.0,
                'missing_detection_count': 1
            }
        }
        assert _assess_coverage(good_analysis) == "GOOD"
        
        # Test needs improvement
        poor_analysis = {
            'boundary_analysis': {
                'detection_coverage_percent': 45.0,
                'missing_detection_count': 8
            }
        }
        assert _assess_coverage(poor_analysis) == "NEEDS_IMPROVEMENT"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])