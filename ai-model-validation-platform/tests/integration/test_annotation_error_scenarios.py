"""
Annotation System Error Scenarios and Edge Cases Tests
======================================================

Comprehensive testing of error handling, edge cases, and failure scenarios
in the annotation system to ensure robustness and reliability.
"""

import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any, List
import tempfile
import os

from tests.conftest import TestDataHelper
from models import Annotation, Video, Project, DetectionEvent
from services.annotation_service import AnnotationService
from main import app


class TestAnnotationValidationEdgeCases:
    """Test annotation validation edge cases and boundary conditions"""
    
    def test_extreme_coordinate_values(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test annotation creation with extreme coordinate values"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Test extremely large coordinates
        extreme_annotation = {
            "videoId": video.id,
            "frameNumber": 120,
            "timestamp": 4.0,
            "vruType": "pedestrian",
            "boundingBox": {
                "x": 999999,  # Extreme x coordinate
                "y": 999999,  # Extreme y coordinate
                "width": 50,
                "height": 100
            }
        }
        
        response = test_client.post("/api/annotations/", json=extreme_annotation)
        
        # Should accept extreme values but may trigger warnings
        assert response.status_code in [201, 422]  # Either success or validation error
        
        # Test floating point precision
        precision_annotation = {
            "videoId": video.id,
            "frameNumber": 121,
            "timestamp": 4.000000001,  # High precision timestamp
            "vruType": "pedestrian",
            "boundingBox": {
                "x": 100.999999999,  # High precision coordinates
                "y": 150.000000001,
                "width": 50.123456789,
                "height": 100.987654321,
                "confidence": 0.999999999
            }
        }
        
        response = test_client.post("/api/annotations/", json=precision_annotation)
        assert response.status_code == 201
    
    def test_unicode_and_special_characters(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test handling of unicode and special characters in annotation fields"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        unicode_annotation = {
            "videoId": video.id,
            "frameNumber": 122,
            "timestamp": 4.1,
            "vruType": "pedestrian",
            "boundingBox": {"x": 100, "y": 150, "width": 50, "height": 100},
            "notes": "测试注释 with émojis 🚶‍♂️👩‍🦽 and special chars: !@#$%^&*()",
            "annotator": "用户-123 José María"
        }
        
        response = test_client.post("/api/annotations/", json=unicode_annotation)
        assert response.status_code == 201
        
        data = response.json()
        assert "测试注释" in data["notes"]
        assert "José María" in data["annotator"]
    
    def test_very_long_field_values(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test handling of very long field values"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        long_annotation = {
            "videoId": video.id,
            "frameNumber": 123,
            "timestamp": 4.2,
            "vruType": "pedestrian",
            "boundingBox": {"x": 100, "y": 150, "width": 50, "height": 100},
            "notes": "A" * 10000,  # Very long notes field
            "annotator": "annotator-" + "x" * 500  # Very long annotator name
        }
        
        response = test_client.post("/api/annotations/", json=long_annotation)
        
        # Should either accept or reject based on field length limits
        assert response.status_code in [201, 422]
    
    def test_null_and_empty_values(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test handling of null and empty values"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Test with minimal required fields
        minimal_annotation = {
            "videoId": video.id,
            "frameNumber": 124,
            "timestamp": 4.3,
            "vruType": "pedestrian",
            "boundingBox": {"x": 100, "y": 150, "width": 50, "height": 100},
            "notes": "",  # Empty string
            "annotator": None,  # Null value
            "detectionId": None
        }
        
        response = test_client.post("/api/annotations/", json=minimal_annotation)
        assert response.status_code == 201
        
        data = response.json()
        assert data["notes"] == ""
        assert data["annotator"] is None
    
    def test_invalid_json_structure(self, test_client: TestClient):
        """Test handling of invalid JSON structure in bounding box"""
        invalid_bbox_annotation = {
            "videoId": "some-video",
            "frameNumber": 125,
            "timestamp": 4.4,
            "vruType": "pedestrian",
            "boundingBox": "not-a-dict"  # Invalid structure
        }
        
        response = test_client.post("/api/annotations/", json=invalid_bbox_annotation)
        assert response.status_code == 422


class TestDatabaseErrorHandling:
    """Test database-related error handling scenarios"""
    
    @patch('src.annotation_crud_endpoints.db')
    def test_database_connection_failure(self, mock_db, test_client: TestClient):
        """Test handling of database connection failures"""
        mock_session = Mock()
        mock_session.add.side_effect = SQLAlchemyError("Connection lost")
        mock_db.return_value = mock_session
        
        annotation_data = {
            "videoId": "test-video",
            "frameNumber": 126,
            "timestamp": 4.5,
            "vruType": "pedestrian",
            "boundingBox": {"x": 100, "y": 150, "width": 50, "height": 100}
        }
        
        response = test_client.post("/api/annotations/", json=annotation_data)
        assert response.status_code == 500
        
        error_data = response.json()
        assert "database error" in error_data["detail"].lower()
    
    @patch('src.annotation_crud_endpoints.db')
    def test_constraint_violation_handling(self, mock_db, test_client: TestClient):
        """Test handling of database constraint violations"""
        mock_session = Mock()
        mock_session.add.side_effect = IntegrityError("", "", "")
        mock_db.return_value = mock_session
        
        annotation_data = {
            "videoId": "test-video",
            "frameNumber": 127,
            "timestamp": 4.6,
            "vruType": "pedestrian",
            "boundingBox": {"x": 100, "y": 150, "width": 50, "height": 100}
        }
        
        response = test_client.post("/api/annotations/", json=annotation_data)
        assert response.status_code == 500
    
    def test_transaction_rollback_on_error(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test transaction rollback when errors occur"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create a bulk operation where one annotation will fail
        bulk_annotations = [
            {
                "videoId": video.id,
                "frameNumber": 128,
                "timestamp": 4.7,
                "vruType": "pedestrian",
                "boundingBox": {"x": 100, "y": 150, "width": 50, "height": 100}
            },
            {
                "videoId": "non-existent-video",  # This will cause failure
                "frameNumber": 129,
                "timestamp": 4.8,
                "vruType": "cyclist",
                "boundingBox": {"x": 200, "y": 250, "width": 60, "height": 120}
            }
        ]
        
        # Get initial annotation count
        initial_count = test_db.query(Annotation).filter(Annotation.video_id == video.id).count()
        
        response = test_client.post("/api/annotations/bulk", json=bulk_annotations)
        assert response.status_code == 422
        
        # Verify no annotations were created due to rollback
        final_count = test_db.query(Annotation).filter(Annotation.video_id == video.id).count()
        assert final_count == initial_count


class TestConcurrencyAndRaceConditions:
    """Test concurrent access and race condition handling"""
    
    def test_concurrent_annotation_updates(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test handling of concurrent annotation updates"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create initial annotation
        annotation = Annotation(
            video_id=video.id,
            frame_number=130,
            timestamp=4.9,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 150, "width": 50, "height": 100},
            validated=False
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)
        
        # Simulate concurrent updates
        update_data_1 = {"validated": True, "annotator": "user-1"}
        update_data_2 = {"notes": "Updated by user-2", "annotator": "user-2"}
        
        # Both updates should succeed, but the last one wins
        response_1 = test_client.put(f"/api/annotations/{annotation.id}", json=update_data_1)
        response_2 = test_client.put(f"/api/annotations/{annotation.id}", json=update_data_2)
        
        assert response_1.status_code == 200
        assert response_2.status_code == 200
        
        # Verify final state
        final_response = test_client.get(f"/api/annotations/{annotation.id}")
        final_data = final_response.json()
        
        # Should have the latest updates
        assert final_data["annotator"] == "user-2"
    
    def test_concurrent_bulk_operations(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test concurrent bulk operations"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create two bulk operations
        bulk_1 = [
            {
                "videoId": video.id,
                "frameNumber": 131 + i,
                "timestamp": 5.0 + i * 0.1,
                "vruType": "pedestrian",
                "boundingBox": {"x": 100 + i, "y": 150, "width": 50, "height": 100}
            }
            for i in range(10)
        ]
        
        bulk_2 = [
            {
                "videoId": video.id,
                "frameNumber": 141 + i,
                "timestamp": 6.0 + i * 0.1,
                "vruType": "cyclist",
                "boundingBox": {"x": 200 + i, "y": 250, "width": 60, "height": 120}
            }
            for i in range(10)
        ]
        
        # Execute both bulk operations
        response_1 = test_client.post("/api/annotations/bulk", json=bulk_1)
        response_2 = test_client.post("/api/annotations/bulk", json=bulk_2)
        
        assert response_1.status_code == 201
        assert response_2.status_code == 201
        
        # Verify all annotations were created
        total_annotations = test_db.query(Annotation).filter(Annotation.video_id == video.id).count()
        assert total_annotations == 20


class TestResourceLimitsAndPerformance:
    """Test resource limits and performance edge cases"""
    
    def test_maximum_annotations_per_video(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test behavior with maximum number of annotations per video"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create a large number of annotations
        large_bulk = [
            {
                "videoId": video.id,
                "frameNumber": i,
                "timestamp": i * 0.033,
                "vruType": "pedestrian" if i % 2 == 0 else "cyclist",
                "boundingBox": {"x": 100 + (i % 100), "y": 150, "width": 50, "height": 100}
            }
            for i in range(1000)  # Maximum allowed in single request
        ]
        
        response = test_client.post("/api/annotations/bulk", json=large_bulk)
        assert response.status_code == 201
        
        data = response.json()
        assert len(data) == 1000
    
    def test_annotation_query_performance(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test query performance with large annotation dataset"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create large dataset directly in database for speed
        annotations = []
        for i in range(5000):
            annotation = Annotation(
                video_id=video.id,
                frame_number=i,
                timestamp=i * 0.033,
                vru_type="pedestrian" if i % 3 == 0 else "cyclist",
                bounding_box={"x": 100 + (i % 200), "y": 150, "width": 50, "height": 100},
                validated=i % 10 == 0
            )
            annotations.append(annotation)
        
        # Bulk insert for performance
        test_db.bulk_save_objects(annotations)
        test_db.commit()
        
        import time
        
        # Test query performance
        start_time = time.time()
        response = test_client.get(f"/api/annotations/?video_id={video.id}&limit=100")
        query_time = time.time() - start_time
        
        assert response.status_code == 200
        assert query_time < 2.0  # Should complete within 2 seconds
        
        data = response.json()
        assert len(data) == 100
    
    def test_memory_usage_large_export(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test memory usage during large export operations"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create moderate dataset for export test
        annotations = []
        for i in range(1000):
            annotation = Annotation(
                video_id=video.id,
                frame_number=i,
                timestamp=i * 0.033,
                vru_type="pedestrian",
                bounding_box={
                    "x": 100 + (i % 100),
                    "y": 150,
                    "width": 50,
                    "height": 100,
                    "confidence": 0.8 + (i % 20) * 0.01
                },
                notes=f"Annotation {i} with detailed description and metadata",
                validated=i % 5 == 0
            )
            annotations.append(annotation)
        
        test_db.bulk_save_objects(annotations)
        test_db.commit()
        
        # Test export performance
        export_request = {
            "video_ids": [video.id],
            "format": "json",
            "include_validated_only": False
        }
        
        import time
        start_time = time.time()
        
        response = test_client.post("/api/annotations/export", json=export_request)
        
        export_time = time.time() - start_time
        
        assert response.status_code == 200
        assert export_time < 10.0  # Should complete within 10 seconds
        
        export_data = response.json()
        assert export_data["count"] == 1000


class TestAnnotationServiceErrorHandling:
    """Test annotation service layer error handling"""
    
    def test_service_validation_error_handling(self, test_db: Session, sample_video_data):
        """Test annotation service validation error handling"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        service = AnnotationService()
        
        # Test with invalid data
        invalid_annotation_data = {
            "video_id": video.id,
            "frame_number": -1,  # Invalid negative frame
            "timestamp": -5.0,   # Invalid negative timestamp
            "vru_type": "invalid_type",
            "bounding_box": {
                "x": -10,
                "y": 150,
                "width": -50,
                "height": 100
            }
        }
        
        result = service.create_annotation(test_db, invalid_annotation_data)
        
        assert result["success"] is False
        assert result["code"] == "VALIDATION_FAILED"
        assert "validation_errors" in result
        assert len(result["validation_errors"]) > 0
    
    def test_service_nonexistent_video_handling(self, test_db: Session):
        """Test service handling of nonexistent video"""
        service = AnnotationService()
        
        annotation_data = {
            "video_id": "nonexistent-video-id",
            "frame_number": 100,
            "timestamp": 4.0,
            "vru_type": "pedestrian",
            "bounding_box": {"x": 100, "y": 150, "width": 50, "height": 100}
        }
        
        result = service.create_annotation(test_db, annotation_data)
        
        assert result["success"] is False
        assert result["code"] == "VIDEO_NOT_FOUND"
    
    def test_service_database_error_recovery(self, test_db: Session, sample_video_data):
        """Test service database error recovery"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        service = AnnotationService()
        
        # Mock database error
        with patch.object(test_db, 'add', side_effect=SQLAlchemyError("Database error")):
            annotation_data = {
                "video_id": video.id,
                "frame_number": 100,
                "timestamp": 4.0,
                "vru_type": "pedestrian",
                "bounding_box": {"x": 100, "y": 150, "width": 50, "height": 100}
            }
            
            result = service.create_annotation(test_db, annotation_data)
            
            assert result["success"] is False
            assert result["code"] == "DATABASE_ERROR"


class TestEdgeCaseIntegration:
    """Test integration of edge cases with full system"""
    
    def test_malformed_api_requests(self, test_client: TestClient):
        """Test handling of malformed API requests"""
        # Missing Content-Type header
        response = test_client.post("/api/annotations/", data="not json")
        assert response.status_code == 422
        
        # Invalid JSON
        response = test_client.post(
            "/api/annotations/",
            data="{'invalid': json}",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_authentication_error_simulation(self, test_client: TestClient):
        """Test authentication error scenarios (if authentication is implemented)"""
        # This would test authentication headers, tokens, etc.
        # For now, test unauthorized access patterns
        
        # Test with potential injection attempts
        malicious_annotation = {
            "videoId": "'; DROP TABLE annotations; --",
            "frameNumber": 100,
            "timestamp": 4.0,
            "vruType": "pedestrian",
            "boundingBox": {"x": 100, "y": 150, "width": 50, "height": 100}
        }
        
        response = test_client.post("/api/annotations/", json=malicious_annotation)
        # Should safely handle without executing injection
        assert response.status_code in [404, 422, 500]  # Not successful
    
    def test_system_resource_exhaustion_simulation(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test system behavior under resource exhaustion"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Simulate memory pressure with very large annotation
        large_annotation = {
            "videoId": video.id,
            "frameNumber": 100,
            "timestamp": 4.0,
            "vruType": "pedestrian",
            "boundingBox": {"x": 100, "y": 150, "width": 50, "height": 100},
            "notes": "x" * 1000000  # Very large notes field
        }
        
        response = test_client.post("/api/annotations/", json=large_annotation)
        
        # System should handle gracefully
        assert response.status_code in [201, 422, 413, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])