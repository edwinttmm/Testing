"""
Test configuration for London School TDD
Provides comprehensive mocks for all external dependencies
"""
import pytest
from unittest.mock import Mock, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_db_session():
    """Mock database session for London School TDD"""
    session = Mock()
    session.query.return_value = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.refresh = Mock()
    session.close = Mock()
    return session


@pytest.fixture
def mock_project_data():
    """Mock project data for testing"""
    return {
        "name": "Test Project",
        "description": "Test Description",
        "camera_model": "Sony IMX390",
        "camera_view": "Front-facing VRU",
        "signal_type": "GPIO"
    }


@pytest.fixture
def mock_video_data():
    """Mock video data for testing"""
    return {
        "filename": "test_video.mp4",
        "file_path": "/uploads/test_video.mp4",
        "project_id": "project_123",
        "file_size": 1024000,
        "duration": 60.0
    }


@pytest.fixture
def mock_file_system():
    """Mock file system operations"""
    mock_fs = Mock()
    mock_fs.exists.return_value = True
    mock_fs.makedirs = Mock()
    mock_fs.remove = Mock()
    return mock_fs


@pytest.fixture
def mock_external_api():
    """Mock external API calls"""
    mock_api = Mock()
    mock_api.post.return_value = Mock(status_code=200, json=lambda: {"success": True})
    mock_api.get.return_value = Mock(status_code=200, json=lambda: {"data": []})
    return mock_api


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Automatically setup test environment for each test"""
    # Set test mode
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    
    yield
    
    # Cleanup
    if "TESTING" in os.environ:
        del os.environ["TESTING"]
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]