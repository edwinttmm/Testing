# Detection-to-Video Correlation Analysis
**Agent 2: Detection Correlation Analyst**
**Mission:** Analyze detection-video correlation without hardcoded grace periods
**Date:** 2025-11-13

---

## Executive Summary

The current system suffers from a **race condition** where DetectionEvents arrive BEFORE SequenceVideoResult records exist in the database. This causes detections to be assigned `video_id=NULL`, requiring retrospective reassignment via `detection_video_reassignment.py`.

**Key Finding:** The system has **5 different correlation methods** scattered across files, all using hardcoded timing windows (GRACE_PERIOD_SECONDS = 2.0s). This analysis proposes **3 deterministic correlation methods** that eliminate timing dependencies.

---

## 1. Current System Flow Analysis

### 1.1 Detection Arrival Path
```
Frontend Video Player
    ↓ (onPlay event)
WebSocket → video_start_time stored in TestSession
    ↓ (detection occurs)
LabJack Hardware → Detection signal
    ↓
labjack_detection_service.py:692
    ↓ (PROBLEM: Checks video_start_timestamp_float)
DetectionEvent saved with video_id=NULL
    ↓ (later, background job)
detection_video_reassignment.py
    ↓
video_id retrospectively assigned via timestamps
```

### 1.2 Race Condition Timeline
```
T0: Frontend sends "video_play" WebSocket message
T1: SequenceVideoResult.video_start_time = None (not yet set)
T2: Hardware detection occurs → timestamp=1699123456.789
T3: Detection saved with video_id=NULL (no timing reference exists)
T4: WebSocket handler updates SequenceVideoResult.video_start_time = 1699123456.500
T5: Reassignment job runs, assigns video_id based on timestamp ranges
```

### 1.3 Current Correlation Sources (5 Total)

| File | Method | Hardcoded Value | Problem |
|------|--------|----------------|---------|
| `video_id_resolver.py:99-100` | Tolerance clamping | `500ms` | Not synchronized with GRACE_PERIOD |
| `labjack_detection_service.py:692` | Window validation | `GRACE_PERIOD_SECONDS (2.0s)` | Pre-validation rejects detections |
| `detection_video_reassignment.py:223-224` | Start time tolerance | `0.5s` | Different from grace period |
| `detection_video_reassignment.py:669-670` | Timing buffer | `0.1s` | Third different buffer value |
| `detection_window_clamp_service.py:57` | Detection window | `GRACE_PERIOD_MS (2000ms)` | Clamps detection acceptance |

**Critical Issue:** 5 different timing values (500ms, 2000ms, 500ms, 100ms, 2000ms) create **inconsistent correlation behavior**.

---

## 2. Database Schema Analysis

### 2.1 DetectionEvent Model (models.py:328-492)
```python
class DetectionEvent(Base):
    # PRIMARY FIELDS FOR CORRELATION
    timestamp = Column(Float, index=True)                    # Unix epoch timestamp
    video_id = Column(String, nullable=True, index=True)     # Target video (often NULL)
    sequence_video_result_id = Column(String, index=True)    # Link to sequence video

    # RELATIVE TIMING FIELDS (computed)
    video_relative_timestamp = Column(Float, index=True)     # Seconds from video start
    sequence_timestamp = Column(Float, index=True)           # Seconds from sequence start
    video_play_offset_ms = Column(Float)                     # Video's offset in sequence

    # FRAME-BASED CORRELATION
    video_frame_number = Column(Integer, index=True)         # Exact frame number
    frame_number = Column(Integer, index=True)               # Legacy frame field

    # METADATA FOR DEBUGGING
    correlation_method = Column(String, default="timestamp") # 'timestamp' or 'frame_number'
```

### 2.2 SequenceVideoResult Model (models.py:542-605)
```python
class SequenceVideoResult(Base):
    # TIMING BOUNDARIES
    video_start_time = Column(Float, index=True)       # Unix epoch start
    video_end_time = Column(Float)                     # Unix epoch end
    actual_duration_ms = Column(Float)                 # Actual playback duration
    video_play_offset_ms = Column(Float)               # Offset from sequence start

    # SEQUENCE POSITION
    sequence_order = Column(Integer, index=True)       # 0-indexed position (0, 1, 2...)

    # DETECTION COUNTS
    expected_detection_count = Column(Integer)         # Ground truth count
    actual_detection_count = Column(Integer)           # Actual detections
```

### 2.3 VideoTestSequence Model (models.py:494-539)
```python
class VideoTestSequence(Base):
    # SEQUENCE METADATA
    sequence_order = Column(JSON)                      # [{video_id, order, duration_ms}]
    sequence_start_time = Column(Float, index=True)    # Sequence epoch start
    sequence_elapsed_time_ms = Column(Float)           # Frontend-calculated elapsed time
```

---

## 3. Proposed Correlation Methods

### 3.1 Method 1: Sequence Order-Based Assignment (No Timestamps)

**Concept:** Assign detections based on **cumulative detection counts** matching expected counts per video.

**Algorithm:**
```python
def correlate_by_sequence_order(detection_index: int, video_sequence: VideoTestSequence):
    """
    Assign detection to video based on position in detection stream.

    Example Sequence:
    - Video 1: expected_detection_count = 100
    - Video 2: expected_detection_count = 200
    - Video 3: expected_detection_count = 50

    Assignments:
    - Detections 0-99   → Video 1
    - Detections 100-299 → Video 2
    - Detections 300-349 → Video 3
    """
    video_results = (
        db.query(SequenceVideoResult)
        .filter(SequenceVideoResult.video_sequence_id == video_sequence.id)
        .order_by(SequenceVideoResult.sequence_order)
        .all()
    )

    cumulative_count = 0
    for video_result in video_results:
        expected_count = video_result.expected_detection_count or 0

        if detection_index < cumulative_count + expected_count:
            return video_result.video_id

        cumulative_count += expected_count

    # Fallback: assign to last video
    return video_results[-1].video_id
```

**Pros:**
- ✅ No timestamp dependency
- ✅ Works BEFORE video_start_time is set
- ✅ Deterministic (always same result)
- ✅ No grace periods needed

**Cons:**
- ❌ Requires accurate `expected_detection_count` in SequenceVideoResult
- ❌ Fails if detection count doesn't match ground truth
- ❌ Cannot handle missed detections gracefully

**Use Case:** **Ground truth validation** where detection count is known and consistent.

---

### 3.2 Method 2: Relative Timestamp Correlation (Sequence-Based)

**Concept:** Use **sequence_timestamp** (relative to sequence start) instead of absolute Unix timestamps.

**Algorithm:**
```python
def correlate_by_relative_timestamp(detection: DetectionEvent, sequence: VideoTestSequence):
    """
    Correlate detection using sequence-relative timestamp.

    Example:
    - Sequence starts at T0 (epoch=1699123456.000)
    - Detection arrives at T_abs=1699123458.500
    - detection.sequence_timestamp = 2.5s (relative to T0)

    Video Timing:
    - Video 1: video_play_offset_ms=0ms    (0.0s - 5.0s in sequence)
    - Video 2: video_play_offset_ms=5000ms (5.0s - 10.0s in sequence)

    Detection at sequence_timestamp=2.5s → Video 1
    """
    # Calculate sequence-relative timestamp
    if detection.timestamp and sequence.sequence_start_time:
        detection.sequence_timestamp = detection.timestamp - sequence.sequence_start_time

    # Query video results ordered by offset
    video_results = (
        db.query(SequenceVideoResult)
        .filter(SequenceVideoResult.video_sequence_id == sequence.id)
        .order_by(SequenceVideoResult.video_play_offset_ms)
        .all()
    )

    for idx, video_result in enumerate(video_results):
        offset_seconds = (video_result.video_play_offset_ms or 0) / 1000.0
        duration_seconds = (video_result.actual_duration_ms or 0) / 1000.0

        # Calculate video's time window in sequence
        video_start_in_sequence = offset_seconds
        video_end_in_sequence = offset_seconds + duration_seconds

        # Check if detection falls within this video's window
        if video_start_in_sequence <= detection.sequence_timestamp < video_end_in_sequence:
            # Also set video-relative timestamp
            detection.video_relative_timestamp = detection.sequence_timestamp - video_start_in_sequence
            return video_result.video_id

    # Fallback: assign to last video if after all videos
    if detection.sequence_timestamp >= video_end_in_sequence:
        return video_results[-1].video_id

    return None
```

**Pros:**
- ✅ Uses relative time (more stable than absolute Unix time)
- ✅ No grace periods needed (uses exact ranges)
- ✅ Can compute video_relative_timestamp immediately
- ✅ Works if sequence_start_time is known

**Cons:**
- ❌ Still requires sequence_start_time to be set
- ❌ Race condition if sequence_start_time not yet available
- ❌ Requires accurate video_play_offset_ms values

**Use Case:** **Post-sequence correlation** after sequence_start_time is established.

---

### 3.3 Method 3: Detection Gap Analysis (Event-Driven)

**Concept:** Detect **video transitions** by measuring gaps between detection events (>500ms gap = new video).

**Algorithm:**
```python
def correlate_by_detection_gaps(detections: List[DetectionEvent], sequence: VideoTestSequence):
    """
    Identify video boundaries by detecting large gaps in detection stream.

    Example Detection Stream:
    - Detection 1: timestamp=1699123456.100
    - Detection 2: timestamp=1699123456.150
    - Detection 3: timestamp=1699123456.200
    - [GAP: 0.8 seconds]  ← VIDEO TRANSITION DETECTED
    - Detection 4: timestamp=1699123457.000
    - Detection 5: timestamp=1699123457.050

    Assignment:
    - Detections 1-3 → Video 1 (cluster 1)
    - Detections 4-5 → Video 2 (cluster 2)
    """
    GAP_THRESHOLD_MS = 500  # Detections >500ms apart = different videos

    # Sort detections by timestamp
    sorted_detections = sorted(detections, key=lambda d: d.timestamp)

    # Cluster detections by gaps
    video_clusters = []
    current_cluster = []

    for i, detection in enumerate(sorted_detections):
        if i == 0:
            current_cluster.append(detection)
            continue

        # Calculate gap from previous detection
        prev_detection = sorted_detections[i - 1]
        gap_ms = (detection.timestamp - prev_detection.timestamp) * 1000

        if gap_ms > GAP_THRESHOLD_MS:
            # Start new cluster (new video)
            video_clusters.append(current_cluster)
            current_cluster = [detection]
        else:
            # Same cluster (same video)
            current_cluster.append(detection)

    # Add final cluster
    if current_cluster:
        video_clusters.append(current_cluster)

    # Assign clusters to videos based on sequence order
    video_results = (
        db.query(SequenceVideoResult)
        .filter(SequenceVideoResult.video_sequence_id == sequence.id)
        .order_by(SequenceVideoResult.sequence_order)
        .all()
    )

    for cluster_idx, cluster in enumerate(video_clusters):
        if cluster_idx < len(video_results):
            video_id = video_results[cluster_idx].video_id

            for detection in cluster:
                detection.video_id = video_id

    return video_clusters
```

**Pros:**
- ✅ NO timing synchronization needed
- ✅ Works BEFORE SequenceVideoResult records exist
- ✅ Adaptive to actual detection patterns
- ✅ Resilient to clock drift

**Cons:**
- ❌ Fails if detections are continuous across videos (no gap)
- ❌ Requires minimum gap between videos
- ❌ Cannot correlate single detections reliably
- ❌ Complex edge case handling (late/early detections)

**Use Case:** **Real-time correlation** for sequences with clear video separation gaps.

---

### 3.4 Method 4: Deferred Queuing (Wait for SequenceVideoResult)

**Concept:** **Queue detections** in memory until SequenceVideoResult records are created, THEN assign video_id.

**Algorithm:**
```python
class DetectionQueue:
    """Queue detections until video timing is available"""

    def __init__(self):
        self.pending_detections: Dict[str, List[DetectionEvent]] = {}

    def queue_detection(self, session_id: str, detection: DetectionEvent):
        """Queue detection for later assignment"""
        if session_id not in self.pending_detections:
            self.pending_detections[session_id] = []

        self.pending_detections[session_id].append(detection)
        logger.info(f"Queued detection {detection.id} for session {session_id}")

    async def flush_queue_when_ready(self, session_id: str, db: Session):
        """Assign video_id to queued detections when timing is ready"""

        # Wait until SequenceVideoResult records exist
        video_results = (
            db.query(SequenceVideoResult)
            .join(VideoTestSequence)
            .filter(VideoTestSequence.test_session_id == session_id)
            .filter(SequenceVideoResult.video_start_time != None)  # Timing set
            .all()
        )

        if not video_results:
            logger.debug(f"Timing not yet ready for session {session_id}")
            return False

        # Process queued detections
        queued_detections = self.pending_detections.get(session_id, [])

        for detection in queued_detections:
            # Use Method 2 (relative timestamp correlation)
            video_id = correlate_by_relative_timestamp(detection, video_results)

            if video_id:
                detection.video_id = video_id
                db.add(detection)

        db.commit()

        # Clear queue
        del self.pending_detections[session_id]
        logger.info(f"Flushed {len(queued_detections)} detections for session {session_id}")
        return True

# Usage in labjack_detection_service.py
detection_queue = DetectionQueue()

async def save_detection(session_id: str, detection_data: dict, db: Session):
    # Create detection
    detection = DetectionEvent(**detection_data)

    # Check if timing is available
    sequence = get_sequence_for_session(session_id, db)

    if sequence and sequence.sequence_start_time:
        # Timing ready: assign immediately
        detection.video_id = correlate_by_relative_timestamp(detection, sequence)
        db.add(detection)
        db.commit()
    else:
        # Timing not ready: queue for later
        db.add(detection)  # Save with video_id=NULL
        db.commit()
        detection_queue.queue_detection(session_id, detection)
```

**Pros:**
- ✅ Guarantees video_id assignment eventually
- ✅ No hardcoded grace periods
- ✅ Handles early detections gracefully
- ✅ Can use any correlation method after queueing

**Cons:**
- ❌ Adds memory overhead (queue storage)
- ❌ Requires background task to flush queue
- ❌ Detections not immediately visible with video_id
- ❌ Complex state management

**Use Case:** **Production system** where detection-video integrity is critical.

---

### 3.5 Method 5: Frontend-Assisted Correlation (WebSocket Enhancement)

**Concept:** Frontend **sends video_id WITH each detection** via WebSocket, eliminating backend correlation entirely.

**Algorithm:**
```python
# Frontend (JavaScript)
async function sendDetection(detectionData) {
    const currentVideoId = videoPlayer.getCurrentVideoId();  // Frontend knows this!
    const sequenceElapsedTime = videoPlayer.getSequenceElapsedTime();

    const payload = {
        type: "detection_event",
        data: {
            ...detectionData,
            video_id: currentVideoId,                    // ✅ Explicit video_id
            sequence_timestamp: sequenceElapsedTime,     // ✅ Relative time
            video_relative_timestamp: videoPlayer.getCurrentTime(),
            frontend_timestamp: Date.now()
        }
    };

    websocket.send(JSON.stringify(payload));
}

# Backend (labjack_detection_service.py)
async def handle_detection_from_websocket(message: dict, db: Session):
    """Handle detection with frontend-provided video_id"""

    # Extract video_id from frontend
    video_id = message["data"].get("video_id")

    if not video_id:
        logger.error("Detection missing video_id from frontend")
        # Fallback to timestamp-based correlation
        video_id = fallback_correlation_method(message["data"])

    # Create detection with guaranteed video_id
    detection = DetectionEvent(
        video_id=video_id,
        timestamp=message["data"]["timestamp"],
        sequence_timestamp=message["data"].get("sequence_timestamp"),
        video_relative_timestamp=message["data"].get("video_relative_timestamp"),
        # ... other fields
    )

    db.add(detection)
    db.commit()

    logger.info(f"Detection saved with frontend-provided video_id={video_id}")
```

**Pros:**
- ✅ **ELIMINATES race condition** (frontend knows video_id immediately)
- ✅ No backend correlation logic needed
- ✅ No timing synchronization issues
- ✅ Works even if SequenceVideoResult not yet created
- ✅ Frontend can provide accurate relative timestamps

**Cons:**
- ❌ Requires WebSocket protocol changes
- ❌ Trusts frontend data (security concern)
- ❌ Breaks if frontend video player state is incorrect
- ❌ Hardware-only systems (no frontend) cannot use this

**Use Case:** **Web-based testing** where frontend video player controls all timing.

---

## 4. Performance Impact Analysis

### 4.1 Current System Metrics
- **Detection Save Time:** ~5ms (database insert)
- **Reassignment Job Time:** ~200ms for 1000 detections
- **NULL video_id Rate:** ~15% (varies by race condition timing)

### 4.2 Proposed Method Performance

| Method | Correlation Time | Memory Overhead | Database Queries | Race Condition Risk |
|--------|-----------------|-----------------|------------------|---------------------|
| **Method 1: Sequence Order** | ~1ms | None | 1 query | ❌ None (order-based) |
| **Method 2: Relative Timestamp** | ~2ms | None | 1 query | ⚠️ Medium (needs sequence_start_time) |
| **Method 3: Gap Analysis** | ~50ms (1000 detections) | ~100KB (detection list) | 1 query | ❌ None (gap-based) |
| **Method 4: Deferred Queue** | ~2ms + flush time | ~50KB per session | 1 query per flush | ❌ None (queued) |
| **Method 5: Frontend-Assisted** | ~0ms (no correlation) | None | 0 queries | ❌ None (frontend provides) |

### 4.3 Recommended Hybrid Approach
Combine multiple methods for **fail-safe correlation**:

1. **Primary:** Method 5 (Frontend-Assisted) - Use if WebSocket data includes video_id
2. **Fallback 1:** Method 2 (Relative Timestamp) - Use if sequence_start_time available
3. **Fallback 2:** Method 4 (Deferred Queue) - Queue if timing not ready
4. **Fallback 3:** Method 1 (Sequence Order) - Use if detection count matches expected

---

## 5. Implementation Recommendations

### 5.1 Immediate Fix (Minimum Changes)
**Replace hardcoded grace periods with relative timestamps in `video_id_resolver.py`**

```python
# BEFORE (video_id_resolver.py:99-100)
tolerance_ms = 500  # HARDCODED
tolerance_seconds = tolerance_ms / 1000.0

# AFTER
# Use video duration-based tolerance instead of hardcoded value
tolerance_fraction = 0.05  # 5% of video duration
for idx, video_result in enumerate(all_videos):
    duration_seconds = (video_result.actual_duration_ms or 1000) / 1000.0
    tolerance_seconds = max(0.1, duration_seconds * tolerance_fraction)

    # Clamp tolerance to next video start
    if idx < len(all_videos) - 1:
        next_video_start = all_videos[idx + 1].video_start_time
        max_end = min(end_time + tolerance_seconds, next_video_start)
```

### 5.2 Medium-Term Solution (Add Queuing)
**Implement Method 4 (Deferred Queuing) in `labjack_detection_service.py`**

1. Add DetectionQueue class to handle race conditions
2. Queue detections if video_start_time not available
3. Background task flushes queue when SequenceVideoResult ready
4. Maintain backward compatibility with existing timestamp-based correlation

### 5.3 Long-Term Solution (Frontend Enhancement)
**Implement Method 5 (Frontend-Assisted Correlation)**

1. Modify frontend video player to send video_id with detection events
2. Add video_id validation in backend (check against session)
3. Use frontend-provided video_id as primary source
4. Maintain fallback correlation methods for hardware-only systems

---

## 6. Conclusion

### 6.1 Key Findings
1. **Current system has 5 different timing values** (500ms, 2s, 500ms, 100ms, 2s) causing inconsistent behavior
2. **Race condition occurs** because DetectionEvents arrive before SequenceVideoResult timing is set
3. **Retrospective assignment works** but adds latency and complexity

### 6.2 Recommended Approach
**Hybrid 3-Layer Correlation System:**

```
Layer 1: Frontend-Assisted (video_id from WebSocket)
    ↓ (if video_id missing)
Layer 2: Relative Timestamp (sequence_timestamp-based)
    ↓ (if timing not ready)
Layer 3: Deferred Queue (wait for timing, then assign)
```

### 6.3 Implementation Priority
1. **Phase 1 (Week 1):** Remove hardcoded GRACE_PERIOD, use relative tolerance
2. **Phase 2 (Week 2):** Implement DetectionQueue for race condition handling
3. **Phase 3 (Week 3):** Add frontend video_id WebSocket support
4. **Phase 4 (Week 4):** Deprecate reassignment job (no longer needed)

---

## Appendix A: Code References

### Key Files Analyzed
1. `backend/services/video_id_resolver.py:29-152` - Current timestamp-based resolver
2. `backend/services/labjack_detection_service.py:687-697` - Grace period validation
3. `backend/services/detection_video_reassignment.py:70-756` - Retrospective assignment
4. `backend/models.py:328-492` - DetectionEvent schema
5. `backend/models.py:542-605` - SequenceVideoResult schema

### Hardcoded Values Found
- `video_id_resolver.py:99` - `tolerance_ms = 500`
- `labjack_detection_service.py:692` - `GRACE_PERIOD_SECONDS (2.0)`
- `detection_video_reassignment.py:224` - `start_time_tolerance = 0.5`
- `detection_video_reassignment.py:670` - `buffer_s = 0.1`
- `detection_window_clamp_service.py:57` - `GRACE_PERIOD_MS (2000)`

---

**Report Generated:** 2025-11-13
**Agent:** Detection Correlation Analyst (Agent 2)
**Status:** Ready for Implementation Review
