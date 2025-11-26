# Monitoring & Alerting System Guide

## Overview

The monitoring system provides comprehensive metrics collection and alerting for timing quality and system health in the AI Model Validation Platform.

## Architecture

### Components

1. **MetricsCollector** - Collects and aggregates session and detection metrics
2. **AlertManager** - Manages alerts and notifications with configurable thresholds
3. **API Endpoints** - RESTful API for accessing metrics and alerts
4. **Alert Handlers** - Pluggable notification handlers (console, log file, email, webhook)

## Available Metrics

### Global Metrics

```python
{
    "total_sessions": 150,
    "degraded_sessions": 12,
    "verified_sessions": 138,
    "total_detections": 4532,
    "validated_detections": 4100,
    "degraded_detections": 432,
    "degradation_rate": 8.0,  # Percentage of degraded sessions
    "validation_rate": 90.47   # Percentage of validated detections
}
```

### Session Metrics

```python
{
    "session_id": "session_20250119_143022",
    "start_time": "2025-01-19T14:30:22.123456",
    "timing_degraded": false,
    "timing_verified": true,
    "total_detections": 45,
    "validated_detections": 42,
    "degraded_detections": 3,
    "validation_rate": 93.33,
    "degradation_rate": 6.67
}
```

## API Endpoints

### Get Global Metrics

```http
GET /api/monitoring/metrics/global
```

Returns aggregated metrics across all sessions.

### Get Session Metrics

```http
GET /api/monitoring/metrics/session/{session_id}
```

Returns metrics for a specific session.

### Get Recent Sessions

```http
GET /api/monitoring/metrics/sessions/recent?limit=10
```

Returns metrics for the most recent sessions.

**Parameters:**
- `limit` (optional): Number of sessions to return (1-100, default: 10)

### Get Database Health

```http
GET /api/monitoring/health/database
```

Returns database connection pool status.

### Get Recent Alerts

```http
GET /api/monitoring/alerts?limit=50&severity=error
```

Returns recent alerts with optional filtering.

**Parameters:**
- `limit` (optional): Number of alerts to return (1-500, default: 50)
- `severity` (optional): Filter by severity (info, warning, error, critical)

### Get Alert Thresholds

```http
GET /api/monitoring/alerts/thresholds
```

Returns configured alert thresholds:

```json
{
    "degradation_rate_critical": 50.0,
    "degradation_rate_warning": 25.0,
    "validation_rate_error": 50.0,
    "validation_rate_warning": 70.0
}
```

### Test Alert System

```http
POST /api/monitoring/alerts/test?severity=info
```

Sends a test alert to verify handler configuration.

### Check Thresholds

```http
POST /api/monitoring/alerts/check-thresholds
```

Manually trigger threshold checks and send alerts if exceeded.

### Get Monitoring Status

```http
GET /api/monitoring/status
```

Returns comprehensive monitoring system status including metrics, database health, and recent alerts.

## Alert System

### Alert Severity Levels

1. **INFO** - Informational messages
2. **WARNING** - Potential issues requiring attention
3. **ERROR** - Error conditions affecting operations
4. **CRITICAL** - Critical failures requiring immediate action

### Default Thresholds

| Metric | Warning | Error | Critical |
|--------|---------|-------|----------|
| Degradation Rate | 25% | - | 50% |
| Validation Rate | 70% | 50% | - |

### Configuring Alert Handlers

#### Console Handler (Default)

```python
from monitoring.alerts import alert_manager, console_alert_handler

# Console handler prints to stdout
alert_manager.register_handler(console_alert_handler)
```

#### Log File Handler

```python
from monitoring.alerts import alert_manager, log_file_alert_handler

# Writes alerts to /tmp/alerts.log
alert_manager.register_handler(log_file_alert_handler)
```

#### Custom Email Handler

```python
import smtplib
from email.message import EmailMessage
from monitoring.alerts import alert_manager, Alert

def email_alert_handler(alert: Alert):
    """Send email for critical alerts"""
    if alert.severity.value not in ['error', 'critical']:
        return

    msg = EmailMessage()
    msg['Subject'] = f'[{alert.severity.value.upper()}] System Alert'
    msg['From'] = 'alerts@example.com'
    msg['To'] = 'admin@example.com'
    msg.set_content(f"""
    Alert: {alert.message}
    Time: {alert.timestamp}
    Context: {alert.context}
    """)

    with smtplib.SMTP('localhost') as server:
        server.send_message(msg)

alert_manager.register_handler(email_alert_handler)
```

#### Custom Webhook Handler

```python
import requests
from monitoring.alerts import alert_manager, Alert

def webhook_alert_handler(alert: Alert):
    """Send alerts to webhook endpoint"""
    webhook_url = "https://hooks.example.com/alerts"

    payload = {
        'severity': alert.severity.value,
        'message': alert.message,
        'timestamp': alert.timestamp.isoformat(),
        'context': alert.context
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Webhook alert failed: {e}")

alert_manager.register_handler(webhook_alert_handler)
```

## Integration Guide

### Recording Session Start

```python
from monitoring.metrics_collector import metrics_collector

# When a monitoring session starts
metrics_collector.record_session_start(
    session_id="session_20250119_143022",
    timing_degraded=False,  # From timing verification
    timing_verified=True     # Whether timing was successfully verified
)
```

### Recording Detections

```python
from monitoring.metrics_collector import metrics_collector

# When a detection is saved
metrics_collector.record_detection(
    session_id="session_20250119_143022",
    usable_for_validation=True  # Based on timing quality
)
```

### Periodic Health Checks

```python
from monitoring.alerts import alert_manager
from monitoring.metrics_collector import metrics_collector

# Run periodic checks (e.g., every 5 minutes)
def periodic_health_check():
    alert_manager.check_all_thresholds(metrics_collector)

# Or check individual thresholds
alert_manager.check_timing_degradation_rate(metrics_collector)
alert_manager.check_validation_rate(metrics_collector)
```

### Custom Threshold Configuration

```python
from monitoring.alerts import alert_manager

# Update thresholds dynamically
alert_manager.set_threshold('degradation_rate_critical', 40.0)
alert_manager.set_threshold('validation_rate_error', 60.0)
```

## Dashboard Usage

### Viewing Global Health

Access the monitoring status dashboard:

```bash
curl http://localhost:8000/api/monitoring/status
```

### Monitoring Specific Sessions

```bash
# Get metrics for a session
curl http://localhost:8000/api/monitoring/metrics/session/session_20250119_143022

# Get recent sessions
curl http://localhost:8000/api/monitoring/metrics/sessions/recent?limit=5
```

### Viewing Alerts

```bash
# Get all recent alerts
curl http://localhost:8000/api/monitoring/alerts?limit=100

# Get only critical alerts
curl http://localhost:8000/api/monitoring/alerts?severity=critical

# Get only errors and critical
curl http://localhost:8000/api/monitoring/alerts?severity=error
```

## Troubleshooting

### No Metrics Appearing

**Problem**: Metrics not being collected

**Solution**:
1. Verify metrics collector is imported and initialized
2. Check that `record_session_start()` is called when sessions begin
3. Confirm `record_detection()` is called for each detection
4. Check logs for errors in metrics collection

```python
# Enable debug logging
import logging
logging.getLogger('monitoring').setLevel(logging.DEBUG)
```

### Alerts Not Firing

**Problem**: Alerts not being sent when thresholds exceeded

**Solution**:
1. Verify alert handlers are registered
2. Check threshold configuration
3. Manually trigger threshold check
4. Review alert handler logs

```bash
# Test alert system
curl -X POST http://localhost:8000/api/monitoring/alerts/test?severity=warning

# Manually trigger checks
curl -X POST http://localhost:8000/api/monitoring/alerts/check-thresholds
```

### High Degradation Rate

**Problem**: Many sessions showing timing degradation

**Root Causes**:
1. Hardware timing issues (check LabJack connections)
2. System resource contention (high CPU/memory usage)
3. USB bandwidth saturation
4. Timing verification configuration errors

**Investigation Steps**:
1. Check database health: `GET /api/monitoring/health/database`
2. Review recent sessions: `GET /api/monitoring/metrics/sessions/recent`
3. Examine session-specific metrics for patterns
4. Check system logs for timing-related errors
5. Verify LabJack device firmware and configuration

### Low Validation Rate

**Problem**: Many detections marked as unusable

**Root Causes**:
1. Degraded timing affecting detection quality
2. Detection threshold too sensitive
3. Environmental noise

**Investigation Steps**:
1. Check global metrics for degradation rate correlation
2. Review individual session metrics
3. Examine detection timing data
4. Adjust detection thresholds if needed

## Best Practices

### 1. Regular Monitoring

- Set up automated threshold checks every 5-10 minutes
- Review global metrics daily
- Investigate anomalies promptly

### 2. Alert Handler Configuration

- Use multiple handlers for redundancy
- Configure email/webhook for critical alerts
- Keep console handler for development
- Test handlers regularly

### 3. Threshold Tuning

- Start with conservative thresholds
- Adjust based on baseline performance
- Document threshold changes
- Monitor false positive rate

### 4. Metrics Retention

- Export metrics periodically for long-term analysis
- Clear old data to prevent memory growth
- Archive important session data

### 5. Performance Optimization

- Use async alert handlers to avoid blocking
- Batch database queries in metrics collection
- Implement metrics aggregation for high-volume systems
- Consider time-series database for large deployments

## Example Workflows

### Basic Setup

```python
from monitoring import metrics_collector, alert_manager
from monitoring.alerts import console_alert_handler, log_file_alert_handler

# Register alert handlers
alert_manager.register_handler(console_alert_handler)
alert_manager.register_handler(log_file_alert_handler)

# Record session
metrics_collector.record_session_start(
    session_id="test_session",
    timing_degraded=False,
    timing_verified=True
)

# Record detections
for _ in range(10):
    metrics_collector.record_detection("test_session", usable_for_validation=True)

# Check health
alert_manager.check_all_thresholds(metrics_collector)

# View results
print(metrics_collector.get_global_summary())
```

### Production Monitoring

```python
import schedule
from monitoring import metrics_collector, alert_manager

def periodic_health_check():
    """Run every 5 minutes"""
    alert_manager.check_all_thresholds(metrics_collector)

    metrics = metrics_collector.get_global_summary()
    logger.info(f"Health check - Degradation: {metrics['degradation_rate']:.1f}%, "
                f"Validation: {metrics['validation_rate']:.1f}%")

# Schedule periodic checks
schedule.every(5).minutes.do(periodic_health_check)

# Run scheduler
while True:
    schedule.run_pending()
    time.sleep(1)
```

## References

- Metrics Collector: `/backend/monitoring/metrics_collector.py`
- Alert Manager: `/backend/monitoring/alerts.py`
- API Endpoints: `/backend/routers/monitoring.py`
- Integration Examples: `/backend/monitoring/integration.py`
