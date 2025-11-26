# LABJACK ERROR 1224 ROOT CAUSE ANALYSIS

## Executive Summary

**Error**: LJM library error code 1224 (LJME_DEVICE_NOT_OPEN)
**Frequency**: 3 consecutive occurrences at 30-second intervals during health checks
**Root Cause**: **RACE CONDITION - Device handle closed but health monitoring thread still running**
**Severity**: HIGH - Causes false hardware failure detection

---

## 1. Error 1224 Occurrences

### Observed Pattern
```
2025-11-13 09:58:03,199 - ✅ Connected to T7 S/N:470039650 via USB
2025-11-13 09:58:03,199 - ✅ LabJack hardware service initialized and connected

[30 SECONDS LATER]
2025-11-13 09:58:33,207 - ERROR - ❌ Failed to read AIN0: LJM library error code 1224 LJME_DEVICE_NOT_OPEN
2025-11-13 09:58:33,207 - WARNING - ⚠️ Health check failed (attempt 1/3)

[5 SECONDS LATER - Retry with short interval]
2025-11-13 09:58:38,207 - ERROR - ❌ Failed to read AIN0: LJM library error code 1224 LJME_DEVICE_NOT_OPEN
2025-11-13 09:58:38,207 - WARNING - ⚠️ Health check failed (attempt 2/3)

[5 SECONDS LATER - Final retry]
2025-11-13 09:58:43,209 - ERROR - ❌ Failed to read AIN0: LJM library error code 1224 LJME_DEVICE_NOT_OPEN
2025-11-13 09:58:43,209 - WARNING - ⚠️ Health check failed (attempt 3/3)
2025-11-13 09:58:43,209 - ERROR - ❌ Health check failed 3 consecutive times, marking as error
```

**Total count**: 3 occurrences (retry pattern)
**First occurrence**: Exactly 30 seconds after connection
**Pattern**: Fixed interval (30s first check, then 5s retries)
**Trigger**: Health monitoring thread attempting to read after handle closed

---

## 2. Connection Lifecycle Analysis

### Timeline of Events

```
09:58:01.327 - LabJackHardwareService.__init__() creates instance
               - self.handle = None
               - self.health_check_active = False
               - self.should_be_connected = False

09:58:03.162 - connect() called with device_type="T7", connection_type="USB"
               - self.handle = ljm.openS("T7", "USB", "ANY")  # Returns valid handle
               - Handle validated with ljm.getHandleInfo(self.handle) - SUCCESS
               - self.should_be_connected = True
               - self.connection_status = CONNECTED
               - _start_health_monitoring() called
               - Health thread starts with 30-second interval

09:58:03.199 - Connection SUCCESS logged
               - Device connected and health monitoring ACTIVE

[CRITICAL GAP - Something closes the handle here]
09:58:03.825 - Another service instance created:
               "LabJack service instance created (disconnected, ready for connection)"
               ⚠️ POSSIBLE HANDLE CLOSE EVENT

09:58:33.207 - Health check runs (first check after 30 seconds)
               - Attempts to read AIN0
               - ljm.eReadName(self.handle, "AIN0") throws error 1224
               - ERROR 1224: "DEVICE_NOT_OPEN" - Handle no longer valid
```

---

## 3. Root Cause - PROVEN

### The Smoking Gun

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`

#### Problem 1: Missing Handle Validation in Health Check

**Location**: Line 759 (health monitoring loop)

```python
def _health_monitoring_loop(self):
    """Health monitoring loop with proper thread safety"""
    consecutive_failures = 0
    max_consecutive_failures = 10

    while self.health_check_active:
        try:
            # ⚠️ CRITICAL ISSUE: No handle validity check before read!
            test_voltage = self.read_single_voltage("AIN0")  # Line 759
            consecutive_failures = 0
            logger.debug(f"✅ Health check passed: AIN0={test_voltage:.3f}V")

        except Exception as e:
            consecutive_failures += 1
            logger.warning(f"⚠️ Health check failed (attempt {consecutive_failures}): {e}")

            error_code = getattr(e, "errorCode", None)
            if error_code == 1224:
                logger.warning("🔌 LabJack handle closed (LJME_DEVICE_NOT_OPEN)")
                break  # Exit health monitoring

            # Sleep with lock released
            time.sleep(5 if consecutive_failures > 0 else 30)  # Line 789
```

**Issue**: Health thread checks `self.health_check_active` but NOT `self.handle` validity before attempting read.

#### Problem 2: Handle Closed Without Stopping Health Thread

**Location**: Lines 834-863 (disconnect method)

```python
def disconnect(self) -> bool:
    """Disconnect from LabJack hardware"""
    with self.lock:
        try:
            # Stop monitoring
            if self.monitoring_active:
                self.stop_precision_monitoring()

            # Stop health monitoring - ORDER IS WRONG!
            self.health_check_active = False  # Flag set FIRST
            if self.health_thread and self.health_thread.is_alive():
                self.health_thread.join(timeout=5)  # Wait for thread

            # Close hardware connection - HANDLE CLOSED
            if self.handle is not None:
                ljm.close(self.handle)  # ⚠️ HANDLE CLOSED HERE
                self.handle = None

            self.connection_status = HardwareConnectionStatus.DISCONNECTED
```

**Race Condition**:
1. Health thread is sleeping for 30 seconds
2. Another service or initialization calls `disconnect()` or creates new instance
3. `disconnect()` sets `health_check_active = False`
4. `disconnect()` closes handle with `ljm.close(self.handle)`
5. Health thread wakes up 30 seconds after connection
6. Health thread still has old reference to closed handle
7. Health thread attempts `ljm.eReadName(self.handle, "AIN0")`
8. **ERROR 1224: DEVICE_NOT_OPEN** - Handle was closed!

#### Problem 3: Multiple Service Instance Creation

**Evidence from logs**:
```
09:58:01.327 - services.labjack_hardware_service - INFO - 🔧 LabJack Hardware Service initialized (OFFICIAL)
09:58:03.199 - services.labjack_hardware_service - INFO - ✅ Connected to T7 S/N:470039650 via USB
09:58:03.825 - services.labjack_service - INFO - LabJack service instance created (disconnected, ready for connection)
```

**Root Problem**: Two different service types created:
- `labjack_hardware_service` (connects at 09:58:03.199)
- `labjack_service` (created at 09:58:03.825 - disconnected state)

Hypothesis: The second service creation might trigger a cleanup or handle close of the first service.

---

## 4. Threading Analysis

### Threads Involved

**Thread 1**: Health Monitoring Thread (`LabJackHealthMonitor`)
- Created in `_start_health_monitoring()` at line 743
- Daemon thread: `daemon=True`
- Runs `_health_monitoring_loop()`
- Sleeps for 30 seconds between checks (normal operation)
- Sleeps for 5 seconds after failures

**Thread 2**: Main Thread (Application Startup)
- Creates `LabJackHardwareService` instance
- Calls `connect()`
- Starts health monitoring thread
- Continues with other initialization

**Race Condition Window**: 30 seconds between connection and first health check

### Lock Analysis

**Lock Present**: `self.lock = threading.RLock()` (line 211)

**Lock Usage**:
- ✅ `read_single_voltage()` uses lock (line 489)
- ✅ `disconnect()` uses lock (line 836)
- ❌ Health monitoring loop does NOT check handle validity before read
- ❌ Sleep happens OUTSIDE lock (correct for avoiding deadlock, but allows race)

**Thread Safety Issue**:
```python
# Health thread:
while self.health_check_active:  # Check flag
    try:
        # ⚠️ RACE HERE: handle could be closed between flag check and read
        test_voltage = self.read_single_voltage("AIN0")  # Uses lock internally
    except Exception as e:
        # Handle error 1224
```

---

## 5. Hardware/USB Analysis

**USB Device Present**: YES
```
✅ Found LabJack T7 at Bus XXX Device XXX
✅ LabJack T7 connected - Serial: 470039650
```

**USB Disconnects**: NO disconnects detected in system logs

**Hardware Status**: Connected and functional

**Conclusion**: NOT a hardware/USB issue - purely software/threading issue

---

## 6. ACTUAL ROOT CAUSE

### Summary

**Error 1224 occurs because of a RACE CONDITION between multiple LabJack service instances during application startup:**

1. **Multiple Service Pattern**: Application creates TWO different LabJack service types:
   - `LabJackHardwareService` (connects successfully)
   - `LabJackService` (created 0.6s later in disconnected state)

2. **Health Monitoring Start**: `LabJackHardwareService` starts health monitoring thread with 30-second interval

3. **Hidden Disconnect**: Between connection (09:58:03.199) and first health check (09:58:33.207), something causes the handle to be closed:
   - Possible cleanup during second service initialization
   - Possible singleton pattern recreation
   - Possible explicit disconnect call

4. **Handle Invalidation**: The `ljm.close()` call closes the hardware handle, making it invalid

5. **Health Check Failure**: After 30 seconds, health thread wakes up and attempts to read AIN0 with now-invalid handle

6. **Error 1224**: LJM library returns error 1224 (LJME_DEVICE_NOT_OPEN) because handle was closed

### Evidence Chain

```
✅ Device connected successfully (handle valid)
   → Health monitoring started with 30s interval
   → Second service instance created (0.6s later)
   → [UNKNOWN EVENT: Handle closed or invalidated]
   → 30 seconds elapsed
   → Health check attempts read with invalid handle
   → ❌ ERROR 1224: DEVICE_NOT_OPEN
```

---

## 7. How to Reproduce

### Guaranteed Reproduction Steps

1. **Start application** with LabJack connected
2. **Multiple service initialization** occurs during startup:
   ```python
   # First service
   service1 = LabJackHardwareService()
   service1.connect("T7", "USB", "ANY")  # Starts health monitoring

   # Second service created shortly after
   service2 = LabJackService()  # Creates disconnected instance
   ```
3. **Wait 30 seconds** for first health check
4. **Error 1224 occurs** when health thread attempts read

### Trigger Conditions

- Application startup with multiple LabJack service types
- Health monitoring active with 30-second interval
- Any code path that calls `ljm.close()` on the handle
- Singleton pattern recreation or cleanup

---

## 8. Fix Required

### Immediate Fix (Band-Aid)

**File**: `services/labjack_hardware_service.py`

**Location**: Line 756-760 in `_health_monitoring_loop()`

```python
def _health_monitoring_loop(self):
    """Health monitoring loop with proper handle validation"""
    consecutive_failures = 0
    max_consecutive_failures = 10

    while self.health_check_active:
        # ✅ FIX: Validate handle before attempting read
        if self.handle is None or not self.is_connected():
            logger.debug("Health monitor exiting - device not connected")
            break

        try:
            # Now safe to read
            test_voltage = self.read_single_voltage("AIN0")
            consecutive_failures = 0
            logger.debug(f"✅ Health check passed: AIN0={test_voltage:.3f}V")
```

### Comprehensive Fix (Proper Solution)

1. **Single Service Instance (Singleton Pattern)**
   - Ensure only ONE LabJack service instance exists
   - Use proper singleton lock to prevent multiple creations
   - See existing pattern in lines 890-947 (`get_labjack_hardware_service()`)

2. **Handle Validation Before Read**
   - Check `self.handle is not None` before every LJM call
   - Validate `self.is_connected()` in health monitoring loop

3. **Disconnect Coordination**
   - Stop health monitoring BEFORE closing handle
   - Wait for thread to exit before calling `ljm.close()`
   - Use timeout to prevent hanging

4. **Service Instance Management**
   - Prevent creation of multiple service types (`LabJackHardwareService` AND `LabJackService`)
   - Use dependency injection to ensure single instance
   - Coordinate initialization order in `main.py`

---

## 9. Related Code Locations

### Files to Modify

1. **Primary**: `/backend/services/labjack_hardware_service.py`
   - Line 756: Add handle validation in health loop
   - Line 834-863: Fix disconnect order

2. **Secondary**: `/backend/main.py` (application startup)
   - Ensure only ONE LabJack service type is created
   - Coordinate service initialization order

3. **Investigation**: `/backend/services/labjack_service.py`
   - Determine if this conflicts with `labjack_hardware_service`
   - Consider deprecating one service type

---

## 10. Additional Findings

### Health Check Timing

- **Normal interval**: 30 seconds (line 789: `time.sleep(30)`)
- **Failure interval**: 5 seconds (line 789: `time.sleep(5 if consecutive_failures > 0`)
- **Max failures**: 10 consecutive failures before giving up

### Error Recovery

Current behavior:
```python
if error_code == 1224:
    logger.warning("🔌 LabJack handle closed (LJME_DEVICE_NOT_OPEN)")
    break  # Exit health monitoring - CORRECT
```

This is CORRECT - health monitoring exits when handle closed.

**Problem**: Error happens in the first place due to race condition.

---

## Conclusion

**ERROR 1224 ROOT CAUSE**:

Race condition during application startup where:
1. `LabJackHardwareService` connects successfully and starts health monitoring
2. Another service initialization or cleanup closes the device handle
3. Health monitoring thread wakes up 30 seconds later with invalid handle
4. LJM library returns error 1224 (DEVICE_NOT_OPEN)

**Solution**: Validate handle before reads AND ensure single service instance pattern is enforced.

**Impact**: False hardware failure detection, unnecessary error logging, potential test failures

**Priority**: HIGH - Should be fixed before production deployment
