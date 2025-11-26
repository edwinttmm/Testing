"""Metrics collection for timing quality and system health"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import threading
from collections import defaultdict


@dataclass
class SessionMetrics:
    """Metrics for a single session"""
    session_id: str
    start_time: datetime
    timing_degraded: bool
    timing_verified: bool
    total_detections: int
    validated_detections: int
    degraded_detections: int

    @property
    def validation_rate(self) -> float:
        """Calculate detection validation rate"""
        if self.total_detections == 0:
            return 0.0
        return self.validated_detections / self.total_detections * 100

    @property
    def degradation_rate(self) -> float:
        """Calculate detection degradation rate"""
        if self.total_detections == 0:
            return 0.0
        return self.degraded_detections / self.total_detections * 100


class MetricsCollector:
    """Collect and aggregate system metrics"""

    def __init__(self):
        self.lock = threading.Lock()
        self.session_metrics: Dict[str, SessionMetrics] = {}
        self.global_stats = {
            'total_sessions': 0,
            'degraded_sessions': 0,
            'verified_sessions': 0,
            'total_detections': 0,
            'validated_detections': 0,
            'degraded_detections': 0
        }
        self.session_history: List[str] = []  # Track session order

    def record_session_start(self, session_id: str, timing_degraded: bool, timing_verified: bool):
        """Record session start with timing quality information

        Args:
            session_id: Unique session identifier
            timing_degraded: Whether timing quality is degraded
            timing_verified: Whether timing has been verified
        """
        with self.lock:
            self.session_metrics[session_id] = SessionMetrics(
                session_id=session_id,
                start_time=datetime.now(),
                timing_degraded=timing_degraded,
                timing_verified=timing_verified,
                total_detections=0,
                validated_detections=0,
                degraded_detections=0
            )

            self.session_history.append(session_id)
            self.global_stats['total_sessions'] += 1

            if timing_degraded:
                self.global_stats['degraded_sessions'] += 1

            if timing_verified:
                self.global_stats['verified_sessions'] += 1

    def record_detection(self, session_id: str, usable_for_validation: bool):
        """Record detection event

        Args:
            session_id: Session where detection occurred
            usable_for_validation: Whether detection has valid timing for validation
        """
        with self.lock:
            if session_id not in self.session_metrics:
                # Auto-create session if not exists
                self.record_session_start(session_id, timing_degraded=False, timing_verified=False)

            metrics = self.session_metrics[session_id]
            metrics.total_detections += 1

            if usable_for_validation:
                metrics.validated_detections += 1
                self.global_stats['validated_detections'] += 1
            else:
                metrics.degraded_detections += 1
                self.global_stats['degraded_detections'] += 1

            self.global_stats['total_detections'] += 1

    def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """Get metrics summary for a session

        Args:
            session_id: Session to retrieve metrics for

        Returns:
            Dictionary with session metrics or None if not found
        """
        with self.lock:
            if session_id not in self.session_metrics:
                return None

            metrics = self.session_metrics[session_id]
            return {
                'session_id': session_id,
                'start_time': metrics.start_time.isoformat(),
                'timing_degraded': metrics.timing_degraded,
                'timing_verified': metrics.timing_verified,
                'total_detections': metrics.total_detections,
                'validated_detections': metrics.validated_detections,
                'degraded_detections': metrics.degraded_detections,
                'validation_rate': round(metrics.validation_rate, 2),
                'degradation_rate': round(metrics.degradation_rate, 2)
            }

    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """Get metrics for recent sessions

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session metrics
        """
        with self.lock:
            recent_ids = self.session_history[-limit:]
            return [
                self.get_session_summary(sid)
                for sid in reversed(recent_ids)
                if sid in self.session_metrics
            ]

    def get_global_summary(self) -> Dict:
        """Get global metrics summary

        Returns:
            Dictionary with aggregated global metrics
        """
        with self.lock:
            total_sessions = self.global_stats['total_sessions']
            total_detections = self.global_stats['total_detections']

            return {
                'total_sessions': total_sessions,
                'degraded_sessions': self.global_stats['degraded_sessions'],
                'verified_sessions': self.global_stats['verified_sessions'],
                'total_detections': total_detections,
                'validated_detections': self.global_stats['validated_detections'],
                'degraded_detections': self.global_stats['degraded_detections'],
                'degradation_rate': round(
                    (self.global_stats['degraded_sessions'] / total_sessions * 100)
                    if total_sessions > 0 else 0,
                    2
                ),
                'validation_rate': round(
                    (self.global_stats['validated_detections'] / total_detections * 100)
                    if total_detections > 0 else 0,
                    2
                )
            }

    def reset_metrics(self):
        """Reset all collected metrics (for testing)"""
        with self.lock:
            self.session_metrics.clear()
            self.session_history.clear()
            self.global_stats = {
                'total_sessions': 0,
                'degraded_sessions': 0,
                'verified_sessions': 0,
                'total_detections': 0,
                'validated_detections': 0,
                'degraded_detections': 0
            }


# Global singleton instance
metrics_collector = MetricsCollector()
