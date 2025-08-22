"""
Signal Detection and Timing Validation Tests
Comprehensive testing for signal detection accuracy and timing validation
"""
import pytest
import asyncio
import time
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import numpy as np

from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

# Import test configuration
import sys
sys.path.append('/home/user/Testing/tests/comprehensive-testing-framework/config')
from test_config import test_config, TEST_DATA_PATTERNS

# Import application models and services
sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')
from models import Project, Video, DetectionEvent, TestSession
from services.signal_processing_service import SignalProcessingWorkflow
from database import SessionLocal
from main import app


class TestSignalDetectionTiming:
    """Test suite for signal detection and timing validation"""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self, test_db_session: Session):
        """Set up test environment for each test"""
        self.db = test_db_session
        self.client = TestClient(app)
        self.signal_processor = SignalProcessingWorkflow(db=test_db_session)
        
        # Create test project
        self.test_project = Project(
            name="Signal Detection Test Project",
            description="Test project for signal detection validation",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        self.db.add(self.test_project)
        self.db.commit()
        
        # Create test video
        self.test_video = Video(
            filename="signal_test_video.mp4",
            file_path="/test/path/signal_test_video.mp4",
            file_size=10485760,  # 10MB
            duration=30.0,
            fps=30.0,
            resolution="1920x1080",
            project_id=self.test_project.id
        )
        self.db.add(self.test_video)
        self.db.commit()
    
    def test_gpio_signal_detection_accuracy(self):
        """Test GPIO signal detection with various timing patterns"""
        # Test data: GPIO signals with precise timing
        gpio_signals = [
            {"timestamp": 1.000, "value": 1, "pin": 18},
            {"timestamp": 2.000, "value": 0, "pin": 18},
            {"timestamp": 3.500, "value": 1, "pin": 18},
            {"timestamp": 4.000, "value": 0, "pin": 18},
            {"timestamp": 5.750, "value": 1, "pin": 18}
        ]
        
        # Expected detection events
        expected_events = [
            {"timestamp": 1.000, "event_type": "signal_high"},
            {"timestamp": 2.000, "event_type": "signal_low"},
            {"timestamp": 3.500, "event_type": "signal_high"},
            {"timestamp": 4.000, "event_type": "signal_low"},
            {"timestamp": 5.750, "event_type": "signal_high"}
        ]
        
        # Process signals
        detected_events = self.signal_processor.process_gpio_signals(
            gpio_signals, 
            tolerance_ms=test_config.signal_detection_config["timing_tolerance_ms"]
        )
        
        # Validate detection accuracy
        assert len(detected_events) == len(expected_events)
        
        for detected, expected in zip(detected_events, expected_events):
            timing_diff = abs(detected["timestamp"] - expected["timestamp"])
            assert timing_diff <= 0.1, f"Timing difference too large: {timing_diff}s"
            assert detected["event_type"] == expected["event_type"]
    
    def test_network_packet_signal_detection(self):
        """Test network packet signal detection with jitter and delays"""
        # Simulate network packets with realistic jitter
        network_packets = [
            {"timestamp": 1.000, "packet_type": "detection_trigger", "source": "192.168.1.100"},
            {"timestamp": 2.050, "packet_type": "detection_trigger", "source": "192.168.1.100"},  # 50ms jitter
            {"timestamp": 3.020, "packet_type": "detection_trigger", "source": "192.168.1.100"},  # 20ms jitter
            {"timestamp": 4.080, "packet_type": "detection_trigger", "source": "192.168.1.100"},  # 80ms jitter
        ]
        
        # Process with jitter compensation
        detected_events = self.signal_processor.process_network_packets(
            network_packets,
            jitter_compensation=True,
            max_jitter_ms=100
        )
        
        # Validate jitter compensation
        assert len(detected_events) == 4
        
        # Check that jitter is compensated in timing calculations
        for i, event in enumerate(detected_events):
            expected_base_time = i + 1.0
            compensated_diff = abs(event["compensated_timestamp"] - expected_base_time)
            assert compensated_diff <= 0.05, f"Jitter compensation failed: {compensated_diff}s"
    
    def test_serial_signal_detection_with_noise(self):
        """Test serial signal detection with noise and interference"""
        # Simulate serial data with noise
        serial_data = [
            {"timestamp": 1.000, "data": "DETECT:PERSON:CONF:0.95", "checksum": "VALID"},
            {"timestamp": 1.500, "data": "NOISE:INVALID:DATA", "checksum": "INVALID"},
            {"timestamp": 2.000, "data": "DETECT:VEHICLE:CONF:0.88", "checksum": "VALID"},
            {"timestamp": 2.200, "data": "CORRUPT", "checksum": "INVALID"},
            {"timestamp": 3.000, "data": "DETECT:BICYCLE:CONF:0.75", "checksum": "VALID"},
        ]
        
        # Process with noise filtering
        detected_events = self.signal_processor.process_serial_data(
            serial_data,
            noise_filtering=True,
            min_confidence=0.7
        )
        
        # Validate noise filtering
        valid_detections = [event for event in detected_events if event["valid"]]
        assert len(valid_detections) == 3  # Only valid detections should pass
        
        # Check detection content
        assert valid_detections[0]["class_label"] == "PERSON"
        assert valid_detections[0]["confidence"] == 0.95
        assert valid_detections[1]["class_label"] == "VEHICLE"
        assert valid_detections[2]["class_label"] == "BICYCLE"
    
    @pytest.mark.asyncio
    async def test_real_time_signal_processing(self):
        """Test real-time signal processing with live timing validation"""
        # Create test session
        test_session = TestSession(
            name="Real-time Signal Test",
            project_id=self.test_project.id,
            video_id=self.test_video.id,
            tolerance_ms=50
        )
        self.db.add(test_session)
        self.db.commit()
        
        # Simulate real-time signal stream
        signal_stream = []
        start_time = time.time()
        
        # Generate signals with precise timing
        for i in range(10):
            signal_time = start_time + (i * 0.5)  # 500ms intervals
            signal_stream.append({
                "timestamp": signal_time,
                "type": "GPIO",
                "value": 1 if i % 2 == 0 else 0,
                "pin": 18
            })
        
        # Process signals in real-time simulation
        processed_events = []
        for signal in signal_stream:
            # Simulate processing delay
            await asyncio.sleep(0.01)  # 10ms processing delay
            
            event = await self.signal_processor.process_real_time_signal(
                signal,
                test_session.id
            )
            processed_events.append(event)
        
        # Validate real-time processing
        assert len(processed_events) == 10
        
        # Check timing accuracy
        for i, event in enumerate(processed_events):
            expected_interval = 0.5
            if i > 0:
                actual_interval = event["timestamp"] - processed_events[i-1]["timestamp"]
                interval_error = abs(actual_interval - expected_interval)
                assert interval_error <= 0.05, f"Real-time timing error: {interval_error}s"
    
    def test_signal_synchronization_accuracy(self):
        """Test synchronization between signals and video timestamps"""
        # Create video timestamps (30 FPS = 33.33ms per frame)
        video_timestamps = [i * (1/30) for i in range(300)]  # 10 seconds of video
        
        # Create signal events at specific video times
        signal_events = [
            {"video_timestamp": 1.000, "signal_timestamp": 1.002, "type": "detection"},  # 2ms delay
            {"video_timestamp": 3.500, "signal_timestamp": 3.498, "type": "detection"},  # 2ms early
            {"video_timestamp": 7.250, "signal_timestamp": 7.255, "type": "detection"},  # 5ms delay
        ]
        
        # Synchronize signals with video
        synchronized_events = self.signal_processor.synchronize_with_video(
            signal_events,
            video_timestamps,
            sync_tolerance_ms=10
        )
        
        # Validate synchronization
        for sync_event in synchronized_events:
            sync_error = abs(sync_event["video_timestamp"] - sync_event["signal_timestamp"])
            assert sync_error <= 0.01, f"Synchronization error too large: {sync_error}s"
            
            # Check frame alignment
            expected_frame = int(sync_event["video_timestamp"] * 30)
            actual_frame = sync_event["video_frame"]
            frame_diff = abs(expected_frame - actual_frame)
            assert frame_diff <= 1, f"Frame alignment error: {frame_diff} frames"
    
    def test_timing_validation_edge_cases(self):
        """Test edge cases in timing validation"""
        edge_cases = [
            # Case 1: Zero timestamp
            {"signals": [{"timestamp": 0.0, "type": "GPIO", "value": 1}]},
            
            # Case 2: Negative timestamp (should be rejected)
            {"signals": [{"timestamp": -1.0, "type": "GPIO", "value": 1}]},
            
            # Case 3: Very large timestamp
            {"signals": [{"timestamp": 3600.0, "type": "GPIO", "value": 1}]},
            
            # Case 4: Duplicate timestamps
            {"signals": [
                {"timestamp": 1.0, "type": "GPIO", "value": 1},
                {"timestamp": 1.0, "type": "GPIO", "value": 0}
            ]},
            
            # Case 5: Out-of-order timestamps
            {"signals": [
                {"timestamp": 2.0, "type": "GPIO", "value": 1},
                {"timestamp": 1.0, "type": "GPIO", "value": 0},
                {"timestamp": 3.0, "type": "GPIO", "value": 1}
            ]}
        ]
        
        for case_index, case in enumerate(edge_cases):
            try:
                result = self.signal_processor.validate_timing(case["signals"])
                
                if case_index == 1:  # Negative timestamp case
                    assert not result["valid"], "Negative timestamps should be rejected"
                elif case_index == 3:  # Duplicate timestamps
                    assert "duplicate_warning" in result, "Duplicate timestamps should generate warning"
                elif case_index == 4:  # Out-of-order timestamps
                    assert result["reordered"], "Out-of-order signals should be automatically reordered"
                    
            except Exception as e:
                # Some edge cases should raise exceptions
                if case_index == 1:  # This is expected for negative timestamps
                    assert "Invalid timestamp" in str(e)
                else:
                    pytest.fail(f"Unexpected exception in case {case_index}: {e}")
    
    def test_multi_signal_source_coordination(self):
        """Test coordination between multiple signal sources"""
        # Multiple signal sources with different timing characteristics
        signal_sources = {
            "gpio_primary": [
                {"timestamp": 1.000, "value": 1, "pin": 18},
                {"timestamp": 2.000, "value": 0, "pin": 18},
                {"timestamp": 3.000, "value": 1, "pin": 18}
            ],
            "network_secondary": [
                {"timestamp": 1.050, "packet_type": "confirmation"},  # 50ms after GPIO
                {"timestamp": 2.030, "packet_type": "confirmation"},  # 30ms after GPIO
                {"timestamp": 3.020, "packet_type": "confirmation"}   # 20ms after GPIO
            ],
            "serial_tertiary": [
                {"timestamp": 1.100, "data": "STATUS:CONFIRMED"},     # 100ms after GPIO
                {"timestamp": 2.080, "data": "STATUS:CONFIRMED"},     # 80ms after GPIO
                {"timestamp": 3.090, "data": "STATUS:CONFIRMED"}      # 90ms after GPIO
            ]
        }
        
        # Coordinate signals with primary source as reference
        coordinated_events = self.signal_processor.coordinate_multi_source(
            signal_sources,
            primary_source="gpio_primary",
            max_coordination_delay_ms=150
        )
        
        # Validate coordination
        assert len(coordinated_events) == 3  # Three primary events
        
        for event in coordinated_events:
            # Each event should have confirmations from secondary sources
            assert "confirmations" in event
            assert len(event["confirmations"]) >= 2  # Network + Serial confirmations
            
            # Check coordination timing
            for confirmation in event["confirmations"]:
                delay = confirmation["timestamp"] - event["primary_timestamp"]
                assert 0 <= delay <= 0.15, f"Coordination delay out of range: {delay}s"
    
    def test_signal_quality_metrics(self):
        """Test signal quality assessment and metrics"""
        # Test signals with varying quality characteristics
        test_signals = [
            # High quality signals
            {"timestamp": 1.000, "amplitude": 5.0, "noise_level": 0.1, "source": "high_quality"},
            {"timestamp": 2.000, "amplitude": 4.8, "noise_level": 0.2, "source": "high_quality"},
            
            # Medium quality signals
            {"timestamp": 3.000, "amplitude": 3.5, "noise_level": 0.8, "source": "medium_quality"},
            {"timestamp": 4.000, "amplitude": 3.2, "noise_level": 1.0, "source": "medium_quality"},
            
            # Low quality signals
            {"timestamp": 5.000, "amplitude": 2.1, "noise_level": 1.5, "source": "low_quality"},
            {"timestamp": 6.000, "amplitude": 1.8, "noise_level": 2.0, "source": "low_quality"},
        ]
        
        # Assess signal quality
        quality_metrics = self.signal_processor.assess_signal_quality(test_signals)
        
        # Validate quality assessment
        assert "overall_quality" in quality_metrics
        assert "signal_to_noise_ratio" in quality_metrics
        assert "reliability_score" in quality_metrics
        
        # Check quality categorization
        high_quality_signals = [s for s in quality_metrics["categorized_signals"] 
                               if s["quality_level"] == "high"]
        assert len(high_quality_signals) == 2
        
        # Validate SNR calculations
        for signal_metric in quality_metrics["individual_metrics"]:
            snr = signal_metric["signal_to_noise_ratio"]
            if signal_metric["source"] == "high_quality":
                assert snr > 20, f"High quality signal should have SNR > 20dB, got {snr}"
            elif signal_metric["source"] == "low_quality":
                assert snr < 5, f"Low quality signal should have SNR < 5dB, got {snr}"


class TestSignalPerformanceBenchmarks:
    """Performance benchmarks for signal processing"""
    
    def test_signal_processing_performance(self):
        """Test signal processing performance under various loads"""
        # Generate large signal dataset
        large_signal_set = []
        for i in range(10000):  # 10,000 signals
            large_signal_set.append({
                "timestamp": i * 0.001,  # 1ms intervals
                "type": "GPIO",
                "value": 1 if i % 2 == 0 else 0,
                "pin": 18
            })
        
        # Measure processing time
        start_time = time.time()
        processed_signals = self.signal_processor.batch_process_signals(large_signal_set)
        processing_time = time.time() - start_time
        
        # Performance assertions
        assert processing_time < 5.0, f"Batch processing too slow: {processing_time}s"
        assert len(processed_signals) == len(large_signal_set)
        
        # Calculate throughput
        throughput = len(large_signal_set) / processing_time
        assert throughput > 2000, f"Processing throughput too low: {throughput} signals/sec"
    
    @pytest.mark.asyncio
    async def test_concurrent_signal_processing(self):
        """Test concurrent signal processing capabilities"""
        # Create multiple concurrent signal streams
        concurrent_streams = []
        for stream_id in range(5):
            stream_signals = []
            for i in range(1000):
                stream_signals.append({
                    "timestamp": i * 0.01,
                    "stream_id": stream_id,
                    "type": "Network",
                    "data": f"stream_{stream_id}_signal_{i}"
                })
            concurrent_streams.append(stream_signals)
        
        # Process streams concurrently
        start_time = time.time()
        tasks = [
            self.signal_processor.process_signal_stream_async(stream)
            for stream in concurrent_streams
        ]
        results = await asyncio.gather(*tasks)
        concurrent_time = time.time() - start_time
        
        # Validate concurrent processing
        assert len(results) == 5
        assert all(len(result) == 1000 for result in results)
        
        # Concurrent processing should be faster than sequential
        assert concurrent_time < 3.0, f"Concurrent processing too slow: {concurrent_time}s"


@pytest.fixture
def signal_processor():
    """Fixture providing signal processor instance"""
    return SignalProcessingWorkflow(db=SessionLocal())


@pytest.fixture
def test_db_session():
    """Fixture providing test database session"""
    session = SessionLocal()
    yield session
    session.close()


# Test utility functions
def generate_test_signals(signal_type: str, count: int, interval_ms: float) -> List[Dict[str, Any]]:
    """Generate test signals for various test scenarios"""
    signals = []
    for i in range(count):
        timestamp = i * (interval_ms / 1000.0)
        
        if signal_type == "GPIO":
            signals.append({
                "timestamp": timestamp,
                "type": "GPIO",
                "value": 1 if i % 2 == 0 else 0,
                "pin": 18
            })
        elif signal_type == "Network":
            signals.append({
                "timestamp": timestamp,
                "type": "Network",
                "packet_type": "detection_trigger",
                "source": "192.168.1.100"
            })
        elif signal_type == "Serial":
            signals.append({
                "timestamp": timestamp,
                "type": "Serial",
                "data": f"DETECT:OBJECT_{i}:CONF:0.{85 + (i % 15)}",
                "checksum": "VALID"
            })
    
    return signals


def validate_timing_accuracy(detected_events: List[Dict], expected_events: List[Dict], 
                           tolerance_ms: float = 100) -> bool:
    """Validate timing accuracy between detected and expected events"""
    if len(detected_events) != len(expected_events):
        return False
    
    for detected, expected in zip(detected_events, expected_events):
        timing_diff = abs(detected["timestamp"] - expected["timestamp"])
        if timing_diff > (tolerance_ms / 1000.0):
            return False
    
    return True