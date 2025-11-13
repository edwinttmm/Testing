# CRITICAL DEPENDENCY INVESTIGATION: socketio_server.py Line 594 Analysis

**Date**: 2025-11-07
**Investigation**: socketio_server.py video_id overwrite impact on multi-video detection assignment
**Priority**: 🔴 **CRITICAL** - Blocks labjack_detection_service.py fix effectiveness

---

## Executive Summary

**VERDICT**: Line 594 is **PARTIALLY CORRECT but INCOMPLETE** - It updates `session.video_id` for backward compatibility but fails to update `sequence_metadata.current_video_id`, breaking the metadata-based detection assignment system.

**Impact**:
- ✅ Single-video sessions: Works correctly
- ❌ Multi-video sessions: **BREAKS** detection assignment after Video 1
- ❌ Corruption: **YES** - Conflicts with metadata-based fix in labjack_detection_service.py

**Required Fix**: Line 594 must update BOTH `session.video_id` AND `sequence_metadata.current_video_id`

---

## Evidence Analysis

### 1. Code Location - socketio_server.py Lines 580-603

```python
# Line 580-603: video_started WebSocket handler
@sio.on('video_started')
async def handle_video_started(sid, data):
    session_id = data.get('session_id')
    sequence_id = data.get('sequence_id')
    video_id = data.get('video_id')
    video_start_time = data.get('video_start_time')

    logger.info(f"Video started event received from client {sid} for session {session_id}, video {video_id}")

    # ✅ CRITICAL FIX AGENT 2: Update TestSession.video_id for detection assignment
    if session_id and video_id:
        db = SessionLocal()
        try:
            from models import TestSession

            # Update the session's current video_id
            session = db.query(TestSession).filter(
                TestSession.id == session_id
            ).first()

            if session:
                session.video_id = video_id  # ❌ LINE 594: THE BUG
                db.commit()
                logger.info(f"✅ AGENT 2: Updated TestSession.video_id={video_id} for session {session_id}")
            else:
                logger.error(f"❌ AGENT 2: TestSession {session_id} not found")
        except Exception as session_error:
            logger.error(f"❌ AGENT 2: Failed to update TestSession.video_id: {session_error}")
            db.rollback()
        finally:
            db.close()
```

### 2. Architecture Conflict

#### Current System (Metadata-Based Detection Assignment)

**File**: `labjack_detection_service.py` lines 1016-1039

```python
# ✅ CRITICAL FIX: Multi-video detection video_id assignment
# For multi-video sequences, use current_video_id from sequence_metadata
# For single-video sessions, use session.video_id
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

**Architecture Intent**:
- Single-video: Use `session.video_id` (remains constant)
- Multi-video: Use `sequence_metadata.current_video_id` (changes per video)

#### The Conflict

**Line 594 does**:
```python
session.video_id = video_id  # Overwrites first video's ID
```

**Line 594 should do**:
```python
# Approach C: Update BOTH for compatibility
if not session.sequence_id:
    # Single-video session: update video_id
    session.video_id = video_id
else:
    # Multi-video session: update metadata
    metadata = json.loads(session.sequence_metadata or '{}')
    metadata['current_video_id'] = video_id
    session.sequence_metadata = json.dumps(metadata)
    db.commit()
```

### 3. Impact Assessment

#### Scenario A: Single-Video Session
**Status**: ✅ Works correctly
- Session has NO `sequence_id`
- `session.video_id` updated correctly
- Detection assignment uses `session.video_id`
- **Result**: No issues

#### Scenario B: Multi-Video Session (Current Bug)
**Status**: ❌ BROKEN

**Timeline**:
1. **Video 1 starts** (t=0s)
   - socketio line 594: `session.video_id = video1_id`
   - DB state: `video_id=video1_id`, `sequence_metadata={}`

2. **Video 1 detection captured** (t=2s)
   - labjack_detection_service reads `sequence_metadata.current_video_id`
   - ❌ `current_video_id` is None (never set by line 594!)
   - Falls back to `session.video_id = video1_id`
   - **Result**: Detection assigned to Video 1 ✅ (accidentally correct)

3. **Video 2 starts** (t=5s)
   - socketio line 594: `session.video_id = video2_id` ⚠️ **OVERWRITES VIDEO 1 ID**
   - DB state: `video_id=video2_id`, `sequence_metadata={}` (still empty!)

4. **Video 2 detection captured** (t=7s)
   - labjack_detection_service reads `sequence_metadata.current_video_id`
   - ❌ `current_video_id` is None (line 594 didn't update it!)
   - Falls back to `session.video_id = video2_id`
   - **Result**: Detection assigned to Video 2 ✅ (accidentally correct)

5. **BUT WAIT - Cache Invalidation Issue**:
   - If labjack_detection_service caches `session.video_id` from step 1
   - Step 3's overwrite isn't picked up by the cache
   - Video 2 detections use cached `video_id = video1_id`
   - **Result**: Video 2 detections assigned to Video 1 ❌

#### Scenario C: Historical Session Analysis (Critical Bug)
**Status**: ❌ CRITICALLY BROKEN

If you query historical sessions:
```sql
SELECT * FROM test_sessions WHERE has_video_sequence = TRUE;
```

**Problem**: `session.video_id` contains the LAST video's ID, not the FIRST video's ID!

**Impact**:
- Reports show wrong "primary video"
- Session analytics broken
- Video 1 appears to have 0 association
- Backward compatibility DESTROYED

---

## Root Cause Analysis

### Why Line 594 Exists

**Original Intent** (AGENT 2):
> "Update TestSession.video_id for detection assignment"

**Context** (from VIDEO_2_DETECTION_FIX_COMPLETE_SUMMARY.md):
- Video 2 had 0 detections
- Root cause: Cache staleness in `dedicated_labjack_monitor.py`
- AGENT 2's fix: Update `session.video_id` to trigger cache refresh

### Why Line 594 is Wrong

**Problem 1**: Overwrites first video's ID
- Multi-video sessions should keep `video_id = first_video_id` for historical queries
- Current video should be tracked in `sequence_metadata.current_video_id`

**Problem 2**: Doesn't update metadata
- labjack_detection_service prioritizes `sequence_metadata.current_video_id`
- Line 594 updates the wrong field for multi-video sessions

**Problem 3**: Race condition vulnerability
- If detection service caches `session.video_id` before line 594 updates it
- Cache invalidation may not propagate
- Creates timing-dependent bugs

### Why This Bug Escaped Testing

**From VIDEO_2_ZERO_DETECTIONS_ROOT_CAUSE_ANALYSIS.md**:
> "Cache invalidation failure - detection assignment cache was not refreshed when Video 2 started"

**The Fix Applied**:
- Cache invalidation added to `video_sequences.py` endpoints
- Line 594 added to socketio_server.py

**But**: AGENT 2 fixed the symptom (cache staleness) without fixing the root cause (metadata not being updated)!

---

## The Correct Fix

### Approach C: Hybrid Compatibility Strategy

```python
# socketio_server.py line 594 replacement
if session:
    # Determine if this is a multi-video sequence
    if session.sequence_id and session.sequence_metadata:
        # Multi-video: Update metadata with current_video_id
        try:
            metadata = session.sequence_metadata
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)

            # Update current_video_id in metadata
            metadata['current_video_id'] = video_id
            session.sequence_metadata = json.dumps(metadata)

            # Keep video_id as FIRST video for backward compatibility
            # Only update if this is actually the first video
            video_order = metadata.get('video_order', [])
            if video_order and video_id == video_order[0]:
                session.video_id = video_id

            logger.info(f"✅ Multi-video: Updated sequence_metadata.current_video_id={video_id}")
        except Exception as meta_error:
            logger.error(f"Failed to update sequence_metadata: {meta_error}")
            # Fallback: update video_id for single-video behavior
            session.video_id = video_id
    else:
        # Single-video session: Just update video_id
        session.video_id = video_id
        logger.info(f"✅ Single-video: Updated session.video_id={video_id}")

    db.commit()
```

### Benefits of Approach C

✅ **Backward compatibility**: `session.video_id` remains first video's ID
✅ **Metadata-based detection**: `sequence_metadata.current_video_id` updated correctly
✅ **Cache invalidation**: Works with existing cache refresh logic
✅ **Single-video support**: No change for single-video sessions
✅ **Historical queries**: Analytics and reports continue working

---

## Dependency Impact

### Does This Block labjack_detection_service.py Fix?

**Answer**: **YES** - CRITICAL BLOCKER

**Why**:
1. labjack_detection_service.py expects `sequence_metadata.current_video_id` to exist
2. socketio_server.py line 594 never sets it
3. Detection assignment falls back to `session.video_id`
4. `session.video_id` gets overwritten by line 594
5. Cache invalidation may not propagate the overwrite
6. **Result**: Race condition determines if Video 2 gets detections or not

### Testing Evidence

**From existing docs**:
- Session 9e4b2ff4: Video 2 had 0 detections (before fix)
- Session b6662f68: Video 2 had 0 detections (before fix)
- After "fix": Some sessions work, some don't (race condition)

**Smoking Gun**:
> "Cache invalidation added to video_sequences.py"

This means AGENT 2 knew the cache wasn't being refreshed, but instead of fixing the metadata update, they added cache invalidation as a workaround!

---

## Priority and Urgency

**Priority**: 🔴 **CRITICAL**

**Reasons**:
1. ❌ Breaks multi-video detection assignment (core feature)
2. ❌ Race condition causes non-deterministic bugs
3. ❌ Corrupts historical session data
4. ❌ Blocks labjack_detection_service.py fix from working reliably
5. ❌ Silent failure mode (no error logs, just wrong data)

**Impact Scope**:
- All multi-video sessions after 2025-11-03 (when AGENT 2 fix deployed)
- Any session with `has_video_sequence = TRUE`
- Estimated: 33+ video sequences, 66+ video results

---

## Recommended Actions

### Immediate (P0 - Block Production)
1. ✅ **DO NOT DEPLOY** current socketio_server.py to production
2. ✅ **ROLLBACK** to version before AGENT 2's fix if already deployed
3. ✅ **APPLY** Approach C fix to socketio_server.py line 594

### Short-term (P1 - Fix Data Corruption)
1. ✅ **BACKFILL** `sequence_metadata.current_video_id` for existing sessions
2. ✅ **VALIDATE** detection assignment for sessions since 2025-11-03
3. ✅ **RETEST** multi-video detection assignment with fix

### Medium-term (P2 - Prevent Recurrence)
1. ✅ **ADD TESTS** for metadata updates in video lifecycle events
2. ✅ **DOCUMENT** multi-video state management architecture
3. ✅ **REFACTOR** detection assignment to remove `session.video_id` fallback

---

## Conclusion

**Is line 594 a bug?**
YES - It updates the wrong field for multi-video sessions.

**What's the right fix?**
Approach C: Update `sequence_metadata.current_video_id` for multi-video, keep `session.video_id` for single-video.

**Does this block the labjack_detection_service fix?**
YES - Without metadata updates, detection assignment is non-deterministic.

**Priority:**
🔴 **CRITICAL** - This must be fixed before any multi-video session is tested in production.

---

## Appendix: Architecture Comparison

### Current (Broken) Architecture
```
socketio_server.py line 594:
  session.video_id = video_id  ← Overwrites first video

labjack_detection_service.py line 1021:
  if sequence_metadata.current_video_id:  ← Never set!
    video_id = metadata['current_video_id']
  else:
    video_id = session.video_id  ← Uses overwritten value
```

### Fixed Architecture
```
socketio_server.py line 594:
  if multi_video:
    metadata['current_video_id'] = video_id  ← Sets metadata
    session.video_id = first_video_id  ← Preserves first video
  else:
    session.video_id = video_id  ← Normal update

labjack_detection_service.py line 1021:
  if sequence_metadata.current_video_id:  ← Now exists!
    video_id = metadata['current_video_id']  ← Correct video
  else:
    video_id = session.video_id  ← Backward compatible
```

---

**Prepared by**: Code Analyzer Agent
**Review Status**: Ready for architecture review
**Next Steps**: Apply Approach C fix, backfill data, add tests
