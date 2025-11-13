"""
Test Ground Truth Upload Endpoint
Tests POST /api/ground-truth and GET /api/videos/{video_id}/ground-truth/validate
"""
import pytest
import json
import io
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

def test_upload_ground_truth_json_success(client: TestClient, db_session):
    """Test successful JSON ground truth upload"""
    # Create mock video
    from models import Video
    video = Video(
        id="test-video-123",
        filename="test.mp4",
        fps=30,
        status="validated"
    )
    db_session.add(video)
    db_session.commit()

    # Prepare JSON file
    gt_data = {
        "objects": [
            {
                "timestamp": 1.5,
                "class_label": "pedestrian",
                "frame_number": 45,
                "tracking_id": "track-001",
                "confidence": 0.95,
                "bbox_x": 100,
                "bbox_y": 200,
                "bbox_width": 50,
                "bbox_height": 80,
                "validated": True
            },
            {
                "timestamp": 2.0,
                "class_label": "cyclist",
                "frame_number": 60,
                "confidence": 0.88,
                "x": 150,
                "y": 250,
                "width": 60,
                "height": 90
            }
        ]
    }

    file_content = json.dumps(gt_data).encode('utf-8')
    files = {
        'file': ('ground_truth.json', io.BytesIO(file_content), 'application/json')
    }

    # Upload ground truth
    response = client.post(
        f"/api/ground-truth?video_id={video.id}",
        files=files
    )

    assert response.status_code == 200
    data = response.json()
    assert data['video_id'] == video.id
    assert data['objects_created'] == 2
    assert data['status'] == 'success'
    assert data['filename'] == 'ground_truth.json'


def test_upload_ground_truth_csv_success(client: TestClient, db_session):
    """Test successful CSV ground truth upload"""
    # Create mock video
    from models import Video
    video = Video(
        id="test-video-456",
        filename="test2.mp4",
        fps=30,
        status="validated"
    )
    db_session.add(video)
    db_session.commit()

    # Prepare CSV file
    csv_content = """timestamp,class_label,frame_number,confidence,bbox_x,bbox_y,bbox_width,bbox_height
1.5,pedestrian,45,0.95,100,200,50,80
2.0,cyclist,60,0.88,150,250,60,90
"""

    files = {
        'file': ('ground_truth.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
    }

    # Upload ground truth
    response = client.post(
        f"/api/ground-truth?video_id={video.id}",
        files=files
    )

    assert response.status_code == 200
    data = response.json()
    assert data['video_id'] == video.id
    assert data['objects_created'] == 2
    assert data['status'] == 'success'


def test_upload_ground_truth_video_not_found(client: TestClient):
    """Test upload with non-existent video"""
    gt_data = {"objects": [{"timestamp": 1.0, "class_label": "test"}]}
    file_content = json.dumps(gt_data).encode('utf-8')
    files = {
        'file': ('ground_truth.json', io.BytesIO(file_content), 'application/json')
    }

    response = client.post(
        "/api/ground-truth?video_id=nonexistent-video",
        files=files
    )

    assert response.status_code == 404
    assert "not found" in response.json()['detail'].lower()


def test_upload_ground_truth_invalid_file_format(client: TestClient, db_session):
    """Test upload with unsupported file format"""
    from models import Video
    video = Video(id="test-video-789", filename="test3.mp4", status="validated")
    db_session.add(video)
    db_session.commit()

    files = {
        'file': ('ground_truth.txt', io.BytesIO(b"invalid content"), 'text/plain')
    }

    response = client.post(
        f"/api/ground-truth?video_id={video.id}",
        files=files
    )

    assert response.status_code == 400
    assert "must be .json or .csv" in response.json()['detail']


def test_validate_ground_truth_exists(client: TestClient, db_session):
    """Test ground truth validation for video with GT data"""
    from models import Video, GroundTruthObject

    # Create video with ground truth
    video = Video(id="test-video-gt", filename="test_gt.mp4", status="validated")
    db_session.add(video)
    db_session.flush()

    # Add ground truth objects
    gt1 = GroundTruthObject(
        video_id=video.id,
        timestamp=1.0,
        class_label="pedestrian",
        x=100, y=200, width=50, height=80
    )
    gt2 = GroundTruthObject(
        video_id=video.id,
        timestamp=2.0,
        class_label="cyclist",
        x=150, y=250, width=60, height=90
    )
    db_session.add_all([gt1, gt2])
    db_session.commit()

    # Validate ground truth
    response = client.get(f"/api/ground-truth/videos/{video.id}/ground-truth/validate")

    assert response.status_code == 200
    data = response.json()
    assert data['video_id'] == video.id
    assert data['ground_truth_count'] == 2
    assert data['has_ground_truth'] is True
    assert data['status'] == 'valid'


def test_validate_ground_truth_no_data(client: TestClient, db_session):
    """Test ground truth validation for video without GT data"""
    from models import Video

    video = Video(id="test-video-no-gt", filename="test_no_gt.mp4", status="validated")
    db_session.add(video)
    db_session.commit()

    # Validate ground truth
    response = client.get(f"/api/ground-truth/videos/{video.id}/ground-truth/validate")

    assert response.status_code == 200
    data = response.json()
    assert data['video_id'] == video.id
    assert data['ground_truth_count'] == 0
    assert data['has_ground_truth'] is False
    assert data['status'] == 'no_ground_truth'


def test_validate_ground_truth_excludes_soft_deleted(client: TestClient, db_session):
    """Test that soft-deleted ground truth is excluded from validation"""
    from models import Video, GroundTruthObject
    from datetime import datetime

    # Create video with ground truth
    video = Video(id="test-video-soft-delete", filename="test_sd.mp4", status="validated")
    db_session.add(video)
    db_session.flush()

    # Add active GT object
    gt_active = GroundTruthObject(
        video_id=video.id,
        timestamp=1.0,
        class_label="pedestrian",
        x=100, y=200, width=50, height=80
    )

    # Add soft-deleted GT object
    gt_deleted = GroundTruthObject(
        video_id=video.id,
        timestamp=2.0,
        class_label="cyclist",
        x=150, y=250, width=60, height=90,
        deleted_at=datetime.utcnow(),
        deleted_by="test_user"
    )

    db_session.add_all([gt_active, gt_deleted])
    db_session.commit()

    # Validate - should only count active GT
    response = client.get(f"/api/ground-truth/videos/{video.id}/ground-truth/validate")

    assert response.status_code == 200
    data = response.json()
    assert data['ground_truth_count'] == 1  # Only active GT counted
    assert data['has_ground_truth'] is True


def test_upload_ground_truth_skips_objects_without_timestamp(client: TestClient, db_session):
    """Test that objects without timestamp are skipped"""
    from models import Video
    video = Video(id="test-video-skip", filename="test_skip.mp4", status="validated")
    db_session.add(video)
    db_session.commit()

    # Data with one valid and one invalid object
    gt_data = {
        "objects": [
            {
                "timestamp": 1.5,
                "class_label": "pedestrian",
                "bbox_x": 100,
                "bbox_y": 200,
                "bbox_width": 50,
                "bbox_height": 80
            },
            {
                # Missing timestamp
                "class_label": "cyclist",
                "bbox_x": 150,
                "bbox_y": 250,
                "bbox_width": 60,
                "bbox_height": 90
            }
        ]
    }

    file_content = json.dumps(gt_data).encode('utf-8')
    files = {
        'file': ('ground_truth.json', io.BytesIO(file_content), 'application/json')
    }

    response = client.post(
        f"/api/ground-truth?video_id={video.id}",
        files=files
    )

    assert response.status_code == 200
    data = response.json()
    assert data['objects_created'] == 1
    assert data['objects_skipped'] == 1
