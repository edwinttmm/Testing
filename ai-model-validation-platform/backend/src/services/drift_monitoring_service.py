"""
Drift Monitoring Service - Production Grade Drift Statistics and Alerting
==========================================================================

Monitors drift measurements, calculates statistics, and generates alerts
for drift anomalies during test execution.

Author: Backend API Developer Agent
Date: 2025-11-20
"""

import logging
import weakref
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone
from enum import Enum
import statistics
import threading

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of drift alerts"""
    HIGH_DRIFT = "high_drift"
    HIGH_VARIANCE = "high_variance"
    DRIFT_TRENDING_UP = "drift_trending_up"
    INCONSISTENT_MEASUREMENTS = "inconsistent_measurements"
    MEASUREMENT_FAILURE = "measurement_failure"


@dataclass
class DriftAlert:
    """Drift monitoring alert"""
    alert_id: str
    session_id: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    drift_value_ms: Optional[float] = None
    variance_ms: Optional[float] = None
    threshold_ms: Optional[float] = None
    metadata: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False


@dataclass
class DriftStatistics:
    """Drift statistics for a session or video"""
    session_id: str
    video_count: int

    # Basic statistics
    mean_drift_ms: float
    median_drift_ms: float
    std_dev_ms: float
    min_drift_ms: float
    max_drift_ms: float

    # Trend analysis
    drift_trend: str  # "stable", "increasing", "decreasing", "erratic"
    trend_confidence: float  # 0.0 to 1.0

    # Quality assessment
    measurement_quality: str  # "excellent", "good", "acceptable", "poor"
    confidence_score: float  # 0.0 to 1.0

    # Alerts
    active_alerts: int
    total_alerts: int

    # Timestamps
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data_points: int = 0


class DriftMonitoringService:
    """
    Production-grade drift monitoring service.

    Features:
    - Real-time drift statistics calculation
    - Automatic alert generation for anomalies
    - Trend analysis
    - Quality assessment
    - Custom alert thresholds
    - Alert callbacks for notifications
    """

    def __init__(
        self,
        high_drift_threshold_ms: float = 500.0,
        high_variance_threshold_ms: float = 100.0
    ) -> None:
        self._alerts: Dict[str, List[DriftAlert]] = {}  # session_id -> alerts
        self._statistics: Dict[str, DriftStatistics] = {}  # session_id -> stats
        self._drift_history: Dict[str, List[float]] = {}  # session_id -> drift values
        # Use weak references to prevent memory leaks from orphaned callbacks
        self._alert_callbacks: List[weakref.ref] = []
        self._lock = threading.RLock()
        self._cleanup_counter = 0  # Track cleanup frequency

        # Configuration
        self.high_drift_threshold_ms: float = high_drift_threshold_ms
        self.high_variance_threshold_ms: float = high_variance_threshold_ms

        logger.info(
            f"Drift Monitoring Service initialized "
            f"(drift_threshold={high_drift_threshold_ms}ms, "
            f"variance_threshold={high_variance_threshold_ms}ms)"
        )

    def register_alert_callback(self, callback: Callable[[DriftAlert], None]) -> None:
        """
        Register a callback to be called when alerts are generated.

        Uses weak references to prevent memory leaks. The callback will be
        automatically removed when the object is garbage collected.

        Args:
            callback: Function that takes DriftAlert as argument
        """
        with self._lock:
            # Wrap in WeakMethod if it's a bound method, otherwise use weakref
            if hasattr(callback, '__self__'):
                weak_callback = weakref.WeakMethod(callback, self._callback_cleanup)
            else:
                weak_callback = weakref.ref(callback, self._callback_cleanup)

            self._alert_callbacks.append(weak_callback)
            logger.info(f"Registered alert callback: {callback.__name__} (using weak reference)")

    def _callback_cleanup(self, ref: weakref.ref) -> None:
        """
        Callback invoked when a weak reference is about to be finalized.

        Args:
            ref: The weak reference being finalized
        """
        logger.debug("Callback garbage collected, weak reference cleaned up")

    def remove_alert_callback(self, callback: Callable[[DriftAlert], None]) -> bool:
        """
        Remove a previously registered callback.

        Args:
            callback: The callback function to remove

        Returns:
            True if callback was found and removed, False otherwise
        """
        with self._lock:
            # Clean dead references first
            self.cleanup_dead_callbacks()

            # Find and remove the matching callback
            for i, weak_callback in enumerate(self._alert_callbacks):
                cb = weak_callback()
                if cb is not None and cb == callback:
                    self._alert_callbacks.pop(i)
                    logger.info(f"Removed alert callback: {callback.__name__}")
                    return True

            logger.warning(f"Callback {callback.__name__} not found in registered callbacks")
            return False

    def cleanup_dead_callbacks(self) -> int:
        """
        Remove dead weak references from callback list.

        Returns:
            Number of dead references removed
        """
        with self._lock:
            before_count = len(self._alert_callbacks)
            self._alert_callbacks = [cb for cb in self._alert_callbacks if cb() is not None]
            removed = before_count - len(self._alert_callbacks)

            if removed > 0:
                logger.info(f"Cleaned up {removed} dead callback references")

            return removed

    def record_drift_measurement(
        self,
        session_id: str,
        drift_ms: float,
        video_id: Optional[str] = None
    ) -> None:
        """
        Record a drift measurement and check for alerts.

        Args:
            session_id: Test session identifier
            drift_ms: Measured drift in milliseconds
            video_id: Optional video identifier
        """
        with self._lock:
            # Store drift value
            if session_id not in self._drift_history:
                self._drift_history[session_id] = []

            self._drift_history[session_id].append(drift_ms)

            # Update statistics
            self._update_statistics(session_id)

            # Check for alerts
            self._check_drift_alerts(session_id, drift_ms, video_id)

            logger.debug(f"Recorded drift measurement for session {session_id}: {drift_ms:.2f}ms")

    def _update_statistics(self, session_id: str) -> None:
        """Update statistics for a session"""
        with self._lock:
            drift_values = self._drift_history.get(session_id, [])

            if len(drift_values) < 2:
                return  # Need at least 2 data points

            # Calculate basic statistics
            mean_drift = statistics.mean(drift_values)
            median_drift = statistics.median(drift_values)
            std_dev = statistics.stdev(drift_values) if len(drift_values) > 1 else 0.0
            min_drift = min(drift_values)
            max_drift = max(drift_values)

            # Analyze trend
            drift_trend, trend_confidence = self._analyze_trend(drift_values)

            # Assess quality
            quality, confidence = self._assess_quality(drift_values, std_dev)

            # Count alerts
            session_alerts = self._alerts.get(session_id, [])
            active_alerts = sum(1 for a in session_alerts if not a.acknowledged)

            stats = DriftStatistics(
                session_id=session_id,
                video_count=len(drift_values),
                mean_drift_ms=mean_drift,
                median_drift_ms=median_drift,
                std_dev_ms=std_dev,
                min_drift_ms=min_drift,
                max_drift_ms=max_drift,
                drift_trend=drift_trend,
                trend_confidence=trend_confidence,
                measurement_quality=quality,
                confidence_score=confidence,
                active_alerts=active_alerts,
                total_alerts=len(session_alerts),
                data_points=len(drift_values)
            )

            self._statistics[session_id] = stats

    def _analyze_trend(self, drift_values: List[float]) -> Tuple[str, float]:
        """Analyze drift trend"""
        if len(drift_values) < 3:
            return "insufficient_data", 0.0

        # Simple linear trend analysis
        recent = drift_values[-5:]  # Last 5 measurements
        if len(recent) < 3:
            return "stable", 0.5

        # Calculate trend direction
        increasing = sum(1 for i in range(len(recent)-1) if recent[i+1] > recent[i])
        decreasing = sum(1 for i in range(len(recent)-1) if recent[i+1] < recent[i])

        total_comparisons = len(recent) - 1

        if increasing / total_comparisons > 0.7:
            return "increasing", 0.8
        elif decreasing / total_comparisons > 0.7:
            return "decreasing", 0.8
        elif abs(max(recent) - min(recent)) < 50:  # Within 50ms range
            return "stable", 0.9
        else:
            return "erratic", 0.6

    def _assess_quality(self, drift_values: List[float], std_dev: float) -> Tuple[str, float]:
        """Assess measurement quality"""
        if len(drift_values) < 3:
            return "insufficient_data", 0.0

        # Quality based on standard deviation
        if std_dev < 25:
            return "excellent", 0.95
        elif std_dev < 50:
            return "good", 0.85
        elif std_dev < 100:
            return "acceptable", 0.70
        else:
            return "poor", 0.40

    def _check_drift_alerts(
        self,
        session_id: str,
        drift_ms: float,
        video_id: Optional[str]
    ) -> None:
        """Check if drift triggers any alerts"""
        alerts_generated = []

        # Check high drift threshold
        if abs(drift_ms) > self.high_drift_threshold_ms:
            alert = self._create_alert(
                session_id=session_id,
                alert_type=AlertType.HIGH_DRIFT,
                severity=AlertSeverity.ERROR if abs(drift_ms) > 1000 else AlertSeverity.WARNING,
                message=f"High drift detected: {drift_ms:.2f}ms exceeds threshold {self.high_drift_threshold_ms}ms",
                drift_value_ms=drift_ms,
                threshold_ms=self.high_drift_threshold_ms,
                metadata={"video_id": video_id} if video_id else {}
            )
            alerts_generated.append(alert)

        # Check variance threshold
        drift_values = self._drift_history.get(session_id, [])
        if len(drift_values) >= 3:
            variance = statistics.stdev(drift_values)
            if variance > self.high_variance_threshold_ms:
                alert = self._create_alert(
                    session_id=session_id,
                    alert_type=AlertType.HIGH_VARIANCE,
                    severity=AlertSeverity.WARNING,
                    message=f"High drift variance detected: {variance:.2f}ms exceeds threshold {self.high_variance_threshold_ms}ms",
                    variance_ms=variance,
                    threshold_ms=self.high_variance_threshold_ms
                )
                alerts_generated.append(alert)

        # Periodic cleanup of dead callbacks (every 100 calls)
        self._cleanup_counter += 1
        if self._cleanup_counter >= 100:
            self.cleanup_dead_callbacks()
            self._cleanup_counter = 0

        # Trigger callbacks for each alert
        # Clean dead refs first to avoid unnecessary iterations
        alive_callbacks = [cb for cb in self._alert_callbacks if cb() is not None]
        self._alert_callbacks = alive_callbacks

        for alert in alerts_generated:
            for weak_callback in self._alert_callbacks:
                callback = weak_callback()
                if callback is not None:
                    try:
                        callback(alert)
                    except Exception as e:
                        logger.error(f"Error in alert callback: {e}")
                else:
                    logger.debug("Skipped dead callback reference")

    def _create_alert(
        self,
        session_id: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        **kwargs
    ) -> DriftAlert:
        """Create and store an alert"""
        with self._lock:
            alert_id = f"{session_id}_{alert_type.value}_{datetime.now(timezone.utc).timestamp()}"

            alert = DriftAlert(
                alert_id=alert_id,
                session_id=session_id,
                alert_type=alert_type,
                severity=severity,
                message=message,
                **kwargs
            )

            if session_id not in self._alerts:
                self._alerts[session_id] = []

            self._alerts[session_id].append(alert)

            logger.warning(f"Alert generated for session {session_id}: {message}")

            return alert

    def get_drift_statistics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get drift statistics for a session"""
        with self._lock:
            stats = self._statistics.get(session_id)
            if not stats:
                return None

            return {
                "session_id": stats.session_id,
                "video_count": stats.video_count,
                "mean_drift_ms": round(stats.mean_drift_ms, 2),
                "median_drift_ms": round(stats.median_drift_ms, 2),
                "std_dev_ms": round(stats.std_dev_ms, 2),
                "min_drift_ms": round(stats.min_drift_ms, 2),
                "max_drift_ms": round(stats.max_drift_ms, 2),
                "drift_trend": stats.drift_trend,
                "trend_confidence": round(stats.trend_confidence, 2),
                "measurement_quality": stats.measurement_quality,
                "confidence_score": round(stats.confidence_score, 2),
                "active_alerts": stats.active_alerts,
                "total_alerts": stats.total_alerts,
                "data_points": stats.data_points,
                "calculated_at": stats.calculated_at.isoformat()
            }

    def get_session_alerts(
        self,
        session_id: str,
        include_acknowledged: bool = True
    ) -> List[Dict[str, Any]]:
        """Get alerts for a session"""
        with self._lock:
            alerts = self._alerts.get(session_id, [])

            if not include_acknowledged:
                alerts = [a for a in alerts if not a.acknowledged]

            return [
                {
                    "alert_id": a.alert_id,
                    "alert_type": a.alert_type.value,
                    "severity": a.severity.value,
                    "message": a.message,
                    "drift_value_ms": a.drift_value_ms,
                    "variance_ms": a.variance_ms,
                    "threshold_ms": a.threshold_ms,
                    "metadata": a.metadata,
                    "timestamp": a.timestamp.isoformat(),
                    "acknowledged": a.acknowledged
                }
                for a in alerts
            ]

    def acknowledge_alert(self, session_id: str, alert_id: str) -> None:
        """Mark an alert as acknowledged"""
        with self._lock:
            alerts = self._alerts.get(session_id, [])
            for alert in alerts:
                if alert.alert_id == alert_id:
                    alert.acknowledged = True
                    logger.info(f"Alert {alert_id} acknowledged")
                    return

    def cleanup_session(self, session_id: str) -> None:
        """Clean up monitoring data for a completed session"""
        with self._lock:
            if session_id in self._alerts:
                del self._alerts[session_id]
            if session_id in self._statistics:
                del self._statistics[session_id]
            if session_id in self._drift_history:
                del self._drift_history[session_id]

            logger.info(f"Cleaned up drift monitoring data for session {session_id}")

    def get_service_statistics(self) -> Dict[str, Any]:
        """Get overall service statistics"""
        with self._lock:
            total_sessions = len(self._drift_history)
            total_measurements = sum(len(vals) for vals in self._drift_history.values())
            total_alerts = sum(len(alerts) for alerts in self._alerts.values())
            active_alerts = sum(
                sum(1 for a in alerts if not a.acknowledged)
                for alerts in self._alerts.values()
            )

            # Count alive callbacks only
            alive_callbacks = sum(1 for cb in self._alert_callbacks if cb() is not None)

            return {
                "total_sessions": total_sessions,
                "total_measurements": total_measurements,
                "total_alerts": total_alerts,
                "active_alerts": active_alerts,
                "high_drift_threshold_ms": self.high_drift_threshold_ms,
                "high_variance_threshold_ms": self.high_variance_threshold_ms,
                "registered_callbacks": alive_callbacks,
                "service_status": "operational"
            }


# Global service instance
_drift_monitoring_service: Optional[DriftMonitoringService] = None


def get_drift_monitoring_service() -> DriftMonitoringService:
    """Get or create the global drift monitoring service instance"""
    global _drift_monitoring_service
    if _drift_monitoring_service is None:
        _drift_monitoring_service = DriftMonitoringService()
    return _drift_monitoring_service


def initialize_drift_monitoring_service(
    high_drift_threshold_ms: float = 500.0,
    high_variance_threshold_ms: float = 100.0
) -> DriftMonitoringService:
    """Initialize the drift monitoring service with custom thresholds"""
    global _drift_monitoring_service
    _drift_monitoring_service = DriftMonitoringService(
        high_drift_threshold_ms=high_drift_threshold_ms,
        high_variance_threshold_ms=high_variance_threshold_ms
    )
    return _drift_monitoring_service
