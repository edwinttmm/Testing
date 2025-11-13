# Comprehensive Data Flow Analysis
## Test Execution Through Approval to Results Display

**Document Version:** 1.0
**Date:** 2025-11-11
**System:** AI Model Validation Platform - HIL Test Execution Pipeline

---

## Executive Summary

This document provides a comprehensive analysis of the complete data flow journey from HIL test execution start through detection events, ground truth matching, validation, approval, metrics calculation, and final results display in the frontend. It maps the entire state machine, data transformations, timing synchronization, and WebSocket event flows across backend services and frontend components.

**Key Flow Stages:**
1. **Test Initialization** - Session creation with T0 timestamp capture
2. **Video Playback Start** - T1 timestamp capture and LabJack monitoring activation
3. **Real-Time Detection** - Hardware event capture with video correlation
4. **Video Completion** - Orchestrator synchronization and evaluation
5. **Session Completion** - Validation, approval, and metrics aggregation
6. **Results Retrieval** - API data fetching and frontend rendering
7. **Real-Time Updates** - WebSocket event broadcasting

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Phase 1: Test Initialization](#2-phase-1-test-initialization)
3. [Phase 2: Video Playback and Monitoring](#3-phase-2-video-playback-and-monitoring)
4. [Phase 3: Real-Time Detection Flow](#4-phase-3-real-time-detection-flow)
5. [Phase 4: Video Completion and Evaluation](#5-phase-4-video-completion-and-evaluation)
6. [Phase 5: Session Completion and Validation](#6-phase-5-session-completion-and-validation)
7. [Phase 6: Results Storage and Aggregation](#7-phase-6-results-storage-and-aggregation)
8. [Phase 7: Frontend Results Display](#8-phase-7-frontend-results-display)
9. [WebSocket Event Flow](#9-websocket-event-flow)
10. [Timing Synchronization Architecture](#10-timing-synchronization-architecture)
11. [State Machine Diagrams](#11-state-machine-diagrams)
12. [Data Transformation Pipeline](#12-data-transformation-pipeline)
13. [Critical Dependencies](#13-critical-dependencies)
14. [Error Handling and Recovery](#14-error-handling-and-recovery)

---

## 1. System Architecture Overview

### 1.1 High-Level Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                            │
├──────────────────────────────────────────────────────────────────┤
│  HILTestExecutionPRD.tsx  →  WebSocket Service  ←  API Service   │
│         ↓                           ↓                    ↓       │
│  SequentialVideoPlayer    HILResults.tsx      detectionService   │
└──────────────────────────────────────────────────────────────────┘
                            ↕ (HTTP + WebSocket)
┌──────────────────────────────────────────────────────────────────┐
│                      BACKEND API LAYER                           │
├──────────────────────────────────────────────────────────────────┤
│  hil_test_complete.py  ←→  socketio_server.py  ←→  test_sessions │
│         ↓                           ↓                    ↓       │
│  timing_orchestration    session_completion   video_sequences    │
└──────────────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER                                │
├──────────────────────────────────────────────────────────────────┤
│  VideoSequenceOrchestrator  ←→  LabJackDetectionMonitor         │
│           ↓                              ↓                       │
│  GroundTruthMatching        ←→  PrecisionTimingService          │
│           ↓                              ↓                       │
│  VideoTimingService         ←→  SessionCompletionService        │
└──────────────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────────────┐
│                     DATABASE LAYER                               │
├──────────────────────────────────────────────────────────────────┤
│  TestSession  ←→  VideoTestSequence  ←→  SequenceVideoResult    │
│       ↓                  ↓                        ↓              │
│  DetectionEvent  ←→  GroundTruthObject  ←→  TestResult          │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow Layers

| Layer | Components | Primary Function |
|-------|-----------|------------------|
| **Presentation** | React Components | UI rendering, user interaction |
| **Transport** | WebSocket + HTTP | Real-time events, API requests |
| **Application** | FastAPI Routers | Request handling, validation |
| **Business Logic** | Service Classes | Orchestration, timing, matching |
| **Data** | SQLAlchemy Models | Persistence, state management |
| **Hardware** | LabJack Service | Physical detection events |

---

## 2. Phase 1: Test Initialization

### 2.1 Flow Sequence

```
User: "Start Test" Button Click
    ↓
Frontend: HILTestExecutionPRD.tsx::handleStartTest()
    ↓
API Call: POST /api/v1/hil-test/session/start
    ↓
Backend: hil_test_complete.py::start_hil_test_session()
    ↓
Timing Orchestration: capture_t0_command_timestamp()
    ↓
Database: Create TestSession record
    ↓
Multi-Video Check: VideoSequenceOrchestrator.start_sequence()
    ↓
Database: Create VideoTestSequence + SequenceVideoResult[]
    ↓
Session Manager: Store in hil_manager.active_sessions
    ↓
Background Task: monitor_test_session() async loop
    ↓
WebSocket Broadcast: "session_started" event
    ↓
Frontend: Update UI with session ID and timing data
```

### 2.2 Critical Timestamp Capture (T0)

**File:** `backend/api/hil_test_complete.py` (Lines 278-283)

```python
# CRITICAL: Capture T0 timestamp IMMEDIATELY when test start command received
t0_capture = timing_orchestration_service.capture_t0_command_timestamp(
    session_id=str(session_data.project_id),  # Temporary ID
    db=None,  # Will store after session creation
    metadata={"command": "start_hil_test", "project_id": session_data.project_id}
)
```

**T0 Data Structure:**
```python
@dataclass
class T0CommandTimestamp:
    command_timestamp: float        # Unix timestamp (seconds.microseconds)
    precision_ns: int              # Nanosecond precision
    capture_latency_ns: int        # Time to capture timestamp
    system_time_utc: datetime      # UTC datetime
    capture_source: str            # "python_time_perf_counter"
```

### 2.3 Multi-Video Sequence Initialization

**File:** `backend/api/hil_test_complete.py` (Lines 303-400)

**Decision Logic:**
```python
project_videos = get_project_videos(db, session_data.project_id)
has_video_sequence = len(project_videos) > 1

if has_video_sequence:
    orchestrator = VideoSequenceOrchestrator()
    sequence_id = orchestrator.start_sequence(
        project_id=session_data.project_id,
        video_ids=video_ids,
        max_latency_ms=session_data.max_latency_ms,
        db=db,
        session_id=str(test_session.id)
    )
```

**Database Records Created:**
1. **TestSession** - Main session record with T0 timestamp
2. **VideoTestSequence** - Sequence container with metadata
3. **SequenceVideoResult[]** - One record per video (status: "pending")

**Sequence Metadata Structure:**
```json
{
  "video_ids": ["video_1", "video_2", "video_3"],
  "sequence_order": [
    {"video_id": "video_1", "order": 0, "duration_ms": 30000},
    {"video_id": "video_2", "order": 1, "duration_ms": 45000},
    {"video_id": "video_3", "order": 2, "duration_ms": 60000}
  ],
  "max_latency_ms": 100,
  "video_names": {
    "video_1": "pedestrian_crossing.mp4",
    "video_2": "cyclist_approach.mp4",
    "video_3": "motorcycle_lane_change.mp4"
  },
  "video_timing": {},  // Populated during video playback
  "labjack_enabled": true
}
```

### 2.4 WebSocket Event: session_started

**Broadcast Data:**
```javascript
{
  "type": "session_started",
  "session_id": 12345,
  "project_id": 67,
  "start_time": "2025-11-11T14:30:00.123456Z",
  "t0_timestamp": 1699714200.123456,
  "timing_precision_ns": 150,
  "timing_quality": "high"  // or "medium" if precision > 1ms
}
```

**Frontend Handler:**
```typescript
// frontend/src/services/websocketService.ts
socket.on('session_started', (data) => {
  setSessionId(data.session_id);
  setTimingQuality(data.timing_quality);
  setSessionStartTime(data.start_time);
});
```

---

## 3. Phase 2: Video Playback and Monitoring

### 3.1 Video Start Flow

```
Frontend: SequentialVideoPlayer.tsx::handleVideoPlay()
    ↓
Extract: video_id, duration, fps, metadata
    ↓
API Call: POST /api/v1/hil-test/session/{id}/video/start
    ↓
Backend: hil_test_complete.py::start_video_playback()
    ↓
Hardware Validation: validate_hil_video_playback()
    ↓
Duration Resolution: get_video_duration() with fallback
    ↓
Timing Capture: capture_t1_video_start_timestamp()
    ↓
Active Session Update: active_session["active_video_id"] = video_id
    ↓
Orchestrator Notification: orchestrator.notify_video_started()
    ↓
Database Update: SequenceVideoResult (video_start_time, status="playing")
    ↓
Sequence Metadata Update: video_timing[video_id] = {...}
    ↓
LabJack Monitoring: ALREADY RUNNING (started at session creation)
    ↓
WebSocket Broadcast: "video_started" event
    ↓
Frontend: Update current video display
```

### 3.2 T1 Timestamp Capture

**File:** `backend/api/hil_test_complete.py` (Lines 578-583)

```python
# CRITICAL: Capture T1 timestamp when video actually starts playing
t1_capture = timing_orchestration_service.capture_t1_video_start_timestamp(
    session_id=str(session_id),
    video_id=video_id,
    db=db,
    video_metadata=video_metadata
)
```

**T1 Data Structure:**
```python
@dataclass
class T1VideoStartTimestamp:
    video_start_timestamp: float   # Unix timestamp
    video_id: str
    precision_ns: int
    capture_source: str            # "frontend_video_onPlay_event"
    metadata: Dict[str, Any]       # fps, duration, resolution
```

### 3.3 Video Duration Resolution (Critical for Auto-Stop)

**File:** `backend/api/hil_test_complete.py` (Lines 75-128)

**Resolution Priority:**
1. **Payload Data** - `video_data.get("duration_s")` or `video_data.get("duration")`
2. **Database Fallback** - `db.query(Video).filter(Video.id == video_id).first().duration`
3. **Validation** - Must be between 0.1s and 7200s (2 hours)

**Why Critical:**
- LabJack monitoring uses duration for automatic stop after video ends
- Without duration, monitoring continues indefinitely (resource leak)
- Prevents detection events after video completion

### 3.4 Per-Video Timing Storage

**File:** `backend/api/hil_test_complete.py` (Lines 613-694)

**Cumulative Offset Calculation (CRITICAL FIX):**
```python
# BUG FIX #6: Calculate cumulative offset from actual video start times
if len(previous_videos) > 0:
    sequence_start_time = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.sequence_order == 0
    ).first().video_start_time

    if sequence_start_time and t1_capture.video_start_timestamp:
        cumulative_offset_ms = (t1_capture.video_start_timestamp - sequence_start_time) * 1000
```

**Database Update:**
```python
sequence_video_result.video_start_time = t1_capture.video_start_timestamp
sequence_video_result.video_start_time_ns = str(int(t1_capture.video_start_timestamp * 1_000_000_000))
sequence_video_result.video_play_offset_ms = cumulative_offset_ms
sequence_video_result.video_status = "playing"
```

### 3.5 Sequence Metadata Update (BUG FIX #7)

**File:** `backend/api/hil_test_complete.py` (Lines 664-690)

**Critical for LabJack Detection Assignment:**
```python
# BUG FIX #7: Update sequence_metadata with video timing
# The LabJack monitor uses this metadata to determine which video a detection belongs to
current_metadata['video_timing'][video_id] = {
    'started_at': t1_capture.video_start_timestamp,
    'start_time': t1_capture.video_start_timestamp,
    'video_id': video_id,
    'video_play_offset_ms': cumulative_offset_ms
}

test_session.sequence_metadata = current_metadata
db.commit()
```

**Why This Matters:**
- LabJackDetectionMonitor reads `session.sequence_metadata.video_timing`
- Uses timestamp ranges to assign detections to correct video
- Without this update, all detections assigned to video_id=NULL

### 3.6 WebSocket Event: video_started

**Broadcast Data:**
```javascript
{
  "type": "video_started",
  "session_id": 12345,
  "video_id": "video_2",
  "t1_timestamp": 1699714230.456789,
  "timing_precision_ns": 200,
  "timing_quality": "high",
  "presentation_delay_ms": 45.3,  // T1 - T0 delay
  "delay_quality": "acceptable",
  "t0_timestamp": 1699714200.123456
}
```

---

## 4. Phase 3: Real-Time Detection Flow

### 4.1 Hardware Detection Pipeline

```
Hardware: LabJack voltage threshold crossed (e.g., AIN0 > 2.5V)
    ↓
LabJack Service: voltage_reading captured with timestamp
    ↓
Detection Monitor: _monitoring_loop() detects threshold crossing
    ↓
Debounce Check: Ensure > 100ms since last detection on this channel
    ↓
Create DetectionEvent: With precise timestamp
    ↓
Video Assignment: get_video_id_for_detection(session_id, detection_timestamp)
    ↓
Timing Sync: Calculate video_relative_timestamp
    ↓
Database Insert: DetectionEvent record
    ↓
Ground Truth Matching: match_detections_to_ground_truth()
    ↓
WebSocket Broadcast: "detection_event" to frontend
    ↓
Frontend: Real-time UI update (timeline, table, metrics)
```

### 4.2 Video ID Assignment Logic

**File:** `backend/services/video_id_resolver.py`

**Algorithm:**
```python
def get_video_id_for_detection(session_id: str, detection_timestamp: float, db: Session) -> Optional[str]:
    """
    Resolve which video a detection belongs to based on timestamp.

    Uses sequence_metadata.video_timing to find the video that was
    playing at the time of the detection.
    """
    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if not session or not session.sequence_metadata:
        return None

    video_timing = session.sequence_metadata.get('video_timing', {})

    for video_id, timing in video_timing.items():
        start_time = timing.get('started_at') or timing.get('start_time')
        end_time = timing.get('ended_at') or timing.get('end_time')

        if not start_time:
            continue  # Video not started yet

        if end_time:
            # Video completed - check if detection in range
            if start_time <= detection_timestamp <= end_time:
                return video_id
        else:
            # Video still playing - check if detection after start
            if detection_timestamp >= start_time:
                return video_id  # Assume this is the current video

    return None  # No matching video found
```

### 4.3 Detection Event Structure

**Database Model:**
```python
class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id = Column(String, primary_key=True)
    test_session_id = Column(String, ForeignKey("test_sessions.id"))
    video_id = Column(String, ForeignKey("videos.id"))  # Assigned via resolver

    # Hardware timing
    detection_timestamp = Column(Float)  # Unix timestamp from LabJack
    voltage = Column(Float)
    channel = Column(String)

    # Video correlation
    video_relative_timestamp = Column(Float)  # Seconds from video start
    frame_number = Column(Integer)  # Calculated from fps
    video_play_offset_ms = Column(Float)  # For multi-video sequences

    # Ground truth matching
    ground_truth_match_id = Column(String, ForeignKey("ground_truth_objects.id"))
    match_status = Column(String)  # "matched", "unmatched", "pending"
    match_distance_ms = Column(Float)  # Distance to matched GT object

    # Validation results
    actual_latency_ms = Column(Float)  # Measured presentation latency
    validation_result = Column(String)  # "PASS", "FAIL", "PENDING"

    # Metadata
    metadata = Column(JSON)
```

### 4.4 Timing Synchronization

**Video-Relative Timestamp Calculation:**
```python
# File: backend/services/timestamp_conversion_utils.py

def calculate_video_relative_timestamp(
    detection_timestamp: float,
    video_start_time: float,
    video_play_offset_ms: float
) -> float:
    """
    Convert hardware detection timestamp to video-relative time.

    Args:
        detection_timestamp: Unix timestamp from LabJack
        video_start_time: T1 timestamp when video started
        video_play_offset_ms: Cumulative offset in multi-video sequence

    Returns:
        Seconds from video start (0-based)
    """
    # Calculate time since video started
    time_since_video_start = detection_timestamp - video_start_time

    # For multi-video sequences, this gives position within current video
    # video_play_offset_ms is NOT subtracted - it's for sequence-level positioning

    return max(0.0, time_since_video_start)
```

### 4.5 Ground Truth Matching

**File:** `backend/services/ground_truth_matching_service.py`

**Matching Algorithm:**
```python
def match_detection_to_ground_truth(
    detection: DetectionEvent,
    ground_truth_objects: List[GroundTruthObject],
    tolerance_ms: float = 100.0
) -> Optional[str]:
    """
    Match detection to ground truth object within tolerance window.

    Matching Rules:
    1. Detection must occur within ±tolerance_ms of GT timestamp
    2. If multiple GTs in window, choose closest
    3. Each GT can only match one detection (first come, first served)
    """
    detection_time_ms = detection.video_relative_timestamp * 1000

    best_match = None
    min_distance = float('inf')

    for gt_obj in ground_truth_objects:
        if gt_obj.matched:
            continue  # GT already matched to another detection

        gt_time_ms = gt_obj.timestamp * 1000
        distance_ms = abs(detection_time_ms - gt_time_ms)

        if distance_ms <= tolerance_ms and distance_ms < min_distance:
            best_match = gt_obj
            min_distance = distance_ms

    if best_match:
        best_match.matched = True
        detection.ground_truth_match_id = best_match.id
        detection.match_status = "matched"
        detection.match_distance_ms = min_distance
        return best_match.id

    detection.match_status = "unmatched"
    return None
```

### 4.6 WebSocket Event: detection_event

**Broadcast Data:**
```javascript
{
  "type": "detection_event",
  "session_id": 12345,
  "video_id": "video_2",
  "detection": {
    "id": "det_abc123",
    "detection_timestamp": 1699714235.789012,
    "video_relative_timestamp": 5.33,
    "frame_number": 160,
    "channel": "AIN0",
    "voltage": 3.2,
    "ground_truth_match_id": "gt_xyz789",
    "match_status": "matched",
    "match_distance_ms": 15.5,
    "actual_latency_ms": 45.8,
    "validation_result": "PASS"
  },
  "metrics_update": {
    "total_detections": 12,
    "matched_detections": 10,
    "unmatched_detections": 2,
    "average_latency_ms": 47.3
  }
}
```

**Frontend Real-Time Update:**
```typescript
// frontend/src/pages/HILResults.tsx
socket.on('detection_event', (data) => {
  // Add to detection table
  setDetections(prev => [...prev, data.detection]);

  // Update metrics cards
  setMetrics(data.metrics_update);

  // Update timeline visualization
  timelineRef.current?.addDetection(data.detection);

  // Play notification sound if enabled
  if (audioEnabled) {
    playDetectionSound(data.detection.validation_result);
  }
});
```

---

## 5. Phase 4: Video Completion and Evaluation

### 5.1 Video End Flow

```
Frontend: SequentialVideoPlayer.tsx::onVideoEnded()
    ↓
Extract: video_id, video_end_time
    ↓
API Call: POST /api/v1/hil-test/session/{id}/video/end
    ↓
Backend: hil_test_complete.py::end_video_playback()
    ↓
Idempotency Check: Already completed? Return early
    ↓
Database Update: SequenceVideoResult (video_end_time, status="completed")
    ↓
Duration Calculation: actual_duration_ms = end_time - start_time
    ↓
Sequence Metadata Update: video_timing[video_id]['ended_at'] = end_time
    ↓
Database Commit: Persist changes
    ↓
Orchestrator Sync: orchestrator.notify_video_ended()
    ↓
Orchestrator Evaluation: Trigger next video or complete sequence
    ↓
WebSocket Broadcast: "video_completed" event
    ↓
Frontend: Update UI, advance to next video or show completion
```

### 5.2 Idempotency Protection

**File:** `backend/api/hil_test_complete.py` (Lines 799-808)

```python
# IDEMPOTENCY CHECK: Return early if video already marked as completed
if (sequence_video_result.video_status == "completed" and
    sequence_video_result.video_end_time is not None):
    logger.info(f"Video {video_id} already marked as completed (idempotency check)")
    return {
        "success": True,
        "video_id": video_id,
        "video_end_time": sequence_video_result.video_end_time,
        "actual_duration_ms": sequence_video_result.actual_duration_ms,
        "message": "Video already completed"
    }
```

**Why Critical:**
- Frontend may call `/video/end` multiple times (race conditions)
- Double-processing corrupts orchestrator state
- Prevents duplicate "video_completed" events

### 5.3 Orchestrator Synchronization

**File:** `backend/services/video_sequence_orchestrator.py`

**notify_video_ended() Logic:**
```python
def notify_video_ended(
    self,
    sequence_id: str,
    video_id: str,
    actual_end_timestamp: float,
    db: Session
) -> bool:
    """
    Notify orchestrator that video playback ended.

    Actions:
    1. Update video status to "completed"
    2. Calculate actual duration
    3. Evaluate video completion criteria
    4. Decide next action (next video or complete sequence)
    5. Update sequence progress
    """
    sequence = self._active_sequences.get(sequence_id)
    if not sequence:
        return False

    # Find video in sequence
    video_info = next((v for v in sequence.videos if v.video_id == video_id), None)
    if not video_info:
        return False

    # Update video state
    video_info.status = "completed"
    video_info.actual_end_timestamp = actual_end_timestamp
    video_info.actual_duration_s = actual_end_timestamp - video_info.actual_start_timestamp

    # Evaluate completion
    completion_result = self._evaluate_video_completion(sequence_id, video_id, db)

    # Decide next action
    if completion_result.should_advance:
        next_video_id = self._get_next_video_id(sequence_id)
        if next_video_id:
            # Trigger next video
            self._trigger_next_video(sequence_id, next_video_id, db)
        else:
            # All videos complete - finalize sequence
            self._finalize_sequence(sequence_id, db)

    return True
```

### 5.4 Sequence Completion Check

**File:** `backend/api/hil_test_complete.py` (Lines 934-960)

```python
# Check if entire sequence is complete
video_sequence = db.query(VideoTestSequence).filter(
    VideoTestSequence.id == sequence_video_result.video_sequence_id
).first()

if video_sequence:
    completed_count = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.video_sequence_id == video_sequence.id,
        SequenceVideoResult.video_status == "completed"
    ).count()

    if completed_count >= video_sequence.total_videos:
        sequence_complete = True
        video_sequence.status = "completed"
        db.commit()

        # Broadcast sequence completion
        await hil_manager.broadcast_status({
            "type": "sequence_completed",
            "session_id": session_id,
            "video_sequence_id": video_sequence.id,
            "total_videos": video_sequence.total_videos,
            "completed_at": datetime.now(timezone.utc).isoformat()
        })
```

### 5.5 WebSocket Events

**Individual Video Completion:**
```javascript
{
  "type": "video_completed",
  "session_id": 12345,
  "video_id": "video_2",
  "video_end_time": 1699714275.456789,
  "actual_duration_ms": 45123,
  "sequence_complete": false,
  "orchestrator_synced": true
}
```

**Sequence Completion:**
```javascript
{
  "type": "sequence_completed",
  "session_id": 12345,
  "video_sequence_id": "seq_xyz789",
  "total_videos": 3,
  "completed_at": "2025-11-11T14:35:15.123456Z"
}
```

---

## 6. Phase 5: Session Completion and Validation

### 6.1 Completion Flow

```
User/System: Trigger session completion
    ↓
API Call: POST /api/v1/hil-test/session/{id}/complete
    ↓
Backend: hil_test_complete.py::complete_test_session()
    ↓
Validation: validate_video_sequence_completion()
    ↓
Detection Count Update: update_sequence_video_detection_counts()
    ↓
LabJack Stop: stop_labjack_monitoring()
    ↓
Video ID Reassignment: reassign_null_video_ids()
    ↓
Session Status Update: status = "completed", completed_at = now()
    ↓
Results Generation: test_execution_service.get_session_results()
    ↓
Ground Truth Matching: matching_service.match_detections_to_ground_truth()
    ↓
Metrics Calculation: Calculate TP/FP/FN, precision, recall, F1
    ↓
Database Commit: Persist all updates
    ↓
TS Compute Trigger: Optional external latency computation
    ↓
WebSocket Broadcast: "session_completed" event
    ↓
Frontend: Navigate to results page
```

### 6.2 Video Sequence Validation

**File:** `backend/services/session_completion_service.py` (Lines 21-169)

**Validation Rules:**
```python
def validate_video_sequence_completion(db: Session, session_id: str) -> tuple[bool, str]:
    """
    Validate that video sequence has proper timing data before completion.

    Prevents sessions from completing when video lifecycle events (start/end)
    never fired, which would leave NULL timestamps in the database.

    Validation Rules:
    1. Non-sequence sessions always pass (no validation needed)
    2. Sequence sessions must have sequence_metadata with video_timing
    3. Each video in sequence must have:
       - started_at timestamp (not NULL)
       - ended_at timestamp (not NULL)
    4. Videos with status "pending" are not allowed at completion time

    Returns:
        (is_valid, error_message)
    """
    session = db.query(TestSession).filter(TestSession.id == session_id).first()

    if not session.has_video_sequence:
        return (True, "")  # Non-sequence, no validation needed

    # Check sequence_metadata exists
    if not session.sequence_metadata:
        return (False, "Video sequence session missing sequence_metadata")

    # Check video_timing exists
    metadata = session.sequence_metadata
    if 'video_timing' not in metadata:
        return (False, "Missing video_timing in sequence_metadata")

    video_timing = metadata['video_timing']

    # Validate each video has start and end times
    missing_start_times = []
    missing_end_times = []

    for video_id, timing in video_timing.items():
        started_at = timing.get('started_at') or timing.get('start_time')
        ended_at = timing.get('ended_at') or timing.get('end_time')

        if started_at is None:
            missing_start_times.append(video_id)
        if ended_at is None:
            missing_end_times.append(video_id)

    if missing_start_times or missing_end_times:
        return (False, f"Videos missing timing data: {missing_start_times + missing_end_times}")

    # Check for pending videos
    pending_videos = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.video_sequence_id == video_sequence.id,
        SequenceVideoResult.video_status == "pending"
    ).all()

    if pending_videos:
        return (False, f"Videos still in 'pending' status: {[v.video_id for v in pending_videos]}")

    return (True, "")  # All validations passed
```

**Validation Failure Response:**
```python
if not is_valid:
    raise HTTPException(
        status_code=400,
        detail={
            "error": "Session completion validation failed",
            "message": error_message,
            "session_id": session_id,
            "validation_type": "video_sequence_timing"
        }
    )
```

### 6.3 Detection Count Update

**File:** `backend/api/hil_test_complete.py` (Lines 1134-1248)

**Efficient Query Pattern:**
```python
# EFFICIENT QUERY: Get detection counts grouped by video_id in single query
detection_counts = db.query(
    DetectionEvent.video_id,
    func.count(DetectionEvent.id).label('count')
).filter(
    DetectionEvent.test_session_id == str(session_id),
    DetectionEvent.video_id.isnot(None)
).group_by(
    DetectionEvent.video_id
).all()

# Convert to dictionary for fast lookup
count_map = {video_id: count for video_id, count in detection_counts}

# Update SequenceVideoResult records
for result in sequence_video_results:
    actual_count = count_map.get(result.video_id, 0)
    result.actual_detection_count = actual_count
```

**Why Single Query:**
- Prevents N+1 query problem (N videos = N queries)
- Database does aggregation (faster than Python loops)
- Single transaction commit

### 6.4 NULL Video ID Reassignment

**File:** `backend/services/detection_video_reassignment.py`

**Race Condition Fix:**
```python
async def reassign_null_video_ids(session_id: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    CRITICAL FIX: Reassign NULL video_ids before marking session complete.

    This fixes race condition where detections arrive before video lifecycle events.

    Algorithm:
    1. Find all detections with video_id = NULL
    2. For each detection, resolve video_id using timestamp
    3. Update detection record with correct video_id
    4. Calculate video-relative timestamp
    """
    null_detections = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id,
        DetectionEvent.video_id.is_(None)
    ).all()

    reassigned_count = 0

    for detection in null_detections:
        # Resolve video_id from timestamp
        video_id = get_video_id_for_detection(
            session_id,
            detection.detection_timestamp,
            db
        )

        if video_id:
            if not dry_run:
                detection.video_id = video_id
                detection.video_relative_timestamp = calculate_video_relative_timestamp(
                    detection.detection_timestamp,
                    video_start_time,
                    video_play_offset_ms
                )
            reassigned_count += 1

    if not dry_run:
        db.commit()

    return {
        "success": True,
        "reassigned_count": reassigned_count
    }
```

### 6.5 Ground Truth Matching Execution

**File:** `backend/services/ground_truth_matching_service.py`

**Session-Level Matching:**
```python
def match_detections_to_ground_truth(self, session_id: str) -> Dict[str, Any]:
    """
    Match all detections in session to ground truth objects.

    Process:
    1. Load all detections for session
    2. Load all ground truth objects for session videos
    3. Group by video_id
    4. For each video, match detections to GT within tolerance
    5. Calculate metrics: TP, FP, FN, precision, recall, F1
    6. Store matching results in database
    """
    db = SessionLocal()

    # Load detections
    detections = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id
    ).all()

    # Group by video_id
    detections_by_video = {}
    for det in detections:
        if det.video_id not in detections_by_video:
            detections_by_video[det.video_id] = []
        detections_by_video[det.video_id].append(det)

    # Match each video
    total_matched = 0
    total_unmatched = 0

    for video_id, video_detections in detections_by_video.items():
        # Load GT objects for this video
        gt_objects = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == video_id
        ).all()

        # Match detections
        matched_count, unmatched_count = self._match_video_detections(
            video_detections,
            gt_objects,
            tolerance_ms=100
        )

        total_matched += matched_count
        total_unmatched += unmatched_count

    db.commit()

    return {
        "matched_count": total_matched,
        "unmatched_count": total_unmatched
    }
```

### 6.6 Metrics Calculation

**Per-Video Metrics:**
```python
class VideoMetrics:
    true_positives: int      # Detections matched to GT
    false_positives: int     # Detections NOT matched to GT
    false_negatives: int     # GT objects NOT matched to detection
    total_ground_truth: int  # Total GT objects for this video

    precision: float = (TP / (TP + FP)) * 100 if (TP + FP) > 0 else 0
    recall: float = (TP / (TP + FN)) * 100 if (TP + FN) > 0 else 0
    f1_score: float = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
```

**Session-Level Aggregation:**
```python
def aggregate_session_metrics(video_metrics: List[VideoMetrics]) -> SessionMetrics:
    """
    Aggregate per-video metrics to session level.

    Aggregation Method:
    - Sum all TP, FP, FN across videos
    - Recalculate precision, recall, F1 from totals
    """
    total_tp = sum(m.true_positives for m in video_metrics)
    total_fp = sum(m.false_positives for m in video_metrics)
    total_fn = sum(m.false_negatives for m in video_metrics)
    total_gt = sum(m.total_ground_truth for m in video_metrics)

    session_precision = (total_tp / (total_tp + total_fp)) * 100 if (total_tp + total_fp) > 0 else 0
    session_recall = (total_tp / (total_tp + total_fn)) * 100 if (total_tp + total_fn) > 0 else 0
    session_f1 = (2 * session_precision * session_recall) / (session_precision + session_recall) if (session_precision + session_recall) > 0 else 0

    return SessionMetrics(
        true_positives=total_tp,
        false_positives=total_fp,
        false_negatives=total_fn,
        total_ground_truth=total_gt,
        precision=session_precision,
        recall=session_recall,
        f1_score=session_f1,
        total_videos=len(video_metrics)
    )
```

---

## 7. Phase 6: Results Storage and Aggregation

### 7.1 Database Schema

**TestSession (Main Record):**
```sql
CREATE TABLE test_sessions (
    id VARCHAR PRIMARY KEY,
    project_id VARCHAR,
    status VARCHAR,  -- "pending", "running", "completed", "failed"

    -- Timing data
    test_start_time TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    command_start_timestamp FLOAT,  -- T0 timestamp
    presentation_delay_ms FLOAT,     -- T1 - T0 delay

    -- Multi-video sequence
    has_video_sequence BOOLEAN,
    sequence_id VARCHAR,
    sequence_metadata JSON,

    -- Aggregated metrics
    total_events INTEGER,
    passed_events INTEGER,
    failed_events INTEGER,
    average_latency_ms FLOAT,

    -- Hardware
    labjack_connected BOOLEAN,
    max_latency_threshold_ms FLOAT,

    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**VideoTestSequence:**
```sql
CREATE TABLE video_test_sequences (
    id VARCHAR PRIMARY KEY,
    test_session_id VARCHAR REFERENCES test_sessions(id),

    name VARCHAR,
    video_ids JSON,           -- ["video_1", "video_2", "video_3"]
    sequence_order JSON,      -- [{video_id, order, duration_ms}, ...]

    -- Progress tracking
    status VARCHAR,           -- "pending", "in_progress", "completed"
    current_video_index INTEGER,
    total_videos INTEGER,
    completed_videos INTEGER,

    -- Timing
    sequence_start_time TIMESTAMP,
    sequence_end_time TIMESTAMP,
    max_latency_ms FLOAT,

    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**SequenceVideoResult:**
```sql
CREATE TABLE sequence_video_results (
    id VARCHAR PRIMARY KEY,
    video_id VARCHAR REFERENCES videos(id),
    video_sequence_id VARCHAR REFERENCES video_test_sequences(id),

    -- Sequence position
    sequence_order INTEGER,
    video_status VARCHAR,  -- "pending", "playing", "completed"

    -- Timing data
    video_start_time FLOAT,        -- T1 timestamp
    video_start_time_ns VARCHAR,   -- Nanosecond precision
    video_end_time FLOAT,
    video_play_offset_ms FLOAT,    -- Cumulative offset in sequence
    actual_duration_ms FLOAT,

    -- Detection counts
    expected_detection_count INTEGER,  -- From ground truth
    actual_detection_count INTEGER,    -- From detections

    -- Metrics (per video)
    ground_truth_comparison JSON,  -- {tp, fp, fn, precision, recall, f1}

    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**DetectionEvent:**
```sql
CREATE TABLE detection_events (
    id VARCHAR PRIMARY KEY,
    test_session_id VARCHAR REFERENCES test_sessions(id),
    video_id VARCHAR REFERENCES videos(id),

    -- Hardware timing
    detection_timestamp FLOAT,     -- Unix timestamp from LabJack
    voltage FLOAT,
    channel VARCHAR,

    -- Video correlation
    video_relative_timestamp FLOAT,  -- Seconds from video start
    frame_number INTEGER,
    video_play_offset_ms FLOAT,

    -- Ground truth matching
    ground_truth_match_id VARCHAR REFERENCES ground_truth_objects(id),
    match_status VARCHAR,           -- "matched", "unmatched", "pending"
    match_distance_ms FLOAT,

    -- Validation
    actual_latency_ms FLOAT,
    validation_result VARCHAR,      -- "PASS", "FAIL", "PENDING"

    metadata JSON,
    created_at TIMESTAMP
);
```

### 7.2 Results Aggregation

**API Endpoint:** `GET /api/test-sessions/{session_id}/enhanced-results`

**File:** `backend/src/api/enhanced_hil_results_endpoints.py`

**Response Structure:**
```python
class EnhancedHILResults(BaseModel):
    # Session metadata
    session_id: str
    project_id: str
    status: str

    # Overall metrics
    total_detections: int
    matched_detections: int
    unmatched_detections: int
    average_latency_ms: float
    pass_rate: float

    # Ground truth comparison (session-level)
    ground_truth_comparison: GroundTruthMetrics

    # Multi-video sequence data
    has_video_sequence: bool
    per_video_results: List[PerVideoResult]

    # Detection events (all videos)
    detection_events: List[EnhancedDetectionEvent]

    # Timing information
    timing_data: TimingData

    # Validation
    validation_status: str
```

**PerVideoResult Structure:**
```python
class PerVideoResult(BaseModel):
    video_id: str
    video_name: str
    video_url: str

    # Video timing
    video_start_time: float
    video_end_time: float
    actual_duration_ms: float
    video_play_offset_ms: float

    # Detection counts
    detection_count: int
    expected_detection_count: int

    # Ground truth metrics (per video)
    ground_truth_comparison: GroundTruthMetrics

    # Detection events (for this video only)
    detection_events: List[EnhancedDetectionEvent]

    # Status
    video_status: str
```

**Query Optimization:**
```python
# Efficient query to load all data in minimal queries
session = db.query(TestSession).filter(TestSession.id == session_id).first()

# Load video sequence if exists
video_sequence = db.query(VideoTestSequence).filter(
    VideoTestSequence.test_session_id == session_id
).first()

# Load all sequence video results in one query
sequence_video_results = db.query(SequenceVideoResult).filter(
    SequenceVideoResult.video_sequence_id == video_sequence.id
).all() if video_sequence else []

# Load all detection events in one query
detection_events = db.query(DetectionEvent).filter(
    DetectionEvent.test_session_id == session_id
).options(
    joinedload(DetectionEvent.ground_truth_match)  # Eager load GT matches
).all()

# Group detections by video_id
detections_by_video = {}
for det in detection_events:
    if det.video_id not in detections_by_video:
        detections_by_video[det.video_id] = []
    detections_by_video[det.video_id].append(det)
```

---

## 8. Phase 7: Frontend Results Display

### 8.1 Page Load Flow

```
User: Navigate to /hil-results/{sessionId}
    ↓
React Router: Load HILResults.tsx component
    ↓
useEffect: Trigger data loading
    ↓
API Call: GET /api/test-sessions/{sessionId}/enhanced-results
    ↓
Backend: Aggregate and return results
    ↓
Frontend: Receive EnhancedHILResults object
    ↓
Data Normalization: normalizeSequenceResults()
    ↓
State Updates: setEnhancedResults(), setPerVideoSummaries(), etc.
    ↓
Component Render: Display metrics, timeline, table
    ↓
WebSocket Connect: Subscribe to session updates
```

### 8.2 Data Normalization

**File:** `frontend/src/utils/hilResultsNormalization.ts`

**Purpose:** Convert backend snake_case to frontend camelCase and handle nested structures

**Key Functions:**
```typescript
export function normalizeSequenceResults(raw: any): VideoSequenceResults {
  return {
    hasVideoSequence: raw.has_video_sequence ?? false,
    perVideoResults: (raw.per_video_results || raw.perVideoResults || []).map(
      normalizePerVideoResult
    ),
    totalDetections: toNumber(raw.total_detections),
    matchedDetections: toNumber(raw.matched_detections),
    averageLatencyMs: toNumber(raw.average_latency_ms),
    passRate: toNumber(raw.pass_rate)
  };
}

export function normalizeDetectionEvent(raw: any): EnhancedDetectionEvent {
  return {
    id: raw.id || `det-${Date.now()}`,
    videoId: raw.video_id || raw.videoId,
    detectionTimestamp: toNumber(raw.detection_timestamp),
    videoRelativeTimestamp: toNumber(raw.video_relative_timestamp),
    frameNumber: toNumber(raw.frame_number),
    voltage: toNumber(raw.voltage),
    channel: raw.channel,

    // Ground truth matching
    groundTruthMatchId: raw.ground_truth_match_id || raw.groundTruthMatchId,
    matchStatus: raw.match_status || raw.matchStatus || 'unmatched',
    matchDistanceMs: toNumber(raw.match_distance_ms || raw.matchDistanceMs),

    // Validation
    actualLatencyMs: toNumber(raw.actual_latency_ms || raw.actualLatencyMs),
    validationResult: raw.validation_result || raw.validationResult || 'PENDING'
  };
}
```

### 8.3 UI Component Architecture

```
HILResults.tsx (Main Container)
├── TestStatusBanner
│   ├── Pass/Fail Status
│   ├── Session Info
│   └── Actions (Re-run, Export)
│
├── Tabs
│   ├── Tab 1: All Results (Default)
│   └── Tab 2: Per-Video Dropdown
│
├── MetricsSummaryCards
│   ├── Total Detections
│   ├── Matched/Unmatched
│   ├── Average Latency
│   └── Pass Rate
│
├── GroundTruthComparisonCards
│   ├── True Positives
│   ├── False Positives
│   ├── False Negatives
│   ├── Precision/Recall/F1
│   └── Confusion Matrix
│
├── FrameCorrelationTimeline
│   ├── Timeline Chart (Detections + GT)
│   ├── Zoom Controls
│   └── Hover Details
│
└── Detection Events Table
    ├── Sortable Columns
    ├── Row: DetectionTableRow
    │   ├── Timestamp
    │   ├── Video (Multi-video only)
    │   ├── Frame Number
    │   ├── Match Status
    │   ├── Latency
    │   └── Validation Result
    └── Pagination
```

### 8.4 Per-Video Filtering

**File:** `frontend/src/pages/HILResults.tsx` (Lines 236-300)

**Video Selection Logic:**
```typescript
const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);

// Filter data based on selected video
const filteredDetections = useMemo(() => {
  if (!selectedVideoId) {
    return baseDetections;  // Show all detections
  }
  return baseDetections.filter(det => det.videoId === selectedVideoId);
}, [baseDetections, selectedVideoId]);

const filteredGroundTruth = useMemo(() => {
  if (!selectedVideoId) {
    return groundTruthEvents;  // Show all GT
  }
  return groundTruthEvents.filter(gt => gt.videoId === selectedVideoId);
}, [groundTruthEvents, selectedVideoId]);

// Get metrics for selected video
const selectedVideoMetrics = useMemo(() => {
  if (!selectedVideoId) {
    return enhancedResults?.ground_truth_comparison;  // Session-level
  }

  const videoResult = perVideoSummaries.find(v => v.videoId === selectedVideoId);
  return videoResult?.ground_truth_comparison;
}, [selectedVideoId, perVideoSummaries, enhancedResults]);
```

**Video Dropdown Component:**
```tsx
<FormControl sx={{ minWidth: 200 }}>
  <Select
    value={selectedVideoId || 'all'}
    onChange={(e) => setSelectedVideoId(e.target.value === 'all' ? null : e.target.value)}
  >
    <MenuItem value="all">All Videos</MenuItem>
    {availableVideos.map(video => (
      <MenuItem key={video.id} value={video.id}>
        {video.filename}
      </MenuItem>
    ))}
  </Select>
</FormControl>
```

### 8.5 Real-Time Updates

**WebSocket Subscription:**
```typescript
useEffect(() => {
  if (!sessionId) return;

  // Connect to WebSocket
  const socket = websocketService.connect();

  // Join session room
  socket.emit('join_session', { session_id: sessionId });

  // Listen for detection events
  socket.on('detection_event', (data) => {
    const normalizedDetection = normalizeDetectionEvent(data.detection);

    // Add to detections list
    setBaseDetections(prev => [...prev, normalizedDetection]);

    // Update metrics
    if (data.metrics_update) {
      setEnhancedResults(prev => ({
        ...prev,
        ...data.metrics_update
      }));
    }
  });

  // Listen for session completion
  socket.on('session_completed', (data) => {
    // Reload full results
    loadResults();
  });

  // Cleanup
  return () => {
    socket.emit('leave_session', { session_id: sessionId });
    socket.off('detection_event');
    socket.off('session_completed');
  };
}, [sessionId]);
```

---

## 9. WebSocket Event Flow

### 9.1 Event Types

| Event Type | Direction | Trigger | Payload |
|-----------|-----------|---------|---------|
| `session_started` | Backend → Frontend | Session creation | session_id, t0_timestamp, timing_quality |
| `video_started` | Backend → Frontend | Video playback start | video_id, t1_timestamp, presentation_delay_ms |
| `detection_event` | Backend → Frontend | LabJack detection | detection object, metrics_update |
| `video_completed` | Backend → Frontend | Video playback end | video_id, actual_duration_ms, sequence_complete |
| `sequence_completed` | Backend → Frontend | All videos complete | total_videos, completed_at |
| `session_completed` | Backend → Frontend | Session finalized | analysis object, final_metrics |
| `join_session` | Frontend → Backend | WebSocket connect | session_id |
| `leave_session` | Frontend → Backend | WebSocket disconnect | session_id |

### 9.2 WebSocket Server Architecture

**File:** `backend/socketio_server.py`

**Server Initialization:**
```python
import socketio
from fastapi import FastAPI

# Create Socket.IO server with async mode
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True
)

# Wrap with ASGI app
socket_app = socketio.ASGIApp(sio)

# Mount to FastAPI
app = FastAPI()
app.mount("/socket.io", socket_app)
```

**Session Room Management:**
```python
@sio.on('join_session')
async def handle_join_session(sid, data):
    """Client joins session-specific room for targeted broadcasts"""
    session_id = data.get('session_id')
    if session_id:
        await sio.enter_room(sid, f"session_{session_id}")
        logger.info(f"Client {sid} joined room: session_{session_id}")

@sio.on('leave_session')
async def handle_leave_session(sid, data):
    """Client leaves session room"""
    session_id = data.get('session_id')
    if session_id:
        await sio.leave_room(sid, f"session_{session_id}")
        logger.info(f"Client {sid} left room: session_{session_id}")
```

**Broadcast Functions:**
```python
async def broadcast_detection_event(session_id: str, detection: DetectionEvent):
    """Broadcast detection event to all clients in session room"""
    await sio.emit(
        'detection_event',
        {
            'type': 'detection_event',
            'session_id': session_id,
            'detection': detection.to_dict(),
            'metrics_update': get_session_metrics(session_id)
        },
        room=f"session_{session_id}"
    )

async def broadcast_session_completed(session_id: str, analysis: dict):
    """Broadcast session completion to all clients"""
    await sio.emit(
        'session_completed',
        {
            'type': 'session_completed',
            'session_id': session_id,
            'analysis': analysis,
            'timestamp': datetime.now(timezone.utc).isoformat()
        },
        room=f"session_{session_id}"
    )
```

### 9.3 Frontend WebSocket Service

**File:** `frontend/src/services/websocketService.ts`

**Connection Management:**
```typescript
import { io, Socket } from 'socket.io-client';

class WebSocketService {
  private socket: Socket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  connect(): Socket {
    if (this.socket?.connected) {
      return this.socket;
    }

    const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';

    this.socket = io(apiUrl, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: this.maxReconnectAttempts
    });

    // Connection event handlers
    this.socket.on('connect', () => {
      console.log('✅ WebSocket connected');
      this.reconnectAttempts = 0;
    });

    this.socket.on('disconnect', (reason) => {
      console.warn('⚠️ WebSocket disconnected:', reason);
    });

    this.socket.on('reconnect_attempt', (attempt) => {
      console.log(`🔄 WebSocket reconnecting... (${attempt}/${this.maxReconnectAttempts})`);
      this.reconnectAttempts = attempt;
    });

    this.socket.on('reconnect_failed', () => {
      console.error('❌ WebSocket reconnection failed after max attempts');
    });

    return this.socket;
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  emit(event: string, data: any) {
    if (this.socket?.connected) {
      this.socket.emit(event, data);
    }
  }

  on(event: string, callback: (data: any) => void) {
    if (this.socket) {
      this.socket.on(event, callback);
    }
  }

  off(event: string, callback?: (data: any) => void) {
    if (this.socket) {
      if (callback) {
        this.socket.off(event, callback);
      } else {
        this.socket.off(event);
      }
    }
  }
}

export default new WebSocketService();
```

---

## 10. Timing Synchronization Architecture

### 10.1 Timing Points

```
T0: Command Timestamp
    User clicks "Start Test"
    Captured: time.perf_counter() or time.time()
    Precision: ~100-500ns (system dependent)
    Stored: TestSession.command_start_timestamp

T1: Video Start Timestamp
    Video element fires onPlay event
    Captured: time.perf_counter() or time.time()
    Precision: ~100-500ns
    Stored: SequenceVideoResult.video_start_time

T_detection: Detection Timestamp
    LabJack voltage threshold crossed
    Captured: LabJack timestamp or time.time()
    Precision: ~1μs (LabJack hardware)
    Stored: DetectionEvent.detection_timestamp

T_GT: Ground Truth Timestamp
    Expected detection time in video
    Calculated: GT frame_number / video_fps
    Stored: GroundTruthObject.timestamp
```

### 10.2 Presentation Delay Calculation

**Formula:**
```
Presentation Delay (ms) = (T1 - T0) * 1000

Where:
- T0 = Command start timestamp (test initiation)
- T1 = Video start timestamp (first frame displayed)
- Result = Time from command to first visible frame
```

**Quality Assessment:**
```python
def assess_presentation_delay_quality(delay_ms: float) -> str:
    """Categorize presentation delay quality"""
    if delay_ms < 50:
        return "excellent"  # < 50ms = imperceptible
    elif delay_ms < 100:
        return "good"       # 50-100ms = acceptable
    elif delay_ms < 200:
        return "acceptable" # 100-200ms = noticeable but OK
    else:
        return "poor"       # > 200ms = problematic
```

### 10.3 Video-Relative Timestamp

**Formula:**
```
Video-Relative Timestamp (s) = T_detection - T1

Where:
- T_detection = Detection event timestamp (hardware)
- T1 = Video start timestamp
- Result = Seconds from video start (0-based)
```

**Frame Number Calculation:**
```python
frame_number = int(video_relative_timestamp * video_fps)
```

### 10.4 Latency Measurement

**Actual Latency Calculation:**
```python
def calculate_actual_latency(detection_timestamp: float,
                            expected_timestamp: float) -> float:
    """
    Calculate actual presentation latency.

    Args:
        detection_timestamp: When detection occurred (hardware)
        expected_timestamp: When GT object should appear (video time)

    Returns:
        Latency in milliseconds (can be negative if early)
    """
    latency_s = detection_timestamp - expected_timestamp
    latency_ms = latency_s * 1000
    return latency_ms
```

**Validation Against Threshold:**
```python
def validate_latency(actual_latency_ms: float,
                    max_latency_threshold_ms: float) -> str:
    """
    Validate latency against configured threshold.

    Returns: "PASS" or "FAIL"
    """
    # Absolute value to handle negative latency (early detection)
    abs_latency = abs(actual_latency_ms)

    if abs_latency <= max_latency_threshold_ms:
        return "PASS"
    else:
        return "FAIL"
```

### 10.5 Timing Service Architecture

**File:** `backend/services/precision_timing_service.py`

**Service Capabilities:**
1. **High-Precision Timestamps** - Sub-millisecond accuracy
2. **Timing Synchronization** - Coordinate hardware/software clocks
3. **Latency Calculation** - Measure system delays
4. **Drift Compensation** - Adjust for clock drift over time

**Key Methods:**
```python
class PrecisionTimingService:
    def get_precise_timestamp(self) -> float:
        """Get high-precision timestamp using best available clock"""
        return time.perf_counter()

    def calculate_elapsed_ms(self, start_time: float) -> float:
        """Calculate elapsed time in milliseconds"""
        return (time.perf_counter() - start_time) * 1000

    def synchronize_timestamps(self,
                              hardware_timestamp: float,
                              software_timestamp: float) -> float:
        """Calculate offset between hardware and software clocks"""
        return software_timestamp - hardware_timestamp
```

---

## 11. State Machine Diagrams

### 11.1 Test Session State Machine

```
┌──────────┐
│  CREATED │ Initial state after database record creation
└────┬─────┘
     │ start_hil_test_session()
     ▼
┌──────────┐
│  RUNNING │ Test in progress, monitoring active
└────┬─────┘
     │ complete_test_session()
     ├─── validate_video_sequence_completion()
     │    ├─ FAIL → VALIDATION_FAILED (terminal)
     │    └─ PASS ↓
     ▼
┌───────────┐
│ COMPLETED │ Test finished successfully
└───────────┘

Error States:
- VALIDATION_FAILED: Video sequence timing missing/invalid
- FAILED: General test failure
```

### 11.2 Video Status State Machine

```
┌─────────┐
│ PENDING │ Video in sequence, not yet started
└────┬────┘
     │ start_video_playback()
     ▼
┌─────────┐
│ PLAYING │ Video actively playing, LabJack monitoring
└────┬────┘
     │ end_video_playback()
     ▼
┌───────────┐
│ COMPLETED │ Video finished, duration calculated
└───────────┘
```

### 11.3 Detection Event State Machine

```
┌──────────┐
│ DETECTED │ Hardware event captured, timestamp recorded
└────┬─────┘
     │ Video ID assignment (timestamp-based)
     ├─ SUCCESS: video_id populated
     ├─ RACE: video_id = NULL (reassigned later)
     ▼
┌────────────┐
│  ASSIGNED  │ Detection correlated to specific video
└─────┬──────┘
      │ Ground truth matching
      ├─ MATCHED: ground_truth_match_id populated
      ├─ UNMATCHED: No GT within tolerance
      ▼
┌──────────┐
│ MATCHED  │ Detection linked to GT object
└────┬─────┘
     │ Latency validation
     ├─ PASS: within threshold
     ├─ FAIL: exceeds threshold
     ▼
┌───────────┐
│ VALIDATED │ Final classification (PASS/FAIL)
└───────────┘
```

### 11.4 Sequence Orchestration State Machine

```
┌────────────────┐
│ SEQUENCE_INIT  │ VideoSequenceOrchestrator.start_sequence()
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ VIDEO_PENDING  │ Waiting for video to start
└───────┬────────┘
        │ notify_video_started()
        ▼
┌────────────────┐
│ VIDEO_PLAYING  │ Video actively playing
└───────┬────────┘
        │ notify_video_ended()
        ├─── evaluate_video_completion()
        │    ├─ More videos → ADVANCE_TO_NEXT
        │    └─ Last video → SEQUENCE_COMPLETE
        ▼
┌────────────────┐
│ ADVANCE_TO_NEXT│ Trigger next video in sequence
└───────┬────────┘
        │ trigger_next_video()
        ▼
┌────────────────┐
│ VIDEO_PENDING  │ (loop back for next video)
└────────────────┘

Terminal State:
┌──────────────────┐
│ SEQUENCE_COMPLETE│ All videos finished
└──────────────────┘
```

---

## 12. Data Transformation Pipeline

### 12.1 Database → API Response Transformation

**Backend Serialization (Pydantic):**
```python
class DetectionEventResponse(BaseModel):
    # Database field → API response field mapping
    id: str
    test_session_id: str = Field(alias="testSessionId")
    video_id: Optional[str] = Field(alias="videoId")

    detection_timestamp: float = Field(alias="detectionTimestamp")
    video_relative_timestamp: Optional[float] = Field(alias="videoRelativeTimestamp")
    frame_number: Optional[int] = Field(alias="frameNumber")

    voltage: float
    channel: str

    ground_truth_match_id: Optional[str] = Field(alias="groundTruthMatchId")
    match_status: str = Field(alias="matchStatus")
    match_distance_ms: Optional[float] = Field(alias="matchDistanceMs")

    actual_latency_ms: Optional[float] = Field(alias="actualLatencyMs")
    validation_result: str = Field(alias="validationResult")

    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(alias="createdAt")

    class Config:
        orm_mode = True  # Allow conversion from SQLAlchemy models
        allow_population_by_field_name = True  # Accept both snake_case and camelCase
```

**Transformation Flow:**
```
SQLAlchemy Model (snake_case)
    ↓ Pydantic serialization
API Response (camelCase)
    ↓ HTTP JSON
Frontend Raw Data (camelCase)
    ↓ normalizeDetectionEvent()
Frontend TypeScript Types (camelCase)
```

### 12.2 Frontend Normalization Functions

**Detection Event Normalization:**
```typescript
export function normalizeDetectionEvent(raw: any): EnhancedDetectionEvent {
  // Handle both snake_case (legacy) and camelCase (new) field names
  return {
    id: raw.id || `det-${Date.now()}`,
    testSessionId: raw.test_session_id || raw.testSessionId,
    videoId: raw.video_id || raw.videoId,

    // Timing fields
    detectionTimestamp: toNumber(raw.detection_timestamp || raw.detectionTimestamp),
    videoRelativeTimestamp: toNumber(raw.video_relative_timestamp || raw.videoRelativeTimestamp),
    frameNumber: toNumber(raw.frame_number || raw.frameNumber),

    // Hardware fields
    voltage: toNumber(raw.voltage),
    channel: raw.channel,

    // Ground truth matching
    groundTruthMatchId: raw.ground_truth_match_id || raw.groundTruthMatchId,
    matchStatus: raw.match_status || raw.matchStatus || 'unmatched',
    matchDistanceMs: toNumber(raw.match_distance_ms || raw.matchDistanceMs),

    // Validation
    actualLatencyMs: toNumber(raw.actual_latency_ms || raw.actualLatencyMs),
    validationResult: raw.validation_result || raw.validationResult || 'PENDING',

    // Metadata
    metadata: raw.metadata || {},
    createdAt: raw.created_at || raw.createdAt || new Date().toISOString()
  };
}
```

**Ground Truth Metrics Normalization:**
```typescript
export function normalizeGroundTruthMetrics(raw: any): GroundTruthMetrics | null {
  if (!raw) return null;

  const tp = toNumber(raw.true_positives ?? raw.truePositives);
  const fp = toNumber(raw.false_positives ?? raw.falsePositives);
  const fn = toNumber(raw.false_negatives ?? raw.falseNegatives);
  const totalGT = toNumber(
    raw.total_ground_truth ??
    raw.totalGroundTruth ??
    raw.ground_truth_total ??
    raw.groundTruthTotal
  );

  // Recalculate metrics if not provided
  const precision = raw.precision ?? (
    (tp + fp) > 0 ? (tp / (tp + fp)) * 100 : 0
  );

  const recall = raw.recall ?? (
    (tp + fn) > 0 ? (tp / (tp + fn)) * 100 : 0
  );

  const f1Score = raw.f1_score ?? raw.f1Score ?? (
    (precision + recall) > 0 ? (2 * precision * recall) / (precision + recall) : 0
  );

  return {
    truePositives: tp,
    falsePositives: fp,
    falseNegatives: fn,
    totalGroundTruth: totalGT,
    precision: toNumber(precision),
    recall: toNumber(recall),
    f1Score: toNumber(f1Score)
  };
}
```

### 12.3 API Response Caching

**Frontend API Service:**
```typescript
class ApiCache {
  private cache = new Map<string, { data: any; timestamp: number; ttl: number }>();

  get(key: string): any | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    const now = Date.now();
    if (now - entry.timestamp > entry.ttl) {
      this.cache.delete(key);
      return null;
    }

    return entry.data;
  }

  set(key: string, data: any, ttl: number = 60000) {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl
    });
  }

  invalidate(pattern: string) {
    for (const key of this.cache.keys()) {
      if (key.includes(pattern)) {
        this.cache.delete(key);
      }
    }
  }
}

// Usage in API service
async getEnhancedResults(sessionId: string): Promise<EnhancedHILResults> {
  const cacheKey = `enhanced-results:${sessionId}`;

  // Check cache first
  const cached = apiCache.get(cacheKey);
  if (cached) {
    console.log('✅ Cache hit:', cacheKey);
    return cached;
  }

  // Fetch from API
  const response = await axios.get(`/api/test-sessions/${sessionId}/enhanced-results`);
  const data = response.data;

  // Cache for 5 minutes (results don't change after completion)
  apiCache.set(cacheKey, data, 300000);

  return data;
}
```

---

## 13. Critical Dependencies

### 13.1 Service Dependency Graph

```
hil_test_complete.py
  ├─ timing_orchestration_service
  │   ├─ precision_timing_service
  │   └─ timestamp_conversion_utils
  ├─ video_sequence_orchestrator
  │   └─ video_timing_service
  ├─ labjack_detection_monitor
  │   ├─ labjack_service
  │   ├─ video_id_resolver
  │   └─ timestamp_video_resolver
  ├─ session_completion_service
  │   ├─ ground_truth_matching_service
  │   └─ detection_video_reassignment
  └─ socketio_server
      └─ WebSocket clients
```

### 13.2 Database Dependencies

**Foreign Key Relationships:**
```sql
TestSession.id
  ← VideoTestSequence.test_session_id
      ← SequenceVideoResult.video_sequence_id
  ← DetectionEvent.test_session_id

Video.id
  ← SequenceVideoResult.video_id
  ← DetectionEvent.video_id
  ← GroundTruthObject.video_id

GroundTruthObject.id
  ← DetectionEvent.ground_truth_match_id
```

**Critical Constraints:**
1. **Cascade Delete:** Deleting TestSession removes all DetectionEvents
2. **Orphan Prevention:** video_id cannot be NULL in SequenceVideoResult
3. **Matching Integrity:** ground_truth_match_id must reference valid GT object

### 13.3 Timing Dependencies

**Prerequisite Order:**
1. T0 must be captured before T1
2. T1 must be captured before detection events
3. Video start must occur before video end
4. Sequence start must occur before any video start
5. All videos must complete before sequence completion

**Failure Impacts:**
- Missing T0 → Cannot calculate presentation delay
- Missing T1 → Cannot calculate video-relative timestamps
- Missing video_timing → Cannot assign detections to videos
- Missing video end time → Session completion blocked

---

## 14. Error Handling and Recovery

### 14.1 Validation Errors

**Session Completion Validation:**
```python
# Error: Video sequence timing missing
{
  "status_code": 400,
  "detail": {
    "error": "Session completion validation failed",
    "message": "Video sequence session missing sequence_metadata. This indicates video lifecycle events never fired.",
    "session_id": "12345",
    "validation_type": "video_sequence_timing"
  }
}
```

**Recovery Action:**
- Investigate why video lifecycle events not triggered
- Check frontend video player event handlers
- Verify WebSocket connection during test
- Review browser console for JavaScript errors

### 14.2 Race Conditions

**NULL Video ID Assignment:**

**Problem:**
- Detection arrives before video lifecycle events fire
- video_id resolver cannot determine which video
- Detection stored with video_id = NULL

**Detection:**
```python
null_detections = db.query(DetectionEvent).filter(
    DetectionEvent.test_session_id == session_id,
    DetectionEvent.video_id.is_(None)
).count()

if null_detections > 0:
    logger.warning(f"Session {session_id} has {null_detections} detections with NULL video_id")
```

**Recovery:**
```python
# Automatic recovery during session completion
await reassign_null_video_ids(session_id, dry_run=False)
```

### 14.3 WebSocket Disconnections

**Problem:** Client loses WebSocket connection during test

**Detection:**
```typescript
socket.on('disconnect', (reason) => {
  console.warn('WebSocket disconnected:', reason);

  if (reason === 'io server disconnect') {
    // Server initiated disconnect
    showError('Lost connection to server. Please refresh page.');
  } else if (reason === 'transport close') {
    // Network issue
    showWarning('Network interruption. Attempting to reconnect...');
  }
});
```

**Recovery:**
```typescript
socket.on('reconnect', (attemptNumber) => {
  console.log('WebSocket reconnected after', attemptNumber, 'attempts');

  // Rejoin session room
  socket.emit('join_session', { session_id: sessionId });

  // Reload results to catch missed events
  loadResults();
});
```

### 14.4 LabJack Hardware Errors

**Connection Loss During Test:**
```python
# Monitoring loop detects hardware disconnection
try:
    voltage = labjack_service.read_voltage(channel)
except LabJackConnectionError:
    logger.error("LabJack disconnected during test session")

    # Broadcast hardware error
    await socketio.emit('hardware_error', {
        'type': 'labjack_disconnected',
        'session_id': session_id,
        'timestamp': datetime.now().isoformat()
    })

    # Mark session as failed
    session.status = "hardware_failure"
    db.commit()
```

**Frontend Handling:**
```typescript
socket.on('hardware_error', (data) => {
  if (data.type === 'labjack_disconnected') {
    showError(
      'Hardware Connection Lost',
      'LabJack device disconnected during test. Test results may be incomplete. Please check hardware connection and restart test.'
    );

    // Disable real-time updates
    setRealtimeEnabled(false);
  }
});
```

---

## Conclusion

This comprehensive data flow analysis documents the complete journey of HIL test execution from start to results display. The system employs:

1. **Multi-layered architecture** with clear separation of concerns
2. **Precise timing synchronization** using T0/T1 timestamps
3. **Real-time WebSocket updates** for live monitoring
4. **Robust error handling** with validation and recovery
5. **Efficient database queries** to prevent N+1 problems
6. **State machine coordination** for complex workflows
7. **Data transformation pipeline** for frontend/backend integration

**Critical Success Factors:**
- Video lifecycle events (onPlay, onEnded) MUST fire for timing data
- LabJack monitoring runs continuously from session start
- Orchestrator synchronization required for multi-video sequences
- Ground truth matching depends on accurate timestamps
- WebSocket connectivity essential for real-time updates

**Known Limitations:**
1. T0/T1 precision depends on system clock accuracy
2. Video timing relies on browser video element events
3. LabJack auto-stop requires accurate video duration
4. NULL video_id reassignment is post-hoc (not real-time)
5. WebSocket disconnection loses intermediate events

**Future Improvements:**
1. Hardware-synchronized timestamps (PTP/NTP)
2. Database triggers for automatic metric calculation
3. GraphQL subscriptions for selective real-time updates
4. Client-side detection event buffering
5. Distributed tracing for debugging timing issues

---

**Document Maintenance:**
- Review quarterly and update for architectural changes
- Update diagrams when services refactored
- Add new WebSocket events as implemented
- Document breaking changes in separate migration guide

**Related Documentation:**
- `PHASE_4_COMPREHENSIVE_ANALYSIS.md` - Implementation details
- `MULTI_VIDEO_TIMING_IMPLEMENTATION.md` - Timing architecture
- `TIMESTAMP_RESOLVER_ARCHITECTURE.md` - Video ID resolution
- `API_VERIFICATION_REPORT.md` - API contract validation
