"""
Session Completion Logic Tests

Tests the session completion service logic including metrics calculation,
test result generation, and database updates for HIL workflows.

Test Coverage:
- Session completion workflow validation
- Metrics calculation accuracy
- Test result generation and validation  
- Database integrity during completion
- Error handling and edge cases
"""

import pytest
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the models and services
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')
from models import (
    TestSession, DetectionEvent, TestResult, Video, Project,
    GroundTruthObject, Base
)
from src.services.session_completion_service import SessionCompletionService


class TestSessionCompletionLogic:
    """Test suite for session completion service logic"""
    
    @pytest.fixture
    def db_session(self):
        """Create a test database session"""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = TestingSessionLocal()
        yield session
        session.close()
    
    @pytest.fixture
    def completion_service(self, db_session: Session):
        """Create session completion service instance"""
        return SessionCompletionService(db_session)
    
    @pytest.fixture
    def test_project(self, db_session: Session):
        """Create a test project"""
        project = Project(
            name="Session Completion Test Project",
            description="Test project for session completion logic",
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
        """Create a test video"""
        video = Video(
            filename="completion_test.mp4",
            file_path="/test/completion_test.mp4",
            file_size=1000000,
            duration=5.0,
            fps=30.0,
            resolution="1920x1080",
            status="validated",
            project_id=test_project.id,
            ground_truth_count=5
        )
        db_session.add(video)
        db_session.commit()
        return video
    
    def create_test_session_with_timing(self, db_session: Session, test_project, test_video) -> tuple:
        """Create a test session with video timing configuration"""
        start_time = datetime.utcnow()
        
        session = TestSession(
            name="Completion Logic Test Session",
            project_id=test_project.id,
            status="running",
            started_at=start_time,
            configuration={
                "video_timing": {
                    "video_start_unix_time": start_time.timestamp(),
                    "video_id": test_video.id,
                    "fps": test_video.fps,
                    "duration_seconds": test_video.duration
                },
                "ground_truth_matching": {
                    "tolerance_ms": 100,
                    "enabled": True
                }
            }
        )
        db_session.add(session)
        db_session.commit()
        return session, start_time
    
    def create_detection_events(self, db_session: Session, session_id: str, 
                               detection_scenarios: List[Dict[str, Any]]) -> List[DetectionEvent]:
        """Create detection events based on scenarios"""
        detection_events = []
        
        for scenario in detection_scenarios:
            detection = DetectionEvent(
                test_session_id=session_id,
                timestamp=scenario["timestamp"],
                signal_type="GPIO",
                signal_value=1,
                gpio_pin=2,
                validation_result=scenario.get("validation_result"),
                latency_ms=scenario.get("latency_ms"),
                event_metadata=scenario.get("metadata", {})
            )
            detection_events.append(detection)
            db_session.add(detection)
        
        db_session.commit()
        return detection_events
    
    def test_basic_session_completion(self, db_session: Session, completion_service: SessionCompletionService,
                                    test_project, test_video):
        """Test basic session completion without errors"""
        session, start_time = self.create_test_session_with_timing(db_session, test_project, test_video)
        
        # Create some detection events
        detection_scenarios = [
            {
                "timestamp": start_time + timedelta(seconds=1),
                "validation_result": "Pass",
                "latency_ms": 25.0,
                "metadata": {"source": "test"}
            },
            {
                "timestamp": start_time + timedelta(seconds=2),
                "validation_result": "Pass", 
                "latency_ms": 45.0,
                "metadata": {"source": "test"}
            },
            {
                "timestamp": start_time + timedelta(seconds=3),
                "validation_result": "Fail",
                "latency_ms": 120.0,
                "metadata": {"source": "test"}
            }
        ]
        
        detections = self.create_detection_events(db_session, session.id, detection_scenarios)
        
        # Complete the session
        result = completion_service.complete_test_session(session.id)
        
        # Verify completion success
        assert result["success"] is True
        assert result["session_id"] == session.id
        assert result["status"] == "completed"
        assert "completed_at" in result
        assert "metrics" in result
        assert "test_result_id" in result
        
        # Verify session was updated
        completed_session = db_session.query(TestSession).filter(TestSession.id == session.id).first()
        assert completed_session.status == "completed"
        assert completed_session.completed_at is not None
        assert "completion_metadata" in completed_session.configuration
    
    def test_metrics_calculation_accuracy(self, db_session: Session, completion_service: SessionCompletionService,
                                        test_project, test_video):
        """Test accuracy of metrics calculation"""
        session, start_time = self.create_test_session_with_timing(db_session, test_project, test_video)
        
        # Create specific detection pattern for metrics testing
        detection_scenarios = [
            {"timestamp": start_time + timedelta(seconds=1), "validation_result": "Pass", "latency_ms": 10.0},
            {"timestamp": start_time + timedelta(seconds=1.5), "validation_result": "Pass", "latency_ms": 20.0},
            {"timestamp": start_time + timedelta(seconds=2), "validation_result": "Pass", "latency_ms": 30.0},
            {"timestamp": start_time + timedelta(seconds=2.5), "validation_result": "Fail", "latency_ms": 150.0},
            {"timestamp": start_time + timedelta(seconds=3), "validation_result": "Fail", "latency_ms": 200.0}
        ]
        
        detections = self.create_detection_events(db_session, session.id, detection_scenarios)
        
        # Complete session
        result = completion_service.complete_test_session(session.id)
        
        # Verify calculated metrics
        metrics = result["metrics"]
        
        # Check basic counts
        assert metrics["total_detections"] == 5
        assert metrics["passed_detections"] == 3  # First 3 passed
        assert metrics["failed_detections"] == 2   # Last 2 failed
        assert metrics["success_rate"] == 60.0     # 3/5 * 100 = 60%
        
        # Check latency statistics
        latency_stats = metrics["latency_stats"]
        expected_avg_latency = (10 + 20 + 30 + 150 + 200) / 5  # 82.0ms
        assert abs(latency_stats["average_ms"] - expected_avg_latency) < 0.1
        assert latency_stats["min_ms"] == 10.0
        assert latency_stats["max_ms"] == 200.0
        assert latency_stats["median_ms"] == 30.0  # Middle value when sorted
        
        # Check percentiles
        assert latency_stats["percentiles"]["25th"] == 20.0  # Second value in sorted list
        assert latency_stats["percentiles"]["75th"] == 150.0 # Fourth value in sorted list
    
    def test_test_result_generation(self, db_session: Session, completion_service: SessionCompletionService,
                                  test_project, test_video):
        """Test TestResult record generation and population"""
        session, start_time = self.create_test_session_with_timing(db_session, test_project, test_video)
        
        # Create detection events
        detection_scenarios = [
            {"timestamp": start_time + timedelta(seconds=1), "validation_result": "Pass", "latency_ms": 50.0},
            {"timestamp": start_time + timedelta(seconds=2), "validation_result": "Pass", "latency_ms": 75.0}
        ]
        
        detections = self.create_detection_events(db_session, session.id, detection_scenarios)
        
        # Complete session
        result = completion_service.complete_test_session(session.id)
        
        # Verify TestResult was created
        test_result = db_session.query(TestResult).filter(
            TestResult.test_session_id == session.id
        ).first()
        
        assert test_result is not None
        assert test_result.test_session_id == session.id
        
        # Verify TestResult fields
        assert test_result.total_detections == 2
        assert test_result.passed_detections == 2
        assert test_result.failed_detections == 0
        assert test_result.pass_rate == 100.0
        
        # Verify latency fields
        assert test_result.avg_latency_ms == 62.5  # (50 + 75) / 2
        assert test_result.min_latency_ms == 50.0
        assert test_result.max_latency_ms == 75.0
        assert test_result.median_latency_ms == 62.5  # Average of two values
        
        # Verify legacy compatibility fields
        assert test_result.accuracy == 1.0  # 100% success rate
        assert test_result.precision == 1.0
        assert test_result.recall == 1.0
        assert test_result.true_positives == 2
        assert test_result.false_positives == 0
        
        # Verify validation type
        assert test_result.validation_type == "labjack_timing"
    
    def test_session_metadata_update(self, db_session: Session, completion_service: SessionCompletionService,
                                   test_project, test_video):
        """Test session metadata gets properly updated during completion"""
        session, start_time = self.create_test_session_with_timing(db_session, test_project, test_video)
        
        # Add some initial configuration
        session.configuration["initial_config"] = {"test": True}
        db_session.commit()
        
        # Create detection events
        detection_scenarios = [
            {"timestamp": start_time + timedelta(seconds=1), "validation_result": "Pass", "latency_ms": 30.0}
        ]
        
        detections = self.create_detection_events(db_session, session.id, detection_scenarios)
        
        # Complete session
        result = completion_service.complete_test_session(session.id)
        
        # Verify metadata was preserved and updated
        updated_session = db_session.query(TestSession).filter(TestSession.id == session.id).first()
        
        # Check original config preserved
        assert "initial_config" in updated_session.configuration
        assert updated_session.configuration["initial_config"]["test"] is True
        
        # Check completion metadata added
        assert "completion_metadata" in updated_session.configuration
        completion_meta = updated_session.configuration["completion_metadata"]
        
        assert completion_meta["total_detections"] == 1
        assert completion_meta["success_rate"] == 100.0
        assert completion_meta["video_count"] >= 1
        assert "duration_seconds" in completion_meta
        assert "completed_at" in completion_meta
        
        # Check results summary
        assert "results_summary" in updated_session
        results_summary = updated_session.results_summary
        assert results_summary["status"] == "completed"
        assert "metrics" in results_summary
        assert "completion_time" in results_summary
    
    def test_video_count_calculation(self, db_session: Session, completion_service: SessionCompletionService,
                                   test_project):
        """Test accurate video count calculation for sessions"""
        # Create multiple videos in project
        videos = []
        for i in range(3):
            video = Video(
                filename=f"test_video_{i}.mp4",
                file_path=f"/test/test_video_{i}.mp4",
                file_size=1000000,
                duration=5.0,
                fps=30.0,
                resolution="1920x1080",
                status="validated",
                project_id=test_project.id
            )
            videos.append(video)
            db_session.add(video)
        
        db_session.commit()
        
        # Create session
        session, start_time = self.create_test_session_with_timing(db_session, test_project, videos[0])
        
        # Create detection events for different videos
        detection_scenarios = [
            {"timestamp": start_time + timedelta(seconds=1), "validation_result": "Pass", "latency_ms": 25.0}
        ]
        
        detections = self.create_detection_events(db_session, session.id, detection_scenarios)
        
        # Set video_id on one detection to test video counting
        detections[0].video_id = videos[1].id
        db_session.commit()
        
        # Complete session
        result = completion_service.complete_test_session(session.id)
        
        # Verify video count is accurate
        metrics = result["metrics"]
        assert metrics["video_count"] >= 3  # Should count all project videos
    
    def test_session_duration_calculation(self, db_session: Session, completion_service: SessionCompletionService,
                                        test_project, test_video):
        """Test accurate session duration calculation"""
        # Create session with specific timing
        start_time = datetime.utcnow()
        
        session = TestSession(
            name="Duration Test Session",
            project_id=test_project.id,
            status="running",
            started_at=start_time,
            configuration={
                "video_timing": {
                    "video_start_unix_time": start_time.timestamp(),
                    "video_id": test_video.id
                }
            }
        )
        db_session.add(session)
        db_session.commit()
        
        # Simulate some time passing
        import time
        time.sleep(0.1)  # 100ms delay
        
        # Complete session
        result = completion_service.complete_test_session(session.id)
        
        # Verify duration calculation
        metrics = result["metrics"]
        assert metrics["duration_seconds"] >= 0.1  # At least 100ms
        assert metrics["duration_seconds"] < 10.0   # But reasonable
        
        # Verify session timestamps
        completed_session = db_session.query(TestSession).filter(TestSession.id == session.id).first()
        assert completed_session.started_at is not None
        assert completed_session.completed_at is not None
        assert completed_session.completed_at > completed_session.started_at
    
    def test_already_completed_session(self, db_session: Session, completion_service: SessionCompletionService,
                                     test_project, test_video):
        """Test handling of already completed sessions"""
        session, start_time = self.create_test_session_with_timing(db_session, test_project, test_video)
        
        # Complete session first time
        result1 = completion_service.complete_test_session(session.id)
        assert result1["success"] is True
        
        # Try to complete again (should handle gracefully)
        result2 = completion_service.complete_test_session(session.id)
        assert result2["success"] is True
        assert result2["message"] == "Test session already completed"
        assert result2["status"] == "completed"
    
    def test_force_completion_with_errors(self, db_session: Session, completion_service: SessionCompletionService,
                                        test_project, test_video):
        """Test forced completion when errors occur"""
        session, start_time = self.create_test_session_with_timing(db_session, test_project, test_video)
        
        # Create problematic scenario - corrupt detection data
        corrupt_detection = DetectionEvent(
            test_session_id=session.id,
            timestamp=None,  # Invalid timestamp
            signal_type="GPIO",
            signal_value=1,
            gpio_pin=2
        )
        db_session.add(corrupt_detection)
        db_session.commit()
        
        # Force completion despite errors
        result = completion_service.complete_test_session(session.id, force_completion=True)
        
        # Should complete with error status
        assert result["success"] is True
        
        # Check session status
        completed_session = db_session.query(TestSession).filter(TestSession.id == session.id).first()
        # Should be either completed or completed_with_errors
        assert completed_session.status in ["completed", "completed_with_errors"]
    
    def test_empty_session_completion(self, db_session: Session, completion_service: SessionCompletionService,
                                    test_project, test_video):
        """Test completion of session with no detection events"""
        session, start_time = self.create_test_session_with_timing(db_session, test_project, test_video)
        
        # Complete session with no detections
        result = completion_service.complete_test_session(session.id)
        
        # Should complete successfully
        assert result["success"] is True
        
        # Verify empty metrics
        metrics = result["metrics"]
        assert metrics["total_detections"] == 0
        assert metrics["passed_detections"] == 0
        assert metrics["failed_detections"] == 0
        assert metrics["success_rate"] == 0.0
        assert metrics["latency_stats"] == {}
        
        # Verify TestResult created with zero values
        test_result = db_session.query(TestResult).filter(
            TestResult.test_session_id == session.id
        ).first()
        
        assert test_result is not None
        assert test_result.total_detections == 0
        assert test_result.pass_rate == 0.0
        assert test_result.avg_latency_ms is None
    
    def test_completion_service_standard_deviation_calculation(self, db_session: Session, 
                                                             completion_service: SessionCompletionService,
                                                             test_project, test_video):
        """Test standard deviation calculation in latency statistics"""
        session, start_time = self.create_test_session_with_timing(db_session, test_project, test_video)
        
        # Create detection events with known latencies for std dev testing
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]  # Mean = 30, Std Dev = ~15.81
        detection_scenarios = []
        
        for i, latency in enumerate(latencies):
            detection_scenarios.append({
                "timestamp": start_time + timedelta(seconds=i+1),
                "validation_result": "Pass",
                "latency_ms": latency
            })
        
        detections = self.create_detection_events(db_session, session.id, detection_scenarios)
        
        # Complete session
        result = completion_service.complete_test_session(session.id)
        
        # Check standard deviation calculation
        latency_stats = result["metrics"]["latency_stats"]
        
        # Manual calculation: sqrt(((10-30)² + (20-30)² + (30-30)² + (40-30)² + (50-30)²) / (5-1))
        # = sqrt((400 + 100 + 0 + 100 + 400) / 4) = sqrt(250) ≈ 15.81
        expected_std_dev = 15.811388300841898  # Exact calculation
        
        assert abs(latency_stats["std_dev"] - expected_std_dev) < 0.01, \
            f"Expected std dev {expected_std_dev}, got {latency_stats['std_dev']}"
    
    def test_session_completion_status_tracking(self, db_session: Session, completion_service: SessionCompletionService,
                                              test_project, test_video):
        """Test session completion status tracking functionality"""
        session, start_time = self.create_test_session_with_timing(db_session, test_project, test_video)
        
        # Test initial status
        status = completion_service.get_session_completion_status(session.id)
        assert status["session_id"] == session.id
        assert status["status"] == "running"
        assert status["detection_events"] == 0
        assert status["completion_ready"] is False
        
        # Add detection events
        detection_scenarios = [
            {"timestamp": start_time + timedelta(seconds=1), "validation_result": "Pass", "latency_ms": 25.0}
        ]
        
        detections = self.create_detection_events(db_session, session.id, detection_scenarios)
        
        # Check status after adding detections
        status = completion_service.get_session_completion_status(session.id)
        assert status["detection_events"] == 1
        assert status["has_results"] is True
        assert status["completion_ready"] is True
        
        # Complete session
        result = completion_service.complete_test_session(session.id)
        
        # Check final status
        final_status = completion_service.get_session_completion_status(session.id)
        assert final_status["status"] == "completed"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])