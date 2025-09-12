"""
Real LabJack Integration Service - Hardware Signal Detection
PRD Module 3: Test Execution - Hardware Signal Capture and Timing

CRITICAL: NO MOCK IMPLEMENTATIONS - Real hardware integration only
"""

import logging
import time
import threading
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class SignalType(Enum):
    """Hardware signal types from GLOBAL_VARIABLES_REFERENCE.md"""
    TTL = "ttl"
    GPIO = "gpio"
    ANALOG = "analog" 
    DIGITAL = "digital"

class DetectionOutcome(Enum):
    """Test execution outcomes from GLOBAL_VARIABLES_REFERENCE.md"""
    PASS = "pass"
    FAIL_HIGH_LATENCY = "fail_high_latency"
    FAIL_MISSED_DETECTION = "fail_missed_detection"

@dataclass
class HardwareEvent:
    """Hardware detection event data structure"""
    timestamp: float
    signal_type: SignalType
    signal_value: float
    channel: str
    voltage: float

class LabJackIntegrationService:
    """
    Real LabJack DAQ Hardware Integration Service
    PRD Requirement: Sub-millisecond precision timing validation
    """
    
    def __init__(self, device_type: str = "U6", connection_type: str = "USB"):
        self.device_type = device_type
        self.connection_type = connection_type
        self.device = None
        self.is_connected = False
        self.monitoring = False
        self.events_buffer: List[HardwareEvent] = []
        self.lock = threading.Lock()
        
        # Timing precision configuration
        self.timing_precision_microseconds = True
        self.monotonic_clock_enabled = True
        
        # TTL Signal configuration from GLOBAL_VARIABLES_REFERENCE.md
        self.ttl_high_voltage_min = 3.3
        self.ttl_low_voltage_max = 0.8
        
    def connect_hardware(self) -> bool:
        """
        Connect to real LabJack hardware
        Returns True if connection successful
        """
        try:
            # Try to import LabJack library
            try:
                import ljm  # LabJack Modbus library
                self.ljm = ljm
                logger.info("LabJack LJM library loaded successfully")
            except ImportError:
                logger.error("LabJack LJM library not installed. Install with: pip install labjack-ljm")
                return False
            
            # Connect to device
            try:
                self.device = self.ljm.openS(self.device_type, self.connection_type, "ANY")
                logger.info(f"✅ Connected to LabJack {self.device_type} via {self.connection_type}")
                self.is_connected = True
                
                # Configure device for optimal timing
                self._configure_device()
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect to LabJack device: {e}")
                return False
                
        except Exception as e:
            logger.error(f"LabJack initialization error: {e}")
            return False
    
    def _configure_device(self):
        """Configure LabJack for precision timing"""
        if not self.device:
            return
            
        try:
            # Configure for maximum timing precision
            # Set up analog input channels for TTL detection
            self.ljm.eWriteName(self.device, "AIN0_NEGATIVE_CH", self.ljm.constants.GND)
            self.ljm.eWriteName(self.device, "AIN0_RANGE", 10.0)  # ±10V range for TTL
            
            logger.info("LabJack configured for precision timing")
            
        except Exception as e:
            logger.error(f"Device configuration error: {e}")
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get hardware connection status"""
        status = {
            "connected": self.is_connected,
            "device_type": self.device_type,
            "connection_type": self.connection_type,
            "monitoring": self.monitoring,
            "events_count": len(self.events_buffer)
        }
        
        if self.is_connected and self.device:
            try:
                # Get device info
                info = self.ljm.eReadName(self.device, "SERIAL_NUMBER")
                status["serial_number"] = int(info)
                status["firmware_version"] = self.ljm.eReadName(self.device, "FIRMWARE_VERSION")
                status["hardware_version"] = self.ljm.eReadName(self.device, "HARDWARE_VERSION")
            except Exception as e:
                logger.warning(f"Could not read device info: {e}")
        
        return status
    
    def start_monitoring(self, channels: List[str] = None) -> bool:
        """
        Start hardware signal monitoring
        Args:
            channels: List of channels to monitor (default: ["AIN0"])
        """
        if not self.is_connected:
            logger.error("Cannot start monitoring - device not connected")
            return False
        
        if channels is None:
            channels = ["AIN0"]  # Default TTL input channel
        
        self.monitoring_channels = channels
        self.monitoring = True
        self.events_buffer.clear()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_signals, daemon=True)
        self.monitor_thread.start()
        
        logger.info(f"Started monitoring channels: {channels}")
        return True
    
    def _monitor_signals(self):
        """Background thread for signal monitoring"""
        logger.info("Hardware signal monitoring started")
        
        while self.monitoring and self.is_connected:
            try:
                # Read voltage from configured channels
                for channel in self.monitoring_channels:
                    voltage = self.ljm.eReadName(self.device, channel)
                    
                    # Detect TTL signal transitions
                    if self._is_ttl_signal(voltage):
                        event = HardwareEvent(
                            timestamp=self._get_precise_timestamp(),
                            signal_type=SignalType.TTL,
                            signal_value=voltage,
                            channel=channel,
                            voltage=voltage
                        )
                        
                        with self.lock:
                            self.events_buffer.append(event)
                        
                        logger.debug(f"TTL signal detected: {voltage}V on {channel}")
                
                # Small delay to prevent overwhelming the system
                time.sleep(0.001)  # 1ms polling rate
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                break
        
        logger.info("Hardware signal monitoring stopped")
    
    def _is_ttl_signal(self, voltage: float) -> bool:
        """Check if voltage represents a TTL high signal"""
        return voltage >= self.ttl_high_voltage_min
    
    def _get_precise_timestamp(self) -> float:
        """Get high-precision timestamp"""
        if self.monotonic_clock_enabled:
            return time.monotonic()
        else:
            return time.time()
    
    def get_recent_events(self, count: int = 100) -> List[Dict[str, Any]]:
        """Get recent hardware events"""
        with self.lock:
            recent_events = self.events_buffer[-count:] if count > 0 else self.events_buffer.copy()
        
        return [
            {
                "timestamp": event.timestamp,
                "signal_type": event.signal_type.value,
                "signal_value": event.signal_value,
                "channel": event.channel,
                "voltage": event.voltage
            }
            for event in recent_events
        ]
    
    def validate_latency(self, expected_time: float, tolerance_ms: float = 100) -> Tuple[bool, float, DetectionOutcome]:
        """
        Validate hardware signal latency
        Args:
            expected_time: Expected signal time
            tolerance_ms: Maximum allowed latency in milliseconds
        Returns:
            (is_valid, actual_latency_ms, outcome)
        """
        with self.lock:
            if not self.events_buffer:
                return False, float('inf'), DetectionOutcome.FAIL_MISSED_DETECTION
            
            # Find closest event to expected time
            closest_event = min(
                self.events_buffer,
                key=lambda e: abs(e.timestamp - expected_time)
            )
            
            latency_ms = abs(closest_event.timestamp - expected_time) * 1000
            
            if latency_ms <= tolerance_ms:
                return True, latency_ms, DetectionOutcome.PASS
            else:
                return False, latency_ms, DetectionOutcome.FAIL_HIGH_LATENCY
    
    def stop_monitoring(self):
        """Stop hardware signal monitoring"""
        self.monitoring = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=1.0)
        logger.info("Hardware monitoring stopped")
    
    def disconnect(self):
        """Disconnect from LabJack hardware"""
        self.stop_monitoring()
        
        if self.device:
            try:
                self.ljm.close(self.device)
                self.device = None
                self.is_connected = False
                logger.info("LabJack device disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting device: {e}")

# Global service instance
labjack_service = LabJackIntegrationService()

def get_labjack_service() -> LabJackIntegrationService:
    """Get the global LabJack service instance"""
    return labjack_service