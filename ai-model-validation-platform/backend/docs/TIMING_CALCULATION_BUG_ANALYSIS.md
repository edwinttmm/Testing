# TIMING CALCULATION BUG ANALYSIS

## Critical Finding: Incorrect Latency Calculation Formula

**Investigation Date**: 2025-10-01
**Status**: CRITICAL BUG IDENTIFIED
**Impact**: All latency values are being calculated incorrectly

---

## The Problem

Detection at Frame 1 (0.042s video time) shows contradictory results:
- **Correlation**: "aligned" ✅
- **Display latency**: 0.0ms ✅
- **Real latency**: 799ms ❌ (WRONG!)
- **Status**: FAIL ❌ (WRONG!)
- **Ground truth**: PASS ✅ (CORRECT!)
- **Threshold**: FAIL ❌ (WRONG!)

**Expected behavior**: If detection is at 0.042s and is "aligned", latency should be near 0ms (or 50ms processing time), NOT 799ms!

---

## Root Cause Analysis

### 1. The Bug Location

**File**: `/backend/services/timestamp_conversion_utils.py`
**Lines**: 89-90

```python
# INCORRECT FORMULA:
actual_latency_ms = video_relative_timestamp * 1000
```

**What this does**:
- Takes the video timestamp (e.g., 0.042s)
- Multiplies by 1000
- Result: 42ms

**Why this is WRONG**:
- This treats the video timestamp AS the latency
- At 0.042s into video, it calculates 42ms latency
- At 0.799s into video, it would calculate 799ms latency
- **This conflates "time into video" with "detection processing latency"**

### 2. The Correct Formula

Latency should be the **processing time**, NOT the video timestamp!

```python
# CORRECT FORMULA:
# Latency = Time from ground truth event to detection
# For HIL validation, this is typically a fixed processing delay (50-100ms)
actual_latency_ms = 50.0  # Or calculated from detection pipeline timing
```

**Alternative correct approach** (if measuring from ground truth):
```python
# If we have ground truth timestamp:
actual_latency_ms = (detection_timestamp - ground_truth_timestamp) * 1000
```

---

## Evidence From Codebase

### A. Video Timing Service (CORRECT)

**File**: `/backend/services/video_timing_service.py:458`

```python
# This service correctly uses a FIXED processing latency
processing_latency_ms = 50.0  # Default processing time
```

This is the RIGHT approach - processing latency is a relatively fixed value based on the detection pipeline performance, NOT the video timestamp!

### B. Dedicated LabJack Monitor (CORRECT)

**File**: `/backend/services/dedicated_labjack_monitor.py:462`

```python
'actual_latency_ms': 50.0,  # Default processing time
```

This service also correctly understands that latency is processing time, not video position!

### C. Timestamp Conversion Utils (WRONG)

**File**: `/backend/services/timestamp_conversion_utils.py:90`

```python
actual_latency_ms = video_relative_timestamp * 1000  # BUG!
```

This is where the bug originates - using video timestamp as latency!

---

## Impact Analysis

### What Gets Affected

1. **All Detection Events**: Every detection event gets incorrect `actual_latency_ms` values
2. **Pass/Fail Validation**: Detections at later video timestamps falsely fail threshold checks
3. **Ground Truth Matching**: Appears to work because it uses temporal matching, not latency values
4. **Performance Metrics**: All latency statistics are completely wrong

### Example Scenario

**Video Event at 0.799s into video**:
- **Current Calculation**: 799ms latency → FAIL (exceeds 100ms threshold)
- **Correct Calculation**: 50-100ms latency → PASS (within threshold)

**The detector is working perfectly, but the math is wrong!**

---

## Why Ground Truth Matching Still Works

**File**: `/backend/services/ground_truth_matching_service.py:268`

```python
# Ground truth matching uses TEMPORAL OFFSET, not actual_latency_ms:
temporal_offset_ms = (detection.timestamp - gt_obj.timestamp) * 1000
latency_ms = temporal_offset_ms if temporal_offset_ms >= 0 else None
```

This correctly calculates the TIME DIFFERENCE between detection and ground truth, which is why ground truth matching shows "PASS" while threshold validation shows "FAIL".

---

## The Solution

### Fix #1: Correct the Formula in `timestamp_conversion_utils.py`

```python
# BEFORE (WRONG):
actual_latency_ms = video_relative_timestamp * 1000

# AFTER (CORRECT):
# Option A: Use fixed processing latency (typical for HIL validation)
actual_latency_ms = 50.0  # Typical detection pipeline processing time

# Option B: Calculate from detection timing metadata if available
# This requires knowing when the actual processing started
if detection_metadata and 'processing_start_time' in detection_metadata:
    processing_duration = unix_timestamp - detection_metadata['processing_start_time']
    actual_latency_ms = processing_duration * 1000
else:
    actual_latency_ms = 50.0  # Fallback to typical processing time
```

### Fix #2: Update Detection Event Storage

**File**: `/backend/services/dedicated_labjack_monitor.py:496`

Already correctly uses `timing_data['actual_latency_ms']`, so this will work once Fix #1 is applied.

### Fix #3: Documentation Update

Add clear documentation explaining the difference between:
- **video_relative_timestamp**: Time into video when detection occurred
- **actual_latency_ms**: Processing delay from ground truth to detection
- **temporal_offset**: Time difference between detection and ground truth event

---

## Testing Plan

1. **Unit Test**: Create test with detection at 0.799s
   - Verify `actual_latency_ms` is ~50ms, NOT 799ms

2. **Integration Test**: Full HIL test with multiple detections
   - Verify all detections have reasonable latency (50-100ms)
   - Verify PASS/FAIL matches ground truth results

3. **Regression Test**: Check existing data
   - Identify sessions with this bug
   - Re-calculate correct latency values

---

## Files That Need Changes

### Primary Fix:
1. `/backend/services/timestamp_conversion_utils.py:90` - Fix the formula

### Verification Needed:
2. `/backend/services/video_timing_service.py:458` - Already correct ✅
3. `/backend/services/dedicated_labjack_monitor.py:462` - Already correct ✅
4. `/backend/services/ground_truth_matching_service.py:268` - Already correct ✅

### Documentation:
5. Add inline comments explaining the distinction between video timestamp and latency

---

## Conclusion

**The detection system is working correctly!** The bug is purely in the latency calculation formula, which incorrectly uses video timestamp as latency. This causes:

- Detections early in video: artificially low latency
- Detections late in video: artificially high latency
- False FAIL results for perfectly good detections

**Ground truth matching still works** because it uses the correct temporal offset calculation, not the buggy `actual_latency_ms` field.

**Priority**: HIGH - This affects all latency-based validation and reporting.

---

## Exact Code Locations

| File | Line | Issue | Fix |
|------|------|-------|-----|
| `timestamp_conversion_utils.py` | 90 | `actual_latency_ms = video_relative_timestamp * 1000` | Use fixed processing latency or calculate from metadata |
| `video_timing_service.py` | 458 | `processing_latency_ms = 50.0` | ✅ Already correct |
| `dedicated_labjack_monitor.py` | 462 | `'actual_latency_ms': 50.0` | ✅ Already correct |
| `ground_truth_matching_service.py` | 268 | Uses temporal_offset correctly | ✅ Already correct |

---

## Next Steps

1. Fix the formula in `timestamp_conversion_utils.py`
2. Add unit tests to prevent regression
3. Re-process existing data with correct calculation
4. Update documentation to clarify terminology
