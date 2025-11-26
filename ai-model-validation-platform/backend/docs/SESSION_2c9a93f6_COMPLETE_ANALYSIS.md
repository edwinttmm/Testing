# Complete Database Analysis: Session 2c9a93f6-8471-4f2e-b1a7-06f239fca548

## Executive Summary

**Session Found:** ✅ YES
**Database:** `/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db` (109MB)
**Table:** `test_sessions`
**Status:** COMPLETED
**Result:** FAIL (Accuracy), PASS (Latency)
**Overall Score:** 47.7%

---

## 1. DATABASE LOCATION

### Primary Database
- **Path:** `/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db`
- **Size:** 109MB
- **Last Modified:** 2025-11-24 19:36
- **Type:** SQLite 3
- **Connection String:** `sqlite:///./dev_database.db` (default fallback)

### Alternative Databases Searched (29 total)
All other databases checked, session only exists in primary `dev_database.db`.

### API Accessibility
- **Endpoint:** `http://localhost:8000/api/test-sessions/2c9a93f6-8471-4f2e-b1a7-06f239fca548`
- **Status:** ✅ Running and accessible
- **Process:** Python main.py (PID 1250371)
- **Data Consistency:** Database and API match perfectly

---

## 2. SESSION DATA COMPLETE EXTRACTION

### Core Information
```yaml
id: 2c9a93f6-8471-4f2e-b1a7-06f239fca548
name: "Video Sequence Test - 2025-11-24 19:35"
project_id: 61ee7ed1-c8a7-415a-9f1b-44e578b6d024
video_id: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
status: completed
session_type: user_created
```

### Timestamps
```yaml
created_at: 2025-11-24 19:35:43.055003
started_at: 2025-11-24 19:35:43.055003
completed_at: 2025-11-24 19:36:00.340736
updated_at: 2025-11-24 19:36:01
duration: ~17 seconds
```

### Test Configuration
```yaml
tolerance_ms: 100
max_latency_threshold_ms: 300.0
latency_threshold_ms: 100
precision_timing_enabled: true
hil_timing_enabled: true
timing_validation_status: synced
hil_compliance_verified: true
frame_sync_enabled: false
drift_compensation_active: false
```

---

## 3. METRICS EXTRACTION

### Accuracy Metrics (From Database)
```yaml
accuracy_result: FAIL
accuracy_f1_score: 0.47701149425287354 (47.7%)
accuracy_precision: 0.9120879120879121 (91.2%)
accuracy_recall: 0.3229571984435798 (32.3%)  ← KEY METRIC

# Detection Counts
tp_count: 83          # True Positives
fp_count: 8           # False Positives
fn_count: 174         # False Negatives ← CRITICAL: 174 missed detections
actual_detections: 91 # Total AI detections (83 TP + 8 FP)
```

### Latency Metrics (From Database)
```yaml
latency_result: PASS
latency_mean_ms: 11.797309400566167 (11.8ms)
latency_max_ms: 89.06006813049316 (89.1ms)
latency_percent_within_threshold: 100.0%
latency_min_ms: 0.1211961110434423 (0.12ms)
latency_std_ms: 12.735168028303018 (12.7ms)
latency_sample_count: 83
```

### Overall Test Results
```yaml
pass_fail_result: FAIL
overall_test_result: FAIL
overall_score: 47.701149425287355
```

---

## 4. GROUND TRUTH COUNT - **CRITICAL FINDING**

### Ground Truth by Video
```yaml
Video 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5: 131 objects
Video 550e3cf8-2755-42df-8c3c-041300735f93: 126 objects
TOTAL GROUND TRUTH OBJECTS: 257
```

### Validation Against Session Data
```yaml
Expected Detections (TP + FN): 83 + 174 = 257 ✅ MATCHES
Ground Truth Objects in Database: 257 ✅ MATCHES
Actual AI Detections: 91
Missed Detections (FN): 174
```

**VERIFIED:** Ground truth count (257) matches expected detections from TP+FN calculation.

### Schema Note
⚠️ `ground_truth_objects` table does NOT have `session_id` column.
Ground truth is linked via `video_id`, not directly to sessions.

---

## 5. VIDEO SEQUENCE CONFIGURATION

### Sequence Details
```yaml
has_video_sequence: true
sequence_id: 19a36b20-3392-4eca-90af-c18074534c32
total_videos: 2
current_video_index: 0
videos_completed: 0
labjack_enabled: true
```

### Video IDs in Sequence
```
1. 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5 (primary)
2. 550e3cf8-2755-42df-8c3c-041300735f93
```

### Video Timing
```yaml
Video 1 (10c2b16c-86fa-4140-b1cf-c0ea42f82ca5):
  started_at: 1764012943.278272
  ended_at: 1764012948.3199387
  duration: 5.042 seconds
  sequence_order: 0

Video 2 (550e3cf8-2755-42df-8c3c-041300735f93):
  started_at: 1764012948.3199387
  ended_at: 1764012953.3616054
  duration: 5.042 seconds
  sequence_order: 1
```

### Post-Processing Status
```yaml
status: queued
updated_at: 2025-11-24T19:36:01.027662+00:00
note: "Triggered by results fetch"
```

---

## 6. DETAILED ACCURACY BREAKDOWN

### From `accuracy_details` JSON
```json
{
  "result": "FAIL",
  "f1Score": 0.47701149425287354,
  "precision": 0.9120879120879121,
  "recall": 0.3229571984435798,
  "truePositives": 83,
  "falsePositives": 8,
  "falseNegatives": 174,
  "reasons": [
    "F1 score 0.477 below acceptable threshold (<0.60)",
    "Precision: 0.912, Recall: 0.323",
    "Critical: Poor recall - missing too many detections",
    "Detection breakdown: 83 TP, 8 FP, 174 FN"
  ]
}
```

### Key Findings
1. **High Precision (91.2%):** AI is accurate when it detects something
2. **Low Recall (32.3%):** AI is missing 67.7% of objects
3. **174 False Negatives:** Majority of ground truth objects not detected
4. **F1 Score (47.7%):** Below acceptable threshold (<60%)

---

## 7. DETAILED LATENCY BREAKDOWN

### From `latency_details` JSON
```json
{
  "result": "PASS",
  "meanLatencyMs": 11.797309400566167,
  "maxLatencyMs": 89.06006813049316,
  "minLatencyMs": 0.1211961110434423,
  "stdLatencyMs": 12.735168028303018,
  "withinTolerancePercent": 100.0,
  "sampleCount": 83,
  "reasons": [
    "Mean latency 11.8ms meets PASS threshold (≤100ms)",
    "100.0% of detections within tolerance (≥95% required)",
    "Latency stats: mean=11.8ms, std=12.7ms, min=0.1ms, max=89.1ms"
  ]
}
```

### Key Findings
1. **Excellent Average Latency:** 11.8ms (well below 100ms threshold)
2. **All Detections Fast:** 100% within tolerance
3. **Low Variance:** Standard deviation 12.7ms
4. **Acceptable Max:** 89.1ms (below 300ms max threshold)

---

## 8. DATABASE SCHEMA ANALYSIS

### test_sessions Table Schema
**Total Columns:** 76

**Key Metric Columns:**
```
tp_count INTEGER          (not "true_positives")
fp_count INTEGER          (not "false_positives")
fn_count INTEGER          (not "false_negatives")
accuracy_recall FLOAT
accuracy_precision FLOAT
accuracy_f1_score FLOAT
expected_detections INTEGER    (NULL in this session)
actual_detections INTEGER      (91)
accuracy_details JSON
latency_details JSON
overall_details JSON
```

**Timing Columns:**
```
video_start_timestamp FLOAT
video_start_timestamp_ns VARCHAR
precision_timing_enabled BOOLEAN
timing_accuracy_ns FLOAT
hil_timing_enabled BOOLEAN
video_timing_sync_status VARCHAR
```

### ground_truth_objects Table Schema
```
id VARCHAR(36)
video_id VARCHAR(36)      ← Links to videos, NOT sessions
tracking_id VARCHAR
frame_number INTEGER
timestamp FLOAT
class_label VARCHAR
x, y, width, height FLOAT
bounding_box JSON
confidence FLOAT
validated BOOLEAN
created_at DATETIME
deleted_at DATETIME
```

⚠️ **Missing:** `session_id` column (would enable direct session queries)

---

## 9. CRITICAL ISSUES IDENTIFIED

### Issue #1: Column Naming Inconsistency
**Database Columns:** `tp_count`, `fp_count`, `fn_count`
**API Response:** `truePositives`, `falsePositives`, `falseNegatives`
**Impact:** Potential confusion in code/queries
**Recommendation:** Standardize naming (prefer snake_case in DB, camelCase in API)

### Issue #2: Missing session_id in ground_truth_objects
**Current:** Ground truth linked via `video_id`
**Required:** Join through videos to get session's ground truth
**Impact:** More complex queries, slower performance
**Recommendation:** Add `session_id` column with migration

### Issue #3: expected_detections NULL
**Database Value:** NULL
**Calculated Value:** 257 (from TP + FN)
**Actual Ground Truth:** 257 objects
**Impact:** Missing explicit expected value in session
**Recommendation:** Calculate and store during session creation

### Issue #4: No Environment Variables
**Current:** Using fallback `sqlite:///./dev_database.db`
**Environment:** No DATABASE_URL, VRU_DATABASE_URL, or AIVALIDATION_DATABASE_URL set
**Impact:** Unclear database configuration
**Recommendation:** Document default behavior or set explicit env vars

---

## 10. DATA CONSISTENCY VERIFICATION

### ✅ All Checks Passed

| Check | Database | API | Match |
|-------|----------|-----|-------|
| Session Exists | ✅ | ✅ | ✅ |
| TP Count | 83 | 83 | ✅ |
| FP Count | 8 | 8 | ✅ |
| FN Count | 174 | 174 | ✅ |
| Accuracy Recall | 0.323 | 0.323 | ✅ |
| Accuracy Precision | 0.912 | 0.912 | ✅ |
| F1 Score | 0.477 | 0.477 | ✅ |
| Actual Detections | 91 | 91 | ✅ |
| Latency Mean | 11.8ms | 11.8ms | ✅ |
| Overall Result | FAIL | FAIL | ✅ |

### ✅ Ground Truth Validation
```
Expected (TP + FN): 257
Database Count: 257
Match: ✅ PERFECT
```

---

## 11. CALCULATION VERIFICATION

### Accuracy Metrics
```
True Positives (TP): 83
False Positives (FP): 8
False Negatives (FN): 174

Precision = TP / (TP + FP) = 83 / 91 = 0.912 ✅
Recall = TP / (TP + FN) = 83 / 257 = 0.323 ✅
F1 Score = 2 * (Precision * Recall) / (Precision + Recall)
         = 2 * (0.912 * 0.323) / (0.912 + 0.323)
         = 2 * 0.294576 / 1.235
         = 0.477 ✅
```

### Detection Counts
```
Actual Detections: TP + FP = 83 + 8 = 91 ✅
Expected Detections: TP + FN = 83 + 174 = 257 ✅
Ground Truth Objects: 257 ✅
```

**All calculations verified and correct.**

---

## 12. RECOMMENDATIONS

### Immediate Actions
1. ✅ **Session Found** - No further search needed
2. ✅ **Data Validated** - All metrics consistent
3. ✅ **Ground Truth Verified** - 257 objects confirmed

### Schema Improvements
1. **Add session_id to ground_truth_objects**
   ```sql
   ALTER TABLE ground_truth_objects ADD COLUMN session_id VARCHAR(36);
   CREATE INDEX idx_gt_session ON ground_truth_objects(session_id);
   ```

2. **Store expected_detections during session creation**
   ```python
   session.expected_detections = len(ground_truth_objects)
   ```

3. **Standardize column naming**
   - Consider migration: `tp_count` → `true_positives` (or keep DB snake_case)
   - Ensure consistent API transformation

### Documentation
1. Document fallback database configuration
2. Add schema relationship diagrams
3. Document ground truth querying via video_id

---

## 13. FINAL ANSWER TO INVESTIGATION

### Session 2c9a93f6-8471-4f2e-b1a7-06f239fca548

**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db`
**Table:** `test_sessions`
**Found:** ✅ YES

### Key Metrics (ACTUAL VALUES FROM DATABASE):
```yaml
accuracyRecall: 0.3229571984435798 (32.3%)
truePositives: 83
falsePositives: 8
falseNegatives: 174
expectedDetections: 257 (calculated from TP + FN)
actualDetections: 91
groundTruthCount: 257 (verified from database)
test_configuration: NULL (not stored)
```

### Ground Truth Count: **257 objects**
- Video 1 (10c2b16c...): 131 objects
- Video 2 (550e3cf8...): 126 objects
- **Total: 257** ✅

### Calculation Validation:
```
TP + FN = 83 + 174 = 257 ✅ MATCHES ground truth count
```

**Investigation Complete.** All data located, extracted, and verified. ✅
