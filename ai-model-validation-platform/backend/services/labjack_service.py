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

# CRITICAL FIX: Import stream state management to prevent error 2605
try:
    from services.labjack_connection_manager import set_stream_active, is_stream_active
except ImportError:
    logging.warning("Could not import stream state functions - error 2605 prevention disabled")
    def set_stream_active(active: bool):
        pass  # Fallback no-op
    def is_stream_active() -> bool:
        return False  # Fallback - assume no stream

logger = logging.getLogger(__name__)

# Import LabJack helper functions for compatibility
try:
    from services.ljm_helpers import numberToType, numberToDeviceType, numberToConnectionType, numberToIP
    HELPERS_AVAILABLE = True
except ImportError:
    HELPERS_AVAILABLE = False
    logger.warning("LabJack helper functions not available")


# ============================================================================
# LJM Error Code Mapping and Recovery Actions
# ============================================================================
LJM_ERROR_CODES = {
    # Connection errors
    1224: ("DEVICE_NOT_OPEN", "reconnect", "Device handle is not open or has been closed"),
    1227: ("DEVICE_DISCONNECTED", "reconnect", "Device has been disconnected"),
    1230: ("DEVICE_NOT_FOUND", "fail", "No LabJack devices found"),
    1239: ("STREAM_NOT_INITIALIZED", "restart_stream", "Stream not properly initialized"),

    # Stream errors
    1301: ("STREAM_SCAN_OVERLAP", "recover", "Stream buffer overflow - data scanning faster than reading"),
    1302: ("STREAM_SCAN_OVERLAP_VARIANT", "recover", "Stream buffer overflow variant"),
    1303: ("STREAM_SAMPLE_NUM_INVALID", "restart_stream", "Invalid sample number in stream"),
    1304: ("STREAM_OUT_OF_MEMORY", "reduce_rate", "Not enough memory for stream buffer"),
    1305: ("STREAM_BUFFER_FULL", "recover", "Stream buffer is full"),
    1306: ("STREAM_AUTO_TARGET_INVALID", "restart_stream", "Invalid auto-target for stream"),
    1307: ("STREAM_NOT_RUNNING", "restart_stream", "Stream is not currently running"),
    1308: ("STREAM_INVALID_TRIGGER", "restart_stream", "Invalid stream trigger configuration"),

    # USB/Communication errors
    2942: ("USB_INIT_ERROR", "reconnect", "USB initialization failed"),
    2943: ("USB_SEND_ERROR", "retry", "USB send operation failed"),
    2944: ("USB_RECEIVE_ERROR", "retry", "USB receive operation failed"),
    2603: ("RECONNECT_FAILED", "fail", "Device reconnection attempt failed"),
    2605: ("DEVICE_BUSY", "retry", "Device busy with another operation (e.g., streaming)"),

    # Configuration errors
    2360: ("INVALID_ADDRESS", "fail", "Invalid register address"),
    2361: ("INVALID_NAME", "fail", "Invalid register name"),
    2362: ("INVALID_PARAMETER", "fail", "Invalid parameter value"),
    2500: ("TIMEOUT", "retry", "Operation timed out"),

    # Network errors (Ethernet/WiFi)
    1233: ("SOCKET_ERROR", "reconnect", "Socket communication error"),
}


def get_error_info(error) -> Tuple[Optional[int], Optional[str], Optional[str], Optional[str]]:
    """Extract error information from exception.

    Returns:
        (error_code, error_name, action, description)
    """
    error_code = getattr(error, 'errorCode', None)
    error_str = str(error)

    # Try to extract error code from string if not in attribute
    if error_code is None:
        import re
        match = re.search(r'\b(\d{4})\b', error_str)
        if match:
            error_code = int(match.group(1))

    if error_code and error_code in LJM_ERROR_CODES:
        error_name, action, description = LJM_ERROR_CODES[error_code]
        return error_code, error_name, action, description

    # Check if error string contains known error names
    for code, (name, action, desc) in LJM_ERROR_CODES.items():
        if name in error_str.upper():
            return code, name, action, desc

    return error_code, None, None, None


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

        # CRITICAL FIX: Track active sessions to prevent premature disconnection
        self.active_sessions = set()
        self.active_session_count = 0

        # Streaming state (existing bridge/high-level streaming)
        self.streaming = False
        self.stream_thread = None
        self.stream_data_queue = queue.Queue(maxsize=50000)
        self.stream_callbacks = []
        self._stop_streaming = threading.Event()

        # Stream mode state tracking (hardware-level stream mode)
        self._stream_active = False
        self._stream_scan_rate = None
        self._stream_channels = []
        self._stream_scans_per_read = 100
        
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
        
        # Lazy connection flag - do NOT connect during initialization
        self._initialized = True
        
        logger.info("LabJack service initialized (lazy connection - will connect when needed)")
    
    async def connect(self, force_mode: Optional[ConnectionMode] = None, allow_mock: bool = False) -> bool:
        """Connect using environment-aware fallback strategy.
        
        CRITICAL SAFETY CHANGE: No automatic mock fallback for HIL testing.
        Mock mode must be explicitly requested via allow_mock=True.
        
        - On WSL: Bridge → Direct → FAIL (no mock fallback)
        - Else:   Direct → Bridge → FAIL (no mock fallback)
        
        Args:
            force_mode: Force specific connection mode
            allow_mock: Allow fallback to mock mode (DANGEROUS for HIL testing)
        """
        import platform
        is_wsl = platform.system() == "Linux" and "microsoft" in platform.uname().release.lower()

        if force_mode:
            if force_mode == ConnectionMode.MOCK and not allow_mock:
                logger.error("❌ Mock mode requested but not allowed - use allow_mock=True if simulation is intended")
                return False
            return await self._connect_specific_mode(force_mode)

        if is_wsl:
            logger.info("🌐 WSL detected: preferring Windows bridge for LabJack access...")
            if await self._connect_bridge():
                return True
            logger.info("🔌 Bridge failed; attempting direct hardware connection...")
            if await self._connect_direct():
                return True
        else:
            # Native Linux/Windows: try direct first
            logger.info("🔌 Attempting direct hardware connection...")
            if await self._connect_direct():
                return True
            logger.info("🌐 Attempting bridge connection...")
            if await self._connect_bridge():
                return True

        # CRITICAL: NO AUTOMATIC MOCK FALLBACK FOR HIL TESTING
        if allow_mock:
            logger.warning("⚠️ Hardware connection failed - falling back to mock mode (SIMULATION DATA ONLY)")
            return await self._connect_mock()
        else:
            logger.error("❌ LabJack hardware connection failed - HIL testing requires real hardware")
            logger.error("   Available connection methods tried: Bridge, Direct")
            logger.error("   To use simulation mode, explicitly set allow_mock=True")
            self.status = ConnectionStatus.ERROR
            return False
    
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
        """Connect via Windows bridge with HTTP-first approach"""
        try:
            self.status = ConnectionStatus.CONNECTING
            self.statistics["connection_attempts"] += 1

            # Load bridge configuration from environment
            self.bridge_config.host = os.getenv("LABJACK_BRIDGE_HOST", "localhost")
            self.bridge_config.port = int(os.getenv("LABJACK_BRIDGE_PORT", "8080"))

            bridge_url = f"http://{self.bridge_config.host}:{self.bridge_config.port}"

            # Check if requests library is available
            if not REQUESTS_AVAILABLE:
                logger.error("requests library not available - cannot use bridge mode")
                return False

            logger.info(f"🌐 Checking bridge availability at {bridge_url}...")

            # Try HTTP bridge first (check status endpoint)
            try:
                response = requests.get(f"{bridge_url}/status", timeout=5)
                response.raise_for_status()
                status_data = response.json()

                if status_data.get("bridge_active") and status_data.get("connected"):
                    logger.info(f"✅ Bridge is active and connected to hardware")

                    # Store bridge connection info
                    self.bridge_url = bridge_url
                    self.mode = ConnectionMode.BRIDGE
                    self.status = ConnectionStatus.CONNECTED

                    # Get device info from bridge
                    device_info = status_data.get("device_info", {})
                    self.device_info = {
                        "device_type": device_info.get("device_type", "T7"),
                        "connection_type": "HTTP_BRIDGE",
                        "serial_number": device_info.get("serial_number", "UNKNOWN"),
                        "ip_address": "N/A",
                        "port": self.bridge_config.port,
                        "is_mock": False,
                        "interface_type": "HTTP_BRIDGE",
                        "bridge_url": bridge_url,
                        "bridge_active": True
                    }

                    # Start health monitoring
                    self._start_health_monitoring()

                    logger.info(f"✅ LabJack connected via HTTP bridge at {bridge_url}")
                    return True
                else:
                    logger.warning(f"Bridge at {bridge_url} is not ready: bridge_active={status_data.get('bridge_active')}, connected={status_data.get('connected')}")
                    return False

            except requests.RequestException as req_error:
                logger.info(f"HTTP bridge not available at {bridge_url}: {req_error}")
                return False

            # If HTTP works, optionally try WebSocket for streaming
            if WEBSOCKET_AVAILABLE:
                logger.info("HTTP bridge available, setting up WebSocket for streaming...")
                self.bridge_client = LabJackBridgeClient(self.bridge_config)

                if await self.bridge_client.connect():
                    # Setup data callback
                    self.bridge_client.add_data_callback(self._handle_stream_data)
                    logger.info("✅ WebSocket streaming enabled via bridge")
                else:
                    logger.warning("WebSocket setup failed, using HTTP-only mode")
            else:
                logger.info("WebSocket not available, using HTTP-only mode")

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
                from labjack import ljm
                # Newer labjack-ljm releases no longer expose the legacy helper
                # functions (numberToType, etc.). Treat core acquisition helpers as
                # the minimum feature set to keep the official library enabled.
                required_attrs = ("openS", "eReadName", "listAll")
                missing_attrs = [attr for attr in required_attrs if not hasattr(ljm, attr)]
                if missing_attrs:
                    logger.warning(
                        "⚠️ Official LabJack library missing expected attributes: %s",
                        ", ".join(missing_attrs)
                    )
                    ljm = None
                else:
                    # Test if the library can actually load (it might fail due to missing .so file)
                    try:
                        ljm.openS("ANY", "ANY", "ANY")  # This will fail but test library loading
                    except Exception as lib_error:
                        if "libLabJackM.so" in str(lib_error) or "Cannot load" in str(lib_error):
                            logger.warning(
                                "⚠️ Official LabJack library present but cannot load shared library: %s",
                                lib_error
                            )
                            ljm = None  # Force fallback to USB stub
                        else:
                            # Library loaded successfully, the error is connection-related which is expected
                            logger.info("✅ Official LabJack LJM library loaded successfully")
            except (ImportError, AttributeError) as e:
                logger.warning(f"⚠️ Official LabJack LJM library not available: {e}")
                ljm = None

            # If official library failed, use USB stub for direct hardware access
            if ljm is None:
                try:
                    # Import our enhanced USB stub implementation
                    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
                    import labjack_usb_stub as ljm
                    logger.info("🚀 Using enhanced LabJack USB interface for direct hardware access")
                except ImportError as stub_error:
                    logger.error(f"❌ LabJack USB interface import failed: {stub_error}")
                    return False

            logger.info(f"🔄 Connection state transition: {self.status.value} → CONNECTING")
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
            device_type = numberToType(info[0]) if HELPERS_AVAILABLE else f"Device_{info[0]}"
            connection_type = numberToConnectionType(info[1]) if HELPERS_AVAILABLE else f"Connection_{info[1]}"
            serial_number = info[2]

            # Store device info
            self.device_info = {
                "device_type": device_type,
                "connection_type": connection_type,
                "serial_number": serial_number,
                "ip_address": (numberToIP(info[3]) if HELPERS_AVAILABLE else f"IP_{info[3]}") if connection_type in ["ETHERNET", "WIFI"] else "N/A",
                "port": info[4] if connection_type in ["ETHERNET", "WIFI"] else "N/A",
                "max_bytes": info[5],
                "is_mock": False,
                "interface_type": "USB_STUB" if "labjack_usb_stub" in str(type(ljm)) else "OFFICIAL_LJM",
                "handle": self.direct_handle,
                "handle_valid": True
            }

            self.mode = ConnectionMode.DIRECT
            logger.info(f"🔄 Connection state transition: {self.status.value} → CONNECTED")
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
                except Exception as close_error:
                    logger.debug(f"Error closing handle during cleanup: {close_error}")
            
            return False
    
    async def _connect_mock(self) -> bool:
        """Connect using mock interface - ONLY for explicit simulation testing"""
        try:
            if not MockLabJackInterface:
                logger.error("❌ Mock LabJack interface not available")
                return False
            
            self.status = ConnectionStatus.CONNECTING
            self.statistics["connection_attempts"] += 1
            
            self.mock_device = MockLabJackInterface(simulate_device_errors=False)
            self.mock_device.connect()
            
            self.mode = ConnectionMode.MOCK
            self.status = ConnectionStatus.CONNECTED
            
            self._start_health_monitoring()
            
            # CRITICAL WARNING: Make it clear this is simulation
            logger.warning("⚠️⚠️⚠️ SIMULATION MODE ACTIVE - NOT REAL HARDWARE ⚠️⚠️⚠️")
            logger.warning("   All detection events will be SIMULATED DATA")
            logger.warning("   This should NOT be used for HIL validation testing")
            
            # Set device info for mock mode with clear warnings
            self.device_info = {
                "device_type": "T7_SIMULATED",
                "connection_type": "MOCK_SIMULATION",
                "serial_number": "SIMULATION_ONLY",
                "ip_address": "127.0.0.1",
                "port": "MOCK",
                "is_mock": True,
                "is_simulation": True,
                "interface_type": "MOCK_SIMULATION",
                "status": "⚠️ SIMULATION MODE - NOT REAL HARDWARE",
                "warning": "This is simulated data - not suitable for HIL validation"
            }
            return True
            
        except Exception as e:
            logger.error(f"❌ Mock connection failed: {e}")
            self.statistics["errors_count"] += 1
            self.statistics["last_error_time"] = datetime.now()
        
        self.status = ConnectionStatus.ERROR
        return False

    # ============================================================================
    # Error Handling Methods
    # ============================================================================

    def handle_ljm_error(self, error: Exception, context: str = "operation") -> bool:
        """Handle LJM errors with appropriate recovery actions.

        Args:
            error: The exception that occurred
            context: Description of the operation that failed

        Returns:
            True if error was handled and recovery successful, False otherwise
        """
        error_code, error_name, action, description = get_error_info(error)

        if error_code:
            logger.error(f"❌ LJM Error {error_code} ({error_name}) during {context}: {description}")
            self.statistics["errors_count"] += 1
            self.statistics["last_error_time"] = datetime.now()

            # Execute appropriate recovery action
            if action == "reconnect":
                logger.info(f"🔄 Executing recovery action: reconnect")
                return asyncio.run(self._reconnect_on_error())
            elif action == "recover":
                logger.info(f"🔄 Executing recovery action: recover stream overflow")
                return self._recover_stream_overflow()
            elif action == "restart_stream":
                logger.info(f"🔄 Executing recovery action: restart stream")
                return self._restart_stream()
            elif action == "retry":
                logger.info(f"🔄 Executing recovery action: retry operation")
                return True  # Caller should retry
            elif action == "reduce_rate":
                logger.warning(f"⚠️ Recovery action required: reduce sample rate")
                return False  # Caller needs to reduce rate and retry
            elif action == "fail":
                logger.error(f"❌ Fatal error - no automatic recovery available")
                return False
        else:
            logger.error(f"❌ Unknown LJM error during {context}: {error}")
            self.statistics["errors_count"] += 1
            self.statistics["last_error_time"] = datetime.now()

        return False

    def _recover_stream_overflow(self) -> bool:
        """Recover from stream buffer overflow by clearing backlog.

        Returns:
            True if recovery successful
        """
        try:
            if not self._stream_active:
                logger.warning("Cannot recover stream - stream not active")
                return False

            logger.info("🔄 Recovering from stream overflow...")

            # Read and discard backlogged data
            data, backlog, success = self.read_stream_mode()
            if success:
                logger.info(f"✅ Recovered from overflow, discarded {len(data)} samples (backlog: {backlog})")
                return True
            else:
                logger.error("❌ Failed to recover from stream overflow")
                return False

        except Exception as e:
            logger.error(f"❌ Error during stream overflow recovery: {e}")
            return False

    def _restart_stream(self) -> bool:
        """Restart streaming after error.

        Returns:
            True if stream restarted successfully
        """
        try:
            if not self._stream_active:
                logger.warning("Cannot restart stream - stream not active")
                return False

            logger.info("🔄 Restarting stream...")

            # Save current stream configuration
            channels = self._stream_channels.copy()
            scan_rate = self._stream_scan_rate
            scans_per_read = self._stream_scans_per_read

            # Stop stream
            stop_success = self.stop_stream_mode()
            if not stop_success:
                logger.error("❌ Failed to stop stream during restart")
                return False

            # Wait briefly
            time.sleep(0.5)

            # Restart stream with same configuration
            success, actual_rate = self.start_stream_mode(channels, scan_rate, scans_per_read)
            if success:
                logger.info(f"✅ Stream restarted successfully at {actual_rate} Hz")
                return True
            else:
                logger.error("❌ Failed to restart stream")
                return False

        except Exception as e:
            logger.error(f"❌ Error during stream restart: {e}")
            return False

    # ============================================================================

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
                        "device_type": numberToType(info[0]) if HELPERS_AVAILABLE else f"Device_{info[0]}",
                        "connection_type": numberToConnectionType(info[1]) if HELPERS_AVAILABLE else f"Connection_{info[1]}",
                        "serial_number": info[2],
                        "ip_address": numberToIP(info[3]) if HELPERS_AVAILABLE else f"IP_{info[3]}",
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
        if self.mode == ConnectionMode.BRIDGE:
            # Use HTTP bridge for stream configuration
            if hasattr(self, 'bridge_url'):
                try:
                    # Note: Bridge may not have a separate configure endpoint
                    # Configuration might happen in start-stream
                    logger.info(f"Stream configuration will be sent with start-stream for bridge mode")
                    return sample_rate  # Return requested rate, actual rate from start_stream
                except Exception as e:
                    logger.error(f"Bridge configure stream error: {e}")
                    return 0
            # Fallback to WebSocket client
            elif self.bridge_client:
                return await self.bridge_client.configure_stream(channels, sample_rate)
        elif self.mode == ConnectionMode.DIRECT and self.direct_handle:
            try:
                scans_per_read = max(sample_rate // 10, 1)
                success, actual_rate = self.start_stream_mode(channels, sample_rate, scans_per_read)
                if success:
                    return actual_rate
                logger.error("Direct stream configuration failed via start_stream_mode")
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
                # Use HTTP bridge to start stream
                if hasattr(self, 'bridge_url'):
                    try:
                        response = requests.post(
                            f"{self.bridge_url}/stream-start",
                            json={"channels": channels, "sample_rate": sample_rate},
                            timeout=10
                        )
                        response.raise_for_status()
                        result = response.json()
                        success = result.get("success", False)
                        if success:
                            logger.info(f"✅ Bridge streaming started via HTTP")
                            self.streaming = True
                            return True
                        else:
                            logger.error(f"Bridge failed to start stream: {result.get('error', 'Unknown error')}")
                            return False
                    except Exception as e:
                        logger.error(f"HTTP bridge start stream error: {e}")
                        return False
                # Fallback to WebSocket client
                elif self.bridge_client:
                    success = await self.bridge_client.start_stream()
                else:
                    success = False
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
                # Use comprehensive error handler
                error_str = str(e)
                # Ignore benign errors
                if "NO_DATA_AVAILABLE" not in error_str and "not streaming" not in error_str.lower():
                    if self.handle_ljm_error(e, "streaming loop"):
                        # Error handled, continue streaming
                        continue
                    else:
                        # Fatal error, break loop
                        logger.error(f"❌ Fatal streaming error, stopping loop")
                        break

            time.sleep(0.01)  # Small delay
    
    async def stop_stream(self) -> bool:
        """Stop streaming"""
        if not self.streaming:
            return True

        try:
            self.streaming = False
            self._stop_streaming.set()

            if self.mode == ConnectionMode.BRIDGE:
                # Use HTTP bridge to stop stream
                if hasattr(self, 'bridge_url'):
                    try:
                        response = requests.post(
                            f"{self.bridge_url}/stream-stop",
                            timeout=10
                        )
                        response.raise_for_status()
                        result = response.json()
                        if result.get("success"):
                            logger.info("✅ Bridge streaming stopped via HTTP")
                        else:
                            logger.warning(f"Bridge stop stream warning: {result.get('error', 'Unknown')}")
                    except Exception as e:
                        logger.error(f"HTTP bridge stop stream error: {e}")
                # Fallback to WebSocket client
                elif self.bridge_client:
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

        # For HTTP bridge mode, poll the stream-read endpoint
        if self.mode == ConnectionMode.BRIDGE and hasattr(self, 'bridge_url'):
            try:
                response = requests.post(
                    f"{self.bridge_url}/stream-read",
                    json={"max_samples": max_samples},
                    timeout=5
                )
                response.raise_for_status()
                result = response.json()
                if result.get("success"):
                    data = result.get("data", [])
                    logger.debug(f"Read {len(data)} samples from HTTP bridge")
                else:
                    logger.warning(f"Bridge stream read warning: {result.get('error', 'Unknown')}")
            except Exception as e:
                logger.error(f"HTTP bridge stream read error: {e}")
            return data

        # For WebSocket or other modes, use the queue
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
        """Read single voltage value with comprehensive error handling"""
        if self.mode == ConnectionMode.BRIDGE:
            # Use HTTP bridge endpoint for reading
            if hasattr(self, 'bridge_url'):
                try:
                    response = requests.post(
                        f"{self.bridge_url}/read-analog",
                        json={"channel": channel},
                        timeout=5
                    )
                    response.raise_for_status()
                    result = response.json()
                    if result.get("success"):
                        return result.get("value", 0.0)
                    else:
                        logger.error(f"Bridge read failed: {result.get('error', 'Unknown error')}")
                        return 0.0
                except Exception as e:
                    logger.error(f"HTTP bridge read error: {e}")
                    return 0.0
            # Fallback to WebSocket client if available
            elif self.bridge_client:
                return await self.bridge_client.read_single_voltage(channel)
        elif self.mode == ConnectionMode.DIRECT and self.direct_handle:
            # FIX: Skip read if stream is active to prevent error 2605
            if is_stream_active():
                logger.debug(f"Skipping {channel} read - stream active (prevents error 2605)")
                return 0.0
            try:
                if hasattr(self, 'ljm_module') and self.ljm_module:
                    ljm = self.ljm_module
                    return ljm.eReadName(self.direct_handle, channel)
                else:
                    logger.error("LJM module not available for voltage reading")
                    return 0.0
            except Exception as e:
                # Use comprehensive error handler
                if self.handle_ljm_error(e, f"voltage read from {channel}"):
                    # Error was handled successfully, retry operation
                    try:
                        if hasattr(self, 'ljm_module') and self.ljm_module:
                            ljm = self.ljm_module
                            return ljm.eReadName(self.direct_handle, channel)
                    except Exception as retry_error:
                        logger.error(f"Failed to read after recovery: {retry_error}")
                        return 0.0
                return 0.0
        elif self.mode == ConnectionMode.MOCK and self.mock_device:
            voltages = self.mock_device.read_single_voltage()
            return voltages.get(channel, 0.0)

        return 0.0

    async def _reconnect_on_error(self, max_retries: int = 3) -> bool:
        """Attempt automatic reconnection after error 1224.

        Args:
            max_retries: Maximum number of reconnection attempts

        Returns:
            True if reconnection successful
        """
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔄 Reconnection attempt {attempt}/{max_retries}")

                # Close existing handle if present
                if self.direct_handle and hasattr(self, 'ljm_module') and self.ljm_module:
                    try:
                        self.ljm_module.close(self.direct_handle)
                    except Exception as close_error:
                        logger.debug(f"Error closing handle during reconnect: {close_error}")
                    self.direct_handle = None

                # Wait before retry (exponential backoff)
                await asyncio.sleep(min(2 ** (attempt - 1), 10))

                # Attempt reconnection
                if await self._connect_direct():
                    logger.info(f"✅ Reconnection successful on attempt {attempt}")
                    return True

            except Exception as e:
                logger.error(f"Reconnection attempt {attempt} failed: {e}")

        logger.error(f"❌ All {max_retries} reconnection attempts failed")
        self.status = ConnectionStatus.ERROR
        return False

    async def validate_hardware_connection(self) -> bool:
        """Validate that hardware connection is active and healthy.

        CRITICAL FIX: Pre-test validation to ensure hardware is ready.

        Returns:
            True if hardware connection is valid and healthy
        """
        try:
            if self.status != ConnectionStatus.CONNECTED:
                logger.error("❌ Hardware not connected")
                return False

            # FIX: Skip validation read if stream is active to prevent error 2605
            # When streaming is active, attempting a validation read causes device busy error
            # Use global is_stream_active() for consistency across all modules
            if is_stream_active() or getattr(self, '_stream_active', False):
                logger.info("✅ Hardware validation skipped - stream active (connection assumed valid)")
                return True

            if self.mode == ConnectionMode.DIRECT and self.direct_handle:
                # Test read to validate connection
                if hasattr(self, 'ljm_module') and self.ljm_module:
                    ljm = self.ljm_module
                    try:
                        # Read device temperature as validation
                        temp = ljm.eReadName(self.direct_handle, "TEMPERATURE_DEVICE_K")
                        logger.info(f"✅ Hardware validation successful (device temp: {temp:.2f}K)")
                        return True
                    except Exception as e:
                        error_code = getattr(e, 'errorCode', None)
                        error_code_int = int(error_code) if error_code else None
                        logger.error(f"❌ Hardware validation failed: error {error_code}")

                        # Handle device not open (1224) or device busy (2605) with retry
                        if error_code_int == 1224:
                            logger.info("Attempting reconnection for validation (error 1224)...")
                            if await self._reconnect_on_error():
                                return True
                        elif error_code_int == 2605:
                            # Device busy - likely streaming, consider validation successful
                            logger.info("✅ Device busy (error 2605) - streaming active, validation accepted")
                            return True
                        return False
            elif self.mode == ConnectionMode.BRIDGE and self.bridge_client:
                return self.bridge_client.connected
            elif self.mode == ConnectionMode.MOCK:
                return True

            return False

        except Exception as e:
            logger.error(f"Hardware validation error: {e}")
            return False

    # ============================================================================
    # Hardware Stream Mode Methods (Direct LabJack Hardware Streaming)
    # ============================================================================

    def start_stream_mode(
        self,
        channels: List[str],
        scan_rate: int = 200,
        scans_per_read: int = 20
    ) -> Tuple[bool, float]:
        """
        Start LabJack in stream mode for high-speed data acquisition.

        Stream mode provides hardware-timed data acquisition with buffering,
        ideal for continuous monitoring and high-frequency sampling.

        Args:
            channels: List of channel names (e.g., ["AIN0", "AIN1"])
            scan_rate: Desired samples per second (1-100000 Hz)
            scans_per_read: Buffer size (number of scans to read per call)

        Returns:
            (success, actual_scan_rate): Success status and actual achieved scan rate

        Example:
            >>> service = LabJackService()
            >>> await service.connect()
            >>> success, rate = service.start_stream_mode(["AIN0", "AIN1"], 1000)
            >>> print(f"Stream started at {rate} Hz")
        """
        try:
            if not hasattr(self, 'ljm_module') or not self.ljm_module:
                logger.error("LJM module not available for stream mode")
                return False, 0.0

            if not self.direct_handle:
                logger.error("No direct hardware connection available for stream mode")
                return False, 0.0

            ljm = self.ljm_module

            if self._stream_active:
                logger.warning("Stream already active, stopping first")
                self.stop_stream_mode()

            # Convert channel names to addresses
            num_addresses = len(channels)
            try:
                addresses = [ljm.nameToAddress(name)[0] for name in channels]
            except Exception as e:
                logger.error(f"Failed to convert channel names to addresses: {e}")
                return False, 0.0

            # Configure stream settings for optimal performance
            try:
                ljm.eWriteName(self.direct_handle, "STREAM_SETTLING_US", 0)
                ljm.eWriteName(self.direct_handle, "STREAM_RESOLUTION_INDEX", 0)
            except Exception as e:
                logger.warning(f"Could not configure stream settings (non-critical): {e}")

            # Start hardware-timed stream
            try:
                actual_scan_rate = ljm.eStreamStart(
                    self.direct_handle,
                    scans_per_read,
                    num_addresses,
                    addresses,
                    scan_rate
                )
            except Exception as e:
                logger.error(f"Failed to start stream: {e}")
                return False, 0.0

            self._stream_active = True
            self._stream_scan_rate = actual_scan_rate
            self._stream_channels = channels
            self._stream_scans_per_read = scans_per_read

            # CRITICAL FIX: Notify connection manager to prevent error 2605
            set_stream_active(True)

            logger.info(f"✅ Stream started: {actual_scan_rate} Hz, channels={channels}, buffer={scans_per_read} scans")
            return True, actual_scan_rate

        except Exception as e:
            logger.error(f"Failed to start stream mode: {e}")
            return False, 0.0

    def read_stream_mode(self) -> Tuple[List[float], int, bool]:
        """
        Read buffered data from stream.

        This method retrieves data from the LabJack's internal stream buffer.
        It should be called regularly to prevent buffer overflow.

        Returns:
            (data, backlog, success): Buffer data, device backlog count, and success status

        Notes:
            - Data array contains interleaved channel samples
            - Backlog indicates number of scans waiting in device buffer
            - High backlog (>2x scans_per_read) indicates insufficient read rate

        Example:
            >>> data, backlog, success = service.read_stream_mode()
            >>> if success:
            >>>     print(f"Received {len(data)} samples, backlog: {backlog}")
        """
        try:
            if not hasattr(self, 'ljm_module') or not self.ljm_module:
                logger.error("LJM module not available for stream reading")
                return [], 0, False

            ljm = self.ljm_module

            if not self._stream_active:
                logger.error("Cannot read stream - stream not started")
                return [], 0, False

            try:
                result = ljm.eStreamRead(self.direct_handle)
                data = result[0]  # Data array
                backlog = result[1]  # Device backlog

                # Check for buffer overflow warning
                if backlog > self._stream_scans_per_read * 2:
                    logger.warning(f"⚠️ High stream backlog: {backlog} scans - increase read frequency or scans_per_read")

                return data, backlog, True

            except Exception as e:
                # Use comprehensive error handler
                if self.handle_ljm_error(e, "stream read"):
                    # Error handled successfully, try to read again
                    try:
                        result = ljm.eStreamRead(self.direct_handle)
                        return result[0], result[1], True
                    except Exception as retry_error:
                        logger.error(f"Retry after error handling also failed: {retry_error}")
                        return [], 0, False
                return [], 0, False

        except Exception as e:
            logger.error(f"Failed to read stream mode: {e}")
            return [], 0, False

    def stop_stream_mode(self) -> bool:
        """
        Stop stream mode.

        Halts hardware-timed streaming and releases stream resources.
        Any remaining buffered data will be lost.

        Returns:
            bool: True if stream stopped successfully

        Example:
            >>> service.stop_stream_mode()
            >>> print("Stream stopped")
        """
        try:
            if not hasattr(self, 'ljm_module') or not self.ljm_module:
                logger.error("LJM module not available for stopping stream")
                return False

            if not self._stream_active:
                return True  # Already stopped

            ljm = self.ljm_module

            try:
                ljm.eStreamStop(self.direct_handle)
            except Exception as e:
                logger.error(f"Error stopping stream: {e}")
                return False

            self._stream_active = False
            self._stream_scan_rate = None
            self._stream_channels = []

            # CRITICAL FIX: Notify connection manager to allow polling again
            set_stream_active(False)

            logger.info("✅ Stream stopped")
            return True

        except Exception as e:
            logger.error(f"Failed to stop stream mode: {e}")
            return False

    def is_streaming_mode(self) -> bool:
        """
        Check if stream mode is currently active.

        Returns:
            bool: True if stream is active

        Example:
            >>> if service.is_streaming_mode():
            >>>     data, backlog, success = service.read_stream_mode()
        """
        return self._stream_active

    def get_stream_mode_info(self) -> Dict[str, Any]:
        """
        Get current stream configuration and status.

        Returns:
            dict: Stream information including:
                - active: Stream active status
                - scan_rate: Actual scan rate (Hz)
                - channels: List of streaming channels
                - scans_per_read: Buffer size

        Example:
            >>> info = service.get_stream_mode_info()
            >>> print(f"Streaming at {info['scan_rate']} Hz")
        """
        return {
            'active': self._stream_active,
            'scan_rate': self._stream_scan_rate,
            'channels': self._stream_channels.copy() if self._stream_channels else [],
            'scans_per_read': self._stream_scans_per_read
        }

    # ============================================================================

    def get_status(self) -> LabJackStatus:
        """Get comprehensive status with simulation warnings"""
        # Ensure device_info exists
        device_info = getattr(self, 'device_info', {}) if self.status == ConnectionStatus.CONNECTED else {}
        
        # Add clear simulation warnings if in mock mode
        if self.mode == ConnectionMode.MOCK and device_info:
            device_info["simulation_warning"] = "⚠️ SIMULATION MODE ACTIVE - NOT REAL HARDWARE"
            device_info["hil_suitable"] = False
        elif device_info:
            device_info["hil_suitable"] = True
        
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
        """Health monitoring loop with active connection validation"""
        consecutive_failures = 0
        max_failures = 5  # Increased from 3 to allow for transient issues

        while self.status == ConnectionStatus.CONNECTED:
            try:
                self.last_health_check = datetime.now()

                # CRITICAL FIX: Active health check with actual validation
                if self.mode == ConnectionMode.BRIDGE:
                    # Check bridge connection via HTTP
                    if hasattr(self, 'bridge_url'):
                        try:
                            response = requests.get(f"{self.bridge_url}/status", timeout=5)
                            response.raise_for_status()
                            status_data = response.json()
                            if status_data.get("bridge_active") and status_data.get("connected"):
                                consecutive_failures = 0
                                logger.debug(f"🩺 Bridge health check OK")
                            else:
                                consecutive_failures += 1
                                logger.warning(f"⚠️ Bridge not fully connected ({consecutive_failures}/{max_failures})")
                        except Exception as health_error:
                            consecutive_failures += 1
                            logger.warning(f"⚠️ Bridge health check failed ({consecutive_failures}/{max_failures}): {health_error}")
                    # Fallback to WebSocket client check
                    elif self.bridge_client and self.bridge_client.connected:
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        logger.warning(f"⚠️ Bridge health check failed ({consecutive_failures}/{max_failures})")

                elif self.mode == ConnectionMode.DIRECT and self.direct_handle:
                    # FIX: Skip health check during active streaming to prevent error 2605
                    if is_stream_active():
                        logger.debug("🩺 Health check skipped - stream active (prevents error 2605)")
                        consecutive_failures = 0  # Don't count as failure during streaming
                        time.sleep(30)
                        continue
                    # Read device temperature as health check
                    try:
                        if hasattr(self, 'ljm_module') and self.ljm_module:
                            ljm = self.ljm_module
                            # Read a register to validate connection
                            temp = ljm.eReadName(self.direct_handle, "TEMPERATURE_DEVICE_K")
                            logger.debug(f"🩺 Health check OK: device temp = {temp:.2f}K")
                            consecutive_failures = 0
                    except Exception as health_error:
                        consecutive_failures += 1
                        error_code, error_name, action, description = get_error_info(health_error)
                        logger.warning(f"⚠️ Health check failed ({consecutive_failures}/{max_failures}): error {error_code} ({error_name})")

                        # CRITICAL: Handle consecutive failures
                        if consecutive_failures >= max_failures:
                            # Check if sessions are active before marking as error
                            active_count = getattr(self, 'active_session_count', 0)
                            if active_count > 0:
                                logger.error(f"❌ Health check failed {max_failures} times with {active_count} active sessions")
                                logger.info("🔄 Attempting automatic recovery to preserve sessions...")
                                # Use error handler for recovery
                                if self.handle_ljm_error(health_error, "health check"):
                                    logger.info("✅ Health check recovery successful")
                                    consecutive_failures = 0
                                else:
                                    logger.error("❌ Health check recovery failed")
                                    self.status = ConnectionStatus.ERROR
                                    break
                            else:
                                logger.info(f"Health check failed {max_failures} times with no active sessions - marking as error")
                                self.status = ConnectionStatus.ERROR
                                break

                elif self.mode == ConnectionMode.MOCK:
                    # Mock is always healthy
                    consecutive_failures = 0

                time.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    self.status = ConnectionStatus.ERROR
                    break
    
    def stop_session_monitoring(self, session_id: str) -> bool:
        """Stop monitoring for a specific session without disconnecting hardware.
        
        CRITICAL FIX: This method stops session-specific monitoring while
        preserving the underlying hardware connection for other sessions.
        
        Args:
            session_id: Session identifier to stop monitoring for
            
        Returns:
            True if session monitoring stopped successfully
        """
        try:
            logger.info(f"🔄 Stopping session monitoring for {session_id} (preserving connection)")
            
            # Track session removal from active sessions
            if hasattr(self, 'active_sessions') and session_id in self.active_sessions:
                self.active_sessions.discard(session_id)
                logger.info(f"📝 Removed {session_id} from active sessions")
            
            # Update active session count
            if hasattr(self, 'active_session_count') and self.active_session_count > 0:
                self.active_session_count -= 1
                logger.info(f"📊 Active session count: {self.active_session_count}")
            
            # Remove session-specific callbacks if they exist
            # Note: This is a session-specific operation, not a global disconnect
            session_callbacks = getattr(self, f'_session_callbacks_{session_id}', [])
            for callback in session_callbacks:
                if callback in self.stream_callbacks:
                    self.stream_callbacks.remove(callback)
            
            # Clear session-specific callback references
            if hasattr(self, f'_session_callbacks_{session_id}'):
                delattr(self, f'_session_callbacks_{session_id}')
            
            # Log connection preservation status
            remaining_sessions = getattr(self, 'active_session_count', 0)
            if remaining_sessions > 0:
                logger.info(f"🔌 Hardware connection preserved for {remaining_sessions} remaining sessions")
            else:
                logger.info("🔌 Hardware connection idle but preserved for future sessions")
            
            logger.info(f"✅ Session monitoring stopped for {session_id} (hardware connection preserved)")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping session monitoring for {session_id}: {e}")
            return False
    
    def start_session(self, session_id: str) -> bool:
        """Register a new session using the LabJack connection.

        CRITICAL: Call this when a test session starts to prevent premature disconnection.

        Args:
            session_id: Unique session identifier

        Returns:
            True if session registered successfully
        """
        try:
            if not hasattr(self, 'active_sessions'):
                self.active_sessions = set()
                self.active_session_count = 0

            self.active_sessions.add(session_id)
            self.active_session_count = len(self.active_sessions)

            logger.info(f"📝 Session {session_id} started (active sessions: {self.active_session_count})")
            logger.info(f"🔌 Connection preserved for active session")

            return True

        except Exception as e:
            logger.error(f"Error starting session {session_id}: {e}")
            return False

    def end_session(self, session_id: str) -> bool:
        """Unregister a session when it completes.

        Args:
            session_id: Session identifier to end

        Returns:
            True if session ended successfully
        """
        try:
            if not hasattr(self, 'active_sessions'):
                return True

            if session_id in self.active_sessions:
                self.active_sessions.discard(session_id)
                self.active_session_count = len(self.active_sessions)
                logger.info(f"📝 Session {session_id} ended (remaining sessions: {self.active_session_count})")

            # Only allow disconnect if no sessions remain
            if self.active_session_count == 0:
                logger.info("✅ All sessions complete - connection can be safely closed if needed")
            else:
                logger.info(f"🔌 Connection preserved for {self.active_session_count} remaining sessions")

            return True

        except Exception as e:
            logger.error(f"Error ending session {session_id}: {e}")
            return False

    async def disconnect(self, force: bool = False):
        """Disconnect from LabJack hardware completely.

        CRITICAL FIX: Prevents disconnection while sessions are active unless forced.
        For session-specific cleanup, use stop_session_monitoring() instead.

        Args:
            force: Force disconnection even if sessions are active (DANGEROUS)
        """
        try:
            # CRITICAL FIX: Block disconnect if sessions are active
            active_count = getattr(self, 'active_session_count', 0)
            if active_count > 0 and not force:
                logger.error(f"❌ DISCONNECT BLOCKED: {active_count} sessions still active")
                logger.error("   Connection must remain open for active test sessions")
                logger.error("   Use end_session() to properly close sessions first")
                logger.error("   Or use force=True to override (may break active tests)")
                return False

            if force and active_count > 0:
                logger.warning(f"🚨 FORCE DISCONNECT: Closing connection despite {active_count} active sessions")
                logger.warning("   This may cause DEVICE_NOT_OPEN errors in active tests!")

            logger.info("🔌 Proceeding with hardware disconnect")

            if self.streaming:
                await self.stop_stream()

            if self.mode == ConnectionMode.BRIDGE and self.bridge_client:
                self.bridge_client.disconnect()
            elif self.mode == ConnectionMode.DIRECT and self.direct_handle:
                if hasattr(self, 'ljm_module') and self.ljm_module:
                    ljm = self.ljm_module
                    ljm.close(self.direct_handle)
                    logger.info("🔌 Hardware connection closed")
            elif self.mode == ConnectionMode.MOCK and self.mock_device:
                self.mock_device.disconnect()

            self.status = ConnectionStatus.DISCONNECTED
            self.direct_handle = None

            # Clear session tracking
            if hasattr(self, 'active_sessions'):
                self.active_sessions.clear()
                self.active_session_count = 0

            # Cleanup threads
            if self.health_thread and self.health_thread.is_alive():
                self.health_thread.join(timeout=5)

            self.executor.shutdown(wait=False)

            logger.info("✅ LabJack hardware fully disconnected")
            return True

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            return False


# Global service instance
_labjack_service: Optional[LabJackService] = None


def get_labjack_service() -> LabJackService:
    """Get global LabJack service instance (lazy initialization - no connection)"""
    global _labjack_service
    if _labjack_service is None:
        _labjack_service = LabJackService()
        logger.info("LabJack service instance created (disconnected, ready for connection)")
        logger.info("⚠️ Service configured for fail-fast HIL mode - no automatic mock fallback")
    return _labjack_service


async def initialize_labjack_service(config: Optional[LabJackConfig] = None, auto_connect: bool = False) -> bool:
    """Initialize LabJack service (optionally connect immediately)"""
    global _labjack_service
    _labjack_service = LabJackService(config)
    
    if auto_connect:
        logger.info("Auto-connecting LabJack service during initialization...")
        return await _labjack_service.connect()
    else:
        logger.info("LabJack service initialized (connection deferred until needed)")
        return True


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
