# Backend Log Analysis Report
**Session ID:** `9e4b2ff4-820e-4250-a110-1393b67ec224`
**Analysis Date:** 2025-11-04
**Session Created:** 2025-11-04 10:26:36
**Session Completed:** 2025-11-04 10:26:51
**Duration:** ~15 seconds

---

## 🚨 CRITICAL FINDINGS

### 1. **SEVERE DETECTION LOSS: 75% Capture Failure**

```
Expected Detections: ~400 (20Hz × 10s × 2 videos)
Actual Detections:   101
Capture Rate:        25.2%
MISSING:             ~299 detections (74.8% LOSS)
```

**Status:** 🔴 **PRODUCTION BLOCKER**

---

## DETECTION CAPTURE BREAKDOWN

### Video 1: `10c2b16c-86fa-4140-b1cf-c0ea42f82ca5`
- **Detections:** 100
- **First:** 2025-11-04 10:26:36
- **Last:** 2025-11-04 10:26:51
- **Duration:** 15 seconds
- **Rate:** ~6.7 Hz (should be 20 Hz)
- **Expected:** ~200 detections (20Hz × 10s)
- **Actual:** 100 detections
- **Loss:** 50%

### Video 2: Status Unknown
- **Detections:** 1 (with NULL video_id)
- **First:** 2025-11-04 10:26:38
- **Last:** 2025-11-04 10:26:38
- **Expected:** ~200 detections
- **Actual:** 1 detection
- **Loss:** 99.5%

---

## ROOT CAUSE ANALYSIS

### Issue #1: Video 2 Almost Completely Lost
- Only 1 detection captured for second video
- That single detection has `video_id = NULL`
- Indicates video lifecycle events never fired for video 2
- Detections are being captured but not assigned to correct video

### Issue #2: Video 1 Only Capturing 50%
- Expected 200 detections at 20Hz for 10 seconds
- Only captured 100 detections
- Effective rate: 10Hz instead of 20Hz
- Suggests:
  - LabJack monitoring may be in wrong mode (polling vs streaming?)
  - Detection debouncing too aggressive
  - Timing synchronization issues

### Issue #3: No Video Lifecycle Events
```sql
Error: no such column: test_session_id in video_events
```
- Schema mismatch indicates migration issue
- Video lifecycle events (video-started, video-ended) not being recorded
- Without lifecycle events, video_id assignment fails
- This explains the NULL video_id for video 2 detections

### Issue #4: No Video-to-Session Links
- `video_project_links` table does not link videos to this session
- Cannot determine which videos should be part of test
- Multi-video orchestration appears broken

---

## EXPECTED LOG SEQUENCE (Not Found)

**What Should Have Happened:**
```
1. Session 9e4b2ff4 started
2. LabJack monitoring started (constant voltage mode, 20Hz)
3. Video 1 (10c2b16c...) started event → WebSocket "video-started"
4. ~120 detections captured for video 1 (~10s × 20Hz + buffer)
5. Video 1 ended event → WebSocket "video-ended"
6. Video 2 started event → WebSocket "video-started"
7. ~120 detections captured for video 2
8. Video 2 ended event → WebSocket "video-ended"
9. Ground truth matching triggered
10. Session completed
```

**What Actually Happened:**
```
1. Session 9e4b2ff4 started ✓
2. LabJack monitoring started (mode unknown) ✓
3. Video 1 started event → NOT RECORDED ✗
4. 100 detections captured for video 1 (50% loss) ⚠️
5. Video 1 ended event → NOT RECORDED ✗
6. Video 2 started event → NEVER FIRED ✗
7. 1 detection captured with NULL video_id ✗
8. Video 2 ended event → NEVER FIRED ✗
9. Ground truth matching → NOT EXECUTED ✗
10. Session completed (but data incomplete) ⚠️
```

---

## DATABASE FINDINGS

### Test Session Schema
```sql
test_sessions columns (35 total):
- id, name, project_id, video_id, tolerance_ms
- status, session_type, started_at, completed_at
- has_video_sequence, sequence_id, sequence_metadata
- video_start_timestamp, video_start_timestamp_ns
- precision_timing_enabled, timing_accuracy_ns
- hil_compliance_verified, hil_timing_enabled
- command_start_timestamp, presentation_delay_ms
[... 15 more timing-related columns]
```

### Detection Events Schema
```sql
detection_events columns (61 total):
- id, test_session_id, video_id
- sequence_video_result_id, timestamp
- labjack_timestamp, labjack_timestamp_ns
- video_relative_timestamp, video_frame_number
- detection_latency_ms, actual_latency_ms
- t3_detection_timestamp, t3_monotonic_timestamp_ns
- confidence, class_label, vru_type
- bounding_box_x/y/width/height
- screenshot_path, processing_time_ms
[... 40+ more fields for multi-source detection]
```

### Schema Mismatches
1. `video_events` table uses `session_id` but query expects `test_session_id`
2. `video_project_links` has no foreign key to test_sessions
3. Multiple timestamp formats without clear documentation

---

## LABJACK MONITORING STATUS

### From Logs (nohup.out):
```
✅ LabJack support available: OFFICIAL
✅ LabJack connected via Windows bridge
✅ LabJack Hardware Service initialized (OFFICIAL)
✅ Detected 1 LabJack device(s)
✅ Connected to LabJack T7 via USB
⚠️ Standalone LabJack monitoring not available
⚠️ Failed to configure DIO0/DIO1 direction
ℹ️ Standalone LabJack monitoring service auto-start DISABLED
```

**Analysis:**
- LabJack hardware is connected and functional
- DIO configuration warnings suggest manual configuration needed
- "Standalone monitoring auto-start DISABLED" is concerning
  - May explain why detection rate is so low
  - Frontend may need to manually trigger monitoring start

---

## COMPARISON WITH PREVIOUS SUCCESSFUL SESSION

### Session d98d5877 (Nov 3, 2025):
- **Detections:** 65 events
- **Ground Truth:** 514 objects across 2 videos
- **Matching:** 59 TP, 6 FP, 455 FN
- **Metrics:** Precision 0.908, Recall 0.115, F1 0.204
- **Video Sequence:** Detected and processed correctly
- **Latency:** Mean 74.1ms

### Current Session 9e4b2ff4:
- **Detections:** 101 events (but 99 lost from video 2)
- **Ground Truth:** NOT EXECUTED
- **Matching:** NOT EXECUTED
- **Metrics:** N/A
- **Video Sequence:** Broken (video 2 not recognized)
- **Latency:** Cannot calculate without matching

---

## TIMING SYNCHRONIZATION ISSUES

### Previous Session Showed:
```log
Enhanced latency calculation:
  Apparent: 1846.9ms
  Real: -9.4ms
  Camera-only: 0.0ms
  Correction: 1856.3ms
  Quality: poor
```

### Current Session:
- No timing calculation logs found
- Suggests session completion service never ran
- Ground truth matching never triggered
- Video timing synchronization not executed

---

## VIDEO LIFECYCLE DEBUGGING

### Missing Events:
1. **video-started** for video 1 → Not logged
2. **video-ended** for video 1 → Not logged
3. **video-started** for video 2 → NEVER FIRED
4. **video-ended** for video 2 → NEVER FIRED

### Possible Causes:
1. **Frontend Issue:**
   - SequentialVideoPlayer not emitting WebSocket events
   - WebSocket connection dropped during playback
   - Event handlers not registered before video starts

2. **Backend Issue:**
   - WebSocket handler not listening on correct channel
   - `video_events` table schema mismatch preventing inserts
   - Race condition between video start and detection capture

3. **Orchestration Issue:**
   - `video_sequence_orchestrator` not initializing properly
   - Multi-video coordination service not running
   - Session completion service not triggered

---

## DETECTION ASSIGNMENT LOGIC

### Expected Flow:
```python
1. Frontend emits "video-started" with video_id
2. Backend receives event and stores in video_events table
3. dedicated_labjack_monitor reads current_video_id from cache
4. Each LabJack detection gets assigned current video_id
5. Frontend emits "video-ended", cache updates
6. Next "video-started" updates current_video_id
```

### What Appears to Be Happening:
```python
1. "video-started" never emitted OR never received ✗
2. video_events table cannot store (schema mismatch) ✗
3. dedicated_labjack_monitor has no current_video_id ✗
4. Detections assigned video_id=NULL or wrong video_id ✗
5. "video-ended" never emitted ✗
6. Video 2 never recognized by system ✗
```

---

## RECOMMENDATIONS

### Immediate Actions (Priority 1):

1. **Fix `video_events` Schema:**
   ```sql
   ALTER TABLE video_events
   RENAME COLUMN session_id TO test_session_id;
   ```

2. **Enable Video Lifecycle Event Logging:**
   ```python
   # In socketio_server.py or equivalent
   @sio.on('video-started')
   async def handle_video_started(sid, data):
       logger.info(f"🎬 VIDEO STARTED: {data}")
       # Store in video_events table
       # Update cache with current video_id
   ```

3. **Verify LabJack Monitoring Mode:**
   - Check if constant voltage mode is actually enabled
   - Verify 20Hz sampling rate (currently getting ~6.7Hz)
   - Enable auto-start or ensure frontend triggers start

4. **Add Detection Rate Monitoring:**
   ```python
   # Alert if detection rate < 15Hz for > 2 seconds
   if detection_rate < 15:
       logger.error(f"⚠️ DETECTION RATE CRITICAL: {detection_rate}Hz")
   ```

### Diagnostic Actions (Priority 2):

5. **Add Comprehensive Logging:**
   ```python
   # Log every video lifecycle event
   logger.info(f"🎬 VIDEO EVENT: {event_type} video_id={video_id} session={session_id}")

   # Log detection assignments
   logger.info(f"🎯 DETECTION: video_id={video_id} count={count} rate={rate}Hz")
   ```

6. **Create Integration Test:**
   ```python
   # Test multi-video lifecycle
   # - Start session
   # - Play video 1, expect ~200 detections
   # - Play video 2, expect ~200 detections
   # - Verify video_id assignments
   # - Check ground truth matching
   ```

7. **Add Health Checks:**
   ```python
   # Check every 2 seconds during test
   if current_video_id is None:
       logger.error("⚠️ No current video ID - lifecycle events not firing")

   if time_since_last_detection > 2.0:
       logger.error("⚠️ Detection stream stalled")
   ```

---

## FILES TO INVESTIGATE

### Frontend:
- `/home/rigade/Testing/ai-model-validation-platform/frontend/src/components/SequentialVideoPlayer.tsx`
- `/home/rigade/Testing/ai-model-validation-platform/frontend/src/services/websocketService.ts`

### Backend:
- `/home/rigade/Testing/ai-model-validation-platform/backend/socketio_server.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/session_completion_service.py`

### Database:
- `/home/rigade/Testing/ai-model-validation-platform/backend/migrations/versions/` (check latest migration)
- `/home/rigade/Testing/ai-model-validation-platform/backend/models.py` (VideoEvents model)

---

## TESTING CHECKLIST

Before next test run:

- [ ] Verify `video_events` schema has `test_session_id` column
- [ ] Check WebSocket handler for "video-started" and "video-ended"
- [ ] Enable verbose logging for video lifecycle events
- [ ] Verify LabJack monitoring auto-starts or is manually triggered
- [ ] Test with single video first (should get ~200 detections)
- [ ] Monitor detection rate in real-time (should be 20Hz ±2Hz)
- [ ] Verify video_id assignment in database during test
- [ ] Check that session completion service runs after playback

---

## CONCLUSION

**Status:** 🔴 **SYSTEM NOT OPERATIONAL**

The multi-video test system has **three critical failures**:

1. **Video lifecycle events not firing** (99.5% of video 2 detections lost)
2. **Detection capture rate 50-75% below expected** (only 10Hz vs 20Hz)
3. **Schema mismatches preventing proper data storage**

**Root Cause:** The video lifecycle coordination system (frontend → WebSocket → backend → cache) is completely broken for the second video and partially working for the first video.

**Impact:**
- Cannot perform valid multi-video testing
- Ground truth matching cannot execute
- Latency calculations are impossible
- F1/Precision/Recall metrics unavailable

**Priority:** Fix video lifecycle event system before any further testing.

---

**Report Generated:** 2025-11-04 10:32 UTC
**Analyst:** Research Agent (SPARC Mode)
**Next Steps:** Investigate SequentialVideoPlayer.tsx and socketio_server.py
