#!/usr/bin/env python3
"""
LabJack Hardware Validation Script
==================================

Comprehensive Python script for validating LabJack hardware connectivity,
communication protocols, and performance on Windows systems.

Requirements:
- LabJack LJM library installed
- Python 3.6+
- Administrator privileges (recommended)

Usage:
    python labjack-hardware-validator.py [options]
    
Options:
    --device-type TYPE    Specify device type (T4, T7, T8, ANY)
    --connection-type TYPE    Specify connection (USB, ETHERNET, WIFI, ANY)  
    --ip-address IP       IP address for Ethernet devices
    --verbose            Enable verbose output
    --export-results     Export results to JSON file
    --run-performance    Run performance benchmarks
    --test-streaming     Test streaming capabilities
    --output-file FILE    Output file for results (default: labjack_validation_results.json)
"""

import sys
import os
import time
import json
import statistics
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Add LabJack Python library path
LABJACK_PYTHON_PATH = r'C:\Program Files (x86)\LabJack\Applications\LJM\Python'
if os.path.exists(LABJACK_PYTHON_PATH):
    sys.path.insert(0, LABJACK_PYTHON_PATH)

try:
    from labjack import ljm
    LABJACK_AVAILABLE = True
except ImportError as e:
    LABJACK_AVAILABLE = False
    IMPORT_ERROR = str(e)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('labjack_validation.log')
    ]
)
logger = logging.getLogger(__name__)

class LabJackValidator:
    """Comprehensive LabJack hardware validation class."""
    
    def __init__(self, device_type="ANY", connection_type="ANY", ip_address=None, verbose=False):
        self.device_type = device_type
        self.connection_type = connection_type
        self.ip_address = ip_address
        self.verbose = verbose
        self.handle = None
        self.device_info = {}
        self.test_results = {
            'timestamp': datetime.now().isoformat(),
            'device_detection': False,
            'communication_test': False,
            'analog_input_test': False,
            'digital_io_test': False,
            'streaming_test': False,
            'performance_benchmark': {},
            'network_discovery': {},
            'error_handling_test': False,
            'device_info': {},
            'test_summary': {},
            'issues': [],
            'recommendations': []
        }
        
    def log(self, message: str, level: str = "INFO", emoji: str = "ℹ️"):
        """Enhanced logging with emojis and colors."""
        formatted_message = f"{emoji} {message}"
        
        if level == "SUCCESS":
            print(f"\033[92m{formatted_message}\033[0m")  # Green
            logger.info(message)
        elif level == "ERROR":
            print(f"\033[91m{formatted_message}\033[0m")  # Red
            logger.error(message)
            self.test_results['issues'].append(message)
        elif level == "WARNING":
            print(f"\033[93m{formatted_message}\033[0m")  # Yellow
            logger.warning(message)
        elif level == "INFO":
            print(f"\033[94m{formatted_message}\033[0m")  # Blue
            logger.info(message)
        else:
            print(formatted_message)
            logger.info(message)
    
    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met."""
        self.log("Checking prerequisites...", "INFO", "🔍")
        
        if not LABJACK_AVAILABLE:
            self.log(f"LabJack LJM library not available: {IMPORT_ERROR}", "ERROR", "❌")
            self.test_results['issues'].append("LabJack LJM Python library not installed")
            self.test_results['recommendations'].append("Install LabJack software bundle from https://labjack.com/support/software")
            return False
        
        # Check if LJM library is accessible
        try:
            ljm_version = ljm.constants.LJM_LIBRARY_VERSION
            self.log(f"LJM Library version: {ljm_version}", "SUCCESS", "✅")
            return True
        except Exception as e:
            self.log(f"LJM library check failed: {e}", "ERROR", "❌")
            return False
    
    def discover_network_devices(self) -> List[Dict]:
        """Discover LabJack devices on the network."""
        self.log("Discovering network devices...", "INFO", "🌐")
        discovered_devices = []
        
        try:
            # Use LJM to discover devices
            num_found, devices_info = ljm.listAll(ljm.constants.dtANY, ljm.constants.ctNETWORK)
            
            for i in range(num_found):
                device_type = devices_info[0][i]
                connection_type = devices_info[1][i]
                serial_number = devices_info[2][i]
                ip_address = devices_info[3][i]
                
                device_info = {
                    'device_type': ljm.numberToDeviceType(device_type),
                    'connection_type': ljm.numberToConnectionType(connection_type),
                    'serial_number': serial_number,
                    'ip_address': ljm.numberToIP(ip_address) if ip_address != 0 else "Unknown"
                }
                
                discovered_devices.append(device_info)
                self.log(f"Found: {device_info['device_type']} at {device_info['ip_address']}", "SUCCESS", "🎯")
                
            if num_found == 0:
                self.log("No network devices discovered", "WARNING", "⚠️")
                
        except Exception as e:
            self.log(f"Network discovery failed: {e}", "ERROR", "❌")
        
        self.test_results['network_discovery'] = {
            'devices_found': len(discovered_devices),
            'devices': discovered_devices
        }
        
        return discovered_devices
    
    def test_device_detection(self) -> bool:
        """Test device detection and connection."""
        self.log("Testing device detection...", "INFO", "🔍")
        
        try:
            # Try to open device with specified parameters
            if self.ip_address:
                identifier = self.ip_address
            else:
                identifier = "ANY"
                
            self.handle = ljm.openS(self.device_type, self.connection_type, identifier)
            
            # Get device information
            info = ljm.getHandleInfo(self.handle)
            device_type_num = info[0]
            connection_type_num = info[1]
            serial_number = info[2]
            
            self.device_info = {
                'device_type': ljm.numberToDeviceType(device_type_num),
                'connection_type': ljm.numberToConnectionType(connection_type_num),
                'serial_number': serial_number,
                'device_type_num': device_type_num,
                'connection_type_num': connection_type_num
            }
            
            self.test_results['device_info'] = self.device_info
            
            self.log(f"Device detected: {self.device_info['device_type']}", "SUCCESS", "✅")
            self.log(f"Connection: {self.device_info['connection_type']}", "INFO", "🔌")
            self.log(f"Serial Number: {self.device_info['serial_number']}", "INFO", "🏷️")
            
            self.test_results['device_detection'] = True
            return True
            
        except ljm.LJMError as e:
            error_msg = f"Device detection failed: {e.errorCode} - {e.errorString}"
            self.log(error_msg, "ERROR", "❌")
            
            # Provide specific recommendations based on error code
            if e.errorCode == ljm.constants.LJME_NO_DEVICES_FOUND:
                self.test_results['recommendations'].extend([
                    "Check USB/Ethernet connection",
                    "Ensure device is powered on",
                    "Try different USB port or cable",
                    "Check Device Manager for driver issues"
                ])
            elif e.errorCode == ljm.constants.LJME_CANNOT_OPEN_DEVICE:
                self.test_results['recommendations'].extend([
                    "Device may be in use by another application",
                    "Try closing Kipling or other LabJack software",
                    "Restart the device"
                ])
            
            return False
        except Exception as e:
            self.log(f"Unexpected error in device detection: {e}", "ERROR", "❌")
            return False
    
    def test_basic_communication(self) -> bool:
        """Test basic communication with the device."""
        if not self.handle:
            self.log("No device handle available for communication test", "ERROR", "❌")
            return False
        
        self.log("Testing basic communication...", "INFO", "💬")
        
        try:
            # Read device name
            device_name = ljm.eReadNameString(self.handle, "DEVICE_NAME_DEFAULT")
            self.log(f"Device name: {device_name}", "SUCCESS", "✅")
            
            # Read firmware version
            firmware_version = ljm.eReadName(self.handle, "FIRMWARE_VERSION")
            self.log(f"Firmware version: {firmware_version}", "INFO", "🔧")
            
            # Read hardware version
            try:
                hardware_version = ljm.eReadName(self.handle, "HARDWARE_VERSION")
                self.log(f"Hardware version: {hardware_version}", "INFO", "⚙️")
            except:
                pass  # Not all devices support this
            
            # Read bootloader version
            try:
                bootloader_version = ljm.eReadName(self.handle, "BOOTLOADER_VERSION")
                self.log(f"Bootloader version: {bootloader_version}", "INFO", "🚀")
            except:
                pass  # Not all devices support this
            
            self.test_results['communication_test'] = True
            return True
            
        except ljm.LJMError as e:
            self.log(f"Communication test failed: {e.errorCode} - {e.errorString}", "ERROR", "❌")
            return False
        except Exception as e:
            self.log(f"Communication test failed: {e}", "ERROR", "❌")
            return False
    
    def test_analog_inputs(self) -> bool:
        """Test analog input functionality."""
        if not self.handle:
            self.log("No device handle available for analog input test", "ERROR", "❌")
            return False
        
        self.log("Testing analog inputs...", "INFO", "📊")
        
        try:
            # Test multiple analog inputs
            analog_channels = ["AIN0", "AIN1", "AIN2", "AIN3"]
            readings = {}
            
            for channel in analog_channels:
                try:
                    voltage = ljm.eReadName(self.handle, channel)
                    readings[channel] = voltage
                    self.log(f"{channel}: {voltage:.4f}V", "INFO", "📈")
                except ljm.LJMError as e:
                    if e.errorCode != ljm.constants.LJME_INVALID_ADDRESS:
                        self.log(f"Error reading {channel}: {e.errorString}", "WARNING", "⚠️")
                
            if not readings:
                self.log("No analog inputs could be read", "ERROR", "❌")
                return False
            
            # Test analog input stability (multiple readings)
            test_channel = list(readings.keys())[0]
            stability_readings = []
            
            for i in range(10):
                voltage = ljm.eReadName(self.handle, test_channel)
                stability_readings.append(voltage)
                time.sleep(0.01)  # 10ms between readings
            
            avg_voltage = statistics.mean(stability_readings)
            voltage_std = statistics.stdev(stability_readings) if len(stability_readings) > 1 else 0
            
            self.log(f"Stability test ({test_channel}):", "INFO", "🎯")
            self.log(f"  Average: {avg_voltage:.6f}V", "INFO", "📊")
            self.log(f"  Std Dev: {voltage_std:.6f}V", "INFO", "📈")
            
            # Check for reasonable stability (less than 100mV standard deviation)
            if voltage_std < 0.1:
                self.log("Analog input stability: GOOD", "SUCCESS", "✅")
            else:
                self.log("Analog input stability: POOR (high noise)", "WARNING", "⚠️")
                self.test_results['recommendations'].append("Check for electrical interference or grounding issues")
            
            self.test_results['analog_input_test'] = {
                'success': True,
                'channels_tested': list(readings.keys()),
                'readings': readings,
                'stability': {
                    'channel': test_channel,
                    'average': avg_voltage,
                    'std_dev': voltage_std,
                    'samples': len(stability_readings)
                }
            }
            
            return True
            
        except ljm.LJMError as e:
            self.log(f"Analog input test failed: {e.errorCode} - {e.errorString}", "ERROR", "❌")
            return False
        except Exception as e:
            self.log(f"Analog input test failed: {e}", "ERROR", "❌")
            return False
    
    def test_digital_io(self) -> bool:
        """Test digital I/O functionality."""
        if not self.handle:
            self.log("No device handle available for digital I/O test", "ERROR", "❌")
            return False
        
        self.log("Testing digital I/O...", "INFO", "🔌")
        
        try:
            # Test digital output on FIO0
            test_pin = "FIO0"
            
            # Configure as output
            ljm.eWriteName(self.handle, f"{test_pin}_EF_ENABLE", 0)  # Disable extended features
            
            # Test setting high
            ljm.eWriteName(self.handle, test_pin, 1)
            state_high = ljm.eReadName(self.handle, test_pin)
            
            # Test setting low  
            ljm.eWriteName(self.handle, test_pin, 0)
            state_low = ljm.eReadName(self.handle, test_pin)
            
            self.log(f"Digital output test ({test_pin}):", "INFO", "🔌")
            self.log(f"  Set HIGH, read: {state_high}", "INFO", "⬆️")
            self.log(f"  Set LOW, read: {state_low}", "INFO", "⬇️")
            
            if state_high == 1 and state_low == 0:
                self.log("Digital I/O test: PASSED", "SUCCESS", "✅")
                success = True
            else:
                self.log("Digital I/O test: FAILED (unexpected states)", "ERROR", "❌")
                success = False
            
            # Test multiple pins if possible
            digital_pins = ["FIO1", "FIO2", "FIO3"]
            pin_results = {}
            
            for pin in digital_pins:
                try:
                    ljm.eWriteName(self.handle, f"{pin}_EF_ENABLE", 0)
                    ljm.eWriteName(self.handle, pin, 1)
                    high_state = ljm.eReadName(self.handle, pin)
                    ljm.eWriteName(self.handle, pin, 0)
                    low_state = ljm.eReadName(self.handle, pin)
                    
                    pin_results[pin] = {
                        'high_state': high_state,
                        'low_state': low_state,
                        'working': high_state == 1 and low_state == 0
                    }
                    
                except ljm.LJMError:
                    pin_results[pin] = {'error': 'Cannot access pin'}
            
            self.test_results['digital_io_test'] = {
                'success': success,
                'primary_pin': test_pin,
                'primary_result': {
                    'high_state': state_high,
                    'low_state': state_low
                },
                'additional_pins': pin_results
            }
            
            return success
            
        except ljm.LJMError as e:
            self.log(f"Digital I/O test failed: {e.errorCode} - {e.errorString}", "ERROR", "❌")
            return False
        except Exception as e:
            self.log(f"Digital I/O test failed: {e}", "ERROR", "❌")
            return False
    
    def test_streaming_capability(self) -> bool:
        """Test high-speed streaming capability."""
        if not self.handle:
            self.log("No device handle available for streaming test", "ERROR", "❌")
            return False
        
        self.log("Testing streaming capability...", "INFO", "🚀")
        
        try:
            # Configure streaming parameters
            scan_rate = 1000  # Hz
            scans_per_read = 100
            
            # Configure channels to stream
            channel_names = ["AIN0", "AIN1"]
            num_addresses = len(channel_names)
            channel_addresses = ljm.namesToAddresses(num_addresses, channel_names)[0]
            
            self.log(f"Streaming config:", "INFO", "⚙️")
            self.log(f"  Channels: {channel_names}", "INFO", "📊")
            self.log(f"  Scan rate: {scan_rate} Hz", "INFO", "⚡")
            self.log(f"  Scans per read: {scans_per_read}", "INFO", "📈")
            
            # Start stream
            start_time = time.time()
            actual_scan_rate = ljm.eStreamStart(self.handle, scans_per_read, num_addresses, channel_addresses, scan_rate)
            
            self.log(f"Stream started. Actual rate: {actual_scan_rate} Hz", "SUCCESS", "✅")
            
            # Read stream data multiple times
            read_count = 5
            total_samples = 0
            read_times = []
            
            for i in range(read_count):
                read_start = time.time()
                ret = ljm.eStreamRead(self.handle, scans_per_read, num_addresses)
                read_end = time.time()
                
                read_time = read_end - read_start
                read_times.append(read_time)
                samples_in_read = len(ret[0])
                total_samples += samples_in_read
                
                self.log(f"Read {i+1}: {samples_in_read} samples in {read_time:.3f}s", "INFO", "📊")
            
            # Stop stream
            ljm.eStreamStop(self.handle)
            total_time = time.time() - start_time
            
            # Calculate performance metrics
            avg_read_time = statistics.mean(read_times)
            samples_per_second = total_samples / total_time
            effective_rate = total_samples / (read_count * scans_per_read) * actual_scan_rate
            
            self.log("Streaming performance:", "SUCCESS", "🎯")
            self.log(f"  Total samples: {total_samples}", "INFO", "📊")
            self.log(f"  Total time: {total_time:.3f}s", "INFO", "⏱️")
            self.log(f"  Avg samples/sec: {samples_per_second:.0f}", "INFO", "⚡")
            self.log(f"  Effective rate: {effective_rate:.1f} Hz", "INFO", "📈")
            
            # Check for missed scans or errors
            try:
                missed_scans = ljm.eReadName(self.handle, "STREAM_NUM_SCANS_MISSED")
                if missed_scans > 0:
                    self.log(f"Warning: {missed_scans} scans were missed", "WARNING", "⚠️")
                    self.test_results['recommendations'].append("Reduce scan rate or scans per read to avoid missed data")
                else:
                    self.log("No missed scans detected", "SUCCESS", "✅")
            except:
                pass  # Not all devices support this register
            
            self.test_results['streaming_test'] = {
                'success': True,
                'configured_rate': scan_rate,
                'actual_rate': actual_scan_rate,
                'effective_rate': effective_rate,
                'total_samples': total_samples,
                'total_time': total_time,
                'avg_read_time': avg_read_time,
                'samples_per_second': samples_per_second,
                'channels': channel_names
            }
            
            return True
            
        except ljm.LJMError as e:
            self.log(f"Streaming test failed: {e.errorCode} - {e.errorString}", "ERROR", "❌")
            
            # Provide recommendations based on error
            if e.errorCode == ljm.constants.LJME_CANNOT_START_STREAM:
                self.test_results['recommendations'].append("Try reducing scan rate or number of channels")
            
            return False
        except Exception as e:
            self.log(f"Streaming test failed: {e}", "ERROR", "❌")
            return False
    
    def run_performance_benchmark(self) -> Dict:
        """Run comprehensive performance benchmarks."""
        if not self.handle:
            self.log("No device handle available for performance benchmark", "ERROR", "❌")
            return {}
        
        self.log("Running performance benchmark...", "INFO", "⚡")
        
        benchmark_results = {}
        
        try:
            # Single read benchmark
            self.log("Testing single read performance...", "INFO", "📊")
            single_read_count = 1000
            start_time = time.time()
            
            for i in range(single_read_count):
                ljm.eReadName(self.handle, "AIN0")
            
            single_read_time = time.time() - start_time
            single_read_rate = single_read_count / single_read_time
            
            self.log(f"Single reads: {single_read_rate:.0f} reads/sec", "SUCCESS", "⚡")
            
            # Batch read benchmark
            self.log("Testing batch read performance...", "INFO", "📊")
            addresses = [0, 2, 4, 6]  # AIN0, AIN1, AIN2, AIN3
            batch_count = 250
            start_time = time.time()
            
            for i in range(batch_count):
                ljm.eReadAddresses(self.handle, len(addresses), addresses)
            
            batch_read_time = time.time() - start_time
            values_per_second = (batch_count * len(addresses)) / batch_read_time
            
            self.log(f"Batch reads: {values_per_second:.0f} values/sec", "SUCCESS", "⚡")
            
            # Write performance test
            self.log("Testing write performance...", "INFO", "📊")
            write_count = 1000
            start_time = time.time()
            
            for i in range(write_count):
                ljm.eWriteName(self.handle, "DAC0", i % 2)  # Alternate between 0 and 1
            
            write_time = time.time() - start_time
            write_rate = write_count / write_time
            
            self.log(f"Writes: {write_rate:.0f} writes/sec", "SUCCESS", "⚡")
            
            # Latency test
            self.log("Testing latency...", "INFO", "📊")
            latencies = []
            
            for i in range(100):
                start_time = time.perf_counter()
                ljm.eReadName(self.handle, "AIN0")
                end_time = time.perf_counter()
                latencies.append((end_time - start_time) * 1000)  # Convert to ms
            
            avg_latency = statistics.mean(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            
            self.log(f"Latency - Avg: {avg_latency:.2f}ms, Min: {min_latency:.2f}ms, Max: {max_latency:.2f}ms", "SUCCESS", "⏱️")
            
            benchmark_results = {
                'single_read_rate': single_read_rate,
                'single_read_time': single_read_time,
                'batch_read_rate': values_per_second,
                'batch_read_time': batch_read_time,
                'write_rate': write_rate,
                'write_time': write_time,
                'latency': {
                    'average_ms': avg_latency,
                    'minimum_ms': min_latency,
                    'maximum_ms': max_latency,
                    'samples': len(latencies)
                }
            }
            
            self.test_results['performance_benchmark'] = benchmark_results
            
        except ljm.LJMError as e:
            self.log(f"Performance benchmark failed: {e.errorCode} - {e.errorString}", "ERROR", "❌")
        except Exception as e:
            self.log(f"Performance benchmark failed: {e}", "ERROR", "❌")
        
        return benchmark_results
    
    def test_error_handling(self) -> bool:
        """Test error handling and recovery."""
        if not self.handle:
            self.log("No device handle available for error handling test", "ERROR", "❌")
            return False
        
        self.log("Testing error handling...", "INFO", "🧪")
        
        try:
            # Test invalid address read
            try:
                ljm.eReadName(self.handle, "INVALID_ADDRESS_123456")
                self.log("Error: Invalid address should have failed", "ERROR", "❌")
                return False
            except ljm.LJMError as e:
                if e.errorCode == ljm.constants.LJME_INVALID_ADDRESS:
                    self.log("✓ Invalid address properly rejected", "SUCCESS", "✅")
                else:
                    self.log(f"Unexpected error for invalid address: {e.errorString}", "WARNING", "⚠️")
            
            # Test invalid value write
            try:
                ljm.eWriteName(self.handle, "DAC0", 999999)  # Way out of range
                self.log("Warning: Out-of-range value was accepted", "WARNING", "⚠️")
            except ljm.LJMError as e:
                self.log("✓ Out-of-range value properly rejected", "SUCCESS", "✅")
            
            # Test communication recovery
            # This is more difficult to test without actually disconnecting the device
            
            self.test_results['error_handling_test'] = True
            return True
            
        except Exception as e:
            self.log(f"Error handling test failed: {e}", "ERROR", "❌")
            return False
    
    def run_full_validation(self) -> Dict:
        """Run complete hardware validation suite."""
        self.log("🚀 Starting LabJack Hardware Validation", "SUCCESS")
        self.log(f"Target device: {self.device_type} via {self.connection_type}", "INFO", "🎯")
        
        # Check prerequisites
        if not self.check_prerequisites():
            self.log("Prerequisites not met, aborting validation", "ERROR", "❌")
            return self.test_results
        
        # Network discovery (if applicable)
        if self.connection_type in ["ETHERNET", "WIFI", "ANY"]:
            self.discover_network_devices()
        
        # Device detection
        if not self.test_device_detection():
            self.log("Device detection failed, aborting remaining tests", "ERROR", "❌")
            self.test_results['recommendations'].extend([
                "Check device connection and power",
                "Verify drivers are installed correctly",
                "Try different connection method (USB vs Ethernet)"
            ])
            return self.test_results
        
        # Basic communication
        if not self.test_basic_communication():
            self.log("Basic communication failed, aborting remaining tests", "ERROR", "❌")
            return self.test_results
        
        # Analog inputs
        self.test_analog_inputs()
        
        # Digital I/O
        self.test_digital_io()
        
        # Streaming capability
        self.test_streaming_capability()
        
        # Performance benchmark
        if self.verbose:
            self.run_performance_benchmark()
        
        # Error handling
        self.test_error_handling()
        
        # Generate summary
        self._generate_test_summary()
        
        # Cleanup
        if self.handle:
            ljm.close(self.handle)
            self.log("Device connection closed", "INFO", "🔒")
        
        return self.test_results
    
    def _generate_test_summary(self):
        """Generate comprehensive test summary."""
        tests_passed = sum([
            self.test_results['device_detection'],
            self.test_results['communication_test'],
            self.test_results['analog_input_test'] and isinstance(self.test_results['analog_input_test'], dict),
            self.test_results['digital_io_test'] and isinstance(self.test_results['digital_io_test'], dict),
            self.test_results['streaming_test'] and isinstance(self.test_results['streaming_test'], dict),
            self.test_results['error_handling_test']
        ])
        
        total_tests = 6
        success_rate = (tests_passed / total_tests) * 100
        
        self.test_results['test_summary'] = {
            'tests_passed': tests_passed,
            'total_tests': total_tests,
            'success_rate': success_rate,
            'overall_status': 'PASS' if tests_passed == total_tests else 'PARTIAL' if tests_passed > 0 else 'FAIL'
        }
        
        self.log("🎯 Validation Complete", "SUCCESS")
        self.log(f"Tests passed: {tests_passed}/{total_tests} ({success_rate:.1f}%)", "INFO", "📊")
        
        if tests_passed == total_tests:
            self.log("🎉 All tests PASSED! Device is working correctly.", "SUCCESS")
        elif tests_passed > 0:
            self.log("⚠️ Some tests FAILED. Check results for details.", "WARNING")
        else:
            self.log("❌ All tests FAILED. Device has serious issues.", "ERROR")
    
    def export_results(self, filename: str):
        """Export validation results to JSON file."""
        try:
            with open(filename, 'w') as f:
                json.dump(self.test_results, f, indent=2, default=str)
            self.log(f"Results exported to: {filename}", "SUCCESS", "💾")
        except Exception as e:
            self.log(f"Failed to export results: {e}", "ERROR", "❌")

def main():
    """Main entry point for the validation script."""
    parser = argparse.ArgumentParser(description='LabJack Hardware Validation Tool')
    parser.add_argument('--device-type', default='ANY', choices=['T4', 'T7', 'T8', 'U3', 'U6', 'ANY'],
                       help='LabJack device type to test')
    parser.add_argument('--connection-type', default='ANY', choices=['USB', 'ETHERNET', 'WIFI', 'ANY'],
                       help='Connection type to use')
    parser.add_argument('--ip-address', help='IP address for Ethernet devices')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--export-results', action='store_true', help='Export results to JSON')
    parser.add_argument('--output-file', default='labjack_validation_results.json',
                       help='Output file for results')
    
    args = parser.parse_args()
    
    # Create validator
    validator = LabJackValidator(
        device_type=args.device_type,
        connection_type=args.connection_type,
        ip_address=args.ip_address,
        verbose=args.verbose
    )
    
    # Run validation
    results = validator.run_full_validation()
    
    # Export results if requested
    if args.export_results:
        validator.export_results(args.output_file)
    
    # Return appropriate exit code
    if results['test_summary'].get('overall_status') == 'PASS':
        return 0
    elif results['test_summary'].get('overall_status') == 'PARTIAL':
        return 1
    else:
        return 2

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n❌ Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)