"""
LabJack Configuration Management Service
PRD Module 3.1 & 3.2 Configuration System

This service provides centralized configuration management for LabJack
hardware integration with environment-based settings, validation,
and dynamic configuration updates.

Features:
- Environment-based configuration loading
- Configuration validation and sanitization
- Dynamic configuration updates
- Configuration templates for different scenarios
- Backup and restore functionality
- Configuration monitoring and alerts
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


class ConfigurationMode(Enum):
    """Configuration modes for different environments"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"
    HIL_TESTING = "hil_testing"
    SIMULATION = "simulation"


class ValidationType(Enum):
    """Configuration validation types"""
    RANGE = "range"
    ENUM = "enum"
    REGEX = "regex"
    CUSTOM = "custom"


@dataclass
class ConfigurationRule:
    """Configuration validation rule"""
    field_name: str
    validation_type: ValidationType
    required: bool = True
    default_value: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[Any]] = None
    pattern: Optional[str] = None
    validator_function: Optional[callable] = None
    description: str = ""


@dataclass
class HardwareConfiguration:
    """Hardware-specific configuration"""
    device_type: str = "ANY"
    connection_type: str = "ANY"
    device_identifier: str = "ANY"
    auto_detect: bool = True
    connection_timeout: int = 10
    reconnect_attempts: int = 3
    reconnect_delay: float = 2.0
    
    # Channel configuration
    default_channels: List[str] = field(default_factory=lambda: ["AIN0", "AIN1"])
    channel_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Sampling configuration
    default_sample_rate: int = 10000
    max_sample_rate: int = 50000
    default_voltage_range: float = 10.0
    default_resolution_index: int = 0
    
    # Safety limits
    max_voltage_input: float = 10.0
    min_sample_rate: int = 100


@dataclass
class MonitoringConfiguration:
    """Signal monitoring configuration"""
    default_threshold_voltage: float = 2.5
    debounce_time_ms: float = 1.0
    detection_window_ms: float = 100.0
    edge_detection: str = "rising_edge"  # "rising_edge", "falling_edge", "high", "low"
    
    # Precision timing
    timing_precision: str = "microsecond"  # "microsecond", "millisecond"
    use_monotonic_clock: bool = True
    high_precision_mode: bool = True
    
    # Event handling
    max_event_queue_size: int = 50000
    event_batch_size: int = 100
    enable_event_callbacks: bool = True


@dataclass
class SynchronizationConfiguration:
    """Video-hardware synchronization configuration"""
    enable_sync: bool = False
    sync_tolerance_ms: float = 50.0
    frame_rate: float = 30.0
    enable_drift_correction: bool = True
    sync_marker_detection: bool = False
    
    # Timing validation
    max_latency_ms: float = 100.0
    latency_warning_threshold_ms: float = 50.0
    detection_rate_threshold: float = 0.95  # 95% detection rate expected


@dataclass
class ErrorHandlingConfiguration:
    """Error handling and recovery configuration"""
    enable_error_recovery: bool = True
    max_retry_attempts: int = 3
    retry_delay_seconds: List[float] = field(default_factory=lambda: [1.0, 2.0, 5.0])
    
    # Circuit breaker
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    circuit_open_duration_minutes: int = 2
    
    # Health monitoring
    health_check_enabled: bool = True
    health_check_interval_seconds: int = 30
    error_alert_threshold: int = 10


@dataclass
class LoggingConfiguration:
    """Logging configuration"""
    log_level: str = "INFO"
    log_hardware_events: bool = True
    log_timing_events: bool = True
    log_error_details: bool = True
    log_performance_metrics: bool = False
    
    # Log rotation
    max_log_size_mb: int = 100
    backup_count: int = 5
    
    # File paths
    hardware_log_file: Optional[str] = None
    timing_log_file: Optional[str] = None
    error_log_file: Optional[str] = None


@dataclass
class LabJackConfiguration:
    """Complete LabJack system configuration"""
    mode: ConfigurationMode = ConfigurationMode.DEVELOPMENT
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    
    # Sub-configurations
    hardware: HardwareConfiguration = field(default_factory=HardwareConfiguration)
    monitoring: MonitoringConfiguration = field(default_factory=MonitoringConfiguration)
    synchronization: SynchronizationConfiguration = field(default_factory=SynchronizationConfiguration)
    error_handling: ErrorHandlingConfiguration = field(default_factory=ErrorHandlingConfiguration)
    logging: LoggingConfiguration = field(default_factory=LoggingConfiguration)
    
    # Custom settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)


class LabJackConfigManager:
    """
    LabJack Configuration Management Service
    
    Provides centralized configuration management with validation,
    environment-based loading, and dynamic updates.
    """
    
    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent.parent / "config"
        self.config_dir.mkdir(exist_ok=True)
        
        # Current configuration
        self.current_config: Optional[LabJackConfiguration] = None
        self.config_file: Optional[Path] = None
        
        # Configuration templates
        self.templates: Dict[ConfigurationMode, LabJackConfiguration] = {}
        self._load_default_templates()
        
        # Validation rules
        self.validation_rules: List[ConfigurationRule] = []
        self._setup_validation_rules()
        
        # Configuration change callbacks
        self.change_callbacks: List[callable] = []
        
        # Thread safety
        self.lock = threading.RLock()
        
        logger.info("⚙️ LabJack Configuration Manager initialized")
    
    def load_configuration(self, mode: ConfigurationMode = ConfigurationMode.DEVELOPMENT,
                          config_file: Optional[Union[str, Path]] = None) -> LabJackConfiguration:
        """
        Load configuration from environment variables and file
        
        Args:
            mode: Configuration mode
            config_file: Optional configuration file path
            
        Returns:
            Loaded and validated configuration
        """
        with self.lock:
            # Start with template for the mode
            config = self._get_template_config(mode)
            
            # Load from environment variables
            config = self._load_from_environment(config)
            
            # Load from file if specified
            if config_file:
                file_config = self._load_from_file(config_file)
                if file_config:
                    config = self._merge_configurations(config, file_config)
                    self.config_file = Path(config_file)
            
            # Validate configuration
            validation_errors = self._validate_configuration(config)
            if validation_errors:
                logger.error(f"Configuration validation errors: {validation_errors}")
                # Apply fixes for common issues
                config = self._fix_configuration_issues(config, validation_errors)
            
            # Update timestamps
            config.modified_at = datetime.now()
            
            self.current_config = config
            
            logger.info(f"✅ Configuration loaded for {mode.value} mode")
            logger.info(f"   Device: {config.hardware.device_type} via {config.hardware.connection_type}")
            logger.info(f"   Channels: {config.hardware.default_channels}")
            logger.info(f"   Sample rate: {config.hardware.default_sample_rate} Hz")
            logger.info(f"   Threshold: {config.monitoring.default_threshold_voltage} V")
            
            return config
    
    def save_configuration(self, config: Optional[LabJackConfiguration] = None,
                          config_file: Optional[Union[str, Path]] = None) -> bool:
        """
        Save configuration to file
        
        Args:
            config: Configuration to save (uses current if None)
            config_file: File path to save to
            
        Returns:
            True if saved successfully
        """
        with self.lock:
            config = config or self.current_config
            if not config:
                logger.error("No configuration to save")
                return False
            
            if not config_file:
                if self.config_file:
                    config_file = self.config_file
                else:
                    config_file = self.config_dir / f"labjack_config_{config.mode.value}.json"
            
            try:
                config_file = Path(config_file)
                config_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Update modification time
                config.modified_at = datetime.now()
                
                # Convert to dictionary and handle datetime serialization
                config_dict = self._config_to_dict(config)
                
                with open(config_file, 'w') as f:
                    json.dump(config_dict, f, indent=2, default=str)
                
                self.config_file = config_file
                
                logger.info(f"💾 Configuration saved to {config_file}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to save configuration: {e}")
                return False
    
    def update_configuration(self, updates: Dict[str, Any], 
                           validate: bool = True, save: bool = True) -> bool:
        """
        Update current configuration with new values
        
        Args:
            updates: Dictionary of configuration updates
            validate: Whether to validate after updates
            save: Whether to save changes to file
            
        Returns:
            True if update was successful
        """
        with self.lock:
            if not self.current_config:
                logger.error("No current configuration to update")
                return False
            
            try:
                # Apply updates
                config = self._apply_updates(self.current_config, updates)
                
                # Validate if requested
                if validate:
                    validation_errors = self._validate_configuration(config)
                    if validation_errors:
                        logger.error(f"Configuration update validation failed: {validation_errors}")
                        return False
                
                # Update current configuration
                old_config = self.current_config
                self.current_config = config
                
                # Save if requested
                if save:
                    self.save_configuration()
                
                # Notify callbacks
                self._notify_config_change(old_config, config)
                
                logger.info("✅ Configuration updated successfully")
                return True
                
            except Exception as e:
                logger.error(f"Configuration update failed: {e}")
                return False
    
    def get_configuration(self) -> Optional[LabJackConfiguration]:
        """Get current configuration"""
        return self.current_config
    
    def get_template_configuration(self, mode: ConfigurationMode) -> LabJackConfiguration:
        """Get template configuration for a specific mode"""
        return self._get_template_config(mode)
    
    def validate_configuration(self, config: Optional[LabJackConfiguration] = None) -> List[str]:
        """
        Validate configuration
        
        Args:
            config: Configuration to validate (uses current if None)
            
        Returns:
            List of validation error messages
        """
        config = config or self.current_config
        if not config:
            return ["No configuration available to validate"]
        
        return self._validate_configuration(config)
    
    def backup_configuration(self, backup_name: Optional[str] = None) -> bool:
        """
        Create backup of current configuration
        
        Args:
            backup_name: Optional backup name
            
        Returns:
            True if backup created successfully
        """
        if not self.current_config:
            logger.error("No configuration to backup")
            return False
        
        backup_name = backup_name or f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_file = self.config_dir / "backups" / f"{backup_name}.json"
        
        return self.save_configuration(config_file=backup_file)
    
    def restore_configuration(self, backup_file: Union[str, Path]) -> bool:
        """
        Restore configuration from backup
        
        Args:
            backup_file: Path to backup file
            
        Returns:
            True if restored successfully
        """
        try:
            config = self._load_from_file(backup_file)
            if config:
                self.current_config = config
                self.save_configuration()
                logger.info(f"✅ Configuration restored from {backup_file}")
                return True
            else:
                logger.error(f"Failed to load backup from {backup_file}")
                return False
        except Exception as e:
            logger.error(f"Configuration restore failed: {e}")
            return False
    
    def add_change_callback(self, callback: callable):
        """Add callback for configuration changes"""
        self.change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: callable):
        """Remove configuration change callback"""
        if callback in self.change_callbacks:
            self.change_callbacks.remove(callback)
    
    def get_environment_variables_map(self) -> Dict[str, str]:
        """Get mapping of configuration fields to environment variables"""
        return {
            # Hardware configuration
            "hardware.device_type": "LABJACK_DEVICE_TYPE",
            "hardware.connection_type": "LABJACK_CONNECTION_TYPE",
            "hardware.device_identifier": "LABJACK_DEVICE_ID",
            "hardware.auto_detect": "LABJACK_AUTO_DETECT",
            "hardware.connection_timeout": "LABJACK_CONNECTION_TIMEOUT",
            "hardware.default_sample_rate": "LABJACK_SAMPLE_RATE",
            "hardware.default_voltage_range": "LABJACK_VOLTAGE_RANGE",
            
            # Monitoring configuration
            "monitoring.default_threshold_voltage": "LABJACK_THRESHOLD_VOLTAGE",
            "monitoring.debounce_time_ms": "LABJACK_DEBOUNCE_TIME_MS",
            "monitoring.edge_detection": "LABJACK_EDGE_DETECTION",
            "monitoring.timing_precision": "LABJACK_TIMING_PRECISION",
            
            # Synchronization configuration
            "synchronization.enable_sync": "LABJACK_ENABLE_SYNC",
            "synchronization.sync_tolerance_ms": "LABJACK_SYNC_TOLERANCE_MS",
            "synchronization.frame_rate": "LABJACK_FRAME_RATE",
            
            # Error handling configuration
            "error_handling.enable_error_recovery": "LABJACK_ENABLE_ERROR_RECOVERY",
            "error_handling.max_retry_attempts": "LABJACK_MAX_RETRY_ATTEMPTS",
            "error_handling.circuit_breaker_enabled": "LABJACK_CIRCUIT_BREAKER_ENABLED",
            
            # Logging configuration
            "logging.log_level": "LABJACK_LOG_LEVEL",
            "logging.log_hardware_events": "LABJACK_LOG_HARDWARE_EVENTS",
            "logging.log_timing_events": "LABJACK_LOG_TIMING_EVENTS"
        }
    
    def _load_default_templates(self):
        """Load default configuration templates"""
        
        # Development template
        self.templates[ConfigurationMode.DEVELOPMENT] = LabJackConfiguration(
            mode=ConfigurationMode.DEVELOPMENT,
            hardware=HardwareConfiguration(
                device_type="ANY",
                connection_type="ANY",
                auto_detect=True,
                default_sample_rate=1000
            ),
            monitoring=MonitoringConfiguration(
                default_threshold_voltage=2.5,
                timing_precision="millisecond",
                high_precision_mode=False
            ),
            synchronization=SynchronizationConfiguration(
                enable_sync=False
            ),
            error_handling=ErrorHandlingConfiguration(
                circuit_breaker_enabled=False,
                health_check_interval_seconds=60
            ),
            logging=LoggingConfiguration(
                log_level="DEBUG",
                log_performance_metrics=True
            )
        )
        
        # Production template
        self.templates[ConfigurationMode.PRODUCTION] = LabJackConfiguration(
            mode=ConfigurationMode.PRODUCTION,
            hardware=HardwareConfiguration(
                device_type="T7",
                connection_type="USB",
                auto_detect=False,
                default_sample_rate=10000
            ),
            monitoring=MonitoringConfiguration(
                default_threshold_voltage=3.3,
                timing_precision="microsecond",
                high_precision_mode=True
            ),
            synchronization=SynchronizationConfiguration(
                enable_sync=True,
                sync_tolerance_ms=20.0
            ),
            error_handling=ErrorHandlingConfiguration(
                circuit_breaker_enabled=True,
                health_check_interval_seconds=30
            ),
            logging=LoggingConfiguration(
                log_level="INFO",
                log_performance_metrics=True
            )
        )
        
        # HIL Testing template
        self.templates[ConfigurationMode.HIL_TESTING] = LabJackConfiguration(
            mode=ConfigurationMode.HIL_TESTING,
            hardware=HardwareConfiguration(
                device_type="T7",
                connection_type="USB",
                auto_detect=False,
                default_sample_rate=20000
            ),
            monitoring=MonitoringConfiguration(
                default_threshold_voltage=3.3,
                debounce_time_ms=0.5,
                timing_precision="microsecond",
                high_precision_mode=True
            ),
            synchronization=SynchronizationConfiguration(
                enable_sync=True,
                sync_tolerance_ms=10.0,
                enable_drift_correction=True
            ),
            error_handling=ErrorHandlingConfiguration(
                circuit_breaker_enabled=True,
                failure_threshold=3,
                health_check_interval_seconds=10
            ),
            logging=LoggingConfiguration(
                log_level="INFO",
                log_hardware_events=True,
                log_timing_events=True,
                log_performance_metrics=True
            )
        )
    
    def _setup_validation_rules(self):
        """Setup configuration validation rules"""
        self.validation_rules = [
            # Hardware validation
            ConfigurationRule(
                "hardware.device_type",
                ValidationType.ENUM,
                allowed_values=["T7", "T8", "U3", "U6", "UE9", "T4", "ANY"],
                description="Valid LabJack device types"
            ),
            ConfigurationRule(
                "hardware.connection_type",
                ValidationType.ENUM,
                allowed_values=["USB", "ETHERNET", "WIFI", "ANY"],
                description="Valid connection types"
            ),
            ConfigurationRule(
                "hardware.default_sample_rate",
                ValidationType.RANGE,
                min_value=1,
                max_value=100000,
                description="Sample rate must be between 1 and 100000 Hz"
            ),
            ConfigurationRule(
                "hardware.default_voltage_range",
                ValidationType.ENUM,
                allowed_values=[0.01, 0.1, 1.0, 10.0, 100.0],
                description="Standard LabJack voltage ranges"
            ),
            
            # Monitoring validation
            ConfigurationRule(
                "monitoring.default_threshold_voltage",
                ValidationType.RANGE,
                min_value=0.0,
                max_value=10.0,
                description="Threshold voltage must be within safe range"
            ),
            ConfigurationRule(
                "monitoring.timing_precision",
                ValidationType.ENUM,
                allowed_values=["millisecond", "microsecond"],
                description="Valid timing precision levels"
            ),
            ConfigurationRule(
                "monitoring.edge_detection",
                ValidationType.ENUM,
                allowed_values=["rising_edge", "falling_edge", "high", "low"],
                description="Valid edge detection modes"
            ),
            
            # Error handling validation
            ConfigurationRule(
                "error_handling.max_retry_attempts",
                ValidationType.RANGE,
                min_value=0,
                max_value=10,
                description="Retry attempts must be reasonable"
            ),
            ConfigurationRule(
                "error_handling.failure_threshold",
                ValidationType.RANGE,
                min_value=1,
                max_value=20,
                description="Circuit breaker failure threshold"
            ),
            
            # Logging validation
            ConfigurationRule(
                "logging.log_level",
                ValidationType.ENUM,
                allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                description="Valid logging levels"
            )
        ]
    
    def _get_template_config(self, mode: ConfigurationMode) -> LabJackConfiguration:
        """Get template configuration for mode"""
        if mode in self.templates:
            # Return a deep copy of the template
            import copy
            return copy.deepcopy(self.templates[mode])
        else:
            # Return development template as default
            import copy
            return copy.deepcopy(self.templates[ConfigurationMode.DEVELOPMENT])
    
    def _load_from_environment(self, config: LabJackConfiguration) -> LabJackConfiguration:
        """Load configuration from environment variables"""
        env_map = self.get_environment_variables_map()
        
        for field_path, env_var in env_map.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                try:
                    # Parse the value based on field type
                    parsed_value = self._parse_env_value(field_path, env_value)
                    self._set_config_field(config, field_path, parsed_value)
                except Exception as e:
                    logger.warning(f"Failed to parse environment variable {env_var}={env_value}: {e}")
        
        # Special handling for channel lists
        channels_str = os.getenv("LABJACK_CHANNELS")
        if channels_str:
            try:
                channels = [ch.strip() for ch in channels_str.split(',')]
                config.hardware.default_channels = channels
            except Exception as e:
                logger.warning(f"Failed to parse LABJACK_CHANNELS: {e}")
        
        return config
    
    def _load_from_file(self, config_file: Union[str, Path]) -> Optional[LabJackConfiguration]:
        """Load configuration from JSON file"""
        try:
            config_file = Path(config_file)
            if not config_file.exists():
                logger.warning(f"Configuration file not found: {config_file}")
                return None
            
            with open(config_file, 'r') as f:
                config_dict = json.load(f)
            
            return self._dict_to_config(config_dict)
            
        except Exception as e:
            logger.error(f"Failed to load configuration from {config_file}: {e}")
            return None
    
    def _merge_configurations(self, base: LabJackConfiguration, 
                            overlay: LabJackConfiguration) -> LabJackConfiguration:
        """Merge two configurations, with overlay taking precedence"""
        import copy
        merged = copy.deepcopy(base)
        
        # Merge each sub-configuration
        merged.hardware = self._merge_dataclass(merged.hardware, overlay.hardware)
        merged.monitoring = self._merge_dataclass(merged.monitoring, overlay.monitoring)
        merged.synchronization = self._merge_dataclass(merged.synchronization, overlay.synchronization)
        merged.error_handling = self._merge_dataclass(merged.error_handling, overlay.error_handling)
        merged.logging = self._merge_dataclass(merged.logging, overlay.logging)
        
        # Merge custom settings
        merged.custom_settings.update(overlay.custom_settings)
        
        # Update metadata
        merged.mode = overlay.mode
        merged.version = overlay.version
        merged.modified_at = datetime.now()
        
        return merged
    
    def _merge_dataclass(self, base, overlay):
        """Merge two dataclass instances"""
        import copy
        merged = copy.deepcopy(base)
        
        for field in overlay.__dataclass_fields__:
            overlay_value = getattr(overlay, field)
            if overlay_value != getattr(base, field, None):
                setattr(merged, field, overlay_value)
        
        return merged
    
    def _validate_configuration(self, config: LabJackConfiguration) -> List[str]:
        """Validate configuration against rules"""
        errors = []
        
        for rule in self.validation_rules:
            try:
                value = self._get_config_field(config, rule.field_name)
                
                if value is None and rule.required:
                    errors.append(f"{rule.field_name} is required but not set")
                    continue
                
                if value is None:
                    continue  # Optional field not set
                
                # Validate based on rule type
                if rule.validation_type == ValidationType.RANGE:
                    if rule.min_value is not None and value < rule.min_value:
                        errors.append(f"{rule.field_name} value {value} is below minimum {rule.min_value}")
                    if rule.max_value is not None and value > rule.max_value:
                        errors.append(f"{rule.field_name} value {value} is above maximum {rule.max_value}")
                
                elif rule.validation_type == ValidationType.ENUM:
                    if rule.allowed_values and value not in rule.allowed_values:
                        errors.append(f"{rule.field_name} value '{value}' not in allowed values: {rule.allowed_values}")
                
                elif rule.validation_type == ValidationType.CUSTOM:
                    if rule.validator_function:
                        if not rule.validator_function(value):
                            errors.append(f"{rule.field_name} failed custom validation")
                
            except Exception as e:
                errors.append(f"Validation error for {rule.field_name}: {e}")
        
        return errors
    
    def _fix_configuration_issues(self, config: LabJackConfiguration, 
                                errors: List[str]) -> LabJackConfiguration:
        """Apply automatic fixes for common configuration issues"""
        import copy
        fixed_config = copy.deepcopy(config)
        
        # Apply common fixes
        for error in errors:
            if "sample_rate" in error.lower() and "above maximum" in error:
                fixed_config.hardware.default_sample_rate = min(
                    fixed_config.hardware.default_sample_rate, 
                    50000
                )
                logger.info("Fixed sample rate to maximum allowed value")
            
            elif "threshold_voltage" in error.lower() and "above maximum" in error:
                fixed_config.monitoring.default_threshold_voltage = min(
                    fixed_config.monitoring.default_threshold_voltage,
                    10.0
                )
                logger.info("Fixed threshold voltage to maximum allowed value")
        
        return fixed_config
    
    def _apply_updates(self, config: LabJackConfiguration, 
                      updates: Dict[str, Any]) -> LabJackConfiguration:
        """Apply configuration updates"""
        import copy
        updated_config = copy.deepcopy(config)
        
        for field_path, value in updates.items():
            try:
                self._set_config_field(updated_config, field_path, value)
            except Exception as e:
                logger.error(f"Failed to apply update {field_path}={value}: {e}")
                raise
        
        updated_config.modified_at = datetime.now()
        return updated_config
    
    def _notify_config_change(self, old_config: LabJackConfiguration, 
                            new_config: LabJackConfiguration):
        """Notify callbacks of configuration changes"""
        for callback in self.change_callbacks:
            try:
                callback(old_config, new_config)
            except Exception as e:
                logger.error(f"Error in configuration change callback: {e}")
    
    def _parse_env_value(self, field_path: str, env_value: str) -> Any:
        """Parse environment variable value based on field type"""
        # Boolean values
        if env_value.lower() in ['true', 'false']:
            return env_value.lower() == 'true'
        
        # Numeric values
        try:
            if '.' in env_value:
                return float(env_value)
            else:
                return int(env_value)
        except ValueError:
            pass
        
        # String values
        return env_value
    
    def _get_config_field(self, config: LabJackConfiguration, field_path: str) -> Any:
        """Get configuration field value by path"""
        parts = field_path.split('.')
        current = config
        
        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        
        return current
    
    def _set_config_field(self, config: LabJackConfiguration, field_path: str, value: Any):
        """Set configuration field value by path"""
        parts = field_path.split('.')
        current = config
        
        for part in parts[:-1]:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                raise ValueError(f"Invalid field path: {field_path}")
        
        if hasattr(current, parts[-1]):
            setattr(current, parts[-1], value)
        else:
            raise ValueError(f"Invalid field path: {field_path}")
    
    def _config_to_dict(self, config: LabJackConfiguration) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "mode": config.mode.value,
            "version": config.version,
            "created_at": config.created_at.isoformat(),
            "modified_at": config.modified_at.isoformat(),
            "hardware": asdict(config.hardware),
            "monitoring": asdict(config.monitoring),
            "synchronization": asdict(config.synchronization),
            "error_handling": asdict(config.error_handling),
            "logging": asdict(config.logging),
            "custom_settings": config.custom_settings
        }
    
    def _dict_to_config(self, config_dict: Dict[str, Any]) -> LabJackConfiguration:
        """Convert dictionary to configuration"""
        # Parse timestamps
        created_at = datetime.fromisoformat(config_dict.get("created_at", datetime.now().isoformat()))
        modified_at = datetime.fromisoformat(config_dict.get("modified_at", datetime.now().isoformat()))
        
        return LabJackConfiguration(
            mode=ConfigurationMode(config_dict.get("mode", "development")),
            version=config_dict.get("version", "1.0.0"),
            created_at=created_at,
            modified_at=modified_at,
            hardware=HardwareConfiguration(**config_dict.get("hardware", {})),
            monitoring=MonitoringConfiguration(**config_dict.get("monitoring", {})),
            synchronization=SynchronizationConfiguration(**config_dict.get("synchronization", {})),
            error_handling=ErrorHandlingConfiguration(**config_dict.get("error_handling", {})),
            logging=LoggingConfiguration(**config_dict.get("logging", {})),
            custom_settings=config_dict.get("custom_settings", {})
        )


# Global configuration manager instance
_config_manager: Optional[LabJackConfigManager] = None


def get_config_manager(config_dir: Optional[Union[str, Path]] = None) -> LabJackConfigManager:
    """Get global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = LabJackConfigManager(config_dir)
    return _config_manager


def load_labjack_config(mode: ConfigurationMode = ConfigurationMode.DEVELOPMENT,
                       config_file: Optional[Union[str, Path]] = None) -> LabJackConfiguration:
    """Load LabJack configuration"""
    manager = get_config_manager()
    return manager.load_configuration(mode, config_file)


# Export key classes and functions
__all__ = [
    "LabJackConfigManager",
    "LabJackConfiguration",
    "HardwareConfiguration",
    "MonitoringConfiguration",
    "SynchronizationConfiguration",
    "ErrorHandlingConfiguration",
    "LoggingConfiguration",
    "ConfigurationMode",
    "get_config_manager",
    "load_labjack_config"
]