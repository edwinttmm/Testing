# Deployment Checklist - Per-Video Monitoring System

**System**: AI Model Validation Platform - Per-Video Monitoring
**Version**: 1.0.0
**Date**: 2025-11-20
**Reviewer**: Production Readiness Validation Agent

---

## Pre-Deployment

### Code Quality
- [ ] All Python files have type hints (checked: ~60% coverage - **WARNING**)
- [ ] All error cases handled with try/except blocks
- [ ] Logging comprehensive and structured (JSON format available)
- [ ] Transactions properly managed (SQLAlchemy ORM)
- [ ] Input validation present on all endpoints

### Database Migration
- [ ] Alembic migration `add_video_markers` reviewed and tested
- [ ] Migration tested on staging/test database
- [ ] Backfill logic verified (handles single-video and multi-video sessions)
- [ ] Rollback script tested (`alembic downgrade -1`)
- [ ] Database backup created before migration
- [ ] Migration validation queries executed successfully

### Environment Configuration
- [ ] Environment variables configured:
  - `VRU_DATABASE_URL` or `DATABASE_URL` set
  - `DATABASE_ECHO=false` (production setting)
  - Python 3.12+ available
  - SQLAlchemy 2.0.23+ installed
- [ ] LabJack hardware connected and accessible
- [ ] LabJack driver installed (`labjack-ljm` Python package)
- [ ] WebSocket endpoints accessible
- [ ] CORS configuration set for production domains

### Hardware Integration
- [ ] LabJack T7/T4 connected via USB
- [ ] LabJack firmware up to date
- [ ] Signal quality test passed (>500mV threshold)
- [ ] Clock sync verified (<10ms offset acceptable)
- [ ] Drift measurement baseline established (expected: <5ms/hour)

### Testing
- [ ] Unit tests pass (Note: pytest not installed - **CRITICAL**)
- [ ] Integration tests pass with real LabJack hardware
- [ ] WebSocket connection tests pass
- [ ] Per-video marker insertion/retrieval tests pass
- [ ] Multi-video sequence tests pass
- [ ] Ground truth matching tests pass with drift compensation

---

## Deployment Steps

### 1. Pre-Deployment Validation
```bash
# Backup database
pg_dump -h $DB_HOST -U $DB_USER $DB_NAME > backup_$(date +%Y%m%d_%H%M%S).sql

# Verify Python environment
python3 --version  # Should be 3.12+
python3 -c "import sqlalchemy; print(sqlalchemy.__version__)"  # Should be 2.0.23+

# Verify LabJack connectivity (if hardware present)
python3 -c "from labjack import ljm; handle = ljm.openS('ANY', 'ANY', 'ANY'); print(f'LabJack connected: {handle}'); ljm.close(handle)"
```

### 2. Database Migration
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Verify current migration state
alembic current

# Run migration (creates video_markers table)
alembic upgrade head

# Verify migration success
alembic current  # Should show: add_video_markers

# Validate data integrity
python3 -c "
from database import get_db
from models import VideoMarker
db = next(get_db())
count = db.query(VideoMarker).count()
print(f'Video markers created: {count}')
"
```

### 3. Code Deployment
```bash
# Pull latest code
git pull origin main

# Install/update dependencies
pip install -r requirements.txt
pip install -r requirements-labjack.txt

# Verify imports
python3 -c "from src.hil_video_frame_monitor import HILVideoFrameMonitor; print('✅ Video monitor import OK')"
python3 -c "from alembic.versions.add_video_markers_table import upgrade; print('✅ Migration import OK')"
```

### 4. Service Restart
```bash
# Option A: Systemd service
sudo systemctl restart ai-validation-backend

# Option B: Docker
docker-compose down
docker-compose up -d

# Option C: Direct process
# Kill existing process
pkill -f "uvicorn main:app"

# Start new process
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 > logs/app.log 2>&1 &
```

### 5. Health Checks
```bash
# Backend health
curl http://localhost:8000/health

# Database connection
curl http://localhost:8000/api/database/health

# LabJack connectivity (if hardware present)
curl http://localhost:8000/api/labjack/status

# WebSocket connectivity
# Use browser console or wscat:
# wscat -c ws://localhost:8000/ws
```

---

## Post-Deployment Validation

### Functional Testing
- [ ] **Per-Video Marker Creation Test**
  ```bash
  # Start test session, verify markers created
  curl -X POST http://localhost:8000/api/hil/start \
    -H "Content-Type: application/json" \
    -d '{"video_id": "test-video-1", "session_id": "test-session-1"}'

  # Verify VIDEO_START marker
  curl http://localhost:8000/api/video-markers?session_id=test-session-1
  ```

- [ ] **Drift Measurement Test**
  ```bash
  # Trigger drift measurement (requires LabJack hardware)
  curl -X POST http://localhost:8000/api/labjack/measure-drift \
    -H "Content-Type: application/json" \
    -d '{"session_id": "test-session-1"}'

  # Expected: drift_ms < 10.0 (acceptable), < 5.0 (good)
  ```

- [ ] **GT Matching with Compensation Test**
  ```bash
  # Upload ground truth with known timestamps
  curl -X POST http://localhost:8000/api/ground-truth/upload \
    -F "file=@test_gt.json" \
    -F "session_id=test-session-1"

  # Verify matching accuracy
  curl http://localhost:8000/api/results/test-session-1
  # Check: matched_count should match expected_count
  ```

### Performance Validation
- [ ] Video frame processing: <100ms per frame (target: <50ms)
- [ ] WebSocket latency: <50ms (target: <20ms)
- [ ] Database query performance: <100ms (target: <50ms)
- [ ] Memory usage stable (no leaks after 1-hour run)
- [ ] CPU usage acceptable (<80% sustained)

### Monitoring Dashboard
- [ ] Access drift metrics dashboard:
  ```bash
  # Frontend route (if deployed)
  http://localhost:3000/admin/drift-monitoring

  # Backend API
  curl http://localhost:8000/api/metrics/drift-dashboard
  ```

### Log Verification
- [ ] Check logs for errors:
  ```bash
  # Application logs
  tail -f logs/app.log | grep -i error

  # LabJack logs
  tail -f logs/labjack.log | grep -i "drift\|error"

  # Database logs
  tail -f logs/db.log | grep -i "slow query\|error"
  ```

### End-to-End Test
- [ ] **Full HIL Test Workflow**
  1. Start HIL session with multi-video sequence
  2. Verify VIDEO_START markers created for each video
  3. Verify drift measurement during test
  4. Verify VIDEO_END markers created
  5. Verify GT matching with drift compensation
  6. Verify results accuracy >= 95%

---

## Rollback Plan

### If Migration Fails
```bash
# Rollback database migration
alembic downgrade -1

# Restore from backup if needed
psql -h $DB_HOST -U $DB_USER $DB_NAME < backup_YYYYMMDD_HHMMSS.sql

# Verify rollback
alembic current  # Should show: add_usable_validation
```

### If Code Deployment Fails
```bash
# Revert to previous commit
git reset --hard HEAD~1

# Restart with previous code
sudo systemctl restart ai-validation-backend

# Verify system functional
curl http://localhost:8000/health
```

### If Performance Degraded
```bash
# Disable drift compensation temporarily
curl -X POST http://localhost:8000/api/config/feature-flags \
  -H "Content-Type: application/json" \
  -d '{"drift_compensation_enabled": false}'

# System will still function, just without drift compensation
# Matching will use raw timestamps
```

---

## Critical Issues Checklist

### Must Fix Before Deployment
- [ ] **pytest not installed**: Install test framework
  ```bash
  pip install pytest pytest-asyncio pytest-cov
  ```

- [ ] **Type hint coverage ~60%**: Acceptable for v1.0, plan for improvement

### Should Fix Before Deployment
- [ ] Add health check endpoint for drift measurement status
- [ ] Add monitoring alerts for drift > 10ms
- [ ] Add automatic drift measurement retry on failure

### Nice to Have (Post-Deployment)
- [ ] Automated drift measurement scheduling (hourly)
- [ ] Historical drift trend analysis
- [ ] Predictive drift compensation (ML-based)
- [ ] Multi-LabJack redundancy support

---

## Verification Commands

### Quick Health Check Script
```bash
#!/bin/bash
# save as: health_check.sh

echo "=== Backend Health ==="
curl -s http://localhost:8000/health | jq .

echo -e "\n=== Database Health ==="
curl -s http://localhost:8000/api/database/health | jq .

echo -e "\n=== LabJack Status ==="
curl -s http://localhost:8000/api/labjack/status | jq .

echo -e "\n=== Video Markers Count ==="
curl -s "http://localhost:8000/api/video-markers/count" | jq .

echo -e "\n=== Recent Drift Measurements ==="
curl -s "http://localhost:8000/api/metrics/drift/recent?limit=5" | jq .

echo -e "\n✅ Health check complete"
```

### Continuous Monitoring Script
```bash
#!/bin/bash
# save as: monitor_drift.sh
# Run in background: ./monitor_drift.sh &

while true; do
  DRIFT=$(curl -s http://localhost:8000/api/metrics/drift/latest | jq -r '.drift_ms')
  TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

  if (( $(echo "$DRIFT > 10.0" | bc -l) )); then
    echo "[$TIMESTAMP] ⚠️  HIGH DRIFT: $DRIFT ms" | tee -a drift_alerts.log
  else
    echo "[$TIMESTAMP] ✅ Drift OK: $DRIFT ms"
  fi

  sleep 300  # Check every 5 minutes
done
```

---

## Support Contacts

- **System Administrator**: [Contact Info]
- **Database Administrator**: [Contact Info]
- **Hardware Engineer**: [Contact Info - LabJack setup]
- **On-Call Engineer**: [Contact Info - 24/7]

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Development Lead | | | |
| QA Lead | | | |
| DevOps Engineer | | | |
| System Administrator | | | |
| **FINAL GO/NO-GO** | | | |

---

**Notes**:
- This checklist assumes PostgreSQL database (adjust for other databases)
- LabJack hardware is optional - system will run without it (fallback mode)
- Drift compensation is graceful degradation feature - system works without it
- All timestamps in UTC
- Backup retention: Keep backups for 30 days minimum
