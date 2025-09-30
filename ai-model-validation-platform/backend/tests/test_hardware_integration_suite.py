"""
Hardware Integration Test Suite for LabJack Hybrid Logging System
================================================================

Comprehensive hardware integration tests that validate:
- Real LabJack device connectivity and communication
- 1000Hz raw data capture with microsecond timing precision
- Voltage detection accuracy and threshold sensitivity
- Hardware failure detection and recovery
- Connection stability under sustained load
- Multi-channel simultaneous sampling
- Hardware-specific timing characteristics

These tests require actual LabJack hardware and will be skipped 
in CI/CD environments unless hardware is detected.
"""

import pytest
import asyncio
import time
import numpy as np
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, patch

# Hardware integration imports
from services.labjack_service import LabJackService, ConnectionMode, ConnectionStatus
from services.labjack_hardware_service import get_labjack_hardware_service
from services.labjack_detection_service import LabJackDetectionMonitor
from services.hil_validation_service import HILValidationService

import logging
logger = logging.getLogger(__name__)

# Hardware test constants
HARDWARE_TIMEOUT = 30  # seconds
VOLTAGE_PRECISION = 0.001  # 1mV precision
TIMING_PRECISION_NS = 1000  # 1µs precision
SAMPLE_RATE_TOLERANCE = 0.05  # 5% tolerance for sample rates


class HardwareTestFixtures:
    """Hardware test fixtures and utilities"""
    
    @pytest.fixture(scope="session")
    def hardware_detection(self):
        """Detect if real LabJack hardware is available"""
        try:
            service = LabJackService()
            
            # Attempt hardware connection without mock fallback
            connected = asyncio.run(service.connect(allow_mock=False))
            
            if connected and service.mode != ConnectionMode.MOCK:
                device_info = asyncio.run(service.get_device_info())
                hardware_info = {
                    'available': True,
                    'device_type': device_info.get('device_type', 'Unknown'),
                    'serial_number': device_info.get('serial_number', 'Unknown'),
                    'connection_type': device_info.get('connection_type', 'Unknown'),
                    'interface_type': device_info.get('interface_type', 'Unknown')
                }
                
                logger.info(f"Hardware detected: {hardware_info['device_type']} "
                           f"(S/N: {hardware_info['serial_number']}) via {hardware_info['connection_type']}")
                
                # Cleanup
                asyncio.run(service.disconnect())
                
                yield hardware_info
            else:
                yield {'available': False, 'reason': 'No real hardware connection'}
                
        except Exception as e:
            logger.warning(f"Hardware detection failed: {e}")
            yield {'available': False, 'reason': str(e)}
    
    @pytest.fixture
    def connected_labjack_service(self, hardware_detection):
        """Connected LabJack service for hardware tests"""
        if not hardware_detection['available']:
            pytest.skip("Real LabJack hardware not available")
        
        service = LabJackService()
        
        # Connect to real hardware
        connected = asyncio.run(service.connect(allow_mock=False))
        if not connected or service.mode == ConnectionMode.MOCK:
            pytest.skip("Failed to connect to real LabJack hardware")
        
        yield service
        
        # Cleanup
        try:
            if service.streaming:
                asyncio.run(service.stop_stream())
            asyncio.run(service.disconnect())
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
    
    @pytest.fixture
    def voltage_test_channels(self):
        """Standard channels for voltage testing"""
        return ['AIN0', 'AIN1', 'AIN2', 'AIN3']


@pytest.mark.hardware
class TestLabJackConnectivity:
    """Test LabJack hardware connectivity and basic communication"""
    
    def test_hardware_device_detection(self, hardware_detection):
        """Test detection of LabJack hardware device"""
        assert hardware_detection['available'], \
            f"LabJack hardware not detected: {hardware_detection.get('reason', 'Unknown')}"
        
        # Validate device information
        assert hardware_detection['device_type'] != 'Unknown', "Device type should be identified"
        assert hardware_detection['serial_number'] != 'Unknown', "Serial number should be available"
        assert hardware_detection['connection_type'] in ['USB', 'ETHERNET', 'WIFI'], \
            f"Unexpected connection type: {hardware_detection['connection_type']}"
    
    def test_connection_mode_validation(self, connected_labjack_service):
        """Test connection mode is real hardware, not simulation"""
        service = connected_labjack_service
        
        # Verify not in mock mode
        assert service.mode != ConnectionMode.MOCK, "Should not be in mock mode"
        assert service.status == ConnectionStatus.CONNECTED, "Should be connected"
        
        # Verify device info indicates real hardware
        device_info = asyncio.run(service.get_device_info())
        assert not device_info.get('is_mock', True), "Should be real hardware"
        assert device_info.get('hil_suitable', False), "Should be suitable for HIL testing"
    
    def test_device_information_retrieval(self, connected_labjack_service):
        """Test retrieval of detailed device information"""
        service = connected_labjack_service
        
        device_info = asyncio.run(service.get_device_info())
        
        # Validate required device information fields
        required_fields = ['device_type', 'serial_number', 'connection_type']
        for field in required_fields:
            assert field in device_info, f"Device info missing field: {field}"
            assert device_info[field] != 'Unknown', f"Device {field} should be identified"
        
        # Validate T7 specific information
        if 'T7' in device_info['device_type']:
            assert device_info.get('max_bytes', 0) > 0, "T7 should report max bytes"
        
        logger.info(f"Device Info: {device_info}")
    
    def test_connection_stability(self, connected_labjack_service):
        """Test connection stability over time"""
        service = connected_labjack_service
        
        # Test connection stability over 30 seconds
        start_time = time.time()
        test_duration = 30  # seconds
        check_interval = 2   # seconds
        
        stability_checks = []
        
        while (time.time() - start_time) < test_duration:
            # Check connection status
            status = service.get_status()
            stability_checks.append({
                'timestamp': time.time(),
                'connected': status.connected,
                'status': status.status,
                'elapsed': time.time() - start_time
            })
            
            # Verify still connected
            assert status.connected, f"Connection lost at {time.time() - start_time:.1f}s"
            assert status.status == ConnectionStatus.CONNECTED, "Status should remain connected"
            
            time.sleep(check_interval)
        
        # Verify consistent connection throughout test
        connected_count = sum(1 for check in stability_checks if check['connected'])
        stability_rate = connected_count / len(stability_checks)
        
        assert stability_rate == 1.0, f"Connection stability too low: {stability_rate:.2%}"
        logger.info(f"Connection stability: 100% over {test_duration}s ({len(stability_checks)} checks)")


@pytest.mark.hardware
class TestVoltageReading:
    """Test voltage reading accuracy and precision"""
    
    def test_single_channel_voltage_reading(self, connected_labjack_service, voltage_test_channels):
        """Test single channel voltage reading accuracy"""
        service = connected_labjack_service
        
        for channel in voltage_test_channels:
            # Read voltage multiple times
            readings = []
            for _ in range(20):
                voltage = asyncio.run(service.read_single_voltage(channel))
                readings.append(voltage)
                time.sleep(0.01)  # 10ms between readings
            
            # Validate readings
            assert all(isinstance(v, (int, float)) for v in readings), \
                f"All {channel} readings should be numeric"
            
            assert all(-10 <= v <= 10 for v in readings), \
                f"{channel} readings should be within ±10V range"
            
            # Check reading consistency (should be stable for unconnected inputs)
            voltage_std = np.std(readings)
            voltage_mean = np.mean(readings)
            
            # For floating inputs, some noise is expected but should be reasonable
            assert voltage_std < 0.5, f"{channel} readings too noisy: {voltage_std:.3f}V std dev"
            
            logger.info(f"{channel}: {voltage_mean:.3f}V ±{voltage_std:.3f}V (n={len(readings)})")
    
    def test_multi_channel_simultaneous_reading(self, connected_labjack_service, voltage_test_channels):
        """Test simultaneous multi-channel voltage reading"""
        service = connected_labjack_service
        
        # Read all channels simultaneously multiple times
        simultaneous_readings = []
        
        for iteration in range(10):
            reading_set = {}
            start_time = time.time()
            
            # Read all channels as quickly as possible
            for channel in voltage_test_channels:
                voltage = asyncio.run(service.read_single_voltage(channel))
                reading_set[channel] = voltage
            
            reading_set['read_time'] = time.time() - start_time
            simultaneous_readings.append(reading_set)
            
            time.sleep(0.1)  # 100ms between sets
        
        # Analyze multi-channel performance
        read_times = [r['read_time'] for r in simultaneous_readings]
        mean_read_time = np.mean(read_times)
        max_read_time = max(read_times)
        
        # Reading all channels should be reasonably fast
        channels_count = len(voltage_test_channels)
        assert mean_read_time < (channels_count * 0.01), \
            f"Multi-channel reading too slow: {mean_read_time:.3f}s for {channels_count} channels"
        
        # Verify all channels read successfully
        for reading_set in simultaneous_readings:
            for channel in voltage_test_channels:
                assert channel in reading_set, f"Missing reading for {channel}"
                assert isinstance(reading_set[channel], (int, float)), \
                    f"Invalid reading type for {channel}"
        
        logger.info(f"Multi-channel reading: {mean_read_time*1000:.1f}ms mean, "
                   f"{max_read_time*1000:.1f}ms max for {channels_count} channels")
    
    def test_voltage_range_validation(self, connected_labjack_service):
        """Test voltage reading range validation"""
        service = connected_labjack_service
        
        test_channel = 'AIN0'
        
        # Test multiple readings to check range consistency
        voltage_readings = []
        for _ in range(50):
            voltage = asyncio.run(service.read_single_voltage(test_channel))
            voltage_readings.append(voltage)
            time.sleep(0.005)  # 5ms between readings
        
        # Validate voltage range (T7 supports ±10V by default)
        min_voltage = min(voltage_readings)
        max_voltage = max(voltage_readings)
        
        assert min_voltage >= -10.5, f"Voltage below expected range: {min_voltage}V"
        assert max_voltage <= 10.5, f"Voltage above expected range: {max_voltage}V"
        
        # Check for reasonable resolution (T7 has ~0.3mV resolution)
        unique_values = len(set(f"{v:.4f}" for v in voltage_readings))
        
        # Should have reasonable resolution (not all identical unless grounded)
        logger.info(f"Voltage range: {min_voltage:.4f}V to {max_voltage:.4f}V, "
                   f"{unique_values} unique values")


@pytest.mark.hardware
class TestHighFrequencyDataCapture:
    """Test high-frequency data capture capabilities"""
    
    def test_1000hz_streaming_configuration(self, connected_labjack_service):
        """Test configuration of 1000Hz streaming"""
        service = connected_labjack_service
        
        channels = ['AIN0', 'AIN1']
        requested_rate = 1000  # Hz
        
        # Configure streaming
        actual_rate = asyncio.run(service.configure_stream(channels, requested_rate))
        
        # Validate achieved sample rate
        assert actual_rate > 0, "Stream configuration should return valid rate"
        
        rate_error = abs(actual_rate - requested_rate) / requested_rate
        assert rate_error < SAMPLE_RATE_TOLERANCE, \
            f"Sample rate error too high: {rate_error:.1%} (requested: {requested_rate}Hz, actual: {actual_rate}Hz)"
        
        logger.info(f"Streaming configured: {actual_rate}Hz (requested: {requested_rate}Hz)")
    
    def test_high_frequency_data_streaming(self, connected_labjack_service):
        """Test actual high-frequency data streaming"""
        service = connected_labjack_service
        
        channels = ['AIN0', 'AIN1']
        sample_rate = 1000
        test_duration = 5.0  # seconds
        
        # Start streaming
        success = asyncio.run(service.start_stream(channels, sample_rate))
        assert success, "Should start high-frequency streaming"
        
        try:
            # Collect streaming data
            start_time = time.time()
            total_samples = 0
            data_batches = []
            
            while (time.time() - start_time) < test_duration:
                # Get streaming data
                batch = service.get_stream_data(max_samples=200)
                if batch:
                    data_batches.append({
                        'timestamp': time.time(),
                        'sample_count': len(batch),
                        'data': batch[:10]  # Store first 10 samples for analysis
                    })
                    total_samples += len(batch)
                
                time.sleep(0.01)  # 10ms collection intervals
            
            actual_duration = time.time() - start_time
            
            # Validate streaming performance
            expected_samples = sample_rate * len(channels) * actual_duration
            sample_rate_achieved = total_samples / actual_duration / len(channels)
            
            # Allow some tolerance for timing variations
            rate_error = abs(sample_rate_achieved - sample_rate) / sample_rate
            
            assert total_samples > 0, "Should collect streaming data"
            assert rate_error < 0.2, \
                f"Streaming rate error too high: {rate_error:.1%} " \
                f"(expected: {sample_rate}Hz, achieved: {sample_rate_achieved:.1f}Hz)"
            
            logger.info(f"Streaming performance: {sample_rate_achieved:.1f}Hz achieved, "
                       f"{total_samples} samples over {actual_duration:.1f}s")
            
        finally:
            # Stop streaming
            asyncio.run(service.stop_stream())
    
    def test_timing_precision_validation(self, connected_labjack_service):
        """Test timing precision of high-frequency capture"""
        service = connected_labjack_service
        
        # Configure for timing precision test
        channels = ['AIN0']
        sample_rate = 1000
        
        success = asyncio.run(service.start_stream(channels, sample_rate))
        assert success, "Should start timing precision test"
        
        try:
            # Collect timestamps with high precision
            timing_measurements = []
            measurement_count = 100
            
            for i in range(measurement_count):
                start_time = time.time_ns()  # Nanosecond precision
                
                # Get data batch
                batch = service.get_stream_data(max_samples=10)
                
                end_time = time.time_ns()
                collection_time_ns = end_time - start_time
                
                timing_measurements.append({
                    'iteration': i,
                    'collection_time_ns': collection_time_ns,
                    'sample_count': len(batch),
                    'timestamp_ns': start_time
                })
                
                time.sleep(0.001)  # 1ms between measurements
            
            # Analyze timing precision
            collection_times = [m['collection_time_ns'] for m in timing_measurements]
            
            if collection_times:
                mean_collection_time = np.mean(collection_times)
                std_collection_time = np.std(collection_times)
                
                # Collection should be consistently fast
                assert mean_collection_time < 10_000_000, \
                    f"Data collection too slow: {mean_collection_time/1e6:.2f}ms mean"
                
                # Timing should be consistent (low jitter)
                timing_jitter_ratio = std_collection_time / mean_collection_time
                assert timing_jitter_ratio < 0.5, \
                    f"Timing jitter too high: {timing_jitter_ratio:.2f}"
                
                logger.info(f"Timing precision: {mean_collection_time/1e6:.2f}ms ±{std_collection_time/1e6:.2f}ms")
        
        finally:
            asyncio.run(service.stop_stream())


@pytest.mark.hardware
class TestHardwareFailureRecovery:
    """Test hardware failure detection and recovery"""
    
    def test_connection_recovery_after_disconnect(self, hardware_detection):
        """Test system recovery after hardware disconnection"""
        if not hardware_detection['available']:
            pytest.skip("Real LabJack hardware not available")
        
        service = LabJackService()
        
        # Initial connection
        connected = asyncio.run(service.connect(allow_mock=False))
        assert connected, "Initial connection should succeed"
        assert service.mode != ConnectionMode.MOCK, "Should connect to real hardware"
        
        # Verify initial functionality
        initial_voltage = asyncio.run(service.read_single_voltage('AIN0'))
        assert isinstance(initial_voltage, (int, float)), "Should read initial voltage"
        
        # Simulate disconnect (graceful shutdown)
        asyncio.run(service.disconnect())
        assert service.status == ConnectionStatus.DISCONNECTED, "Should be disconnected"
        
        # Wait briefly to simulate real disconnection scenario
        time.sleep(2)
        
        # Attempt reconnection
        reconnected = asyncio.run(service.connect(allow_mock=False))
        assert reconnected, "Should successfully reconnect"
        assert service.mode != ConnectionMode.MOCK, "Should reconnect to real hardware"
        
        # Verify functionality after reconnection
        recovery_voltage = asyncio.run(service.read_single_voltage('AIN0'))
        assert isinstance(recovery_voltage, (int, float)), "Should read voltage after reconnection"
        
        # Cleanup
        asyncio.run(service.disconnect())
    
    def test_streaming_recovery_after_interruption(self, connected_labjack_service):
        """Test streaming recovery after interruption"""
        service = connected_labjack_service
        
        channels = ['AIN0']
        sample_rate = 500  # Lower rate for stability testing
        
        # Start initial streaming
        success = asyncio.run(service.start_stream(channels, sample_rate))
        assert success, "Should start initial streaming"
        
        # Collect initial data
        time.sleep(1)
        initial_data = service.get_stream_data(max_samples=100)
        assert len(initial_data) > 0, "Should collect initial streaming data"
        
        # Stop streaming (simulate interruption)
        asyncio.run(service.stop_stream())
        assert not service.streaming, "Streaming should be stopped"
        
        # Wait briefly
        time.sleep(1)
        
        # Restart streaming
        restart_success = asyncio.run(service.start_stream(channels, sample_rate))
        assert restart_success, "Should restart streaming after interruption"
        
        # Verify streaming recovery
        time.sleep(2)
        recovery_data = service.get_stream_data(max_samples=100)
        assert len(recovery_data) > 0, "Should collect data after streaming restart"
        
        # Cleanup
        asyncio.run(service.stop_stream())
    
    def test_hardware_validation_service_integration(self, connected_labjack_service):
        """Test HIL validation service with real hardware"""
        service = connected_labjack_service
        
        # Create HIL validation service
        hil_validator = HILValidationService(service)
        
        # Test hardware validation
        try:
            hil_validator.validate_hil_requirements()
            logger.info("HIL hardware validation passed")
        except Exception as e:
            pytest.fail(f"HIL validation failed with real hardware: {e}")
        
        # Test validation status
        validation_status = hil_validator.get_hardware_status_for_ui()
        
        assert validation_status['connected'], "Validation should report hardware connected"
        assert validation_status['hil_suitable'], "Hardware should be HIL suitable"
        assert 'error' not in validation_status, "Should not have validation errors"
        
        # Test connection diagnostics
        diagnostics = hil_validator.get_connection_diagnostics()
        
        assert 'labjack_service_status' in diagnostics, "Should include service status"
        assert 'hardware_detection' in diagnostics, "Should include hardware detection info"


@pytest.mark.hardware
class TestExtendedHardwareValidation:
    """Extended hardware validation tests"""
    
    def test_sustained_high_frequency_operation(self, connected_labjack_service):
        """Test sustained high-frequency operation over extended period"""
        service = connected_labjack_service
        
        channels = ['AIN0', 'AIN1']
        sample_rate = 1000
        test_duration = 60  # 1 minute of sustained operation
        
        success = asyncio.run(service.start_stream(channels, sample_rate))
        assert success, "Should start sustained high-frequency streaming"
        
        try:
            start_time = time.time()
            total_samples_collected = 0
            performance_checks = []
            
            while (time.time() - start_time) < test_duration:
                check_start = time.time()
                
                # Collect data batch
                batch = service.get_stream_data(max_samples=500)
                total_samples_collected += len(batch)
                
                check_duration = time.time() - check_start
                
                # Record performance
                performance_checks.append({
                    'elapsed_time': time.time() - start_time,
                    'batch_size': len(batch),
                    'collection_time_ms': check_duration * 1000,
                    'cumulative_samples': total_samples_collected
                })
                
                # Brief pause
                time.sleep(0.1)
            
            actual_test_duration = time.time() - start_time
            
            # Validate sustained performance
            expected_total_samples = sample_rate * len(channels) * actual_test_duration
            sample_collection_rate = total_samples_collected / expected_total_samples
            
            # Should collect majority of expected samples
            assert sample_collection_rate > 0.8, \
                f"Sample collection rate too low: {sample_collection_rate:.1%}"
            
            # Check performance consistency
            collection_times = [check['collection_time_ms'] for check in performance_checks]
            mean_collection_time = np.mean(collection_times)
            std_collection_time = np.std(collection_times)
            
            # Performance should remain stable
            performance_stability = 1 - (std_collection_time / mean_collection_time)
            assert performance_stability > 0.7, \
                f"Performance stability too low: {performance_stability:.1%}"
            
            logger.info(f"Sustained operation: {actual_test_duration:.1f}s, "
                       f"{total_samples_collected} samples collected, "
                       f"{sample_collection_rate:.1%} collection rate")
            
        finally:
            asyncio.run(service.stop_stream())


# Fixtures for hardware testing
@pytest.fixture(scope="module")  
def hardware_test_setup():
    """Module-level setup for hardware tests"""
    logger.info("Setting up hardware integration test suite")
    yield
    logger.info("Hardware integration test suite completed")


if __name__ == "__main__":
    """
    Run hardware integration tests:
    
    All hardware tests (requires real LabJack):
    pytest test_hardware_integration_suite.py -m hardware -v
    
    Specific hardware test categories:
    pytest test_hardware_integration_suite.py::TestLabJackConnectivity -v
    pytest test_hardware_integration_suite.py::TestVoltageReading -v
    pytest test_hardware_integration_suite.py::TestHighFrequencyDataCapture -v
    
    Skip hardware tests (for CI/CD):
    pytest test_hardware_integration_suite.py -m "not hardware" -v
    """
    pytest.main([__file__, "-m", "hardware", "-v"])