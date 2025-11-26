"""
Pytest Configuration and Shared Fixtures for HIL Detection Pipeline Tests

Provides common fixtures, mock data, and utilities for test execution.
"""

import pytest
import time
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone


@pytest.fixture
def mock_labjack_connection():
    """Standard mock LabJack connection manager"""
    manager = Mock()
    manager.is_connected.return_value = True
    manager.connect.return_value = True
    manager.read_voltage.return_value = 3.5
    manager.disconnect = Mock()
    return manager


@pytest.fixture
def mock_database_session():
    """Standard mock database session"""
    db = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.close = Mock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


@pytest.fixture
def sample_detection_event():
    """Sample detection event for testing"""
    from services.simple_labjack_detection import DetectionEvent

    return DetectionEvent(
        id="test_detection_123",
        session_id="test_session",
        timestamp=datetime.now(timezone.utc),
        channel="AIN0",
        voltage=3.5,
        threshold=2.5,
        detected=True,
        is_duplicate=False,
        metadata={
            'sample_rate': 1000,
            'debounce_ms': 100
        },
        video_relative_timestamp=1.5,
        actual_latency_ms=45.0
    )


@pytest.fixture
def sample_video_timing_config():
    """Sample video timing configuration"""
    return {
        'video_id': 'test_video_123',
        'fps': 24,
        'duration': 5.0,
        'channels': ['AIN0'],
        'voltage_threshold': 2.5,
        'sample_rate': 1000,
        'debounce_ms': 100,
        'enable_websocket': True,
        'store_in_db': True
    }


@pytest.fixture
def sample_test_session():
    """Sample test session data"""
    return {
        'id': 'test_session_123',
        'name': 'HIL Test Session',
        'video_id': 'video_123',
        'status': 'running',
        'started_at': datetime.now(timezone.utc),
        'video_start_timestamp': time.time()
    }


@pytest.fixture(autouse=True)
def cleanup_detection_service():
    """Clean up detection service after each test"""
    yield
    # Cleanup happens after test
    from services.simple_labjack_detection import get_detection_service
    try:
        service = get_detection_service()
        # Stop all active sessions
        for session_id in list(service.active_sessions.keys()):
            service.stop_session_monitoring(session_id)
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def mock_websocket_emit():
    """Mock WebSocket emission function"""
    from unittest.mock import AsyncMock
    return AsyncMock()


@pytest.fixture
def mock_ground_truth_data():
    """Sample ground truth data for matching tests"""
    return [
        {
            'frame_number': 118,
            'timestamp': 4.917,
            'object_type': 'pedestrian',
            'bounding_box': {'x': 100, 'y': 200, 'width': 50, 'height': 100}
        },
        {
            'frame_number': 119,
            'timestamp': 4.958,
            'object_type': 'pedestrian',
            'bounding_box': {'x': 105, 'y': 200, 'width': 50, 'height': 100}
        },
        {
            'frame_number': 120,
            'timestamp': 5.000,
            'object_type': 'pedestrian',
            'bounding_box': {'x': 110, 'y': 200, 'width': 50, 'height': 100}
        }
    ]


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance benchmark"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running (> 1s)"
    )
