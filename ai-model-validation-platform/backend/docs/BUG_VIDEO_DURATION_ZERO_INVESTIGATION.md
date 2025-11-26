# Bug Investigation: Zero-Duration Videos Causing Matching Failures

**Session ID:** `daad8bf6-b5da-4423-abc4-a85e83bc1c16`
**Date:** 2024-11-24
**Severity:** CRITICAL

## Problem Statement

Video timing map shows 0-duration videos, causing all ground truth matches to fail:

```
INFO:services.ground_truth_matching_service:📹 Video 1: 1763988511.882s - 1763988511.882s (duration: 0.00s)
INFO:services.ground_truth_matching_service:📹 Video 2: 1763988516.924s - 1763988516.924s (duration: 0.00s)
WARNING:services.optimal_matching_service:⚠️ No feasible matches found (all outside tolerance)
```

**Result:** All 8 detections marked as False Positives.

---

## Root Cause

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py`
**Line:** 1050

```python
# BUG: Uses result.actual_duration_ms which is NULL in database
duration_s = result.actual_duration_ms / 1000.0 if result.actual_duration_ms else 0
video_end = video_start + duration_s if video_start else None
```

**Database Evidence:**

```python
# SequenceVideoResult data for session daad8bf6-b5da-4423-abc4-a85e83bc1c16

Video 1:
  video_start_time: 1763988511.881546
  video_end_time: 1763988516.9232128  ✅ CORRECT (populated)
  actual_duration_ms: None             ❌ BUG (not populated)

  Calculated:
    duration_s = 0.00s                 ❌ WRONG
    video_end = video_start + 0        ❌ WRONG (same as start)

Video 2:
  video_start_time: 1763988516.9242127
  video_end_time: 1763988521.9648795  ✅ CORRECT (populated)
  actual_duration_ms: None             ❌ BUG (not populated)

  Calculated:
    duration_s = 0.00s                 ❌ WRONG
    video_end = video_start + 0        ❌ WRONG (same as start)
```

**Video Model Has Duration:**

```python
# From models.py - Video table has duration in seconds:
Video.duration = 5.041666666666667  # ✅ Available for both videos
```

---

## Why This Breaks Matching

When video duration = 0:
- Video boundaries: `[video_start, video_start]` (zero-width window)
- Detection at `video_start + 0.5s` is OUTSIDE the window
- All detections marked as out-of-bounds → False Positives
- Correct matches impossible

**Example:**
```
Video 1 timing map: 1763988511.882s - 1763988511.882s (0.00s duration)
Detection timestamp: 1763988512.382s (0.5s into video)
Result: OUTSIDE video bounds → FALSE POSITIVE ❌
```

---

## Fix Options

### Option 1: Use Existing video_end_time (RECOMMENDED)

`SequenceVideoResult.video_end_time` is already populated correctly.

```python
# BEFORE (Line 1050):
duration_s = result.actual_duration_ms / 1000.0 if result.actual_duration_ms else 0
video_end = video_start + duration_s if video_start else None

# AFTER:
video_end = result.video_end_time  # Already correct in DB
duration_s = (video_end - video_start) if (video_end and video_start) else 0
```

**Pros:**
- Uses authoritative source (already-calculated end time)
- No dependency on `actual_duration_ms`
- Matches what's actually in the database

---

### Option 2: Calculate from video_end_time - video_start_time

```python
# Calculate duration from start/end times
if result.video_start_time and result.video_end_time:
    video_start = result.video_start_time
    video_end = result.video_end_time
    duration_s = video_end - video_start
else:
    video_start = result.video_start_time
    duration_s = 0
    video_end = video_start
```

---

### Option 3: Populate actual_duration_ms Earlier

**Problem:** Need to trace back to where `SequenceVideoResult` is created and ensure `actual_duration_ms` is populated.

**Investigation needed:**
- Find video result creation code
- Add: `result.actual_duration_ms = (video_end_time - video_start_time) * 1000`

---

## Recommended Fix

**Use Option 1** - it's the simplest and uses already-correct database values.

```python
# File: services/ground_truth_matching_service.py
# Line: 1048-1051

# REPLACE:
video_start = result.video_start_time
duration_s = result.actual_duration_ms / 1000.0 if result.actual_duration_ms else 0
video_end = video_start + duration_s if video_start else None

# WITH:
video_start = result.video_start_time
video_end = result.video_end_time  # Use authoritative end time from DB
duration_s = (video_end - video_start) if (video_end and video_start) else 0
```

**Expected Result:**
```
📹 Video 1: 1763988511.882s - 1763988516.923s (duration: 5.04s) ✅
📹 Video 2: 1763988516.924s - 1763988521.965s (duration: 5.04s) ✅
✅ Matches found: 8 TP, 0 FP, 0 FN
```

---

## Testing Results

### ✅ Phase 1: Duration Fix - SUCCESSFUL

```
Video Timing Map (after fix):
  Video 1: 1763988511.882s - 1763988516.923s (duration: 5.04s) ✅
  Video 2: 1763988516.924s - 1763988521.965s (duration: 5.04s) ✅
```

**Result:** Video durations now correct! No longer showing 0.00s.

---

### ❌ Phase 2: Matching - STILL FAILING

**New Problem Found: Timestamp Coordinate Mismatch**

```
Detection Timestamps (absolute Unix time):
  1763988511.976s, 1763988512.118s, 1763988512.229s, ...

Ground Truth Timestamps (video-relative):
  0.000s, 0.042s, 0.083s, 0.125s, ...
```

**Root Cause:** Detections use absolute Unix timestamps, but Ground Truth uses video-relative timestamps (seconds from start of video).

**Why Matching Fails:**
- Detection at `1763988511.976s` is compared to GT at `0.000s`
- Difference: `1763988511.976 seconds` (HUGE!)
- This is way outside tolerance (100ms = 0.1s)
- Result: No matches possible

---

## Testing Plan (Updated)

1. ✅ **Phase 1:** Apply duration fix to `ground_truth_matching_service.py`
2. ✅ **Verify logs** show correct video durations (~5.04s)
3. ❌ **Phase 2:** Fix timestamp coordinate system mismatch
4. **Re-run matching** for session `daad8bf6-b5da-4423-abc4-a85e83bc1c16`
5. **Verify results** show True Positives (not all False Positives)
6. **Check database** that `DetectionEvent` records have correct `validation_result = 'Pass'`

---

## Related Issues

- **Bug #5 Fix**: This code was part of the multi-video timing fix
- **Root Issue**: Assumed `actual_duration_ms` would be populated
- **Reality**: `video_end_time` is the authoritative source, not `actual_duration_ms`

---

---

## Secondary Bug: Timestamp Coordinate System Mismatch

After fixing the duration bug, matching still fails due to coordinate system mismatch.

### Problem

**Detections** use absolute Unix timestamps:
```python
DetectionEvent.timestamp = 1763988511.976  # Absolute Unix time
```

**Ground Truth** uses video-relative timestamps:
```python
GroundTruthObject.timestamp = 0.000  # Seconds from video start
```

### Investigation Needed

The code has functions to convert between coordinate systems:
- `extract_ground_truth_video_time()` - Should convert GT to absolute time
- `extract_detection_video_time()` - Should convert detection to absolute time

**Check if these functions are working correctly:**

1. Are they being called?
2. Are they using the video timing map correctly?
3. Is the video timing map being passed to them?

### Files to Investigate

1. `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py`
   - Line 1092: `extract_ground_truth_video_time()` call
   - Line 1097: `extract_detection_video_time()` call
   - These functions should convert to same coordinate system

---

## Files Modified

1. ✅ `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py` (Line 1048-1053)
   - Fixed: Now uses `video_end_time` instead of calculating from `actual_duration_ms`
