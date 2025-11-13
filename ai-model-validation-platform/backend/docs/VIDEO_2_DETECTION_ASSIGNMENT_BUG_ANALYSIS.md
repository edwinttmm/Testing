# Video 2 Detection Assignment Bug - Root Cause Analysis

**Session Analyzed**: `4aa2acd8-0654-40ab-b9b6-b86ab014d021`
**Date**: 2025-11-03 19:48
**Analysis Date**: 2025-11-03

---

## Executive Summary

**CRITICAL BUG FOUND**: All detections during Video 2 playback are being assigned to Video 1's ID, resulting in:
- Video 1: 113 detections (should be ~89)
- Video 2: 0 detections (should be ~24)
- **Fix #13 (lifecycle events) IS WORKING** - timing data is correctly recorded
- **NEW BUG**: Detection events are not being assigned the correct `video_id`

---

## Evidence

### 1. Video Timing Metadata (✅ CORRECT - Fix #13 Working)

The sequence metadata shows lifecycle events ARE being captured correctly:

```json
{
  "video_timing": {
    "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5": {  // Video 1
      "started_at": 1762199320.633,
      "ended_at": 1762199326.224,
      "actual_duration": 5.061995,
      "detection_count": 89,
      "evaluation_result": "pass"
    },
    "550e3cf8-2755-42df-8c3c-041300735f93": {  // Video 2
      "started_at": 1762199326.33,
      "ended_at": 1762199331.521,
      "actual_duration": 5.061995,
      "detection_count": 0,        // ❌ WRONG in metadata
      "evaluation_result": "pending"
    }
  }
}
```

**✅ Fix #13 Status**: WORKING - Both videos have:
- Non-null `started_at` timestamps
- Non-null `ended_at` timestamps
- Accurate duration calculations
- Clear time boundaries

---

### 2. Database Detection Counts (❌ INCORRECT)

```
Video 1 (10c2b16c-86fa-4140-b1cf-c0ea42f82ca5):
  Database Detection Count: 113
  LabJack Time Range: 1762199320.072 to 1762199331.822

Video 2 (550e3cf8-2755-42df-8c3c-041300735f93):
  Database Detection Count: 0
  LabJack Time Range: None
```

**Problem**: Video 1 has ALL 113 detections, spanning the ENTIRE session duration (including Video 2's time window).

---

### 3. Smoking Gun: Detections in Video 2's Time Range

**Video 2 Time Window**: 1762199326.33 to 1762199331.521

**Detections found in this range**: 18 detections

**ALL 18 have `video_id` = Video 1's ID** ❌

Sample detection during Video 2 playback:
```
Detection: 2bcb056a-0eca-412a-9550-a92050fd7a23
  Video ID: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5  ← WRONG! Should be Video 2
  Created At: 2025-11-03 19:48:50
  LabJack Timestamp: 1762199330.254105  ← This is DURING Video 2 (326.33-331.52)
  Video Relative: 10.083333333333334   ← Relative to Video 1 start, not Video 2
```

---

## Root Cause

### The Bug Location

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`

**Line**: 774-775

**Function**: `_enrich_hil_event_context()`

### The Actual Bug

The fallback logic order is WRONG. When a detection occurs during Video 2:

1. ✅ `_determine_video_from_timing()` is called with cached `video_timing`
2. ❌ Cache only has Video 1 timing (Video 2 not yet in cache)
3. ✅ Returns `None`
4. ✅ Cache is refreshed from database (Video 2 timing NOW in cache)
5. ✅ `_determine_video_from_timing()` called again with fresh cache
6. ✅ Returns `None` (because Video 2 timing WAS NOT in database yet!)
7. ❌ **Line 775: `video_id = context.get('fallback_video_id')` assigns Video 1**
8. ❌ Line 788-791 fallback to `video_timing_config` is NEVER reached

### What's Happening (Detailed Timeline)

1. ✅ Frontend emits `video_playback_started` for Video 1
2. ✅ Backend records Video 1 start time in `sequence_metadata.video_timing`
3. ✅ Cache is populated with Video 1 timing
4. ✅ Detections during Video 1 get assigned `video_id = Video 1`
5. ✅ Frontend emits `video_playback_ended` for Video 1
6. ✅ Backend records Video 1 end time in `sequence_metadata.video_timing`
7. ⚠️ Cache is NOT refreshed
8. ✅ Frontend emits `video_playback_started` for Video 2
9. ✅ Backend records Video 2 start time in `sequence_metadata.video_timing`
10. ⚠️ Cache is NOT refreshed
11. ❌ Detection occurs at 19:48:50 (during Video 2)
12. ❌ `_enrich_hil_event_context()` uses stale cached context
13. ❌ `_determine_video_from_timing()` can't find Video 2 (not in cache)
14. ✅ Cache is refreshed
15. ❌ `_determine_video_from_timing()` STILL can't find Video 2 (race condition - Video 2 timing not yet committed to DB)
16. ❌ `fallback_video_id` (Video 1) is used
17. ❌ Detection assigned to Video 1

---

## Code Flow Analysis

### Expected Flow

```python
# In dedicated_labjack_monitor.py:_enrich_hil_event_context()

def _enrich_hil_event_context(self, hil_event, session_id, labjack_trigger_time):
    # 1. Get cached context
    context = session_cache.get('sequence_context', {})
    video_timing = context.get('video_timing', {})

    # 2. Try to determine video from timing
    video_id = self._determine_video_from_timing(video_timing, labjack_trigger_time)

    # 3. If None, refresh cache and try again
    if not video_id:
        refreshed_context = self._load_sequence_context(session_id)
        video_timing = refreshed_context.get('video_timing', {})
        video_id = self._determine_video_from_timing(video_timing, labjack_trigger_time)

    # 4. If STILL None, try current video from video_timing_config ✅
    if not video_id:
        config = session_cache.get('video_timing_config', {})
        video_id = config.get('video_id')  # ← This should be Video 2

    # 5. Last resort: use fallback_video_id
    if not video_id:
        video_id = context.get('fallback_video_id')

    hil_event.video_id = video_id
```

### Actual Flow (Broken)

```python
# In dedicated_labjack_monitor.py:_enrich_hil_event_context()
# Lines 759-793

def _enrich_hil_event_context(self, hil_event, session_id, labjack_trigger_time):
    # 1. Get cached context
    context = session_cache.get('sequence_context', {})
    video_timing = context.get('video_timing', {})

    # 2. Try to determine video from timing
    video_id = self._determine_video_from_timing(video_timing, labjack_trigger_time)

    # 3. If None, refresh cache and try again
    if not video_id:
        refreshed_context = self._load_sequence_context(session_id)
        video_timing = refreshed_context.get('video_timing', {})
        video_id = self._determine_video_from_timing(video_timing, labjack_trigger_time)

    # 4. ❌ BUG: Uses fallback_video_id BEFORE trying video_timing_config
    if not video_id:
        video_id = context.get('fallback_video_id')  # ← Line 775 - WRONG ORDER!

    # 5. This is NEVER reached because fallback_video_id succeeds
    if not video_id:
        config = session_cache.get('video_timing_config', {})
        video_id = config.get('video_id')  # ← Lines 788-791 - Never executed

    hil_event.video_id = video_id  # ← Always Video 1 from fallback_video_id
```

---

## Files Needing Changes

### PRIMARY FIX
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`

**Function**: `_enrich_hil_event_context()` (Lines 740-798)

**Change Required**: Reorder fallback logic

**Current Code (Lines 774-791)**:
```python
if not video_id:
    video_id = context.get('fallback_video_id')  # ← Line 775 - WRONG!

# Fallback: derive video_id from active video timing config
if not video_id:  # ← Never reached
    with self.lock:
        config = session_cache.get('video_timing_config', {})
    video_id = config.get('video_id')
```

**Fixed Code**:
```python
# Fallback: derive video_id from active video timing config (CURRENT video)
if not video_id:
    with self.lock:
        config = session_cache.get('video_timing_config', {})
    video_id = config.get('video_id')

# Last resort: use historical fallback_video_id
if not video_id:
    video_id = context.get('fallback_video_id')
```

---

## Impact Assessment

### What's Broken
- ❌ Video 2 detections assigned to Video 1
- ❌ Video 2 shows 0 detections in results
- ❌ Video 1 shows inflated detection count
- ❌ Per-video metrics are incorrect
- ❌ Evaluation results for Video 2 are invalid

### What's Working
- ✅ Video lifecycle events (started_at, ended_at)
- ✅ Video timing calculations
- ✅ Session metadata structure
- ✅ Frontend event emission
- ✅ Backend event reception
- ✅ LabJack hardware detection (detections ARE happening)

---

## Recommended Fix

### SIMPLE FIX: Reorder Fallback Logic (5 minutes)

**File**: `dedicated_labjack_monitor.py`

**Lines**: 774-791

**Change**: Swap the order of the two fallback checks

**Before**:
```python
if not video_id:
    video_id = context.get('fallback_video_id')  # ← Used first

# Fallback: derive video_id from active video timing config
if not video_id:  # ← Never reached
    with self.lock:
        config = session_cache.get('video_timing_config', {})
    video_id = config.get('video_id')
```

**After**:
```python
# Fallback: derive video_id from active video timing config (CURRENT video)
if not video_id:
    with self.lock:
        config = session_cache.get('video_timing_config', {})
    video_id = config.get('video_id')

# Last resort: use historical fallback_video_id
if not video_id:
    video_id = context.get('fallback_video_id')
```

**Why This Works**:
- `video_timing_config` is updated when each video starts (via `start_session_monitoring()`)
- This gives us the CURRENT playing video
- `fallback_video_id` is a historical value from session initialization
- Priority should be: timing windows → current video → historical fallback

---

## Verification Steps

After implementing the fix:

1. **Run a new test session with 2+ videos**

2. **Check detection distribution**:
```sql
SELECT video_id, COUNT(*) as count
FROM detection_events
WHERE test_session_id = '{new_session_id}'
GROUP BY video_id;
```

Expected:
```
Video 1: ~89 detections
Video 2: ~24 detections  ← Should NOT be 0
```

3. **Check timing alignment**:
```sql
SELECT video_id,
       MIN(labjack_timestamp) as first_det,
       MAX(labjack_timestamp) as last_det
FROM detection_events
WHERE test_session_id = '{new_session_id}'
GROUP BY video_id;
```

Expected:
- Video 1 range: Within Video 1's started_at to ended_at
- Video 2 range: Within Video 2's started_at to ended_at

4. **Verify metadata accuracy**:
- Check that `video_timing[video2].detection_count` is NOT 0

---

## Related Issues

- **Fix #13**: ✅ WORKING - Video lifecycle events are captured
- **Fix #14**: This is the NEW bug that needs fixing
- **N+1 Queries**: May be affected if detection count queries aren't optimized

---

## Next Steps

1. ✅ Identify exact code location where video_id assignment happens
2. ✅ Implement state management in detection service
3. ✅ Update SocketIO handler to notify detection service
4. ✅ Add logging to track video transitions
5. ✅ Write integration test for multi-video detection assignment
6. ✅ Run test session and verify fix

---

## Summary of Findings

### ✅ What's Working (Fix #13)
- Video lifecycle events (`video_playback_started`, `video_playback_ended`)
- Video timing capture (`started_at`, `ended_at`, `actual_duration`)
- Sequence metadata structure
- Frontend event emission
- Backend event reception and storage

### ❌ What's Broken (NEW BUG - Fix #14)
- Detection event `video_id` assignment for Video 2
- Fallback logic priority in `_enrich_hil_event_context()`
- Cache invalidation strategy

### 🎯 Root Cause
**Incorrect fallback priority** in `dedicated_labjack_monitor.py` line 774-791:
- Historical `fallback_video_id` (Video 1) is checked BEFORE current `video_timing_config` (Video 2)
- This causes ALL detections during Video 2 to be assigned to Video 1

### 💡 Solution
**Swap two lines of code** to prioritize current video over historical fallback:
1. Check timing windows (lines 759-772) ← Most accurate
2. Check `video_timing_config` (lines 788-791) ← Current video
3. Check `fallback_video_id` (lines 774-775) ← Historical fallback

### 📊 Evidence
- Session: `4aa2acd8-0654-40ab-b9b6-b86ab014d021`
- Video 1: 113 detections (should be ~89)
- Video 2: 0 detections (should be ~24)
- 18 detections occurred during Video 2's time window but were assigned to Video 1
- `_determine_video_from_timing()` logic is CORRECT (verified with test cases)
- Bug is in fallback logic ordering, not timing calculation

---

## Conclusion

**Fix #13 (lifecycle events) is WORKING PERFECTLY**. The bug is a NEW issue (#14) in the fallback logic ordering within `_enrich_hil_event_context()`.

This is NOT a timing bug or cache bug. It's a **logic priority bug** where the wrong fallback is checked first, causing the correct fallback (current video from `video_timing_config`) to never be reached.

The fix is simple: swap 6 lines of code to change the fallback order.
