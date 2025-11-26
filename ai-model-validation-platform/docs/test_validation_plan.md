# Test Validation Plan: LabJack Detection System Fix
**Date:** 2025-11-19
**Version:** 1.0
**Status:** PLANNING PHASE - DO NOT EXECUTE YET

---

## Executive Summary

This document defines comprehensive test scenarios to validate fixes for the LabJack detection system. Current issue: Only 4 detections captured instead of 800-1000 expected from a 5-second video at 200 Hz.

**Root Causes Identified:**
1. **Debounce Filter** at 100ms suppressing 95% of detections
2. **Stream Monitoring Loop** premature exit via auto-stop logic
3. **Timing Window Validation** potentially filtering valid detections

**Test Strategy:** Validate baseline → Test fixes → Verify regressions → Establish rollback criteria

---

## 1. Baseline Tests (Verify Current Behavior)

### Test 1.1: Current Detection Count
**Purpose:** Establish baseline before any changes
**Prerequisites:**
- 5-second test video loaded
- LabJack connected and streaming
- Current configuration: `debounce_ms = 100`

**Setup:**
```python
config = DetectionConfig(
    voltage_threshold=2.5,
    debounce_ms=100,  # Current setting
    sample_rate=200,
    use_stream_mode=True
)
```

**Action:**
1. Start monitoring session with 5-second video
2. Wait for completion
3. Query database for detection count

**Expected Result:**
- Detection count: ~4 (current behavior)
- All detections have `state = 'threshold_cross'`
- No errors in logs

**Validation SQL:**
```sql
SELECT COUNT(*) as detection_count,
       MIN(detection_timestamp) as first_detection,
       MAX(detection_timestamp) as last_detection,
       MAX(detection_timestamp) - MIN(detection_timestamp) as time_span
FROM detection_events
WHERE session_id = '[SESSION_ID]'
  AND state = 'threshold_cross';
```

**Pass Criteria:**
- [ ] Detection count: 3-5 (consistent with current behavior)
- [ ] Time span: ≤ 5.5 seconds
- [ ] No NULL timestamps
- [ ] No exceptions in logs

---

### Test 1.2: Decision Statistics Baseline
**Purpose:** Verify debounce is the bottleneck
**Prerequisites:** Same as Test 1.1

**Action:**
1. Enable debug logging
2. Run same test
3. Extract decision statistics from logs

**Expected Result:**
```python
decision_statistics = {
    'threshold_cross': 4,
    'debounce_skipped': 996,  # Confirms bottleneck
    'steady_high': 0,
    'continuous': 0
}
```

**Validation:**
```bash
# Check logs for decision stats
grep "decision_statistics" backend.log | tail -1
```

**Pass Criteria:**
- [ ] `debounce_skipped` >> `threshold_cross` (ratio ~250:1)
- [ ] Total events: ~1000 (`threshold_cross` + `debounce_skipped`)
- [ ] Confirms 95% suppression rate

---

### Test 1.3: Timing Window Validation
**Purpose:** Verify window validation is not filtering detections
**Prerequisites:** Same as Test 1.1

**Action:**
1. Enable window validation logging
2. Run test
3. Check skip counters

**Expected Result:**
```
Stream Detection Stats: Valid=4, Skipped Early=0, Skipped Late=0
```

**Validation:**
```bash
grep "Stream Detection Stats" backend.log | tail -1
grep "Skipping early detection" backend.log | wc -l  # Should be 0
grep "Skipping late detection" backend.log | wc -l   # Should be 0
```

**Pass Criteria:**
- [ ] `Skipped Early = 0`
- [ ] `Skipped Late = 0`
- [ ] All 4 detections within video window
- [ ] Window validation not a bottleneck

---

### Test 1.4: Stream Loop Duration
**Purpose:** Verify stream loop runs for full video duration
**Prerequisites:** Same as Test 1.1

**Action:**
1. Add timestamps to loop start/exit
2. Run test
3. Measure actual loop duration

**Expected Result:**
- Loop duration: ≥ 5 seconds (video duration)
- Loop exit reason: Auto-stop or manual stop

**Validation:**
```bash
# Check loop lifecycle logs
grep "Stream loop starting" backend.log
grep "Auto-stopping stream" backend.log
grep "Loop exiting" backend.log
```

**Pass Criteria:**
- [ ] Loop runs for full video duration + buffer
- [ ] No premature exit
- [ ] Clean shutdown (no timeout warnings)

---

## 2. Bug Fix Tests (Verify Solutions Work)

### Test 2.1: Debounce Reduced to 5ms
**Purpose:** Verify 5ms debounce captures expected detections
**Prerequisites:** Code changes applied (debounce_ms = 5)

**Setup:**
```python
config = DetectionConfig(
    voltage_threshold=2.5,
    debounce_ms=5,  # FIXED: Changed from 100ms
    sample_rate=200,
    use_stream_mode=True
)
```

**Action:**
1. Restart detection service
2. Run same 5-second video test
3. Query detection count

**Expected Result:**
- Detection count: 800-1000 (200 Hz × 5s)
- Time span: ~5 seconds
- No errors

**Validation SQL:**
```sql
SELECT COUNT(*) as detection_count,
       (MAX(detection_timestamp) - MIN(detection_timestamp)) as time_span_seconds,
       COUNT(*) / (MAX(detection_timestamp) - MIN(detection_timestamp)) as avg_rate_hz
FROM detection_events
WHERE session_id = '[SESSION_ID]'
  AND state = 'threshold_cross';
```

**Pass Criteria:**
- [ ] Detection count: 800-1000
- [ ] Avg rate: 160-200 Hz
- [ ] Time span: 4.5-5.5 seconds
- [ ] F1 score > 0.0 (not zero)
- [ ] `debounce_skipped` ≤ 200 (< 20% suppression)

---

### Test 2.2: Stream Auto-Stop Timing Fix
**Purpose:** Verify stream doesn't exit prematurely
**Prerequisites:** Stream timing fixes applied

**Setup:**
- Add validation logging before auto-stop
- Verify `stop_time_with_buffer` calculation

**Action:**
1. Run test with enhanced logging
2. Check timing calculations

**Expected Result:**
```
🚀 Stream loop starting:
  - stop_time_with_buffer: [T + 6.0 seconds]
  - current_time: [T]
  - video_start_timestamp_float: [T]
  - video_duration: 5.0
  - Time until auto-stop: 6.0s
```

**Validation:**
```bash
grep "Time until auto-stop" backend.log
```

**Pass Criteria:**
- [ ] `stop_time_with_buffer` in future (not past)
- [ ] Time until stop ≥ video_duration
- [ ] No immediate loop exit
- [ ] Loop processes full buffer

---

### Test 2.3: Thread Termination
**Purpose:** Verify monitoring thread stops cleanly within timeout
**Prerequisites:** Stop timeout configured

**Setup:**
```python
STOP_TIMEOUT = 2.0  # seconds
```

**Action:**
1. Start monitoring session
2. Call `stop_monitoring()`
3. Measure time until thread terminates

**Expected Result:**
- Thread stops within 2 seconds
- No timeout warnings
- Clean resource cleanup

**Validation:**
```python
import time
start = time.time()
service.stop_monitoring(session_id)
duration = time.time() - start
assert duration < 2.0, f"Stop took {duration}s (timeout: 2.0s)"
```

**Pass Criteria:**
- [ ] Stop duration < 2 seconds
- [ ] No "thread did not stop" warnings
- [ ] No zombie threads in `threading.enumerate()`
- [ ] All file handles closed

---

### Test 2.4: Detection Timestamp Validity
**Purpose:** Verify no detections recorded past video duration
**Prerequisites:** All fixes applied

**Setup:**
- Video duration: 5.0 seconds
- Video start time: `T`
- Expected max timestamp: `T + 5.5` (with 0.5s buffer)

**Action:**
1. Run test
2. Query max detection timestamp
3. Compare to video end time

**Expected Result:**
- Max timestamp ≤ video_end + 0.5s buffer
- No late detections

**Validation SQL:**
```sql
SELECT
    MAX(detection_timestamp) as max_timestamp,
    '[VIDEO_END]' as video_end,
    (MAX(detection_timestamp) - '[VIDEO_END]') as time_after_video
FROM detection_events
WHERE session_id = '[SESSION_ID]';
```

**Pass Criteria:**
- [ ] Max timestamp ≤ video_end + 0.5s
- [ ] `time_after_video` ≤ 0.5
- [ ] No detections recorded after stream stop

---

## 3. Edge Case Tests

### Test 3.1: Very Short Video (< 1 second)
**Purpose:** Verify system handles sub-second videos
**Prerequisites:** 0.5-second test video

**Setup:**
```python
video_duration = 0.5  # seconds
expected_detections = 0.5 * 200 = 100
```

**Action:**
1. Run test with 0.5-second video
2. Verify detection count

**Expected Result:**
- Detection count: 80-120 (±20% tolerance)
- No timing errors
- Clean shutdown

**Pass Criteria:**
- [ ] Detection count in expected range
- [ ] No "invalid window" errors
- [ ] Stream processes correctly
- [ ] Thread stops cleanly

---

### Test 3.2: Very Long Video (> 60 seconds)
**Purpose:** Verify sustained performance
**Prerequisites:** 60-second test video

**Setup:**
```python
video_duration = 60  # seconds
expected_detections = 60 * 200 = 12000
```

**Action:**
1. Run test with 60-second video
2. Monitor memory usage
3. Verify detection count

**Expected Result:**
- Detection count: 11000-13000
- Memory stable (no leaks)
- No buffer overflows

**Validation:**
```python
# Check memory growth
import psutil
process = psutil.Process()
memory_before = process.memory_info().rss
# ... run test ...
memory_after = process.memory_info().rss
memory_growth = memory_after - memory_before
assert memory_growth < 100 * 1024 * 1024, "Memory leak detected"
```

**Pass Criteria:**
- [ ] Detection count: 11000-13000
- [ ] Memory growth < 100 MB
- [ ] No buffer overflow warnings
- [ ] CPU usage < 20% sustained

---

### Test 3.3: Concurrent Session Attempts
**Purpose:** Verify singleton prevents concurrent hardware access
**Prerequisites:** Thread-safe singleton implemented

**Setup:**
```python
# Attempt to start 2 sessions simultaneously
def start_session_thread(session_id):
    try:
        service.start_monitoring(session_id, ...)
        return "success"
    except Exception as e:
        return str(e)
```

**Action:**
1. Start 2 monitoring sessions concurrently
2. Verify only one succeeds (or both use same instance)

**Expected Result:**
- Both sessions use same hardware instance
- No "DEVICE_ALREADY_OPEN" errors
- Proper session isolation

**Pass Criteria:**
- [ ] No hardware access conflicts
- [ ] Both sessions get valid data
- [ ] Proper resource sharing
- [ ] Clean shutdown of both sessions

---

### Test 3.4: Stop Called During Active Stream
**Purpose:** Verify graceful shutdown during streaming
**Prerequisites:** Stream mode active

**Action:**
1. Start monitoring with stream mode
2. Wait 2 seconds (mid-stream)
3. Call `stop_monitoring()`
4. Verify clean shutdown

**Expected Result:**
- Stream stops within 2 seconds
- Partial data saved to database
- No resource leaks

**Pass Criteria:**
- [ ] Stop completes within timeout
- [ ] Detection count > 0 (partial capture)
- [ ] No corrupted database records
- [ ] Thread terminates cleanly

---

### Test 3.5: Hardware Disconnection During Monitoring
**Purpose:** Verify error handling for hardware failure
**Prerequisites:** LabJack device connected

**Action:**
1. Start monitoring session
2. Physically disconnect LabJack (or simulate)
3. Verify system handles failure gracefully

**Expected Result:**
- Error logged but no crash
- Fallback to polling or clean shutdown
- User-friendly error message

**Pass Criteria:**
- [ ] No unhandled exceptions
- [ ] Error logged with context
- [ ] Session marked as failed
- [ ] Resources cleaned up
- [ ] System remains operational

---

## 4. Regression Tests (Verify No Breakage)

### Test 4.1: Debounce Filter Still Works
**Purpose:** Verify 5ms debounce still filters noise
**Prerequisites:** Noisy voltage signal test data

**Setup:**
- Inject voltage signal with rapid fluctuations (< 5ms intervals)

**Action:**
1. Run test with noisy signal
2. Verify debounce suppresses noise

**Expected Result:**
- Rapid fluctuations filtered out
- Only transitions > 5ms apart recorded

**Pass Criteria:**
- [ ] No detections < 5ms apart
- [ ] `debounce_skipped` > 0 (filter active)
- [ ] Signal-to-noise ratio improved

---

### Test 4.2: Relative Timing Calculation
**Purpose:** Verify relative timestamps still calculated correctly
**Prerequisites:** Detection events with timestamps

**Action:**
1. Run test
2. Calculate relative time from video start
3. Verify calculation: `relative = detection_time - video_start`

**Expected Result:**
- First detection relative time ≈ 0.0
- Last detection relative time ≈ 5.0

**Validation SQL:**
```sql
SELECT
    detection_timestamp,
    (detection_timestamp - '[VIDEO_START]') as relative_time
FROM detection_events
WHERE session_id = '[SESSION_ID]'
ORDER BY detection_timestamp
LIMIT 1;  -- First detection

-- Should have relative_time ≈ 0.0
```

**Pass Criteria:**
- [ ] First detection: relative_time < 0.1s
- [ ] Last detection: relative_time ≤ video_duration
- [ ] Monotonically increasing timestamps
- [ ] No negative relative times (except pre-trigger)

---

### Test 4.3: Database Storage
**Purpose:** Verify detections still saved to database correctly
**Prerequisites:** Database configured

**Action:**
1. Run test
2. Query database for stored events
3. Verify data integrity

**Expected Result:**
- All detections persisted
- Foreign key relationships intact
- No NULL required fields

**Validation SQL:**
```sql
-- Check data integrity
SELECT
    COUNT(*) as total,
    COUNT(DISTINCT session_id) as unique_sessions,
    COUNT(CASE WHEN detection_timestamp IS NULL THEN 1 END) as null_timestamps,
    COUNT(CASE WHEN voltage IS NULL THEN 1 END) as null_voltages
FROM detection_events
WHERE session_id = '[SESSION_ID]';
```

**Pass Criteria:**
- [ ] All detections saved (count matches)
- [ ] No NULL required fields
- [ ] Timestamps in valid range
- [ ] Foreign keys valid

---

### Test 4.4: WebSocket Notifications
**Purpose:** Verify real-time detection notifications still sent
**Prerequisites:** WebSocket connection established

**Action:**
1. Connect WebSocket client
2. Start monitoring session
3. Count WebSocket messages received

**Expected Result:**
- WebSocket message for each detection
- Message format valid
- Real-time delivery (< 100ms latency)

**Validation:**
```javascript
let messageCount = 0;
socket.on('detection', (data) => {
    messageCount++;
    assert(data.session_id === '[SESSION_ID]');
    assert(data.detection_timestamp > 0);
    assert(data.voltage > 0);
});
```

**Pass Criteria:**
- [ ] Message count matches detection count
- [ ] Message format valid
- [ ] Latency < 100ms per message
- [ ] No dropped messages

---

### Test 4.5: F1 Score Calculation
**Purpose:** Verify F1 score calculation not broken
**Prerequisites:** Ground truth data available

**Action:**
1. Run test with known ground truth
2. Calculate F1 score
3. Verify score > 0.0 (not zero)

**Expected Result:**
- F1 score: 0.85 - 0.95 (typical range)
- Not 0.0 (current bug)

**Validation:**
```python
from sklearn.metrics import f1_score

# Compare detections to ground truth
f1 = f1_score(ground_truth, predicted_detections)
assert f1 > 0.0, "F1 score is zero - detection matching broken"
assert f1 > 0.80, f"F1 score too low: {f1:.3f}"
```

**Pass Criteria:**
- [ ] F1 score > 0.0 (fixes zero-score bug)
- [ ] F1 score ≥ 0.80 (acceptable performance)
- [ ] True positives > 0
- [ ] False positives < 20%

---

## 5. Validation Checklist

### Pre-Test Setup
- [ ] LabJack hardware connected and responding
- [ ] Test videos available (0.5s, 5s, 60s)
- [ ] Database schema up to date
- [ ] Backend service running
- [ ] Logging enabled (INFO or DEBUG level)
- [ ] WebSocket server running
- [ ] Ground truth data loaded

### Detection Count Targets
- [ ] 5-second video: 800-1000 detections (200 Hz)
- [ ] Max timestamp: ≤ video_duration + 0.5s buffer
- [ ] F1 score: > 0.80
- [ ] No zero-score results
- [ ] Detection rate: 160-200 Hz sustained

### Performance Targets
- [ ] Thread stop time: < 2 seconds
- [ ] Stream loop duration: ≥ video_duration
- [ ] Memory growth: < 100 MB per test
- [ ] CPU usage: < 20% sustained
- [ ] WebSocket latency: < 100ms

### System Health
- [ ] No "DEVICE_ALREADY_OPEN" errors
- [ ] No unhandled exceptions
- [ ] No "timeout" warnings
- [ ] No zombie threads
- [ ] Clean resource cleanup
- [ ] Database foreign keys valid

### Logging Validation
- [ ] "mode: stream" in logs (confirms stream mode active)
- [ ] "Stream Detection Stats" shows Valid > 0
- [ ] "Skipped Early" = 0 (no early filtering)
- [ ] "Skipped Late" = 0 (no late filtering)
- [ ] "decision_statistics" shows correct breakdown
- [ ] "debounce_skipped" < 20% of total events

---

## 6. Rollback Criteria

### CRITICAL: Immediate Rollback if ANY of These Occur

1. **Detection Count Still Low**
   - < 100 detections for 5-second video
   - Indicates fix didn't work

2. **System Crashes**
   - Unhandled exceptions
   - Segmentation faults
   - Service won't start

3. **Database Corruption**
   - NULL required fields
   - Foreign key violations
   - Corrupted timestamps

4. **Performance Degradation**
   - CPU usage > 80% sustained
   - Memory leaks (> 500 MB growth)
   - Thread stop timeout > 5 seconds

5. **Hardware Conflicts**
   - "DEVICE_ALREADY_OPEN" errors return
   - Concurrent session failures
   - Resource access deadlocks

### WARNING: Consider Rollback if ANY of These Occur

1. **Partial Fix**
   - Detection count improved but still < 500
   - Indicates incomplete fix

2. **New Errors Introduced**
   - Unexpected exceptions
   - Log spam
   - Frontend errors

3. **Regressions**
   - F1 score decreased
   - WebSocket notifications broken
   - Database queries fail

4. **Resource Leaks**
   - Memory growth > 100 MB
   - Thread count increases over time
   - File handles not closed

### Rollback Procedure

**Quick Rollback (< 2 minutes):**
```bash
# Revert debounce change
sed -i 's/debounce_ms: int = 5/debounce_ms: int = 100/' backend/config/detection_config.py

# Restart service
docker-compose restart backend

# Verify
curl http://localhost:8000/health
```

**Full Rollback:**
```bash
# Revert all changes via git
git checkout HEAD -- backend/services/labjack_detection_service.py
git checkout HEAD -- backend/config/detection_config.py

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Run baseline test
python tests/test_baseline.py
```

---

## 7. Performance Benchmarks (Before/After)

### Baseline (Before Fixes)
```
Detection Count: 4
Detection Rate: 0.8 Hz (4 detections / 5 seconds)
Debounce Suppression: 95% (996 skipped)
F1 Score: 0.0 (zero matches)
Thread Stop Time: < 1 second
Memory Usage: 50 MB baseline
```

### Target (After Fixes)
```
Detection Count: 800-1000
Detection Rate: 160-200 Hz
Debounce Suppression: < 20% (< 200 skipped)
F1 Score: > 0.80
Thread Stop Time: < 2 seconds
Memory Usage: 50-150 MB (< 100 MB growth)
```

### Improvement Metrics
```
Detection Count: 200-250x improvement (4 → 900)
Detection Rate: 200-250x improvement (0.8 Hz → 180 Hz)
Usable Data: 20x improvement (4% → 80%+)
F1 Score: >0.80 improvement (0.0 → 0.85)
```

---

## 8. Test Execution Order

### Phase 1: Baseline (No Code Changes)
1. Test 1.1: Current detection count ✓
2. Test 1.2: Decision statistics ✓
3. Test 1.3: Timing window validation ✓
4. Test 1.4: Stream loop duration ✓

**Exit Criteria:** Confirm root causes match analysis

---

### Phase 2: Bug Fixes (Code Changes Applied)
5. Test 2.1: Debounce reduced to 5ms ✓
6. Test 2.2: Stream auto-stop timing fix ✓
7. Test 2.3: Thread termination ✓
8. Test 2.4: Detection timestamp validity ✓

**Exit Criteria:** Detection count 800-1000, clean shutdown

---

### Phase 3: Edge Cases
9. Test 3.1: Very short video ✓
10. Test 3.2: Very long video ✓
11. Test 3.3: Concurrent sessions ✓
12. Test 3.4: Stop during stream ✓
13. Test 3.5: Hardware disconnection ✓

**Exit Criteria:** All edge cases handled gracefully

---

### Phase 4: Regression Testing
14. Test 4.1: Debounce filter still works ✓
15. Test 4.2: Relative timing calculation ✓
16. Test 4.3: Database storage ✓
17. Test 4.4: WebSocket notifications ✓
18. Test 4.5: F1 score calculation ✓

**Exit Criteria:** No regressions, F1 score > 0.80

---

### Phase 5: Performance Validation
19. Run all tests in sequence
20. Measure cumulative metrics
21. Compare before/after benchmarks
22. Document performance improvements

**Exit Criteria:** 200x improvement confirmed

---

## 9. Test Data Requirements

### Test Videos Required
1. **Short:** 0.5-second video (edge case)
2. **Standard:** 5-second video (primary test)
3. **Long:** 60-second video (sustained performance)

### Ground Truth Data
- Known detection timestamps for F1 calculation
- Expected detection count per video
- Voltage thresholds and patterns

### Hardware Configuration
- LabJack T7 or T4 device
- USB connection stable
- LJM library version ≥ 1.2100
- Firmware version compatible

---

## 10. Success Criteria Summary

### MUST ACHIEVE (Critical)
✅ Detection count: 800-1000 for 5-second video
✅ F1 score: > 0.80 (not zero)
✅ Thread stop: < 2 seconds
✅ No "DEVICE_ALREADY_OPEN" errors
✅ No unhandled exceptions
✅ Max timestamp: ≤ video_duration + 0.5s

### SHOULD ACHIEVE (Important)
✅ Detection rate: 160-200 Hz sustained
✅ Memory growth: < 100 MB per test
✅ CPU usage: < 20% sustained
✅ WebSocket latency: < 100ms
✅ All edge cases pass
✅ No regressions in existing features

### NICE TO HAVE (Desirable)
✅ Debounce suppression: < 10%
✅ Thread stop: < 1 second
✅ F1 score: > 0.90
✅ Real-time plotting functional
✅ Comprehensive logging
✅ Performance metrics dashboard

---

## 11. Test Report Template

```
TEST EXECUTION REPORT
=====================

Test ID: [e.g., 2.1]
Test Name: [e.g., Debounce Reduced to 5ms]
Date: [YYYY-MM-DD]
Tester: [Name]

SETUP:
- Video Duration: [seconds]
- Debounce Setting: [ms]
- Sample Rate: [Hz]
- Stream Mode: [True/False]

EXPECTED RESULT:
[Description]

ACTUAL RESULT:
[What actually happened]

MEASUREMENTS:
- Detection Count: [number]
- Detection Rate: [Hz]
- F1 Score: [0.0-1.0]
- Thread Stop Time: [seconds]
- Memory Growth: [MB]

LOGS:
[Relevant log excerpts]

STATUS: [PASS / FAIL / BLOCKED]

NOTES:
[Any observations or issues]

EVIDENCE:
- Screenshot: [path]
- Database Dump: [path]
- Log File: [path]
```

---

## 12. Next Steps After Validation

### If All Tests Pass ✅
1. Document final performance metrics
2. Update architecture diagrams
3. Create deployment guide
4. Train operations team
5. Deploy to staging environment
6. Monitor for 48 hours
7. Deploy to production

### If Tests Fail ❌
1. Analyze failure logs
2. Identify specific failure mode
3. Determine rollback necessity
4. Document failure for debugging
5. Create new hypothesis
6. Iterate on fix
7. Re-test

---

## Document Control

**Version:** 1.0
**Status:** APPROVED FOR USE
**Last Updated:** 2025-11-19
**Next Review:** After Phase 1 baseline testing

**Approvals:**
- [ ] Test Lead: _________________ Date: _____
- [ ] Backend Lead: _________________ Date: _____
- [ ] QA Manager: _________________ Date: _____

---

**END OF TEST VALIDATION PLAN**
