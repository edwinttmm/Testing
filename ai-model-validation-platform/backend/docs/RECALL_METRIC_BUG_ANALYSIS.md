# RECALL METRIC BUG ANALYSIS - Session fa204ef2-9d8b-4480-9692-86e338c1218a

## CRITICAL FINDING: Recall Metric Displaying 100% When Actual Is 36%

**Discovery Date:** 2025-11-24
**Severity:** HIGH - False confidence in validation results
**Impact:** Users see "Recall 100.0%" but actual recall is only 36% (87/242)

---

## 1. PROBLEM STATEMENT

### User-Reported Issue
Session `fa204ef2-9d8b-4480-9692-86e338c1218a` displays:
- **UI Display**: "Recall 100.0%"
- **Also Shows**: "87 TP / 242 Ground Truth Events"
- **Actual Calculation**: 87 ÷ 242 = **0.3595 = 35.95%** (NOT 100%)

This is a **critical metric calculation bug** giving false confidence in test results.

---

## 2. RECALL CALCULATION LOCATION

### File: `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py`

**Function:** `_calculate_and_store_metrics()` (Lines 1612-1780)

#### Correct Recall Calculation (Line 1683):
```python
recall = true_positives / actual_gt_count if actual_gt_count > 0 else 0.0
```

Where:
- `true_positives` = 87 (TP count from database)
- `actual_gt_count` = Retrieved via `_get_actual_ground_truth_count()`

**Formula:** `recall = TP / (TP + FN)` = `TP / total_ground_truth`

---

## 3. ROOT CAUSE ANALYSIS

### Hypothesis: Per-Video vs Session-Wide Metric Confusion

The bug likely stems from **mixing per-video recall with session-wide recall**:

#### A) Per-Video Recall (Can Be 100%)
```python
# For a SINGLE video in the sequence
per_video_recall = video_tp / (video_tp + video_fn)
# Example: Video 3 might have 10 TP / 10 GT = 100% recall
```

#### B) Session-Wide Recall (Should Be 36%)
```python
# For ALL videos in the session
session_recall = total_tp / total_gt_across_all_videos
# Actual: 87 TP / 242 GT = 36% recall
```

### Suspected Issue Locations

1. **API Response Construction** (`routers/test_sessions.py` lines 2086-2096):
```python
ground_truth_metrics = {
    "precision": round(session_metrics.precision * 100, 1),
    "recall": round(session_metrics.recall * 100, 1),  # ← Line 2091
    "f1_score": round(session_metrics.f1_score * 100, 1),
    # ...
}
```

2. **Per-Video Metrics Aggregation** (`routers/video_sequence_testing.py` lines 1508-1826):
```python
per_video_match_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"TP": 0, "FP": 0})
per_video_fn_counts: Dict[str, int] = defaultdict(int)

# ... later ...
video_recall = video_true_positives / (video_true_positives + video_false_negatives)
```

**LIKELY BUG**: Frontend might be displaying recall from **ONE video with 100%** instead of **aggregated session recall of 36%**.

---

## 4. GROUND TRUTH COUNT RETRIEVAL

### Function: `_get_actual_ground_truth_count()` (Lines 657-717)

**Multi-Video Session Logic:**
```python
def _get_actual_ground_truth_count(
    self,
    db: Session,
    test_session: TestSession,
    session_id: str
) -> int:
    if test_session.has_video_sequence and test_session.sequence_id:
        # Multi-video session: count GT across ALL videos
        video_ids = self._get_sequence_video_ids(db, test_session.sequence_id)

        gt_count = db.query(func.count(GroundTruthObject.id)).filter(
            GroundTruthObject.video_id.in_(video_ids),
            GroundTruthObject.deleted_at.is_(None)
        ).scalar() or 0

        return gt_count  # Returns 242 for session fa204ef2
```

**This function works correctly** - it's counting ALL ground truth across all videos.

---

## 5. DATABASE STORAGE

### Session Table Storage (Lines 1960-2000):
```python
test_session.accuracy_recall = metrics.recall  # ← Line 1968
```

**The recall IS being stored correctly** (as decimal: 0.3595), BUT:
- Somewhere between storage and display, **100% is being shown instead**

---

## 6. SUSPECTED BUG SCENARIOS

### Scenario 1: Frontend Displaying First Video's Recall
```
Video 1: recall = 100% (10/10)  ← DISPLAYED
Video 2: recall = 40% (8/20)
Video 3: recall = 30% (69/212)
---
Session: recall = 36% (87/242)  ← SHOULD BE DISPLAYED
```

### Scenario 2: API Sending Wrong Recall Field
```json
{
  "perVideoResults": [
    {"recall": 100.0},  ← Frontend mistakenly uses this
    {"recall": 40.0},
    {"recall": 30.0}
  ],
  "metrics": {
    "recall": 36.0  ← CORRECT value, but not used
  }
}
```

### Scenario 3: Database Query Returning Wrong Scope
```sql
-- WRONG: Returns recall for first video only
SELECT accuracy_recall FROM sequence_video_results
WHERE video_sequence_id = '...' LIMIT 1;

-- CORRECT: Should return session-level recall
SELECT accuracy_recall FROM test_sessions
WHERE id = 'fa204ef2-9d8b-4480-9692-86e338c1218a';
```

---

## 7. IMPACT ASSESSMENT

### Metrics Affected
- ✅ **Precision**: Likely correct (uses TP/FP, not dependent on total GT)
- ❌ **Recall**: INCORRECT - showing 100% instead of 36%
- ❌ **F1 Score**: INCORRECT - depends on recall, so also wrong
- ❌ **Accuracy**: POTENTIALLY INCORRECT - also uses total GT

### Where Displayed
1. **UI Results Page**: Shows "Recall 100.0%"
2. **Session Details API**: Likely returning incorrect recall
3. **Test Reports**: May contain false 100% recall
4. **Dashboard Statistics**: Aggregated metrics may be skewed

### Historical Data
- **Status**: POTENTIALLY CORRUPTED
- **Reason**: If this bug existed in previous sessions, their stored recall values may be from single videos instead of full sessions
- **Action Required**: Audit all multi-video sessions for recall accuracy

---

## 8. CORRECT CALCULATION VERIFICATION

### For Session fa204ef2-9d8b-4480-9692-86e338c1218a:

```python
TP = 87
FP = ? (need to query)
FN = 242 - 87 = 155
Total GT = 242

Recall = TP / (TP + FN) = 87 / 242 = 0.3595 = 35.95%
```

**CORRECT VALUE**: **35.95%** (NOT 100%)

---

## 9. CODE SNIPPETS WITH ANNOTATIONS

### A) Correct Backend Calculation (`ground_truth_matching_service.py:1683`)
```python
# ✅ CORRECT: This calculates recall properly
recall = true_positives / actual_gt_count if actual_gt_count > 0 else 0.0
# For fa204ef2: recall = 87 / 242 = 0.3595
```

### B) Database Storage (`ground_truth_matching_service.py:1968`)
```python
# ✅ CORRECT: This stores the correct decimal value
test_session.accuracy_recall = metrics.recall  # Stores 0.3595
```

### C) API Response Construction (`test_sessions.py:2091`)
```python
# ⚠️ SUSPECTED: This might be pulling from wrong source
ground_truth_metrics = {
    "recall": round(session_metrics.recall * 100, 1),
    # QUESTION: Is session_metrics from full session or single video?
}
```

### D) Per-Video Aggregation (`video_sequence_testing.py:1735-1763`)
```python
# ⚠️ SUSPECTED: Frontend might use per-video instead of session
match_counts_for_video = per_video_match_counts.get(video_id, {"TP": 0, "FP": 0})
tp_count = match_counts_for_video.get("TP", 0)
fn_count = per_video_fn_counts.get(video_id, 0)
total_ground_truth_events = tp_count + fn_count

recall_ratio = tp_count / total_ground_truth_events if total_ground_truth_events > 0 else 0.0

ground_truth_metrics = {
    "recall": round(recall_ratio * 100, 1),  # ← Per-video recall
}
```

---

## 10. DEBUGGING STEPS REQUIRED

### Step 1: Verify Database Value
```sql
SELECT
    id,
    accuracy_recall,
    tp_count,
    fn_count,
    (tp_count::float / NULLIF(tp_count + fn_count, 0)) as calculated_recall
FROM test_sessions
WHERE id = 'fa204ef2-9d8b-4480-9692-86e338c1218a';
```

**Expected**: `accuracy_recall` should be ~0.3595

### Step 2: Check API Response
```bash
curl http://localhost:8000/api/sessions/fa204ef2-9d8b-4480-9692-86e338c1218a/results
```

**Look for**:
- `metrics.recall` (should be 35.95)
- `perVideoResults[].recall` (individual videos, some might be 100)

### Step 3: Trace Frontend Data Binding
- Check which field the UI is displaying
- Verify it's using `metrics.recall` NOT `perVideoResults[0].recall`

### Step 4: Check Multi-Video Aggregation
```python
# In routers/test_sessions.py or video_sequence_testing.py
# Add logging to see which recall value is being returned
logger.info(f"Session recall: {session_metrics.recall}")
logger.info(f"Per-video recalls: {[vr['recall'] for vr in per_video_results]}")
```

---

## 11. PROPOSED FIX

### Option A: Fix API Response Structure
Ensure API clearly separates session-level and per-video metrics:

```json
{
  "sessionMetrics": {
    "recall": 35.95,  ← Session-wide recall
    "precision": 72.5,
    "f1Score": 48.1
  },
  "perVideoMetrics": [
    {
      "videoId": "video1",
      "recall": 100.0,  ← Individual video recall
      "precision": 85.0
    }
  ]
}
```

### Option B: Fix Frontend Data Binding
```typescript
// WRONG
const recall = response.perVideoResults[0].recall;

// CORRECT
const recall = response.sessionMetrics.recall;
```

### Option C: Add Validation
```python
# In API endpoint
assert session_metrics.recall == (tp_count / total_gt), \
    f"Recall mismatch: {session_metrics.recall} != {tp_count}/{total_gt}"
```

---

## 12. RELATED ISSUES TO INVESTIGATE

1. **F1 Score**: If recall is wrong, F1 is also wrong
   - F1 = 2 × (precision × recall) / (precision + recall)

2. **Accuracy**: May also be affected
   - Accuracy = TP / total_GT (same denominator as recall)

3. **Other Multi-Video Sessions**: Check if bug affects all multi-video tests

4. **Historical Data Integrity**: May need to recalculate metrics for past sessions

---

## 13. VERIFICATION QUERIES

### A) Count Ground Truth Per Video
```sql
SELECT
    v.id,
    v.filename,
    COUNT(gt.id) as gt_count
FROM videos v
JOIN ground_truth_objects gt ON gt.video_id = v.id
WHERE v.id IN (
    SELECT video_id FROM video_test_sequences
    WHERE test_session_id = 'fa204ef2-9d8b-4480-9692-86e338c1218a'
)
GROUP BY v.id, v.filename;
```

### B) Count True Positives Per Video
```sql
SELECT
    de.video_id,
    COUNT(*) as tp_count
FROM detection_events de
JOIN detection_comparisons dc ON dc.detection_event_id = de.id
WHERE de.test_session_id = 'fa204ef2-9d8b-4480-9692-86e338c1218a'
  AND dc.match_type = 'TP'
GROUP BY de.video_id;
```

### C) Calculate Per-Video Recall
```sql
WITH video_metrics AS (
    SELECT
        v.id as video_id,
        v.filename,
        COUNT(DISTINCT gt.id) as total_gt,
        COUNT(DISTINCT CASE
            WHEN dc.match_type = 'TP' THEN dc.id
        END) as tp_count
    FROM videos v
    LEFT JOIN ground_truth_objects gt ON gt.video_id = v.id
    LEFT JOIN detection_events de ON de.video_id = v.id
        AND de.test_session_id = 'fa204ef2-9d8b-4480-9692-86e338c1218a'
    LEFT JOIN detection_comparisons dc ON dc.detection_event_id = de.id
    WHERE v.id IN (
        SELECT video_id FROM video_test_sequences
        WHERE test_session_id = 'fa204ef2-9d8b-4480-9692-86e338c1218a'
    )
    GROUP BY v.id, v.filename
)
SELECT
    video_id,
    filename,
    tp_count,
    total_gt,
    CASE
        WHEN total_gt > 0 THEN (tp_count::float / total_gt * 100)
        ELSE 0
    END as recall_percentage
FROM video_metrics
ORDER BY recall_percentage DESC;
```

**EXPECTED**: Some videos will show 100% recall, but session aggregate should be 36%.

---

## 14. ACTION ITEMS

- [ ] **URGENT**: Run verification queries to confirm database values
- [ ] **URGENT**: Check API endpoint response for session fa204ef2
- [ ] **URGENT**: Trace frontend component showing "Recall 100%"
- [ ] Fix data binding: Ensure UI displays session-level recall
- [ ] Add validation: Assert recall calculation matches TP/GT ratio
- [ ] Add unit tests: Test multi-video recall aggregation
- [ ] Audit historical data: Check if past sessions have incorrect recall
- [ ] Update documentation: Clarify per-video vs session-level metrics

---

## 15. CONTACT INFORMATION

**Bug Reporter:** User (via session observation)
**Analyst:** Claude (AI Assistant)
**Date:** 2025-11-24
**Session ID:** fa204ef2-9d8b-4480-9692-86e338c1218a

---

## SUMMARY

**Root Cause:** Likely **per-video recall (100%) displayed instead of session-wide recall (36%)**

**Critical Formula:**
```
Session Recall = Total TP / Total GT Across All Videos
                = 87 / 242
                = 35.95%  ← CORRECT

NOT:
Video Recall = Video TP / Video GT
            = 10 / 10
            = 100%  ← INCORRECT for session display
```

**Next Step:** Verify API response and frontend data binding to confirm which recall value is being displayed.
