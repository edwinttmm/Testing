# INVESTIGATION SUMMARY - EXECUTIVE BRIEF

**Issue:** Health monitor starts 28 seconds after application startup when device is not connected

**Status:** 🔴 ROOT CAUSE IDENTIFIED - CODE BUG

---

## The Problem in One Sentence

The application logs "HIL monitoring will be started per-test as needed" at startup, but then **immediately contradicts itself** by initializing the legacy hardware service with `force_wsl_connection=True`, which auto-connects to the device and starts health monitoring.

---

## The Smoking Gun

### 1. MISLEADING LOG MESSAGE (main.py:465)
```python
# Line 463: Comment says monitoring should only start per-test
# HIL monitoring should ONLY be started per-test via dedicated_labjack_monitor.py
logger.info("ℹ️ HIL monitoring will be started per-test as needed")
```

### 2. CONTRADICTORY CODE (main.py:1230)
```python
# Line 1230: 760 lines later, code contradicts the log message
hardware_initialized = initialize_hardware_service(force_wsl_connection=True)
# This IMMEDIATELY connects to device and starts health monitoring
```

---

## Exact Call Stack

```
main.py:1230
  → initialize_hardware_service(force_wsl_connection=True)
    → labjack_hardware_service.py:978: service = get_labjack_hardware_service()
    → labjack_hardware_service.py:979: devices = service.detect_devices()
    → labjack_hardware_service.py:984: success = service.connect(...)
      → labjack_hardware_service.py:424: self._start_health_monitoring()
        → Health monitor thread starts with 30-second interval
        → 28 seconds later: Health check fails with DEVICE_NOT_OPEN
```

---

## Timeline

| Time | Event | Code Location |
|------|-------|---------------|
| 09:29:07 | App starts | main.py:startup |
| 09:29:07 | Log: "per-test mode" | main.py:465 |
| 09:29:07 | **AUTO-CONNECT TRIGGERED** | main.py:1230 |
| 09:29:07 | Device connected | labjack_hardware_service.py:358 |
| 09:29:07 | Health monitor started | labjack_hardware_service.py:424 |
| 09:29:35 | Health check fails | labjack_hardware_service.py:758 |

---

## Why The Bug Exists

The codebase has **TWO CONFLICTING HARDWARE SERVICES**:

### Service 1: New "Real" LabJack Service (Per-Test Mode) ✅
- **Location:** `services/real_labjack_service.py`
- **Initialized:** main.py:1213
- **Mode:** `auto_connect=False` (per-test)
- **Behavior:** Does NOT connect at startup
- **Status:** Working as intended

### Service 2: Legacy Hardware Service (Auto-Connect Mode) ❌
- **Location:** `services/labjack_hardware_service.py`
- **Initialized:** main.py:1230
- **Mode:** `force_wsl_connection=True` (immediate connect)
- **Behavior:** AUTOMATICALLY connects at startup
- **Status:** **CONTRADICTS** per-test architecture

---

## The Fix (3 Options)

### Option A: Disable Legacy Service (FASTEST)
```bash
export DISABLE_LEGACY_LABJACK_HARDWARE=true
```
**Impact:** Skips legacy service entirely, uses only new per-test service

### Option B: Add auto_connect Parameter (CLEANEST)
```python
# main.py:1230
hardware_initialized = initialize_hardware_service(
    force_wsl_connection=True,
    auto_connect=False  # NEW: Prevent auto-connection
)
```
**Impact:** Legacy service initialized but doesn't connect until requested

### Option C: Remove Health Monitor Auto-Start (SURGICAL)
```python
# labjack_hardware_service.py:424
# Comment out or add conditional:
# self._start_health_monitoring()  # Don't start until explicitly needed
```
**Impact:** Health monitor only starts when manually triggered

---

## Recommended Solution

**Use Option A + Option B**:

1. **Short-term:** Set `DISABLE_LEGACY_LABJACK_HARDWARE=true` to immediately fix the issue
2. **Long-term:** Modify `initialize_hardware_service()` to accept `auto_connect=False` parameter
3. **Future:** Deprecate and remove legacy service entirely

---

## Why This Matters

1. **System Integrity:** Device shouldn't be claimed at startup in per-test mode
2. **Error Logs:** False-positive health check failures pollute logs
3. **Architecture Violation:** Code contradicts stated per-test design
4. **Device Conflicts:** Two services may compete for same device

---

## Files Modified for Fix

1. `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`
   - Add `auto_connect` parameter to `initialize_hardware_service()`

2. `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
   - Change line 1230 to use `auto_connect=False`

Or simply:

3. `/home/rigade/Testing/ai-model-validation-platform/backend/.env`
   - Add: `DISABLE_LEGACY_LABJACK_HARDWARE=true`

---

## Verification

After fix is applied, startup logs should show:

```
✅ Application startup completed successfully
ℹ️ HIL monitoring will be started per-test as needed
✅ Real LabJack hardware service initialized (lazy connection)
✅ LabJack hardware service initialized (per-test connection mode)
```

**And NO health check errors for first 30 seconds.**

---

## Conclusion

The health monitor starts because the legacy hardware service **ignores the per-test architecture** and automatically connects to the device at startup. The log message saying "per-test mode" is misleading because it's immediately contradicted by code 760 lines later.

**This is a straightforward code bug, not a hardware issue.**
