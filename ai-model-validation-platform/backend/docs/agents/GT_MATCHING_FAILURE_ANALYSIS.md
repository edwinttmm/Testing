# Ground Truth Matching Failure Analysis

**Session ID**: 49e5d00f-eea7-44cb-a647-480268ef43ee
**Issue**: 100% GT FAIL rate - All 192 detections show "GT FAIL"
**Date**: 2025-11-20

---

## Executive Summary

**ROOT CAUSE**: Timestamp format mismatch between detections and ground truth objects.

- **Detections**: Use absolute epoch timestamps (~1.76 billion seconds)
- **Ground Truth**: Use relative video timestamps (1-14 seconds from video start)
- **Impact**: No temporal matches possible, causing 100% GT FAIL

---

## Database Analysis Results

### Session Overview
```
Session: Video Sequence Test - 2025-11-20 00:36
Video ID: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
Tolerance: 100ms
Total Detections: 192
Ground Truth Objects: 262
```

### Detection Data
```
Total Detections: 192
Usable for Validation: 192 (100.0%)
Matched to GT: 0 (0.0%)
Unmatched: 192 (100.0%)
```

**Sample Detection Timestamps**:
```
Detection 1: Frame None, Time 1763598993.556s (epoch time)
Detection 2: Frame None, Time 1763598993.556s
Detection 3: Frame None, Time 1763598993.669s
Detection 4: Frame None, Time 1763598993.669s
Detection 5: Frame None, Time 1763598993.730s

Timestamp Range: 1763598993.556s - 1763599007.369s (~14 seconds duration)
```

### Ground Truth Data
```
Total GT Objects: 262
Video ID: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5 ✓ (matches session)
```

**Sample GT Timestamps**:
```
GT 1: Frame 0, Time 1.042s (relative time)
GT 2: Frame 0, Time 1.083s
GT 3: Frame 0, Time 1.125s
GT 4: Frame 0, Time 1.292s
GT 5: Frame 0, Time 1.792s

Timestamp Range: 1.042s - ~14s
```

### Detection Comparisons
```
Total Comparisons Created: 449
  - False Negatives (FN): 257 (GT objects with no detection match)
  - False Positives (FP): 192 (Detections with no GT match)
  - True Positives (TP): 0
```

---

## Root Cause Diagnosis

### The Problem

The matching algorithm compares timestamps within a tolerance window (100ms), but:

1. **Detection timestamps** are in **epoch time** (seconds since 1970-01-01)
   - Example: `1763598993.556` = Wednesday, November 20, 2025 12:36:33 AM

2. **Ground truth timestamps** are in **relative video time** (seconds since video start)
   - Example: `1.042` = 1.042 seconds into the video

3. **Difference**: ~1,763,598,992 seconds (55.9 years!)

### Why This Causes 100% GT FAIL

In `ground_truth_matching_service.py` line 228:
```python
tolerance_ms = tolerance_ms if tolerance_ms is not None else self.default_tolerance_ms
tolerance_seconds = tolerance_ms / 1000.0
```

Then line 256-261 filters detections:
```python
detections_in_window = session.query(DetectionEvent).filter(
    DetectionEvent.test_session_id == test_session_id,
    DetectionEvent.usable_for_validation == True,  # FILTER 1: Quality check
    DetectionEvent.timestamp >= (gt_timestamp - tolerance_seconds),  # FILTER 2: Time window
    DetectionEvent.timestamp <= (gt_timestamp + tolerance_seconds)   # FILTER 3: Time window
).all()
```

**Example calculation**:
- GT timestamp: `1.042s`
- Tolerance: `0.1s` (100ms)
- Window: `0.942s - 1.142s`
- Detection timestamp: `1763598993.556s`
- **Match**: NO (off by 55.9 years)

---

## Why Quality Filter Was Suspected

Initial investigation focused on line 256's `usable_for_validation == TRUE` filter because:
- If ALL detections had `usable_for_validation = FALSE`, they'd be excluded
- This would cause 0% matching

**Database check proved this wrong**:
```
Usable for validation: 192/192 (100.0%)
```

All detections ARE usable, so the quality filter is working correctly.

---

## The Real Issue: Timestamp Normalization

### Where Timestamps Come From

1. **Detections** (`DetectionEvent.timestamp`):
   - Set during detection ingestion
   - Uses system clock or hardware timestamp
   - Format: Absolute epoch time

2. **Ground Truth** (`GroundTruthObject.timestamp`):
   - Extracted from video annotation files
   - Format: Relative to video start (0.0s = first frame)

### Expected Behavior

The matching service SHOULD normalize one timestamp to match the other:
```python
# Option 1: Convert detection to relative time
detection_relative = detection.timestamp - video_start_timestamp

# Option 2: Convert GT to absolute time
gt_absolute = video_start_timestamp + gt.timestamp
```

---

## Proposed Fix

### Option 1: Normalize Detections to Relative Time (RECOMMENDED)

**Location**: `services/ground_truth_matching_service.py`, line ~240

**Current Code**:
```python
detections_in_window = session.query(DetectionEvent).filter(
    DetectionEvent.test_session_id == test_session_id,
    DetectionEvent.usable_for_validation == True,
    DetectionEvent.timestamp >= (gt_timestamp - tolerance_seconds),
    DetectionEvent.timestamp <= (gt_timestamp + tolerance_seconds)
).all()
```

**Fixed Code**:
```python
# Get video start timestamp for normalization
video = session.query(Video).join(TestSession).filter(
    TestSession.id == test_session_id
).first()

if not video:
    logger.error(f"No video found for session {test_session_id}")
    return []

video_start_timestamp = getattr(video, 'start_timestamp', None)

# If video has no start timestamp, use first detection as reference
if video_start_timestamp is None:
    first_detection = session.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == test_session_id
    ).order_by(DetectionEvent.timestamp.asc()).first()

    if first_detection:
        video_start_timestamp = first_detection.timestamp
        logger.warning(f"Using first detection timestamp as video start: {video_start_timestamp}")
    else:
        logger.error("No detections found to establish video start time")
        return []

# Normalize GT timestamp to absolute time OR normalize detection to relative time
# OPTION A: Normalize GT to absolute (add video start)
gt_timestamp_absolute = video_start_timestamp + gt_timestamp

detections_in_window = session.query(DetectionEvent).filter(
    DetectionEvent.test_session_id == test_session_id,
    DetectionEvent.usable_for_validation == True,
    DetectionEvent.timestamp >= (gt_timestamp_absolute - tolerance_seconds),
    DetectionEvent.timestamp <= (gt_timestamp_absolute + tolerance_seconds)
).all()
```

### Option 2: Add `video_relative_timestamp` Field

**Better long-term solution**:

1. Add `video_relative_timestamp` column to `DetectionEvent` (already exists!)
2. Populate it during detection ingestion:
   ```python
   detection.video_relative_timestamp = detection.timestamp - video.start_timestamp
   ```
3. Match using relative timestamps:
   ```python
   detections_in_window = session.query(DetectionEvent).filter(
       DetectionEvent.test_session_id == test_session_id,
       DetectionEvent.usable_for_validation == True,
       DetectionEvent.video_relative_timestamp >= (gt_timestamp - tolerance_seconds),
       DetectionEvent.video_relative_timestamp <= (gt_timestamp + tolerance_seconds)
   ).all()
   ```

---

## Implementation Plan

### Immediate Fix (Option 1)
1. Modify `ground_truth_matching_service.py` to normalize timestamps
2. Add video start timestamp lookup
3. Convert GT timestamps to absolute time before matching
4. Test with session 49e5d00f-eea7-44cb-a647-480268ef43ee

### Long-term Fix (Option 2)
1. Update detection ingestion to populate `video_relative_timestamp`
2. Modify matching service to use relative timestamps
3. Add database migration if needed
4. Update all timestamp handling to use relative time

---

## Testing Plan

### Test Case 1: Verify Fix
```bash
# Re-run matching for session 49e5d00f-eea7-44cb-a647-480268ef43ee
python3 -c "
from services.ground_truth_matching_service import GroundTruthMatchingService
from database import SessionLocal

db = SessionLocal()
service = GroundTruthMatchingService(db)
results = service.match_detections('49e5d00f-eea7-44cb-a647-480268ef43ee')
print(f'TP: {results[\"tp_count\"]}, FP: {results[\"fp_count\"]}, FN: {results[\"fn_count\"]}')
db.close()
"
```

**Expected Results**:
- TP > 0 (should match nearby detections)
- Match rate > 70%
- No "GT FAIL" on obvious matches

### Test Case 2: Normal Session
```bash
# Test with a working session to ensure fix doesn't break existing functionality
```

---

## Success Criteria

- [ ] Session 49e5d00f shows >0 True Positives
- [ ] Match rate >70% for sessions with good quality detections
- [ ] Existing working sessions still function correctly
- [ ] No regression in matching accuracy

---

## Additional Notes

### Why Frame Numbers Are None

Sample detections show `Frame None`, which suggests:
1. Frame extraction may not be working
2. This could be a separate issue from timestamp matching
3. Frame numbers are not critical for temporal matching (timestamps are)

### Detection Duplicates

Multiple detections at identical timestamps:
```
Detection 1: Time 1763598993.556s
Detection 2: Time 1763598993.556s
```

This suggests either:
- Multiple objects detected in same frame
- Duplicate detection events
- Should not affect matching if timestamps are normalized

---

## UPDATED ROOT CAUSE (Final Analysis)

### Initial Hypothesis: WRONG
Initially suspected timestamp format mismatch (epoch vs relative time).

### Database Investigation Revealed:
1. **Timestamps ARE normalized**: Detections have `video_relative_timestamp` populated
   - Detection range: 0.027s - 8.797s
   - GT range: 0.000s - 5.000s
   - **These DO overlap!**

2. **20+ overlaps found manually** within ±100ms tolerance:
   ```
   GT 0.042s -> Det 0.027s (offset: -14.2ms) ✓
   GT 0.083s -> Det 0.140s (offset: +56.4ms) ✓
   GT 0.167s -> Det 0.140s (offset: -27.0ms) ✓
   ```

3. **Matching service DID run**:
   - 449 DetectionComparisons created (192 FP + 257 FN)
   - But ALL have `temporal_offset: 0.0` and `iou_score: 0.0`
   - FPs have `ground_truth_id: NULL`
   - FNs have `detection_event_id: NULL`

### ACTUAL ROOT CAUSE

**The `optimal_detection_matching` algorithm is failing to match despite overlapping timestamps.**

Possible reasons:
1. **Missing scipy dependency**: The optimal matching service imports `scipy.optimize.linear_sum_assignment`
   - Error seen: `ModuleNotFoundError: No module named 'scipy'`
   - If scipy is missing at runtime, matching may silently fail

2. **Algorithm bug**: The Hungarian algorithm may have a bug preventing matches
   - Returns 0 TP despite valid temporal overlaps
   - Need to check `optimal_matching_service.py` implementation

3. **Video ID filtering**: Cross-video match prevention may be too aggressive
   - Line 866 in matching service checks video_id boundaries
   - May be rejecting valid matches

4. **Timestamp extraction returning wrong values**: Despite `video_relative_timestamp` being populated,
   the `extract_detection_video_time()` function may not be using it correctly in production

### The Fix

**IMMEDIATE**: Install scipy dependency
```bash
pip install scipy
```

**VERIFY**: Test optimal matching algorithm with known overlaps
```python
from services.optimal_matching_service import optimal_detection_matching
gt_times = [0.042, 0.083, 0.167]
det_times = [0.027, 0.140, 0.201]
tolerance_seconds = 0.1
result = optimal_detection_matching(gt_times, det_times, tolerance_seconds)
# Should return TP matches, not 0
```

**FALLBACK**: If optimal matching is broken, use simple greedy matching
- Find nearest detection for each GT within tolerance
- Mark as TP if found, FN otherwise
- Mark remaining detections as FP

## Conclusion

The 100% GT FAIL rate is caused by the optimal matching algorithm failing to find matches, despite:
- Timestamps being correctly normalized to video-relative time
- 20+ valid overlaps existing within ±100ms tolerance
- Detection quality being 100% usable

**Root cause**: Either scipy missing or bug in `optimal_matching_service.py`

**Impact**: Installing scipy or fixing the matching algorithm should restore normal matching rates (>70%)

The quality filter (`usable_for_validation`) is working correctly and is NOT the cause.
