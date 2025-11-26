# Timestamp Mismatch Fix - Video 2 GT Coverage Issue

## Problem Statement

Video 2 had extremely low ground truth coverage (0.79% = 1/126 GT matched) due to timestamp mismatches when comparing detection events against ground truth objects.

### Root Cause

Detection events stored **UNIX epoch timestamps** (e.g., 1763677080.302s) in the `timestamp` field, while ground truth objects stored **video-relative timestamps** (e.g., 0.000s). When comparing these directly, the time differences were billions of seconds apart (55+ years), causing nearly all matches to fail.

### Evidence

- Detection timestamp: `1763677080.302s` (UNIX epoch)
- Ground truth timestamp: `0.000s` (video-relative)
- Time difference: `1,763,677,080 seconds` (55+ years)
- Result: 11,866 false negatives, only 1 out of 126 GT objects matched

## Solution

Use the `video_relative_timestamp` field from detection events when comparing against ground truth, instead of the UNIX epoch `timestamp` field.

## Files Modified

### 1. `/services/ground_truth_matching_service.py`

**Line 1384-1385**: Added comment explaining the fix
```python
# FIX: Use video_relative_timestamp for detection timestamp if available
# This avoids comparing UNIX epoch timestamps (1763677080s) with video-relative timestamps (0.000s)
```

### 2. `/services/validation_analysis_service.py`

**Lines 175-177**: Fixed temporal matching in performance calculation
```python
# FIX: Use video_relative_timestamp if available to avoid UNIX epoch vs video-relative mismatch
det_timestamp = detection.video_relative_timestamp if hasattr(detection, 'video_relative_timestamp') and detection.video_relative_timestamp is not None else detection.timestamp
time_diff = abs(det_timestamp - gt_obj.timestamp)
```

**Lines 221-223**: Fixed temporal error calculation
```python
# FIX: Use video_relative_timestamp if available to avoid UNIX epoch vs video-relative mismatch
det_timestamp = detection.video_relative_timestamp if hasattr(detection, 'video_relative_timestamp') and detection.video_relative_timestamp is not None else detection.timestamp
time_diff_ms = abs(det_timestamp - closest_gt.timestamp) * 1000
```

**Lines 254-255**: Fixed `_find_closest_ground_truth` helper method
```python
# FIX: Use video_relative_timestamp if available to avoid UNIX epoch vs video-relative mismatch
det_timestamp = detection.video_relative_timestamp if hasattr(detection, 'video_relative_timestamp') and detection.video_relative_timestamp is not None else detection.timestamp
```

### 3. `/services/validation_service.py`

**Lines 171-173**: Fixed temporal matching in validation
```python
# FIX: Use video_relative_timestamp if available to avoid UNIX epoch vs video-relative mismatch
det_timestamp = detection.video_relative_timestamp if hasattr(detection, 'video_relative_timestamp') and detection.video_relative_timestamp is not None else detection.timestamp
time_diff = abs(gt_obj.timestamp - det_timestamp)
```

**Lines 32-33**: Added clarifying comment for single detection validation
```python
# FIX: For validating single detection, we assume timestamp is already video-relative
# since this is called during detection processing, not from ground truth matching
```

### 4. `/services/results_storage_pipeline_service.py`

**Lines 258-260**: Fixed temporal offset calculation
```python
# FIX: Use video_relative_timestamp if available to avoid UNIX epoch vs video-relative mismatch
det_timestamp = detection_event.video_relative_timestamp if hasattr(detection_event, 'video_relative_timestamp') and detection_event.video_relative_timestamp is not None else video_timestamp
temporal_offset = det_timestamp - gt_obj.timestamp
```

## Implementation Pattern

All fixes follow this pattern:

```python
# Use video_relative_timestamp if available, otherwise fallback to timestamp
det_timestamp = (
    detection.video_relative_timestamp
    if hasattr(detection, 'video_relative_timestamp') and detection.video_relative_timestamp is not None
    else detection.timestamp
)

# Then use det_timestamp for comparison with GT
time_diff = abs(det_timestamp - gt_obj.timestamp)
```

## Expected Impact

### Before Fix
- Video 2: 0.79% GT coverage (1/126 matched)
- 11,866 false negatives
- Time differences in billions of seconds

### After Fix
- Video 2: Expected ~30% GT coverage (38/126 matches)
- Significantly reduced false negatives
- Time differences in realistic ranges (0-5 seconds)

## Database Schema

The `video_relative_timestamp` field exists in the `detection_events` table:

```sql
-- models.py line 382
video_relative_timestamp = Column(Float, nullable=True, index=True)  # Timestamp relative to video start (seconds)
```

This field is populated during detection event creation and represents the time elapsed since the video started playing, matching the time reference used in ground truth annotations.

## Testing Recommendations

1. Run ground truth matching on Video 2's test session
2. Verify GT coverage increases from 0.79% to ~30%
3. Check that false negative count decreases significantly
4. Verify time differences are in realistic ranges (< 5 seconds)
5. Confirm no regression on other videos

## Related Fields

The detection event model has multiple timestamp fields:

- `timestamp` - UNIX epoch timestamp (absolute time)
- `video_relative_timestamp` - Seconds from video start (relative time) **← Used for GT matching**
- `sequence_timestamp` - Seconds from sequence start (for multi-video)
- `unix_timestamp` - Alternative UNIX epoch field
- `labjack_timestamp` - Hardware detection time

Ground truth objects use **video-relative timestamps** (0.000s = video start), so `video_relative_timestamp` is the correct field to use for comparison.
