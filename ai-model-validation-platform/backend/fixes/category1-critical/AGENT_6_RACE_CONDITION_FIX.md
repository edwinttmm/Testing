# Agent #6: Sequence Start Race Condition Fix

## Mission
Fix race condition in `sequence_start_time` update using database-level atomic operations.

## Problem Analysis

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`

**Line 293-314:** Race condition in `notify_video_started()`

```python
# VULNERABLE CODE (Line 294-297):
if sequence.sequence_start_time is None:
    sequence.sequence_start_time = actual_start_timestamp
    sequence.status = SequenceStatus.RUNNING
    logger.info(f"Sequence {sequence_id} started at {actual_start_timestamp:.6f}")
```

**Race Condition Scenario:**
1. Video 1 starts → Thread A checks `sequence_start_time is None` → TRUE
2. Video 2 starts → Thread B checks `sequence_start_time is None` → TRUE (Thread A hasn't committed yet)
3. Thread A sets `sequence_start_time = 10.5`
4. Thread B sets `sequence_start_time = 20.0` → **OVERWRITES Thread A's value!**
5. Result: `sequence_start_time = 20.0` (should be 10.5)

**Impact:**
- All timing calculations corrupted
- Detections assigned to wrong videos
- Latency calculations incorrect

## Fix Implementation

### Solution: Database-Level Atomic CAS (Compare-And-Swap)

```python
# /home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py

def notify_video_started(
    self,
    sequence_id: str,
    video_id: str,
    actual_start_timestamp: float,
    db: Session
) -> bool:
    """
    Record when a video actually starts playing.

    CRITICAL FIX: Uses database-level atomic CAS to prevent race condition
    in sequence_start_time initialization.
    """
    try:
        sequence = self._get_sequence(sequence_id)

        # Validate video belongs to sequence
        if video_id not in sequence.video_ids:
            raise VideoSequenceOrchestratorError(f"Video {video_id} not in sequence {sequence_id}")

        # === CRITICAL FIX: Atomic Sequence Start Time Initialization ===
        #
        # BEFORE: In-memory check + update (vulnerable to race condition)
        # AFTER: Database-level atomic CAS operation
        #
        # This ensures ONLY ONE thread can set sequence_start_time, even if
        # multiple videos start simultaneously.

        sequence_initialized = False

        try:
            # Attempt atomic update using SQL UPDATE with WHERE clause
            from sqlalchemy import text, and_
            from models import VideoTestSequence as VideoTestSequenceModel

            # Atomic CAS: UPDATE ... WHERE sequence_start_time IS NULL
            # This will succeed for ONLY ONE thread
            update_result = db.execute(
                text("""
                    UPDATE video_test_sequences
                    SET sequence_start_time = :start_time,
                        status = 'running'
                    WHERE id = :sequence_id
                      AND sequence_start_time IS NULL
                """),
                {
                    'start_time': actual_start_timestamp,
                    'sequence_id': sequence_id
                }
            )

            rows_affected = update_result.rowcount
            db.commit()

            if rows_affected > 0:
                # THIS thread won the race - it initialized sequence_start_time
                sequence.sequence_start_time = actual_start_timestamp
                sequence.status = SequenceStatus.RUNNING
                sequence_initialized = True

                logger.info(
                    f"✅ ATOMIC INIT: Sequence {sequence_id} started at {actual_start_timestamp:.6f} "
                    f"(this thread won the CAS race)"
                )
            else:
                # ANOTHER thread already initialized sequence_start_time
                # Fetch the value that was set
                video_sequence_db = db.query(VideoTestSequenceModel).filter(
                    VideoTestSequenceModel.id == sequence_id
                ).first()

                if video_sequence_db and video_sequence_db.sequence_start_time:
                    sequence.sequence_start_time = video_sequence_db.sequence_start_time
                    sequence.status = SequenceStatus.RUNNING

                    logger.info(
                        f"ℹ️  ATOMIC SKIP: Sequence {sequence_id} already started at "
                        f"{sequence.sequence_start_time:.6f} (lost CAS race, using existing value)"
                    )
                else:
                    logger.error(f"❌ CRITICAL: CAS failed but no sequence_start_time found in DB!")
                    raise VideoSequenceOrchestratorError("Sequence start time initialization failed")

        except Exception as db_error:
            logger.error(f"❌ Atomic CAS failed: {db_error}")
            db.rollback()
            raise

        # Verify sequence_start_time is now set (either by this thread or another)
        if sequence.sequence_start_time is None:
            raise VideoSequenceOrchestratorError(
                f"Sequence start time not initialized after CAS operation"
            )

        # === Rest of function continues as normal ===

        # Calculate video play offset from sequence start
        video_play_offset_ms = (actual_start_timestamp - sequence.sequence_start_time) * 1000.0

        # Update video metadata
        metadata = sequence.video_metadata[video_id]
        metadata.video_start_time = actual_start_timestamp
        metadata.video_play_offset_ms = video_play_offset_ms

        # Update video result
        result = sequence.video_results[video_id]
        result.video_start_time = actual_start_timestamp
        result.video_play_offset_ms = video_play_offset_ms
        result.status = VideoStatus.PLAYING
        result.expected_detections = metadata.ground_truth_count

        # Update current video index
        sequence.current_video_index = sequence.video_ids.index(video_id)

        # Start video timing in timing service
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

        logger.info(f"Video started: {video_id}")
        logger.info(f"  Start time: {actual_start_timestamp:.6f}")
        logger.info(f"  Play offset: {video_play_offset_ms:.3f}ms")
        logger.info(f"  Expected detections: {metadata.ground_truth_count}")

        return True

    except Exception as e:
        logger.error(f"Failed to notify video started: {e}")
        return False
```

### Database Schema Requirements

Ensure `video_test_sequences` table has proper index:

```sql
-- Migration: Add index for atomic CAS performance
CREATE INDEX IF NOT EXISTS idx_vts_sequence_start_null
ON video_test_sequences(id)
WHERE sequence_start_time IS NULL;
```

## Testing Strategy

### Stress Test: Concurrent Video Starts

```python
# /home/rigade/Testing/ai-model-validation-platform/backend/tests/test_race_condition_fix.py

import pytest
import threading
import time
from services.video_sequence_orchestrator import get_video_sequence_orchestrator

class TestRaceConditionFix:

    def test_concurrent_video_starts_atomic_cas(self, test_db):
        """
        Simulate 3 videos starting simultaneously - only ONE should initialize
        sequence_start_time, all should see the same value.
        """
        orchestrator = get_video_sequence_orchestrator()

        # Create sequence with 3 videos
        sequence_id = orchestrator.start_sequence(
            project_id="test-project",
            video_ids=["video1", "video2", "video3"],
            max_latency_ms=100,
            db=test_db
        )

        # Shared results
        results = {
            'video1': {'start_time': None, 'offset_ms': None, 'error': None},
            'video2': {'start_time': None, 'offset_ms': None, 'error': None},
            'video3': {'start_time': None, 'offset_ms': None, 'error': None}
        }

        def start_video(video_id: str, start_timestamp: float):
            """Thread worker to start a video"""
            try:
                success = orchestrator.notify_video_started(
                    sequence_id=sequence_id,
                    video_id=video_id,
                    actual_start_timestamp=start_timestamp,
                    db=test_db
                )

                # Record the sequence_start_time this thread sees
                sequence = orchestrator._active_sequences[sequence_id]
                results[video_id]['start_time'] = sequence.sequence_start_time
                results[video_id]['offset_ms'] = sequence.video_metadata[video_id].video_play_offset_ms

            except Exception as e:
                results[video_id]['error'] = str(e)

        # Start all 3 videos SIMULTANEOUSLY at slightly different timestamps
        threads = []
        timestamps = [1000.0, 1000.1, 1000.2]

        for video_id, ts in zip(["video1", "video2", "video3"], timestamps):
            thread = threading.Thread(target=start_video, args=(video_id, ts))
            threads.append(thread)

        # Start all threads at once
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # VERIFICATION: All threads should see the SAME sequence_start_time
        start_times = [r['start_time'] for r in results.values() if r['start_time'] is not None]

        assert len(start_times) == 3, "All videos should have recorded a start_time"
        assert len(set(start_times)) == 1, f"Race condition detected! Different start times: {start_times}"

        # VERIFICATION: sequence_start_time should be the EARLIEST timestamp
        assert start_times[0] == 1000.0, f"Sequence should start at earliest time (1000.0), got {start_times[0]}"

        # VERIFICATION: Video offsets should be correct relative to sequence start
        assert results['video1']['offset_ms'] == 0.0, "Video1 offset should be 0ms"
        assert results['video2']['offset_ms'] == 100.0, "Video2 offset should be 100ms"
        assert results['video3']['offset_ms'] == 200.0, "Video3 offset should be 200ms"

        print("✅ Atomic CAS test PASSED - no race condition detected")

    def test_late_video_start_uses_existing_sequence_time(self, test_db):
        """
        When video starts AFTER sequence_start_time is initialized, it should
        use the existing value (not attempt to reinitialize).
        """
        orchestrator = get_video_sequence_orchestrator()

        sequence_id = orchestrator.start_sequence(
            project_id="test-project",
            video_ids=["video1", "video2"],
            max_latency_ms=100,
            db=test_db
        )

        # Start video1 first (initializes sequence_start_time)
        orchestrator.notify_video_started(
            sequence_id=sequence_id,
            video_id="video1",
            actual_start_timestamp=1000.0,
            db=test_db
        )

        sequence = orchestrator._active_sequences[sequence_id]
        first_start_time = sequence.sequence_start_time

        # Start video2 later (should use existing sequence_start_time)
        time.sleep(0.1)  # Small delay to simulate real-world scenario

        orchestrator.notify_video_started(
            sequence_id=sequence_id,
            video_id="video2",
            actual_start_timestamp=1005.0,  # 5 seconds later
            db=test_db
        )

        second_start_time = sequence.sequence_start_time

        # VERIFICATION: sequence_start_time should NOT have changed
        assert first_start_time == second_start_time, \
            f"Sequence start time changed from {first_start_time} to {second_start_time}!"

        assert second_start_time == 1000.0, "Sequence should still start at original time"

        # VERIFICATION: Video2 offset should be relative to original sequence start
        video2_offset = sequence.video_metadata["video2"].video_play_offset_ms
        assert video2_offset == 5000.0, f"Video2 offset should be 5000ms, got {video2_offset}ms"

        print("✅ Late video start test PASSED - sequence_start_time unchanged")
```

## Deployment Checklist
- [ ] Add database index for performance
- [ ] Deploy atomic CAS code to production
- [ ] Run stress test with 10 concurrent video starts
- [ ] Monitor logs for "ATOMIC INIT" vs "ATOMIC SKIP" messages
- [ ] Verify zero "sequence_start_time overwrite" errors

## Success Criteria
- [ ] Stress test with 100 concurrent starts shows zero race conditions
- [ ] All videos in sequence see identical `sequence_start_time`
- [ ] First video always initializes, subsequent videos skip
- [ ] No database deadlocks or timeout errors
