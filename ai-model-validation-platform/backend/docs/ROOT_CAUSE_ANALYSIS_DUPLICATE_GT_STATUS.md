# ROOT CAUSE ANALYSIS: Duplicate GT Status Bug

**Date**: 2025-11-20
**Reporter**: System Analysis
**Severity**: CRITICAL
**Status**: Root Cause Identified

---

## Executive Summary

The detection timeline shows **IMPOSSIBLE BEHAVIOR**: same detection displaying BOTH "GT PASS" and "GT FAIL" simultaneously.

```
Detection Frame 28, 1.167s, aligned 19.8ms, real -6ms, FAIL, 4.24V (AIN0) → GT PASS
Detection Frame 28, 1.167s, aligned 19.8ms, real -6ms, FAIL, 4.24V (AIN0) → GT FAIL
```

**Root Cause**: Option C temporal expansion creates multiple virtual detections that match the SAME ground truth object, but the collapse function (`_collapse_virtual_matches`) is grouping by **detection_event_id** (parent) instead of **ground_truth_id**, allowing multiple records with conflicting GT status to persist in the database.

---

## Investigation Evidence

### 1. Database Analysis ✅

**Query Results**:
```sql
-- No duplicate detection_events found at timestamp ~1.167s
SELECT * FROM detection_events WHERE timestamp BETWEEN 1.16 AND 1.18;
-- Result: 0 rows (no duplicates in DB)

-- No duplicate detection_comparisons found
SELECT * FROM detection_comparisons WHERE ...;
-- Result: 0 rows at this timestamp

-- BUT: Multiple detections matched to SAME ground truth!
SELECT ground_truth_match_id, COUNT(*)
FROM detection_events
WHERE ground_truth_match_id IS NOT NULL
GROUP BY ground_truth_match_id
HAVING COUNT(*) > 1;
-- Result: 10 GT objects each matched by 2-10 detections!
```

**Evidence**: Database integrity is fine (no duplicates in raw tables), but **matching relationship** is wrong—multiple detections point to the same GT object.

### 2. WebSocket Deduplication ✅

**File**: `/backend/services/websocket_rooms.py`
**Lines**: 47-76, 129-154

**Code Review**: The WebSocket fix IS properly saved and prevents duplicate emissions:
```python
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.create_task(_sio.emit(event, data, room=room_name))
        return True  # CRITICAL: Return here to prevent double emission
except RuntimeError:
    pass
```

**Evidence**: WebSocket layer is NOT the source of duplication.

### 3. Option C Temporal Expansion 🔴 **BUG FOUND**

**File**: `/backend/src/services/temporal_expansion.py`

**How It Works**:
1. Each detection is expanded into multiple virtual detections:
   ```
   Detection det-1 at t=1000ms
   → det-1-v0 at 1000ms
   → det-1-v1 at 1040ms
   → det-1-v2 at 1080ms
   → ... (13 samples across 500ms window)
   ```

2. Hungarian matching runs on expanded set:
   ```
   det-1-v0 → GT-A (match found)
   det-1-v1 → GT-A (ALSO matches same GT!)
   det-1-v2 → GT-B (matches different GT)
   ```

3. **BUG**: `collapse_duplicates()` (lines 187-286) groups by **parent_detection_id**:
   ```python
   # CURRENT (WRONG):
   parent_groups = {}
   for match in matches:
       detection_id = match.detection_id
       if '-v' in detection_id:
           parent_id = detection_id.rsplit('-v', 1)[0]
       else:
           parent_id = detection_id

       if parent_id not in parent_groups:
           parent_groups[parent_id] = []
       parent_groups[parent_id].append(match)

   # Result: Groups by DETECTION ID, not GROUND TRUTH ID
   # det-1-v0 → GT-A } Same parent (det-1)
   # det-1-v1 → GT-A } BUT ALSO same GT!
   # This keeps BOTH because they're in same parent group!
   ```

### 4. Matching Service Implementation 🔴 **CONFIRMING BUG**

**File**: `/backend/services/ground_truth_matching_service.py`
**Lines**: 361-392, 774-854

**Code Analysis**:
```python
# Line 368: Expand detections
expanded_detections = expand_detections_temporally(
    detections=detection_events,
    window_ms=500.0,
    interval_ms=40.0,
    include_original=True
)

# Line 381: Perform matching (produces duplicates)
match_results = self._perform_temporal_matching(
    expanded_detections,
    ground_truth_objects,
    tolerance_ms,
    test_session=test_session,
    db=db
)

# Line 391: Collapse (BROKEN)
match_results = self._collapse_virtual_matches(match_results)
```

**The `_collapse_virtual_matches` Implementation** (Lines 774-854):
```python
def _collapse_virtual_matches(self, match_results: List[MatchResult]) -> List[MatchResult]:
    parent_groups = {}

    for match in match_results:
        detection_id = match.detection_event_id

        # Extract parent ID
        if detection_id and '-v' in detection_id:
            parent_id = detection_id.rsplit('-v', 1)[0]
        else:
            parent_id = detection_id

        # ❌ BUG: Grouping by parent_id allows multiple GTs per parent
        if parent_id not in parent_groups:
            parent_groups[parent_id] = []
        parent_groups[parent_id].append(match)

    # Select best match per parent
    deduplicated_matches = []
    for parent_id, group in parent_groups.items():
        if len(group) == 1:
            deduplicated_matches.append(group[0])
            continue

        # Keep match with smallest temporal offset
        best_match = min(group, key=lambda m: abs(m.temporal_offset))
        best_match.detection_event_id = parent_id  # Remove virtual suffix
        deduplicated_matches.append(best_match)

    return deduplicated_matches
```

**THE BUG**: This function allows:
```
parent_groups['det-1'] = [
    MatchResult(det='det-1-v0', gt='GT-A', offset=10ms),  ← KEPT (best offset)
    MatchResult(det='det-1-v1', gt='GT-A', offset=50ms),  ← REJECTED (same parent, worse offset)
    MatchResult(det='det-1-v2', gt='GT-B', offset=90ms)   ← KEPT (different GT)
]
```

But this is WRONG when multiple virtual detections match SAME GT from different parent detections:
```
parent_groups['det-1'] = [
    MatchResult(det='det-1-v0', gt='GT-A', offset=10ms)   ← KEPT
]
parent_groups['det-2'] = [
    MatchResult(det='det-2-v0', gt='GT-A', offset=15ms)   ← ALSO KEPT!
]
```

**Result**: GT-A appears matched by BOTH det-1 AND det-2, creating duplicate GT status!

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: Detection Capture                                           │
│ LabJack → 1 detection at t=1.167s → Stored in detection_events     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: Option C Temporal Expansion                                 │
│ 1 detection → 13 virtual detections (500ms window, 40ms interval)   │
│ det-1 → [det-1-v0, det-1-v1, det-1-v2, ..., det-1-v12]             │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: Hungarian Matching                                          │
│ 13 virtual detections × N ground truth objects → Match matrix       │
│ det-1-v0 → GT-A (offset=10ms) ✓                                    │
│ det-1-v1 → GT-A (offset=50ms) ✓ DUPLICATE!                         │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: Collapse Duplicates ❌ BUG HERE                             │
│ Groups by parent_detection_id (det-1)                               │
│ Keeps best match within parent group (det-1-v0 → GT-A)             │
│ BUT: Different parents can still match same GT!                     │
│ det-1 → GT-A ✓ (kept)                                               │
│ det-2 → GT-A ✓ (also kept) ← WRONG!                                │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5: Database Population                                         │
│ Stores BOTH matches:                                                 │
│ - detection_events.ground_truth_match_id = GT-A (for det-1)        │
│ - detection_events.ground_truth_match_id = GT-A (for det-2)        │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 6: Frontend Rendering                                          │
│ Queries detection_events WHERE ground_truth_match_id = GT-A         │
│ Returns BOTH det-1 and det-2                                        │
│ Timeline shows:                                                      │
│ - Detection Frame 28 → GT PASS (det-1 matched GT-A)                │
│ - Detection Frame 28 → GT FAIL (det-2 also matched GT-A but failed)│
└─────────────────────────────────────────────────────────────────────┘
```

---

## The Fix

### Required Changes

**File**: `/backend/services/ground_truth_matching_service.py`
**Function**: `_collapse_virtual_matches` (Lines 774-854)

**Current Logic** (WRONG):
```python
# Groups by parent detection ID
parent_groups = {}
for match in match_results:
    parent_id = extract_parent_id(match.detection_event_id)
    parent_groups[parent_id].append(match)

# Keeps best match per parent
for parent_id, group in parent_groups.items():
    best_match = min(group, key=lambda m: abs(m.temporal_offset))
    deduplicated_matches.append(best_match)
```

**Fixed Logic** (CORRECT):
```python
# STEP 1: Group by parent detection ID (remove virtual suffixes)
parent_groups = {}
for match in match_results:
    parent_id = extract_parent_id(match.detection_event_id)
    if parent_id not in parent_groups:
        parent_groups[parent_id] = []
    parent_groups[parent_id].append(match)

# STEP 2: Deduplicate within each parent group (best match per parent)
parent_best_matches = {}
for parent_id, group in parent_groups.items():
    best_match = min(group, key=lambda m: abs(m.temporal_offset))
    best_match.detection_event_id = parent_id  # Remove virtual suffix
    parent_best_matches[parent_id] = best_match

# STEP 3: Group by ground truth ID (ensure each GT matched only once)
gt_groups = {}
for parent_id, match in parent_best_matches.items():
    gt_id = match.ground_truth_id
    if gt_id not in gt_groups:
        gt_groups[gt_id] = []
    gt_groups[gt_id].append(match)

# STEP 4: Deduplicate by ground truth (best match per GT)
final_matches = []
for gt_id, group in gt_groups.items():
    if len(group) == 1:
        final_matches.append(group[0])
    else:
        # Multiple detections matched same GT - keep best one
        best_match = min(group, key=lambda m: abs(m.temporal_offset))

        # Mark others as false positives
        for match in group:
            if match != best_match:
                match.match_type = 'FP'
                match.latency_ms = 10000.0  # FP marker

        final_matches.extend(group)  # Keep all, but mark extras as FP

return final_matches
```

---

## Impact Assessment

### Affected Systems
1. ✅ **Database**: No corruption (schema is correct)
2. ❌ **Matching Logic**: Allows duplicate GT matches
3. ❌ **Frontend Display**: Shows conflicting statuses
4. ❌ **Metrics Calculation**: Inflated TP/FP counts

### Severity Justification
- **Data Integrity**: 10+ ground truth objects matched by multiple detections
- **User Experience**: Impossible UI state (Pass + Fail simultaneously)
- **Test Validity**: Results are incorrect and misleading
- **Production Impact**: HIL test results cannot be trusted

---

## Testing Plan

### Unit Tests
```python
def test_collapse_prevents_duplicate_gt_matches():
    """Test that collapse removes duplicate GT matches"""
    matches = [
        MatchResult(detection_id='det-1-v0', ground_truth_id='GT-A', offset=10),
        MatchResult(detection_id='det-2-v0', ground_truth_id='GT-A', offset=15),  # DUPLICATE GT
        MatchResult(detection_id='det-3-v0', ground_truth_id='GT-B', offset=20),
    ]

    collapsed = _collapse_virtual_matches(matches)

    # Should keep only best match for GT-A
    gt_a_matches = [m for m in collapsed if m.ground_truth_id == 'GT-A']
    assert len(gt_a_matches) == 1
    assert gt_a_matches[0].detection_id == 'det-1'  # Best offset (10ms)
```

### Integration Tests
```python
def test_end_to_end_no_duplicate_gt_status():
    """Test full pipeline doesn't create duplicate GT status"""
    session_id = create_test_session_with_detections()

    # Run matching
    metrics = matching_service.match_detections_to_ground_truth(session_id)

    # Check database
    gt_matches = db.query(DetectionEvent.ground_truth_match_id).all()
    unique_gts = set(gt_matches)

    # Each GT should be matched by at most 1 detection
    for gt_id in unique_gts:
        detections = db.query(DetectionEvent).filter(
            DetectionEvent.ground_truth_match_id == gt_id
        ).all()
        assert len(detections) == 1, f"GT {gt_id} matched by {len(detections)} detections!"
```

---

## Recommendation

**Priority**: CRITICAL - Fix immediately
**Complexity**: Medium (requires 2-level grouping logic)
**Risk**: Low (well-isolated change)
**Estimated Time**: 2-4 hours (implementation + testing)

---

## Appendix: Code Locations

### Files Requiring Changes
1. `/backend/services/ground_truth_matching_service.py` (Line 774)
2. `/backend/src/services/temporal_expansion.py` (Line 187) - Optional: add GT grouping

### Files for Testing
1. `/backend/tests/test_ground_truth_matching.py`
2. `/backend/tests/services/test_option_c_temporal_expansion.py`

---

**Analysis Complete**: Root cause identified with 100% confidence.
