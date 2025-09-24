"""
LabJack Connection Manager - Centralized Device Access

This module provides a singleton connection manager to resolve device conflicts
by ensuring only one LabJack handle is created per device, shared across all
services within the same process.

Solves the LJME_DEVICE_CURRENTLY_CLAIMED_BY_ANOTHER_PROCESS error by:
1. Creating a single shared device handle
2. Providing thread-safe access methods
3. Coordinating access across multiple services
"""

import logging
import threading
import time
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import uuid

# LabJack imports with fallback
try:
    import labjack.ljm as ljm
    LJM_AVAILABLE = True
    LJM_TYPE = "OFFICIAL"
except ImportError:
    try:
        # Fallback to USB stub
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        import labjack_usb_stub as ljm
        LJM_AVAILABLE = True
        LJM_TYPE = "USB_STUB"
    except ImportError:
        LJM_AVAILABLE = False
        LJM_TYPE = "NONE"
        ljm = None

# Helper imports
try:
    from services.ljm_helpers import numberToType, numberToConnectionType, numberToIP
    HELPERS_AVAILABLE = True
except ImportError:
    HELPERS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection states for the LabJack device"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


@dataclass
class DeviceInfo:
    """LabJack device information"""
    device_type: str
    connection_type: str
    serial_number: int
    ip_address: Optional[str]
    port: Optional[int]
    firmware_version: str
    hardware_version: str
    ljm_type: str
    connected_at: datetime


class LabJackConnectionManager:
    """
    Singleton connection manager for LabJack devices
    
    Resolves device conflicts by providing a single shared handle
    across all services within the same process.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
    
    def __init__(self):
        # Prevent re-initialization of singleton
        if hasattr(self, '_initialized'):
            return
        
        # Connection state
        self._handle: Optional[int] = None
        self._device_info: Optional[DeviceInfo] = None
        self._connection_state = ConnectionState.DISCONNECTED
        self._connection_lock = threading.RLock()
        self._last_error: Optional[str] = None
        
        # Statistics
        self._stats = {
            "connection_attempts": 0,
            "successful_connections": 0,
            "failed_connections": 0,
            "total_operations": 0,
            "last_operation_time": None,
            "uptime_start": None
        }
        
        # Configuration
        self._auto_reconnect = True
        self._reconnect_delay = 5.0
        self._max_reconnect_attempts = 3
        
        self._initialized = True
        logger.info(f"🔧 LabJack Connection Manager initialized (LJM: {LJM_TYPE})")
    
    @classmethod
    def get_instance(cls) -> 'LabJackConnectionManager':
        """Get the singleton instance"""
        return cls()
    
    def connect(self, device_type: str = "ANY", connection_type: str = "ANY", 
                identifier: str = "ANY", force_reconnect: bool = False) -> bool:
        """
        Connect to LabJack device with shared handle management
        
        Args:
            device_type: Device type ("T7", "U6", "ANY", etc.)
            connection_type: Connection type ("USB", "ETHERNET", "WIFI", "ANY")
            identifier: Device identifier (serial number, IP, or "ANY")
            force_reconnect: Force reconnection even if already connected
        
        Returns:
            True if connected successfully
        """
        if not LJM_AVAILABLE:
            logger.error("❌ LabJack LJM library not available")
            return False
        
        with self._connection_lock:
            # Check if already connected
            if (self._connection_state == ConnectionState.CONNECTED and 
                self._handle is not None and not force_reconnect):
                logger.debug("✅ Already connected to LabJack device")
                return True
            
            # Disconnect existing connection if forcing reconnect
            if force_reconnect and self._handle is not None:
                self._disconnect_internal()
            
            self._connection_state = ConnectionState.CONNECTING
            self._stats["connection_attempts"] += 1
            
            try:
                logger.info(f"🔌 Connecting to LabJack {device_type} via {connection_type}...")
                
                # Open device - this creates the exclusive handle
                self._handle = ljm.openS(device_type, connection_type, identifier)
                
                if self._handle is None or self._handle <= 0:
                    raise ValueError("Invalid handle returned from LabJack")
                
                # Get device information
                device_info_tuple = ljm.getHandleInfo(self._handle)
                device_type_num, connection_type_num, serial_number, ip_number, port, max_bytes = device_info_tuple
                
                # Convert to readable strings
                if HELPERS_AVAILABLE:
                    device_type_str = numberToType(device_type_num)
                    connection_type_str = numberToConnectionType(connection_type_num)
                    ip_str = numberToIP(ip_number) if connection_type_str in ["ETHERNET", "WIFI"] else None
                else:
                    device_type_str = f"DeviceType_{device_type_num}"
                    connection_type_str = f"ConnectionType_{connection_type_num}"
                    ip_str = f"IP_{ip_number}" if connection_type_num in [3, 4] else None
                
                # Get version information
                try:
                    firmware_version = str(ljm.eReadName(self._handle, "FIRMWARE_VERSION"))
                    hardware_version = str(ljm.eReadName(self._handle, "HARDWARE_VERSION"))
                except Exception as e:
                    logger.warning(f"Could not read version info: {e}")
                    firmware_version = "Unknown"
                    hardware_version = "Unknown"
                
                # Store device information
                self._device_info = DeviceInfo(
                    device_type=device_type_str,
                    connection_type=connection_type_str,
                    serial_number=serial_number,
                    ip_address=ip_str,
                    port=port if connection_type_str in ["ETHERNET", "WIFI"] else None,
                    firmware_version=firmware_version,
                    hardware_version=hardware_version,
                    ljm_type=LJM_TYPE,
                    connected_at=datetime.now()
                )
                
                # Update connection state
                self._connection_state = ConnectionState.CONNECTED
                self._stats["successful_connections"] += 1
                self._stats["uptime_start"] = datetime.now()
                self._last_error = None
                
                logger.info(f"✅ Connected to {device_type_str} S/N:{serial_number} via {connection_type_str}")
                if ip_str:
                    logger.info(f"📡 IP Address: {ip_str}:{port}")
                logger.info(f"🔧 Firmware: {firmware_version}, Hardware: {hardware_version}")
                
                return True
                
            except Exception as e:
                error_msg = f"Connection failed: {e}"
                if hasattr(e, 'errorCode') and hasattr(ljm, 'errorToString'):
                    try:
                        error_msg = f"LJM Error {e.errorCode}: {ljm.errorToString(e.errorCode)}"
                    except:
                        pass
                
                logger.error(f"❌ {error_msg}")
                self._connection_state = ConnectionState.ERROR
                self._stats["failed_connections"] += 1
                self._last_error = error_msg
                
                # Clean up failed handle
                if self._handle is not None:
                    try:
                        ljm.close(self._handle)
                    except:
                        pass
                    self._handle = None
                
                return False
    
    def disconnect(self) -> bool:
        """Disconnect from LabJack device"""
        with self._connection_lock:
            return self._disconnect_internal()
    
    def _disconnect_internal(self) -> bool:
        """Internal disconnect method (assumes lock is held)"""
        try:
            if self._handle is not None:
                ljm.close(self._handle)
                self._handle = None
                logger.info("🔌 LabJack device disconnected")
            
            self._connection_state = ConnectionState.DISCONNECTED
            self._device_info = None
            self._stats["uptime_start"] = None
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error during disconnect: {e}")
            self._connection_state = ConnectionState.ERROR
            return False
    
    def is_connected(self) -> bool:
        """Check if device is connected"""
        return (self._connection_state == ConnectionState.CONNECTED and 
                self._handle is not None)
    
    def get_shared_handle(self) -> Optional[int]:
        """
        Get the shared LabJack handle
        
        WARNING: This handle should NEVER be closed by calling services.
        Use the connection manager's methods for all operations.
        """
        if not self.is_connected():
            return None
        return self._handle
    
    def read_voltage(self, channel: str) -> Optional[float]:
        """
        Thread-safe voltage reading
        
        Args:
            channel: Analog input channel (e.g., "AIN0", "AIN1")
        
        Returns:
            Voltage value or None if read failed
        """
        with self._connection_lock:
            if not self.is_connected():
                logger.warning(f"Cannot read {channel}: device not connected")
                return None
            
            try:
                voltage = ljm.eReadName(self._handle, channel)
                self._stats["total_operations"] += 1
                self._stats["last_operation_time"] = datetime.now()
                return voltage
                
            except Exception as e:
                logger.error(f"❌ Failed to read voltage from {channel}: {e}")
                # Check if this is a connection error
                if "HANDLE_NOT_OPEN" in str(e) or "NO_DEVICES_FOUND" in str(e):
                    self._connection_state = ConnectionState.ERROR
                return None
    
    def read_multiple_voltages(self, channels: List[str]) -> Dict[str, float]:
        """
        Thread-safe multiple voltage reading
        
        Args:
            channels: List of analog input channels
        
        Returns:
            Dictionary mapping channel names to voltage values
        """
        with self._connection_lock:
            results = {}
            
            if not self.is_connected():
                logger.warning("Cannot read voltages: device not connected")
                return results
            
            try:
                # Use batch read if available
                if hasattr(ljm, 'eReadNames'):
                    values = ljm.eReadNames(self._handle, len(channels), channels)
                    results = dict(zip(channels, values))
                else:
                    # Fallback to individual reads
                    for channel in channels:
                        try:
                            results[channel] = ljm.eReadName(self._handle, channel)
                        except Exception as e:
                            logger.error(f"Failed to read {channel}: {e}")
                            results[channel] = 0.0
                
                self._stats["total_operations"] += len(channels)
                self._stats["last_operation_time"] = datetime.now()
                
            except Exception as e:
                logger.error(f"❌ Failed to read multiple voltages: {e}")
                if "HANDLE_NOT_OPEN" in str(e):
                    self._connection_state = ConnectionState.ERROR
            
            return results
    
    def write_voltage(self, channel: str, voltage: float) -> bool:
        """
        Thread-safe voltage writing (for DAC channels)
        
        Args:
            channel: Output channel (e.g., "DAC0", "DAC1")
            voltage: Voltage value to write
        
        Returns:
            True if write successful
        """
        with self._connection_lock:
            if not self.is_connected():
                logger.warning(f"Cannot write to {channel}: device not connected")
                return False
            
            try:
                ljm.eWriteName(self._handle, channel, voltage)
                self._stats["total_operations"] += 1
                self._stats["last_operation_time"] = datetime.now()
                return True
                
            except Exception as e:
                logger.error(f"❌ Failed to write voltage to {channel}: {e}")
                if "HANDLE_NOT_OPEN" in str(e):
                    self._connection_state = ConnectionState.ERROR
                return False
    
    def configure_channel(self, channel: str, **config) -> bool:
        """
        Configure channel settings (range, resolution, etc.)
        
        Args:
            channel: Channel to configure
            **config: Configuration parameters
        
        Returns:
            True if configuration successful
        """
        with self._connection_lock:
            if not self.is_connected():
                logger.warning(f"Cannot configure {channel}: device not connected")
                return False
            
            try:
                for setting, value in config.items():
                    register_name = f"{channel}_{setting.upper()}"
                    ljm.eWriteName(self._handle, register_name, value)
                
                self._stats["total_operations"] += len(config)
                logger.debug(f"✅ Configured {channel} with {config}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Failed to configure {channel}: {e}")
                return False
    
    def get_device_info(self) -> Optional[Dict[str, Any]]:
        """Get device information"""
        if self._device_info is None:
            return None
        
        return {
            "device_type": self._device_info.device_type,
            "connection_type": self._device_info.connection_type,
            "serial_number": self._device_info.serial_number,
            "ip_address": self._device_info.ip_address,
            "port": self._device_info.port,
            "firmware_version": self._device_info.firmware_version,
            "hardware_version": self._device_info.hardware_version,
            "ljm_type": self._device_info.ljm_type,
            "connected_at": self._device_info.connected_at.isoformat()
        }
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get comprehensive connection status"""
        uptime_seconds = 0
        if self._stats["uptime_start"]:
            uptime_seconds = (datetime.now() - self._stats["uptime_start"]).total_seconds()
        
        return {
            "connected": self.is_connected(),
            "connection_state": self._connection_state.value,
            "device_info": self.get_device_info(),
            "statistics": {
                "connection_attempts": self._stats["connection_attempts"],
                "successful_connections": self._stats["successful_connections"],
                "failed_connections": self._stats["failed_connections"],
                "total_operations": self._stats["total_operations"],
                "uptime_seconds": uptime_seconds,
                "last_operation_time": (self._stats["last_operation_time"].isoformat() 
                                      if self._stats["last_operation_time"] else None)
            },
            "last_error": self._last_error,
            "ljm_available": LJM_AVAILABLE,
            "ljm_type": LJM_TYPE,
            "timestamp": datetime.now().isoformat()
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check and return status"""
        health_status = {
            "healthy": False,
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Check basic connection
            if not self.is_connected():
                health_status["issues"].append("Device not connected")
                health_status["recommendations"].append("Call connect() to establish connection")
            else:
                # Test a simple read operation
                try:
                    voltage = self.read_voltage("AIN0")
                    if voltage is not None:
                        health_status["healthy"] = True
                        health_status["test_voltage"] = voltage
                    else:
                        health_status["issues"].append("Voltage read test failed")
                except Exception as e:
                    health_status["issues"].append(f"Health check read failed: {e}")
        
        except Exception as e:
            health_status["issues"].append(f"Health check error: {e}")
        
        health_status.update(self.get_connection_status())
        return health_status


# Global singleton instance
_connection_manager = None


def get_connection_manager() -> LabJackConnectionManager:
    """Get the global LabJack connection manager instance"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = LabJackConnectionManager()
    return _connection_manager


# Convenience functions for backward compatibility
def connect_labjack(device_type: str = "ANY", connection_type: str = "ANY", 
                   identifier: str = "ANY") -> bool:
    """Connect to LabJack device using shared connection manager"""
    manager = get_connection_manager()
    return manager.connect(device_type, connection_type, identifier)


def disconnect_labjack() -> bool:
    """Disconnect from LabJack device"""
    manager = get_connection_manager()
    return manager.disconnect()


def read_labjack_voltage(channel: str) -> Optional[float]:
    """Read voltage from LabJack channel using shared connection"""
    manager = get_connection_manager()
    return manager.read_voltage(channel)


def is_labjack_connected() -> bool:
    """Check if LabJack device is connected"""
    manager = get_connection_manager()
    return manager.is_connected()


# Export main classes and functions
__all__ = [
    "LabJackConnectionManager",
    "ConnectionState",
    "DeviceInfo",
    "get_connection_manager",
    "connect_labjack",
    "disconnect_labjack", 
    "read_labjack_voltage",
    "is_labjack_connected"
]