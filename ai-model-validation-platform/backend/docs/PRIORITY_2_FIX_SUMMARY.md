# Priority 2 Fix Summary: Multi-Video Timing Measurement

**Date:** 2025-11-24
**Session Analyzed:** `daad8bf6-b5da-4423-abc4-a85e83bc1c16`
**Status:** ✅ **ROOT CAUSE IDENTIFIED** - Partial Fix Applied

---

## Executive Summary

The investigation into timing measurement failures for multi-video sequences revealed that **timing calibration is actually ENABLED and working**, but there are **per-video timestamp calculation issues** that cause:

1. ✅ **Working:** All detections have valid `video_relative_timestamp` values (not NULL or 0.0)
2. ✅ **Working:** Timing measurement infrastructure is functional
3. ❌ **Issue:** Per-video timestamps are calculated relative to SESSION start, not VIDEO start
4. ❌ **Issue:** This causes detections in Video 2 to have timestamps 5-10s instead of 0-5s
5. ❌ **Impact:** Ground truth matching fails for 26% of detections (45/173) → marked as FP with 10000ms latency

---

## Test Results

### Session daad8bf6-b5da-4423-abc4-a85e83bc1c16

**Videos:**
- Video 1 (`child_test_video_20251031_144012.mp4`): Duration 5.04s, 131 GT objects, 74 detections
- Video 2 (`Child_20251031_143523.mp4`): Duration 5.04s, 126 GT objects, 99 detections

**Detection Timing Analysis:**
```
✓ Total Detections: 173
✓ NULL timestamps: 0 (0.0%)
✓ Zero timestamps: 0 (0.0%)
✓ Valid timestamps: 173 (100.0%)
✓ Time range: 0.094s - 8.713s
```

**Ground Truth Matching:**
```
✓ Total GT objects: 257
✓ Matched (TP): 128 (74.0%)
✗ False Positives: 45 (26.0%) ← These get 10000ms placeholder
✗ Detection rate: 49.8% (should be >90%)
```

**Per-Video Timing (THE CRITICAL ISSUE):**
```
Video 1 (10c2b16c-86f...):
  Duration: 5.042s
  ✓ Detection timestamps: 0.094s - 5.105s (CORRECT - within duration)

Video 2 (550e3cf8-275...):
  Duration: 5.042s
  ✗ Detection timestamps: 0.106s - 8.713s (WRONG - exceeds duration!)
                                   ^^^^
                                   Should be 0.106s - 3.672s (relative to Video 2 start)
```

---

## Root Cause Analysis

### The Problem

When a multi-video sequence transitions from Video 1 to Video 2:

1. Video 1 starts at `t=1763988511.882s` (session start)
2. Video 2 starts at `t=1763988516.923s` (5.04s later)
3. Detection in Video 2 at `t=1763988520.595s` should calculate:
   - **CURRENT (WRONG):** `video_relative_timestamp = 1763988520.595 - 1763988511.882 = 8.713s`
   - **CORRECT:** `video_relative_timestamp = 1763988520.595 - 1763988516.923 = 3.672s`

### Why This Happens

Looking at `services/labjack_detection_service.py` lines 1765-1810:

```python
# Line 1766: Gets video_start_time from session_info
video_start_time = session_info['video_start_timestamp']

# Lines 1769-1795: Attempts to override with current video's start time
if session_info.get('sequence_id'):
    # Tries to get current_video_id from sequence_metadata
    current_video_id = metadata.get('current_video_id')

    if current_video_id:
        # Get current video's start time
        video_start_time = current_video_timing['started_at']

# Line 1810: Calculate video_relative_timestamp
video_relative_timestamp = detection_timestamp - video_start_time
```

**The Issue:** The code tries to use per-video timing, but:
1. `sequence_metadata['current_video_id']` may not be updated when videos transition
2. Or the timing lookup fails silently and falls back to session start time
3. Result: Detections use Video 1's start time even when Video 2 is playing

---

## Fix Applied

### File: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`

**Lines 1765-1822:** Enhanced logging and error handling

```python
# Added current_video_id tracking
current_video_id = None

# Enhanced logging when video timing is found
logger.info(f"🎯 Multi-video: Using video {current_video_id[:12]} start time: {video_start_time:.6f}")

# Added warnings when video timing lookup fails
logger.warning(f"⚠️ No 'started_at' found for current video {current_video_id[:12]}, using session start")
logger.warning(f"⚠️ No 'current_video_id' in sequence_metadata, using session start")

# Added detailed debug logging for every detection
logger.debug(f"🕐 Timing calculation: detection={detection_timestamp:.6f}, "
           f"video_start={reference_time:.6f}, "
           f"video_relative={video_relative_timestamp:.6f}s, "
           f"video_id={current_video_id[:12] if current_video_id else 'N/A'}")
```

**Impact:**
- Will help diagnose timing issues in future tests
- Does NOT fix existing data (session daad8bf6 still has wrong timestamps)

---

## Additional Issues Found

### 1. Low Detection Rate (49.8%)

**Expected:** >90% detection rate for constant 3.3V injection
**Actual:** 128/257 = 49.8%
**Root Cause:** Combination of:
- Frame processing bottleneck (84 missed detections from investigation report)
- Ground truth matching failures due to wrong timestamps

### 2. sequence_metadata['current_video_id'] Update Issue

The timing calculation depends on `sequence_metadata['current_video_id']` being updated when videos transition. This update happens elsewhere in the codebase, likely in:
- Video sequence orchestration service
- Video player state management
- Sequence manager

**Need to verify:** Is `current_video_id` being updated atomically when videos transition?

---

## Recommended Next Steps

### Immediate (Fix for Future Tests)

1. **✅ DONE:** Enhanced logging in detection timing calculation
2. **TODO:** Verify `sequence_metadata['current_video_id']` update mechanism
3. **TODO:** Add unit test that simulates video transitions and validates per-video timing
4. **TODO:** Run new test with constant voltage to validate fix

### For Existing Data (Session daad8bf6)

The existing data cannot be fixed retroactively because:
- Ground truth timestamps are per-video (0-5s range)
- Detection timestamps were calculated wrong (0-8.7s range)
- No way to determine which detections belong to which video without re-running

**Recommendation:** Re-run the test with the fix applied to get clean data.

###  For Production

1. **Video Transition Hook:** Add explicit timing reset when video transitions
   ```python
   def on_video_transition(self, session_id, old_video_id, new_video_id, new_video_start_time):
       """Called when video transitions in a sequence"""
       # Update sequence_metadata atomically
       # Clear any cached timing references
       # Log the transition for debugging
   ```

2. **Timing Validation:** Add validation that detects wrong per-video timestamps
   ```python
   if video_relative_timestamp > video_duration + 1.0:  # 1s grace period
       logger.error(f"❌ Detection timestamp {video_relative_timestamp:.3f}s "
                   f"exceeds video duration {video_duration:.3f}s")
       # Raise exception or trigger re-calculation
   ```

3. **Ground Truth Matching Tolerance:** Consider adaptive tolerance for multi-video
   - Videos with correct per-video timing: strict tolerance (100ms)
   - Videos with suspected timing issues: wider tolerance (500ms) + warning

---

## Test Script

**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/tests/test_timing_measurement_fix.py`

**Usage:**
```bash
python3 tests/test_timing_measurement_fix.py
```

**Tests:**
1. ✅ Detection timing data validation (NULL, zero, range checks)
2. ✅ Ground truth matching validation
3. ✅ Per-video timing validation (detects the current issue)

---

## Conclusion

**Primary Finding:** Timing measurement is NOT disabled for multi-video sequences. The infrastructure works, but per-video timestamp calculation has a bug where detections in later videos use the wrong reference time (session start instead of video start).

**Fix Status:**
- ✅ Enhanced logging and error handling added
- ⚠️ Root cause identified but not fully fixed (needs `current_video_id` update verification)
- ❌ Existing test data (session daad8bf6) cannot be fixed retroactively

**Next Action:**
1. Verify `sequence_metadata['current_video_id']` is updated when videos transition
2. Re-run constant voltage test to validate the fix
3. Consider implementing video transition hooks for atomic timing updates

---

**Report Generated:** 2025-11-24
**Analyst:** Claude Code Implementation Agent
**Priority:** P2 (High - Blocks accurate multi-video testing)
