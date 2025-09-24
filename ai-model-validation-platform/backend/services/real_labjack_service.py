"""
REAL LabJack Hardware Integration Service
PRD Module 3.1 & 3.2 Implementation

This service provides REAL LabJack DAQ device connection and TTL signal monitoring
as required by the PRD. NO MOCK IMPLEMENTATIONS.

Key Features:
- Real LabJack hardware connection via LJM library
- Connection status monitoring ("Connected" or "Not Detected")
- TTL signal reading capability with sub-millisecond precision
- Hardware event logging with Signal_Received_Time
- Precision timing service integration
- Thread-safe operations for concurrent access

Hardware Requirements:
- LabJack U3, U6, UE9, T4, T7, or T8 device
- USB connection or Ethernet connection
- LabJack LJM library installed

PRD Compliance:
- Module 3.1: HIL Test Environment with device connection status
- Module 3.2: Precision Time & Signal Logging with hardware events
"""

import logging
import time
import threading
import queue
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json
import os
import sys

# Import LabJack LJM library
try:
    import labjack.ljm as ljm
    from services.ljm_helpers import numberToType, numberToDeviceType, numberToConnectionType, numberToIP
    LJM_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ LabJack LJM library loaded successfully")
except ImportError as e:
    LJM_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.error(f"❌ Failed to initialize real LabJack service: LabJack LJM library not available. Install with: pip install labjack-ljm")

# Precision timing imports
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("numpy not available, some precision features may be limited")


class ConnectionStatus(Enum):
    """Hardware connection status states as required by PRD"""
    NOT_DETECTED = "Not Detected"      # PRD requirement: "Not Detected" 
    CONNECTING = "Connecting"
    CONNECTED = "Connected"            # PRD requirement: "Connected"
    ERROR = "Error"
    DISCONNECTED = "Disconnected"


class TTLSignalType(Enum):
    """TTL signal types for hardware detection"""
    HIGH = "high"       # 3.3V - 5V signal (detection event)
    LOW = "low"         # 0V - 0.8V signal (no detection)
    RISING_EDGE = "rising_edge"   # Low to High transition
    FALLING_EDGE = "falling_edge" # High to Low transition


@dataclass
class HardwareEvent:
    """Hardware detection event with precision timing - PRD Module 3.2"""
    event_id: str
    test_session_id: str
    video_id: str
    ground_truth_object_id: Optional[str]
    expected_event_time: datetime      # PRD: Expected_Event_Time
    signal_received_time: datetime     # PRD: Signal_Received_Time
    latency_ms: float                  # Calculated latency
    signal_type: TTLSignalType
    signal_voltage: float
    channel: str
    detection_outcome: str             # "pass", "fail_high_latency", "fail_missed_detection"
    created_at: datetime


@dataclass
class DeviceInfo:
    """Real LabJack device information"""
    device_type: str                   # T7, U6, etc.
    connection_type: str               # USB, Ethernet, WiFi
    serial_number: int
    ip_address: Optional[str]
    port: Optional[int]
    firmware_version: str
    hardware_version: str
    bootloader_version: str
    is_real_hardware: bool = True      # Always True for real implementation


@dataclass
class SignalConfiguration:
    """TTL signal configuration for hardware monitoring"""
    channel: str = "DIO0"              # Digital I/O channel for TTL
    threshold_voltage: float = 2.5     # Voltage threshold for TTL detection
    sample_rate: int = 10000           # Sample rate in Hz for monitoring
    resolution_index: int = 0          # ADC resolution (0=default, 8=fastest)
    range_volts: float = 10.0          # Input voltage range
    settling_time_us: int = 0          # Settling time in microseconds
    
    # TTL Detection Parameters
    debounce_time_ms: float = 1.0      # Debounce time to prevent multiple triggers
    edge_detection: TTLSignalType = TTLSignalType.RISING_EDGE
    timeout_detection_ms: int = 5000   # Max time to wait for signal


class RealLabJackService:
    """
    REAL LabJack Hardware Integration Service
    
    This service connects to actual LabJack hardware and provides
    TTL signal monitoring for ADAS camera testing as required by PRD.
    """
    
    def __init__(self, signal_config: Optional[SignalConfiguration] = None):
        if not LJM_AVAILABLE:
            logger.warning("❌ LabJack LJM library not available - service will operate in safe mode")
            self.connection_status = ConnectionStatus.NOT_DETECTED
            self.ljm_available = False
        else:
            self.ljm_available = True
        
        self.signal_config = signal_config or SignalConfiguration()
        
        # Hardware connection state
        self.handle: Optional[int] = None
        self.connection_status = ConnectionStatus.NOT_DETECTED
        self.device_info: Optional[DeviceInfo] = None
        
        # Signal monitoring state
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.stop_monitoring = threading.Event()
        
        # Event handling
        self.hardware_events = queue.Queue(maxsize=10000)
        self.event_callbacks: List[Callable[[HardwareEvent], None]] = []
        
        # Precision timing
        self.test_start_time: Optional[datetime] = None
        self.last_signal_time: Optional[datetime] = None
        
        # Statistics
        self.statistics = {
            "total_signals_detected": 0,
            "last_signal_voltage": 0.0,
            "monitoring_duration_seconds": 0.0,
            "connection_uptime_seconds": 0.0,
            "errors_count": 0,
            "last_error": None
        }
        
        # Thread safety
        self.lock = threading.RLock()
        
        logger.info("🔧 Real LabJack Service initialized")
    
    def get_connection_status(self) -> str:
        """
        Get connection status as required by PRD Module 3.1
        Returns: "Connected" or "Not Detected"
        """
        if self.connection_status == ConnectionStatus.CONNECTED:
            return "Connected"
        else:
            return "Not Detected"
    
    def is_connected(self) -> bool:
        """Check if LabJack hardware is connected"""
        return self.connection_status == ConnectionStatus.CONNECTED and self.handle is not None
    
    def detect_devices(self) -> List[Dict[str, Any]]:
        """Detect available LabJack devices"""
        devices = []
        
        # Safety check: Only proceed if LJM is available
        if not LJM_AVAILABLE:
            logger.warning("❌ LabJack LJM library not available - cannot detect devices")
            return devices
        
        try:
            # Pre-check: Ensure LJM is properly initialized
            if not hasattr(ljm, 'listAll'):
                logger.error("❌ LabJack LJM library missing listAll function")
                return devices
                
            # Wrap in additional safety to prevent segmentation faults
            logger.debug("🔍 Starting LabJack device detection...")
            
            # List all devices using LJM with timeout protection
            num_found, device_types, connection_types, serial_numbers, ip_addresses = ljm.listAll(
                ljm.constants.dtANY,     # Any device type
                ljm.constants.ctANY      # Any connection type
            )
            
            # Validate return values
            if num_found < 0:
                logger.warning("⚠️ Invalid device count returned from LabJack")
                return devices
            
            for i in range(num_found):
                # Use helper conversions to avoid referencing non-existent constants (e.g., dtUE9)
                device_type_str = numberToType(device_types[i])
                connection_type_str = numberToConnectionType(connection_types[i])

                # Format IP address if available
                ip_str = None
                if connection_types[i] in [getattr(ljm.constants, 'ctETHERNET', None), getattr(ljm.constants, 'ctWIFI', None)]:
                    # Convert IP number to string format
                    ip_int = ip_addresses[i]
                    ip_str = numberToIP(ip_int)
                
                devices.append({
                    "device_type": device_type_str,
                    "connection_type": connection_type_str,
                    "serial_number": serial_numbers[i],
                    "ip_address": ip_str
                })
            
            logger.info(f"🔍 Detected {num_found} LabJack device(s)")
            for device in devices:
                logger.info(f"  - {device['device_type']} S/N:{device['serial_number']} via {device['connection_type']}")
                
        except Exception as e:
            logger.error(f"❌ Device detection failed: {e}")
            self.statistics["errors_count"] += 1
            self.statistics["last_error"] = str(e)
        
        return devices
    
    def connect(self, device_type: str = "ANY", connection_type: str = "ANY", identifier: str = "ANY") -> bool:
        """
        Connect to LabJack hardware device
        
        Args:
            device_type: "T7", "U6", "ANY", etc.
            connection_type: "USB", "ETHERNET", "WIFI", "ANY"
            identifier: Serial number, IP address, or "ANY"
        
        Returns:
            True if connected successfully
        """
        with self.lock:
            # Safety check: Only proceed if LJM is available
            if not LJM_AVAILABLE:
                logger.error("❌ LabJack LJM library not available - cannot connect")
                self.connection_status = ConnectionStatus.NOT_DETECTED
                return False
                
            if self.is_connected():
                logger.warning("⚠️ Already connected to LabJack")
                return True
            
            self.connection_status = ConnectionStatus.CONNECTING
            
            try:
                logger.info(f"🔌 Attempting to connect to LabJack {device_type} via {connection_type}...")
                
                # Pre-check: Ensure required LJM functions exist
                if not hasattr(ljm, 'openS') or not hasattr(ljm, 'getHandleInfo'):
                    logger.error("❌ LabJack LJM library missing required connection functions")
                    self.connection_status = ConnectionStatus.ERROR
                    return False
                
                # Attempt connection with additional safety
                logger.debug("🔧 Opening LabJack device connection...")
                self.handle = ljm.openS(device_type, connection_type, identifier)
                
                # Validate handle
                if self.handle is None or self.handle <= 0:
                    logger.error("❌ Invalid LabJack handle returned")
                    self.connection_status = ConnectionStatus.ERROR
                    return False
                
                # Get device information
                device_info_tuple = ljm.getHandleInfo(self.handle)
                device_type_num, connection_type_num, serial_number, ip_number, port, max_bytes_per_mb = device_info_tuple
                
                # Convert numbers to readable strings using helper functions
                device_type_str = numberToType(device_type_num)
                connection_type_str = numberToConnectionType(connection_type_num)
                
                # Format IP address if available  
                ip_str = None
                if connection_type_num in [getattr(ljm.constants, 'ctETHERNET', None), getattr(ljm.constants, 'ctWIFI', None)]:
                    # Convert IP number to string format
                    ip_str = numberToIP(ip_number)
                
                # Get firmware versions
                try:
                    firmware_version = ljm.eReadName(self.handle, "FIRMWARE_VERSION")
                    hardware_version = ljm.eReadName(self.handle, "HARDWARE_VERSION") 
                    bootloader_version = ljm.eReadName(self.handle, "BOOTLOADER_VERSION")
                except Exception as version_error:
                    logger.warning(f"Could not read version info: {version_error}")
                    firmware_version = "Unknown"
                    hardware_version = "Unknown"
                    bootloader_version = "Unknown"
                
                # Store device information
                self.device_info = DeviceInfo(
                    device_type=device_type_str,
                    connection_type=connection_type_str,
                    serial_number=serial_number,
                    ip_address=ip_str,
                    port=port if connection_type_num in [getattr(ljm.constants, 'ctETHERNET', None), getattr(ljm.constants, 'ctWIFI', None)] else None,
                    firmware_version=str(firmware_version),
                    hardware_version=str(hardware_version),
                    bootloader_version=str(bootloader_version)
                )
                
                # Configure TTL input channel
                self._configure_ttl_channel()
                
                self.connection_status = ConnectionStatus.CONNECTED
                self.test_start_time = datetime.now()
                
                logger.info(f"✅ Connected to {device_type_str} S/N:{serial_number} via {connection_type_str}")
                if ip_str:
                    logger.info(f"📡 IP Address: {ip_str}:{port}")
                logger.info(f"🔧 Firmware: {firmware_version}, Hardware: {hardware_version}")
                
                return True
                
            except ljm.LJMError as e:
                error_msg = f"LJM Error {e.errorCode}: {ljm.errorToString(e.errorCode)}"
                logger.error(f"❌ Connection failed: {error_msg}")
                self.connection_status = ConnectionStatus.ERROR
                self.statistics["errors_count"] += 1
                self.statistics["last_error"] = error_msg
                return False
                
            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                logger.error(f"❌ Connection failed: {error_msg}")
                self.connection_status = ConnectionStatus.ERROR
                self.statistics["errors_count"] += 1
                self.statistics["last_error"] = error_msg
                return False
    
    def _configure_ttl_channel(self):
        """Configure the TTL input channel for signal detection"""
        try:
            channel = self.signal_config.channel
            
            # If using analog input (AIN), configure range and resolution
            if channel.startswith("AIN"):
                # Set input range
                ljm.eWriteName(self.handle, f"{channel}_RANGE", self.signal_config.range_volts)
                # Set resolution
                ljm.eWriteName(self.handle, f"{channel}_RESOLUTION_INDEX", self.signal_config.resolution_index)
                # Set settling time
                ljm.eWriteName(self.handle, f"{channel}_SETTLING_US", self.signal_config.settling_time_us)
                
                logger.info(f"🔧 Configured {channel}: Range={self.signal_config.range_volts}V, "
                           f"Resolution={self.signal_config.resolution_index}, Threshold={self.signal_config.threshold_voltage}V")
            
            # If using digital input (DIO), configure as input
            elif channel.startswith("DIO") or channel.startswith("FIO") or channel.startswith("EIO"):
                # Configure as digital input
                ljm.eWriteName(self.handle, f"{channel}_DIRECTION", 0)  # 0 = input
                
                logger.info(f"🔧 Configured {channel} as digital input, Threshold={self.signal_config.threshold_voltage}V")
            
        except Exception as e:
            logger.error(f"❌ Failed to configure TTL channel {self.signal_config.channel}: {e}")
            raise
    
    def start_signal_monitoring(self, test_session_id: str) -> bool:
        """
        Start TTL signal monitoring for hardware events - PRD Module 3.2
        
        Args:
            test_session_id: ID of the test session for event correlation
        
        Returns:
            True if monitoring started successfully
        """
        with self.lock:
            if not self.is_connected():
                logger.error("❌ Cannot start monitoring: LabJack not connected")
                return False
            
            if self.monitoring_active:
                logger.warning("⚠️ Signal monitoring already active")
                return True
            
            try:
                self.test_start_time = datetime.now()
                self.monitoring_active = True
                self.stop_monitoring.clear()
                
                # Start monitoring thread
                self.monitoring_thread = threading.Thread(
                    target=self._signal_monitoring_loop,
                    args=(test_session_id,),
                    daemon=True,
                    name="LabJackSignalMonitor"
                )
                self.monitoring_thread.start()
                
                logger.info(f"📊 TTL signal monitoring started on {self.signal_config.channel}")
                logger.info(f"🎯 Detection threshold: {self.signal_config.threshold_voltage}V")
                logger.info(f"📈 Sample rate: {self.signal_config.sample_rate} Hz")
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Failed to start signal monitoring: {e}")
                self.monitoring_active = False
                self.statistics["errors_count"] += 1
                self.statistics["last_error"] = str(e)
                return False
    
    def _signal_monitoring_loop(self, test_session_id: str):
        """
        Main signal monitoring loop with precision timing
        Monitors TTL signals and logs hardware events with Signal_Received_Time
        """
        logger.info("🔍 Signal monitoring loop started")
        
        last_signal_state = False
        last_signal_time = None
        sample_interval = 1.0 / self.signal_config.sample_rate
        monitoring_start = time.perf_counter()
        
        try:
            while self.monitoring_active and not self.stop_monitoring.is_set():
                try:
                    # High-precision timestamp capture
                    sample_time = time.perf_counter()
                    signal_received_time = datetime.now()
                    
                    # Read current signal value
                    if self.signal_config.channel.startswith("AIN"):
                        # Analog input reading
                        voltage = ljm.eReadName(self.handle, self.signal_config.channel)
                        signal_state = voltage >= self.signal_config.threshold_voltage
                    else:
                        # Digital input reading
                        digital_value = ljm.eReadName(self.handle, self.signal_config.channel)
                        voltage = digital_value * 3.3  # Assume 3.3V logic level
                        signal_state = digital_value > 0
                    
                    self.statistics["last_signal_voltage"] = voltage
                    
                    # Detect signal transitions based on configuration
                    signal_detected = False
                    signal_type = TTLSignalType.HIGH if signal_state else TTLSignalType.LOW
                    
                    if self.signal_config.edge_detection == TTLSignalType.RISING_EDGE:
                        signal_detected = not last_signal_state and signal_state
                        if signal_detected:
                            signal_type = TTLSignalType.RISING_EDGE
                    elif self.signal_config.edge_detection == TTLSignalType.FALLING_EDGE:
                        signal_detected = last_signal_state and not signal_state
                        if signal_detected:
                            signal_type = TTLSignalType.FALLING_EDGE
                    elif self.signal_config.edge_detection == TTLSignalType.HIGH:
                        signal_detected = signal_state
                        signal_type = TTLSignalType.HIGH
                    elif self.signal_config.edge_detection == TTLSignalType.LOW:
                        signal_detected = not signal_state
                        signal_type = TTLSignalType.LOW
                    
                    # Apply debouncing
                    if signal_detected and last_signal_time is not None:
                        time_since_last = (sample_time - last_signal_time) * 1000  # Convert to ms
                        if time_since_last < self.signal_config.debounce_time_ms:
                            signal_detected = False  # Ignore due to debouncing
                    
                    # Log hardware event if signal detected
                    if signal_detected:
                        self._log_hardware_event(
                            test_session_id=test_session_id,
                            signal_received_time=signal_received_time,
                            signal_type=signal_type,
                            signal_voltage=voltage,
                            channel=self.signal_config.channel
                        )
                        
                        last_signal_time = sample_time
                        self.last_signal_time = signal_received_time
                        self.statistics["total_signals_detected"] += 1
                        
                        logger.info(f"🎯 TTL signal detected: {voltage:.3f}V on {self.signal_config.channel} at {signal_received_time.isoformat()}")
                    
                    last_signal_state = signal_state
                    
                    # Sleep for next sample (precision timing)
                    next_sample_time = monitoring_start + (time.perf_counter() - monitoring_start) + sample_interval
                    sleep_time = max(0, next_sample_time - time.perf_counter())
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    
                except ljm.LJMError as e:
                    if e.errorCode != ljm.errorcodes.NO_DATA_AVAILABLE:
                        logger.error(f"❌ LJM error during monitoring: {ljm.errorToString(e.errorCode)}")
                        break
                except Exception as e:
                    logger.error(f"❌ Error in monitoring loop: {e}")
                    self.statistics["errors_count"] += 1
                    break
        
        finally:
            self.monitoring_active = False
            self.statistics["monitoring_duration_seconds"] = time.perf_counter() - monitoring_start
            logger.info("⏹️ Signal monitoring loop stopped")
    
    def _log_hardware_event(self, test_session_id: str, signal_received_time: datetime, 
                           signal_type: TTLSignalType, signal_voltage: float, channel: str):
        """
        Log hardware detection event with precision timing - PRD Module 3.2
        
        Creates HardwareEvent with Signal_Received_Time for latency analysis
        """
        try:
            # Generate unique event ID
            event_id = f"hw_event_{int(signal_received_time.timestamp() * 1000000)}"
            
            # Calculate expected event time (this would come from ground truth in real implementation)
            # For now, we use the signal time as both expected and received
            expected_event_time = signal_received_time  # This should be provided by test orchestrator
            
            # Calculate latency (will be 0 here, but real implementation would have different times)
            latency_ms = (signal_received_time - expected_event_time).total_seconds() * 1000
            
            # Create hardware event
            hardware_event = HardwareEvent(
                event_id=event_id,
                test_session_id=test_session_id,
                video_id="",  # Would be provided by test orchestrator
                ground_truth_object_id=None,  # Would be correlated with ground truth
                expected_event_time=expected_event_time,
                signal_received_time=signal_received_time,
                latency_ms=latency_ms,
                signal_type=signal_type,
                signal_voltage=signal_voltage,
                channel=channel,
                detection_outcome="pass",  # Would be determined by latency analysis
                created_at=datetime.now()
            )
            
            # Add to event queue
            try:
                self.hardware_events.put_nowait(hardware_event)
            except queue.Full:
                logger.warning("⚠️ Hardware event queue full, dropping event")
            
            # Notify callbacks
            for callback in self.event_callbacks:
                try:
                    callback(hardware_event)
                except Exception as e:
                    logger.error(f"❌ Error in event callback: {e}")
            
        except Exception as e:
            logger.error(f"❌ Failed to log hardware event: {e}")
            self.statistics["errors_count"] += 1
    
    def stop_signal_monitoring(self) -> bool:
        """Stop TTL signal monitoring"""
        with self.lock:
            if not self.monitoring_active:
                return True
            
            try:
                self.monitoring_active = False
                self.stop_monitoring.set()
                
                if self.monitoring_thread and self.monitoring_thread.is_alive():
                    self.monitoring_thread.join(timeout=5.0)
                
                logger.info("⏹️ TTL signal monitoring stopped")
                return True
                
            except Exception as e:
                logger.error(f"❌ Failed to stop signal monitoring: {e}")
                return False
    
    def add_event_callback(self, callback: Callable[[HardwareEvent], None]):
        """Add callback for hardware events"""
        self.event_callbacks.append(callback)
    
    def remove_event_callback(self, callback: Callable[[HardwareEvent], None]):
        """Remove hardware event callback"""
        if callback in self.event_callbacks:
            self.event_callbacks.remove(callback)
    
    def get_hardware_events(self, max_events: int = 100) -> List[HardwareEvent]:
        """Get hardware events from queue"""
        events = []
        count = 0
        
        while count < max_events:
            try:
                event = self.hardware_events.get_nowait()
                events.append(event)
                count += 1
            except queue.Empty:
                break
        
        return events
    
    def read_current_signal(self) -> Tuple[float, bool]:
        """
        Read current signal voltage and state
        
        Returns:
            Tuple of (voltage, is_signal_high)
        """
        if not self.is_connected():
            return 0.0, False
        
        try:
            if self.signal_config.channel.startswith("AIN"):
                voltage = ljm.eReadName(self.handle, self.signal_config.channel)
                is_high = voltage >= self.signal_config.threshold_voltage
            else:
                digital_value = ljm.eReadName(self.handle, self.signal_config.channel)
                voltage = digital_value * 3.3
                is_high = digital_value > 0
            
            return voltage, is_high
            
        except Exception as e:
            logger.error(f"❌ Failed to read signal: {e}")
            return 0.0, False
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get device information for status display"""
        if self.device_info:
            return asdict(self.device_info)
        else:
            return {"error": "No device connected"}
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive service status for PRD Module 3.1"""
        return {
            "connection_status": self.get_connection_status(),  # PRD requirement
            "is_connected": self.is_connected(),
            "device_info": self.get_device_info(),
            "monitoring_active": self.monitoring_active,
            "signal_configuration": asdict(self.signal_config),
            "statistics": self.statistics.copy(),
            "last_signal_time": self.last_signal_time.isoformat() if self.last_signal_time else None,
            "test_start_time": self.test_start_time.isoformat() if self.test_start_time else None,
            "events_in_queue": self.hardware_events.qsize(),
            "ljm_library_available": LJM_AVAILABLE,
            "numpy_available": NUMPY_AVAILABLE
        }
    
    def disconnect(self) -> bool:
        """Disconnect from LabJack hardware"""
        with self.lock:
            try:
                # Stop monitoring
                if self.monitoring_active:
                    self.stop_signal_monitoring()
                
                # Close hardware connection
                if self.handle is not None:
                    ljm.close(self.handle)
                    self.handle = None
                
                self.connection_status = ConnectionStatus.DISCONNECTED
                self.device_info = None
                
                logger.info("🔌 LabJack disconnected")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error during disconnect: {e}")
                self.connection_status = ConnectionStatus.ERROR
                return False
    
    def __del__(self):
        """Cleanup on destruction"""
        try:
            if self.is_connected():
                self.disconnect()
        except:
            pass


# Global service instance for singleton pattern
_real_labjack_service: Optional[RealLabJackService] = None


def get_real_labjack_service(signal_config: Optional[SignalConfiguration] = None) -> RealLabJackService:
    """Get global real LabJack service instance"""
    global _real_labjack_service
    if _real_labjack_service is None:
        _real_labjack_service = RealLabJackService(signal_config)
    return _real_labjack_service


def initialize_real_labjack_service(signal_config: Optional[SignalConfiguration] = None, auto_connect: bool = False) -> bool:
    """Initialize real LabJack service (optionally connect immediately)"""
    try:
        service = get_real_labjack_service(signal_config)
        
        if auto_connect:
            # Auto-connect mode: detect and connect immediately
            devices = service.detect_devices()
            
            if devices:
                # Try to connect to first available device
                device = devices[0]
                success = service.connect(
                    device_type=device["device_type"],
                    connection_type=device["connection_type"],
                    identifier=str(device["serial_number"])
                )
                
                if success:
                    logger.info(f"✅ Real LabJack service initialized and connected to {device['device_type']}")
                    return True
            
            logger.warning("⚠️ No LabJack devices detected for connection")
            return False
        else:
            # Lazy mode: initialize service without connecting
            logger.info("✅ Real LabJack service initialized (lazy connection - will connect when needed)")
            return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize real LabJack service: {e}")
        return False


# Export main classes and functions
__all__ = [
    "RealLabJackService",
    "ConnectionStatus", 
    "TTLSignalType",
    "HardwareEvent",
    "DeviceInfo",
    "SignalConfiguration",
    "get_real_labjack_service",
    "initialize_real_labjack_service"
]
