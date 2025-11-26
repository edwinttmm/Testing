# Thread Lifecycle Research: Monitoring Thread Stop Issue

**Research Date**: 2025-11-19
**File Analyzed**: `/backend/services/labjack_detection_service.py` (2507 lines)
**Problem**: Monitoring thread continues processing after stop signal sent

---

## Executive Summary

The monitoring thread doesn't stop cleanly because of a **multi-threaded race condition** involving:
1. Main monitoring thread (daemon)
2. Storage worker thread (non-daemon)
3. Storage queue still being populated while thread is "stopping"
4. Callbacks executing AFTER stop_event is set but BEFORE thread exits

**Root Cause**: The stop sequence waits for the thread to exit, then waits for the storage queue to drain, but **new events can be queued DURING the thread exit process** because the monitoring loop continues processing buffered data while shutting down.

---

## Thread Architecture

### 1. Primary Threads

#### **Monitoring Thread** (Lines 464-470)
```python
monitor_thread = threading.Thread(
    target=target_func,  # _monitoring_loop or _monitoring_loop_stream
    args=(session_id,),
    daemon=True,  # ⚠️ CRITICAL: Daemon thread
    name=f"LabJackMonitor-{session_id}-{mode_label}"
)
```

**Properties**:
- **Daemon**: True (terminates when main thread exits)
- **Function**: `_monitoring_loop()` (polling) or `_monitoring_loop_stream()` (stream mode)
- **Stop Signal**: `threading.Event` per session (line 445)

#### **Storage Worker Thread** (Lines 1842-1846)
```python
threading.Thread(
    target=self._storage_worker,
    daemon=False,  # ⚠️ Non-daemon to allow graceful shutdown
    name="DetectionStorageWorker"
).start()
```

**Properties**:
- **Daemon**: False (survives main thread exit)
- **Function**: `_storage_worker()` processes `storage_queue`
- **Stop Signal**: `self.storage_worker_running` flag (line 1857)

---

## Stop Sequence Analysis

### Current Stop Flow (Lines 479-577)

```
1. Lock acquired
2. Set status to STOPPING (line 506)
3. Set stop_event (line 510)
4. Wait for monitoring thread (timeout=5.0s) (line 518)
5. Check if thread stopped (line 520-523)
6. Wait for storage queue to drain (timeout=5.0s) (lines 530-543)
7. Flush batch commits (line 546)
8. Clean up session data
```

### Critical Timeline with Race Conditions

```
Time    Main Thread              Monitoring Thread           Storage Worker
------  -----------------------  --------------------------  ------------------
T+0ms   Set stop_event           [Running loop iteration]    [Processing queue]

T+10ms  Wait for thread.join()   Checks stop_event.is_set()  [Processing...]
                                 (STILL FALSE at top of loop)

T+15ms  [Waiting...]             Reads stream buffer         [Processing...]
                                 → Finds 500 samples

T+20ms  [Waiting...]             Processing sample 1/500     [Processing...]
                                 → Creates detection event
                                 → Calls _record_detection_event()

T+25ms  [Waiting...]             Processing sample 50/500    [Processing...]
                                 → Queues to storage_queue ⚠️

T+30ms  [Waiting...]             Processing sample 100/500   [Processing event]
                                 → More events queued ⚠️

T+50ms  [Waiting...]             Processing sample 200/500   [Processing event]
                                 → Callbacks fired ⚠️

T+100ms [Waiting...]             Finally checks stop_event   [Processing...]
                                 at top of NEXT iteration
                                 → Loop exits

T+105ms [Waiting...]             Finally block executing     [Processing...]
                                 → stop_stream_mode() called

T+110ms Thread.join() returns    Thread exited              [Processing...]

T+115ms Wait for queue drain     [Stopped]                  [Processing event]
                                                             (150 items left!)

T+5000ms Queue timeout!          [Stopped]                  [Still processing]
        Warning logged: "queue not fully drained"

T+5001ms Function returns        [Stopped]                  [STILL PROCESSING]
        "✅ Monitoring stopped"                              ⚠️ RACE CONDITION
```

---

## Key Issues Identified

### 1. **Buffered Data Processing During Shutdown**

**Location**: Lines 1266-1393 (`_monitoring_loop_stream`)

```python
while not stop_event.is_set():
    # Read stream data - can return HUNDREDS of samples
    stream_data, backlog, read_success = self.labjack_service.read_stream_mode()

    # Process EACH sample (lines 1307-1389)
    for i in range(num_samples):  # ⚠️ Could be 500+ samples!
        # Extract channel values
        # Calculate timestamp
        # Check threshold
        # Create detection event
        # Call _record_detection_event()  # ⚠️ Queues to storage_queue
```

**Problem**: At 1000 Hz scan rate with `scans_per_read=100`, a single `read_stream_mode()` call can return 100+ samples. If `stop_event` is checked at the TOP of the loop but the loop is in the middle of processing a large buffer, it will continue processing ALL samples before checking again.

**Example**:
- Loop iteration starts, `stop_event.is_set()` = False
- Reads 500 samples from stream buffer
- Stop signal arrives during processing
- Continues processing all 500 samples (takes 50-100ms)
- Each sample can trigger detection → queued to storage
- Loop finally checks `stop_event` at next iteration

### 2. **Storage Queue Continues After Thread Stops**

**Location**: Lines 1832-1888

```python
def _schedule_db_storage(self, event: DetectionEvent):
    """Schedule database storage from synchronous context"""
    if not hasattr(self, 'storage_queue'):
        self.storage_queue = queue.Queue()
        # Start worker thread if not already running
        if not hasattr(self, 'storage_worker_running'):
            self.storage_worker_running = True
            threading.Thread(...).start()

    self.storage_queue.put(event)  # ⚠️ No check if stopping!
```

**Problem**: `_schedule_db_storage()` has NO GUARDS to prevent queueing during shutdown. Events can be queued even after `stop_event` is set.

### 3. **Callback Firing During Shutdown**

**Location**: Lines 1826-1830

```python
# Notify callbacks
self._notify_detection_callbacks(event)

# Send WebSocket notification
if config and config.enable_websocket:
    self._notify_websocket_callbacks(session_id, event)
```

**Problem**: Callbacks are invoked for EVERY detection event, even during shutdown. These callbacks can:
- Trigger async operations
- Queue more work
- Log messages (causing "still processing" logs)

### 4. **Storage Worker Non-Daemon Thread**

**Location**: Lines 1842-1846

```python
threading.Thread(
    target=self._storage_worker,
    daemon=False,  # ⚠️ Non-daemon to allow graceful shutdown
    name="DetectionStorageWorker"
).start()
```

**Problem**: Storage worker is **non-daemon** (intentionally, to prevent data loss), but there's no mechanism to signal it to stop quickly. It processes queue with 1.0s timeout on `queue.get()`, meaning it can continue for seconds after main thread reports "stopped".

### 5. **Thread Join Timeout Too Short**

**Location**: Line 518

```python
thread.join(timeout=5.0)  # Wait up to 5 seconds
```

**Problem**: 5-second timeout may not be enough if:
- Large stream buffer (500+ samples)
- Each sample triggers database writes
- Network latency to database
- Multiple sessions stopping simultaneously

### 6. **Race Between Stop Event and Loop Check**

**Location**: Lines 850, 1266

```python
while not stop_event.is_set():  # ⚠️ Checked only at loop start
    try:
        # ... process data (can take 50-100ms)
```

**Problem**: Stop event is checked ONCE per loop iteration at the start. During the iteration body, the thread can:
- Read from hardware (blocking call)
- Process hundreds of samples
- Queue to storage
- Fire callbacks

The thread doesn't respect the stop signal until the NEXT iteration check.

---

## Detailed Call Flow

### `stop_session_monitoring()` Execution Path

```
stop_session_monitoring(session_id)
├─ Acquire self.lock
├─ Set detection_status[session_id] = STOPPING
├─ Set stop_events[session_id].set()  # Signal thread to stop
├─ Wait for thread:
│  ├─ thread.join(timeout=5.0)
│  │  └─ [Monitoring thread continues processing buffer...]
│  └─ Check if thread.is_alive()
│     ├─ If alive: Log warning "did not stop within timeout"
│     └─ If stopped: Log "✅ Monitoring thread stopped"
├─ Wait for storage queue:
│  ├─ while not storage_queue.empty() and time < 5s:
│  │  └─ sleep(0.1)
│  └─ If not empty: Log warning "queue not fully drained"
├─ Flush batch commits
├─ Log statistics
└─ Clean up session resources
```

### `_monitoring_loop_stream()` Execution Path

```
_monitoring_loop_stream(session_id)
├─ Get config and stop_event
├─ Set status = MONITORING
├─ While not stop_event.is_set():  # ⚠️ Checked HERE
│  ├─ Check auto-stop condition
│  ├─ Read stream: stream_data, backlog, success = read_stream_mode()
│  │  └─ [BLOCKING CALL - can return 500+ samples]
│  ├─ For each sample in buffer:  # ⚠️ Stop event NOT checked here
│  │  ├─ Extract channel values
│  │  ├─ Calculate timestamp
│  │  ├─ Check voltage threshold
│  │  └─ If detection:
│  │     ├─ Create DetectionEvent
│  │     ├─ Call _record_detection_event()
│  │     │  ├─ Add to detection_events list
│  │     │  ├─ Call _schedule_db_storage()  # ⚠️ Queues to storage
│  │     │  ├─ Call _notify_detection_callbacks()  # ⚠️ Fires callbacks
│  │     │  └─ Call _notify_websocket_callbacks()  # ⚠️ Fires WS
│  │     └─ Log detection
│  └─ [Loop continues until next iteration check]
├─ Finally block:
│  ├─ Stop stream mode
│  └─ Set status = STOPPED
└─ Return
```

### `_storage_worker()` Execution Path

```
_storage_worker()
├─ While self.storage_worker_running:  # ⚠️ Never set to False!
│  ├─ Try:
│  │  ├─ event = storage_queue.get(timeout=1.0)
│  │  ├─ Store event in database
│  │  └─ storage_queue.task_done()
│  └─ Except queue.Empty:
│     └─ continue  # ⚠️ Continues indefinitely
└─ Log "stopped"
```

**CRITICAL**: `storage_worker_running` is NEVER set to False anywhere in the codebase! The worker thread runs FOREVER, only sleeping when queue is empty.

---

## Race Condition Scenarios

### Scenario 1: Large Stream Buffer During Stop

```
1. Monitoring loop iteration starts
2. Checks stop_event.is_set() → False
3. Calls read_stream_mode() → Returns 500 samples
4. User calls stop_monitoring()
   - Sets stop_event
   - Starts waiting for thread.join()
5. Thread processes sample 1/500 → Creates event → Queues to storage
6. Thread processes sample 2/500 → Creates event → Queues to storage
   ...
   [100ms passes while processing buffer]
   ...
7. Thread processes sample 500/500 → Creates event → Queues to storage
8. Thread finally checks stop_event at next iteration → Exits loop
9. stop_monitoring() thread.join() returns
10. Queue has 500 items, starts draining
11. Timeout after 5s, queue still has 350 items
12. Function returns "✅ Monitoring stopped"
13. Storage worker STILL processing remaining 350 events ⚠️
```

### Scenario 2: Callback Async Operations

```
1. Stop signal sent
2. Thread processing buffer, triggers detection
3. _notify_detection_callbacks(event) called
4. Callback launches async database query
5. Thread exits monitoring loop
6. stop_monitoring() returns
7. Callback's async operation completes AFTER stop
8. Logs "Detection event processed" ⚠️
```

### Scenario 3: Multiple Sessions

```
Session A:
1. Stop signal at T+0ms
2. Thread processing large buffer
3. Queuing 200 events to SHARED storage_queue

Session B:
1. Stop signal at T+50ms
2. Thread processing different buffer
3. Queuing 300 events to SAME storage_queue

Storage Worker:
1. Processing queue (shared by all sessions)
2. Queue depth = 500 items
3. 5-second timeout → Only processes ~50 items
4. 450 items remain AFTER both sessions "stopped"
```

---

## Thread Coordination Issues

### 1. **No Intra-Loop Stop Check**

**Current**:
```python
while not stop_event.is_set():
    # Process 500 samples (no stop check)
```

**Better**:
```python
while not stop_event.is_set():
    for i in range(num_samples):
        if stop_event.is_set():  # ⚠️ Check INSIDE loop
            break
        # Process sample
```

### 2. **No Storage Worker Shutdown Signal**

**Current**:
```python
self.storage_worker_running = True  # Set once, never False!
```

**Missing**:
```python
def shutdown_storage_worker(self):
    self.storage_worker_running = False
    # Signal worker to exit
```

### 3. **No Queue Rejection During Stop**

**Current**:
```python
def _schedule_db_storage(self, event):
    self.storage_queue.put(event)  # Always accepts
```

**Better**:
```python
def _schedule_db_storage(self, event):
    if session_id in self.stop_events and self.stop_events[session_id].is_set():
        logger.debug("Rejecting storage during shutdown")
        return
    self.storage_queue.put(event)
```

### 4. **No Callback Removal Before Stop**

**Current**:
```python
def stop_session_monitoring(self, session_id):
    stop_event.set()
    thread.join()
    # Callbacks still registered! ⚠️
```

**Better**:
```python
def stop_session_monitoring(self, session_id):
    # Remove callbacks FIRST
    self._remove_session_callbacks(session_id)
    # Then signal stop
    stop_event.set()
    thread.join()
```

---

## Memory and Resource Implications

### Shared State Between Threads

**Shared Resources**:
1. `self.storage_queue` - Single queue for ALL sessions
2. `self.detection_callbacks` - Global callback list
3. `self.websocket_callbacks` - Global callback list
4. `self.detection_events[session_id]` - Per-session event list
5. `self.active_sessions[session_id]` - Session config
6. `self.labjack_service` - Shared hardware connection

**Lock Protection**:
- `self.lock` (RLock) used for:
  - Adding/removing sessions
  - Accessing detection_events
  - Callback registration

**NOT Lock Protected**:
- Queue operations (thread-safe by design)
- Detection event creation
- Callback invocation

### Memory Leak Potential

If storage worker never stops and queue continues filling:
- Each `DetectionEvent` ~500 bytes
- 1000 events/sec → 500 KB/sec
- After 1 hour: 1.8 GB of events in queue

---

## Recommendations

### 1. **Immediate Fix: Intra-Loop Stop Check**

**Priority**: CRITICAL
**Complexity**: Low
**Location**: Lines 1307-1389

Add stop check inside sample processing loop:
```python
for i in range(num_samples):
    if stop_event.is_set():
        logger.info("Stop signal received mid-buffer, breaking")
        break
    # Process sample...
```

### 2. **Critical Fix: Guard Storage Queue During Stop**

**Priority**: CRITICAL
**Complexity**: Low
**Location**: Line 1848

Check stop state before queueing:
```python
def _schedule_db_storage(self, event: DetectionEvent):
    # Don't queue if session is stopping
    if (event.session_id in self.stop_events and
        self.stop_events[event.session_id].is_set()):
        logger.debug(f"Skipping storage for {event.id} - session stopping")
        return

    self.storage_queue.put(event)
```

### 3. **High Priority: Storage Worker Shutdown**

**Priority**: HIGH
**Complexity**: Medium
**Location**: Lines 1853-1888

Add proper shutdown mechanism:
```python
def shutdown_storage_worker(self):
    """Signal storage worker to stop and wait for it"""
    if hasattr(self, 'storage_worker_running'):
        self.storage_worker_running = False

    # Give worker thread time to finish current item
    if hasattr(self, 'storage_worker_thread'):
        self.storage_worker_thread.join(timeout=10.0)
        if self.storage_worker_thread.is_alive():
            logger.warning("Storage worker did not stop cleanly")
```

Call in `stop_session_monitoring()` after queue drain.

### 4. **Medium Priority: Remove Callbacks Before Stop**

**Priority**: MEDIUM
**Complexity**: Medium
**Location**: Lines 309-328

Add per-session callback tracking:
```python
self.session_callbacks: Dict[str, List[Callable]] = {}

def add_detection_callback(self, callback, session_id=None):
    with self.lock:
        if session_id:
            self.session_callbacks.setdefault(session_id, []).append(callback)
        self.detection_callbacks.append(callback)

def _remove_session_callbacks(self, session_id):
    """Remove all callbacks for a session"""
    with self.lock:
        for callback in self.session_callbacks.get(session_id, []):
            if callback in self.detection_callbacks:
                self.detection_callbacks.remove(callback)
        self.session_callbacks.pop(session_id, None)
```

### 5. **Low Priority: Increase Thread Join Timeout**

**Priority**: LOW
**Complexity**: Trivial
**Location**: Line 518

```python
# Increase timeout for large buffers
thread.join(timeout=10.0)  # Was 5.0
```

### 6. **Architectural: Separate Storage Queues Per Session**

**Priority**: MEDIUM (Long-term)
**Complexity**: High

```python
self.storage_queues: Dict[str, queue.Queue] = {}
self.storage_workers: Dict[str, threading.Thread] = {}

def start_monitoring(self, session_id, ...):
    # Create dedicated queue and worker for this session
    self.storage_queues[session_id] = queue.Queue()
    worker = threading.Thread(
        target=self._storage_worker,
        args=(session_id,),
        daemon=False
    )
    self.storage_workers[session_id] = worker
    worker.start()

def stop_session_monitoring(self, session_id):
    # Stop only this session's worker
    if session_id in self.storage_queues:
        # Wait for queue to drain
        # Signal worker to stop
        # Join worker thread
```

**Benefits**:
- Session isolation (one session's buffer doesn't affect others)
- Cleaner shutdown (each session's worker stops independently)
- Better monitoring (per-session queue metrics)

---

## Testing Strategy

### Unit Tests Needed

1. **Test: Stop during buffer processing**
   - Start monitoring with large scan rate
   - Generate 500+ samples
   - Call stop mid-buffer
   - Assert: Thread stops within 1s
   - Assert: No events queued after stop signal

2. **Test: Storage worker shutdown**
   - Queue 100 events
   - Stop monitoring
   - Wait for queue drain
   - Assert: Storage worker thread terminates
   - Assert: All 100 events processed

3. **Test: Multiple session stop**
   - Start 3 sessions
   - Stop all simultaneously
   - Assert: All threads stop cleanly
   - Assert: No queue overflow

4. **Test: Callback removal**
   - Register callback for session
   - Stop session
   - Trigger detection (shouldn't happen, but simulate)
   - Assert: Callback not invoked

### Integration Tests Needed

1. **Stress test: High-frequency detection during stop**
   - 1000 Hz signal with 200 Hz detection
   - Stop after 1 second
   - Assert: Clean shutdown within 2s

2. **Latency test: Stop response time**
   - Measure time from stop_signal to thread exit
   - Target: < 500ms

---

## Metrics to Track

### Thread Health Metrics

1. **Thread Stop Latency**
   - Time from `stop_event.set()` to `thread.join()` return
   - Target: < 500ms

2. **Queue Drain Time**
   - Time to drain storage queue after thread stop
   - Target: < 2s

3. **Residual Event Count**
   - Events queued AFTER stop signal
   - Target: 0

4. **Storage Worker Idle Time**
   - Time storage worker spends waiting (queue empty)
   - Target: > 90% when no active sessions

### Implementation Checklist

- [ ] Add intra-loop stop check in `_monitoring_loop_stream()`
- [ ] Add stop guard in `_schedule_db_storage()`
- [ ] Implement `shutdown_storage_worker()`
- [ ] Add per-session callback tracking
- [ ] Increase thread join timeout to 10s
- [ ] Add metrics logging for stop latency
- [ ] Create unit tests for stop scenarios
- [ ] Create integration tests for multi-session stop
- [ ] Document new shutdown protocol
- [ ] Update API docs with shutdown behavior

---

## Appendix: Key Code Locations

| Component | Line Range | Function |
|-----------|------------|----------|
| Thread creation | 464-470 | `start_monitoring()` |
| Stop signal | 509-510 | `stop_session_monitoring()` |
| Thread join | 514-526 | `stop_session_monitoring()` |
| Queue drain wait | 530-543 | `stop_session_monitoring()` |
| Monitoring loop | 1266-1406 | `_monitoring_loop_stream()` |
| Stop check | 1266, 850 | While loop condition |
| Buffer processing | 1307-1389 | Sample iteration |
| Event recording | 1383 | `_record_detection_event()` |
| Storage queueing | 1832-1851 | `_schedule_db_storage()` |
| Storage worker | 1853-1888 | `_storage_worker()` |
| Callback firing | 1826-1830 | `_record_detection_event()` |
| Stream reading | 1277 | `read_stream_mode()` |
| Stream stopping | 1408-1414 | Finally block |

---

## Conclusion

The "monitoring thread did not stop within timeout" issue is caused by a **cascade of race conditions**:

1. **Primary cause**: Stop event checked only at loop start, not during buffer processing
2. **Secondary cause**: Storage queue continues accepting events during shutdown
3. **Tertiary cause**: Storage worker thread never receives shutdown signal
4. **Contributing factor**: Callbacks fire during shutdown, generating more work
5. **Amplifying factor**: Large stream buffers (500+ samples) take 50-100ms to process

**Immediate action required**: Add intra-loop stop check and storage queue guard.

**Long-term solution**: Per-session storage workers with proper shutdown coordination.

---

**Research completed by**: Claude Code Research Agent
**Approval status**: Ready for implementation team review
