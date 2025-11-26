# Root Cause Analysis: "No Feasible Matches" Bug

## Executive Summary

**Problem:** Optimal matching algorithm reports "No feasible matches found" despite having correct timestamps and valid matches within tolerance.

**Root Cause:** scipy's `linear_sum_assignment` (Hungarian algorithm) throws a `ValueError` when the cost matrix has entire rows or columns filled with infinity, even if some finite costs exist elsewhere.

**Impact:** Zero true positives reported, all detections marked as false positives, all ground truth as false negatives.

---

## Evidence

### 1. Database Timestamps (Confirmed Correct)
```
Ground Truth (24 FPS):
- GT[0] = 0.000s
- GT[1] = 0.042s
- GT[2] = 0.083s
- GT[3] = 0.125s
- GT[4] = 0.167s

Detections:
- DET[0] = 0.094s
- DET[1] = 0.236s
- DET[2] = 0.378s
- DET[3] = 0.520s
- DET[4] = 0.662s

Tolerance: 100ms (0.1s)
```

### 2. Expected Matches (6 Valid Within 100ms)
```
✅ GT[0]=0.000s ↔ DET[0]=0.094s: diff=94ms
✅ GT[1]=0.042s ↔ DET[0]=0.094s: diff=52ms
✅ GT[2]=0.083s ↔ DET[0]=0.094s: diff=11ms ← BEST MATCH
✅ GT[3]=0.125s ↔ DET[0]=0.094s: diff=31ms
✅ GT[4]=0.167s ↔ DET[0]=0.094s: diff=73ms
✅ GT[4]=0.167s ↔ DET[1]=0.236s: diff=69ms
```

### 3. Cost Matrix Built (6 Valid Entries)
```
     DET[0]  DET[1]  DET[2]  DET[3]  DET[4]
GT[0] 0.094   inf     inf     inf     inf
GT[1] 0.052   inf     inf     inf     inf
GT[2] 0.011   inf     inf     inf     inf  ← Best match to DET[0]
GT[3] 0.031   inf     inf     inf     inf
GT[4] 0.073   0.069   inf     inf     inf
```

**Observation:** Columns 2, 3, 4 are **all infinity** (no matches possible).

### 4. Hungarian Algorithm Failure
```python
try:
    gt_indices, det_indices = linear_sum_assignment(cost_matrix)
except ValueError as e:
    # Exception: "cost matrix is infeasible"
```

**Reason:** scipy's Hungarian algorithm requires that every row and column can be assigned. When entire columns/rows are infinity, the problem is deemed "infeasible" and throws ValueError.

---

## Root Cause Explanation

### Why Hungarian Algorithm Fails

The Hungarian algorithm solves the **assignment problem**: assign N workers to N jobs such that total cost is minimized. It assumes:

1. **Square or rectangular matrix** where assignment is possible
2. **Every row can be assigned to some column** (at least one finite value per row)
3. **Every column can be assigned to some row** (at least one finite value per column)

In our case:
- **DET[2], DET[3], DET[4]** have **NO matches** (all infinity)
- The algorithm cannot complete the assignment
- Throws `ValueError: "cost matrix is infeasible"`

### Why This Happens in Production

**Scenario:** Detections arrive in bursts (temporal clustering)

```
Video Timeline (5 seconds):
0s──────1s──────2s──────3s──────4s──────5s
│       │       │       │       │       │
GT: ●●●●●●●●●●  (uniform 24 FPS)
DET: ●●        ●●●●      ●   (clustered, not uniform)
     ↑         ↑         ↑
     burst1    burst2    burst3
```

**Result:** Many detections fall **outside 100ms window** of any ground truth, creating entire rows/columns of infinity in the cost matrix.

---

## Solutions

### Option 1: Prefilter Cost Matrix (RECOMMENDED)

Remove rows/columns that are entirely infinity before calling Hungarian algorithm:

```python
# Filter out infeasible rows/columns
finite_rows = np.any(cost_matrix < float('inf'), axis=1)
finite_cols = np.any(cost_matrix < float('inf'), axis=0)

if not np.any(finite_rows) or not np.any(finite_cols):
    # No matches at all
    return {'true_positives': [], 'false_positives': [...], ...}

# Extract feasible submatrix
feasible_cost = cost_matrix[finite_rows, :][:, finite_cols]

# Run Hungarian on feasible submatrix
gt_indices, det_indices = linear_sum_assignment(feasible_cost)

# Map back to original indices
original_gt_indices = np.where(finite_rows)[0][gt_indices]
original_det_indices = np.where(finite_cols)[0][det_indices]

# Classify filtered-out rows/cols as FP/FN
```

**Pros:**
- Fixes the immediate bug
- Mathematically sound
- Preserves optimality for feasible matches

**Cons:**
- More complex code
- Requires index mapping

### Option 2: Use Greedy Algorithm Fallback

Already implemented for timeout protection, can extend for infeasible matrices:

```python
try:
    gt_indices, det_indices = linear_sum_assignment(cost_matrix)
except ValueError as e:
    if "infeasible" in str(e):
        logger.warning("Cost matrix infeasible, falling back to greedy algorithm")
        return greedy_matching(...)
```

**Pros:**
- Simple code change
- Robust fallback

**Cons:**
- Loses optimality guarantee
- Greedy may give suboptimal results

### Option 3: Modify Cost Matrix (Use Large Finite Value)

Replace `inf` with a very large finite value (e.g., `1e9`):

```python
cost_matrix[cost_matrix == float('inf')] = 1e9
```

**Pros:**
- Minimal code change
- Hungarian algorithm will avoid high-cost assignments naturally

**Cons:**
- Not mathematically clean
- May cause numerical issues
- Assignments with cost 1e9 still need to be filtered out

---

## Recommended Fix

**Implement Option 1 (Prefilter) with Option 2 (Greedy Fallback)**

1. **Before Hungarian:** Filter out infeasible rows/columns
2. **If empty submatrix:** Return all FP/FN immediately
3. **Run Hungarian:** On feasible submatrix
4. **Map results back:** To original indices
5. **Classify remaining:** Filtered rows → FN, filtered columns → FP

---

## Impact on Production

### Current Behavior (Buggy)
```
Input: 173 detections, 176 ground truth
Temporal expansion: 173 → 519 detections
Result: 0 TP, 519 FP, 176 FN ← BUG!
```

### Expected Behavior (After Fix)
```
Input: 173 detections, 176 ground truth
Temporal expansion: 173 → 519 detections
Result: ~150-170 TP, ~49 FP, ~6-26 FN ← Realistic
```

---

## Testing Strategy

### Unit Tests
1. **Test with all-infinity matrix** → should handle gracefully
2. **Test with partially-infinity matrix** → should find feasible matches
3. **Test with fully-finite matrix** → should work as before

### Integration Tests
1. **Test with real HIL data** → verify >90% TP rate
2. **Test with clustered detections** → verify robust handling
3. **Test with temporal expansion** → verify expansion doesn't break matching

---

## Files to Modify

1. **`services/optimal_matching_service.py`**
   - Function: `_run_hungarian_no_timeout()`
   - Add prefiltering logic before line 310 (before linear_sum_assignment)

2. **`tests/services/test_optimal_matching_service.py`** (create if not exists)
   - Add unit tests for edge cases

---

## Estimated Fix Complexity

- **Code changes:** ~50 lines
- **Testing:** ~100 lines
- **Time to implement:** 2-3 hours
- **Risk level:** Medium (core matching logic)

---

## Conclusion

The bug is **NOT in timestamp extraction** (timestamps are correct). The bug is in the **Hungarian algorithm error handling** when the cost matrix has infeasible rows/columns. The fix is to **prefilter the cost matrix** before calling `linear_sum_assignment` and properly classify filtered elements as FP/FN.
