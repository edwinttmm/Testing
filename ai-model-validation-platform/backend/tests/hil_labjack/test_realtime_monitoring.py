"""
HIL LabJack Real-time Monitoring Tests

Tests for real-time voltage monitoring at 10Hz with proper database storage
and detection event handling.
"""

import pytest
import time
import threading
import sqlite3
import json
import os
import statistics
import logging
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from typing import List, Dict, Any

# Import services
import sys
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')
from services.labjack_monitoring_service import LabJackMonitoringService

logger = logging.getLogger(__name__)

class TestRealtimeMonitoring:
    """Test suite for real-time voltage monitoring and storage"""
    
    @pytest.fixture
    def test_database(self):
        """Create test database with detection_events table"""
        db_path = 'test_realtime_monitoring.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create detection_events table matching the schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detection_events (
                id TEXT PRIMARY KEY,
                test_session_id TEXT NOT NULL,
                timestamp REAL,
                confidence REAL,
                class_label TEXT,
                validation_result TEXT,
                created_at TEXT,
                vru_type TEXT,
                processing_time_ms REAL
            )
        """)
        conn.commit()
        conn.close()
        
        yield db_path
        
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)
    
    @pytest.fixture
    def monitoring_service(self, test_database):
        """Create monitoring service with test database"""
        service = LabJackMonitoringService()
        
        # Patch database path to use test database
        with patch('services.labjack_monitoring_service.sqlite3.connect') as mock_connect:
            original_connect = sqlite3.connect
            mock_connect.side_effect = lambda path: original_connect(test_database)
            yield service
        
        # Cleanup
        if service.monitoring_active:
            service.stop_monitoring()
    
    def test_10hz_sampling_rate(self, monitoring_service):
        """Test that monitoring achieves 10Hz sampling rate"""
        session_id = "sampling_rate_test"
        target_rate = 10  # Hz
        test_duration = 1.0  # seconds
        
        sample_timestamps = []
        
        # Mock signal service to capture timing
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            def capture_timing(channel):
                sample_timestamps.append(time.time())
                return {
                    "success": True,
                    "voltage": 2.5,  # Below threshold to avoid events
                    "timestamp": time.time()
                }
            
            mock_signal.read_voltage_signal.side_effect = capture_timing
            
            # Start monitoring at 10Hz
            monitoring_service.start_monitoring(session_id, sample_rate=target_rate)
            
            # Run for test duration
            time.sleep(test_duration)
            
            # Stop monitoring
            monitoring_service.stop_monitoring()
        
        # Analyze sampling rate
        if len(sample_timestamps) >= 2:
            # Calculate intervals between samples
            intervals = [sample_timestamps[i+1] - sample_timestamps[i] 
                        for i in range(len(sample_timestamps)-1)]
            
            avg_interval = statistics.mean(intervals)
            measured_rate = 1.0 / avg_interval if avg_interval > 0 else 0
            
            # Should be close to target rate (within 10% tolerance)
            rate_tolerance = target_rate * 0.1
            assert abs(measured_rate - target_rate) < rate_tolerance, \
                f"Measured rate {measured_rate:.1f}Hz not within tolerance of {target_rate}Hz"
            
            # Check consistency of intervals
            interval_std = statistics.stdev(intervals) if len(intervals) > 1 else 0
            max_jitter = 0.02  # 20ms max jitter
            assert interval_std < max_jitter, \
                f"Sampling jitter {interval_std:.4f}s exceeds maximum {max_jitter}s"
    
    def test_voltage_threshold_detection(self, monitoring_service, test_database):
        """Test voltage threshold detection and event storage"""
        session_id = "threshold_test"
        threshold = 3.0  # V
        
        # Test voltages: mix above and below threshold
        test_voltages = [2.5, 3.5, 1.8, 4.2, 2.0, 3.8, 1.5, 4.5]
        voltage_index = 0
        
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            def provide_voltage(channel):
                nonlocal voltage_index
                if voltage_index < len(test_voltages):
                    voltage = test_voltages[voltage_index]
                    voltage_index += 1
                else:
                    voltage = 2.0  # Default low voltage
                
                return {
                    "success": True,
                    "voltage": voltage,
                    "timestamp": time.time()
                }
            
            mock_signal.read_voltage_signal.side_effect = provide_voltage
            
            # Start monitoring
            monitoring_service.start_monitoring(session_id, sample_rate=20)
            
            # Run until all test voltages are processed
            time.sleep(0.5)
            
            # Stop monitoring
            monitoring_service.stop_monitoring()
        
        # Check database for detection events
        conn = sqlite3.connect(test_database)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT confidence, class_label, validation_result, vru_type
            FROM detection_events 
            WHERE test_session_id = ?
            ORDER BY timestamp
        """, (session_id,))
        
        events = cursor.fetchall()
        conn.close()
        
        # Count expected high voltage events
        expected_high_voltage_count = len([v for v in test_voltages if v > threshold])
        
        # Should have detection events for voltages above threshold
        assert len(events) >= min(expected_high_voltage_count, 1), \
            f"Expected at least 1 detection event, got {len(events)}"
        
        # Verify event data
        for event in events:
            confidence, class_label, validation_result, vru_type = event
            
            # Confidence field stores voltage value
            assert confidence > threshold, f"Stored voltage {confidence} not above threshold"
            
            # Class label should indicate LabJack channel
            assert "LabJack_AIN0" in class_label, f"Invalid class_label: {class_label}"
            
            # Validation result should be "passed" for high voltage
            assert validation_result == "passed", f"Expected 'passed', got '{validation_result}'"
            
            # VRU type should contain voltage info
            assert "LabJack_" in vru_type and "V" in vru_type, f"Invalid vru_type: {vru_type}"
    
    def test_sub_100ms_latency(self, monitoring_service, test_database):
        """Test that detection latency is below 100ms"""
        session_id = "latency_test"
        
        detection_latencies = []
        
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            def timed_voltage_read(channel):
                # Record read start time
                read_start = time.time()
                
                # Simulate processing time
                time.sleep(0.001)  # 1ms processing
                
                # Return high voltage to trigger detection
                return {
                    "success": True,
                    "voltage": 3.5,
                    "timestamp": read_start
                }
            
            mock_signal.read_voltage_signal.side_effect = timed_voltage_read
            
            # Patch database to capture latency
            original_connect = sqlite3.connect
            
            def capture_latency_connect(path):
                conn = original_connect(path)
                original_execute = conn.cursor().execute
                
                def execute_with_timing(*args, **kwargs):
                    if len(args) > 0 and "INSERT INTO detection_events" in args[0]:
                        # Extract processing_time_ms from the query
                        if len(args) > 1 and len(args[1]) > 8:
                            latency_ms = args[1][8]  # processing_time_ms is 9th parameter
                            detection_latencies.append(latency_ms)
                    return original_execute(*args, **kwargs)
                
                conn.cursor().execute = execute_with_timing
                return conn
            
            with patch('services.labjack_monitoring_service.sqlite3.connect', capture_latency_connect):
                # Start monitoring
                monitoring_service.start_monitoring(session_id, sample_rate=10)
                
                # Wait for some detections
                time.sleep(0.5)
                
                # Stop monitoring
                monitoring_service.stop_monitoring()
        
        # Verify latencies
        assert len(detection_latencies) > 0, "No detection latencies captured"
        
        max_latency = 100.0  # 100ms requirement
        for latency in detection_latencies:
            assert latency < max_latency, \
                f"Detection latency {latency}ms exceeds requirement {max_latency}ms"
        
        # Check average latency
        avg_latency = statistics.mean(detection_latencies)
        assert avg_latency < max_latency / 2, \
            f"Average latency {avg_latency}ms should be well below requirement"
    
    def test_continuous_monitoring_stability(self, monitoring_service, test_database):
        """Test monitoring stability over extended period"""
        session_id = "stability_test"
        test_duration = 2.0  # seconds
        
        sample_count = 0
        error_count = 0
        
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            def stable_voltage_read(channel):
                nonlocal sample_count, error_count
                sample_count += 1
                
                # Occasionally simulate read errors
                if sample_count % 50 == 0:  # Error every 50 samples
                    error_count += 1
                    return {"success": False, "error": "Simulated read error"}
                
                # Alternate between high and low voltages
                voltage = 3.5 if sample_count % 10 < 5 else 2.0
                
                return {
                    "success": True,
                    "voltage": voltage,
                    "timestamp": time.time()
                }
            
            mock_signal.read_voltage_signal.side_effect = stable_voltage_read
            
            # Start monitoring
            start_time = time.time()
            monitoring_service.start_monitoring(session_id, sample_rate=20)
            
            # Monitor for extended period
            while time.time() - start_time < test_duration:
                # Check that monitoring is still active
                status = monitoring_service.get_monitoring_status()
                assert status["active"] is True, "Monitoring became inactive during test"
                time.sleep(0.1)
            
            # Stop monitoring
            monitoring_service.stop_monitoring()
        
        # Verify stability
        expected_samples = int(test_duration * 20)  # 20Hz for 2 seconds
        sample_tolerance = expected_samples * 0.2  # 20% tolerance
        
        assert sample_count >= expected_samples - sample_tolerance, \
            f"Sample count {sample_count} below expected {expected_samples}"
        
        # Check error handling
        assert error_count > 0, "No errors were simulated"
        error_rate = error_count / sample_count
        assert error_rate < 0.1, f"Error rate {error_rate:.2%} too high"
        
        # Verify database integrity
        conn = sqlite3.connect(test_database)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM detection_events 
            WHERE test_session_id = ?
        """, (session_id,))
        
        event_count = cursor.fetchone()[0]
        conn.close()
        
        # Should have some detection events (high voltage periods)
        expected_events = sample_count // 20  # Rough estimate
        assert event_count >= expected_events, \
            f"Event count {event_count} lower than expected {expected_events}"
    
    def test_concurrent_session_handling(self, test_database):
        """Test handling of concurrent monitoring session attempts"""
        session1 = "concurrent_test_001"
        session2 = "concurrent_test_002"
        
        service1 = LabJackMonitoringService()
        service2 = LabJackMonitoringService()
        
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            mock_signal.read_voltage_signal.return_value = {
                "success": True,
                "voltage": 3.5,
                "timestamp": time.time()
            }
            
            # Start first session
            result1 = service1.start_monitoring(session1, sample_rate=10)
            assert result1 is True
            
            # Attempt to start second session should fail
            result2 = service2.start_monitoring(session2, sample_rate=10)
            assert result2 is False
            
            # First session should still be active
            status1 = service1.get_monitoring_status()
            assert status1["active"] is True
            assert status1["session_id"] == session1
            
            # Second session should not be active
            status2 = service2.get_monitoring_status()
            assert status2["active"] is False
            
            # Stop first session
            service1.stop_monitoring()
            
            # Now second session should be able to start
            result3 = service2.start_monitoring(session2, sample_rate=10)
            assert result3 is True
            
            # Cleanup
            service2.stop_monitoring()
    
    def test_database_transaction_integrity(self, monitoring_service, test_database):
        """Test database transaction integrity during high-frequency writes"""
        session_id = "transaction_test"
        
        # High-frequency detection events
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            mock_signal.read_voltage_signal.return_value = {
                "success": True,
                "voltage": 3.5,  # Always above threshold
                "timestamp": time.time()
            }
            
            # Start high-rate monitoring
            monitoring_service.start_monitoring(session_id, sample_rate=50)
            
            # Run for short period to generate many events
            time.sleep(0.5)
            
            # Stop monitoring
            monitoring_service.stop_monitoring()
        
        # Verify database integrity
        conn = sqlite3.connect(test_database)
        cursor = conn.cursor()
        
        # Check for data consistency
        cursor.execute("""
            SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
            FROM detection_events 
            WHERE test_session_id = ?
        """, (session_id,))
        
        count, min_timestamp, max_timestamp = cursor.fetchone()
        
        # Should have events
        assert count > 0, "No events were stored"
        
        # Timestamps should be reasonable
        assert min_timestamp is not None and max_timestamp is not None
        assert max_timestamp >= min_timestamp
        
        # Check for duplicate IDs (should be unique)
        cursor.execute("""
            SELECT COUNT(DISTINCT id), COUNT(*)
            FROM detection_events 
            WHERE test_session_id = ?
        """, (session_id,))
        
        unique_count, total_count = cursor.fetchone()
        assert unique_count == total_count, f"Duplicate IDs found: {unique_count} unique vs {total_count} total"
        
        conn.close()
    
    def test_memory_usage_monitoring(self, monitoring_service):
        """Test memory usage during extended monitoring"""
        import psutil
        import os
        
        session_id = "memory_test"
        
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            mock_signal.read_voltage_signal.return_value = {
                "success": True,
                "voltage": 3.5,
                "timestamp": time.time()
            }
            
            # Get initial memory usage
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Start monitoring
            monitoring_service.start_monitoring(session_id, sample_rate=20)
            
            # Monitor memory usage over time
            memory_samples = []
            for _ in range(10):  # 1 second total
                time.sleep(0.1)
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_samples.append(current_memory)
            
            # Stop monitoring
            monitoring_service.stop_monitoring()
            
            # Final memory check
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Check memory growth
        memory_growth = final_memory - initial_memory
        max_memory_growth = 50  # MB
        
        assert memory_growth < max_memory_growth, \
            f"Memory growth {memory_growth:.1f}MB exceeds limit {max_memory_growth}MB"
        
        # Check for memory leaks (steady growth)
        if len(memory_samples) > 5:
            early_avg = statistics.mean(memory_samples[:3])
            late_avg = statistics.mean(memory_samples[-3:])
            memory_trend = late_avg - early_avg
            
            max_trend = 10  # MB
            assert memory_trend < max_trend, \
                f"Memory trend {memory_trend:.1f}MB suggests potential leak"
    
    def test_signal_validation_integration(self, monitoring_service, test_database):
        """Test integration with signal validation service"""
        session_id = "signal_validation_test"
        
        # Test different signal scenarios
        test_scenarios = [
            {"voltage": 3.5, "success": True, "expected_event": True},
            {"voltage": 2.0, "success": True, "expected_event": False},
            {"voltage": 4.2, "success": True, "expected_event": True},
            {"voltage": None, "success": False, "expected_event": False},
        ]
        
        scenario_index = 0
        
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            def scenario_provider(channel):
                nonlocal scenario_index
                if scenario_index < len(test_scenarios):
                    scenario = test_scenarios[scenario_index]
                    scenario_index += 1
                    
                    if scenario["success"]:
                        return {
                            "success": True,
                            "voltage": scenario["voltage"],
                            "timestamp": time.time()
                        }
                    else:
                        return {
                            "success": False,
                            "error": "Simulated read failure"
                        }
                else:
                    # Default to low voltage
                    return {
                        "success": True,
                        "voltage": 2.0,
                        "timestamp": time.time()
                    }
            
            mock_signal.read_voltage_signal.side_effect = scenario_provider
            
            # Start monitoring
            monitoring_service.start_monitoring(session_id, sample_rate=10)
            
            # Wait for scenarios to be processed
            time.sleep(0.5)
            
            # Stop monitoring
            monitoring_service.stop_monitoring()
        
        # Verify database results
        conn = sqlite3.connect(test_database)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT confidence, validation_result
            FROM detection_events 
            WHERE test_session_id = ?
            ORDER BY timestamp
        """, (session_id,))
        
        events = cursor.fetchall()
        conn.close()
        
        # Should have events for high voltage scenarios only
        expected_events = len([s for s in test_scenarios if s["expected_event"]])
        assert len(events) >= min(expected_events, 1), \
            f"Expected {expected_events} events, got {len(events)}"
        
        # Verify event data matches scenarios
        for event in events:
            confidence, validation_result = event
            assert confidence > 3.0, "Event voltage should be above threshold"
            assert validation_result == "passed", "High voltage should result in 'passed'"

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])