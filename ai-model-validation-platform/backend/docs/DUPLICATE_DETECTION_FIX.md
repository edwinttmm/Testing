# Duplicate Detection Bug Fix

## Problem Summary

**Bug**: Every detection appeared TWICE in the timeline with identical timestamps.

**Evidence**:
- Frame 0: Two detections at 0.000s (identical voltage 4.21V)
- Frame 4: Two detections at 0.167s (identical voltage 4.24V)
- Frame 6: Two detections at 0.250s (identical voltage 4.20V)
- Pattern continued throughout all test sessions

**Impact**:
- Inflated detection count (78 shown, but only 39 real detections)
- Broke ground truth matching (expects 1:1, gets 2:1 ratio)
- Confused metrics and validation results
- Made precision/recall calculations incorrect

## Root Cause

The duplication occurred in `socketio_server.py` where detection events were being emitted to **multiple WebSocket rooms** with the **same event name** (`'detection_event'`).

### Duplication Points

#### 1. `simulate_hil_test_session()` function (lines 465-469)

```python
# OLD CODE - CAUSED DUPLICATES:
await sio.emit('detection_event', detection_data, room=room)           # Emit #1
await sio.emit('detection_event', detection_data, room='detections')   # Emit #2 (DUPLICATE!)
await sio.emit('hil_update', detection_data, room='general')
```

**Problem**: If a client was subscribed to BOTH the session-specific room AND the 'detections' room, they would receive the same detection event twice.

#### 2. `emit_detection_event()` function (lines 559-562)

```python
# OLD CODE - CAUSED DUPLICATES:
room = f"session_{test_session_id}"
await sio.emit('detection_event', detection_data, room=room)          # Emit #1
await sio.emit('detection_event', detection_data, room='detections')  # Emit #2 (DUPLICATE!)
```

**Problem**: Same issue - clients subscribed to multiple rooms would receive duplicates.

## Solution

### Fix Applied

Removed the redundant emission to the general `'detections'` room. Clients should subscribe to the **session-specific room** only.

#### 1. `simulate_hil_test_session()` - FIXED

```python
# FIXED CODE:
# Emit detection_event only to session room to prevent duplicates
# Clients should subscribe to the session-specific room, NOT the general 'detections' room
await sio.emit('detection_event', detection_data, room=room)

# Emit separate event type for monitoring dashboards (different event name)
await sio.emit('hil_update', detection_data, room='general')
```

#### 2. `emit_detection_event()` - FIXED

```python
# FIXED CODE:
# Emit to test session room only to prevent duplicates
# Clients should subscribe to session-specific room, NOT the general 'detections' room
room = f"session_{test_session_id}"
await sio.emit('detection_event', detection_data, room=room)
```

### Why This Works

1. **Single source of truth**: Each detection is emitted exactly once per session
2. **Clear subscription model**: Clients subscribe to `session_{session_id}` room
3. **Separate monitoring channel**: Global monitoring uses `'hil_update'` event (different event name)
4. **No database changes needed**: This was purely a WebSocket emission issue

## Verification

### Expected Behavior After Fix

1. **Detection count should be accurate**: 39 real detections (not 78)
2. **Timeline should show unique detections**: No duplicate timestamps
3. **Ground truth matching should work**: 1:1 ratio between detections and GT objects
4. **Metrics should be correct**: Precision/recall calculated on actual detection count

### Testing Checklist

- [ ] Run HIL test session
- [ ] Verify detection count matches LabJack events (not doubled)
- [ ] Check timeline for duplicate timestamps
- [ ] Verify ground truth matching finds correct pairs
- [ ] Confirm metrics are accurate (TP + FP = total detections)

## Client-Side Changes (if needed)

### Before (Caused Duplicates):
```javascript
// DON'T DO THIS - subscribes to multiple rooms
socket.emit('subscribe_to_detections', { session_id: sessionId });
socket.emit('subscribe_to_updates', { type: 'detections' });
```

### After (Correct):
```javascript
// Subscribe to session-specific room only
socket.emit('join_session', { session_id: sessionId });

// Listen for detection_event
socket.on('detection_event', (data) => {
  // Handle detection - will receive exactly once
});

// Optional: Subscribe to global monitoring (different event name)
socket.on('hil_update', (data) => {
  // Handle monitoring updates
});
```

## Related Files

- **Fixed**: `/backend/socketio_server.py` (lines 465-469, 559-562)
- **No changes needed**:
  - `/backend/services/labjack_monitoring_service.py` (stores to DB correctly)
  - `/backend/src/services/temporal_expansion.py` (Option C expansion is virtual only)
  - `/backend/src/services/ground_truth_matching_service.py` (matching logic is correct)

## Technical Details

### Why Option C Expansion Was NOT the Cause

Option C (temporal expansion) creates **virtual detections** in-memory for matching purposes but:
- Does NOT write to database
- Does NOT emit WebSocket events
- Only used during ground truth matching algorithm
- Collapses duplicates after matching

The expansion was working correctly. The duplication was purely in WebSocket emission.

### Why Database Inserts Were Correct

The `labjack_monitoring_service.py` stores detections correctly:
- Line 163-184: Single `INSERT INTO detection_events` per detection
- Line 108-116: Edge detection logic prevents duplicate storage
- Database records were correct (39 detections stored)

The bug was only in how those 39 detections were being **broadcast** via WebSocket.

## Prevention

### Guidelines for Future WebSocket Emissions

1. **One event, one room**: Emit each event to exactly one room per session
2. **Use different event names**: If broadcasting to multiple rooms, use different event names
3. **Document room subscriptions**: Clearly document which rooms clients should join
4. **Test with multiple subscriptions**: Verify clients subscribed to multiple rooms don't get duplicates

### Code Review Checklist

When reviewing WebSocket emission code, check for:
- Multiple `sio.emit()` calls with the same event name
- Same data being sent to different rooms
- Clients potentially subscribed to multiple destination rooms
- Missing documentation about room subscription patterns

## Conclusion

**Root cause**: WebSocket emission to multiple rooms with same event name
**Fix**: Emit to session-specific room only, use different event names for monitoring
**Impact**: Fixes duplicate detections, corrects metrics, enables proper ground truth matching
**Verification**: Detection count should match actual LabJack events (not doubled)

The fix is minimal, focused, and does not require any database migrations or client-side changes (assuming clients are already subscribing to session-specific rooms).
