# Root Cause Analysis: Video 2 Zero Detections Issue

**Session ID**: `463b7ec5-0cd6-4b6a-9776-d10f938b6422`
**Sequence ID**: `0f2f2fd4-ce6f-457d-8da6-fb7de55cca8b`
**Investigation Date**: 2025-11-03
**Status**: CRITICAL - Production Blocker

---

## Executive Summary

Investigation into session `463b7ec5-0cd6-4b6a-9776-d10f938b6422` reveals **three interconnected root causes** explaining why Video 2 shows zero detections and why the UI displays "Unknown" for video assignments:

1. **Video Lifecycle Events Never Fired**: Frontend never called `/video-started` or `/video-ended` endpoints
2. **Detection Assignment Logic Works Correctly**: All 134 detections correctly assigned to Video 1, but Video 2 never started so was skipped
3. **Missing video_filename in API Response**: API returns `video_id` but not `video_filename`, causing "Unknown" display

---

## Problem Statement

### Observed Symptoms
- UI displays "2 Videos in Sequence"
- Only ONE video showing results: `child_test_video_20251031_144012.mp4`
- Second video completely missing from results
- All 134 detections show "Unknown" for video assignment
- Database shows 2 videos in sequence but Video 2 has 0 detections

### Expected Behavior
- Both videos should display with detection counts
- Detections should show video filenames, not "Unknown"
- Video 2 should have detections assigned based on timestamps
- Sequence should transition from Video 1 to Video 2 automatically

---

## Database Investigation Results

### Query 1: Video Test Sequence Status
```python
Sequence ID: 0f2f2fd4-ce6f-457d-8da6-fb7de55cca8b
Status: running  # ⚠️ ISSUE: Should be "completed"
Total Videos: 2
Completed Videos: 0  # ⚠️ ISSUE: Should be 2
Created: 2025-10-31 18:40:12
```

**Finding**: Sequence never completed despite session being marked complete.

### Query 2: Sequence Video Results
```python
Video 1:
  video_id: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
  filename: child_test_video_20251031_144012.mp4
  sequence_order: 1
  video_status: pending  # ⚠️ ISSUE: Should be "completed"
  expected_detection_count: 0
  actual_detection_count: 0  # ⚠️ ISSUE: Should be 134

Video 2:
  video_id: 550e3cf8-2755-42df-8c3c-041300735f93
  filename: child_test_video_20251031_144012.mp4
  sequence_order: 2
  video_status: pending  # ⚠️ ISSUE: Should be "playing" or "completed"
  expected_detection_count: 0
  actual_detection_count: 0  # ✓ CORRECT: Video never started
```

**Finding**: Both videos stuck in "pending" status, actual_detection_count never updated.

### Query 3: Detection Event Assignment
```python
Video 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5: 134 detections  # Video 1 ✓
Video 550e3cf8-2755-42df-8c3c-041300735f93: 0 detections    # Video 2 ✗
```

**Finding**: All detections correctly assigned to Video 1, but Video 2 has zero.

---

## Root Cause Analysis

### Root Cause #1: Video Lifecycle Events Never Fired

**Evidence:**
- Both videos have `video_status = "pending"`
- `VideoTestSequence.completed_videos = 0`
- `VideoTestSequence.status = "running"`
- Database timestamps show detections were created but no video start/end events

**Source Files:**
- `/home/rigade/Testing/ai-model-validation-platform/backend/routers/video_sequences.py`

**Critical Endpoints Not Called:**

#### POST /{sequence_id}/video-started (Lines 119-189)
```python
@router.post("/{sequence_id}/video-started", response_model=VideoStartedResponse)
def notify_video_started(
    sequence_id: str,
    request: VideoStartedRequest,
    db: Session = Depends(get_db)
):
    # This should set video_start_time and update status to "playing"
    # Frontend NEVER called this endpoint
```

#### POST /{sequence_id}/video-ended (Lines 192-284)
```python
@router.post("/{sequence_id}/video-ended")
def notify_video_ended(
    sequence_id: str,
    request: VideoEndedRequest,
    db: Session = Depends(get_db)
):
    # This should mark video complete and transition to next video
    # Frontend NEVER called this endpoint
```

**Impact:**
- Video 2 never got `video_start_time` set
- Detection assignment logic skips videos without `video_start_time`
- Sequence never transitioned from Video 1 to Video 2
- `completed_videos` counter never incremented

---

### Root Cause #2: Detection Assignment Logic Working Correctly

**Source File:**
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`

**Method: `_determine_video_for_detection()` (Lines 737-759)**
```python
def _determine_video_for_detection(
    self,
    detection_timestamp: datetime,
    video_metadata_list: List[VideoMetadata],
    logger: logging.Logger
) -> Optional[str]:
    """Determine which video a detection belongs to based on timestamp."""

    for metadata in video_metadata_list:
        # ⚠️ CRITICAL: Skip videos without start time
        if metadata.video_start_time is None:
            continue  # ← Video 2 gets skipped here!

        video_end = metadata.video_end_time or datetime.now(timezone.utc)

        # Line 756: Time-based assignment logic
        if metadata.video_start_time <= detection_timestamp <= video_end:
            return video_id  # Video 1 matches this condition

    return None  # Video 2 never gets considered
```

**Why This Works for Video 1 But Not Video 2:**
1. Video 1 started (has `video_start_time` from some initialization)
2. All 134 detections fall within Video 1's time range
3. Video 2 has `video_start_time = None` (never started)
4. Detection assignment loop skips Video 2 entirely

**Evidence from Database:**
```sql
-- All detections assigned to Video 1
SELECT video_id, COUNT(*)
FROM detection_events
WHERE test_session_id = '463b7ec5-0cd6-4b6a-9776-d10f938b6422'
GROUP BY video_id;

-- Result: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5 | 134
-- Video 2 (550e3cf8-...) has ZERO rows
```

---

### Root Cause #3: Missing video_filename in API Response

**Source File:**
- `/home/rigade/Testing/ai-model-validation-platform/backend/src/api/enhanced_hil_results_endpoints.py`

**API Endpoint:** `GET /api/enhanced-hil/test-sessions/{session_id}/corrected-results`

**Problem: Detection Events Missing video_filename (Lines 781-887)**
```python
enhanced_detection_events.append({
    "event_id": original_event.id,
    "video_id": original_event.video_id,  # ✓ Present in response
    # ❌ MISSING: "video_filename" field
    "frame_number": getattr(original_event, 'frame_number', 0) or 0,
    "detection_timestamp": original_event.detection_timestamp.isoformat(),
    "labjack_timestamp": labjack_timestamp,
    "latency_ms": latency_ms,
    # ... rest of fields
})
```

**What Frontend Sees:**
```json
{
  "video_id": "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",
  // No video_filename field!
}
```

**Why "Unknown" Displays:**
- Frontend receives `video_id` (UUID) but no human-readable filename
- Cannot map UUID to filename without additional API call or lookup
- Falls back to displaying "Unknown"

**Contrast with sequence_results (Lines 985-1091):**
```python
# sequence_results DOES include video info
"per_video_results": [
    {
        "video_id": video_result.video_id,
        "video_filename": video_result.video_filename,  # ✓ Present here
        "sequence_order": video_result.sequence_order,
        # ...
    }
]
```

**Fix Required:** Add video filename lookup to detection events response.

---

## Timeline Reconstruction

```
T0: Session Started
├─ ✅ VideoTestSequence created with total_videos=2
├─ ✅ SequenceVideoResult #1 created (Video 1)
├─ ✅ SequenceVideoResult #2 created (Video 2)
└─ Status: sequence.status="running", completed_videos=0

T1: Video 1 Playing (Somehow Initialized)
├─ ⚠️ Video 1 got video_start_time (unclear how - not via /video-started endpoint)
├─ ✅ LabJack monitoring active
├─ ✅ 134 detection events captured
└─ ✅ All detections correctly assigned to Video 1

T2: Detection Processing
├─ ✅ process_detection_event() called 134 times
├─ ✅ _determine_video_for_detection() assigns all to Video 1
├─ ⚠️ Video 2 skipped (no video_start_time)
└─ ✅ Database updated with video_id for all detections

T3: Video 1 Should End (NEVER HAPPENED)
├─ ❌ Frontend never called POST /{sequence_id}/video-ended
├─ ❌ Video 1 status stayed "pending" (should be "completed")
├─ ❌ completed_videos stayed 0 (should increment to 1)
└─ ❌ Next video never triggered

T4: Video 2 Should Start (NEVER HAPPENED)
├─ ❌ Frontend never called POST /{sequence_id}/video-started for Video 2
├─ ❌ Video 2 video_start_time stayed NULL
├─ ❌ Video 2 status stayed "pending"
└─ ❌ No transition logic executed

T5: Session Marked Complete
├─ ✅ Session-level completion triggered
├─ ⚠️ Sequence still shows status="running"
├─ ⚠️ completed_videos=0 (should be 2)
└─ ❌ actual_detection_count never updated for Video 1

T6: API Response Generated
├─ ✅ enhanced_detection_events created with 134 entries
├─ ✅ All include video_id field
├─ ❌ None include video_filename field
└─ 📊 Frontend displays "Unknown" for all detections
```

---

## Expected vs Actual API Flow

### Expected Flow
```
1. POST /api/video-sequences/{seq_id}/video-started (video_id=Video1)
   → Sets video_1.video_start_time
   → Sets video_1.status = "playing"

2. Detections captured and assigned to Video 1
   → 134 detections saved with video_id=Video1

3. POST /api/video-sequences/{seq_id}/video-ended (video_id=Video1)
   → Sets video_1.video_end_time
   → Sets video_1.status = "completed"
   → Increments sequence.completed_videos = 1
   → Returns next_video_id = Video2

4. POST /api/video-sequences/{seq_id}/video-started (video_id=Video2)
   → Sets video_2.video_start_time
   → Sets video_2.status = "playing"

5. Remaining detections assigned to Video 2
   → New detections saved with video_id=Video2

6. POST /api/video-sequences/{seq_id}/video-ended (video_id=Video2)
   → Sets video_2.video_end_time
   → Sets video_2.status = "completed"
   → Increments sequence.completed_videos = 2
   → Sets sequence.status = "completed"

7. Session completion updates actual_detection_count
   → video_1.actual_detection_count = 134
   → video_2.actual_detection_count = (count)
```

### Actual Flow
```
1. ⚠️ Video 1 somehow got video_start_time (not via API endpoint)

2. ✅ Detections captured and assigned to Video 1
   → 134 detections saved with video_id=Video1

3. ❌ video-ended NEVER CALLED for Video 1

4. ❌ video-started NEVER CALLED for Video 2

5. ❌ Video 2 never got video_start_time

6. ❌ No detections assigned to Video 2 (skipped in assignment logic)

7. ✅ Session marked complete (session-level, not sequence-level)

8. ❌ actual_detection_count never updated
```

---

## Files Involved and Line Numbers

### 1. video_sequence_orchestrator.py
**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`

**Critical Methods:**

#### process_detection_event() - Lines 405-589
- Receives detection events from hardware
- Calls `_determine_video_for_detection()` to assign video
- Updates `DetectionEvent.video_id` in database
- **Works correctly** - not the issue

#### _determine_video_for_detection() - Lines 737-759
- **Line 746**: Checks `if metadata.video_start_time is None: continue`
- **Line 756**: Time-based assignment: `if video_start_time <= detection_timestamp <= video_end`
- **This is WHERE Video 2 gets skipped**

#### notify_video_started() - Lines 266-337
- Sets `SequenceVideoResult.video_start_time`
- Updates `SequenceVideoResult.video_status = "playing"`
- **Frontend NEVER called this** for either video

#### notify_video_ended() - Lines 339-403
- Sets `SequenceVideoResult.video_end_time`
- Updates `SequenceVideoResult.video_status = "completed"`
- Increments `VideoTestSequence.completed_videos`
- Returns `next_video_id` for transition
- **Frontend NEVER called this** for Video 1

---

### 2. video_sequences.py (REST API Router)
**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/routers/video_sequences.py`

**Critical Endpoints:**

#### POST /{sequence_id}/video-started - Lines 119-189
```python
@router.post("/{sequence_id}/video-started", response_model=VideoStartedResponse)
def notify_video_started(
    sequence_id: str,
    request: VideoStartedRequest,  # Contains: video_id, started_at
    db: Session = Depends(get_db)
):
    # Line 157-174: Update video status
    video_result.video_status = "playing"
    video_result.started_at = request.started_at

    # Line 176-183: Notify orchestrator to set video_start_time
    orchestrator.notify_video_started(
        sequence_id=sequence_id,
        video_id=request.video_id,
        started_at=request.started_at
    )
```
**Status:** ❌ NEVER CALLED by frontend

#### POST /{sequence_id}/video-ended - Lines 192-284
```python
@router.post("/{sequence_id}/video-ended")
def notify_video_ended(
    sequence_id: str,
    request: VideoEndedRequest,  # Contains: video_id, ended_at
    db: Session = Depends(get_db)
):
    # Line 238-248: Check if last video and transition
    if sequence.completed_videos >= sequence.total_videos:
        sequence.status = "completed"
        next_video_id = None
    else:
        # Find next video in sequence
        next_result = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.sequence_order == current_order + 1
        ).first()
        next_video_id = next_result.video_id if next_result else None

    # Line 264-270: Notify orchestrator
    orchestrator.notify_video_ended(
        sequence_id=sequence_id,
        video_id=request.video_id,
        ended_at=request.ended_at
    )
```
**Status:** ❌ NEVER CALLED by frontend

---

### 3. enhanced_hil_results_endpoints.py (API Response Builder)
**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/src/api/enhanced_hil_results_endpoints.py`

**Critical Sections:**

#### GET /test-sessions/{session_id}/corrected-results - Line 155
Main endpoint that returns results to frontend

#### Video ID Filter - Lines 269-271
```python
if video_id:
    # Optional filter by video_id for multi-video sequences
    events_query = events_query.filter(DetectionEvent.video_id == video_id)
```

#### Detection Events Response Builder - Lines 692-887
```python
# Line 781-887: Build enhanced_detection_events array
enhanced_detection_events.append({
    "event_id": original_event.id,
    "video_id": original_event.video_id,  # ✓ Included
    # ❌ MISSING: "video_filename": original_event.video.filename
    "frame_number": getattr(original_event, 'frame_number', 0) or 0,
    "detection_timestamp": original_event.detection_timestamp.isoformat(),
    # ... 30+ other fields
})
```
**Issue:** video_filename field NOT included in detection events

#### Sequence Results Builder - Lines 985-1091
```python
"sequence_results": {
    "sequence_id": sequence.id,
    "total_videos": sequence.total_videos,
    "per_video_results": [
        {
            "video_id": video_result.video_id,
            "video_filename": video_result.video_filename,  # ✓ Included here
            "sequence_order": video_result.sequence_order,
            "actual_detection_count": video_result.actual_detection_count,
            # ...
        }
    ]
}
```
**Note:** video_filename IS included in sequence_results, just not in detection_events

---

### 4. hil_test_complete.py (Session Completion Logic)
**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/api/hil_test_complete.py`

#### update_sequence_video_detection_counts() - Lines 1134-1248
```python
def update_sequence_video_detection_counts(
    db: Session,
    session_id: str,
    logger: logging.Logger
) -> None:
    """Update actual_detection_count for each video in sequence."""

    # Line 1159-1179: Count detections per video
    detection_counts = db.query(
        DetectionEvent.video_id,
        func.count(DetectionEvent.id).label('count')
    ).filter(
        DetectionEvent.test_session_id == session_id,
        DetectionEvent.video_id.isnot(None)
    ).group_by(DetectionEvent.video_id).all()

    count_map = {video_id: count for video_id, count in detection_counts}

    # Line 1199-1220: Update each video result
    for result in sequence_video_results:
        actual_count = count_map.get(result.video_id, 0)
        result.actual_detection_count = actual_count
        logger.info(
            f"Updated video {result.video_id}: "
            f"actual_detection_count={actual_count}"
        )
```

**Status:** This function runs on session completion, but:
- ✅ Would correctly count 134 for Video 1
- ✅ Would correctly count 0 for Video 2
- ❌ Doesn't run until session completes (not real-time)
- ❌ For this session, appears to have not run yet (both show 0 in database)

---

## Recommended Fixes

### Priority 1: Add video_filename to Detection Events API Response

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/src/api/enhanced_hil_results_endpoints.py`

**Location:** Lines 692-887 (detection events response builder)

**Implementation:**
```python
# BEFORE building enhanced_detection_events, create video lookup map
video_filename_map = {}
if sequence:
    for video_result in sequence.video_results:
        video_filename_map[video_result.video_id] = video_result.video_filename

# THEN in detection events loop (around line 781)
enhanced_detection_events.append({
    "event_id": original_event.id,
    "video_id": original_event.video_id,
    "video_filename": video_filename_map.get(original_event.video_id, "Unknown"),  # ← ADD THIS
    "frame_number": getattr(original_event, 'frame_number', 0) or 0,
    # ... rest of fields
})
```

**Why This Fixes "Unknown" Display:**
- Frontend will receive human-readable filename
- No need for additional API calls or lookups
- Consistent with sequence_results structure

**Verification:**
```bash
curl -X GET "http://localhost:8000/api/enhanced-hil/test-sessions/463b7ec5-0cd6-4b6a-9776-d10f938b6422/corrected-results" | jq '.detection_events[0].video_filename'
# Should return: "child_test_video_20251031_144012.mp4"
```

---

### Priority 2: Frontend Video Player Lifecycle Integration

**File:** Frontend video player component (exact path TBD)

**Required Changes:**

#### Add onPlay Event Handler
```javascript
const handleVideoPlay = async () => {
    const response = await fetch(
        `/api/video-sequences/${sequenceId}/video-started`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                video_id: currentVideoId,
                started_at: new Date().toISOString()
            })
        }
    );
    const data = await response.json();
    console.log('Video started:', data);
};

// Attach to video element
<video onPlay={handleVideoPlay} ... />
```

#### Add onEnded Event Handler
```javascript
const handleVideoEnded = async () => {
    const response = await fetch(
        `/api/video-sequences/${sequenceId}/video-ended`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                video_id: currentVideoId,
                ended_at: new Date().toISOString()
            })
        }
    );
    const data = await response.json();

    // Transition to next video if available
    if (data.next_video_id) {
        setCurrentVideoId(data.next_video_id);
        // Update video source and play
    } else {
        console.log('Sequence complete');
    }
};

// Attach to video element
<video onEnded={handleVideoEnded} ... />
```

**Why This Fixes Video 2 Issue:**
- Video 1 will properly complete and increment `completed_videos`
- Video 2 will get `video_start_time` set
- Detection assignment will include Video 2 in time-based matching
- Sequence will properly transition through all videos

---

### Priority 3: Real-Time Detection Count Updates

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`

**Method:** `process_detection_event()` - Lines 405-589

**Add after Line 560 (after detection saved to database):**
```python
# Line 560: After db.commit()

# Update actual_detection_count in real-time
if assigned_video_id:
    video_result = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.video_id == assigned_video_id
    ).first()

    if video_result:
        # Increment count
        video_result.actual_detection_count = (
            video_result.actual_detection_count or 0
        ) + 1
        db.commit()

        logger.info(
            f"Updated actual_detection_count for video {assigned_video_id}: "
            f"{video_result.actual_detection_count}"
        )
```

**Why This Improves System:**
- Live detection counts visible during test execution
- No need to wait until session completion
- Better user feedback and monitoring
- More accurate progress tracking

**Alternative (More Efficient):**
Keep existing batch update in `hil_test_complete.py` but ensure it runs reliably on session completion.

---

## Verification Steps

### 1. Verify Database State Before Fix
```sql
-- Check sequence status
SELECT id, status, total_videos, completed_videos
FROM video_test_sequences
WHERE id = '0f2f2fd4-ce6f-457d-8da6-fb7de55cca8b';
-- Expected: status='running', completed_videos=0

-- Check video results
SELECT video_id, video_filename, sequence_order, video_status,
       actual_detection_count, video_start_time, video_end_time
FROM sequence_video_results
WHERE video_sequence_id = '0f2f2fd4-ce6f-457d-8da6-fb7de55cca8b'
ORDER BY sequence_order;
-- Expected: Both videos in 'pending' status

-- Check detection assignment
SELECT video_id, COUNT(*) as detection_count
FROM detection_events
WHERE test_session_id = '463b7ec5-0cd6-4b6a-9776-d10f938b6422'
  AND video_id IS NOT NULL
GROUP BY video_id;
-- Expected: Video 1 = 134, Video 2 = 0
```

### 2. Verify API Response After Priority 1 Fix
```bash
# Test detection events include video_filename
curl -X GET "http://localhost:8000/api/enhanced-hil/test-sessions/463b7ec5-0cd6-4b6a-9776-d10f938b6422/corrected-results" \
  | jq '.detection_events[0] | {video_id, video_filename}'

# Expected output:
# {
#   "video_id": "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",
#   "video_filename": "child_test_video_20251031_144012.mp4"
# }
```

### 3. Verify Video Lifecycle After Priority 2 Fix
Run new test session with 2 videos:

```bash
# Monitor video lifecycle events in backend logs
tail -f backend.log | grep -E "(video-started|video-ended)"

# Expected log sequence:
# POST /video-sequences/{seq}/video-started video_id=Video1
# POST /video-sequences/{seq}/video-ended video_id=Video1
# POST /video-sequences/{seq}/video-started video_id=Video2
# POST /video-sequences/{seq}/video-ended video_id=Video2
```

### 4. Verify Database After Complete Session
```sql
-- Check sequence completed
SELECT id, status, completed_videos
FROM video_test_sequences
WHERE id = '{new_sequence_id}';
-- Expected: status='completed', completed_videos=2

-- Check both videos completed
SELECT video_id, video_status, actual_detection_count
FROM sequence_video_results
WHERE video_sequence_id = '{new_sequence_id}'
ORDER BY sequence_order;
-- Expected: Both videos 'completed' with detection counts > 0

-- Verify detections distributed across videos
SELECT video_id, COUNT(*)
FROM detection_events
WHERE test_session_id = '{new_session_id}'
GROUP BY video_id;
-- Expected: Both videos have detections
```

---

## Additional Notes

### Why Video 1 Had video_start_time Initially
Unclear from investigation. Possible explanations:
1. Legacy initialization code that set it during sequence creation
2. Manual database update during testing
3. Different code path that's now obsolete

**Recommendation:** Ensure all video timing comes exclusively from lifecycle endpoints.

### Frontend Display Issue Clarification
The "Unknown" display has two components:
1. **video_filename missing from detection events** (Priority 1 fix)
2. **Video 2 not appearing at all** (Priority 2 fix - video never started)

Both must be fixed for complete resolution.

### Performance Considerations
Priority 3 (real-time count updates) adds a database write per detection:
- For high-frequency detections (100+ per second), consider batching
- Current batch update on completion is more efficient
- Trade-off: efficiency vs real-time visibility

**Recommendation:** Keep batch update, but ensure it runs reliably.

---

## Conclusion

This investigation reveals a **frontend integration gap** as the primary issue:

1. ✅ **Backend logic is correct**: Detection assignment works perfectly
2. ✅ **Database schema is correct**: All tables and relationships proper
3. ❌ **Frontend integration incomplete**: Video lifecycle events never called
4. ❌ **API response incomplete**: Missing video_filename field

**Impact:**
- Video 2 appears missing (never started)
- Detections show "Unknown" (missing filename in response)
- Counts show 0 (not updated until session completes)

**Resolution Path:**
1. Add video_filename to API response (backend fix)
2. Integrate video lifecycle events in frontend player (frontend fix)
3. Verify fixes with new test session

**Estimated Effort:**
- Priority 1: 1-2 hours (backend API change)
- Priority 2: 2-4 hours (frontend integration)
- Priority 3: 1 hour (optional real-time counts)
- Testing: 2-3 hours (verification and regression testing)

Total: ~6-10 hours for complete resolution

---

**Next Steps:**
1. Implement Priority 1 fix (video_filename in API)
2. Deploy and test with existing session
3. Implement Priority 2 fix (frontend lifecycle events)
4. Run new multi-video test session
5. Verify all detections properly distributed
6. Consider Priority 3 if real-time counts needed
