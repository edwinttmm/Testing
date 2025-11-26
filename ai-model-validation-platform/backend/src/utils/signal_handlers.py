"""
Production-grade signal handlers for graceful shutdown.

Handles SIGTERM, SIGINT to ensure all resources are properly cleaned up
when the application receives shutdown signals.

Usage:
    from src.utils.signal_handlers import GracefulShutdown

    shutdown_handler = GracefulShutdown()
    shutdown_handler.register_cleanup(db.close)
    shutdown_handler.register_cleanup(labjack.stop_monitoring)
    shutdown_handler.install_handlers()
"""

import signal
import sys
import logging
import asyncio
from typing import Callable, List, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError


logger = logging.getLogger(__name__)


class GracefulShutdown:
    """
    Handles SIGTERM, SIGINT for graceful shutdown.

    This class ensures that all registered cleanup functions are called
    in LIFO order when the application receives shutdown signals. It includes
    timeout protection to prevent hanging on cleanup operations.

    Attributes:
        cleanup_callbacks: List of cleanup functions to execute on shutdown
        shutdown_initiated: Flag indicating if shutdown is in progress
        timeout_seconds: Maximum time allowed for cleanup operations
        logger: Logger instance for this class

    Example:
        shutdown_handler = GracefulShutdown(timeout_seconds=10)
        shutdown_handler.register_cleanup(database.dispose)
        shutdown_handler.register_cleanup(monitor.stop)
        shutdown_handler.install_handlers()
    """

    def __init__(self, timeout_seconds: int = 10):
        """
        Initialize graceful shutdown handler.

        Args:
            timeout_seconds: Maximum time to allow for cleanup operations (default: 10)
        """
        self.cleanup_callbacks: List[Callable] = []
        self.shutdown_initiated: bool = False
        self.timeout_seconds: int = timeout_seconds
        self.logger = logging.getLogger(__name__)
        self._executor = ThreadPoolExecutor(max_workers=1)

    def register_cleanup(self, callback: Callable) -> None:
        """
        Register cleanup function to call on shutdown.

        Cleanup functions are called in LIFO (Last In, First Out) order
        to ensure dependencies are cleaned up in reverse order of creation.

        Args:
            callback: Function to call during shutdown (must be callable)

        Raises:
            TypeError: If callback is not callable

        Example:
            shutdown_handler.register_cleanup(lambda: db_engine.dispose())
            shutdown_handler.register_cleanup(cleanup_temp_files)
        """
        if not callable(callback):
            raise TypeError(f"Callback must be callable, got {type(callback)}")

        self.cleanup_callbacks.append(callback)
        self.logger.debug(f"Registered cleanup callback: {callback.__name__ if hasattr(callback, '__name__') else 'lambda'}")

    def install_handlers(self) -> None:
        """
        Install signal handlers for SIGTERM, SIGINT.

        This should be called after all cleanup callbacks are registered.
        Signal handlers will be installed for:
        - SIGTERM: Graceful termination signal
        - SIGINT: Interrupt signal (Ctrl+C)

        Example:
            shutdown_handler.install_handlers()
        """
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        self.logger.info("Signal handlers installed for SIGTERM and SIGINT")

    def _signal_handler(self, signum: int, frame) -> None:
        """
        Handle shutdown signals.

        This method is called when SIGTERM or SIGINT is received.
        It executes all registered cleanup callbacks in reverse order
        with timeout protection.

        Args:
            signum: Signal number received
            frame: Current stack frame (unused)
        """
        if self.shutdown_initiated:
            self.logger.warning("Shutdown already initiated, ignoring duplicate signal")
            return

        self.shutdown_initiated = True
        signal_name = signal.Signals(signum).name
        self.logger.info(f"Received {signal_name}, initiating graceful shutdown...")

        # Execute cleanup callbacks in reverse order (LIFO)
        total_callbacks = len(self.cleanup_callbacks)
        success_count = 0
        failure_count = 0

        for idx, callback in enumerate(reversed(self.cleanup_callbacks), 1):
            callback_name = callback.__name__ if hasattr(callback, '__name__') else 'lambda'
            self.logger.info(f"Executing cleanup {idx}/{total_callbacks}: {callback_name}")

            try:
                # Execute with timeout protection
                future = self._executor.submit(callback)
                future.result(timeout=self.timeout_seconds)
                success_count += 1
                self.logger.debug(f"Cleanup callback '{callback_name}' completed successfully")

            except FutureTimeoutError:
                failure_count += 1
                self.logger.error(
                    f"Cleanup callback '{callback_name}' timed out after {self.timeout_seconds}s"
                )

            except Exception as e:
                failure_count += 1
                self.logger.error(
                    f"Cleanup callback '{callback_name}' failed: {e}",
                    exc_info=True
                )

        # Log final cleanup summary
        self.logger.info(
            f"Graceful shutdown complete: {success_count} successful, "
            f"{failure_count} failed out of {total_callbacks} callbacks"
        )

        # Exit with appropriate code
        exit_code = 0 if failure_count == 0 else 1
        self.logger.info(f"Exiting with code {exit_code}")
        sys.exit(exit_code)

    def __del__(self):
        """Cleanup executor on object destruction."""
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass


# Global instance for easy access
_global_shutdown_handler: Optional[GracefulShutdown] = None


def get_shutdown_handler() -> GracefulShutdown:
    """
    Get or create global shutdown handler instance.

    Returns:
        GracefulShutdown: Global shutdown handler singleton

    Example:
        handler = get_shutdown_handler()
        handler.register_cleanup(my_cleanup_function)
    """
    global _global_shutdown_handler
    if _global_shutdown_handler is None:
        _global_shutdown_handler = GracefulShutdown()
    return _global_shutdown_handler
