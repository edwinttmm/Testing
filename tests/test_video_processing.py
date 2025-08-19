"""
Comprehensive TDD Tests for Video Processing Platform
Tests all critical functionality identified in the analysis
"""
import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from io import BytesIO

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Import after setting up test database
import sys
backend_path = Path(__file__).parent.parent / "ai-model-validation-platform" / "backend"
sys.path.append(str(backend_path))

from models import Base, Video, Project, GroundTruthObject
from schemas_enhanced import ProcessingStatusEnum, VideoStatusEnum, VideoResponse

# Create test database
Base.metadata.create_all(bind=engine)

class TestDatabaseSchema:
    """Test database schema and migrations"""
    
    def test_video_table_has_processing_status(self):
        """Test that videos table has processing_status column"""
        from sqlalchemy import inspect
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('videos')]
        assert 'processing_status' in columns, "processing_status column missing from videos table"
    
    def test_video_table_has_ground_truth_generated(self):
        """Test that videos table has ground_truth_generated column"""
        from sqlalchemy import inspect
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('videos')]
        assert 'ground_truth_generated' in columns, "ground_truth_generated column missing from videos table"
    
    def test_ground_truth_table_has_required_columns(self):
        """Test that ground_truth_objects table has all required columns"""
        from sqlalchemy import inspect
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('ground_truth_objects')]
        
        required_columns = ['id', 'video_id', 'timestamp', 'class_label', 'x', 'y', 'width', 'height']
        for col in required_columns:
            assert col in columns, f"{col} column missing from ground_truth_objects table"

class TestVideoModel:
    """Test Video model functionality"""
    
    def setup_method(self):
        """Setup test data"""
        self.db = TestingSessionLocal()
        
        # Create test project
        self.test_project = Project(
            id="test-project-id",
            name="Test Project",
            camera_model="Test Camera",
            camera_view="Front-facing",
            signal_type="GPIO"
        )
        self.db.add(self.test_project)
        self.db.commit()
    
    def teardown_method(self):
        """Cleanup test data"""
        self.db.query(Video).delete()
        self.db.query(Project).delete()
        self.db.commit()
        self.db.close()
    
    def test_create_video_with_processing_status(self):
        """Test creating video with processing_status"""
        video = Video(
            id="test-video-id",
            filename="test.mp4",
            file_path="/test/path.mp4",
            file_size=1000,
            status="uploaded",
            processing_status="pending",
            ground_truth_generated=False,
            project_id=self.test_project.id
        )
        
        self.db.add(video)
        self.db.commit()
        
        # Retrieve and verify
        saved_video = self.db.query(Video).filter(Video.id == "test-video-id").first()
        assert saved_video is not None
        assert saved_video.processing_status == "pending"
        assert saved_video.ground_truth_generated is False
    
    def test_update_processing_status(self):
        """Test updating video processing status"""
        video = Video(
            id="test-video-update",
            filename="test.mp4",
            file_path="/test/path.mp4",
            status="uploaded",
            processing_status="pending",
            project_id=self.test_project.id
        )
        
        self.db.add(video)
        self.db.commit()
        
        # Update status
        video.processing_status = "processing"
        self.db.commit()
        
        # Verify update
        updated_video = self.db.query(Video).filter(Video.id == "test-video-update").first()
        assert updated_video.processing_status == "processing"

class TestVideoProcessingWorkflow:
    """Test video processing workflow"""
    
    def setup_method(self):
        """Setup test environment"""
        self.db = TestingSessionLocal()
        
        # Create test project
        self.test_project = Project(
            id="workflow-project",
            name="Workflow Test Project",
            camera_model="Test Camera",
            camera_view="Front-facing",
            signal_type="GPIO"
        )
        self.db.add(self.test_project)
        self.db.commit()
        
        # Create test video
        self.test_video = Video(
            id="workflow-video",
            filename="workflow_test.mp4",
            file_path="/test/workflow.mp4",
            status="uploaded",
            processing_status="pending",
            ground_truth_generated=False,
            project_id=self.test_project.id
        )
        self.db.add(self.test_video)
        self.db.commit()
    
    def teardown_method(self):
        """Cleanup"""
        self.db.query(Video).delete()
        self.db.query(Project).delete()
        self.db.commit()
        self.db.close()
    
    @pytest.mark.asyncio
    async def test_processing_status_update(self):
        """Test processing status update workflow"""
        from services.video_processing_workflow import VideoProcessingWorkflow
        
        # Mock socketio
        mock_socketio = Mock()
        workflow = VideoProcessingWorkflow(self.db, mock_socketio)
        
        # Test status update
        result = await workflow.update_processing_status(
            "workflow-video",
            ProcessingStatusEnum.PROCESSING,
            progress=50.0,
            message="Processing in progress"
        )
        
        assert result is True
        
        # Verify database update
        updated_video = self.db.query(Video).filter(Video.id == "workflow-video").first()
        assert updated_video.processing_status == "processing"
    
    @pytest.mark.asyncio
    async def test_processing_completion(self):
        """Test processing completion workflow"""
        from services.video_processing_workflow import VideoProcessingWorkflow
        
        workflow = VideoProcessingWorkflow(self.db)
        
        # Test completion
        result = await workflow.update_processing_status(
            "workflow-video",
            ProcessingStatusEnum.COMPLETED,
            progress=100.0,
            message="Processing completed"
        )
        
        assert result is True
        
        # Verify completion status
        completed_video = self.db.query(Video).filter(Video.id == "workflow-video").first()
        assert completed_video.processing_status == "completed"
        assert completed_video.ground_truth_generated is True
        assert completed_video.status == "completed"

class TestAPIEndpoints:
    """Test API endpoints"""
    
    def setup_method(self):
        """Setup test client"""
        # Mock the database dependency
        def override_get_db():
            try:
                db = TestingSessionLocal()
                yield db
            finally:
                db.close()
        
        # Import and setup app
        from main import app
        from database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        self.client = TestClient(app)
        
        # Setup test data
        db = TestingSessionLocal()
        test_project = Project(
            id="api-test-project",
            name="API Test Project",
            camera_model="Test Camera",
            camera_view="Front-facing",
            signal_type="GPIO"
        )
        db.add(test_project)
        db.commit()
        db.close()
    
    def teardown_method(self):
        """Cleanup"""
        db = TestingSessionLocal()
        db.query(Video).delete()
        db.query(Project).delete()
        db.commit()
        db.close()
    
    def test_video_upload_endpoint(self):
        """Test video upload endpoint"""
        # Create test file
        test_file_content = b"fake video content for testing"
        
        response = self.client.post(
            "/upload-video/",
            files={"file": ("test.mp4", BytesIO(test_file_content), "video/mp4")},
            data={"project_id": "api-test-project"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "video_id" in data
    
    def test_get_videos_endpoint(self):
        """Test get videos endpoint"""
        response = self.client.get("/videos/")
        assert response.status_code == 200
        
        videos = response.json()
        assert isinstance(videos, list)

class TestRealTimeNotifications:
    """Test real-time notification system"""
    
    @pytest.mark.asyncio
    async def test_socketio_notification(self):
        """Test Socket.IO notification sending"""
        from services.video_processing_workflow import VideoProcessingWorkflow
        from schemas_enhanced import RealTimeNotification
        
        # Mock socketio
        mock_socketio = Mock()
        mock_socketio.emit = Mock()
        
        # Setup database
        db = TestingSessionLocal()
        test_project = Project(
            id="notification-project",
            name="Notification Test",
            camera_model="Test Camera",
            camera_view="Front-facing",
            signal_type="GPIO"
        )
        db.add(test_project)
        
        test_video = Video(
            id="notification-video",
            filename="notification_test.mp4",
            file_path="/test/notification.mp4",
            status="uploaded",
            processing_status="pending",
            project_id=test_project.id
        )
        db.add(test_video)
        db.commit()
        
        # Test notification
        workflow = VideoProcessingWorkflow(db, mock_socketio)
        await workflow.update_processing_status(
            "notification-video",
            ProcessingStatusEnum.PROCESSING,
            progress=25.0,
            message="Test notification"
        )
        
        # Verify socketio.emit was called
        mock_socketio.emit.assert_called_once()
        
        db.close()

class TestErrorHandling:
    """Test error handling and recovery"""
    
    def test_nonexistent_video_processing(self):
        """Test handling of nonexistent video processing"""
        from services.video_processing_workflow import VideoProcessingWorkflow
        
        db = TestingSessionLocal()
        workflow = VideoProcessingWorkflow(db)
        
        # Test with nonexistent video
        status = workflow.get_processing_status("nonexistent-video")
        assert status is None
        
        db.close()
    
    def test_database_error_handling(self):
        """Test database error handling"""
        # This would test database connection failures, constraint violations, etc.
        # Implementation depends on specific error scenarios
        pass

class TestPerformance:
    """Test performance and optimization"""
    
    def test_database_indexes(self):
        """Test that required indexes exist"""
        from sqlalchemy import inspect
        inspector = inspect(engine)
        
        # Get indexes for videos table
        indexes = inspector.get_indexes('videos')
        index_columns = set()
        for index in indexes:
            index_columns.update(index['column_names'])
        
        # Check for performance-critical indexes
        assert 'processing_status' in index_columns, "Missing index on processing_status"
        assert 'project_id' in index_columns, "Missing index on project_id"

# Integration test runner
if __name__ == "__main__":
    pytest.main([__file__, "-v"])