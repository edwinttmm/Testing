"""
Comprehensive API Tests for Dataset Annotation System
=====================================================

Tests cover all annotation endpoints, data validation, CRUD operations,
and error handling scenarios following QA best practices.
"""

import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, List, Any

# Import test fixtures and utilities
from tests.conftest import TestDataHelper
from main import app
from models import Annotation, Video, Project, DetectionEvent
from database import get_db


class TestAnnotationAPICRUD:
    """Test annotation API CRUD operations"""
    
    def test_create_annotation_success(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test successful annotation creation"""
        # Setup test video
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        annotation_data = {
            "videoId": video.id,
            "frameNumber": 120,
            "timestamp": 4.0,
            "vruType": "pedestrian",
            "boundingBox": {
                "x": 100,
                "y": 150,
                "width": 50,
                "height": 100,
                "confidence": 0.95,
                "label": "person"
            },
            "occluded": False,
            "truncated": False,
            "difficult": False,
            "notes": "Test annotation",
            "annotator": "test-user-123",
            "validated": False
        }
        
        response = test_client.post("/api/annotations/", json=annotation_data)
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert data["videoId"] == video.id
        assert data["frameNumber"] == 120
        assert data["timestamp"] == 4.0
        assert data["vruType"] == "pedestrian"
        assert data["boundingBox"]["x"] == 100
        assert data["boundingBox"]["confidence"] == 0.95
        assert data["annotator"] == "test-user-123"
        assert data["validated"] is False
        
        # Verify database record
        db_annotation = test_db.query(Annotation).filter(Annotation.id == data["id"]).first()
        assert db_annotation is not None
        assert db_annotation.video_id == video.id
        assert db_annotation.frame_number == 120
    
    def test_create_annotation_validation_errors(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test annotation creation with validation errors"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Test missing required fields
        invalid_data = {
            "videoId": video.id,
            "frameNumber": -1,  # Invalid negative frame
            "timestamp": -5.0,   # Invalid negative timestamp
            "vruType": "invalid_type",  # Invalid VRU type
            "boundingBox": {
                "x": -10,  # Invalid negative coordinate
                "y": 150,
                "width": -50,  # Invalid negative width
                "height": 100
            }
        }
        
        response = test_client.post("/api/annotations/", json=invalid_data)
        
        assert response.status_code == 422
        error_data = response.json()
        assert "errors" in error_data["detail"]
        
        # Verify specific validation errors
        errors = error_data["detail"]["errors"]
        assert any("frame number must be non-negative" in error.lower() for error in errors)
        assert any("timestamp must be non-negative" in error.lower() for error in errors)
        assert any("invalid vru type" in error.lower() for error in errors)
        assert any("bounding box coordinates must be non-negative" in error.lower() for error in errors)
    
    def test_get_annotations_with_filters(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test getting annotations with various filters"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create test annotations with different properties
        annotations_data = [
            {
                "video_id": video.id,
                "frame_number": 100,
                "timestamp": 3.33,
                "vru_type": "pedestrian",
                "bounding_box": {"x": 100, "y": 100, "width": 50, "height": 80},
                "validated": True,
                "annotator": "user1"
            },
            {
                "video_id": video.id,
                "frame_number": 200,
                "timestamp": 6.67,
                "vru_type": "cyclist",
                "bounding_box": {"x": 200, "y": 200, "width": 60, "height": 90},
                "validated": False,
                "annotator": "user2"
            },
            {
                "video_id": video.id,
                "frame_number": 300,
                "timestamp": 10.0,
                "vru_type": "pedestrian",
                "bounding_box": {"x": 300, "y": 300, "width": 55, "height": 85},
                "validated": True,
                "annotator": "user1"
            }
        ]
        
        for ann_data in annotations_data:
            annotation = Annotation(**ann_data)
            test_db.add(annotation)
        test_db.commit()
        
        # Test filtering by video_id
        response = test_client.get(f"/api/annotations/?video_id={video.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        
        # Test filtering by VRU type
        response = test_client.get(f"/api/annotations/?video_id={video.id}&vru_type=pedestrian")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(ann["vruType"] == "pedestrian" for ann in data)
        
        # Test filtering by validation status
        response = test_client.get(f"/api/annotations/?video_id={video.id}&validated=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(ann["validated"] is True for ann in data)
        
        # Test pagination
        response = test_client.get(f"/api/annotations/?video_id={video.id}&limit=2&offset=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
    
    def test_get_annotation_by_id(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test getting specific annotation by ID"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        annotation = Annotation(
            video_id=video.id,
            frame_number=150,
            timestamp=5.0,
            vru_type="cyclist",
            bounding_box={"x": 150, "y": 150, "width": 60, "height": 90},
            validated=True,
            annotator="test-user"
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)
        
        response = test_client.get(f"/api/annotations/{annotation.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == annotation.id
        assert data["videoId"] == video.id
        assert data["frameNumber"] == 150
        assert data["vruType"] == "cyclist"
        assert data["validated"] is True
    
    def test_get_nonexistent_annotation(self, test_client: TestClient):
        """Test getting non-existent annotation returns 404"""
        response = test_client.get("/api/annotations/non-existent-id")
        
        assert response.status_code == 404
        error_data = response.json()
        assert "not found" in error_data["detail"].lower()
    
    def test_update_annotation_success(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test successful annotation update"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        annotation = Annotation(
            video_id=video.id,
            frame_number=100,
            timestamp=3.33,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 100, "width": 50, "height": 80},
            validated=False,
            annotator="original-user"
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)
        
        update_data = {
            "validated": True,
            "annotator": "validator-user",
            "notes": "Updated annotation after review",
            "boundingBox": {
                "x": 105,
                "y": 105,
                "width": 55,
                "height": 85,
                "confidence": 0.98
            }
        }
        
        response = test_client.put(f"/api/annotations/{annotation.id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["validated"] is True
        assert data["annotator"] == "validator-user"
        assert data["notes"] == "Updated annotation after review"
        assert data["boundingBox"]["x"] == 105
        assert data["boundingBox"]["confidence"] == 0.98
        
        # Verify database update
        updated_annotation = test_db.query(Annotation).filter(Annotation.id == annotation.id).first()
        assert updated_annotation.validated is True
        assert updated_annotation.annotator == "validator-user"
    
    def test_delete_annotation_success(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test successful annotation deletion"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        annotation = Annotation(
            video_id=video.id,
            frame_number=100,
            timestamp=3.33,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 100, "width": 50, "height": 80}
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)
        
        response = test_client.delete(f"/api/annotations/{annotation.id}")
        
        assert response.status_code == 204
        
        # Verify deletion from database
        deleted_annotation = test_db.query(Annotation).filter(Annotation.id == annotation.id).first()
        assert deleted_annotation is None
    
    def test_delete_nonexistent_annotation(self, test_client: TestClient):
        """Test deleting non-existent annotation returns 404"""
        response = test_client.delete("/api/annotations/non-existent-id")
        
        assert response.status_code == 404
        error_data = response.json()
        assert "not found" in error_data["detail"].lower()


class TestAnnotationBulkOperations:
    """Test bulk annotation operations"""
    
    def test_bulk_create_annotations_success(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test successful bulk annotation creation"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        bulk_annotations = [
            {
                "videoId": video.id,
                "frameNumber": 100 + i,
                "timestamp": 3.0 + i * 0.5,
                "vruType": "pedestrian" if i % 2 == 0 else "cyclist",
                "boundingBox": {
                    "x": 100 + i * 10,
                    "y": 100 + i * 5,
                    "width": 50,
                    "height": 80,
                    "confidence": 0.9 + i * 0.01
                },
                "annotator": f"user-{i}"
            }
            for i in range(5)
        ]
        
        response = test_client.post("/api/annotations/bulk", json=bulk_annotations)
        
        assert response.status_code == 201
        data = response.json()
        
        assert len(data) == 5
        assert all("id" in annotation for annotation in data)
        assert data[0]["vruType"] == "pedestrian"
        assert data[1]["vruType"] == "cyclist"
        
        # Verify database records
        db_annotations = test_db.query(Annotation).filter(Annotation.video_id == video.id).all()
        assert len(db_annotations) == 5
    
    def test_bulk_create_annotations_validation_error(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test bulk creation with validation errors"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Include one invalid annotation in the batch
        bulk_annotations = [
            {
                "videoId": video.id,
                "frameNumber": 100,
                "timestamp": 3.0,
                "vruType": "pedestrian",
                "boundingBox": {"x": 100, "y": 100, "width": 50, "height": 80}
            },
            {
                "videoId": video.id,
                "frameNumber": -1,  # Invalid negative frame
                "timestamp": 3.5,
                "vruType": "invalid_type",  # Invalid VRU type
                "boundingBox": {"x": 150, "y": 150, "width": -50, "height": 80}  # Invalid negative width
            }
        ]
        
        response = test_client.post("/api/annotations/bulk", json=bulk_annotations)
        
        assert response.status_code == 422
        error_data = response.json()
        assert "validation failed for annotation 2" in error_data["detail"]["message"].lower()
        
        # Verify no annotations were created due to transaction rollback
        db_annotations = test_db.query(Annotation).filter(Annotation.video_id == video.id).all()
        assert len(db_annotations) == 0
    
    def test_bulk_create_empty_list(self, test_client: TestClient):
        """Test bulk creation with empty list"""
        response = test_client.post("/api/annotations/bulk", json=[])
        
        assert response.status_code == 422
        error_data = response.json()
        assert "no annotations provided" in error_data["detail"].lower()
    
    def test_bulk_create_too_many_annotations(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test bulk creation with too many annotations"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create more than the allowed limit (1000)
        bulk_annotations = [
            {
                "videoId": video.id,
                "frameNumber": i,
                "timestamp": i * 0.033,
                "vruType": "pedestrian",
                "boundingBox": {"x": 100, "y": 100, "width": 50, "height": 80}
            }
            for i in range(1001)  # Exceed limit
        ]
        
        response = test_client.post("/api/annotations/bulk", json=bulk_annotations)
        
        assert response.status_code == 422
        error_data = response.json()
        assert "cannot create more than 1000" in error_data["detail"].lower()


class TestAnnotationStatistics:
    """Test annotation statistics endpoints"""
    
    def test_get_annotation_stats_success(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test getting annotation statistics"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create test annotations with variety
        annotations_data = [
            {"video_id": video.id, "vru_type": "pedestrian", "validated": True, "difficult": False},
            {"video_id": video.id, "vru_type": "pedestrian", "validated": False, "difficult": True},
            {"video_id": video.id, "vru_type": "cyclist", "validated": True, "occluded": True},
            {"video_id": video.id, "vru_type": "cyclist", "validated": True, "truncated": True},
            {"video_id": video.id, "vru_type": "motorcyclist", "validated": False, "difficult": True}
        ]
        
        for i, ann_data in enumerate(annotations_data):
            ann_data.update({
                "frame_number": i * 100,
                "timestamp": i * 2.0,
                "bounding_box": {"x": 100, "y": 100, "width": 50, "height": 80}
            })
            annotation = Annotation(**ann_data)
            test_db.add(annotation)
        test_db.commit()
        
        response = test_client.get(f"/api/annotations/stats/summary?video_id={video.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify statistics structure
        assert data["total_annotations"] == 5
        assert data["validated_annotations"] == 3
        assert data["validation_rate"] == 0.6
        
        # Check VRU type distribution
        vru_distribution = data["vru_type_distribution"]
        assert vru_distribution["pedestrian"] == 2
        assert vru_distribution["cyclist"] == 2
        assert vru_distribution["motorcyclist"] == 1
        
        # Check quality metrics
        quality_metrics = data["quality_metrics"]
        assert quality_metrics["difficult"] == 2
        assert quality_metrics["occluded"] == 1
        assert quality_metrics["truncated"] == 1
    
    def test_get_annotation_stats_empty_video(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test getting statistics for video with no annotations"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        response = test_client.get(f"/api/annotations/stats/summary?video_id={video.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_annotations"] == 0
        assert data["validated_annotations"] == 0
        assert data["validation_rate"] == 0
        assert data["vru_type_distribution"] == {}


class TestAnnotationExport:
    """Test annotation export functionality"""
    
    def test_export_annotations_json_format(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test exporting annotations in JSON format"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create test annotations
        annotations_data = [
            {
                "video_id": video.id,
                "frame_number": 100,
                "timestamp": 3.33,
                "vru_type": "pedestrian",
                "bounding_box": {"x": 100, "y": 100, "width": 50, "height": 80},
                "validated": True,
                "notes": "Test annotation 1"
            },
            {
                "video_id": video.id,
                "frame_number": 200,
                "timestamp": 6.67,
                "vru_type": "cyclist",
                "bounding_box": {"x": 200, "y": 200, "width": 60, "height": 90},
                "validated": False,
                "notes": "Test annotation 2"
            }
        ]
        
        for ann_data in annotations_data:
            annotation = Annotation(**ann_data)
            test_db.add(annotation)
        test_db.commit()
        
        export_request = {
            "video_ids": [video.id],
            "format": "json",
            "include_validated_only": False
        }
        
        response = test_client.post("/api/annotations/export", json=export_request)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["format"] == "json"
        assert data["count"] == 2
        assert "data" in data
        
        exported_annotations = data["data"]
        assert len(exported_annotations) == 2
        
        # Verify exported data structure
        first_annotation = exported_annotations[0]
        assert "id" in first_annotation
        assert first_annotation["video_id"] == video.id
        assert first_annotation["frame_number"] == 100
        assert first_annotation["vru_type"] == "pedestrian"
        assert first_annotation["bounding_box"]["x"] == 100
    
    def test_export_annotations_validated_only(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test exporting only validated annotations"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create annotations with mixed validation status
        annotations_data = [
            {
                "video_id": video.id,
                "frame_number": 100,
                "timestamp": 3.33,
                "vru_type": "pedestrian",
                "bounding_box": {"x": 100, "y": 100, "width": 50, "height": 80},
                "validated": True
            },
            {
                "video_id": video.id,
                "frame_number": 200,
                "timestamp": 6.67,
                "vru_type": "cyclist",
                "bounding_box": {"x": 200, "y": 200, "width": 60, "height": 90},
                "validated": False
            }
        ]
        
        for ann_data in annotations_data:
            annotation = Annotation(**ann_data)
            test_db.add(annotation)
        test_db.commit()
        
        export_request = {
            "video_ids": [video.id],
            "format": "json",
            "include_validated_only": True
        }
        
        response = test_client.post("/api/annotations/export", json=export_request)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["count"] == 1  # Only validated annotation
        exported_annotations = data["data"]
        assert len(exported_annotations) == 1
        assert exported_annotations[0]["validated"] is True


class TestAnnotationErrorHandling:
    """Test annotation error handling scenarios"""
    
    def test_create_annotation_nonexistent_video(self, test_client: TestClient):
        """Test creating annotation for non-existent video"""
        annotation_data = {
            "videoId": "non-existent-video",
            "frameNumber": 120,
            "timestamp": 4.0,
            "vruType": "pedestrian",
            "boundingBox": {"x": 100, "y": 150, "width": 50, "height": 100}
        }
        
        response = test_client.post("/api/annotations/", json=annotation_data)
        
        assert response.status_code == 422
        error_data = response.json()
        assert "does not exist" in error_data["detail"]["errors"][0].lower()
    
    def test_annotation_bounding_box_validation(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test bounding box validation edge cases"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Test zero dimensions
        annotation_data = {
            "videoId": video.id,
            "frameNumber": 120,
            "timestamp": 4.0,
            "vruType": "pedestrian",
            "boundingBox": {
                "x": 100,
                "y": 150,
                "width": 0,  # Invalid zero width
                "height": 0  # Invalid zero height
            }
        }
        
        response = test_client.post("/api/annotations/", json=annotation_data)
        
        assert response.status_code == 422
        error_data = response.json()
        assert any("dimensions must be positive" in error.lower() for error in error_data["detail"]["errors"])
    
    def test_annotation_timestamp_validation(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test timestamp validation"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Test end_timestamp before start_timestamp
        annotation_data = {
            "videoId": video.id,
            "frameNumber": 120,
            "timestamp": 10.0,
            "endTimestamp": 5.0,  # Before start timestamp
            "vruType": "pedestrian",
            "boundingBox": {"x": 100, "y": 150, "width": 50, "height": 100}
        }
        
        response = test_client.post("/api/annotations/", json=annotation_data)
        
        assert response.status_code == 422
        error_data = response.json()
        assert any("end timestamp must be greater" in error.lower() for error in error_data["detail"]["errors"])
    
    def test_database_error_handling(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test database error handling"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Mock database error
        with patch('src.annotation_crud_endpoints.db.add') as mock_add:
            mock_add.side_effect = Exception("Database connection error")
            
            annotation_data = {
                "videoId": video.id,
                "frameNumber": 120,
                "timestamp": 4.0,
                "vruType": "pedestrian",
                "boundingBox": {"x": 100, "y": 150, "width": 50, "height": 100}
            }
            
            response = test_client.post("/api/annotations/", json=annotation_data)
            
            assert response.status_code == 500
            error_data = response.json()
            assert "database error" in error_data["detail"].lower()


@pytest.mark.integration
class TestAnnotationWorkflow:
    """Integration tests for complete annotation workflows"""
    
    def test_complete_annotation_lifecycle(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test complete annotation lifecycle: create, read, update, validate, delete"""
        # Setup
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # 1. Create annotation
        create_data = {
            "videoId": video.id,
            "frameNumber": 120,
            "timestamp": 4.0,
            "vruType": "pedestrian",
            "boundingBox": {"x": 100, "y": 150, "width": 50, "height": 100, "confidence": 0.8},
            "annotator": "annotator-1",
            "validated": False,
            "notes": "Initial annotation"
        }
        
        create_response = test_client.post("/api/annotations/", json=create_data)
        assert create_response.status_code == 201
        annotation_id = create_response.json()["id"]
        
        # 2. Read annotation
        get_response = test_client.get(f"/api/annotations/{annotation_id}")
        assert get_response.status_code == 200
        annotation_data = get_response.json()
        assert annotation_data["validated"] is False
        assert annotation_data["annotator"] == "annotator-1"
        
        # 3. Update annotation
        update_data = {
            "boundingBox": {"x": 105, "y": 155, "width": 55, "height": 105, "confidence": 0.9},
            "notes": "Refined bounding box",
            "annotator": "reviewer-1"
        }
        
        update_response = test_client.put(f"/api/annotations/{annotation_id}", json=update_data)
        assert update_response.status_code == 200
        updated_data = update_response.json()
        assert updated_data["boundingBox"]["x"] == 105
        assert updated_data["boundingBox"]["confidence"] == 0.9
        assert updated_data["annotator"] == "reviewer-1"
        
        # 4. Validate annotation
        validate_data = {"validated": True, "annotator": "validator-1"}
        validate_response = test_client.put(f"/api/annotations/{annotation_id}", json=validate_data)
        assert validate_response.status_code == 200
        validated_data = validate_response.json()
        assert validated_data["validated"] is True
        assert validated_data["annotator"] == "validator-1"
        
        # 5. Verify in statistics
        stats_response = test_client.get(f"/api/annotations/stats/summary?video_id={video.id}")
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert stats_data["total_annotations"] == 1
        assert stats_data["validated_annotations"] == 1
        assert stats_data["validation_rate"] == 1.0
        
        # 6. Export annotation
        export_request = {
            "video_ids": [video.id],
            "format": "json",
            "include_validated_only": True
        }
        export_response = test_client.post("/api/annotations/export", json=export_request)
        assert export_response.status_code == 200
        export_data = export_response.json()
        assert export_data["count"] == 1
        
        # 7. Delete annotation
        delete_response = test_client.delete(f"/api/annotations/{annotation_id}")
        assert delete_response.status_code == 204
        
        # 8. Verify deletion
        get_after_delete = test_client.get(f"/api/annotations/{annotation_id}")
        assert get_after_delete.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])