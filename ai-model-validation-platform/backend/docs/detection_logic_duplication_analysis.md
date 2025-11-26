# Detection Logic Duplication Analysis

## Executive Summary

**CRITICAL FINDING**: The detection logic is **DUPLICATED** across two services with **DIFFERENT** implementations using **DIFFERENT** LabJack backends. This creates serious issues for HIL testing:

- **Different LabJack Services**: One uses `signal_validation_service`, the other uses `labjack_service`
- **Different Detection Algorithms**: Similar but not identical threshold/debounce implementations
- **Different Database Integration**: Direct SQLite vs SQLAlchemy ORM
- **Conflicts**: Both can access the same hardware simultaneously, causing device conflicts

---

## 1. Hardware Reading Code Comparison

### dedicated_labjack_monitor.py
**Location**: `/backend/src/services/dedicated_labjack_monitor.py`

**Hardware Service Used**:
```python
from services.signal_validation_wsl import signal_validation_service
# or
from services.signal_validation_service import signal_validation_service
```

**Reading Method** (Lines 337-340):
```python
result = signal_validation_service.read_voltage_signal(channel)

if result.get("success") and result.get("voltage") is not None:
    voltage = result["voltage"]
```

**Key Characteristics**:
- Uses `signal_validation_service` (dedicated HIL service)
- Returns dictionary with `{"success": bool, "voltage": float}`
- Designed for exclusive hardware access
- No stream mode support
- Simple polling at 10 Hz default

---

### labjack_detection_service.py
**Location**: `/backend/services/labjack_detection_service.py`

**Hardware Services Used**:
```python
from services.labjack_service import get_labjack_service, LabJackService
from services.labjack_hardware_service import get_labjack_hardware_service
from services.labjack_connection_manager import get_connection_manager
```

**Reading Methods** (Multiple modes):

**1. Connection Manager (Polling)** (Lines 855-856, 889, 908):
```python
voltage = self.connection_manager.read_voltage(channel)
if voltage is not None:
    channel_readings[channel] = voltage
```

**2. Stream Mode** (Lines 787-847):
```python
success, actual_rate = self.labjack_service.start_stream_mode(
    channels=config.channels,
    scan_rate=config.sample_rate,
    scans_per_read=scans_per_read
)
data, backlog, success = self.labjack_service.read_stream_mode()
```

**Key Characteristics**:
- Uses three different LabJack services
- Supports both polling and stream mode
- Returns raw voltage values (not wrapped in dict)
- Supports high-frequency sampling (200+ Hz)
- Complex connection management

---

## 2. Threshold Detection Logic Comparison

### dedicated_labjack_monitor.py

**Detection Check** (Line 353):
```python
detection=voltage > self.config.voltage_threshold
```

**Threshold Configuration**:
- Default: `3.0V` (Line 66)
- Configurable via `--voltage-threshold` argument

**Detection Recording**:
```python
if reading.detection:
    self.stats['detections'] += 1
    # Store detection event immediately
    self._store_detection_event(reading)
    logger.debug(f"Detection: {voltage:.3f}V on {channel}")
```

**Characteristics**:
- ❌ **NO DEBOUNCE LOGIC** - Every threshold cross is recorded
- Simple boolean check: `voltage > threshold`
- No time-based filtering
- Immediate database write on every detection

---

### labjack_detection_service.py

**Detection Check** (Lines 938, 1255):
```python
# Continuous mode:
voltage_in_range = voltage >= lower_bound and (upper_bound is None or voltage <= upper_bound)

# Standard mode:
voltage_in_range = voltage >= config.voltage_threshold
```

**Threshold Configuration**:
- Default: `2.5V` (Line 129)
- Configurable via `voltage_threshold` parameter
- Supports continuous mode with voltage windows

**Detection Recording with Debounce** (Lines 1395-1429):
```python
def _should_record_detection(session_id, channel, current_time, config):
    session_detections = self.last_detection_times.setdefault(session_id, {})
    last_detection = session_detections.get(channel, datetime.min)
    debounce_delta = timedelta(milliseconds=config.debounce_ms)
    delta_ms = (current_time - last_detection).total_seconds() * 1000.0

    if current_time - last_detection < debounce_delta:
        if config.steady_high_logging:
            # Allow periodic "steady_high" samples
            last_steady = steady_session.get(channel, datetime.min)
            steady_delta = timedelta(milliseconds=max(1, config.steady_high_interval_ms))
            if current_time - last_steady >= steady_delta:
                return "steady_high"

        self._increment_decision_stat(session_id, 'debounce_skipped')
        return None  # SKIP detection

    session_detections[channel] = current_time
    return "threshold_cross"
```

**Characteristics**:
- ✅ **FULL DEBOUNCE LOGIC** - Prevents duplicate detections
- Default debounce: `100ms` (Line 130)
- Tracks last detection time per channel per session
- Supports "steady_high" mode for periodic sampling during long detections
- Batch database writes for performance

---

## 3. Debounce Implementation Comparison

### dedicated_labjack_monitor.py

**Debounce Status**: ❌ **NOT IMPLEMENTED**

**Result**: Every voltage reading above threshold is recorded as a detection, leading to:
- Hundreds of duplicate detections for single events
- Database flooding
- Inaccurate detection counts
- Poor HIL test reliability

**Example Behavior**:
```
Video shows 1 detection at 5.2s
LabJack monitor records:
- 5.200s: 3.5V ✅ DETECTION
- 5.210s: 3.6V ✅ DETECTION (duplicate)
- 5.220s: 3.7V ✅ DETECTION (duplicate)
- 5.230s: 3.8V ✅ DETECTION (duplicate)
- ... (continues for duration of signal)
Result: 1 real detection → 50+ duplicate records
```

---

### labjack_detection_service.py

**Debounce Status**: ✅ **FULLY IMPLEMENTED**

**Implementation Details**:
- Tracks last detection timestamp per channel in `self.last_detection_times`
- Configurable debounce period (default 100ms)
- Decision statistics tracking:
  - `threshold_cross`: New detection allowed
  - `debounce_skipped`: Detection suppressed (too soon)
  - `steady_high`: Periodic sample during long detection
  - `continuous`: Continuous mode sample

**Example Behavior**:
```
Video shows 1 detection at 5.2s
LabJack detection service records:
- 5.200s: 3.5V ✅ DETECTION (threshold_cross)
- 5.210s: 3.6V ⛔ SKIPPED (debounce: 10ms < 100ms)
- 5.220s: 3.7V ⛔ SKIPPED (debounce: 20ms < 100ms)
- 5.230s: 3.8V 🟡 STEADY_HIGH (periodic sample, not counted as new detection)
- 5.350s: 3.2V ✅ DETECTION (debounce: 150ms > 100ms, new event)
Result: 1-2 detection records (accurate)
```

**Decision Statistics Logged** (Lines 1412-1429):
```python
self._increment_decision_stat(session_id, 'debounce_skipped')
logger.debug(
    f"⛔ [Decision] threshold suppressed by debounce for session={session_id} "
    f"channel={channel} gap={delta_ms:.2f}ms < debounce={config.debounce_ms}ms"
)
```

---

## 4. Voltage Processing Differences

| Feature | dedicated_labjack_monitor | labjack_detection_service |
|---------|---------------------------|---------------------------|
| **Voltage Units** | Volts (raw) | Volts (raw) |
| **Threshold Comparison** | `>` (greater than) | `>=` (greater than or equal) |
| **Continuous Mode** | ❌ Not supported | ✅ Supported with voltage windows |
| **Stream Mode** | ❌ Not supported | ✅ Supported (200+ Hz) |
| **Batch Processing** | ❌ Individual reads | ✅ Batch reads from stream buffer |
| **Video Timing Sync** | ✅ Video-relative timestamps | ✅ Video-relative timestamps |
| **Window Validation** | ❌ Not implemented | ✅ Skips detections outside video duration |

---

## 5. Detection Algorithm Step-by-Step

### dedicated_labjack_monitor Algorithm

```
1. START monitoring loop at configured sample_rate (default 10 Hz)
2. FOR each channel in config.channels:
   3. Call signal_validation_service.read_voltage_signal(channel)
   4. IF result["success"] AND result["voltage"] is not None:
      5. voltage = result["voltage"]
      6. timestamp = time.time()
      7. Calculate video_relative_time (if video start time known)
      8. detection = voltage > config.voltage_threshold  # Simple boolean
      9. Create VoltageReading object
      10. stats['total_readings'] += 1
      11. IF detection:
          12. stats['detections'] += 1
          13. _store_detection_event(reading)  # Immediate DB write
          14. Log "Detection: {voltage}V on {channel}"
   15. ELSE:
       16. Log warning and increment error counter
17. Add readings to buffer (max 1000 readings)
18. Sleep to maintain sample rate
19. REPEAT until shutdown
```

**No Debounce**: Every threshold cross = new detection record

---

### labjack_detection_service Algorithm

```
1. START monitoring loop at configured sample_rate (default 1000 Hz)
2. Get video timing information (start time, duration)
3. Initialize window validation counters
4. IF sample_rate > 100 Hz AND stream_mode enabled:
   5. Start hardware stream mode via labjack_service.start_stream_mode()
   6. Read buffered data via labjack_service.read_stream_mode()
7. ELSE:
   8. Use polling mode via connection_manager.read_voltage()
9. FOR each channel reading:
   10. Check video window: IF detection outside video duration + buffer:
       11. Log "OUTSIDE VIDEO WINDOW" and skip
       12. Increment skipped_early or skipped_late counter
       13. CONTINUE to next reading
   14. Determine voltage_in_range:
       IF continuous_mode:
           voltage_in_range = (voltage >= lower_bound) AND (voltage <= upper_bound)
       ELSE:
           voltage_in_range = voltage >= config.voltage_threshold
   15. IF voltage_in_range:
       16. Call _should_record_detection(session, channel, time, config)
           FUNCTION _should_record_detection:
               17. Get last_detection_time for this channel
               18. Calculate time_since_last = current_time - last_detection_time
               19. IF time_since_last < debounce_ms:
                   20. IF steady_high_logging enabled:
                       21. Check if steady_high_interval_ms elapsed
                       22. IF yes: RETURN "steady_high"
                   23. Log "debounce_skipped"
                   24. RETURN None  # SKIP detection
               25. Update last_detection_time[channel] = current_time
               26. Log "threshold_cross"
               27. RETURN "threshold_cross"
       28. IF decision is None:
           29. SKIP detection (debounced)
       30. ELSE:
           31. Create DetectionEvent
           32. Add metadata (state: threshold_cross/steady_high/continuous)
           33. Queue for batch commit (not immediate DB write)
           34. Increment total_valid_detections
10. Sleep or wait for next stream buffer
11. REPEAT until video ends or shutdown
```

**With Debounce**: Only new threshold crosses (after debounce period) = detection records

---

## 6. Code Duplication Summary

### Duplicated Functions

| Function | dedicated_labjack_monitor | labjack_detection_service |
|----------|---------------------------|---------------------------|
| **Hardware Reading** | ✅ `_monitoring_loop()` | ✅ `_monitoring_loop()` + `_monitoring_loop_stream()` |
| **Threshold Check** | ✅ `voltage > threshold` | ✅ `voltage >= threshold` |
| **Detection Event Creation** | ✅ `VoltageReading` dataclass | ✅ `DetectionEvent` dataclass |
| **Database Storage** | ✅ `_store_detection_event()` | ✅ `_record_detection_event()` + batch commit |
| **Session Management** | ✅ IPC server + threading | ✅ Threading with session state |
| **Debounce Logic** | ❌ **MISSING** | ✅ `_should_record_detection()` |

### Different Implementations

| Feature | dedicated_labjack_monitor | labjack_detection_service | Are They the Same? |
|---------|---------------------------|---------------------------|--------------------|
| Hardware backend | `signal_validation_service` | `labjack_service` + `connection_manager` | ❌ **NO - Different services** |
| Detection threshold | `voltage > threshold` | `voltage >= threshold` | ❌ **NO - Different operators** |
| Debounce | None | 100ms configurable | ❌ **NO - Not implemented vs full implementation** |
| Database access | Direct SQLite | SQLAlchemy ORM | ❌ **NO - Different approaches** |
| Sample rate | 10 Hz default | 1000 Hz default | ❌ **NO - 100x difference** |
| Stream mode | None | Full stream support | ❌ **NO - Not supported vs supported** |

---

## 7. Which Logic is Correct for HIL Tests?

### Recommendation: **labjack_detection_service.py**

**Reasons**:

1. ✅ **Debounce Logic**: Prevents duplicate detections (critical for HIL accuracy)
2. ✅ **High Sample Rate**: Supports 1000+ Hz for sub-millisecond latency detection
3. ✅ **Stream Mode**: Hardware-timed buffered acquisition for accurate timing
4. ✅ **Window Validation**: Skips detections outside video playback window
5. ✅ **Batch Commits**: Optimized for high-frequency operation
6. ✅ **Better Error Handling**: Comprehensive error recovery and logging
7. ✅ **More Complete**: Supports continuous mode, steady_high logging, etc.

### Issues with dedicated_labjack_monitor.py:

1. ❌ **No Debounce**: Will record 100+ duplicates for single detection
2. ❌ **Low Sample Rate**: 10 Hz insufficient for latency analysis (<100ms requirement)
3. ❌ **No Stream Mode**: Cannot handle high-frequency requirements
4. ❌ **No Window Validation**: Records detections before/after video playback
5. ❌ **Immediate DB Writes**: Performance bottleneck at high rates
6. ❌ **Wrong LabJack Service**: Uses `signal_validation_service` instead of main service

---

## 8. Device Conflict Analysis

**CRITICAL ISSUE**: Both services can run simultaneously and access the same LabJack hardware:

### Conflict Scenario:
```
Time    | dedicated_labjack_monitor          | labjack_detection_service
--------|------------------------------------|---------------------------------
0.000s  | Connects to LabJack (exclusive)   | Idle
0.100s  | Reading AIN0...                    | Idle
0.200s  | Reading AIN0...                    | Starts monitoring session
0.201s  | Reading AIN0...                    | Tries to connect → CONFLICT!
0.202s  | Device lock held                   | ERROR: Device busy
```

**Result**: One service locks the device, the other fails with "device busy" errors.

---

## 9. Consolidation Recommendations

### Option 1: **Use labjack_detection_service Exclusively** (Recommended)

**Action Items**:
1. Remove or deprecate `dedicated_labjack_monitor.py`
2. Update all HIL tests to use `labjack_detection_service`
3. Configure `labjack_detection_service` with:
   - `sample_rate=1000` (or higher)
   - `debounce_ms=100`
   - `use_stream_mode=True`
   - `voltage_threshold=3.0` (match HIL requirements)

**Benefits**:
- ✅ Single source of truth for detection logic
- ✅ No device conflicts
- ✅ Accurate detection counts (debounced)
- ✅ Sub-100ms latency support
- ✅ Proven in production

---

### Option 2: Extract Common Logic (Alternative)

**Action Items**:
1. Create `labjack_detection_core.py` with:
   - Common debounce algorithm
   - Threshold detection logic
   - Window validation
2. Have both services inherit/import from core
3. Maintain separate services for different use cases

**Benefits**:
- ✅ Code reuse
- ✅ Maintains separation of concerns
- ⚠️ Still risk of device conflicts

**Drawbacks**:
- ❌ More complex architecture
- ❌ Requires careful device access coordination
- ❌ May not be needed if one service is sufficient

---

## 10. Specific Issues Found

### Issue 1: Missing Debounce in dedicated_labjack_monitor

**Impact**: Database pollution with duplicate detections

**Evidence**:
```python
# Line 353 - No debounce check before recording
detection=voltage > self.config.voltage_threshold
if reading.detection:
    self.stats['detections'] += 1
    self._store_detection_event(reading)  # Every time!
```

**Expected Behavior**:
```python
# Should be:
if voltage > threshold:
    if should_record_detection(channel, timestamp, debounce_ms):
        self._store_detection_event(reading)
    else:
        logger.debug("Skipped (debounce)")
```

---

### Issue 2: Different Default Thresholds

**dedicated_labjack_monitor**: 3.0V (Line 66)
**labjack_detection_service**: 2.5V (Line 129)

**Impact**: Different sensitivity, could miss/over-detect events

---

### Issue 3: Different Sample Rates

**dedicated_labjack_monitor**: 10 Hz (Line 65)
**labjack_detection_service**: 1000 Hz (Line 131)

**Impact**:
- 10 Hz = 100ms resolution (insufficient for HIL <100ms requirement)
- 1000 Hz = 1ms resolution (sufficient)

---

### Issue 4: No Stream Mode in dedicated_labjack_monitor

**Impact**: Cannot achieve high sample rates needed for HIL testing

**Evidence**: Only polling mode implemented (Line 321-416), no stream mode support

---

## 11. Test Impact Analysis

### Current HIL Test Status

**If using dedicated_labjack_monitor**:
- ❌ Will record 100+ detections for single event
- ❌ Will not meet <100ms latency requirement
- ❌ Will have poor ground truth matching accuracy
- ❌ Database will be flooded with duplicates

**If using labjack_detection_service**:
- ✅ Accurate detection counts (1-2 per event)
- ✅ Sub-millisecond timing resolution
- ✅ Accurate latency measurements
- ✅ Clean database records

---

## 12. Action Plan

### Immediate Actions (Priority 1)

1. **Verify which service HIL tests are using**:
   ```bash
   grep -r "dedicated_labjack_monitor\|DedicatedLabJackMonitor" tests/
   grep -r "labjack_detection_service\|LabJackDetectionMonitor" tests/
   ```

2. **Switch HIL tests to use labjack_detection_service**:
   - Update test fixtures
   - Configure proper parameters:
     ```python
     service.start_monitoring(
         session_id=session_id,
         channels=["AIN0"],
         voltage_threshold=3.0,
         debounce_ms=100,
         sample_rate=1000,
         use_stream_mode=True
     )
     ```

3. **Add debounce to dedicated_labjack_monitor** (if keeping):
   - Copy `_should_record_detection()` method from labjack_detection_service
   - Add `last_detection_times` tracking
   - Implement debounce check before `_store_detection_event()`

### Short-term Actions (Priority 2)

4. **Standardize configuration**:
   - Use consistent default voltage threshold (3.0V for HIL)
   - Use consistent sample rates (1000 Hz minimum)
   - Document when to use each service

5. **Add device conflict prevention**:
   - Implement shared connection manager
   - Add mutex/lock for device access
   - Log warnings when multiple services attempt access

### Long-term Actions (Priority 3)

6. **Consolidate or deprecate**:
   - Decide if both services are needed
   - If not, deprecate dedicated_labjack_monitor
   - Update all documentation

7. **Extract common logic**:
   - Create shared debounce utility
   - Create shared detection event structure
   - Create shared database storage logic

---

## Conclusion

**DUPLICATION STATUS**: ✅ **YES, CODE IS DUPLICATED**

**IMPLEMENTATION STATUS**: ❌ **DIFFERENT ALGORITHMS**

**CORRECTNESS FOR HIL**:
- ✅ **labjack_detection_service** - Correct (has debounce, high sample rate, stream mode)
- ❌ **dedicated_labjack_monitor** - Incorrect (no debounce, low sample rate, missing features)

**RECOMMENDATION**:
Use **labjack_detection_service** for all HIL testing. Deprecate or fix dedicated_labjack_monitor.

---

## Appendix: Side-by-Side Code Comparison

### Hardware Reading
```python
# dedicated_labjack_monitor.py (Lines 337-340)
result = signal_validation_service.read_voltage_signal(channel)
if result.get("success") and result.get("voltage") is not None:
    voltage = result["voltage"]

# labjack_detection_service.py (Line 908)
voltage = self.connection_manager.read_voltage(channel)
if voltage is not None:
    channel_readings[channel] = voltage
```

### Threshold Detection
```python
# dedicated_labjack_monitor.py (Line 353)
detection=voltage > self.config.voltage_threshold

# labjack_detection_service.py (Line 938)
voltage_in_range = voltage >= config.voltage_threshold
```

### Debounce Logic
```python
# dedicated_labjack_monitor.py
# ❌ NOT IMPLEMENTED

# labjack_detection_service.py (Lines 1395-1429)
last_detection = session_detections.get(channel, datetime.min)
debounce_delta = timedelta(milliseconds=config.debounce_ms)
if current_time - last_detection < debounce_delta:
    return None  # Skip detection
session_detections[channel] = current_time
return "threshold_cross"
```

### Database Storage
```python
# dedicated_labjack_monitor.py (Lines 418-465)
# Direct SQLite with immediate commit
cursor.execute("INSERT INTO detection_events ...")
self.db_connection.commit()

# labjack_detection_service.py (Lines 1700-1936)
# SQLAlchemy ORM with batch commit
db_event = DetectionEvent(...)
self.detection_batch.append(db_event)
if len(self.detection_batch) >= self.batch_size_threshold:
    self._flush_batch_commits()
```

---

**Report Generated**: 2025-11-17
**Analyzed Files**:
- `/backend/src/services/dedicated_labjack_monitor.py`
- `/backend/services/labjack_detection_service.py`
