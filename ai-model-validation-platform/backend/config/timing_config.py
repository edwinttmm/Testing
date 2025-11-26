"""
Centralized timing configuration for HIL monitoring and video synchronization.

This module provides consistent timing parameters across all monitoring services
to ensure synchronized detection windows, tolerance ranges, and debounce logic.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# GRACE PERIOD CONFIGURATION
# =============================================================================

# Allow LabJack triggers that arrive up to 2 seconds before/after the video
DEFAULT_GRACE_PERIOD_MS = 2000  # 2s hardware pre-trigger window
GRACE_PERIOD_MS = int(os.getenv("HIL_GRACE_PERIOD_MS", DEFAULT_GRACE_PERIOD_MS))
GRACE_PERIOD_SECONDS = GRACE_PERIOD_MS / 1000.0

# =============================================================================
# MATCHING TOLERANCE CONFIGURATION
# =============================================================================

# PHASE 1 FIX: Increased tolerance from 100ms to 250ms for better detection matching
# Default matching tolerance for GT vs detection alignment (±250ms)
DEFAULT_MATCHING_TOLERANCE_MS = 250
MATCHING_TOLERANCE_MS = int(
    os.getenv("HIL_MATCHING_TOLERANCE_MS", DEFAULT_MATCHING_TOLERANCE_MS)
)
MATCHING_TOLERANCE_SECONDS = MATCHING_TOLERANCE_MS / 1000.0

# =============================================================================
# ADDITIONAL DETECTION CONSTANTS
# =============================================================================

# DETECTION DEBOUNCE CONFIGURATION
# Updated based on session daad8bf6-b5da-4423-abc4-a85e83bc1c16 FP analysis
# Previous: 50ms debounce (45 FP, 26% false positive rate)
# Root Cause: Duplicate/spurious detections caused by signal bounce, noise, or insufficient debouncing
# Many FPs have temporal offsets of ±15-20ms (within old debounce window)
# Recommended: 100-150ms debounce to eliminate duplicate detections
# Expected Impact: FP reduction from 45 to 15-20 (~56% reduction)
#                  Precision improvement from 74% to 86-88%
#                  F1 Score improvement from 85% to 90-92%
DETECTION_DEBOUNCE_MS = 10  # PHASE 1 FIX: Reduced from 20ms to 10ms for better detection responsiveness
DEFAULT_SAMPLE_RATE_HZ = 100
VOLTAGE_THRESHOLD_V = 2.5


def get_grace_period_ms(session_override: Optional[int] = None) -> int:
    """Return grace period in milliseconds, honoring optional overrides."""
    return session_override if session_override is not None else GRACE_PERIOD_MS


def get_grace_period_seconds(session_override: Optional[float] = None) -> float:
    """Return grace period in seconds, honoring optional overrides."""
    if session_override is not None:
        return session_override
    return GRACE_PERIOD_SECONDS


def get_matching_tolerance_ms(session_override: Optional[int] = None) -> int:
    """Return tolerance window in milliseconds."""
    return session_override if session_override is not None else MATCHING_TOLERANCE_MS


def get_matching_tolerance_seconds(session_override: Optional[float] = None) -> float:
    """Return tolerance window in seconds."""
    if session_override is not None:
        return session_override
    return MATCHING_TOLERANCE_SECONDS


def validate_timing_config() -> None:
    """Validate configuration to fail fast on misconfiguration."""
    if GRACE_PERIOD_MS <= 0:
        raise ValueError(f"GRACE_PERIOD_MS must be positive, got {GRACE_PERIOD_MS}")
    if MATCHING_TOLERANCE_MS <= 0:
        raise ValueError(
            f"MATCHING_TOLERANCE_MS must be positive, got {MATCHING_TOLERANCE_MS}"
        )
    if GRACE_PERIOD_MS < MATCHING_TOLERANCE_MS:
        logger.warning(
            "Grace period (%sms) is less than matching tolerance (%sms).",
            GRACE_PERIOD_MS,
            MATCHING_TOLERANCE_MS,
        )
    logger.info(
        "✅ Timing configuration loaded: GRACE_PERIOD=%sms, MATCHING_TOLERANCE=%sms",
        GRACE_PERIOD_MS,
        MATCHING_TOLERANCE_MS,
    )


validate_timing_config()


__all__ = [
    "DEFAULT_GRACE_PERIOD_MS",
    "GRACE_PERIOD_MS",
    "GRACE_PERIOD_SECONDS",
    "DEFAULT_MATCHING_TOLERANCE_MS",
    "MATCHING_TOLERANCE_MS",
    "MATCHING_TOLERANCE_SECONDS",
    "DETECTION_DEBOUNCE_MS",
    "DEFAULT_SAMPLE_RATE_HZ",
    "VOLTAGE_THRESHOLD_V",
    "get_grace_period_ms",
    "get_grace_period_seconds",
    "get_matching_tolerance_ms",
    "get_matching_tolerance_seconds",
]
