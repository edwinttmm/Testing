# CRITICAL FINDING: Ground Truth Table Missing

**Date**: 2025-11-21
**Severity**: CRITICAL - BLOCKS ALL HIL TESTING

## Executive Summary

The `ground_truth_events` table **DOES NOT EXIST** in the database. This explains why test session `e8e108b0-cb20-4cba-a2db-fc29f21efd16` has 0 ground truth events.

**Impact**: ALL HIL tests will report 0% accuracy because there's no ground truth to compare against.

---

## Evidence

### Database Query Result:
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: ground_truth_events
```

### Test Session Data:
```
Session ID: e8e108b0-cb20-4cba-a2db-fc29f21efd16
Status: completed
Detections: 334 (167 from each duplicate source)
Ground Truth Events: ERROR - table does not exist
```

---

## Root Cause Analysis

### What the Code Expects:
The ground truth matching service queries `ground_truth_events` table:

**File**: `/backend/services/ground_truth_matching_service.py`
```python
ground_truth_events = session.query(GroundTruthEvent).filter(
    GroundTruthEvent.test_session_id == test_session_id
).all()
```

### What Actually Exists:
The database **does not have** a `ground_truth_events` table. The code is trying to query a non-existent table.

---

## Two Possible Scenarios

### Scenario A: Table Never Created (Missing Migration)
- The Alembic migration to create `ground_truth_events` table was never run
- Database schema is incomplete
- **Fix**: Run missing migration or create table manually

### Scenario B: Different Table Name (Architecture Change)
- Ground truth may be stored in a different table (e.g., `video_events`, `ground_truth_objects`)
- Code and database are out of sync
- **Fix**: Update code to query correct table OR create expected table

---

## Immediate Actions Required

### Option 1: Create Missing Table (Recommended)

```sql
CREATE TABLE IF NOT EXISTS ground_truth_events (
    id VARCHAR(36) PRIMARY KEY,
    test_session_id VARCHAR(36) NOT NULL,
    video_id VARCHAR(36),
    timestamp FLOAT NOT NULL,
    event_type VARCHAR(50),
    object_class VARCHAR(50),
    confidence FLOAT,
    bounding_box_x FLOAT,
    bounding_box_y FLOAT,
    bounding_box_width FLOAT,
    bounding_box_height FLOAT,
    metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (test_session_id) REFERENCES test_sessions(id) ON DELETE CASCADE
);

CREATE INDEX idx_gt_events_session ON ground_truth_events(test_session_id);
CREATE INDEX idx_gt_events_timestamp ON ground_truth_events(timestamp);
CREATE INDEX idx_gt_events_video ON ground_truth_events(video_id);
```

### Option 2: Find Alternative Ground Truth Storage

Check these potential tables:
```sql
-- Check for video_events
SELECT COUNT(*) FROM video_events WHERE video_id = '[your_video_id]';

-- Check for ground_truth_objects
SELECT COUNT(*) FROM ground_truth_objects WHERE test_session_id = '[session_id]';

-- Check for validation_events
SELECT COUNT(*) FROM validation_events WHERE test_session_id = '[session_id]';
```

If ground truth exists in another table, update the matching service to query that table instead.

---

## Investigation Steps

### 1. List All Tables

Run database query to see what tables exist:
```bash
source venv/bin/activate
python -c "
from sqlalchemy import create_engine, text
from config_settings import Settings

engine = create_engine(Settings().database_url)
with engine.connect() as conn:
    tables = conn.execute(text('SELECT name FROM sqlite_master WHERE type=\"table\" ORDER BY name')).fetchall()
    print('All tables:')
    for t in tables:
        print(f'  - {t[0]}')
"
```

### 2. Check Alembic Migrations

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
ls -la alembic/versions/
```

Look for migration creating `ground_truth_events` table.

### 3. Check SQLAlchemy Models

```bash
grep -r "class.*GroundTruth" models.py
```

Verify if `GroundTruthEvent` model exists and what table it expects.

---

## Impact Assessment

### Current State:
- ❌ **0% accuracy** - no ground truth to compare
- ❌ **All detections marked as false positives**
- ❌ **HIL testing completely blocked**
- ❌ **Production deployment impossible**

### After Fix:
- ✅ Ground truth can be imported
- ✅ Detections can be matched against GT
- ✅ Accurate F1/Precision/Recall metrics
- ✅ HIL testing functional

---

## Recommended Fix Path

**PRIORITY 0 - CRITICAL BLOCKER**

1. **Identify ground truth storage strategy** (5 minutes)
   - Check if table exists with different name
   - Check SQLAlchemy models for expected table
   - Review migration files

2. **Create missing table** (10 minutes)
   - Run SQL CREATE TABLE statement
   - Add indexes for performance
   - Verify table exists

3. **Import ground truth data** (15 minutes)
   - Locate GT CSV/JSON files
   - Run GT import API or script
   - Verify data inserted correctly

4. **Rerun matching** (5 minutes)
   - Re-execute matching algorithm
   - Verify metrics calculated correctly
   - Check F1/Precision/Recall values

**Total Time**: ~35 minutes to unblock HIL testing

---

## Prevention

To prevent this in the future:

1. **Database Schema Validation**: Add startup check verifying all required tables exist
2. **Alembic Migration Verification**: Run `alembic current` to check migration status
3. **Integration Tests**: Test that queries all required tables before allowing tests
4. **Documentation**: Document required database schema in README

---

## Related Issues

This missing table may be related to:
1. Broken Alembic migration chain (we saw `KeyError: 'add_video_id_to_detection_events'` earlier)
2. Database initialized from incomplete schema
3. Migration files not run in correct order

**Recommendation**: After fixing ground truth table, audit ALL database tables against expected schema.

---

## Next Steps

**User Action Required**:

1. Run investigation steps above to identify where ground truth SHOULD be stored
2. Create `ground_truth_events` table (use SQL above)
3. Import ground truth data for test video
4. Re-run matching algorithm
5. Verify metrics are now calculated correctly

**Expected Outcome After Fix**:
- Ground truth events: >0 (actual GT count for video)
- F1 score: 0.65-0.85 (realistic accuracy)
- Precision: 0.70-0.90 (few false positives after duplicate fix)
- Recall: 0.60-0.80 (most GT events detected)

---

## Contact

This is a **CRITICAL BLOCKER** for HIL testing. Fix this before attempting any other improvements.
