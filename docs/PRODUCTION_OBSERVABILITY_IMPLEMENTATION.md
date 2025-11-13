# Production Observability Implementation Guide

**Implementation Date:** 2025-11-11
**Status:** Complete
**Components:** Logging, Metrics, Health Checks, Performance Monitoring, Error Tracking, Audit Logs

---

## Overview

This document describes the production-grade observability infrastructure implemented for the HIL test validation platform. All components follow enterprise best practices for monitoring, debugging, and compliance.

---

## Components Implemented

### 1. Structured Logging (`backend/utils/logging_config.py`)

**Features:**
- JSON-formatted logs for ELK/CloudWatch/Splunk
- Request correlation IDs for distributed tracing
- Automatic context enrichment (session_id, user_id, etc.)
- Multiple log levels with structured fields
- Pre-configured loggers for common modules

**Usage:**
```python
from utils.logging_config import session_logger

session_logger.info(
    "Session completed successfully",
    session_id=session_id,
    metrics={'precision': 0.85, 'recall': 0.78},
    duration_ms=1523.4
)
```

**Log Output:**
```json
{
  "timestamp": "2025-11-11T12:00:00.000Z",
  "level": "INFO",
  "logger": "session",
  "message": "Session completed successfully",
  "correlation_id": "a1b2c3d4-...",
  "session_id": "abc-123",
  "metrics": {"precision": 0.85, "recall": 0.78},
  "duration_ms": 1523.4
}
```

### 2. Prometheus Metrics (`backend/utils/metrics.py`)

**Metrics Collected:**

| Metric | Type | Description |
|--------|------|-------------|
| `hil_session_completions_total` | Counter | Total sessions by status/outcome |
| `hil_session_duration_seconds` | Histogram | Session completion duration |
| `hil_detection_events_total` | Counter | Detection events by classification |
| `hil_detection_latency_milliseconds` | Histogram | Detection latency distribution |
| `hil_gt_matching_duration_seconds` | Histogram | Matching algorithm performance |
| `hil_api_request_duration_seconds` | Histogram | API endpoint latency |
| `hil_slow_requests_total` | Counter | Requests >1s |
| `hil_db_query_duration_seconds` | Histogram | Database query performance |
| `hil_websocket_connections_active` | Gauge | Active WebSocket connections |
| `hil_active_sessions` | Gauge | Currently running sessions |

**Usage:**
```python
from utils.metrics import (
    track_session_completion,
    detection_latency_ms,
    matching_duration_seconds
)

@track_session_completion
def complete_test_session(session_id):
    # Automatically tracked
    pass

# Manual recording
detection_latency_ms.observe(latency_ms)
matching_duration_seconds.observe(duration_seconds)
```

### 3. Health Check Endpoints (`backend/routers/health.py`)

**Endpoints:**

| Endpoint | Purpose | Use Case |
|----------|---------|----------|
| `GET /health/live` | Liveness probe | Kubernetes restart |
| `GET /health/ready` | Readiness probe | Load balancer routing |
| `GET /health/health` | Comprehensive health | Monitoring dashboards |
| `GET /health/metrics` | Prometheus scrape | Metrics collection |
| `GET /health/info` | System information | Deployment verification |

**Example Response (`/health/health`):**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-11T12:00:00.000Z",
  "checks": {
    "database": {"status": "ok", "query_time_ms": 2.34},
    "websocket": {"status": "ok"},
    "memory": {"status": "ok"},
    "disk": {"status": "ok"},
    "cpu": {"status": "ok"}
  },
  "metrics": {
    "memory": {
      "total_mb": 16384,
      "available_mb": 8192,
      "percent_used": 50.0
    },
    "disk": {
      "total_gb": 500,
      "free_gb": 250,
      "percent_used": 50.0
    },
    "cpu_percent": 25.5,
    "database_size_mb": 1024.5
  }
}
```

### 4. Performance Monitoring Middleware (`backend/middleware/performance.py`)

**Features:**
- Automatic request duration tracking
- Slow request detection and logging (>1s)
- Prometheus metrics integration
- Correlation ID generation
- Performance headers in responses

**Response Headers:**
```
X-Request-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
X-Response-Time: 234.56ms
```

**Integration:**
```python
# main.py
from middleware.performance import PerformanceMiddleware

app.add_middleware(
    PerformanceMiddleware,
    slow_threshold_seconds=1.0
)
```

### 5. Error Tracking (`backend/utils/error_tracking.py`)

**Features:**
- Sentry integration for exception aggregation
- Performance transaction tracking
- Custom context and tags
- Breadcrumb trail for debugging
- Automatic stack trace capture

**Usage:**
```python
from utils.error_tracking import (
    capture_exception,
    add_breadcrumb,
    set_session_context,
    start_transaction
)

# Set context
set_session_context(session_id, {'video_count': 3})

# Track performance
with start_transaction("session_completion", op="task") as transaction:
    try:
        # Add debug breadcrumbs
        add_breadcrumb(
            "Starting ground truth matching",
            category="matching",
            data={'tolerance_ms': 100}
        )

        result = match_detections(session_id)

    except Exception as e:
        capture_exception(
            e,
            context={'session_id': session_id},
            tags={'component': 'matching'}
        )
        raise
```

**Environment Variables:**
```bash
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
ENVIRONMENT=production
RELEASE_VERSION=v1.2.3
```

### 6. Audit Log System (`backend/models_audit.py`)

**Features:**
- Complete audit trail for compliance
- Who/what/when/where tracking
- Before/after state capture
- Request correlation
- Success/failure recording

**Schema:**
```sql
CREATE TABLE audit_logs (
    id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    user_id VARCHAR,
    user_email VARCHAR,
    action VARCHAR NOT NULL,
    resource_type VARCHAR NOT NULL,
    resource_id VARCHAR NOT NULL,
    changes JSONB,
    metadata JSONB,
    ip_address VARCHAR,
    user_agent VARCHAR,
    correlation_id VARCHAR,
    session_id VARCHAR,
    success INTEGER DEFAULT 1,
    error_message VARCHAR
);
```

**Usage:**
```python
from models_audit import AuditLog, AuditAction, ResourceType

def log_audit(db, action, resource_type, resource_id, changes, user_id):
    audit = AuditLog(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        changes=changes,
        user_id=user_id,
        correlation_id=get_correlation_id()
    )
    db.add(audit)
    db.commit()

# Example: Session approval
log_audit(
    db,
    action=AuditAction.SESSION_APPROVED,
    resource_type=ResourceType.TEST_SESSION,
    resource_id=session_id,
    changes={
        'before': {'approval_status': 'pending'},
        'after': {'approval_status': 'approved'}
    },
    user_id=current_user.id
)
```

### 7. Alerting Configuration (`config/alerts.yaml`)

**Alert Severities:**
- **Critical**: Immediate action required (database down, memory exhaustion)
- **High**: Action required within hours (timeouts, slow queries)
- **Warning**: Investigate when convenient (disk space, slow requests)
- **Info**: Awareness only (low pass rate, elevated latency)

**Example Alerts:**
```yaml
- name: high_validation_failure_rate
  severity: critical
  condition: |
    rate(hil_session_completions_total{status="validation_failed"}[1h]) /
    rate(hil_session_completions_total[1h]) > 0.20
  duration: 5m
  actions:
    - page_oncall
    - post_to_slack

- name: slow_matching_algorithm
  severity: high
  condition: |
    histogram_quantile(0.95, rate(hil_gt_matching_duration_seconds_bucket[5m])) > 5
  duration: 5m
  actions:
    - post_to_slack
    - create_incident
```

---

## Integration Guide

### Step 1: Initialize Logging in Main Application

```python
# backend/main.py
from utils.logging_config import api_logger
from middleware.performance import PerformanceMiddleware

# Add performance middleware
app.add_middleware(PerformanceMiddleware, slow_threshold_seconds=1.0)

# Log startup
api_logger.info("HIL Backend starting", version="1.0.0", environment="production")
```

### Step 2: Add Health Check Router

```python
# backend/main.py
from routers import health

app.include_router(health.router)
```

### Step 3: Initialize Error Tracking

```python
# backend/main.py
from utils.error_tracking import init_error_tracking

init_error_tracking(
    environment="production",
    release="v1.2.3",
    traces_sample_rate=0.1
)
```

### Step 4: Create Audit Log Table

```sql
-- Run migration
python -m alembic revision --autogenerate -m "add_audit_logs"
python -m alembic upgrade head
```

### Step 5: Instrument Services

```python
# backend/services/session_completion_service.py
from utils.logging_config import session_logger
from utils.metrics import track_session_completion, session_duration_seconds
from utils.error_tracking import capture_exception, add_breadcrumb
from models_audit import log_audit, AuditAction, ResourceType

@track_session_completion
def complete_test_session(session_id: str, db, user_id: str = None):
    session_logger.info("Session completion started", session_id=session_id)

    try:
        add_breadcrumb("Validating session", data={'session_id': session_id})

        # ... completion logic ...

        # Log audit
        log_audit(
            db,
            action=AuditAction.SESSION_COMPLETED,
            resource_type=ResourceType.TEST_SESSION,
            resource_id=session_id,
            changes={'before': {'status': 'running'}, 'after': {'status': 'completed'}},
            user_id=user_id
        )

        session_logger.info(
            "Session completed successfully",
            session_id=session_id,
            metrics={'precision': session.precision, 'recall': session.recall}
        )

    except Exception as e:
        capture_exception(
            e,
            context={'session_id': session_id},
            tags={'component': 'session_completion'}
        )
        session_logger.error(
            "Session completion failed",
            exc_info=True,
            session_id=session_id
        )
        raise
```

### Step 6: Configure Prometheus Scraping

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'hil-backend'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/health/metrics'
```

### Step 7: Configure Alerting

```yaml
# alertmanager.yml
global:
  slack_api_url: ${SLACK_WEBHOOK_URL}

route:
  receiver: 'default'
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

receivers:
  - name: 'default'
    slack_configs:
      - channel: '#hil-alerts'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
```

---

## Monitoring Dashboards

### Grafana Dashboard - Session Performance

**Panels:**
1. Session completion rate (success/fail)
2. Mean session duration
3. Active sessions gauge
4. Validation failure breakdown
5. Detection latency histogram
6. API request rate by endpoint
7. Database query performance

### Grafana Dashboard - Business KPIs

**Panels:**
1. Test pass rate (24h rolling)
2. Mean precision/recall/F1
3. Detection classification distribution (TP/FP/FN)
4. Latency within tolerance percentage
5. Sessions per hour
6. Ground truth matching performance

---

## Production Readiness Checklist

- ✅ Structured JSON logging implemented
- ✅ Prometheus metrics instrumented
- ✅ Health check endpoints created
- ✅ Performance monitoring middleware added
- ✅ Error tracking (Sentry) integrated
- ✅ Audit log system implemented
- ✅ Alert rules configured
- ✅ Monitoring dashboards defined

---

## Environment Variables Required

```bash
# Error Tracking
SENTRY_DSN=https://your-dsn@sentry.io/project-id
ENVIRONMENT=production
RELEASE_VERSION=v1.2.3

# Alerting
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
PAGERDUTY_SERVICE_KEY=...

# Database
DATABASE_URL=postgresql://user:pass@localhost/hil_db
```

---

## Runbook References

- **High Validation Failure Rate**: Investigate session configuration, ground truth quality
- **Database Connectivity Lost**: Check PostgreSQL status, connection pool
- **Memory Exhaustion**: Review active sessions, restart application
- **Slow Matching Algorithm**: Check detection count, database indexes
- **Race Conditions**: Review video lifecycle event timing

---

## Next Steps

1. **Deploy to staging** - Test all observability components
2. **Configure Grafana dashboards** - Import dashboard JSON templates
3. **Set up Prometheus** - Configure scraping and retention
4. **Enable Sentry** - Create project and obtain DSN
5. **Test alerting** - Trigger test alerts to verify routing
6. **Train team** - Document how to use logs, metrics, and dashboards

---

**Implementation Complete**: All production observability components ready for deployment.
