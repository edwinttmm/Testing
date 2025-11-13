# HIL System Dependency Graph & Critical Analysis

**Generated**: 2025-10-31
**Purpose**: Map all dependencies, failure chains, and critical paths for the 6 HIL system fixes

---

## 🎯 Executive Summary

This document maps the complete dependency structure of the HIL validation system, identifying:
- **6 Critical Fixes** and their interdependencies
- **Single Points of Failure** (SPOFs)
- **Domino Effect Chains** (what breaks when X fails)
- **Startup Order Requirements**
- **Failure Recovery Procedures**

**Key Findings**:
- 3 Single Points of Failure identified
- 4 Critical startup dependencies that must initialize in order
- 2 Race conditions in multi-video sequences
- Maximum blast radius: 5 components from orchestrator failure

---

## 📊 Visual Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          HARDWARE LAYER                                  │
│  ┌──────────────┐                                                        │
│  │ LabJack T7   │◄──────────────────────┐                               │
│  │ Hardware     │                        │                               │
│  └──────┬───────┘                        │                               │
│         │                                 │                               │
└─────────┼─────────────────────────────────┼───────────────────────────────┘
          │                                 │
          │ FIX #1: Raw LabJack Integration │
          │ (Voltage detection threshold)   │
          ▼                                 │
┌─────────────────────────────────────────────────────────────────────────┐
│                      DETECTION LAYER                                     │
│  ┌────────────────────────────┐                                         │
│  │ DedicatedLabJackMonitor    │◄────────┐                               │
│  │ - Start monitoring FIRST   │         │                               │
│  │ - Detect 3.3V threshold    │         │                               │
│  └────────┬────────────────┬──┘         │                               │
│           │                │            │                               │
│           │ FIX #2        │            │                               │
│           │ Timing Sync   │            │                               │
│           ▼                ▼            │                               │
│  ┌──────────────────┐  ┌───────────────────┐                           │
│  │ VideoTimingService│  │ PrecisionTiming  │                           │
│  │ - Video sync     │  │ - Sub-ms timing   │                           │
│  └─────────┬────────┘  └──────────────────┘                           │
└────────────┼───────────────────────────────────────────────────────────┘
             │
             │ FIX #3: Database Storage
             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       DATABASE LAYER                                     │
│  ┌──────────────────────────────────────────────┐                       │
│  │ detection_events table                        │                       │
│  │ - Store voltage, channel, latency            │                       │
│  │ - video_id, sequence_id linking              │                       │
│  └────────┬─────────────────────────────────────┘                       │
│           │                                                              │
│           │ FIX #4 + #5: Multi-Video & Ground Truth                     │
│           ▼                                                              │
│  ┌──────────────────────┐      ┌──────────────────────┐                │
│  │ VideoTestSequence    │◄─────┤ SequenceVideoResult  │                │
│  │ - Sequence metadata  │      │ - Per-video results  │                │
│  └──────┬───────────────┘      └──────┬───────────────┘                │
│         │                              │                                 │
└─────────┼──────────────────────────────┼─────────────────────────────────┘
          │                              │
          │ FIX #6: Session Completion   │
          ▼                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATION LAYER                                  │
│  ┌──────────────────────────────────────────────────┐                   │
│  │ VideoSequenceOrchestrator                        │                   │
│  │ - start_sequence()                               │                   │
│  │ - notify_video_started()                         │                   │
│  │ - process_detection_event()                      │                   │
│  │ - notify_video_ended()                           │                   │
│  │ - _finalize_sequence()                           │                   │
│  └────────┬─────────────────────────────────────────┘                   │
│           │                                                              │
│           ▼                                                              │
│  ┌──────────────────────────────────────────────────┐                   │
│  │ GroundTruthMatchingService                       │                   │
│  │ - match_detections_to_ground_truth()             │                   │
│  │ - Video boundary validation (BUG #10 FIX)        │                   │
│  └────────┬─────────────────────────────────────────┘                   │
│           │                                                              │
└───────────┼──────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      WEBSOCKET LAYER                                     │
│  ┌──────────────────────────────────────────────────┐                   │
│  │ socketio_server                                  │                   │
│  │ - emit_detection_event()                         │                   │
│  │ - Real-time frontend updates                     │                   │
│  └──────────────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       FRONTEND LAYER                                     │
│  ┌──────────────────────────────────────────────────┐                   │
│  │ HILResults.tsx                                   │                   │
│  │ - Display detection events                       │                   │
│  │ - Video selector (multi-video)                   │                   │
│  │ - Ground truth visualization                     │                   │
│  └──────────────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔗 Fix Dependencies Matrix

| Fix | Depends On | Blocks | Can Fail Independently? |
|-----|-----------|--------|------------------------|
| **FIX #1**: Raw LabJack Integration | LabJack hardware | FIX #2, #3, #4, #5, #6 | ❌ No - SPOFs entire system |
| **FIX #2**: Video Timing Sync | FIX #1 | FIX #5 (ground truth matching) | ⚠️ Partial - detection works but latency wrong |
| **FIX #3**: Database Storage | FIX #1, #2 | FIX #5, #6 | ❌ No - SPOFs persistence |
| **FIX #4**: Multi-Video Orchestrator | FIX #1, #2, #3 | FIX #5 (multi-video GT) | ✅ Yes - single video fallback |
| **FIX #5**: Ground Truth Matching | FIX #1, #2, #3, #4 | FIX #6 (session completion) | ✅ Yes - detections work but no pass/fail |
| **FIX #6**: Session Completion | FIX #1, #2, #3, #5 | Frontend display | ✅ Yes - manual completion possible |

---

## 🎲 Domino Effect Matrix

### If FIX #1 (Raw LabJack Integration) Fails:

**Blast Radius**: 🔴 **CRITICAL - Entire system down**

```
LabJack Integration Failure
    ↓
✗ No voltage detection events
    ↓
✗ FIX #2: Video timing has nothing to sync
    ↓
✗ FIX #3: Database has no events to store
    ↓
✗ FIX #4: Orchestrator has no events to process
    ↓
✗ FIX #5: Ground truth matching has no detections
    ↓
✗ FIX #6: Session completes with 0 detections
    ↓
✗ Frontend displays "No detections found"
```

**Recovery**: Hardware reconnect + restart monitoring

---

### If FIX #2 (Video Timing Sync) Fails:

**Blast Radius**: 🟡 **MODERATE - Detection works but timing wrong**

```
Video Timing Sync Failure
    ↓
⚠ Detections saved with incorrect video_relative_timestamp
    ↓
✓ FIX #3: Events still stored in database
    ↓
✓ FIX #4: Orchestrator still processes events
    ↓
✗ FIX #5: Ground truth matching fails (wrong timestamps)
    ↓
✗ FIX #6: Session completes but all GT mismatches
    ↓
⚠ Frontend shows detections but 0% match rate
```

**Recovery**: Timing calibration adjustment + recompute results

---

### If FIX #3 (Database Storage) Fails:

**Blast Radius**: 🔴 **CRITICAL - No persistence**

```
Database Storage Failure
    ↓
✓ Detections still emitted via WebSocket (real-time only)
    ↓
✗ Events not persisted to detection_events table
    ↓
✗ FIX #5: Ground truth matching has no DB records
    ↓
✗ FIX #6: Session completion finds 0 stored events
    ↓
✗ Frontend refresh loses all detection data
```

**Recovery**: Database connection restore + replay detection buffer

---

### If FIX #4 (Multi-Video Orchestrator) Fails:

**Blast Radius**: 🟢 **LOW - Single video fallback works**

```
Orchestrator Failure
    ↓
⚠ Sequence not initialized properly
    ↓
✓ FIX #1: LabJack still detects voltage
    ↓
✓ FIX #2: Video timing still syncs
    ↓
✓ FIX #3: Events still stored (with NULL sequence_id)
    ↓
⚠ FIX #5: Ground truth matching works per video (no cross-video)
    ↓
✓ FIX #6: Session completion works (single video mode)
    ↓
⚠ Frontend shows detections but no video selector
```

**Recovery**: Restart test with single video

---

### If FIX #5 (Ground Truth Matching) Fails:

**Blast Radius**: 🟢 **LOW - Detections work, no validation**

```
Ground Truth Matching Failure
    ↓
✓ FIX #1-4: All detections captured and stored
    ↓
✗ No True Positive / False Positive classification
    ↓
✗ No precision / recall / F1 metrics
    ↓
⚠ FIX #6: Session completes but no pass/fail result
    ↓
⚠ Frontend shows detections but no GT comparison
```

**Recovery**: Rerun matching manually via API

---

### If FIX #6 (Session Completion) Fails:

**Blast Radius**: 🟢 **LOW - Manual completion possible**

```
Session Completion Failure
    ↓
✓ FIX #1-5: All detections captured and validated
    ↓
⚠ Session status stuck in "running"
    ↓
⚠ Detection events accessible but session incomplete
    ↓
⚠ Frontend can manually trigger completion
```

**Recovery**: Manual API call to complete session

---

## 🚨 Single Points of Failure (SPOFs)

### SPOF #1: LabJack Hardware Connection
**Component**: LabJack T7 USB device
**Impact**: Entire system inoperable
**Mitigation**:
- Hardware health checks every 10s
- Automatic reconnection on disconnect
- Fallback to mock hardware for testing

**Detection**:
```python
# Check: services/dedicated_labjack_monitor.py line 199
success = self.labjack_monitor.start_monitoring(session_id, **labjack_config)
if not success:
    # Hardware unavailable - SPOF triggered
```

**Recovery Procedure**:
1. Check USB connection
2. Restart LabJack service: `windows_labjack_bridge.restart_connection()`
3. Reinitialize monitoring session

---

### SPOF #2: Database Connection
**Component**: PostgreSQL/SQLite database
**Impact**: No persistence, session loss on crash
**Mitigation**:
- Connection pooling with auto-reconnect
- In-memory buffer for detection events
- Periodic flush to disk

**Detection**:
```python
# Check: services/dedicated_labjack_monitor.py line 690
db.add(detection_event)
db.commit()  # If this fails -> SPOF triggered
```

**Recovery Procedure**:
1. Check database connection: `db.execute(text("SELECT 1"))`
2. Reconnect: `SessionLocal()`
3. Replay buffered events from memory

---

### SPOF #3: VideoSequenceOrchestrator Initialization
**Component**: Orchestrator service singleton
**Impact**: Multi-video tests fail, single video fallback
**Mitigation**:
- Validate sequence metadata on startup
- Graceful degradation to single video mode
- Retry orchestrator initialization

**Detection**:
```python
# Check: services/video_sequence_orchestrator.py line 250
sequence = VideoTestSequence(...)
self._active_sequences[sequence_id] = sequence
if sequence_id not in self._active_sequences:
    # Orchestrator SPOF triggered
```

**Recovery Procedure**:
1. Clear sequence cache: `orchestrator._active_sequences.clear()`
2. Reinitialize: `orchestrator.start_sequence(...)`
3. Fallback to single video if fails

---

## 🔄 Critical Startup Order

### Phase 1: Hardware & Database (Parallel)
**Must complete before Phase 2**

```
[START]
   ├─> Initialize Database Connection
   │   └─> Create tables if missing
   │   └─> Verify schema version
   │
   └─> Initialize LabJack Hardware
       └─> USB connection check
       └─> Configure channels
       └─> Start voltage monitoring

[CHECKPOINT: Both must succeed or ABORT]
```

**Time**: ~2-3 seconds
**Failure Impact**: Cannot proceed to Phase 2

---

### Phase 2: Timing & Detection Services (Sequential)
**Must complete before Phase 3**

```
[After Phase 1]
   ↓
1. Initialize VideoTimingService
   └─> Load video metadata (fps, duration)
   └─> Set up timing synchronization
   ↓
2. Initialize DedicatedLabJackMonitor
   └─> Register detection callbacks
   └─> Link to timing service
   ↓
3. Start Raw LabJack Integration
   └─> Begin voltage polling
   └─> Enable detection threshold

[CHECKPOINT: Monitoring active]
```

**Time**: ~1-2 seconds
**Failure Impact**: Detections not captured

---

### Phase 3: Video Playback & Orchestration (Sequential)
**Must complete before testing**

```
[After Phase 2]
   ↓
1. Initialize VideoSequenceOrchestrator
   └─> Load sequence metadata
   └─> Validate video IDs
   └─> Create sequence object
   ↓
2. Start Video Timing (AFTER LabJack monitoring)
   └─> Record video_start_time
   └─> Begin frame synchronization
   ↓
3. Notify Orchestrator: notify_video_started()
   └─> Update sequence state
   └─> Link detections to video

[CHECKPOINT: Ready for test execution]
```

**Time**: ~500ms per video
**Failure Impact**: Timing desync, wrong video associations

---

### Phase 4: Session Management (Background)
**Runs concurrently during test**

```
[During Test Execution]
   ↓
1. Process Detection Events
   └─> Convert timestamps
   └─> Store in database
   └─> Emit WebSocket events
   ↓
2. Monitor Video Transitions
   └─> Detect video end
   └─> Evaluate per-video results
   └─> Transition to next video
   ↓
3. Session Completion (on last video end)
   └─> Finalize sequence
   └─> Run ground truth matching
   └─> Calculate metrics
   └─> Mark session complete

[END]
```

**Time**: Duration of test (video length)
**Failure Impact**: Incomplete session, missing results

---

## ⚠️ Race Conditions & Timing Issues

### Race Condition #1: Video Start vs First Detection
**Problem**: First detection may arrive BEFORE video timing service records `video_start_time`

**Location**: `services/dedicated_labjack_monitor.py` line 243
```python
# CRITICAL: Start LabJack monitoring BEFORE video timing
success = self.labjack_monitor.start_monitoring(session_id, **labjack_config)
# ... then start video timing
video_start_time = self.video_timing_service.start_video_timing(...)
```

**Current Fix**: LabJack monitoring starts FIRST (line 199), then video timing starts (line 243)

**Validation**:
```python
# Check that video_start_time exists before processing detections
if metadata.video_start_time is None:
    logger.warning(f"Video {video_id} has no start time recorded")
    return None
```

---

### Race Condition #2: Multi-Video Transition Gap
**Problem**: Detection event during video transition may be assigned to wrong video

**Location**: `services/video_sequence_orchestrator.py` line 737
```python
def _determine_video_for_detection(self, sequence, detection_timestamp):
    # Check if detection falls within video time range
    if metadata.video_start_time <= detection_timestamp <= video_end:
        return video_id
```

**Current Fix**: Video boundary validation with 1-second buffer (line 445)

**Mitigation**:
```python
buffer_seconds = 1.0  # Allow 1 second buffer
if video_relative_timestamp < -buffer_seconds:
    logger.warning("Detection timestamp outside video duration")
```

---

## 📡 WebSocket Dependency Chain

### Real-Time Detection Flow

```
LabJack Hardware Trigger
    ↓
DedicatedLabJackMonitor._handle_detection_with_video_sync()
    ↓
_schedule_websocket_emission(hil_event, session_id)
    ↓ [threading.Thread]
_emit_detection_event_sync(hil_event, session_id)
    ↓ [asyncio.run_until_complete]
socketio_server.emit_detection_event(detection_data, session_id)
    ↓ [Socket.IO]
Frontend HILResults.tsx receives event
    ↓
Updates detection table in real-time
```

**Critical Path Time**: <50ms from hardware trigger to frontend update

**Failure Points**:
1. Thread creation failure → Detection not emitted (logged but continues)
2. AsyncIO loop conflict → Detection stored in DB but not real-time
3. Socket.IO disconnected → Detection stored in DB, displayed on refresh

---

## 🛡️ Failure Recovery Procedures

### Procedure 1: Hardware Disconnect Recovery
**Trigger**: LabJack USB disconnect detected

```bash
# Detection
tail -f logs/backend.log | grep "LabJack connection lost"

# Recovery
1. Check USB connection
2. Restart monitoring:
   curl -X POST http://localhost:8000/api/labjack/restart
3. Reinitialize active sessions:
   curl -X POST http://localhost:8000/api/sessions/{session_id}/restart-monitoring
```

---

### Procedure 2: Database Lock Recovery
**Trigger**: SQLAlchemy OperationalError "database is locked"

```bash
# Detection
tail -f logs/backend.log | grep "database is locked"

# Recovery
1. Check for long-running queries:
   sqlite3 dev_database.db ".timeout 5000"
2. Kill blocking transactions:
   pkill -f "python.*main.py"
3. Restart backend with connection pooling:
   python main.py --pool-size 10
```

---

### Procedure 3: Timing Desync Recovery
**Trigger**: Ground truth matching shows 0% match rate but detections exist

```bash
# Detection
curl http://localhost:8000/api/sessions/{session_id}/results | jq '.metrics.precision'
# Output: 0.0 (but total_detections > 0)

# Recovery
1. Check timing calibration:
   curl http://localhost:8000/api/debug/timing-status/{session_id}
2. Recompute with calibration:
   curl -X POST http://localhost:8000/api/sessions/{session_id}/recompute-latency \
        -d '{"calibration_offset_ms": 166}'
3. Re-run ground truth matching:
   curl -X POST http://localhost:8000/api/ground-truth/match/{session_id}
```

---

### Procedure 4: Orphaned Session Recovery
**Trigger**: Session stuck in "running" status after test completion

```bash
# Detection
curl http://localhost:8000/api/sessions | jq '.[] | select(.status=="running")'

# Recovery
1. Force session completion:
   curl -X POST http://localhost:8000/api/sessions/{session_id}/force-complete
2. Run ground truth matching:
   curl -X POST http://localhost:8000/api/ground-truth/match/{session_id}
3. Verify detection count:
   curl http://localhost:8000/api/sessions/{session_id}/detections/count
```

---

## 🔍 Dependency Validation Checklist

Use this checklist before deploying or after system modifications:

### Hardware Layer
- [ ] LabJack T7 connected and recognized
- [ ] Voltage threshold configured (3.3V)
- [ ] Channels configured correctly (AIN0, AIN1, etc.)
- [ ] Bridge service running (if WSL environment)

### Detection Layer
- [ ] `DedicatedLabJackMonitor` initializes successfully
- [ ] `VideoTimingService` loads video metadata
- [ ] Detection callbacks registered
- [ ] Monitoring starts BEFORE video timing

### Database Layer
- [ ] Database connection pool initialized
- [ ] All tables exist (run migrations)
- [ ] Indexes created for performance
- [ ] No existing locks or deadlocks

### Orchestration Layer
- [ ] `VideoSequenceOrchestrator` singleton created
- [ ] Sequence metadata loaded from database
- [ ] Video IDs validated
- [ ] Ground truth matching service available

### WebSocket Layer
- [ ] Socket.IO server started
- [ ] CORS origins configured
- [ ] Frontend connected successfully
- [ ] Heartbeat active

### Frontend Layer
- [ ] HILResults.tsx mounted
- [ ] WebSocket connection established
- [ ] Video selector visible (multi-video)
- [ ] Detection table rendering

---

## 🎯 Critical Metrics for Monitoring

Monitor these metrics to detect dependency failures early:

| Metric | Normal Range | Alert Threshold | Indicates Failure Of |
|--------|-------------|-----------------|---------------------|
| Detection Event Rate | 1-10 events/sec | 0 events for 5s | FIX #1 (LabJack) |
| Video Timing Sync Quality | 95-100% | <80% | FIX #2 (Timing) |
| Database Write Latency | <5ms | >100ms | FIX #3 (Database) |
| Sequence Initialization Time | <500ms | >2s | FIX #4 (Orchestrator) |
| Ground Truth Match Rate | 70-100% | <50% | FIX #5 (GT Matching) |
| Session Completion Time | <1s after video | >10s | FIX #6 (Completion) |

**Dashboard Query**:
```sql
SELECT
    COUNT(*) as detection_count,
    AVG(actual_latency_ms) as avg_latency,
    AVG(CASE WHEN timing_sync_quality = 'high' THEN 1 ELSE 0 END) * 100 as sync_quality_pct
FROM detection_events
WHERE test_session_id = ?
  AND created_at > datetime('now', '-5 minutes');
```

---

## 📝 Conclusion

**Key Takeaways**:

1. **FIX #1 (LabJack Integration)** is the root dependency - everything else cascades from it
2. **FIX #3 (Database Storage)** is the persistence layer - without it, detections are ephemeral
3. **3 SPOFs identified**: Hardware, Database, Orchestrator initialization
4. **Startup order is critical**: LabJack monitoring MUST start before video timing
5. **2 Race conditions mitigated**: First detection timing, multi-video transitions
6. **Recovery procedures exist** for all critical failure modes

**Recommended Actions**:
- Implement hardware health checks every 10s
- Add database connection retry logic with exponential backoff
- Create system startup validation script (run all checks in order)
- Add orchestrator fallback to single-video mode
- Implement detection event replay from memory buffer

---

**Document Version**: 1.0
**Last Updated**: 2025-10-31
**Maintainer**: HIL System Architecture Team
