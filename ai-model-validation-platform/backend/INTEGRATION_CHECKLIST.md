# Integration Checklist - Required Before Running main.py

**Status**: ⚠️ 3 Critical Steps Required

---

## Quick Summary

✅ **Code Written**: All fixes implemented
✅ **Models Updated**: Database schema fields added
✅ **Modules Working**: All imports successful
❌ **Router Registration**: Monitoring router not added to main.py
❌ **Database Migration**: Schema changes not applied to database
❌ **Verification**: Integration not tested

**Estimated Time**: 30 minutes

---

## Step 1: Register Monitoring Router (2 minutes)

### Add Import to main.py

Find the router imports section (around line 90) and add:

```python
# Import monitoring router
try:
    from routers.monitoring import router as monitoring_router
    print("✅ Monitoring router loaded")
except ImportError as e:
    print(f"Warning: monitoring router not available: {e}")
    monitoring_router = None
```

### Register the Router

Find where other routers are registered with `app.include_router()` and add:

```python
# Register monitoring router
if monitoring_router:
    app.include_router(monitoring_router)
```

---

## Step 2: Run Database Migrations (10 minutes)

### Option A: Using Alembic (Recommended if configured)

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
alembic upgrade head
```

### Option B: Using Manual Migration Scripts

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Apply schema changes
python3 migrations/add_detection_quality_fields.py

# Or use the comprehensive migration
python3 migrations/versions/20251119_add_timing_quality_tracking.py
```

### Verify Migration Success

```bash
python3 -c "
from database import SessionLocal
from models import TestSession, DetectionEvent

db = SessionLocal()
try:
    # Test query with new fields
    session = db.query(TestSession).first()
    if session and hasattr(session, 'timing_degraded'):
        print('✅ Migration successful - timing_degraded field exists')
    else:
        print('❌ Migration failed or no sessions exist')

    detection = db.query(DetectionEvent).first()
    if detection and hasattr(detection, 'usable_for_validation'):
        print('✅ Migration successful - usable_for_validation field exists')
    else:
        print('⚠️ No detections to check')
finally:
    db.close()
"
```

---

## Step 3: Integration Verification (15 minutes)

### Test 1: Import Verification

```bash
python3 -c "
# Test all new modules
from utils.validation import validate_uuid
from utils.security import verify_session_ownership
from utils.rate_limiter import RateLimiter
from monitoring.metrics_collector import metrics_collector
from monitoring.alerts import alert_manager
print('✅ All modules import successfully')
"
```

### Test 2: API Endpoint Check

```bash
# Start the backend
python3 main.py &
BACKEND_PID=$!

# Wait for startup
sleep 5

# Test monitoring endpoint
curl http://localhost:8000/api/monitoring/status

# Test health check
curl http://localhost:8000/api/monitoring/health/database

# Stop backend
kill $BACKEND_PID
```

### Test 3: Run Integration Tests

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-asyncio

# Run integration tests
pytest tests/integration/test_all_fixes_integration.py -v

# Run security tests
pytest tests/security/test_security_fixes.py -v
```

---

## Step 4: Production Deployment (Optional)

### Update Environment Variables

Create/update `.env` file:

```bash
# Monitoring Configuration
ENABLE_MONITORING=true
ALERT_EMAIL_TO=your-email@example.com
ALERT_WEBHOOK_URL=https://your-webhook-url.com

# Security Configuration
ENABLE_RATE_LIMITING=true
ENABLE_UUID_VALIDATION=true
```

### Restart Backend with New Configuration

```bash
# Stop current backend
pkill -f "python.*main.py"

# Start with environment
python3 main.py
```

---

## Verification Checklist

After completing all steps, verify:

- [ ] Monitoring router registered in main.py
- [ ] Database migrations applied successfully
- [ ] All imports work without errors
- [ ] Backend starts without errors
- [ ] Monitoring endpoints accessible (http://localhost:8000/api/monitoring/status)
- [ ] Database has new fields (timing_degraded, usable_for_validation)
- [ ] Integration tests pass
- [ ] Security tests pass

---

## If Something Goes Wrong

### Import Errors

```bash
# Check Python path
python3 -c "import sys; print('\n'.join(sys.path))"

# Verify files exist
ls -la utils/validation.py
ls -la monitoring/metrics_collector.py
ls -la routers/monitoring.py
```

### Database Migration Errors

```bash
# Check current database schema
python3 -c "
from database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
columns = inspector.get_columns('test_sessions')
print('test_sessions columns:', [c['name'] for c in columns])

columns = inspector.get_columns('detection_events')
print('detection_events columns:', [c['name'] for c in columns])
"
```

### Backend Won't Start

```bash
# Check for errors
python3 main.py 2>&1 | head -50

# Check port availability
lsof -i :8000
```

---

## Quick Start Script

Save this as `integrate_and_start.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Starting integration..."

# Step 1: Verify files exist
echo "📁 Checking files..."
test -f utils/validation.py && echo "✅ validation.py exists"
test -f monitoring/metrics_collector.py && echo "✅ metrics_collector.py exists"
test -f routers/monitoring.py && echo "✅ monitoring router exists"

# Step 2: Run migrations
echo "🗄️ Running database migrations..."
python3 migrations/add_detection_quality_fields.py

# Step 3: Verify imports
echo "📦 Testing imports..."
python3 -c "from utils.validation import validate_uuid; from monitoring.metrics_collector import metrics_collector; print('✅ Imports successful')"

# Step 4: Start backend
echo "🎬 Starting backend..."
python3 main.py
```

Run with:
```bash
chmod +x integrate_and_start.sh
./integrate_and_start.sh
```

---

## Summary

**Before running main.py, you MUST**:

1. ✏️ Edit main.py to add monitoring router (2 minutes)
2. 🗄️ Run database migrations (10 minutes)
3. ✅ Verify integration (15 minutes)

**Total Time**: ~30 minutes

**Then you can run**: `python3 main.py`

---

## Need Help?

Check these files for detailed documentation:
- `/backend/docs/MONITORING_INTEGRATION.md` - Monitoring setup
- `/backend/docs/DATABASE_MIGRATION_GUIDE.md` - Migration details
- `/backend/docs/SECURITY_FIXES.md` - Security implementation
