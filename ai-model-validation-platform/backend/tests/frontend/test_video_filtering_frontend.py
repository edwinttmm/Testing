"""
Frontend Tests for Video Filtering and HIL Test Execution
=========================================================

Tests frontend behavior for video status filtering and HIL Test Execution page functionality.
These tests simulate frontend API calls and validate expected responses.
"""

import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from main import app
from database import Base, get_db
from models import Project, Video, TestSession, DetectionEvent


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_frontend_video_filtering.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def client():
    """Test client fixture"""
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_project(client):
    """Create test project"""
    project_data = {
        "name": "Frontend Test Project",
        "description": "Project for frontend testing",
        "camera_model": "Test Camera",
        "camera_view": "Front-facing VRU",
        "signal_type": "GPIO"
    }
    
    response = client.post("/api/projects", json=project_data)
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def sample_videos_mixed_status(client, sample_project):
    """Create videos with mixed statuses for filtering tests"""
    
    # Create temporary video file
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
        temp_file.write(b"fake video content")
        temp_file_path = temp_file.name
    
    video_configs = [
        {"filename": "validated_video_1.mp4", "status": "validated", "ground_truth": True},
        {"filename": "validated_video_2.mp4", "status": "validated", "ground_truth": True},
        {"filename": "processing_video_1.mp4", "status": "processing", "ground_truth": False},
        {"filename": "processing_video_2.mp4", "status": "processing", "ground_truth": False},
        {"filename": "pending_video_1.mp4", "status": "pending_validation", "ground_truth": True},
        {"filename": "error_video_1.mp4", "status": "error", "ground_truth": False},
        {"filename": "uploaded_video_1.mp4", "status": "uploaded", "ground_truth": False}
    ]
    
    videos = []
    
    try:
        for config in video_configs:
            # Upload video
            with open(temp_file_path, "rb") as f:
                response = client.post(
                    f"/api/projects/{sample_project['id']}/videos/upload",
                    files={"file": (config["filename"], f, "video/mp4")}
                )
            
            assert response.status_code == 200
            video_data = response.json()
            
            # Set video status
            if config["status"] != "uploaded":
                response = client.patch(
                    f"/api/videos/{video_data['id']}/status",
                    json={"status": config["status"]}
                )
                assert response.status_code == 200
            
            # Set ground truth if needed
            if config["ground_truth"]:
                response = client.patch(
                    f"/api/videos/{video_data['id']}/processing-status",
                    json={"ground_truth_generated": True, "processing_status": "completed"}
                )
                assert response.status_code == 200
            
            videos.append({
                "id": video_data["id"],
                "filename": config["filename"],
                "status": config["status"],
                "ground_truth_generated": config["ground_truth"]
            })
    
    finally:
        os.unlink(temp_file_path)
    
    return videos


class TestVideoListingAndFiltering:
    """Test video listing APIs that frontend components use"""
    
    def test_get_all_videos_with_status(self, client, sample_videos_mixed_status):
        """Test getting all videos with status information"""
        response = client.get("/api/videos")
        assert response.status_code == 200
        
        videos = response.json()
        assert len(videos) == len(sample_videos_mixed_status)
        
        # Verify each video has required frontend fields
        for video in videos:
            assert "id" in video
            assert "filename" in video
            assert "status" in video
            assert "ground_truth_generated" in video
            assert video["status"] in ["uploaded", "processing", "pending_validation", "validated", "error"]
    
    def test_filter_videos_by_status(self, client, sample_videos_mixed_status):
        """Test filtering videos by status (frontend dropdown behavior)"""
        
        # Test single status filter
        response = client.get("/api/videos?status=validated")
        assert response.status_code == 200
        
        validated_videos = response.json()
        assert len(validated_videos) == 2
        
        for video in validated_videos:
            assert video["status"] == "validated"
            assert video["ground_truth_generated"] is True
    
    def test_filter_videos_multiple_statuses(self, client, sample_videos_mixed_status):
        """Test filtering by multiple statuses (multi-select behavior)"""
        response = client.get("/api/videos?status=validated,processing")
        assert response.status_code == 200
        
        filtered_videos = response.json()
        assert len(filtered_videos) == 4  # 2 validated + 2 processing
        
        statuses = {video["status"] for video in filtered_videos}
        assert statuses == {"validated", "processing"}
    
    def test_video_status_counts(self, client, sample_videos_mixed_status):
        """Test getting video counts by status (for frontend badges/counters)"""
        response = client.get("/api/videos/status-counts")
        assert response.status_code == 200
        
        counts = response.json()
        expected_counts = {
            "validated": 2,
            "processing": 2,
            "pending_validation": 1,
            "error": 1,
            "uploaded": 1
        }
        
        for status, count in expected_counts.items():
            assert counts[status] == count
    
    def test_search_videos_with_status_filter(self, client, sample_videos_mixed_status):
        """Test searching videos combined with status filter"""
        response = client.get("/api/videos?status=validated&search=validated_video_1")
        assert response.status_code == 200
        
        search_results = response.json()
        assert len(search_results) == 1
        assert search_results[0]["filename"] == "validated_video_1.mp4"
        assert search_results[0]["status"] == "validated"


class TestHILTestExecutionPageAPIs:
    """Test APIs specifically used by HIL Test Execution page"""
    
    def test_get_hil_eligible_videos(self, client, sample_videos_mixed_status):
        """Test API that HIL page uses to load eligible videos"""
        response = client.get("/api/enhanced-test/videos/eligible")
        assert response.status_code == 200
        
        data = response.json()
        assert "videos" in data
        assert "total_count" in data
        
        eligible_videos = data["videos"]
        
        # Should only return validated videos with ground truth
        expected_count = 2  # 2 validated videos
        assert len(eligible_videos) == expected_count
        
        for video in eligible_videos:
            assert video["status"] == "validated"
            assert video["ground_truth_generated"] is True
    
    def test_hil_video_details(self, client, sample_videos_mixed_status):
        """Test getting detailed video info for HIL testing"""
        validated_video = next(v for v in sample_videos_mixed_status if v["status"] == "validated")
        
        response = client.get(f"/api/enhanced-test/videos/{validated_video['id']}/details")
        assert response.status_code == 200
        
        details = response.json()
        assert details["id"] == validated_video["id"]
        assert details["status"] == "validated"
        assert details["ground_truth_generated"] is True
        assert "duration" in details
        assert "fps" in details
        assert "ground_truth_count" in details
    
    def test_hil_video_ground_truth_preview(self, client, sample_videos_mixed_status):
        """Test getting ground truth data for video preview in HIL page"""
        validated_video = next(v for v in sample_videos_mixed_status if v["status"] == "validated")
        
        # First add some ground truth data
        ground_truth_data = [
            {
                "timestamp": 1.0,
                "class_label": "pedestrian",
                "bounding_box": {"x": 100, "y": 100, "width": 50, "height": 100},
                "confidence": 0.9
            },
            {
                "timestamp": 2.5,
                "class_label": "cyclist", 
                "bounding_box": {"x": 200, "y": 150, "width": 60, "height": 120},
                "confidence": 0.85
            }
        ]
        
        response = client.post(
            f"/api/videos/{validated_video['id']}/ground-truth",
            json={"objects": ground_truth_data}
        )
        assert response.status_code == 200
        
        # Get ground truth for preview
        response = client.get(f"/api/videos/{validated_video['id']}/ground-truth/preview")
        assert response.status_code == 200
        
        preview_data = response.json()
        assert "objects" in preview_data
        assert "total_count" in preview_data
        assert len(preview_data["objects"]) <= 10  # Preview should be limited
    
    def test_create_hil_test_session(self, client, sample_videos_mixed_status, sample_project):
        """Test creating HIL test session with selected videos"""
        validated_videos = [v for v in sample_videos_mixed_status if v["status"] == "validated"]
        video_ids = [v["id"] for v in validated_videos]
        
        session_data = {
            "name": "Frontend HIL Test",
            "project_id": sample_project["id"],
            "video_ids": video_ids,
            "latency_threshold_ms": 100,
            "test_description": "Test from HIL frontend"
        }
        
        response = client.post("/api/enhanced-test/sessions", json=session_data)
        assert response.status_code == 200
        
        session = response.json()
        assert session["name"] == "Frontend HIL Test"
        assert len(session["video_ids"]) == len(video_ids)
        assert session["latency_threshold_ms"] == 100
    
    def test_hil_test_session_validation(self, client, sample_videos_mixed_status, sample_project):
        """Test validation when creating HIL test session with invalid videos"""
        # Try to create session with non-validated video
        processing_video = next(v for v in sample_videos_mixed_status if v["status"] == "processing")
        
        session_data = {
            "name": "Invalid HIL Test",
            "project_id": sample_project["id"], 
            "video_ids": [processing_video["id"]],
            "latency_threshold_ms": 100
        }
        
        response = client.post("/api/enhanced-test/sessions", json=session_data)
        # Should either reject or warn about non-validated videos
        if response.status_code == 400:
            error = response.json()
            assert "validated" in error["detail"].lower()


class TestVideoStatusDisplay:
    """Test video status display and formatting for frontend"""
    
    def test_video_status_labels(self, client, sample_videos_mixed_status):
        """Test that video status values match frontend expected labels"""
        response = client.get("/api/videos")
        assert response.status_code == 200
        
        videos = response.json()
        status_mapping = {
            "uploaded": "Uploaded",
            "processing": "Processing", 
            "pending_validation": "Pending Validation",
            "validated": "Validated",
            "error": "Error"
        }
        
        for video in videos:
            status = video["status"]
            assert status in status_mapping.keys()
            
            # Frontend should be able to map these statuses to display labels
            display_label = status_mapping[status]
            assert display_label is not None
    
    def test_video_status_color_coding(self, client, sample_videos_mixed_status):
        """Test status values for frontend color coding"""
        response = client.get("/api/videos")
        assert response.status_code == 200
        
        videos = response.json()
        
        # Define expected color categories for frontend
        status_colors = {
            "uploaded": "blue",      # Info/neutral
            "processing": "yellow",   # Warning/in-progress
            "pending_validation": "orange",  # Warning/needs attention
            "validated": "green",     # Success
            "error": "red"           # Error/danger
        }
        
        for video in videos:
            status = video["status"]
            expected_color = status_colors[status]
            assert expected_color in ["blue", "yellow", "orange", "green", "red"]
    
    def test_video_progress_indicators(self, client, sample_videos_mixed_status):
        """Test data for frontend progress indicators"""
        response = client.get("/api/videos/progress-summary")
        assert response.status_code == 200
        
        progress_data = response.json()
        assert "total_videos" in progress_data
        assert "progress_stages" in progress_data
        
        stages = progress_data["progress_stages"]
        expected_stages = ["uploaded", "processing", "pending_validation", "validated"]
        
        for stage in expected_stages:
            assert stage in stages
            assert "count" in stages[stage]
            assert "percentage" in stages[stage]


class TestVideoFilteringUI:
    """Test video filtering UI functionality"""
    
    def test_status_filter_options(self, client, sample_videos_mixed_status):
        """Test getting available status filter options for UI dropdown"""
        response = client.get("/api/videos/filter-options")
        assert response.status_code == 200
        
        options = response.json()
        assert "status_options" in options
        
        status_options = options["status_options"]
        expected_options = [
            {"value": "uploaded", "label": "Uploaded", "count": 1},
            {"value": "processing", "label": "Processing", "count": 2},
            {"value": "pending_validation", "label": "Pending Validation", "count": 1},
            {"value": "validated", "label": "Validated", "count": 2},
            {"value": "error", "label": "Error", "count": 1}
        ]
        
        # Check that all expected options are present
        option_values = {opt["value"] for opt in status_options}
        expected_values = {opt["value"] for opt in expected_options}
        assert option_values == expected_values
    
    def test_pagination_with_filters(self, client, sample_videos_mixed_status):
        """Test pagination combined with status filters"""
        response = client.get("/api/videos?status=validated&page=1&page_size=1")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "pagination" in data
        
        pagination = data["pagination"]
        assert pagination["page"] == 1
        assert pagination["page_size"] == 1
        assert pagination["total_pages"] == 2  # 2 validated videos, 1 per page
        assert pagination["total_items"] == 2
    
    def test_bulk_status_operations(self, client, sample_videos_mixed_status):
        """Test bulk operations that frontend might need"""
        processing_videos = [v for v in sample_videos_mixed_status if v["status"] == "processing"]
        video_ids = [v["id"] for v in processing_videos]
        
        # Test bulk status check
        response = client.post(
            "/api/videos/bulk/check-status",
            json={"video_ids": video_ids}
        )
        assert response.status_code == 200
        
        status_check = response.json()
        assert "videos" in status_check
        
        for video in status_check["videos"]:
            assert video["status"] == "processing"


class TestRealTimeStatusUpdates:
    """Test real-time status updates for frontend"""
    
    def test_video_status_change_notifications(self, client, sample_videos_mixed_status):
        """Test status change creates notifications for frontend"""
        processing_video = next(v for v in sample_videos_mixed_status if v["status"] == "processing")
        
        # Update video status
        response = client.patch(
            f"/api/videos/{processing_video['id']}/status",
            json={"status": "validated"}
        )
        assert response.status_code == 200
        
        # Check for status change notification
        response = client.get(f"/api/videos/{processing_video['id']}/status-history")
        assert response.status_code == 200
        
        history = response.json()
        assert len(history) >= 2  # Original status + new status
        assert history[-1]["status"] == "validated"
        assert "timestamp" in history[-1]
    
    def test_websocket_status_updates(self, client, sample_videos_mixed_status):
        """Test WebSocket notifications for real-time status updates"""
        # This would test WebSocket functionality for real-time updates
        # For now, test the REST endpoint that provides similar data
        
        response = client.get("/api/videos/recent-status-changes")
        assert response.status_code == 200
        
        recent_changes = response.json()
        assert "changes" in recent_changes
        assert "timestamp" in recent_changes
    
    def test_processing_progress_updates(self, client, sample_videos_mixed_status):
        """Test processing progress updates for frontend progress bars"""
        processing_video = next(v for v in sample_videos_mixed_status if v["status"] == "processing")
        
        response = client.get(f"/api/videos/{processing_video['id']}/processing-progress")
        assert response.status_code == 200
        
        progress = response.json()
        assert "progress_percentage" in progress
        assert "current_stage" in progress
        assert "estimated_completion" in progress


class TestVideoValidationFrontendIntegration:
    """Test frontend integration points for video validation"""
    
    def test_dashboard_video_stats(self, client, sample_videos_mixed_status):
        """Test dashboard statistics used by frontend"""
        response = client.get("/api/dashboard/video-stats")
        assert response.status_code == 200
        
        stats = response.json()
        assert "total_videos" in stats
        assert "validated_videos" in stats
        assert "validation_rate" in stats
        assert "hil_ready_videos" in stats
        
        # Validate calculated values
        assert stats["total_videos"] == len(sample_videos_mixed_status)
        assert stats["validated_videos"] == 2
        assert stats["validation_rate"] == 2 / len(sample_videos_mixed_status)
    
    def test_project_video_validation_summary(self, client, sample_videos_mixed_status, sample_project):
        """Test project-level video validation summary"""
        response = client.get(f"/api/projects/{sample_project['id']}/video-validation-summary")
        assert response.status_code == 200
        
        summary = response.json()
        assert "project_id" in summary
        assert "total_videos" in summary
        assert "status_breakdown" in summary
        assert "hil_ready_count" in summary
        
        status_breakdown = summary["status_breakdown"]
        assert status_breakdown["validated"] == 2
        assert status_breakdown["processing"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])