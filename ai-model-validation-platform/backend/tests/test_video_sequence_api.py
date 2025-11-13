"""
Test Video Sequence Testing API
================================

Integration tests for multi-video sequential HIL testing endpoints.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, Base, engine
from models import Project, Video
import uuid

# Create test client
client = TestClient(app)


@pytest.fixture(scope="function")
def test_db():
    """Create fresh test database for each test"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
    # Clean up after test
    # Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_project(test_db):
    """Create a test project"""
    project = Project(
        id=str(uuid.uuid4()),
        name="Test Video Sequence Project",
        description="Test project for video sequences",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO",
        status="active"
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)
    return project


@pytest.fixture
def test_videos(test_db, test_project):
    """Create test videos"""
    videos = []
    for i in range(3):
        video = Video(
            id=str(uuid.uuid4()),
            filename=f"test_video_{i+1}.mp4",
            file_path=f"/test/videos/test_video_{i+1}.mp4",
            project_id=test_project.id,
            duration=30.0 + (i * 10),
            fps=30.0,
            status="uploaded",
            ground_truth_generated=True,
            ground_truth_count=10 + i
        )
        test_db.add(video)
        videos.append(video)

    test_db.commit()
    for video in videos:
        test_db.refresh(video)

    return videos


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/api/video-sequences/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "features" in data


def test_start_video_sequence(test_project, test_videos):
    """Test starting a video sequence"""
    video_ids = [video.id for video in test_videos]

    payload = {
        "projectId": test_project.id,
        "videoIds": video_ids,
        "maxLatencyMs": 300.0,
        "testName": "Test Sequence",
        "testDescription": "Testing multi-video sequence",
        "enableLabjackMonitoring": False  # Disable for testing
    }

    response = client.post("/api/video-sequences/start", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "sequenceId" in data
    assert "testSessionId" in data
    assert data["totalVideos"] == 3
    assert len(data["videoPlaylist"]) == 3
    assert data["maxLatencyMs"] == 300.0
    assert data["status"] == "running"

    # Verify playlist order
    playlist = data["videoPlaylist"]
    for i, video_meta in enumerate(playlist):
        assert video_meta["sequenceIndex"] == i
        assert video_meta["videoId"] == video_ids[i]


def test_record_video_started(test_project, test_videos):
    """Test recording video start event"""
    # First start a sequence
    video_ids = [video.id for video in test_videos]
    start_payload = {
        "projectId": test_project.id,
        "videoIds": video_ids,
        "maxLatencyMs": 300.0,
        "enableLabjackMonitoring": False
    }

    start_response = client.post("/api/video-sequences/start", json=start_payload)
    sequence_id = start_response.json()["sequenceId"]

    # Record first video start
    import time
    started_at = time.time()

    video_start_payload = {
        "videoId": video_ids[0],
        "startedAt": started_at
    }

    response = client.post(
        f"/api/video-sequences/{sequence_id}/video-started",
        json=video_start_payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sequenceId"] == sequence_id
    assert data["videoId"] == video_ids[0]
    assert "message" in data


def test_record_video_ended(test_project, test_videos):
    """Test recording video end event"""
    # Start sequence and record video start
    video_ids = [video.id for video in test_videos]
    start_payload = {
        "projectId": test_project.id,
        "videoIds": video_ids,
        "maxLatencyMs": 300.0,
        "enableLabjackMonitoring": False
    }

    start_response = client.post("/api/video-sequences/start", json=start_payload)
    sequence_id = start_response.json()["sequenceId"]

    import time
    started_at = time.time()

    # Record video start
    client.post(
        f"/api/video-sequences/{sequence_id}/video-started",
        json={"videoId": video_ids[0], "startedAt": started_at}
    )

    # Record video end
    time.sleep(0.1)  # Small delay
    ended_at = time.time()

    video_end_payload = {
        "videoId": video_ids[0],
        "endedAt": ended_at,
        "actualDuration": ended_at - started_at
    }

    response = client.post(
        f"/api/video-sequences/{sequence_id}/video-ended",
        json=video_end_payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["videoId"] == video_ids[0]
    assert data["detectionCount"] >= 0
    assert "nextVideo" in data
    assert data["sequenceComplete"] == False  # Should have more videos

    # Verify next video info
    if data["nextVideo"]:
        assert data["nextVideo"]["videoId"] == video_ids[1]
        assert data["nextVideo"]["sequenceIndex"] == 1


def test_get_sequence_status(test_project, test_videos):
    """Test getting sequence status"""
    video_ids = [video.id for video in test_videos]
    start_payload = {
        "projectId": test_project.id,
        "videoIds": video_ids,
        "maxLatencyMs": 300.0,
        "enableLabjackMonitoring": False
    }

    start_response = client.post("/api/video-sequences/start", json=start_payload)
    sequence_id = start_response.json()["sequenceId"]

    response = client.get(f"/api/video-sequences/{sequence_id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["sequenceId"] == sequence_id
    assert data["overallStatus"] == "running"
    assert data["totalVideos"] == 3
    assert data["videosCompleted"] == 0
    assert data["videosRemaining"] == 3


def test_get_sequence_results(test_project, test_videos):
    """Test getting complete sequence results"""
    video_ids = [video.id for video in test_videos]
    start_payload = {
        "projectId": test_project.id,
        "videoIds": video_ids,
        "maxLatencyMs": 300.0,
        "enableLabjackMonitoring": False
    }

    start_response = client.post("/api/video-sequences/start", json=start_payload)
    sequence_id = start_response.json()["sequenceId"]

    response = client.get(f"/api/video-sequences/{sequence_id}/results")

    assert response.status_code == 200
    data = response.json()
    assert data["sequenceId"] == sequence_id
    assert data["totalVideos"] == 3
    assert "perVideoResults" in data
    assert len(data["perVideoResults"]) == 3
    assert "aggregateMetrics" in data


def test_record_detection_event(test_project, test_videos):
    """Test recording detection event"""
    video_ids = [video.id for video in test_videos]
    start_payload = {
        "projectId": test_project.id,
        "videoIds": video_ids,
        "maxLatencyMs": 300.0,
        "enableLabjackMonitoring": False
    }

    start_response = client.post("/api/video-sequences/start", json=start_payload)
    sequence_id = start_response.json()["sequenceId"]

    import time
    started_at = time.time()

    # Record video start
    client.post(
        f"/api/video-sequences/{sequence_id}/video-started",
        json={"videoId": video_ids[0], "startedAt": started_at}
    )

    # Record detection event
    time.sleep(0.05)
    detection_timestamp = time.time()

    detection_payload = {
        "unixTimestamp": detection_timestamp,
        "signalType": "GPIO",
        "channel": 1,
        "signalValue": 3.3,
        "metadata": {"test": "detection"}
    }

    response = client.post(
        f"/api/video-sequences/{sequence_id}/detection",
        json=detection_payload
    )

    assert response.status_code == 201
    data = response.json()
    assert data["sequenceId"] == sequence_id
    assert data["stored"] == True
    assert "detectionId" in data


def test_stop_sequence(test_project, test_videos):
    """Test stopping sequence early"""
    video_ids = [video.id for video in test_videos]
    start_payload = {
        "projectId": test_project.id,
        "videoIds": video_ids,
        "maxLatencyMs": 300.0,
        "enableLabjackMonitoring": False
    }

    start_response = client.post("/api/video-sequences/start", json=start_payload)
    sequence_id = start_response.json()["sequenceId"]

    stop_payload = {
        "reason": "Testing early stop",
        "force": False
    }

    response = client.post(
        f"/api/video-sequences/{sequence_id}/stop",
        json=stop_payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sequenceId"] == sequence_id
    assert data["stopped"] == True
    assert data["finalStatus"] == "stopped"


def test_invalid_sequence_id():
    """Test handling of invalid sequence ID"""
    fake_id = str(uuid.uuid4())

    response = client.get(f"/api/video-sequences/{fake_id}/status")
    assert response.status_code == 404


def test_invalid_project_id(test_videos):
    """Test handling of invalid project ID"""
    fake_project_id = str(uuid.uuid4())
    video_ids = [video.id for video in test_videos]

    payload = {
        "projectId": fake_project_id,
        "videoIds": video_ids,
        "maxLatencyMs": 300.0
    }

    response = client.post("/api/video-sequences/start", json=payload)
    assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])