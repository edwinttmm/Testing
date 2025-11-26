# LabJack Detection Debounce Configuration Analysis

## Executive Summary

**Problem**: Detection events are being missed with 125ms gaps between detections while ground truth (GT) shows continuous pedestrian presence.

**Root Cause**: Excessive debounce time (100ms) is suppressing valid detection events during continuous pedestrian presence.

**Impact**:
- Missing detections during continuous GT presence
- 125ms gaps = 100ms debounce + ~25ms processing/sampling overhead
- Detection rate significantly reduced for continuous scenarios

---

## Current Debounce Configuration

### 1. Primary Detection Service (`labjack_detection_service.py`)

**Location**: `/backend/services/labjack_detection_service.py:135`

```python
debounce_ms: int = 100  # Increased from 5ms to reduce false positives
```

**Comment Context**:
```python
# PRIORITY 4 FIX: Increased default debounce from 5ms to 100ms to eliminate duplicate detections
# Previous: 5ms (for 200 Hz) resulted in 45 FP (26% false positive rate)
# Current: 100ms aligns with timing_config.DETECTION_DEBOUNCE_MS
# Expected: FP reduction from 45 to 15-20, precision improvement from 74% to 86-88%
```

**Key Parameters**:
- **Default debounce**: 100ms
- **Sample rate**: 1000 Hz (default)
- **Voltage threshold**: 2.5V (default)
- **Debounce logic location**: Line 1647 in `_should_record_detection()` method

### 2. Centralized Timing Config (`timing_config.py`)

**Location**: `/backend/config/timing_config.py:49`

```python
DETECTION_DEBOUNCE_MS = 100  # Increased from 50ms to reduce false positives
```

**Comment Context**:
```python
# DETECTION DEBOUNCE CONFIGURATION
# Updated based on session daad8bf6-b5da-4423-abc4-a85e83bc1c16 FP analysis
# Previous: 50ms debounce (45 FP, 26% false positive rate)
# Root Cause: Duplicate/spurious detections caused by signal bounce, noise, or insufficient debouncing
# Many FPs have temporal offsets of ±15-20ms (within old debounce window)
# Recommended: 100-150ms debounce to eliminate duplicate detections
```

### 3. LabJack Hardware Config (`labjack_config.py`)

**Location**: `/backend/config/labjack_config.py:68`

```python
debounce_time_ms: float = 1.0  # Debounce time to prevent multiple triggers
```

**Environment Variable**: `LABJACK_DEBOUNCE_TIME_MS` (default: 1.0ms)

**Note**: This appears to be a hardware-level debounce separate from software debounce.

### 4. Raw LabJack Logger (`raw_labjack_logger.py`)

**Location**: `/backend/services/raw_labjack_logger.py:275`

```python
'debounce_ms': kwargs.get('debounce_ms', 20 if not kwargs.get('constant_voltage_mode', False) else 0)
# FIXED: Changed from 100ms to 20ms for 24 FPS video (41.67ms frame period)
```

**Note**: Uses 20ms default, or 0ms in constant voltage mode.

### 5. API Endpoint Default (`api_labjack_detection.py`)

**Location**: `/backend/api_labjack_detection.py:46`

```python
debounce_ms: int = Field(default=100, ge=10, le=5000, description="Debounce time in milliseconds")
```

**Validation**: 10ms minimum, 5000ms maximum

---

## Debounce Logic Implementation

### Core Algorithm (Lines 1625-1678 in `labjack_detection_service.py`)

```python
def _should_record_detection(self, session_id, channel, current_time, config):
    # Get last detection time for this channel
    session_detections = self.last_detection_times.setdefault(session_id, {})
    last_detection = session_detections.get(channel, datetime.min)
    debounce_delta = timedelta(milliseconds=config.debounce_ms)
    delta_ms = (current_time - last_detection).total_seconds() * 1000.0

    # BYPASS MODE: Constant voltage testing
    if config.constant_voltage_mode:
        session_detections[channel] = current_time
        return "threshold_cross"  # Bypass debounce completely

    # NORMAL DEBOUNCE: Suppress if within debounce window
    if current_time - last_detection < debounce_delta:
        # Check steady_high_logging (allows periodic samples during steady high)
        if config.steady_high_logging:
            steady_session = self.last_steady_high_emit_times.setdefault(session_id, {})
            last_steady = steady_session.get(channel, datetime.min)
            steady_delta = timedelta(milliseconds=max(1, config.steady_high_interval_ms))

            if current_time - last_steady >= steady_delta:
                steady_session[channel] = current_time
                return "steady_high"  # Allow periodic sample

        # SUPPRESSED: Within debounce window
        return None  # Detection suppressed

    # ACCEPTED: Outside debounce window
    session_detections[channel] = current_time
    return "threshold_cross"
```

**Detection States**:
1. **threshold_cross**: Initial detection, outside debounce window
2. **steady_high**: Periodic detection during steady high voltage (if enabled)
3. **continuous**: Continuous mode sampling (separate mode)
4. **None**: Suppressed by debounce

---

## Sampling Configuration

### Sampling Rate Hierarchy

1. **Default**: 1000 Hz (1ms interval)
2. **Stream Mode Threshold**: Automatically enabled at >100 Hz
3. **Hardware Config**: 10,000 Hz capable
4. **API Default**: 200 Hz (from `api_labjack_detection.py:47`)

**Stream Mode Configuration** (Lines 856-880):
- Enabled when: `sample_rate > 100 Hz` AND `use_stream_mode = True`
- Buffer size: `max(20, sample_rate // 10)` scans
- Example: 200 Hz → 20 scans = 100ms batches

### Polling Mode vs Stream Mode

**Polling Mode** (Lines 975-1002):
- Used when: `sample_rate <= 100 Hz` OR `use_stream_mode = False`
- Reads voltage on-demand via `connection_manager.read_voltage()`
- Poll interval: `1/sample_rate` seconds
- Environment override: `LABJACK_FORCE_POLLING=true`

**Stream Mode** (Lines 920-973):
- Hardware-timed continuous sampling
- Buffered reads from hardware stream
- Backlog warning at >50 scans
- More precise timing, higher throughput

---

## Detection Window Validation

### Video Window Clamping (Lines 1027-1051)

```python
# CRITICAL FIX: WINDOW VALIDATION - Only save if within video playback window
if video_start_timestamp_float is None:
    # Allow detection if timing not yet established
    pass
elif current_epoch_time < (video_start_timestamp_float - GRACE_PERIOD_SECONDS):
    # Pre-trigger detection allowed (>2s before video start)
    pass
elif not self._is_detection_within_video_window(...):
    # SKIP: Detection outside video window
    continue
```

**Grace Period**: 2000ms (2 seconds) before video start
**Purpose**: Allow hardware triggers that arrive before video playback starts

---

## Special Modes

### 1. Constant Voltage Mode

**Flag**: `constant_voltage_mode = True` (default: False)

**Purpose**: Testing with constant voltage injection at 24 FPS (41.67ms frame period)

**Behavior**:
- **Bypasses debounce completely** (Line 1633)
- Captures EVERY threshold crossing
- Use case: Testing with constant 4.2V injection
- Expected result: 100% detection rate (8/8 frames vs 37.5% with 100ms debounce)

**Configuration** (Line 426):
```python
constant_voltage_mode=kwargs.get('constant_voltage_mode', False)
```

**API Field** (`api_labjack_detection.py:51`):
```python
constant_voltage_mode: bool = Field(
    default=False,
    description="Bypass debounce for constant voltage testing (100% detection rate)"
)
```

### 2. Steady High Logging

**Flag**: `steady_high_logging = True` (default: True)

**Purpose**: Emit periodic detections while voltage remains above threshold

**Interval**: `steady_high_interval_ms = 5` (default: 5ms)

**Behavior**:
- Even when debounce suppresses new detections
- Allows periodic samples during continuous high voltage
- Interval is **much shorter** than debounce (5ms vs 100ms)
- Creates "steady_high" state detections

**Configuration** (Lines 1648-1660):
```python
if config.steady_high_logging:
    if current_time - last_steady >= steady_delta:
        return "steady_high"
```

### 3. Continuous Mode

**Flag**: `continuous_mode = True` (default: False)

**Purpose**: Emit detections continuously while voltage stays within bounds

**Parameters**:
- `continuous_lower_bound`: Lower voltage bound (default: threshold)
- `continuous_upper_bound`: Upper voltage bound (default: None/unlimited)
- `continuous_interval_ms`: Sampling interval (default: 5ms)

**Behavior**:
- Independent of threshold crossing
- Level detection instead of edge detection
- Used for continuous voltage monitoring

---

## Problem Analysis: 125ms Gap Issue

### Root Cause

**Current Configuration**:
- Debounce: 100ms
- Processing overhead: ~20-25ms
- Total gap: 125ms

**Ground Truth Scenario**:
- Pedestrian continuously present in frame
- Expected: Continuous/frequent detections
- Actual: Detection → 125ms gap → Detection

**Debounce Impact**:
```
Time: 0ms    → Detection 1 (threshold crossed)
Time: 10ms   → SUPPRESSED (within 100ms debounce)
Time: 20ms   → SUPPRESSED (within 100ms debounce)
Time: 40ms   → SUPPRESSED (within 100ms debounce)
Time: 80ms   → SUPPRESSED (within 100ms debounce)
Time: 100ms  → SUPPRESSED (within 100ms debounce)
Time: 125ms  → Detection 2 (100ms + processing delay)
```

### Why 100ms Debounce Was Chosen

**Historical Context** (from comments):
1. **Initial**: 5ms debounce (for 200 Hz sampling)
   - Result: 45 false positives (26% FP rate)
   - Problem: Signal bounce, noise, duplicates

2. **Intermediate**: 50ms debounce
   - Result: Still had duplicates with ±15-20ms temporal offsets
   - Problem: Within debounce window

3. **Current**: 100ms debounce
   - Goal: Eliminate duplicate detections
   - Expected: FP reduction to 15-20 (56% reduction)
   - Expected: Precision improvement 74% → 86-88%
   - Expected: F1 Score improvement 85% → 90-92%

### Trade-off

**100ms Debounce Optimizes For**:
- ✅ Reducing false positives (duplicate detections)
- ✅ Improving precision metrics
- ✅ Clean edge detection (single event per trigger)

**100ms Debounce Problems**:
- ❌ Misses events during continuous presence
- ❌ Under-reports detection rate for steady scenarios
- ❌ 125ms gaps don't match GT continuous presence
- ❌ Poor for level detection (vs edge detection)

---

## Recommended Configuration Changes

### Option 1: Reduce Debounce (Aggressive)

**Use Case**: Continuous pedestrian presence, prioritize detection rate

```python
debounce_ms = 20  # Down from 100ms
```

**Expected Impact**:
- ✅ Reduce gaps to ~40-45ms (20ms + processing)
- ✅ Better tracking of continuous presence
- ✅ ~2.5x more detections per second
- ❌ May increase false positives
- ❌ May need duplicate filtering post-processing

**Frame Period Alignment**:
- 24 FPS = 41.67ms frame period
- 20ms debounce = ~2 detections per frame max
- Better matches video frame timing

### Option 2: Enable Steady High Mode (Recommended)

**Use Case**: Preserve 100ms debounce but sample during continuous high

```python
debounce_ms = 100  # Keep current
steady_high_logging = True  # Already enabled
steady_high_interval_ms = 20  # Up from 5ms
```

**Expected Impact**:
- ✅ Keep low FP rate (100ms debounce on threshold crossings)
- ✅ Periodic samples during steady high (every 20ms)
- ✅ Distinguishable detection states (threshold_cross vs steady_high)
- ✅ Better continuous tracking without sacrificing precision
- ⚠️ Needs GT matching to understand "steady_high" state

**Detection Pattern**:
```
0ms:    threshold_cross  (initial detection)
20ms:   steady_high      (periodic sample)
40ms:   steady_high      (periodic sample)
60ms:   steady_high      (periodic sample)
80ms:   steady_high      (periodic sample)
100ms:  steady_high      (periodic sample)
120ms:  steady_high      (periodic sample)
```

### Option 3: Enable Constant Voltage Mode (Testing Only)

**Use Case**: Isolated testing, maximum detection rate

```python
constant_voltage_mode = True  # Bypass debounce
```

**Expected Impact**:
- ✅ 100% detection rate (no suppression)
- ✅ Maximum sensitivity
- ❌ **NOT RECOMMENDED FOR PRODUCTION** (high FP risk)
- ⚠️ Only for controlled testing environments

### Option 4: Adaptive Debounce (Advanced)

**Use Case**: Different debounce for different scenarios

**Pseudocode**:
```python
if signal_stable and above_threshold_duration > 200ms:
    # Continuous presence detected, reduce debounce
    debounce_ms = 20
else:
    # Edge detection, use full debounce
    debounce_ms = 100
```

**Expected Impact**:
- ✅ Best of both worlds (low FP + high detection rate)
- ✅ Context-aware filtering
- ❌ More complex implementation
- ❌ Needs signal stability detection

---

## Configuration Priority Hierarchy

### 1. API Request Override (Highest Priority)
```python
POST /api/detection/start
{
    "debounce_ms": 20,  # Override default
    "constant_voltage_mode": false
}
```

### 2. Environment Variable Override
```bash
export LABJACK_DEBOUNCE_TIME_MS=20.0
```

### 3. Code Defaults
- `labjack_detection_service.py`: 100ms
- `timing_config.py`: 100ms
- `labjack_config.py`: 1.0ms (hardware level)
- `raw_labjack_logger.py`: 20ms

---

## Specific File Changes Needed

### Change 1: Reduce Default Debounce in Detection Service

**File**: `/backend/services/labjack_detection_service.py`
**Line**: 135
**Current**:
```python
debounce_ms: int = 100  # Increased from 5ms to reduce false positives
```
**Recommended**:
```python
debounce_ms: int = 20  # Optimized for 24 FPS video (41.67ms frame period)
```

### Change 2: Reduce Debounce in Timing Config

**File**: `/backend/config/timing_config.py`
**Line**: 49
**Current**:
```python
DETECTION_DEBOUNCE_MS = 100  # Increased from 50ms to reduce false positives
```
**Recommended**:
```python
DETECTION_DEBOUNCE_MS = 20  # Optimized for continuous detection scenarios
```

### Change 3: Increase Steady High Interval

**File**: `/backend/services/labjack_detection_service.py`
**Line**: 144
**Current**:
```python
steady_high_interval_ms: int = 5
```
**Recommended**:
```python
steady_high_interval_ms: int = 20  # Match reduced debounce for consistency
```

### Change 4: Update API Documentation

**File**: `/backend/api_labjack_detection.py`
**Line**: 46
**Current**:
```python
debounce_ms: int = Field(default=100, ge=10, le=5000, ...)
```
**Recommended**:
```python
debounce_ms: int = Field(default=20, ge=5, le=5000, ...)
```

---

## Testing Recommendations

### Test 1: Baseline with Current Config (100ms)
- Record detection gaps
- Measure detection rate
- Count missed GT events

### Test 2: Reduced Debounce (20ms)
- Compare detection gaps (expect ~40-45ms)
- Measure detection rate (expect 2-3x increase)
- Monitor false positive rate

### Test 3: Steady High Mode Enhanced
- Set `steady_high_interval_ms = 20`
- Verify steady_high state detections
- Compare GT matching accuracy

### Test 4: Constant Voltage Mode
- Enable for isolated testing only
- Verify 100% detection rate
- Measure false positive baseline

### Test 5: Adaptive Debounce
- Implement signal stability detection
- Test with mixed scenarios (edges + continuous)
- Measure overall performance improvement

---

## Environment Variable Summary

### Current Environment Variables

```bash
# Hardware debounce (labjack_config.py)
LABJACK_DEBOUNCE_TIME_MS=1.0  # Default: 1.0ms (hardware level)

# Sample rate control
LABJACK_SAMPLE_RATE=10000     # Default: 10000 Hz
LABJACK_DEFAULT_STREAM_MODE=auto  # auto | true | false

# Voltage threshold
LABJACK_VOLTAGE_THRESHOLD=2.5  # Default: 2.5V

# Force polling mode (bypass stream)
LABJACK_FORCE_POLLING=false    # Default: false

# Detection threshold for monitors
LABJACK_DEFAULT_THRESHOLD=0.5  # Default: 0.5V (dedicated monitor)
```

### Recommended New Variables

```bash
# Software debounce override
LABJACK_DETECTION_DEBOUNCE_MS=20  # Override default 100ms

# Steady high mode configuration
LABJACK_STEADY_HIGH_INTERVAL_MS=20  # Override default 5ms

# Adaptive debounce mode (future)
LABJACK_ADAPTIVE_DEBOUNCE=true  # Enable adaptive debounce logic
```

---

## Signal Quality Filtering

### Current Implementation (Lines 1680-1714)

**Quality Checks**:
1. **Voltage Margin Check**: Signal must be >10% above threshold
   ```python
   margin_threshold = threshold * 1.1
   if voltage < margin_threshold:
       return False  # Too close to threshold, likely noise
   ```

2. **Signal Stability Check**: Low variance required (if history available)
   ```python
   variance = statistics.variance(signal_history[-5:])
   max_variance = (threshold * 0.2) ** 2  # Allow 20% variance
   if variance > max_variance:
       return False  # Too noisy/unstable
   ```

**Purpose**: Filter out noisy/bouncing signals that cause false positives

**Note**: This is applied BEFORE debounce check (Line 1055)

---

## Duplicate Detection Prevention

### Merge Window (Lines 1746-1772)

**Current Implementation**:
```python
merge_window_ms = 150.0  # Check for duplicates within 150ms
```

**Logic**:
- Before creating new detection event
- Check if existing detection within 150ms window
- If found, merge instead of creating duplicate
- Applied at Line 1063

**Purpose**: Additional layer of duplicate prevention (beyond debounce)

---

## Performance Metrics

### Batch Processing (Lines 2555-2615)

**Optimization for High-Frequency Detection**:
- Batch size threshold: 100 events
- Batch time threshold: 1.0 seconds
- Commits when either threshold reached

**Purpose**: Reduce database overhead at high detection rates (e.g., 200 Hz)

**Impact on Debounce**: None (batch processing happens after detection decision)

---

## Summary

### Current State
- **Debounce**: 100ms (optimized for low false positives)
- **Gap**: 125ms (100ms debounce + 25ms overhead)
- **Problem**: Missing detections during continuous GT presence

### Root Cause
- Trade-off between false positive reduction and detection rate
- 100ms debounce too aggressive for continuous scenarios
- Better suited for edge detection than level detection

### Recommended Solution
**Option 2: Enhanced Steady High Mode**
- Keep 100ms debounce for threshold crossings (low FP)
- Increase steady_high_interval to 20ms (better coverage)
- Distinguish detection states in GT matching logic
- Provides both precision and detection rate

### Quick Fix (Lowest Risk)
**Change steady_high_interval_ms**:
```python
# Line 144 in labjack_detection_service.py
steady_high_interval_ms: int = 20  # Up from 5ms
```
**Impact**: Immediate improvement in continuous detection without changing debounce

---

## File Locations Reference

| Configuration | File | Line | Current Value |
|---------------|------|------|---------------|
| Main debounce | `services/labjack_detection_service.py` | 135 | 100ms |
| Timing config debounce | `config/timing_config.py` | 49 | 100ms |
| Hardware debounce | `config/labjack_config.py` | 68 | 1.0ms |
| Raw logger debounce | `services/raw_labjack_logger.py` | 275 | 20ms |
| API default debounce | `api_labjack_detection.py` | 46 | 100ms |
| Steady high interval | `services/labjack_detection_service.py` | 144 | 5ms |
| Constant voltage flag | `services/labjack_detection_service.py` | 154 | False |
| Debounce logic | `services/labjack_detection_service.py` | 1625-1678 | Main algorithm |
| Signal quality check | `services/labjack_detection_service.py` | 1680-1714 | Quality filter |
| Duplicate merge | `services/labjack_detection_service.py` | 1063 | 150ms window |

---

## Decision Matrix

| Requirement | Debounce 100ms | Debounce 20ms | Steady High 20ms | Constant Voltage | Adaptive |
|-------------|----------------|---------------|------------------|------------------|----------|
| Low false positives | ✅ Excellent | ⚠️ Moderate | ✅ Excellent | ❌ Poor | ✅ Excellent |
| High detection rate | ❌ Poor | ✅ Excellent | ✅ Good | ✅ Excellent | ✅ Excellent |
| Continuous tracking | ❌ Poor | ✅ Good | ✅ Excellent | ✅ Excellent | ✅ Excellent |
| Edge detection | ✅ Excellent | ⚠️ Good | ✅ Excellent | ⚠️ Moderate | ✅ Excellent |
| Implementation complexity | ✅ Simple | ✅ Simple | ✅ Simple | ✅ Simple | ⚠️ Complex |
| Production ready | ✅ Yes | ⚠️ Needs testing | ✅ Yes | ❌ No | ⚠️ Needs development |

**Recommendation**: **Enhanced Steady High Mode (Column 3)** provides the best balance.

---

*Analysis generated: 2025-11-25*
*System: AI Model Validation Platform - LabJack Detection System*
