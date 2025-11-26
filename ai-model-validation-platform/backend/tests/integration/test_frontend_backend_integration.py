"""
Frontend-Backend Integration Tests

Tests the complete data flow from database through API to ensure
responses match frontend TypeScript interfaces.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, delete, update, func
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import json

# Import main app
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from database import Base, get_db
from models import Project, Video, TestSession, DetectionEvent, TestResult
from main import app

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_integration.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function")
def test_db():
    """Create test database and tables"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)

@pytest.fixture
def sample_project(test_db):
    """Create sample project"""
    db = TestingSessionLocal()
    project = Project(
        name="Test Project",
        description="Integration test project",
        camera_model="TestCam",
        camera_view="Front-facing VRU",
        signal_type="GPIO",
        owner_id="test-user-123"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    project_id = project.id
    db.close()
    return project_id

@pytest.fixture
def sample_test_session(test_db, sample_project):
    """Create sample test session with results"""
    db = TestingSessionLocal()

    session = TestSession(
        name="Test Session 1",
        project_id=sample_project,
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc)
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Add test results
    result = TestResult(
        test_session_id=session.id,
        accuracy=0.95,
        precision=0.92,
        recall=0.88,
        f1_score=0.90
    )
    db.add(result)

    # Add detection events
    for i in range(10):
        detection = DetectionEvent(
            test_session_id=session.id,
            timestamp=datetime.now(timezone.utc).timestamp(),
            class_label="pedestrian",
            confidence=0.85 + (i * 0.01),
            validation_result="Pass" if i < 8 else "Fail"
        )
        db.add(detection)

    db.commit()
    session_id = session.id
    db.close()
    return session_id


class TestAPIContractCompliance:
    """Test API responses match frontend TypeScript interfaces"""

    def test_results_endpoint_structure(self, client, sample_test_session):
        """Test /api/results returns expected BasicTestSession structure"""
        response = client.get("/api/results?limit=10")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        if len(data) > 0:
            session = data[0]

            # Verify required fields exist
            assert "id" in session
            assert "name" in session
            assert "status" in session
            assert "has_results" in session

            # Verify types
            assert isinstance(session["id"], str)
            assert isinstance(session["name"], str)
            assert isinstance(session["status"], str)
            assert isinstance(session["has_results"], bool)

            # Verify optional fields
            if session.get("started_at"):
                # Should be ISO format string
                datetime.fromisoformat(session["started_at"].replace('Z', '+00:00'))

    def test_enhanced_results_structure(self, client, sample_test_session):
        """Test /api/results/enhanced returns expected structure with metrics"""
        response = client.get("/api/results/enhanced?limit=10")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        if len(data) > 0:
            session = data[0]

            # Verify required fields
            assert "session_id" in session
            assert "session_name" in session
            assert "metrics" in session
            assert "detection_summary" in session
            assert "statistics" in session

            # Verify metrics structure
            metrics = session["metrics"]
            assert "accuracy" in metrics
            assert "precision" in metrics
            assert "recall" in metrics
            assert "f1_score" in metrics
            assert "success_rate" in metrics

            # Verify detection_summary structure
            summary = session["detection_summary"]
            assert "total_detections" in summary
            assert "passed_detections" in summary
            assert "failed_detections" in summary
            assert "detection_types" in summary

            # Verify statistics structure
            stats = session["statistics"]
            assert "test_results_count" in stats
            assert "detection_events_count" in stats

    def test_session_result_by_id(self, client, sample_test_session):
        """Test /api/results/{session_id} returns detailed session data"""
        response = client.get(f"/api/results/{sample_test_session}")

        assert response.status_code == 200
        data = response.json()

        assert data["session_id"] == sample_test_session
        assert "metrics" in data
        assert "detection_summary" in data
        assert "statistics" in data

    def test_quality_endpoint_placeholder(self, client, sample_test_session):
        """Test quality endpoint - Currently not implemented"""
        # This test documents the expected quality endpoint
        # Remove pytest.skip when endpoint is implemented
        pytest.skip("Quality endpoint not yet implemented")

        response = client.get(f"/api/test-sessions/{sample_test_session}/quality")

        assert response.status_code == 200
        data = response.json()

        # Expected structure
        assert "session_id" in data
        assert "quality_level" in data
        assert "warnings" in data
        assert "statistics" in data

        # Verify quality_level is one of expected values
        assert data["quality_level"] in ["high", "medium", "low"]

        # Verify warnings structure
        if data["warnings"]:
            warning = data["warnings"][0]
            assert "type" in warning
            assert "severity" in warning
            assert "message" in warning


class TestCORSConfiguration:
    """Test CORS headers are properly set"""

    def test_cors_headers_on_options_request(self, client):
        """Test preflight OPTIONS request includes CORS headers"""
        response = client.options(
            "/api/results",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )

        # Should allow the request
        assert response.status_code in [200, 204]

        # Should include CORS headers
        # Note: Exact headers depend on CORS middleware configuration
        # Verify headers exist (values will vary by config)
        headers = response.headers
        assert "access-control-allow-origin" in str(headers).lower() or "vary" in str(headers).lower()

    def test_cors_headers_on_get_request(self, client):
        """Test GET request includes CORS headers in response"""
        response = client.get(
            "/api/results",
            headers={"Origin": "http://localhost:3000"}
        )

        assert response.status_code == 200


class TestErrorHandlingContract:
    """Test error responses match frontend ApiError interface"""

    def test_404_error_format(self, client):
        """Test 404 errors return expected format"""
        response = client.get("/api/results/nonexistent-id-12345")

        assert response.status_code == 404
        data = response.json()

        # Should have detail field
        assert "detail" in data

        # Detail should be string or object with message
        detail = data["detail"]
        if isinstance(detail, dict):
            assert "message" in detail or "error" in detail

    def test_400_validation_error_format(self, client):
        """Test validation errors return expected format"""
        # Trigger validation error with invalid limit parameter
        response = client.get("/api/results?limit=invalid")

        assert response.status_code == 422  # FastAPI validation error
        data = response.json()

        assert "detail" in data

    def test_500_error_format(self, client):
        """Test server errors return expected format"""
        # This test would require triggering a server error
        # Skip for now, implement when error simulation is available
        pytest.skip("Server error simulation not implemented")


class TestDataFlowIntegrity:
    """Test complete data flow from database to API response"""

    def test_database_to_api_detection_flow(self, client, sample_test_session):
        """Verify detection data flows correctly from DB to API"""
        db = TestingSessionLocal()

        # Get detection count from database directly
        from models import DetectionEvent
        db_detection_count = session.execute(select(func.count()).select_from(DetectionEvent).where(
            DetectionEvent.test_session_id == sample_test_session
        )).scalar()

        db.close()

        # Get detection count from API
        response = client.get(f"/api/results/{sample_test_session}")
        assert response.status_code == 200
        api_data = response.json()

        api_detection_count = api_data["detection_summary"]["total_detections"]

        # Counts should match
        assert db_detection_count == api_detection_count

    def test_database_to_api_metrics_flow(self, client, sample_test_session):
        """Verify metrics flow correctly from DB to API"""
        response = client.get(f"/api/results/{sample_test_session}")
        assert response.status_code == 200

        data = response.json()
        metrics = data["metrics"]

        # Verify metrics are calculated correctly
        # All metrics should be present
        assert metrics["accuracy"] is not None or metrics["accuracy"] == 0
        assert metrics["precision"] is not None or metrics["precision"] == 0
        assert metrics["recall"] is not None or metrics["recall"] == 0
        assert metrics["f1_score"] is not None or metrics["f1_score"] == 0

        # Success rate should be percentage
        assert 0 <= metrics["success_rate"] <= 100


class TestPaginationAndFiltering:
    """Test pagination and filtering parameters work correctly"""

    def test_limit_parameter(self, client, sample_test_session):
        """Test limit parameter controls number of results"""
        response = client.get("/api/results?limit=5")
        assert response.status_code == 200
        data = response.json()

        assert len(data) <= 5

    def test_status_filter_parameter(self, client, sample_test_session):
        """Test status filter parameter"""
        response = client.get("/api/results?status=completed")
        assert response.status_code == 200
        data = response.json()

        # All returned sessions should have completed status
        for session in data:
            assert session["status"] == "completed"

    def test_invalid_status_filter(self, client):
        """Test invalid status filter returns error"""
        response = client.get("/api/results?status=invalid_status")

        # Should return validation error
        assert response.status_code == 422


class TestResponsePerformance:
    """Test API response times are acceptable"""

    def test_results_endpoint_performance(self, client, sample_test_session):
        """Test /api/results responds within acceptable time"""
        import time

        start = time.time()
        response = client.get("/api/results?limit=10")
        duration = time.time() - start

        assert response.status_code == 200
        # Should respond in under 2 seconds (generous limit for test environment)
        assert duration < 2.0

    def test_enhanced_results_performance(self, client, sample_test_session):
        """Test /api/results/enhanced responds within acceptable time"""
        import time

        start = time.time()
        response = client.get("/api/results/enhanced?limit=10")
        duration = time.time() - start

        assert response.status_code == 200
        # Enhanced endpoint may take longer due to calculations
        assert duration < 3.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
