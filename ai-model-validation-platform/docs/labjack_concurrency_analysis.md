# LabJack Concurrency Analysis Report
## Hardware Resource Conflict Investigation

**Date:** 2025-11-25
**Issue:** Concurrent test sessions competing for exclusive LabJack access
**Files Analyzed:**
- `/backend/services/labjack_connection_manager.py`
- `/backend/services/dedicated_labjack_monitor.py`
- `/backend/services/labjack_detection_service.py`

---

## Executive Summary

The platform implements a **singleton connection manager** to share a single LabJack hardware handle across multiple test sessions. While this prevents the `LJME_DEVICE_CURRENTLY_CLAIMED_BY_ANOTHER_PROCESS` error, **the current implementation has critical concurrency issues** that cause hardware validation failures when multiple sessions run simultaneously.

### Critical Findings

1. ✅ **Singleton Pattern Implemented** - But not consistently used
2. ⚠️ **Lock Granularity Issues** - RLock used but monitoring loops bypass it
3. ❌ **No Session-Level Access Control** - Multiple threads read simultaneously
4. ❌ **Race Conditions in Monitoring Loops** - Uncoordinated hardware access
5. ⚠️ **Timing Synchronization Conflicts** - video_start_time null errors

---

## Architecture Analysis

### 1. Connection Management Design

#### Current Implementation (LabJackConnectionManager)

```python
class LabJackConnectionManager:
    """Singleton connection manager for LabJack devices"""

    _instance = None
    _lock = threading.Lock()  # Class-level lock for singleton

    def __init__(self):
        self._handle: Optional[int] = None  # SINGLE shared handle
        self._connection_lock = threading.RLock()  # Instance-level lock
        self._device_info: Optional[DeviceInfo] = None
        self._connection_state = ConnectionState.DISCONNECTED
```

**Design Intent:**
- Single hardware connection shared across all services
- Thread-safe access through `_connection_lock` (RLock)
- Prevents multiple processes from claiming the device

**Implementation Status:**
```python
# Line 269-278: Thread-safe read operation
def read_voltage(self, channel: str) -> Optional[float]:
    with self._connection_lock:  # ✅ Lock acquired
        if not self.is_connected():
            return None
        try:
            voltage = ljm.eReadName(self._handle, channel)
            return voltage
        except Exception as e:
            logger.error(f"Failed to read voltage: {e}")
            return None
```

---

### 2. Session Management Architecture

#### Multiple Sessions Share Single Hardware Handle

```python
# LabJackDetectionMonitor (labjack_detection_service.py)
class LabJackDetectionMonitor:
    def __init__(self):
        # Lines 174-176: Session tracking
        self.active_sessions: Dict[str, DetectionConfig] = {}
        self.monitoring_threads: Dict[str, threading.Thread] = {}
        self.detection_events: Dict[str, List[DetectionEvent]] = {}

        # Lines 199-203: Shared connection manager
        from services.labjack_connection_manager import get_connection_manager
        self.connection_manager = get_connection_manager()  # ✅ Singleton
```

**Session Lifecycle:**
1. `start_monitoring(session_id)` → Creates monitoring thread
2. Thread runs `_monitoring_loop(session_id)` → Polls hardware continuously
3. `stop_session_monitoring(session_id)` → Stops thread, preserves connection

---

## Concurrency Issues Identified

### Issue 1: Uncoordinated Monitoring Loops (CRITICAL)

**Location:** `labjack_detection_service.py:888-999`

**Problem:**
```python
# Line 888: Each session has its own monitoring thread
while not stop_event.is_set():
    # Line 976-999: Direct hardware reads
    for channel in config.channels:
        # Line 980-990: RACE CONDITION
        if self.connection_manager:
            if not self.connection_manager.is_connected():
                self.connection_manager.connect()  # ❌ Multiple threads may connect

            voltage = self.connection_manager.read_voltage(channel)  # ⚠️ Concurrent reads
```

**Race Condition Sequence:**
```
Thread A (Session 1):  Check connected → Read AIN0 → Read AIN1
Thread B (Session 2):                  Check connected → Read AIN0 → Read AIN1
                       ↑                                 ↑
                       └─────── Hardware Conflict ──────┘
```

**Impact:**
- **Interleaved Reads:** Thread A reads AIN0, Thread B reads AIN0, Thread A reads AIN1
- **Timing Skew:** Voltage readings from different points in time
- **Data Corruption:** Mixed samples from different detection events

---

### Issue 2: Connection State Synchronization

**Location:** `labjack_connection_manager.py:264-267`

**Problem:**
```python
def is_connected(self) -> bool:
    """Check if device is connected"""
    return (self._connection_state == ConnectionState.CONNECTED and
            self._handle is not None)
```

**Race Condition:**
```
Thread A: is_connected() → True
Thread B: is_connected() → True
Thread A: read_voltage("AIN0")
Thread B: disconnect() → _handle = None  # ❌ Thread A's read fails
Thread A: [ERROR] Handle no longer valid
```

**Observed Error:**
```python
# Line 304: Error handling in read_voltage
if "HANDLE_NOT_OPEN" in str(e) or "NO_DEVICES_FOUND" in str(e):
    self._connection_state = ConnectionState.ERROR
```

---

### Issue 3: Stream Mode Conflicts (HIGH PRIORITY)

**Location:** `labjack_detection_service.py:856-880`

**Problem:**
```python
# Line 858-878: Stream mode initialization (per session!)
if config.use_stream_mode:
    success, actual_rate = self.labjack_service.start_stream_mode(
        channels=config.channels,
        scan_rate=config.sample_rate,
        scans_per_read=scans_per_read
    )
```

**Issue:**
- LabJack hardware supports **ONE stream configuration** at a time
- Multiple sessions may attempt to start stream with **different configurations**
- No coordination between sessions on stream ownership

**Failure Scenario:**
```
Session 1: start_stream_mode(channels=["AIN0"], rate=1000)  ✅
Session 2: start_stream_mode(channels=["AIN0", "AIN1"], rate=200)  ❌ Conflict!
```

---

### Issue 4: Timing Synchronization Null References

**Location:** Multiple files - grep results show:

```python
# socketio_server.py:1100
if video_result.video_start_time:
    video_result.actual_duration_ms = (video_end_time - video_result.video_start_time) * 1000.0
else:
    logger.warning(f"⚠️ video_start_time is NULL")  # ❌ Observed in logs
```

**Root Cause:**
- `video_start_time` populated by first session starting video playback
- Second concurrent session **may not receive timing data** if it starts monitoring **before** video timing is established
- Leads to:
  - `video_relative_timestamp: None`
  - `actual_latency_ms: None`
  - Ground truth matching failures

---

### Issue 5: Batch Commit Race Conditions

**Location:** `labjack_detection_service.py:188-195`

**Problem:**
```python
# Batch commit optimization
self.detection_batch: List[Any] = []  # ❌ Shared across all sessions
self.last_commit_time: float = time.time()
self.batch_size_threshold: int = 100
self.batch_lock = threading.Lock()  # ✅ Lock exists
self.batch_db_session = None  # ⚠️ Single DB session for all batches
```

**Race Condition:**
```python
# Multiple threads adding to same batch list
Thread A (Session 1): batch.append(detection_event_1)
Thread B (Session 2): batch.append(detection_event_2)
Thread A: _flush_batch_commits() → commits events from BOTH sessions
Thread B: _flush_batch_commits() → sees empty batch, skips commit
```

---

## Detection Window Validation Errors

**Location:** `labjack_detection_service.py:851-854`

```python
# CRITICAL FIX: Initialize detection window validation counters
skipped_early_detections = 0
skipped_late_detections = 0  # ❌ Incremented when timing data missing
total_valid_detections = 0
```

**"Skipped Late" Detections:**
- Occur when `video_start_time` is `None` or timing window undefined
- Detection events received **after expected video end time**
- Caused by concurrent sessions with misaligned timing synchronization

---

## Recommended Fixes

### Fix 1: Session-Level Hardware Access Scheduling (CRITICAL)

**Approach:** Implement a hardware access coordinator with per-session time slots

```python
class LabJackAccessCoordinator:
    """Coordinate hardware access across multiple sessions"""

    def __init__(self, connection_manager: LabJackConnectionManager):
        self.connection_manager = connection_manager
        self.session_access_lock = threading.Lock()
        self.active_session_queue = queue.Queue()
        self.session_time_slots: Dict[str, float] = {}  # session_id -> next_access_time

    def acquire_hardware_access(self, session_id: str, timeout: float = 0.1) -> bool:
        """
        Acquire exclusive hardware access for a session with timeout

        Returns:
            True if access granted within timeout, False otherwise
        """
        acquired = self.session_access_lock.acquire(timeout=timeout)
        if acquired:
            self.session_time_slots[session_id] = time.time()
        return acquired

    def release_hardware_access(self, session_id: str):
        """Release hardware access"""
        try:
            self.session_access_lock.release()
        except RuntimeError:
            logger.warning(f"Session {session_id} attempted to release lock it didn't hold")

    def read_channels_synchronized(self, session_id: str, channels: List[str]) -> Dict[str, float]:
        """
        Read all channels atomically for a session

        This ensures all channel reads happen without interruption from other sessions
        """
        if not self.acquire_hardware_access(session_id, timeout=0.05):
            logger.warning(f"Session {session_id} failed to acquire hardware access")
            return {ch: 0.0 for ch in channels}

        try:
            # Atomic multi-channel read
            return self.connection_manager.read_multiple_voltages(channels)
        finally:
            self.release_hardware_access(session_id)
```

**Integration:**
```python
# In _monitoring_loop()
def _monitoring_loop(self, session_id: str):
    config = self.active_sessions[session_id]
    coordinator = self.hardware_access_coordinator

    while not stop_event.is_set():
        # Synchronized hardware read
        channel_readings = coordinator.read_channels_synchronized(
            session_id,
            config.channels
        )

        # Process detections with consistent snapshot
        for channel, voltage in channel_readings.items():
            self._process_detection(session_id, channel, voltage)
```

---

### Fix 2: Stream Mode Mutual Exclusion

**Problem:** Only one session can use stream mode at a time

**Solution:** First session to start gets stream mode, others use polling

```python
class LabJackStreamManager:
    """Manage stream mode ownership across sessions"""

    def __init__(self):
        self.stream_owner: Optional[str] = None  # session_id
        self.stream_lock = threading.Lock()
        self.stream_config: Optional[Dict[str, Any]] = None

    def acquire_stream_mode(self, session_id: str, channels: List[str], rate: int) -> bool:
        """
        Try to acquire stream mode for a session

        Returns:
            True if stream mode acquired, False if another session owns it
        """
        with self.stream_lock:
            if self.stream_owner is None:
                self.stream_owner = session_id
                self.stream_config = {'channels': channels, 'rate': rate}
                logger.info(f"✅ Session {session_id} acquired stream mode")
                return True
            elif self.stream_owner == session_id:
                return True  # Already owns it
            else:
                logger.warning(
                    f"❌ Session {session_id} cannot use stream mode - "
                    f"owned by {self.stream_owner}"
                )
                return False

    def release_stream_mode(self, session_id: str):
        """Release stream mode ownership"""
        with self.stream_lock:
            if self.stream_owner == session_id:
                self.stream_owner = None
                self.stream_config = None
                logger.info(f"🔓 Session {session_id} released stream mode")
```

---

### Fix 3: Per-Session Timing Synchronization

**Problem:** `video_start_time` null errors when multiple sessions start concurrently

**Solution:** Each session must wait for its own timing data before processing detections

```python
class SessionTimingCoordinator:
    """Coordinate timing synchronization per session"""

    def __init__(self):
        self.session_timing: Dict[str, Dict[str, Any]] = {}
        self.timing_ready_events: Dict[str, threading.Event] = {}
        self.timing_lock = threading.Lock()

    def register_session(self, session_id: str) -> threading.Event:
        """Register a session and return its timing ready event"""
        with self.timing_lock:
            if session_id not in self.timing_ready_events:
                self.timing_ready_events[session_id] = threading.Event()
                self.session_timing[session_id] = {
                    'video_start_time': None,
                    'video_duration': None,
                    'video_ids': []
                }
            return self.timing_ready_events[session_id]

    def set_timing_data(self, session_id: str, video_start_time: float,
                       video_duration: float, video_ids: List[str]):
        """Set timing data and signal ready event"""
        with self.timing_lock:
            self.session_timing[session_id] = {
                'video_start_time': video_start_time,
                'video_duration': video_duration,
                'video_ids': video_ids
            }
            if session_id in self.timing_ready_events:
                self.timing_ready_events[session_id].set()
                logger.info(f"✅ Timing data ready for session {session_id}")

    def wait_for_timing(self, session_id: str, timeout: float = 5.0) -> bool:
        """Wait for timing data to be ready"""
        if session_id not in self.timing_ready_events:
            return False

        ready = self.timing_ready_events[session_id].wait(timeout=timeout)
        if not ready:
            logger.error(f"❌ Timeout waiting for timing data: {session_id}")
        return ready

    def get_timing_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get timing data for a session"""
        with self.timing_lock:
            return self.session_timing.get(session_id)
```

**Integration:**
```python
# In start_monitoring()
def start_monitoring(self, session_id: str, **kwargs):
    # Register session for timing coordination
    timing_ready_event = self.timing_coordinator.register_session(session_id)

    # Store event in config metadata
    metadata = kwargs.get('metadata', {})
    metadata['timing_ready_event'] = timing_ready_event

    # Start monitoring thread
    config = DetectionConfig(session_id=session_id, metadata=metadata, ...)
    monitor_thread = threading.Thread(target=self._monitoring_loop, args=(session_id,))
    monitor_thread.start()

# In _monitoring_loop()
def _monitoring_loop(self, session_id: str):
    config = self.active_sessions[session_id]

    # Wait for timing data before processing detections
    timing_ready_event = config.metadata.get('timing_ready_event')
    if timing_ready_event:
        if not self.timing_coordinator.wait_for_timing(session_id, timeout=10.0):
            logger.error(f"❌ Cannot start monitoring without timing data: {session_id}")
            return

    # Get validated timing data
    timing_data = self.timing_coordinator.get_timing_data(session_id)
    video_start_time = timing_data['video_start_time']
    video_duration = timing_data['video_duration']

    # Now safe to process detections with timing context
    while not stop_event.is_set():
        # ... monitoring loop with guaranteed timing data
```

---

### Fix 4: Per-Session Batch Commit Isolation

**Problem:** Single batch list shared across all sessions

**Solution:** Separate batch lists per session

```python
class SessionBatchManager:
    """Manage per-session detection event batching"""

    def __init__(self):
        self.session_batches: Dict[str, List[Any]] = {}  # session_id -> events
        self.session_locks: Dict[str, threading.Lock] = {}
        self.session_db_sessions: Dict[str, Session] = {}

    def add_event(self, session_id: str, event: DetectionEvent):
        """Add event to session-specific batch"""
        if session_id not in self.session_locks:
            self.session_locks[session_id] = threading.Lock()
            self.session_batches[session_id] = []

        with self.session_locks[session_id]:
            self.session_batches[session_id].append(event)

    def flush_batch(self, session_id: str, force: bool = False):
        """Flush batch for a specific session"""
        if session_id not in self.session_locks:
            return

        with self.session_locks[session_id]:
            batch = self.session_batches.get(session_id, [])
            if not batch:
                return

            # Check if batch should be committed
            if force or len(batch) >= 100:
                try:
                    db = self.session_db_sessions.get(session_id) or SessionLocal()
                    for event in batch:
                        db.add(event)
                    db.commit()
                    logger.info(f"✅ Committed {len(batch)} events for session {session_id}")
                    self.session_batches[session_id] = []
                except Exception as e:
                    logger.error(f"Batch commit failed for {session_id}: {e}")
                    db.rollback()
```

---

## Testing Strategy

### Test Scenario 1: Concurrent Session Detection

**Setup:**
- Start Session A with 1000Hz polling on AIN0
- Start Session B with 200Hz polling on AIN0, AIN1
- Inject detection signal on AIN0

**Expected Behavior (Current):**
- ❌ Sessions read interleaved voltage samples
- ❌ Detection timestamps from different points in time
- ❌ Ground truth matching fails due to timing skew

**Expected Behavior (Fixed):**
- ✅ Sessions acquire hardware access sequentially
- ✅ Each session gets complete atomic snapshots
- ✅ Detection timestamps properly synchronized

### Test Scenario 2: Stream Mode Contention

**Setup:**
- Session A requests stream mode at 1000Hz
- Session B requests stream mode at 200Hz

**Expected Behavior (Current):**
- ❌ Second session overwrites stream configuration
- ❌ First session receives incorrect sample rate

**Expected Behavior (Fixed):**
- ✅ Session A acquires stream mode
- ✅ Session B falls back to polling mode
- ✅ Both sessions function correctly

### Test Scenario 3: Timing Synchronization Race

**Setup:**
- Start Session A monitoring
- Start Session B monitoring 50ms later
- Video playback starts after 100ms

**Expected Behavior (Current):**
- ❌ Session B processes detections before timing data available
- ❌ `video_start_time is None` warnings
- ❌ Detections marked as "skipped late"

**Expected Behavior (Fixed):**
- ✅ Both sessions wait for timing data
- ✅ Processing begins only after timing synchronized
- ✅ All detections have valid timing context

---

## Implementation Priority

### Phase 1: Critical Fixes (Immediate)
1. **Session-Level Hardware Access Coordination** - Prevents race conditions
2. **Stream Mode Mutual Exclusion** - One owner at a time
3. **Per-Session Timing Synchronization** - Eliminate null references

### Phase 2: Performance Optimization (Short-term)
4. **Per-Session Batch Commit Isolation** - Prevent cross-session interference
5. **Hardware Access Scheduling** - Time-slot allocation for fairness

### Phase 3: Advanced Features (Long-term)
6. **Session Priority Queue** - Critical sessions get priority
7. **Hardware Access Metrics** - Track contention and wait times
8. **Adaptive Polling Rates** - Reduce contention with dynamic rates

---

## Validation Criteria

### Success Metrics

1. **Zero Hardware Access Conflicts**
   - No `LJME_DEVICE_CURRENTLY_CLAIMED_BY_ANOTHER_PROCESS` errors
   - No interleaved channel reads between sessions

2. **Consistent Timing Synchronization**
   - Zero `video_start_time is None` warnings
   - All detections have valid `video_relative_timestamp`
   - Ground truth matching success rate > 95%

3. **Session Isolation**
   - Session A stopping does not affect Session B
   - Batch commits isolated per session
   - Clean session cleanup without side effects

4. **Performance Targets**
   - Hardware access contention < 5% of monitoring time
   - Detection latency variance < 10ms between concurrent sessions
   - Stream mode fallback < 1% of sessions

---

## Appendix: Code References

### Key File Locations

| Component | File | Lines |
|-----------|------|-------|
| Connection Manager | `labjack_connection_manager.py` | 75-546 |
| Detection Monitor | `labjack_detection_service.py` | 157-1200 |
| Dedicated Monitor | `dedicated_labjack_monitor.py` | 80-1100 |
| Timing Service | `video_timing_service.py` | - |
| Orchestrator | `video_sequence_orchestrator.py` | - |

### Error Messages to Monitor

```python
# Device conflict errors
"LJME_DEVICE_CURRENTLY_CLAIMED_BY_ANOTHER_PROCESS"
"HANDLE_NOT_OPEN"
"NO_DEVICES_FOUND"

# Timing errors
"video_start_time is NULL"
"skipped late detections"
"Cannot calculate actual_duration_ms"

# Synchronization errors
"Timeout waiting for timing data"
"Failed to acquire hardware access"
"Stream mode conflict"
```

---

## Conclusion

The LabJack connection manager implements proper **singleton** and **thread-safe** patterns, but **lacks session-level coordination** for concurrent hardware access. The primary issues are:

1. **Uncoordinated monitoring loops** causing interleaved hardware reads
2. **Stream mode conflicts** with no mutual exclusion
3. **Timing synchronization race conditions** leading to null references
4. **Shared batch commit system** without session isolation

Implementing the recommended fixes will resolve these concurrency issues and enable reliable multi-session hardware validation testing.
