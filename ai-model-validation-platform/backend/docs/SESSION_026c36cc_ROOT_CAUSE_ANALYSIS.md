# Session 026c36cc Root Cause Analysis

**Session ID**: `026c36cc-3801-4aa7-971f-b54c24d27505`
**Investigation Date**: 2025-11-04
**Status**: Root Cause Identified

---

## Executive Summary

Frontend displays **"No detections found"** but database contains **108 valid detections**. Root cause: Detection assignment logic fails to populate `video_id` and `sequence_video_result_id` fields, causing frontend filtering to return empty results.

---

## Database Evidence

### Detection Events Table
```sql
Total Detections: 108
  - With video_id: 0
  - With video_id NULL: 108
  - With sequence_video_result_id: 0
  - With sequence_video_result_id NULL: 108

Detection Timeline:
  First: 1762250708.073777 (2025-11-04 10:05:08)
  Last:  1762250725.058964 (2025-11-04 10:05:25)
  Duration: ~17 seconds
```

### Test Session Metadata
```json
{
  "sequence_id": "a19211af-08cd-4bef-8997-10bd82cd70ce",
  "video_ids": [
    "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",
    "550e3cf8-2755-42df-8c3c-041300735f93"
  ],
  "total_videos": 2,
  "videos_completed": 2,
  "video_timing": {
    "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5": {
      "started_at": 1762250712.891,
      "ended_at": 1762250718.179,
      "detection_count": 0
    },
    "550e3cf8-2755-42df-8c3c-041300735f93": {
      "started_at": 1762250718.787,
      "ended_at": 1762250723.972,
      "detection_count": 0
    }
  }
}
```

### Sequence Video Results
```
Video 0:
  ID: e1514388-fca9-4f2d-a13d-dd315630dff6
  Video ID: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
  Start Time: NULL
  End Time: NULL
  Detections: 0
  Status: pending

Video 1:
  ID: 728abae3-a695-43c7-8f0b-daaa4ce86ba7
  Video ID: 550e3cf8-2755-42df-8c3c-041300735f93
  Start Time: NULL
  End Time: NULL
  Detections: 0
  Status: pending
```

---

## Root Cause Analysis

### Critical Bug: Detection Assignment Failure

**Problem**: When detection events are created, the following fields are never populated:
- `detection_events.video_id` → Should reference `videos.id`
- `detection_events.sequence_video_result_id` → Should reference `sequence_video_results.id`

**Impact Chain**:
1. Detections are captured from LabJack hardware (108 detections)
2. Detections are stored in `detection_events` table
3. But `video_id` and `sequence_video_result_id` remain NULL
4. Frontend queries: `/api/detection-events?session_id={id}&video_id={videoId}`
5. Backend filters: `detections.filter(d => d.video_id === videoId)`
6. Since `video_id` is NULL, filter returns `[]`
7. Frontend displays: "No detections found"

### Expected Behavior

**Detection Creation Flow**:
```
1. LabJack detects signal at timestamp T
2. Determine which video was active at T:
   - Query sequence_video_results for current video
   - Match T against video_start_time ≤ T ≤ video_end_time
3. Assign detection to video:
   - detection_events.video_id = videos.id
   - detection_events.sequence_video_result_id = sequence_video_results.id
4. Store detection with proper linkage
```

**Current Broken Flow**:
```
1. LabJack detects signal at timestamp T
2. ❌ Video matching logic FAILS or SKIPPED
3. Store detection with NULL video_id
4. Frontend cannot filter by video
```

---

## Additional Issues Discovered

### 1. Sequence Video Results Missing Timing Data
```
sequence_video_results.video_start_time = NULL
sequence_video_results.video_end_time = NULL
```

**Impact**: Cannot determine which detections belong to which video, even if we wanted to retroactively fix the data.

**Expected**: These fields should be populated from session metadata:
```python
sequence_video_results.video_start_time = 1762250712.891  # Video 0
sequence_video_results.video_end_time = 1762250718.179

sequence_video_results.video_start_time = 1762250718.787  # Video 1
sequence_video_results.video_end_time = 1762250723.972
```

### 2. Video Test Sequences Out of Sync
```
video_test_sequences.status = "running"  # Should be "completed"
video_test_sequences.completed_videos = 0  # Should be 2
```

Session metadata says completed, but `video_test_sequences` table disagrees.

---

## Code Locations to Investigate

### Backend Detection Recording Service
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/raw_labjack_integration.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/precision_timing_service.py`

**Search for**:
```python
# Find where detection_events are created
"INSERT INTO detection_events"
"DetectionEvent("
"create_detection_event"

# Find video assignment logic
"video_id ="
"sequence_video_result_id ="
"assign_video_to_detection"
```

### Video Sequence Orchestrator
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`

**Look for**:
- Video timing recording
- Sequence video results creation
- Detection-to-video linkage logic

### Session Completion Service
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/session_completion_service.py`

**Check if**:
- Session completion updates sequence_video_results timing
- Detection reassignment happens on completion
- video_test_sequences status is updated

---

## Fix Strategy

### Immediate Fix (Band-Aid)
Create a retroactive assignment script:
```python
# Assign detections to videos based on timestamp matching
for detection in detections:
    for video_result in sequence_video_results:
        if video_result.start <= detection.timestamp <= video_result.end:
            detection.video_id = video_result.video_id
            detection.sequence_video_result_id = video_result.id
            break
```

### Proper Fix (Root Cause)
1. **Fix detection creation logic**:
   - When storing detection, query current active video
   - Assign video_id and sequence_video_result_id immediately
   - Add validation: REQUIRE these fields before insert

2. **Fix sequence video results timing**:
   - Populate video_start_time/end_time when video starts/ends
   - Update from session metadata if available
   - Add database constraint: NOT NULL after video completion

3. **Fix session completion**:
   - Update video_test_sequences.status to "completed"
   - Update video_test_sequences.completed_videos count
   - Ensure sequence_video_results timing is finalized

---

## Testing Verification

### Database Queries to Run After Fix
```sql
-- Should return 0 (all detections have video_id)
SELECT COUNT(*) FROM detection_events
WHERE test_session_id = '026c36cc-3801-4aa7-971f-b54c24d27505'
AND video_id IS NULL;

-- Should match total detections
SELECT COUNT(*) FROM detection_events
WHERE test_session_id = '026c36cc-3801-4aa7-971f-b54c24d27505'
AND video_id IS NOT NULL;

-- Should show proper distribution
SELECT video_id, COUNT(*) as count
FROM detection_events
WHERE test_session_id = '026c36cc-3801-4aa7-971f-b54c24d27505'
GROUP BY video_id;
```

### Frontend Verification
1. Navigate to session `026c36cc-3801-4aa7-971f-b54c24d27505`
2. Select Video 1 from dropdown
3. Verify detections table shows data
4. Select Video 2 from dropdown
5. Verify detections table shows data
6. Check "All Videos" shows combined results

---

## Related Issues

- Similar to Session `463b7ec5` Video 2 zero detections issue
- Detection assignment logic appears to be broken across multiple sessions
- This is a **systemic regression**, not an isolated incident

## Priority

**P0 - Critical Production Blocker**

This affects ALL multi-video test sessions. Users cannot view detection results despite data being captured correctly.

---

## Files Referenced

- Database: `/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db`
- Investigation Script: (inline Python in bash)
- Related Docs:
  - `SESSION_463b7ec5_VIDEO_2_ZERO_DETECTIONS_ROOT_CAUSE.md`
  - `VIDEO_2_DETECTION_ASSIGNMENT_BUG_ANALYSIS.md`
