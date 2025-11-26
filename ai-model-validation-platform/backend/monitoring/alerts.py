"""Alerting system for critical conditions"""
import logging
from enum import Enum
from typing import List, Callable, Optional, Dict
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert notification"""
    severity: AlertSeverity
    message: str
    context: Dict
    timestamp: datetime

    def __init__(self, severity: AlertSeverity, message: str, context: Optional[Dict] = None):
        self.severity = severity
        self.message = message
        self.context = context or {}
        self.timestamp = datetime.now()

    def __str__(self):
        return f"[{self.severity.value.upper()}] {self.message}"

    def to_dict(self) -> Dict:
        """Convert alert to dictionary"""
        return {
            'severity': self.severity.value,
            'message': self.message,
            'context': self.context,
            'timestamp': self.timestamp.isoformat()
        }


class AlertManager:
    """Manage system alerts"""

    def __init__(self):
        self.handlers: List[Callable[[Alert], None]] = []
        self.alert_history: List[Alert] = []
        self.max_history = 1000  # Keep last 1000 alerts

        # Alert thresholds
        self.thresholds = {
            'degradation_rate_critical': 50.0,
            'degradation_rate_warning': 25.0,
            'validation_rate_error': 50.0,
            'validation_rate_warning': 70.0
        }

    def register_handler(self, handler: Callable[[Alert], None]):
        """Register alert handler (e.g., email, webhook)

        Args:
            handler: Callable that accepts an Alert object
        """
        self.handlers.append(handler)
        logger.info(f"Registered alert handler: {handler.__name__}")

    def send_alert(self, severity: AlertSeverity, message: str, context: Optional[Dict] = None):
        """Send alert to all handlers

        Args:
            severity: Alert severity level
            message: Alert message
            context: Additional context information
        """
        alert = Alert(severity, message, context)

        # Add to history
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history.pop(0)

        # Log alert
        log_level = {
            AlertSeverity.INFO: logger.info,
            AlertSeverity.WARNING: logger.warning,
            AlertSeverity.ERROR: logger.error,
            AlertSeverity.CRITICAL: logger.critical
        }[severity]

        log_level(f"🚨 ALERT: {alert}")

        # Notify handlers
        for handler in self.handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler {handler.__name__} failed: {e}")

    def check_timing_degradation_rate(self, metrics_collector):
        """Check if timing degradation rate exceeds thresholds

        Args:
            metrics_collector: MetricsCollector instance
        """
        summary = metrics_collector.get_global_summary()
        degradation_rate = summary['degradation_rate']

        if degradation_rate > self.thresholds['degradation_rate_critical']:
            self.send_alert(
                AlertSeverity.CRITICAL,
                f"High timing degradation rate: {degradation_rate:.1f}%",
                {
                    'degradation_rate': degradation_rate,
                    'threshold': self.thresholds['degradation_rate_critical'],
                    'degraded_sessions': summary['degraded_sessions'],
                    'total_sessions': summary['total_sessions']
                }
            )
        elif degradation_rate > self.thresholds['degradation_rate_warning']:
            self.send_alert(
                AlertSeverity.WARNING,
                f"Elevated timing degradation rate: {degradation_rate:.1f}%",
                {
                    'degradation_rate': degradation_rate,
                    'threshold': self.thresholds['degradation_rate_warning'],
                    'degraded_sessions': summary['degraded_sessions'],
                    'total_sessions': summary['total_sessions']
                }
            )

    def check_validation_rate(self, metrics_collector):
        """Check if validation rate is below thresholds

        Args:
            metrics_collector: MetricsCollector instance
        """
        summary = metrics_collector.get_global_summary()
        validation_rate = summary['validation_rate']

        if validation_rate < self.thresholds['validation_rate_error']:
            self.send_alert(
                AlertSeverity.ERROR,
                f"Low detection validation rate: {validation_rate:.1f}%",
                {
                    'validation_rate': validation_rate,
                    'threshold': self.thresholds['validation_rate_error'],
                    'validated_detections': summary['validated_detections'],
                    'total_detections': summary['total_detections']
                }
            )
        elif validation_rate < self.thresholds['validation_rate_warning']:
            self.send_alert(
                AlertSeverity.WARNING,
                f"Reduced detection validation rate: {validation_rate:.1f}%",
                {
                    'validation_rate': validation_rate,
                    'threshold': self.thresholds['validation_rate_warning'],
                    'validated_detections': summary['validated_detections'],
                    'total_detections': summary['total_detections']
                }
            )

    def check_all_thresholds(self, metrics_collector):
        """Run all threshold checks

        Args:
            metrics_collector: MetricsCollector instance
        """
        self.check_timing_degradation_rate(metrics_collector)
        self.check_validation_rate(metrics_collector)

    def get_recent_alerts(self, limit: int = 50, severity: Optional[AlertSeverity] = None) -> List[Dict]:
        """Get recent alerts

        Args:
            limit: Maximum number of alerts to return
            severity: Filter by severity level

        Returns:
            List of alert dictionaries
        """
        alerts = self.alert_history[-limit:]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return [a.to_dict() for a in reversed(alerts)]

    def set_threshold(self, name: str, value: float):
        """Update alert threshold

        Args:
            name: Threshold name
            value: New threshold value
        """
        if name in self.thresholds:
            self.thresholds[name] = value
            logger.info(f"Updated threshold {name} to {value}")
        else:
            logger.warning(f"Unknown threshold: {name}")

    def get_thresholds(self) -> Dict[str, float]:
        """Get all configured thresholds"""
        return self.thresholds.copy()


# Global singleton instance
alert_manager = AlertManager()


# Example alert handlers

def console_alert_handler(alert: Alert):
    """Simple console alert handler"""
    print(f"\n{'='*60}")
    print(f"ALERT: {alert}")
    print(f"Time: {alert.timestamp}")
    if alert.context:
        print(f"Context: {alert.context}")
    print(f"{'='*60}\n")


def log_file_alert_handler(alert: Alert):
    """Write alerts to dedicated log file"""
    try:
        with open('/tmp/alerts.log', 'a') as f:
            f.write(f"{alert.timestamp.isoformat()} | {alert.severity.value.upper()} | {alert.message}\n")
            if alert.context:
                f.write(f"  Context: {alert.context}\n")
    except Exception as e:
        logger.error(f"Failed to write alert to file: {e}")
