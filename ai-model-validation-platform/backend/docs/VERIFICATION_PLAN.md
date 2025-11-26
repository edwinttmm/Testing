# Comprehensive Verification Plan for Bug Fixes

## Overview

This document outlines the verification plan for three critical bug fixes in the AI Model Validation Platform.

**Date Created**: 2025-11-21
**Test Session**: `e8e108b0-cb20-4cba-a2db-fc29f21efd16`
**Status**: Awaiting completion of fixes by coder agent

---

## Bugs Being Fixed

### 1. ✅ GT Aggregation Bug (ALREADY FIXED)

**Issue**: Ground truth count showing 41 instead of 257
**Root Cause**: Aggregation function only counting Video 1 GT (131) instead of both videos
**Fix Status**: COMPLETED by previous agent
**Expected Result**: 257 total GT objects (Video 1: 131 + Video 2: 126)

**Verification Query**:
```sql
SELECT COUNT(*) FROM ground_truth_objects
WHERE video_id IN (
    SELECT DISTINCT video_id FROM video_test_sequences
    WHERE test_session_id = 'e8e108b0-cb20-4cba-a2db-fc29f21efd16'
)
-- Expected: 257
```

---

### 2. ⏳ Duplicate Detection Sources (IN PROGRESS)

**Issue**: Both 'labjack' and 'dedicated_labjack_monitor' writing detections
**Root Cause**: Two detection services running simultaneously
**Current State**: 334 total detections (167 x 2 = 100% duplication)
**Fix Status**: Being fixed by coder agent

**Files Involved**:
- `services/labjack_detection_service.py` (line 2193: source='labjack')
- `services/dedicated_labjack_monitor.py` (lines 1365, 2099: source='dedicated_labjack_monitor')

**Expected Result**: Only ONE source active, 167 unique detections

**Verification Query**:
```sql
SELECT source, COUNT(*) as count
FROM detection_events
WHERE test_session_id = 'e8e108b0-cb20-4cba-a2db-fc29f21efd16'
GROUP BY source
-- Expected: Only ONE row with count=167
```

**Fix Options**:
1. **Option A**: Disable `labjack_detection_service.py` (comment out source assignment)
2. **Option B**: Disable `dedicated_labjack_monitor.py` (comment out source assignment)
3. **Option C**: Add configuration flag to enable/disable each service

**Recommended**: Option A - Keep only `dedicated_labjack_monitor` active

---

### 3. ⏳ Video 2 Timestamp Mismatch (IN PROGRESS)

**Issue**: Video 2 GT objects not matching detections (0.8% coverage)
**Root Cause**: Timestamp offset or tolerance window mismatch
**Current State**: Only 1 of 126 Video 2 GT objects matched
**Fix Status**: Being fixed by coder agent

**Expected Result**: At least 20% coverage (25+ GT objects matched)

**Verification Query**:
```sql
SELECT
    COUNT(DISTINCT gt.id) as matched_gt,
    (SELECT COUNT(*) FROM ground_truth_objects WHERE video_id = '550e3cf8-2755-42df-8c3c-041300735f93') as total_gt,
    ROUND(100.0 * COUNT(DISTINCT gt.id) / (SELECT COUNT(*) FROM ground_truth_objects WHERE video_id = '550e3cf8-2755-42df-8c3c-041300735f93'), 2) as coverage_pct
FROM detection_comparisons dc
JOIN ground_truth_objects gt ON dc.ground_truth_id = gt.id
WHERE gt.video_id = '550e3cf8-2755-42df-8c3c-041300735f93'
AND dc.is_match = 1
-- Expected: coverage_pct >= 20
```

**Potential Fixes**:
1. Adjust timestamp normalization for Video 2
2. Increase tolerance window for Video 2
3. Apply drift compensation/offset correction
4. Review Video 2 ground truth timestamp format

---

## Verification Script

**Location**: `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/verify_all_fixes.sh`

**Usage**:
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
./scripts/verify_all_fixes.sh
```

**Exit Codes**:
- `0`: All tests passed
- `1`: One or more tests failed
- `2`: Warnings detected

---

## Verification Steps

### Step 1: Run Verification Script

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
source venv/bin/activate
./scripts/verify_all_fixes.sh
```

### Step 2: Review Individual Checks

The script performs 4 comprehensive checks:

#### Check 1: Detection Source Verification
- **Pass**: Only ONE source active
- **Fail**: Multiple sources with equal counts (duplication)
- **Warning**: Multiple sources with different counts

#### Check 2: GT Aggregation Verification
- **Pass**: Total GT count = 257
- **Fail**: Total GT count = 131 (only Video 1)
- **Warning**: Unexpected GT count

#### Check 3: Video 2 Matching Verification
- **Pass**: Coverage >= 20%
- **Partial**: Coverage 5-20%
- **Fail**: Coverage < 5%

#### Check 4: Metrics Calculation Verification
- **Pass**: Stored metrics match calculated metrics
- **Warning**: Metrics need recalculation

### Step 3: Manual Verification (Optional)

If automated checks fail, perform manual verification:

```bash
# Connect to database
python3 << 'EOF'
from sqlalchemy import create_engine, text
from config_settings import Settings

engine = create_engine(Settings().database_url)
with engine.connect() as conn:
    # Check 1: Detection Sources
    print("=== Detection Sources ===")
    sources = conn.execute(text("""
        SELECT source, COUNT(*) FROM detection_events
        WHERE test_session_id = 'e8e108b0-cb20-4cba-a2db-fc29f21efd16'
        GROUP BY source
    """)).fetchall()
    for source, count in sources:
        print(f"{source}: {count}")

    # Check 2: GT Aggregation
    print("\n=== GT Aggregation ===")
    gt_count = conn.execute(text("""
        SELECT COUNT(*) FROM ground_truth_objects
        WHERE video_id IN (
            SELECT DISTINCT video_id FROM video_test_sequences
            WHERE test_session_id = 'e8e108b0-cb20-4cba-a2db-fc29f21efd16'
        )
    """)).scalar()
    print(f"Total GT: {gt_count}")

    # Check 3: Video 2 Matching
    print("\n=== Video 2 Matching ===")
    video2_stats = conn.execute(text("""
        SELECT
            COUNT(*) as total_gt,
            SUM(CASE WHEN dc.is_match = 1 THEN 1 ELSE 0 END) as matched_gt
        FROM ground_truth_objects gt
        LEFT JOIN detection_comparisons dc ON gt.id = dc.ground_truth_id
        WHERE gt.video_id = '550e3cf8-2755-42df-8c3c-041300735f93'
    """)).fetchone()
    total, matched = video2_stats
    print(f"Video 2 GT: {total}, Matched: {matched}, Coverage: {matched/total*100:.2f}%")
EOF
```

---

## Success Criteria

All fixes are considered successfully implemented when:

1. **Detection Sources**: Only ONE source active
   - `SELECT COUNT(DISTINCT source) FROM detection_events WHERE test_session_id = '...'` returns 1

2. **GT Aggregation**: Total count = 257
   - `SELECT COUNT(*) FROM ground_truth_objects WHERE video_id IN (...)` returns 257

3. **Video 2 Matching**: Coverage >= 20%
   - At least 25 of 126 Video 2 GT objects matched to detections

4. **Metrics Calculation**: Stored metrics match calculated
   - Precision, Recall, F1 calculated from correct GT count (257) and unique detections (167)

---

## Post-Verification Actions

### If All Checks Pass
1. Run full test suite: `pytest tests/`
2. Verify API endpoints return correct metrics
3. Update documentation with fix details
4. Close related issue tickets

### If Checks Fail
1. Review failure details from verification script
2. Check coder agent's implementation
3. Review relevant code files
4. Re-run verification after fixes
5. Consider rollback if issues persist

---

## Code Review Checklist

When reviewing the coder agent's fixes, verify:

### Detection Source Fix
- [ ] Only ONE detection service writes to database
- [ ] Source field is consistent across all detections
- [ ] No duplicate timestamps in detection_events table
- [ ] Service startup configuration correct

### GT Aggregation Fix
- [ ] `aggregate_ground_truth()` function counts all videos
- [ ] `video_test_sequences` table properly joined
- [ ] Multi-video sessions handled correctly
- [ ] Edge cases tested (single video, multiple videos)

### Video 2 Matching Fix
- [ ] Timestamp normalization consistent across videos
- [ ] Tolerance window appropriate for Video 2
- [ ] Drift compensation applied if needed
- [ ] Ground truth timestamps validated

### Metrics Calculation Fix
- [ ] Uses correct GT count (257, not 131)
- [ ] Uses non-duplicate detections (167, not 334)
- [ ] Precision = TP / (TP + FP)
- [ ] Recall = TP / (TP + FN)
- [ ] F1 = 2 * (Precision * Recall) / (Precision + Recall)

---

## Expected Timeline

1. **Coder Agent Fixes**: 15-30 minutes
   - Implement detection source fix
   - Verify GT aggregation fix
   - Implement Video 2 matching fix

2. **Verification**: 5-10 minutes
   - Run automated verification script
   - Review results
   - Perform manual checks if needed

3. **Review**: 10-15 minutes
   - Code review by reviewer agent
   - Documentation updates
   - Final validation

**Total Estimated Time**: 30-55 minutes

---

## Contact Information

**Reviewer**: Code Review Agent
**Coder**: Implementation Agent
**Tester**: Verification Script (`verify_all_fixes.sh`)

---

## Appendix: Key Database Queries

### Check Detection Source Status
```sql
SELECT source, COUNT(*) as count,
       MIN(timestamp) as first_detection,
       MAX(timestamp) as last_detection
FROM detection_events
WHERE test_session_id = 'e8e108b0-cb20-4cba-a2db-fc29f21efd16'
GROUP BY source
ORDER BY count DESC;
```

### Check GT Aggregation
```sql
SELECT
    vts.video_id,
    COUNT(gt.id) as gt_count
FROM video_test_sequences vts
LEFT JOIN ground_truth_objects gt ON vts.video_id = gt.video_id
WHERE vts.test_session_id = 'e8e108b0-cb20-4cba-a2db-fc29f21efd16'
GROUP BY vts.video_id
ORDER BY vts.video_id;
```

### Check Video 2 Matching Details
```sql
SELECT
    gt.id as gt_id,
    gt.timestamp as gt_timestamp,
    de.id as detection_id,
    de.timestamp as detection_timestamp,
    dc.temporal_offset_ms,
    dc.is_match
FROM ground_truth_objects gt
LEFT JOIN detection_comparisons dc ON gt.id = dc.ground_truth_id
LEFT JOIN detection_events de ON dc.detection_event_id = de.id
WHERE gt.video_id = '550e3cf8-2755-42df-8c3c-041300735f93'
ORDER BY gt.timestamp
LIMIT 10;
```

### Verify Metrics Calculation
```sql
SELECT
    ts.id,
    ts.accuracy_f1_score as stored_f1,
    ts.accuracy_precision as stored_precision,
    ts.accuracy_recall as stored_recall,
    -- Calculated metrics
    (SELECT SUM(CASE WHEN is_match = 1 THEN 1 ELSE 0 END)
     FROM detection_comparisons WHERE test_session_id = ts.id) as tp,
    (SELECT SUM(CASE WHEN is_match = 0 AND detection_event_id IS NOT NULL THEN 1 ELSE 0 END)
     FROM detection_comparisons WHERE test_session_id = ts.id) as fp,
    (SELECT SUM(CASE WHEN detection_event_id IS NULL THEN 1 ELSE 0 END)
     FROM detection_comparisons WHERE test_session_id = ts.id) as fn
FROM test_sessions ts
WHERE ts.id = 'e8e108b0-cb20-4cba-a2db-fc29f21efd16';
```

---

## Version History

- **v1.0** (2025-11-21): Initial verification plan created
- Awaiting fixes from coder agent before running verification
