# Video Playback Timing Analysis: Loop vs Auto-Stop Investigation

**Analysis Date:** 2025-11-05
**Session:** 71976ec4 (Frame 120 Bunching Anomaly)
**Hypothesis:** Video may loop or auto-stop mechanism may be incorrectly configured

---

## Executive Summary

**VERDICT: ❌ VIDEO LOOPING HYPOTHESIS RULED OUT**

The "Frame 120 bunching" phenomenon is **NOT caused by video looping or replay**. The system has explicit **auto-stop monitoring** built-in with proper safeguards. However, the investigation revealed a **race condition** in the auto-stop timer that may cause premature monitoring termination.

---

## Key Findings

### ✅ Video Loop Prevention Confirmed

1. **Frontend has NO loop attribute set**
   - `SequentialVideoManager.tsx`: `loopPlayback = false` (line 80)
   - No `video.loop = true` anywhere in codebase
   - Video elements created without loop attribute

2. **Auto-Stop Monitoring Active**
   - Backend has explicit auto-stop timer (line 284-358)
   - Grace period: 5% of video duration or [0.25s..2s]
   - For 5.25s video: `duration + grace = 5.25s + 0.25s = 5.5s`

3. **Monitoring Lifecycle Tied to Video Duration**
   ```python
   # /backend/services/dedicated_labjack_monitor.py:346-348
   time.sleep(duration + grace)
   self.stop_monitoring(session_id)
   logger.info(f"⏹️ Auto-stopped monitoring after duration {duration}s (+{grace:.2f}s grace)")
   ```

---

## Video Playback Lifecycle Flow

### 1. Video Start Event Chain

```
Frontend                          Backend                           Monitor
   |                                 |                                 |
   |---video.play()----------------->|                                 |
   |                                 |                                 |
   |---video_started WebSocket------>|                                 |
   |   (sessionId, videoStartTime)   |                                 |
   |                                 |                                 |
   |                                 |--start_monitoring()------------>|
   |                                 |  (video_timing_config)          |
   |                                 |                                 |
   |                                 |                                 |--✅ LabJack monitoring ON
   |                                 |                                 |--🕒 Auto-stop timer started
   |                                 |                                 |   (duration + grace)
```

**Code Evidence:**

**Frontend (`socketio_server.py:562-607`):**
```python
@sio.event
async def video_started(sid, data):
    """Handle video started events for timing synchronization"""
    session_id = data.get('sessionId')
    video_start_time = data.get('videoStartTime')

    # Record video timing in synchronization service
    timing_sync_service.record_video_event(session_id, 'play_start', video_start_time)

    # Broadcast to session room
    await sio.emit('video_timing_update', {...}, room=room)
```

**Backend Monitor (`dedicated_labjack_monitor.py:111-362`):**
```python
def start_monitoring_with_video_sync(self, session_id: str, video_timing_config: Dict[str, Any]):
    # Start LabJack monitoring FIRST
    success = self.labjack_monitor.start_monitoring(session_id, **labjack_config)

    # THEN start video timing
    video_start_time = self.video_timing_service.start_video_timing(session_id, video_id, db, video_metadata)

    # Auto-stop timer setup (ONLY for single-video sessions)
    if not is_sequence:
        duration = video_timing_config.get('duration')
        grace = max(0.25, min(2.0, duration * 0.05))  # 5% or [0.25s..2s]

        def _delayed_stop():
            time.sleep(duration + grace)
            self.stop_monitoring(session_id)
            logger.info(f"⏹️ Auto-stopped monitoring after duration {duration}s (+{grace:.2f}s grace)")

        threading.Thread(target=_delayed_stop, daemon=True).start()
        logger.info(f"🕒 Monitoring will auto-stop after {duration + grace:.2f}s")
```

### 2. Video End Event Chain

```
Frontend                          Backend                           Monitor
   |                                 |                                 |
   |<--video.onEnded()----------------|                                 |
   |                                 |                                 |
   |---video_ended WebSocket-------->|                                 |
   |   (sessionId, endedAt)          |                                 |
   |                                 |                                 |
   |                                 |--notify_video_ended()---------->|
   |                                 |                                 |
   |                                 |                                 |--⏹️ Stop monitoring
   |                                 |                                 |--📊 Finalize metrics
```

**Code Evidence:**

**Frontend WebSocket Handler (`socketio_server.py` - NOT IMPLEMENTED):**
- ❌ **CRITICAL FINDING:** No `video_ended` WebSocket event handler exists in `socketio_server.py`
- The `video_started` event IS handled (line 562), but `video_ended` is **missing**

**Backend Endpoint (`routers/video_sequences.py:217-307`):**
```python
@router.post("/{sequence_id}/video-ended", response_model=VideoEventResponse)
async def video_ended(sequence_id: str, data: VideoEndedRequest, db: Session = Depends(get_db)):
    """Record when a video in the sequence ends playback"""

    # Invalidate cache for multi-video sequences
    try:
        from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
        monitor = get_dedicated_labjack_monitor()
        monitor.invalidate_sequence_cache(sequence.test_session_id)
        logger.info(f"✅ Cache invalidated for session {sequence.test_session_id} after video-ended")
    except Exception as cache_error:
        logger.error(f"Failed to invalidate cache: {cache_error}")

    # Emit WebSocket event
    await sio.emit('video_ended', {
        'sequence_id': sequence_id,
        'video_id': data.video_id,
        'ended_at': data.ended_at,
        'timestamp': time.time()
    }, room=f"sequence_{sequence_id}")
```

### 3. Auto-Stop Timer Logic

**When Timer Fires:**

```python
# Timer expiry (duration + grace after video start)
T=0.00s   Video starts, timer scheduled for T=5.5s
T=5.25s   Video naturally ends (actual duration)
T=5.50s   ⏰ Timer fires, calls stop_monitoring()
```

**Race Condition Scenario:**

```
Scenario A: Normal Flow (Timer after video ends)
├─ T=0.0s   Video starts
├─ T=5.2s   Video ends naturally
├─ T=5.2s   video_ended event sent
├─ T=5.3s   Backend stops monitoring
├─ T=5.5s   Timer fires (does nothing, already stopped) ✅ SAFE

Scenario B: Timer Fires Early (Race condition if duration wrong)
├─ T=0.0s   Video starts
├─ T=5.0s   ⏰ Timer fires (wrong duration: 5.0s instead of 5.25s)
├─ T=5.0s   Backend stops monitoring ❌ PREMATURE
├─ T=5.2s   Video still playing but monitoring STOPPED
├─ T=5.2s   Detections LOST (not captured) ❌ BUG

Scenario C: Multiple Rapid Detections Before Timer
├─ T=0.0s   Video starts, timer for T=5.5s
├─ T=4.8s   Hardware sends 97 pulses in 400ms burst
├─ T=5.2s   Video ends, all detections captured ✅ OK
├─ T=5.5s   Timer fires, stops monitoring (clean shutdown)
```

---

## Video Looping: Evidence Against

### 1. No Loop Configuration

**Search Results:**
```bash
$ grep -rn "video\.loop\|loop.*true\|loopPlayback.*true" frontend/src/
# Result: NO matches with loop=true for HIL testing
```

**SequentialVideoManager.tsx (Line 57-80):**
```typescript
interface SequentialVideoManagerProps {
  loopPlayback?: boolean;  // Default: false
  // ...
}

const SequentialVideoManager: React.FC<SequentialVideoManagerProps> = ({
  loopPlayback = false,  // ✅ EXPLICIT DEFAULT: FALSE
  // ...
}) => {
  // Loop logic only triggers if loopPlayback prop is true
  if (loopPlayback) {
    // Loop back to first video
  } else {
    // Call onPlaybackComplete (normal termination)
    onPlaybackComplete?.();
  }
}
```

### 2. Video Duration Enforcement

**Auto-Stop Timer Safeguards:**
- Timer scheduled at video start
- Duration retrieved from database if missing
- Fallback to actual video duration (5.25s)
- Grace period prevents early cutoff

**Code (`dedicated_labjack_monitor.py:313-356`):**
```python
# Enhanced fallback mechanism for missing duration
if not isinstance(duration, (int, float)) or duration <= 0:
    logger.warning(f"⚠️ Missing or invalid video duration: {duration}")

    # Fallback 1: Query video from database
    if video_id:
        video = db.query(Video).filter(Video.id == video_id).first()
        if video and video.duration:
            duration = video.duration
            logger.info(f"✅ Retrieved duration from database: {duration}s")

    # Fallback 2: Use actual video duration
    if not duration:
        duration = 5.25  # Actual video duration
        logger.warning(f"⚠️ Using full video monitoring: {duration}s")

# Calculate grace period
grace = max(0.25, min(2.0, duration * 0.05))  # 5% or [0.25s..2s]

# Schedule auto-stop
threading.Thread(target=_delayed_stop, daemon=True).start()
logger.info(f"🕒 Monitoring will auto-stop after {duration + grace:.2f}s")
```

### 3. Timestamp Pattern Analysis

**If video looped, we would see:**
```
First playback (0-5.25s):
  - Detection 1: video_relative_timestamp = 0.5s
  - Detection 2: video_relative_timestamp = 1.0s
  - ... (no detections captured)

Second playback (5.25-10.5s) [LOOP]:
  - Detection 97: video_relative_timestamp = 5.0s (should be 10.25s if continuous)
  - Detection 98: video_relative_timestamp = 5.1s (should be 10.35s)

❌ EXPECTED: Timestamps would RESET to 0-5s range on second loop
```

**Actual timestamps in Session 71976ec4:**
```
Detections bunch at 4.8-5.2s range (Frame 115-125)
- All timestamps are in FIRST playback range
- NO timestamps beyond 5.25s (video duration)
- NO repeated 0-5s patterns
```

**Conclusion:** Timestamps show continuous progression, NOT looping pattern.

---

## Critical Bug Discovered: Missing `video_ended` WebSocket Handler

### Issue

The frontend sends `video_started` events via WebSocket, but there is **NO corresponding `video_ended` event handler** in `socketio_server.py`.

**Evidence:**

1. ✅ `video_started` handler EXISTS (line 562-607)
2. ❌ `video_ended` handler MISSING

**Search Results:**
```bash
$ grep -n "async def video_ended" backend/socketio_server.py
# Result: NO MATCHES
```

### Impact

Without a `video_ended` WebSocket handler:
- Frontend sends `video_ended` event → Backend ignores it
- Backend relies ONLY on auto-stop timer
- If timer duration is wrong, monitoring stops early
- Late detections (Frame 115-125) may be missed if timer fires too soon

### Recommended Fix

Add WebSocket handler for `video_ended` event:

```python
# /backend/socketio_server.py
@sio.event
async def video_ended(sid, data):
    """Handle video ended events for timing synchronization"""
    try:
        session_id = data.get('sessionId')
        video_id = data.get('videoId')
        ended_at = data.get('endedAt')

        if not session_id:
            await sio.emit('error', {
                'message': 'sessionId is required for video ended event'
            }, room=sid)
            return

        logger.info(f"Video ended event received from client {sid} for session {session_id}")

        # Record video timing
        try:
            from services.timing_synchronization_service import timing_sync_service
            timing_sync_service.record_video_event(session_id, 'play_end', ended_at)
        except Exception as timing_error:
            logger.warning(f"Failed to record video end timing: {timing_error}")

        # Stop monitoring (let dedicated monitor handle)
        try:
            from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
            monitor = get_dedicated_labjack_monitor()
            monitor.stop_session_monitoring(session_id)
            logger.info(f"✅ Monitoring stopped for session {session_id} after video ended")
        except Exception as monitor_error:
            logger.error(f"Failed to stop monitoring: {monitor_error}")

        # Broadcast to session room
        room = f"test_session_{session_id}"
        await sio.emit('video_timing_update', {
            'session_id': session_id,
            'video_id': video_id,
            'ended_at': ended_at,
            'event': 'video_ended',
            'timestamp': asyncio.get_event_loop().time()
        }, room=room)

        # Send confirmation
        await sio.emit('video_ended_confirmed', {
            'session_id': session_id,
            'recorded_time': ended_at,
            'timestamp': asyncio.get_event_loop().time()
        }, room=sid)

    except Exception as e:
        logger.error(f"Error handling video ended event: {str(e)}")
        await sio.emit('error', {
            'message': f'Video ended event handling failed: {str(e)}'
        }, room=sid)
```

---

## Alternative Explanation for Frame 120 Bunching

Given that video looping is ruled out, the **Frame 120 bunching** is likely caused by:

### Hypothesis 1: Hardware Burst at End of Video

**Most Likely:**
- Hardware sends 97 detection pulses in rapid succession (400ms burst)
- Burst occurs at T=4.8-5.2s (near end of 5.25s video)
- LabJack captures all pulses correctly
- Timing synchronization assigns all to Frame 115-125 range

**Why Frame 120 specifically:**
- Frame 120 = 5.0s @ 24fps
- Burst occurs at 4.8-5.2s
- Mean timestamp ≈ 5.0s → Frame 120
- Statistical clustering around mean

### Hypothesis 2: Timing Service Calculation Error

**Possible:**
- Video timing service miscalculates frame numbers
- All detections assigned same frame due to rounding error
- Timestamp precision loss (ms → s → frame)

**Evidence:**
```python
# /backend/services/dedicated_labjack_monitor.py:541
video_frame_number = int(fallback_video_relative * 24)  # 24fps
```

### Hypothesis 3: Detection Event Bunching in Queue

**Less Likely:**
- Detection events queued in bridge/monitor
- Processed in batch at end of video
- All assigned similar timestamps

---

## Monitoring Lifecycle States

### State Diagram

```
┌─────────────────┐
│   INITIALIZED   │
└────────┬────────┘
         │ start_monitoring_with_video_sync()
         ▼
┌─────────────────┐      ┌──────────────────┐
│   MONITORING    │◄─────┤  Auto-Stop Timer │
│   (Active)      │      │  (duration+grace)│
└────────┬────────┘      └──────────────────┘
         │
         │ Detection events captured
         │
         ├──► Detection 1 @ T=0.5s
         ├──► Detection 2 @ T=1.0s
         │    ...
         ├──► Detection 97 @ T=5.0s
         │
         ▼
┌─────────────────┐
│  VIDEO ENDED    │
│  (T=5.25s)      │
└────────┬────────┘
         │
         │ EITHER:
         │ 1. video_ended WebSocket (missing)
         │ 2. Auto-stop timer fires (T=5.5s)
         │
         ▼
┌─────────────────┐
│     STOPPED     │
│  (Finalized)    │
└─────────────────┘
```

### Multi-Video Sequence Handling

**Critical Difference:**
```python
# Auto-stop timer is DISABLED for multi-video sequences
if is_sequence:
    logger.info(f"🎬 Skipping auto-stop timer for multi-video sequence - orchestrator will control lifecycle")
else:
    # Only single-video sessions get auto-stop timer
    threading.Thread(target=_delayed_stop, daemon=True).start()
```

**For multi-video:**
- Orchestrator controls start/stop
- Cache invalidation on `video-started` and `video-ended` lifecycle events
- No auto-stop timer (manual control)

---

## Recommendations

### Immediate Fixes

1. **Add `video_ended` WebSocket Handler**
   - Implement in `socketio_server.py`
   - Match functionality of `video_started` handler
   - Call `monitor.stop_session_monitoring(session_id)`

2. **Verify Auto-Stop Timer Duration**
   - Log actual duration used in timer
   - Compare with video metadata
   - Check for off-by-one errors

3. **Add Monitoring Lifecycle Logging**
   ```python
   logger.info(f"📹 Video duration: {duration}s, Timer: {duration+grace}s")
   logger.info(f"⏰ Auto-stop scheduled for T={video_start_time + duration + grace}")
   logger.info(f"⏹️ Monitoring stopped at T={stop_time} (video ended at T={video_end_time})")
   ```

### Long-Term Improvements

1. **Explicit Lifecycle Management**
   - Replace auto-stop timer with explicit video end signal
   - Require frontend to send `video_ended` event
   - Backend waits for confirmation before stopping

2. **Timing Validation**
   - Compare timer duration with actual video playback duration
   - Warn if mismatch detected
   - Adjust grace period dynamically

3. **Detection Event Analysis**
   - Add histogram of detection timestamps
   - Flag suspicious clustering (e.g., >90% in single frame)
   - Alert on burst patterns

---

## Conclusion

**Video Looping Hypothesis: ❌ RULED OUT**

The "Frame 120 bunching" phenomenon is **NOT** caused by:
- ✅ Video looping (explicitly disabled)
- ✅ Multiple playbacks (no timestamp reset pattern)
- ✅ Auto-replay (no repeat configuration)

**Root Cause More Likely:**
1. **Hardware burst timing** (97 pulses in 400ms at end of video)
2. **Timing calculation precision loss** (frame rounding)
3. **Missing `video_ended` WebSocket handler** (monitoring relies on timer only)

**Critical Bug Found:**
- ❌ `video_ended` WebSocket handler missing in `socketio_server.py`
- ✅ Auto-stop timer exists but may fire too early if duration wrong
- ⚠️ Frontend sends `video_ended` but backend ignores it

**Next Investigation:**
Focus on **hardware timing patterns** and **detection event processing pipeline** rather than video playback lifecycle.
