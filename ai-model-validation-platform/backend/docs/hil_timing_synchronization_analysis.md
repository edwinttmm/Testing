# HIL Timing Synchronization Root Cause Analysis

**Date**: 2025-11-20
**System**: AI Model Validation Platform - Hardware-in-the-Loop Testing
**Issue**: LabJack LED timing doesn't match video playback timing
**Severity**: CRITICAL - Invalidates all latency measurements

## Executive Summary

The HIL test system shows **fundamental timing desynchronization** between video playback and LabJack hardware monitoring. Physical LED indicators show that LabJack detection **starts BEFORE video plays** and **stops BEFORE video ends**, resulting in **negative latency values (real -6ms)** and complete timing incoherence.

### Core Problem

**LabJack monitoring starts immediately when `start_monitoring()` is called, but video playback timing is established 200-500ms later**, creating a timing window desynchronization.

---

## 1. Current Behavior (Observed)

### Timeline of Events

```
T0 = 0ms      : POST /api/test-sessions/{id}/start called
T1 = 10ms     : Session.started_at = datetime.now()
T2 = 15ms     : session.video_playback_start_time = started_at.timestamp()
T3 = 20ms     : start_hil_monitoring() called
T4 = 25ms     : LabJack monitoring thread STARTS (LED turns ON)
              : ⚠️ LabJack immediately begins detecting voltages
T5 = 30-50ms  : Hardware starts generating signals
T6 = 200-500ms: Video ACTUALLY starts playing in browser
T7 = Video End: Video stops playing
T8 = End+50ms : LabJack monitoring stops (LED turns OFF)
              : ⚠️ LabJack stops BEFORE video completes
```

### Physical Evidence

1. **LED Starts Early**: Physical detection LED on T7 blinks BEFORE video starts
2. **LED Stops Early**: Physical detection LED stops BEFORE video ends
3. **Negative Latencies**: Timeline shows "real -6ms" (impossible)
4. **Timing Drift**: 200-500ms desynchronization window

---

## 2. Root Cause Analysis

### 2.1 Primary Issue: Premature LabJack Monitoring Start

**Location**: `services/dedicated_labjack_monitor.py:632-651`

```python
# STEP 1: Start LabJack monitoring BEFORE video timing
logger.info(f"🚀 STEP 1: Starting LabJack monitoring FIRST for session {session_id}")

success = self.labjack_monitor.start_monitoring(
    session_id,
    timing_ready_event=timing_ready_event,  # Event that's never properly waited on
    **labjack_config
)
```

**Problem**:
- LabJack monitoring thread starts immediately
- Hardware begins capturing voltages at T4 = 25ms
- But video doesn't start until T6 = 200-500ms
- **Result**: 175-475ms of detections with WRONG timestamps

### 2.2 Secondary Issue: Incorrect Timestamp Baseline

**Location**: `routers/test_sessions.py:1089-1098`

```python
session.started_at = datetime.utcnow()  # T1 = 10ms
video_playback_start_time = session.started_at.timestamp()  # T2 = 15ms

# This timestamp is assigned BEFORE video actually plays!
session.video_playback_start_time = video_playback_start_time
```

**Problem**:
- `video_playback_start_time` is set to session start time
- Actual video playback starts 200-500ms later
- All relative timestamps calculated from wrong baseline
- **Result**: Negative latencies and timing incoherence

### 2.3 Tertiary Issue: No Video Start Confirmation

**Location**: Video timing service initialization

**Missing**:
- No callback when video ACTUALLY starts playing
- No frame 0 timestamp capture
- No browser-to-server video start notification
- **Result**: Server has no idea when video really begins

---

## 3. Sequence Diagrams

### 3.1 Current (Broken) Sequence

```
┌─────────┐         ┌─────────────┐         ┌──────────┐         ┌─────────┐
│ Client  │         │   Server    │         │ LabJack  │         │  Video  │
└────┬────┘         └──────┬──────┘         └────┬─────┘         └────┬────┘
     │                     │                     │                     │
     │ POST /start         │                     │                     │
     ├────────────────────>│                     │                     │
     │                     │                     │                     │
     │                     │ Set started_at      │                     │
     │                     │ (WRONG baseline!)   │                     │
     │                     │                     │                     │
     │                     │ start_monitoring()  │                     │
     │                     ├────────────────────>│                     │
     │                     │                     │                     │
     │                     │                     │ LED ON (TOO EARLY!) │
     │                     │                     │ Start detecting     │
     │                     │                     ├──────────────┐      │
     │                     │                     │ Detections @ │      │
     │                     │                     │ T=0-200ms    │      │
     │                     │                     │ (WRONG TIME!)│      │
     │                     │                     │              │      │
     │ Video start command │                     │              │      │
     ├─────────────────────┼────────────────────────────────────────> │
     │                     │                     │              │      │
     │                     │                     │              │  Video plays
     │                     │                     │              │  @ T=200ms
     │                     │                     │              │      │
     │                     │                     │<──Detections────────┤
     │                     │                     │ @ T=200-500ms       │
     │                     │                     │ (CORRECT TIME)      │
     │                     │                     │                     │
     │                     │                     │                Video ends
     │                     │                     │                @ T=500ms
     │                     │                     │                     │
     │ POST /complete      │                     │                     │
     ├────────────────────>│                     │                     │
     │                     │ stop_monitoring()   │                     │
     │                     ├────────────────────>│                     │
     │                     │                     │                     │
     │                     │                     │ LED OFF (TOO EARLY!)│
     │                     │                     │ Stop detecting      │
     │                     │                     │                     │
     │                     │ Calculate latencies │                     │
     │                     │ (WRONG - negative!) │                     │
     └─────────┘         └─────────────┘         └───────────┘         └─────────┘
```

**Key Problems**:
1. LabJack LED turns ON at T=25ms, but video starts at T=200ms (175ms early)
2. LabJack LED turns OFF at T=550ms, but video ends at T=500ms (50ms late stop)
3. Timestamps use `started_at` as baseline, not actual video start time
4. Result: Real -6ms latencies (physically impossible)

---

### 3.2 Expected (Correct) Sequence

```
┌─────────┐         ┌─────────────┐         ┌──────────┐         ┌─────────┐
│ Client  │         │   Server    │         │ LabJack  │         │  Video  │
└────┬────┘         └──────┬──────┘         └────┬─────┘         └────┬────┘
     │                     │                     │                     │
     │ POST /start         │                     │                     │
     ├────────────────────>│                     │                     │
     │                     │                     │                     │
     │                     │ Set started_at      │                     │
     │                     │ (command time only) │                     │
     │                     │                     │                     │
     │ Video start command │                     │                     │
     ├─────────────────────┼────────────────────────────────────────> │
     │                     │                     │                     │
     │                     │                     │                Video plays
     │                     │                     │                @ T=200ms
     │                     │                     │                     │
     │ video_started event │                     │                     │
     │ {timestamp: T=200ms}│                     │                     │
     ├────────────────────>│                     │                     │
     │                     │                     │                     │
     │                     │ Capture video_start_time                  │
     │                     │ T1 = 200ms          │                     │
     │                     │                     │                     │
     │                     │ start_monitoring()  │                     │
     │                     │ (NOW synchronized!) │                     │
     │                     ├────────────────────>│                     │
     │                     │                     │                     │
     │                     │                     │ LED ON (CORRECT!)   │
     │                     │                     │ Start detecting     │
     │                     │                     ├──────────────┐      │
     │                     │                     │ Detections @ │      │
     │                     │                     │ T=200-500ms  │      │
     │                     │                     │ (CORRECT!)   │      │
     │                     │                     │              │      │
     │                     │                     │<──Detections────────┤
     │                     │                     │ @ relative time     │
     │                     │                     │ 0ms-300ms (correct!)│
     │                     │                     │                     │
     │                     │                     │                Video ends
     │                     │                     │                @ T=500ms
     │                     │                     │                     │
     │ video_ended event   │                     │                     │
     │ {timestamp: T=500ms}│                     │                     │
     ├────────────────────>│                     │                     │
     │                     │                     │                     │
     │                     │ stop_monitoring()   │                     │
     │                     ├────────────────────>│                     │
     │                     │                     │                     │
     │                     │                     │ LED OFF (CORRECT!)  │
     │                     │                     │ Stop detecting      │
     │                     │                     │                     │
     │                     │ Calculate latencies │                     │
     │                     │ (CORRECT - positive)│                     │
     └─────────┘         └─────────────┘         └───────────┘         └─────────┘
```

**Key Improvements**:
1. LabJack monitoring **waits** for video to actually start
2. Video sends `video_started` event with actual start timestamp
3. LabJack uses video start time as T1 baseline, not session start time
4. LabJack stops monitoring when video ends
5. Result: Positive latencies, synchronized timing

---

## 4. Code Analysis

### 4.1 Test Session Start Endpoint

**File**: `routers/test_sessions.py:1069-1202`

**Issues**:

1. **Wrong timestamp assignment** (Line 1089-1098):
```python
session.started_at = datetime.utcnow()  # Command time
video_playback_start_time = session.started_at.timestamp()  # WRONG!

# This timestamp is set BEFORE video plays
session.video_playback_start_time = video_playback_start_time
```

**Fix Needed**:
```python
# T0: Capture command time only
session.started_at = datetime.utcnow()

# DON'T set video_playback_start_time here - wait for actual video start!
# Video timing service will set this when video actually starts
```

2. **Immediate monitoring start** (Line 1144):
```python
success = await start_hil_monitoring(session_id, video_timing_config)
```

**Fix Needed**:
- Don't start monitoring here
- Wait for `video_started` event from browser
- Then start monitoring with synchronized timestamp

### 4.2 Dedicated LabJack Monitor

**File**: `services/dedicated_labjack_monitor.py:449-698`

**Issues**:

1. **Monitoring starts immediately** (Line 638):
```python
success = self.labjack_monitor.start_monitoring(
    session_id,
    timing_ready_event=timing_ready_event,  # Not properly used
    **labjack_config
)
```

**Analysis**:
- `timing_ready_event` is created but monitoring thread doesn't wait for it
- Monitoring loop starts immediately, capturing detections
- No synchronization with video playback

2. **No video start confirmation** (Line 542-558):
```python
self.active_sessions[session_id] = {
    'video_start_time': None,  # This stays None!
    # ... other fields
}
```

**Analysis**:
- `video_start_time` field exists but is never populated
- No mechanism to capture actual video start timestamp
- Missing integration with video timing service

### 4.3 LabJack Monitoring Service

**File**: `services/labjack_monitoring_service.py:29-80`

**Issues**:

1. **Monitoring loop starts immediately** (Line 81-163):
```python
def _monitor_loop(self, session_id: str):
    # Starts immediately when thread is created
    while self.monitoring_active and not self._stop_event.is_set():
        result = signal_validation_service.read_voltage_signal("AIN0")
        # Process immediately - no wait for video timing
```

**Analysis**:
- No synchronization primitives
- Begins detecting immediately on thread start
- Cannot be paused waiting for video timing

---

## 5. Timing Synchronization Requirements

### 5.1 Timestamp Definitions

| Timestamp | Definition | When Captured | Purpose |
|-----------|-----------|---------------|---------|
| **T0** | Command timestamp | When POST /start called | Test initiation tracking |
| **T1** | Video start timestamp | When video frame 0 displays | Baseline for all detection timing |
| **T-detection** | Detection timestamp | When LabJack sees voltage edge | Hardware event time |
| **T-relative** | Relative timestamp | T-detection - T1 | Time since video started |
| **Latency** | Detection latency | T-detection - T-ground-truth | Real model latency |

### 5.2 Synchronization Points

1. **Session Initialization**:
   - Capture T0 (command time)
   - Store session metadata
   - **DO NOT start monitoring yet**

2. **Video Start Event**:
   - Browser emits `video_started` event
   - Server captures T1 (actual video start)
   - **NOW start LabJack monitoring**
   - Use T1 as baseline for all timestamps

3. **Detection Capture**:
   - LabJack detects voltage edge
   - Calculate T-relative = T-detection - T1
   - Store with correct relative timestamp

4. **Video End Event**:
   - Browser emits `video_ended` event
   - Server stops LabJack monitoring
   - Process final detection timestamps

---

## 6. Recommended Fixes

### 6.1 High-Level Architecture Changes

```
CURRENT FLOW:
POST /start → Set timestamps → Start monitoring → Send video command → Video plays (200ms later)
                                ↑ TOO EARLY!

CORRECT FLOW:
POST /start → Set T0 → Send video command → Video plays → video_started event → Capture T1 → Start monitoring
                                                              ↑ WAIT FOR THIS!
```

### 6.2 Implementation Changes

#### Change 1: Remove premature timestamp assignment

**File**: `routers/test_sessions.py:1089-1098`

```python
# BEFORE (WRONG):
session.started_at = datetime.utcnow()
video_playback_start_time = session.started_at.timestamp()
session.video_playback_start_time = video_playback_start_time

# AFTER (CORRECT):
# Only capture command time (T0)
session.started_at = datetime.utcnow()

# DON'T set video_playback_start_time here!
# Will be set by video timing service when video actually starts
```

#### Change 2: Defer monitoring start

**File**: `routers/test_sessions.py:1144`

```python
# BEFORE (WRONG):
success = await start_hil_monitoring(session_id, video_timing_config)
# This starts monitoring IMMEDIATELY

# AFTER (CORRECT):
# Store config for later use
session.hil_config = video_timing_config

# DON'T start monitoring yet - wait for video_started event
# Monitoring will be started by video lifecycle handler
```

#### Change 3: Add video_started event handler

**File**: `routers/video_sequences.py` or new `video_lifecycle_api.py`

```python
@router.post("/api/video-lifecycle/{session_id}/started")
async def handle_video_started(
    session_id: str,
    video_start_data: VideoStartedEvent,
    db: Session = Depends(get_db)
):
    """
    Handle video_started event from browser.
    This is the CORRECT time to start LabJack monitoring.
    """
    # 1. Capture T1 (actual video start time)
    video_start_timestamp = video_start_data.timestamp  # From browser

    # 2. Store T1 in session
    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    session.video_playback_start_time = video_start_timestamp
    session.video_playback_start_time_ns = str(int(video_start_timestamp * 1e9))
    db.commit()

    # 3. NOW start LabJack monitoring (synchronized with video)
    hil_config = session.hil_config
    hil_config['video_start_timestamp'] = video_start_timestamp

    success = await start_hil_monitoring(session_id, hil_config)

    return {
        "success": success,
        "video_start_timestamp": video_start_timestamp,
        "monitoring_started": success
    }
```

#### Change 4: Update LabJack monitor to use T1 baseline

**File**: `services/dedicated_labjack_monitor.py:_handle_detection_with_video_sync`

```python
def _handle_detection_with_video_sync(self, session_id: str, event: DetectionEvent):
    """Calculate relative timestamp using video start time as baseline"""

    # Get video start time (T1) from session
    session_data = self.active_sessions.get(session_id)
    video_start_time = session_data.get('video_start_time')

    if not video_start_time:
        logger.error(f"No video start time for session {session_id}")
        return

    # Calculate relative timestamp: T-relative = T-detection - T1
    detection_timestamp = event.timestamp  # T-detection
    relative_timestamp = detection_timestamp - video_start_time  # Correct!

    # Store with correct relative timestamp
    event.video_relative_timestamp = relative_timestamp
    event.video_playback_start_time = video_start_time
```

#### Change 5: Add video_ended event handler

**File**: Same as Change 3

```python
@router.post("/api/video-lifecycle/{session_id}/ended")
async def handle_video_ended(
    session_id: str,
    video_end_data: VideoEndedEvent,
    db: Session = Depends(get_db)
):
    """
    Handle video_ended event from browser.
    This is the CORRECT time to stop LabJack monitoring.
    """
    # Stop monitoring NOW (synchronized with video end)
    await stop_hil_monitoring(session_id)

    return {
        "success": True,
        "monitoring_stopped": True
    }
```

---

## 7. Testing Plan

### 7.1 Unit Tests

```python
def test_video_start_timestamp_capture():
    """Verify T1 is captured from video_started event, not session start"""
    session = create_test_session()

    # Session start should NOT set video_playback_start_time
    assert session.video_playback_start_time is None

    # Simulate video_started event 200ms later
    time.sleep(0.2)
    video_start_time = time.time()
    handle_video_started(session.id, VideoStartedEvent(timestamp=video_start_time))

    # NOW video_playback_start_time should be set
    session = get_session(session.id)
    assert session.video_playback_start_time == video_start_time
    assert abs(session.video_playback_start_time - session.started_at.timestamp()) > 0.15  # At least 150ms difference

def test_labjack_monitoring_waits_for_video():
    """Verify LabJack monitoring doesn't start until video_started event"""
    session = create_test_session()
    start_test_session(session.id)

    # Monitoring should NOT be active yet
    assert not is_monitoring_active(session.id)

    # Simulate video_started event
    handle_video_started(session.id, VideoStartedEvent(timestamp=time.time()))

    # NOW monitoring should be active
    assert is_monitoring_active(session.id)
```

### 7.2 Integration Tests

```python
def test_end_to_end_timing_synchronization():
    """Full HIL test with verified timing synchronization"""
    # 1. Create session and start test
    session = create_test_session()
    response = client.post(f"/api/test-sessions/{session.id}/start")
    t0 = time.time()

    # 2. Simulate browser video start (200ms delay)
    time.sleep(0.2)
    t1 = time.time()
    client.post(f"/api/video-lifecycle/{session.id}/started",
                json={"timestamp": t1})

    # 3. Verify monitoring started AFTER video
    assert t1 - t0 > 0.15  # At least 150ms delay

    # 4. Verify timestamps are relative to T1, not T0
    detections = get_detections(session.id)
    for detection in detections:
        assert detection.video_relative_timestamp >= 0  # No negative timestamps!
        assert detection.video_relative_timestamp < (time.time() - t1)  # Relative to T1
```

### 7.3 Hardware Validation

```python
def test_physical_led_timing():
    """Verify physical LED turns on AFTER video starts"""
    # 1. Start test session
    session = create_test_session()
    client.post(f"/api/test-sessions/{session.id}/start")

    # 2. Verify LED is still OFF
    time.sleep(0.05)
    assert not is_led_on()  # LED should be OFF before video starts

    # 3. Start video
    t1 = time.time()
    client.post(f"/api/video-lifecycle/{session.id}/started",
                json={"timestamp": t1})

    # 4. NOW LED should turn ON
    time.sleep(0.05)
    assert is_led_on()  # LED should be ON after video starts

    # 5. Verify LED timing matches video timing
    led_on_time = get_led_on_timestamp()
    assert abs(led_on_time - t1) < 0.1  # Within 100ms of video start
```

---

## 8. Success Criteria

### 8.1 Functional Requirements

- [ ] LabJack LED turns ON **after** video starts playing (not before)
- [ ] LabJack LED turns OFF **after** video stops playing (not before)
- [ ] All latency values are **positive** (no negative values)
- [ ] Timeline shows correct sequence: Video Start → Monitoring Start → Detections
- [ ] `video_playback_start_time` matches actual browser video start time

### 8.2 Timing Requirements

- [ ] Video start to monitoring start delay: < 100ms
- [ ] Timestamp baseline accuracy: ±10ms
- [ ] Detection timestamp accuracy: ±1ms (LabJack T7 resolution)
- [ ] End-to-end timing drift: < 50ms over 60-second video

### 8.3 Data Integrity Requirements

- [ ] All detection events have `video_relative_timestamp >= 0`
- [ ] `video_playback_start_time` is populated for all sessions
- [ ] Detection timestamps relative to video start, not session start
- [ ] Ground truth matching uses video-relative timestamps

---

## 9. Migration Path

### 9.1 Phase 1: Backend Changes (1-2 days)

1. Update `test_sessions.py` to remove premature timestamp assignment
2. Update `dedicated_labjack_monitor.py` to use T1 baseline
3. Add video lifecycle event handlers
4. Add video timing synchronization service

### 9.2 Phase 2: Frontend Changes (1 day)

1. Add `video_started` event emission from video player
2. Add `video_ended` event emission from video player
3. Include high-precision timestamp in events

### 9.3 Phase 3: Testing & Validation (2-3 days)

1. Unit tests for timing synchronization
2. Integration tests for end-to-end flow
3. Hardware validation with physical LED verification
4. Performance testing under load

### 9.4 Phase 4: Deployment (1 day)

1. Database migration for new timestamp fields
2. Deploy backend changes
3. Deploy frontend changes
4. Monitor production timing for 24 hours

**Total Estimated Time**: 5-7 days

---

## 10. Conclusion

The root cause of the HIL timing desynchronization is **premature LabJack monitoring start**. The system starts monitoring immediately when `/start` is called, but video playback doesn't begin until 200-500ms later. This creates a timing window where:

1. LabJack detections occur before video starts (early LED activation)
2. Timestamps use wrong baseline (session start instead of video start)
3. Latency calculations produce negative values (physically impossible)

The solution is to **defer LabJack monitoring until video actually starts** by:
1. Waiting for `video_started` event from browser
2. Using video start timestamp as T1 baseline
3. Starting monitoring only after T1 is established

This architectural change will synchronize hardware detection timing with video playback timing, producing accurate latency measurements and enabling proper HIL validation.

---

## Appendix A: Key Files Requiring Changes

| File | Change Type | Priority |
|------|-------------|----------|
| `routers/test_sessions.py` | Modify timestamp assignment | HIGH |
| `services/dedicated_labjack_monitor.py` | Add T1 baseline support | HIGH |
| `routers/video_lifecycle_api.py` | Create new file | HIGH |
| `services/video_timing_service.py` | Enhance sync support | MEDIUM |
| `services/labjack_monitoring_service.py` | Add sync primitives | MEDIUM |
| Frontend video player | Add lifecycle events | HIGH |

---

## Appendix B: Configuration Changes

Add to `.env`:
```bash
# Video timing synchronization
VIDEO_TIMING_SYNC_ENABLED=true
VIDEO_TIMING_SYNC_TIMEOUT_MS=5000
VIDEO_LIFECYCLE_EVENTS_ENABLED=true

# LabJack monitoring synchronization
LABJACK_WAIT_FOR_VIDEO_START=true
LABJACK_VIDEO_SYNC_TIMEOUT_MS=10000
```

---

**Prepared by**: System Architecture Analysis
**Reviewers**: [To be assigned]
**Status**: Draft - Awaiting Review
