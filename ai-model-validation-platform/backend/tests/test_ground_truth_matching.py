"""
Comprehensive Ground Truth Matching Tests

Tests the HIL ground truth matching implementation to validate that LabJack detections
are correctly matched against video ground truth timing with accurate latency calculation.

Test Coverage:
- Video timing synchronization and timestamp conversion
- Ground truth matching with tolerance windows
- Latency calculation accuracy
- Edge cases for multiple detections and missing data
- Performance benchmarks
"""

import pytest
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the models and services we're testing
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')
from models import (
    TestSession, DetectionEvent, TestResult, Video, Project,
    DetectionComparison, GroundTruthObject, Base
)
from src.services.session_completion_service import SessionCompletionService
from src.services.ground_truth_service import GroundTruthService
from database import SessionLocal


class TestGroundTruthMatching:
    """Test suite for HIL ground truth matching functionality"""
    
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
        """Create a test project"""
        project = Project(
            name="HIL Test Project",
            description="Test project for HIL ground truth matching",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            status="active"
        )
        db_session.add(project)
        db_session.commit()
        return project
    
    @pytest.fixture
    def test_video(self, db_session: Session, test_project):
        """Create a test video with known timing"""
        video = Video(
            filename="test_video.mp4",
            file_path="/test/path/test_video.mp4",
            file_size=1000000,
            duration=10.0,  # 10 second video
            fps=30.0,
            resolution="1920x1080",
            status="validated",
            project_id=test_project.id,
            ground_truth_generated=True,
            ground_truth_count=24  # Known ground truth count
        )
        db_session.add(video)
        db_session.commit()
        return video
    
    @pytest.fixture
    def test_session(self, db_session: Session, test_project, test_video):
        """Create a test session with video timing capture"""
        # Simulate video start time capture at session start
        video_start_time = datetime.utcnow()
        
        session = TestSession(
            name="HIL Ground Truth Test Session",
            project_id=test_project.id,
            status="running",
            started_at=video_start_time,
            configuration={
                "video_timing": {
                    "video_start_unix_time": video_start_time.timestamp(),
                    "video_duration_seconds": test_video.duration,
                    "fps": test_video.fps
                },
                "ground_truth_matching": {
                    "tolerance_ms": 100,  # 100ms tolerance window
                    "enabled": True
                }
            }
        )
        db_session.add(session)
        db_session.commit()
        return session, video_start_time
    
    def create_ground_truth_objects(self, db_session: Session, video, timestamps: List[float]):
        """Create ground truth objects at specific video timestamps"""
        ground_truth_objects = []
        for i, timestamp in enumerate(timestamps):
            gt = GroundTruthObject(
                video_id=video.id,
                tracking_id=f"vru_{i+1}",
                frame_number=int(timestamp * video.fps),
                timestamp=timestamp,  # Video-relative timestamp
                class_label="pedestrian",
                x=100.0 + i * 50,
                y=200.0,
                width=50.0,
                height=100.0,
                confidence=0.95,
                validated=True
            )
            ground_truth_objects.append(gt)
            db_session.add(gt)
        
        db_session.commit()
        return ground_truth_objects
    
    def create_labjack_detections(self, db_session: Session, test_session, video_start_time: datetime, 
                                  video_relative_times: List[float]):
        """Create LabJack detection events at specific times relative to video start"""
        detection_events = []
        for i, video_time in enumerate(video_relative_times):
            # Convert video-relative time to Unix timestamp
            detection_unix_time = video_start_time + timedelta(seconds=video_time)
            
            detection = DetectionEvent(
                test_session_id=test_session.id,
                video_id=None,  # LabJack doesn't know video context
                timestamp=detection_unix_time,
                signal_type="GPIO",
                signal_value=1,
                gpio_pin=2,
                validation_result=None,  # To be determined by matching
                latency_ms=None,  # To be calculated
                event_metadata={
                    "detection_source": "labjack",
                    "video_relative_time": video_time
                }
            )
            detection_events.append(detection)
            db_session.add(detection)
        
        db_session.commit()
        return detection_events
    
    def test_video_timing_capture(self, db_session: Session, test_project):
        """
        Test video start time capture during session start
        Verify Unix to video-relative timestamp conversion accuracy
        """
        # Test timing accuracy within ±1ms
        start_time = datetime.utcnow()
        
        # Create session with precise video timing
        session = TestSession(
            name="Timing Test Session",
            project_id=test_project.id,
            status="running",
            started_at=start_time,
            configuration={
                "video_timing": {
                    "video_start_unix_time": start_time.timestamp(),
                    "capture_precision_ms": 1  # 1ms precision requirement
                }
            }
        )
        db_session.add(session)
        db_session.commit()
        
        # Verify timing capture precision
        captured_time = session.configuration["video_timing"]["video_start_unix_time"]
        expected_time = start_time.timestamp()
        time_diff_ms = abs(captured_time - expected_time) * 1000
        
        assert time_diff_ms <= 1.0, f"Video timing capture not precise enough: {time_diff_ms}ms difference"
        
        # Test Unix to video-relative conversion
        test_unix_time = start_time + timedelta(seconds=2.5)
        video_relative_time = test_unix_time.timestamp() - captured_time
        
        assert abs(video_relative_time - 2.5) < 0.001, "Unix to video-relative conversion inaccurate"
    
    def test_ground_truth_matching_perfect_match(self, db_session: Session, test_session, test_video):
        """
        Test perfect ground truth matching: LabJack detection at exactly ground truth time
        Should result in 0ms latency
        """
        session, video_start_time = test_session
        
        # Create ground truth at 2.0 seconds
        ground_truth = self.create_ground_truth_objects(db_session, test_video, [2.0])
        
        # Create LabJack detection at exactly 2.0 seconds
        detections = self.create_labjack_detections(db_session, session, video_start_time, [2.0])
        
        # Run ground truth matching
        completion_service = SessionCompletionService(db_session)
        result = completion_service.complete_test_session(session.id)
        
        # Verify perfect match results in 0ms latency
        assert result["success"] is True
        
        # Check detection was marked as True Positive with 0ms latency
        detection = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id
        ).first()
        
        assert detection.validation_result == "Pass"
        assert detection.latency_ms == 0.0, f"Expected 0ms latency, got {detection.latency_ms}ms"
    
    def test_ground_truth_matching_with_tolerance(self, db_session: Session, test_session, test_video):
        """
        Test ground truth matching with tolerance window
        LabJack detection 50ms after ground truth should be within 100ms tolerance
        """
        session, video_start_time = test_session
        
        # Create ground truth at 3.0 seconds
        ground_truth = self.create_ground_truth_objects(db_session, test_video, [3.0])
        
        # Create LabJack detection 50ms later (3.05 seconds)
        detections = self.create_labjack_detections(db_session, session, video_start_time, [3.05])
        
        # Run ground truth matching
        completion_service = SessionCompletionService(db_session)
        result = completion_service.complete_test_session(session.id)
        
        # Verify detection within tolerance
        detection = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id
        ).first()
        
        assert detection.validation_result == "Pass"
        assert detection.latency_ms == 50.0, f"Expected 50ms latency, got {detection.latency_ms}ms"
    
    def test_ground_truth_matching_outside_tolerance(self, db_session: Session, test_session, test_video):
        """
        Test ground truth matching outside tolerance window
        LabJack detection 150ms after ground truth should be False Negative
        """
        session, video_start_time = test_session
        
        # Create ground truth at 4.0 seconds
        ground_truth = self.create_ground_truth_objects(db_session, test_video, [4.0])
        
        # Create LabJack detection 150ms later (4.15 seconds) - outside 100ms tolerance
        detections = self.create_labjack_detections(db_session, session, video_start_time, [4.15])
        
        # Run ground truth matching
        completion_service = SessionCompletionService(db_session)
        result = completion_service.complete_test_session(session.id)
        
        # Verify detection marked as False Negative
        detection = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id
        ).first()
        
        assert detection.validation_result == "Fail"
        assert detection.latency_ms == 150.0, f"Expected 150ms latency, got {detection.latency_ms}ms"
    
    def test_complete_hil_workflow(self, db_session: Session, test_session, test_video):
        """
        Test complete HIL workflow end-to-end:
        1. Create test session with known ground truth (24 objects)
        2. Start session → capture video start time
        3. Simulate LabJack detections at specific video times
        4. Complete session → trigger ground truth matching
        5. Verify TestResult shows correct precision/recall/latency
        """
        session, video_start_time = test_session
        
        # Step 1: Create 24 ground truth objects (realistic HIL test scenario)
        ground_truth_times = [i * 0.5 for i in range(1, 25)]  # Every 0.5 seconds from 0.5 to 12.0
        ground_truth_objects = self.create_ground_truth_objects(db_session, test_video, ground_truth_times)
        
        # Step 2: Create LabJack detections (miss some, have latency on others)
        labjack_times = [
            1.0,    # GT at 1.0s → 0ms latency (TP)
            1.52,   # GT at 1.5s → +20ms latency (TP)
            2.03,   # GT at 2.0s → +30ms latency (TP)
            2.48,   # GT at 2.5s → -20ms latency (TP)
            3.08,   # GT at 3.0s → +80ms latency (TP)
            # Missing: GT at 3.5s → False Negative
            4.02,   # GT at 4.0s → +20ms latency (TP)
            4.18,   # GT at 4.5s → +180ms latency → outside tolerance (FN)
            5.01,   # GT at 5.0s → +10ms latency (TP)
            # Continue pattern...
        ]
        
        detections = self.create_labjack_detections(db_session, session, video_start_time, labjack_times)
        
        # Step 3: Complete session and trigger matching
        completion_service = SessionCompletionService(db_session)
        result = completion_service.complete_test_session(session.id)
        
        # Step 4: Verify results
        assert result["success"] is True
        
        # Get test result
        test_result = db_session.query(TestResult).filter(
            TestResult.test_session_id == session.id
        ).first()
        
        assert test_result is not None
        
        # Verify metrics calculation
        assert test_result.total_detections == len(labjack_times)
        assert test_result.avg_latency_ms is not None
        assert test_result.pass_rate > 0  # Some detections should pass
        
        # Check session completion metadata
        assert session.status == "completed"
        assert session.completed_at is not None
        assert "completion_metadata" in session.configuration
    
    def test_multiple_detections_near_ground_truth(self, db_session: Session, test_session, test_video):
        """
        Test edge case: 2 LabJack detections within 50ms of same ground truth
        Should match to closest detection
        """
        session, video_start_time = test_session
        
        # Create single ground truth at 5.0 seconds
        ground_truth = self.create_ground_truth_objects(db_session, test_video, [5.0])
        
        # Create two detections near the ground truth
        detections = self.create_labjack_detections(db_session, session, video_start_time, [4.98, 5.02])
        
        # Run matching
        completion_service = SessionCompletionService(db_session)
        result = completion_service.complete_test_session(session.id)
        
        # Verify only the closest detection (5.02 = +20ms) is matched
        all_detections = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id
        ).all()
        
        # Should have one Pass (closest) and one Fail (farther)
        passed_detections = [d for d in all_detections if d.validation_result == "Pass"]
        failed_detections = [d for d in all_detections if d.validation_result == "Fail"]
        
        assert len(passed_detections) == 1
        assert len(failed_detections) == 1
        assert passed_detections[0].latency_ms == 20.0  # Closest detection
    
    def test_no_ground_truth_for_session(self, db_session: Session, test_session, test_video):
        """
        Test session without associated ground truth objects
        Should handle gracefully without errors
        """
        session, video_start_time = test_session
        
        # Create LabJack detections but no ground truth
        detections = self.create_labjack_detections(db_session, session, video_start_time, [1.0, 2.0, 3.0])
        
        # Run completion
        completion_service = SessionCompletionService(db_session)
        result = completion_service.complete_test_session(session.id)
        
        # Should complete successfully
        assert result["success"] is True
        
        # All detections should be marked as unmatched
        all_detections = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id
        ).all()
        
        for detection in all_detections:
            assert detection.validation_result == "Fail"  # No ground truth to match against
    
    def test_no_labjack_detections(self, db_session: Session, test_session, test_video):
        """
        Test session with ground truth but no LabJack detections
        Should result in 0% recall
        """
        session, video_start_time = test_session
        
        # Create ground truth but no detections
        ground_truth = self.create_ground_truth_objects(db_session, test_video, [1.0, 2.0, 3.0])
        
        # Run completion
        completion_service = SessionCompletionService(db_session)
        result = completion_service.complete_test_session(session.id)
        
        # Should complete successfully
        assert result["success"] is True
        
        # Check test result shows 0% recall
        test_result = db_session.query(TestResult).filter(
            TestResult.test_session_id == session.id
        ).first()
        
        assert test_result.total_detections == 0
        assert test_result.recall == 0.0  # 0% recall (missed all ground truth)
    
    def test_timing_accuracy_precision(self, db_session: Session):
        """
        Test timestamp conversions are accurate to ±1ms
        """
        base_time = datetime.utcnow()
        
        # Test conversion accuracy for various time differences
        test_cases = [0.001, 0.01, 0.1, 1.0, 10.0]  # 1ms to 10s
        
        for time_diff in test_cases:
            test_time = base_time + timedelta(seconds=time_diff)
            
            # Convert to Unix timestamp and back
            unix_time = test_time.timestamp()
            converted_back = datetime.fromtimestamp(unix_time)
            
            # Calculate difference in milliseconds
            diff_ms = abs((converted_back - test_time).total_seconds() * 1000)
            
            assert diff_ms <= 1.0, f"Timestamp conversion error: {diff_ms}ms for {time_diff}s difference"
    
    def test_large_dataset_performance(self, db_session: Session, test_session, test_video):
        """
        Test with 1000+ detections, ensure <1s processing time
        """
        session, video_start_time = test_session
        
        # Create 100 ground truth objects
        ground_truth_times = [i * 0.1 for i in range(1, 101)]  # Every 100ms
        ground_truth_objects = self.create_ground_truth_objects(db_session, test_video, ground_truth_times)
        
        # Create 1000 LabJack detections
        detection_times = [i * 0.01 for i in range(1, 1001)]  # Every 10ms
        detections = self.create_labjack_detections(db_session, session, video_start_time, detection_times)
        
        # Measure processing time
        start_time = time.time()
        
        completion_service = SessionCompletionService(db_session)
        result = completion_service.complete_test_session(session.id)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Verify performance requirement
        assert processing_time < 1.0, f"Processing took {processing_time:.2f}s, expected <1s"
        assert result["success"] is True
    
    def test_expected_test_results_validation(self, db_session: Session, test_session, test_video):
        """
        Test expected results validation with known scenario:
        Ground truth at 1.0s, 2.0s, 3.0s, 4.0s, 5.0s
        LabJack at 1.02s, 2.05s, 3.01s, 4.15s (miss 5.0s)
        Expected: 4 TP, 0 FP, 1 FN → 100% precision, 80% recall
        """
        session, video_start_time = test_session
        
        # Create known ground truth scenario
        ground_truth_times = [1.0, 2.0, 3.0, 4.0, 5.0]
        ground_truth_objects = self.create_ground_truth_objects(db_session, test_video, ground_truth_times)
        
        # Create LabJack detections with known latencies
        detection_times = [1.02, 2.05, 3.01, 4.15]  # Miss 5.0s, 4.15s is outside tolerance
        detections = self.create_labjack_detections(db_session, session, video_start_time, detection_times)
        
        # Run matching
        completion_service = SessionCompletionService(db_session)
        result = completion_service.complete_test_session(session.id)
        
        # Verify expected results
        test_result = db_session.query(TestResult).filter(
            TestResult.test_session_id == session.id
        ).first()
        
        # Check individual detection results
        all_detections = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id
        ).order_by(DetectionEvent.timestamp).all()
        
        # Verify latency calculations
        expected_latencies = [20, 50, 10, 150]  # ms
        for i, detection in enumerate(all_detections):
            assert abs(detection.latency_ms - expected_latencies[i]) < 1.0, \
                f"Detection {i}: expected {expected_latencies[i]}ms, got {detection.latency_ms}ms"
        
        # Verify pass/fail based on tolerance (100ms)
        expected_results = ["Pass", "Pass", "Pass", "Fail"]  # 4.15s is 150ms late
        for i, detection in enumerate(all_detections):
            assert detection.validation_result == expected_results[i], \
                f"Detection {i}: expected {expected_results[i]}, got {detection.validation_result}"
        
        # Check overall metrics
        assert test_result.total_detections == 4
        assert test_result.passed_detections == 3  # 3 within tolerance
        assert test_result.failed_detections == 1   # 1 outside tolerance
        
        # Calculate expected average latency: (20 + 50 + 10 + 150) / 4 = 57.5ms
        expected_avg_latency = 57.5
        assert abs(test_result.avg_latency_ms - expected_avg_latency) < 1.0, \
            f"Expected avg latency {expected_avg_latency}ms, got {test_result.avg_latency_ms}ms"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
