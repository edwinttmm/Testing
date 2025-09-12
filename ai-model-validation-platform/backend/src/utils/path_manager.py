"""
Path Management Utility System
Provides deployment-environment independent path resolution and management.
Designed for containerized deployments and cross-platform compatibility.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union, List
from urllib.parse import urlparse
import uuid
from enum import Enum
import json
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class PathType(Enum):
    """Path type enumeration for path resolution context"""
    UPLOAD = "upload"
    SCREENSHOT = "screenshot"  
    VIDEO = "video"
    GROUND_TRUTH = "ground_truth"
    REPORT = "report"
    TEMP = "temp"
    LOG = "log"
    STATIC = "static"


class DeploymentContext(Enum):
    """Deployment context enumeration"""
    DEVELOPMENT = "development"
    CONTAINER = "container"
    PRODUCTION = "production"
    TEST = "test"


@dataclass
class PathResolutionResult:
    """Result of path resolution operation"""
    resolved_path: Path
    absolute_path: str
    relative_path: str
    exists: bool
    is_writable: bool
    context: DeploymentContext
    errors: List[str]
    metadata: Dict[str, Any]


class PathResolver(ABC):
    """Abstract base class for path resolution strategies"""
    
    @abstractmethod
    def resolve_path(self, path: Union[str, Path], path_type: PathType) -> PathResolutionResult:
        """Resolve path based on deployment context"""
        pass
    
    @abstractmethod
    def get_base_directory(self, path_type: PathType) -> Path:
        """Get base directory for given path type"""
        pass


class ContainerPathResolver(PathResolver):
    """Path resolver for containerized deployments"""
    
    def __init__(self, container_root: str = "/app"):
        self.container_root = Path(container_root)
        self.volume_mappings = {
            PathType.UPLOAD: "/app/uploads",
            PathType.SCREENSHOT: "/app/screenshots", 
            PathType.VIDEO: "/app/videos",
            PathType.GROUND_TRUTH: "/app/ground_truth",
            PathType.REPORT: "/app/reports",
            PathType.TEMP: "/tmp/ai-validation",
            PathType.LOG: "/app/logs",
            PathType.STATIC: "/app/static"
        }
    
    def resolve_path(self, path: Union[str, Path], path_type: PathType) -> PathResolutionResult:
        """Resolve path for container environment"""
        errors = []
        base_dir = self.get_base_directory(path_type)
        
        try:
            # Convert to Path object
            if isinstance(path, str):
                path_obj = Path(path)
            else:
                path_obj = path
            
            # If already absolute and within container, use as-is
            if path_obj.is_absolute():
                if str(path_obj).startswith(str(self.container_root)):
                    resolved = path_obj
                else:
                    # External absolute path - move to container structure
                    resolved = base_dir / path_obj.name
                    errors.append(f"External path moved to container: {path} -> {resolved}")
            else:
                # Relative path - resolve against base directory
                resolved = base_dir / path_obj
            
            # Ensure parent directories exist
            resolved.parent.mkdir(parents=True, exist_ok=True)
            
            # Calculate relative path from container root
            try:
                relative = resolved.relative_to(self.container_root)
            except ValueError:
                relative = resolved.name
                errors.append(f"Path outside container root: {resolved}")
            
            return PathResolutionResult(
                resolved_path=resolved,
                absolute_path=str(resolved),
                relative_path=str(relative),
                exists=resolved.exists(),
                is_writable=self._check_writable(resolved),
                context=DeploymentContext.CONTAINER,
                errors=errors,
                metadata={
                    "container_root": str(self.container_root),
                    "base_directory": str(base_dir),
                    "path_type": path_type.value
                }
            )
            
        except Exception as e:
            errors.append(f"Path resolution failed: {str(e)}")
            # Fallback to safe path
            fallback = base_dir / f"fallback_{uuid.uuid4().hex[:8]}"
            return PathResolutionResult(
                resolved_path=fallback,
                absolute_path=str(fallback),
                relative_path=str(fallback.name),
                exists=False,
                is_writable=False,
                context=DeploymentContext.CONTAINER,
                errors=errors,
                metadata={"fallback": True}
            )
    
    def get_base_directory(self, path_type: PathType) -> Path:
        """Get base directory for path type in container"""
        return Path(self.volume_mappings.get(path_type, "/app/data"))
    
    def _check_writable(self, path: Path) -> bool:
        """Check if path is writable"""
        try:
            if path.exists():
                return os.access(path, os.W_OK)
            else:
                # Check parent directory
                return os.access(path.parent, os.W_OK)
        except Exception:
            return False


class DevelopmentPathResolver(PathResolver):
    """Path resolver for development environment"""
    
    def __init__(self, project_root: Optional[str] = None):
        if project_root:
            self.project_root = Path(project_root)
        else:
            # Auto-detect project root
            self.project_root = self._find_project_root()
        
        self.data_directories = {
            PathType.UPLOAD: self.project_root / "uploads",
            PathType.SCREENSHOT: self.project_root / "screenshots",
            PathType.VIDEO: self.project_root / "videos", 
            PathType.GROUND_TRUTH: self.project_root / "ground_truth",
            PathType.REPORT: self.project_root / "reports",
            PathType.TEMP: Path.home() / ".ai-validation" / "temp",
            PathType.LOG: self.project_root / "logs",
            PathType.STATIC: self.project_root / "static"
        }
    
    def resolve_path(self, path: Union[str, Path], path_type: PathType) -> PathResolutionResult:
        """Resolve path for development environment"""
        errors = []
        base_dir = self.get_base_directory(path_type)
        
        try:
            if isinstance(path, str):
                path_obj = Path(path)
            else:
                path_obj = path
            
            # Handle different path scenarios
            if path_obj.is_absolute():
                resolved = path_obj
            else:
                resolved = base_dir / path_obj
            
            # Normalize path
            resolved = resolved.resolve()
            
            # Ensure directory exists
            resolved.parent.mkdir(parents=True, exist_ok=True)
            
            # Calculate relative path from project root
            try:
                relative = resolved.relative_to(self.project_root)
            except ValueError:
                relative = resolved.name
                errors.append(f"Path outside project root: {resolved}")
            
            return PathResolutionResult(
                resolved_path=resolved,
                absolute_path=str(resolved),
                relative_path=str(relative),
                exists=resolved.exists(),
                is_writable=self._check_writable(resolved),
                context=DeploymentContext.DEVELOPMENT,
                errors=errors,
                metadata={
                    "project_root": str(self.project_root),
                    "base_directory": str(base_dir),
                    "path_type": path_type.value
                }
            )
            
        except Exception as e:
            errors.append(f"Path resolution failed: {str(e)}")
            fallback = base_dir / f"fallback_{uuid.uuid4().hex[:8]}"
            return PathResolutionResult(
                resolved_path=fallback,
                absolute_path=str(fallback),
                relative_path=str(fallback.name),
                exists=False,
                is_writable=False,
                context=DeploymentContext.DEVELOPMENT,
                errors=errors,
                metadata={"fallback": True}
            )
    
    def get_base_directory(self, path_type: PathType) -> Path:
        """Get base directory for path type in development"""
        return self.data_directories.get(path_type, self.project_root / "data")
    
    def _find_project_root(self) -> Path:
        """Find project root by looking for common markers"""
        current = Path.cwd()
        markers = ['.git', 'pyproject.toml', 'requirements.txt', 'package.json']
        
        while current != current.parent:
            if any((current / marker).exists() for marker in markers):
                return current
            current = current.parent
        
        # Fallback to current working directory
        return Path.cwd()
    
    def _check_writable(self, path: Path) -> bool:
        """Check if path is writable"""
        try:
            if path.exists():
                return os.access(path, os.W_OK)
            else:
                return os.access(path.parent, os.W_OK)
        except Exception:
            return False


class ProductionPathResolver(PathResolver):
    """Path resolver for production environment"""
    
    def __init__(self):
        self.production_root = Path("/var/lib/ai-validation")
        self.data_directories = {
            PathType.UPLOAD: Path("/var/lib/ai-validation/uploads"),
            PathType.SCREENSHOT: Path("/var/lib/ai-validation/screenshots"),
            PathType.VIDEO: Path("/var/lib/ai-validation/videos"),
            PathType.GROUND_TRUTH: Path("/var/lib/ai-validation/ground_truth"),
            PathType.REPORT: Path("/var/lib/ai-validation/reports"), 
            PathType.TEMP: Path("/tmp/ai-validation"),
            PathType.LOG: Path("/var/log/ai-validation"),
            PathType.STATIC: Path("/var/lib/ai-validation/static")
        }
    
    def resolve_path(self, path: Union[str, Path], path_type: PathType) -> PathResolutionResult:
        """Resolve path for production environment"""
        errors = []
        base_dir = self.get_base_directory(path_type)
        
        try:
            if isinstance(path, str):
                path_obj = Path(path)
            else:
                path_obj = path
            
            # Security: Only allow paths within production directories
            if path_obj.is_absolute():
                # Check if path is within allowed production directories
                allowed_roots = [self.production_root, Path("/tmp/ai-validation")]
                if not any(str(path_obj).startswith(str(root)) for root in allowed_roots):
                    errors.append(f"Path outside allowed production directories: {path_obj}")
                    resolved = base_dir / path_obj.name
                else:
                    resolved = path_obj
            else:
                resolved = base_dir / path_obj
            
            # Normalize and secure path
            resolved = resolved.resolve()
            
            # Double-check security after resolution
            if not any(str(resolved).startswith(str(root)) for root in [self.production_root, Path("/tmp/ai-validation")]):
                errors.append(f"Resolved path outside production boundaries: {resolved}")
                resolved = base_dir / f"secure_{uuid.uuid4().hex[:8]}"
            
            # Ensure directory exists with proper permissions
            resolved.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            
            # Calculate relative path
            try:
                relative = resolved.relative_to(self.production_root)
            except ValueError:
                relative = resolved.name
            
            return PathResolutionResult(
                resolved_path=resolved,
                absolute_path=str(resolved),
                relative_path=str(relative),
                exists=resolved.exists(),
                is_writable=self._check_writable(resolved),
                context=DeploymentContext.PRODUCTION,
                errors=errors,
                metadata={
                    "production_root": str(self.production_root),
                    "base_directory": str(base_dir),
                    "path_type": path_type.value,
                    "security_validated": True
                }
            )
            
        except Exception as e:
            errors.append(f"Production path resolution failed: {str(e)}")
            fallback = base_dir / f"secure_{uuid.uuid4().hex[:8]}"
            return PathResolutionResult(
                resolved_path=fallback,
                absolute_path=str(fallback),
                relative_path=str(fallback.name),
                exists=False,
                is_writable=False,
                context=DeploymentContext.PRODUCTION,
                errors=errors,
                metadata={"fallback": True, "security_violation": True}
            )
    
    def get_base_directory(self, path_type: PathType) -> Path:
        """Get base directory for path type in production"""
        return self.data_directories.get(path_type, self.production_root / "data")
    
    def _check_writable(self, path: Path) -> bool:
        """Check if path is writable with production security"""
        try:
            if path.exists():
                return os.access(path, os.W_OK)
            else:
                return os.access(path.parent, os.W_OK)
        except Exception:
            return False


class PathManager:
    """Central path management system with automatic context detection"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.context = self._detect_deployment_context()
        self.resolver = self._create_resolver()
        
        logger.info(f"PathManager initialized for {self.context.value} context")
    
    def resolve_path(self, path: Union[str, Path], path_type: PathType) -> PathResolutionResult:
        """Resolve path using appropriate resolver for current context"""
        result = self.resolver.resolve_path(path, path_type)
        
        # Log any errors or warnings
        if result.errors:
            for error in result.errors:
                logger.warning(f"Path resolution: {error}")
        
        return result
    
    def get_absolute_path(self, path: Union[str, Path], path_type: PathType) -> str:
        """Get absolute path string for database storage"""
        result = self.resolve_path(path, path_type)
        return result.absolute_path
    
    def get_relative_path(self, path: Union[str, Path], path_type: PathType) -> str:
        """Get relative path string for portability"""
        result = self.resolve_path(path, path_type)
        return result.relative_path
    
    def ensure_directory_exists(self, path_type: PathType) -> Path:
        """Ensure base directory exists for given path type"""
        base_dir = self.resolver.get_base_directory(path_type)
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir
    
    def validate_path_access(self, path: Union[str, Path], path_type: PathType) -> Dict[str, Any]:
        """Validate path access and return status information"""
        result = self.resolve_path(path, path_type)
        
        return {
            "valid": len(result.errors) == 0,
            "exists": result.exists,
            "writable": result.is_writable,
            "absolute_path": result.absolute_path,
            "errors": result.errors,
            "context": result.context.value
        }
    
    def migrate_relative_paths(self, old_paths: List[str], path_type: PathType) -> Dict[str, str]:
        """Migrate relative paths to new absolute paths"""
        migrations = {}
        
        for old_path in old_paths:
            try:
                result = self.resolve_path(old_path, path_type)
                migrations[old_path] = result.absolute_path
                logger.info(f"Migrated path: {old_path} -> {result.absolute_path}")
            except Exception as e:
                logger.error(f"Failed to migrate path {old_path}: {str(e)}")
                migrations[old_path] = None
        
        return migrations
    
    def _detect_deployment_context(self) -> DeploymentContext:
        """Detect current deployment context"""
        # Check for container environment
        if (os.path.exists("/.dockerenv") or 
            os.getenv("DOCKER_CONTAINER") or 
            os.getenv("KUBERNETES_SERVICE_HOST")):
            return DeploymentContext.CONTAINER
        
        # Check for production indicators
        if (os.getenv("ENVIRONMENT") == "production" or
            os.getenv("APP_ENV") == "production" or
            os.path.exists("/etc/production.marker")):
            return DeploymentContext.PRODUCTION
        
        # Check for test environment
        if (os.getenv("ENVIRONMENT") == "test" or
            "pytest" in os.getenv("_", "")):
            return DeploymentContext.TEST
        
        # Default to development
        return DeploymentContext.DEVELOPMENT
    
    def _create_resolver(self) -> PathResolver:
        """Create appropriate path resolver for current context"""
        if self.context == DeploymentContext.CONTAINER:
            container_root = self.config.get("container_root", "/app")
            return ContainerPathResolver(container_root)
        elif self.context == DeploymentContext.PRODUCTION:
            return ProductionPathResolver()
        else:  # Development or Test
            project_root = self.config.get("project_root")
            return DevelopmentPathResolver(project_root)


# Global path manager instance
_path_manager = None


def get_path_manager(config: Optional[Dict[str, Any]] = None) -> PathManager:
    """Get global path manager instance"""
    global _path_manager
    if _path_manager is None or config is not None:
        _path_manager = PathManager(config)
    return _path_manager


def resolve_path(path: Union[str, Path], path_type: PathType) -> PathResolutionResult:
    """Convenience function for path resolution"""
    return get_path_manager().resolve_path(path, path_type)


def get_absolute_path(path: Union[str, Path], path_type: PathType) -> str:
    """Convenience function to get absolute path"""
    return get_path_manager().get_absolute_path(path, path_type)


def ensure_directory(path_type: PathType) -> Path:
    """Convenience function to ensure directory exists"""
    return get_path_manager().ensure_directory_exists(path_type)