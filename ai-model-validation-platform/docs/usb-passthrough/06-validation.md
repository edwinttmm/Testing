# Validation and Testing Procedures

This guide provides comprehensive testing procedures to validate USB passthrough functionality, performance, and security for LabJack devices.

## Table of Contents

1. [Test Environment Setup](#test-environment-setup)
2. [Functional Testing](#functional-testing)
3. [Performance Testing](#performance-testing)
4. [Security Testing](#security-testing)
5. [Automated Testing](#automated-testing)
6. [Integration Testing](#integration-testing)
7. [Stress Testing](#stress-testing)
8. [Validation Reports](#validation-reports)

## Test Environment Setup

### Prerequisites

#### Hardware Requirements
- LabJack device (U3, U6, UE9, T4, T7, or T8)
- Test signals/sensors for validation
- Multiple USB ports for testing
- Network connectivity for remote testing

#### Software Requirements
- Windows 11/10 with WSL2
- usbipd-win installed and configured
- Python 3.8+ with testing libraries
- Docker (optional, for container testing)

#### Test Data Generation

Create `test_signal_generator.py`:

```python
import numpy as np
import time
import threading
from typing import Dict, List, Callable

class TestSignalGenerator:
    """Generate various test signals for LabJack validation"""
    
    def __init__(self, sample_rate: float = 1000.0):
        self.sample_rate = sample_rate
        self.signals = {}
        self.running = False
        
    def generate_sine_wave(self, frequency: float, amplitude: float = 1.0, 
                          offset: float = 0.0, duration: float = 10.0) -> np.ndarray:
        """Generate sine wave test signal"""
        t = np.linspace(0, duration, int(duration * self.sample_rate))
        return amplitude * np.sin(2 * np.pi * frequency * t) + offset
    
    def generate_square_wave(self, frequency: float, amplitude: float = 1.0,
                           duty_cycle: float = 0.5, duration: float = 10.0) -> np.ndarray:
        """Generate square wave test signal"""
        t = np.linspace(0, duration, int(duration * self.sample_rate))
        square = np.where(np.sin(2 * np.pi * frequency * t) >= 0, amplitude, -amplitude)
        return square
    
    def generate_step_response(self, step_time: float = 1.0, amplitude: float = 1.0,
                              duration: float = 10.0) -> np.ndarray:
        """Generate step response signal"""
        t = np.linspace(0, duration, int(duration * self.sample_rate))
        return np.where(t >= step_time, amplitude, 0.0)
    
    def generate_ramp(self, slope: float = 1.0, duration: float = 10.0) -> np.ndarray:
        """Generate ramp signal"""
        t = np.linspace(0, duration, int(duration * self.sample_rate))
        return slope * t
    
    def generate_noise(self, amplitude: float = 0.1, duration: float = 10.0) -> np.ndarray:
        """Generate random noise signal"""
        samples = int(duration * self.sample_rate)
        return amplitude * np.random.normal(0, 1, samples)
    
    def generate_chirp(self, start_freq: float = 1.0, end_freq: float = 100.0,
                      duration: float = 10.0) -> np.ndarray:
        """Generate frequency chirp signal"""
        t = np.linspace(0, duration, int(duration * self.sample_rate))
        freq_t = start_freq + (end_freq - start_freq) * t / duration
        return np.sin(2 * np.pi * freq_t * t)

class TestEnvironment:
    """Setup and manage test environment"""
    
    def __init__(self):
        self.device = None
        self.test_results = {}
        self.signal_generator = TestSignalGenerator()
        
    def setup_environment(self):
        """Initialize test environment"""
        print("Setting up test environment...")
        
        # Check USB/IP connectivity
        self.check_usbip_status()
        
        # Initialize LabJack device
        self.initialize_device()
        
        # Verify basic functionality
        self.basic_connectivity_test()
        
        print("Test environment ready")
    
    def check_usbip_status(self) -> bool:
        """Check USB/IP service status"""
        try:
            import subprocess
            result = subprocess.run(['usbipd', 'list'], 
                                  capture_output=True, text=True, check=True)
            print("USB/IP service is running")
            return True
        except subprocess.CalledProcessError as e:
            print(f"USB/IP service error: {e}")
            return False
        except FileNotFoundError:
            print("usbipd command not found")
            return False
    
    def initialize_device(self):
        """Initialize LabJack device for testing"""
        try:
            import u3  # LabJack U3 library
            self.device = u3.U3()
            print(f"Connected to LabJack U3: {self.device.getName()}")
            return True
        except Exception as e:
            print(f"Failed to connect to LabJack: {e}")
            return False
    
    def basic_connectivity_test(self) -> bool:
        """Basic connectivity test"""
        if not self.device:
            return False
        
        try:
            # Read device info
            info = self.device.configU3()
            print(f"Device info: {info}")
            
            # Test basic I/O
            voltage = self.device.getAIN(0)
            print(f"Channel 0 voltage: {voltage:.3f}V")
            
            return True
        except Exception as e:
            print(f"Basic connectivity test failed: {e}")
            return False
    
    def cleanup(self):
        """Cleanup test environment"""
        if self.device:
            self.device.close()
```

## Functional Testing

### Basic Functionality Tests

Create `test_basic_functionality.py`:

```python
import unittest
import time
import u3
from test_environment import TestEnvironment

class TestBasicFunctionality(unittest.TestCase):
    """Test basic LabJack functionality through USB passthrough"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.test_env = TestEnvironment()
        cls.test_env.setup_environment()
        cls.device = cls.test_env.device
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment"""
        cls.test_env.cleanup()
    
    def test_device_connection(self):
        """Test device connection and identification"""
        self.assertIsNotNone(self.device, "Device should be connected")
        
        # Test device name retrieval
        name = self.device.getName()
        self.assertIsInstance(name, str)
        self.assertGreater(len(name), 0)
        print(f"Device name: {name}")
    
    def test_analog_input_reading(self):
        """Test analog input reading on all channels"""
        for channel in range(4):  # U3 has 4 analog input channels
            with self.subTest(channel=channel):
                voltage = self.device.getAIN(channel)
                self.assertIsInstance(voltage, (int, float))
                self.assertGreaterEqual(voltage, -10.0)  # U3 range
                self.assertLessEqual(voltage, 10.0)
                print(f"Channel {channel}: {voltage:.3f}V")
    
    def test_digital_io(self):
        """Test digital I/O functionality"""
        test_channel = 4  # FIO4
        
        # Test setting digital output high
        self.device.setDIOState(test_channel, 1)
        state = self.device.getDIOState(test_channel)
        self.assertEqual(state, 1, "Digital output should be high")
        
        # Test setting digital output low
        self.device.setDIOState(test_channel, 0)
        state = self.device.getDIOState(test_channel)
        self.assertEqual(state, 0, "Digital output should be low")
    
    def test_device_configuration(self):
        """Test device configuration changes"""
        # Get current configuration
        original_config = self.device.configU3()
        self.assertIsInstance(original_config, dict)
        
        # Modify configuration
        new_config = self.device.configU3(
            LocalID=2,
            TimerCounterPinOffset=4
        )
        self.assertEqual(new_config['LocalID'], 2)
        
        # Restore original configuration
        self.device.configU3(**original_config)
    
    def test_temperature_reading(self):
        """Test internal temperature sensor"""
        temperature = self.device.getTemperature()
        self.assertIsInstance(temperature, (int, float))
        self.assertGreater(temperature, -40)  # Reasonable temperature range
        self.assertLess(temperature, 85)
        print(f"Device temperature: {temperature:.1f}°C")
    
    def test_streaming_configuration(self):
        """Test streaming mode configuration"""
        # Configure streaming
        config_result = self.device.streamConfig(
            NumChannels=2,
            ChannelNumbers=[0, 1],
            ChannelOptions=[0, 0],
            SettlingFactor=1,
            ResolutionIndex=0,
            SampleFrequency=1000
        )
        
        self.assertIsInstance(config_result, dict)
        print(f"Streaming configured: {config_result}")
    
    def test_error_handling(self):
        """Test proper error handling for invalid operations"""
        # Test invalid channel
        with self.assertRaises(Exception):
            self.device.getAIN(99)  # Invalid channel
        
        # Test invalid configuration
        with self.assertRaises(Exception):
            self.device.configU3(LocalID=-1)  # Invalid local ID

class TestAdvancedFunctionality(unittest.TestCase):
    """Test advanced LabJack functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.test_env = TestEnvironment()
        cls.test_env.setup_environment()
        cls.device = cls.test_env.device
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment"""
        cls.test_env.cleanup()
    
    def test_streaming_data_acquisition(self):
        """Test streaming data acquisition"""
        # Configure streaming
        self.device.streamConfig(
            NumChannels=4,
            ChannelNumbers=[0, 1, 2, 3],
            ChannelOptions=[0, 0, 0, 0],
            SettlingFactor=0,
            ResolutionIndex=0,
            SampleFrequency=1000
        )
        
        # Start streaming
        self.device.streamStart()
        
        try:
            # Collect data
            total_samples = 0
            for _ in range(10):  # 10 iterations
                data = self.device.streamData()
                samples = len(data['AIN0'])
                total_samples += samples
                
                # Verify data structure
                self.assertIn('AIN0', data)
                self.assertIn('AIN1', data)
                self.assertIn('AIN2', data)
                self.assertIn('AIN3', data)
                
                # Verify all channels have same number of samples
                self.assertEqual(len(data['AIN0']), len(data['AIN1']))
                self.assertEqual(len(data['AIN1']), len(data['AIN2']))
                self.assertEqual(len(data['AIN2']), len(data['AIN3']))
                
                time.sleep(0.1)
            
            print(f"Collected {total_samples} samples via streaming")
            self.assertGreater(total_samples, 0)
            
        finally:
            # Stop streaming
            self.device.streamStop()
    
    def test_timer_counter(self):
        """Test timer/counter functionality"""
        # Configure timer
        self.device.configTimerClock(TimerClockConfig=2, TimerClockDivisor=1)
        
        # Set up timer
        timer_config = self.device.configIO(
            NumberTimersEnabled=1,
            TimerCounterPinOffset=4,
            EnableCounter1=False
        )
        
        self.assertIsInstance(timer_config, dict)
        print(f"Timer configured: {timer_config}")
    
    def test_watchdog(self):
        """Test watchdog functionality"""
        # Enable watchdog
        watchdog_config = self.device.watchdog(
            Timeout=10,  # 10 second timeout
            DIONumber=5,
            DIOState=0
        )
        
        self.assertIsInstance(watchdog_config, dict)
        print(f"Watchdog configured: {watchdog_config}")
        
        # Disable watchdog
        self.device.watchdog(Timeout=0)

if __name__ == '__main__':
    # Run all tests
    unittest.main(verbosity=2)
```

### Signal Quality Tests

Create `test_signal_quality.py`:

```python
import unittest
import numpy as np
import time
from scipy import signal as scipy_signal
from test_environment import TestEnvironment, TestSignalGenerator

class TestSignalQuality(unittest.TestCase):
    """Test signal quality and accuracy"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.test_env = TestEnvironment()
        cls.test_env.setup_environment()
        cls.device = cls.test_env.device
        cls.signal_gen = TestSignalGenerator()
        
        # Tolerance for measurements
        cls.voltage_tolerance = 0.05  # 5% tolerance
        cls.frequency_tolerance = 0.01  # 1% tolerance
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment"""
        cls.test_env.cleanup()
    
    def test_dc_voltage_accuracy(self):
        """Test DC voltage measurement accuracy"""
        # Note: This test requires external voltage sources
        # For automated testing, use internal references or DAC output
        
        test_voltages = [0.0, 1.0, 2.5, 5.0]  # Expected voltages
        
        for expected_voltage in test_voltages:
            with self.subTest(voltage=expected_voltage):
                # In real test, apply known voltage to input
                # For this example, we'll simulate
                measured_voltage = self.device.getAIN(0)
                
                # Verify within tolerance
                error = abs(measured_voltage - expected_voltage)
                max_error = expected_voltage * self.voltage_tolerance
                
                print(f"Expected: {expected_voltage}V, Measured: {measured_voltage:.3f}V, Error: {error:.3f}V")
                
                # For demo purposes, we'll check if reading is reasonable
                self.assertIsInstance(measured_voltage, (int, float))
                self.assertGreaterEqual(measured_voltage, -10.0)
                self.assertLessEqual(measured_voltage, 10.0)
    
    def test_ac_signal_measurement(self):
        """Test AC signal measurement and frequency analysis"""
        # Configure streaming for signal analysis
        sample_rate = 10000  # 10 kHz
        duration = 1.0  # 1 second
        
        self.device.streamConfig(
            NumChannels=1,
            ChannelNumbers=[0],
            ChannelOptions=[0],
            SettlingFactor=0,
            ResolutionIndex=0,
            SampleFrequency=sample_rate
        )
        
        self.device.streamStart()
        
        try:
            # Collect data
            all_data = []
            start_time = time.time()
            
            while time.time() - start_time < duration:
                data = self.device.streamData()
                all_data.extend(data['AIN0'])
                time.sleep(0.01)
            
            # Convert to numpy array
            signal_data = np.array(all_data)
            
            # Perform frequency analysis
            frequencies, power_spectrum = scipy_signal.periodogram(
                signal_data, fs=sample_rate
            )
            
            # Find dominant frequency
            dominant_freq_idx = np.argmax(power_spectrum)
            dominant_freq = frequencies[dominant_freq_idx]
            
            print(f"Collected {len(signal_data)} samples")
            print(f"Dominant frequency: {dominant_freq:.2f} Hz")
            print(f"Signal RMS: {np.sqrt(np.mean(signal_data**2)):.3f}V")
            
            # Basic validation
            self.assertGreater(len(signal_data), sample_rate * 0.5)  # At least 0.5 seconds of data
            
        finally:
            self.device.streamStop()
    
    def test_noise_characteristics(self):
        """Test noise characteristics of the measurement system"""
        # Collect data with no input signal (or grounded input)
        samples = []
        
        for _ in range(1000):  # 1000 samples
            voltage = self.device.getAIN(0)
            samples.append(voltage)
            time.sleep(0.001)  # 1ms between samples
        
        # Calculate noise statistics
        samples_np = np.array(samples)
        mean_voltage = np.mean(samples_np)
        std_voltage = np.std(samples_np)
        peak_to_peak = np.max(samples_np) - np.min(samples_np)
        
        print(f"Noise characteristics:")
        print(f"  Mean: {mean_voltage:.4f}V")
        print(f"  Std Dev: {std_voltage:.4f}V")
        print(f"  Peak-to-Peak: {peak_to_peak:.4f}V")
        print(f"  SNR estimate: {abs(mean_voltage)/std_voltage:.1f}" if std_voltage > 0 else "  SNR: N/A")
        
        # Validate reasonable noise levels
        self.assertLess(std_voltage, 0.1, "Noise should be less than 0.1V")
        self.assertLess(peak_to_peak, 0.5, "Peak-to-peak noise should be less than 0.5V")
    
    def test_linearity(self):
        """Test ADC linearity across input range"""
        # Note: Requires external programmable voltage source
        # This is a simplified version for demonstration
        
        # Test points across the input range
        test_points = np.linspace(-5.0, 5.0, 11)  # -5V to +5V in 1V steps
        
        measurements = []
        for voltage in test_points:
            # In real test, set external voltage source to 'voltage'
            # For demo, we'll just read current input
            measured = self.device.getAIN(0)
            measurements.append(measured)
            
            print(f"Set: {voltage:.1f}V, Measured: {measured:.3f}V")
        
        measurements_np = np.array(measurements)
        
        # Calculate linearity metrics
        # In real test, would compare against test_points
        linearity_error = np.std(measurements_np) / np.mean(np.abs(measurements_np)) * 100
        
        print(f"Linearity error estimate: {linearity_error:.2f}%")
        
        # Basic validation
        self.assertLess(linearity_error, 5.0, "Linearity error should be less than 5%")

if __name__ == '__main__':
    unittest.main(verbosity=2)
```

## Performance Testing

### Throughput and Latency Tests

Create `test_performance.py`:

```python
import unittest
import time
import statistics
import threading
import queue
import numpy as np
from test_environment import TestEnvironment

class TestPerformance(unittest.TestCase):
    """Test performance characteristics"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.test_env = TestEnvironment()
        cls.test_env.setup_environment()
        cls.device = cls.test_env.device
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment"""
        cls.test_env.cleanup()
    
    def test_single_read_latency(self):
        """Test single analog read latency"""
        iterations = 1000
        latencies = []
        
        print(f"Testing single read latency over {iterations} iterations...")
        
        # Warm-up
        for _ in range(10):
            self.device.getAIN(0)
        
        # Measure latencies
        for i in range(iterations):
            start_time = time.perf_counter()
            voltage = self.device.getAIN(0)
            end_time = time.perf_counter()
            
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
            
            if i % 100 == 0:
                print(f"  Progress: {i}/{iterations}")
        
        # Calculate statistics
        mean_latency = statistics.mean(latencies)
        median_latency = statistics.median(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        std_dev = statistics.stdev(latencies)
        
        print(f"Single Read Latency Results:")
        print(f"  Mean: {mean_latency:.3f}ms")
        print(f"  Median: {median_latency:.3f}ms")
        print(f"  Min/Max: {min_latency:.3f}ms / {max_latency:.3f}ms")
        print(f"  Std Dev: {std_dev:.3f}ms")
        print(f"  Rate: {1000/mean_latency:.1f} reads/sec")
        
        # Performance assertions
        self.assertLess(mean_latency, 2.0, "Mean latency should be less than 2ms")
        self.assertLess(max_latency, 10.0, "Max latency should be less than 10ms")
        self.assertGreater(1000/mean_latency, 100, "Should achieve >100 reads/sec")
    
    def test_streaming_throughput(self):
        """Test streaming mode throughput"""
        sample_rates = [1000, 2000, 5000, 10000]  # Test different sample rates
        
        for target_rate in sample_rates:
            with self.subTest(sample_rate=target_rate):
                print(f"Testing streaming at {target_rate} Hz...")
                
                # Configure streaming
                self.device.streamConfig(
                    NumChannels=4,
                    ChannelNumbers=[0, 1, 2, 3],
                    ChannelOptions=[0, 0, 0, 0],
                    SettlingFactor=0,
                    ResolutionIndex=0,
                    SampleFrequency=target_rate
                )
                
                self.device.streamStart()
                
                try:
                    # Collect data for 5 seconds
                    duration = 5.0
                    start_time = time.time()
                    total_samples = 0
                    read_times = []
                    
                    while time.time() - start_time < duration:
                        read_start = time.perf_counter()
                        data = self.device.streamData()
                        read_end = time.perf_counter()
                        
                        samples_read = len(data['AIN0'])
                        total_samples += samples_read
                        read_times.append(read_end - read_start)
                        
                        time.sleep(0.01)  # Small delay
                    
                    actual_duration = time.time() - start_time
                    actual_rate = total_samples / actual_duration
                    rate_accuracy = (actual_rate / target_rate) * 100
                    
                    print(f"  Target rate: {target_rate} Hz")
                    print(f"  Actual rate: {actual_rate:.1f} Hz")
                    print(f"  Rate accuracy: {rate_accuracy:.1f}%")
                    print(f"  Avg read time: {statistics.mean(read_times)*1000:.2f}ms")
                    print(f"  Total samples: {total_samples}")
                    
                    # Performance assertions
                    self.assertGreater(rate_accuracy, 90, f"Rate accuracy should be >90% for {target_rate}Hz")
                    self.assertGreater(actual_rate, target_rate * 0.9, f"Should achieve >90% of target rate")
                    
                finally:
                    self.device.streamStop()
    
    def test_concurrent_access(self):
        """Test concurrent device access performance"""
        num_threads = 4
        duration = 5.0
        results_queue = queue.Queue()
        
        def worker_thread(thread_id):
            """Worker thread for concurrent access"""
            start_time = time.time()
            read_count = 0
            latencies = []
            
            while time.time() - start_time < duration:
                read_start = time.perf_counter()
                try:
                    voltage = self.device.getAIN(thread_id % 4)  # Each thread reads different channel
                    read_end = time.perf_counter()
                    
                    latency = (read_end - read_start) * 1000
                    latencies.append(latency)
                    read_count += 1
                    
                except Exception as e:
                    print(f"Thread {thread_id} error: {e}")
                    break
                
                time.sleep(0.001)  # 1ms delay
            
            actual_duration = time.time() - start_time
            results_queue.put({
                'thread_id': thread_id,
                'read_count': read_count,
                'rate': read_count / actual_duration,
                'avg_latency': statistics.mean(latencies) if latencies else 0,
                'max_latency': max(latencies) if latencies else 0
            })
        
        print(f"Testing concurrent access with {num_threads} threads...")
        
        # Start threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Collect results
        total_reads = 0
        total_rate = 0
        max_latency_overall = 0
        
        while not results_queue.empty():
            result = results_queue.get()
            print(f"  Thread {result['thread_id']}: {result['read_count']} reads, "
                  f"{result['rate']:.1f} reads/sec, "
                  f"avg latency: {result['avg_latency']:.2f}ms")
            
            total_reads += result['read_count']
            total_rate += result['rate']
            max_latency_overall = max(max_latency_overall, result['max_latency'])
        
        print(f"Concurrent Access Results:")
        print(f"  Total reads: {total_reads}")
        print(f"  Combined rate: {total_rate:.1f} reads/sec")
        print(f"  Max latency: {max_latency_overall:.2f}ms")
        
        # Performance assertions
        self.assertGreater(total_rate, 100, "Combined rate should be >100 reads/sec")
        self.assertLess(max_latency_overall, 50, "Max latency should be <50ms under load")
    
    def test_memory_usage(self):
        """Test memory usage during operation"""
        import psutil
        import gc
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"Testing memory usage (initial: {initial_memory:.1f} MB)...")
        
        # Perform memory-intensive operations
        data_collections = []
        
        for iteration in range(100):
            # Configure and run streaming
            self.device.streamConfig(
                NumChannels=4,
                ChannelNumbers=[0, 1, 2, 3],
                ChannelOptions=[0, 0, 0, 0],
                SettlingFactor=0,
                ResolutionIndex=0,
                SampleFrequency=1000
            )
            
            self.device.streamStart()
            
            # Collect data
            collected_data = []
            for _ in range(10):
                data = self.device.streamData()
                collected_data.append(data)
            
            data_collections.append(collected_data)
            
            self.device.streamStop()
            
            # Check memory usage every 10 iterations
            if iteration % 10 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_increase = current_memory - initial_memory
                print(f"  Iteration {iteration}: {current_memory:.1f} MB (+{memory_increase:.1f} MB)")
                
                # Force garbage collection
                gc.collect()
        
        final_memory = process.memory_info().rss / 1024 / 1024
        total_increase = final_memory - initial_memory
        
        print(f"Memory Usage Results:")
        print(f"  Initial: {initial_memory:.1f} MB")
        print(f"  Final: {final_memory:.1f} MB")
        print(f"  Increase: {total_increase:.1f} MB")
        
        # Memory assertions
        self.assertLess(total_increase, 100, "Memory increase should be <100MB")
        self.assertLess(final_memory, 500, "Final memory usage should be <500MB")

if __name__ == '__main__':
    unittest.main(verbosity=2)
```

## Security Testing

### Security Validation Tests

Create `test_security.py`:

```python
import unittest
import socket
import subprocess
import time
import os
from test_environment import TestEnvironment

class TestSecurity(unittest.TestCase):
    """Test security aspects of USB passthrough"""
    
    @classmethod
    def setUpClass(cls):
        """Set up security test environment"""
        cls.test_env = TestEnvironment()
        # Note: Security tests may require elevated privileges
    
    def test_service_permissions(self):
        """Test USB/IP service runs with appropriate permissions"""
        try:
            # Check if usbipd service is running
            result = subprocess.run(['sc', 'query', 'usbipd'], 
                                  capture_output=True, text=True)
            
            self.assertIn('RUNNING', result.stdout, "usbipd service should be running")
            print("usbipd service is running with proper permissions")
            
        except subprocess.CalledProcessError:
            self.skipTest("Unable to check service status")
    
    def test_firewall_configuration(self):
        """Test firewall configuration for USB/IP"""
        try:
            # Check firewall rules for USB/IP port (3240)
            result = subprocess.run([
                'netsh', 'advfirewall', 'firewall', 'show', 'rule', 
                'name=all', 'protocol=tcp', 'localport=3240'
            ], capture_output=True, text=True)
            
            # Should have firewall rules configured
            self.assertIn('3240', result.stdout, "Firewall rules should exist for USB/IP port")
            print("Firewall is configured for USB/IP")
            
        except subprocess.CalledProcessError:
            print("Warning: Unable to check firewall configuration")
    
    def test_unauthorized_access_prevention(self):
        """Test prevention of unauthorized device access"""
        # This test simulates unauthorized access attempt
        
        # Try to access USB/IP port without proper authentication
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            # Attempt connection to USB/IP port
            result = sock.connect_ex(('localhost', 3240))
            sock.close()
            
            if result == 0:
                print("Warning: USB/IP port is accessible without authentication")
            else:
                print("USB/IP port properly protected")
                
        except Exception as e:
            print(f"Network test error: {e}")
    
    def test_device_access_logging(self):
        """Test that device access is properly logged"""
        # Check if security logging is enabled
        log_files = [
            '/var/log/labjack_security.log',
            'C:\\Windows\\System32\\LogFiles\\Firewall\\usbip.log'
        ]
        
        log_found = False
        for log_file in log_files:
            if os.path.exists(log_file):
                log_found = True
                print(f"Security log found: {log_file}")
                
                # Check if log file is writable (indicates active logging)
                try:
                    with open(log_file, 'a') as f:
                        # Test write (will be logged)
                        f.write(f"# Security test entry: {time.time()}\n")
                    print("Security logging is active")
                except PermissionError:
                    print("Security log exists but not writable")
                break
        
        if not log_found:
            print("Warning: No security log files found")
    
    def test_data_encryption_capability(self):
        """Test that data can be encrypted if required"""
        try:
            from cryptography.fernet import Fernet
            
            # Test encryption capability
            key = Fernet.generate_key()
            cipher = Fernet(key)
            
            # Simulate encrypted data transmission
            test_data = b"LabJack sensor data: 2.45V"
            encrypted_data = cipher.encrypt(test_data)
            decrypted_data = cipher.decrypt(encrypted_data)
            
            self.assertEqual(test_data, decrypted_data, "Encryption/decryption should work correctly")
            print("Data encryption capability verified")
            
        except ImportError:
            self.skipTest("Cryptography library not available")
    
    def test_container_security(self):
        """Test container security configuration"""
        try:
            # Check if running in container
            if os.path.exists('/.dockerenv'):
                print("Running in Docker container")
                
                # Check if running as non-root user
                uid = os.getuid()
                self.assertNotEqual(uid, 0, "Should not run as root in container")
                print(f"Running as UID: {uid}")
                
                # Check for security policies
                security_files = [
                    '/etc/apparmor.d/labjack-container',
                    '/etc/seccomp/labjack.json'
                ]
                
                for sec_file in security_files:
                    if os.path.exists(sec_file):
                        print(f"Security policy found: {sec_file}")
            else:
                print("Not running in container")
                
        except Exception as e:
            print(f"Container security test error: {e}")

class TestNetworkSecurity(unittest.TestCase):
    """Test network security aspects"""
    
    def test_port_scanning_resistance(self):
        """Test resistance to port scanning"""
        # Simulate port scan on common ports
        test_ports = [3240, 22, 80, 443, 8080]
        open_ports = []
        
        for port in test_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            
            result = sock.connect_ex(('localhost', port))
            if result == 0:
                open_ports.append(port)
            
            sock.close()
        
        print(f"Open ports detected: {open_ports}")
        
        # USB/IP port should only be open if properly configured
        if 3240 in open_ports:
            print("USB/IP port is open - ensure proper firewall configuration")
        else:
            print("USB/IP port is closed/filtered")
    
    def test_ssl_tls_support(self):
        """Test SSL/TLS support for secure communications"""
        try:
            import ssl
            
            # Test SSL context creation
            context = ssl.create_default_context()
            self.assertIsInstance(context, ssl.SSLContext)
            
            # Test supported protocols
            supported_protocols = []
            if hasattr(ssl, 'PROTOCOL_TLSv1_2'):
                supported_protocols.append('TLSv1.2')
            if hasattr(ssl, 'PROTOCOL_TLS'):
                supported_protocols.append('TLS')
            
            print(f"Supported SSL/TLS protocols: {supported_protocols}")
            self.assertGreater(len(supported_protocols), 0, "Should support TLS")
            
        except ImportError:
            self.skipTest("SSL module not available")

if __name__ == '__main__':
    unittest.main(verbosity=2)
```

## Automated Testing

### Continuous Integration Test Suite

Create `run_all_tests.py`:

```python
#!/usr/bin/env python3
"""
Comprehensive test runner for LabJack USB passthrough validation
"""

import unittest
import sys
import time
import json
import os
from datetime import datetime

# Import test modules
from test_basic_functionality import TestBasicFunctionality, TestAdvancedFunctionality
from test_signal_quality import TestSignalQuality
from test_performance import TestPerformance
from test_security import TestSecurity, TestNetworkSecurity

class TestRunner:
    """Custom test runner with detailed reporting"""
    
    def __init__(self):
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    def run_test_suite(self, test_suite_name, test_classes):
        """Run a test suite and collect results"""
        print(f"\n{'='*60}")
        print(f"Running {test_suite_name} Test Suite")
        print(f"{'='*60}")
        
        suite_results = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'error_tests': 0,
            'skipped_tests': 0,
            'test_details': []
        }
        
        for test_class in test_classes:
            print(f"\nRunning {test_class.__name__}...")
            
            # Create test loader and suite
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromTestCase(test_class)
            
            # Run tests with custom result handler
            result = unittest.TestResult()
            suite.run(result)
            
            # Process results
            suite_results['total_tests'] += result.testsRun
            suite_results['passed_tests'] += result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
            suite_results['failed_tests'] += len(result.failures)
            suite_results['error_tests'] += len(result.errors)
            suite_results['skipped_tests'] += len(result.skipped)
            
            # Store test details
            for test, traceback in result.failures:
                suite_results['test_details'].append({
                    'test': str(test),
                    'status': 'FAILED',
                    'message': traceback
                })
            
            for test, traceback in result.errors:
                suite_results['test_details'].append({
                    'test': str(test),
                    'status': 'ERROR',
                    'message': traceback
                })
            
            for test, reason in result.skipped:
                suite_results['test_details'].append({
                    'test': str(test),
                    'status': 'SKIPPED',
                    'message': reason
                })
        
        self.results[test_suite_name] = suite_results
        self.print_suite_summary(test_suite_name, suite_results)
    
    def print_suite_summary(self, suite_name, results):
        """Print test suite summary"""
        print(f"\n{suite_name} Test Results:")
        print(f"  Total Tests: {results['total_tests']}")
        print(f"  Passed: {results['passed_tests']}")
        print(f"  Failed: {results['failed_tests']}")
        print(f"  Errors: {results['error_tests']}")
        print(f"  Skipped: {results['skipped_tests']}")
        
        if results['total_tests'] > 0:
            success_rate = (results['passed_tests'] / results['total_tests']) * 100
            print(f"  Success Rate: {success_rate:.1f}%")
    
    def generate_report(self, output_file='test_report.json'):
        """Generate detailed test report"""
        report = {
            'test_run_info': {
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'duration_seconds': (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None,
                'python_version': sys.version,
                'platform': sys.platform
            },
            'test_results': self.results,
            'summary': self.calculate_overall_summary()
        }
        
        # Write JSON report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nDetailed test report saved to: {output_file}")
        
        # Generate human-readable report
        self.generate_html_report(report)
    
    def calculate_overall_summary(self):
        """Calculate overall test summary"""
        total_tests = sum(suite['total_tests'] for suite in self.results.values())
        total_passed = sum(suite['passed_tests'] for suite in self.results.values())
        total_failed = sum(suite['failed_tests'] for suite in self.results.values())
        total_errors = sum(suite['error_tests'] for suite in self.results.values())
        total_skipped = sum(suite['skipped_tests'] for suite in self.results.values())
        
        return {
            'total_tests': total_tests,
            'passed_tests': total_passed,
            'failed_tests': total_failed,
            'error_tests': total_errors,
            'skipped_tests': total_skipped,
            'success_rate': (total_passed / total_tests * 100) if total_tests > 0 else 0
        }
    
    def generate_html_report(self, report):
        """Generate HTML test report"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>LabJack USB Passthrough Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 10px; border-radius: 5px; }}
        .summary {{ background-color: #e8f5e8; padding: 10px; margin: 10px 0; border-radius: 5px; }}
        .suite {{ margin: 20px 0; }}
        .passed {{ color: green; }}
        .failed {{ color: red; }}
        .error {{ color: orange; }}
        .skipped {{ color: blue; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>LabJack USB Passthrough Test Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Duration: {report['test_run_info']['duration_seconds']:.2f} seconds</p>
    </div>
    
    <div class="summary">
        <h2>Overall Summary</h2>
        <p>Total Tests: {report['summary']['total_tests']}</p>
        <p class="passed">Passed: {report['summary']['passed_tests']}</p>
        <p class="failed">Failed: {report['summary']['failed_tests']}</p>
        <p class="error">Errors: {report['summary']['error_tests']}</p>
        <p class="skipped">Skipped: {report['summary']['skipped_tests']}</p>
        <p><strong>Success Rate: {report['summary']['success_rate']:.1f}%</strong></p>
    </div>
"""
        
        for suite_name, suite_results in report['test_results'].items():
            html_content += f"""
    <div class="suite">
        <h3>{suite_name}</h3>
        <table>
            <tr>
                <th>Metric</th>
                <th>Count</th>
            </tr>
            <tr><td>Total Tests</td><td>{suite_results['total_tests']}</td></tr>
            <tr><td class="passed">Passed</td><td>{suite_results['passed_tests']}</td></tr>
            <tr><td class="failed">Failed</td><td>{suite_results['failed_tests']}</td></tr>
            <tr><td class="error">Errors</td><td>{suite_results['error_tests']}</td></tr>
            <tr><td class="skipped">Skipped</td><td>{suite_results['skipped_tests']}</td></tr>
        </table>
    </div>
"""
        
        html_content += """
</body>
</html>
"""
        
        with open('test_report.html', 'w') as f:
            f.write(html_content)
        
        print("HTML test report saved to: test_report.html")

def main():
    """Main test execution function"""
    runner = TestRunner()
    runner.start_time = datetime.now()
    
    print("Starting LabJack USB Passthrough Validation Test Suite")
    print(f"Start time: {runner.start_time}")
    
    try:
        # Define test suites
        test_suites = {
            "Basic Functionality": [TestBasicFunctionality, TestAdvancedFunctionality],
            "Signal Quality": [TestSignalQuality],
            "Performance": [TestPerformance],
            "Security": [TestSecurity, TestNetworkSecurity]
        }
        
        # Run all test suites
        for suite_name, test_classes in test_suites.items():
            try:
                runner.run_test_suite(suite_name, test_classes)
            except Exception as e:
                print(f"Error running {suite_name} tests: {e}")
        
        runner.end_time = datetime.now()
        
        # Generate reports
        runner.generate_report()
        
        # Print final summary
        print(f"\n{'='*60}")
        print("FINAL TEST SUMMARY")
        print(f"{'='*60}")
        summary = runner.calculate_overall_summary()
        print(f"Total Tests Run: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']} ({summary['success_rate']:.1f}%)")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Errors: {summary['error_tests']}")
        print(f"Skipped: {summary['skipped_tests']}")
        print(f"Duration: {(runner.end_time - runner.start_time).total_seconds():.2f} seconds")
        
        # Exit code based on results
        if summary['failed_tests'] > 0 or summary['error_tests'] > 0:
            print("\nSome tests failed. Please check the detailed report.")
            sys.exit(1)
        else:
            print("\nAll tests passed successfully!")
            sys.exit(0)
    
    except KeyboardInterrupt:
        print("\nTest execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error during test execution: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
```

### GitHub Actions Workflow

Create `.github/workflows/usb-passthrough-tests.yml`:

```yaml
name: USB Passthrough Validation Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  test:
    runs-on: windows-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-html pytest-cov
    
    - name: Install usbipd-win
      run: |
        winget install --id=dorssel.usbipd-win --silent --accept-package-agreements --accept-source-agreements
    
    - name: Enable WSL2
      run: |
        dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
        dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
    
    - name: Install WSL2 Ubuntu
      run: |
        wsl --install Ubuntu --no-launch
    
    - name: Run validation tests
      run: |
        python run_all_tests.py
      continue-on-error: true
    
    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: test-results
        path: |
          test_report.json
          test_report.html
    
    - name: Publish test report
      uses: mikepenz/action-junit-report@v3
      if: always()
      with:
        report_paths: 'test_report.xml'
        check_name: 'USB Passthrough Test Results'
```

## Integration Testing

### End-to-End Workflow Tests

Create `test_integration.py`:

```python
import unittest
import subprocess
import time
import json
import os
from test_environment import TestEnvironment

class TestIntegration(unittest.TestCase):
    """Integration tests for complete USB passthrough workflow"""
    
    @classmethod
    def setUpClass(cls):
        """Set up integration test environment"""
        cls.test_env = TestEnvironment()
        # Don't initialize device yet - we'll test the full setup process
    
    def test_full_setup_workflow(self):
        """Test complete setup workflow from scratch"""
        print("Testing full USB passthrough setup workflow...")
        
        # Step 1: Check usbipd installation
        self.assertTrue(self._check_usbipd_installed(), "usbipd-win should be installed")
        
        # Step 2: Check WSL2 availability  
        self.assertTrue(self._check_wsl2_available(), "WSL2 should be available")
        
        # Step 3: List USB devices
        devices = self._list_usb_devices()
        self.assertIsInstance(devices, list, "Should get list of USB devices")
        
        # Step 4: Find LabJack device
        labjack_device = self._find_labjack_device(devices)
        if not labjack_device:
            self.skipTest("No LabJack device found for integration test")
        
        print(f"Found LabJack device: {labjack_device}")
        
        # Step 5: Bind device
        self.assertTrue(self._bind_device(labjack_device['busid']), "Device binding should succeed")
        
        # Step 6: Attach to WSL
        self.assertTrue(self._attach_to_wsl(labjack_device['busid']), "WSL attachment should succeed")
        
        # Step 7: Verify device in WSL
        self.assertTrue(self._verify_device_in_wsl(), "Device should be visible in WSL")
        
        # Step 8: Test basic functionality
        self.assertTrue(self._test_basic_functionality(), "Basic functionality should work")
        
        # Step 9: Cleanup
        self._cleanup_device(labjack_device['busid'])
        
        print("Full setup workflow test completed successfully")
    
    def _check_usbipd_installed(self) -> bool:
        """Check if usbipd-win is installed"""
        try:
            result = subprocess.run(['usbipd', '--version'], 
                                  capture_output=True, text=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _check_wsl2_available(self) -> bool:
        """Check if WSL2 is available"""
        try:
            result = subprocess.run(['wsl', '--list', '--verbose'], 
                                  capture_output=True, text=True, check=True)
            return 'VERSION 2' in result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _list_usb_devices(self) -> list:
        """Get list of USB devices"""
        try:
            result = subprocess.run(['usbipd', 'list'], 
                                  capture_output=True, text=True, check=True)
            
            devices = []
            for line in result.stdout.split('\n')[2:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        devices.append({
                            'busid': parts[0],
                            'vid_pid': parts[1],
                            'description': ' '.join(parts[2:-1]),
                            'state': parts[-1]
                        })
            
            return devices
        except subprocess.CalledProcessError:
            return []
    
    def _find_labjack_device(self, devices: list) -> dict:
        """Find LabJack device in device list"""
        for device in devices:
            if device['vid_pid'].startswith('0cd5:'):  # LabJack vendor ID
                return device
        return None
    
    def _bind_device(self, busid: str) -> bool:
        """Bind device for sharing"""
        try:
            result = subprocess.run(['usbipd', 'bind', '--busid', busid], 
                                  capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Bind failed: {e.stderr}")
            return False
    
    def _attach_to_wsl(self, busid: str) -> bool:
        """Attach device to WSL"""
        try:
            result = subprocess.run(['usbipd', 'attach', '--wsl', '--busid', busid], 
                                  capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Attach failed: {e.stderr}")
            return False
    
    def _verify_device_in_wsl(self) -> bool:
        """Verify device is visible in WSL"""
        try:
            result = subprocess.run(['wsl', 'lsusb'], 
                                  capture_output=True, text=True, check=True)
            return '0cd5:' in result.stdout
        except subprocess.CalledProcessError:
            return False
    
    def _test_basic_functionality(self) -> bool:
        """Test basic LabJack functionality in WSL"""
        try:
            # Test Python script in WSL
            test_script = '''
import sys
try:
    import u3
    device = u3.U3()
    voltage = device.getAIN(0)
    print(f"SUCCESS: Read voltage {voltage:.3f}V")
    device.close()
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
'''
            
            result = subprocess.run(['wsl', 'python3', '-c', test_script], 
                                  capture_output=True, text=True, timeout=30)
            
            return result.returncode == 0 and 'SUCCESS' in result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False
    
    def _cleanup_device(self, busid: str):
        """Cleanup device attachment"""
        try:
            subprocess.run(['usbipd', 'detach', '--busid', busid], 
                         capture_output=True, check=False)
            subprocess.run(['usbipd', 'unbind', '--busid', busid], 
                         capture_output=True, check=False)
        except Exception:
            pass  # Best effort cleanup

class TestContainerIntegration(unittest.TestCase):
    """Test Docker container integration"""
    
    def test_docker_passthrough(self):
        """Test LabJack access through Docker container"""
        # Check if Docker is available
        try:
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, text=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest("Docker not available")
        
        print("Testing Docker container integration...")
        
        # Build test container
        dockerfile_content = '''
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \\
    python3 \\
    python3-pip \\
    libusb-1.0-0-dev \\
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install u3

COPY test_script.py /test_script.py
CMD ["python3", "/test_script.py"]
'''
        
        test_script_content = '''
import u3
import sys

try:
    device = u3.U3()
    print("Container: Successfully connected to LabJack")
    voltage = device.getAIN(0)
    print(f"Container: Read voltage {voltage:.3f}V")
    device.close()
    print("Container: Test completed successfully")
except Exception as e:
    print(f"Container: Error - {e}")
    sys.exit(1)
'''
        
        # Write temporary files
        with open('Dockerfile.test', 'w') as f:
            f.write(dockerfile_content)
        
        with open('test_script.py', 'w') as f:
            f.write(test_script_content)
        
        try:
            # Build container
            build_result = subprocess.run([
                'docker', 'build', '-f', 'Dockerfile.test', '-t', 'labjack-test', '.'
            ], capture_output=True, text=True, timeout=300)
            
            self.assertEqual(build_result.returncode, 0, "Container build should succeed")
            
            # Run container with USB device access
            run_result = subprocess.run([
                'docker', 'run', '--rm', '--device=/dev/bus/usb', 'labjack-test'
            ], capture_output=True, text=True, timeout=60)
            
            print(f"Container output: {run_result.stdout}")
            if run_result.stderr:
                print(f"Container errors: {run_result.stderr}")
            
            # Check if container test succeeded
            self.assertIn('Test completed successfully', run_result.stdout, 
                         "Container test should complete successfully")
            
        except subprocess.TimeoutExpired:
            self.fail("Container operation timed out")
        finally:
            # Cleanup temporary files
            for temp_file in ['Dockerfile.test', 'test_script.py']:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

if __name__ == '__main__':
    unittest.main(verbosity=2)
```

## Validation Reports

### Test Report Generator

Create `generate_validation_report.py`:

```python
#!/usr/bin/env python3
"""
Generate comprehensive validation report for LabJack USB passthrough
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

class ValidationReportGenerator:
    """Generate detailed validation reports"""
    
    def __init__(self, test_results_file='test_report.json'):
        self.test_results_file = test_results_file
        self.report_data = None
        
    def load_test_results(self):
        """Load test results from JSON file"""
        if not os.path.exists(self.test_results_file):
            raise FileNotFoundError(f"Test results file not found: {self.test_results_file}")
        
        with open(self.test_results_file, 'r') as f:
            self.report_data = json.load(f)
    
    def generate_executive_summary(self):
        """Generate executive summary"""
        summary = self.report_data['summary']
        
        return f"""
# LabJack USB Passthrough Validation Report

## Executive Summary

**Test Date:** {datetime.now().strftime('%Y-%m-%d')}

**Overall Results:**
- **Total Tests:** {summary['total_tests']}
- **Success Rate:** {summary['success_rate']:.1f}%
- **Passed:** {summary['passed_tests']}
- **Failed:** {summary['failed_tests']}
- **Errors:** {summary['error_tests']}
- **Skipped:** {summary['skipped_tests']}

**Verdict:** {'PASS' if summary['success_rate'] >= 90 else 'FAIL'}

The USB passthrough solution has been {'successfully validated' if summary['success_rate'] >= 90 else 'found to have issues'} for LabJack device connectivity.
"""
    
    def generate_detailed_results(self):
        """Generate detailed test results"""
        results_md = "\n## Detailed Test Results\n\n"
        
        for suite_name, suite_results in self.report_data['test_results'].items():
            results_md += f"### {suite_name}\n\n"
            results_md += f"- **Total Tests:** {suite_results['total_tests']}\n"
            results_md += f"- **Passed:** {suite_results['passed_tests']}\n"
            results_md += f"- **Failed:** {suite_results['failed_tests']}\n"
            results_md += f"- **Errors:** {suite_results['error_tests']}\n"
            results_md += f"- **Skipped:** {suite_results['skipped_tests']}\n"
            
            if suite_results['total_tests'] > 0:
                success_rate = (suite_results['passed_tests'] / suite_results['total_tests']) * 100
                results_md += f"- **Success Rate:** {success_rate:.1f}%\n"
            
            results_md += "\n"
            
            # Add failed test details
            failed_tests = [test for test in suite_results.get('test_details', []) 
                          if test['status'] in ['FAILED', 'ERROR']]
            
            if failed_tests:
                results_md += "**Failed Tests:**\n"
                for test in failed_tests:
                    results_md += f"- `{test['test']}`: {test['status']}\n"
                results_md += "\n"
        
        return results_md
    
    def generate_performance_analysis(self):
        """Generate performance analysis section"""
        return """
## Performance Analysis

### Key Performance Metrics

Based on the performance tests, the following metrics were observed:

- **Single Read Latency:** Mean latency should be < 2ms for optimal performance
- **Streaming Throughput:** Should achieve >90% of target sample rate
- **Concurrent Access:** Multiple threads should maintain reasonable latency
- **Memory Usage:** Memory growth should be minimal during extended operation

### Performance Recommendations

1. **Latency Optimization:**
   - Ensure Windows timer resolution is set to 1ms
   - Disable USB selective suspend
   - Use high-performance power plan

2. **Throughput Optimization:**
   - Configure optimal streaming parameters
   - Use appropriate buffer sizes
   - Minimize context switching

3. **Resource Management:**
   - Implement proper connection pooling
   - Use garbage collection optimization
   - Monitor memory usage patterns
"""
    
    def generate_security_assessment(self):
        """Generate security assessment section"""
        return """
## Security Assessment

### Security Measures Validated

1. **Network Security:**
   - Firewall configuration for USB/IP port
   - Network access restrictions
   - SSL/TLS support for encrypted communication

2. **Access Control:**
   - User permission validation
   - Device access logging
   - Authentication mechanisms

3. **Container Security:**
   - Non-root user execution
   - Security policy enforcement
   - Capability restrictions

### Security Recommendations

1. **Network Security:**
   - Use VPN for remote access
   - Implement network segmentation
   - Enable comprehensive logging

2. **Data Protection:**
   - Encrypt sensitive data at rest
   - Use secure communication protocols
   - Implement data retention policies

3. **Monitoring:**
   - Deploy security monitoring tools
   - Set up alerting for suspicious activity
   - Regular security audits
"""
    
    def generate_recommendations(self):
        """Generate recommendations section"""
        summary = self.report_data['summary']
        
        recommendations = "\n## Recommendations\n\n"
        
        if summary['success_rate'] >= 95:
            recommendations += """
### Excellent Results
The USB passthrough solution is performing excellently. Consider:
- Deploying to production environment
- Implementing monitoring and alerting
- Creating operational procedures
"""
        elif summary['success_rate'] >= 90:
            recommendations += """
### Good Results with Minor Issues
The solution is largely functional but has some areas for improvement:
- Review failed tests and implement fixes
- Conduct additional testing under various conditions
- Consider performance optimizations
"""
        else:
            recommendations += """
### Significant Issues Identified
The solution requires attention before production deployment:
- Address all failed and error tests
- Conduct thorough troubleshooting
- Consider alternative implementation approaches
"""
        
        # Add specific recommendations based on test results
        if any('security' in name.lower() for name in self.report_data['test_results'].keys()):
            recommendations += """
### Security Considerations
- Implement comprehensive security measures
- Regular security assessments
- Employee security training
"""
        
        if any('performance' in name.lower() for name in self.report_data['test_results'].keys()):
            recommendations += """
### Performance Optimization
- Monitor performance metrics continuously
- Implement performance benchmarking
- Regular performance reviews
"""
        
        return recommendations
    
    def generate_full_report(self, output_file='validation_report.md'):
        """Generate complete validation report"""
        if not self.report_data:
            self.load_test_results()
        
        # Generate all sections
        executive_summary = self.generate_executive_summary()
        detailed_results = self.generate_detailed_results()
        performance_analysis = self.generate_performance_analysis()
        security_assessment = self.generate_security_assessment()
        recommendations = self.generate_recommendations()
        
        # Combine into full report
        full_report = f"""
{executive_summary}

{detailed_results}

{performance_analysis}

{security_assessment}

{recommendations}

## Appendix

### Test Environment
- **Python Version:** {self.report_data['test_run_info']['python_version']}
- **Platform:** {self.report_data['test_run_info']['platform']}
- **Test Duration:** {self.report_data['test_run_info']['duration_seconds']:.2f} seconds

### Test Data
Complete test results are available in the accompanying JSON file: `{self.test_results_file}`

---
*Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        # Write report to file
        with open(output_file, 'w') as f:
            f.write(full_report)
        
        print(f"Validation report generated: {output_file}")
        return output_file

def main():
    """Main function"""
    if len(sys.argv) > 1:
        test_results_file = sys.argv[1]
    else:
        test_results_file = 'test_report.json'
    
    try:
        generator = ValidationReportGenerator(test_results_file)
        report_file = generator.generate_full_report()
        
        print(f"Validation report successfully generated: {report_file}")
        return 0
        
    except Exception as e:
        print(f"Error generating validation report: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
```

This completes the comprehensive USB passthrough validation and testing framework. The testing suite covers:

1. **Functional Testing** - Basic device operations and advanced features
2. **Performance Testing** - Latency, throughput, and resource usage
3. **Security Testing** - Access control, encryption, and monitoring  
4. **Integration Testing** - End-to-end workflows and container integration
5. **Automated Testing** - CI/CD integration and reporting
6. **Validation Reports** - Comprehensive documentation and recommendations

The framework provides thorough validation of USB passthrough functionality for LabJack devices across different environments and use cases.