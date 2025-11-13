# Latency Calculation Analysis Report

**Generated**: 2025-11-05
**Purpose**: Complete analysis of latency calculation methods, negative latencies, and timing corrections

---

## Executive Summary

### Key Findings

1. **NEGATIVE LATENCIES ARE VALID** - They indicate detections arriving BEFORE the ground truth event time
2. **TWO LATENCY TYPES**:
   - `temporal_offset_ms` = detection_time - ground_truth_time (can be negative)
   - `latency_ms` = Only stored if temporal_offset_ms >= 0 (positive only)
3. **LARGE LATENCIES AT FRAME 120** are time-since-video-start, NOT detection latency
4. **TWO CALCULATION METHODS** exist: "real" and "aligned" latencies with timing corrections

---

## 1. What Does NEGATIVE Latency Mean?

### Answer: Detection Arrived BEFORE Ground Truth Event Time

**From `ground_truth_matching_service.py:770`:**
```python
temporal_offset_ms = (detection_time - gt_time) * 1000
latency_ms = temporal_offset_ms if temporal_offset_ms >= 0 else None
```

### Interpretation:

- **Negative temporal_offset**: Detection timestamp is EARLIER than ground truth timestamp
- **Example**: `-10.4ms` means detection arrived 10.4ms BEFORE the ground truth event
- **This is EXPECTED** in hardware systems due to:
  - Clock synchronization differences
  - Timing calibration offsets
  - Hardware trigger timing variations

### Observable Data Validation:

From session data:
- `-20ms to +18ms` = **Normal early/late variations** (within tolerance)
- `-10.4ms, -17.5ms, -18.9ms` = **Valid early detections**

---

## 2. Complete Latency Calculation Formulas

### 2.1 Ground Truth Matching Service (Primary)

**File**: `/services/ground_truth_matching_service.py:769-771`

```python
detection_time = extract_detection_video_time(detection, session_start_time)
temporal_offset_ms = (detection_time - gt_time) * 1000
latency_ms = temporal_offset_ms if temporal_offset_ms >= 0 else None
```

**Formula:**
```
temporal_offset_ms = (detection_timestamp - ground_truth_timestamp) × 1000
latency_ms = temporal_offset_ms if positive, else None
```

**Key Points:**
- Uses video-relative timestamps (seconds since video start)
- Can produce negative values (early detections)
- `latency_ms` field only stores positive values
- `temporal_offset_ms` stores both positive and negative

---

### 2.2 Timing Synchronization Calculator (Enhanced)

**File**: `/services/timing_synchronization_calculator.py:278-282`

```python
# Apparent latency = total time from LabJack start to detection
apparent_latency_ms = (detection_system_time - labjack_start_time) * 1000.0

# Real latency = detection_time - ground_truth_event_system_time
real_latency_ms = (detection_system_time - gt_system_time) * 1000.0

# Apply dynamic timing correction
latency_correction_ms = self.calculate_latency_correction(
    detection_system_time,
    gt_system_time,
    video_start_system_time,
    startup_delay_ms
)
```

**Two Types of Latency:**

1. **Apparent Latency** (time since session start):
   ```
   apparent_latency_ms = (detection_time - session_start_time) × 1000
   ```
   - Always positive
   - Includes video startup delay
   - **This is what causes "large latencies" at Frame 120**

2. **Real Latency** (actual detection delay):
   ```
   real_latency_ms = (detection_time - ground_truth_event_time) × 1000
   ```
   - Can be negative
   - Corrected for video startup delay
   - **This is the true detection performance metric**

---

## 3. Timing Corrections Applied

### 3.1 "Real" vs "Aligned" Latency

From observable data:
- **"real" latency**: Raw calculation without corrections
- **"aligned" latency**: Corrected with timing calibration offset

**Example from session:**
```
Real: -10ms → Aligned: -10.4ms (calibration offset applied)
```

### 3.2 Calibration Offset Calculation

**File**: `/services/labjack_detection_service.py:509-553`

```python
def calculate_calibration_offset(self, session_id: str) -> float:
    """Calculate calibration offset from actual detection timing data."""

    # Get first 10 detections
    detections = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id
    ).order_by(DetectionEvent.labjack_timestamp).limit(10).all()

    # Calculate median offset from ground truth
    calibration_offset = statistics.median(offsets)
    return calibration_offset
```

**Purpose:**
- Corrects for hardware clock drift
- Compensates for video start time offset
- Applied dynamically per session

---

## 4. Why Large Latencies at Frame 120?

### Root Cause: Time-Since-Video-Start vs Detection Latency

**Observed**: Detection at 6.762s, Frame 120 at 5.000s = **1762ms difference**

**This is NOT latency!** This is:
```
time_since_video_start = detection_absolute_time - video_start_time
```

### Correct Latency Calculation:

**Should be**:
```python
detection_latency = detection_time - corresponding_frame_time
```

**For Frame 120 example:**
- Frame 120 at 5.000s (24fps = frame at 5.0s)
- Detection at 6.762s
- **This means detection is for a LATER frame**, not Frame 120!
- If Frame 162 (6.75s @ 24fps), latency would be ~12ms

### Database Field Analysis:

**From `models.py:309-313`:**
```python
video_relative_timestamp = Column(Float, nullable=True, index=True)
# Timestamp relative to video start (seconds)

actual_latency_ms = Column(Float, nullable=True, index=True)
# Actual measured latency from video start (milliseconds)
```

**Issue**: `actual_latency_ms` name is misleading
- Contains: Time since video start
- Should contain: Detection delay from ground truth event

---

## 5. Database Schema Fields

### 5.1 DetectionEvent Model Fields

**Timing Fields:**
```python
# ABSOLUTE TIMESTAMPS (Unix epoch)
timestamp = Column(Float)                    # Raw detection timestamp
labjack_timestamp = Column(Float)            # LabJack hardware timestamp
video_start_time = Column(Float)             # Video playback start

# VIDEO-RELATIVE TIMESTAMPS (seconds since video start)
video_relative_timestamp = Column(Float)     # Position in video (0 to duration)
sequence_timestamp = Column(Float)           # Position in multi-video sequence

# LATENCY MEASUREMENTS (milliseconds)
actual_latency_ms = Column(Float)            # WARNING: Contains time-since-start, not latency!
latency_threshold_ms = Column(Float)         # Pass/fail threshold
```

### 5.2 DetectionComparison Model Fields

**From `models.py:685-687`:**
```python
temporal_offset = Column(Float)              # Can be negative (ms)
latency_ms = Column(Float)                   # Stored latency (only if positive)
```

---

## 6. Latency Calculation Code Locations

### Primary Calculation Points:

1. **Ground Truth Matching** (line 770):
   ```
   /services/ground_truth_matching_service.py
   ```
   - Main matching algorithm
   - Produces `temporal_offset_ms` and `latency_ms`

2. **Timing Synchronization** (line 278-282):
   ```
   /services/timing_synchronization_calculator.py
   ```
   - Calculates "real" vs "apparent" latency
   - Applies timing corrections

3. **LabJack Detection Service** (line 589):
   ```
   /services/labjack_detection_service.py
   ```
   - Creates detection events
   - Applies calibration offset

4. **Precision Timing Service** (line 168-177):
   ```
   /services/precision_timing_service.py
   ```
   - Sub-millisecond precision calculations
   - Uses monotonic clocks

---

## 7. Correct Formulas and Fixes Needed

### 7.1 Current Formula (Ground Truth Matching)

✅ **CORRECT**:
```python
temporal_offset_ms = (detection_time - ground_truth_time) * 1000
latency_ms = temporal_offset_ms if temporal_offset_ms >= 0 else None
```

**This correctly:**
- Calculates time difference
- Allows negative values
- Only stores positive in `latency_ms` field

---

### 7.2 Timing Correction Formula

✅ **CORRECT** (after Fix #1 applied):
```python
# Apparent latency (includes startup delay)
apparent_latency_ms = (detection_system_time - labjack_start_time) * 1000.0

# Real latency (corrected for video timing)
real_latency_ms = (detection_system_time - gt_system_time) * 1000.0

# Dynamic correction (removes startup delay)
latency_correction_ms = calculate_latency_correction(...)
```

---

### 7.3 Video-Relative Timestamp Calculation

✅ **CORRECT**:
```python
# File: timing_synchronization_calculator.py:296
video_relative_timestamp = detection_system_time - video_start_system_time
```

**This correctly calculates position in video (0 to duration)**

---

### 7.4 Frame Number Calculation

✅ **CORRECT**:
```python
# File: timing_synchronization_calculator.py:302
fps = video_timing_metadata.fps or 24.0
video_frame_number = int(video_relative_timestamp * fps)
```

**This correctly converts time to frame number**

---

## 8. Issues and Fixes Required

### 8.1 CRITICAL: `actual_latency_ms` Field Misuse

**Current Code** (`labjack_detection_service.py:589`):
```python
# ✅ FIXED: Don't hardcode latency - will be calculated from actual pipeline timing
actual_latency_ms = None  # Should be populated from t3_processing_time_ms
```

**Issue:**
- Field named `actual_latency_ms` but contains `video_relative_timestamp`
- Causes confusion when displaying "latency"

**Fix Applied:**
- Set to `None` during creation
- Populated later by ground truth matching service
- Frontend should use `temporal_offset` from `DetectionComparison` table

---

### 8.2 Frontend Display Confusion

**Issue**: Two latency values shown:
- "real -10ms" (from temporal_offset)
- "aligned -10.4ms" (with calibration offset)

**Fix Required:**
```typescript
// Frontend should display:
if (detection.temporal_offset < 0) {
  label = "Early Detection";
  value = Math.abs(detection.temporal_offset);
  color = "blue";
} else {
  label = "Detection Latency";
  value = detection.temporal_offset;
  color = detection.temporal_offset <= threshold ? "green" : "red";
}
```

---

## 9. Testing Recommendations

### 9.1 Validate Negative Latency Handling

```python
def test_negative_latency_calculation():
    """Test that early detections produce negative temporal_offset"""
    detection_time = 5.0  # seconds
    ground_truth_time = 5.02  # 20ms later

    temporal_offset = (detection_time - ground_truth_time) * 1000
    assert temporal_offset == -20.0  # Early by 20ms

    latency_ms = temporal_offset if temporal_offset >= 0 else None
    assert latency_ms is None  # Not stored as latency
```

### 9.2 Validate Frame 120 Large Latency

```python
def test_frame_120_timing():
    """Test that large values are video position, not latency"""
    detection_time = 6.762  # seconds
    video_start_time = 0.0
    frame_120_time = 120 / 24.0  # = 5.0 seconds at 24fps

    # Video-relative position
    video_relative_timestamp = detection_time - video_start_time
    assert video_relative_timestamp == 6.762  # Position in video

    # Frame number
    frame_number = int(video_relative_timestamp * 24.0)
    assert frame_number == 162  # Not Frame 120!

    # Actual latency (if detection was for Frame 162)
    expected_frame_time = 162 / 24.0  # = 6.75s
    actual_latency_ms = (detection_time - expected_frame_time) * 1000
    assert actual_latency_ms ≈ 12ms  # This is the real latency
```

---

## 10. Summary and Conclusions

### 10.1 Negative Latencies

✅ **VALID and EXPECTED**
- Indicate detections arriving before ground truth event
- Common in hardware systems with clock synchronization
- Stored in `temporal_offset` field
- NOT stored in `latency_ms` field (which only holds positive values)

### 10.2 Latency Calculation

✅ **CORRECT IMPLEMENTATION**
```
temporal_offset_ms = (detection_time - ground_truth_time) × 1000
latency_ms = temporal_offset_ms (if ≥ 0, else None)
```

### 10.3 Timing Corrections

✅ **TWO TYPES**:
1. **Real latency**: detection_time - ground_truth_time
2. **Aligned latency**: Real latency + calibration_offset

### 10.4 Large Latencies at Frame 120

❌ **BUG IDENTIFIED**:
- Value is `video_relative_timestamp` (time since video start)
- NOT actual detection latency
- Should use `temporal_offset` from matching service
- Frontend needs to fetch from `DetectionComparison` table

### 10.5 Database Fields

⚠️ **NAMING ISSUE**:
- `actual_latency_ms` field is misleading
- Contains video position, not latency
- Use `DetectionComparison.temporal_offset` for true latency

---

## 11. Action Items

### High Priority

1. **Frontend Fix**: Use `DetectionComparison.temporal_offset` instead of `DetectionEvent.actual_latency_ms`
2. **Documentation**: Update API docs to clarify field meanings
3. **Testing**: Add test cases for negative latencies

### Medium Priority

4. **Database Migration**: Consider renaming `actual_latency_ms` → `video_position_ms`
5. **UI Enhancement**: Display "Early Detection" label for negative temporal offsets
6. **Logging**: Add warnings when large latencies indicate wrong field usage

### Low Priority

7. **Code Comments**: Add inline documentation for latency calculations
8. **Metrics Dashboard**: Show distribution of early vs late detections

---

## 12. References

### Code Files Analyzed

1. `/services/ground_truth_matching_service.py` (lines 769-771)
2. `/services/timing_synchronization_calculator.py` (lines 278-282, 296, 302)
3. `/services/labjack_detection_service.py` (lines 509-553, 589)
4. `/services/precision_timing_service.py` (lines 168-177)
5. `/models.py` (lines 276-431)

### Database Schema

- `DetectionEvent` model (lines 276-431)
- `DetectionComparison` model (lines 676-704)
- `TestSession` model (lines 212-274)

---

**Report Complete** ✅

**Next Steps**: Frontend team should use `DetectionComparison.temporal_offset` for accurate latency display.
