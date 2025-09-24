"""
Test Fixtures and Utilities for HIL Video Duration Testing

This module provides comprehensive test fixtures, mock objects, and utilities
for testing the HIL video duration auto-stop system across various scenarios.

Fixtures include:
- Mock video objects with various duration configurations
- Mock database sessions with different query responses
- HIL test session mock objects
- Timing service mock implementations
- Realistic test data for various video types and edge cases
"""

from typing import Dict, Any, Optional, List, Tuple
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
from datetime import datetime, timezone
import time
import random


@dataclass
class VideoTestFixture:
    """Test fixture for video objects with various configurations"""
    video_id: str
    filename: str
    duration: Optional[float] = None
    fps: Optional[float] = 30.0
    resolution: Optional[str] = "1920x1080"
    file_size: Optional[int] = None
    status: str = "validated"
    
    def to_video_data_payload(self, include_duration_s: bool = True, include_duration: bool = True) -> Dict[str, Any]:
        """Convert to video_data payload format used by HIL API"""
        payload = {
            "video_id": self.video_id,
            "filename": self.filename,
            "fps": self.fps,
            "resolution": self.resolution,
            "status": self.status
        }
        
        if self.duration is not None:
            if include_duration_s:
                payload["duration_s"] = self.duration
            elif include_duration:
                payload["duration"] = self.duration
        
        if self.file_size is not None:
            payload["file_size"] = self.file_size
        
        return payload
    
    def to_database_video_mock(self):
        """Convert to mock database Video object"""
        mock_video = Mock()
        mock_video.id = self.video_id
        mock_video.filename = self.filename
        mock_video.duration = self.duration
        mock_video.fps = self.fps
        mock_video.resolution = self.resolution
        mock_video.file_size = self.file_size
        mock_video.status = self.status
        return mock_video


class VideoFixtureFactory:
    """Factory for creating video test fixtures with various characteristics"""
    
    @staticmethod
    def create_short_videos() -> List[VideoTestFixture]:
        """Create fixtures for short duration videos (< 5 seconds)"""
        return [
            VideoTestFixture("short_001", "quick_test.mp4", 0.5, 30.0, "1920x1080"),
            VideoTestFixture("short_002", "flash_scene.mp4", 1.0, 60.0, "1280x720"),
            VideoTestFixture("short_003", "micro_test.mp4", 2.5, 25.0, "640x480"),
            VideoTestFixture("short_004", "brief_clip.mp4", 4.8, 30.0, "1920x1080"),
        ]
    
    @staticmethod
    def create_medium_videos() -> List[VideoTestFixture]:
        """Create fixtures for medium duration videos (5-60 seconds)"""
        return [
            VideoTestFixture("medium_001", "standard_test.mp4", 10.0, 30.0, "1920x1080"),
            VideoTestFixture("medium_002", "pedestrian_crossing.mp4", 15.5, 30.0, "1920x1080"),
            VideoTestFixture("medium_003", "vehicle_detection.mp4", 30.0, 30.0, "1920x1080"),
            VideoTestFixture("medium_004", "traffic_scenario.mp4", 45.0, 60.0, "3840x2160"),
            VideoTestFixture("medium_005", "complex_scene.mp4", 58.2, 25.0, "1920x1080"),
        ]
    
    @staticmethod
    def create_long_videos() -> List[VideoTestFixture]:
        """Create fixtures for long duration videos (> 60 seconds)"""
        return [
            VideoTestFixture("long_001", "highway_drive.mp4", 120.0, 30.0, "1920x1080"),
            VideoTestFixture("long_002", "extended_test.mp4", 180.0, 30.0, "1920x1080"),
            VideoTestFixture("long_003", "marathon_scenario.mp4", 300.0, 30.0, "1920x1080"),
            VideoTestFixture("long_004", "endurance_test.mp4", 600.0, 60.0, "3840x2160"),
        ]
    
    @staticmethod
    def create_edge_case_videos() -> List[VideoTestFixture]:
        """Create fixtures for edge cases and boundary conditions"""
        return [
            VideoTestFixture("edge_001", "minimum_duration.mp4", 0.1, 30.0, "1920x1080"),  # Minimum valid
            VideoTestFixture("edge_002", "maximum_duration.mp4", 7200.0, 30.0, "1920x1080"),  # Maximum valid (2 hours)
            VideoTestFixture("edge_003", "fractional_duration.mp4", 12.345, 29.97, "1920x1080"),  # Fractional
            VideoTestFixture("edge_004", "high_fps.mp4", 10.0, 120.0, "1920x1080"),  # High FPS
            VideoTestFixture("edge_005", "low_fps.mp4", 30.0, 15.0, "1920x1080"),  # Low FPS
        ]
    
    @staticmethod
    def create_invalid_videos() -> List[VideoTestFixture]:
        """Create fixtures with invalid duration values"""
        return [
            VideoTestFixture("invalid_001", "negative_duration.mp4", -5.0, 30.0, "1920x1080"),
            VideoTestFixture("invalid_002", "zero_duration.mp4", 0.0, 30.0, "1920x1080"),
            VideoTestFixture("invalid_003", "too_short.mp4", 0.01, 30.0, "1920x1080"),  # Below minimum
            VideoTestFixture("invalid_004", "too_long.mp4", 10000.0, 30.0, "1920x1080"),  # Above maximum
        ]
    
    @staticmethod
    def create_missing_duration_videos() -> List[VideoTestFixture]:
        """Create fixtures with missing/None duration values"""
        return [
            VideoTestFixture("missing_001", "no_duration.mp4", None, 30.0, "1920x1080"),
            VideoTestFixture("missing_002", "unknown_length.mp4", None, 60.0, "3840x2160"),
        ]
    
    @staticmethod
    def get_all_fixtures() -> Dict[str, List[VideoTestFixture]]:
        """Get all fixture categories"""
        return {
            "short": VideoFixtureFactory.create_short_videos(),
            "medium": VideoFixtureFactory.create_medium_videos(), 
            "long": VideoFixtureFactory.create_long_videos(),
            "edge_case": VideoFixtureFactory.create_edge_case_videos(),
            "invalid": VideoFixtureFactory.create_invalid_videos(),
            "missing_duration": VideoFixtureFactory.create_missing_duration_videos()
        }


class GracePeriodCalculator:
    """Utility for calculating grace periods and auto-stop times"""
    
    @staticmethod
    def calculate_grace_period(duration: float) -> float:
        """Calculate grace period: 5% of duration, min 0.25s, max 2.0s"""
        grace = duration * 0.05
        return max(0.25, min(2.0, grace))
    
    @staticmethod
    def calculate_auto_stop_time(duration: float) -> float:
        """Calculate LabJack auto-stop time: duration + grace_period"""
        grace_period = GracePeriodCalculator.calculate_grace_period(duration)
        return duration + grace_period
    
    @staticmethod
    def get_grace_period_test_cases() -> List[Tuple[float, float, float]]:
        """Get test cases for grace period validation: (duration, expected_grace, expected_stop_time)"""
        return [
            (0.5, 0.25, 0.75),      # Very short: min grace
            (1.0, 0.25, 1.25),      # Short: min grace
            (5.0, 0.25, 5.25),      # Medium: min grace
            (10.0, 0.5, 10.5),      # Medium: 5% grace
            (20.0, 1.0, 21.0),      # Medium: 5% grace
            (30.0, 1.5, 31.5),      # Medium: 5% grace
            (40.0, 2.0, 42.0),      # Long: max grace
            (60.0, 2.0, 62.0),      # Long: max grace
            (120.0, 2.0, 122.0),    # Long: max grace
            (300.0, 2.0, 302.0),    # Very long: max grace
        ]


class MockDatabaseFactory:
    """Factory for creating mock database sessions with various behaviors"""
    
    @staticmethod
    def create_successful_db_mock(video_fixture: VideoTestFixture) -> Mock:
        """Create mock database that successfully returns video"""
        mock_db = Mock()
        mock_query = Mock()
        mock_filter = Mock()
        
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = video_fixture.to_database_video_mock()
        mock_db.query.return_value = mock_query
        
        return mock_db
    
    @staticmethod
    def create_video_not_found_db_mock() -> Mock:
        """Create mock database that returns None (video not found)"""
        mock_db = Mock()
        mock_query = Mock()
        mock_filter = Mock()
        
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_db.query.return_value = mock_query
        
        return mock_db
    
    @staticmethod
    def create_database_error_mock(error_type: Exception = Exception) -> Mock:
        """Create mock database that raises an exception"""
        mock_db = Mock()
        mock_db.query.side_effect = error_type("Database connection failed")
        
        return mock_db


class HILTestSessionMockFactory:
    """Factory for creating HIL test session mocks"""
    
    @staticmethod
    def create_active_session_mock(session_id: int, video_fixture: VideoTestFixture) -> Dict[str, Any]:
        """Create mock active HIL test session"""
        return {
            "session_id": session_id,
            "start_time": datetime.now(timezone.utc),
            "current_video_id": video_fixture.video_id,
            "current_video_index": 0,
            "expected_events": [],
            "detection_events": [],
            "status": "running",
            "video_duration": video_fixture.duration,
            "grace_period": GracePeriodCalculator.calculate_grace_period(video_fixture.duration) if video_fixture.duration else None,
            "auto_stop_time": GracePeriodCalculator.calculate_auto_stop_time(video_fixture.duration) if video_fixture.duration else None
        }
    
    @staticmethod
    def create_completed_session_mock(session_id: int, total_events: int = 10) -> Dict[str, Any]:
        """Create mock completed HIL test session"""
        return {
            "session_id": session_id,
            "status": "completed",
            "total_events": total_events,
            "passed_events": random.randint(0, total_events),
            "failed_events": random.randint(0, total_events//2),
            "average_latency_ms": random.uniform(30.0, 120.0),
            "completion_time": datetime.now(timezone.utc)
        }


class TimingServiceMockFactory:
    """Factory for creating timing service mocks"""
    
    @staticmethod
    def create_precision_timing_mock() -> Mock:
        """Create mock precision timing service"""
        mock_service = Mock()
        
        # Mock timing accuracy
        mock_service.get_timing_accuracy_ns.return_value = 1000  # 1μs accuracy
        
        # Mock timestamp generation
        mock_service.get_monotonic_timestamp_ns.return_value = time.time_ns()
        
        # Mock sync point creation
        mock_sync_point = Mock()
        mock_sync_point.utc_timestamp = datetime.now(timezone.utc)
        mock_sync_point.monotonic_ns = time.time_ns()
        mock_service.create_sync_point.return_value = mock_sync_point
        
        return mock_service
    
    @staticmethod
    def create_video_timing_mock() -> Mock:
        """Create mock video timing service"""
        mock_service = Mock()
        
        # Mock timing data storage
        mock_service._timing_cache = {}
        
        # Mock start video timing
        def mock_start_timing(session_id, video_id, db=None, video_metadata=None):
            start_time = time.time()
            mock_service._timing_cache[session_id] = {
                "video_id": video_id,
                "start_timestamp": start_time,
                "video_metadata": video_metadata
            }
            return start_time
        
        mock_service.start_video_timing.side_effect = mock_start_timing
        
        # Mock get start time
        def mock_get_start_time(session_id, db=None):
            return mock_service._timing_cache.get(session_id, {}).get("start_timestamp")
        
        mock_service.get_video_start_time.side_effect = mock_get_start_time
        
        return mock_service


class LabJackServiceMockFactory:
    """Factory for creating LabJack service mocks"""
    
    @staticmethod
    def create_connected_labjack_mock() -> Mock:
        """Create mock LabJack service in connected state"""
        mock_service = Mock()
        
        # Mock connection status
        mock_status = Mock()
        mock_status.connected = True
        mock_status.device_type = "T7"
        mock_status.device_serial = "MOCK_12345"
        mock_status.last_check = datetime.now(timezone.utc)
        mock_status.error_message = None
        
        mock_service.get_connection_status.return_value = mock_status
        
        # Mock monitoring methods
        mock_service.start_monitoring.return_value = True
        mock_service.stop_monitoring.return_value = True
        mock_service.is_monitoring = False
        
        return mock_service
    
    @staticmethod
    def create_disconnected_labjack_mock() -> Mock:
        """Create mock LabJack service in disconnected state"""
        mock_service = Mock()
        
        # Mock connection status
        mock_status = Mock()
        mock_status.connected = False
        mock_status.device_type = None
        mock_status.device_serial = None
        mock_status.last_check = datetime.now(timezone.utc)
        mock_status.error_message = "Device not found"
        
        mock_service.get_connection_status.return_value = mock_status
        
        # Mock monitoring methods (should fail when disconnected)
        mock_service.start_monitoring.return_value = False
        mock_service.stop_monitoring.return_value = False
        mock_service.is_monitoring = False
        
        return mock_service


class TestScenarioBuilder:
    """Builder for creating comprehensive test scenarios"""
    
    @staticmethod
    def build_duration_resolution_scenarios() -> List[Dict[str, Any]]:
        """Build scenarios for testing duration resolution from various sources"""
        scenarios = []
        
        # Scenario 1: Duration from video_data["duration_s"]
        video_fixture = VideoFixtureFactory.create_medium_videos()[0]
        scenarios.append({
            "name": "Duration from payload duration_s",
            "video_fixture": video_fixture,
            "video_data": video_fixture.to_video_data_payload(include_duration_s=True, include_duration=False),
            "db_mock": MockDatabaseFactory.create_video_not_found_db_mock(),  # Should not be called
            "expected_duration": video_fixture.duration,
            "expected_db_called": False
        })
        
        # Scenario 2: Duration from video_data["duration"] (fallback)
        scenarios.append({
            "name": "Duration from payload duration fallback",
            "video_fixture": video_fixture,
            "video_data": video_fixture.to_video_data_payload(include_duration_s=False, include_duration=True),
            "db_mock": MockDatabaseFactory.create_video_not_found_db_mock(),  # Should not be called
            "expected_duration": video_fixture.duration,
            "expected_db_called": False
        })
        
        # Scenario 3: Duration from database (payload missing)
        scenarios.append({
            "name": "Duration from database fallback",
            "video_fixture": video_fixture,
            "video_data": {"video_id": video_fixture.video_id, "filename": video_fixture.filename},  # No duration
            "db_mock": MockDatabaseFactory.create_successful_db_mock(video_fixture),
            "expected_duration": video_fixture.duration,
            "expected_db_called": True
        })
        
        # Scenario 4: No duration available
        missing_duration_fixture = VideoFixtureFactory.create_missing_duration_videos()[0]
        scenarios.append({
            "name": "No duration available",
            "video_fixture": missing_duration_fixture,
            "video_data": {"video_id": missing_duration_fixture.video_id, "filename": missing_duration_fixture.filename},
            "db_mock": MockDatabaseFactory.create_successful_db_mock(missing_duration_fixture),
            "expected_duration": None,
            "expected_db_called": True
        })
        
        return scenarios
    
    @staticmethod
    def build_grace_period_scenarios() -> List[Dict[str, Any]]:
        """Build scenarios for testing grace period calculations"""
        scenarios = []
        
        for duration, expected_grace, expected_stop_time in GracePeriodCalculator.get_grace_period_test_cases():
            scenarios.append({
                "duration": duration,
                "expected_grace_period": expected_grace,
                "expected_auto_stop_time": expected_stop_time,
                "scenario_type": "normal" if 5.0 <= duration <= 60.0 else ("short" if duration < 5.0 else "long")
            })
        
        return scenarios
    
    @staticmethod
    def build_integration_scenarios() -> List[Dict[str, Any]]:
        """Build scenarios for integration testing"""
        scenarios = []
        
        # Get various video fixtures
        all_fixtures = VideoFixtureFactory.get_all_fixtures()
        
        for category, fixtures in all_fixtures.items():
            for fixture in fixtures[:2]:  # Limit to 2 per category for manageable test suite
                scenarios.append({
                    "name": f"Integration test - {category} video",
                    "video_fixture": fixture,
                    "session_mock": HILTestSessionMockFactory.create_active_session_mock(1, fixture),
                    "labjack_mock": LabJackServiceMockFactory.create_connected_labjack_mock(),
                    "timing_mock": TimingServiceMockFactory.create_video_timing_mock(),
                    "category": category
                })
        
        return scenarios


# Export key classes and functions
__all__ = [
    'VideoTestFixture',
    'VideoFixtureFactory',
    'GracePeriodCalculator', 
    'MockDatabaseFactory',
    'HILTestSessionMockFactory',
    'TimingServiceMockFactory',
    'LabJackServiceMockFactory',
    'TestScenarioBuilder'
]