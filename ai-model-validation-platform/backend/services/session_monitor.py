"""
Session Monitor Service for Backend-Driven State Management

This service provides timeout monitoring and autonomous state management
to eliminate fragile frontend event dependencies.

Key Features:
- Background timeout monitoring for video lifecycle
- Automatic session failure on timeout
- Graceful degradation when frontend disconnects
- Comprehensive logging and error handling

Production Standards:
- No frontend dependency for critical state
- Robust error handling
- Database transaction safety
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Callable, Any
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    """Session lifecycle states"""
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TimeoutTask:
    """Represents a timeout monitoring task"""
    session_id: str
    video_id: Optional[str]
    timeout_ms: int
    created_at: float
    task: Optional[asyncio.Task] = None
    callback: Optional[Callable] = None


class SessionMonitor:
    """
    Background task monitoring session health.
    If no activity within timeout, mark as failed.

    This provides autonomous backend state management without
    relying on frontend events.
    """

    def __init__(self):
        """Initialize session monitor"""
        self._active_timeouts: Dict[str, TimeoutTask] = {}
        self._lock = asyncio.Lock()

        # Configuration
        self.default_video_start_timeout_ms = 30000  # 30 seconds
        self.default_video_end_timeout_ms = 60000    # 60 seconds
        self.default_session_timeout_ms = 600000     # 10 minutes

        logger.info("SessionMonitor initialized")

    async def monitor_session_lifecycle(
        self,
        session_id: str,
        timeout_ms: int = None,
        db_session: Session = None,
        failure_callback: Optional[Callable] = None
    ) -> bool:
        """
        Background task monitoring session health.
        If no activity within timeout, mark as failed.

        Args:
            session_id: Test session identifier
            timeout_ms: Timeout in milliseconds (default: 10 minutes)
            db_session: Database session for marking failure
            failure_callback: Optional callback when timeout occurs

        Returns:
            True if monitoring started successfully
        """
        if timeout_ms is None:
            timeout_ms = self.default_session_timeout_ms

        try:
            async with self._lock:
                # Check if already monitoring
                if session_id in self._active_timeouts:
                    logger.warning(f"Session {session_id} already has active timeout monitor")
                    return False

                # Create timeout task
                task = asyncio.create_task(
                    self._session_timeout_worker(
                        session_id,
                        timeout_ms,
                        db_session,
                        failure_callback
                    )
                )

                timeout_obj = TimeoutTask(
                    session_id=session_id,
                    video_id=None,
                    timeout_ms=timeout_ms,
                    created_at=time.time(),
                    task=task,
                    callback=failure_callback
                )

                self._active_timeouts[session_id] = timeout_obj

                logger.info(
                    f"Started session lifecycle monitoring - "
                    f"Session: {session_id}, Timeout: {timeout_ms}ms"
                )

                return True

        except Exception as e:
            logger.error(f"Failed to start session monitoring for {session_id}: {e}")
            return False

    async def monitor_video_start(
        self,
        session_id: str,
        video_id: str,
        timeout_ms: int = None,
        db_session: Session = None,
        failure_callback: Optional[Callable] = None
    ) -> bool:
        """
        Monitor video start event with timeout.
        If video doesn't start within timeout, mark session as failed.

        Args:
            session_id: Test session identifier
            video_id: Video identifier
            timeout_ms: Timeout in milliseconds (default: 30 seconds)
            db_session: Database session
            failure_callback: Optional callback when timeout occurs

        Returns:
            True if monitoring started successfully
        """
        if timeout_ms is None:
            timeout_ms = self.default_video_start_timeout_ms

        try:
            async with self._lock:
                monitor_key = f"{session_id}:video_start:{video_id}"

                # Check if already monitoring
                if monitor_key in self._active_timeouts:
                    logger.warning(f"Video start already monitored: {monitor_key}")
                    return False

                # Create timeout task
                task = asyncio.create_task(
                    self._video_start_timeout_worker(
                        session_id,
                        video_id,
                        timeout_ms,
                        db_session,
                        failure_callback
                    )
                )

                timeout_obj = TimeoutTask(
                    session_id=session_id,
                    video_id=video_id,
                    timeout_ms=timeout_ms,
                    created_at=time.time(),
                    task=task,
                    callback=failure_callback
                )

                self._active_timeouts[monitor_key] = timeout_obj

                logger.info(
                    f"Started video start monitoring - "
                    f"Session: {session_id}, Video: {video_id}, Timeout: {timeout_ms}ms"
                )

                return True

        except Exception as e:
            logger.error(f"Failed to start video start monitoring: {e}")
            return False

    async def cancel_timeout(self, session_id: str, video_id: Optional[str] = None) -> bool:
        """
        Cancel timeout monitoring (called when event successfully fires).

        Args:
            session_id: Test session identifier
            video_id: Optional video identifier for video-specific timeouts

        Returns:
            True if timeout was cancelled
        """
        try:
            async with self._lock:
                if video_id:
                    monitor_key = f"{session_id}:video_start:{video_id}"
                else:
                    monitor_key = session_id

                if monitor_key not in self._active_timeouts:
                    logger.debug(f"No active timeout to cancel: {monitor_key}")
                    return False

                timeout_obj = self._active_timeouts[monitor_key]

                # Cancel the async task
                if timeout_obj.task and not timeout_obj.task.done():
                    timeout_obj.task.cancel()
                    try:
                        await timeout_obj.task
                    except asyncio.CancelledError:
                        pass  # Expected

                # Remove from active timeouts
                del self._active_timeouts[monitor_key]

                logger.info(f"Cancelled timeout monitor: {monitor_key}")

                return True

        except Exception as e:
            logger.error(f"Failed to cancel timeout for {monitor_key}: {e}")
            return False

    async def _session_timeout_worker(
        self,
        session_id: str,
        timeout_ms: int,
        db_session: Optional[Session],
        failure_callback: Optional[Callable]
    ):
        """Background worker that sleeps until timeout, then marks session failed"""
        try:
            timeout_seconds = timeout_ms / 1000.0

            logger.debug(f"Session timeout worker started - waiting {timeout_seconds}s")

            # Wait for timeout
            await asyncio.sleep(timeout_seconds)

            # If we get here, timeout occurred (not cancelled)
            logger.error(
                f"Session timeout occurred - Session: {session_id}, "
                f"Timeout: {timeout_ms}ms"
            )

            # Mark session as failed in database
            if db_session:
                await self._mark_session_failed(
                    session_id,
                    f"Session timeout: No activity for {timeout_ms}ms",
                    db_session
                )

            # Execute callback if provided
            if failure_callback:
                try:
                    if asyncio.iscoroutinefunction(failure_callback):
                        await failure_callback(session_id, "session_timeout")
                    else:
                        failure_callback(session_id, "session_timeout")
                except Exception as cb_error:
                    logger.error(f"Error in failure callback: {cb_error}")

            # Emit WebSocket event (if socketio available)
            await self._emit_session_failed(
                session_id,
                "timeout",
                f"Session inactive for {timeout_ms}ms"
            )

        except asyncio.CancelledError:
            logger.debug(f"Session timeout cancelled for {session_id} (activity detected)")
            # This is expected when timeout is cancelled
            raise
        except Exception as e:
            logger.error(f"Error in session timeout worker: {e}")

    async def _video_start_timeout_worker(
        self,
        session_id: str,
        video_id: str,
        timeout_ms: int,
        db_session: Optional[Session],
        failure_callback: Optional[Callable]
    ):
        """Background worker for video start timeout"""
        try:
            timeout_seconds = timeout_ms / 1000.0

            logger.debug(
                f"Video start timeout worker started - "
                f"Session: {session_id}, Video: {video_id}, "
                f"Waiting {timeout_seconds}s"
            )

            # Wait for timeout
            await asyncio.sleep(timeout_seconds)

            # If we get here, timeout occurred
            logger.error(
                f"Video start timeout - Session: {session_id}, "
                f"Video: {video_id}, Timeout: {timeout_ms}ms"
            )

            # Mark session as failed
            if db_session:
                await self._mark_session_failed(
                    session_id,
                    f"Video {video_id} failed to start within {timeout_ms}ms",
                    db_session
                )

            # Execute callback
            if failure_callback:
                try:
                    if asyncio.iscoroutinefunction(failure_callback):
                        await failure_callback(session_id, video_id, "video_start_timeout")
                    else:
                        failure_callback(session_id, video_id, "video_start_timeout")
                except Exception as cb_error:
                    logger.error(f"Error in failure callback: {cb_error}")

            # Emit WebSocket event
            await self._emit_session_failed(
                session_id,
                "video_start_timeout",
                f"Video {video_id} did not start within {timeout_ms}ms"
            )

        except asyncio.CancelledError:
            logger.debug(f"Video start timeout cancelled (video started)")
            raise
        except Exception as e:
            logger.error(f"Error in video start timeout worker: {e}")

    async def _mark_session_failed(
        self,
        session_id: str,
        failure_reason: str,
        db_session: Session
    ):
        """Mark session as failed in database"""
        try:
            from models import TestSession

            # Query session
            session = db_session.query(TestSession).filter(
                TestSession.id == session_id
            ).first()

            if not session:
                logger.error(f"Session {session_id} not found in database")
                return

            # Update status
            session.status = SessionState.TIMEOUT.value
            session.failure_reason = failure_reason
            session.failed_at = datetime.now(timezone.utc)

            db_session.commit()

            logger.info(
                f"Marked session {session_id} as failed - "
                f"Reason: {failure_reason}"
            )

        except SQLAlchemyError as e:
            logger.error(f"Database error marking session failed: {e}")
            db_session.rollback()
        except Exception as e:
            logger.error(f"Error marking session failed: {e}")

    async def _emit_session_failed(
        self,
        session_id: str,
        failure_type: str,
        failure_message: str
    ):
        """Emit WebSocket event for session failure"""
        try:
            # Import socketio if available
            from socketio_server import sio

            await sio.emit(
                'session_failed',
                {
                    'session_id': session_id,
                    'failure_type': failure_type,
                    'message': failure_message,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                room=session_id  # Send only to this session's room
            )

            logger.info(f"Emitted session_failed event for {session_id}")

        except ImportError:
            logger.warning("SocketIO not available - cannot emit session_failed event")
        except Exception as e:
            logger.error(f"Error emitting session_failed event: {e}")

    def get_active_monitors(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active timeout monitors"""
        monitors = {}

        for key, timeout_obj in self._active_timeouts.items():
            monitors[key] = {
                'session_id': timeout_obj.session_id,
                'video_id': timeout_obj.video_id,
                'timeout_ms': timeout_obj.timeout_ms,
                'created_at': timeout_obj.created_at,
                'elapsed_ms': (time.time() - timeout_obj.created_at) * 1000,
                'is_running': timeout_obj.task and not timeout_obj.task.done()
            }

        return monitors

    async def cleanup_session(self, session_id: str):
        """Clean up all monitors for a session"""
        async with self._lock:
            keys_to_remove = [
                key for key in self._active_timeouts
                if self._active_timeouts[key].session_id == session_id
            ]

            for key in keys_to_remove:
                timeout_obj = self._active_timeouts[key]
                if timeout_obj.task and not timeout_obj.task.done():
                    timeout_obj.task.cancel()
                    try:
                        await timeout_obj.task
                    except asyncio.CancelledError:
                        pass

                del self._active_timeouts[key]

            logger.info(f"Cleaned up {len(keys_to_remove)} monitors for session {session_id}")


# Global singleton instance
_session_monitor = None


def get_session_monitor() -> SessionMonitor:
    """Get global session monitor instance"""
    global _session_monitor

    if _session_monitor is None:
        _session_monitor = SessionMonitor()

    return _session_monitor
