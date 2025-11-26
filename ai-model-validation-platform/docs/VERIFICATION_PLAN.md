# LabJack HIL Service Fix Verification Plan

## Overview
This document outlines the verification steps for validating the LabJack HIL service concurrency and stream mode fixes implemented in Phases 1-3.

## Phase 1 Verification: Thread-Safe Singleton

### Test 1: Concurrent Singleton Access
**Objective:** Verify only one instance created under concurrent load

**Steps:**
1. Reset singleton state
2. Spawn 20 concurrent threads
3. Each thread calls `get_labjack_hardware_service()`
4. Verify all receive same instance (same `id()`)

**Success Criteria:**
- ✅ All 20 threads receive identical instance
- ✅ No "DEVICE_ALREADY_OPEN" errors
- ✅ Execution completes in <1 second

### Test 2: Config Validation
**Objective:** Verify configuration mismatch detection

**Steps:**
1. Create service with Config A (device_type="T7")
2. Attempt to get service with Config B (device_type="T4")
3. Should raise `RuntimeError` with "Configuration mismatch"

**Success Criteria:**
- ✅ RuntimeError raised
- ✅ Error message clearly indicates config mismatch
- ✅ First instance remains intact

### Test 3: Exception Safety
**Objective:** Verify no partial state on initialization failure

**Steps:**
1. Mock `LabJackHardwareService.__init__` to raise exception
2. Call `get_labjack_hardware_service()`
3. Verify exception propagates
4. Remove mock and retry
5. Should succeed

**Success Criteria:**
- ✅ Exception properly propagated
- ✅ No partial instance created
- ✅ Retry succeeds after fixing error

---

## Phase 2 Verification: Stream Mode Implementation

### Test 4: No Asyncio in Threads
**Objective:** Verify no asyncio event loops in daemon threads

**Steps:**
1. Inspect `_monitoring_loop_stream()` source code
2. Search for `asyncio.new_event_loop`, `asyncio.get_event_loop`
3. Verify function is NOT async (`inspect.iscoroutinefunction`)

**Success Criteria:**
- ✅ No asyncio event loop creation found
- ✅ Function is synchronous (not async def)
- ✅ No `await` keywords in function body

### Test 5: Correct Method Calls
**Objective:** Verify correct hardware API methods called

**Steps:**
1. Inspect `_monitoring_loop_stream()` source
2. Verify calls to:
   - `start_stream_mode()` (not `start_stream()`)
   - `read_stream_mode()` (not `get_stream_data()`)
   - `stop_stream_mode()`

**Success Criteria:**
- ✅ All three methods present in source
- ✅ No calls to async variants
- ✅ No queue-based data retrieval

### Test 6: Fallback Mechanism
**Objective:** Verify graceful degradation to polling

**Steps:**
1. Simulate stream mode failure
2. Verify `_use_polling_fallback()` called
3. Verify transitions to `_monitoring_loop()` (polling)
4. Verify no recursion to `_monitoring_loop_stream()`

**Success Criteria:**
- ✅ Fallback function exists
- ✅ Calls polling mode (not recursive)
- ✅ Config updated to `use_stream_mode: False`
- ✅ Monitoring continues successfully

---

## Phase 3 Verification: Production Readiness

### Test 7: Real Hardware Test (Manual)
**Objective:** Validate with actual LabJack device

**Prerequisites:**
- LabJack T7 or T4 device connected
- LJM library installed
- Test video with known ground truth

**Steps:**
1. Restart backend: `docker-compose restart backend`
2. Create test session with stream mode enabled
3. Apply constant voltage (e.g., 3.3V) to AIN0
4. Run 5-second test video
5. Check detection count and logs

**Success Criteria:**
- ✅ Logs show "mode: stream" (not "mode: polling")
- ✅ Detection count ~1000 (for 5s @ 5ms interval)
- ✅ No hardware errors in logs
- ✅ F1 score > 0.95

**Expected Log Output:**
```
INFO: 🚀 Starting stream mode monitoring loop
INFO: ✅ Stream mode started successfully
INFO: Actual scan rate: 200.00 Hz
INFO: Stream detection: AIN0=3.300V at 1234567890.123
INFO: Detection count: 987 (expected ~1000)
INFO: F1 Score: 0.98
```

### Test 8: Concurrent Sessions Test (Manual)
**Objective:** Verify multiple sessions can use service safely

**Steps:**
1. Start Session 1 with video A
2. Immediately start Session 2 with video B (within 1 second)
3. Monitor both sessions
4. Verify both complete successfully

**Success Criteria:**
- ✅ Session 2 doesn't fail with "DEVICE_ALREADY_OPEN"
- ✅ Both sessions share same hardware service instance
- ✅ Both sessions produce valid detections
- ✅ No race condition errors in logs

### Test 9: Performance Validation
**Objective:** Measure performance improvement

**Baseline (Polling Mode):**
- Detection rate: ~20-100 Hz
- Latency: 10-50ms
- CPU usage: Moderate (constant polling)

**Expected (Stream Mode):**
- Detection rate: 200-10,000 Hz
- Latency: <1ms
- CPU usage: Lower (hardware buffering)

**Steps:**
1. Run test with polling mode (`use_stream_mode: False`)
2. Measure baseline metrics
3. Run test with stream mode (`use_stream_mode: True`)
4. Compare metrics

**Success Criteria:**
- ✅ Stream mode detection rate ≥ 10x polling mode
- ✅ Stream mode latency ≤ 10% of polling mode
- ✅ CPU usage stable or reduced

---

## Regression Testing

### Test 10: Polling Mode Still Works
**Objective:** Ensure polling mode unchanged

**Steps:**
1. Set `use_stream_mode: False` in config
2. Run standard HIL test
3. Verify detections still work

**Success Criteria:**
- ✅ Polling mode executes without errors
- ✅ Detections created successfully
- ✅ Performance matches pre-fix baseline

---

## Deployment Checklist

Before production deployment:

- [ ] All automated tests pass
- [ ] Manual hardware test successful
- [ ] Concurrent sessions test successful
- [ ] Performance validation complete
- [ ] Polling mode regression test passed
- [ ] Documentation updated
- [ ] Rollback plan documented
- [ ] Monitoring alerts configured

---

## Rollback Plan

If issues occur in production:

1. **Immediate:** Set `use_stream_mode: False` in `test_sessions.py`
2. **Restart:** `docker-compose restart backend`
3. **Verify:** Check logs for "mode: polling"
4. **Monitor:** Ensure tests run with reduced performance

**Rollback Files:**
- `backend/routers/test_sessions.py` (line 1135)

**Time to Rollback:** <2 minutes

---

## Success Metrics

**Phase 1 (Singleton):**
- ✅ 0 "DEVICE_ALREADY_OPEN" errors
- ✅ 100% concurrent session success rate

**Phase 2 (Stream Mode):**
- ✅ 0 deadlocks/hangs
- ✅ Detection rate ≥ 200 Hz
- ✅ Latency < 1ms

**Phase 3 (Production):**
- ✅ F1 Score ≥ 0.95
- ✅ Uptime ≥ 99.9%
- ✅ 0 critical errors in 7 days

---

## Contact & Support

**Implementation Team:** Phase 1-3 Fix Team
**Date:** 2025-11-18
**Documentation:** See `docs/` directory
