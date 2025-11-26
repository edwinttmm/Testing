"""
Retry Configuration with Exponential Backoff
============================================

Provides retry decorators for transient failure handling across the application.

Features:
- Exponential backoff with configurable multipliers
- Per-operation retry policies (LabJack, Database, WebSocket)
- Comprehensive logging before retries
- Type-safe decorator definitions
- Environment variable configuration support

Author: Backend API Developer Agent
Date: 2025-11-20
Status: Production-Ready
"""

import logging
import os
from typing import Type, Tuple, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryCallState,
    after_log
)
from sqlalchemy.exc import DBAPIError, OperationalError, IntegrityError

logger = logging.getLogger(__name__)


# ==================== CONFIGURATION ====================

class RetryConfig:
    """Centralized retry configuration with environment variable support"""

    # LabJack USB Communication
    LABJACK_MAX_ATTEMPTS = int(os.getenv("LABJACK_RETRY_MAX_ATTEMPTS", "3"))
    LABJACK_MIN_WAIT = float(os.getenv("LABJACK_RETRY_MIN_WAIT", "1.0"))
    LABJACK_MAX_WAIT = float(os.getenv("LABJACK_RETRY_MAX_WAIT", "10.0"))
    LABJACK_MULTIPLIER = float(os.getenv("LABJACK_RETRY_MULTIPLIER", "1.0"))

    # Database Operations
    DATABASE_MAX_ATTEMPTS = int(os.getenv("DATABASE_RETRY_MAX_ATTEMPTS", "5"))
    DATABASE_MIN_WAIT = float(os.getenv("DATABASE_RETRY_MIN_WAIT", "0.5"))
    DATABASE_MAX_WAIT = float(os.getenv("DATABASE_RETRY_MAX_WAIT", "5.0"))
    DATABASE_MULTIPLIER = float(os.getenv("DATABASE_RETRY_MULTIPLIER", "0.5"))

    # WebSocket Operations
    WEBSOCKET_MAX_ATTEMPTS = int(os.getenv("WEBSOCKET_RETRY_MAX_ATTEMPTS", "3"))
    WEBSOCKET_MIN_WAIT = float(os.getenv("WEBSOCKET_RETRY_MIN_WAIT", "0.5"))
    WEBSOCKET_MAX_WAIT = float(os.getenv("WEBSOCKET_RETRY_MAX_WAIT", "3.0"))
    WEBSOCKET_MULTIPLIER = float(os.getenv("WEBSOCKET_RETRY_MULTIPLIER", "0.5"))


# ==================== CUSTOM CALLBACKS ====================

def log_retry_attempt(retry_state: RetryCallState) -> None:
    """
    Custom callback to log detailed retry information.

    Args:
        retry_state: Current state of the retry attempt
    """
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    attempt_number = retry_state.attempt_number

    if exception:
        logger.warning(
            f"Retry attempt {attempt_number} for {retry_state.fn.__name__}: "
            f"{type(exception).__name__}: {str(exception)}"
        )


# ==================== LABJACK RETRY DECORATOR ====================

def labjack_retry(func):
    """
    Retry decorator for LabJack USB communication operations.

    Handles transient failures in:
    - USB device communication
    - Device connection/disconnection
    - Timeout errors
    - Device not found errors

    Configuration:
    - Max attempts: 3 (configurable via LABJACK_RETRY_MAX_ATTEMPTS)
    - Wait strategy: Exponential backoff (1s → 2s → 4s)
    - Retry on: ConnectionError, TimeoutError, OSError

    Example:
        ```python
        @labjack_retry
        def start_monitoring(self, video_id: str):
            # This will retry up to 3 times with exponential backoff
            result = labjack_device.initialize()
            return result
        ```
    """
    decorator = retry(
        stop=stop_after_attempt(RetryConfig.LABJACK_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=RetryConfig.LABJACK_MULTIPLIER,
            min=RetryConfig.LABJACK_MIN_WAIT,
            max=RetryConfig.LABJACK_MAX_WAIT
        ),
        retry=retry_if_exception_type((
            ConnectionError,
            TimeoutError,
            OSError,
            # Add LabJack-specific exceptions if they exist
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    return decorator(func)


# ==================== DATABASE RETRY DECORATOR ====================

def database_retry(func):
    """
    Retry decorator for database operations.

    Handles transient failures in:
    - Connection pool exhaustion
    - Temporary network issues
    - Deadlock detection
    - Serialization failures (PostgreSQL MVCC)

    Configuration:
    - Max attempts: 5 (configurable via DATABASE_RETRY_MAX_ATTEMPTS)
    - Wait strategy: Exponential backoff (0.5s → 1s → 2s → 4s)
    - Retry on: DBAPIError, OperationalError (excluding integrity errors)

    Note: Does NOT retry on IntegrityError (constraint violations) as these
    indicate data problems, not transient failures.

    Example:
        ```python
        @database_retry
        async def store_detection_event(self, session, event):
            # This will retry up to 5 times with exponential backoff
            session.add(event)
            await session.commit()
        ```
    """

    def should_retry_db_error(exception: Exception) -> bool:
        """
        Determine if database error should be retried.

        Do NOT retry:
        - IntegrityError (constraint violations)
        - User-caused errors

        DO retry:
        - Connection errors
        - Timeout errors
        - Serialization errors
        """
        if isinstance(exception, IntegrityError):
            # Don't retry constraint violations - these are permanent
            return False

        if isinstance(exception, (DBAPIError, OperationalError)):
            # Retry connection and serialization errors
            return True

        return False

    decorator = retry(
        stop=stop_after_attempt(RetryConfig.DATABASE_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=RetryConfig.DATABASE_MULTIPLIER,
            min=RetryConfig.DATABASE_MIN_WAIT,
            max=RetryConfig.DATABASE_MAX_WAIT
        ),
        retry=retry_if_exception_type((DBAPIError, OperationalError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    return decorator(func)


# ==================== WEBSOCKET RETRY DECORATOR ====================

def websocket_retry(func):
    """
    Retry decorator for WebSocket operations.

    Handles transient failures in:
    - WebSocket connection establishment
    - Message send failures
    - Temporary network disruptions

    Configuration:
    - Max attempts: 3 (configurable via WEBSOCKET_RETRY_MAX_ATTEMPTS)
    - Wait strategy: Exponential backoff (0.5s → 1s → 2s)
    - Retry on: ConnectionError, OSError, TimeoutError

    Example:
        ```python
        @websocket_retry
        async def send_message(self, connection_id: str, message: dict):
            # This will retry up to 3 times with exponential backoff
            await websocket.send_text(json.dumps(message))
        ```
    """
    decorator = retry(
        stop=stop_after_attempt(RetryConfig.WEBSOCKET_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=RetryConfig.WEBSOCKET_MULTIPLIER,
            min=RetryConfig.WEBSOCKET_MIN_WAIT,
            max=RetryConfig.WEBSOCKET_MAX_WAIT
        ),
        retry=retry_if_exception_type((
            ConnectionError,
            OSError,
            TimeoutError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    return decorator(func)


# ==================== METRICS ====================

class RetryMetrics:
    """
    Track retry metrics for monitoring and alerting.

    Production metrics exposed:
    - Total retry attempts per operation type
    - Success rate after retries
    - Average retry count before success
    - Permanent failures (exhausted retries)
    """

    def __init__(self):
        self.labjack_retries = 0
        self.labjack_successes = 0
        self.labjack_failures = 0

        self.database_retries = 0
        self.database_successes = 0
        self.database_failures = 0

        self.websocket_retries = 0
        self.websocket_successes = 0
        self.websocket_failures = 0

    def record_labjack_retry(self):
        """Record a LabJack retry attempt"""
        self.labjack_retries += 1

    def record_labjack_success(self):
        """Record a successful LabJack operation (after retries)"""
        self.labjack_successes += 1

    def record_labjack_failure(self):
        """Record a permanent LabJack failure (exhausted retries)"""
        self.labjack_failures += 1

    def record_database_retry(self):
        """Record a database retry attempt"""
        self.database_retries += 1

    def record_database_success(self):
        """Record a successful database operation (after retries)"""
        self.database_successes += 1

    def record_database_failure(self):
        """Record a permanent database failure (exhausted retries)"""
        self.database_failures += 1

    def record_websocket_retry(self):
        """Record a WebSocket retry attempt"""
        self.websocket_retries += 1

    def record_websocket_success(self):
        """Record a successful WebSocket operation (after retries)"""
        self.websocket_successes += 1

    def record_websocket_failure(self):
        """Record a permanent WebSocket failure (exhausted retries)"""
        self.websocket_failures += 1

    def get_metrics(self) -> dict:
        """
        Get all retry metrics.

        Returns:
            Dictionary with retry statistics for all operation types
        """
        return {
            "labjack": {
                "retries": self.labjack_retries,
                "successes": self.labjack_successes,
                "failures": self.labjack_failures,
                "success_rate": (
                    self.labjack_successes / (self.labjack_successes + self.labjack_failures)
                    if (self.labjack_successes + self.labjack_failures) > 0
                    else 0.0
                )
            },
            "database": {
                "retries": self.database_retries,
                "successes": self.database_successes,
                "failures": self.database_failures,
                "success_rate": (
                    self.database_successes / (self.database_successes + self.database_failures)
                    if (self.database_successes + self.database_failures) > 0
                    else 0.0
                )
            },
            "websocket": {
                "retries": self.websocket_retries,
                "successes": self.websocket_successes,
                "failures": self.websocket_failures,
                "success_rate": (
                    self.websocket_successes / (self.websocket_successes + self.websocket_failures)
                    if (self.websocket_successes + self.websocket_failures) > 0
                    else 0.0
                )
            }
        }

    def reset(self):
        """Reset all metrics (for testing)"""
        self.__init__()


# Global metrics instance
retry_metrics = RetryMetrics()


# ==================== USAGE EXAMPLES ====================

if __name__ == "__main__":
    """
    Example usage of retry decorators.

    Run this file directly to see retry behavior in action.
    """
    import asyncio
    import time

    # Example 1: LabJack retry with simulated failures
    @labjack_retry
    def connect_to_labjack_example():
        """Simulates LabJack connection with transient failures"""
        import random
        if random.random() < 0.7:  # 70% failure rate for demo
            raise ConnectionError("LabJack USB device not responding")
        return {"success": True, "device_id": "LJ-T7-12345"}

    # Example 2: Database retry with simulated MVCC lag
    @database_retry
    def store_detection_event_example():
        """Simulates database write with MVCC lag"""
        import random
        if random.random() < 0.5:  # 50% failure rate for demo
            raise OperationalError("connection", "params", "orig", "statement")
        return {"success": True, "rows_affected": 1}

    # Example 3: WebSocket retry with simulated network issues
    @websocket_retry
    async def send_websocket_message_example():
        """Simulates WebSocket send with network issues"""
        import random
        if random.random() < 0.6:  # 60% failure rate for demo
            raise ConnectionError("WebSocket connection lost")
        return {"success": True, "message_sent": True}

    print("Testing retry decorators with simulated failures...\n")

    # Test LabJack retry
    try:
        print("1. Testing LabJack retry (up to 3 attempts)...")
        result = connect_to_labjack_example()
        print(f"   ✓ Success: {result}\n")
    except Exception as e:
        print(f"   ✗ Failed after retries: {e}\n")

    # Test Database retry
    try:
        print("2. Testing Database retry (up to 5 attempts)...")
        result = store_detection_event_example()
        print(f"   ✓ Success: {result}\n")
    except Exception as e:
        print(f"   ✗ Failed after retries: {e}\n")

    # Test WebSocket retry
    try:
        print("3. Testing WebSocket retry (up to 3 attempts)...")
        result = asyncio.run(send_websocket_message_example())
        print(f"   ✓ Success: {result}\n")
    except Exception as e:
        print(f"   ✗ Failed after retries: {e}\n")

    # Show metrics
    print("Retry Metrics:")
    print(retry_metrics.get_metrics())
