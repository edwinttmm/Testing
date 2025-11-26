"""
Integration patch for dedicated_labjack_monitor.py to use monitoring system

This module provides integration functions to connect the monitoring system
with the existing DedicatedLabJackMonitor service.
"""
import logging
from typing import Dict, Any
from monitoring.integration import (
    record_session_start,
    record_detection,
    run_health_check,
    get_session_health,
    get_system_health
)

logger = logging.getLogger(__name__)


def integrate_monitoring_with_labjack_monitor(monitor_instance):
    """
    Integrate monitoring system with DedicatedLabJackMonitor instance

    This function patches the monitoring instance to automatically record
    metrics for sessions and detections.

    Args:
        monitor_instance: Instance of DedicatedLabJackMonitor
    """
    original_start_monitoring = monitor_instance.start_monitoring
    original_save_detection_event = getattr(monitor_instance, 'save_detection_event', None)

    def wrapped_start_monitoring(session_id: str, **kwargs):
        """Wrapped start_monitoring that records metrics"""
        # Call original method
        result = original_start_monitoring(session_id, **kwargs)

        # Extract session info from result or active sessions
        session_info = monitor_instance.active_sessions.get(session_id, {})

        # Determine timing quality from session info
        timing_degraded = session_info.get('timing_degraded', False)
        timing_verified = session_info.get('timing_verified', False)

        # Record session start in monitoring system
        record_session_start(
            session_id=session_id,
            timing_degraded=timing_degraded,
            timing_verified=timing_verified
        )

        logger.info(f"📊 Monitoring integrated for session {session_id}")

        return result

    def wrapped_save_detection_event(detection_event: Dict[str, Any]):
        """Wrapped save_detection_event that records metrics"""
        # Call original method
        if original_save_detection_event:
            result = original_save_detection_event(detection_event)
        else:
            result = None

        # Extract session_id and validation status
        session_id = detection_event.get('session_id')
        usable_for_validation = detection_event.get('usable_for_validation', False)

        if session_id:
            # Record detection in monitoring system
            record_detection(
                session_id=session_id,
                usable_for_validation=usable_for_validation
            )

        return result

    # Apply patches
    monitor_instance.start_monitoring = wrapped_start_monitoring
    if original_save_detection_event:
        monitor_instance.save_detection_event = wrapped_save_detection_event

    logger.info("✅ Monitoring system integrated with LabJack monitor")


def get_labjack_session_health(monitor_instance, session_id: str) -> Dict[str, Any]:
    """
    Get combined health metrics for a LabJack monitoring session

    Args:
        monitor_instance: DedicatedLabJackMonitor instance
        session_id: Session identifier

    Returns:
        Dictionary with combined metrics from monitoring system and LabJack service
    """
    # Get monitoring system metrics
    monitoring_health = get_session_health(session_id)

    # Get LabJack-specific metrics
    labjack_metrics = {
        'session_active': session_id in monitor_instance.active_sessions,
        'total_events': len(monitor_instance.detection_events.get(session_id, [])),
    }

    # Combine metrics
    return {
        'session_id': session_id,
        'monitoring': monitoring_health,
        'labjack': labjack_metrics
    }


def check_labjack_system_health(monitor_instance) -> Dict[str, Any]:
    """
    Get comprehensive system health including LabJack and monitoring metrics

    Args:
        monitor_instance: DedicatedLabJackMonitor instance

    Returns:
        Dictionary with comprehensive system health metrics
    """
    # Get monitoring system health
    monitoring_health = get_system_health()

    # Get LabJack-specific health
    labjack_health = {
        'active_sessions': len(monitor_instance.active_sessions),
        'total_detections': monitor_instance.total_detections,
        'successful_conversions': monitor_instance.successful_conversions,
        'failed_conversions': monitor_instance.failed_conversions,
        'conversion_success_rate': (
            monitor_instance.successful_conversions /
            monitor_instance.total_detections * 100
            if monitor_instance.total_detections > 0 else 0
        )
    }

    # Run periodic health check
    run_health_check()

    return {
        'monitoring': monitoring_health,
        'labjack': labjack_health,
        'overall_status': 'healthy' if monitoring_health.get('validation_rate', 0) > 70 else 'degraded'
    }


# Usage example for integration
"""
# In your application startup or where DedicatedLabJackMonitor is instantiated:

from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
from monitoring.labjack_monitor_integration import (
    integrate_monitoring_with_labjack_monitor,
    check_labjack_system_health
)

# Create monitor instance
monitor = DedicatedLabJackMonitor()

# Integrate monitoring system
integrate_monitoring_with_labjack_monitor(monitor)

# Periodically check health
import schedule
schedule.every(5).minutes.do(lambda: check_labjack_system_health(monitor))
"""
