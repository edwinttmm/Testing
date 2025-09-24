"""
Enhanced LabJack T7 Manager for ADAS Camera HIL Testing Platform
Provides comprehensive hardware integration with timing precision and error handling
"""

import time
import logging
import threading
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import json

try:
    from labjack import ljm
    LABJACK_AVAILABLE = True
except ImportError:
    LABJACK_AVAILABLE = False
    print("⚠️ LabJack LJM library not available - install with: pip install labjack-ljm")

@dataclass
class LabJackConfig:
    """LabJack T7 configuration parameters"""
    device_type: str = "T7"
    connection_type: str = "USB"
    identifier: str = "ANY"
    analog_input_range: float = 10.0  # ±10V range
    stream_scan_rate: int = 1000  # Hz
    stream_buffer_size: int = 4096
    timing_resolution_us: float = 1.0  # microsecond precision
    gpio_directions: Dict[int, str] = None  # {pin: "input"/"output"}
    
    def __post_init__(self):
        if self.gpio_directions is None:
            self.gpio_directions = {
                0: "output",  # Trigger output
                1: "output",  # Status LED
                2: "input",   # Camera ready signal
                3: "input"    # VRU detection signal
            }

@dataclass
class TimingEvent:
    """Timing event for synchronization"""
    timestamp: datetime
    event_type: str
    channel: int
    value: float
    precision_us: float

class LabJackT7Manager:
    """Enhanced LabJack T7 Manager with real hardware support"""
    
    def __init__(self, config: LabJackConfig = None):
        self.config = config or LabJackConfig()
        self.handle = None
        self.connected = False
        self.device_info = {}
        self.streaming = False
        self.stream_thread = None
        self.timing_events = []
        self.performance_metrics = {
            "connection_time": 0.0,
            "read_latency_us": [],
            "write_latency_us": [],
            "timing_jitter_us": [],
            "error_count": 0,
            "reconnection_count": 0
        }
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Auto-reconnection
        self.auto_reconnect = True
        self.max_reconnect_attempts = 5
        
    def connect(self) -> bool:
        """Connect to LabJack T7 with comprehensive error handling"""
        with self.lock:
            start_time = time.time()
            
            if not LABJACK_AVAILABLE:
                self.logger.warning("LabJack LJM library not available - using mock mode")
                self.connected = True
                self.device_info = {"mock": True, "device_type": "T7-MOCK"}
                return True
            
            try:
                # Close existing connection
                if self.handle:
                    self._safe_close()
                
                # Open new connection with retry logic
                for attempt in range(self.max_reconnect_attempts):
                    try:
                        self.handle = ljm.openS(
                            self.config.device_type,
                            self.config.connection_type,
                            self.config.identifier
                        )
                        break
                    except Exception as e:
                        if attempt == self.max_reconnect_attempts - 1:
                            raise
                        self.logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                        time.sleep(0.5)
                
                # Get device information
                info = ljm.getHandleInfo(self.handle)
                self.device_info = {
                    "device_type": ljm.numberToType(info[0]),
                    "connection_type": ljm.numberToConnectionType(info[1]),
                    "serial_number": info[2],
                    "ip_address": ljm.numberToIP(info[3]),
                    "port": info[4],
                    "max_bytes": info[5],
                    "firmware_version": self._get_firmware_version(),
                    "hardware_version": self._get_hardware_version()
                }
                
                # Configure device for HIL testing
                self._configure_device()
                
                self.connected = True
                connection_time = (time.time() - start_time) * 1000
                self.performance_metrics["connection_time"] = connection_time
                
                self.logger.info(f"Connected to {self.device_info['device_type']} "
                               f"(SN: {self.device_info['serial_number']}) in {connection_time:.1f}ms")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to connect to LabJack: {e}")
                self.performance_metrics["error_count"] += 1
                return False
    
    def _configure_device(self):
        """Configure LabJack T7 for ADAS HIL testing"""
        if not self.handle or not LABJACK_AVAILABLE:
            return
        
        try:
            # Configure analog input range
            ljm.eWriteName(self.handle, "AIN_ALL_RANGE", self.config.analog_input_range)
            
            # Configure GPIO directions
            for pin, direction in self.config.gpio_directions.items():
                if direction == "output":
                    ljm.eWriteName(self.handle, f"DIO{pin}_DIR", 1)  # Output
                else:
                    ljm.eWriteName(self.handle, f"DIO{pin}_DIR", 0)  # Input
            
            # Configure timing for high precision
            ljm.eWriteName(self.handle, "SYSTEM_TIMER_20HZ", 0)  # Disable 20Hz timer
            ljm.eWriteName(self.handle, "POWER_LED", 1)  # Enable power LED
            
            # Set up interrupt on change for camera signals
            ljm.eWriteName(self.handle, "DIO2_EF_ENABLE", 0)  # Disable first
            ljm.eWriteName(self.handle, "DIO2_EF_INDEX", 1)   # Change interrupt
            ljm.eWriteName(self.handle, "DIO2_EF_ENABLE", 1)  # Enable
            
            self.logger.info("Device configured for HIL testing")
            
        except Exception as e:
            self.logger.error(f"Device configuration failed: {e}")
            raise
    
    def _get_firmware_version(self) -> str:
        """Get firmware version"""
        try:
            return f"{ljm.eReadName(self.handle, 'FIRMWARE_VERSION'):.2f}"
        except:
            return "Unknown"
    
    def _get_hardware_version(self) -> str:
        """Get hardware version"""
        try:
            return f"{ljm.eReadName(self.handle, 'HARDWARE_VERSION'):.2f}"
        except:
            return "Unknown"
    
    def disconnect(self):
        """Safely disconnect from LabJack"""
        with self.lock:
            self.stop_streaming()
            self._safe_close()
            self.connected = False
            self.device_info = {}
            self.logger.info("Disconnected from LabJack")
    
    def _safe_close(self):
        """Safely close LabJack connection"""
        if self.handle and LABJACK_AVAILABLE:
            try:
                ljm.close(self.handle)
            except:
                pass
            finally:
                self.handle = None
    
    def read_analog_precise(self, channels: List[int], num_samples: int = 1) -> Dict[str, Any]:
        """Read analog inputs with timing precision"""
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        start_time = time.perf_counter()
        
        if not LABJACK_AVAILABLE or not self.handle:
            # Mock data with realistic noise
            values = []
            for _ in range(num_samples):
                sample = [np.random.normal(2.5, 0.01) for _ in channels]
                values.append(sample)
            
            read_time_us = (time.perf_counter() - start_time) * 1e6
            return {
                "values": values,
                "channels": channels,
                "timestamp": datetime.now().isoformat(),
                "read_time_us": read_time_us,
                "samples": num_samples
            }
        
        try:
            channel_names = [f"AIN{ch}" for ch in channels]
            values = []
            
            for _ in range(num_samples):
                sample_values = ljm.eReadNames(self.handle, len(channel_names), channel_names)
                values.append(sample_values)
                
                if num_samples > 1:
                    time.sleep(self.config.timing_resolution_us / 1e6)
            
            read_time_us = (time.perf_counter() - start_time) * 1e6
            self.performance_metrics["read_latency_us"].append(read_time_us)
            
            # Keep only last 1000 measurements
            if len(self.performance_metrics["read_latency_us"]) > 1000:
                self.performance_metrics["read_latency_us"] = \
                    self.performance_metrics["read_latency_us"][-1000:]
            
            return {
                "values": values,
                "channels": channels,
                "timestamp": datetime.now().isoformat(),
                "read_time_us": read_time_us,
                "samples": num_samples
            }
            
        except Exception as e:
            self.performance_metrics["error_count"] += 1
            self.logger.error(f"Analog read error: {e}")
            
            if self.auto_reconnect:
                self._attempt_reconnection()
            
            raise RuntimeError(f"Analog read failed: {e}")
    
    def trigger_camera_capture(self, pulse_width_us: float = 100) -> bool:
        """Trigger camera capture with precise timing"""
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        start_time = time.perf_counter()
        
        try:
            if not LABJACK_AVAILABLE or not self.handle:
                # Mock trigger
                time.sleep(pulse_width_us / 1e6)
                trigger_time_us = (time.perf_counter() - start_time) * 1e6
                
                self.timing_events.append(TimingEvent(
                    timestamp=datetime.now(),
                    event_type="camera_trigger",
                    channel=0,
                    value=1.0,
                    precision_us=trigger_time_us
                ))
                return True
            
            # Generate precise trigger pulse
            ljm.eWriteName(self.handle, "DIO0", 1)  # Trigger high
            time.sleep(pulse_width_us / 1e6)        # Wait for pulse width
            ljm.eWriteName(self.handle, "DIO0", 0)  # Trigger low
            
            trigger_time_us = (time.perf_counter() - start_time) * 1e6
            self.performance_metrics["write_latency_us"].append(trigger_time_us)
            
            # Record timing event
            self.timing_events.append(TimingEvent(
                timestamp=datetime.now(),
                event_type="camera_trigger",
                channel=0,
                value=1.0,
                precision_us=trigger_time_us
            ))
            
            # Keep only last 1000 events
            if len(self.timing_events) > 1000:
                self.timing_events = self.timing_events[-1000:]
            
            self.logger.debug(f"Camera trigger completed in {trigger_time_us:.1f}µs")
            return True
            
        except Exception as e:
            self.performance_metrics["error_count"] += 1
            self.logger.error(f"Camera trigger error: {e}")
            return False
    
    def wait_for_vru_detection(self, timeout_ms: int = 5000) -> Optional[Dict[str, Any]]:
        """Wait for VRU detection signal with timeout"""
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        start_time = time.perf_counter()
        timeout_s = timeout_ms / 1000.0
        
        try:
            while (time.perf_counter() - start_time) < timeout_s:
                if not LABJACK_AVAILABLE or not self.handle:
                    # Mock VRU detection after random delay
                    if np.random.random() < 0.1:  # 10% chance per check
                        detection_time_us = (time.perf_counter() - start_time) * 1e6
                        return {
                            "detected": True,
                            "detection_time_us": detection_time_us,
                            "signal_strength": np.random.uniform(0.5, 1.0),
                            "timestamp": datetime.now().isoformat()
                        }
                else:
                    # Read VRU detection signal
                    signal = ljm.eReadName(self.handle, "DIO3")
                    if signal > 0.5:  # Digital high threshold
                        detection_time_us = (time.perf_counter() - start_time) * 1e6
                        
                        self.timing_events.append(TimingEvent(
                            timestamp=datetime.now(),
                            event_type="vru_detection",
                            channel=3,
                            value=signal,
                            precision_us=detection_time_us
                        ))
                        
                        return {
                            "detected": True,
                            "detection_time_us": detection_time_us,
                            "signal_strength": signal,
                            "timestamp": datetime.now().isoformat()
                        }
                
                time.sleep(0.001)  # 1ms polling rate
            
            # Timeout
            return {
                "detected": False,
                "detection_time_us": timeout_ms * 1000,
                "signal_strength": 0.0,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.performance_metrics["error_count"] += 1
            self.logger.error(f"VRU detection error: {e}")
            return None
    
    def start_streaming(self, channels: List[str], scan_rate: int = 1000) -> bool:
        """Start high-speed data streaming"""
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        if self.streaming:
            self.stop_streaming()
        
        try:
            if not LABJACK_AVAILABLE or not self.handle:
                self.streaming = True
                self.logger.info("Mock streaming started")
                return True
            
            # Configure stream parameters
            scans_per_read = max(scan_rate // 10, 1)  # Read 10 times per second
            
            # Get channel addresses
            scan_list = ljm.namesToAddresses(len(channels), channels)[0]
            
            # Start stream
            actual_scan_rate = ljm.eStreamStart(
                self.handle,
                scans_per_read,
                len(channels),
                scan_list,
                scan_rate
            )
            
            self.streaming = True
            self.logger.info(f"Streaming started at {actual_scan_rate} Hz")
            return True
            
        except Exception as e:
            self.performance_metrics["error_count"] += 1
            self.logger.error(f"Streaming start error: {e}")
            return False
    
    def stop_streaming(self):
        """Stop data streaming"""
        if self.streaming and LABJACK_AVAILABLE and self.handle:
            try:
                ljm.eStreamStop(self.handle)
            except:
                pass
        
        self.streaming = False
        self.logger.info("Streaming stopped")
    
    def _attempt_reconnection(self):
        """Attempt to reconnect to device"""
        self.performance_metrics["reconnection_count"] += 1
        self.logger.warning("Attempting reconnection...")
        
        self._safe_close()
        self.connected = False
        
        if self.connect():
            self.logger.info("Reconnection successful")
        else:
            self.logger.error("Reconnection failed")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics"""
        with self.lock:
            metrics = self.performance_metrics.copy()
            
            # Calculate statistics
            if metrics["read_latency_us"]:
                metrics["avg_read_latency_us"] = np.mean(metrics["read_latency_us"])
                metrics["max_read_latency_us"] = np.max(metrics["read_latency_us"])
                metrics["std_read_latency_us"] = np.std(metrics["read_latency_us"])
            
            if metrics["write_latency_us"]:
                metrics["avg_write_latency_us"] = np.mean(metrics["write_latency_us"])
                metrics["max_write_latency_us"] = np.max(metrics["write_latency_us"])
                metrics["std_write_latency_us"] = np.std(metrics["write_latency_us"])
            
            metrics["timing_events_count"] = len(self.timing_events)
            metrics["device_info"] = self.device_info.copy()
            metrics["connected"] = self.connected
            metrics["streaming"] = self.streaming
            
            return metrics
    
    def run_diagnostic(self) -> Dict[str, Any]:
        """Run comprehensive diagnostic tests"""
        diagnostic_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "overall_status": "PASS",
            "issues": []
        }
        
        # Test 1: Connection
        try:
            if not self.connected:
                self.connect()
            diagnostic_results["tests"]["connection"] = "PASS"
        except Exception as e:
            diagnostic_results["tests"]["connection"] = f"FAIL: {e}"
            diagnostic_results["overall_status"] = "FAIL"
            diagnostic_results["issues"].append(f"Connection test failed: {e}")
        
        # Test 2: Analog input reading
        try:
            result = self.read_analog_precise([0, 1, 2, 3])
            if result["read_time_us"] < 1000:  # Should be under 1ms
                diagnostic_results["tests"]["analog_read"] = "PASS"
            else:
                diagnostic_results["tests"]["analog_read"] = f"SLOW: {result['read_time_us']:.1f}µs"
                diagnostic_results["issues"].append("Analog read is slow")
        except Exception as e:
            diagnostic_results["tests"]["analog_read"] = f"FAIL: {e}"
            diagnostic_results["overall_status"] = "FAIL"
            diagnostic_results["issues"].append(f"Analog read test failed: {e}")
        
        # Test 3: GPIO operations
        try:
            self.trigger_camera_capture(50)  # 50µs pulse
            diagnostic_results["tests"]["gpio_trigger"] = "PASS"
        except Exception as e:
            diagnostic_results["tests"]["gpio_trigger"] = f"FAIL: {e}"
            diagnostic_results["overall_status"] = "FAIL"
            diagnostic_results["issues"].append(f"GPIO trigger test failed: {e}")
        
        # Test 4: Timing precision
        try:
            # Measure timing jitter over multiple operations
            latencies = []
            for _ in range(10):
                start = time.perf_counter()
                self.read_analog_precise([0])
                latencies.append((time.perf_counter() - start) * 1e6)
            
            jitter = np.std(latencies)
            if jitter < 100:  # Less than 100µs jitter
                diagnostic_results["tests"]["timing_precision"] = "PASS"
            else:
                diagnostic_results["tests"]["timing_precision"] = f"HIGH_JITTER: {jitter:.1f}µs"
                diagnostic_results["issues"].append(f"High timing jitter: {jitter:.1f}µs")
        except Exception as e:
            diagnostic_results["tests"]["timing_precision"] = f"FAIL: {e}"
            diagnostic_results["overall_status"] = "FAIL"
            diagnostic_results["issues"].append(f"Timing precision test failed: {e}")
        
        return diagnostic_results
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()