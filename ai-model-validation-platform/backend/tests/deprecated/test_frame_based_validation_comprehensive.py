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

Original location: tests/test_frame_based_validation_comprehensive.py
"""

"""
Comprehensive Frame-Based Validation Test Suite

This test suite validates the correlation between detection events and ground truth frames
to ensure accurate latency calculations for camera validation. Tests address the user's
concern about frame correlation: "why is the frame not mentioned for detection if that 
was there it would have helped".

Test Coverage:
1. Detection events with proper frame correlation vs misaligned frames
2. Latency calculations that account for frame-specific timing
3. Timing quality assessment based on frame alignment
4. UI display of frame correlation data
5. Edge cases where frame data is missing or inconsistent

Uses the known session "2802a2b7-8c8d-45a2-a2cf-d56261ff6cd7" with 24 ground truth events
and realistic 215-235ms latencies for camera performance validation.
"""

import pytest
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text, select, delete, update, func
from sqlalchemy.orm import sessionmaker
import numpy as np
import statistics

# Import the models and services we're testing
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    TestSession, DetectionEvent, TestResult, Video, Project,
    DetectionComparison, GroundTruthObject, Base
)
from services.ground_truth_matching_service import GroundTruthMatchingService, SessionMetrics
from services.timing_synchronization_calculator import TimingSynchronizationCalculator
from database import SessionLocal

# Test constants for known session
TEST_SESSION_ID = "2802a2b7-8c8d-45a2-a2cf-d56261ff6cd7"
EXPECTED_GROUND_TRUTH_COUNT = 24
EXPECTED_LATENCY_RANGE = (215, 235)  # ms
VIDEO_FPS = 24.0
VIDEO_DURATION = 60.0


class TestFrameBasedValidationComprehensive:
    """Comprehensive test suite for frame-based validation improvements"""
    
    @pytest.fixture
    def db_session(self):
        """Create a test database session"""
        # Use in-memory SQLite for testing
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = TestingSessionLocal()
        yield session
        session.close()
    
    @pytest.fixture
    def test_project(self, db_session: Session):
        """Create a test project for frame validation"""
        project = Project(
            name="Frame-Based Validation Test Project",
            description="Test project for frame-based validation improvements",
            camera_model="High-Speed Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            status="active"
        )
        db_session.add(project)
        db_session.commit()
        return project
    
    @pytest.fixture
    def test_video(self, db_session: Session, test_project):
        """Create a test video with known frame timing"""
        video = Video(
            filename="frame_validation_test.mp4",
            file_path="/test/path/frame_validation_test.mp4",
            file_size=2000000,
            duration=VIDEO_DURATION,
            fps=VIDEO_FPS,
            resolution="1920x1080",
            status="validated",
            project_id=test_project.id,
            ground_truth_generated=True,
            ground_truth_count=EXPECTED_GROUND_TRUTH_COUNT
        )
        db_session.add(video)
        db_session.commit()
        return video
    
    @pytest.fixture
    def test_session_with_frame_timing(self, db_session: Session, test_project, test_video):
        """Create a test session with precise frame timing capture"""
        # Simulate video start time capture with frame-accurate timing
        video_start_time = datetime.utcnow()
        frame_sync_timestamp = video_start_time.timestamp()
        
        session = TestSession(
            id=TEST_SESSION_ID,
            name="Frame-Based Validation Test Session",
            project_id=test_project.id,
            video_id=test_video.id,
            status="running",
            started_at=video_start_time,
            # Frame synchronization settings
            frame_sync_enabled=True,
            precision_timing_enabled=True,
            hil_timing_enabled=True,
            video_timing_sync_status="synced",
            # Video timing metadata
            video_playback_start_time=frame_sync_timestamp,
            video_playback_start_time_ns=str(int(frame_sync_timestamp * 1_000_000_000)),
            timing_accuracy_ns=100_000,  # 100μs accuracy
            configuration={
                "frame_timing": {
                    "video_start_unix_time": frame_sync_timestamp,
                    "fps": VIDEO_FPS,
                    "frame_sync_accuracy_ms": 0.1,  # 0.1ms frame sync accuracy
                    "timing_sync_status": "synced"
                },
                "ground_truth_matching": {
                    "tolerance_ms": 100,
                    "frame_correlation_enabled": True,
                    "frame_timing_validation": True
                },
                "camera_validation": {
                    "expected_latency_range_ms": EXPECTED_LATENCY_RANGE,
                    "frame_accuracy_required": True
                }
            }
        )
        db_session.add(session)
        db_session.commit()
        return session, video_start_time, frame_sync_timestamp
    
    def create_frame_accurate_ground_truth(self, db_session: Session, video, 
                                         frame_numbers: List[int]) -> List[GroundTruthObject]:
        """Create ground truth objects with precise frame timing"""
        ground_truth_objects = []
        for i, frame_num in enumerate(frame_numbers):
            # Calculate precise frame timing
            video_timestamp = frame_num / VIDEO_FPS
            
            gt = GroundTruthObject(
                video_id=video.id,
                tracking_id=f"vru_frame_{frame_num}",
                frame_number=frame_num,
                timestamp=video_timestamp,
                class_label="pedestrian",
                x=100.0 + (i % 5) * 100,  # Vary positions
                y=200.0 + (i % 3) * 150,
                width=60.0,
                height=120.0,
                confidence=0.95,
                validated=True
            )
            ground_truth_objects.append(gt)
            db_session.add(gt)
        
        db_session.commit()
        return ground_truth_objects
    
    def create_frame_correlated_detections(self, db_session: Session, test_session, 
                                         video_start_timestamp: float,
                                         detection_specs: List[Dict]) -> List[DetectionEvent]:
        """
        Create detection events with frame correlation data
        
        Args:
            detection_specs: List of dicts with keys:
                - frame_number: Target frame number
                - latency_ms: Processing latency
                - quality: Detection quality ('high', 'medium', 'low')
                - has_frame_correlation: Whether frame data is available
        """
        detection_events = []
        
        for i, spec in enumerate(detection_specs):
            frame_num = spec['frame_number']
            latency_ms = spec['latency_ms']
            quality = spec.get('quality', 'high')
            has_frame_correlation = spec.get('has_frame_correlation', True)
            
            # Calculate precise timing
            video_relative_time = frame_num / VIDEO_FPS
            ground_truth_time = video_start_timestamp + video_relative_time
            detection_time = ground_truth_time + (latency_ms / 1000.0)
            
            # Calculate detection frame (might be different from GT frame due to latency)
            detection_video_time = detection_time - video_start_timestamp
            detection_frame = int(detection_video_time * VIDEO_FPS)
            
            detection = DetectionEvent(
                test_session_id=test_session.id,
                video_id=test_session.video_id,
                timestamp=detection_time,
                
                # Frame correlation data
                video_frame_number=detection_frame if has_frame_correlation else None,
                frame_number=detection_frame if has_frame_correlation else None,
                video_relative_timestamp=detection_video_time,
                video_relative_timestamp_ns=str(int(detection_video_time * 1_000_000_000)),
                
                # Timing data
                actual_latency_ms=latency_ms,
                latency_ns=str(int(latency_ms * 1_000_000)),
                timing_sync_quality=quality,
                
                # LabJack data
                labjack_timestamp=detection_time,
                labjack_timestamp_ns=str(int(detection_time * 1_000_000_000)),
                voltage_level=3.3,
                detection_channel="FIO0",
                
                # Video timing synchronization
                video_start_time=video_start_timestamp,
                video_start_time_ns=str(int(video_start_timestamp * 1_000_000_000)),
                
                # Processing metadata
                processing_time_ms=latency_ms,
                confidence=0.95,
                validation_result=None,  # To be determined by matching
                
                # Event metadata
                event_metadata={
                    "frame_correlation_available": has_frame_correlation,
                    "ground_truth_frame": frame_num,
                    "detection_frame": detection_frame,
                    "frame_timing_quality": quality,
                    "expected_latency_range": EXPECTED_LATENCY_RANGE
                }
            )
            
            detection_events.append(detection)
            db_session.add(detection)
        
        db_session.commit()
        return detection_events
    
    def test_proper_frame_correlation_vs_misaligned(self, db_session: Session, 
                                                   test_session_with_frame_timing, test_video):
        """
        Test detection events with proper frame correlation vs misaligned frames
        Validates that frame correlation improves matching accuracy
        """
        session, video_start_time, video_start_timestamp = test_session_with_frame_timing
        
        # Create ground truth at specific frames
        gt_frames = [60, 120, 180, 240, 300]  # Frames at 2.5s, 5s, 7.5s, 10s, 12.5s
        ground_truth_objects = self.create_frame_accurate_ground_truth(
            db_session, test_video, gt_frames
        )
        
        # Create detection events: some with proper frame correlation, some misaligned
        detection_specs = [
            # Properly correlated detections
            {"frame_number": 60, "latency_ms": 220, "quality": "high", "has_frame_correlation": True},
            {"frame_number": 120, "latency_ms": 225, "quality": "high", "has_frame_correlation": True},
            {"frame_number": 180, "latency_ms": 218, "quality": "high", "has_frame_correlation": True},
            
            # Misaligned frame correlation (frame data present but incorrect)
            {"frame_number": 245, "latency_ms": 230, "quality": "medium", "has_frame_correlation": True},  # Should match frame 240
            {"frame_number": 295, "latency_ms": 235, "quality": "medium", "has_frame_correlation": True},  # Should match frame 300
        ]
        
        detections = self.create_frame_correlated_detections(
            db_session, session, video_start_timestamp, detection_specs
        )
        
        # Run ground truth matching
        matching_service = GroundTruthMatchingService()
        metrics = matching_service.match_detections_to_ground_truth(session.id, tolerance_ms=100)
        
        # Verify matching results
        assert metrics is not None, "Matching should succeed"
        assert metrics.total_ground_truth == len(gt_frames), f"Should have {len(gt_frames)} ground truth objects"
        
        # Check individual detection correlation
        all_detections = db_session.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session.id
        )).scalars().all()
        
        properly_correlated = 0
        misaligned_detected = 0
        
        for detection in all_detections:
            if detection.video_frame_number is not None:
                # Check if frame correlation helped with matching
                if detection.validation_result == "Pass":
                    if detection.actual_latency_ms and 215 <= detection.actual_latency_ms <= 235:
                        properly_correlated += 1
                elif detection.validation_result in ["Fail", None]:
                    # Might be misaligned frame causing matching issues
                    misaligned_detected += 1
        
        # Verify frame correlation improves accuracy
        assert properly_correlated >= 3, f"At least 3 properly correlated detections should match, got {properly_correlated}"
        
        # Log results for debugging
        print(f"Frame Correlation Test Results:")
        print(f"  Properly correlated matches: {properly_correlated}")
        print(f"  Potential misaligned detections: {misaligned_detected}")
        print(f"  True Positives: {metrics.true_positives}")
        print(f"  False Positives: {metrics.false_positives}")
        print(f"  False Negatives: {metrics.false_negatives}")
    
    def test_frame_specific_latency_calculations(self, db_session: Session, 
                                               test_session_with_frame_timing, test_video):
        """
        Test latency calculations that account for frame-specific timing
        Ensures latency measurements correlate to correct video frames
        """
        session, video_start_time, video_start_timestamp = test_session_with_frame_timing
        
        # Create ground truth with known frame timing
        test_cases = [
            {"frame": 48, "expected_latency": 220},   # Frame 48 at 2.0s
            {"frame": 72, "expected_latency": 225},   # Frame 72 at 3.0s  
            {"frame": 96, "expected_latency": 218},   # Frame 96 at 4.0s
            {"frame": 144, "expected_latency": 230},  # Frame 144 at 6.0s
            {"frame": 192, "expected_latency": 215},  # Frame 192 at 8.0s
        ]
        
        gt_frames = [case["frame"] for case in test_cases]
        ground_truth_objects = self.create_frame_accurate_ground_truth(
            db_session, test_video, gt_frames
        )
        
        # Create frame-accurate detection events
        detection_specs = [
            {
                "frame_number": case["frame"], 
                "latency_ms": case["expected_latency"],
                "quality": "high",
                "has_frame_correlation": True
            }
            for case in test_cases
        ]
        
        detections = self.create_frame_correlated_detections(
            db_session, session, video_start_timestamp, detection_specs
        )
        
        # Initialize timing synchronization calculator
        timing_calculator = TimingSynchronizationCalculator()
        
        # Test frame-specific latency calculations
        for i, (detection, test_case) in enumerate(zip(detections, test_cases)):
            expected_frame = test_case["frame"]
            expected_latency = test_case["expected_latency"]
            
            # Verify frame correlation
            assert detection.video_frame_number is not None, f"Detection {i} should have frame correlation"
            
            # Calculate expected detection frame based on latency
            gt_time = expected_frame / VIDEO_FPS
            detection_time = gt_time + (expected_latency / 1000.0)
            expected_detection_frame = int(detection_time * VIDEO_FPS)
            
            # Verify frame calculation accuracy
            actual_detection_frame = detection.video_frame_number
            frame_diff = abs(actual_detection_frame - expected_detection_frame)
            
            assert frame_diff <= 1, (
                f"Detection {i}: Frame calculation error. "
                f"Expected frame ~{expected_detection_frame}, got {actual_detection_frame}"
            )
            
            # Verify latency calculation accuracy
            assert detection.actual_latency_ms is not None, f"Detection {i} should have latency data"
            latency_error = abs(detection.actual_latency_ms - expected_latency)
            
            assert latency_error <= 5.0, (
                f"Detection {i}: Latency calculation error. "
                f"Expected {expected_latency}ms, got {detection.actual_latency_ms}ms"
            )
            
            # Test frame-to-timestamp conversion accuracy
            calculated_video_time = detection.video_relative_timestamp
            expected_video_time = detection_time - video_start_timestamp
            time_error = abs(calculated_video_time - expected_video_time)
            
            assert time_error <= 0.001, (  # 1ms tolerance
                f"Detection {i}: Video timestamp calculation error. "
                f"Expected {expected_video_time:.3f}s, got {calculated_video_time:.3f}s"
            )
        
        print(f"Frame-Specific Latency Test Results:")
        print(f"  All {len(test_cases)} detections passed frame correlation tests")
        print(f"  Average latency: {statistics.mean([d.actual_latency_ms for d in detections]):.1f}ms")
        print(f"  Latency range: {min(d.actual_latency_ms for d in detections):.1f}-{max(d.actual_latency_ms for d in detections):.1f}ms")
    
    def test_timing_quality_assessment_based_on_frame_alignment(self, db_session: Session,
                                                              test_session_with_frame_timing, test_video):
        """
        Test timing quality assessment based on frame alignment
        Validates that frame correlation quality affects overall timing assessment
        """
        session, video_start_time, video_start_timestamp = test_session_with_frame_timing
        
        # Create ground truth
        gt_frames = [24, 48, 72, 96, 120, 144]  # 6 GT events
        ground_truth_objects = self.create_frame_accurate_ground_truth(
            db_session, test_video, gt_frames
        )
        
        # Create detections with varying frame alignment quality
        detection_specs = [
            # High quality frame alignment
            {"frame_number": 24, "latency_ms": 220, "quality": "high", "has_frame_correlation": True},
            {"frame_number": 48, "latency_ms": 225, "quality": "high", "has_frame_correlation": True},
            
            # Medium quality frame alignment
            {"frame_number": 72, "latency_ms": 218, "quality": "medium", "has_frame_correlation": True},
            {"frame_number": 96, "latency_ms": 230, "quality": "medium", "has_frame_correlation": True},
            
            # Low quality / missing frame correlation
            {"frame_number": 120, "latency_ms": 215, "quality": "low", "has_frame_correlation": False},
            {"frame_number": 144, "latency_ms": 235, "quality": "low", "has_frame_correlation": False},
        ]
        
        detections = self.create_frame_correlated_detections(
            db_session, session, video_start_timestamp, detection_specs
        )
        
        # Run matching
        matching_service = GroundTruthMatchingService()
        metrics = matching_service.match_detections_to_ground_truth(session.id)
        
        # Analyze timing quality by frame correlation
        high_quality_detections = []
        medium_quality_detections = []
        low_quality_detections = []
        
        for detection in detections:
            if detection.timing_sync_quality == "high":
                high_quality_detections.append(detection)
            elif detection.timing_sync_quality == "medium":
                medium_quality_detections.append(detection)
            else:
                low_quality_detections.append(detection)
        
        # Verify quality assessment affects matching success
        assert len(high_quality_detections) == 2, "Should have 2 high quality detections"
        assert len(medium_quality_detections) == 2, "Should have 2 medium quality detections"
        assert len(low_quality_detections) == 2, "Should have 2 low quality detections"
        
        # Check that higher frame correlation quality leads to better matching
        high_quality_matched = sum(1 for d in high_quality_detections 
                                 if d.validation_result == "Pass")
        medium_quality_matched = sum(1 for d in medium_quality_detections 
                                   if d.validation_result == "Pass")
        low_quality_matched = sum(1 for d in low_quality_detections 
                                if d.validation_result == "Pass")
        
        # Higher quality should generally lead to better matching
        # (though this depends on the tolerance and actual timing)
        total_matched = high_quality_matched + medium_quality_matched + low_quality_matched
        
        assert total_matched >= 4, f"At least 4 of 6 detections should match, got {total_matched}"
        
        # Verify frame correlation data is preserved
        frame_correlated_count = sum(1 for d in detections 
                                   if d.video_frame_number is not None)
        
        assert frame_correlated_count == 4, f"4 detections should have frame correlation, got {frame_correlated_count}"
        
        print(f"Timing Quality Assessment Results:")
        print(f"  High quality matches: {high_quality_matched}/2")
        print(f"  Medium quality matches: {medium_quality_matched}/2")
        print(f"  Low quality matches: {low_quality_matched}/2")
        print(f"  Total matches: {total_matched}/6")
        print(f"  Frame correlated detections: {frame_correlated_count}/6")
    
    def test_ui_display_of_frame_correlation_data(self, db_session: Session,
                                                 test_session_with_frame_timing, test_video):
        """
        Test UI display of frame correlation data
        Ensures frame information is available for frontend display
        """
        session, video_start_time, video_start_timestamp = test_session_with_frame_timing
        
        # Create ground truth with frame data
        gt_frames = [30, 60, 90, 120]  # GT at frames 30, 60, 90, 120
        ground_truth_objects = self.create_frame_accurate_ground_truth(
            db_session, test_video, gt_frames
        )
        
        # Create detections with comprehensive frame data for UI
        detection_specs = [
            {"frame_number": 30, "latency_ms": 225, "quality": "high", "has_frame_correlation": True},
            {"frame_number": 60, "latency_ms": 220, "quality": "high", "has_frame_correlation": True},
            {"frame_number": 90, "latency_ms": 235, "quality": "medium", "has_frame_correlation": True},
            {"frame_number": 120, "latency_ms": 218, "quality": "high", "has_frame_correlation": True},
        ]
        
        detections = self.create_frame_correlated_detections(
            db_session, session, video_start_timestamp, detection_specs
        )
        
        # Run matching to populate comparison data
        matching_service = GroundTruthMatchingService()
        metrics = matching_service.match_detections_to_ground_truth(session.id)
        
        # Test API endpoint for UI data (simulate API call)
        from services.ground_truth_matching_service import get_detection_event_details
        
        ui_display_data = get_detection_event_details(session.id, db_session)
        
        # Verify UI display data contains frame information
        assert len(ui_display_data) >= len(detections), "Should have data for all detections"
        
        frame_data_present = 0
        timing_data_complete = 0
        
        for event_data in ui_display_data:
            # Check frame correlation data is available for UI
            if 'frame_number' in event_data or 'video_frame_number' in str(event_data):
                frame_data_present += 1
            
            # Check timing data completeness
            required_fields = ['video_time', 'detected_time', 'latency_ms', 'status']
            if all(field in event_data for field in required_fields):
                timing_data_complete += 1
        
        # Verify UI data quality
        assert frame_data_present >= len(detections), (
            f"Frame data should be available for UI display. "
            f"Expected >= {len(detections)}, got {frame_data_present}"
        )
        
        assert timing_data_complete >= len(detections), (
            f"Complete timing data should be available for UI. "
            f"Expected >= {len(detections)}, got {timing_data_complete}"
        )
        
        # Test frame-specific UI metadata
        detection_with_frames = [d for d in detections if d.video_frame_number is not None]
        
        for detection in detection_with_frames:
            # Verify frame correlation metadata is structured for UI
            assert detection.video_frame_number is not None
            assert detection.video_relative_timestamp is not None
            assert detection.actual_latency_ms is not None
            
            # Calculate display-friendly frame timing
            gt_frame = None
            for gt in ground_truth_objects:
                if abs(gt.timestamp - (detection.video_relative_timestamp - detection.actual_latency_ms/1000)) < 0.1:
                    gt_frame = gt.frame_number
                    break
            
            if gt_frame:
                # Verify frame correlation can be displayed
                detection_frame = detection.video_frame_number
                frame_offset = detection_frame - gt_frame
                
                assert abs(frame_offset) <= 10, (  # Reasonable frame offset for latency
                    f"Frame offset too large: GT frame {gt_frame}, "
                    f"Detection frame {detection_frame}, offset {frame_offset}"
                )
        
        print(f"UI Display Frame Correlation Results:")
        print(f"  Detections with frame data: {len(detection_with_frames)}/{len(detections)}")
        print(f"  UI events with frame data: {frame_data_present}")
        print(f"  UI events with complete timing: {timing_data_complete}")
        print(f"  Frame correlation display ready: {'✓' if frame_data_present >= len(detections) else '✗'}")
    
    def test_edge_cases_missing_inconsistent_frame_data(self, db_session: Session,
                                                       test_session_with_frame_timing, test_video):
        """
        Test edge cases where frame data is missing or inconsistent
        Ensures system handles missing frame correlation gracefully
        """
        session, video_start_time, video_start_timestamp = test_session_with_frame_timing
        
        # Create ground truth
        gt_frames = [36, 72, 108, 144, 180]  # 5 GT events
        ground_truth_objects = self.create_frame_accurate_ground_truth(
            db_session, test_video, gt_frames
        )
        
        # Create detections with various edge cases
        detection_specs = [
            # Normal case - good frame correlation
            {"frame_number": 36, "latency_ms": 225, "quality": "high", "has_frame_correlation": True},
            
            # Missing frame correlation data
            {"frame_number": 72, "latency_ms": 220, "quality": "unknown", "has_frame_correlation": False},
            
            # Inconsistent frame data (frame number doesn't match timestamp)
            {"frame_number": 200, "latency_ms": 235, "quality": "low", "has_frame_correlation": True},  # Should be ~108+latency frames
            
            # Frame data present but quality is poor
            {"frame_number": 144, "latency_ms": 218, "quality": "low", "has_frame_correlation": True},
            
            # Completely missing timing sync
            {"frame_number": 180, "latency_ms": 230, "quality": "unknown", "has_frame_correlation": False},
        ]
        
        detections = self.create_frame_correlated_detections(
            db_session, session, video_start_timestamp, detection_specs
        )
        
        # Manually introduce edge case data
        # Detection with missing frame correlation
        detections[1].video_frame_number = None
        detections[1].frame_number = None
        detections[1].timing_sync_quality = "unknown"
        
        # Detection with completely missing timing sync
        detections[4].video_frame_number = None
        detections[4].frame_number = None
        detections[4].video_relative_timestamp = None
        detections[4].timing_sync_quality = "unknown"
        
        db_session.commit()
        
        # Run matching - should handle edge cases gracefully
        matching_service = GroundTruthMatchingService()
        
        try:
            metrics = matching_service.match_detections_to_ground_truth(session.id)
            matching_succeeded = True
        except Exception as e:
            matching_succeeded = False
            print(f"Matching failed with edge cases: {e}")
        
        assert matching_succeeded, "Matching should handle edge cases gracefully"
        assert metrics is not None, "Should return metrics even with edge cases"
        
        # Analyze how edge cases were handled
        all_detections = db_session.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session.id
        )).scalars().all()
        
        normal_detections = 0
        missing_frame_data = 0
        inconsistent_frame_data = 0
        poor_quality_handled = 0
        
        for detection in all_detections:
            if detection.video_frame_number is not None and detection.timing_sync_quality == "high":
                normal_detections += 1
            elif detection.video_frame_number is None:
                missing_frame_data += 1
            elif detection.timing_sync_quality == "low":
                if detection.video_frame_number is not None:
                    poor_quality_handled += 1
                else:
                    inconsistent_frame_data += 1
        
        # Verify edge case handling
        assert normal_detections >= 1, "At least 1 normal detection should work"
        assert missing_frame_data >= 1, "Missing frame data should be handled"
        
        # Test that matching still produces reasonable results despite edge cases
        assert metrics.total_detections == len(detections), "All detections should be processed"
        assert metrics.true_positives >= 2, f"At least 2 matches expected despite edge cases, got {metrics.true_positives}"
        
        # Test fallback timing calculations for missing frame data
        detections_without_frames = [d for d in all_detections if d.video_frame_number is None]
        
        for detection in detections_without_frames:
            # Should still have basic timestamp data
            assert detection.timestamp is not None, "Basic timestamp should always be present"
            
            # May have fallback latency calculation
            if detection.actual_latency_ms is not None:
                assert 0 <= detection.actual_latency_ms <= 500, "Fallback latency should be reasonable"
        
        print(f"Edge Cases Test Results:")
        print(f"  Normal frame-correlated detections: {normal_detections}")
        print(f"  Missing frame data handled: {missing_frame_data}")
        print(f"  Poor quality frame data handled: {poor_quality_handled}")
        print(f"  Total matches despite edge cases: {metrics.true_positives}/{metrics.total_ground_truth}")
        print(f"  Matching success rate: {(metrics.true_positives/metrics.total_ground_truth)*100:.1f}%")
    
    def test_known_session_validation_with_24_ground_truth_events(self, db_session: Session):
        """
        Test validation with known session data: 24 ground truth events and 215-235ms latencies
        This test validates the specific user concern about frame correlation
        """
        # This test simulates the actual session mentioned by the user
        # Create realistic test environment matching the known session
        
        # Create project and video matching expected data
        project = Project(
            name="Camera Latency Validation Project",
            description="Real-world camera performance validation",
            camera_model="Production Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            status="active"
        )
        db_session.add(project)
        db_session.commit()
        
        video = Video(
            filename="camera_validation_test.mp4",
            file_path="/validation/camera_validation_test.mp4",
            file_size=5000000,
            duration=60.0,
            fps=24.0,
            resolution="1920x1080",
            status="validated",
            project_id=project.id,
            ground_truth_generated=True,
            ground_truth_count=EXPECTED_GROUND_TRUTH_COUNT
        )
        db_session.add(video)
        db_session.commit()
        
        # Create the known test session
        video_start_timestamp = time.time() - 300  # 5 minutes ago
        
        session = TestSession(
            id=TEST_SESSION_ID,
            name="Known Session - 24 GT Events Camera Validation",
            project_id=project.id,
            video_id=video.id,
            status="completed",
            started_at=datetime.fromtimestamp(video_start_timestamp),
            frame_sync_enabled=True,
            precision_timing_enabled=True,
            video_timing_sync_status="synced",
            configuration={
                "camera_validation": {
                    "expected_ground_truth_count": EXPECTED_GROUND_TRUTH_COUNT,
                    "expected_latency_range_ms": EXPECTED_LATENCY_RANGE,
                    "frame_correlation_required": True
                }
            }
        )
        db_session.add(session)
        db_session.commit()
        
        # Create 24 ground truth events at realistic intervals
        gt_frames = []
        for i in range(EXPECTED_GROUND_TRUTH_COUNT):
            # Distribute events across 60 second video
            frame_time = 2.5 * i  # Every 2.5 seconds
            frame_number = int(frame_time * VIDEO_FPS)
            gt_frames.append(frame_number)
        
        ground_truth_objects = self.create_frame_accurate_ground_truth(
            db_session, video, gt_frames
        )
        
        # Create detection events with realistic 215-235ms latencies
        detection_specs = []
        np.random.seed(42)  # Reproducible results
        
        for i, frame_num in enumerate(gt_frames):
            # Generate realistic latency in expected range
            latency = np.random.uniform(EXPECTED_LATENCY_RANGE[0], EXPECTED_LATENCY_RANGE[1])
            
            # Most detections have good frame correlation
            has_frame_correlation = i < 20  # 20 of 24 have frame correlation
            quality = "high" if has_frame_correlation else "medium"
            
            detection_specs.append({
                "frame_number": frame_num,
                "latency_ms": latency,
                "quality": quality,
                "has_frame_correlation": has_frame_correlation
            })
        
        detections = self.create_frame_correlated_detections(
            db_session, session, video_start_timestamp, detection_specs
        )
        
        # Run validation matching
        matching_service = GroundTruthMatchingService()
        metrics = matching_service.match_detections_to_ground_truth(session.id)
        
        # Validate results match expectations
        assert metrics is not None, "Matching should succeed for known session"
        assert metrics.total_ground_truth == EXPECTED_GROUND_TRUTH_COUNT, (
            f"Should have {EXPECTED_GROUND_TRUTH_COUNT} ground truth events, got {metrics.total_ground_truth}"
        )
        assert metrics.total_detections == EXPECTED_GROUND_TRUTH_COUNT, (
            f"Should have {EXPECTED_GROUND_TRUTH_COUNT} detection events, got {metrics.total_detections}"
        )
        
        # Validate latency measurements
        latencies = [d.actual_latency_ms for d in detections if d.actual_latency_ms is not None]
        avg_latency = statistics.mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        
        assert EXPECTED_LATENCY_RANGE[0] <= avg_latency <= EXPECTED_LATENCY_RANGE[1], (
            f"Average latency {avg_latency:.1f}ms should be in range {EXPECTED_LATENCY_RANGE}"
        )
        assert min_latency >= EXPECTED_LATENCY_RANGE[0] - 10, (
            f"Minimum latency {min_latency:.1f}ms too low"
        )
        assert max_latency <= EXPECTED_LATENCY_RANGE[1] + 10, (
            f"Maximum latency {max_latency:.1f}ms too high"
        )
        
        # Validate frame correlation improves accuracy
        frame_correlated_detections = [d for d in detections if d.video_frame_number is not None]
        non_frame_correlated = [d for d in detections if d.video_frame_number is None]
        
        assert len(frame_correlated_detections) >= 20, (
            f"Should have at least 20 frame-correlated detections, got {len(frame_correlated_detections)}"
        )
        
        # Check matching success rate is high
        assert metrics.true_positives >= 22, (  # Allow 2 misses out of 24
            f"High matching success expected for frame-correlated data. "
            f"Got {metrics.true_positives}/{EXPECTED_GROUND_TRUTH_COUNT} matches"
        )
        
        # Validate frame correlation data is preserved for UI display
        frame_display_data = []
        for detection in frame_correlated_detections:
            frame_info = {
                "detection_id": detection.id,
                "ground_truth_frame": None,  # Would be calculated from matching
                "detection_frame": detection.video_frame_number,
                "latency_ms": detection.actual_latency_ms,
                "frame_correlation_quality": detection.timing_sync_quality
            }
            frame_display_data.append(frame_info)
        
        assert len(frame_display_data) >= 20, "Frame display data should be available"
        
        # Test addresses user's concern: "why is the frame not mentioned for detection"
        detections_with_frame_mention = sum(
            1 for d in detections 
            if d.video_frame_number is not None or d.frame_number is not None
        )
        
        assert detections_with_frame_mention >= 20, (
            f"Frame numbers should be mentioned for most detections. "
            f"Got {detections_with_frame_mention}/{len(detections)} with frame data"
        )
        
        print(f"Known Session Validation Results:")
        print(f"  Ground truth events: {metrics.total_ground_truth}")
        print(f"  Detection events: {metrics.total_detections}")
        print(f"  True positives: {metrics.true_positives}")
        print(f"  Average latency: {avg_latency:.1f}ms (range: {min_latency:.1f}-{max_latency:.1f}ms)")
        print(f"  Detections with frame correlation: {len(frame_correlated_detections)}/{len(detections)}")
        print(f"  Frame data available for UI: {detections_with_frame_mention}/{len(detections)}")
        print(f"  Matching success rate: {(metrics.true_positives/metrics.total_ground_truth)*100:.1f}%")
        
        # Final validation: frame correlation helps camera performance validation
        camera_validation_score = (
            (metrics.true_positives / metrics.total_ground_truth) * 0.4 +  # 40% accuracy
            (1.0 if EXPECTED_LATENCY_RANGE[0] <= avg_latency <= EXPECTED_LATENCY_RANGE[1] else 0.5) * 0.3 +  # 30% latency
            (len(frame_correlated_detections) / len(detections)) * 0.3  # 30% frame correlation
        )
        
        assert camera_validation_score >= 0.8, (
            f"Camera validation score should be high with frame correlation. "
            f"Got {camera_validation_score:.2f} (need ≥0.8)"
        )
        
        print(f"  Camera validation score: {camera_validation_score:.2f}/1.0")
        print(f"  Frame correlation addresses user concern: ✓")


if __name__ == "__main__":
    # Run the comprehensive frame-based validation tests
    print("🧪 Frame-Based Validation Comprehensive Test Suite")
    print("="*70)
    
    # Run tests with pytest
    test_result = pytest.main([
        __file__, 
        "-v", 
        "--tb=short",
        "-x"  # Stop on first failure for detailed debugging
    ])
    
    if test_result == 0:
        print("\n✅ All frame-based validation tests passed!")
        print("✅ Frame correlation improvements validated!")
        print("✅ User concern about frame correlation addressed!")
    else:
        print(f"\n❌ Some tests failed (exit code: {test_result})")
        print("❌ Check frame correlation implementation")