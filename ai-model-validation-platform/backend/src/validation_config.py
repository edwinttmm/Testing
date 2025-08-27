#!/usr/bin/env python3
"""
VRU Validation Engine Configuration Management

This module provides comprehensive configuration management for the VRU validation engine,
including environment-specific settings, validation criteria profiles, and runtime configuration.

Key Features:
- Environment-specific configuration (development, testing, production)
- Validation criteria profiles (default, strict, performance, safety)
- Dynamic configuration updates and validation
- Configuration persistence and backup
- Integration with existing system configuration

Configuration Hierarchy:
1. Default built-in configuration
2. Environment-specific overrides
3. Project-specific overrides
4. Runtime dynamic updates
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timezone

# Import validation engine components
from validation_engine import ValidationCriteria, AlignmentMethod, LatencyCategory

logger = logging.getLogger(__name__)

class ConfigurationProfile(Enum):
    """Predefined configuration profiles"""
    DEFAULT = "default"
    STRICT = "strict"
    PERFORMANCE = "performance"
    SAFETY_CRITICAL = "safety_critical"
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"

class ValidationMode(Enum):
    """Validation operation modes"""
    REAL_TIME = "real_time"
    BATCH = "batch"
    SIMULATION = "simulation"
    BENCHMARK = "benchmark"

@dataclass
class TemporalConfiguration:
    """Temporal alignment configuration"""
    default_tolerance_ms: float = 100.0
    adaptive_tolerance: bool = True
    alignment_method: AlignmentMethod = AlignmentMethod.ADAPTIVE
    strict_class_matching: bool = True
    interpolation_window_ms: float = 200.0
    clustering_threshold: float = 0.5
    max_alignment_distance_ms: float = 500.0

@dataclass
class LatencyConfiguration:
    """Latency analysis configuration"""
    base_threshold_ms: float = 100.0
    adaptive_thresholds: bool = True
    percentile_tracking: List[float] = field(default_factory=lambda: [50, 90, 95, 99])
    historical_window_size: int = 1000
    threshold_adaptation_rate: float = 0.7
    critical_threshold_multiplier: float = 2.0

@dataclass
class PerformanceConfiguration:
    """Performance and optimization configuration"""
    thread_pool_size: int = 4
    cache_size: int = 1000
    batch_processing_size: int = 100
    memory_limit_mb: int = 512
    timeout_seconds: int = 300
    enable_profiling: bool = False

@dataclass
class ReportConfiguration:
    """Report generation configuration"""
    default_format: str = "json"
    include_detailed_analysis: bool = True
    include_visualizations: bool = False
    export_raw_data: bool = False
    compression_enabled: bool = True
    retention_days: int = 90
    auto_export: bool = False

@dataclass
class IntegrationConfiguration:
    """Integration with external systems"""
    enable_camera_validation: bool = True
    enable_ml_engine_integration: bool = True
    database_connection_pool_size: int = 10
    api_timeout_seconds: int = 30
    webhook_endpoints: List[str] = field(default_factory=list)
    notification_channels: List[str] = field(default_factory=list)

@dataclass
class ValidationEngineConfiguration:
    """Complete validation engine configuration"""
    profile: ConfigurationProfile = ConfigurationProfile.DEFAULT
    mode: ValidationMode = ValidationMode.REAL_TIME
    validation_criteria: ValidationCriteria = field(default_factory=lambda: ValidationCriteria())
    temporal_config: TemporalConfiguration = field(default_factory=TemporalConfiguration)
    latency_config: LatencyConfiguration = field(default_factory=LatencyConfiguration)
    performance_config: PerformanceConfiguration = field(default_factory=PerformanceConfiguration)
    report_config: ReportConfiguration = field(default_factory=ReportConfiguration)
    integration_config: IntegrationConfiguration = field(default_factory=IntegrationConfiguration)
    
    # Metadata
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = "VRU Validation Engine Configuration"
    environment: str = "development"

class ConfigurationManager:
    """Comprehensive configuration management for VRU validation engine"""
    
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir) if config_dir else self._get_default_config_dir()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration cache
        self._config_cache = {}
        self._profile_cache = {}
        
        # Configuration file paths
        self.main_config_file = self.config_dir / "validation_engine.yaml"
        self.profiles_dir = self.config_dir / "profiles"
        self.profiles_dir.mkdir(exist_ok=True)
        
        # Load configurations
        self._load_configurations()
        
        logger.info(f"Configuration manager initialized with config dir: {self.config_dir}")
    
    def _get_default_config_dir(self) -> Path:
        """Get default configuration directory"""
        # Try to use project config directory
        backend_dir = Path(__file__).parent.parent
        config_dir = backend_dir.parent / "config"
        
        if not config_dir.exists():
            config_dir = backend_dir / "config"
        
        return config_dir
    
    def _load_configurations(self) -> None:
        """Load all configuration files"""
        try:
            # Load main configuration
            if self.main_config_file.exists():
                self._config_cache['main'] = self._load_config_file(self.main_config_file)
            else:
                self._config_cache['main'] = self._create_default_configuration()
                self.save_configuration(self._config_cache['main'])
            
            # Load profile configurations
            self._load_profile_configurations()
            
        except Exception as e:
            logger.error(f"Failed to load configurations: {e}")
            # Use default configuration as fallback
            self._config_cache['main'] = self._create_default_configuration()
    
    def _load_config_file(self, file_path: Path) -> ValidationEngineConfiguration:
        """Load configuration from file"""
        try:
            with open(file_path, 'r') as f:
                if file_path.suffix.lower() == '.yaml' or file_path.suffix.lower() == '.yml':
                    config_data = yaml.safe_load(f)
                else:
                    config_data = json.load(f)
            
            return self._dict_to_configuration(config_data)
            
        except Exception as e:
            logger.error(f"Failed to load config file {file_path}: {e}")
            raise
    
    def _dict_to_configuration(self, config_data: Dict) -> ValidationEngineConfiguration:
        """Convert dictionary to configuration object"""
        try:
            # Handle nested dataclass conversion
            config = ValidationEngineConfiguration()
            
            for key, value in config_data.items():
                if hasattr(config, key):
                    if key == 'validation_criteria':
                        setattr(config, key, ValidationCriteria(**value))
                    elif key == 'temporal_config':
                        # Handle AlignmentMethod enum
                        if 'alignment_method' in value:
                            value['alignment_method'] = AlignmentMethod(value['alignment_method'])
                        setattr(config, key, TemporalConfiguration(**value))
                    elif key == 'latency_config':
                        setattr(config, key, LatencyConfiguration(**value))
                    elif key == 'performance_config':
                        setattr(config, key, PerformanceConfiguration(**value))
                    elif key == 'report_config':
                        setattr(config, key, ReportConfiguration(**value))
                    elif key == 'integration_config':
                        setattr(config, key, IntegrationConfiguration(**value))
                    elif key == 'profile':
                        setattr(config, key, ConfigurationProfile(value))
                    elif key == 'mode':
                        setattr(config, key, ValidationMode(value))
                    elif key in ['created_at', 'updated_at']:
                        if isinstance(value, str):
                            setattr(config, key, datetime.fromisoformat(value))
                        else:
                            setattr(config, key, value)
                    else:
                        setattr(config, key, value)
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to convert dict to configuration: {e}")
            return self._create_default_configuration()
    
    def _load_profile_configurations(self) -> None:
        """Load all profile configurations"""
        try:
            # Create default profiles if they don't exist
            for profile in ConfigurationProfile:
                profile_file = self.profiles_dir / f"{profile.value}.yaml"
                
                if profile_file.exists():
                    self._profile_cache[profile.value] = self._load_config_file(profile_file)
                else:
                    # Create default profile configuration
                    default_config = self._create_profile_configuration(profile)
                    self._profile_cache[profile.value] = default_config
                    self._save_config_file(default_config, profile_file)
                    
        except Exception as e:
            logger.error(f"Failed to load profile configurations: {e}")
    
    def _create_default_configuration(self) -> ValidationEngineConfiguration:
        """Create default configuration"""
        return ValidationEngineConfiguration(
            profile=ConfigurationProfile.DEFAULT,
            mode=ValidationMode.REAL_TIME,
            environment=os.getenv("APP_ENVIRONMENT", "development")
        )
    
    def _create_profile_configuration(self, profile: ConfigurationProfile) -> ValidationEngineConfiguration:
        """Create configuration for specific profile"""
        base_config = self._create_default_configuration()
        base_config.profile = profile
        
        if profile == ConfigurationProfile.STRICT:
            base_config.validation_criteria = ValidationCriteria(
                precision_threshold=0.95,
                recall_threshold=0.90,
                f1_threshold=0.92,
                accuracy_threshold=0.93,
                latency_threshold_ms=50.0,
                temporal_tolerance_ms=25.0,
                confidence_threshold=0.85,
                adaptive_thresholds=False,
                strict_temporal_matching=True
            )
            base_config.temporal_config.default_tolerance_ms = 25.0
            base_config.latency_config.base_threshold_ms = 50.0
            
        elif profile == ConfigurationProfile.PERFORMANCE:
            base_config.validation_criteria = ValidationCriteria(
                latency_threshold_ms=200.0,
                adaptive_thresholds=True
            )
            base_config.performance_config.thread_pool_size = 8
            base_config.performance_config.batch_processing_size = 200
            base_config.temporal_config.alignment_method = AlignmentMethod.NEAREST_NEIGHBOR  # Fastest
            
        elif profile == ConfigurationProfile.SAFETY_CRITICAL:
            base_config.validation_criteria = ValidationCriteria(
                precision_threshold=0.98,
                recall_threshold=0.95,
                f1_threshold=0.96,
                accuracy_threshold=0.97,
                latency_threshold_ms=30.0,
                temporal_tolerance_ms=15.0,
                confidence_threshold=0.90,
                false_positive_rate_threshold=0.02,
                false_negative_rate_threshold=0.05,
                strict_temporal_matching=True
            )
            base_config.temporal_config.default_tolerance_ms = 15.0
            base_config.latency_config.base_threshold_ms = 30.0
            
        elif profile == ConfigurationProfile.DEVELOPMENT:
            base_config.validation_criteria.adaptive_thresholds = True
            base_config.performance_config.enable_profiling = True
            base_config.report_config.include_detailed_analysis = True
            base_config.report_config.export_raw_data = True
            
        elif profile == ConfigurationProfile.TESTING:
            base_config.mode = ValidationMode.SIMULATION
            base_config.performance_config.timeout_seconds = 600  # Longer timeout for tests
            base_config.report_config.auto_export = True
            
        elif profile == ConfigurationProfile.PRODUCTION:
            base_config.mode = ValidationMode.REAL_TIME
            base_config.performance_config.memory_limit_mb = 1024
            base_config.integration_config.enable_camera_validation = True
            base_config.integration_config.enable_ml_engine_integration = True
            base_config.report_config.compression_enabled = True
        
        base_config.description = f"Configuration profile for {profile.value} environment"
        return base_config
    
    def get_configuration(self, profile: Optional[ConfigurationProfile] = None) -> ValidationEngineConfiguration:
        """Get configuration for specified profile"""
        try:
            if profile is None:
                return self._config_cache.get('main', self._create_default_configuration())
            
            profile_key = profile.value
            if profile_key in self._profile_cache:
                return self._profile_cache[profile_key]
            else:
                # Create and cache profile configuration
                config = self._create_profile_configuration(profile)
                self._profile_cache[profile_key] = config
                return config
                
        except Exception as e:
            logger.error(f"Failed to get configuration for profile {profile}: {e}")
            return self._create_default_configuration()
    
    def save_configuration(
        self,
        config: ValidationEngineConfiguration,
        profile: Optional[ConfigurationProfile] = None
    ) -> None:
        """Save configuration to file"""
        try:
            config.updated_at = datetime.now(timezone.utc)
            
            if profile is None:
                # Save as main configuration
                self._config_cache['main'] = config
                file_path = self.main_config_file
            else:
                # Save as profile configuration
                self._profile_cache[profile.value] = config
                file_path = self.profiles_dir / f"{profile.value}.yaml"
            
            self._save_config_file(config, file_path)
            logger.info(f"Configuration saved to {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise
    
    def _save_config_file(self, config: ValidationEngineConfiguration, file_path: Path) -> None:
        """Save configuration to file"""
        try:
            # Convert to dictionary
            config_dict = asdict(config)
            
            # Handle special types for serialization
            def serialize_special_types(obj):
                if isinstance(obj, Enum):
                    return obj.value
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                return obj
            
            # Recursively process the dictionary
            def process_dict(d):
                if isinstance(d, dict):
                    return {k: process_dict(v) for k, v in d.items()}
                elif isinstance(d, list):
                    return [process_dict(item) for item in d]
                else:
                    return serialize_special_types(d)
            
            processed_dict = process_dict(config_dict)
            
            # Save as YAML
            with open(file_path, 'w') as f:
                yaml.dump(processed_dict, f, default_flow_style=False, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save config file {file_path}: {e}")
            raise
    
    def update_configuration(
        self,
        updates: Dict[str, Any],
        profile: Optional[ConfigurationProfile] = None
    ) -> ValidationEngineConfiguration:
        """Update configuration with new values"""
        try:
            config = self.get_configuration(profile)
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(config, key):
                    setattr(config, key, value)
                else:
                    logger.warning(f"Unknown configuration key: {key}")
            
            # Save updated configuration
            self.save_configuration(config, profile)
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to update configuration: {e}")
            raise
    
    def validate_configuration(self, config: ValidationEngineConfiguration) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        try:
            # Validate validation criteria
            criteria = config.validation_criteria
            if not (0.0 <= criteria.precision_threshold <= 1.0):
                issues.append("Precision threshold must be between 0.0 and 1.0")
            
            if not (0.0 <= criteria.recall_threshold <= 1.0):
                issues.append("Recall threshold must be between 0.0 and 1.0")
            
            if criteria.latency_threshold_ms <= 0:
                issues.append("Latency threshold must be positive")
            
            # Validate temporal configuration
            temporal = config.temporal_config
            if temporal.default_tolerance_ms <= 0:
                issues.append("Default tolerance must be positive")
            
            if temporal.max_alignment_distance_ms < temporal.default_tolerance_ms:
                issues.append("Max alignment distance must be >= default tolerance")
            
            # Validate performance configuration
            perf = config.performance_config
            if perf.thread_pool_size <= 0:
                issues.append("Thread pool size must be positive")
            
            if perf.memory_limit_mb <= 0:
                issues.append("Memory limit must be positive")
            
            # Validate report configuration
            report = config.report_config
            if report.default_format not in ['json', 'csv', 'html', 'yaml']:
                issues.append("Invalid default report format")
            
            if report.retention_days <= 0:
                issues.append("Report retention days must be positive")
            
        except Exception as e:
            issues.append(f"Configuration validation error: {e}")
        
        return issues
    
    def get_environment_configuration(self) -> ValidationEngineConfiguration:
        """Get configuration based on current environment"""
        env = os.getenv("APP_ENVIRONMENT", "development").lower()
        
        env_profile_mapping = {
            "development": ConfigurationProfile.DEVELOPMENT,
            "dev": ConfigurationProfile.DEVELOPMENT,
            "testing": ConfigurationProfile.TESTING,
            "test": ConfigurationProfile.TESTING,
            "production": ConfigurationProfile.PRODUCTION,
            "prod": ConfigurationProfile.PRODUCTION,
        }
        
        profile = env_profile_mapping.get(env, ConfigurationProfile.DEFAULT)
        return self.get_configuration(profile)
    
    def export_configuration(
        self,
        output_path: str,
        profile: Optional[ConfigurationProfile] = None,
        format_type: str = 'yaml'
    ) -> None:
        """Export configuration to file"""
        try:
            config = self.get_configuration(profile)
            output_file = Path(output_path)
            
            if format_type.lower() == 'json':
                config_dict = asdict(config)
                with open(output_file, 'w') as f:
                    json.dump(config_dict, f, indent=2, default=str)
            else:
                self._save_config_file(config, output_file)
            
            logger.info(f"Configuration exported to {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            raise
    
    def import_configuration(
        self,
        input_path: str,
        profile: Optional[ConfigurationProfile] = None
    ) -> ValidationEngineConfiguration:
        """Import configuration from file"""
        try:
            config = self._load_config_file(Path(input_path))
            
            # Validate imported configuration
            issues = self.validate_configuration(config)
            if issues:
                logger.warning(f"Configuration validation issues: {issues}")
            
            # Save imported configuration
            self.save_configuration(config, profile)
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to import configuration: {e}")
            raise
    
    def create_configuration_backup(self) -> str:
        """Create backup of all configurations"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.config_dir / "backups" / timestamp
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup main configuration
            if self.main_config_file.exists():
                backup_file = backup_dir / "validation_engine.yaml"
                backup_file.write_text(self.main_config_file.read_text())
            
            # Backup profile configurations
            profiles_backup_dir = backup_dir / "profiles"
            profiles_backup_dir.mkdir(exist_ok=True)
            
            for profile_file in self.profiles_dir.glob("*.yaml"):
                backup_file = profiles_backup_dir / profile_file.name
                backup_file.write_text(profile_file.read_text())
            
            logger.info(f"Configuration backup created at {backup_dir}")
            return str(backup_dir)
            
        except Exception as e:
            logger.error(f"Failed to create configuration backup: {e}")
            raise
    
    def list_available_profiles(self) -> List[str]:
        """List all available configuration profiles"""
        return list(self._profile_cache.keys())
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get summary of current configuration state"""
        try:
            return {
                'config_dir': str(self.config_dir),
                'main_config_exists': self.main_config_file.exists(),
                'available_profiles': self.list_available_profiles(),
                'cache_size': len(self._config_cache) + len(self._profile_cache),
                'last_updated': max(
                    config.updated_at for config in 
                    list(self._config_cache.values()) + list(self._profile_cache.values())
                    if hasattr(config, 'updated_at')
                ) if (self._config_cache or self._profile_cache) else None
            }
        except Exception as e:
            logger.error(f"Failed to get configuration summary: {e}")
            return {}


# Utility functions for easy configuration access

def get_default_configuration() -> ValidationEngineConfiguration:
    """Get default validation engine configuration"""
    manager = ConfigurationManager()
    return manager.get_configuration()

def get_configuration_for_environment(environment: str = None) -> ValidationEngineConfiguration:
    """Get configuration for specific environment"""
    if environment:
        os.environ["APP_ENVIRONMENT"] = environment
    
    manager = ConfigurationManager()
    return manager.get_environment_configuration()

def create_configuration_manager(config_dir: str = None) -> ConfigurationManager:
    """Create configuration manager instance"""
    return ConfigurationManager(config_dir)


# CLI interface for configuration management
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="VRU Validation Engine Configuration Manager")
    parser.add_argument("--config-dir", help="Configuration directory path")
    parser.add_argument("--profile", choices=[p.value for p in ConfigurationProfile], help="Configuration profile")
    parser.add_argument("--export", help="Export configuration to file")
    parser.add_argument("--import", dest="import_file", help="Import configuration from file")
    parser.add_argument("--validate", action="store_true", help="Validate configuration")
    parser.add_argument("--backup", action="store_true", help="Create configuration backup")
    parser.add_argument("--list-profiles", action="store_true", help="List available profiles")
    parser.add_argument("--summary", action="store_true", help="Show configuration summary")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        manager = ConfigurationManager(args.config_dir)
        profile = ConfigurationProfile(args.profile) if args.profile else None
        
        if args.export:
            manager.export_configuration(args.export, profile)
            print(f"Configuration exported to {args.export}")
        
        elif args.import_file:
            config = manager.import_configuration(args.import_file, profile)
            print(f"Configuration imported from {args.import_file}")
            print(f"Profile: {config.profile.value}")
        
        elif args.validate:
            config = manager.get_configuration(profile)
            issues = manager.validate_configuration(config)
            if issues:
                print("Configuration validation issues:")
                for issue in issues:
                    print(f"  - {issue}")
            else:
                print("Configuration is valid")
        
        elif args.backup:
            backup_path = manager.create_configuration_backup()
            print(f"Configuration backup created at {backup_path}")
        
        elif args.list_profiles:
            profiles = manager.list_available_profiles()
            print("Available configuration profiles:")
            for profile_name in profiles:
                print(f"  - {profile_name}")
        
        elif args.summary:
            summary = manager.get_configuration_summary()
            print("Configuration Summary:")
            for key, value in summary.items():
                print(f"  {key}: {value}")
        
        else:
            config = manager.get_configuration(profile)
            print(f"Current configuration profile: {config.profile.value}")
            print(f"Environment: {config.environment}")
            print(f"Mode: {config.mode.value}")
            print(f"Version: {config.version}")
        
    except Exception as e:
        print(f"Configuration management failed: {e}")
        exit(1)