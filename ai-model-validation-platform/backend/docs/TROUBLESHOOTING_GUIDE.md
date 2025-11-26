# Troubleshooting Guide - Per-Video Monitoring System

**System**: AI Model Validation Platform
**Component**: Per-Video Monitoring with Drift Compensation
**Version**: 1.0.0
**Last Updated**: 2025-11-20

---

## Quick Reference

| Issue | Quick Fix | Section |
|-------|-----------|---------|
| Video markers not created | Check database migration | [§1.1](#11-video-markers-not-created) |
| LabJack not detected | Check USB connection & drivers | [§2.1](#21-labjack-not-detected) |
| Drift measurement fails | Verify signal quality | [§2.2](#22-drift-measurement-fails) |
| Frame processing slow | Check GPU/CPU load | [§3.1](#31-frame-processing-slow) |
| WebSocket disconnects | Check CORS configuration | [§4.1](#41-websocket-disconnects) |
| GT matching inaccurate | Verify drift compensation | [§5.1](#51-ground-truth-matching-inaccurate) |
| Database connection fails | Check DATABASE_URL | [§6.1](#61-database-connection-fails) |

---

## 1. Video Marker Issues

### 1.1 Video Markers Not Created

**Symptoms**:
- No VIDEO_START markers in database
- Query returns empty: `SELECT * FROM video_markers WHERE test_session_id = 'xxx'`
- Logs show: "Failed to create video marker"

**Diagnosis**:
```bash
# Check if table exists
psql -h $DB_HOST -U $DB_USER $DB_NAME -c "\d video_markers"

# Check migration status
alembic current
# Should show: add_video_markers

# Check for errors in application logs
tail -f logs/app.log | grep -i "video.marker"
```

**Solutions**:

**Solution A: Migration Not Run**
```bash
# Run migration
alembic upgrade head

# Verify table created
psql -h $DB_HOST -U $DB_USER $DB_NAME -c "\d video_markers"
```

**Solution B: Foreign Key Violation**
```bash
# Check if test_session exists
psql -h $DB_HOST -U $DB_USER $DB_NAME -c "SELECT id FROM test_sessions WHERE id = 'xxx';"

# Check if video exists
psql -h $DB_HOST -U $DB_USER $DB_NAME -c "SELECT id FROM videos WHERE id = 'xxx';"

# If missing, create test session first before starting video monitoring
```

**Solution C: Permission Issues**
```bash
# Check database user permissions
psql -h $DB_HOST -U $DB_USER $DB_NAME -c "SELECT has_table_privilege('video_markers', 'INSERT');"

# Grant permissions if needed
psql -h $DB_HOST -U postgres $DB_NAME -c "GRANT INSERT, SELECT, UPDATE ON video_markers TO $DB_USER;"
```

**Prevention**:
- Always verify migration ran successfully before deployment
- Use database health check endpoint: `GET /api/database/health`
- Monitor logs for foreign key violations

---

### 1.2 Duplicate Video Markers

**Symptoms**:
- Multiple VIDEO_START markers for same video
- Unique constraint violation errors
- Query shows duplicates: `SELECT test_session_id, video_id, marker_type, COUNT(*) FROM video_markers GROUP BY 1,2,3 HAVING COUNT(*) > 1`

**Diagnosis**:
```bash
# Find duplicates
psql -h $DB_HOST -U $DB_USER $DB_NAME <<EOF
SELECT
    test_session_id,
    video_id,
    marker_type,
    COUNT(*) as count
FROM video_markers
GROUP BY test_session_id, video_id, marker_type
HAVING COUNT(*) > 1;
EOF
```

**Solutions**:

**Solution A: Cleanup Duplicates**
```sql
-- Keep only the earliest marker per (session, video, type)
DELETE FROM video_markers
WHERE id NOT IN (
    SELECT DISTINCT ON (test_session_id, video_id, video_index, marker_type)
        id
    FROM video_markers
    ORDER BY test_session_id, video_id, video_index, marker_type, timestamp ASC
);
```

**Solution B: Application Logic Fix**
```python
# In code, use upsert pattern instead of insert
from sqlalchemy.dialects.postgresql import insert

stmt = insert(VideoMarker).values(
    test_session_id=session_id,
    video_id=video_id,
    marker_type='VIDEO_START',
    ...
).on_conflict_do_update(
    index_elements=['test_session_id', 'video_id', 'video_index', 'marker_type'],
    set_={'timestamp': stmt.excluded.timestamp}
)
```

**Prevention**:
- Unique constraint enforced at database level (already in migration)
- Add application-level check before insertion
- Use database transaction with rollback on conflict

---

## 2. LabJack Hardware Issues

### 2.1 LabJack Not Detected

**Symptoms**:
- Error: "Failed to open LabJack device"
- Logs show: "No LabJack devices found"
- Health check returns: `labjack_connected: false`

**Diagnosis**:
```bash
# Check USB connection
lsusb | grep -i labjack
# Should show: "Bus XXX Device YYY: ID 0cd5:XXXX LabJack"

# Test Python driver
python3 -c "
from labjack import ljm
try:
    handle = ljm.openS('ANY', 'ANY', 'ANY')
    print(f'✅ LabJack connected: handle={handle}')
    info = ljm.getHandleInfo(handle)
    print(f'   Device type: {info[0]}, Connection: {info[1]}, Serial: {info[2]}')
    ljm.close(handle)
except Exception as e:
    print(f'❌ Failed to connect: {e}')
"

# Check for permission issues (Linux)
ls -la /dev/bus/usb/*/*
# LabJack device should be readable by application user
```

**Solutions**:

**Solution A: Driver Not Installed**
```bash
# Install LabJack Python package
pip install labjack-ljm

# Install LJM library (required by Python package)
# Ubuntu/Debian:
wget https://labjack.com/sites/default/files/software/labjack_ljm_installer.run
sudo sh labjack_ljm_installer.run

# Verify installation
ldconfig -p | grep libLabJackM
```

**Solution B: USB Permission Issues (Linux)**
```bash
# Add udev rule for LabJack
sudo tee /etc/udev/rules.d/99-labjack.rules <<EOF
# LabJack T7
SUBSYSTEM=="usb", ATTR{idVendor}=="0cd5", ATTR{idProduct}=="0007", MODE="0666"
# LabJack T4
SUBSYSTEM=="usb", ATTR{idVendor}=="0cd5", ATTR{idProduct}=="0004", MODE="0666"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Reconnect LabJack device
```

**Solution C: Device in Use**
```bash
# Check if another process is using LabJack
lsof | grep -i labjack

# Kill processes using LabJack (if safe)
pkill -f "labjack"

# Or restart application with exclusive access
```

**Solution D: WSL/Docker Issues**
```bash
# WSL: USB passthrough required
# Use usbipd-win to attach USB device to WSL
usbipd wsl attach --busid X-Y

# Docker: USB device passthrough
docker run --device=/dev/bus/usb/XXX/YYY ...
```

**Prevention**:
- Run hardware check script before starting application
- Implement health check endpoint that polls LabJack every 60 seconds
- Add automatic reconnection logic with exponential backoff

---

### 2.2 Drift Measurement Fails

**Symptoms**:
- Error: "Drift measurement failed"
- Logs show: "Signal quality too low"
- API returns: `drift_ms: null` or `drift_quality: "low"`

**Diagnosis**:
```bash
# Check signal quality
curl http://localhost:8000/api/labjack/signal-quality

# Expected output:
# {
#   "voltage": 3.3,
#   "quality": "high",  # Should be "high" or "medium"
#   "threshold_mv": 500
# }

# Check recent measurements
curl http://localhost:8000/api/metrics/drift/recent?limit=10

# Manual test with LabJack
python3 <<EOF
from labjack import ljm
handle = ljm.openS('ANY', 'ANY', 'ANY')

# Read AIN0 (adjust for your setup)
voltage = ljm.eReadName(handle, 'AIN0')
print(f'Voltage: {voltage:.3f}V')

if voltage < 0.5:
    print('⚠️  Signal too weak (<0.5V)')
elif voltage > 5.0:
    print('⚠️  Signal too strong (>5.0V)')
else:
    print('✅ Signal OK')

ljm.close(handle)
EOF
```

**Solutions**:

**Solution A: Signal Quality Too Low**
```bash
# Check physical connections
# - Verify signal wire connected to correct LabJack terminal (AIN0)
# - Verify ground wire connected
# - Check for loose connections

# Adjust signal threshold if needed (temporary workaround)
# In configuration or code:
SIGNAL_THRESHOLD_MV = 300  # Lower from 500 (use cautiously)
```

**Solution B: Timing Issue**
```python
# In drift measurement code, increase timeout
async def measure_drift(self, timeout_seconds=30):  # Increase from 10
    ...
```

**Solution C: Clock Not Synchronized**
```bash
# Verify system clock is synchronized
timedatectl status
# "System clock synchronized: yes" should be true

# If not synchronized, enable NTP
sudo timedatectl set-ntp true

# Verify NTP is working
ntpq -p
```

**Prevention**:
- Run signal quality check before each test
- Set minimum signal quality threshold
- Alert if drift measurement fails 3 times in a row
- Implement fallback: use previous drift measurement if recent measurement fails

---

## 3. Performance Issues

### 3.1 Frame Processing Slow

**Symptoms**:
- Frame processing >150ms per frame
- Logs show: "slow_frame_processing: true"
- Real-time monitoring lags behind video playback

**Diagnosis**:
```bash
# Check current processing speed
curl http://localhost:8000/api/monitoring/stats | jq '.average_detection_time_ms'

# Check system resources
top -p $(pgrep -f "uvicorn main:app")
# Look for high CPU% or VIRT (memory usage)

# Check GPU usage (if using GPU for inference)
nvidia-smi

# Check frame queue backlog
curl http://localhost:8000/api/monitoring/stats | jq '.frame_queue_size'
```

**Solutions**:

**Solution A: High CPU Load**
```bash
# Reduce concurrent frame processing
# In hil_video_frame_monitor.py, adjust:
max_concurrent_frames = 2  # Reduce from 4

# Or reduce max FPS
max_fps = 15.0  # Reduce from 30.0
```

**Solution B: Model Inference Slow**
```python
# Use lighter YOLO model
# In T3 pipeline configuration:
model_size = "yolov5s"  # Instead of "yolov5m" or "yolov5l"

# Reduce input resolution
inference_size = 416  # Instead of 640

# Enable half-precision inference (if GPU available)
use_half_precision = True
```

**Solution C: Memory Bottleneck**
```bash
# Clear memory cache
# In code, after processing batch of frames:
import gc
gc.collect()

# If using PyTorch:
torch.cuda.empty_cache()  # If using GPU
```

**Solution D: Database Writes Blocking**
```python
# Make database writes asynchronous and batched
# Instead of writing each detection immediately:
async def batch_write_detections(self, detections_batch):
    async with self.db_session() as session:
        session.bulk_insert_mappings(DetectionEvent, detections_batch)
        await session.commit()

# Call every 100 detections instead of every detection
```

**Prevention**:
- Monitor frame processing time continuously
- Set alert threshold: >100ms average over 5 minutes
- Use performance profiler to identify bottlenecks:
  ```bash
  py-spy record -o profile.svg -- python3 main.py
  ```

---

### 3.2 Database Queries Slow

**Symptoms**:
- API responses >500ms
- Logs show: "slow query" warnings
- Database CPU at 100%

**Diagnosis**:
```sql
-- Find slow queries (PostgreSQL)
SELECT
    query,
    calls,
    mean_exec_time,
    total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check for missing indexes
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE tablename = 'video_markers';

-- Check for table bloat
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename = 'video_markers';
```

**Solutions**:

**Solution A: Missing Indexes**
```sql
-- Already created in migration, but verify:
CREATE INDEX IF NOT EXISTS idx_video_markers_session_timestamp
    ON video_markers (test_session_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_video_markers_session_video
    ON video_markers (test_session_id, video_id);
```

**Solution B: Query Not Using Indexes**
```python
# Use EXPLAIN to check query plan
query = session.query(VideoMarker).filter_by(test_session_id=session_id)
print(str(query.statement.compile(compile_kwargs={"literal_binds": True})))

# Run EXPLAIN in psql:
# EXPLAIN ANALYZE SELECT * FROM video_markers WHERE test_session_id = 'xxx';
# Should show "Index Scan" not "Seq Scan"
```

**Solution C: Connection Pool Exhausted**
```python
# In database.py, increase pool size:
engine = create_engine(
    DATABASE_URL,
    pool_size=50,  # Increase from 25
    max_overflow=100,  # Increase from 50
    pool_timeout=60
)
```

**Prevention**:
- Enable slow query logging (>100ms)
- Monitor database connection pool usage
- Run VACUUM ANALYZE periodically
- Set up database performance monitoring (pg_stat_statements extension)

---

## 4. WebSocket Issues

### 4.1 WebSocket Disconnects

**Symptoms**:
- Frontend shows "Disconnected" frequently
- Logs show: "WebSocket closed unexpectedly"
- Real-time updates stop working

**Diagnosis**:
```bash
# Test WebSocket connection
wscat -c ws://localhost:8000/ws
# Should stay connected and receive messages

# Check for connection timeout
curl http://localhost:8000/api/websocket/stats | jq '.active_connections'

# Check logs for disconnect reasons
tail -f logs/app.log | grep -i "websocket"
```

**Solutions**:

**Solution A: CORS Issues**
```python
# In main.py, ensure proper CORS configuration:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Solution B: WebSocket Timeout**
```python
# In WebSocket handler, add ping/pong:
import asyncio

async def websocket_handler(websocket: WebSocket):
    await websocket.accept()

    async def send_ping():
        while True:
            await asyncio.sleep(30)  # Ping every 30 seconds
            try:
                await websocket.send_json({"type": "ping"})
            except:
                break

    ping_task = asyncio.create_task(send_ping())

    try:
        # Main message loop
        ...
    finally:
        ping_task.cancel()
```

**Solution C: Reverse Proxy Configuration**
```nginx
# If using nginx, ensure WebSocket upgrade headers:
location /ws {
    proxy_pass http://backend:8000/ws;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400;  # 24 hours
}
```

**Prevention**:
- Implement reconnection logic in frontend (exponential backoff)
- Monitor WebSocket connection duration
- Set up health check that maintains test connection

---

## 5. Ground Truth Matching Issues

### 5.1 Ground Truth Matching Inaccurate

**Symptoms**:
- Matching accuracy <80% (expected: >95%)
- Many "unmatched" detections
- API shows: `matched: 10, unmatched: 50`

**Diagnosis**:
```bash
# Check matching tolerance
curl http://localhost:8000/api/config/matching-tolerance
# Should show: tolerance_ms: 50 (adjust based on your needs)

# Check drift compensation status
curl http://localhost:8000/api/metrics/drift/latest
# Should show recent drift measurement

# Check time alignment
curl http://localhost:8000/api/results/test-session-xxx | jq '.detections[] | {gt_time, det_time, offset: (.det_time - .gt_time)}'
# Offsets should be small (<50ms)
```

**Solutions**:

**Solution A: Drift Compensation Not Applied**
```bash
# Verify drift compensation is enabled
curl http://localhost:8000/api/config/features | jq '.drift_compensation_enabled'
# Should be: true

# If false, enable it:
curl -X POST http://localhost:8000/api/config/features \
  -H "Content-Type: application/json" \
  -d '{"drift_compensation_enabled": true}'

# Re-run matching
curl -X POST http://localhost:8000/api/ground-truth/rematch/test-session-xxx
```

**Solution B: Incorrect Video Start Time**
```bash
# Verify video start time recorded correctly
curl http://localhost:8000/api/video-markers?session_id=test-session-xxx&marker_type=VIDEO_START

# Should show VIDEO_START marker with timestamp
# If missing, video monitoring was not started correctly

# Check test_sessions table for video_playback_start_time
psql -h $DB_HOST -U $DB_USER $DB_NAME -c "
SELECT
    id,
    video_playback_start_time,
    video_playback_start_time_ns
FROM test_sessions
WHERE id = 'test-session-xxx';
"
```

**Solution C: Matching Tolerance Too Strict**
```python
# Increase matching tolerance temporarily to diagnose
# In config or API:
MATCHING_TOLERANCE_MS = 100  # Increase from 50

# If accuracy improves significantly, indicates timing issue:
# - Clock synchronization needed
# - Drift measurement needed
# - Video timestamps incorrect
```

**Solution D: Algorithm Issue**
```bash
# Check if using correct matching algorithm
curl http://localhost:8000/api/config/matching-algorithm
# Should show: "hungarian" or "optimal"

# Not: "greedy" (less accurate)

# Switch algorithm if needed:
curl -X POST http://localhost:8000/api/config/matching-algorithm \
  -H "Content-Type: application/json" \
  -d '{"algorithm": "hungarian"}'
```

**Prevention**:
- Run drift measurement before each test session
- Verify drift < 10ms before starting test
- Monitor matching accuracy in real-time
- Alert if accuracy drops below 90%
- Keep audit log of all matching operations

---

## 6. Database Issues

### 6.1 Database Connection Fails

**Symptoms**:
- Error: "FATAL: password authentication failed"
- Error: "could not connect to server: Connection refused"
- Application won't start

**Diagnosis**:
```bash
# Check DATABASE_URL environment variable
echo $DATABASE_URL
# Should show: postgresql://user:pass@host:port/dbname

# Test connection manually
psql $DATABASE_URL -c "SELECT 1;"

# Check database server is running
pg_isready -h $DB_HOST -p $DB_PORT
```

**Solutions**:

**Solution A: Wrong Credentials**
```bash
# Verify credentials
psql -h $DB_HOST -U $DB_USER $DB_NAME
# Should prompt for password and connect

# Update .env file with correct credentials:
DATABASE_URL=postgresql://user:password@localhost:5432/ai_validation

# Restart application
```

**Solution B: Database Server Not Running**
```bash
# Start PostgreSQL (Ubuntu/Debian)
sudo systemctl start postgresql

# Start PostgreSQL (Docker)
docker start postgres-container

# Verify running
sudo systemctl status postgresql
```

**Solution C: Network Issue**
```bash
# Test network connectivity
ping $DB_HOST

# Test port accessibility
telnet $DB_HOST $DB_PORT
# Or: nc -zv $DB_HOST $DB_PORT

# Check firewall rules
sudo ufw status
# Ensure port 5432 (or your DB port) is open
```

**Solution D: Connection Pool Exhausted**
```bash
# Check active connections
psql $DATABASE_URL -c "
SELECT
    count(*),
    state
FROM pg_stat_activity
WHERE datname = current_database()
GROUP BY state;
"

# If too many "idle" connections, restart application
# Or increase connection pool limits in database.py

# Kill idle connections manually if needed:
psql $DATABASE_URL -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
  AND state_change < now() - interval '1 hour';
"
```

**Prevention**:
- Use connection pool with proper limits
- Enable pool_pre_ping to validate connections
- Set pool_recycle to refresh connections periodically
- Monitor connection pool usage

---

### 6.2 Migration Fails

**Symptoms**:
- Error: "Target database is not up to date"
- Error: "DETAIL: Key (id)=(xxx) is not present in table"
- Alembic commands fail

**Diagnosis**:
```bash
# Check current migration status
alembic current

# Check pending migrations
alembic history

# Check for partial migration
psql $DATABASE_URL -c "\d video_markers"
# If table partially exists, migration was interrupted
```

**Solutions**:

**Solution A: Rollback and Re-run**
```bash
# Rollback to previous version
alembic downgrade -1

# Verify rollback
alembic current

# Re-run migration
alembic upgrade head
```

**Solution B: Force Stamp (Dangerous)**
```bash
# Only use if you know migration already applied manually
# This marks migration as complete without running it
alembic stamp head

# Verify
alembic current
```

**Solution C: Manual Cleanup**
```sql
-- If migration partially completed, clean up:
DROP TABLE IF EXISTS video_markers CASCADE;
DROP FUNCTION IF EXISTS check_video_marker_order();
DROP TRIGGER IF EXISTS validate_marker_order ON video_markers;

-- Then re-run migration:
-- alembic upgrade head
```

**Prevention**:
- Always backup database before migrations
- Test migrations on staging first
- Never interrupt running migrations
- Use transactions in migrations (Alembic default)

---

## 7. Common Error Messages

### 7.1 "No module named 'labjack'"

**Cause**: LabJack Python package not installed

**Solution**:
```bash
pip install labjack-ljm
```

### 7.2 "Failed to initialize T3 YOLO pipeline"

**Cause**: YOLO model files missing or corrupted

**Solution**:
```bash
# Re-download YOLO model
python3 -c "
import torch
model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)
"
```

### 7.3 "video_markers table does not exist"

**Cause**: Database migration not run

**Solution**:
```bash
alembic upgrade head
```

### 7.4 "Timeout waiting for drift measurement"

**Cause**: LabJack not responding or signal not present

**Solution**:
1. Check LabJack connection (see §2.1)
2. Check signal quality (see §2.2)
3. Increase timeout in configuration

### 7.5 "Memory error: Cannot allocate memory"

**Cause**: System running out of RAM

**Solution**:
```bash
# Check memory usage
free -h

# Reduce frame queue sizes in config
MAX_QUEUE_SIZE = 20  # Reduce from 50

# Or add swap space
sudo dd if=/dev/zero of=/swapfile bs=1G count=4
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## 8. Diagnostic Tools

### 8.1 Health Check Script

```bash
#!/bin/bash
# Save as: system_health.sh

echo "=== System Health Check ==="
echo

echo "1. Backend API"
curl -s http://localhost:8000/health | jq . || echo "❌ Backend not responding"
echo

echo "2. Database Connection"
curl -s http://localhost:8000/api/database/health | jq . || echo "❌ Database not accessible"
echo

echo "3. LabJack Hardware"
curl -s http://localhost:8000/api/labjack/status | jq . || echo "❌ LabJack not accessible"
echo

echo "4. Video Markers Table"
curl -s http://localhost:8000/api/video-markers/count | jq . || echo "❌ Video markers table error"
echo

echo "5. Recent Drift Measurements"
curl -s http://localhost:8000/api/metrics/drift/recent?limit=1 | jq . || echo "⚠️  No recent drift measurements"
echo

echo "6. System Resources"
echo "   CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')%"
echo "   Memory: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
echo "   Disk: $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}')"
echo

echo "✅ Health check complete"
```

### 8.2 Log Analysis Script

```bash
#!/bin/bash
# Save as: analyze_logs.sh

LOG_FILE=${1:-logs/app.log}
HOURS=${2:-1}

echo "=== Log Analysis (last $HOURS hour(s)) ==="
echo

echo "Errors:"
grep -i error $LOG_FILE | tail -20
echo

echo "Warnings:"
grep -i warning $LOG_FILE | tail -20
echo

echo "Drift Measurements:"
grep -i "drift" $LOG_FILE | grep -i "measurement" | tail -10
echo

echo "Frame Processing Stats:"
grep -i "frame.*processed" $LOG_FILE | tail -10
echo

echo "Database Queries:"
grep -i "slow query" $LOG_FILE | tail -10
echo
```

---

## 9. Emergency Procedures

### 9.1 System Unresponsive

```bash
# 1. Check if process is running
pgrep -f "uvicorn main:app"

# 2. Check resource usage
top -p $(pgrep -f "uvicorn main:app")

# 3. If high CPU/memory, restart gracefully
kill -SIGTERM $(pgrep -f "uvicorn main:app")

# 4. Wait 10 seconds for graceful shutdown
sleep 10

# 5. Force kill if still running
pkill -9 -f "uvicorn main:app"

# 6. Restart application
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > logs/app.log 2>&1 &
```

### 9.2 Database Corruption Suspected

```bash
# 1. Stop application
pkill -f "uvicorn main:app"

# 2. Backup current database
pg_dump $DATABASE_URL > emergency_backup_$(date +%Y%m%d_%H%M%S).sql

# 3. Run integrity check
psql $DATABASE_URL -c "SELECT * FROM pg_catalog.pg_indexes WHERE schemaname = 'public';"

# 4. Reindex if needed
psql $DATABASE_URL -c "REINDEX DATABASE ai_validation;"

# 5. Restart application
# ...
```

### 9.3 Complete System Failure

```bash
# 1. Restore from last known good backup
psql $DATABASE_URL < backup_YYYYMMDD_HHMMSS.sql

# 2. Rollback code to last stable version
git reset --hard v1.0.0-stable

# 3. Rollback database migration if needed
alembic downgrade -1

# 4. Restart all services
sudo systemctl restart postgresql
sudo systemctl restart ai-validation-backend

# 5. Verify system functional
curl http://localhost:8000/health
```

---

## 10. Contact & Escalation

### Level 1: Self-Service (0-15 minutes)
- Check this troubleshooting guide
- Run health check script
- Check logs for error messages

### Level 2: Team Support (15-60 minutes)
- Contact: Development Team (#dev-support Slack channel)
- Provide: Error messages, logs, health check output
- Response SLA: 30 minutes during business hours

### Level 3: On-Call Engineer (Critical Issues)
- Contact: [On-Call Phone Number]
- Escalate if:
  - System completely down
  - Data loss suspected
  - Security incident
- Response SLA: 15 minutes 24/7

### Level 4: Vendor Support (Hardware/Third-Party)
- **LabJack**: support@labjack.com, +1-970-482-4775
- **PostgreSQL**: Community forums or commercial support
- **Cloud Provider**: [Your cloud provider support]

---

## 11. Useful Commands Reference

```bash
# Database
alembic current                          # Check migration status
alembic upgrade head                     # Run all pending migrations
alembic downgrade -1                     # Rollback one migration
psql $DATABASE_URL                       # Connect to database

# Application
uvicorn main:app --reload               # Run in development mode
uvicorn main:app --workers 4            # Run with 4 worker processes
pkill -f "uvicorn main:app"             # Stop application

# LabJack
python3 -c "from labjack import ljm; ..."  # Test LabJack connection

# Logs
tail -f logs/app.log                    # Follow application logs
grep -i error logs/app.log | tail -20  # Show recent errors

# Health Checks
curl http://localhost:8000/health                      # Backend health
curl http://localhost:8000/api/database/health        # Database health
curl http://localhost:8000/api/labjack/status         # LabJack status
curl http://localhost:8000/api/metrics/drift/latest   # Latest drift

# Performance
top -p $(pgrep -f uvicorn)              # CPU/memory usage
lsof -p $(pgrep -f uvicorn) | wc -l     # Open file descriptors
netstat -an | grep :8000                # Network connections
```

---

**Document Version**: 1.0
**Last Updated**: 2025-11-20
**Next Review**: 2026-01-20
**Maintainer**: DevOps Team
