# Video Sequence Orchestrator Service

## Overview

The `VideoSequenceOrchestrator` service manages multi-video sequential testing for HIL (Hardware-in-the-Loop) validation. It coordinates video playback, timing synchronization, detection correlation, and per-video/sequence-level evaluation with **dynamic timing management** - no hardcoded assumptions.

## Architecture

### Key Principles

1. **Dynamic Timing**: All timing is event-driven based on actual video start/end notifications
2. **Detection Correlation**: LabjJack events are correlated to the correct video using timing ranges
3. **Per-Video Evaluation**: Each video is evaluated independently with its own metrics
4. **Sequence Aggregation**: Sequence-level metrics aggregate results from all videos
5. **No Hardcoded Values**: Video durations, FPS, and frame counts are loaded dynamically from database

### Core Components

```
VideoSequenceOrchestrator
├── Sequence Initialization
│   ├── Load video metadata dynamically
│   ├── Create VideoTestSequence container
│   └── Initialize per-video results
├── Timing Management
│   ├── Track sequence start time (first video)
│   ├── Record video start/end times
│   ├── Calculate video play offsets
│   └── Handle video delays/buffering
├── Detection Correlation
│   ├── Receive LabjJack detection events
│   ├── Determine which video was playing
│   ├── Calculate video-relative timestamps
│   └── Create VideoDetectionEvent
├── Per-Video Evaluation
│   ├── Compare detections vs ground truth
│   ├── Calculate latency metrics
│   ├── Determine pass/fail
│   └── Store SequenceVideoResult
└── Sequence Completion
    ├── Aggregate per-video metrics
    ├── Calculate sequence pass rate
    └── Finalize sequence status
```

## Data Structures

### VideoTestSequence

Container for complete sequence information:

```python
@dataclass
class VideoTestSequence:
    sequence_id: str
    project_id: str
    session_id: str

    # Configuration
    video_ids: List[str]
    max_latency_ms: float

    # Status
    status: SequenceStatus  # INITIALIZING, READY, RUNNING, COMPLETED, FAILED
    current_video_index: int

    # Dynamic timing
    sequence_start_time: Optional[float]  # Set when first video starts
    sequence_end_time: Optional[float]    # Set when last video ends

    # Per-video data
    video_metadata: Dict[str, VideoMetadata]
    video_results: Dict[str, SequenceVideoResult]

    # Aggregate metrics
    total_expected_detections: int
    total_detected: int
    total_missed: int
    sequence_pass_rate: float
```

### VideoMetadata

Dynamically loaded video information:

```python
@dataclass
class VideoMetadata:
    video_id: str
    filename: str
    duration: float          # From database
    fps: float              # From database
    frame_count: int        # Calculated: duration * fps
    ground_truth_count: int # From database query

    # Dynamic timing (set during playback)
    video_start_time: Optional[float]
    video_end_time: Optional[float]
    video_play_offset_ms: Optional[float]  # Offset from sequence start
```

### SequenceVideoResult

Per-video evaluation results:

```python
@dataclass
class SequenceVideoResult:
    video_id: str
    video_index: int
    status: VideoStatus  # PENDING, LOADING, PLAYING, COMPLETED, FAILED

    # Dynamic timing
    video_start_time: Optional[float]
    video_end_time: Optional[float]
    video_play_offset_ms: Optional[float]

    # Detection metrics
    expected_detections: int
    detected_count: int
    missed_detections: int
    false_positives: int

    # Latency metrics
    avg_latency_ms: Optional[float]
    max_latency_ms: Optional[float]
    min_latency_ms: Optional[float]
    latency_threshold_ms: float

    # Pass/fail evaluation
    passed: bool
    pass_rate: float
    failure_reason: Optional[str]
```

## API Methods

### 1. start_sequence

Initialize a new video test sequence.

```python
sequence_id = orchestrator.start_sequence(
    project_id="project-123",
    video_ids=["video-1", "video-2", "video-3"],
    max_latency_ms=100.0,
    db=db_session,
    session_id=None  # Optional, will create new if not provided
)
```

**Process:**
1. Validate all videos exist in database
2. Load video metadata dynamically (duration, fps, frame_count)
3. Query ground truth counts for each video
4. Create VideoTestSequence container
5. Initialize SequenceVideoResult for each video
6. Create or update TestSession in database

**Returns:** Sequence ID

**Raises:** `VideoSequenceOrchestratorError` if initialization fails

### 2. notify_video_started

Record when a video actually starts playing.

```python
success = orchestrator.notify_video_started(
    sequence_id="seq-123",
    video_id="video-1",
    actual_start_timestamp=time.time(),
    db=db_session
)
```

**Process:**
1. Initialize sequence_start_time on first video
2. Calculate video_play_offset_ms from sequence start
3. Update VideoMetadata with start time
4. Update SequenceVideoResult status to PLAYING
5. Start video timing in VideoTimingService
6. Update current_video_index

**Critical:** This establishes the timing reference for all subsequent detection correlation.

### 3. notify_video_ended

Record when a video ends and evaluate its results.

```python
success = orchestrator.notify_video_ended(
    sequence_id="seq-123",
    video_id="video-1",
    actual_end_timestamp=time.time(),
    db=db_session
)
```

**Process:**
1. Record video_end_time
2. Update SequenceVideoResult status to COMPLETED
3. Evaluate video results:
   - Query detection events for this video
   - Compare against ground truth
   - Calculate latency metrics
   - Determine pass/fail
4. Check if last video (finalize sequence if so)

### 4. process_detection_event

Process LabjJack detection event and correlate to correct video.

```python
detection_id = orchestrator.process_detection_event(
    sequence_id="seq-123",
    labjack_signal={
        'voltage': 3.3,
        'channel': 'AIN0'
    },
    sequence_timestamp=unix_timestamp,
    db=db_session
)
```

**Process:**
1. Determine which video was playing using timing ranges
2. Calculate video-relative timestamp
3. Calculate video frame number
4. Create DetectionEvent with:
   - video_id (correlated video)
   - video_relative_timestamp
   - video_frame_number
   - video_start_time (reference)
   - labjack signal data
5. Add detection to SequenceVideoResult

**Returns:** Detection event ID or None if correlation fails

### 5. get_sequence_status

Get current execution status.

```python
status = orchestrator.get_sequence_status("seq-123")

# Returns:
{
    "sequence_id": "seq-123",
    "status": "running",
    "current_video_index": 1,
    "total_videos": 3,
    "current_video_id": "video-2",
    "sequence_start_time": 1234567890.123,
    "total_expected_detections": 45,
    "total_detected": 12,
    "video_statuses": {
        "video-1": "completed",
        "video-2": "playing",
        "video-3": "pending"
    }
}
```

### 6. get_sequence_results

Get complete results for a sequence.

```python
results = orchestrator.get_sequence_results("seq-123", db_session)

# Returns:
{
    "sequence_id": "seq-123",
    "session_id": "session-456",
    "project_id": "project-789",
    "status": "completed",
    "video_count": 3,
    "max_latency_ms": 100.0,

    # Timing
    "sequence_start_time": 1234567890.123,
    "sequence_end_time": 1234567935.456,
    "total_duration_s": 45.333,

    # Aggregate metrics
    "total_expected_detections": 45,
    "total_detected": 43,
    "total_missed": 2,
    "sequence_pass_rate": 0.9556,

    # Per-video results
    "video_results": [
        {
            "video_id": "video-1",
            "video_index": 0,
            "filename": "test1.mp4",
            "status": "completed",
            "passed": true,
            "pass_rate": 1.0,
            "expected_detections": 15,
            "detected_count": 15,
            "missed_detections": 0,
            "avg_latency_ms": 45.2,
            "max_latency_ms": 67.8,
            "video_start_time": 1234567890.123,
            "video_end_time": 1234567900.123,
            "video_play_offset_ms": 0.0
        },
        # ... more videos
    ]
}
```

## Dynamic Timing Flow

### Example: 3-Video Sequence

```
Timeline (seconds):
0.0  - Sequence initialized
2.3  - Video 1 starts (sequence_start_time = 2.3)
       video_play_offset_ms = 0
12.5 - Video 1 ends
13.1 - Video 2 starts
       video_play_offset_ms = (13.1 - 2.3) * 1000 = 10,800ms
28.4 - Video 2 ends
29.0 - Video 3 starts
       video_play_offset_ms = (29.0 - 2.3) * 1000 = 26,700ms
45.2 - Video 3 ends (sequence_end_time = 45.2)
       total_duration_s = 45.2 - 2.3 = 42.9s
```

### Detection Correlation Example

```python
# Detection arrives at sequence timestamp = 25.5
# Need to determine: which video was playing?

Video 1: start=2.3, end=12.5   -> 25.5 not in range
Video 2: start=13.1, end=28.4  -> 25.5 IS in range! ✓
Video 3: start=29.0, end=45.2  -> 25.5 not in range

# Detection belongs to Video 2
video_relative_timestamp = 25.5 - 13.1 = 12.4 seconds
video_frame_number = int(12.4 * 30.0) = 372  # Assuming 30 FPS
```

## Error Handling

### VideoSequenceOrchestratorError

Custom exception raised for orchestration errors:

```python
try:
    sequence_id = orchestrator.start_sequence(...)
except VideoSequenceOrchestratorError as e:
    logger.error(f"Orchestrator error: {e}")
    # Handle error
```

### Common Error Scenarios

1. **Invalid Video**: Video ID not found in database
2. **Video Not in Sequence**: Attempting to start/end video not in sequence
3. **Sequence Not Found**: Attempting to access non-existent sequence
4. **Database Errors**: SQLAlchemy exceptions during persistence
5. **Timing Errors**: Video start time not set when needed

## Integration with Other Services

### VideoTimingService

Used for high-precision video timing:

```python
self._timing_service.start_video_timing(
    session_id=sequence.session_id,
    video_id=video_id,
    db=db,
    video_metadata={
        'fps': metadata.fps,
        'duration': metadata.duration,
        'frame_count': metadata.frame_count
    }
)
```

### Database Models

Persists data to:
- `TestSession`: Overall test session
- `VideoTestSequence`: Sequence container
- `SequenceVideoResult`: Per-video results
- `DetectionEvent`: Individual detection events

## Usage Example

```python
from services.video_sequence_orchestrator import get_video_sequence_orchestrator

# Initialize
orchestrator = get_video_sequence_orchestrator()

# Start sequence
sequence_id = orchestrator.start_sequence(
    project_id="test-project",
    video_ids=["vid1", "vid2", "vid3"],
    max_latency_ms=100.0,
    db=db
)

# Video 1 starts
orchestrator.notify_video_started(
    sequence_id=sequence_id,
    video_id="vid1",
    actual_start_timestamp=time.time(),
    db=db
)

# Process detections
for detection in labjack_detections:
    orchestrator.process_detection_event(
        sequence_id=sequence_id,
        labjack_signal=detection['signal'],
        sequence_timestamp=detection['timestamp'],
        db=db
    )

# Video 1 ends (automatic evaluation)
orchestrator.notify_video_ended(
    sequence_id=sequence_id,
    video_id="vid1",
    actual_end_timestamp=time.time(),
    db=db
)

# Continue for remaining videos...

# Get final results
results = orchestrator.get_sequence_results(sequence_id, db)
print(f"Sequence pass rate: {results['sequence_pass_rate']:.2%}")
```

## Testing

Comprehensive unit tests in `tests/test_video_sequence_orchestrator.py`:

```bash
pytest backend/tests/test_video_sequence_orchestrator.py -v
```

Tests cover:
- Sequence initialization
- Video timing notifications
- Detection event processing
- Video-to-detection correlation
- Per-video evaluation
- Sequence aggregation
- Error handling

## Performance Considerations

1. **In-Memory Storage**: Active sequences stored in memory for fast access
2. **Database Queries**: Optimized queries for video metadata and ground truth
3. **Timing Precision**: Uses VideoTimingService for sub-millisecond accuracy
4. **Batch Operations**: Evaluations performed per-video, not per-detection

## Future Enhancements

1. **Parallel Video Processing**: Support concurrent video analysis
2. **Partial Sequence Recovery**: Resume from interrupted sequences
3. **Advanced Correlation**: Support frame-based correlation methods
4. **Real-time Streaming**: WebSocket updates for sequence progress
5. **Historical Analysis**: Query past sequence executions

## Troubleshooting

### No Detections Correlated

**Problem**: Detections not being assigned to any video

**Solutions:**
- Verify video start times are being set correctly
- Check detection timestamps are within video time ranges
- Ensure sequence_start_time is initialized

### Incorrect Video Assignment

**Problem**: Detections assigned to wrong video

**Solutions:**
- Verify video_play_offset_ms calculations
- Check for overlapping video time ranges
- Ensure video end times are accurate

### Missing Ground Truth

**Problem**: Expected detections count is 0

**Solutions:**
- Verify ground truth objects exist in database
- Check ground truth video_id matches sequence video_id
- Ensure ground truth generation completed successfully

## References

- Video Timing Service: `services/video_timing_service.py`
- Database Models: `models.py` (VideoTestSequence, SequenceVideoResult)
- Schemas: `schemas.py` (Multi-video sequence schemas)
- Test Suite: `tests/test_video_sequence_orchestrator.py`