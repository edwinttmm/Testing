# Ground Truth 514 Object Bug - Root Cause Analysis & Remediation

## Executive Summary

**Session ID:** `6c899aa4-bbd2-4a93-b052-f09e4e11889c`
**Problem:** Session shows 514 ground truth objects when it should be ~240 (2 videos × ~120 objects each)
**Root Cause:** Duplicate ground truth objects stored with both enum format (`VRUTypeEnum.PEDESTRIAN`) and string format (`pedestrian`)
**Impact:** 257 duplicate records across 2 videos (~100% duplication rate)

---

## Database Audit Results

### Session Details
- **Session ID:** `6c899aa4-bbd2-4a93-b052-f09e4e11889c`
- **Name:** "Video Sequence Test - 2025-11-05 20:18"
- **Status:** completed
- **Has Video Sequence:** Yes
- **Sequence ID:** `390a175e-832c-4960-ac31-43859b7c0e87`

### Videos in Session
1. **Video 1:** `10c2b16c-86fa-4140-b1cf-c0ea42f82ca5`
   - **Expected GT objects:** ~121 (121 unique timestamps)
   - **Actual GT objects:** 262
   - **Extra objects:** 141 (116.5% duplication)
   - **Status:** pending

2. **Video 2:** `550e3cf8-2755-42df-8c3c-041300735f93`
   - **Expected GT objects:** ~121 (121 unique timestamps)
   - **Actual GT objects:** 252
   - **Extra objects:** 131 (108.3% duplication)
   - **Status:** pending

**Total Active GT:** 514 objects
**Expected Total GT:** ~240 objects
**Duplicates:** 257 objects (50% of total)

---

## Root Cause Analysis

### 1. Class Label Duplication Pattern

Both videos have ground truth objects stored with **two different class label formats**:

**Video 1 Class Labels:**
```
'VRUTypeEnum.PEDESTRIAN': 121 objects  ❌ DUPLICATE (enum format)
'pedestrian':             121 objects  ✅ CORRECT
'VRUTypeEnum.CYCLIST':     10 objects  ❌ DUPLICATE (enum format)
'cyclist':                 10 objects  ✅ CORRECT
```

**Video 2 Class Labels:**
```
'VRUTypeEnum.PEDESTRIAN': 121 objects  ❌ DUPLICATE (enum format)
'pedestrian':             121 objects  ✅ CORRECT
'VRUTypeEnum.CYCLIST':      5 objects  ❌ DUPLICATE (enum format)
'cyclist':                  5 objects  ✅ CORRECT
```

### 2. Source of Bug

The duplicate class labels are created by **improper enum serialization** where both:
- **Enum string representation** (`VRUTypeEnum.PEDESTRIAN`) - Python's `str(enum)` representation
- **Enum value** (`pedestrian`) - The actual enum value

...are being stored as separate ground truth objects.

### 3. Timestamp Analysis

- Both videos have identical timestamp ranges: **0.00s to 5.00s**
- Both have **121 unique timestamps**
- No duplicate frame/timestamp combinations (after grouping by class_label)
- Ground truth created on **2025-10-31** (several days before test session)

### 4. No Spatial Duplication

When checking for spatially duplicate objects (same timestamp, frame, bounding box), **no duplicates were found**. This confirms the issue is purely **class label formatting**, not repeated detections.

---

## Impact Analysis

### Database Impact
- **257 extra records** consuming storage
- **Inflated ground truth counts** in UI and reports
- **Incorrect metrics** for ground truth validation
- **Soft delete support** means records remain but marked as deleted

### User-Facing Impact
- Session shows **514 objects** instead of **~240**
- Ground truth count per video appears **doubled**
- Metrics calculations may be incorrect
- UI displays duplicate detections with different labels

### System Performance
- Queries on ground truth return **2x the expected results**
- Increased memory usage in result processing
- Slower ground truth matching algorithms

---

## Code Analysis

### Ground Truth Service (`services/ground_truth_service.py`)

The ground truth service uses YOLO for detection and stores results with:

```python
# Line 443-455: Detection storage
detection = {
    "frame_number": frame_count,
    "timestamp": timestamp,
    "class_label": self.vru_classes[class_id],  # ✅ Stores string value
    "x": float(x1),
    "y": float(y1),
    "width": float(x2 - x1),
    "height": float(y2 - y1),
    "confidence": confidence,
    "validated": True,
    "difficult": False,
    "screenshot_path": screenshot_path,
    "screenshot_zoom_path": screenshot_zoom_path
}
```

The service correctly stores **string values** (`'pedestrian'`, `'cyclist'`).

### Suspected Import/Upload Path

The duplicate `VRUTypeEnum.PEDESTRIAN` format suggests:
1. **CSV/JSON import** converting enum objects incorrectly
2. **Frontend upload** serializing enum as `str(enum)` instead of `enum.value`
3. **API endpoint** accepting both formats without validation
4. **Annotation tool** storing enum class name instead of value

---

## Remediation Plan

### Phase 1: Immediate Cleanup (SQL Execution)

**Soft delete all 257 duplicate records with VRUTypeEnum. prefix:**

```sql
-- Soft delete duplicate ground truth objects with VRUTypeEnum. prefix
UPDATE ground_truth_objects
SET deleted_at = datetime('now'),
    deleted_by = 'system_cleanup'
WHERE class_label LIKE 'VRUTypeEnum.%'
AND deleted_at IS NULL;
```

**Verification query:**
```sql
SELECT video_id, class_label, COUNT(*) as count
FROM ground_truth_objects
WHERE deleted_at IS NULL
AND video_id IN (
    '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5',
    '550e3cf8-2755-42df-8c3c-041300735f93'
)
GROUP BY video_id, class_label;
```

**Expected result after cleanup:**
```
Video 10c2b16c...: pedestrian (121), cyclist (10)  = 131 objects
Video 550e3cf8...: pedestrian (121), cyclist (5)   = 126 objects
Total: 257 objects (was 514 before cleanup)
```

### Phase 2: Prevent Future Duplicates

**1. Add Database Constraint:**
```python
# In models.py - Add validation to GroundTruthObject
@validates('class_label')
def validate_class_label(self, key, class_label):
    """Prevent VRUTypeEnum. prefix from being stored"""
    if isinstance(class_label, str) and class_label.startswith('VRUTypeEnum.'):
        # Strip enum prefix and convert to lowercase value
        return class_label.replace('VRUTypeEnum.', '').lower()
    return class_label
```

**2. Add API Input Validation:**
```python
# In ground truth upload endpoints
def normalize_vru_type(class_label: str) -> str:
    """Normalize VRU type to lowercase string value"""
    if class_label.startswith('VRUTypeEnum.'):
        return class_label.replace('VRUTypeEnum.', '').lower()
    return class_label.lower()
```

**3. Add Schema Validation:**
```python
# In schemas.py - GroundTruthObject
class GroundTruthObject(CamelCaseModel):
    class_label: str

    @field_validator('class_label')
    @classmethod
    def normalize_class_label(cls, v):
        """Strip enum prefix if present"""
        if v.startswith('VRUTypeEnum.'):
            return v.replace('VRUTypeEnum.', '').lower()
        return v
```

### Phase 3: Data Integrity Verification

**1. Check all ground truth records for enum prefixes:**
```sql
SELECT
    class_label,
    COUNT(*) as count,
    COUNT(DISTINCT video_id) as video_count
FROM ground_truth_objects
WHERE deleted_at IS NULL
AND class_label LIKE '%Enum.%'
GROUP BY class_label;
```

**2. Verify no other sessions affected:**
```sql
SELECT
    ts.id as session_id,
    ts.name,
    COUNT(DISTINCT gt.class_label) as label_count,
    GROUP_CONCAT(DISTINCT gt.class_label) as labels
FROM test_sessions ts
JOIN video_test_sequences vts ON vts.test_session_id = ts.id
JOIN sequence_video_results svr ON svr.video_sequence_id = vts.id
JOIN ground_truth_objects gt ON gt.video_id = svr.video_id
WHERE gt.deleted_at IS NULL
GROUP BY ts.id
HAVING label_count > 2;
```

---

## Cleanup SQL Commands

### Execute Soft Delete

```sql
-- Backup verification before cleanup
SELECT
    video_id,
    class_label,
    COUNT(*) as count
FROM ground_truth_objects
WHERE deleted_at IS NULL
GROUP BY video_id, class_label
ORDER BY video_id, class_label;

-- Soft delete all VRUTypeEnum. prefixed records
UPDATE ground_truth_objects
SET deleted_at = datetime('now'),
    deleted_by = 'system_cleanup_agent7'
WHERE class_label LIKE 'VRUTypeEnum.%'
AND deleted_at IS NULL;

-- Verify cleanup
SELECT
    video_id,
    class_label,
    COUNT(*) as count
FROM ground_truth_objects
WHERE deleted_at IS NULL
AND video_id IN (
    '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5',
    '550e3cf8-2755-42df-8c3c-041300735f93'
)
GROUP BY video_id, class_label;

-- Count deleted records
SELECT COUNT(*) as deleted_count
FROM ground_truth_objects
WHERE deleted_by = 'system_cleanup_agent7';
```

### Verify Session Ground Truth Count

```sql
-- Check session ground truth totals
SELECT
    svr.video_id,
    v.filename,
    COUNT(gt.id) as gt_count
FROM sequence_video_results svr
JOIN videos v ON v.id = svr.video_id
LEFT JOIN ground_truth_objects gt ON gt.video_id = svr.video_id AND gt.deleted_at IS NULL
WHERE svr.video_sequence_id IN (
    SELECT id FROM video_test_sequences WHERE test_session_id = '6c899aa4-bbd2-4a93-b052-f09e4e11889c'
)
GROUP BY svr.video_id;
```

---

## Expected Results After Cleanup

### Before Cleanup
```
Session 6c899aa4-bbd2-4a93-b052-f09e4e11889c
├─ Video 1 (10c2b16c...): 262 GT objects
│  ├─ VRUTypeEnum.PEDESTRIAN: 121 (DUPLICATE)
│  ├─ pedestrian: 121
│  ├─ VRUTypeEnum.CYCLIST: 10 (DUPLICATE)
│  └─ cyclist: 10
├─ Video 2 (550e3cf8...): 252 GT objects
│  ├─ VRUTypeEnum.PEDESTRIAN: 121 (DUPLICATE)
│  ├─ pedestrian: 121
│  ├─ VRUTypeEnum.CYCLIST: 5 (DUPLICATE)
│  └─ cyclist: 5
└─ TOTAL: 514 GT objects
```

### After Cleanup
```
Session 6c899aa4-bbd2-4a93-b052-f09e4e11889c
├─ Video 1 (10c2b16c...): 131 GT objects
│  ├─ pedestrian: 121
│  └─ cyclist: 10
├─ Video 2 (550e3cf8...): 126 GT objects
│  ├─ pedestrian: 121
│  └─ cyclist: 5
└─ TOTAL: 257 GT objects (50% reduction)
```

---

## Files to Review for Prevention

1. **Ground Truth Import:**
   - `/home/rigade/Testing/ai-model-validation-platform/backend/routers/ground_truth.py`
   - `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_service.py`

2. **Ground Truth Upload:**
   - `/home/rigade/Testing/ai-model-validation-platform/backend/routers/datasets.py`
   - Any CSV/JSON import handlers

3. **Enum Serialization:**
   - `/home/rigade/Testing/ai-model-validation-platform/backend/schemas.py` (VRUType enum)
   - API response serialization

4. **Detection Event Storage:**
   - `/home/rigade/Testing/ai-model-validation-platform/backend/crud.py`
   - `create_ground_truth_object()` function

---

## Recommendations

1. **Immediate:** Execute cleanup SQL to soft-delete 257 duplicate records
2. **Short-term:** Add input validation to prevent `VRUTypeEnum.` prefix
3. **Medium-term:** Add database migration to normalize existing class_label values
4. **Long-term:** Implement comprehensive enum serialization testing

---

## Testing Verification

After cleanup, verify:

```bash
# 1. Check ground truth counts via API
curl http://localhost:8000/api/test-sessions/6c899aa4-bbd2-4a93-b052-f09e4e11889c

# 2. Check video ground truth stats
curl http://localhost:8000/api/ground-truth/videos/10c2b16c-86fa-4140-b1cf-c0ea42f82ca5/stats
curl http://localhost:8000/api/ground-truth/videos/550e3cf8-2755-42df-8c3c-041300735f93/stats

# 3. Run test session to verify metrics are correct
```

---

## Conclusion

**Root Cause:** Enum serialization bug causing duplicate ground truth objects to be stored with both `VRUTypeEnum.PEDESTRIAN` format and `pedestrian` format.

**Impact:** 514 objects shown instead of ~240 (100% duplication)

**Solution:** Soft delete 257 duplicate records with `VRUTypeEnum.` prefix and add validation to prevent future occurrences.

**Status:** Ready for cleanup execution

---

**Report Generated:** 2025-11-05
**Agent:** Agent 7 - Ground Truth Audit
**Session:** 6c899aa4-bbd2-4a93-b052-f09e4e11889c
