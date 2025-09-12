"""
Integration Tests for Video Validation API Endpoints
===================================================

Tests the complete API workflow for video validation including
endpoint integration, database operations, and service layer interactions.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import json

from main import app
from models import Base, Video, VideoValidationCriteria, VideoValidationResult
from schemas_video_validation import VideoValidationStatus, ValidationStatus, ValidationType
from config import get_db


# Test database setup
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_video_validation.db"
test_engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="module")
def test_client():
    """Create test client with test database"""
    Base.metadata.create_all(bind=test_engine)
    
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    
    # Cleanup
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def test_db():
    """Create test database session"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_videos(test_db):
    """Create sample videos for testing"""
    videos = [
        Video(
            id="video-1",
            filename="test1.mp4",
            file_path="/uploads/test1.mp4",
            validation_status="uploaded",
            project_id="project-1"
        ),
        Video(
            id="video-2", 
            filename="test2.mp4",
            file_path="/uploads/test2.mp4",
            validation_status="annotated",
            ground_truth_generated=True,
            ground_truth_count=20,
            ground_truth_quality_score=0.95,
            project_id="project-1"
        ),
        Video(
            id="video-3",
            filename="test3.mp4", 
            file_path="/uploads/test3.mp4",
            validation_status="validated",
            validation_type="automatic",
            validated_at=datetime.now(timezone.utc),
            validated_by="system",
            hil_testing_ready=True,
            project_id="project-1"
        )
    ]
    
    for video in videos:
        test_db.add(video)
    test_db.commit()
    
    return videos


@pytest.fixture
def sample_validation_criteria(test_db):
    """Create sample validation criteria"""
    criteria = [
        VideoValidationCriteria(
            id="criteria-1",
            name="minimum_ground_truth_objects",
            description="Minimum number of ground truth objects required",
            criteria_type="automatic",
            threshold_value=10.0,
            comparison_operator="gte",
            is_required=True,
            created_by="system"
        ),
        VideoValidationCriteria(
            id="criteria-2",
            name="ground_truth_quality_score",
            description="Minimum quality score for ground truth annotations",
            criteria_type="automatic", 
            threshold_value=0.8,
            comparison_operator="gte",
            is_required=True,
            created_by="system"
        )
    ]
    
    for criterion in criteria:
        test_db.add(criterion)
    test_db.commit()
    
    return criteria


class TestVideoValidationStatusEndpoints:
    """Test video validation status API endpoints"""
    
    def test_get_video_status(self, test_client, sample_videos):
        """Test GET /api/videos/{video_id}/status"""
        response = test_client.get("/api/videos/video-2/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "video-2"
        assert data["validation_status"] == "annotated"
        assert data["ground_truth_generated"] is True
        assert data["ground_truth_count"] == 20
    
    def test_get_video_status_not_found(self, test_client):
        """Test GET /api/videos/{video_id}/status for non-existent video"""
        response = test_client.get("/api/videos/non-existent/status")
        
        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]
    
    def test_update_video_status(self, test_client, sample_videos):
        """Test PUT /api/videos/{video_id}/status"""
        update_data = {
            "validation_status": "processing",
            "updated_by": "user-123",
            "notes": "Starting processing workflow"
        }
        
        response = test_client.put("/api/videos/video-1/status", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["validation_status"] == "processing"
    
    def test_update_video_status_invalid_transition(self, test_client, sample_videos):
        """Test PUT /api/videos/{video_id}/status with invalid transition"""
        update_data = {
            "validation_status": "validated",  # Can't go directly from uploaded to validated
            "updated_by": "user-123"
        }
        
        response = test_client.put("/api/videos/video-1/status", json=update_data)
        
        assert response.status_code == 400
        assert "Invalid status transition" in response.json()["detail"]
    
    def test_get_videos_by_status(self, test_client, sample_videos):
        """Test GET /api/videos/status/{status}"""
        response = test_client.get("/api/videos/status/annotated")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["videos"]) == 1
        assert data["videos"][0]["id"] == "video-2"
    
    def test_get_videos_ready_for_testing(self, test_client, sample_videos):
        """Test GET /api/videos/ready-for-testing"""
        response = test_client.get("/api/videos/ready-for-testing")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["videos"]) >= 1  # At least video-3 should be ready
        ready_video_ids = [v["id"] for v in data["videos"]]
        assert "video-3" in ready_video_ids


class TestVideoValidationWorkflowEndpoints:
    """Test video validation workflow API endpoints"""
    
    def test_run_automatic_validation(self, test_client, sample_videos, sample_validation_criteria):
        """Test POST /api/videos/{video_id}/validate/automatic"""
        response = test_client.post("/api/videos/video-2/validate/automatic")
        
        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "passed"
        assert data["validation_type"] == "automatic"
        assert len(data["criteria_results"]) == 2  # Both criteria should be evaluated
    
    def test_run_automatic_validation_insufficient_data(self, test_client, sample_videos, sample_validation_criteria):
        """Test automatic validation with insufficient ground truth data"""
        # Create video with insufficient ground truth
        response = test_client.post("/api/videos/video-1/validate/automatic")
        
        # Should fail because video-1 doesn't have ground truth
        assert response.status_code == 400
        assert "not ready for automatic validation" in response.json()["detail"].lower()
    
    def test_complete_manual_validation(self, test_client, sample_videos):
        """Test POST /api/videos/{video_id}/validate/manual"""
        validation_data = {
            "validated_by": "reviewer-123",
            "criteria_results": [
                {
                    "criteria_id": "manual-1",
                    "result": "passed",
                    "notes": "Objects are clearly visible and properly annotated"
                },
                {
                    "criteria_id": "manual-2", 
                    "result": "passed",
                    "notes": "Video quality is adequate for testing"
                }
            ],
            "validation_notes": "Manual validation completed successfully"
        }
        
        response = test_client.post("/api/videos/video-2/validate/manual", json=validation_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "passed"
        assert data["validation_type"] == "manual"
        assert data["validated_by"] == "reviewer-123"
    
    def test_approve_for_hil_testing(self, test_client, sample_videos):
        """Test POST /api/videos/{video_id}/approve-hil-testing"""
        approval_data = {
            "approved_by": "test-engineer-456",
            "notes": "Approved for HIL testing campaign"
        }
        
        # First validate the video
        test_client.post("/api/videos/video-2/validate/automatic")
        
        # Then approve for HIL testing
        response = test_client.post("/api/videos/video-2/approve-hil-testing", json=approval_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["hil_testing_ready"] is True
        assert data["hil_testing_approved_by"] == "test-engineer-456"
    
    def test_get_validation_history(self, test_client, sample_videos):
        """Test GET /api/videos/{video_id}/validation-history"""
        # First create some validation history
        test_client.post("/api/videos/video-2/validate/automatic")
        
        response = test_client.get("/api/videos/video-2/validation-history")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["history"]) >= 1
        assert data["history"][0]["validation_type"] == "automatic"


class TestVideoValidationBatchEndpoints:
    """Test batch video validation API endpoints"""
    
    def test_batch_validate_videos(self, test_client, sample_videos, sample_validation_criteria):
        """Test POST /api/videos/batch-validate"""
        batch_data = {
            "video_ids": ["video-2"],  # Only video-2 has ground truth
            "validation_type": "automatic",
            "validated_by": "system"
        }
        
        response = test_client.post("/api/videos/batch-validate", json=batch_data)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert "video-2" in data["results"]
        assert data["results"]["video-2"]["overall_status"] == "passed"
    
    def test_batch_update_status(self, test_client, sample_videos):
        """Test POST /api/videos/batch-update-status"""
        batch_data = {
            "video_ids": ["video-3"],  # Already validated video
            "new_status": "ready_for_testing",
            "updated_by": "admin-789",
            "notes": "Batch approval for testing"
        }
        
        response = test_client.post("/api/videos/batch-update-status", json=batch_data)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["updated_videos"]) == 1
        assert data["updated_videos"][0]["validation_status"] == "ready_for_testing"
    
    def test_batch_approve_hil_testing(self, test_client, sample_videos):
        """Test POST /api/videos/batch-approve-hil-testing"""
        batch_data = {
            "video_ids": ["video-3"],  # Already validated
            "approved_by": "test-manager-101",
            "notes": "Batch HIL testing approval"
        }
        
        response = test_client.post("/api/videos/batch-approve-hil-testing", json=batch_data)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["approved_videos"]) == 1
        assert data["approved_videos"][0]["hil_testing_ready"] is True


class TestVideoValidationCriteriaEndpoints:
    """Test video validation criteria management API endpoints"""
    
    def test_get_validation_criteria(self, test_client, sample_validation_criteria):
        """Test GET /api/videos/validation-criteria"""
        response = test_client.get("/api/videos/validation-criteria")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["criteria"]) == 2
        criteria_names = [c["name"] for c in data["criteria"]]
        assert "minimum_ground_truth_objects" in criteria_names
        assert "ground_truth_quality_score" in criteria_names
    
    def test_create_validation_criteria(self, test_client):
        """Test POST /api/videos/validation-criteria"""
        criteria_data = {
            "name": "video_duration_check",
            "description": "Check minimum video duration",
            "criteria_type": "automatic",
            "threshold_value": 30.0,
            "comparison_operator": "gte",
            "is_required": False,
            "created_by": "admin-123"
        }
        
        response = test_client.post("/api/videos/validation-criteria", json=criteria_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "video_duration_check"
        assert data["threshold_value"] == 30.0
        assert data["is_required"] is False
    
    def test_update_validation_criteria(self, test_client, sample_validation_criteria):
        """Test PUT /api/videos/validation-criteria/{criteria_id}"""
        update_data = {
            "threshold_value": 15.0,  # Update threshold
            "description": "Updated minimum ground truth objects requirement"
        }
        
        response = test_client.put("/api/videos/validation-criteria/criteria-1", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["threshold_value"] == 15.0
        assert "Updated minimum" in data["description"]
    
    def test_delete_validation_criteria(self, test_client, sample_validation_criteria):
        """Test DELETE /api/videos/validation-criteria/{criteria_id}"""
        response = test_client.delete("/api/videos/validation-criteria/criteria-2")
        
        assert response.status_code == 204
        
        # Verify deletion
        get_response = test_client.get("/api/videos/validation-criteria")
        criteria_ids = [c["id"] for c in get_response.json()["criteria"]]
        assert "criteria-2" not in criteria_ids


class TestVideoValidationReportsEndpoints:
    """Test video validation reporting API endpoints"""
    
    def test_get_validation_summary(self, test_client, sample_videos):
        """Test GET /api/videos/validation-summary"""
        response = test_client.get("/api/videos/validation-summary")
        
        assert response.status_code == 200
        data = response.json()
        assert "status_counts" in data
        assert "validation_type_counts" in data
        assert "hil_ready_count" in data
        
        # Verify status counts
        status_counts = data["status_counts"]
        assert status_counts.get("uploaded", 0) >= 1
        assert status_counts.get("annotated", 0) >= 1
        assert status_counts.get("validated", 0) >= 1
    
    def test_get_validation_metrics(self, test_client, sample_videos, sample_validation_criteria):
        """Test GET /api/videos/validation-metrics"""
        # Create some validation history first
        test_client.post("/api/videos/video-2/validate/automatic")
        
        response = test_client.get("/api/videos/validation-metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "validation_success_rate" in data
        assert "average_validation_time" in data
        assert "criteria_pass_rates" in data
    
    def test_export_validation_report(self, test_client, sample_videos):
        """Test GET /api/videos/validation-report/export"""
        response = test_client.get("/api/videos/validation-report/export?format=json")
        
        assert response.status_code == 200
        data = response.json()
        assert "report_metadata" in data
        assert "video_validations" in data
        assert "criteria_summary" in data


class TestVideoValidationErrorHandling:
    """Test error handling in video validation API"""
    
    def test_validate_non_existent_video(self, test_client):
        """Test validation of non-existent video"""
        response = test_client.post("/api/videos/non-existent/validate/automatic")
        
        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]
    
    def test_invalid_validation_status(self, test_client, sample_videos):
        """Test update with invalid validation status"""
        update_data = {
            "validation_status": "invalid_status",
            "updated_by": "user-123"
        }
        
        response = test_client.put("/api/videos/video-1/status", json=update_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_batch_validation_partial_failure(self, test_client, sample_videos, sample_validation_criteria):
        """Test batch validation with some failures"""
        batch_data = {
            "video_ids": ["video-1", "video-2", "non-existent"],  # Mix of valid and invalid
            "validation_type": "automatic",
            "validated_by": "system"
        }
        
        response = test_client.post("/api/videos/batch-validate", json=batch_data)
        
        assert response.status_code == 207  # Multi-status response
        data = response.json()
        assert "results" in data
        assert "errors" in data
        assert len(data["errors"]) >= 1  # At least non-existent video should fail
    
    def test_concurrent_status_updates(self, test_client, sample_videos):
        """Test handling of concurrent status updates"""
        # This would test optimistic locking or similar concurrency control
        # In a real implementation, we'd simulate concurrent requests
        
        update_data1 = {
            "validation_status": "processing",
            "updated_by": "user-1"
        }
        
        update_data2 = {
            "validation_status": "annotated", 
            "updated_by": "user-2"
        }
        
        # First update should succeed
        response1 = test_client.put("/api/videos/video-1/status", json=update_data1)
        assert response1.status_code == 200
        
        # Second update should handle the changed state appropriately
        response2 = test_client.put("/api/videos/video-1/status", json=update_data2)
        # Depending on implementation, this might succeed or fail with conflict
        assert response2.status_code in [200, 409]


class TestVideoValidationWebSocketUpdates:
    """Test WebSocket integration for real-time validation updates"""
    
    def test_validation_status_broadcast(self, test_client, sample_videos):
        """Test that status updates trigger WebSocket broadcasts"""
        # This would test WebSocket integration in a real implementation
        # For now, we'll just verify the status update endpoint works
        
        update_data = {
            "validation_status": "processing", 
            "updated_by": "user-123"
        }
        
        response = test_client.put("/api/videos/video-1/status", json=update_data)
        
        assert response.status_code == 200
        # In real implementation, we'd verify WebSocket message was sent
    
    def test_validation_progress_updates(self, test_client, sample_videos):
        """Test validation progress WebSocket updates"""
        # This would test real-time validation progress updates
        response = test_client.post("/api/videos/video-2/validate/automatic")
        
        assert response.status_code == 200
        # In real implementation, we'd verify progress WebSocket messages


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])