"""
Integration tests for all API endpoints with real database schema
"""
import pytest
import json
from datetime import datetime


class TestProjectEndpoints:
    """Test project-related API endpoints"""
    
    def test_create_project_endpoint(self, test_client, sample_project_data):
        """Test project creation endpoint"""
        response = test_client.post("/projects", json=sample_project_data)
        
        assert response.status_code == 201
        project_data = response.json()
        
        assert project_data["name"] == sample_project_data["name"]
        assert project_data["cameraModel"] == sample_project_data["cameraModel"]
        assert project_data["cameraView"] == sample_project_data["cameraView"]
        assert project_data["signalType"] == sample_project_data["signalType"]
        assert "id" in project_data
        assert "createdAt" in project_data
    
    def test_get_project_endpoint(self, test_client, created_project):
        """Test get project by ID endpoint"""
        response = test_client.get(f"/projects/{created_project.id}")
        
        assert response.status_code == 200
        project_data = response.json()
        
        assert project_data["id"] == created_project.id
        assert project_data["name"] == created_project.name
        assert project_data["status"] == created_project.status
    
    def test_get_projects_list_endpoint(self, test_client, test_db_session):
        """Test get projects list endpoint"""
        # Create multiple projects
        from models import Project
        
        projects = []
        for i in range(3):
            project = Project(
                name=f"Test Project {i}",
                camera_model="Test Camera",
                camera_view="Front-facing VRU",
                signal_type="GPIO"
            )
            projects.append(project)
            test_db_session.add(project)
        
        test_db_session.commit()
        
        response = test_client.get("/projects")
        
        assert response.status_code == 200
        projects_data = response.json()
        
        assert len(projects_data) >= 3
        assert all("id" in p for p in projects_data)
        assert all("name" in p for p in projects_data)
    
    def test_update_project_endpoint(self, test_client, created_project):
        """Test project update endpoint"""
        update_data = {
            "name": "Updated Project Name",
            "description": "Updated description"
        }
        
        response = test_client.put(f"/projects/{created_project.id}", json=update_data)
        
        assert response.status_code == 200
        updated_project = response.json()
        
        assert updated_project["name"] == "Updated Project Name"
        assert updated_project["description"] == "Updated description"
    
    def test_delete_project_endpoint(self, test_client, created_project):
        """Test project deletion endpoint"""
        response = test_client.delete(f"/projects/{created_project.id}")
        
        assert response.status_code == 204
        
        # Verify project is deleted
        get_response = test_client.get(f"/projects/{created_project.id}")
        assert get_response.status_code == 404


class TestVideoEndpoints:
    """Test video-related API endpoints"""
    
    def test_get_video_endpoint(self, test_client, created_video):
        """Test get video by ID endpoint"""
        response = test_client.get(f"/videos/{created_video.id}")
        
        assert response.status_code == 200
        video_data = response.json()
        
        assert video_data["id"] == created_video.id
        assert video_data["filename"] == created_video.filename
        assert video_data["projectId"] == created_video.project_id
        assert video_data["status"] == created_video.status
        assert "processingStatus" in video_data
        assert "groundTruthGenerated" in video_data
    
    def test_get_project_videos_endpoint(self, test_client, created_project):
        """Test get videos for a project endpoint"""
        response = test_client.get(f"/projects/{created_project.id}/videos")
        
        assert response.status_code == 200
        videos_data = response.json()
        
        assert isinstance(videos_data, list)
        # May be empty if no videos uploaded yet
    
    def test_video_status_endpoint(self, test_client, created_video):
        """Test video processing status endpoint"""
        response = test_client.get(f"/videos/{created_video.id}/status")
        
        assert response.status_code == 200
        status_data = response.json()
        
        assert "processingStatus" in status_data
        assert "groundTruthGenerated" in status_data
        assert status_data["processingStatus"] in ["pending", "processing", "completed", "failed"]
    
    def test_video_metadata_endpoint(self, test_client, created_video):
        """Test video metadata endpoint"""
        response = test_client.get(f"/videos/{created_video.id}/metadata")
        
        assert response.status_code == 200
        metadata = response.json()
        
        assert "duration" in metadata
        assert "fps" in metadata
        assert "resolution" in metadata
        assert "fileSize" in metadata
    
    def test_delete_video_endpoint(self, test_client, created_video):
        """Test video deletion endpoint"""
        response = test_client.delete(f"/videos/{created_video.id}")
        
        assert response.status_code == 204
        
        # Verify video is deleted
        get_response = test_client.get(f"/videos/{created_video.id}")
        assert get_response.status_code == 404


class TestGroundTruthEndpoints:
    """Test ground truth related API endpoints"""
    
    def test_get_ground_truth_endpoint(self, test_client, created_video, sample_ground_truth_objects):
        """Test get ground truth for video endpoint"""
        response = test_client.get(f"/videos/{created_video.id}/ground-truth")
        
        assert response.status_code == 200
        gt_data = response.json()
        
        assert "objects" in gt_data
        assert "totalDetections" in gt_data
        assert "status" in gt_data
        assert len(gt_data["objects"]) == 5  # From fixture
    
    def test_ground_truth_statistics_endpoint(self, test_client, created_video, sample_ground_truth_objects):
        """Test ground truth statistics endpoint"""
        response = test_client.get(f"/videos/{created_video.id}/ground-truth/stats")
        
        assert response.status_code == 200
        stats = response.json()
        
        assert "totalDetections" in stats
        assert "classDistribution" in stats
        assert "confidenceStats" in stats
    
    def test_regenerate_ground_truth_endpoint(self, test_client, created_video):
        """Test regenerate ground truth endpoint"""
        response = test_client.post(f"/videos/{created_video.id}/ground-truth/regenerate")
        
        assert response.status_code == 202  # Accepted for async processing
        result = response.json()
        
        assert "message" in result
        assert "taskId" in result or "status" in result


class TestTestSessionEndpoints:
    """Test test session related API endpoints"""
    
    def test_create_test_session_endpoint(self, test_client, created_project, created_video):
        """Test test session creation endpoint"""
        session_data = {
            "name": "API Test Session",
            "project_id": created_project.id,
            "video_id": created_video.id,
            "tolerance_ms": 75
        }
        
        response = test_client.post("/test-sessions", json=session_data)
        
        assert response.status_code == 201
        session = response.json()
        
        assert session["name"] == "API Test Session"
        assert session["project_id"] == created_project.id
        assert session["video_id"] == created_video.id
        assert session["tolerance_ms"] == 75
    
    def test_get_test_session_endpoint(self, test_client, created_test_session):
        """Test get test session endpoint"""
        response = test_client.get(f"/test-sessions/{created_test_session.id}")
        
        assert response.status_code == 200
        session_data = response.json()
        
        assert session_data["id"] == created_test_session.id
        assert session_data["name"] == created_test_session.name
        assert session_data["status"] == created_test_session.status
    
    def test_start_test_session_endpoint(self, test_client, created_test_session):
        """Test start test session endpoint"""
        response = test_client.post(f"/test-sessions/{created_test_session.id}/start")
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["status"] == "running"
        assert "startedAt" in result
    
    def test_stop_test_session_endpoint(self, test_client, test_db_session, created_test_session):
        """Test stop test session endpoint"""
        # Start session first
        created_test_session.status = "running"
        created_test_session.started_at = datetime.now()
        test_db_session.commit()
        
        response = test_client.post(f"/test-sessions/{created_test_session.id}/stop")
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["status"] == "completed"
        assert "completedAt" in result
    
    def test_test_session_results_endpoint(self, test_client, created_test_session, sample_detection_events):
        """Test get test session results endpoint"""
        response = test_client.get(f"/test-sessions/{created_test_session.id}/results")
        
        assert response.status_code == 200
        results = response.json()
        
        assert "metrics" in results
        assert "detectionEvents" in results
        assert "summary" in results


class TestDetectionEventEndpoints:
    """Test detection event related API endpoints"""
    
    def test_create_detection_event_endpoint(self, test_client, created_test_session):
        """Test detection event creation endpoint"""
        event_data = {
            "testSessionId": created_test_session.id,
            "timestamp": 5.5,
            "confidence": 0.92,
            "classLabel": "pedestrian"
        }
        
        response = test_client.post("/detection-events", json=event_data)
        
        assert response.status_code == 201
        event = response.json()
        
        assert event["timestamp"] == 5.5
        assert event["confidence"] == 0.92
        assert event["classLabel"] == "pedestrian"
    
    def test_get_detection_events_endpoint(self, test_client, created_test_session, sample_detection_events):
        """Test get detection events for session endpoint"""
        response = test_client.get(f"/test-sessions/{created_test_session.id}/detection-events")
        
        assert response.status_code == 200
        events = response.json()
        
        assert len(events) == 3  # From fixture
        assert all("timestamp" in event for event in events)
        assert all("confidence" in event for event in events)


class TestValidationEndpoints:
    """Test validation related API endpoints"""
    
    def test_validate_detection_performance_endpoint(self, test_client, created_test_session):
        """Test detection performance validation endpoint"""
        response = test_client.post(f"/test-sessions/{created_test_session.id}/validate")
        
        assert response.status_code == 200
        validation_result = response.json()
        
        assert "accuracy" in validation_result
        assert "precision" in validation_result
        assert "recall" in validation_result
        assert "f1_score" in validation_result
    
    def test_get_validation_metrics_endpoint(self, test_client, created_test_session):
        """Test get validation metrics endpoint"""
        response = test_client.get(f"/test-sessions/{created_test_session.id}/metrics")
        
        assert response.status_code == 200
        metrics = response.json()
        
        assert "truePositives" in metrics
        assert "falsePositives" in metrics
        assert "falseNegatives" in metrics
        assert "precision" in metrics
        assert "recall" in metrics


class TestDashboardEndpoints:
    """Test dashboard and statistics endpoints"""
    
    def test_dashboard_stats_endpoint(self, test_client):
        """Test dashboard statistics endpoint"""
        response = test_client.get("/dashboard/stats")
        
        assert response.status_code == 200
        stats = response.json()
        
        assert "projectCount" in stats
        assert "videoCount" in stats
        assert "testCount" in stats
        assert "totalDetections" in stats
        assert "averageAccuracy" in stats
    
    def test_system_health_endpoint(self, test_client):
        """Test system health check endpoint"""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        health = response.json()
        
        assert "status" in health
        assert "database" in health
        assert health["status"] in ["healthy", "unhealthy"]
    
    def test_api_info_endpoint(self, test_client):
        """Test API information endpoint"""
        response = test_client.get("/")
        
        assert response.status_code == 200
        info = response.json()
        
        assert "message" in info
        assert "version" in info or "description" in info


class TestErrorHandlingEndpoints:
    """Test API error handling"""
    
    def test_not_found_endpoints(self, test_client):
        """Test 404 error handling"""
        # Test with non-existent project ID
        response = test_client.get("/projects/non-existent-id")
        assert response.status_code == 404
        
        # Test with non-existent video ID
        response = test_client.get("/videos/non-existent-id")
        assert response.status_code == 404
        
        # Test with non-existent test session ID
        response = test_client.get("/test-sessions/non-existent-id")
        assert response.status_code == 404
    
    def test_validation_error_endpoints(self, test_client):
        """Test validation error handling"""
        # Test project creation with invalid data
        invalid_data = {
            "name": "",  # Empty name should fail
            "cameraModel": "Test",
            "cameraView": "Invalid View",  # Invalid enum
            "signalType": "GPIO"
        }
        
        response = test_client.post("/projects", json=invalid_data)
        assert response.status_code in [400, 422]  # Bad request or validation error
    
    def test_database_error_handling(self, test_client, database_error_simulator):
        """Test database error handling in endpoints"""
        # Simulate database error
        database_error_simulator.simulate_query_error()
        
        response = test_client.get("/projects")
        
        # Should handle database errors gracefully
        assert response.status_code == 500
        
        # Restore database
        database_error_simulator.restore()
    
    def test_concurrent_request_handling(self, test_client, created_project):
        """Test handling of concurrent requests"""
        import concurrent.futures
        import time
        
        def make_request():
            return test_client.get(f"/projects/{created_project.id}")
        
        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        assert all(result.status_code == 200 for result in results)
    
    def test_large_payload_handling(self, test_client):
        """Test handling of large request payloads"""
        # Create large project description
        large_description = "x" * 10000  # 10KB description
        
        project_data = {
            "name": "Large Payload Test",
            "description": large_description,
            "cameraModel": "Test Camera",
            "cameraView": "Front-facing VRU",
            "signalType": "GPIO"
        }
        
        response = test_client.post("/projects", json=project_data)
        
        # Should handle large payloads within reasonable limits
        assert response.status_code in [201, 413]  # Created or payload too large


class TestAPIAuthentication:
    """Test API authentication and authorization (if implemented)"""
    
    def test_unauthenticated_access(self, test_client):
        """Test access without authentication"""
        # Most endpoints should be accessible without auth in current implementation
        response = test_client.get("/projects")
        assert response.status_code == 200
    
    def test_rate_limiting(self, test_client):
        """Test rate limiting (if implemented)"""
        # Make many rapid requests
        responses = []
        for _ in range(100):
            response = test_client.get("/health")
            responses.append(response)
        
        # All should succeed in current implementation (no rate limiting)
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count >= 90  # Allow for some failures due to other reasons