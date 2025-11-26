"""
LabJack Configuration for Real Hardware Integration
PRD Module 3.1 & 3.2 Configuration

Configuration settings for LabJack DAQ device connection and signal monitoring.
All settings are loaded from environment variables for production deployment.
"""

import os
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class DeviceType(Enum):
    """Supported LabJack device types"""
    T7 = "T7"
    T8 = "T8"
    U3 = "U3"
    U6 = "U6"
    UE9 = "UE9"
    T4 = "T4"
    ANY = "ANY"


class ConnectionType(Enum):
    """Supported connection types"""
    USB = "USB"
    ETHERNET = "ETHERNET"
    WIFI = "WIFI"
    ANY = "ANY"


@dataclass
class LabJackConfig:
    """LabJack hardware configuration"""
    
    # Device connection settings
    device_type: str = "ANY"                    # T7, U6, etc. or ANY
    connection_type: str = "ANY"                # USB, ETHERNET, WIFI, or ANY  
    device_identifier: str = "ANY"              # Serial number, IP, or ANY
    
    # TTL signal configuration
    ttl_channel: str = "DIO0"                   # Digital I/O channel for TTL
    analog_channel: str = "AIN0"                # Analog input as fallback
    voltage_threshold: float = 2.5              # TTL detection threshold (volts)
    voltage_range: float = 10.0                 # Input voltage range
    resolution_index: int = 0                   # ADC resolution (0=default, 8=fastest)
    settling_time_us: int = 0                   # Settling time in microseconds
    
    # Sampling configuration
    sample_rate: int = 10000                    # Sample rate in Hz
    samples_per_read: int = 100                 # Samples per read operation

    # Stream mode configuration (used when sample_rate > 100 Hz)
    use_stream_mode: bool = True                # Enable stream mode for high-speed sampling
    stream_scans_per_read: int = 100            # Buffer size (samples to read per stream call)
    stream_settling_us: int = 0                 # Stream settling time in microseconds
    stream_resolution_index: int = 0            # Stream resolution: 0 (fastest) to 8 (most accurate)
    stream_auto_fallback: bool = True           # Fallback to command-response if stream fails

    # Note: Stream mode is automatically enabled when:
    # - use_stream_mode = True AND sample_rate > 100 Hz
    # Otherwise, command-response (polling) mode is used

    # Detection parameters
    edge_detection: str = "rising_edge"         # "rising_edge", "falling_edge", "high", "low"
    debounce_time_ms: float = 1.0              # Debounce time to prevent multiple triggers
    signal_timeout_ms: int = 5000              # Max time to wait for signal
    
    # Timing precision (PRD Module 3.2)
    timing_precision: str = "microsecond"      # "microsecond", "millisecond", "nanosecond"
    use_monotonic_clock: bool = True           # Use monotonic clock for timing
    
    # Connection health monitoring
    connection_timeout_s: int = 10             # Connection timeout
    reconnect_attempts: int = 3                # Number of reconnection attempts
    health_check_interval_s: int = 30          # Health check interval
    
    # Performance tuning
    stream_buffer_size: int = 50000            # Stream data buffer size
    max_queue_size: int = 10000                # Hardware event queue size
    thread_priority: str = "normal"            # "normal", "high", "realtime"
    
    # Logging configuration
    log_level: str = "INFO"                    # Logging level
    log_hardware_events: bool = True           # Log all hardware events
    log_timing_events: bool = True             # Log precision timing events
    
    # Safety limits
    max_voltage_input: float = 10.0            # Maximum safe input voltage
    min_sample_rate: int = 1                   # Minimum sample rate
    max_sample_rate: int = 50000               # Maximum sample rate


def load_config_from_env() -> LabJackConfig:
    """
    Load LabJack configuration from environment variables
    
    Environment Variables:
    - LABJACK_DEVICE_TYPE: Device type (T7, U6, etc.)
    - LABJACK_CONNECTION_TYPE: Connection type (USB, ETHERNET, etc.)
    - LABJACK_DEVICE_ID: Device identifier (serial number or IP)
    - LABJACK_TTL_CHANNEL: TTL input channel
    - LABJACK_VOLTAGE_THRESHOLD: TTL detection threshold
    - LABJACK_SAMPLE_RATE: Sampling rate in Hz
    - LABJACK_USE_STREAM_MODE: Enable stream mode (true/false)
    - LABJACK_STREAM_SCANS_PER_READ: Stream buffer size (samples per read)
    - LABJACK_STREAM_SETTLING_US: Stream settling time (microseconds)
    - LABJACK_STREAM_RESOLUTION_INDEX: Stream resolution (0-8)
    - LABJACK_STREAM_AUTO_FALLBACK: Auto fallback to polling (true/false)
    - LABJACK_TIMING_PRECISION: Timing precision level
    - And more...
    """
    
    return LabJackConfig(
        # Device settings
        device_type=os.getenv("LABJACK_DEVICE_TYPE", "ANY"),
        connection_type=os.getenv("LABJACK_CONNECTION_TYPE", "ANY"),
        device_identifier=os.getenv("LABJACK_DEVICE_ID", "ANY"),
        
        # Signal settings
        ttl_channel=os.getenv("LABJACK_TTL_CHANNEL", "DIO0"),
        analog_channel=os.getenv("LABJACK_ANALOG_CHANNEL", "AIN0"),
        voltage_threshold=float(os.getenv("LABJACK_VOLTAGE_THRESHOLD", "2.5")),
        voltage_range=float(os.getenv("LABJACK_VOLTAGE_RANGE", "10.0")),
        resolution_index=int(os.getenv("LABJACK_RESOLUTION_INDEX", "0")),
        settling_time_us=int(os.getenv("LABJACK_SETTLING_TIME_US", "0")),
        
        # Sampling settings
        sample_rate=int(os.getenv("LABJACK_SAMPLE_RATE", "10000")),
        samples_per_read=int(os.getenv("LABJACK_SAMPLES_PER_READ", "100")),

        # Stream mode settings
        use_stream_mode=os.getenv("LABJACK_USE_STREAM_MODE", "true").lower() == "true",
        stream_scans_per_read=int(os.getenv("LABJACK_STREAM_SCANS_PER_READ", "100")),
        stream_settling_us=int(os.getenv("LABJACK_STREAM_SETTLING_US", "0")),
        stream_resolution_index=int(os.getenv("LABJACK_STREAM_RESOLUTION_INDEX", "0")),
        stream_auto_fallback=os.getenv("LABJACK_STREAM_AUTO_FALLBACK", "true").lower() == "true",

        # Detection settings
        edge_detection=os.getenv("LABJACK_EDGE_DETECTION", "rising_edge"),
        debounce_time_ms=float(os.getenv("LABJACK_DEBOUNCE_TIME_MS", "1.0")),
        signal_timeout_ms=int(os.getenv("LABJACK_SIGNAL_TIMEOUT_MS", "5000")),
        
        # Timing settings
        timing_precision=os.getenv("LABJACK_TIMING_PRECISION", "microsecond"),
        use_monotonic_clock=os.getenv("LABJACK_USE_MONOTONIC_CLOCK", "true").lower() == "true",
        
        # Connection settings
        connection_timeout_s=int(os.getenv("LABJACK_CONNECTION_TIMEOUT_S", "10")),
        reconnect_attempts=int(os.getenv("LABJACK_RECONNECT_ATTEMPTS", "3")),
        health_check_interval_s=int(os.getenv("LABJACK_HEALTH_CHECK_INTERVAL_S", "30")),
        
        # Performance settings
        stream_buffer_size=int(os.getenv("LABJACK_STREAM_BUFFER_SIZE", "50000")),
        max_queue_size=int(os.getenv("LABJACK_MAX_QUEUE_SIZE", "10000")),
        thread_priority=os.getenv("LABJACK_THREAD_PRIORITY", "normal"),
        
        # Logging settings
        log_level=os.getenv("LABJACK_LOG_LEVEL", "INFO"),
        log_hardware_events=os.getenv("LABJACK_LOG_HARDWARE_EVENTS", "true").lower() == "true",
        log_timing_events=os.getenv("LABJACK_LOG_TIMING_EVENTS", "true").lower() == "true",
        
        # Safety settings
        max_voltage_input=float(os.getenv("LABJACK_MAX_VOLTAGE_INPUT", "10.0")),
        min_sample_rate=int(os.getenv("LABJACK_MIN_SAMPLE_RATE", "1")),
        max_sample_rate=int(os.getenv("LABJACK_MAX_SAMPLE_RATE", "50000"))
    )


def validate_config(config: LabJackConfig) -> List[str]:
    """
    Validate LabJack configuration settings
    
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    # Validate device type
    try:
        if config.device_type != "ANY":
            DeviceType(config.device_type)
    except ValueError:
        errors.append(f"Invalid device_type: {config.device_type}")
    
    # Validate connection type
    try:
        if config.connection_type != "ANY":
            ConnectionType(config.connection_type)
    except ValueError:
        errors.append(f"Invalid connection_type: {config.connection_type}")
    
    # Validate voltage settings
    if not (0.1 <= config.voltage_threshold <= config.max_voltage_input):
        errors.append(f"voltage_threshold must be between 0.1 and {config.max_voltage_input}")
    
    if not (1.0 <= config.voltage_range <= 20.0):
        errors.append("voltage_range must be between 1.0 and 20.0")
    
    # Validate sample rate
    if not (config.min_sample_rate <= config.sample_rate <= config.max_sample_rate):
        errors.append(f"sample_rate must be between {config.min_sample_rate} and {config.max_sample_rate}")

    # Validate stream mode settings
    if config.stream_scans_per_read < 1 or config.stream_scans_per_read > 10000:
        errors.append("stream_scans_per_read must be between 1 and 10000")

    if config.stream_settling_us < 0:
        errors.append("stream_settling_us must be non-negative")

    if not (0 <= config.stream_resolution_index <= 8):
        errors.append("stream_resolution_index must be between 0 and 8")

    # Warn if stream mode is disabled but sample rate is high
    if not config.use_stream_mode and config.sample_rate > 100:
        errors.append("Warning: High sample rate (>100 Hz) without stream mode may cause performance issues")

    # Validate timing precision
    valid_precisions = ["millisecond", "microsecond", "nanosecond"]
    if config.timing_precision not in valid_precisions:
        errors.append(f"timing_precision must be one of: {valid_precisions}")
    
    # Validate edge detection
    valid_edges = ["rising_edge", "falling_edge", "high", "low"]
    if config.edge_detection not in valid_edges:
        errors.append(f"edge_detection must be one of: {valid_edges}")
    
    # Validate debounce time
    if not (0.0 <= config.debounce_time_ms <= 1000.0):
        errors.append("debounce_time_ms must be between 0.0 and 1000.0")
    
    return errors


# Production configuration examples
PRODUCTION_CONFIG = LabJackConfig(
    device_type="T7",
    connection_type="USB",
    ttl_channel="DIO0",
    voltage_threshold=3.3,
    sample_rate=10000,
    use_stream_mode=True,
    stream_scans_per_read=200,
    stream_settling_us=0,
    stream_resolution_index=0,
    timing_precision="microsecond",
    log_level="INFO"
)

DEVELOPMENT_CONFIG = LabJackConfig(
    device_type="ANY",
    connection_type="ANY",
    ttl_channel="DIO0",
    voltage_threshold=2.5,
    sample_rate=1000,
    use_stream_mode=True,
    stream_scans_per_read=100,
    stream_settling_us=0,
    stream_resolution_index=1,
    timing_precision="microsecond",
    log_level="DEBUG"
)

TEST_CONFIG = LabJackConfig(
    device_type="ANY",
    connection_type="ANY",
    ttl_channel="DIO0",
    voltage_threshold=2.5,
    sample_rate=100,
    use_stream_mode=False,  # Use polling mode for low sample rate
    stream_scans_per_read=50,
    stream_settling_us=10,
    stream_resolution_index=2,
    timing_precision="millisecond",
    log_level="INFO"
)


def get_config_for_environment(env: str = "development") -> LabJackConfig:
    """Get configuration for specific environment"""
    if env.lower() == "production":
        return PRODUCTION_CONFIG
    elif env.lower() == "test":
        return TEST_CONFIG
    else:
        return DEVELOPMENT_CONFIG


# Default configuration (loaded from environment)
default_config = load_config_from_env()