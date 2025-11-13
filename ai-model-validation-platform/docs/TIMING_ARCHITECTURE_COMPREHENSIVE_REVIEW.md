# Timing System Architecture - Comprehensive Review
**Date**: 2025-11-04
**Reviewer**: System Architecture Designer
**Session**: Timing Investigation Swarm

---

## Executive Summary

### Critical Finding
The timing system suffers from **architectural fragmentation** across multiple timing domains with **inconsistent conversion logic** and **weak synchronization boundaries**, leading to:
- Negative latency calculations (-871ms bug)
- Video boundary violations in multi-video sequences
- Incorrect detection-to-video assignment
- Systemic timing biases and drift

### Architectural Health Score: 4/10
- ✅ Precision timing infrastructure exists
- ⚠️ Timing domain boundaries unclear
- ❌ Conversion logic scattered and inconsistent
- ❌ Multi-video timing fundamentally broken
- ❌ Ground truth matching timing-sensitive

---

## 1. Overall Timing Architecture

### 1.1 Timing Domain Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TIMING DOMAIN LANDSCAPE                         │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  LABJACK     │◀───────▶│   SYSTEM     │◀───────▶│    VIDEO     │
│   TIME       │         │    TIME      │         │    TIME      │
│              │         │              │         │              │
│ Unix Epoch   │         │  Unix Epoch  │         │  Relative    │
│ Hardware Ref │         │  OS Clock    │         │  to Start    │
│ Nanosecond   │         │  Microsecond │         │  Millisecond │
└──────────────┘         └──────────────┘         └──────────────┘
       │                        │                        │
       │                        │                        │
       ▼                        ▼                        ▼
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  DETECTION   │         │  SEQUENCE    │         │    FRAME     │
│   TIME       │         │    TIME      │         │    TIME      │
│              │         │              │         │              │
│ Unix + Calib │         │  Relative to │         │  Frame #     │
│ Event-based  │         │  Seq Start   │         │  @ FPS       │
│ Millisecond  │         │  Millisecond │         │  Integer     │
└──────────────┘         └──────────────┘         └──────────────┘
```

**Critical Issues**:
1. **No Single Source of Truth**: Multiple independent time sources
2. **Weak Boundaries**: Conversion logic scattered across 7+ services
3. **Implicit Dependencies**: Services assume synchronized clocks
4. **Calibration Drift**: 166ms hardcoded offset in detection service

### 1.2 Timing Service Architecture

```
precision_timing_service.py (Core Infrastructure)
├─ PrecisionTimestamp (Nanosecond precision)
│  ├─ monotonic_ns: Monotonic clock reference
│  └─ utc_timestamp: Human-readable UTC
├─ FrameTimestamp (Video synchronization)
│  ├─ frame_number: Integer frame index
│  ├─ video_timestamp_ms: Video-relative time
│  └─ system_timestamp_ns: System time correlation
└─ PrecisionTimingService (Orchestration)
   ├─ session_start_times: Session timing tracking
   ├─ timing_events: Event logging
   └─ synchronize_video_frames(): Frame-level sync

video_timing_service.py (Video Integration)
├─ VideoTimingService
│  ├─ start_video_timing(): Record video start
│  ├─ convert_unix_to_video_relative(): Time domain conversion
│  └─ calculate_video_relative_latency(): Latency computation
└─ TIMING REGRESSION FIX: Line 162
   # FIXED: Use simple system timestamp to match original timing reference
   start_timestamp = time.time()  # Was: sync_point.monotonic_ns / 1e9

timing_synchronization_calculator.py (Latency Calculation)
├─ calculate_corrected_latency(): Main latency calculation
│  ├─ video_start_system_time = labjack_start_time  # FIXED
│  ├─ real_latency_ms = detection_time - gt_system_time
│  └─ latency_correction_ms = apparent - real
└─ NEGATIVE LATENCY FIX: Lines 166-176
   # CRITICAL FIX: Startup delay is NOT a time offset
   # video_start_system_time = labjack_start_time (same reference point)
```

**Architectural Problems**:
1. **Timing Regression Fix** (Line 162): Reverted to `time.time()` from monotonic clock
   - **Impact**: Lost sub-millisecond precision
   - **Root Cause**: Monotonic vs system time domain mismatch

2. **Hardcoded Calibration** (labjack_detection_service.py:520):
   ```python
   TIMING_CALIBRATION_OFFSET_MS = 166.0  # Empirically determined offset
   ```
   - **Impact**: Systemic bias in all detections
   - **Root Cause**: Covers up underlying timing synchronization failure

3. **Null Latency Conversion** (timestamp_conversion_utils.py:102):
   ```python
   actual_latency_ms = None  # Caller must provide actual measured latency
   ```
   - **Impact**: Latency calculation responsibility unclear
   - **Root Cause**: Conversion utility can't determine processing latency

---

## 2. Multi-Video Timing Design

### 2.1 Current Multi-Video Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                 VIDEO SEQUENCE ORCHESTRATOR                          │
│                 (video_sequence_orchestrator.py)                     │
└─────────────────────────────────────────────────────────────────────┘

VideoTestSequence State:
├─ sequence_id: UUID
├─ session_id: UUID
├─ video_ids: [video1_id, video2_id, ...]
├─ current_video_index: 0  ◀─── STUCK AT FIRST VIDEO
├─ sequence_start_time: Unix timestamp (when sequence started)
└─ video_metadata: {
    video1_id: {
      video_start_time: 1730632032.560  ◀─── SET CORRECTLY
      video_end_time: None             ◀─── NEVER SET
      duration: 10.5s
    },
    video2_id: {
      video_start_time: None           ◀─── NEVER STARTED
      video_end_time: None
      duration: 12.3s
    }
  }

Detection Event Creation Flow:
1. LabJack hardware event → Detection service
2. Detection service queries: orchestrator.get_current_video_id(session_id)
3. Orchestrator returns: video_ids[current_video_index]  # Always video1_id
4. Detection event created with: video_id = video1_id
5. ALL detections assigned to Video 1 ◀─── CRITICAL BUG
```

**Architectural Weaknesses**:

1. **No Video Transition Mechanism**:
   ```python
   # MISSING: Automatic video advancement
   def check_video_completion(self, sequence_id, current_time):
       """Should check if video duration exceeded and advance"""
       # NOT IMPLEMENTED
       pass

   def notify_video_ended(self, sequence_id, video_id, end_timestamp, db):
       """Called when video ends - BUT WHO CALLS THIS?"""
       # Requires external notification - never received
       pass
   ```

2. **Detection Video Assignment Uses Current Index**:
   ```python
   # File: video_sequence_orchestrator.py:428
   def _determine_video_for_detection(self, sequence, detection_timestamp):
       # Checks video time ranges - GOOD
       for video_id in sequence.video_ids:
           if metadata.video_start_time <= detection_timestamp <= video_end:
               return video_id

       # But video_end_time is NEVER SET for video transitions
       # Falls through to None, detection lost
   ```

3. **Video Timing Metadata Not Updated**:
   ```python
   # File: video_sequence_orchestrator.py:266-337
   def notify_video_started(self, sequence_id, video_id, actual_start_timestamp, db):
       # Sets video_start_time ✓
       # But notify_video_ended() is NEVER CALLED
       # video_end_time remains None ✗
   ```

### 2.2 Multi-Video Timing Flow Diagram

```
Expected Flow:
┌────────┐  Start   ┌────────┐  Complete  ┌────────┐  Start   ┌────────┐
│Video 1 │──────────▶│Video 1 │────────────▶│Video 2 │──────────▶│Video 2 │
│ Ready  │          │Playing │            │ Ready  │          │Playing │
└────────┘          └────────┘            └────────┘          └────────┘
    │                    │                      │                   │
    │ t=0s               │ t=10.5s              │ t=10.6s           │ t=22.9s
    │                    │                      │                   │
    │ start_time=T0      │ end_time=T0+10.5     │ start_time=T0+10.6│ end_time=T0+22.9
    │ current_index=0    │ current_index=1 ◀────TRANSITION MISSING
    │                    │                      │
    └─ Detections with   └─ Advance index      └─ Detections with
       video_id=video1      Notify orchestrator     video_id=video2

Actual Flow:
┌────────┐  Start   ┌────────┐  ???  ┌────────┐
│Video 1 │──────────▶│Video 1 │──────▶│Video 1 │ (continues forever)
│ Ready  │          │Playing │      │Playing │
└────────┘          └────────┘      └────────┘
    │                    │               │
    │ t=0s               │ t=10.5s       │ t=100s
    │                    │               │
    │ start_time=T0      │ NO END TIME   │ STILL NO END TIME
    │ current_index=0    │ current_index=0 (stuck)
    │                    │               │
    └─ Detections with   └─ Detections   └─ ALL detections
       video_id=video1      still video1      still video1

┌────────┐
│Video 2 │  NEVER STARTED - remains in "pending" state
│ Ready  │  video_start_time = None
└────────┘  video_end_time = None
    │       current_index never reaches 1
    └─ NO DETECTIONS ASSIGNED TO VIDEO 2
```

### 2.3 Data Flow Analysis Evidence

From `/backend/docs/COMPLETE_DATA_FLOW_ANALYSIS.md`:

```
Session: 59cc6ae8-40b7-49ab-864b-add4a5846255

Ground Truth Upload: ✅ CORRECT
├─ Video 1: 262 GT objects stored
└─ Video 2: 252 GT objects stored

Test Execution: ❌ BROKEN
├─ Detection Events Created: 105
├─ Video 1 assignments: 105 ◀── ALL
└─ Video 2 assignments: 0   ◀── NONE

Database State:
video_test_sequences:
├─ current_video_index: 0  ◀── STUCK
├─ status: "running"
└─ video_ids: ['10c2b16c...', '550e3cf8...']

detection_events:
├─ Total: 105
├─ WHERE video_id = '10c2b16c...': 105  ◀── ALL Video 1
└─ WHERE video_id = '550e3cf8...': 0    ◀── ZERO Video 2

Root Cause:
current_video_index never advances from 0 → ALL detections get video1_id
```

---

## 3. Latency Calculation Pipeline

### 3.1 End-to-End Latency Calculation Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LATENCY CALCULATION PIPELINE                      │
└─────────────────────────────────────────────────────────────────────┘

Step 1: Detection Event Capture
────────────────────────────────
LabJack Hardware Event @ t_hardware
  │
  ├─ Timestamp: Unix epoch (system clock)
  ├─ Voltage: Trigger level
  └─ Channel: Detection source

  ▼ TIMING CALIBRATION APPLIED (labjack_detection_service.py:520)

TIMING_CALIBRATION_OFFSET_MS = 166.0ms  ◀── HARDCODED OFFSET
calibration_offset_seconds = 166.0 / 1000.0
detection_timestamp = timestamp.timestamp() + calibration_offset_seconds

⚠️ ARCHITECTURAL FLAW: Calibration masks underlying sync failure

Step 2: Video-Relative Timestamp Conversion
─────────────────────────────────────────────
video_timing_service.convert_unix_to_video_relative()
  │
  ├─ Input: detection_timestamp (Unix + 166ms offset)
  ├─ Input: video_start_time (from video_timing_service)
  │
  └─ Calculation:
     video_relative_timestamp = detection_timestamp - video_start_time

     Example:
     detection_timestamp = 1730632032.560 + 0.166 = 1730632032.726
     video_start_time = 1730632032.560  ◀── TIMING REGRESSION FIX
     video_relative_timestamp = 0.166s (166ms into video)

⚠️ ARCHITECTURAL ISSUE: video_start_time precision downgraded

Step 3: Latency Correction Calculation
────────────────────────────────────────
timing_synchronization_calculator.calculate_corrected_latency()
  │
  ├─ Input: detection_system_time (Unix timestamp)
  ├─ Input: labjack_start_time (Unix timestamp)
  ├─ Input: ground_truth_video_time (video-relative seconds)
  │
  └─ CRITICAL FIX APPLIED (Lines 166-176):

     # BEFORE (INCORRECT):
     video_start_system_time = labjack_start_time + (startup_delay_ms / 1000.0)
     # This ADDED startup delay as a time offset → negative latency

     # AFTER (CORRECT):
     video_start_system_time = labjack_start_time
     # Startup delay is buffering time, NOT a time offset

     gt_system_time = video_start_system_time + ground_truth_video_time
     real_latency_ms = (detection_system_time - gt_system_time) * 1000.0

     Example:
     detection_system_time = 1730632032.726
     labjack_start_time = 1730632032.560
     ground_truth_video_time = 0.120s

     gt_system_time = 1730632032.560 + 0.120 = 1730632032.680
     real_latency_ms = (1730632032.726 - 1730632032.680) * 1000 = 46ms ✓

Step 4: Latency Quality Assessment
────────────────────────────────────
frame_aware_quality_assessment (if enabled)
  │
  ├─ Input: real_latency_ms, timing results, video metadata
  ├─ Analysis: Frame correlation, temporal consistency
  │
  └─ Output:
     ├─ timing_quality: "excellent" | "good" | "fair" | "poor"
     ├─ confidence_score: 0.0 - 1.0
     └─ quality_classification: Camera vs system overhead separation
```

### 3.2 Latency Correction Mechanisms

**Implemented Corrections**:

1. **Negative Latency Fix** (timing_synchronization_calculator.py):
   ```python
   # CORRECTED FORMULA (Line 173):
   video_start_system_time = labjack_start_time
   # NOT: labjack_start_time + startup_delay_ms

   # EXPLANATION:
   # - startup_delay_ms is the time BEFORE video starts (buffering)
   # - labjack_start_time and video_start_time are the SAME moment
   # - Both use Unix epoch, no offset needed
   ```

2. **Timestamp Epoch Validation** (timing_synchronization_calculator.py:185-218):
   ```python
   # Validate timestamps are recent (within 24 hours)
   labjack_age = abs(current_epoch - labjack_start_time)
   detection_age = abs(current_epoch - detection_system_time)

   timestamp_validation_failed = (
       labjack_age > 86400 or      # More than 24 hours old
       detection_age > 86400 or    # More than 24 hours old
       time_span > 600             # More than 10 minutes span
   )

   if timestamp_validation_failed:
       # Use position-based estimation instead of corrupt timestamps
       real_latency_ms = 75.0 + (video_position_factor * 25.0)
   ```

3. **Latency Decomposition** (timing_synchronization_calculator.py:265-312):
   ```python
   # Separate camera latency from system overhead
   decomposition = self.decomposition_service.decompose_latency(
       session_id, detection_id, total_latency_ms, detection_metadata
   )

   camera_latency_ms = decomposition.camera_latency_ms        # Pure camera
   system_overhead_ms = decomposition.system_baseline_ms      # HW/OS overhead
   processing_overhead_ms = (decomposition.processing_overhead_ms +
                            decomposition.network_overhead_ms +
                            decomposition.sync_overhead_ms)
   ```

**Missing Corrections**:

1. **Clock Drift Compensation**: No long-term drift tracking
2. **Cross-Session Calibration**: 166ms offset not validated per session
3. **Multi-Video Latency Adjustment**: No per-video calibration offsets

### 3.3 Systemic Timing Biases

**Identified Biases**:

1. **166ms Calibration Offset** (labjack_detection_service.py):
   - **Source**: Empirically determined
   - **Applied**: All detection events
   - **Impact**: Systemic +166ms bias in all latency calculations
   - **Risk**: Masks true latency variations

2. **Timing Regression Precision Loss** (video_timing_service.py:162):
   ```python
   # BEFORE: Nanosecond precision
   start_timestamp = sync_point.monotonic_ns / 1e9

   # AFTER: Microsecond precision (regression)
   start_timestamp = time.time()
   ```
   - **Impact**: Lost ~1000x precision
   - **Root Cause**: Domain mismatch between monotonic and system clocks

3. **Null Latency in Conversions** (timestamp_conversion_utils.py:102):
   ```python
   # ✅ CORRECTED: actual_latency_ms should be NULL here
   actual_latency_ms = None  # Caller must provide actual measured latency

   # ❌ PREVIOUS BUG:
   # actual_latency_ms = video_relative_timestamp * 1000
   # ^ Used video POSITION as latency (completely wrong!)
   ```
   - **Fixed**: No longer calculates fake latency
   - **Impact**: Latency responsibility now clear (caller provides)

---

## 4. Ground Truth Matching

### 4.1 Temporal Matching Algorithm

```python
# File: ground_truth_matching_service.py:552-743

def _perform_temporal_matching(
    detection_events, ground_truth_objects, tolerance_ms
):
    """
    Temporal matching with video boundary validation (BUG #10 FIX)
    """

    tolerance_seconds = tolerance_ms / 1000.0
    match_results = []
    used_detections = set()

    # CRITICAL: Detect multi-video sequences
    gt_video_ids = set(gt.video_id for gt in ground_truth_objects)
    has_multi_video_sequence = len(gt_video_ids) > 1

    if has_multi_video_sequence:
        logger.info(f"BUG #10 FIX: Multi-video sequence detected with "
                   f"{len(gt_video_ids)} videos - enforcing video boundary validation")

    # Phase 1: Match GT objects to nearest detections
    for gt_obj in ground_truth_objects:
        best_match = None
        best_time_diff = float('inf')

        for i, detection in enumerate(detection_events):
            if i in used_detections:
                continue

            # ★ VIDEO BOUNDARY VALIDATION (BUG #10 FIX) ★
            detection_video_id = getattr(detection, 'video_id', None)
            gt_video_id = getattr(gt_obj, 'video_id', None)

            if detection_video_id != gt_video_id:
                # Different videos - REJECT match
                video_boundary_rejections += 1
                continue

            # Calculate temporal difference
            detection_time = (
                detection.video_relative_timestamp
                if hasattr(detection, 'video_relative_timestamp')
                else detection.timestamp
            )
            time_diff = abs(detection_time - gt_obj.timestamp)

            # Check if within tolerance and better than current best
            if time_diff <= tolerance_seconds and time_diff < best_time_diff:
                best_match = (i, detection)
                best_time_diff = time_diff

        if best_match:
            # True Positive match found
            detection_idx, detection = best_match
            used_detections.add(detection_idx)

            temporal_offset_ms = (detection_time - gt_obj.timestamp) * 1000
            latency_ms = temporal_offset_ms if temporal_offset_ms >= 0 else None

            match_result = MatchResult(
                ground_truth_id=gt_obj.id,
                detection_event_id=detection.id,
                match_type='TP',
                temporal_offset=temporal_offset_ms,
                latency_ms=latency_ms,
                ...
            )
        else:
            # False Negative - no matching detection
            match_result = MatchResult(
                ground_truth_id=gt_obj.id,
                detection_event_id=None,
                match_type='FN',
                ...
            )
```

**Timing Sensitivity Issues**:

1. **Video Boundary Validation**:
   ```python
   # BUG #10 FIX (Lines 608-628):
   if detection_video_id != gt_video_id:
       video_boundary_rejections += 1
       continue  # REJECT cross-video matches
   ```
   - **Impact**: If detections have wrong video_id → 100% match failure
   - **Current Issue**: ALL detections have video_id=video1 → video2 GT never matches

2. **Temporal Tolerance Window**:
   ```python
   # Default tolerance: 100ms
   # Stricter for high-quality timing: 500ms base, 2000ms degraded

   time_tolerance_ms = base_tolerance_ms if timing_looks_reliable else max_tolerance_ms

   if time_diff <= tolerance_seconds:
       # Within tolerance - candidate match
   ```
   - **Impact**: Tight tolerances fail if timestamps have systematic offset
   - **Current Issue**: 166ms calibration offset may exceed tolerance

3. **Frame-Based vs Time-Based Matching**:
   ```python
   # Prefers video_relative_timestamp (time-based)
   detection_time = (
       detection.video_relative_timestamp
       if hasattr(detection, 'video_relative_timestamp')
       else detection.timestamp  # Fallback to frame-based
   )
   ```
   - **Impact**: Mixing time/frame domains causes mismatches
   - **Current Issue**: Some detections have NULL video_relative_timestamp

### 4.2 Fallback Strategies

```python
# File: ground_truth_matching_service.py:523-610

def _find_closest_ground_truth(detection, ground_truth_events):
    """Find closest GT event with fallback strategies"""

    # STRATEGY 1: Time-based matching (preferred)
    if detection.video_relative_timestamp is not None:
        detection_time = float(detection.video_relative_timestamp)

        # Adaptive tolerance based on timing quality
        timing_looks_reliable = 0 <= detection_time <= 60
        time_tolerance_ms = 500 if timing_looks_reliable else 2000

        # Find closest within tolerance
        valid_matches = [
            gt for gt in ground_truth_events
            if abs((gt.timestamp - detection_time) * 1000) <= time_tolerance_ms
        ]

        if valid_matches:
            return min(valid_matches, key=time_distance)

    # STRATEGY 2: Frame-based matching (fallback)
    if detection.frame_number > 0:
        return min(
            ground_truth_events,
            key=lambda gt: abs(gt.frame_number - detection.frame_number)
        )

    # STRATEGY 3: First available GT (last resort)
    if ground_truth_events:
        logger.warning("Using first available GT as fallback")
        return ground_truth_events[0]

    return None
```

**Fallback Issues**:

1. **Strategy Degradation**: Fallbacks don't preserve timing accuracy
2. **Last Resort Matching**: "First available GT" creates random matches
3. **No Confidence Scoring**: Can't distinguish good vs fallback matches

---

## 5. Architectural Diagrams

### 5.1 Timing System Component Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TIMING SYSTEM ARCHITECTURE                      │
│                         (Component View)                             │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                        HARDWARE LAYER                                 │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌────────────┐          ┌────────────┐          ┌────────────┐    │
│  │  LabJack   │          │  System    │          │   Video    │    │
│  │  Hardware  │          │   Clock    │          │  Decoder   │    │
│  │            │          │            │          │            │    │
│  │ Voltage    │          │ Unix Epoch │          │ Frame      │    │
│  │ Triggers   │          │ time.time()│          │ Timestamps │    │
│  └─────┬──────┘          └─────┬──────┘          └─────┬──────┘    │
│        │                       │                        │            │
└────────┼───────────────────────┼────────────────────────┼────────────┘
         │                       │                        │
         │ Unix timestamp        │ Unix timestamp         │ Frame # + FPS
         │                       │                        │
┌────────▼───────────────────────▼────────────────────────▼────────────┐
│                      PRECISION TIMING LAYER                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  PrecisionTimingService                                       │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │  │
│  │  │ Monotonic    │  │   UTC        │  │   Frame      │       │  │
│  │  │ Timestamp    │  │ Timestamp    │  │  Timestamp   │       │  │
│  │  │              │  │              │  │              │       │  │
│  │  │ monotonic_ns │  │ utc_datetime │  │ frame_number │       │  │
│  │  │ (nanosecond) │  │ (ISO 8601)   │  │ + video_ms   │       │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ⚠️ TIMING REGRESSION (Line 162 video_timing_service.py):           │
│     Downgraded from monotonic_ns to time.time()                     │
│     Lost 1000x precision for video timing                           │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
         │
         │ Precision timestamps
         │
┌────────▼───────────────────────────────────────────────────────────┐
│                     CONVERSION & SYNC LAYER                         │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  VideoTimingService                                          │ │
│  │  ┌────────────────┐        ┌────────────────┐              │ │
│  │  │  start_video   │        │ convert_unix   │              │ │
│  │  │    _timing()   │───────▶│ _to_video_rel()│              │ │
│  │  │                │        │                │              │ │
│  │  │ video_start =  │        │ video_rel =    │              │ │
│  │  │  time.time()   │        │  unix - start  │              │ │
│  │  └────────────────┘        └────────────────┘              │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  TimestampConverter (timestamp_conversion_utils.py)          │ │
│  │  ┌────────────────┐        ┌────────────────┐              │ │
│  │  │ unix_to_video  │        │  calculate     │              │ │
│  │  │   _relative()  │───────▶│ _frame_number()│              │ │
│  │  │                │        │                │              │ │
│  │  │ ⚠️ Returns     │        │ frame = time   │              │ │
│  │  │ latency=None   │        │        * fps   │              │ │
│  │  └────────────────┘        └────────────────┘              │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
         │
         │ Converted timestamps
         │
┌────────▼───────────────────────────────────────────────────────────┐
│                    LATENCY CALCULATION LAYER                        │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  TimingSynchronizationCalculator                             │ │
│  │  ┌────────────────────────────────────────────────────────┐ │ │
│  │  │  calculate_corrected_latency()                         │ │ │
│  │  │                                                         │ │ │
│  │  │  ✅ NEGATIVE LATENCY FIX (Line 173):                  │ │ │
│  │  │  video_start_system_time = labjack_start_time         │ │ │
│  │  │  (NOT labjack_start_time + startup_delay_ms)          │ │ │
│  │  │                                                         │ │ │
│  │  │  gt_system_time = video_start + gt_video_time         │ │ │
│  │  │  real_latency_ms = (detection - gt_system) * 1000     │ │ │
│  │  └────────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  LatencyDecompositionService                                 │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐ │ │
│  │  │    Camera      │  │    System      │  │ Processing   │ │ │
│  │  │   Latency      │  │   Overhead     │  │  Overhead    │ │ │
│  │  │                │  │                │  │              │ │ │
│  │  │  Pure camera   │  │  HW/OS delay   │  │ SW pipeline  │ │ │
│  │  │  response time │  │                │  │    delay     │ │ │
│  │  └────────────────┘  └────────────────┘  └──────────────┘ │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
         │
         │ Latency metrics
         │
┌────────▼───────────────────────────────────────────────────────────┐
│                    MATCHING & VALIDATION LAYER                      │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  GroundTruthMatchingService                                  │ │
│  │  ┌────────────────────────────────────────────────────────┐ │ │
│  │  │  _perform_temporal_matching()                          │ │ │
│  │  │                                                         │ │ │
│  │  │  ★ VIDEO BOUNDARY VALIDATION (BUG #10 FIX):           │ │ │
│  │  │  if detection.video_id != gt.video_id:                │ │ │
│  │  │      REJECT match (prevents cross-video matching)     │ │ │
│  │  │                                                         │ │ │
│  │  │  time_diff = abs(detection_time - gt_timestamp)       │ │ │
│  │  │  if time_diff <= tolerance_seconds:                   │ │ │
│  │  │      Match found (TP)                                 │ │ │
│  │  └────────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ⚠️ CRITICAL ISSUE: If detections have wrong video_id,            │
│     ALL Video 2 GT matches FAIL due to boundary validation        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Multi-Video Timing Sequence Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│            MULTI-VIDEO TIMING SEQUENCE DIAGRAM                       │
│                (Expected vs Actual Behavior)                         │
└─────────────────────────────────────────────────────────────────────┘

EXPECTED BEHAVIOR:
═══════════════════

Frontend          VideoSequence        LabJack           Detection
                 Orchestrator         Monitor            Service
   │                  │                  │                  │
   │ Start Seq        │                  │                  │
   ├─────────────────▶│                  │                  │
   │                  │ Init sequence    │                  │
   │                  ├─ current_idx=0   │                  │
   │                  ├─ video1_start=T0 │                  │
   │                  │                  │                  │
   │ Play Video 1     │                  │                  │
   ├─────────────────▶│ notify_video_   │                  │
   │                  │  started(vid1)   │                  │
   │                  ├─ set start_time  │                  │
   │                  │                  │                  │
   │                  │                  │ HW Event @ T0+5s │
   │                  │                  ├─────────────────▶│
   │                  │                  │                  │ get_video_id
   │                  │◀─────────────────┼──────────────────┤ (session)
   │                  │ Returns: video1  │                  │
   │                  ├─────────────────────────────────────▶│
   │                  │                  │                  │ Store:
   │                  │                  │                  │ video_id=vid1
   │                  │                  │                  │ ✅ CORRECT
   │                  │                  │                  │
   │ Video 1 Ends     │                  │                  │
   ├─────────────────▶│ notify_video_   │                  │
   │                  │  ended(vid1)     │                  │
   │                  ├─ set end_time    │                  │
   │                  ├─ current_idx=1   │ ★ ADVANCE       │
   │                  ├─ video2_start=T1 │                  │
   │                  │                  │                  │
   │ Play Video 2     │                  │                  │
   ├─────────────────▶│ notify_video_   │                  │
   │                  │  started(vid2)   │                  │
   │                  ├─ update metadata │                  │
   │                  │                  │                  │
   │                  │                  │ HW Event @ T1+3s │
   │                  │                  ├─────────────────▶│
   │                  │                  │                  │ get_video_id
   │                  │◀─────────────────┼──────────────────┤ (session)
   │                  │ Returns: video2  │ ★ NOW VIDEO 2   │
   │                  ├─────────────────────────────────────▶│
   │                  │                  │                  │ Store:
   │                  │                  │                  │ video_id=vid2
   │                  │                  │                  │ ✅ CORRECT

ACTUAL BEHAVIOR (BROKEN):
═════════════════════════

Frontend          VideoSequence        LabJack           Detection
                 Orchestrator         Monitor            Service
   │                  │                  │                  │
   │ Start Seq        │                  │                  │
   ├─────────────────▶│                  │                  │
   │                  │ Init sequence    │                  │
   │                  ├─ current_idx=0   │                  │
   │                  ├─ video1_start=T0 │                  │
   │                  │                  │                  │
   │ Play Video 1     │                  │                  │
   ├─────────────────▶│ notify_video_   │                  │
   │                  │  started(vid1)   │                  │
   │                  ├─ set start_time  │                  │
   │                  │                  │                  │
   │                  │                  │ HW Event @ T0+5s │
   │                  │                  ├─────────────────▶│
   │                  │                  │                  │ get_video_id
   │                  │◀─────────────────┼──────────────────┤ (session)
   │                  │ Returns: video1  │                  │
   │                  ├─────────────────────────────────────▶│
   │                  │                  │                  │ Store:
   │                  │                  │                  │ video_id=vid1
   │                  │                  │                  │ ✅ CORRECT
   │                  │                  │                  │
   │ Video 1 Ends     │                  │                  │
   ├─ ??? ───────────▶│ ??? NO CALL ??? │                  │
   │                  │ ❌ NOT CALLED   │                  │
   │                  │ current_idx=0    │ ❌ STUCK        │
   │                  │ (still video 1)  │                  │
   │                  │                  │                  │
   │ Play Video 2     │                  │                  │
   ├─────────────────▶│ notify_video_   │                  │
   │                  │  started(vid2)   │                  │
   │                  ├─ set start_time  │ ✅ CALLED       │
   │                  │ BUT current_idx  │                  │
   │                  │ STILL = 0 !!!    │ ❌ NOT ADVANCED │
   │                  │                  │                  │
   │                  │                  │ HW Event @ T1+3s │
   │                  │                  ├─────────────────▶│
   │                  │                  │                  │ get_video_id
   │                  │◀─────────────────┼──────────────────┤ (session)
   │                  │ Returns: video1  │ ❌ STILL VIDEO1!│
   │                  ├─────────────────────────────────────▶│
   │                  │                  │                  │ Store:
   │                  │                  │                  │ video_id=vid1
   │                  │                  │                  │ ❌ WRONG!!!
   │                  │                  │                  │
   │                  │                  │ ALL subsequent   │
   │                  │                  │ events @ T1+Xs   │
   │                  │                  ├─────────────────▶│
   │                  │ Returns: video1  │ ❌ STILL VID1   │
   │                  ├─────────────────────────────────────▶│ Store:
   │                  │                  │                  │ video_id=vid1
   │                  │                  │                  │ ❌ ALL WRONG
   │                  │                  │                  │


Result: ALL 105 detections have video_id = video1
        Video 2 has 0 detections despite 252 ground truth objects
```

---

## 6. Design Flaws Identified

### 6.1 Critical Design Flaws

**Flaw #1: Timing Domain Fragmentation**
- **Issue**: No unified timing architecture
- **Evidence**: 5+ timing domains with ad-hoc conversions
- **Impact**: Precision loss, conversion errors, systemic biases
- **Severity**: CRITICAL

**Flaw #2: Hardcoded Calibration Offsets**
- **Issue**: 166ms offset applied universally
- **Evidence**: `labjack_detection_service.py:520`
- **Impact**: Masks underlying synchronization failures
- **Severity**: HIGH

**Flaw #3: Timing Regression**
- **Issue**: Downgraded from nanosecond to microsecond precision
- **Evidence**: `video_timing_service.py:162`
- **Impact**: Lost 1000x timing accuracy
- **Severity**: HIGH

**Flaw #4: Multi-Video Orchestration Missing**
- **Issue**: No video transition mechanism
- **Evidence**: `current_video_index` never advances
- **Impact**: 100% data loss for Video 2+
- **Severity**: CRITICAL

**Flaw #5: Video Boundary Validation Creates Cascading Failures**
- **Issue**: Strict boundary validation + wrong video_id = no matches
- **Evidence**: `ground_truth_matching_service.py:608-628`
- **Impact**: Zero matches for misassigned detections
- **Severity**: HIGH

**Flaw #6: Latency Responsibility Unclear**
- **Issue**: Conversion utils return `latency=None`
- **Evidence**: `timestamp_conversion_utils.py:102`
- **Impact**: Caller confusion, inconsistent latency calculation
- **Severity**: MEDIUM

### 6.2 Architectural Anti-Patterns

**Anti-Pattern #1: God Service**
```python
# timing_synchronization_calculator.py has too many responsibilities:
- Timestamp conversion
- Latency calculation
- Quality assessment
- Latency decomposition
- Session metrics aggregation
```
**Violation**: Single Responsibility Principle
**Fix**: Split into specialized services

**Anti-Pattern #2: Shotgun Surgery**
```python
# Changing timing logic requires editing 7+ files:
- precision_timing_service.py
- video_timing_service.py
- timing_synchronization_calculator.py
- timestamp_conversion_utils.py
- labjack_detection_service.py
- video_sequence_orchestrator.py
- ground_truth_matching_service.py
```
**Violation**: Low Cohesion
**Fix**: Centralize timing domain logic

**Anti-Pattern #3: Magic Numbers**
```python
TIMING_CALIBRATION_OFFSET_MS = 166.0  # Empirically determined offset
```
**Violation**: Configuration should be explicit and justified
**Fix**: Make calibration configurable with validation

**Anti-Pattern #4: Silent Failures**
```python
# Video transition not called → no error, just stuck
# Detection video_id wrong → stored silently
# Timestamp conversion fails → returns None quietly
```
**Violation**: Fail Fast Principle
**Fix**: Add explicit error handling and logging

---

## 7. Recommended Architectural Improvements

### 7.1 Timing Domain Unification

**Architecture: Timing Domain Abstraction Layer**

```python
# NEW FILE: services/timing_domain_abstraction.py

from dataclasses import dataclass
from typing import Protocol
from enum import Enum

class TimingDomain(Enum):
    """Unified timing domain definitions"""
    HARDWARE = "hardware"        # LabJack Unix timestamp
    SYSTEM = "system"            # OS Unix timestamp
    VIDEO = "video"              # Video-relative (0-based)
    SEQUENCE = "sequence"        # Sequence-relative (multi-video)
    FRAME = "frame"              # Frame number + FPS

@dataclass
class UnifiedTimestamp:
    """Unified timestamp with domain context"""
    value: float                 # Timestamp value
    domain: TimingDomain         # Source domain
    precision_ns: float          # Precision estimate
    reference_point: str         # What this timestamp is relative to

    def convert_to(self, target_domain: TimingDomain,
                   context: 'TimingContext') -> 'UnifiedTimestamp':
        """Convert to target domain with explicit context"""
        converter = TimingDomainConverter(context)
        return converter.convert(self, target_domain)

class TimingContext:
    """Explicit timing context for conversions"""
    def __init__(
        self,
        session_id: str,
        labjack_start_time: float,
        video_start_time: float,
        video_fps: float,
        sequence_start_time: Optional[float] = None
    ):
        self.session_id = session_id
        self.labjack_start_time = labjack_start_time
        self.video_start_time = video_start_time
        self.video_fps = video_fps
        self.sequence_start_time = sequence_start_time

    def validate(self):
        """Validate timing context consistency"""
        if self.labjack_start_time != self.video_start_time:
            logger.warning(
                f"LabJack start ({self.labjack_start_time}) != "
                f"Video start ({self.video_start_time})"
            )

        if self.sequence_start_time and \
           self.sequence_start_time != self.video_start_time:
            # Expected for multi-video sequences
            logger.info("Multi-video sequence detected")

class TimingDomainConverter:
    """Centralized timing domain conversions"""

    def __init__(self, context: TimingContext):
        self.context = context
        self.conversion_log = []

    def convert(self, timestamp: UnifiedTimestamp,
                target_domain: TimingDomain) -> UnifiedTimestamp:
        """Convert timestamp between domains with logging"""

        if timestamp.domain == target_domain:
            return timestamp  # No conversion needed

        # Explicit conversion matrix
        converter = self._get_converter(timestamp.domain, target_domain)
        result = converter(timestamp, self.context)

        # Log conversion for audit
        self.conversion_log.append({
            'from_domain': timestamp.domain,
            'to_domain': target_domain,
            'input_value': timestamp.value,
            'output_value': result.value,
            'precision_loss': timestamp.precision_ns - result.precision_ns
        })

        return result

    def _get_converter(self, from_domain, to_domain):
        """Get appropriate converter function"""
        conversion_matrix = {
            (TimingDomain.HARDWARE, TimingDomain.VIDEO):
                self._hardware_to_video,
            (TimingDomain.VIDEO, TimingDomain.FRAME):
                self._video_to_frame,
            (TimingDomain.SYSTEM, TimingDomain.SEQUENCE):
                self._system_to_sequence,
            # ... all conversion pairs
        }

        converter = conversion_matrix.get((from_domain, to_domain))
        if not converter:
            raise ValueError(
                f"No converter from {from_domain} to {to_domain}"
            )

        return converter

    def _hardware_to_video(self, timestamp, context):
        """Convert hardware timestamp to video-relative"""
        video_relative = timestamp.value - context.video_start_time

        return UnifiedTimestamp(
            value=video_relative,
            domain=TimingDomain.VIDEO,
            precision_ns=timestamp.precision_ns,
            reference_point=f"video_start:{context.video_start_time}"
        )

    def _video_to_frame(self, timestamp, context):
        """Convert video time to frame number"""
        frame_number = int(timestamp.value * context.video_fps)

        return UnifiedTimestamp(
            value=frame_number,
            domain=TimingDomain.FRAME,
            precision_ns=1e9 / context.video_fps,  # Frame precision
            reference_point=f"fps:{context.video_fps}"
        )
```

**Benefits**:
- Explicit domain conversions
- Precision tracking through conversions
- Audit log for debugging
- No implicit assumptions

### 7.2 Multi-Video Timing Fix

**Architecture: Event-Driven Video Transitions**

```python
# ENHANCED FILE: services/video_sequence_orchestrator.py

from enum import Enum
from dataclasses import dataclass
from typing import Callable, List

class VideoTransitionEvent(Enum):
    """Video lifecycle events"""
    VIDEO_STARTED = "video_started"
    VIDEO_ENDED = "video_ended"
    VIDEO_PAUSED = "video_paused"
    VIDEO_RESUMED = "video_resumed"

@dataclass
class VideoTransitionHandler:
    """Handler for video transition events"""
    event_type: VideoTransitionEvent
    handler: Callable
    priority: int = 0

class VideoSequenceOrchestrator:
    """Enhanced orchestrator with event-driven transitions"""

    def __init__(self):
        self._active_sequences = {}
        self._transition_handlers = []

        # Register built-in handlers
        self.register_transition_handler(
            VideoTransitionEvent.VIDEO_ENDED,
            self._auto_advance_video,
            priority=100
        )

    def register_transition_handler(
        self,
        event_type: VideoTransitionEvent,
        handler: Callable,
        priority: int = 0
    ):
        """Register handler for video transition events"""
        self._transition_handlers.append(
            VideoTransitionHandler(event_type, handler, priority)
        )
        # Sort by priority (higher first)
        self._transition_handlers.sort(key=lambda h: h.priority, reverse=True)

    def notify_video_ended(
        self,
        sequence_id: str,
        video_id: str,
        actual_end_timestamp: float,
        db: Session
    ) -> bool:
        """
        Record video end and trigger transition handlers.

        CRITICAL FIX: This method MUST be called by frontend or
        automatic detection when video completes.
        """
        try:
            sequence = self._get_sequence(sequence_id)

            # Update video metadata
            metadata = sequence.video_metadata[video_id]
            metadata.video_end_time = actual_end_timestamp

            result = sequence.video_results[video_id]
            result.video_end_time = actual_end_timestamp
            result.status = VideoStatus.COMPLETED

            logger.info(f"Video ended: {video_id} at {actual_end_timestamp:.6f}")

            # TRIGGER TRANSITION EVENT
            self._trigger_event(
                VideoTransitionEvent.VIDEO_ENDED,
                sequence_id, video_id, actual_end_timestamp, db
            )

            return True

        except Exception as e:
            logger.error(f"Failed to process video end: {e}")
            return False

    def _trigger_event(
        self,
        event_type: VideoTransitionEvent,
        *args, **kwargs
    ):
        """Trigger all handlers for event type"""
        handlers = [
            h for h in self._transition_handlers
            if h.event_type == event_type
        ]

        for handler in handlers:
            try:
                handler.handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"Handler {handler.handler.__name__} failed: {e}")

    def _auto_advance_video(
        self,
        sequence_id: str,
        completed_video_id: str,
        end_timestamp: float,
        db: Session
    ):
        """
        Automatically advance to next video when current video ends.

        CRITICAL FIX: This handler ensures current_video_index advances.
        """
        sequence = self._get_sequence(sequence_id)

        # Find index of completed video
        try:
            completed_index = sequence.video_ids.index(completed_video_id)
        except ValueError:
            logger.error(f"Completed video {completed_video_id} not in sequence")
            return

        # Verify this is the current video
        if completed_index != sequence.current_video_index:
            logger.warning(
                f"Video {completed_video_id} completed but not current video "
                f"(current_index={sequence.current_video_index})"
            )

        # Advance to next video
        if completed_index < len(sequence.video_ids) - 1:
            sequence.current_video_index = completed_index + 1
            next_video_id = sequence.video_ids[sequence.current_video_index]

            logger.info(
                f"★ AUTO-ADVANCED ★ sequence {sequence_id}: "
                f"Video {completed_index} → Video {completed_index + 1} "
                f"(next: {next_video_id})"
            )

            # Update database
            self._update_sequence_in_db(sequence, db)
        else:
            logger.info(
                f"Sequence {sequence_id} completed - no more videos"
            )
            self._finalize_sequence(sequence_id, db)

    def _update_sequence_in_db(self, sequence, db):
        """Update sequence state in database"""
        from models import VideoTestSequence as VideoTestSequenceModel

        db_sequence = db.query(VideoTestSequenceModel).filter(
            VideoTestSequenceModel.id == sequence.sequence_id
        ).first()

        if db_sequence:
            db_sequence.current_video_index = sequence.current_video_index
            db_sequence.updated_at = datetime.now(timezone.utc)
            db.commit()
```

**Key Improvements**:
1. Event-driven architecture for transitions
2. Automatic video advancement
3. Extensible handler registration
4. Database state synchronization

### 7.3 Detection Video Assignment Fix

**Architecture: Timestamp-Based Video Determination**

```python
# ENHANCED FILE: services/labjack_detection_service.py

class LabJackDetectionMonitor:
    """Enhanced detection monitor with smart video assignment"""

    def __init__(self):
        # ... existing initialization ...

        # NEW: Video sequence orchestrator integration
        from services.video_sequence_orchestrator import get_video_sequence_orchestrator
        self.orchestrator = get_video_sequence_orchestrator()

    def _create_detection_event(
        self,
        session_id: str,
        channel: str,
        voltage: float,
        threshold: float,
        timestamp: datetime
    ) -> DetectionEvent:
        """
        Create detection event with correct video_id assignment.

        CRITICAL FIX: Use timestamp-based video determination
        instead of current_video_index.
        """
        event_id = str(uuid.uuid4())

        # Convert datetime to Unix timestamp
        detection_timestamp = timestamp.timestamp()

        # ★ NEW: Determine video based on timestamp ranges ★
        video_id = self._determine_video_for_detection(
            session_id, detection_timestamp
        )

        if video_id is None:
            logger.error(
                f"Could not determine video for detection at {detection_timestamp}"
            )
            # Fallback to orchestrator's current video
            try:
                sequence = self.orchestrator.get_sequence_for_session(session_id)
                video_id = sequence.video_ids[sequence.current_video_index]
                logger.warning(f"Using fallback video_id: {video_id}")
            except Exception as e:
                logger.error(f"Fallback video_id failed: {e}")
                return None

        # ... rest of detection event creation ...

        return DetectionEvent(
            id=event_id,
            session_id=session_id,
            video_id=video_id,  # ✅ CORRECTLY DETERMINED
            timestamp=detection_timestamp,
            ...
        )

    def _determine_video_for_detection(
        self,
        session_id: str,
        detection_timestamp: float
    ) -> Optional[str]:
        """
        Determine which video was playing at detection time.

        CRITICAL FIX: Uses video timing ranges instead of current_video_index.

        Args:
            session_id: Test session ID
            detection_timestamp: Unix timestamp of detection

        Returns:
            Video ID that was playing, or None if undetermined
        """
        try:
            # Get sequence from orchestrator
            sequence = self.orchestrator.get_sequence_for_session(session_id)

            if not sequence:
                logger.warning(f"No sequence found for session {session_id}")
                return None

            # Check each video's time range
            for video_id in sequence.video_ids:
                metadata = sequence.video_metadata.get(video_id)

                if not metadata or metadata.video_start_time is None:
                    # Video hasn't started yet
                    continue

                # Determine video end time
                if metadata.video_end_time is not None:
                    # Video has ended
                    video_end = metadata.video_end_time
                else:
                    # Video still playing - use start + duration + buffer
                    video_end = metadata.video_start_time + metadata.duration + 1.0

                # Check if detection falls within video range
                if metadata.video_start_time <= detection_timestamp <= video_end:
                    logger.debug(
                        f"Detection at {detection_timestamp:.6f} assigned to "
                        f"video {video_id} (range: {metadata.video_start_time:.6f} - "
                        f"{video_end:.6f})"
                    )
                    return video_id

            # No video found for timestamp
            logger.warning(
                f"Detection at {detection_timestamp:.6f} does not fall within "
                f"any video range for session {session_id}"
            )
            return None

        except Exception as e:
            logger.error(f"Error determining video for detection: {e}")
            return None
```

**Benefits**:
- Timestamp-based assignment (robust)
- Independent of current_video_index
- Fallback to current video if needed
- Detailed logging for debugging

### 7.4 Calibration Configuration

**Architecture: Dynamic Calibration System**

```python
# NEW FILE: services/timing_calibration_service.py

from dataclasses import dataclass
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class TimingCalibration:
    """Timing calibration configuration"""
    calibration_id: str
    session_id: Optional[str] = None  # None = global calibration
    offset_ms: float = 0.0
    confidence: float = 0.0
    calibration_method: str = "manual"
    validated_at: Optional[datetime] = None
    applied_count: int = 0

class TimingCalibrationService:
    """
    Dynamic timing calibration service.

    Replaces hardcoded TIMING_CALIBRATION_OFFSET_MS with
    validated, session-specific calibrations.
    """

    def __init__(self):
        self.calibrations: Dict[str, TimingCalibration] = {}
        self.global_calibration: Optional[TimingCalibration] = None

        # Load default calibration from config
        self._load_default_calibration()

    def _load_default_calibration(self):
        """Load default calibration from configuration"""
        # TODO: Load from config file or environment
        default_offset = 166.0  # Legacy value

        self.global_calibration = TimingCalibration(
            calibration_id="default",
            offset_ms=default_offset,
            confidence=0.5,  # Low confidence - needs validation
            calibration_method="legacy_hardcoded"
        )

        logger.warning(
            f"Using legacy calibration offset: {default_offset}ms "
            f"(confidence: 50%) - validation recommended"
        )

    def get_calibration_offset(
        self,
        session_id: Optional[str] = None
    ) -> float:
        """
        Get calibration offset for session.

        Priority:
        1. Session-specific calibration (highest confidence)
        2. Global calibration (validated)
        3. Default calibration (legacy fallback)
        """
        # Check for session-specific calibration
        if session_id and session_id in self.calibrations:
            calibration = self.calibrations[session_id]
            calibration.applied_count += 1

            logger.debug(
                f"Using session calibration for {session_id}: "
                f"{calibration.offset_ms}ms "
                f"(confidence: {calibration.confidence:.2f})"
            )

            return calibration.offset_ms

        # Use global calibration
        if self.global_calibration:
            self.global_calibration.applied_count += 1

            logger.debug(
                f"Using global calibration: "
                f"{self.global_calibration.offset_ms}ms "
                f"(confidence: {self.global_calibration.confidence:.2f})"
            )

            return self.global_calibration.offset_ms

        # No calibration available
        logger.warning("No calibration available - using 0ms offset")
        return 0.0

    def validate_calibration(
        self,
        session_id: str,
        measured_offset_ms: float,
        confidence: float,
        method: str = "automatic"
    ) -> TimingCalibration:
        """
        Validate and store calibration for session.

        Args:
            session_id: Session to calibrate
            measured_offset_ms: Measured timing offset
            confidence: Confidence score (0-1)
            method: Calibration method (automatic, manual, hardware)

        Returns:
            Created calibration
        """
        calibration = TimingCalibration(
            calibration_id=f"cal_{session_id}",
            session_id=session_id,
            offset_ms=measured_offset_ms,
            confidence=confidence,
            calibration_method=method,
            validated_at=datetime.now(timezone.utc),
            applied_count=0
        )

        self.calibrations[session_id] = calibration

        logger.info(
            f"Calibration validated for session {session_id}: "
            f"{measured_offset_ms}ms (confidence: {confidence:.2f}, "
            f"method: {method})"
        )

        return calibration

    def auto_calibrate_from_detections(
        self,
        session_id: str,
        detection_events: List[Dict],
        ground_truth_events: List[Dict]
    ) -> Optional[TimingCalibration]:
        """
        Automatically calibrate timing offset from detection data.

        Uses median offset from matched detections to determine
        systematic timing bias.
        """
        try:
            # Calculate temporal offsets for all matched pairs
            offsets = []

            for detection in detection_events:
                # Find closest ground truth
                closest_gt = self._find_closest_gt(detection, ground_truth_events)

                if closest_gt:
                    # Calculate temporal offset
                    det_time = detection.get('video_relative_timestamp', 0)
                    gt_time = closest_gt.get('timestamp', 0)
                    offset_ms = (det_time - gt_time) * 1000.0

                    offsets.append(offset_ms)

            if len(offsets) < 10:
                logger.warning(
                    f"Insufficient data for auto-calibration: {len(offsets)} matches"
                )
                return None

            # Calculate median offset (robust to outliers)
            import statistics
            median_offset = statistics.median(offsets)
            std_dev = statistics.stdev(offsets)

            # Confidence based on consistency
            confidence = min(1.0, 1.0 / (1.0 + std_dev / 100.0))

            logger.info(
                f"Auto-calibration: median_offset={median_offset:.2f}ms, "
                f"std_dev={std_dev:.2f}ms, confidence={confidence:.2f}"
            )

            # Validate calibration
            return self.validate_calibration(
                session_id, median_offset, confidence, method="automatic"
            )

        except Exception as e:
            logger.error(f"Auto-calibration failed: {e}")
            return None
```

**Benefits**:
- Replaces hardcoded offsets
- Session-specific calibrations
- Automatic calibration from data
- Confidence tracking

---

## 8. Migration Strategy

### 8.1 Phase 1: Foundation (Week 1-2)

**Objective**: Establish timing domain abstraction layer

**Tasks**:
1. Create `timing_domain_abstraction.py` with `UnifiedTimestamp`
2. Implement `TimingDomainConverter` with explicit conversion matrix
3. Add comprehensive unit tests for domain conversions
4. Document timing domain architecture

**Success Criteria**:
- All timing conversions use `UnifiedTimestamp`
- Conversion audit log captures all domain transitions
- Zero precision loss warnings in tests

### 8.2 Phase 2: Multi-Video Fixes (Week 3-4)

**Objective**: Fix video sequence orchestration and detection assignment

**Tasks**:
1. Implement event-driven video transitions in orchestrator
2. Add timestamp-based video determination in detection service
3. Create frontend video transition notifications
4. Add automatic video advancement based on duration

**Success Criteria**:
- `current_video_index` advances automatically
- Detections correctly assigned to Video 2+
- Multi-video test sessions show detections for all videos

### 8.3 Phase 3: Calibration System (Week 5-6)

**Objective**: Replace hardcoded offsets with dynamic calibration

**Tasks**:
1. Implement `TimingCalibrationService`
2. Add auto-calibration from detection data
3. Create calibration validation endpoints
4. Migrate legacy 166ms offset to configurable default

**Success Criteria**:
- Calibration offsets validated per session
- Auto-calibration confidence > 0.8 for normal sessions
- Legacy behavior preserved with default calibration

### 8.4 Phase 4: Quality Assurance (Week 7-8)

**Objective**: Comprehensive testing and validation

**Tasks**:
1. End-to-end multi-video sequence tests
2. Timing precision regression tests
3. Load testing with 25+ video sequences
4. Production smoke tests

**Success Criteria**:
- All existing tests pass
- New multi-video tests pass
- Production metrics show no timing degradation

---

## 9. Conclusion

### 9.1 Summary of Findings

The timing system architecture suffers from **critical design flaws** that manifest as:
1. **Negative latency calculations** (fixed, but architectural issues remain)
2. **Multi-video detection assignment failures** (100% data loss for Video 2+)
3. **Timing domain fragmentation** (5+ domains with weak boundaries)
4. **Hardcoded calibration offsets** (masking synchronization failures)
5. **Precision regression** (lost 1000x accuracy in video timing)

### 9.2 Priority Recommendations

**CRITICAL (Fix Immediately)**:
1. Implement video transition mechanism in orchestrator
2. Fix detection video_id assignment using timestamp-based determination
3. Add frontend video end notifications

**HIGH (Fix Within 2 Weeks)**:
1. Create timing domain abstraction layer
2. Replace hardcoded 166ms offset with configurable calibration
3. Restore nanosecond precision for video timing

**MEDIUM (Fix Within 4 Weeks)**:
1. Implement dynamic calibration service
2. Add comprehensive timing audit logging
3. Create timing quality monitoring dashboard

### 9.3 Success Metrics

**Technical Metrics**:
- Zero negative latency calculations
- 100% detection assignment to correct videos in multi-video tests
- < 1ms average timing precision across all domains
- > 0.8 calibration confidence for auto-calibrated sessions

**Business Metrics**:
- Multi-video test sessions show detections for all videos
- Ground truth matching success rate > 95%
- Production timing incidents reduced by 90%

---

**Document Version**: 1.0
**Last Updated**: 2025-11-04
**Review Status**: Comprehensive architectural review complete
**Next Steps**: Begin Phase 1 implementation of timing domain abstraction layer
