# MYSTERY #2: LabJack Connection Lifecycle Investigation

## Investigation Report
**Date**: 2025-11-19
**Investigator**: System Architecture Designer
**Objective**: Determine why LabJack connection closes 8 seconds after "connection preserved" log

---

## Executive Summary

**FINDING: DUAL-SERVICE ARCHITECTURE WITH DISCONNECTED LIFECYCLE MANAGEMENT**

The "Connection preserved - 0 sessions remaining" followed by "LJME_DEVICE_NOT_OPEN" 8 seconds later is caused by **two separate services managing the same hardware connection with no coordination**.

### Root Cause
1. **LabJackService** logs "Connection preserved" and manages session counts
2. **LabJackHardwareService** actually owns the hardware handle and runs health checks
3. **No coordination** between these services when sessions end
4. Health check in LabJackHardwareService attempts to read from hardware 8s after session ends
5. Connection has been closed by some other code path, causing LJME_DEVICE_NOT_OPEN

---

## Architecture Discovery

### Dual Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  DedicatedLabJackMonitor                    │
│                                                             │
│  self.labjack_monitor = LabJackDetectionMonitor()         │
│      ├── self.labjack_service (LabJackService)            │
│      │   └── Session management, connection status        │
│      │                                                      │
│      └── self.hardware_service (LabJackHardwareService)    │
│          └── ACTUAL hardware handle + health checks        │
└─────────────────────────────────────────────────────────────┘
```

**Critical Files:**
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
  - Line 154: `self.labjack_service = labjack_service or get_labjack_service()`
  - Line 156: `self.hardware_service = get_labjack_hardware_service()`

---

## Connection Lifecycle Mapping

### Phase 1: Session Start
```
1. DedicatedLabJackMonitor.start_hil_session_monitoring()
2. LabJackDetectionMonitor created
   ├── LabJackService initialized (session tracking)
   └── LabJackHardwareService initialized (hardware handle)
3. Hardware connected via LabJackHardwareService.connect()
   └── Line 425: self._start_health_monitoring()
4. LabJackService.start_session(session_id)
   └── Line 1684: logger.info("🔌 Connection preserved for active session")
```

### Phase 2: Session Running
```
Health Monitor Thread (LabJackHardwareService):
├── Line 751: _health_monitoring_loop()
├── Line 759: test_voltage = self.read_single_voltage("AIN0")
└── Runs every 30 seconds while health_check_active = True
```

### Phase 3: Session End (THE PROBLEM)
```
Timeline from logs:
13:40:11.771 - DedicatedLabJackMonitor.stop_session_monitoring()
            └─> Line 2101: success = self.labjack_monitor.stop_monitoring(session_id)
            └─> LabJackDetectionMonitor.stop_monitoring()
            └─> Line 2471: logger.info("🔌 Connection preserved - 0 sessions remaining")

13:40:19.473 - LabJackHardwareService health check (8s later)
            └─> Line 759: test_voltage = self.read_single_voltage("AIN0")
            └─> Line 490: if not self.is_connected(): raise RuntimeError
            └─> ERROR: LJME_DEVICE_NOT_OPEN (error 1224)
```

---

## Code Evidence Analysis

### 1. LabJackDetectionService Connection Preservation

**File**: `services/labjack_detection_service.py`

**Line 2467-2476**: Connection preservation logic
```python
def _cleanup_session_preserving_connection(self, session_id: str):
    # Remove from active sessions
    self.active_sessions.pop(session_id, None)
    # ... cleanup session data ...

    # CRITICAL: DO NOT close hardware connection - preserve for other sessions
    # The connection manager handles the actual hardware connection lifecycle
    if self.connection_manager:
        remaining_count = len(self.active_sessions)
        logger.info(f"🔌 Connection preserved - {remaining_count} sessions remaining")

        # Only log connection status if no sessions remain
        if remaining_count == 0:
            logger.info("🔌 LabJack connection idle but maintained for future sessions")
```

**Analysis**:
- ✅ Correctly preserves connection
- ✅ Logs "Connection preserved - 0 sessions remaining"
- ❌ NO coordination with LabJackHardwareService
- ❌ NO notification that hardware_service should stop health checks

### 2. LabJackHardwareService Health Monitoring

**File**: `services/labjack_hardware_service.py`

**Line 734-749**: Health monitoring starts on connection
```python
def _start_health_monitoring(self):
    """Start health monitoring thread"""
    if self.health_thread and self.health_thread.is_alive():
        return
    if not self.is_connected():
        logger.debug("Skipping health monitor start - hardware not connected")
        return

    self.health_check_active = True
    self.health_thread = threading.Thread(
        target=self._health_monitoring_loop,
        daemon=True,
        name="LabJackHealthMonitor"
    )
    self.health_thread.start()
```

**Line 751-789**: Health monitoring loop
```python
def _health_monitoring_loop(self):
    """Health monitoring loop with proper thread safety"""
    consecutive_failures = 0
    max_consecutive_failures = 10

    while self.health_check_active:
        try:
            # read_single_voltage() now has internal lock protection
            test_voltage = self.read_single_voltage("AIN0")
            consecutive_failures = 0
            logger.debug(f"✅ Health check passed: AIN0={test_voltage:.3f}V")

        except RuntimeError as e:
            # Device not connected - expected during disconnection
            if "not connected" in str(e).lower():
                logger.debug("Health monitor exiting - device disconnected")
                break
            consecutive_failures += 1

        except Exception as e:
            consecutive_failures += 1
            error_code = getattr(e, "errorCode", None)
            if error_code == 1224:  # LJME_DEVICE_NOT_OPEN
                logger.warning("🔌 LabJack handle closed (LJME_DEVICE_NOT_OPEN)")
                break

        # Sleep outside any locks
        time.sleep(5 if consecutive_failures > 0 else 30)
```

**Analysis**:
- ⚠️ Health check runs every 30 seconds
- ⚠️ Continues running even when sessions = 0
- ❌ NO notification when LabJackDetectionService stops monitoring
- ❌ health_check_active never set to False by session cleanup
- ✅ Handles error 1224 gracefully by breaking loop

### 3. Connection Closure Paths

**Search Results**: All places where connection can be closed

```bash
# Direct connection closure:
services/labjack_hardware_service.py:849:  ljm.close(self.handle)
services/labjack_hardware_service.py:453:  ljm.close(self.handle) # during error cleanup
services/labjack_service.py:1755:          ljm.close(self.direct_handle)
services/labjack_service.py:709:           self.ljm_module.close(self.direct_handle)
services/labjack_service.py:1214:          self.ljm_module.close(self.direct_handle)
```

**File**: `services/labjack_service.py`

**Line 1722-1770**: Disconnect method with session protection
```python
async def disconnect(self, force: bool = False):
    """Disconnect from LabJack hardware completely.

    CRITICAL FIX: Prevents disconnection while sessions are active unless forced.
    """
    try:
        # CRITICAL FIX: Block disconnect if sessions are active
        active_count = getattr(self, 'active_session_count', 0)
        if active_count > 0 and not force:
            logger.error(f"❌ DISCONNECT BLOCKED: {active_count} sessions still active")
            return False

        if force and active_count > 0:
            logger.warning(f"🚨 FORCE DISCONNECT: Closing connection despite {active_count} active sessions")

        # ... proceed with disconnect ...
        if self.mode == ConnectionMode.DIRECT and self.direct_handle:
            if hasattr(self, 'ljm_module') and self.ljm_module:
                ljm = self.ljm_module
                ljm.close(self.direct_handle)
                logger.info("🔌 Hardware connection closed")
```

**Analysis**:
- ✅ LabJackService.disconnect() has session protection
- ❌ LabJackHardwareService.disconnect() has NO session protection
- ⚠️ Two independent disconnect methods for same hardware

---

## The 8-Second Mystery Explained

### Timing Analysis

```
T+0.000s  - Session ends
T+0.000s  - LabJackDetectionService logs "Connection preserved - 0 sessions remaining"
T+0.000s  - Session cleanup completes
T+0.000s  - health_check_active STILL TRUE (never set to False)
T+0.000s  - Hardware handle STILL VALID (not closed by session cleanup)

[Health monitor continues running in background thread]

T+8.000s  - Health monitor wakes up from sleep(30s) after ~8s elapsed
T+8.473s  - Attempts: test_voltage = self.read_single_voltage("AIN0")
T+8.473s  - Reads: self.handle (EXPECTING valid handle)
T+8.473s  - LJM library error: handle is CLOSED (error 1224)
T+8.473s  - ERROR: LJME_DEVICE_NOT_OPEN
```

**Key Questions:**
1. ✅ Why "Connection preserved" appears? - LabJackDetectionService correctly preserves
2. ❓ **WHY was handle closed?** - SOMETHING closed it between T+0s and T+8s
3. ❓ What closed the handle? - Need to trace closure path
4. ❓ Why wasn't health_check_active set to False? - No coordination between services

---

## Missing Coordination Mechanisms

### Current State
```
LabJackDetectionService          LabJackHardwareService
     (manages sessions)           (owns hardware handle)
          │                                │
          │ 0 sessions remaining           │
          │ "Connection preserved"         │
          │                                │
          ✓ (logs message)                 │
          │                                │
          │                      health_check_active=True
          │                                │
          │                         [8s later]
          │                                │
          │                        ❌ LJME_DEVICE_NOT_OPEN
```

### What Should Happen
```
LabJackDetectionService          LabJackHardwareService
     (manages sessions)           (owns hardware handle)
          │                                │
          │ 0 sessions remaining           │
          ├──────────notify─────────────>  │
          │                                │
          │                    health_check_active=False
          │                                │
          │                    [monitor sleeps indefinitely]
```

---

## Critical Code Locations

### Session End Path
1. **DedicatedLabJackMonitor** (`services/dedicated_labjack_monitor.py`)
   - Line 2095-2108: stop_session_monitoring()
   - Line 2101: `success = self.labjack_monitor.stop_monitoring(session_id)`

2. **LabJackDetectionMonitor** (`services/labjack_detection_service.py`)
   - Line 581: `stop_monitoring()` (redirects to stop_session_monitoring)
   - Line 482-579: `stop_session_monitoring()`
   - Line 570: `self._cleanup_session_preserving_connection(session_id)`
   - Line 2467-2476: `_cleanup_session_preserving_connection()`
   - Line 2471: Logs "🔌 Connection preserved - {remaining_count} sessions remaining"

### Health Check Path
3. **LabJackHardwareService** (`services/labjack_hardware_service.py`)
   - Line 425: `self._start_health_monitoring()` (on connect)
   - Line 734-749: `_start_health_monitoring()`
   - Line 751-789: `_health_monitoring_loop()`
   - Line 759: `test_voltage = self.read_single_voltage("AIN0")`
   - Line 777: Catches error 1224 (LJME_DEVICE_NOT_OPEN)

### Connection Closure Path
4. **Connection Close Methods**
   - LabJackHardwareService.disconnect() - Line 834-862
   - LabJackService.disconnect() - Line 1722-1770
   - Direct ljm.close() calls - Lines 453, 709, 849, 1214, 1755

---

## Unanswered Questions (Next Investigation)

1. **WHO closed the handle between T+0s and T+8s?**
   - Need to add logging to ljm.close() calls
   - Need to trace who called disconnect() on hardware_service
   - Check for cleanup/garbage collection paths

2. **Is there a timeout mechanism?**
   - Check for idle connection timeouts
   - Check for automatic cleanup after sessions=0

3. **Is there a race condition?**
   - Multiple threads accessing health_check_active
   - Connection manager interference

4. **Why wasn't this caught in testing?**
   - Tests might force disconnect immediately
   - Tests might not run long enough to hit health check cycle

---

## Architectural Issues Identified

### Issue 1: Dual Service Ownership
**Problem**: Two services manage same hardware connection independently
- LabJackService (high-level session management)
- LabJackHardwareService (low-level hardware access)

**Risk**: Desynchronization, race conditions, unclear ownership

### Issue 2: No Service Communication
**Problem**: Services don't notify each other of state changes
- Session count changes in LabJackDetectionService
- Health monitoring continues in LabJackHardwareService
- No event bus, no callbacks, no shared state

**Risk**: Zombie threads, resource leaks, unexpected errors

### Issue 3: Health Monitor Lifecycle
**Problem**: Health monitor has no concept of "idle but preserved"
- Only states: CONNECTED vs DISCONNECTED
- No "idle" state for 0 sessions but connection preserved
- Continues attempting reads when unnecessary

**Risk**: Error spam, resource waste, confusion in logs

### Issue 4: Connection Manager Unclear
**Problem**: LabJackDetectionService mentions connection_manager
- Line 186: `self.connection_manager = get_connection_manager()`
- Line 2467: `if self.connection_manager:` (in cleanup)
- **But hardware_service has NO reference to connection_manager**

**Risk**: Unclear who actually manages connection lifecycle

---

## Next Steps

### Immediate Actions
1. Add debug logging to ALL ljm.close() calls to trace closure
2. Add logging to hardware_service.disconnect() with call stack
3. Monitor for automatic cleanup/timeout mechanisms

### Coordination Fixes Needed
1. Implement health_check_pause() method when sessions=0
2. Add notification from LabJackDetectionService to LabJackHardwareService
3. Define clear ownership: WHO controls connection lifecycle?
4. Add connection_manager to LabJackHardwareService

### Design Improvements
1. Consolidate to single connection service
2. Implement proper state machine: CONNECTED → IDLE → DISCONNECTED
3. Add event bus for service communication
4. Document ownership and lifecycle rules

---

## Files Analyzed

1. `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_service.py`
2. `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
3. `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`
4. `/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`

## Key Evidence Lines

- labjack_detection_service.py:154 - Dual service initialization
- labjack_detection_service.py:2471 - "Connection preserved" log
- labjack_hardware_service.py:759 - Health check read attempt
- labjack_hardware_service.py:777 - LJME_DEVICE_NOT_OPEN handler
- labjack_service.py:1722 - disconnect() with session protection

---

**Conclusion**: The "mystery" is partially solved. The architecture creates the POTENTIAL for the observed behavior (two services, no coordination), but we still need to identify the ACTUAL code path that closes the handle between session end and health check. The 8-second gap matches the health check timing (sleep 30s, interrupted at ~8s), but the root cause of closure remains to be discovered.
