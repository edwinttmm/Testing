# Timing Fixes - Implementation Guide

**Date**: 2025-11-24
**Estimated Total Time**: 5-6 hours
**Risk Level**: LOW (changes are additive and localized)

---

## Implementation Order

```
Priority    Fix                          File                            Time    Risk
────────────────────────────────────────────────────────────────────────────────────
P0          Video Start Time Lookup      video_timing_service.py         2h      LOW
P0          Frame-Based Calculation      timing_synchronization_...py    1h      LOW
P1          Remove Clamping              latency_decomposition_...py     0.5h    LOW
P1          Timestamp Validation         timing_validation.py (NEW)      2h      LOW
────────────────────────────────────────────────────────────────────────────────────
TOTAL                                                                    5.5h    LOW
```

---

## Fix #1: Correct Video Start Time for Sequential Videos

### **File**: `backend/services/video_timing_service.py`

### **Step 1: Add new method** (add after line 300)

```python
def get_video_start_time_for_detection(
    self,
    session_id: str,
    detection_timestamp: float,
    db: Session
) -> float:
    """
    Get the correct video start time for a detection.
    Handles sequential videos correctly by finding which video contains the detection.

    Args:
        session_id: Test session identifier
        detection_timestamp: Unix epoch timestamp of detection
        db: Database session

    Returns:
        Correct video start time for the video containing this detection

    Raises:
        VideoTimingError: If session or videos not found
    """
    try:
        with self._lock:
            # Import here to avoid circular dependency
            from models import VideoTestSequence, TestSession

            # Query all videos in this session, ordered by start time
            videos = db.query(VideoTestSequence)\
                .filter(VideoTestSequence.session_id == session_id)\
                .order_by(VideoTestSequence.start_time)\
                .all()

            if not videos:
                # No video sequence data, fallback to session start
                logger.warning(f"No VideoTestSequence found for session {session_id}, using session start")
                session = db.query(TestSession).filter(TestSession.id == session_id).first()
                if session and session.labjack_start_time:
                    return session.labjack_start_time
                raise VideoTimingError(f"No timing data found for session {session_id}")

            # Find which video window contains this detection
            for i, video in enumerate(videos):
                video_start = video.start_time
                video_end = video_start + video.duration

                if video_start <= detection_timestamp < video_end:
                    logger.debug(
                        f"Detection at {detection_timestamp:.6f} belongs to video {i+1} "
                        f"(start: {video_start:.6f}, end: {video_end:.6f})"
                    )
                    return video.start_time

            # Detection is after all videos (post-roll grace period)
            # Use last video's start time
            last_video = videos[-1]
            last_video_end = last_video.start_time + last_video.duration
            logger.warning(
                f"Detection at {detection_timestamp:.6f} is after all videos "
                f"(last video ends at {last_video_end:.6f}). "
                f"Using last video start time: {last_video.start_time:.6f}"
            )
            return last_video.start_time

    except Exception as e:
        logger.error(f"Failed to get video start time for detection: {e}")
        # Fallback to session start as last resort
        try:
            from models import TestSession
            session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if session and session.labjack_start_time:
                return session.labjack_start_time
        except Exception:
            pass
        raise VideoTimingError(f"Could not determine video start time: {e}")
```

### **Step 2: Update calculate_corrected_latency call**

**File**: `backend/services/timing_synchronization_calculator.py`

**Find**: Line 214-220 (current code)

```python
# Use video-specific start time if provided, otherwise fall back to labjack_start_time
if video_start_time is not None:
    video_start_system_time = video_start_time
    logger.debug(f"Using per-video start time: {video_start_system_time}")
else:
    # Fallback to labjack_start_time for backward compatibility
    video_start_system_time = labjack_start_time
    logger.debug(f"Using labjack_start_time (fallback): {video_start_system_time}")
    logger.warning(f"No video_start_time provided for detection {detection_id}, using labjack_start_time as fallback")
```

**Replace with**:

```python
# CRITICAL FIX: Get correct video start time for sequential videos
# Use video timing service to find which video contains this detection
if video_start_time is not None:
    # Explicit video start time provided (trusted)
    video_start_system_time = video_start_time
    logger.debug(f"Using provided video start time: {video_start_system_time:.6f}")
else:
    # Query database to find correct video start time
    try:
        from services.video_timing_service import VideoTimingService
        from database import get_db

        # Get database session
        db = next(get_db())
        timing_service = VideoTimingService()

        # Find correct video start time for this detection
        video_start_system_time = timing_service.get_video_start_time_for_detection(
            session_id=session_id,
            detection_timestamp=detection_system_time,
            db=db
        )
        logger.info(
            f"✓ Found correct video start time for detection {detection_id}: "
            f"{video_start_system_time:.6f} (vs session start: {labjack_start_time:.6f}, "
            f"offset: {video_start_system_time - labjack_start_time:.3f}s)"
        )
    except Exception as e:
        # Fallback to session start if lookup fails
        video_start_system_time = labjack_start_time
        logger.warning(
            f"Could not lookup video start time for detection {detection_id}: {e}. "
            f"Falling back to session start: {labjack_start_time:.6f}"
        )
```

### **Step 3: Add test**

**File**: `backend/tests/test_timing_fixes.py` (NEW FILE)

```python
"""
Tests for timing synchronization fixes.
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from services.video_timing_service import VideoTimingService
from services.timing_synchronization_calculator import TimingSynchronizationCalculator
from models import TestSession, VideoTestSequence
from database import get_db


class TestSequentialVideoTiming:
    """Test correct video start time handling for sequential videos."""

    def test_get_video_start_time_for_detection_video1(self, db: Session):
        """Test detection in first video gets video 1 start time."""
        # Setup: Create session with 2 sequential videos
        session_start = datetime.now(timezone.utc).timestamp()

        session = TestSession(
            id="test_session_1",
            labjack_start_time=session_start,
            status="in_progress"
        )
        db.add(session)

        video1 = VideoTestSequence(
            id="video_1",
            session_id="test_session_1",
            start_time=session_start,  # Starts at t=0
            duration=5.04,
            sequence_number=0
        )
        video2 = VideoTestSequence(
            id="video_2",
            session_id="test_session_1",
            start_time=session_start + 5.04,  # Starts at t=5.04s
            duration=5.04,
            sequence_number=1
        )
        db.add(video1)
        db.add(video2)
        db.commit()

        # Test: Detection at t=2.5s (in video 1)
        timing_service = VideoTimingService()
        detection_time = session_start + 2.5

        video_start = timing_service.get_video_start_time_for_detection(
            session_id="test_session_1",
            detection_timestamp=detection_time,
            db=db
        )

        # Assert: Should use video 1 start time
        assert video_start == session_start, \
            f"Expected video 1 start {session_start}, got {video_start}"

    def test_get_video_start_time_for_detection_video2(self, db: Session):
        """Test detection in second video gets video 2 start time (NOT video 1)."""
        # Setup: Create session with 2 sequential videos
        session_start = datetime.now(timezone.utc).timestamp()

        session = TestSession(
            id="test_session_2",
            labjack_start_time=session_start,
            status="in_progress"
        )
        db.add(session)

        video1 = VideoTestSequence(
            id="video_1",
            session_id="test_session_2",
            start_time=session_start,
            duration=5.04,
            sequence_number=0
        )
        video2 = VideoTestSequence(
            id="video_2",
            session_id="test_session_2",
            start_time=session_start + 5.04,  # Starts at t=5.04s
            duration=5.04,
            sequence_number=1
        )
        db.add(video1)
        db.add(video2)
        db.commit()

        # Test: Detection at t=7.5s (in video 2)
        timing_service = VideoTimingService()
        detection_time = session_start + 7.5

        video_start = timing_service.get_video_start_time_for_detection(
            session_id="test_session_2",
            detection_timestamp=detection_time,
            db=db
        )

        # Assert: Should use video 2 start time (NOT video 1)
        expected_start = session_start + 5.04
        assert abs(video_start - expected_start) < 0.001, \
            f"Expected video 2 start {expected_start}, got {video_start}"

    def test_post_roll_detection_uses_last_video(self, db: Session):
        """Test detection after all videos uses last video start time."""
        # Setup
        session_start = datetime.now(timezone.utc).timestamp()

        session = TestSession(
            id="test_session_3",
            labjack_start_time=session_start,
            status="in_progress"
        )
        db.add(session)

        video1 = VideoTestSequence(
            id="video_1",
            session_id="test_session_3",
            start_time=session_start,
            duration=5.04,
            sequence_number=0
        )
        video2 = VideoTestSequence(
            id="video_2",
            session_id="test_session_3",
            start_time=session_start + 5.04,
            duration=5.04,
            sequence_number=1
        )
        db.add(video1)
        db.add(video2)
        db.commit()

        # Test: Detection at t=12s (after both videos end at 10.08s)
        timing_service = VideoTimingService()
        detection_time = session_start + 12.0

        video_start = timing_service.get_video_start_time_for_detection(
            session_id="test_session_3",
            detection_timestamp=detection_time,
            db=db
        )

        # Assert: Should use video 2 start time (last video)
        expected_start = session_start + 5.04
        assert abs(video_start - expected_start) < 0.001, \
            f"Post-roll detection should use last video start {expected_start}, got {video_start}"
```

---

## Fix #2: Frame-Based Latency Calculation

### **File**: `backend/services/timing_synchronization_calculator.py`

### **Step 1: Add frame-based calculation method** (add after line 157)

```python
def calculate_latency_from_frames(
    self,
    detection_frame: int,
    gt_frame: int,
    fps: float,
    allow_negative: bool = False
) -> float:
    """
    Calculate latency using frame numbers (reliable, not affected by timestamp issues).

    This is the PRIMARY latency calculation method because:
    - Frame numbers are directly measured (ground truth)
    - Not affected by Unix epoch / video-relative time domain confusion
    - Frame rate is known and stable (from video metadata)

    Args:
        detection_frame: Frame number where detection occurred
        gt_frame: Frame number of ground truth event
        fps: Video frame rate (frames per second)
        allow_negative: Allow negative latencies (detection before GT)

    Returns:
        Latency in milliseconds

    Raises:
        ValueError: If negative latency and not allowed
    """
    if gt_frame > detection_frame:
        error_msg = (
            f"GT frame {gt_frame} is after detection frame {detection_frame}. "
            f"This indicates detection BEFORE ground truth event."
        )
        if not allow_negative:
            logger.error(error_msg)
            raise ValueError(error_msg)
        else:
            logger.warning(error_msg + " (allowed by caller)")

    frame_diff = detection_frame - gt_frame
    latency_seconds = frame_diff / fps
    latency_ms = latency_seconds * 1000.0

    logger.info(
        f"Frame-based latency: {frame_diff} frames @ {fps:.2f}fps = "
        f"{latency_ms:.3f}ms ({latency_seconds:.3f}s)"
    )

    # Sanity check: latency should be reasonable (<60 seconds for test videos)
    if abs(latency_ms) > 60_000:
        logger.warning(
            f"Frame-based latency {latency_ms:.1f}ms seems unrealistic. "
            f"Check frame numbers and fps: detection_frame={detection_frame}, "
            f"gt_frame={gt_frame}, fps={fps}"
        )

    return latency_ms
```

### **Step 2: Update calculate_corrected_latency to use frames first**

**Find**: Line 275-282 (current calculation)

```python
# Apparent latency = total time from LabJack start to detection
logger.debug(f"detection_system_time = {detection_system_time}, type = {type(detection_system_time)}")
logger.debug(f"About to calculate apparent_latency_ms = ({detection_system_time} - {labjack_start_time}) * 1000.0")
apparent_latency_ms = (detection_system_time - labjack_start_time) * 1000.0
logger.debug(f"apparent_latency_ms = {apparent_latency_ms}")

# CORRECT CALCULATION (after Fix #1 applied)
# Real latency = detection_time - ground_truth_event_system_time
# Now uses proper Unix epoch timestamps for both detection_system_time and gt_system_time
logger.debug(f"About to calculate real_latency_ms = ({detection_system_time} - {gt_system_time}) * 1000.0")
real_latency_ms = (detection_system_time - gt_system_time) * 1000.0
logger.debug(f"real_latency_ms = {real_latency_ms}")
```

**Replace with**:

```python
# CRITICAL FIX #2: Use frame-based calculation as PRIMARY method
# Frame numbers are ground truth, timestamps can have domain confusion

# Calculate video frame number for detection
fps = video_timing_metadata.fps if video_timing_metadata and video_timing_metadata.fps > 0 else 30.0
video_relative_timestamp = detection_system_time - video_start_system_time
detection_frame = int(video_relative_timestamp * fps)

# Try frame-based calculation first (PRIMARY METHOD)
if ground_truth_frame is not None and detection_frame is not None:
    try:
        real_latency_ms = self.calculate_latency_from_frames(
            detection_frame=detection_frame,
            gt_frame=ground_truth_frame,
            fps=fps,
            allow_negative=False
        )
        logger.info(f"✓ Using frame-based latency (primary method): {real_latency_ms:.3f}ms")

        # Calculate apparent latency for reporting
        apparent_latency_ms = (detection_system_time - labjack_start_time) * 1000.0

    except ValueError as e:
        # Frame-based failed (negative latency or invalid frames)
        logger.warning(f"Frame-based calculation failed: {e}. Falling back to time-based.")

        # Fallback to time-based (SECONDARY METHOD)
        apparent_latency_ms = (detection_system_time - labjack_start_time) * 1000.0
        gt_system_time = video_start_system_time + ground_truth_video_time
        real_latency_ms = (detection_system_time - gt_system_time) * 1000.0

        logger.warning(
            f"⚠️ Using time-based latency (fallback - may be inaccurate): "
            f"apparent={apparent_latency_ms:.1f}ms, real={real_latency_ms:.1f}ms"
        )
else:
    # No frame data available, must use time-based
    logger.warning("No frame data available, using time-based latency calculation")

    apparent_latency_ms = (detection_system_time - labjack_start_time) * 1000.0
    gt_system_time = video_start_system_time + ground_truth_video_time
    real_latency_ms = (detection_system_time - gt_system_time) * 1000.0

    logger.info(
        f"Time-based latency: apparent={apparent_latency_ms:.1f}ms, "
        f"real={real_latency_ms:.1f}ms"
    )
```

---

## Fix #3: Remove Misleading Clamping

### **File**: `backend/services/latency_decomposition_service.py`

### **Find**: Line 391-394

```python
if camera_latency_ns > camera_latency_bounds_ns[1]:
    # Camera latency exceeds expected bounds, some overhead is unaccounted
    unknown_overhead_ns = camera_latency_ns - camera_latency_bounds_ns[1]
    camera_latency_ns = camera_latency_bounds_ns[1]
```

### **Replace with**:

```python
if camera_latency_ns > camera_latency_bounds_ns[1]:
    # Camera latency exceeds expected bounds
    # This indicates INCORRECT TIMESTAMP CALCULATION, not camera issues
    logger.error(
        f"❌ TIMESTAMP VALIDATION ERROR: "
        f"Camera latency {camera_latency_ns/1e6:.1f}ms exceeds expected bounds "
        f"({camera_latency_bounds_ns[1]/1e6:.1f}ms max). "
        f"This indicates incorrect timestamp calculation upstream, not camera performance issues. "
        f"Total input latency: {total_latency_ms:.1f}ms, "
        f"Overhead: {total_overhead_ns/1e6:.1f}ms"
    )

    # Return INVALID result instead of hiding the problem
    return LatencyDecomposition(
        session_id=session_id,
        detection_id=detection_id,
        total_latency_ms=total_latency_ms,
        camera_latency_ms=0.0,
        system_baseline_ms=0.0,
        processing_overhead_ms=0.0,
        network_overhead_ms=0.0,
        sync_overhead_ms=0.0,
        unknown_overhead_ms=total_latency_ms,
        decomposition_confidence=0.0,
        measurement_accuracy_ns=0.0,
        validation_status="INVALID_INPUT_TIMESTAMPS",
        calculation_timestamp=datetime.now(timezone.utc),
        baseline_profile_used=baseline.profile_timestamp.isoformat() if baseline else "N/A",
        methodology_version="2.0_validation_enforced"
    )
```

---

## Fix #4: Add Timestamp Validation

### **File**: `backend/services/timing_validation.py` (NEW FILE)

Create complete new file (see timing-root-cause-summary.md for full implementation).

### **Then update timing_synchronization_calculator.py**:

Add import at top:
```python
from services.timing_validation import validate_timestamp, TimestampValidationResult
```

Add validation at line 230 (before any calculations):
```python
# CRITICAL: Validate timestamps before calculations
current_time = time.time()

# Validate detection timestamp
det_validation = validate_timestamp(
    detection_system_time,
    "Detection",
    labjack_start_time,
    max_age_seconds=86400,  # 24 hours
    max_span_seconds=600     # 10 minutes for test videos
)
if not det_validation.is_valid:
    raise ValueError(
        f"Invalid detection timestamp for {detection_id}: "
        f"{det_validation.error_message}"
    )

# Validate LabJack start timestamp
lj_validation = validate_timestamp(
    labjack_start_time,
    "LabJack start",
    current_time,
    max_age_seconds=86400
)
if not lj_validation.is_valid:
    raise ValueError(
        f"Invalid LabJack start timestamp: {lj_validation.error_message}"
    )

logger.debug("✓ Timestamp validation passed")
```

---

## Testing the Fixes

### **Run Unit Tests**

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Run specific timing tests
pytest tests/test_timing_fixes.py -v

# Expected output:
# test_timing_fixes.py::TestSequentialVideoTiming::test_get_video_start_time_for_detection_video1 PASSED
# test_timing_fixes.py::TestSequentialVideoTiming::test_get_video_start_time_for_detection_video2 PASSED
# test_timing_fixes.py::TestSequentialVideoTiming::test_post_roll_detection_uses_last_video PASSED
```

### **Run Integration Test with Real Data**

```python
# test_real_hil_session.py
from services.timing_synchronization_calculator import TimingSynchronizationCalculator
from database import get_db

db = next(get_db())

# Use real session from logs
session_id = "YOUR_SESSION_ID_HERE"

calculator = TimingSynchronizationCalculator()

# Get all detections for session
detections = db.query(DetectionEvent)\
    .filter(DetectionEvent.session_id == session_id)\
    .all()

print(f"\nAnalyzing {len(detections)} detections...")

post_roll_count = 0
latency_too_high = 0
decomp_invalid = 0

for detection in detections:
    # Calculate with fixed logic
    result = calculator.calculate_corrected_latency(
        session_id=session_id,
        detection_id=detection.id,
        detection_system_time=detection.timestamp,
        ground_truth_frame=detection.ground_truth_frame,
        ground_truth_video_time=detection.ground_truth_video_time,
        video_timing_metadata=...,  # Get from session
        labjack_start_time=...  # Get from session
    )

    # Check for issues
    if detection.video_id == "post_roll":
        post_roll_count += 1

    if result.real_latency_ms > 1000:  # >1 second is unrealistic
        latency_too_high += 1

    if result.decomposition_confidence < 0.5:
        decomp_invalid += 1

print(f"\nResults:")
print(f"  Post-roll detections: {post_roll_count} (should be 0)")
print(f"  Latencies >1s: {latency_too_high} (should be 0)")
print(f"  Invalid decompositions: {decomp_invalid} (should be 0)")

if post_roll_count == 0 and latency_too_high == 0:
    print("\n✅ SUCCESS: All fixes working correctly!")
else:
    print("\n❌ FAILURES: Some issues remain")
```

---

## Rollback Plan

If fixes cause issues:

```bash
# Revert changes
git checkout HEAD~1 backend/services/video_timing_service.py
git checkout HEAD~1 backend/services/timing_synchronization_calculator.py
git checkout HEAD~1 backend/services/latency_decomposition_service.py

# Remove new file
rm backend/services/timing_validation.py

# Restart backend
./RESTART_BACKEND.sh
```

---

## Success Criteria

After implementing all fixes, verify:

- ✅ **Zero post-roll detections** for valid test videos
- ✅ **Latencies in 10-500ms range** (realistic for HIL systems)
- ✅ **Quality assessments pass** (no more "unreliable")
- ✅ **Decomposition makes sense** (<30% overhead)
- ✅ **No "INVALID_INPUT_TIMESTAMPS" errors** (unless truly invalid)

---

**Ready to implement! Each fix is independent and can be tested separately.**
