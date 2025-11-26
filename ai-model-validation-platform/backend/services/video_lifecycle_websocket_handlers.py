"""
Video Lifecycle WebSocket Event Handlers

Handles VIDEO_STARTED, VIDEO_ENDED, VIDEO_ERROR events from frontend
and coordinates with LabJack monitoring via orchestrator.

Integration:
- Receives lifecycle events from frontend via WebSocket
- Calls VideoLifecycleOrchestrator to manage LabJack monitoring
- Implements clock synchronization for timing accuracy
- Provides error handling and recovery
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class VideoLifecycleWebSocketHandler:
    """Handles video lifecycle WebSocket events and coordinates with orchestrator"""

    def __init__(self, sio, db_session_factory):
        """
        Initialize handler with Socket.IO server and database session factory

        Args:
            sio: Socket.IO server instance
            db_session_factory: Database session factory (SessionLocal)
        """
        self.sio = sio
        self.db_session_factory = db_session_factory

    async def handle_video_lifecycle(self, sid: str, data: Dict[str, Any]) -> None:
        """
        Handle video lifecycle events from frontend.

        Events: VIDEO_STARTED, VIDEO_ENDED, VIDEO_ERROR

        Args:
            sid: Socket.IO session ID
            data: Event data containing:
                - event: Event type (VIDEO_STARTED, VIDEO_ENDED, VIDEO_ERROR)
                - sessionId: Test session ID
                - videoId: Video ID
                - timestamp: Frontend timestamp
                - clockOffset: Clock offset in milliseconds (optional)
                - error: Error message (for VIDEO_ERROR)
        """
        try:
            event_type = data.get('event')
            session_id = data.get('sessionId')
            video_id = data.get('videoId')
            frontend_timestamp = data.get('timestamp')
            clock_offset = data.get('clockOffset', 0)

            # Validate required fields
            if not event_type:
                logger.warning(f"Video lifecycle event missing 'event' field from {sid}")
                await self.sio.emit('video-lifecycle-error', {
                    'error': 'Missing required field: event',
                    'timestamp': time.time()
                }, room=sid)
                return

            if not session_id:
                logger.warning(f"Video lifecycle event missing 'sessionId' field from {sid}")
                await self.sio.emit('video-lifecycle-error', {
                    'error': 'Missing required field: sessionId',
                    'event': event_type,
                    'timestamp': time.time()
                }, room=sid)
                return

            if not video_id and event_type != 'VIDEO_ERROR':
                logger.warning(f"Video lifecycle event missing 'videoId' field from {sid}")
                await self.sio.emit('video-lifecycle-error', {
                    'error': 'Missing required field: videoId',
                    'event': event_type,
                    'sessionId': session_id,
                    'timestamp': time.time()
                }, room=sid)
                return

            logger.info(
                f"Video lifecycle: {event_type} for video {video_id} "
                f"in session {session_id} (sid: {sid})"
            )

            # Route to appropriate handler
            if event_type == 'VIDEO_STARTED':
                await self._handle_video_started(
                    sid=sid,
                    session_id=session_id,
                    video_id=video_id,
                    frontend_timestamp=frontend_timestamp,
                    clock_offset_ms=clock_offset
                )

            elif event_type == 'VIDEO_ENDED':
                await self._handle_video_ended(
                    sid=sid,
                    session_id=session_id,
                    video_id=video_id,
                    frontend_timestamp=frontend_timestamp
                )

            elif event_type == 'VIDEO_ERROR':
                await self._handle_video_error(
                    sid=sid,
                    session_id=session_id,
                    video_id=video_id,
                    error_message=data.get('error', 'Unknown error')
                )

            else:
                logger.warning(f"Unknown video lifecycle event type: {event_type}")
                await self.sio.emit('video-lifecycle-error', {
                    'error': f'Unknown event type: {event_type}',
                    'sessionId': session_id,
                    'timestamp': time.time()
                }, room=sid)

        except Exception as e:
            logger.error(
                f"Error handling video lifecycle event: {e}",
                exc_info=True
            )
            # Don't crash the test, just log and notify client
            try:
                await self.sio.emit('video-lifecycle-error', {
                    'error': f'Internal server error: {str(e)}',
                    'sessionId': data.get('sessionId'),
                    'videoId': data.get('videoId'),
                    'timestamp': time.time()
                }, room=sid)
            except Exception as emit_error:
                logger.error(f"Failed to emit error response: {emit_error}")

    async def _handle_video_started(
        self,
        sid: str,
        session_id: str,
        video_id: str,
        frontend_timestamp: Optional[float],
        clock_offset_ms: float
    ) -> None:
        """
        Handle VIDEO_STARTED event - start LabJack monitoring

        Args:
            sid: Socket.IO session ID
            session_id: Test session ID
            video_id: Video ID
            frontend_timestamp: Frontend timestamp (seconds since epoch)
            clock_offset_ms: Clock offset in milliseconds
        """
        db = self.db_session_factory()
        try:
            # Import orchestrator (lazy import to avoid circular dependencies)
            from services.video_lifecycle_orchestrator import VideoLifecycleOrchestrator

            orchestrator = VideoLifecycleOrchestrator(db)

            # Call orchestrator to start LabJack monitoring
            success = await orchestrator.handle_video_started(
                session_id=session_id,
                video_id=video_id,
                frontend_timestamp=frontend_timestamp,
                clock_offset_ms=clock_offset_ms
            )

            if success:
                logger.info(
                    f"✅ LabJack monitoring started for video {video_id} "
                    f"in session {session_id}"
                )

                # Send acknowledgment to client
                await self.sio.emit('video-started-ack', {
                    'sessionId': session_id,
                    'videoId': video_id,
                    'status': 'monitoring_started',
                    'timestamp': time.time()
                }, room=sid)

                # Also broadcast to session room for other clients
                session_room = f"session_{session_id}"
                await self.sio.emit('video-monitoring-update', {
                    'event': 'monitoring_started',
                    'sessionId': session_id,
                    'videoId': video_id,
                    'timestamp': time.time()
                }, room=session_room)

            else:
                logger.error(
                    f"❌ Failed to start LabJack monitoring for video {video_id}"
                )
                await self.sio.emit('video-lifecycle-error', {
                    'error': 'Failed to start LabJack monitoring',
                    'sessionId': session_id,
                    'videoId': video_id,
                    'timestamp': time.time()
                }, room=sid)

        except Exception as e:
            logger.error(
                f"Exception in _handle_video_started: {e}",
                exc_info=True
            )
            await self.sio.emit('video-lifecycle-error', {
                'error': f'Failed to start monitoring: {str(e)}',
                'sessionId': session_id,
                'videoId': video_id,
                'timestamp': time.time()
            }, room=sid)
        finally:
            db.close()

    async def _handle_video_ended(
        self,
        sid: str,
        session_id: str,
        video_id: str,
        frontend_timestamp: Optional[float]
    ) -> None:
        """
        Handle VIDEO_ENDED event - stop LabJack monitoring

        Args:
            sid: Socket.IO session ID
            session_id: Test session ID
            video_id: Video ID
            frontend_timestamp: Frontend timestamp (seconds since epoch)
        """
        db = self.db_session_factory()
        try:
            # Import orchestrator
            from services.video_lifecycle_orchestrator import VideoLifecycleOrchestrator

            orchestrator = VideoLifecycleOrchestrator(db)

            # Call orchestrator to stop LabJack monitoring
            success = await orchestrator.handle_video_ended(
                session_id=session_id,
                video_id=video_id,
                frontend_timestamp=frontend_timestamp
            )

            if success:
                logger.info(
                    f"✅ LabJack monitoring stopped for video {video_id} "
                    f"in session {session_id}"
                )

                # Send acknowledgment to client
                await self.sio.emit('video-ended-ack', {
                    'sessionId': session_id,
                    'videoId': video_id,
                    'status': 'monitoring_stopped',
                    'timestamp': time.time()
                }, room=sid)

                # Broadcast to session room
                session_room = f"session_{session_id}"
                await self.sio.emit('video-monitoring-update', {
                    'event': 'monitoring_stopped',
                    'sessionId': session_id,
                    'videoId': video_id,
                    'timestamp': time.time()
                }, room=session_room)

            else:
                logger.error(
                    f"❌ Failed to stop LabJack monitoring for video {video_id}"
                )
                await self.sio.emit('video-lifecycle-error', {
                    'error': 'Failed to stop LabJack monitoring',
                    'sessionId': session_id,
                    'videoId': video_id,
                    'timestamp': time.time()
                }, room=sid)

        except Exception as e:
            logger.error(
                f"Exception in _handle_video_ended: {e}",
                exc_info=True
            )
            await self.sio.emit('video-lifecycle-error', {
                'error': f'Failed to stop monitoring: {str(e)}',
                'sessionId': session_id,
                'videoId': video_id,
                'timestamp': time.time()
            }, room=sid)
        finally:
            db.close()

    async def _handle_video_error(
        self,
        sid: str,
        session_id: str,
        video_id: Optional[str],
        error_message: str
    ) -> None:
        """
        Handle VIDEO_ERROR event - log error and stop monitoring

        Args:
            sid: Socket.IO session ID
            session_id: Test session ID
            video_id: Video ID (optional)
            error_message: Error message from frontend
        """
        db = self.db_session_factory()
        try:
            logger.error(
                f"❌ Video error for video {video_id} in session {session_id}: "
                f"{error_message}"
            )

            # Import orchestrator
            from services.video_lifecycle_orchestrator import VideoLifecycleOrchestrator

            orchestrator = VideoLifecycleOrchestrator(db)

            # Call orchestrator to handle error (stop monitoring if active)
            success = await orchestrator.handle_video_error(
                session_id=session_id,
                video_id=video_id,
                error_message=error_message
            )

            # Send acknowledgment to client
            await self.sio.emit('video-error-ack', {
                'sessionId': session_id,
                'videoId': video_id,
                'status': 'error_handled',
                'error': error_message,
                'timestamp': time.time()
            }, room=sid)

            # Broadcast to session room
            session_room = f"session_{session_id}"
            await self.sio.emit('video-monitoring-update', {
                'event': 'monitoring_error',
                'sessionId': session_id,
                'videoId': video_id,
                'error': error_message,
                'timestamp': time.time()
            }, room=session_room)

        except Exception as e:
            logger.error(
                f"Exception in _handle_video_error: {e}",
                exc_info=True
            )
        finally:
            db.close()

    async def handle_clock_sync_ping(self, sid: str, data: Dict[str, Any]) -> None:
        """
        Handle NTP-like clock sync ping from frontend

        Args:
            sid: Socket.IO session ID
            data: Data containing:
                - t1: Client timestamp when ping was sent
        """
        try:
            t1_client = data.get('t1')

            if t1_client is None:
                logger.warning(f"Clock sync ping missing t1 from {sid}")
                return

            # Server receive time
            t2_server = time.time()

            # Respond immediately with server timestamps
            await self.sio.emit('clock-sync-pong', {
                't1': t1_client,  # Client send time
                't2': t2_server,  # Server receive time
                't3': time.time()  # Server send time
            }, room=sid)

            logger.debug(
                f"Clock sync: t1={t1_client:.6f}, t2={t2_server:.6f}, "
                f"t3={time.time():.6f}"
            )

        except Exception as e:
            logger.error(f"Error handling clock sync ping: {e}", exc_info=True)


def register_video_lifecycle_handlers(sio, db_session_factory):
    """
    Register video lifecycle WebSocket event handlers

    Args:
        sio: Socket.IO server instance
        db_session_factory: Database session factory (SessionLocal)
    """
    handler = VideoLifecycleWebSocketHandler(sio, db_session_factory)

    @sio.event
    async def video_lifecycle(sid, data):
        """Video lifecycle event handler"""
        await handler.handle_video_lifecycle(sid, data)

    @sio.event
    async def clock_sync_ping(sid, data):
        """Clock synchronization ping handler"""
        await handler.handle_clock_sync_ping(sid, data)

    logger.info("✅ Video lifecycle WebSocket handlers registered")


# Export handler class and registration function
__all__ = [
    'VideoLifecycleWebSocketHandler',
    'register_video_lifecycle_handlers'
]
