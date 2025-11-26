"""Integration module for connecting monitoring system with existing code"""
import logging
from typing import Optional
from monitoring.metrics_collector import metrics_collector
from monitoring.alerts import alert_manager, AlertSeverity

logger = logging.getLogger(__name__)


class MonitoringIntegration:
    """Helper class for integrating monitoring into existing workflows"""

    @staticmethod
    def on_session_start(session_id: str, session_info: dict):
        """Called when a new monitoring session starts

        Args:
            session_id: Unique session identifier
            session_info: Session information dictionary with timing quality data

        Example:
            session_info = {
                'timing_degraded': False,
                'timing_verified': True,
                'timing_quality': 'verified'
            }
        """
        timing_degraded = session_info.get('timing_degraded', False)
        timing_verified = session_info.get('timing_verified', False)

        metrics_collector.record_session_start(
            session_id=session_id,
            timing_degraded=timing_degraded,
            timing_verified=timing_verified
        )

        # Log session start
        quality_status = "DEGRADED" if timing_degraded else "VERIFIED" if timing_verified else "UNKNOWN"
        logger.info(f"📊 Session {session_id} started - Timing quality: {quality_status}")

        # Send alert if timing is degraded
        if timing_degraded:
            alert_manager.send_alert(
                AlertSeverity.WARNING,
                f"Session {session_id} started with degraded timing",
                {
                    'session_id': session_id,
                    'timing_verified': timing_verified
                }
            )

    @staticmethod
    def on_detection_saved(session_id: str, detection: dict):
        """Called when a detection is saved to database

        Args:
            session_id: Session identifier
            detection: Detection data including timing quality

        Example:
            detection = {
                'id': 123,
                'usable_for_validation': True,
                'timing_quality': 'good',
                'timestamp': '2025-01-19T14:30:22'
            }
        """
        usable_for_validation = detection.get('usable_for_validation', False)

        metrics_collector.record_detection(
            session_id=session_id,
            usable_for_validation=usable_for_validation
        )

        if not usable_for_validation:
            logger.debug(f"⚠️ Detection in session {session_id} not usable for validation")

    @staticmethod
    def periodic_health_check():
        """Run periodic health checks and send alerts if thresholds exceeded

        Should be called periodically (e.g., every 5 minutes) via scheduler
        """
        logger.debug("Running periodic health check")

        # Check all thresholds
        alert_manager.check_all_thresholds(metrics_collector)

        # Log current status
        metrics = metrics_collector.get_global_summary()
        logger.info(
            f"📊 System health - Sessions: {metrics['total_sessions']}, "
            f"Degradation: {metrics['degradation_rate']:.1f}%, "
            f"Validation: {metrics['validation_rate']:.1f}%"
        )

    @staticmethod
    def get_session_health(session_id: str) -> Optional[dict]:
        """Get health metrics for a specific session

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with session metrics or None if not found
        """
        return metrics_collector.get_session_summary(session_id)

    @staticmethod
    def get_system_health() -> dict:
        """Get overall system health metrics

        Returns:
            Dictionary with global system metrics
        """
        return metrics_collector.get_global_summary()


# Convenience functions for direct import

def record_session_start(session_id: str, timing_degraded: bool, timing_verified: bool):
    """Record session start (convenience function)

    Args:
        session_id: Session identifier
        timing_degraded: Whether timing is degraded
        timing_verified: Whether timing was verified
    """
    MonitoringIntegration.on_session_start(
        session_id,
        {
            'timing_degraded': timing_degraded,
            'timing_verified': timing_verified
        }
    )


def record_detection(session_id: str, usable_for_validation: bool):
    """Record detection event (convenience function)

    Args:
        session_id: Session identifier
        usable_for_validation: Whether detection is usable for validation
    """
    MonitoringIntegration.on_detection_saved(
        session_id,
        {'usable_for_validation': usable_for_validation}
    )


def run_health_check():
    """Run health check (convenience function)"""
    MonitoringIntegration.periodic_health_check()


def get_session_health(session_id: str) -> Optional[dict]:
    """Get session health (convenience function)"""
    return MonitoringIntegration.get_session_health(session_id)


def get_system_health() -> dict:
    """Get system health (convenience function)"""
    return MonitoringIntegration.get_system_health()
