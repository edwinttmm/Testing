"""
Camera Configuration Manager
Handles camera configuration management, persistence, and external IP integration
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass, asdict, field
import yaml
import os
import sqlite3
from contextlib import contextmanager

from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

# Configuration data models
@dataclass
class NetworkConfig:
    """Network configuration for camera connections"""
    external_ip: str = "155.138.239.131"
    internal_ip: str = "127.0.0.1"
    base_port: int = 8080
    port_range: range = field(default_factory=lambda: range(8080, 8100))
    websocket_port: int = 9090
    max_connections: int = 100
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_delay_seconds: int = 5

@dataclass
class CameraHardwareConfig:
    """Hardware-specific camera configuration"""
    camera_id: str
    display_name: str
    camera_type: str  # "webcam", "ip_camera", "usb", "gpio_trigger", "network_packet", "serial", "can_bus"
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    supported_formats: List[str] = field(default_factory=list)
    supported_resolutions: List[tuple] = field(default_factory=list)

@dataclass
class CameraConnectionConfig:
    """Camera connection configuration"""
    connection_type: str  # "tcp", "udp", "serial", "gpio", "usb"
    connection_url: str  # IP:port, device path, or GPIO pin
    protocol: Optional[str] = None  # "rtsp", "mjpeg", "h264", "raw"
    authentication: Optional[Dict[str, str]] = None
    ssl_enabled: bool = False
    compression: Optional[str] = None
    quality_settings: Optional[Dict[str, Any]] = None

@dataclass
class CameraProcessingConfig:
    """Camera processing and validation configuration"""
    validation_enabled: bool = True
    real_time_processing: bool = True
    buffer_size: int = 100
    max_fps: int = 30
    target_fps: int = 30
    resolution: tuple = (1920, 1080)
    format: str = "mjpeg"
    color_space: str = "RGB"
    preprocessing_enabled: bool = False
    preprocessing_steps: List[str] = field(default_factory=list)
    ml_inference_enabled: bool = True
    confidence_threshold: float = 0.5

@dataclass
class CameraAdvancedConfig:
    """Advanced camera configuration options"""
    auto_exposure: bool = True
    auto_white_balance: bool = True
    auto_focus: bool = True
    exposure_compensation: float = 0.0
    iso_sensitivity: Optional[int] = None
    white_balance_temperature: Optional[int] = None
    focus_distance: Optional[float] = None
    zoom_level: float = 1.0
    image_stabilization: bool = False
    noise_reduction: bool = True
    hdr_enabled: bool = False

@dataclass
class CameraMonitoringConfig:
    """Camera monitoring and alerting configuration"""
    health_check_enabled: bool = True
    health_check_interval_seconds: int = 30
    performance_monitoring: bool = True
    alert_on_failure: bool = True
    alert_threshold_fps: int = 15
    alert_threshold_latency_ms: int = 1000
    log_level: str = "INFO"
    metrics_collection: bool = True
    metrics_retention_days: int = 30

@dataclass
class CompleteCameraConfig:
    """Complete camera configuration combining all aspects"""
    camera_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    enabled: bool = True
    version: str = "1.0"
    
    # Sub-configurations
    hardware: CameraHardwareConfig = None
    network: NetworkConfig = None
    connection: CameraConnectionConfig = None
    processing: CameraProcessingConfig = None
    advanced: CameraAdvancedConfig = None
    monitoring: CameraMonitoringConfig = None
    
    # Additional metadata
    tags: List[str] = field(default_factory=list)
    description: Optional[str] = None
    location: Optional[str] = None
    owner: Optional[str] = None
    environment: str = "production"  # "development", "staging", "production"
    
    def __post_init__(self):
        """Initialize default sub-configurations if not provided"""
        if self.network is None:
            self.network = NetworkConfig()
        if self.processing is None:
            self.processing = CameraProcessingConfig()
        if self.advanced is None:
            self.advanced = CameraAdvancedConfig()
        if self.monitoring is None:
            self.monitoring = CameraMonitoringConfig()

class CameraConfigValidator:
    """Validates camera configurations"""
    
    @staticmethod
    def validate_network_config(network_config: NetworkConfig) -> List[str]:
        """Validate network configuration"""
        errors = []
        
        try:
            # Validate IP addresses
            import ipaddress
            ipaddress.ip_address(network_config.external_ip)
            ipaddress.ip_address(network_config.internal_ip)
        except ValueError as e:
            errors.append(f"Invalid IP address: {str(e)}")
        
        # Validate ports
        if not (1 <= network_config.base_port <= 65535):
            errors.append("Base port must be between 1 and 65535")
        
        if not (1 <= network_config.websocket_port <= 65535):
            errors.append("WebSocket port must be between 1 and 65535")
        
        # Validate connection limits
        if network_config.max_connections <= 0:
            errors.append("Max connections must be positive")
        
        if network_config.timeout_seconds <= 0:
            errors.append("Timeout must be positive")
        
        return errors
    
    @staticmethod
    def validate_processing_config(processing_config: CameraProcessingConfig) -> List[str]:
        """Validate processing configuration"""
        errors = []
        
        # Validate buffer size
        if processing_config.buffer_size <= 0:
            errors.append("Buffer size must be positive")
        
        # Validate FPS
        if not (1 <= processing_config.max_fps <= 120):
            errors.append("Max FPS must be between 1 and 120")
        
        if not (1 <= processing_config.target_fps <= processing_config.max_fps):
            errors.append("Target FPS must be between 1 and max FPS")
        
        # Validate resolution
        width, height = processing_config.resolution
        if width <= 0 or height <= 0:
            errors.append("Resolution dimensions must be positive")
        
        # Validate confidence threshold
        if not (0.0 <= processing_config.confidence_threshold <= 1.0):
            errors.append("Confidence threshold must be between 0.0 and 1.0")
        
        return errors
    
    @staticmethod
    def validate_complete_config(config: CompleteCameraConfig) -> List[str]:
        """Validate complete camera configuration"""
        errors = []
        
        # Validate camera ID
        if not config.camera_id or not config.camera_id.strip():
            errors.append("Camera ID is required")
        
        # Validate sub-configurations
        if config.network:
            errors.extend(CameraConfigValidator.validate_network_config(config.network))
        
        if config.processing:
            errors.extend(CameraConfigValidator.validate_processing_config(config.processing))
        
        # Validate hardware config if present
        if config.hardware:
            if not config.hardware.camera_type:
                errors.append("Camera type is required in hardware configuration")
        
        return errors

class CameraConfigPersistence:
    """Handles persistence of camera configurations"""
    
    def __init__(self, storage_path: str = "camera_configs"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        self.db_path = self.storage_path / "camera_configs.db"
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for configuration storage"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS camera_configs (
                    camera_id TEXT PRIMARY KEY,
                    config_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    environment TEXT NOT NULL
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS config_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    camera_id TEXT NOT NULL,
                    config_data TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    version TEXT NOT NULL,
                    change_reason TEXT,
                    FOREIGN KEY (camera_id) REFERENCES camera_configs (camera_id)
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_config_history_camera_id 
                ON config_history (camera_id)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_config_history_timestamp 
                ON config_history (timestamp)
            ''')
    
    @contextmanager
    def get_connection(self):
        """Get database connection context manager"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            yield conn
        finally:
            conn.close()
    
    def save_config(self, config: CompleteCameraConfig, change_reason: str = None) -> bool:
        """Save camera configuration to database"""
        try:
            config.updated_at = datetime.utcnow()
            config_json = json.dumps(asdict(config), default=str, indent=2)
            
            with self.get_connection() as conn:
                # Save current config
                conn.execute('''
                    INSERT OR REPLACE INTO camera_configs 
                    (camera_id, config_data, created_at, updated_at, version, enabled, environment)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    config.camera_id,
                    config_json,
                    config.created_at.isoformat(),
                    config.updated_at.isoformat(),
                    config.version,
                    1 if config.enabled else 0,
                    config.environment
                ))
                
                # Save to history
                conn.execute('''
                    INSERT INTO config_history 
                    (camera_id, config_data, timestamp, version, change_reason)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    config.camera_id,
                    config_json,
                    config.updated_at.isoformat(),
                    config.version,
                    change_reason or "Configuration updated"
                ))
                
                conn.commit()
            
            logger.info(f"Saved configuration for camera {config.camera_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config for {config.camera_id}: {str(e)}")
            return False
    
    def load_config(self, camera_id: str) -> Optional[CompleteCameraConfig]:
        """Load camera configuration from database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    'SELECT config_data FROM camera_configs WHERE camera_id = ?',
                    (camera_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                config_dict = json.loads(row[0])
                
                # Convert datetime strings back to datetime objects
                config_dict['created_at'] = datetime.fromisoformat(config_dict['created_at'])
                config_dict['updated_at'] = datetime.fromisoformat(config_dict['updated_at'])
                
                # Reconstruct sub-configurations
                if config_dict.get('hardware'):
                    config_dict['hardware'] = CameraHardwareConfig(**config_dict['hardware'])
                if config_dict.get('network'):
                    config_dict['network'] = NetworkConfig(**config_dict['network'])
                if config_dict.get('connection'):
                    config_dict['connection'] = CameraConnectionConfig(**config_dict['connection'])
                if config_dict.get('processing'):
                    config_dict['processing'] = CameraProcessingConfig(**config_dict['processing'])
                if config_dict.get('advanced'):
                    config_dict['advanced'] = CameraAdvancedConfig(**config_dict['advanced'])
                if config_dict.get('monitoring'):
                    config_dict['monitoring'] = CameraMonitoringConfig(**config_dict['monitoring'])
                
                config = CompleteCameraConfig(**config_dict)
                logger.info(f"Loaded configuration for camera {camera_id}")
                return config
                
        except Exception as e:
            logger.error(f"Failed to load config for {camera_id}: {str(e)}")
            return None
    
    def list_configs(self, environment: str = None, enabled_only: bool = False) -> List[str]:
        """List all camera configuration IDs"""
        try:
            query = 'SELECT camera_id FROM camera_configs WHERE 1=1'
            params = []
            
            if environment:
                query += ' AND environment = ?'
                params.append(environment)
            
            if enabled_only:
                query += ' AND enabled = 1'
            
            query += ' ORDER BY camera_id'
            
            with self.get_connection() as conn:
                cursor = conn.execute(query, params)
                return [row[0] for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to list configs: {str(e)}")
            return []
    
    def delete_config(self, camera_id: str) -> bool:
        """Delete camera configuration"""
        try:
            with self.get_connection() as conn:
                # Delete from both tables
                conn.execute('DELETE FROM camera_configs WHERE camera_id = ?', (camera_id,))
                conn.execute('DELETE FROM config_history WHERE camera_id = ?', (camera_id,))
                conn.commit()
            
            logger.info(f"Deleted configuration for camera {camera_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete config for {camera_id}: {str(e)}")
            return False
    
    def get_config_history(self, camera_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get configuration history for a camera"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT timestamp, version, change_reason 
                    FROM config_history 
                    WHERE camera_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (camera_id, limit))
                
                return [
                    {
                        "timestamp": row[0],
                        "version": row[1],
                        "change_reason": row[2]
                    }
                    for row in cursor.fetchall()
                ]
                
        except Exception as e:
            logger.error(f"Failed to get config history for {camera_id}: {str(e)}")
            return []

class CameraConfigManager:
    """Main camera configuration manager"""
    
    def __init__(self, storage_path: str = "camera_configs", external_ip: str = "155.138.239.131"):
        self.persistence = CameraConfigPersistence(storage_path)
        self.validator = CameraConfigValidator()
        self.external_ip = external_ip
        self.configs_cache: Dict[str, CompleteCameraConfig] = {}
        self.cache_timeout = timedelta(minutes=5)
        self.last_cache_update: Dict[str, datetime] = {}
    
    def create_default_config(self, camera_id: str, camera_type: str = "ip_camera") -> CompleteCameraConfig:
        """Create default configuration for a camera"""
        hardware_config = CameraHardwareConfig(
            camera_id=camera_id,
            display_name=f"Camera {camera_id}",
            camera_type=camera_type,
            capabilities=["video_streaming", "real_time_processing"],
            supported_formats=["mjpeg", "h264", "raw"],
            supported_resolutions=[(1920, 1080), (1280, 720), (640, 480)]
        )
        
        network_config = NetworkConfig(external_ip=self.external_ip)
        
        connection_config = CameraConnectionConfig(
            connection_type="tcp",
            connection_url=f"{self.external_ip}:8080",
            protocol="mjpeg"
        )
        
        return CompleteCameraConfig(
            camera_id=camera_id,
            hardware=hardware_config,
            network=network_config,
            connection=connection_config,
            description=f"Default configuration for {camera_type} camera",
            environment="development"
        )
    
    def validate_config(self, config: CompleteCameraConfig) -> tuple[bool, List[str]]:
        """Validate camera configuration"""
        errors = self.validator.validate_complete_config(config)
        return len(errors) == 0, errors
    
    def save_config(self, config: CompleteCameraConfig, change_reason: str = None) -> tuple[bool, List[str]]:
        """Save camera configuration with validation"""
        # Validate first
        is_valid, errors = self.validate_config(config)
        if not is_valid:
            return False, errors
        
        # Save to persistence
        success = self.persistence.save_config(config, change_reason)
        
        # Update cache
        if success:
            self.configs_cache[config.camera_id] = config
            self.last_cache_update[config.camera_id] = datetime.utcnow()
        
        return success, []
    
    def load_config(self, camera_id: str, use_cache: bool = True) -> Optional[CompleteCameraConfig]:
        """Load camera configuration"""
        # Check cache first
        if use_cache and camera_id in self.configs_cache:
            cache_time = self.last_cache_update.get(camera_id, datetime.min)
            if datetime.utcnow() - cache_time < self.cache_timeout:
                return self.configs_cache[camera_id]
        
        # Load from persistence
        config = self.persistence.load_config(camera_id)
        
        # Update cache
        if config:
            self.configs_cache[camera_id] = config
            self.last_cache_update[camera_id] = datetime.utcnow()
        
        return config
    
    def list_cameras(self, environment: str = None, enabled_only: bool = False) -> List[str]:
        """List all camera IDs"""
        return self.persistence.list_configs(environment, enabled_only)
    
    def delete_config(self, camera_id: str) -> bool:
        """Delete camera configuration"""
        success = self.persistence.delete_config(camera_id)
        
        # Remove from cache
        if success and camera_id in self.configs_cache:
            del self.configs_cache[camera_id]
            del self.last_cache_update[camera_id]
        
        return success
    
    def update_external_ip(self, new_external_ip: str) -> int:
        """Update external IP for all camera configurations"""
        updated_count = 0
        
        for camera_id in self.list_cameras():
            config = self.load_config(camera_id)
            if config and config.network:
                config.network.external_ip = new_external_ip
                
                # Update connection URL if it uses the old IP
                if config.connection and self.external_ip in config.connection.connection_url:
                    config.connection.connection_url = config.connection.connection_url.replace(
                        self.external_ip, new_external_ip
                    )
                
                success, _ = self.save_config(config, f"Updated external IP to {new_external_ip}")
                if success:
                    updated_count += 1
        
        self.external_ip = new_external_ip
        return updated_count
    
    def export_configs(self, output_path: str, format: str = "json") -> bool:
        """Export all configurations to file"""
        try:
            all_configs = {}
            
            for camera_id in self.list_cameras():
                config = self.load_config(camera_id)
                if config:
                    all_configs[camera_id] = asdict(config)
            
            output_file = Path(output_path)
            
            if format.lower() == "json":
                with open(output_file, 'w') as f:
                    json.dump(all_configs, f, default=str, indent=2)
            elif format.lower() in ["yaml", "yml"]:
                with open(output_file, 'w') as f:
                    yaml.dump(all_configs, f, default_flow_style=False)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            logger.info(f"Exported {len(all_configs)} configurations to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export configurations: {str(e)}")
            return False
    
    def import_configs(self, input_path: str, overwrite: bool = False) -> tuple[int, int]:
        """Import configurations from file"""
        imported_count = 0
        failed_count = 0
        
        try:
            input_file = Path(input_path)
            
            if not input_file.exists():
                raise FileNotFoundError(f"Import file not found: {input_path}")
            
            # Determine format from extension
            format = input_file.suffix.lower()
            
            if format == ".json":
                with open(input_file, 'r') as f:
                    configs_data = json.load(f)
            elif format in [".yaml", ".yml"]:
                with open(input_file, 'r') as f:
                    configs_data = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported file format: {format}")
            
            for camera_id, config_dict in configs_data.items():
                try:
                    # Check if config already exists
                    if not overwrite and self.load_config(camera_id):
                        logger.warning(f"Skipping existing config: {camera_id}")
                        continue
                    
                    # Convert datetime strings back to datetime objects
                    if isinstance(config_dict.get('created_at'), str):
                        config_dict['created_at'] = datetime.fromisoformat(config_dict['created_at'])
                    if isinstance(config_dict.get('updated_at'), str):
                        config_dict['updated_at'] = datetime.fromisoformat(config_dict['updated_at'])
                    
                    # Reconstruct sub-configurations
                    if config_dict.get('hardware'):
                        config_dict['hardware'] = CameraHardwareConfig(**config_dict['hardware'])
                    if config_dict.get('network'):
                        config_dict['network'] = NetworkConfig(**config_dict['network'])
                    if config_dict.get('connection'):
                        config_dict['connection'] = CameraConnectionConfig(**config_dict['connection'])
                    if config_dict.get('processing'):
                        config_dict['processing'] = CameraProcessingConfig(**config_dict['processing'])
                    if config_dict.get('advanced'):
                        config_dict['advanced'] = CameraAdvancedConfig(**config_dict['advanced'])
                    if config_dict.get('monitoring'):
                        config_dict['monitoring'] = CameraMonitoringConfig(**config_dict['monitoring'])
                    
                    config = CompleteCameraConfig(**config_dict)
                    success, errors = self.save_config(config, "Imported from file")
                    
                    if success:
                        imported_count += 1
                    else:
                        logger.error(f"Failed to import {camera_id}: {errors}")
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error importing config {camera_id}: {str(e)}")
                    failed_count += 1
            
            logger.info(f"Import completed: {imported_count} imported, {failed_count} failed")
            return imported_count, failed_count
            
        except Exception as e:
            logger.error(f"Failed to import configurations: {str(e)}")
            return 0, 1
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of all camera configurations"""
        camera_ids = self.list_cameras()
        
        summary = {
            "total_cameras": len(camera_ids),
            "enabled_cameras": len(self.list_cameras(enabled_only=True)),
            "camera_types": {},
            "environments": {},
            "external_ip": self.external_ip,
            "cache_size": len(self.configs_cache)
        }
        
        for camera_id in camera_ids:
            config = self.load_config(camera_id)
            if config:
                # Count camera types
                if config.hardware:
                    camera_type = config.hardware.camera_type
                    summary["camera_types"][camera_type] = summary["camera_types"].get(camera_type, 0) + 1
                
                # Count environments
                env = config.environment
                summary["environments"][env] = summary["environments"].get(env, 0) + 1
        
        return summary

# Global configuration manager instance
camera_config_manager = CameraConfigManager()

# Export main classes and instance
__all__ = [
    "CompleteCameraConfig",
    "CameraHardwareConfig", 
    "NetworkConfig",
    "CameraConnectionConfig",
    "CameraProcessingConfig",
    "CameraAdvancedConfig",
    "CameraMonitoringConfig",
    "CameraConfigManager",
    "camera_config_manager"
]