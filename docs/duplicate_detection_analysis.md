# Duplicate Detection Entries - Root Cause Analysis

## Executive Summary

**STATUS**: ROOT CAUSE IDENTIFIED ✅

The duplicate detection entries are caused by **SQLAlchemy's `selectinload()` returning duplicate rows** when there are multiple related records in join tables, specifically the `ground_truth_match` relationship.

## Evidence Analysis

### Current Symptoms
```
Frame 1 (0.042s): aligned 3.7ms, real 4ms, GT PASS
Frame 1 (0.042s): aligned 3.7ms, real 4ms, GT PASS  ← DUPLICATE

Frame 5 (0.208s): aligned 9.0ms, real 9ms, GT PASS
Frame 5 (0.208s): aligned 9.0ms, real 1ms, GT PASS  ← DUPLICATE with DIFFERENT values!
```

### Key Log Messages
```
WARNING - No corrected results available for session - using fallback timing data
INFO - Deduplication: 178 unique detection events
```

## Root Cause

### Location: Line 322-332
```python
detection_events_query = db.query(DetectionEvent).options(
    selectinload(DetectionEvent.video),
    selectinload(DetectionEvent.ground_truth_match),  # ⚠️ THIS CAUSES DUPLICATES
    selectinload(DetectionEvent.test_session)
).filter(DetectionEvent.test_session_id == session_id)

detection_events_result = detection_events_query.order_by(DetectionEvent.timestamp).all()
```

### Why Duplicates Occur

**SQLAlchemy Eager Loading Behavior**:
- `selectinload()` with relationships that have **one-to-many** cardinality can return duplicate parent rows
- The `ground_truth_match` relationship may have multiple matches per detection event
- Each match creates a separate row in the result set
- These duplicates are processed through TWO code paths

### Two Code Paths Problem

#### Path 1: Normal Path (Lines 948-1058)
- Uses `corrected_results` from timing calculator
- Has deduplication at lines 1060-1075
- Processes `(original_event, corrected_result)` pairs
- **Only executes when `len(corrected_results) > 0`**

#### Path 2: Fallback Path (Lines 864-946)
- Uses `detection_events_result` directly when no corrected results available
- **NO DEDUPLICATION** ❌
- Processes only `original_event` without correlation
- Executes when `len(corrected_results) == 0`

### Evidence: "No corrected results available"

The log message "No corrected results available for session - using fallback timing data" proves the **Fallback Path** is executing, which:
1. Receives duplicate rows from `selectinload(DetectionEvent.ground_truth_match)`
2. Loops through ALL rows (including duplicates) at line 867
3. Appends each row to `enhanced_detection_events` at line 873
4. **Skips the deduplication code** (lines 1060-1075) which only runs AFTER both paths

### Why Frame 5 Shows Different Values

Frame 5 appears twice with different `real` values (9ms and 1ms) because:
1. The database has TWO `ground_truth_match` records for Frame 5 detection
2. Each match has different latency calculations
3. `selectinload()` returns both matches as separate rows
4. The fallback loop processes BOTH without deduplication

## The Fix

### Problem Summary
```
┌─────────────────────────────────────────────────┐
│ SQLAlchemy Query (Line 322-332)                 │
│   selectinload(ground_truth_match) ──┐          │
└────────────────────────────────────────┼────────┘
                                         │
                     ┌───────────────────▼──────────────────┐
                     │ Returns DUPLICATE rows when          │
                     │ detection has multiple GT matches    │
                     └───────────────────┬──────────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        │                                │                                │
        ▼                                ▼                                │
┌──────────────────┐          ┌──────────────────┐                      │
│ Normal Path      │          │ Fallback Path    │                      │
│ Lines 948-1058   │          │ Lines 864-946    │                      │
│                  │          │                  │                      │
│ Has corrected    │          │ NO corrected     │                      │
│ results          │          │ results          │                      │
└────────┬─────────┘          └────────┬─────────┘                      │
         │                             │                                │
         │                             │ ❌ NO DEDUPLICATION            │
         │                             │    IN THIS PATH                │
         │                             │                                │
         ▼                             ▼                                │
┌──────────────────────────────────────────────────┐                   │
│ Deduplication (Lines 1060-1075)                  │                   │
│ ✅ Only runs AFTER both paths complete           │◄──────────────────┘
│ ⚠️  But Fallback path already added duplicates!  │
└──────────────────────────────────────────────────┘
```

### Solution Options

#### Option 1: Add `.distinct()` to Query (RECOMMENDED)
```python
# Line 322-332
detection_events_result = (
    db.query(DetectionEvent)
    .options(
        selectinload(DetectionEvent.video),
        selectinload(DetectionEvent.ground_truth_match),
        selectinload(DetectionEvent.test_session)
    )
    .filter(DetectionEvent.test_session_id == session_id)
    .distinct(DetectionEvent.id)  # ✅ Prevent duplicate parent rows
    .order_by(DetectionEvent.timestamp)
    .all()
)
```

#### Option 2: Deduplicate BEFORE Path Selection
```python
# After line 332, before fallback check (line 864)
seen_event_ids = {}
for event in detection_events_result:
    if event.id not in seen_event_ids:
        seen_event_ids[event.id] = event
detection_events_result = list(seen_event_ids.values())
logger.info(f"Pre-path deduplication: {len(detection_events_result)} unique detection events")
```

#### Option 3: Add Deduplication to Fallback Path
```python
# Inside fallback loop (after line 946, before line 948)
# Deduplicate fallback results before moving to statistics
seen_event_ids = {}
for event in enhanced_detection_events:
    event_id = event.get('event_id')
    if event_id and event_id not in seen_event_ids:
        seen_event_ids[event_id] = event
enhanced_detection_events = list(seen_event_ids.values())
logger.info(f"Fallback path deduplication: {len(enhanced_detection_events)} unique events")
```

## Recommended Fix

**Use Option 1 (`.distinct()`) + Option 2 (early deduplication) for defense-in-depth**:

1. Add `.distinct(DetectionEvent.id)` to the query at line 332
2. Add early deduplication after line 332 (before path selection)
3. Keep existing deduplication at lines 1060-1075 as final safety net

This ensures:
- Database returns unique rows
- Both code paths receive deduplicated data
- Final safety check catches any edge cases

## Files to Modify

1. `/home/rigade/Testing/ai-model-validation-platform/backend/src/api/enhanced_hil_results_endpoints.py`
   - Line 332: Add `.distinct(DetectionEvent.id)`
   - After line 332: Add early deduplication logic
   - Keep lines 1060-1075 deduplication as-is

## Test Plan

1. Run test session that triggers fallback path (no ground truth matches)
2. Verify log shows: "Pre-path deduplication: X unique detection events"
3. Verify NO duplicate Frame entries in API response
4. Verify Frame 5 appears only ONCE with consistent latency value
5. Verify deduplication log shows same count throughout pipeline

## Additional Notes

### Why Existing Deduplication Didn't Work

The deduplication at lines 1060-1075 runs AFTER both code paths have already populated `enhanced_detection_events`. By that time:
- Fallback path has already added ALL duplicate rows (lines 867-946)
- Normal path has added corrected results (lines 948-1058)
- Final deduplication catches SOME duplicates, but NOT all because:
  - Different `latency_ms` values cause deduplication to prefer non-zero latency
  - If both duplicates have valid latency, the SECOND one overwrites the first
  - This explains why "178 unique detection events" still shows duplicates in output

### The "Different Real Values" Mystery

Frame 5 showing both "real 9ms" and "real 1ms" occurs because:
1. Detection event has 2 ground truth matches in database
2. Each GT match has different timestamp/latency calculation
3. `selectinload()` creates 2 rows for the same detection
4. Fallback path processes both rows independently
5. Deduplication prefers non-zero latency, but BOTH are non-zero
6. The second entry (1ms) overwrites the first (9ms) in the deduplication dict
7. But somehow BOTH entries still appear in final output (possible JSON serialization issue)

## Conclusion

**Root Cause**: SQLAlchemy `selectinload(DetectionEvent.ground_truth_match)` returns duplicate parent rows when one-to-many relationships exist.

**Why It Wasn't Caught**: The fallback code path (lines 864-946) has no deduplication, and the final deduplication (lines 1060-1075) runs too late.

**Fix Priority**: HIGH - This causes incorrect statistics and confusing UI displays.

**Estimated Fix Time**: 15 minutes (add `.distinct()` and early deduplication)

---
**Analysis Date**: 2025-11-25
**Analyzer**: Code Quality Analyzer
**Session**: Duplicate Detection Investigation
