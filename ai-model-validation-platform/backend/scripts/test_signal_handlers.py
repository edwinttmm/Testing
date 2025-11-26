#!/usr/bin/env python3
"""
Quick test script for signal handlers.
Simulates basic functionality without requiring pytest.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.signal_handlers import GracefulShutdown, get_shutdown_handler
import signal
from unittest.mock import Mock, patch


def test_initialization():
    """Test handler initialization."""
    print("Testing initialization...")
    handler = GracefulShutdown()
    assert handler.shutdown_initiated is False
    assert handler.timeout_seconds == 10
    assert len(handler.cleanup_callbacks) == 0
    print("✓ Initialization test passed")


def test_register_cleanup():
    """Test registering cleanup callbacks."""
    print("Testing callback registration...")
    handler = GracefulShutdown()
    mock_callback = Mock()

    handler.register_cleanup(mock_callback)
    assert len(handler.cleanup_callbacks) == 1

    # Test invalid callback
    try:
        handler.register_cleanup("not a function")
        assert False, "Should have raised TypeError"
    except TypeError:
        pass

    print("✓ Callback registration test passed")


def test_cleanup_order():
    """Test LIFO cleanup order."""
    print("Testing LIFO cleanup order...")
    handler = GracefulShutdown()
    execution_order = []

    def callback1():
        execution_order.append(1)

    def callback2():
        execution_order.append(2)

    def callback3():
        execution_order.append(3)

    handler.register_cleanup(callback1)
    handler.register_cleanup(callback2)
    handler.register_cleanup(callback3)

    # Simulate signal
    with patch('sys.exit'):
        handler._signal_handler(signal.SIGTERM, None)

    # Should execute in reverse order: 3, 2, 1
    assert execution_order == [3, 2, 1], f"Expected [3, 2, 1], got {execution_order}"
    print("✓ LIFO cleanup order test passed")


def test_signal_execution():
    """Test that callbacks are executed on signal."""
    print("Testing signal execution...")
    handler = GracefulShutdown()
    mock_callback = Mock()

    handler.register_cleanup(mock_callback)

    with patch('sys.exit'):
        handler._signal_handler(signal.SIGTERM, None)

    mock_callback.assert_called_once()
    assert handler.shutdown_initiated is True
    print("✓ Signal execution test passed")


def test_duplicate_signal_ignored():
    """Test that duplicate signals are ignored."""
    print("Testing duplicate signal handling...")
    handler = GracefulShutdown()
    mock_callback = Mock()

    handler.register_cleanup(mock_callback)

    # First signal
    with patch('sys.exit'):
        handler._signal_handler(signal.SIGTERM, None)

    # Reset mock
    mock_callback.reset_mock()

    # Second signal should be ignored
    with patch('sys.exit'):
        handler._signal_handler(signal.SIGTERM, None)

    mock_callback.assert_not_called()
    print("✓ Duplicate signal handling test passed")


def test_cleanup_failure_handling():
    """Test that cleanup continues even if a callback fails."""
    print("Testing cleanup failure handling...")
    handler = GracefulShutdown()

    mock_success1 = Mock()
    mock_failure = Mock(side_effect=Exception("Cleanup failed"))
    mock_success2 = Mock()

    handler.register_cleanup(mock_success1)
    handler.register_cleanup(mock_failure)
    handler.register_cleanup(mock_success2)

    with patch('sys.exit') as mock_exit:
        handler._signal_handler(signal.SIGTERM, None)

    # All callbacks should be attempted
    mock_success1.assert_called_once()
    mock_failure.assert_called_once()
    mock_success2.assert_called_once()

    # Should exit with error code
    mock_exit.assert_called_once_with(1)
    print("✓ Cleanup failure handling test passed")


def test_singleton_pattern():
    """Test global shutdown handler singleton."""
    print("Testing singleton pattern...")
    handler1 = get_shutdown_handler()
    handler2 = get_shutdown_handler()
    assert handler1 is handler2
    print("✓ Singleton pattern test passed")


def test_lambda_callbacks():
    """Test that lambda functions work as cleanup callbacks."""
    print("Testing lambda callbacks...")
    handler = GracefulShutdown()
    result = []

    handler.register_cleanup(lambda: result.append("cleaned"))

    with patch('sys.exit'):
        handler._signal_handler(signal.SIGTERM, None)

    assert result == ["cleaned"]
    print("✓ Lambda callback test passed")


def test_integration_scenario():
    """Test simulated database and LabJack cleanup."""
    print("Testing integration scenario...")
    handler = GracefulShutdown()

    # Mock database engine
    mock_db_engine = Mock()
    mock_db_engine.dispose = Mock()

    # Mock LabJack monitor
    mock_monitor = Mock()
    mock_monitor.cleanup = Mock()

    handler.register_cleanup(lambda: mock_db_engine.dispose())
    handler.register_cleanup(lambda: mock_monitor.cleanup())

    with patch('sys.exit'):
        handler._signal_handler(signal.SIGTERM, None)

    mock_db_engine.dispose.assert_called_once()
    mock_monitor.cleanup.assert_called_once()
    print("✓ Integration scenario test passed")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Signal Handlers Test Suite")
    print("=" * 60)

    tests = [
        test_initialization,
        test_register_cleanup,
        test_cleanup_order,
        test_signal_execution,
        test_duplicate_signal_ignored,
        test_cleanup_failure_handling,
        test_singleton_pattern,
        test_lambda_callbacks,
        test_integration_scenario,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
