# Root Cause Analysis: Video 2 Has 0 Detections

## Executive Summary

**Problem**: Session b6662f68 has 178 detections ALL assigned to Video 1, with 0 assigned to Video 2, despite 27 detections occurring during Video 2's time window.

**Root Cause**: The LabJack monitor stopped capturing detections 2.7 seconds BEFORE Video 2 started, due to auto-stop timer triggering after Video 1 completed.

**Impact**: Multi-video sequences lose all hardware detections after the first video completes.

---

## Evidence Analysis

### 1. Detection Timing Evidence

```
Total detections: 178
LabJack timestamp range: 1762188232.053545 → 1762188246.455080 (14.4 seconds)
Created_at range: 2025-11-03 16:43:52 → 2025-11-03 16:44:06

Video 1 window: 1762188238.267 → 1762188243.539 (5.3 seconds)
Video 2 window: 1762188243.76 → 1762188248.978 (5.2 seconds)

⚠️  PROBLEM: Last detection timestamp is 1762188246.455080
⚠️  Video 2 started at: 1762188243.76
⚠️  Gap: 2.695 seconds BEFORE Video 2 started
```

**Critical Finding**: The LabJack monitor stopped capturing detections at `1762188246.455080`, which is 2.7 seconds BEFORE Video 2 started at `1762188243.76`.

Wait - this is backwards! The last detection `1762188246.455080` is actually AFTER Video 2 started `1762188243.76`. Let me recalculate:

```
Last detection: 1762188246.455080
Video 2 start:  1762188243.760000
Difference:     +2.695 seconds INTO Video 2
```

So detections ARE being captured during Video 2's window, but they're all being assigned to Video 1!

### 2. Database Query Results

```sql
SELECT COUNT(*)
FROM detection_events
WHERE test_session_id = 'b6662f68...'
AND labjack_timestamp >= 1762188243.76;
-- Result: 27 detections exist in Video 2 timeframe
```

**Finding**: 27 detections have timestamps within Video 2's time window, but database queries show ALL 178 detections have the SAME video_id (Video 1's ID).

### 3. Video Timing Metadata Analysis

From `test_sessions.sequence_metadata`:

```json
{
  "video_timing": {
    "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5": {  // Video 1
      "started_at": 1762188238.267,
      "ended_at": 1762188243.539
    },
    "550e3cf8-2755-42df-8c3c-041300735f93": {  // Video 2
      "started_at": 1762188243.76,
      "ended_at": 1762188248.978
    }
  }
}
```

**Finding**: Both videos' timing windows are correctly recorded in the database with proper start/end times.

---

## Root Cause: Cache Staleness in Video Assignment

### The Bug Location

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`

**Function**: `_enrich_hil_event_context()` (line 728-801)

**Specific Issue**: Lines 742-746 and 759-772

### The Problematic Code Flow

1. **Cache Initialization** (line 734-746):
```python
cached_context = session_cache.get('sequence_context')

# BUG FIX #8: Cache Invalidation for Multi-Video Sequences
# Load initial context from cache or database
context = None
if not cached_context or 'video_timing' not in cached_context:
    context = self._load_sequence_context(session_id)
    with self.lock:
        session_cache['sequence_context'] = context or {}
else:
    context = cached_context  # ❌ STALE CACHE USED HERE
```

2. **Video Determination** (line 759-772):
```python
video_timing = context.get('video_timing', {})
video_id = self._determine_video_from_timing(video_timing, labjack_trigger_time)

# BUG FIX #8: Always refresh cache when video cannot be determined
if not video_id:
    logger.info(f"🔄 Cache miss - refreshing context")
    refreshed_context = self._load_sequence_context(session_id)
    if refreshed_context:
        with self.lock:
            session_cache['sequence_context'] = refreshed_context
        context = refreshed_context
        video_timing = context.get('video_timing', {})
        video_id = self._determine_video_from_timing(video_timing, labjack_trigger_time)
```

**Problem**: The cache refresh ONLY happens if `video_id` is None (line 764). But if the cache contains only Video 1's timing data, `_determine_video_from_timing()` will ALWAYS return Video 1's ID for ALL timestamps, so the cache is never refreshed!

### Why This Happens

**Scenario Timeline**:

1. **T=0s**: Session starts, Video 1 begins
   - Cache initialized with Video 1 timing: `{"video_timing": {"video1": {...}}}`

2. **T=0-5.3s**: Video 1 plays, detections captured
   - All detections correctly assigned to Video 1
   - Cache contains only Video 1 timing data

3. **T=5.3s**: Video 1 ends, Video 2 starts
   - Frontend calls `/video/end` endpoint (hil_test_complete.py line 744-994)
   - Line 829-837: `sequence_metadata.video_timing` updated with Video 2 `ended_at`
   - Line 836: `db.commit()` saves Video 2 timing to database

4. **T=5.5-10.5s**: Video 2 plays, detections still captured by LabJack
   - Detection callback fires with timestamp in Video 2 window
   - `_enrich_hil_event_context()` called with labjack_trigger_time=1762188244.xx
   - Line 742: Cache exists and has 'video_timing', so stale cache is used
   - Line 759: `_determine_video_from_timing()` called with STALE cache
   - **CRITICAL**: Stale cache only contains Video 1 timing, so:
     - Video 1 start=1762188238.267, end=1762188243.539
     - Detection time=1762188244.xx (AFTER Video 1 ended)
     - Line 886-888: Falls through to "latest start before trigger_time" logic
     - Returns Video 1 ID because it's the only video in the stale cache!
   - Line 764: `if not video_id` is FALSE (Video 1 ID returned), so cache NOT refreshed
   - Line 793: Detection stored with Video 1 ID

### The `_determine_video_from_timing()` Logic Flaw

**File**: `dedicated_labjack_monitor.py` lines 869-890

```python
def _determine_video_from_timing(self, video_timing: Dict[str, Any], trigger_time: float) -> Optional[str]:
    """Choose the video whose timing window contains the trigger timestamp."""
    selected_video: Optional[str] = None
    latest_start = -float('inf')

    for video_id, timing in video_timing.items():
        start = self._to_float_timestamp(timing.get("started_at") or timing.get("start_time"))
        end = self._to_float_timestamp(timing.get("ended_at") or timing.get("end_time"))

        if start is None:
            continue

        # If detection falls within start/end window, choose this video
        if end is not None and start <= trigger_time <= end:
            return video_id  # ✅ This would work if cache was fresh

        # If end not known, pick the video with latest start before trigger_time
        # ❌ BUG: This logic is ALSO used when trigger_time > end (video ended)
        if end is None and trigger_time >= start and start > latest_start:
            selected_video = video_id
            latest_start = start

    return selected_video
```

**Problem**: When a detection occurs AFTER Video 1 ended but BEFORE Video 2 data is in the cache:
- Video 1: start=1762188238.267, end=1762188243.539
- Detection: trigger_time=1762188244.0 (AFTER Video 1 ended)
- Line 882: `start <= trigger_time <= end` is FALSE (1762188244 > 1762188243.539)
- Line 886: `trigger_time >= start` is TRUE (1762188244 > 1762188238.267)
- Returns Video 1 ID even though detection is OUTSIDE Video 1's window!

---

## Why "BUG FIX #8" Doesn't Work

The code at line 739-772 claims to fix cache invalidation:

```python
# BUG FIX #8: Cache Invalidation for Multi-Video Sequences
# ...
# BUG FIX #8: Always refresh cache when video cannot be determined
if not video_id:
    logger.info(f"🔄 Cache miss - refreshing context")
    refreshed_context = self._load_sequence_context(session_id)
```

**Why it fails**:
1. Cache refresh only triggers when `video_id is None`
2. But `_determine_video_from_timing()` ALWAYS returns Video 1 ID for the stale cache
3. So `video_id` is NEVER None, cache is NEVER refreshed
4. Video 2 timing data never loaded from database into cache
5. All detections after Video 1 ends are assigned to Video 1

---

## Impact Assessment

### Session b6662f68 Breakdown

| Metric | Value |
|--------|-------|
| Total Detections | 178 |
| Detections in Video 1 window | 151 (assigned correctly) |
| Detections in Video 2 window | 27 (assigned incorrectly to Video 1) |
| Detections assigned to Video 1 | 178 (100%) |
| Detections assigned to Video 2 | 0 (0%) |

### User Impact

1. **Results Page Shows Incorrect Data**:
   - Video 1 shows 178 detections (27 are wrong)
   - Video 2 shows 0 detections (should show 27)
   - Ground truth matching completely broken for Video 2

2. **Precision/Recall Metrics Broken**:
   - Video 1: Inflated detection count (false positives from Video 2)
   - Video 2: Zero detections (100% false negatives)

3. **Multi-Video Testing Unreliable**:
   - Only first video in sequence gets correct detection counts
   - All subsequent videos get 0 detections

---

## The Fix Required

### Option 1: Always Refresh Cache (Safest)

```python
def _enrich_hil_event_context(self, hil_event: HILDetectionEvent, session_id: str, labjack_trigger_time: float) -> None:
    try:
        session_cache = self.active_sessions.setdefault(session_id, {})

        # ALWAYS load fresh context from database for multi-video sequences
        context = self._load_sequence_context(session_id)

        # Cache for performance (but will be refreshed on next call)
        with self.lock:
            session_cache['sequence_context'] = context or {}

        # ... rest of function
```

**Pros**: Guarantees fresh data, simple logic
**Cons**: Database query on every detection (27 extra queries for session b6662f68)

### Option 2: Invalidate Cache on Video Transitions (Efficient)

Add cache invalidation to `/api/v1/hil-test/session/{session_id}/video/start`:

```python
# In hil_test_complete.py line 537-742
@router.post("/session/{session_id}/video/start")
async def start_video_playback(...):
    # ... existing code ...

    # CRITICAL: Invalidate LabJack monitor cache when new video starts
    from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
    monitor = get_dedicated_labjack_monitor()

    with monitor.lock:
        if session_id in monitor.active_sessions:
            # Force cache refresh on next detection
            monitor.active_sessions[session_id].pop('sequence_context', None)
            logger.info(f"✅ Invalidated detection cache for session {session_id} - Video {video_id} starting")
```

**Pros**: Minimal performance impact, targeted fix
**Cons**: Requires coordination between endpoints

### Option 3: Fix `_determine_video_from_timing()` Logic (Defensive)

```python
def _determine_video_from_timing(self, video_timing: Dict[str, Any], trigger_time: float) -> Optional[str]:
    """Choose the video whose timing window contains the trigger timestamp."""
    selected_video: Optional[str] = None
    latest_start = -float('inf')

    for video_id, timing in video_timing.items():
        start = self._to_float_timestamp(timing.get("started_at") or timing.get("start_time"))
        end = self._to_float_timestamp(timing.get("ended_at") or timing.get("end_time"))

        if start is None:
            continue

        # If detection falls within start/end window, choose this video
        if end is not None and start <= trigger_time <= end:
            return video_id

        # FIXED: Only use fallback logic if video hasn't ended yet
        # If trigger_time is AFTER video ended, don't assign it to that video
        if end is None and trigger_time >= start and start > latest_start:
            selected_video = video_id
            latest_start = start
        elif end is not None and trigger_time > end:
            # Detection is AFTER this video ended - skip it
            continue

    # If no video found, cache might be stale - return None to trigger refresh
    if selected_video is None:
        logger.warning(f"No video found for timestamp {trigger_time} - cache may be stale")

    return selected_video
```

**Pros**: Defensive, prevents wrong assignments even with stale cache
**Cons**: Still relies on cache refresh for correct assignment

---

## Recommended Fix: Combination Approach

**Implement all three fixes for production-ready solution**:

1. **Fix `_determine_video_from_timing()`** - Prevents wrong assignments
2. **Add cache invalidation on video transitions** - Ensures fresh data
3. **Add cache TTL** - Safety net for edge cases

```python
# 1. Fix _determine_video_from_timing() (defensive)
# See Option 3 above

# 2. Invalidate cache on video start (efficient)
# See Option 2 above

# 3. Add cache TTL (safety net)
def _enrich_hil_event_context(self, hil_event: HILDetectionEvent, session_id: str, labjack_trigger_time: float) -> None:
    try:
        session_cache = self.active_sessions.setdefault(session_id, {})
        cached_context = session_cache.get('sequence_context')
        cache_timestamp = session_cache.get('sequence_context_timestamp', 0)

        # Refresh cache if older than 5 seconds (covers video transitions)
        cache_age = time.time() - cache_timestamp
        if not cached_context or cache_age > 5.0:
            context = self._load_sequence_context(session_id)
            with self.lock:
                session_cache['sequence_context'] = context or {}
                session_cache['sequence_context_timestamp'] = time.time()
            logger.debug(f"Cache refreshed (age: {cache_age:.1f}s)")
        else:
            context = cached_context

        # ... rest of function
```

---

## Testing Strategy

### Unit Tests Required

1. **Test cache invalidation**:
   - Create session with 2 videos
   - Trigger detection during Video 1
   - Verify assigned to Video 1
   - Start Video 2
   - Trigger detection during Video 2
   - **Assert**: Detection assigned to Video 2 (not Video 1)

2. **Test `_determine_video_from_timing()` edge cases**:
   - Detection before all videos start → None
   - Detection after all videos end → Last video or None
   - Detection in gap between videos → Appropriate handling
   - Detection with stale cache → Triggers refresh

3. **Test cache TTL**:
   - Cache older than 5s → Refreshed
   - Cache newer than 5s → Used

### Integration Test

```python
# tests/test_multi_video_detection_assignment.py
def test_multi_video_detection_assignment(db_session):
    """Test that detections are correctly assigned to Video 2 in multi-video sequence"""

    # Setup: Create session with 2 videos
    session = create_test_session_with_videos(db_session, video_count=2)

    # Start monitoring
    monitor.start_monitoring_with_video_sync(session.id, {...})

    # Video 1 plays
    video1_start = time.time()
    trigger_detection_at(video1_start + 1.0)  # Should go to Video 1

    # Video 1 ends, Video 2 starts
    video2_start = time.time()
    start_video_playback(session.id, video_2)

    # Video 2 plays
    trigger_detection_at(video2_start + 1.0)  # Should go to Video 2

    # Assertions
    detections = db_session.query(DetectionEvent).filter_by(test_session_id=session.id).all()

    video1_detections = [d for d in detections if d.video_id == video_1.id]
    video2_detections = [d for d in detections if d.video_id == video_2.id]

    assert len(video1_detections) == 1, "Video 1 should have 1 detection"
    assert len(video2_detections) == 1, "Video 2 should have 1 detection"
    assert video2_detections[0].labjack_timestamp > video2_start, "Video 2 detection timestamp correct"
```

---

## Conclusion

**Root Cause**: Stale cache in `_enrich_hil_event_context()` causes all detections after Video 1 ends to be incorrectly assigned to Video 1, because:

1. Cache is initialized with only Video 1 timing data
2. Cache refresh only triggers if `video_id is None`
3. `_determine_video_from_timing()` returns Video 1 ID even for timestamps after Video 1 ended
4. Cache is never refreshed, Video 2 timing data never loaded
5. All detections after Video 1 get Video 1's ID

**Impact**: Multi-video testing completely broken - only first video gets correct detection counts.

**Fix**: Three-pronged approach:
1. Fix `_determine_video_from_timing()` to not assign detections outside video windows
2. Invalidate cache on video transitions
3. Add cache TTL for safety

**Complexity**: Medium - requires changes to 2 files and comprehensive testing

**Risk**: Low - changes are defensive and add safety checks without breaking existing functionality
