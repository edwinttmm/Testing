"""
Test Suite for Annotation API Routes
SPARC TDD Implementation - Testing REST endpoints
"""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

# We'll mock the FastAPI app for testing
from src.routes.annotation_routes import router


class TestAnnotationRoutes:
    """Test annotation API endpoints"""
    
    @pytest.fixture
    def mock_app(self):
        """Create mock FastAPI app for testing"""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return app
    
    @pytest.fixture
    def client(self, mock_app):
        """Create test client"""
        return TestClient(mock_app)
    
    @pytest.fixture
    def valid_annotation_data(self):
        return {
            "video_id": "test-video-id",
            "frame_number": 100,
            "timestamp": 3.33,
            "vru_type": "pedestrian",
            "bounding_box": {
                "x": 100,
                "y": 200,
                "width": 50,
                "height": 100
            },
            "annotator": "test_user"
        }
    
    def test_create_annotation_success(self, client, valid_annotation_data):
        """Test successful annotation creation via API"""
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.annotation_service.create_annotation') as mock_create:
                mock_create.return_value = {
                    "success": True,
                    "annotation": {"id": "test-annotation-id", **valid_annotation_data},
                    "validation_warnings": [],
                    "validation_metadata": {}
                }
                
                response = client.post("/api/annotations/", json=valid_annotation_data)
                
                assert response.status_code == 201
                data = response.json()
                assert data["message"] == "Annotation created successfully"
                assert "data" in data
                assert data["data"]["id"] == "test-annotation-id"
    
    def test_create_annotation_validation_error(self, client, valid_annotation_data):
        """Test annotation creation with validation errors"""
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.annotation_service.create_annotation') as mock_create:
                mock_create.return_value = {
                    "success": False,
                    "error": "Validation failed",
                    "code": "VALIDATION_FAILED",
                    "validation_errors": ["Invalid bounding box"],
                    "validation_warnings": []
                }
                
                response = client.post("/api/annotations/", json=valid_annotation_data)
                
                assert response.status_code == 422
                data = response.json()
                assert "validation_errors" in data["detail"]
    
    def test_create_annotation_invalid_vru_type(self, client, valid_annotation_data):
        """Test annotation creation with invalid VRU type"""
        invalid_data = valid_annotation_data.copy()
        invalid_data["vru_type"] = "invalid_type"
        
        response = client.post("/api/annotations/", json=invalid_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "vru_type" in str(data["detail"])
    
    def test_create_annotation_invalid_bounding_box(self, client, valid_annotation_data):
        """Test annotation creation with invalid bounding box"""
        invalid_data = valid_annotation_data.copy()
        invalid_data["bounding_box"]["width"] = -10  # Negative width
        
        response = client.post("/api/annotations/", json=invalid_data)
        
        assert response.status_code == 422
    
    def test_get_annotation_success(self, client):
        """Test successful annotation retrieval"""
        annotation_id = "test-annotation-id"
        
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.annotation_service.get_annotation') as mock_get:
                mock_get.return_value = {
                    "id": annotation_id,
                    "vru_type": "pedestrian",
                    "validated": True
                }
                
                response = client.get(f"/api/annotations/{annotation_id}")
                
                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Annotation retrieved successfully"
                assert data["data"]["id"] == annotation_id
    
    def test_get_annotation_not_found(self, client):
        """Test annotation retrieval with non-existent ID"""
        annotation_id = "non-existent-id"
        
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.annotation_service.get_annotation') as mock_get:
                mock_get.return_value = None
                
                response = client.get(f"/api/annotations/{annotation_id}")
                
                assert response.status_code == 404
    
    def test_update_annotation_success(self, client):
        """Test successful annotation update"""
        annotation_id = "test-annotation-id"
        update_data = {
            "validated": True,
            "notes": "Updated annotation"
        }
        
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.annotation_service.update_annotation') as mock_update:
                mock_update.return_value = {
                    "success": True,
                    "annotation": {"id": annotation_id, "validated": True},
                    "validation_warnings": []
                }
                
                response = client.put(f"/api/annotations/{annotation_id}", json=update_data)
                
                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Annotation updated successfully"
    
    def test_delete_annotation_success(self, client):
        """Test successful annotation deletion"""
        annotation_id = "test-annotation-id"
        
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.annotation_service.delete_annotation') as mock_delete:
                mock_delete.return_value = {
                    "success": True,
                    "message": f"Annotation {annotation_id} deleted successfully"
                }
                
                response = client.delete(f"/api/annotations/{annotation_id}")
                
                assert response.status_code == 200
                data = response.json()
                assert "deleted successfully" in data["message"]
    
    def test_get_video_annotations_with_filters(self, client):
        """Test getting video annotations with query filters"""
        video_id = "test-video-id"
        
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.annotation_service.get_video_annotations') as mock_get_annotations:
                mock_get_annotations.return_value = {
                    "success": True,
                    "annotations": [{"id": "ann1"}, {"id": "ann2"}],
                    "count": 2,
                    "filters_applied": {"vru_type": "pedestrian"}
                }
                
                response = client.get(
                    f"/api/annotations/video/{video_id}",
                    params={"vru_type": "pedestrian", "validated": True}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["count"] == 2
                assert "filters_applied" in data
    
    def test_get_annotation_statistics(self, client):
        """Test getting annotation statistics for a video"""
        video_id = "test-video-id"
        
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.annotation_service.get_annotation_statistics') as mock_stats:
                mock_stats.return_value = {
                    "success": True,
                    "statistics": {
                        "total_annotations": 10,
                        "by_vru_type": {"pedestrian": 6, "cyclist": 4},
                        "validation_status": {"validated": 8, "pending": 2}
                    }
                }
                
                response = client.get(f"/api/annotations/video/{video_id}/statistics")
                
                assert response.status_code == 200
                data = response.json()
                assert data["data"]["total_annotations"] == 10
    
    def test_validate_annotation_sequence(self, client):
        """Test annotation sequence validation"""
        video_id = "test-video-id"
        
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.annotation_service.validate_annotation_sequence') as mock_validate:
                mock_validate.return_value = {
                    "success": True,
                    "validation": {
                        "temporal_consistency": {"consistency": 0.9},
                        "geometric_overlaps": [],
                        "overall_score": 0.85
                    }
                }
                
                response = client.get(f"/api/annotations/video/{video_id}/validate")
                
                assert response.status_code == 200
                data = response.json()
                assert data["data"]["overall_score"] == 0.85
    
    def test_bulk_update_annotations(self, client):
        """Test bulk updating annotations"""
        bulk_data = {
            "annotation_ids": ["ann1", "ann2", "ann3"],
            "update_data": {"validated": True, "annotator": "bulk_user"}
        }
        
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.annotation_service.bulk_update_annotations') as mock_bulk:
                mock_bulk.return_value = {
                    "success": True,
                    "updated_count": 3,
                    "total_requested": 3,
                    "errors": []
                }
                
                response = client.put("/api/annotations/bulk-update", json=bulk_data)
                
                assert response.status_code == 200
                data = response.json()
                assert "3/3 annotations updated" in data["message"]
    
    def test_create_annotation_session(self, client):
        """Test annotation session creation"""
        session_data = {
            "video_id": "test-video-id",
            "project_id": "test-project-id",
            "annotator_id": "test-user",
            "total_frames": 900
        }
        
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.session_service.create_session') as mock_create:
                mock_create.return_value = {
                    "success": True,
                    "session": {"id": "test-session-id", **session_data}
                }
                
                response = client.post("/api/annotations/sessions", json=session_data)
                
                assert response.status_code == 201
                data = response.json()
                assert data["message"] == "Annotation session created successfully"
    
    def test_update_session_progress(self, client):
        """Test updating session progress"""
        session_id = "test-session-id"
        progress_data = {
            "current_frame": 450,
            "total_detections": 25,
            "validated_detections": 20
        }
        
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.session_service.update_session_progress') as mock_update:
                mock_update.return_value = {
                    "success": True,
                    "session": {"id": session_id, "current_frame": 450}
                }
                
                response = client.put(
                    f"/api/annotations/sessions/{session_id}/progress",
                    json=progress_data
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Session progress updated successfully"
    
    def test_health_check(self, client):
        """Test annotation system health check"""
        response = client.get("/api/annotations/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "annotation_api"


class TestAnnotationRouteValidation:
    """Test API route validation and error handling"""
    
    @pytest.fixture
    def mock_app(self):
        """Create mock FastAPI app for testing"""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return app
    
    @pytest.fixture
    def client(self, mock_app):
        """Create test client"""
        return TestClient(mock_app)
    
    def test_create_annotation_missing_required_fields(self, client):
        """Test validation of missing required fields"""
        incomplete_data = {
            "video_id": "test-video-id"
            # Missing frame_number, timestamp, vru_type, bounding_box
        }
        
        response = client.post("/api/annotations/", json=incomplete_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_create_annotation_invalid_data_types(self, client):
        """Test validation of incorrect data types"""
        invalid_data = {
            "video_id": "test-video-id",
            "frame_number": "not_a_number",  # Should be int
            "timestamp": "not_a_number",     # Should be float
            "vru_type": "pedestrian",
            "bounding_box": {
                "x": 100,
                "y": 200,
                "width": 50,
                "height": 100
            }
        }
        
        response = client.post("/api/annotations/", json=invalid_data)
        
        assert response.status_code == 422
    
    def test_create_annotation_negative_coordinates(self, client):
        """Test validation of negative coordinates"""
        invalid_data = {
            "video_id": "test-video-id",
            "frame_number": 100,
            "timestamp": 3.33,
            "vru_type": "pedestrian",
            "bounding_box": {
                "x": -10,    # Negative x
                "y": 200,
                "width": 50,
                "height": 100
            }
        }
        
        response = client.post("/api/annotations/", json=invalid_data)
        
        assert response.status_code == 422
    
    def test_create_annotation_zero_dimensions(self, client):
        """Test validation of zero dimensions"""
        invalid_data = {
            "video_id": "test-video-id",
            "frame_number": 100,
            "timestamp": 3.33,
            "vru_type": "pedestrian",
            "bounding_box": {
                "x": 100,
                "y": 200,
                "width": 0,      # Zero width
                "height": 100
            }
        }
        
        response = client.post("/api/annotations/", json=invalid_data)
        
        assert response.status_code == 422
    
    def test_create_annotation_invalid_end_timestamp(self, client):
        """Test validation of end timestamp"""
        invalid_data = {
            "video_id": "test-video-id",
            "frame_number": 100,
            "timestamp": 10.0,
            "end_timestamp": 5.0,  # End before start
            "vru_type": "pedestrian",
            "bounding_box": {
                "x": 100,
                "y": 200,
                "width": 50,
                "height": 100
            }
        }
        
        response = client.post("/api/annotations/", json=invalid_data)
        
        assert response.status_code == 422
    
    def test_path_parameter_validation(self, client):
        """Test path parameter validation"""
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.annotation_service.get_annotation') as mock_get:
                mock_get.return_value = None
                
                # Test with valid UUID-like string
                response = client.get("/api/annotations/123e4567-e89b-12d3-a456-426614174000")
                assert response.status_code == 404  # Not found but valid format
                
                # Test with invalid format (should still work as string)
                response = client.get("/api/annotations/invalid-id")
                assert response.status_code == 404
    
    def test_query_parameter_validation(self, client):
        """Test query parameter validation"""
        video_id = "test-video-id"
        
        with patch('src.routes.annotation_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            
            with patch('src.routes.annotation_routes.annotation_service.get_video_annotations') as mock_get:
                mock_get.return_value = {
                    "success": True,
                    "annotations": [],
                    "count": 0,
                    "filters_applied": {}
                }
                
                # Test with invalid frame numbers (negative)
                response = client.get(
                    f"/api/annotations/video/{video_id}",
                    params={"frame_start": -10}
                )
                assert response.status_code == 422
                
                # Test with invalid timestamps (negative)
                response = client.get(
                    f"/api/annotations/video/{video_id}",
                    params={"timestamp_start": -5.0}
                )
                assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])