import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from main import app
from database import get_db
from database import Base
from models import Project, Video, TestSession
from config import settings

# Create a temporary database for testing
@pytest.fixture
def test_db():
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    test_database_url = f"sqlite:///{db_path}"
    
    # Create test engine
    engine = create_engine(test_database_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Override get_db dependency
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield TestingSessionLocal
    
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)
    app.dependency_overrides.clear()

@pytest.fixture
def client(test_db):
    return TestClient(app)

def test_root_endpoint(client):
    """Test the root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "AI Model Validation Platform API"}

def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_create_project_success(client):
    """Test successful project creation"""
    project_data = {
        "name": "Test Project",
        "description": "A test project",
        "cameraModel": "Test Camera",
        "cameraView": "Front-facing VRU",
        "signalType": "GPIO"
    }
    
    response = client.post("/api/projects", json=project_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["cameraModel"] == "Test Camera"  # API returns camelCase due to Field aliases
    assert data["cameraView"] == "Front-facing VRU"
    assert data["signalType"] == "GPIO"
    assert data["status"] == "Active"

def test_create_project_validation_error(client):
    """Test project creation with validation errors"""
    project_data = {
        "name": "",  # Empty name should fail
        "description": "A test project",
        "cameraModel": "Test Camera",
        "cameraView": "Front-facing VRU",
        "signalType": "GPIO"
    }
    
    response = client.post("/api/projects", json=project_data)
    assert response.status_code == 400
    assert "Project name is required" in response.json()["detail"]

def test_get_projects_empty(client):
    """Test getting projects when none exist"""
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert response.json() == []

def test_get_projects_with_data(client, test_db):
    """Test getting projects with existing data"""
    # Create a project directly in database
    db = next(test_db())
    project = Project(
        name="Test Project",
        description="Test Description",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO"
    )
    db.add(project)
    db.commit()
    db.close()
    
    response = client.get("/api/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) == 1
    assert projects[0]["name"] == "Test Project"

def test_get_project_not_found(client):
    """Test getting a non-existent project"""
    response = client.get("/api/projects/non-existent-id")
    assert response.status_code == 404
    assert "Project not found" in response.json()["detail"]

def test_dashboard_stats_empty(client):
    """Test dashboard stats with empty database"""
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    
    stats = response.json()
    assert stats["projectCount"] == 0
    assert stats["videoCount"] == 0
    assert stats["testCount"] == 0

def test_detection_event_validation_error(client):
    """Test detection event with validation errors"""
    detection_data = {
        "test_session_id": "test-session",
        "timestamp": -1,  # Negative timestamp should fail
        "confidence": 0.95,
        "class_label": "pedestrian"
    }
    
    response = client.post("/api/detection-events", json=detection_data)
    assert response.status_code == 400
    assert "Timestamp must be non-negative" in response.json()["detail"]

def test_detection_event_confidence_validation(client):
    """Test detection event with invalid confidence"""
    detection_data = {
        "test_session_id": "test-session",
        "timestamp": 1.5,
        "confidence": 1.5,  # Confidence > 1 should fail
        "class_label": "pedestrian"
    }
    
    response = client.post("/api/detection-events", json=detection_data)
    assert response.status_code == 400
    assert "Confidence must be between 0 and 1" in response.json()["detail"]

def test_video_upload_validation_error(client):
    """Test video upload with invalid file type"""
    # Create a fake file with wrong extension
    files = {"file": ("test.txt", b"fake content", "text/plain")}
    
    response = client.post("/api/projects/test-project/videos", files=files)
    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]

def test_create_test_session_validation_error(client):
    """Test test session creation with validation errors"""
    test_session_data = {
        "name": "",  # Empty name should fail
        "project_id": "test-project",
        "video_id": "test-video",
        "tolerance_ms": 100
    }
    
    response = client.post("/api/test-sessions", json=test_session_data)
    assert response.status_code == 400
    assert "Test session name is required" in response.json()["detail"]

def test_cors_headers(client):
    """Test CORS headers are properly set"""
    response = client.options("/api/projects")
    assert response.status_code == 200
    
def test_get_ground_truth_mock_response(client):
    """Test ground truth endpoint returns mock data"""
    response = client.get("/api/videos/test-video/ground-truth")
    assert response.status_code == 200
    
    data = response.json()
    assert data["video_id"] == "test-video"
    assert data["status"] == "pending"
    assert "annotations" in data

def test_get_test_results_mock_response(client):
    """Test test results endpoint returns mock data"""
    response = client.get("/api/test-sessions/test-session/results")
    assert response.status_code == 200
    
    data = response.json()
    assert data["session_id"] == "test-session"
    assert "accuracy" in data
    assert "precision" in data
    assert "recall" in data

# Configuration tests
def test_settings_validation():
    """Test that settings are properly validated"""
    assert settings.app_name == "AI Model Validation Platform"
    assert settings.max_file_size > 0
    assert len(settings.allowed_video_extensions) > 0
    assert settings.log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

if __name__ == "__main__":
    pytest.main([__file__])