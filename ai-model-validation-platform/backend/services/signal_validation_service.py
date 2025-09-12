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
    logging.warning("LabJack LJM library not installed. Using mock mode.")
    # Import mock LabJack interface
    try:
        from services.mock_labjack import ljm, get_mock_labjack_status
        logging.info("Mock LabJack interface loaded successfully")
    except ImportError as mock_error:
        logging.error(f"Failed to load mock LabJack interface: {mock_error}")
        ljm = None

# Import configuration
try:
    from config.labjack_env_config import load_config_from_env, detect_labjack_availability
except ImportError:
    logging.warning("LabJack environment configuration not available")
    load_config_from_env = None
    detect_labjack_availability = None

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
    """Interface for LabJack voltage signal acquisition with fallback support"""
    
    def __init__(self, force_mock_mode: bool = False):
        self.handle = None
        self.is_connected = False
        self.voltage_threshold = 2.5  # Voltage threshold for detection (adjustable)
        self.sample_rate = 1000  # Hz
        self.channels = ["AIN0", "AIN1"]  # Analog input channels
        self.mock_mode = force_mock_mode or not LABJACK_AVAILABLE
        self.connection_retries = 0
        self.max_retries = 3
        
        # Load configuration if available
        if load_config_from_env:
            try:
                config = load_config_from_env()
                self.voltage_threshold = config.voltage_threshold
                self.sample_rate = config.sample_rate
                self.channels = config.channels
                self.mock_mode = config.mock_mode or self.mock_mode
                logger.info(f"LabJack configuration loaded: mock_mode={self.mock_mode}")
            except Exception as e:
                logger.warning(f"Failed to load LabJack configuration: {e}")
        
        if self.mock_mode:
            logger.info("🔧 LabJack interface initialized in MOCK MODE")
        else:
            logger.info("🔌 LabJack interface initialized in HARDWARE MODE")
        
    def connect(self, device_type: str = "ANY", connection_type: str = "ANY", identifier: str = "ANY"):
        """Connect to LabJack device with automatic fallback to mock mode"""
        if ljm is None:
            raise RuntimeError("Neither real nor mock LabJack interface is available")
        
        # Reset connection retry counter
        self.connection_retries = 0
        
        while self.connection_retries < self.max_retries:
            try:
                if self.mock_mode:
                    # Use mock interface
                    self.handle = ljm.openS(device_type, connection_type, identifier)
                    logger.info(f"🔧 Connected to Mock LabJack - Device Type: {device_type}")
                else:
                    # Try real hardware connection
                    self.handle = ljm.openS(device_type, connection_type, identifier)
                    info = ljm.getHandleInfo(self.handle)
                    logger.info(f"🔌 Connected to LabJack - Device Type: {info[0]}, Connection: {info[1]}, "
                               f"Serial: {info[2]}, IP: {ljm.numberToIP(info[3])}, Port: {info[4]}")
                
                # Configure analog inputs for best resolution
                # Set analog input range to ±10V for better signal detection
                for channel in self.channels:
                    ljm.eWriteName(self.handle, f"{channel}_RANGE", 10.0)
                    ljm.eWriteName(self.handle, f"{channel}_RESOLUTION_INDEX", 0)  # Default resolution
                    
                self.is_connected = True
                return True
                
            except Exception as e:
                self.connection_retries += 1
                error_msg = str(e)
                
                # Check if this is a "no devices found" error and we're not in mock mode
                if not self.mock_mode and ("NO_DEVICES_FOUND" in error_msg or "LJME_NO_DEVICES_FOUND" in error_msg):
                    logger.warning(f"No LabJack hardware found (attempt {self.connection_retries}), falling back to mock mode")
                    self.mock_mode = True
                    continue
                elif self.connection_retries < self.max_retries:
                    logger.warning(f"Connection attempt {self.connection_retries} failed: {e}")
                    continue
                else:
                    logger.error(f"Failed to connect to LabJack after {self.max_retries} attempts: {e}")
                    return False
        
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
        """Read voltage signals for specified duration with error handling"""
        if not self.is_connected:
            return []
            
        signals = []
        
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
                                    "threshold": self.voltage_threshold,
                                    "mock_mode": self.mock_mode
                                }
                            )
                            signals.append(signal)
                            
        except Exception as e:
            # Handle both real and mock LabJack errors
            error_code = getattr(e, 'errorCode', None)
            no_data_codes = [2398]  # NO_DATA_AVAILABLE
            
            if hasattr(ljm, 'errorcodes') and hasattr(ljm.errorcodes, 'NO_DATA_AVAILABLE'):
                no_data_codes.append(ljm.errorcodes.NO_DATA_AVAILABLE)
            
            if error_code not in no_data_codes:
                logger.error(f"Stream read error: {e}")
                
        return signals
    
    def read_single_voltage(self) -> Dict[str, float]:
        """Read single voltage values from all channels with error handling"""
        if not self.is_connected:
            return {}
            
        voltages = {}
        try:
            for channel in self.channels:
                voltage = ljm.eReadName(self.handle, channel)
                voltages[channel] = voltage
        except Exception as e:
            logger.error(f"Failed to read voltage: {e}")
            # Return empty dict on error
            return {}
            
        return voltages
    
    def disconnect(self):
        """Disconnect from LabJack with proper cleanup"""
        if self.handle is not None:
            try:
                ljm.eStreamStop(self.handle)
            except:
                pass
            try:
                ljm.close(self.handle)
            except:
                pass
            self.is_connected = False
            mode_text = "Mock LabJack" if self.mock_mode else "LabJack"
            logger.info(f"Disconnected from {mode_text}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of LabJack interface"""
        status = {
            "connected": self.is_connected,
            "mock_mode": self.mock_mode,
            "voltage_threshold": self.voltage_threshold,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "connection_retries": self.connection_retries,
            "max_retries": self.max_retries
        }
        
        if self.is_connected:
            try:
                voltages = self.read_single_voltage()
                status["current_voltages"] = voltages
            except Exception as e:
                status["voltage_read_error"] = str(e)
        
        return status


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
        
        # Initialize LabJack interface (with automatic fallback)
        try:
            self.labjack = LabJackInterface()
            logger.info("LabJack interface initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LabJack interface: {e}")
            self.labjack = None
    
    async def initialize_labjack(self, device_config: Dict[str, Any] = None) -> bool:
        """Initialize LabJack connection with automatic fallback to mock mode"""
        try:
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
                    
                mode_text = "Mock LabJack" if self.labjack.mock_mode else "LabJack hardware"
                logger.info(f"{mode_text} initialized successfully")
                return True
            else:
                logger.error("Failed to initialize LabJack (all connection attempts failed)")
                return False
                
        except Exception as e:
            logger.error(f"Error during LabJack initialization: {e}")
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
        """Check LabJack connection status and current readings with comprehensive error handling"""
        
        try:
            if self.labjack is None:
                return {
                    "connected": False,
                    "mock_mode": False,
                    "error": "LabJack interface not initialized"
                }
            
            # Get detailed status from LabJack interface
            status = self.labjack.get_status()
            
            if not status["connected"]:
                return {
                    "connected": False,
                    "mock_mode": status["mock_mode"],
                    "error": "LabJack not connected"
                }
            
            # Add system availability information
            if detect_labjack_availability:
                availability = detect_labjack_availability()
                status.update({
                    "hardware_availability": availability,
                    "ljm_library_available": availability.get("ljm_library", False)
                })
            
            return status
            
        except Exception as e:
            logger.error(f"Error checking LabJack connection: {e}")
            return {
                "connected": False,
                "mock_mode": True,
                "error": f"Connection check failed: {e}"
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