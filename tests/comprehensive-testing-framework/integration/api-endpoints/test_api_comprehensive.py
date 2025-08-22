"""
Comprehensive API Endpoint Testing Suite
Complete testing coverage for all REST API endpoints with various scenarios
"""
import pytest
import json
import time
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch
import tempfile
import os

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import test configuration
import sys
sys.path.append('/home/user/Testing/tests/comprehensive-testing-framework/config')
from test_config import test_config

# Import application
sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')
from main import app
from database import SessionLocal
from models import Project, Video, TestSession, DetectionEvent, Annotation


class TestProjectEndpoints:
    """Test suite for project-related API endpoints"""
    
    def setup_method(self):
        """Set up test client and common test data"""
        self.client = TestClient(app)
        self.test_user_id = "test_user_123"
        
        self.valid_project_data = {
            "name": "Test Project API",
            "description": "Testing project API endpoints",
            "camera_model": "TestCam Pro",
            "camera_view": "Front-facing VRU",
            "lens_type": "Wide Angle",
            "resolution": "1920x1080",
            "frame_rate": 30,
            "signal_type": "GPIO",
            "owner_id": self.test_user_id
        }
    
    def test_create_project_success(self):
        """Test successful project creation"""
        response = self.client.post("/projects/", json=self.valid_project_data)
        
        assert response.status_code == 201
        
        project = response.json()
        assert project["name"] == self.valid_project_data["name"]
        assert project["status"] == "Active"
        assert project["owner_id"] == self.test_user_id
        assert "id" in project
        assert "created_at" in project
        
        return project["id"]
    
    def test_create_project_validation_errors(self):
        """Test project creation with validation errors"""
        # Test missing required fields
        invalid_data_cases = [
            # Missing name
            {**self.valid_project_data, "name": ""},
            # Missing camera_model
            {**self.valid_project_data, "camera_model": ""},
            # Invalid camera_view
            {**self.valid_project_data, "camera_view": "Invalid View"},
            # Invalid signal_type
            {**self.valid_project_data, "signal_type": "Invalid Signal"},
            # Invalid frame_rate
            {**self.valid_project_data, "frame_rate": -1},
            # Missing required fields
            {"name": "Incomplete Project"}
        ]
        
        for invalid_data in invalid_data_cases:
            response = self.client.post("/projects/", json=invalid_data)
            assert response.status_code == 422, f"Should fail validation for: {invalid_data}"
    
    def test_get_projects_list(self):
        """Test retrieving list of projects"""
        # Create multiple projects
        project_ids = []
        for i in range(3):
            project_data = {
                **self.valid_project_data,
                "name": f"Test Project {i}",
                "description": f"Description for project {i}"
            }
            response = self.client.post("/projects/", json=project_data)
            project_ids.append(response.json()["id"])
        
        # Get projects list
        response = self.client.get("/projects/")
        assert response.status_code == 200
        
        projects = response.json()
        assert len(projects) >= 3
        
        # Test pagination
        response_paged = self.client.get("/projects/?skip=0&limit=2")
        assert response_paged.status_code == 200
        paged_projects = response_paged.json()
        assert len(paged_projects) == 2
        
        # Test filtering by owner
        response_filtered = self.client.get(f"/projects/?owner_id={self.test_user_id}")
        assert response_filtered.status_code == 200
        filtered_projects = response_filtered.json()
        assert all(p["owner_id"] == self.test_user_id for p in filtered_projects)
    
    def test_get_project_by_id(self):
        """Test retrieving project by ID"""
        # Create project
        project_id = self.test_create_project_success()
        
        # Get project by ID
        response = self.client.get(f"/projects/{project_id}")
        assert response.status_code == 200
        
        project = response.json()
        assert project["id"] == project_id
        assert project["name"] == self.valid_project_data["name"]
        
        # Test non-existent project
        response = self.client.get("/projects/non-existent-id")
        assert response.status_code == 404
    
    def test_update_project(self):
        """Test updating project"""
        # Create project
        project_id = self.test_create_project_success()
        
        # Update project
        update_data = {
            "name": "Updated Project Name",
            "description": "Updated description",
            "status": "In Progress"
        }
        
        response = self.client.patch(f"/projects/{project_id}", json=update_data)
        assert response.status_code == 200
        
        updated_project = response.json()
        assert updated_project["name"] == update_data["name"]
        assert updated_project["description"] == update_data["description"]
        assert updated_project["status"] == update_data["status"]
        
        # Test invalid updates
        invalid_update = {"status": "Invalid Status"}
        response = self.client.patch(f"/projects/{project_id}", json=invalid_update)
        assert response.status_code == 422
    
    def test_delete_project(self):
        """Test project deletion"""
        # Create project
        project_id = self.test_create_project_success()
        
        # Delete project
        response = self.client.delete(f"/projects/{project_id}")
        assert response.status_code == 204
        
        # Verify project is deleted
        response = self.client.get(f"/projects/{project_id}")
        assert response.status_code == 404
        
        # Test deleting non-existent project
        response = self.client.delete("/projects/non-existent-id")
        assert response.status_code == 404
    
    def test_project_statistics(self):
        """Test project statistics endpoint"""
        # Create project with videos
        project_id = self.test_create_project_success()
        
        # Get project statistics
        response = self.client.get(f"/projects/{project_id}/statistics")
        assert response.status_code == 200
        
        stats = response.json()
        assert "video_count" in stats
        assert "total_duration" in stats
        assert "annotation_count" in stats
        assert "test_session_count" in stats


class TestVideoEndpoints:
    """Test suite for video-related API endpoints"""
    
    def setup_method(self):
        """Set up test client and create test project"""
        self.client = TestClient(app)
        
        # Create test project
        project_data = {
            "name": "Video Test Project",
            "description": "Project for testing video endpoints",
            "camera_model": "TestCam",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        response = self.client.post("/projects/", json=project_data)
        self.project_id = response.json()["id"]
    
    def test_video_upload_success(self):
        """Test successful video upload"""
        # Create test video file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video.write(b"fake video content for testing")
            temp_video_path = temp_video.name
        
        try:
            with open(temp_video_path, 'rb') as video_file:
                files = {"file": ("test_video.mp4", video_file, "video/mp4")}
                data = {"project_id": self.project_id}
                
                response = self.client.post("/videos/upload", files=files, data=data)
                assert response.status_code == 201
                
                video = response.json()
                assert video["filename"] == "test_video.mp4"
                assert video["project_id"] == self.project_id
                assert video["status"] == "uploaded"
                assert "id" in video
                
                return video["id"]
        
        finally:
            os.unlink(temp_video_path)
    
    def test_video_upload_validation_errors(self):
        """Test video upload with various validation errors"""
        # Test missing project_id
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video.write(b"test content")
            temp_video_path = temp_video.name
        
        try:
            with open(temp_video_path, 'rb') as video_file:
                files = {"file": ("test.mp4", video_file, "video/mp4")}
                
                response = self.client.post("/videos/upload", files=files)
                assert response.status_code == 422
        
        finally:
            os.unlink(temp_video_path)
        
        # Test invalid file type
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
            temp_file.write(b"not a video file")
            temp_file_path = temp_file.name
        
        try:
            with open(temp_file_path, 'rb') as invalid_file:
                files = {"file": ("test.txt", invalid_file, "text/plain")}
                data = {"project_id": self.project_id}
                
                response = self.client.post("/videos/upload", files=files, data=data)
                assert response.status_code == 400
        
        finally:
            os.unlink(temp_file_path)
        
        # Test non-existent project
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video.write(b"test content")
            temp_video_path = temp_video.name
        
        try:
            with open(temp_video_path, 'rb') as video_file:
                files = {"file": ("test.mp4", video_file, "video/mp4")}
                data = {"project_id": "non-existent-project"}
                
                response = self.client.post("/videos/upload", files=files, data=data)
                assert response.status_code == 404
        
        finally:
            os.unlink(temp_video_path)
    
    def test_get_videos_list(self):
        """Test retrieving list of videos"""
        # Upload multiple videos
        video_ids = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                temp_video.write(f"video content {i}".encode())
                temp_video_path = temp_video.name
            
            try:
                with open(temp_video_path, 'rb') as video_file:
                    files = {"file": (f"test_video_{i}.mp4", video_file, "video/mp4")}
                    data = {"project_id": self.project_id}
                    
                    response = self.client.post("/videos/upload", files=files, data=data)
                    video_ids.append(response.json()["id"])
            
            finally:
                os.unlink(temp_video_path)
        
        # Get videos list
        response = self.client.get("/videos/")
        assert response.status_code == 200
        
        videos = response.json()
        assert len(videos) >= 3
        
        # Test filtering by project
        response = self.client.get(f"/videos/?project_id={self.project_id}")
        assert response.status_code == 200
        
        project_videos = response.json()
        assert all(v["project_id"] == self.project_id for v in project_videos)
        assert len(project_videos) == 3
    
    def test_video_processing(self):
        """Test video processing workflow"""
        # Upload video
        video_id = self.test_video_upload_success()
        
        # Start processing
        response = self.client.post(f"/videos/{video_id}/process")
        assert response.status_code == 200
        
        # Check processing status
        response = self.client.get(f"/videos/{video_id}/status")
        assert response.status_code == 200
        
        status = response.json()
        assert "processing_status" in status
        assert status["processing_status"] in ["pending", "processing", "completed", "failed"]
        
        # Test processing non-existent video
        response = self.client.post("/videos/non-existent-id/process")
        assert response.status_code == 404
    
    def test_video_metadata_update(self):
        """Test updating video metadata"""
        # Upload video
        video_id = self.test_video_upload_success()
        
        # Update metadata
        metadata_update = {
            "duration": 120.5,
            "fps": 30.0,
            "resolution": "1920x1080"
        }
        
        response = self.client.patch(f"/videos/{video_id}", json=metadata_update)
        assert response.status_code == 200
        
        updated_video = response.json()
        assert updated_video["duration"] == metadata_update["duration"]
        assert updated_video["fps"] == metadata_update["fps"]
        assert updated_video["resolution"] == metadata_update["resolution"]
    
    def test_video_deletion(self):
        """Test video deletion"""
        # Upload video
        video_id = self.test_video_upload_success()
        
        # Delete video
        response = self.client.delete(f"/videos/{video_id}")
        assert response.status_code == 204
        
        # Verify video is deleted
        response = self.client.get(f"/videos/{video_id}")
        assert response.status_code == 404


class TestTestSessionEndpoints:
    """Test suite for test session API endpoints"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
        
        # Create test project
        project_data = {
            "name": "Test Session Project",
            "description": "Project for testing test sessions",
            "camera_model": "TestCam",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        response = self.client.post("/projects/", json=project_data)
        self.project_id = response.json()["id"]
        
        # Upload test video
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video.write(b"test video for sessions")
            temp_video_path = temp_video.name
        
        try:
            with open(temp_video_path, 'rb') as video_file:
                files = {"file": ("session_test.mp4", video_file, "video/mp4")}
                data = {"project_id": self.project_id}
                
                response = self.client.post("/videos/upload", files=files, data=data)
                self.video_id = response.json()["id"]
        
        finally:
            os.unlink(temp_video_path)
    
    def test_create_test_session(self):
        """Test test session creation"""
        session_data = {
            "name": "API Test Session",
            "project_id": self.project_id,
            "video_id": self.video_id,
            "tolerance_ms": 100,
            "test_criteria": {
                "min_accuracy": 0.85,
                "max_false_positives": 5
            }
        }
        
        response = self.client.post("/test-sessions/", json=session_data)
        assert response.status_code == 201
        
        session = response.json()
        assert session["name"] == session_data["name"]
        assert session["project_id"] == self.project_id
        assert session["video_id"] == self.video_id
        assert session["status"] == "created"
        
        return session["id"]
    
    def test_test_session_lifecycle(self):
        """Test complete test session lifecycle"""
        # Create session
        session_id = self.test_create_test_session()
        
        # Start session
        response = self.client.post(f"/test-sessions/{session_id}/start")
        assert response.status_code == 200
        
        # Check status
        response = self.client.get(f"/test-sessions/{session_id}")
        session = response.json()
        assert session["status"] == "running"
        
        # Add detection events
        events = [
            {
                "test_session_id": session_id,
                "timestamp": 1.5,
                "detection_type": "person",
                "confidence": 0.92,
                "bounding_box": {"x": 100, "y": 200, "width": 80, "height": 180}
            },
            {
                "test_session_id": session_id,
                "timestamp": 3.2,
                "detection_type": "vehicle",
                "confidence": 0.88,
                "bounding_box": {"x": 300, "y": 150, "width": 200, "height": 100}
            }
        ]
        
        for event_data in events:
            response = self.client.post("/detection-events/", json=event_data)
            assert response.status_code == 201
        
        # Complete session
        response = self.client.post(f"/test-sessions/{session_id}/complete")
        assert response.status_code == 200
        
        # Get results
        response = self.client.get(f"/test-sessions/{session_id}/results")
        assert response.status_code == 200
        
        results = response.json()
        assert "detection_count" in results
        assert results["detection_count"] == 2
    
    def test_test_session_validation_errors(self):
        """Test test session validation errors"""
        invalid_cases = [
            # Missing name
            {
                "project_id": self.project_id,
                "video_id": self.video_id,
                "tolerance_ms": 100
            },
            # Invalid tolerance
            {
                "name": "Invalid Session",
                "project_id": self.project_id,
                "video_id": self.video_id,
                "tolerance_ms": -50
            },
            # Non-existent project
            {
                "name": "Invalid Session",
                "project_id": "non-existent",
                "video_id": self.video_id,
                "tolerance_ms": 100
            }
        ]
        
        for invalid_data in invalid_cases:
            response = self.client.post("/test-sessions/", json=invalid_data)
            assert response.status_code in [422, 404]


class TestAnnotationEndpoints:
    """Test suite for annotation API endpoints"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
        
        # Create test project and video (reuse from previous tests)
        project_data = {
            "name": "Annotation Test Project",
            "description": "Project for testing annotations",
            "camera_model": "TestCam",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        response = self.client.post("/projects/", json=project_data)
        self.project_id = response.json()["id"]
        
        # Upload test video
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video.write(b"annotation test video")
            temp_video_path = temp_video.name
        
        try:
            with open(temp_video_path, 'rb') as video_file:
                files = {"file": ("annotation_test.mp4", video_file, "video/mp4")}
                data = {"project_id": self.project_id}
                
                response = self.client.post("/videos/upload", files=files, data=data)
                self.video_id = response.json()["id"]
        
        finally:
            os.unlink(temp_video_path)
        
        # Create annotation session
        session_data = {
            "name": "Test Annotation Session",
            "project_id": self.project_id,
            "video_id": self.video_id,
            "annotator_name": "test_annotator"
        }
        
        response = self.client.post("/annotation-sessions/", json=session_data)
        self.session_id = response.json()["id"]
    
    def test_create_annotation(self):
        """Test annotation creation"""
        annotation_data = {
            "session_id": self.session_id,
            "frame_number": 100,
            "timestamp": 3.33,
            "class_label": "person",
            "x": 100,
            "y": 200,
            "width": 80,
            "height": 180,
            "confidence": 0.95
        }
        
        response = self.client.post("/annotations/", json=annotation_data)
        assert response.status_code == 201
        
        annotation = response.json()
        assert annotation["class_label"] == "person"
        assert annotation["frame_number"] == 100
        assert annotation["confidence"] == 0.95
        
        return annotation["id"]
    
    def test_annotation_crud_operations(self):
        """Test complete annotation CRUD operations"""
        # Create
        annotation_id = self.test_create_annotation()
        
        # Read
        response = self.client.get(f"/annotations/{annotation_id}")
        assert response.status_code == 200
        
        annotation = response.json()
        assert annotation["id"] == annotation_id
        
        # Update
        update_data = {
            "confidence": 0.88,
            "class_label": "pedestrian"
        }
        
        response = self.client.patch(f"/annotations/{annotation_id}", json=update_data)
        assert response.status_code == 200
        
        updated_annotation = response.json()
        assert updated_annotation["confidence"] == 0.88
        assert updated_annotation["class_label"] == "pedestrian"
        
        # Delete
        response = self.client.delete(f"/annotations/{annotation_id}")
        assert response.status_code == 204
        
        # Verify deletion
        response = self.client.get(f"/annotations/{annotation_id}")
        assert response.status_code == 404
    
    def test_annotation_export(self):
        """Test annotation export functionality"""
        # Create multiple annotations
        annotations = []
        for i in range(3):
            annotation_data = {
                "session_id": self.session_id,
                "frame_number": 100 + i * 50,
                "timestamp": 3.33 + i * 1.67,
                "class_label": ["person", "vehicle", "bicycle"][i],
                "x": 100 + i * 100,
                "y": 200,
                "width": 80,
                "height": 180,
                "confidence": 0.9 - i * 0.1
            }
            
            response = self.client.post("/annotations/", json=annotation_data)
            annotations.append(response.json()["id"])
        
        # Export annotations
        export_data = {
            "format": "COCO",
            "include_metadata": True
        }
        
        response = self.client.post(f"/annotation-sessions/{self.session_id}/export", 
                                  json=export_data)
        assert response.status_code == 200
        
        exported_data = response.json()
        assert "annotations" in exported_data
        assert len(exported_data["annotations"]) == 3


class TestAPIPerformanceAndReliability:
    """Test API performance and reliability characteristics"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
    
    def test_api_response_times(self):
        """Test API response time performance"""
        # Test project creation performance
        project_data = {
            "name": "Performance Test Project",
            "description": "Testing API performance",
            "camera_model": "TestCam",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        start_time = time.time()
        response = self.client.post("/projects/", json=project_data)
        create_time = time.time() - start_time
        
        assert response.status_code == 201
        assert create_time < 2.0, f"Project creation too slow: {create_time}s"
        
        project_id = response.json()["id"]
        
        # Test project retrieval performance
        start_time = time.time()
        response = self.client.get(f"/projects/{project_id}")
        get_time = time.time() - start_time
        
        assert response.status_code == 200
        assert get_time < 0.5, f"Project retrieval too slow: {get_time}s"
    
    def test_concurrent_api_requests(self):
        """Test API behavior under concurrent load"""
        import threading
        import queue
        
        # Create project for testing
        project_data = {
            "name": "Concurrent Test Project",
            "description": "Testing concurrent requests",
            "camera_model": "TestCam",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        response = self.client.post("/projects/", json=project_data)
        project_id = response.json()["id"]
        
        # Concurrent GET requests
        results = queue.Queue()
        
        def make_request():
            try:
                response = self.client.get(f"/projects/{project_id}")
                results.put({"status": response.status_code, "success": True})
            except Exception as e:
                results.put({"status": 500, "success": False, "error": str(e)})
        
        # Start multiple concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Analyze results
        successes = 0
        while not results.empty():
            result = results.get()
            if result["success"] and result["status"] == 200:
                successes += 1
        
        # Should handle concurrent requests gracefully
        assert successes >= 8, f"Too many concurrent request failures: {successes}/10"
    
    def test_api_error_handling(self):
        """Test API error handling and status codes"""
        error_cases = [
            # 404 errors
            {"method": "GET", "url": "/projects/non-existent", "expected": 404},
            {"method": "GET", "url": "/videos/non-existent", "expected": 404},
            {"method": "DELETE", "url": "/projects/non-existent", "expected": 404},
            
            # 422 validation errors
            {"method": "POST", "url": "/projects/", "data": {}, "expected": 422},
            {"method": "POST", "url": "/projects/", "data": {"name": ""}, "expected": 422},
        ]
        
        for case in error_cases:
            if case["method"] == "GET":
                response = self.client.get(case["url"])
            elif case["method"] == "POST":
                response = self.client.post(case["url"], json=case.get("data", {}))
            elif case["method"] == "DELETE":
                response = self.client.delete(case["url"])
            
            assert response.status_code == case["expected"], \
                f"Expected {case['expected']}, got {response.status_code} for {case['method']} {case['url']}"
    
    def test_api_rate_limiting(self):
        """Test API rate limiting (if implemented)"""
        # This test assumes rate limiting might be implemented
        # Make many rapid requests to trigger rate limiting
        
        project_data = {
            "name": "Rate Limit Test",
            "description": "Testing rate limits",
            "camera_model": "TestCam",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        response = self.client.post("/projects/", json=project_data)
        project_id = response.json()["id"]
        
        # Make rapid requests
        responses = []
        for i in range(100):
            response = self.client.get(f"/projects/{project_id}")
            responses.append(response.status_code)
            
            if response.status_code == 429:  # Rate limit exceeded
                break
        
        # Check if rate limiting was applied
        rate_limited = any(status == 429 for status in responses)
        
        # Rate limiting is optional, so we just log the result
        if rate_limited:
            print("Rate limiting is active")
        else:
            print("No rate limiting detected")
    
    def test_api_input_sanitization(self):
        """Test API input sanitization and security"""
        # Test SQL injection attempts
        malicious_inputs = [
            "'; DROP TABLE projects; --",
            "<script>alert('xss')</script>",
            "' OR '1'='1",
            "../../../../etc/passwd",
            "null; rm -rf /",
        ]
        
        for malicious_input in malicious_inputs:
            project_data = {
                "name": malicious_input,
                "description": "Testing input sanitization",
                "camera_model": "TestCam",
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            }
            
            response = self.client.post("/projects/", json=project_data)
            
            # Should either succeed with sanitized input or fail validation
            assert response.status_code in [201, 422], \
                f"Unexpected response to malicious input: {response.status_code}"
            
            if response.status_code == 201:
                # If successful, verify input was sanitized
                project = response.json()
                assert project["name"] != malicious_input or \
                       len(project["name"]) != len(malicious_input), \
                       "Input not properly sanitized"


class TestAPIDocumentationCompliance:
    """Test API compliance with documentation and OpenAPI spec"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
    
    def test_openapi_schema_availability(self):
        """Test OpenAPI schema endpoint"""
        response = self.client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        
        # Verify key endpoints are documented
        paths = schema["paths"]
        assert "/projects/" in paths
        assert "/videos/upload" in paths
        assert "/test-sessions/" in paths
    
    def test_api_documentation_endpoint(self):
        """Test API documentation endpoint"""
        response = self.client.get("/docs")
        assert response.status_code == 200
        
        # Should return HTML documentation
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_health_check_endpoint(self):
        """Test health check endpoint"""
        response = self.client.get("/health")
        
        # Health endpoint might not exist, so check if it's implemented
        if response.status_code == 200:
            health_data = response.json()
            assert "status" in health_data
            assert health_data["status"] in ["healthy", "unhealthy"]
        elif response.status_code == 404:
            # Health endpoint not implemented, which is acceptable
            pass
        else:
            pytest.fail(f"Unexpected health check response: {response.status_code}")


# Test fixtures and utilities
@pytest.fixture(scope="module")
def test_db():
    """Module-scoped database fixture"""
    # This would set up a test database
    # Implementation depends on your database setup
    pass


@pytest.fixture
def auth_headers():
    """Fixture for authentication headers"""
    return {"Authorization": "Bearer test-token"}


def assert_response_schema(response_data: dict, expected_fields: list):
    """Helper function to validate response schema"""
    for field in expected_fields:
        assert field in response_data, f"Missing required field: {field}"


def generate_large_payload(size_mb: int) -> dict:
    """Generate large payload for testing"""
    large_string = "x" * (size_mb * 1024 * 1024)
    return {"large_data": large_string}


def time_api_call(client, method: str, url: str, **kwargs) -> tuple:
    """Time an API call and return response and duration"""
    start_time = time.time()
    
    if method.upper() == "GET":
        response = client.get(url, **kwargs)
    elif method.upper() == "POST":
        response = client.post(url, **kwargs)
    elif method.upper() == "PUT":
        response = client.put(url, **kwargs)
    elif method.upper() == "PATCH":
        response = client.patch(url, **kwargs)
    elif method.upper() == "DELETE":
        response = client.delete(url, **kwargs)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")
    
    duration = time.time() - start_time
    return response, duration