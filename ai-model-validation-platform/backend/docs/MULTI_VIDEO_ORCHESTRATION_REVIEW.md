# Backend Multi-Video Session and Orchestration Setup Review

**Analysis Date:** 2025-10-30
**Reviewed By:** Backend API Developer Agent
**Scope:** Multi-video session creation, video start notifications, orchestration service integration

---

## Executive Summary

### Overall Assessment: ⚠️ **PARTIALLY IMPLEMENTED WITH CRITICAL GAPS**

The multi-video session architecture has database schema and data structures in place, but **the orchestration service is not integrated** into the main HIL test workflow. The system creates records but does not use the VideoSequenceOrchestrator service for coordination.

### Critical Findings:
1. ✅ **Database schema is complete** - All tables and fields exist
2. ✅ **Session creation works correctly** - Detects multi-video and creates records
3. ✅ **Video start notification stores timing** - SequenceVideoResult updated
4. ❌ **Orchestrator service NOT integrated** - Service exists but unused in HIL workflow
5. ⚠️ **video_play_offset_ms calculation is INCORRECT** - Uses cumulative actual_duration_ms instead of dynamic timing

---

## 1. Session Creation Analysis (`start_hil_test_session`)

### ✅ Correctly Implemented

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/api/hil_test_complete.py` (Lines 263-327)

```python
# MULTI-VIDEO SUPPORT: Check if project has multiple videos
project_videos = get_project_videos(db, session_data.project_id)
has_video_sequence = len(project_videos) > 1  # ✅ CORRECT: Detects multi-video

session_create = TestSessionCreate(
    project_id=session_data.project_id,
    max_latency_ms=session_data.max_latency_ms,
    test_start_time=test_start_time,
    labjack_connected=True,
    status="running",
    has_video_sequence=has_video_sequence  # ✅ CORRECT: Flag set
)

test_session = create_test_session(db, session_create)

# MULTI-VIDEO SUPPORT: Create VideoTestSequence and SequenceVideoResult records
if has_video_sequence:
    from models import VideoTestSequence, SequenceVideoResult
    from uuid import uuid4

    # Create VideoTestSequence
    video_sequence = VideoTestSequence(
        id=str(uuid4()),
        test_session_id=str(test_session.id),
        sequence_order=list(range(len(project_videos))),  # ✅ CORRECT: [0, 1, 2, ...]
        total_videos=len(project_videos),
        status="pending"
    )
    db.add(video_sequence)
    db.flush()

    # Create SequenceVideoResult for each video
    for idx, video in enumerate(project_videos):
        sequence_video_result = SequenceVideoResult(
            id=str(uuid4()),
            video_id=video.id,
            video_sequence_id=video_sequence.id,
            sequence_order=idx,  # ✅ CORRECT: 0-indexed position
            video_status="pending"  # ✅ CORRECT: Initial state
        )
        db.add(sequence_video_result)

    db.commit()
    logger.info(f"Created multi-video sequence for session {test_session.id} with {len(project_videos)} videos")
```

**Analysis:**
- ✅ Correctly detects multi-video projects (`len(project_videos) > 1`)
- ✅ Sets `has_video_sequence` flag on TestSession
- ✅ Creates VideoTestSequence parent record
- ✅ Creates SequenceVideoResult for each video with correct sequence_order
- ✅ All records initialized with correct status ("pending")
- ✅ Database commits happen after flush

**Potential Issues:**
- ⚠️ No validation that all videos exist and are accessible
- ⚠️ No check for duplicate video IDs in sequence
- ⚠️ VideoTestSequence.sequence_order stores simple list [0,1,2] instead of detailed metadata

---

## 2. Video Start Notification Analysis (`start_video_playback`)

### ⚠️ PARTIALLY CORRECT WITH TIMING BUG

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/api/hil_test_complete.py` (Lines 460-598)

```python
async def start_video_playback(
    session_id: int,
    video_data: dict,
    db: Session = Depends(get_db)
):
    # ... T1 capture and validation ...

    # MULTI-VIDEO SEQUENCE SUPPORT: Store per-video timing in SequenceVideoResult
    from models import TestSession, VideoTestSequence, SequenceVideoResult
    test_session = db.query(TestSession).filter(TestSession.id == session_id).first()

    if test_session and test_session.has_video_sequence:  # ✅ CORRECT: Checks flag
        # Find the active video sequence for this session
        video_sequence = db.query(VideoTestSequence).filter(
            VideoTestSequence.test_session_id == str(session_id)  # ✅ CORRECT: Query
        ).first()

        if video_sequence:
            # Find or create SequenceVideoResult for this video
            sequence_video_result = db.query(SequenceVideoResult).filter(
                SequenceVideoResult.video_sequence_id == video_sequence.id,
                SequenceVideoResult.video_id == video_id  # ✅ CORRECT: Matches video
            ).first()

            if sequence_video_result:
                # ❌ CRITICAL BUG: Calculate cumulative offset from previous videos
                previous_videos = db.query(SequenceVideoResult).filter(
                    SequenceVideoResult.video_sequence_id == video_sequence.id,
                    SequenceVideoResult.sequence_order < sequence_video_result.sequence_order
                ).all()

                cumulative_offset_ms = sum(
                    float(v.actual_duration_ms or 0) for v in previous_videos  # ❌ BUG!
                )

                # Update SequenceVideoResult with video start timing
                sequence_video_result.video_start_time = t1_capture.video_start_timestamp  # ✅ CORRECT
                sequence_video_result.video_start_time_ns = str(int(t1_capture.video_start_timestamp * 1_000_000_000))  # ✅ CORRECT
                sequence_video_result.video_play_offset_ms = cumulative_offset_ms  # ❌ WRONG VALUE
                sequence_video_result.video_status = "playing"  # ✅ CORRECT

                db.commit()
```

**Analysis:**

✅ **Correctly Implemented:**
- Receives video_id from video_data payload
- Checks `test_session.has_video_sequence` flag
- Queries VideoTestSequence by test_session_id
- Queries SequenceVideoResult by video_id
- Stores video_start_time from T1 capture
- Updates video_status to "playing"
- Commits to database

❌ **CRITICAL BUG: video_play_offset_ms Calculation**

```python
# Current implementation (WRONG):
cumulative_offset_ms = sum(
    float(v.actual_duration_ms or 0) for v in previous_videos
)
# Problem: actual_duration_ms is NULL until video completes!
# Result: Always calculates 0ms offset for all videos
```

**Correct Implementation Should Be:**
```python
# CORRECT: Calculate offset from sequence start time
if video_sequence.sequence_start_time is None:
    video_sequence.sequence_start_time = t1_capture.video_start_timestamp
    video_play_offset_ms = 0.0
else:
    video_play_offset_ms = (t1_capture.video_start_timestamp - video_sequence.sequence_start_time) * 1000.0

sequence_video_result.video_play_offset_ms = video_play_offset_ms
```

**Missing Data:**
- ⚠️ No sequence_order, duration, fps passed to frontend in payload
- ⚠️ No actual_duration_ms or video_end_time populated (only on completion)

---

## 3. Video Sequence Orchestrator Integration

### ❌ CRITICAL: SERVICE NOT INTEGRATED

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`

**Status:** ❌ **Service exists but is NEVER CALLED by hil_test_complete.py**

**Evidence:**
```bash
$ grep -r "video_sequence_orchestrator\|VideoSequenceOrchestrator" backend/api/hil_test_complete.py
# NO RESULTS - Service not imported or used!
```

**What the Orchestrator SHOULD Do:**

```python
# services/video_sequence_orchestrator.py (Lines 175-260)
def start_sequence(
    self,
    project_id: str,
    video_ids: List[str],
    max_latency_ms: float,
    db: Session,
    session_id: Optional[str] = None
) -> str:
    """Initialize and start a new video test sequence."""
    # - Validates all videos exist
    # - Loads video metadata (duration, fps, frame_count)
    # - Creates sequence tracking structures
    # - Returns sequence_id

def notify_video_started(
    self,
    sequence_id: str,
    video_id: str,
    actual_start_timestamp: float,
    db: Session
) -> bool:
    """Record when a video actually starts playing."""
    # - Updates video metadata with start time
    # - Calculates video_play_offset_ms CORRECTLY (from sequence start)
    # - Updates VideoTestSequence.sequence_start_time on first video
    # - Sets video_status to "playing"
    # - Tracks current_video_index

def process_detection_event(
    self,
    sequence_id: str,
    labjack_signal: Dict[str, Any],
    sequence_timestamp: float,
    db: Session
) -> Optional[str]:
    """Process LabjJack detection and correlate to correct video."""
    # - Determines which video was playing at detection time
    # - Calculates video-relative timestamp
    # - Creates DetectionEvent with correct video_id
    # - Updates detection counts per video
```

**Why It's Not Being Used:**

1. **No Import Statement** - hil_test_complete.py doesn't import the orchestrator
2. **Manual DB Queries** - Direct SQLAlchemy queries instead of service calls
3. **No Coordination** - Each function operates independently
4. **Missing Logic** - Detection correlation logic not implemented

---

## 4. Detection Event Tagging

### ⚠️ VIDEO_ID BACKFILL EXISTS BUT SEQUENCE CORRELATION MISSING

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`

**Current Implementation:**
```python
# Detection events get video_id from session
if not video_id and test_session:
    video_id = test_session.video_id  # ⚠️ Only works for single-video sessions
```

**Missing for Multi-Video:**
- ❌ No logic to determine which video was playing at detection time
- ❌ No sequence timestamp correlation
- ❌ No video-relative timestamp calculation
- ❌ SequenceVideoResult.sequence_video_result_id not populated

**What's Needed:**
```python
# For multi-video sequences
if test_session.has_video_sequence:
    # Determine active video at detection time
    active_video_id = orchestrator.determine_video_for_detection(
        sequence_id=test_session.sequence_id,
        detection_timestamp=labjack_timestamp
    )

    # Get SequenceVideoResult for proper correlation
    sequence_video_result = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.video_sequence_id == sequence_id,
        SequenceVideoResult.video_id == active_video_id
    ).first()

    detection_event.video_id = active_video_id
    detection_event.sequence_video_result_id = sequence_video_result.id
    detection_event.video_relative_timestamp = (
        detection_timestamp - sequence_video_result.video_start_time
    )
```

---

## 5. Critical Integration Points

### Database Commits
✅ **Status:** All commits happen correctly
- Session creation commits after adding VideoTestSequence and SequenceVideoResult
- Video start commits after updating SequenceVideoResult timing
- No race conditions detected in commit ordering

### Error Handling
⚠️ **Status:** Basic error handling present but incomplete
```python
# Current error handling
if not sequence_video_result:
    # Silently fails - should raise error or log warning
    pass

if not video_sequence:
    # Silently fails - should raise error
    pass
```

**Missing Error Handling:**
- No validation that video_id exists in sequence
- No check for duplicate video start notifications
- No handling of out-of-order video starts

### Race Conditions
⚠️ **Potential Race Condition Identified:**

**Scenario:** Frontend calls `start_video_playback` for Video 2 before Video 1 completes

```python
# Current implementation has NO protection:
if sequence_video_result:
    # No check if previous video completed
    # No check if sequence_order is correct
    sequence_video_result.video_status = "playing"  # ⚠️ Allows out-of-order
```

**Mitigation Needed:**
```python
# Check if previous video completed
previous_incomplete = db.query(SequenceVideoResult).filter(
    SequenceVideoResult.video_sequence_id == video_sequence.id,
    SequenceVideoResult.sequence_order < sequence_video_result.sequence_order,
    SequenceVideoResult.video_status != "completed"
).first()

if previous_incomplete:
    raise HTTPException(
        status_code=400,
        detail=f"Cannot start video {video_id}: previous video not completed"
    )
```

---

## 6. Code Quality and Maintainability

### Imports and Dependencies
✅ **Status:** All necessary imports present
```python
from models import VideoTestSequence, SequenceVideoResult  # ✅ Imported when needed
from uuid import uuid4  # ✅ Used for ID generation
```

### Code Organization
⚠️ **Status:** Logic scattered across multiple locations

**Current Structure:**
- `hil_test_complete.py` - Manual DB queries for sequence operations
- `video_sequence_orchestrator.py` - Complete service implementation UNUSED
- `labjack_detection_service.py` - Detection storage without sequence correlation

**Recommended Structure:**
```
hil_test_complete.py
  └─> video_sequence_orchestrator.start_sequence()
  └─> video_sequence_orchestrator.notify_video_started()
  └─> video_sequence_orchestrator.process_detection_event()
```

### Documentation
⚠️ **Status:** Code comments exist but incomplete

**Gaps:**
- No docstring for multi-video session creation logic
- No explanation of video_play_offset_ms calculation
- No documentation of expected video_data payload structure

---

## 7. Summary of Findings

### ✅ Correctly Implemented Features

1. **Multi-video detection** - Correctly identifies projects with multiple videos
2. **Database schema** - All tables (VideoTestSequence, SequenceVideoResult) exist
3. **Record creation** - VideoTestSequence and SequenceVideoResult records created
4. **Flag management** - has_video_sequence flag set and checked correctly
5. **Basic timing storage** - video_start_time captured from T1 timestamp
6. **Status tracking** - video_status transitions (pending → playing)

### ⚠️ Potential Issues and Edge Cases

1. **video_play_offset_ms calculation** - Uses cumulative actual_duration_ms (always 0)
2. **No video existence validation** - Doesn't verify videos are accessible before session start
3. **Missing payload fields** - Frontend may need sequence_order, duration, fps not sent
4. **Silent failure modes** - Missing records cause silent failures instead of errors
5. **Race condition risk** - Out-of-order video starts not prevented

### ❌ Critical Bugs and Missing Functionality

1. **VideoSequenceOrchestrator NOT INTEGRATED**
   - Service exists with full implementation
   - Never imported or called by hil_test_complete.py
   - Manual DB queries duplicate orchestrator logic

2. **Detection correlation MISSING**
   - No logic to determine which video was playing at detection time
   - DetectionEvent.sequence_video_result_id not populated
   - Video-relative timestamps not calculated

3. **video_play_offset_ms ALWAYS 0**
   - Current: `sum(v.actual_duration_ms or 0)` where actual_duration_ms is NULL
   - Should: `(video_start_time - sequence_start_time) * 1000`

4. **No video end notification handling**
   - Missing `notify_video_ended` implementation
   - actual_duration_ms never populated
   - No transition detection between videos

---

## 8. Detailed Code Snippets with Line Numbers

### Session Creation (CORRECT)
**File:** `api/hil_test_complete.py:284-327`
```python
284:        # MULTI-VIDEO SUPPORT: Check if project has multiple videos
285:        project_videos = get_project_videos(db, session_data.project_id)
286:        has_video_sequence = len(project_videos) > 1
287:
288:        session_create = TestSessionCreate(
289:            project_id=session_data.project_id,
290:            max_latency_ms=session_data.max_latency_ms,
291:            test_start_time=test_start_time,
292:            labjack_connected=True,
293:            status="running",
294:            has_video_sequence=has_video_sequence
295:        )
296:
297:        test_session = create_test_session(db, session_create)
298:
299:        # MULTI-VIDEO SUPPORT: Create VideoTestSequence and SequenceVideoResult records
300:        if has_video_sequence:
301:            from models import VideoTestSequence, SequenceVideoResult
302:            from uuid import uuid4
303:
304:            # Create VideoTestSequence
305:            video_sequence = VideoTestSequence(
306:                id=str(uuid4()),
307:                test_session_id=str(test_session.id),
308:                sequence_order=list(range(len(project_videos))),
309:                total_videos=len(project_videos),
310:                status="pending"
311:            )
312:            db.add(video_sequence)
313:            db.flush()
314:
315:            # Create SequenceVideoResult for each video
316:            for idx, video in enumerate(project_videos):
317:                sequence_video_result = SequenceVideoResult(
318:                    id=str(uuid4()),
319:                    video_id=video.id,
320:                    video_sequence_id=video_sequence.id,
321:                    sequence_order=idx,
322:                    video_status="pending"
323:                )
324:                db.add(sequence_video_result)
325:
326:            db.commit()
327:            logger.info(f"Created multi-video sequence for session {test_session.id} with {len(project_videos)} videos")
```

### Video Start Notification (BUG IN OFFSET CALCULATION)
**File:** `api/hil_test_complete.py:512-551`
```python
512:        # MULTI-VIDEO SEQUENCE SUPPORT: Store per-video timing in SequenceVideoResult
513:        from models import TestSession, VideoTestSequence, SequenceVideoResult
514:        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
515:
516:        if test_session and test_session.has_video_sequence:
517:            # Find the active video sequence for this session
518:            video_sequence = db.query(VideoTestSequence).filter(
519:                VideoTestSequence.test_session_id == str(session_id)
520:            ).first()
521:
522:            if video_sequence:
523:                # Find or create SequenceVideoResult for this video
524:                sequence_video_result = db.query(SequenceVideoResult).filter(
525:                    SequenceVideoResult.video_sequence_id == video_sequence.id,
526:                    SequenceVideoResult.video_id == video_id
527:                ).first()
528:
529:                if sequence_video_result:
530:                    # ❌ BUG: Calculate cumulative offset from previous videos
531:                    previous_videos = db.query(SequenceVideoResult).filter(
532:                        SequenceVideoResult.video_sequence_id == video_sequence.id,
533:                        SequenceVideoResult.sequence_order < sequence_video_result.sequence_order
534:                    ).all()
535:
536:                    cumulative_offset_ms = sum(
537:                        float(v.actual_duration_ms or 0) for v in previous_videos
538:                    )  # ❌ actual_duration_ms is always NULL here!
539:
540:                    # Update SequenceVideoResult with video start timing
541:                    sequence_video_result.video_start_time = t1_capture.video_start_timestamp
542:                    sequence_video_result.video_start_time_ns = str(int(t1_capture.video_start_timestamp * 1_000_000_000))
543:                    sequence_video_result.video_play_offset_ms = cumulative_offset_ms  # ❌ Always 0!
544:                    sequence_video_result.video_status = "playing"
545:
546:                    db.commit()
547:
548:                    logger.info(f"Stored per-video timing for video {video_id}: "
549:                               f"start_time={t1_capture.video_start_timestamp}, "
550:                               f"offset_ms={cumulative_offset_ms}")
```

### VideoSequenceOrchestrator (UNUSED SERVICE)
**File:** `services/video_sequence_orchestrator.py:261-332`
```python
261:    def notify_video_started(
262:        self,
263:        sequence_id: str,
264:        video_id: str,
265:        actual_start_timestamp: float,
266:        db: Session
267:    ) -> bool:
268:        """Record when a video actually starts playing."""
269:        try:
270:            sequence = self._get_sequence(sequence_id)
271:
272:            # Validate video belongs to sequence
273:            if video_id not in sequence.video_ids:
274:                raise VideoSequenceOrchestratorError(f"Video {video_id} not in sequence {sequence_id}")
275:
276:            # Initialize sequence start time on first video
277:            if sequence.sequence_start_time is None:
278:                sequence.sequence_start_time = actual_start_timestamp
279:                sequence.status = SequenceStatus.RUNNING
280:                logger.info(f"Sequence {sequence_id} started at {actual_start_timestamp:.6f}")
281:
282:            # ✅ CORRECT: Calculate video play offset from sequence start
283:            video_play_offset_ms = (actual_start_timestamp - sequence.sequence_start_time) * 1000.0
284:
285:            # Update video metadata
286:            metadata = sequence.video_metadata[video_id]
287:            metadata.video_start_time = actual_start_timestamp
288:            metadata.video_play_offset_ms = video_play_offset_ms
289:
290:            # Update video result
291:            result = sequence.video_results[video_id]
292:            result.video_start_time = actual_start_timestamp
293:            result.video_play_offset_ms = video_play_offset_ms
294:            result.status = VideoStatus.PLAYING
295:            result.expected_detections = metadata.ground_truth_count
296:
297:            # Update current video index
298:            sequence.current_video_index = sequence.video_ids.index(video_id)
299:
300:            # Start video timing in timing service
301:            self._timing_service.start_video_timing(
302:                session_id=sequence.session_id,
303:                video_id=video_id,
304:                db=db,
305:                video_metadata={
306:                    'fps': metadata.fps,
307:                    'duration': metadata.duration,
308:                    'frame_count': metadata.frame_count
309:                }
310:            )
311:
312:            logger.info(f"Video started: {video_id}")
313:            logger.info(f"  Start time: {actual_start_timestamp:.6f}")
314:            logger.info(f"  Play offset: {video_play_offset_ms:.3f}ms")
315:            logger.info(f"  Expected detections: {metadata.ground_truth_count}")
316:
317:            return True
318:
319:        except Exception as e:
320:            logger.error(f"Failed to notify video started: {e}")
321:            return False
```

---

## 9. Recommendations

### CRITICAL - Fix Immediately

1. **Integrate VideoSequenceOrchestrator into HIL workflow**
   ```python
   # In hil_test_complete.py
   from services.video_sequence_orchestrator import get_video_sequence_orchestrator

   orchestrator = get_video_sequence_orchestrator()

   # Replace manual session creation with:
   sequence_id = orchestrator.start_sequence(
       project_id=session_data.project_id,
       video_ids=[v.id for v in project_videos],
       max_latency_ms=session_data.max_latency_ms,
       db=db,
       session_id=str(test_session.id)
   )

   # Replace manual video start notification with:
   orchestrator.notify_video_started(
       sequence_id=sequence_id,
       video_id=video_id,
       actual_start_timestamp=t1_capture.video_start_timestamp,
       db=db
   )
   ```

2. **Fix video_play_offset_ms calculation**
   ```python
   # Replace lines 530-543 with:
   if video_sequence.sequence_start_time is None:
       video_sequence.sequence_start_time = t1_capture.video_start_timestamp
       video_play_offset_ms = 0.0
   else:
       video_play_offset_ms = (
           t1_capture.video_start_timestamp - video_sequence.sequence_start_time
       ) * 1000.0

   sequence_video_result.video_play_offset_ms = video_play_offset_ms
   ```

3. **Implement detection correlation logic**
   ```python
   # In labjack_detection_service.py
   if test_session.has_video_sequence:
       detection_event.video_id = orchestrator.determine_video_for_detection(
           sequence_id=test_session.sequence_id,
           detection_timestamp=labjack_timestamp
       )
       detection_event.video_relative_timestamp = (
           labjack_timestamp - sequence_video_result.video_start_time
       )
       detection_event.sequence_video_result_id = sequence_video_result.id
   ```

### HIGH PRIORITY - Implement Soon

4. **Add video end notification handler**
   ```python
   @router.post("/session/{session_id}/video/end")
   async def end_video_playback(session_id: int, video_data: dict, db: Session):
       orchestrator.notify_video_ended(
           sequence_id=sequence_id,
           video_id=video_id,
           actual_end_timestamp=time.time(),
           db=db
       )
   ```

5. **Add validation and error handling**
   - Check video existence before session start
   - Prevent out-of-order video starts
   - Raise errors on missing sequence records

6. **Add race condition protection**
   - Lock sequence during video transitions
   - Verify previous video completed before starting next

### MEDIUM PRIORITY - Technical Debt

7. **Consolidate duplicate logic**
   - Remove manual DB queries from hil_test_complete.py
   - Use orchestrator service exclusively
   - Delete redundant code

8. **Improve logging and monitoring**
   - Add structured logging for sequence events
   - Track timing metrics per video
   - Monitor sequence completion rates

9. **Add comprehensive documentation**
   - Document multi-video workflow
   - Explain video_play_offset_ms calculation
   - Provide integration examples

---

## 10. Testing Recommendations

### Integration Tests Needed

1. **Multi-video session creation**
   - Verify VideoTestSequence created
   - Verify SequenceVideoResult records for each video
   - Check has_video_sequence flag

2. **Video start notification**
   - Test video_play_offset_ms calculation
   - Verify sequence_start_time initialization
   - Check status transitions

3. **Detection correlation**
   - Test video_id assignment
   - Verify video-relative timestamps
   - Check sequence_video_result_id population

4. **Edge cases**
   - Out-of-order video starts
   - Missing sequence records
   - Duplicate video start notifications

### Manual Testing Steps

```bash
# 1. Create multi-video project
POST /api/projects { name: "Multi-Video Test", videos: [vid1, vid2, vid3] }

# 2. Start HIL session
POST /api/hil-test/session/start { project_id: "...", max_latency_ms: 100 }

# 3. Verify database records
SELECT * FROM video_test_sequences WHERE test_session_id = '...';
SELECT * FROM sequence_video_results WHERE video_sequence_id = '...';

# 4. Start first video
POST /api/hil-test/session/{id}/video/start { video_id: "vid1", duration: 30.0, fps: 30 }

# 5. Check video_play_offset_ms (should be 0.0)
SELECT video_play_offset_ms FROM sequence_video_results WHERE video_id = 'vid1';

# 6. Start second video after first completes
POST /api/hil-test/session/{id}/video/start { video_id: "vid2", duration: 25.0, fps: 30 }

# 7. Check video_play_offset_ms (should be > 0.0 based on actual timing)
SELECT video_play_offset_ms FROM sequence_video_results WHERE video_id = 'vid2';
```

---

## 11. Conclusion

The backend multi-video session infrastructure is **partially implemented** with critical gaps:

**✅ Working:**
- Database schema
- Record creation
- Basic timing storage

**❌ Not Working:**
- VideoSequenceOrchestrator integration
- video_play_offset_ms calculation
- Detection correlation
- Video end notifications

**Priority Fix:**
Integrate the VideoSequenceOrchestrator service into hil_test_complete.py to enable proper sequence coordination and timing management.

**Estimated Effort:**
- Critical fixes: 4-6 hours
- High priority features: 8-12 hours
- Testing and validation: 4-6 hours
- **Total:** 16-24 hours

---

**Report Generated:** 2025-10-30
**Next Review:** After orchestrator integration is complete
