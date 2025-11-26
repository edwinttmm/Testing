"""
DEPRECATED TEST FILE
===================

This test file has been deprecated on 2025-11-20 because it imports services
that no longer exist or have been removed from the codebase.

Deprecated services used:
- Services that were removed during architecture refactoring
- Services that were consolidated into other modules
- Services that were replaced with newer implementations

This file is preserved for historical reference but is not actively maintained.
If you need similar functionality, please check the current service implementations
in src/services/ or consult the documentation.

Original location: tests/test_frame_aware_quality_assessment.py
"""

"""
Test Frame-Aware Timing Quality Assessment

This test validates the enhanced timing quality assessment system that considers
frame-level correlation accuracy to distinguish camera timing from system overhead.
"""

import logging
import time
import sys
import os
from typing import Dict, List, Any

# Add parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the services to test
from services.frame_aware_quality_assessment import (
    get_frame_aware_quality_service,
    FrameCorrelationMetrics,
    TimingQualityDimensions,
    QualityClassification
)
from services.timing_synchronization_calculator import (
    get_timing_synchronization_calculator,
    VideoTimingMetadata
)

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestFrameAwareQualityAssessment:
    """Test suite for frame-aware timing quality assessment"""
    
    def setup_method(self):
        """Setup test environment"""
        self.quality_service = get_frame_aware_quality_service()
        self.timing_calculator = get_timing_synchronization_calculator()
        
    def create_test_detection_events(self, quality_level: str = "good") -> List[Dict[str, Any]]:
        """Create test detection events with different quality levels"""
        base_time = time.time()
        fps = 30
        frame_interval = 1.0 / fps
        
        events = []
        
        if quality_level == "excellent":
            # Perfect frame alignment and timing
            for i in range(10):
                frame_num = i * 3  # Every 3rd frame for realistic detection
                timestamp = i * 0.1  # 100ms intervals
                events.append({
                    'id': f'det_{i}',
                    'timestamp': base_time + timestamp,
                    'video_relative_timestamp': timestamp,
                    'frame_number': frame_num,
                    'video_frame_number': frame_num,
                    'confidence': 0.95
                })
                
        elif quality_level == "good":
            # Good frame alignment with minor drift
            for i in range(10):
                frame_num = i * 3
                timestamp = i * 0.1 + (i * 0.002)  # Small cumulative drift
                events.append({
                    'id': f'det_{i}',
                    'timestamp': base_time + timestamp,
                    'video_relative_timestamp': timestamp,
                    'frame_number': frame_num,
                    'video_frame_number': frame_num,
                    'confidence': 0.85
                })
                
        elif quality_level == "poor":
            # Poor frame alignment and inconsistent timing
            for i in range(10):
                frame_num = i * 3 + (i % 3)  # Inconsistent frame spacing
                timestamp = i * 0.1 + (i * 0.02 * (i % 2))  # Irregular timing
                events.append({
                    'id': f'det_{i}',
                    'timestamp': base_time + timestamp,
                    'video_relative_timestamp': timestamp,
                    'frame_number': frame_num,
                    'video_frame_number': frame_num,
                    'confidence': 0.6
                })
        
        return events
    
    def create_test_ground_truth_events(self) -> List[Dict[str, Any]]:
        """Create test ground truth events"""
        events = []
        for i in range(5):
            events.append({
                'id': f'gt_{i}',
                'timestamp': i * 0.2,  # Every 200ms
                'video_timestamp': i * 0.2,
                'frame_number': i * 6,  # Every 6th frame at 30fps
                'confidence': 1.0
            })
        return events
    
    def create_test_video_metadata(self) -> Dict[str, Any]:
        """Create test video metadata"""
        return {
            'fps': 30,
            'frame_rate': 30,
            'duration': 2.0,
            'startup_delay_ms': 1500,
            'timing_sync_status': 'synchronized'
        }
    
    def test_frame_correlation_assessment_excellent_quality(self):
        """Test frame correlation assessment with excellent quality data"""
        logger.info("Testing frame correlation assessment with excellent quality")
        
        detection_events = self.create_test_detection_events("excellent")
        ground_truth_events = self.create_test_ground_truth_events()
        video_metadata = self.create_test_video_metadata()
        
        # Assess frame correlation
        frame_metrics = self.quality_service.assess_frame_correlation(
            detection_events, ground_truth_events, video_metadata
        )
        
        # Verify excellent quality metrics
        assert frame_metrics.frame_alignment_accuracy >= 0.8, f"Expected high alignment accuracy, got {frame_metrics.frame_alignment_accuracy}"
        assert frame_metrics.temporal_consistency >= 0.8, f"Expected high temporal consistency, got {frame_metrics.temporal_consistency}"
        assert frame_metrics.confidence_score >= 0.7, f"Expected high confidence, got {frame_metrics.confidence_score}"
        assert frame_metrics.frame_drift_ms <= 50, f"Expected low frame drift, got {frame_metrics.frame_drift_ms}ms"
        
        logger.info(f"Excellent quality metrics: alignment={frame_metrics.frame_alignment_accuracy:.3f}, "
                   f"consistency={frame_metrics.temporal_consistency:.3f}, "
                   f"confidence={frame_metrics.confidence_score:.3f}")
    
    def test_frame_correlation_assessment_poor_quality(self):
        """Test frame correlation assessment with poor quality data"""
        logger.info("Testing frame correlation assessment with poor quality")
        
        detection_events = self.create_test_detection_events("poor")
        ground_truth_events = self.create_test_ground_truth_events()
        video_metadata = self.create_test_video_metadata()
        
        # Assess frame correlation
        frame_metrics = self.quality_service.assess_frame_correlation(
            detection_events, ground_truth_events, video_metadata
        )
        
        # Verify poor quality detection
        assert frame_metrics.confidence_score <= 0.7, f"Expected lower confidence for poor quality, got {frame_metrics.confidence_score}"
        
        logger.info(f"Poor quality metrics: alignment={frame_metrics.frame_alignment_accuracy:.3f}, "
                   f"consistency={frame_metrics.temporal_consistency:.3f}, "
                   f"confidence={frame_metrics.confidence_score:.3f}")
    
    def test_comprehensive_quality_assessment(self):
        """Test comprehensive multi-dimensional quality assessment"""
        logger.info("Testing comprehensive quality assessment")
        
        detection_events = self.create_test_detection_events("good")
        ground_truth_events = self.create_test_ground_truth_events()
        video_metadata = self.create_test_video_metadata()
        
        # Create mock timing results
        timing_results = [{
            'real_latency_ms': 75.0,
            'timing_accuracy_ns': 500_000,  # 0.5ms
            'camera_only_latency_ms': 50.0,
            'system_overhead_ms': 15.0,
            'processing_overhead_ms': 10.0
        }]
        
        # Perform comprehensive assessment
        quality_dimensions = self.quality_service.assess_comprehensive_quality(
            detection_events, ground_truth_events, timing_results, video_metadata
        )
        
        # Verify all dimensions are assessed
        assert quality_dimensions.frame_correlation is not None
        assert 0.0 <= quality_dimensions.timestamp_precision <= 1.0
        assert 0.0 <= quality_dimensions.latency_consistency <= 1.0
        assert 0.0 <= quality_dimensions.system_overhead_ratio <= 1.0
        assert 0.0 <= quality_dimensions.camera_response_quality <= 1.0
        assert 0.0 <= quality_dimensions.validation_reliability <= 1.0
        assert 0.0 <= quality_dimensions.overall_quality_score <= 1.0
        
        logger.info(f"Quality dimensions: overall={quality_dimensions.overall_quality_score:.3f}, "
                   f"validation_reliability={quality_dimensions.validation_reliability:.3f}, "
                   f"camera_quality={quality_dimensions.camera_response_quality:.3f}")
    
    def test_quality_classification(self):
        """Test quality classification with actionable insights"""
        logger.info("Testing quality classification")
        
        detection_events = self.create_test_detection_events("good")
        ground_truth_events = self.create_test_ground_truth_events()
        video_metadata = self.create_test_video_metadata()
        
        # Create timing results
        timing_results = [{
            'real_latency_ms': 75.0,
            'timing_accuracy_ns': 500_000,
            'camera_only_latency_ms': 50.0,
            'system_overhead_ms': 15.0,
            'processing_overhead_ms': 10.0
        }]
        
        # Perform assessment and classification
        quality_dimensions = self.quality_service.assess_comprehensive_quality(
            detection_events, ground_truth_events, timing_results, video_metadata
        )
        
        classification = self.quality_service.classify_timing_quality(quality_dimensions)
        
        # Verify classification fields
        assert classification.category in ['excellent', 'good', 'fair', 'poor', 'unreliable']
        assert classification.confidence_level in ['high', 'medium', 'low']
        assert classification.validation_suitability in ['suitable', 'conditional', 'unsuitable']
        assert classification.camera_timing_quality in ['precise', 'acceptable', 'imprecise']
        assert classification.system_timing_quality in ['precise', 'acceptable', 'imprecise']
        assert isinstance(classification.recommendations, list)
        assert isinstance(classification.warning_flags, list)
        
        logger.info(f"Classification: {classification.category} quality, "
                   f"{classification.confidence_level} confidence, "
                   f"{classification.validation_suitability} for validation")
        logger.info(f"Recommendations: {', '.join(classification.recommendations)}")
        
        if classification.warning_flags:
            logger.info(f"Warning flags: {', '.join(classification.warning_flags)}")
    
    def test_enhanced_timing_calculator_integration(self):
        """Test integration with timing synchronization calculator"""
        logger.info("Testing enhanced timing calculator integration")
        
        detection_events = self.create_test_detection_events("good")
        ground_truth_events = self.create_test_ground_truth_events()
        
        # Create video timing metadata
        video_metadata = VideoTimingMetadata(
            startup_delay_ms=1500.0,
            fps=30.0,
            duration=2.0,
            timing_sync_status="synchronized",
            timing_accuracy_ns=500_000
        )
        
        session_id = "test_session_001"
        labjack_start_time = time.time()
        
        # Test batch calculation with frame-aware quality
        results = self.timing_calculator.calculate_batch_corrected_latencies(
            session_id=session_id,
            detection_events=detection_events,
            ground_truth_events=ground_truth_events,
            video_timing_metadata=video_metadata,
            labjack_start_time=labjack_start_time,
            enable_frame_aware_quality=True
        )
        
        # Verify enhanced results
        assert len(results) > 0, "Should have calculated some results"
        
        for result in results:
            # Check that enhanced quality metrics are present
            if result.quality_classification:
                assert result.quality_classification.category is not None
                assert result.quality_classification.validation_suitability is not None
                logger.info(f"Result {result.detection_id}: {result.quality_classification.category} quality")
            
            # Timing quality should be assessed
            assert result.timing_quality is not None
            assert result.confidence_score >= 0.0
            
        logger.info(f"Processed {len(results)} results with enhanced quality assessment")
    
    def test_camera_vs_system_timing_distinction(self):
        """Test distinction between camera timing and system timing issues"""
        logger.info("Testing camera vs system timing distinction")
        
        # Test scenario 1: Good camera timing, poor system timing
        detection_events_good_camera = self.create_test_detection_events("excellent")
        
        # Create timing results with high system overhead
        timing_results_high_overhead = [{
            'real_latency_ms': 200.0,  # High total latency
            'timing_accuracy_ns': 2_000_000,  # Poor system timing precision
            'camera_only_latency_ms': 60.0,   # Good camera response
            'system_overhead_ms': 100.0,      # High system overhead
            'processing_overhead_ms': 40.0    # High processing overhead
        }]
        
        ground_truth_events = self.create_test_ground_truth_events()
        video_metadata = self.create_test_video_metadata()
        
        quality_dimensions = self.quality_service.assess_comprehensive_quality(
            detection_events_good_camera, ground_truth_events, timing_results_high_overhead, video_metadata
        )
        
        classification = self.quality_service.classify_timing_quality(quality_dimensions)
        
        # Should detect good camera timing but poor system timing
        assert classification.camera_timing_quality in ['precise', 'acceptable'], \
            f"Expected good camera timing, got {classification.camera_timing_quality}"
        
        # Should detect high system overhead
        assert quality_dimensions.system_overhead_ratio > 0.5, \
            f"Expected high system overhead ratio, got {quality_dimensions.system_overhead_ratio}"
        
        # Should recommend system optimization
        recommendations_text = ' '.join(classification.recommendations).lower()
        assert any(keyword in recommendations_text for keyword in ['system', 'overhead', 'optimize']), \
            f"Expected system optimization recommendations, got: {classification.recommendations}"
        
        logger.info(f"Camera timing: {classification.camera_timing_quality}, "
                   f"System timing: {classification.system_timing_quality}, "
                   f"System overhead ratio: {quality_dimensions.system_overhead_ratio:.3f}")


if __name__ == "__main__":
    # Run tests directly
    test_suite = TestFrameAwareQualityAssessment()
    test_suite.setup_method()
    
    try:
        print("🧪 Testing Frame-Aware Timing Quality Assessment")
        print("=" * 60)
        
        # Run individual tests
        test_suite.test_frame_correlation_assessment_excellent_quality()
        print("✅ Frame correlation assessment (excellent quality) - PASSED")
        
        test_suite.test_frame_correlation_assessment_poor_quality()
        print("✅ Frame correlation assessment (poor quality) - PASSED")
        
        test_suite.test_comprehensive_quality_assessment()
        print("✅ Comprehensive quality assessment - PASSED")
        
        test_suite.test_quality_classification()
        print("✅ Quality classification - PASSED")
        
        test_suite.test_enhanced_timing_calculator_integration()
        print("✅ Enhanced timing calculator integration - PASSED")
        
        test_suite.test_camera_vs_system_timing_distinction()
        print("✅ Camera vs system timing distinction - PASSED")
        
        print("\n" + "=" * 60)
        print("🎉 All frame-aware quality assessment tests PASSED!")
        print("\nKey improvements implemented:")
        print("• Frame correlation accuracy scoring")
        print("• Multi-dimensional quality assessment")
        print("• Camera vs system timing distinction")
        print("• Actionable recommendations and warnings")
        print("• Enhanced confidence metrics")
        print("• Validation reliability indicators")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()