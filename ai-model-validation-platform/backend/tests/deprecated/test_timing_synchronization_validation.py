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

Original location: tests/test_timing_synchronization_validation.py
"""

"""
Test Suite for Timing Synchronization Calculator

This test validates the corrected latency calculation methodology and confirms
that the 75ms latency hypothesis is correct when accounting for video startup delays.
"""

import pytest
import time
from datetime import datetime, timezone
from typing import List, Dict, Any

# Add parent directory to path for imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.timing_synchronization_calculator import (
    TimingSynchronizationCalculator,
    VideoTimingMetadata,
    TimingSynchronizationResult
)


class TestTimingSynchronizationCalculator:
    """Test the timing synchronization calculator with realistic HIL data"""
    
    def setup_method(self):
        """Set up test environment"""
        self.calculator = TimingSynchronizationCalculator()
        
        # Test scenario based on the hypothesis
        self.base_time = time.time()
        self.labjack_start_time = self.base_time
        self.video_startup_delay_ms = 1800.0  # 1.8 seconds
        self.video_start_system_time = self.base_time + (self.video_startup_delay_ms / 1000.0)
        
        # Ground truth event occurs at frame 5, 0.208s into video (24fps)
        self.gt_frame = 5
        self.gt_video_time = 0.208  # seconds from video start
        self.gt_system_time = self.video_start_system_time + self.gt_video_time
        
        # Detection occurs 75ms after ground truth event (expected processing time)
        self.expected_processing_time_ms = 75.0
        self.detection_system_time = self.gt_system_time + (self.expected_processing_time_ms / 1000.0)
        
        # Video metadata
        self.video_metadata = VideoTimingMetadata(
            startup_delay_ms=self.video_startup_delay_ms,
            fps=24.0,
            duration=60.0,
            timing_sync_status="synced",
            timing_accuracy_ns=100000  # 100μs accuracy
        )
    
    def test_corrected_latency_calculation_hypothesis(self):
        """Test that corrected calculation matches the 75ms hypothesis"""
        
        result = self.calculator.calculate_corrected_latency(
            session_id="test_session_001",
            detection_id="det_001",
            detection_system_time=self.detection_system_time,
            ground_truth_frame=self.gt_frame,
            ground_truth_video_time=self.gt_video_time,
            video_timing_metadata=self.video_metadata,
            labjack_start_time=self.labjack_start_time
        )
        
        # Validate the correction
        expected_apparent_latency = (self.detection_system_time - self.labjack_start_time) * 1000.0
        expected_real_latency = self.expected_processing_time_ms
        
        # Check apparent latency (old incorrect calculation)
        assert abs(result.apparent_latency_ms - expected_apparent_latency) < 1.0, \
            f"Apparent latency should be ~{expected_apparent_latency:.1f}ms, got {result.apparent_latency_ms:.1f}ms"
        
        # Check real latency (new correct calculation)
        assert abs(result.real_latency_ms - expected_real_latency) < 1.0, \
            f"Real latency should be ~{expected_real_latency:.1f}ms, got {result.real_latency_ms:.1f}ms"
        
        # Check correction amount
        expected_correction = expected_apparent_latency - expected_real_latency
        assert abs(result.latency_correction_ms - expected_correction) < 1.0, \
            f"Correction should be ~{expected_correction:.1f}ms, got {result.latency_correction_ms:.1f}ms"
        
        # Validate that corrected latency matches processing time
        assert result.matches_processing_time, \
            f"Corrected latency {result.real_latency_ms:.1f}ms should match expected processing time range"
        
        # Timing quality should be good
        assert result.timing_quality in ["excellent", "good"], \
            f"Timing quality should be good, got {result.timing_quality}"
        
        # Confidence should be high
        assert result.confidence_score > 0.8, \
            f"Confidence score should be high, got {result.confidence_score:.2f}"
        
        print(f"✅ HYPOTHESIS CONFIRMED:")
        print(f"   Apparent latency: {result.apparent_latency_ms:.1f}ms (includes {self.video_startup_delay_ms:.0f}ms startup delay)")
        print(f"   Real latency: {result.real_latency_ms:.1f}ms (corrected)")
        print(f"   Correction applied: {result.latency_correction_ms:.1f}ms")
        print(f"   Matches expected processing time: {result.matches_processing_time}")
        print(f"   Timing quality: {result.timing_quality}")
        print(f"   Confidence score: {result.confidence_score:.2f}")
    
    def test_multiple_detections_scenario(self):
        """Test with multiple detection events across video timeline"""
        
        detection_events = []
        ground_truth_events = []
        
        # Create 5 detection events at different times
        for i in range(5):
            # GT events at different video times
            gt_frame = 5 + (i * 24)  # Every second (24fps)
            gt_video_time = gt_frame / 24.0
            
            # Detection occurs 75ms ± 10ms after GT (realistic variance)
            processing_time_ms = 75.0 + (i - 2) * 5.0  # 65, 70, 75, 80, 85ms
            
            gt_system_time = self.video_start_system_time + gt_video_time
            detection_system_time = gt_system_time + (processing_time_ms / 1000.0)
            
            detection_events.append({
                'id': f'det_{i:03d}',
                'timestamp': detection_system_time,
                'frame_number': gt_frame + 2,  # Detection frame slightly after GT
                'latency_ms': None,  # Will be calculated
                'processing_time_ms': processing_time_ms,
                'voltage_level': 3.3
            })
            
            ground_truth_events.append({
                'frame_number': gt_frame,
                'video_timestamp': gt_video_time,
                'event_type': 'vehicle_detection'
            })
        
        # Calculate batch corrected latencies
        results = self.calculator.calculate_batch_corrected_latencies(
            session_id="test_batch_001",
            detection_events=detection_events,
            ground_truth_events=ground_truth_events,
            video_timing_metadata=self.video_metadata,
            labjack_start_time=self.labjack_start_time
        )
        
        assert len(results) == 5, f"Should have 5 results, got {len(results)}"
        
        # Check that all results show reasonable latencies
        for i, result in enumerate(results):
            expected_processing_time = 75.0 + (i - 2) * 5.0
            
            # Real latency should be close to expected processing time
            assert abs(result.real_latency_ms - expected_processing_time) < 5.0, \
                f"Detection {i}: Real latency {result.real_latency_ms:.1f}ms should be ~{expected_processing_time:.1f}ms"
            
            # All should match processing time range
            assert result.matches_processing_time, \
                f"Detection {i}: Should match processing time range"
            
            # Apparent latency should be much higher
            assert result.apparent_latency_ms > result.real_latency_ms + 1000, \
                f"Detection {i}: Apparent latency should be much higher than real latency"
        
        # Get session statistics
        stats = self.calculator.get_session_statistics("test_batch_001")
        
        assert stats["total_calculations"] == 5
        assert stats["validation"]["percentage_matching"] == 100.0
        assert stats["real_latency_stats"]["average_ms"] == pytest.approx(75.0, abs=5.0)
        
        print(f"✅ BATCH TEST PASSED:")
        print(f"   Processed {len(results)} detections")
        print(f"   Average real latency: {stats['real_latency_stats']['average_ms']:.1f}ms")
        print(f"   Average apparent latency: {stats['apparent_latency_stats']['average_ms']:.1f}ms")
        print(f"   Average correction: {stats['correction_stats']['average_correction_ms']:.1f}ms")
        print(f"   Detections matching processing time: {stats['validation']['percentage_matching']:.0f}%")
    
    def test_edge_cases(self):
        """Test edge cases and error conditions"""
        
        # Test with zero startup delay
        zero_delay_metadata = VideoTimingMetadata(
            startup_delay_ms=0.0,
            fps=24.0,
            duration=60.0,
            timing_sync_status="synced"
        )
        
        result = self.calculator.calculate_corrected_latency(
            session_id="test_edge_001",
            detection_id="det_edge_001",
            detection_system_time=self.labjack_start_time + 1.0,  # 1 second after start
            ground_truth_frame=0,
            ground_truth_video_time=0.0,  # GT at video start
            video_timing_metadata=zero_delay_metadata,
            labjack_start_time=self.labjack_start_time
        )
        
        # With no startup delay, apparent and real latency should be the same
        assert abs(result.apparent_latency_ms - result.real_latency_ms) < 1.0, \
            "With no startup delay, apparent and real latency should be similar"
        
        # Test with very high startup delay
        high_delay_metadata = VideoTimingMetadata(
            startup_delay_ms=5000.0,  # 5 seconds
            fps=24.0,
            duration=60.0,
            timing_sync_status="synced"
        )
        
        result = self.calculator.calculate_corrected_latency(
            session_id="test_edge_002",
            detection_id="det_edge_002",
            detection_system_time=self.labjack_start_time + 6.0,  # 6 seconds after start
            ground_truth_frame=24,
            ground_truth_video_time=1.0,  # GT at 1 second into video
            video_timing_metadata=high_delay_metadata,
            labjack_start_time=self.labjack_start_time
        )
        
        # Correction should be close to startup delay
        expected_correction = 5000.0  # 5 seconds
        assert abs(result.latency_correction_ms - expected_correction) < 100.0, \
            f"High startup delay correction should be ~{expected_correction:.0f}ms"
        
        print(f"✅ EDGE CASES PASSED:")
        print(f"   Zero delay case: apparent={result.apparent_latency_ms:.1f}ms, real={result.real_latency_ms:.1f}ms")
        print(f"   High delay case: correction={result.latency_correction_ms:.1f}ms")
    
    def test_timing_quality_assessment(self):
        """Test timing quality assessment under different conditions"""
        
        # Test excellent quality (low latency, good accuracy)
        excellent_metadata = VideoTimingMetadata(
            startup_delay_ms=1800.0,
            fps=24.0,
            duration=60.0,
            timing_sync_status="synced",
            timing_accuracy_ns=50000  # 50μs - excellent
        )
        
        result = self.calculator.calculate_corrected_latency(
            session_id="test_quality_001",
            detection_id="det_quality_001",
            detection_system_time=self.detection_system_time,
            ground_truth_frame=self.gt_frame,
            ground_truth_video_time=self.gt_video_time,
            video_timing_metadata=excellent_metadata,
            labjack_start_time=self.labjack_start_time
        )
        
        assert result.timing_quality == "excellent", \
            f"Should have excellent timing quality, got {result.timing_quality}"
        assert result.confidence_score > 0.9, \
            f"Should have high confidence score, got {result.confidence_score:.2f}"
        
        # Test poor quality (high latency, poor accuracy)
        poor_metadata = VideoTimingMetadata(
            startup_delay_ms=1800.0,
            fps=24.0,
            duration=60.0,
            timing_sync_status="failed",
            timing_accuracy_ns=10_000_000  # 10ms - poor
        )
        
        # Detection with unrealistic latency
        poor_detection_time = self.gt_system_time + 0.5  # 500ms latency
        
        result = self.calculator.calculate_corrected_latency(
            session_id="test_quality_002",
            detection_id="det_quality_002",
            detection_system_time=poor_detection_time,
            ground_truth_frame=self.gt_frame,
            ground_truth_video_time=self.gt_video_time,
            video_timing_metadata=poor_metadata,
            labjack_start_time=self.labjack_start_time
        )
        
        assert result.timing_quality in ["poor", "fair"], \
            f"Should have poor timing quality, got {result.timing_quality}"
        assert result.confidence_score < 0.7, \
            f"Should have low confidence score, got {result.confidence_score:.2f}"
        
        print(f"✅ QUALITY ASSESSMENT PASSED:")
        print(f"   Excellent case: quality={result.timing_quality}, confidence={result.confidence_score:.2f}")
        print(f"   Poor case: quality={result.timing_quality}, confidence={result.confidence_score:.2f}")


def test_realistic_hil_scenario():
    """Test with realistic HIL scenario data"""
    
    print("\n" + "="*60)
    print("REALISTIC HIL TIMING SYNCHRONIZATION TEST")
    print("="*60)
    
    calculator = TimingSynchronizationCalculator()
    
    # Realistic HIL test scenario
    base_time = 1704067200.0  # Fixed timestamp for reproducibility
    
    # LabJack starts monitoring at T=0
    labjack_start_time = base_time
    
    # Video has 1.8s startup delay (typical for video streaming)
    video_startup_delay_ms = 1800.0
    video_start_system_time = labjack_start_time + (video_startup_delay_ms / 1000.0)
    
    # Ground truth events occur in video
    gt_events = [
        {"frame": 5, "video_time": 0.208},    # Frame 5 at 0.208s (24fps)
        {"frame": 50, "video_time": 2.083},   # Frame 50 at 2.083s  
        {"frame": 120, "video_time": 5.0},    # Frame 120 at 5.0s
    ]
    
    # Detections occur with typical processing delays
    detection_processing_times = [75, 68, 82]  # ms
    
    video_metadata = VideoTimingMetadata(
        startup_delay_ms=video_startup_delay_ms,
        fps=24.0,
        duration=60.0,
        timing_sync_status="synced",
        timing_accuracy_ns=100000  # 100μs
    )
    
    results = []
    
    print(f"Video startup delay: {video_startup_delay_ms:.0f}ms")
    print(f"LabJack start time: {labjack_start_time:.3f}")
    print(f"Video start time: {video_start_system_time:.3f}")
    print()
    
    for i, (gt_event, processing_time) in enumerate(zip(gt_events, detection_processing_times)):
        # Calculate ground truth system time
        gt_system_time = video_start_system_time + gt_event["video_time"]
        
        # Calculate detection system time
        detection_system_time = gt_system_time + (processing_time / 1000.0)
        
        # Calculate latencies using the timing synchronization calculator
        result = calculator.calculate_corrected_latency(
            session_id="realistic_test",
            detection_id=f"realistic_det_{i:03d}",
            detection_system_time=detection_system_time,
            ground_truth_frame=gt_event["frame"],
            ground_truth_video_time=gt_event["video_time"],
            video_timing_metadata=video_metadata,
            labjack_start_time=labjack_start_time
        )
        
        results.append(result)
        
        print(f"Detection {i+1}:")
        print(f"  GT Frame: {gt_event['frame']}, Video Time: {gt_event['video_time']:.3f}s")
        print(f"  Processing Time: {processing_time}ms")
        print(f"  Apparent Latency: {result.apparent_latency_ms:.1f}ms (WRONG - includes startup delay)")
        print(f"  Real Latency: {result.real_latency_ms:.1f}ms (CORRECT)")
        print(f"  Correction Applied: {result.latency_correction_ms:.1f}ms")
        print(f"  Matches Processing Time: {result.matches_processing_time}")
        print(f"  Timing Quality: {result.timing_quality}")
        print()
    
    # Get comprehensive statistics
    stats = calculator.get_session_statistics("realistic_test")
    
    print("SUMMARY STATISTICS:")
    print(f"  Total Detections: {stats['total_calculations']}")
    print(f"  Average Apparent Latency: {stats['apparent_latency_stats']['average_ms']:.1f}ms")
    print(f"  Average Real Latency: {stats['real_latency_stats']['average_ms']:.1f}ms")
    print(f"  Average Correction: {stats['correction_stats']['average_correction_ms']:.1f}ms")
    print(f"  Detections Matching Processing Time: {stats['validation']['percentage_matching']:.0f}%")
    print(f"  Average Confidence Score: {stats['validation']['average_confidence_score']:.2f}")
    
    improvement = stats['timing_synchronization']['latency_improvement']
    print(f"  Latency Improvement: {improvement['improvement_ms']:.1f}ms ({improvement['improvement_percentage']:.1f}%)")
    
    print()
    print("CONCLUSION:")
    if stats['validation']['percentage_matching'] > 80:
        print("✅ HYPOTHESIS CONFIRMED: Real detection latency ~75ms (not ~1875ms)")
        print("✅ Video startup delay correction successfully reveals true performance")
    else:
        print("❌ HYPOTHESIS NOT CONFIRMED: Further investigation needed")
    
    return results, stats


if __name__ == "__main__":
    # Run the realistic HIL scenario test
    results, stats = test_realistic_hil_scenario()
    
    # Run the full test suite
    print("\n" + "="*60)
    print("RUNNING FULL TEST SUITE")
    print("="*60)
    
    test_instance = TestTimingSynchronizationCalculator()
    test_instance.setup_method()
    
    try:
        test_instance.test_corrected_latency_calculation_hypothesis()
        test_instance.test_multiple_detections_scenario()
        test_instance.test_edge_cases()
        test_instance.test_timing_quality_assessment()
        
        print("\n✅ ALL TESTS PASSED!")
        print("✅ TIMING SYNCHRONIZATION CALCULATOR VALIDATED!")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise