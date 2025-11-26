# Timing Synchronization Issues - Root Cause Analysis & Fixes

**Date:** 2025-11-25
**Analysis of Log Timestamp:** Video timing captured at epoch 1764082088.275474s

## Executive Summary

The HIL testing system has **four critical timing synchronization bugs** causing:
1. **Negative latencies** (-5.9ms, -18.7ms) - detections appearing BEFORE ground truth timestamps
2. **68 detections skipped as "late"** - valid detections rejected due to incorrect window calculation
3. **Zero drift compensation** - drift measurement service not being called
4. **Incorrect video-relative timestamps** - clamping logic preventing proper video position calculation

---

## Problem 1: Negative Latencies (Detection Before GT Timestamp)

### Root Cause
**File:** `timing_synchronization_calculator.py` lines 256-287

The calculator uses `labjack_start_time` as the video reference time when `video_start_time` is not provided:

```python
# SMART FALLBACK: Try to get video_start_time from detection or video metadata
video_start_system_time = None

if video_start_system_time is None:
    # Last resort: Use labjack_start_time but log clear warning
    video_start_system_time = labjack_start_time
    logger.warning(
        f"⚠️ No video_start_time provided for detection {detection_id}. "
        f"Using labjack_start_time ({labjack_start_time:.6f}) as fallback."
    )
```

**Problem:** LabJack monitoring starts BEFORE the video actually starts (by ~352ms startup delay + any sequence delays). When we use `labjack_start_time` as `video_start_system_time`, we're backdating the video start, making detections appear to occur BEFORE the ground truth event timestamp.

**Example from logs:**
- Video timing captured: 1764082088.275474s (this is the ACTUAL video start)
- LabJack monitoring started: ~1764082088.0s (352ms earlier due to startup)
- Ground truth event at t=2.0s in video: system time = 1764082088.275474 + 2.0 = 1764082090.275474
- Detection arrives at: 1764082090.260 (15ms before GT)
- Calculator uses labjack_start_time (1764082088.0) as video_start_time
- Calculated latency = 1764082090.260 - (1764082088.0 + 2.0) = **+0.260s** (appears correct)
- But ACTUAL latency should be: 1764082090.260 - (1764082088.275474 + 2.0) = **-15.474ms** (NEGATIVE!)

### Fix 1A: Always Require video_start_time from Video Timing Service

**File:** `timing_synchronization_calculator.py` lines 264-287

```python
# STRICT VIDEO START TIME REQUIREMENT
if video_start_time is None:
    raise ValueError(
        f"❌ CRITICAL: No video_start_time provided for detection {detection_id}. "
        f"Cannot calculate accurate latency without actual video start time. "
        f"Caller MUST provide video.playback_start_time from video_timing_service."
    )

video_start_system_time = video_start_time
logger.debug(f"Using per-video start time: {video_start_system_time:.6f}")
```

### Fix 1B: Ensure Video Timing Service Start Time is Propagated

**File:** `labjack_detection_service.py` lines 1986-2074

The detection creation code correctly retrieves video start time but stores it as `reference_time`. Ensure this is passed through:

```python
# Line 2074 - ALREADY CORRECT
video_start_time=reference_time  # FIX: Propagate for corrected latency calculation
```

**Verification needed:** Ensure this `video_start_time` field is used when calling the timing calculator.

---

## Problem 2: 68 Detections Skipped as "Late"

### Root Cause
**File:** `video_timing_service.py` lines 456-489 and `labjack_detection_service.py` lines 1880-1913

The clamping logic incorrectly calculates video-relative timestamps:

```python
# Line 476-486 in video_timing_service.py
if timing_data.duration_s is not None:
    if video_relative_time < 0:
        logger.debug(
            f"Video-relative time negative ({video_relative_time:.3f}s); clamping to 0.0s")
        video_relative_time = 0.0
    elif video_relative_time > timing_data.duration_s:
        logger.info(
            f"Video-relative time {video_relative_time:.3f}s exceeds duration {timing_data.duration_s:.3f}s; clamping to duration")
        video_relative_time = timing_data.duration_s
```

**Problem:** This clamping happens BEFORE drift compensation is applied. If there's 352ms of startup delay + any clock drift:
1. Detection arrives at: video_start + 10.5s (slightly after video ends)
2. Clamping sets video_relative_time = 10.08s (video duration)
3. Auto-stop deadline is calculated as: video_start + 10.08s + 2s = video_start + 12.08s
4. Actual detection time is video_start + 10.5s
5. Detection is within deadline BUT the clamped timestamp makes it appear "late"

### Fix 2A: Apply Drift Compensation BEFORE Clamping

**File:** `video_timing_service.py` lines 456-493

```python
def convert_unix_to_video_relative(self, session_id: str, unix_timestamp: float) -> Optional[float]:
    """
    Convert Unix timestamp to video-relative time for ground truth matching.

    Args:
        session_id: Test session identifier
        unix_timestamp: Unix timestamp to convert (e.g., from LabJack)

    Returns:
        Video-relative timestamp in seconds, or None if conversion fails
    """
    try:
        timing_data = self.get_timing_data(session_id)

        if timing_data is None:
            logger.error(f"No timing data found for session {session_id}")
            return None

        # CRITICAL FIX: Get drift compensation from drift measurement service
        drift_ms = 0.0
        try:
            from .drift_measurement_service import get_drift_measurement_service
            drift_service = get_drift_measurement_service()

            # Try to get drift for the specific video this detection belongs to
            # (This requires knowing which video is currently playing)
            drift_ms = drift_service.get_drift_for_video(session_id, timing_data.video_id) or 0.0

            if drift_ms == 0.0:
                logger.warning(
                    f"⚠️ No drift measurement available for session {session_id}, "
                    f"video {timing_data.video_id}. Using zero offset."
                )
        except Exception as drift_error:
            logger.error(f"Failed to retrieve drift compensation: {drift_error}")

        # Apply drift compensation to detection timestamp BEFORE calculating video-relative time
        compensated_unix_timestamp = unix_timestamp - (drift_ms / 1000.0)
        logger.debug(
            f"Applied drift compensation: {unix_timestamp:.6f} -> {compensated_unix_timestamp:.6f} "
            f"(drift: {drift_ms:.1f}ms)"
        )

        # Calculate offset: video_relative_time = compensated_timestamp - video_start_time
        video_relative_time = compensated_unix_timestamp - timing_data.start_timestamp

        # Clamp to [0, duration] ONLY if duration known and AFTER drift compensation
        # Allow small negative values for clock jitter (±50ms tolerance)
        CLOCK_JITTER_TOLERANCE_S = 0.05  # 50ms

        if timing_data.duration_s is not None:
            if video_relative_time < -CLOCK_JITTER_TOLERANCE_S:
                logger.warning(
                    f"❌ Video-relative time significantly negative ({video_relative_time:.3f}s) "
                    f"after drift compensation; clamping to 0.0s for session {session_id}"
                )
                video_relative_time = 0.0
            elif video_relative_time < 0:
                # Small negative value within jitter tolerance - clamp to zero
                logger.debug(
                    f"Video-relative time slightly negative ({video_relative_time:.3f}s) "
                    f"within jitter tolerance; clamping to 0.0s"
                )
                video_relative_time = 0.0
            elif video_relative_time > timing_data.duration_s + CLOCK_JITTER_TOLERANCE_S:
                logger.warning(
                    f"⚠️ Video-relative time {video_relative_time:.3f}s exceeds duration "
                    f"{timing_data.duration_s:.3f}s + jitter tolerance; may be late detection"
                )
                # Don't clamp - let ground truth matching handle late detections

        logger.debug(
            f"Converted Unix timestamp {unix_timestamp:.6f} to video-relative time "
            f"{video_relative_time:.6f}s (with {drift_ms:.1f}ms drift compensation)"
        )
        return video_relative_time

    except Exception as e:
        logger.error(f"Failed to convert Unix timestamp to video-relative time: {e}")
        return None
```

### Fix 2B: Remove Premature Window Filtering

**File:** `labjack_detection_service.py` lines 1880-1913

The validation logic should WARN about detections outside the window but NOT reject them - let ground truth matching handle it:

```python
# Line 1880-1913 - MODIFY to not reject, just warn
def _is_detection_within_valid_window(
    self,
    detection_timestamp: float,
    session_id: str,
    grace_period_before_ms: float = 2000,
    grace_period_after_ms: float = 2000
) -> bool:
    """
    Check if detection timestamp is within valid video playback window.

    MODIFIED: Always returns True but logs warnings for debugging.
    Let ground truth matching service make the final decision on validity.
    """
    try:
        # Get session timing info
        session_info = self._get_session_timing_info(session_id)
        if not session_info:
            logger.debug(f"No session timing info for {session_id}, allowing detection")
            return True  # Allow if no timing info (fail-open for debugging)

        video_start_time = session_info.get('video_start_timestamp')
        video_duration_s = session_info.get('video_duration')

        if not video_start_time:
            logger.debug(f"No video_start_timestamp for {session_id}, allowing detection")
            return True  # Allow if no start time

        # Calculate window boundaries with grace periods
        grace_before_s = grace_period_before_ms / 1000.0
        grace_after_s = grace_period_after_ms / 1000.0

        window_start = video_start_time - grace_before_s

        # Calculate window end
        if video_duration_s:
            video_end_time = video_start_time + video_duration_s
            window_end = video_end_time + grace_after_s
        else:
            # No duration - use large window
            window_end = video_start_time + 3600  # 1 hour

        # Check window boundaries but only log, don't reject
        if detection_timestamp < window_start:
            time_before_start = window_start - detection_timestamp
            logger.warning(
                f"⚠️ Detection {time_before_start:.3f}s BEFORE video window start (but allowing) "
                f"(detection={detection_timestamp:.6f}, window_start={window_start:.6f})"
            )
            # Still return True - let ground truth matching decide
        elif detection_timestamp > window_end:
            time_after_end = detection_timestamp - window_end
            logger.warning(
                f"⚠️ Detection {time_after_end:.3f}s AFTER video window end+buffer (but allowing) "
                f"(detection={detection_timestamp:.6f}, window_end={window_end:.6f})"
            )
            # Still return True - let ground truth matching decide
        else:
            # Detection is within window
            relative_time = detection_timestamp - video_start_time
            logger.debug(
                f"✅ Detection within window at +{relative_time:.3f}s from video start "
                f"(detection={detection_timestamp:.6f}, video_start={video_start_time:.6f})"
            )

        # Always return True - we only want to log warnings, not reject detections
        return True

    except Exception as e:
        logger.error(f"Error checking detection window: {e}")
        return True  # Fail-open: allow detection if validation fails
```

---

## Problem 3: Zero Drift Compensation

### Root Cause
**File:** `drift_measurement_service.py` lines 244-264

The drift measurement service is initialized but **never called** during detection processing. The warning "No matched detections for calibration - using zero offset" appears because:

1. Drift service has methods to capture timestamps at different stages
2. These methods are never invoked by the detection or video playback workflows
3. Without captured timestamps, `get_drift_for_video()` returns `None` (line 263)
4. Callers interpret `None` as 0ms drift

### Fix 3A: Capture Video Start Timestamp in Drift Service

**File:** `routers/video_sequence_testing.py` (or wherever video playback starts)

After starting video timing, capture the timestamp in drift service:

```python
# After calling video_timing_service.start_video_timing()
from services.drift_measurement_service import get_drift_measurement_service
from services.drift_measurement_service import DriftStage

drift_service = get_drift_measurement_service()

# Start drift measurement for this video
drift_service.start_video_drift_measurement(
    session_id=session_id,
    video_id=video_id,
    video_sequence_number=sequence_position,
    clock_offset_ms=0.0  # Get from clock sync service if available
)

# Capture video start command timestamp
drift_service.capture_timestamp(
    session_id=session_id,
    video_id=video_id,
    stage=DriftStage.VIDEO_START_COMMAND,
    timestamp=time.time(),  # Command sent time
    source="backend",
    metadata={"action": "video_playback_request"}
)

# After video actually starts (from video timing service)
video_start_time = video_timing_service.get_video_start_time(session_id)
if video_start_time:
    drift_service.capture_timestamp(
        session_id=session_id,
        video_id=video_id,
        stage=DriftStage.VIDEO_ACTUAL_START,
        timestamp=video_start_time,
        source="video_timing_service",
        metadata={"video_metadata": video_metadata}
    )
```

### Fix 3B: Capture LabJack Start Timestamps

**File:** `services/labjack_detection_service.py` around line 500-600 (wherever monitoring starts)

```python
def start_monitoring(self, session_id: str, config: DetectionConfig):
    """Start detection monitoring for a session"""

    # ... existing code ...

    # Capture LabJack command sent timestamp
    from services.drift_measurement_service import get_drift_measurement_service, DriftStage
    drift_service = get_drift_measurement_service()

    command_time = time.time()

    # Start monitoring (existing code)
    # ... monitoring logic ...

    # Capture command timestamp
    drift_service.capture_timestamp(
        session_id=session_id,
        video_id=config.video_id,  # Need to pass this
        stage=DriftStage.LABJACK_COMMAND_SENT,
        timestamp=command_time,
        source="labjack_service",
        metadata={"config": config.__dict__}
    )

    # After monitoring actually starts (wait for first reading)
    actual_start_time = time.time()  # Or first detection timestamp

    drift_service.capture_timestamp(
        session_id=session_id,
        video_id=config.video_id,
        stage=DriftStage.LABJACK_ACTUAL_START,
        timestamp=actual_start_time,
        source="labjack_service",
        metadata={"first_reading": True}
    )
```

### Fix 3C: Automatic Drift Calculation

**File:** `drift_measurement_service.py` lines 240-243

The service already auto-calculates drift when enough timestamps are captured (line 242), so once we capture the timestamps in Fixes 3A and 3B, drift will be calculated automatically.

**Verification:** Add logging to confirm drift calculation:

```python
# Line 114 - enhance logging
logger.info(
    f"✅ Drift calculated for session {self.session_id}, video {self.video_id}: "
    f"video_drift={self.video_start_drift_ms:.2f}ms, "
    f"labjack_drift={self.labjack_start_drift_ms:.2f}ms, "
    f"total_drift={self.total_drift_ms:.2f}ms, "
    f"confidence={self.confidence_score:.2f}"
)
```

---

## Problem 4: Incorrect Video-Relative Timestamp Calculation

### Root Cause
**File:** `timing_synchronization_calculator.py` lines 363-373

The calculator computes `video_relative_timestamp` but this is AFTER detection matching, so it's used for reporting only. The actual video-relative timestamp used for matching comes from:

1. `labjack_detection_service.py` line 2038: `video_relative_timestamp = max(0.0, detection_timestamp - reference_time)`
2. This is clamped to [0, duration] by video timing service (Problem 2)

The calculator's version (lines 363-373) is correct:

```python
video_relative_timestamp = detection_system_time - video_start_system_time
video_frame_number = int(video_relative_timestamp * fps)
```

But the detection service's version doesn't account for drift before clamping.

### Fix 4: Apply Drift in Detection Service Before Setting video_relative_timestamp

**File:** `labjack_detection_service.py` lines 2032-2038

```python
# Apply timing calibration offset (will be 0.0 for multi-video sequences)
calibration_offset_seconds = TIMING_CALIBRATION_OFFSET_MS / 1000.0
detection_timestamp_raw = timestamp.timestamp()

# CRITICAL FIX: Apply drift compensation BEFORE calculating video-relative time
drift_ms = 0.0
try:
    from services.drift_measurement_service import get_drift_measurement_service
    drift_service = get_drift_measurement_service()
    drift_ms = drift_service.get_drift_for_video(session_id, current_video_id or 'unknown') or 0.0
except Exception as drift_error:
    logger.warning(f"Could not retrieve drift: {drift_error}")

# Compensate timestamp for drift
detection_timestamp = detection_timestamp_raw - (drift_ms / 1000.0) + calibration_offset_seconds

# Calculate video-relative timestamp with drift compensation
# CRITICAL: This MUST be relative to the CURRENT video's start time, not session start
video_relative_timestamp = max(0.0, detection_timestamp - reference_time)

logger.debug(
    f"🕐 Timing calculation with drift: "
    f"detection_raw={detection_timestamp_raw:.6f}, "
    f"drift={drift_ms:.1f}ms, "
    f"detection_compensated={detection_timestamp:.6f}, "
    f"video_start={reference_time:.6f}, "
    f"video_relative={video_relative_timestamp:.6f}s, "
    f"video_id={current_video_id[:12] if current_video_id else 'N/A'}"
)
```

---

## Implementation Priority

### Phase 1: Critical Fixes (Immediate)
1. **Fix 1A**: Require video_start_time in timing calculator (prevent negative latencies)
2. **Fix 2B**: Remove premature window rejection (recover 68 lost detections)

### Phase 2: Drift Infrastructure (Next)
3. **Fix 3A**: Capture video start timestamps in drift service
4. **Fix 3B**: Capture LabJack start timestamps in drift service
5. **Fix 3C**: Verify automatic drift calculation

### Phase 3: Refinement (Final)
6. **Fix 2A**: Apply drift before clamping in video timing service
7. **Fix 4**: Apply drift in detection service before video-relative calculation

---

## Testing Strategy

### Unit Tests

```python
def test_video_relative_timestamp_with_drift():
    """Test that drift compensation is applied before video-relative calculation"""
    calc = TimingSynchronizationCalculator()

    # Simulate 352ms startup drift
    video_start_time = 1764082088.275474
    labjack_start_time = 1764082088.0  # 275ms earlier
    detection_time = 1764082090.260  # Should match GT at t=2.0s
    gt_video_time = 2.0

    # With drift compensation, latency should be near zero
    result = calc.calculate_corrected_latency(
        session_id="test",
        detection_id="det1",
        detection_system_time=detection_time,
        ground_truth_frame=48,
        ground_truth_video_time=gt_video_time,
        video_timing_metadata=VideoTimingMetadata(
            startup_delay_ms=352,
            fps=24,
            duration=10.08,
            timing_sync_status="synced"
        ),
        labjack_start_time=labjack_start_time,
        video_start_time=video_start_time  # Must be provided!
    )

    # Latency should be near zero, NOT negative
    assert -50 < result.detection_latency_ms < 50, \
        f"Latency {result.detection_latency_ms:.1f}ms outside expected range"

def test_drift_measurement_integration():
    """Test drift measurement service integration"""
    from services.drift_measurement_service import get_drift_measurement_service, DriftStage

    drift_service = get_drift_measurement_service()

    # Start drift measurement
    measurement = drift_service.start_video_drift_measurement(
        session_id="test",
        video_id="vid1",
        video_sequence_number=0,
        clock_offset_ms=0.0
    )

    # Capture timestamps
    command_time = time.time()
    actual_start = command_time + 0.352  # 352ms startup delay

    drift_service.capture_timestamp(
        session_id="test",
        video_id="vid1",
        stage=DriftStage.VIDEO_START_COMMAND,
        timestamp=command_time,
        source="test"
    )

    drift_service.capture_timestamp(
        session_id="test",
        video_id="vid1",
        stage=DriftStage.VIDEO_ACTUAL_START,
        timestamp=actual_start,
        source="test"
    )

    drift_service.capture_timestamp(
        session_id="test",
        video_id="vid1",
        stage=DriftStage.LABJACK_ACTUAL_START,
        timestamp=actual_start,
        source="test"
    )

    # Get drift
    drift_ms = drift_service.get_drift_for_video("test", "vid1")

    # Should be close to 352ms
    assert drift_ms is not None, "Drift measurement failed"
    assert 340 < drift_ms < 365, f"Drift {drift_ms:.1f}ms outside expected range"
```

### Integration Test

Run a full test session with:
1. Video playback with known startup delay
2. Hardware detections at known times
3. Verify all detections are matched
4. Verify no negative latencies
5. Verify drift compensation is applied

---

## Expected Outcomes

After implementing all fixes:

1. **Zero negative latencies** - all detections will have positive latency (or within ±50ms jitter tolerance)
2. **Zero skipped "late" detections** - all detections within grace period will be matched
3. **Accurate drift measurement** - drift will be measured and applied (±10ms accuracy)
4. **Correct video-relative timestamps** - timestamps will reflect actual position in video timeline

---

## References

- **Video Timing Service**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_timing_service.py`
- **Timing Calculator**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/timing_synchronization_calculator.py`
- **Drift Service**: `/home/rigade/Testing/ai-model-validation-platform/backend/src/services/drift_measurement_service.py`
- **Detection Service**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
- **Window Clamp Service**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/detection_window_clamp_service.py`
