"""
Path Configuration Management
Centralized configuration for path management across deployment contexts.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import json

from src.utils.path_manager import PathType, DeploymentContext

logger = logging.getLogger(__name__)


@dataclass
class PathConfiguration:
    """Configuration for a specific path type in a deployment context"""
    path_type: PathType
    base_directory: str
    absolute_base_path: str
    create_if_missing: bool = True
    permissions: int = 0o755
    max_size_mb: Optional[int] = None
    allowed_extensions: Optional[List[str]] = None
    cleanup_policy: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None


class PathConfigManager:
    """Manages path configurations for different deployment contexts"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self.configurations = {}
        self._load_configurations()
    
    def _load_configurations(self):
        """Load path configurations from environment and config file"""
        
        # Load default configurations
        self._load_default_configurations()
        
        # Load from config file if provided
        if self.config_file and os.path.exists(self.config_file):
            self._load_from_file()
        
        # Override with environment variables
        self._load_from_environment()
    
    def _load_default_configurations(self):
        """Load default configurations for all deployment contexts"""
        
        # Development context configurations
        self.configurations[DeploymentContext.DEVELOPMENT] = {
            PathType.UPLOAD: PathConfiguration(
                path_type=PathType.UPLOAD,
                base_directory="uploads",
                absolute_base_path=str(Path.cwd() / "uploads"),
                max_size_mb=1000,
                allowed_extensions=['.mp4', '.avi', '.mov', '.mkv', '.webm'],
                cleanup_policy={'max_age_days': 30}
            ),
            PathType.SCREENSHOT: PathConfiguration(
                path_type=PathType.SCREENSHOT,
                base_directory="screenshots",
                absolute_base_path=str(Path.cwd() / "screenshots"),
                max_size_mb=500,
                allowed_extensions=['.jpg', '.jpeg', '.png'],
                cleanup_policy={'max_age_days': 7}
            ),
            PathType.VIDEO: PathConfiguration(
                path_type=PathType.VIDEO,
                base_directory="videos",
                absolute_base_path=str(Path.cwd() / "videos"),
                max_size_mb=5000,
                allowed_extensions=['.mp4', '.avi', '.mov', '.mkv', '.webm']
            ),
            PathType.GROUND_TRUTH: PathConfiguration(
                path_type=PathType.GROUND_TRUTH,
                base_directory="ground_truth",
                absolute_base_path=str(Path.cwd() / "ground_truth"),
                max_size_mb=100,
                allowed_extensions=['.json', '.xml', '.txt']
            ),
            PathType.REPORT: PathConfiguration(
                path_type=PathType.REPORT,
                base_directory="reports",
                absolute_base_path=str(Path.cwd() / "reports"),
                max_size_mb=200,
                allowed_extensions=['.html', '.pdf', '.json', '.csv'],
                cleanup_policy={'max_age_days': 90}
            ),
            PathType.TEMP: PathConfiguration(
                path_type=PathType.TEMP,
                base_directory="temp",
                absolute_base_path=str(Path.home() / ".ai-validation" / "temp"),
                max_size_mb=1000,
                cleanup_policy={'max_age_hours': 24}
            ),
            PathType.LOG: PathConfiguration(
                path_type=PathType.LOG,
                base_directory="logs",
                absolute_base_path=str(Path.cwd() / "logs"),
                max_size_mb=100,
                allowed_extensions=['.log', '.txt'],
                cleanup_policy={'max_files': 10, 'max_age_days': 30}
            )
        }
        
        # Container context configurations
        self.configurations[DeploymentContext.CONTAINER] = {
            PathType.UPLOAD: PathConfiguration(
                path_type=PathType.UPLOAD,
                base_directory="/app/uploads",
                absolute_base_path="/app/uploads",
                max_size_mb=2000,
                allowed_extensions=['.mp4', '.avi', '.mov', '.mkv', '.webm']
            ),
            PathType.SCREENSHOT: PathConfiguration(
                path_type=PathType.SCREENSHOT,
                base_directory="/app/screenshots",
                absolute_base_path="/app/screenshots",
                max_size_mb=1000,
                allowed_extensions=['.jpg', '.jpeg', '.png']
            ),
            PathType.VIDEO: PathConfiguration(
                path_type=PathType.VIDEO,
                base_directory="/app/videos",
                absolute_base_path="/app/videos",
                max_size_mb=10000,
                allowed_extensions=['.mp4', '.avi', '.mov', '.mkv', '.webm']
            ),
            PathType.GROUND_TRUTH: PathConfiguration(
                path_type=PathType.GROUND_TRUTH,
                base_directory="/app/ground_truth",
                absolute_base_path="/app/ground_truth",
                max_size_mb=500,
                allowed_extensions=['.json', '.xml', '.txt']
            ),
            PathType.REPORT: PathConfiguration(
                path_type=PathType.REPORT,
                base_directory="/app/reports",
                absolute_base_path="/app/reports",
                max_size_mb=1000,
                allowed_extensions=['.html', '.pdf', '.json', '.csv']
            ),
            PathType.TEMP: PathConfiguration(
                path_type=PathType.TEMP,
                base_directory="/tmp/ai-validation",
                absolute_base_path="/tmp/ai-validation",
                max_size_mb=2000,
                cleanup_policy={'max_age_hours': 12}
            ),
            PathType.LOG: PathConfiguration(
                path_type=PathType.LOG,
                base_directory="/app/logs",
                absolute_base_path="/app/logs",
                max_size_mb=500,
                allowed_extensions=['.log', '.txt']
            )
        }
        
        # Production context configurations
        self.configurations[DeploymentContext.PRODUCTION] = {
            PathType.UPLOAD: PathConfiguration(
                path_type=PathType.UPLOAD,
                base_directory="/var/lib/ai-validation/uploads",
                absolute_base_path="/var/lib/ai-validation/uploads",
                permissions=0o750,
                max_size_mb=10000,
                allowed_extensions=['.mp4', '.avi', '.mov', '.mkv', '.webm'],
                cleanup_policy={'max_age_days': 365}
            ),
            PathType.SCREENSHOT: PathConfiguration(
                path_type=PathType.SCREENSHOT,
                base_directory="/var/lib/ai-validation/screenshots",
                absolute_base_path="/var/lib/ai-validation/screenshots",
                permissions=0o750,
                max_size_mb=5000,
                allowed_extensions=['.jpg', '.jpeg', '.png'],
                cleanup_policy={'max_age_days': 30}
            ),
            PathType.VIDEO: PathConfiguration(
                path_type=PathType.VIDEO,
                base_directory="/var/lib/ai-validation/videos",
                absolute_base_path="/var/lib/ai-validation/videos",
                permissions=0o750,
                max_size_mb=50000,
                allowed_extensions=['.mp4', '.avi', '.mov', '.mkv', '.webm']
            ),
            PathType.GROUND_TRUTH: PathConfiguration(
                path_type=PathType.GROUND_TRUTH,
                base_directory="/var/lib/ai-validation/ground_truth",
                absolute_base_path="/var/lib/ai-validation/ground_truth",
                permissions=0o750,
                max_size_mb=1000,
                allowed_extensions=['.json', '.xml', '.txt']
            ),
            PathType.REPORT: PathConfiguration(
                path_type=PathType.REPORT,
                base_directory="/var/lib/ai-validation/reports",
                absolute_base_path="/var/lib/ai-validation/reports",
                permissions=0o750,
                max_size_mb=5000,
                allowed_extensions=['.html', '.pdf', '.json', '.csv'],
                cleanup_policy={'max_age_days': 180}
            ),
            PathType.TEMP: PathConfiguration(
                path_type=PathType.TEMP,
                base_directory="/tmp/ai-validation",
                absolute_base_path="/tmp/ai-validation",
                permissions=0o755,
                max_size_mb=5000,
                cleanup_policy={'max_age_hours': 6}
            ),
            PathType.LOG: PathConfiguration(
                path_type=PathType.LOG,
                base_directory="/var/log/ai-validation",
                absolute_base_path="/var/log/ai-validation",
                permissions=0o750,
                max_size_mb=1000,
                allowed_extensions=['.log', '.txt'],
                cleanup_policy={'max_files': 50, 'max_age_days': 90}
            )
        }
    
    def _load_from_file(self):
        """Load configurations from JSON config file"""
        try:
            with open(self.config_file, 'r') as f:
                file_config = json.load(f)
            
            # Merge file configurations with defaults
            for context_name, context_config in file_config.items():
                try:
                    context = DeploymentContext(context_name)
                    if context not in self.configurations:
                        self.configurations[context] = {}
                    
                    for path_type_name, path_config in context_config.items():
                        try:
                            path_type = PathType(path_type_name)
                            self.configurations[context][path_type] = PathConfiguration(
                                path_type=path_type,
                                base_directory=path_config.get('base_directory', ''),
                                absolute_base_path=path_config.get('absolute_base_path', ''),
                                create_if_missing=path_config.get('create_if_missing', True),
                                permissions=int(path_config.get('permissions', '0o755'), 8),
                                max_size_mb=path_config.get('max_size_mb'),
                                allowed_extensions=path_config.get('allowed_extensions'),
                                cleanup_policy=path_config.get('cleanup_policy'),
                                metadata=path_config.get('metadata', {})
                            )
                        except ValueError:
                            logger.warning(f"Unknown path type in config: {path_type_name}")
                except ValueError:
                    logger.warning(f"Unknown deployment context in config: {context_name}")
                    
        except Exception as e:
            logger.error(f"Failed to load path config from file: {str(e)}")
    
    def _load_from_environment(self):
        """Load configurations from environment variables"""
        
        # Environment variable patterns:
        # AI_VALIDATION_PATH_{CONTEXT}_{PATH_TYPE}_{SETTING}
        # Example: AI_VALIDATION_PATH_CONTAINER_UPLOAD_BASE_DIRECTORY
        
        env_prefix = "AI_VALIDATION_PATH_"
        
        for env_key, env_value in os.environ.items():
            if env_key.startswith(env_prefix):
                try:
                    # Parse environment variable name
                    parts = env_key[len(env_prefix):].lower().split('_')
                    if len(parts) >= 3:
                        context_name = parts[0]
                        path_type_name = parts[1]
                        setting_name = '_'.join(parts[2:])
                        
                        context = DeploymentContext(context_name)
                        path_type = PathType(path_type_name)
                        
                        # Get or create configuration
                        if context not in self.configurations:
                            self.configurations[context] = {}
                        if path_type not in self.configurations[context]:
                            self.configurations[context][path_type] = PathConfiguration(
                                path_type=path_type,
                                base_directory='',
                                absolute_base_path=''
                            )
                        
                        config = self.configurations[context][path_type]
                        
                        # Update configuration based on setting name
                        if setting_name == 'base_directory':
                            config.base_directory = env_value
                        elif setting_name == 'absolute_base_path':
                            config.absolute_base_path = env_value
                        elif setting_name == 'max_size_mb':
                            config.max_size_mb = int(env_value)
                        elif setting_name == 'permissions':
                            config.permissions = int(env_value, 8)  # Octal
                        elif setting_name == 'allowed_extensions':
                            config.allowed_extensions = env_value.split(',')
                        
                except (ValueError, IndexError) as e:
                    logger.warning(f"Invalid environment variable {env_key}: {str(e)}")
    
    def get_configuration(self, context: DeploymentContext, path_type: PathType) -> Optional[PathConfiguration]:
        """Get configuration for specific context and path type"""
        return self.configurations.get(context, {}).get(path_type)
    
    def get_all_configurations(self, context: DeploymentContext) -> Dict[PathType, PathConfiguration]:
        """Get all configurations for a deployment context"""
        return self.configurations.get(context, {})
    
    def validate_configuration(self, context: DeploymentContext) -> List[str]:
        """Validate configuration for a deployment context"""
        errors = []
        
        config = self.configurations.get(context, {})
        
        # Check that all required path types are configured
        required_path_types = [PathType.UPLOAD, PathType.VIDEO, PathType.SCREENSHOT]
        for path_type in required_path_types:
            if path_type not in config:
                errors.append(f"Missing configuration for {path_type.value} in {context.value}")
            else:
                path_config = config[path_type]
                if not path_config.absolute_base_path:
                    errors.append(f"Missing absolute_base_path for {path_type.value} in {context.value}")
        
        # Validate paths exist or can be created
        for path_type, path_config in config.items():
            try:
                path_obj = Path(path_config.absolute_base_path)
                if path_config.create_if_missing:
                    path_obj.mkdir(parents=True, exist_ok=True)
                elif not path_obj.exists():
                    errors.append(f"Path does not exist and create_if_missing is False: {path_config.absolute_base_path}")
                
                # Check permissions if path exists
                if path_obj.exists() and not os.access(path_obj, os.W_OK):
                    errors.append(f"Path is not writable: {path_config.absolute_base_path}")
                    
            except Exception as e:
                errors.append(f"Path validation failed for {path_type.value}: {str(e)}")
        
        return errors
    
    def create_directories(self, context: DeploymentContext) -> Dict[PathType, bool]:
        """Create all directories for a deployment context"""
        results = {}
        
        config = self.configurations.get(context, {})
        
        for path_type, path_config in config.items():
            try:
                if path_config.create_if_missing:
                    path_obj = Path(path_config.absolute_base_path)
                    path_obj.mkdir(parents=True, exist_ok=True)
                    
                    # Set permissions
                    if hasattr(path_config, 'permissions') and path_config.permissions:
                        path_obj.chmod(path_config.permissions)
                    
                    results[path_type] = True
                    logger.info(f"Created directory: {path_config.absolute_base_path}")
                else:
                    results[path_type] = Path(path_config.absolute_base_path).exists()
                    
            except Exception as e:
                logger.error(f"Failed to create directory for {path_type.value}: {str(e)}")
                results[path_type] = False
        
        return results
    
    def get_disk_usage(self, context: DeploymentContext) -> Dict[PathType, Dict[str, Any]]:
        """Get disk usage information for all configured paths"""
        usage = {}
        
        config = self.configurations.get(context, {})
        
        for path_type, path_config in config.items():
            try:
                path_obj = Path(path_config.absolute_base_path)
                if path_obj.exists():
                    # Calculate directory size
                    total_size = sum(f.stat().st_size for f in path_obj.rglob('*') if f.is_file())
                    file_count = len([f for f in path_obj.rglob('*') if f.is_file()])
                    
                    # Get disk space
                    disk_usage = os.statvfs(path_obj)
                    free_space = disk_usage.f_frsize * disk_usage.f_bavail
                    
                    usage[path_type] = {
                        'total_size_mb': total_size / (1024 * 1024),
                        'max_size_mb': path_config.max_size_mb,
                        'usage_percent': (total_size / (1024 * 1024)) / path_config.max_size_mb * 100 if path_config.max_size_mb else 0,
                        'file_count': file_count,
                        'free_space_mb': free_space / (1024 * 1024),
                        'path': str(path_obj)
                    }
                else:
                    usage[path_type] = {
                        'total_size_mb': 0,
                        'file_count': 0,
                        'path': str(path_obj),
                        'exists': False
                    }
                    
            except Exception as e:
                logger.error(f"Failed to get disk usage for {path_type.value}: {str(e)}")
                usage[path_type] = {'error': str(e)}
        
        return usage
    
    def export_configuration(self, context: DeploymentContext) -> Dict[str, Any]:
        """Export configuration as JSON-serializable dictionary"""
        config = self.configurations.get(context, {})
        
        exported = {
            'deployment_context': context.value,
            'configurations': {}
        }
        
        for path_type, path_config in config.items():
            exported['configurations'][path_type.value] = {
                'base_directory': path_config.base_directory,
                'absolute_base_path': path_config.absolute_base_path,
                'create_if_missing': path_config.create_if_missing,
                'permissions': oct(path_config.permissions) if path_config.permissions else None,
                'max_size_mb': path_config.max_size_mb,
                'allowed_extensions': path_config.allowed_extensions,
                'cleanup_policy': path_config.cleanup_policy,
                'metadata': path_config.metadata
            }
        
        return exported


# Global configuration manager
_config_manager = None


def get_path_config_manager(config_file: Optional[str] = None) -> PathConfigManager:
    """Get global path configuration manager"""
    global _config_manager
    if _config_manager is None or config_file is not None:
        _config_manager = PathConfigManager(config_file)
    return _config_manager


def get_path_configuration(context: DeploymentContext, path_type: PathType) -> Optional[PathConfiguration]:
    """Convenience function to get path configuration"""
    return get_path_config_manager().get_configuration(context, path_type)


def validate_all_configurations() -> Dict[DeploymentContext, List[str]]:
    """Validate configurations for all deployment contexts"""
    config_manager = get_path_config_manager()
    validation_results = {}
    
    for context in DeploymentContext:
        validation_results[context] = config_manager.validate_configuration(context)
    
    return validation_results