"""
Comprehensive Error Handling for File Access Issues
Provides robust error handling patterns for path and file operations.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Callable
from enum import Enum
from dataclasses import dataclass
import time
import functools
import traceback
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class FileAccessErrorType(Enum):
    """Types of file access errors"""
    PATH_NOT_FOUND = "path_not_found"
    PERMISSION_DENIED = "permission_denied"
    DISK_FULL = "disk_full"
    NETWORK_ERROR = "network_error"
    CORRUPTED_FILE = "corrupted_file"
    PATH_TOO_LONG = "path_too_long"
    INVALID_CHARACTER = "invalid_character"
    SYMLINK_LOOP = "symlink_loop"
    DEVICE_ERROR = "device_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class FileAccessError:
    """Structured file access error information"""
    error_type: FileAccessErrorType
    original_path: str
    resolved_path: Optional[str]
    error_message: str
    system_error_code: Optional[int]
    timestamp: float
    recovery_suggestions: List[str]
    metadata: Dict[str, Any]


class FileAccessRecoveryStrategy:
    """Base class for file access recovery strategies"""
    
    def can_recover(self, error: FileAccessError) -> bool:
        """Check if this strategy can recover from the given error"""
        return False
    
    def attempt_recovery(self, error: FileAccessError) -> Optional[str]:
        """Attempt to recover from the error, return new path if successful"""
        return None


class PathNotFoundRecovery(FileAccessRecoveryStrategy):
    """Recovery strategy for path not found errors"""
    
    def __init__(self, fallback_directories: List[str]):
        self.fallback_directories = fallback_directories
    
    def can_recover(self, error: FileAccessError) -> bool:
        return error.error_type == FileAccessErrorType.PATH_NOT_FOUND
    
    def attempt_recovery(self, error: FileAccessError) -> Optional[str]:
        """Try to find the file in fallback directories"""
        if not error.original_path:
            return None
        
        filename = Path(error.original_path).name
        
        for fallback_dir in self.fallback_directories:
            fallback_path = Path(fallback_dir) / filename
            if fallback_path.exists():
                logger.info(f"File recovered in fallback directory: {fallback_path}")
                return str(fallback_path)
        
        # Try to create parent directory if it doesn't exist
        original_path = Path(error.original_path)
        try:
            original_path.parent.mkdir(parents=True, exist_ok=True)
            if original_path.parent.exists():
                logger.info(f"Created missing parent directory: {original_path.parent}")
                return error.original_path
        except Exception as e:
            logger.warning(f"Failed to create parent directory: {str(e)}")
        
        return None


class PermissionDeniedRecovery(FileAccessRecoveryStrategy):
    """Recovery strategy for permission denied errors"""
    
    def can_recover(self, error: FileAccessError) -> bool:
        return error.error_type == FileAccessErrorType.PERMISSION_DENIED
    
    def attempt_recovery(self, error: FileAccessError) -> Optional[str]:
        """Try to fix permissions or suggest alternative path"""
        if not error.resolved_path:
            return None
        
        path_obj = Path(error.resolved_path)
        
        try:
            # Try to fix permissions
            if path_obj.exists():
                path_obj.chmod(0o644)  # Basic read/write permissions
                if os.access(path_obj, os.R_OK | os.W_OK):
                    logger.info(f"Fixed permissions for: {path_obj}")
                    return str(path_obj)
            
            # Try parent directory permissions
            if path_obj.parent.exists():
                path_obj.parent.chmod(0o755)
                logger.info(f"Fixed parent directory permissions: {path_obj.parent}")
                return error.resolved_path
                
        except Exception as e:
            logger.warning(f"Failed to fix permissions: {str(e)}")
        
        return None


class DiskFullRecovery(FileAccessRecoveryStrategy):
    """Recovery strategy for disk full errors"""
    
    def __init__(self, cleanup_functions: List[Callable[[], int]]):
        self.cleanup_functions = cleanup_functions
    
    def can_recover(self, error: FileAccessError) -> bool:
        return error.error_type == FileAccessErrorType.DISK_FULL
    
    def attempt_recovery(self, error: FileAccessError) -> Optional[str]:
        """Try to free up disk space"""
        freed_bytes = 0
        
        for cleanup_func in self.cleanup_functions:
            try:
                freed = cleanup_func()
                freed_bytes += freed
                logger.info(f"Freed {freed} bytes using cleanup function")
                
                # Check if we have enough space now
                if freed_bytes > 100 * 1024 * 1024:  # 100MB threshold
                    return error.resolved_path or error.original_path
                    
            except Exception as e:
                logger.warning(f"Cleanup function failed: {str(e)}")
        
        return None


class FileAccessErrorHandler:
    """Comprehensive file access error handler with recovery strategies"""
    
    def __init__(self):
        self.recovery_strategies: List[FileAccessRecoveryStrategy] = []
        self.error_history: List[FileAccessError] = []
        self.max_history = 1000
        
        # Add default recovery strategies
        self._setup_default_strategies()
    
    def _setup_default_strategies(self):
        """Setup default recovery strategies"""
        # Path not found recovery
        fallback_dirs = [
            "/tmp",
            "/var/tmp", 
            str(Path.home() / "tmp"),
            str(Path.cwd() / "fallback")
        ]
        self.recovery_strategies.append(PathNotFoundRecovery(fallback_dirs))
        
        # Permission denied recovery
        self.recovery_strategies.append(PermissionDeniedRecovery())
        
        # Disk full recovery
        cleanup_functions = [
            self._cleanup_temp_files,
            self._cleanup_old_logs,
            self._cleanup_old_screenshots
        ]
        self.recovery_strategies.append(DiskFullRecovery(cleanup_functions))
    
    def add_recovery_strategy(self, strategy: FileAccessRecoveryStrategy):
        """Add a custom recovery strategy"""
        self.recovery_strategies.append(strategy)
    
    def handle_file_access_error(self, 
                                original_exception: Exception,
                                original_path: str,
                                resolved_path: Optional[str] = None,
                                context: Dict[str, Any] = None) -> FileAccessError:
        """Handle file access error and attempt recovery"""
        
        # Classify the error
        error_type = self._classify_error(original_exception)
        
        # Create error object
        error = FileAccessError(
            error_type=error_type,
            original_path=original_path,
            resolved_path=resolved_path,
            error_message=str(original_exception),
            system_error_code=getattr(original_exception, 'errno', None),
            timestamp=time.time(),
            recovery_suggestions=[],
            metadata=context or {}
        )
        
        # Add to history
        self.error_history.append(error)
        if len(self.error_history) > self.max_history:
            self.error_history.pop(0)
        
        # Attempt recovery
        recovered_path = self._attempt_recovery(error)
        if recovered_path:
            error.recovery_suggestions.append(f"Recovered using path: {recovered_path}")
            error.metadata['recovered_path'] = recovered_path
            logger.info(f"File access error recovered: {original_path} -> {recovered_path}")
        else:
            error.recovery_suggestions = self._generate_recovery_suggestions(error)
        
        return error
    
    def _classify_error(self, exception: Exception) -> FileAccessErrorType:
        """Classify exception into error type"""
        if isinstance(exception, FileNotFoundError):
            return FileAccessErrorType.PATH_NOT_FOUND
        elif isinstance(exception, PermissionError):
            return FileAccessErrorType.PERMISSION_DENIED
        elif isinstance(exception, OSError):
            if hasattr(exception, 'errno'):
                if exception.errno == 28:  # ENOSPC
                    return FileAccessErrorType.DISK_FULL
                elif exception.errno == 40:  # ELOOP
                    return FileAccessErrorType.SYMLINK_LOOP
                elif exception.errno == 36:  # ENAMETOOLONG
                    return FileAccessErrorType.PATH_TOO_LONG
        elif "timeout" in str(exception).lower():
            return FileAccessErrorType.TIMEOUT
        elif "network" in str(exception).lower():
            return FileAccessErrorType.NETWORK_ERROR
        elif "corrupt" in str(exception).lower():
            return FileAccessErrorType.CORRUPTED_FILE
        
        return FileAccessErrorType.UNKNOWN
    
    def _attempt_recovery(self, error: FileAccessError) -> Optional[str]:
        """Attempt recovery using available strategies"""
        for strategy in self.recovery_strategies:
            if strategy.can_recover(error):
                try:
                    recovered_path = strategy.attempt_recovery(error)
                    if recovered_path:
                        return recovered_path
                except Exception as e:
                    logger.warning(f"Recovery strategy failed: {str(e)}")
        
        return None
    
    def _generate_recovery_suggestions(self, error: FileAccessError) -> List[str]:
        """Generate human-readable recovery suggestions"""
        suggestions = []
        
        if error.error_type == FileAccessErrorType.PATH_NOT_FOUND:
            suggestions.extend([
                "Check if the file path is correct",
                "Verify that the file exists in the expected location",
                "Check if the parent directory exists",
                "Consider using an absolute path instead of relative path"
            ])
        
        elif error.error_type == FileAccessErrorType.PERMISSION_DENIED:
            suggestions.extend([
                "Check file and directory permissions",
                "Verify that the process has read/write access",
                "Consider running with appropriate privileges",
                "Check if the file is locked by another process"
            ])
        
        elif error.error_type == FileAccessErrorType.DISK_FULL:
            suggestions.extend([
                "Free up disk space",
                "Clean up temporary files",
                "Move large files to another location",
                "Consider using a different storage location"
            ])
        
        elif error.error_type == FileAccessErrorType.PATH_TOO_LONG:
            suggestions.extend([
                "Use a shorter file path",
                "Move files closer to the root directory",
                "Consider using symbolic links"
            ])
        
        elif error.error_type == FileAccessErrorType.CORRUPTED_FILE:
            suggestions.extend([
                "Verify file integrity",
                "Restore from backup if available",
                "Re-upload or recreate the file"
            ])
        
        else:
            suggestions.extend([
                "Check system logs for more details",
                "Verify network connectivity if using network storage",
                "Try the operation again after a short delay"
            ])
        
        return suggestions
    
    def _cleanup_temp_files(self) -> int:
        """Cleanup temporary files to free disk space"""
        freed_bytes = 0
        temp_dirs = ["/tmp", "/var/tmp", str(Path.home() / "tmp")]
        
        for temp_dir in temp_dirs:
            temp_path = Path(temp_dir)
            if temp_path.exists():
                try:
                    for file_path in temp_path.rglob("ai-validation-*"):
                        if file_path.is_file() and file_path.stat().st_mtime < time.time() - 3600:  # 1 hour old
                            size = file_path.stat().st_size
                            file_path.unlink()
                            freed_bytes += size
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp files in {temp_dir}: {str(e)}")
        
        return freed_bytes
    
    def _cleanup_old_logs(self) -> int:
        """Cleanup old log files"""
        freed_bytes = 0
        log_dirs = ["logs", "/var/log/ai-validation"]
        
        for log_dir in log_dirs:
            log_path = Path(log_dir)
            if log_path.exists():
                try:
                    for file_path in log_path.glob("*.log"):
                        if file_path.stat().st_mtime < time.time() - 7 * 24 * 3600:  # 7 days old
                            size = file_path.stat().st_size
                            file_path.unlink()
                            freed_bytes += size
                except Exception as e:
                    logger.warning(f"Failed to cleanup logs in {log_dir}: {str(e)}")
        
        return freed_bytes
    
    def _cleanup_old_screenshots(self) -> int:
        """Cleanup old screenshot files"""
        freed_bytes = 0
        screenshot_dirs = ["screenshots", "/var/lib/ai-validation/screenshots"]
        
        for screenshot_dir in screenshot_dirs:
            screenshot_path = Path(screenshot_dir)
            if screenshot_path.exists():
                try:
                    for file_path in screenshot_path.glob("*.jpg"):
                        if file_path.stat().st_mtime < time.time() - 24 * 3600:  # 1 day old
                            size = file_path.stat().st_size
                            file_path.unlink()
                            freed_bytes += size
                except Exception as e:
                    logger.warning(f"Failed to cleanup screenshots in {screenshot_dir}: {str(e)}")
        
        return freed_bytes
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics from history"""
        if not self.error_history:
            return {}
        
        total_errors = len(self.error_history)
        error_types = {}
        recovery_success = 0
        
        for error in self.error_history:
            error_type = error.error_type.value
            error_types[error_type] = error_types.get(error_type, 0) + 1
            
            if 'recovered_path' in error.metadata:
                recovery_success += 1
        
        return {
            'total_errors': total_errors,
            'error_types': error_types,
            'recovery_success_rate': recovery_success / total_errors if total_errors > 0 else 0,
            'most_common_error': max(error_types.items(), key=lambda x: x[1])[0] if error_types else None
        }


# Decorator for automatic error handling
def handle_file_access_errors(error_handler: Optional[FileAccessErrorHandler] = None,
                             reraise: bool = False,
                             return_none_on_error: bool = False):
    """Decorator to automatically handle file access errors"""
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handler = error_handler or get_default_error_handler()
                
                # Extract path information from arguments
                original_path = None
                for arg in args:
                    if isinstance(arg, (str, Path)):
                        original_path = str(arg)
                        break
                
                if not original_path:
                    for key, value in kwargs.items():
                        if 'path' in key.lower() and isinstance(value, (str, Path)):
                            original_path = str(value)
                            break
                
                # Handle the error
                error_info = handler.handle_file_access_error(
                    e, 
                    original_path or "unknown",
                    context={'function': func.__name__, 'args': str(args)[:100]}
                )
                
                # Check if we have a recovered path
                if 'recovered_path' in error_info.metadata:
                    # Try the function again with recovered path
                    try:
                        if original_path:
                            # Replace path in args/kwargs and retry
                            new_args = []
                            for arg in args:
                                if isinstance(arg, (str, Path)) and str(arg) == original_path:
                                    new_args.append(error_info.metadata['recovered_path'])
                                else:
                                    new_args.append(arg)
                            
                            return func(*new_args, **kwargs)
                    except Exception:
                        pass  # Recovery failed, handle below
                
                if return_none_on_error:
                    return None
                elif reraise:
                    raise
                else:
                    logger.error(f"File access error in {func.__name__}: {error_info.error_message}")
                    return None
        
        return wrapper
    return decorator


# Context manager for safe file operations
@contextmanager
def safe_file_operation(path: Union[str, Path], 
                       operation_type: str = "read",
                       error_handler: Optional[FileAccessErrorHandler] = None):
    """Context manager for safe file operations with automatic error handling"""
    
    handler = error_handler or get_default_error_handler()
    original_path = str(path)
    
    try:
        resolved_path = Path(path).resolve()
        yield resolved_path
        
    except Exception as e:
        error_info = handler.handle_file_access_error(
            e,
            original_path,
            str(resolved_path) if 'resolved_path' in locals() else None,
            context={'operation_type': operation_type}
        )
        
        # Try recovery if available
        if 'recovered_path' in error_info.metadata:
            try:
                recovered_path = Path(error_info.metadata['recovered_path'])
                yield recovered_path
            except Exception as recovery_error:
                logger.error(f"Recovery also failed: {recovery_error}")
                raise e
        else:
            raise e


# Global error handler instance
_default_error_handler = None


def get_default_error_handler() -> FileAccessErrorHandler:
    """Get the default global error handler"""
    global _default_error_handler
    if _default_error_handler is None:
        _default_error_handler = FileAccessErrorHandler()
    return _default_error_handler


def set_default_error_handler(handler: FileAccessErrorHandler):
    """Set the default global error handler"""
    global _default_error_handler
    _default_error_handler = handler