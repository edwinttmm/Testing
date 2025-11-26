# Video Timing Race Condition Fix - Quick Reference Card

## 🚨 Problem in 3 Lines

1. LabJack detections arrive BEFORE SequenceVideoResult cached → NULL video_id
2. 15% of detections have NULL video_id in production
3. Cache invalidation happens too late to fix early detections

## ✅ Solution in 3 Lines

1. Pre-populate cache BEFORE starting LabjJack monitoring
2. Verify cache ready as initialization barrier
3. Refresh cache after lifecycle events + flush detection queue

---

## 📝 Files to Change

### 1. CREATE NEW FILE
**Path**: `/backend/services/video_timing_cache_prepopulator.py`
**Size**: ~200 lines
**Purpose**: Pre-populate video timing cache before monitoring starts

### 2. MODIFY EXISTING
**Path**: `/backend/routers/video_sequence_testing.py`

**Location 1** (Lines 528-532):
```python
# ADD after db.commit():
prepopulator = get_cache_prepopulator()
cache_ready = prepopulator.prepopulate_sequence_cache(session_id, sequence_id, db)
if not prepopulator.verify_cache_ready(session_id):
    raise HTTPException(500, "Cache not ready")
# THEN start_hil_monitoring()
```

**Location 2** (Lines 694-708):
```python
# CHANGE from:
monitor.invalidate_sequence_cache(session_id)
flush_detection_queue(session_id, video_id, db)

# TO:
monitor.invalidate_sequence_cache(session_id)
prepopulator.refresh_cache(session_id, sequence_id, db)  # NEW
flush_detection_queue(session_id, video_id, db)
```

---

## 🔍 Code Snippets

### Complete Cache Pre-Populator Service

```python
# /backend/services/video_timing_cache_prepopulator.py

from typing import Optional
import logging
from sqlalchemy.orm import Session, joinedload
from models import TestSession, SequenceVideoResult, VideoTestSequence
from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor

logger = logging.getLogger(__name__)

class CachePrePopulator:
    """Pre-populate video timing cache for race-free detection correlation"""

    def __init__(self):
        self.monitor = get_dedicated_labjack_monitor()

    def prepopulate_sequence_cache(
        self,
        session_id: str,
        sequence_id: str,
        db: Session
    ) -> bool:
        """
        Pre-populate cache with video timing data.

        Returns True if successful, False otherwise.
        """
        try:
            # Load with optimized queries
            test_session = db.query(TestSession).options(
                joinedload(TestSession.video_sequence)
            ).filter_by(id=session_id).first()

            if not test_session:
                logger.error(f"❌ TestSession {session_id} not found")
                return False

            video_results = db.query(SequenceVideoResult).options(
                joinedload(SequenceVideoResult.video)
            ).filter_by(
                video_sequence_id=sequence_id
            ).order_by(
                SequenceVideoResult.sequence_order
            ).all()

            if not video_results:
                logger.error(f"❌ No SequenceVideoResult records")
                return False

            # Build video_timing structure
            video_timing = {}
            for result in video_results:
                video_timing[result.video_id] = {
                    'sequence_order': result.sequence_order,
                    'status': result.video_status or 'pending',
                    'expected_detection_count': result.expected_detection_count,
                    'started_at': None,  # Will be set by lifecycle events
                    'ended_at': None,
                    'initialized': True
                }

            # Build lookup dict
            sequence_video_results = {}
            for result in video_results:
                sequence_video_results[result.video_id] = {
                    'id': result.id,
                    'sequence_order': result.sequence_order,
                    'video_status': result.video_status,
                    'expected_detection_count': result.expected_detection_count,
                    'latency_threshold_ms': result.latency_threshold_ms
                }

            # Build cache context
            cache_context = {
                'sequence_id': sequence_id,
                'test_session_id': session_id,
                'video_timing': video_timing,
                'sequence_video_results': sequence_video_results,
                'video_ids': [r.video_id for r in video_results],
                'total_videos': len(video_results),
                'cache_prepopulated': True,
                'prepopulated_at': time.time()
            }

            # Inject into monitor cache (thread-safe)
            with self.monitor.lock:
                if session_id not in self.monitor.session_data:
                    self.monitor.session_data[session_id] = {}
                self.monitor.session_data[session_id]['sequence_context'] = cache_context

            logger.info(
                f"✅ Cache pre-populated: {len(video_results)} videos"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Cache prepopulation failed: {e}", exc_info=True)
            return False

    def verify_cache_ready(self, session_id: str) -> bool:
        """Verify cache contains required data"""
        try:
            with self.monitor.lock:
                session_cache = self.monitor.session_data.get(session_id, {})
                context = session_cache.get('sequence_context')

            if not context:
                logger.error(f"❌ No sequence_context")
                return False

            if 'video_timing' not in context:
                logger.error(f"❌ No video_timing in context")
                return False

            if not context.get('cache_prepopulated'):
                logger.warning(f"⚠️ Cache not marked as prepopulated")
                return False

            logger.info(f"✅ Cache verified: {len(context['video_timing'])} videos")
            return True

        except Exception as e:
            logger.error(f"❌ Cache verification failed: {e}")
            return False

    def refresh_cache(self, session_id: str, sequence_id: str, db: Session) -> bool:
        """Force refresh cache with latest timing data"""
        logger.info(f"🔄 Refreshing cache for {session_id}")
        return self.prepopulate_sequence_cache(session_id, sequence_id, db)


# Singleton
_prepopulator: Optional[CachePrePopulator] = None

def get_cache_prepopulator() -> CachePrePopulator:
    """Get singleton cache pre-populator"""
    global _prepopulator
    if _prepopulator is None:
        _prepopulator = CachePrePopulator()
        logger.info("✅ CachePrePopulator initialized")
    return _prepopulator
```

### Router Modification (start_video_sequence)

```python
# /backend/routers/video_sequence_testing.py

@router.post("/start", response_model=VideoSequenceStartResponse, status_code=201)
async def start_video_sequence(
    request: VideoSequenceStartRequest,
    db: Session = Depends(get_db)
):
    """Start multi-video sequential HIL test with race-free initialization."""
    try:
        # ... existing code: create session, sequence, video results ...

        # ✅ BARRIER #1: Commit all records
        db.commit()
        logger.info(f"✅ Database records committed")

        # ========== ADD THIS BLOCK (NEW) ==========
        from services.video_timing_cache_prepopulator import get_cache_prepopulator

        prepopulator = get_cache_prepopulator()

        logger.info(f"🔄 Pre-populating cache for sequence {sequence_id}")

        cache_ready = prepopulator.prepopulate_sequence_cache(
            session_id=test_session_id,
            sequence_id=sequence_id,
            db=db
        )

        if not cache_ready:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize video timing cache"
            )

        # ✅ BARRIER #2: Verify cache ready
        if not prepopulator.verify_cache_ready(test_session_id):
            raise HTTPException(
                status_code=500,
                detail="Cache verification failed"
            )

        logger.info(f"✅ Cache pre-populated and verified")
        # ========== END NEW BLOCK ==========

        # NOW SAFE: Start LabjJack monitoring
        labjack_monitoring_enabled = False
        if request.enable_labjack_monitoring and HIL_MONITORING_AVAILABLE:
            # ... existing monitoring start code ...
            pass

        return VideoSequenceStartResponse(...)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
```

### Router Modification (record_video_started)

```python
# /backend/routers/video_sequence_testing.py

@router.post("/{sequence_id}/video-started", status_code=200)
async def record_video_started(
    sequence_id: str = Path(...),
    request: VideoStartedRequest = Body(...),
    db: Session = Depends(get_db)
):
    """Record video start with cache refresh."""
    try:
        # ... existing code: update timing, commit ...

        db.commit()

        # ========== MODIFY THIS BLOCK ==========
        try:
            from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
            from services.video_timing_cache_prepopulator import get_cache_prepopulator

            monitor = get_dedicated_labjack_monitor()
            prepopulator = get_cache_prepopulator()

            # Step 1: Invalidate stale cache
            monitor.invalidate_sequence_cache(test_session.id)
            logger.info(f"✅ Cache invalidated")

            # ✅ NEW: Step 2: Re-populate with fresh data
            cache_refreshed = prepopulator.refresh_cache(
                session_id=test_session.id,
                sequence_id=sequence_id,
                db=db
            )

            if cache_refreshed:
                logger.info(f"✅ Cache refreshed with video {request.video_id} timing")
            else:
                logger.warning(f"⚠️ Cache refresh failed")

        except Exception as cache_error:
            logger.error(f"❌ Cache refresh error: {cache_error}")

        # Step 3: Flush detection queue (existing)
        try:
            from services.detection_queue_service import flush_detection_queue
            flushed_count = flush_detection_queue(test_session.id, request.video_id, db)
            if flushed_count > 0:
                logger.info(f"✅ Flushed {flushed_count} queued detections")
        except Exception as queue_error:
            logger.error(f"❌ Queue flush error: {queue_error}")
        # ========== END MODIFIED BLOCK ==========

        return {...}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 🧪 Testing Checklist

### Unit Tests

```python
# test_cache_prepopulator.py

def test_prepopulate_sequence_cache():
    """Test cache prepopulation creates correct structure"""
    prepopulator = get_cache_prepopulator()
    session_id = create_test_session()
    sequence_id = create_test_sequence(session_id, 3)

    success = prepopulator.prepopulate_sequence_cache(session_id, sequence_id, db)
    assert success
    assert prepopulator.verify_cache_ready(session_id)

def test_verify_cache_without_prepopulation():
    """Test verification fails without prepopulation"""
    prepopulator = get_cache_prepopulator()
    assert not prepopulator.verify_cache_ready("nonexistent")
```

### Integration Tests

```python
# test_video_sequence_race_condition.py

async def test_early_detection_assigned():
    """Test detection during initialization gets assigned"""
    sequence_id = await start_video_sequence(...)

    # Inject detection IMMEDIATELY
    inject_gpio_event(session_id, voltage=5.0)

    # Check assigned to first video
    detection = db.query(DetectionEvent).first()
    assert detection.video_id is not None
    assert detection.video_id == video1_id
```

---

## 📊 Success Metrics

| Metric | Target | How to Check |
|--------|--------|--------------|
| **NULL video_id rate** | 0% | Query DetectionEvent WHERE video_id IS NULL |
| **Cache hit rate** | >95% | Monitor logs for "Cache HIT" vs "Cache MISS" |
| **Cache prepopulation success** | 100% | Check logs for "Cache pre-populated and verified" |
| **Detection queue size** | <10 | Call `/health/timing-sync` endpoint |

---

## 🚀 Deployment Commands

```bash
# 1. Add new file
cp video_timing_cache_prepopulator.py /backend/services/

# 2. Run tests
pytest backend/tests/test_cache_prepopulator.py -v
pytest backend/tests/test_video_sequence_race_condition.py -v

# 3. Deploy to staging
docker-compose -f docker-compose.staging.yml up -d backend

# 4. Monitor logs
docker logs -f backend | grep -E "Cache (pre-populated|verified|refreshed)"

# 5. Check health
curl http://staging:8000/api/video-sequences/health/timing-sync | jq

# 6. Deploy to production (gradual)
# Canary: 10% traffic
# Full: 100% traffic after 24h monitoring
```

---

## 🔧 Troubleshooting

### Problem: Cache Prepopulation Fails

**Symptom**: HTTPException 500 "Failed to initialize video timing cache"

**Check**:
```bash
# Check database records exist
SELECT * FROM sequence_video_result WHERE video_sequence_id = '<sequence_id>';

# Check logs
grep "Cache prepopulation failed" backend.log
```

**Fix**: Verify SequenceVideoResult records created before prepopulation

---

### Problem: Cache Hit Rate Low

**Symptom**: Cache hit rate <90% in logs

**Check**:
```bash
# Count cache hits vs misses
grep -c "Cache HIT" backend.log
grep -c "Cache MISS" backend.log
```

**Fix**: Check cache invalidation frequency, may be invalidating too often

---

### Problem: Detection Queue Size Growing

**Symptom**: `/health/timing-sync` shows queue_size > 50

**Check**:
```bash
# Check queue health
curl http://localhost:8000/api/video-sequences/health/timing-sync | jq '.queue_health'
```

**Fix**: Check video lifecycle events arriving, may need manual flush

---

## 📞 Support

**Documentation**:
- [Architecture](VIDEO_TIMING_RACE_CONDITION_ARCHITECTURE.md)
- [Diagrams](VIDEO_TIMING_RACE_CONDITION_DIAGRAMS.md)
- [Implementation Guide](VIDEO_TIMING_RACE_CONDITION_IMPLEMENTATION_GUIDE.md)

**Monitoring**:
- Health: `GET /api/video-sequences/health/timing-sync`
- Logs: `docker logs -f backend | grep -E "Cache|video_id"`

**Rollback**:
```bash
# Disable feature flag
export ENABLE_CACHE_PREPOPULATION=false
docker-compose restart backend
```

---

**Version**: 1.0
**Last Updated**: 2025-11-14
**Status**: Ready for Implementation
