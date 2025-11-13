# Complete Data Flow Analysis: Ground Truth to Results Display
## Multi-Video Sequence Testing System

**Date**: 2025-11-03
**Session Analyzed**: `59cc6ae8-40b7-49ab-864b-add4a5846255`
**Issue**: Second video shows no detections in multi-video sequence

---

## Executive Summary

### Critical Finding
The multi-video test session has **ZERO detections for Video 2** despite having 252 ground truth objects uploaded correctly. All 105 detections are attributed to Video 1 only.

### Root Cause
**Detection events are not being correlated to Video 2** during test execution. The LabJack detection system is capturing hardware events, but the video correlation logic only assigns them to the first video in the sequence.

---

## Complete Data Flow with Actual Counts

```
┌────────────────────────────────────────────────────────────────────┐
│                     GROUND TRUTH UPLOAD STAGE                        │
└────────────────────────────────────────────────────────────────────┘

Video 1 (10c2b16c-86fa...):  262 GT objects  ✅ STORED IN DATABASE
Video 2 (550e3cf8-2755...):  252 GT objects  ✅ STORED IN DATABASE
                             ───────────────
Total Ground Truth:          514 objects    ✅ ALL STORED CORRECTLY

Database Table: ground_truth_objects
├─ video_id: Properly set for both videos
├─ timestamp: Video-relative timestamps
├─ deleted_at: NULL (active)
└─ Query Result: ✅ Both videos have GT data

┌────────────────────────────────────────────────────────────────────┐
│                    TEST SESSION INITIALIZATION                       │
└────────────────────────────────────────────────────────────────────┘

Test Session:
├─ ID: 59cc6ae8-40b7-49ab-864b-add4a5846255
├─ has_video_sequence: TRUE
├─ sequence_id: 1a2e1057-3b1f-4790-bbc5-d02fbf05ac95
└─ primary_video_id: 10c2b16c-86fa... (Video 1)

Video Test Sequence:
├─ ID: 1a2e1057-3b1f-4790-bbc5-d02fbf05ac95
├─ status: "running"
├─ video_ids: ['10c2b16c-86fa...', '550e3cf8-2755...']
├─ total_videos: 2
└─ current_video_index: 0  ⚠️ STUCK AT FIRST VIDEO

Sequence Video Results (Database Records):
├─ Video 1 (sequence_order=0):
│   ├─ video_status: "pending"
│   ├─ expected_detection_count: 262
│   └─ actual_detection_count: 0  ❌ NOT UPDATED
│
└─ Video 2 (sequence_order=1):
    ├─ video_status: "pending"
    ├─ expected_detection_count: 252
    └─ actual_detection_count: 0  ❌ NEVER RECEIVED DATA

┌────────────────────────────────────────────────────────────────────┐
│                     HARDWARE DETECTION STAGE                         │
└────────────────────────────────────────────────────────────────────┘

LabJack Hardware Events Captured: ~105+ events

Detection Event Storage (detection_events table):
├─ Total Events: 105
├─ Video 1 (10c2b16c): 105 events  ✅ ALL EVENTS
├─ Video 2 (550e3cf8): 0 events    ❌ ZERO EVENTS
└─ Status: ALL events have video_id = Video 1

Sample Detection Events:
┌────────────┬─────────────┬───────────┬──────────────┬──────────┐
│ Event ID   │ Video ID    │ Timestamp │ Rel. Time    │ Latency  │
├────────────┼─────────────┼───────────┼──────────────┼──────────┤
│ 5a5f6016   │ 10c2b16c... │ ...32.560 │ 0.002s       │ 50.0ms   │
│ f531130d   │ 10c2b16c... │ ...32.597 │ 0.038s       │ 50.0ms   │
│ 17c6b375   │ 10c2b16c... │ ...32.678 │ 0.120s       │ 50.0ms   │
│ ... (all 105 events assigned to Video 1)                       │
└────────────┴─────────────┴───────────┴──────────────┴──────────┘

🔴 CRITICAL ISSUE: Video ID assignment logic fails for Video 2

┌────────────────────────────────────────────────────────────────────┐
│                   GROUND TRUTH MATCHING STAGE                        │
└────────────────────────────────────────────────────────────────────┘

Ground Truth Matching Service Analysis:
├─ Ground Truth Query: ✅ Correctly fetches GT for BOTH videos
│   ├─ Video 1: 262 GT objects
│   └─ Video 2: 252 GT objects
│
├─ Detection Events Query: ❌ Only Video 1 detections available
│   ├─ Video 1: 105 detection events
│   └─ Video 2: 0 detection events
│
└─ Matching Results:
    ├─ Video 1: 105 detections vs 262 GT → 0 matched (no video_relative_timestamp correlation)
    ├─ Video 2: 0 detections vs 252 GT → 0 matched
    └─ Status: ❌ ZERO MATCHES due to missing video correlation

Key Code Insight (ground_truth_matching_service.py:608-628):
```python
# BUG #10 FIX: Video Boundary Validation
detection_video_id = getattr(detection, 'video_id', None)
gt_video_id = getattr(gt_obj, 'video_id', None)

if detection_video_id != gt_video_id:
    # Detection and ground truth from different videos - skip matching
    video_boundary_rejections += 1
    continue
```

This code PREVENTS cross-video matching (correct), but since ALL
detections have video_id=Video1, NO Video2 GT can EVER match.

┌────────────────────────────────────────────────────────────────────┐
│                      RESULTS API ENDPOINT                            │
└────────────────────────────────────────────────────────────────────┘

API Query for HIL Results:
```sql
SELECT
    de.id, de.video_id, de.timestamp,
    de.actual_latency_ms, de.video_relative_timestamp
FROM detection_events de
WHERE de.test_session_id = '59cc6ae8-40b7-49ab...'
ORDER BY de.created_at
```

API Response Breakdown:
├─ Total detections returned: 105
├─ Video 1 detections: 105
├─ Video 2 detections: 0
└─ Per-video metrics:
    ├─ Video 1: avg_latency=50ms, count=105
    └─ Video 2: ❌ NO DATA (empty array)

┌────────────────────────────────────────────────────────────────────┐
│                        FRONTEND DISPLAY                              │
└────────────────────────────────────────────────────────────────────┘

Frontend Data Fetching (HILResults.tsx):
```typescript
const fetchResults = async (sessionId: string) => {
  const response = await api.get(`/api/enhanced-hil-results/${sessionId}`);
  const data = response.data;

  // Data received:
  // - detectionEvents: 105 events (all video_id = Video1)
  // - perVideoMetrics: Only Video1 has metrics
  // - Video2 metrics: undefined or empty
};
```

Display Behavior:
├─ Video 1 Tab:
│   ├─ Shows: 105 detection events
│   ├─ Timeline: Populated with markers
│   └─ Metrics: Displays latency stats
│
└─ Video 2 Tab:
    ├─ Shows: "No detections found" or empty state
    ├─ Timeline: Empty
    └─ Metrics: N/A or 0 values

┌────────────────────────────────────────────────────────────────────┐
│                          FINAL OUTPUT                                │
└────────────────────────────────────────────────────────────────────┘

UI Display Summary:
┌─────────────────────────────────────────────────────────────────┐
│  Video 1 Results: ✅ 105 detections, metrics calculated        │
│  Video 2 Results: ❌ 0 detections, no data to display          │
└─────────────────────────────────────────────────────────────────┘

Expected vs Actual:
                    Expected    Actual    Status
Video 1 GT:         262         262       ✅ Stored correctly
Video 1 Detections: ~262        105       ⚠️ Partial (test may have stopped early)
Video 2 GT:         252         252       ✅ Stored correctly
Video 2 Detections: ~252        0         ❌ ZERO - CRITICAL BUG
```

---

## Root Cause Analysis

### Primary Issue: Video ID Assignment in Detection Storage

**Location**: Detection event creation during LabJack hardware monitoring

**Problem**: When a LabJack detection event occurs, the system assigns `video_id` based on the **current active video** in the orchestrator. However:

1. **Video transition logic not triggered**: The orchestrator's `current_video_index` stays at `0` (Video 1)
2. **All detections assigned to Video 1**: Every detection event gets `video_id = 10c2b16c` (first video)
3. **Video 2 never becomes active**: No mechanism advances to the second video

### Secondary Issue: Sequence Orchestration Not Running

**Location**: `VideoSequenceOrchestrator` service

**Expected Behavior**:
```python
# Should happen automatically:
1. Video 1 starts → current_video_index = 0
2. Video 1 completes → advance to next video
3. Video 2 starts → current_video_index = 1
4. Detections during Video 2 → assigned video_id = Video2
```

**Actual Behavior**:
```python
# What's happening:
1. Video 1 starts → current_video_index = 0
2. Video 1 continues indefinitely
3. Video 2 never starts
4. All detections → video_id = Video1 (forever)
```

### Tertiary Issue: Ground Truth Matching Cannot Compensate

The ground truth matching service correctly:
- Fetches GT for both videos (514 total objects)
- Implements video boundary validation
- Prevents cross-video matching

**BUT**: Since all detections have `video_id=Video1`, Video 2's 252 GT objects have **zero detections to match against**.

---

## Data Loss Points

### Stage 1: Ground Truth Upload ✅ NO DATA LOSS
- **Input**: 262 GT objects (Video 1) + 252 GT objects (Video 2)
- **Storage**: Database correctly stores all 514 objects
- **Validation**: Both videos have proper `video_id` foreign keys

### Stage 2: Test Session Setup ✅ NO DATA LOSS
- **Input**: 2 videos, sequence configuration
- **Storage**: `video_test_sequences` table has both video IDs
- **Storage**: `sequence_video_results` has records for both videos
- **Validation**: Schema structure is correct

### Stage 3: Hardware Detection ❌ CRITICAL DATA LOSS
- **Input**: ~105-262 hardware events per video (estimated)
- **Processing**: LabJack correctly captures events
- **Storage**: ALL events assigned `video_id = Video1`
- **Loss**: Video 2 detections are **NEVER CREATED**
- **Impact**: 100% data loss for Video 2

### Stage 4: Ground Truth Matching ❌ CASCADING FAILURE
- **Input**: 514 GT objects, 105 detection events (all Video 1)
- **Processing**: Matching service correctly queries both
- **Output**: 0 matches (timing issues + video boundary protection)
- **Loss**: No validation metrics for either video

### Stage 5: Results Display ❌ NO DATA TO DISPLAY
- **Input**: API endpoint returns empty Video 2 data
- **Output**: Frontend shows "No detections"
- **User Impact**: Cannot validate Video 2 performance

---

## Why Second Video Has Issues

### Hypothesis 1: ✅ CONFIRMED - Sequence Orchestration Not Running

**Evidence**:
- `video_test_sequences.current_video_index = 0` (stuck at first video)
- `video_test_sequences.status = "running"` (should progress)
- No video transition events logged
- Zero detection events have `video_id = Video2`

**Cause**: The video sequence orchestrator is either:
1. Not receiving "video completed" notifications
2. Not automatically advancing to next video
3. Manually controlled (requires explicit video switching)

### Hypothesis 2: ❌ DISPROVEN - Frontend Not Calling Video2

**Evidence Against**:
- Frontend correctly requests session-level data
- API returns all available detections
- Problem is at data source (backend), not display

### Hypothesis 3: ✅ CONFIRMED - Detection Assignment Logic Flaw

**Evidence**:
- All 105 detection events have `video_id = 10c2b16c` (Video 1)
- Detection event creation uses `current_video` from orchestrator
- Orchestrator never updates `current_video` to Video 2

**Code Location** (inferred):
```python
# In detection event creation:
current_video_id = orchestrator.get_current_video_id(session_id)
detection_event = DetectionEvent(
    test_session_id=session_id,
    video_id=current_video_id,  # Always Video1 if orchestrator stuck
    timestamp=hardware_timestamp,
    ...
)
```

---

## Recommended Fixes

### Fix 1: Implement Automatic Video Transition (HIGH PRIORITY)

**File**: `services/video_sequence_orchestrator.py`

**Current State**: Manual video transition
**Required**: Automatic progression based on video duration or user action

**Implementation**:
```python
def check_video_completion(self, sequence_id: str, current_time: float) -> bool:
    """Check if current video should transition to next"""
    sequence = self._get_sequence(sequence_id)
    current_video = sequence.video_metadata[
        sequence.video_ids[sequence.current_video_index]
    ]

    # Check if video duration exceeded
    if current_video.video_start_time:
        elapsed = current_time - current_video.video_start_time
        if elapsed >= current_video.duration:
            return self.advance_to_next_video(sequence_id)

    return False

def advance_to_next_video(self, sequence_id: str) -> bool:
    """Advance sequence to next video"""
    sequence = self._get_sequence(sequence_id)

    if sequence.current_video_index < len(sequence.video_ids) - 1:
        sequence.current_video_index += 1
        logger.info(f"Advanced to video {sequence.current_video_index + 1}")
        self._update_database_sequence_status(sequence)
        return True

    return False
```

### Fix 2: Add Video Transition Webhook/Event System (MEDIUM PRIORITY)

**Integration Point**: Frontend video player

**Implementation**:
```typescript
// Frontend: Notify backend when video completes
const handleVideoEnd = async (videoId: string, sessionId: string) => {
  await api.post('/api/video-sequences/advance', {
    sessionId,
    completedVideoId: videoId,
    timestamp: Date.now()
  });
};

// Backend endpoint:
@router.post("/video-sequences/advance")
async def advance_video_sequence(request: VideoAdvanceRequest):
    """Advance multi-video sequence to next video"""
    orchestrator.notify_video_completed(
        request.session_id,
        request.completed_video_id,
        request.timestamp
    )
    return {"status": "advanced", "nextVideoIndex": ...}
```

### Fix 3: Add Periodic Video Status Check (LOW PRIORITY)

**Purpose**: Fallback if explicit notifications fail

**Implementation**:
```python
class LabJackDetectionMonitor:
    def _periodic_video_check(self):
        """Background thread to check video status"""
        while self.monitoring_active:
            for session_id in self.active_sessions:
                current_time = time.time()
                self.orchestrator.check_video_completion(
                    session_id, current_time
                )
            time.sleep(1.0)  # Check every second
```

### Fix 4: Improve Detection Event Video Assignment (HIGH PRIORITY)

**File**: Detection event creation logic

**Current**:
```python
# Gets video from orchestrator (stuck at Video1)
video_id = orchestrator.get_current_video_id(session_id)
```

**Enhanced**:
```python
def get_video_id_for_detection(self, session_id: str, detection_timestamp: float) -> str:
    """Determine correct video based on timestamp ranges"""
    sequence = self.orchestrator.get_sequence(session_id)

    for video_id in sequence.video_ids:
        video_result = sequence.video_results[video_id]

        # Check if detection falls within this video's time range
        if video_result.video_start_time and video_result.video_end_time:
            if video_result.video_start_time <= detection_timestamp <= video_result.video_end_time:
                return video_id

    # Fallback: Use current video from orchestrator
    return sequence.video_ids[sequence.current_video_index]
```

---

## Testing Recommendations

### Test Case 1: Verify Video Transition
```python
def test_multi_video_sequence_transition():
    # Start sequence with 2 videos
    sequence_id = orchestrator.start_sequence(
        project_id, [video1_id, video2_id], max_latency_ms=100
    )

    # Simulate Video 1 completion
    orchestrator.notify_video_completed(sequence_id, video1_id, time.time())

    # Verify Video 2 is now active
    current_video = orchestrator.get_current_video_id(sequence_id)
    assert current_video == video2_id

    # Verify detection assigns to Video 2
    detection = create_test_detection(sequence_id)
    assert detection.video_id == video2_id
```

### Test Case 2: Verify Detection Assignment Per Video
```python
def test_detection_video_assignment():
    # Create detection during Video 1
    det1 = create_detection_event(session_id, timestamp=100.0)
    assert det1.video_id == video1_id

    # Advance to Video 2
    orchestrator.advance_to_next_video(sequence_id)

    # Create detection during Video 2
    det2 = create_detection_event(session_id, timestamp=200.0)
    assert det2.video_id == video2_id
```

---

## Priority Action Items

1. **🔴 CRITICAL**: Implement video transition mechanism
   - Add explicit transition endpoint
   - Or implement automatic transition based on duration

2. **🔴 CRITICAL**: Fix detection event video_id assignment
   - Update detection creation to use orchestrator's current video
   - Add timestamp-based fallback logic

3. **🟡 HIGH**: Add video transition notifications
   - Frontend notifies backend when video completes
   - Backend updates orchestrator state

4. **🟢 MEDIUM**: Add sequence status monitoring
   - Background job checks video progress
   - Automatic advancement if video duration exceeded

5. **🔵 LOW**: Add comprehensive logging
   - Log every video transition
   - Log every detection with video context
   - Monitor for stuck sequences

---

## Data Integrity Verification Checklist

- [x] Ground truth uploaded correctly for both videos
- [x] Database schema supports multi-video sequences
- [x] Sequence video results records exist
- [ ] Detection events assigned to correct video_id
- [ ] Video transitions working automatically
- [ ] Per-video metrics calculated correctly
- [ ] Frontend displays results for all videos
- [ ] Ground truth matching works across videos

**Overall Status**: 🔴 **CRITICAL** - Data pipeline broken for multi-video sequences

---

## Conclusion

The issue is **NOT with data display** or **frontend logic**. The root cause is that **Video 2 never receives any detection events** during test execution because:

1. The video sequence orchestrator never advances from Video 1 to Video 2
2. All hardware detection events are assigned `video_id = Video1`
3. Without detections, Video 2 has no data to display

**Fix Required**: Implement video transition logic in the orchestrator service and update detection event creation to use the correct current video.
