"""Monitoring dashboard API endpoints"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from monitoring.metrics_collector import metrics_collector
from monitoring.alerts import alert_manager, AlertSeverity
from utils.pool_monitor import PoolMonitor

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/metrics/global")
async def get_global_metrics():
    """Get global system metrics

    Returns aggregated metrics across all sessions including:
    - Total sessions and detections
    - Degradation and validation rates
    - Session timing quality statistics
    """
    return metrics_collector.get_global_summary()


@router.get("/metrics/session/{session_id}")
async def get_session_metrics(session_id: str):
    """Get metrics for specific session

    Args:
        session_id: Session identifier

    Returns:
        Session-specific metrics or 404 if not found
    """
    metrics = metrics_collector.get_session_summary(session_id)
    if metrics is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return metrics


@router.get("/metrics/sessions/recent")
async def get_recent_sessions(limit: int = Query(default=10, ge=1, le=100)):
    """Get metrics for recent sessions

    Args:
        limit: Maximum number of sessions to return (1-100)

    Returns:
        List of recent session metrics
    """
    return metrics_collector.get_recent_sessions(limit)


@router.get("/health/database")
async def get_database_health():
    """Get database connection pool health

    Returns:
        Database pool status including active connections and availability
    """
    return PoolMonitor.get_pool_status()


@router.get("/alerts")
async def get_recent_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    severity: Optional[str] = Query(default=None, regex="^(info|warning|error|critical)$")
):
    """Get recent alerts

    Args:
        limit: Maximum number of alerts to return (1-500)
        severity: Filter by severity level (info, warning, error, critical)

    Returns:
        List of recent alerts
    """
    severity_enum = None
    if severity:
        severity_enum = AlertSeverity(severity)

    return alert_manager.get_recent_alerts(limit, severity_enum)


@router.get("/alerts/thresholds")
async def get_alert_thresholds():
    """Get configured alert thresholds

    Returns:
        Dictionary of all alert thresholds
    """
    return alert_manager.get_thresholds()


@router.post("/alerts/test")
async def test_alert_system(severity: str = "info"):
    """Test alert system

    Args:
        severity: Alert severity to test (info, warning, error, critical)

    Returns:
        Confirmation of alert sent
    """
    try:
        severity_enum = AlertSeverity(severity)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity: {severity}. Must be one of: info, warning, error, critical"
        )

    alert_manager.send_alert(
        severity_enum,
        f"Alert system test - {severity} level",
        {'test': True, 'severity': severity}
    )

    return {
        "status": "alert sent",
        "severity": severity,
        "handlers_count": len(alert_manager.handlers)
    }


@router.post("/alerts/check-thresholds")
async def check_thresholds():
    """Manually trigger threshold checks

    Runs all configured threshold checks against current metrics
    and sends alerts if thresholds are exceeded.

    Returns:
        Current metrics and alert status
    """
    alert_manager.check_all_thresholds(metrics_collector)

    return {
        "status": "checks completed",
        "metrics": metrics_collector.get_global_summary(),
        "thresholds": alert_manager.get_thresholds()
    }


@router.get("/status")
async def get_monitoring_status():
    """Get overall monitoring system status

    Returns comprehensive status including:
    - Metrics collection status
    - Alert system status
    - Database health
    - Recent alerts summary
    """
    metrics = metrics_collector.get_global_summary()
    db_health = PoolMonitor.get_pool_status()
    recent_alerts = alert_manager.get_recent_alerts(10)

    # Count alerts by severity
    alert_counts = {
        'info': 0,
        'warning': 0,
        'error': 0,
        'critical': 0
    }
    for alert in recent_alerts:
        alert_counts[alert['severity']] += 1

    return {
        "monitoring": {
            "active": True,
            "alert_handlers": len(alert_manager.handlers),
            "alert_history_size": len(alert_manager.alert_history)
        },
        "metrics": metrics,
        "database": db_health,
        "recent_alerts": {
            "total": len(recent_alerts),
            "by_severity": alert_counts,
            "latest": recent_alerts[:3] if recent_alerts else []
        }
    }
