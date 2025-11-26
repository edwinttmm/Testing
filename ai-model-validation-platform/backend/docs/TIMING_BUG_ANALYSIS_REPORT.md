# Timing Synchronization and Latency Calculation Bug Analysis Report

**Generated:** 2025-11-24
**Session:** ce45b6c2-9f66-4106-8804-a8974910529d
**Status:** CRITICAL BUGS IDENTIFIED

---

## Executive Summary

Multiple interconnected bugs have been identified in the timing synchronization, latency calculation, and validation logic that cause:
1. **97%+ camera overhead** calculations when camera latency is only 200ms
2. **All timing quality marked as "unreliable"** despite valid data
3. **Negative latency values** (-13ms, -12ms, -7ms) causing PASS/FAIL confusion
4. **Ground truth matching failures** despite ±100ms tolerance window
5. **5000ms hardcoded offsets** creating artificial latency corrections

---

## Bug #1: Hardcoded 5000ms Offset in Dynamic Latency Correction

### Location
**File:** `/backend/services/timing_synchronization_calculator.py`
**Lines:** 128-156, 284-291

### The Problem
```python
def calculate_latency_correction(self, detection_system_time, gt_system_time,
                                 video_start_system_time, startup_delay_ms):
    """Calculate dynamic latency correction based on video timing context.
    Replaces hardcoded 5000ms correction with per-detection calculation."""

    # Calculate apparent latency (from video start to detection)
    apparent_latency_s = detection_system_time - video_start_system_time

    # Calculate real latency (from GT event to detection)
    real_latency_s = detection_system_time - gt_system_time

    # Correction is the difference
    correction_s = apparent_latency_s - real_latency_s

    return correction_s * 1000.0  # Return in milliseconds
```

**Why it's wrong:**
- The function claims to replace "hardcoded 5000ms" but the logic is fundamentally flawed
- `apparent_latency_s` includes the entire video position (0-10 seconds)
- `real_latency_s` is just the detection latency (typically 50-200ms)
- `correction_s = apparent_latency_s - real_latency_s` produces values in the 1000-9000ms range
- This creates **massive artificial corrections** that don't represent actual timing issues

**Evidence from test report:**
```json
{
  "average_latency_ms": 2100.697,
  "max_latency_ms": 9077.594,
  "latency_distribution": {
    "500ms+": 83  // 83 out of 138 detections show >500ms latency
  }
}
```

**Impact:**
- Detections at 5s video position get ~5000ms "correction"
- Detections at 9s video position get ~9000ms "correction"
- This is NOT correcting for startup delay - it's adding video position as latency

---

## Bug #2: Camera Overhead Calculation is Inverted

### Location
**File:** `/backend/services/latency_decomposition_service.py`
**Lines:** 337-394, 108-111

### The Problem
```python
def decompose_latency(self, session_id, detection_id, total_latency_ms,
                     detection_metadata=None):
    # Extract system baseline overhead
    system_baseline_ns = baseline.total_baseline_ns  # ~2-5ms typically

    # Estimate processing pipeline overhead
    processing_overhead_ns = self._estimate_processing_overhead(metadata)  # ~5-8ms

    # Estimate network/communication overhead
    network_overhead_ns = self._estimate_network_overhead(metadata)  # ~0.5-1ms

    # Estimate synchronization overhead
    sync_overhead_ns = self._estimate_sync_overhead(metadata)  # ~0.5-1ms

    # Calculate camera latency (remaining after subtracting overheads)
    total_overhead_ns = (system_baseline_ns + processing_overhead_ns +
                        network_overhead_ns + sync_overhead_ns)

    camera_latency_ns = max(0, total_latency_ns - total_overhead_ns)  # ⚠️ BUG HERE
```

**Why it's wrong:**
When `total_latency_ms` is **inflated** by Bug #1 (e.g., 6000ms instead of 200ms):
- System overhead: ~10-15ms (correct)
- Total latency: 6000ms (WRONG - includes video position)
- Camera latency: 6000ms - 15ms = **5985ms**
- Overhead percentage: 15ms / 6000ms = **0.25%**

But the code **reports it inverted**:
```python
def get_overhead_percentage(self):
    overhead = (system_baseline_ms + processing_overhead_ms +
                network_overhead_ms + sync_overhead_ms + unknown_overhead_ms)
    return (overhead / total_latency_ms) * 100.0
```

**The actual bug is in Bug #1 - total_latency_ms is wrong!**

When the "Unknown overhead" adjustment kicks in:
```python
if camera_latency_ns > camera_latency_bounds_ns[1]:  # bounds = (10ms, 200ms)
    # Camera latency exceeds expected bounds, some overhead is unaccounted
    unknown_overhead_ns = camera_latency_ns - camera_latency_bounds_ns[1]  # 5985 - 200 = 5785ms
    camera_latency_ns = camera_latency_bounds_ns[1]  # Capped at 200ms
```

Now we get:
- Camera latency: 200ms (capped)
- Unknown overhead: 5785ms (the video position error from Bug #1)
- Total overhead: 5785 + 15 = 5800ms
- **Overhead percentage: 5800ms / 6000ms = 96.7%** ✓ Matches the report!

**Evidence:**
```
Camera overhead: 97.1% when camera latency is only 200ms of 6-9 second total
```

---

## Bug #3: "Apparent" vs "Real" Latency Confusion

### Location
**File:** `/backend/services/timing_synchronization_calculator.py`
**Lines:** 264-291

### The Problem
```python
# Apparent latency = total time from LabJack start to detection
apparent_latency_ms = (detection_system_time - labjack_start_time) * 1000.0

# Real latency = detection_time - ground_truth_event_system_time
real_latency_ms = (detection_system_time - gt_system_time) * 1000.0

# Correction is the difference
latency_correction_ms = apparent_latency_ms - real_latency_ms
```

**What these actually mean:**
- `apparent_latency_ms`: Time from **session start** to detection (includes all video position)
- `real_latency_ms`: Time from **GT event** to detection (actual detection latency)
- `latency_correction_ms`: **Not a correction!** This is just the GT event's position in the session

**Example calculation:**
```
labjack_start_time = 1763978801.0
gt_system_time = 1763978806.0  (5 seconds into session)
detection_system_time = 1763978806.2  (detection occurs 200ms after GT)

apparent_latency_ms = (1763978806.2 - 1763978801.0) * 1000 = 5200ms
real_latency_ms = (1763978806.2 - 1763978806.0) * 1000 = 200ms
latency_correction_ms = 5200 - 200 = 5000ms  ⚠️ This is not a "correction"!
```

**Impact:**
- The 5000ms "correction" is actually just the ground truth event's position (5 seconds)
- Applying this as a "correction" to latency calculations adds video position as latency
- This is the root cause of the 6-9 second latencies in the report

---

## Bug #4: Quality Assessment Marks Everything "Unreliable"

### Location
**File:** `/backend/services/timing_synchronization_calculator.py`
**Lines:** 719-746

### The Problem
```python
def _assess_traditional_timing_quality(self, real_latency_ms, startup_delay_ms,
                                      timing_accuracy_ns):
    # Check if latency is within expected range
    latency_reasonable = (self.expected_processing_time_range[0] <= real_latency_ms
                         <= self.expected_processing_time_range[1])  # (50, 100)ms

    # Check startup delay reasonableness (should be > 1000ms for video startup)
    startup_delay_reasonable = 1000 <= startup_delay_ms <= 5000

    # Check timing accuracy if available
    timing_accuracy_good = True
    if timing_accuracy_ns is not None:
        timing_accuracy_good = timing_accuracy_ns <= 1_000_000  # <= 1ms

    if latency_reasonable and startup_delay_reasonable and timing_accuracy_good:
        return "excellent"
    elif latency_reasonable and startup_delay_reasonable:
        return "good"
    elif latency_reasonable or startup_delay_reasonable:
        return "fair"
    else:
        return "poor"  # ⚠️ Everything falls here!
```

**Why everything is marked "poor":**
1. `real_latency_ms` is 2000-9000ms (due to Bug #1) - NOT in (50, 100)ms range → `latency_reasonable = False`
2. `startup_delay_ms` is typically 200-300ms for HIL hardware - NOT in (1000, 5000)ms range → `startup_delay_reasonable = False`
3. Both conditions false → Quality = "poor" (unreliable)

**The thresholds are wrong:**
- Expected latency (50-100ms): Too narrow, doesn't account for camera specs
- Startup delay (1000-5000ms): This is for **video file decoding**, not **hardware camera startup**
- Hardware cameras have ~50-300ms initialization, not 1-5 seconds

**Impact:**
```
"timing_quality": "unreliable" for 138/138 detections
```

---

## Bug #5: Ground Truth Matching Tolerance Window Failure

### Location
**File:** `/backend/services/ground_truth_matching_service.py`
**Lines:** 585-672

### The Problem
```python
def _find_closest_ground_truth(self, detection, ground_truth_events):
    detection_video_timestamp = detection.get('video_relative_timestamp')

    if detection_video_timestamp is not None:
        detection_time = float(detection_video_timestamp)

        # Use adaptive tolerance based on video timing quality
        base_tolerance_ms = 500  # Base 500ms tolerance  ⚠️ Too large!
        max_tolerance_ms = 2000  # Maximum 2s tolerance  ⚠️ WAY too large!

        timing_looks_reliable = 0 <= detection_time <= 60
        time_tolerance_ms = base_tolerance_ms if timing_looks_reliable else max_tolerance_ms

        def time_distance(gt):
            gt_timestamp = gt.get('timestamp', gt.get('video_timestamp'))
            gt_time = float(gt_timestamp)
            time_diff_ms = abs((gt_time - detection_time) * 1000)

            if time_diff_ms <= time_tolerance_ms:
                return time_diff_ms
            else:
                return float('inf')  # Outside tolerance, ignore
```

**Multiple Issues:**

### 5a. Tolerance Window is 500ms, Not ±100ms
The code uses:
- Base tolerance: **500ms** (not 100ms)
- Max tolerance: **2000ms** (for "degraded" timing)

But the system specification requires:
- Tolerance: **±100ms** for ground truth matching

**Impact:**
- System is looking for GT events within ±500ms instead of ±100ms
- This makes it **harder** to find matches because inflated latencies (from Bug #1) put detections 6-9 seconds away from their GT events
- A detection at "real time" 5.2s gets inflated to 5200ms latency, so it's matched against GT at 10.2s video time (5.2 + 5.0) instead of 5.2s

### 5b. Video-Relative Timestamp Calculation is Wrong

When `video_relative_timestamp` is calculated:
```python
# From timing_synchronization_calculator.py, line 296
video_relative_timestamp = detection_system_time - video_start_system_time
```

For multi-video sequences:
- Video 1: `video_start_system_time = session_start_time` ✓ Correct
- Video 2: `video_start_system_time = session_start_time` ✗ **Should be video2_start_time**

**Example:**
```
Session starts: 1763978801.0
Video 1 plays: 1763978801.0 - 1763978811.0 (10 seconds)
Video 2 plays: 1763978811.0 - 1763978821.0 (10 seconds)

Detection at 1763978815.0 (4 seconds into Video 2):
video_relative_timestamp = 1763978815.0 - 1763978801.0 = 14.0 seconds  ✗ WRONG!
Should be: 1763978815.0 - 1763978811.0 = 4.0 seconds  ✓ Correct

Ground truth for Video 2 has timestamps 0-10s (video-relative)
Detection is looking for GT at 14s (doesn't exist!)
Result: "No ground truth events within 500ms"
```

### 5c. Frame-Based Fallback Uses Absolute Frame Numbers

```python
# Fallback to frame-based matching if time-based fails
detection_frame = detection.get('frame_number')

def frame_dist(gt):
    gf_int = int(gt.get('frame_number'))
    return abs(gf_int - detection_frame)

closest_gt = min(ground_truth_events, key=frame_dist)
```

**Problem:**
- Detection frame numbers are **session-relative** (0-600 for 20 seconds @ 30fps)
- Ground truth frame numbers are **video-relative** (0-300 per video)
- Comparing detection frame 450 (Video 2, frame 150) to GT frames 0-300 (Video 2) gives massive differences

**Evidence from logs:**
```
"No ground truth events within 500ms of detection at 14.000s"
"Frame-based fallback: detection frame 450 matched to GT frame 300 (diff: 150 frames)"
```

---

## Bug #6: Negative Latency Values

### Location
Multiple files, root cause in timing calculation

### The Problem
Test report shows:
```json
{
  "min_latency_ms": -20.607,
  "latency_distribution": {
    "0-50ms": 51  // Some of these may be negative
  }
}
```

Logs mention: "Detection at -13ms, -12ms, -7ms causing FAIL"

### Root Causes

#### 6a. Timestamp Validation Failure
```python
# From timing_synchronization_calculator.py, line 228-262
current_time = time.time()
time_span = detection_system_time - labjack_start_time

labjack_age = abs(current_epoch - labjack_start_time)
detection_age = abs(current_epoch - detection_system_time)

timestamp_validation_failed = (
    labjack_age > 86400 or  # More than 24 hours old
    detection_age > 86400 or  # More than 24 hours old
    time_span > 600  # More than 10 minutes span for short video
)

if timestamp_validation_failed:
    # Use position-based estimate instead
    real_latency_ms = 75.0 + (video_position_factor * 25.0)  # 75-325ms range
```

**Why negative values occur:**
- Validation only checks if timestamps are "too old" (>24 hours)
- Doesn't check if detection timestamp is **before** video start
- When detection arrives before video fully initializes, negative values slip through

#### 6b. Clock Skew Not Detected
```python
# From latency_validation_service.py, line 151-153
if latency_ms < 0:
    # Detection before video start - error condition
    result = LatencyResult.ERROR
```

This correctly marks negative latencies as ERROR, but:
- These ERROR results still get included in statistics
- PASS/FAIL logic doesn't check for ERROR state
- Detections with negative latency appear as "0-50ms" in distribution

---

## Bug #7: PASS/FAIL Logic Doesn't Account for Inflated Latencies

### Location
**File:** `/backend/services/test_execution_service.py`
**Lines:** 247-248, 410

### The Problem
```python
# Pass if latency <= threshold, Fail otherwise
if latency <= latency_threshold_ms:  # threshold = 100ms
    validation_result = "Pass"
else:
    validation_result = "Fail"
```

**Why it causes incorrect results:**
1. `latency` value is inflated by Bug #1 (6000ms instead of 200ms)
2. Detections with actual 50ms latency show as 5050ms → FAIL
3. Threshold is 100ms, so nearly everything fails
4. The few PASSes (52/138) are detections with negative or near-zero latency (Bug #6)

**Evidence from report:**
```json
{
  "passed_events": 52,
  "failed_events": 86,
  "average_latency_ms": 2100.697,  // Inflated by Bug #1
  "latency_threshold_ms": 100,
  "success_summary": {
    "average_success_latency_ms": 0.23  // Only near-zero latencies pass!
  }
}
```

**The 52 "passing" detections averaged 0.23ms - suspiciously low:**
- This suggests they had negative latencies that got abs()'d or clamped to 0
- Or they occurred during video initialization before timing started

---

## Interconnected Bug Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Detection occurs at real latency = 200ms                        │
│ GT event at video position = 5.0 seconds                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────────────────────────────────────────┐
        │ BUG #1: Latency Correction Calculation                  │
        │ apparent = 5.2s, real = 0.2s, correction = 5.0s         │
        │ This adds video position as "correction"                │
        └─────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────────────────────────────────────────┐
        │ BUG #2: Latency Decomposition                           │
        │ Total latency = 5200ms (inflated)                       │
        │ Camera latency = 5200 - 15 = 5185ms                     │
        │ Capped at 200ms → Unknown overhead = 5000ms             │
        │ Result: 97% overhead, 3% camera                         │
        └─────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────────────────────────────────────────┐
        │ BUG #3: Quality Assessment                              │
        │ Latency = 5200ms, not in (50, 100)ms range              │
        │ Startup delay = 200ms, not in (1000, 5000)ms range      │
        │ Result: Quality = "unreliable"                          │
        └─────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────────────────────────────────────────┐
        │ BUG #4: Ground Truth Matching                           │
        │ video_relative_timestamp = 14s (should be 4s)           │
        │ Looking for GT at 14s, but GT only exists 0-10s         │
        │ Result: "No ground truth within 500ms"                  │
        └─────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────────────────────────────────────────┐
        │ BUG #5: PASS/FAIL Decision                              │
        │ Latency = 5200ms > threshold (100ms)                    │
        │ Result: FAIL                                            │
        └─────────────────────────────────────────────────────────┘
                              ↓
                ┌─────────────────────────┐
                │ Test Report: 86% FAIL   │
                │ Average latency: 2100ms │
                │ Quality: "unreliable"   │
                │ Camera overhead: 97%    │
                └─────────────────────────┘
```

---

## Priority Fixes

### CRITICAL (Must Fix Immediately)

1. **Fix Bug #1: Remove faulty latency correction**
   - File: `timing_synchronization_calculator.py`, lines 284-291
   - **Action:** Delete the `calculate_latency_correction` function call
   - **Replace with:** `latency_correction_ms = startup_delay_ms`
   - **Reason:** The "correction" is actually video position, not a timing offset

2. **Fix Bug #3: Use per-video start times**
   - File: `timing_synchronization_calculator.py`, lines 214-221
   - File: `ground_truth_matching_service.py`, lines 131-164
   - **Action:** Always use `video_start_time` parameter instead of `labjack_start_time`
   - **Reason:** Multi-video sequences need per-video timing

3. **Fix Bug #4: Correct quality assessment thresholds**
   - File: `timing_synchronization_calculator.py`, lines 719-746
   - **Action:**
     ```python
     # Hardware camera expectations (not video file expectations)
     latency_reasonable = 10 <= real_latency_ms <= 500  # 10-500ms range
     startup_delay_reasonable = 50 <= startup_delay_ms <= 500  # 50-500ms hardware init
     ```

### HIGH (Fix Next)

4. **Fix Bug #5: Ground truth tolerance window**
   - File: `ground_truth_matching_service.py`, lines 600-606
   - **Action:** Change `base_tolerance_ms = 500` to `base_tolerance_ms = 100`
   - **Reason:** Spec requires ±100ms, not ±500ms

5. **Fix Bug #6: Negative latency detection**
   - File: `timing_synchronization_calculator.py`, lines 151-156
   - **Action:** Add check and reject:
     ```python
     if latency_ms < 0:
         logger.error(f"Negative latency detected: {latency_ms:.3f}ms")
         result = LatencyResult.ERROR
         return result
     ```

6. **Fix Bug #2: Latency decomposition validation**
   - File: `latency_decomposition_service.py`, lines 385-394
   - **Action:** Add warning when unknown overhead is high:
     ```python
     if unknown_overhead_ns > 1_000_000_000:  # > 1 second
         logger.warning(f"Suspiciously high unknown overhead: {unknown_overhead_ns/1e6:.1f}ms")
         logger.warning("This indicates total_latency_ms may be incorrect")
     ```

---

## Verification Testing

After fixes, verify with these checks:

### Test 1: Single Video Latency
```python
# Expected results:
- Latency range: 50-300ms (hardware camera typical)
- Camera latency: ~70-80% of total
- System overhead: ~20-30% of total
- Quality: "good" or "excellent"
- PASS rate: >90% for <100ms threshold
```

### Test 2: Multi-Video Sequence
```python
# Expected results:
- Video 1 detections match GT in 0-10s range
- Video 2 detections match GT in 0-10s range (NOT 10-20s)
- Ground truth matching: >95% success rate
- No "No ground truth within 500ms" warnings
```

### Test 3: Timing Consistency
```python
# Expected results:
- No negative latencies
- apparent_latency ≈ real_latency + startup_delay
- latency_correction ≈ startup_delay (NOT video position!)
- Overhead percentage: 20-40% (NOT 97%)
```

---

## Conclusion

The core issue is **Bug #1** - the `calculate_latency_correction` function adds video position as a "correction", creating cascading failures in:
- Latency decomposition (Bug #2)
- Quality assessment (Bug #4)
- Ground truth matching (Bug #5)
- PASS/FAIL decisions (Bug #7)

**Fix Bug #1 first**, then the other bugs will be much easier to address. The current system is measuring "time since session start" instead of "detection latency", which explains all the symptoms.
