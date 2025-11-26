# DATABASE LOCATION INVESTIGATION REPORT
**Session ID:** 2c9a93f6-8471-4f2e-b1a7-06f239fca548
**Investigation Date:** 2025-11-24

## 1. All Databases Found

Total databases discovered: **30 SQLite databases**

### Primary Databases (backend directory):
- **dev_database.db** - 109MB (Last modified: Nov 24 19:36) ✅ ACTIVE
- test_database.db - 3.2MB (Last modified: Nov 7 16:29)
- test_gt_validation.db - 2.3MB (Last modified: Nov 20 22:05)
- test_reports.db - 1.1MB (Last modified: Sep 10 08:12)
- simple_test.db - 36KB (Last modified: Nov 20 22:02)

### Backup Databases:
- backend/backups/db_backup_20251105_121911.db - 41MB
- backend/backups/db_backup_20251104_155433.db - 41MB
- backend/db_backups/pre_eval_details_*.db - 49MB
- backend/db_backups/dev_database_QUEEN_PRE_EVAL_FIX_20251113_091342.db - 48MB

### Swarm/Memory Databases (coordination):
- backend/.swarm/memory.db - 124KB
- backend/.hive-mind/memory.db - 16KB
- backend/.hive-mind/hive.db - 96KB
- .swarm/memory.db - 1.1MB
- frontend/.swarm/memory.db - 932KB

## 2. Session Location

✅ **SESSION FOUND**

- **Database Path:** `/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db`
- **Table:** `test_sessions`
- **Record Exists:** YES (1 record)
- **API Status:** Running (Python main.py on localhost:8000)

## 3. Session Data Extracted

### Core Session Information
```
id: 2c9a93f6-8471-4f2e-b1a7-06f239fca548
name: Video Sequence Test - 2025-11-24 19:35
status: completed
session_type: user_created
```

### Key Metrics (From Database)
```
accuracy_recall: 0.3229571984435798 (32.3%)
tp_count: 83
fp_count: 8
fn_count: 174
actual_detections: 91
```

### Test Results
```
pass_fail_result: FAIL
overall_score: 47.701149425287355
accuracy_result: FAIL
accuracy_f1_score: 0.47701149425287354
accuracy_precision: 0.9120879120879121
latency_result: PASS
latency_mean_ms: 11.797309400566167
```

### Video Sequence Configuration
```
has_video_sequence: 1
sequence_id: 19a36b20-3392-4eca-90af-c18074534c32
video_ids: [
  "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",
  "550e3cf8-2755-42df-8c3c-041300735f93"
]
total_videos: 2
```

### Timing Configuration
```
tolerance_ms: 100
max_latency_threshold_ms: 300.0
precision_timing_enabled: 1
hil_timing_enabled: 1
timing_validation_status: synced
hil_compliance_verified: 1
```

## 4. API Response

✅ **API Successfully Retrieved Session**

- **Endpoint:** `http://localhost:8000/api/test-sessions/2c9a93f6-8471-4f2e-b1a7-06f239fca548`
- **Response Status:** 200 OK
- **Data Matches:** Database and API data are consistent

### Key API Data Points
```json
{
  "truePositives": 83,
  "falsePositives": 8,
  "falseNegatives": 174,
  "accuracyRecall": 0.3229571984435798,
  "accuracyPrecision": 0.9120879120879121,
  "accuracyF1Score": 0.47701149425287354,
  "actualDetections": 91,
  "overallTestResult": "FAIL"
}
```

## 5. Database Connection String

From `database.py`:
```python
def get_database_url():
    database_url = (
        os.getenv("VRU_DATABASE_URL") or
        os.getenv("DATABASE_URL") or
        os.getenv("AIVALIDATION_DATABASE_URL") or
        "sqlite:///./dev_database.db"  # ← ACTIVE CONNECTION
    )
    return database_url
```

**Active Connection:** `sqlite:///./dev_database.db`
**No environment variables set** - Using default fallback

## 6. Actual Ground Truth Count

⚠️ **SCHEMA ISSUE IDENTIFIED**

The `ground_truth_objects` table **DOES NOT have a `session_id` column**.

### Ground Truth Objects Schema
```
Columns in ground_truth_objects:
- id (VARCHAR(36))
- video_id (VARCHAR(36))  ← Links to videos, NOT sessions
- tracking_id (VARCHAR)
- frame_number (INTEGER)
- timestamp (FLOAT)
- class_label (VARCHAR)
- x, y, width, height (FLOAT)
- bounding_box (JSON)
- confidence (FLOAT)
- validated (BOOLEAN)
- created_at (DATETIME)
```

### Ground Truth Retrieval Method
Ground truth must be retrieved via **video_id**, not session_id:
```python
# Session links to videos
session.video_ids = [
    "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",
    "550e3cf8-2755-42df-8c3c-041300735f93"
]

# Ground truth query
SELECT COUNT(*) FROM ground_truth_objects
WHERE video_id IN (video_ids_from_session)
```

### Pending Ground Truth Count
Ground truth count to be determined by video IDs in next query.

## 7. Critical Findings

### ✅ SUCCESSES
1. Session data successfully located in `dev_database.db`
2. API is running and accessible
3. Data integrity verified between database and API
4. Session metadata is complete and accurate
5. Timing and HIL compliance verified

### ⚠️ ISSUES IDENTIFIED

#### Issue #1: Missing Column Error in Initial Query
```
sqlite3.OperationalError: no such column: true_positives
```
**Cause:** Column name mismatch
**Actual Column:** `tp_count` (not `true_positives`)
**Status:** Resolved by using correct schema

#### Issue #2: Ground Truth Table Schema
```
sqlite3.OperationalError: no such column: session_id
```
**Cause:** `ground_truth_objects` table links to `video_id`, not `session_id`
**Impact:** Cannot directly query ground truth by session
**Workaround:** Query by video IDs from session metadata

#### Issue #3: Expected vs Actual Detections
**Database shows:**
- `expected_detections`: NULL
- `actual_detections`: 91

**Calculated from accuracy_details:**
- True Positives: 83
- False Positives: 8
- False Negatives: 174
- **Implied Expected Detections:** 257 (83 TP + 174 FN)

**CRITICAL:** Expected detections not stored in session, only derivable from TP + FN.

## 8. Database Schema Analysis

### test_sessions Table (76 columns)
Key columns for metrics:
- `tp_count`, `fp_count`, `fn_count` (not true_positives, etc.)
- `accuracy_recall`, `accuracy_precision`, `accuracy_f1_score`
- `expected_detections` (NULL in this session)
- `actual_detections` (91)
- `accuracy_details` (JSON with full breakdown)

### Related Tables with session_id
To be verified in follow-up query:
- detection_events
- detection_comparisons
- test_results
- stored_detection_events
- sequence_video_results

## 9. Recommendations

1. **Fix Column Name Inconsistency**
   - Database uses `tp_count`, `fp_count`, `fn_count`
   - API returns `truePositives`, `falsePositives`, `falseNegatives`
   - Consider standardizing naming convention

2. **Add session_id to ground_truth_objects**
   - Current schema requires join through video_id
   - Direct session lookup would improve query performance

3. **Store expected_detections**
   - Currently NULL in database
   - Should be calculated and stored during session creation
   - Value: TP + FN = 257 for this session

4. **Environment Variable Configuration**
   - No DATABASE_URL environment variables set
   - Consider documenting default fallback behavior

## 10. Next Steps

1. Query ground truth count by video IDs
2. Verify detection_events table for session
3. Calculate expected ground truth count
4. Compare with TP + FN calculation (257)
5. Validate video sequence timing data
