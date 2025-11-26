# Matching Algorithm Refinement Plan
## From 59.53% to 90%+ F1 Score

**Session ID:** daad8bf6-b5da-4423-abc4-a85e83bc1c16
**Date:** 2025-11-24
**Current Performance:** TP=128, FP=45, FN=129 → F1=59.53%, Precision=73.99%, Recall=49.81%
**Target Performance:** F1 ≥ 90%

---

## Executive Summary

### Root Cause Analysis

The Hungarian algorithm is failing with "infeasible cost matrix" errors, falling back to a greedy algorithm that achieves only 59.53% F1 score. The failure is caused by **extreme cost matrix sparsity** due to:

1. **Temporal Expansion Over-Generation**: 173 real detections → 519 virtual detections (3x expansion)
2. **Sparse Valid Matches**: Only 2,432 finite values out of 125,440 total cells (1.94% density)
3. **Infeasible Rows/Columns**: Many entire rows/columns contain only infinity values

### Key Findings

| Metric | Value | Issue |
|--------|-------|-------|
| Real Detections | 173 | Baseline |
| Virtual Detections | 519 | 3x expansion factor |
| Ground Truth Objects | 257 | Targets to match |
| Cost Matrix Size | 256 × 490 | Reduced from 257 × 519 |
| Finite Values | 2,432 / 125,440 | 1.94% density (too sparse) |
| Hungarian Status | **FAILS** | "Infeasible cost matrix" |
| Fallback Algorithm | Greedy | Suboptimal assignments |
| Current F1 Score | 59.53% | Far below 90% target |

---

## Problem Diagnosis

### Issue 1: Temporal Expansion Amplifies Sparsity

**Configuration:**
```python
expand_detections_temporally(
    detections=detection_events,
    window_ms=100.0,  # ±100ms window
    interval_ms=40.0,  # 40ms intervals
    include_original=True
)
```

**Math:**
- Samples per detection: ceil(100 / 40) + 1 = 3 virtual detections per real detection
- Total virtual detections: 173 × 3 = 519 detections
- Cost matrix growth: 173 × 257 = 44,461 cells → 519 × 257 = 133,383 cells (3x increase)

**Problem:**
- Temporal expansion creates 3x more detection candidates
- Most virtual detections fall **outside** the 100ms tolerance window
- Creates massive "dead zones" of infinity values in cost matrix
- Hungarian algorithm cannot handle matrices with entire rows/columns of infinity

### Issue 2: Hungarian Algorithm Infeasibility

**Scipy Requirement:**
The Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) requires:
1. Every row has at least one finite value
2. Every column has at least one finite value
3. A complete assignment is mathematically possible

**Current State:**
```
Reduced Matrix: 256 × 490 (after prefiltering)
Finite Values: 2,432 / 125,440 = 1.94%
Status: STILL INFEASIBLE
```

**Why It Fails:**
- Even after removing obviously infeasible rows/columns, the matrix remains too sparse
- Many detections cluster temporally, leaving gaps with no ground truth nearby
- Temporal expansion creates "phantom" detections that can never match

### Issue 3: Greedy Fallback Suboptimality

**Greedy Algorithm Behavior:**
```python
for gt in ground_truth:
    find closest_detection within tolerance
    assign if available (first-match wins)
```

**Problems:**
1. **Local Optima**: Makes locally optimal choices that prevent globally optimal assignment
2. **Order Dependency**: Results depend on processing order
3. **No Backtracking**: Cannot undo bad early assignments
4. **Suboptimal Matches**: Frequently misses better global assignments

**Example Pathological Case:**
```
GT[0] at 0.000s, GT[1] at 0.050s
DET[0] at 0.045s, DET[1] at 0.055s

Greedy: GT[0] → DET[0] (45ms), GT[1] → DET[1] (5ms) ✓
Optimal: GT[0] → DET[0] (45ms), GT[1] → DET[1] (5ms) ✓ (same)

But with 3 GTs:
GT[0] at 0.000s, GT[1] at 0.050s, GT[2] at 0.100s
DET[0] at 0.045s, DET[1] at 0.055s

Greedy: GT[0] → DET[0], GT[1] unmatched, GT[2] unmatched (suboptimal)
Optimal: GT[0] unmatched, GT[1] → DET[0], GT[2] → DET[1] (better global cost)
```

---

## Proposed Solutions

### Solution 1: Disable/Reduce Temporal Expansion (IMMEDIATE IMPACT)

**Recommendation:** Disable temporal expansion entirely or reduce expansion factor

**Option A: Disable Temporal Expansion**
```python
# In ground_truth_matching_service.py line 387
enable_temporal_expansion = False  # Changed from True
```

**Expected Impact:**
- Detections: 519 → 173 (66.7% reduction)
- Cost Matrix: 133,383 → 44,461 cells (66.7% reduction)
- Sparsity: Likely improves to 5-10% (from 1.94%)
- Hungarian: Likely succeeds (fewer infeasible rows/columns)
- F1 Score: **Estimated 75-85%** (greedy becomes viable)

**Option B: Reduce Expansion Window**
```python
expanded_detections = expand_detections_temporally(
    detections=detection_events,
    window_ms=40.0,  # Reduced from 100.0ms (matches interval)
    interval_ms=40.0,
    include_original=True
)
```

**Expected Impact:**
- Samples per detection: 1 (only original) or 2 (original + 1 virtual)
- Detections: 519 → 173-346
- Better than full expansion, worse than disabling

**Rationale:**
- Temporal expansion was intended to improve matching accuracy
- In practice, it amplifies sparsity and breaks Hungarian algorithm
- The greedy fallback negates any theoretical benefit
- **Net effect: Temporal expansion currently HURTS performance**

### Solution 2: Advanced Cost Matrix Preprocessing (COMPREHENSIVE FIX)

**Recommendation:** Implement multi-stage Hungarian algorithm with smart prefiltering

**Stage 1: Aggressive Prefiltering**
```python
def prefilter_cost_matrix(cost_matrix, threshold=1e9):
    """Remove rows/columns with fewer than 2 finite values"""
    n_rows, n_cols = cost_matrix.shape

    # Count finite values per row/column
    finite_per_row = np.sum(cost_matrix < threshold, axis=1)
    finite_per_col = np.sum(cost_matrix < threshold, axis=0)

    # Keep rows/columns with at least 2 finite values
    # (more robust than requiring just 1)
    feasible_rows = finite_per_row >= 2
    feasible_cols = finite_per_col >= 2

    # Extract reduced matrix
    reduced_matrix = cost_matrix[np.ix_(feasible_rows, feasible_cols)]

    return reduced_matrix, feasible_rows, feasible_cols
```

**Stage 2: Per-Video Matching**
```python
def per_video_hungarian_matching(
    ground_truth_times,
    detection_times,
    ground_truth_video_ids,
    detection_video_ids,
    tolerance_seconds
):
    """
    Run Hungarian algorithm separately for each video.

    This prevents cross-video sparsity from creating infeasible matrices.
    """
    all_matches = []

    # Group by video_id
    for video_id in set(ground_truth_video_ids):
        gt_mask = [vid == video_id for vid in ground_truth_video_ids]
        det_mask = [vid == video_id for vid in detection_video_ids]

        gt_times_video = [t for t, m in zip(ground_truth_times, gt_mask) if m]
        det_times_video = [t for t, m in zip(detection_times, det_mask) if m]

        # Run Hungarian on this video's detections only
        video_matches = optimal_detection_matching(
            gt_times_video,
            det_times_video,
            tolerance_seconds
        )

        all_matches.append(video_matches)

    return merge_video_matches(all_matches)
```

**Stage 3: Iterative Matching**
```python
def iterative_hungarian_matching(cost_matrix):
    """
    Match in multiple passes:
    1. High-confidence matches (cost < 0.020s)
    2. Medium-confidence matches (cost < 0.050s)
    3. Low-confidence matches (cost < 0.100s)

    This prevents low-quality matches from blocking high-quality ones.
    """
    matched_gts = set()
    matched_dets = set()
    all_tp = []

    for threshold in [0.020, 0.050, 0.100]:
        # Create subproblem with unmatched elements
        remaining_cost = cost_matrix.copy()
        remaining_cost[list(matched_gts), :] = float('inf')
        remaining_cost[:, list(matched_dets)] = float('inf')
        remaining_cost[remaining_cost > threshold] = float('inf')

        # Run Hungarian on this confidence tier
        try:
            tp, fp, fn = _run_hungarian_algorithm(remaining_cost, ...)
            all_tp.extend(tp)
            matched_gts.update([gt for gt, _, _ in tp])
            matched_dets.update([det for _, det, _ in tp])
        except ValueError:
            continue  # Try next threshold tier

    return all_tp, ...
```

**Expected Impact:**
- Hungarian Success Rate: 95%+ (from current ~0%)
- F1 Score: **Estimated 85-92%**
- Matches: Better global optimization than greedy

### Solution 3: Hybrid Algorithm (BALANCED APPROACH)

**Recommendation:** Use Hungarian where feasible, greedy as fallback, combine results

```python
def hybrid_matching(cost_matrix, tolerance_seconds):
    """
    1. Try Hungarian on full matrix
    2. If infeasible, partition into feasible subproblems
    3. Run Hungarian on each partition
    4. Use greedy for remaining ambiguous cases
    """
    # Attempt 1: Full Hungarian
    try:
        return hungarian_matching(cost_matrix)
    except ValueError:
        pass

    # Attempt 2: Per-video partitioning
    try:
        return per_video_hungarian_matching(...)
    except ValueError:
        pass

    # Attempt 3: Iterative confidence tiers
    try:
        return iterative_hungarian_matching(cost_matrix)
    except ValueError:
        pass

    # Fallback: Greedy with post-optimization
    greedy_matches = greedy_matching(cost_matrix)
    return optimize_greedy_matches(greedy_matches)  # Local search improvement
```

**Expected Impact:**
- Combines best of both algorithms
- F1 Score: **Estimated 88-93%**
- Robust to edge cases

---

## Recommended Implementation Plan

### Phase 1: Quick Win (1-2 hours) - TARGET: 75-85% F1

**Action:** Disable temporal expansion
```python
# File: backend/services/ground_truth_matching_service.py
# Line: 387

# Change this:
enable_temporal_expansion = True

# To this:
enable_temporal_expansion = False  # DISABLED: Causes infeasible cost matrices
```

**Testing:**
```bash
# Run test session
python -m pytest tests/services/test_ground_truth_matching.py -v

# Verify F1 improvement
# Expected: F1 > 75%
```

**Rationale:**
- Zero code risk (simple flag flip)
- Immediate 66.7% reduction in problem size
- Likely makes Hungarian algorithm feasible
- Can always re-enable later if needed

### Phase 2: Advanced Preprocessing (4-8 hours) - TARGET: 85-92% F1

**Action:** Implement per-video matching + aggressive prefiltering

**Code Changes:**

**File 1: `backend/services/optimal_matching_service.py`**

Add after line 308 (before running Hungarian):
```python
def _prefilter_cost_matrix_advanced(
    cost_matrix: np.ndarray,
    ground_truth_video_ids: List[str],
    detection_video_ids: List[str],
    min_finite_per_row: int = 2,
    min_finite_per_col: int = 2
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Advanced prefiltering with video-aware partitioning.

    Returns:
        reduced_matrix, feasible_row_indices, feasible_col_indices
    """
    LARGE_VALUE = 1e9
    n_gt, n_det = cost_matrix.shape

    # Count finite values per row/column
    finite_per_row = np.sum(cost_matrix < LARGE_VALUE, axis=1)
    finite_per_col = np.sum(cost_matrix < LARGE_VALUE, axis=0)

    # Require at least N finite values (more robust)
    feasible_rows = finite_per_row >= min_finite_per_row
    feasible_cols = finite_per_col >= min_finite_per_col

    # If still infeasible, try per-video partitioning
    if np.sum(feasible_rows) == 0 or np.sum(feasible_cols) == 0:
        # Log warning and return partitioned approach
        logger.warning(
            f"Cost matrix still infeasible after prefiltering. "
            f"Attempting per-video partitioning."
        )
        # Return empty arrays to signal partitioning needed
        return np.array([]), np.array([]), np.array([])

    reduced_matrix = cost_matrix[np.ix_(feasible_rows, feasible_cols)]

    logger.info(
        f"Advanced prefiltering: {n_gt}×{n_det} → "
        f"{np.sum(feasible_rows)}×{np.sum(feasible_cols)} "
        f"(kept {np.sum(feasible_rows)/n_gt*100:.1f}% rows, "
        f"{np.sum(feasible_cols)/n_det*100:.1f}% cols)"
    )

    return reduced_matrix, feasible_rows, feasible_cols
```

**File 2: `backend/services/per_video_matching_service.py` (NEW)**

Create new service for per-video partitioning:
```python
"""
Per-Video Matching Service

Handles cost matrix partitioning for multi-video sequences.
Prevents cross-video sparsity from breaking Hungarian algorithm.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)

def per_video_hungarian_matching(
    ground_truth_times: List[float],
    detection_times: List[float],
    ground_truth_video_ids: List[str],
    detection_video_ids: List[str],
    tolerance_seconds: float
) -> Dict[str, Any]:
    """
    Run Hungarian algorithm separately per video, then merge results.

    This is more robust than running on the full cost matrix when:
    - Multiple videos in sequence
    - Sparse matches (clustering)
    - High temporal expansion factors
    """
    from services.optimal_matching_service import optimal_detection_matching

    # Group indices by video_id
    video_ids = sorted(set(ground_truth_video_ids + detection_video_ids))

    all_tp = []
    all_fp = []
    all_fn = []
    total_cost = 0.0

    for video_id in video_ids:
        # Extract indices for this video
        gt_indices = [i for i, vid in enumerate(ground_truth_video_ids) if vid == video_id]
        det_indices = [i for i, vid in enumerate(detection_video_ids) if vid == video_id]

        if not gt_indices or not det_indices:
            # No matches possible for this video
            all_fn.extend(gt_indices)
            all_fp.extend(det_indices)
            continue

        # Extract times for this video
        gt_times_video = [ground_truth_times[i] for i in gt_indices]
        det_times_video = [detection_times[i] for i in det_indices]

        # Run Hungarian on this video's subset
        video_result = optimal_detection_matching(
            gt_times_video,
            det_times_video,
            tolerance_seconds,
            return_cost_matrix=False,
            ground_truth_video_ids=None,  # Already filtered
            detection_video_ids=None
        )

        # Map results back to global indices
        for gt_local, det_local, latency in video_result['true_positives']:
            gt_global = gt_indices[gt_local]
            det_global = det_indices[det_local]
            all_tp.append((gt_global, det_global, latency))

        for det_local in video_result['false_positives']:
            all_fp.append(det_indices[det_local])

        for gt_local in video_result['false_negatives']:
            all_fn.append(gt_indices[gt_local])

        total_cost += video_result['total_cost']

    logger.info(
        f"Per-video matching complete: {len(video_ids)} videos, "
        f"{len(all_tp)} TP, {len(all_fp)} FP, {len(all_fn)} FN"
    )

    return {
        'true_positives': all_tp,
        'false_positives': all_fp,
        'false_negatives': all_fn,
        'total_cost': total_cost,
        'algorithm': 'per_video_hungarian'
    }
```

**Testing:**
```python
# Add to tests/services/test_optimal_matching_service.py

def test_per_video_matching_multi_video_sequence():
    """Test per-video matching with sparse cost matrix"""
    # Video 1: 3 GT, 2 Det
    gt_times = [0.0, 0.1, 0.2, 5.0, 5.1, 5.2]
    det_times = [0.05, 0.15, 5.05, 5.15]
    gt_video_ids = ['v1', 'v1', 'v1', 'v2', 'v2', 'v2']
    det_video_ids = ['v1', 'v1', 'v2', 'v2']

    result = per_video_hungarian_matching(
        gt_times, det_times, gt_video_ids, det_video_ids,
        tolerance_seconds=0.1
    )

    # Should match: GT[0]→Det[0], GT[1]→Det[1], GT[3]→Det[2], GT[4]→Det[3]
    assert len(result['true_positives']) == 4
    assert len(result['false_negatives']) == 2  # GT[2], GT[5]
    assert len(result['false_positives']) == 0
```

### Phase 3: Hybrid Algorithm (6-12 hours) - TARGET: 88-93% F1

**Action:** Implement full hybrid approach with iterative matching

**Code Changes:**

**File: `backend/services/hybrid_matching_service.py` (NEW)**

Implement iterative confidence-tier matching as shown in Solution 3 above.

**Integration:**
```python
# In optimal_matching_service.py

def optimal_detection_matching(...):
    # Try hybrid algorithm first
    if USE_HYBRID_ALGORITHM:
        return hybrid_matching(...)

    # Fallback to original logic
    ...
```

---

## Expected Performance Improvements

### Current Performance (Baseline)
```
Algorithm: Greedy (Hungarian fails)
True Positives: 128
False Positives: 45
False Negatives: 129
Precision: 73.99%
Recall: 49.81%
F1 Score: 59.53%
```

### Phase 1: Disable Temporal Expansion (Estimated)
```
Algorithm: Hungarian (likely succeeds)
True Positives: 155-165 (↑ 21-29%)
False Positives: 8-18 (↓ 60-82%)
False Negatives: 92-102 (↓ 21-29%)
Precision: 90.0-95.0% (↑ 22%)
Recall: 60.0-64.0% (↑ 20%)
F1 Score: 72.0-76.0% (↑ 21%)
```

**Rationale:**
- Removing virtual detections reduces FP significantly
- Hungarian algorithm likely succeeds on 173×257 matrix (vs 519×257)
- Better global optimization improves TP/FN balance

### Phase 2: Per-Video Matching (Estimated)
```
Algorithm: Per-Video Hungarian
True Positives: 215-225 (↑ 68-76%)
False Positives: 5-10 (↓ 89-94%)
False Negatives: 32-42 (↓ 67-75%)
Precision: 95.6-97.8% (↑ 29%)
Recall: 83.7-87.5% (↑ 68%)
F1 Score: 89.0-92.0% (↑ 50%)
```

**Rationale:**
- Partitioning by video eliminates cross-video sparsity
- Hungarian succeeds on smaller, denser subproblems
- Each video gets optimal assignments
- Significantly reduces FP through better discrimination

### Phase 3: Hybrid Algorithm (Estimated)
```
Algorithm: Hybrid (iterative + per-video + greedy fallback)
True Positives: 225-235 (↑ 76-84%)
False Positives: 3-8 (↓ 82-93%)
False Negatives: 22-32 (↓ 75-83%)
Precision: 96.6-98.7% (↑ 31%)
Recall: 87.5-91.4% (↑ 76%)
F1 Score: 91.5-94.5% (↑ 54%)
```

**Rationale:**
- Iterative matching handles edge cases better
- Confidence tiers prevent low-quality matches from blocking high-quality ones
- Greedy fallback handles truly ambiguous cases
- Near-optimal performance across all scenarios

---

## Risk Assessment

### Phase 1: Disable Temporal Expansion
- **Risk Level:** LOW
- **Reversibility:** HIGH (simple flag)
- **Testing Required:** Moderate (verify F1 improvement)
- **Deployment Impact:** None (algorithm change only)

### Phase 2: Per-Video Matching
- **Risk Level:** MEDIUM
- **Reversibility:** MEDIUM (new code path)
- **Testing Required:** High (unit + integration tests)
- **Deployment Impact:** Low (backward compatible)

### Phase 3: Hybrid Algorithm
- **Risk Level:** MEDIUM-HIGH
- **Reversibility:** MEDIUM (complex logic)
- **Testing Required:** Very High (extensive edge cases)
- **Deployment Impact:** Low (backward compatible)

---

## Testing Strategy

### Unit Tests (All Phases)
```python
# tests/services/test_matching_algorithms.py

def test_sparse_cost_matrix_handling():
    """Test algorithm handles sparse matrices correctly"""
    # 90% infinity values
    ...

def test_multi_video_cross_filtering():
    """Test cross-video matches are filtered"""
    ...

def test_temporal_expansion_disabled():
    """Test matching works without expansion"""
    ...

def test_per_video_partitioning():
    """Test per-video matching produces correct results"""
    ...

def test_iterative_confidence_tiers():
    """Test confidence-based iterative matching"""
    ...
```

### Integration Tests
```python
# tests/integration/test_ground_truth_matching_e2e.py

def test_real_hil_dataset_f1_improvement():
    """Test F1 score on real HIL data"""
    session_id = "daad8bf6-b5da-4423-abc4-a85e83bc1c16"
    result = match_detections_to_ground_truth(session_id)

    # Verify F1 > 90%
    assert result.f1_score >= 0.90
    assert result.precision >= 0.85
    assert result.recall >= 0.85
```

### Performance Tests
```python
def test_matching_performance_large_dataset():
    """Test algorithm completes in reasonable time"""
    # 1000 detections × 1000 GT
    start = time.time()
    result = optimal_detection_matching(...)
    duration = time.time() - start

    # Should complete in < 5 seconds
    assert duration < 5.0
```

---

## Rollout Plan

### Week 1: Quick Win
- [ ] Disable temporal expansion (Phase 1)
- [ ] Deploy to staging
- [ ] Run full test suite
- [ ] Verify F1 > 75%
- [ ] Deploy to production if successful

### Week 2: Advanced Implementation
- [ ] Implement per-video matching (Phase 2)
- [ ] Add comprehensive unit tests
- [ ] Deploy to staging
- [ ] A/B test vs Phase 1
- [ ] Verify F1 > 88%

### Week 3: Hybrid Algorithm
- [ ] Implement iterative matching (Phase 3)
- [ ] Performance optimization
- [ ] Stress testing
- [ ] Deploy to production

### Week 4: Monitoring & Optimization
- [ ] Monitor F1 scores across all sessions
- [ ] Identify edge cases
- [ ] Fine-tune parameters
- [ ] Document findings

---

## Success Metrics

| Metric | Current | Phase 1 Target | Phase 2 Target | Phase 3 Target |
|--------|---------|----------------|----------------|----------------|
| F1 Score | 59.53% | 75%+ | 90%+ | 92%+ |
| Precision | 73.99% | 90%+ | 96%+ | 97%+ |
| Recall | 49.81% | 62%+ | 84%+ | 88%+ |
| Hungarian Success | 0% | 85%+ | 95%+ | 98%+ |
| Execution Time | <1s | <1s | <2s | <3s |

---

## Conclusion

The current 59.53% F1 score is primarily caused by:
1. **Temporal expansion over-generation** creating 3x sparse cost matrices
2. **Hungarian algorithm infeasibility** due to extreme sparsity
3. **Greedy fallback suboptimality** producing poor global assignments

**Recommended Immediate Action:** Disable temporal expansion (Phase 1) for quick 75%+ F1 score.

**Recommended Long-Term Solution:** Implement per-video partitioned Hungarian matching (Phase 2) for 90%+ F1 score.

**Future Enhancement:** Add hybrid algorithm (Phase 3) for 92%+ F1 score and maximum robustness.

**Temporal Expansion Decision:** Keep disabled until cost matrix construction is improved to handle increased density. Current implementation adds complexity without providing benefit.

---

## Appendices

### Appendix A: Mathematical Analysis

**Hungarian Algorithm Complexity:**
- Time: O(n³) for n×n matrix
- Space: O(n²)
- Requirement: Complete bipartite graph (all finite costs)

**Current Problem:**
- Matrix: 519 × 257 (expanded)
- Density: 1.94% finite values
- Infeasible: Yes (entire rows/columns of infinity)

**Phase 1 Improvement:**
- Matrix: 173 × 257 (original)
- Expected Density: 5-10% finite values
- Infeasible: Likely no

### Appendix B: Code Locations

**Files to Modify:**
1. `backend/services/ground_truth_matching_service.py` - Line 387 (temporal expansion flag)
2. `backend/services/optimal_matching_service.py` - Lines 308-362 (Hungarian prefiltering)
3. `backend/services/per_video_matching_service.py` - New file (per-video partitioning)
4. `backend/services/hybrid_matching_service.py` - New file (hybrid algorithm)

**Files to Create:**
1. `backend/tests/services/test_per_video_matching.py`
2. `backend/tests/services/test_hybrid_matching.py`
3. `backend/tests/integration/test_matching_e2e.py`

### Appendix C: References

- Hungarian Algorithm: Kuhn, H. W. (1955). "The Hungarian Method for the assignment problem"
- Greedy Algorithm Limitations: Cormen et al. "Introduction to Algorithms" Chapter 16
- Cost Matrix Sparsity: Current analysis from session daad8bf6-b5da-4423-abc4-a85e83bc1c16
- Temporal Expansion: `backend/src/services/temporal_expansion.py` lines 69-184

---

**Document Version:** 1.0
**Last Updated:** 2025-11-24
**Author:** System Architecture Designer
**Review Status:** Ready for Implementation
