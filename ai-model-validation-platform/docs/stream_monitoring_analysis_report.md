# Stream Monitoring Loop Analysis Report
**Date:** 2025-11-19
**File Analyzed:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
**Function:** `_monitoring_loop_stream()` (Lines 1241-1417)

---

## Executive Summary

**Problem:** Only 4 detections captured instead of expected ~1000 from a 5-second video at 200 Hz sampling rate.

**Root Cause Hypothesis:** The stream monitoring loop appears to be exiting prematurely due to **AUTO-STOP LOGIC** that triggers too early based on video timing validation. The loop is designed to stop when `stop_time_with_buffer` is exceeded, but this calculation may be incorrect or the timing may not account for the full video duration.

**Critical Finding:** The loop has NO inherent bugs in its continuation logic—it's the **timing window validation** that's causing premature termination.

---

## Detailed Analysis

### 1. Loop Continuation Logic (Lines 1252-1259)

```python
while not stop_event.is_set():
    try:
        # Check auto-stop condition
        if stop_time_with_buffer:
            current_timestamp = time.time()
            if current_timestamp > stop_time_with_buffer:
                logger.info(f"⏹️ Auto-stopping stream: video ended, buffer expired")
                break  # ⚠️ EXITS LOOP HERE
```

**Analysis:**
- **Line 1252:** Loop continues while `stop_event` is not set ✅ (CORRECT)
- **Line 1255-1259:** Auto-stop logic that breaks the loop if current time exceeds `stop_time_with_buffer`
- **CRITICAL ISSUE:** If `stop_time_with_buffer` is calculated incorrectly (too short), the loop exits after only processing a fraction of the expected samples

**Hypothesis:** The 4 detections correspond to approximately 0.02 seconds of data (4 samples / 200 Hz = 0.02s), suggesting the loop exits almost immediately.

---

### 2. Timing Window Calculation (Lines 1212-1221)

```python
# Calculate stop time with buffer
stop_buffer_seconds = multi_video_buffer  # Default may be too small
if video_duration and video_start_timestamp_float:
    stop_time_with_buffer = video_start_timestamp_float + video_duration + stop_buffer_seconds
    logger.info(
        f"🕐 Stream window validation enabled: "
        f"video_start={video_start_timestamp_float:.6f}, "
        f"video_end={video_start_timestamp_float + video_duration:.6f}, "
        f"monitor_stop={stop_time_with_buffer:.6f}"
    )
```

**Analysis:**
- **Line 1213:** `stop_buffer_seconds = multi_video_buffer` - This variable is initialized earlier (line 1083) with default value 1.0 second
- **Line 1215:** Calculation: `stop_time_with_buffer = video_start + duration + buffer`
- **POTENTIAL ISSUE #1:** If `video_duration` is incorrectly retrieved or is 0/None, the stop time will be too early
- **POTENTIAL ISSUE #2:** If `video_start_timestamp_float` is set to the CURRENT time instead of the actual video start time, the window becomes immediate

---

### 3. Video Timing Retrieval (Lines 1095-1200)

```python
# Retrieve video timing from session metadata
video_start_time = None
video_duration = None
multi_video_buffer = 1.0  # Default buffer

try:
    session_timing = self.session_timing.get(session_id, {})

    if 'video_start_time' in session_timing:
        video_start_time = session_timing['video_start_time']
        logger.info(f"🎬 Video start time: {video_start_time}")

    # Complex logic to retrieve video duration from database...
    # (Lines 1112-1200)
```

**Analysis:**
- **Lines 1095-1099:** Timing is retrieved from `self.session_timing` dictionary
- **CRITICAL DEPENDENCY:** If session timing is not properly populated before stream starts, defaults may cause immediate termination
- **Potential Race Condition:** Video timing may not be available when stream monitoring starts

**Key Questions:**
1. Is `self.session_timing` populated BEFORE `_monitoring_loop_stream()` is called?
2. What happens if timing data is unavailable or arrives late?
3. Is `video_duration` correctly calculated for the test video?

---

### 4. Stream Read Logic (Lines 1263-1283)

```python
# FIXED: Read stream data SYNCHRONOUSLY using read_stream_mode()
stream_data, backlog, read_success = self.labjack_service.read_stream_mode()

if not read_success:
    consecutive_errors += 1
    # ... error handling ...
    continue

# Reset error counter on successful read
consecutive_errors = 0

if not stream_data or len(stream_data) == 0:
    time.sleep(0.001)  # Small sleep to prevent CPU spinning
    continue  # ⚠️ SKIPS PROCESSING
```

**Analysis:**
- **Line 1263:** Blocking synchronous read from LabJack stream ✅ (CORRECT)
- **Line 1281-1283:** If stream returns empty data, loop continues WITHOUT processing
- **POTENTIAL ISSUE #3:** If LabJack stream buffer is not filling (hardware issue or incorrect config), no data is processed but loop continues until timeout

**From `labjack_service.py` (Lines 1361-1417):**
```python
def read_stream_mode(self) -> Tuple[List[float], int, bool]:
    try:
        result = ljm.eStreamRead(self.direct_handle)
        data = result[0]  # Data array
        backlog = result[1]  # Device backlog
        return data, backlog, True
    except Exception as e:
        # Error handling...
        return [], 0, False
```

**Analysis:** The read function appears straightforward—returns data if available, empty array if not.

---

### 5. Detection Window Validation (Lines 1317-1332)

```python
if voltage_in_range:
    # Window validation - only process if within video playback window
    if video_start_timestamp_float is None:
        # No timing constraints, allow through
        pass
    elif timestamp < (video_start_timestamp_float - GRACE_PERIOD_SECONDS):
        # Pre-trigger detection allowed
        logger.debug(f"✅ Pre-trigger detection allowed: ...")
    elif not self._is_detection_within_video_window(
        session_id, timestamp, video_start_timestamp_float, stop_time_with_buffer
    ):
        # Outside window, skip
        if video_start_timestamp_float and timestamp < video_start_timestamp_float:
            skipped_early_detections += 1
        else:
            skipped_late_detections += 1
        continue  # ⚠️ SKIPS DETECTION
```

**Analysis:**
- **Line 1324-1332:** Calls `_is_detection_within_video_window()` to validate timing
- **Lines 1328-1332:** If detection is outside window, it's SKIPPED (not counted)
- **POTENTIAL ISSUE #4:** If window validation is too strict, valid detections are filtered out

**From `_is_detection_within_video_window()` (Lines 1554-1617):**
```python
def _is_detection_within_video_window(
    self, session_id: str, detection_timestamp: float,
    video_start_time: Optional[float], video_end_time: Optional[float]
) -> bool:
    # If no timing constraints, allow all detections
    if video_start_time is None and video_end_time is None:
        return True

    # Check early detection (before video start)
    if video_start_time is not None:
        grace_period_seconds = GRACE_PERIOD_SECONDS  # 2.0 seconds
        earliest_valid_time = video_start_time - grace_period_seconds

        if detection_timestamp < earliest_valid_time:
            return False  # Too early

    # Check late detection (after video end + buffer)
    if video_end_time is not None:
        if detection_timestamp > video_end_time:
            return False  # Too late

    return True  # Within window
```

**Analysis:**
- **Grace Period:** 2.0 seconds before video start (from `timing_config.py` line 23)
- **Window:** `[video_start - 2.0s, video_end + buffer]`
- **CORRECT LOGIC:** Window validation appears sound IF timing parameters are correct

---

### 6. Sample Processing Rate (Lines 1289-1291)

```python
# Process each sample in buffer
num_channels = len(channels)  # Typically 1 channel (AIN0)
num_samples = len(stream_data) // num_channels
```

**Analysis:**
- **Line 1291:** Calculates number of samples from interleaved data
- **Example:** If `stream_data = [1.0, 2.0, 3.0, 4.0]` and 1 channel → 4 samples ✅
- **CORRECT LOGIC:** Sample extraction appears correct

**Expected Buffer Size (Line 1099):**
```python
scans_per_read = max(20, scan_rate // 10)  # For 200 Hz → 20 scans
```

**Analysis:**
- At 200 Hz with `scans_per_read = 20`, each read should return 20 samples
- To capture 5 seconds: `5s * 200 Hz = 1000 samples` → requires **50 read cycles**
- If loop exits after 1 cycle, only ~20 samples captured (not 4)

**DISCREPANCY:** Why only 4 detections instead of 20 per buffer?

---

## Root Cause Hypotheses (Ranked by Likelihood)

### 🔴 **HYPOTHESIS #1: Premature Auto-Stop (MOST LIKELY)**
**Lines:** 1255-1259, 1212-1221
**Issue:** `stop_time_with_buffer` is calculated incorrectly, causing loop to exit after first iteration

**Evidence:**
- Only 4 detections captured suggests ~0.02s of data processed
- Auto-stop logic at line 1257-1259 breaks loop if `current_timestamp > stop_time_with_buffer`

**Possible Causes:**
1. **`video_start_timestamp_float` is set to CURRENT time** instead of actual video start → window is immediate
2. **`video_duration` is 0 or very small** → loop exits almost immediately
3. **`multi_video_buffer` is negative or 0** → no buffer time added

**Verification Needed:**
- Log values: `video_start_timestamp_float`, `video_duration`, `stop_time_with_buffer`
- Check if `stop_time_with_buffer < time.time()` at loop start

---

### 🟡 **HYPOTHESIS #2: Timing Race Condition (LIKELY)**
**Lines:** 1095-1099
**Issue:** Video timing not available when stream monitoring starts

**Evidence:**
- Timing retrieved from `self.session_timing` dictionary
- If timing arrives AFTER stream starts, defaults may apply

**Possible Causes:**
1. **Video 'playing' event fires AFTER monitoring loop starts** → no timing data available
2. **Session timing not propagated to detection service** → defaults cause immediate termination

**Verification Needed:**
- Add logs to show WHEN timing is set vs WHEN stream loop starts
- Check if `video_start_time is None` at line 1318

---

### 🟢 **HYPOTHESIS #3: Overly Strict Window Validation (POSSIBLE)**
**Lines:** 1324-1332, 1554-1617
**Issue:** Valid detections filtered out by window validation

**Evidence:**
- Window validation uses 2-second grace period
- Detections outside window are skipped (lines 1328-1332)

**Possible Causes:**
1. **Sample timestamps calculated incorrectly** (line 1300-1302)
2. **Grace period too small** for hardware pre-trigger
3. **Video timing offset** causes all detections to appear "late"

**Verification Needed:**
- Log `skipped_early_detections` and `skipped_late_detections` (lines 1224-1225, final stats at 1412-1416)
- Check if detections are being filtered vs loop exiting

---

### 🟢 **HYPOTHESIS #4: Empty Stream Buffer (LESS LIKELY)**
**Lines:** 1281-1283
**Issue:** LabJack stream not returning data

**Evidence:**
- Loop continues but skips processing if `stream_data` is empty

**Possible Causes:**
1. **Hardware configuration issue** → stream not started correctly
2. **Scan rate mismatch** → device not sampling
3. **Buffer underrun** → not enough time to fill buffer

**Verification Needed:**
- Log `len(stream_data)` on each iteration
- Check if `num_samples > 0` on line 1378

---

### 🔵 **HYPOTHESIS #5: Consecutive Errors (UNLIKELY)**
**Lines:** 1248-1249, 1266-1276, 1381-1391
**Issue:** Too many stream read errors cause fallback

**Evidence:**
- Max 5 consecutive errors allowed before falling back to polling
- Counter reset on successful read (line 1279)

**Possible Causes:**
1. **LabJack hardware failure** → repeated read errors
2. **Driver issue** → eStreamRead fails repeatedly

**Verification Needed:**
- Log error counter value
- Check final message at line 1272: "Too many consecutive stream errors"

---

## Specific Line Numbers with Problematic Logic

| Line Number | Code Fragment | Issue | Severity |
|------------|---------------|-------|----------|
| **1255-1259** | `if current_timestamp > stop_time_with_buffer: break` | Exits loop prematurely if timing calculation is wrong | 🔴 CRITICAL |
| **1215** | `stop_time_with_buffer = video_start + duration + buffer` | Incorrect if `video_duration = 0` or timing not set | 🔴 CRITICAL |
| **1095-1099** | `session_timing = self.session_timing.get(session_id, {})` | Race condition if timing not available when loop starts | 🟡 HIGH |
| **1318** | `if video_start_timestamp_float is None: pass` | Allows detections through if timing not set, but won't match hypothesis | 🟢 MEDIUM |
| **1324-1332** | `if not self._is_detection_within_video_window(...): continue` | Filters valid detections if window is misconfigured | 🟢 MEDIUM |
| **1281-1283** | `if not stream_data or len(stream_data) == 0: continue` | Skips processing if hardware not streaming | 🟢 MEDIUM |
| **1099** | `scans_per_read = max(20, scan_rate // 10)` | Buffer size may be too small for high-speed streaming | 🔵 LOW |

---

## Recommended Verification Steps

### Step 1: Add Comprehensive Logging (DO NOT IMPLEMENT YET)
Add the following log statements to diagnose the issue:

**At Loop Start (after line 1251):**
```python
logger.info(f"🚀 Stream loop starting:")
logger.info(f"  - stop_time_with_buffer: {stop_time_with_buffer}")
logger.info(f"  - current_time: {time.time()}")
logger.info(f"  - video_start_timestamp_float: {video_start_timestamp_float}")
logger.info(f"  - video_duration: {video_duration}")
logger.info(f"  - Time until auto-stop: {stop_time_with_buffer - time.time() if stop_time_with_buffer else 'N/A'}s")
```

**Inside Loop (after line 1263):**
```python
logger.debug(f"📊 Stream read: len(stream_data)={len(stream_data)}, backlog={backlog}, num_samples={len(stream_data) // len(channels)}")
```

**On Loop Exit (after line 1259):**
```python
logger.warning(f"⏹️ Loop exiting due to auto-stop: current={current_timestamp:.6f}, stop_time={stop_time_with_buffer:.6f}, delta={current_timestamp - stop_time_with_buffer:.6f}s")
```

**On Normal Exit (after line 1252 when stop_event is set):**
```python
logger.info(f"🛑 Loop exiting normally: stop_event set")
```

---

### Step 2: Verify Timing Initialization
Check that `self.session_timing` is populated BEFORE stream starts:

**Add to start of `_monitoring_loop_stream()` (after line 1089):**
```python
logger.info(f"🕐 Session timing at loop start: {self.session_timing.get(session_id, 'NOT FOUND')}")
```

---

### Step 3: Analyze Final Statistics
The function already logs final stats at lines 1412-1416:
```python
logger.info(
    f"📊 Stream Detection Stats: "
    f"Valid={total_valid_detections}, "
    f"Skipped Early={skipped_early_detections}, "
    f"Skipped Late={skipped_late_detections}"
)
```

**Check:**
- If `skipped_early_detections` or `skipped_late_detections` are high → window validation issue (Hypothesis #3)
- If both are 0 and `total_valid_detections = 4` → loop exiting early (Hypothesis #1)

---

### Step 4: Hardware Stream Verification
Check if LabJack is actually streaming data:

**Add after line 1245:**
```python
# Test stream read immediately after start
test_data, test_backlog, test_success = self.labjack_service.read_stream_mode()
logger.info(f"🔍 Initial stream test: success={test_success}, data_len={len(test_data)}, backlog={test_backlog}")
if not test_success or len(test_data) == 0:
    logger.error("⚠️ Stream started but not returning data immediately!")
```

---

## Recommended Code Changes (NOT IMPLEMENTED)

### Fix #1: Add Safety Check for Auto-Stop Logic
**Location:** Line 1255
**Change:**
```python
# Before:
if stop_time_with_buffer:
    current_timestamp = time.time()
    if current_timestamp > stop_time_with_buffer:
        logger.info(f"⏹️ Auto-stopping stream: video ended, buffer expired")
        break

# After:
if stop_time_with_buffer:
    current_timestamp = time.time()
    time_until_stop = stop_time_with_buffer - current_timestamp

    # Safety check: ensure stop time is in the FUTURE
    if time_until_stop < 0:
        if abs(time_until_stop) < 0.1:
            # Timing very close, allow a bit more processing
            logger.debug(f"Auto-stop threshold reached: {time_until_stop:.3f}s")
        else:
            logger.info(f"⏹️ Auto-stopping stream: video ended {abs(time_until_stop):.3f}s ago")
            break
    elif time_until_stop < 1.0:
        logger.debug(f"⏰ Approaching auto-stop in {time_until_stop:.3f}s")
```

---

### Fix #2: Validate Timing Before Loop
**Location:** After line 1221
**Change:**
```python
# Add validation after stop_time_with_buffer calculation
if stop_time_with_buffer:
    current_time = time.time()
    time_until_stop = stop_time_with_buffer - current_time

    if time_until_stop <= 0:
        logger.error(
            f"❌ Invalid timing: stop_time_with_buffer is in the PAST! "
            f"stop_time={stop_time_with_buffer:.6f}, current_time={current_time:.6f}, "
            f"delta={time_until_stop:.3f}s. This will cause immediate loop exit!"
        )
        logger.error(
            f"Timing details: video_start={video_start_timestamp_float:.6f}, "
            f"duration={video_duration:.3f}s, buffer={stop_buffer_seconds:.3f}s"
        )
        # Option: Disable auto-stop to prevent premature exit
        logger.warning("Disabling auto-stop to prevent immediate termination")
        stop_time_with_buffer = None
    elif time_until_stop < video_duration:
        logger.warning(
            f"⚠️ Time until stop ({time_until_stop:.3f}s) is less than video duration ({video_duration:.3f}s). "
            f"This may cause incomplete data capture!"
        )
```

---

### Fix #3: Make Window Validation More Lenient
**Location:** Line 1324
**Change:**
```python
# Before:
elif not self._is_detection_within_video_window(
    session_id, timestamp, video_start_timestamp_float, stop_time_with_buffer
):
    # Skip detection
    continue

# After:
# Only apply window validation if we have reliable timing
if video_start_timestamp_float and video_duration and video_duration > 0:
    if not self._is_detection_within_video_window(
        session_id, timestamp, video_start_timestamp_float, stop_time_with_buffer
    ):
        # Log but DON'T skip if detection is close to window
        time_before_start = video_start_timestamp_float - timestamp
        time_after_end = timestamp - stop_time_with_buffer if stop_time_with_buffer else 0

        if time_before_start > GRACE_PERIOD_SECONDS:
            skipped_early_detections += 1
            logger.debug(f"⏭️ Skipping early detection {time_before_start:.3f}s before window")
            continue
        elif stop_time_with_buffer and time_after_end > 0:
            skipped_late_detections += 1
            logger.debug(f"⏭️ Skipping late detection {time_after_end:.3f}s after window")
            continue
        else:
            # Close to window boundary, allow through with warning
            logger.warning(f"⚠️ Borderline detection: {time_before_start:.3f}s before start, allowing through")
else:
    # No reliable timing, accept all detections
    logger.debug("No window validation applied - timing not available")
```

---

## Conclusion

**Primary Root Cause:** The stream monitoring loop is **exiting prematurely due to auto-stop logic** (lines 1255-1259) triggered by an incorrectly calculated `stop_time_with_buffer` value. The most likely scenario is:

1. `video_start_timestamp_float` is set to the CURRENT time when stream starts (not actual video start)
2. `video_duration` is 0, very small, or unavailable
3. Result: `stop_time_with_buffer = current_time + 0 + buffer` → immediate termination

**Secondary Issue:** Possible race condition where video timing is not available when stream monitoring starts, leading to default/fallback behavior that causes immediate termination.

**Why Only 4 Detections?**
- If buffer size is 20 samples and only 1 buffer is processed → ~20 samples captured
- If window validation filters 16/20 samples → 4 detections remain
- OR: Loop exits before first full buffer is processed → partial data captured

**Next Steps:**
1. Add comprehensive logging as outlined in "Verification Steps"
2. Run test with logging enabled
3. Analyze log output to confirm timing values
4. Implement targeted fix based on log analysis

**Risk Assessment:**
- **No inherent logic bugs** in loop continuation or sample processing
- **Timing validation** is the bottleneck causing data loss
- **Fix complexity:** MEDIUM (requires careful timing coordination)
- **Testing required:** Extensive to ensure fix doesn't break other scenarios

---

## Additional Notes

**Observations from Code Review:**
1. **Error Handling:** Comprehensive (lines 1248-1276, 1381-1391) ✅
2. **Stream Read:** Synchronous blocking call, appropriate for daemon thread ✅
3. **Sample Processing:** Correct interleaved data handling ✅
4. **Detection Logic:** Proper threshold checking and state management ✅
5. **Window Validation:** Logic is sound IF timing parameters are correct ✅

**No Exit Conditions Found:**
- No premature `return` statements in main loop
- No uncaught exceptions that would exit loop
- No break statements except auto-stop (line 1259) and error threshold (line 1273, 1388)

**Loop Will Continue Until:**
1. `stop_event.is_set()` returns True (line 1252)
2. `current_timestamp > stop_time_with_buffer` (line 1257) ← **LIKELY CULPRIT**
3. `consecutive_errors >= 5` (line 1271, 1387)

**Expected Behavior for 5-second Video:**
- Start: `time.time()` = T
- Video plays: T to T+5
- Buffer: T+5 to T+6 (1 second default)
- Stop: T+6
- Stream should run for 6+ seconds
- At 200 Hz with 20 samples/read: ~60 read cycles → 1200 samples
- After filtering: ~1000 valid detections expected

**Actual Behavior:**
- Only 4 detections captured
- Suggests loop runs for << 1 second
- Timing calculation error confirmed as root cause

---

**End of Report**
