# HIL Detection Zero Events Fix - Implementation Plan

**Date:** 2025-11-14
**Issue:** Zero detections shown in frontend despite hardware signals being captured
**Root Cause:** WebSocket room join timing race condition (100-200ms gap)

---

## Implementation Strategy

### Fix #1: Proactive Room Join (PRIMARY FIX)
**Priority:** IMMEDIATE
**Impact:** Eliminates 100% detection loss
**Approach:** Join WebSocket session room BEFORE creating test session

### Implementation Steps

#### Step 1: Frontend - Proactive Room Join
**File:** `/frontend/src/pages/HILTestExecution.tsx`

**Current Flow (BROKEN):**
```
1. Frontend: Create test session via API (T=0ms)
2. Backend: Session created in database (T=50ms)
3. Frontend: Receives session_id (T=75ms)
4. Frontend: Emits join_session (T=100ms)
5. Backend: Confirms room join (T=150ms)
6. ⚠️ PROBLEM: Detections emitted starting at T=125ms (room empty)
```

**New Flow (FIXED):**
```
1. Frontend: Generate temporary session_id (T=0ms)
2. Frontend: Join WebSocket room immediately (T=10ms)
3. Backend: Confirms room join (T=50ms)
4. Frontend: Create test session with pre-generated ID (T=75ms)
5. Backend: Detections start emitting (T=125ms)
6. ✅ SUCCESS: Frontend already in room to receive events
```

#### Step 2: Frontend - Update startTest Function
**Location:** Lines 291-345 in `HILTestExecution.tsx`

**Changes Required:**
1. Generate session_id on frontend BEFORE API call
2. Join WebSocket room using websocketService.joinSession()
3. Pass pre-generated session_id to API endpoint
4. Backend accepts pre-defined session_id (optional override)

#### Step 3: Backend - Support Pre-defined Session ID
**File:** `/backend/routers/video_sequence_testing.py`

**Changes Required:**
1. Accept optional `session_id` in request body
2. Use provided session_id if valid, generate new one otherwise
3. Validate session_id format (UUID)

#### Step 4: Backend - Ensure Room Created Early
**File:** `/backend/services/websocket_service.py`

**Changes Required:**
1. Create session room when join_session event received
2. Buffer room creation before session record exists
3. Allow room join with non-existent session (temporary)

---

## Code Changes

### Frontend: HILTestExecution.tsx

**BEFORE (Lines 291-345):**
```typescript
const startTest = async () => {
  const validation = validateTestStart();
  if (!validation.canStart) {
    setError(`Cannot start test:\n${validation.errors.join('\n')}`);
    return;
  }

  try {
    setLoading(true);
    setError(null);

    // Create test session
    const testSessionData: TestSessionCreate = {
      projectId: selectedProject!.id,
      name: `HIL Test Session - ${new Date().toISOString()}`,
      maxLatencyMs,
      labjackConnected: labjackStatus!.connected,
      status: 'running'
    };

    const session = await apiService.post<TestSessionInterface>('/api/v1/test-sessions', testSessionData);
    setCurrentTestSession(session);

    // ⚠️ GAP: Time passes here (75-100ms)

    // Subscribe to hardware signals via WebSocket (TOO LATE)
    if (wsConnected) {
      wsEmit('subscribe_hardware_signals', {
        sessionId: session.id,
        signalType: labjackStatus!.signalType
      });
    }

    // ... rest of function
  } catch (err: any) {
    setError(`Failed to start test: ${err.message}`);
  } finally {
    setLoading(false);
  }
};
```

**AFTER (FIXED):**
```typescript
const startTest = async () => {
  const validation = validateTestStart();
  if (!validation.canStart) {
    setError(`Cannot start test:\n${validation.errors.join('\n')}`);
    return;
  }

  try {
    setLoading(true);
    setError(null);

    // ✅ FIX #1: Generate session ID upfront
    const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // ✅ FIX #2: Join WebSocket room BEFORE creating session
    if (wsConnected) {
      try {
        await websocketService.joinSession(sessionId);
        console.log(`✅ Proactively joined session room: ${sessionId}`);
      } catch (error) {
        setError('Failed to join WebSocket session. Please retry.');
        setLoading(false);
        return;
      }
    } else {
      setError('WebSocket not connected. Cannot start test.');
      setLoading(false);
      return;
    }

    // ✅ FIX #3: Create test session with pre-generated ID
    const testSessionData: TestSessionCreate = {
      sessionId, // Pass pre-generated ID
      projectId: selectedProject!.id,
      name: `HIL Test Session - ${new Date().toISOString()}`,
      maxLatencyMs,
      labjackConnected: labjackStatus!.connected,
      status: 'running'
    };

    const session = await apiService.post<TestSessionInterface>('/api/v1/test-sessions', testSessionData);
    setCurrentTestSession(session);

    // ✅ NOW IN ROOM: Detections will be received immediately

    // Subscribe to hardware signals (already in room)
    if (wsConnected) {
      wsEmit('subscribe_hardware_signals', {
        sessionId: session.id,
        signalType: labjackStatus!.signalType
      });
    }

    // Capture high-precision Test_Start_Time (PRD requirement)
    const startTime = new Date();
    setTestStartTime(startTime);
    setTestInProgress(true);

    // Switch to full-screen mode (PRD requirement)
    await enterFullScreen();

    // Start video playback
    setCurrentVideoIndex(0);
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
      await videoRef.current.play();
    }

    setSuccessMessage('HIL test started successfully');
    setStartTestDialog(false);

  } catch (err: any) {
    setError(`Failed to start test: ${err.message}`);
  } finally {
    setLoading(false);
  }
};
```

### Backend: TestSessionCreate Schema

**File:** `/backend/schemas_video_annotation.py` (or wherever TestSessionCreate is defined)

**BEFORE:**
```python
class TestSessionCreate(BaseModel):
    projectId: str
    name: str
    maxLatencyMs: int
    labjackConnected: bool
    status: str
```

**AFTER:**
```python
class TestSessionCreate(BaseModel):
    sessionId: Optional[str] = None  # ✅ Allow pre-generated ID
    projectId: str
    name: str
    maxLatencyMs: int
    labjackConnected: bool
    status: str
```

### Backend: Test Session Endpoint

**File:** `/backend/routers/video_sequence_testing.py`

**BEFORE:**
```python
@router.post("/test-sessions", response_model=TestSessionResponse)
async def create_test_session(
    session_data: TestSessionCreate,
    db: Session = Depends(get_db)
):
    # Generate new session ID
    session_id = str(uuid.uuid4())

    # Create session record
    new_session = TestSession(
        id=session_id,
        project_id=session_data.projectId,
        # ... other fields
    )
    db.add(new_session)
    db.commit()

    return new_session
```

**AFTER:**
```python
@router.post("/test-sessions", response_model=TestSessionResponse)
async def create_test_session(
    session_data: TestSessionCreate,
    db: Session = Depends(get_db)
):
    # ✅ Use provided session_id if valid, otherwise generate
    if session_data.sessionId:
        # Validate format (should be string with session_ prefix)
        if not session_data.sessionId.startswith('session_'):
            raise HTTPException(
                status_code=400,
                detail="Invalid session_id format. Must start with 'session_'"
            )
        session_id = session_data.sessionId
        logger.info(f"✅ Using pre-generated session ID: {session_id}")
    else:
        session_id = f"session_{uuid.uuid4()}"
        logger.info(f"📝 Generated new session ID: {session_id}")

    # Create session record
    new_session = TestSession(
        id=session_id,
        project_id=session_data.projectId,
        # ... other fields
    )
    db.add(new_session)
    db.commit()

    return new_session
```

---

## Testing Plan

### Test Case 1: Basic Flow
**Steps:**
1. Start test in HILTestExecution
2. Verify WebSocket join happens before API call
3. Send test detection signal
4. Verify detection appears in frontend immediately

**Expected Result:**
- ✅ Zero detection events displayed in real-time
- ✅ No 100-200ms delay in first detection

### Test Case 2: WebSocket Disconnection
**Steps:**
1. Start test with room join
2. Disconnect WebSocket mid-test
3. Verify PROTOCOL #47 auto-rejoin works
4. Verify detections resume after reconnection

**Expected Result:**
- ✅ Auto-rejoin to same session room
- ✅ Buffered events flushed after rejoin

### Test Case 3: Multiple Rapid Starts
**Steps:**
1. Start test
2. Stop test immediately
3. Start new test within 1 second
4. Verify no room membership conflicts

**Expected Result:**
- ✅ Clean room transitions
- ✅ No cross-session event leakage

---

## Rollback Plan

If issues occur with proactive room join:

1. **Revert frontend changes** to original flow
2. **Enable PROTOCOL #47 buffering** for initial join (already implemented in code)
3. **Increase backend event buffer** as temporary fallback

---

## Metrics to Monitor

### Success Criteria
- **Detection latency:** < 50ms from hardware signal to frontend display
- **Zero detection rate:** 0% (down from current ~100%)
- **Room join success rate:** > 99.9%
- **Event delivery rate:** 100% of emitted events received

### Monitoring Dashboard
Track these metrics in real-time:
1. WebSocket room join timing (target: < 10ms)
2. First detection arrival time (target: < 100ms from test start)
3. Total detections received vs emitted (target: 100% match)
4. Session room membership before first emission (target: 100%)

---

## Implementation Timeline

**Phase 1 (Immediate):**
- [ ] Frontend: Generate session_id upfront
- [ ] Frontend: Proactive WebSocket room join
- [ ] Frontend: Pass session_id to backend

**Phase 2 (15 minutes):**
- [ ] Backend: Accept optional session_id
- [ ] Backend: Validate session_id format
- [ ] Backend: Log session_id source (pre-gen vs generated)

**Phase 3 (Testing):**
- [ ] Test basic detection flow
- [ ] Test reconnection handling
- [ ] Test rapid start/stop cycles
- [ ] Verify metrics dashboard

**Phase 4 (Monitoring):**
- [ ] Monitor zero detection rate (target: 0%)
- [ ] Monitor room join timing
- [ ] Monitor first detection latency
- [ ] Document results

---

## Risk Assessment

### Low Risk
- ✅ Frontend change is isolated to startTest function
- ✅ Backend change is backward compatible (optional field)
- ✅ WebSocket room join already tested and working

### Medium Risk
- ⚠️ Session ID collision (mitigated by timestamp + random)
- ⚠️ Room cleanup timing (mitigated by existing cleanup logic)

### Mitigation
- Add session_id uniqueness validation
- Implement room TTL (time-to-live) for abandoned rooms
- Log all session_id sources for debugging

---

## Expected Outcome

**Before Fix:**
- Detection events: 0 shown (100% loss)
- User experience: "No detections found" despite hardware working

**After Fix:**
- Detection events: 100% delivery rate
- User experience: Real-time detection display with < 50ms latency
- Zero detection rate: 0%

**Timeline:** Complete fix in < 30 minutes
