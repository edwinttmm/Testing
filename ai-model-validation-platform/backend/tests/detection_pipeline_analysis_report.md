# Detection Event Creation Flow Analysis Report

## Executive Summary
**Finding: 0 detection events created due to voltage reading failure in monitoring loop**

The detection pipeline is failing because the LabJack connection manager is returning 0.0V for all voltage readings, which is below the 3.3V detection threshold.

---

## Root Cause Analysis

### 1. Detection Flow Overview

```
Frontend Test Start
    ↓
start_monitoring_with_video_sync() - dedicated_labjack_monitor.py:130
    ↓
labjack_monitor.start_monitoring() - labjack_detection_service.py:175
    ↓
_monitoring_loop() - labjack_detection_service.py:388
    ↓
connection_manager.read_voltage() - Returns 0.0V ❌
    ↓
voltage (0.0V) < threshold (3.3V) → NO DETECTION
```

### 2. Critical Issues Found

#### Issue #1: Voltage Reading Returns 0.0V
**Location**: `labjack_detection_service.py:416-424`

```python
# Use shared connection manager for voltage reading
voltage = self.connection_manager.read_voltage(channel)
if voltage is not None:
    logger.debug(f"📊 {channel}: {voltage:.4f}V (threshold: {config.voltage_threshold}V)")
else:
    voltage = 0.0  # ❌ Falls back to 0.0V on failure
```

**Problem**:
- LabJack may not be streaming data
- Connection manager may not be initialized properly
- Hardware connection may be dropped
- Returns 0.0V which is always below 3.3V threshold

#### Issue #2: Threshold Configuration
**Location**: `dedicated_labjack_monitor.py:130`

```python
'voltage_threshold': video_timing_config.get('voltage_threshold', 3.3),  # Default 3.3V
```

**Current threshold**: 3.3V
- If LabJack is reading 0.0V, no detections will occur
- No error logging when voltage reads fail
- Silent failure mode

#### Issue #3: No Streaming Verification
**Location**: `labjack_detection_service.py:389-463`

The monitoring loop assumes LabJack is streaming but doesn't verify:
- ✅ Creates monitoring thread
- ❌ Doesn't verify LabJack is actually streaming
- ❌ Doesn't check if connection_manager is initialized
- ❌ No fallback to alternative reading methods

---

## Detection Event Creation Process

### Expected Flow (Working)
1. ✅ `start_monitoring_with_video_sync()` creates session
2. ✅ Registers detection callback
3. ✅ Starts LabJack monitoring
4. ✅ `_monitoring_loop()` polls voltages
5. ✅ Voltage >= 3.3V triggers detection
6. ✅ `_create_detection_event()` creates event
7. ✅ `_record_detection_event()` stores in DB
8. ✅ Callbacks notify video timing service

### Actual Flow (Broken)
1. ✅ `start_monitoring_with_video_sync()` creates session
2. ✅ Registers detection callback
3. ✅ Starts LabJack monitoring
4. ⚠️ `_monitoring_loop()` polls voltages
5. ❌ **connection_manager.read_voltage() returns 0.0V**
6. ❌ **0.0V < 3.3V threshold → NO DETECTION**
7. ❌ Loop continues indefinitely reading 0.0V
8. ❌ Session ends with 0 detections

---

## Database Analysis

### Detection Events Table Schema
**Location**: `models.py:270-320`

All required fields are present:
- ✅ `labjack_voltage` (Float, nullable=True)
- ✅ `detection_channel` (String, nullable=True)
- ✅ `video_relative_timestamp` (Float, nullable=True)
- ✅ `actual_latency_ms` (Float, nullable=True)

### Database Statistics
```sql
Total detection events: 20,916
Events with voltage data: 15,687 (75%)
```

**Recent session (3b8a9e2f)**: 0 detection events ❌

---

## Voltage Threshold Detection Logic

### Raw Logger Threshold Check
**Location**: `raw_labjack_logger.py:548-576`

```python
def _check_detection_thresholds(self, session_id: str, voltages: List[float], timestamp_ns: int):
    config = self.session_configs.get(session_id, {})
    threshold = config.get('detection_threshold', 2.5)  # Default 2.5V ⚠️

    for i, voltage in enumerate(voltages):
        if voltage > threshold:  # Simple comparison
            # Create detection event
            detection_data = {...}
            # Notify callbacks
```

**Note**: Raw logger uses 2.5V default, but it's not being used in the current flow.

### Detection Service Threshold Check
**Location**: `labjack_detection_service.py:437-447`

```python
for channel, voltage in channel_readings.items():
    if voltage >= config.voltage_threshold:  # Uses 3.3V
        logger.info(f"🎯 DETECTION! {channel}: {voltage:.3f}V > {config.voltage_threshold}V threshold")
        if self._should_record_detection(session_id, channel, current_time, config):
            event = self._create_detection_event(...)
            self._record_detection_event(session_id, event)
```

**Issue**: `voltage >= 3.3` where voltage is always 0.0V

---

## Why 0 Detections Occurred

### Critical Failure Points

1. **LabJack Not Streaming**
   - Connection manager exists but LabJack isn't streaming
   - `read_voltage()` fails silently
   - Returns 0.0V instead of error

2. **No Error Detection**
   - No verification that LabJack is connected
   - No logging when voltage read fails
   - Silent degradation to 0.0V

3. **Threshold Too High**
   - 3.3V threshold requires strong signal
   - 0.0V readings will never trigger
   - No adaptive threshold adjustment

4. **Missing Validation**
   ```python
   # MISSING:
   if not self.connection_manager.is_connected():
       logger.error("LabJack not connected!")
       return False

   if not self.connection_manager.is_streaming():
       logger.error("LabJack not streaming!")
       return False
   ```

---

## Required Voltage Level for Detection

### Current Configuration
- **Threshold**: 3.3V (configured in `dedicated_labjack_monitor.py:130`)
- **Actual voltage**: 0.0V (connection manager failure)
- **Detection condition**: `voltage >= 3.3`

### Required Voltage
- Minimum: **3.3V or higher**
- Recommended: 3.5V - 5.0V for reliable detection
- Current: 0.0V ❌

---

## Configuration Issues

### 1. Monitoring Configuration
**Location**: `dedicated_labjack_monitor.py:127-135`

```python
labjack_config = {
    'channels': video_timing_config.get('channels', ['AIN0']),
    'voltage_threshold': video_timing_config.get('voltage_threshold', 3.3),  # ✅ Correct
    'debounce_ms': video_timing_config.get('debounce_ms', 0),  # ✅ No debounce
    'sample_rate': video_timing_config.get('sample_rate', 20),  # ⚠️ Low rate
    'store_in_db': False,  # ✅ Handled by dedicated monitor
    'enable_websocket': video_timing_config.get('enable_websocket', True)
}
```

**Issues**:
- Sample rate: 20Hz (may miss fast signals)
- No verification of LabJack connection
- No fallback configuration

### 2. Connection Manager Integration
**Location**: `labjack_detection_service.py:136-143`

```python
try:
    from services.labjack_connection_manager import get_connection_manager
    self.connection_manager = get_connection_manager()
    logger.info("✅ Using shared LabJack connection manager")
except ImportError:
    self.connection_manager = None
    logger.warning("⚠️ LabJack connection manager not available")
```

**Issue**: ImportError is caught but monitoring continues anyway

---

## Recommended Fixes

### Fix #1: Add Connection Verification
```python
# In _monitoring_loop()
if not self.connection_manager or not self.connection_manager.is_connected():
    logger.error(f"❌ LabJack not connected for session {session_id}")
    self.detection_status[session_id] = DetectionStatus.ERROR
    return

if hasattr(self.connection_manager, 'is_streaming') and not self.connection_manager.is_streaming():
    logger.error(f"❌ LabJack not streaming for session {session_id}")
    # Attempt to start streaming
    self.connection_manager.start_stream(config.channels, config.sample_rate)
```

### Fix #2: Better Error Handling
```python
voltage = self.connection_manager.read_voltage(channel)
if voltage is None:
    logger.error(f"❌ Voltage read failed for {channel} - connection lost?")
    voltage = 0.0
elif voltage == 0.0:
    logger.warning(f"⚠️ Zero voltage on {channel} - verify hardware")
else:
    logger.debug(f"✅ {channel}: {voltage:.4f}V (threshold: {config.voltage_threshold}V)")
```

### Fix #3: Add Streaming Verification
```python
def start_monitoring(self, session_id: str, ...):
    # ... existing code ...

    # VERIFY LABJACK IS STREAMING BEFORE MONITORING
    if self.connection_manager:
        if not self.connection_manager.is_connected():
            logger.error("❌ LabJack not connected - cannot start monitoring")
            return False

        # Start streaming if not already active
        if hasattr(self.connection_manager, 'start_stream'):
            self.connection_manager.start_stream(channels, sample_rate)
            logger.info(f"✅ Started LabJack streaming for {session_id}")
```

### Fix #4: Lower Threshold for Testing
```python
# Temporary fix for debugging
'voltage_threshold': video_timing_config.get('voltage_threshold', 0.5),  # Lower for testing
```

---

## Logging Evidence

### Expected Logs (Not Present)
```
🎯 DETECTION! AIN0: 3.500V > 3.300V threshold
📝 Detection event recorded: 3.500V at 2025-10-01 11:45:23
```

### Actual Logs (Likely Present)
```
📊 AIN0: 0.0000V (threshold: 3.300V)
📊 AIN0: 0.0000V (threshold: 3.300V)
📊 AIN0: 0.0000V (threshold: 3.300V)
```

### Missing Logs
- No error when voltage read fails
- No warning when LabJack not streaming
- No connection verification logs

---

## Summary

### Why 0 Detections? ✅ ROOT CAUSE IDENTIFIED

1. ✅ Threshold configured correctly (3.3V)
2. ✅ Database schema supports voltage storage
3. ✅ Detection callbacks registered
4. ❌ **LabJack hardware NOT CONNECTED to system**
5. ❌ **Connection manager returns None → converted to 0.0V**
6. ❌ **0.0V < 3.3V threshold → NO DETECTIONS**

### Root Cause (CONFIRMED)
**Log Evidence** (backend.log):
```
2025-09-29 15:47:31,232 - services.labjack_hardware_service - WARNING - ⚠️ No LabJack devices detected for connection
```

**Detection Flow with No Hardware**:
```
start_monitoring() → ✅ Creates monitoring thread
_monitoring_loop() → ✅ Polls for voltages
connection_manager.read_voltage("AIN0") → ❌ Returns None (no device)
voltage = None → ❌ Converted to 0.0V
0.0V < 3.3V → ❌ NO DETECTION
Loop continues reading 0.0V forever
Session ends with 0 detections
```

### Connection Manager Behavior (Verified)
**Location**: `labjack_connection_manager.py:280-306`

```python
def read_voltage(self, channel: str) -> Optional[float]:
    if not self.is_connected():
        logger.warning(f"Cannot read {channel}: device not connected")
        return None  # ❌ Returns None when not connected

    try:
        voltage = ljm.eReadName(self._handle, channel)
        return voltage
    except Exception as e:
        logger.error(f"❌ Failed to read voltage from {channel}: {e}")
        return None  # ❌ Returns None on error
```

**Detection Service Conversion**:
```python
voltage = self.connection_manager.read_voltage(channel)
if voltage is not None:
    logger.debug(f"📊 {channel}: {voltage:.4f}V")
else:
    voltage = 0.0  # ❌ Converts None to 0.0V
```

### Critical Path to Fix

**IMMEDIATE ACTION REQUIRED**:
1. ✅ **Connect LabJack hardware to system** (PRIMARY FIX)
2. ✅ Verify LabJack USB connection (Windows or WSL bridge)
3. ✅ Test with `ljm.openS("ANY", "ANY", "ANY")` to confirm detection

**CODE IMPROVEMENTS** (After hardware is connected):
1. Add hardware check before starting monitoring
2. Fail fast if LabJack not detected
3. Better error messages to user
4. Add health check endpoint

**Recommended Fix**:
```python
def start_monitoring(self, session_id: str, ...):
    # VERIFY HARDWARE FIRST
    if not self.connection_manager.is_connected():
        if not self.connection_manager.connect():
            logger.error("❌ FATAL: LabJack hardware not detected - cannot start monitoring")
            raise RuntimeError("LabJack hardware not connected. Please connect device and retry.")

    # ... rest of monitoring code
```

### Next Steps
1. ✅ **Connect LabJack hardware** (T7, T4, or compatible device)
2. ✅ Verify driver installation (LJM library)
3. ✅ Test connection with minimal code
4. ✅ Restart backend with hardware connected
5. ✅ Run test session again
6. ✅ Verify detection events are created

### Testing Checklist
- [ ] Connect LabJack USB to system
- [ ] Verify LabJack appears in device manager/lsusb
- [ ] Install/update LJM drivers if needed
- [ ] Test with simple voltage read script
- [ ] Restart backend server
- [ ] Create new test session
- [ ] Verify detection events are logged
- [ ] Check database for voltage data
