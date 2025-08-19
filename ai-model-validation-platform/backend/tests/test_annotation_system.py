import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os
import uuid
from datetime import datetime

from main import app
from database import Base, get_db
from models_annotation import Annotation, AnnotationSession, VideoProjectLink
from models import Project, Video

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_annotation.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture
def test_db():
    """Create test database session"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def sample_project(test_db):
    """Create sample project for testing"""
    project = Project(
        id=str(uuid.uuid4()),
        name="Test Project",
        description="Test project for annotation system",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO",
        status="Active"
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)
    return project

@pytest.fixture
def sample_video(test_db, sample_project):
    """Create sample video for testing"""
    video = Video(
        id=str(uuid.uuid4()),
        filename="test_video.mp4",
        file_path="/test/path/test_video.mp4",
        file_size=1024000,
        duration=60.0,
        fps=30.0,
        resolution="1920x1080",
        project_id=sample_project.id
    )
    test_db.add(video)
    test_db.commit()
    test_db.refresh(video)
    return video

class TestAnnotationCRUD:
    """Test annotation CRUD operations"""
    
    def test_create_annotation(self, sample_video):
        """Test creating a new annotation"""
        annotation_data = {
            "videoId": sample_video.id,
            "detectionId": "DET_PED_0001",
            "frameNumber": 100,
            "timestamp": 3.33,
            "vruType": "pedestrian",
            "boundingBox": {"x": 100, "y": 150, "width": 80, "height": 120},
            "occluded": False,
            "truncated": False,
            "difficult": False,
            "validated": False
        }
        
        response = client.post(f"/api/videos/{sample_video.id}/annotations", json=annotation_data)
        assert response.status_code == 200
        
        result = response.json()
        assert result["videoId"] == sample_video.id
        assert result["detectionId"] == "DET_PED_0001"
        assert result["frameNumber"] == 100
        assert result["vruType"] == "pedestrian"
        assert "id" in result
        assert "createdAt" in result
    
    def test_get_annotations_for_video(self, sample_video, test_db):
        """Test retrieving annotations for a video"""
        # Create test annotations
        annotation1 = Annotation(
            id=str(uuid.uuid4()),
            video_id=sample_video.id,
            detection_id="DET_PED_0001",
            frame_number=100,
            timestamp=3.33,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 150, "width": 80, "height": 120},
            validated=True
        )
        annotation2 = Annotation(
            id=str(uuid.uuid4()),
            video_id=sample_video.id,
            detection_id="DET_CYC_0001",
            frame_number=200,
            timestamp=6.67,
            vru_type="cyclist",
            bounding_box={"x": 200, "y": 250, "width": 90, "height": 130},
            validated=False
        )
        
        test_db.add(annotation1)
        test_db.add(annotation2)
        test_db.commit()
        
        # Test getting all annotations
        response = client.get(f"/api/videos/{sample_video.id}/annotations")
        assert response.status_code == 200
        
        annotations = response.json()
        assert len(annotations) == 2
        
        # Test getting only validated annotations
        response = client.get(f"/api/videos/{sample_video.id}/annotations?validated_only=true")
        assert response.status_code == 200
        
        validated_annotations = response.json()
        assert len(validated_annotations) == 1
        assert validated_annotations[0]["validated"] == True
    
    def test_update_annotation(self, sample_video, test_db):
        """Test updating an annotation"""
        # Create test annotation
        annotation = Annotation(
            id=str(uuid.uuid4()),
            video_id=sample_video.id,
            detection_id="DET_PED_0001",
            frame_number=100,
            timestamp=3.33,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 150, "width": 80, "height": 120},
            validated=False
        )
        test_db.add(annotation)
        test_db.commit()
        
        # Update annotation
        update_data = {
            "boundingBox": {"x": 110, "y": 160, "width": 85, "height": 125},
            "validated": True,
            "notes": "Updated annotation"
        }
        
        response = client.put(f"/api/annotations/{annotation.id}", json=update_data)
        assert response.status_code == 200
        
        result = response.json()
        assert result["boundingBox"]["x"] == 110
        assert result["validated"] == True
        assert result["notes"] == "Updated annotation"
    
    def test_delete_annotation(self, sample_video, test_db):
        """Test deleting an annotation"""
        # Create test annotation
        annotation = Annotation(
            id=str(uuid.uuid4()),
            video_id=sample_video.id,
            detection_id="DET_PED_0001",
            frame_number=100,
            timestamp=3.33,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 150, "width": 80, "height": 120}
        )
        test_db.add(annotation)
        test_db.commit()
        
        # Delete annotation
        response = client.delete(f"/api/annotations/{annotation.id}")
        assert response.status_code == 200
        
        # Verify deletion
        response = client.get(f"/api/annotations/{annotation.id}")
        assert response.status_code == 404
    
    def test_validate_annotation(self, sample_video, test_db):
        """Test validating an annotation"""
        # Create test annotation
        annotation = Annotation(
            id=str(uuid.uuid4()),
            video_id=sample_video.id,
            detection_id="DET_PED_0001",
            frame_number=100,
            timestamp=3.33,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 150, "width": 80, "height": 120},
            validated=False
        )
        test_db.add(annotation)
        test_db.commit()
        
        # Validate annotation
        response = client.patch(f"/api/annotations/{annotation.id}/validate?validated=true")
        assert response.status_code == 200
        
        result = response.json()
        assert result["validated"] == True

class TestProjectVideoLinking:
    """Test project-video linking functionality"""
    
    def test_link_video_to_project(self, sample_project, sample_video):
        """Test linking a video to a project"""
        link_data = {
            "videoId": sample_video.id,
            "projectId": sample_project.id,
            "assignmentReason": "Test linking"
        }
        
        response = client.post(f"/api/projects/{sample_project.id}/videos/link", json=link_data)
        assert response.status_code == 200
        
        result = response.json()
        assert result["videoId"] == sample_video.id
        assert result["projectId"] == sample_project.id
        assert result["assignmentReason"] == "Test linking"
        assert result["intelligentMatch"] == True
    
    def test_get_linked_videos(self, sample_project, sample_video, test_db):
        """Test getting videos linked to a project"""
        # Create video-project link
        link = VideoProjectLink(
            id=str(uuid.uuid4()),
            video_id=sample_video.id,
            project_id=sample_project.id,
            assignment_reason="Test link"
        )
        test_db.add(link)
        test_db.commit()
        
        response = client.get(f"/api/projects/{sample_project.id}/videos/linked")
        assert response.status_code == 200
        
        linked_videos = response.json()
        assert len(linked_videos) >= 1
        assert any(video["id"] == sample_video.id for video in linked_videos)
    
    def test_unlink_video_from_project(self, sample_project, sample_video, test_db):
        """Test unlinking a video from a project"""
        # Create video-project link
        link = VideoProjectLink(
            id=str(uuid.uuid4()),
            video_id=sample_video.id,
            project_id=sample_project.id,
            assignment_reason="Test link"
        )
        test_db.add(link)
        test_db.commit()
        
        response = client.delete(f"/api/projects/{sample_project.id}/videos/{sample_video.id}/unlink")
        assert response.status_code == 200
        
        # Verify unlinking
        response = client.get(f"/api/projects/{sample_project.id}/videos/linked")
        linked_videos = response.json()
        assert not any(video["id"] == sample_video.id for video in linked_videos)

class TestAnnotationSession:
    """Test annotation session functionality"""
    
    def test_create_annotation_session(self, sample_project, sample_video):
        """Test creating an annotation session"""
        session_data = {
            "videoId": sample_video.id,
            "projectId": sample_project.id,
            "annotatorId": "test_user_123"
        }
        
        response = client.post("/api/annotation-sessions", json=session_data)
        assert response.status_code == 200
        
        result = response.json()
        assert result["videoId"] == sample_video.id
        assert result["projectId"] == sample_project.id
        assert result["annotatorId"] == "test_user_123"
        assert result["status"] == "active"
        assert "id" in result
    
    def test_get_annotation_session(self, sample_project, sample_video, test_db):
        """Test retrieving an annotation session"""
        # Create annotation session
        session = AnnotationSession(
            id=str(uuid.uuid4()),
            video_id=sample_video.id,
            project_id=sample_project.id,
            annotator_id="test_user_123",
            status="active",
            total_detections=50,
            validated_detections=25,
            current_frame=100
        )
        test_db.add(session)
        test_db.commit()
        
        response = client.get(f"/api/annotation-sessions/{session.id}")
        assert response.status_code == 200
        
        result = response.json()
        assert result["id"] == session.id
        assert result["totalDetections"] == 50
        assert result["validatedDetections"] == 25
        assert result["currentFrame"] == 100

class TestExportFunctionality:
    """Test annotation export functionality"""
    
    def test_export_json_format(self, sample_video, test_db):
        """Test exporting annotations in JSON format"""
        # Create test annotations
        annotation = Annotation(
            id=str(uuid.uuid4()),
            video_id=sample_video.id,
            detection_id="DET_PED_0001",
            frame_number=100,
            timestamp=3.33,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 150, "width": 80, "height": 120},
            validated=True
        )
        test_db.add(annotation)
        test_db.commit()
        
        response = client.get(f"/api/videos/{sample_video.id}/annotations/export?format=json")
        assert response.status_code == 200
        
        result = response.json()
        assert "annotations" in result
        assert len(result["annotations"]) >= 1

# Cleanup
def teardown_module():
    """Clean up test database"""
    if os.path.exists("./test_annotation.db"):
        os.unlink("./test_annotation.db")