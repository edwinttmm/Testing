"""
Integration test for Detection Boundary Analysis Service

This test validates the complete detection boundary analysis workflow
including the API endpoint integration with realistic HIL test data.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from services.detection_boundary_service import DetectionBoundaryAnalyzer

class TestDetectionBoundaryIntegration:
    """Integration tests for the detection boundary analysis system"""
    
    def setup_method(self):
        """Set up test fixtures with realistic HIL test data"""
        self.analyzer = DetectionBoundaryAnalyzer()
        
        # Realistic HIL test scenario:
        # Video: 90 seconds (2700 frames at 30fps)
        # Detection monitoring stops at Frame 84 (~2.8 seconds)
        # Ground truth events exist beyond Frame 84 (should be marked as "video ended")
        
        self.realistic_detections = [
            {
                'id': 1, 
                'timestamp': 1.2, 
                'detection_time': 1.2, 
                'video_timestamp': 1.2,
                'video_frame': 36,
                'latency_ms': 45
            },
            {
                'id': 2, 
                'timestamp': 2.1, 
                'detection_time': 2.1, 
                'video_timestamp': 2.1,
                'video_frame': 63,
                'latency_ms': 38
            },
            {
                'id': 3, 
                'timestamp': 2.8, 
                'detection_time': 2.8, 
                'video_timestamp': 2.8,
                'video_frame': 84,  # Last detection at Frame 84
                'latency_ms': 42
            }
        ]
        
        self.realistic_ground_truth = [
            # GT events during monitoring (should have matched detections)
            {'id': 1, 'video_frame': 30, 'frame_number': 30, 'event_type': 'pedestrian_detection'},
            {'id': 2, 'video_frame': 60, 'frame_number': 60, 'event_type': 'pedestrian_detection'},
            {'id': 3, 'video_frame': 85, 'frame_number': 85, 'event_type': 'pedestrian_detection'},
            
            # GT events after monitoring stopped (should be marked as "expected no detection")
            {'id': 4, 'video_frame': 150, 'frame_number': 150, 'event_type': 'pedestrian_detection'},
            {'id': 5, 'video_frame': 300, 'frame_number': 300, 'event_type': 'pedestrian_detection'},
            {'id': 6, 'video_frame': 600, 'frame_number': 600, 'event_type': 'pedestrian_detection'},
            {'id': 7, 'video_frame': 1200, 'frame_number': 1200, 'event_type': 'pedestrian_detection'},
            {'id': 8, 'video_frame': 2400, 'frame_number': 2400, 'event_type': 'pedestrian_detection'}
        ]
        
        self.video_metadata = {
            'duration': 90.0,
            'duration_s': 90.0,
            'fps': 30,
            'frame_rate': 30,
            'total_frames': 2700,
            'filename': 'hil_test_pedestrian_detection.mp4',
            'width': 1920,
            'height': 1080
        }
    
    def test_hil_boundary_analysis_realistic_scenario(self):
        """Test boundary analysis with realistic HIL test scenario"""
        
        result = self.analyzer.analyze_detection_boundaries(
            detection_events=self.realistic_detections,
            ground_truth_events=self.realistic_ground_truth,
            video_metadata=self.video_metadata
        )
        
        # Verify basic structure
        assert 'last_detection_time' in result
        assert 'video_duration' in result
        assert 'monitoring_end_time' in result
        assert 'categorized_events' in result
        assert 'boundary_analysis' in result
        
        # Test boundary detection
        assert result['last_detection_time'] == 2.8  # Last detection at 2.8s
        assert result['video_duration'] == 90.0
        assert result['monitoring_end_time'] > 2.8  # Should have grace period
        
        # Test event categorization
        categorized = result['categorized_events']
        
        # During monitoring: Frame 30 (1.0s), Frame 60 (2.0s), Frame 85 (2.83s)
        assert len(categorized['during_monitoring']) == 3
        
        # After monitoring: Frames 150, 300, 600, 1200, 2400 (all after ~3.0s)
        assert len(categorized['after_monitoring']) == 5
        
        # Expected after monitoring (same as after_monitoring for this scenario)
        assert len(categorized['expected_after']) == 5
        
        # Test boundary analysis metrics
        analysis = result['boundary_analysis']
        
        # Coverage should be very low (2.8s / 90s = ~3.1%)
        assert analysis['detection_coverage_percent'] < 10
        
        # Should have sufficient status for early monitoring period
        assert analysis['recommended_status'] == 'insufficient_coverage'
        
        # Post-video GT count should match events after monitoring
        assert analysis['post_video_gt_count'] == 5
        
        # Total events should match
        assert analysis['total_gt_events'] == 8
        assert analysis['total_detection_events'] == 3
    
    def test_edge_case_complete_video_coverage(self):
        """Test scenario where detection monitoring covers entire video"""
        
        # Extend detection monitoring to near end of video
        extended_detections = self.realistic_detections + [
            {'id': 4, 'timestamp': 45.0, 'detection_time': 45.0, 'video_frame': 1350},
            {'id': 5, 'timestamp': 87.5, 'detection_time': 87.5, 'video_frame': 2625}  # Near end
        ]
        
        result = self.analyzer.analyze_detection_boundaries(
            detection_events=extended_detections,
            ground_truth_events=self.realistic_ground_truth,
            video_metadata=self.video_metadata
        )
        
        # Should have much better coverage
        analysis = result['boundary_analysis']
        assert analysis['detection_coverage_percent'] > 95  # 87.5/90 = ~97%
        assert analysis['recommended_status'] in ['complete_coverage', 'good_coverage']
        
        # Should have fewer events after monitoring
        categorized = result['categorized_events']
        assert len(categorized['after_monitoring']) <= 1  # Only last GT event might be after
    
    def test_missing_detections_identification(self):
        """Test identification of missing detections vs video end scenarios"""
        
        # Remove middle detection to simulate missing detection during monitoring
        detections_with_gap = [
            self.realistic_detections[0],  # Keep first
            # Skip second detection (missing detection)
            self.realistic_detections[2]   # Keep third
        ]
        
        result = self.analyzer.analyze_detection_boundaries(
            detection_events=detections_with_gap,
            ground_truth_events=self.realistic_ground_truth,
            video_metadata=self.video_metadata
        )
        
        # Should identify missing detection during monitoring period
        categorized = result['categorized_events']
        
        # Should have unmatched GT events during monitoring (missing detections)
        assert len(categorized['unmatched_during']) >= 1
        
        # Should still have events after monitoring (video end, not missing detections)
        assert len(categorized['expected_after']) >= 3
        
        analysis = result['boundary_analysis']
        
        # Missing detection count should be positive
        assert analysis['missing_detection_count'] > 0
        
        # Post-video GT count should remain high (not missing, just after video)
        assert analysis['post_video_gt_count'] >= 3
    
    def test_zero_duration_video_handling(self):
        """Test handling of zero or invalid video duration"""
        
        zero_duration_metadata = {**self.video_metadata, 'duration': 0, 'duration_s': 0}
        
        result = self.analyzer.analyze_detection_boundaries(
            detection_events=self.realistic_detections,
            ground_truth_events=self.realistic_ground_truth,
            video_metadata=zero_duration_metadata
        )
        
        # Should handle gracefully
        assert result['boundary_analysis']['detection_coverage_percent'] == 0.0
        assert result['boundary_analysis']['monitoring_completeness'] == 0.0
    
    def test_api_endpoint_data_format_compatibility(self):
        """Test that the service output is compatible with API endpoint format"""
        
        result = self.analyzer.analyze_detection_boundaries(
            detection_events=self.realistic_detections,
            ground_truth_events=self.realistic_ground_truth,
            video_metadata=self.video_metadata
        )
        
        # Verify API endpoint expected fields
        required_fields = [
            'last_detection_time', 'video_duration', 'monitoring_end_time',
            'categorized_events', 'boundary_analysis'
        ]
        
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
        
        # Verify categorized_events structure
        categorized = result['categorized_events']
        required_categories = [
            'during_monitoring', 'after_monitoring', 'unmatched_during', 'expected_after'
        ]
        
        for category in required_categories:
            assert category in categorized, f"Missing category: {category}"
            assert isinstance(categorized[category], list), f"Category {category} should be a list"
        
        # Verify boundary_analysis structure
        analysis = result['boundary_analysis']
        required_analysis_fields = [
            'detection_coverage_percent', 'missing_detection_count', 
            'post_video_gt_count', 'recommended_status'
        ]
        
        for field in required_analysis_fields:
            assert field in analysis, f"Missing analysis field: {field}"
        
        # Verify data types
        assert isinstance(analysis['detection_coverage_percent'], (int, float))
        assert isinstance(analysis['missing_detection_count'], int)
        assert isinstance(analysis['post_video_gt_count'], int)
        assert isinstance(analysis['recommended_status'], str)
    
    def test_frame_84_boundary_specific_case(self):
        """Test the specific Frame 84 boundary case mentioned in requirements"""
        
        # Simulate exact scenario: last detection at Frame 84, GT events beyond
        frame_84_detections = [
            {'id': 1, 'timestamp': 2.8, 'detection_time': 2.8, 'video_frame': 84}
        ]
        
        beyond_frame_84_gt = [
            {'id': 1, 'video_frame': 84, 'frame_number': 84},   # At boundary
            {'id': 2, 'video_frame': 85, 'frame_number': 85},   # Just after
            {'id': 3, 'video_frame': 100, 'frame_number': 100}, # Well after
            {'id': 4, 'video_frame': 200, 'frame_number': 200}, # Much later
        ]
        
        result = self.analyzer.analyze_detection_boundaries(
            detection_events=frame_84_detections,
            ground_truth_events=beyond_frame_84_gt,
            video_metadata=self.video_metadata
        )
        
        categorized = result['categorized_events']
        
        # Frame 84 GT should be during monitoring (matched)
        during_monitoring = categorized['during_monitoring']
        assert len(during_monitoring) >= 1
        assert any(event['frame_number'] == 84 for event in during_monitoring)
        
        # Frames 85, 100, 200 should be after monitoring (video ended)
        after_monitoring = categorized['after_monitoring']
        after_frames = [event['frame_number'] for event in after_monitoring]
        
        assert 85 in after_frames or 100 in after_frames or 200 in after_frames
        
        # These should be marked as "expected after" not "missing detections"
        expected_after = categorized['expected_after']
        assert len(expected_after) >= 2  # At least events after Frame 84

if __name__ == "__main__":
    pytest.main([__file__, "-v"])