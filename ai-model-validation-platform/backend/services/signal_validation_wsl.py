"""
Signal Validation Service - WSL Enhanced Version
PRD Module 3.1 & 3.2 Implementation with Windows/WSL Bridge Support

This service provides LabJack signal validation in a Windows/WSL environment
using the WSL bridge service for hardware access.
"""

import logging
import platform
from typing import Dict, Any, Optional, List
from datetime import datetime

# Import the WSL bridge service
from .labjack_wsl_service import labjack_service

logger = logging.getLogger(__name__)

class SignalValidationServiceWSL:
    """Signal validation service for Windows/WSL environments"""
    
    def __init__(self):
        self.labjack_service = labjack_service
        self._last_config = None
        self._voltage_config = None
        self._monitoring_session_id = None
        self._signal_monitoring = False
        logger.info("🔌 LabJack interface initialized in WSL BRIDGE MODE")
        logger.info("LabJack interface initialized successfully")
        
    def get_labjack_status(self) -> Dict[str, Any]:
        """Get LabJack connection status"""
        try:
            status = self.labjack_service.get_connection_status()
            
            # Add WSL-specific information
            status["wsl_info"] = {
                "environment": "WSL",
                "platform": platform.system(),
                "kernel": platform.uname().release,
                "bridge_service": "active"
            }
            
            return status
        except Exception as e:
            logger.error(f"Failed to get LabJack status: {e}")
            return {
                "connected": False,
                "mock_mode": False,
                "error": f"WSL Bridge Error: {str(e)}",
                "timestamp": "",
                "system_info": {
                    "platform": "windows-wsl",
                    "bridge_active": False,
                    "backend_status": "error"
                },
                "recommendations": [
                    "Check WSL LabJack bridge service",
                    "Verify Windows LabJack hardware connection",
                    "Consider USB/IP setup for direct access"
                ]
            }
    
    async def check_labjack_connection(self) -> Dict[str, Any]:
        """Async wrapper for get_labjack_status for API compatibility"""
        from datetime import datetime, timezone
        status = self.get_labjack_status()
        
        # Ensure timestamp is present
        if "timestamp" not in status or not status["timestamp"]:
            status["timestamp"] = datetime.now(timezone.utc).isoformat()
            
        return status
    
    def read_ttl_signal(self, channel: str = "FIO0") -> Dict[str, Any]:
        """Read TTL signal from LabJack"""
        return self.labjack_service.read_digital_input(channel)
    
    def read_voltage_signal(self, channel: str = "AIN0") -> Dict[str, Any]:
        """Read analog voltage signal from LabJack"""
        try:
            # Use the Windows bridge to read voltage
            from .windows_labjack_bridge import labjack_bridge
            
            # Check bridge connection status
            connection_status = self.labjack_service.check_connection()
            
            # If no hardware detected, simulate mock reading
            if not (connection_status and connection_status.connected):
                # Return simulated 4.2V reading for development/testing
                import random
                base_voltage = 4.2
                noise = (random.random() - 0.5) * 0.1  # ±0.05V noise
                simulated_voltage = base_voltage + noise
                
                logger.info(f"🔧 Simulating voltage reading: {simulated_voltage:.2f}V on {channel}")
                
                return {
                    "success": True,
                    "voltage": round(simulated_voltage, 2),
                    "channel": channel,
                    "timestamp": datetime.now().isoformat(),
                    "method": "mock",
                    "note": "Mock voltage reading simulating 4.2V TTL signal",
                    "bridge_info": {
                        "environment": "WSL",
                        "bridge_method": "mock_simulation",
                        "connection_status": False,
                        "development_mode": True
                    }
                }
            
            # Try real hardware reading
            result = labjack_bridge.read_analog_voltage(channel)
            
            # Add WSL-specific information
            result["bridge_info"] = {
                "environment": "WSL",
                "bridge_method": result.get("method", "unknown"),
                "connection_status": connection_status.connected if connection_status else False
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Voltage read error: {e}")
            return {
                "success": False,
                "error": str(e),
                "voltage": None,
                "timestamp": datetime.now().isoformat(),
                "channel": channel
            }
    
    async def initialize_labjack(self, config: Dict[str, Any] = None) -> bool:
        """Initialize LabJack connection with configuration
        
        Args:
            config: Configuration parameters including:
                - device_type: Device type (T4, T7, etc.) or "ANY"
                - connection_type: Connection type (USB, Ethernet, WiFi) or "ANY"
                - identifier: Device serial number, IP address, or "ANY"
                - voltage_threshold: Detection threshold in volts (default: 2.5V)
                - channels: List of analog input channels (default: ["AIN0", "AIN1"])
                - force_mock_mode: Force mock mode regardless of hardware availability
                
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            logger.info("🔧 Initializing LabJack via WSL Bridge...")
            
            # Store configuration
            if config:
                self._last_config = config
            
            # Check bridge connection
            connection_info = self.check_connection()
            
            if connection_info.connected:
                logger.info(f"✅ LabJack initialized successfully via {connection_info.method}")
                return True
            else:
                logger.warning(f"⚠️ LabJack initialization failed: {connection_info.error}")
                logger.info("💡 Consider using setup instructions for manual configuration")
                return False
                
        except Exception as e:
            logger.error(f"❌ LabJack initialization error: {e}")
            return False
    
    async def configure_voltage_detection(
        self, 
        voltage_threshold: float = 2.5,
        channels: Optional[List[str]] = None,
        sample_rate: int = 1000
    ) -> Dict[str, Any]:
        """Configure voltage detection parameters
        
        Args:
            voltage_threshold: Voltage level that triggers detection (volts)
            sample_rate: Sampling rate in Hz (100-50000)
            channels: List of analog input channels (e.g., ["AIN0", "AIN1"])
            
        Returns:
            Dict containing success status and configuration details
        """
        try:
            connection_status = self.labjack_service.check_connection()
            if not (connection_status and connection_status.connected):
                return {
                    "success": False,
                    "error": "LabJack not connected - initialize connection first"
                }
            
            # Store configuration parameters
            self._voltage_config = {
                "voltage_threshold": voltage_threshold,
                "channels": channels or ["FIO0"],
                "sample_rate": sample_rate
            }
            
            logger.info(f"🔧 Voltage detection configured: threshold={voltage_threshold}V, "
                       f"channels={channels}, rate={sample_rate}Hz")
            
            return {
                "success": True,
                "configuration": self._voltage_config,
                "message": "Voltage detection configured successfully"
            }
            
        except Exception as e:
            logger.error(f"Configuration error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def start_signal_monitoring(self, test_session_id: str):
        """Start continuous monitoring of external signals for a test session"""
        try:
            self._monitoring_session_id = test_session_id
            self._signal_monitoring = True
            
            logger.info(f"📡 Signal monitoring started for session: {test_session_id}")
            
            # Register session with bridge monitoring
            if hasattr(self.labjack_service, 'add_connection_callback'):
                self.labjack_service.add_connection_callback(self._on_signal_detected)
                
        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            raise
    
    def stop_signal_monitoring(self):
        """Stop signal monitoring"""
        self._signal_monitoring = False
        self._monitoring_session_id = None
        logger.info("⏹️ Signal monitoring stopped")
    
    async def process_external_signal(
        self, 
        signal_type: str,
        signal_data: Dict[str, Any],
        video_timestamp: float,
        test_session_id: str
    ) -> Dict[str, Any]:
        """Process an incoming detection signal from external camera"""
        try:
            if signal_type == "voltage":
                voltage = signal_data.get("voltage", 0.0)
                channel = signal_data.get("channel", "FIO0")
                
                # Validate signal threshold
                threshold = getattr(self, '_voltage_config', {}).get('voltage_threshold', 2.5)
                signal_detected = voltage >= threshold
                
                # Get current connection status
                connection_status = self.labjack_service.check_connection()
                
                result = {
                    "signal_type": signal_type,
                    "voltage": voltage,
                    "channel": channel,
                    "signal_detected": signal_detected,
                    "video_timestamp": video_timestamp,
                    "test_session_id": test_session_id,
                    "timestamp": datetime.now().isoformat(),
                    "bridge_method": connection_status.method if connection_status else "unknown"
                }
                
                if signal_detected:
                    logger.info(f"🔔 Signal detected: {voltage}V on {channel} at {video_timestamp}s")
                
                return result
                
        except Exception as e:
            logger.error(f"Signal processing error: {e}")
            return {
                "error": str(e),
                "signal_type": signal_type,
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_signal_statistics(self, test_session_id: str) -> Dict[str, Any]:
        """Get statistics for signals in a test session"""
        try:
            # Basic statistics for WSL bridge implementation
            connection_status = self.labjack_service.check_connection()
            return {
                "test_session_id": test_session_id,
                "total_signals": 0,  # Would be populated from database
                "signal_types": [],
                "connection_method": connection_status.method if connection_status else "unknown",
                "bridge_active": True,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {"error": str(e)}
    
    def _on_signal_detected(self, connection_info):
        """Callback for signal detection events"""
        if self._signal_monitoring and connection_info and connection_info.connected:
            logger.debug(f"Signal callback triggered: {connection_info.method}")

    def get_setup_instructions(self) -> Dict[str, Any]:
        """Get setup instructions for LabJack in WSL"""
        return self.labjack_service.get_setup_instructions()

# Global instance
signal_validation_service = SignalValidationServiceWSL()