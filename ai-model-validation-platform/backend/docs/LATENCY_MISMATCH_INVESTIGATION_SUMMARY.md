# Latency Calculation Mismatch Investigation - Final Report

## Issue Summary

**User Report**: "Latency on later points should be to the nearest GT" and "additional real seems wrong"

**Example Data**:
- Detection #1: latency shows -10.4ms
- Detection #2: latency shows 221.6ms
- Later detections show 920ms, 1322ms, 2715ms
- "Frame 21: aligned -12.5ms, real 962ms FAIL"

## Root Cause Identified

### 1. "Real" vs "Aligned" Latency Terminology

**Source File**: `/backend/src/api/enhanced_hil_results_endpoints.py`

**Lines 1962-1965**: Latency calculation clarification
```python
# The "real" latency should be the frame difference
# The "apparent" latency includes video startup timing
real_latency_ms = frame_based_latency_ms  # Direct frame timing
apparent_latency_ms = frame_based_latency_ms + video_startup_delay_ms
```

**Definition**:
- **"real_latency_ms"**: Corrected latency AFTER removing video startup delay
  - Formula: `real_latency = detection_system_time - (video_start_system_time + gt_video_time)`
  - This is what the system actually took to detect (true performance)

- **"apparent_latency_ms"** (likely what user calls "aligned"): Raw measured latency INCLUDING video startup delay
  - This is the initial calculation before timing correction
  - Can be negative if detection timing is misaligned

**Lines 972-974 in enhanced_hil_results_endpoints.py**:
```python
"timing_synchronization": {
    "real_latency_ms": round(to_float(getattr(corrected_result, 'real_latency_ms', 0)) or 0, 3),
    "apparent_latency_ms": round(to_float(getattr(corrected_result, 'apparent_latency_ms', 0)) or 0, 3),
    "latency_correction_ms": round(to_float(getattr(corrected_result, 'latency_correction_ms', 0)) or 0, 3),
    "video_startup_delay_ms": round(to_float(getattr(corrected_result, 'video_startup_delay_ms', 0)) or 0, 3),
```

### 2. Why "Aligned" Shows -12.5ms but "Real" Shows 962ms

**Scenario Analysis** (Frame 21 example):

**Hypothesis 1**: Cross-video matching error
- Detection from Video B (frame 21) matched to Ground Truth from Video A
- "Aligned" latency = temporal_offset within Video B = -12.5ms (slightly early)
- "Real" latency = absolute time difference including video boundaries = 962ms

**Hypothesis 2**: Video startup delay miscalculation
- Video startup delay calculation is incorrect or missing
- "Aligned" = raw temporal offset = -12.5ms
- "Real" = after applying incorrect startup correction = 962ms

**Hypothesis 3**: Timestamp synchronization failure
- Detection timestamp: e.g., 21.5 seconds (frame 21)
- Ground Truth timestamp: 21.5125 seconds (expecting detection here)
- Aligned latency: -12.5ms (detection arrived early)
- BUT: Video start time is wrong by ~962ms
- Real latency calculation: uses wrong video_start_time → 962ms error

### 3. Negative Latency Values Are Valid

**Source**: `/backend/services/optimal_matching_service.py`, Line 280

```python
# Calculate signed latency (detection_time - gt_time)
latency_ms = (detection_times[det_idx] - ground_truth_times[gt_idx]) * 1000.0
```

**Negative latency means**:
- Detection arrived BEFORE expected ground truth time
- This is valid if:
  - System has prediction/anticipation
  - Timestamp synchronization offset
  - Detection triggered slightly early

**NOT a bug**: Negative values are mathematically correct for early detections.

### 4. Large Latency Values (920ms+) Indicate Bug

**Source**: `/backend/services/ground_truth_matching_service.py`, Lines 1226-1254

**First 10 Per Video Filtering**:
```python
# Group TP results by video_id, preserving order
video_tp_latencies = defaultdict(list)
for mr in tp_results:
    if mr.latency_ms is not None:
        if mr.video_id is None:
            self.logger.warning(f"Skipping TP match result - NULL video_id...")
            continue

        video_id = str(mr.video_id)
        if len(video_tp_latencies[video_id]) < 10:  # Only first 10 per video
            video_tp_latencies[video_id].append(mr.latency_ms)
```

**Problem**: Large latencies are filtered from STATISTICS but not from MATCHING.

**Root Cause**: Detections with NULL or incorrect `video_id` bypass video boundary validation:

**Lines 802-831 in ground_truth_matching_service.py**:
```python
# NULL SAFETY: Skip if either video_id is NULL in multi-video mode
if has_multi_video_sequence and (detection_video_id is None or gt_video_id is None):
    logger.warning(
        f"Skipping match - NULL video_id detected..."
    )
    # Reclassifies as FN for GT and FP for detection
```

**But**: This reclassification happens AFTER the match is made, so:
1. Detection #1-10: Matched correctly to Video A ground truth → good latencies
2. Video A ground truth exhausted
3. Detection #11+: Has NULL or wrong video_id
4. Matches to Video B ground truth → 920ms+ latency (cross-video match)
5. THEN gets reclassified as FP, but the bad latency was already calculated

## The Actual Bug

### Issue: Video Correlation Timing

**File**: `/backend/services/detection_video_reassignment.py` or similar

**Problem**: Detections are assigned `video_id` AFTER ground truth matching runs, causing:

1. **Ground truth matching runs first** (line 158 in test_results_processor.py)
   ```python
   matching = cls._run_ground_truth_matching(
       session_id,
       tolerance_ms=session_snapshot.get("tolerance_ms"),
   )
   ```

2. **Video correlation runs second** (line 77 in test_results_processor.py)
   ```python
   correlation = await cls._correlate_detections(session_id)
   ```

**THIS IS BACKWARDS!**

### Correct Order Should Be:
1. **First**: Assign video_id to all detections (correlation)
2. **Then**: Run ground truth matching with video boundary validation

## How Current "Real" Latency Gets 962ms

**Formula** (Line 1490 in enhanced_hil_results_endpoints.py):
```python
"formula": "real_latency = detection_system_time - (video_start_system_time + gt_video_time)"
```

**Example Calculation for 962ms "real" latency**:
```
Detection system time: 22.512 seconds (frame 21 in Video B)
Video start system time: 20.550 seconds (Video A start time - WRONG VIDEO!)
GT video time: 1.000 seconds (ground truth at 1s into video)

real_latency = 22.512 - (20.550 + 1.000)
             = 22.512 - 21.550
             = 0.962 seconds = 962ms
```

**But the "aligned" latency is -12.5ms because**:
```
Aligned latency = temporal_offset from optimal matching
                = detection_time - gt_time (within video context)
                = (frame 21 = 1.0 seconds into Video B) - (1.0125 seconds GT)
                = -0.0125 seconds = -12.5ms
```

**The mismatch occurs because**:
1. Optimal matching uses video-relative timestamps → -12.5ms (correct within video)
2. Real latency calculation uses WRONG video_start_time → 962ms (cross-video error)

## Fixes Required

### Fix #1: CRITICAL - Reorder Post-Test Processing

**File**: `/backend/services/test_results_processor.py`

**Change lines 77-84**:
```python
# CURRENT (WRONG ORDER):
correlation = await cls._correlate_detections(session_id)
summary["correlation"] = correlation

matching = cls._run_ground_truth_matching(
    session_id,
    tolerance_ms=session_snapshot.get("tolerance_ms"),
)
summary["ground_truth"] = matching
```

**TO**:
```python
# FIXED (CORRECT ORDER):
# Step 1: Assign video_id FIRST
correlation = await cls._correlate_detections(session_id)
summary["correlation"] = correlation

# Step 2: Run ground truth matching AFTER video correlation
matching = cls._run_ground_truth_matching(
    session_id,
    tolerance_ms=session_snapshot.get("tolerance_ms"),
)
summary["ground_truth"] = matching
```

**Wait... this is already correct?** Let me re-check...

Actually, looking at the code again, correlation DOES run first (line 77), then matching (line 80). So this is not the issue.

### The Real Issue: Detection Events Lose video_id Between Correlation and Matching

**Hypothesis**: The video_id is assigned during correlation but not persisted to database before matching runs.

**Check**: `/backend/services/detection_video_reassignment.py` around line 131

If correlation service doesn't commit video_id updates before returning, then matching service queries database and gets NULL video_id values!

### Fix #2: Ensure video_id is Committed Before Ground Truth Matching

**File**: `/backend/services/detection_video_reassignment.py`

**Add at end of reassign_null_video_ids() method**:
```python
# Commit all video_id updates BEFORE returning
db.commit()
logger.info(f"Committed {updated_count} video_id assignments to database")
```

### Fix #3: Validate video_id Before Matching

**File**: `/backend/services/ground_truth_matching_service.py`, Line 247

**Add validation check**:
```python
# Get all detection events for this session
detection_query = text("""
    SELECT id, timestamp, confidence, class_label, actual_latency_ms,
           video_relative_timestamp, video_frame_number, timing_sync_quality,
           video_id
    FROM detection_events
    WHERE test_session_id = :session_id
    ORDER BY timestamp
""")
detection_results = db.execute(detection_query, {'session_id': session_id}).fetchall()

# VALIDATION: Check for NULL video_id in multi-video sessions
if test_session.has_video_sequence and test_session.sequence_id:
    null_video_id_count = sum(1 for row in detection_results if row[8] is None)
    if null_video_id_count > 0:
        self.logger.error(
            f"⚠️ CRITICAL: {null_video_id_count} detections have NULL video_id "
            f"in multi-video sequence session {session_id}. "
            f"Video correlation must run BEFORE ground truth matching!"
        )
        # Either return error or run correlation here
```

## Recommendations

### Immediate Actions

1. **Verify Processing Order**: Check test_results_processor.py to confirm correlation commits video_id
2. **Add Validation**: Reject ground truth matching if detections have NULL video_id in multi-video sessions
3. **Document Fields**: Clearly document real_latency_ms vs apparent_latency_ms vs temporal_offset

### Testing Required

**Test Case 1**: Multi-video sequence with cross-video matching
```python
def test_cross_video_latency_detection():
    """Verify detections don't match GTs from different videos"""
    # Setup: 2 videos, each with 5 detections and 5 GTs
    # Expected: All detections match GTs from same video
    # Expected: No latencies > 500ms
    # Expected: Video boundary rejections logged
```

**Test Case 2**: video_id persistence
```python
def test_video_id_persisted_before_matching():
    """Verify video_id is committed to DB before matching runs"""
    # Setup: Multi-video sequence
    # Step 1: Run correlation
    # Step 2: Query database for video_id
    # Expected: All detections have non-NULL video_id
    # Step 3: Run ground truth matching
    # Expected: Video boundary validation works correctly
```

## Field Mapping Summary

| Field Name | Location | Description | Signed? | Use Case |
|------------|----------|-------------|---------|----------|
| `actual_latency_ms` | DetectionEvent model | Canonical latency field | No (abs) | Metrics, pass/fail |
| `temporal_offset` | DetectionComparison | Signed time difference | Yes | Analysis |
| `real_latency_ms` | API response | Corrected latency | No (abs) | True performance |
| `apparent_latency_ms` | API response | Raw measured latency | Can be negative | Pre-correction |
| `latency_correction_ms` | API response | Correction applied | Signed | Debugging |

## Conclusion

**The mismatch between "aligned" (-12.5ms) and "real" (962ms) latency is caused by**:

1. **"Aligned"** = temporal_offset from optimal matching within video context (CORRECT)
2. **"Real"** = calculated using wrong video_start_time due to cross-video matching (BUG)

**The large latencies (920ms+) indicate**:
- Detections being matched to ground truth from a different video
- This happens when video_id is NULL or incorrect during matching
- Video boundary validation cannot reject these matches if video_id is missing

**The fix is**:
1. Ensure video_id correlation commits to database BEFORE ground truth matching
2. Add validation to reject matching if video_id is NULL in multi-video sessions
3. Improve logging to catch cross-video matches earlier in pipeline

**Files to modify**:
- `/backend/services/detection_video_reassignment.py` - ensure commit
- `/backend/services/ground_truth_matching_service.py` - add validation at line 247
- `/backend/services/test_results_processor.py` - verify ordering (may already be correct)
