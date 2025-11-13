"""
Heartbeat Service for Session Activity Tracking

This service tracks session activity through heartbeat signals
and detects stalled sessions that have lost connection.

Key Features:
- WebSocket heartbeat tracking
- Last activity timestamp management
- Stalled session detection
- Automatic cleanup of inactive sessions

Production Standards:
- Thread-safe operations
- Minimal performance overhead
- Comprehensive logging
"""

import logging
import time
import threading
from typing import Dict, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SessionHeartbeat:
    """Tracks session activity and heartbeat status"""
    session_id: str
    last_heartbeat: float
    first_heartbeat: float
    heartbeat_count: int
    is_active: bool
    last_event_type: Optional[str] = None


class HeartbeatService:
    """
    Tracks session activity, detects stalled sessions.

    Monitors heartbeat signals from frontend and marks sessions
    as stalled if no heartbeat received within threshold.
    """

    def __init__(self):
        """Initialize heartbeat service"""
        self._heartbeats: Dict[str, SessionHeartbeat] = {}
        self._lock = threading.RLock()

        # Configuration
        self.heartbeat_interval_seconds = 5  # Expected heartbeat frequency
        self.stall_threshold_seconds = 30    # Mark stalled after this time
        self.cleanup_threshold_seconds = 300  # Remove after 5 minutes

        # Statistics
        self._total_heartbeats = 0
        self._stalled_sessions_detected = 0

        logger.info("HeartbeatService initialized")

    def record_heartbeat(
        self,
        session_id: str,
        event_type: str = "heartbeat",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record a heartbeat signal from frontend.

        Args:
            session_id: Test session identifier
            event_type: Type of activity (heartbeat, video_start, detection, etc.)
            metadata: Optional metadata about the activity

        Returns:
            True if heartbeat recorded successfully
        """
        try:
            with self._lock:
                current_time = time.time()

                if session_id in self._heartbeats:
                    # Update existing heartbeat
                    heartbeat = self._heartbeats[session_id]
                    heartbeat.last_heartbeat = current_time
                    heartbeat.heartbeat_count += 1
                    heartbeat.is_active = True
                    heartbeat.last_event_type = event_type
                else:
                    # Create new heartbeat tracker
                    heartbeat = SessionHeartbeat(
                        session_id=session_id,
                        last_heartbeat=current_time,
                        first_heartbeat=current_time,
                        heartbeat_count=1,
                        is_active=True,
                        last_event_type=event_type
                    )
                    self._heartbeats[session_id] = heartbeat

                self._total_heartbeats += 1

                logger.debug(
                    f"Heartbeat recorded - Session: {session_id}, "
                    f"Type: {event_type}, Count: {heartbeat.heartbeat_count}"
                )

                return True

        except Exception as e:
            logger.error(f"Failed to record heartbeat for {session_id}: {e}")
            return False

    def get_last_activity(self, session_id: str) -> Optional[float]:
        """
        Get timestamp of last activity for a session.

        Args:
            session_id: Test session identifier

        Returns:
            Timestamp of last activity, or None if session not tracked
        """
        with self._lock:
            heartbeat = self._heartbeats.get(session_id)
            return heartbeat.last_heartbeat if heartbeat else None

    def is_session_stalled(self, session_id: str) -> bool:
        """
        Check if session is stalled (no heartbeat within threshold).

        Args:
            session_id: Test session identifier

        Returns:
            True if session is stalled
        """
        with self._lock:
            heartbeat = self._heartbeats.get(session_id)

            if not heartbeat:
                return False  # Unknown session

            time_since_last_heartbeat = time.time() - heartbeat.last_heartbeat
            is_stalled = time_since_last_heartbeat > self.stall_threshold_seconds

            if is_stalled and heartbeat.is_active:
                # First detection of stall
                heartbeat.is_active = False
                self._stalled_sessions_detected += 1

                logger.warning(
                    f"Session stalled - Session: {session_id}, "
                    f"Last heartbeat: {time_since_last_heartbeat:.1f}s ago"
                )

            return is_stalled

    def get_time_since_last_activity(self, session_id: str) -> Optional[float]:
        """
        Get time elapsed since last activity in seconds.

        Args:
            session_id: Test session identifier

        Returns:
            Seconds since last activity, or None if session not tracked
        """
        with self._lock:
            heartbeat = self._heartbeats.get(session_id)

            if not heartbeat:
                return None

            return time.time() - heartbeat.last_heartbeat

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed heartbeat information for a session.

        Args:
            session_id: Test session identifier

        Returns:
            Dictionary with heartbeat information, or None
        """
        with self._lock:
            heartbeat = self._heartbeats.get(session_id)

            if not heartbeat:
                return None

            time_since_last = time.time() - heartbeat.last_heartbeat
            session_duration = time.time() - heartbeat.first_heartbeat

            return {
                'session_id': session_id,
                'is_active': heartbeat.is_active,
                'is_stalled': self.is_session_stalled(session_id),
                'last_heartbeat': heartbeat.last_heartbeat,
                'last_heartbeat_iso': datetime.fromtimestamp(
                    heartbeat.last_heartbeat,
                    tz=timezone.utc
                ).isoformat(),
                'time_since_last_heartbeat_seconds': time_since_last,
                'heartbeat_count': heartbeat.heartbeat_count,
                'session_duration_seconds': session_duration,
                'last_event_type': heartbeat.last_event_type
            }

    def get_all_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all active (non-stalled) sessions"""
        with self._lock:
            active_sessions = {}

            for session_id, heartbeat in self._heartbeats.items():
                if not self.is_session_stalled(session_id):
                    active_sessions[session_id] = self.get_session_info(session_id)

            return active_sessions

    def get_all_stalled_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all stalled sessions"""
        with self._lock:
            stalled_sessions = {}

            for session_id, heartbeat in self._heartbeats.items():
                if self.is_session_stalled(session_id):
                    stalled_sessions[session_id] = self.get_session_info(session_id)

            return stalled_sessions

    def cleanup_session(self, session_id: str) -> bool:
        """
        Remove heartbeat tracking for a session.

        Args:
            session_id: Test session identifier

        Returns:
            True if session was removed
        """
        try:
            with self._lock:
                if session_id in self._heartbeats:
                    del self._heartbeats[session_id]
                    logger.info(f"Cleaned up heartbeat tracking for session {session_id}")
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to cleanup session {session_id}: {e}")
            return False

    def cleanup_old_sessions(self) -> int:
        """
        Remove heartbeat tracking for sessions inactive beyond cleanup threshold.

        Returns:
            Number of sessions cleaned up
        """
        try:
            with self._lock:
                current_time = time.time()
                sessions_to_remove = []

                for session_id, heartbeat in self._heartbeats.items():
                    time_since_last = current_time - heartbeat.last_heartbeat

                    if time_since_last > self.cleanup_threshold_seconds:
                        sessions_to_remove.append(session_id)

                for session_id in sessions_to_remove:
                    del self._heartbeats[session_id]

                if sessions_to_remove:
                    logger.info(
                        f"Cleaned up {len(sessions_to_remove)} old sessions: "
                        f"{sessions_to_remove}"
                    )

                return len(sessions_to_remove)

        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return 0

    def get_statistics(self) -> Dict[str, Any]:
        """Get heartbeat service statistics"""
        with self._lock:
            active_count = len([
                s for s in self._heartbeats.values()
                if not self.is_session_stalled(s.session_id)
            ])
            stalled_count = len([
                s for s in self._heartbeats.values()
                if self.is_session_stalled(s.session_id)
            ])

            return {
                'total_sessions_tracked': len(self._heartbeats),
                'active_sessions': active_count,
                'stalled_sessions': stalled_count,
                'total_heartbeats_received': self._total_heartbeats,
                'stalled_sessions_detected_lifetime': self._stalled_sessions_detected,
                'heartbeat_interval_seconds': self.heartbeat_interval_seconds,
                'stall_threshold_seconds': self.stall_threshold_seconds,
                'cleanup_threshold_seconds': self.cleanup_threshold_seconds
            }


# Global singleton instance
_heartbeat_service = None
_heartbeat_lock = threading.Lock()


def get_heartbeat_service() -> HeartbeatService:
    """Get global heartbeat service instance (thread-safe singleton)"""
    global _heartbeat_service

    if _heartbeat_service is None:
        with _heartbeat_lock:
            if _heartbeat_service is None:
                _heartbeat_service = HeartbeatService()

    return _heartbeat_service
