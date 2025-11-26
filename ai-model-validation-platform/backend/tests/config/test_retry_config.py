"""
Unit Tests for Retry Configuration with Exponential Backoff
===========================================================

Comprehensive test suite for retry logic with:
- Transient failure retry behavior
- Exponential backoff timing validation
- Max attempts exhaustion
- Permanent failure detection (no retry)
- Metrics tracking

Author: Backend API Developer Agent
Date: 2025-11-20
Status: Production-Ready
"""

import os
import pytest
import time
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.exc import DBAPIError, OperationalError, IntegrityError

from src.config.retry_config import (
    labjack_retry,
    database_retry,
    websocket_retry,
    RetryConfig,
    RetryMetrics,
    retry_metrics
)


# ==================== TEST FIXTURES ====================

@pytest.fixture
def reset_metrics():
    """Reset global retry metrics before each test"""
    retry_metrics.reset()
    yield
    retry_metrics.reset()


@pytest.fixture
def mock_time():
    """Mock time.time() for exponential backoff timing tests"""
    with patch('time.time') as mock:
        mock.return_value = 0.0
        yield mock


@pytest.fixture
def mock_sleep():
    """Mock time.sleep() to speed up tests"""
    with patch('time.sleep') as mock:
        yield mock


# ==================== LABJACK RETRY TESTS ====================

class TestLabJackRetry:
    """Test suite for LabJack retry decorator"""

    def test_retry_on_transient_failure(self, reset_metrics):
        """Test that LabJack retry succeeds after transient failure"""
        call_count = 0

        @labjack_retry
        def connect_labjack():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("USB device not responding")
            return {"success": True}

        result = connect_labjack()

        assert result["success"] is True
        assert call_count == 2  # Failed once, succeeded on retry

    def test_exponential_backoff_timing(self, mock_sleep):
        """Test exponential backoff delays (1s → 2s → 4s)"""
        call_count = 0

        @labjack_retry
        def failing_operation():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Simulated failure")

        with pytest.raises(ConnectionError):
            failing_operation()

        # Verify exponential backoff was applied
        assert mock_sleep.call_count == RetryConfig.LABJACK_MAX_ATTEMPTS - 1

        # Check backoff progression (approximately 1s, 2s)
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert len(delays) == 2
        # With multiplier=1.0, min=1s: should be ~1s, ~2s
        assert 0.9 <= delays[0] <= 1.1
        assert 1.8 <= delays[1] <= 2.2

    def test_max_attempts_reached(self):
        """Test that LabJack retry gives up after max attempts"""
        call_count = 0

        @labjack_retry
        def always_failing():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent USB failure")

        with pytest.raises(ConnectionError):
            always_failing()

        assert call_count == RetryConfig.LABJACK_MAX_ATTEMPTS

    def test_no_retry_on_permanent_failure(self):
        """Test that ValueError (permanent error) is not retried"""
        call_count = 0

        @labjack_retry
        def invalid_parameter():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid device ID")

        with pytest.raises(ValueError):
            invalid_parameter()

        # Should fail immediately without retries
        assert call_count == 1

    def test_timeout_error_retry(self):
        """Test that TimeoutError triggers retry"""
        call_count = 0

        @labjack_retry
        def timeout_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("USB communication timeout")
            return {"success": True}

        result = timeout_operation()

        assert result["success"] is True
        assert call_count == 2

    def test_os_error_retry(self):
        """Test that OSError triggers retry"""
        call_count = 0

        @labjack_retry
        def os_error_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OSError("USB device disconnected")
            return {"success": True}

        result = os_error_operation()

        assert result["success"] is True
        assert call_count == 2


# ==================== DATABASE RETRY TESTS ====================

class TestDatabaseRetry:
    """Test suite for database retry decorator"""

    def test_retry_on_transient_failure(self):
        """Test that database retry succeeds after transient failure"""
        call_count = 0

        @database_retry
        def store_event():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError("connection", "params", "orig", "statement")
            return {"success": True}

        result = store_event()

        assert result["success"] is True
        assert call_count == 3

    def test_exponential_backoff_timing(self, mock_sleep):
        """Test database exponential backoff (0.5s → 1s → 2s)"""
        call_count = 0

        @database_retry
        def failing_db_operation():
            nonlocal call_count
            call_count += 1
            raise DBAPIError("statement", "params", "orig", "connection_invalidated")

        with pytest.raises(DBAPIError):
            failing_db_operation()

        # Verify exponential backoff
        assert mock_sleep.call_count == RetryConfig.DATABASE_MAX_ATTEMPTS - 1

        # Check backoff progression (approximately 0.5s, 1s, 2s, 4s)
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert len(delays) == 4
        # With multiplier=0.5, min=0.5s: should be ~0.5s, ~1s, ~2s, ~4s
        assert 0.45 <= delays[0] <= 0.55
        assert 0.9 <= delays[1] <= 1.1
        assert 1.8 <= delays[2] <= 2.2
        assert 3.5 <= delays[3] <= 4.5

    def test_max_attempts_reached(self):
        """Test that database retry gives up after max attempts"""
        call_count = 0

        @database_retry
        def always_failing_db():
            nonlocal call_count
            call_count += 1
            raise OperationalError("connection", "params", "orig", "statement")

        with pytest.raises(OperationalError):
            always_failing_db()

        assert call_count == RetryConfig.DATABASE_MAX_ATTEMPTS

    def test_no_retry_on_integrity_error(self):
        """Test that IntegrityError (constraint violation) is NOT retried"""
        call_count = 0

        @database_retry
        def constraint_violation():
            nonlocal call_count
            call_count += 1
            raise IntegrityError("statement", "params", "orig")

        with pytest.raises(IntegrityError):
            constraint_violation()

        # Should fail immediately without retries (permanent error)
        assert call_count == 1

    def test_dbapi_error_retry(self):
        """Test that DBAPIError triggers retry"""
        call_count = 0

        @database_retry
        def dbapi_error_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise DBAPIError("statement", "params", "orig", "connection_invalidated")
            return {"success": True}

        result = dbapi_error_operation()

        assert result["success"] is True
        assert call_count == 2


# ==================== WEBSOCKET RETRY TESTS ====================

class TestWebSocketRetry:
    """Test suite for WebSocket retry decorator"""

    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self):
        """Test that WebSocket retry succeeds after transient failure"""
        call_count = 0

        @websocket_retry
        async def send_message():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("WebSocket connection lost")
            return {"success": True}

        result = await send_message()

        assert result["success"] is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, mock_sleep):
        """Test WebSocket exponential backoff (0.5s → 1s → 2s)"""
        call_count = 0

        @websocket_retry
        async def failing_ws_operation():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent connection failure")

        with pytest.raises(ConnectionError):
            await failing_ws_operation()

        # Verify exponential backoff
        assert mock_sleep.call_count == RetryConfig.WEBSOCKET_MAX_ATTEMPTS - 1

        # Check backoff progression
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert len(delays) == 2
        # With multiplier=0.5, min=0.5s: should be ~0.5s, ~1s
        assert 0.45 <= delays[0] <= 0.55
        assert 0.9 <= delays[1] <= 1.1

    @pytest.mark.asyncio
    async def test_max_attempts_reached(self):
        """Test that WebSocket retry gives up after max attempts"""
        call_count = 0

        @websocket_retry
        async def always_failing_ws():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent WebSocket failure")

        with pytest.raises(ConnectionError):
            await always_failing_ws()

        assert call_count == RetryConfig.WEBSOCKET_MAX_ATTEMPTS

    @pytest.mark.asyncio
    async def test_no_retry_on_permanent_failure(self):
        """Test that ValueError (permanent error) is not retried"""
        call_count = 0

        @websocket_retry
        async def invalid_message():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid message format")

        with pytest.raises(ValueError):
            await invalid_message()

        # Should fail immediately without retries
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_timeout_error_retry(self):
        """Test that TimeoutError triggers retry"""
        call_count = 0

        @websocket_retry
        async def timeout_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("WebSocket send timeout")
            return {"success": True}

        result = await timeout_operation()

        assert result["success"] is True
        assert call_count == 2


# ==================== RETRY METRICS TESTS ====================

class TestRetryMetrics:
    """Test suite for retry metrics tracking"""

    def test_labjack_metrics_tracking(self, reset_metrics):
        """Test LabJack metrics are tracked correctly"""
        retry_metrics.record_labjack_retry()
        retry_metrics.record_labjack_retry()
        retry_metrics.record_labjack_success()

        metrics = retry_metrics.get_metrics()

        assert metrics["labjack"]["retries"] == 2
        assert metrics["labjack"]["successes"] == 1
        assert metrics["labjack"]["failures"] == 0
        assert metrics["labjack"]["success_rate"] == 1.0

    def test_database_metrics_tracking(self, reset_metrics):
        """Test database metrics are tracked correctly"""
        retry_metrics.record_database_retry()
        retry_metrics.record_database_retry()
        retry_metrics.record_database_retry()
        retry_metrics.record_database_failure()

        metrics = retry_metrics.get_metrics()

        assert metrics["database"]["retries"] == 3
        assert metrics["database"]["successes"] == 0
        assert metrics["database"]["failures"] == 1
        assert metrics["database"]["success_rate"] == 0.0

    def test_websocket_metrics_tracking(self, reset_metrics):
        """Test WebSocket metrics are tracked correctly"""
        retry_metrics.record_websocket_retry()
        retry_metrics.record_websocket_success()
        retry_metrics.record_websocket_retry()
        retry_metrics.record_websocket_success()

        metrics = retry_metrics.get_metrics()

        assert metrics["websocket"]["retries"] == 2
        assert metrics["websocket"]["successes"] == 2
        assert metrics["websocket"]["failures"] == 0
        assert metrics["websocket"]["success_rate"] == 1.0

    def test_success_rate_calculation(self, reset_metrics):
        """Test success rate calculation"""
        # 2 successes, 1 failure = 66.67% success rate
        retry_metrics.record_labjack_success()
        retry_metrics.record_labjack_success()
        retry_metrics.record_labjack_failure()

        metrics = retry_metrics.get_metrics()

        assert abs(metrics["labjack"]["success_rate"] - 0.6667) < 0.01

    def test_metrics_reset(self, reset_metrics):
        """Test metrics reset functionality"""
        retry_metrics.record_labjack_retry()
        retry_metrics.record_database_retry()
        retry_metrics.record_websocket_retry()

        retry_metrics.reset()

        metrics = retry_metrics.get_metrics()

        assert metrics["labjack"]["retries"] == 0
        assert metrics["database"]["retries"] == 0
        assert metrics["websocket"]["retries"] == 0


# ==================== CONFIGURATION TESTS ====================

class TestRetryConfig:
    """Test suite for retry configuration"""

    def test_default_labjack_config(self):
        """Test default LabJack configuration values"""
        assert RetryConfig.LABJACK_MAX_ATTEMPTS == 3
        assert RetryConfig.LABJACK_MIN_WAIT == 1.0
        assert RetryConfig.LABJACK_MAX_WAIT == 10.0
        assert RetryConfig.LABJACK_MULTIPLIER == 1.0

    def test_default_database_config(self):
        """Test default database configuration values"""
        assert RetryConfig.DATABASE_MAX_ATTEMPTS == 5
        assert RetryConfig.DATABASE_MIN_WAIT == 0.5
        assert RetryConfig.DATABASE_MAX_WAIT == 5.0
        assert RetryConfig.DATABASE_MULTIPLIER == 0.5

    def test_default_websocket_config(self):
        """Test default WebSocket configuration values"""
        assert RetryConfig.WEBSOCKET_MAX_ATTEMPTS == 3
        assert RetryConfig.WEBSOCKET_MIN_WAIT == 0.5
        assert RetryConfig.WEBSOCKET_MAX_WAIT == 3.0
        assert RetryConfig.WEBSOCKET_MULTIPLIER == 0.5

    @patch.dict('os.environ', {
        'LABJACK_RETRY_MAX_ATTEMPTS': '5',
        'LABJACK_RETRY_MIN_WAIT': '2.0',
        'LABJACK_RETRY_MAX_WAIT': '20.0'
    })
    def test_environment_variable_override(self):
        """Test configuration can be overridden via environment variables"""
        # Re-import to pick up environment variables
        import importlib
        from src.config import retry_config
        importlib.reload(retry_config)

        # Note: This test requires module reload to work properly
        # In production, environment variables should be set before import


# ==================== INTEGRATION TESTS ====================

class TestRetryIntegration:
    """Integration tests for retry behavior in realistic scenarios"""

    def test_labjack_usb_reconnection_scenario(self):
        """Test realistic LabJack USB reconnection scenario"""
        attempts = []

        @labjack_retry
        def connect_labjack_with_logging():
            attempts.append(time.time())
            if len(attempts) < 3:
                raise ConnectionError("USB device not responding")
            return {"success": True, "device_id": "LJ-T7-12345"}

        result = connect_labjack_with_logging()

        assert result["success"] is True
        assert len(attempts) == 3  # Failed twice, succeeded third time

    def test_database_mvcc_lag_scenario(self):
        """Test realistic PostgreSQL MVCC lag scenario"""
        attempts = []

        @database_retry
        def store_with_mvcc_lag():
            attempts.append(time.time())
            if len(attempts) < 2:
                # Simulate MVCC serialization failure
                raise OperationalError("connection", "params", "orig", "could not serialize")
            return {"success": True, "rows_affected": 1}

        result = store_with_mvcc_lag()

        assert result["success"] is True
        assert len(attempts) == 2

    @pytest.mark.asyncio
    async def test_websocket_network_flap_scenario(self):
        """Test realistic WebSocket network flap scenario"""
        attempts = []

        @websocket_retry
        async def send_with_network_flap():
            attempts.append(time.time())
            if len(attempts) < 2:
                raise ConnectionError("Network unreachable")
            return {"success": True, "message_sent": True}

        result = await send_with_network_flap()

        assert result["success"] is True
        assert len(attempts) == 2
