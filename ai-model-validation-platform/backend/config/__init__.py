"""
Configuration package for AI Model Validation Platform
"""

# Re-export everything from config_settings for backward compatibility
import sys
import os

# Import from the renamed config_settings.py file
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import all from config_settings module
import config_settings

# Re-export all public attributes
for attr in dir(config_settings):
    if not attr.startswith('_'):
        globals()[attr] = getattr(config_settings, attr)

# Import timing configuration constants
from config.timing_config import (
    GRACE_PERIOD_MS,
    GRACE_PERIOD_SECONDS,
    DETECTION_DEBOUNCE_MS,
    DEFAULT_SAMPLE_RATE_HZ,
    VOLTAGE_THRESHOLD_V
)

# Add to exports
__all__ = [attr for attr in dir() if not attr.startswith('_')]
