# Multi-Video Sequence Root Cause Analysis
## Session 6d05fcd1-0c9b-432b-acbd-675c5e3683c9

**Date**: 2025-11-05
**Issue**: Frame 120 bunching, missing Video 2 data, timing anomalies
**Root Cause**: Missing video lifecycle events in multi-video sequence

---

## Executive Summary

The timing issues in session `6d05fcd1` are **NOT** caused by timestamp calculation bugs. They are caused by **missing video lifecycle events** (`video-started`, `video-ended`) in a multi-video sequence test.

Without these events, the backend cannot:
1. Assign detections to the correct video (`video_id` remains NULL)
2. Calculate video-relative timestamps correctly
3. Reset frame numbers for Video 2
4. Apply proper timing offsets for sequential videos

---

## Evidence

### 1. Session Configuration

```sql
Session ID: 6d05fcd1-0c9b-432b-acbd-675c5e3683c9
Has Video Sequence: TRUE
Sequence ID: 3aea0970-4d24-4e8c-9d32-cab68bc3e58d
Total Videos: 2
Sequence Status: running
```

**Finding**: This is a multi-video sequence test with 2 videos.

### 2. Video Lifecycle Events (MISSING!)

```sql
Video 0: child_test_video_20251031_144012.mp4 (5.04s, 121 frames)
  video_id: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
  status: pending              ❌ Should be "completed"
  start_time: NULL             ❌ Should be ~1762352910.606
  end_time: NULL               ❌ Should be ~1762352915.648
  duration_ms: NULL            ❌ Should be ~5041ms
  detection_count: 0           ❌ Should be ~80

Video 1: Child_20251031_143523.mp4 (5.04s, 121 frames)
  video_id: 550e3cf8-2755-42df-8c3c-041300735f93
  status: pending              ❌ Should be "completed"
  start_time: NULL             ❌ Should be ~1762352915.648
  end_time: NULL               ❌ Should be ~1762352920.690
  duration_ms: NULL            ❌ Should be ~5041ms
  detection_count: 0           ❌ Should be ~81
```

**Finding**: Both videos have NULL timing data, indicating the frontend never sent `video-started` or `video-ended` events to the backend.

### 3. Detection Events (All Unassigned)

```sql
video_id: NULL                ❌ Should be split between two video_ids
  Count: 161
  Frames: 4 - 309             ❌ Spans both videos without reset
  Frame 120: 2 detections     ⚠️ This is the "bunching" symptom
  Time Range: 0.198s - 12.890s ❌ Spans both videos (2 × 5.04s = 10.08s)
```

**Finding**: All 161 detections are orphaned with `video_id: NULL` because the backend cannot determine which video they belong to.

### 4. Frame Number Analysis

Expected behavior:
- **Video 1**: Frames 0-120 (5.04s @ 24fps = 121 frames)
- **Video 2**: Frames 0-120 (reset to 0, another 121 frames)

Actual behavior:
- **All detections**: Frames 4-309 (continuous, no reset)
- **Frame 120 bunching**: 2 detections at exactly Frame 120
  - This is likely the transition point between videos
  - Without reset, Video 2 detections start at Frame 121+

### 5. Timestamp Analysis

```
Detection timestamps: 0.198s - 12.890s
Video 1 duration: 5.04s
Video 2 duration: 5.04s
Total expected: ~10.08s
Actual span: 12.69s (includes startup delays)
```

**Finding**: Timestamps span both videos but are calculated relative to a single video start time, not per-video relative times.

---

## Root Cause Chain

```
1. Frontend plays Video 1
   └─> ❌ No video-started event sent to backend
   └─> ❌ SequenceVideoResult.video_start_time remains NULL

2. Detections arrive from LabjJack
   └─> video_sequence_orchestrator.py::process_detection_event()
   └─> _determine_video_for_detection() checks video timing
   └─> ❌ All video.video_start_time are NULL
   └─> ❌ Cannot assign video_id → detection.video_id = NULL
   └─> ❌ Frame numbers calculated from sequence start, not video start

3. Frontend transitions to Video 2
   └─> ❌ No video-ended event for Video 1
   └─> ❌ No video-started event for Video 2
   └─> ❌ Frame numbers continue from 121+

4. More detections arrive
   └─> Still cannot assign video_id (all timing NULL)
   └─> Frames continue incrementing: 122, 123, ..., 309
   └─> Timestamps continue from sequence start

5. Results endpoint called
   └─> enhanced_hil_results_endpoints.py builds response
   └─> Queries SequenceVideoResult records
   └─> ❌ Both show actual_detection_count = 0 (no assigned detections)
   └─> ❌ Cannot provide per-video metrics
   └─> Falls back to session-level aggregation
   └─> Frame 120 becomes a "pivot point" artifact
```

---

## Why Frame 120 Bunching Occurs

The "bunching" at Frame 120 is an **artifact** of the missing video lifecycle events:

1. **Video 1** ends at Frame 120 (5.04s ÷ 24fps = 120 frames)
2. **Video 2** should start at Frame 0, but the system doesn't know Video 1 ended
3. Frontend continues playing, but backend has no timing reference
4. Some detections land exactly at the transition point
5. Without proper video assignment, they all map to "Frame 120" relative to a single start time

This is NOT a timing calculation bug. It's a **data synchronization issue** between frontend and backend.

---

## Code Analysis

### Video Sequence Orchestrator (Correct Implementation)

File: `/backend/services/video_sequence_orchestrator.py`

```python
def process_detection_event(
    self,
    sequence_id: str,
    labjack_signal: Dict[str, Any],
    sequence_timestamp: float,
    db: Session
) -> Optional[str]:
    """Process a LabjJack detection event and correlate to correct video."""

    # Determine which video was playing at detection time
    video_id = self._determine_video_for_detection(sequence, sequence_timestamp)

    if video_id is None:
        logger.warning(f"Could not determine video for detection at {sequence_timestamp:.6f}")
        return None  # ❌ Returns None when video timing is missing
```

```python
def _determine_video_for_detection(
    self,
    sequence: VideoTestSequence,
    detection_timestamp: float
) -> Optional[str]:
    """Determine which video was playing at detection time"""

    for video_id in sequence.video_ids:
        metadata = sequence.video_metadata[video_id]

        # Skip videos that haven't started yet
        if metadata.video_start_time is None:  # ❌ This is always True
            continue

        # Check if detection falls within video time range
        if metadata.video_start_time <= detection_timestamp <= video_end:
            return video_id

    return None  # ❌ Always returns None when all start times are NULL
```

**Analysis**: The orchestrator logic is **correct**. It cannot assign video_id when `video_start_time` is NULL.

### Video Sequences Router (Missing Event Handling)

File: `/backend/routers/video_sequences.py`

```python
@router.post("/{sequence_id}/video-started", response_model=VideoEventResponse)
async def video_started(sequence_id: str, data: VideoStartedRequest, db: Session = Depends(get_db)):
    """Track when a video in a sequence starts playing."""

    # Find the SequenceVideoResult for this video
    video_result = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.video_sequence_id == sequence_id,
        SequenceVideoResult.video_id == data.videoId
    ).first()

    # Update video start time with nanosecond precision
    video_result.video_start_time = data.timestamp  # ❌ Never called for this session
    video_result.video_status = "playing"
```

**Analysis**: The endpoint exists and is correctly implemented, but **it was never called** during the test session.

---

## Expected vs Actual Behavior

### Expected (With Lifecycle Events)

```
1. Frontend starts Video 1
   └─> POST /api/video-sequences/{id}/video-started
   └─> video_id: 10c2b16c..., timestamp: 1762352910.606

2. Detections arrive (Frames 0-120)
   └─> Assigned to video_id: 10c2b16c...
   └─> video_relative_timestamp: 0.0s - 5.04s
   └─> video_frame_number: 0 - 120

3. Frontend ends Video 1
   └─> POST /api/video-sequences/{id}/video-ended
   └─> video_id: 10c2b16c..., timestamp: 1762352915.648

4. Frontend starts Video 2
   └─> POST /api/video-sequences/{id}/video-started
   └─> video_id: 550e3cf8..., timestamp: 1762352915.648

5. Detections arrive (Frames 0-120)
   └─> Assigned to video_id: 550e3cf8...
   └─> video_relative_timestamp: 0.0s - 5.04s (reset)
   └─> video_frame_number: 0 - 120 (reset)

6. Results endpoint returns:
   └─> Video 1: 80 detections, Frames 0-120
   └─> Video 2: 81 detections, Frames 0-120
```

### Actual (Without Lifecycle Events)

```
1. Frontend starts Video 1
   └─> ❌ No API call

2. Detections arrive (should be Frames 0-120 for Video 1)
   └─> video_id: NULL (cannot assign)
   └─> video_relative_timestamp: 0.198s - 5.xxx s (relative to session start)
   └─> video_frame_number: 4 - 1xx (no video context)

3. Frontend ends Video 1
   └─> ❌ No API call

4. Frontend starts Video 2
   └─> ❌ No API call

5. Detections continue (should be Frames 0-120 for Video 2)
   └─> video_id: NULL (still cannot assign)
   └─> video_relative_timestamp: 5.xxx s - 12.890s (still relative to session start)
   └─> video_frame_number: 1xx - 309 (continues counting)

6. Results endpoint returns:
   └─> Video 1: 0 detections (no assignments)
   └─> Video 2: 0 detections (no assignments)
   └─> Session-level fallback: 161 detections, Frames 4-309
   └─> Frame 120 appears as "bunching" artifact
```

---

## Frontend Integration Point

File: `/frontend/src/components/SequentialVideoPlayer.tsx` (or similar)

Expected calls:

```typescript
// When video starts playing
const handleVideoStart = async (videoId: string) => {
  await fetch(`/api/video-sequences/${sequenceId}/video-started`, {
    method: 'POST',
    body: JSON.stringify({
      videoId,
      timestamp: performance.now() / 1000,
      sequenceElapsedTime: getSequenceElapsedTime()
    })
  });
};

// When video ends
const handleVideoEnd = async (videoId: string) => {
  await fetch(`/api/video-sequences/${sequenceId}/video-ended`, {
    method: 'POST',
    body: JSON.stringify({
      videoId,
      timestamp: performance.now() / 1000,
      actualDuration: videoRef.current.currentTime
    })
  });
};
```

**Finding**: These calls are either:
1. Not implemented in the frontend component
2. Implemented but failing silently
3. Implemented but using incorrect sequence_id/video_id

---

## Implications for Timing Calculations

### Current Hypothesis (INCORRECT)

> "Frame 120 bunching is caused by timestamp calculation errors in `timestamp_conversion_utils.py`"

### Actual Root Cause (CORRECT)

> "Frame 120 bunching is an artifact of missing video lifecycle events, which prevents proper video assignment and frame number reset."

### Why This Matters

All the timing calculation fixes applied to `timing_synchronization_calculator.py`, `timestamp_conversion_utils.py`, and related services are **operating on incomplete data**:

- They receive detections with `video_id: NULL`
- They have no video timing reference (`video_start_time: NULL`)
- They cannot calculate video-relative timestamps correctly
- They cannot reset frame numbers between videos

**The timing calculations themselves are likely correct**, but they're processing data that should have been split across two videos.

---

## Recommended Fixes

### Priority 1: Frontend Integration (CRITICAL)

**File**: `/frontend/src/components/SequentialVideoPlayer.tsx`

1. **Add video lifecycle event handlers**:
   ```typescript
   const handlePlay = () => {
     notifyVideoStarted(currentVideo.id);
   };

   const handleEnded = () => {
     notifyVideoEnded(currentVideo.id);
     playNextVideo();
   };
   ```

2. **Implement API calls**:
   ```typescript
   const notifyVideoStarted = async (videoId: string) => {
     try {
       const response = await fetch(
         `/api/video-sequences/${sequenceId}/video-started`,
         {
           method: 'POST',
           headers: { 'Content-Type': 'application/json' },
           body: JSON.stringify({
             videoId,
             timestamp: Date.now() / 1000,
             startedAt: performance.now() / 1000,
             sequenceElapsedTime: getSequenceElapsedTime()
           })
         }
       );

       if (!response.ok) {
         console.error('Failed to notify video start:', await response.text());
       }
     } catch (error) {
       console.error('Error notifying video start:', error);
     }
   };
   ```

3. **Add error handling and retry logic** for failed API calls

### Priority 2: Backend Resilience (HIGH)

**File**: `/backend/services/detection_video_reassignment.py`

The reassignment service already exists and can fix orphaned detections **after the fact**, but it needs video timing data:

```python
async def reassign_null_video_ids(
    session_id: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Reassign video_id to detections that were stored with NULL."""

    # Build video timing map from SequenceVideoResult
    video_timing_map = self._build_video_timing_map(session, video_results, db)

    if not video_timing_map:
        # ❌ Cannot reassign without timing data
        return {"error": "Missing video timing data"}
```

**Enhancement**: Add fallback timing estimation when lifecycle events are missing:

```python
def _estimate_video_timing_from_metadata(
    self,
    video_results: List[SequenceVideoResult],
    session: TestSession,
    db: Session
) -> Dict[str, Dict[str, Any]]:
    """
    Estimate video timing when lifecycle events are missing.

    Uses:
    - Session start time as reference
    - Video duration metadata for boundaries
    - Sequential ordering for cumulative offsets
    """
    estimated_timing = {}
    cumulative_offset = 0.0

    session_start_time = session.started_at.timestamp()

    for vr in sorted(video_results, key=lambda x: x.sequence_order):
        video = db.query(Video).filter(Video.id == vr.video_id).first()
        if not video or not video.duration:
            continue

        estimated_start = session_start_time + cumulative_offset
        estimated_end = estimated_start + video.duration

        estimated_timing[vr.video_id] = {
            "start_time": estimated_start,
            "end_time": estimated_end,
            "duration_s": video.duration,
            "estimated": True,  # Flag for logging
            "confidence": "low"
        }

        cumulative_offset += video.duration

    return estimated_timing
```

### Priority 3: Validation & Testing (MEDIUM)

**File**: `/backend/tests/test_multi_video_lifecycle_events.py`

Create integration test:

```python
def test_multi_video_sequence_with_lifecycle_events(client, db):
    """Test that video lifecycle events enable proper detection assignment."""

    # 1. Create 2-video sequence
    sequence_id = create_test_sequence(db, video_count=2)

    # 2. Start Video 1
    response = client.post(
        f"/api/video-sequences/{sequence_id}/video-started",
        json={"videoId": video1_id, "timestamp": time.time()}
    )
    assert response.status_code == 200

    # 3. Simulate detections for Video 1
    for _ in range(80):
        create_detection_event(db, session_id, video_id=None)  # Initially NULL

    # 4. End Video 1, Start Video 2
    client.post(f"/api/video-sequences/{sequence_id}/video-ended", ...)
    client.post(f"/api/video-sequences/{sequence_id}/video-started", ...)

    # 5. Simulate detections for Video 2
    for _ in range(81):
        create_detection_event(db, session_id, video_id=None)

    # 6. Verify assignments
    results = get_sequence_results(db, sequence_id)

    assert results["per_video_results"][0]["actual_detection_count"] == 80
    assert results["per_video_results"][1]["actual_detection_count"] == 81
    assert all(d.video_id is not None for d in get_all_detections(db, session_id))
```

### Priority 4: Monitoring & Alerting (LOW)

Add health check endpoint:

```python
@router.get("/api/video-sequences/{sequence_id}/health")
async def check_sequence_health(sequence_id: str, db: Session = Depends(get_db)):
    """Check if video sequence has proper timing data."""

    video_results = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.video_sequence_id == sequence_id
    ).all()

    issues = []
    for vr in video_results:
        if vr.video_status == "playing" and vr.video_start_time is None:
            issues.append(f"Video {vr.video_id} playing but no start_time recorded")

        if vr.video_status == "completed" and vr.video_end_time is None:
            issues.append(f"Video {vr.video_id} completed but no end_time recorded")

    return {
        "sequence_id": sequence_id,
        "health": "healthy" if not issues else "degraded",
        "issues": issues
    }
```

---

## Verification Steps

To confirm this diagnosis:

1. **Check frontend network logs** for session `6d05fcd1`:
   ```bash
   # Filter browser DevTools Network tab for:
   POST /api/video-sequences/*/video-started
   POST /api/video-sequences/*/video-ended
   ```
   Expected: No requests found (confirms they weren't sent)

2. **Check backend access logs**:
   ```bash
   grep "video-started" /backend/logs/access.log | grep "6d05fcd1"
   grep "video-ended" /backend/logs/access.log | grep "6d05fcd1"
   ```
   Expected: No matches (confirms backend never received them)

3. **Test with manual API calls**:
   ```bash
   # Manually trigger lifecycle events
   curl -X POST http://localhost:8000/api/video-sequences/3aea0970.../video-started \
     -H "Content-Type: application/json" \
     -d '{"videoId": "10c2b16c...", "timestamp": 1762352910.606}'

   # Run reassignment service
   curl -X POST http://localhost:8000/api/detection-reassignment/6d05fcd1.../run

   # Check if detections now have video_id
   SELECT COUNT(*), video_id FROM detection_events
   WHERE test_session_id = '6d05fcd1...' GROUP BY video_id;
   ```
   Expected: Detections should now be split between two video_ids

---

## Conclusion

**This is NOT a timestamp calculation bug.**

The Frame 120 bunching and missing Video 2 data are symptoms of a **missing integration** between the frontend video player and the backend video sequence orchestrator.

The backend is correctly implemented to handle multi-video sequences, but it depends on lifecycle events (`video-started`, `video-ended`) that the frontend is not sending.

**Fix**: Implement lifecycle event handlers in `SequentialVideoPlayer.tsx` to call the backend API endpoints when videos start and end. This will enable proper:
- Video assignment (`detection.video_id`)
- Frame number reset between videos
- Video-relative timestamp calculation
- Per-video metrics and evaluation

**Impact**: All timing calculation fixes applied so far are likely correct, but they're operating on incomplete/malformed data due to missing video context. Once lifecycle events are properly sent, the existing timing logic should work correctly.
