"""
Enhanced LabJack Service with Bridge Integration

This service provides LabJack data acquisition through multiple connection modes:
1. Bridge Mode: Communicates with Windows LabJack bridge via HTTP/WebSocket
2. Direct Mode: Direct LabJack hardware connection (Linux/Windows)
3. Mock Mode: Simulated LabJack for development/testing

Features:
- Automatic fallback: Bridge → Direct → Mock
- WebSocket streaming from bridge service
- Connection health monitoring
- Real-time signal validation
- Thread-safe operations
- Comprehensive error handling
"""

import asyncio
import logging
import json
import time
import threading
import os
import queue
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

# Optional imports
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logging.warning("websocket-client not available, bridge mode disabled")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logging.warning("requests not available, bridge mode disabled")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logging.warning("numpy not available, some features may be limited")

# Import configuration
try:
    from config.labjack_env_config import load_config_from_env, LabJackConfig
except ImportError:
    logging.warning("LabJack configuration not available")
    LabJackConfig = None
    load_config_from_env = None

# Import mock LabJack for fallback
try:
    from services.mock_labjack import MockLabJackInterface, get_mock_labjack_status
except ImportError:
    logging.warning("Mock LabJack not available")
    MockLabJackInterface = None
    get_mock_labjack_status = None

logger = logging.getLogger(__name__)


class ConnectionMode(Enum):
    """LabJack connection modes"""
    BRIDGE = "bridge"      # Windows bridge via HTTP/WebSocket
    DIRECT = "direct"      # Direct hardware connection
    MOCK = "mock"          # Simulated hardware


class ConnectionStatus(Enum):
    """Connection status states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RETRYING = "retrying"


@dataclass
class BridgeConfig:
    """Configuration for Windows bridge connection"""
    host: str = "localhost"
    port: int = 8080
    http_timeout: int = 10
    websocket_timeout: int = 30
    reconnect_interval: int = 5
    max_reconnect_attempts: int = 10
    health_check_interval: int = 30
    
    @property
    def http_url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    @property
    def websocket_url(self) -> str:
        return f"ws://{self.host}:{self.port}/ws"


@dataclass
class LabJackStatus:
    """Comprehensive LabJack system status"""
    mode: ConnectionMode
    status: ConnectionStatus
    connected: bool
    device_info: Dict[str, Any]
    streaming: bool
    sample_rate: int
    channels: List[str]
    voltage_threshold: float
    last_data_time: Optional[datetime]
    error_message: Optional[str]
    statistics: Dict[str, Any]


class LabJackBridgeClient:
    """Client for communicating with Windows LabJack bridge service"""
    
    def __init__(self, config: BridgeConfig):
        self.config = config
        self.session = requests.Session()
        self.session.timeout = config.http_timeout
        self.ws_client = None
        self.ws_thread = None
        self.connected = False
        self.data_queue = queue.Queue(maxsize=10000)
        self.callbacks = []
        self.reconnect_count = 0
        self._stop_event = threading.Event()
        
    def add_data_callback(self, callback: Callable[[List[float]], None]):
        """Add callback for received data"""
        self.callbacks.append(callback)
        
    def _notify_callbacks(self, data: List[float]):
        """Notify all callbacks with new data"""
        for callback in self.callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in data callback: {e}")
    
    async def connect(self) -> bool:
        """Connect to bridge service"""
        try:
            # Test HTTP connection
            response = self.session.get(f"{self.config.http_url}/status")
            response.raise_for_status()
            
            # Start WebSocket connection
            if await self._connect_websocket():
                self.connected = True
                self.reconnect_count = 0
                logger.info(f"✅ Connected to LabJack bridge at {self.config.http_url}")
                return True
                
        except requests.RequestException as e:
            logger.error(f"Failed to connect to bridge: {e}")
        except Exception as e:
            logger.error(f"Unexpected error connecting to bridge: {e}")
            
        return False
    
    async def _connect_websocket(self) -> bool:
        """Establish WebSocket connection"""
        try:
            def on_message(ws, message):
                try:
                    data = json.loads(message)
                    if data.get("type") == "stream_data":
                        stream_data = data.get("data", [])
                        self.data_queue.put(stream_data)
                        self._notify_callbacks(stream_data)
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}")
            
            def on_error(ws, error):
                logger.error(f"WebSocket error: {error}")
                
            def on_close(ws, close_status_code, close_msg):
                logger.info("WebSocket connection closed")
                self.connected = False
                if not self._stop_event.is_set():
                    self._schedule_reconnect()
            
            def on_open(ws):
                logger.info("WebSocket connection established")
                
            self.ws_client = websocket.WebSocketApp(
                self.config.websocket_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            # Start WebSocket in separate thread
            self.ws_thread = threading.Thread(
                target=self.ws_client.run_forever,
                kwargs={"ping_interval": 30, "ping_timeout": 10},
                daemon=True
            )
            self.ws_thread.start()
            
            # Wait for connection
            for _ in range(50):  # Wait up to 5 seconds
                if self.ws_client.sock and self.ws_client.sock.connected:
                    return True
                await asyncio.sleep(0.1)
            
            return False
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            return False
    
    def _schedule_reconnect(self):
        """Schedule reconnection attempt"""
        if self.reconnect_count < self.config.max_reconnect_attempts:
            self.reconnect_count += 1
            timer = threading.Timer(
                self.config.reconnect_interval,
                self._reconnect
            )
            timer.daemon = True
            timer.start()
            logger.info(f"Scheduling reconnection attempt {self.reconnect_count}")
    
    def _reconnect(self):
        """Attempt to reconnect"""
        if not self._stop_event.is_set():
            asyncio.create_task(self.connect())
    
    async def get_device_info(self) -> Dict[str, Any]:
        """Get device information from bridge"""
        try:
            response = self.session.get(f"{self.config.http_url}/device-info")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get device info: {e}")
            return {}
    
    async def configure_stream(self, channels: List[str], sample_rate: int) -> int:
        """Configure streaming through bridge"""
        try:
            payload = {
                "channels": channels,
                "sample_rate": sample_rate
            }
            response = self.session.post(
                f"{self.config.http_url}/configure-stream",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            return result.get("actual_sample_rate", sample_rate)
        except Exception as e:
            logger.error(f"Failed to configure stream: {e}")
            return 0
    
    async def start_stream(self) -> bool:
        """Start streaming through bridge"""
        try:
            response = self.session.post(f"{self.config.http_url}/start-stream")
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to start stream: {e}")
            return False
    
    async def stop_stream(self) -> bool:
        """Stop streaming through bridge"""
        try:
            response = self.session.post(f"{self.config.http_url}/stop-stream")
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to stop stream: {e}")
            return False
    
    def get_stream_data(self, timeout: float = 0.1) -> List[float]:
        """Get streaming data from queue"""
        data = []
        try:
            while True:
                item = self.data_queue.get(timeout=timeout)
                data.extend(item)
                self.data_queue.task_done()
        except queue.Empty:
            pass
        return data
    
    async def read_single_voltage(self, channel: str) -> float:
        """Read single voltage value"""
        try:
            response = self.session.get(f"{self.config.http_url}/read-voltage/{channel}")
            response.raise_for_status()
            result = response.json()
            return result.get("voltage", 0.0)
        except Exception as e:
            logger.error(f"Failed to read voltage: {e}")
            return 0.0
    
    def disconnect(self):
        """Disconnect from bridge"""
        self._stop_event.set()
        self.connected = False
        
        if self.ws_client:
            self.ws_client.close()
            
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=5)
            
        self.session.close()
        logger.info("Disconnected from LabJack bridge")


class LabJackService:
    """Enhanced LabJack service with bridge integration and fallback modes"""
    
    def __init__(self, config: Optional[LabJackConfig] = None):
        self.config = config or load_config_from_env() if load_config_from_env else None
        self.bridge_config = BridgeConfig()
        
        # Connection management - Start in DISCONNECTED state, not MOCK
        self.mode = ConnectionMode.DIRECT  # Try DIRECT mode first
        self.status = ConnectionStatus.DISCONNECTED
        self.bridge_client = None
        self.direct_handle = None
        self.mock_device = None
        
        # Streaming state
        self.streaming = False
        self.stream_thread = None
        self.stream_data_queue = queue.Queue(maxsize=50000)
        self.stream_callbacks = []
        self._stop_streaming = threading.Event()
        
        # Statistics and monitoring
        self.statistics = {
            "samples_received": 0,
            "errors_count": 0,
            "connection_attempts": 0,
            "last_error_time": None,
            "uptime_start": datetime.now()
        }
        
        # Health monitoring
        self.health_thread = None
        self.last_health_check = datetime.now()
        
        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info("LabJack service initialized")
    
    async def connect(self, force_mode: Optional[ConnectionMode] = None) -> bool:
        """Connect using fallback strategy: Bridge → Direct → Mock"""
        
        if force_mode:
            return await self._connect_specific_mode(force_mode)
        
        # Try Direct mode FIRST (prioritize real hardware)
        logger.info("🔌 Attempting direct hardware connection...")
        if await self._connect_direct():
            return True
        
        # Try Bridge mode second
        logger.info("🌐 Attempting bridge connection...")
        if await self._connect_bridge():
            return True
        
        # Fallback to Mock mode LAST
        logger.info("🔧 Falling back to mock mode...")
        return await self._connect_mock()
    
    async def _connect_specific_mode(self, mode: ConnectionMode) -> bool:
        """Connect using specific mode"""
        if mode == ConnectionMode.BRIDGE:
            return await self._connect_bridge()
        elif mode == ConnectionMode.DIRECT:
            return await self._connect_direct()
        elif mode == ConnectionMode.MOCK:
            return await self._connect_mock()
        return False
    
    async def _connect_bridge(self) -> bool:
        """Connect via Windows bridge"""
        try:
            self.status = ConnectionStatus.CONNECTING
            self.statistics["connection_attempts"] += 1
            
            # Load bridge configuration from environment
            self.bridge_config.host = os.getenv("LABJACK_BRIDGE_HOST", "localhost")
            self.bridge_config.port = int(os.getenv("LABJACK_BRIDGE_PORT", "8080"))
            
            self.bridge_client = LabJackBridgeClient(self.bridge_config)
            
            if await self.bridge_client.connect():
                self.mode = ConnectionMode.BRIDGE
                self.status = ConnectionStatus.CONNECTED
                
                # Setup data callback
                self.bridge_client.add_data_callback(self._handle_stream_data)
                
                # Start health monitoring
                self._start_health_monitoring()
                
                logger.info("✅ LabJack connected via bridge")
                return True
                
        except Exception as e:
            logger.error(f"Bridge connection failed: {e}")
            self.statistics["errors_count"] += 1
            self.statistics["last_error_time"] = datetime.now()
        
        self.status = ConnectionStatus.ERROR
        return False
    
    async def _connect_direct(self) -> bool:
        """Connect directly to LabJack hardware"""
        try:
            # Import LabJack library with fallback to USB stub
            ljm = None
            
            # First, try to import the official LabJack library
            try:
                import labjack.ljm as ljm
                # Test if this is the real library by checking for key functions
                if hasattr(ljm, 'numberToType') and hasattr(ljm, 'openS'):
                    # Test if the library can actually load (it might fail due to missing .so file)
                    try:
                        ljm.openS("ANY", "ANY", "ANY")  # This will fail but test library loading
                    except Exception as lib_error:
                        if "libLabJackM.so" in str(lib_error) or "Cannot load" in str(lib_error):
                            logger.warning(f"⚠️ Official LabJack library present but cannot load shared library: {lib_error}")
                            ljm = None  # Force fallback to USB stub
                        else:
                            # Library loaded successfully, the error is connection-related which is expected
                            logger.info("✅ Official LabJack LJM library loaded successfully")
                else:
                    logger.warning("⚠️ Official LabJack library missing required functions")
                    ljm = None
            except (ImportError, AttributeError) as e:
                logger.warning(f"⚠️ Official LabJack LJM library not available: {e}")
                ljm = None
            
            # If official library failed, use USB stub for direct hardware access
            if ljm is None:
                try:
                    # Import our enhanced USB stub implementation
                    import sys
                    import os
                    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
                    import labjack_usb_stub as ljm
                    logger.info("🚀 Using enhanced LabJack USB interface for direct hardware access")
                except ImportError as stub_error:
                    logger.error(f"❌ LabJack USB interface import failed: {stub_error}")
                    return False
            
            self.status = ConnectionStatus.CONNECTING
            self.statistics["connection_attempts"] += 1
            
            # Store reference to the LJM module for later use
            self.ljm_module = ljm
            
            # Open device - try USB first since we know it's connected via USB/IP
            try:
                # Try T7 via USB first (this should work with our USB stub)
                logger.info("🔌 Attempting to connect to LabJack T7 via USB/IP...")
                self.direct_handle = ljm.openS("T7", "USB", "ANY")
                logger.info("✅ Successfully connected to T7 via USB interface")
            except Exception as usb_error:
                logger.warning(f"USB connection attempt failed: {usb_error}")
                # Try with ANY parameters as fallback
                try:
                    logger.info("🔌 Attempting fallback connection with ANY parameters...")
                    self.direct_handle = ljm.openS("ANY", "ANY", "ANY")
                    logger.info("✅ Successfully connected with fallback method")
                except Exception as any_error:
                    logger.error(f"All connection methods failed: {any_error}")
                    raise any_error
            
            # Verify connection and get device info
            info = ljm.getHandleInfo(self.direct_handle)
            device_type = ljm.numberToType(info[0])
            connection_type = ljm.numberToConnectionType(info[1])
            serial_number = info[2]
            
            # Store device info
            self.device_info = {
                "device_type": device_type,
                "connection_type": connection_type,
                "serial_number": serial_number,
                "ip_address": ljm.numberToIP(info[3]) if connection_type in ["ETHERNET", "WIFI"] else "N/A",
                "port": info[4] if connection_type in ["ETHERNET", "WIFI"] else "N/A",
                "max_bytes": info[5],
                "is_mock": False,
                "interface_type": "USB_STUB" if "labjack_usb_stub" in str(type(ljm)) else "OFFICIAL_LJM"
            }
            
            self.mode = ConnectionMode.DIRECT
            self.status = ConnectionStatus.CONNECTED
            
            self._start_health_monitoring()
            
            logger.info(f"✅ LabJack connected directly - {device_type} (S/N: {serial_number}) via {connection_type}")
            logger.info(f"📡 Interface: {self.device_info['interface_type']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Direct connection failed: {e}")
            self.statistics["errors_count"] += 1
            self.statistics["last_error_time"] = datetime.now()
            self.status = ConnectionStatus.ERROR
            
            # Clean up handle if it was created
            if hasattr(self, 'direct_handle') and self.direct_handle:
                try:
                    if hasattr(self, 'ljm_module') and self.ljm_module:
                        self.ljm_module.close(self.direct_handle)
                    self.direct_handle = None
                except:
                    pass
            
            return False
    
    async def _connect_mock(self) -> bool:
        """Connect using mock interface"""
        try:
            if not MockLabJackInterface:
                logger.error("Mock LabJack interface not available")
                return False
            
            self.status = ConnectionStatus.CONNECTING
            self.statistics["connection_attempts"] += 1
            
            self.mock_device = MockLabJackInterface(simulate_device_errors=False)
            self.mock_device.connect()
            
            self.mode = ConnectionMode.MOCK
            self.status = ConnectionStatus.CONNECTED
            
            self._start_health_monitoring()
            
            logger.info("✅ LabJack connected in mock mode (simulation)")
            # Set device info for mock mode
            self.device_info = {
                "device_type": "T7_SIMULATED",
                "connection_type": "MOCK",
                "serial_number": "MOCK_12345",
                "ip_address": "127.0.0.1",
                "port": "MOCK",
                "is_mock": True,
                "interface_type": "MOCK_SIMULATION",
                "status": "Connected in simulation mode - hardware testing available"
            }
            return True
            
        except Exception as e:
            logger.error(f"Mock connection failed: {e}")
            self.statistics["errors_count"] += 1
            self.statistics["last_error_time"] = datetime.now()
        
        self.status = ConnectionStatus.ERROR
        return False
    
    def _handle_stream_data(self, data: List[float]):
        """Handle streaming data from bridge"""
        try:
            self.stream_data_queue.put(data, block=False)
            self.statistics["samples_received"] += len(data)
            
            # Notify callbacks
            for callback in self.stream_callbacks:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in stream callback: {e}")
                    
        except queue.Full:
            logger.warning("Stream data queue full, dropping samples")
    
    def add_stream_callback(self, callback: Callable[[List[float]], None]):
        """Add callback for streaming data"""
        self.stream_callbacks.append(callback)
    
    def remove_stream_callback(self, callback: Callable[[List[float]], None]):
        """Remove streaming callback"""
        if callback in self.stream_callbacks:
            self.stream_callbacks.remove(callback)
    
    async def get_device_info(self) -> Dict[str, Any]:
        """Get device information"""
        if self.mode == ConnectionMode.BRIDGE and self.bridge_client:
            return await self.bridge_client.get_device_info()
        elif self.mode == ConnectionMode.DIRECT and self.direct_handle:
            # Use the stored device info from connection
            if hasattr(self, 'device_info') and self.device_info:
                return self.device_info
            # Fallback to reading from device
            try:
                if hasattr(self, 'ljm_module') and self.ljm_module:
                    ljm = self.ljm_module
                    info = ljm.getHandleInfo(self.direct_handle)
                    return {
                        "device_type": ljm.numberToType(info[0]),
                        "connection_type": ljm.numberToConnectionType(info[1]),
                        "serial_number": info[2],
                        "ip_address": ljm.numberToIP(info[3]),
                        "port": info[4],
                        "is_mock": False
                    }
                else:
                    logger.error("LJM module not available for device info")
                    return {"error": "LJM module not available"}
            except Exception as e:
                logger.error(f"Failed to get device info: {e}")
                return {}
        elif self.mode == ConnectionMode.MOCK and self.mock_device:
            return self.mock_device.get_device_info()
        
        return {"error": "Not connected"}
    
    async def configure_stream(self, channels: List[str], sample_rate: int) -> int:
        """Configure streaming"""
        if self.mode == ConnectionMode.BRIDGE and self.bridge_client:
            return await self.bridge_client.configure_stream(channels, sample_rate)
        elif self.mode == ConnectionMode.DIRECT and self.direct_handle:
            try:
                if hasattr(self, 'ljm_module') and self.ljm_module:
                    ljm = self.ljm_module
                    addresses, types = ljm.namesToAddresses(len(channels), channels)
                    actual_rate = ljm.eStreamStart(
                        self.direct_handle,
                        sample_rate,
                        len(addresses),
                        addresses,
                        sample_rate // 10  # Scans per read
                    )
                    return actual_rate
                else:
                    logger.error("LJM module not available for stream configuration")
                    return 0
            except Exception as e:
                logger.error(f"Failed to configure direct stream: {e}")
                return 0
        elif self.mode == ConnectionMode.MOCK and self.mock_device:
            return self.mock_device.configure_stream(sample_rate)
        
        return 0
    
    async def start_stream(self, channels: List[str], sample_rate: int = 1000) -> bool:
        """Start streaming data acquisition"""
        if self.streaming:
            logger.warning("Stream already active")
            return True
        
        try:
            actual_rate = await self.configure_stream(channels, sample_rate)
            if actual_rate <= 0:
                logger.error("Failed to configure stream")
                return False
            
            if self.mode == ConnectionMode.BRIDGE:
                success = await self.bridge_client.start_stream()
            elif self.mode == ConnectionMode.DIRECT:
                success = True  # Already started in configure_stream
                self._start_direct_streaming()
            elif self.mode == ConnectionMode.MOCK:
                success = True  # Mock streaming handled automatically
            else:
                success = False
            
            if success:
                self.streaming = True
                logger.info(f"✅ Streaming started at {actual_rate} Hz")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to start stream: {e}")
            return False
    
    def _start_direct_streaming(self):
        """Start direct streaming thread"""
        self._stop_streaming.clear()
        self.stream_thread = threading.Thread(
            target=self._direct_stream_loop,
            daemon=True
        )
        self.stream_thread.start()
    
    def _direct_stream_loop(self):
        """Direct streaming data acquisition loop"""
        if not (hasattr(self, 'ljm_module') and self.ljm_module):
            logger.error("LJM module not available for streaming")
            return
            
        ljm = self.ljm_module
        
        while not self._stop_streaming.is_set() and self.streaming:
            try:
                data, backlog, error = ljm.eStreamRead(self.direct_handle)
                if data:
                    self._handle_stream_data(data)
                
                if error:
                    logger.warning(f"Stream read error: {error}")
                
            except Exception as e:
                # Handle different types of LJM errors
                error_str = str(e)
                if hasattr(e, '__class__') and "LJMError" in str(e.__class__):
                    if "NO_DATA_AVAILABLE" not in error_str and "not streaming" not in error_str.lower():
                        logger.error(f"Stream read error: {e}")
                        break
                else:
                    logger.error(f"Stream loop error: {e}")
                    break
            
            time.sleep(0.01)  # Small delay
    
    async def stop_stream(self) -> bool:
        """Stop streaming"""
        if not self.streaming:
            return True
        
        try:
            self.streaming = False
            self._stop_streaming.set()
            
            if self.mode == ConnectionMode.BRIDGE and self.bridge_client:
                await self.bridge_client.stop_stream()
            elif self.mode == ConnectionMode.DIRECT and self.direct_handle:
                if hasattr(self, 'ljm_module') and self.ljm_module:
                    ljm = self.ljm_module
                    ljm.eStreamStop(self.direct_handle)
            elif self.mode == ConnectionMode.MOCK and self.mock_device:
                self.mock_device.stop_stream()
            
            if self.stream_thread and self.stream_thread.is_alive():
                self.stream_thread.join(timeout=5)
            
            logger.info("⏹️ Streaming stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop stream: {e}")
            return False
    
    def get_stream_data(self, max_samples: int = 1000) -> List[float]:
        """Get streaming data"""
        data = []
        samples_read = 0
        
        try:
            while samples_read < max_samples:
                try:
                    batch = self.stream_data_queue.get_nowait()
                    data.extend(batch)
                    samples_read += len(batch)
                    self.stream_data_queue.task_done()
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"Error getting stream data: {e}")
        
        return data
    
    async def read_single_voltage(self, channel: str) -> float:
        """Read single voltage value"""
        if self.mode == ConnectionMode.BRIDGE and self.bridge_client:
            return await self.bridge_client.read_single_voltage(channel)
        elif self.mode == ConnectionMode.DIRECT and self.direct_handle:
            try:
                if hasattr(self, 'ljm_module') and self.ljm_module:
                    ljm = self.ljm_module
                    return ljm.eReadName(self.direct_handle, channel)
                else:
                    logger.error("LJM module not available for voltage reading")
                    return 0.0
            except Exception as e:
                logger.error(f"Failed to read voltage from {channel}: {e}")
                return 0.0
        elif self.mode == ConnectionMode.MOCK and self.mock_device:
            voltages = self.mock_device.read_single_voltage()
            return voltages.get(channel, 0.0)
        
        return 0.0
    
    def get_status(self) -> LabJackStatus:
        """Get comprehensive status"""
        # Ensure device_info exists
        device_info = getattr(self, 'device_info', {}) if self.status == ConnectionStatus.CONNECTED else {}
        
        return LabJackStatus(
            mode=self.mode,
            status=self.status,
            connected=self.status == ConnectionStatus.CONNECTED,
            device_info=device_info,
            streaming=self.streaming,
            sample_rate=self.config.sample_rate if self.config else 1000,
            channels=self.config.channels if self.config else ["AIN0", "AIN1"],
            voltage_threshold=self.config.voltage_threshold if self.config else 2.5,
            last_data_time=None,  # Could track this
            error_message=None,   # Could track last error
            statistics=self.statistics.copy()
        )
    
    def _start_health_monitoring(self):
        """Start health monitoring thread"""
        if self.health_thread and self.health_thread.is_alive():
            return
        
        self.health_thread = threading.Thread(
            target=self._health_monitor_loop,
            daemon=True
        )
        self.health_thread.start()
    
    def _health_monitor_loop(self):
        """Health monitoring loop"""
        while self.status == ConnectionStatus.CONNECTED:
            try:
                self.last_health_check = datetime.now()
                
                # Check connection health based on mode
                if self.mode == ConnectionMode.BRIDGE:
                    # Could ping bridge service
                    pass
                elif self.mode == ConnectionMode.DIRECT:
                    # Could read a test register
                    pass
                elif self.mode == ConnectionMode.MOCK:
                    # Mock is always healthy
                    pass
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                break
    
    async def disconnect(self):
        """Disconnect from LabJack"""
        try:
            if self.streaming:
                await self.stop_stream()
            
            if self.mode == ConnectionMode.BRIDGE and self.bridge_client:
                self.bridge_client.disconnect()
            elif self.mode == ConnectionMode.DIRECT and self.direct_handle:
                if hasattr(self, 'ljm_module') and self.ljm_module:
                    ljm = self.ljm_module
                    ljm.close(self.direct_handle)
            elif self.mode == ConnectionMode.MOCK and self.mock_device:
                self.mock_device.disconnect()
            
            self.status = ConnectionStatus.DISCONNECTED
            self.mode = ConnectionMode.MOCK  # Reset to mock
            
            # Cleanup threads
            if self.health_thread and self.health_thread.is_alive():
                self.health_thread.join(timeout=5)
            
            self.executor.shutdown(wait=False)
            
            logger.info("🔌 LabJack disconnected")
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")


# Global service instance
_labjack_service: Optional[LabJackService] = None


def get_labjack_service() -> LabJackService:
    """Get global LabJack service instance"""
    global _labjack_service
    if _labjack_service is None:
        _labjack_service = LabJackService()
    return _labjack_service


async def initialize_labjack_service(config: Optional[LabJackConfig] = None) -> bool:
    """Initialize and connect LabJack service"""
    global _labjack_service
    _labjack_service = LabJackService(config)
    return await _labjack_service.connect()


# Export key classes and functions
__all__ = [
    "LabJackService",
    "ConnectionMode", 
    "ConnectionStatus",
    "BridgeConfig",
    "LabJackStatus",
    "get_labjack_service",
    "initialize_labjack_service"
]