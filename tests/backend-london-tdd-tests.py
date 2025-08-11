"""
London School TDD Test Suite for AI Model Validation Platform Backend

This test suite follows London School (mockist) TDD principles:
- Mock all external dependencies (database, file system, services)
- Focus on behavior verification over state assertion  
- Test object collaborations and interactions
- Use test doubles to define contracts and drive design
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from sqlalchemy.orm import Session
from fastapi import HTTPException

# Import application modules
from main import app
from models import Project, Video, TestSession, DetectionEvent
from schemas import ProjectCreate, TestSessionCreate, DetectionEvent as DetectionEventSchema
from crud import create_project, get_projects, create_test_session
from services.validation_service import ValidationService
from services.ground_truth_service import GroundTruthService


class TestProjectServiceCollaborations:
    """London School TDD tests focusing on object interactions"""
    
    def setup_method(self):
        # Mock all external dependencies - London School principle
        self.mock_db = Mock(spec=Session)
        self.mock_audit_service = Mock()
        self.mock_notification_service = Mock() 
        
        # Service under test with mocked dependencies
        self.project_service = ProjectService(
            db_session=self.mock_db,
            audit_service=self.mock_audit_service,
            notification_service=self.mock_notification_service
        )
    
    def test_create_project_coordinates_with_audit_and_notification_services(self):
        """Test how ProjectService orchestrates project creation workflow"""
        # GIVEN - Mock setup defines expected collaborations
        project_data = ProjectCreate(
            name="Test Project",
            camera_model="Test Camera", 
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        
        expected_project = Project(
            id="project-123",
            name="Test Project",
            status="Active"
        )
        
        # Mock database interactions
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock()
        self.mock_db.refresh = Mock()
        self.mock_db.refresh.return_value = expected_project
        
        # WHEN - Execute the behavior under test
        result = self.project_service.create(project_data, user_id="user-456")
        
        # THEN - Verify interactions between collaborators (London School focus)
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once() 
        self.mock_db.refresh.assert_called_once()
        
        # Verify audit service interaction
        self.mock_audit_service.log_event.assert_called_once_with(
            event_type="project_created",
            user_id="user-456", 
            project_id="project-123"
        )
        
        # Verify notification service interaction  
        self.mock_notification_service.send_notification.assert_called_once_with(
            user_id="user-456",
            message="Project 'Test Project' created successfully"
        )
        
        assert result == expected_project
    
    def test_create_project_handles_database_failure_with_proper_rollback(self):
        """Test error handling coordination between services"""
        # GIVEN - Database failure scenario
        project_data = ProjectCreate(name="Test Project", camera_model="Camera1")
        
        self.mock_db.add = Mock()
        self.mock_db.commit = Mock(side_effect=Exception("Database error"))
        self.mock_db.rollback = Mock()
        
        # WHEN - Database operation fails
        with pytest.raises(Exception, match="Database error"):
            self.project_service.create(project_data, user_id="user-123")
        
        # THEN - Verify proper error handling coordination
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.rollback.assert_called_once()
        
        # Verify no audit/notification on failure
        self.mock_audit_service.log_event.assert_not_called()
        self.mock_notification_service.send_notification.assert_not_called()


class TestVideoProcessingWorkflow:
    """Test video upload and processing coordination"""
    
    def setup_method(self):
        # Mock all external dependencies
        self.mock_db = Mock(spec=Session)
        self.mock_file_storage = Mock()
        self.mock_ground_truth_service = Mock(spec=GroundTruthService)
        self.mock_video_processor = Mock()
        
        self.video_service = VideoService(
            db_session=self.mock_db,
            file_storage=self.mock_file_storage,
            ground_truth_service=self.mock_ground_truth_service,
            video_processor=self.mock_video_processor
        )
    
    def test_upload_video_orchestrates_complete_processing_pipeline(self):
        """Test video upload coordinates with multiple services"""
        # GIVEN - Video upload scenario
        project_id = "project-123"
        file_data = b"fake video content"
        filename = "test-video.mp4"
        
        # Mock the processing pipeline responses
        self.mock_file_storage.save_file.return_value = "/uploads/test-video.mp4"
        self.mock_video_processor.extract_metadata.return_value = {
            "duration": 120.0,
            "fps": 30.0,
            "resolution": "1920x1080"
        }
        
        expected_video = Video(
            id="video-456",
            filename=filename,
            project_id=project_id,
            status="processing"
        )
        self.mock_db.refresh.return_value = expected_video
        
        # WHEN - Video upload is processed
        result = self.video_service.upload_and_process(project_id, file_data, filename)
        
        # THEN - Verify the processing pipeline coordination
        # File storage interaction
        self.mock_file_storage.save_file.assert_called_once_with(
            file_data, filename, project_id
        )
        
        # Video metadata extraction
        self.mock_video_processor.extract_metadata.assert_called_once_with(
            "/uploads/test-video.mp4"
        )
        
        # Ground truth generation triggered
        self.mock_ground_truth_service.generate_async.assert_called_once_with(
            video_id="video-456",
            file_path="/uploads/test-video.mp4"
        )
        
        # Database operations
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        
        assert result.status == "processing"


class TestValidationServiceInteractions:
    """Test AI model validation workflow coordination"""
    
    def setup_method(self):
        self.mock_db = Mock(spec=Session)
        self.mock_ground_truth_service = Mock(spec=GroundTruthService)
        self.mock_detection_matcher = Mock()
        self.mock_metrics_calculator = Mock()
        
        self.validation_service = ValidationService(
            db_session=self.mock_db,
            ground_truth_service=self.mock_ground_truth_service,
            detection_matcher=self.mock_detection_matcher,
            metrics_calculator=self.mock_metrics_calculator
        )
    
    def test_validate_detection_events_coordinates_matching_and_scoring(self):
        """Test validation workflow interactions"""
        # GIVEN - Test session with detection events
        test_session_id = "session-123"
        
        # Mock detection events from database
        mock_detections = [
            DetectionEvent(id="det-1", timestamp=10.0, confidence=0.95),
            DetectionEvent(id="det-2", timestamp=20.0, confidence=0.87)
        ]
        
        # Mock ground truth data
        mock_ground_truth = [
            {"id": "gt-1", "timestamp": 10.1, "class_label": "person"},
            {"id": "gt-2", "timestamp": 19.9, "class_label": "vehicle"}
        ]
        
        self.mock_db.query.return_value.filter.return_value.all.return_value = mock_detections
        self.mock_ground_truth_service.get_ground_truth.return_value = mock_ground_truth
        
        # Mock matching and metrics calculation
        self.mock_detection_matcher.match_detections.return_value = [
            {"detection_id": "det-1", "ground_truth_id": "gt-1", "match_type": "TP"},
            {"detection_id": "det-2", "ground_truth_id": None, "match_type": "FP"}
        ]
        
        self.mock_metrics_calculator.calculate_metrics.return_value = {
            "precision": 0.5,
            "recall": 0.5,
            "f1_score": 0.5,
            "accuracy": 0.75
        }
        
        # WHEN - Validation is performed
        result = self.validation_service.validate_session(test_session_id)
        
        # THEN - Verify service coordination
        # Data retrieval interactions
        self.mock_db.query.assert_called()
        self.mock_ground_truth_service.get_ground_truth.assert_called_once()
        
        # Detection matching interaction
        self.mock_detection_matcher.match_detections.assert_called_once_with(
            detections=mock_detections,
            ground_truth=mock_ground_truth,
            tolerance_ms=100  # default tolerance
        )
        
        # Metrics calculation interaction
        self.mock_metrics_calculator.calculate_metrics.assert_called_once()
        
        assert result["accuracy"] == 0.75


class TestAPIEndpointCollaborations:
    """Test FastAPI endpoint interactions with services"""
    
    def setup_method(self):
        # Mock all service dependencies
        self.mock_project_service = Mock()
        self.mock_video_service = Mock()
        self.mock_validation_service = Mock()
        
        # Dependency injection mocks
        self.mock_get_db = Mock()
        
    @patch('main.get_db')
    @patch('main.create_project')
    def test_create_project_endpoint_coordinates_validation_and_creation(
        self, mock_create_project, mock_get_db
    ):
        """Test API endpoint behavior coordination"""
        # GIVEN - API request data
        project_data = {
            "name": "Test Project",
            "cameraModel": "Test Camera",
            "cameraView": "Front-facing VRU", 
            "signalType": "GPIO"
        }
        
        expected_response = {
            "id": "project-123",
            "name": "Test Project",
            "status": "Active"
        }
        
        # Mock database session
        mock_db_session = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db_session
        
        # Mock CRUD operation
        mock_create_project.return_value = expected_response
        
        # WHEN - API endpoint is called
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.post("/api/projects", json=project_data)
        
        # THEN - Verify endpoint coordination
        assert response.status_code == 200
        
        # Verify CRUD function called with correct parameters
        mock_create_project.assert_called_once_with(
            db=mock_db_session,
            project=pytest.Any,  # ProjectCreate instance
            user_id="anonymous"
        )
        
        response_data = response.json()
        assert response_data["name"] == "Test Project"


# ============================================================================
# SERVICE CLASSES (to be implemented based on test specifications)
# ============================================================================

class ProjectService:
    """Project service following London School TDD design"""
    
    def __init__(self, db_session, audit_service, notification_service):
        self.db = db_session
        self.audit_service = audit_service
        self.notification_service = notification_service
    
    def create(self, project_data: ProjectCreate, user_id: str) -> Project:
        """Create project with proper service coordination"""
        try:
            # Create project entity
            project = Project(**project_data.dict())
            
            # Database operations
            self.db.add(project)
            self.db.commit()
            self.db.refresh(project)
            
            # Coordinate with other services
            self.audit_service.log_event(
                event_type="project_created",
                user_id=user_id,
                project_id=project.id
            )
            
            self.notification_service.send_notification(
                user_id=user_id,
                message=f"Project '{project.name}' created successfully"
            )
            
            return project
            
        except Exception as e:
            self.db.rollback()
            raise e


class VideoService:
    """Video service with processing pipeline coordination"""
    
    def __init__(self, db_session, file_storage, ground_truth_service, video_processor):
        self.db = db_session
        self.file_storage = file_storage
        self.ground_truth_service = ground_truth_service
        self.video_processor = video_processor
    
    def upload_and_process(self, project_id: str, file_data: bytes, filename: str) -> Video:
        """Upload video and coordinate processing pipeline"""
        # Save file
        file_path = self.file_storage.save_file(file_data, filename, project_id)
        
        # Extract metadata
        metadata = self.video_processor.extract_metadata(file_path)
        
        # Create video record
        video = Video(
            filename=filename,
            project_id=project_id,
            file_path=file_path,
            duration=metadata["duration"],
            fps=metadata["fps"],
            resolution=metadata["resolution"],
            status="processing"
        )
        
        self.db.add(video)
        self.db.commit()
        self.db.refresh(video)
        
        # Trigger async ground truth generation
        self.ground_truth_service.generate_async(
            video_id=video.id,
            file_path=file_path
        )
        
        return video


class ValidationService:
    """Validation service coordinating AI model evaluation"""
    
    def __init__(self, db_session, ground_truth_service, detection_matcher, metrics_calculator):
        self.db = db_session
        self.ground_truth_service = ground_truth_service
        self.detection_matcher = detection_matcher
        self.metrics_calculator = metrics_calculator
    
    def validate_session(self, test_session_id: str) -> dict:
        """Validate test session by coordinating multiple services"""
        # Get detection events
        detections = self.db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == test_session_id
        ).all()
        
        # Get ground truth data
        ground_truth = self.ground_truth_service.get_ground_truth(test_session_id)
        
        # Match detections to ground truth
        matches = self.detection_matcher.match_detections(
            detections=detections,
            ground_truth=ground_truth,
            tolerance_ms=100
        )
        
        # Calculate validation metrics
        metrics = self.metrics_calculator.calculate_metrics(matches)
        
        return metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])