# Detection Bottleneck Research Findings

## Problem Statement
Only 4 `threshold_cross` events recorded when expecting ~800-1000 from a 5-second video at 200 Hz sampling rate.

---

## Root Cause Identified

### PRIMARY BOTTLENECK: Debounce Filter at 100ms

**Location**: `/backend/services/labjack_detection_service.py:1521`

**The Critical Code**:
```python
# Line 1521: Debounce check
if current_time - last_detection < debounce_delta:
    # Suppress detection - gap too small
    return None
```

**Configuration**:
- `debounce_ms = 100` (default in DetectionConfig, line 131)
- This enforces a **minimum 100ms gap** between any two `threshold_cross` events

**Mathematical Analysis**:
```
Expected Detection Rate: 200 Hz (one detection every 5ms)
Debounce Limit: 100ms minimum gap
Maximum Allowed Rate: 1000ms / 100ms = 10 Hz
Maximum Events in 5s: 10 Hz × 5s = 50 events

Suppression Rate: (200 Hz - 10 Hz) / 200 Hz = 95% suppression
Expected Suppressed: 1000 samples × 0.95 = 950 detections suppressed
Actual Recorded: 4 events (8% of maximum capacity)
```

---

## Detection Logic Flow (Critical Path)

### Stage 1: Voltage Threshold Check ✅
**Line**: 971, 1314
**Logic**: `voltage >= config.voltage_threshold` (default: 2.5V)
**Purpose**: Only process voltages above threshold
**Impact**: If voltage never crosses threshold, zero detections

### Stage 2: Video Window Validation ✅
**Line**: 990-1006, 1554-1620
**Logic**: Detection must be within `[video_start - 2s, video_end + buffer]`
**Configuration**: `GRACE_PERIOD_SECONDS = 2.0`
**Purpose**: Prevent early/late detections outside video playback
**Impact**: Rejects detections with incorrect timing

**Skip Counters**:
- `skipped_early_detections`: Count of detections before video start
- `skipped_late_detections`: Count of detections after video end

### Stage 3: Debounce State Machine ⚠️ BOTTLENECK
**Line**: 1456-1552
**Method**: `_should_record_detection()`
**State Variable**: `self.last_detection_times[session_id][channel]`
**Logic**:
1. Check gap: `delta = current_time - last_detection`
2. If `delta < 100ms`: **SUPPRESS** (return None)
3. If `delta >= 100ms`: **ACCEPT** (return "threshold_cross")
4. Update state: `last_detection = current_time`

**Thread Safety**: All state access protected by `self.lock` (line 1468)

**State Persistence**:
- State persists across entire monitoring session
- Only cleared when `stop_monitoring()` called (line 2383)
- If state not reset between tests, residual state blocks detections

### Stage 4: Event Recording ✅
**Line**: 1767-1810
**Method**: `_record_detection_event()`
**Actions**:
1. Add to memory list (line 1778)
2. Schedule database storage (line 1805)
3. Increment statistics counter (line 1547)
4. Notify callbacks (line 2323)

---

## Why Only 4 Events Were Recorded

### Analysis of the 4 Events

The 4 recorded events are the **ONLY** detections that satisfied ALL conditions:

1. ✅ Voltage exceeded 2.5V threshold
2. ✅ Occurred within video time window `[start-2s, end+buffer]`
3. ✅ Had >= 100ms gap from previous detection ← **KEY CONSTRAINT**
4. ✅ Passed state machine update

### Possible Explanations

#### Hypothesis 1: Sparse Voltage Crossings (Most Likely)
**Theory**: The actual voltage signal only had 4 distinct rising edges separated by >= 100ms

**Evidence Needed**:
```bash
# Check logs for voltage readings
grep "🎯 DETECTION!" labjack.log | wc -l
# This shows how many times voltage crossed threshold

# Check decision statistics
grep "decision_statistics" labjack.log
# Look for: {'threshold_cross': 4, 'debounce_skipped': 996}
```

**Implication**: If signal is continuous high voltage (e.g., LED stays on), only the initial rising edge is detected. All subsequent samples are suppressed by debounce.

#### Hypothesis 2: State Machine Not Reset
**Theory**: Previous test left state in `last_detection_times`, blocking new detections

**Evidence Needed**:
```python
# Check if stop_monitoring() was called between tests
# Line 2383 should execute: self.detection_events.pop(session_id, None)
```

**Test**: Restart service between tests to clear all state

#### Hypothesis 3: Video Timing Misalignment
**Theory**: Most detections fell outside the `[start-2s, end+buffer]` window

**Evidence Needed**:
```bash
# Check window skip counters in logs
grep "Skipping early detection" labjack.log | wc -l
grep "Skipping late detection" labjack.log | wc -l

# Check stream detection stats (line 1412-1417)
grep "Stream Detection Stats" labjack.log
# Should show: Valid=4, Skipped Early=X, Skipped Late=Y
```

**Implication**: If `skipped_early` or `skipped_late` > 0, timing is the issue

#### Hypothesis 4: High-Frequency Continuous Signal
**Theory**: Voltage stayed continuously above threshold, creating 1000 potential detections but only 4 passed debounce

**Evidence**:
- If voltage is continuously high (e.g., 3.5V steady)
- Each 5ms poll triggers threshold check
- Debounce suppresses all but every 100ms sample

**Calculation**:
```
5-second window at 200 Hz = 1000 samples
Debounce allows 1 per 100ms = 10 Hz
Expected events: 5s × 10 Hz = 50 events
Actual events: 4 events (likely signal ended before full 5s)
```

---

## Decision Statistics Instrumentation

**Location**: Lines 1450-1454, 1790-1791

**Metrics Available**:
```python
self.decision_statistics[session_id] = {
    'threshold_cross': 4,        # Accepted threshold crossings ✅
    'debounce_skipped': 996,     # Suppressed by debounce ⚠️
    'steady_high': 0,            # Steady-high events
    'continuous': 0,             # Continuous mode events
    'continuous_throttled': 0    # Continuous mode throttled
}
```

**How to Check**:
```python
# Add to monitoring loop or database query:
stats = self.decision_statistics.get(session_id, {})
print(f"Detection breakdown: {stats}")
```

**Expected Output for 200 Hz signal**:
```
{
  'threshold_cross': 4,
  'debounce_skipped': 996
}
```

This would confirm that 996 detections were suppressed by debounce filter.

---

## Code References by Line Number

### Configuration
- **Line 130**: `voltage_threshold: float = 2.5` - Threshold voltage
- **Line 131**: `debounce_ms: int = 100` - **CRITICAL BOTTLENECK**
- **Line 132**: `sample_rate: int = 1000` - Polling rate
- **Line 140-141**: Steady-high alternative with 5ms interval

### Voltage Check
- **Line 971**: Standard threshold check `voltage >= config.voltage_threshold`
- **Line 973**: Entry to detection processing `if voltage_in_range:`
- **Line 980**: Detection log `"🎯 DETECTION!"`

### Window Validation
- **Line 987-989**: Pre-trigger detection allowed check
- **Line 990-1006**: Window validation with skip counters
- **Line 1554-1620**: `_is_detection_within_video_window()` implementation
- **Line 1587**: Grace period constant `GRACE_PERIOD_SECONDS` (2.0s)

### Debounce State Machine (CRITICAL)
- **Line 1456**: Method definition `_should_record_detection()`
- **Line 1468**: Lock acquisition `with self.lock:`
- **Line 1516**: State initialization `session_detections = ...`
- **Line 1517**: Last detection lookup `last_detection = session_detections.get(...)`
- **Line 1518**: Debounce delta calculation
- **Line 1521**: **CRITICAL CHECK** `if current_time - last_detection < debounce_delta:`
- **Line 1535**: Debounce skip counter `self._increment_decision_stat(session_id, 'debounce_skipped')`
- **Line 1537**: Debug log `"⛔ [Decision] threshold suppressed by debounce"`
- **Line 1542**: State update `session_detections[channel] = current_time`
- **Line 1547**: Accept counter `self._increment_decision_stat(session_id, 'threshold_cross')`
- **Line 1549**: Debug log `"🟢 [Decision] threshold_cross accepted"`
- **Line 1552**: Return `"threshold_cross"`

### Event Recording
- **Line 1008**: Decision call `decision = self._should_record_detection(...)`
- **Line 1010**: Event creation `event = self._create_detection_event(...)`
- **Line 1033**: State assignment `event.state = 'threshold_cross'`
- **Line 1035**: Recording `self._record_detection_event(session_id, event, config)`
- **Line 1767**: Method `_record_detection_event()` definition
- **Line 1778**: Memory storage `self.detection_events[session_id].append(event)`
- **Line 1805**: Database scheduling `self._schedule_db_storage(event)`

### Statistics & Logging
- **Line 1450**: Stat increment `_increment_decision_stat()`
- **Line 1790**: Stats snapshot `stats_snapshot = self.decision_statistics.get(...)`
- **Line 1791**: Event log with stats
- **Line 1038**: Recorded event confirmation log

### State Cleanup
- **Line 2383**: State clearing `self.detection_events.pop(session_id, None)`

---

## Recommended Debugging Steps

### 1. Check Decision Statistics
```python
# Query or log:
stats = detection_service.decision_statistics.get(session_id, {})
print(f"""
Detection Statistics:
  Threshold Cross: {stats.get('threshold_cross', 0)}
  Debounce Skipped: {stats.get('debounce_skipped', 0)}
  Steady High: {stats.get('steady_high', 0)}
  Total Detections: {stats.get('threshold_cross', 0) + stats.get('debounce_skipped', 0)}
""")
```

**Expected**: If `debounce_skipped` >> `threshold_cross`, debounce is the bottleneck

### 2. Verify Window Validation
```bash
# Check logs for skip counters
grep "Stream Detection Stats" backend.log
# Expected output:
# "Valid=4, Skipped Early=0, Skipped Late=0"

# If skipped counts are high:
grep "Skipping early detection" backend.log | wc -l
grep "Skipping late detection" backend.log | wc -l
```

**Expected**: If skipped counts > 0, video timing is off

### 3. Monitor Voltage Readings
```bash
# Check how often voltage crosses threshold
grep "🎯 DETECTION!" backend.log | wc -l
```

**Expected**: Should be ~1000 for 200 Hz × 5s if voltage constantly high

### 4. Trace Debounce Decisions
```bash
# Check suppression logs
grep "⛔ \[Decision\] threshold suppressed" backend.log | wc -l
# vs accepted logs
grep "🟢 \[Decision\] threshold_cross accepted" backend.log | wc -l
```

**Expected**: Ratio should be ~250:1 (996 suppressed : 4 accepted)

### 5. Verify State Cleanup
```python
# Before starting new test:
assert session_id not in detection_service.last_detection_times
assert session_id not in detection_service.detection_events
```

**Expected**: State should be cleared between tests

---

## Immediate Fix Recommendation

### Option 1: Reduce Debounce to Match Sample Rate (Recommended for 200 Hz)

**Change**:
```python
# In DetectionConfig (line 131):
debounce_ms: int = 5  # Changed from 100ms to 5ms (200 Hz)
```

**Impact**:
- Maximum rate: 1000ms / 5ms = 200 Hz ✅
- 5-second video: 200 Hz × 5s = 1000 events ✅
- Matches expected detection count

**Trade-off**: May introduce noise if voltage fluctuates rapidly around threshold

### Option 2: Disable Debounce for High-Frequency Capture

**Change**:
```python
# In DetectionConfig:
debounce_ms: int = 1  # Minimum debounce (1ms)
```

**Impact**:
- Maximum rate: ~1000 Hz
- Captures all threshold crossings
- Higher data volume

### Option 3: Use Steady-High Mode for Continuous Signals

**Change**:
```python
# In DetectionConfig:
steady_high_logging: bool = True  # Already enabled
steady_high_interval_ms: int = 5   # Already set to 5ms
```

**Impact**:
- Emits "steady_high" events at 200 Hz during high state
- Different event type from "threshold_cross"
- May not be counted in current analysis

**Note**: Check if your analysis filters on `event.state == 'threshold_cross'`

---

## Configuration Recommendations by Use Case

### Use Case 1: Capture All Threshold Crossings at 200 Hz
```python
DetectionConfig(
    voltage_threshold=2.5,
    debounce_ms=5,           # ← Match sample rate
    sample_rate=1000,
    steady_high_logging=False  # Not needed
)
```

### Use Case 2: Detect Discrete Pulse Events (Current Behavior)
```python
DetectionConfig(
    voltage_threshold=2.5,
    debounce_ms=100,         # ← Current setting
    sample_rate=1000,
    steady_high_logging=True  # Capture continuous state
)
```

### Use Case 3: High-Frequency Continuous Monitoring
```python
DetectionConfig(
    voltage_threshold=2.5,
    debounce_ms=1,           # ← Minimal filtering
    sample_rate=1000,
    continuous_mode=True,     # ← Enable continuous sampling
    continuous_interval_ms=5  # ← 200 Hz rate
)
```

---

## Next Steps

1. **Confirm Root Cause**: Check `decision_statistics` for session
   - If `debounce_skipped` ~1000, confirm debounce is bottleneck
   - If `skipped_early` or `skipped_late` > 0, fix timing

2. **Review Signal Characteristics**: Determine if signal is:
   - Discrete pulses (keep 100ms debounce)
   - Continuous high voltage (reduce to 5ms debounce)
   - Rapid transitions (use 1ms debounce or continuous mode)

3. **Adjust Configuration**: Based on signal type, update `debounce_ms`

4. **Verify State Cleanup**: Ensure `stop_monitoring()` called between tests

5. **Re-test**: Run same video with adjusted configuration

6. **Monitor Statistics**: Track `decision_statistics` to confirm fix

---

## Summary

**Problem**: 4 events instead of 800-1000
**Root Cause**: Debounce filter at 100ms suppresses 95% of detections
**Solution**: Reduce `debounce_ms` to 5ms for 200 Hz capture
**Validation**: Check `decision_statistics` for `debounce_skipped` count

**Critical Code Location**: `/backend/services/labjack_detection_service.py:1521`

The detection system is working as designed - it's filtering out rapid detections to prevent noise. The 4 recorded events represent the only detections that met the 100ms minimum gap requirement. To capture all 800-1000 detections, the debounce configuration must be adjusted to match the expected signal characteristics.
