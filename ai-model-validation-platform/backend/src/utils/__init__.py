"""
Utility modules for the AI Model Validation Platform
==================================================

This package contains utility functions and classes for common operations
including path management, validation, and other helper functions.
"""

from .path_utils import (
    PathManager,
    get_path_manager,
    resolve_path,
    resolve_upload_path,
    resolve_screenshot_path,
    migrate_legacy_path,
    ensure_path_exists,
    is_safe_path,
    get_relative_path
)

__all__ = [
    'PathManager',
    'get_path_manager',
    'resolve_path',
    'resolve_upload_path', 
    'resolve_screenshot_path',
    'migrate_legacy_path',
    'ensure_path_exists',
    'is_safe_path',
    'get_relative_path'
]