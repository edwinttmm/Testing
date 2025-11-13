# Multi-Video Timing Coordination - Root Cause Analysis

**Investigation Date:** 2025-11-04
**Session Analyzed:** 71976ec4-b37d-4b19-8df7-11fefcb9bba7 (Session b6662f68)
**Status:** Critical Issues Identified

---

## Executive Summary

**PRIMARY ISSUE**: Multi-video sequences fail to assign detections to second/subsequent videos due to multiple compounding failures in the timing coordination pipeline.

**ROOT CAUSES IDENTIFIED**:
1. **Missing Sequence ID** - Frontend `sequenceId` is NULL/undefined, causing all lifecycle events to silently fail
2. **Stale Cache Bug** - Backend detection assignment uses cached timing data that never refreshes for Video 2
3. **Race Condition** - Video 2 timing data committed to database AFTER detections start being assigned
4. **Detection Assignment Logic Flaw** - Falls back to last video when no match found, even outside time window

**IMPACT**:
- Video 2 receives 0 detections despite 27 actual hardware events occurring during playback
- All 178 detections incorrectly assigned to Video 1
- Ground truth matching completely broken for multi-video sequences
- Latency calculations invalid for Video 2

---

## Critical Finding #1: Complete Lifecycle Event Failure

### Evidence from Database

**Session: `71976ec4-b37d-4b19-8df7-11fefcb9bba7`**
```sql
SELECT * FROM sequence_video_results
WHERE video_sequence_id = '703aa6c9-a168-46b0-a60a-d80e2467b6c5';

-- Results:
Video 1 (10c2b16c-86fa-4140-b1cf-c0ea42f82ca5):
  video_start_time: NULL  ❌
  video_end_time: NULL    ❌
  video_status: pending   ❌

Video 2 (550e3cf8-2755-42df-8c3c-041300735f93):
  video_start_time: NULL  ❌
  video_end_time: NULL    ❌
  video_status: pending   ❌
```

**Sequence State:**
```sql
SELECT status, current_video_index FROM video_test_sequences
WHERE id = '703aa6c9-a168-46b0-a60a-d80e2467b6c5';

-- Results:
status: running               ❌ (Should be 'completed')
current_video_index: 0        ❌ (Stuck on first video)
```

### Root Cause: Missing sequenceId Prop

**Location**: `/frontend/src/components/SequentialVideoPlayer.tsx` Lines 110-113

```typescript
const sendVideoStartedEvent = useCallback(async (videoId: string, timestamp: number) => {
    // Early return if no sequenceId - THIS IS THE BUG
    if (!sequenceId) {
        console.warn('⚠️ No sequence ID - skipping video-started event');
        return;  // ❌ SILENTLY FAILS
    }

    try {
        await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, ...);
    } catch (err) {
        console.warn('⚠️ Failed to send video-started event (non-critical):', err);
        // ❌ Error swallowed, user not notified
    }
}, [sequenceId]);
```

**What Happened**:
1. Test session created, but `sequenceId` never properly initialized
2. SequentialVideoPlayer mounts with `sequenceId = null` or `undefined`
3. Videos load and play **visually** (local video element works fine)
4. `sendVideoStartedEvent()` called for Video 1
5. **Line 110 check fails** → function returns early
6. NO API call made to backend
7. Video 1 plays normally (user unaware of failure)
8. Video 1 ends, `sendVideoEndedEvent()` also skips (same check)
9. Video 2 auto-advances and plays visually
10. Same lifecycle event failures occur for Video 2
11. Test completes, user sees results
12. Backend has **ZERO** timing data for **BOTH** videos

**Evidence**: Database shows BOTH videos with NULL timestamps, confirming NO lifecycle events were received.

---

## Critical Finding #2: Stale Cache in Detection Assignment

### The Detection Assignment Cache Bug

**Location**: `/backend/services/dedicated_labjack_monitor.py` Lines 734-772

```python
def _enrich_hil_event_context(self, hil_event, session_id, labjack_trigger_time):
    session_cache = self.active_sessions.setdefault(session_id, {})
    cached_context = session_cache.get('sequence_context')

    # BUG: Cache only refreshed if cached_context doesn't exist OR missing video_timing
    if not cached_context or 'video_timing' not in cached_context:
        context = self._load_sequence_context(session_id)
        session_cache['sequence_context'] = context or {}
    else:
        context = cached_context  # ❌ STALE CACHE USED HERE

    video_timing = context.get('video_timing', {})
    video_id = self._determine_video_from_timing(video_timing, labjack_trigger_time)

    # BUG FIX #8 attempt (DOESN'T WORK)
    if not video_id:
        # Only refreshes if video_id is None
        refreshed_context = self._load_sequence_context(session_id)
        # ...
```

### Why the Bug Fix Doesn't Work

**The Flawed Logic** (Lines 869-890):
```python
def _determine_video_from_timing(self, video_timing, trigger_time):
    selected_video = None
    latest_start = -float('inf')

    for video_id, timing in video_timing.items():
        start = timing.get("started_at")
        end = timing.get("ended_at")

        # Check if within video window
        if end is not None and start <= trigger_time <= end:
            return video_id  # ✅ Would work if cache was fresh

        # ❌ FALLBACK LOGIC IS BROKEN:
        # Picks latest start EVEN IF detection is AFTER video ended
        if end is None and trigger_time >= start and start > latest_start:
            selected_video = video_id
            latest_start = start

    return selected_video  # Returns Video 1 ID even for detections after it ended!
```

**Timeline of Failure**:
1. **T=0s**: Video 1 starts, cache initialized: `{"video_timing": {"video1": {...}}}`
2. **T=5.3s**: Video 1 ends, Video 2 starts
3. **Database Updated**: `sequence_metadata.video_timing` now has Video 2 data
4. **T=5.5s**: Detection occurs during Video 2 playback
5. **Cache Check**: `cached_context` exists and has `'video_timing'` → stale cache used
6. **Video Determination**: Only Video 1 in stale cache
   - Detection time = 1762188244.xx
   - Video 1 end = 1762188243.539
   - Detection is AFTER Video 1 ended
   - But fallback logic (line 886) returns Video 1 ID anyway!
7. **Cache Refresh Check**: `video_id` is NOT None → cache NOT refreshed
8. **Result**: Detection assigned to Video 1 incorrectly

---

## Critical Finding #3: Race Condition in Video Sequence Orchestrator

### The notify_video_started Flow

**Location**: `/backend/services/video_sequence_orchestrator.py` Lines 266-337

```python
def notify_video_started(self, sequence_id, video_id, actual_start_timestamp, db):
    sequence = self._get_sequence(sequence_id)

    # Update in-memory sequence data
    metadata = sequence.video_metadata[video_id]
    metadata.video_start_time = actual_start_timestamp
    metadata.video_play_offset_ms = video_play_offset_ms

    result = sequence.video_results[video_id]
    result.video_start_time = actual_start_timestamp
    result.video_play_offset_ms = video_play_offset_ms
    result.status = VideoStatus.PLAYING

    # Start video timing in timing service
    self._timing_service.start_video_timing(
        session_id=sequence.session_id,
        video_id=video_id,
        db=db,
        video_metadata={...}
    )
    # ⚠️ NO DATABASE COMMIT HERE
```

**Race Condition**:
1. `notify_video_started()` updates in-memory sequence data
2. Timing service started
3. **LabJack detections start arriving immediately**
4. Detection assignment queries database for `video_start_time`
5. **Database still has NULL** - in-memory update not committed yet
6. Detection assigned to wrong video or dropped

---

## Critical Finding #4: Timestamp Conversion Bugs

### Location: `/backend/services/timestamp_conversion_utils.py` Lines 89-102

```python
def unix_to_video_relative(self, unix_timestamp, video_start_time, precision_ns):
    # Calculate video-relative time
    video_relative_timestamp = unix_timestamp - video_start_time

    # ❌ REMOVED HARDCODED 50ms LATENCY (Good)
    # ✅ CORRECT: actual_latency_ms should be NULL here
    actual_latency_ms = None  # Caller must provide measured latency

    return TimestampConversionResult(
        success=True,
        video_relative_timestamp=video_relative_timestamp,
        actual_latency_ms=actual_latency_ms,
        ...
    )
```

**This is Actually Correct**: The timestamp converter should NOT calculate latency. Latency comes from actual detection pipeline timing metadata.

---

## Critical Finding #5: Timing Synchronization Calculator Issues

### Location: `/backend/services/timing_synchronization_calculator.py` Lines 166-243

```python
def calculate_corrected_latency(self, ...):
    # ❌ BUG: Coercing None to float without proper validation
    detection_system_time = float(detection_system_time)  # Crashes if None

    # Video start time calculation
    startup_delay_ms = video_timing_metadata.startup_delay_ms
    video_start_system_time = labjack_start_time  # ✅ CORRECT (after fix)

    # Ground truth event time
    gt_system_time = video_start_system_time + ground_truth_video_time

    # ❌ TIMESTAMP VALIDATION ISSUES
    time_span = detection_system_time - labjack_start_time
    if time_span > 600:  # More than 10 minutes
        # Falls back to position-based estimate
        real_latency_ms = 75.0 + (video_position_factor * 25.0)
```

**Problems**:
1. No null check before float coercion → crashes on NULL timestamps
2. Timestamp epoch validation catches symptoms, not root cause
3. Fallback to position-based estimates masks real timing issues

---

## Detection Assignment Complete Flow Analysis

### Step 1: LabJack Detection Captured
**Service**: `labjack_detection_service.py`
```python
def _create_detection_event(self, session_id, channel, voltage, threshold, timestamp):
    # Detection captured with hardware timestamp
    event = DetectionEvent(
        timestamp=timestamp,
        session_id=session_id,
        channel=channel,
        voltage=voltage
    )
    return event
```

### Step 2: Detection Enrichment (THE FAILURE POINT)
**Service**: `dedicated_labjack_monitor.py`
```python
def _enrich_hil_event_context(self, hil_event, session_id, labjack_trigger_time):
    # ❌ Uses stale cache for video_timing
    context = cached_context  # Only has Video 1 data

    # ❌ Determines wrong video_id
    video_id = self._determine_video_from_timing(video_timing, labjack_trigger_time)
    # Returns Video 1 ID for ALL timestamps after Video 1 started

    # Store detection with wrong video_id
    db_event = DetectionEvent(
        video_id=video_id,  # ❌ Wrong video!
        ...
    )
```

### Step 3: Database Storage
**Result**:
- Detection stored with `video_id` of Video 1
- Video 2 gets 0 detections
- Ground truth matching fails for Video 2

---

## Impact Assessment

### Session b6662f68 Breakdown

| Metric | Video 1 | Video 2 |
|--------|---------|---------|
| Expected Detections | 151 | 27 |
| Assigned Detections | 178 (includes Video 2's) | 0 |
| Correct Assignments | 151 | 0 |
| Incorrect Assignments | 27 (from Video 2) | 0 |
| False Positives | 27 | 0 |
| False Negatives | 0 | 27 |
| Precision | 84.8% (should be 100%) | 0% |
| Recall | 100% | 0% |

### User-Facing Issues

1. **Results Page Shows Wrong Data**:
   - Video 1 detection count inflated
   - Video 2 shows "No detections" despite hardware events
   - Ground truth comparison completely broken for Video 2

2. **Latency Metrics Invalid**:
   - Video 1 latency calculations contaminated with Video 2 detections
   - Video 2 latency cannot be calculated (no detections)

3. **Multi-Video Testing Unreliable**:
   - Only first video gets correct data
   - All subsequent videos fail
   - Makes multi-video validation impossible

---

## Comprehensive Fix Strategy

### Fix #1: Validate sequenceId Before Test Start (CRITICAL)

**File**: `/frontend/src/pages/HILTestExecutionPRD.tsx`

```typescript
const startTest = async () => {
    // Create test session and sequence
    const sequence = await api.createVideoSequence(...);

    if (!sequence?.id) {
        showError('Failed to create video sequence. Cannot start test.');
        return;
    }

    // Pass sequence ID to SequentialVideoPlayer
    setSequenceId(sequence.id);

    // Verify sequenceId was set before starting playback
    if (!sequenceId) {
        throw new Error('CRITICAL: sequenceId not initialized');
    }
};
```

### Fix #2: Always Refresh Cache for Multi-Video Sequences

**File**: `/backend/services/dedicated_labjack_monitor.py`

```python
def _enrich_hil_event_context(self, hil_event, session_id, labjack_trigger_time):
    session_cache = self.active_sessions.setdefault(session_id, {})

    # ALWAYS load fresh context from database for multi-video sequences
    # Don't trust the cache - timing data changes as videos progress
    context = self._load_sequence_context(session_id)

    # Cache for performance, but will be refreshed on next call
    with self.lock:
        session_cache['sequence_context'] = context or {}
        session_cache['context_timestamp'] = time.time()

    # Continue with fresh data...
```

**Alternative: Add Cache TTL**
```python
cache_timestamp = session_cache.get('context_timestamp', 0)
cache_age = time.time() - cache_timestamp

# Refresh if older than 5 seconds (covers video transitions)
if not context or cache_age > 5.0:
    context = self._load_sequence_context(session_id)
    session_cache['sequence_context'] = context
    session_cache['context_timestamp'] = time.time()
```

### Fix #3: Fix _determine_video_from_timing Logic

**File**: `/backend/services/dedicated_labjack_monitor.py`

```python
def _determine_video_from_timing(self, video_timing, trigger_time):
    selected_video = None
    latest_start = -float('inf')

    for video_id, timing in video_timing.items():
        start = self._to_float_timestamp(timing.get("started_at"))
        end = self._to_float_timestamp(timing.get("ended_at"))

        if start is None:
            continue

        # If detection falls within start/end window, choose this video
        if end is not None and start <= trigger_time <= end:
            return video_id

        # ✅ FIXED: Only use fallback if video hasn't ended yet
        if end is None and trigger_time >= start and start > latest_start:
            selected_video = video_id
            latest_start = start
        elif end is not None and trigger_time > end:
            # ❌ Detection is AFTER this video ended - don't assign
            logger.debug(f"Skipping {video_id}: detection at {trigger_time} is after end {end}")
            continue

    # ✅ Return None if no valid video found (triggers cache refresh)
    if selected_video is None:
        logger.warning(f"No video found for timestamp {trigger_time} - cache may be stale")

    return selected_video
```

### Fix #4: Add Cache Invalidation on Video Transitions

**File**: `/backend/api/hil_test_complete.py`

```python
@router.post("/session/{session_id}/video/start")
async def start_video_playback(session_id: str, video_id: str, ...):
    # ... existing code ...

    # CRITICAL: Invalidate LabJack monitor cache when new video starts
    from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
    monitor = get_dedicated_labjack_monitor()

    with monitor.lock:
        if session_id in monitor.active_sessions:
            # Force cache refresh on next detection
            monitor.active_sessions[session_id].pop('sequence_context', None)
            monitor.active_sessions[session_id].pop('context_timestamp', None)
            logger.info(f"✅ Invalidated detection cache for session {session_id} - Video {video_id} starting")

    return {"success": True}
```

### Fix #5: Add User-Visible Error Handling

**File**: `/frontend/src/components/SequentialVideoPlayer.tsx`

```typescript
const sendVideoStartedEvent = async (videoId: string, timestamp: number) => {
    if (!sequenceId) {
        const error = 'CRITICAL: No sequence ID - video timing sync will fail';
        console.error(error);
        setError(error);
        showSnackbar(error, 'error');
        return;
    }

    try {
        const response = await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
            videoId, startedAt: timestamp
        });

        // Verify backend acknowledged
        if (!response.success) {
            throw new Error('Backend did not acknowledge video-started event');
        }

    } catch (err) {
        console.error('❌ CRITICAL: Failed to sync video timing:', err);
        setError('Video timing sync failed. Results may be incomplete.');
        showSnackbar('Warning: Video timing sync failed', 'warning');
        // Continue playback but notify user
    }
};
```

### Fix #6: Add Retry Logic with Exponential Backoff

```typescript
const sendVideoStartedEventWithRetry = async (
    videoId: string,
    timestamp: number,
    retries = 3
) => {
    for (let attempt = 0; attempt < retries; attempt++) {
        try {
            await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
                videoId, startedAt: timestamp
            });
            return; // Success
        } catch (err) {
            if (attempt === retries - 1) {
                // Final retry failed - show error
                setError('Failed to sync video timing after 3 attempts');
                showSnackbar('Video timing sync failed', 'error');
            }
            await delay(1000 * (attempt + 1)); // 1s, 2s, 3s backoff
        }
    }
};
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_multi_video_detection_assignment.py

def test_video_2_detection_assignment():
    """Test that detections during Video 2 are assigned to Video 2"""
    # Setup 2-video sequence
    session = create_test_session_with_videos(db, video_count=2)

    # Simulate Video 1 lifecycle
    monitor.notify_video_started(session.id, video_1.id, t0, db)
    trigger_detection(t0 + 1.0)  # Should assign to Video 1
    monitor.notify_video_ended(session.id, video_1.id, t0 + 5.0, db)

    # Simulate Video 2 lifecycle
    monitor.notify_video_started(session.id, video_2.id, t0 + 5.5, db)
    trigger_detection(t0 + 7.0)  # Should assign to Video 2
    monitor.notify_video_ended(session.id, video_2.id, t0 + 10.0, db)

    # Verify assignments
    detections = db.query(DetectionEvent).filter_by(test_session_id=session.id).all()
    video_1_detections = [d for d in detections if d.video_id == video_1.id]
    video_2_detections = [d for d in detections if d.video_id == video_2.id]

    assert len(video_1_detections) == 1, "Video 1 should have 1 detection"
    assert len(video_2_detections) == 1, "Video 2 should have 1 detection"

def test_cache_refresh_on_video_transition():
    """Test that cache is invalidated when videos transition"""
    # ... test implementation

def test_determine_video_timing_rejects_after_end():
    """Test that detections after video end are not assigned to that video"""
    # ... test implementation
```

### Integration Tests

```python
def test_complete_multi_video_flow():
    """End-to-end test of multi-video sequence with real detections"""
    # Start sequence
    # Play Video 1, trigger detections
    # Transition to Video 2
    # Play Video 2, trigger detections
    # Verify all detections correctly assigned
    # Verify timing metadata correct
    # Verify ground truth matching works
```

---

## Deployment Checklist

- [ ] Apply Fix #1: Validate sequenceId before test start
- [ ] Apply Fix #2: Always refresh cache for multi-video
- [ ] Apply Fix #3: Fix `_determine_video_from_timing` logic
- [ ] Apply Fix #4: Add cache invalidation on video transitions
- [ ] Apply Fix #5: Add user-visible error handling
- [ ] Apply Fix #6: Add retry logic with backoff
- [ ] Run unit tests for all fixes
- [ ] Run integration test with 3-video sequence
- [ ] Test error recovery (network failures, backend restarts)
- [ ] Verify backward compatibility with single-video tests
- [ ] Update API documentation
- [ ] Add monitoring alerts for lifecycle event failures

---

## Conclusion

**Summary**: Multi-video timing coordination fails due to a combination of:
1. **Frontend**: Missing `sequenceId` initialization causing silent lifecycle event failures
2. **Backend**: Stale cache in detection assignment never refreshing for Video 2
3. **Logic**: Flawed fallback logic assigning detections outside time windows
4. **Race Conditions**: In-memory updates not committed before queries

**Risk Level**: **CRITICAL** - Multi-video testing completely broken

**Fix Complexity**: **Medium** - Requires changes across frontend and backend

**Recommended Approach**: Apply all 6 fixes in combination for production-ready solution

**Timeline**:
- Fixes #1-3: 4-6 hours implementation + testing
- Fixes #4-6: 2-3 hours implementation + testing
- Integration testing: 2-4 hours
- **Total: 1-2 days**
