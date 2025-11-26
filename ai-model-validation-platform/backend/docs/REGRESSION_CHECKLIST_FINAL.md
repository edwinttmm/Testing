# Regression Testing Checklist - Pre-Deployment Validation
**Date**: 2025-11-19
**Purpose**: Ensure all fixes don't break existing functionality
**Status**: Ready for execution

---

## Critical Functionality Tests (MUST PASS)

### 1. Session Management

- [ ] **Create single-video session**
  - Endpoint: `POST /api/video-sequences/start`
  - Expected: Session created, returns `session_id`
  - Verify: Session exists in `test_sessions` table

- [ ] **Create multi-video sequence**
  - Endpoint: `POST /api/video-sequences/start` with multiple videos
  - Expected: Single primary session, multiple `VideoTestSequence` records
  - Verify: All videos linked to same session

- [ ] **Query session results**
  - Endpoint: `GET /api/test-sessions/{session_id}/results`
  - Expected: Returns detections, timing, ground truth matches
  - Verify: Data format unchanged from v2.0

### 2. Detection Recording

- [ ] **LabJack detection captured**
  - Simulate: Voltage spike above threshold
  - Expected: Detection saved to database within 200ms
  - Verify: `detection_events` table has new row

- [ ] **Detection assigned to correct session**
  - Create: Session with UUID="primary-123"
  - Monitor: Start with same session ID
  - Detect: Capture voltage spike
  - Verify: `detection_events.test_session_id = 'primary-123'`

- [ ] **Timing data populated**
  - Expected: Detection has `timestamp`, `latency_ms` fields
  - Verify: Timestamps are reasonable (not 0 or null)

### 3. Ground Truth Matching

- [ ] **Ground truth upload works**
  - Endpoint: `POST /api/ground-truth/upload`
  - Expected: Ground truth objects saved
  - Verify: `ground_truth_objects` table populated

- [ ] **Matching algorithm runs**
  - Expected: Detections matched to ground truth within tolerance
  - Verify: `F1 score > 0` if detections align

- [ ] **Multi-video ground truth**
  - Upload: Ground truth for video 1, 2, 3
  - Test: Run sequence with all 3 videos
  - Verify: Matching works per video

### 4. Database Integrity

- [ ] **No orphaned detections**
  ```sql
  SELECT COUNT(*) FROM detection_events de
  WHERE NOT EXISTS (
    SELECT 1 FROM test_sessions ts
    WHERE ts.id = de.test_session_id
  );
  -- Expected: 0
  ```

- [ ] **Foreign key constraints valid**
  ```sql
  SELECT constraint_name, table_name
  FROM information_schema.table_constraints
  WHERE constraint_type = 'FOREIGN KEY'
    AND table_schema = 'public';
  -- Expected: All constraints intact
  ```

- [ ] **No duplicate session IDs**
  ```sql
  SELECT test_session_id, COUNT(*)
  FROM detection_events
  GROUP BY test_session_id
  HAVING COUNT(DISTINCT test_session_id) > 1;
  -- Expected: 0 rows
  ```

### 5. Connection Stability

- [ ] **LabJack connection persists**
  - Start: Session 1
  - End: Session 1
  - Start: Session 2
  - Verify: No "LJME_DEVICE_NOT_OPEN" error

- [ ] **Connection pool doesn't exhaust**
  - Create: 10 sessions concurrently
  - Verify: All start successfully
  - Check: `pg_stat_activity` shows < 25 active connections

---

## Edge Case Handling (SHOULD GRACEFULLY DEGRADE)

### 6. Timing Failures

- [ ] **Timing service returns None**
  - Mock: `start_video_timing()` returns `None`
  - Expected: Monitor continues, uses fallback timing
  - Verify: Detection saved with wall clock timestamp

- [ ] **Timing service throws exception**
  - Mock: `start_video_timing()` raises `Exception`
  - Expected: Event signaled, monitor continues
  - Verify: Log shows "Timing event signaled despite error"

### 7. Database Failures

- [ ] **Session not found (race condition)**
  - Create: Session in transaction 1
  - Query: From transaction 2 immediately
  - Expected: Retry logic succeeds within 350ms
  - Verify: Detection saved after retry

- [ ] **Database connection lost**
  - Simulate: Kill PostgreSQL connection
  - Expected: Error logged, monitor continues
  - Verify: System recovers after reconnect

### 8. Concurrent Operations

- [ ] **5 simultaneous sessions**
  - Start: 5 sessions within 1 second
  - Expected: No session ID confusion
  - Verify: Each has isolated detections

- [ ] **Session transitions**
  - Video 1 → Video 2 → Video 3 in same session
  - Expected: Session ID unchanged
  - Verify: Timing accurate per video

---

## Performance Tests (SHOULD NOT DEGRADE)

### 9. Latency Benchmarks

- [ ] **Detection latency < 100ms**
  ```
  Measure: Time from voltage spike to database save
  Target: p95 < 100ms
  Max: p99 < 200ms
  ```

- [ ] **Monitor startup < 500ms**
  ```
  Measure: Time from start_hil_monitoring() call to ready
  Target: < 500ms
  Max: < 1000ms
  ```

- [ ] **Query response < 1s**
  ```
  Measure: GET /api/test-sessions/{id}/results
  Target: < 500ms
  Max: < 1000ms
  ```

### 10. Resource Usage

- [ ] **Memory stable during session**
  ```
  Baseline: 200MB after startup
  During: Should not grow > 50MB during 10-min session
  After: Should return to baseline after session ends
  ```

- [ ] **Connection pool usage < 80%**
  ```
  Pool size: 25 connections
  Usage: Should stay < 20 connections
  Check: pg_stat_activity
  ```

---

## Backward Compatibility (EXISTING FEATURES)

### 11. Historical Data Access

- [ ] **Query old test sessions**
  - Sessions: Created before fixes applied
  - Expected: Data still accessible
  - Verify: No schema migration broke queries

- [ ] **Report generation works**
  - Generate: PDF report for historical session
  - Expected: Report renders correctly
  - Verify: No missing fields

### 12. API Compatibility

- [ ] **Endpoint signatures unchanged**
  ```
  POST /api/video-sequences/start
  GET /api/test-sessions/{id}
  GET /api/test-sessions/{id}/results
  POST /api/ground-truth/upload
  ```

- [ ] **Response formats unchanged**
  ```json
  {
    "session_id": "uuid",
    "status": "active|completed|failed",
    "detections": [...],
    "timing_data": {...},
    "ground_truth_matches": {...}
  }
  ```

### 13. Frontend Integration

- [ ] **UI displays results correctly**
  - Navigate: Dashboard → Session Details
  - Expected: Detections shown in timeline
  - Verify: Timing chart renders

- [ ] **WebSocket updates work**
  - Start: Test session
  - Expected: Real-time detection events in UI
  - Verify: WebSocket connection stable

---

## Validation Commands

### Run All Checks

```bash
# Syntax validation
python3 -m py_compile services/dedicated_labjack_monitor.py
python3 -m py_compile services/video_timing_service.py
python3 -m py_compile src/services/ground_truth_matching_service.py

# Import validation
python3 -c "from models import TestSession, DetectionEvent, Video, VideoTestSequence"
python3 -c "from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor"

# Database integrity
psql -U postgres -d ai_validation -f scripts/validate_database_integrity.sql

# Integration tests
pytest tests/integration/test_fix_integration_comprehensive.py -v

# Regression tests
pytest tests/test_session_completion_logic.py -v
pytest tests/test_ground_truth_matching_fixes.py -v
```

### Monitor Production Health

```bash
# Check logs for errors
tail -f logs/backend.log | grep -E "ERROR|CRITICAL|Timed out|LJME_DEVICE_NOT_OPEN"

# Monitor connection pool
psql -c "SELECT state, COUNT(*) FROM pg_stat_activity WHERE datname='ai_validation' GROUP BY state;"

# Check session success rate
psql -c "SELECT
    COUNT(*) FILTER (WHERE detection_count > 0) * 100.0 / COUNT(*) AS success_rate
FROM (
    SELECT ts.id, COUNT(de.id) AS detection_count
    FROM test_sessions ts
    LEFT JOIN detection_events de ON de.test_session_id = ts.id
    WHERE ts.created_at > NOW() - INTERVAL '1 hour'
    GROUP BY ts.id
) AS stats;"
```

---

## Pass/Fail Criteria

### GO Criteria (All must be TRUE)

✅ **Critical Functionality**: All 5 tests pass
✅ **Edge Cases**: Handle gracefully (no crashes)
✅ **Performance**: Within target ranges
✅ **Backward Compatibility**: No regressions
✅ **Database Integrity**: No orphaned data

### NO-GO Criteria (Any triggers rollback)

❌ **Critical Test Failure**: Session creation fails
❌ **Data Loss**: Detections not saved
❌ **Connection Crash**: Pool exhausted or deadlock
❌ **API Breaking Change**: Frontend can't query results
❌ **Performance Regression**: > 50% slower

---

## Test Execution Log

| Test # | Description | Status | Notes |
|--------|-------------|--------|-------|
| 1.1 | Create single-video session | ⏳ Pending | |
| 1.2 | Create multi-video sequence | ⏳ Pending | |
| 1.3 | Query session results | ⏳ Pending | |
| 2.1 | LabJack detection captured | ⏳ Pending | |
| 2.2 | Detection assigned correctly | ⏳ Pending | |
| 2.3 | Timing data populated | ⏳ Pending | |
| 3.1 | Ground truth upload | ⏳ Pending | |
| 3.2 | Matching algorithm runs | ⏳ Pending | |
| 3.3 | Multi-video ground truth | ⏳ Pending | |
| 4.1 | No orphaned detections | ⏳ Pending | |
| 4.2 | Foreign keys valid | ⏳ Pending | |
| 4.3 | No duplicate session IDs | ⏳ Pending | |
| 5.1 | Connection persists | ⏳ Pending | |
| 5.2 | Pool doesn't exhaust | ⏳ Pending | |
| 6.1 | Timing returns None | ⏳ Pending | |
| 6.2 | Timing throws exception | ⏳ Pending | |
| 7.1 | Session not found | ⏳ Pending | |
| 7.2 | Connection lost | ⏳ Pending | |
| 8.1 | 5 simultaneous sessions | ⏳ Pending | |
| 8.2 | Session transitions | ⏳ Pending | |
| 9.1 | Detection latency | ⏳ Pending | |
| 9.2 | Monitor startup | ⏳ Pending | |
| 9.3 | Query response | ⏳ Pending | |
| 10.1 | Memory stable | ⏳ Pending | |
| 10.2 | Connection pool | ⏳ Pending | |
| 11.1 | Query old sessions | ⏳ Pending | |
| 11.2 | Report generation | ⏳ Pending | |
| 12.1 | Endpoint signatures | ⏳ Pending | |
| 12.2 | Response formats | ⏳ Pending | |
| 13.1 | UI displays results | ⏳ Pending | |
| 13.2 | WebSocket updates | ⏳ Pending | |

**Status Key**:
- ⏳ Pending
- ✅ Passed
- ❌ Failed
- ⚠️ Warning (acceptable)

---

## Post-Deployment Monitoring (Week 1)

### Daily Checks

```bash
# Day 1: Monitor every hour
for i in {1..8}; do
    ./scripts/check_system_health.sh
    sleep 3600
done

# Day 2-3: Monitor every 4 hours
# Day 4-7: Monitor daily
```

### Key Metrics Dashboard

```
Session Success Rate: [____95%____] ✅ Target: > 95%
Detection Save Rate:  [____99%____] ✅ Target: > 99%
Timing Timeout Rate:  [____1.5%___] ✅ Target: < 2%
Connection Pool:      [____18/25__] ✅ Target: < 20
MVCC Retry Success:   [____96%____] ✅ Target: > 95%
```

---

## Rollback Plan

If any NO-GO criterion triggered:

```bash
# 1. Stop backend
sudo systemctl stop backend-service

# 2. Rollback code
git checkout HEAD~1 -- services/dedicated_labjack_monitor.py
git checkout HEAD~1 -- services/video_timing_service.py
git checkout HEAD~1 -- src/services/ground_truth_matching_service.py

# 3. Restart backend
sudo systemctl start backend-service

# 4. Verify rollback
curl http://localhost:8000/health

# 5. Document issue
echo "Rollback triggered at $(date): $REASON" >> rollback.log
```

---

## Sign-Off

**Tested By**: _________________________
**Date**: ___________________________
**Environment**: Production / Staging (circle one)

**Result**: PASS / FAIL (circle one)

**Deployment Approved**: YES / NO (circle one)

**Signature**: _________________________

---

**Checklist Version**: 1.0
**Last Updated**: 2025-11-19
**Maintained By**: Agent 5 (QA & Integration Testing)
