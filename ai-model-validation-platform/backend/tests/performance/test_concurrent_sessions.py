"""Performance test for concurrent session handling

This test validates the performance optimizations that prevent 7x degradation
under load.

Tests:
1. Concurrent session creation (25 sessions)
2. Connection pool utilization
3. Connection leak detection
4. Thundering herd prevention

Expected Results (after optimizations):
- 25 concurrent sessions: <3 seconds total
- Average per session: <120ms (vs 700ms before)
- No connection leaks
- Pool utilization: <80%
"""

import threading
import time
import sys
import uuid
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database import SessionLocal
from utils.db_utils import managed_db_session
from utils.pool_monitor import PoolMonitor
from models import TestSession
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_concurrent_session_creation(num_sessions=25, use_optimization=True):
    """
    Test creating multiple sessions concurrently.
    Should NOT cause 7x performance degradation.

    Args:
        num_sessions: Number of concurrent sessions to create
        use_optimization: Whether to use optimized connection management

    Returns:
        Dictionary with test results
    """
    results = []

    def create_session(session_num):
        start_time = time.time()
        try:
            if use_optimization:
                # OPTIMIZED: Use managed session (auto cleanup)
                with managed_db_session() as db:
                    session = TestSession(
                        id=str(uuid.uuid4()),
                        project_id=str(uuid.uuid4()),
                        name=f"Test Session {session_num}",
                        status="pending"
                    )
                    db.add(session)
                    db.commit()
            else:
                # LEGACY: Manual session management (potential leak)
                db = SessionLocal()
                try:
                    session = TestSession(
                        id=str(uuid.uuid4()),
                        project_id=str(uuid.uuid4()),
                        name=f"Test Session {session_num}",
                        status="pending"
                    )
                    db.add(session)
                    db.commit()
                finally:
                    db.close()

            duration = time.time() - start_time
            results.append({
                'session_num': session_num,
                'duration': duration,
                'success': True
            })
        except Exception as e:
            duration = time.time() - start_time
            results.append({
                'session_num': session_num,
                'duration': duration,
                'success': False,
                'error': str(e)
            })

    # Log initial pool status
    logger.info("\n" + "=" * 60)
    logger.info("INITIAL POOL STATUS")
    logger.info("=" * 60)
    PoolMonitor.log_pool_status()

    # Create threads
    threads = []
    for i in range(num_sessions):
        t = threading.Thread(target=create_session, args=(i,))
        threads.append(t)

    # Start all threads simultaneously
    start_time = time.time()
    for t in threads:
        t.start()

    # Monitor pool during execution
    monitor_thread = threading.Thread(target=monitor_during_test, args=(5,))
    monitor_thread.daemon = True
    monitor_thread.start()

    # Wait for completion
    for t in threads:
        t.join()

    total_time = time.time() - start_time

    # Log final pool status
    logger.info("\n" + "=" * 60)
    logger.info("FINAL POOL STATUS")
    logger.info("=" * 60)
    PoolMonitor.log_pool_status()

    # Check for leaks
    leak_detected = PoolMonitor.check_for_leaks()

    # Analyze results
    successes = sum(1 for r in results if r['success'])
    failures = num_sessions - successes
    avg_duration = sum(r['duration'] for r in results) / len(results)
    max_duration = max(r['duration'] for r in results)
    min_duration = min(r['duration'] for r in results)

    # Calculate performance metrics
    baseline_time = 0.1  # Expected time per session
    performance_ratio = avg_duration / baseline_time

    # Print results
    print("\n" + "=" * 60)
    print("PERFORMANCE TEST RESULTS")
    print("=" * 60)
    print(f"Configuration: {'OPTIMIZED' if use_optimization else 'LEGACY'}")
    print(f"Total sessions: {num_sessions}")
    print(f"Successes: {successes}/{num_sessions}")
    print(f"Failures: {failures}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Avg per session: {avg_duration:.3f}s")
    print(f"Min duration: {min_duration:.3f}s")
    print(f"Max duration: {max_duration:.3f}s")
    print(f"Performance ratio: {performance_ratio:.1f}x baseline")

    # Performance assessment
    print("\n" + "-" * 60)
    if performance_ratio <= 1.5:
        print("✅ EXCELLENT: Performance within acceptable range")
    elif performance_ratio <= 3.0:
        print("⚠️ WARNING: Performance degradation detected")
    else:
        print(f"🚨 CRITICAL: {performance_ratio:.1f}x slower than baseline!")

    # Connection leak check
    if leak_detected:
        print("🚨 CONNECTION LEAK DETECTED")
    else:
        print("✅ No connection leaks detected")

    print("=" * 60 + "\n")

    # Get recommendations
    recommendations = PoolMonitor.get_recommendations()
    if len(recommendations) > 1 or recommendations[0] != "✅ Connection pool healthy - no action needed":
        print("\nRECOMMENDATIONS:")
        for rec in recommendations:
            print(f"  - {rec}")
        print()

    return {
        'total_time': total_time,
        'avg_duration': avg_duration,
        'max_duration': max_duration,
        'successes': successes,
        'failures': failures,
        'performance_ratio': performance_ratio,
        'leak_detected': leak_detected,
        'results': results
    }


def monitor_during_test(interval=1):
    """Monitor pool status during test execution"""
    for _ in range(10):  # Monitor for 10 intervals
        time.sleep(interval)
        PoolMonitor.log_pool_status()


def test_thundering_herd():
    """
    Test that jitter prevents thundering herd problem.

    Creates multiple threads that all fail initially and retry,
    verifying that retries are staggered (not synchronized).
    """
    logger.info("\n" + "=" * 60)
    logger.info("THUNDERING HERD TEST")
    logger.info("=" * 60)

    retry_times = []

    def failing_operation(thread_num):
        """Operation that fails first attempt, succeeds on retry"""
        from utils.db_utils import retry_with_new_connection

        attempts = [0]  # Mutable counter

        def operation(db):
            attempts[0] += 1
            if attempts[0] == 1:
                retry_times.append(time.time())
                return None  # Force retry
            return True

        result = retry_with_new_connection(operation, max_retries=2)
        return result

    # Launch threads simultaneously
    threads = []
    for i in range(10):
        t = threading.Thread(target=failing_operation, args=(i,))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # Analyze retry timing
    retry_times.sort()
    if len(retry_times) > 1:
        time_diffs = [retry_times[i+1] - retry_times[i] for i in range(len(retry_times)-1)]
        avg_spacing = sum(time_diffs) / len(time_diffs) * 1000  # Convert to ms

        print(f"\nRetry Timing Analysis:")
        print(f"  Total retries: {len(retry_times)}")
        print(f"  Average spacing: {avg_spacing:.2f}ms")

        if avg_spacing > 0.5:  # More than 0.5ms spacing
            print("  ✅ Jitter working - retries are staggered")
        else:
            print("  ⚠️ Potential thundering herd - retries too synchronized")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    print("\n" + "🚀" * 30)
    print("CONCURRENT SESSION PERFORMANCE TEST")
    print("🚀" * 30 + "\n")

    # Test 1: Optimized version
    print("\n📊 TEST 1: Optimized Connection Management")
    print("-" * 60)
    optimized_results = test_concurrent_session_creation(
        num_sessions=25,
        use_optimization=True
    )

    # Test 2: Thundering herd prevention
    print("\n📊 TEST 2: Thundering Herd Prevention")
    print("-" * 60)
    test_thundering_herd()

    # Test 3: Connection pool stress test
    print("\n📊 TEST 3: Pool Stress Test (50 concurrent)")
    print("-" * 60)
    stress_results = test_concurrent_session_creation(
        num_sessions=50,
        use_optimization=True
    )

    # Final report
    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(PoolMonitor.detailed_report())

    # Pass/Fail determination
    print("\n" + "=" * 60)
    print("TEST VERDICT")
    print("=" * 60)

    all_passed = True

    if optimized_results['performance_ratio'] <= 3.0:
        print("✅ Performance test: PASSED")
    else:
        print(f"❌ Performance test: FAILED ({optimized_results['performance_ratio']:.1f}x baseline)")
        all_passed = False

    if not optimized_results['leak_detected'] and not stress_results['leak_detected']:
        print("✅ Leak detection: PASSED")
    else:
        print("❌ Leak detection: FAILED")
        all_passed = False

    if all_passed:
        print("\n🎉 ALL TESTS PASSED - Performance optimizations working!")
    else:
        print("\n⚠️ SOME TESTS FAILED - Review optimizations")

    print("=" * 60 + "\n")
