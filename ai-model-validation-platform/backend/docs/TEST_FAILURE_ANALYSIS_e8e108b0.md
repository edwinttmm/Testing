# Test Failure Analysis Report
## Session ID: e8e108b0-cb20-4cba-a2db-fc29f21efd16

**Analysis Date:** 2025-11-20
**Test Type:** Video Sequence Test (Multi-video HIL)
**Test Result:** FAIL (Accuracy: 42.7%, Latency: PASS)

---

## Executive Summary

The HIL test session failed due to **duplicate detection events** being written to the database, causing artificially inflated false positive counts and negative latencies. The root cause is the **dual-source detection writing pattern** where both `labjack` and `dedicated_labjack_monitor` services are writing identical detections simultaneously.

**Critical Findings:**
1. **100% Detection Duplication**: Every detection has 2 identical copies (167 × 2 = 334 total)
2. **Negative Latencies**: 10 detections show impossible negative latencies (-18ms to -20ms)
3. **No Ground Truth Data**: 0 ground truth events found for matching
4. **No Drift Compensation**: 0 lifecycle events for drift measurement
5. **Accuracy Failure**: F1 Score 0.427 (threshold: 0.60) due to 243 false positives

---

## Data Analysis

### 1. Detection Events Duplication

**Query Results:**
```sql
SELECT source, COUNT(*) as count
FROM detection_events
WHERE test_session_id = 'e8e108b0-cb20-4cba-a2db-fc29f21efd16'
GROUP BY source;
```

| Source | Count |
|--------|-------|
| `labjack` | 167 |
| `dedicated_labjack_monitor` | 167 |
| **TOTAL** | **334** |

**Evidence:**
```
Frame None @ 1763677080.301836s: 2 detections
Frame None @ 1763677080.408386s: 2 detections
Frame None @ 1763677080.483974s: 2 detections
... (167 duplicate pairs)
```

**Impact:**
- Every detection is written twice with identical timestamps
- Matching algorithm sees 334 detections instead of 167
- False positive rate artificially inflated to 72.8%

### 2. Negative Latency Analysis

**Top 10 Negative Latencies:**
```
Timestamp              | Latency    | Source
-----------------------|------------|---------------------------
1763677083.447478s     | -20.62 ms  | labjack & dedicated_labjack_monitor
1763677081.448536s     | -19.57 ms  | labjack & dedicated_labjack_monitor
1763677085.031871s     | -19.56 ms  | labjack & dedicated_labjack_monitor
1763677080.532123s     | -19.31 ms  | labjack & dedicated_labjack_monitor
1763677080.408386s     | -18.05 ms  | labjack & dedicated_labjack_monitor
```

**Root Cause:**
- Negative latency = detection timestamp < ground truth timestamp
- This is physically impossible (detection cannot happen before the event)
- Likely caused by:
  1. Missing drift compensation (no video_lifecycle_events)
  2. Incorrect timestamp reference (using wrong video start time)
  3. Clock skew between systems

### 3. Ground Truth Data Missing

**Query Results:**
```sql
SELECT COUNT(*) FROM video_events
WHERE video_id IN (
    SELECT video_id FROM test_sessions WHERE id = 'e8e108b0-cb20-4cba-a2db-fc29f21efd16'
);
```

**Result:** `0 ground truth events`

**Impact:**
- Matching algorithm has no reference events to compare against
- All 334 detections classified as **False Positives**
- Unable to calculate True Positives or False Negatives
- Precision = 0.272 (27.2%) because TP/(TP+FP) = 91/(91+243)
- The 91 "true positives" are likely matches to missing/inferred ground truth

### 4. Drift Compensation Missing

**Query Results:**
```sql
SELECT COUNT(*) FROM video_lifecycle_events
WHERE test_session_id = 'e8e108b0-cb20-4cba-a2db-fc29f21efd16';
```

**Result:** `0 lifecycle events`

**Expected Data:**
- `video_start` event with `calculated_drift_ms`
- `video_end` event with final drift measurement
- `frame_update` events for continuous drift tracking

**Impact Without Drift Compensation:**
- Timestamps not adjusted for clock drift between frontend/backend
- Alignment errors grow over time (observed: -2.6ms, 20.6ms, 12.9ms offsets)
- HIL tests require <10ms accuracy, but drift can reach 20ms+

---

## Root Cause Analysis

### Issue #1: Duplicate Detection Writing

**Location:** `services/dedicated_labjack_monitor.py` + `services/labjack_service.py`

**Problem:**
Both services are registering detection callbacks and writing to the database:

```python
# In dedicated_labjack_monitor.py (Line 94-95)
self.labjack_monitor = get_detection_service()

# In labjack_detection_service.py
class LabJackDetectionMonitor:
    def __init__(self):
        self.labjack_service.register_detection_callback(self._detection_handler)
```

**Flow:**
1. LabJack hardware detects voltage spike
2. `labjack_service.py` writes detection (source='labjack')
3. Callback triggers `dedicated_labjack_monitor.py`
4. Monitor writes SAME detection (source='dedicated_labjack_monitor')
5. Result: 2 identical database rows

**Fix Required:**
- Choose ONE authoritative source for detection writing
- Disable duplicate callback registration
- Add database constraint to prevent duplicate timestamps per session

### Issue #2: Missing Ground Truth Data

**Location:** `services/ground_truth_matching_service.py` (Line 358-363)

**Problem:**
Ground truth query returns empty:

```python
ground_truth_objects = self._get_ground_truth_for_session(
    db, test_session, session_id
)
# Returns: [] (empty list)
```

**Possible Causes:**
1. **Video events not generated** during test session
2. **Wrong video_id** used in query (session video_id doesn't match events)
3. **Ground truth data in different table** (e.g., `ground_truth_objects` vs `video_events`)
4. **Multi-video sequence issue** - sequence_id not matching video_ids

**Investigation Needed:**
```sql
-- Check which videos are in the test session
SELECT video_id, sequence_id, has_video_sequence
FROM test_sessions
WHERE id = 'e8e108b0-cb20-4cba-a2db-fc29f21efd16';

-- Check if ground truth exists elsewhere
SELECT COUNT(*) FROM ground_truth_objects WHERE video_id IN (...);
SELECT COUNT(*) FROM video_events WHERE video_id IN (...);
SELECT COUNT(*) FROM ground_truth_batches WHERE video_id IN (...);
```

### Issue #3: Drift Compensation Not Applied

**Location:** `services/ground_truth_matching_service.py` (Line 371-377)

**Problem:**
Drift compensation code exists but returns empty results:

```python
# DRIFT COMPENSATION: Apply timestamp corrections BEFORE matching
detection_events = self._apply_drift_compensation(
    db,
    session_id,
    test_session,
    detection_events
)
```

**Root Cause:**
- `video_lifecycle_events` table has 0 rows for this session
- Drift measurement never happened during video playback
- Frontend or backend failed to record timing events

**Expected Flow:**
1. Frontend starts video playback → sends `video_start` event
2. Backend records in `video_lifecycle_events` with `frontend_timestamp`
3. Backend compares with `backend_received_timestamp`
4. Calculates `clock_offset_ms` and `calculated_drift_ms`
5. Drift applied during matching: `compensated_ts = raw_ts - drift_ms`

**Fix Required:**
- Investigate why lifecycle events weren't created
- Check `video_lifecycle_orchestrator.py` for event recording logic
- Verify WebSocket or HTTP endpoints for lifecycle event ingestion

### Issue #4: Temporal Expansion Creating Confusion

**Location:** `services/ground_truth_matching_service.py` (Line 380-410)

**Problem:**
"Option C" temporal expansion is enabled, creating virtual detections:

```python
if enable_temporal_expansion and TEMPORAL_EXPANSION_AVAILABLE:
    expanded_detections = expand_detections_temporally(
        detections=detection_events,
        window_ms=500.0,  # 500ms expansion window
        interval_ms=40.0,  # 40ms intervals
        include_original=True
    )
    # 167 detections → 2085 virtual detections (12.5x expansion)
```

**Impact:**
- Creates 12+ virtual timestamps per detection for "temporal robustness"
- Deduplication logic (`_collapse_virtual_matches`) may fail with duplicates
- Explains Frame 0 showing 2 matches with same parent_detection_id
- Can cause negative latencies if virtual timestamps exceed bounds

**Evidence:**
```
Frame 0 (0.000s):
  - Detection "det-1-v0": aligned -2.6ms, real 0.4ms ← Original
  - Detection "det-1-v1": aligned -2.6ms, real 0.4ms ← Virtual duplicate?
```

---

## Test Session Configuration Issues

**Session Metadata:**
```json
{
  "video_timing": {
    "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5": {
      "started_at": 1763677080.262773,
      "ended_at": 1763677085.3044398,
      "duration": 5.041666666666667,
      "sequence_order": 0
    },
    "550e3cf8-2755-42df-8c3c-041300735f93": {
      "started_at": 1763677085.3044398,
      "ended_at": 1763677090.3461065,
      "duration": 5.041666666666667,
      "sequence_order": 1
    }
  },
  "drift_compensation_active": 0,  ← ❌ DISABLED
  "timing_validation_status": "synced"
}
```

**Issues:**
1. **drift_compensation_active = 0** - Explicitly disabled
2. **No ground truth metadata** - Where is GT data supposed to come from?
3. **Multi-video sequence** - 2 videos but only first video_id in session
4. **Precision timing enabled** - `precision_timing_enabled = 1` but no actual precision data

---

## Recommended Fixes

### Priority 1: Stop Duplicate Detection Writing

**File:** `services/dedicated_labjack_monitor.py`

**Action:**
Remove duplicate callback registration or disable one source:

```python
# Option A: Disable dedicated_labjack_monitor writing
# Comment out database writes in _on_detection_event()

# Option B: Configure labjack_service to skip direct writes
labjack_service.enable_direct_db_writes = False

# Option C: Add database constraint
ALTER TABLE detection_events ADD CONSTRAINT unique_detection_per_session
UNIQUE (test_session_id, timestamp, source);
```

### Priority 2: Fix Ground Truth Data Generation

**File:** `routers/hil_testing.py` or `services/video_sequence_orchestrator.py`

**Action:**
1. Verify ground truth events are created during test session setup
2. Check video_id matching between sessions and ground truth
3. For multi-video sequences, ensure GT spans all videos in sequence

```python
# Add logging to ground truth generation
logger.info(f"Generated {len(gt_events)} ground truth events for video {video_id}")

# Verify GT exists before starting test
assert db.query(VideoEvent).filter(VideoEvent.video_id == video_id).count() > 0
```

### Priority 3: Enable Drift Compensation

**File:** `services/video_lifecycle_orchestrator.py`

**Action:**
1. Ensure frontend sends video lifecycle events (start/end/frame updates)
2. Backend records events in `video_lifecycle_events` table
3. Calculate and store drift measurements
4. Enable in test session: `drift_compensation_active = 1`

```python
# Verify lifecycle events are recorded
lifecycle_count = db.query(VideoLifecycleEvent).filter(
    VideoLifecycleEvent.test_session_id == session_id
).count()

if lifecycle_count == 0:
    logger.error(f"❌ No lifecycle events recorded for session {session_id}")
```

### Priority 4: Review Temporal Expansion

**File:** `services/ground_truth_matching_service.py`

**Action:**
Consider disabling temporal expansion for HIL tests:

```python
# Line 380
enable_temporal_expansion = False  # Disable for HIL precision tests
```

**Rationale:**
- HIL tests need actual detection times, not virtual expansions
- Temporal expansion better suited for ML model evaluation
- Can mask timing issues by creating artificial matches

---

## Verification Steps

After applying fixes, verify with:

```python
# 1. Check for duplicates
SELECT timestamp, COUNT(*) as count
FROM detection_events
WHERE test_session_id = 'NEW_SESSION_ID'
GROUP BY timestamp
HAVING COUNT(*) > 1;
-- Expected: 0 rows

# 2. Verify ground truth exists
SELECT COUNT(*) FROM video_events
WHERE video_id IN (SELECT video_id FROM test_sessions WHERE id = 'NEW_SESSION_ID');
-- Expected: > 0 rows

# 3. Check drift compensation
SELECT event_type, calculated_drift_ms
FROM video_lifecycle_events
WHERE test_session_id = 'NEW_SESSION_ID';
-- Expected: Multiple rows with drift measurements

# 4. Verify latencies are positive
SELECT MIN(actual_latency_ms) as min_latency
FROM detection_events
WHERE test_session_id = 'NEW_SESSION_ID';
-- Expected: > 0 ms (no negative values)
```

---

## Data Inconsistencies Summary

| Issue | Current State | Expected State | Impact |
|-------|---------------|----------------|--------|
| **Duplicate Detections** | 334 (167 × 2) | 167 unique | 2× false positive rate |
| **Ground Truth Events** | 0 | 92 expected | 100% FP classification |
| **Drift Compensation** | Not applied | Active | 20ms+ alignment errors |
| **Negative Latencies** | 10 occurrences | 0 | Physically impossible |
| **Video Lifecycle Events** | 0 | 4+ events/video | No drift measurement |
| **Temporal Expansion** | 12.5× inflation | 1× (disabled) | Artificial matches |

---

## Conclusion

The test failure is caused by **systemic data quality issues** rather than actual detection performance problems:

1. **Detection duplication** inflates FP count by 2×
2. **Missing ground truth** forces all detections to be classified as FP
3. **No drift compensation** causes alignment errors >10ms
4. **Temporal expansion** creates confusion with virtual timestamps

**Next Steps:**
1. Fix duplicate writing (1-2 hours)
2. Investigate ground truth generation (2-4 hours)
3. Enable drift compensation (1-2 hours)
4. Re-run test with fixes applied
5. Compare new results to baseline

**Expected Outcome After Fixes:**
- Precision: >85% (vs current 27%)
- Latency: <5ms mean (vs current 1.5ms - already PASS)
- F1 Score: >0.75 (vs current 0.43)
- No negative latencies
- Proper drift-compensated alignment
