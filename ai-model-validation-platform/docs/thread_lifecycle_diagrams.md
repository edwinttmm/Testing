# Thread Lifecycle Visual Diagrams

## 1. Thread Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    LabJackDetectionMonitor                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐         ┌──────────────────┐            │
│  │ Session A        │         │ Session B        │            │
│  │ Monitoring Thread│         │ Monitoring Thread│            │
│  │ (daemon=True)    │         │ (daemon=True)    │            │
│  └────────┬─────────┘         └────────┬─────────┘            │
│           │                             │                       │
│           │ Queues events               │ Queues events        │
│           ▼                             ▼                       │
│  ┌────────────────────────────────────────────────┐            │
│  │         Shared Storage Queue                   │            │
│  │         (thread-safe, unbounded)               │            │
│  └────────────────────┬───────────────────────────┘            │
│                       │                                         │
│                       │ Processes events                        │
│                       ▼                                         │
│  ┌────────────────────────────────────────────────┐            │
│  │    Storage Worker Thread                       │            │
│  │    (daemon=False, single shared worker)        │            │
│  │    ⚠️ NEVER STOPS - no shutdown signal!        │            │
│  └────────────────────────────────────────────────┘            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Current Stop Sequence (With Race Condition)

```
Main Thread                 Monitoring Thread              Storage Worker
    │                              │                              │
    │ stop_session_monitoring()    │                              │
    ├─────────────────────────────►│                              │
    │ Set stop_event               │                              │
    │                              │ ◄────────── RACE WINDOW ────►│
    │                              │                              │
    │ thread.join(timeout=5.0)     │                              │
    │ [WAITING...]                 │ Still in loop iteration      │
    │                              │ while not stop_event:        │
    │                              │   stream_data = read()       │
    │                              │   # Returns 500 samples!     │
    │                              │                              │
    │                              │   for i in range(500):       │
    │                              │     process_sample(i)        │
    │                              │     create_detection()       │
    │                              │     queue.put(event) ────────►│ Accepting events!
    │                              │     [sample 50/500]          │
    │                              │                              │
    │ [STILL WAITING...]           │     [sample 100/500]         │
    │                              │                              │
    │                              │     [sample 200/500]         │
    │                              │     callback(event) ⚠️       │
    │                              │                              │
    │                              │     [sample 500/500] ✓       │
    │                              │                              │
    │                              │ Check stop_event ✓           │
    │                              │ Exit loop                    │
    │ ◄────────────────────────────┤                              │
    │ Thread joined                │ [STOPPED]                    │
    │                              │                              │
    │ Wait for queue drain         │                              │
    │ while not queue.empty():     │                              │ Processing...
    │   sleep(0.1)                 │                              │ (450 items)
    │   [timeout after 5s] ⏱️       │                              │
    │                              │                              │
    │ ⚠️ Queue not drained!         │                              │ Still processing!
    │ Return "✅ Stopped"           │                              │ (350 items left)
    │                              │                              │
    │ [Function returns]           │                              │ ⚠️ STILL RUNNING!
    │                              │                              │
```

## 3. Race Condition Timing Diagram

```
Timeline showing stop signal vs actual stop:

T=0ms    │ User calls stop_monitoring()
         │ Set stop_event
         ▼
         ┌──────────────────────────────────────┐
         │    CRITICAL RACE WINDOW              │
         │                                      │
T=10ms   │ Thread reads stop_event.is_set()    │ ← Returns FALSE
         │ (at top of loop)                    │
         │                                      │
T=15ms   │ Thread calls read_stream_mode()     │ ← BLOCKING
         │ Returns 500 samples                 │
         │                                      │
T=20ms   │ Processing sample 1/500             │
         │ Creates event, queues to storage    │ ← Event queued AFTER stop!
         │                                      │
T=30ms   │ Processing sample 50/500            │
         │ Main thread waiting in join()       │
         │                                      │
T=50ms   │ Processing sample 100/500           │
         │ Callbacks fired for each detection  │
         │                                      │
T=100ms  │ Processing sample 500/500 ✓         │
         │                                      │
T=105ms  │ Finally checks stop_event           │ ← Returns TRUE
         │ Exits loop                          │
         │                                      │
         └──────────────────────────────────────┘
T=110ms  │ Thread exits, join() returns
         │ ✅ "Monitoring thread stopped"
         ▼
         But storage worker still processing 450 events...
```

## 4. Data Flow During Shutdown

```
┌─────────────────────────────────────────────────────────────────┐
│  Stream Buffer (Hardware)                                       │
│  ┌────┬────┬────┬────┬────┬────┬────┬─...─┬────┬────┬────┐    │
│  │ S1 │ S2 │ S3 │ S4 │ S5 │ S6 │ S7 │ ... │498 │499 │500 │    │
│  └────┴────┴────┴────┴────┴────┴────┴─...─┴────┴────┴────┘    │
│         ▲                                                        │
│         │ read_stream_mode() returns ALL samples at once       │
│         │                                                        │
└─────────┼────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Monitoring Thread Loop                                         │
│                                                                 │
│  while not stop_event.is_set():  ◄─── Checked HERE only       │
│      stream_data = read_stream()                               │
│                                                                 │
│      for sample in stream_data:  ◄─── No stop check inside!   │
│          if voltage > threshold:                               │
│              event = create_detection()                        │
│              ├─► storage_queue.put(event)  ⚠️ During stop!     │
│              ├─► callback(event)           ⚠️ During stop!     │
│              └─► websocket.emit(event)     ⚠️ During stop!     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Storage Queue (Continues filling during stop!)                │
│                                                                 │
│  ┌────┬────┬────┬────┬────┬────┬────┬─...─┬────┬────┬────┐    │
│  │ E1 │ E2 │ E3 │ E4 │ E5 │ E6 │ E7 │ ... │450 │451 │452 │    │
│  └────┴────┴────┴────┴────┴────┴────┴─...─┴────┴────┴────┘    │
│         ▲                                                        │
│         │ Events queued AFTER stop_event.set()                 │
│         │                                                        │
└─────────┼────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Storage Worker (Never stops!)                                 │
│                                                                 │
│  while self.storage_worker_running:  ◄─── Always True!        │
│      event = queue.get(timeout=1.0)                            │
│      store_in_database(event)                                  │
│                                                                 │
│  ⚠️ storage_worker_running NEVER set to False                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 5. Multiple Session Stop Race

```
Session A                    Session B                    Storage Queue
    │                           │                               │
    │ Stop signal               │                               │
    ├─────────────────────────► Queue events                    │
    │ (processing 500 samples)  │                               │
    │                           │ Stop signal                   │
    │                           ├─────────────────────────────► │
    │                           │ (processing 500 samples)      │
    │                           │                               │
    │ Event 1                   │                               │
    ├───────────────────────────────────────────────────────────►│ Count: 1
    │                           │ Event 1                       │
    │                           ├───────────────────────────────►│ Count: 2
    │ Event 2                   │                               │
    ├───────────────────────────────────────────────────────────►│ Count: 3
    │                           │ Event 2                       │
    │                           ├───────────────────────────────►│ Count: 4
    │ ...                       │ ...                           │
    │                           │                               │
    │ Event 250 ✓               │                               │
    ├───────────────────────────────────────────────────────────►│ Count: 500
    │ Thread stops              │                               │
    │ "✅ Stopped"               │                               │
    │                           │ Event 250 ✓                   │
    │                           ├───────────────────────────────►│ Count: 750
    │                           │ Thread stops                  │
    │                           │ "✅ Stopped"                   │
    │                           │                               │
    │                           │                               │ ⚠️ 750 items
    │                           │                               │    still queued!
    │                           │                               │
```

## 6. Recommended Fix: Intra-Loop Stop Check

```
┌─────────────────────────────────────────────────────────────────┐
│  BEFORE (Current - Race Condition)                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  while not stop_event.is_set():       ◄── Check only here     │
│      stream_data = read_stream()                               │
│                                                                 │
│      for sample in stream_data:       ◄── No check inside!    │
│          if voltage > threshold:                               │
│              process_detection()      ◄── Continues even if    │
│                                            stop signaled!       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  AFTER (Fixed - No Race)                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  while not stop_event.is_set():       ◄── Check at loop start │
│      stream_data = read_stream()                               │
│                                                                 │
│      for sample in stream_data:                                │
│          if stop_event.is_set():      ◄── ✅ Check inside!     │
│              break                    ◄── ✅ Exit immediately  │
│                                                                 │
│          if voltage > threshold:                               │
│              process_detection()                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 7. Recommended Fix: Storage Queue Guard

```
┌─────────────────────────────────────────────────────────────────┐
│  BEFORE (Current - Accepts During Stop)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  def _schedule_db_storage(event):                              │
│      self.storage_queue.put(event)    ◄── Always accepts!     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  AFTER (Fixed - Rejects During Stop)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  def _schedule_db_storage(event):                              │
│      session_id = event.session_id                             │
│                                                                 │
│      # ✅ Check if session is stopping                         │
│      if (session_id in self.stop_events and                    │
│          self.stop_events[session_id].is_set()):               │
│          logger.debug("Rejecting - session stopping")          │
│          return  # ◄── Early return, don't queue              │
│                                                                 │
│      self.storage_queue.put(event)                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 8. Thread State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│  Monitoring Thread States                                      │
└─────────────────────────────────────────────────────────────────┘

    STOPPED ──────────────────────────────────┐
       ▲                                       │
       │                                       │ start_monitoring()
       │                                       ▼
       │                                   STARTING
       │                                       │
       │                                       │ Thread started
       │                                       ▼
       │                                  MONITORING
       │                                       │
       │                                       │ Process samples
       │                                       │ Queue events
       │                                       │ Fire callbacks
       │                                       │
       │ stop_event.set()                      │
       │                                       ▼
       │                                   STOPPING
       │                                  ┌─────────┐
       │                                  │ ⚠️ RACE │
       │                                  │ WINDOW  │
       │                                  │         │
       │                                  │ Still   │
       │                                  │ process │
       │                                  │ buffer  │
       │                                  └─────────┘
       │                                       │
       │                                       │ Loop exits
       └───────────────────────────────────────┘

Current Problem: STOPPING state can last 50-100ms while buffer processes
Recommended: Add intra-loop check to exit STOPPING → STOPPED quickly
```

## 9. Memory Impact Over Time

```
Memory Usage When Stop Hangs:

Storage Queue Growth:
┌────────────────────────────────────────────────────────────────┐
│ Events in Queue                                                │
│                                                                │
│ 1000│                                            ╱╲            │
│     │                                          ╱    ╲          │
│  800│                                        ╱        ╲        │
│     │                                      ╱            ╲      │
│  600│                                    ╱                ╲    │
│     │                              ╱╲  ╱                    ╲  │
│  400│                            ╱    ╱                       ╲│
│     │                          ╱    ╱                          │
│  200│                    ╱╲  ╱    ╱                            │
│     │              ╱╲  ╱    ╱                                  │
│    0├────────────────────────────────────────────────────────►│
│     0s    10s   20s  30s  40s  50s  60s  70s  80s  90s   100s │
│                                                                │
│     Normal     Session   Stop      Queue     Worker           │
│     operation  ends      signal    drains    catches up       │
│                                                                │
│ Problem: Spike at "Stop signal" because buffer still          │
│          processes 500 samples, queuing all events            │
│                                                                │
└────────────────────────────────────────────────────────────────┘

Each Event ≈ 500 bytes
Peak 1000 events = 500 KB
If not drained: Memory leak
```

## 10. Ideal Shutdown Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  Proper Shutdown Sequence (Recommended)                        │
└─────────────────────────────────────────────────────────────────┘

Main Thread              Monitoring Thread           Storage Worker
    │                           │                           │
    │ 1. Remove callbacks       │                           │
    ├──────────────────────────►│                           │
    │    [Callbacks cleared]    │                           │
    │                           │                           │
    │ 2. Set stop_event         │                           │
    ├──────────────────────────►│                           │
    │                           │ Check stop (in loop)      │
    │                           │ ✓ Break immediately       │
    │                           │                           │
    │ 3. Wait for thread        │                           │
    │    [max 500ms]            │                           │
    │ ◄─────────────────────────┤                           │
    │    Thread stopped         │ [STOPPED]                 │
    │                           │                           │
    │ 4. Wait for queue drain   │                           │
    │    [max 5s]               │                           │ Processing...
    │                           │                           │ (50 items left)
    │ ◄──────────────────────────────────────────────────────┤
    │    Queue empty            │                           │
    │                           │                           │
    │ 5. Stop storage worker    │                           │
    ├───────────────────────────────────────────────────────►│
    │    Set worker_running=False                           │
    │                           │                           │ Exits loop
    │ 6. Join worker thread     │                           │
    │    [max 2s]               │                           │
    │ ◄──────────────────────────────────────────────────────┤
    │    Worker stopped         │                           │ [STOPPED]
    │                           │                           │
    │ 7. Clean up resources     │                           │
    │    ✅ ALL STOPPED          │                           │
    │                           │                           │
```

---

## Summary

**Current State**: 3-phase race condition
1. Monitor thread continues processing buffer after stop signal
2. Events queued to storage during shutdown
3. Storage worker never receives stop signal, runs indefinitely

**Fix Priority**:
1. ✅ CRITICAL: Add intra-loop stop check (1 line change)
2. ✅ CRITICAL: Guard storage queue during stop (5 line change)
3. ✅ HIGH: Implement storage worker shutdown (new method)
4. ⚠️ MEDIUM: Remove callbacks before stop (refactor)
5. 💡 LOW: Increase timeouts (config change)

**Expected Result After Fixes**:
- Stop latency: < 500ms (currently > 5s)
- Zero events queued after stop (currently 100-500)
- Clean thread shutdown (currently hangs)
- No memory leaks (currently possible)
