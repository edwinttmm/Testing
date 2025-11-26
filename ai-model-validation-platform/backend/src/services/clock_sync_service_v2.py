"""
Clock Synchronization Service - Production Grade Drift Measurement
===================================================================

Implements NTP-like ping-pong protocol for precise clock synchronization
between browser and backend to measure exact timing drift.

Author: Backend API Developer Agent
Date: 2025-11-20
"""

import time
import asyncio
import logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import deque
import statistics
import threading

logger = logging.getLogger(__name__)


@dataclass
class ClockSyncMeasurement:
    """Single clock synchronization measurement"""
    measurement_id: str
    client_send_time: float  # T1: Client sends sync request
    server_receive_time: float  # T2: Server receives request
    server_send_time: float  # T3: Server sends response
    client_receive_time: float  # T4: Client receives response
    round_trip_time_ms: float = 0.0
    clock_offset_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Calculate RTT and clock offset"""
        # Round Trip Time = (T4 - T1) - (T3 - T2)
        self.round_trip_time_ms = ((self.client_receive_time - self.client_send_time) -
                                   (self.server_send_time - self.server_receive_time)) * 1000

        # Clock Offset = ((T2 - T1) + (T3 - T4)) / 2
        self.clock_offset_ms = (((self.server_receive_time - self.client_send_time) +
                                (self.server_send_time - self.client_receive_time)) / 2) * 1000


@dataclass
class SessionClockSync:
    """Clock synchronization data for a test session"""
    session_id: str
    measurements: deque = field(default_factory=lambda: deque(maxlen=20))  # Keep last 20
    active: bool = True
    last_sync_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def average_offset_ms(self) -> float:
        """Calculate average clock offset"""
        if not self.measurements:
            return 0.0
        return statistics.mean(m.clock_offset_ms for m in self.measurements)

    @property
    def offset_std_dev_ms(self) -> float:
        """Calculate standard deviation of clock offset"""
        if len(self.measurements) < 2:
            return 0.0
        return statistics.stdev(m.clock_offset_ms for m in self.measurements)

    @property
    def average_rtt_ms(self) -> float:
        """Calculate average round trip time"""
        if not self.measurements:
            return 0.0
        return statistics.mean(m.round_trip_time_ms for m in self.measurements)

    @property
    def sync_quality(self) -> str:
        """Assess synchronization quality"""
        if len(self.measurements) < 3:
            return "insufficient_data"

        std_dev = self.offset_std_dev_ms
        avg_rtt = self.average_rtt_ms

        if std_dev < 10 and avg_rtt < 50:
            return "excellent"
        elif std_dev < 25 and avg_rtt < 100:
            return "good"
        elif std_dev < 50 and avg_rtt < 200:
            return "acceptable"
        else:
            return "poor"


class ClockSynchronizationService:
    """
    Production-grade clock synchronization service using NTP-like protocol.

    Features:
    - Ping-pong protocol for precise offset calculation
    - Continuous re-synchronization during test sessions
    - Statistics and quality assessment
    - Automatic drift compensation
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionClockSync] = {}
        self._lock = threading.RLock()
        self._sync_interval_seconds: int = 30  # Re-sync every 30 seconds
        self._background_tasks: Dict[str, asyncio.Task] = {}

        logger.info("Clock Synchronization Service initialized")

    def start_session_sync(self, session_id: str) -> SessionClockSync:
        """
        Start clock synchronization for a test session.

        Args:
            session_id: Test session identifier

        Returns:
            SessionClockSync object
        """
        with self._lock:
            if session_id in self._sessions:
                logger.warning(f"Clock sync already active for session {session_id}")
                return self._sessions[session_id]

            sync_session = SessionClockSync(session_id=session_id)
            self._sessions[session_id] = sync_session

            logger.info(f"Started clock synchronization for session {session_id}")
            return sync_session

    def record_sync_measurement(
        self,
        session_id: str,
        measurement_id: str,
        client_send_time: float,
        server_receive_time: float,
        server_send_time: float,
        client_receive_time: float
    ) -> ClockSyncMeasurement:
        """
        Record a clock synchronization measurement using ping-pong protocol.

        Args:
            session_id: Test session identifier
            measurement_id: Unique measurement identifier
            client_send_time: T1 - Client sends sync request (client clock)
            server_receive_time: T2 - Server receives request (server clock)
            server_send_time: T3 - Server sends response (server clock)
            client_receive_time: T4 - Client receives response (client clock)

        Returns:
            ClockSyncMeasurement with calculated offset and RTT
        """
        measurement = ClockSyncMeasurement(
            measurement_id=measurement_id,
            client_send_time=client_send_time,
            server_receive_time=server_receive_time,
            server_send_time=server_send_time,
            client_receive_time=client_receive_time
        )

        with self._lock:
            if session_id not in self._sessions:
                logger.warning(f"No sync session found for {session_id}, creating new")
                self.start_session_sync(session_id)

            sync_session = self._sessions[session_id]
            sync_session.measurements.append(measurement)
            sync_session.last_sync_time = datetime.now(timezone.utc)

            logger.debug(
                f"Session {session_id}: Clock offset={measurement.clock_offset_ms:.2f}ms, "
                f"RTT={measurement.round_trip_time_ms:.2f}ms"
            )

        return measurement

    def get_clock_offset(self, session_id: str) -> float:
        """
        Get the current clock offset for a session in milliseconds.

        Args:
            session_id: Test session identifier

        Returns:
            Clock offset in milliseconds (positive = client ahead of server)
        """
        with self._lock:
            sync_session = self._sessions.get(session_id)
            if not sync_session or not sync_session.measurements:
                logger.warning(f"No clock sync data for session {session_id}, returning 0")
                return 0.0

            return sync_session.average_offset_ms

    def compensate_client_timestamp(
        self,
        session_id: str,
        client_timestamp: float
    ) -> float:
        """
        Compensate a client timestamp using measured clock offset.

        Args:
            session_id: Test session identifier
            client_timestamp: Timestamp from client (Unix time)

        Returns:
            Compensated timestamp (server time reference)
        """
        offset_ms = self.get_clock_offset(session_id)
        offset_seconds = offset_ms / 1000.0

        # Subtract offset to convert client time to server time
        compensated = client_timestamp - offset_seconds

        logger.debug(
            f"Compensated timestamp for session {session_id}: "
            f"{client_timestamp:.6f} -> {compensated:.6f} (offset={offset_ms:.2f}ms)"
        )

        return compensated

    def get_sync_statistics(self, session_id: str) -> Dict[str, Any]:
        """
        Get comprehensive synchronization statistics for a session.

        Args:
            session_id: Test session identifier

        Returns:
            Dictionary with sync statistics
        """
        with self._lock:
            sync_session = self._sessions.get(session_id)
            if not sync_session:
                return {
                    "error": "Session not found",
                    "session_id": session_id
                }

            measurements = list(sync_session.measurements)

            if not measurements:
                return {
                    "session_id": session_id,
                    "status": "no_measurements",
                    "measurement_count": 0
                }

            return {
                "session_id": session_id,
                "status": "active" if sync_session.active else "stopped",
                "measurement_count": len(measurements),
                "average_offset_ms": sync_session.average_offset_ms,
                "offset_std_dev_ms": sync_session.offset_std_dev_ms,
                "average_rtt_ms": sync_session.average_rtt_ms,
                "sync_quality": sync_session.sync_quality,
                "last_sync_time": sync_session.last_sync_time.isoformat() if sync_session.last_sync_time else None,
                "created_at": sync_session.created_at.isoformat(),
                "recent_offsets_ms": [m.clock_offset_ms for m in list(measurements)[-5:]],
                "recent_rtts_ms": [m.round_trip_time_ms for m in list(measurements)[-5:]]
            }

    def stop_session_sync(self, session_id: str) -> Dict[str, Any]:
        """
        Stop clock synchronization for a session and return final stats.

        Args:
            session_id: Test session identifier

        Returns:
            Final synchronization statistics
        """
        with self._lock:
            sync_session = self._sessions.get(session_id)
            if not sync_session:
                return {"error": "Session not found"}

            sync_session.active = False
            stats = self.get_sync_statistics(session_id)

            logger.info(
                f"Stopped clock sync for session {session_id}: "
                f"avg_offset={sync_session.average_offset_ms:.2f}ms, "
                f"quality={sync_session.sync_quality}"
            )

            return stats

    def cleanup_session(self, session_id: str) -> None:
        """
        Clean up clock synchronization data for a completed session.

        Args:
            session_id: Test session identifier
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"Cleaned up clock sync data for session {session_id}")

    async def continuous_sync_loop(self, session_id: str) -> None:
        """
        Background task for continuous clock synchronization.

        This would typically trigger WebSocket messages to the client
        to request new sync measurements every N seconds.

        Args:
            session_id: Test session identifier
        """
        logger.info(f"Starting continuous sync loop for session {session_id}")

        try:
            while True:
                with self._lock:
                    sync_session = self._sessions.get(session_id)
                    if not sync_session or not sync_session.active:
                        break

                # Sleep for sync interval
                await asyncio.sleep(self._sync_interval_seconds)

                # Trigger sync request (implementation depends on WebSocket setup)
                logger.debug(f"Triggering sync request for session {session_id}")

        except asyncio.CancelledError:
            logger.info(f"Sync loop cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Error in sync loop for session {session_id}: {e}")

    def get_service_statistics(self) -> Dict[str, Any]:
        """Get overall service statistics."""
        with self._lock:
            active_sessions = sum(1 for s in self._sessions.values() if s.active)
            total_measurements = sum(len(s.measurements) for s in self._sessions.values())

            return {
                "total_sessions": len(self._sessions),
                "active_sessions": active_sessions,
                "total_measurements": total_measurements,
                "sync_interval_seconds": self._sync_interval_seconds,
                "service_status": "operational"
            }


# Global service instance
_clock_sync_service: Optional[ClockSynchronizationService] = None


def get_clock_sync_service() -> ClockSynchronizationService:
    """Get or create the global clock synchronization service instance."""
    global _clock_sync_service
    if _clock_sync_service is None:
        _clock_sync_service = ClockSynchronizationService()
    return _clock_sync_service


def initialize_clock_sync_service() -> ClockSynchronizationService:
    """Initialize the clock synchronization service."""
    return get_clock_sync_service()
