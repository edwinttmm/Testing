# LabJack Detection and Ground Truth Correlation - Deep Dive Analysis

**Research Date:** 2025-11-26
**Analyzed Codebase:** `/home/rigade/Testing/ai-model-validation-platform/backend`
**Agent:** Research and Analysis Specialist

---

## Executive Summary

This document provides a comprehensive analysis of the LabJack hardware integration, voltage-based detection system, ground truth correlation algorithms, and HIL (Hardware-in-the-Loop) test execution flow. The system implements a sophisticated real-time detection pipeline with optimal matching algorithms for validation.

---

## 1. LabJack Hardware Integration Architecture

### 1.1 Connection Modes

The system supports three connection modes with automatic fallback (**services/labjack_service.py**):

```python
class ConnectionMode(Enum):
    BRIDGE = "bridge"   # Windows bridge via HTTP/WebSocket (WSL support)
    DIRECT = "direct"   # Direct USB/hardware connection
    MOCK = "mock"       # Simulation mode (explicitly disabled for HIL)
```

**Connection Strategy:**
- **WSL Environment:** Bridge → Direct → FAIL (no mock fallback for HIL safety)
- **Native Linux/Windows:** Direct → Bridge → FAIL
- **Mock Mode:** Requires explicit `allow_mock=True` parameter to prevent accidental simulation during HIL testing

### 1.2 Hardware Communication Layers

#### Layer 1: Hardware Interface (`services/labjack_service.py`)

**Direct Mode:**
- Uses official LabJack LJM library or enhanced USB stub (`labjack_usb_stub.py`)
- Supports both polling and stream modes
- Error handling for LJM error codes (1224, 1227, 2605, etc.)

**Bridge Mode:**
- HTTP REST API for commands (`/status`, `/read-analog`, `/stream-start`)
- WebSocket for real-time data streaming
- Automatic reconnection with exponential backoff

**Key Methods:**
```python
start_stream_mode(channels, scan_rate, scans_per_read)  # Hardware-timed acquisition
read_stream_mode()  # Read buffered samples with backlog monitoring
stop_stream_mode()  # Halt streaming and release resources
```

#### Layer 2: Connection Management (`services/labjack_connection_manager.py`)

- Global stream state tracking (prevents error 2605 during concurrent operations)
- Session-based connection lifecycle
- Health monitoring with active validation reads
- Prevents premature disconnection during active test sessions

**Stream State Protection:**
```python
set_stream_active(True)   # Block polling during streaming
is_stream_active()        # Check before validation reads
```

---

## 2. Detection System Architecture

### 2.1 Voltage Threshold Detection Flow

The detection pipeline converts voltage readings into discrete detection events through multiple stages:

```
┌────────────────────────────────────────────────────────────────┐
│                     DETECTION PIPELINE                          │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. VOLTAGE ACQUISITION                                         │
│     ├─ Stream Mode: Hardware-timed buffered reads (200 Hz)     │
│     └─ Polling Mode: Software-timed single reads (100 Hz)      │
│                                                                 │
│  2. THRESHOLD CROSSING DETECTION                                │
│     ├─ Voltage > 2.5V threshold check                          │
│     ├─ Constant voltage mode: Bypass debounce (HIL mode)       │
│     └─ Signal quality validation (unless constant voltage)     │
│                                                                 │
│  3. TEMPORAL FILTERING                                          │
│     ├─ Duplicate detection suppression (2ms merge window)      │
│     ├─ Debounce logic (10ms for normal mode)                   │
│     └─ Clustering by time threshold (20ms window)              │
│                                                                 │
│  4. VIDEO WINDOW VALIDATION                                     │
│     ├─ Check detection within video timing bounds              │
│     ├─ Apply grace period (±2s hardware pre-trigger)           │
│     └─ Filter cross-video detections in multi-video sequences  │
│                                                                 │
│  5. DETECTION EVENT CREATION                                    │
│     ├─ Timestamp synchronization (epoch → video-relative)      │
│     ├─ Quality metadata (timing_sync_quality flag)             │
│     └─ Database persistence with batch commits                 │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 Detection Configuration Parameters

**File:** `services/labjack_detection_service.py`

```python
@dataclass
class DetectionConfig:
    voltage_threshold: float = 2.5          # Detection trigger level
    debounce_ms: int = 10                   # Minimum time between detections
    sample_rate: int = 100                  # Polling frequency

    # PRIORITY 2 FIX: Constant Voltage Mode
    constant_voltage_mode: bool = True      # Bypass debounce for HIL testing

    # Continuous sampling mode
    continuous_mode: bool = False           # Emit detections continuously
    continuous_interval_ms: int = 40        # ~25 Hz (24 fps video rate)
    continuous_lower_bound: float = 2.5     # Lower voltage threshold
    continuous_upper_bound: float = None    # Upper threshold (None = unlimited)
```

**Key Features:**

1. **Constant Voltage Mode (HIL Default):**
   - Bypasses debounce logic for continuous voltage scenarios
   - Captures detection at frame rate instead of only on threshold crossing
   - Critical for constant voltage HIL testing where VRU presence = constant HIGH signal

2. **Signal Quality Validation:**
   - 10% margin above threshold required (2.5V → 2.75V minimum)
   - Variance check: σ² ≤ (threshold × 0.2)²
   - **Bypassed in constant_voltage_mode**

### 2.3 Detection Event Data Structure

```python
@dataclass
class DetectionEvent:
    channel: str                    # AIN0, AIN1, etc.
    timestamp: datetime             # Epoch timestamp (UTC)
    voltage: float                  # Measured voltage value
    threshold: float                # Configured threshold (2.5V)
    session_id: str                 # Test session UUID
    frame_number: Optional[int]     # Video frame number (if available)
    confidence: float = 1.0         # Detection confidence score

    # Timing synchronization
    video_relative_timestamp: Optional[float]  # Seconds from video start
    video_frame_number: Optional[int]          # Frame index
    timing_sync_quality: str = "high"          # Quality indicator

    # Metadata
    state: str = "threshold_cross"  # Detection type
    metadata: Dict[str, Any]        # Additional context
```

### 2.4 Voltage Reading Methods

#### Stream Mode (High-Speed Continuous)
```python
# Start hardware-timed stream at 200 Hz
success, actual_rate = labjack_service.start_stream_mode(
    channels=["AIN0", "AIN1"],
    scan_rate=200,
    scans_per_read=20  # Buffer size
)

# Read buffered samples (called in monitoring loop)
data, backlog, success = labjack_service.read_stream_mode()
# Returns: [AIN0_scan0, AIN1_scan0, AIN0_scan1, AIN1_scan1, ...]
```

**Stream Mode Characteristics:**
- Hardware-timed acquisition (precise timing)
- Buffered reads with backlog monitoring
- Typical rate: 200 Hz for detection
- Used for continuous monitoring during HIL tests

#### Polling Mode (Software-Timed)
```python
# Read single voltage value
voltage = await labjack_service.read_single_voltage("AIN0")
# Returns: float (0.0 if error or stream active)
```

**Polling Mode Characteristics:**
- Software-timed, lower precision
- Used for health checks and status queries
- **Blocked during stream mode** (prevents error 2605)
- Fallback when streaming unavailable

---

## 3. Ground Truth Generation and Storage

### 3.1 Ground Truth Object Structure

**File:** `models.py` - `GroundTruthObject` table

```python
class GroundTruthObject:
    id: str (UUID)
    video_id: str (Foreign Key → Video)
    frame_number: int              # Frame index in video
    timestamp: float               # Time in seconds from video start
    class_label: str               # "pedestrian", "cyclist", etc.

    # Bounding box (YOLO format)
    x: float                       # X coordinate
    y: float                       # Y coordinate
    width: float                   # Box width
    height: float                  # Box height

    # Quality metrics
    confidence: float              # Detection confidence
    validated: bool                # Manual validation flag
    difficult: bool                # Difficult object flag

    # Timestamps
    created_at: datetime
    deleted_at: datetime           # Soft delete support
```

### 3.2 Ground Truth Sources

1. **Pre-recorded Ground Truth Files:**
   - JSON format with frame-by-frame annotations
   - Uploaded via `/api/ground-truth/upload` endpoint
   - Parsed and stored in database before HIL test execution

2. **ML-Generated Ground Truth:**
   - YOLO model inference on video frames
   - Batch processing for entire video sequences
   - Confidence threshold filtering (default: 0.5)

3. **Manual Annotation:**
   - UI-based annotation tool
   - Frame-by-frame object labeling
   - Validation workflow support

### 3.3 Ground Truth Query for Sessions

**File:** `src/services/ground_truth_matching_service.py`

```python
def _get_ground_truth_for_session(db, test_session, session_id):
    """
    Supports both single-video and multi-video sequences.

    Query Strategy:
    - Single video: Direct query by video_id
    - Multi-video sequence: Batch query with video_id IN clause
    - Large sequences (>25k objects): Per-video caching strategy
    """

    if test_session.has_video_sequence:
        # Multi-video: Get all video IDs from sequence
        video_ids = _get_sequence_video_ids(db, test_session.sequence_id)

        # Batch query with soft delete filter
        ground_truth_objects = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id.in_(video_ids),
            GroundTruthObject.deleted_at.is_(None)
        ).order_by(
            GroundTruthObject.video_id.asc(),
            GroundTruthObject.timestamp.asc()
        ).all()
    else:
        # Single video
        ground_truth_objects = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == test_session.video_id,
            GroundTruthObject.deleted_at.is_(None)
        ).order_by(
            GroundTruthObject.timestamp
        ).all()

    return ground_truth_objects
```

**Performance Optimization:**
- Batch query for sequences with <25,000 GT objects
- Per-video caching for larger sequences
- Query timeout protection (30s limit)
- Eager loading with `selectinload()` to prevent N+1 queries

---

## 4. Ground Truth Matching Algorithm

### 4.1 Temporal Matching Overview

The system uses a **Hungarian Algorithm (Kuhn-Munkres)** for optimal assignment between detections and ground truth objects, with intelligent fallback strategies.

**File:** `services/optimal_matching_service.py`

```python
def optimal_detection_matching(
    ground_truth_times: List[float],     # GT timestamps (video-relative)
    detection_times: List[float],        # Detection timestamps
    tolerance_seconds: float = 0.1,      # ±100ms window (default)
    ground_truth_video_ids: List[str] = None,  # Multi-video support
    detection_video_ids: List[str] = None
) -> Dict[str, Any]:
```

### 4.2 Matching Algorithm Selection

```
┌─────────────────────────────────────────────────────────────┐
│                 MATCHING ALGORITHM DECISION TREE             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Input: n_gt ground truth, n_det detections                 │
│                                                              │
│  1. Check Constant Voltage Scenario                         │
│     IF n_det < n_gt × 0.95 (low detection rate)             │
│     THEN: Many-to-One Matching                              │
│     ├─ Single detection can match multiple GT frames        │
│     └─ Appropriate for constant voltage HIL tests           │
│                                                              │
│  2. Check Dataset Size                                      │
│     IF max(n_gt, n_det) > 1000                              │
│     THEN: Greedy Matching (performance fallback)            │
│     └─ O(n*m) complexity, < 1s execution                    │
│                                                              │
│  3. Run Hungarian Algorithm with Timeout                    │
│     IF execution time > 30 seconds                          │
│     THEN: Greedy Fallback                                   │
│     ELSE: Return optimal assignment                         │
│     └─ O(n³) complexity, guaranteed optimal                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Hungarian Algorithm Implementation

**Step 1: Build Cost Matrix**

```python
# Create n_gt × n_det cost matrix
cost_matrix = np.full((n_gt, n_det), float('inf'))

for i, gt_time in enumerate(ground_truth_times):
    for j, det_time in enumerate(detection_times):
        time_diff = abs(det_time - gt_time)

        # Filter 1: Cross-video pairs (multi-video sequences)
        if gt_video_ids[i] != det_video_ids[j]:
            continue  # Cost remains infinity

        # Filter 2: Outside tolerance window
        if time_diff <= tolerance_seconds:
            cost_matrix[i, j] = time_diff
        # else: cost remains infinity
```

**Cost Matrix Properties:**
- **Finite values:** Valid matches within tolerance
- **Infinity values:** Invalid matches (outside tolerance or cross-video)
- **Sparse matrix:** Typical HIL test has ~10% valid matches

**Step 2: Pre-Aggregation (Constant Voltage Optimization)**

When `n_det >> n_gt` (e.g., 80 detections for 10 GT frames):

```python
def pre_aggregate_detections_by_frame(gt_times, det_times, tolerance):
    """
    Reduce many detections per frame to one detection per GT frame.

    Example:
    GT times: [1.0, 2.0, 3.0]  # 3 frames
    Detection times: [1.001, 1.005, 1.008, 2.002, 2.004, 3.001]  # 6 detections

    Pre-aggregation picks closest detection per GT:
    - GT 1.0 → Det 1.001 (index 0)
    - GT 2.0 → Det 2.002 (index 3)
    - GT 3.0 → Det 3.001 (index 5)

    Returns: ([1.001, 2.002, 3.001], [0, 3, 5])
    """
    aggregated_times = []
    original_indices = []

    for gt_time in gt_times:
        best_det_idx = min(
            enumerate(det_times),
            key=lambda x: abs(x[1] - gt_time) if abs(x[1] - gt_time) <= tolerance else inf
        )
        if best_det_idx:
            aggregated_times.append(det_times[best_det_idx])
            original_indices.append(best_det_idx)

    return aggregated_times, original_indices
```

**Step 3: Run Hungarian Algorithm**

```python
from scipy.optimize import linear_sum_assignment

# Pre-filter infeasible rows/columns (all costs = infinity)
feasible_rows = [i for i in range(n_gt) if any(cost_matrix[i, :] < 1e9)]
feasible_cols = [j for j in range(n_det) if any(cost_matrix[:, j] < 1e9)]

# Create reduced cost matrix
reduced_matrix = cost_matrix[np.ix_(feasible_rows, feasible_cols)]

# Run Hungarian algorithm
row_ind, col_ind = linear_sum_assignment(reduced_matrix)

# Map back to original indices
matches = [(feasible_rows[i], feasible_cols[j])
           for i, j in zip(row_ind, col_ind)
           if reduced_matrix[i, j] < 1e9]
```

**Step 4: Classify Results**

```python
# True Positives: Matched pairs within tolerance
true_positives = [
    (gt_idx, det_idx, latency_ms)
    for gt_idx, det_idx in matches
    if cost_matrix[gt_idx, det_idx] < tolerance_seconds
]

# False Positives: Unmatched detections
matched_det_indices = set(det_idx for _, det_idx, _ in true_positives)
false_positives = [i for i in range(n_det) if i not in matched_det_indices]

# False Negatives: Unmatched ground truth
matched_gt_indices = set(gt_idx for gt_idx, _, _ in true_positives)
false_negatives = [i for i in range(n_gt) if i not in matched_gt_indices]
```

### 4.4 Many-to-One Matching (Constant Voltage Mode)

For HIL tests with constant voltage where detections < GT frames:

```python
def many_to_one_gt_matching(gt_times, det_times, tolerance):
    """
    Allow single detection to satisfy multiple adjacent GT frames.

    Algorithm:
    1. For each GT frame, find closest detection within tolerance
    2. Same detection can match multiple GT frames
    3. GT frames without match become FN
    4. Detections not matched become FP
    """
    true_positives = []
    used_detections = set()

    for gt_idx, gt_time in enumerate(gt_times):
        # Find closest detection within tolerance
        best_det_idx = min(
            range(len(det_times)),
            key=lambda j: abs(det_times[j] - gt_time)
        )

        if abs(det_times[best_det_idx] - gt_time) <= tolerance:
            latency_ms = (det_times[best_det_idx] - gt_time) * 1000.0
            true_positives.append((gt_idx, best_det_idx, latency_ms))
            used_detections.add(best_det_idx)

    false_negatives = [i for i in range(len(gt_times))
                       if i not in [tp[0] for tp in true_positives]]
    false_positives = [i for i in range(len(det_times))
                       if i not in used_detections]

    return {
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'algorithm': 'many_to_one',
        'detections_used': used_detections
    }
```

### 4.5 Greedy Fallback Algorithm

Used when Hungarian times out or dataset is too large:

```python
def greedy_detection_matching(gt_times, det_times, tolerance):
    """
    O(n*m) greedy first-match algorithm.

    Limitations:
    - Suboptimal: First match wins even if not globally optimal
    - Example pathological case:
      GT = [1.0, 2.0], Det = [1.05, 1.06]
      Greedy: GT1→Det1, GT2 unmatched
      Optimal: GT1→Det1, GT2→Det2 (better global assignment)
    """
    true_positives = []
    used_detections = set()

    for gt_idx, gt_time in enumerate(gt_times):
        best_match = None
        best_diff = float('inf')

        for det_idx, det_time in enumerate(det_times):
            if det_idx in used_detections:
                continue

            diff = abs(det_time - gt_time)
            if diff <= tolerance and diff < best_diff:
                best_match = det_idx
                best_diff = diff

        if best_match is not None:
            latency_ms = (det_times[best_match] - gt_time) * 1000.0
            true_positives.append((gt_idx, best_match, latency_ms))
            used_detections.add(best_match)

    # Classify unmatched
    matched_gt = set(tp[0] for tp in true_positives)
    false_negatives = [i for i in range(len(gt_times)) if i not in matched_gt]
    false_positives = [i for i in range(len(det_times)) if i not in used_detections]

    return {
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'algorithm': 'greedy'
    }
```

---

## 5. Correlation Parameters and Thresholds

### 5.1 Timing Configuration

**File:** `config/timing_config.py`

```python
# Matching tolerance: How close detection must be to GT for valid match
DEFAULT_MATCHING_TOLERANCE_MS = 250  # ±250ms window
MATCHING_TOLERANCE_SECONDS = 0.25    # 0.25 seconds

# Grace period: Allow early/late detections outside video bounds
DEFAULT_GRACE_PERIOD_MS = 2000       # ±2s hardware pre-trigger window
GRACE_PERIOD_SECONDS = 2.0

# Detection debounce: Minimum time between consecutive detections
DETECTION_DEBOUNCE_MS = 10           # 10ms (reduced for 24fps support)

# Voltage threshold
VOLTAGE_THRESHOLD_V = 2.5            # Detection trigger level
```

### 5.2 Tolerance Window Justification

**250ms Tolerance (±125ms from GT):**

1. **Video Frame Rate Considerations:**
   - 24 fps = 41.67ms per frame
   - 30 fps = 33.33ms per frame
   - Tolerance covers ±3 frames at 24fps

2. **System Latency Sources:**
   - LabJack sampling: ~5-10ms
   - Detection processing: ~5-15ms
   - Video frame timing drift: ±50ms
   - Total expected latency: 60-75ms

3. **Safety Margin:**
   - 250ms tolerance provides 3× safety factor
   - Reduces false negatives from timing jitter
   - Accommodates variable system loads

### 5.3 Drift Compensation

**File:** `src/services/drift_measurement_service.py`

The system measures and compensates for clock drift between video and hardware timestamps:

```python
class DriftMeasurementService:
    """
    Measures timing drift between video playback and LabJack sampling.

    Captures:
    - video_start_time_epoch: Video playback start (system clock)
    - first_detection_epoch: First LabJack detection (system clock)

    Calculates drift:
    drift_ms = (first_detection_epoch - video_start_time_epoch) * 1000
    """

    def apply_drift_compensation(self, detection_timestamp):
        """
        Adjust detection timestamp to align with video timeline.

        compensated_ts = original_ts - (drift_ms / 1000.0)
        """
        drift_ms = self.get_drift_ms()
        return detection_timestamp - (drift_ms / 1000.0)
```

**Drift Sources:**
- Video playback start vs. monitoring start timing mismatch
- System clock precision differences
- Processing delays in detection pipeline

---

## 6. Latency Calculation

### 6.1 Latency Definition

**Latency = Detection Timestamp - Ground Truth Timestamp**

- **Positive latency:** Detection occurred after GT object appeared
- **Negative latency:** Detection occurred before GT object (pre-trigger)
- **Zero latency:** Perfect timing alignment

### 6.2 Latency Calculation in Matching

```python
# In optimal_detection_matching
for gt_idx, det_idx in matched_pairs:
    gt_time = ground_truth_times[gt_idx]
    det_time = detection_times[det_idx]

    # Signed latency in milliseconds
    latency_ms = (det_time - gt_time) * 1000.0

    true_positives.append((gt_idx, det_idx, latency_ms))
```

### 6.3 False Positive Latency Marker

```python
# False Positives get sentinel latency value
FP_LATENCY_MARKER = 10000.0  # 10 seconds

# This marks FP detections clearly and excludes them from statistics
if detection_type == "FP":
    latency_ms = FP_LATENCY_MARKER
```

### 6.4 Latency Statistics

**File:** `src/services/ground_truth_matching_service.py`

```python
@dataclass
class SessionMetrics:
    mean_latency_ms: float          # Average detection latency
    std_latency_ms: float           # Standard deviation
    max_latency_ms: float           # Worst-case latency
    min_latency_ms: float           # Best-case latency
    within_tolerance_percentage: float  # % within ±250ms
    latency_sample_count: int       # Number of TP used for stats
    per_video_latency_samples: Dict[str, int]  # Per-video breakdown
```

**Latency Filtering:**
- Only TP (True Positive) detections included in statistics
- FP detections excluded (latency = 10000ms marker)
- FN (False Negative) have no latency value

---

## 7. HIL Test Execution Flow

### 7.1 Complete HIL Test Sequence

```
┌──────────────────────────────────────────────────────────────────┐
│                   HIL TEST EXECUTION FLOW                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. PRE-TEST SETUP                                                │
│     ├─ Load ground truth from JSON file                          │
│     ├─ Parse and store GT objects in database                    │
│     ├─ Initialize LabJack hardware connection                    │
│     ├─ Validate hardware health (temperature read)               │
│     └─ Create test session record in database                    │
│                                                                   │
│  2. START MONITORING                                              │
│     ├─ Start LabJack stream mode (200 Hz, AIN0/AIN1)            │
│     ├─ Initialize detection monitor with session ID              │
│     ├─ Start drift measurement service                           │
│     └─ Begin video playback (external system)                    │
│                                                                   │
│  3. REAL-TIME DETECTION LOOP                                      │
│     ├─ Read stream buffer (20 scans × 2 channels)               │
│     ├─ Check voltage threshold (>2.5V)                           │
│     ├─ Apply constant voltage mode logic                         │
│     ├─ Validate detection within video window                    │
│     ├─ Create detection event with metadata                      │
│     ├─ Batch commit to database (every 100 events or 1s)        │
│     └─ Emit WebSocket notification to frontend                   │
│                                                                   │
│  4. POST-TEST CORRELATION                                         │
│     ├─ Stop monitoring and stream mode                           │
│     ├─ Fetch all detections from database                        │
│     ├─ Fetch all ground truth from database                      │
│     ├─ Apply drift compensation to detections                    │
│     ├─ Run optimal matching algorithm (Hungarian)                │
│     ├─ Classify TP/FP/FN with latency calculations              │
│     ├─ Store detection comparisons in database                   │
│     └─ Calculate and store session metrics                       │
│                                                                   │
│  5. RESULTS GENERATION                                            │
│     ├─ Compute precision, recall, F1 score                       │
│     ├─ Calculate mean/std/min/max latency                        │
│     ├─ Generate latency histograms                               │
│     ├─ Create per-video breakdown (multi-video sequences)        │
│     └─ Update test session with final results                    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 7.2 Database Schema for HIL Results

**DetectionComparison Table:**
```python
class DetectionComparison:
    id: str (UUID)
    test_session_id: str (Foreign Key)
    ground_truth_id: str (Foreign Key → GroundTruthObject)
    detection_event_id: str (Foreign Key → DetectionEvent, nullable)

    # Classification
    match_type: str  # "TP", "FP", "FN"

    # Timing
    temporal_offset: float       # Time difference (seconds)
    latency_ms: float           # Detection latency (milliseconds)

    # Quality
    iou_score: float            # Intersection over Union (spatial)
    confidence: float           # Detection confidence

    # Metadata
    created_at: datetime
```

### 7.3 Multi-Video Sequence Support

**VideoTestSequence Table:**
```python
class VideoTestSequence:
    id: str (UUID)
    name: str                          # Sequence name
    video_ids: List[str]               # Ordered list of video IDs
    sequence_order: List[Dict]         # Detailed sequence metadata
    total_duration: float              # Total sequence duration
    video_timing_map: Dict[str, Dict]  # Per-video timing info
```

**Ground Truth Expansion for Sequences:**
```python
# Query GT across all videos in sequence
video_ids = sequence.video_ids  # ["video1", "video2", "video3"]

ground_truth_objects = db.query(GroundTruthObject).filter(
    GroundTruthObject.video_id.in_(video_ids),
    GroundTruthObject.deleted_at.is_(None)
).order_by(
    GroundTruthObject.video_id.asc(),
    GroundTruthObject.timestamp.asc()
).all()
```

**Detection Assignment to Videos:**
- Each detection tagged with `video_id` during capture
- Detections assigned to current video based on timing window
- Cross-video matches filtered out during correlation

---

## 8. Algorithm Performance Characteristics

### 8.1 Hungarian Algorithm Complexity

**Time Complexity:** O(n³) where n = max(n_gt, n_det)

**Execution Time Examples:**
- 10×10 matrix: < 1ms
- 100×100 matrix: ~10ms
- 1,000×1,000 matrix: ~1s
- 5,000×5,000 matrix: ~73s (timeout threshold)

**Space Complexity:** O(n²) for cost matrix storage

### 8.2 Optimization Strategies

**1. Pre-Aggregation:**
- Reduces 80:10 detection-to-GT ratio to ~10:10
- Cuts matching time from 73s to < 1s
- Applied automatically when `n_det > n_gt × 2`

**2. Timeout Protection:**
- 30-second timeout with greedy fallback
- Prevents session timeouts on large datasets
- Max size threshold: 1,000 elements

**3. Sparse Matrix Optimization:**
- Pre-filter infeasible rows/columns (all costs = infinity)
- Reduce matrix size before Hungarian algorithm
- Typically reduces by 50-70% for HIL tests

**4. Multi-Video Filtering:**
- Filter cross-video pairs in cost matrix construction
- Prevents invalid matches from being considered
- Reduces search space by ~50% in 2-video sequences

### 8.3 Algorithm Selection Tradeoffs

| Algorithm | Complexity | Optimal? | Max Dataset | Use Case |
|-----------|-----------|----------|-------------|----------|
| Hungarian | O(n³) | Yes | 1,000 | Normal HIL tests |
| Many-to-One | O(n×m) | No | Unlimited | Constant voltage HIL |
| Greedy | O(n×m) | No | Unlimited | Large datasets, timeouts |

**Recommendation:**
- **< 1,000 pairs:** Use Hungarian (optimal results)
- **1,000-10,000 pairs:** Use greedy (acceptable performance)
- **Constant voltage:** Use many-to-one (appropriate for scenario)

---

## 9. Data Structures and Flow Diagrams

### 9.1 Detection Event Lifecycle

```
Voltage Reading → Threshold Check → Signal Quality → Debounce Filter
      ↓                  ↓                ↓                ↓
   Raw ADC         >2.5V check     Variance OK     Not duplicate
      ↓                  ↓                ↓                ↓
Video Window → Detection Event → Batch Queue → Database Commit
      ↓                  ↓                ↓                ↓
 Within bounds    Metadata added    Buffer full   Persistence
```

### 9.2 Ground Truth Matching Pipeline

```
Session Start → Fetch Detections → Fetch Ground Truth
      ↓                  ↓                  ↓
Drift Compensation → Video-Relative Times → Build Cost Matrix
      ↓                  ↓                  ↓
Cross-Video Filter → Tolerance Filter → Run Hungarian Algorithm
      ↓                  ↓                  ↓
Extract Matches → Calculate Latencies → Classify TP/FP/FN
      ↓                  ↓                  ↓
Store Comparisons → Compute Metrics → Update Session
```

### 9.3 Memory and Storage Patterns

**In-Memory Structures:**
- Detection events: Held in batch queue (max 100 events or 1s)
- Stream buffer: LabJack hardware buffer (20 scans × 2 channels)
- Cost matrix: NumPy array (n_gt × n_det, sparse)

**Database Storage:**
- Detection events: Inserted in batches (reduces transaction overhead)
- Ground truth objects: Queried once per session (cached)
- Detection comparisons: Bulk insert after matching

**WebSocket Streaming:**
- Real-time detection notifications to frontend
- Throttled to prevent UI overload (100ms minimum interval)
- JSON payload with detection metadata

---

## 10. Key Insights and Recommendations

### 10.1 Critical Success Factors

1. **Constant Voltage Mode:**
   - Essential for HIL testing with continuous VRU presence
   - Bypasses debounce to capture at frame rate
   - Default enabled (`constant_voltage_mode=True`)

2. **Drift Compensation:**
   - Corrects for video/hardware timing mismatch
   - Critical for accurate latency calculations
   - Measured during session initialization

3. **Many-to-One Matching:**
   - Appropriate for low detection rate scenarios
   - Allows single detection to satisfy multiple GT frames
   - Prevents artificial FN inflation

4. **Video Window Validation:**
   - Grace period (±2s) accommodates hardware pre-trigger
   - Prevents early/late detections from being discarded
   - Essential for multi-video sequence support

### 10.2 Performance Bottlenecks

1. **Hungarian Algorithm Timeout:**
   - Occurs with >1,000 detections or GT objects
   - Mitigated with pre-aggregation and greedy fallback
   - Consider batch processing for large sequences

2. **Database Query Performance:**
   - Multi-video sequences can have >25,000 GT objects
   - Mitigated with batch queries and per-video caching
   - Soft delete filter adds overhead (use indexes)

3. **Stream Buffer Overflow:**
   - Occurs when read rate < sample rate
   - Monitored via backlog counter
   - Mitigated with buffer size tuning (scans_per_read)

### 10.3 Testing and Validation

**Recommended Test Scenarios:**

1. **Baseline Test:**
   - Single video, ~100 GT objects, ~100 detections
   - Verify Hungarian algorithm produces optimal results
   - Check latency statistics are reasonable (50-100ms mean)

2. **Constant Voltage Test:**
   - 10 GT frames, 80+ detections
   - Verify many-to-one matching is applied
   - Confirm no artificial FN from detection rate mismatch

3. **Multi-Video Sequence Test:**
   - 3 videos, ~300 GT objects total
   - Verify cross-video filtering works correctly
   - Check per-video metrics are calculated

4. **Edge Case Test:**
   - No detections (all FN)
   - No ground truth (all FP)
   - Perfect match (100% precision/recall)

---

## 11. Troubleshooting Guide

### 11.1 Common Issues

**Issue:** High False Positive Rate

**Diagnosis:**
- Check detection debounce setting (should be 10ms)
- Review voltage threshold (2.5V may be too sensitive)
- Inspect signal quality variance
- Check for electrical noise on analog input

**Solution:**
```python
# Increase debounce for noisy environments
config.debounce_ms = 20  # from 10ms

# Or tighten signal quality requirements
margin_threshold = threshold * 1.2  # from 1.1
```

---

**Issue:** High False Negative Rate

**Diagnosis:**
- Check tolerance window (should be 250ms)
- Verify drift compensation is applied
- Review constant voltage mode setting
- Check for detections outside video window

**Solution:**
```python
# Increase tolerance if needed
tolerance_ms = 500  # from 250ms

# Ensure constant voltage mode enabled
config.constant_voltage_mode = True

# Check grace period
GRACE_PERIOD_MS = 3000  # from 2000ms
```

---

**Issue:** Matching Algorithm Timeout

**Diagnosis:**
- Check dataset size (n_gt × n_det)
- Review pre-aggregation logs
- Verify greedy fallback occurred

**Solution:**
```python
# Adjust timeout threshold
HUNGARIAN_MAX_SIZE = 500  # from 1000

# Or force greedy algorithm
result = greedy_detection_matching(...)
```

---

**Issue:** Cross-Video Detections

**Diagnosis:**
- Check video_id assignment logic
- Verify video timing boundaries
- Review grace period configuration

**Solution:**
```python
# Tighten video window validation
grace_period_ms = 1000  # from 2000ms

# Or enforce strict video boundaries
detection_window.strict_mode = True
```

---

## 12. File Reference Guide

### 12.1 Core Detection Files

| File Path | Description | Key Functions |
|-----------|-------------|---------------|
| `services/labjack_service.py` | Hardware interface layer | `start_stream_mode()`, `read_stream_mode()`, `read_single_voltage()` |
| `services/labjack_detection_service.py` | Detection pipeline | `start_monitoring()`, `_create_detection_event()`, `_should_record_detection()` |
| `services/labjack_connection_manager.py` | Connection lifecycle | `set_stream_active()`, `is_stream_active()` |

### 12.2 Matching Algorithm Files

| File Path | Description | Key Functions |
|-----------|-------------|---------------|
| `services/optimal_matching_service.py` | Hungarian algorithm | `optimal_detection_matching()`, `many_to_one_gt_matching()`, `pre_aggregate_detections_by_frame()` |
| `src/services/ground_truth_matching_service.py` | Matching orchestration | `match_detections_to_ground_truth()`, `_perform_temporal_matching()` |

### 12.3 Configuration Files

| File Path | Description | Key Parameters |
|-----------|-------------|----------------|
| `config/timing_config.py` | Timing constants | `MATCHING_TOLERANCE_MS`, `GRACE_PERIOD_MS`, `DETECTION_DEBOUNCE_MS` |
| `config/labjack_config.py` | Hardware settings | `sample_rate`, `voltage_threshold`, `channels` |

### 12.4 Data Models

| File Path | Description | Key Tables |
|-----------|-------------|------------|
| `models.py` | Database schema | `DetectionEvent`, `GroundTruthObject`, `DetectionComparison`, `TestSession` |

---

## 13. Conclusion

The LabJack detection and ground truth correlation system implements a sophisticated pipeline that converts real-time voltage readings into validated detection events through optimal matching algorithms. Key strengths include:

1. **Robust Hardware Integration:** Multi-mode connection with automatic fallback
2. **Intelligent Detection:** Constant voltage mode for HIL scenarios
3. **Optimal Matching:** Hungarian algorithm with timeout protection
4. **Multi-Video Support:** Batch processing for large sequences
5. **Comprehensive Metrics:** Precision, recall, F1, latency statistics

The system is production-ready for HIL validation testing with appropriate safeguards for performance and accuracy.

---

**Document Version:** 1.0
**Last Updated:** 2025-11-26
**Maintained By:** Research and Analysis Team
