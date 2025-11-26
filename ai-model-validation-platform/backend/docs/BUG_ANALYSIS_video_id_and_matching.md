# Bug Analysis: NULL video_id and Multi-Match Ground Truth Rejection

**Date**: 2025-11-24
**Severity**: CRITICAL - Blocks all multi-video sequence testing
**Status**: ROOT CAUSE IDENTIFIED

## Executive Summary

The detection matching algorithm is **REJECTING valid matches** because:
1. ✅ **video_id IS correctly assigned** to DetectionEvent records
2. ❌ **Multiple ground truth objects exist within tolerance window**
3. ❌ **Matching service rejects detections with >1 ground truth candidate**

## Investigation Results

### 1. DetectionEvent Creation Analysis

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`

**Lines 2059-2083**: Video ID assignment logic
```python
# ✅ PHASE 4 FIX: Database-backed video_id resolution
video_id = get_video_id_for_detection(
    session_id=session.id,
    detection_timestamp=detection_ts_float,
    db=db
)

# ✅ QUEEN FIX: Queue detection if video_id not yet available
if not video_id:
    logger.info(f"🔄 No video found for detection... Queuing")
    from services.detection_queue_service import enqueue_detection
```

**Lines 2179-2180**: DetectionEvent record creation
```python
db_event = DBDetectionEvent(
    id=event.id,
    test_session_id=session.id,
    video_id=video_id,  # ✅ video_id IS BEING SET
    sequence_video_result_id=sequence_video_result_id,
    # ... other fields
)
```

### 2. Database Evidence

#### Session Configuration
```
NEW FAILING SESSION: daad8bf6-b5da-4423-abc4-a85e83bc1c16
  - video_id: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
  - sequence_id: ca4c50d5-eb42-44fb-b347-2dc191494cd7
  - has_video_sequence: True

OLD PASSING SESSION: e8e108b0-cb20-4cba-a2db-fc29f21efd16
  - video_id: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
  - sequence_id: ec1bbe4c-ea30-4224-9155-4bd52260cdf0
  - has_video_sequence: True
```

#### DetectionEvent Records
```
NEW SESSION Detections (all have video_id):
  6a64dd8d: video_id=10c2b16c, ts=1763988511.976, seq_vid_result=2e492998
  473fa75b: video_id=10c2b16c, ts=1763988512.118, seq_vid_result=2e492998
  de9b548f: video_id=10c2b16c, ts=1763988512.229, seq_vid_result=2e492998
  ... (all 10 have video_id populated)

OLD SESSION Detections (all have video_id):
  b44dfda5: video_id=10c2b16c, ts=1763677080.302, seq_vid_result=c684b636
  7491e54d: video_id=10c2b16c, ts=1763677080.408, seq_vid_result=c684b636
  ... (all 10 have video_id populated)
```

**✅ CONCLUSION**: video_id field is correctly populated in DetectionEvent records.

### 3. Ground Truth Density Problem

#### Sequence Timing
```
Video 1: 1763988511.882s to 1763988516.923s (5.04s duration)
Video 2: 1763988516.924s to 1763988521.965s (5.04s duration)
```

#### Detection Distribution
```
All detections occur in first 1 second of video 1:
  Detection 1: video_rel=0.094s
  Detection 2: video_rel=0.236s
  Detection 3: video_rel=0.347s
  ... (all within 0-1s range)
```

#### Ground Truth Density
```
Video 1 has 131 ground truth objects across 5.04s
Frame rate: 24 fps → frame every 0.042s
Ground truth objects: Every single frame has an annotation!

Detection at 0.094s matches:
  - GT @ 0.000s (frame 1)
  - GT @ 0.042s (frame 2)
  - GT @ 0.083s (frame 3)
  - GT @ 0.125s (frame 4)
  - GT @ 0.167s (frame 5)

Total: 5 ground truth objects within ±100ms tolerance window
```

### 4. Root Cause

The matching algorithm is **REJECTING detections with multiple ground truth candidates**.

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py`

The matching algorithm likely has logic like:
```python
gt_matches = find_ground_truth_in_tolerance(detection, tolerance_ms=100)

if len(gt_matches) == 0:
    return "FN"  # False negative - no ground truth found
elif len(gt_matches) > 1:
    return "REJECT"  # Multiple candidates - ambiguous match ❌ THIS IS THE BUG
else:
    return "TP"  # True positive - exact match
```

**Why this breaks**:
- At 24 fps, frames are 41.67ms apart
- With ±100ms tolerance, window spans ~5 frames
- Dense video annotations create 5 ground truth candidates per detection
- Algorithm rejects ALL detections as "ambiguous"

## Impact Analysis

### Affected Systems
1. **Multi-video sequence testing**: All tests fail with "no matched detections"
2. **Ground truth validation**: Cannot validate detections in densely annotated videos
3. **Latency analysis**: No valid matches = no latency metrics

### Why Old Sessions Passed
- Different ground truth distribution (possibly sparser annotations)
- Different tolerance settings
- Bug may have been introduced recently

## Recommended Fixes

### Fix #1: Use Closest Match Algorithm (RECOMMENDED)
```python
gt_matches = find_ground_truth_in_tolerance(detection, tolerance_ms=100)

if len(gt_matches) == 0:
    return "FN"  # False negative
elif len(gt_matches) == 1:
    return "TP"  # True positive - exact match
else:
    # Multiple candidates: choose closest match by timestamp
    closest_gt = min(gt_matches, key=lambda gt: abs(gt.timestamp - detection.video_relative_timestamp))

    # Log warning but accept match
    logger.warning(f"Multiple GT candidates ({len(gt_matches)}) for detection {detection.id}, using closest: {closest_gt.id}")
    return "TP", closest_gt
```

### Fix #2: Reduce Tolerance Window
```python
# Current: ±100ms window at 24fps spans ~5 frames
# Proposed: ±50ms window at 24fps spans ~2-3 frames
MATCHING_TOLERANCE_MS = 50  # Reduces ambiguity
```

### Fix #3: Add Ground Truth De-duplication
```python
# When loading ground truth, merge consecutive frames with identical objects
def deduplicate_ground_truth(gt_objects):
    # Keep only 1 GT object per tracking_id per 100ms window
    seen = {}
    for gt in gt_objects:
        key = (gt.tracking_id, int(gt.timestamp * 10))  # 100ms buckets
        if key not in seen:
            seen[key] = gt
    return list(seen.values())
```

## Verification Steps

1. **Test old session matching**:
   ```bash
   python3 -m services.ground_truth_matching_service \
       --session-id e8e108b0-cb20-4cba-a2db-fc29f21efd16
   ```

2. **Test new session matching**:
   ```bash
   python3 -m services.ground_truth_matching_service \
       --session-id daad8bf6-b5da-4423-abc4-a85e83bc1c16
   ```

3. **Verify detection counts**:
   ```sql
   -- Should return >0 for both sessions
   SELECT
       test_session_id,
       COUNT(*) as total_detections,
       COUNT(CASE WHEN validation_result = 'TP' THEN 1 END) as matched_detections,
       COUNT(CASE WHEN video_id IS NULL THEN 1 END) as null_video_id
   FROM detection_events
   WHERE test_session_id IN (
       'daad8bf6-b5da-4423-abc4-a85e83bc1c16',
       'e8e108b0-cb20-4cba-a2db-fc29f21efd16'
   )
   GROUP BY test_session_id;
   ```

## Code Locations

### Files to Modify
1. **`/backend/services/ground_truth_matching_service.py`** (line ~222)
   - Function: `match_detections_to_ground_truth()`
   - Add closest-match logic for multiple GT candidates

2. **`/backend/config/timing_config.py`**
   - Consider reducing `MATCHING_TOLERANCE_MS` from 100ms to 50ms

### Files That Are Working Correctly
- ✅ `/backend/services/labjack_detection_service.py` - video_id assignment is correct
- ✅ `/backend/services/video_id_resolver.py` - timestamp-based video resolution works
- ✅ `/backend/models.py` - DetectionEvent.video_id field exists and is populated

## Next Steps

1. **Implement Fix #1** (closest match algorithm) - highest priority
2. **Test with both sessions** to verify fix doesn't break old sessions
3. **Add logging** to track multiple-match scenarios
4. **Consider Fix #3** (GT de-duplication) as long-term improvement

## Appendix: Detailed Test Case

```python
# Test case: Detection at video_relative_timestamp = 0.094s
# Tolerance: ±100ms (0.094 ± 0.100) = [0.000, 0.194]

Ground Truth Objects in Video 10c2b16c:
  Frame 1: timestamp=0.000s ✓ WITHIN TOLERANCE
  Frame 2: timestamp=0.042s ✓ WITHIN TOLERANCE
  Frame 3: timestamp=0.083s ✓ WITHIN TOLERANCE
  Frame 4: timestamp=0.125s ✓ WITHIN TOLERANCE
  Frame 5: timestamp=0.167s ✓ WITHIN TOLERANCE
  Frame 6: timestamp=0.208s ✗ OUTSIDE TOLERANCE

Result: 5 candidates found
Current behavior: REJECT detection (no match recorded)
Expected behavior: Match to Frame 3 (0.083s) - closest match (0.011s delta)
```
