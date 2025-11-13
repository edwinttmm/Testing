"""
Clock Synchronization Service

Validates clock drift between frontend, backend, and hardware timestamps.
Prevents timing issues caused by clock skew across distributed components.
"""

import time
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class ClockSkewError(Exception):
    """Raised when clock drift exceeds tolerance."""

    def __init__(self, message: str, drift_seconds: float):
        super().__init__(message)
        self.drift_seconds = drift_seconds


def validate_clock_sync(
    frontend_timestamp: float,
    backend_timestamp: Optional[float] = None,
    hardware_timestamp: Optional[float] = None,
    max_frontend_drift_seconds: float = 5.0,
    max_hardware_drift_seconds: float = 1.0
) -> Tuple[bool, Optional[str]]:
    """
    Validate clock synchronization between frontend, backend, and hardware.

    Args:
        frontend_timestamp: Timestamp from frontend (Unix timestamp)
        backend_timestamp: Backend reference timestamp (defaults to time.time())
        hardware_timestamp: Hardware (LabJack) timestamp if available
        max_frontend_drift_seconds: Maximum acceptable frontend drift (default 5s)
        max_hardware_drift_seconds: Maximum acceptable hardware drift (default 1s)

    Returns:
        (is_valid, error_message) - Tuple indicating validation status

    Raises:
        ClockSkewError: If clock drift exceeds maximum tolerance
    """
    if backend_timestamp is None:
        backend_timestamp = time.time()

    # Check frontend clock drift
    frontend_drift = abs(frontend_timestamp - backend_timestamp)
    if frontend_drift > max_frontend_drift_seconds:
        raise ClockSkewError(
            f"Frontend clock drift {frontend_drift:.2f}s exceeds maximum {max_frontend_drift_seconds}s",
            frontend_drift
        )

    # Check hardware clock drift (if provided)
    if hardware_timestamp is not None:
        hardware_drift = abs(hardware_timestamp - backend_timestamp)
        if hardware_drift > max_hardware_drift_seconds:
            raise ClockSkewError(
                f"Hardware clock drift {hardware_drift:.2f}s exceeds maximum {max_hardware_drift_seconds}s",
                hardware_drift
            )

    return (True, None)


def log_clock_drift_metrics(
    frontend_timestamp: float,
    backend_timestamp: Optional[float] = None,
    hardware_timestamp: Optional[float] = None,
    context: str = "unknown"
) -> dict:
    """
    Log clock drift metrics for monitoring without raising errors.

    Args:
        frontend_timestamp: Frontend timestamp
        backend_timestamp: Backend timestamp (defaults to time.time())
        hardware_timestamp: Hardware timestamp if available
        context: Context description for logging

    Returns:
        Dictionary with drift metrics
    """
    if backend_timestamp is None:
        backend_timestamp = time.time()

    metrics = {
        'context': context,
        'frontend_timestamp': frontend_timestamp,
        'backend_timestamp': backend_timestamp,
        'frontend_drift_ms': (frontend_timestamp - backend_timestamp) * 1000.0,
        'frontend_drift_abs_ms': abs(frontend_timestamp - backend_timestamp) * 1000.0
    }

    if hardware_timestamp is not None:
        metrics['hardware_timestamp'] = hardware_timestamp
        metrics['hardware_drift_ms'] = (hardware_timestamp - backend_timestamp) * 1000.0
        metrics['hardware_drift_abs_ms'] = abs(hardware_timestamp - backend_timestamp) * 1000.0

    logger.debug(f"Clock drift metrics [{context}]: {metrics}")

    return metrics
