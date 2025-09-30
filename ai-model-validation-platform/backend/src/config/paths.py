"""
Centralized Path Management System
Replaces hardcoded file paths with configurable, environment-aware path management
"""

import os
import tempfile
import logging
from pathlib import Path
from typing import Dict, Optional, Union, List
from enum import Enum

logger = logging.getLogger(__name__)

class PathType(Enum):
    """Enumeration of different path types used in the system"""
    UPLOAD = "upload"
    SCREENSHOTS = "screenshots"
    MODELS = "models"
    EXPORTS = "exports"
    LOGS = "logs"
    TEMP = "temp"
    CONFIG = "config"
    CACHE = "cache"
    BACKUPS = "backups"

class PathManager:
    """
    Centralized path management with environment awareness
    
    Features:
    - Environment-specific path resolution
    - Automatic directory creation
    - Path validation and sanitization
    - Cross-platform compatibility
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.environment = self._detect_environment()
        self.base_dir = base_dir or self._get_base_directory()
        self._paths: Dict[PathType, Path] = {}
        
        # Initialize all paths
        self._initialize_paths()
        
        logger.info(f"PathManager initialized for environment: {self.environment}")
        logger.debug(f"Base directory: {self.base_dir}")
    
    def _detect_environment(self) -> str:
        """Detect current environment"""
        env_indicators = [
            os.getenv('AIVALIDATION_APP_ENVIRONMENT'),
            os.getenv('APP_ENV'),
            os.getenv('ENVIRONMENT'),
        ]
        
        for env in env_indicators:
            if env:
                env_lower = env.lower()
                if env_lower in ['production', 'prod']:
                    return 'production'
                elif env_lower in ['staging', 'stage']:
                    return 'staging'
                elif env_lower in ['test', 'testing']:
                    return 'test'
                elif env_lower in ['development', 'dev', 'local']:
                    return 'development'
        
        return 'development'
    
    def _get_base_directory(self) -> Path:
        """Get base directory for the application"""
        # Priority order for base directory
        base_candidates = [
            os.getenv('AIVALIDATION_BASE_DIR'),
            os.getenv('APP_BASE_DIR'),
            os.getenv('BASE_DIR'),
        ]
        
        for candidate in base_candidates:
            if candidate:
                path = Path(candidate)
                if path.exists() or self.environment in ['production', 'staging']:
                    return path.resolve()
        
        # Environment-specific defaults
        if self.environment == 'production':
            return Path('/app')
        elif self.environment == 'staging':
            return Path('/app')
        elif self.environment == 'test':
            # Use temporary directory for testing
            return Path(tempfile.mkdtemp(prefix='aivalidation_test_'))
        else:
            # Development - use current working directory
            return Path.cwd()
    
    def _initialize_paths(self):
        """Initialize all path configurations"""
        if self.environment == 'production':
            self._paths = {
                PathType.UPLOAD: self._resolve_path('UPLOAD_DIRECTORY', '/app/data/uploads'),
                PathType.SCREENSHOTS: self._resolve_path('SCREENSHOTS_DIRECTORY', '/app/data/screenshots'),
                PathType.MODELS: self._resolve_path('MODELS_DIRECTORY', '/app/models'),
                PathType.EXPORTS: self._resolve_path('EXPORTS_DIRECTORY', '/app/data/exports'),
                PathType.LOGS: self._resolve_path('LOGS_DIRECTORY', '/app/logs'),
                PathType.TEMP: self._resolve_path('TEMP_DIRECTORY', '/tmp/aivalidation'),
                PathType.CONFIG: self._resolve_path('CONFIG_DIRECTORY', '/app/config'),
                PathType.CACHE: self._resolve_path('CACHE_DIRECTORY', '/app/cache'),
                PathType.BACKUPS: self._resolve_path('BACKUPS_DIRECTORY', '/app/backups'),
            }
        elif self.environment == 'staging':
            self._paths = {
                PathType.UPLOAD: self._resolve_path('UPLOAD_DIRECTORY', '/app/data/uploads'),
                PathType.SCREENSHOTS: self._resolve_path('SCREENSHOTS_DIRECTORY', '/app/data/screenshots'),
                PathType.MODELS: self._resolve_path('MODELS_DIRECTORY', '/app/models'),
                PathType.EXPORTS: self._resolve_path('EXPORTS_DIRECTORY', '/app/data/exports'),
                PathType.LOGS: self._resolve_path('LOGS_DIRECTORY', '/app/logs'),
                PathType.TEMP: self._resolve_path('TEMP_DIRECTORY', '/tmp/aivalidation_staging'),
                PathType.CONFIG: self._resolve_path('CONFIG_DIRECTORY', '/app/config'),
                PathType.CACHE: self._resolve_path('CACHE_DIRECTORY', '/app/cache'),
                PathType.BACKUPS: self._resolve_path('BACKUPS_DIRECTORY', '/app/backups'),
            }
        elif self.environment == 'test':
            # Use temporary directories for all paths in test environment
            temp_base = self.base_dir
            self._paths = {
                PathType.UPLOAD: temp_base / 'uploads',
                PathType.SCREENSHOTS: temp_base / 'screenshots', 
                PathType.MODELS: temp_base / 'models',
                PathType.EXPORTS: temp_base / 'exports',
                PathType.LOGS: temp_base / 'logs',
                PathType.TEMP: temp_base / 'temp',
                PathType.CONFIG: temp_base / 'config',
                PathType.CACHE: temp_base / 'cache',
                PathType.BACKUPS: temp_base / 'backups',
            }
        else:  # development
            self._paths = {
                PathType.UPLOAD: self._resolve_path('UPLOAD_DIRECTORY', 'uploads'),
                PathType.SCREENSHOTS: self._resolve_path('SCREENSHOTS_DIRECTORY', 'screenshots'),
                PathType.MODELS: self._resolve_path('MODELS_DIRECTORY', 'models'),
                PathType.EXPORTS: self._resolve_path('EXPORTS_DIRECTORY', 'exports'),
                PathType.LOGS: self._resolve_path('LOGS_DIRECTORY', 'logs'),
                PathType.TEMP: self._resolve_path('TEMP_DIRECTORY', 'temp'),
                PathType.CONFIG: self._resolve_path('CONFIG_DIRECTORY', 'config'),
                PathType.CACHE: self._resolve_path('CACHE_DIRECTORY', 'cache'),
                PathType.BACKUPS: self._resolve_path('BACKUPS_DIRECTORY', 'backups'),
            }
    
    def _resolve_path(self, env_var: str, default: str) -> Path:
        """Resolve path from environment variable or default"""
        # Try environment variable first
        path_str = os.getenv(env_var)
        if path_str:
            path = Path(path_str)
        else:
            path = Path(default)
        
        # Convert relative paths to absolute based on base directory
        if not path.is_absolute():
            path = self.base_dir / path
        
        return path.resolve()
    
    def get_path(self, path_type: PathType) -> Path:
        """Get path for specific type"""
        if path_type not in self._paths:
            raise ValueError(f"Unknown path type: {path_type}")
        
        return self._paths[path_type]
    
    def ensure_path_exists(self, path_type: PathType) -> Path:
        """Ensure path exists and return it"""
        path = self.get_path(path_type)
        
        try:
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured path exists: {path}")
        except PermissionError as e:
            logger.error(f"Permission denied creating directory {path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to create directory {path}: {e}")
            raise
        
        return path
    
    def get_model_path(self, model_name: str) -> Path:
        """Get full path for a model file"""
        models_dir = self.ensure_path_exists(PathType.MODELS)
        return models_dir / model_name
    
    def get_upload_path(self, filename: str) -> Path:
        """Get full path for an uploaded file"""
        upload_dir = self.ensure_path_exists(PathType.UPLOAD)
        return upload_dir / filename
    
    def get_screenshot_path(self, filename: str) -> Path:
        """Get full path for a screenshot file"""
        screenshots_dir = self.ensure_path_exists(PathType.SCREENSHOTS)
        return screenshots_dir / filename
    
    def get_export_path(self, filename: str) -> Path:
        """Get full path for an export file"""
        exports_dir = self.ensure_path_exists(PathType.EXPORTS)
        return exports_dir / filename
    
    def get_log_path(self, filename: str) -> Path:
        """Get full path for a log file"""
        logs_dir = self.ensure_path_exists(PathType.LOGS)
        return logs_dir / filename
    
    def get_temp_path(self, filename: str) -> Path:
        """Get full path for a temporary file"""
        temp_dir = self.ensure_path_exists(PathType.TEMP)
        return temp_dir / filename
    
    def get_cache_path(self, filename: str) -> Path:
        """Get full path for a cache file"""
        cache_dir = self.ensure_path_exists(PathType.CACHE)
        return cache_dir / filename
    
    def get_backup_path(self, filename: str) -> Path:
        """Get full path for a backup file"""
        backup_dir = self.ensure_path_exists(PathType.BACKUPS)
        return backup_dir / filename
    
    def create_unique_filename(self, base_name: str, extension: str = "", path_type: PathType = PathType.TEMP) -> Path:
        """Create a unique filename in the specified directory"""
        import uuid
        import time
        
        # Generate unique suffix
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        
        if extension and not extension.startswith('.'):
            extension = f'.{extension}'
        
        unique_name = f"{base_name}_{timestamp}_{unique_id}{extension}"
        
        if path_type == PathType.UPLOAD:
            return self.get_upload_path(unique_name)
        elif path_type == PathType.SCREENSHOTS:
            return self.get_screenshot_path(unique_name)
        elif path_type == PathType.EXPORTS:
            return self.get_export_path(unique_name)
        elif path_type == PathType.LOGS:
            return self.get_log_path(unique_name)
        elif path_type == PathType.CACHE:
            return self.get_cache_path(unique_name)
        elif path_type == PathType.BACKUPS:
            return self.get_backup_path(unique_name)
        else:  # TEMP or others
            return self.get_temp_path(unique_name)
    
    def validate_path(self, path: Union[str, Path], path_type: Optional[PathType] = None) -> bool:
        """Validate if a path is safe and within expected boundaries"""
        try:
            path_obj = Path(path).resolve()
            
            # Check if path is within expected base directory
            if path_type:
                expected_base = self.get_path(path_type)
                try:
                    path_obj.relative_to(expected_base)
                except ValueError:
                    logger.warning(f"Path {path_obj} is outside expected base {expected_base}")
                    return False
            
            # Check for path traversal attempts
            path_str = str(path_obj)
            dangerous_patterns = ['..', '~', '$']
            if any(pattern in path_str for pattern in dangerous_patterns):
                logger.warning(f"Potentially dangerous path: {path_str}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Path validation failed for {path}: {e}")
            return False
    
    def cleanup_temp_files(self, older_than_hours: int = 24) -> int:
        """Clean up temporary files older than specified hours"""
        import time
        
        temp_dir = self.get_path(PathType.TEMP)
        if not temp_dir.exists():
            return 0
        
        current_time = time.time()
        cutoff_time = current_time - (older_than_hours * 3600)
        cleaned_count = 0
        
        try:
            for file_path in temp_dir.rglob('*'):
                if file_path.is_file():
                    file_mtime = file_path.stat().st_mtime
                    if file_mtime < cutoff_time:
                        try:
                            file_path.unlink()
                            cleaned_count += 1
                            logger.debug(f"Cleaned up temp file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to clean up {file_path}: {e}")
            
            logger.info(f"Cleaned up {cleaned_count} temporary files older than {older_than_hours} hours")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error during temp file cleanup: {e}")
            return 0
    
    def get_disk_usage(self, path_type: Optional[PathType] = None) -> Dict[str, Dict[str, Union[int, float]]]:
        """Get disk usage information for paths"""
        import shutil
        
        usage_info = {}
        
        path_types = [path_type] if path_type else list(PathType)
        
        for pt in path_types:
            try:
                path = self.get_path(pt)
                if path.exists():
                    total, used, free = shutil.disk_usage(path)
                    
                    # Calculate directory size
                    dir_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
                    
                    usage_info[pt.value] = {
                        'path': str(path),
                        'total_bytes': total,
                        'used_bytes': used,
                        'free_bytes': free,
                        'directory_size_bytes': dir_size,
                        'usage_percent': (used / total) * 100 if total > 0 else 0
                    }
                else:
                    usage_info[pt.value] = {
                        'path': str(path),
                        'exists': False
                    }
            except Exception as e:
                usage_info[pt.value] = {
                    'path': str(self.get_path(pt)),
                    'error': str(e)
                }
        
        return usage_info
    
    def get_path_summary(self) -> Dict[str, str]:
        """Get summary of all configured paths"""
        return {
            path_type.value: str(self.get_path(path_type))
            for path_type in PathType
        }
    
    def create_all_directories(self) -> List[Path]:
        """Create all configured directories"""
        created_paths = []
        
        for path_type in PathType:
            try:
                path = self.ensure_path_exists(path_type)
                created_paths.append(path)
            except Exception as e:
                logger.error(f"Failed to create directory for {path_type}: {e}")
        
        logger.info(f"Created {len(created_paths)} directories")
        return created_paths

# Global instance
path_manager = PathManager()

# Convenience functions for backward compatibility and ease of use
def get_upload_directory() -> Path:
    """Get upload directory path"""
    return path_manager.ensure_path_exists(PathType.UPLOAD)

def get_screenshots_directory() -> Path:
    """Get screenshots directory path"""
    return path_manager.ensure_path_exists(PathType.SCREENSHOTS)

def get_models_directory() -> Path:
    """Get models directory path"""
    return path_manager.ensure_path_exists(PathType.MODELS)

def get_exports_directory() -> Path:
    """Get exports directory path"""
    return path_manager.ensure_path_exists(PathType.EXPORTS)

def get_logs_directory() -> Path:
    """Get logs directory path"""
    return path_manager.ensure_path_exists(PathType.LOGS)

def get_temp_directory() -> Path:
    """Get temporary files directory path"""
    return path_manager.ensure_path_exists(PathType.TEMP)

def resolve_upload_directory() -> Path:
    """Resolve upload directory for legacy compatibility"""
    return get_upload_directory()

def get_path_summary() -> Dict[str, str]:
    """Get summary of all paths"""
    return path_manager.get_path_summary()

def validate_file_path(file_path: Union[str, Path], path_type: Optional[PathType] = None) -> bool:
    """Validate file path for security"""
    return path_manager.validate_path(file_path, path_type)