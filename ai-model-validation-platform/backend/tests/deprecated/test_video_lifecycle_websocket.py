"""
DEPRECATED TEST FILE
===================

This test file has been deprecated on 2025-11-20 because it imports services
that no longer exist or have been removed from the codebase.

Deprecated services used:
- Services that were removed during architecture refactoring
- Services that were consolidated into other modules
- Services that were replaced with newer implementations

This file is preserved for historical reference but is not actively maintained.
If you need similar functionality, please check the current service implementations
in src/services/ or consult the documentation.

Original location: tests/test_video_lifecycle_websocket.py
"""

"""
Test Video Lifecycle WebSocket Handlers

Tests the WebSocket event handlers for VIDEO_STARTED, VIDEO_ENDED, VIDEO_ERROR
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from services.video_lifecycle_websocket_handlers import (
    VideoLifecycleWebSocketHandler,
    register_video_lifecycle_handlers
)


@pytest.fixture
def mock_sio():
    """Mock Socket.IO server"""
    sio = Mock()
    sio.emit = AsyncMock()
    sio.event = Mock()
    return sio


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = Mock()
    session.close = Mock()
    return session


@pytest.fixture
def mock_db_factory(mock_db_session):
    """Mock database session factory"""
    return lambda: mock_db_session


@pytest.fixture
def handler(mock_sio, mock_db_factory):
    """Create handler instance"""
    return VideoLifecycleWebSocketHandler(mock_sio, mock_db_factory)


class TestVideoLifecycleWebSocketHandler:
    """Test video lifecycle WebSocket handlers"""

    @pytest.mark.asyncio
    async def test_handle_video_started_success(self, handler, mock_sio):
        """Test successful VIDEO_STARTED event handling"""
        # Mock orchestrator
        with patch('services.video_lifecycle_websocket_handlers.VideoLifecycleOrchestrator') as mock_orch_class:
            mock_orchestrator = Mock()
            mock_orchestrator.handle_video_started = AsyncMock(return_value=True)
            mock_orch_class.return_value = mock_orchestrator

            # Call handler
            data = {
                'event': 'VIDEO_STARTED',
                'sessionId': 'test-session-123',
                'videoId': 'video-456',
                'timestamp': 1234567890.5,
                'clockOffset': 10
            }

            await handler.handle_video_lifecycle('client-sid', data)

            # Verify orchestrator was called
            mock_orchestrator.handle_video_started.assert_called_once_with(
                session_id='test-session-123',
                video_id='video-456',
                frontend_timestamp=1234567890.5,
                clock_offset_ms=10
            )

            # Verify acknowledgment was sent
            assert mock_sio.emit.call_count >= 1
            calls = [call[0] for call in mock_sio.emit.call_args_list]
            assert 'video-started-ack' in calls or 'video-monitoring-update' in calls

    @pytest.mark.asyncio
    async def test_handle_video_started_missing_session_id(self, handler, mock_sio):
        """Test VIDEO_STARTED with missing sessionId"""
        data = {
            'event': 'VIDEO_STARTED',
            'videoId': 'video-456',
            'timestamp': 1234567890.5
        }

        await handler.handle_video_lifecycle('client-sid', data)

        # Verify error was emitted
        mock_sio.emit.assert_called()
        call_args = mock_sio.emit.call_args_list[0]
        assert call_args[0][0] == 'video-lifecycle-error'
        assert 'sessionId' in call_args[0][1]['error']

    @pytest.mark.asyncio
    async def test_handle_video_started_missing_video_id(self, handler, mock_sio):
        """Test VIDEO_STARTED with missing videoId"""
        data = {
            'event': 'VIDEO_STARTED',
            'sessionId': 'test-session-123',
            'timestamp': 1234567890.5
        }

        await handler.handle_video_lifecycle('client-sid', data)

        # Verify error was emitted
        mock_sio.emit.assert_called()
        call_args = mock_sio.emit.call_args_list[0]
        assert call_args[0][0] == 'video-lifecycle-error'
        assert 'videoId' in call_args[0][1]['error']

    @pytest.mark.asyncio
    async def test_handle_video_started_orchestrator_failure(self, handler, mock_sio):
        """Test VIDEO_STARTED when orchestrator fails"""
        with patch('services.video_lifecycle_websocket_handlers.VideoLifecycleOrchestrator') as mock_orch_class:
            mock_orchestrator = Mock()
            mock_orchestrator.handle_video_started = AsyncMock(return_value=False)
            mock_orch_class.return_value = mock_orchestrator

            data = {
                'event': 'VIDEO_STARTED',
                'sessionId': 'test-session-123',
                'videoId': 'video-456',
                'timestamp': 1234567890.5
            }

            await handler.handle_video_lifecycle('client-sid', data)

            # Verify error was emitted
            error_calls = [
                call for call in mock_sio.emit.call_args_list
                if call[0][0] == 'video-lifecycle-error'
            ]
            assert len(error_calls) >= 1
            assert 'Failed to start LabJack monitoring' in error_calls[0][0][1]['error']

    @pytest.mark.asyncio
    async def test_handle_video_ended_success(self, handler, mock_sio):
        """Test successful VIDEO_ENDED event handling"""
        with patch('services.video_lifecycle_websocket_handlers.VideoLifecycleOrchestrator') as mock_orch_class:
            mock_orchestrator = Mock()
            mock_orchestrator.handle_video_ended = AsyncMock(return_value=True)
            mock_orch_class.return_value = mock_orchestrator

            data = {
                'event': 'VIDEO_ENDED',
                'sessionId': 'test-session-123',
                'videoId': 'video-456',
                'timestamp': 1234567900.5
            }

            await handler.handle_video_lifecycle('client-sid', data)

            # Verify orchestrator was called
            mock_orchestrator.handle_video_ended.assert_called_once_with(
                session_id='test-session-123',
                video_id='video-456',
                frontend_timestamp=1234567900.5
            )

            # Verify acknowledgment was sent
            assert mock_sio.emit.call_count >= 1

    @pytest.mark.asyncio
    async def test_handle_video_error(self, handler, mock_sio):
        """Test VIDEO_ERROR event handling"""
        with patch('services.video_lifecycle_websocket_handlers.VideoLifecycleOrchestrator') as mock_orch_class:
            mock_orchestrator = Mock()
            mock_orchestrator.handle_video_error = AsyncMock(return_value=True)
            mock_orch_class.return_value = mock_orchestrator

            data = {
                'event': 'VIDEO_ERROR',
                'sessionId': 'test-session-123',
                'videoId': 'video-456',
                'error': 'Video playback failed'
            }

            await handler.handle_video_lifecycle('client-sid', data)

            # Verify orchestrator was called
            mock_orchestrator.handle_video_error.assert_called_once_with(
                session_id='test-session-123',
                video_id='video-456',
                error_message='Video playback failed'
            )

            # Verify acknowledgment was sent
            assert mock_sio.emit.call_count >= 1

    @pytest.mark.asyncio
    async def test_handle_unknown_event_type(self, handler, mock_sio):
        """Test handling of unknown event type"""
        data = {
            'event': 'UNKNOWN_EVENT',
            'sessionId': 'test-session-123',
            'videoId': 'video-456'
        }

        await handler.handle_video_lifecycle('client-sid', data)

        # Verify error was emitted
        error_calls = [
            call for call in mock_sio.emit.call_args_list
            if call[0][0] == 'video-lifecycle-error'
        ]
        assert len(error_calls) >= 1
        assert 'Unknown event type' in error_calls[0][0][1]['error']

    @pytest.mark.asyncio
    async def test_clock_sync_ping(self, handler, mock_sio):
        """Test clock synchronization ping"""
        data = {'t1': 1234567890.123456}

        await handler.handle_clock_sync_ping('client-sid', data)

        # Verify pong was sent
        mock_sio.emit.assert_called_once()
        call_args = mock_sio.emit.call_args_list[0]
        assert call_args[0][0] == 'clock-sync-pong'
        assert call_args[0][1]['t1'] == 1234567890.123456
        assert 't2' in call_args[0][1]
        assert 't3' in call_args[0][1]

    @pytest.mark.asyncio
    async def test_clock_sync_ping_missing_t1(self, handler, mock_sio):
        """Test clock sync ping with missing t1"""
        data = {}

        await handler.handle_clock_sync_ping('client-sid', data)

        # Should not emit anything
        mock_sio.emit.assert_not_called()


class TestRegisterHandlers:
    """Test handler registration"""

    def test_register_video_lifecycle_handlers(self, mock_sio, mock_db_factory):
        """Test handler registration with Socket.IO"""
        register_video_lifecycle_handlers(mock_sio, mock_db_factory)

        # Verify event decorator was called
        assert mock_sio.event.call_count == 2

        # Verify correct events were registered
        event_names = [call[0][0].__name__ for call in mock_sio.event.call_args_list]
        assert 'video_lifecycle' in event_names
        assert 'clock_sync_ping' in event_names


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
