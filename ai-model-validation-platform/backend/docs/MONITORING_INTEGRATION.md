# Monitoring System Integration Guide

## Adding Monitoring Router to Main Application

### Step 1: Update main.py

Add these imports near the top of `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`:

```python
# Import monitoring router
try:
    from routers.monitoring import router as monitoring_router
    print("✅ Monitoring router loaded")
except ImportError as e:
    print(f"Warning: monitoring router not available: {e}")
    monitoring_router = None
```

### Step 2: Register Router

Add this line with the other `app.include_router()` calls (around line 740):

```python
# Register monitoring router
if monitoring_router:
    app.include_router(monitoring_router)
    print("✅ Monitoring endpoints registered at /api/monitoring")
```

### Step 3: Setup Alert Handlers (Optional)

Add startup event handler to register alert handlers from environment:

```python
@app.on_event("startup")
async def setup_monitoring_system():
    """Setup monitoring and alert handlers on application startup"""
    try:
        from monitoring.example_handlers import register_handlers_from_env
        handlers_count = register_handlers_from_env()

        if handlers_count > 0:
            logger.info(f"✅ Monitoring system initialized with {handlers_count} alert handler(s)")
        else:
            logger.info("✅ Monitoring system initialized (no alert handlers configured)")
    except Exception as e:
        logger.error(f"Failed to setup monitoring system: {e}")
```

### Step 4: Integrate with LabJack Monitor (Optional)

If you want automatic metrics collection for LabJack monitoring sessions, add to your LabJack monitor initialization:

```python
from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
from monitoring.labjack_monitor_integration import integrate_monitoring_with_labjack_monitor

# Create or get monitor instance
monitor = DedicatedLabJackMonitor()

# Integrate monitoring (automatically patches methods)
integrate_monitoring_with_labjack_monitor(monitor)

logger.info("✅ LabJack monitor integrated with monitoring system")
```

### Step 5: Add Periodic Health Checks (Optional)

For automatic threshold checking, add a background task:

```python
import schedule
import threading
from monitoring.integration import run_health_check

def health_check_scheduler():
    """Background thread for periodic health checks"""
    schedule.every(5).minutes.do(run_health_check)

    while True:
        schedule.run_pending()
        time.sleep(1)

# Start scheduler on application startup
@app.on_event("startup")
async def start_health_monitoring():
    health_thread = threading.Thread(target=health_check_scheduler, daemon=True)
    health_thread.start()
    logger.info("✅ Health monitoring scheduler started (5 minute intervals)")
```

## Complete Integration Example

Here's a complete example of all integration points:

```python
# In main.py

# Imports (at top of file)
try:
    from routers.monitoring import router as monitoring_router
    from monitoring.example_handlers import register_handlers_from_env
    from monitoring.integration import run_health_check
    print("✅ Monitoring system imported")
except ImportError as e:
    monitoring_router = None
    print(f"⚠️ Monitoring system not available: {e}")

# Router registration (with other routers)
if monitoring_router:
    app.include_router(monitoring_router)
    logger.info("✅ Monitoring endpoints available at /api/monitoring/*")

# Startup configuration
@app.on_event("startup")
async def configure_monitoring_system():
    """Configure monitoring system with alert handlers and health checks"""
    if not monitoring_router:
        return

    try:
        # Register alert handlers from environment
        handlers_count = register_handlers_from_env()
        logger.info(f"✅ Registered {handlers_count} alert handler(s)")

        # Start health check scheduler
        import schedule
        import threading

        def health_scheduler():
            schedule.every(5).minutes.do(run_health_check)
            while True:
                schedule.run_pending()
                time.sleep(1)

        health_thread = threading.Thread(target=health_scheduler, daemon=True)
        health_thread.start()
        logger.info("✅ Health monitoring active (5min intervals)")

    except Exception as e:
        logger.error(f"Failed to configure monitoring: {e}")
```

## Verifying Integration

### Test API Endpoints

```bash
# Check if monitoring endpoints are available
curl http://localhost:8000/api/monitoring/status

# Get global metrics
curl http://localhost:8000/api/monitoring/metrics/global

# Get database health
curl http://localhost:8000/api/monitoring/health/database

# Get recent alerts
curl http://localhost:8000/api/monitoring/alerts?limit=10
```

### Test Alert System

```bash
# Send test alert
curl -X POST http://localhost:8000/api/monitoring/alerts/test?severity=info
```

### Check Logs

Look for these messages in application logs:

```
✅ Monitoring router loaded
✅ Monitoring endpoints registered at /api/monitoring
✅ Monitoring system initialized with X alert handler(s)
✅ Health monitoring scheduler started
```

## Environment Variables

Configure alert handlers via environment variables:

```bash
# Email alerts
export ALERT_EMAIL_SMTP_HOST=smtp.gmail.com
export ALERT_EMAIL_SMTP_PORT=587
export ALERT_EMAIL_FROM=alerts@example.com
export ALERT_EMAIL_TO=admin@example.com
export ALERT_EMAIL_USERNAME=your_username
export ALERT_EMAIL_PASSWORD=your_password
export ALERT_EMAIL_MIN_SEVERITY=warning

# Webhook alerts
export ALERT_WEBHOOK_URL=https://hooks.example.com/alerts
export ALERT_WEBHOOK_TOKEN=your_token
export ALERT_WEBHOOK_MIN_SEVERITY=info

# Slack alerts
export ALERT_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK
export ALERT_SLACK_CHANNEL=#alerts
export ALERT_SLACK_MIN_SEVERITY=warning
```

## Troubleshooting

### Issue: Router Not Loading

```
Warning: monitoring router not available
```

**Solution**: Ensure monitoring package is in Python path and all dependencies are installed:

```bash
pip install -r requirements.txt
```

### Issue: No Alert Handlers Registered

```
⚠️ No alert handlers configured via environment variables
```

**Solution**: Set environment variables for at least one handler type (email, webhook, or Slack).

### Issue: Health Checks Not Running

**Solution**: Check that scheduler thread started:

```python
import logging
logging.getLogger('monitoring').setLevel(logging.DEBUG)
```

## Next Steps

1. Configure environment variables for alert handlers
2. Test endpoints to verify integration
3. Monitor logs for metrics and alerts
4. Integrate with existing monitoring dashboards
5. Set up production alert routing

## Support

- See `/docs/MONITORING_GUIDE.md` for comprehensive documentation
- Check `/monitoring/README.md` for quick reference
- Review `/tests/monitoring/` for usage examples
