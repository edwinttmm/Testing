#!/usr/bin/env python3
"""
Circuit Breaker Pattern for LabJack Hardware Communication
===========================================================

Implements the circuit breaker pattern to prevent system hangs when LabJack
hardware fails repeatedly. The circuit breaker monitors failure rates and
automatically "opens" to reject calls when failures exceed thresholds,
preventing cascading failures and system hangs.

Circuit States:
- CLOSED: Normal operation, allow all calls
- OPEN: Failing, reject all calls (return cached or error)
- HALF_OPEN: Testing recovery, allow limited calls

Thresholds:
- failure_threshold: 5 failures → OPEN
- timeout: 30 seconds before HALF_OPEN
- success_threshold: 2 successes in HALF_OPEN → CLOSED

Usage:
    breaker = CircuitBreaker(name="LabJackUSB", failure_threshold=5)

    try:
        result = breaker.call(labjack_function, *args, **kwargs)
    except CircuitBreakerOpen as e:
        logger.error(f"Circuit open, retry after {e.retry_after}s")
        # Use cached value or return error
"""

import logging
import time
import threading
from enum import Enum
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"          # Normal operation, allow all calls
    OPEN = "open"              # Failing, reject all calls
    HALF_OPEN = "half_open"    # Testing recovery, allow one call


class CircuitBreakerOpen(Exception):
    """
    Raised when circuit breaker is open.

    Attributes:
        name: Circuit breaker name
        retry_after: Seconds until circuit may transition to HALF_OPEN
        last_failure: Timestamp of last failure
    """
    def __init__(self, name: str, retry_after: float, last_failure: Optional[datetime] = None):
        self.name = name
        self.retry_after = retry_after
        self.last_failure = last_failure
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. System is failing. "
            f"Retry after {retry_after:.1f}s"
        )


@dataclass
class CircuitBreakerMetrics:
    """Metrics for monitoring circuit breaker health"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_transitions: Dict[str, int] = field(default_factory=lambda: {
        "CLOSED->OPEN": 0,
        "OPEN->HALF_OPEN": 0,
        "HALF_OPEN->CLOSED": 0,
        "HALF_OPEN->OPEN": 0
    })
    time_in_open_state: float = 0.0  # Total seconds in OPEN state
    time_in_half_open_state: float = 0.0  # Total seconds in HALF_OPEN state
    last_state_change: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for logging/monitoring"""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "success_rate": self.successful_calls / max(1, self.total_calls),
            "rejection_rate": self.rejected_calls / max(1, self.total_calls),
            "state_transitions": self.state_transitions,
            "time_in_open_state_seconds": self.time_in_open_state,
            "time_in_half_open_state_seconds": self.time_in_half_open_state,
            "last_state_change": self.last_state_change.isoformat() if self.last_state_change else None
        }


class CircuitBreaker:
    """
    Circuit breaker pattern for LabJack hardware communication.

    Protects against repeated hardware failures by:
    1. Monitoring failure rate
    2. Opening circuit when threshold exceeded
    3. Testing recovery periodically
    4. Automatically closing when recovered

    Thread-safe implementation using RLock.

    Example:
        breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=30.0,
            success_threshold=2,
            name="LabJackUSB"
        )

        try:
            voltage = breaker.call(read_voltage, channel="AIN0")
        except CircuitBreakerOpen as e:
            logger.error(f"Hardware unavailable: {e}")
            # Use cached value or return error
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 30.0,
        success_threshold: int = 2,
        name: str = "CircuitBreaker"
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before opening circuit
            timeout: Seconds to wait before attempting recovery (OPEN -> HALF_OPEN)
            success_threshold: Number of successes in HALF_OPEN before closing circuit
            name: Circuit breaker identifier for logging
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold
        self.name = name

        # State management
        self._state = CircuitState.CLOSED
        self._lock = threading.RLock()  # Reentrant lock for thread safety

        # Failure tracking
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._state_start_time: float = time.time()

        # Metrics
        self.metrics = CircuitBreakerMetrics()

        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"failure_threshold={failure_threshold}, "
            f"timeout={timeout}s, "
            f"success_threshold={success_threshold}"
        )

    @property
    def state(self) -> CircuitState:
        """Thread-safe state access"""
        with self._lock:
            return self._state

    @property
    def failure_count(self) -> int:
        """Thread-safe failure count access"""
        with self._lock:
            return self._failure_count

    @property
    def success_count(self) -> int:
        """Thread-safe success count access"""
        with self._lock:
            return self._success_count

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func(*args, **kwargs)

        Raises:
            CircuitBreakerOpen: If circuit is OPEN and timeout not expired
            Exception: Any exception raised by func
        """
        with self._lock:
            self.metrics.total_calls += 1

            # Check current state and handle accordingly
            current_state = self._state

            if current_state == CircuitState.OPEN:
                return self._handle_open_state(func, *args, **kwargs)
            elif current_state == CircuitState.HALF_OPEN:
                return self._handle_half_open_state(func, *args, **kwargs)
            else:  # CLOSED
                return self._handle_closed_state(func, *args, **kwargs)

    def _handle_open_state(self, func: Callable, *args, **kwargs) -> Any:
        """Handle call when circuit is OPEN"""
        # Check if timeout has expired
        if self._last_failure_time is None:
            # Should never happen, but handle gracefully
            self._transition_to_half_open()
            return self._execute_function(func, *args, **kwargs)

        elapsed = time.time() - self._last_failure_time

        if elapsed >= self.timeout:
            # Timeout expired, transition to HALF_OPEN
            logger.info(
                f"Circuit breaker '{self.name}': Timeout expired "
                f"({elapsed:.1f}s >= {self.timeout}s), transitioning to HALF_OPEN"
            )
            self._transition_to_half_open()
            return self._execute_function(func, *args, **kwargs)
        else:
            # Still in timeout period, reject call
            self.metrics.rejected_calls += 1
            retry_after = self.timeout - elapsed
            logger.warning(
                f"Circuit breaker '{self.name}': Circuit OPEN, "
                f"rejecting call (retry in {retry_after:.1f}s)"
            )
            raise CircuitBreakerOpen(
                name=self.name,
                retry_after=retry_after,
                last_failure=datetime.fromtimestamp(self._last_failure_time)
            )

    def _handle_half_open_state(self, func: Callable, *args, **kwargs) -> Any:
        """Handle call when circuit is HALF_OPEN (testing recovery)"""
        logger.debug(
            f"Circuit breaker '{self.name}': HALF_OPEN, "
            f"attempting recovery test ({self._success_count}/{self.success_threshold})"
        )
        return self._execute_function(func, *args, **kwargs)

    def _handle_closed_state(self, func: Callable, *args, **kwargs) -> Any:
        """Handle call when circuit is CLOSED (normal operation)"""
        return self._execute_function(func, *args, **kwargs)

    def _execute_function(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function and update circuit breaker state based on result.

        This method is called with lock already held.
        """
        try:
            # Execute the function
            result = func(*args, **kwargs)

            # Success - update state
            self._on_success()

            return result

        except Exception as e:
            # Failure - update state
            self._on_failure(e)

            # Re-raise the original exception
            raise

    def _on_success(self):
        """Handle successful function execution (called with lock held)"""
        self.metrics.successful_calls += 1
        self._failure_count = 0  # Reset failure counter

        current_state = self._state

        if current_state == CircuitState.HALF_OPEN:
            # Increment success counter in HALF_OPEN
            self._success_count += 1

            logger.debug(
                f"Circuit breaker '{self.name}': Success in HALF_OPEN "
                f"({self._success_count}/{self.success_threshold})"
            )

            # Check if we've hit success threshold
            if self._success_count >= self.success_threshold:
                self._transition_to_closed()
        else:
            # In CLOSED state, just log success
            logger.debug(f"Circuit breaker '{self.name}': Call succeeded")

    def _on_failure(self, exception: Exception):
        """Handle failed function execution (called with lock held)"""
        self.metrics.failed_calls += 1
        self._failure_count += 1
        self._last_failure_time = time.time()

        current_state = self._state

        logger.warning(
            f"Circuit breaker '{self.name}': Call failed "
            f"(failure {self._failure_count}/{self.failure_threshold}): {exception}"
        )

        if current_state == CircuitState.CLOSED:
            # Check if we've hit failure threshold
            if self._failure_count >= self.failure_threshold:
                self._transition_to_open()

        elif current_state == CircuitState.HALF_OPEN:
            # Any failure in HALF_OPEN goes back to OPEN
            logger.warning(
                f"Circuit breaker '{self.name}': Failure in HALF_OPEN, "
                f"returning to OPEN state"
            )
            self._transition_to_open()

    def _transition_to_open(self):
        """Transition to OPEN state (called with lock held)"""
        old_state = self._state
        self._state = CircuitState.OPEN
        self._success_count = 0  # Reset success counter

        # Update metrics
        transition_key = f"{old_state.value.upper()}->OPEN"
        self.metrics.state_transitions[transition_key] = \
            self.metrics.state_transitions.get(transition_key, 0) + 1
        self.metrics.last_state_change = datetime.now()

        logger.error(
            f"Circuit breaker '{self.name}': OPENING circuit "
            f"(failures: {self._failure_count}/{self.failure_threshold}). "
            f"Will retry in {self.timeout}s"
        )

    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state (called with lock held)"""
        old_state = self._state

        # Update time spent in old state
        if old_state == CircuitState.OPEN:
            time_in_state = time.time() - self._state_start_time
            self.metrics.time_in_open_state += time_in_state

        self._state = CircuitState.HALF_OPEN
        self._success_count = 0  # Reset success counter
        self._failure_count = 0  # Reset failure counter
        self._state_start_time = time.time()

        # Update metrics
        transition_key = f"{old_state.value.upper()}->HALF_OPEN"
        self.metrics.state_transitions[transition_key] = \
            self.metrics.state_transitions.get(transition_key, 0) + 1
        self.metrics.last_state_change = datetime.now()

        logger.info(
            f"Circuit breaker '{self.name}': Transitioning to HALF_OPEN "
            f"(testing recovery)"
        )

    def _transition_to_closed(self):
        """Transition to CLOSED state (called with lock held)"""
        old_state = self._state

        # Update time spent in old state
        if old_state == CircuitState.HALF_OPEN:
            time_in_state = time.time() - self._state_start_time
            self.metrics.time_in_half_open_state += time_in_state

        self._state = CircuitState.CLOSED
        self._failure_count = 0  # Reset failure counter
        self._success_count = 0  # Reset success counter
        self._state_start_time = time.time()

        # Update metrics
        transition_key = f"{old_state.value.upper()}->CLOSED"
        self.metrics.state_transitions[transition_key] = \
            self.metrics.state_transitions.get(transition_key, 0) + 1
        self.metrics.last_state_change = datetime.now()

        logger.info(
            f"Circuit breaker '{self.name}': Circuit CLOSED "
            f"(recovered after {self.success_threshold} successes)"
        )

    def reset(self):
        """Manually reset circuit breaker to CLOSED state"""
        with self._lock:
            old_state = self._state
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None

            logger.info(
                f"Circuit breaker '{self.name}': Manually reset to CLOSED "
                f"(was {old_state.value})"
            )

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics for monitoring/debugging.

        Returns:
            Dictionary with current metrics and state
        """
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "failure_threshold": self.failure_threshold,
                "success_threshold": self.success_threshold,
                "timeout_seconds": self.timeout,
                "last_failure_time": datetime.fromtimestamp(self._last_failure_time).isoformat()
                    if self._last_failure_time else None,
                "time_since_last_failure": time.time() - self._last_failure_time
                    if self._last_failure_time else None,
                "metrics": self.metrics.to_dict()
            }
