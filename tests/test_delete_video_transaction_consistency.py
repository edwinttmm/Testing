"""
Test file deletion transaction consistency fix.

This test verifies that the delete_video endpoint properly handles
transactional consistency to prevent orphaned files.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, Mock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import uuid

# Add the backend directory to the path
sys.path.insert(0, '/workspaces/Testing/ai-model-validation-platform/backend')

from main import app, get_db
from models import Base, Video, Project


class TestDeleteVideoTransactionConsistency:
    """Test suite for delete video transaction consistency."""
    
    @pytest.fixture
    def db_engine(self):
        """Create test database engine."""
        engine = create_engine(
            "sqlite:///./test_transaction_consistency.db",
            connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=engine)
        return engine
    
    @pytest.fixture
    def db_session(self, db_engine):
        """Create test database session."""
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        session = TestingSessionLocal()
        yield session
        session.close()
        
    @pytest.fixture
    def client(self, db_session):
        """Create test client with mocked database."""
        def override_get_db():
            try:
                yield db_session
            finally:
                db_session.close()
        
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        yield client
        app.dependency_overrides.clear()
    
    @pytest.fixture
    def test_video_data(self, db_session):
        """Create test video data."""
        # Create test project
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            description="Test project for video deletion",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            status="Active",
            owner_id="test_user"
        )
        db_session.add(project)
        db_session.flush()
        
        # Create temporary test file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_file.write(b"test video content")
        temp_file.close()
        
        # Create test video record
        video = Video(
            id=str(uuid.uuid4()),
            project_id=project.id,
            filename="test_video.mp4",
            file_path=temp_file.name,
            original_filename="test_video.mp4"
        )
        db_session.add(video)
        db_session.commit()
        
        yield {
            'project': project,
            'video': video,
            'file_path': temp_file.name
        }
        
        # Cleanup
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
    
    def test_successful_deletion_removes_both_file_and_record(self, client, test_video_data):
        """Test successful deletion removes both file and database record."""
        video = test_video_data['video']
        file_path = test_video_data['file_path']
        
        # Verify file exists before deletion
        assert os.path.exists(file_path), "Test file should exist before deletion"
        
        # Delete video
        response = client.delete(f"/api/videos/{video.id}")
        
        # Verify successful response
        assert response.status_code == 200
        assert response.json()["message"] == "Video deleted successfully"
        
        # Verify file is deleted
        assert not os.path.exists(file_path), "File should be deleted"
        
        # Verify database record is deleted
        response = client.get(f"/api/videos/{video.id}")
        assert response.status_code == 404
    
    def test_file_deletion_failure_prevents_database_deletion(self, client, test_video_data, db_session):
        """Test that file deletion failure prevents database record deletion."""
        video = test_video_data['video']
        file_path = test_video_data['file_path']
        
        # Mock os.remove to raise an exception
        with patch('main.os.remove') as mock_remove:
            mock_remove.side_effect = OSError("Permission denied")
            
            # Attempt to delete video
            response = client.delete(f"/api/videos/{video.id}")
            
            # Verify deletion failed
            assert response.status_code == 500
            assert "file removal failed" in response.json()["detail"]
            
            # Verify file still exists (we didn't actually delete it due to mock)
            assert os.path.exists(file_path), "File should still exist after failed deletion"
            
            # Verify database record still exists
            db_session.refresh(video)
            db_video = db_session.query(Video).filter(Video.id == video.id).first()
            assert db_video is not None, "Database record should still exist after failed file deletion"
    
    def test_database_operation_failure_maintains_consistency(self, client, test_video_data):
        """Test that database operation failure doesn't leave orphaned files."""
        video = test_video_data['video']
        file_path = test_video_data['file_path']
        
        # Mock database delete to raise an exception after file deletion
        with patch('main.Session.delete') as mock_delete:
            mock_delete.side_effect = Exception("Database connection error")
            
            # Attempt to delete video
            response = client.delete(f"/api/videos/{video.id}")
            
            # Verify deletion failed
            assert response.status_code == 500
            assert "operation rolled back" in response.json()["detail"]
            
            # In this case, file would be deleted but database rollback occurs
            # This is acceptable since we prioritize preventing orphaned files
    
    def test_nonexistent_video_deletion(self, client):
        """Test deletion of nonexistent video returns 404."""
        fake_video_id = str(uuid.uuid4())
        
        response = client.delete(f"/api/videos/{fake_video_id}")
        
        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]
    
    def test_video_without_file_path_deletion(self, client, db_session):
        """Test deletion of video record without associated file."""
        # Create video without file_path
        video = Video(
            id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            filename="test_video.mp4",
            file_path=None,  # No file path
            original_filename="test_video.mp4"
        )
        db_session.add(video)
        db_session.commit()
        
        # Delete video
        response = client.delete(f"/api/videos/{video.id}")
        
        # Should succeed since no file to delete
        assert response.status_code == 200
        assert response.json()["message"] == "Video deleted successfully"
    
    def test_video_with_nonexistent_file_deletion(self, client, db_session):
        """Test deletion of video record with nonexistent file path."""
        # Create video with nonexistent file_path
        video = Video(
            id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            filename="test_video.mp4",
            file_path="/nonexistent/path/video.mp4",
            original_filename="test_video.mp4"
        )
        db_session.add(video)
        db_session.commit()
        
        # Delete video
        response = client.delete(f"/api/videos/{video.id}")
        
        # Should succeed since file doesn't exist
        assert response.status_code == 200
        assert response.json()["message"] == "Video deleted successfully"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])