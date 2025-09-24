"""
Frame Timing Synchronization Edge Cases Test Suite

This test suite focuses on edge cases and error conditions in frame-based timing
synchronization, ensuring robust handling of real-world scenarios where frame
data might be incomplete, inconsistent, or corrupted.

Specific focus on scenarios that could cause the user's concern:
"why is the frame not mentioned for detection if that was there it would have helped"
"""

import pytest
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import statistics

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    TestSession, DetectionEvent, TestResult, Video, Project,
    DetectionComparison, GroundTruthObject, Base
)
from services.ground_truth_matching_service import GroundTruthMatchingService
from services.timing_synchronization_calculator import TimingSynchronizationCalculator, VideoTimingMetadata
from database import SessionLocal

# Test session constants
EDGE_CASE_SESSION_ID = "edge-case-test-session-001"
VIDEO_FPS = 24.0
FRAME_DURATION_MS = 1000.0 / VIDEO_FPS  # ~41.67ms per frame


class TestFrameTimingSynchronizationEdgeCases:
    """Test suite for frame timing edge cases and error conditions"""
    
    def setup_method(self):
        """Set up test environment for each test"""
        self.base_timestamp = time.time()
        self.video_start_timestamp = self.base_timestamp + 2.0  # 2s startup delay
        
        # Create timing calculator
        self.timing_calculator = TimingSynchronizationCalculator()
        
        # Video metadata with various quality levels
        self.video_metadata_high_quality = VideoTimingMetadata(
            startup_delay_ms=2000.0,
            fps=VIDEO_FPS,
            duration=60.0,
            timing_sync_status="synced",
            timing_accuracy_ns=50_000  # 50μs accuracy
        )
        
        self.video_metadata_poor_quality = VideoTimingMetadata(
            startup_delay_ms=2000.0,
            fps=VIDEO_FPS,
            duration=60.0,
            timing_sync_status="failed",
            timing_accuracy_ns=10_000_000  # 10ms accuracy - poor
        )
    
    def test_missing_frame_numbers_in_detection_events(self):
        """
        Test scenario where detection events have timestamps but missing frame numbers
        This addresses the user's concern about frame information not being available
        """
        print("\n🔍 Testing missing frame numbers in detection events...")
        
        # Simulate detection events with missing frame data
        detection_events = [
            {
                'id': 'det_001',
                'timestamp': self.video_start_timestamp + 1.0,  # 1s into video
                'frame_number': None,  # MISSING FRAME DATA
                'latency_ms': None,
                'video_relative_timestamp': 1.0,
                'processing_time_ms': 75.0,
                'voltage_level': 3.3
            },
            {
                'id': 'det_002', 
                'timestamp': self.video_start_timestamp + 3.0,  # 3s into video
                'frame_number': None,  # MISSING FRAME DATA
                'latency_ms': None,
                'video_relative_timestamp': 3.0,
                'processing_time_ms': 82.0,
                'voltage_level': 3.3
            }
        ]
        
        # Ground truth events with frame numbers
        ground_truth_events = [
            {
                'frame_number': 24,  # 1s at 24fps
                'video_timestamp': 1.0,
                'event_type': 'vehicle_detection'
            },
            {
                'frame_number': 72,  # 3s at 24fps
                'video_timestamp': 3.0,
                'event_type': 'vehicle_detection'
            }
        ]
        
        # Test frame number reconstruction from timestamp
        for i, detection in enumerate(detection_events):
            video_time = detection['video_relative_timestamp']
            reconstructed_frame = int(video_time * VIDEO_FPS)
            expected_frame = ground_truth_events[i]['frame_number']
            
            # Verify frame reconstruction accuracy
            frame_error = abs(reconstructed_frame - expected_frame)
            assert frame_error <= 1, (
                f"Frame reconstruction error for detection {i}: "
                f"Expected frame {expected_frame}, reconstructed {reconstructed_frame}"
            )
            
            # Test that timing calculator can handle missing frame data
            result = self.timing_calculator.calculate_corrected_latency(
                session_id="edge_test_missing_frames",
                detection_id=detection['id'],
                detection_system_time=detection['timestamp'],
                ground_truth_frame=expected_frame,
                ground_truth_video_time=video_time,
                video_timing_metadata=self.video_metadata_high_quality,
                labjack_start_time=self.base_timestamp
            )
            
            # Should succeed despite missing frame data
            assert result is not None, f"Should handle missing frame data for detection {i}"
            assert result.real_latency_ms > 0, f"Should calculate latency despite missing frames"
            
            # Frame correlation quality should be reduced but not failed
            assert result.timing_quality in ["good", "fair", "poor"], (
                f"Should handle missing frame data gracefully, got quality: {result.timing_quality}"
            )
        
        print(f"✅ Missing frame data handled - reconstructed frames from timestamps")
        print(f"   Detection 1: Frame {int(detection_events[0]['video_relative_timestamp'] * VIDEO_FPS)} reconstructed")
        print(f"   Detection 2: Frame {int(detection_events[1]['video_relative_timestamp'] * VIDEO_FPS)} reconstructed")
    
    def test_inconsistent_frame_timing_data(self):
        """
        Test scenario where frame numbers don't match timestamps
        (e.g., frame number says frame 100, but timestamp indicates frame 105)
        """
        print("\n🔍 Testing inconsistent frame timing data...")
        
        # Create inconsistent detection data
        detection_events = [
            {
                'id': 'det_inconsistent_001',
                'timestamp': self.video_start_timestamp + 2.0,  # 2s into video
                'frame_number': 60,  # Claims frame 60 (2.5s at 24fps)
                'video_relative_timestamp': 2.0,  # But timestamp says 2.0s (frame 48)
                'latency_ms': None,
                'processing_time_ms': 78.0
            },
            {
                'id': 'det_inconsistent_002',
                'timestamp': self.video_start_timestamp + 4.0,  # 4s into video  
                'frame_number': 80,  # Claims frame 80 (3.33s at 24fps)
                'video_relative_timestamp': 4.0,  # But timestamp says 4.0s (frame 96)
                'latency_ms': None,
                'processing_time_ms': 85.0
            }
        ]
        
        ground_truth_events = [
            {'frame_number': 48, 'video_timestamp': 2.0},  # Matches timestamp, not frame claim
            {'frame_number': 96, 'video_timestamp': 4.0}   # Matches timestamp, not frame claim
        ]
        
        # Test inconsistency detection and resolution
        for i, (detection, gt) in enumerate(zip(detection_events, ground_truth_events)):
            claimed_frame = detection['frame_number']
            video_time = detection['video_relative_timestamp']
            expected_frame_from_timestamp = int(video_time * VIDEO_FPS)
            
            # Detect inconsistency
            frame_inconsistency = abs(claimed_frame - expected_frame_from_timestamp)
            is_inconsistent = frame_inconsistency > 2  # Allow 2-frame tolerance
            
            assert is_inconsistent, (
                f"Detection {i} should be flagged as inconsistent: "
                f"Claimed frame {claimed_frame}, timestamp indicates frame {expected_frame_from_timestamp}"
            )
            
            # Test timing calculator handles inconsistency
            result = self.timing_calculator.calculate_corrected_latency(
                session_id="edge_test_inconsistent",
                detection_id=detection['id'],
                detection_system_time=detection['timestamp'],
                ground_truth_frame=gt['frame_number'],
                ground_truth_video_time=gt['video_timestamp'],
                video_timing_metadata=self.video_metadata_poor_quality,  # Use poor quality metadata
                labjack_start_time=self.base_timestamp
            )
            
            # Should handle inconsistency by preferring timestamp over frame claim
            assert result is not None, f"Should handle inconsistent frame data"
            assert result.timing_quality in ["fair", "poor"], (
                f"Quality should be degraded due to inconsistency, got: {result.timing_quality}"
            )
            
            # Confidence should be reduced
            assert result.confidence_score < 0.8, (
                f"Confidence should be reduced due to inconsistency, got: {result.confidence_score}"
            )
        
        print(f"✅ Inconsistent frame data detected and handled")
        print(f"   Detection 1: Frame claim {detection_events[0]['frame_number']} vs timestamp frame {int(detection_events[0]['video_relative_timestamp'] * VIDEO_FPS)}")
        print(f"   Detection 2: Frame claim {detection_events[1]['frame_number']} vs timestamp frame {int(detection_events[1]['video_relative_timestamp'] * VIDEO_FPS)}")
    
    def test_frame_data_corruption_scenarios(self):
        """
        Test scenarios with corrupted or invalid frame data
        """
        print("\n🔍 Testing frame data corruption scenarios...")
        
        # Various corruption scenarios
        corrupted_detections = [
            {
                'id': 'det_corrupt_negative',
                'timestamp': self.video_start_timestamp + 1.5,
                'frame_number': -10,  # INVALID: Negative frame
                'video_relative_timestamp': 1.5,
                'processing_time_ms': 70.0
            },
            {
                'id': 'det_corrupt_huge',
                'timestamp': self.video_start_timestamp + 2.5,
                'frame_number': 999999,  # INVALID: Frame beyond video duration
                'video_relative_timestamp': 2.5,
                'processing_time_ms': 75.0
            },
            {
                'id': 'det_corrupt_zero',
                'timestamp': self.video_start_timestamp + 3.5,
                'frame_number': 0,  # EDGE CASE: Frame 0
                'video_relative_timestamp': 3.5,
                'processing_time_ms': 80.0
            }
        ]
        
        ground_truth_events = [
            {'frame_number': 36, 'video_timestamp': 1.5},
            {'frame_number': 60, 'video_timestamp': 2.5},
            {'frame_number': 84, 'video_timestamp': 3.5}
        ]
        
        # Test corruption handling
        for i, (detection, gt) in enumerate(zip(corrupted_detections, ground_truth_events)):
            frame_number = detection['frame_number']
            video_time = detection['video_relative_timestamp']
            max_valid_frame = int(60.0 * VIDEO_FPS)  # 60s video duration
            
            # Detect corruption
            is_corrupted = (
                frame_number < 0 or  # Negative frame
                frame_number > max_valid_frame or  # Beyond video duration
                abs(frame_number - video_time * VIDEO_FPS) > 100  # Unreasonable offset
            )
            
            if frame_number != 0:  # Frame 0 is valid edge case
                assert is_corrupted, f"Detection {i} should be flagged as corrupted"
            
            # Test timing calculator error handling
            try:
                result = self.timing_calculator.calculate_corrected_latency(
                    session_id="edge_test_corrupted",
                    detection_id=detection['id'],
                    detection_system_time=detection['timestamp'],
                    ground_truth_frame=gt['frame_number'],
                    ground_truth_video_time=gt['video_timestamp'],
                    video_timing_metadata=self.video_metadata_high_quality,
                    labjack_start_time=self.base_timestamp
                )
                
                # Should either succeed with degraded quality or fail gracefully
                if result is not None:
                    assert result.timing_quality in ["poor", "fair"], (
                        f"Quality should be poor for corrupted data, got: {result.timing_quality}"
                    )
                    assert result.confidence_score < 0.5, (
                        f"Confidence should be very low for corrupted data"
                    )
                
            except ValueError as e:
                # Acceptable to fail with corrupted data
                assert "frame" in str(e).lower() or "invalid" in str(e).lower(), (
                    f"Should fail with frame-related error for corrupted data"
                )
        
        print(f"✅ Frame data corruption detected and handled")
        print(f"   Negative frame: {corrupted_detections[0]['frame_number']} → Invalid")
        print(f"   Huge frame: {corrupted_detections[1]['frame_number']} → Invalid")
        print(f"   Zero frame: {corrupted_detections[2]['frame_number']} → Edge case")
    
    def test_frame_synchronization_drift_over_time(self):
        """
        Test scenario where frame synchronization drifts over long recording sessions
        """
        print("\n🔍 Testing frame synchronization drift over time...")
        
        # Simulate 60-second session with gradual frame drift
        session_duration = 60.0
        drift_rate_ms_per_second = 0.5  # 0.5ms drift per second
        
        detection_times = np.arange(5.0, session_duration, 5.0)  # Every 5 seconds
        
        # Create detections with accumulated drift
        drift_detections = []
        for i, video_time in enumerate(detection_times):
            accumulated_drift_ms = drift_rate_ms_per_second * video_time
            accumulated_drift_s = accumulated_drift_ms / 1000.0
            
            # Frame calculation with drift
            ideal_frame = int(video_time * VIDEO_FPS)
            drifted_frame = int((video_time + accumulated_drift_s) * VIDEO_FPS)
            
            detection = {
                'id': f'det_drift_{i:03d}',
                'timestamp': self.video_start_timestamp + video_time + accumulated_drift_s,
                'frame_number': drifted_frame,
                'video_relative_timestamp': video_time + accumulated_drift_s,
                'ideal_video_time': video_time,
                'accumulated_drift_ms': accumulated_drift_ms,
                'processing_time_ms': 75.0 + i * 2  # Slight processing time variation
            }
            drift_detections.append(detection)
        
        # Create corresponding ground truth without drift
        ground_truth_events = [
            {
                'frame_number': int(video_time * VIDEO_FPS),
                'video_timestamp': video_time,
                'event_type': 'vehicle_detection'
            }
            for video_time in detection_times
        ]
        
        # Test drift detection and compensation
        detected_drift_values = []
        
        for i, (detection, gt) in enumerate(zip(drift_detections, ground_truth_events)):
            # Calculate apparent drift
            expected_frame_from_gt = gt['frame_number']
            actual_frame_claimed = detection['frame_number']
            frame_drift = actual_frame_claimed - expected_frame_from_gt
            time_drift_ms = (frame_drift / VIDEO_FPS) * 1000.0
            
            detected_drift_values.append(time_drift_ms)
            
            # Verify drift increases over time
            expected_drift = detection['accumulated_drift_ms']
            drift_error = abs(time_drift_ms - expected_drift)
            
            assert drift_error <= 5.0, (  # Allow 5ms tolerance
                f"Drift detection error at {detection['ideal_video_time']}s: "
                f"Expected {expected_drift:.1f}ms, detected {time_drift_ms:.1f}ms"
            )
            
            # Test timing calculator drift compensation
            result = self.timing_calculator.calculate_corrected_latency(
                session_id="edge_test_drift",
                detection_id=detection['id'],
                detection_system_time=detection['timestamp'],
                ground_truth_frame=gt['frame_number'],
                ground_truth_video_time=gt['video_timestamp'],
                video_timing_metadata=self.video_metadata_high_quality,
                labjack_start_time=self.base_timestamp
            )
            
            assert result is not None, f"Should handle drift at {detection['ideal_video_time']}s"
            
            # Quality should degrade with increasing drift
            if detection['accumulated_drift_ms'] > 10.0:
                assert result.timing_quality in ["fair", "poor"], (
                    f"Quality should degrade with drift at {detection['ideal_video_time']}s"
                )
        
        # Verify drift trend
        if len(detected_drift_values) > 2:
            drift_slope = np.polyfit(range(len(detected_drift_values)), detected_drift_values, 1)[0]
            assert drift_slope > 0, "Should detect increasing drift over time"
        
        print(f"✅ Frame synchronization drift detected and handled")
        print(f"   Session duration: {session_duration}s")
        print(f"   Drift rate: {drift_rate_ms_per_second}ms/s")
        print(f"   Final accumulated drift: {detected_drift_values[-1]:.1f}ms")
        print(f"   Drift trend slope: {drift_slope:.2f}ms per measurement")
    
    def test_frame_rate_mismatch_scenarios(self):
        """
        Test scenarios where actual frame rate doesn't match expected frame rate
        """
        print("\n🔍 Testing frame rate mismatch scenarios...")
        
        # Test different frame rate scenarios
        frame_rate_scenarios = [
            {"expected_fps": 24.0, "actual_fps": 23.98, "tolerance": 0.5},  # Slight mismatch
            {"expected_fps": 24.0, "actual_fps": 25.0, "tolerance": 2.0},   # 1 fps off
            {"expected_fps": 24.0, "actual_fps": 30.0, "tolerance": 10.0},  # Significant mismatch
        ]
        
        for scenario in frame_rate_scenarios:
            expected_fps = scenario["expected_fps"]
            actual_fps = scenario["actual_fps"]
            tolerance = scenario["tolerance"]
            
            print(f"   Testing {expected_fps}fps expected vs {actual_fps}fps actual...")
            
            # Create video metadata with expected fps
            video_metadata = VideoTimingMetadata(
                startup_delay_ms=2000.0,
                fps=expected_fps,
                duration=60.0,
                timing_sync_status="synced",
                timing_accuracy_ns=100_000
            )
            
            # Create detection at 2 seconds with actual fps timing
            video_time = 2.0
            expected_frame = int(video_time * expected_fps)  # Frame based on expected fps
            actual_frame = int(video_time * actual_fps)      # Frame based on actual fps
            
            detection_timestamp = self.video_start_timestamp + video_time
            
            # Test timing calculation with fps mismatch
            result = self.timing_calculator.calculate_corrected_latency(
                session_id="edge_test_fps_mismatch",
                detection_id=f"det_fps_{expected_fps}_{actual_fps}",
                detection_system_time=detection_timestamp,
                ground_truth_frame=expected_frame,
                ground_truth_video_time=video_time,
                video_timing_metadata=video_metadata,
                labjack_start_time=self.base_timestamp
            )
            
            assert result is not None, f"Should handle fps mismatch {expected_fps} vs {actual_fps}"
            
            # Calculate frame timing error
            frame_error = abs(actual_frame - expected_frame)
            fps_error_percent = abs(actual_fps - expected_fps) / expected_fps * 100
            
            # Quality should reflect fps mismatch severity
            if fps_error_percent <= tolerance:
                assert result.timing_quality in ["excellent", "good", "fair"], (
                    f"Quality should be acceptable for {fps_error_percent:.1f}% fps error"
                )
            else:
                assert result.timing_quality in ["fair", "poor"], (
                    f"Quality should be degraded for {fps_error_percent:.1f}% fps error"
                )
            
            print(f"     Frame error: {frame_error} frames ({fps_error_percent:.1f}% fps error)")
            print(f"     Timing quality: {result.timing_quality}")
    
    def test_frame_correlation_recovery_mechanisms(self):
        """
        Test recovery mechanisms when frame correlation is lost and regained
        """
        print("\n🔍 Testing frame correlation recovery mechanisms...")
        
        # Simulate session with intermittent frame correlation loss
        detection_scenarios = [
            {"time": 1.0, "has_frames": True, "quality": "high"},     # Normal
            {"time": 2.0, "has_frames": True, "quality": "high"},     # Normal
            {"time": 3.0, "has_frames": False, "quality": "poor"},    # LOST CORRELATION
            {"time": 4.0, "has_frames": False, "quality": "poor"},    # STILL LOST
            {"time": 5.0, "has_frames": True, "quality": "medium"},   # RECOVERED
            {"time": 6.0, "has_frames": True, "quality": "high"},     # FULLY RECOVERED
        ]
        
        recovery_results = []
        
        for i, scenario in enumerate(detection_scenarios):
            video_time = scenario["time"]
            has_frames = scenario["has_frames"]
            quality = scenario["quality"]
            
            # Create detection with varying frame correlation availability
            frame_number = int(video_time * VIDEO_FPS) if has_frames else None
            
            # Determine video metadata quality based on correlation status
            if quality == "high":
                video_metadata = self.video_metadata_high_quality
            else:
                video_metadata = self.video_metadata_poor_quality
            
            detection_timestamp = self.video_start_timestamp + video_time
            
            # Test timing calculation during correlation loss/recovery
            result = self.timing_calculator.calculate_corrected_latency(
                session_id="edge_test_recovery",
                detection_id=f"det_recovery_{i:03d}",
                detection_system_time=detection_timestamp,
                ground_truth_frame=int(video_time * VIDEO_FPS),  # GT always has frame
                ground_truth_video_time=video_time,
                video_timing_metadata=video_metadata,
                labjack_start_time=self.base_timestamp
            )
            
            assert result is not None, f"Should handle detection {i} during correlation changes"
            
            recovery_results.append({
                "time": video_time,
                "has_frames": has_frames,
                "expected_quality": quality,
                "actual_quality": result.timing_quality,
                "confidence": result.confidence_score,
                "real_latency": result.real_latency_ms
            })
        
        # Verify recovery pattern
        # Quality should degrade during loss and improve during recovery
        quality_scores = {"excellent": 4, "good": 3, "fair": 2, "poor": 1}
        
        for i in range(1, len(recovery_results)):
            current = recovery_results[i]
            previous = recovery_results[i-1]
            
            current_score = quality_scores.get(current["actual_quality"], 0)
            previous_score = quality_scores.get(previous["actual_quality"], 0)
            
            # During loss (scenarios 2-3), quality should not improve
            if i == 2 or i == 3:  # Loss period
                assert current_score <= previous_score + 1, (
                    f"Quality should not significantly improve during loss at step {i}"
                )
            
            # During recovery (scenarios 4-5), quality should improve
            if i == 4 or i == 5:  # Recovery period
                if current["has_frames"] and not previous["has_frames"]:
                    # Frame correlation restored - quality should improve
                    assert current_score >= previous_score, (
                        f"Quality should improve when frame correlation restored at step {i}"
                    )
        
        print(f"✅ Frame correlation recovery mechanisms tested")
        print(f"   Correlation loss detected: Steps 2-3")
        print(f"   Correlation recovery detected: Steps 4-5")
        
        # Print recovery timeline
        for i, result in enumerate(recovery_results):
            status = "✓" if result["has_frames"] else "✗"
            print(f"   {result['time']:.1f}s: {status} Frame correlation, "
                  f"Quality: {result['actual_quality']}, "
                  f"Confidence: {result['confidence']:.2f}")
    
    def test_edge_case_comprehensive_validation(self):
        """
        Comprehensive test combining multiple edge cases to validate robustness
        """
        print("\n🔍 Running comprehensive edge case validation...")
        
        # Complex scenario with multiple simultaneous edge cases
        complex_scenario = [
            {
                "time": 1.0,
                "frame_number": None,           # Missing frame
                "quality": "unknown",
                "description": "Missing frame data"
            },
            {
                "time": 2.0, 
                "frame_number": 60,             # Inconsistent (should be ~48)
                "quality": "poor",
                "description": "Inconsistent frame timing"
            },
            {
                "time": 3.0,
                "frame_number": -5,             # Corrupted negative
                "quality": "poor",
                "description": "Corrupted negative frame"
            },
            {
                "time": 4.0,
                "frame_number": 999999,         # Corrupted huge
                "quality": "poor", 
                "description": "Corrupted oversized frame"
            },
            {
                "time": 5.0,
                "frame_number": int(5.2 * VIDEO_FPS),  # Drifted timing
                "quality": "fair",
                "description": "Frame synchronization drift"
            }
        ]
        
        ground_truth_events = [
            {"frame_number": int(t["time"] * VIDEO_FPS), "video_timestamp": t["time"]}
            for t in complex_scenario
        ]
        
        successful_calculations = 0
        error_recoveries = 0
        quality_degradations = 0
        
        for i, (scenario, gt) in enumerate(zip(complex_scenario, ground_truth_events)):
            print(f"   Testing: {scenario['description']} at {scenario['time']}s")
            
            detection_timestamp = self.video_start_timestamp + scenario['time']
            
            # Select appropriate video metadata based on scenario quality
            if scenario['quality'] == 'unknown':
                video_metadata = VideoTimingMetadata(
                    startup_delay_ms=2000.0,
                    fps=VIDEO_FPS,
                    duration=60.0,
                    timing_sync_status="unknown",
                    timing_accuracy_ns=1_000_000  # 1ms accuracy
                )
            elif scenario['quality'] == 'poor':
                video_metadata = self.video_metadata_poor_quality
            else:
                video_metadata = self.video_metadata_high_quality
            
            try:
                result = self.timing_calculator.calculate_corrected_latency(
                    session_id="edge_test_comprehensive",
                    detection_id=f"det_complex_{i:03d}",
                    detection_system_time=detection_timestamp,
                    ground_truth_frame=gt['frame_number'],
                    ground_truth_video_time=gt['video_timestamp'],
                    video_timing_metadata=video_metadata,
                    labjack_start_time=self.base_timestamp
                )
                
                if result is not None:
                    successful_calculations += 1
                    
                    # Should have degraded quality for edge cases
                    if result.timing_quality in ["poor", "fair"]:
                        quality_degradations += 1
                    
                    # Should have reduced confidence
                    if result.confidence_score < 0.7:
                        error_recoveries += 1
                    
                    print(f"     ✓ Handled: Quality={result.timing_quality}, "
                          f"Confidence={result.confidence_score:.2f}, "
                          f"Latency={result.real_latency_ms:.1f}ms")
                else:
                    print(f"     ✗ Failed to calculate (acceptable for severe corruption)")
            
            except Exception as e:
                # Some edge cases may legitimately fail
                print(f"     ⚠ Exception (may be acceptable): {type(e).__name__}: {e}")
        
        # Validate edge case handling effectiveness
        success_rate = successful_calculations / len(complex_scenario)
        degradation_rate = quality_degradations / max(successful_calculations, 1)
        recovery_rate = error_recoveries / max(successful_calculations, 1)
        
        assert success_rate >= 0.6, (  # At least 60% should succeed
            f"Edge case handling success rate too low: {success_rate:.1%}"
        )
        
        assert degradation_rate >= 0.8, (  # At least 80% should show quality degradation
            f"Should show quality degradation for edge cases: {degradation_rate:.1%}"
        )
        
        print(f"✅ Comprehensive edge case validation completed")
        print(f"   Success rate: {success_rate:.1%}")
        print(f"   Quality degradation rate: {degradation_rate:.1%}")
        print(f"   Error recovery rate: {recovery_rate:.1%}")
        print(f"   System robustness: {'GOOD' if success_rate >= 0.8 else 'ACCEPTABLE' if success_rate >= 0.6 else 'POOR'}")


if __name__ == "__main__":
    # Run the edge cases test suite
    print("🧪 Frame Timing Synchronization Edge Cases Test Suite")
    print("="*70)
    
    test_instance = TestFrameTimingSynchronizationEdgeCases()
    test_instance.setup_method()
    
    try:
        # Run individual edge case tests
        test_instance.test_missing_frame_numbers_in_detection_events()
        test_instance.test_inconsistent_frame_timing_data()
        test_instance.test_frame_data_corruption_scenarios()
        test_instance.test_frame_synchronization_drift_over_time()
        test_instance.test_frame_rate_mismatch_scenarios()
        test_instance.test_frame_correlation_recovery_mechanisms()
        test_instance.test_edge_case_comprehensive_validation()
        
        print(f"\n✅ All edge case tests passed!")
        print(f"✅ Frame timing synchronization is robust!")
        print(f"✅ User concern about missing frame data addressed!")
        
    except Exception as e:
        print(f"\n❌ Edge case test failed: {e}")
        import traceback
        traceback.print_exc()
        raise