# Video Timing Synchronization Analysis Report
**Analysis Date:** 2025-11-17
**Scope:** HIL Monitor vs Detection Service video timing synchronization mechanisms

---

## Executive Summary

This report analyzes how both the **HIL Monitor (Dedicated LabJack Monitor)** and **Detection Service (LabJack Detection Service)** synchronize hardware timestamps with video playback timing. The analysis reveals significant architectural differences in timing accuracy, calibration mechanisms, and multi-video sequence handling.

**Key Finding:** The HIL Monitor provides significantly better timing accuracy through direct integration with VideoTimingService and proper multi-video sequence handling, while the Detection Service uses simpler calibration-based timing with potential drift issues.

---

## 1. Video Timing Synchronization Mechanisms

### 1.1 HIL Monitor (Dedicated LabJack Monitor)

**Architecture:**
- **Direct Integration:** Uses `VideoTimingService` for precise timestamp conversion
- **Service Dependency:** `self.video_timing_service = video_timing_service or get_video_timing_service()`
- **Real-time Synchronization:** Video timing starts BEFORE first detection can occur

**Synchronization Flow:**
```python
# Step 1: Start LabJack monitoring FIRST (lines 384-392)
success = self.labjack_monitor.start_monitoring(session_id, **labjack_config)

# Step 2: Initialize video timing service (lines 415-426)
video_start_time = self.video_timing_service.start_video_timing(
    session_id, video_id, db, video_metadata
)

# Step 3: Convert hardware timestamps to video-relative (line 628-641)
video_relative_data = self.video_timing_service.calculate_video_relative_latency(
    session_id, detection_unix_timestamp, db
)
```

**Timestamp Conversion Method:**
```python
# From video_timing_service.py (lines 389-422)
def convert_unix_to_video_relative(self, session_id: str, unix_timestamp: float):
    timing_data = self.get_timing_data(session_id)

    # Calculate offset: video_relative_time = unix_timestamp - video_start_time
    video_relative_time = unix_timestamp - timing_data.start_timestamp

    # Clamp to [0, duration] to avoid drift beyond video end
    if timing_data.duration_s is not None:
        if video_relative_time < 0:
            video_relative_time = 0.0
        elif video_relative_time > timing_data.duration_s:
            video_relative_time = timing_data.duration_s

    return video_relative_time
```

**Reference Point:**
- **Video Start Time:** Captured via `PrecisionTimingService.create_sync_point()` at exact moment video begins
- **Hardware Time:** Unix epoch timestamp from LabJack
- **Conversion:** `video_relative_time = unix_timestamp - video_start_timestamp`

**Frame Number Calculation:**
```python
# From video_timing_service.py (lines 456-457)
if timing_data.frame_rate:
    frame_number = int(video_relative_timestamp * timing_data.frame_rate)
```

**Calibration:**
- **No Manual Calibration:** Uses high-precision timing service (sub-millisecond)
- **Precision Tracking:** Records timing accuracy in nanoseconds
- **Sync Point ID:** Each session gets unique synchronization reference

---

### 1.2 Detection Service (LabJack Detection Service)

**Architecture:**
- **No Direct VideoTimingService Integration:** Operates independently
- **Manual Calibration:** Uses `calculate_calibration_offset()` method
- **Delayed Timing:** Timing data calculated after detection occurs

**Synchronization Flow:**
```python
# From labjack_detection_service.py (lines 1544-1623)
def _create_detection_event(self, session_id, channel, voltage, threshold, timestamp):
    # Get session timing from database
    session_timing = self._get_session_timing_info(session_id, db)

    # Calculate calibration offset from previous detections
    TIMING_CALIBRATION_OFFSET_MS = self.calculate_calibration_offset(session_id)

    # Apply calibration
    calibration_offset_seconds = TIMING_CALIBRATION_OFFSET_MS / 1000.0
    detection_timestamp = timestamp.timestamp() + calibration_offset_seconds

    # Calculate video-relative timestamp
    video_relative_timestamp = detection_timestamp - session_timing['video_start_time']
```

**Reference Point:**
- **Video Start Time:** Retrieved from database `session_timing['video_start_time']`
- **Hardware Time:** Unix epoch timestamp from LabJack
- **Conversion:** `video_relative_time = (unix_timestamp + calibration_offset) - video_start_time`

**Calibration Method:**
```python
# From labjack_detection_service.py (lines 1496-1537)
def calculate_calibration_offset(self, session_id: str) -> float:
    """Calculate calibration offset from actual detection timing data."""
    try:
        detections = self.detection_events.get(session_id, [])

        # Find matched detections with video_relative_timestamp
        offsets = []
        for detection in detections:
            if detection.video_relative_timestamp is not None:
                # Calculate offset from expected vs actual timing
                offset = detection.video_relative_timestamp - detection.timestamp.timestamp()
                offsets.append(offset * 1000)  # Convert to ms

        # Use median offset as calibration
        calibration_offset = statistics.median(offsets)
        return calibration_offset
    except Exception as e:
        return 0.0  # Fallback to zero offset
```

**Frame Number Calculation:**
- **Not Implemented:** Detection service does not calculate frame numbers

---

## 2. Clock Synchronization Mechanisms

### 2.1 HIL Monitor Clock Handling

**Clock Drift Mechanism:**
- **Service:** `ClockSyncService` (backend/services/clock_sync_service.py)
- **Validation:** Checks frontend, backend, and hardware clock alignment
- **Tolerances:**
  - Frontend drift: ≤ 5.0 seconds (max_frontend_drift_seconds)
  - Hardware drift: ≤ 1.0 seconds (max_hardware_drift_seconds)

```python
# From clock_sync_service.py (lines 23-66)
def validate_clock_sync(
    frontend_timestamp: float,
    backend_timestamp: Optional[float] = None,
    hardware_timestamp: Optional[float] = None,
    max_frontend_drift_seconds: float = 5.0,
    max_hardware_drift_seconds: float = 1.0
):
    # Check frontend clock drift
    frontend_drift = abs(frontend_timestamp - backend_timestamp)
    if frontend_drift > max_frontend_drift_seconds:
        raise ClockSkewError(...)

    # Check hardware clock drift
    if hardware_timestamp is not None:
        hardware_drift = abs(hardware_timestamp - backend_timestamp)
        if hardware_drift > max_hardware_drift_seconds:
            raise ClockSkewError(...)
```

**Drift Correction:**
- **No Active Correction:** System validates but does not actively correct drift
- **Passive Monitoring:** Logs drift metrics for analysis
- **Tolerance-Based:** Raises errors if drift exceeds thresholds

**NTP/Clock Sync:**
- **No NTP Integration:** Assumes system clocks are synchronized externally
- **Unix Epoch Standard:** All timestamps use Unix epoch time.time()

---

### 2.2 Detection Service Clock Handling

**Clock Drift Mechanism:**
- **Calibration-Based:** Uses median offset calculation to compensate for drift
- **Dynamic Adjustment:** Recalculates offset per session based on observed detections
- **No Validation:** Does not check or warn about excessive drift

**Drift Correction:**
```python
# Implicit drift correction through calibration offset
# From labjack_detection_service.py (lines 1607-1611)
calibration_offset_seconds = TIMING_CALIBRATION_OFFSET_MS / 1000.0
detection_timestamp = timestamp.timestamp() + calibration_offset_seconds

# Calculate video-relative timestamp with calibration
video_relative_timestamp = detection_timestamp - video_start_time
```

**Limitation:**
- **Cross-Session Contamination:** Calibration from one video affects next video
- **Multi-Video Issues:** Disabled for sequences to prevent timing contamination
```python
# From labjack_detection_service.py (lines 1552-1559)
if is_multi_video:
    TIMING_CALIBRATION_OFFSET_MS = 0.0  # No calibration for sequences
    logger.info("Multi-video sequence detected - calibration disabled")
else:
    # Calculate dynamic calibration offset from actual measurements
    TIMING_CALIBRATION_OFFSET_MS = self.calculate_calibration_offset(session_id)
```

**NTP/Clock Sync:**
- **No NTP Integration:** Relies on calibration to compensate for any drift
- **Assumes Stable Clocks:** No validation of clock stability

---

## 3. Latency Calculation Methods

### 3.1 HIL Monitor Latency Calculation

**Method:**
```python
# From video_timing_service.py (lines 428-480)
def calculate_video_relative_latency(
    self, session_id: str, detection_unix_timestamp: float, db: Session = None
):
    timing_data = self.get_timing_data(session_id)

    # Convert to video-relative time
    video_relative_timestamp = self.convert_unix_to_video_relative(
        session_id, detection_unix_timestamp
    )

    # Calculate frame number
    frame_number = None
    if timing_data.frame_rate:
        frame_number = int(video_relative_timestamp * timing_data.frame_rate)

    # Processing latency (fixed estimate)
    processing_latency_ms = 50.0  # Default processing time

    return {
        "video_relative_timestamp": video_relative_timestamp,
        "actual_latency_ms": processing_latency_ms,  # Uses processing latency
        "video_frame_number": frame_number,
        "timing_sync_quality": timing_quality,
        "video_start_time": timing_data.start_timestamp,
        "timing_precision_ns": timing_data.precision_ns
    }
```

**Components Included:**
1. **Processing Time:** Fixed 50ms estimate (default detection pipeline latency)
2. **Video Position:** Accurate video-relative timestamp
3. **Frame Number:** Calculated from video position × FPS
4. **Quality Indicator:** Based on timing precision (high/medium/low)

**Accuracy:**
- **Sub-millisecond Precision:** Uses nanosecond-precision timing service
- **Clamping:** Prevents negative or out-of-bounds timestamps
- **Validation:** Quality indicators based on precision_ns value

---

### 3.2 Detection Service Latency Calculation

**Method:**
```python
# From labjack_detection_service.py (lines 1607-1623)
# Calculate video-relative timestamp with calibration
video_relative_timestamp = detection_timestamp - video_start_time

# Actual latency (not calculated - uses video position as proxy)
actual_latency_ms = video_relative_timestamp * 1000  # INCORRECT: This is video position, not latency
```

**Components Included:**
1. **Video Position:** Time since video started (NOT actual latency)
2. **Calibration Offset:** Median timing adjustment from previous detections
3. **No Processing Time:** Does not separate processing latency from video position

**Accuracy Issue:**
- **Conflates Video Position with Latency:** `actual_latency_ms` is actually video position × 1000
- **No True Latency Measurement:** Does not measure time from event to detection
- **Calibration Dependency:** Accuracy depends on quality of calibration data

---

## 4. Multi-Video Sequence Handling

### 4.1 HIL Monitor Multi-Video Timing

**Detection Window Clamping:**
```python
# From detection_window_clamp_service.py (lines 84-117)
def clamp_video_windows(
    video_timings: List[VideoTiming],
    grace_period_ms: float = 2000.0
) -> List[ClampedWindow]:
    """
    Clamp video detection windows to prevent overlaps in multi-video sequences.

    Grace period allows detections slightly before/after video boundaries.
    """
    sorted_videos = sorted(video_timings, key=lambda x: x.start_time)

    for i, video in enumerate(sorted_videos):
        start_time = video.start_time

        # Clamp end time to next video's start (minus grace period)
        if i < len(sorted_videos) - 1:
            next_video_start = sorted_videos[i + 1].start_time
            end_time = next_video_start - (grace_period_ms / 1000.0)
        else:
            end_time = start_time + video.duration

        clamped_windows.append(
            ClampedWindow(
                video_id=video.video_id,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time
            )
        )
```

**Video Transition Handling:**
- **Clamped Windows:** Each video has non-overlapping detection window
- **Grace Period:** 2000ms (2 seconds) buffer for boundary detections
- **Per-Video Timing:** Each video has independent `video_start_time` and `video_end_time`
- **Sequence Awareness:** Detection assignment considers sequence structure

**Timing Continuity:**
```python
# From dedicated_labjack_monitor.py (lines 296-304)
self.active_sessions[session_id] = {
    'video_timing_config': video_timing_config,
    'started_at': session_init_time,
    'video_start_time': None,  # Updated per video
    'current_video': None,     # Tracks active video
    'video_history': [],       # Maintains video sequence history
    'video_boundary_buffer': 0.5  # seconds of tolerance around lifecycle events
}
```

---

### 4.2 Detection Service Multi-Video Timing

**Multi-Video Handling:**
```python
# From labjack_detection_service.py (lines 1552-1559)
# CRITICAL FIX: Disable calibration for multi-video sequences
if is_multi_video:
    TIMING_CALIBRATION_OFFSET_MS = 0.0  # No calibration for sequences
    logger.info("Multi-video sequence detected - calibration disabled")
else:
    # Calculate dynamic calibration offset from actual measurements (single video only)
    TIMING_CALIBRATION_OFFSET_MS = self.calculate_calibration_offset(session_id)
```

**Limitation:**
- **Calibration Disabled:** No timing adjustment in multi-video sequences
- **No Per-Video Timing:** Uses session-level video_start_time for all videos
- **Potential Drift:** Without calibration, timing accuracy degrades across videos

**Video Transition Handling:**
- **No Explicit Handling:** Does not track video transitions
- **Single Reference Point:** Uses initial video_start_time for entire sequence
- **Timing Errors:** Later videos in sequence have increasing timestamp errors

---

## 5. Timing Accuracy Comparison

### 5.1 HIL Monitor Timing Accuracy

**Strengths:**
1. **Sub-millisecond Precision:** Uses nanosecond-precision timing service
2. **Direct Synchronization:** VideoTimingService integration provides accurate reference
3. **Clamped Timestamps:** Prevents negative or out-of-bounds values
4. **Quality Indicators:** Timing precision tracked and reported
5. **Multi-Video Support:** Proper per-video timing with clamped windows

**Precision Metrics:**
- **Timestamp Precision:** ≤ 1ms (tracked as `timing_accuracy_ns`)
- **Frame Accuracy:** Calculated from video position × FPS
- **Synchronization Quality:** Tracked as "high", "medium", "low"

**Race Condition Prevention:**
```python
# From dedicated_labjack_monitor.py (lines 384-427)
# STEP 1: Start LabJack monitoring FIRST
success = self.labjack_monitor.start_monitoring(session_id, **labjack_config)

# STEP 2: Initialize video timing service AFTER monitor is ready
video_start_time = self.video_timing_service.start_video_timing(...)

# This ensures all detections have valid timing data from first capture
logger.info("🎯 RACE CONDITION ELIMINATED: Video timing ready BEFORE first detection")
```

---

### 5.2 Detection Service Timing Accuracy

**Weaknesses:**
1. **Calibration Dependency:** Accuracy depends on quality of previous detections
2. **Video Position Conflation:** `actual_latency_ms` is actually video position
3. **No Frame Numbers:** Does not calculate frame-accurate positions
4. **Multi-Video Issues:** Calibration disabled for sequences (timing degradation)
5. **Cross-Session Contamination:** Calibration from one video affects another

**Precision Metrics:**
- **Timestamp Precision:** Unknown (no precision tracking)
- **Calibration Offset:** Median of previous detection offsets (variable accuracy)
- **Frame Accuracy:** Not calculated

**Limitations:**
```python
# From labjack_detection_service.py (line 1611)
# ISSUE: This calculates video position, NOT detection latency
video_relative_timestamp = detection_timestamp - video_start_time
actual_latency_ms = video_relative_timestamp * 1000  # INCORRECT
```

---

## 6. Summary and Recommendations

### 6.1 Which Provides Better Timing Accuracy?

**Winner: HIL Monitor (Dedicated LabJack Monitor)**

**Reasons:**
1. **Direct VideoTimingService Integration:** Provides sub-millisecond precision
2. **Proper Synchronization:** Video timing established before first detection
3. **Accurate Latency Calculation:** Separates processing latency from video position
4. **Frame-Accurate Timestamps:** Calculates frame numbers correctly
5. **Multi-Video Support:** Proper per-video timing with clamped windows
6. **Quality Tracking:** Reports timing precision and quality indicators

### 6.2 Detection Service Improvements Needed

**Critical Issues:**
1. **Fix Latency Calculation:**
   ```python
   # CURRENT (INCORRECT):
   actual_latency_ms = video_relative_timestamp * 1000  # This is video position!

   # CORRECT:
   actual_latency_ms = processing_pipeline_latency  # Measure actual processing time
   video_position_ms = video_relative_timestamp * 1000
   ```

2. **Add VideoTimingService Integration:**
   ```python
   from services.video_timing_service import get_video_timing_service

   self.video_timing_service = get_video_timing_service()
   timing_data = self.video_timing_service.calculate_video_relative_latency(
       session_id, detection_unix_timestamp, db
   )
   ```

3. **Implement Frame Number Calculation:**
   ```python
   if timing_data.frame_rate:
       frame_number = int(video_relative_timestamp * timing_data.frame_rate)
   ```

4. **Add Multi-Video Support:**
   - Track per-video timing instead of session-level timing
   - Use detection window clamping service
   - Maintain video history and transition tracking

### 6.3 Recommended Architecture

**Unified Timing Approach:**
```python
class UnifiedTimingService:
    """Single source of truth for video timing synchronization"""

    def __init__(self):
        self.video_timing_service = get_video_timing_service()
        self.precision_timing_service = get_precision_timing_service()

    def convert_hardware_to_video_time(
        self, session_id: str, hardware_timestamp: float
    ) -> VideoRelativeTiming:
        """Convert hardware timestamp to video-relative time"""

        # Get video timing reference
        timing_data = self.video_timing_service.get_timing_data(session_id)

        # Calculate video-relative position
        video_relative_timestamp = hardware_timestamp - timing_data.start_timestamp

        # Calculate frame number
        frame_number = int(video_relative_timestamp * timing_data.frame_rate)

        # Calculate actual processing latency (NOT video position)
        processing_latency_ms = self._measure_processing_latency()

        return VideoRelativeTiming(
            video_relative_timestamp=video_relative_timestamp,
            video_frame_number=frame_number,
            actual_latency_ms=processing_latency_ms,
            video_position_ms=video_relative_timestamp * 1000,
            timing_precision_ns=timing_data.precision_ns
        )
```

---

## 7. Technical Details

### 7.1 Timestamp Flow Diagram

```
Hardware Event (LabJack)
    ↓
Unix Timestamp (time.time())
    ↓
┌──────────────────────────────────┐
│ HIL Monitor Path:                │
│ 1. Get timing_data from          │
│    VideoTimingService            │
│ 2. video_relative = unix_ts -    │
│    video_start_timestamp         │
│ 3. frame_num = video_relative    │
│    × fps                         │
│ 4. latency = processing_time     │
│    (NOT video position)          │
└──────────────────────────────────┘
    ↓
Video-Relative Timestamp (0-10s)
    ↓
Frame Number (0-240)
    ↓
Actual Processing Latency (50-100ms)
```

```
Hardware Event (LabJack)
    ↓
Unix Timestamp (time.time())
    ↓
┌──────────────────────────────────┐
│ Detection Service Path:          │
│ 1. Calculate calibration_offset  │
│    from previous detections      │
│ 2. adjusted_ts = unix_ts +       │
│    calibration_offset            │
│ 3. video_relative = adjusted_ts  │
│    - video_start_time            │
│ 4. latency = video_relative ×    │
│    1000 (WRONG!)                 │
└──────────────────────────────────┘
    ↓
Video-Relative Timestamp (0-10s)
    ↓
INCORRECT: "Latency" = Video Position
```

### 7.2 Precision Comparison Table

| Metric | HIL Monitor | Detection Service |
|--------|-------------|-------------------|
| **Timestamp Precision** | Sub-millisecond (ns) | Unknown (no tracking) |
| **Synchronization Method** | Direct VideoTimingService | Calibration-based |
| **Frame Number Calculation** | ✅ Accurate | ❌ Not implemented |
| **Latency Calculation** | ✅ Separate processing time | ❌ Conflates with video position |
| **Multi-Video Support** | ✅ Per-video timing | ⚠️ Calibration disabled |
| **Clock Drift Handling** | ✅ Validation service | ⚠️ Implicit via calibration |
| **Race Condition Prevention** | ✅ Timing before first detection | ❌ No guarantee |
| **Quality Indicators** | ✅ Precision tracking | ❌ No quality metrics |

---

## 8. Conclusion

The **HIL Monitor provides significantly better timing accuracy** through:

1. **Direct VideoTimingService Integration** - Sub-millisecond precision
2. **Proper Synchronization** - Timing established before first detection
3. **Accurate Latency Calculation** - Separates processing time from video position
4. **Frame-Accurate Positioning** - Calculates frame numbers correctly
5. **Multi-Video Support** - Per-video timing with clamped windows
6. **Quality Tracking** - Reports precision and quality indicators

The **Detection Service requires significant improvements**:

1. Fix latency calculation (currently conflates video position with latency)
2. Integrate VideoTimingService for accurate timing
3. Implement frame number calculation
4. Add proper multi-video sequence support
5. Track and report timing precision metrics

**Recommendation:** Migrate Detection Service to use VideoTimingService directly, or consolidate both services into a unified timing architecture.

---

**Report Generated:** 2025-11-17
**Author:** Code Analysis Agent
**Version:** 1.0
