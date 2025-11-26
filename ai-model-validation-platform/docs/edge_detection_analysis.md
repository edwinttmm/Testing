# Edge Detection and Threshold Logic Analysis

## Executive Summary

**Problem**: Only 4 threshold_cross events recorded when expecting ~800-1000 from a 5-second video at 200 Hz.

**Root Cause Analysis**: The detection system has multiple filtering layers that severely restrict which voltage threshold crossings are recorded as detection events. The 4 events likely represent the only detections that passed ALL filtering criteria.

---

## Detection Logic Flow

### 1. Voltage Threshold Check (Lines 963-1008, 1304-1369)

**Location**: `_monitoring_loop()` method

**Logic**:
```python
# Line 971: Standard threshold check
voltage_in_range = voltage >= config.voltage_threshold

# Line 973: If voltage exceeds threshold
if voltage_in_range:
    # Proceed to additional checks
```

**Key Points**:
- Default threshold: `2.5V` (from DetectionConfig, line 130)
- This is the FIRST filter - voltage must be >= 2.5V
- This check happens every poll cycle or stream sample

---

## 2. Video Window Validation (Lines 982-1006, Critical Filter)

**Location**: `_is_detection_within_video_window()` method (lines 1554-1620)

**State Machine Logic**:

### Pre-Video Detection Filtering
```python
# Line 987-989: Pre-trigger detection allowed
elif current_epoch_time < (video_start_timestamp_float - GRACE_PERIOD_SECONDS):
    # Detection is MORE than grace period before video start - allow it (pre-trigger)
    logger.debug(f"✅ Pre-trigger detection allowed...")
```

### Window Validation (Lines 1554-1620)
```python
# Line 1587-1597: CRITICAL FILTER
grace_period_seconds = GRACE_PERIOD_SECONDS  # 2.0 seconds
earliest_valid_time = video_start_time - grace_period_seconds

if detection_timestamp < earliest_valid_time:
    # ❌ REJECT: Detection too early (>2s before video start)
    return False
```

**Configuration**:
- `GRACE_PERIOD_SECONDS = 2.0` (from config/timing_config.py, line 23)
- `GRACE_PERIOD_MS = 2000` (line 22)
- Detections must be within: `[video_start - 2s, video_end + buffer]`

**Skip Counters**:
- `skipped_early_detections`: Count detections before video window
- `skipped_late_detections`: Count detections after video window
- Lines 994-1006 track these statistics

**Why This Matters**:
- If video timing is off by even a few seconds, ALL detections could be filtered
- If `video_start_timestamp_float` is incorrect, this filter rejects everything
- The 4 recorded events are the ONLY ones within the time window

---

## 3. Debounce Filter (Lines 1456-1552, CRITICAL BOTTLENECK)

**Location**: `_should_record_detection()` method

**State Machine**:

### State Variables (Lines 168, 1516-1517)
```python
# Instance variable tracking last detection per channel
self.last_detection_times: Dict[str, Dict[str, datetime]] = {}

# In _should_record_detection:
session_detections = self.last_detection_times.setdefault(session_id, {})
last_detection = session_detections.get(channel, datetime.min)
```

### Debounce Logic (Lines 1518-1540)
```python
debounce_delta = timedelta(milliseconds=config.debounce_ms)
delta_ms = (current_time - last_detection).total_seconds() * 1000.0

# Line 1521: CRITICAL CHECK
if current_time - last_detection < debounce_delta:
    # ⛔ SUPPRESS: Detection too soon after last detection
    self._increment_decision_stat(session_id, 'debounce_skipped')
    logger.debug(
        f"⛔ [Decision] threshold suppressed by debounce for session={session_id} "
        f"channel={channel} gap={delta_ms:.2f}ms < debounce={config.debounce_ms}ms"
    )
    return None
```

**Configuration**:
- Default `debounce_ms = 100` (line 131 in DetectionConfig)
- Minimum gap between detections: **100 milliseconds**

**Critical Analysis**:
- **Maximum detection rate**: 1000ms / 100ms = **10 detections per second**
- **5-second video maximum**: 10 Hz × 5s = **50 detections maximum**
- **Expected from video**: 800-1000 detections at 200 Hz
- **Theoretical suppression**: 750-950 detections (93-95% of signals)

### State Update (Line 1542)
```python
# Only if debounce check passes
session_detections[channel] = current_time
```

**State Machine Behavior**:
- **State**: Last detection timestamp per (session_id, channel)
- **Transition**: Only updates when debounce gap is satisfied
- **Lock**: Thread-safe update (line 1468: `with self.lock:`)
- **Race Condition Prevention**: Atomic check-and-update (lines 1780-1782)

---

## 4. Steady-High vs Threshold-Cross Decision (Lines 1522-1534)

**Alternative Path**:
```python
if current_time - last_detection < debounce_delta:
    # Within debounce window
    if config.steady_high_logging:
        # Can still emit "steady_high" events at different interval
        if current_time - last_steady >= steady_delta:
            return "steady_high"  # Different event type
    return None  # Suppress
```

**Configuration**:
- `steady_high_logging = True` (line 140)
- `steady_high_interval_ms = 5` (line 141)
- This allows periodic sampling at 200 Hz (5ms intervals) during "high" state

**Why This Exists**:
- Captures continuous high voltage states
- Different event type from threshold_cross
- NOT counted in "threshold_cross" statistics

---

## 5. Continuous Mode Throttling (Lines 1469-1514)

**Alternative Detection Mode**:
```python
if config.continuous_mode:
    # Sample at fixed interval regardless of voltage
    interval_delta = timedelta(milliseconds=max(1, config.continuous_interval_ms))
    if current_time - last_emit < interval_delta:
        return None  # Throttle
    return "continuous"
```

**Configuration**:
- `continuous_mode = False` (default, line 136)
- `continuous_interval_ms = 5` (line 139)
- This mode is likely NOT active for your test

---

## Critical State Machine Diagram

```
Voltage Threshold Cross Detected
         ↓
[Window Validation Check]
  ├─ Outside window → ❌ SKIP (increment skip counter)
  └─ Inside window → Continue
         ↓
[Debounce State Machine]
  ├─ Gap < 100ms → Check steady_high
  │    ├─ steady_high enabled → Maybe emit "steady_high"
  │    └─ steady_high disabled → ❌ SUPPRESS (debounce_skipped++)
  └─ Gap >= 100ms → ✅ ACCEPT
         ↓
    Update State: last_detection_times[session][channel] = current_time
         ↓
    Return "threshold_cross"
         ↓
[Create DetectionEvent]
         ↓
[Store in Database]
```

---

## Why Only 4 Events Were Recorded

### Hypothesis 1: Debounce Bottleneck (Most Likely)
**Evidence**:
- Debounce = 100ms → Max 10 events/second → 50 events in 5 seconds
- If 4 events recorded, suggests sparse threshold crossings
- Most detections suppressed by debounce filter

**Calculation**:
```
Expected: 800-1000 detections (200 Hz × 5s = 1000 samples)
Debounce limit: 10 Hz × 5s = 50 detections maximum
Actual: 4 detections (8% of maximum capacity)
```

**Implication**: Only 4 voltage crossings had gaps >= 100ms between them

### Hypothesis 2: Video Window Filtering
**Evidence**:
- If video timing is off, window validation rejects detections
- Check `skipped_early_detections` and `skipped_late_detections` counters
- Lines 994-1006 log these statistics

**Test**:
```python
# Check logs for:
"⏭️ Skipping early detection"  # Line 996
"⏭️ Skipping late detection"   # Line 1002
```

### Hypothesis 3: Voltage Never Crosses Threshold
**Evidence**:
- If voltage stays below 2.5V, no detections recorded
- If voltage stays constantly high (>2.5V), only first crossing detected

**Test**:
```python
# Look for log line 980:
"🎯 DETECTION! {channel}: {voltage:.3f}V > {config.voltage_threshold}V threshold"
```

### Hypothesis 4: State Machine Stuck
**State Reset Analysis**:
- `last_detection_times` persists across monitoring loop
- Only cleared on `stop_monitoring()` (line 2383)
- If state not reset between tests, first detection blocks all others

**Test**:
```python
# Check if session cleanup happened:
self.detection_events.pop(session_id, None)  # Line 2383
```

---

## Decision Statistics Tracking (Lines 1450-1454)

**Instrumentation**:
```python
self.decision_statistics.setdefault(session_id, {})
# Counters:
# - 'continuous_throttled': Continuous mode throttled
# - 'continuous': Continuous samples emitted
# - 'debounce_skipped': Suppressed by debounce
# - 'steady_high': Steady-high events
# - 'threshold_cross': Threshold cross events ✅
```

**Where to Check**:
- Line 1547: `self._increment_decision_stat(session_id, 'threshold_cross')`
- Line 1535: `self._increment_decision_stat(session_id, 'debounce_skipped')`
- Line 1791: `stats_snapshot = self.decision_statistics.get(session_id, {})`

**Recommended Debug Query**:
```python
# Add logging to see decision breakdown:
print(f"Decision stats: {self.decision_statistics.get(session_id, {})}")
# Expected output:
# {'threshold_cross': 4, 'debounce_skipped': 996}
```

---

## Specific Line References for Debugging

### Threshold Check
- **Line 971**: `voltage_in_range = voltage >= config.voltage_threshold`
- **Line 973**: `if voltage_in_range:` - Entry point for detection processing
- **Line 980**: `logger.info(f"🎯 DETECTION! ...")` - First detection log

### Window Validation
- **Line 990-1006**: Video window check with early/late skip counters
- **Line 1554-1620**: `_is_detection_within_video_window()` method
- **Line 1587**: Grace period calculation (2.0 seconds)

### Debounce State Machine
- **Line 1456**: `_should_record_detection()` - Main decision method
- **Line 1516-1517**: State variable initialization
- **Line 1521**: Critical debounce check
- **Line 1535**: Debounce skip counter
- **Line 1542**: State update (last detection timestamp)
- **Line 1547**: Threshold cross counter

### Event Creation
- **Line 1008**: `decision = self._should_record_detection(...)`
- **Line 1010**: `event = self._create_detection_event(...)`
- **Line 1035**: `self._record_detection_event(session_id, event, config)`

### Statistics Logging
- **Line 1791**: Statistics snapshot log
- **Line 1038-1041**: Detection recorded confirmation log

---

## Configuration Values Summary

| Parameter | Default Value | Location | Impact |
|-----------|---------------|----------|---------|
| `voltage_threshold` | 2.5V | Line 130 | Minimum voltage for detection |
| `debounce_ms` | 100ms | Line 131 | **Minimum gap between detections** |
| `sample_rate` | 1000 Hz | Line 132 | Polling/stream frequency |
| `GRACE_PERIOD_SECONDS` | 2.0s | timing_config.py:23 | Window before/after video |
| `steady_high_interval_ms` | 5ms | Line 141 | Alternative event interval |
| `continuous_interval_ms` | 5ms | Line 139 | Continuous mode interval |

---

## Recommended Actions

### 1. Check Decision Statistics
```python
# Add to logs or database query:
SELECT COUNT(*) FROM decision_statistics
WHERE session_id = '<session_id>'
GROUP BY metric;
```

### 2. Verify Video Timing
```python
# Check if video_start_timestamp is correct:
# Look for logs with "Window validation" at lines 985-1006
```

### 3. Review Debounce Configuration
```python
# For 200 Hz detection (5ms intervals):
debounce_ms = 5  # Allow 200 Hz detection rate
# Current: debounce_ms = 100 (only allows 10 Hz)
```

### 4. Check Voltage Data
```python
# Verify voltage actually crosses threshold:
# Look for "🎯 DETECTION!" logs at line 980
```

### 5. Monitor State Machine
```python
# Add logging in _should_record_detection:
logger.info(f"Debounce check: gap={delta_ms:.2f}ms, required={config.debounce_ms}ms")
```

---

## Conclusion

The detection system uses a **multi-stage filtering pipeline**:

1. ✅ **Voltage Threshold** (>= 2.5V)
2. ✅ **Video Window Validation** (within [start-2s, end+buffer])
3. ⚠️ **Debounce Filter** (100ms minimum gap) ← **PRIMARY BOTTLENECK**
4. ✅ **State Machine Update** (atomic timestamp tracking)

**The 4 recorded events represent the ONLY detections that:**
- Exceeded 2.5V threshold
- Occurred within video time window
- Had >= 100ms gap from previous detection

**Most likely cause**: The **debounce filter (100ms)** is suppressing 99.5% of detections at 200 Hz sampling rate. To capture 800-1000 events, reduce `debounce_ms` to match your sample rate (5ms for 200 Hz).
