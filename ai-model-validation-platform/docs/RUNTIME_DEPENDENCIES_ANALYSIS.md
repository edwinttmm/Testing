# Runtime Dependencies Analysis - Ground Truth Fixes
## Critical Service Startup Order & Prerequisites Investigation

**Date:** 2025-10-31
**Target:** All 6 ground-truth matching fixes
**Objective:** Identify missing runtime prerequisites causing startup failures

---

## Executive Summary

### Critical Finding: Race Condition in Orchestrator Initialization (Issue #1)

**Problem:** The `VideoSequenceOrchestrator` is initialized AFTER endpoints are registered but BEFORE actual session starts. This creates a race condition where:
1. `/api/test-sessions/start` endpoint is registered with `orchestrator = None`
2. HIL test starts and calls `start_hil_test_session()`
3. Orchestrator is created in `hil_test_complete.py:303-318` but NOT stored in `hil_manager.active_sessions`
4. Video end notifications fail because orchestrator reference is lost

**Root Cause:** `hil_manager.active_sessions` in `hil_test_complete.py:73` is NOT the same as `orchestrator._active_sequences` in `video_sequence_orchestrator.py:176`

---

## Service Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                        Startup Order                            │
└─────────────────────────────────────────────────────────────────┘

1. ⚙️  Database Engine (database.py:engine)
   └─> SQLAlchemy SessionLocal factory
   └─> Table migrations (main.py:230-440)

2. 🔌 WebSocket Server (socketio_server.py)
   └─> Socket.IO server initialization (line 15-47)
   └─> active_sessions: Dict[str, Any] (line 50) ⚠️ POTENTIAL CONFLICT

3. 📡 LabJack Hardware Service (BEFORE video playback)
   ├─> services/real_labjack_service.py (main.py:1172-1176)
   ├─> services/dedicated_labjack_monitor.py (main.py:222-227)
   └─> services/raw_labjack_integration.py (bridge service)

   ⚠️ CRITICAL: Must be initialized BEFORE video timing starts
   └─> Prevents missed detections during startup delay

4. 🎬 Video Sequence Orchestrator (LAZY INITIALIZATION)
   ├─> Created: hil_test_complete.py:304 (during session start)
   ├─> Stored: hil_manager.active_sessions[session_id]['orchestrator']
   └─> ⚠️ RACE CONDITION: Not persisted across endpoint calls

5. 🎯 Video Timing Service (ON-DEMAND)
   └─> services/video_timing_service.py
   └─> Initialized when video starts playing

6. 🔍 Detection Services (SESSION-SCOPED)
   ├─> services/labjack_detection_service.py
   └─> services/ground_truth_matching_service.py
```

---

## Critical Race Condition Analysis

### Issue #1: Orchestrator Lifecycle Management

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/api/hil_test_complete.py`

**Problem Code (Line 303-424):**
```python
# BUG #4 FIX: Initialize VideoSequenceOrchestrator for multi-video sessions
orchestrator = None
sequence_id: Optional[str] = None

if has_video_sequence:
    # Create orchestrator instance for this session ⚠️ LOCAL VARIABLE
    orchestrator = VideoSequenceOrchestrator()
    sequence_id = orchestrator.start_sequence(...)

    # Store in active_sessions
    hil_manager.active_sessions[test_session.id] = {
        # ... other fields ...
        'orchestrator': orchestrator,  # ⚠️ STORED HERE
        'active_video_id': None
    }
```

**Problem Code (Line 719-943):**
```python
@router.post("/session/{session_id}/video/end")
async def end_video_playback(...):
    # Get active session and orchestrator
    active_session = hil_manager.active_sessions.get(session_id)  # ⚠️ MAY BE EMPTY

    if active_session:
        orchestrator = active_session.get("orchestrator")  # ⚠️ MAY BE None

        if orchestrator:
            # ... orchestrator sync logic ...
        else:
            logger.info("No orchestrator attached to session")  # ⚠️ FAILS SILENTLY
```

**Root Cause:**
1. `hil_manager.active_sessions` is a **module-level global** (line 73)
2. Each API endpoint call may run in different **FastAPI worker thread/process**
3. Session data is NOT persisted to database immediately after creation
4. Orchestrator instance is stored in **memory** but not **serialized**

**Verification Evidence:**
```python
# socketio_server.py:50
active_sessions: Dict[str, Any] = {}  # ⚠️ GLOBAL MODULE STATE

# hil_test_complete.py:73
hil_manager = HILTestManager()  # ⚠️ DIFFERENT INSTANCE

class HILTestManager:
    def __init__(self):
        self.active_sessions: Dict[int, dict] = {}  # ⚠️ INSTANCE STATE
```

---

## Missing Prerequisites Checklist

### ❌ CRITICAL: Missing Service Coordination

| **Prerequisite** | **Status** | **Location** | **Impact** |
|------------------|-----------|--------------|------------|
| Global orchestrator registry | ❌ MISSING | N/A | Video end fails |
| Database session persistence | ⚠️ PARTIAL | test_sessions.sequence_id | Orchestrator lost |
| WebSocket-LabJack coordination | ⚠️ PARTIAL | dedicated_labjack_monitor.py:78-82 | Detections may miss |
| Video timing pre-initialization | ❌ MISSING | N/A | Race condition |
| Orchestrator recovery mechanism | ❌ MISSING | N/A | Cannot resume |

### ✅ WORKING: Existing Services

| **Service** | **Status** | **Initialization** |
|-------------|-----------|-------------------|
| Database connection | ✅ WORKING | main.py:210-218 |
| WebSocket server | ✅ WORKING | socketio_server.py:15-47 |
| LabJack hardware | ✅ WORKING | main.py:1172-1218 |
| Detection monitoring | ✅ WORKING | dedicated_labjack_monitor.py |

---

## Startup Order Requirements

### Phase 1: Infrastructure (BEFORE FastAPI app start)
```python
# main.py lifespan context manager
1. Database engine initialization (line 210)
2. Table migrations (line 230-440)
3. WebSocket server creation (line 28)
4. LabJack hardware initialization (line 1172-1218)
```

### Phase 2: Service Registration (FastAPI app creation)
```python
# main.py after app = FastAPI()
5. Router registration (line 620-927)
   ├─> test_sessions router (line 679)
   └─> video_sequence_testing router (line 687)
```

### Phase 3: Session Initialization (Per-request)
```python
# When /api/test-sessions/start is called
6. HIL test session creation (hil_test_complete.py:267)
7. VideoSequenceOrchestrator creation (line 304)
   ⚠️ PROBLEM: Orchestrator stored in local memory only
8. LabJack monitoring start (line 442)
9. Video timing start (line 243)
```

---

## Failure Scenarios

### Scenario 1: Orchestrator is None at startup
**Trigger:** First video start after session creation
**Symptom:** `active_session.get("orchestrator")` returns `None`
**Root Cause:** Session data not persisted across endpoint calls
**Fix Required:** Global orchestrator registry or database persistence

### Scenario 2: LabJack starts AFTER video timing
**Trigger:** Video starts before LabJack monitoring is ready
**Symptom:** First ~200ms of detections are missed
**Root Cause:** No startup coordination between services
**Fix Required:** Wait for `monitoring_ready` WebSocket event

### Scenario 3: Multiple sessions access same orchestrator
**Trigger:** Two sessions start simultaneously
**Symptom:** Orchestrator `_active_sequences` dict corrupted
**Root Cause:** No thread-safety in VideoSequenceOrchestrator
**Fix Required:** Thread locks or session isolation

### Scenario 4: WebSocket disconnects during test
**Trigger:** Network interruption or page refresh
**Symptom:** Detection events not emitted, but test continues
**Root Cause:** No reconnection logic in dedicated_labjack_monitor.py
**Fix Required:** Persistent WebSocket subscription

### Scenario 5: Database commit fails during orchestrator sync
**Trigger:** SQLite lock or connection timeout
**Symptom:** Video end recorded but orchestrator not notified
**Root Cause:** No rollback logic in hil_test_complete.py:810-816
**Fix Required:** Transaction isolation

---

## Recommended Startup Validation Checks

### Pre-Flight Checklist (Add to main.py lifespan)
```python
async def validate_hil_services():
    """Validate all HIL services are ready before accepting requests"""

    # 1. Database connectivity
    assert engine.connect(), "Database connection failed"

    # 2. WebSocket server
    assert sio is not None, "WebSocket server not initialized"

    # 3. LabJack hardware (if required)
    if settings.require_labjack:
        from services.real_labjack_service import get_real_labjack_service
        service = get_real_labjack_service()
        assert service.get_status().connected, "LabJack not connected"

    # 4. Global orchestrator registry (NEW)
    from services.video_sequence_orchestrator import _orchestrator_service
    assert _orchestrator_service is not None, "Orchestrator service not initialized"

    # 5. Video timing service
    from services.video_timing_service import get_video_timing_service
    timing_service = get_video_timing_service()
    assert timing_service is not None, "Video timing service not initialized"

    logger.info("✅ All HIL services validated successfully")
```

### Runtime Health Checks (Add to /health endpoint)
```python
@app.get("/health/hil-services")
async def hil_services_health():
    """Check health of all HIL-critical services"""

    health = {
        "database": check_database_connection(),
        "websocket": check_websocket_server(),
        "labjack": check_labjack_hardware(),
        "orchestrator_registry": check_orchestrator_registry(),  # NEW
        "active_sessions": len(hil_manager.active_sessions),
        "pending_detections": get_pending_detection_count()
    }

    if not all(health.values()):
        return JSONResponse(status_code=503, content=health)

    return health
```

---

## Environment Variables Required

```bash
# Database
DATABASE_URL=sqlite:///./dev_database.db

# WebSocket
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# LabJack (Optional - use mock if not present)
LABJACK_REQUIRED=false
LABJACK_MOCK_MODE=true

# Video Timing
VIDEO_TIMING_BUFFER_MS=31.75
TIMING_CALIBRATION_OFFSET_MS=166.0

# Orchestrator (NEW)
ORCHESTRATOR_GLOBAL_REGISTRY=true  # Enable global registry
ORCHESTRATOR_SESSION_PERSISTENCE=true  # Persist to database
```

---

## Configuration Files Required

### Database Schema (Already exists)
- `models.py`: VideoTestSequence, SequenceVideoResult, TestSession
- `migrations/`: Alembic migration scripts

### Service Configuration (Missing)
- `config/orchestrator.yaml`: Orchestrator registry settings
- `config/labjack.yaml`: LabJack hardware configuration
- `config/timing.yaml`: Video timing calibration values

---

## Solution: Global Orchestrator Registry

### Implementation Plan

**File:** `services/orchestrator_registry.py` (NEW)
```python
"""
Global orchestrator registry to persist instances across endpoint calls
"""
import threading
from typing import Dict, Optional
from services.video_sequence_orchestrator import VideoSequenceOrchestrator

class OrchestratorRegistry:
    """Thread-safe global registry for VideoSequenceOrchestrator instances"""

    def __init__(self):
        self._orchestrators: Dict[str, VideoSequenceOrchestrator] = {}
        self._lock = threading.RLock()

    def register(self, session_id: str, orchestrator: VideoSequenceOrchestrator):
        """Register orchestrator for a session"""
        with self._lock:
            self._orchestrators[session_id] = orchestrator

    def get(self, session_id: str) -> Optional[VideoSequenceOrchestrator]:
        """Get orchestrator for a session"""
        with self._lock:
            return self._orchestrators.get(session_id)

    def unregister(self, session_id: str):
        """Remove orchestrator after session completes"""
        with self._lock:
            self._orchestrators.pop(session_id, None)

# Global singleton
_registry = OrchestratorRegistry()

def get_orchestrator_registry() -> OrchestratorRegistry:
    return _registry
```

**Integration in hil_test_complete.py:**
```python
from services.orchestrator_registry import get_orchestrator_registry

# In start_hil_test_session (line 304):
if has_video_sequence:
    orchestrator = VideoSequenceOrchestrator()
    sequence_id = orchestrator.start_sequence(...)

    # Register globally (NEW)
    registry = get_orchestrator_registry()
    registry.register(str(test_session.id), orchestrator)

    # Also store in active_sessions for backward compatibility
    hil_manager.active_sessions[test_session.id] = {
        'orchestrator': orchestrator,
        # ... other fields ...
    }

# In end_video_playback (line 823):
# Try registry first, then fallback to active_sessions
registry = get_orchestrator_registry()
orchestrator = registry.get(str(session_id))

if not orchestrator:
    # Fallback to active_sessions
    active_session = hil_manager.active_sessions.get(session_id)
    if active_session:
        orchestrator = active_session.get("orchestrator")

if orchestrator:
    # Orchestrator sync logic...
else:
    logger.error(f"No orchestrator found for session {session_id} in registry or active_sessions")
    raise HTTPException(status_code=500, detail="Orchestrator not found")
```

---

## Timing Diagram: Correct Startup Sequence

```
Time (ms)  │ Service Activity
────────────┼──────────────────────────────────────────────────────────
0          │ FastAPI app starts
           │ └─> Database engine initialized
           │ └─> WebSocket server created
           │ └─> LabJack hardware initialized (lazy)
           │
+50        │ API endpoints registered
           │ └─> /api/test-sessions/start
           │ └─> /api/video-sequences/*
           │
+100       │ HTTP Server listening on :8000
           │ ✅ Ready to accept requests
           │
────────────┼──────────────────────────────────────────────────────────
           │ USER CLICKS "Start Test"
────────────┼──────────────────────────────────────────────────────────
           │
+0         │ POST /api/test-sessions/start
           │ └─> Create TestSession record
           │ └─> Create VideoSequenceOrchestrator
           │ └─> Register in global registry ⚠️ NEW
           │ └─> Start LabJack monitoring
           │
+20        │ LabJack monitoring ready
           │ └─> Emit 'monitoring_ready' WebSocket event
           │
+50        │ Frontend receives 'monitoring_ready'
           │ └─> Frontend starts video playback
           │
+80        │ POST /api/test-sessions/{id}/video/start
           │ └─> Capture T1 video start timestamp
           │ └─> Start video timing service
           │ └─> Notify orchestrator: video started ⚠️ CRITICAL
           │
────────────┼──────────────────────────────────────────────────────────
           │ VIDEO PLAYING - DETECTIONS CAPTURED
────────────┼──────────────────────────────────────────────────────────
           │
+5250      │ Video ends (5.25s duration)
           │ └─> Frontend emits 'video_ended' event
           │
+5270      │ POST /api/test-sessions/{id}/video/end
           │ └─> Get orchestrator from global registry ⚠️ NEW
           │ └─> Update SequenceVideoResult
           │ └─> Notify orchestrator: video ended ⚠️ CRITICAL
           │ └─> Orchestrator evaluates video results
           │ └─> Orchestrator triggers next video (if any)
           │
+5300      │ Sequence complete
           │ └─> Unregister orchestrator from registry
           │
────────────┴──────────────────────────────────────────────────────────
```

---

## Blockers Identified

### Priority 1 - CRITICAL BLOCKERS (Must fix before deployment)

1. **Orchestrator Lost Between Endpoint Calls**
   - **Impact:** Video end notifications fail, sequence never completes
   - **Fix:** Global orchestrator registry (see solution above)
   - **ETA:** 2 hours

2. **LabJack Monitoring Starts After Video**
   - **Impact:** First ~200ms of detections missed
   - **Fix:** Wait for `monitoring_ready` WebSocket event
   - **ETA:** 1 hour

3. **No Database Transaction Rollback**
   - **Impact:** Inconsistent state if orchestrator sync fails
   - **Fix:** Add try/except around DB commit in `hil_test_complete.py:810`
   - **ETA:** 30 minutes

### Priority 2 - IMPORTANT (Fix before production)

4. **WebSocket Disconnection Not Handled**
   - **Impact:** Detections not emitted if client reconnects
   - **Fix:** Persistent subscription manager
   - **ETA:** 3 hours

5. **No Thread Safety in Orchestrator**
   - **Impact:** Concurrent sessions may corrupt `_active_sequences`
   - **Fix:** Add `threading.RLock()` to VideoSequenceOrchestrator
   - **ETA:** 1 hour

6. **Missing Health Check Endpoint**
   - **Impact:** Cannot validate services are ready
   - **Fix:** Add `/health/hil-services` endpoint (see above)
   - **ETA:** 1 hour

---

## Testing Strategy

### Unit Tests Required
```python
# tests/test_orchestrator_registry.py
def test_orchestrator_persistence_across_calls():
    """Verify orchestrator survives endpoint transition"""

def test_concurrent_session_isolation():
    """Verify thread safety with multiple sessions"""

def test_registry_cleanup_on_completion():
    """Verify orchestrator is unregistered after session ends"""
```

### Integration Tests Required
```python
# tests/test_video_sequence_integration.py
def test_full_sequence_with_orchestrator():
    """End-to-end test: session start -> video play -> video end -> sequence complete"""

def test_orchestrator_recovery_after_failure():
    """Verify orchestrator can be recovered from database if registry fails"""
```

---

## Conclusion

**Root Cause:** The VideoSequenceOrchestrator is stored in module-level memory (`hil_manager.active_sessions`) which is NOT shared across FastAPI endpoint calls. This creates a critical race condition where the orchestrator is created during session start but is `None` when video end is called.

**Solution:** Implement a global orchestrator registry with database persistence fallback to ensure orchestrator instances survive across endpoint calls.

**Estimated Fix Time:** 8 hours (includes testing)

**Risk:** HIGH - Without this fix, multi-video sequences will never complete successfully.

---

## Appendix A: Service Dependency Matrix

| Service | Depends On | Initialization Order | Critical? |
|---------|-----------|---------------------|-----------|
| Database Engine | None | 1 | ✅ YES |
| WebSocket Server | None | 2 | ✅ YES |
| LabJack Hardware | Database | 3 | ⚠️ CONDITIONAL |
| Orchestrator Registry | Database | 4 | ✅ YES (NEW) |
| Video Timing Service | Database, WebSocket | 5 | ✅ YES |
| Detection Services | LabJack, Video Timing | 6 | ✅ YES |

---

## Appendix B: Configuration Validation Script

```python
#!/usr/bin/env python3
"""
Validate HIL service prerequisites before startup
"""
import os
import sys

def validate_environment():
    """Check all required environment variables"""
    required = [
        'DATABASE_URL',
        'CORS_ORIGINS'
    ]

    optional = [
        'LABJACK_REQUIRED',
        'ORCHESTRATOR_GLOBAL_REGISTRY'
    ]

    missing = [var for var in required if not os.getenv(var)]

    if missing:
        print(f"❌ Missing required environment variables: {missing}")
        return False

    print("✅ All required environment variables present")
    return True

def validate_database():
    """Check database connectivity"""
    from database import engine
    try:
        engine.connect()
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def validate_services():
    """Check all services are importable"""
    try:
        from services.video_sequence_orchestrator import VideoSequenceOrchestrator
        from services.video_timing_service import get_video_timing_service
        from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
        print("✅ All services importable")
        return True
    except Exception as e:
        print(f"❌ Service import failed: {e}")
        return False

if __name__ == "__main__":
    checks = [
        validate_environment(),
        validate_database(),
        validate_services()
    ]

    if not all(checks):
        print("\n❌ Pre-flight validation FAILED")
        sys.exit(1)

    print("\n✅ All pre-flight checks PASSED")
    sys.exit(0)
```

**Usage:**
```bash
# Run before starting the backend server
python validate_hil_services.py && uvicorn main:app
```

---

**Document Version:** 1.0
**Last Updated:** 2025-10-31
**Author:** System Architecture Designer
