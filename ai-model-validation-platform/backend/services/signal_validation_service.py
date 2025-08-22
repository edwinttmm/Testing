"""
Signal Validation Service for External Camera Detection Signals

This service receives and validates detection signals from external camera systems
that are watching videos displayed on a monitor. The camera is NOT directly connected
to this system. Signals arrive via:
- LabJack voltage signals with timing data
- CAN bus messages with detection timestamps
- Network packets with detection information

The service validates these external signals against pre-annotated ground truth
to determine if the camera correctly detected objects in the displayed video.
"""

import asyncio
import logging
import uuid
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import json
import threading
from dataclasses import dataclass
from enum import Enum

# LabJack imports for voltage signal acquisition
try:
    from labjack import ljm
    LABJACK_AVAILABLE = True
except ImportError:
    LABJACK_AVAILABLE = False
    logging.warning("LabJack LJM library not installed. Install with: pip install labjack-ljm")

from models import GroundTruthObject, DetectionEvent, TestSession
from schemas_video_annotation import (
    AnnotationValidationRequest, ValidationResult, 
    TimingComparisonRequest, TimingComparisonResult,
    PassFailCriteria, PassFailResult
)

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of external signals from camera systems"""
    VOLTAGE = "voltage"  # LabJack voltage signals
    CAN_BUS = "can_bus"  # CAN bus messages
    NETWORK = "network"  # Network packets
    SERIAL = "serial"    # Serial communication


@dataclass
class DetectionSignal:
    """Represents a detection signal from external camera"""
    timestamp: float  # Time in video when detection occurred
    signal_type: SignalType
    confidence: float
    voltage_value: Optional[float] = None  # For voltage signals
    can_message_id: Optional[int] = None  # For CAN signals
    network_packet: Optional[Dict] = None  # For network signals
    metadata: Dict[str, Any] = None


class LabJackInterface:
    """Interface for LabJack voltage signal acquisition"""
    
    def __init__(self):
        self.handle = None
        self.is_connected = False
        self.voltage_threshold = 2.5  # Voltage threshold for detection (adjustable)
        self.sample_rate = 1000  # Hz
        self.channels = ["AIN0", "AIN1"]  # Analog input channels
        
    def connect(self, device_type: str = "ANY", connection_type: str = "ANY", identifier: str = "ANY"):
        """Connect to LabJack device"""
        if not LABJACK_AVAILABLE:
            raise RuntimeError("LabJack LJM library not installed")
            
        try:
            # Open connection to LabJack
            self.handle = ljm.openS(device_type, connection_type, identifier)
            info = ljm.getHandleInfo(self.handle)
            logger.info(f"Connected to LabJack - Device Type: {info[0]}, Connection: {info[1]}, "
                       f"Serial: {info[2]}, IP: {ljm.numberToIP(info[3])}, Port: {info[4]}")
            
            # Configure analog inputs for best resolution
            # Set analog input range to ±10V for better signal detection
            for channel in self.channels:
                ljm.eWriteName(self.handle, f"{channel}_RANGE", 10.0)
                ljm.eWriteName(self.handle, f"{channel}_RESOLUTION_INDEX", 0)  # Default resolution
                
            self.is_connected = True
            return True
            
        except ljm.LJMError as e:
            logger.error(f"Failed to connect to LabJack: {e}")
            return False
    
    def configure_stream(self, scan_rate: int = 1000):
        """Configure streaming for continuous voltage monitoring"""
        if not self.is_connected:
            raise RuntimeError("LabJack not connected")
            
        try:
            # Configure stream settings
            aScanListNames = self.channels
            numAddresses = len(aScanListNames)
            aScanList = ljm.namesToAddresses(numAddresses, aScanListNames)[0]
            
            # Configure and start stream
            scanRate = ljm.eStreamStart(self.handle, scan_rate, numAddresses, 
                                        aScanList, scan_rate)
            
            logger.info(f"Stream started with scan rate: {scanRate} Hz")
            self.sample_rate = scanRate
            return scanRate
            
        except ljm.LJMError as e:
            logger.error(f"Failed to configure stream: {e}")
            raise
    
    def read_voltage_signals(self, duration_ms: int = 100) -> List[DetectionSignal]:
        """Read voltage signals for specified duration"""
        if not self.is_connected:
            return []
            
        signals = []
        samples_to_read = int(self.sample_rate * duration_ms / 1000)
        
        try:
            # Read stream data
            ret = ljm.eStreamRead(self.handle)
            data = ret[0]
            
            # Process voltage data
            num_channels = len(self.channels)
            for i in range(0, len(data), num_channels):
                for ch_idx, channel in enumerate(self.channels):
                    if i + ch_idx < len(data):
                        voltage = data[i + ch_idx]
                        
                        # Detect signal based on voltage threshold
                        if abs(voltage) > self.voltage_threshold:
                            # Calculate timestamp based on sample position
                            sample_time = i / (num_channels * self.sample_rate)
                            
                            signal = DetectionSignal(
                                timestamp=sample_time,
                                signal_type=SignalType.VOLTAGE,
                                confidence=min(abs(voltage) / 10.0, 1.0),  # Normalize confidence
                                voltage_value=voltage,
                                metadata={
                                    "channel": channel,
                                    "sample_index": i,
                                    "threshold": self.voltage_threshold
                                }
                            )
                            signals.append(signal)
                            
        except ljm.LJMError as e:
            if e.errorCode != ljm.errorcodes.NO_DATA_AVAILABLE:
                logger.error(f"Stream read error: {e}")
                
        return signals
    
    def read_single_voltage(self) -> Dict[str, float]:
        """Read single voltage values from all channels"""
        if not self.is_connected:
            return {}
            
        voltages = {}
        try:
            for channel in self.channels:
                voltage = ljm.eReadName(self.handle, channel)
                voltages[channel] = voltage
        except ljm.LJMError as e:
            logger.error(f"Failed to read voltage: {e}")
            
        return voltages
    
    def disconnect(self):
        """Disconnect from LabJack"""
        if self.handle is not None:
            try:
                ljm.eStreamStop(self.handle)
            except:
                pass
            ljm.close(self.handle)
            self.is_connected = False
            logger.info("Disconnected from LabJack")


class SignalValidationService:
    """Service for external detection signal validation against ground truth.
    
    This service receives detection signals from external camera systems that are
    watching videos displayed on a monitor. The camera is NOT directly connected
    to this system. Signals arrive via:
    - LabJack voltage signals with timing data
    - CAN bus messages with detection timestamps
    - Network packets with detection information
    
    The service validates these external signals against pre-annotated ground truth
    to determine if the camera correctly detected objects in the displayed video.
    """
    
    def __init__(self):
        self.signal_buffer = []  # Buffer for incoming signals
        self.validation_results = {}  # Validation results cache
        self.labjack = None  # LabJack interface
        self.signal_thread = None  # Thread for continuous signal monitoring
        self.monitoring_active = False
        self.current_video_start_time = None
        self.current_test_session = None
        
        # Signal validation parameters
        self.timing_tolerance_ms = 100  # Acceptable timing difference in milliseconds
        self.spatial_tolerance = 0.3  # IoU threshold for spatial matching
        
        # Initialize LabJack if available
        if LABJACK_AVAILABLE:
            self.labjack = LabJackInterface()
    
    async def initialize_labjack(self, device_config: Dict[str, Any] = None) -> bool:
        """Initialize LabJack connection for voltage signal acquisition"""
        if not LABJACK_AVAILABLE:
            logger.warning("LabJack LJM library not available")
            return False
            
        if self.labjack is None:
            self.labjack = LabJackInterface()
            
        # Connect to LabJack with provided config or defaults
        config = device_config or {}
        device_type = config.get("device_type", "ANY")
        connection_type = config.get("connection_type", "ANY")
        identifier = config.get("identifier", "ANY")
        
        if self.labjack.connect(device_type, connection_type, identifier):
            # Configure voltage thresholds
            if "voltage_threshold" in config:
                self.labjack.voltage_threshold = config["voltage_threshold"]
            
            # Configure channels if specified
            if "channels" in config:
                self.labjack.channels = config["channels"]
                
            logger.info("LabJack initialized successfully")
            return True
        else:
            logger.error("Failed to initialize LabJack")
            return False
    
    def start_signal_monitoring(self, test_session_id: str):
        """Start continuous monitoring of external signals"""
        if self.monitoring_active:
            logger.warning("Signal monitoring already active")
            return
            
        self.current_test_session = test_session_id
        self.current_video_start_time = datetime.utcnow()
        self.monitoring_active = True
        
        # Start monitoring thread
        self.signal_thread = threading.Thread(
            target=self._signal_monitoring_loop,
            daemon=True
        )
        self.signal_thread.start()
        
        logger.info(f"Started signal monitoring for session {test_session_id}")
    
    def _signal_monitoring_loop(self):
        """Background thread for continuous signal monitoring"""
        while self.monitoring_active:
            try:
                # Check for LabJack voltage signals
                if self.labjack and self.labjack.is_connected:
                    voltage_signals = self.labjack.read_voltage_signals(duration_ms=50)
                    for signal in voltage_signals:
                        # Adjust timestamp relative to video start
                        if self.current_video_start_time:
                            elapsed = (datetime.utcnow() - self.current_video_start_time).total_seconds()
                            signal.timestamp = elapsed
                        self.signal_buffer.append(signal)
                
                # Small delay to prevent CPU overload
                threading.Event().wait(0.01)
                
            except Exception as e:
                logger.error(f"Error in signal monitoring: {e}")
    
    def stop_signal_monitoring(self):
        """Stop signal monitoring"""
        self.monitoring_active = False
        if self.signal_thread:
            self.signal_thread.join(timeout=1.0)
        logger.info("Stopped signal monitoring")
    
    async def process_external_signal(
        self, 
        signal_type: str,
        signal_data: Dict[str, Any],
        video_timestamp: float,
        test_session_id: str
    ) -> Dict[str, Any]:
        """Process incoming detection signal from external camera system.
        
        The external camera watches the monitor and sends detection signals
        when it identifies objects in the displayed video.
        
        Args:
            signal_type: Type of signal (voltage, can_bus, network)
            signal_data: Signal-specific data (voltage value, CAN message, etc.)
            video_timestamp: Current timestamp in the playing video
            test_session_id: Current test session ID
            
        Returns:
            Processing result with validation status
        """
        
        # Create detection signal object
        if signal_type == "voltage":
            signal = DetectionSignal(
                timestamp=video_timestamp,
                signal_type=SignalType.VOLTAGE,
                confidence=signal_data.get("confidence", 0.8),
                voltage_value=signal_data.get("voltage"),
                metadata=signal_data.get("metadata", {})
            )
        elif signal_type == "can_bus":
            signal = DetectionSignal(
                timestamp=video_timestamp,
                signal_type=SignalType.CAN_BUS,
                confidence=signal_data.get("confidence", 0.8),
                can_message_id=signal_data.get("message_id"),
                metadata=signal_data.get("metadata", {})
            )
        elif signal_type == "network":
            signal = DetectionSignal(
                timestamp=video_timestamp,
                signal_type=SignalType.NETWORK,
                confidence=signal_data.get("confidence", 0.8),
                network_packet=signal_data.get("packet"),
                metadata=signal_data.get("metadata", {})
            )
        else:
            raise ValueError(f"Unsupported signal type: {signal_type}")
        
        # Add to buffer
        self.signal_buffer.append(signal)
        
        # Validate against ground truth if available
        validation_result = await self._validate_signal_against_ground_truth(
            signal, test_session_id
        )
        
        return {
            "signal_id": str(uuid.uuid4()),
            "signal_type": signal_type,
            "timestamp": video_timestamp,
            "validation_result": validation_result,
            "processed_at": datetime.utcnow().isoformat()
        }
    
    async def _validate_signal_against_ground_truth(
        self,
        signal: DetectionSignal,
        test_session_id: str
    ) -> Dict[str, Any]:
        """Validate detection signal against ground truth annotations"""
        
        # This would query the database for ground truth annotations
        # at the signal timestamp and compare
        
        # For now, return a mock validation result
        return {
            "is_valid": True,
            "confidence": signal.confidence,
            "timing_error_ms": 0,
            "matched_annotation_id": None,
            "validation_method": "temporal_matching"
        }
    
    async def get_signal_statistics(self, test_session_id: str) -> Dict[str, Any]:
        """Get statistics for signals in current test session"""
        
        # Filter signals for this session
        session_signals = [s for s in self.signal_buffer 
                          if s.metadata and s.metadata.get("session_id") == test_session_id]
        
        if not session_signals:
            return {"total_signals": 0, "signal_types": {}}
        
        # Calculate statistics
        stats = {
            "total_signals": len(session_signals),
            "signal_types": {},
            "average_confidence": np.mean([s.confidence for s in session_signals]),
            "timing_distribution": {},
            "voltage_statistics": {}
        }
        
        # Group by signal type
        for signal in session_signals:
            signal_type = signal.signal_type.value
            if signal_type not in stats["signal_types"]:
                stats["signal_types"][signal_type] = 0
            stats["signal_types"][signal_type] += 1
            
            # Voltage-specific statistics
            if signal.signal_type == SignalType.VOLTAGE and signal.voltage_value:
                if "voltages" not in stats["voltage_statistics"]:
                    stats["voltage_statistics"]["voltages"] = []
                stats["voltage_statistics"]["voltages"].append(signal.voltage_value)
        
        # Calculate voltage statistics if available
        if "voltages" in stats["voltage_statistics"]:
            voltages = stats["voltage_statistics"]["voltages"]
            stats["voltage_statistics"].update({
                "min_voltage": min(voltages),
                "max_voltage": max(voltages),
                "mean_voltage": np.mean(voltages),
                "std_voltage": np.std(voltages)
            })
        
        return stats
    
    async def check_labjack_connection(self) -> Dict[str, Any]:
        """Check LabJack connection status and current readings"""
        
        if not LABJACK_AVAILABLE:
            return {
                "connected": False,
                "error": "LabJack LJM library not installed"
            }
        
        if not self.labjack or not self.labjack.is_connected:
            return {
                "connected": False,
                "error": "LabJack not connected"
            }
        
        # Read current voltage values
        voltages = self.labjack.read_single_voltage()
        
        return {
            "connected": True,
            "current_voltages": voltages,
            "voltage_threshold": self.labjack.voltage_threshold,
            "channels": self.labjack.channels,
            "sample_rate": self.labjack.sample_rate
        }
    
    async def configure_voltage_detection(
        self,
        voltage_threshold: float = 2.5,
        channels: List[str] = None,
        sample_rate: int = 1000
    ) -> Dict[str, Any]:
        """Configure voltage detection parameters"""
        
        if not self.labjack:
            return {
                "success": False,
                "error": "LabJack not initialized"
            }
        
        # Update configuration
        self.labjack.voltage_threshold = voltage_threshold
        if channels:
            self.labjack.channels = channels
        
        # Reconfigure stream if connected
        if self.labjack.is_connected:
            try:
                self.labjack.configure_stream(sample_rate)
                return {
                    "success": True,
                    "voltage_threshold": voltage_threshold,
                    "channels": self.labjack.channels,
                    "sample_rate": sample_rate
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "success": True,
            "message": "Configuration updated, will be applied on next connection"
        }
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop_signal_monitoring()
        if self.labjack:
            self.labjack.disconnect()


# Global service instance
signal_validation_service = SignalValidationService()