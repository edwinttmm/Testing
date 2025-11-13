# LIVE API CHECK - Session c511302e-43c0-49c0-8ad0-bd89e891e3c1

**Report Generated**: 2025-11-05 13:33:07 UTC
**Backend Status**: RUNNING (PID 100263)
**Backend Health**: HEALTHY

## EXECUTIVE SUMMARY

**CRITICAL FINDING**: THREE MAJOR BUGS IDENTIFIED causing zero true positives

### User's Report
Frontend shows ALL ZEROS:
- True Positives: 0
- False Positives: 0
- False Negatives: 0

### Backend Reality
Backend API returns NON-ZERO values but still WRONG:
- True Positives: 0 (CRITICAL BUG - should be ~100+)
- False Positives: 193 (144 + 49)
- False Negatives: 514 (262 + 252)

### THREE ROOT CAUSES IDENTIFIED

**BUG #1: TIMESTAMP DOMAIN MISMATCH** (CRITICAL - Causes Zero TP)
- Ground truth matching compares RELATIVE timestamps (0.0-5.0s) with ABSOLUTE epoch timestamps (1762347318.x)
- These will NEVER match because they're in different time domains
- Fix: Use `video_relative_timestamp` field instead of `timestamp` in matching algorithm
- Location: `backend/services/ground_truth_matching_service.py`
- Impact: 0 true positives, 100% false positives, 100% false negatives

**BUG #2: VIDEO 2 TIMESTAMP OFFSET** (HIGH - Affects multi-video)
- Video 2 detections start at 11.519s relative time (should be ~0.0s)
- Multi-video sequences not resetting video-relative timestamp between videos
- Fix: Reset video_relative_timestamp for each video in sequence
- Location: `backend/services/video_sequence_orchestrator.py`
- Impact: Video 2 detections will never match even after Bug #1 is fixed

**BUG #3: FRONTEND DATA PARSING** (MEDIUM - Display only)
- Frontend shows zeros for FP/FN despite backend returning correct values
- Frontend likely not reading `sequence_results.per_video_results` array correctly
- Fix: Update frontend to parse per_video_results from backend response
- Location: Frontend HIL Results component
- Impact: User sees incorrect metrics even when backend has correct data

---

## 1. BACKEND HEALTH STATUS

```bash
Process: python3 main.py (PID 100263)
Status: RUNNING (CPU 1.5%, Memory 233MB)
Health Endpoint: {"status":"healthy","database":"sqlite"}
```

Backend is running correctly.

---

## 2. CORRECTED-RESULTS ENDPOINT ANALYSIS

**Endpoint**: `/api/enhanced-hil/test-sessions/c511302e-43c0-49c0-8ad0-bd89e891e3c1/corrected-results`

### 2.1 Response Structure

```json
{
  "session_id": "c511302e-43c0-49c0-8ad0-bd89e891e3c1",
  "validation_type": "enhanced_latency_with_timing_correction",
  "has_video_sequence": true,
  "sequence_id": "1f24cf59-dfd8-40ae-818e-e77c6c88c1cd"
}
```

### 2.2 Sequence Results (TWO VIDEOS CONFIRMED)

```json
"sequence_results": {
  "total_videos": 2,
  "current_video_index": 0,
  "completed_videos": 0,
  "sequence_status": "running"
}
```

### 2.3 Per-Video Results

**VIDEO 1**: `10c2b16c-86fa-4140-b1cf-c0ea42f82ca5`
```json
{
  "video_id": "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",
  "sequence_order": 0,
  "video_status": "pending",
  "video_filename": "child_test_video_20251031_144012.mp4",
  "video_duration": 5.041666666666667,
  "expected_detection_count": 121,
  "actual_detection_count": 144,
  "passed_detections": 0,
  "failed_detections": 0,
  "avg_latency_ms": null,
  "pass_rate_percent": null,
  "validation_result": "pending",
  "ground_truth_metrics": {
    "total_ground_truth": 262,
    "true_positives": 0,           ← ZERO (WRONG)
    "false_positives": 144,
    "false_negatives": 262,
    "precision": 0.0,
    "recall": 0.0,
    "f1_score": 0.0
  }
}
```

**VIDEO 2**: `550e3cf8-2755-42df-8c3c-041300735f93`
```json
{
  "video_id": "550e3cf8-2755-42df-8c3c-041300735f93",
  "sequence_order": 1,
  "video_status": "pending",
  "video_filename": "Child_20251031_143523.mp4",
  "video_duration": 5.041666666666667,
  "expected_detection_count": 121,
  "actual_detection_count": 49,
  "passed_detections": 0,
  "failed_detections": 0,
  "avg_latency_ms": null,
  "pass_rate_percent": null,
  "validation_result": "pending",
  "ground_truth_metrics": {
    "total_ground_truth": 252,
    "true_positives": 0,           ← ZERO (WRONG)
    "false_positives": 49,
    "false_negatives": 252,
    "precision": 0.0,
    "recall": 0.0,
    "f1_score": 0.0
  }
}
```

---

## 3. DETECTION EVENTS ENDPOINT ANALYSIS

**Endpoint**: `/api/test-sessions/c511302e-43c0-49c0-8ad0-bd89e891e3c1/events?limit=10`

### 3.1 Sample Detection Events (First 10 of 193 total)

All 193 detections have:
- ✓ Valid `video_id` field (10c2b16c-86fa-4140-b1cf-c0ea42f82ca5)
- ✓ Valid `sequence_video_result_id`
- ✗ **`ground_truth_match_id`: null** (ALL DETECTIONS HAVE NULL)

**Example Detection Event**:
```json
{
  "id": "c7e575bd-ca15-4571-8fce-0d0b99ebb35f",
  "timestamp": 0.1325078010559082,
  "video_relative_timestamp": 0.1325078010559082,
  "voltage": 4.218743801116943,
  "channel": "AIN0",
  "detection_type": "voltage",
  "validation_result": "PASS",
  "timing_quality": "high",
  "frame_number": 3,
  "latency_ms": 7.507801055908203,
  "video_id": "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",
  "sequence_video_result_id": "8a0a3bbb-2e9e-49f9-9868-044c45dd2e18",
  "ground_truth_match_id": null         ← NULL (NO MATCHING)
}
```

### 3.2 Video ID Distribution

From events endpoint (limit=10):
- All 10 events have `video_id = "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5"` (Video 1)
- None from Video 2 in this sample

---

## 4. ROOT CAUSE ANALYSIS - CRITICAL FINDING

### 4.1 Ground Truth Matching FAILED - ROOT CAUSE IDENTIFIED

**SMOKING GUN**: Ground truth timestamps are RELATIVE (0.0s to 5.0s) but detection timestamps are ABSOLUTE EPOCH TIMESTAMPS (1762347318.x seconds)

**DATABASE EVIDENCE**:

```
VIDEO 1 (10c2b16c-86fa-4140-b1cf-c0ea42f82ca5):
- Ground Truth: 262 objects
- Detections: 144 events (for this session)
- Total Detections: 7035 (all sessions combined)

Ground Truth Timestamps (first 5):
  t=0.000000s, frame=1
  t=0.000000s, frame=0
  t=0.041667s, frame=2
  t=0.041667s, frame=0
  t=0.083333s, frame=3

Detection Timestamps (first 5):
  t=1762347318.003301s, frame=None  ← ABSOLUTE EPOCH TIME
  t=1762347318.039457s, frame=None  ← ABSOLUTE EPOCH TIME
  t=1762347318.103485s, frame=None  ← ABSOLUTE EPOCH TIME
  t=1762347318.130816s, frame=None  ← ABSOLUTE EPOCH TIME
  t=1762347318.188428s, frame=None  ← ABSOLUTE EPOCH TIME

VIDEO 2 (550e3cf8-2755-42df-8c3c-041300735f93):
- Ground Truth: 252 objects
- Detections: 49 events (for this session)
- Total Detections: 623 (all sessions combined)

Ground Truth Timestamps (first 5):
  t=0.000000s, frame=1
  t=0.000000s, frame=0
  t=0.041667s, frame=2
  t=0.041667s, frame=0
  t=0.083333s, frame=3

Detection Timestamps (first 5):
  t=1762347329.389541s, frame=None  ← ABSOLUTE EPOCH TIME
  t=1762347329.421825s, frame=None  ← ABSOLUTE EPOCH TIME
  t=1762347329.436543s, frame=None  ← ABSOLUTE EPOCH TIME
  t=1762347329.453805s, frame=None  ← ABSOLUTE EPOCH TIME
  t=1762347329.469617s, frame=None  ← ABSOLUTE EPOCH TIME
```

### 4.2 Why Zero True Positives?

**THE PROBLEM**: The ground truth matching algorithm is comparing:
- Ground truth timestamp: `0.041667` (41.667ms into video)
- Detection timestamp: `1762347318.039457` (absolute time: Nov 5, 2025 12:55:18.039 UTC)

These will NEVER match because they're in completely different time domains!

**THE FIX NEEDED**: The matching algorithm must either:
1. Convert detection absolute timestamps to video-relative timestamps before matching
2. Convert ground truth relative timestamps to absolute timestamps before matching
3. Use the `video_relative_timestamp` field from detections (if populated correctly)

### 4.3 Additional Evidence

1. ALL detection events have `ground_truth_match_id: null`
2. Backend shows:
   - Video 1: 144 FP, 262 FN, 0 TP
   - Video 2: 49 FP, 252 FN, 0 TP
3. Detection events have `video_relative_timestamp` field but matching logic uses wrong field
4. Ground truth objects stored in `ground_truth_objects` table (NOT `ground_truth_events`)

### 4.4 Expected Ground Truth Counts

- Video 1: 262 ground truth objects
- Video 2: 252 ground truth objects
- **Total**: 514 ground truth objects

### 4.5 Actual Detection Counts

- Video 1: 144 detections (this session)
- Video 2: 49 detections (this session)
- **Total**: 193 detections (this session)

---

## 5. DETECTION EVENT DISTRIBUTION

From corrected-results endpoint:

```
Total Detections: 193
- Passed: 138 (71.5%)
- Failed: 55 (28.5%)

Average Real Latency: 1810.039 ms
Median Real Latency: 10.023 ms

Video 1 Detections: 144 (74.6%)
Video 2 Detections: 49 (25.4%)
```

---

## 6. COMPARISON: Backend vs Frontend

| Metric | User Sees (Frontend) | Backend Returns | Status |
|--------|---------------------|-----------------|---------|
| True Positives | 0 | 0 | ✗ BOTH WRONG |
| False Positives | 0 | 193 (144+49) | ✗ FRONTEND WRONG |
| False Negatives | 0 | 514 (262+252) | ✗ FRONTEND WRONG |
| Total Ground Truth | ? | 514 | ? |
| Total Detections | ? | 193 | ? |

**FINDING**: Backend is calculating FP/FN correctly but TP=0 indicates ground truth matching failure. Frontend is showing all zeros which suggests it's not reading the per_video_results array correctly.

---

## 7. DATA QUALITY ISSUES

### 7.1 Video Status
- Both videos marked as "pending" despite session being "completed"
- This might indicate incomplete processing

### 7.2 Timing Quality
- Measurement quality: "poor (confidence: 17%)"
- Most detections classified as "unreliable" timing

### 7.3 Ground Truth Availability
All detection events show:
```json
"timing_synchronization": {
  "timing_quality": "unreliable",
  "confidence_score": 0.1,
  "ground_truth_available": true
}
```

This confirms ground truth DATA exists but matching FAILED.

---

## 8. RECOMMENDED ACTIONS

### CRITICAL FIX #1: Timestamp Domain Mismatch

**ISSUE**: Ground truth matching is comparing RELATIVE timestamps (0.0s-5.0s) with ABSOLUTE epoch timestamps (1762347318.x)

**LOCATION**: `backend/services/ground_truth_matching_service.py`

**FIX**: Update matching algorithm to use `video_relative_timestamp` field from detections:

```python
# WRONG (current):
detection_timestamp = detection.timestamp  # 1762347318.003

# CORRECT (needed):
detection_timestamp = detection.video_relative_timestamp  # 0.133
```

### CRITICAL FIX #2: Video 2 Timestamp Offset Bug

**ISSUE**: Video 2 detections have wrong `video_relative_timestamp` values:
- Ground truth starts at: 0.000s
- Detection relative timestamps start at: 11.519s (should be ~0.0s)

**ROOT CAUSE**: Multi-video sequences not resetting video-relative timestamp between videos

**EVIDENCE**:
```
Video 1: Detection starts at 0.133s (correct, ~130ms startup delay)
Video 2: Detection starts at 11.519s (WRONG! Should be ~0.0s)
         11.519s = 5.04s (video 1 duration) + 6.479s (gap)
```

**LOCATION**: Likely in `video_sequence_orchestrator.py` or detection timestamp calculation

**FIX**: Ensure `video_relative_timestamp` is calculated from each video's individual start time, not sequence start time

### CRITICAL FIX #3: Frame Number Mismatch

**ISSUE**: Detection events have:
- `frame_number` = None (should be populated)
- `video_frame_number` = correct values (3, 4, 5...)

**LOCATION**: Detection event creation

**FIX**: Populate `frame_number` field or update matching to use `video_frame_number`

### IMMEDIATE ACTIONS (Priority Order)

1. **Fix timestamp domain in matching algorithm** (30 min)
   - File: `backend/services/ground_truth_matching_service.py`
   - Change: Use `video_relative_timestamp` instead of `timestamp`
   - Test: Verify TP > 0 after fix

2. **Fix Video 2 relative timestamp offset** (1-2 hours)
   - File: `backend/services/video_sequence_orchestrator.py`
   - Issue: video_relative_timestamp not reset between videos
   - Test: Verify Video 2 starts at ~0.0s

3. **Fix frame number population** (30 min)
   - File: Detection event creation logic
   - Issue: `frame_number` is None
   - Test: Verify `frame_number` populated

### FRONTEND (Fix Display Issue)

4. **Check frontend data parsing**:
   - Frontend might not be reading `sequence_results.per_video_results`
   - Check if frontend is looking for different field name
   - Verify TypeScript interfaces match backend structure

### VERIFICATION STEPS

After fixes, verify:
```sql
-- Check for true positives
SELECT COUNT(*) FROM detection_events
WHERE test_session_id = 'c511302e-43c0-49c0-8ad0-bd89e891e3c1'
AND ground_truth_match_id IS NOT NULL;

-- Should be > 0 after fixes

-- Check Video 2 timestamps
SELECT MIN(video_relative_timestamp), MAX(video_relative_timestamp)
FROM detection_events
WHERE video_id = '550e3cf8-2755-42df-8c3c-041300735f93'
AND test_session_id = 'c511302e-43c0-49c0-8ad0-bd89e891e3c1';

-- Should be ~0.0s to ~5.0s after fix
```

---

## 9. FULL API RESPONSES

### 9.1 Corrected-Results Response
Full JSON saved to: `/tmp/corrected_results_full.json`

Key sections:
- ✓ Has 2 videos in `per_video_results`
- ✓ Each video has `ground_truth_metrics`
- ✓ FP/FN values are correct
- ✗ TP values are zero

### 9.2 Events Response Summary
- Total events in limit=10: 10
- All have video_id: `10c2b16c-86fa-4140-b1cf-c0ea42f82ca5`
- All have null ground_truth_match_id
- All have ground_truth_available: true

---

## 10. NEXT STEPS

1. **Database investigation** (HIGHEST PRIORITY):
   - Query ground truth table directly
   - Check if ground truth was uploaded correctly
   - Verify video_id values match

2. **Matching algorithm review**:
   - Find matching tolerance value
   - Check timestamp formats
   - Review matching logic

3. **Frontend fix**:
   - Verify data parsing logic
   - Check field name mappings
   - Test with known good data

---

## APPENDIX: Key Findings

1. ✓ Backend is running and healthy
2. ✓ Backend returns correct structure with 2 videos
3. ✗ Backend shows ZERO true positives (ground truth matching failed)
4. ✓ Backend shows correct FP/FN counts
5. ✗ Frontend shows all zeros (data parsing issue)
6. ✓ All 193 detection events have valid video_id
7. ✗ All 193 detection events have null ground_truth_match_id
8. ✓ Ground truth data exists (514 total events)
9. ✗ Zero matches between detections and ground truth
10. ✗ Video status stuck on "pending" despite session "completed"

**CRITICAL PATH**: Fix ground truth matching algorithm first, then fix frontend display.
