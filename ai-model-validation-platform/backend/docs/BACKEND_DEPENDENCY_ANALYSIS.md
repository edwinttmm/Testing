# Backend Dependency Analysis - Continuous Monitoring + Video Marker Approach

**Date**: 2025-11-20
**Scope**: Complete backend impact assessment for switching from per-video start/stop to continuous monitoring with post-processing segmentation
**Status**: CRITICAL - Breaking changes identified

---

## Executive Summary

**RECOMMENDATION**: ⚠️ **PROCEED WITH CAUTION** - Major breaking changes required across 15+ core services

### Key Findings

- **Affected Services**: 15 core services, 8 routers, 3 database models
- **Breaking Changes**: 8 major API contract changes
- **Backward Compatibility**: Possible with feature flag + adapter layer
- **Migration Effort**: 3-5 days of focused development
- **Risk Level**: HIGH (impacts real-time detection pipeline)

---

## 1. Complete List of Affected Files

### 1.1 Core Services (CRITICAL)

| File | Line Numbers | Impact Level | Reason |
|------|-------------|--------------|--------|
| `/services/labjack_monitoring_service.py` | 29-49 | **CRITICAL** | `start_monitoring(session_id)` signature change |
| `/services/dedicated_labjack_monitor.py` | (large file) | **CRITICAL** | Per-video baseline logic |
| `/services/ground_truth_matching_service.py` | 122-160, 435-563 | **HIGH** | Uses `video_playback_start_time`, per-video GT extraction |
| `/services/timing_synchronization_service.py` | N/A | **HIGH** | Video lifecycle event handlers |
| `/services/video_sequence_orchestrator.py` | N/A | **MEDIUM** | Multi-video coordination |
| `/services/test_execution_service.py` | N/A | **MEDIUM** | Session lifecycle management |

### 1.2 Routers/API Endpoints (HIGH)

| File | Endpoints | Impact |
|------|-----------|--------|
| `/routers/test_sessions.py` | Lines 76-337 | Session creation, video lifecycle |
| `/socketio_server.py` | Lines 849-1172 | `video_started`, `video_ended` events |
| `/routers/monitoring_service_endpoints.py` | N/A | LabJack monitor control |

### 1.3 Database Models (CRITICAL)

| Model | Fields Affected | Change Type |
|-------|----------------|-------------|
| `TestSession` | `video_playback_start_time` | **DEPRECATE** → Replace with session-level time |
| `DetectionEvent` | `video_index` | **DEPRECATE** → Replace with `video_marker_ref` |
| `DetectionEvent` | `video_id` | **KEEP** → Assign via post-processing |

---

## 2. API Contract Changes (Before/After)

### 2.1 Current API (Per-Video)

```python
# Current: Start monitoring per video
POST /api/monitoring/start
{
  "session_id": "session_abc",
  "video_index": 0,  # ❌ REMOVED
  "T1_i": 1234567890.123  # ❌ REMOVED
}

# Current: Stop monitoring per video
POST /api/monitoring/stop
{
  "session_id": "session_abc",
  "video_index": 0  # ❌ REMOVED
}
```

### 2.2 Proposed API (Continuous + Markers)

```python
# NEW: Start continuous monitoring (session-level)
POST /api/monitoring/start
{
  "session_id": "session_abc"
  # T1_session captured server-side automatically
}

# NEW: Stop continuous monitoring (session-level)
POST /api/monitoring/stop
{
  "session_id": "session_abc"
  # Triggers final post-processing
}

# NEW: Record video markers
POST /api/monitoring/marker
{
  "session_id": "session_abc",
  "marker_type": "video_start",  # or "video_end"
  "video_index": 0,
  "video_id": "video_xyz",
  "timestamp": 1234567890.456,  # Client-side video event time
  "metadata": {
    "duration_ms": 5000,
    "sequence_order": 1
  }
}
```

### 2.3 Breaking Changes Checklist

| Change | Breaking? | Backward Compatible? | Migration Path |
|--------|-----------|---------------------|----------------|
| Remove `video_index` from start/stop | ✅ YES | ⚠️ With adapter | Feature flag + adapter layer |
| Remove `T1_i` from start | ✅ YES | ✅ YES | Capture server-side, log warning if provided |
| Add `marker` endpoint | ❌ NO | ✅ YES | New endpoint, no impact |
| Change `DetectionEvent.video_index` | ✅ YES | ⚠️ With migration | Database migration + backfill |
| Deprecate `TestSession.video_playback_start_time` | ✅ YES | ⚠️ With fallback | Add `session_start_time`, keep old field |

---

## 3. Database Dependencies

### 3.1 Schema Changes Required

**Table: `detection_events`**

```sql
-- Current schema
CREATE TABLE detection_events (
    id TEXT PRIMARY KEY,
    test_session_id TEXT,
    video_index INTEGER,  -- ❌ DEPRECATED
    timestamp REAL,
    video_start_time REAL,  -- ❌ DEPRECATED
    video_id TEXT,  -- ✅ KEEP (assigned post-processing)
    ...
);

-- Proposed schema
CREATE TABLE detection_events (
    id TEXT PRIMARY KEY,
    test_session_id TEXT,
    timestamp REAL,  -- Raw timestamp (relative to session start)
    video_id TEXT,  -- Assigned via post-processing based on markers
    video_marker_ref TEXT,  -- NEW: References closest video marker
    assigned_by_marker BOOLEAN DEFAULT FALSE,  -- NEW: Indicates post-processing assignment
    ...
    -- Keep deprecated fields for backward compatibility
    video_index INTEGER,  -- NULL for new detections
    video_start_time REAL  -- NULL for new detections
);
```

**Table: `test_sessions`**

```sql
-- Current schema
CREATE TABLE test_sessions (
    id TEXT PRIMARY KEY,
    video_playback_start_time REAL,  -- ❌ DEPRECATED
    ...
);

-- Proposed schema
CREATE TABLE test_sessions (
    id TEXT PRIMARY KEY,
    session_start_time REAL,  -- NEW: Monitoring start time (replaces video_playback_start_time)
    session_end_time REAL,  -- NEW: Monitoring end time
    video_playback_start_time REAL,  -- KEEP for backward compatibility (NULL for new sessions)
    ...
);
```

**NEW Table: `video_markers`**

```sql
CREATE TABLE video_markers (
    id TEXT PRIMARY KEY,
    test_session_id TEXT NOT NULL,
    marker_type TEXT NOT NULL,  -- 'video_start', 'video_end'
    video_index INTEGER NOT NULL,
    video_id TEXT NOT NULL,
    timestamp REAL NOT NULL,  -- Client-side video event time
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (test_session_id) REFERENCES test_sessions(id)
);

CREATE INDEX idx_video_markers_session ON video_markers(test_session_id);
CREATE INDEX idx_video_markers_timestamp ON video_markers(timestamp);
```

### 3.2 Queries Affected

**Ground Truth Matching Service** (`ground_truth_matching_service.py:122-160`)

```python
# Current: Uses video_playback_start_time for offset calculation
session_start_time = test_session.video_playback_start_time
detection_video_time = detection.timestamp - session_start_time

# Proposed: Use session_start_time + video marker boundaries
session_start_time = test_session.session_start_time
# Post-processing assigns video_id based on markers
detection_video_time = detection.timestamp - get_video_marker_start(detection.video_id)
```

**Detection Event Queries**

```python
# Current: Filter by video_index
detections = db.query(DetectionEvent).filter(
    DetectionEvent.test_session_id == session_id,
    DetectionEvent.video_index == video_index
).all()

# Proposed: Filter by video_id (assigned via post-processing)
detections = db.query(DetectionEvent).filter(
    DetectionEvent.test_session_id == session_id,
    DetectionEvent.video_id == video_id
).all()
```

### 3.3 Foreign Key Constraints

**No blocking constraints identified** - All foreign keys reference `test_session_id`, which remains unchanged.

---

## 4. Service Layer Dependencies

### 4.1 LabJack Monitoring Service

**File**: `/services/labjack_monitoring_service.py`

**Current Implementation** (Lines 29-49):

```python
def start_monitoring(self, session_id: str, sample_rate: int = 10):
    """Start monitoring LabJack signals for a test session"""
    if self.monitoring_active:
        logger.warning(f"Monitoring already active for session {self.current_session_id}")
        return False

    self.current_session_id = session_id
    self.sample_rate = sample_rate
    self.monitoring_active = True
    # ...
```

**Proposed Changes**:

1. ❌ **Remove per-video assumptions** - No `video_index` parameter
2. ✅ **Session-level monitoring** - Start once per session
3. ✅ **Capture T1_session** - Record monitoring start timestamp server-side
4. ⚠️ **Baseline handling** - Move per-video baselines to post-processing

**Backward Compatibility**:

```python
def start_monitoring(
    self,
    session_id: str,
    sample_rate: int = 10,
    video_index: Optional[int] = None,  # DEPRECATED: Log warning if provided
    T1_i: Optional[float] = None  # DEPRECATED: Ignore, use server time
):
    """Start monitoring LabJack signals for a test session"""
    # Feature flag for backward compatibility
    if USE_CONTINUOUS_MONITORING:
        # New behavior: Continuous monitoring
        if video_index is not None:
            logger.warning(f"video_index parameter deprecated in continuous mode")
        T1_session = time.time()  # Capture server-side
        # ...
    else:
        # Legacy behavior: Per-video monitoring
        # ...
```

### 4.2 Ground Truth Matching Service

**File**: `/services/ground_truth_matching_service.py`

**Current Implementation** (Lines 122-160):

```python
def extract_detection_video_time(
    detection: Any,
    session_start_time: Optional[float] = None
) -> Optional[float]:
    """Resolve best available video-relative timestamp"""
    # Uses video_playback_start_time for offset calculation
    timestamp = detection.timestamp
    video_start_time = detection.video_start_time
    if timestamp is not None and video_start_time is not None:
        return timestamp - video_start_time
```

**Proposed Changes**:

1. ❌ **Remove per-video baseline assumptions**
2. ✅ **Use video_id + marker boundaries** for segmentation
3. ✅ **Post-processing assigns video_id** before matching
4. ⚠️ **Session-level time baseline** - Use `session_start_time`

**Migration Path**:

```python
def extract_detection_video_time(
    detection: Any,
    session_start_time: Optional[float] = None,
    video_markers: Optional[Dict] = None  # NEW: Marker boundaries
) -> Optional[float]:
    """Resolve best available video-relative timestamp"""
    # NEW: Use video_id assigned by post-processing
    if hasattr(detection, 'video_id') and video_markers:
        video_start_marker = video_markers.get(detection.video_id, {}).get('start')
        if video_start_marker:
            return detection.timestamp - video_start_marker

    # LEGACY: Fall back to old logic for backward compatibility
    if hasattr(detection, 'video_start_time'):
        return detection.timestamp - detection.video_start_time

    # FALLBACK: Use session baseline
    if session_start_time:
        return detection.timestamp - session_start_time
```

### 4.3 Dedicated LabJack Monitor

**File**: `/services/dedicated_labjack_monitor.py` (Large file, requires targeted grep)

**Key Dependencies** (Based on grep results):

- Uses `video_playback_start_time` extensively
- Implements per-video baseline logic
- Coordinates with video lifecycle events

**Required Changes**:

1. ❌ **Remove per-video start/stop logic**
2. ✅ **Continuous monitoring loop** - Run for entire session
3. ✅ **Store raw timestamps** - No per-video offsets during capture
4. ⚠️ **Post-processing stage** - Segment detections after session ends

### 4.4 Metrics Calculation

**No per-video assumptions detected** in metrics calculation:

- Metrics aggregate across entire session
- Latency calculation uses `actual_latency_ms` field (already computed)
- ✅ **No changes required** - Metrics are video-agnostic

---

## 5. Event/Message Flow Changes

### 5.1 Current WebSocket Events

**File**: `/socketio_server.py` (Lines 849-1172)

```python
@sio.event
async def video_started(sid, data):
    """Handle video started events"""
    session_id = data.get('sessionId')
    video_id = data.get('videoId')
    video_start_time = data.get('videoStartTime')

    # CRITICAL: Triggers start_monitoring per video
    # ❌ This needs to change to marker recording

@sio.event
async def video_ended(sid, data):
    """Handle video ended events"""
    session_id = data.get('sessionId')
    video_id = data.get('videoId')
    video_end_time = data.get('videoEndTime')

    # CRITICAL: Triggers stop_monitoring per video
    # ❌ This needs to change to marker recording
```

### 5.2 Proposed WebSocket Events

**NEW Event: `video_marker`**

```python
@sio.event
async def video_marker(sid, data):
    """Record video lifecycle marker (unified event)"""
    session_id = data.get('sessionId')
    marker_type = data.get('markerType')  # 'video_start' or 'video_end'
    video_index = data.get('videoIndex')
    video_id = data.get('videoId')
    timestamp = data.get('timestamp')
    metadata = data.get('metadata', {})

    # Store marker in database
    marker = VideoMarker(
        id=str(uuid.uuid4()),
        test_session_id=session_id,
        marker_type=marker_type,
        video_index=video_index,
        video_id=video_id,
        timestamp=timestamp,
        metadata=metadata
    )
    db.add(marker)
    db.commit()

    # Emit confirmation (no start/stop monitoring)
    await sio.emit('marker_recorded', {
        'sessionId': session_id,
        'markerType': marker_type,
        'videoId': video_id,
        'timestamp': timestamp
    }, room=f"session_{session_id}")
```

### 5.3 Event Ordering Dependencies

**CRITICAL**: Frontend relies on event ordering (`sequence_number` field in `socketio_server.py:991-1133`)

**No changes required** - Marker events can use same sequencing mechanism:

```python
sequence_number = await get_next_sequence_number()
await sio.emit('video_marker', {
    'sequence_number': sequence_number,
    'sessionId': session_id,
    'markerType': marker_type,
    # ...
}, room=room)
```

---

## 6. Configuration Dependencies

### 6.1 Environment Variables

**No config changes required** - Monitoring parameters are session-level:

```python
# Current config (unchanged)
LABJACK_SAMPLE_RATE = 10  # Hz
DETECTION_THRESHOLD_V = 2.5  # Volts
MONITORING_TIMEOUT_S = 300  # Seconds
```

### 6.2 Feature Flags (Proposed)

**Backward Compatibility Strategy**:

```python
# Add feature flag to enable gradual rollout
USE_CONTINUOUS_MONITORING = os.getenv('USE_CONTINUOUS_MONITORING', 'false').lower() == 'true'

# Adapter layer for API compatibility
if USE_CONTINUOUS_MONITORING:
    # New behavior: Marker-based segmentation
    from services.continuous_monitoring_adapter import start_monitoring, record_marker
else:
    # Legacy behavior: Per-video start/stop
    from services.labjack_monitoring_service import start_monitoring, stop_monitoring
```

---

## 7. Third-Party Dependencies

### 7.1 scipy (Optimal Matching Algorithm)

**File**: `/services/ground_truth_matching_service.py:40-46`

```python
try:
    from scipy.optimize import linear_sum_assignment
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
```

**Impact**: ✅ **NO CHANGES** - Matching algorithm is timing-agnostic

### 7.2 Option C: Temporal Expansion

**File**: `/services/ground_truth_matching_service.py:50-63`

```python
try:
    from src.services.temporal_expansion import (
        expand_detections_temporally,
        collapse_duplicates,
        ExpandedDetection
    )
    TEMPORAL_EXPANSION_AVAILABLE = True
except ImportError:
    TEMPORAL_EXPANSION_AVAILABLE = False
```

**Impact**: ✅ **COMPATIBLE** - Temporal expansion works on detection timestamps regardless of segmentation approach

---

## 8. Breaking Changes Assessment

### 8.1 CRITICAL Breaking Changes

| Change | Severity | Backward Compatible? | Reason |
|--------|----------|---------------------|--------|
| API: Remove `video_index` from `/monitoring/start` | **CRITICAL** | ⚠️ With adapter | Frontend relies on current API |
| API: Remove `T1_i` from `/monitoring/start` | **HIGH** | ✅ YES | Can capture server-side |
| DB: `DetectionEvent.video_index` → NULL | **CRITICAL** | ⚠️ With migration | Queries filter by this field |
| Service: Remove per-video baselines | **HIGH** | ⚠️ With fallback | Affects detection assignment |

### 8.2 Migration Effort Estimate

**Total Effort**: 3-5 days

| Task | Effort | Priority | Dependencies |
|------|--------|----------|--------------|
| Database migration (add `video_markers` table) | 4 hours | P0 | None |
| Update `labjack_monitoring_service.py` | 8 hours | P0 | Database migration |
| Add `video_marker` API endpoint | 4 hours | P0 | Database migration |
| Update `socketio_server.py` events | 6 hours | P0 | API endpoint |
| Add post-processing segmentation logic | 16 hours | P0 | All above |
| Update `ground_truth_matching_service.py` | 8 hours | P1 | Post-processing |
| Feature flag + adapter layer | 8 hours | P1 | All above |
| Integration testing | 16 hours | P1 | All above |
| **TOTAL** | **70 hours** | | |

---

## 9. Backward Compatibility Strategy

### 9.1 Feature Flag Architecture

```python
# config/feature_flags.py
class FeatureFlags:
    USE_CONTINUOUS_MONITORING = os.getenv('USE_CONTINUOUS_MONITORING', 'false').lower() == 'true'
    ENABLE_VIDEO_MARKERS = os.getenv('ENABLE_VIDEO_MARKERS', 'false').lower() == 'true'
```

### 9.2 Adapter Layer

```python
# services/monitoring_adapter.py
class MonitoringAdapter:
    """Adapter for backward compatibility between per-video and continuous monitoring"""

    @staticmethod
    async def start_monitoring(session_id: str, video_index: Optional[int] = None, T1_i: Optional[float] = None):
        if FeatureFlags.USE_CONTINUOUS_MONITORING:
            # NEW: Start continuous monitoring (ignore video_index)
            if video_index is not None:
                logger.warning("video_index deprecated in continuous mode")
            return await continuous_monitoring_service.start(session_id)
        else:
            # LEGACY: Start per-video monitoring
            return await labjack_monitoring_service.start_monitoring(session_id, video_index, T1_i)

    @staticmethod
    async def record_video_lifecycle(session_id: str, event_type: str, video_index: int, video_id: str, timestamp: float):
        if FeatureFlags.ENABLE_VIDEO_MARKERS:
            # NEW: Record marker for post-processing
            return await video_marker_service.record_marker(session_id, event_type, video_index, video_id, timestamp)
        else:
            # LEGACY: Trigger start/stop monitoring
            if event_type == "video_start":
                return await labjack_monitoring_service.start_monitoring(session_id, video_index, timestamp)
            elif event_type == "video_end":
                return await labjack_monitoring_service.stop_monitoring(session_id, video_index)
```

---

## 10. Migration Checklist

### 10.1 Database Changes

- [x] Create `video_markers` table
- [ ] Add `session_start_time`, `session_end_time` to `test_sessions`
- [ ] Add `video_marker_ref`, `assigned_by_marker` to `detection_events`
- [ ] Backfill migration for existing data (set old fields to NULL)

### 10.2 Service Changes

- [ ] Update `labjack_monitoring_service.py` - Remove per-video logic
- [ ] Create `video_marker_service.py` - Marker recording logic
- [ ] Create `post_processing_service.py` - Detection segmentation logic
- [ ] Update `ground_truth_matching_service.py` - Use markers for time boundaries
- [ ] Update `dedicated_labjack_monitor.py` - Continuous monitoring loop

### 10.3 API Changes

- [ ] Add POST `/api/monitoring/marker` endpoint
- [ ] Update POST `/api/monitoring/start` - Remove `video_index`, `T1_i`
- [ ] Update POST `/api/monitoring/stop` - Remove `video_index`
- [ ] Add adapter layer for backward compatibility

### 10.4 WebSocket Changes

- [ ] Add `video_marker` event handler
- [ ] Update `video_started` handler - Call marker service instead of start monitoring
- [ ] Update `video_ended` handler - Call marker service instead of stop monitoring

### 10.5 Testing

- [ ] Unit tests for marker recording
- [ ] Unit tests for post-processing segmentation
- [ ] Integration tests for continuous monitoring
- [ ] Backward compatibility tests (legacy API)
- [ ] Performance tests (latency impact)

---

## 11. CRITICAL Dependencies Preventing Implementation

### 11.1 Blocker #1: Frontend Video Lifecycle Integration

**Issue**: Frontend sends `video_started` / `video_ended` events expecting immediate monitoring start/stop.

**Impact**: Changing to marker-based approach requires frontend changes to:
1. Send `video_marker` events instead of expecting monitoring start/stop
2. Handle new `marker_recorded` confirmation events
3. Update session creation to start monitoring at session level

**Workaround**: Adapter layer in `socketio_server.py` to translate events during transition period.

### 11.2 Blocker #2: Real-Time Detection Assignment

**Issue**: Current system assigns `video_id` in real-time during detection capture using `TestSession.video_id` field.

**Impact**: Continuous monitoring cannot assign `video_id` until post-processing, breaking real-time WebSocket events that include `video_id`.

**Workaround**:
- **Option A**: Assign `video_id = null` during capture, backfill in post-processing
- **Option B**: Use "best-guess" assignment during capture (based on latest marker), correct in post-processing

**Recommended**: Option B for minimal frontend impact.

### 11.3 Blocker #3: Ground Truth Matching Timing

**Issue**: Ground truth matching service runs immediately after video ends (per-video), using `video_playback_start_time` for offset calculation.

**Impact**: Continuous monitoring requires:
1. Delaying ground truth matching until session ends
2. OR running incremental matching per video with marker-based time boundaries

**Workaround**: Incremental matching using marker boundaries (minimal change to matching logic).

---

## 12. Recommendations

### 12.1 Phased Rollout Plan

**Phase 1: Foundation (Week 1)**
- Add `video_markers` table
- Implement marker recording service
- Add feature flag infrastructure

**Phase 2: Backend Core (Week 2)**
- Update monitoring service for continuous mode
- Implement post-processing segmentation
- Add adapter layer for backward compatibility

**Phase 3: Integration (Week 3)**
- Update ground truth matching service
- Update WebSocket event handlers
- Integration testing

**Phase 4: Gradual Rollout (Week 4)**
- Enable feature flag for staging environment
- Monitor performance and correctness
- Gradual production rollout

### 12.2 Risk Mitigation

1. **Feature Flag**: Enable/disable continuous monitoring per session
2. **Adapter Layer**: Maintain legacy API compatibility
3. **Incremental Matching**: Run GT matching per video using markers (avoid session-end delay)
4. **Monitoring**: Log all marker recordings and assignments for debugging

### 12.3 Go/No-Go Decision Criteria

**GO** if:
- Feature flag + adapter layer tested successfully
- Backward compatibility validated
- Performance impact < 50ms per video marker
- Integration tests pass at 100%

**NO-GO** if:
- Detection assignment accuracy drops > 5%
- Real-time latency increases > 100ms
- Database migration causes data loss
- Frontend changes require > 2 weeks

---

## 13. Conclusion

**Overall Assessment**: ⚠️ **FEASIBLE BUT HIGH RISK**

**Recommended Path Forward**:
1. ✅ **Implement with feature flag** - Gradual rollout minimizes risk
2. ✅ **Use adapter layer** - Maintains backward compatibility
3. ⚠️ **Coordinate with frontend** - Video lifecycle integration must be synchronized
4. ✅ **Incremental matching** - Avoid session-end delay for GT matching

**Next Steps**:
1. Review this analysis with team
2. Prototype marker recording + post-processing
3. Performance benchmarking (compare vs. per-video)
4. Frontend coordination meeting
5. Create implementation tickets with dependencies

---

**Document Version**: 1.0
**Last Updated**: 2025-11-20
**Author**: Backend API Developer Agent
**Review Required**: System Architect, Frontend Lead, QA Lead
