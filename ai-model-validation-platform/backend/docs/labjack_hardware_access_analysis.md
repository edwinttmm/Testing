# LabJack Hardware Access Analysis Report
**Date**: 2025-11-17
**Analyst**: Code Analyzer Agent
**Focus**: Hardware resource sharing and code duplication analysis

## Executive Summary

Both `dedicated_labjack_monitor.py` and `labjack_detection_service.py` **share the same underlying hardware access layer** through `labjack_service.py`. They do **NOT** implement independent hardware access logic. However, they can potentially create **resource conflicts** by accessing the same LabJack device handle simultaneously.

---

## 1. Hardware Access Architecture

### 1.1 Shared Core Service: `labjack_service.py`

**Purpose**: Single source of truth for LabJack hardware communication
**Location**: `/services/labjack_service.py`
**Lines of Code**: 1,818 lines

#### Key Responsibilities:
- **Direct Hardware Access**: Manages `self.direct_handle` - the exclusive device handle
- **LJM Library Calls**: All `ljm.eReadName()`, `ljm.eStreamRead()`, `ljm.eStreamStart()` calls
- **Connection Management**: Handles device open/close, reconnection, health monitoring
- **Stream Mode Operations**: Provides hardware-timed data acquisition at 200+ Hz
- **Singleton Pattern**: `get_labjack_service()` returns global instance

#### Hardware Handle Management:
```python
# Lines 412, 648, 662
self.direct_handle = None  # Initialized as None
self.direct_handle = ljm.openS("T7", "USB", "ANY")  # Device connection
info = ljm.getHandleInfo(self.direct_handle)  # Device info retrieval
```

#### Critical Hardware Methods:
| Method | Line | Purpose | Resource Usage |
|--------|------|---------|----------------|
| `read_single_voltage()` | 1148 | Single voltage read | `ljm.eReadName()` - blocking |
| `start_stream_mode()` | 1280 | Start hardware streaming | `ljm.eStreamStart()` - exclusive |
| `read_stream_mode()` | 1361 | Read stream buffer | `ljm.eStreamRead()` - blocking |
| `stop_stream_mode()` | 1418 | Stop hardware streaming | `ljm.eStreamStop()` - exclusive |

---

## 2. Service Layer Analysis

### 2.1 Dedicated LabJack Monitor (`dedicated_labjack_monitor.py`)

**Lines of Code**: ~2,500+ lines (file was too large to read completely)
**Purpose**: High-level HIL test orchestration with video timing synchronization

#### Hardware Access Pattern:
```python
# Line 40: Import shared service
from services.labjack_service import get_labjack_service, ConnectionStatus

# Line 353: Get singleton instance
labjack_service = get_labjack_service()

# Line 356-367: Hardware validation and connection
if labjack_service.status != ConnectionStatus.CONNECTED:
    connected = await labjack_service.connect()
hardware_valid = await labjack_service.validate_hardware_connection()
```

#### Key Operations:
1. **Session Management**: Registers sessions with `labjack_service`
2. **Delegates Hardware Access**: Calls `labjack_monitor.start_monitoring()`
3. **Video Timing Sync**: Coordinates LabJack timestamps with video playback
4. **No Direct Hardware Calls**: Uses `labjack_detection_service` as intermediary

---

### 2.2 LabJack Detection Service (`labjack_detection_service.py`)

**Lines of Code**: ~2,700+ lines
**Purpose**: Real-time detection event monitoring with threshold-based triggering

#### Hardware Access Pattern:
```python
# Line 64: Import shared service
from services.labjack_service import get_labjack_service, LabJackService

# Line 153: Initialize with singleton
self.labjack_service = labjack_service or get_labjack_service()

# Line 787-793: Stream mode hardware access
success, actual_rate = self.labjack_service.start_stream_mode(
    channels=channels,
    scan_rate=sample_rate,
    scans_per_read=scans_per_read
)

# Line 847-851: Read hardware stream data
data, backlog, success = self.labjack_service.read_stream_mode()
```

#### Key Operations:
1. **Threshold Detection**: Monitors voltage levels for event triggers
2. **Stream Mode Management**: Uses `labjack_service.start_stream_mode()`
3. **Batch Processing**: Accumulates detection events for database commits
4. **WebSocket Notifications**: Emits real-time detection events

---

## 3. Hardware Resource Management

### 3.1 Shared Device Handle

**CRITICAL FINDING**: Both services access the **SAME** hardware handle:

```python
# labjack_service.py - Line 412
self.direct_handle = None  # Single device handle for entire application

# Accessed by labjack_detection_service.py via:
self.labjack_service.start_stream_mode()  # Exclusive access required
self.labjack_service.read_stream_mode()   # Requires stream to be active

# Accessed by dedicated_labjack_monitor.py via:
labjack_service.validate_hardware_connection()  # May conflict with streaming
labjack_service.connect()                        # Reconnects device handle
```

---

### 3.2 Resource Conflict Scenarios

#### Scenario A: Simultaneous Streaming
```python
# Thread 1 (detection_service)
self.labjack_service.start_stream_mode()  # Starts hardware stream
self.labjack_service.read_stream_mode()   # Reads stream buffer

# Thread 2 (dedicated_monitor)
labjack_service.read_single_voltage()     # ❌ CONFLICT: Stream mode active
```

**Result**: `read_single_voltage()` may fail or return invalid data while stream is active.

---

#### Scenario B: Connection State Management
```python
# Thread 1 (detection_service monitoring loop)
data, backlog, success = self.labjack_service.read_stream_mode()

# Thread 2 (dedicated_monitor health check)
hardware_valid = await labjack_service.validate_hardware_connection()
# Calls: ljm.eReadName(self.direct_handle, "TEMPERATURE_DEVICE_K")

# ❌ POTENTIAL CONFLICT: Both threads access device handle simultaneously
```

**Result**: Race condition on device handle access - LJM library may not be thread-safe.

---

#### Scenario C: Premature Disconnection
```python
# Session 1 (dedicated_monitor)
labjack_service.start_session(session_id)  # Registers session

# Session 2 (detection_service)
# Assumes connection is valid, but session 1 ends:
labjack_service.end_session(session_id)
# If last session, may trigger disconnect()

# ❌ RISK: Session 2 loses hardware connection unexpectedly
```

**Result**: DEVICE_NOT_OPEN errors (LJM Error 1224).

---

### 3.3 Mitigation Mechanisms

#### Existing Protections:
1. **Session Tracking** (Lines 1664-1720 in `labjack_service.py`):
   ```python
   self.active_sessions = set()
   self.active_session_count = 0

   def start_session(self, session_id: str) -> bool:
       self.active_sessions.add(session_id)
       self.active_session_count += 1
       logger.info(f"Connection preserved for active session")
   ```

2. **Connection Lock** (Lines 1721-1778):
   ```python
   async def disconnect(self, force: bool = False):
       active_count = getattr(self, 'active_session_count', 0)
       if active_count > 0 and not force:
           logger.error(f"❌ DISCONNECT BLOCKED: {active_count} sessions still active")
           return False
   ```

3. **Thread Safety** (Line 171 in `labjack_detection_service.py`):
   ```python
   self.lock = threading.RLock()  # Reentrant lock for thread safety
   ```

#### Missing Protections:
- **No Mutex on Hardware Handle**: `self.direct_handle` accessed without exclusive lock
- **No Stream Mode Flag Check**: Services don't verify if stream is active before reading
- **No Connection Manager**: Multiple services can call `connect()` independently

---

## 4. Dependency Analysis

### 4.1 Dependency Tree

```
dedicated_labjack_monitor.py
├── services.labjack_service (get_labjack_service)
├── services.labjack_detection_service (get_detection_service)
│   └── services.labjack_service (get_labjack_service)  ← SAME INSTANCE
└── services.video_timing_service (video sync)

labjack_detection_service.py
├── services.labjack_service (get_labjack_service)  ← SHARED SINGLETON
└── services.labjack_hardware_service (additional hardware features)
```

**Key Finding**: Both services use `get_labjack_service()` which returns the **SAME GLOBAL INSTANCE**.

---

### 4.2 Shared Utilities

#### `ljm_helpers.py` (106 lines)
- **Purpose**: Compatibility layer for LJM library version differences
- **Shared By**: `labjack_service.py`, `real_labjack_service.py`
- **Functions**:
  - `numberToType()` - Device type conversion
  - `numberToConnectionType()` - Connection type conversion
  - `numberToIP()` - IP address formatting

**Usage in `labjack_service.py`**:
```python
# Line 73-77
from services.ljm_helpers import (
    numberToType,
    numberToDeviceType,
    numberToConnectionType,
    numberToIP
)
```

#### No Duplicate Detection Logic
- **Threshold detection**: Implemented ONLY in `labjack_detection_service.py` (Lines 90-142)
- **Debounce logic**: Implemented ONLY in `labjack_detection_service.py` (monitoring loops)
- **Video timing sync**: Implemented ONLY in `dedicated_labjack_monitor.py` (Lines 54-77)

---

## 5. Hardware Resource Conflict Analysis

### 5.1 Can Both Services Access LabJack Simultaneously?

**Answer**: ⚠️ **YES, but with caveats**

#### Simultaneous Access Scenarios:

| Scenario | Service A | Service B | Result | Risk Level |
|----------|-----------|-----------|--------|------------|
| 1 | Stream mode active | Single voltage read | ❌ Conflict | **HIGH** |
| 2 | Single voltage reads | Single voltage reads | ✅ OK (sequential) | **LOW** |
| 3 | Stream mode reading | Health check read | ⚠️ Race condition | **MEDIUM** |
| 4 | Stream starting | Connection validation | ❌ Handle conflict | **HIGH** |
| 5 | Monitoring session 1 | Monitoring session 2 | ✅ OK (same handle) | **LOW** |

---

### 5.2 Resource Locking/Sharing Analysis

#### Current State:
```python
# labjack_service.py - Line 171
self.lock = threading.RLock()  # Used for connection state

# labjack_detection_service.py - Line 198
self.lock = threading.RLock()  # Used for detection state

# ❌ NO LOCK ON HARDWARE HANDLE ACCESS
# ljm.eReadName(self.direct_handle, channel)  # Not protected by mutex
```

**Finding**: Locks protect **service state**, but not **hardware handle access**.

---

### 5.3 What Happens If Both Try to Read Simultaneously?

#### Test Case: Concurrent Stream and Single Read
```python
# Thread 1: labjack_detection_service monitoring loop
while monitoring:
    data, backlog, success = self.labjack_service.read_stream_mode()
    # Calls: ljm.eStreamRead(self.direct_handle)

# Thread 2: dedicated_monitor health check
voltage = await labjack_service.read_single_voltage("AIN0")
# Calls: ljm.eReadName(self.direct_handle, "AIN0")
```

**Potential Outcomes**:
1. ✅ **Sequential Success**: LJM library internally serializes access (undocumented)
2. ❌ **LJM Error 1239**: `STREAM_NOT_INITIALIZED` - stream state corrupted
3. ❌ **LJM Error 1224**: `DEVICE_NOT_OPEN` - handle invalidated
4. ❌ **Segmentation Fault**: LJM library crash (worst case)

**Observed Behavior**: Based on logs in codebase, error 1224 has been encountered frequently.

---

## 6. Shared vs Unique Code

### 6.1 Shared Code (No Duplication)

| Component | Location | Shared By | Purpose |
|-----------|----------|-----------|---------|
| Hardware access | `labjack_service.py` | All services | LJM API calls |
| Type conversions | `ljm_helpers.py` | All services | Compatibility |
| Connection management | `labjack_service.py` | All services | Device lifecycle |
| Stream mode | `labjack_service.py` | All services | High-speed acquisition |

---

### 6.2 Unique Code (Service-Specific)

| Component | Location | Purpose |
|-----------|----------|---------|
| Threshold detection | `labjack_detection_service.py` | Event triggering |
| Debounce logic | `labjack_detection_service.py` | Duplicate prevention |
| Video timing sync | `dedicated_labjack_monitor.py` | Ground truth matching |
| Session orchestration | `dedicated_labjack_monitor.py` | HIL test coordination |
| Database storage | `labjack_detection_service.py` | Event persistence |
| WebSocket emission | `labjack_detection_service.py` | Real-time updates |

---

## 7. Recommendations

### 7.1 Critical: Implement Hardware Access Mutex

**Problem**: No exclusive locking on `self.direct_handle` access.

**Solution**:
```python
# In labjack_service.py
class LabJackService:
    def __init__(self):
        self.hardware_lock = threading.Lock()  # NEW: Hardware access mutex

    async def read_single_voltage(self, channel: str) -> float:
        with self.hardware_lock:  # CRITICAL: Protect hardware access
            if self.mode == ConnectionMode.DIRECT and self.direct_handle:
                try:
                    return ljm.eReadName(self.direct_handle, channel)
                except Exception as e:
                    self.handle_ljm_error(e, f"voltage read from {channel}")
```

**Impact**: Prevents race conditions on device handle.

---

### 7.2 High Priority: Stream Mode Guard

**Problem**: Services don't check if stream mode is active before single reads.

**Solution**:
```python
async def read_single_voltage(self, channel: str) -> float:
    if self._stream_active:
        logger.error("Cannot read single voltage while stream mode is active")
        return 0.0

    with self.hardware_lock:
        # ... existing code
```

---

### 7.3 Medium Priority: Connection Manager Pattern

**Problem**: Multiple services can independently call `connect()` and `disconnect()`.

**Solution**:
```python
# New file: labjack_connection_manager.py
class LabJackConnectionManager:
    """Centralized connection lifecycle management"""
    def __init__(self):
        self.connection_lock = threading.Lock()
        self.active_users = {}  # service_id -> reference count

    def acquire_connection(self, service_id: str) -> LabJackService:
        with self.connection_lock:
            if service_id not in self.active_users:
                self.active_users[service_id] = 1
            else:
                self.active_users[service_id] += 1
            return get_labjack_service()

    def release_connection(self, service_id: str):
        with self.connection_lock:
            if service_id in self.active_users:
                self.active_users[service_id] -= 1
                if self.active_users[service_id] == 0:
                    del self.active_users[service_id]
```

---

### 7.4 Low Priority: Extract Common Detection Utilities

**Current State**: No code duplication detected.
**Action**: None required - code is well-factored.

---

## 8. Conclusion

### Summary of Findings:

1. ✅ **No Code Duplication**: Both services properly share `labjack_service.py`
2. ⚠️ **Resource Conflict Risk**: Simultaneous hardware access not properly protected
3. ✅ **Session Management**: Good session tracking prevents premature disconnection
4. ❌ **Missing Hardware Mutex**: Device handle access lacks exclusive locking
5. ❌ **Stream Mode Guard**: No check prevents conflicting read operations

### Risk Assessment:

| Risk | Severity | Likelihood | Mitigation Effort |
|------|----------|------------|-------------------|
| Race condition on handle | **HIGH** | Medium | Low (add mutex) |
| Stream/single read conflict | **HIGH** | High | Low (add guard) |
| Premature disconnection | **MEDIUM** | Low | None (already mitigated) |
| LJM library crash | **CRITICAL** | Low | Medium (connection manager) |

### Implementation Priority:

1. **Immediate**: Add hardware access mutex (Recommendation 7.1)
2. **This Sprint**: Implement stream mode guard (Recommendation 7.2)
3. **Next Sprint**: Design connection manager pattern (Recommendation 7.3)
4. **Backlog**: Monitor for additional race conditions

---

## Appendix A: Hardware Access Call Map

### Direct Hardware Calls in `labjack_service.py`:

| Line | Method | Call | Resource | Thread-Safe? |
|------|--------|------|----------|--------------|
| 648 | `_connect_direct()` | `ljm.openS()` | Device open | ❌ No lock |
| 662 | `_connect_direct()` | `ljm.getHandleInfo()` | Device info | ❌ No lock |
| 947 | `configure_stream()` | `ljm.eStreamStart()` | Stream start | ❌ No lock |
| 1042 | `_direct_stream_loop()` | `ljm.eStreamRead()` | Stream read | ⚠️ Loop only |
| 1095 | `stop_stream()` | `ljm.eStreamStop()` | Stream stop | ❌ No lock |
| 1176 | `read_single_voltage()` | `ljm.eReadName()` | Single read | ❌ No lock |
| 1253 | `validate_hardware_connection()` | `ljm.eReadName()` | Health check | ❌ No lock |
| 1338 | `start_stream_mode()` | `ljm.eStreamStart()` | Stream start | ❌ No lock |
| 1393 | `read_stream_mode()` | `ljm.eStreamRead()` | Stream read | ❌ No lock |
| 1443 | `stop_stream_mode()` | `ljm.eStreamStop()` | Stream stop | ❌ No lock |
| 1572 | `_health_monitor_loop()` | `ljm.eReadName()` | Health check | ⚠️ Loop only |
| 1754 | `disconnect()` | `ljm.close()` | Device close | ⚠️ Partial lock |

**Total Direct Hardware Calls**: 12 unique call sites
**Thread-Safe Calls**: 0
**Partially Protected Calls**: 3 (loop-based serialization)

---

## Appendix B: Service Interaction Diagram

```
┌─────────────────────────────────────────┐
│  dedicated_labjack_monitor.py          │
│  (HIL Test Orchestration)               │
└──────────────┬──────────────────────────┘
               │ delegates to
               ▼
┌─────────────────────────────────────────┐
│  labjack_detection_service.py          │
│  (Detection Event Monitoring)           │
└──────────────┬──────────────────────────┘
               │ uses
               ▼
┌─────────────────────────────────────────┐
│  labjack_service.py (SINGLETON)        │
│  ┌───────────────────────────────────┐ │
│  │  self.direct_handle (SHARED)      │ │ ⚠️ NO MUTEX PROTECTION
│  └───────────────────────────────────┘ │
│  ├─ ljm.eReadName()                   │
│  ├─ ljm.eStreamStart()                │
│  ├─ ljm.eStreamRead()                 │
│  └─ ljm.eStreamStop()                 │
└──────────────┬──────────────────────────┘
               │ calls
               ▼
┌─────────────────────────────────────────┐
│  LabJack LJM Library (C/C++)           │
│  (Hardware Driver)                      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  LabJack T7 Hardware                    │
│  (USB/Ethernet Device)                  │
└─────────────────────────────────────────┘
```

---

**Report End**
