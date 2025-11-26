# Zero Detections Root Cause Analysis - Duplicate Execution Paths

## Executive Summary

**Issue**: 0 out of 242 expected detections captured during HIL test execution (Session: 438b5071-ba9e-4926-b132-b4077653daaf)

**Root Cause**: Multiple conflicting detection monitoring systems running simultaneously, causing detection flow disruption

**Status**: ✅ Diagnosed - Duplicate monitoring initialization and WebSocket emission path conflicts identified

---

## Problem Statement

From user-provided browser console logs:
- **Expected**: 242 detections (121 ground truth events × 2 videos)
- **Actual**: 0 detections captured
- **Frontend Status**: "Connected" (WebSocket connection established)
- **Backend LabJack Status**: Connected → Disconnected during test

Console log snippet:
```
✅ [HIL] WebSocket connected - polling NOT needed
⚠️ [HIL WebSocket] Detection missing timestamp, skipping:
    {type: 'connection_established', session_id: '438b5071...', timestamp: '2025-11-17T17:10:32...'}
```

---

## Detected Duplication Issues

### 1. **Duplicate WebSocket Emission Path Registration** ⚠️

**Location 1**: `main.py:238-242`
```python
# Initial registration during app startup
from socketio_server import emit_detection_event
from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor

monitor = get_dedicated_labjack_monitor(websocket_emit_fn=emit_detection_event)
logger.info("✅ WebSocket real-time detection broadcasting enabled")
```

**Location 2**: `main.py:4075-4147` - WebSocket endpoint
```python
@app.websocket("/ws/test-sessions/{session_id}/detections")
async def websocket_test_session_detections(websocket: WebSocket, session_id: str):
    # ...
    async def send_detection_to_client(detection_data: dict, event_session_id: str):
        # Session-specific callback
        if event_session_id == session_id:
            await websocket.send_json({"type": "detection_event", "data": detection_data})

    # ❌ OVERWRITES the global emit function registered in main.py:241
    if detection_monitor and hasattr(detection_monitor, 'set_websocket_emit_function'):
        detection_monitor.set_websocket_emit_function(send_detection_to_client)
        callback_registered = True
```

**Impact**: The WebSocket endpoint **REPLACES** the broadcast emission function with a session-specific callback, breaking detection flow for:
- Global detection broadcasting
- Multiple simultaneous sessions
- Detection persistence pipeline

---

### 2. **Duplicate Detection Monitoring Systems** ⚠️⚠️

**System 1**: HIL Dedicated Monitor
- **File**: `services/dedicated_labjack_monitor.py`
- **Method**: `start_monitoring_with_video_sync()`
- **Purpose**: Video-synchronized HIL detection with timing analysis

**System 2**: Basic Detection Service
- **File**: `services/raw_labjack_integration.py:177`
- **Method**: `detection_service.start_monitoring()`
- **Purpose**: Standard detection monitoring

**Evidence from raw_labjack_integration.py:158-182**:
```python
# Line 162: Start HIL monitoring
hil_success = await self.dedicated_monitor.start_monitoring_with_video_sync(
    test_session_id, video_timing_config
)

# Line 177: ALSO start basic detection monitoring
detection_success = self.detection_service.start_monitoring(
    test_session_id,
    channels=channels,
    voltage_threshold=self.config.detection_threshold_volts,
    debounce_ms=self.config.debounce_time_ms,
    sample_rate=10
)
```

**Impact**: Two monitoring systems compete for:
- LabJack device access
- Detection event emission
- Database writes
- WebSocket broadcasts

---

### 3. **Multiple LabJack Monitor Instantiation** ⚠️

**Pattern**: `get_dedicated_labjack_monitor()` called in multiple locations:

1. **main.py:241** - App initialization with websocket_emit_fn
2. **socketio_server.py:976** - Cache invalidation (video_started event)
3. **socketio_server.py:1128** - Cache invalidation (video_ended event)
4. **main.py:4090** - WebSocket endpoint via `get_detection_service()`

**Note**: Calls at socketio_server.py lines 976 and 1128 are for cache invalidation only (`invalidate_sequence_cache()`), not starting monitoring. However, the multiple instantiation pattern indicates poor singleton management.

---

## Detection Flow Breakdown

### Expected Flow (Correct)
```
LabJack Hardware
    ↓ Voltage Reading
DedicatedLabJackMonitor
    ↓ Detection Event
emit_detection_event() [socketio_server.py]
    ↓ WebSocket Broadcast
Frontend Client
```

### Actual Flow (Broken)
```
LabJack Hardware
    ↓
[CONFLICT] Multiple monitors reading simultaneously:
    - DedicatedLabJackMonitor (HIL)
    - DetectionService (Basic)
    ↓
[CONFLICT] Emission function overwritten:
    - Initial: emit_detection_event (broadcast)
    - Replaced: send_detection_to_client (session-specific)
    ↓
❌ Detections not reaching frontend
❌ "Detection missing timestamp" warnings
❌ 0 detections captured
```

---

## Evidence from Console Logs

### 1. WebSocket Connection Established ✅
```
HILTestExecutionPRD.tsx:1333 ✅ [HIL] WebSocket connected - polling NOT needed
```
**Analysis**: Connection WAS successful, ruling out device exclusivity as the primary issue

### 2. Detection Skipped Due to Missing Timestamp ❌
```
HILTestExecutionPRD.tsx:1350 ⚠️ [HIL WebSocket] Detection missing timestamp, skipping:
    {type: 'connection_established', session_id: '438b5071...', timestamp: '2025-11-17T17:10:32...'}
```
**Analysis**: Frontend received a message but rejected it because:
- Message type was 'connection_established' instead of 'detection_event'
- Detection validation logic expected different message format

### 3. LabJack Status Changes
```
✅ [HIL] Detection stream initialized
✅ [HIL] WebSocket connected
⏹️ [HIL] Dedicated LabJack monitor session stopped
```
**Analysis**: LabJack monitoring started and stopped properly, but NO detection events flowed through

---

## Resolution Strategy

### Immediate Fixes Required

#### 1. **Remove Duplicate Detection Monitoring**
**File**: `services/raw_labjack_integration.py`

**Problem Lines 177-182**:
```python
# ❌ DELETE THIS - Creates duplicate monitoring
detection_success = self.detection_service.start_monitoring(
    test_session_id,
    channels=channels,
    voltage_threshold=self.config.detection_threshold_volts,
    debounce_ms=self.config.debounce_time_ms,
    sample_rate=10
)
```

**Reason**: HIL monitoring via `start_monitoring_with_video_sync()` already handles detection capture. The basic detection service creates a conflicting parallel system.

#### 2. **Fix WebSocket Emission Path Overwrite**
**File**: `main.py:4110-4112`

**Current Code** (BREAKS broadcasting):
```python
# ❌ This OVERWRITES the global broadcast function
if detection_monitor and hasattr(detection_monitor, 'set_websocket_emit_function'):
    detection_monitor.set_websocket_emit_function(send_detection_to_client)
```

**Solution**: Use Socket.IO room-based broadcasting instead of replacing emit function
```python
# ✅ Let the global broadcast function handle it via Socket.IO rooms
# Remove the set_websocket_emit_function() call
# Socket.IO will handle session-specific delivery via rooms
```

**Reason**: Overwriting the emit function:
- Breaks global broadcasting to all connected clients
- Prevents detection persistence pipeline
- Causes session isolation issues
- Creates race conditions when multiple sessions connect

#### 3. **Enforce Singleton Pattern for LabJack Monitor**
**Files**: `services/dedicated_labjack_monitor.py`

**Current**: Multiple calls to `get_dedicated_labjack_monitor()` without guaranteed singleton

**Solution**: Implement proper singleton with thread-safety:
```python
_monitor_instance = None
_monitor_lock = threading.Lock()

def get_dedicated_labjack_monitor(websocket_emit_fn=None):
    global _monitor_instance
    with _monitor_lock:
        if _monitor_instance is None:
            _monitor_instance = DedicatedLabJackMonitor(websocket_emit_fn)
        elif websocket_emit_fn is not None:
            # Only allow setting emit function once during initialization
            raise RuntimeError("Cannot modify websocket_emit_fn after initialization")
        return _monitor_instance
```

---

## Testing Recommendations

### 1. Unit Test: Detection Flow
- Verify only ONE monitoring system starts per session
- Confirm WebSocket emission function not overwritten
- Validate detection events reach frontend

### 2. Integration Test: Multi-Session
- Start 2 simultaneous HIL sessions
- Verify each session receives only its own detections
- Confirm no detection cross-contamination

### 3. End-to-End Test: Full HIL Workflow
- Run complete 2-video sequence test
- Capture all console logs
- Verify 242/242 detections captured
- Check timing synchronization accuracy

---

## File References

### Key Files Involved
1. **main.py**
   - Line 238-244: Initial monitor setup with emit function
   - Line 4075-4147: WebSocket endpoint with emission override

2. **socketio_server.py**
   - Line 522: `emit_detection_event()` function definition
   - Line 851-1027: `video_started` event handler
   - Line 1029-1160: `video_ended` event handler
   - Line 975-976, 1127-1128: Cache invalidation calls

3. **services/dedicated_labjack_monitor.py**
   - Primary HIL monitoring implementation
   - `start_monitoring_with_video_sync()` method

4. **services/raw_labjack_integration.py**
   - Line 162-182: Duplicate monitoring system startup
   - Creates conflict with dedicated HIL monitor

5. **services/hybrid_session_manager.py**
   - Line 371: Calls `start_monitoring_with_video_sync()`
   - Orchestrates hybrid logging setup

---

## Conclusion

The zero detection issue is caused by **architectural conflicts** from duplicate monitoring systems and WebSocket emission path overwrites, NOT device exclusivity. The frontend showing "connected" confirms the backend received connections successfully.

**Primary Culprits**:
1. ✅ Duplicate detection monitoring (HIL + Basic systems running simultaneously)
2. ✅ WebSocket emission function overwrite breaking broadcast
3. ⚠️ Weak singleton pattern allowing multiple monitor instances

**User's Diagnosis**: ✅ CORRECT - "duplication within python main.py calling and running twice"

---

**Analysis Date**: 2025-11-17
**Session ID**: 438b5071-ba9e-4926-b132-b4077653daaf
**Sequence ID**: c1f5cc12-1819-4945-907c-d48708cfb001
**Test Videos**: 2
**Expected Detections**: 242 (121 per video)
**Actual Detections**: 0
**Status**: 🔍 Root cause identified, fixes documented
