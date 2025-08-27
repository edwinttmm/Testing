#!/usr/bin/env python3
"""
Configuration module for AI Model Validation Platform
Provides unified settings and database configuration
"""

from .vru_settings import (
    VRUSettings,
    Environment,
    DatabaseType,
    get_settings,
    get_config,
    settings
)

__all__ = [
    "VRUSettings",
    "Environment", 
    "DatabaseType",
    "get_settings",
    "get_config",
    "settings"
]