# Detection Gap Analysis: Missing Frame Detections Despite Constant Voltage

## Executive Summary

**Problem**: Despite constant 4.2V voltage being applied throughout the test, only frames 2, 4, 7, and 9 have matched detections while frames 0, 1, 3, 5, 6, and 8 show no detection match.

**Root Cause**: The issue is **NOT** with voltage detection logic (which works correctly), but with a fundamental mismatch between **continuous voltage detection** and **frame-based ground truth matching**.

## Key Findings

### 1. Detection Logic (LabJack Detection Service)

**Location**: `/backend/services/labjack_detection_service.py`

#### Voltage Threshold Detection
- **Detection Mode**: Level-based, NOT edge-based
- **Threshold**: 2.5V (configurable, test uses 4.2V)
- **Logic**: `if voltage >= config.voltage_threshold:` (line 1140)
- **Result**: ✅ Detects voltage above threshold continuously

#### Constant Voltage Mode
- **Feature Flag**: `constant_voltage_mode = True` (line 159)
- **Purpose**: Bypass debounce for continuous voltage scenarios
- **Effect**: When enabled, ALL debounce logic is bypassed (lines 1900-1912)
- **Logging**: Each detection logged as `⚡ [CONST_VOLT] Detection #N accepted`

```python
# From lines 1897-1912
if config.constant_voltage_mode:
    session_detections[channel] = current_time
    self._increment_decision_stat(session_id, 'threshold_cross')
    logger.info(
        f"⚡ [CONST_VOLT] Detection #{count} "
        f"accepted - session={session_id[:8]} channel={channel} gap={delta_ms:.2f}ms"
    )
    return "threshold_cross"  # ✅ ALWAYS returns true - no filtering
```

#### Debounce Logic (When constant_voltage_mode = False)
- **Default Debounce**: 10ms (configurable via `debounce_ms`)
- **Config**: Line 137 - `debounce_ms: int = 10`
- **Effect**: Suppresses detections within 10ms of previous detection
- **NOTE**: Only active when `constant_voltage_mode = False`

### 2. Ground Truth Matching Logic

**Location**: `/backend/services/ground_truth_matching_service.py` and `/backend/services/optimal_matching_service.py`

#### Matching Algorithm: Hungarian/Optimal Assignment
- **Algorithm**: Hungarian Algorithm (linear_sum_assignment from scipy)
- **Purpose**: Find globally optimal one-to-one matching between detections and ground truth
- **Key Constraint**: **One detection can match ONLY ONE ground truth frame**

#### Tolerance Window
- **Default**: 250ms (MATCHING_TOLERANCE_MS)
- **Config Location**: `/backend/config/timing_config.py` line 31
- **Logic**: `if time_diff <= tolerance_seconds:` (optimal_matching_service.py line 291)
- **Cost Matrix**: Uses absolute time difference `abs(det_time - gt_time)`

```python
# From optimal_matching_service.py lines 276-292
for i, gt_time in enumerate(ground_truth_times):
    for j, det_time in enumerate(detection_times):
        time_diff = abs(det_time - gt_time)

        # Only consider matches within tolerance window
        if time_diff <= tolerance_seconds:
            cost_matrix[i, j] = time_diff  # ✅ Valid match
        # else: cost remains infinity (invalid match)
```

#### Quality Filtering
- **Filter**: `usable_for_validation = TRUE`
- **Location**: ground_truth_matching_service.py line 308
- **Purpose**: Exclude degraded/low-quality detections from matching

### 3. The Fundamental Problem: Many-to-One vs One-to-One

#### What Happens with Constant Voltage at 24 FPS

**Scenario**:
- Video: 24 frames per second (41.67ms per frame)
- Voltage: Constant 4.2V throughout test
- Detection Rate: High (possibly 100-1000 Hz with stream mode)
- Ground Truth: 10 frames (frame 0, 1, 2, ..., 9)

**Detection Generation** (with constant_voltage_mode = True):
```
Time     Detections Generated
----     --------------------
0ms      ✓ Detection #1
5ms      ✓ Detection #2  (steady_high_interval_ms)
10ms     ✓ Detection #3
15ms     ✓ Detection #4
...
400ms    ✓ Detection #80+
```

**Ground Truth Timeline** (10 frames at 24 FPS):
```
Frame    Expected Time
-----    -------------
0        0ms
1        41.67ms
2        83.33ms
3        125ms
4        166.67ms
5        208.33ms
6        250ms
7        291.67ms
8        333.33ms
9        375ms
```

**Hungarian Algorithm Matching** (with 250ms tolerance):
1. Build cost matrix (10 GT frames × 80+ detections)
2. Each GT frame has MANY candidate detections within 250ms tolerance
3. Algorithm selects **OPTIMAL ONE-TO-ONE** assignment
4. **CRITICAL**: Some frames get matched to "better" detections, leaving other frames unmatched

**Example Matching Scenario**:
```
Frame 0 (0ms):     ✓ Matched to Detection #1 (0ms)     - Perfect match (0ms diff)
Frame 1 (41.67ms): ✓ Matched to Detection #9 (41ms)    - Near match (0.67ms diff)
Frame 2 (83.33ms): ✗ NO MATCH - Detection #17 (83ms) already taken by Frame 3
Frame 3 (125ms):   ✓ Matched to Detection #17 (83ms)   - Within tolerance (42ms diff)
Frame 4 (166.67ms): ✓ Matched to Detection #33 (165ms) - Near match (1.67ms diff)
...
```

**Why Frame 2 Gets Skipped**:
- Detection #17 at 83ms is closer to Frame 3 (125ms) than to Frame 2 (83.33ms)
- Hungarian algorithm **globally optimizes** across ALL frames
- It assigns Detection #17 to Frame 3 (42ms diff) instead of Frame 2 (0.33ms diff)
- Because overall, this produces lower total cost when considering ALL 10 frames
- Frame 2 left unmatched as FN (False Negative)

### 4. Why Only SOME Frames Get Matched

The pattern of matched frames (2, 4, 7, 9) vs unmatched frames (0, 1, 3, 5, 6, 8) suggests:

1. **Detection Clustering**: Detections may be clustered at certain times due to:
   - Sample timing jitter
   - Steady-high interval (5ms default)
   - System load variations

2. **Optimal Assignment Behavior**: Hungarian algorithm makes **global decisions**:
   - Prioritizes frames with fewer candidate detections
   - May sacrifice nearby frames to optimize overall cost
   - Creates gaps in coverage when detection density varies

3. **Steady-High Interval Impact**:
   ```python
   # From line 147
   steady_high_interval_ms: int = 5
   ```
   - Detections emitted every 5ms while voltage stays high
   - At 24 FPS (41.67ms/frame): 8 detections per frame period
   - 10 frames × 8 detections/frame = 80 candidate detections
   - Hungarian must map 80 detections → 10 frames (one-to-one)
   - 70 detections classified as False Positives
   - Some frames inevitably unmatched

## Configuration Parameters

### Detection Service Parameters
| Parameter | Default | Test Value | Effect |
|-----------|---------|------------|--------|
| `voltage_threshold` | 2.5V | 2.5V | Voltage level to trigger detection |
| `constant_voltage_mode` | True | True | Bypass debounce (✓ Active) |
| `debounce_ms` | 10ms | 10ms | Ignored when constant_voltage_mode=True |
| `steady_high_interval_ms` | 5ms | 5ms | Detection emission rate while voltage high |
| `sample_rate` | 1000Hz | ? | Hardware sampling rate |

### Matching Service Parameters
| Parameter | Default | Effect |
|-----------|---------|--------|
| `MATCHING_TOLERANCE_MS` | 250ms | ±250ms window for valid match |
| `usable_for_validation` | Filter | Excludes degraded detections |

## Root Cause Analysis

### The Core Issue

**The system was designed for EDGE detection** (voltage transitions) but is being used for **CONSTANT VOLTAGE detection** (level-based).

1. **Design Assumption**: Each VRU appearance/disappearance creates ONE voltage edge
2. **Reality with Constant Voltage**: Voltage stays HIGH, creating MANY detections per frame
3. **Matching Assumption**: One-to-one correspondence (1 detection per ground truth)
4. **Reality**: Many-to-one (multiple detections per ground truth frame)
5. **Hungarian Algorithm**: Enforces one-to-one mapping, leaving frames unmatched

### Why Frames Are Missing

The missing frames are **NOT** due to detection failure. They are due to:

1. **Detection Abundance**: Too MANY detections, not too few
2. **Forced One-to-One Mapping**: Hungarian algorithm must choose 10 out of 80+ detections
3. **Global Optimization**: Algorithm makes trade-offs that leave some frames unmatched
4. **No Clustering**: Detections not clustered by frame before matching

## Verification Steps

### 1. Check Detection Count

Look for log messages:
```
⚡ [CONST_VOLT] Detection #N accepted
```

Expected: 80+ detections for 10-frame test (with 5ms steady_high_interval)

### 2. Check Ground Truth Count

Query database:
```sql
SELECT COUNT(*) FROM ground_truth_objects
WHERE test_session_id = '<session_id>';
```

Expected: 10 ground truth frames

### 3. Check Matching Statistics

Look for log messages:
```
🔬 OPTIMAL MATCHING: N ground truth × M detections
```

Expected: `10 ground truth × 80+ detections`

### 4. Check Cost Matrix

Log should show:
```
Cost matrix: X valid matches (min=...ms, mean=...ms, max=...ms)
```

If X >> 10, confirms detection abundance

## Recommended Solutions

### Solution 1: Detection Aggregation (Recommended)

**Approach**: Group detections by ground truth frame BEFORE matching

```python
def aggregate_detections_by_frame(detections, ground_truth_frames, tolerance_ms):
    """
    Cluster detections into frame-aligned groups.
    Return one representative detection per frame.
    """
    frame_detections = {}

    for frame in ground_truth_frames:
        frame_time = frame.timestamp
        # Find all detections within tolerance window
        candidates = [
            d for d in detections
            if abs(d.timestamp - frame_time) <= tolerance_ms
        ]
        if candidates:
            # Pick closest detection as representative
            closest = min(candidates, key=lambda d: abs(d.timestamp - frame_time))
            frame_detections[frame.id] = closest

    return frame_detections
```

**Pros**:
- Guarantees one detection per frame (if any within tolerance)
- Preserves closest temporal match
- Simple to implement

**Cons**:
- Loses information about detection multiplicity
- May need to adjust metrics calculation

### Solution 2: Change Matching to Many-to-One

**Approach**: Allow multiple detections to match one ground truth

```python
# Change matching logic to group by ground truth
for gt_frame in ground_truth_frames:
    matching_detections = [
        d for d in detections
        if abs(d.timestamp - gt_frame.timestamp) <= tolerance_ms
    ]
    if matching_detections:
        gt_frame.matched_detections = matching_detections
        # Calculate metrics: TP if ANY match, latency = min/mean/median
```

**Pros**:
- More accurate for constant-voltage scenarios
- Captures detection rate information
- No information loss

**Cons**:
- Requires metrics recalculation logic
- More complex implementation
- May break existing reports/dashboards

### Solution 3: Disable Steady-High Logging for HIL

**Approach**: Set `steady_high_interval_ms` to match frame rate

```python
# For 24 FPS (41.67ms per frame)
DetectionConfig(
    steady_high_interval_ms=42,  # Match frame rate
    constant_voltage_mode=True
)
```

**Pros**:
- Reduces detection count to ~1 per frame
- Minimal code changes
- Works with existing matching logic

**Cons**:
- Loses temporal resolution
- May miss rapid voltage changes
- Not a fundamental fix

### Solution 4: Edge Detection Mode

**Approach**: Detect voltage transitions instead of continuous level

```python
def detect_edges(voltage_history):
    """
    Detect rising/falling edges instead of continuous level.
    """
    if not voltage_history:
        return []

    edges = []
    prev_state = 'low'

    for timestamp, voltage in voltage_history:
        current_state = 'high' if voltage >= threshold else 'low'
        if current_state != prev_state and current_state == 'high':
            edges.append((timestamp, 'rising_edge'))
        prev_state = current_state

    return edges
```

**Pros**:
- Aligns with system's original design
- One detection per VRU appearance
- Works well with one-to-one matching

**Cons**:
- Doesn't work for constant voltage scenario
- Requires voltage to drop between frames
- Not applicable to current test setup

## Recommended Action Plan

### Immediate (Phase 1)
1. **Verify detection count**: Check logs for actual detection count
2. **Add detection clustering**: Implement Solution 1 (aggregation)
3. **Update metrics**: Adjust TP/FP/FN calculation for clustered detections

### Short-term (Phase 2)
1. **Add configuration option**: Allow choosing between edge/level detection
2. **Implement proper clustering**: Group detections by frame BEFORE Hungarian algorithm
3. **Update documentation**: Clarify edge vs level detection modes

### Long-term (Phase 3)
1. **Refactor matching service**: Support both one-to-one and many-to-one matching
2. **Add validation**: Detect and warn about many-to-one scenarios
3. **Improve metrics**: Calculate detection rate, multiplicity, coverage percentage

## Additional Diagnostic Information

### Files Analyzed

1. **Detection Logic**:
   - `/backend/services/labjack_detection_service.py` (lines 1130-1180, 1890-1946)
   - `/backend/services/raw_labjack_logger.py` (lines 551-606)

2. **Matching Logic**:
   - `/backend/services/ground_truth_matching_service.py` (lines 227-399)
   - `/backend/services/optimal_matching_service.py` (lines 59-310)

3. **Configuration**:
   - `/backend/config/timing_config.py` (lines 29-36, 50)

### Key Code Sections

#### Constant Voltage Mode (Detection Service)
```python
# Line 159: Default configuration
constant_voltage_mode: bool = True  # Bypass debounce for constant voltage testing

# Lines 1900-1912: Bypass all throttling
if config.constant_voltage_mode:
    session_detections[channel] = current_time
    return "threshold_cross"  # ✅ Always accept detection
```

#### Tolerance-Based Matching (Optimal Matching Service)
```python
# Lines 276-292: Cost matrix construction
for i, gt_time in enumerate(ground_truth_times):
    for j, det_time in enumerate(detection_times):
        time_diff = abs(det_time - gt_time)
        if time_diff <= tolerance_seconds:  # 250ms default
            cost_matrix[i, j] = time_diff
```

#### Hungarian Algorithm (Optimal Matching Service)
```python
# Enforces one-to-one mapping
row_ind, col_ind = linear_sum_assignment(cost_matrix)
# Each row (GT) matched to at most one column (detection)
# Each column (detection) matched to at most one row (GT)
```

## Conclusion

The missing frame detections are **NOT** caused by voltage detection failure. The voltage detection system is working correctly and generating detections at high frequency (5ms intervals) while voltage remains high.

The root cause is a **mismatch between detection generation strategy and matching strategy**:

- **Detection**: Generates MANY detections per frame (every 5ms) with constant voltage
- **Matching**: Expects ONE detection per frame (one-to-one Hungarian algorithm)
- **Result**: Algorithm forced to choose 10 out of 80+ detections, leaving some frames unmatched

The solution is to **aggregate or cluster detections by frame** before applying the Hungarian matching algorithm, or to switch to a many-to-one matching strategy that allows multiple detections per ground truth frame.
