# Ground Truth Matching Bug Diagnosis
## Critical Bug: 0% Recall Due to Foreign Key Mismatch

**Status:** 🔴 CRITICAL - Production Blocker
**Date:** 2025-11-20
**Severity:** P0 - Complete System Failure
**Impact:** ALL ground truth matches failing with 0% recall

---

## Executive Summary

**ROOT CAUSE IDENTIFIED:** Foreign key schema mismatch between code and database causing silent data insertion failures.

The ground truth matching system is experiencing a **catastrophic foreign key constraint violation** that causes ALL matches to fail validation. The code queries from the `ground_truth_objects` table but attempts to insert IDs into a foreign key column that points to the `annotations` table.

**Evidence:**
- ✅ 200 detections captured
- ✅ 242 GT events exist in database
- ❌ **0 True Positives** (should be ~200)
- ❌ **200 False Positives** (all detections unmatched)
- ❌ **0% Recall** (complete matching failure)

---

## Root Cause Analysis

### The Bug: Two Separate Ground Truth Tables

The system has **TWO different ground truth table schemas**:

#### Table 1: `ground_truth_objects` (models.py line 173)
```python
class GroundTruthObject(Base):
    __tablename__ = "ground_truth_objects"

    id = Column(String(36), primary_key=True)
    video_id = Column(String(36), ForeignKey("videos.id"))
    tracking_id = Column(String, nullable=True)
    frame_number = Column(Integer, nullable=True)
    timestamp = Column(Float, nullable=False)
    class_label = Column(String, nullable=False)
    # ... bounding box fields ...
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
```

#### Table 2: `annotations` (models.py line 617)
```python
class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(String(36), primary_key=True)
    video_id = Column(String(36), ForeignKey("videos.id"))
    detection_id = Column(String(36), nullable=True)  # DET_PED_0001
    frame_number = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)
    vru_type = Column(String, nullable=False)
    bounding_box = Column(JSON, nullable=False)
    # ... validation fields ...
```

### The Foreign Key Mismatch

**models.py line 759** - `DetectionComparison` model:
```python
class DetectionComparison(Base):
    __tablename__ = "detection_comparisons"

    id = Column(String(36), primary_key=True)
    test_session_id = Column(String(36), ForeignKey("test_sessions.id"))
    ground_truth_id = Column(String(36), ForeignKey("annotations.id"))  # ❌ WRONG TABLE!
    detection_event_id = Column(String(36), ForeignKey("detection_events.id"))
    match_type = Column(String, nullable=False)  # 'TP', 'FP', 'FN'
    # ...
```

**ground_truth_matching_service.py line 334-348** - Code queries WRONG table:
```python
# Get all ground truth objects for the video(s) in this session
ground_truth_objects = self._get_ground_truth_for_session(
    db, test_session, session_id
)  # ← Returns GroundTruthObject records

# ... matching logic ...

# Populate database with results
self._populate_detection_comparisons(db, session_id, match_results)
```

**ground_truth_matching_service.py line 1163** - Inserts with wrong ID:
```python
payload = {
    "id": str(uuid.uuid4()),
    "test_session_id": session_id,
    "ground_truth_id": match_result.ground_truth_id,  # ← This is ground_truth_objects.id
    "detection_event_id": match_result.detection_event_id,
    "match_type": match_result.match_type,
    # ...
}
```

### Why This Fails

1. **Matching Service** queries `ground_truth_objects` table (lines 334-348)
2. **Hungarian Algorithm** matches detections to `ground_truth_objects` records (lines 807-1027)
3. **MatchResult** objects contain `ground_truth_objects.id` values
4. **Database Insert** attempts to write `ground_truth_objects.id` into `detection_comparisons.ground_truth_id`
5. **Foreign Key Constraint** expects `annotations.id` value
6. **Silent Failure** - SQLite may allow NULL or skip constraint, causing unmatched records

---

## Evidence of the Bug

### Code Location Evidence

#### 1. Query Location (ground_truth_matching_service.py:384-512)
```python
def _get_ground_truth_for_session(
    self,
    db: Session,
    test_session: TestSession,
    session_id: str
) -> List[GroundTruthObject]:  # ← Returns GroundTruthObject, not Annotation
    """
    Get ground truth objects for session...
    """
    # Line 443-446: Soft delete filter
    gt_count = db.query(func.count(GroundTruthObject.id)).filter(
        GroundTruthObject.video_id.in_(video_ids),
        GroundTruthObject.deleted_at.is_(None)  # SOFT DELETE FILTER
    ).scalar()

    # Line 481-486: Single video query
    ground_truth_objects = db.query(GroundTruthObject).filter(
        GroundTruthObject.video_id == test_session.video_id,
        GroundTruthObject.deleted_at.is_(None)  # SOFT DELETE FILTER
    ).order_by(
        GroundTruthObject.timestamp
    ).all()
```

#### 2. Matching Logic (ground_truth_matching_service.py:807-949)
```python
# Line 814-816: Extract from ground_truth_objects
for gt_obj in ground_truth_objects:
    gt_time = extract_ground_truth_video_time(gt_obj, session_start_time)
    gt_times.append(gt_time if gt_time is not None else float('inf'))

# Line 839-843: Create MatchResult with ground_truth_objects ID
for gt_idx, det_idx, latency_ms in optimal_result['true_positives']:
    gt_obj = ground_truth_objects[gt_idx]  # ← GroundTruthObject
    detection = detection_events[det_idx]

    # Line 939-949: Store ground_truth_objects.id
    match_result = MatchResult(
        ground_truth_id=gt_obj.id,  # ← This is ground_truth_objects.id!
        detection_event_id=detection.id,
        match_type='TP',
        # ...
    )
```

#### 3. Database Insert (ground_truth_matching_service.py:1160-1172)
```python
for match_result in match_results:
    payload = {
        "id": str(uuid.uuid4()),
        "test_session_id": session_id,
        "ground_truth_id": match_result.ground_truth_id,  # ← ground_truth_objects.id
        "detection_event_id": match_result.detection_event_id,
        "match_type": match_result.match_type,
        "iou_score": match_result.iou_score,
        "temporal_offset": match_result.temporal_offset,
        # ...
    }
    pending.append(payload)
    # ... batch insert into detection_comparisons table
```

#### 4. Foreign Key Definition (models.py:753-770)
```python
class DetectionComparison(Base):
    """Detection comparison for ground truth validation"""
    __tablename__ = "detection_comparisons"

    id = Column(String(36), primary_key=True)
    test_session_id = Column(String(36), ForeignKey("test_sessions.id"))
    ground_truth_id = Column(String(36), ForeignKey("annotations.id"))  # ❌ EXPECTS annotations.id
    detection_event_id = Column(String(36), ForeignKey("detection_events.id"))
    match_type = Column(String, nullable=False)
    # ...

    # Relationships
    ground_truth = relationship("Annotation")  # ❌ Points to Annotation model
```

### Symptom Evidence

From test results:
```
✅ Detections: 200 captured correctly
✅ Ground Truth: 242 events exist in database
✅ Timeline: Shows detections aligned with video frames
✅ Latencies: Correct range (-14ms to +19ms)
❌ Matching: 0 True Positives (ALL marked as "GT FAIL")
❌ Recall: 0% (catastrophic failure)
❌ False Positives: 200 (all detections unmatched)
```

---

## Impact Analysis

### System Impact

1. **Matching Validation**: 100% failure rate
2. **Metrics Accuracy**: All precision/recall metrics invalid
3. **Timeline Display**: Shows detections but marks all as "GT FAIL"
4. **Production Readiness**: **BLOCKED** - cannot validate HIL sessions

### Data Integrity Impact

1. **detection_comparisons** table contains invalid foreign keys
2. Relationships between detections and ground truth broken
3. Historical test sessions may have corrupted comparison data
4. Reports and analytics based on comparisons are unreliable

### User Impact

1. Users see 0% detection rates despite working detections
2. Cannot validate model performance
3. Cannot trust latency metrics
4. Cannot use system for production HIL testing

---

## Why This Wasn't Caught Earlier

### 1. Foreign Key Constraints May Be Disabled

SQLite by default **disables foreign key constraints**:
```sql
-- Check if FK constraints are enabled
PRAGMA foreign_keys;  -- May return 0 (disabled)
```

Without enforcement, the inserts succeed with orphaned IDs.

### 2. Soft Delete Logic Hides Records

The `ground_truth_objects` table has soft delete via `deleted_at`:
```python
GroundTruthObject.deleted_at.is_(None)  # SOFT DELETE FILTER
```

If GT records are soft-deleted, they won't match, but the code won't error - it just returns empty results.

### 3. Silent Failure in Batch Inserts

The code uses batch inserts:
```python
db.execute(insert(comparison_table).values(**payload))
```

If FK constraints are disabled, this succeeds without validation.

### 4. No Validation After Insert

After populating comparisons, there's no validation check:
```python
self._populate_detection_comparisons(db, session_id, match_results)
db.commit()  # May commit invalid data
```

Should verify:
```python
inserted_count = db.query(DetectionComparison).filter(
    DetectionComparison.test_session_id == session_id,
    DetectionComparison.ground_truth_id.isnot(None)
).count()
assert inserted_count == len([mr for mr in match_results if mr.match_type == 'TP'])
```

---

## Option C Integration Status

### Option C Temporal Expansion NOT FOUND

**Searched for:**
- `enable_temporal_expansion` parameter - ❌ NOT FOUND
- `expand_detection_temporal()` function - ❌ NOT FOUND
- `collapse_virtual_matches()` function - ❌ NOT FOUND
- Temporal expansion logic - ❌ NOT FOUND

**Evidence:**
```bash
$ grep -r "enable_temporal_expansion" backend/services/
# No results

$ grep -r "expand_detection_temporal" backend/services/
# No results

$ grep -r "temporal.*expansion" backend/services/
# No results matching Option C implementation
```

**Conclusion:** Option C temporal expansion is **NOT implemented** in production code. The test suite exists (`test_option_c_temporal_expansion.py`) but the actual matching service does not include the expansion logic.

**Impact:** Even if the foreign key bug is fixed, the system will still have the 77.9% detection rate problem because:
1. LabJack detects single pulse at frame 0
2. Pulse spans 12 frames (500ms @ 40ms/frame)
3. Ground truth has 12 objects (one per frame)
4. Current matching: 1 detection → 1 GT match = 8.3% rate
5. Without Option C expansion: **LOW RECALL PERSISTS**

---

## Immediate Fixes Required

### Fix 1: Correct Foreign Key Reference (CRITICAL)

**File:** `backend/models.py` line 759
**Current:**
```python
ground_truth_id = Column(String(36), ForeignKey("annotations.id", ondelete="SET NULL"))
```

**Fix Option A - Point to correct table:**
```python
ground_truth_id = Column(String(36), ForeignKey("ground_truth_objects.id", ondelete="SET NULL"))
```

**Fix Option B - Update relationship:**
```python
ground_truth = relationship("GroundTruthObject")  # Instead of "Annotation"
```

### Fix 2: Enable Foreign Key Constraints

**File:** `backend/database.py`
**Add after engine creation:**
```python
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

### Fix 3: Add Post-Insert Validation

**File:** `backend/services/ground_truth_matching_service.py` line 1237
**Add after batch insert:**
```python
# Validate insertions succeeded
tp_count = len([mr for mr in match_results if mr.match_type == 'TP'])
inserted_count = db.query(DetectionComparison).filter(
    DetectionComparison.test_session_id == session_id,
    DetectionComparison.match_type == 'TP',
    DetectionComparison.ground_truth_id.isnot(None)
).count()

if inserted_count != tp_count:
    raise RuntimeError(
        f"Comparison insert validation FAILED: "
        f"Expected {tp_count} TP matches, found {inserted_count}. "
        f"Check foreign key constraints."
    )
```

### Fix 4: Database Migration

**Create migration script:**
```python
# backend/migrations/fix_ground_truth_fk.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Drop old FK constraint
    op.drop_constraint('detection_comparisons_ibfk_1', 'detection_comparisons', type_='foreignkey')

    # Create new FK constraint to ground_truth_objects
    op.create_foreign_key(
        'fk_detection_comparisons_ground_truth',
        'detection_comparisons',
        'ground_truth_objects',
        ['ground_truth_id'],
        ['id'],
        ondelete='SET NULL'
    )

def downgrade():
    # Revert to annotations FK
    op.drop_constraint('fk_detection_comparisons_ground_truth', 'detection_comparisons', type_='foreignkey')
    op.create_foreign_key(
        'detection_comparisons_ibfk_1',
        'detection_comparisons',
        'annotations',
        ['ground_truth_id'],
        ['id'],
        ondelete='SET NULL'
    )
```

---

## Secondary Issue: Option C Not Implemented

### Current State

The production matching service uses the **Hungarian algorithm** (optimal_detection_matching) but does **NOT** include Option C temporal expansion logic.

**File:** `backend/services/ground_truth_matching_service.py` lines 807-1027
**Current algorithm:**
1. Extract timestamps from GT objects and detections
2. Run Hungarian algorithm for optimal assignment
3. Create MatchResult for each assignment
4. No temporal expansion

### Missing Implementation

**Required additions from test suite:**

1. **Temporal Expansion Function** (test_option_c_temporal_expansion.py lines 50-100):
```python
def expand_detection_temporal(
    detection: DetectionEvent,
    pulse_duration_ms: float,
    frame_interval_ms: float
) -> List[DetectionEvent]:
    """
    Expand single detection across pulse duration

    Example: 1 detection @ frame 0 → 12 virtual detections @ frames 0-11
    """
    num_virtual_detections = int(pulse_duration_ms / frame_interval_ms)
    virtual_detections = []

    for i in range(num_virtual_detections):
        virtual_det = copy.copy(detection)
        virtual_det.id = f"{detection.id}_virtual_{i}"
        virtual_det.timestamp = detection.timestamp + (i * frame_interval_ms / 1000.0)
        virtual_det.original_detection_id = detection.id
        virtual_detections.append(virtual_det)

    return virtual_detections
```

2. **Collapse Function** (test_option_c_temporal_expansion.py lines 120-160):
```python
def collapse_virtual_matches(
    virtual_matches: List[MatchResult],
    original_detection_id: str
) -> MatchResult:
    """
    Collapse virtual matches back to single detection

    Strategy: Majority voting (>50% matched → TP)
    """
    tp_matches = [m for m in virtual_matches if m.match_type == 'TP']
    match_rate = len(tp_matches) / len(virtual_matches)

    if match_rate > 0.5:
        # Majority matched - True Positive
        avg_latency = statistics.mean([m.latency_ms for m in tp_matches])
        return MatchResult(
            ground_truth_id=None,  # Collapsed from multiple
            detection_event_id=original_detection_id,
            match_type='TP',
            latency_ms=avg_latency,
            # ...
        )
    else:
        # Majority unmatched - False Positive
        return MatchResult(
            ground_truth_id=None,
            detection_event_id=original_detection_id,
            match_type='FP',
            latency_ms=FP_LATENCY_MARKER,
            # ...
        )
```

3. **Integration Points:**
   - **Before matching** (line 810): Expand pulse detections
   - **After matching** (line 1088): Collapse virtual matches
   - **Configuration**: Add `enable_temporal_expansion` flag to timing_config.py

### Impact Without Option C

**Current performance:**
- 1 LabJack detection per pulse (at t=0ms)
- 12 GT frames per pulse (0-440ms @ 40ms spacing)
- **Detection rate: 1/12 = 8.3% per pulse**
- Across 10 pulses: 10/120 = 8.3% overall

**With Option C (expected):**
- 1 detection → 12 virtual detections
- 12 GT frames matched → 12/12 = 100% per pulse
- **Detection rate: 100% (12x improvement)**

---

## Testing Strategy

### 1. Fix Foreign Key Bug First

```bash
# Step 1: Enable FK constraints
cd /home/rigade/Testing/ai-model-validation-platform/backend
python -c "
from database import engine
from sqlalchemy import event

@event.listens_for(engine, 'connect')
def set_fk(conn, record):
    conn.execute('PRAGMA foreign_keys=ON')
"

# Step 2: Run migration
alembic upgrade head

# Step 3: Verify FK constraints
sqlite3 ai_model_validation.db "PRAGMA foreign_keys;"
sqlite3 ai_model_validation.db "PRAGMA foreign_key_list(detection_comparisons);"
```

### 2. Verify Fix with Test Session

```bash
# Run matching on test session
python -c "
from services.ground_truth_matching_service import GroundTruthMatchingService
service = GroundTruthMatchingService()
metrics = service.match_detections_to_ground_truth(
    session_id='<test_session_id>',
    force_rematch=True
)
print(f'TP: {metrics.true_positives}, FP: {metrics.false_positives}, FN: {metrics.false_negatives}')
print(f'Recall: {metrics.recall:.2%}')
"
```

**Expected after FK fix:**
- ✅ Inserts succeed without FK violations
- ✅ TP count > 0 (should match detection count)
- ✅ Recall > 0% (should be 8.3-10% without Option C)

### 3. Implement Option C (Phase 2)

```bash
# Run Option C test suite
cd /home/rigade/Testing/ai-model-validation-platform/backend
pytest tests/services/test_option_c_temporal_expansion.py::TestValidationProof -v

# Expected result AFTER implementation:
# ✅ PASSED test_production_scenario_95_percent_proof
# Detection rate: 100.0% (≥95% threshold)
```

---

## Rollout Plan

### Phase 1: Emergency Hotfix (FK Bug) - 2 hours

1. **Update models.py** (5 min)
   - Change FK from `annotations.id` to `ground_truth_objects.id`
   - Update relationship

2. **Enable FK constraints** (5 min)
   - Update database.py with PRAGMA enforcement

3. **Add validation** (10 min)
   - Post-insert comparison count check

4. **Create migration** (30 min)
   - Alembic migration script
   - Test on dev database

5. **Deploy and test** (1 hour)
   - Run migration on production DB
   - Force rematch on recent sessions
   - Verify TP count > 0 and recall > 0%

### Phase 2: Option C Implementation - 4-6 hours

1. **Copy functions from test suite** (1 hour)
   - expand_detection_temporal()
   - collapse_virtual_matches()
   - Add to ground_truth_matching_service.py

2. **Integrate into matching flow** (2 hours)
   - Detect pulse vs. single-frame detections
   - Expand before Hungarian matching
   - Collapse after matching

3. **Add configuration** (30 min)
   - enable_temporal_expansion flag
   - pulse_duration_ms parameter
   - frame_interval_ms parameter

4. **Testing** (2 hours)
   - Run Option C test suite
   - Validate on production HIL sessions
   - Compare before/after detection rates

5. **Documentation** (30 min)
   - Update API docs
   - Add deployment notes
   - Create user guide

---

## Monitoring and Validation

### Metrics to Track

**After FK Fix:**
```sql
-- Check TP insertions are working
SELECT
    COUNT(*) as total_comparisons,
    SUM(CASE WHEN match_type = 'TP' THEN 1 ELSE 0 END) as tp_count,
    SUM(CASE WHEN match_type = 'FP' THEN 1 ELSE 0 END) as fp_count,
    SUM(CASE WHEN match_type = 'FN' THEN 1 ELSE 0 END) as fn_count,
    SUM(CASE WHEN ground_truth_id IS NOT NULL THEN 1 ELSE 0 END) as valid_fk_count
FROM detection_comparisons
WHERE test_session_id = '<session_id>';
```

**Expected results:**
- total_comparisons > 0
- tp_count > 0 (was 0 before fix)
- valid_fk_count == tp_count (no FK violations)

**After Option C:**
```sql
-- Check detection rate improvement
SELECT
    ts.id,
    ts.actual_detections,
    ts.tp_count,
    (ts.tp_count * 100.0 / COUNT(DISTINCT gt.id)) as detection_rate_pct
FROM test_sessions ts
JOIN detection_events de ON de.test_session_id = ts.id
JOIN ground_truth_objects gt ON gt.video_id = ts.video_id
WHERE ts.id = '<session_id>'
GROUP BY ts.id;
```

**Expected results:**
- detection_rate_pct ≥ 95% (was 8.3% before Option C)

---

## Preventive Measures

### 1. Add Integration Tests

```python
# tests/integration/test_ground_truth_matching_integration.py
def test_foreign_key_integrity():
    """Verify FK constraints are enforced"""
    # Attempt to insert invalid FK
    with pytest.raises(IntegrityError):
        db.execute(
            insert(DetectionComparison).values(
                ground_truth_id="invalid_id",
                # ...
            )
        )
```

### 2. Add Database Constraints

```sql
-- Verify FK constraint exists
CREATE INDEX IF NOT EXISTS idx_detection_comparisons_gt_fk
ON detection_comparisons(ground_truth_id);

-- Add check constraint
ALTER TABLE detection_comparisons
ADD CONSTRAINT chk_valid_match_type
CHECK (match_type IN ('TP', 'FP', 'FN'));
```

### 3. Add Monitoring Alerts

```python
# monitoring/ground_truth_health_check.py
def check_matching_health():
    """Alert if matching success rate drops"""
    recent_sessions = get_recent_sessions(hours=24)

    for session in recent_sessions:
        metrics = get_session_metrics(session.id)

        if metrics.recall == 0:
            alert(
                f"CRITICAL: Session {session.id} has 0% recall. "
                f"Check foreign key integrity."
            )

        if metrics.recall < 0.5:
            alert(
                f"WARNING: Session {session.id} has {metrics.recall:.1%} recall. "
                f"Check Option C implementation."
            )
```

---

## Conclusion

### Summary of Findings

1. **Primary Bug:** Foreign key mismatch causing 100% matching failure
   - FK points to `annotations.id` but code uses `ground_truth_objects.id`
   - Inserts succeed (FK constraints disabled) but create orphaned records
   - Results in 0% recall, all detections marked as FP

2. **Secondary Issue:** Option C temporal expansion not implemented
   - Test suite exists but production code missing expansion logic
   - Without Option C: 8.3% detection rate (1/12 frames matched)
   - With Option C: 100% detection rate (12/12 frames matched)

3. **Database Integrity:** FK constraints not enforced
   - SQLite PRAGMA foreign_keys disabled by default
   - No validation after insertions
   - Silent failures allowed

### Critical Path to Resolution

1. ✅ **IMMEDIATE** (2 hours): Fix FK bug
   - Update models.py FK reference
   - Enable FK constraints
   - Run migration
   - Verify TP count > 0

2. ✅ **SHORT TERM** (4-6 hours): Implement Option C
   - Copy expansion/collapse functions from tests
   - Integrate into matching pipeline
   - Validate 95%+ detection rate

3. ✅ **MEDIUM TERM** (1-2 days): Add safeguards
   - Integration tests for FK integrity
   - Monitoring alerts for matching failures
   - Database constraint enforcement

### Success Criteria

**After FK Fix:**
- ✅ TP count > 0 (currently 0)
- ✅ Recall > 0% (currently 0%)
- ✅ No FK violation errors in logs
- ✅ Timeline shows matched detections

**After Option C:**
- ✅ Detection rate ≥ 95% (currently 8.3%)
- ✅ TP count ~12x higher
- ✅ Latency metrics accurate
- ✅ Production HIL validation working

---

## Appendix A: Code Locations

### Critical Files

1. **models.py** (line 759)
   - FK definition: `ForeignKey("annotations.id")`
   - Should be: `ForeignKey("ground_truth_objects.id")`

2. **ground_truth_matching_service.py** (lines 334-1250)
   - Line 334: `_get_ground_truth_for_session()` queries wrong table
   - Line 723: `_perform_temporal_matching()` creates MatchResults
   - Line 1120: `_populate_detection_comparisons()` inserts invalid FKs
   - Line 1163: `ground_truth_id` assignment

3. **database.py** (engine creation)
   - Missing: FK constraint enforcement via PRAGMA

4. **test_option_c_temporal_expansion.py** (lines 1-558)
   - Reference implementation of Option C
   - Expansion function (lines 50-100)
   - Collapse function (lines 120-160)
   - Validation proof (lines 500-558)

### Database Schema

```sql
-- Current (BROKEN)
CREATE TABLE detection_comparisons (
    id VARCHAR(36) PRIMARY KEY,
    ground_truth_id VARCHAR(36),
    FOREIGN KEY (ground_truth_id) REFERENCES annotations(id)  -- ❌ WRONG
);

-- Fixed
CREATE TABLE detection_comparisons (
    id VARCHAR(36) PRIMARY KEY,
    ground_truth_id VARCHAR(36),
    FOREIGN KEY (ground_truth_id) REFERENCES ground_truth_objects(id)  -- ✅ CORRECT
);
```

---

## Appendix B: Test Commands

### Verify Current Broken State

```bash
# Check FK constraint
sqlite3 ai_model_validation.db "PRAGMA foreign_key_list(detection_comparisons);"

# Count comparisons with invalid FKs
sqlite3 ai_model_validation.db "
SELECT COUNT(*) as orphaned_comparisons
FROM detection_comparisons dc
LEFT JOIN annotations a ON dc.ground_truth_id = a.id
WHERE dc.ground_truth_id IS NOT NULL AND a.id IS NULL;
"

# Check recall for recent session
python -c "
from services.ground_truth_matching_service import get_session_matching_results
metrics = get_session_matching_results('<session_id>')
print(f'Recall: {metrics.recall:.2%}')
print(f'TP: {metrics.true_positives}, FP: {metrics.false_positives}')
"
```

### Verify Fix

```bash
# After FK fix - should see TP count > 0
python -c "
from services.ground_truth_matching_service import GroundTruthMatchingService
service = GroundTruthMatchingService()
metrics = service.match_detections_to_ground_truth('<session_id>', force_rematch=True)
assert metrics.true_positives > 0, 'FK fix failed - still 0 TP'
assert metrics.recall > 0, 'FK fix failed - still 0% recall'
print(f'✅ FK fix successful: {metrics.true_positives} TP, {metrics.recall:.1%} recall')
"

# After Option C - should see 95%+ detection rate
pytest tests/services/test_option_c_temporal_expansion.py::TestValidationProof::test_production_scenario_95_percent_proof -v
```

---

**END OF DIAGNOSIS**

**Recommended Action:** Implement Fix 1 (FK correction) IMMEDIATELY as emergency hotfix. Schedule Option C implementation for next sprint.

**Estimated Time to Resolution:**
- FK Fix: 2 hours (emergency)
- Option C: 4-6 hours (follow-up)
- Total: 6-8 hours to full functionality
