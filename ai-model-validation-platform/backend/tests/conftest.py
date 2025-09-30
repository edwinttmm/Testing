"""
Pytest Configuration and Shared Fixtures for Video Validation System Tests
==========================================================================

Central configuration file for all video validation system tests,
providing shared fixtures, test utilities, and configuration.
"""

"""
PyTest Configuration and Shared Fixtures for LabJack Hybrid Logging System Tests
===============================================================================

This configuration file provides:
- Common test fixtures for all test modules
- Test markers for categorizing tests
- Database setup for testing
- Mock services and utilities
- Performance testing configuration
- Hardware detection utilities

Test Categories (Markers):
- hardware: Tests requiring real LabJack hardware
- integration: Integration tests with mock services  
- performance: Performance benchmarking tests
- stress: Stress and load testing
- fallback: Fallback and error handling tests
- frontend: Frontend integration tests
- compatibility: Backward compatibility tests
- ci_cd: CI/CD specific tests
"""

import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from datetime import datetime, timezone
import tempfile
import shutil
from pathlib import Path

# Import application components
from main import app
from models import Base, Video, VideoValidationCriteria, VideoValidationResult, VideoStatusTransition
from schemas_video_validation import VideoValidationStatus, ValidationStatus, ValidationType
from config import get_db


# Test database configuration
TEST_DATABASE_URL = "sqlite:///./test_video_validation_system.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session")
def test_database():
    """Create test database for the entire test session"""
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def test_db(test_database):
    """Create test database session for individual tests"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()  # Rollback any uncommitted changes
        db.close()


@pytest.fixture
def test_client(test_database):
    """Create FastAPI test client with test database override"""
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
    app.dependency_overrides.clear()


@pytest.fixture
def temp_upload_dir():
    """Create temporary directory for file uploads during tests"""
    temp_dir = tempfile.mkdtemp(prefix="test_uploads_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_video_data():
    """Standard video data for testing"""
    return {
        "id": "test-video-standard",
        "filename": "standard_test.mp4",
        "file_path": "/uploads/standard_test.mp4",
        "project_id": "test-project-standard",
        "validation_status": "uploaded",
        "processing_status": "pending",
        "ground_truth_generated": False
    }


@pytest.fixture
def annotated_video_data():
    """Video data with ground truth for validation testing"""
    return {
        "id": "test-video-annotated",
        "filename": "annotated_test.mp4",
        "file_path": "/uploads/annotated_test.mp4", 
        "project_id": "test-project-annotated",
        "validation_status": "annotated",
        "processing_status": "completed",
        "ground_truth_generated": True,
        "ground_truth_count": 20,
        "ground_truth_quality_score": 0.92
    }


@pytest.fixture
def validated_video_data():
    """Video data that has been validated and ready for HIL testing"""
    return {
        "id": "test-video-validated",
        "filename": "validated_test.mp4",
        "file_path": "/uploads/validated_test.mp4",
        "project_id": "test-project-validated",
        "validation_status": "validated",
        "processing_status": "completed", 
        "ground_truth_generated": True,
        "ground_truth_count": 25,
        "ground_truth_quality_score": 0.95,
        "validation_type": "automatic",
        "validated_at": datetime.now(timezone.utc),
        "validated_by": "system",
        "hil_testing_ready": True
    }


@pytest.fixture
def standard_validation_criteria(test_db):
    """Create standard validation criteria for testing"""
    criteria = [
        VideoValidationCriteria(
            id="criteria-min-objects",
            name="minimum_ground_truth_objects",
            description="Minimum number of ground truth objects required",
            criteria_type="automatic",
            threshold_value=10.0,
            comparison_operator="gte",
            is_required=True,
            created_by="test-system"
        ),
        VideoValidationCriteria(
            id="criteria-quality-score",
            name="ground_truth_quality_score", 
            description="Minimum quality score for ground truth annotations",
            criteria_type="automatic",
            threshold_value=0.8,
            comparison_operator="gte",
            is_required=True,
            created_by="test-system"
        ),
        VideoValidationCriteria(
            id="criteria-duration",
            name="video_duration",
            description="Minimum video duration in seconds",
            criteria_type="automatic", 
            threshold_value=30.0,
            comparison_operator="gte",
            is_required=False,
            created_by="test-system"
        ),
        VideoValidationCriteria(
            id="criteria-manual-quality",
            name="manual_annotation_quality",
            description="Manual assessment of annotation quality",
            criteria_type="manual",
            is_required=True,
            created_by="test-system"
        ),
        VideoValidationCriteria(
            id="criteria-manual-coverage",
            name="manual_object_coverage",
            description="Manual assessment of object coverage",
            criteria_type="manual", 
            is_required=True,
            created_by="test-system"
        )
    ]
    
    for criterion in criteria:
        test_db.add(criterion)
    test_db.commit()
    
    return criteria


@pytest.fixture
def video_status_transition_samples():
    """Sample data for video status transitions"""
    return [
        {
            "from_status": "uploaded",
            "to_status": "processing",
            "changed_by": "user-123",
            "notes": "Started processing workflow"
        },
        {
            "from_status": "processing", 
            "to_status": "annotated",
            "changed_by": "system",
            "notes": "Ground truth generation completed"
        },
        {
            "from_status": "annotated",
            "to_status": "validated",
            "changed_by": "validator-456",
            "notes": "Automatic validation passed"
        },
        {
            "from_status": "validated",
            "to_status": "ready_for_testing",
            "changed_by": "approver-789",
            "notes": "Approved for HIL testing"
        }
    ]


@pytest.fixture 
def batch_video_data():
    """Generate batch video data for testing"""
    def _generate_batch(count=10, base_status="uploaded"):
        videos = []
        for i in range(count):
            videos.append({
                "id": f"batch-video-{i}",
                "filename": f"batch_test_{i}.mp4",
                "file_path": f"/uploads/batch_test_{i}.mp4",
                "project_id": "batch-test-project",
                "validation_status": base_status,
                "processing_status": "pending" if base_status == "uploaded" else "completed",
                "ground_truth_generated": base_status != "uploaded",
                "ground_truth_count": 15 + i if base_status != "uploaded" else 0,
                "ground_truth_quality_score": 0.85 + (i * 0.01) if base_status != "uploaded" else None
            })
        return videos
    
    return _generate_batch


@pytest.fixture
def legacy_video_migration_data():
    """Legacy video data for migration testing"""
    return [
        {
            "id": "legacy-completed-1",
            "filename": "legacy1.mp4", 
            "status": "completed",  # Legacy status
            "processing_status": "completed",
            "ground_truth_generated": True
        },
        {
            "id": "legacy-completed-2",
            "filename": "legacy2.mp4",
            "status": "completed",  # Legacy status
            "processing_status": "completed", 
            "ground_truth_generated": True
        },
        {
            "id": "legacy-uploaded-1",
            "filename": "legacy3.mp4",
            "status": "uploaded",  # Legacy status
            "processing_status": "pending",
            "ground_truth_generated": False
        },
        {
            "id": "legacy-error-1",
            "filename": "legacy4.mp4", 
            "status": "error",  # Legacy status
            "processing_status": "failed",
            "ground_truth_generated": False
        }
    ]


@pytest.fixture
def mock_validation_service():
    """Mock video validation service for isolated testing"""
    from unittest.mock import Mock
    from services.video_validation_service import VideoValidationService
    
    mock_service = Mock(spec=VideoValidationService)
    
    # Configure common mock returns
    mock_service.transition_video_status.return_value = Mock()
    mock_service.run_automatic_validation.return_value = Mock(
        overall_status=ValidationStatus.PASSED,
        validation_type=ValidationType.AUTOMATIC,
        criteria_results=[]
    )
    mock_service.complete_manual_validation.return_value = Mock(
        overall_status=ValidationStatus.PASSED,
        validation_type=ValidationType.MANUAL,
        validated_by="test-reviewer"
    )
    
    return mock_service


# Test utilities
class TestDataHelper:
    """Helper class for creating test data"""
    
    @staticmethod
    def create_video(db, video_data):
        """Create a video record in the test database"""
        video = Video(**video_data)
        db.add(video)
        db.commit()
        db.refresh(video)
        return video
    
    @staticmethod
    def create_validation_result(db, video_id, status="passed", validation_type="automatic"):
        """Create a validation result record"""
        result = VideoValidationResult(
            video_id=video_id,
            overall_status=status,
            validation_type=validation_type,
            validated_by="test-system",
            validated_at=datetime.now(timezone.utc)
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        return result
    
    @staticmethod
    def create_status_transition(db, video_id, from_status, to_status, changed_by="test-user"):
        """Create a status transition record"""
        transition = VideoStatusTransition(
            video_id=video_id,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            changed_at=datetime.now(timezone.utc),
            notes=f"Test transition from {from_status} to {to_status}"
        )
        db.add(transition)
        db.commit()
        db.refresh(transition)
        return transition


@pytest.fixture
def test_data_helper():
    """Provide test data helper utility"""
    return TestDataHelper


# Performance testing fixtures
@pytest.fixture
def performance_test_config():
    """Configuration for performance tests"""
    return {
        "small_batch_size": 10,
        "medium_batch_size": 50, 
        "large_batch_size": 100,
        "concurrent_threads": 5,
        "timeout_seconds": 30,
        "max_response_time_ms": 5000,
        "max_batch_processing_time_s": 15
    }


# Error simulation fixtures
@pytest.fixture
def error_simulation_data():
    """Data for testing error conditions"""
    return {
        "invalid_video_ids": ["non-existent-1", "non-existent-2"],
        "invalid_statuses": ["invalid_status", "bad_status"],
        "insufficient_ground_truth_videos": [
            {
                "id": "insufficient-gt-1",
                "ground_truth_count": 3,  # Below threshold
                "ground_truth_quality_score": 0.5  # Below threshold
            }
        ],
        "corrupted_data_scenarios": [
            {"field": "ground_truth_count", "value": -1},
            {"field": "ground_truth_quality_score", "value": 1.5},  # Over 1.0
            {"field": "validation_status", "value": None}
        ]
    }


# Async test support
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Test markers for categorizing tests
pytest_plugins = []

def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Tests that take longer to run")
    config.addinivalue_line("markers", "database: Tests that require database")
    config.addinivalue_line("markers", "migration: Database migration tests")


# Custom test collection
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location"""
    for item in items:
        # Add markers based on test file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        
        # Add database marker for tests using database fixtures
        if any(fixture in item.fixturenames for fixture in ['test_db', 'test_client']):
            item.add_marker(pytest.mark.database)
        
        # Add slow marker for performance and e2e tests
        if any(marker in item.keywords for marker in ['performance', 'e2e']):
            item.add_marker(pytest.mark.slow)