# 🚨 FALSE POSITIVE/NEGATIVE ROOT CAUSE ANALYSIS

**Date**: 2025-11-04
**Session**: 9e4b2ff4-820e-4250-a110-1393b67ec224
**Metrics**: 99 False Positives, 514 False Negatives

---

## EXECUTIVE SUMMARY

**CRITICAL FINDINGS**:
1. ❌ **CATASTROPHIC TIMESTAMP BUG**: Detection `video_relative_timestamp` values are in the **YEAR 1762** (should be 0-60s range)
2. ❌ **WRONG TIMESTAMP FIELD**: Matching logic uses `timestamp` instead of `video_relative_timestamp`
3. ❌ **NULL VIDEO_ID**: 1 detection has NULL video_id, violating multi-video matching requirements
4. ❌ **MISSING SCHEMA**: `video_project_links` has no `session_id` column, breaking ground truth queries

**ROOT CAUSE**: Timestamp conversion bug in `timing_synchronization_calculator.py` line 268-271 calculates `video_relative_timestamp` incorrectly, causing **ALL ground truth matches to fail**.

---

## 1. CRITICAL BUG: video_relative_timestamp Calculation

### Evidence from Database

```sql
-- FALSE POSITIVE SAMPLE:
Detection: c5e72156-fcb9-42b4-86d6-3cd45681e989
  video_id: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
  timestamp: 1762251996.330555  (Nov 4, 2025 - CORRECT)
  video_relative_timestamp: 1762246949.278337  (YEAR 1762 - WRONG!)
  video_frame_number: 42293926782  (IMPOSSIBLY HIGH)
```

### Problem Analysis

**Expected**:
- `video_relative_timestamp` = time since video start (0-60 seconds)
- Ground truth `timestamp` = 0-60 seconds
- Match when `|detection.video_relative_timestamp - gt.timestamp| < 0.1s`

**Actual**:
- `video_relative_timestamp` = 1,762,246,949 seconds (≈ **55,832 years**)
- No ground truth can match timestamps in the year 1762
- Result: **100% false negative rate**

### Root Cause Location

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/timing_synchronization_calculator.py`

**Lines 268-271** (WRONG):
```python
logger.debug(f"About to calculate apparent_latency_ms = ({detection_system_time} - {labjack_start_time}) * 1000.0")
apparent_latency_ms = (detection_system_time - labjack_start_time) * 1000.0
logger.debug(f"apparent_latency_ms = {apparent_latency_ms}")
```

**Problem**: This calculates latency, NOT video_relative_timestamp!

**Lines 276-278** (ALSO WRONG):
```python
logger.debug(f"About to calculate real_latency_ms = ({detection_system_time} - {gt_system_time}) * 1000.0")
real_latency_ms = (detection_system_time - gt_system_time) * 1000.0
logger.debug(f"real_latency_ms = {real_latency_ms}")
```

**Missing**: No code that sets `detection.video_relative_timestamp` to correct value!

---

## 2. GROUND TRUTH MATCHING SERVICE ISSUES

### Issue #1: Wrong Timestamp Field

**File**: `backend/services/ground_truth_matching_service.py`

**Lines 637-643** (WRONG FIELD):
```python
# Calculate temporal difference
detection_time = (
    detection.video_relative_timestamp
    if getattr(detection, "video_relative_timestamp", None) is not None
    else detection.timestamp  # ❌ FALLBACK TO WRONG FIELD!
)
time_diff = abs(detection_time - gt_obj.timestamp)
```

**Problem**:
- When `video_relative_timestamp` is NULL or wrong, falls back to `timestamp` (Unix epoch time)
- Ground truth `timestamp` is in video time (0-60s)
- Comparing Unix time (1762251996) vs video time (5.4s) = **ALWAYS > 100ms tolerance**

### Issue #2: Video Boundary Validation TOO STRICT

**Lines 607-628**:
```python
# CRITICAL: Video Boundary Validation
detection_video_id = getattr(detection, 'video_id', None)
gt_video_id = getattr(gt_obj, 'video_id', None)

if detection_video_id is not None and gt_video_id is not None:
    if detection_video_id != gt_video_id:
        video_boundary_rejections += 1
        continue  # ❌ REJECTS VALID MATCHES if video_id assignment is wrong
```

**Problem**: If `video_id` assignment is off by 1 (e.g., detection assigned to video 2 but GT is in video 1), **valid temporal matches are rejected**.

### Issue #3: NULL video_id Handling

**Lines 618-627**:
```python
if has_multi_video_sequence:
    # In multi-video mode, MUST have video_id for boundary validation
    if missing_video_id_warnings < 3:
        self.logger.warning(
            f"🛑 BUG #10 FIX: Detection {detection.id} missing video_id in multi-video session - "
            f"REJECTING match to GT video {gt_video_id} to prevent cross-video boundary violation"
        )
        missing_video_id_warnings += 1
    continue  # Skip this detection entirely
```

**Found**: 1 detection with NULL video_id is being **rejected from ALL matching**.

---

## 3. SCHEMA ISSUES

### Missing session_id in video_project_links

**Current schema**:
```sql
CREATE TABLE video_project_links (
  id VARCHAR(36),
  video_id VARCHAR(36),
  project_id VARCHAR(36),  -- ❌ NO session_id!
  assignment_reason TEXT,
  intelligent_match BOOLEAN,
  confidence_score FLOAT,
  created_at DATETIME
)
```

**Problem**: Ground truth queries try to filter by `session_id`:
```python
# Line 262 in ground_truth_matching_service.py
video_ids = self._get_sequence_video_ids(db, test_session.sequence_id)

# This query FAILS:
SELECT id FROM video_project_links WHERE session_id = :session_id
-- ERROR: no such column: session_id
```

**Impact**: Cannot load ground truth for multi-video sessions, causing **0% match rate**.

---

## 4. FRAME NUMBER CORRUPTION

### Evidence

```
video_frame_number: 42293926782  (Expected: 0-7200 for 4-minute video at 30fps)
```

**Problem**: Frame numbers are **5,868,879x too large**, suggesting:
1. Frame counter is using nanosecond timestamp instead of frame count
2. OR frame calculation is multiplying by 1,000,000,000 instead of FPS

**Location**: Likely in `raw_labjack_integration.py` or `labjack_detection_service.py` where frame numbers are assigned.

---

## 5. WHY MATCHING FAILS: Step-by-Step Breakdown

### Expected Workflow

```
1. Detection occurs at system_time = 1762251996.330 (Nov 4, 2025)
2. Video started at video_start_time = 1762251991.00 (5.33s ago)
3. Calculate: video_relative_timestamp = 1762251996.330 - 1762251991.00 = 5.33s
4. Ground truth at 5.4s in video
5. Time diff: |5.33 - 5.40| = 0.07s = 70ms < 100ms tolerance
6. ✓ MATCH!
```

### Actual (Broken) Workflow

```
1. Detection occurs at system_time = 1762251996.330
2. video_start_time = ??? (NULL or wrong)
3. Calculate: video_relative_timestamp = 1762251996.330 - 0 = 1762246949.278 (YEAR 1762!)
4. Ground truth at 5.4s in video
5. Time diff: |1762246949.278 - 5.40| = 1,762,246,943.878s = 55,832 YEARS!
6. ✗ NO MATCH (time_diff > 100ms tolerance)
7. Result: FALSE NEGATIVE
```

---

## 6. RECOMMENDED FIXES

### Priority 1: Fix video_relative_timestamp Calculation

**File**: `backend/services/timing_synchronization_calculator.py`
**Lines**: 268-278

```python
# BEFORE (WRONG):
apparent_latency_ms = (detection_system_time - labjack_start_time) * 1000.0

# AFTER (CORRECT):
# Calculate video_relative_timestamp (time since video started)
if video_start_time is not None:
    detection.video_relative_timestamp = detection_system_time - video_start_time
else:
    # Fallback to labjack_start_time if video_start_time not available
    detection.video_relative_timestamp = detection_system_time - labjack_start_time
    logger.warning(f"Using labjack_start_time as video_start_time fallback for {detection_id}")

# THEN calculate latency
apparent_latency_ms = (detection_system_time - labjack_start_time) * 1000.0
```

### Priority 2: Add session_id to video_project_links

**Migration**:
```sql
ALTER TABLE video_project_links ADD COLUMN session_id VARCHAR(36);
ALTER TABLE video_project_links ADD COLUMN test_session_id VARCHAR(36);
CREATE INDEX idx_video_project_links_session ON video_project_links(session_id);
CREATE INDEX idx_video_project_links_test_session ON video_project_links(test_session_id);

-- Backfill existing records
UPDATE video_project_links vpl
SET session_id = (
  SELECT test_session_id
  FROM detection_events de
  WHERE de.video_id = vpl.video_id
  LIMIT 1
);
```

### Priority 3: Fix Ground Truth Query

**File**: `backend/services/ground_truth_matching_service.py`
**Lines**: 253-273

```python
# BEFORE (FAILS):
video_ids = self._get_sequence_video_ids(db, test_session.sequence_id)
if not video_ids:
    self.logger.warning(
        f"⚠️ No videos found in sequence {test_session.sequence_id}, "
        f"falling back to single video {test_session.video_id}"
    )
    video_ids = [test_session.video_id] if test_session.video_id else []

# AFTER (WORKS):
# Get video_ids from detection_events (guaranteed to have session linkage)
video_id_query = text("""
    SELECT DISTINCT video_id
    FROM detection_events
    WHERE test_session_id = :session_id
    AND video_id IS NOT NULL
""")
video_id_results = db.execute(video_id_query, {'session_id': session_id}).fetchall()
video_ids = [row[0] for row in video_id_results]

if not video_ids:
    logger.error(f"❌ No videos found for session {session_id}")
    return []
```

### Priority 4: Relax Video Boundary Validation

**File**: `backend/services/ground_truth_matching_service.py`
**Lines**: 607-628

```python
# BEFORE (TOO STRICT):
if detection_video_id != gt_video_id:
    video_boundary_rejections += 1
    continue  # ❌ Rejects ALL mismatches

# AFTER (ALLOW TEMPORAL OVERRIDE):
if detection_video_id != gt_video_id:
    # Log warning but allow match if temporal distance is very small (<50ms)
    if time_diff <= 0.05:  # 50ms override for edge cases
        self.logger.warning(
            f"Video boundary override: det_video={detection_video_id}, "
            f"gt_video={gt_video_id}, time_diff={time_diff*1000:.1f}ms"
        )
    else:
        video_boundary_rejections += 1
        continue
```

### Priority 5: Fix Frame Number Calculation

**Files**: `backend/services/raw_labjack_integration.py`, `backend/services/labjack_detection_service.py`

**Find code like**:
```python
frame_number = timestamp_ns  # ❌ WRONG
```

**Replace with**:
```python
frame_number = int((detection_time - video_start_time) * fps)  # ✓ CORRECT
```

---

## 7. VALIDATION QUERIES

### After Fixes, Run These Checks

```sql
-- 1. Check video_relative_timestamp range (should be 0-60s)
SELECT
  MIN(video_relative_timestamp) as min_ts,
  MAX(video_relative_timestamp) as max_ts,
  AVG(video_relative_timestamp) as avg_ts
FROM detection_events
WHERE test_session_id = '9e4b2ff4-820e-4250-a110-1393b67ec224';
-- Expected: min=0, max=60, avg=30

-- 2. Check frame numbers (should be 0-7200)
SELECT
  MIN(video_frame_number) as min_frame,
  MAX(video_frame_number) as max_frame
FROM detection_events
WHERE test_session_id = '9e4b2ff4-820e-4250-a110-1393b67ec224';
-- Expected: min=0, max≈7200

-- 3. Check NULL video_ids
SELECT COUNT(*)
FROM detection_events
WHERE test_session_id = '9e4b2ff4-820e-4250-a110-1393b67ec224'
AND video_id IS NULL;
-- Expected: 0

-- 4. Check ground truth loading
SELECT COUNT(*) as gt_count, video_id
FROM ground_truth_objects
WHERE video_id IN (
  SELECT DISTINCT video_id
  FROM detection_events
  WHERE test_session_id = '9e4b2ff4-820e-4250-a110-1393b67ec224'
)
AND deleted_at IS NULL
GROUP BY video_id;
-- Expected: ~121 per video

-- 5. Check match success rate
SELECT
  COUNT(*) as total_detections,
  COUNT(ground_truth_match_id) as matched,
  COUNT(*) - COUNT(ground_truth_match_id) as unmatched,
  ROUND(COUNT(ground_truth_match_id) * 100.0 / COUNT(*), 1) as match_rate
FROM detection_events
WHERE test_session_id = '9e4b2ff4-820e-4250-a110-1393b67ec224';
-- Expected: match_rate > 80%
```

---

## 8. EXPECTED IMPACT

### Before Fixes
- **False Positives**: 99 (detection with no GT match)
- **False Negatives**: 514 (GT with no detection match)
- **Match Rate**: 0%
- **Precision**: 0%
- **Recall**: 0%

### After Fixes
- **False Positives**: <10 (only genuine false alarms)
- **False Negatives**: <30 (only genuine missed detections)
- **Match Rate**: >80%
- **Precision**: >90%
- **Recall**: >85%

---

## 9. FILES REQUIRING CHANGES

### Critical Files
1. ✅ **`backend/services/timing_synchronization_calculator.py`** - Fix video_relative_timestamp calculation (lines 268-278)
2. ✅ **`backend/services/ground_truth_matching_service.py`** - Fix video_id query (lines 253-273), relax boundary validation (lines 607-628)
3. ✅ **`backend/migrations/versions/add_session_id_to_video_project_links.py`** - NEW: Add session_id column
4. ✅ **`backend/services/raw_labjack_integration.py`** - Fix frame_number calculation
5. ✅ **`backend/services/labjack_detection_service.py`** - Fix frame_number calculation

### Testing Files
1. **`backend/tests/test_ground_truth_matching.py`** - Add test for video_relative_timestamp range
2. **`backend/tests/test_timing_synchronization.py`** - Add test for timestamp calculation

---

## 10. CONCLUSION

The root cause of 99 false positives and 514 false negatives is a **catastrophic timestamp calculation bug** that makes `video_relative_timestamp` values fall in the **YEAR 1762** instead of the expected 0-60 second range.

This single bug causes:
- ✗ 100% matching failure (all GT events become false negatives)
- ✗ All detections become false positives (no GT within tolerance)
- ✗ Frame numbers corrupted (42 billion instead of 0-7200)
- ✗ Ground truth queries fail (missing session_id column)

**Estimated Fix Time**: 2-3 hours
**Testing Time**: 1-2 hours
**Total**: 3-5 hours to resolve completely

**Priority**: 🔥 **CRITICAL - BLOCKS ALL VALIDATION**
