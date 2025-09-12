#!/usr/bin/env python3
"""
PathResolver - SPARC Architecture Component  
Environment-aware filesystem path management
Handles Docker vs Local path differences with intelligent fallbacks
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum

from .environment_detector import detect_environment, EnvironmentType, ServiceMode

logger = logging.getLogger(__name__)

class PathType(Enum):
    """Types of paths that need resolution"""
    UPLOAD_DIRECTORY = "upload_directory"
    LOG_DIRECTORY = "log_directory"
    DATA_DIRECTORY = "data_directory"
    CONFIG_DIRECTORY = "config_directory"
    TEMP_DIRECTORY = "temp_directory"
    MODEL_DIRECTORY = "model_directory"
    EXPORT_DIRECTORY = "export_directory"
    CACHE_DIRECTORY = "cache_directory"

@dataclass
class ResolvedPath:
    """Resolved path information"""
    path: str
    exists: bool
    is_writable: bool
    is_readable: bool
    absolute_path: str
    parent_exists: bool
    resolved_from: str  # How the path was resolved
    
class PathResolver:
    """
    Environment-aware path resolver with intelligent fallbacks
    Handles Docker container paths vs local development paths
    """
    
    def __init__(self):
        self._env_info = detect_environment()
        self._path_cache: Dict[str, ResolvedPath] = {}
        
        # Base path strategies by environment type
        self._base_paths = {
            EnvironmentType.DOCKER: {
                'root': '/app',
                'data': '/app/data',
                'uploads': '/app/uploads',
                'logs': '/app/logs',
                'config': '/app/config',
                'temp': '/tmp',
                'models': '/app/models',
                'exports': '/app/exports',
                'cache': '/app/cache'
            },
            EnvironmentType.LOCAL: {
                'root': os.getcwd(),
                'data': './data',
                'uploads': './uploads',
                'logs': './logs',
                'config': './config',
                'temp': './temp',
                'models': './models',
                'exports': './exports',
                'cache': './cache'
            },
            EnvironmentType.WSL: {
                'root': os.getcwd(),
                'data': './data',
                'uploads': './uploads', 
                'logs': './logs',
                'config': './config',
                'temp': '/tmp',
                'models': './models',
                'exports': './exports',
                'cache': './cache'
            }
        }
        
    def resolve_path(self, 
                    path_type: PathType, 
                    custom_path: Optional[str] = None,
                    ensure_exists: bool = True) -> ResolvedPath:
        """
        Resolve a path based on environment and requirements
        
        Args:
            path_type: Type of path to resolve
            custom_path: Custom path override (from env vars or config)
            ensure_exists: Whether to create the path if it doesn't exist
            
        Returns:
            ResolvedPath with complete path information
        """
        cache_key = f"{path_type.value}:{custom_path}:{ensure_exists}"
        
        # Check cache first
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]
        
        logger.debug(f"🗂️  Resolving path for {path_type.value}")
        
        # Try resolution strategies in order
        strategies = [
            lambda: self._resolve_from_custom(path_type, custom_path),
            lambda: self._resolve_from_environment_variables(path_type),
            lambda: self._resolve_from_base_paths(path_type),
            lambda: self._resolve_fallback(path_type)
        ]
        
        resolved_path = None
        
        for strategy in strategies:
            try:
                result = strategy()
                if result:
                    resolved_path = result
                    break
            except Exception as e:
                logger.debug(f"Path resolution strategy failed: {e}")
        
        if not resolved_path:
            # Final fallback
            resolved_path = ResolvedPath(
                path="./",
                exists=True,
                is_writable=True,
                is_readable=True,
                absolute_path=os.path.abspath("./"),
                parent_exists=True,
                resolved_from="final_fallback"
            )
        
        # Ensure path exists if requested
        if ensure_exists and not resolved_path.exists:
            try:
                os.makedirs(resolved_path.path, exist_ok=True)
                resolved_path.exists = True
                resolved_path.parent_exists = True
                logger.info(f"✅ Created directory: {resolved_path.path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to create directory {resolved_path.path}: {e}")
        
        # Cache the result
        self._path_cache[cache_key] = resolved_path
        
        logger.debug(f"✅ Resolved {path_type.value} -> {resolved_path.path} "
                    f"(from: {resolved_path.resolved_from})")
        
        return resolved_path
    
    def _resolve_from_custom(self, path_type: PathType, custom_path: Optional[str]) -> Optional[ResolvedPath]:
        """Resolve from explicitly provided custom path"""
        if not custom_path:
            return None
        
        return self._create_resolved_path(custom_path, "custom_override")
    
    def _resolve_from_environment_variables(self, path_type: PathType) -> Optional[ResolvedPath]:
        """Resolve from environment variables"""
        
        # Environment variable patterns for each path type
        env_patterns = {
            PathType.UPLOAD_DIRECTORY: [
                'AIVALIDATION_UPLOAD_DIRECTORY',
                'UPLOAD_DIRECTORY',
                'UPLOADS_PATH'
            ],
            PathType.LOG_DIRECTORY: [
                'AIVALIDATION_LOG_DIRECTORY',
                'LOG_DIRECTORY',
                'LOGS_PATH'
            ],
            PathType.DATA_DIRECTORY: [
                'AIVALIDATION_DATA_DIRECTORY', 
                'DATA_DIRECTORY',
                'DATA_PATH'
            ],
            PathType.CONFIG_DIRECTORY: [
                'AIVALIDATION_CONFIG_DIRECTORY',
                'CONFIG_DIRECTORY',
                'CONFIG_PATH'
            ],
            PathType.TEMP_DIRECTORY: [
                'AIVALIDATION_TEMP_DIRECTORY',
                'TEMP_DIRECTORY',
                'TMP',
                'TMPDIR'
            ],
            PathType.MODEL_DIRECTORY: [
                'AIVALIDATION_MODEL_DIRECTORY',
                'MODEL_DIRECTORY',
                'MODELS_PATH'
            ],
            PathType.EXPORT_DIRECTORY: [
                'AIVALIDATION_EXPORT_DIRECTORY',
                'EXPORT_DIRECTORY',
                'EXPORTS_PATH'
            ],
            PathType.CACHE_DIRECTORY: [
                'AIVALIDATION_CACHE_DIRECTORY',
                'CACHE_DIRECTORY',
                'CACHE_PATH'
            ]
        }
        
        patterns = env_patterns.get(path_type, [])
        
        for pattern in patterns:
            env_value = os.getenv(pattern)
            if env_value:
                return self._create_resolved_path(env_value, f"env_var_{pattern}")
        
        return None
    
    def _resolve_from_base_paths(self, path_type: PathType) -> Optional[ResolvedPath]:
        """Resolve from environment-specific base paths"""
        
        env_type = self._env_info.environment_type
        base_paths = self._base_paths.get(env_type, self._base_paths[EnvironmentType.LOCAL])
        
        # Map path types to base path keys
        path_mapping = {
            PathType.UPLOAD_DIRECTORY: 'uploads',
            PathType.LOG_DIRECTORY: 'logs',
            PathType.DATA_DIRECTORY: 'data',
            PathType.CONFIG_DIRECTORY: 'config',
            PathType.TEMP_DIRECTORY: 'temp',
            PathType.MODEL_DIRECTORY: 'models',
            PathType.EXPORT_DIRECTORY: 'exports',
            PathType.CACHE_DIRECTORY: 'cache'
        }
        
        key = path_mapping.get(path_type)
        if key and key in base_paths:
            path = base_paths[key]
            return self._create_resolved_path(path, f"base_path_{env_type.value}")
        
        return None
    
    def _resolve_fallback(self, path_type: PathType) -> ResolvedPath:
        """Final fallback path resolution"""
        
        # Fallback paths based on path type
        fallback_paths = {
            PathType.UPLOAD_DIRECTORY: './uploads',
            PathType.LOG_DIRECTORY: './logs',
            PathType.DATA_DIRECTORY: './data',
            PathType.CONFIG_DIRECTORY: './config',
            PathType.TEMP_DIRECTORY: '/tmp' if os.path.exists('/tmp') else './temp',
            PathType.MODEL_DIRECTORY: './models',
            PathType.EXPORT_DIRECTORY: './exports',
            PathType.CACHE_DIRECTORY: './cache'
        }
        
        fallback_path = fallback_paths.get(path_type, './temp')
        return self._create_resolved_path(fallback_path, "fallback")
    
    def _create_resolved_path(self, path: str, resolved_from: str) -> ResolvedPath:
        """Create ResolvedPath object with full path analysis"""
        
        try:
            # Expand path
            expanded_path = os.path.expanduser(os.path.expandvars(path))
            absolute_path = os.path.abspath(expanded_path)
            
            # Check path properties
            exists = os.path.exists(expanded_path)
            is_readable = os.access(expanded_path, os.R_OK) if exists else False
            is_writable = os.access(expanded_path, os.W_OK) if exists else self._test_write_access(expanded_path)
            parent_exists = os.path.exists(os.path.dirname(expanded_path))
            
            return ResolvedPath(
                path=expanded_path,
                exists=exists,
                is_writable=is_writable,
                is_readable=is_readable,
                absolute_path=absolute_path,
                parent_exists=parent_exists,
                resolved_from=resolved_from
            )
            
        except Exception as e:
            logger.warning(f"Error analyzing path {path}: {e}")
            return ResolvedPath(
                path=path,
                exists=False,
                is_writable=False,
                is_readable=False,
                absolute_path=os.path.abspath(path),
                parent_exists=False,
                resolved_from=f"{resolved_from}_error"
            )
    
    def _test_write_access(self, path: str) -> bool:
        """Test if we can write to a path (or its parent if path doesn't exist)"""
        try:
            # If path exists, test directly
            if os.path.exists(path):
                test_file = os.path.join(path, '.write_test')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                return True
            else:
                # Test parent directory
                parent = os.path.dirname(path)
                if os.path.exists(parent):
                    return os.access(parent, os.W_OK)
                else:
                    # Recursively check parent
                    return self._test_write_access(parent)
        except:
            return False
    
    def resolve_upload_directory(self, custom_path: Optional[str] = None) -> str:
        """Get upload directory path"""
        resolved = self.resolve_path(PathType.UPLOAD_DIRECTORY, custom_path)
        return resolved.path
    
    def resolve_log_directory(self, custom_path: Optional[str] = None) -> str:
        """Get log directory path"""
        resolved = self.resolve_path(PathType.LOG_DIRECTORY, custom_path)
        return resolved.path
    
    def resolve_data_directory(self, custom_path: Optional[str] = None) -> str:
        """Get data directory path"""
        resolved = self.resolve_path(PathType.DATA_DIRECTORY, custom_path)
        return resolved.path
    
    def resolve_config_directory(self, custom_path: Optional[str] = None) -> str:
        """Get config directory path"""
        resolved = self.resolve_path(PathType.CONFIG_DIRECTORY, custom_path)
        return resolved.path
    
    def resolve_temp_directory(self, custom_path: Optional[str] = None) -> str:
        """Get temporary directory path"""
        resolved = self.resolve_path(PathType.TEMP_DIRECTORY, custom_path)
        return resolved.path
    
    def resolve_model_directory(self, custom_path: Optional[str] = None) -> str:
        """Get model directory path"""
        resolved = self.resolve_path(PathType.MODEL_DIRECTORY, custom_path)
        return resolved.path
    
    def resolve_export_directory(self, custom_path: Optional[str] = None) -> str:
        """Get export directory path"""
        resolved = self.resolve_path(PathType.EXPORT_DIRECTORY, custom_path)
        return resolved.path
    
    def resolve_cache_directory(self, custom_path: Optional[str] = None) -> str:
        """Get cache directory path"""
        resolved = self.resolve_path(PathType.CACHE_DIRECTORY, custom_path)
        return resolved.path
    
    def ensure_directory_structure(self, directories: Optional[List[PathType]] = None) -> Dict[str, ResolvedPath]:
        """Ensure all required directories exist"""
        
        if directories is None:
            directories = list(PathType)
        
        results = {}
        
        for path_type in directories:
            try:
                resolved = self.resolve_path(path_type, ensure_exists=True)
                results[path_type.value] = resolved
                
                if resolved.exists:
                    logger.debug(f"✅ Directory ready: {path_type.value} -> {resolved.path}")
                else:
                    logger.warning(f"⚠️ Directory not accessible: {path_type.value} -> {resolved.path}")
                    
            except Exception as e:
                logger.error(f"❌ Failed to ensure directory {path_type.value}: {e}")
                
        return results
    
    def validate_paths(self) -> Dict[str, Any]:
        """Validate all resolved paths and return status"""
        
        validation_results = {
            'environment_type': self._env_info.environment_type.value,
            'service_mode': self._env_info.service_mode.value,
            'paths': {},
            'warnings': [],
            'errors': []
        }
        
        for path_type in PathType:
            try:
                resolved = self.resolve_path(path_type, ensure_exists=False)
                validation_results['paths'][path_type.value] = {
                    'path': resolved.path,
                    'exists': resolved.exists,
                    'is_writable': resolved.is_writable,
                    'is_readable': resolved.is_readable,
                    'resolved_from': resolved.resolved_from
                }
                
                # Collect warnings and errors
                if not resolved.exists and path_type in [PathType.UPLOAD_DIRECTORY, PathType.LOG_DIRECTORY]:
                    validation_results['warnings'].append(
                        f"Critical directory does not exist: {path_type.value} -> {resolved.path}"
                    )
                
                if not resolved.is_writable and path_type in [
                    PathType.UPLOAD_DIRECTORY, PathType.LOG_DIRECTORY, PathType.TEMP_DIRECTORY
                ]:
                    validation_results['errors'].append(
                        f"Directory not writable: {path_type.value} -> {resolved.path}"
                    )
                    
            except Exception as e:
                validation_results['errors'].append(
                    f"Failed to validate {path_type.value}: {e}"
                )
        
        return validation_results
    
    def get_path_summary(self) -> Dict[str, str]:
        """Get a simple summary of all resolved paths"""
        summary = {}
        
        for path_type in PathType:
            try:
                resolved = self.resolve_path(path_type, ensure_exists=False)
                summary[path_type.value] = resolved.path
            except Exception as e:
                summary[path_type.value] = f"ERROR: {e}"
        
        return summary
    
    def clear_cache(self):
        """Clear the path resolution cache"""
        self._path_cache.clear()
        logger.info("Path resolver cache cleared")

# Global path resolver instance
path_resolver = PathResolver()

# Convenience functions
def resolve_upload_directory(custom_path: Optional[str] = None) -> str:
    """Get upload directory path"""
    return path_resolver.resolve_upload_directory(custom_path)

def resolve_log_directory(custom_path: Optional[str] = None) -> str:
    """Get log directory path"""
    return path_resolver.resolve_log_directory(custom_path)

def resolve_data_directory(custom_path: Optional[str] = None) -> str:
    """Get data directory path"""
    return path_resolver.resolve_data_directory(custom_path)

def ensure_directory_structure() -> Dict[str, ResolvedPath]:
    """Ensure all required directories exist"""
    return path_resolver.ensure_directory_structure()

def get_path_summary() -> Dict[str, str]:
    """Get summary of all resolved paths"""
    return path_resolver.get_path_summary()

if __name__ == "__main__":
    # Test the path resolver
    import json
    
    resolver = PathResolver()
    
    print("Path Summary:")
    summary = resolver.get_path_summary()
    print(json.dumps(summary, indent=2))
    
    print("\nPath Validation:")
    validation = resolver.validate_paths()
    print(json.dumps(validation, indent=2, default=str))
    
    print("\nEnsuring directory structure...")
    results = resolver.ensure_directory_structure()
    for path_type, resolved_path in results.items():
        print(f"{path_type}: {resolved_path.path} (exists: {resolved_path.exists})")