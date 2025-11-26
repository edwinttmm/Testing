"""
Environment Configuration for LabJack Integration

This module handles environment variable configuration for the LabJack signal validation system.
It provides:
- Automatic detection of LabJack availability
- Mock mode configuration
- Environment-based settings
- Fallback configurations
- Validation of settings

Environment Variables:
    LABJACK_MOCK_MODE: Force mock mode (true/false)
    LABJACK_DEVICE_TYPE: Default device type (T4, T7, ANY)
    LABJACK_CONNECTION_TYPE: Default connection (USB, Ethernet, WiFi, ANY)
    LABJACK_VOLTAGE_THRESHOLD: Detection threshold in volts (default: 2.5)
    LABJACK_SAMPLE_RATE: Default sample rate in Hz (default: 1000)
    LABJACK_CHANNELS: Comma-separated list of channels (default: AIN0,AIN1)
    LABJACK_AUTO_DETECT: Auto-detect hardware on startup (true/false)
    LABJACK_SIMULATION_MODE: Type of simulation (detection_spikes, sine, square, etc.)
"""

import os
import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class LabJackConfig:
    """Configuration class for LabJack integration"""
    
    # Hardware connection settings
    mock_mode: bool = False
    auto_detect: bool = True
    device_type: str = "ANY"
    connection_type: str = "ANY"
    identifier: str = "ANY"
    
    # Bridge settings (for Windows bridge)
    bridge_enabled: bool = True
    bridge_host: str = "localhost"
    bridge_port: int = 8080
    bridge_timeout: int = 10
    bridge_reconnect_interval: int = 5
    bridge_max_reconnects: int = 10
    
    # Signal acquisition settings
    voltage_threshold: float = 2.5
    sample_rate: int = 200
    channels: List[str] = field(default_factory=lambda: ["AIN0", "AIN1"])

    # Stream mode configuration (for high-speed sampling)
    use_stream_mode: bool = True
    stream_scans_per_read: int = 100
    stream_settling_us: int = 0
    stream_resolution_index: int = 0
    stream_auto_fallback: bool = True

    # Simulation settings (for mock mode)
    simulation_mode: str = "detection_spikes"
    detection_probability: float = 0.05
    noise_amplitude: float = 0.1
    
    # System settings
    connection_timeout: int = 5
    retry_attempts: int = 3
    log_level: str = "INFO"
    
    # Safety settings
    max_voltage: float = 10.0
    min_sample_rate: int = 100
    max_sample_rate: int = 50000
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        self._validate_config()
    
    def _validate_config(self):
        """Validate configuration parameters"""
        # Validate voltage threshold
        if not (0.1 <= self.voltage_threshold <= self.max_voltage):
            logger.warning(f"Voltage threshold {self.voltage_threshold}V outside safe range, "
                          f"clamping to 0.1-{self.max_voltage}V")
            self.voltage_threshold = max(0.1, min(self.voltage_threshold, self.max_voltage))
        
        # Validate sample rate
        if not (self.min_sample_rate <= self.sample_rate <= self.max_sample_rate):
            logger.warning(f"Sample rate {self.sample_rate}Hz outside valid range, "
                          f"clamping to {self.min_sample_rate}-{self.max_sample_rate}Hz")
            self.sample_rate = max(self.min_sample_rate,
                                 min(self.sample_rate, self.max_sample_rate))

        # Validate stream mode settings
        if not (1 <= self.stream_scans_per_read <= 10000):
            logger.warning(f"Stream scans per read {self.stream_scans_per_read} outside valid range, "
                          "clamping to 1-10000")
            self.stream_scans_per_read = max(1, min(self.stream_scans_per_read, 10000))

        if self.stream_settling_us < 0:
            logger.warning("Stream settling time must be non-negative, setting to 0")
            self.stream_settling_us = 0

        if not (0 <= self.stream_resolution_index <= 8):
            logger.warning(f"Stream resolution index {self.stream_resolution_index} outside valid range, "
                          "clamping to 0-8")
            self.stream_resolution_index = max(0, min(self.stream_resolution_index, 8))

        # Auto-disable stream mode for low sample rates
        if self.use_stream_mode and self.sample_rate <= 100:
            logger.info(f"Sample rate {self.sample_rate}Hz is low, stream mode may not be optimal")

        # Validate channels
        valid_channels = [f"AIN{i}" for i in range(14)]  # LabJack supports AIN0-AIN13
        self.channels = [ch for ch in self.channels if ch in valid_channels]
        
        if not self.channels:
            logger.warning("No valid channels specified, defaulting to AIN0")
            self.channels = ["AIN0"]
        
        # Validate simulation settings
        if not (0.0 <= self.detection_probability <= 1.0):
            self.detection_probability = max(0.0, min(self.detection_probability, 1.0))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "mock_mode": self.mock_mode,
            "auto_detect": self.auto_detect,
            "device_type": self.device_type,
            "connection_type": self.connection_type,
            "identifier": self.identifier,
            "bridge_enabled": self.bridge_enabled,
            "bridge_host": self.bridge_host,
            "bridge_port": self.bridge_port,
            "bridge_timeout": self.bridge_timeout,
            "bridge_reconnect_interval": self.bridge_reconnect_interval,
            "bridge_max_reconnects": self.bridge_max_reconnects,
            "voltage_threshold": self.voltage_threshold,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "use_stream_mode": self.use_stream_mode,
            "stream_scans_per_read": self.stream_scans_per_read,
            "stream_settling_us": self.stream_settling_us,
            "stream_resolution_index": self.stream_resolution_index,
            "stream_auto_fallback": self.stream_auto_fallback,
            "simulation_mode": self.simulation_mode,
            "detection_probability": self.detection_probability,
            "noise_amplitude": self.noise_amplitude,
            "connection_timeout": self.connection_timeout,
            "retry_attempts": self.retry_attempts,
            "log_level": self.log_level,
            "max_voltage": self.max_voltage,
            "min_sample_rate": self.min_sample_rate,
            "max_sample_rate": self.max_sample_rate
        }
    
    def save_to_file(self, filepath: Union[str, Path]):
        """Save configuration to JSON file"""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        
        logger.info(f"LabJack configuration saved to {filepath}")
    
    @classmethod
    def from_file(cls, filepath: Union[str, Path]) -> 'LabJackConfig':
        """Load configuration from JSON file"""
        filepath = Path(filepath)
        
        if not filepath.exists():
            logger.warning(f"Configuration file {filepath} not found, using defaults")
            return cls()
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            return cls(**data)
            
        except Exception as e:
            logger.error(f"Failed to load configuration from {filepath}: {e}")
            return cls()


def detect_labjack_availability() -> Dict[str, Any]:
    """Detect if LabJack hardware/software is available"""
    status = {
        "ljm_library": False,
        "system_libraries": False,
        "hardware_connected": False,
        "mock_mode_required": True,
        "detection_method": "auto",
        "errors": []
    }
    
    # Try to import LabJack LJM library
    try:
        import labjack.ljm as ljm
        status["ljm_library"] = True
        logger.info("✅ LabJack LJM library is available")
        
        # Try to detect hardware
        try:
            handle = ljm.openS("ANY", "ANY", "ANY")
            ljm.close(handle)
            status["hardware_connected"] = True
            status["mock_mode_required"] = False
            logger.info("✅ LabJack hardware detected and accessible")
            
        except ljm.LJMError as e:
            if "NO_DEVICES_FOUND" in str(e):
                logger.info("ℹ️ LabJack library available but no hardware connected")
                status["mock_mode_required"] = True
            else:
                logger.warning(f"LabJack hardware test failed: {e}")
                status["errors"].append(f"Hardware test failed: {e}")
        
    except ImportError as e:
        logger.info("ℹ️ LabJack LJM library not available, will use mock mode")
        status["errors"].append(f"LJM library not found: {e}")
    
    except Exception as e:
        logger.error(f"Unexpected error during LabJack detection: {e}")
        status["errors"].append(f"Detection error: {e}")
    
    # Check system libraries (Linux)
    if os.name == 'posix':
        status["system_libraries"] = _check_linux_system_libraries()
    
    return status


def _check_linux_system_libraries() -> bool:
    """Check if required Linux system libraries are available"""
    try:
        import subprocess
        
        # Check for required libraries
        libraries = ["libusb-1.0", "libudev"]
        
        for lib in libraries:
            result = subprocess.run(
                ["pkg-config", "--exists", lib],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode != 0:
                logger.warning(f"System library {lib} not found")
                return False
        
        logger.debug("✅ Linux system libraries available")
        return True
        
    except Exception as e:
        logger.debug(f"System library check failed: {e}")
        return False


def load_config_from_env() -> LabJackConfig:
    """Load LabJack configuration from environment variables"""
    
    # Auto-detect hardware availability
    availability = detect_labjack_availability()
    
    # Determine mock mode
    mock_mode = os.getenv('LABJACK_MOCK_MODE', '').lower() == 'true'
    if not mock_mode:
        # Use mock mode if hardware is not available
        mock_mode = availability['mock_mode_required']
    
    # Parse channels from environment
    channels_str = os.getenv('LABJACK_CHANNELS', 'AIN0,AIN1')
    channels = [ch.strip() for ch in channels_str.split(',') if ch.strip()]
    
    # Create configuration
    config = LabJackConfig(
        mock_mode=mock_mode,
        auto_detect=os.getenv('LABJACK_AUTO_DETECT', 'true').lower() == 'true',
        device_type=os.getenv('LABJACK_DEVICE_TYPE', 'ANY'),
        connection_type=os.getenv('LABJACK_CONNECTION_TYPE', 'ANY'),
        identifier=os.getenv('LABJACK_IDENTIFIER', 'ANY'),
        bridge_enabled=os.getenv('LABJACK_BRIDGE_ENABLED', 'true').lower() == 'true',
        bridge_host=os.getenv('LABJACK_BRIDGE_HOST', 'localhost'),
        bridge_port=int(os.getenv('LABJACK_BRIDGE_PORT', '8080')),
        bridge_timeout=int(os.getenv('LABJACK_BRIDGE_TIMEOUT', '10')),
        bridge_reconnect_interval=int(os.getenv('LABJACK_BRIDGE_RECONNECT_INTERVAL', '5')),
        bridge_max_reconnects=int(os.getenv('LABJACK_BRIDGE_MAX_RECONNECTS', '10')),
        voltage_threshold=float(os.getenv('LABJACK_VOLTAGE_THRESHOLD', '2.5')),
        sample_rate=int(os.getenv('LABJACK_SAMPLE_RATE', '200')),
        channels=channels,
        use_stream_mode=os.getenv('LABJACK_USE_STREAM_MODE', 'true').lower() == 'true',
        stream_scans_per_read=int(os.getenv('LABJACK_STREAM_SCANS_PER_READ', '20')),
        stream_settling_us=int(os.getenv('LABJACK_STREAM_SETTLING_US', '0')),
        stream_resolution_index=int(os.getenv('LABJACK_STREAM_RESOLUTION_INDEX', '0')),
        stream_auto_fallback=os.getenv('LABJACK_STREAM_AUTO_FALLBACK', 'true').lower() == 'true',
        simulation_mode=os.getenv('LABJACK_SIMULATION_MODE', 'detection_spikes'),
        detection_probability=float(os.getenv('LABJACK_DETECTION_PROBABILITY', '0.05')),
        noise_amplitude=float(os.getenv('LABJACK_NOISE_AMPLITUDE', '0.1')),
        connection_timeout=int(os.getenv('LABJACK_CONNECTION_TIMEOUT', '5')),
        retry_attempts=int(os.getenv('LABJACK_RETRY_ATTEMPTS', '3')),
        log_level=os.getenv('LABJACK_LOG_LEVEL', 'INFO')
    )
    
    # Log configuration status
    if config.mock_mode:
        logger.info("🔧 LabJack running in MOCK MODE")
        logger.info(f"   - Simulation: {config.simulation_mode}")
        logger.info(f"   - Detection probability: {config.detection_probability}")
    else:
        logger.info("🔌 LabJack running in HARDWARE MODE")
        logger.info(f"   - Device: {config.device_type}")
        logger.info(f"   - Connection: {config.connection_type}")
    
    logger.info(f"   - Voltage threshold: {config.voltage_threshold}V")
    logger.info(f"   - Sample rate: {config.sample_rate}Hz")
    logger.info(f"   - Channels: {', '.join(config.channels)}")

    # Log stream mode configuration
    if config.use_stream_mode:
        stream_mode = "Stream mode" if config.sample_rate > 100 else "Stream mode (may use polling)"
        logger.info(f"   - Mode: {stream_mode}")
        logger.info(f"   - Stream buffer: {config.stream_scans_per_read} scans")
        logger.info(f"   - Stream resolution: {config.stream_resolution_index}")
    else:
        logger.info("   - Mode: Command-response (polling)")

    return config


def get_environment_status() -> Dict[str, Any]:
    """Get comprehensive status of LabJack environment"""
    config = load_config_from_env()
    availability = detect_labjack_availability()
    
    return {
        "timestamp": None,
        "config": config.to_dict(),
        "availability": availability,
        "environment_variables": {
            "LABJACK_MOCK_MODE": os.getenv('LABJACK_MOCK_MODE'),
            "LABJACK_DEVICE_TYPE": os.getenv('LABJACK_DEVICE_TYPE'),
            "LABJACK_CONNECTION_TYPE": os.getenv('LABJACK_CONNECTION_TYPE'),
            "LABJACK_BRIDGE_ENABLED": os.getenv('LABJACK_BRIDGE_ENABLED'),
            "LABJACK_BRIDGE_HOST": os.getenv('LABJACK_BRIDGE_HOST'),
            "LABJACK_BRIDGE_PORT": os.getenv('LABJACK_BRIDGE_PORT'),
            "LABJACK_VOLTAGE_THRESHOLD": os.getenv('LABJACK_VOLTAGE_THRESHOLD'),
            "LABJACK_SAMPLE_RATE": os.getenv('LABJACK_SAMPLE_RATE'),
            "LABJACK_CHANNELS": os.getenv('LABJACK_CHANNELS'),
            "LABJACK_USE_STREAM_MODE": os.getenv('LABJACK_USE_STREAM_MODE'),
            "LABJACK_STREAM_SCANS_PER_READ": os.getenv('LABJACK_STREAM_SCANS_PER_READ'),
            "LABJACK_STREAM_SETTLING_US": os.getenv('LABJACK_STREAM_SETTLING_US'),
            "LABJACK_STREAM_RESOLUTION_INDEX": os.getenv('LABJACK_STREAM_RESOLUTION_INDEX'),
            "LABJACK_STREAM_AUTO_FALLBACK": os.getenv('LABJACK_STREAM_AUTO_FALLBACK'),
            "LABJACK_AUTO_DETECT": os.getenv('LABJACK_AUTO_DETECT'),
            "LABJACK_SIMULATION_MODE": os.getenv('LABJACK_SIMULATION_MODE')
        },
        "recommendations": _generate_recommendations(config, availability)
    }


def _generate_recommendations(config: LabJackConfig, availability: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on current configuration and availability"""
    recommendations = []
    
    if config.mock_mode:
        recommendations.append("Running in mock mode - no hardware required")
        if not availability["ljm_library"]:
            recommendations.append("Install LabJack LJM library for hardware support: pip install labjack-ljm")
    
    else:
        if not availability["hardware_connected"]:
            recommendations.append("No LabJack hardware detected - check connections")
        
        if not availability["ljm_library"]:
            recommendations.append("LabJack LJM library required for hardware mode")
        
        if not availability["system_libraries"] and os.name == 'posix':
            recommendations.append("Install system libraries: sudo apt-get install libusb-1.0-0-dev libudev-dev")
    
    if config.voltage_threshold < 1.0:
        recommendations.append("Consider increasing voltage threshold to reduce noise sensitivity")
    
    if config.sample_rate > 10000:
        recommendations.append("High sample rates may impact system performance")
    
    if len(config.channels) > 4:
        recommendations.append("Using many channels may reduce per-channel sample rate")
    
    return recommendations


def create_default_env_file(filepath: Union[str, Path] = None):
    """Create a default .env file with LabJack configuration"""
    if filepath is None:
        filepath = Path(__file__).parent.parent / ".env.labjack"
    else:
        filepath = Path(filepath)
    
    env_content = """# LabJack Signal Validation Configuration
# Set LABJACK_MOCK_MODE=true for development without hardware

# Hardware Configuration
LABJACK_MOCK_MODE=false
LABJACK_AUTO_DETECT=true
LABJACK_DEVICE_TYPE=ANY
LABJACK_CONNECTION_TYPE=ANY
LABJACK_IDENTIFIER=ANY

# Bridge Configuration (Windows LabJack Bridge Service)
LABJACK_BRIDGE_ENABLED=true
LABJACK_BRIDGE_HOST=localhost
LABJACK_BRIDGE_PORT=8080
LABJACK_BRIDGE_TIMEOUT=10
LABJACK_BRIDGE_RECONNECT_INTERVAL=5
LABJACK_BRIDGE_MAX_RECONNECTS=10

# Signal Acquisition Settings
LABJACK_VOLTAGE_THRESHOLD=2.5
LABJACK_SAMPLE_RATE=1000
LABJACK_CHANNELS=AIN0,AIN1

# Stream Mode Configuration (for high-speed sampling > 100 Hz)
LABJACK_USE_STREAM_MODE=true
LABJACK_STREAM_SCANS_PER_READ=100
LABJACK_STREAM_SETTLING_US=0
LABJACK_STREAM_RESOLUTION_INDEX=0
LABJACK_STREAM_AUTO_FALLBACK=true

# Mock Mode Settings (used when LABJACK_MOCK_MODE=true)
LABJACK_SIMULATION_MODE=detection_spikes
LABJACK_DETECTION_PROBABILITY=0.05
LABJACK_NOISE_AMPLITUDE=0.1

# System Settings
LABJACK_CONNECTION_TIMEOUT=5
LABJACK_RETRY_ATTEMPTS=3
LABJACK_LOG_LEVEL=INFO
"""
    
    with open(filepath, 'w') as f:
        f.write(env_content)
    
    logger.info(f"Default LabJack environment file created: {filepath}")
    return filepath


# Initialize global configuration
_global_config = None


def get_global_config() -> LabJackConfig:
    """Get the global LabJack configuration instance"""
    global _global_config
    if _global_config is None:
        _global_config = load_config_from_env()
    return _global_config


def refresh_global_config():
    """Refresh the global configuration from environment variables"""
    global _global_config
    _global_config = load_config_from_env()
    logger.info("LabJack configuration refreshed")


# Example usage and testing
if __name__ == "__main__":
    print("🔧 LabJack Environment Configuration Test")
    
    # Test configuration loading
    config = load_config_from_env()
    print(f"📋 Configuration loaded:")
    print(f"   Mock mode: {config.mock_mode}")
    print(f"   Device type: {config.device_type}")
    print(f"   Voltage threshold: {config.voltage_threshold}V")
    print(f"   Sample rate: {config.sample_rate}Hz")
    print(f"   Channels: {', '.join(config.channels)}")
    
    # Test hardware detection
    availability = detect_labjack_availability()
    print(f"\n🔍 Hardware Availability:")
    print(f"   LJM library: {availability['ljm_library']}")
    print(f"   Hardware connected: {availability['hardware_connected']}")
    print(f"   Mock mode required: {availability['mock_mode_required']}")
    
    # Test environment status
    status = get_environment_status()
    print(f"\n💡 Recommendations:")
    for rec in status['recommendations']:
        print(f"   - {rec}")
    
    # Create default env file
    env_file = create_default_env_file("/tmp/test_labjack.env")
    print(f"\n📄 Default env file created: {env_file}")