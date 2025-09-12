"""
Unit Tests for LatencyValidationService

Tests the core functionality of LabJack timing-based validation including:
- Detection validation based on latency thresholds
- Session metrics calculation and statistics
- Real-time detection event processing
- Database integration and storage
- Batch validation processing
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any, List

# Import the service under test
from services.latency_validation_service import (
    LatencyValidationService, 
    LatencyMetrics, 
    DetectionValidationResult,
    latency_validation_service
)


class TestLatencyValidationService:
    """Test suite for LatencyValidationService"""
    
    def setup_method(self):
        """Setup test environment"""
        self.service = LatencyValidationService()
        self.mock_session_id = "test-session-123"
        self.mock_video_start_time = 1693492800.0  # Unix timestamp
        self.mock_threshold_ms = 50
    
    def test_validate_detection_pass(self):
        """Test detection validation that passes threshold"""
        labjack_timestamp = self.mock_video_start_time + 0.030  # 30ms later
        
        result = self.service.validate_detection(
            labjack_timestamp, 
            self.mock_video_start_time, 
            self.mock_threshold_ms
        )
        
        assert result == "Pass"
    
    def test_validate_detection_fail(self):
        """Test detection validation that fails threshold"""
        labjack_timestamp = self.mock_video_start_time + 0.080  # 80ms later
        
        result = self.service.validate_detection(
            labjack_timestamp, 
            self.mock_video_start_time, 
            self.mock_threshold_ms
        )
        
        assert result == "Fail"
    
    def test_validate_detection_exact_threshold(self):
        """Test detection validation exactly at threshold"""
        labjack_timestamp = self.mock_video_start_time + (self.mock_threshold_ms / 1000)  # Exactly at threshold
        
        result = self.service.validate_detection(
            labjack_timestamp, 
            self.mock_video_start_time, 
            self.mock_threshold_ms
        )
        
        assert result == "Pass"  # Should pass when equal to threshold
    
    def test_calculate_latency_ms(self):
        """Test latency calculation"""
        labjack_timestamp = self.mock_video_start_time + 0.035  # 35ms later
        
        latency = self.service.calculate_latency_ms(labjack_timestamp, self.mock_video_start_time)
        
        assert latency == 35.0
    
    def test_calculate_latency_ms_negative(self):
        """Test latency calculation with negative result (LabJack before video)"""
        labjack_timestamp = self.mock_video_start_time - 0.010  # 10ms before
        
        latency = self.service.calculate_latency_ms(labjack_timestamp, self.mock_video_start_time)
        
        assert latency == -10.0
    
    def test_process_detection_event_success(self):
        """Test processing a detection event successfully"""
        labjack_data = {
            "detection_id": "det-001",
            "hardware_timestamp": self.mock_video_start_time + 0.025,  # 25ms
            "threshold_ms": 50,
            "pin_state": True,
            "signal_value": 3.2
        }
        
        video_timing = {
            "start_time": self.mock_video_start_time,
            "frame_rate": 30.0
        }
        
        with patch.object(self.service, '_store_detection_event') as mock_store:
            result = self.service.process_detection_event(
                self.mock_session_id, 
                labjack_data, 
                video_timing
            )
        
        assert isinstance(result, DetectionValidationResult)
        assert result.detection_id == "det-001"
        assert result.latency_ms == 25.0
        assert result.validation_result == "Pass"
        assert result.threshold_ms == 50
        assert mock_store.called
    
    def test_process_detection_event_with_error(self):
        """Test processing detection event with malformed data"""
        labjack_data = {}  # Missing required fields
        video_timing = {}
        
        result = self.service.process_detection_event(
            self.mock_session_id, 
            labjack_data, 
            video_timing
        )
        
        assert isinstance(result, DetectionValidationResult)
        assert result.validation_result == "Fail"
        assert result.latency_ms == float('inf')
    
    @patch('services.latency_validation_service.SessionLocal')
    def test_calculate_session_metrics_success(self, mock_session_local):
        """Test successful session metrics calculation"""
        # Mock database session and query results
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        # Create mock detection events
        mock_events = []
        latencies = [15.0, 25.0, 35.0, 45.0, 65.0]  # Mix of pass/fail at 50ms threshold
        
        for i, latency in enumerate(latencies):
            mock_event = Mock()
            mock_event.latency_ms = latency
            mock_event.validation_result = "Pass" if latency <= 50 else "Fail"
            mock_event.threshold_ms = 50
            mock_events.append(mock_event)
        
        mock_db.query().filter().all.return_value = mock_events
        
        with patch.object(self.service, '_store_session_metrics') as mock_store:
            metrics = self.service.calculate_session_metrics(self.mock_session_id)
        
        assert isinstance(metrics, LatencyMetrics)
        assert metrics.total_detections == 5
        assert metrics.pass_count == 4  # 4 detections <= 50ms
        assert metrics.fail_count == 1   # 1 detection > 50ms
        assert metrics.pass_rate == 80.0  # 4/5 * 100
        assert metrics.average_latency_ms == 37.0  # Mean of latencies
        assert metrics.min_latency_ms == 15.0
        assert metrics.max_latency_ms == 65.0
        assert metrics.threshold_ms == 50
        assert mock_store.called
    
    @patch('services.latency_validation_service.SessionLocal')
    def test_calculate_session_metrics_no_events(self, mock_session_local):
        """Test session metrics calculation with no events"""
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        mock_db.query().filter().all.return_value = []
        
        metrics = self.service.calculate_session_metrics(self.mock_session_id)
        
        assert metrics is None
    
    def test_validate_batch_detections(self):
        """Test batch validation of multiple detections"""
        detection_batch = [
            {"detection_id": "det-001", "hardware_timestamp": self.mock_video_start_time + 0.020},  # 20ms - Pass
            {"detection_id": "det-002", "hardware_timestamp": self.mock_video_start_time + 0.080},  # 80ms - Fail
            {"detection_id": "det-003", "hardware_timestamp": self.mock_video_start_time + 0.040},  # 40ms - Pass
        ]
        
        results = self.service.validate_batch_detections(
            detection_batch, 
            self.mock_video_start_time, 
            self.mock_threshold_ms
        )
        
        assert len(results) == 3
        assert results[0].validation_result == "Pass"
        assert results[0].latency_ms == 20.0
        assert results[1].validation_result == "Fail"
        assert results[1].latency_ms == 80.0
        assert results[2].validation_result == "Pass"
        assert results[2].latency_ms == 40.0
    
    def test_validate_batch_detections_with_errors(self):
        """Test batch validation with some malformed entries"""
        detection_batch = [
            {"detection_id": "det-001", "hardware_timestamp": self.mock_video_start_time + 0.020},  # Valid
            {"detection_id": "det-002"},  # Missing timestamp
            {"hardware_timestamp": self.mock_video_start_time + 0.030},  # Missing ID
        ]
        
        results = self.service.validate_batch_detections(
            detection_batch, 
            self.mock_video_start_time, 
            self.mock_threshold_ms
        )
        
        assert len(results) == 3
        assert results[0].validation_result == "Pass"
        assert results[1].validation_result == "Fail"  # Error case
        assert results[2].validation_result == "Pass"   # Should still work with missing ID
    
    def test_create_latency_histogram(self):
        """Test creation of latency distribution histogram"""
        latencies = [5.0, 15.0, 25.0, 35.0, 45.0, 75.0, 150.0, 250.0]
        
        histogram = self.service._create_latency_histogram(latencies, 50)
        
        assert isinstance(histogram, dict)
        assert "0-10ms" in histogram
        assert "11-25ms" in histogram
        assert "26-50ms" in histogram
        assert "51-100ms" in histogram
        assert "101-200ms" in histogram
        assert "200ms+" in histogram
        
        # Check counts
        assert histogram["0-10ms"] == 1   # 5.0
        assert histogram["11-25ms"] == 2  # 15.0, 25.0
        assert histogram["26-50ms"] == 2  # 35.0, 45.0
        assert histogram["51-100ms"] == 1 # 75.0
        assert histogram["101-200ms"] == 1 # 150.0
        assert histogram["200ms+"] == 1   # 250.0
    
    def test_create_latency_histogram_empty(self):
        """Test histogram creation with empty latency list"""
        histogram = self.service._create_latency_histogram([], 50)
        assert histogram == {}
    
    @patch('services.latency_validation_service.SessionLocal')
    def test_get_session_summary_success(self, mock_session_local):
        """Test getting session summary successfully"""
        # Mock the calculate_session_metrics method
        mock_metrics = LatencyMetrics(
            total_detections=10,
            pass_count=8,
            fail_count=2,
            pass_rate=80.0,
            average_latency_ms=32.5,
            min_latency_ms=10.0,
            max_latency_ms=75.0,
            median_latency_ms=30.0,
            std_dev_latency_ms=15.2,
            latency_histogram={"0-10ms": 1, "11-25ms": 3, "26-50ms": 4, "51-100ms": 2},
            threshold_ms=50
        )
        
        with patch.object(self.service, 'calculate_session_metrics', return_value=mock_metrics):
            summary = self.service.get_session_summary(self.mock_session_id)
        
        assert summary is not None
        assert summary["session_id"] == self.mock_session_id
        assert summary["validation_type"] == "latency_based"
        assert summary["total_detections"] == 10
        assert summary["pass_count"] == 8
        assert summary["fail_count"] == 2
        assert summary["pass_rate"] == 80.0
        assert summary["status"] == "Pass"  # 80% pass rate >= 80% threshold
        
        latency_stats = summary["latency_stats"]
        assert latency_stats["average_ms"] == 32.5
        assert latency_stats["min_ms"] == 10.0
        assert latency_stats["max_ms"] == 75.0
        assert latency_stats["median_ms"] == 30.0
        assert latency_stats["threshold_ms"] == 50
    
    @patch('services.latency_validation_service.SessionLocal')
    def test_get_session_summary_low_pass_rate(self, mock_session_local):
        """Test session summary with low pass rate (should fail)"""
        mock_metrics = LatencyMetrics(
            total_detections=10,
            pass_count=5,  # Only 50% pass rate
            fail_count=5,
            pass_rate=50.0,
            average_latency_ms=65.0,
            min_latency_ms=20.0,
            max_latency_ms=120.0,
            median_latency_ms=60.0,
            std_dev_latency_ms=25.0,
            latency_histogram={},
            threshold_ms=50
        )
        
        with patch.object(self.service, 'calculate_session_metrics', return_value=mock_metrics):
            summary = self.service.get_session_summary(self.mock_session_id)
        
        assert summary["status"] == "Fail"  # 50% pass rate < 80% threshold
    
    def test_get_session_summary_no_metrics(self):
        """Test session summary when no metrics available"""
        with patch.object(self.service, 'calculate_session_metrics', return_value=None):
            summary = self.service.get_session_summary(self.mock_session_id)
        
        assert summary is None


class TestLatencyValidationServiceIntegration:
    """Integration tests for LatencyValidationService with database"""
    
    def setup_method(self):
        """Setup integration test environment"""
        self.service = LatencyValidationService()
    
    @pytest.mark.asyncio
    async def test_end_to_end_validation_workflow(self):
        """Test complete end-to-end validation workflow"""
        session_id = "integration-test-session"
        video_start_time = 1693492800.0
        threshold_ms = 50
        
        # Simulate multiple detection events
        detection_events = [
            {
                "detection_id": f"det-{i:03d}",
                "hardware_timestamp": video_start_time + (i * 0.01) + (0.02 if i % 3 == 0 else 0.08),
                "threshold_ms": threshold_ms,
                "pin_state": True
            }
            for i in range(5)
        ]
        
        video_timing = {
            "start_time": video_start_time,
            "frame_rate": 30.0
        }
        
        # Process each detection event
        validation_results = []
        with patch.object(self.service, '_store_detection_event'):
            for event_data in detection_events:
                result = self.service.process_detection_event(
                    session_id, 
                    event_data, 
                    video_timing
                )
                validation_results.append(result)
        
        # Verify results
        assert len(validation_results) == 5
        for i, result in enumerate(validation_results):
            assert isinstance(result, DetectionValidationResult)
            assert result.detection_id == f"det-{i:03d}"
            assert result.threshold_ms == threshold_ms
            
            # Verify Pass/Fail based on timing pattern
            expected_latency = (i * 10) + (20 if i % 3 == 0 else 80)
            assert abs(result.latency_ms - expected_latency) < 1.0  # Allow small floating point errors
            
            if expected_latency <= threshold_ms:
                assert result.validation_result == "Pass"
            else:
                assert result.validation_result == "Fail"


class TestGlobalServiceInstance:
    """Test the global service instance"""
    
    def test_global_service_exists(self):
        """Test that global service instance exists and is correct type"""
        assert latency_validation_service is not None
        assert isinstance(latency_validation_service, LatencyValidationService)
    
    def test_global_service_functionality(self):
        """Test basic functionality through global instance"""
        result = latency_validation_service.validate_detection(
            1693492800.030,  # 30ms after start
            1693492800.0,    # Start time
            50               # 50ms threshold
        )
        
        assert result == "Pass"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])