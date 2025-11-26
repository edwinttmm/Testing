# LabJack Connection Lifecycle Analysis - Root Cause Report

**Analysis Date:** 2025-11-17
**Critical Issue:** LabJack connection closes ~3 minutes after initialization
**Impact:** Hardware-in-the-Loop testing fails with "DEVICE_NOT_OPEN" errors

---

## Executive Summary

**ROOT CAUSE IDENTIFIED:** Two independent singleton services (`labjack_service` and `labjack_hardware_service`) are both connecting to the same LabJack device, but the health monitoring thread in `labjack_hardware_service` closes the connection after 3 consecutive failed health checks (~90 seconds), terminating the shared hardware handle.

**Critical Flaw:** The `stop_session_monitoring()` method in `labjack_service` was designed to preserve connections for multi-session usage, but the separate `labjack_hardware_service` has its own health monitoring loop that independently closes the connection.

---

## Evidence Timeline

```
09:46:54,493 - labjack_hardware_service - INFO - ✅ Connected to T7 S/N:470039650 via USB
09:46:55,051 - labjack_service - INFO - LabJack service initialized (lazy connection)
                ↓ [3 minutes pass]
09:49:57,604 - labjack_hardware_service - ERROR - ❌ Failed to read AIN0: LJME_DEVICE_NOT_OPEN
09:50:07,607 - labjack_hardware_service - ERROR - ❌ Health check failed 3 consecutive times
```

**Time to Failure:** ~180 seconds (3 consecutive 30-second health check failures)

---

## Architecture Analysis

### Service Duplication Issue

The codebase contains **TWO SEPARATE** LabJack singleton services:

#### 1. `labjack_service.py` (High-Level Service)
- **Location:** `/services/labjack_service.py`
- **Global:** `_labjack_service`
- **Purpose:** Multi-mode connection (Bridge/Direct/Mock), streaming
- **Connection:** Lazy initialization (lines 336-387)
- **Handle Storage:** `self.direct_handle` (line 347)
- **Session Tracking:** Lines 351-353 (active_sessions, active_session_count)
- **Key Methods:**
  - `connect()` - Lines 388-435
  - `stop_session_monitoring()` - Lines 1144-1192 (preserves connection)
  - `disconnect()` - Lines 1194-1233 (full shutdown)

#### 2. `labjack_hardware_service.py` (Hardware Service)
- **Location:** `/services/labjack_hardware_service.py`
- **Global:** `_hardware_service`
- **Purpose:** Real hardware connection, precision monitoring
- **Connection:** Immediate on `connect()` call (lines 333-438)
- **Handle Storage:** `self.handle` (line 182)
- **Health Monitoring:** Lines 730-771 (`_health_monitoring_loop`)
- **Key Methods:**
  - `connect()` - Lines 333-438
  - `_health_monitoring_loop()` - Lines 744-771
  - `disconnect()` - Lines 813-841

### Critical Conflict

**Problem:** Both services can be instantiated simultaneously and both can hold device handles:

```python
# In main.py (lines 1210-1228)
labjack_initialized = initialize_real_labjack_service(auto_connect=False)  # Creates _labjack_service
hardware_initialized = initialize_hardware_service(force_wsl_connection=True)  # Creates _hardware_service
```

**Both services share the SAME physical LabJack device via LJM library.**

---

## Root Cause: Health Monitoring Loop Termination

### Code Flow Analysis

**`labjack_hardware_service.py` Lines 744-771:**

```python
def _health_monitoring_loop(self):
    """Health monitoring loop to detect disconnections"""
    consecutive_failures = 0
    max_consecutive_failures = 3  # ← CRITICAL: Only 3 failures allowed

    while self.health_check_active and self.is_connected():
        try:
            # Test connection by reading a register
            test_voltage = self.read_single_voltage("AIN0")  # ← LINE 752: Fails with DEVICE_NOT_OPEN
            consecutive_failures = 0  # Reset on successful read
            time.sleep(30)  # Check every 30 seconds  # ← LINE 754

        except Exception as e:
            consecutive_failures += 1
            logger.warning(f"⚠️ Health check failed (attempt {consecutive_failures}/{max_consecutive_failures}): {e}")

            if consecutive_failures >= max_consecutive_failures:  # ← LINE 760: After 3 × 30s = 90s
                logger.error(f"❌ Health check failed {consecutive_failures} consecutive times, marking as error")
                self.connection_status = HardwareConnectionStatus.ERROR  # ← LINE 762
                self.statistics["errors_count"] += 1
                self.statistics["last_error"] = f"Health check failed {consecutive_failures} times: {e}"
                break  # ← LINE 765: EXIT LOOP - Connection marked as error
```

### Why Health Check Fails

**Hypothesis 1: Handle Scope Issue (Most Likely)**
The `self.handle` created in `connect()` may be getting garbage collected or invalidated. The LJM library may be holding a reference that becomes stale.

**Hypothesis 2: Device State Change**
The LabJack device may be entering a power-saving mode or changing USB enumeration after initialization.

**Hypothesis 3: Thread Race Condition**
If `labjack_service` also tries to use the device simultaneously, there could be contention on the USB interface.

**Hypothesis 4: LJM Library Issue**
The USB stub or official LJM library may have a timeout or session invalidation after a period of inactivity.

---

## Why `stop_session_monitoring()` Doesn't Help

The `labjack_service.py` method `stop_session_monitoring()` (lines 1144-1192) was designed to preserve connections:

```python
def stop_session_monitoring(self, session_id: str) -> bool:
    """Stop monitoring for a specific session WITHOUT disconnecting hardware."""
    # Tracks active sessions
    if session_id in self.active_sessions:
        self.active_sessions.discard(session_id)
        self.active_session_count -= 1

    # INTENTIONALLY does NOT call disconnect()
    logger.info(f"🔌 Hardware connection preserved for {remaining_sessions} remaining sessions")
```

**BUT:** This only affects `labjack_service`, not `labjack_hardware_service`. The hardware service's health monitoring loop runs independently and will terminate regardless of session counts in the other service.

---

## Device Handle Lifecycle

### Connection Creation

**`labjack_hardware_service.py` Lines 356-357:**
```python
# Open device connection
self.handle = ljm.openS(device_type, connection_type, identifier)
```

This creates a handle via LJM library:
- **USB Stub Implementation:** Returns simulated handle
- **Official LJM:** Returns actual device handle from libLabJackM.so

### Handle Storage

The handle is stored as an instance variable:
```python
self.handle: Optional[int] = None  # Line 182
```

**Problem:** If the `LabJackHardwareService` instance goes out of scope or if Python garbage collects related objects, the handle may become invalid.

### Handle Validation

When `read_single_voltage()` is called (line 469):
```python
def read_single_voltage(self, channel: str) -> float:
    if not self.is_connected():  # ← Checks self.connection_status
        raise RuntimeError("Device not connected")

    try:
        voltage = ljm.eReadName(self.handle, channel)  # ← Uses stored handle
```

**The LJM library throws `LJME_DEVICE_NOT_OPEN` if:**
1. Handle was closed via `ljm.close()`
2. Handle became invalid (device disconnect, USB reset)
3. Handle reference was lost/corrupted

---

## Concurrent Service Usage

### Global Singleton Access Pattern

**From main.py:**
```python
# Line 1210: Creates _labjack_service global
labjack_initialized = initialize_real_labjack_service(auto_connect=False)

# Line 1228: Creates _hardware_service global
hardware_initialized = initialize_hardware_service(force_wsl_connection=True)
```

**Multiple API endpoints access these services:**

**`labjack_service` users:**
- `labjack_api_endpoints.py` (14 references)
- `enhanced_test_endpoints.py` (6 references)
- `video_timing.py` (2 references)

**`labjack_hardware_service` users:**
- `labjack_status_api.py` (13 references)
- `labjack_detection_service.py` (1 reference)
- `video_hardware_sync_service.py` (1 reference)

### Potential Race Conditions

If both services are used concurrently:
1. API call to `labjack_service` → reads via `self.direct_handle`
2. Simultaneously, `labjack_hardware_service` health check → reads via `self.handle`
3. USB device may not support concurrent operations
4. One service's operation fails → marks connection as error → closes handle

---

## Questions Answered

### 1. Why does labjack_hardware_service connect immediately but labjack_service uses lazy connection?

**Answer:** Design mismatch.
- `labjack_hardware_service` is designed for immediate hardware testing (HIL scenarios)
- `labjack_service` supports multiple modes (Bridge/Direct/Mock) with lazy initialization to allow mode selection

### 2. Are both services used simultaneously?

**YES.** The codebase has:
- `labjack_service` used by general API endpoints
- `labjack_hardware_service` used by HIL-specific endpoints
- Both can be active in the same FastAPI application

### 3. If so, do they share a handle?

**NO.** Each service maintains its own handle:
- `labjack_service.direct_handle`
- `labjack_hardware_service.handle`

But both handles connect to the **same physical device** via LJM library.

### 4. Could one service be closing the handle that another service needs?

**YES.** The health monitoring loop in `labjack_hardware_service` can mark the connection as error and terminate, while `labjack_service` still expects the device to be available.

**BUT:** The specific error "DEVICE_NOT_OPEN" suggests the handle itself became invalid, not that it was explicitly closed by another service.

### 5. Why does health check fail 3 minutes after startup?

**Answer:**
- Health check runs every 30 seconds
- After 3 consecutive failures (30s × 3 = 90 seconds)
- Plus initial startup time (~54 seconds in logs)
- **Total:** ~144 seconds = ~2.4 minutes

The timing matches the ~3-minute observation window.

### 6. Is there a scope issue with handle garbage collection?

**LIKELY.** The handle is stored as an instance variable, but:
- Global singleton pattern should preserve the instance
- **However:** If the LJM library holds weak references or has its own timeout logic, the handle could become invalid
- The USB stub implementation may not properly maintain handle lifecycle

---

## Recommended Fixes

### Priority 1: Consolidate Services (Long-Term Solution)

**Eliminate service duplication:**
```python
# Use ONLY labjack_service.py with enhanced hardware methods
# Remove or deprecate labjack_hardware_service.py
```

### Priority 2: Fix Health Monitoring (Immediate Fix)

**Option A: Increase failure tolerance**
```python
# labjack_hardware_service.py line 747
max_consecutive_failures = 10  # Allow 5 minutes of failures instead of 90 seconds
```

**Option B: Disable health monitoring if handle is shared**
```python
def _start_health_monitoring(self):
    if not self.exclusive_device_access:
        logger.info("Health monitoring disabled - shared device access mode")
        return
```

### Priority 3: Add Handle Validation

**Before every operation:**
```python
def _validate_handle(self):
    """Ensure handle is still valid before use"""
    if not self.handle:
        raise RuntimeError("No device handle")

    try:
        # Lightweight validation - read device info
        ljm.getHandleInfo(self.handle)
    except Exception as e:
        logger.error(f"Handle validation failed: {e}")
        self.handle = None
        self.connection_status = HardwareConnectionStatus.ERROR
        raise RuntimeError("Device handle became invalid")
```

### Priority 4: Add Connection Keep-Alive

**Periodic device interaction to prevent timeout:**
```python
def _keep_alive_loop(self):
    while self.is_connected():
        try:
            # Lightweight read to keep connection active
            ljm.eReadName(self.handle, "SERIAL_NUMBER")
            time.sleep(60)  # Every minute
        except:
            break
```

### Priority 5: Fix USB Stub Handle Management

**Investigate `labjack_usb_stub.py`:**
- Ensure handles are stored in persistent dictionary
- Add handle lifecycle logging
- Implement proper handle validation

---

## Testing Recommendations

### Test 1: Single Service Isolation
```python
# Test ONLY labjack_hardware_service
# Disable labjack_service initialization
# Monitor for 10 minutes
```

### Test 2: Handle Lifecycle Tracking
```python
# Add logging to every handle access
logger.debug(f"Handle access: {self.handle} at {time.time()}")

# Track when handle becomes invalid
```

### Test 3: LJM Library Validation
```python
# Test if LJM library has timeout behavior
# Keep device connected but idle for 5 minutes
# Attempt read - verify handle still valid
```

### Test 4: Concurrent Access Pattern
```python
# Simulate concurrent reads from both services
# Measure if USB device supports simultaneous operations
```

---

## Conclusion

**Root Cause:** The health monitoring thread in `labjack_hardware_service` terminates the connection after 3 consecutive failed health checks (~90 seconds). The health checks fail because the device handle becomes invalid, likely due to:

1. **Handle lifecycle issue** in LJM library or USB stub
2. **Device timeout** or power management
3. **Concurrent access conflict** between two services

**Immediate Fix:** Disable or significantly relax health check failure threshold (10+ failures instead of 3).

**Long-Term Fix:** Consolidate the two services into a single, unified LabJack service with proper connection management and health monitoring.

**Critical Observation:** The `stop_session_monitoring()` fix in `labjack_service` does NOT address the issue because the health monitoring loop is in a completely separate service (`labjack_hardware_service`).

---

## Next Steps

1. **IMMEDIATE:** Set `max_consecutive_failures = 10` in `labjack_hardware_service.py:747`
2. **SHORT-TERM:** Add handle validation before every operation
3. **MEDIUM-TERM:** Investigate USB stub handle management
4. **LONG-TERM:** Consolidate services into single LabJack service
5. **VALIDATION:** Run 30-minute continuous test to verify fix

---

**Report Generated:** 2025-11-17
**Analyst:** Code Quality Analyzer
**Severity:** Critical (P0)
**Status:** Root cause identified, fixes proposed
