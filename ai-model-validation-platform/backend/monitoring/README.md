# Monitoring & Alerting System

Complete monitoring and alerting infrastructure for timing quality and system health.

## 📁 Directory Structure

```
monitoring/
├── __init__.py                     # Package initialization
├── metrics_collector.py            # Core metrics collection
├── alerts.py                       # Alert management system
├── integration.py                  # Integration helpers
├── labjack_monitor_integration.py  # LabJack-specific integration
├── example_handlers.py             # Email, webhook, Slack handlers
└── README.md                       # This file

routers/
└── monitoring.py                   # API endpoints

tests/monitoring/
├── __init__.py
├── test_metrics_collector.py       # Metrics collection tests
└── test_alerts.py                  # Alert system tests

docs/
└── MONITORING_GUIDE.md             # Comprehensive documentation
```

## 🚀 Quick Start

### 1. Import and Use

```python
from monitoring import metrics_collector, alert_manager

# Record session start
metrics_collector.record_session_start(
    session_id="session_123",
    timing_degraded=False,
    timing_verified=True
)

# Record detections
metrics_collector.record_detection(
    session_id="session_123",
    usable_for_validation=True
)

# Check health
from monitoring.integration import run_health_check
run_health_check()
```

### 2. Register Alert Handlers

```python
from monitoring.alerts import alert_manager
from monitoring.example_handlers import (
    create_email_handler_from_env,
    create_webhook_handler_from_env,
    create_slack_handler_from_env
)

# Register handlers from environment variables
email_handler = create_email_handler_from_env()
if email_handler:
    alert_manager.register_handler(email_handler)

webhook_handler = create_webhook_handler_from_env()
if webhook_handler:
    alert_manager.register_handler(webhook_handler)

slack_handler = create_slack_handler_from_env()
if slack_handler:
    alert_manager.register_handler(slack_handler)
```

### 3. API Endpoints

```bash
# Get global metrics
GET /api/monitoring/metrics/global

# Get session metrics
GET /api/monitoring/metrics/session/{session_id}

# Get recent sessions
GET /api/monitoring/metrics/sessions/recent?limit=10

# Get database health
GET /api/monitoring/health/database

# Get alerts
GET /api/monitoring/alerts?limit=50&severity=error

# Check thresholds
POST /api/monitoring/alerts/check-thresholds

# Get monitoring status
GET /api/monitoring/status
```

## 📊 Metrics Collected

### Session Metrics
- Session timing quality (degraded/verified)
- Detection counts (total, validated, degraded)
- Validation rate
- Degradation rate

### Global Metrics
- Total sessions
- Degraded sessions count
- Total detections
- Validated detections
- System-wide degradation rate
- System-wide validation rate

## 🚨 Alert System

### Severity Levels
- **INFO**: Informational messages
- **WARNING**: Potential issues
- **ERROR**: Error conditions
- **CRITICAL**: Critical failures

### Default Thresholds
- **Degradation Rate Critical**: 50%
- **Degradation Rate Warning**: 25%
- **Validation Rate Error**: 50%
- **Validation Rate Warning**: 70%

### Available Handlers
- **Console**: Print to stdout
- **Log File**: Write to file
- **Email**: SMTP email notifications
- **Webhook**: HTTP POST to endpoint
- **Slack**: Slack channel notifications

## 🔧 Configuration

### Environment Variables

#### Email Alerts
```bash
ALERT_EMAIL_SMTP_HOST=smtp.gmail.com
ALERT_EMAIL_SMTP_PORT=587
ALERT_EMAIL_FROM=alerts@example.com
ALERT_EMAIL_TO=admin@example.com,ops@example.com
ALERT_EMAIL_USERNAME=your_username
ALERT_EMAIL_PASSWORD=your_password
ALERT_EMAIL_USE_TLS=true
ALERT_EMAIL_MIN_SEVERITY=warning
```

#### Webhook Alerts
```bash
ALERT_WEBHOOK_URL=https://hooks.example.com/alerts
ALERT_WEBHOOK_TOKEN=your_auth_token
ALERT_WEBHOOK_MIN_SEVERITY=info
```

#### Slack Alerts
```bash
ALERT_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
ALERT_SLACK_CHANNEL=#alerts
ALERT_SLACK_USERNAME=Alert Bot
ALERT_SLACK_MIN_SEVERITY=warning
```

## 🔌 Integration with Existing Code

### Option 1: Direct Integration

```python
from monitoring.integration import record_session_start, record_detection

# When session starts
record_session_start(
    session_id=session_id,
    timing_degraded=timing_degraded,
    timing_verified=timing_verified
)

# When detection occurs
record_detection(
    session_id=session_id,
    usable_for_validation=usable_for_validation
)
```

### Option 2: LabJack Monitor Integration

```python
from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
from monitoring.labjack_monitor_integration import integrate_monitoring_with_labjack_monitor

# Create monitor
monitor = DedicatedLabJackMonitor()

# Integrate monitoring (automatically patches methods)
integrate_monitoring_with_labjack_monitor(monitor)
```

### Option 3: Periodic Health Checks

```python
import schedule
from monitoring.integration import run_health_check

# Run every 5 minutes
schedule.every(5).minutes.do(run_health_check)

# Run in background
import threading
def scheduler_thread():
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=scheduler_thread, daemon=True).start()
```

## 🧪 Testing

```bash
# Run all monitoring tests
pytest tests/monitoring/ -v

# Run specific test file
pytest tests/monitoring/test_metrics_collector.py -v
pytest tests/monitoring/test_alerts.py -v

# Run with coverage
pytest tests/monitoring/ --cov=monitoring --cov-report=html
```

## 📖 Documentation

See `/home/rigade/Testing/ai-model-validation-platform/backend/docs/MONITORING_GUIDE.md` for comprehensive documentation including:

- Available metrics
- Alert thresholds
- Dashboard usage
- Custom alert handlers
- Troubleshooting guide
- Best practices

## 🎯 Key Features

✅ **Thread-safe** metrics collection
✅ **Real-time** health monitoring
✅ **Configurable** alert thresholds
✅ **Pluggable** alert handlers
✅ **RESTful** API endpoints
✅ **Comprehensive** test coverage
✅ **Easy integration** with existing code
✅ **Production-ready** error handling

## 📝 Example Usage

```python
# Complete example
from monitoring import metrics_collector, alert_manager
from monitoring.alerts import console_alert_handler
from monitoring.integration import run_health_check
import schedule
import time

# Register console handler
alert_manager.register_handler(console_alert_handler)

# Record some data
for i in range(10):
    session_id = f"session_{i}"
    metrics_collector.record_session_start(
        session_id,
        timing_degraded=i < 2,  # 20% degraded
        timing_verified=i >= 2
    )

    for j in range(10):
        metrics_collector.record_detection(
            session_id,
            usable_for_validation=j < 8  # 80% validated
        )

# Check health
run_health_check()

# Get summary
summary = metrics_collector.get_global_summary()
print(f"Degradation rate: {summary['degradation_rate']:.1f}%")
print(f"Validation rate: {summary['validation_rate']:.1f}%")

# Schedule periodic checks
schedule.every(5).minutes.do(run_health_check)

while True:
    schedule.run_pending()
    time.sleep(1)
```

## 🛠️ Adding to Main Application

Add to `main.py`:

```python
# Import monitoring router
from routers.monitoring import router as monitoring_router

# Register router
app.include_router(monitoring_router)

# Optional: Register alert handlers on startup
@app.on_event("startup")
async def setup_monitoring():
    from monitoring.example_handlers import register_handlers_from_env
    register_handlers_from_env()
```

## 📧 Support

For issues or questions:
1. Check `/docs/MONITORING_GUIDE.md`
2. Review test files for examples
3. Check application logs
