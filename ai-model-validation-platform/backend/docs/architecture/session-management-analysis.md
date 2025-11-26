# Session Management Architecture Analysis - Duplicate Session Root Cause

**Date:** 2025-11-25
**Author:** System Architecture Designer
**Status:** Root Cause Identified
**Priority:** HIGH - System Correctness Issue

## Executive Summary

The HIL testing system is creating **TWO concurrent sessions** for a single test execution, causing:
- Duplicate detection processing (2 callbacks for same video)
- Resource contention on shared LabJack hardware
- Data integrity issues (detections split between sessions)
- Timing conflicts (stream mode vs polling mode simultaneously)

### Key Evidence from Logs

```
Session 1: 90fb1ae4-152c-44cb-b98d-c5ff2a4ec50e (stream mode)
Session 2: 028afcb1-c0c9-458d-9979-a0ad199e2906 (polling mode, sequence test)
Both monitoring: Video 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
Detection callbacks: 2 (should be 1)
Video start times: 1764082088.275 vs 1764082088.494 (219ms drift)
```

## Root Cause Analysis

### 1. Session Creation Flow

#### Path 1: API-Created Session (Correct)
```
/api/video-sequences/start
└─> video_sequence_testing.py:start_video_sequence()
    ├─> Creates TestSession in database
    │   ├─> session_id = uuid4() # First UUID generated
    │   ├─> sequence_id = uuid4()
    │   └─> test_session.id = test_session_id
    │
    ├─> Commits to database
    │
    └─> Calls start_hil_monitoring(video_timing_config)
        └─> video_timing_config['test_session_id'] = test_session_id ✅
```

**File:** `/backend/routers/video_sequence_testing.py:546-700`

```python
# LINE 547-548: First session created
sequence_id = str(uuid.uuid4())
test_session_id = str(uuid.uuid4())  # Session 1: 028afcb1...

# LINE 552-571: TestSession object created
test_session = TestSession(
    id=test_session_id,
    project_id=request.project_id,
    video_id=request.video_ids[0],
    name=request.test_name or f"Video Sequence Test - {timestamp}",
    status="running",
    sequence_id=sequence_id,
    # ... other fields
)

# LINE 656: Committed to database
db.commit()

# LINE 673-700: Config prepared with PRIMARY session ID
video_timing_config = {
    'test_session_id': test_session_id,  # ✅ Correct
    'video_id': request.video_ids[0],
    'video_ids': request.video_ids,
    'sequence_id': sequence_id,
    # ... other config
}

# LINE 698: Monitoring started
success = await start_hil_monitoring(video_timing_config)
```

#### Path 2: Monitor-Created Session (BUG - SHOULD NOT HAPPEN)

The bug occurs in `dedicated_labjack_monitor.py` when the monitor **CREATES A SECOND SESSION** despite receiving `test_session_id` in config.

**File:** `/backend/services/dedicated_labjack_monitor.py:547-550`

```python
# LINE 547-550: PROBLEM - Creates NEW session dict in memory
session_init_time = datetime.now(timezone.utc)
timing_ready_event = threading.Event()
logger.info(f"📝 Initializing session {session_id} at {session_init_time}")

# LINE 552-564: SECOND session entry created
self.active_sessions[session_id] = {  # ⚠️ Uses parameter session_id
    'video_timing_config': video_timing_config,
    'labjack_config': labjack_config,
    'started_at': session_init_time,  # Different timestamp!
    'video_start_time': None,
    'detection_callback': None,
    # ... other fields
}
```

### 2. The Critical Bug

**Location:** `dedicated_labjack_monitor.py:450-464` - `start_monitoring_with_video_sync()`

```python
async def start_monitoring_with_video_sync(
    self,
    session_id: str,  # ⚠️ This parameter ACCEPTS a session_id
    video_timing_config: Dict[str, Any],
    force_polling: bool = False
) -> bool:
    """Start LabJack monitoring with video timing synchronization."""
```

**The wrapper correctly extracts the session ID:**

**File:** `dedicated_labjack_monitor.py:2525-2552`

```python
async def start_hil_monitoring(video_timing_config: Dict[str, Any]) -> bool:
    """
    ✅ FIX-2: Extract primary session ID from config instead of parameter
    This prevents session ID duplication
    """
    # ✅ Correctly extracts PRIMARY session ID
    primary_session_id = video_timing_config.get('test_session_id')

    if not primary_session_id:
        raise ValueError("test_session_id must be provided in video_timing_config")

    logger.info(f"✅ FIX-2: Using PRIMARY session ID: {primary_session_id}")

    monitor = get_dedicated_labjack_monitor()
    # ✅ Passes correct session_id
    return await monitor.start_monitoring_with_video_sync(
        primary_session_id,  # ✅ This should be the ONLY session
        video_timing_config
    )
```

### 3. Why Two Sessions Are Created

**Hypothesis:** There's a **SECOND call path** to `start_monitoring_with_video_sync()` that bypasses the wrapper and creates a new session ID.

#### Potential Call Paths:

1. **Direct Monitor Calls** - Check for:
   - WebSocket handlers calling monitor directly
   - Frontend lifecycle events triggering monitoring
   - Background threads re-initializing monitoring

2. **Video Lifecycle Events** - Check:
   - `/video-started` endpoint calling monitor
   - `/video-ended` endpoint calling monitor
   - Video playlist transitions triggering new sessions

3. **Bridge Initialization** - Check:
   ```python
   # LINE 580-588 in start_monitoring_with_video_sync
   def start_bridge_async():
       try:
           from services.windows_labjack_bridge import windows_labjack_bridge
           windows_labjack_bridge.start_session_monitoring(session_id)
   ```
   Does the bridge create its own session?

### 4. Evidence of Dual Session Behavior

From logs:
```
[Session Creation Timeline]
T+0.000s: API creates session 028afcb1... (polling mode)
T+0.100s: start_hil_monitoring called with test_session_id=028afcb1...
T+0.150s: Monitor creates active_sessions[028afcb1...] entry
T+0.???s: UNKNOWN TRIGGER creates session 90fb1ae4... (stream mode)
T+0.494s: Second video_start_time set for 90fb1ae4...

[Concurrent State]
active_sessions = {
    '028afcb1...': {  # Polling mode, sequence test
        'video_start_time': 1764082088.275,
        'labjack_config': {'use_stream_mode': False}
    },
    '90fb1ae4...': {  # Stream mode, mystery session
        'video_start_time': 1764082088.494,
        'labjack_config': {'use_stream_mode': True}
    }
}

[Callback Registration]
Detection callbacks: 2 ⚠️
Both bound to same video: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
```

## Architecture Design Issues

### 1. Session Lifecycle Management

**Current Design (Problematic):**
```
┌─────────────────────────────────────────────────────────────┐
│  API Layer (video_sequence_testing.py)                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Creates TestSession in Database                      │   │
│  │  - session_id = uuid4()                              │   │
│  │  - status = "running"                                │   │
│  └────────────────┬────────────────────────────────────┘   │
│                   │                                          │
│                   ▼                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Calls start_hil_monitoring(config)                   │   │
│  │  config['test_session_id'] = session_id              │   │
│  └────────────────┬────────────────────────────────────┘   │
└───────────────────┼──────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Monitor Layer (dedicated_labjack_monitor.py)               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ start_hil_monitoring(config) [Wrapper]               │   │
│  │  - Extracts session_id from config ✅                 │   │
│  │  - Calls monitor.start_monitoring_with_video_sync()  │   │
│  └────────────────┬────────────────────────────────────┘   │
│                   │                                          │
│                   ▼                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ start_monitoring_with_video_sync(session_id, config) │   │
│  │  - Creates active_sessions[session_id] dict ✅        │   │
│  │  - Adds detection callback                           │   │
│  └────────────────┬────────────────────────────────────┘   │
│                   │                                          │
│                   ▼                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ❌ MYSTERY: Second call creates session 90fb1ae4...  │   │
│  │  - Different config (stream mode vs polling)         │   │
│  │  - Adds second detection callback                    │   │
│  │  - Causes duplicate processing                       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Desired Design:**
```
┌─────────────────────────────────────────────────────────────┐
│  API Layer                                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Creates SINGLE TestSession                           │   │
│  │  - session_id (authoritative source)                 │   │
│  └────────────────┬────────────────────────────────────┘   │
└───────────────────┼──────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Monitor Layer                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Session Registry (SINGLETON)                         │   │
│  │  - Guards against duplicate sessions                 │   │
│  │  - Validates session_id exists in database          │   │
│  │  - ONE callback per session                          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2. LabJack Hardware Contention

**Problem:** Two sessions trying to configure hardware differently:

| Session | Mode | Sample Rate | Threshold | Debounce |
|---------|------|-------------|-----------|----------|
| 028afcb1... | Polling | 200 Hz | 0.5V | 0ms |
| 90fb1ae4... | Stream | 500 Hz | 0.5V | 0ms |

**Result:**
- Hardware alternates between stream/poll modes
- Detection timing becomes unreliable
- Race conditions in voltage readings

### 3. Detection Callback Architecture

**Current (Buggy):**
```python
# Session 1 callback
callback_1 = lambda event: self._handle_detection_with_video_sync(
    '028afcb1...', event
)
self.labjack_monitor.add_detection_callback(callback_1)

# Session 2 callback (DUPLICATE)
callback_2 = lambda event: self._handle_detection_with_video_sync(
    '90fb1ae4...', event
)
self.labjack_monitor.add_detection_callback(callback_2)

# Result: BOTH callbacks fire for EVERY detection
# Each detection processed twice, stored twice, reported twice
```

**Should be:**
```python
# SINGLE callback per video
callback = lambda event: self._handle_detection_with_video_sync(
    'primary_session_id', event
)
self.labjack_monitor.add_detection_callback(callback)

# Validation: Only ONE callback per video/session pair
assert len(self.detection_callbacks) == 1
```

## Recommended Solutions

### Solution 1: Session Registry Pattern (Preferred)

Implement a centralized session registry that prevents duplicate sessions:

```python
class SessionRegistry:
    """Singleton registry preventing duplicate sessions"""

    def __init__(self):
        self._sessions: Dict[str, SessionInfo] = {}
        self._lock = threading.Lock()
        self._video_to_session: Dict[str, str] = {}  # video_id -> session_id

    def register_session(
        self,
        session_id: str,
        video_id: str,
        config: Dict[str, Any]
    ) -> bool:
        """Register a session. Returns False if duplicate detected."""
        with self._lock:
            # Check if session already exists
            if session_id in self._sessions:
                logger.warning(
                    f"⚠️ Session {session_id} already registered. "
                    f"Ignoring duplicate registration."
                )
                return False

            # Check if video already has active session
            if video_id in self._video_to_session:
                existing_session = self._video_to_session[video_id]
                logger.error(
                    f"❌ Video {video_id} already has active session "
                    f"{existing_session}. Cannot create duplicate session "
                    f"{session_id}."
                )
                raise DuplicateSessionError(
                    f"Video {video_id} already monitored by session "
                    f"{existing_session}"
                )

            # Register new session
            self._sessions[session_id] = SessionInfo(
                session_id=session_id,
                video_id=video_id,
                config=config,
                created_at=datetime.now(timezone.utc)
            )
            self._video_to_session[video_id] = session_id

            logger.info(f"✅ Registered session {session_id} for video {video_id}")
            return True

    def unregister_session(self, session_id: str):
        """Remove session from registry"""
        with self._lock:
            if session_id in self._sessions:
                session_info = self._sessions[session_id]
                video_id = session_info.video_id

                del self._sessions[session_id]
                if video_id in self._video_to_session:
                    del self._video_to_session[video_id]

                logger.info(f"✅ Unregistered session {session_id}")
```

**Integration:**
```python
# In DedicatedLabJackMonitor.__init__()
self.session_registry = SessionRegistry()

# In start_monitoring_with_video_sync()
video_id = video_timing_config.get('video_id')
try:
    self.session_registry.register_session(
        session_id, video_id, video_timing_config
    )
except DuplicateSessionError as e:
    logger.error(f"Cannot start monitoring: {e}")
    return False
```

### Solution 2: Database-Backed Session Validation

Validate sessions against database before creating monitor entries:

```python
async def start_monitoring_with_video_sync(
    self,
    session_id: str,
    video_timing_config: Dict[str, Any],
    force_polling: bool = False
) -> bool:
    """Start monitoring with database validation"""

    # STEP 1: Validate session exists in database
    db = SessionLocal()
    try:
        session_db = db.query(TestSession).filter(
            TestSession.id == session_id
        ).first()

        if not session_db:
            logger.error(
                f"❌ Session {session_id} not found in database. "
                f"Cannot start monitoring without valid database session."
            )
            return False

        if session_db.status != "running":
            logger.warning(
                f"⚠️ Session {session_id} has status '{session_db.status}'. "
                f"Expected 'running' status."
            )

        logger.info(
            f"✅ Validated session {session_id} in database "
            f"(project: {session_db.project_id}, "
            f"video: {session_db.video_id})"
        )
    finally:
        db.close()

    # STEP 2: Check for duplicate monitoring
    with self.lock:
        if session_id in self.active_sessions:
            logger.warning(
                f"⚠️ Session {session_id} already has active monitoring. "
                f"Refusing to create duplicate."
            )
            return False  # Already monitoring, don't create duplicate

        # STEP 3: Initialize monitoring (continues as before)
        # ...
```

### Solution 3: Idempotent Session Creation

Make session creation idempotent - repeated calls with same ID are no-ops:

```python
def _ensure_session_initialized(
    self,
    session_id: str,
    video_timing_config: Dict[str, Any]
) -> bool:
    """Ensure session is initialized exactly once (idempotent)"""

    with self.lock:
        if session_id in self.active_sessions:
            logger.info(
                f"ℹ️ Session {session_id} already initialized. "
                f"Reusing existing session."
            )
            return True  # Already initialized, success

        # Initialize new session
        self.active_sessions[session_id] = {
            'video_timing_config': video_timing_config,
            'started_at': datetime.now(timezone.utc),
            'detection_callback': None,
            # ... other fields
        }

        logger.info(f"✅ Initialized NEW session {session_id}")
        return True
```

### Solution 4: Find and Block Duplicate Call Path

**Investigation needed:**

1. **Search for direct monitor calls:**
   ```bash
   grep -r "start_monitoring_with_video_sync" backend/ \
     | grep -v "def start_monitoring_with_video_sync"
   ```

2. **Check video lifecycle handlers:**
   ```bash
   grep -r "video.started\|video_started\|on_video_start" backend/
   ```

3. **Check WebSocket handlers:**
   ```bash
   grep -r "websocket.*session\|ws.*session" backend/
   ```

4. **Check background workers:**
   ```bash
   grep -r "threading.Thread\|asyncio.create_task" backend/ \
     | grep -i monitor
   ```

## Testing Strategy

### Test 1: Session Creation Uniqueness
```python
def test_single_session_per_video():
    """Verify only one session created per video"""

    # Start video sequence
    response = client.post("/api/video-sequences/start", json={
        "project_id": project_id,
        "video_ids": [video_id],
        "enable_labjack_monitoring": True
    })

    session_id = response.json()["test_session_id"]

    # Wait for monitoring to initialize
    await asyncio.sleep(1.0)

    # Get monitor state
    monitor = get_dedicated_labjack_monitor()
    active_sessions = monitor.active_sessions

    # ASSERT: Only ONE session exists
    assert len(active_sessions) == 1, \
        f"Expected 1 session, found {len(active_sessions)}"

    # ASSERT: Session ID matches API-created session
    assert session_id in active_sessions, \
        f"Session {session_id} not found in active sessions"

    # ASSERT: Only ONE detection callback registered
    callback_count = len(monitor.labjack_monitor.detection_callbacks)
    assert callback_count == 1, \
        f"Expected 1 detection callback, found {callback_count}"
```

### Test 2: Detection Processing Once
```python
def test_detection_processed_once():
    """Verify detections processed exactly once"""

    # Trigger detection
    simulate_voltage_spike(channel='AIN0', voltage=3.3)

    await asyncio.sleep(0.5)

    # Query database
    db = SessionLocal()
    detections = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id
    ).all()
    db.close()

    # ASSERT: Exactly ONE detection stored
    assert len(detections) == 1, \
        f"Expected 1 detection, found {len(detections)}"
```

### Test 3: Hardware Configuration Consistency
```python
def test_hardware_mode_consistency():
    """Verify hardware stays in one mode"""

    # Start monitoring
    await start_hil_monitoring(config)

    # Record initial mode
    monitor = get_dedicated_labjack_monitor()
    initial_mode = monitor.labjack_monitor.current_mode

    # Wait and check mode hasn't changed
    await asyncio.sleep(2.0)
    final_mode = monitor.labjack_monitor.current_mode

    assert initial_mode == final_mode, \
        f"Hardware mode changed: {initial_mode} -> {final_mode}"
```

## Monitoring and Observability

### Metrics to Track

1. **Active Session Count**
   ```python
   gauge("hil.active_sessions.count", len(monitor.active_sessions))
   ```

2. **Detection Callback Count**
   ```python
   gauge("hil.detection_callbacks.count",
         len(monitor.labjack_monitor.detection_callbacks))
   ```

3. **Duplicate Session Attempts**
   ```python
   counter("hil.duplicate_session.attempts")
   counter("hil.duplicate_session.blocked")
   ```

4. **Hardware Mode Transitions**
   ```python
   counter("hil.hardware_mode.transitions", tags=["from", "to"])
   ```

### Alert Conditions

```yaml
alerts:
  - name: MultipleSessions
    condition: hil.active_sessions.count > 1
    severity: critical
    message: "Multiple sessions detected for single test"

  - name: MultipleCallbacks
    condition: hil.detection_callbacks.count > 1
    severity: critical
    message: "Multiple detection callbacks registered"

  - name: HardwareModeFlapping
    condition: rate(hil.hardware_mode.transitions) > 0.1
    severity: warning
    message: "Hardware mode changing frequently"
```

## Implementation Priority

1. **IMMEDIATE (Same Day):**
   - Add session existence check in `start_monitoring_with_video_sync()`
   - Add duplicate detection logging
   - Find second call path creating 90fb1ae4 session

2. **SHORT TERM (1-2 Days):**
   - Implement SessionRegistry pattern
   - Add database validation
   - Make session creation idempotent

3. **MEDIUM TERM (1 Week):**
   - Add comprehensive testing suite
   - Implement monitoring metrics
   - Add alerting for duplicate sessions

4. **LONG TERM (2-4 Weeks):**
   - Refactor session lifecycle management
   - Implement session state machine
   - Add session health checks

## Conclusion

The duplicate session issue is a **critical architectural flaw** that compromises:
- Data integrity (duplicate detections)
- Hardware reliability (mode conflicts)
- System correctness (timing inconsistencies)

**The root cause** is that two code paths are calling `start_monitoring_with_video_sync()` with different session IDs for the same video. The **immediate fix** is to find and block the second call path. The **long-term solution** is implementing proper session lifecycle management with a registry pattern.

**Next Steps:**
1. Search codebase for direct monitor calls
2. Add session existence guards
3. Implement SessionRegistry pattern
4. Add comprehensive testing

---

**Files Analyzed:**
- `/backend/routers/video_sequence_testing.py` (lines 546-700)
- `/backend/services/dedicated_labjack_monitor.py` (lines 450-2570)
- `/backend/services/session_management_service.py` (complete)
- `/backend/routers/test_sessions.py` (partial)

**Cross-References:**
- [HIL Timing Fix Implementation](../hil_timing_fix_implementation.md)
- [Database Schema Design](../database/schema-design.md)
- [Session Completion Service](../src/services/session_completion_service.py)
