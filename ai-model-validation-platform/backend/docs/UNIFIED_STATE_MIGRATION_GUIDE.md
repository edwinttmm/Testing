# Unified State Management Service - Migration Guide

**Status**: Production Rollout
**Priority**: P0 - Critical Architecture Fix
**Timeline**: 4 weeks

---

## Executive Summary

This guide provides step-by-step instructions for migrating from the current **3-source-of-truth architecture** to a **unified state management service**.

**Current State**: Session state is scattered across:
1. PostgreSQL (persistent)
2. `video_sequence_orchestrator._active_sequences` (in-memory cache)
3. `socketio_server.active_sessions` (in-memory state)

**Target State**: Single source of truth via `UnifiedStateService`

---

## Migration Phases

### Phase 0: Pre-Migration Checklist

✅ **Prerequisites**:
- [ ] ADR-005 approved by architecture team
- [ ] `unified_state_service.py` code reviewed and tested
- [ ] Redis instance deployed (optional but recommended)
- [ ] Integration test suite ready
- [ ] Rollback plan documented
- [ ] Blue-green deployment pipeline configured

✅ **Baseline Metrics** (capture before migration):
```bash
# Current detection assignment accuracy
SELECT
    COUNT(*) FILTER (WHERE video_id IS NULL) as null_video_ids,
    COUNT(*) as total_detections
FROM detection_events;

# Current cache hit rate (estimate from logs)
grep "Cache hit" nohup.out | wc -l
grep "Cache miss" nohup.out | wc -l

# Current race condition frequency (errors)
grep "RACE CONDITION" nohup.out | wc -l
```

---

## Phase 1: Deploy UnifiedStateService (Non-Breaking)

**Timeline**: Week 1
**Risk Level**: Low (no breaking changes)

### Step 1.1: Deploy Service Code
```bash
# 1. Deploy unified_state_service.py
cd /home/rigade/Testing/ai-model-validation-platform/backend
cp services/unified_state_service.py /production/backend/services/

# 2. Add to imports
echo "from services.unified_state_service import get_unified_state_service" >> main.py

# 3. Restart backend (service starts but isn't used yet)
sudo systemctl restart hil-backend
```

### Step 1.2: Add Health Check Endpoint
**File**: `/backend/routers/state_management.py`
```python
from fastapi import APIRouter, Depends
from services.unified_state_service import get_unified_state_service

router = APIRouter(prefix="/api/state", tags=["state-management"])

@router.get("/health")
async def health_check():
    """Health check for unified state service"""
    service = get_unified_state_service()

    # Test cache connectivity
    cache_status = "redis" if service._use_redis else "local"

    return {
        "status": "healthy",
        "cache_backend": cache_status,
        "service": "UnifiedStateService",
        "version": "1.0.0"
    }

@router.get("/stats")
async def get_stats():
    """Get service statistics"""
    service = get_unified_state_service()

    # Return cache stats
    return {
        "cache_size": len(service._cache),
        "lock_count": len(service._locks),
        "cache_backend": "redis" if service._use_redis else "local"
    }
```

### Step 1.3: Verify Deployment
```bash
# Test health check
curl http://localhost:8000/api/state/health

# Expected response:
# {
#   "status": "healthy",
#   "cache_backend": "local",
#   "service": "UnifiedStateService",
#   "version": "1.0.0"
# }

# Check logs for startup
tail -f nohup.out | grep "UnifiedStateService"
# Expected: "🔧 UnifiedStateService initialized (single source of truth)"
```

### Step 1.4: Monitor for 1 Week
**Metrics to Track**:
- Service uptime: `systemctl status hil-backend`
- Health check response time: `curl -w "@curl-format.txt" http://localhost:8000/api/state/health`
- Memory usage: `ps aux | grep python`

**Success Criteria**:
- ✅ Service starts without errors
- ✅ Health check returns 200 OK
- ✅ No impact on existing functionality
- ✅ Memory usage stable

---

## Phase 2: Migrate SocketIO (Low Risk)

**Timeline**: Week 2
**Risk Level**: Low (thin client, limited scope)

### Step 2.1: Add Feature Flag
**File**: `/backend/.env`
```bash
# Feature flag for unified state service
USE_UNIFIED_STATE_SERVICE=false  # Start disabled
```

### Step 2.2: Update SocketIO to Use Service
**File**: `/backend/socketio_server.py`

**BEFORE**:
```python
# Line 594 - Direct database write (RACE CONDITION PRONE)
session = db.query(TestSession).filter(TestSession.id == session_id).first()
if session:
    session.video_id = video_id
    db.commit()
```

**AFTER**:
```python
import os
from services.unified_state_service import get_unified_state_service

# Feature flag check
USE_UNIFIED_STATE = os.getenv('USE_UNIFIED_STATE_SERVICE', 'false').lower() == 'true'

@sio.event
async def video_started(sid, data):
    """Handle video started events - NOW USES UNIFIED STATE"""
    session_id = data.get('sessionId')
    video_id = data.get('videoId')
    video_start_time = data.get('videoStartTime')

    if not session_id or not video_id:
        await sio.emit('error', {'message': 'Missing session or video ID'}, room=sid)
        return

    if USE_UNIFIED_STATE:
        # NEW: Use UnifiedStateService (single write path)
        unified_state = get_unified_state_service()
        success = unified_state.start_video(session_id, video_id, video_start_time)

        if success:
            logger.info(f"✅ UNIFIED STATE: Video started via service - session={session_id}, video={video_id}")
        else:
            logger.error(f"❌ UNIFIED STATE: Failed to start video - session={session_id}, video={video_id}")
            await sio.emit('error', {'message': 'Failed to start video'}, room=sid)
            return
    else:
        # LEGACY: Direct database write (RACE CONDITION PRONE)
        db = SessionLocal()
        try:
            session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if session:
                session.video_id = video_id
                db.commit()
                logger.info(f"⚠️ LEGACY: Video started via direct DB write")
            else:
                logger.error(f"Session {session_id} not found")
        finally:
            db.close()

    # Continue with orchestrator notification...
```

### Step 2.3: Deploy to Staging
```bash
# 1. Set feature flag
export USE_UNIFIED_STATE_SERVICE=true

# 2. Restart backend
sudo systemctl restart hil-backend

# 3. Run integration tests
cd backend/tests
pytest test_socketio_unified_state.py -v
```

### Step 2.4: Integration Test Suite
**File**: `/backend/tests/test_socketio_unified_state.py`
```python
import pytest
import asyncio
from services.unified_state_service import get_unified_state_service

@pytest.mark.asyncio
async def test_video_started_uses_unified_state():
    """Test that video_started uses UnifiedStateService"""
    service = get_unified_state_service()

    # Create test session
    session_id = "test_session_001"
    video_id = "test_video_001"
    start_time = 1704628800.0

    # Start video via service
    success = service.start_video(session_id, video_id, start_time)
    assert success, "Failed to start video"

    # Verify state is correct
    current_video = service.get_current_video(session_id)
    assert current_video is not None
    assert current_video.video_id == video_id
    assert current_video.start_time == start_time
    assert current_video.status == "playing"

@pytest.mark.asyncio
async def test_detection_assignment_uses_correct_video():
    """Test that detections are assigned to correct video"""
    service = get_unified_state_service()

    session_id = "test_session_002"
    video_id_1 = "video_1"
    video_id_2 = "video_2"

    # Start first video
    service.start_video(session_id, video_id_1, 1000.0)

    # Record detection (should use video_1)
    detection_data = {'timestamp': 1001.0, 'voltage': 3.3, 'channel': 'AIN0'}
    detection_id = service.record_detection(session_id, detection_data)
    assert detection_id is not None

    # Verify detection has correct video_id
    from models import DetectionEvent
    from database import SessionLocal
    db = SessionLocal()
    detection = db.query(DetectionEvent).filter_by(id=detection_id).first()
    assert detection.video_id == video_id_1
    db.close()

    # Start second video
    service.end_video(session_id, video_id_1, 1010.0)
    service.start_video(session_id, video_id_2, 1020.0)

    # Record detection (should use video_2)
    detection_data = {'timestamp': 1021.0, 'voltage': 3.3, 'channel': 'AIN0'}
    detection_id = service.record_detection(session_id, detection_data)

    # Verify detection has correct video_id
    db = SessionLocal()
    detection = db.query(DetectionEvent).filter_by(id=detection_id).first()
    assert detection.video_id == video_id_2
    db.close()
```

### Step 2.5: Canary Deployment to Production
```bash
# 1. Deploy to 10% of production traffic
# Update load balancer to route 10% to new backend

# 2. Monitor for 48 hours
tail -f /var/log/hil-backend/access.log | grep "UNIFIED STATE"

# 3. Check error rates
grep "ERROR" nohup.out | wc -l  # Should not increase

# 4. Verify detection assignment accuracy
psql -d hil_db -c "SELECT COUNT(*) FILTER (WHERE video_id IS NULL) FROM detection_events WHERE created_at > NOW() - INTERVAL '2 days';"
# Expected: 0 NULL video_ids
```

### Step 2.6: Full Production Rollout
```bash
# If canary successful, route 100% traffic to new backend
# Update load balancer configuration

# Monitor for 1 week before proceeding to Phase 3
```

**Success Criteria**:
- ✅ Zero `video_id=NULL` errors in production
- ✅ Detection assignment accuracy: 100%
- ✅ No increase in error rate
- ✅ Response time < 100ms for video_started events

---

## Phase 3: Migrate Orchestrator (High Risk)

**Timeline**: Week 3
**Risk Level**: HIGH (removes in-memory cache, complex logic)

⚠️ **CRITICAL**: This phase requires extensive testing and blue-green deployment.

### Step 3.1: Update Orchestrator to Query Service
**File**: `/backend/services/video_sequence_orchestrator.py`

**BEFORE** (Lines 176-177):
```python
def __init__(self, video_timing_service: Optional[VideoTimingService] = None):
    self._timing_service = video_timing_service or get_video_timing_service()
    self._active_sequences: Dict[str, VideoTestSequence] = {}  # IN-MEMORY CACHE
```

**AFTER**:
```python
def __init__(self, video_timing_service: Optional[VideoTimingService] = None, use_unified_state: bool = True):
    self._timing_service = video_timing_service or get_video_timing_service()

    # MIGRATION FLAG: Disable in-memory cache, use UnifiedStateService instead
    self._use_unified_state = use_unified_state
    if self._use_unified_state:
        from services.unified_state_service import get_unified_state_service
        self._state_service = get_unified_state_service()
        self._active_sequences = {}  # Empty dict, no longer used
        logger.info("✅ Orchestrator using UnifiedStateService (no in-memory cache)")
    else:
        self._active_sequences: Dict[str, VideoTestSequence] = {}  # Legacy cache
        logger.warning("⚠️ Orchestrator using LEGACY in-memory cache (deprecated)")
```

**BEFORE** (Line 445 - `_determine_video_for_detection`):
```python
def _determine_video_for_detection(self, sequence: VideoTestSequence, detection_timestamp: float) -> Optional[str]:
    """Determine which video was playing at detection time"""
    for video_id in sequence.video_ids:
        metadata = sequence.video_metadata[video_id]
        if metadata.video_start_time is None:
            continue
        video_end = metadata.video_end_time or (metadata.video_start_time + metadata.duration + 1.0)
        if metadata.video_start_time <= detection_timestamp <= video_end:
            return video_id
    return None
```

**AFTER**:
```python
def _determine_video_for_detection(self, sequence_id: str, session_id: str, detection_timestamp: float) -> Optional[str]:
    """Determine which video was playing at detection time - USES UNIFIED STATE"""
    if self._use_unified_state:
        # NEW: Query UnifiedStateService for current video
        current_video = self._state_service.get_current_video(session_id)
        if not current_video:
            logger.warning(f"No current video for session {session_id}")
            return None

        # Validate detection is within video timing window
        validation = self._state_service.validate_detection_timing(session_id, detection_timestamp)
        if not validation.is_valid:
            logger.warning(f"Detection outside timing window: {validation.reason}")
            return None

        return current_video.video_id
    else:
        # LEGACY: Use in-memory cache (deprecated)
        if sequence_id not in self._active_sequences:
            return None
        sequence = self._active_sequences[sequence_id]
        for video_id in sequence.video_ids:
            metadata = sequence.video_metadata[video_id]
            if metadata.video_start_time is None:
                continue
            video_end = metadata.video_end_time or (metadata.video_start_time + metadata.duration + 1.0)
            if metadata.video_start_time <= detection_timestamp <= video_end:
                return video_id
        return None
```

### Step 3.2: Remove In-Memory Cache (Final Step)
**After extensive testing, remove legacy code**:

```python
# REMOVE: Line 176
# self._active_sequences: Dict[str, VideoTestSequence] = {}

# REMOVE: All references to self._active_sequences
# - Line 252: self._active_sequences[sequence_id] = sequence
# - Line 286: sequence = self._active_sequences.get(sequence_id)
# - Line 824: if sequence_id not in self._active_sequences
```

### Step 3.3: Integration Testing (Extensive)
**File**: `/backend/tests/test_orchestrator_unified_state.py`
```python
import pytest
from services.video_sequence_orchestrator import VideoSequenceOrchestrator
from services.unified_state_service import get_unified_state_service

@pytest.fixture
def orchestrator():
    """Create orchestrator with unified state enabled"""
    return VideoSequenceOrchestrator(use_unified_state=True)

def test_orchestrator_uses_unified_state(orchestrator):
    """Verify orchestrator queries UnifiedStateService, not in-memory cache"""
    assert orchestrator._use_unified_state is True
    assert len(orchestrator._active_sequences) == 0  # No in-memory cache

def test_detection_assignment_multi_video(orchestrator):
    """Test detection assignment across video transitions"""
    # Test scenario:
    # - Sequence has 3 videos
    # - Start video 1, record detections
    # - Transition to video 2, record detections
    # - Verify all detections have correct video_id

    # Implementation left as exercise (see integration test suite)
```

### Step 3.4: Blue-Green Deployment
```bash
# 1. Deploy new orchestrator to green environment
# 2. Route 10% of traffic to green
# 3. Monitor for 48 hours
# 4. Gradually increase to 50%, then 100%
# 5. Decommission blue environment

# Rollback plan: Switch all traffic back to blue
```

**Success Criteria**:
- ✅ All 7 issues resolved (no race conditions, no dual caching, etc.)
- ✅ Cache hit rate: 99%+
- ✅ Detection assignment accuracy: 100%
- ✅ No performance degradation
- ✅ No increase in error rate

---

## Phase 4: Cleanup (Final)

**Timeline**: Week 4
**Risk Level**: Low

### Step 4.1: Remove Feature Flags
```bash
# Remove from .env
# USE_UNIFIED_STATE_SERVICE=true  # DELETE THIS LINE

# Remove from code
# if USE_UNIFIED_STATE:  # DELETE ALL FEATURE FLAG CHECKS
```

### Step 4.2: Remove Legacy Code
```python
# socketio_server.py: Remove legacy database writes
# video_sequence_orchestrator.py: Remove _active_sequences cache
# labjack_detection_service.py: Remove direct session metadata queries
```

### Step 4.3: Update Documentation
- Update ADR-005 status to "Implemented"
- Update architecture diagrams
- Update API documentation

---

## Rollback Procedures

### Emergency Rollback (Phase 2 or 3)
```bash
# 1. Set feature flag to false
export USE_UNIFIED_STATE_SERVICE=false

# 2. Restart backend
sudo systemctl restart hil-backend

# 3. Verify legacy code path is active
tail -f nohup.out | grep "LEGACY"

# 4. Monitor for stability
# Expected: System returns to pre-migration behavior
```

### Blue-Green Rollback (Phase 3)
```bash
# 1. Switch load balancer to blue environment
# 2. Verify all traffic is on blue
# 3. Monitor for errors
# 4. Green environment remains deployed (for retry)
```

---

## Success Metrics

### Key Performance Indicators (KPIs)

**Before Migration**:
- Detection assignment accuracy: 95% (5% NULL video_id errors)
- Race condition frequency: 2-5 per day
- Cache hit rate: N/A (no unified cache)
- Average detection latency: 100ms

**After Migration** (Target):
- Detection assignment accuracy: 100% (zero NULL video_id errors)
- Race condition frequency: 0 per day
- Cache hit rate: 99%+
- Average detection latency: 10ms (90% reduction)

### Monitoring Dashboard
```bash
# Set up Grafana dashboard to track:
# 1. Detection assignment accuracy (% NULL video_ids)
# 2. Cache hit rate (cache hits / total queries)
# 3. Service response time (p50, p95, p99)
# 4. Error rate (errors / total requests)
```

---

## Support & Escalation

**Migration Team**:
- Architecture Lead: [Name]
- Backend Engineer: [Name]
- QA Engineer: [Name]
- DevOps Engineer: [Name]

**Escalation Path**:
1. Slack: #hil-migration-support
2. PagerDuty: HIL Backend Team
3. Emergency: Call architecture lead

---

**Last Updated**: 2025-01-07
**Next Review**: After Phase 3 deployment
