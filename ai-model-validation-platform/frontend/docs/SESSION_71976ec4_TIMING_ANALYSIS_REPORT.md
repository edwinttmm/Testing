# Session 71976ec4-b37d-4b19-8df7-11fefcb9bba7 Timing Analysis Report

**Date:** 2025-11-03
**Session Duration:** 18.27 seconds (17:41:08 - 17:41:26)
**Total Detections:** 268
**Videos in Sequence:** 2

---

## Executive Summary

### 🚨 CRITICAL ISSUES IDENTIFIED

1. **Incorrect Video Assignment**: All 268 detections assigned to Video 1, despite 51 occurring during Video 2's time window
2. **Metadata Inconsistency**: Detection counts in metadata don't match database reality
3. **Timing Window Mismatch**: Actual detections span 18.8s but expected video windows only cover 10.5s total
4. **Missing Video 2 Detections**: 51 detections occurred in Video 2 time window but were incorrectly assigned to Video 1

---

## Detailed Timing Breakdown

### Session-Level Timing
```
Video Start Timestamp (session): 1762191668.606187
Started At:                       2025-11-03 17:41:08.446283
Completed At:                     2025-11-03 17:41:26.718949
Session Duration:                 18.27 seconds
```

### Detection Timeline
```
First Detection:  1762191668.607250 (session start + 0.001s)
Last Detection:   1762191687.450024 (session start + 18.844s)
Detection Span:   18.843 seconds
Total Detections: 268
```

---

## Video 1: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5

### Expected Window (from sequence_metadata)
```
Start Time:      1762191677.750000
End Time:        1762191683.072000
Duration:        5.062 seconds
Expected Detections: 183
```

### Actual Detections (from detection_events table)
```
Detections:      268 (ALL detections in session)
First Detection: 1762191668.607250
Last Detection:  1762191687.450024
Time Span:       18.843 seconds
```

### Discrepancies
```
❌ Detection count: DB=268, Metadata=183 (difference: +85)
❌ Start offset: Detections start 9.143s BEFORE expected window
❌ End offset: Detections extend 4.378s BEYOND expected window
```

### Evidence
- Detections begin at session start (1762191668.607)
- Expected window doesn't start until 1762191677.750 (9+ seconds later)
- This suggests the "expected window" in metadata is incorrect

---

## Video 2: 550e3cf8-2755-42df-8c3c-041300735f93

### Expected Window (from sequence_metadata)
```
Start Time:      1762191683.453000
End Time:        1762191688.610000
Duration:        5.062 seconds
Expected Detections: 0
```

### Actual Detections (from detection_events table)
```
Detections in DB: 0 (assigned to this video_id)
Metadata Claims:  0
```

### CRITICAL FINDING: Misassigned Detections
Query for detections within Video 2's time window (1762191683.453 - 1762191688.610):
```
🚨 51 detections occurred during Video 2's time window
🚨 ALL 51 were assigned to Video 1's video_id
```

### Evidence of Misassignment
Last 10 detections (all after Video 2 started at 1762191683.453):
```
1. 1762191687.450024 -> Assigned to Video 1 ❌
2. 1762191687.377263 -> Assigned to Video 1 ❌
3. 1762191687.147174 -> Assigned to Video 1 ❌
4. 1762191686.978185 -> Assigned to Video 1 ❌
5. 1762191686.867975 -> Assigned to Video 1 ❌
6. 1762191686.793979 -> Assigned to Video 1 ❌
7. 1762191686.728975 -> Assigned to Video 1 ❌
8. 1762191686.663738 -> Assigned to Video 1 ❌
9. 1762191686.598862 -> Assigned to Video 1 ❌
10. 1762191686.533628 -> Assigned to Video 1 ❌
```

All of these timestamps are >= 1762191683.453 (Video 2 start time).

---

## Gap Analysis

### Video Transition Gap
```
Video 1 ends:    1762191683.072000
Video 2 starts:  1762191683.453000
Gap duration:    0.381 seconds
```

This 381ms gap is reasonable for video transition, but detections continue to be assigned to Video 1 even after Video 2 starts.

---

## Detection Distribution

### Time-Based Distribution
```
Total session time:        18.843s
Video 1 expected window:   5.062s (26.9%)
Video 2 expected window:   5.062s (26.9%)
Total expected coverage:   10.124s (53.7%)
Unaccounted time:          8.719s (46.3%)
```

### Actual Detection Distribution
```
Detections in Video 1 window: 217 (81.0%)
Detections in Video 2 window: 51 (19.0%)
Detections before Video 1:   ~34 (12.7%)
Detections after Video 2:    ~0 (0%)
```

### Detection Density
```
Overall:  268 detections / 18.843s = 14.2 det/sec
Video 1:  217 detections / 5.062s = 42.9 det/sec
Video 2:  51 detections / 5.062s = 10.1 det/sec
```

---

## Root Cause Analysis

### Primary Issue: Incorrect video_id Assignment
The `video_id` field in `detection_events` table is set to Video 1's ID for ALL detections, regardless of when they occurred.

### Evidence:
1. **Database state**: All 268 detections have `video_id = '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5'`
2. **Timing evidence**: 51 detections occurred AFTER Video 2 started (timestamp >= 1762191683.453)
3. **Metadata inconsistency**: Metadata claims 183 detections for Video 1, but DB has 268

### Likely Bug Location:
The code that assigns `video_id` when storing detection events is:
- Not checking the current video in the sequence
- Not using the video timing windows to determine correct video_id
- Defaulting to the first video in sequence or session's primary video_id

### Expected Behavior:
```python
def assign_video_id(labjack_timestamp, sequence_metadata):
    for video in sequence_metadata['videos']:
        if video['started_at'] <= labjack_timestamp <= video['ended_at']:
            return video['video_id']
    return None  # or first video as fallback
```

### Actual Behavior:
```python
# Appears to be using session.video_id for ALL detections
detection.video_id = test_session.video_id
```

---

## Secondary Issue: Timing Window Calculation

### Problem:
The expected timing windows in `sequence_metadata` don't match when detections actually started:

```
Expected Video 1 start: 1762191677.750000
Actual first detection: 1762191668.607250
Difference: 9.143 seconds
```

### Possible Causes:
1. **Session start != Video start**: Videos may have been loading/buffering before playback
2. **Timing metadata created post-hoc**: The `started_at` times in metadata may reflect UI events (play button click) rather than actual LabJack/detection start
3. **Multiple timing references**: System has multiple timing sources that aren't synchronized:
   - `video_start_timestamp` (session level): 1762191668.606187
   - `started_at` (metadata): 1762191677.750000
   - Actual first detection: 1762191668.607250

---

## Impact Assessment

### Data Integrity
- ❌ **Critical**: 51 detections (19%) assigned to wrong video
- ❌ **High**: Cannot trust per-video metrics (precision, recall, latency)
- ⚠️ **Medium**: Overall session metrics are intact (total detection count correct)

### User Experience
- ❌ Results page shows incorrect per-video statistics
- ❌ Video 2 appears to have 0 detections when it had 51
- ❌ Video 1 metrics include detections from Video 2 timeframe

### Ground Truth Matching
- ❌ GT objects for Video 2 cannot match (no detections assigned to Video 2)
- ❌ GT objects for Video 1 may include false matches from Video 2 detections
- ❌ Latency calculations incorrect for misassigned detections

---

## Recommendations

### Immediate Fixes (Priority 1)

1. **Fix video_id assignment logic** in detection event creation:
   ```python
   # In labjack_detection_service.py or detection storage
   def get_current_video_id(timestamp, session):
       if session.sequence_metadata:
           for video in session.sequence_metadata['video_timing'].values():
               if video['started_at'] <= timestamp <= video['ended_at']:
                   return video['video_id']
       return session.video_id  # fallback to session video
   ```

2. **Add validation** when storing detections:
   ```python
   if detection.labjack_timestamp < video_timing['started_at']:
       logger.warning(f"Detection before video start: {detection.labjack_timestamp}")
   ```

3. **Migration script** to fix existing data:
   - Query all multi-video sessions
   - Re-assign video_id based on labjack_timestamp vs. video timing windows
   - Update detection_events table
   - Recalculate per-video metrics

### Architecture Improvements (Priority 2)

1. **Single source of truth** for timing:
   - Decide: Is it `video_start_timestamp` (session) or `started_at` (metadata)?
   - Reconcile the 9-second discrepancy

2. **Real-time video tracking**:
   - Store "current_video_id" in session state
   - Update when video transitions occur
   - Use this for detection assignment

3. **Timing validation**:
   - Add checks when metadata is created
   - Validate that video windows cover all detections
   - Alert if detections fall outside expected windows

### Data Recovery (Priority 3)

1. **Re-process Session 71976ec4**:
   ```sql
   -- Reassign detections to Video 2
   UPDATE detection_events
   SET video_id = '550e3cf8-2755-42df-8c3c-041300735f93'
   WHERE test_session_id = '71976ec4-b37d-4b19-8df7-11fefcb9bba7'
   AND labjack_timestamp >= 1762191683.453
   AND labjack_timestamp <= 1762191688.610;
   ```

2. **Recalculate metrics**:
   - Re-run ground truth matching for both videos
   - Update sequence_metadata detection counts
   - Regenerate results summary

---

## Testing Checklist

Before considering this bug fixed:

- [ ] Create new multi-video session
- [ ] Verify detections assigned to correct video_id in real-time
- [ ] Check database after each video completes
- [ ] Validate no detections assigned to wrong video
- [ ] Verify timing windows in metadata match actual detection range
- [ ] Test video transition (gap between videos)
- [ ] Confirm UI shows correct per-video counts
- [ ] Validate ground truth matching works per-video
- [ ] Check latency calculations use correct video reference

---

## Appendix: Raw Data

### Complete Detection Timeline (sample)
```
Detection #1:   1762191668.607250 -> Video 1 (should be Video 1) ✓
Detection #217: 1762191683.400000 -> Video 1 (should be Video 1) ✓
Detection #218: 1762191683.500000 -> Video 1 (should be Video 2) ❌
Detection #268: 1762191687.450024 -> Video 1 (should be Video 2) ❌
```

### Sequence Metadata (JSON)
```json
{
  "video_ids": [
    "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",
    "550e3cf8-2755-42df-8c3c-041300735f93"
  ],
  "total_videos": 2,
  "current_video_index": 1,
  "videos_completed": 2,
  "labjack_enabled": true,
  "video_timing": {
    "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5": {
      "started_at": 1762191677.75,
      "ended_at": 1762191683.072,
      "actual_duration": 5.061995,
      "detection_count": 183,
      "evaluation_result": "pass"
    },
    "550e3cf8-2755-42df-8c3c-041300735f93": {
      "started_at": 1762191683.453,
      "ended_at": 1762191688.61,
      "actual_duration": 5.061995,
      "detection_count": 0,
      "evaluation_result": "pending"
    }
  }
}
```

---

**Report Generated:** 2025-11-03
**Analysis Tool:** SQLite direct query + Python analysis
**Database:** `/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db`
