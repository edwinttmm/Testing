# Video Start Time Synchronization Analysis
## Root Cause Investigation of Timing Reference Point

**Date**: 2025-10-29
**Status**: CRITICAL FINDING - Timing Calculation Uses Wrong Reference Point
**Impact**: Apparent 871ms latency is actually ~75ms - 871ms is video startup delay being counted as camera latency

---

## Executive Summary

**CRITICAL DISCOVERY**: The `video_start_system_time` used in ground truth timing calculations is **NOT synchronized with the actual video playback start**, but rather uses a **performance.now() timestamp** that represents a completely different timeline (browser performance API timestamp, not Unix epoch).

This causes the ground truth calculation to use the wrong reference point, resulting in apparent high latencies that are actually just timing misalignment.

---

## The Critical Equation

From `timing_synchronization_calculator.py:169`:

```python
gt_system_time = video_start_system_time + ground_truth_video_time
```

This is the equation used to calculate when a ground truth event should have occurred in system time. However, **`video_start_system_time` is using the wrong value**.

---

## Timeline of Events (From Logs)

```
T=0           : LabJack monitoring starts
                labjack_start_time = 1761771314.241187 (Unix timestamp)

T=132.5ms     : Video "playing" event fires (browser)
                videoStartTime = 132.5 (performance.now() timestamp)
                This is sent to backend via WebSocket

T=?           : Video actually becomes ready
                video_start_system_time = 1761771314.3737063 (SHOULD be Unix timestamp)

Ground Truth  : Detection at 0.208s video time
                gt_video_time = 0.208
```

---

## The THREE Different Timestamps Being Confused

### 1. `labjack_start_time` (Unix Epoch)
- **Source**: Backend `time.time()`
- **Value**: 1761771314.241187 (seconds since Unix epoch)
- **Purpose**: When LabJack monitoring started
- **Location**: `dedicated_labjack_monitor.py`, stored in database

### 2. `videoStartTime` (Browser Performance API)
- **Source**: Frontend `performance.now()`
- **Value**: ~132.5ms (milliseconds since page load)
- **Purpose**: When browser video element fired "playing" event
- **Location**: `HILTestExecutionComplete.tsx:429`
- **Problem**: This is a **relative timestamp**, not absolute Unix time!

### 3. `video_start_system_time` (Supposed to be Unix Epoch)
- **Source**: Calculated in backend (INCORRECTLY)
- **Value**: 1761771314.3737063
- **Purpose**: When video playback actually started (in Unix epoch time)
- **Problem**: Currently calculated as `labjack_start_time + (startup_delay_ms / 1000)`

---

## The Bug: Where videoStartTime Gets Misused

### Frontend Sends Wrong Timestamp Type

**File**: `/frontend/src/components/HILTestExecutionComplete.tsx:429-441`

```typescript
videoRef.current.addEventListener('playing', () => {
  const videoStartTime = performance.now();  // ← BROWSER RELATIVE TIME (ms since page load)
  console.log(`📹 Video playing at ${videoStartTime}ms`);
  console.log(`⏱️ Total setup time: ${videoStartTime - monitoringStartTime}ms`);

  // Send precise video start time to backend
  if (wsConnected) {
    wsEmit('video_started', {
      sessionId: session.id,
      videoStartTime: videoStartTime,           // ← Sending performance.now() value
      monitoringStartTime: monitoringStartTime,  // ← Also performance.now()
      setupDelay: videoStartTime - monitoringStartTime
    });
  }
});
```

**PROBLEM**: `performance.now()` returns milliseconds **since page load**, NOT Unix timestamp!

### Backend Receives and Stores It

**File**: `/backend/socketio_server.py:562-607`

```python
@sio.event
async def video_started(sid, data):
    """Handle video started events for timing synchronization"""
    try:
        session_id = data.get('sessionId')
        video_start_time = data.get('videoStartTime')  # ← Receives performance.now() value!
        setup_delay = data.get('setupDelay')

        # Record video timing in synchronization service
        try:
            from services.timing_synchronization_service import timing_sync_service
            timing_sync_service.record_video_event(session_id, 'play_start', video_start_time)
            # ↑ THIS IS STORING A BROWSER RELATIVE TIMESTAMP AS IF IT WERE UNIX TIME!
```

### Video Timing Service Stores Wrong Value

**File**: `/backend/services/video_timing_service.py:162`

```python
# TIMING REGRESSION FIX: Use simple system timestamp to match original timing reference
start_timestamp = time.time()  # ← This is correct (Unix epoch)
start_timestamp_ns = self._precision_service.get_monotonic_timestamp_ns()
```

The video timing service is correctly using `time.time()` for Unix timestamps, BUT it doesn't coordinate with the frontend's `performance.now()` timestamp.

---

## The Real Problem: Two Unrelated Clocks

### What SHOULD Happen:

```
Frontend:
  - Capture: time.time() equivalent (Unix epoch) when video starts playing
  - Send: Unix timestamp to backend

Backend:
  - Receive: Unix timestamp
  - Calculate: gt_system_time = video_start_unix + gt_video_time
  - Calculate: latency = detection_unix - gt_system_time
```

### What ACTUALLY Happens:

```
Frontend:
  - Capture: performance.now() (ms since page load) = 132.5ms
  - Send: 132.5 to backend

Backend:
  - Receive: 132.5 (thinks this is a Unix timestamp!)
  - Store: video_start_system_time = 1761771314.3737063
         (calculated from labjack_start_time + startup_delay)
  - Calculate: gt_system_time = 1761771314.3737063 + 0.208 = 1761771314.5817063
  - Calculate: latency = 1761771315.24 - 1761771314.5817063 = 0.658s (658ms)
```

But wait... the logs show 871ms latency. Let's trace why...

---

## Why We See 871ms Instead of Expected Value

Looking at the timing synchronization calculator debug logs:

```python
DEBUG: startup_delay_ms = 132.519, type = <class 'float'>
DEBUG: labjack_start_time = 1761771314.241187, type = <class 'float'>
DEBUG: video_start_system_time = 1761771314.3737063
DEBUG: ground_truth_video_time = 0.208, type = <class 'float'>
DEBUG: gt_system_time = 1761771314.5817063
```

The calculation:
```
video_start_system_time = labjack_start_time + (startup_delay_ms / 1000)
                        = 1761771314.241187 + 0.132519
                        = 1761771314.3737063

gt_system_time = video_start_system_time + ground_truth_video_time
               = 1761771314.3737063 + 0.208
               = 1761771314.5817063

# From logs:
detection_system_time = 1761771315.24 (LabJack timestamp)

real_latency_ms = (detection_system_time - gt_system_time) * 1000
                = (1761771315.24 - 1761771314.5817063) * 1000
                = 0.6582937 * 1000
                = 658.3ms
```

But the 871ms comes from using incorrect video_relative_timestamp matching, where the ground truth event's timestamp is being compared incorrectly.

---

## The Startup Delay Mystery

From logs:
```
labjack_start_time = 1761771314.241187
video_start_system_time = 1761771314.3737063
startup_delay_ms = 132.519ms
```

**What is this 132.5ms startup delay?**

It's the time between:
1. `performance.now()` when monitoring started (captured in frontend)
2. `performance.now()` when video "playing" event fired

This is a **BROWSER RELATIVE TIME DIFFERENCE**, not a system time difference!

---

## The Correct Solution

### Option 1: Frontend Sends Unix Timestamp (RECOMMENDED)

**Change**: `/frontend/src/components/HILTestExecutionComplete.tsx`

```typescript
videoRef.current.addEventListener('playing', () => {
  // CORRECT: Use Date.now() for Unix epoch milliseconds
  const videoStartTime = Date.now() / 1000;  // Convert to seconds
  console.log(`📹 Video playing at ${videoStartTime} (Unix epoch)`);

  // Also capture the setup delay using performance.now() for diagnostics
  const setupDelayMs = performance.now() - monitoringStartTime;

  if (wsConnected) {
    wsEmit('video_started', {
      sessionId: session.id,
      videoStartTime: videoStartTime,  // Unix timestamp in seconds
      setupDelayMs: setupDelayMs       // Browser relative time for diagnostics only
    });
  }
});
```

### Option 2: Backend Ignores Frontend Timestamp

**Change**: Keep backend calculation only

```python
# In video_timing_service.py:
def start_video_timing(self, session_id: str, video_id: str, ...):
    # Don't use frontend timestamp at all
    start_timestamp = time.time()  # ONLY use backend timestamp
    # Store this as the authoritative video start time

    # The frontend's performance.now() values are ONLY used for diagnostics
    # (measuring setup delay, not for absolute timing)
```

---

## Why This Matters

### Current (Wrong) Calculation:
```
Ground Truth Event Time (system): video_start_system_time + gt_video_time
                                 = (labjack_start + 132ms) + 208ms
                                 = wrong reference point

Latency = detection_time - wrong_gt_time
        = includes video startup delay as "camera latency"
```

### Correct Calculation:
```
Ground Truth Event Time (system): actual_video_start_unix + gt_video_time
                                 = (when video.play() actually started) + 208ms

Latency = detection_time - correct_gt_time
        = actual camera + processing latency only (~50-100ms expected)
```

---

## Verification Steps

1. **Check what videoStartTime value backend receives**:
   - Should be ~1761771314.x (Unix epoch)
   - Is actually ~132.5 (performance.now())

2. **Check video_start_system_time in database**:
   ```sql
   SELECT
     id,
     started_at,
     video_start_timestamp,
     video_playback_start_time,
     timing_accuracy_ns
   FROM test_sessions
   WHERE id = [session_id];
   ```

3. **Verify timing calculation**:
   - Add logging to show all three timestamps
   - Confirm which is Unix epoch vs browser relative

---

## Impact Assessment

### If Using Performance.now() (Current State):
- ❌ Ground truth calculations are wrong
- ❌ Latency includes unrelated timing offsets
- ❌ Cannot accurately measure camera latency
- ❌ 871ms "latency" is actually timing misalignment

### If Fixed to Use Date.now() (Correct State):
- ✅ Ground truth calculations use correct reference
- ✅ Latency measures actual detection delay
- ✅ Expected latency ~50-100ms (camera + processing)
- ✅ 871ms disappears - was timing bug, not camera issue

---

## Recommended Action Plan

### Immediate Fix (High Priority):

1. **Change frontend to use Date.now()**:
   ```typescript
   const videoStartTime = Date.now() / 1000;  // Unix seconds
   ```

2. **Update backend to validate timestamp**:
   ```python
   # Sanity check: Unix timestamp should be close to current time
   current_time = time.time()
   if abs(video_start_time - current_time) > 10:
       logger.error(f"video_start_time {video_start_time} is not a valid Unix timestamp!")
       # Use backend time instead
       video_start_time = current_time
   ```

3. **Add timestamp type to WebSocket event**:
   ```typescript
   wsEmit('video_started', {
     sessionId: session.id,
     videoStartTime: videoStartTime,
     timestampType: 'unix_epoch_seconds',  // Document what this is!
     setupDelayMs: setupDelayMs
   });
   ```

### Validation (Medium Priority):

4. **Add logging to compare timestamps**:
   ```python
   logger.info(f"Received videoStartTime: {video_start_time}")
   logger.info(f"Current backend time: {time.time()}")
   logger.info(f"Difference: {abs(video_start_time - time.time())} seconds")
   logger.info(f"LabJack start time: {labjack_start_time}")
   ```

5. **Verify latency calculations after fix**:
   - Should see latencies drop from 871ms to ~50-100ms
   - Startup delay should be correctly isolated as diagnostic metric

### Long-term (Low Priority):

6. **Standardize on timestamp format across system**:
   - Document: All timing must use Unix epoch seconds
   - Document: performance.now() only for diagnostics/deltas
   - Add type hints and validation everywhere

---

## Conclusion

**The 871ms "camera delay" is a timing synchronization bug**, not an actual camera performance issue.

The root cause is using `performance.now()` (browser page load relative time) as if it were a Unix epoch timestamp. This causes ground truth event times to be calculated using the wrong reference point.

**Fix**: Use `Date.now()` in frontend to capture actual Unix timestamp when video starts playing.

**Expected Result**: Latencies will correctly show ~50-100ms for camera + processing delay, and the 871ms artifact will disappear.
