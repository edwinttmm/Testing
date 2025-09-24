"""
Comprehensive test suite for LabJack T7 Manager
Tests all functionality including hardware integration, timing precision, and error handling
"""

import pytest
import time
import threading
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from labjack_t7_manager import LabJackT7Manager, LabJackConfig, TimingEvent

class TestLabJackT7Manager:
    """Test suite for LabJack T7 Manager"""
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return LabJackConfig(
            device_type="T7",
            connection_type="USB",
            identifier="ANY",
            analog_input_range=10.0,
            stream_scan_rate=1000,
            gpio_directions={0: "output", 1: "output", 2: "input", 3: "input"}
        )
    
    @pytest.fixture
    def manager(self, config):
        """Test manager instance"""
        return LabJackT7Manager(config)
    
    def test_config_initialization(self, config):
        """Test configuration initialization"""
        assert config.device_type == "T7"
        assert config.connection_type == "USB"
        assert config.identifier == "ANY"
        assert config.analog_input_range == 10.0
        assert config.stream_scan_rate == 1000
        assert len(config.gpio_directions) == 4
        assert config.gpio_directions[0] == "output"
        assert config.gpio_directions[2] == "input"
    
    def test_manager_initialization(self, manager):
        """Test manager initialization"""
        assert manager.config is not None
        assert not manager.connected
        assert manager.handle is None
        assert not manager.streaming
        assert manager.auto_reconnect
        assert manager.max_reconnect_attempts == 5
        assert len(manager.performance_metrics) > 0
        assert manager.performance_metrics["error_count"] == 0
    
    def test_connection_mock_mode(self, manager):
        """Test connection in mock mode"""
        # Should work even without hardware
        result = manager.connect()
        assert result is True
        assert manager.connected
        assert "mock" in manager.device_info or manager.device_info.get("device_type") == "T7-MOCK"
    
    def test_disconnect(self, manager):
        """Test disconnection"""
        manager.connect()
        assert manager.connected
        
        manager.disconnect()
        assert not manager.connected
        assert manager.device_info == {}
        assert not manager.streaming
    
    def test_context_manager(self, manager):
        """Test context manager functionality"""
        with manager as mgr:
            assert mgr.connected
        assert not manager.connected
    
    def test_analog_read_single_sample(self, manager):
        """Test single analog sample reading"""
        manager.connect()
        
        result = manager.read_analog_precise([0, 1, 2, 3])
        
        assert "values" in result
        assert "channels" in result
        assert "timestamp" in result
        assert "read_time_us" in result
        assert "samples" in result
        
        assert result["channels"] == [0, 1, 2, 3]
        assert len(result["values"]) == 1
        assert len(result["values"][0]) == 4
        assert result["samples"] == 1
        assert result["read_time_us"] > 0
    
    def test_analog_read_multiple_samples(self, manager):
        """Test multiple analog samples reading"""
        manager.connect()
        
        result = manager.read_analog_precise([0, 1], num_samples=5)
        
        assert len(result["values"]) == 5
        assert all(len(sample) == 2 for sample in result["values"])
        assert result["samples"] == 5
    
    def test_analog_read_without_connection(self, manager):
        """Test analog read without connection raises error"""
        with pytest.raises(RuntimeError, match="Device not connected"):
            manager.read_analog_precise([0])
    
    def test_camera_trigger_timing(self, manager):
        """Test camera trigger with timing measurement"""
        manager.connect()
        
        pulse_width = 100  # microseconds
        start_time = time.perf_counter()
        
        result = manager.trigger_camera_capture(pulse_width)
        
        end_time = time.perf_counter()
        elapsed_us = (end_time - start_time) * 1e6
        
        assert result is True
        assert len(manager.timing_events) > 0
        
        last_event = manager.timing_events[-1]
        assert last_event.event_type == "camera_trigger"
        assert last_event.channel == 0
        assert last_event.value == 1.0
        
        # Timing should be reasonably close to pulse width
        assert elapsed_us >= pulse_width  # At least the pulse width
        assert elapsed_us < pulse_width * 10  # But not too much overhead
    
    def test_camera_trigger_without_connection(self, manager):
        """Test camera trigger without connection raises error"""
        with pytest.raises(RuntimeError, match="Device not connected"):
            manager.trigger_camera_capture()
    
    def test_vru_detection_timeout(self, manager):
        """Test VRU detection with timeout"""
        manager.connect()
        
        start_time = time.perf_counter()
        result = manager.wait_for_vru_detection(timeout_ms=100)
        end_time = time.perf_counter()
        
        elapsed_ms = (end_time - start_time) * 1000
        
        assert result is not None
        assert "detected" in result
        assert "detection_time_us" in result
        assert "signal_strength" in result
        assert "timestamp" in result
        
        # Should timeout around 100ms (allow some variance)
        if not result["detected"]:
            assert 90 <= elapsed_ms <= 150
    
    def test_vru_detection_without_connection(self, manager):
        """Test VRU detection without connection raises error"""
        with pytest.raises(RuntimeError, match="Device not connected"):
            manager.wait_for_vru_detection()
    
    def test_streaming_start_stop(self, manager):
        """Test data streaming start and stop"""
        manager.connect()
        
        # Start streaming
        channels = ["AIN0", "AIN1", "AIN2"]
        result = manager.start_streaming(channels, scan_rate=500)
        
        assert result is True
        assert manager.streaming
        
        # Stop streaming
        manager.stop_streaming()
        assert not manager.streaming
    
    def test_streaming_without_connection(self, manager):
        """Test streaming without connection raises error"""
        with pytest.raises(RuntimeError, match="Device not connected"):
            manager.start_streaming(["AIN0"])
    
    def test_performance_metrics(self, manager):
        """Test performance metrics collection"""
        manager.connect()
        
        # Perform some operations
        manager.read_analog_precise([0, 1])
        manager.trigger_camera_capture(50)
        
        metrics = manager.get_performance_metrics()
        
        assert "connection_time" in metrics
        assert "read_latency_us" in metrics
        assert "write_latency_us" in metrics
        assert "timing_jitter_us" in metrics
        assert "error_count" in metrics
        assert "reconnection_count" in metrics
        assert "device_info" in metrics
        assert "connected" in metrics
        assert "streaming" in metrics
        
        # Should have recorded some latencies
        assert len(metrics["read_latency_us"]) > 0
        assert len(metrics["write_latency_us"]) > 0
        
        # Should have calculated statistics
        if metrics["read_latency_us"]:
            assert "avg_read_latency_us" in metrics
            assert "max_read_latency_us" in metrics
            assert "std_read_latency_us" in metrics
    
    def test_timing_events_recording(self, manager):
        """Test timing events are recorded correctly"""
        manager.connect()
        
        initial_count = len(manager.timing_events)
        
        # Trigger some events
        manager.trigger_camera_capture(100)
        manager.trigger_camera_capture(200)
        
        assert len(manager.timing_events) == initial_count + 2
        
        # Check event details
        for event in manager.timing_events[-2:]:
            assert isinstance(event, TimingEvent)
            assert event.event_type == "camera_trigger"
            assert event.channel == 0
            assert event.value == 1.0
            assert event.precision_us > 0
            assert isinstance(event.timestamp, datetime)
    
    def test_timing_events_limit(self, manager):
        """Test timing events list is limited to prevent memory issues"""
        manager.connect()
        
        # Generate more than 1000 events
        for _ in range(1100):
            manager.timing_events.append(TimingEvent(
                timestamp=datetime.now(),
                event_type="test",
                channel=0,
                value=1.0,
                precision_us=100.0
            ))
        
        # Trigger an event to activate the limit
        manager.trigger_camera_capture(50)
        
        # Should be limited to 1000 events
        assert len(manager.timing_events) <= 1000
    
    def test_diagnostic_full_suite(self, manager):
        """Test comprehensive diagnostic suite"""
        result = manager.run_diagnostic()
        
        assert "timestamp" in result
        assert "tests" in result
        assert "overall_status" in result
        assert "issues" in result
        
        # Should have multiple test results
        assert len(result["tests"]) >= 4
        assert "connection" in result["tests"]
        assert "analog_read" in result["tests"]
        assert "gpio_trigger" in result["tests"]
        assert "timing_precision" in result["tests"]
        
        # Status should be PASS or FAIL
        assert result["overall_status"] in ["PASS", "FAIL"]
        
        # Issues should be a list
        assert isinstance(result["issues"], list)
    
    def test_error_handling_and_recovery(self, manager):
        """Test error handling and auto-reconnection"""
        manager.connect()
        initial_error_count = manager.performance_metrics["error_count"]
        
        # Simulate connection loss
        manager.handle = None
        manager.connected = False
        
        # This should increment error count
        try:
            manager.read_analog_precise([0])
            assert False, "Should have raised RuntimeError"
        except RuntimeError:
            pass
        
        # Error count should have increased
        assert manager.performance_metrics["error_count"] > initial_error_count
    
    def test_concurrent_operations(self, manager):
        """Test thread safety with concurrent operations"""
        manager.connect()
        results = []
        errors = []
        
        def worker():
            try:
                for _ in range(10):
                    result = manager.read_analog_precise([0])
                    results.append(result)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Run multiple threads
        threads = []
        for _ in range(3):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have results without errors
        assert len(results) > 0
        assert len(errors) == 0
    
    def test_timing_precision_measurement(self, manager):
        """Test timing precision and jitter measurement"""
        manager.connect()
        
        latencies = []
        num_measurements = 50
        
        for _ in range(num_measurements):
            start = time.perf_counter()
            manager.read_analog_precise([0])
            latency = (time.perf_counter() - start) * 1e6
            latencies.append(latency)
        
        # Calculate statistics
        avg_latency = np.mean(latencies)
        max_latency = np.max(latencies)
        std_latency = np.std(latencies)
        
        # Reasonable performance expectations
        assert avg_latency < 10000  # Less than 10ms average
        assert max_latency < 50000  # Less than 50ms max
        assert std_latency < avg_latency  # Reasonable jitter
        
        print(f"Timing Analysis:")
        print(f"  Average latency: {avg_latency:.1f}µs")
        print(f"  Maximum latency: {max_latency:.1f}µs")
        print(f"  Standard deviation: {std_latency:.1f}µs")
        print(f"  Jitter (CV): {std_latency/avg_latency*100:.1f}%")
    
    def test_memory_usage_monitoring(self, manager):
        """Test memory usage doesn't grow excessively"""
        manager.connect()
        
        initial_metrics_len = len(manager.performance_metrics["read_latency_us"])
        
        # Generate many readings
        for _ in range(1500):
            manager.read_analog_precise([0])
        
        # Should be limited to 1000 measurements
        final_metrics_len = len(manager.performance_metrics["read_latency_us"])
        assert final_metrics_len <= 1000
        assert final_metrics_len > initial_metrics_len
    
    @pytest.mark.integration
    def test_adas_hil_integration_scenario(self, manager):
        """Test complete ADAS HIL integration scenario"""
        manager.connect()
        
        # Scenario: VRU detection test
        scenario_results = {
            "camera_triggers": [],
            "vru_detections": [],
            "timing_precision": [],
            "errors": []
        }
        
        try:
            # Step 1: Initialize monitoring
            analog_baseline = manager.read_analog_precise([0, 1, 2, 3])
            scenario_results["baseline"] = analog_baseline
            
            # Step 2: Trigger camera capture
            trigger_start = time.perf_counter()
            trigger_result = manager.trigger_camera_capture(100)
            trigger_time = (time.perf_counter() - trigger_start) * 1e6
            
            scenario_results["camera_triggers"].append({
                "success": trigger_result,
                "timing_us": trigger_time
            })
            
            # Step 3: Wait for VRU detection signal
            vru_result = manager.wait_for_vru_detection(timeout_ms=1000)
            scenario_results["vru_detections"].append(vru_result)
            
            # Step 4: Read analog signals during detection
            detection_signals = manager.read_analog_precise([0, 1, 2, 3], num_samples=5)
            scenario_results["detection_signals"] = detection_signals
            
            # Step 5: Validate timing precision
            timing_events = manager.timing_events[-5:] if manager.timing_events else []
            for event in timing_events:
                scenario_results["timing_precision"].append({
                    "event_type": event.event_type,
                    "precision_us": event.precision_us,
                    "timestamp": event.timestamp.isoformat()
                })
            
        except Exception as e:
            scenario_results["errors"].append(str(e))
        
        # Validate scenario results
        assert len(scenario_results["errors"]) == 0
        assert len(scenario_results["camera_triggers"]) > 0
        assert scenario_results["camera_triggers"][0]["success"] is True
        assert scenario_results["camera_triggers"][0]["timing_us"] < 1000  # Less than 1ms
        
        if scenario_results["vru_detections"]:
            vru_detection = scenario_results["vru_detections"][0]
            assert "detected" in vru_detection
            assert "detection_time_us" in vru_detection
        
        print("ADAS HIL Integration Scenario Results:")
        print(f"  Camera triggers: {len(scenario_results['camera_triggers'])}")
        print(f"  VRU detections: {len(scenario_results['vru_detections'])}")
        print(f"  Timing events: {len(scenario_results['timing_precision'])}")
        print(f"  Errors: {len(scenario_results['errors'])}")

if __name__ == "__main__":
    # Run basic tests
    pytest.main([__file__, "-v"])