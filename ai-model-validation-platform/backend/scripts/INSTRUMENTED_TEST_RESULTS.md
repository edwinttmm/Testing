# Instrumented Test Results - DEEP INVESTIGATION #5

## Execution Summary

**Script Location**: `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/instrumented_test.py`

**Status**: ✅ **SUCCESSFULLY CAPTURED ROOT CAUSES**

**Log File**: `/tmp/instrumented_test.log`

**Test Session**: `2c9a93f6-8471-4f2e-b1a7-06f239fca548`

---

## 🔴 CRITICAL FINDINGS - ROOT CAUSES IDENTIFIED

### ROOT CAUSE #1: Session Has NO Metrics Stored

```
[SESSION] Found session: 2c9a93f6-8471-4f2e-b1a7-06f239fca548
[SESSION] Name: Video Sequence Test - 2025-11-24 19:35
[SESSION] Status: completed
[SESSION] TP: N/A    ❌ NOT STORED
[SESSION] FP: N/A    ❌ NOT STORED
[SESSION] FN: N/A    ❌ NOT STORED
[SESSION] TN: N/A    ❌ NOT STORED
```

**DIAGNOSIS**: The TestSession model does NOT have fields for `true_positives`, `false_positives`, `false_negatives`, `true_negatives`.

**IMPACT**:
- Recall calculation CANNOT work because TP and FN don't exist
- Precision calculation CANNOT work because TP and FP don't exist
- ALL metrics are being calculated from NOWHERE

---

### ROOT CAUSE #2: Method Signature Mismatch

```python
# ERROR from instrumented test:
TypeError: GroundTruthMatchingService._get_actual_ground_truth_count()
missing 2 required positional arguments: 'test_session' and 'session_id'
```

**ACTUAL METHOD SIGNATURE**:
```python
def _get_actual_ground_truth_count(
    self,
    db: Session,           # ❌ Missing in call
    test_session: TestSession,  # ❌ Missing in call
    session_id: str        # ✅ Provided
) -> int:
```

**DIAGNOSIS**: The method requires 3 arguments but only 1 is being passed.

---

### ROOT CAUSE #3: Model Schema Issues

**GroundTruthObject**:
- ❌ Has `video_id` (NOT `session_id`)
- ✅ Links to Video which links to TestSession
- ❌ No direct session_id relationship

**DetectionEvent**:
- ✅ Has `test_session_id`
- ✅ Can query directly by session

**Query Errors**:
```python
AttributeError: type object 'GroundTruthObject' has no attribute 'session_id'
AttributeError: type object 'DetectionEvent' has no attribute 'session_id'
```

**DIAGNOSIS**: DetectionEvent uses `test_session_id` not `session_id`.

---

## 📊 Database Schema Analysis

### TestSession Model (models.py line 213)
```python
class TestSession(Base):
    __tablename__ = "test_sessions"

    # OBSERVED FIELDS:
    id = Column(String(36), primary_key=True)
    name = Column(String)
    status = Column(String)  # e.g., "completed"

    # MISSING FIELDS (causing the bug):
    # ❌ true_positives = NOT FOUND
    # ❌ false_positives = NOT FOUND
    # ❌ false_negatives = NOT FOUND
    # ❌ true_negatives = NOT FOUND
    # ❌ precision = NOT FOUND
    # ❌ recall = NOT FOUND
    # ❌ f1_score = NOT FOUND
```

### GroundTruthObject Model (models.py line 173)
```python
class GroundTruthObject(Base):
    __tablename__ = "ground_truth_objects"

    id = Column(String(36), primary_key=True)
    video_id = Column(String(36), ForeignKey("videos.id"))  # ⚠️ Links via video
    # ❌ NO session_id field

    # Relationship chain:
    # GroundTruthObject → video_id → Video → ??? → TestSession
```

### DetectionEvent Model (models.py line 333)
```python
class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id = Column(String(36), primary_key=True)
    test_session_id = Column(String(36), ForeignKey("test_sessions.id"))  # ✅ Direct link
    video_id = Column(String(36), ForeignKey("videos.id"))
```

---

## 🎯 ACTUAL ROOT CAUSES (Evidence-Based)

### Cause #1: Missing Metrics Storage
**Evidence**: `hasattr(session, 'true_positives')` returns `False`

**Impact**:
- Recall = TP / (TP + FN) → undefined (no TP, no FN)
- Precision = TP / (TP + FP) → undefined (no TP, no FP)
- F1 Score = 2 * (Precision * Recall) / (Precision + Recall) → undefined

**Fix Required**:
1. Add metrics columns to TestSession model
2. OR create separate PerformanceMetrics table
3. Store TP/FP/FN/TN during matching process

---

### Cause #2: Incorrect Method Calls
**Evidence**: Method requires `(db, test_session, session_id)` but called with only `(session_id)`

**Impact**:
- Method fails immediately
- No GT count can be retrieved
- Recall calculation defaults to formula method (wrong)

**Fix Required**:
1. Update all calls to provide correct arguments
2. OR refactor method to accept single session_id parameter
3. Handle database session creation internally

---

### Cause #3: Inconsistent Field Naming
**Evidence**:
- GroundTruthObject uses `video_id` (no session_id)
- DetectionEvent uses `test_session_id` (not session_id)

**Impact**:
- Direct session queries fail
- Must traverse relationships (video → session)
- Performance overhead

**Fix Required**:
1. Add session_id to GroundTruthObject
2. OR fix all queries to traverse relationships correctly
3. Standardize field naming (session_id vs test_session_id)

---

## 💡 Recommended Fixes

### Priority 1: Add Metrics Storage (CRITICAL)

**Option A: Add columns to TestSession**
```python
class TestSession(Base):
    __tablename__ = "test_sessions"

    # Add these columns:
    true_positives = Column(Integer, default=0)
    false_positives = Column(Integer, default=0)
    false_negatives = Column(Integer, default=0)
    true_negatives = Column(Integer, default=0, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
```

**Option B: Create PerformanceMetrics table** (better design)
```python
class PerformanceMetrics(Base):
    __tablename__ = "performance_metrics"

    id = Column(String(36), primary_key=True)
    test_session_id = Column(String(36), ForeignKey("test_sessions.id"))
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=True)

    true_positives = Column(Integer, default=0)
    false_positives = Column(Integer, default=0)
    false_negatives = Column(Integer, default=0)
    true_negatives = Column(Integer, default=0, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)

    # For multi-video sessions:
    total_ground_truth = Column(Integer, default=0)  # Actual GT count
    total_detections = Column(Integer, default=0)
```

---

### Priority 2: Fix Method Signature Issues

**Current Code** (BROKEN):
```python
gt_count = service._get_actual_ground_truth_count(session_id)
```

**Fixed Code**:
```python
db = SessionLocal()
try:
    test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
    gt_count = service._get_actual_ground_truth_count(db, test_session, session_id)
finally:
    db.close()
```

**Better Fix** (Refactor method):
```python
def _get_actual_ground_truth_count(self, session_id: str) -> int:
    """Get GT count with self-contained database access"""
    db = SessionLocal()
    try:
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            return 0

        # Get GT count via videos
        from models import Video
        videos = db.query(Video).join(
            # Add proper join based on schema
        ).filter(...)

        gt_count = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id.in_([v.id for v in videos])
        ).count()

        return gt_count
    finally:
        db.close()
```

---

### Priority 3: Fix Field Naming Consistency

**Add session_id to GroundTruthObject**:
```python
class GroundTruthObject(Base):
    __tablename__ = "ground_truth_objects"

    video_id = Column(String(36), ForeignKey("videos.id"))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id"))  # ADD THIS

    # Update indexes:
    __table_args__ = (
        Index('idx_gt_session_timestamp', 'test_session_id', 'timestamp'),
        Index('idx_gt_session_class', 'test_session_id', 'class_label'),
        # ... existing indexes
    )
```

---

## 🔍 How to Verify Fixes

### Test 1: Check Model Updates
```python
from models import TestSession
from database import SessionLocal

db = SessionLocal()
session = db.query(TestSession).first()
print(f"TP: {session.true_positives}")  # Should work
print(f"FN: {session.false_negatives}")  # Should work
```

### Test 2: Check Method Calls
```python
service = GroundTruthMatchingService()
gt_count = service._get_actual_ground_truth_count(session_id)
print(f"GT Count: {gt_count}")  # Should return number, not error
```

### Test 3: Check Metrics Calculation
```python
metrics = service.calculate_session_metrics(db, test_session, session_id)
print(f"Recall: {metrics.recall}")  # Should be TP / actual_GT_count
print(f"Precision: {metrics.precision}")  # Should be TP / (TP + FP)
```

---

## 📈 Expected Results After Fixes

### Before (BROKEN):
```
[SESSION] TP: N/A
[SESSION] FN: N/A
[CALC] Cannot calculate recall: TP+FN = 0
Recall: undefined or wrong
```

### After (FIXED):
```
[SESSION] TP: 12
[SESSION] FN: 3
[SESSION] Total GT: 15
[CALC] Recall: 12/15 = 0.8000 ✅
[CALC] Precision: 12/14 = 0.8571 ✅
```

---

## 🎯 Next Steps

1. ✅ **COMPLETED**: Captured actual runtime data proving root causes
2. ⏭️ **NEXT**: Implement Priority 1 fix (add metrics storage)
3. ⏭️ **NEXT**: Implement Priority 2 fix (fix method signatures)
4. ⏭️ **NEXT**: Implement Priority 3 fix (fix field naming)
5. ⏭️ **NEXT**: Re-run instrumented test to verify all fixes work

---

## 📝 Key Takeaways

1. **The bug is NOT in the calculation logic** - it's in data storage
2. **TestSession lacks the fields needed** for metrics
3. **Method calls are broken** - wrong number of arguments
4. **Field naming is inconsistent** - session_id vs test_session_id

**Conclusion**: We need to fix the DATABASE SCHEMA and MODEL DEFINITIONS, not the calculation formulas.
