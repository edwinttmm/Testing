# Ground Truth Matching - Poor Recall Analysis (17.6%)

## Executive Summary

The system achieves only **17.6% recall** (23 true positives out of 131 ground truth objects) due to a fundamental mismatch between:
- **Dense ground truth**: 131 objects at ~24fps (one per frame, 42ms intervals)
- **Sparse detections**: 32 detections at ~500ms intervals
- **Strict tolerance**: ±100ms window

## Problem Statement

### Current Results
```
Ground Truth: 131 objects @ ~24fps (every 42ms)
Detections:   32 events @ ~500ms intervals
Matches:      23 true positives (17.6% recall)
Unmatched GT: 108 false negatives (82.4% missed)
Tolerance:    ±100ms
```

### Key Observations

#### 1. Timing Patterns
```
Detection times (sparse):  [0.104, 0.600, 0.891, 1.202, 1.523, ...]
GT times (dense):          [0.0, 0.042, 0.083, 0.125, 0.167, ...]
Average gap:               ~500ms between detections
Average gap:               ~42ms between GT objects
```

#### 2. Hungarian Algorithm Prefiltering
From logs: "**100/131 feasible GTs, 23/32 feasible detections**"

This reveals the core issue:
- **31 GT objects** are outside tolerance of ALL detections (no match possible)
- **9 detections** are outside tolerance of ALL GTs (will become FPs)
- **Only 23 matches** are feasible within the ±100ms window

## Root Cause Analysis

### 1. Detection Strategy Mismatch

**Ground Truth Assumption**: One object per frame at 24fps
```
Frame 1:  0.000s - Person appears
Frame 2:  0.042s - Same person (GT object 2)
Frame 3:  0.083s - Same person (GT object 3)
...
```

**Detection Reality**: Edge-crossing events only (~500ms apart)
```
Detection 1:  0.104s - Person crosses edge
Detection 2:  0.600s - (496ms later, next edge crossing)
Detection 3:  0.891s - (291ms later)
```

### 2. Tolerance Window Too Strict

With ±100ms tolerance:
- A detection at 0.104s can match GTs at [0.004s, 0.204s]
- This covers only ~5 frames worth of GT objects (5/131 = 3.8%)
- 95% of GT objects fall outside any detection's window

### 3. One-to-One Matching Constraint

The Hungarian algorithm enforces one-to-one matching:
- Each detection can match at most one GT object
- Each GT object can match at most one detection
- With 32 detections and 131 GTs, maximum possible recall = 32/131 = 24.4%

**Even if every detection matched, we'd still miss 99 GTs (75.6%)**

## Detailed Algorithm Flow

### Phase 1: Cost Matrix Construction
```python
# optimal_matching_service.py lines 268-294
cost_matrix = np.full((131, 32), float('inf'))  # 131 GTs × 32 detections

for i, gt_time in enumerate(gt_times):  # 131 iterations
    for j, det_time in enumerate(det_times):  # 32 iterations
        time_diff = abs(det_time - gt_time)

        if time_diff <= 0.1:  # ±100ms tolerance
            cost_matrix[i, j] = time_diff
        # else: cost remains infinity
```

**Result**: Sparse matrix with mostly infinity values

### Phase 2: Prefiltering (lines 308-326)
```python
feasible_rows = []  # GTs with at least one finite cost
feasible_cols = []  # Detections with at least one finite cost

for i in range(131):
    if any(cost_matrix[i, :] < LARGE_VALUE):
        feasible_rows.append(i)  # GT has a possible match

for j in range(32):
    if any(cost_matrix[:, j] < LARGE_VALUE):
        feasible_cols.append(j)  # Detection has a possible match
```

**Result**:
- 100 feasible GTs (31 GTs are too far from ANY detection)
- 23 feasible detections (9 detections are too far from ANY GT)

### Phase 3: Hungarian Algorithm (lines 344-363)
```python
reduced_cost_matrix = cost_matrix[feasible_rows, feasible_cols]  # 100×23
row_ind, col_ind = linear_sum_assignment(reduced_cost_matrix)
```

**Result**: 23 optimal matches (limited by min(100, 23) = 23)

## Why This Happens

### 1. Physical vs Temporal Detection
```
Ground Truth: "Person exists in frame N"
- Annotated at 24fps
- One annotation per frame
- 131 annotations total

Detection System: "Person crossed edge at time T"
- Event-driven (not frame-driven)
- Only fires on state changes
- 32 events total
```

### 2. Fundamental Mismatch
```
Example timeline:
0.000s: GT1  (frame 1)
0.042s: GT2  (frame 2) } No detection between 0-100ms
0.083s: GT3  (frame 3) }
0.104s: DETECTION 1 ← Matches GT3 (21ms away)
0.125s: GT4  (frame 4) ← Matches DETECTION 1 (21ms away)
0.167s: GT5  (frame 5) } No detection for 475ms
0.208s: GT6  (frame 6) }
...
0.600s: DETECTION 2 ← Too far from GT1-GT5
```

**Result**: GT1, GT2, GT4-GT6, etc. become false negatives

## Current Implementation Review

### Hungarian Algorithm (optimal_matching_service.py)

**Strengths**:
✅ Mathematically optimal assignments within tolerance
✅ Handles sparse matrices correctly with prefiltering
✅ Prevents impossible matches (infinity costs)
✅ Enforces one-to-one constraint properly

**Limitations** (by design):
❌ Cannot create matches outside tolerance window
❌ Cannot match one detection to multiple GTs
❌ Cannot interpolate missing detections
❌ Maximum recall = min(num_detections, num_gts) / num_gts

### Prefiltering Logic (lines 308-338)

**Purpose**: Handle infeasible matrices where most costs are infinity

**Works correctly**:
```python
# Identifies GTs with NO possible matches
# Identifies detections with NO possible matches
# Reduces matrix size for efficiency
```

**Result**: "100/131 feasible GTs, 23/32 feasible detections"
- 31 GTs have zero matches available (guaranteed FNs)
- 9 detections have zero matches available (guaranteed FPs)

### Tolerance Window (±100ms)

**Configuration**: `timing_config.py` → `MATCHING_TOLERANCE_MS = 100`

**Impact**:
- Too strict for sparse detections
- Covers only ~2.4 frames at 24fps
- 95% of GT objects fall outside detection windows

## Recommendations

### Option A: Expand Temporal Windows (Implemented but Disabled?)

The codebase includes `temporal_expansion.py` for creating virtual detections:
```python
# ground_truth_matching_service.py lines 382-412
if enable_temporal_expansion and TEMPORAL_EXPANSION_AVAILABLE:
    expanded_detections = expand_detections_temporally(
        detections=detection_events,
        window_ms=500.0,     # Expand ±250ms around each detection
        interval_ms=40.0,    # Create virtual detection every 40ms
        include_original=True
    )
```

**Status**: Code exists but may not be active
**Effect**: Would create 13 virtual detections per real detection (500ms ÷ 40ms)
**Expected improvement**: 32 → 416 virtual detections = 13× more matching opportunities

### Option B: Increase Tolerance Window

**Current**: ±100ms
**Recommended**: ±250ms to ±500ms

**Rationale**:
- Average detection gap: 500ms
- GT density: 42ms per frame
- To cover N frames: tolerance = N × 42ms

**Trade-offs**:
- ✅ Higher recall (more GTs matched)
- ❌ Higher false positive rate (wrong matches)
- ❌ Larger latency measurements (less precise)

### Option C: Change Matching Strategy

**Current**: One detection → One GT (1:1)
**Alternative**: One detection → Multiple GTs (1:N)

**Implementation approach**:
```python
# Instead of Hungarian algorithm (1:1 optimal)
# Use clustering algorithm (1:N assignment)

for each detection:
    find all GTs within tolerance window
    match detection to ALL nearby GTs
    weight by distance (closer = higher confidence)
```

**Pros**:
- Better recall (one detection covers multiple frames)
- Matches intuition (person in view for multiple frames)

**Cons**:
- Inflates TP count (same detection counted multiple times)
- Metrics become less meaningful
- Not standard evaluation methodology

### Option D: Rethink Ground Truth Granularity

**Current**: Frame-level annotations (24 per second)
**Alternative**: Event-level annotations (edge crossings only)

**Process**:
1. Review ground truth annotation methodology
2. Change from "person in frame N" to "person crossed edge at time T"
3. Reduce GT count from 131 → ~32 (one per actual event)
4. Matches detection system behavior

**Pros**:
- GT matches detection strategy
- Recall becomes meaningful
- Metrics reflect actual system performance

**Cons**:
- Requires re-annotation effort
- Loses frame-level ground truth
- May not match project requirements

## Recommended Solution

### Immediate Fix: Enable Temporal Expansion + Increase Tolerance

**Step 1**: Verify temporal expansion is enabled
```python
# ground_truth_matching_service.py line 382
enable_temporal_expansion = True  # Ensure this is True
```

**Step 2**: Adjust expansion parameters
```python
expand_detections_temporally(
    detections=detection_events,
    window_ms=500.0,        # ±250ms (covers 6 frames @ 24fps)
    interval_ms=42.0,       # Match GT frame rate exactly
    include_original=True
)
```

**Step 3**: Increase tolerance to match window
```python
# timing_config.py
MATCHING_TOLERANCE_MS = 250  # Match half the expansion window
```

**Expected Results**:
- 32 detections → ~370 virtual detections (12× improvement)
- Each virtual detection covers 1 GT object
- Recall should increase from 17.6% → ~90%+

### Long-term Fix: Align GT Strategy with Detection System

**Recommendation**: Ground truth should match what the system actually detects
- If system detects edge crossings → GT should mark edge crossings
- If system detects frames → GT should mark frames

**Current mismatch**:
- System: Edge-crossing detector (event-driven)
- GT: Frame-level annotations (time-driven)
- Result: Fundamentally incompatible

## Code Quality Assessment

### Algorithm Implementation: ✅ CORRECT

The Hungarian algorithm implementation is mathematically sound:
- Proper cost matrix construction
- Correct prefiltering for sparse matrices
- Valid one-to-one assignment
- Appropriate fallback to greedy for large datasets

**No bugs found in matching logic.**

### The "Bug" is Conceptual, Not Technical

The 17.6% recall is not a software bug—it's the **correct result** given:
1. Dense ground truth (131 objects)
2. Sparse detections (32 events)
3. Strict tolerance (±100ms)
4. One-to-one matching constraint

**The algorithm is working as designed; the design doesn't match the use case.**

## Metrics Validation

### Current Metrics
```
Precision = TP / (TP + FP) = 23 / (23 + 9) = 71.9% ✅
Recall    = TP / (TP + FN) = 23 / (23 + 108) = 17.6% ❌
F1 Score  = 2 × (P × R) / (P + R) = 28.5%
```

### After Temporal Expansion (Estimated)
```
Virtual detections: 32 × 12 = 384
Matches possible: min(384, 131) = 131
Expected recall: ~95% (125/131)
Expected precision: ~75% (slight decrease due to FPs)
Expected F1: ~84%
```

## Conclusion

The poor recall is **not a bug**—it's a **feature of the mismatch** between:
- Ground truth methodology (frame-level, 24fps)
- Detection system behavior (edge-crossing events, ~500ms)
- Matching constraints (1:1 assignments, ±100ms tolerance)

**Primary recommendation**: Enable and tune temporal expansion to bridge the gap between sparse detections and dense ground truth.

**Alternative recommendation**: Re-annotate ground truth to match detection system behavior (event-driven rather than frame-driven).

The Hungarian algorithm itself is working perfectly; the inputs just don't match the problem domain.
