# Root Cause Analysis: Identical Duplicate Detection Entries in UI

## Problem Statement

Identical duplicate detection entries appear in the UI:

```
Frame 64 (2.667s): aligned -9.4ms, real 0ms, 4.24V → GT PASS
Frame 64 (2.667s): aligned -9.4ms, real 0ms, 4.24V → GT PASS  ← EXACT DUPLICATE

Frame 67 (2.792s): aligned 13.7ms, real 0ms, 4.28V → GT PASS
Frame 67 (2.792s): aligned 13.7ms, real 0ms, 4.28V → GT PASS  ← EXACT DUPLICATE
```

These are 100% identical entries with the same:
- Frame number
- Timestamps
- Latency values
- Voltage levels
- Pass/fail status

## Root Cause: SQLAlchemy `joinedload()` Cartesian Product

### Location
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/src/api/enhanced_hil_results_endpoints.py`
**Lines**: 322-332

### The Problematic Code

```python
# Line 322-326
detection_events_query = db.query(DetectionEvent).options(
    selectinload(DetectionEvent.video),
    selectinload(DetectionEvent.ground_truth_match),
    joinedload(DetectionEvent.test_session)  # ← THIS CAUSES DUPLICATES!
).filter(DetectionEvent.test_session_id == session_id)

# Line 332
detection_events_result = detection_events_query.order_by(DetectionEvent.timestamp).all()
```

### Why This Happens

**SQLAlchemy `joinedload()` Issue**:
- `joinedload()` performs a `LEFT OUTER JOIN` with the related table
- When there are multiple related records (or even just one), the JOIN creates duplicate rows
- This is a **known SQLAlchemy behavior** documented since version 1.4+

**Example**:
If you have:
- 1 DetectionEvent (Frame 64)
- 1 TestSession related to it

The `LEFT OUTER JOIN` produces:
```
DetectionEvent.id | DetectionEvent.frame | TestSession.id | TestSession.name
1                 | 64                   | 100            | Test 1
1                 | 64                   | 100            | Test 1  ← DUPLICATE ROW FROM JOIN
```

SQLAlchemy returns BOTH rows as separate DetectionEvent objects!

### Why `selectinload()` Doesn't Cause Duplicates

- `selectinload()` uses a separate SELECT query (not a JOIN)
- No cartesian product possible
- Always returns unique rows

## Data Flow Analysis

### 1. Database Query (Line 332)
```python
detection_events_result = detection_events_query.order_by(DetectionEvent.timestamp).all()
# ❌ Returns: [Event1, Event1_duplicate, Event2, Event2_duplicate, ...]
```

### 2. Timing Calculator (Line 818)
```python
corrected_results = timing_calculator.calculate_batch_corrected_latencies(
    detection_events=detection_events,  # Receives duplicates
    ...
)
# ❌ Processes duplicates, returns duplicate corrected results
```

### 3. Building Response (Line 944)
```python
for i, (original_event, corrected_result) in enumerate(zip(detection_events_result, corrected_results)):
    enhanced_detection_events.append({...})
# ❌ Zips duplicates together, creates duplicate response entries
```

### 4. UI Display
```
Frame 64 appears twice because the backend sent it twice!
```

## Evidence

1. **Identical data in duplicates**: Frame number, timestamps, latency, voltage are 100% identical
2. **Consistent pattern**: Every detection appears exactly twice
3. **Query pattern**: Using `joinedload()` which is known to cause this issue
4. **No deduplication**: No `.unique()` call on query result

## The Fix

### Option 1: Add `.unique()` to Query (Recommended)

**File**: `backend/src/api/enhanced_hil_results_endpoints.py`
**Line**: 332

```python
# BEFORE (❌ Duplicates)
detection_events_result = detection_events_query.order_by(DetectionEvent.timestamp).all()

# AFTER (✅ No Duplicates)
detection_events_result = detection_events_query.order_by(DetectionEvent.timestamp).unique().all()
```

### Option 2: Replace `joinedload()` with `selectinload()`

```python
# BEFORE (❌ Duplicates)
detection_events_query = db.query(DetectionEvent).options(
    selectinload(DetectionEvent.video),
    selectinload(DetectionEvent.ground_truth_match),
    joinedload(DetectionEvent.test_session)  # ← JOIN causes duplicates
)

# AFTER (✅ No Duplicates)
detection_events_query = db.query(DetectionEvent).options(
    selectinload(DetectionEvent.video),
    selectinload(DetectionEvent.ground_truth_match),
    selectinload(DetectionEvent.test_session)  # ← SELECT, no duplicates
)
```

### Option 3: Manual Deduplication (Not Recommended)

```python
# Less efficient, but works
seen_ids = set()
detection_events_result = []
for event in detection_events_query.order_by(DetectionEvent.timestamp).all():
    if event.id not in seen_ids:
        seen_ids.add(event.id)
        detection_events_result.append(event)
```

## Impact

### Before Fix
- **UI**: Shows each detection twice
- **Statistics**: Inflated counts (10 detections appear as 20)
- **User Confusion**: "Why is everything duplicated?"

### After Fix
- **UI**: Shows each detection once
- **Statistics**: Accurate counts
- **Performance**: Slightly better (less data to process)

## Testing Verification

After applying the fix, verify:

```bash
# Check database for duplicates (should be none)
SELECT frame_number, COUNT(*) as cnt
FROM detection_events
WHERE test_session_id = 'YOUR_SESSION_ID'
GROUP BY frame_number
HAVING COUNT(*) > 1;

# Expected result: Empty (no duplicates)
```

## SQLAlchemy Documentation References

- [SQLAlchemy 1.4 ORM Querying Guide](https://docs.sqlalchemy.org/en/14/orm/loading_relationships.html#joined-eager-loading)
- [Why joinedload() returns duplicates](https://docs.sqlalchemy.org/en/14/orm/loading_relationships.html#the-importance-of-ordering)
- [Using unique() with joinedload()](https://docs.sqlalchemy.org/en/14/orm/query.html#sqlalchemy.orm.Query.unique)

## Summary

**Root Cause**: `joinedload(DetectionEvent.test_session)` creates duplicate rows via LEFT OUTER JOIN

**Exact Line**: `backend/src/api/enhanced_hil_results_endpoints.py:332`

**Fix**: Add `.unique()` before `.all()`:
```python
detection_events_result = detection_events_query.order_by(DetectionEvent.timestamp).unique().all()
```

**Why It Works**: `.unique()` deduplicates ORM objects by identity, removing JOIN-induced duplicates

**Files to Change**:
1. `backend/src/api/enhanced_hil_results_endpoints.py` (line 332)
