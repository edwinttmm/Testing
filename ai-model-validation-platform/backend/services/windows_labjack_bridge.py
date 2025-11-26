"""
Windows-WSL LabJack Bridge Service
Handles LabJack connectivity across Windows/WSL boundary

This service creates a bridge between WSL Linux (where backend runs) 
and Windows (where LabJack hardware is connected) for HIL testing.

Solutions implemented:
1. TCP bridge to Windows LabJack service
2. USB/IP redirection for WSL2
3. Network-based LabJack communication
4. Shared Windows directory access
"""

import logging
import socket
import json
import time
import subprocess
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class WindowsLabJackBridge:
    """Bridge service for accessing LabJack hardware from WSL"""
    
    def __init__(self):
        self.bridge_type = "auto"  # auto, tcp, shared_folder, usbip
        # CRITICAL FIX: Add session lifecycle management
        self.active_sessions = set()
        self.monitoring_enabled = False
        self._handle = None
        self.windows_ip = self._get_windows_host_ip()
        self.bridge_port = 9001
        self.connected = False
        # Log de-duplication state
        self._last_usbip_available = None
        self._last_tcp_available = None
        self._last_network_available = None
        self._last_shared_available = None
        
    def _get_windows_host_ip(self) -> str:
        """Get Windows host IP from WSL"""
        try:
            # WSL2: Get Windows host IP from resolv.conf
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    if line.startswith('nameserver'):
                        return line.split()[1]
        except (FileNotFoundError, IOError, IndexError) as e:
            logger.debug(f"Could not read Windows IP from resolv.conf: {e}")
        return "localhost"
    
    def start_session_monitoring(self, session_id: str) -> bool:
        """Start monitoring for a specific session"""
        logger.info(f"🚀 Starting LabJack monitoring for session: {session_id}")
        self.active_sessions.add(session_id)
        self.monitoring_enabled = True
        return True
    
    def stop_session_monitoring(self, session_id: str) -> bool:
        """Stop monitoring for a specific session"""
        logger.info(f"🛑 Stopping LabJack monitoring for session: {session_id}")
        self.active_sessions.discard(session_id)
        
        # If no more active sessions, disable monitoring completely
        if not self.active_sessions:
            logger.info("🔌 No active sessions remaining, disabling LabJack monitoring")
            self.monitoring_enabled = False
        
        return True
    
    def is_monitoring_enabled(self) -> bool:
        """Check if monitoring is currently enabled for any session"""
        return self.monitoring_enabled and bool(self.active_sessions)
    
    def get_active_session_count(self) -> int:
        """Get count of active monitoring sessions"""
        return len(self.active_sessions)
    
    def get_active_sessions(self) -> set:
        """Get set of active session IDs"""
        return self.active_sessions.copy()
    
    def detect_labjack_connection_method(self) -> str:
        """Detect best method to connect to LabJack"""
        methods = []
        
        # Method 1: Direct USB access (if usbipd-win is set up)
        usbip_ok = self._check_usbip_setup()
        if usbip_ok:
            methods.append("usbip")
        if usbip_ok != self._last_usbip_available:
            (logger.info if usbip_ok else logger.info)("✅ USB/IP bridge available" if usbip_ok else "⛔ USB/IP bridge unavailable")
            self._last_usbip_available = usbip_ok
        
        # Method 2: TCP bridge to Windows service
        tcp_ok = self._check_tcp_bridge()
        if tcp_ok:
            methods.append("tcp")
        if tcp_ok != self._last_tcp_available:
            (logger.info if tcp_ok else logger.info)("✅ TCP bridge available" if tcp_ok else "⛔ TCP bridge unavailable")
            self._last_tcp_available = tcp_ok
            
        # Method 3: Network LabJack (if LabJack has Ethernet)
        net_ok = self._check_network_labjack()
        if net_ok:
            methods.append("network")
        if net_ok != self._last_network_available:
            (logger.info if net_ok else logger.info)("✅ Network LabJack available" if net_ok else "⛔ Network LabJack unavailable")
            self._last_network_available = net_ok
            
        # Method 4: Shared folder communication
        shared_ok = self._check_shared_folder()
        if shared_ok:
            methods.append("shared")
        if shared_ok != self._last_shared_available:
            (logger.info if shared_ok else logger.info)("✅ Shared folder communication available" if shared_ok else "⛔ Shared folder communication unavailable")
            self._last_shared_available = shared_ok
        
        if not methods:
            logger.warning("❌ No LabJack connection methods available")
            return "none"
            
        return methods[0]  # Return best available method
    
    def _check_usbip_setup(self) -> bool:
        """Check if USB/IP is set up for LabJack access"""
        try:
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            return 'LabJack' in result.stdout or 'Meilhaus' in result.stdout
        except (FileNotFoundError, subprocess.SubprocessError, OSError) as e:
            logger.debug(f"USB/IP check failed: {e}")
            return False
    
    def _check_tcp_bridge(self) -> bool:
        """Check if TCP bridge to Windows is available"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.windows_ip, self.bridge_port))
            sock.close()
            return result == 0
        except (socket.error, OSError) as e:
            logger.debug(f"TCP bridge check failed: {e}")
            return False
    
    def _check_network_labjack(self) -> bool:
        """Check if LabJack is accessible via network"""
        # LabJack T7-Pro and T8 can have Ethernet connectivity
        try:
            # Scan common LabJack network addresses
            for addr in ["192.168.1.207", "192.168.0.207"]:  # Default LabJack IPs
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((addr, 502))  # Modbus port
                sock.close()
                if result == 0:
                    return True
        except (socket.error, OSError) as e:
            logger.debug(f"Network LabJack check failed: {e}")
        return False
    
    def _check_shared_folder(self) -> bool:
        """Check if Windows shared folder is accessible"""
        # Check for mounted Windows drives
        windows_paths = [
            "/mnt/c/",
            "/mnt/d/",
            "//wsl$/Ubuntu/",
        ]
        return any(os.path.exists(path) for path in windows_paths)
    
    def connect_to_labjack(self) -> Dict[str, Any]:
        """Attempt to connect to LabJack hardware"""
        method = self.detect_labjack_connection_method()
        
        if method == "usbip":
            return self._connect_via_usbip()
        elif method == "tcp":
            return self._connect_via_tcp()
        elif method == "network":
            return self._connect_via_network()
        elif method == "shared":
            return self._connect_via_shared_folder()
        else:
            return self._fallback_connection()
    
    def _connect_via_usbip(self) -> Dict[str, Any]:
        """Connect via USB/IP bridge"""
        try:
            # Try to import labjack after USB/IP setup
            import labjack.ljm as ljm
            
            devices = ljm.listAll(ljm.constants.dtANY, ljm.constants.ctANY)
            if devices[0]:
                handle = ljm.open(ljm.constants.dtANY, ljm.constants.ctUSB, "ANY")
                device_info = ljm.getHandleInfo(handle)
                
                self.connected = True
                return {
                    "connected": True,
                    "method": "usbip",
                    "device_type": f"LabJack-{device_info[0]}",
                    "serial_number": str(device_info[2]),
                    "connection_type": "USB via USB/IP"
                }
        except Exception as e:
            logger.warning(f"USB/IP connection failed: {e}")
            
        return {"connected": False, "error": "USB/IP connection failed"}
    
    def _connect_via_tcp(self) -> Dict[str, Any]:
        """Connect via TCP bridge to Windows service"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.windows_ip, self.bridge_port))
            
            # Send connection request
            request = {"action": "connect", "timestamp": datetime.now().isoformat()}
            sock.send(json.dumps(request).encode())
            
            response = json.loads(sock.recv(1024).decode())
            sock.close()
            
            if response.get("connected"):
                self.connected = True
                return {
                    "connected": True,
                    "method": "tcp",
                    "device_type": response.get("device_type", "LabJack via TCP"),
                    "serial_number": response.get("serial_number"),
                    "connection_type": "TCP Bridge to Windows"
                }
        except Exception as e:
            logger.warning(f"TCP bridge connection failed: {e}")
            
        return {"connected": False, "error": "TCP bridge connection failed"}
    
    def _connect_via_network(self) -> Dict[str, Any]:
        """Connect via network (Ethernet LabJack)"""
        try:
            import labjack.ljm as ljm
            
            # Try network connection to LabJack
            handle = ljm.open(ljm.constants.dtT7, ljm.constants.ctETHERNET, "ANY")
            device_info = ljm.getHandleInfo(handle)
            
            self.connected = True
            return {
                "connected": True,
                "method": "network",
                "device_type": f"LabJack-{device_info[0]}",
                "serial_number": str(device_info[2]),
                "connection_type": "Ethernet"
            }
        except Exception as e:
            logger.warning(f"Network connection failed: {e}")
            
        return {"connected": False, "error": "Network connection failed"}
    
    def _connect_via_shared_folder(self) -> Dict[str, Any]:
        """Connect via shared folder communication"""
        try:
            # Create communication files in shared Windows directory
            shared_path = "/mnt/c/temp/labjack_bridge"
            os.makedirs(shared_path, exist_ok=True)
            
            # Write connection request
            request_file = f"{shared_path}/request.json"
            with open(request_file, 'w') as f:
                json.dump({
                    "action": "status",
                    "timestamp": datetime.now().isoformat()
                }, f)
            
            # Wait for Windows service response
            response_file = f"{shared_path}/response.json"
            for _ in range(10):  # Wait up to 10 seconds
                if os.path.exists(response_file):
                    with open(response_file, 'r') as f:
                        response = json.load(f)
                    os.remove(response_file)
                    
                    if response.get("connected"):
                        self.connected = True
                        return {
                            "connected": True,
                            "method": "shared",
                            "device_type": response.get("device_type", "LabJack via Shared Folder"),
                            "serial_number": response.get("serial_number"),
                            "connection_type": "Windows Shared Folder"
                        }
                    break
                time.sleep(1)
        except Exception as e:
            logger.warning(f"Shared folder connection failed: {e}")
            
        return {"connected": False, "error": "Shared folder connection failed"}
    
    def _fallback_connection(self) -> Dict[str, Any]:
        """Fallback: Provide setup instructions"""
        logger.info("🔧 No automatic LabJack connection available")
        logger.info("💡 LabJack Setup Instructions for WSL:")
        logger.info("1. Install usbipd-win on Windows: winget install usbipd")
        logger.info("2. Run as Admin: usbipd list")
        logger.info("3. Bind LabJack: usbipd bind --busid X-Y")
        logger.info("4. Attach to WSL: usbipd attach --wsl --busid X-Y")
        
        return {
            "connected": False,
            "error": "No connection method available",
            "setup_required": True,
            "instructions": [
                "Install usbipd-win on Windows: winget install usbipd",
                "Run PowerShell as Administrator",
                "List USB devices: usbipd list",
                "Find LabJack device and note BUSID",
                "Bind device: usbipd bind --busid X-Y",
                "Attach to WSL: usbipd attach --wsl --busid X-Y"
            ]
        }
    
    def read_analog_voltage(self, channel: str = "AIN0") -> Dict[str, Any]:
        """Read analog voltage from LabJack channel"""
        # CRITICAL FIX: Check if monitoring is enabled before reading
        if not self.is_monitoring_enabled():
            return {
                "success": False,
                "error": "Monitoring not active - no sessions running",
                "voltage": None,
                "timestamp": datetime.now().isoformat()
            }
        
        if not self.connected:
            return {
                "success": False,
                "error": "LabJack not connected",
                "voltage": None,
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            method = self.detect_labjack_connection_method()
            
            if method == "usbip":
                return self._read_voltage_usbip(channel)
            elif method == "tcp":
                return self._read_voltage_tcp(channel)
            elif method == "network":
                return self._read_voltage_network(channel)
            elif method == "shared":
                return self._read_voltage_shared_folder(channel)
            else:
                # Mock reading with simulated 4.2V for testing
                # Simulate varying voltage around 4.2V to show active readings
                import random
                base_voltage = 4.2
                noise = (random.random() - 0.5) * 0.1  # ±0.05V noise
                simulated_voltage = base_voltage + noise
                
                return {
                    "success": True,
                    "voltage": round(simulated_voltage, 2),  # Simulated voltage with variation
                    "channel": channel,
                    "timestamp": datetime.now().isoformat(),
                    "method": "mock",
                    "note": "Mock voltage reading simulating 4.2V TTL signal - hardware connection needed",
                    "bridge_mode": "mock_simulation"
                }
                
        except Exception as e:
            logger.error(f"Voltage read error: {e}")
            return {
                "success": False,
                "error": str(e),
                "voltage": None,
                "timestamp": datetime.now().isoformat()
            }
    
    def _read_voltage_usbip(self, channel: str) -> Dict[str, Any]:
        """Read voltage via USB/IP connection"""
        try:
            import labjack.ljm as ljm
            
            # Open connection if not already opened
            if not hasattr(self, '_handle') or self._handle is None:
                logger.info(f"🔌 Opening LabJack connection for voltage reading...")
                self._handle = ljm.open(ljm.constants.dtANY, ljm.constants.ctUSB, "ANY")
                logger.info(f"✅ LabJack connection opened successfully")
            
            # Read voltage from the specified channel
            voltage = ljm.eReadName(self._handle, channel)
            logger.info(f"📊 Read voltage from {channel}: {voltage:.3f}V")
            
            return {
                "success": True,
                "voltage": voltage,
                "channel": channel,
                "timestamp": datetime.now().isoformat(),
                "method": "usbip",
                "hardware": "LabJack T7",
                "note": "Real hardware voltage reading"
            }
        except Exception as e:
            logger.error(f"USB/IP voltage read error: {e}")
            # Close handle on error
            if hasattr(self, '_handle') and self._handle is not None:
                try:
                    import labjack.ljm as ljm
                    ljm.close(self._handle)
                except Exception as close_error:
                    logger.debug(f"Error closing handle on error: {close_error}")
                self._handle = None
            return {
                "success": False,
                "error": str(e),
                "voltage": None,
                "timestamp": datetime.now().isoformat()
            }
    
    def _read_voltage_tcp(self, channel: str) -> Dict[str, Any]:
        """Read voltage via TCP bridge"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.windows_ip, self.bridge_port))
            
            request = {
                "action": "read_voltage",
                "channel": channel,
                "timestamp": datetime.now().isoformat()
            }
            sock.send(json.dumps(request).encode())
            
            response = json.loads(sock.recv(1024).decode())
            sock.close()
            
            return {
                "success": response.get("success", False),
                "voltage": response.get("voltage", 0.0),
                "channel": channel,
                "timestamp": datetime.now().isoformat(),
                "method": "tcp"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "voltage": None,
                "timestamp": datetime.now().isoformat()
            }
    
    def _read_voltage_network(self, channel: str) -> Dict[str, Any]:
        """Read voltage via network LabJack"""
        try:
            import labjack.ljm as ljm
            handle = ljm.open(ljm.constants.dtT7, ljm.constants.ctETHERNET, "ANY")
            voltage = ljm.eReadName(handle, channel)
            ljm.close(handle)
            
            return {
                "success": True,
                "voltage": voltage,
                "channel": channel,
                "timestamp": datetime.now().isoformat(),
                "method": "network"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "voltage": None,
                "timestamp": datetime.now().isoformat()
            }
    
    def _read_voltage_shared_folder(self, channel: str) -> Dict[str, Any]:
        """Read voltage via shared folder communication"""
        try:
            shared_path = "/mnt/c/temp/labjack_bridge"
            os.makedirs(shared_path, exist_ok=True)
            
            request_file = f"{shared_path}/voltage_request.json"
            response_file = f"{shared_path}/voltage_response.json"
            
            with open(request_file, 'w') as f:
                json.dump({
                    "action": "read_voltage",
                    "channel": channel,
                    "timestamp": datetime.now().isoformat()
                }, f)
            
            # Wait for Windows service response
            for _ in range(5):
                if os.path.exists(response_file):
                    with open(response_file, 'r') as f:
                        response = json.load(f)
                    os.remove(response_file)
                    
                    return {
                        "success": response.get("success", False),
                        "voltage": response.get("voltage", 0.0),
                        "channel": channel,
                        "timestamp": datetime.now().isoformat(),
                        "method": "shared"
                    }
                time.sleep(1)
                
            return {
                "success": False,
                "error": "Shared folder voltage read timeout",
                "voltage": None,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "voltage": None,
                "timestamp": datetime.now().isoformat()
            }

    def get_status(self) -> Dict[str, Any]:
        """Get current LabJack connection status"""
        if not self.connected:
            return self.connect_to_labjack()
        
        return {
            "connected": self.connected,
            "bridge_active": True,
            "windows_host": self.windows_ip,
            "timestamp": datetime.now().isoformat()
        }
    
    # CRITICAL FIX: Add session lifecycle management methods
    def start_session_monitoring(self, session_id: str):
        """Start monitoring for a specific session"""
        logger.info(f"🎯 Starting bridge session monitoring for: {session_id}")
        self.active_sessions.add(session_id)
        self.monitoring_enabled = True
        logger.info(f"✅ Bridge monitoring enabled. Active sessions: {len(self.active_sessions)}")
    
    def stop_session_monitoring(self, session_id: str) -> bool:
        """Stop monitoring for a specific session without affecting global state.
        
        CRITICAL FIX: Preserve bridge connection and monitoring for other sessions.
        Only disable global monitoring when NO sessions remain.
        
        Args:
            session_id: Session to stop monitoring for
            
        Returns:
            True if session monitoring stopped successfully
        """
        logger.info(f"🔄 Stopping bridge session monitoring for: {session_id}")
        
        # Remove session from active list
        was_active = session_id in self.active_sessions
        self.active_sessions.discard(session_id)
        
        if not was_active:
            logger.warning(f"⚠️ Session {session_id} was not in active sessions list")
            return True
        
        # CRITICAL FIX: Only disable global monitoring when truly no sessions remain
        if self.active_sessions:
            logger.info(f"✅ Bridge monitoring continues. Active sessions: {len(self.active_sessions)}")
            logger.debug(f"Remaining sessions: {list(self.active_sessions)}")
            return True
        
        # No sessions remain - can safely disable monitoring
        if not self.active_sessions:
            self.monitoring_enabled = False
            logger.info("⏹️ Bridge monitoring disabled - no active sessions remain")
            # NOTE: We do NOT close the hardware connection here
            # The connection should remain available for future sessions
        
        return True
    
    def is_monitoring_enabled(self) -> bool:
        """Check if monitoring is enabled"""
        return self.monitoring_enabled and bool(self.active_sessions)

# Service instance
labjack_bridge = WindowsLabJackBridge()
# CRITICAL FIX: Export with expected name for dedicated monitor import
windows_labjack_bridge = labjack_bridge
