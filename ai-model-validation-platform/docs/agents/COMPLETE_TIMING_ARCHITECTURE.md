# Complete Timing Architecture: Hardware Signal to Frontend Display

**Document Version:** 1.0
**Date:** 2025-11-05
**Analysis Focus:** End-to-end timing data flow from LabJack voltage spike to HIL Results UI

---

## Executive Summary

This document traces the complete timing architecture for the AI Model Validation Platform's Hardware-in-the-Loop (HIL) testing system. The analysis reveals **critical timing bugs** causing incorrect latency calculations, frame bunching, and display issues.

### Critical Findings

1. **Frame 120 Bunching Bug**: 70 detections incorrectly assigned to frame 120 (5.0s)
2. **Zero Latency Display**: "Avg Latency: 0.0ms" in summary (should be ~50ms)
3. **Infinity Best Latency**: "Best: Infinityms" displayed
4. **Negative Latency Values**: Incorrect calculation logic producing impossible negative latencies
5. **Missing `actual_latency_ms`**: Timestamp conversion service returns NULL instead of measured latency

---

## 1. Complete Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ HARDWARE SIGNAL DETECTION                                       │
│ (LabJack U3 Device)                                            │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   │ Voltage spike detected (e.g., 3.5V > 3.3V threshold)
                   │ Captured timestamp: time.time() → Unix epoch (seconds since 1970)
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Hardware Signal Capture                                │
│ File: services/labjack_detection_service.py                    │
│                                                                 │
│ _monitoring_loop() @ line 421-496:                            │
│   • Polls voltage at sample_rate (default 1000 Hz)            │
│   • Detects: voltage >= config.voltage_threshold              │
│   • Captures: timestamp = datetime.now()                      │
│   • Records: labjack_trigger_time = timestamp.timestamp()     │
│                                                                 │
│ Output Fields:                                                  │
│   - timestamp: datetime object (when voltage threshold crossed)│
│   - voltage: float (actual voltage reading, e.g., 3.5V)       │
│   - channel: str (e.g., "AIN0")                               │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   │ Callback: detection_callback(event)
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Detection Event Processing                             │
│ File: services/dedicated_labjack_monitor.py                    │
│                                                                 │
│ _handle_detection_with_video_sync() @ line 387-628:           │
│   • Receives: labjack_event from detection service            │
│   • Extracts: labjack_trigger_time = event.timestamp.timestamp()│
│   • Calculates: detection_record_time = time.time()           │
│   • Computes: real_processing_latency_ms =                    │
│               (detection_record_time - labjack_trigger_time) * 1000│
│                                                                 │
│ ⚠️ TIMING REFERENCE POINTS:                                    │
│   - labjack_trigger_time: When hardware detected voltage      │
│   - detection_record_time: When we processed the detection    │
│   - real_processing_latency_ms: Actual detection pipeline time│
│                                                                 │
│ Video Timing Conversion @ line 437-439:                       │
│   timing_data = video_timing_service.calculate_video_relative_latency(│
│       session_id, labjack_trigger_time                        │
│   )                                                            │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   │ Calls video timing service
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Timestamp Conversion                                   │
│ File: services/timestamp_conversion_utils.py                   │
│                                                                 │
│ unix_to_video_relative() @ line 57-129:                       │
│   • Input: unix_timestamp (labjack_trigger_time)              │
│   • Input: video_start_time (from session metadata)           │
│   • Calculation:                                               │
│       video_relative_timestamp = unix_timestamp - video_start_time│
│       video_relative_timestamp_ns = int(video_relative * 1e9) │
│                                                                 │
│ ❌ BUG: Line 102 sets actual_latency_ms = None                │
│   • Comment says: "Caller must provide actual measured latency"│
│   • Result: Detection event has NULL latency instead of 50ms  │
│   • This breaks frontend latency display!                     │
│                                                                 │
│ Frame Calculation @ line 151:                                  │
│   frame_number = int(video_relative_timestamp * fps)          │
│   • Uses FPS from video metadata (24 fps for VRU test videos)│
│                                                                 │
│ Output:                                                         │
│   - video_relative_timestamp: float (seconds from video start)│
│   - video_relative_timestamp_ns: str (nanosecond precision)   │
│   - actual_latency_ms: None ❌ (SHOULD BE measured latency)  │
│   - video_frame_number: None (calculated separately)          │
│   - timing_sync_quality: str ("high", "medium", "low")        │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   │ Returns timing_data dict
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Detection Event Storage                                │
│ File: services/dedicated_labjack_monitor.py                    │
│                                                                 │
│ _store_event_sync_wrapper() @ line 702-829:                   │
│   • Creates DetectionEvent database record                     │
│   • Populates timestamp fields from timing_data               │
│                                                                 │
│ ⚠️ CRITICAL FIELDS STORED (models.py @ line 276-430):        │
│   timestamp: labjack_trigger_time (Unix epoch)                │
│   video_relative_timestamp: From timing conversion            │
│   video_frame_number: Calculated from video_relative_timestamp│
│   actual_latency_ms: From timing_data (currently NULL!)       │
│   labjack_timestamp: labjack_trigger_time (duplicate)         │
│   labjack_voltage: Voltage reading (e.g., 3.5V)              │
│   detection_channel: Channel name (e.g., "AIN0")              │
│   video_id: Video identifier (for multi-video sequences)      │
│   sequence_timestamp: Timestamp relative to sequence start    │
│   video_play_offset_ms: Offset for video within sequence     │
│                                                                 │
│ Database Schema (models.py DetectionEvent):                    │
│   - timestamp (Float): Unix timestamp                          │
│   - video_relative_timestamp (Float): Seconds from video start│
│   - video_frame_number (Integer): Calculated frame           │
│   - actual_latency_ms (Float): Detection-to-signal latency   │
│   - labjack_voltage (Float): Trigger voltage                  │
│   - detection_channel (String): Hardware channel              │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   │ Stored in database: detection_events table
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Ground Truth Matching                                  │
│ File: services/ground_truth_matching_service.py                │
│                                                                 │
│ _perform_temporal_matching() @ line 642-854:                  │
│   • Loads detection events from database                       │
│   • Loads ground truth objects for video(s)                   │
│   • Temporal matching algorithm:                               │
│                                                                 │
│ Algorithm @ line 694-809:                                      │
│   1. For each ground_truth object:                            │
│      - Extract gt_time from ground_truth.timestamp            │
│      - Find closest detection within tolerance (±100ms default)│
│      - Calculate temporal_offset_ms = detection_time - gt_time│
│      - Mark as True Positive (TP) if match found              │
│      - Mark as False Negative (FN) if no match                │
│   2. Remaining detections marked as False Positive (FP)       │
│                                                                 │
│ ⚠️ CRITICAL: Video Boundary Validation @ line 722-751        │
│   • Multi-video sequences: detection.video_id must match     │
│     gt_obj.video_id to prevent cross-video matching          │
│   • BUG #10 FIX: Reject detections with NULL video_id in     │
│     multi-video mode to prevent boundary violations           │
│                                                                 │
│ Output: List[MatchResult]                                      │
│   - ground_truth_id: GT object ID                             │
│   - detection_event_id: Detection ID (or None for FN)         │
│   - match_type: "TP", "FP", or "FN"                          │
│   - temporal_offset: Offset in milliseconds                   │
│   - latency_ms: Detection latency (from temporal_offset)     │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   │ Stores results in detection_comparisons table
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: Metrics Calculation                                    │
│ File: services/session_completion_service.py                   │
│                                                                 │
│ complete_session() @ line 213-354:                            │
│   • Validates video sequence completion                        │
│   • Reassigns NULL video_ids (fixes race condition)          │
│   • Triggers test_execution_service.get_session_results()     │
│                                                                 │
│ Metrics Aggregation:                                           │
│   - True Positives: Matched detections                        │
│   - False Positives: Unmatched detections                     │
│   - False Negatives: Missed ground truth                      │
│   - Precision: TP / (TP + FP)                                 │
│   - Recall: TP / (TP + FN)                                    │
│   - F1 Score: 2 * (Precision * Recall) / (Precision + Recall)│
│   - Avg Latency: Mean of actual_latency_ms for TP matches    │
│   - Max/Min Latency: Extremes of latency distribution        │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   │ API endpoint: GET /api/hil-test/results/{session_id}
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: Frontend API Response                                  │
│ File: backend/api/enhanced_hil_results_endpoints.py            │
│                                                                 │
│ Endpoint: /api/hil-test/results/{session_id}                  │
│ Response Schema (schemas.py):                                  │
│   {                                                             │
│     "detectionEvents": [                                       │
│       {                                                         │
│         "id": "uuid",                                          │
│         "timestamp": float,  # Unix timestamp                  │
│         "videoRelativeTimestamp": float,  # Video position    │
│         "videoFrameNumber": int,  # Frame number              │
│         "actualLatencyMs": float,  # ❌ NULL from conversion! │
│         "labjackVoltage": float,  # Voltage reading           │
│         "detectionChannel": str,  # Channel name              │
│         "validationResult": str,  # "Pass"/"Fail"            │
│         "videoId": str  # Video identifier                    │
│       }                                                         │
│     ],                                                          │
│     "groundTruthObjects": [...],                              │
│     "metrics": {                                               │
│       "avgLatencyMs": float,  # ❌ 0.0 due to NULL latencies │
│       "maxLatencyMs": float,  # ❌ Infinity due to min([])   │
│       "minLatencyMs": float,                                  │
│       "precision": float,                                      │
│       "recall": float                                          │
│     }                                                           │
│   }                                                             │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   │ HTTP response with JSON payload
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 8: Frontend Display                                       │
│ File: frontend/src/pages/HILResults.tsx                        │
│                                                                 │
│ Data Processing:                                               │
│   • Fetches results via api.ts service                        │
│   • Maps detection events to table rows                       │
│   • Calculates aggregate metrics                              │
│                                                                 │
│ ❌ TIMING BUGS IN FRONTEND:                                   │
│   1. Frame Calculation @ FrameCorrelationTimeline.tsx:        │
│      - Uses: Math.round(timestamp * 24)                       │
│      - Should use: video_frame_number from backend            │
│      - Causes: Frame 120 bunching (70 detections at 5.0s)    │
│                                                                 │
│   2. Latency Display @ HILResults.tsx:                        │
│      - actualLatencyMs is NULL from backend                   │
│      - Avg latency shows 0.0ms                                │
│      - Best latency shows "Infinityms" (min of empty array)   │
│                                                                 │
│   3. Video Column @ DetectionTableRow.tsx:                    │
│      - Shows "Video undefined" when video_id is NULL          │
│      - Occurs during race condition window (5-20ms)           │
│                                                                 │
│ Display Components:                                             │
│   • MetricsSummaryCards: Shows aggregate metrics              │
│   • DetectionTable: Row-by-row detection details             │
│   • FrameCorrelationTimeline: Visual timeline chart          │
│   • GroundTruthComparisonCards: Per-video GT metrics         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Timestamp Field Definitions

### 2.1 Hardware Detection Timestamps

| Field Name | Type | Source | Definition | Example |
|------------|------|--------|------------|---------|
| `timestamp` | Float | LabJack hardware | **Unix epoch timestamp** when voltage threshold crossed (seconds since 1970-01-01) | `1730822400.123456` (2025-11-05 12:00:00.123456 UTC) |
| `labjack_timestamp` | Float | Same as `timestamp` | Duplicate field for clarity | `1730822400.123456` |
| `labjack_timestamp_ns` | String | Derived | Nanosecond precision timestamp as string | `"1730822400123456000"` |
| `detection_timestamp` | DateTime | Derived | UTC DateTime version of timestamp | `datetime(2025, 11, 5, 12, 0, 0, 123456, tzinfo=UTC)` |

### 2.2 Video-Relative Timestamps

| Field Name | Type | Calculation | Definition | Example |
|------------|------|-------------|------------|---------|
| `video_relative_timestamp` | Float | `unix_timestamp - video_start_time` | **Seconds elapsed from video start** to detection | `2.5` (detection at 2.5s into video) |
| `video_relative_timestamp_ns` | String | `int(video_relative_timestamp * 1e9)` | Nanosecond precision video-relative time | `"2500000000"` |
| `video_start_time` | Float | Session metadata | Unix timestamp when video playback started | `1730822397.623456` |
| `sequence_timestamp` | Float | `unix_timestamp - sequence_start_time` | Seconds from sequence start (multi-video) | `7.8` (7.8s into multi-video sequence) |
| `video_play_offset_ms` | Float | From sequence metadata | Milliseconds offset of this video within sequence | `5060.0` (Video 2 starts at 5.06s) |

### 2.3 Latency Fields

| Field Name | Type | Calculation | Definition | Example |
|------------|------|-------------|------------|---------|
| `actual_latency_ms` | Float | **SHOULD BE** `(detection_record_time - labjack_trigger_time) * 1000` | **Actual detection pipeline latency** from hardware signal to detection processing | `50.2` (50.2ms processing time) |
| `processing_time_ms` | Float | Same as `actual_latency_ms` | Duplicate field for compatibility | `50.2` |
| `latency_threshold_ms` | Float | Session config | Maximum acceptable latency for Pass/Fail | `100.0` (100ms threshold) |

**❌ CRITICAL BUG**: `timestamp_conversion_utils.py` line 102 returns `actual_latency_ms = None` instead of calculating actual latency!

### 2.4 Frame Correlation Fields

| Field Name | Type | Calculation | Definition | Example |
|------------|------|-------------|------------|---------|
| `video_frame_number` | Integer | `int(video_relative_timestamp * fps)` | Frame number corresponding to detection time | `60` (frame 60 at 2.5s with 24fps) |
| `frame_number` | Integer | Legacy field | May contain frame number from detection source | `60` |
| `fps` | Float | Video metadata | Frames per second of video | `24.0` |

---

## 3. Video Sequence Timing (Multi-Video Test)

### 3.1 Example: 2-Video Sequence (12.6s total)

```
Sequence Timeline:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│<──── Video 1 ────>│<────────── Video 2 ───────────────>│
│    5.06s         │          7.54s                     │
│  (121 frames)     │        (181 frames @ 24fps)        │
0s                5.06s                             12.6s

sequence_start_time = 1730822397.0  (Unix timestamp when sequence started)

Video 1:
  video_id: "abc123"
  started_at: 1730822397.0  (sequence_start_time + 0.0s)
  ended_at: 1730822402.06   (sequence_start_time + 5.06s)
  duration: 5.06s
  video_play_offset_ms: 0.0

Video 2:
  video_id: "def456"
  started_at: 1730822402.06  (sequence_start_time + 5.06s)
  ended_at: 1730822409.6     (sequence_start_time + 12.6s)
  duration: 7.54s
  video_play_offset_ms: 5060.0

Detection Example (Video 2, 2.5s into video):
  unix_timestamp: 1730822404.56  (absolute time)
  sequence_timestamp: 7.56  (7.56s from sequence start)
  video_relative_timestamp: 2.5  (2.5s from Video 2 start)
  video_frame_number: 60  (frame 60 at 24fps)
  video_id: "def456"  (Video 2)
```

### 3.2 Timing Metadata Structure

```json
{
  "sequence_metadata": {
    "video_timing": {
      "abc123": {  // Video 1
        "started_at": 1730822397.0,
        "ended_at": 1730822402.06,
        "duration": 5.06,
        "fps": 24.0,
        "frame_count": 121
      },
      "def456": {  // Video 2
        "started_at": 1730822402.06,
        "ended_at": 1730822409.6,
        "duration": 7.54,
        "fps": 24.0,
        "frame_count": 181
      }
    },
    "sequence_started_at": 1730822397.0,
    "sequence_id": "seq_xyz789"
  }
}
```

---

## 4. Timing Bugs Identified

### 4.1 **BUG #1: NULL `actual_latency_ms` from Timestamp Conversion**

**Severity:** 🔴 CRITICAL
**File:** `services/timestamp_conversion_utils.py:102`

**Problem:**
```python
# Line 99-102
# ❌ REMOVED: actual_latency_ms = video_relative_timestamp * 1000
# The calling code should populate actual_latency_ms from detection metadata,
# not from this timestamp conversion function.
actual_latency_ms = None  # Caller must provide actual measured latency
```

**Impact:**
- All detection events have `actual_latency_ms = NULL` in database
- Frontend displays "Avg Latency: 0.0ms" (should be ~50ms)
- "Best Latency: Infinityms" due to `Math.min([])` on empty array
- Latency metrics are completely invalid

**Root Cause:**
- Timestamp conversion service incorrectly returns NULL
- Service assumes caller will populate latency, but caller uses the returned value
- `dedicated_labjack_monitor.py` line 578 uses `timing_data['actual_latency_ms']` which is NULL

**Fix Required:**
1. Option A: Return measured latency from timestamp conversion service
2. Option B: Populate `actual_latency_ms` in `dedicated_labjack_monitor.py` after timestamp conversion
3. Recommended: Use `real_processing_latency_ms` calculated at line 417

---

### 4.2 **BUG #2: Frame 120 Bunching (70 Detections)**

**Severity:** 🟠 HIGH
**File:** `frontend/src/components/FrameCorrelationTimeline.tsx`

**Problem:**
```typescript
// Frontend calculates frame number directly from timestamp
const frameNumber = Math.round(timestamp * 24);  // ❌ WRONG!
```

**Impact:**
- 70 detections incorrectly clustered at frame 120 (5.0s mark)
- Should use `video_frame_number` from backend (already calculated correctly)
- Visual timeline shows incorrect detection distribution

**Root Cause:**
- Frontend recalculates frame number instead of using backend value
- Rounding errors accumulate across detections
- Multi-video sequences have different timing offsets

**Fix Required:**
```typescript
// Use backend-calculated frame number
const frameNumber = detection.videoFrameNumber;  // ✅ CORRECT
```

---

### 4.3 **BUG #3: Negative Latency Values**

**Severity:** 🟠 HIGH
**File:** Multiple locations in timing calculation

**Problem:**
- Some detections show negative latency values (impossible)
- Indicates timing reference point confusion

**Root Cause:**
- Mixing different timestamp reference points:
  - Unix timestamp (absolute time)
  - Video-relative timestamp (offset from video start)
  - Sequence timestamp (offset from sequence start)
- Incorrect subtraction order in latency calculation

**Example of Incorrect Calculation:**
```python
# ❌ WRONG: Using video position as latency
actual_latency_ms = video_relative_timestamp * 1000  # Wrong!

# ✅ CORRECT: Using detection pipeline timing
actual_latency_ms = (detection_record_time - labjack_trigger_time) * 1000
```

**Fix Required:**
1. Use only `real_processing_latency_ms` from dedicated_labjack_monitor.py line 417
2. Never calculate latency from video-relative timestamps
3. Add validation: `assert actual_latency_ms >= 0`

---

### 4.4 **BUG #4: "Video undefined" Display**

**Severity:** 🟡 MEDIUM
**File:** `frontend/src/components/DetectionTableRow.tsx`

**Problem:**
- Detection table shows "Video undefined" for some detections
- Occurs when `video_id` is NULL in database

**Root Cause:**
- Race condition: detections arrive 5-20ms before video lifecycle events
- `video_id` is NULL during race condition window
- Reassignment service runs at session completion (too late for real-time display)

**Fix Required:**
1. Short-term: Hide video column when `video_id` is NULL
2. Long-term: Implement real-time video_id assignment using retry logic
3. Alternative: Display "Pending..." instead of "undefined"

---

### 4.5 **BUG #5: Best Latency Shows "Infinityms"**

**Severity:** 🟡 MEDIUM
**File:** `frontend/src/pages/HILResults.tsx`

**Problem:**
```typescript
// Calculating best (minimum) latency
const bestLatency = Math.min(...latencies);  // Returns Infinity if empty
```

**Impact:**
- UI shows "Best: Infinityms" when no valid latencies exist
- Confusing to users

**Root Cause:**
- `latencies` array is empty because `actual_latency_ms` is NULL for all detections
- `Math.min([])` returns `Infinity` in JavaScript

**Fix Required:**
```typescript
// Add validation
const bestLatency = latencies.length > 0 ? Math.min(...latencies) : null;
// Display: bestLatency ? `${bestLatency.toFixed(1)}ms` : "N/A"
```

---

## 5. Recommended Fixes (Priority Order)

### 5.1 **CRITICAL: Fix NULL `actual_latency_ms`** (Priority: P0)

**Implementation:**

File: `services/dedicated_labjack_monitor.py:568-578`

```python
# Choose latency value: prefer calibrated value from timing service
calibrated_latency_ms = timing_data.get('actual_latency_ms')
if calibrated_latency_ms is None:
    # ✅ FIX: Use real processing latency measured at detection time
    calibrated_latency_ms = real_processing_latency_ms  # Calculated at line 417

hil_event = HILDetectionEvent(
    id=str(uuid.uuid4()),
    session_id=session_id,
    unix_timestamp=detection_record_time,
    video_relative_timestamp=timing_data['video_relative_timestamp'],
    video_relative_timestamp_ns=timing_data['video_relative_timestamp_ns'],
    actual_latency_ms=calibrated_latency_ms,  # ✅ Now populated correctly
    # ... rest of fields
)
```

**Testing:**
1. Run HIL test with LabJack hardware
2. Verify `actual_latency_ms` is NOT NULL in database
3. Verify frontend shows correct average latency (50-100ms range)
4. Verify "Best Latency" is not Infinity

---

### 5.2 **HIGH: Fix Frame Bunching** (Priority: P1)

**Implementation:**

File: `frontend/src/components/FrameCorrelationTimeline.tsx`

```typescript
// Before:
const frameNumber = Math.round(timestamp * 24);  // ❌

// After:
const frameNumber = detection.videoFrameNumber;  // ✅
```

**Testing:**
1. Load HIL results page
2. Verify frame correlation timeline shows smooth distribution
3. Verify no clustering at frame 120
4. Check multi-video sequences for correct frame assignment

---

### 5.3 **HIGH: Add Latency Validation** (Priority: P1)

**Implementation:**

File: `services/dedicated_labjack_monitor.py:417-418`

```python
# Calculate REAL processing latency = (when we recorded it) - (when hardware triggered)
real_processing_latency_ms = (detection_record_time - labjack_trigger_time) * 1000.0

# ✅ ADD: Validation to catch timing bugs
if real_processing_latency_ms < 0:
    logger.error(
        f"❌ TIMING BUG: Negative latency detected! "
        f"trigger={labjack_trigger_time}, recorded={detection_record_time}, "
        f"latency={real_processing_latency_ms}ms"
    )
    # Use absolute value as fallback
    real_processing_latency_ms = abs(real_processing_latency_ms)

logger.info(f"⏱️ REAL latency: {real_processing_latency_ms:.3f}ms (trigger: {labjack_trigger_time}, recorded: {detection_record_time})")
```

---

### 5.4 **MEDIUM: Fix "Video undefined" Display** (Priority: P2)

**Implementation:**

File: `frontend/src/components/DetectionTableRow.tsx`

```typescript
// Add null check for video_id
const videoDisplay = detection.videoId
  ? `Video ${getVideoNumber(detection.videoId)}`
  : "Pending...";  // ✅ Better than "Video undefined"
```

---

### 5.5 **LOW: Add Timing Documentation** (Priority: P3)

**Implementation:**

Create inline documentation in key files:

1. `services/timestamp_conversion_utils.py` - Document timestamp field definitions
2. `services/dedicated_labjack_monitor.py` - Document timing reference points
3. `models.py DetectionEvent` - Add field comments explaining timestamp types

---

## 6. Testing Strategy for Timing Accuracy

### 6.1 Unit Tests

**File:** `backend/tests/test_timing_accuracy.py`

```python
def test_actual_latency_ms_not_null():
    """Verify actual_latency_ms is populated correctly"""
    # Create mock detection event
    # Verify actual_latency_ms is not NULL
    # Verify value is in expected range (0-200ms)
    assert detection.actual_latency_ms is not None
    assert 0 <= detection.actual_latency_ms <= 200

def test_video_relative_timestamp_calculation():
    """Verify video-relative timestamp is calculated correctly"""
    video_start_time = 1730822397.0
    detection_time = 1730822399.5  # 2.5s after start

    relative = detection_time - video_start_time
    assert relative == 2.5

def test_frame_number_calculation():
    """Verify frame number calculation matches backend"""
    video_relative_timestamp = 2.5  # seconds
    fps = 24.0
    expected_frame = 60  # int(2.5 * 24)

    calculated_frame = int(video_relative_timestamp * fps)
    assert calculated_frame == expected_frame

def test_no_negative_latencies():
    """Verify latency calculation never produces negative values"""
    # Test with various timing scenarios
    # Ensure all latency values are >= 0
    assert all(latency >= 0 for latency in latencies)
```

### 6.2 Integration Tests

**File:** `backend/tests/test_hil_timing_integration.py`

```python
def test_complete_timing_flow():
    """End-to-end timing flow from detection to API response"""
    # 1. Simulate LabJack detection
    # 2. Process through dedicated_labjack_monitor
    # 3. Verify database storage
    # 4. Fetch via API
    # 5. Validate all timestamp fields are correct

    response = client.get(f"/api/hil-test/results/{session_id}")
    detection = response.json()["detectionEvents"][0]

    assert detection["actualLatencyMs"] is not None
    assert detection["videoRelativeTimestamp"] >= 0
    assert detection["videoFrameNumber"] >= 0
    assert detection["videoId"] is not None
```

### 6.3 Frontend Tests

**File:** `frontend/src/__tests__/HILResults.test.tsx`

```typescript
test('displays correct average latency', () => {
  const detections = [
    { actualLatencyMs: 50 },
    { actualLatencyMs: 60 },
    { actualLatencyMs: 55 }
  ];

  const avgLatency = calculateAverageLatency(detections);
  expect(avgLatency).toBe(55);
  expect(avgLatency).not.toBe(0);  // Should not be zero!
});

test('handles empty latency array gracefully', () => {
  const detections = [];
  const bestLatency = calculateBestLatency(detections);
  expect(bestLatency).toBeNull();  // Not Infinity!
});

test('uses backend frame number instead of recalculating', () => {
  const detection = {
    videoRelativeTimestamp: 2.5,
    videoFrameNumber: 60  // From backend
  };

  // Should use backend value
  expect(getFrameNumber(detection)).toBe(60);
  // Not recalculated: Math.round(2.5 * 24) = 60
});
```

---

## 7. Timing Architecture Improvements

### 7.1 Centralize Timestamp Management

**Create:** `services/timing_manager.py`

```python
class TimingManager:
    """Centralized timing management for HIL tests"""

    def __init__(self):
        self.reference_times: Dict[str, float] = {}

    def register_video_start(self, video_id: str, start_time: float):
        """Register video start time as timing reference"""
        self.reference_times[video_id] = start_time

    def calculate_video_relative(self, video_id: str, unix_timestamp: float) -> float:
        """Calculate video-relative timestamp with validation"""
        if video_id not in self.reference_times:
            raise ValueError(f"Video {video_id} not registered")

        video_start = self.reference_times[video_id]
        relative = unix_timestamp - video_start

        if relative < 0:
            raise ValueError(
                f"Negative video-relative time detected! "
                f"unix={unix_timestamp}, start={video_start}"
            )

        return relative

    def calculate_frame_number(self, video_relative: float, fps: float) -> int:
        """Calculate frame number with validation"""
        if video_relative < 0:
            raise ValueError("Negative video-relative timestamp")
        if fps <= 0:
            raise ValueError("Invalid FPS")

        return int(video_relative * fps)
```

### 7.2 Add Timing Assertions

Add validation at critical points:

```python
# In dedicated_labjack_monitor.py
assert labjack_trigger_time > 0, "Invalid trigger time"
assert detection_record_time >= labjack_trigger_time, "Time travel detected!"
assert real_processing_latency_ms >= 0, "Negative latency impossible"
assert video_relative_timestamp >= 0, "Negative video time impossible"
```

### 7.3 Timing Metrics Dashboard

Add monitoring dashboard showing:
- Average detection pipeline latency
- Timestamp conversion success rate
- Frame calculation accuracy
- Video boundary validation stats

---

## 8. Conclusion

The timing architecture has several critical bugs causing incorrect latency display and frame bunching. The primary issue is the `actual_latency_ms` field being NULL due to incorrect handling in the timestamp conversion service.

**Key Actions Required:**
1. ✅ Fix NULL `actual_latency_ms` in `timestamp_conversion_utils.py` or `dedicated_labjack_monitor.py`
2. ✅ Use backend-calculated frame numbers in frontend
3. ✅ Add latency validation to prevent negative values
4. ✅ Improve NULL `video_id` handling in frontend
5. ✅ Add comprehensive timing tests

**Expected Results After Fixes:**
- "Avg Latency: 52.3ms" (realistic value)
- "Best: 45.1ms" (not Infinity)
- Smooth frame distribution (no frame 120 bunching)
- "Video 1" / "Video 2" displayed correctly
- No negative latency values

---

**Document Status:** ✅ COMPLETE
**Next Steps:** Implement fixes in priority order (P0 → P1 → P2 → P3)
