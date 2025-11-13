#!/usr/bin/env python3
"""
Timing Configuration - Single Source of Truth for Detection Window Parameters

This module centralizes all timing-related configuration for the HIL test platform,
preventing inconsistencies like the grace period mismatch (100ms vs 2000ms).

CRITICAL: All services MUST import from this file instead of hardcoding values.
"""

import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# GRACE PERIOD CONFIGURATION
# =============================================================================

# Default grace period for detection windows
# This allows hardware LabJack signals that arrive before the 'playing' event
# Hardware pre-trigger can fire 0-2 seconds before frontend fires 'playing' event
DEFAULT_GRACE_PERIOD_MS = 2000  # 2 seconds (2000ms)

# Environment variable override
GRACE_PERIOD_MS = int(os.getenv('HIL_GRACE_PERIOD_MS', DEFAULT_GRACE_PERIOD_MS))

# Convert to seconds for convenience
GRACE_PERIOD_SECONDS = GRACE_PERIOD_MS / 1000.0

# =============================================================================
# MATCHING TOLERANCE CONFIGURATION
# =============================================================================

# Default matching tolerance for ground truth correlation
DEFAULT_MATCHING_TOLERANCE_MS = 100  # 100ms

# Environment variable override
MATCHING_TOLERANCE_MS = int(os.getenv('HIL_MATCHING_TOLERANCE_MS', DEFAULT_MATCHING_TOLERANCE_MS))

# Convert to seconds for convenience
MATCHING_TOLERANCE_SECONDS = MATCHING_TOLERANCE_MS / 1000.0

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_grace_period_ms(session_tolerance: Optional[int] = None) -> int:
    """
    Get grace period value with optional session override.

    Args:
        session_tolerance: Optional override for specific session

    Returns:
        Grace period in milliseconds
    """
    return session_tolerance if session_tolerance is not None else GRACE_PERIOD_MS


def get_grace_period_seconds(session_tolerance: Optional[float] = None) -> float:
    """
    Get grace period value in seconds with optional session override.

    Args:
        session_tolerance: Optional override for specific session (in seconds)

    Returns:
        Grace period in seconds
    """
    if session_tolerance is not None:
        return session_tolerance
    return GRACE_PERIOD_SECONDS


def get_matching_tolerance_ms(session_tolerance: Optional[int] = None) -> int:
    """
    Get matching tolerance value with optional session override.

    Args:
        session_tolerance: Optional override for specific session

    Returns:
        Matching tolerance in milliseconds
    """
    return session_tolerance if session_tolerance is not None else MATCHING_TOLERANCE_MS


def get_matching_tolerance_seconds(session_tolerance: Optional[float] = None) -> float:
    """
    Get matching tolerance value in seconds with optional session override.

    Args:
        session_tolerance: Optional override for specific session (in seconds)

    Returns:
        Matching tolerance in seconds
    """
    if session_tolerance is not None:
        return session_tolerance
    return MATCHING_TOLERANCE_SECONDS


# =============================================================================
# VALIDATION
# =============================================================================

def validate_timing_config():
    """Validate timing configuration on module load"""
    if GRACE_PERIOD_MS <= 0:
        raise ValueError(f"GRACE_PERIOD_MS must be positive, got {GRACE_PERIOD_MS}")

    if MATCHING_TOLERANCE_MS <= 0:
        raise ValueError(f"MATCHING_TOLERANCE_MS must be positive, got {MATCHING_TOLERANCE_MS}")

    if GRACE_PERIOD_MS < MATCHING_TOLERANCE_MS:
        logger.warning(
            f"Grace period ({GRACE_PERIOD_MS}ms) is less than matching tolerance ({MATCHING_TOLERANCE_MS}ms). "
            "This may cause unexpected behavior."
        )

    logger.info(f"✅ Timing configuration loaded: GRACE_PERIOD={GRACE_PERIOD_MS}ms, MATCHING_TOLERANCE={MATCHING_TOLERANCE_MS}ms")


# Run validation on import
validate_timing_config()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'GRACE_PERIOD_MS',
    'GRACE_PERIOD_SECONDS',
    'MATCHING_TOLERANCE_MS',
    'MATCHING_TOLERANCE_SECONDS',
    'get_grace_period_ms',
    'get_grace_period_seconds',
    'get_matching_tolerance_ms',
    'get_matching_tolerance_seconds',
]
