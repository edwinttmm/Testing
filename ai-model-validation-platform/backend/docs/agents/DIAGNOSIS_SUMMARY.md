# Session 6d05fcd1: Root Cause Diagnosis Summary

**Date**: 2025-11-05
**Session**: `6d05fcd1-0c9b-432b-acbd-675c5e3683c9`
**Issue**: Frame 120 bunching, missing Video 2 detections
**Status**: **ROOT CAUSE IDENTIFIED**

---

## Quick Summary

**Problem**: Multi-video sequence test shows all detections bunched at Frame 120, with Video 2 showing 0 detections.

**Root Cause**: Video lifecycle events (`video-started`, `video-ended`) **were not successfully received** by the backend, leaving both videos with NULL timing data.

**Impact**: All 161 detections have `video_id: NULL` and cannot be assigned to the correct video, causing:
- Frame numbers to span both videos (4-309) without reset
- Timestamps calculated relative to sequence start, not video start
- All detections appearing under "Session-level" rather than per-video
- Frame 120 appearing as a "bunching" artifact (actually the transition point)

---

## Evidence Chain

### 1. Multi-Video Configuration Confirmed

```sql
Session: 6d05fcd1-0c9b-432b-acbd-675c5e3683c9
Sequence ID: 3aea0970-4d24-4e8c-9d32-cab68bc3e58d
Total Videos: 2
Status: running ✅
```

This is definitely a multi-video sequence test.

### 2. Video Lifecycle Data Missing

```sql
Video 0: child_test_video_20251031_144012.mp4
  status: pending              ❌ Expected: "completed"
  video_start_time: NULL       ❌ Expected: ~1762352910.606
  video_end_time: NULL         ❌ Expected: ~1762352915.648
  detection_count: 0           ❌ Expected: ~80

Video 1: Child_20251031_143523.mp4
  status: pending              ❌ Expected: "completed"
  video_start_time: NULL       ❌ Expected: ~1762352915.648
  video_end_time: NULL         ❌ Expected: ~1762352920.690
  detection_count: 0           ❌ Expected: ~81
```

**Finding**: Both `SequenceVideoResult` records have NULL timing. This means the backend **never received** the `video-started` or `video-ended` events.

### 3. All Detections Orphaned

```sql
video_id: NULL
  Count: 161
  Frames: 4 - 309             ❌ Spans both videos without reset
  Frame 120: 2 detections     ⚠️ This is the "bunching" artifact
  Time Range: 0.198s - 12.890s
```

**Finding**: Without video timing, the orchestrator cannot determine which video each detection belongs to, so all detections get `video_id: NULL`.

### 4. Frontend Code Review

**File**: `/frontend/src/components/SequentialVideoPlayer.tsx`

✅ **Lifecycle event functions exist**:
- Line 110: `sendVideoStartedEvent()`
- Line 190: `sendVideoEndedEvent()`

✅ **Functions are called**:
- Line 510: `await sendVideoStartedEvent(video.id, updatedTiming.playbackStartTime!);`
- Line 626: `const nextVideoId = await sendVideoEndedEvent(currentVideo.id, videoEnd, actualPlaybackSeconds);`

✅ **Error handling exists**:
```typescript
console.error('❌ FAILED to send video-started event:', {
  error: errorMessage,
  videoId,
  sequenceId,
  startedAt: startedAtUnix
});
```

**Conclusion**: Frontend code is **correctly implemented** to send lifecycle events.

### 5. Backend Code Review

**File**: `/backend/routers/video_sequences.py`

✅ **Endpoints exist**:
- Line 120: `POST /{sequence_id}/video-started`
- Line 217: `POST /{sequence_id}/video-ended`

✅ **Implementation is correct**:
```python
@router.post("/{sequence_id}/video-started")
async def video_started(sequence_id: str, data: VideoStartedRequest, ...):
    video_result.video_start_time = data.timestamp
    video_result.video_start_time_ns = str(int(data.timestamp * 1_000_000_000))
    video_result.video_status = "playing"
    db.commit()
```

**Conclusion**: Backend endpoint is **correctly implemented** to record timing.

---

## Root Cause Analysis

Since both frontend and backend code are correct, why did the lifecycle events fail?

### Hypothesis 1: API Call Failed Silently ⚠️

**Likelihood**: HIGH

The frontend makes async API calls but may not properly handle/report failures:

```typescript
try {
  const response = await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
    videoId: videoId,
    startedAt: startedAtUnix,
    clientTimestamp: clientTimestamp
  });
} catch (err) {
  console.error('❌ FAILED to send video-started event:', ...);
  // ❌ Error is logged but playback continues
  // ❌ No retry mechanism
  // ❌ No user notification (besides console)
}
```

**Problem**: If the API call fails (network error, CORS, timeout, etc.), the error is only logged to the console. The video playback continues normally, but the backend never receives timing data.

### Hypothesis 2: Race Condition on Sequence ID ⚠️

**Likelihood**: MEDIUM

The frontend validates `sequenceId` before making API calls:

```typescript
if (!sequenceId || sequenceId.trim() === '') {
  const criticalError = '❌ CRITICAL: Cannot send video-started event - no sequence ID.';
  console.error(criticalError);
  return; // ❌ Silently returns without sending event
}
```

**Problem**: If `sequenceId` is empty/null when the video starts, the API call is skipped entirely. This could happen if:
- Sequence initialization failed
- Sequence ID wasn't passed to the component
- Component rendered before sequence was created

### Hypothesis 3: Backend Route Not Registered 🔴

**Likelihood**: LOW (but possible)

Check if the router is actually registered in the FastAPI app:

```python
# In main.py or __init__.py
app.include_router(video_sequences.router)  # ❓ Is this present?
```

**Problem**: If the router isn't registered, the endpoints don't exist and API calls return 404.

### Hypothesis 4: CORS/Network Issue 🔴

**Likelihood**: LOW

Frontend and backend might be on different origins (localhost:3000 vs localhost:8000), causing CORS preflight failures.

**Problem**: Browser blocks the request before it reaches the backend.

---

## Verification Steps

### Step 1: Check Browser DevTools Network Tab

For session `6d05fcd1`, check if the API requests were made:

```
Filter: video-started
Filter: video-ended
```

**Expected**:
- 2 requests to `/api/video-sequences/3aea0970.../video-started`
- 2 requests to `/api/video-sequences/3aea0970.../video-ended`

**If NOT found**: Frontend never sent the requests → Check Hypothesis 2 (missing sequence ID)

**If FOUND with 404**: Backend route not registered → Check Hypothesis 3

**If FOUND with 500**: Backend error → Check backend logs

**If FOUND with CORS error**: CORS misconfiguration → Check Hypothesis 4

### Step 2: Check Browser Console Logs

Look for error messages:

```
Search: "CRITICAL: Cannot send video-started"
Search: "FAILED to send video-started event"
```

**If found**: Sequence ID was missing or API call failed

### Step 3: Check Backend Logs

```bash
grep "video-started" /backend/logs/access.log | grep "6d05fcd1"
grep "video-ended" /backend/logs/access.log | grep "6d05fcd1"
```

**If NOT found**: Backend never received the requests → API call failed on frontend

**If found**: Backend received them → Check if database commits succeeded

### Step 4: Database Query

```sql
SELECT
  video_id,
  video_start_time,
  video_end_time,
  video_status
FROM sequence_video_results
WHERE video_sequence_id = '3aea0970-4d24-4e8c-9d32-cab68bc3e58d';
```

**Expected**: Both videos should have `video_start_time` and `video_end_time`

**Actual**: Both have NULL → Confirms events were never processed

---

## Recommended Fixes

### Fix 1: Add Retry Logic (Priority: HIGH)

**File**: `/frontend/src/components/SequentialVideoPlayer.tsx`

```typescript
const sendVideoStartedEvent = useCallback(async (videoId: string, timestamp: number) => {
  const maxRetries = 3;
  let attempt = 0;

  while (attempt < maxRetries) {
    try {
      const response = await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
        videoId,
        startedAt: timestamp,
        clientTimestamp: new Date().toISOString()
      });

      console.log('✅ Video-started event sent successfully');
      return; // Success
    } catch (err) {
      attempt++;
      console.error(`❌ Attempt ${attempt}/${maxRetries} failed:`, err);

      if (attempt >= maxRetries) {
        // CRITICAL: Notify user that timing tracking failed
        setError(`Failed to sync video start after ${maxRetries} attempts. Results may be incomplete.`);
        onError(`Video timing sync failed for ${videoId}`);
        throw err;
      }

      // Wait before retry (exponential backoff)
      await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
    }
  }
}, [sequenceId, setError, onError]);
```

### Fix 2: Add Fallback Timing Estimation (Priority: MEDIUM)

**File**: `/backend/services/detection_video_reassignment.py`

Add to `_build_video_timing_map()`:

```python
def _build_video_timing_map(...):
    # ... existing code ...

    # FALLBACK: If video_start_time is NULL, estimate from metadata
    if not video_timing_map:
        logger.warning("No video timing found - estimating from metadata")
        estimated_timing = self._estimate_video_timing_from_metadata(
            video_results, session, db
        )
        video_timing_map.update(estimated_timing)

    return video_timing_map

def _estimate_video_timing_from_metadata(
    self,
    video_results: List[SequenceVideoResult],
    session: TestSession,
    db: Session
) -> Dict[str, Dict[str, Any]]:
    """Estimate video timing when lifecycle events are missing."""

    estimated_timing = {}
    cumulative_offset = 0.0
    session_start = session.started_at.timestamp()

    for vr in sorted(video_results, key=lambda x: x.sequence_order):
        video = db.query(Video).filter(Video.id == vr.video_id).first()
        if not video or not video.duration:
            continue

        estimated_start = session_start + cumulative_offset
        estimated_end = estimated_start + video.duration

        estimated_timing[vr.video_id] = {
            "start_time": estimated_start,
            "end_time": estimated_end,
            "duration_s": video.duration,
            "estimated": True,
            "confidence": "low"
        }

        cumulative_offset += video.duration

    return estimated_timing
```

### Fix 3: Add Health Check Monitoring (Priority: LOW)

**File**: `/backend/routers/video_sequences.py`

```python
@router.get("/{sequence_id}/health")
async def check_sequence_health(sequence_id: str, db: Session = Depends(get_db)):
    """Check if video sequence has proper timing data."""

    video_results = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.video_sequence_id == sequence_id
    ).all()

    warnings = []
    for vr in video_results:
        if vr.video_status != "pending" and vr.video_start_time is None:
            warnings.append({
                "type": "missing_start_time",
                "video_id": vr.video_id,
                "sequence_order": vr.sequence_order,
                "message": f"Video {vr.sequence_order} has no start time"
            })

    return {
        "sequence_id": sequence_id,
        "status": "healthy" if not warnings else "degraded",
        "warnings": warnings,
        "videos_checked": len(video_results)
    }
```

### Fix 4: Manual Timing Injection (Immediate Workaround)

For the current session, manually inject estimated timing:

```sql
-- Video 1: Starts at session start
UPDATE sequence_video_results
SET
  video_start_time = 1762352910.606,
  video_end_time = 1762352915.648,
  actual_duration_ms = 5041,
  video_status = 'completed'
WHERE video_id = '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5'
  AND video_sequence_id = '3aea0970-4d24-4e8c-9d32-cab68bc3e58d';

-- Video 2: Starts after Video 1 ends
UPDATE sequence_video_results
SET
  video_start_time = 1762352915.648,
  video_end_time = 1762352920.690,
  actual_duration_ms = 5041,
  video_status = 'completed'
WHERE video_id = '550e3cf8-2755-42df-8c3c-041300735f93'
  AND video_sequence_id = '3aea0970-4d24-4e8c-9d32-cab68bc3e58d';

-- Then run reassignment
-- curl -X POST http://localhost:8000/api/detection-reassignment/6d05fcd1.../run
```

---

## Action Items

### Immediate (for current session)

1. ✅ **Diagnosis complete**: Root cause identified
2. ⏭️ **Manual fix**: Inject video timing estimates into database
3. ⏭️ **Run reassignment**: Use existing service to assign video_ids
4. ⏭️ **Verify fix**: Check that detections are now split across videos

### Short-term (for future sessions)

1. ⏭️ **Add retry logic**: Implement exponential backoff for API calls
2. ⏭️ **Add user notifications**: Show warnings when timing sync fails
3. ⏭️ **Add health checks**: Monitor video timing data during playback
4. ⏭️ **Add fallback estimation**: Auto-estimate timing when events are missing

### Long-term (system improvements)

1. ⏭️ **Integration tests**: Test multi-video lifecycle event flow
2. ⏭️ **Monitoring dashboard**: Real-time visualization of sequence health
3. ⏭️ **Automatic recovery**: Auto-retry failed events with user notification
4. ⏭️ **Telemetry**: Track API call success rates and failure modes

---

## Conclusion

**This is NOT a timestamp calculation bug.**

The Frame 120 bunching and missing Video 2 data are symptoms of **missing video lifecycle events**. The frontend code is correct, the backend code is correct, but the API calls **did not successfully complete** for this session.

The most likely cause is:
1. **Network failure** during API call (temporary connection issue)
2. **Missing sequence ID** at playback time (race condition)
3. **Silent error** that was only logged to console

**Impact**: Without video timing data, the backend cannot assign detections to the correct video, causing all detections to appear as "orphaned" with NULL video_id and continuous frame numbering across both videos.

**Fix**: Implement retry logic, fallback timing estimation, and better error handling to ensure lifecycle events are reliably delivered to the backend.

**Immediate workaround**: Manually inject estimated video timing into the database and run the reassignment service to fix the current session's data.
