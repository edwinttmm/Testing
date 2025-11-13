# Video Sequence Orchestrator - Quick Start Guide

## Installation

The orchestrator is ready to use - no additional installation required.

```python
from services.video_sequence_orchestrator import get_video_sequence_orchestrator
```

## Basic Usage

### 1. Initialize Orchestrator

```python
from services.video_sequence_orchestrator import get_video_sequence_orchestrator
from database import get_db

# Get singleton instance
orchestrator = get_video_sequence_orchestrator()

# Get database session
db = next(get_db())
```

### 2. Start a Sequence

```python
# Define your video sequence
video_ids = [
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002",
    "550e8400-e29b-41d4-a716-446655440003"
]

# Start the sequence
sequence_id = orchestrator.start_sequence(
    project_id="my-project-id",
    video_ids=video_ids,
    max_latency_ms=100.0,  # 100ms latency threshold
    db=db
)

print(f"Sequence started: {sequence_id}")
```

### 3. Notify Video Started

When your video player starts a video:

```python
import time

# Get actual start timestamp
start_time = time.time()

# Notify orchestrator
success = orchestrator.notify_video_started(
    sequence_id=sequence_id,
    video_id=video_ids[0],  # First video
    actual_start_timestamp=start_time,
    db=db
)

if success:
    print(f"Video {video_ids[0]} started at {start_time}")
```

### 4. Process Detection Events

When LabjJack detects a signal:

```python
# Detection event from LabjJack
detection_timestamp = time.time()
labjack_signal = {
    'voltage': 3.3,
    'channel': 'AIN0'
}

# Process detection
detection_id = orchestrator.process_detection_event(
    sequence_id=sequence_id,
    labjack_signal=labjack_signal,
    sequence_timestamp=detection_timestamp,
    db=db
)

if detection_id:
    print(f"Detection processed: {detection_id}")
```

### 5. Notify Video Ended

When video playback completes:

```python
# Get actual end timestamp
end_time = time.time()

# Notify orchestrator (triggers automatic evaluation)
success = orchestrator.notify_video_ended(
    sequence_id=sequence_id,
    video_id=video_ids[0],
    actual_end_timestamp=end_time,
    db=db
)

if success:
    print(f"Video {video_ids[0]} completed and evaluated")
```

### 6. Check Status

Get real-time status:

```python
status = orchestrator.get_sequence_status(sequence_id)

print(f"Status: {status['status']}")
print(f"Current video: {status['current_video_index'] + 1}/{status['total_videos']}")
print(f"Detections: {status['total_detected']}/{status['total_expected_detections']}")
```

### 7. Get Results

After all videos complete:

```python
results = orchestrator.get_sequence_results(sequence_id, db)

print(f"\n=== Sequence Results ===")
print(f"Status: {results['status']}")
print(f"Pass Rate: {results['sequence_pass_rate']:.2%}")
print(f"Total Detected: {results['total_detected']}/{results['total_expected_detections']}")

# Per-video breakdown
for video_result in results['video_results']:
    print(f"\nVideo: {video_result['filename']}")
    print(f"  Status: {video_result['status']}")
    print(f"  Passed: {video_result['passed']}")
    print(f"  Pass Rate: {video_result['pass_rate']:.2%}")
    print(f"  Detected: {video_result['detected_count']}/{video_result['expected_detections']}")
    if video_result['avg_latency_ms']:
        print(f"  Avg Latency: {video_result['avg_latency_ms']:.2f}ms")
```

## Complete Example

```python
from services.video_sequence_orchestrator import get_video_sequence_orchestrator
from database import get_db
import time

def run_video_sequence_test(project_id, video_ids, max_latency_ms=100.0):
    """
    Run a complete video sequence test.

    Args:
        project_id: Project identifier
        video_ids: List of video IDs in playback order
        max_latency_ms: Maximum acceptable latency

    Returns:
        Dictionary with sequence results
    """
    # Initialize
    orchestrator = get_video_sequence_orchestrator()
    db = next(get_db())

    try:
        # Start sequence
        print("Starting video sequence test...")
        sequence_id = orchestrator.start_sequence(
            project_id=project_id,
            video_ids=video_ids,
            max_latency_ms=max_latency_ms,
            db=db
        )
        print(f"Sequence ID: {sequence_id}")

        # Process each video
        for idx, video_id in enumerate(video_ids):
            print(f"\n--- Video {idx + 1}/{len(video_ids)}: {video_id} ---")

            # Start video
            start_time = time.time()
            orchestrator.notify_video_started(
                sequence_id=sequence_id,
                video_id=video_id,
                actual_start_timestamp=start_time,
                db=db
            )
            print(f"Video started at {start_time:.6f}")

            # Simulate video playback and detection events
            # In real use, these would come from video player and LabjJack

            # Example: Process detection after 2 seconds
            time.sleep(2.0)
            detection_time = time.time()
            orchestrator.process_detection_event(
                sequence_id=sequence_id,
                labjack_signal={'voltage': 3.3, 'channel': 'AIN0'},
                sequence_timestamp=detection_time,
                db=db
            )
            print(f"Detection processed at {detection_time:.6f}")

            # Simulate rest of video playback
            time.sleep(3.0)

            # End video
            end_time = time.time()
            orchestrator.notify_video_ended(
                sequence_id=sequence_id,
                video_id=video_id,
                actual_end_timestamp=end_time,
                db=db
            )
            print(f"Video ended at {end_time:.6f}")

            # Check status
            status = orchestrator.get_sequence_status(sequence_id)
            print(f"Status: {status['status']}, Progress: {idx + 1}/{len(video_ids)}")

        # Get final results
        print("\n=== Final Results ===")
        results = orchestrator.get_sequence_results(sequence_id, db)
        print(f"Sequence Status: {results['status']}")
        print(f"Overall Pass Rate: {results['sequence_pass_rate']:.2%}")
        print(f"Total Duration: {results['total_duration_s']:.2f}s")

        return results

    finally:
        db.close()

# Example usage
if __name__ == "__main__":
    results = run_video_sequence_test(
        project_id="test-project",
        video_ids=[
            "video-id-1",
            "video-id-2",
            "video-id-3"
        ],
        max_latency_ms=100.0
    )
```

## Common Patterns

### Pattern 1: Real-time Status Updates

```python
def monitor_sequence_progress(sequence_id):
    """Monitor sequence progress in real-time"""
    orchestrator = get_video_sequence_orchestrator()

    while True:
        status = orchestrator.get_sequence_status(sequence_id)

        if status['status'] in ['completed', 'failed', 'cancelled']:
            break

        print(f"Video {status['current_video_index'] + 1}/{status['total_videos']}")
        print(f"Detected: {status['total_detected']}/{status['total_expected_detections']}")

        time.sleep(1.0)  # Update every second
```

### Pattern 2: Batch Detection Processing

```python
def process_detection_batch(sequence_id, detections, db):
    """Process multiple detections efficiently"""
    orchestrator = get_video_sequence_orchestrator()

    processed_count = 0
    for detection in detections:
        detection_id = orchestrator.process_detection_event(
            sequence_id=sequence_id,
            labjack_signal=detection['signal'],
            sequence_timestamp=detection['timestamp'],
            db=db
        )
        if detection_id:
            processed_count += 1

    return processed_count
```

### Pattern 3: Error Recovery

```python
def safe_video_transition(sequence_id, video_id, db):
    """Safely transition to next video with error handling"""
    orchestrator = get_video_sequence_orchestrator()

    try:
        # Try to end current video
        success = orchestrator.notify_video_ended(
            sequence_id=sequence_id,
            video_id=video_id,
            actual_end_timestamp=time.time(),
            db=db
        )

        if not success:
            logging.warning(f"Failed to end video {video_id}")
            return False

        # Start next video
        next_video_id = get_next_video_id(sequence_id)
        if next_video_id:
            success = orchestrator.notify_video_started(
                sequence_id=sequence_id,
                video_id=next_video_id,
                actual_start_timestamp=time.time(),
                db=db
            )

        return success

    except Exception as e:
        logging.error(f"Error during video transition: {e}")
        return False
```

## WebSocket Integration Example

```python
from fastapi import WebSocket

async def websocket_sequence_updates(
    websocket: WebSocket,
    sequence_id: str
):
    """Send real-time sequence updates via WebSocket"""
    orchestrator = get_video_sequence_orchestrator()

    await websocket.accept()

    try:
        while True:
            # Get current status
            status = orchestrator.get_sequence_status(sequence_id)

            # Send update
            await websocket.send_json({
                'type': 'sequence_status',
                'data': status
            })

            # Check if completed
            if status['status'] in ['completed', 'failed']:
                # Send final results
                results = orchestrator.get_sequence_results(sequence_id, db)
                await websocket.send_json({
                    'type': 'sequence_results',
                    'data': results
                })
                break

            # Wait before next update
            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        logging.info(f"WebSocket disconnected for sequence {sequence_id}")
```

## FastAPI Endpoint Examples

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from services.video_sequence_orchestrator import get_video_sequence_orchestrator

router = APIRouter(prefix="/api/sequences", tags=["Video Sequences"])

@router.post("/start")
def start_sequence(
    project_id: str,
    video_ids: List[str],
    max_latency_ms: float = 100.0,
    db: Session = Depends(get_db)
):
    """Start a new video sequence"""
    orchestrator = get_video_sequence_orchestrator()

    try:
        sequence_id = orchestrator.start_sequence(
            project_id=project_id,
            video_ids=video_ids,
            max_latency_ms=max_latency_ms,
            db=db
        )
        return {"sequence_id": sequence_id, "status": "started"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{sequence_id}/video-started")
def notify_video_started(
    sequence_id: str,
    video_id: str,
    timestamp: float,
    db: Session = Depends(get_db)
):
    """Notify that a video has started"""
    orchestrator = get_video_sequence_orchestrator()

    success = orchestrator.notify_video_started(
        sequence_id=sequence_id,
        video_id=video_id,
        actual_start_timestamp=timestamp,
        db=db
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to start video")

    return {"status": "success"}

@router.get("/{sequence_id}/status")
def get_sequence_status(sequence_id: str):
    """Get current sequence status"""
    orchestrator = get_video_sequence_orchestrator()
    return orchestrator.get_sequence_status(sequence_id)

@router.get("/{sequence_id}/results")
def get_sequence_results(
    sequence_id: str,
    db: Session = Depends(get_db)
):
    """Get complete sequence results"""
    orchestrator = get_video_sequence_orchestrator()
    return orchestrator.get_sequence_results(sequence_id, db)
```

## Troubleshooting

### Issue: Detections Not Being Correlated

**Problem**: Detection events not assigned to any video

**Solution**:
```python
# Check sequence status
status = orchestrator.get_sequence_status(sequence_id)
print(f"Sequence start time: {status['sequence_start_time']}")

# Verify video start times
sequence = orchestrator._active_sequences[sequence_id]
for video_id, metadata in sequence.video_metadata.items():
    print(f"Video {video_id}: start={metadata.video_start_time}")
```

### Issue: Incorrect Video Assignment

**Problem**: Detections assigned to wrong video

**Solution**:
```python
# Check video timing ranges
for video_id in sequence.video_ids:
    metadata = sequence.video_metadata[video_id]
    print(f"Video {video_id}:")
    print(f"  Start: {metadata.video_start_time}")
    print(f"  End: {metadata.video_end_time}")
    print(f"  Offset: {metadata.video_play_offset_ms}ms")
```

## Next Steps

1. **API Integration**: Add FastAPI endpoints (examples above)
2. **Frontend Integration**: Update video player to send notifications
3. **WebSocket Updates**: Implement real-time status streaming
4. **Error Handling**: Add comprehensive error recovery
5. **Testing**: Run end-to-end integration tests

## Resources

- Complete Documentation: `VIDEO_SEQUENCE_ORCHESTRATOR.md`
- Implementation Summary: `IMPLEMENTATION_SUMMARY.md`
- Unit Tests: `tests/test_video_sequence_orchestrator.py`
- Service Code: `services/video_sequence_orchestrator.py`