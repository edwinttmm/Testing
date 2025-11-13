# Detection Events API Fix

## Problem
The backend API was only returning detection event counts instead of the actual detection event data, making it impossible for the frontend to display detailed detection information.

## Solution

### Changes Made to `/backend/routers/video_sequence_testing.py`

1. **Added DetectionEventSummary schema** (lines 171-178)
   - Schema for serializing detection events to the frontend
   - Fields: id, timestamp, video_relative_timestamp, signal_type, channel, signal_value

2. **Updated VideoResultSummary schema** (line 190)
   - Added `detection_events: List[DetectionEventSummary]` field
   - Provides array of actual detection events instead of just count

3. **Modified detection query** (lines 742-761)
   - Changed from `.count()` to `.order_by(DetectionEvent.timestamp).all()`
   - Now retrieves actual detection events ordered by timestamp
   - Serializes events into DetectionEventSummary objects

4. **Updated response** (line 784)
   - Includes `detection_events=detection_events_summary` in VideoResultSummary

## API Response Changes

### Before:
```json
{
  "video_id": "abc123",
  "detection_count": 5,
  "detection_events": []  // Always empty
}
```

### After:
```json
{
  "video_id": "abc123", 
  "detection_count": 5,
  "detection_events": [
    {
      "id": "det-001",
      "timestamp": 1234567890.123,
      "video_relative_timestamp": 2.5,
      "signal_type": "GPIO",
      "channel": 0,
      "signal_value": 1.0
    },
    // ... more events
  ]
}
```

## Impact

- Frontend can now display actual detection events in the UI
- Detection timing can be visualized
- Enables detailed analysis of detection patterns
- Maintains backward compatibility (detection_count still present)

## Files Modified

- `/backend/routers/video_sequence_testing.py`
  - DetectionEventSummary schema added
  - VideoResultSummary schema updated
  - Detection query changed from count() to all()
  - Response serialization updated
