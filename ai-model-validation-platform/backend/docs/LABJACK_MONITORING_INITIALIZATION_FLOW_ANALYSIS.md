# LabJack Monitoring Initialization Flow Analysis

## Complete Call Chain Trace

### Starting Point: POST /api/video-sequences/start

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/routers/video_sequence_testing.py`

---

## 1. API Endpoint Entry (Line 444-602)

```python
@router.post("/start", response_model=VideoSequenceStartResponse, status_code=201)
async def start_video_sequence(request: VideoSequenceStartRequest, db: Session)
```

### Step 1.1: Request Validation
**Location:** Lines 232-239

```python
class VideoSequenceStartRequest(CamelCaseModel):
    project_id: str
    video_ids: List[str]
    max_latency_ms: float = 300.0
    test_name: Optional[str] = None
    test_description: Optional[str] = None
    enable_labjack_monitoring: bool = Field(True, description="Enable LabjJack hardware monitoring")  # DEFAULT: TRUE
```

**Key Point:** `enable_labjack_monitoring` defaults to `True` - monitoring is opt-out, not opt-in.

---

### Step 1.2: Import Check (Lines 82-93)

```python
try:
    from services.dedicated_labjack_monitor import (
        start_hil_monitoring,
        stop_hil_monitoring,
        get_hil_session_events
    )
    HIL_MONITORING_AVAILABLE = True
    logger.info("✅ HIL monitoring available")
except ImportError as e:
    HIL_MONITORING_AVAILABLE = False
    logger.warning(f"⚠️ HIL monitoring not available: {e}")
```

**Critical Condition:** If import fails, `HIL_MONITORING_AVAILABLE = False` and monitoring never starts.

---

### Step 1.3: Database Session Creation (Lines 488-595)

**Flow:**
1. Create `TestSession` record (lines 494-513)
2. `db.flush()` + verify (lines 517-525)
3. Create `VideoTestSequence` record (lines 528-551)
4. Create `SequenceVideoResult` entries for each video (lines 557-591)
5. **CRITICAL:** `db.commit()` at line 594
6. `await asyncio.sleep(0.1)` delay at line 598 (ensures commit is visible)

---

### Step 1.4: Monitoring Condition Check (Line 602)

```python
if request.enable_labjack_monitoring and HIL_MONITORING_AVAILABLE:
```

**Two conditions must BOTH be true:**
1. `request.enable_labjack_monitoring == True` (default)
2. `HIL_MONITORING_AVAILABLE == True` (import succeeded)

**If either is False, monitoring is skipped entirely with NO error logged.**

---

### Step 1.5: Build Monitoring Configuration (Lines 604-617)

```python
first_video = videos[0]
video_timing_config = {
    'video_id': request.video_ids[0],
    'fps': first_video.fps or 24,
    'duration': cumulative_duration,  # Total sequence duration
    'voltage_threshold': 3.3,
    'debounce_ms': 0,
    'channels': ['AIN0'],
    'sample_rate': 20,
    'enable_websocket': True,
    'store_in_db': True
}
```

---

### Step 1.6: Call start_hil_monitoring (Lines 620-632)

```python
success = start_hil_monitoring(
    session_id=test_session_id,
    video_timing_config=video_timing_config
)

if success:
    labjack_monitoring_enabled = True
    logger.info(f"✅ LabjJack monitoring started for sequence {sequence_id}, session {test_session_id}")
else:
    logger.warning(f"⚠️ LabjJack monitoring failed to start for session {test_session_id}")
```

**Logs to check:**
- `"✅ LabjJack monitoring started"` = success
- `"⚠️ LabjJack monitoring failed to start"` = failure
- **NO LOG** = condition check failed (line 602)

---

## 2. start_hil_monitoring() Function

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`
**Location:** Lines 1911-1914

```python
def start_hil_monitoring(session_id: str, video_timing_config: Dict[str, Any]) -> bool:
    """Start HIL monitoring with video timing synchronization"""
    monitor = get_dedicated_labjack_monitor()
    return monitor.start_monitoring_with_video_sync(session_id, video_timing_config)
```

**Simple wrapper - delegates to monitor instance.**

---

## 3. start_monitoring_with_video_sync() Method

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`
**Location:** Lines 128-277

### Step 3.1: Initial Validation (Lines 143-152)

```python
logger.info(f"🚀 Starting monitoring for session {session_id}")
logger.debug(f"🔧 Video timing config: {video_timing_config}")

with self.lock:
    video_id = video_timing_config.get('video_id')
    if not video_id:
        logger.error(f"❌ Video ID required for session {session_id}")
        return False
```

**Early exit if video_id missing.**

---

### Step 3.2: Build LabJack Configuration (Lines 154-192)

```python
requested_sample_rate = video_timing_config.get('sample_rate')
sample_rate = max(requested_sample_rate or 1000, 240)

labjack_config = {
    'channels': video_timing_config.get('channels', ['AIN0']),
    'voltage_threshold': video_timing_config.get('voltage_threshold', 3.3),
    'debounce_ms': video_timing_config.get('debounce_ms', 0),
    'sample_rate': sample_rate,
    'store_in_db': True,
    'enable_websocket': video_timing_config.get('enable_websocket', True)
}
```

---

### Step 3.3: Initialize Session Entry (Lines 194-216)

```python
session_init_time = datetime.now(timezone.utc)
logger.info(f"📝 Initializing session {session_id} at {session_init_time}")

self.active_sessions[session_id] = {
    'video_timing_config': video_timing_config,
    'labjack_config': labjack_config,
    'started_at': session_init_time,
    'video_start_time': None,
    'detection_callback': None,
    'current_video': None,
    'video_history': [],
    'video_boundary_buffer': 0.5
}

logger.debug(f"✅ Session entry created: {list(self.active_sessions[session_id].keys())}")

detection_callback = lambda event: self._handle_detection_with_video_sync(session_id, event)
self.active_sessions[session_id]['detection_callback'] = detection_callback
```

---

### Step 3.4: Register Detection Callback (Line 219)

```python
self.labjack_monitor.add_detection_callback(detection_callback)
```

---

### Step 3.5: Start LabJack Monitoring (Lines 254-264)

```python
logger.info(f"🚀 STEP 1: Starting LabJack monitoring FIRST for session {session_id}")

success = self.labjack_monitor.start_monitoring(session_id, **labjack_config)

if not success:
    logger.error(f"❌ Failed to start LabJack monitoring for session {session_id}")
    return False

logger.info(f"✅ STEP 1 COMPLETE: LabJack monitoring active and ready to capture detections")
```

**This calls LabJackDetectionMonitor.start_monitoring()**

---

## 4. LabJackDetectionMonitor.start_monitoring()

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
**Location:** Lines 216-301

### Step 4.1: Session State Check (Lines 240-243)

```python
with self.lock:
    if session_id in self.active_sessions:
        logger.warning(f"Monitoring already active for session {session_id}")
        return True
```

---

### Step 4.2: Create Detection Configuration (Lines 256-270)

```python
config = DetectionConfig(
    session_id=session_id,
    channels=channels,
    voltage_threshold=voltage_threshold,
    debounce_ms=debounce_ms,
    sample_rate=sample_rate,
    enable_websocket=kwargs.get('enable_websocket', True),
    store_in_db=kwargs.get('store_in_db', True),
    metadata=metadata,
    continuous_mode=kwargs.get('continuous_mode', False),
    continuous_lower_bound=kwargs.get('continuous_lower_bound'),
    continuous_upper_bound=kwargs.get('continuous_upper_bound'),
    continuous_interval_ms=kwargs.get('continuous_interval_ms', 20)
)
```

---

### Step 4.3: Initialize Session State (Lines 272-278)

```python
self.active_sessions[session_id] = config
self.detection_status[session_id] = DetectionStatus.STARTING
self.detection_events[session_id] = []
self.last_detection_times[session_id] = {ch: datetime.min for ch in channels}
self.last_continuous_emit_times[session_id] = {ch: datetime.min for ch in channels}
self.stop_events[session_id] = threading.Event()
```

---

### Step 4.4: Start Monitoring Thread (Lines 288-296)

```python
monitor_thread = threading.Thread(
    target=self._monitoring_loop,
    args=(session_id,),
    daemon=True,
    name=f"LabJackMonitor-{session_id}"
)
self.monitoring_threads[session_id] = monitor_thread
monitor_thread.start()

logger.info(f"✅ Started detection monitoring for session {session_id}")
```

**Key Log:** `"✅ Started detection monitoring for session {session_id}"`

---

### Step 4.5: Return Success (Line 301)

```python
return True
```

---

## 5. _monitoring_loop() Thread

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
**Location:** Lines 452+

### Step 5.1: Status Update

```python
self.detection_status[session_id] = DetectionStatus.MONITORING
```

---

### Step 5.2: Polling Loop

```python
poll_interval = 1.0 / config.sample_rate

while not stop_event.is_set():
    try:
        # Read voltage from each channel
        for channel in config.channels:
            voltage = self._read_voltage_safe(channel)

            if voltage is not None:
                # Check threshold and emit detection events
                if voltage >= config.voltage_threshold:
                    # Create and emit detection event
                    self._emit_detection(session_id, channel, voltage, config)

    time.sleep(poll_interval)
```

---

### Step 5.3: Device Reading (_read_voltage_safe)

**This is where device connection matters:**

```python
def _read_voltage_safe(self, channel: str) -> Optional[float]:
    try:
        # Option 1: Use connection manager
        from services.labjack_connection_manager import get_connection_manager
        manager = get_connection_manager()
        return manager.read_voltage(channel)
    except:
        # Option 2: Direct read (fallback)
        return None
```

**If connection manager or device fails, returns None - NO voltage readings, NO detections.**

---

## Potential Failure Points for Session eecd7cff

### 1. Import Failure (Most Likely)

**Condition:** Line 82-93 in video_sequence_testing.py

```python
except ImportError as e:
    HIL_MONITORING_AVAILABLE = False
```

**Result:** Line 602 check fails silently, no monitoring started, NO LOGS.

**How to verify:**
```bash
grep "HIL monitoring available\|HIL monitoring not available" backend.log
```

---

### 2. Request Flag False (Unlikely)

**Condition:** Client sent `enable_labjack_monitoring: false`

**Result:** Line 602 check fails, no monitoring started, NO LOGS.

**How to verify:** Check frontend request payload.

---

### 3. LabJack Device Not Connected

**Condition:** Device not detected by connection manager

**Result:**
- Monitoring thread starts
- `_read_voltage_safe()` returns None repeatedly
- No detections captured
- **BUT** log shows `"✅ Started detection monitoring"`

**How to verify:**
```bash
grep "LabJack.*connection\|device not found" backend.log
```

---

### 4. Connection Manager Failure

**Condition:** Connection manager fails to connect to device

**Result:** Same as #3 - no voltage readings

**How to verify:**
```bash
grep "Connection manager.*failed\|read_voltage.*error" backend.log
```

---

## Diagnostic Commands for Session eecd7cff

### 1. Check if monitoring condition passed:
```bash
grep -A 5 "eecd7cff" backend.log | grep "LabjJack monitoring started\|LabjJack monitoring failed"
```

### 2. Check if start_hil_monitoring was called:
```bash
grep "Starting monitoring for session eecd7cff" backend.log
```

### 3. Check if monitoring thread started:
```bash
grep "Started detection monitoring for session eecd7cff" backend.log
```

### 4. Check for device connection issues:
```bash
grep "LabJack.*connection\|device.*not found" backend.log
```

### 5. Check HIL_MONITORING_AVAILABLE status:
```bash
grep "HIL monitoring available\|HIL monitoring not available" backend.log
```

---

## Expected Log Sequence for Successful Initialization

```
1. "✅ HIL monitoring available"                          (import success)
2. "✅ Test session {id} flushed and verified"          (database commit)
3. "🚀 Starting monitoring for session {session_id}"    (start_monitoring_with_video_sync entry)
4. "📝 Initializing session {session_id}"               (session entry creation)
5. "✅ Session entry created"                            (state initialization)
6. "✅ Detection callback registered"                    (callback setup)
7. "🚀 STEP 1: Starting LabJack monitoring FIRST"       (before device start)
8. "✅ Started detection monitoring for session"         (thread started)
9. "✅ STEP 1 COMPLETE: LabJack monitoring active"      (monitoring confirmed)
10. "✅ LabjJack monitoring started for sequence"        (final confirmation)
```

---

## Why Session eecd7cff Might Have No Logs

### Hypothesis 1: Condition Check Failed (Most Likely)

**Scenario:**
```python
if request.enable_labjack_monitoring and HIL_MONITORING_AVAILABLE:  # Line 602
    # This block never executed
```

**Evidence needed:**
- Log line 92: `"⚠️ HIL monitoring not available: {e}"` → import failed
- OR client sent `enable_labjack_monitoring: false`

**Result:** NO calls to start_hil_monitoring, NO logs about session eecd7cff in monitoring code.

---

### Hypothesis 2: Device Connection Failed Silently

**Scenario:**
- Monitoring thread started
- Connection manager couldn't connect to device
- `_read_voltage_safe()` returns None
- No detections, but thread is "running"

**Evidence needed:**
```bash
grep "Started detection monitoring for session eecd7cff" backend.log
```

If found: Device connection is the issue
If not found: Condition check is the issue

---

## Recommended Fix Strategy

### 1. Add Explicit Logging at Condition Check

**File:** `routers/video_sequence_testing.py`, line 602

```python
# BEFORE:
if request.enable_labjack_monitoring and HIL_MONITORING_AVAILABLE:

# AFTER:
logger.info(f"🔍 LabJack monitoring check: enable={request.enable_labjack_monitoring}, available={HIL_MONITORING_AVAILABLE}")
if request.enable_labjack_monitoring and HIL_MONITORING_AVAILABLE:
    logger.info(f"🚀 Proceeding with LabJack monitoring for session {test_session_id}")
else:
    logger.warning(f"⚠️ LabJack monitoring SKIPPED: enable={request.enable_labjack_monitoring}, available={HIL_MONITORING_AVAILABLE}")
```

---

### 2. Add Device Connection Verification

**File:** `services/labjack_detection_service.py`, line 258 (after config creation)

```python
# Verify device is actually connected before starting thread
from services.labjack_connection_manager import get_connection_manager
manager = get_connection_manager()
if not manager.is_connected():
    logger.error(f"❌ LabJack device not connected - cannot start monitoring for {session_id}")
    return False

logger.info(f"✅ LabJack device connected and ready for session {session_id}")
```

---

### 3. Add Heartbeat Logging in Monitoring Loop

**File:** `services/labjack_detection_service.py`, in `_monitoring_loop`

```python
# After starting monitoring
heartbeat_counter = 0
while not stop_event.is_set():
    heartbeat_counter += 1
    if heartbeat_counter % 100 == 0:  # Log every 100 iterations
        logger.debug(f"💓 Monitoring heartbeat {session_id}: {heartbeat_counter} iterations")
```

---

## Summary: Why No start_hil_monitoring Logs for Session eecd7cff

**Root Cause:** The condition check at line 602 likely failed:

```python
if request.enable_labjack_monitoring and HIL_MONITORING_AVAILABLE:
```

**Most Probable Reason:**
1. `HIL_MONITORING_AVAILABLE = False` due to import failure
2. OR client sent `enable_labjack_monitoring: false`

**Evidence:**
- NO logs showing `"🚀 Starting monitoring for session eecd7cff"`
- Indicates start_hil_monitoring() was NEVER CALLED
- This happens BEFORE any monitoring code executes

**Next Steps:**
1. Check backend.log for line: `"⚠️ HIL monitoring not available"`
2. Check client request payload for `enableLabjackMonitoring` field
3. Add explicit logging at condition check (recommended fix #1 above)

---

## File References

| File | Lines | Purpose |
|------|-------|---------|
| `routers/video_sequence_testing.py` | 82-93 | Import check & HIL_MONITORING_AVAILABLE |
| `routers/video_sequence_testing.py` | 232-239 | Request schema with enable_labjack_monitoring |
| `routers/video_sequence_testing.py` | 602-632 | Monitoring condition check & start call |
| `services/dedicated_labjack_monitor.py` | 1911-1914 | start_hil_monitoring wrapper |
| `services/dedicated_labjack_monitor.py` | 128-277 | start_monitoring_with_video_sync implementation |
| `services/labjack_detection_service.py` | 216-301 | LabJackDetectionMonitor.start_monitoring |
| `services/labjack_detection_service.py` | 452+ | _monitoring_loop thread |
| `services/labjack_connection_manager.py` | 127-147 | Device connection logic |

---

**Generated:** 2025-11-14
**Purpose:** Root cause analysis for session eecd7cff missing LabJack monitoring initialization
