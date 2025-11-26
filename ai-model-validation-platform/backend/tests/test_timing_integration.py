"""
Test suite for T0-T1 timing integration in HIL validation platform.

This module tests the complete Phase 1 integration:
- T0 command timestamp capture
- T1 video start timing measurement  
- T1-T0 presentation delay calculation
- Database storage of timing data
"""

import pytest
import time
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock

from services.timing_orchestration_service import (
    TimingOrchestrationService, 
    T0TimingCapture, 
    T1TimingCapture,
    T1MinusT0Measurement
)
from services.labjack_timing_service import PrecisionTimingService
from services.video_timing_service import VideoTimingService
from models import TestSession
from database import get_db


class TestTimingOrchestrationService:
    """Test timing orchestration service T0-T1 integration"""
    
    @pytest.fixture
    def timing_service(self):
        """Create timing orchestration service for testing"""
        precision_service = Mock(spec=PrecisionTimingService)
        precision_service.get_monotonic_timestamp_ns.return_value = 123456789000000
        precision_service.get_timing_accuracy_ns.return_value = 500000  # 0.5ms precision
        
        video_service = Mock(spec=VideoTimingService)
        video_service.start_video_timing.return_value = time.time()
        video_service.get_timing_data.return_value = Mock(
            start_timestamp_ns=123456790000000,
            precision_ns=800000
        )
        
        return TimingOrchestrationService(
            precision_service=precision_service,
            video_timing_service=video_service
        )
    
    def test_t0_capture_precision(self, timing_service):
        """Test T0 command timestamp capture with nanosecond precision"""
        session_id = "test_session_123"
        
        # Capture T0 timestamp
        t0_capture = timing_service.capture_t0_command_timestamp(session_id)
        
        # Verify T0 capture structure
        assert isinstance(t0_capture, T0TimingCapture)
        assert t0_capture.session_id == session_id
        assert t0_capture.command_timestamp > 0
        assert t0_capture.command_timestamp_ns > 0
        assert t0_capture.precision_ns == 500000  # 0.5ms from mock
        assert t0_capture.capture_latency_ns >= 0
        assert t0_capture.hardware_sync_enabled is False  # No LabJack in test
        
        # Verify T0 is stored in service
        retrieved_t0 = timing_service.get_t0_capture(session_id)
        assert retrieved_t0 == t0_capture
    
    def test_t1_capture_integration(self, timing_service):
        """Test T1 video start timestamp capture"""
        session_id = "test_session_456"
        video_id = "test_video_789"
        
        # First capture T0
        t0_capture = timing_service.capture_t0_command_timestamp(session_id)
        
        # Add small delay to simulate real T1-T0 gap
        time.sleep(0.001)  # 1ms delay
        
        # Capture T1 timestamp
        video_metadata = {"fps": 30, "duration": 60.0}
        t1_capture = timing_service.capture_t1_video_start_timestamp(
            session_id, video_id, video_metadata=video_metadata
        )
        
        # Verify T1 capture structure
        assert isinstance(t1_capture, T1TimingCapture)
        assert t1_capture.session_id == session_id
        assert t1_capture.video_id == video_id
        assert t1_capture.video_start_timestamp > t0_capture.command_timestamp
        assert t1_capture.precision_ns == 800000  # From mock
        assert t1_capture.capture_source == "video_timing_service"
        
        # Verify T1 is stored in service
        retrieved_t1 = timing_service.get_t1_capture(session_id)
        assert retrieved_t1 == t1_capture
    
    def test_presentation_delay_calculation(self, timing_service):
        """Test T1-T0 presentation delay calculation"""
        session_id = "test_session_delay"
        video_id = "test_video_delay"
        
        # Capture T0
        t0_capture = timing_service.capture_t0_command_timestamp(session_id)
        t0_time = t0_capture.command_timestamp
        
        # Simulate presentation delay
        time.sleep(0.002)  # 2ms delay
        
        # Capture T1
        t1_capture = timing_service.capture_t1_video_start_timestamp(session_id, video_id)
        
        # Get presentation delay measurement
        delay_measurement = timing_service.get_timing_measurement(session_id)
        
        # Verify delay measurement
        assert isinstance(delay_measurement, T1MinusT0Measurement)
        assert delay_measurement.session_id == session_id
        assert delay_measurement.t0_timestamp == t0_time
        assert delay_measurement.t1_timestamp == t1_capture.video_start_timestamp
        assert delay_measurement.presentation_delay_ms >= 1.0  # At least 1ms delay
        assert delay_measurement.presentation_delay_ns >= 1000000  # At least 1ms in ns
        assert delay_measurement.timing_quality in ["high", "medium", "low"]
        assert delay_measurement.measurement_accuracy_ns > 0
    
    def test_timing_quality_assessment(self, timing_service):
        """Test timing quality assessment based on precision"""
        session_id = "test_quality"
        
        # Mock high precision timing
        timing_service._precision_service.get_timing_accuracy_ns.return_value = 50000  # 0.05ms
        timing_service._video_timing_service.get_timing_data.return_value.precision_ns = 80000  # 0.08ms
        
        # Capture timing
        timing_service.capture_t0_command_timestamp(session_id)
        timing_service.capture_t1_video_start_timestamp(session_id, "video_1")
        
        delay_measurement = timing_service.get_timing_measurement(session_id)
        assert delay_measurement.timing_quality == "high"  # Both < 0.1ms
        
        # Test medium precision
        timing_service._precision_service.get_timing_accuracy_ns.return_value = 800000  # 0.8ms
        session_id_2 = "test_quality_2"
        timing_service.capture_t0_command_timestamp(session_id_2)
        timing_service.capture_t1_video_start_timestamp(session_id_2, "video_2")
        
        delay_measurement_2 = timing_service.get_timing_measurement(session_id_2)
        assert delay_measurement_2.timing_quality == "medium"  # 0.8ms < 1ms
    
    def test_service_statistics(self, timing_service):
        """Test timing service statistics collection"""
        # Perform several timing operations
        for i in range(3):
            session_id = f"stats_session_{i}"
            timing_service.capture_t0_command_timestamp(session_id)
            timing_service.capture_t1_video_start_timestamp(session_id, f"video_{i}")
        
        stats = timing_service.get_timing_statistics()
        
        assert stats["total_timing_captures"] == 3
        assert stats["active_sessions"] == 3
        assert stats["completed_measurements"] == 3
        assert stats["services"]["precision_timing"] is True
        assert stats["services"]["video_timing"] is True
        assert stats["services"]["labjack_hardware"] is False
    
    def test_session_cleanup(self, timing_service):
        """Test session timing data cleanup"""
        session_id = "cleanup_session"
        
        # Create timing data
        timing_service.capture_t0_command_timestamp(session_id)
        timing_service.capture_t1_video_start_timestamp(session_id, "cleanup_video")
        
        # Verify data exists
        assert timing_service.get_t0_capture(session_id) is not None
        assert timing_service.get_t1_capture(session_id) is not None
        assert timing_service.get_timing_measurement(session_id) is not None
        
        # Clear session data
        result = timing_service.clear_session_timing(session_id)
        assert result is True
        
        # Verify data is cleared
        assert timing_service.get_t0_capture(session_id) is None
        assert timing_service.get_t1_capture(session_id) is None
        assert timing_service.get_timing_measurement(session_id) is None


class TestHILAPITimingIntegration:
    """Test HIL API endpoints with T0-T1 timing integration"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        db = Mock()
        test_session = Mock(spec=TestSession)
        test_session.id = "api_test_session"
        test_session.project_id = "test_project"
        test_session.status = "running"
        
        db.query.return_value.filter.return_value.first.return_value = test_session
        return db, test_session
    
    @patch('api.hil_test_complete.timing_orchestration_service')
    @patch('api.hil_test_complete.labjack_service')
    async def test_start_session_t0_capture(self, mock_labjack, mock_timing_service, mock_db_session):
        """Test that starting HIL session captures T0 timestamp"""
        from api.hil_test_complete import start_hil_test_session
        from schemas import TestSessionCreate
        
        db, test_session = mock_db_session
        
        # Mock LabJack as connected
        mock_labjack.get_connection_status.return_value = AsyncMock(connected=True)
        
        # Mock T0 capture
        mock_t0_capture = Mock(spec=T0TimingCapture)
        mock_t0_capture.command_timestamp = time.time()
        mock_t0_capture.precision_ns = 100000
        mock_timing_service.capture_t0_command_timestamp.return_value = mock_t0_capture
        
        # Create test session request
        session_request = TestSessionCreate(
            project_id="test_project",
            max_latency_ms=100
        )
        
        # Call API endpoint
        with patch('api.hil_test_complete.create_test_session', return_value=test_session):
            result = await start_hil_test_session(session_request, db)
        
        # Verify T0 capture was called
        mock_timing_service.capture_t0_command_timestamp.assert_called_once()
        
        # Verify T0 data storage was called
        mock_timing_service._store_t0_timing_data.assert_called_once()
        
        assert result == test_session
    
    @patch('api.hil_test_complete.timing_orchestration_service')
    async def test_video_start_t1_capture(self, mock_timing_service):
        """Test video start endpoint captures T1 timestamp"""
        from api.hil_test_complete import start_video_playback
        
        # Mock active session
        session_id = 123
        with patch('api.hil_test_complete.hil_manager') as mock_manager:
            mock_manager.active_sessions = {session_id: {"status": "running"}}
            
            # Mock T1 capture
            mock_t1_capture = Mock(spec=T1TimingCapture)
            mock_t1_capture.video_start_timestamp = time.time()
            mock_t1_capture.precision_ns = 200000
            mock_timing_service.capture_t1_video_start_timestamp.return_value = mock_t1_capture
            
            # Mock delay measurement
            mock_delay = Mock(spec=T1MinusT0Measurement)
            mock_delay.presentation_delay_ms = 15.5
            mock_delay.timing_quality = "high"
            mock_timing_service.get_timing_measurement.return_value = mock_delay
            
            video_data = {
                "video_id": "test_video",
                "fps": 30,
                "duration_s": 60.0
            }
            
            # Call API endpoint
            result = await start_video_playback(session_id, video_data, db=Mock())
        
        # Verify T1 capture was called
        mock_timing_service.capture_t1_video_start_timestamp.assert_called_once_with(
            session_id=str(session_id),
            video_id="test_video",
            db=Mock(),
            video_metadata={"fps": 30, "duration": 60.0, "resolution": None, "filename": None}
        )
        
        # Verify response includes timing data
        assert result["success"] is True
        assert "t1_timestamp" in result
        assert "timing_precision_ns" in result
        assert "presentation_delay_ms" in result


class TestDatabaseTimingStorage:
    """Test database storage of T0-T1 timing data"""
    
    def test_t0_database_fields(self):
        """Test T0 timing data is stored in correct database fields"""
        from models import TestSession
        
        # Verify new T0 fields exist in model
        assert hasattr(TestSession, 'command_start_timestamp')
        assert hasattr(TestSession, 'command_start_timestamp_ns')
        assert hasattr(TestSession, 'presentation_delay_ms')
        assert hasattr(TestSession, 'presentation_delay_ns')
        assert hasattr(TestSession, 'presentation_delay_quality')
    
    @patch('services.timing_orchestration_service.TestSession')
    def test_timing_data_storage(self, mock_test_session):
        """Test timing data is correctly stored in database"""
        from services.timing_orchestration_service import TimingOrchestrationService
        
        # Create service and mock database
        service = TimingOrchestrationService()
        mock_db = Mock()
        mock_session = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        
        # Test T0 storage
        t0_capture = Mock(spec=T0TimingCapture)
        t0_capture.command_timestamp = 1234567890.123456
        t0_capture.command_timestamp_ns = 1234567890123456789
        t0_capture.precision_ns = 100000
        
        service._store_t0_timing_data("test_session", t0_capture, mock_db)
        
        # Verify database fields are set
        assert mock_session.command_start_timestamp == t0_capture.command_timestamp
        assert mock_session.command_start_timestamp_ns == str(t0_capture.command_timestamp_ns)
        assert mock_session.precision_timing_enabled is True
        assert mock_session.timing_accuracy_ns == float(t0_capture.precision_ns)
        
        mock_db.commit.assert_called_once()


if __name__ == "__main__":
    # Run specific tests
    pytest.main([__file__, "-v"])