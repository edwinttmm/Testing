"""
HIL Hardware Validation Service

This service provides critical safety validation for HIL testing to prevent
the dangerous use of simulation data in place of real hardware testing.

CRITICAL SAFETY FEATURES:
1. Validates real LabJack hardware connection before HIL sessions
2. Prevents silent fallback to simulation mode
3. Provides clear error messages when hardware is required but missing
4. Ensures frontend displays accurate hardware connection status

This service addresses the critical bug where HIL sessions would silently
use simulated detection data when hardware was expected but failed to connect.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from services.labjack_service import LabJackService, ConnectionMode, ConnectionStatus

logger = logging.getLogger(__name__)


class HILValidationError(Exception):
    """Custom exception for HIL validation failures"""
    pass


class HardwareRequirement(Enum):
    """Hardware requirement levels for different operations"""
    NONE = "none"              # No hardware required (development/testing)
    RECOMMENDED = "recommended" # Hardware recommended but not required
    REQUIRED = "required"       # Hardware absolutely required
    CRITICAL = "critical"       # Hardware required for safety-critical operations


@dataclass
class HILHardwareStatus:
    """Comprehensive HIL hardware status"""
    is_connected: bool
    device_type: str
    serial_number: str
    connection_type: str
    is_simulation: bool
    hil_suitable: bool
    connection_mode: str
    status_message: str
    warning_message: Optional[str]
    validation_timestamp: datetime
    hardware_requirement_met: bool


class HILValidationService:
    """
    HIL Hardware Validation Service
    
    Provides fail-fast validation to prevent dangerous simulation fallback
    in HIL testing scenarios where real hardware is required.
    """
    
    def __init__(self, labjack_service: LabJackService):
        self.labjack_service = labjack_service
        self.last_validation_timestamp: Optional[datetime] = None
        self.validation_cache: Optional[HILHardwareStatus] = None
        self.cache_valid_seconds = 5  # Cache hardware status for 5 seconds
        
        logger.info("🛡️ HIL Validation Service initialized - fail-fast mode enabled")
    
    def validate_hardware_for_hil(self, requirement_level: HardwareRequirement = HardwareRequirement.REQUIRED) -> HILHardwareStatus:
        """
        Validate hardware requirements for HIL testing
        
        Args:
            requirement_level: Level of hardware requirement
            
        Returns:
            HILHardwareStatus with validation results
            
        Raises:
            HILValidationError: If hardware requirements not met
        """
        try:
            # Get current hardware status
            status = self._get_hardware_status()
            
            # Validate based on requirement level
            validation_passed = self._validate_requirement_level(status, requirement_level)
            
            if not validation_passed:
                error_msg = self._generate_validation_error(status, requirement_level)
                logger.error(f"🚫 HIL hardware validation failed: {error_msg}")
                raise HILValidationError(error_msg)
            
            # Log successful validation
            logger.info(f"✅ HIL hardware validation passed: {status.device_type} (S/N: {status.serial_number})")
            
            return status
            
        except HILValidationError:
            raise  # Re-raise validation errors
        except Exception as e:
            logger.error(f"❌ HIL hardware validation error: {e}")
            raise HILValidationError(f"Hardware validation system error: {str(e)}")
    
    def _get_hardware_status(self) -> HILHardwareStatus:
        """Get comprehensive hardware status with caching"""
        now = datetime.now()
        
        # Check cache validity
        if (self.validation_cache is not None and 
            self.last_validation_timestamp is not None and
            (now - self.last_validation_timestamp).total_seconds() < self.cache_valid_seconds):
            return self.validation_cache
        
        # Get fresh status from LabJack service
        labjack_status = self.labjack_service.get_status()
        device_info = labjack_status.device_info
        
        # Determine if this is simulation mode - FIXED: More accurate detection
        is_simulation = (
            labjack_status.mode == ConnectionMode.MOCK or
            device_info.get("is_mock", False) or
            device_info.get("is_simulation", False) or
            device_info.get("device_type", "Unknown").lower().startswith("mock")
        )
        
        # Generate status message
        if labjack_status.connected:
            if is_simulation:
                status_message = "⚠️ Simulation Mode (NOT REAL HARDWARE)"
                warning_message = "This is simulated data - not suitable for HIL validation"
            else:
                status_message = "✅ Real Hardware Connected"
                warning_message = None
        else:
            status_message = "❌ Not Connected"
            warning_message = "No LabJack hardware detected"
        
        # Create comprehensive status
        status = HILHardwareStatus(
            is_connected=labjack_status.connected,
            device_type=device_info.get("device_type", "Unknown"),
            serial_number=str(device_info.get("serial_number", "Unknown")),
            connection_type=device_info.get("connection_type", "Unknown"),
            is_simulation=is_simulation,
            hil_suitable=device_info.get("hil_suitable", not is_simulation),
            connection_mode=labjack_status.mode.value,
            status_message=status_message,
            warning_message=warning_message,
            validation_timestamp=now,
            hardware_requirement_met=labjack_status.connected and not is_simulation
        )
        
        # Cache the result
        self.validation_cache = status
        self.last_validation_timestamp = now
        
        return status
    
    def _validate_requirement_level(self, status: HILHardwareStatus, requirement: HardwareRequirement) -> bool:
        """Validate hardware status against requirement level"""
        if requirement == HardwareRequirement.NONE:
            return True  # No hardware required
        
        elif requirement == HardwareRequirement.RECOMMENDED:
            # Hardware recommended but not required - always pass but log warnings
            if not status.hardware_requirement_met:
                logger.warning(f"⚠️ Hardware recommended but not available: {status.status_message}")
            return True
        
        elif requirement == HardwareRequirement.REQUIRED:
            # Hardware absolutely required
            return status.hardware_requirement_met
        
        elif requirement == HardwareRequirement.CRITICAL:
            # Hardware required for safety-critical operations
            return (
                status.hardware_requirement_met and 
                status.hil_suitable and 
                not status.is_simulation
            )
        
        return False
    
    def _generate_validation_error(self, status: HILHardwareStatus, requirement: HardwareRequirement) -> str:
        """Generate detailed error message for validation failure"""
        if not status.is_connected:
            return (
                f"HIL testing requires LabJack hardware connection. "
                f"Status: {status.status_message}. "
                f"Please connect a LabJack device and ensure drivers are installed."
            )
        
        if status.is_simulation:
            return (
                f"HIL testing detected simulation mode. "
                f"Real LabJack hardware is required for validation testing. "
                f"Current mode: {status.connection_mode}. "
                f"Warning: {status.warning_message}"
            )
        
        if not status.hil_suitable:
            return (
                f"Connected LabJack device is not suitable for HIL testing. "
                f"Device: {status.device_type} (S/N: {status.serial_number})"
            )
        
        # Generic failure message
        return (
            f"HIL hardware validation failed. "
            f"Requirement: {requirement.value}, "
            f"Status: {status.status_message}"
        )
    
    def get_hardware_status_for_ui(self) -> Dict[str, Any]:
        """Get hardware status formatted for UI display"""
        try:
            status = self._get_hardware_status()
            
            return {
                "connected": status.is_connected,
                "status": status.status_message,
                "device_type": status.device_type,
                "serial_number": status.serial_number,
                "connection_type": status.connection_type,
                "connection_mode": status.connection_mode,
                "is_simulation": status.is_simulation,
                "hil_suitable": status.hil_suitable,
                "warning": status.warning_message,
                "last_validated": status.validation_timestamp.isoformat(),
                "hardware_icon": "🔌" if status.is_connected and not status.is_simulation else "❌",
                "status_color": "green" if status.hardware_requirement_met else ("orange" if status.is_simulation else "red")
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting hardware status for UI: {e}")
            return {
                "connected": False,
                "status": "❌ Error",
                "error": str(e),
                "hardware_icon": "❌",
                "status_color": "red"
            }
    
    def validate_hil_session_start(self) -> HILHardwareStatus:
        """Validate hardware for HIL session start - CRITICAL validation"""
        return self.validate_hardware_for_hil(HardwareRequirement.CRITICAL)
    
    def validate_hil_video_playback(self) -> HILHardwareStatus:
        """Validate hardware for HIL video playback"""
        return self.validate_hardware_for_hil(HardwareRequirement.REQUIRED)
    
    def validate_hil_timing_event(self) -> HILHardwareStatus:
        """Validate hardware for HIL timing event logging"""
        return self.validate_hardware_for_hil(HardwareRequirement.REQUIRED)
    
    def clear_validation_cache(self):
        """Clear validation cache to force fresh hardware check"""
        self.validation_cache = None
        self.last_validation_timestamp = None
        logger.debug("🔄 HIL validation cache cleared")
    
    def get_connection_diagnostics(self) -> Dict[str, Any]:
        """Get detailed connection diagnostics for troubleshooting"""
        try:
            status = self._get_hardware_status()
            labjack_status = self.labjack_service.get_status()
            
            return {
                "validation_service_status": "operational",
                "hardware_status": {
                    "connected": status.is_connected,
                    "device_type": status.device_type,
                    "serial_number": status.serial_number,
                    "connection_type": status.connection_type,
                    "connection_mode": status.connection_mode
                },
                "safety_checks": {
                    "is_simulation": status.is_simulation,
                    "hil_suitable": status.hil_suitable,
                    "hardware_requirement_met": status.hardware_requirement_met
                },
                "labjack_service_info": {
                    "mode": labjack_status.mode.value,
                    "status": labjack_status.status.value,
                    "streaming": labjack_status.streaming,
                    "statistics": labjack_status.statistics
                },
                "validation_cache": {
                    "cached": self.validation_cache is not None,
                    "cache_age_seconds": (
                        (datetime.now() - self.last_validation_timestamp).total_seconds()
                        if self.last_validation_timestamp else None
                    )
                }
            }
            
        except Exception as e:
            return {
                "validation_service_status": "error",
                "error": str(e)
            }


# Global validation service instance
_hil_validation_service: Optional[HILValidationService] = None


def get_hil_validation_service(labjack_service: Optional[LabJackService] = None) -> HILValidationService:
    """Get global HIL validation service instance"""
    global _hil_validation_service
    
    if _hil_validation_service is None:
        if labjack_service is None:
            from services.labjack_service import get_labjack_service
            labjack_service = get_labjack_service()
        
        _hil_validation_service = HILValidationService(labjack_service)
        logger.info("🛡️ HIL Validation Service singleton created")
    
    return _hil_validation_service


# Export main classes and functions
__all__ = [
    "HILValidationService",
    "HILValidationError",
    "HardwareRequirement",
    "HILHardwareStatus",
    "get_hil_validation_service"
]