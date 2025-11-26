# Configuration Guide - Quality Tracking System

**Version**: 1.0.0
**Last Updated**: 2025-11-19

---

## Quick Start

### Minimum Configuration

Create `.env` file with these essentials:

```bash
# Database (required)
DATABASE_URL=postgresql://user:password@localhost:5432/validation_platform

# CORS (required for frontend)
CORS_ORIGINS=["http://localhost:3000"]

# Quality tracking (recommended)
ENABLE_AUTO_METRICS=true
ALERT_CONSOLE_ENABLED=true
ALERT_FILE_ENABLED=true
```

That's it! Default values work for most use cases.

---

## Environment Variables

### Database Configuration

```bash
# PostgreSQL (production)
DATABASE_URL=postgresql://user:password@host:5432/dbname

# SQLite (development)
DATABASE_URL=sqlite:///./dev_database.db

# Pool settings (optional - good defaults exist)
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
```

---

### CORS Configuration

```bash
# Development
CORS_ORIGINS=["http://localhost:3000"]

# Production (multiple origins)
CORS_ORIGINS=["https://app.yourcompany.com", "https://www.yourcompany.com"]

# Advanced
CORS_CREDENTIALS=true
CORS_METHODS=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
CORS_HEADERS=["*"]
```

---

### Metrics & Monitoring

```bash
# Auto-metrics collection (optional)
ENABLE_AUTO_METRICS=true  # Automatic metric collection from API calls

# Background monitoring intervals (seconds)
POOL_CHECK_INTERVAL=60        # Database pool health check
METRICS_CHECK_INTERVAL=300    # Metrics summary logging
THRESHOLD_CHECK_INTERVAL=600  # Alert threshold checks
```

---

### Security

```bash
# UUID validation (recommended for production)
ENABLE_UUID_VALIDATION=true

# Rate limiting (recommended for production)
ENABLE_RATE_LIMITING=true
RATE_LIMIT_REQUESTS=100   # Requests per window
RATE_LIMIT_WINDOW=60      # Window in seconds
```

---

### Alert Handlers

#### Console Alerts (always enabled)

```bash
ALERT_CONSOLE_ENABLED=true
ALERT_CONSOLE_MIN_SEVERITY=info  # info|warning|error|critical
```

#### File Alerts

```bash
ALERT_FILE_ENABLED=true
ALERT_FILE_PATH=logs/alerts.log
ALERT_FILE_MIN_SEVERITY=warning
```

#### Email Alerts

```bash
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_SMTP_HOST=smtp.gmail.com
ALERT_EMAIL_SMTP_PORT=587
ALERT_EMAIL_FROM=alerts@yourcompany.com
ALERT_EMAIL_TO=admin@yourcompany.com
ALERT_EMAIL_USERNAME=alerts@yourcompany.com
ALERT_EMAIL_PASSWORD=your_app_password
ALERT_EMAIL_MIN_SEVERITY=error
```

**Gmail App Password Setup**:
1. Enable 2-factor authentication on Google account
2. Go to https://myaccount.google.com/apppasswords
3. Create app password for "Mail"
4. Use this password in `ALERT_EMAIL_PASSWORD`

#### Slack Alerts

```bash
ALERT_SLACK_ENABLED=true
ALERT_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK
ALERT_SLACK_CHANNEL=#system-alerts
ALERT_SLACK_MIN_SEVERITY=warning
```

**Slack Webhook Setup**:
1. Go to https://api.slack.com/apps
2. Create new app or select existing
3. Add "Incoming Webhooks" feature
4. Activate webhooks and create webhook for channel
5. Copy webhook URL

#### Webhook Alerts

```bash
ALERT_WEBHOOK_ENABLED=true
ALERT_WEBHOOK_URL=https://your-monitoring-system.com/alerts
ALERT_WEBHOOK_TOKEN=your_auth_token
ALERT_WEBHOOK_MIN_SEVERITY=warning
```

---

### Alert Thresholds

```bash
# Quality thresholds (percentage)
ALERT_DEGRADATION_THRESHOLD=25.0   # % of degraded detections
ALERT_VALIDATION_THRESHOLD=75.0    # % of usable detections (minimum)
ALERT_TIMING_THRESHOLD=50.0        # % of sessions with timing issues

# Performance thresholds
ALERT_POOL_UTILIZATION=80.0        # % database pool usage
ALERT_RESPONSE_TIME_MS=1000        # API response time threshold
ALERT_ERROR_RATE=5.0               # % error rate threshold
```

**Tuning Recommendations**:
- **Strict**: Lower degradation threshold (15%), higher validation threshold (90%)
- **Lenient**: Higher degradation threshold (35%), lower validation threshold (60%)
- **Default** (recommended): 25% / 75% balances alerting vs noise

---

## Configuration Templates

### Development Environment

```bash
# .env.development
DATABASE_URL=sqlite:///./dev_database.db
CORS_ORIGINS=["http://localhost:3000"]
ENABLE_AUTO_METRICS=true
ALERT_CONSOLE_ENABLED=true
ALERT_FILE_ENABLED=true
ALERT_FILE_PATH=logs/alerts.log
ALERT_DEGRADATION_THRESHOLD=25.0
ALERT_VALIDATION_THRESHOLD=75.0
```

### Production Environment

```bash
# .env.production
DATABASE_URL=postgresql://user:password@db.yourcompany.com:5432/validation_platform
CORS_ORIGINS=["https://app.yourcompany.com"]
ENABLE_AUTO_METRICS=true
ENABLE_UUID_VALIDATION=true
ENABLE_RATE_LIMITING=true

# Console alerts
ALERT_CONSOLE_ENABLED=true
ALERT_CONSOLE_MIN_SEVERITY=info

# File alerts
ALERT_FILE_ENABLED=true
ALERT_FILE_PATH=/var/log/validation-platform/alerts.log
ALERT_FILE_MIN_SEVERITY=warning

# Email alerts
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_SMTP_HOST=smtp.gmail.com
ALERT_EMAIL_SMTP_PORT=587
ALERT_EMAIL_FROM=alerts@yourcompany.com
ALERT_EMAIL_TO=ops-team@yourcompany.com
ALERT_EMAIL_USERNAME=alerts@yourcompany.com
ALERT_EMAIL_PASSWORD=${EMAIL_PASSWORD}
ALERT_EMAIL_MIN_SEVERITY=error

# Slack alerts
ALERT_SLACK_ENABLED=true
ALERT_SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
ALERT_SLACK_CHANNEL=#production-alerts
ALERT_SLACK_MIN_SEVERITY=warning

# Thresholds
ALERT_DEGRADATION_THRESHOLD=20.0
ALERT_VALIDATION_THRESHOLD=85.0
ALERT_TIMING_THRESHOLD=40.0
ALERT_POOL_UTILIZATION=75.0
```

### Docker Environment

```bash
# .env.docker
DATABASE_URL=postgresql://postgres:postgres@db:5432/validation_platform
CORS_ORIGINS=["http://frontend:3000"]
ENABLE_AUTO_METRICS=true
ALERT_CONSOLE_ENABLED=true
ALERT_FILE_ENABLED=true
ALERT_FILE_PATH=/app/logs/alerts.log
```

---

## Alert Severity Levels

| Level | When to Use | Example |
|-------|-------------|---------|
| `info` | Informational messages | Health check passed, system started |
| `warning` | Issues that need attention | Quality degrading, high pool usage |
| `error` | Errors requiring action | Database connection failed, API errors |
| `critical` | Urgent issues | Service down, data corruption |

**Filtering Recommendations**:
- **Console**: `info` (see everything during development)
- **File**: `warning` (persistent log of issues)
- **Email**: `error` (only serious issues)
- **Slack**: `warning` (team needs to know)

---

## Testing Configuration

### Test Alert Handlers

```bash
# Test console alerts (watch logs)
curl -X POST "http://localhost:8000/api/monitoring/alerts/test?severity=info"

# Test file alerts (check log file)
curl -X POST "http://localhost:8000/api/monitoring/alerts/test?severity=warning"
tail -f logs/alerts.log

# Test email alerts (check inbox)
curl -X POST "http://localhost:8000/api/monitoring/alerts/test?severity=error&message=Test%20email"

# Test Slack alerts (check channel)
curl -X POST "http://localhost:8000/api/monitoring/alerts/test?severity=warning&message=Test%20Slack"
```

### Verify Configuration

```bash
# Check which handlers are active
curl http://localhost:8000/api/monitoring/status | jq '.monitoring.alert_handlers'

# Check current thresholds
curl http://localhost:8000/api/monitoring/alerts/thresholds | jq
```

---

## Best Practices

### Security

1. **Never commit `.env` files** to version control
2. **Use environment-specific files** (`.env.development`, `.env.production`)
3. **Rotate credentials regularly** (email passwords, API keys)
4. **Use secrets management** (Vault, AWS Secrets Manager) in production

### Performance

1. **Tune pool sizes** based on load (higher for more concurrent users)
2. **Adjust check intervals** based on need (less frequent for stable systems)
3. **Monitor metrics** to find optimal thresholds

### Monitoring

1. **Start with default thresholds** and adjust based on actual data
2. **Review alerts weekly** to reduce noise
3. **Document threshold changes** and reasoning

---

## Troubleshooting

### Problem: Alerts not sending

**Check**:
```bash
# Verify handler is enabled
python -c "import os; print('Enabled:', os.getenv('ALERT_FILE_ENABLED'))"

# Check logs for errors
tail -f logs/backend.log | grep -i "alert"

# Test specific handler
curl -X POST "http://localhost:8000/api/monitoring/alerts/test"
```

### Problem: Too many alerts

**Solution**: Increase thresholds

```bash
# In .env
ALERT_DEGRADATION_THRESHOLD=35.0  # Was 25.0
ALERT_VALIDATION_THRESHOLD=65.0   # Was 75.0
```

### Problem: Missing alerts

**Solution**: Lower thresholds or change severity filtering

```bash
# Lower thresholds
ALERT_DEGRADATION_THRESHOLD=15.0

# Or change minimum severity
ALERT_FILE_MIN_SEVERITY=info  # Was warning
```

---

**Configuration Guide Version**: 1.0.0
**Last Updated**: 2025-11-19
