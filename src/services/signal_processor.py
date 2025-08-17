"""
Signal Processing Service
Handles GPIO, Network, Serial, and CAN Bus signal inputs with precise timing
"""

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator, Union
from enum import Enum

from src.core.config import settings, SignalConfig
from src.core.exceptions import VRUDetectionException
from src.models.database import SignalType as DBSignalType

logger = logging.getLogger(__name__)


@dataclass
class SignalEvent:
    """Signal event data structure"""
    id: str
    test_session_id: uuid.UUID
    timestamp: float  # High-precision timestamp
    signal_type: str
    signal_data: Dict[str, Any]
    source_identifier: str
    received_at: datetime


class SignalProcessor:
    """Main signal processing coordinator"""
    
    def __init__(self):
        self.handlers: Dict[str, BaseSignalHandler] = {}
        self.active_sessions: Dict[uuid.UUID, SignalSession] = {}
        self.precision_timer = HighPrecisionTimer()
        
    async def initialize(self) -> None:
        """Initialize signal processor and handlers"""
        try:
            logger.info("Initializing Signal Processor...")
            
            # Initialize signal handlers
            self.handlers = {
                DBSignalType.GPIO.value: GPIOSignalHandler(),
                DBSignalType.NETWORK_PACKET.value: NetworkSignalHandler(), 
                DBSignalType.SERIAL.value: SerialSignalHandler(),
                DBSignalType.CAN_BUS.value: CANBusSignalHandler()
            }
            
            # Initialize each handler
            for signal_type, handler in self.handlers.items():
                try:
                    await handler.initialize()
                    logger.info(f"{signal_type} handler initialized successfully")
                except Exception as e:
                    logger.warning(f"Failed to initialize {signal_type} handler: {e}")
            
            # Initialize precision timer
            await self.precision_timer.initialize()
            
            logger.info("Signal Processor initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize signal processor: {e}")
            raise VRUDetectionException(
                "SIGNAL_PROCESSOR_INIT_FAILED",
                "Failed to initialize signal processor",
                details={"error": str(e)}
            )
    
    async def start_signal_session(
        self,
        test_session_id: uuid.UUID,
        signal_configs: List[Dict[str, Any]]
    ) -> str:
        """
        Start a new signal processing session
        
        Args:
            test_session_id: Associated test session ID
            signal_configs: List of signal configuration dictionaries
            
        Returns:
            Session ID for the started signal session
        """
        try:
            session = SignalSession(
                test_session_id=test_session_id,
                processor=self,
                configs=signal_configs
            )
            
            await session.start()
            self.active_sessions[test_session_id] = session
            
            logger.info(f"Signal session started for test session: {test_session_id}")
            return str(test_session_id)
            
        except Exception as e:
            logger.error(f"Failed to start signal session: {e}")
            raise VRUDetectionException(
                "SIGNAL_SESSION_START_FAILED",
                "Failed to start signal session",
                details={"test_session_id": str(test_session_id), "error": str(e)}
            )
    
    async def stop_signal_session(self, test_session_id: uuid.UUID) -> None:
        """Stop and cleanup signal session"""
        try:
            if test_session_id in self.active_sessions:
                session = self.active_sessions[test_session_id]
                await session.stop()
                del self.active_sessions[test_session_id]
                
                logger.info(f"Signal session stopped: {test_session_id}")
            
        except Exception as e:
            logger.error(f"Failed to stop signal session {test_session_id}: {e}")
    
    async def get_signal_events(
        self,
        test_session_id: uuid.UUID,
        since_timestamp: Optional[float] = None
    ) -> List[SignalEvent]:
        """Get signal events for a test session"""
        try:
            if test_session_id in self.active_sessions:
                session = self.active_sessions[test_session_id]
                return await session.get_events(since_timestamp)
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to get signal events: {e}")
            return []
    
    async def cleanup(self) -> None:
        """Cleanup signal processor resources"""
        try:
            # Stop all active sessions
            for test_session_id in list(self.active_sessions.keys()):
                await self.stop_signal_session(test_session_id)
            
            # Cleanup handlers
            for handler in self.handlers.values():
                await handler.cleanup()
            
            logger.info("Signal processor cleanup completed")
            
        except Exception as e:
            logger.error(f"Signal processor cleanup failed: {e}")


class HighPrecisionTimer:
    """High-precision timing for signal correlation"""
    
    def __init__(self):
        self.start_time = None
        self.precision_mode = SignalConfig.HIGH_PRECISION_MODE
        
    async def initialize(self) -> None:
        """Initialize high-precision timer"""
        self.start_time = time.time_ns()  # Nanosecond precision
        logger.info("High-precision timer initialized")
    
    def get_precise_timestamp(self) -> float:
        """Get high-precision timestamp"""
        if self.precision_mode:
            # Nanosecond precision converted to seconds
            current_time_ns = time.time_ns()
            return (current_time_ns - self.start_time) / 1_000_000_000
        else:
            # Standard precision
            return time.time()
    
    def microseconds_since_start(self) -> int:
        """Get microseconds since timer start"""
        current_time_ns = time.time_ns()
        return (current_time_ns - self.start_time) // 1000


class SignalSession:
    """Individual signal processing session"""
    
    def __init__(self, test_session_id: uuid.UUID, processor: SignalProcessor, configs: List[Dict]):
        self.test_session_id = test_session_id
        self.processor = processor
        self.configs = configs
        self.active_streams: List[asyncio.Task] = []
        self.events: List[SignalEvent] = []
        self.running = False
        
    async def start(self) -> None:
        """Start signal processing streams"""
        self.running = True
        
        for config in self.configs:
            signal_type = config.get("signal_type")
            
            if signal_type in self.processor.handlers:
                handler = self.processor.handlers[signal_type]
                
                # Start signal stream
                stream_task = asyncio.create_task(
                    self._process_signal_stream(handler, config)
                )
                self.active_streams.append(stream_task)
    
    async def stop(self) -> None:
        """Stop signal processing streams"""
        self.running = False
        
        # Cancel all active streams
        for task in self.active_streams:
            task.cancel()
        
        # Wait for cleanup
        await asyncio.gather(*self.active_streams, return_exceptions=True)
        self.active_streams.clear()
    
    async def get_events(self, since_timestamp: Optional[float] = None) -> List[SignalEvent]:
        """Get events since specified timestamp"""
        if since_timestamp is None:
            return self.events.copy()
        
        return [
            event for event in self.events 
            if event.timestamp >= since_timestamp
        ]
    
    async def _process_signal_stream(self, handler: 'BaseSignalHandler', config: Dict) -> None:
        """Process signal stream from handler"""
        try:
            async for signal_data in handler.stream_signals(config):
                if not self.running:
                    break
                
                # Create signal event
                event = SignalEvent(
                    id=f"{self.test_session_id}_{uuid.uuid4().hex[:8]}",
                    test_session_id=self.test_session_id,
                    timestamp=self.processor.precision_timer.get_precise_timestamp(),
                    signal_type=config.get("signal_type"),
                    signal_data=signal_data,
                    source_identifier=config.get("source_identifier", "unknown"),
                    received_at=datetime.utcnow()
                )
                
                self.events.append(event)
                
                # Limit event history
                if len(self.events) > 10000:  # Keep last 10k events
                    self.events = self.events[-8000:]  # Remove oldest 2k
                    
        except asyncio.CancelledError:
            logger.info(f"Signal stream cancelled for {config.get('signal_type')}")
        except Exception as e:
            logger.error(f"Signal stream error: {e}")


class BaseSignalHandler(ABC):
    """Base class for signal handlers"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the signal handler"""
        pass
    
    @abstractmethod
    async def stream_signals(self, config: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream signals based on configuration"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup handler resources"""
        pass


class GPIOSignalHandler(BaseSignalHandler):
    """GPIO signal handler for Raspberry Pi and similar"""
    
    def __init__(self):
        self.gpio_available = False
        self.gpio_lib = None
        
    async def initialize(self) -> None:
        """Initialize GPIO handler"""
        try:
            # Try to import GPIO library
            if settings.MOCK_SIGNAL_PROCESSOR:
                self.gpio_available = False
                logger.info("GPIO handler initialized in mock mode")
                return
            
            try:
                import RPi.GPIO as GPIO
                self.gpio_lib = GPIO
                GPIO.setmode(GPIO.BCM)
                self.gpio_available = True
                logger.info("GPIO handler initialized successfully")
            except (ImportError, RuntimeError):
                # Not on Raspberry Pi or GPIO not available
                self.gpio_available = False
                logger.warning("GPIO not available - using mock mode")
                
        except Exception as e:
            logger.error(f"GPIO handler initialization failed: {e}")
            self.gpio_available = False
    
    async def stream_signals(self, config: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream GPIO signals"""
        if not self.gpio_available:
            # Mock GPIO signals
            async for signal in self._mock_gpio_signals(config):
                yield signal
            return
        
        try:
            pin = int(config.get("source_identifier", "21"))  # Default to GPIO 21
            sampling_rate = config.get("sampling_rate", 1000.0)
            
            # Setup GPIO pin
            self.gpio_lib.setup(pin, self.gpio_lib.IN, pull_up_down=self.gpio_lib.PUD_DOWN)
            
            previous_state = self.gpio_lib.input(pin)
            
            while True:
                current_state = self.gpio_lib.input(pin)
                
                # Detect state change
                if current_state != previous_state:
                    yield {
                        "pin": pin,
                        "state": current_state,
                        "edge": "rising" if current_state else "falling",
                        "voltage": 3.3 if current_state else 0.0
                    }
                    previous_state = current_state
                
                # Sampling delay
                await asyncio.sleep(1.0 / sampling_rate)
                
        except Exception as e:
            logger.error(f"GPIO streaming error: {e}")
    
    async def _mock_gpio_signals(self, config: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate mock GPIO signals for testing"""
        import random
        
        pin = int(config.get("source_identifier", "21"))
        state = False
        
        while True:
            # Random state changes
            if random.random() < 0.1:  # 10% chance of state change
                state = not state
                yield {
                    "pin": pin,
                    "state": state,
                    "edge": "rising" if state else "falling",
                    "voltage": 3.3 if state else 0.0
                }
            
            await asyncio.sleep(0.1)  # 10Hz sampling
    
    async def cleanup(self) -> None:
        """Cleanup GPIO resources"""
        if self.gpio_available and self.gpio_lib:
            try:
                self.gpio_lib.cleanup()
            except Exception as e:
                logger.error(f"GPIO cleanup error: {e}")


class NetworkSignalHandler(BaseSignalHandler):
    """Network packet signal handler"""
    
    async def initialize(self) -> None:
        """Initialize network handler"""
        logger.info("Network signal handler initialized")
    
    async def stream_signals(self, config: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream network signals"""
        # Mock implementation
        async for signal in self._mock_network_signals(config):
            yield signal
    
    async def _mock_network_signals(self, config: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate mock network signals"""
        import random
        
        source_ip = config.get("source_identifier", "192.168.1.100")
        
        while True:
            # Simulate random network packets
            if random.random() < 0.3:  # 30% chance of packet
                yield {
                    "source_ip": source_ip,
                    "packet_type": random.choice(["UDP", "TCP", "ICMP"]),
                    "payload_size": random.randint(64, 1500),
                    "sequence": random.randint(1, 65535)
                }
            
            await asyncio.sleep(0.05)  # 20Hz sampling
    
    async def cleanup(self) -> None:
        """Cleanup network resources"""
        pass


class SerialSignalHandler(BaseSignalHandler):
    """Serial port signal handler"""
    
    async def initialize(self) -> None:
        """Initialize serial handler"""
        logger.info("Serial signal handler initialized")
    
    async def stream_signals(self, config: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream serial signals"""
        # Mock implementation
        async for signal in self._mock_serial_signals(config):
            yield signal
    
    async def _mock_serial_signals(self, config: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate mock serial signals"""
        import random
        
        port = config.get("source_identifier", "/dev/ttyUSB0")
        
        while True:
            # Simulate random serial data
            if random.random() < 0.2:  # 20% chance of data
                yield {
                    "port": port,
                    "data": f"SENSOR_{random.randint(100, 999)}",
                    "bytes_received": random.randint(1, 32),
                    "baud_rate": 115200
                }
            
            await asyncio.sleep(0.1)  # 10Hz sampling
    
    async def cleanup(self) -> None:
        """Cleanup serial resources"""
        pass


class CANBusSignalHandler(BaseSignalHandler):
    """CAN Bus signal handler"""
    
    async def initialize(self) -> None:
        """Initialize CAN Bus handler"""
        logger.info("CAN Bus signal handler initialized")
    
    async def stream_signals(self, config: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream CAN Bus signals"""
        # Mock implementation
        async for signal in self._mock_can_signals(config):
            yield signal
    
    async def _mock_can_signals(self, config: Dict) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate mock CAN signals"""
        import random
        
        interface = config.get("source_identifier", "can0")
        
        while True:
            # Simulate random CAN messages
            if random.random() < 0.4:  # 40% chance of message
                yield {
                    "interface": interface,
                    "can_id": random.randint(0x100, 0x7FF),
                    "data": [random.randint(0, 255) for _ in range(8)],
                    "dlc": 8,
                    "extended": False
                }
            
            await asyncio.sleep(0.02)  # 50Hz sampling
    
    async def cleanup(self) -> None:
        """Cleanup CAN Bus resources"""
        pass