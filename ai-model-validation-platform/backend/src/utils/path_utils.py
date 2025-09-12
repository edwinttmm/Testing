"""
Path Utilities for Robust File Path Management
============================================

Provides centralized path management functions for the AI Model Validation Platform.
Handles path resolution, validation, normalization, and backwards compatibility.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Union, Tuple
from urllib.parse import urlparse
import tempfile
import shutil

logger = logging.getLogger(__name__)


class PathManager:
    """Centralized path management with robust resolution and validation."""
    
    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        """Initialize path manager with optional base directory."""
        if base_dir is None:
            # Use backend directory as default base
            self.base_dir = Path(__file__).parent.parent.parent
        else:
            self.base_dir = Path(base_dir)
        
        self.base_dir = self.base_dir.resolve()  # Always use absolute paths
        
        # Standard directories
        self.uploads_dir = self.base_dir / "uploads"
        self.screenshots_dir = self.base_dir / "screenshots"
        self.data_dir = self.base_dir / "data"
        self.logs_dir = self.base_dir / "logs"
        
        # Ensure directories exist
        self.ensure_directories()
        
        logger.info(f"PathManager initialized with base directory: {self.base_dir}")
    
    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        directories = [
            self.uploads_dir,
            self.screenshots_dir,
            self.data_dir,
            self.logs_dir
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensured directory exists: {directory}")
            except Exception as e:
                logger.error(f"Failed to create directory {directory}: {e}")
                raise
    
    def resolve_path(self, path: Union[str, Path], base_dir: Optional[Path] = None) -> Path:
        """
        Resolve a path to absolute path with robust handling.
        
        Args:
            path: Input path (can be relative or absolute)
            base_dir: Optional base directory for relative paths
            
        Returns:
            Absolute Path object
            
        Raises:
            ValueError: If path is invalid or unsafe
        """
        if not path:
            raise ValueError("Path cannot be empty or None")
        
        path_obj = Path(path)
        
        # If already absolute, validate and return
        if path_obj.is_absolute():
            resolved_path = path_obj.resolve()
            self._validate_path_safety(resolved_path)
            return resolved_path
        
        # Handle relative paths
        if base_dir is None:
            base_dir = self.base_dir
        else:
            base_dir = Path(base_dir).resolve()
        
        resolved_path = (base_dir / path_obj).resolve()
        self._validate_path_safety(resolved_path)
        
        return resolved_path
    
    def resolve_upload_path(self, filename: str) -> Path:
        """Resolve path for uploaded files with validation."""
        if not filename:
            raise ValueError("Filename cannot be empty")
        
        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)
        
        # Resolve to uploads directory
        file_path = self.uploads_dir / safe_filename
        
        logger.debug(f"Resolved upload path: {filename} -> {file_path}")
        return file_path
    
    def resolve_screenshot_path(self, filename: str) -> Path:
        """Resolve path for screenshot files with validation."""
        if not filename:
            raise ValueError("Filename cannot be empty")
        
        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)
        
        # Resolve to screenshots directory
        file_path = self.screenshots_dir / safe_filename
        
        logger.debug(f"Resolved screenshot path: {filename} -> {file_path}")
        return file_path
    
    def get_relative_path(self, absolute_path: Union[str, Path]) -> str:
        """
        Get relative path from absolute path for database storage.
        Maintains backwards compatibility.
        """
        try:
            abs_path = Path(absolute_path).resolve()
            rel_path = abs_path.relative_to(self.base_dir)
            return str(rel_path)
        except (ValueError, AttributeError):
            # If can't make relative, return as-is for backwards compatibility
            logger.warning(f"Could not make path relative: {absolute_path}")
            return str(absolute_path)
    
    def migrate_legacy_path(self, legacy_path: str) -> Path:
        """
        Migrate legacy relative paths to absolute paths.
        Handles backwards compatibility with existing data.
        """
        if not legacy_path:
            raise ValueError("Legacy path cannot be empty")
        
        legacy_path_obj = Path(legacy_path)
        
        # If already absolute and exists, return as-is
        if legacy_path_obj.is_absolute():
            if legacy_path_obj.exists():
                return legacy_path_obj.resolve()
            else:
                logger.warning(f"Legacy absolute path does not exist: {legacy_path}")
                return legacy_path_obj.resolve()
        
        # Try common legacy patterns
        migration_candidates = [
            self.base_dir / legacy_path,  # Direct relative to base
            self.uploads_dir / legacy_path,  # In uploads
            self.screenshots_dir / legacy_path,  # In screenshots
            Path.cwd() / legacy_path,  # Relative to current working directory
        ]
        
        # Try each candidate
        for candidate in migration_candidates:
            try:
                resolved = candidate.resolve()
                if resolved.exists():
                    logger.info(f"Successfully migrated legacy path: {legacy_path} -> {resolved}")
                    return resolved
            except Exception as e:
                logger.debug(f"Migration candidate failed {candidate}: {e}")
                continue
        
        # If no existing file found, use base_dir as default
        resolved = (self.base_dir / legacy_path).resolve()
        logger.warning(f"Legacy path file not found, using default: {legacy_path} -> {resolved}")
        return resolved
    
    def ensure_path_exists(self, path: Union[str, Path]) -> Path:
        """
        Ensure a path's parent directory exists, creating if necessary.
        """
        path_obj = Path(path)
        if not path_obj.is_absolute():
            path_obj = self.resolve_path(path_obj)
        
        # Create parent directory if it doesn't exist
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        return path_obj
    
    def is_safe_path(self, path: Union[str, Path]) -> bool:
        """Check if a path is safe (no path traversal attacks)."""
        try:
            self._validate_path_safety(Path(path))
            return True
        except ValueError:
            return False
    
    def copy_to_managed_location(self, source_path: Union[str, Path], 
                                target_dir: str = "uploads") -> Tuple[Path, Path]:
        """
        Copy a file to a managed location and return both old and new paths.
        
        Args:
            source_path: Source file path
            target_dir: Target directory name (uploads, screenshots, data)
            
        Returns:
            Tuple of (old_path, new_path)
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file does not exist: {source}")
        
        # Determine target directory
        if target_dir == "uploads":
            target_base = self.uploads_dir
        elif target_dir == "screenshots":
            target_base = self.screenshots_dir
        elif target_dir == "data":
            target_base = self.data_dir
        else:
            target_base = self.base_dir / target_dir
        
        # Ensure target directory exists
        target_base.mkdir(parents=True, exist_ok=True)
        
        # Create target path with sanitized filename
        safe_filename = self._sanitize_filename(source.name)
        target_path = target_base / safe_filename
        
        # Handle filename conflicts
        counter = 1
        original_target = target_path
        while target_path.exists():
            stem = original_target.stem
            suffix = original_target.suffix
            target_path = original_target.parent / f"{stem}_{counter}{suffix}"
            counter += 1
        
        # Copy file
        try:
            shutil.copy2(source, target_path)
            logger.info(f"Copied file: {source} -> {target_path}")
            return source.resolve(), target_path.resolve()
        except Exception as e:
            logger.error(f"Failed to copy file {source} to {target_path}: {e}")
            raise
    
    def cleanup_temp_files(self, temp_dir: Optional[Union[str, Path]] = None) -> int:
        """Clean up temporary files. Returns number of files cleaned."""
        if temp_dir is None:
            temp_dir = tempfile.gettempdir()
        
        temp_path = Path(temp_dir)
        cleaned = 0
        
        try:
            # Clean up old temporary files (older than 1 hour)
            import time
            current_time = time.time()
            
            for file_path in temp_path.glob("ai_validation_*"):
                try:
                    if (current_time - file_path.stat().st_mtime) > 3600:  # 1 hour
                        if file_path.is_file():
                            file_path.unlink()
                        elif file_path.is_dir():
                            shutil.rmtree(file_path)
                        cleaned += 1
                except Exception as e:
                    logger.debug(f"Could not clean temp file {file_path}: {e}")
            
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} temporary files")
                
        except Exception as e:
            logger.error(f"Error during temp file cleanup: {e}")
        
        return cleaned
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent security issues."""
        if not filename:
            raise ValueError("Filename cannot be empty")
        
        # Remove directory separators and dangerous characters
        dangerous_chars = '<>:"|?*\\/\0'
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # Remove leading/trailing whitespace and dots
        filename = filename.strip('. ')
        
        # Ensure filename is not empty after sanitization
        if not filename:
            filename = "unnamed_file"
        
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255-len(ext)] + ext
        
        return filename
    
    def _validate_path_safety(self, path: Path) -> None:
        """
        Validate that a path is safe (no path traversal).
        
        Raises:
            ValueError: If path is unsafe
        """
        try:
            resolved = path.resolve()
            
            # Check if path tries to escape base directory
            try:
                resolved.relative_to(self.base_dir)
            except ValueError:
                # Path is outside base directory - check if it's in system allowed locations
                allowed_prefixes = [
                    Path("/tmp"),
                    Path(tempfile.gettempdir()),
                    Path.home() / "Downloads",  # Common download location
                ]
                
                is_allowed = False
                for prefix in allowed_prefixes:
                    try:
                        resolved.relative_to(prefix.resolve())
                        is_allowed = True
                        break
                    except ValueError:
                        continue
                
                if not is_allowed:
                    raise ValueError(f"Path outside allowed directories: {resolved}")
            
            # Check for dangerous path components
            dangerous_components = ['..', '.', '']
            for part in resolved.parts:
                if part in dangerous_components and part != resolved.parts[0]:
                    logger.warning(f"Potentially dangerous path component detected: {part}")
            
        except Exception as e:
            logger.error(f"Path validation failed for {path}: {e}")
            raise ValueError(f"Invalid or unsafe path: {path}")


# Global path manager instance
_path_manager = None

def get_path_manager() -> PathManager:
    """Get global path manager instance."""
    global _path_manager
    if _path_manager is None:
        _path_manager = PathManager()
    return _path_manager


# Convenience functions
def resolve_path(path: Union[str, Path], base_dir: Optional[Path] = None) -> Path:
    """Resolve path using global path manager."""
    return get_path_manager().resolve_path(path, base_dir)


def resolve_upload_path(filename: str) -> Path:
    """Resolve upload path using global path manager."""
    return get_path_manager().resolve_upload_path(filename)


def resolve_screenshot_path(filename: str) -> Path:
    """Resolve screenshot path using global path manager."""
    return get_path_manager().resolve_screenshot_path(filename)


def migrate_legacy_path(legacy_path: str) -> Path:
    """Migrate legacy path using global path manager."""
    return get_path_manager().migrate_legacy_path(legacy_path)


def ensure_path_exists(path: Union[str, Path]) -> Path:
    """Ensure path exists using global path manager."""
    return get_path_manager().ensure_path_exists(path)


def is_safe_path(path: Union[str, Path]) -> bool:
    """Check if path is safe using global path manager."""
    return get_path_manager().is_safe_path(path)


def get_relative_path(absolute_path: Union[str, Path]) -> str:
    """Get relative path using global path manager."""
    return get_path_manager().get_relative_path(absolute_path)