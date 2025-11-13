# Video 2 Zero Detections - Root Cause Analysis and Fix

## Executive Summary

**Problem**: Video 2 has 0 detections in database despite 45 detections occurring during its time window. All 100 detections were incorrectly assigned to Video 1.

**Root Cause**: Cache invalidation failure in multi-video sequences. The `_load_sequence_context()` cache is not refreshed when Video 2 starts, causing all Video 2 detections to use stale Video 1 timing data.

## Evidence from Database Analysis

### Video Timing Windows (from sequence_metadata)
```
Video 1 (10c2b16c-86fa-4140-b1cf-c0ea42f82ca5):
  - Started: 1762252000.742
  - Ended: 1762252006.014
  - Expected detections: 50

Video 2 (550e3cf8-2755-42df-8c3c-041300735f93):
  - Started: 1762252006.147
  - Ended: 1762252011.333
  - Expected detections: 0 (metadata)
```

### Actual Detection Distribution
```
Detections by labjack_timestamp range:
  Video 1 window (1762252000.742 - 1762252006.014): 10 detections
  Video 2 window (1762252006.147 - 1762252011.333): 45 detections

Detections by assigned video_id:
  Video 1: 100 detections ❌
  Video 2: 0 detections ❌
```

### Sample Misassigned Detections
```
Timestamp          Assigned Video    Should Be Video
1762252006.547     Video 1           Video 2         ❌
1762252006.685     Video 1           Video 2         ❌
1762252007.006     Video 1           Video 2         ❌
1762252010.522     Video 1           Video 2         ❌
1762252011.268     Video 1           Video 2         ❌
```

## Root Cause Analysis

### The Bug Chain

1. **Video 1 Starts**
   - `video-started` event sent by frontend
   - Backend updates `sequence_metadata.video_timing` with Video 1 timing
   - `_load_sequence_context()` caches this data

2. **Video 1 Detections** (Correct)
   - Detections arrive with timestamps in Video 1 window
   - `_determine_video_from_timing()` correctly assigns to Video 1
   - Result: ✅ 10 detections correctly assigned to Video 1

3. **Video 2 Starts** (Cache Not Refreshed)
   - `video-started` event sent by frontend
   - Backend updates `sequence_metadata.video_timing` with Video 2 timing
   - ❌ BUT: `_load_sequence_context()` cache is NOT invalidated
   - Cache still contains only Video 1 timing data

4. **Video 2 Detections** (Misassigned)
   - Detections arrive with timestamps in Video 2 window (1762252006.547+)
   - `_load_sequence_context()` returns cached data (only Video 1 timing)
   - `_determine_video_from_timing()` doesn't find Video 2 in timing data
   - Fallback logic assigns to Video 1
   - Result: ❌ 45 detections incorrectly assigned to Video 1

### Code Analysis

#### Location: `dedicated_labjack_monitor.py`

**Problem Area 1: Cache Invalidation (Line 859-862)**
```python
# ALWAYS refresh cache for multi-video sequences
if is_multi_video:
    with self.lock:
        session_cache.pop('sequence_context', None)
    logger.info(f"Cache invalidated for multi-video session {session_id}")
```

**Issue**: Cache invalidation happens in `_enrich_hil_event_context()`, but this only invalidates when a NEW detection arrives. The cache is not proactively invalidated when `video-started` events are received.

**Problem Area 2: Video Assignment (Line 810-813)**
```python
# Try to determine video
video_id = self._determine_video_from_timing(
    video_timing=context.get('video_timing', {}),
    trigger_time=trigger_time
)
```

**Issue**: The `video_timing` dict only contains Video 1 data because cache wasn't refreshed after Video 2 started.

## The Fix

### 1. Add Explicit Cache Invalidation Method

Add a public method that can be called by the video lifecycle endpoints:

```python
def invalidate_sequence_cache(self, session_id: str):
    """Invalidate sequence context cache - called by video lifecycle events."""
    with self.lock:
        session_cache = self.active_sessions.get(session_id, {})
        session_cache.pop('sequence_context', None)
    logger.info(f"✅ Cache invalidated for session {session_id}")
```

### 2. Call Cache Invalidation from Video Lifecycle Endpoints

In `routers/video_sequences.py`, call the cache invalidation method:

```python
@router.post("/{sequence_id}/video-started", response_model=VideoEventResponse)
async def record_video_started(
    sequence_id: str,
    request: VideoStartedRequest,
    db: Session = Depends(get_db)
):
    # ... existing code ...

    # CRITICAL: Invalidate detection assignment cache
    from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
    monitor = DedicatedLabJackMonitor.get_instance()
    if monitor and session:
        monitor.invalidate_sequence_cache(session.id)
        logger.info(f"✅ Cache invalidated for session {session.id} after video-started")

    # ... rest of existing code ...
```

### 3. Force Cache Refresh on Every Detection (Belt and Suspenders)

Modify `_load_sequence_context()` to always refresh for multi-video:

```python
def _load_sequence_context(self, session_id: str, retry_attempt: int = 0) -> Optional[Dict[str, Any]]:
    """
    Load sequence metadata and cache it for quick lookup.

    MULTI-VIDEO FIX: For multi-video sequences, always fetch fresh data
    to ensure video timing windows are up-to-date.
    """
    try:
        db = next(get_db())
        try:
            session_record = db.query(TestSession).filter(
                TestSession.id == session_id
            ).first()

            if not session_record:
                return None

            # Check if multi-video sequence
            is_multi_video = session_record.has_video_sequence and \
                           len(session_record.sequence_metadata.get('video_ids', [])) > 1

            # For multi-video, ALWAYS fetch fresh data (no caching)
            # This ensures we get the latest video timing windows
            if is_multi_video:
                logger.debug(f"Multi-video sequence detected - fetching fresh timing data")

            # Parse metadata
            context = {
                "sequence_id": session_record.sequence_id,
                "fallback_video_id": session_record.video_id,
                "sequence_started_at": session_record.started_at.timestamp() if session_record.started_at else None,
                "video_timing": {},
                "sequence_video_results": {},
                "is_multi_video": is_multi_video
            }

            # Get video timing from sequence_metadata
            raw_metadata = session_record.sequence_metadata
            if isinstance(raw_metadata, str):
                try:
                    metadata = json.loads(raw_metadata)
                except json.JSONDecodeError:
                    metadata = {}
            elif isinstance(raw_metadata, dict):
                metadata = dict(raw_metadata)
            else:
                metadata = {}

            context["video_timing"] = metadata.get("video_timing", {})

            # Log the video timing data for debugging
            logger.debug(f"Loaded video_timing for session {session_id}: {context['video_timing'].keys()}")

            return context
        finally:
            db.close()
    except Exception as exc:
        logger.warning(f"⚠️ Failed to load sequence context for session {session_id}: {exc}")
        return None
```

## Backfill Strategy

### Option 1: Reassign Based on Timestamps (Recommended)

```sql
-- Update detections to correct video based on timestamp ranges
UPDATE detection_events
SET video_id = '550e3cf8-2755-42df-8c3c-041300735f93'
WHERE test_session_id = '9e4b2ff4-820e-4250-a110-1393b67ec224'
  AND labjack_timestamp >= 1762252006.147
  AND labjack_timestamp < 1762252011.333
  AND video_id = '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5';
```

### Option 2: Delete and Recapture (High Risk)

Only if timestamps are corrupted. NOT recommended for this case.

## Testing the Fix

### Test Case 1: New Multi-Video Session
1. Start multi-video session
2. Play Video 1
3. Verify detections assigned to Video 1
4. Play Video 2
5. Verify detections assigned to Video 2
6. Check database: `SELECT video_id, COUNT(*) FROM detection_events WHERE test_session_id = '...' GROUP BY video_id`

### Test Case 2: Cache Invalidation
1. Enable debug logging
2. Start multi-video session
3. Send `video-started` for Video 1
4. Check logs: "Cache invalidated for session..."
5. Send `video-started` for Video 2
6. Check logs: "Cache invalidated for session..."
7. Verify detections have correct video_id

### Test Case 3: Verify Backfill
```sql
-- Check detection counts after backfill
SELECT
  video_id,
  COUNT(*) as count,
  MIN(labjack_timestamp) as min_ts,
  MAX(labjack_timestamp) as max_ts
FROM detection_events
WHERE test_session_id = '9e4b2ff4-820e-4250-a110-1393b67ec224'
GROUP BY video_id;
```

Expected result:
```
Video 1 (10c2b16c-...): 55 detections (10 in window + 45 before window)
Video 2 (550e3cf8-...): 45 detections (all in window)
```

## Files to Modify

1. `/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`
   - Add `invalidate_sequence_cache()` method (line 767 - already exists)
   - Modify `_load_sequence_context()` to skip cache for multi-video (line 983)

2. `/home/rigade/Testing/ai-model-validation-platform/backend/routers/video_sequences.py`
   - Call cache invalidation in `video-started` endpoint (line 119)
   - Call cache invalidation in `video-ended` endpoint (line 192)

3. Create backfill script:
   - `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/backfill_video_2_detections.py`

## Deployment Steps

1. Apply code fixes
2. Restart backend server
3. Run backfill script for existing sessions
4. Test with new multi-video session
5. Verify in production UI

## Success Criteria

- ✅ Video 2 detections correctly assigned to Video 2
- ✅ Detection count matches expected count per video
- ✅ Latency calculations use correct video timing
- ✅ Ground truth matching works for all videos
- ✅ No cache staleness in multi-video sequences
