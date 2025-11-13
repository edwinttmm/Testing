"""
Integration Tests for Backend Event Dependency Fixes

Tests timeout monitoring, heartbeat tracking, and state machine
to verify elimination of frontend event dependency.

Test Coverage:
- Session timeout scenarios
- Video start timeout scenarios
- Heartbeat tracking and stall detection
- Video state machine transitions
- Error recovery and graceful degradation
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

# Import services under test
from services.session_monitor import SessionMonitor, get_session_monitor, SessionState
from services.heartbeat_service import HeartbeatService, get_heartbeat_service
from services.video_state_machine import VideoStateMachine, get_video_state_machine, VideoState


class TestSessionMonitor:
    """Test session timeout monitoring"""

    @pytest.mark.asyncio
    async def test_session_timeout_triggers(self):
        """Test that session timeout fires when no activity"""
        monitor = SessionMonitor()

        session_id = "test-session-timeout"
        timeout_ms = 1000  # 1 second for fast test

        # Start monitoring
        result = await monitor.monitor_session_lifecycle(
            session_id=session_id,
            timeout_ms=timeout_ms
        )

        assert result is True
        assert session_id in monitor._active_timeouts

        # Wait for timeout to fire
        await asyncio.sleep(1.5)  # Wait longer than timeout

        # Timeout should have completed
        assert session_id not in monitor._active_timeouts

    @pytest.mark.asyncio
    async def test_session_timeout_cancelled(self):
        """Test that timeout is cancelled when activity detected"""
        monitor = SessionMonitor()

        session_id = "test-session-activity"
        timeout_ms = 2000  # 2 seconds

        # Start monitoring
        await monitor.monitor_session_lifecycle(
            session_id=session_id,
            timeout_ms=timeout_ms
        )

        # Cancel timeout (simulating activity)
        result = await monitor.cancel_timeout(session_id)

        assert result is True
        assert session_id not in monitor._active_timeouts

    @pytest.mark.asyncio
    async def test_video_start_timeout(self):
        """Test video start timeout monitoring"""
        monitor = SessionMonitor()

        session_id = "test-video-start"
        video_id = "video-1"
        timeout_ms = 1000  # 1 second

        # Track timeout fires
        timeout_fired = False

        async def on_timeout(sid, vid, reason):
            nonlocal timeout_fired
            timeout_fired = True

        # Start video start monitoring
        result = await monitor.monitor_video_start(
            session_id=session_id,
            video_id=video_id,
            timeout_ms=timeout_ms,
            failure_callback=on_timeout
        )

        assert result is True

        # Wait for timeout
        await asyncio.sleep(1.5)

        # Callback should have fired
        assert timeout_fired is True

    @pytest.mark.asyncio
    async def test_multiple_video_timeouts(self):
        """Test monitoring multiple videos simultaneously"""
        monitor = SessionMonitor()

        session_id = "test-multi-video"

        # Start monitoring for 3 videos
        for i in range(3):
            video_id = f"video-{i}"
            await monitor.monitor_video_start(
                session_id=session_id,
                video_id=video_id,
                timeout_ms=5000
            )

        # Should have 3 active monitors
        active_monitors = monitor.get_active_monitors()
        video_monitors = [
            k for k in active_monitors.keys()
            if k.startswith(f"{session_id}:video_start")
        ]

        assert len(video_monitors) == 3

        # Cancel first video
        await monitor.cancel_timeout(session_id, "video-0")

        # Should have 2 remaining
        active_monitors = monitor.get_active_monitors()
        video_monitors = [
            k for k in active_monitors.keys()
            if k.startswith(f"{session_id}:video_start")
        ]

        assert len(video_monitors) == 2


class TestHeartbeatService:
    """Test heartbeat tracking service"""

    def test_record_heartbeat(self):
        """Test recording heartbeat signals"""
        service = HeartbeatService()

        session_id = "test-heartbeat"

        # Record first heartbeat
        result = service.record_heartbeat(session_id)

        assert result is True

        # Get session info
        info = service.get_session_info(session_id)

        assert info is not None
        assert info['session_id'] == session_id
        assert info['heartbeat_count'] == 1
        assert info['is_active'] is True

        # Record second heartbeat
        service.record_heartbeat(session_id, event_type="detection")

        info = service.get_session_info(session_id)
        assert info['heartbeat_count'] == 2
        assert info['last_event_type'] == "detection"

    def test_stall_detection(self):
        """Test detection of stalled sessions"""
        service = HeartbeatService()
        service.stall_threshold_seconds = 1  # 1 second for testing

        session_id = "test-stall"

        # Record heartbeat
        service.record_heartbeat(session_id)

        # Should not be stalled initially
        assert service.is_session_stalled(session_id) is False

        # Wait for stall threshold
        time.sleep(1.5)

        # Should now be stalled
        assert service.is_session_stalled(session_id) is True

    def test_last_activity_tracking(self):
        """Test tracking of last activity timestamp"""
        service = HeartbeatService()

        session_id = "test-activity"

        # No activity initially
        last_activity = service.get_last_activity(session_id)
        assert last_activity is None

        # Record heartbeat
        before = time.time()
        service.record_heartbeat(session_id)
        after = time.time()

        # Last activity should be within timeframe
        last_activity = service.get_last_activity(session_id)
        assert last_activity is not None
        assert before <= last_activity <= after

    def test_cleanup_old_sessions(self):
        """Test cleanup of old inactive sessions"""
        service = HeartbeatService()
        service.cleanup_threshold_seconds = 1  # 1 second for testing

        # Create sessions
        for i in range(3):
            service.record_heartbeat(f"session-{i}")

        # Should have 3 sessions
        assert len(service._heartbeats) == 3

        # Wait for cleanup threshold
        time.sleep(1.5)

        # Cleanup old sessions
        cleaned = service.cleanup_old_sessions()

        assert cleaned == 3
        assert len(service._heartbeats) == 0


class TestVideoStateMachine:
    """Test video state machine"""

    def test_initialize_video(self):
        """Test initializing video state tracking"""
        machine = VideoStateMachine()

        session_id = "test-session"
        video_id = "test-video"

        # Initialize video
        result = machine.initialize_video(session_id, video_id)

        assert result is True

        # Check initial state
        state = machine.get_state(session_id, video_id)
        assert state == VideoState.PENDING

    def test_valid_state_transitions(self):
        """Test valid state transitions"""
        machine = VideoStateMachine()

        session_id = "test-transitions"
        video_id = "video-1"

        # Initialize
        machine.initialize_video(session_id, video_id)

        # PENDING → LOADING (valid)
        result = machine.transition_state(
            session_id, video_id,
            VideoState.LOADING,
            reason="Video loading started"
        )
        assert result is True
        assert machine.get_state(session_id, video_id) == VideoState.LOADING

        # LOADING → PLAYING (valid)
        result = machine.transition_state(
            session_id, video_id,
            VideoState.PLAYING,
            reason="Video playback started"
        )
        assert result is True
        assert machine.get_state(session_id, video_id) == VideoState.PLAYING

        # PLAYING → COMPLETED (valid)
        result = machine.transition_state(
            session_id, video_id,
            VideoState.COMPLETED,
            reason="Video playback completed"
        )
        assert result is True
        assert machine.get_state(session_id, video_id) == VideoState.COMPLETED

    def test_invalid_state_transitions(self):
        """Test that invalid transitions are blocked"""
        machine = VideoStateMachine()

        session_id = "test-invalid"
        video_id = "video-1"

        # Initialize
        machine.initialize_video(session_id, video_id)

        # PENDING → COMPLETED (invalid - must go through LOADING and PLAYING)
        result = machine.transition_state(
            session_id, video_id,
            VideoState.COMPLETED,
            reason="Invalid transition"
        )

        assert result is False
        assert machine.get_state(session_id, video_id) == VideoState.PENDING

        # Should have blocked the transition
        assert machine._invalid_transitions_blocked > 0

    def test_error_state_transition(self):
        """Test transition to error state"""
        machine = VideoStateMachine()

        session_id = "test-error"
        video_id = "video-1"

        # Initialize and start loading
        machine.initialize_video(session_id, video_id)
        machine.transition_state(session_id, video_id, VideoState.LOADING)

        # Transition to error
        result = machine.transition_state(
            session_id, video_id,
            VideoState.ERROR,
            reason="Video failed to load"
        )

        assert result is True
        assert machine.get_state(session_id, video_id) == VideoState.ERROR

        # Error is terminal state
        assert machine.is_terminal_state(session_id, video_id) is True

    def test_state_history_tracking(self):
        """Test that state transitions are recorded in history"""
        machine = VideoStateMachine()

        session_id = "test-history"
        video_id = "video-1"

        # Initialize and make transitions
        machine.initialize_video(session_id, video_id)
        machine.transition_state(session_id, video_id, VideoState.LOADING)
        machine.transition_state(session_id, video_id, VideoState.PLAYING)
        machine.transition_state(session_id, video_id, VideoState.COMPLETED)

        # Get state info
        info = machine.get_state_info(session_id, video_id)

        assert info is not None
        assert info['transition_count'] == 3
        assert len(info['state_history']) == 3

        # Check history order
        assert info['state_history'][0]['from'] == 'pending'
        assert info['state_history'][0]['to'] == 'loading'
        assert info['state_history'][1]['from'] == 'loading'
        assert info['state_history'][1]['to'] == 'playing'
        assert info['state_history'][2]['from'] == 'playing'
        assert info['state_history'][2]['to'] == 'completed'

    def test_timing_field_updates(self):
        """Test that timing fields are updated on transitions"""
        machine = VideoStateMachine()

        session_id = "test-timing"
        video_id = "video-1"

        # Initialize
        machine.initialize_video(session_id, video_id)

        # Transition to LOADING
        before_loading = time.time()
        machine.transition_state(session_id, video_id, VideoState.LOADING)
        after_loading = time.time()

        info = machine.get_state_info(session_id, video_id)
        assert info['loading_started_at'] is not None
        assert before_loading <= info['loading_started_at'] <= after_loading

        # Transition to PLAYING
        before_playing = time.time()
        machine.transition_state(session_id, video_id, VideoState.PLAYING)
        after_playing = time.time()

        info = machine.get_state_info(session_id, video_id)
        assert info['playback_started_at'] is not None
        assert before_playing <= info['playback_started_at'] <= after_playing

        # Transition to COMPLETED
        before_completed = time.time()
        machine.transition_state(session_id, video_id, VideoState.COMPLETED)
        after_completed = time.time()

        info = machine.get_state_info(session_id, video_id)
        assert info['completed_at'] is not None
        assert before_completed <= info['completed_at'] <= after_completed


class TestIntegration:
    """Integration tests combining all services"""

    @pytest.mark.asyncio
    async def test_complete_video_lifecycle_with_monitoring(self):
        """Test complete video lifecycle with all monitoring services"""
        # Initialize services
        monitor = SessionMonitor()
        heartbeat = HeartbeatService()
        state_machine = VideoStateMachine()

        session_id = "integration-test"
        video_id = "video-1"

        # 1. Initialize video state
        state_machine.initialize_video(session_id, video_id)
        assert state_machine.get_state(session_id, video_id) == VideoState.PENDING

        # 2. Start video start timeout monitor
        await monitor.monitor_video_start(
            session_id=session_id,
            video_id=video_id,
            timeout_ms=5000
        )

        # 3. Record heartbeat
        heartbeat.record_heartbeat(session_id, event_type="video_loading")

        # 4. Transition to LOADING
        state_machine.transition_state(
            session_id, video_id,
            VideoState.LOADING,
            reason="Frontend triggered loading"
        )

        # 5. Record heartbeat
        heartbeat.record_heartbeat(session_id, event_type="video_playing")

        # 6. Transition to PLAYING
        state_machine.transition_state(
            session_id, video_id,
            VideoState.PLAYING,
            reason="Frontend confirmed playback"
        )

        # 7. Cancel timeout (video started successfully)
        await monitor.cancel_timeout(session_id, video_id)

        # 8. Record final heartbeat
        heartbeat.record_heartbeat(session_id, event_type="video_ended")

        # 9. Transition to COMPLETED
        state_machine.transition_state(
            session_id, video_id,
            VideoState.COMPLETED,
            reason="Playback completed"
        )

        # Verify final state
        assert state_machine.get_state(session_id, video_id) == VideoState.COMPLETED
        assert state_machine.is_terminal_state(session_id, video_id) is True

        # Verify heartbeat activity
        heartbeat_info = heartbeat.get_session_info(session_id)
        assert heartbeat_info['heartbeat_count'] == 3
        assert heartbeat_info['is_active'] is True

    @pytest.mark.asyncio
    async def test_timeout_triggers_error_state(self):
        """Test that timeout automatically transitions to error state"""
        monitor = SessionMonitor()
        state_machine = VideoStateMachine()

        session_id = "timeout-error-test"
        video_id = "video-1"

        # Initialize video
        state_machine.initialize_video(session_id, video_id)
        state_machine.transition_state(session_id, video_id, VideoState.LOADING)

        # Define callback to transition to error on timeout
        async def on_timeout(sid, vid, reason):
            state_machine.transition_state(
                sid, vid,
                VideoState.TIMEOUT,
                reason=f"Timeout: {reason}"
            )

        # Start monitoring with short timeout
        await monitor.monitor_video_start(
            session_id=session_id,
            video_id=video_id,
            timeout_ms=1000,
            failure_callback=on_timeout
        )

        # Wait for timeout
        await asyncio.sleep(1.5)

        # State should be TIMEOUT
        assert state_machine.get_state(session_id, video_id) == VideoState.TIMEOUT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
