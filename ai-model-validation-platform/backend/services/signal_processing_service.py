from typing import Dict, List, Optional, AsyncGenerator, Any
from dataclasses import dataclass
from enum import Enum
import asyncio
import time
import logging
import json
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    serial = None
import socket
import struct
from abc import ABC, abstractmethod
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)

class SignalType(Enum):
    GPIO = "gpio"
    NETWORK_PACKET = "network_packet"
    SERIAL = "serial"
    CAN_BUS = "can_bus"
    ETHERNET = "ethernet"

@dataclass
class SignalConfig:
    signal_type: SignalType
    source_identifier: str  # GPIO pin, IP:port, /dev/ttyUSB0, etc.
    sampling_rate: float    # Hz
    buffer_size: int       # samples
    precision_mode: bool   # high-precision timestamping
    filters: List[Any]     # Signal filters
    metadata: Dict = None

@dataclass
class SignalEvent:
    id: str
    test_session_id: str
    timestamp: float
    signal_type: SignalType
    signal_data: Dict
    source_identifier: str
    precision_us: float = 0.0

class SignalFilter(ABC):
    """Base class for signal filters"""
    
    @abstractmethod
    async def filter(self, signal_data: Any) -> Optional[Any]:
        pass

class DebounceFilter(SignalFilter):
    """Debounce filter to prevent rapid signal changes"""
    
    def __init__(self, min_interval_ms: int = 10):
        self.min_interval_ms = min_interval_ms
        self.last_signal_time = 0
    
    async def filter(self, signal_data: Any) -> Optional[Any]:
        current_time = time.time() * 1000  # Convert to milliseconds
        
        if current_time - self.last_signal_time >= self.min_interval_ms:
            self.last_signal_time = current_time
            return signal_data
        
        return None  # Filter out signal

class NoiseFilter(SignalFilter):
    """Filter out noise based on threshold"""
    
    def __init__(self, threshold: float = 0.1):
        self.threshold = threshold
    
    async def filter(self, signal_data: Any) -> Optional[Any]:
        if isinstance(signal_data, (int, float)):
            if abs(signal_data) > self.threshold:
                return signal_data
            return None
        
        return signal_data  # Pass through non-numeric data

class LowPassFilter(SignalFilter):
    """Simple low-pass filter for smoothing"""
    
    def __init__(self, alpha: float = 0.7):
        self.alpha = alpha
        self.filtered_value = None
    
    async def filter(self, signal_data: Any) -> Optional[Any]:
        if isinstance(signal_data, (int, float)):
            if self.filtered_value is None:
                self.filtered_value = signal_data
            else:
                self.filtered_value = self.alpha * signal_data + (1 - self.alpha) * self.filtered_value
            
            return self.filtered_value
        
        return signal_data

class SignalHandler(ABC):
    """Base class for signal handlers"""
    
    def __init__(self, config: SignalConfig):
        self.config = config
        self.running = False
        self.signal_buffer = []
    
    @abstractmethod
    async def connect(self):
        """Connect to signal source"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from signal source"""
        pass
    
    @abstractmethod
    async def read_signal(self) -> Optional[Any]:
        """Read single signal value"""
        pass
    
    async def stream_signals(self, config: SignalConfig) -> AsyncGenerator[Any, None]:
        """Stream signals from source"""
        await self.connect()
        self.running = True
        
        try:
            while self.running:
                signal_data = await self.read_signal()
                if signal_data is not None:
                    # Apply filters
                    filtered_data = signal_data
                    for filter_obj in config.filters:
                        filtered_data = await filter_obj.filter(filtered_data)
                        if filtered_data is None:
                            break
                    
                    if filtered_data is not None:
                        yield filtered_data
                
                # Respect sampling rate
                if config.sampling_rate > 0:
                    await asyncio.sleep(1.0 / config.sampling_rate)
        
        finally:
            await self.disconnect()
    
    def stop(self):
        """Stop signal streaming"""
        self.running = False

class GPIOSignalHandler(SignalHandler):
    """Handler for GPIO signals"""
    
    def __init__(self, config: SignalConfig):
        super().__init__(config)
        self.gpio_pin = int(config.source_identifier.replace("GPIO_", ""))
        self.gpio_initialized = False
    
    async def connect(self):
        """Initialize GPIO connection"""
        try:
            # Mock GPIO implementation for testing
            # In production: import RPi.GPIO as GPIO
            self.gpio_initialized = True
            logger.info(f"Connected to GPIO pin {self.gpio_pin}")
        except Exception as e:
            logger.error(f"Failed to connect to GPIO: {str(e)}")
            raise
    
    async def disconnect(self):
        """Cleanup GPIO connection"""
        if self.gpio_initialized:
            # Mock cleanup
            # In production: GPIO.cleanup()
            self.gpio_initialized = False
            logger.info(f"Disconnected from GPIO pin {self.gpio_pin}")
    
    async def read_signal(self) -> Optional[Dict]:
        """Read GPIO signal state"""
        if not self.gpio_initialized:
            return None
        
        try:
            # Mock GPIO reading
            # In production: value = GPIO.input(self.gpio_pin)
            import random
            value = random.choice([0, 1])  # Mock GPIO value
            
            return {
                "pin": self.gpio_pin,
                "value": value,
                "timestamp": time.time(),
                "voltage": value * 3.3  # Mock voltage
            }
        
        except Exception as e:
            logger.error(f"Error reading GPIO signal: {str(e)}")
            return None

class NetworkSignalHandler(SignalHandler):
    """Handler for network packet signals"""
    
    def __init__(self, config: SignalConfig):
        super().__init__(config)
        self.host, self.port = config.source_identifier.split(":")
        self.port = int(self.port)
        self.socket = None
    
    async def connect(self):
        """Connect to network signal source"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind((self.host, self.port))
            self.socket.settimeout(0.1)  # Non-blocking with timeout
            logger.info(f"Connected to network source {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to network source: {str(e)}")
            raise
    
    async def disconnect(self):
        """Close network connection"""
        if self.socket:
            self.socket.close()
            self.socket = None
            logger.info(f"Disconnected from network source {self.host}:{self.port}")
    
    async def read_signal(self) -> Optional[Dict]:
        """Read network signal packet"""
        if not self.socket:
            return None
        
        try:
            data, addr = self.socket.recvfrom(1024)
            
            # Parse packet (assuming simple format)
            packet_data = self._parse_packet(data)
            
            return {
                "source_address": addr,
                "packet_size": len(data),
                "timestamp": time.time(),
                "data": packet_data
            }
        
        except socket.timeout:
            return None
        except Exception as e:
            logger.error(f"Error reading network signal: {str(e)}")
            return None
    
    def _parse_packet(self, data: bytes) -> Dict:
        """Parse network packet data"""
        try:
            # Try to parse as JSON first
            return json.loads(data.decode('utf-8'))
        except:
            # Fallback to raw bytes
            return {
                "raw_data": data.hex(),
                "length": len(data)
            }

class SerialSignalHandler(SignalHandler):
    """Handler for serial communication signals"""
    
    def __init__(self, config: SignalConfig):
        super().__init__(config)
        self.device_path = config.source_identifier
        self.serial_connection = None
        self.baud_rate = config.metadata.get("baud_rate", 9600) if config.metadata else 9600
    
    async def connect(self):
        """Connect to serial device"""
        if not SERIAL_AVAILABLE:
            logger.warning("pyserial not available - using mock serial connection")
            self.serial_connection = MockSerialConnection()
            return
            
        try:
            self.serial_connection = serial.Serial(
                self.device_path,
                self.baud_rate,
                timeout=0.1  # Non-blocking with timeout
            )
            logger.info(f"Connected to serial device {self.device_path}")
        except Exception as e:
            logger.error(f"Failed to connect to serial device: {str(e)}")
            # Fallback to mock connection
            self.serial_connection = MockSerialConnection()
            # Create mock connection for testing
            self.serial_connection = MockSerialConnection()
    
    async def disconnect(self):
        """Close serial connection"""
        if self.serial_connection:
            self.serial_connection.close()
            self.serial_connection = None
            logger.info(f"Disconnected from serial device {self.device_path}")
    
    async def read_signal(self) -> Optional[Dict]:
        """Read serial signal data"""
        if not self.serial_connection:
            return None
        
        try:
            if self.serial_connection.in_waiting > 0:
                data = self.serial_connection.readline()
                
                return {
                    "raw_data": data.decode('utf-8', errors='ignore').strip(),
                    "timestamp": time.time(),
                    "bytes_received": len(data)
                }
        
        except Exception as e:
            logger.error(f"Error reading serial signal: {str(e)}")
            return None
        
        return None

class MockSerialConnection:
    """Mock serial connection for testing"""
    
    def __init__(self):
        self.in_waiting = 0
        self.message_counter = 0
    
    def readline(self) -> bytes:
        """Mock readline that returns test data"""
        self.message_counter += 1
        if self.message_counter % 10 == 0:  # Send data every 10th call
            return f"SIGNAL_DATA_{self.message_counter}\n".encode('utf-8')
        return b""
    
    def close(self):
        """Mock close method"""
        pass

class CANBusSignalHandler(SignalHandler):
    """Handler for CAN Bus signals"""
    
    def __init__(self, config: SignalConfig):
        super().__init__(config)
        self.interface = config.source_identifier
        self.can_bus = None
    
    async def connect(self):
        """Connect to CAN Bus"""
        try:
            # Mock CAN bus connection
            # In production: import can; self.can_bus = can.interface.Bus(...)
            self.can_bus = MockCANBus()
            logger.info(f"Connected to CAN Bus interface {self.interface}")
        except Exception as e:
            logger.error(f"Failed to connect to CAN Bus: {str(e)}")
            raise
    
    async def disconnect(self):
        """Disconnect from CAN Bus"""
        if self.can_bus:
            self.can_bus.shutdown()
            self.can_bus = None
            logger.info(f"Disconnected from CAN Bus interface {self.interface}")
    
    async def read_signal(self) -> Optional[Dict]:
        """Read CAN Bus message"""
        if not self.can_bus:
            return None
        
        try:
            message = self.can_bus.recv(timeout=0.1)
            if message:
                return {
                    "arbitration_id": message.arbitration_id,
                    "data": message.data.hex(),
                    "timestamp": message.timestamp,
                    "is_extended_id": message.is_extended_id
                }
        
        except Exception as e:
            logger.error(f"Error reading CAN Bus signal: {str(e)}")
            return None
        
        return None

class MockCANBus:
    """Mock CAN Bus for testing"""
    
    def __init__(self):
        self.message_counter = 0
    
    def recv(self, timeout: float):
        """Mock receive method"""
        import random
        
        self.message_counter += 1
        if random.random() < 0.1:  # 10% chance of message
            return MockCANMessage(
                arbitration_id=0x123,
                data=bytes([random.randint(0, 255) for _ in range(8)]),
                timestamp=time.time()
            )
        return None
    
    def shutdown(self):
        """Mock shutdown method"""
        pass

class MockCANMessage:
    """Mock CAN message"""
    
    def __init__(self, arbitration_id: int, data: bytes, timestamp: float):
        self.arbitration_id = arbitration_id
        self.data = data
        self.timestamp = timestamp
        self.is_extended_id = False

class HighPrecisionTimer:
    """High-precision timing for signal events"""
    
    def __init__(self):
        self.reference_time = time.time_ns()
    
    def get_precise_timestamp(self) -> float:
        """Get high-precision timestamp in seconds"""
        current_time_ns = time.time_ns()
        return (current_time_ns - self.reference_time) / 1_000_000_000.0
    
    def get_microsecond_precision(self) -> float:
        """Get timestamp with microsecond precision"""
        return time.time_ns() / 1_000_000_000.0

class SignalProcessingWorkflow:
    """Main workflow orchestrator for signal processing"""
    
    def __init__(self):
        self.signal_handlers = {
            SignalType.GPIO: GPIOSignalHandler,
            SignalType.NETWORK_PACKET: NetworkSignalHandler,
            SignalType.SERIAL: SerialSignalHandler,
            SignalType.CAN_BUS: CANBusSignalHandler,
        }
        self.active_sessions = {}
        self.precision_timer = HighPrecisionTimer()
    
    async def start_signal_processing(self, test_session_id: str, signal_config: SignalConfig) -> AsyncGenerator[SignalEvent, None]:
        """Start processing signals for a test session"""
        if signal_config.signal_type not in self.signal_handlers:
            raise ValueError(f"Unsupported signal type: {signal_config.signal_type}")
        
        handler_class = self.signal_handlers[signal_config.signal_type]
        handler = handler_class(signal_config)
        
        self.active_sessions[test_session_id] = handler
        
        try:
            async for raw_signal in handler.stream_signals(signal_config):
                # Get high-precision timestamp
                precise_timestamp = self.precision_timer.get_precise_timestamp()
                
                # Create signal event
                signal_event = SignalEvent(
                    id=str(uuid.uuid4()),
                    test_session_id=test_session_id,
                    timestamp=precise_timestamp,
                    signal_type=signal_config.signal_type,
                    signal_data=raw_signal,
                    source_identifier=signal_config.source_identifier,
                    precision_us=1.0  # 1 microsecond precision
                )
                
                yield signal_event
        
        finally:
            if test_session_id in self.active_sessions:
                del self.active_sessions[test_session_id]
    
    def stop_signal_processing(self, test_session_id: str):
        """Stop signal processing for a test session"""
        if test_session_id in self.active_sessions:
            handler = self.active_sessions[test_session_id]
            handler.stop()
            del self.active_sessions[test_session_id]
            logger.info(f"Stopped signal processing for session {test_session_id}")
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active signal processing sessions"""
        return list(self.active_sessions.keys())

class SignalCorrelationEngine:
    """Engine for correlating signals with detection events"""
    
    def __init__(self, tolerance_ms: int = 100):
        self.tolerance_ms = tolerance_ms
        self.signal_buffer = {}
    
    def add_signal_event(self, signal_event: SignalEvent):
        """Add signal event to correlation buffer"""
        session_id = signal_event.test_session_id
        if session_id not in self.signal_buffer:
            self.signal_buffer[session_id] = []
        
        self.signal_buffer[session_id].append(signal_event)
        
        # Keep buffer size manageable (last 1000 signals)
        if len(self.signal_buffer[session_id]) > 1000:
            self.signal_buffer[session_id] = self.signal_buffer[session_id][-1000:]
    
    def find_correlated_signal(self, detection_timestamp: float, test_session_id: str) -> Optional[SignalEvent]:
        """Find signal event that correlates with detection timestamp"""
        if test_session_id not in self.signal_buffer:
            return None
        
        tolerance_seconds = self.tolerance_ms / 1000.0
        best_match = None
        min_time_diff = float('inf')
        
        for signal_event in self.signal_buffer[test_session_id]:
            time_diff = abs(signal_event.timestamp - detection_timestamp)
            
            if time_diff <= tolerance_seconds and time_diff < min_time_diff:
                min_time_diff = time_diff
                best_match = signal_event
        
        return best_match
    
    def calculate_timing_metrics(self, detection_timestamp: float, signal_timestamp: float) -> Dict:
        """Calculate timing metrics between detection and signal"""
        latency_ms = abs(detection_timestamp - signal_timestamp) * 1000
        
        return {
            "latency_ms": latency_ms,
            "detection_timestamp": detection_timestamp,
            "signal_timestamp": signal_timestamp,
            "within_tolerance": latency_ms <= self.tolerance_ms,
            "precision_rating": "high" if latency_ms <= 10 else "medium" if latency_ms <= 50 else "low"
        }

# Example signal configurations
def create_gpio_config(pin: int, sampling_rate: float = 1000.0) -> SignalConfig:
    """Create GPIO signal configuration"""
    return SignalConfig(
        signal_type=SignalType.GPIO,
        source_identifier=f"GPIO_{pin}",
        sampling_rate=sampling_rate,
        buffer_size=100,
        precision_mode=True,
        filters=[
            DebounceFilter(min_interval_ms=10),
            NoiseFilter(threshold=0.1)
        ]
    )

def create_network_config(host: str, port: int) -> SignalConfig:
    """Create network signal configuration"""
    return SignalConfig(
        signal_type=SignalType.NETWORK_PACKET,
        source_identifier=f"{host}:{port}",
        sampling_rate=0,  # Event-driven
        buffer_size=1000,
        precision_mode=True,
        filters=[]
    )

def create_serial_config(device: str, baud_rate: int = 9600) -> SignalConfig:
    """Create serial signal configuration"""
    return SignalConfig(
        signal_type=SignalType.SERIAL,
        source_identifier=device,
        sampling_rate=100.0,
        buffer_size=500,
        precision_mode=True,
        filters=[
            DebounceFilter(min_interval_ms=5)
        ],
        metadata={"baud_rate": baud_rate}
    )

def create_can_config(interface: str) -> SignalConfig:
    """Create CAN Bus signal configuration"""
    return SignalConfig(
        signal_type=SignalType.CAN_BUS,
        source_identifier=interface,
        sampling_rate=0,  # Event-driven
        buffer_size=2000,
        precision_mode=True,
        filters=[
            LowPassFilter(alpha=0.8)
        ]
    )