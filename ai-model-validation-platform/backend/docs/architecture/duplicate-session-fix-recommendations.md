# Duplicate Session Fix Recommendations

**Date:** 2025-11-25
**Priority:** CRITICAL
**Impact:** Data Integrity, Hardware Reliability, System Correctness

## Problem Summary

Two concurrent sessions are being created for a single test execution:
- **Session 1 (Primary):** `028afcb1-c0c9-458d-9979-a0ad199e2906` - Created by API (polling mode)
- **Session 2 (Phantom):** `90fb1ae4-152c-44cb-b98d-c5ff2a4ec50e` - Created by unknown path (stream mode)

**Symptoms:**
- 2 detection callbacks registered for same video
- Duplicate detection processing
- LabJack hardware mode conflicts (stream vs polling)
- Data split between two sessions
- 219ms timing drift between sessions

## Investigation Status

### ✅ Confirmed Working Code Paths

1. **API Session Creation** (`routers/video_sequence_testing.py:546-700`)
   - Creates `TestSession` in database
   - Passes `test_session_id` in `video_timing_config`
   - Calls `start_hil_monitoring(config)`
   - **Status:** Working correctly

2. **Monitor Wrapper** (`services/dedicated_labjack_monitor.py:2525-2552`)
   - Extracts `test_session_id` from config
   - Validates session ID presence
   - Calls `start_monitoring_with_video_sync(primary_session_id, config)`
   - **Status:** Working correctly

3. **Video Lifecycle Events** (`routers/video_sequences.py:120-214`)
   - `/video-started` endpoint updates timing
   - Invalidates detection cache
   - Does NOT create new sessions
   - **Status:** Not the culprit

### ❓ Unknown Call Path (Needs Investigation)

**The phantom session `90fb1ae4...` is being created by an unidentified code path.**

### Potential Sources

1. **Background Workers or Threads**
   - Health check loops
   - Automatic session recovery
   - Watchdog processes

2. **WebSocket Handlers** (Not yet analyzed)
   - `backend/src/websocket_connection_manager.py`
   - `backend/src/websocket_orchestration.py`
   - Real-time event handlers

3. **LabJack Service Manager** (`src/services/labjack_service_manager.py`)
   - Has method `start_monitoring_for_session()`
   - May create independent monitoring instances
   - **Needs investigation**

4. **Bridge Services**
   - `services/windows_labjack_bridge.py`
   - Called asynchronously: `windows_labjack_bridge.start_session_monitoring(session_id)`
   - May create duplicate sessions

5. **Lifecycle Orchestrator** (`src/services/video_lifecycle_orchestrator.py`)
   - Has method `_start_labjack_monitoring()`
   - May be triggered independently

## Immediate Action Items

### 1. Add Session Registration Guard (HIGH PRIORITY)

Implement in `dedicated_labjack_monitor.py:start_monitoring_with_video_sync()`:

```python
async def start_monitoring_with_video_sync(
    self,
    session_id: str,
    video_timing_config: Dict[str, Any],
    force_polling: bool = False
) -> bool:
    """Start monitoring with duplicate prevention"""

    with self.lock:
        # GUARD 1: Check if session already exists
        if session_id in self.active_sessions:
            logger.warning(
                f"⚠️ Session {session_id} already has active monitoring. "
                f"Refusing to create duplicate. "
                f"Existing session started at: "
                f"{self.active_sessions[session_id]['started_at']}"
            )
            return False  # Idempotent: already initialized

        # GUARD 2: Validate session exists in database
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

            logger.info(
                f"✅ Validated session {session_id} in database "
                f"(project: {session_db.project_id}, video: {session_db.video_id})"
            )
        finally:
            db.close()

        # GUARD 3: Check video isn't already being monitored
        video_id = video_timing_config.get('video_id')
        for sid, session_data in self.active_sessions.items():
            if session_data.get('video_timing_config', {}).get('video_id') == video_id:
                logger.error(
                    f"❌ Video {video_id} is already being monitored by "
                    f"session {sid}. Cannot monitor same video with "
                    f"multiple sessions."
                )
                raise DuplicateSessionError(
                    f"Video {video_id} already monitored by session {sid}"
                )

        # Continue with initialization...
        logger.info(f"✅ All guards passed. Initializing session {session_id}")
        # ... existing code ...
```

**Files to modify:**
- `/backend/services/dedicated_labjack_monitor.py` (lines 450-470)

### 2. Add Comprehensive Logging (IMMEDIATE)

Add stack trace logging to identify call sources:

```python
import traceback

async def start_monitoring_with_video_sync(
    self,
    session_id: str,
    video_timing_config: Dict[str, Any],
    force_polling: bool = False
) -> bool:
    """Start monitoring with call source tracking"""

    # Log call source
    call_stack = traceback.format_stack()
    logger.info(
        f"📞 start_monitoring_with_video_sync() called for session {session_id}\n"
        f"Call stack (last 5 frames):\n" +
        "".join(call_stack[-5:])
    )

    # Log config details
    logger.info(
        f"📋 Config: video_id={video_timing_config.get('video_id')}, "
        f"sequence_id={video_timing_config.get('sequence_id')}, "
        f"use_stream_mode={video_timing_config.get('use_stream_mode', False)}"
    )

    # ... rest of function ...
```

**Deploy this immediately** to capture the source of the phantom session.

### 3. Create Session Registry (SHORT TERM)

Implement centralized session management:

```python
# File: backend/services/session_registry.py

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional
import threading
import logging

logger = logging.getLogger(__name__)

@dataclass
class SessionInfo:
    """Active session information"""
    session_id: str
    video_id: str
    project_id: str
    created_at: datetime
    config: Dict
    source: str  # "api", "websocket", "worker", etc.

class SessionRegistry:
    """
    Singleton registry preventing duplicate sessions.
    Ensures one session per video at any time.
    """

    def __init__(self):
        self._sessions: Dict[str, SessionInfo] = {}
        self._video_to_session: Dict[str, str] = {}
        self._lock = threading.Lock()

    def register_session(
        self,
        session_id: str,
        video_id: str,
        project_id: str,
        config: Dict,
        source: str = "unknown"
    ) -> bool:
        """
        Register a session. Returns False if duplicate detected.

        Raises:
            DuplicateSessionError: If video already has active session
        """
        with self._lock:
            # Check 1: Session ID already exists
            if session_id in self._sessions:
                existing = self._sessions[session_id]
                logger.warning(
                    f"⚠️ Session {session_id} already registered at "
                    f"{existing.created_at} from {existing.source}"
                )
                return False

            # Check 2: Video already has session
            if video_id in self._video_to_session:
                existing_session_id = self._video_to_session[video_id]
                existing_session = self._sessions[existing_session_id]

                logger.error(
                    f"❌ Video {video_id} already monitored by session "
                    f"{existing_session_id} (created by {existing_session.source} "
                    f"at {existing_session.created_at})"
                )

                raise DuplicateSessionError(
                    f"Video {video_id} already monitored by session "
                    f"{existing_session_id}. Stop existing session before "
                    f"creating new one."
                )

            # Register new session
            session_info = SessionInfo(
                session_id=session_id,
                video_id=video_id,
                project_id=project_id,
                created_at=datetime.now(timezone.utc),
                config=config,
                source=source
            )

            self._sessions[session_id] = session_info
            self._video_to_session[video_id] = session_id

            logger.info(
                f"✅ Registered session {session_id} for video {video_id} "
                f"(source: {source})"
            )
            return True

    def unregister_session(self, session_id: str):
        """Remove session from registry"""
        with self._lock:
            if session_id not in self._sessions:
                logger.warning(f"Session {session_id} not in registry")
                return

            session_info = self._sessions[session_id]
            video_id = session_info.video_id

            # Remove mappings
            del self._sessions[session_id]
            if video_id in self._video_to_session:
                if self._video_to_session[video_id] == session_id:
                    del self._video_to_session[video_id]

            logger.info(
                f"✅ Unregistered session {session_id} for video {video_id}"
            )

    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """Get session information"""
        with self._lock:
            return self._sessions.get(session_id)

    def get_video_session(self, video_id: str) -> Optional[str]:
        """Get session ID monitoring a video"""
        with self._lock:
            return self._video_to_session.get(video_id)

    def get_all_sessions(self) -> Dict[str, SessionInfo]:
        """Get all active sessions"""
        with self._lock:
            return dict(self._sessions)

    def clear(self):
        """Clear all sessions (for testing)"""
        with self._lock:
            self._sessions.clear()
            self._video_to_session.clear()

# Global singleton
session_registry = SessionRegistry()

class DuplicateSessionError(Exception):
    """Raised when attempting to create duplicate session"""
    pass
```

**Integration:**

```python
# In dedicated_labjack_monitor.py

from services.session_registry import session_registry, DuplicateSessionError

async def start_monitoring_with_video_sync(
    self,
    session_id: str,
    video_timing_config: Dict[str, Any],
    force_polling: bool = False
) -> bool:
    """Start monitoring with registry validation"""

    video_id = video_timing_config.get('video_id')
    project_id = video_timing_config.get('project_id')

    try:
        # Register session BEFORE creating monitoring
        session_registry.register_session(
            session_id=session_id,
            video_id=video_id,
            project_id=project_id,
            config=video_timing_config,
            source="api"  # or extract from call stack
        )
    except DuplicateSessionError as e:
        logger.error(f"Cannot start monitoring: {e}")
        return False

    # ... existing monitoring setup ...

    # On success, session stays registered
    # On failure, unregister session
    try:
        # ... monitoring initialization ...
        return True
    except Exception as e:
        session_registry.unregister_session(session_id)
        raise
```

### 4. Find Phantom Session Source (URGENT)

**Investigation script:**

```python
# File: backend/scripts/find_duplicate_sessions.py

import logging
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
import time

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def monitor_session_creation():
    """Monitor for duplicate session creation"""

    monitor = get_dedicated_labjack_monitor()

    known_sessions = set()

    while True:
        current_sessions = set(monitor.active_sessions.keys())

        # Check for new sessions
        new_sessions = current_sessions - known_sessions

        if new_sessions:
            for session_id in new_sessions:
                session_data = monitor.active_sessions[session_id]
                video_id = session_data.get('video_timing_config', {}).get('video_id')

                logger.info(f"🆕 NEW SESSION DETECTED: {session_id}")
                logger.info(f"   Video: {video_id}")
                logger.info(f"   Started: {session_data.get('started_at')}")
                logger.info(f"   Config: {session_data.get('labjack_config')}")

                # Check for duplicate video monitoring
                for sid in known_sessions:
                    if sid in monitor.active_sessions:
                        existing_video = monitor.active_sessions[sid].get(
                            'video_timing_config', {}
                        ).get('video_id')

                        if existing_video == video_id:
                            logger.error(
                                f"🚨 DUPLICATE SESSION DETECTED!\n"
                                f"   New session {session_id} monitoring video {video_id}\n"
                                f"   But session {sid} already monitoring same video!\n"
                                f"   This is the bug we're looking for!"
                            )

            known_sessions.update(new_sessions)

        # Check for removed sessions
        removed_sessions = known_sessions - current_sessions
        if removed_sessions:
            for session_id in removed_sessions:
                logger.info(f"🔚 Session stopped: {session_id}")
            known_sessions -= removed_sessions

        time.sleep(0.5)

if __name__ == "__main__":
    logger.info("Starting duplicate session monitor...")
    logger.info("Run video sequence test in another terminal")
    monitor_session_creation()
```

**Run this during testing** to catch the duplicate session creation in real-time.

### 5. Add Metrics and Alerts (MEDIUM TERM)

```python
# File: backend/services/monitoring_metrics.py

from prometheus_client import Counter, Gauge, Histogram

# Session metrics
active_sessions = Gauge(
    'hil_active_sessions',
    'Number of active HIL monitoring sessions'
)

session_creation_total = Counter(
    'hil_session_creation_total',
    'Total number of session creation attempts',
    ['status', 'source']  # status: success/duplicate/error
)

duplicate_session_attempts = Counter(
    'hil_duplicate_session_attempts',
    'Number of duplicate session creation attempts blocked'
)

detection_callbacks = Gauge(
    'hil_detection_callbacks',
    'Number of registered detection callbacks'
)

# Usage in dedicated_labjack_monitor.py:

def start_monitoring_with_video_sync(...):
    try:
        # Check for duplicate
        if session_id in self.active_sessions:
            duplicate_session_attempts.inc()
            session_creation_total.labels(
                status='duplicate',
                source='api'
            ).inc()
            return False

        # Create session
        # ...

        # Success
        active_sessions.inc()
        detection_callbacks.set(len(self.labjack_monitor.detection_callbacks))
        session_creation_total.labels(
            status='success',
            source='api'
        ).inc()

    except Exception as e:
        session_creation_total.labels(
            status='error',
            source='api'
        ).inc()
        raise
```

**Alert rules:**

```yaml
# alerts.yml
groups:
  - name: hil_monitoring
    interval: 10s
    rules:
      - alert: MultipleSessions
        expr: hil_active_sessions > 1
        for: 5s
        labels:
          severity: critical
        annotations:
          summary: "Multiple HIL sessions detected"
          description: "{{ $value }} sessions active (expected 1)"

      - alert: DuplicateSessionAttempts
        expr: rate(hil_duplicate_session_attempts[1m]) > 0
        labels:
          severity: warning
        annotations:
          summary: "Duplicate session creation attempts"
          description: "System attempting to create duplicate sessions"

      - alert: MultipleCallbacks
        expr: hil_detection_callbacks > 1
        for: 5s
        labels:
          severity: critical
        annotations:
          summary: "Multiple detection callbacks registered"
          description: "{{ $value }} callbacks active (expected 1)"
```

## Testing Strategy

### Test 1: Session Uniqueness
```python
# File: backend/tests/test_session_uniqueness.py

import pytest
from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
from services.session_registry import session_registry, DuplicateSessionError

@pytest.fixture(autouse=True)
def clear_registry():
    """Clear session registry before each test"""
    session_registry.clear()
    yield
    session_registry.clear()

def test_single_session_per_video():
    """Verify only one session can monitor a video"""

    monitor = get_dedicated_labjack_monitor()

    session_id_1 = "test-session-1"
    session_id_2 = "test-session-2"
    video_id = "test-video-123"

    config = {
        'video_id': video_id,
        'project_id': 'test-project',
        'fps': 30,
        'duration': 10.0
    }

    # First session should succeed
    success = await monitor.start_monitoring_with_video_sync(
        session_id_1, config
    )
    assert success, "First session should start successfully"

    # Second session for same video should fail
    with pytest.raises(DuplicateSessionError):
        await monitor.start_monitoring_with_video_sync(
            session_id_2, config
        )

    # Verify only one session exists
    assert len(monitor.active_sessions) == 1
    assert session_id_1 in monitor.active_sessions
    assert session_id_2 not in monitor.active_sessions

def test_session_idempotency():
    """Verify repeated calls with same session ID are idempotent"""

    monitor = get_dedicated_labjack_monitor()
    session_id = "test-session"
    config = {
        'video_id': 'test-video',
        'project_id': 'test-project',
        'fps': 30
    }

    # First call
    success1 = await monitor.start_monitoring_with_video_sync(
        session_id, config
    )
    assert success1

    # Second call with same ID should return False (already exists)
    success2 = await monitor.start_monitoring_with_video_sync(
        session_id, config
    )
    assert not success2  # Already exists

    # Should still only have one session
    assert len(monitor.active_sessions) == 1

def test_detection_callback_uniqueness():
    """Verify only one detection callback per session"""

    monitor = get_dedicated_labjack_monitor()
    session_id = "test-session"
    config = {'video_id': 'test-video', 'project_id': 'test-project'}

    initial_callback_count = len(
        monitor.labjack_monitor.detection_callbacks
    )

    await monitor.start_monitoring_with_video_sync(session_id, config)

    final_callback_count = len(
        monitor.labjack_monitor.detection_callbacks
    )

    # Should have added exactly one callback
    assert final_callback_count == initial_callback_count + 1
```

### Test 2: Detection Processing
```python
def test_detection_processed_once(test_session):
    """Verify detections processed exactly once"""

    # Trigger hardware detection
    simulate_voltage_spike(channel='AIN0', voltage=3.3)

    await asyncio.sleep(1.0)

    # Query database
    db = SessionLocal()
    detections = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == test_session.id
    ).all()
    db.close()

    # Should have exactly ONE detection
    assert len(detections) == 1, \
        f"Expected 1 detection, found {len(detections)}"

    # Detection should have correct session ID
    assert detections[0].test_session_id == test_session.id
```

## Deployment Plan

### Phase 1: Immediate (Day 1)
1. ✅ Add stack trace logging to `start_monitoring_with_video_sync()`
2. ✅ Add session existence check guard
3. ✅ Deploy monitoring script to production
4. ✅ Run video sequence test and capture logs
5. ✅ Identify phantom session source

### Phase 2: Short Term (Days 2-3)
1. ⏳ Implement `SessionRegistry` class
2. ⏳ Integrate registry into `DedicatedLabJackMonitor`
3. ⏳ Add `DuplicateSessionError` exception
4. ⏳ Update all session creation code paths
5. ⏳ Add comprehensive unit tests

### Phase 3: Medium Term (Week 1)
1. ⏳ Add Prometheus metrics
2. ⏳ Configure alerts in monitoring system
3. ⏳ Add session health checks
4. ⏳ Implement session state machine
5. ⏳ Add admin dashboard for session management

### Phase 4: Long Term (Weeks 2-4)
1. ⏳ Refactor session lifecycle management
2. ⏳ Implement proper session recovery
3. ⏳ Add session migration capabilities
4. ⏳ Comprehensive integration testing
5. ⏳ Performance optimization

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| Breaking existing tests | Medium | High | Comprehensive testing, gradual rollout |
| False positive duplicates | Low | Medium | Proper idempotency checks |
| Performance degradation | Low | Low | Registry uses efficient dict lookups |
| Race conditions | Low | High | Use threading locks consistently |
| Database connection exhaustion | Low | Medium | Use connection pooling, proper cleanup |

## Success Criteria

1. ✅ **Zero duplicate sessions** - Only ONE session per test execution
2. ✅ **Single callback** - Exactly ONE detection callback per video
3. ✅ **Consistent hardware mode** - No stream/poll mode switching
4. ✅ **Unified timing** - Single authoritative video start time
5. ✅ **Clean session lifecycle** - Proper creation, monitoring, cleanup

## Monitoring Checklist

- [ ] Active session count = 1 during test
- [ ] Detection callback count = 1
- [ ] Zero duplicate session attempts
- [ ] Zero session creation errors
- [ ] Hardware mode stays constant
- [ ] All detections assigned to primary session
- [ ] Database shows only primary session

## Conclusion

The duplicate session issue requires **immediate attention** as it compromises data integrity and system reliability. The recommended approach is:

1. **Immediate:** Add guards and logging to identify source
2. **Short-term:** Implement `SessionRegistry` for prevention
3. **Long-term:** Refactor session lifecycle management

The root cause is likely a **secondary code path** (websocket handler, background worker, or bridge service) calling `start_monitoring_with_video_sync()` independently. Once identified, this path should be:
- Blocked from creating new sessions
- Modified to use existing session
- Or eliminated if unnecessary

**Priority:** CRITICAL - Deploy Phase 1 fixes immediately.

---

**Related Documents:**
- [Session Management Analysis](./session-management-analysis.md)
- [HIL Timing Fix Implementation](../hil_timing_fix_implementation.md)
- [Database Schema Design](../database/schema-design.md)
