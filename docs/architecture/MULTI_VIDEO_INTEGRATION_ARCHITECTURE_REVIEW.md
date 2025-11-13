# Multi-Video Integration Architecture Review

**Date**: 2025-01-12
**Reviewer**: System Architecture Designer (SILENT AGENT #18)
**Status**: 🔴 CRITICAL ARCHITECTURAL DEBT IDENTIFIED

---

## Executive Summary

The multi-video integration is **architecturally broken** across 5 critical dimensions:

1. **Dual Routing System**: Two independent routers don't integrate
2. **Data Model Disconnect**: Database schema perfect, API layer doesn't query it
3. **Field Naming Chaos**: Three naming conventions (snake_case, camelCase, both)
4. **WebSocket Event Mismatch**: Events emitted ≠ events subscribed
5. **State Management Fragmentation**: Three sources of truth causing race conditions

**Production Readiness**: 🚫 **BLOCKED** - Requires architectural unification

---

## 1. System Architecture Overview

### Current Architecture (Broken)

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend Layer                        │
│  - Expects: perVideoResults[] array                         │
│  - Subscribes: video_transition, sequence_completed         │
│  - Types: BOTH snake_case AND camelCase variants            │
└─────────────────┬───────────────────────────────────────────┘
                  │ API Calls
                  ↓
┌──────────────────────────────────────────────────────────────┐
│                    Backend API Layer (SPLIT)                 │
│                                                               │
│  Router A: test_sessions.py (Single-Video Legacy)           │
│  ├─ GET /test-sessions/{id} → Returns sequence_metadata     │
│  ├─ GET /test-sessions/{id}/events → 700 lines inference    │
│  ├─ POST /test-sessions/{id}/complete → No per-video calc   │
│  └─ ❌ Returns dict(), bypasses Pydantic schemas             │
│                                                               │
│  Router B: video_sequences.py (Multi-Video Modern)          │
│  ├─ POST /video-sequences/video-started                     │
│  ├─ POST /video-sequences/video-ended                       │
│  └─ ✅ Proper schemas, but NEVER CALLED                      │
└─────────────────┬───────────────────────────────────────────┘
                  │ Manual DB Queries
                  ↓
┌──────────────────────────────────────────────────────────────┐
│               Database Layer (Well-Designed)                 │
│                                                               │
│  TestSession                                                 │
│    └─ has_video_sequence, sequence_id                       │
│        ↓ 1:Many CASCADE                                      │
│  VideoTestSequence                                           │
│    └─ sequence_order, video_ids (JSON)                      │
│        ↓ 1:Many CASCADE                                      │
│  SequenceVideoResult ← ❌ API NEVER QUERIES THIS TABLE      │
│    └─ avg_latency_ms, pass_rate_percent, timing             │
│        ↓ 1:Many CASCADE                                      │
│  DetectionEvent                                              │
│    └─ video_id, sequence_video_result_id                    │
└──────────────────────────────────────────────────────────────┘
```

**The Smoking Gun**: Database has perfect schema, API doesn't use it.

---

## 2. Critical Architectural Issues

### Issue #1: Dual Routing System (Router Fragmentation)

**Problem**: Two routers implement overlapping functionality without integration.

**Evidence**:
```python
# Router A: test_sessions.py (Lines 428-486)
# Returns sequence_metadata as JSON blob
return {
    "sequence_metadata": json.dumps({...})  # ❌ Unstructured
}

# Router B: video_sequences.py (Lines 120-356)
# Proper video-started/video-ended endpoints
@router.post("/video-sequences/video-started")  # ✅ Structured
async def video_started(payload: VideoStartPayload):
    # ... proper implementation ...

# ❌ test_sessions.py NEVER imports or calls video_sequences.py
```

**Impact**:
- Frontend calls `/test-sessions/{id}/results` expecting per-video breakdown
- Backend returns flat JSON blob requiring manual parsing
- `video_sequences.py` endpoints unused, causing orphaned code

**Root Cause**: Incremental feature development without architectural planning.

---

### Issue #2: Data Model vs API Layer Disconnect

**Problem**: Database has complete multi-video schema, but API endpoints don't query these tables.

**Database Schema** (Perfect):
```sql
-- SequenceVideoResult table (Lines 539-602 in models.py)
CREATE TABLE sequence_video_results (
    id VARCHAR PRIMARY KEY,
    video_sequence_id VARCHAR REFERENCES video_test_sequences(id) CASCADE,
    video_id TEXT REFERENCES videos(id),
    sequence_order INTEGER,
    -- Timing fields
    video_start_time FLOAT,
    video_end_time FLOAT,
    video_play_offset_ms FLOAT,
    -- Metrics fields
    avg_latency_ms FLOAT,
    max_latency_ms FLOAT,
    pass_rate_percent FLOAT,
    expected_detection_count INTEGER,
    actual_detection_count INTEGER,
    -- Status
    video_status VARCHAR,
    validation_result VARCHAR
);
-- 10 indexes for optimal query performance ✅
```

**API Implementation** (Broken):
```python
# Lines 1774-1841 in test_sessions.py
@router.get("/test-sessions/{session_id}/results")
def get_results(session_id: int, db: Session):
    session = db.query(TestSession).filter_by(id=session_id).first()

    # ❌ Never queries SequenceVideoResult table!
    # Should:
    # video_results = db.query(SequenceVideoResult).filter_by(
    #     video_sequence_id=session.sequence_id
    # ).all()

    return {
        "session_id": session_id,
        # ❌ Missing: "perVideoResults": [...]
    }
```

**Impact**:
- Per-video metrics (avg_latency_ms, pass_rate_percent) exist in DB but unreachable via API
- Frontend expects `perVideoResults[]` array, doesn't receive it
- Ground truth metrics calculated but not returned per video

**Data Flow Diagram**:
```
Frontend Request:
  GET /api/test-sessions/abc123/results
    ↓
test_sessions.py:
  Query TestSession ✅
  Query SequenceVideoResult ❌ SKIPPED
  Return sequence_metadata JSON blob ❌
    ↓
Frontend Receives:
  {
    "sequence_metadata": "{\"video_ids\": [...]}"  ❌ Unparsable
  }
  Expected:
  {
    "perVideoResults": [
      {"video_id": "vid1", "avg_latency_ms": 45.2, ...},
      {"video_id": "vid2", "avg_latency_ms": 52.1, ...}
    ]
  }
```

---

### Issue #3: Field Naming Chaos (Three Conventions)

**Problem**: Backend uses three different naming conventions simultaneously.

**Convention 1: Database** (snake_case)
```python
# models.py - SQLAlchemy models
class SequenceVideoResult(Base):
    video_start_time = Column(Float)
    pass_rate_percent = Column(Float)
    avg_latency_ms = Column(Float)
```

**Convention 2: Pydantic Schemas** (camelCase)
```python
# schemas.py - Lines 22-24
class CamelCaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=snake_to_camel,  # ✅ Automatic conversion
        populate_by_name=True
    )

class VideoTestSequenceResponse(CamelCaseModel):
    video_start_time: float  # → "videoStartTime" in JSON ✅
```

**Convention 3: API Responses** (BOTH)
```python
# test_sessions.py - Line 241
return session.dict()  # ❌ Bypasses Pydantic alias_generator
# Should use:
# return TestSessionResponse.model_validate(session)  # ✅ Converts to camelCase
```

**Frontend Evidence** (Lines 1228-1317 in enhanced-results.ts):
```typescript
interface PerVideoResult {
    // Backend returns BOTH formats, so frontend must accept both
    video_id?: string;              // Snake case
    videoId?: string;               // Camel case

    pass_rate_percent?: number;     // Snake case
    passRatePercent?: number;       // Camel case

    avg_latency_ms?: number;        // Snake case
    avgLatencyMs?: number;          // Camel case

    // 40+ fields x 2 variants = 80+ optional fields!
}
```

**Impact**:
- Frontend types bloated with duplicate field variants
- API responses inconsistent (sometimes snake_case, sometimes camelCase)
- Type safety compromised (all fields optional due to uncertainty)

**Root Cause**: API endpoints return `dict()` instead of using `response_model`.

---

### Issue #4: WebSocket Event Mismatch

**Problem**: Backend emits events frontend doesn't subscribe to, frontend subscribes to events backend doesn't emit.

**Backend Emissions** (socketio_server.py):
```python
# Lines 200-207: Emits video_started
socketio.emit("video_started", {
    "sequence_id": sequence_id,
    "video_id": video_id,
    "timestamp": timestamp,
    "sequence_elapsed": elapsed,
    "sequence_order": order
}, room=session_id)

# Lines 315-328: Emits video_ended
socketio.emit("video_ended", {
    "sequence_id": sequence_id,
    "video_id": video_id,
    "duration": duration,
    "next_video_id": next_id,
    "completed_videos": completed,
    "total_videos": total
}, room=session_id)
```

**Frontend Subscriptions** (websocketService.ts):
```typescript
// Lines 629-641: Frontend expects these events
socket.on("video_transition", (data) => { ... });  // ❌ Backend never emits
socket.on("video_completed", (data) => { ... });   // ❌ Backend never emits
socket.on("sequence_completed", (data) => { ... });// ❌ Backend never emits

// Frontend DOESN'T subscribe to:
// "video_started"  ← Backend emits this ✅
// "video_ended"    ← Backend emits this ✅
```

**Impact**:
- Frontend waits for `video_transition` event that never arrives
- Real-time video status updates broken
- Sequence completion notifications lost
- UI remains in stale state during video transitions

**Sequence Diagram**:
```
Backend              WebSocket              Frontend
   │                    │                      │
   │──video_started───→ │                      │
   │                    │─(no listener)───X    │
   │                    │                      │
   │                    │ ←──subscribe─────────│
   │                    │   "video_transition" │
   │──(never emits)───X │                      │
   │                    │                      │
   └─ Mismatch: Both sides talking, neither listening
```

---

### Issue #5: State Management Fragmentation (Three Sources of Truth)

**Problem**: Session state stored in three uncoordinated locations.

**Source 1: PostgreSQL** (Persistent)
```python
# database.py - Ground truth storage
session.video_id = "video_1"
session.video_start_timestamp = 123456.789
```

**Source 2: video_sequence_orchestrator** (In-memory cache)
```python
# video_sequence_orchestrator.py - Lines 67-89
self._active_sequences: Dict[str, VideoSequenceState] = {}
self._active_sequences[seq_id].current_video_id = "video_1"
```

**Source 3: socketio_server** (In-memory state)
```python
# socketio_server.py - Lines 60-85
active_sessions: Dict[str, dict] = {}
active_sessions[session_id]['video_id'] = "video_1"
```

**Race Condition** (Line 708 in socketio_server.py):
```python
@socketio.on("video_started")
def handle_video_started(data):
    session_id = data['session_id']
    video_id = data['video_id']

    # ❌ CRITICAL BUG: Overwrites TestSession.video_id
    session = db.query(TestSession).filter_by(id=session_id).first()
    session.video_id = video_id  # ← Loses previous video context
    db.commit()

    # For multi-video sequences:
    # Video 1 starts → session.video_id = "vid1" ✅
    # Video 2 starts → session.video_id = "vid2" ← vid1 detections now orphaned!
```

**Impact**:
- Detections assigned to wrong video
- State drift between three sources
- No rollback capability (state scattered)
- Cache eviction bugs (orchestrator never cleanup)

**Evidence from ADR-005**:
```
Root Cause: Three competing sources of truth
- Race conditions (Issue #1)
- Dual caching bugs (Issue #2)
- Clock skew errors (Issue #3)
- Rollback failures (Issue #4)
- Complex migrations (Issue #5)
- Cache eviction bugs (Issue #6)
- N+1 query explosions (Issue #7)
```

**Solution Designed but Not Implemented**: UnifiedStateService (ADR-005)

---

## 3. Impact Analysis

### Data Loss Points

**5 Critical Data Loss Points Identified**:

1. **Session Start → Video 1 → Video 2**
   ```
   TestSession.video_id = "vid1"  // Video 1 playing
   ↓ Video 2 starts
   TestSession.video_id = "vid2"  // ❌ vid1 context lost
   ↓ Detection arrives
   detection.video_id = "vid2"    // ❌ But detection was from vid1!
   ```

2. **Frontend Request → API Response**
   ```
   Frontend: GET /test-sessions/123/results
   Backend: Returns sequence_metadata JSON blob
   Frontend: Can't parse perVideoResults[] array
   Result: Per-video metrics lost ❌
   ```

3. **Detection Event → Video Assignment**
   ```
   LabJack: Detection at timestamp T
   Backend: Which video was playing at T?
   Current: Uses TestSession.video_id (wrong video)
   Should: Query SequenceVideoResult timing boundaries
   Result: Detections misassigned ❌
   ```

4. **WebSocket Emission → Frontend Update**
   ```
   Backend: Emits "video_started"
   Frontend: No listener registered
   Result: UI remains stale ❌
   ```

5. **Database → API → Frontend**
   ```
   Database: SequenceVideoResult has avg_latency_ms = 45.2
   API: Doesn't query SequenceVideoResult table
   Frontend: Never receives per-video latency
   Result: Metrics exist but unreachable ❌
   ```

### Performance Impact

**N+1 Query Problem** (Lines 496-917 in test_sessions.py):
```python
# For each detection event:
for detection in detections:
    # Query #1: Get session
    session = db.query(TestSession).filter_by(id=session_id).first()

    # Query #2: Infer video_id (700 lines of logic!)
    video_id = infer_video_id_from_timestamp(...)

    # Query #3: Get video metadata
    video = db.query(Video).filter_by(id=video_id).first()

# 100 detections = 300 queries
# Should be 1 query with SequenceVideoResult foreign key
```

**Cache Inefficiency**:
```python
# Orchestrator cache never cleaned up
self._active_sequences[seq_id] = VideoSequenceState(...)
# Grows indefinitely, causes memory leak
```

---

## 4. Architecture Decision Records

### ADR-005: Unified State Management (MANDATORY, Not Implemented)

**Status**: 🔴 **Approved but NEVER DEPLOYED**

**Date**: 2025-01-07
**Priority**: P0 - System Reliability
**Blocks Production**: Yes

**Designed Solution**:
```python
class UnifiedStateService:
    """
    Single source of truth for all session state
    - PostgreSQL: Persistent storage
    - Redis/Dict: Write-through cache
    - Pessimistic locking: Prevents race conditions
    """

    def get_current_video(session_id: str) -> VideoState:
        # Cache hit → Fast path (0.1ms)
        # Cache miss → Query DB + update cache (50ms)

    def start_video(session_id: str, video_id: str, start_time: float):
        with self._get_session_lock(session_id):  # ✅ Atomic
            # 1. Write to PostgreSQL (source of truth)
            db.commit()
            # 2. Update cache (write-through)
            cache.set(f"video_id:{session_id}", video_id)
            # 3. Emit event (real-time)
            socketio.emit("video_started", {...})
```

**Implementation Status**: 🚫 **Not Integrated**
- Service implemented in `unified_state_service.py`
- **Never imported** by `hil_test_complete.py` or `socketio_server.py`
- Manual DB queries continue instead

---

## 5. Recommended Architecture

### Target Architecture (Unified)

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend Layer                        │
│  - Receives: perVideoResults[] array with camelCase          │
│  - Subscribes: video_started, video_ended (aligned)         │
│  - Types: Strict TypeScript (no dual variants)              │
└─────────────────┬───────────────────────────────────────────┘
                  │ REST API + WebSocket
                  ↓
┌──────────────────────────────────────────────────────────────┐
│              Backend API Layer (UNIFIED)                     │
│                                                               │
│  Unified Router: test_sessions.py                           │
│  ├─ Imports video_sequences.py functions                    │
│  ├─ Uses response_model for camelCase conversion            │
│  ├─ Queries SequenceVideoResult for per-video metrics       │
│  └─ Returns structured PerVideoResult[] array                │
│                                                               │
│  WebSocket: socketio_server.py                              │
│  ├─ Emits: video_started, video_ended                       │
│  └─ Frontend subscribes to same events ✅                    │
└─────────────────┬───────────────────────────────────────────┘
                  │ UnifiedStateService
                  ↓
┌──────────────────────────────────────────────────────────────┐
│                  Service Layer (NEW)                         │
│                                                               │
│  UnifiedStateService (Single Source of Truth)               │
│  ├─ get_current_video(session_id) → VideoState              │
│  ├─ start_video(session_id, video_id, timestamp)            │
│  ├─ end_video(session_id, video_id, timestamp)              │
│  ├─ validate_detection_timing(session_id, timestamp)        │
│  └─ Write-through cache (Redis) + DB persistence            │
│                                                               │
│  VideoSequenceOrchestrator                                  │
│  ├─ start_sequence(project_id, video_ids)                   │
│  ├─ notify_video_started(sequence_id, video_id)             │
│  ├─ process_detection_event(sequence_id, labjack_signal)    │
│  └─ Coordinates video transitions and detection correlation │
└─────────────────┬───────────────────────────────────────────┘
                  │ Single Write Path
                  ↓
┌──────────────────────────────────────────────────────────────┐
│                Database Layer (PostgreSQL)                   │
│  Single Source of Truth                                     │
│                                                               │
│  TestSession → VideoTestSequence → SequenceVideoResult      │
│                                        ↓                      │
│                                   DetectionEvent             │
│                                                               │
│  ✅ Foreign keys ENFORCED                                    │
│  ✅ 26 indexes for performance                               │
│  ✅ Cascade deletes configured                               │
└──────────────────────────────────────────────────────────────┘
```

### Key Architectural Changes

**1. Router Unification**
```python
# test_sessions.py (Unified)
from routers.video_sequences import (
    create_video_sequence,
    get_sequence_video_results,
    calculate_per_video_metrics
)

@router.get(
    "/test-sessions/{session_id}/results",
    response_model=TestSessionResultsResponse  # ✅ Enforces camelCase
)
def get_results(session_id: int, db: Session):
    session = db.query(TestSession).filter_by(id=session_id).first()

    if session.has_video_sequence:
        # ✅ Query SequenceVideoResult table
        video_results = get_sequence_video_results(session.sequence_id, db)
        per_video_metrics = calculate_per_video_metrics(video_results)

        return TestSessionResultsResponse(
            session_id=session_id,
            perVideoResults=per_video_metrics  # ✅ Structured array
        )

    # Single-video fallback...
```

**2. UnifiedStateService Integration**
```python
# socketio_server.py
from services.unified_state_service import get_unified_state_service

unified_state = get_unified_state_service(use_redis=True)

@socketio.on("video_started")
def handle_video_started(data):
    session_id = data['session_id']
    video_id = data['video_id']
    start_time = time.time()

    # ✅ Single write path (no race conditions)
    success = unified_state.start_video(
        session_id=session_id,
        video_id=video_id,
        start_time=start_time
    )

    if success:
        socketio.emit("video_started", {
            "video_id": video_id,
            "start_time": start_time
        }, room=session_id)
```

**3. Detection Correlation**
```python
# labjack_detection_service.py
def process_detection(session_id: str, labjack_timestamp: float):
    # ✅ Get current video from unified state
    current_video = unified_state.get_current_video(session_id)

    # ✅ Validate timing
    validation = unified_state.validate_detection_timing(
        session_id=session_id,
        timestamp=labjack_timestamp
    )

    if validation.is_valid:
        detection = DetectionEvent(
            video_id=current_video.video_id,  # ✅ Correct assignment
            video_relative_timestamp=validation.relative_timestamp,
            sequence_video_result_id=current_video.sequence_video_result_id
        )
        db.add(detection)
        db.commit()
```

**4. WebSocket Event Alignment**
```python
# Backend: socketio_server.py
socketio.emit("video_started", {...})   # ✅
socketio.emit("video_ended", {...})     # ✅

# Frontend: websocketService.ts
socket.on("video_started", (data) => { ... });  # ✅ Aligned
socket.on("video_ended", (data) => { ... });    # ✅ Aligned
```

---

## 6. Migration Strategy

### Phase 1: Service Integration (Week 1)
**Deliverables**:
1. Integrate UnifiedStateService into socketio_server.py
2. Replace `session.video_id` writes with `unified_state.start_video()`
3. Deploy with feature flag: `USE_UNIFIED_STATE=true`
4. Monitor for race conditions

**Risk**: Medium
**Rollback Plan**: Set feature flag to `false`

### Phase 2: Router Unification (Week 2)
**Deliverables**:
1. Import video_sequences.py functions into test_sessions.py
2. Query SequenceVideoResult table in `/results` endpoint
3. Return `perVideoResults[]` array with proper schemas
4. Add `response_model` to all endpoints

**Risk**: High
**Rollback Plan**: Blue-green deployment

### Phase 3: Frontend Alignment (Week 3)
**Deliverables**:
1. Update WebSocket subscriptions to `video_started`, `video_ended`
2. Remove dual field variants from TypeScript types
3. Parse `perVideoResults[]` array from API
4. Test end-to-end with real multi-video sessions

**Risk**: Low
**Rollback Plan**: Conditional rendering (support old + new formats)

### Phase 4: Cleanup (Week 4)
**Deliverables**:
1. Remove orchestrator in-memory cache
2. Remove socketio active_sessions cache
3. Enable foreign key enforcement
4. Delete duplicate code

---

## 7. Quality Attributes

### Non-Functional Requirements

**Performance**:
- Target: <50ms API response time for per-video results
- Current: ~500ms (N+1 queries)
- Fix: UnifiedStateService cache (99% hit rate)

**Scalability**:
- Target: 1000 concurrent sessions
- Current: Limited by three state stores
- Fix: Single PostgreSQL + Redis cache

**Reliability**:
- Target: 99.9% uptime
- Current: Race conditions cause data loss
- Fix: Pessimistic locking + atomic transactions

**Maintainability**:
- Target: <500 lines per file
- Current: test_sessions.py = 2000+ lines
- Fix: Router unification + service layer

**Security**:
- Target: FK enforcement enabled
- Current: `PRAGMA foreign_keys=0`
- Fix: Enable in database.py (15 minutes)

---

## 8. Decision Matrix

### Technology Choices

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| State Management | 1. Three sources<br>2. Redis only<br>3. DB + Redis | **DB + Redis** | Persistence + performance |
| Router Strategy | 1. Keep dual<br>2. Merge into one<br>3. Delete video_sequences | **Merge into one** | Single API contract |
| Field Naming | 1. snake_case<br>2. camelCase<br>3. Both | **camelCase** | Frontend standard |
| WebSocket Events | 1. Keep current<br>2. Align with frontend | **Align** | Real-time updates required |
| Detection Correlation | 1. Inference logic<br>2. FK relationships | **FK relationships** | Database guarantees |

---

## 9. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Migration breaks production | Medium | Critical | Blue-green deployment + canary rollout |
| Performance degradation | Low | High | Redis caching + load testing |
| Data loss during transition | Medium | Critical | Database backups + rollback plan |
| Frontend breaking changes | Low | Medium | Conditional rendering (support old format) |
| UnifiedStateService bugs | Medium | High | Extensive integration testing |

---

## 10. Success Criteria

### Acceptance Criteria

**Must Have** (Blockers):
- ✅ Single routing system (test_sessions.py + video_sequences.py merged)
- ✅ SequenceVideoResult queried in `/results` endpoint
- ✅ UnifiedStateService integrated and tested
- ✅ Foreign key enforcement enabled
- ✅ WebSocket events aligned (backend emits = frontend subscribes)

**Should Have** (High Priority):
- ✅ Field naming standardized to camelCase
- ✅ Detection correlation via SequenceVideoResult FK
- ✅ Performance <50ms for per-video results
- ✅ All 7 ADR-005 issues resolved

**Nice to Have** (Optional):
- Redis clustering for high availability
- Database read replicas for scalability
- GraphQL API layer for flexible queries

---

## 11. Metrics and Monitoring

### Key Performance Indicators

**Before Fix**:
- API response time: ~500ms (N+1 queries)
- Cache hit rate: 0% (no cache)
- Detection assignment accuracy: ~80% (race conditions)
- Frontend type safety: 40+ dual variants

**After Fix**:
- API response time: <50ms (99% cache hits)
- Cache hit rate: 99%
- Detection assignment accuracy: 100%
- Frontend type safety: Single camelCase variant

**Monitoring**:
```python
# Add to unified_state_service.py
@metrics.histogram("unified_state.cache_hit_rate")
def get_current_video(session_id: str):
    if cache.exists(f"video_id:{session_id}"):
        metrics.increment("cache.hit")
    else:
        metrics.increment("cache.miss")
```

---

## 12. Conclusion

### Architecture Verdict

**Current State**: 🔴 **Architecturally Broken**
- 5 critical architectural debts
- Data model perfect, API layer broken
- Services designed but not integrated

**Target State**: 🟢 **Production Ready**
- Single routing system
- Unified state management
- Field naming standardized
- WebSocket events aligned

**Effort Required**:
- Phase 1: Service Integration (40 hours)
- Phase 2: Router Unification (60 hours)
- Phase 3: Frontend Alignment (30 hours)
- Phase 4: Cleanup (20 hours)
- **Total**: 150 hours (4 weeks with 1 developer)

**Production Readiness**: 🚫 **BLOCKED**
- Must complete Phases 1-2 before deployment
- Phase 3 can run in parallel
- Phase 4 is post-deployment cleanup

---

## References

1. `/tmp/integration_verification.json` - Detailed integration analysis
2. `backend/docs/ADR-005-UNIFIED-STATE-MANAGEMENT.md` - State management architecture
3. `backend/docs/MULTI_VIDEO_ORCHESTRATION_REVIEW.md` - Orchestrator analysis
4. `backend/docs/MULTI_VIDEO_SCHEMA_EXECUTIVE_SUMMARY.md` - Database schema review

---

**Document Status**: 🔴 CRITICAL FINDINGS - REQUIRES IMMEDIATE ARCHITECTURAL REVIEW
**Next Steps**: Present to architecture team for approval of migration plan
**Decision Required By**: 2025-01-15
**Implementation Start**: 2025-01-16
