# Multi-Video Timing Testing Guide

**Quick Reference for Testing Per-Video Timing Implementation**

---

## 🧪 Manual Testing Checklist

### Test 1: Single Video (Backward Compatibility)
**Expected:** Works exactly as before, no regression

```bash
# Start test session
POST /api/v1/hil-test/session/start
{
  "project_id": "test-project",
  "video_id": "video-1"
}

# Start video
POST /api/v1/hil-test/session/{session_id}/video/start
{
  "video_id": "video-1",
  "fps": 24,
  "duration_s": 60
}

# Get results (no video_id parameter)
GET /api/enhanced-hil/test-sessions/{session_id}/corrected-results

✅ Expected: Uses session-level timing, no sequence queries
```

---

### Test 2: Multi-Video Sequence (3 Videos)
**Expected:** Each video gets correct offset and timing

```bash
# Video 1: Starts at T0
POST /api/v1/hil-test/session/{session_id}/video/start
{
  "video_id": "video-1",
  "duration_s": 10
}
# Check DB: video_play_offset_ms = 0ms

# Video 2: Starts at T0 + 10s
POST /api/v1/hil-test/session/{session_id}/video/start
{
  "video_id": "video-2",
  "duration_s": 15
}
# Check DB: video_play_offset_ms = 10000ms

# Video 3: Starts at T0 + 25s
POST /api/v1/hil-test/session/{session_id}/video/start
{
  "video_id": "video-3",
  "duration_s": 20
}
# Check DB: video_play_offset_ms = 25000ms

# Get per-video results
GET /api/enhanced-hil/test-sessions/{session_id}/corrected-results?video_id=video-2

✅ Expected: Uses video-2 timing (offset = 10000ms)
```

---

### Test 3: Per-Video Results API
**Expected:** Different timing for each video

```bash
# Video 1 results
GET /corrected-results?video_id=video-1
# Expected: startup_delay_ms = 0ms (or small value)

# Video 2 results
GET /corrected-results?video_id=video-2
# Expected: startup_delay_ms = 10000ms

# Video 3 results
GET /corrected-results?video_id=video-3
# Expected: startup_delay_ms = 25000ms

✅ Expected: Each video shows different startup delay
```

---

## 🔍 Database Verification

### Check Stored Timing Data:
```sql
-- View all sequence video results
SELECT
  svr.video_id,
  svr.sequence_order,
  svr.video_start_time,
  svr.video_play_offset_ms,
  svr.actual_duration_ms,
  svr.video_status
FROM sequence_video_results svr
WHERE svr.video_sequence_id = '<sequence-id>'
ORDER BY svr.sequence_order;

-- Expected Output:
-- video-1: order=0, offset=0ms, duration=10000ms
-- video-2: order=1, offset=10000ms, duration=15000ms
-- video-3: order=2, offset=25000ms, duration=20000ms
```

### Verify Cumulative Offsets:
```sql
-- Check offset calculations
SELECT
  video_id,
  sequence_order,
  video_play_offset_ms,
  actual_duration_ms,
  -- Next video's offset should be current offset + duration
  video_play_offset_ms + actual_duration_ms as expected_next_offset
FROM sequence_video_results
WHERE video_sequence_id = '<sequence-id>'
ORDER BY sequence_order;
```

---

## 📊 Log Verification

### Expected Log Patterns:

#### Video Start Logs:
```
✅ Session 123: Video video-1 duration resolved to 10.0s for LabJack auto-stop
✅ Stored per-video timing for video video-1: start_time=1698765432.123, offset_ms=0.0

✅ Session 123: Video video-2 duration resolved to 15.0s for LabJack auto-stop
✅ Stored per-video timing for video video-2: start_time=1698765442.456, offset_ms=10000.0
```

#### Results API Logs:
```
✅ Using per-video timing for video video-2: video_play_offset_ms=10000.0ms, video_start_time=1698765442.456
✅ 🎯 Using per-video LabJack reference time for video video-2: 1698765442.456 (position offset: 10000.0ms)
```

### Warning Logs to Check:
```
⚠️ No SequenceVideoResult found for video video-2, using session-level timing
# This is OK for single-video tests or if data not yet stored
```

---

## 🐛 Troubleshooting

### Issue: "No SequenceVideoResult found" warning
**Diagnosis:**
```sql
-- Check if entry exists
SELECT * FROM sequence_video_results WHERE video_id = '<video-id>';

-- Check if session is marked as sequence
SELECT has_video_sequence FROM test_sessions WHERE id = '<session-id>';
```

**Fix:**
- Ensure `TestSession.has_video_sequence = True`
- Ensure `SequenceVideoResult` entry created before video starts
- Check foreign key relationships

---

### Issue: Offset calculation incorrect
**Diagnosis:**
```sql
-- Check previous videos' durations
SELECT
  video_id,
  sequence_order,
  actual_duration_ms
FROM sequence_video_results
WHERE video_sequence_id = '<sequence-id>'
  AND sequence_order < <current-order>
ORDER BY sequence_order;
```

**Fix:**
- Verify `actual_duration_ms` is populated correctly
- Check that videos played in sequential order
- Verify no videos were skipped

---

### Issue: Latency calculations wrong for video N
**Diagnosis:**
```python
# Add debug logging in enhanced_hil_results_endpoints.py:
logger.warning(f"DEBUG: video_id={video_id}")
logger.warning(f"DEBUG: sequence_video_result={sequence_video_result}")
logger.warning(f"DEBUG: video_startup_delay_ms={video_startup_delay_ms}")
logger.warning(f"DEBUG: labjack_start_time={labjack_start_time}")
```

**Common Causes:**
- `video_id` not passed to API
- `SequenceVideoResult` missing timing data
- Cumulative offset calculation error
- LabJack reference time not adjusted

---

## 🎯 Success Criteria

### ✅ Implementation Success Indicators:

1. **Single-Video Tests:**
   - No change in behavior from before
   - No new database queries for non-sequence sessions
   - Latency calculations match previous results

2. **Multi-Video Sequences:**
   - Each video stores timing in `SequenceVideoResult`
   - Cumulative offset increases correctly
   - Per-video results API returns different timing

3. **Edge Cases:**
   - Handles missing `SequenceVideoResult` gracefully
   - Falls back to session timing when needed
   - Logs clear warnings for debugging

4. **Performance:**
   - No significant slowdown in API response times
   - Database queries remain efficient
   - No N+1 query problems

---

## 📈 Performance Metrics

### Expected Query Counts:

#### Video Start Endpoint:
```
Single Video: 2-3 queries
Multi-Video:  5-6 queries (adds sequence queries)
```

#### Results API:
```
Single Video: 10-15 queries
Multi-Video:  12-17 queries (adds 1-2 queries for SequenceVideoResult)
```

### Timing Benchmarks:
```
Video Start:  < 100ms
Results API:  < 500ms (depends on detection count)
```

---

## 🔧 Development Testing Script

```python
# backend/tests/test_multi_video_timing.py

def test_multi_video_timing_flow():
    """End-to-end test of multi-video timing"""
    # Create sequence
    session = create_test_session(has_video_sequence=True)
    sequence = create_video_sequence(session_id=session.id, video_ids=["v1", "v2", "v3"])

    # Start video 1
    response1 = start_video("v1", session_id=session.id)
    assert response1["success"] == True

    # Verify video 1 timing
    svr1 = get_sequence_video_result("v1")
    assert svr1.video_play_offset_ms == 0.0

    # Start video 2 (after 10 seconds)
    time.sleep(10)
    response2 = start_video("v2", session_id=session.id)

    # Verify video 2 timing
    svr2 = get_sequence_video_result("v2")
    assert svr2.video_play_offset_ms >= 10000.0

    # Get per-video results
    results1 = get_corrected_results(session.id, video_id="v1")
    results2 = get_corrected_results(session.id, video_id="v2")

    # Verify different timing
    assert results1["video_timing"]["startup_delay_ms"] != results2["video_timing"]["startup_delay_ms"]
```

---

## 📞 Support

**If tests fail:**
1. Check database schema matches `models.py`
2. Verify foreign keys are correct
3. Check log files for warnings
4. Run SQL queries from "Database Verification" section
5. Add debug logging to track data flow

**Common Gotchas:**
- Forgetting to pass `video_id` parameter to results API
- Not setting `has_video_sequence = True` on session
- SequenceVideoResult created but timing not populated
- Frontend not sending video duration correctly

---

**Happy Testing!** 🎉
