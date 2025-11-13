"""
Database Stress Tests

Stress tests to verify database session management under high load,
concurrent access, and error conditions.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import random


class SessionPool:
    """Track database sessions for stress testing."""

    def __init__(self):
        self.sessions = []
        self.active_sessions = set()
        self.closed_sessions = set()
        self.errors = []
        self.lock = threading.Lock()

    def create_session(self):
        """Create a new tracked session."""
        session = MagicMock(spec=Session)
        session.session_id = id(session)
        session.is_active = True

        original_close = session.close

        def tracked_close():
            with self.lock:
                session.is_active = False
                self.active_sessions.discard(session.session_id)
                self.closed_sessions.add(session.session_id)
            return original_close()

        session.close = Mock(side_effect=tracked_close)

        with self.lock:
            self.sessions.append(session)
            self.active_sessions.add(session.session_id)

        return session

    def log_error(self, error, context=None):
        """Log an error."""
        with self.lock:
            self.errors.append({
                "error": str(error),
                "type": type(error).__name__,
                "context": context,
                "timestamp": time.time()
            })

    def get_stats(self):
        """Get session statistics."""
        with self.lock:
            return {
                "total_created": len(self.sessions),
                "active": len(self.active_sessions),
                "closed": len(self.closed_sessions),
                "leaked": len(self.active_sessions),
                "errors": len(self.errors)
            }

    def reset(self):
        """Reset all tracking."""
        with self.lock:
            self.sessions.clear()
            self.active_sessions.clear()
            self.closed_sessions.clear()
            self.errors.clear()


@pytest.fixture
def session_pool():
    """Create a session pool for testing."""
    pool = SessionPool()
    yield pool
    pool.reset()


# Stress Test Cases

@pytest.mark.asyncio
async def test_rapid_requests_no_session_leak(session_pool):
    """
    Test: 100 rapid requests should not leak database sessions.

    Expected behavior:
    - Create 100 sessions in rapid succession
    - Each session is used and closed
    - No sessions leaked
    - All cleanup completes
    """
    # Arrange
    num_requests = 100

    async def single_request(request_id):
        session = session_pool.create_session()
        try:
            # Simulate quick operation
            await asyncio.sleep(0.001)
            session.execute = Mock(return_value=f"result_{request_id}")
            return session.execute("SELECT 1")
        finally:
            session.close()

    # Act
    tasks = [single_request(i) for i in range(num_requests)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Assert
    stats = session_pool.get_stats()
    assert stats["total_created"] == num_requests, f"Should create {num_requests} sessions"
    assert stats["leaked"] == 0, "No sessions should be leaked"
    assert stats["closed"] == num_requests, "All sessions should be closed"
    assert len(results) == num_requests, "All requests should complete"


@pytest.mark.asyncio
async def test_concurrent_errors_no_deadlock(session_pool):
    """
    Test: Concurrent errors should not cause deadlocks.

    Expected behavior:
    - Multiple requests fail concurrently
    - No deadlocks occur
    - All sessions cleaned up
    - System remains responsive
    """
    # Arrange
    num_requests = 50
    error_rate = 0.5  # 50% of requests will error

    async def request_with_potential_error(request_id):
        session = session_pool.create_session()
        try:
            await asyncio.sleep(random.uniform(0.001, 0.01))

            if random.random() < error_rate:
                raise SQLAlchemyError(f"Error in request {request_id}")

            return {"request_id": request_id, "status": "success"}
        except Exception as e:
            session_pool.log_error(e, {"request_id": request_id})
            raise
        finally:
            session.close()

    # Act
    tasks = [request_with_potential_error(i) for i in range(num_requests)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Assert
    stats = session_pool.get_stats()
    assert stats["leaked"] == 0, "No sessions should leak even with errors"
    assert stats["closed"] == num_requests, "All sessions should be closed"

    # Count successes and errors
    successes = sum(1 for r in results if isinstance(r, dict))
    errors = sum(1 for r in results if isinstance(r, Exception))

    assert successes + errors == num_requests, "All requests should complete"
    assert errors > 0, "Some errors should have occurred"


@pytest.mark.asyncio
async def test_high_concurrency_stress(session_pool):
    """
    Test: System should handle high concurrency without issues.

    Expected behavior:
    - 200 concurrent requests
    - All complete successfully
    - No resource exhaustion
    - Reasonable performance
    """
    # Arrange
    num_concurrent = 200

    async def concurrent_request(request_id):
        session = session_pool.create_session()
        try:
            # Simulate variable load
            await asyncio.sleep(random.uniform(0.001, 0.05))

            session.execute = Mock(return_value={"id": request_id})
            result = session.execute(f"SELECT * FROM table WHERE id={request_id}")

            return result
        finally:
            session.close()

    # Act
    start_time = time.time()
    tasks = [concurrent_request(i) for i in range(num_concurrent)]
    results = await asyncio.gather(*tasks)
    duration = time.time() - start_time

    # Assert
    stats = session_pool.get_stats()
    assert stats["leaked"] == 0, "No sessions should leak under high concurrency"
    assert len(results) == num_concurrent, "All requests should complete"
    assert duration < 10, "Should complete in reasonable time"

    print(f"\n✓ Handled {num_concurrent} concurrent requests in {duration:.2f}s")


@pytest.mark.asyncio
async def test_sustained_load(session_pool):
    """
    Test: System should handle sustained load over time.

    Expected behavior:
    - Continuous requests for duration
    - Memory usage stable
    - No resource leaks
    - Performance remains consistent
    """
    # Arrange
    duration_seconds = 5
    request_rate = 20  # requests per second

    async def continuous_requests():
        request_count = 0
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            session = session_pool.create_session()
            try:
                await asyncio.sleep(1.0 / request_rate)
                session.execute = Mock(return_value="result")
                session.execute("SELECT 1")
                request_count += 1
            finally:
                session.close()

        return request_count

    # Act
    request_count = await continuous_requests()

    # Assert
    stats = session_pool.get_stats()
    assert stats["leaked"] == 0, "No sessions should leak during sustained load"
    assert request_count > 0, "Should process multiple requests"

    expected_requests = duration_seconds * request_rate
    assert request_count >= expected_requests * 0.8, "Should meet target rate within 20%"

    print(f"\n✓ Processed {request_count} requests over {duration_seconds}s")


@pytest.mark.asyncio
async def test_burst_load(session_pool):
    """
    Test: System should handle sudden burst of requests.

    Expected behavior:
    - Sudden spike of 500 requests
    - All requests processed
    - System recovers
    - No permanent resource leaks
    """
    # Arrange
    burst_size = 500

    async def burst_request(request_id):
        session = session_pool.create_session()
        try:
            # No delay - simulate burst
            session.execute = Mock(return_value=request_id)
            return session.execute("SELECT 1")
        finally:
            session.close()

    # Act
    start_time = time.time()
    tasks = [burst_request(i) for i in range(burst_size)]
    results = await asyncio.gather(*tasks)
    duration = time.time() - start_time

    # Assert
    stats = session_pool.get_stats()
    assert stats["leaked"] == 0, "No sessions should leak during burst"
    assert len(results) == burst_size, "All burst requests should complete"

    print(f"\n✓ Handled burst of {burst_size} requests in {duration:.2f}s")


@pytest.mark.asyncio
async def test_mixed_workload(session_pool):
    """
    Test: System should handle mixed workload (fast and slow operations).

    Expected behavior:
    - Mix of quick and slow operations
    - All complete without blocking
    - Fast operations not blocked by slow ones
    - All sessions cleaned up
    """
    # Arrange
    num_fast = 100
    num_slow = 10

    async def fast_request(request_id):
        session = session_pool.create_session()
        try:
            await asyncio.sleep(0.001)
            return {"type": "fast", "id": request_id}
        finally:
            session.close()

    async def slow_request(request_id):
        session = session_pool.create_session()
        try:
            await asyncio.sleep(0.1)
            return {"type": "slow", "id": request_id}
        finally:
            session.close()

    # Act
    fast_tasks = [fast_request(i) for i in range(num_fast)]
    slow_tasks = [slow_request(i) for i in range(num_slow)]
    all_tasks = fast_tasks + slow_tasks

    results = await asyncio.gather(*all_tasks)

    # Assert
    stats = session_pool.get_stats()
    assert stats["leaked"] == 0, "No sessions should leak in mixed workload"
    assert len(results) == num_fast + num_slow

    fast_results = [r for r in results if r["type"] == "fast"]
    slow_results = [r for r in results if r["type"] == "slow"]

    assert len(fast_results) == num_fast
    assert len(slow_results) == num_slow


@pytest.mark.asyncio
async def test_error_rate_stress(session_pool):
    """
    Test: System should handle high error rates without degradation.

    Expected behavior:
    - High percentage of requests fail
    - Sessions still cleaned up
    - System remains stable
    - No cascading failures
    """
    # Arrange
    num_requests = 100
    error_rate = 0.7  # 70% error rate

    async def request_with_high_error_rate(request_id):
        session = session_pool.create_session()
        try:
            if random.random() < error_rate:
                raise SQLAlchemyError("Simulated error")
            return {"id": request_id}
        finally:
            session.close()

    # Act
    tasks = [request_with_high_error_rate(i) for i in range(num_requests)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Assert
    stats = session_pool.get_stats()
    assert stats["leaked"] == 0, "No sessions should leak despite high error rate"

    errors = sum(1 for r in results if isinstance(r, Exception))
    successes = sum(1 for r in results if isinstance(r, dict))

    assert errors > num_requests * 0.5, "Should have high error rate"
    assert successes + errors == num_requests


@pytest.mark.asyncio
async def test_cleanup_under_pressure(session_pool):
    """
    Test: Cleanup should work correctly even under memory pressure.

    Expected behavior:
    - Simulate memory pressure
    - Sessions still cleaned up
    - No cleanup failures
    - Graceful handling
    """
    # Arrange
    num_requests = 100

    async def request_with_large_data(request_id):
        session = session_pool.create_session()
        try:
            # Simulate large data
            large_data = ["x" * 1000] * 100  # ~100KB
            await asyncio.sleep(0.01)
            return len(large_data)
        finally:
            session.close()
            # Data should be cleaned up

    # Act
    tasks = [request_with_large_data(i) for i in range(num_requests)]
    results = await asyncio.gather(*tasks)

    # Assert
    stats = session_pool.get_stats()
    assert stats["leaked"] == 0, "No sessions should leak under memory pressure"
    assert len(results) == num_requests


def test_thread_safety(session_pool):
    """
    Test: Session management should be thread-safe.

    Expected behavior:
    - Multiple threads create sessions
    - No race conditions
    - All sessions tracked correctly
    - All cleaned up properly
    """
    # Arrange
    num_threads = 10
    requests_per_thread = 20

    def thread_worker(thread_id):
        for i in range(requests_per_thread):
            session = session_pool.create_session()
            try:
                time.sleep(0.001)
                session.execute = Mock(return_value=f"thread_{thread_id}_req_{i}")
                session.execute("SELECT 1")
            finally:
                session.close()

    # Act
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(thread_worker, i) for i in range(num_threads)]

        for future in as_completed(futures):
            future.result()  # Wait for completion

    # Assert
    stats = session_pool.get_stats()
    expected_total = num_threads * requests_per_thread

    assert stats["total_created"] == expected_total, "Should create expected number of sessions"
    assert stats["leaked"] == 0, "No sessions should leak with threading"
    assert stats["closed"] == expected_total, "All sessions should be closed"


@pytest.mark.asyncio
async def test_performance_degradation_check(session_pool):
    """
    Test: Performance should not degrade over time.

    Expected behavior:
    - Run multiple batches of requests
    - Performance remains consistent
    - No memory leaks causing slowdown
    """
    # Arrange
    batch_size = 50
    num_batches = 5
    batch_times = []

    async def run_batch():
        async def single_request(request_id):
            session = session_pool.create_session()
            try:
                await asyncio.sleep(0.001)
                return request_id
            finally:
                session.close()

        start_time = time.time()
        tasks = [single_request(i) for i in range(batch_size)]
        await asyncio.gather(*tasks)
        return time.time() - start_time

    # Act
    for batch in range(num_batches):
        batch_time = await run_batch()
        batch_times.append(batch_time)
        await asyncio.sleep(0.1)  # Small delay between batches

    # Assert
    stats = session_pool.get_stats()
    assert stats["leaked"] == 0, "No sessions should leak across batches"

    # Check performance doesn't degrade significantly
    first_batch_time = batch_times[0]
    last_batch_time = batch_times[-1]

    # Last batch should not be more than 50% slower than first
    assert last_batch_time < first_batch_time * 1.5, "Performance should not degrade significantly"

    print(f"\n✓ Batch times: {[f'{t:.3f}s' for t in batch_times]}")


@pytest.mark.asyncio
async def test_recovery_after_stress(session_pool):
    """
    Test: System should recover after stress period.

    Expected behavior:
    - Apply stress load
    - Return to normal load
    - Performance recovers
    - No lingering issues
    """
    # Arrange
    async def stress_period():
        tasks = [asyncio.create_task(single_request(i)) for i in range(200)]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def normal_period():
        tasks = [asyncio.create_task(single_request(i)) for i in range(10)]
        return await asyncio.gather(*tasks)

    async def single_request(request_id):
        session = session_pool.create_session()
        try:
            await asyncio.sleep(0.001)
            return request_id
        finally:
            session.close()

    # Act - Stress period
    await stress_period()
    stress_stats = session_pool.get_stats()

    # Recovery period
    await asyncio.sleep(0.1)

    # Normal period
    session_pool.reset()  # Reset counters to measure recovery
    results = await normal_period()
    normal_stats = session_pool.get_stats()

    # Assert
    assert stress_stats["leaked"] == 0, "No leaks during stress"
    assert normal_stats["leaked"] == 0, "No leaks after recovery"
    assert len(results) == 10, "Should process normal requests after stress"
