"""
Unit tests for signal handlers module.

Tests graceful shutdown functionality including:
- SIGTERM handling
- SIGINT handling
- Cleanup callback execution
- LIFO cleanup order
- Timeout handling
- Error handling
"""

import sys
import pytest
import signal
import time
import os
from unittest.mock import Mock, patch, call
from src.utils.signal_handlers import GracefulShutdown, get_shutdown_handler


class TestGracefulShutdown:
    """Test suite for GracefulShutdown class."""

    def test_initialization(self):
        """Test handler initialization with default timeout."""
        handler = GracefulShutdown()
        assert handler.shutdown_initiated is False
        assert handler.timeout_seconds == 10
        assert len(handler.cleanup_callbacks) == 0

    def test_initialization_custom_timeout(self):
        """Test handler initialization with custom timeout."""
        handler = GracefulShutdown(timeout_seconds=30)
        assert handler.timeout_seconds == 30

    def test_register_cleanup_valid_callback(self):
        """Test registering a valid cleanup callback."""
        handler = GracefulShutdown()
        mock_callback = Mock()

        handler.register_cleanup(mock_callback)

        assert len(handler.cleanup_callbacks) == 1
        assert handler.cleanup_callbacks[0] == mock_callback

    def test_register_cleanup_multiple_callbacks(self):
        """Test registering multiple cleanup callbacks."""
        handler = GracefulShutdown()
        mock1 = Mock()
        mock2 = Mock()
        mock3 = Mock()

        handler.register_cleanup(mock1)
        handler.register_cleanup(mock2)
        handler.register_cleanup(mock3)

        assert len(handler.cleanup_callbacks) == 3
        assert handler.cleanup_callbacks == [mock1, mock2, mock3]

    def test_register_cleanup_invalid_callback(self):
        """Test that registering non-callable raises TypeError."""
        handler = GracefulShutdown()

        with pytest.raises(TypeError, match="Callback must be callable"):
            handler.register_cleanup("not a function")

        with pytest.raises(TypeError, match="Callback must be callable"):
            handler.register_cleanup(123)

    def test_install_handlers(self):
        """Test signal handler installation."""
        handler = GracefulShutdown()

        with patch('signal.signal') as mock_signal:
            handler.install_handlers()

            # Verify signal handlers were installed
            assert mock_signal.call_count == 2
            calls = mock_signal.call_args_list
            assert any(call[0][0] == signal.SIGTERM for call in calls)
            assert any(call[0][0] == signal.SIGINT for call in calls)

    def test_cleanup_execution_order_lifo(self):
        """Test that cleanup callbacks are executed in LIFO order."""
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
        assert execution_order == [3, 2, 1]

    def test_cleanup_callbacks_executed_on_sigterm(self):
        """Test that cleanup callbacks are executed when SIGTERM is received."""
        handler = GracefulShutdown()
        mock_callback = Mock()

        handler.register_cleanup(mock_callback)

        # Simulate SIGTERM
        with patch('sys.exit'):
            handler._signal_handler(signal.SIGTERM, None)

        mock_callback.assert_called_once()
        assert handler.shutdown_initiated is True

    def test_cleanup_callbacks_executed_on_sigint(self):
        """Test that cleanup callbacks are executed when SIGINT is received."""
        handler = GracefulShutdown()
        mock_callback = Mock()

        handler.register_cleanup(mock_callback)

        # Simulate SIGINT
        with patch('sys.exit'):
            handler._signal_handler(signal.SIGINT, None)

        mock_callback.assert_called_once()
        assert handler.shutdown_initiated is True

    def test_duplicate_signal_ignored(self):
        """Test that duplicate signals are ignored during shutdown."""
        handler = GracefulShutdown()
        mock_callback = Mock()

        handler.register_cleanup(mock_callback)

        # First signal
        with patch('sys.exit'):
            handler._signal_handler(signal.SIGTERM, None)

        # Reset mock to verify it's not called again
        mock_callback.reset_mock()

        # Second signal should be ignored
        with patch('sys.exit'):
            handler._signal_handler(signal.SIGTERM, None)

        mock_callback.assert_not_called()

    def test_cleanup_failure_handling(self):
        """Test that cleanup continues even if a callback fails."""
        handler = GracefulShutdown()

        mock_success1 = Mock()
        mock_failure = Mock(side_effect=Exception("Cleanup failed"))
        mock_success2 = Mock()

        handler.register_cleanup(mock_success1)
        handler.register_cleanup(mock_failure)
        handler.register_cleanup(mock_success2)

        # Simulate signal
        with patch('sys.exit') as mock_exit:
            handler._signal_handler(signal.SIGTERM, None)

        # All callbacks should be attempted
        mock_success1.assert_called_once()
        mock_failure.assert_called_once()
        mock_success2.assert_called_once()

        # Should exit with error code due to failure
        mock_exit.assert_called_once_with(1)

    def test_cleanup_timeout_handling(self):
        """Test that cleanup has timeout protection."""
        handler = GracefulShutdown(timeout_seconds=1)

        def slow_callback():
            time.sleep(5)  # Longer than timeout

        handler.register_cleanup(slow_callback)

        # Should timeout and exit with error code
        with patch('sys.exit') as mock_exit:
            handler._signal_handler(signal.SIGTERM, None)

        mock_exit.assert_called_once_with(1)

    def test_successful_cleanup_exit_code(self):
        """Test that successful cleanup exits with code 0."""
        handler = GracefulShutdown()
        mock_callback = Mock()

        handler.register_cleanup(mock_callback)

        with patch('sys.exit') as mock_exit:
            handler._signal_handler(signal.SIGTERM, None)

        mock_exit.assert_called_once_with(0)

    def test_failed_cleanup_exit_code(self):
        """Test that failed cleanup exits with code 1."""
        handler = GracefulShutdown()
        mock_callback = Mock(side_effect=Exception("Failed"))

        handler.register_cleanup(mock_callback)

        with patch('sys.exit') as mock_exit:
            handler._signal_handler(signal.SIGTERM, None)

        mock_exit.assert_called_once_with(1)

    def test_lambda_callbacks_supported(self):
        """Test that lambda functions work as cleanup callbacks."""
        handler = GracefulShutdown()
        result = []

        handler.register_cleanup(lambda: result.append("cleaned"))

        with patch('sys.exit'):
            handler._signal_handler(signal.SIGTERM, None)

        assert result == ["cleaned"]


class TestGetShutdownHandler:
    """Test suite for global shutdown handler singleton."""

    def test_get_shutdown_handler_returns_instance(self):
        """Test that get_shutdown_handler returns a valid instance."""
        handler = get_shutdown_handler()
        assert isinstance(handler, GracefulShutdown)

    def test_get_shutdown_handler_singleton(self):
        """Test that get_shutdown_handler returns same instance."""
        handler1 = get_shutdown_handler()
        handler2 = get_shutdown_handler()
        assert handler1 is handler2


class TestIntegrationScenarios:
    """Integration tests for real-world shutdown scenarios."""

    def test_database_cleanup_scenario(self):
        """Test simulated database cleanup on shutdown."""
        handler = GracefulShutdown()

        # Mock database engine
        mock_db_engine = Mock()
        mock_db_engine.dispose = Mock()

        handler.register_cleanup(lambda: mock_db_engine.dispose())

        with patch('sys.exit'):
            handler._signal_handler(signal.SIGTERM, None)

        mock_db_engine.dispose.assert_called_once()

    def test_labjack_cleanup_scenario(self):
        """Test simulated LabJack monitor cleanup on shutdown."""
        handler = GracefulShutdown()

        # Mock LabJack monitor
        mock_monitor = Mock()
        mock_monitor.stop_monitoring = Mock()
        mock_monitor.cleanup = Mock()

        handler.register_cleanup(lambda: mock_monitor.stop_monitoring())
        handler.register_cleanup(lambda: mock_monitor.cleanup())

        with patch('sys.exit'):
            handler._signal_handler(signal.SIGTERM, None)

        mock_monitor.stop_monitoring.assert_called_once()
        mock_monitor.cleanup.assert_called_once()

    def test_multiple_resource_cleanup_scenario(self):
        """Test cleanup of multiple resources in correct order."""
        handler = GracefulShutdown()

        mock_labjack = Mock()
        mock_database = Mock()
        mock_cache = Mock()

        # Register in order: labjack, database, cache
        handler.register_cleanup(lambda: mock_labjack.cleanup())
        handler.register_cleanup(lambda: mock_database.dispose())
        handler.register_cleanup(lambda: mock_cache.clear())

        with patch('sys.exit'):
            handler._signal_handler(signal.SIGTERM, None)

        # All should be called
        mock_labjack.cleanup.assert_called_once()
        mock_database.dispose.assert_called_once()
        mock_cache.clear.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
