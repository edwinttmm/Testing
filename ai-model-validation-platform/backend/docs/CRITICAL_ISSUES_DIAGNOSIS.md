# Critical System Issues - Diagnostic Report
**Date**: 2025-11-19
**Session ID Analyzed**: 9a98313e-e9e3-4353-8bf7-0fcb83952631, 0f85dc24-fe76-4822-b3d1-8ca86cc1f9e9

## Executive Summary

Three critical issues are preventing detection recording and ground truth matching:

1. **FIXED** ✅ Missing `VideoTestSequence` import causing NameError
2. **CRITICAL** ⚠️ Timing data timeout preventing detection processing
3. **CRITICAL** ⚠️ LabJack device connection lost mid-session
4. **UNDER INVESTIGATION** 🔍 Detection recorded but not persisted to database

---

## Issue #1: Missing VideoTestSequence Import ✅ FIXED

### Problem
```
NameError: name 'VideoTestSequence' is not defined
File: /home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py, line 487
```

### Root Cause
Two versions of `ground_truth_matching_service.py` exist:
- **services/ground_truth_matching_service.py** (newer, has import)
- **src/services/ground_truth_matching_service.py** (older, MISSING import) ← Backend uses this

### Fix Applied
```python
# File: src/services/ground_truth_matching_service.py line 24
# OLD:
from models import DetectionEvent, GroundTruthObject, Video, TestSession

# NEW:
from models import DetectionEvent, GroundTruthObject, Video, TestSession, VideoTestSequence, DetectionComparison
```

### Status
✅ **FIXED** - Import added to src/services version

---

## Issue #2: Timing Data Timeout ⚠️ CRITICAL

### Problem
```
❌ Timed out waiting for timing data for session 9a98313e-e9e3-4353-8bf7-0fcb83952631 after 10s. Aborting detection.
```

### Evidence from Logs
```
File: services/dedicated_labjack_monitor.py:857
timing_ready_event.wait(timeout=10.0) → TIMEOUT
```

### Root Cause Analysis

**Expected Flow:**
1. `start_monitoring_with_video_sync()` creates `timing_ready_event`
2. LabJack monitor starts capturing detections
3. `video_timing_service.start_video_timing()` is called
4. On success → `timing_ready_event.set()` (line 658)
5. Detection callback can process detections

**Actual Flow:**
1. `timing_ready_event` created ✅
2. LabJack monitoring starts ✅
3. `start_video_timing()` called...
4. **Exception occurs** or returns None ❌
5. `timing_ready_event.set()` is **NEVER CALLED** ❌
6. Detection callback waits 10s, times out, aborts ❌

### Code Location
```python
# File: services/dedicated_labjack_monitor.py:646-655
video_start_time = self.video_timing_service.start_video_timing(
    session_id, video_id, db, video_metadata
)

if video_start_time is None:  # ← This condition is TRUE
    logger.error(f"Failed to start video timing for session {session_id}")
    db.close()
    self.labjack_monitor.stop_monitoring(session_id)
    return False  # ← Exits WITHOUT setting timing_ready_event

# This line is NEVER reached:
timing_ready_event.set()  # line 658
```

### Potential Causes

1. **Exception in `start_video_timing()`**:
   - Method signature says it raises `VideoTimingError`
   - But code checks for `None` return
   - Exception may be caught upstream and converted to None

2. **Database session issues**:
   - `_store_enhanced_video_timing()` may fail silently (line 211)

3. **Precision service failure**:
   - `_precision_service.create_sync_point()` may fail (line 158)

### Fix Required

**Option A**: Add try-except in calling code
```python
try:
    video_start_time = self.video_timing_service.start_video_timing(
        session_id, video_id, db, video_metadata
    )
    timing_ready_event.set()  # Always signal even if partial success
    logger.info(f"✅ Timing data is ready")
except Exception as e:
    logger.error(f"Video timing failed: {e}")
    timing_ready_event.set()  # Signal with degraded timing
    # Continue anyway - detections can use wall clock
```

**Option B**: Modify `start_video_timing()` to never return None
- Always return a timestamp (even if degraded)
- Log warnings for partial failures
- Only raise exception for critical failures

### Recommended Fix
**Use Option A** - More defensive, allows system to continue even with degraded timing

---

## Issue #3: LabJack Device Connection Lost ⚠️ CRITICAL

### Problem
```
❌ Failed to read AIN0: LJM library error code 1224 LJME_DEVICE_NOT_OPEN
⚠️ Health check failed (attempt 1/10): LJM library error code 1224 LJME_DEVICE_NOT_OPEN
🔌 LabJack handle closed (LJME_DEVICE_NOT_OPEN); pausing health monitor until next connection
```

### Evidence
```
File: services/labjack_hardware_service.py:764-777
Error code: 1224 (LJME_DEVICE_NOT_OPEN)
Health monitor detects closed handle and pauses
```

### Root Cause

The LabJack connection is being closed prematurely or lost during operation:

1. **Connection established** ✅
2. **Session starts monitoring** ✅
3. **Detection recorded** ✅ (1 detection at 4.212V)
4. **"Stop detected mid-buffer"** - Session ends early
5. **Connection closed** ❌ (should be preserved)
6. **Health check fails** - Device not open

### Timeline from Logs
```
13:40:01.324 - Detection recorded: 4.212V (threshold_cross)
13:40:11.488 - Timed out waiting for timing data (10s timeout)
13:40:11.488 - Stop detected mid-buffer, abandoning 19 samples
13:40:11.489 - Stopping stream mode
13:40:11.602 - Stream stopped
13:40:11.771 - Connection preserved - 0 sessions remaining
13:40:19.473 - Health check failed: LJME_DEVICE_NOT_OPEN ← 8s later!
```

### Issues Identified

1. **Premature session termination**:
   - Detection at 13:40:01
   - Timeout at 13:40:11 (10s later)
   - Suggests video timing setup failed immediately

2. **Connection closure despite "preserved" log**:
   - Log says "Connection preserved"
   - But 8s later, device is not open
   - Suggests connection is closed elsewhere

3. **"Stop detected mid-buffer"**:
   - Line 1356: `labjack_detection_service.py`
   - Abandons 19 remaining samples
   - May be discarding valid detections

### Fix Required

**Short-term**:
1. Add connection health monitoring BEFORE critical operations
2. Reconnect automatically if device closed
3. Add retry logic for device operations

**Long-term**:
1. Implement connection pooling
2. Add connection state machine with proper lifecycle
3. Separate "logical session" from "hardware connection"

---

## Issue #4: Detection Not Persisted to Database 🔍

### Problem
```
Ground truth matching: 0 TP, 0 FP, 131 FN
Total detections in database: 0
But logs show: "Stream detection recorded (threshold_cross): 4.212V (valid: 1)"
```

### Evidence

**Detection WAS captured**:
```
Session: 0f85dc24-fe76-4822-b3d1-8ca86cc1f9e9
13:40:01.324234 - Detection recorded: 4.212V
Stream Detection Stats: Valid=1, Skipped Early=0, Skipped Late=0
```

**But database shows 0 detections**:
```
Session: 9a98313e-e9e3-4353-8bf7-0fcb83952631
[Tracing] detection query returned 0 rows
📡 Returning 0 video frame detection events
```

### Critical Observations

1. **Two different session IDs**:
   - Detection recorded in: `0f85dc24-fe76-4822-b3d1-8ca86cc1f9e9`
   - Results requested for: `9a98313e-e9e3-4353-8bf7-0fcb83952631`
   - **THESE ARE DIFFERENT SESSIONS!**

2. **Session lifecycle issues**:
   - Detection recorded at 13:40:01
   - Timing timeout at 13:40:11
   - Detection callback aborted due to timeout
   - Detection never written to database

### Root Cause

**Detection flow breakdown**:
```
1. LabJack captures signal (4.212V) ✅
2. Detection event created ✅
3. Detection callback waits for timing_ready_event...
4. Timeout after 10s (timing data never ready) ❌
5. Detection callback aborts ❌
6. Detection NEVER written to database ❌
```

**Code location**:
```python
# File: dedicated_labjack_monitor.py:855-858
is_set = timing_ready_event.wait(timeout=10.0)
if not is_set:
    logger.error(f"❌ Timed out waiting for timing data...")
    return  # ← ABORTS WITHOUT SAVING DETECTION!
```

### Fix Required

**Critical**: Detections must be saved even if timing data is unavailable

```python
# BEFORE:
if not is_set:
    logger.error("Timed out waiting for timing data")
    return  # ← Discards detection!

# AFTER:
if not is_set:
    logger.warning("Timing data not ready - using wall clock timestamp")
    # Continue with degraded timing
    # STILL SAVE THE DETECTION!
```

---

## Cascade Effect Analysis

The issues create a destructive cascade:

```
Issue #3 (LabJack timeout)
    ↓
Timing service fails to initialize
    ↓
Issue #2 (timing_ready_event never set)
    ↓
Detection callback times out after 10s
    ↓
Issue #4 (Detection discarded, never saved)
    ↓
Issue #1 (VideoTestSequence import fails during matching)
    ↓
Complete system failure: 0 detections, 0 TP, 131 FN
```

---

## Recommended Fix Priority

### Priority 1: IMMEDIATE (Prevents data loss)
1. **Fix detection callback timeout**:
   - Don't discard detections when timing unavailable
   - Use wall clock timestamps as fallback
   - Save detection even with degraded timing

### Priority 2: HIGH (Enables timing)
2. **Fix timing_ready_event**:
   - Always signal event (even on partial failure)
   - Add exception handling around `start_video_timing()`
   - Log timing degradation but continue

### Priority 3: MEDIUM (Improves reliability)
3. **Fix LabJack connection lifecycle**:
   - Implement proper connection state machine
   - Add automatic reconnection
   - Separate session lifecycle from connection lifecycle

### Priority 4: COMPLETED ✅
4. **Fix VideoTestSequence import** - Already done

---

## Testing Recommendations

After fixes:
1. Run single-video test session
2. Verify detection captured and saved
3. Run multi-video sequence test
4. Test with intentional timing delays
5. Test LabJack disconnect/reconnect
6. Verify ground truth matching works with degraded timing

---

## Next Steps

1. Apply Priority 1 fix (detection callback timeout)
2. Restart backend service
3. Run test session
4. Verify detections are saved
5. Apply Priority 2 fix (timing_ready_event)
6. Run full integration test
7. Monitor for any remaining issues

---

## Additional Notes

### Session ID Confusion
The logs show two different session IDs being used concurrently:
- `0f85dc24-fe76-4822-b3d1-8ca86cc1f9e9` (had 1 detection)
- `9a98313e-e9e3-4353-8bf7-0fcb83952631` (being queried for results)

This may indicate:
- Frontend/backend session ID mismatch
- Session recreation after failure
- Race condition in session management

**Recommendation**: Add session ID validation at API boundaries

---

## Conclusion

The system has three interdependent critical failures that create a cascade effect. The root cause is the timing service initialization failure, which triggers a timeout that discards valid detections. The LabJack connection issues compound the problem.

**Primary fix**: Make the detection callback more resilient to timing failures. Secondary fixes address the underlying timing and connection issues.

**Estimated effort**: 2-4 hours for Priority 1 & 2 fixes, 1-2 days for Priority 3.

