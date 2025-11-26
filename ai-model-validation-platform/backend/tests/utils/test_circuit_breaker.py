#!/usr/bin/env python3
"""
Unit Tests for Circuit Breaker Pattern
======================================

Comprehensive tests for CircuitBreaker class including:
- State transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Failure threshold behavior
- Timeout recovery
- Success threshold in HALF_OPEN
- Thread safety
- Metrics tracking
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch
from datetime import datetime

import sys
from pathlib import Path

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpen,
    CircuitBreakerMetrics
)


class TestCircuitBreakerBasic:
    """Basic circuit breaker functionality tests"""

    def test_initialization(self):
        """Test circuit breaker initializes correctly"""
        breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=10.0,
            success_threshold=2,
            name="TestBreaker"
        )

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0
        assert breaker.name == "TestBreaker"
        assert breaker.failure_threshold == 3
        assert breaker.timeout == 10.0
        assert breaker.success_threshold == 2

    def test_successful_call_in_closed_state(self):
        """Test successful function call in CLOSED state"""
        breaker = CircuitBreaker(name="TestBreaker")

        mock_func = Mock(return_value="success")
        result = breaker.call(mock_func, "arg1", key="value")

        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.metrics.successful_calls == 1
        mock_func.assert_called_once_with("arg1", key="value")

    def test_failed_call_below_threshold(self):
        """Test failed calls below failure threshold stay CLOSED"""
        breaker = CircuitBreaker(failure_threshold=3, name="TestBreaker")

        mock_func = Mock(side_effect=Exception("Test failure"))

        # First failure
        with pytest.raises(Exception, match="Test failure"):
            breaker.call(mock_func)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 1
        assert breaker.metrics.failed_calls == 1

        # Second failure
        with pytest.raises(Exception, match="Test failure"):
            breaker.call(mock_func)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 2


class TestCircuitBreakerStateTransitions:
    """Test state transition logic"""

    def test_transition_to_open(self):
        """Test CLOSED -> OPEN transition on failure threshold"""
        breaker = CircuitBreaker(failure_threshold=3, name="TestBreaker")

        mock_func = Mock(side_effect=Exception("Hardware failure"))

        # Hit failure threshold
        for i in range(3):
            with pytest.raises(Exception):
                breaker.call(mock_func)

        # Should now be OPEN
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 3
        assert breaker.metrics.state_transitions["CLOSED->OPEN"] == 1

    def test_open_state_rejects_calls(self):
        """Test OPEN state rejects calls before timeout"""
        breaker = CircuitBreaker(
            failure_threshold=2,
            timeout=10.0,  # 10 second timeout
            name="TestBreaker"
        )

        # Trigger OPEN state
        mock_func = Mock(side_effect=Exception("Failure"))
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(mock_func)

        assert breaker.state == CircuitState.OPEN

        # Now calls should be rejected
        with pytest.raises(CircuitBreakerOpen) as exc_info:
            breaker.call(mock_func)

        assert exc_info.value.name == "TestBreaker"
        assert exc_info.value.retry_after <= 10.0
        assert breaker.metrics.rejected_calls == 1

    def test_transition_to_half_open_after_timeout(self):
        """Test OPEN -> HALF_OPEN transition after timeout"""
        breaker = CircuitBreaker(
            failure_threshold=2,
            timeout=0.1,  # 100ms timeout for fast test
            name="TestBreaker"
        )

        # Trigger OPEN state
        mock_func = Mock(side_effect=Exception("Failure"))
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(mock_func)

        assert breaker.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(0.15)

        # Next call should transition to HALF_OPEN
        mock_func.side_effect = None
        mock_func.return_value = "success"

        result = breaker.call(mock_func)

        assert result == "success"
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.metrics.state_transitions["OPEN->HALF_OPEN"] == 1

    def test_half_open_to_closed_on_success_threshold(self):
        """Test HALF_OPEN -> CLOSED transition on success threshold"""
        breaker = CircuitBreaker(
            failure_threshold=2,
            timeout=0.1,
            success_threshold=2,  # Need 2 successes
            name="TestBreaker"
        )

        # Get to OPEN state
        mock_func = Mock(side_effect=Exception("Failure"))
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(mock_func)

        # Wait for timeout
        time.sleep(0.15)

        # Transition to HALF_OPEN with success
        mock_func.side_effect = None
        mock_func.return_value = "success"
        breaker.call(mock_func)

        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.success_count == 1

        # Second success should close circuit
        breaker.call(mock_func)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.success_count == 0  # Reset on transition
        assert breaker.failure_count == 0  # Reset on transition
        assert breaker.metrics.state_transitions["HALF_OPEN->CLOSED"] == 1

    def test_half_open_to_open_on_failure(self):
        """Test HALF_OPEN -> OPEN transition on any failure"""
        breaker = CircuitBreaker(
            failure_threshold=2,
            timeout=0.1,
            name="TestBreaker"
        )

        # Get to HALF_OPEN state
        mock_func = Mock(side_effect=Exception("Failure"))
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(mock_func)

        time.sleep(0.15)

        # First call succeeds (enters HALF_OPEN)
        mock_func.side_effect = None
        mock_func.return_value = "success"
        breaker.call(mock_func)

        assert breaker.state == CircuitState.HALF_OPEN

        # Next call fails -> back to OPEN
        mock_func.side_effect = Exception("Failed again")
        with pytest.raises(Exception):
            breaker.call(mock_func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.metrics.state_transitions["HALF_OPEN->OPEN"] == 1


class TestCircuitBreakerThreadSafety:
    """Test thread safety of circuit breaker"""

    def test_concurrent_calls(self):
        """Test circuit breaker handles concurrent calls safely"""
        breaker = CircuitBreaker(
            failure_threshold=10,
            name="TestBreaker"
        )

        call_count = 0
        lock = threading.Lock()

        def mock_func():
            with lock:
                nonlocal call_count
                call_count += 1
            return "success"

        # Spawn 20 threads making calls concurrently
        threads = []
        for _ in range(20):
            thread = threading.Thread(
                target=lambda: breaker.call(mock_func)
            )
            thread.start()
            threads.append(thread)

        # Wait for all threads
        for thread in threads:
            thread.join()

        # All calls should have succeeded
        assert call_count == 20
        assert breaker.metrics.successful_calls == 20
        assert breaker.state == CircuitState.CLOSED

    def test_concurrent_state_transitions(self):
        """Test state transitions are thread-safe"""
        breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=0.05,
            name="TestBreaker"
        )

        results = {"success": 0, "failure": 0, "rejected": 0}
        lock = threading.Lock()

        def failing_func():
            raise Exception("Failure")

        def make_call():
            try:
                breaker.call(failing_func)
                with lock:
                    results["success"] += 1
            except CircuitBreakerOpen:
                with lock:
                    results["rejected"] += 1
            except Exception:
                with lock:
                    results["failure"] += 1

        # Spawn threads to trigger state transitions
        threads = []
        for _ in range(20):
            thread = threading.Thread(target=make_call)
            thread.start()
            threads.append(thread)
            time.sleep(0.01)  # Stagger starts

        for thread in threads:
            thread.join()

        # Verify state is consistent
        assert breaker.state in [CircuitState.OPEN, CircuitState.HALF_OPEN]

        # Total calls should match
        total_calls = results["success"] + results["failure"] + results["rejected"]
        assert breaker.metrics.total_calls == total_calls


class TestCircuitBreakerMetrics:
    """Test metrics tracking"""

    def test_metrics_tracking(self):
        """Test metrics are tracked correctly"""
        breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=0.1,
            success_threshold=2,
            name="TestBreaker"
        )

        mock_func = Mock()

        # 5 successful calls
        mock_func.return_value = "success"
        for _ in range(5):
            breaker.call(mock_func)

        assert breaker.metrics.successful_calls == 5
        assert breaker.metrics.failed_calls == 0

        # 3 failed calls (triggers OPEN)
        mock_func.side_effect = Exception("Failure")
        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call(mock_func)

        assert breaker.metrics.failed_calls == 3

        # Rejected call
        with pytest.raises(CircuitBreakerOpen):
            breaker.call(mock_func)

        assert breaker.metrics.rejected_calls == 1

        # Check total
        assert breaker.metrics.total_calls == 9  # 5 success + 3 fail + 1 rejected

    def test_get_metrics(self):
        """Test get_metrics returns complete information"""
        breaker = CircuitBreaker(
            failure_threshold=2,
            timeout=5.0,
            name="TestBreaker"
        )

        metrics = breaker.get_metrics()

        assert metrics["name"] == "TestBreaker"
        assert metrics["state"] == "closed"
        assert metrics["failure_count"] == 0
        assert metrics["failure_threshold"] == 2
        assert metrics["timeout_seconds"] == 5.0
        assert "metrics" in metrics
        assert metrics["metrics"]["total_calls"] == 0

    def test_time_tracking(self):
        """Test time spent in each state is tracked"""
        breaker = CircuitBreaker(
            failure_threshold=2,
            timeout=0.1,
            success_threshold=1,
            name="TestBreaker"
        )

        # Trigger OPEN
        mock_func = Mock(side_effect=Exception("Failure"))
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(mock_func)

        # Wait in OPEN state
        time.sleep(0.15)

        # Transition to HALF_OPEN and then CLOSED
        mock_func.side_effect = None
        mock_func.return_value = "success"
        breaker.call(mock_func)

        metrics = breaker.get_metrics()

        # Should have spent time in OPEN state
        assert breaker.metrics.time_in_open_state > 0.1


class TestCircuitBreakerReset:
    """Test manual reset functionality"""

    def test_manual_reset(self):
        """Test circuit can be manually reset"""
        breaker = CircuitBreaker(
            failure_threshold=2,
            name="TestBreaker"
        )

        # Trigger OPEN state
        mock_func = Mock(side_effect=Exception("Failure"))
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(mock_func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 2

        # Manual reset
        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0

    def test_reset_from_half_open(self):
        """Test reset works from HALF_OPEN state"""
        breaker = CircuitBreaker(
            failure_threshold=2,
            timeout=0.1,
            name="TestBreaker"
        )

        # Get to HALF_OPEN
        mock_func = Mock(side_effect=Exception("Failure"))
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(mock_func)

        time.sleep(0.15)

        mock_func.side_effect = None
        mock_func.return_value = "success"
        breaker.call(mock_func)

        assert breaker.state == CircuitState.HALF_OPEN

        # Reset
        breaker.reset()

        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerEdgeCases:
    """Test edge cases and error conditions"""

    def test_function_with_return_value(self):
        """Test function return values are preserved"""
        breaker = CircuitBreaker(name="TestBreaker")

        def func(x, y):
            return x + y

        result = breaker.call(func, 10, 20)
        assert result == 30

    def test_function_with_kwargs(self):
        """Test kwargs are properly passed"""
        breaker = CircuitBreaker(name="TestBreaker")

        def func(a, b=5, c=10):
            return a + b + c

        result = breaker.call(func, 1, b=2, c=3)
        assert result == 6

    def test_exception_details_preserved(self):
        """Test original exception is preserved"""
        breaker = CircuitBreaker(failure_threshold=5, name="TestBreaker")

        class CustomException(Exception):
            pass

        mock_func = Mock(side_effect=CustomException("Custom error"))

        with pytest.raises(CustomException, match="Custom error"):
            breaker.call(mock_func)

    def test_zero_timeout(self):
        """Test circuit breaker with zero timeout"""
        breaker = CircuitBreaker(
            failure_threshold=2,
            timeout=0.0,  # Immediate retry
            name="TestBreaker"
        )

        # Trigger OPEN
        mock_func = Mock(side_effect=Exception("Failure"))
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(mock_func)

        # Immediately should transition to HALF_OPEN
        mock_func.side_effect = None
        mock_func.return_value = "success"

        result = breaker.call(mock_func)
        assert result == "success"
        assert breaker.state == CircuitState.HALF_OPEN


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
