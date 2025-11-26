# HIL Monitor vs Detection Service - Feature Analysis & Consolidation Plan

**Analysis Date**: 2025-11-17
**Context**: Both running simultaneously causes 0 detections due to device conflicts
**Goal**: Identify BEST features to keep for optimal HIL testing

---

## Executive Summary

**Recommendation**: **MERGE HIL Monitor's video sync into Detection Service's stream mode**

| System | Keep? | Why |
|--------|-------|-----|
| HIL Monitor (hil_video_frame_monitor.py) | ❌ **Deprecate** | 10 Hz polling insufficient for sub-100ms validation |
| Detection Service (labjack_detection_service.py) | ✅ **Keep** | 1000 Hz stream mode provides ±1-2ms accuracy |
| Dedicated Monitor (dedicated_labjack_monitor.py) | ✅ **Keep & Enhance** | Already orchestrates both correctly |

**Critical Finding**: `dedicated_labjack_monitor.py` ALREADY integrates both systems correctly but HIL Monitor should be removed from direct use.

---

## Part 1: Best Features from HIL Monitor

### Location
`/backend/src/hil_video_frame_monitor.py` (618 lines)

### ✅ UNIQUE & ESSENTIAL Features

#### 1. Video Frame Synchronization ⭐⭐⭐
**Code Location**: Lines 158-203, 289-410

```python
class HILVideoFrameMonitor:
    async def start_hil_monitoring(self, session_id: str, video_path: str,
                                   video_id: str = None, start_frame: int = 0):
        # Initialize video capture
        self.video_cap = cv2.VideoCapture(video_path)
        self.video_fps = self.video_cap.get(cv2.CAP_PROP_FPS)
        self.video_start_time = time.time()

        # Start T3 pipeline for session
        await self.t3_pipeline.start_hil_session(
            session_id, self.current_video_id, self.video_start_time
        )
```

**Why Essential**:
- Frame-accurate video playback control
- Direct cv2.VideoCapture management
- Frame seeking capability (line 529-546)
- Frame-by-frame processing with precise timing

**User Value**:
- Replay specific detection events
- Navigate to exact frames
- Frame-level ground truth matching

---

#### 2. T3 YOLO Detection Pipeline Integration ⭐⭐
**Code Location**: Lines 142-156, 307-310

```python
# Initialize T3 YOLO pipeline
self.t3_pipeline = await get_t3_yolo_pipeline()
self.t3_db_service = get_t3_database_service()

# Process frame for T3 detection
t3_events = await self.t3_pipeline.process_video_frame_for_t3(
    frame, self.current_frame_number, video_timestamp
)
```

**Why Essential**:
- Integrated ML detection on video frames
- Synchronized with hardware detection timing
- Direct database storage via T3 service

**User Value**:
- Compare ML detections vs hardware triggers
- Validate ML model accuracy in HIL context
- Unified detection timeline

---

#### 3. Real-time Frame Processing Statistics ⭐
**Code Location**: Lines 120-135, 324-374, 506-527

```python
self.stats = {
    'total_frames_processed': 0,
    'total_detections': 0,
    'average_processing_fps': 0.0,
    'average_detection_time_ms': 0.0,
    'software_delays': {
        'slow_frame_processing': False,
        'processing_rate_drift': False
    },
    'alerts': []
}

# Alert if processing too slow
if processing_time_ms > 120.0:
    alerts.append({
        'type': 'slow_frame_processing',
        'severity': 'warning',
        'message': f'Frame processing {processing_time_ms:.1f}ms exceeds threshold'
    })
```

**Why Essential**:
- Live monitoring of video processing performance
- Alerts for software delays affecting timing
- Processing rate drift detection

**User Value**:
- Identify software bottlenecks during tests
- Validate system capable of maintaining frame rate
- Troubleshoot timing issues

---

#### 4. Frame Callbacks for Custom Processing ⭐
**Code Location**: Lines 469-504

```python
def add_frame_callback(self, callback: Callable[[np.ndarray, FrameProcessingResult], Any]):
    """Add callback for processed frames"""
    self.frame_callbacks.append(callback)

async def _notify_frame_callbacks(self, frame: np.ndarray, result: FrameProcessingResult):
    """Notify frame processing callbacks"""
    for callback in self.frame_callbacks:
        try:
            await callback(frame, result)
        except Exception as e:
            logger.error(f"Frame callback error: {e}")
```

**Why Essential**:
- Extensible architecture for custom frame analysis
- Real-time frame access with detection results
- Screenshot capture integration point

**User Value**:
- Custom image processing during tests
- Real-time visualization
- Ground truth screenshot capture

---

### ❌ REDUNDANT OR INFERIOR Features

#### 1. 10 Hz Polling Detection ❌
**Code Location**: Lines 412-468

**Problem**:
- 100ms sleep causes ±10-100ms jitter
- Insufficient for sub-100ms latency validation
- Misses short-duration events (< 100ms)

**Better Alternative**: Detection Service stream mode (200-1000 Hz)

---

#### 2. Continuous Monitoring Loop ❌
**Code Location**: Lines 412-468

```python
async def run_continuous_monitoring(self, frame_limit: Optional[int] = None):
    while self.is_monitoring and (frame_limit is None or frames_processed < frame_limit):
        result = await self.process_next_frame()
        # Rate limiting to maintain target FPS
        if self.max_fps > 0:
            frame_duration = 1.0 / self.max_fps
            await asyncio.sleep(frame_duration - processing_time)
```

**Problem**:
- Sleep-based rate limiting adds jitter
- Async overhead for simple frame processing
- CPU polling wastes resources

**Better Alternative**: Detection Service uses hardware-timed streaming

---

#### 3. In-memory Frame Queue ❌
**Code Location**: Lines 113-114

```python
self.frame_processing_queue = asyncio.Queue(maxsize=50)
self.processing_results_queue = Queue(maxsize=200)
```

**Problem**:
- Memory overhead for frame buffering
- Queue management complexity
- Not used for timing-critical detection

**Better Alternative**: Process frames on-demand via seeking

---

## Part 2: Best Features from Detection Service

### Location
`/backend/services/labjack_detection_service.py` (3100+ lines)

### ✅ UNIQUE & ESSENTIAL Features

#### 1. Hardware-Timed Stream Mode ⭐⭐⭐⭐⭐
**Code Location**: Lines 336-443

```python
def start_monitoring(self, session_id: str, channels: List[str] = None,
                    voltage_threshold: float = 2.5, debounce_ms: int = 100,
                    sample_rate: int = 1000, use_stream_mode: bool = None):
    """
    Args:
        use_stream_mode: Use hardware-timed stream mode (200+ Hz)
            - Accuracy: ±1-2ms
            - Immune to OS scheduler jitter
            - Batch USB reads (20 samples per read)
    """
    # Auto-enable for high-frequency sampling
    default_stream_mode = sample_rate >= 200
```

**Why Essential**:
- **±1-2ms timing accuracy** (vs ±10-100ms polling)
- Hardware 80 MHz clock (not affected by Python GIL)
- Batch USB transactions (95% reduction)
- Meets sub-100ms latency validation requirements

**User Value**:
- Reliable latency measurements
- Capture short-duration events (<100ms)
- Hardware-grade timing precision

**Code Evidence** (from HOW_DETECTION_ACTUALLY_WORKS.md):
```
Stream Mode Timeline:
0.000s: LED ON (captured by hardware)
0.005s: Sample 2 (captured by hardware)
...
0.100s: USB read receives all 20 samples
Result: ±1-2ms accuracy
```

---

#### 2. Debounce Logic ⭐⭐⭐⭐
**Code Location**: Lines 128-141, detection processing

```python
@dataclass
class DetectionConfig:
    debounce_ms: int = 100  # Prevents duplicate detections
    voltage_threshold: float = 2.5

# In monitoring loop:
if voltage >= threshold and prev_voltage < threshold:
    if (timestamp - last_detection_time) > debounce_ms:
        detection = DetectionEvent(...)
        store_detection(detection)
        last_detection_time = timestamp
```

**Why Essential**:
- Prevents recording same hardware event multiple times
- Critical for accurate detection counts
- Configurable per-session

**User Value**:
- Accurate detection counts (no duplicates)
- Clean precision/recall metrics
- Reliable ground truth matching

**Without This**: HIL Monitor creates duplicate detections during 100ms polling window

---

#### 3. Batch Database Commits ⭐⭐⭐
**Code Location**: Lines 173-180, 513-543

```python
# Batch commit optimization for 200 Hz operation
self.detection_batch: List[Any] = []
self.last_commit_time: float = time.time()
self.batch_size_threshold: int = 100  # Commit after 100 events
self.batch_time_threshold: float = 1.0  # OR after 1 second

def _flush_batch_commits(self):
    """Critical: Flush remaining batch before stopping"""
    with self.batch_lock:
        if self.detection_batch:
            db.bulk_save_objects(self.detection_batch)
            db.commit()
```

**Why Essential**:
- Prevents database connection exhaustion (6000+ events/hour)
- Reduces write overhead by 100x
- Maintains data integrity during high-frequency detection

**User Value**:
- System stability during long tests
- No database connection errors
- Faster test execution

**Comparison**:
```
HIL Monitor:
- 1 INSERT per detection
- New connection each time
- 100 detections = 100 DB transactions

Detection Service:
- 1 INSERT with 100 rows
- Persistent connection
- 100 detections = 1 DB transaction
```

---

#### 4. Connection Manager Integration ⭐⭐⭐⭐
**Code Location**: Lines 182-189

```python
# Use shared LabJack connection manager to prevent device conflicts
try:
    from services.labjack_connection_manager import get_connection_manager
    self.connection_manager = get_connection_manager()
    logger.info("✅ Using shared LabJack connection manager")
except ImportError:
    self.connection_manager = None
    logger.warning("⚠️ May have device conflicts")
```

**Why Essential**:
- **Prevents "device in use" errors** when multiple services run
- Shared hardware access coordination
- Critical for concurrent monitoring

**User Value**:
- **FIXES THE CORE ISSUE**: Multiple services can't both access LabJack
- Eliminates 0 detection problem
- Reliable hardware access

---

#### 5. Session-Preserving Cleanup ⭐⭐⭐
**Code Location**: Lines 445-543

```python
def stop_session_monitoring(self, session_id: str) -> bool:
    """
    Session-preserving cleanup:
    1. Only stops monitoring for specified session
    2. Preserves LabJack hardware connection for other sessions
    3. Maintains thread safety
    4. Flushes remaining batch commits
    """
    # Wait for storage queue to drain
    while not self.storage_queue.empty() and (time.time() - start_time) < 5.0:
        time.sleep(0.1)

    # Flush batch commits
    self._flush_batch_commits()

    # Clean up session-specific state only
    self._cleanup_session_preserving_connection(session_id)
```

**Why Essential**:
- Multi-session support (run multiple tests concurrently)
- No data loss during cleanup
- Prevents connection reset overhead

**User Value**:
- Run multiple tests simultaneously
- No data loss when stopping tests
- Faster test turnaround

---

#### 6. Continuous Mode with Voltage Window ⭐⭐
**Code Location**: Lines 136-141, 279-290 (dedicated_labjack_monitor)

```python
@dataclass
class DetectionConfig:
    continuous_mode: bool = False  # Emit continuously while in voltage window
    continuous_lower_bound: Optional[float] = None  # Lower voltage bound
    continuous_upper_bound: Optional[float] = None  # Upper voltage bound
    continuous_interval_ms: int = 20  # Sample interval during continuous
    steady_high_logging: bool = True  # Log while voltage remains high
```

**Why Essential**:
- Streaming voltage data for time-series analysis
- Alternative to threshold-only detection
- Configurable sampling during voltage conditions

**User Value**:
- Capture full voltage curves (not just threshold crossings)
- Analyze signal characteristics
- Debugging hardware issues

---

#### 7. Orphaned Session Recovery ⭐⭐
**Code Location**: Lines 226-284

```python
def recover_orphaned_sessions(self):
    """Recover sessions left in monitoring state from crashes"""
    # Find sessions still "monitoring" from previous backend run
    orphaned = db.query(TestSession).filter(
        TestSession.completed_at == None,
        TestSession.status == "monitoring",
        TestSession.created_at < cutoff_time
    ).all()

    for session in orphaned:
        session.status = "crashed"
        session.metadata['recovered'] = True
```

**Why Essential**:
- Database cleanup after crashes
- Prevents "ghost" monitoring sessions
- System resilience

**User Value**:
- Clean database state after failures
- Clear test history
- No manual cleanup needed

---

### ❌ REDUNDANT Features (Already in Dedicated Monitor)

#### 1. Video Timing Conversion ❌
**Already Better**: `dedicated_labjack_monitor.py` has superior video sync via `VideoTimingService`

#### 2. WebSocket Callbacks ❌
**Already Better**: Detection Service has this PLUS dedicated monitor orchestrates it properly

#### 3. Direct Database Storage ❌
**Already Better**: Batch commit system is superior

---

## Part 3: Redundant Features Analysis

### Both Systems Have (Pick Best Version)

| Feature | HIL Monitor | Detection Service | Winner |
|---------|-------------|-------------------|--------|
| **Detection Capture** | 10 Hz polling | 1000 Hz stream | **Detection Service** |
| **Timestamp Recording** | Python time.time() | LabJack 80 MHz clock | **Detection Service** |
| **Database Storage** | Immediate per-event | Batch commits | **Detection Service** |
| **WebSocket Updates** | Via callbacks | Via callbacks | **Tie** (both good) |
| **Session Management** | Basic | Session-preserving | **Detection Service** |
| **Video Sync** | Direct frame timing | Via service | **HIL Monitor** |
| **Frame Access** | cv2.VideoCapture | N/A | **HIL Monitor** |
| **Statistics** | Frame processing | Detection events | **Tie** (different purposes) |

---

## Part 4: Required Features for HIL Testing

### ✅ Features We MUST Have

1. **Sub-100ms Latency Validation** (±1-2ms accuracy)
   - **Source**: Detection Service stream mode
   - **Evidence**: HOW_DETECTION_ACTUALLY_WORKS.md line 405-415

2. **Video-Frame Synchronization**
   - **Source**: HIL Monitor frame management
   - **Evidence**: hil_video_frame_monitor.py lines 249-287

3. **Ground Truth Matching**
   - **Source**: Already in dedicated_labjack_monitor
   - **Evidence**: dedicated_labjack_monitor.py lines 99-100

4. **Multi-Video Sequence Support**
   - **Source**: Already in dedicated_labjack_monitor
   - **Evidence**: dedicated_labjack_monitor.py lines 143-180

5. **Screenshot Capture at Detection Time**
   - **Source**: Already in dedicated_labjack_monitor via HIL comparison service
   - **Evidence**: dedicated_labjack_monitor.py lines 99-100

6. **Real-time WebSocket Updates**
   - **Source**: Both have it
   - **Evidence**: socketio_server.py

7. **Database Persistence**
   - **Source**: Detection Service (batch commits)
   - **Evidence**: labjack_detection_service.py lines 173-180

8. **Connection Management** (CRITICAL)
   - **Source**: Detection Service connection manager
   - **Evidence**: labjack_detection_service.py lines 182-189

---

## Part 5: Feature Consolidation Matrix

| Feature Category | HIL Monitor | Detection Service | Dedicated Monitor | **Keep From** |
|-----------------|-------------|-------------------|-------------------|---------------|
| **Detection Capture** | | | | |
| Hardware sampling | 10 Hz polling ❌ | 1000 Hz stream ✅ | Uses Detection Service | **Detection Service** |
| Timing accuracy | ±10-100ms ❌ | ±1-2ms ✅ | N/A | **Detection Service** |
| Debounce logic | ❌ None | ✅ 100ms | N/A | **Detection Service** |
| **Video Integration** | | | | |
| Frame synchronization | ✅ Direct cv2 | ❌ None | ✅ VideoTimingService | **HIL Monitor + Service** |
| Frame seeking | ✅ seek_to_frame() | ❌ None | ❌ Not implemented | **HIL Monitor** |
| Multi-video sequences | ❌ Single video | ❌ Single video | ✅ Full support | **Dedicated Monitor** |
| **ML Integration** | | | | |
| T3 YOLO pipeline | ✅ Integrated | ❌ None | ❌ None | **HIL Monitor** |
| Frame-by-frame detection | ✅ Yes | ❌ None | ❌ None | **HIL Monitor** |
| **Database** | | | | |
| Storage method | Immediate ❌ | Batch ✅ | Uses Detection Service | **Detection Service** |
| Connection management | New per write ❌ | Persistent ✅ | N/A | **Detection Service** |
| Batch commits | ❌ None | ✅ 100 events | N/A | **Detection Service** |
| **Real-time Updates** | | | | |
| WebSocket emission | ✅ Via callbacks | ✅ Via callbacks | ✅ Orchestrates | **All** |
| Session rooms | ❌ Not implemented | ❌ Not implemented | ✅ Yes | **Dedicated Monitor** |
| **System Management** | | | | |
| Connection pooling | ❌ None | ✅ Connection manager | N/A | **Detection Service** |
| Session preservation | ❌ Basic cleanup | ✅ Advanced | N/A | **Detection Service** |
| Orphaned recovery | ❌ None | ✅ Yes | ✅ Yes | **Detection Service** |
| Crash recovery | ❌ None | ✅ Signal handlers | ✅ Yes | **Detection Service** |
| **Statistics & Monitoring** | | | | |
| Frame processing stats | ✅ Detailed | ❌ Basic | ❌ Basic | **HIL Monitor** |
| Software delay alerts | ✅ Yes | ❌ No | ❌ No | **HIL Monitor** |
| Detection counts | ✅ Yes | ✅ Yes | ✅ Yes | **All** |

---

## Part 6: Recommended Consolidation Plan

### Phase 1: Deprecate HIL Monitor Direct Use

**Action**: Remove `hil_video_frame_monitor.py` from direct API endpoints

**Keep Code For**:
- Frame seeking utility functions
- T3 YOLO pipeline integration
- Frame processing statistics

**Migrate To**: Helper utilities called by dedicated_labjack_monitor

---

### Phase 2: Enhance Dedicated Monitor

**Add from HIL Monitor**:

1. **Frame Seeking Capability**
```python
# In dedicated_labjack_monitor.py
async def seek_to_detection_frame(self, detection_id: str) -> np.ndarray:
    """Seek to frame where detection occurred and return frame"""
    detection = db.query(DetectionEvent).filter_by(id=detection_id).first()
    video_path = get_video_path(detection.video_id)

    cap = cv2.VideoCapture(video_path)
    frame_number = detection.video_frame_number
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    cap.release()

    return frame
```

2. **Frame Processing Statistics**
```python
# Add to dedicated_labjack_monitor.py
self.frame_stats = {
    'frames_analyzed': 0,
    'ml_detections': 0,
    'processing_fps': 0.0,
    'software_delays': []
}
```

3. **T3 YOLO Integration** (if needed)
```python
# Optional: Add ML detection to dedicated monitor
from src.hil_t3_yolo_pipeline import get_t3_yolo_pipeline

async def analyze_detection_frame(self, frame, timestamp):
    """Run ML detection on frame for comparison"""
    t3_events = await self.t3_pipeline.process_video_frame_for_t3(
        frame, frame_number, timestamp
    )
    return t3_events
```

---

### Phase 3: Update API Endpoints

**Remove**:
```python
# ❌ Old HIL Monitor endpoints
POST /api/hil/monitor/start
POST /api/hil/monitor/process-frame
```

**Keep & Update**:
```python
# ✅ Dedicated Monitor endpoints
POST /api/hil/start-monitoring  # Uses dedicated_labjack_monitor + detection service
GET  /api/hil/{session_id}/detections  # From detection_events table
GET  /api/hil/{session_id}/frame/{frame_number}  # Add frame seeking
POST /api/hil/{session_id}/analyze-frame  # Optional ML analysis
```

---

### Phase 4: Configuration Consolidation

**Single Config File**: `/backend/config/hil_config.json`

```json
{
  "detection": {
    "sample_rate": 1000,
    "use_stream_mode": true,
    "voltage_threshold": 3.3,
    "debounce_ms": 100,
    "batch_commit_size": 100,
    "batch_commit_interval_s": 1.0
  },
  "video": {
    "enable_frame_sync": true,
    "enable_ml_detection": false,
    "capture_screenshots": true,
    "fps_target": 24.0
  },
  "ground_truth": {
    "enable_matching": true,
    "tolerance_ms": 100,
    "screenshot_zoom_factor": 2.0
  },
  "system": {
    "use_connection_manager": true,
    "enable_orphan_recovery": true,
    "max_concurrent_sessions": 5
  }
}
```

---

## Part 7: Final Recommendations

### Keep These Services

1. **✅ dedicated_labjack_monitor.py**
   - Main orchestration service
   - Already integrates both systems correctly
   - Video timing service integration
   - Ground truth matching
   - WebSocket coordination

2. **✅ labjack_detection_service.py**
   - Hardware-timed stream mode (critical for accuracy)
   - Batch database commits
   - Connection manager
   - Session-preserving cleanup
   - Debounce logic

3. **✅ labjack_connection_manager.py**
   - Prevents device conflicts
   - Shared hardware access
   - Critical for concurrent operations

4. **✅ video_timing_service.py**
   - Video-relative timestamp conversion
   - Frame number calculation
   - Multi-video sequence support

5. **✅ hil_screenshot_service.py**
   - Screenshot capture
   - Ground truth comparison
   - Frame analysis

---

### Deprecate These

1. **❌ hil_video_frame_monitor.py** (direct use)
   - Extract utilities into helpers
   - Keep T3 YOLO integration separate
   - Remove 10 Hz polling detection

---

### Architecture After Consolidation

```
┌────────────────────────────────────────────────────────────────┐
│                        HIL TEST FLOW                            │
└────────────────────────────────────────────────────────────────┘

API Endpoint: POST /api/hil/start-monitoring
    ↓
DedicatedLabJackMonitor (orchestration)
    ├─► LabJackDetectionService (hardware, stream mode, ±1-2ms)
    │   └─► LabJackConnectionManager (prevents conflicts)
    │
    ├─► VideoTimingService (video sync, frame numbers)
    │
    ├─► HILScreenshotService (captures, ground truth)
    │
    └─► WebSocket (real-time updates to frontend)

Database: detection_events (batch commits from detection service)
```

---

## Part 8: Migration Checklist

### Pre-Migration Testing

- [ ] Test detection service stream mode at 200 Hz
- [ ] Verify connection manager prevents conflicts
- [ ] Validate batch commits don't lose data
- [ ] Test multi-session concurrency
- [ ] Benchmark timing accuracy (should be ±1-2ms)

### Migration Steps

- [ ] Extract frame seeking from HIL monitor to utility
- [ ] Add frame seeking to dedicated monitor API
- [ ] Update API endpoints to use dedicated monitor only
- [ ] Remove direct HIL monitor endpoints
- [ ] Update frontend to use new endpoints
- [ ] Add integration tests for consolidated flow
- [ ] Update documentation

### Post-Migration Validation

- [ ] Verify 0 detection issue resolved
- [ ] Confirm sub-100ms latency validation works
- [ ] Test multi-video sequences
- [ ] Validate ground truth matching accuracy
- [ ] Check database performance under load
- [ ] Monitor for connection errors

---

## Conclusion

**The dedicated_labjack_monitor.py already does this correctly!**

**Root Issue**: HIL Monitor and Detection Service both trying to access LabJack hardware directly causes device conflicts (0 detections).

**Solution**: Use dedicated_labjack_monitor.py as main entry point:
- It calls Detection Service (proper hardware access)
- It adds video synchronization on top
- It already has all necessary features

**What to Fix**:
1. Ensure connection manager is always used
2. Remove any direct HIL monitor usage
3. Add frame seeking utility from HIL monitor
4. Keep T3 YOLO integration separate (optional feature)

**Result**: Best of both worlds with no conflicts.

---

**Document Status**: Complete Analysis
**Next Steps**: Implement migration plan Phase 1-4
**Expected Outcome**: Sub-100ms validation with full video sync and no device conflicts
