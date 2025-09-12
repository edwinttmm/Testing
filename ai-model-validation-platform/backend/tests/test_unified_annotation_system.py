"""
Comprehensive Test Suite for Unified Annotation System
=====================================================

Tests for the consolidated annotation API endpoints and functionality.
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from database import get_db
from models import Annotation, Video, Project
from schemas_annotation import AnnotationCreate, VRUTypeEnum, BoundingBox


class TestUnifiedAnnotationSystem:
    """Test suite for the unified annotation system"""
    
    @pytest.fixture
    def client(self):
        """Test client fixture"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def sample_video(self):
        """Sample video for testing"""
        return Video(
            id="test-video-123",
            filename="test_video.mp4",
            file_path="/path/to/test_video.mp4",
            created_at=datetime.now(timezone.utc)
        )
    
    @pytest.fixture
    def sample_annotation(self):
        """Sample annotation for testing"""
        return Annotation(
            id="test-annotation-123",
            video_id="test-video-123",
            frame_number=100,
            timestamp=5.0,
            vru_type="pedestrian",
            bounding_box={
                "x": 10.0,
                "y": 20.0,
                "width": 50.0,
                "height": 80.0,
                "confidence": 0.95
            },
            occluded=False,
            truncated=False,
            difficult=False,
            validated=False,
            created_at=datetime.now(timezone.utc)
        )
    
    @pytest.fixture
    def annotation_create_data(self):
        """Sample annotation creation data"""
        return {
            "frameNumber": 150,
            "timestamp": 7.5,
            "vruType": "cyclist",
            "boundingBox": {
                "x": 15.0,
                "y": 25.0,
                "width": 60.0,
                "height": 90.0,
                "confidence": 0.88
            },
            "occluded": True,
            "truncated": False,
            "difficult": False,
            "notes": "Test annotation",
            "annotator": "test_user",
            "validated": False
        }

    def test_create_annotation_success(self, client, mock_db, sample_video, annotation_create_data):
        """Test successful annotation creation"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.post(
                f"/api/annotations/videos/{sample_video.id}/annotations",
                json=annotation_create_data
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "annotation" in data
        assert data["annotation"]["frameNumber"] == 150
        assert data["annotation"]["vruType"] == "cyclist"

    def test_create_annotation_video_not_found(self, client, mock_db, annotation_create_data):
        """Test annotation creation with non-existent video"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.post(
                "/api/annotations/videos/nonexistent-video/annotations",
                json=annotation_create_data
            )
        
        assert response.status_code == 400
        data = response.json()
        assert "errors" in data["detail"]

    def test_create_annotation_invalid_data(self, client, mock_db, sample_video):
        """Test annotation creation with invalid data"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        
        invalid_data = {
            "frameNumber": -1,  # Invalid negative frame
            "timestamp": -5.0,  # Invalid negative timestamp
            "vruType": "invalid_type",
            "boundingBox": {
                "x": -10.0,  # Invalid negative coordinate
                "y": 25.0,
                "width": 0.0,  # Invalid zero width
                "height": 90.0
            }
        }
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.post(
                f"/api/annotations/videos/{sample_video.id}/annotations",
                json=invalid_data
            )
        
        assert response.status_code == 400

    def test_get_video_annotations_success(self, client, mock_db, sample_video, sample_annotation):
        """Test successful retrieval of video annotations"""
        mock_db.query.return_value.filter.return_value.count.return_value = 1
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [sample_annotation]
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.get(f"/api/annotations/videos/{sample_video.id}/annotations")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "annotations" in data
        assert len(data["annotations"]) == 1
        assert "pagination" in data

    def test_get_video_annotations_with_filters(self, client, mock_db, sample_video):
        """Test video annotations retrieval with filters"""
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.get(
                f"/api/annotations/videos/{sample_video.id}/annotations?validated_only=true&skip=10&limit=50"
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["pagination"]["skip"] == 10
        assert data["pagination"]["limit"] == 50

    def test_get_annotation_success(self, client, mock_db, sample_annotation):
        """Test successful retrieval of specific annotation"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_annotation
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.get(f"/api/annotations/annotations/{sample_annotation.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["annotation"]["id"] == sample_annotation.id

    def test_get_annotation_not_found(self, client, mock_db):
        """Test retrieval of non-existent annotation"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.get("/api/annotations/annotations/nonexistent-id")
        
        assert response.status_code == 404

    def test_update_annotation_success(self, client, mock_db, sample_annotation):
        """Test successful annotation update"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_annotation
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        update_data = {
            "notes": "Updated notes",
            "validated": True
        }
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.put(
                f"/api/annotations/annotations/{sample_annotation.id}",
                json=update_data
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "annotation" in data

    def test_delete_annotation_success(self, client, mock_db, sample_annotation):
        """Test successful annotation deletion"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_annotation
        mock_db.delete = Mock()
        mock_db.commit = Mock()
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.delete(f"/api/annotations/annotations/{sample_annotation.id}")
        
        assert response.status_code == 204

    def test_delete_annotation_not_found(self, client, mock_db):
        """Test deletion of non-existent annotation"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.delete("/api/annotations/annotations/nonexistent-id")
        
        assert response.status_code == 404

    def test_batch_create_annotations_success(self, client, mock_db, sample_video):
        """Test successful batch annotation creation"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        batch_data = [
            {
                "frameNumber": 100,
                "timestamp": 5.0,
                "vruType": "pedestrian",
                "boundingBox": {"x": 10, "y": 20, "width": 50, "height": 80},
                "occluded": False,
                "truncated": False,
                "difficult": False
            },
            {
                "frameNumber": 200,
                "timestamp": 10.0,
                "vruType": "cyclist",
                "boundingBox": {"x": 30, "y": 40, "width": 60, "height": 90},
                "occluded": False,
                "truncated": False,
                "difficult": False
            }
        ]
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.post(
                f"/api/annotations/videos/{sample_video.id}/annotations/batch",
                json=batch_data
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["created"] == 2
        assert data["errors"] == 0

    def test_validate_annotation_success(self, client, mock_db, sample_annotation):
        """Test successful annotation validation"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_annotation
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.patch(
                f"/api/annotations/annotations/{sample_annotation.id}/validate",
                json={"validated": True}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_export_annotations_json(self, client, mock_db, sample_video, sample_annotation):
        """Test annotation export in JSON format"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = [sample_annotation]
        mock_db.query.return_value = mock_query
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.get(
                f"/api/annotations/videos/{sample_video.id}/annotations/export?format=json"
            )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json; charset=utf-8"

    def test_export_annotations_csv(self, client, mock_db, sample_video, sample_annotation):
        """Test annotation export in CSV format"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = [sample_annotation]
        mock_db.query.return_value = mock_query
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.get(
                f"/api/annotations/videos/{sample_video.id}/annotations/export?format=csv"
            )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

    def test_get_annotation_analytics(self, client, mock_db):
        """Test annotation analytics endpoint"""
        # Mock statistics queries
        mock_db.query.return_value.filter.return_value.count.return_value = 100
        mock_db.query.return_value.filter.return_value.filter.return_value.count.return_value = 75
        mock_db.query.return_value.filter.return_value.with_entities.return_value.group_by.return_value.all.return_value = [
            ("pedestrian", 60),
            ("cyclist", 40)
        ]
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.get("/api/annotations/analytics/summary?days=30")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "summary" in data
        assert "vruDistribution" in data
        assert data["summary"]["totalAnnotations"] == 100
        assert data["summary"]["validatedAnnotations"] == 75

    def test_health_check_success(self, client, mock_db):
        """Test annotation system health check"""
        mock_db.query.return_value.count.return_value = 150
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.get("/api/annotations/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["totalAnnotations"] == 150

    def test_health_check_failure(self, client, mock_db):
        """Test annotation system health check with database failure"""
        mock_db.query.side_effect = Exception("Database connection failed")
        
        with patch('src.api.unified_annotation_endpoints.get_db', return_value=mock_db):
            response = client.get("/api/annotations/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data


class TestAnnotationSchemas:
    """Test annotation schema validation"""
    
    def test_valid_bounding_box(self):
        """Test valid bounding box creation"""
        bbox = BoundingBox(
            x=10.0,
            y=20.0,
            width=50.0,
            height=80.0,
            confidence=0.95
        )
        assert bbox.x == 10.0
        assert bbox.y == 20.0
        assert bbox.width == 50.0
        assert bbox.height == 80.0
        assert bbox.confidence == 0.95

    def test_invalid_bounding_box_negative_coordinates(self):
        """Test bounding box with negative coordinates"""
        with pytest.raises(ValueError):
            BoundingBox(
                x=-10.0,  # Invalid negative x
                y=20.0,
                width=50.0,
                height=80.0
            )

    def test_invalid_bounding_box_zero_dimensions(self):
        """Test bounding box with zero dimensions"""
        with pytest.raises(ValueError):
            BoundingBox(
                x=10.0,
                y=20.0,
                width=0.0,  # Invalid zero width
                height=80.0
            )

    def test_valid_annotation_create(self):
        """Test valid annotation creation schema"""
        bbox = BoundingBox(x=10, y=20, width=50, height=80)
        
        annotation = AnnotationCreate(
            frame_number=100,
            timestamp=5.0,
            vru_type=VRUTypeEnum.PEDESTRIAN,
            bounding_box=bbox,
            occluded=False,
            truncated=False,
            difficult=False,
            notes="Test annotation",
            annotator="test_user",
            validated=False
        )
        
        assert annotation.frame_number == 100
        assert annotation.timestamp == 5.0
        assert annotation.vru_type == VRUTypeEnum.PEDESTRIAN
        assert annotation.bounding_box == bbox

    def test_invalid_annotation_create_negative_frame(self):
        """Test annotation creation with negative frame number"""
        bbox = BoundingBox(x=10, y=20, width=50, height=80)
        
        with pytest.raises(ValueError):
            AnnotationCreate(
                frame_number=-1,  # Invalid negative frame
                timestamp=5.0,
                vru_type=VRUTypeEnum.PEDESTRIAN,
                bounding_box=bbox
            )

    def test_invalid_annotation_create_negative_timestamp(self):
        """Test annotation creation with negative timestamp"""
        bbox = BoundingBox(x=10, y=20, width=50, height=80)
        
        with pytest.raises(ValueError):
            AnnotationCreate(
                frame_number=100,
                timestamp=-5.0,  # Invalid negative timestamp
                vru_type=VRUTypeEnum.PEDESTRIAN,
                bounding_box=bbox
            )


class TestAnnotationUtilities:
    """Test annotation utility functions"""
    
    def test_validate_annotation_data_valid(self):
        """Test validation with valid annotation data"""
        from src.api.unified_annotation_endpoints import validate_annotation_data
        
        bbox = BoundingBox(x=10, y=20, width=50, height=80)
        annotation_data = AnnotationCreate(
            frame_number=100,
            timestamp=5.0,
            vru_type=VRUTypeEnum.PEDESTRIAN,
            bounding_box=bbox
        )
        
        mock_db = Mock()
        video = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = video
        
        result = validate_annotation_data(annotation_data, "test-video-id", mock_db)
        
        assert result["valid"] is True
        assert result["video"] == video

    def test_validate_annotation_data_video_not_found(self):
        """Test validation with non-existent video"""
        from src.api.unified_annotation_endpoints import validate_annotation_data
        
        bbox = BoundingBox(x=10, y=20, width=50, height=80)
        annotation_data = AnnotationCreate(
            frame_number=100,
            timestamp=5.0,
            vru_type=VRUTypeEnum.PEDESTRIAN,
            bounding_box=bbox
        )
        
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = validate_annotation_data(annotation_data, "nonexistent-video", mock_db)
        
        assert result["valid"] is False
        assert "does not exist" in result["errors"][0]

    def test_create_annotation_response(self):
        """Test annotation response creation"""
        from src.api.unified_annotation_endpoints import create_annotation_response
        
        annotation = Mock()
        annotation.id = "test-id"
        annotation.video_id = "test-video-id"
        annotation.detection_id = "test-detection-id"
        annotation.frame_number = 100
        annotation.timestamp = 5.0
        annotation.end_timestamp = 6.0
        annotation.vru_type = "pedestrian"
        annotation.bounding_box = {"x": 10, "y": 20, "width": 50, "height": 80}
        annotation.occluded = False
        annotation.truncated = False
        annotation.difficult = False
        annotation.notes = "Test notes"
        annotation.annotator = "test_user"
        annotation.validated = True
        annotation.created_at = datetime(2023, 1, 1, 12, 0, 0)
        annotation.updated_at = None
        
        response = create_annotation_response(annotation)
        
        assert response["id"] == "test-id"
        assert response["videoId"] == "test-video-id"
        assert response["frameNumber"] == 100
        assert response["vruType"] == "pedestrian"
        assert response["validated"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])