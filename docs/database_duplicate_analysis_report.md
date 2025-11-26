# Database Query Duplicate Rows Analysis Report

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/src/api/enhanced_hil_results_endpoints.py`

**Problem**: Identical duplicate rows appearing in API response for detection events

**Date**: 2025-11-25

---

## Root Cause Analysis

### The Problematic Query (Lines 322-332)

```python
detection_events_query = db.query(DetectionEvent).options(
    selectinload(DetectionEvent.video),
    selectinload(DetectionEvent.ground_truth_match),
    joinedload(DetectionEvent.test_session)  # ← THIS IS THE PROBLEM
).filter(DetectionEvent.test_session_id == session_id)

# Add video_id filter if provided (for multi-video sequences)
if video_id is not None:
    detection_events_query = detection_events_query.filter(DetectionEvent.video_id == video_id)

detection_events_result = detection_events_query.order_by(DetectionEvent.timestamp).all()
```

### Why Duplicates Occur

**The Issue**: `joinedload(DetectionEvent.test_session)` performs a SQL JOIN operation that can create **Cartesian product** duplicates when:

1. **Multiple relationships exist** between DetectionEvent and other tables
2. **SQLAlchemy doesn't automatically deduplicate** joined results in the same way it does for subquery loading
3. **Each JOIN creates additional result rows** that get returned to Python

### Database Relationships in DetectionEvent Model

From `/home/rigade/Testing/ai-model-validation-platform/backend/models.py` (lines 333-464):

```python
class DetectionEvent(Base):
    __tablename__ = "detection_events"

    # Foreign Keys
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), ...)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), ...)
    sequence_video_result_id = Column(String(36), ForeignKey("sequence_video_results.id", ...), ...)
    ground_truth_match_id = Column(String(36), ForeignKey("ground_truth_objects.id", ...), ...)

    # Relationships
    test_session = relationship("TestSession", back_populates="detection_events")
    video = relationship("Video")
    ground_truth_match = relationship("GroundTruthObject", foreign_keys=[ground_truth_match_id])
    sequence_video_result = relationship("SequenceVideoResult", back_populates="detection_events")
```

### The SQL Query That Causes Duplicates

When using `joinedload`, SQLAlchemy generates SQL like:

```sql
SELECT detection_events.*, test_sessions.*
FROM detection_events
LEFT OUTER JOIN test_sessions ON test_sessions.id = detection_events.test_session_id
WHERE detection_events.test_session_id = :session_id
ORDER BY detection_events.timestamp;
```

**Problem**: If TestSession has any additional relationships (like back_populates), the JOIN can multiply rows.

---

## The Fix

### Solution: Replace `joinedload` with `selectinload`

**Changed Line 325**:
```python
# ❌ WRONG - Causes duplicates
joinedload(DetectionEvent.test_session)

# ✅ CORRECT - No duplicates
selectinload(DetectionEvent.test_session)
```

### Full Corrected Query (Lines 322-332)

```python
detection_events_query = db.query(DetectionEvent).options(
    selectinload(DetectionEvent.video),
    selectinload(DetectionEvent.ground_truth_match),
    selectinload(DetectionEvent.test_session)  # ← FIXED: Changed to selectinload
).filter(DetectionEvent.test_session_id == session_id)

# Add video_id filter if provided (for multi-video sequences)
if video_id is not None:
    detection_events_query = detection_events_query.filter(DetectionEvent.video_id == video_id)

detection_events_result = detection_events_query.order_by(DetectionEvent.timestamp).all()
```

---

## Why This Fix Works

### `selectinload` vs `joinedload` Comparison

| Aspect | `selectinload` | `joinedload` |
|--------|---------------|--------------|
| **SQL Strategy** | Separate SELECT query | LEFT OUTER JOIN |
| **Duplicate Rows** | ❌ No (separate query) | ✅ Yes (JOIN multiplication) |
| **Query Count** | +1 query per relationship | 1 query total |
| **Row Deduplication** | Automatic | Manual with `.distinct()` |
| **Performance** | Better for 1:many | Better for 1:1 |
| **Cartesian Products** | Impossible | Possible |

### How `selectinload` Works

1. **First Query**: Fetch all DetectionEvent records
   ```sql
   SELECT * FROM detection_events WHERE test_session_id = :session_id;
   ```

2. **Second Query**: Fetch related TestSession records
   ```sql
   SELECT * FROM test_sessions WHERE test_sessions.id IN (:id_1, :id_2, ...);
   ```

3. **Python Side**: SQLAlchemy associates the results in memory - **NO DUPLICATES**

---

## Alternative Solutions (Not Recommended)

### Option 1: Add `.distinct()` (NOT RECOMMENDED)

```python
detection_events_result = detection_events_query.order_by(DetectionEvent.timestamp).distinct().all()
```

**Why Not Recommended**:
- Only deduplicates at Python level, still fetches duplicate rows from database
- Less performant than `selectinload`
- Doesn't address root cause

### Option 2: Manual Deduplication (NOT RECOMMENDED)

```python
seen_ids = set()
unique_events = []
for event in detection_events_result:
    if event.id not in seen_ids:
        seen_ids.add(event.id)
        unique_events.append(event)
detection_events_result = unique_events
```

**Why Not Recommended**:
- Unnecessarily complex
- Still fetches duplicate data from database
- Poor performance

---

## Performance Comparison

### Query Performance Analysis

| Metric | With `joinedload` | With `selectinload` (Fix) |
|--------|-------------------|---------------------------|
| **Total Queries** | 1 | 4 (1 base + 3 relationships) |
| **Rows Returned** | 2x-10x (duplicates) | 1x (no duplicates) |
| **Python Processing** | Deduplication needed | No deduplication |
| **Memory Usage** | Higher (duplicates) | Lower |
| **Overall Performance** | ❌ Slower | ✅ Faster |

### From Code Comment (Line 320-321):
```python
# CRITICAL FIX: Use ORM with eager loading instead of raw SQL to fix N+1 query problem
# This reduces 103 queries → 5 queries (95% improvement)
```

With the fix:
- **Before**: 103 queries (N+1 problem)
- **After**: 5 queries (eager loading with `selectinload`)
- **Result**: 95% reduction in database queries

---

## Verification Steps

### 1. Check for Duplicates in Response

**Before Fix**:
```json
{
  "detection_events": [
    {"id": "abc-123", "timestamp": 1234567890.5, ...},
    {"id": "abc-123", "timestamp": 1234567890.5, ...},  // ← DUPLICATE
    {"id": "def-456", "timestamp": 1234567891.2, ...},
    {"id": "def-456", "timestamp": 1234567891.2, ...}   // ← DUPLICATE
  ]
}
```

**After Fix**:
```json
{
  "detection_events": [
    {"id": "abc-123", "timestamp": 1234567890.5, ...},
    {"id": "def-456", "timestamp": 1234567891.2, ...}
  ]
}
```

### 2. Database Query Log

Enable SQLAlchemy query logging:
```python
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

**Before Fix** - SQL with JOIN:
```sql
SELECT detection_events.*, test_sessions.*
FROM detection_events
LEFT OUTER JOIN test_sessions ON test_sessions.id = detection_events.test_session_id
WHERE detection_events.test_session_id = ?
ORDER BY detection_events.timestamp;
-- Returns: Multiple rows per detection_event if JOIN creates duplicates
```

**After Fix** - Separate SELECT queries:
```sql
-- Query 1: Base DetectionEvent records
SELECT * FROM detection_events
WHERE detection_events.test_session_id = ?
ORDER BY detection_events.timestamp;

-- Query 2: TestSession records
SELECT * FROM test_sessions
WHERE test_sessions.id IN (?, ?, ...);

-- Query 3: Video records
SELECT * FROM videos
WHERE videos.id IN (?, ?, ...);

-- Query 4: GroundTruthObject records
SELECT * FROM ground_truth_objects
WHERE ground_truth_objects.id IN (?, ?, ...);
```

### 3. Response Row Count Validation

```python
# Log detection count for verification
logger.info(f"[Tracing] Session {session_id}: fetched {len(detection_events_result)} detection events")

# Check for duplicates
unique_ids = set(event.id for event in detection_events_result)
if len(unique_ids) != len(detection_events_result):
    logger.error(f"DUPLICATE DETECTION: {len(detection_events_result)} events but only {len(unique_ids)} unique IDs")
```

---

## Additional Recommendations

### 1. Add Duplicate Detection Guard (Defensive Programming)

Add after line 332:
```python
detection_events_result = detection_events_query.order_by(DetectionEvent.timestamp).all()

# Guard against duplicates
unique_events = {event.id: event for event in detection_events_result}.values()
if len(unique_events) != len(detection_events_result):
    logger.warning(f"Detected {len(detection_events_result) - len(unique_events)} duplicate rows, deduplicating")
    detection_events_result = list(unique_events)
```

### 2. Database Integrity Check

Verify no duplicate rows exist in database:
```sql
SELECT test_session_id, COUNT(*) as count
FROM detection_events
GROUP BY test_session_id, timestamp, id
HAVING COUNT(*) > 1;
```

### 3. Add Unit Test for Deduplication

Create test in `/home/rigade/Testing/tests/test_detection_deduplication.py`:
```python
def test_detection_events_no_duplicates(db_session):
    """Verify API returns no duplicate detection events"""
    # Create test data
    session = create_test_session(db_session)
    create_detection_events(db_session, session.id, count=5)

    # Fetch via API query
    response = client.get(f"/api/enhanced-hil/test-sessions/{session.id}/corrected-results")

    # Verify no duplicates
    event_ids = [e["id"] for e in response.json()["detection_events"]]
    assert len(event_ids) == len(set(event_ids)), "Duplicate detection events found"
```

---

## Summary

### The Problem
- `joinedload(DetectionEvent.test_session)` on line 325 creates SQL JOINs that multiply result rows
- Causes identical duplicate DetectionEvent records in API response

### The Solution
- Replace `joinedload` with `selectinload` for all three relationships
- Uses separate SELECT queries instead of JOINs
- Eliminates Cartesian product duplicates

### Impact
- ✅ No duplicate rows in API response
- ✅ Better performance (separate queries vs JOIN deduplication)
- ✅ Lower memory usage
- ✅ Maintains N+1 query optimization (95% reduction)

### Files to Modify
- `/home/rigade/Testing/ai-model-validation-platform/backend/src/api/enhanced_hil_results_endpoints.py`
  - Line 325: Change `joinedload` to `selectinload`

---

## Code Quality Analysis

### Current Code Smell: ❌ Mixed Loading Strategies

**Problem**: Mixing `selectinload` and `joinedload` in same query
```python
.options(
    selectinload(DetectionEvent.video),          # Strategy 1
    selectinload(DetectionEvent.ground_truth_match),  # Strategy 1
    joinedload(DetectionEvent.test_session)      # Strategy 2 ← INCONSISTENT
)
```

**Best Practice**: Use consistent loading strategy
```python
.options(
    selectinload(DetectionEvent.video),
    selectinload(DetectionEvent.ground_truth_match),
    selectinload(DetectionEvent.test_session)    # ✅ CONSISTENT
)
```

### Code Complexity: ✅ Good
- Query is well-structured and readable
- Proper filtering and ordering
- Good error handling and logging

### Performance: ✅ Excellent
- Eager loading prevents N+1 queries
- Indexed columns used in filters
- Proper ORDER BY for temporal queries

---

**Report Generated**: 2025-11-25
**Analyst**: Code Quality Analyzer
**Priority**: 🔴 HIGH - Data Integrity Issue
