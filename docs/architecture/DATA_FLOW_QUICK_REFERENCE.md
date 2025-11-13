# Data Flow Quick Reference Guide

**Related:** [Comprehensive Data Flow Analysis](./COMPREHENSIVE_DATA_FLOW_ANALYSIS.md)

---

## Quick Navigation

### Phase 1: Test Initialization (T0 Capture)
```
User Click → API Call → T0 Timestamp → Database → WebSocket → UI Update
```
**Key Files:** `hil_test_complete.py::start_hil_test_session()` (Line 267)

### Phase 2: Video Playback Start (T1 Capture)
```
Video Play → T1 Timestamp → Orchestrator → Metadata Update → WebSocket
```
**Key Files:** `hil_test_complete.py::start_video_playback()` (Line 537)

### Phase 3: Real-Time Detection
```
LabJack → Detection Monitor → Video Assignment → GT Matching → WebSocket
```
**Key Files:** `labjack_detection_service.py::_monitoring_loop()`

### Phase 4: Video Completion
```
Video End → Database → Orchestrator Sync → Next Video/Complete → WebSocket
```
**Key Files:** `hil_test_complete.py::end_video_playback()` (Line 744)

### Phase 5: Session Completion
```
Validate → Reassign → Match GT → Calculate Metrics → Commit → WebSocket
```
**Key Files:** `session_completion_service.py::complete_session()` (Line 214)

### Phase 6: Results Retrieval
```
API Call → Database Query → Aggregate → Normalize → Cache → Display
```
**Key Files:** `enhanced_hil_results_endpoints.py`, `HILResults.tsx`

---

## Critical Data Structures

### T0 Timestamp Capture
```python
{
  "command_timestamp": 1699714200.123456,
  "precision_ns": 150,
  "capture_latency_ns": 200,
  "system_time_utc": "2025-11-11T14:30:00.123456Z"
}
```

### T1 Video Start
```python
{
  "video_start_timestamp": 1699714230.456789,
  "video_id": "video_2",
  "precision_ns": 200,
  "capture_source": "frontend_video_onPlay_event",
  "metadata": {"fps": 30, "duration": 45.5}
}
```

### Detection Event
```python
{
  "id": "det_abc123",
  "detection_timestamp": 1699714235.789012,
  "video_id": "video_2",
  "video_relative_timestamp": 5.33,
  "frame_number": 160,
  "ground_truth_match_id": "gt_xyz789",
  "match_status": "matched",
  "actual_latency_ms": 45.8,
  "validation_result": "PASS"
}
```

### Sequence Metadata
```json
{
  "video_timing": {
    "video_1": {
      "started_at": 1699714230.123,
      "ended_at": 1699714260.456,
      "video_play_offset_ms": 0
    },
    "video_2": {
      "started_at": 1699714261.789,
      "ended_at": 1699714306.912,
      "video_play_offset_ms": 31666
    }
  }
}
```

---

## WebSocket Events

| Event | Trigger | Payload |
|-------|---------|---------|
| `session_started` | Session creation | t0_timestamp, timing_quality |
| `video_started` | Video play | video_id, t1_timestamp, presentation_delay_ms |
| `detection_event` | LabJack detection | detection object, metrics_update |
| `video_completed` | Video end | actual_duration_ms, sequence_complete |
| `session_completed` | Test finished | final_metrics, analysis |

---

## Critical Validations

### Session Completion Validation
✅ All videos have `started_at` timestamp
✅ All videos have `ended_at` timestamp
✅ No videos in "pending" status
✅ sequence_metadata exists
❌ FAIL → HTTP 400 with error details

### Video ID Assignment
1. Check `sequence_metadata.video_timing`
2. Find video where `started_at <= detection_timestamp <= ended_at`
3. If no match, assign to currently playing video
4. If still NULL, defer to post-completion reassignment

### Ground Truth Matching
1. Calculate distance: `|detection_time - gt_time|`
2. Check if within tolerance (default: 100ms)
3. Choose closest GT if multiple in window
4. Each GT matches only once (first come, first served)

---

## State Transitions

### Session States
```
CREATED → RUNNING → COMPLETED
              ↓
        VALIDATION_FAILED
```

### Video States
```
PENDING → PLAYING → COMPLETED
```

### Detection States
```
DETECTED → ASSIGNED → MATCHED → VALIDATED
```

---

## Database Schema (Quick Reference)

### TestSession
- `command_start_timestamp` (T0)
- `presentation_delay_ms` (T1 - T0)
- `sequence_metadata` (video_timing, video_ids)
- `status` ("running", "completed", "validation_failed")

### SequenceVideoResult
- `video_start_time` (T1 for this video)
- `video_end_time`
- `actual_duration_ms`
- `video_play_offset_ms` (cumulative offset in sequence)
- `actual_detection_count`
- `ground_truth_comparison` (TP/FP/FN/metrics)

### DetectionEvent
- `detection_timestamp` (hardware time)
- `video_id` (resolved from timestamp)
- `video_relative_timestamp` (seconds from video start)
- `ground_truth_match_id`
- `actual_latency_ms`
- `validation_result` ("PASS"/"FAIL")

---

## Timing Calculations

### Presentation Delay
```
delay_ms = (T1 - T0) * 1000
```

### Video-Relative Timestamp
```
video_rel_time = detection_timestamp - video_start_time
```

### Frame Number
```
frame_number = int(video_rel_time * fps)
```

### Actual Latency
```
latency_ms = (detection_timestamp - expected_timestamp) * 1000
```

---

## Common Issues & Solutions

### Issue: NULL video_id in detections
**Cause:** Race condition - detection before video lifecycle events
**Solution:** Automatic reassignment during session completion

### Issue: Session completion blocked
**Cause:** Missing video timing data in sequence_metadata
**Solution:** Check frontend video event handlers (onPlay, onEnded)

### Issue: Incorrect metrics display
**Cause:** Frontend recalculation instead of backend data
**Solution:** Always use `ground_truth_comparison` from API response

### Issue: Real-time updates not working
**Cause:** WebSocket disconnection or room not joined
**Solution:** Check socket connection, emit 'join_session' event

---

## Performance Optimizations

### Database Queries
✅ Single GROUP BY query for detection counts
✅ Eager load ground truth matches
✅ Index on (test_session_id, video_id)

### API Response
✅ Pydantic serialization with camelCase aliases
✅ 5-minute cache for completed sessions
✅ Batch load all sequence video results

### Frontend
✅ useMemo for filtered data
✅ Debounced video selection
✅ Virtual scrolling for large detection tables

---

## File Locations

### Backend Services
- `backend/api/hil_test_complete.py` - Main HIL API endpoints
- `backend/services/session_completion_service.py` - Completion logic
- `backend/services/video_sequence_orchestrator.py` - Multi-video coordination
- `backend/services/labjack_detection_service.py` - Hardware monitoring
- `backend/services/ground_truth_matching_service.py` - GT matching
- `backend/socketio_server.py` - WebSocket server

### Frontend Components
- `frontend/src/pages/HILResults.tsx` - Results display page
- `frontend/src/services/websocketService.ts` - WebSocket client
- `frontend/src/services/api.ts` - API service
- `frontend/src/utils/hilResultsNormalization.ts` - Data normalization

---

## Testing Checklist

- [ ] T0 timestamp captured on session start
- [ ] T1 timestamp captured on video play
- [ ] LabJack monitoring started
- [ ] Detections assigned to correct video_id
- [ ] Ground truth matching executed
- [ ] Metrics calculated correctly
- [ ] WebSocket events broadcast
- [ ] Session completion validation passes
- [ ] Results display with correct data

---

**For detailed information, see:** [Comprehensive Data Flow Analysis](./COMPREHENSIVE_DATA_FLOW_ANALYSIS.md)
