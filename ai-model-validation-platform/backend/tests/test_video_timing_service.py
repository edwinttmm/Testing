"""
Integration Tests for Video Timing Service

Tests the video timing service functionality including:
- High-precision timestamp recording
- LabJack synchronization
- Latency calculation
- Database integration
- API endpoints

Run with: python -m pytest tests/test_video_timing_service.py -v
"""

import pytest
import time
import uuid
import asyncio
import json
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import services and models
from services.video_timing_service import (
    VideoTimingService,
    get_video_timing_service,
    VideoTimingData,
    LatencyMeasurement,
    VideoTimingError,
    start_video_timing,
    get_video_start_time,
    calculate_latency
)

from database import Base, get_db
from models import TestSession, Video, Project

# Import routes
from routes.video_timing import router as timing_router
from main import app  # Assuming main.py contains the FastAPI app

# Test database configuration
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_video_timing.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Override database dependency
app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)


@pytest.fixture(scope="module")
def setup_database():
    """Setup test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(setup_database):
    """Create database session for tests"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_project(db_session):
    """Create test project"""
    project = Project(
        id=str(uuid.uuid4()),
        name="Test Video Timing Project",
        description="Project for testing video timing",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO"
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def test_video(db_session, test_project):
    """Create test video"""
    video = Video(
        id=str(uuid.uuid4()),
        filename="test_video.mp4",
        file_path="/test/path/test_video.mp4",
        project_id=test_project.id,
        duration=30.0,
        fps=30.0,
        resolution="1920x1080"
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


@pytest.fixture
def test_session(db_session, test_project, test_video):
    """Create test session"""
    session = TestSession(
        id=str(uuid.uuid4()),
        name="Test Video Timing Session",
        project_id=test_project.id,
        video_id=test_video.id,
        tolerance_ms=100,
        status="created"
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture
def timing_service():
    """Get video timing service instance"""
    return get_video_timing_service()


@pytest.fixture
def mock_labjack_service():
    """Mock LabJack service for testing"""
    mock_service = Mock()
    mock_service.start_monitoring.return_value = True
    mock_service.get_detection_timestamp.return_value = time.time() + 0.1  # 100ms later
    return mock_service


class TestVideoTimingService:
    """Test cases for VideoTimingService class"""
    
    def test_service_initialization(self, timing_service):
        """Test service initializes correctly"""
        assert timing_service is not None
        assert hasattr(timing_service, '_timing_cache')
        assert hasattr(timing_service, '_session_videos')
        assert hasattr(timing_service, '_timer_precision')
        
        # Test singleton behavior
        service2 = get_video_timing_service()
        assert timing_service is service2
    
    def test_timer_precision_check(self, timing_service):
        """Test timer precision measurement"""
        precision = timing_service._timer_precision
        assert precision > 0
        assert precision < 1000000  # Should be less than 1ms
        
        stats = timing_service.get_timing_statistics()
        assert stats['timer_precision_ns'] == precision
        assert stats['precision_class'] in ['high', 'standard']
    
    def test_start_video_timing(self, timing_service, test_session, test_video, db_session):
        """Test starting video timing"""
        session_id = test_session.id
        video_id = test_video.id
        
        # Clear any existing timing data
        timing_service.clear_session_timing(session_id)
        
        # Start timing
        timestamp = timing_service.start_video_timing(session_id, video_id, db_session)
        
        # Verify timestamp
        assert timestamp > 0
        assert isinstance(timestamp, float)
        
        # Check timing data is cached
        timing_data = timing_service.get_timing_data(session_id)
        assert timing_data is not None
        assert timing_data.session_id == session_id
        assert timing_data.video_id == video_id
        assert timing_data.start_timestamp == timestamp
        
        # Verify session videos tracking
        session_videos = timing_service.get_session_videos(session_id)
        assert video_id in session_videos
    
    def test_get_video_start_time(self, timing_service, test_session, test_video, db_session):
        """Test retrieving video start time"""
        session_id = test_session.id
        video_id = test_video.id
        
        # Start timing first
        original_timestamp = timing_service.start_video_timing(session_id, video_id, db_session)
        
        # Get start time from cache
        retrieved_timestamp = timing_service.get_video_start_time(session_id, db_session)
        
        assert retrieved_timestamp == original_timestamp
        
        # Clear cache and test database retrieval
        timing_service.clear_session_timing(session_id)
        
        # Should still retrieve from database (if implemented)
        db_timestamp = timing_service.get_video_start_time(session_id, db_session)
        # Note: This depends on database field implementation
        
        # Test non-existent session
        fake_session_id = str(uuid.uuid4())
        none_timestamp = timing_service.get_video_start_time(fake_session_id, db_session)
        assert none_timestamp is None
    
    def test_calculate_latency(self, timing_service, test_session, test_video, db_session):
        """Test latency calculation"""
        session_id = test_session.id
        video_id = test_video.id
        
        # Start timing
        video_start_time = timing_service.start_video_timing(session_id, video_id, db_session)
        
        # Simulate detection after 50ms
        detection_timestamp = video_start_time + 0.050  # 50ms later
        
        # Calculate latency
        measurement = timing_service.calculate_latency(session_id, detection_timestamp, db_session)
        
        assert measurement is not None
        assert measurement.session_id == session_id
        assert measurement.video_start_time == video_start_time
        assert measurement.detection_timestamp == detection_timestamp
        assert abs(measurement.latency_ms - 50.0) < 1.0  # Should be ~50ms
        assert measurement.precision_indicator in ['high', 'standard']
        
        # Test with no video timing
        fake_session_id = str(uuid.uuid4())
        no_measurement = timing_service.calculate_latency(fake_session_id, detection_timestamp, db_session)
        assert no_measurement is None
    
    def test_synchronize_with_labjack(self, timing_service, test_session, test_video, 
                                    db_session, mock_labjack_service):
        """Test LabJack synchronization"""
        session_id = test_session.id
        video_id = test_video.id
        
        # Start timing first
        timing_service.start_video_timing(session_id, video_id, db_session)
        
        # Test synchronization
        sync_result = timing_service.synchronize_with_labjack(session_id, mock_labjack_service)
        
        assert sync_result is True
        mock_labjack_service.start_monitoring.assert_called_once()
        
        # Verify call arguments
        call_args = mock_labjack_service.start_monitoring.call_args
        assert call_args[1]['session_id'] == session_id
        assert 'reference_timestamp' in call_args[1]
        assert 'sync_timestamp' in call_args[1]
        
        # Test with no timing data
        fake_session_id = str(uuid.uuid4())
        no_sync_result = timing_service.synchronize_with_labjack(fake_session_id, mock_labjack_service)
        assert no_sync_result is False
        
        # Test with service that doesn't support start_monitoring
        bad_service = Mock(spec=[])  # No start_monitoring method
        bad_sync_result = timing_service.synchronize_with_labjack(session_id, bad_service)
        assert bad_sync_result is False
    
    def test_service_statistics(self, timing_service, test_session, test_video, db_session):
        """Test service statistics"""
        # Get initial stats
        initial_stats = timing_service.get_timing_statistics()
        initial_sessions = initial_stats['active_sessions']
        
        # Add timing data
        session_id = test_session.id
        video_id = test_video.id
        timing_service.start_video_timing(session_id, video_id, db_session)
        
        # Get updated stats
        updated_stats = timing_service.get_timing_statistics()
        
        assert updated_stats['active_sessions'] >= initial_sessions
        assert updated_stats['total_videos'] >= 1
        assert updated_stats['timer_precision_ns'] > 0
        assert updated_stats['precision_class'] in ['high', 'standard']
        assert updated_stats['cache_size_bytes'] > 0
        
        # Check active sessions list
        active_sessions = timing_service.get_active_sessions()
        assert session_id in active_sessions
    
    def test_clear_session_timing(self, timing_service, test_session, test_video, db_session):
        """Test clearing session timing data"""
        session_id = test_session.id
        video_id = test_video.id
        
        # Start timing
        timing_service.start_video_timing(session_id, video_id, db_session)
        
        # Verify data exists
        assert timing_service.get_timing_data(session_id) is not None
        assert timing_service.get_session_videos(session_id) != []
        
        # Clear timing data
        cleared = timing_service.clear_session_timing(session_id)
        assert cleared is True
        
        # Verify data is cleared
        assert timing_service.get_timing_data(session_id) is None
        assert timing_service.get_session_videos(session_id) == []
        
        # Test clearing non-existent session
        fake_session_id = str(uuid.uuid4())
        not_cleared = timing_service.clear_session_timing(fake_session_id)
        assert not_cleared is False


class TestVideoTimingAPI:
    """Test cases for Video Timing API endpoints"""
    
    def test_start_video_timing_endpoint(self, test_session, test_video):
        """Test POST /api/sessions/{id}/start-video"""
        session_id = test_session.id
        video_id = test_video.id
        
        # Clear any existing timing data
        get_video_timing_service().clear_session_timing(session_id)
        
        payload = {
            "video_id": video_id,
            "sync_labjack": False  # Disable for simpler test
        }
        
        response = client.post(f"/api/sessions/{session_id}/start-video", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert 'data' in data
        assert 'start_timestamp' in data['data']
        assert data['data']['video_id'] == video_id
        assert isinstance(data['data']['start_timestamp'], float)
    
    def test_get_video_timing_endpoint(self, test_session, test_video):
        """Test GET /api/sessions/{id}/video-timing"""
        session_id = test_session.id
        video_id = test_video.id
        
        # Start timing first
        get_video_timing_service().start_video_timing(session_id, video_id)
        
        response = client.get(f"/api/sessions/{session_id}/video-timing")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert 'data' in data
        assert 'start_timestamp' in data['data']
        assert data['data']['session_id'] == session_id
        assert data['data']['video_id'] == video_id
        assert data['data']['source'] == 'cache'
    
    def test_calculate_latency_endpoint(self, test_session, test_video):
        """Test POST /api/sessions/{id}/calculate-latency"""
        session_id = test_session.id
        video_id = test_video.id
        
        # Start timing
        start_time = get_video_timing_service().start_video_timing(session_id, video_id)
        
        # Calculate latency for detection 75ms later
        detection_timestamp = start_time + 0.075
        
        payload = {
            "detection_timestamp": detection_timestamp
        }
        
        response = client.post(f"/api/sessions/{session_id}/calculate-latency", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert 'data' in data
        assert 'latency_ms' in data['data']
        assert abs(data['data']['latency_ms'] - 75.0) < 1.0
        assert data['data']['session_id'] == session_id
    
    def test_timing_statistics_endpoint(self, test_session):
        """Test GET /api/sessions/{id}/timing-stats"""
        session_id = test_session.id
        
        response = client.get(f"/api/sessions/{session_id}/timing-stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert 'data' in data
        assert 'active_sessions' in data['data']
        assert 'timer_precision_ns' in data['data']
        assert 'precision_class' in data['data']
        assert data['data']['requested_session_id'] == session_id
    
    def test_clear_timing_endpoint(self, test_session, test_video):
        """Test DELETE /api/sessions/{id}/clear-timing"""
        session_id = test_session.id
        video_id = test_video.id
        
        # Start timing
        get_video_timing_service().start_video_timing(session_id, video_id)
        
        response = client.delete(f"/api/sessions/{session_id}/clear-timing")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['data']['cleared'] is True
        assert data['data']['session_id'] == session_id
        
        # Verify data is cleared
        timing_data = get_video_timing_service().get_timing_data(session_id)
        assert timing_data is None
    
    def test_health_check_endpoint(self):
        """Test GET /api/sessions/timing-service/health"""
        response = client.get("/api/sessions/timing-service/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['data']['service'] == 'VideoTimingService'
        assert data['data']['status'] == 'healthy'
        assert 'timer_precision_class' in data['data']
    
    def test_invalid_session_handling(self):
        """Test API endpoints with invalid session IDs"""
        fake_session_id = str(uuid.uuid4())
        
        # Test start video timing
        payload = {"video_id": str(uuid.uuid4())}
        response = client.post(f"/api/sessions/{fake_session_id}/start-video", json=payload)
        assert response.status_code == 404
        
        # Test get timing data
        response = client.get(f"/api/sessions/{fake_session_id}/video-timing")
        assert response.status_code == 404
        
        # Test calculate latency
        payload = {"detection_timestamp": time.time()}
        response = client.post(f"/api/sessions/{fake_session_id}/calculate-latency", json=payload)
        assert response.status_code == 404


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_start_video_timing_function(self, test_session, test_video, db_session):
        """Test start_video_timing convenience function"""
        session_id = test_session.id
        video_id = test_video.id
        
        timestamp = start_video_timing(session_id, video_id, db_session)
        
        assert timestamp > 0
        assert isinstance(timestamp, float)
        
        # Verify timing data exists
        service = get_video_timing_service()
        timing_data = service.get_timing_data(session_id)
        assert timing_data is not None
        assert timing_data.start_timestamp == timestamp
    
    def test_get_video_start_time_function(self, test_session, test_video, db_session):
        """Test get_video_start_time convenience function"""
        session_id = test_session.id
        video_id = test_video.id
        
        # Start timing
        original_time = start_video_timing(session_id, video_id, db_session)
        
        # Get start time
        retrieved_time = get_video_start_time(session_id, db_session)
        
        assert retrieved_time == original_time
    
    def test_calculate_latency_function(self, test_session, test_video, db_session):
        """Test calculate_latency convenience function"""
        session_id = test_session.id
        video_id = test_video.id
        
        # Start timing
        start_time = start_video_timing(session_id, video_id, db_session)
        detection_time = start_time + 0.100  # 100ms later
        
        # Calculate latency
        measurement = calculate_latency(session_id, detection_time, db_session)
        
        assert measurement is not None
        assert abs(measurement.latency_ms - 100.0) < 1.0


class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_video_timing_error_handling(self, timing_service):
        """Test VideoTimingError handling"""
        # Test with invalid inputs
        with pytest.raises(VideoTimingError):
            timing_service.start_video_timing("", "", None)  # Empty strings
    
    def test_concurrent_access(self, timing_service, test_session, test_video, db_session):
        """Test thread safety with concurrent access"""
        import threading
        import concurrent.futures
        
        session_id = test_session.id
        video_id = test_video.id
        
        def start_timing():
            return timing_service.start_video_timing(session_id, video_id, db_session)
        
        def get_timing():
            return timing_service.get_video_start_time(session_id, db_session)
        
        # Run concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Start timing in multiple threads
            start_futures = [executor.submit(start_timing) for _ in range(3)]
            get_futures = [executor.submit(get_timing) for _ in range(3)]
            
            # Wait for completion
            start_results = [f.result() for f in start_futures]
            get_results = [f.result() for f in get_futures]
            
            # Verify results are consistent
            assert len(set([r for r in start_results if r is not None])) == 1  # All should return same timestamp
            assert all(r is not None for r in get_results)  # All should succeed


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])