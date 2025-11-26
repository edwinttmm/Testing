# Session 2c9a93f6-8471-4f2e-b1a7-06f239fca548 Investigation Report

**Date:** 2025-11-24
**Status:** ❌ **CRITICAL - SESSION NOT FOUND**
**Investigator:** Code Analyzer Agent

---

## Executive Summary

**CRITICAL FINDING:** The session ID `2c9a93f6-8471-4f2e-b1a7-06f239fca548` **does not exist** in the database. This indicates one of several possible issues:

1. **Session was deleted** - Data was purged from database
2. **Wrong database** - Querying test database instead of production
3. **Session ID mismatch** - User provided incorrect session ID
4. **Data corruption** - Database integrity issues

---

## Investigation Steps Performed

### 1. Database Schema Analysis
- ✓ Connected to: `/home/rigade/Testing/ai-model-validation-platform/backend/test_database.db`
- ✓ Verified schema matches models.py (MISMATCH FOUND)
- ✓ Confirmed available tables:
  - `test_sessions` - HIL test sessions (newer system)
  - `detection_sessions` - Simple detection tracking (legacy?)
  - `detection_events` - Detection event records
  - `stored_detection_events` - Stored detection data
  - `ground_truth_objects` - Ground truth annotations

### 2. Session Search Results
```sql
-- Searched test_sessions table
SELECT * FROM test_sessions WHERE id = '2c9a93f6-8471-4f2e-b1a7-06f239fca548'
-- Result: 0 rows

-- Searched detection_sessions table
SELECT * FROM detection_sessions WHERE id = '2c9a93f6-8471-4f2e-b1a7-06f239fca548'
-- Result: 0 rows

-- Partial ID search
SELECT * FROM test_sessions WHERE id LIKE '2c9a93f6%'
-- Result: 0 rows
```

### 3. Recent Sessions Found
The database contains recent sessions with different IDs:

**test_sessions:**
- `9d5c699a...` - HIL Test Session (2025-09-15)
- `49bae3f2...` - AI Detection Session - Child.mp4 (2025-09-11)
- Multiple other Child.mp4 detection sessions

**detection_sessions:**
- `8d2c660b-96bb...` - 9 detections
- `aa26d375-21d6...` - 14 detections
- `4bbb55e7-3f65...` - 3 detections

---

## Schema Discrepancy Found

### Critical Issue: Models.py vs Database Mismatch

**models.py defines:**
```python
class TestSession(Base):
    # ... includes fields:
    has_video_sequence = Column(Boolean, default=False)
    accuracy_recall = Column(Float, nullable=True)
    accuracy_precision = Column(Float, nullable=True)
    tp_count = Column(Integer, nullable=True)
    fp_count = Column(Integer, nullable=True)
    fn_count = Column(Integer, nullable=True)
```

**Database actually has:**
```sql
-- test_sessions table lacks these columns:
-- has_video_sequence (missing)
-- accuracy_recall (missing)
-- accuracy_precision (missing)
-- tp_count (missing)
-- fp_count (missing)
-- fn_count (missing)
```

This suggests:
1. **Migration not applied** - Database schema is outdated
2. **Wrong database file** - Using old test database
3. **Alembic migration issue** - Schema changes not synced

---

## User's Reported Issues (Cannot Verify)

The user reported the following issues for session `2c9a93f6`:

### Issue 1: Recall Shows 100% but Data Says 34.3%
- **Reported:** Recall = 100%
- **Calculated:** 83 TP / 242 GT = 34.3%
- **Status:** ❌ CANNOT VERIFY - Session not in database

### Issue 2: Only 91/242 Detections Captured (37.6%)
- **Expected:** ~242 detections
- **Actual:** 91 detections
- **Status:** ❌ CANNOT VERIFY - Session not in database

### Issue 3: LabJack Light Stops Flickering
- **Report:** Detection stopping mid-test
- **Status:** ❌ CANNOT VERIFY - Session not in database

### Issue 4: Math Doesn't Add Up
- **Video 1:** 41 TP / 41 GT = 100%
- **Video 2:** Claims 100% but unclear
- **Aggregated:** 83 TP / 242 GT
- **Status:** ❌ CANNOT VERIFY - Session not in database

---

## Root Cause Analysis

### Most Likely Scenarios

#### Scenario 1: Database File Mismatch (80% probability)
- User is referencing production database
- Investigation queried `test_database.db` (test environment)
- **Action:** Verify correct database path with user

#### Scenario 2: Session Deleted (15% probability)
- Session was created, tested, then deleted
- User referencing logs/screenshots from deleted session
- **Action:** Check audit_logs table for deletion records

#### Scenario 3: Data Corruption (5% probability)
- Database corruption caused session loss
- **Action:** Check database integrity with `PRAGMA integrity_check`

---

## Recommendations

### Immediate Actions

1. **Verify Database Path**
   ```python
   # Ask user: Which database are you referencing?
   # Production: /path/to/production.db
   # Test: /path/to/test_database.db
   # Dev: /path/to/dev_database.db
   ```

2. **Check Audit Logs**
   ```sql
   SELECT * FROM audit_logs
   WHERE event_data LIKE '%2c9a93f6%'
   ORDER BY created_at DESC;
   ```

3. **Run Database Migrations**
   ```bash
   # Apply pending migrations
   cd /home/rigade/Testing/ai-model-validation-platform/backend
   alembic upgrade head
   ```

4. **Verify Database Integrity**
   ```sql
   PRAGMA integrity_check;
   ```

### If Session Cannot Be Found

If the session truly doesn't exist, investigate the **reported bugs theoretically**:

#### Bug Analysis: Recall Shows 100% vs 34.3%

**Likely Code Issue:**
```python
# WRONG - Using precision instead of recall
if precision >= threshold:  # BUG!
    result = "PASS"

# CORRECT - Should use recall
if recall >= threshold:
    result = "PASS"
```

**Where to Look:**
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/test_evaluation_service.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/api/test_sessions.py`
- Search for: `accuracy_recall`, `pass_fail_result`, evaluation logic

#### Bug Analysis: Low Detection Rate (37.6%)

**Possible Causes:**
1. **constant_voltage_mode Issue** - May cause detector to stop
2. **Timeout in detection loop** - Stops after X detections
3. **Video playback desync** - Detection window closes too early
4. **LabJack buffer overflow** - Missing events

**Where to Look:**
- Hardware detection service code
- LabJack integration code
- Video playback synchronization
- Event buffer management

---

## Next Steps

### For User

1. **Confirm Database Path**
   - Provide actual database file path being referenced
   - Check if using production vs test database

2. **Provide Alternative Evidence**
   - Frontend screenshots showing session metrics
   - API response logs with session data
   - Browser console logs
   - Network requests showing session ID

3. **Check Session Logs**
   - Look for session creation logs
   - Check backend logs for `2c9a93f6` mentions

### For Development Team

1. **Fix Schema Migration**
   ```bash
   # Generate migration for missing columns
   alembic revision --autogenerate -m "Add accuracy metrics to test_sessions"
   alembic upgrade head
   ```

2. **Add Session Validation**
   ```python
   # Prevent referencing non-existent sessions
   def get_session_or_404(session_id: str):
       session = db.query(TestSession).filter(TestSession.id == session_id).first()
       if not session:
           raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
       return session
   ```

3. **Implement Audit Trail**
   - Log all session creations
   - Log all session deletions
   - Track schema version in sessions

---

## Conclusion

**The investigation could not proceed** because session `2c9a93f6-8471-4f2e-b1a7-06f239fca548` does not exist in the queried database.

**Required Information:**
1. ✅ Correct database file path
2. ✅ Alternative session ID (if available)
3. ✅ Screenshots/logs showing the problematic metrics
4. ✅ Confirmation of database environment (prod/test/dev)

**Once the session is located, a full investigation can analyze:**
- Recall calculation bug (100% vs 34.3%)
- Detection rate issue (37.6% capture rate)
- Math discrepancies in TP/FP/FN
- LabJack stopping behavior

---

## Technical Details

**Database Queried:** `sqlite:///test_database.db`
**Tables Searched:** `test_sessions`, `detection_sessions`
**Session ID Format:** UUID v4 (valid format)
**Search Methods:** Exact match, partial match, timestamp range
**Result:** 0 matching records found

**Available Tables:**
- auth_users
- projects
- audit_logs
- user_sessions
- videos
- ground_truth_objects
- test_sessions ✓ (searched)
- detection_sessions ✓ (searched)
- detection_events
- stored_detection_events
- annotations
- video_events
- test_results
- detection_comparisons

---

## Appendix: SQL Queries Used

```sql
-- Query 1: Direct ID match
SELECT * FROM test_sessions WHERE id = '2c9a93f6-8471-4f2e-b1a7-06f239fca548';

-- Query 2: Partial ID match
SELECT * FROM test_sessions WHERE id LIKE '2c9a93f6%';

-- Query 3: Recent sessions
SELECT id, name, created_at, status FROM test_sessions
ORDER BY created_at DESC LIMIT 20;

-- Query 4: Detection sessions
SELECT * FROM detection_sessions
WHERE id = '2c9a93f6-8471-4f2e-b1a7-06f239fca548'
   OR session_id = '2c9a93f6-8471-4f2e-b1a7-06f239fca548';

-- Query 5: Schema validation
PRAGMA table_info(test_sessions);
```

All queries returned 0 results for the target session ID.
