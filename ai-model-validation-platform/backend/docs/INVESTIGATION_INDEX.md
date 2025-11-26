# Investigation Report Index: Health Monitor Premature Start

**Date:** 2025-11-19
**Issue:** Health monitor starts 28 seconds after startup when device is not connected
**Status:** 🔴 ROOT CAUSE IDENTIFIED

---

## Quick Links

1. **[Executive Summary](INVESTIGATION_SUMMARY_EXECUTIVE.md)** - 5-minute read, non-technical
2. **[Full Investigation Report](INVESTIGATION_HEALTH_MONITOR_PREMATURE_START.md)** - Complete analysis
3. **[Visual Diagrams](INVESTIGATION_VISUAL_DIAGRAM.md)** - Flow charts and timelines
4. **[Code Evidence](INVESTIGATION_CODE_EVIDENCE.md)** - Exact code locations and snippets

---

## The Problem (One Sentence)

The application logs "HIL monitoring will be started per-test as needed" but then immediately contradicts itself by auto-connecting to the device and starting health monitoring at startup.

---

## Root Cause (Technical)

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Line:** 1230

```python
hardware_initialized = initialize_hardware_service(force_wsl_connection=True)
```

This function:
1. Creates singleton service instance
2. Scans for available devices
3. **Automatically connects to first device found**
4. **Automatically starts health monitoring** (line 424 of `labjack_hardware_service.py`)

---

## Evidence Summary

### Timeline:
- **09:29:07** - App starts
- **09:29:07** - Log: "per-test mode"
- **09:29:07** - Legacy service auto-connects
- **09:29:07** - Health monitor starts
- **09:29:35** - Health check fails (DEVICE_NOT_OPEN)

### Call Stack:
```
main.py:1230
  → initialize_hardware_service()
    → get_labjack_hardware_service()
    → detect_devices()
    → connect()  ← AUTO-CONNECTS
      → _start_health_monitoring()  ← BUG HERE
```

---

## The Fix (3 Options)

### Option A: Environment Variable (Fastest)
```bash
export DISABLE_LEGACY_LABJACK_HARDWARE=true
```

### Option B: Code Modification (Cleanest)
Add `auto_connect=False` parameter:
```python
# main.py:1230
hardware_initialized = initialize_hardware_service(
    force_wsl_connection=True,
    auto_connect=False  # NEW
)
```

### Option C: Conditional Health Monitoring (Surgical)
Modify `_start_health_monitoring()` to check per-test mode:
```python
# labjack_hardware_service.py:733
def _start_health_monitoring(self):
    # ... existing checks ...
    if not self.should_be_connected:  # NEW
        logger.debug("Skipping health monitor - per-test mode")
        return
    # ... start thread ...
```

---

## Files Analyzed

1. `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
   - Line 465: "per-test" log message
   - Line 1213: New service (works correctly)
   - Line 1230: Legacy service (causes bug)

2. `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`
   - Line 172: `__init__()` (doesn't start monitoring)
   - Line 424: `connect()` (starts monitoring - BUG)
   - Line 733: `_start_health_monitoring()` (no per-test check)
   - Line 750: `_health_monitoring_loop()` (fails at line 758)
   - Line 967: `initialize_hardware_service()` (auto-connects)

---

## Key Findings

### Why Health Monitor Starts:
1. ✅ Singleton created correctly (Phase 1 fix works)
2. ❌ Initialization function auto-connects (shouldn't in per-test mode)
3. ❌ Connect method unconditionally starts health monitor
4. ❌ No check for per-test mode before starting health thread

### Why It Fails:
1. Connection succeeds initially (USB stub or real device)
2. Health monitor thread sleeps 30 seconds
3. Device becomes unavailable in that 28-second window
4. First health check fails with LJME_DEVICE_NOT_OPEN (error 1224)

### Two Services Conflict:
1. **New Service:** `real_labjack_service.py` (per-test mode) ✅
2. **Legacy Service:** `labjack_hardware_service.py` (auto-connect) ❌

---

## Recommended Action

**Immediate (5 minutes):**
```bash
# Add to .env file
DISABLE_LEGACY_LABJACK_HARDWARE=true
```

**Short-term (1 hour):**
Modify `initialize_hardware_service()` to accept `auto_connect` parameter and default to `False`.

**Long-term (future):**
Deprecate and remove legacy hardware service entirely. Use only the new per-test service.

---

## Verification

After fix, startup logs should show:
```
✅ Application startup completed successfully
ℹ️ HIL monitoring will be started per-test as needed
✅ Real LabJack hardware service initialized (lazy connection)
✅ LabJack hardware service initialized (per-test connection mode)
```

**No health check errors for first 30+ seconds.**

---

## Documentation Structure

```
INVESTIGATION_INDEX.md (this file)
├── INVESTIGATION_SUMMARY_EXECUTIVE.md
│   └── Non-technical summary for stakeholders
│       • 5-minute read
│       • Problem statement
│       • Fix options
│       • Impact assessment
│
├── INVESTIGATION_HEALTH_MONITOR_PREMATURE_START.md
│   └── Complete technical investigation
│       • Full call stack analysis
│       • Timeline of events
│       • Code location details
│       • Detailed fix recommendations
│       • Verification procedures
│
├── INVESTIGATION_VISUAL_DIAGRAM.md
│   └── Visual flow charts and diagrams
│       • Call chain visualization
│       • Timeline diagram
│       • Before/after comparison
│       • Service conflict diagram
│
└── INVESTIGATION_CODE_EVIDENCE.md
    └── Exact code snippets and evidence
        • 10 pieces of code evidence
        • Line-by-line analysis
        • Actual log output
        • Missing code examples
```

---

## Investigation Methodology

### Tools Used:
- `Read` - Read source files
- `Grep` - Search for function calls and patterns
- `Bash` - List files and verify structure

### Files Examined:
- `main.py` (1300+ lines)
- `labjack_hardware_service.py` (1015 lines)
- Log output analysis

### Search Patterns:
```bash
grep -n "health_monitoring\|start.*health\|_health_monitoring_loop\|health_thread"
grep -rn "get_labjack_hardware_service\|initialize_hardware"
grep -rn "per-test\|HIL monitoring will be started"
```

---

## Questions Answered

### 1. Where does health monitor start?
**Answer:** Line 424 of `labjack_hardware_service.py` in the `connect()` method.

### 2. Why does it start when device not connected?
**Answer:** Device **IS** connected at startup by `initialize_hardware_service()` function.

### 3. What is "per-test mode"?
**Answer:** Architecture where device connection is deferred until test session starts. The new service follows this, but legacy service doesn't.

### 4. Why does it fail 28 seconds later?
**Answer:** Health monitor sleeps 30 seconds. Device becomes unavailable during that window. First check fails with DEVICE_NOT_OPEN.

### 5. Is this a hardware issue?
**Answer:** No. It's a code bug - legacy service contradicts per-test architecture.

### 6. Which service should we use?
**Answer:** The new `real_labjack_service.py` with per-test mode. Disable the legacy service.

---

## Related Documents

- **ADR-001:** LabJack Device Conflict Resolution
- **Phase 1 Fix:** Singleton Pattern Implementation
- **CRITICAL_FIXES_APPLIED_SUMMARY.md:** Previous fixes documentation

---

## Conclusion

**The health monitor starts because the legacy hardware service auto-connects at startup and unconditionally starts health monitoring, contradicting the "per-test mode" architecture described in the logs.**

**Fix:** Add `auto_connect=False` parameter to `initialize_hardware_service()` or disable legacy service entirely.

**Impact:** Low-risk fix. Health monitoring will start when test sessions are created, as intended.

---

**Generated:** 2025-11-19
**Investigator:** Claude Code Quality Analyzer
**Files Created:** 5 investigation documents (54KB total)
