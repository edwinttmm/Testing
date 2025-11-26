# HIL Timing Synchronization Fix - Implementation Guide

**Date**: 2025-11-20
**Issue**: LabJack LED timing doesn't match video playback timing
**Root Cause**: Premature monitoring start before video plays
**Solution**: Defer monitoring until video_started event

---

## Implementation Summary

This document provides step-by-step code changes to fix the HIL timing synchronization issue. All changes are designed to be **backward compatible** and can be deployed incrementally.

---

## Change 1: Create Video Lifecycle Event Handler

**File**: `routers/video_lifecycle_api.py` (NEW FILE)

**Purpose**: Handle browser video lifecycle events (`video_started`, `video_ended`)

```python
"""
Video Lifecycle Event Handler
Handles video playback lifecycle events for HIL timing synchronization
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional
import logging
import time

from database import get_db
from models import TestSession

# Import HIL monitoring services
try:
    from services.dedicated_labjack_monitor import (
        get_dedicated_labjack_monitor,
        start_hil_monitoring
    )
    HIL_MONITORING_AVAILABLE = True
except ImportError:
    HIL_MONITORING_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video-lifecycle", tags=["Video Lifecycle"])


class VideoStartedEvent(BaseModel):
    """Video started event from browser"""
    timestamp: float  # Unix timestamp when video frame 0 displayed
    video_id: str
    frame_number: int = 0
    video_time: float = 0.0  # Should be 0 for video start
    browser_timestamp: Optional[float] = None  # Browser performance.now()


class VideoEndedEvent(BaseModel):
    """Video ended event from browser"""
    timestamp: float  # Unix timestamp when video ended
    video_id: str
    final_frame: Optional[int] = None
    video_duration: Optional[float] = None
    browser_timestamp: Optional[float] = None


@router.post("/{session_id}/started")
async def handle_video_started(
    session_id: str,
    event: VideoStartedEvent,
    db: Session = Depends(get_db)
):
    """
    Handle video_started event from browser.

    This is the CORRECT time to:
    1. Capture T1 (actual video start time)
    2. Start LabJack monitoring (synchronized with video)
    3. Establish timestamp baseline for all detections

    Args:
        session_id: Test session identifier
        event: Video started event data from browser

    Returns:
        Success status and monitoring start confirmation
    """
    try:
        logger.info(f"🎬 VIDEO STARTED EVENT: session={session_id}, video={event.video_id}, t1={event.timestamp:.6f}")

        # 1. Get session from database
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # 2. Capture T1 (actual video start timestamp from browser)
        video_start_timestamp = event.timestamp  # This is T1!
        video_start_timestamp_ns = int(video_start_timestamp * 1e9)

        # 3. Store T1 in session (this is the CORRECT baseline for all timing)
        session.video_playback_start_time = video_start_timestamp
        session.video_playback_start_time_ns = str(video_start_timestamp_ns)
        session.video_timing_sync_status = "video_started"

        # Also store in configuration for backward compatibility
        if not hasattr(session, 'configuration') or session.configuration is None:
            session.configuration = {}

        session.configuration.update({
            "video_playback_start_time": video_start_timestamp,
            "video_start_timestamp_ns": video_start_timestamp_ns,
            "video_id": event.video_id,
            "timing_sync_enabled": True
        })

        db.commit()

        logger.info(f"✅ T1 captured and stored: {video_start_timestamp:.6f} "
                   f"(session started at {session.started_at.timestamp():.6f}, "
                   f"video start delay: {(video_start_timestamp - session.started_at.timestamp()) * 1000:.1f}ms)")

        # 4. NOW start LabJack monitoring (synchronized with video)
        monitoring_started = False
        monitoring_error = None

        if HIL_MONITORING_AVAILABLE:
            try:
                # Get stored HIL configuration from session
                hil_config = session.configuration.get('hil_config', {})

                if not hil_config:
                    logger.warning(f"⚠️ No HIL config stored for session {session_id}, creating default")
                    hil_config = {
                        'video_id': event.video_id,
                        'channels': ['AIN0'],
                        'voltage_threshold': 0.5,
                        'sample_rate': 200,
                        'enable_websocket': True
                    }

                # Add video start timestamp to config
                hil_config['video_start_timestamp'] = video_start_timestamp
                hil_config['video_start_timestamp_ns'] = video_start_timestamp_ns
                hil_config['timing_sync_enabled'] = True

                logger.info(f"🚀 Starting LabJack monitoring NOW (synchronized with video start)")

                # Start HIL monitoring with synchronized timestamp
                success = await start_hil_monitoring(hil_config)

                if success:
                    monitoring_started = True
                    session.video_timing_sync_status = "monitoring_synchronized"
                    db.commit()

                    logger.info(f"✅ LabJack monitoring started and synchronized with video")
                else:
                    monitoring_error = "start_hil_monitoring returned False"
                    logger.error(f"❌ Failed to start LabJack monitoring: {monitoring_error}")

            except Exception as e:
                monitoring_error = str(e)
                logger.error(f"❌ Exception starting LabJack monitoring: {e}", exc_info=True)
        else:
            monitoring_error = "HIL monitoring service not available"
            logger.warning(f"⚠️ HIL monitoring not available, skipping")

        # 5. Return success response
        return {
            "success": True,
            "session_id": session_id,
            "video_id": event.video_id,
            "video_start_timestamp": video_start_timestamp,
            "video_start_timestamp_ns": video_start_timestamp_ns,
            "timing_sync_status": session.video_timing_sync_status,
            "monitoring_started": monitoring_started,
            "monitoring_error": monitoring_error,
            "t0_command_timestamp": session.started_at.timestamp(),
            "t1_video_start_timestamp": video_start_timestamp,
            "t1_minus_t0_ms": (video_start_timestamp - session.started_at.timestamp()) * 1000,
            "message": "Video start captured and monitoring synchronized" if monitoring_started else "Video start captured but monitoring failed"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error handling video_started event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to handle video start: {str(e)}")


@router.post("/{session_id}/ended")
async def handle_video_ended(
    session_id: str,
    event: VideoEndedEvent,
    db: Session = Depends(get_db)
):
    """
    Handle video_ended event from browser.

    This is the CORRECT time to stop LabJack monitoring (synchronized with video end).

    Args:
        session_id: Test session identifier
        event: Video ended event data from browser

    Returns:
        Success status and monitoring stop confirmation
    """
    try:
        logger.info(f"🎬 VIDEO ENDED EVENT: session={session_id}, video={event.video_id}, t_end={event.timestamp:.6f}")

        # 1. Get session from database
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # 2. Store video end timestamp
        video_end_timestamp = event.timestamp
        session.video_timing_sync_status = "video_ended"
        db.commit()

        logger.info(f"✅ Video end captured: {video_end_timestamp:.6f}")

        # 3. Stop LabJack monitoring NOW (synchronized with video end)
        monitoring_stopped = False
        monitoring_stats = {}

        if HIL_MONITORING_AVAILABLE:
            try:
                from services.dedicated_labjack_monitor import stop_hil_monitoring

                logger.info(f"⏹️ Stopping LabJack monitoring NOW (synchronized with video end)")

                stats = stop_hil_monitoring(session_id)

                if stats.get("success"):
                    monitoring_stopped = True
                    monitoring_stats = stats

                    logger.info(f"✅ LabJack monitoring stopped: {stats.get('detection_count', 0)} detections")
                else:
                    logger.error(f"❌ Failed to stop LabJack monitoring: {stats.get('error')}")

            except Exception as e:
                logger.error(f"❌ Exception stopping LabJack monitoring: {e}", exc_info=True)

        # 4. Calculate video duration
        if session.video_playback_start_time:
            video_duration = video_end_timestamp - session.video_playback_start_time
            logger.info(f"📊 Video duration: {video_duration:.3f}s")
        else:
            video_duration = None
            logger.warning(f"⚠️ No video start time recorded, cannot calculate duration")

        # 5. Return success response
        return {
            "success": True,
            "session_id": session_id,
            "video_id": event.video_id,
            "video_end_timestamp": video_end_timestamp,
            "video_duration": video_duration,
            "monitoring_stopped": monitoring_stopped,
            "monitoring_stats": monitoring_stats,
            "message": "Video end captured and monitoring stopped" if monitoring_stopped else "Video end captured but monitoring stop failed"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error handling video_ended event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to handle video end: {str(e)}")
```

---

## Change 2: Modify Test Session Start to Store Config (Not Start Monitoring)

**File**: `routers/test_sessions.py:1069-1202`

**Purpose**: Remove premature monitoring start, store config for later use

### Change 2a: Remove premature timestamp assignment

**Location**: Lines 1089-1098

```python
# BEFORE (WRONG):
session.started_at = datetime.utcnow()
video_playback_start_time = session.started_at.timestamp()
video_playback_start_time_ns = time.time_ns()

if hasattr(session, 'video_playback_start_time'):
    session.video_playback_start_time = video_playback_start_time
    session.video_playback_start_time_ns = str(video_playback_start_time_ns)

# AFTER (CORRECT):
# Only capture command time (T0)
session.started_at = datetime.utcnow()

# DON'T set video_playback_start_time here!
# It will be set by video_lifecycle_api when video actually starts
# Just mark that timing will be synchronized
if hasattr(session, 'video_timing_sync_status'):
    session.video_timing_sync_status = "waiting_for_video_start"
```

### Change 2b: Store HIL config instead of starting monitoring

**Location**: Lines 1113-1187

```python
# BEFORE (WRONG):
if HIL_MONITORING_AVAILABLE and VIDEO_TIMING_AVAILABLE:
    logger.info(f"🚀 Starting HIL monitoring with video timing sync for session: {session_id}")

    # ... configure video_timing_config ...

    # Start HIL monitoring with video synchronization
    success = await start_hil_monitoring(session_id, video_timing_config)

# AFTER (CORRECT):
if HIL_MONITORING_AVAILABLE and VIDEO_TIMING_AVAILABLE:
    logger.info(f"📝 Preparing HIL config for session: {session_id} (monitoring will start when video starts)")

    # Get video information for timing synchronization
    video = db.query(Video).filter(Video.id == session.video_id).first() if session.video_id else None

    # Configure HIL monitoring (but don't start yet!)
    video_timing_config = {
        "video_id": session.video_id,
        "fps": getattr(video, 'fps', 30.0) if video else 30.0,
        "duration": getattr(video, 'duration', None) if video else None,
        "channels": ["AIN0"],
        "voltage_threshold": float(os.getenv("LABJACK_DEFAULT_THRESHOLD", "0.5")),
        "voltage_range": 10.0,
        "debug_voltage": True,
        "debounce_ms": 0,
        "sample_rate": 200,
        "enable_websocket": True,
        "enable_frame_sync": True,
        "use_stream_mode": True,
        "continuous_mode": False,
        "continuous_lower_bound": float(os.getenv("LABJACK_DEFAULT_THRESHOLD", "0.5")),
        "continuous_interval_ms": 5,
        "steady_high_logging": True,
        "steady_high_interval_ms": 5
    }

    # CRITICAL FIX: Store config in session for later use by video_lifecycle_api
    # DO NOT start monitoring here - wait for video_started event!
    if not hasattr(session, 'configuration') or session.configuration is None:
        session.configuration = {}

    session.configuration['hil_config'] = video_timing_config
    session.video_timing_sync_status = "config_stored"
    db.commit()

    logger.info(f"✅ HIL config stored for session: {session_id}")
    logger.info(f"⏳ Waiting for video_started event to begin monitoring...")

else:
    logger.warning("⚠️ HIL monitoring or video timing service not available")
```

---

## Change 3: Update Dedicated LabJack Monitor to Use T1 Baseline

**File**: `services/dedicated_labjack_monitor.py`

### Change 3a: Add video start timestamp to session data

**Location**: Lines 542-558

```python
# BEFORE:
self.active_sessions[session_id] = {
    'video_timing_config': video_timing_config,
    'labjack_config': labjack_config,
    'started_at': session_init_time,
    'video_start_time': None,  # Never populated!
    # ... other fields
}

# AFTER:
self.active_sessions[session_id] = {
    'video_timing_config': video_timing_config,
    'labjack_config': labjack_config,
    'started_at': session_init_time,
    'video_start_time': video_timing_config.get('video_start_timestamp'),  # T1 from config
    'video_start_timestamp_ns': video_timing_config.get('video_start_timestamp_ns'),
    'timing_baseline': 'video_start',  # Use video start as baseline, not session start
    # ... other fields
}

logger.info(f"✅ Session initialized with video start time: {video_timing_config.get('video_start_timestamp'):.6f}")
```

### Change 3b: Update detection handler to use T1 baseline

**Location**: `_handle_detection_with_video_sync` method (find and update)

```python
def _handle_detection_with_video_sync(self, session_id: str, event: DetectionEvent):
    """
    Handle detection event with video timing synchronization.
    Calculate relative timestamps using T1 (video start time) as baseline.
    """
    try:
        session_data = self.active_sessions.get(session_id)
        if not session_data:
            logger.warning(f"No active session data for {session_id}")
            return

        # Get T1 (video start time) as baseline
        video_start_time = session_data.get('video_start_time')

        if not video_start_time:
            logger.error(f"❌ No video start time for session {session_id} - cannot calculate relative timestamp")
            # Store with absolute timestamp as fallback
            event.video_relative_timestamp = None
            event.video_playback_start_time = None
            return

        # Calculate relative timestamp: T-relative = T-detection - T1
        detection_timestamp = event.timestamp  # Absolute timestamp
        relative_timestamp = detection_timestamp - video_start_time

        # Validate relative timestamp is positive
        if relative_timestamp < 0:
            logger.warning(f"⚠️ Negative relative timestamp detected: {relative_timestamp:.6f}s "
                          f"(detection={detection_timestamp:.6f}, video_start={video_start_time:.6f})")
            # Clamp to 0 if negative (detection before video start)
            relative_timestamp = 0.0

        # Store corrected timestamps in detection event
        event.video_relative_timestamp = relative_timestamp
        event.video_playback_start_time = video_start_time

        # Calculate video frame number if FPS available
        fps = session_data.get('video_timing_config', {}).get('fps', 30.0)
        frame_number = int(relative_timestamp * fps)
        event.video_frame_number = frame_number

        logger.debug(f"✅ Detection synchronized: t_rel={relative_timestamp:.6f}s, frame={frame_number}")

    except Exception as e:
        logger.error(f"❌ Error in video sync detection handler: {e}", exc_info=True)
```

---

## Change 4: Register Video Lifecycle Router

**File**: `main.py` (or wherever routers are registered)

**Purpose**: Register the new video lifecycle event handler

```python
# Add to main.py where routers are registered

from routers import video_lifecycle_api

# Register video lifecycle router
app.include_router(video_lifecycle_api.router)

logger.info("✅ Video lifecycle event handler registered")
```

---

## Change 5: Frontend - Emit Video Lifecycle Events

**File**: Frontend video player component (e.g., `VideoPlayer.tsx`)

**Purpose**: Emit video_started and video_ended events to backend

```javascript
// Add to your video player component

const VideoPlayer = ({ sessionId, videoUrl }) => {
  const videoRef = useRef(null);

  const handleVideoStarted = async () => {
    // Capture high-precision timestamp when video actually starts
    const timestamp = Date.now() / 1000;  // Unix timestamp in seconds
    const browserTimestamp = performance.now();  // High-precision browser time

    console.log(`🎬 Video started at T1=${timestamp}, emitting event...`);

    try {
      const response = await fetch(`/api/video-lifecycle/${sessionId}/started`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          timestamp: timestamp,
          video_id: videoUrl,
          frame_number: 0,
          video_time: 0.0,
          browser_timestamp: browserTimestamp
        })
      });

      const data = await response.json();
      console.log('✅ Video start event processed:', data);

      if (!data.monitoring_started) {
        console.warn('⚠️ Monitoring failed to start:', data.monitoring_error);
      }
    } catch (error) {
      console.error('❌ Failed to send video_started event:', error);
    }
  };

  const handleVideoEnded = async () => {
    // Capture timestamp when video ends
    const timestamp = Date.now() / 1000;
    const browserTimestamp = performance.now();

    console.log(`🎬 Video ended at T_end=${timestamp}, emitting event...`);

    try {
      const response = await fetch(`/api/video-lifecycle/${sessionId}/ended`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          timestamp: timestamp,
          video_id: videoUrl,
          final_frame: Math.floor(videoRef.current.currentTime * 30),  // Assuming 30fps
          video_duration: videoRef.current.duration,
          browser_timestamp: browserTimestamp
        })
      });

      const data = await response.json();
      console.log('✅ Video end event processed:', data);

      if (!data.monitoring_stopped) {
        console.warn('⚠️ Monitoring failed to stop');
      }
    } catch (error) {
      console.error('❌ Failed to send video_ended event:', error);
    }
  };

  useEffect(() => {
    const video = videoRef.current;

    // Listen for 'playing' event (video actually starts)
    // NOT 'play' event (user clicked play button)
    video.addEventListener('playing', handleVideoStarted);
    video.addEventListener('ended', handleVideoEnded);

    return () => {
      video.removeEventListener('playing', handleVideoStarted);
      video.removeEventListener('ended', handleVideoEnded);
    };
  }, [sessionId]);

  return (
    <video
      ref={videoRef}
      src={videoUrl}
      controls
      onPlay={() => console.log('▶️ User clicked play (but video not playing yet)')}
    />
  );
};
```

---

## Testing the Fix

### Test 1: Verify Video Start Event Flow

```bash
# 1. Start test session
curl -X POST http://localhost:8000/api/test-sessions/{session_id}/start

# Expected: Session starts, but monitoring does NOT start yet
# Check logs for: "⏳ Waiting for video_started event to begin monitoring..."

# 2. Simulate video_started event (or let frontend send it)
curl -X POST http://localhost:8000/api/video-lifecycle/{session_id}/started \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": 1700000000.5,
    "video_id": "video_123",
    "frame_number": 0,
    "video_time": 0.0
  }'

# Expected response:
# {
#   "success": true,
#   "monitoring_started": true,
#   "t1_video_start_timestamp": 1700000000.5,
#   "t1_minus_t0_ms": 250.0  # Should be 200-500ms
# }

# Check logs for: "✅ LabJack monitoring started and synchronized with video"
```

### Test 2: Verify Timestamp Calculations

```bash
# After session completes, check detection events
curl http://localhost:8000/api/test-sessions/{session_id}/events

# Expected: All events should have:
# - video_relative_timestamp >= 0 (NO NEGATIVE VALUES)
# - video_playback_start_time = T1 (from video_started event)
# - timestamp - video_playback_start_time = video_relative_timestamp
```

### Test 3: Hardware Validation

```python
import time
from test_client import TestClient

client = TestClient()

# 1. Start session
response = client.post(f"/api/test-sessions/{session_id}/start")
t0 = time.time()

# 2. Verify LED is OFF (monitoring hasn't started)
time.sleep(0.1)
assert not is_led_on(), "LED should be OFF before video starts"

# 3. Send video_started event
time.sleep(0.2)  # Simulate 200ms video start delay
t1 = time.time()
client.post(f"/api/video-lifecycle/{session_id}/started", json={
    "timestamp": t1,
    "video_id": "test_video",
    "frame_number": 0
})

# 4. Verify LED is NOW ON (monitoring started after video)
time.sleep(0.1)
assert is_led_on(), "LED should be ON after video starts"

print(f"✅ SUCCESS: LED turned on {(t1-t0)*1000:.1f}ms after session start")
print(f"✅ This matches video start delay (expected 200-500ms)")
```

---

## Deployment Checklist

- [ ] Backend Changes
  - [ ] Create `routers/video_lifecycle_api.py`
  - [ ] Modify `routers/test_sessions.py` (remove premature monitoring start)
  - [ ] Update `services/dedicated_labjack_monitor.py` (use T1 baseline)
  - [ ] Register video lifecycle router in `main.py`

- [ ] Frontend Changes
  - [ ] Add video lifecycle event emission to video player
  - [ ] Test event timing with console logs
  - [ ] Verify events reach backend correctly

- [ ] Database Changes
  - [ ] Ensure `video_timing_sync_status` field exists in `test_sessions` table
  - [ ] No migration needed (fields already exist)

- [ ] Testing
  - [ ] Unit tests for video lifecycle handlers
  - [ ] Integration tests for timing synchronization
  - [ ] Hardware validation with physical LED
  - [ ] Load testing with concurrent sessions

- [ ] Monitoring
  - [ ] Add metrics for T1-T0 delay (should be 200-500ms)
  - [ ] Add alerts for negative latencies (should never occur)
  - [ ] Monitor video start event success rate

---

## Rollback Plan

If issues occur after deployment:

1. **Emergency Rollback**: Set environment variable `LEGACY_TIMING_MODE=true`
2. **Graceful Rollback**: Restore `test_sessions.py` to start monitoring immediately
3. **Partial Rollback**: Keep video lifecycle events but use old timing baseline

---

## Success Metrics

After deployment, monitor these metrics:

| Metric | Target | Measurement |
|--------|--------|-------------|
| LED starts after video | 100% | Hardware observation |
| Negative latencies | 0% | Detection event analysis |
| T1-T0 delay | 200-500ms | Session timing analysis |
| Video start event success rate | >99% | API monitoring |
| Timing synchronization accuracy | ±10ms | Ground truth comparison |

---

**Implementation Status**: Ready for Implementation
**Estimated Implementation Time**: 1-2 days
**Risk Level**: Low (backward compatible, incremental deployment)
**Testing Required**: Unit, Integration, Hardware Validation
