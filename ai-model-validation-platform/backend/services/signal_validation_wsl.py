"""
Signal Validation Service - WSL Enhanced Version
PRD Module 3.1 & 3.2 Implementation with Windows/WSL Bridge Support

This service provides LabJack signal validation in a Windows/WSL environment
using the WSL bridge service for hardware access.
"""

import logging
import platform
from typing import Dict, Any, Optional

# Import the WSL bridge service
from .labjack_wsl_service import labjack_service

logger = logging.getLogger(__name__)

class SignalValidationServiceWSL:
    """Signal validation service for Windows/WSL environments"""
    
    def __init__(self):
        self.labjack_service = labjack_service
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
    
    def get_setup_instructions(self) -> Dict[str, Any]:
        """Get setup instructions for LabJack in WSL"""
        return self.labjack_service.get_setup_instructions()

# Global instance
signal_validation_service = SignalValidationServiceWSL()