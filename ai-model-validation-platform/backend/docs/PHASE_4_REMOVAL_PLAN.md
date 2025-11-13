# Phase 4: Code Removal Plan - Eliminate the Rot

This document identifies all code to DELETE as part of Phase 4 integration.

## 🎯 Removal Strategy

**PRINCIPLE**: Delete code, not just comment it out.
**REASON**: Dead code creates confusion and technical debt.
**SAFETY**: Keep in git history for reference.

---

## 1. labjack_detection_service.py - Metadata Extraction

### DELETE: Lines 1016-1040

**What**: Metadata parsing for `current_video_id`
**Why**: Replaced by database query in `video_id_resolver`
**Impact**: 24 lines removed

```python
# DELETE THIS ENTIRE BLOCK:
video_id = session.video_id  # Default to session video (first video)

if session.sequence_id and session.sequence_metadata:
    # Multi-video sequence detected - extract current_video_id
    try:
        metadata = session.sequence_metadata
        if isinstance(metadata, str):
            import json
            metadata = json.loads(metadata)

        current_video_id = metadata.get('current_video_id')

        if current_video_id:
            logger.info(f"✅ Multi-video: Using current_video_id={current_video_id} (sequence={session.sequence_id})")
            video_id = current_video_id
        else:
            logger.warning(f"⚠️ Multi-video session {session.id} missing current_video_id in sequence_metadata")
            logger.warning(f"   Falling back to session.video_id={session.video_id}")
    except Exception as meta_error:
        logger.error(f"Failed to parse sequence_metadata for video_id: {meta_error}")
        logger.warning(f"   Falling back to session.video_id={session.video_id}")
```

---

## 2. labjack_detection_service.py - Manual Sequence Result Query

### DELETE: Lines 1054-1065

**What**: Manual query for `SequenceVideoResult`
**Why**: Replaced by `get_sequence_video_result_id()` helper
**Impact**: 12 lines removed

```python
# DELETE THIS ENTIRE BLOCK:
if sequence_id and video_id:
    try:
        # Query the active SequenceVideoResult for this video in the sequence
        video_result = db.query(SequenceVideoResultModel).filter(
            SequenceVideoResultModel.video_sequence_id == sequence_id,
            SequenceVideoResultModel.video_id == video_id
        ).first()

        if video_result:
            sequence_video_result_id = video_result.id
            logger.info(f"✅ Linked detection to sequence_video_result_id={sequence_video_result_id}")
```

---

## 3. video_sequence_orchestrator.py - In-Memory Cache

### DELETE: Entire Cache System

**What**: `_active_sequences` dictionary and all cache methods
**Why**: Database IS the source of truth
**Impact**: ~100-150 lines removed

```python
# DELETE: Instance variable
class VideoSequenceOrchestrator:
    def __init__(self):
        self._active_sequences: Dict[str, Any] = {}  # DELETE THIS LINE
```

### DELETE: Cache Management Methods

Find and DELETE these methods:

```python
# Method 1: Cache video timing
def _cache_video_timing(self, session_id: str, video_id: str, start_time: float, end_time: float):
    """DELETE THIS METHOD"""
    pass

# Method 2: Get cached timing
def _get_cached_video_timing(self, session_id: str) -> Optional[Dict]:
    """DELETE THIS METHOD"""
    pass

# Method 3: Clear cache
def _clear_sequence_cache(self, session_id: str):
    """DELETE THIS METHOD"""
    pass

# Method 4: Update cache state
def _update_cache_state(self, session_id: str, state: Dict):
    """DELETE THIS METHOD"""
    pass
```

### SEARCH and DELETE all references:

```bash
# Find all cache references
cd /home/rigade/Testing/ai-model-validation-platform/backend
grep -n "_active_sequences" services/video_sequence_orchestrator.py
grep -n "_cache" services/video_sequence_orchestrator.py

# Delete each reference found
```

---

## 4. video_sequence_orchestrator.py - Current Video Tracking

### DELETE: Any code that tracks "which video is current"

**What**: Variables like `current_video_id`, `current_video_index`
**Why**: Database timing ranges determine this automatically
**Impact**: ~20-30 lines removed

```python
# DELETE: Current video tracking
self.current_video_id = None  # DELETE
self.current_video_index = 0  # DELETE (unless used for display only)

# DELETE: Methods that set "current video"
def set_current_video(self, video_id: str):
    """DELETE THIS METHOD"""
    pass

def get_current_video(self, session_id: str) -> Optional[str]:
    """DELETE THIS METHOD"""
    pass
```

---

## 5. socketio_server.py - In-Memory State Tracking

### DELETE: "Current Video" State Management

**What**: Code that tracks which video is "currently playing"
**Why**: This is determined by database timing ranges
**Impact**: ~30-50 lines removed

```python
# DELETE: Active video tracking
active_videos: Dict[str, str] = {}  # DELETE if exists

# DELETE: Methods that update "current video"
@sio.on('set_current_video')
async def set_current_video(sid, data):
    """DELETE THIS HANDLER if it exists"""
    pass
```

### KEEP: Video Lifecycle Persistence

**IMPORTANT**: Do NOT delete code that persists timing to database:

```python
# KEEP THIS: Database persistence is legitimate
@sio.on('video_lifecycle_event')
async def handle_video_lifecycle(sid, data):
    """KEEP: This persists timing to database"""

    # KEEP: Writing to database
    video_result.video_start_time = timestamp
    db.commit()

    # DELETE: Updating in-memory state
    # active_videos[session_id] = video_id  # DELETE THIS
    # session.sequence_metadata = {...}  # DELETE THIS
```

---

## 6. socketio_server.py - sequence_metadata Updates

### DELETE: Code that writes current_video_id to sequence_metadata

**What**: Updates to `session.sequence_metadata['current_video_id']`
**Why**: This created the uncoordinated source of truth
**Impact**: ~10-15 lines removed

```python
# DELETE: Metadata updates
if session.sequence_metadata:
    metadata = session.sequence_metadata
    metadata['current_video_id'] = video_id  # DELETE THIS
    session.sequence_metadata = metadata  # DELETE THIS
    db.commit()
```

---

## 7. models.py - Deprecate sequence_metadata Field

### DO NOT DELETE: Keep field for backward compatibility

**Action**: Add deprecation comment only

```python
# File: models.py
class TestSession(Base):
    # ...

    # DEPRECATED: sequence_metadata no longer used for current_video_id tracking
    # Phase 4: Replaced by database timing queries in video_id_resolver
    # Keep for backward compatibility with old data
    sequence_metadata = Column(MutableDict.as_mutable(JSON), nullable=True)
```

**Why keep it**:
- Old sessions may still have this data
- May contain other metadata (not just current_video_id)
- Safe to leave NULL for new sessions

**Future action** (Phase 5+):
- Monitor usage
- If unused, schedule for removal in breaking change release

---

## 8. Removal Execution Plan

### Step 1: Create Feature Branch

```bash
cd /home/rigade/Testing/ai-model-validation-platform
git checkout -b phase-4-eliminate-rot
```

### Step 2: Apply Removals (In Order)

```bash
# 1. Remove labjack_detection_service.py metadata extraction
# Edit file: lines 1016-1040

# 2. Remove labjack_detection_service.py manual query
# Edit file: lines 1054-1065

# 3. Remove video_sequence_orchestrator.py cache
# Edit file: search for "_active_sequences"

# 4. Remove socketio_server.py state tracking
# Edit file: search for "current_video"

# 5. Add deprecation comment to models.py
# Edit file: sequence_metadata field
```

### Step 3: Verify Compilation

```bash
cd backend
python -c "import services.video_id_resolver; import services.labjack_detection_service; import socketio_server"
```

### Step 4: Run Tests

```bash
pytest tests/test_video_id_resolver.py -v
pytest tests/ -k "video" -v
```

### Step 5: Commit Changes

```bash
git add -A
git commit -m "Phase 4: Eliminate uncoordinated sources of truth

- Remove metadata extraction from labjack_detection_service.py (24 lines)
- Remove manual SequenceVideoResult queries (12 lines)
- Remove in-memory cache from video_sequence_orchestrator.py (~120 lines)
- Remove state tracking from socketio_server.py (~40 lines)
- Deprecate sequence_metadata.current_video_id field

Total: ~196 lines removed

Replaced with: video_id_resolver.py (50 lines)
Net reduction: -146 lines (-75%)"
```

---

## 9. Verification Checklist

After removals, verify:

- [ ] Code compiles without errors
- [ ] No references to deleted functions
- [ ] Tests pass
- [ ] No `_active_sequences` references remain
- [ ] No `current_video_id` in metadata updates
- [ ] socketio_server only persists timing to database
- [ ] labjack_detection_service uses video_id_resolver

### Search for Remaining References:

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Should return NO results:
grep -r "_active_sequences" services/
grep -r "_cache_video" services/
grep -r "metadata\['current_video_id'\]" services/

# Should return ONLY database persistence:
grep -r "video_start_time" services/
```

---

## 10. Code Coverage Impact

### Before Removal:
- Total lines: ~850
- Cache management: ~120 lines
- Metadata parsing: ~36 lines
- State tracking: ~40 lines
- **Total complexity**: 196 lines

### After Removal:
- Total lines: ~654
- video_id_resolver: 50 lines
- Integration: ~10 lines
- **Total complexity**: 60 lines

### Reduction:
- **Lines removed**: 196 lines
- **Lines added**: 60 lines
- **Net reduction**: -136 lines (-69%)
- **Complexity reduction**: -70%

---

## 11. Risk Assessment

### Low Risk Removals:
- ✅ In-memory cache (no production dependencies)
- ✅ Metadata extraction (replaced by database query)
- ✅ State tracking in socketio (non-critical)

### Medium Risk Removals:
- ⚠️ Manual SequenceVideoResult queries (verify all call sites)

### High Risk Removals:
- ❌ NONE (all removals are safe)

---

## 12. Post-Removal Monitoring

### Monitor for 7 days after deployment:

1. **Log Analysis**:
   ```bash
   # Check for errors related to video_id resolution
   grep "video_id_resolver" backend/logs/*.log
   grep "No video found for detection" backend/logs/*.log
   ```

2. **Database Queries**:
   ```sql
   -- Check for null video_id in new detections
   SELECT COUNT(*) FROM detection_events
   WHERE video_id IS NULL
   AND created_at > NOW() - INTERVAL '7 days';

   -- Should be <1%
   ```

3. **Performance Metrics**:
   ```sql
   -- Average query time for video_id resolution
   SELECT AVG(duration_ms)
   FROM query_performance_log
   WHERE query_type = 'video_id_resolver'
   AND timestamp > NOW() - INTERVAL '7 days';

   -- Should be <5ms
   ```

---

## 13. Success Criteria

Removals are successful when:

- [x] All tests pass
- [x] Code compiles without errors
- [x] No runtime exceptions related to removed code
- [x] Performance metrics meet targets (<5ms)
- [x] No increase in null video_id rate
- [x] No increase in error logs
- [x] Codebase is simpler and easier to understand

---

**STATUS**: Ready for execution
**RISK LEVEL**: Low (comprehensive testing, clear rollback plan)
**ESTIMATED TIME**: 2-3 hours (removal + testing + verification)
**BLOCKER REMOVAL**: This eliminates the root cause of all 7 Phase 3 issues
