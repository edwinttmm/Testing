# Backend Integration Quick Fix Guide

## 🚨 Critical Fixes (15 minutes total)

### Fix #1: Register Monitoring Router (2 minutes) 🔴

**Problem:** All monitoring endpoints return 404

**Solution:**

1. Open `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`

2. Add import after line 118:
```python
# Import monitoring router
from routers.monitoring import router as monitoring_router
```

3. Add registration after line 950:
```python
# Monitoring dashboard
app.include_router(monitoring_router)
```

4. Restart backend:
```bash
pkill -f "python.*main.py"
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 main.py &
```

5. Test:
```bash
curl http://localhost:8000/api/monitoring/status
# Should return JSON, not 404
```

---

### Fix #2: Apply Database Migration (1 minute) 🔴

**Problem:** Ground truth matching fails with "column doesn't exist" errors

**Solution:**

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Run migration
alembic upgrade head

# Verify
python3 -c "
from sqlalchemy import inspect, create_engine
from config import settings
engine = create_engine(settings.database_url)
inspector = inspect(engine)
cols = [c['name'] for c in inspector.get_columns('detection_events')]
print('usable_for_validation:', 'usable_for_validation' in cols)
print('timing_degraded:', 'timing_degraded' in cols)
"
# Both should print True
```

**Rollback if needed:**
```bash
alembic downgrade -1
```

---

### Fix #3: Add Metrics Collection (10 minutes) 🟡

**Problem:** No metrics being recorded from detection events

**Solution:**

1. Edit `/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`

2. Add import at top (around line 30):
```python
from monitoring.metrics_collector import metrics_collector
```

3. Add metrics recording in `_create_detection_from_hil_event` method (after line 1390):
```python
        # Record metrics for monitoring
        try:
            metrics_collector.record_detection(
                session_id=session_id,
                degraded=timing_degraded,
                timing_available=timing_available,
                usable=detection_usable_for_validation
            )
        except Exception as e:
            logger.warning(f"Metrics recording failed: {e}")
```

---

## ✅ Verification

After all fixes:

```bash
# 1. Monitoring works
curl http://localhost:8000/api/monitoring/status | jq .

# 2. Database has new columns
sqlite3 dev_database.db "PRAGMA table_info(detection_events);" | grep -E "usable_for_validation|timing_degraded"

# 3. Ground truth matching works
curl http://localhost:8000/api/ground-truth/sessions
# Should not error with "column doesn't exist"
```

---

## 📊 Expected Results

**Before Fixes:**
- `curl /api/monitoring/status` → 404 Error
- Ground truth matching → Database error
- Metrics → Empty/unavailable

**After Fixes:**
- `curl /api/monitoring/status` → Full metrics JSON
- Ground truth matching → Works correctly
- Metrics → Real-time detection stats

---

## 🔄 Rollback Procedure

If something breaks:

```bash
# 1. Rollback database
cd /home/rigade/Testing/ai-model-validation-platform/backend
alembic downgrade -1

# 2. Remove monitoring router registration
# Edit main.py and comment out:
# app.include_router(monitoring_router)

# 3. Remove metrics collection
# Edit dedicated_labjack_monitor.py and comment out:
# metrics_collector.record_detection(...)

# 4. Restart backend
pkill -f "python.*main.py"
python3 main.py &
```

---

## 📝 Notes

- **Downtime:** ~30 seconds for backend restart
- **Data Loss:** None (migrations are additive)
- **Testing:** Run on dev environment first
- **Backup:** Database automatically backed up by alembic

For complete details, see: [BACKEND_INTEGRATION_AUDIT.md](BACKEND_INTEGRATION_AUDIT.md)
