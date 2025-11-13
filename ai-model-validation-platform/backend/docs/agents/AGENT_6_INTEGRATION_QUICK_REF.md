# Agent #6 Integration Quick Reference

## Files Modified

### `backend/services/dedicated_labjack_monitor.py`

#### 1. Imports Added (Lines 40-46)
```python
# Import detection window clamp service for overlap prevention
from services.detection_window_clamp_service import (
    clamp_video_windows,
    assign_detection,
    VideoTiming,
    ClampedWindow
)
```

#### 2. Cache Added (Lines 104-105)
```python
# Detection window clamping (prevents overlaps in multi-video sequences)
self._clamped_windows: Dict[str, List[ClampedWindow]] = {}  # session_id -> clamped windows
```

#### 3. Cache Invalidation (Lines 875-892)
```python
def invalidate_sequence_cache(self, session_id: str):
    """
    Invalidate sequence context cache - called by video lifecycle events.

    INTEGRATION FIX: Also clears clamped window cache so they're regenerated
    with updated video timing information.
    """
    with self.lock:
        # Clear sequence context cache
        session_cache = self.active_sessions.get(session_id, {})
        session_cache.pop('sequence_context', None)

        # Clear clamped windows cache (will be regenerated on next detection)
        if session_id in self._clamped_windows:
            del self._clamped_windows[session_id]
            logger.info(f"🔧 Cleared clamped windows cache for session {session_id}")

    logger.info(f"✅ Cache invalidated for session {session_id}")
```

#### 4. New Method: `_get_or_create_clamped_windows()` (Lines 1278-1352)
**Purpose**: Generate non-overlapping detection windows using clamping service

**Key Logic**:
- Check cache first
- Convert video timing dict → VideoTiming objects
- Call `clamp_video_windows(timings, grace_ms=2000)`
- Cache and return ClampedWindow objects

#### 5. Modified: `_determine_video_from_timing()` (Lines 1354-1410)
**BEFORE**: Used raw grace period logic with potential overlaps
**AFTER**: Uses clamped windows for deterministic assignment

**Key Changes**:
- Lookup session_id from active_sessions
- Get or create clamped windows
- Call `assign_detection(trigger_time, clamped_windows)`
- Return (video_id, match_type) tuple

#### 6. New Method: `_determine_video_from_timing_legacy()` (Lines 1412-1477)
**Purpose**: Fallback to original logic when clamping not available

**Used When**:
- Session ID cannot be determined
- Clamped windows generation fails
- Single-video sessions (clamping unnecessary)

---

## Integration Points

### Where Clamping is Used

1. **Detection Enrichment** (`_enrich_hil_event_context()`)
   - Calls `_determine_video_from_timing()`
   - Uses clamped windows to assign video_id

2. **Retry Logic** (`_get_video_id_with_retry()`)
   - Calls `_determine_video_from_timing()` on each retry
   - Benefits from cached clamped windows

3. **Cache Invalidation** (`invalidate_sequence_cache()`)
   - Called by orchestrator after lifecycle events
   - Clears clamped windows so they regenerate with fresh timing

---

## Log Signatures

### Successful Integration
```
🔧 Generated 2 clamped detection windows for session abc123
  📊 Video video_1: [1762383483.000s - 1762383488.261s] (grace: 1000ms, clamped: True)
  📊 Video video_2: [1762383488.261s - 1762383493.503s] (grace: 2000ms, clamped: False)
✅ Detection at 1762383485.123s assigned to video_1 via clamping service (match_type=exact_window_match)
```

### Fallback to Legacy
```
Could not determine session_id for clamped windows - using legacy logic
✅ LEGACY: Detection at 1762383485.123s assigned to video_1
```

### Cache Invalidation
```
🔧 Cleared clamped windows cache for session abc123
✅ Cache invalidated for session abc123
```

---

## Verification Commands

```bash
# Syntax check
python3 -m py_compile backend/services/dedicated_labjack_monitor.py

# Import test
python3 -c "from services.dedicated_labjack_monitor import DedicatedLabJackMonitor; print('✅ Import successful')"

# Run clamping service tests
pytest backend/tests/test_detection_window_clamp_service.py -v
```

---

## Before/After Comparison

### BEFORE (Raw Grace Period)
```python
def _determine_video_from_timing(self, video_timing, trigger_time):
    grace_start = video_start - 2.0  # Fixed 2s grace

    if grace_start <= trigger_time < video_end:
        return video_id  # Could match BOTH videos in overlap zone
```

**Problem**: Overlapping grace periods → non-deterministic assignment

### AFTER (Clamped Windows)
```python
def _determine_video_from_timing(self, video_timing, trigger_time):
    clamped_windows = self._get_or_create_clamped_windows(session_id, video_timing)

    result = assign_detection(trigger_time, clamped_windows)
    if result:
        video_id, match_type = result
        return video_id  # Deterministic - windows never overlap
```

**Solution**: Gap-splitting algorithm → deterministic assignment

---

**Status**: ✅ Integration Complete
**Date**: 2025-11-12
**Agent**: #6 Window Clamp Integration Specialist
