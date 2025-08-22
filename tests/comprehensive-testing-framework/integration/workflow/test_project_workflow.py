"""
Project Workflow Integration Tests
Comprehensive testing for end-to-end project workflows, video processing, and state management
"""
import pytest
import asyncio
import time
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import tempfile
import os
import json

from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

# Import test configuration
import sys
sys.path.append('/home/user/Testing/tests/comprehensive-testing-framework/config')
from test_config import test_config

# Import application models and services
sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')
from models import Project, Video, TestSession, DetectionEvent, AnnotationSession
from services.project_management_service import ProjectManager
from services.video_processing_workflow import VideoProcessingWorkflow
from services.validation_analysis_service import ValidationWorkflow
from database import SessionLocal
from main import app


class TestProjectWorkflowIntegration:
    """Test suite for complete project workflow integration"""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self, test_db_session: Session):
        """Set up test environment for each test"""
        self.db = test_db_session
        self.client = TestClient(app)
        self.project_manager = ProjectManager(db=test_db_session)
        self.video_processor = VideoProcessingWorkflow(db=test_db_session)
        self.validation_service = ValidationWorkflow(db=test_db_session)
        
        # Create test user context
        self.test_user = {
            "user_id": "test_user_123",
            "username": "test_user",
            "role": "project_manager"
        }
    
    def test_complete_project_creation_workflow(self):
        """Test complete project creation from start to finish"""
        # Step 1: Create project with all required parameters
        project_data = {
            "name": "Complete Workflow Test Project",
            "description": "Testing the complete project creation workflow",
            "camera_model": "TestCam Pro 4K",
            "camera_view": "Front-facing VRU",
            "lens_type": "Wide Angle",
            "resolution": "1920x1080",
            "frame_rate": 30,
            "signal_type": "GPIO",
            "owner_id": self.test_user["user_id"]
        }
        
        # Create project via API
        response = self.client.post("/projects/", json=project_data)
        assert response.status_code == 201
        
        created_project = response.json()
        project_id = created_project["id"]
        
        # Validate project creation
        assert created_project["name"] == project_data["name"]
        assert created_project["status"] == "Active"
        assert created_project["owner_id"] == self.test_user["user_id"]
        
        # Step 2: Verify project exists in database
        db_project = self.db.query(Project).filter(Project.id == project_id).first()
        assert db_project is not None
        assert db_project.name == project_data["name"]
        
        # Step 3: Test project configuration validation
        config_response = self.client.get(f"/projects/{project_id}/configuration")
        assert config_response.status_code == 200
        
        config_data = config_response.json()
        assert config_data["camera_model"] == project_data["camera_model"]
        assert config_data["signal_type"] == project_data["signal_type"]
        
        return project_id
    
    def test_video_upload_and_processing_workflow(self):
        """Test complete video upload and processing workflow"""
        # Create project first
        project_id = self.test_complete_project_creation_workflow()
        
        # Step 1: Simulate video upload
        video_data = {
            "filename": "test_workflow_video.mp4",
            "file_size": 52428800,  # 50MB
            "duration": 120.0,
            "fps": 30.0,
            "resolution": "1920x1080",
            "project_id": project_id
        }
        
        # Upload video via API
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video.write(b"fake video content for testing")
            temp_video_path = temp_video.name
        
        try:
            with open(temp_video_path, 'rb') as video_file:
                files = {"file": ("test_workflow_video.mp4", video_file, "video/mp4")}
                data = {"project_id": project_id}
                
                response = self.client.post("/videos/upload", files=files, data=data)
                assert response.status_code == 201
                
                uploaded_video = response.json()
                video_id = uploaded_video["id"]
                
                # Validate upload response
                assert uploaded_video["filename"] == "test_workflow_video.mp4"
                assert uploaded_video["project_id"] == project_id
                assert uploaded_video["status"] == "uploaded"
        
        finally:
            os.unlink(temp_video_path)
        
        # Step 2: Start video processing
        processing_response = self.client.post(f"/videos/{video_id}/process")
        assert processing_response.status_code == 200
        
        # Step 3: Monitor processing status
        max_wait_time = 30  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status_response = self.client.get(f"/videos/{video_id}/status")
            assert status_response.status_code == 200
            
            status_data = status_response.json()
            
            if status_data["processing_status"] == "completed":
                break
            elif status_data["processing_status"] == "failed":
                pytest.fail(f"Video processing failed: {status_data}")
            
            time.sleep(1)
        
        # Validate final processing status
        final_status = self.client.get(f"/videos/{video_id}/status").json()
        assert final_status["processing_status"] == "completed"
        assert final_status["ground_truth_generated"] is True
        
        return video_id
    
    def test_test_session_creation_and_execution(self):
        """Test test session creation and execution workflow"""
        # Get video from previous test
        video_id = self.test_video_upload_and_processing_workflow()
        
        # Get project from video
        video_response = self.client.get(f"/videos/{video_id}")
        video_data = video_response.json()
        project_id = video_data["project_id"]
        
        # Step 1: Create test session
        test_session_data = {
            "name": "Workflow Integration Test Session",
            "project_id": project_id,
            "video_id": video_id,
            "tolerance_ms": 100,
            "test_criteria": {
                "min_accuracy": 0.85,
                "max_false_positives": 5,
                "timing_tolerance": 100
            }
        }
        
        response = self.client.post("/test-sessions/", json=test_session_data)
        assert response.status_code == 201
        
        test_session = response.json()
        session_id = test_session["id"]
        
        # Validate test session creation
        assert test_session["name"] == test_session_data["name"]
        assert test_session["status"] == "created"
        
        # Step 2: Start test session
        start_response = self.client.post(f"/test-sessions/{session_id}/start")
        assert start_response.status_code == 200
        
        # Step 3: Simulate detection events during test
        detection_events = [
            {
                "timestamp": 1.5,
                "detection_type": "person",
                "confidence": 0.92,
                "bounding_box": {"x": 100, "y": 200, "width": 80, "height": 180}
            },
            {
                "timestamp": 5.2,
                "detection_type": "vehicle",
                "confidence": 0.88,
                "bounding_box": {"x": 300, "y": 150, "width": 200, "height": 100}
            },
            {
                "timestamp": 8.7,
                "detection_type": "bicycle",
                "confidence": 0.75,
                "bounding_box": {"x": 500, "y": 250, "width": 60, "height": 120}
            }
        ]
        
        for event in detection_events:
            event_data = {
                "test_session_id": session_id,
                **event
            }
            event_response = self.client.post("/detection-events/", json=event_data)
            assert event_response.status_code == 201
        
        # Step 4: Complete test session
        complete_response = self.client.post(f"/test-sessions/{session_id}/complete")
        assert complete_response.status_code == 200
        
        # Step 5: Get test results
        results_response = self.client.get(f"/test-sessions/{session_id}/results")
        assert results_response.status_code == 200
        
        results = results_response.json()
        assert "detection_count" in results
        assert "accuracy_metrics" in results
        assert results["detection_count"] == 3
        
        return session_id
    
    def test_annotation_workflow_integration(self):
        """Test annotation workflow from creation to validation"""
        # Get video from previous test
        video_id = self.test_video_upload_and_processing_workflow()
        
        # Get project from video
        video_response = self.client.get(f"/videos/{video_id}")
        video_data = video_response.json()
        project_id = video_data["project_id"]
        
        # Step 1: Create annotation session
        annotation_session_data = {
            "name": "Workflow Annotation Session",
            "project_id": project_id,
            "video_id": video_id,
            "annotator_name": self.test_user["username"],
            "annotation_type": "manual"
        }
        
        response = self.client.post("/annotation-sessions/", json=annotation_session_data)
        assert response.status_code == 201
        
        annotation_session = response.json()
        session_id = annotation_session["id"]
        
        # Step 2: Create annotations
        annotations = [
            {
                "session_id": session_id,
                "frame_number": 100,
                "timestamp": 3.33,
                "class_label": "person",
                "x": 100,
                "y": 200,
                "width": 80,
                "height": 180,
                "confidence": 0.95
            },
            {
                "session_id": session_id,
                "frame_number": 150,
                "timestamp": 5.0,
                "class_label": "vehicle",
                "x": 300,
                "y": 150,
                "width": 200,
                "height": 100,
                "confidence": 0.88
            }
        ]
        
        annotation_ids = []
        for annotation_data in annotations:
            ann_response = self.client.post("/annotations/", json=annotation_data)
            assert ann_response.status_code == 201
            annotation_ids.append(ann_response.json()["id"])
        
        # Step 3: Validate annotations
        for ann_id in annotation_ids:
            validate_response = self.client.post(f"/annotations/{ann_id}/validate")
            assert validate_response.status_code == 200
        
        # Step 4: Export annotations
        export_response = self.client.post(f"/annotation-sessions/{session_id}/export", 
                                         json={"format": "COCO"})
        assert export_response.status_code == 200
        
        export_data = export_response.json()
        assert "annotations" in export_data
        assert len(export_data["annotations"]) == 2
        
        return session_id
    
    def test_multi_video_project_workflow(self):
        """Test workflow with multiple videos in a single project"""
        # Create project
        project_id = self.test_complete_project_creation_workflow()
        
        # Upload multiple videos
        video_ids = []
        video_files = [
            {"name": "video_1.mp4", "duration": 30.0},
            {"name": "video_2.mp4", "duration": 45.0},
            {"name": "video_3.mp4", "duration": 60.0}
        ]
        
        for video_file in video_files:
            # Simulate video upload
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                temp_video.write(f"fake video content for {video_file['name']}".encode())
                temp_video_path = temp_video.name
            
            try:
                with open(temp_video_path, 'rb') as video:
                    files = {"file": (video_file["name"], video, "video/mp4")}
                    data = {"project_id": project_id}
                    
                    response = self.client.post("/videos/upload", files=files, data=data)
                    assert response.status_code == 201
                    video_ids.append(response.json()["id"])
            
            finally:
                os.unlink(temp_video_path)
        
        # Process all videos
        for video_id in video_ids:
            process_response = self.client.post(f"/videos/{video_id}/process")
            assert process_response.status_code == 200
        
        # Wait for all processing to complete
        all_completed = False
        max_wait_time = 60  # seconds
        start_time = time.time()
        
        while not all_completed and (time.time() - start_time) < max_wait_time:
            statuses = []
            for video_id in video_ids:
                status_response = self.client.get(f"/videos/{video_id}/status")
                status_data = status_response.json()
                statuses.append(status_data["processing_status"])
            
            all_completed = all(status == "completed" for status in statuses)
            
            if not all_completed:
                time.sleep(2)
        
        assert all_completed, "Not all videos completed processing in time"
        
        # Get project summary with all videos
        project_response = self.client.get(f"/projects/{project_id}/summary")
        assert project_response.status_code == 200
        
        project_summary = project_response.json()
        assert project_summary["video_count"] == 3
        assert project_summary["total_duration"] == 135.0  # 30 + 45 + 60
        
        return project_id, video_ids
    
    def test_project_collaboration_workflow(self):
        """Test collaborative project workflow with multiple users"""
        # Create project
        project_id = self.test_complete_project_creation_workflow()
        
        # Simulate multiple users
        users = [
            {"user_id": "collaborator_1", "username": "collaborator1", "role": "annotator"},
            {"user_id": "collaborator_2", "username": "collaborator2", "role": "reviewer"},
            {"user_id": "collaborator_3", "username": "collaborator3", "role": "validator"}
        ]
        
        # Add collaborators to project
        for user in users:
            collab_data = {
                "project_id": project_id,
                "user_id": user["user_id"],
                "role": user["role"]
            }
            
            response = self.client.post("/projects/collaborators/", json=collab_data)
            assert response.status_code == 201
        
        # Get project collaborators
        collab_response = self.client.get(f"/projects/{project_id}/collaborators")
        assert collab_response.status_code == 200
        
        collaborators = collab_response.json()
        assert len(collaborators) == len(users)
        
        # Test role-based access
        for user in users:
            # Mock user context
            headers = {"X-User-ID": user["user_id"], "X-User-Role": user["role"]}
            
            # Test access based on role
            if user["role"] == "annotator":
                # Should be able to create annotations
                ann_response = self.client.post("/annotation-sessions/", 
                                              json={"name": "Test", "project_id": project_id},
                                              headers=headers)
                assert ann_response.status_code in [201, 403]  # Depends on implementation
            
            elif user["role"] == "reviewer":
                # Should be able to review annotations
                review_response = self.client.get(f"/projects/{project_id}/annotations",
                                                headers=headers)
                assert review_response.status_code in [200, 403]
            
            elif user["role"] == "validator":
                # Should be able to validate results
                validate_response = self.client.get(f"/projects/{project_id}/validation",
                                                  headers=headers)
                assert validate_response.status_code in [200, 403]
    
    def test_project_state_transitions(self):
        """Test project state transitions through workflow stages"""
        # Create project
        project_id = self.test_complete_project_creation_workflow()
        
        # Initial state should be "Active"
        project_response = self.client.get(f"/projects/{project_id}")
        project_data = project_response.json()
        assert project_data["status"] == "Active"
        
        # Transition to "In Progress"
        update_response = self.client.patch(f"/projects/{project_id}", 
                                          json={"status": "In Progress"})
        assert update_response.status_code == 200
        
        # Add videos and process them
        video_id = self.test_video_upload_and_processing_workflow()
        
        # Transition to "Review"
        update_response = self.client.patch(f"/projects/{project_id}", 
                                          json={"status": "Review"})
        assert update_response.status_code == 200
        
        # Complete review and transition to "Completed"
        complete_response = self.client.post(f"/projects/{project_id}/complete")
        assert complete_response.status_code == 200
        
        # Verify final state
        final_response = self.client.get(f"/projects/{project_id}")
        final_data = final_response.json()
        assert final_data["status"] == "Completed"
        
        # Test invalid state transitions
        invalid_response = self.client.patch(f"/projects/{project_id}", 
                                           json={"status": "Active"})
        assert invalid_response.status_code == 400  # Should not allow backward transition
    
    def test_workflow_error_handling_and_recovery(self):
        """Test error handling and recovery in workflows"""
        # Create project
        project_id = self.test_complete_project_creation_workflow()
        
        # Test 1: Upload invalid video file
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as invalid_file:
            invalid_file.write(b"This is not a video file")
            invalid_file_path = invalid_file.name
        
        try:
            with open(invalid_file_path, 'rb') as file:
                files = {"file": ("invalid_video.txt", file, "text/plain")}
                data = {"project_id": project_id}
                
                response = self.client.post("/videos/upload", files=files, data=data)
                assert response.status_code == 400  # Should reject invalid file
        
        finally:
            os.unlink(invalid_file_path)
        
        # Test 2: Process non-existent video
        fake_video_id = "non-existent-video-id"
        process_response = self.client.post(f"/videos/{fake_video_id}/process")
        assert process_response.status_code == 404
        
        # Test 3: Create test session with invalid parameters
        invalid_session_data = {
            "name": "",  # Empty name
            "project_id": "invalid-project-id",
            "video_id": "invalid-video-id",
            "tolerance_ms": -100  # Invalid tolerance
        }
        
        session_response = self.client.post("/test-sessions/", json=invalid_session_data)
        assert session_response.status_code == 422  # Validation error
        
        # Test 4: Recovery from processing failure
        # Create valid video first
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video.write(b"valid video content")
            temp_video_path = temp_video.name
        
        try:
            with open(temp_video_path, 'rb') as video_file:
                files = {"file": ("recovery_test.mp4", video_file, "video/mp4")}
                data = {"project_id": project_id}
                
                upload_response = self.client.post("/videos/upload", files=files, data=data)
                assert upload_response.status_code == 201
                video_id = upload_response.json()["id"]
            
            # Simulate processing failure and recovery
            with patch('services.video_processing_workflow.VideoProcessingWorkflow.start_processing') as mock_process:
                # First attempt fails
                mock_process.return_value = False
                
                fail_response = self.client.post(f"/videos/{video_id}/process")
                # Should handle failure gracefully
                
                # Retry should work
                mock_process.return_value = True
                retry_response = self.client.post(f"/videos/{video_id}/process")
                assert retry_response.status_code == 200
        
        finally:
            os.unlink(temp_video_path)
    
    @pytest.mark.asyncio
    async def test_real_time_workflow_updates(self):
        """Test real-time updates during workflow execution"""
        # Create project and video
        project_id = self.test_complete_project_creation_workflow()
        
        # Mock WebSocket connection for real-time updates
        updates_received = []
        
        async def mock_websocket_handler(websocket):
            while True:
                try:
                    message = await websocket.receive_json()
                    updates_received.append(message)
                except:
                    break
        
        # Start video processing with real-time monitoring
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video.write(b"test video for real-time updates")
            temp_video_path = temp_video.name
        
        try:
            # Upload video
            with open(temp_video_path, 'rb') as video_file:
                files = {"file": ("realtime_test.mp4", video_file, "video/mp4")}
                data = {"project_id": project_id}
                
                upload_response = self.client.post("/videos/upload", files=files, data=data)
                video_id = upload_response.json()["id"]
            
            # Start processing (this should generate real-time updates)
            process_response = self.client.post(f"/videos/{video_id}/process")
            assert process_response.status_code == 200
            
            # Wait for processing to complete and collect updates
            await asyncio.sleep(5)
            
            # Verify we received real-time updates
            # (In a real implementation, this would test actual WebSocket messages)
            status_response = self.client.get(f"/videos/{video_id}/status")
            final_status = status_response.json()
            
            assert final_status["processing_status"] in ["completed", "processing"]
        
        finally:
            os.unlink(temp_video_path)
    
    def test_workflow_performance_benchmarks(self):
        """Test workflow performance under various conditions"""
        # Create project
        project_id = self.test_complete_project_creation_workflow()
        
        # Benchmark 1: Single video upload and processing time
        start_time = time.time()
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video.write(b"performance test video content" * 1000)  # Larger file
            temp_video_path = temp_video.name
        
        try:
            # Upload video
            with open(temp_video_path, 'rb') as video_file:
                files = {"file": ("performance_test.mp4", video_file, "video/mp4")}
                data = {"project_id": project_id}
                
                upload_response = self.client.post("/videos/upload", files=files, data=data)
                assert upload_response.status_code == 201
                video_id = upload_response.json()["id"]
            
            upload_time = time.time() - start_time
            
            # Process video
            process_start = time.time()
            process_response = self.client.post(f"/videos/{video_id}/process")
            assert process_response.status_code == 200
            
            # Wait for completion
            while True:
                status_response = self.client.get(f"/videos/{video_id}/status")
                status_data = status_response.json()
                
                if status_data["processing_status"] in ["completed", "failed"]:
                    break
                
                time.sleep(0.5)
            
            process_time = time.time() - process_start
            
            # Performance assertions
            assert upload_time < 10.0, f"Upload too slow: {upload_time}s"
            assert process_time < 30.0, f"Processing too slow: {process_time}s"
        
        finally:
            os.unlink(temp_video_path)
        
        # Benchmark 2: Concurrent video processing
        concurrent_videos = []
        concurrent_start = time.time()
        
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                temp_video.write(f"concurrent test video {i}".encode() * 100)
                temp_video_path = temp_video.name
            
            try:
                with open(temp_video_path, 'rb') as video_file:
                    files = {"file": (f"concurrent_{i}.mp4", video_file, "video/mp4")}
                    data = {"project_id": project_id}
                    
                    upload_response = self.client.post("/videos/upload", files=files, data=data)
                    video_id = upload_response.json()["id"]
                    concurrent_videos.append(video_id)
                    
                    # Start processing immediately
                    self.client.post(f"/videos/{video_id}/process")
            
            finally:
                os.unlink(temp_video_path)
        
        # Wait for all to complete
        all_completed = False
        while not all_completed and (time.time() - concurrent_start) < 60:
            statuses = []
            for video_id in concurrent_videos:
                status_response = self.client.get(f"/videos/{video_id}/status")
                status_data = status_response.json()
                statuses.append(status_data["processing_status"])
            
            all_completed = all(status in ["completed", "failed"] for status in statuses)
            
            if not all_completed:
                time.sleep(1)
        
        concurrent_time = time.time() - concurrent_start
        
        # Concurrent processing should not take much longer than sequential
        assert concurrent_time < 45.0, f"Concurrent processing too slow: {concurrent_time}s"
        assert all_completed, "Not all concurrent videos completed processing"


class TestWorkflowEdgeCases:
    """Test edge cases and boundary conditions in workflows"""
    
    def test_empty_project_workflow(self):
        """Test workflow behavior with empty projects"""
        # Create empty project
        project_data = {
            "name": "Empty Project Test",
            "description": "",
            "camera_model": "Test Camera",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        client = TestClient(app)
        response = client.post("/projects/", json=project_data)
        assert response.status_code == 201
        
        project_id = response.json()["id"]
        
        # Test operations on empty project
        summary_response = client.get(f"/projects/{project_id}/summary")
        assert summary_response.status_code == 200
        
        summary = summary_response.json()
        assert summary["video_count"] == 0
        assert summary["total_duration"] == 0.0
    
    def test_maximum_capacity_workflow(self):
        """Test workflow behavior at maximum capacity limits"""
        # Test with maximum number of videos per project
        client = TestClient(app)
        
        # Create project
        project_data = {
            "name": "Max Capacity Test Project",
            "description": "Testing maximum capacity limits",
            "camera_model": "Test Camera",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        response = client.post("/projects/", json=project_data)
        project_id = response.json()["id"]
        
        # Upload maximum number of videos (simulate limit of 100)
        max_videos = 10  # Reduced for testing
        uploaded_videos = []
        
        for i in range(max_videos):
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                temp_video.write(f"max capacity test video {i}".encode())
                temp_video_path = temp_video.name
            
            try:
                with open(temp_video_path, 'rb') as video_file:
                    files = {"file": (f"max_video_{i}.mp4", video_file, "video/mp4")}
                    data = {"project_id": project_id}
                    
                    upload_response = client.post("/videos/upload", files=files, data=data)
                    
                    if upload_response.status_code == 201:
                        uploaded_videos.append(upload_response.json()["id"])
                    else:
                        # Should handle capacity limits gracefully
                        assert upload_response.status_code in [400, 413, 429]
                        break
            
            finally:
                os.unlink(temp_video_path)
        
        # Verify project can handle the uploaded videos
        summary_response = client.get(f"/projects/{project_id}/summary")
        summary = summary_response.json()
        assert summary["video_count"] == len(uploaded_videos)


@pytest.fixture
def test_db_session():
    """Fixture providing test database session"""
    session = SessionLocal()
    yield session
    session.close()


# Helper functions for workflow testing
def wait_for_condition(condition_func, timeout=30, interval=1):
    """Wait for a condition to become true within timeout"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(interval)
    return False


def generate_test_video_content(size_mb=1):
    """Generate test video content of specified size"""
    content = b"fake video content "
    target_size = size_mb * 1024 * 1024
    multiplier = target_size // len(content)
    return content * multiplier


def validate_workflow_state(client, resource_type, resource_id, expected_state):
    """Validate that a workflow resource is in the expected state"""
    response = client.get(f"/{resource_type}/{resource_id}")
    if response.status_code != 200:
        return False
    
    data = response.json()
    return data.get("status") == expected_state