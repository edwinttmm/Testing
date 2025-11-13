"""
Production tests for ground truth validation endpoint (Issue #3 Backend)

Tests the pre-session validation endpoint that checks if videos have sufficient
ground truth data before starting a test session.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid

from database import Base
from main import app
from models import Video, GroundTruthObject, Project
from routers.test_sessions import get_db


# Test database setup
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_gt_validation.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function")
def setup_database():
    """Setup test database with fresh schema for each test"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(setup_database):
    """Provide database session for test setup"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_test_project(db):
    """Helper to create test project"""
    project = Project(
        id=str(uuid.uuid4()),
        name="Test Project",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO",
        status="active",
        owner_id="anonymous"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def create_test_video(db, project_id: str, filename: str = "test_video.mp4") -> Video:
    """Helper to create test video"""
    video = Video(
        id=str(uuid.uuid4()),
        filename=filename,
        file_path=f"/uploads/{filename}",
        project_id=project_id,
        status="uploaded",
        ground_truth_generated=False,
        ground_truth_count=0
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def create_ground_truth_objects(db, video_id: str, count: int):
    """Helper to create ground truth objects"""
    objects = []
    for i in range(count):
        gt_obj = GroundTruthObject(
            id=str(uuid.uuid4()),
            video_id=video_id,
            timestamp=float(i),
            frame_number=i * 30,
            class_label="pedestrian",
            x=100.0,
            y=100.0,
            width=50.0,
            height=100.0,
            confidence=0.95,
            validated=True
        )
        db.add(gt_obj)
        objects.append(gt_obj)

    db.commit()
    for obj in objects:
        db.refresh(obj)
    return objects


class TestGroundTruthValidationEndpoint:
    """Test suite for ground truth validation endpoint"""

    def test_validate_single_video_with_ground_truth(self, db_session):
        """Test validation with a single video that has ground truth"""
        # Setup
        project = create_test_project(db_session)
        video = create_test_video(db_session, project.id)
        create_ground_truth_objects(db_session, video.id, 10)

        # Request
        response = client.post(
            "/api/test-sessions/validate-ground-truth",
            json={"videoIds": [video.id]}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        assert data["hasIssues"] is False
        assert len(data["videosWithoutGt"]) == 0
        assert data["gtCounts"][video.id] == 10
        assert data["totalVideos"] == 1
        assert data["readyVideos"] == 1
        assert len(data["videoDetails"]) == 1
        assert data["videoDetails"][0]["videoId"] == video.id
        assert data["videoDetails"][0]["gtCount"] == 10
        assert data["videoDetails"][0]["hasGroundTruth"] is True
        assert data["videoDetails"][0]["status"] == "ready"

    def test_validate_single_video_without_ground_truth(self, db_session):
        """Test validation with a single video that has NO ground truth"""
        # Setup
        project = create_test_project(db_session)
        video = create_test_video(db_session, project.id)
        # No ground truth objects created

        # Request
        response = client.post(
            "/api/test-sessions/validate-ground-truth",
            json={"videoIds": [video.id]}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        assert data["hasIssues"] is True
        assert len(data["videosWithoutGt"]) == 1
        assert video.id in data["videosWithoutGt"]
        assert data["gtCounts"][video.id] == 0
        assert data["totalVideos"] == 1
        assert data["readyVideos"] == 0
        assert data["videoDetails"][0]["status"] == "missing_gt"

    def test_validate_multiple_videos_mixed_ground_truth(self, db_session):
        """Test validation with multiple videos, some with GT, some without"""
        # Setup
        project = create_test_project(db_session)
        video1 = create_test_video(db_session, project.id, "video1.mp4")
        video2 = create_test_video(db_session, project.id, "video2.mp4")
        video3 = create_test_video(db_session, project.id, "video3.mp4")

        # video1: 10 GT objects (ready)
        create_ground_truth_objects(db_session, video1.id, 10)
        # video2: 3 GT objects (insufficient)
        create_ground_truth_objects(db_session, video2.id, 3)
        # video3: 0 GT objects (missing)

        # Request
        response = client.post(
            "/api/test-sessions/validate-ground-truth",
            json={"videoIds": [video1.id, video2.id, video3.id]}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        assert data["hasIssues"] is True
        assert video3.id in data["videosWithoutGt"]
        assert video1.id not in data["videosWithoutGt"]
        assert data["gtCounts"][video1.id] == 10
        assert data["gtCounts"][video2.id] == 3
        assert data["gtCounts"][video3.id] == 0
        assert data["totalVideos"] == 3
        assert data["readyVideos"] == 1  # Only video1 is ready (>= 5 GT)

        # Check detailed status
        video_statuses = {v["videoId"]: v for v in data["videoDetails"]}
        assert video_statuses[video1.id]["status"] == "ready"
        assert video_statuses[video2.id]["status"] == "insufficient_gt"
        assert video_statuses[video3.id]["status"] == "missing_gt"

    def test_validate_empty_video_list(self, db_session):
        """Test validation with empty video list (should fail)"""
        response = client.post(
            "/api/test-sessions/validate-ground-truth",
            json={"videoIds": []}
        )

        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]

    def test_validate_nonexistent_video(self, db_session):
        """Test validation with non-existent video ID"""
        fake_video_id = str(uuid.uuid4())

        response = client.post(
            "/api/test-sessions/validate-ground-truth",
            json={"videoIds": [fake_video_id]}
        )

        # Should succeed but report zero ground truth
        assert response.status_code == 200
        data = response.json()
        assert data["gtCounts"][fake_video_id] == 0
        assert fake_video_id in data["videosWithoutGt"]

    def test_validate_performance_with_many_videos(self, db_session):
        """Test validation performance with multiple videos (should use single query)"""
        import time

        # Setup 20 videos with varying GT counts
        project = create_test_project(db_session)
        video_ids = []

        for i in range(20):
            video = create_test_video(db_session, project.id, f"video_{i}.mp4")
            video_ids.append(video.id)
            # Create varying amounts of GT (0-20)
            create_ground_truth_objects(db_session, video.id, i)

        # Request with timing
        start_time = time.time()
        response = client.post(
            "/api/test-sessions/validate-ground-truth",
            json={"videoIds": video_ids}
        )
        elapsed_time = time.time() - start_time

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["totalVideos"] == 20

        # Performance check: should complete in < 1 second (single query)
        assert elapsed_time < 1.0, f"Validation took {elapsed_time:.2f}s (should be < 1s)"

        # Verify counts
        for i, video_id in enumerate(video_ids):
            assert data["gtCounts"][video_id] == i

    def test_create_session_with_force_start(self, db_session):
        """Test session creation with force_start parameter"""
        # Setup video WITHOUT ground truth
        project = create_test_project(db_session)
        video = create_test_video(db_session, project.id)

        # Attempt to create session WITHOUT force_start (should fail)
        response = client.post(
            "/api/test-sessions",
            json={
                "name": "Test Session",
                "projectId": project.id,
                "videoId": video.id
            }
        )
        assert response.status_code == 422
        assert "no ground truth" in response.json()["detail"]

        # Create session WITH force_start (should succeed)
        response = client.post(
            "/api/test-sessions?force_start=true",
            json={
                "name": "Test Session",
                "projectId": project.id,
                "videoId": video.id
            }
        )
        assert response.status_code == 200
        assert "id" in response.json()

    def test_create_session_with_ground_truth(self, db_session):
        """Test session creation succeeds when video has ground truth"""
        # Setup video WITH ground truth
        project = create_test_project(db_session)
        video = create_test_video(db_session, project.id)
        create_ground_truth_objects(db_session, video.id, 10)

        # Create session (should succeed without force_start)
        response = client.post(
            "/api/test-sessions",
            json={
                "name": "Test Session",
                "projectId": project.id,
                "videoId": video.id
            }
        )
        assert response.status_code == 200
        assert "id" in response.json()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
