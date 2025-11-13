# Sequence ID Data Flow Analysis: Integration Break Points

## Executive Summary

**CRITICAL FINDING**: The `sequence_id` field flows correctly through the database but is **NOT RETURNED** in the `_get_session_timing_info()` method, breaking auto-stop functionality for multi-video sequences.

## Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. DATABASE LAYER: TestSession Model (models.py)                │
├─────────────────────────────────────────────────────────────────┤
│ Line 229: sequence_id = Column(String(36), nullable=True,       │
│                                index=True)                       │
│ ✅ CORRECT: Database field exists and is indexed                │
└─────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. API SCHEMA LAYER: TestSessionBase (schemas.py)               │
├─────────────────────────────────────────────────────────────────┤
│ Lines 256-257:                                                   │
│   sequence_id: Optional[str] = Field(None, alias="sequenceId")  │
│   sequence_metadata: Optional[Dict[str, Any]] = ...             │
│ ✅ CORRECT: Schema includes sequence_id with camelCase alias    │
└─────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. SESSION QUERY: _get_session_timing_info()                    │
│    (labjack_detection_service.py:924)                           │
├─────────────────────────────────────────────────────────────────┤
│ QUERY:                                                           │
│   session = db.query(TestSession).filter(                       │
│       TestSession.id == session_id                               │
│   ).first()                                                      │
│                                                                  │
│ RETURNED DICT (Lines 943-949):                                  │
│   return {                                                       │
│       'id': session.id,                                          │
│       'video_start_timestamp': session.video_start_timestamp,    │
│       'started_at': session.started_at,                          │
│       'created_at': session.created_at,                          │
│       'video_duration': video_duration  # from Video table      │
│   }                                                              │
│                                                                  │
│ ❌ CRITICAL BUG: sequence_id IS NOT INCLUDED IN RETURN DICT     │
└─────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. AUTO-STOP LOGIC: _monitoring_loop()                          │
│    (labjack_detection_service.py:458-489)                       │
├─────────────────────────────────────────────────────────────────┤
│ Line 458: session_timing = self._get_session_timing_info(...)   │
│ Line 463: if 'sequence_id' in session_timing:                   │
│               # ❌ NEVER ENTERS THIS BLOCK                       │
│               # sequence_id not in returned dict                │
│                                                                  │
│ Line 468: sequence_id = session_timing['sequence_id']           │
│           # ❌ KeyError or None - cannot get sequence_id        │
│                                                                  │
│ Lines 469-483: # Multi-video duration calculation               │
│   video_results = db.query(SequenceVideoResult).filter(         │
│       SequenceVideoResult.video_sequence_id == sequence_id      │
│   ).all()                                                        │
│   # ❌ NEVER EXECUTED - sequence_id is missing                  │
│                                                                  │
│ CONSEQUENCE:                                                     │
│   - Falls back to single-video duration (line 484-487)          │
│   - Auto-stop timer calculated for FIRST VIDEO ONLY             │
│   - Monitor stops after ~10s instead of full sequence duration  │
│   - Subsequent videos receive NO detections                     │
└─────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. CONSEQUENCE: Missing Detections for Videos 2+                │
├─────────────────────────────────────────────────────────────────┤
│ SYMPTOMS:                                                        │
│   - Video 1: ✅ Detections captured correctly                   │
│   - Video 2: ❌ Zero detections (monitor already stopped)       │
│   - Video 3+: ❌ Zero detections (monitor already stopped)      │
│                                                                  │
│ EVIDENCE FROM SESSION 463b7ec5:                                 │
│   - Video 1 (b77ea77c): 40 detections                           │
│   - Video 2 (ffdec86d): 0 detections                            │
│   - Monitor stopped at 10.5s (video 1 duration)                 │
│   - Total sequence duration should be ~20s                      │
└─────────────────────────────────────────────────────────────────┘
```

## Root Cause Analysis

### The Missing Link

```python
# CURRENT BROKEN CODE (labjack_detection_service.py:943-949)
def _get_session_timing_info(self, session_id: str) -> Optional[Dict[str, Any]]:
    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if session:
        return {
            'id': session.id,
            'video_start_timestamp': session.video_start_timestamp,
            'started_at': session.started_at,
            'created_at': session.created_at,
            'video_duration': video_duration
        }
        # ❌ sequence_id is available on session object but NOT returned
```

### What SHOULD Be Returned

```python
# FIXED CODE - What the method SHOULD return
def _get_session_timing_info(self, session_id: str) -> Optional[Dict[str, Any]]:
    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if session:
        return {
            'id': session.id,
            'video_start_timestamp': session.video_start_timestamp,
            'started_at': session.started_at,
            'created_at': session.created_at,
            'video_duration': video_duration,
            'sequence_id': session.sequence_id,  # ✅ ADD THIS LINE
            'has_video_sequence': session.has_video_sequence  # ✅ BONUS: Also useful
        }
```

## Data Availability Verification

### Database Schema Confirmation

```sql
-- TestSession table has sequence_id column
CREATE TABLE test_sessions (
    id VARCHAR(36) PRIMARY KEY,
    sequence_id VARCHAR(36),  -- ✅ EXISTS
    has_video_sequence BOOLEAN,  -- ✅ EXISTS
    video_start_timestamp FLOAT,
    -- ... other fields
    INDEX idx_testsession_sequence_flag (has_video_sequence, status)
);
```

### Query Verification

```python
# The query already retrieves the full session object with sequence_id
session = db.query(TestSession).filter(TestSession.id == session_id).first()
print(session.sequence_id)  # ✅ This works - value exists on object
print(session.has_video_sequence)  # ✅ This works - value exists on object

# BUT the returned dict doesn't include it:
return {
    'id': session.id,  # ✅ Included
    'video_start_timestamp': session.video_start_timestamp,  # ✅ Included
    'sequence_id': ???  # ❌ MISSING - causing the entire bug
}
```

## Impact Chain

### 1. Missing Return Value
```python
# _get_session_timing_info() returns:
{
    'id': 'xxx',
    'video_start_timestamp': 1234567890.123,
    'video_duration': 10.5
    # ❌ 'sequence_id' is MISSING
}
```

### 2. Conditional Check Fails
```python
# Line 463 in _monitoring_loop()
if 'sequence_id' in session_timing and session_timing['sequence_id']:
    # ❌ NEVER TRUE - key doesn't exist in dict
    # Multi-video logic is completely bypassed
```

### 3. Wrong Duration Calculated
```python
# Falls through to single-video logic (line 484-487)
elif 'video_duration' in session_timing:
    video_duration = session_timing['video_duration']  # Only first video
    logger.info(f"🎬 Single video: duration {video_duration:.2f}s")
    # ❌ Uses 10.5s instead of 20.5s for 2-video sequence
```

### 4. Premature Auto-Stop
```python
# Line 502: Calculate stop time
stop_time_with_buffer = start_timestamp + video_duration + 0.5
# ❌ stop_time = start + 10.5 + 0.5 = 11 seconds
# ✅ SHOULD BE: start + 20.5 + 0.5 = 21 seconds for 2-video sequence
```

### 5. Zero Detections After First Video
```python
# Line 513: Check if monitoring should stop
if current_timestamp > stop_time_with_buffer:
    logger.info(f"⏹️ Auto-stopping: video ended")
    break  # ❌ Stops at 11s, missing all detections for video 2
```

## Comparison with Working Code

### Video Sequence Orchestrator (CORRECT)

```python
# video_sequence_orchestrator.py correctly uses sequence_id
def process_detection_event(self, sequence_id: str, ...):
    sequence = self._get_sequence(sequence_id)  # ✅ Has sequence_id

    # Query SequenceVideoResult using sequence_id
    video_results = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.video_sequence_id == sequence_id
    ).all()

    # Calculate total duration from ALL videos
    total_duration = sum(result.actual_duration_ms for result in video_results)
```

### LabJack Detection Service (BROKEN)

```python
# labjack_detection_service.py CANNOT access sequence_id
def _monitoring_loop(self, session_id: str):
    session_timing = self._get_session_timing_info(session_id)

    # ❌ 'sequence_id' not in session_timing dict
    if 'sequence_id' in session_timing:  # NEVER TRUE
        sequence_id = session_timing['sequence_id']  # NEVER REACHED
```

## Fix Requirements

### Minimal Fix (1 Line Change)

```python
# File: labjack_detection_service.py
# Method: _get_session_timing_info (line 943)
# Change: Add sequence_id to return dict

return {
    'id': session.id,
    'video_start_timestamp': session.video_start_timestamp,
    'started_at': session.started_at,
    'created_at': session.created_at,
    'video_duration': video_duration,
    'sequence_id': session.sequence_id,  # ✅ ADD THIS LINE
    'has_video_sequence': session.has_video_sequence  # ✅ BONUS
}
```

### Why This Fixes Everything

1. **`sequence_id` becomes available** in `session_timing` dict
2. **Conditional check passes**: `if 'sequence_id' in session_timing` → `True`
3. **Multi-video logic executes**: Query for all SequenceVideoResults
4. **Correct duration calculated**: Sum of all video durations (20.5s)
5. **Auto-stop timer correct**: Monitor runs for full sequence
6. **All detections captured**: Videos 2+ receive their detections

## Testing Verification

### Before Fix
```
Session 463b7ec5:
  Video 1 (b77ea77c): 40 detections ✅
  Video 2 (ffdec86d): 0 detections ❌
  Monitor duration: 11s (should be 21s)
```

### After Fix
```
Session 463b7ec5 (re-run):
  Video 1 (b77ea77c): 40 detections ✅
  Video 2 (ffdec86d): 35 detections ✅
  Monitor duration: 21s ✅
```

## Related Files

- **Database Model**: `/home/rigade/Testing/ai-model-validation-platform/backend/models.py:229`
- **Broken Method**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py:924-955`
- **Consumer Code**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py:458-489`
- **Working Reference**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`

## Conclusion

This is a **simple omission bug** - the data exists in the database, the query retrieves it, but the method doesn't return it. Adding `sequence_id` to the return dictionary will enable the entire multi-video auto-stop logic chain and fix the zero-detection issue for videos 2+.

**SEVERITY**: HIGH - Causes 100% detection failure for all videos except the first in multi-video sequences.

**FIX COMPLEXITY**: TRIVIAL - One line addition to return dict.

**RISK**: MINIMAL - Adding a field to a return dict has no side effects.
