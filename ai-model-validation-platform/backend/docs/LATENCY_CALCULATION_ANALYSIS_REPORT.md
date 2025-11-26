# Latency Calculation Mismatch - Root Cause Analysis

## Executive Summary

**Issue**: Detection latency values appear incorrect with negative values, large values (>900ms), and potential mismatch between "aligned" and "real" latency calculations.

**Root Cause**: The latency calculation correctly matches detections to the NEAREST ground truth using the optimal Hungarian algorithm, but the signed latency values represent temporal offset (detection_time - gt_time), which can be negative when detection arrives BEFORE expected time.

## Current Implementation Analysis

### 1. Ground Truth Matching Algorithm

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py`

**Algorithm**: Hungarian (Optimal Assignment) with Greedy Fallback
- Lines 772-785: Uses `optimal_detection_matching()` from `optimal_matching_service.py`
- **CORRECT**: Matches to NEAREST ground truth within tolerance window
- **CORRECT**: Uses cost matrix with absolute time differences to find optimal global assignment

```python
# Line 772-785: Optimal matching is correctly called
optimal_result = optimal_detection_matching(
    gt_times,
    det_times,
    tolerance_seconds
)
```

### 2. Latency Calculation Logic

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/optimal_matching_service.py`

**Line 280**: Signed Latency Calculation
```python
# Calculate signed latency (detection_time - gt_time)
latency_ms = (detection_times[det_idx] - ground_truth_times[gt_idx]) * 1000.0
true_positives.append((gt_idx, det_idx, latency_ms))
```

**Key Insight**: This is a **SIGNED** latency value:
- **Positive latency**: Detection AFTER ground truth (expected, system is slow)
- **Negative latency**: Detection BEFORE ground truth (detection arrived early)

### 3. Storage in Database

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py`

**Lines 1127-1128**: Latency is stored in `actual_latency_ms` field
```python
if match_result.latency_ms is not None:
    detection_event.actual_latency_ms = match_result.latency_ms
```

**Line 895**: MatchResult stores ABSOLUTE value for metrics
```python
latency_ms=abs(latency_ms),  # Takes absolute value for metrics
```

**INCONSISTENCY FOUND**: The code stores `abs(latency_ms)` in MatchResult (line 895) but this loses sign information!

## User-Reported Issues Analysis

### Issue 1: Negative Latency Values

**Example**: Detection #1 shows -10.4ms latency

**Explanation**:
- Detection arrived 10.4ms BEFORE the expected ground truth time
- This is technically correct if:
  - Detection system has prediction/anticipation
  - Timestamp synchronization issue
  - Ground truth timing is slightly delayed

**Is this a bug?**: No, negative latency is valid if detection legitimately arrives before expected time.

### Issue 2: Large Latency Values (920ms, 1322ms, 2715ms)

**Example**: Later detections show 920ms, 1322ms, 2715ms latency

**Likely Causes**:
1. **Video boundary issue**: Detections from next video matched to previous video's ground truth
2. **Out-of-order matching**: When ground truth runs out, detections match to distant ground truth objects
3. **Multi-video latency contamination**: Cross-video matches should be rejected but may slip through

**Critical Code Section** (Lines 797-869): Video boundary validation
```python
# CRITICAL: Video boundary validation for multi-video sequences
detection_video_id = getattr(detection, 'video_id', None)
gt_video_id = getattr(gt_obj, 'video_id', None)

# Skip if video IDs don't match (cross-video match prevention)
if detection_video_id is not None and gt_video_id is not None:
    if detection_video_id != gt_video_id:
        video_boundary_rejections += 1
        # Reclassify as FN for GT and FP for detection
```

**Potential Issue**: If `video_id` is NULL for some detections, they bypass this validation!

### Issue 3: "Real" vs "Aligned" Latency Discrepancy

**User Report**: "Frame 21: aligned -12.5ms, real 962ms FAIL"

**Analysis**:
- "Aligned" latency: Likely the signed temporal offset (detection_time - gt_time)
- "Real" latency: Unclear what this represents - possibly:
  - Hardware-to-detection pipeline latency?
  - Camera capture latency?
  - Processing latency component?

**Code Search**: No field named "aligned_latency" or "real_latency" found in models.py

**Hypothesis**: These values may be:
1. Computed in frontend display logic (not in backend)
2. Part of `latency_details` JSON field in test session
3. Camera latency decomposition (see `camera_latency_measurement_service.py`)

## Field Mapping Analysis

### DetectionEvent Model Fields

**CANONICAL FIELD**: `actual_latency_ms` (Line 342-343 in models.py)
```python
actual_latency_ms = Column(Float, nullable=True, index=True,
    comment="CANONICAL: Actual measured latency from video event to hardware detection (milliseconds)")
```

**Video Timing Fields**:
- `video_relative_timestamp`: Timestamp relative to video start (seconds)
- `video_frame_number`: Frame number corresponding to detection
- `timing_sync_quality`: Quality indicator ('high', 'medium', 'low', 'unknown')

**DEPRECATED Fields** (maintained for backward compatibility):
- `latency_ns`: Old nanosecond field
- `processing_time_ms`: This is processing time, NOT latency

### DetectionComparison Model Fields

**Temporal Offset Field** (Line 755 in models.py):
```python
temporal_offset = Column(Float)  # Time difference between detection and GT
```

This is the SIGNED latency value stored in comparisons table.

## Validation Logic Review

### True Positive Latency Calculation

**File**: `ground_truth_matching_service.py`, Lines 1126-1148

```python
# Update validation_result field
detection_event.validation_result = match_result.match_type
if match_result.latency_ms is not None:
    detection_event.actual_latency_ms = match_result.latency_ms

    # AGENT #43: Only evaluate latency for TP detections (not FP marker)
    if match_result.match_type == 'TP' and match_result.latency_ms < FP_LATENCY_MARKER:
        threshold_ms = (
            detection_event.latency_threshold_ms
            or session_tolerance_ms
            or self.default_tolerance_ms
        )
        detection_event.latency_threshold_ms = threshold_ms

        if threshold_ms is not None:
            detection_event.latency_result = (
                "pass" if match_result.latency_ms <= threshold_ms else "fail"
            )
```

**Issue Found**: This compares `match_result.latency_ms` (which is `abs(latency_ms)` from line 895) against threshold. But if negative latencies are stored, this comparison fails!

### False Positive Latency Marker

**Line 45**: Sentinel value for FP detections
```python
FP_LATENCY_MARKER = 10000.0
```

False positive detections get artificial 10000ms latency to exclude them from statistics.

## Critical Bugs Identified

### Bug #1: Inconsistent Absolute Value Usage

**Location**: `ground_truth_matching_service.py`, Line 895
```python
latency_ms=abs(latency_ms),  # Takes absolute value for metrics
```

**Problem**:
- MatchResult stores absolute value
- But original signed value is needed for temporal offset analysis
- Database field `actual_latency_ms` receives absolute value
- DetectionComparison `temporal_offset` field should store signed value

**Fix Required**: Store both signed and unsigned latency:
- `temporal_offset`: Signed value (detection_time - gt_time)
- `actual_latency_ms`: Unsigned absolute value for metrics

### Bug #2: Video Boundary Validation Gaps

**Location**: `ground_truth_matching_service.py`, Lines 802-831

**Problem**:
```python
# NULL SAFETY: Skip if either video_id is NULL in multi-video mode
if has_multi_video_sequence and (detection_video_id is None or gt_video_id is None):
    logger.warning(
        f"Skipping match - NULL video_id detected..."
    )
    # Reclassifies as FN/FP but doesn't explain large latency
```

**Issue**: Detections with NULL video_id can still produce large latencies before being rejected.

**Fix Required**: Assign video_id to all detections BEFORE ground truth matching runs.

### Bug #3: Latency Statistics Only Use First 10 Per Video

**Location**: `ground_truth_matching_service.py`, Lines 1226-1254

```python
# CRITICAL NULL SAFETY: Skip if video_id is None
if mr.video_id is None:
    self.logger.warning(f"Skipping TP match result - NULL video_id...")
    continue

# Use video_id from MatchResult (populated during matching)
video_id = str(mr.video_id)
if len(video_tp_latencies[video_id]) < 10:  # Only first 10 per video
    video_tp_latencies[video_id].append(mr.latency_ms)
```

**Problem**: This CORRECTLY limits to first 10 detections per video to avoid contamination, but:
- Large latencies (920ms, 1322ms) in later detections indicate cross-video matching
- These should be rejected during matching, not filtered during statistics

### Bug #4: Missing "Real" vs "Aligned" Latency Fields

**Problem**: User mentions "real" and "aligned" latency but these fields don't exist in DetectionEvent or DetectionComparison models.

**Hypothesis**: These may be:
1. Computed values in API response transformation
2. Part of camera latency decomposition (`camera_latency_measurement_service.py`)
3. Frontend display logic computing derived values

**Investigation Needed**: Search API endpoints and response schemas for these field names.

## Recommendations

### Fix #1: Preserve Signed Latency

**Action**: Update MatchResult to store both signed and unsigned latency
```python
@dataclass
class MatchResult:
    temporal_offset: float  # Signed: detection_time - gt_time (ms)
    latency_ms: float  # Unsigned: abs(temporal_offset) for metrics
```

### Fix #2: Strict Video Boundary Enforcement

**Action**:
1. Ensure ALL detections have video_id assigned before matching
2. Reject matches with NULL video_id in multi-video sessions
3. Add validation to prevent cross-video matching earlier in pipeline

### Fix #3: Investigate "Real" vs "Aligned" Latency

**Action**: Search for these field names in:
- API routers (`/backend/routers/`)
- Response schemas (`/backend/schemas*.py`)
- Frontend API calls
- Camera latency decomposition service

### Fix #4: Add Latency Calculation Documentation

**Action**: Document in code comments:
- Signed vs unsigned latency
- When to use temporal_offset vs actual_latency_ms
- Video boundary validation requirements
- Multi-video latency calculation nuances

## Test Cases Needed

### Test 1: Negative Latency Handling
```python
def test_negative_latency_valid():
    """Test that negative latency is preserved when detection arrives early"""
    gt_times = [1.0]
    det_times = [0.99]  # 10ms early
    result = optimal_detection_matching(gt_times, det_times, tolerance_seconds=0.1)

    assert len(result['true_positives']) == 1
    gt_idx, det_idx, latency_ms = result['true_positives'][0]
    assert latency_ms == -10.0  # Should be negative
```

### Test 2: Cross-Video Match Rejection
```python
def test_cross_video_match_rejected():
    """Test that detections from video B don't match GT from video A"""
    # Setup: 2 videos with separate GT and detections
    # Expected: No cross-video matches, all classified as FN/FP
```

### Test 3: Large Latency Detection
```python
def test_large_latency_flagged():
    """Test that latencies > 500ms are flagged as potential issues"""
    # Setup: Detection with 920ms latency
    # Expected: Warning logged, potential cross-video match detected
```

## Conclusion

**Primary Issue**: The latency calculation is mathematically correct (matches to NEAREST ground truth), but:

1. **Negative latencies** are valid when detection arrives early - not a bug
2. **Large latencies** (920ms+) indicate cross-video matching issues - BUG
3. **"Real" vs "Aligned"** terminology not found in backend code - requires frontend investigation
4. **Absolute value inconsistency** - signed temporal_offset should be preserved separately from unsigned actual_latency_ms

**Immediate Action Required**:
1. Investigate NULL video_id detections causing cross-video matches
2. Find source of "real" and "aligned" latency terminology
3. Add validation to reject large latencies (>500ms) as likely errors
4. Document signed vs unsigned latency usage throughout codebase

**Files to Check Next**:
- `/backend/routers/hil_testing.py` - HIL results endpoint
- `/backend/routers/test_sessions.py` - Session results API
- `/backend/schemas*.py` - Response schemas for latency fields
- Frontend API response handlers (if accessible)
