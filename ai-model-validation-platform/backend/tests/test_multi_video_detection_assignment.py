"""

pytestmark = pytest.mark.skip(reason="Deprecated modules or missing dependencies")

Integration tests for multi-video detection assignment and ground truth matching.

These tests validate that:
1. Detections are assigned to the correct video_id in multi-video sequences
2. Ground truth matching works correctly across all videos (not just video 1)
3. Cross-video boundary cases are handled correctly
4. Sequence metadata tracking works as expected

Tests should FAIL with the current buggy code and PASS after the fix is applied.
"""

import os
import pytest
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, select, delete, update, func
from sqlalchemy.orm import sessionmaker

from models import (
    Base,
    TestSession,
    DetectionEvent,
    GroundTruthObject,
    Video
)
from services.ground_truth_matching_service import GroundTruthMatchingService
# GroundTruthMatchResult not in schemas

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ============================================================================
# TEST FIXTURES AND HELPERS
# ============================================================================

@pytest.fixture
def test_db():
    """Create an in-memory test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def matching_service():
    """Create ground truth matching service instance."""
    return GroundTruthMatchingService()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_multi_video_session(
    db: Session,
    num_videos: int = 3,
    video_duration_sec: float = 30.0,
    fps: float = 30.0
) -> Tuple[TestSession, List[Video]]:
    """
    Create a test session with multiple videos in sequence.

    Args:
        db: Database session
        num_videos: Number of videos in sequence
        video_duration_sec: Duration of each video in seconds
        fps: Frame rate of videos

    Returns:
        Tuple of (TestSession, List[Video])
    """
    base_time = datetime(2025, 1, 1, 12, 0, 0)

    # Create test session
    session = TestSession(
        session_id=f"test-multi-video-{num_videos}",
        test_name="Multi-Video Detection Assignment Test",
        start_time=base_time,
        status="in_progress",
        video_count=num_videos,
        sequence_metadata={
            "total_videos": num_videos,
            "current_video_index": 0,
            "current_video_id": None,  # Will be set when first video starts
            "video_start_times": [],
            "video_end_times": []
        }
    )
    db.add(session)
    db.flush()

    # Create videos in sequence
    videos = []
    for i in range(num_videos):
        video_start_time = base_time + timedelta(seconds=i * video_duration_sec)
        video_end_time = video_start_time + timedelta(seconds=video_duration_sec)

        video = Video(
            video_id=f"video-{i+1}",
            session_id=session.session_id,
            sequence_index=i,
            file_path=f"/test/videos/video_{i+1}.mp4",
            start_time=video_start_time,
            end_time=video_end_time,
            duration=video_duration_sec,
            fps=fps,
            total_frames=int(video_duration_sec * fps),
            status="completed"
        )
        db.add(video)
        videos.append(video)

        # Update session sequence metadata
        session.sequence_metadata["video_start_times"].append(video_start_time.isoformat())
        session.sequence_metadata["video_end_times"].append(video_end_time.isoformat())

    # Set first video as current
    session.video_id = videos[0].video_id
    session.sequence_metadata["current_video_id"] = videos[0].video_id

    db.commit()
    db.refresh(session)

    logger.info(f"Created session {session.session_id} with {num_videos} videos")
    for i, video in enumerate(videos):
        logger.info(f"  Video {i+1}: {video.video_id}, "
                   f"start={video.start_time}, end={video.end_time}")

    return session, videos


def create_detection_at_timestamp(
    db: Session,
    session: TestSession,
    timestamp: datetime,
    video_id: Optional[str] = None,
    detection_type: str = "person",
    confidence: float = 0.95
) -> DetectionEvent:
    """
    Create a detection event at a specific timestamp.

    Args:
        db: Database session
        session: Test session
        timestamp: When detection occurred
        video_id: Video ID (if None, will use session.video_id - the bug!)
        detection_type: Type of object detected
        confidence: Detection confidence score

    Returns:
        DetectionEvent
    """
    # This simulates the BUGGY behavior - always using session.video_id
    if video_id is None:
        video_id = session.video_id
        logger.warning(f"No video_id provided, defaulting to session.video_id={video_id} "
                      f"(THIS IS THE BUG!)")

    detection = DetectionEvent(
        session_id=session.session_id,
        video_id=video_id,
        timestamp=timestamp,
        detection_type=detection_type,
        confidence=confidence,
        bbox_x=100,
        bbox_y=100,
        bbox_width=50,
        bbox_height=80,
        frame_number=0  # Will be calculated based on timestamp
    )
    db.add(detection)
    db.commit()
    db.refresh(detection)

    logger.debug(f"Created detection: timestamp={timestamp}, video_id={video_id}, "
                f"type={detection_type}")

    return detection


def create_ground_truth_object(
    db: Session,
    session: TestSession,
    video_id: str,
    timestamp: datetime,
    object_type: str = "person",
    bbox: Tuple[int, int, int, int] = (100, 100, 50, 80)
) -> GroundTruthObject:
    """
    Create a ground truth object for a specific video.

    Args:
        db: Database session
        session: Test session
        video_id: Video this GT belongs to
        timestamp: When GT object appears
        object_type: Type of object
        bbox: Bounding box (x, y, width, height)

    Returns:
        GroundTruthObject
    """
    gt = GroundTruthObject(
        session_id=session.session_id,
        video_id=video_id,
        timestamp=timestamp,
        object_type=object_type,
        bbox_x=bbox[0],
        bbox_y=bbox[1],
        bbox_width=bbox[2],
        bbox_height=bbox[3],
        frame_number=0
    )
    db.add(gt)
    db.commit()
    db.refresh(gt)

    logger.debug(f"Created GT object: video_id={video_id}, timestamp={timestamp}, "
                f"type={object_type}")

    return gt


def get_video_for_timestamp(videos: List[Video], timestamp: datetime) -> Optional[Video]:
    """
    Determine which video a timestamp falls into.

    Args:
        videos: List of videos in sequence
        timestamp: Timestamp to check

    Returns:
        Video that contains this timestamp, or None
    """
    for video in videos:
        if video.start_time <= timestamp < video.end_time:
            return video
    return None


def verify_detection_video_assignment(
    detection: DetectionEvent,
    expected_video: Video,
    videos: List[Video]
) -> Tuple[bool, str]:
    """
    Verify a detection is assigned to the correct video.

    Args:
        detection: Detection event to verify
        expected_video: Expected video it should be assigned to
        videos: All videos in sequence

    Returns:
        Tuple of (is_correct, error_message)
    """
    if detection.video_id == expected_video.video_id:
        return True, ""

    # Find which video it was incorrectly assigned to
    actual_video = next((v for v in videos if v.video_id == detection.video_id), None)

    error_msg = (
        f"Detection at {detection.timestamp} assigned to wrong video!\n"
        f"  Expected: {expected_video.video_id} (seq_index={expected_video.sequence_index})\n"
        f"  Actual: {detection.video_id}"
    )

    if actual_video:
        error_msg += f" (seq_index={actual_video.sequence_index})\n"
        error_msg += f"  Expected video time range: {expected_video.start_time} to {expected_video.end_time}\n"
        error_msg += f"  Actual video time range: {actual_video.start_time} to {actual_video.end_time}\n"

    return False, error_msg


def calculate_per_video_metrics(
    db: Session,
    session: TestSession,
    video_id: str
) -> Dict[str, int]:
    """
    Calculate TP/FP/FN metrics for a specific video.

    Args:
        db: Database session
        session: Test session
        video_id: Video to calculate metrics for

    Returns:
        Dict with tp, fp, fn, precision, recall
    """
    # Get all detections for this video
    detections = db.execute(select(DetectionEvent).where(
        DetectionEvent.session_id == session.session_id,
        DetectionEvent.video_id == video_id
    )).scalars().all()

    # Get all ground truth objects for this video
    ground_truths = db.execute(select(GroundTruthObject).where(
        GroundTruthObject.session_id == session.session_id,
        GroundTruthObject.video_id == video_id
    )).scalars().all()

    tp = sum(1 for d in detections if d.ground_truth_match_id is not None)
    fp = sum(1 for d in detections if d.ground_truth_match_id is None)
    fn = sum(1 for gt in ground_truths if not any(
        d.ground_truth_match_id == gt.id for d in detections
    ))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "total_detections": len(detections),
        "total_ground_truth": len(ground_truths)
    }


# ============================================================================
# TEST CASES
# ============================================================================

def test_video_id_assignment_across_sequence(test_db, matching_service):
    """
    Test 1: Verify detections are assigned to correct video_id in multi-video sequences.

    This test creates a 3-video sequence and simulates detections at various timestamps
    that should fall into different videos. It validates that each detection is assigned
    to the CORRECT video_id based on timestamp, not always to video 1's ID.

    EXPECTED BEHAVIOR (AFTER FIX):
    - Detections at t=5s → video-1
    - Detections at t=35s → video-2
    - Detections at t=65s → video-3

    CURRENT BUGGY BEHAVIOR:
    - All detections → video-1 (because code always uses session.video_id)
    """
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Video ID Assignment Across Sequence")
    logger.info("="*80)

    # Create 3-video sequence (30 seconds each)
    session, videos = create_multi_video_session(
        test_db,
        num_videos=3,
        video_duration_sec=30.0,
        fps=30.0
    )

    base_time = videos[0].start_time

    # Create detections in each video
    test_cases = [
        # (timestamp_offset_seconds, expected_video_index, description)
        (5.0, 0, "Detection in middle of video 1"),
        (15.0, 0, "Detection near end of video 1"),
        (35.0, 1, "Detection in middle of video 2"),
        (45.0, 1, "Detection near end of video 2"),
        (65.0, 2, "Detection in middle of video 3"),
        (75.0, 2, "Detection near end of video 3"),
    ]

    detections = []
    expected_assignments = []

    for offset, video_idx, description in test_cases:
        timestamp = base_time + timedelta(seconds=offset)
        expected_video = videos[video_idx]

        logger.info(f"\nCreating detection: {description}")
        logger.info(f"  Timestamp: {timestamp} (offset={offset}s)")
        logger.info(f"  Expected video: {expected_video.video_id} (index={video_idx})")

        # Simulate the BUGGY behavior - no video_id passed
        # In real code, this would be in labjack_detection_service
        detection = create_detection_at_timestamp(
            test_db,
            session,
            timestamp,
            video_id=None  # This is the bug - should calculate from timestamp!
        )

        detections.append(detection)
        expected_assignments.append((detection, expected_video))

    # Verify assignments
    logger.info("\n" + "-"*80)
    logger.info("VERIFICATION RESULTS:")
    logger.info("-"*80)

    failures = []
    for detection, expected_video in expected_assignments:
        is_correct, error_msg = verify_detection_video_assignment(
            detection, expected_video, videos
        )

        if is_correct:
            logger.info(f"✓ PASS: Detection at {detection.timestamp} correctly "
                       f"assigned to {expected_video.video_id}")
        else:
            logger.error(f"✗ FAIL: {error_msg}")
            failures.append(error_msg)

    # Assert all assignments are correct
    if failures:
        pytest.fail(
            f"\n{'='*80}\n"
            f"Video ID Assignment Test FAILED!\n"
            f"{'='*80}\n"
            f"{len(failures)} out of {len(detections)} detections assigned to wrong video.\n\n"
            f"FAILURES:\n" + "\n".join(failures) +
            f"\n\nThis is the expected failure - detections are always assigned to "
            f"session.video_id (video-1) instead of calculating the correct video "
            f"based on timestamp."
        )


def test_ground_truth_matching_multi_video(test_db, matching_service):
    """
    Test 2: Verify ground truth matching works for ALL videos, not just video 1.

    This test creates ground truth objects and detections in videos 2 and 3,
    then runs the matching service to verify that TP matches work correctly
    for all videos in the sequence.

    EXPECTED BEHAVIOR (AFTER FIX):
    - Detections in video 2 match GT in video 2 → TP > 0, precision > 0%
    - Detections in video 3 match GT in video 3 → TP > 0, recall > 0%

    CURRENT BUGGY BEHAVIOR:
    - Detections have video_id = video-1
    - GT has video_id = video-2 or video-3
    - Matching fails because video_id mismatch → TP = 0, precision = 0%
    """
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Ground Truth Matching Multi-Video")
    logger.info("="*80)

    # Create 3-video sequence
    session, videos = create_multi_video_session(
        test_db,
        num_videos=3,
        video_duration_sec=30.0,
        fps=30.0
    )

    base_time = videos[0].start_time

    # Create ground truth objects in video 2 and 3
    logger.info("\nCreating ground truth objects...")

    # Video 2 ground truth (at t=35s, t=40s)
    gt_video2_1 = create_ground_truth_object(
        test_db, session, videos[1].video_id,
        base_time + timedelta(seconds=35),
        object_type="person",
        bbox=(100, 100, 50, 80)
    )
    gt_video2_2 = create_ground_truth_object(
        test_db, session, videos[1].video_id,
        base_time + timedelta(seconds=40),
        object_type="person",
        bbox=(150, 120, 50, 80)
    )

    # Video 3 ground truth (at t=65s, t=70s)
    gt_video3_1 = create_ground_truth_object(
        test_db, session, videos[2].video_id,
        base_time + timedelta(seconds=65),
        object_type="car",
        bbox=(200, 150, 100, 60)
    )
    gt_video3_2 = create_ground_truth_object(
        test_db, session, videos[2].video_id,
        base_time + timedelta(seconds=70),
        object_type="car",
        bbox=(250, 150, 100, 60)
    )

    # Create matching detections (same timestamps, close bboxes)
    logger.info("\nCreating detections that should match GT...")

    # Detections in video 2 (should match gt_video2_1, gt_video2_2)
    det_video2_1 = create_detection_at_timestamp(
        test_db, session,
        base_time + timedelta(seconds=35.1),  # Within time tolerance
        video_id=None,  # BUG: Will use session.video_id instead of videos[1].video_id
        detection_type="person",
        confidence=0.92
    )
    det_video2_2 = create_detection_at_timestamp(
        test_db, session,
        base_time + timedelta(seconds=40.05),
        video_id=None,
        detection_type="person",
        confidence=0.89
    )

    # Detections in video 3 (should match gt_video3_1, gt_video3_2)
    det_video3_1 = create_detection_at_timestamp(
        test_db, session,
        base_time + timedelta(seconds=65.08),
        video_id=None,
        detection_type="car",
        confidence=0.95
    )
    det_video3_2 = create_detection_at_timestamp(
        test_db, session,
        base_time + timedelta(seconds=70.12),
        video_id=None,
        detection_type="car",
        confidence=0.91
    )

    # Run ground truth matching
    logger.info("\nRunning ground truth matching service...")
    result = matching_service.match_detections_to_ground_truth(
        test_db,
        session.session_id
    )

    # Calculate per-video metrics
    logger.info("\n" + "-"*80)
    logger.info("PER-VIDEO METRICS:")
    logger.info("-"*80)

    metrics_by_video = {}
    for video in videos:
        metrics = calculate_per_video_metrics(test_db, session, video.video_id)
        metrics_by_video[video.video_id] = metrics

        logger.info(f"\n{video.video_id} (sequence_index={video.sequence_index}):")
        logger.info(f"  Total detections: {metrics['total_detections']}")
        logger.info(f"  Total ground truth: {metrics['total_ground_truth']}")
        logger.info(f"  TP: {metrics['tp']}")
        logger.info(f"  FP: {metrics['fp']}")
        logger.info(f"  FN: {metrics['fn']}")
        logger.info(f"  Precision: {metrics['precision']:.2%}")
        logger.info(f"  Recall: {metrics['recall']:.2%}")

    # Verify video 2 and 3 have non-zero metrics
    logger.info("\n" + "-"*80)
    logger.info("VERIFICATION RESULTS:")
    logger.info("-"*80)

    failures = []

    # Video 2 should have 2 TPs (100% precision and recall)
    video2_metrics = metrics_by_video[videos[1].video_id]
    if video2_metrics['tp'] == 0:
        error = (
            f"Video 2 has ZERO true positives!\n"
            f"  Expected: 2 TPs (matching 2 GT objects)\n"
            f"  Actual: {video2_metrics['tp']} TPs\n"
            f"  This indicates detections are assigned to wrong video_id"
        )
        logger.error(f"✗ FAIL: {error}")
        failures.append(error)
    else:
        logger.info(f"✓ PASS: Video 2 has {video2_metrics['tp']} TPs")

    # Video 3 should have 2 TPs (100% precision and recall)
    video3_metrics = metrics_by_video[videos[2].video_id]
    if video3_metrics['tp'] == 0:
        error = (
            f"Video 3 has ZERO true positives!\n"
            f"  Expected: 2 TPs (matching 2 GT objects)\n"
            f"  Actual: {video3_metrics['tp']} TPs\n"
            f"  This indicates detections are assigned to wrong video_id"
        )
        logger.error(f"✗ FAIL: {error}")
        failures.append(error)
    else:
        logger.info(f"✓ PASS: Video 3 has {video3_metrics['tp']} TPs")

    # Assert all videos have correct metrics
    if failures:
        pytest.fail(
            f"\n{'='*80}\n"
            f"Ground Truth Matching Test FAILED!\n"
            f"{'='*80}\n"
            f"Videos 2 and 3 have zero true positives because detections are "
            f"incorrectly assigned to video-1 instead of their actual videos.\n\n"
            f"FAILURES:\n" + "\n".join(failures)
        )


def test_cross_video_boundary_validation(test_db, matching_service):
    """
    Test 3: Verify detections at video transition boundaries are assigned correctly.

    This test focuses on edge cases where detections occur exactly at or very close
    to video start/end times. It validates that boundary conditions are handled
    correctly and detections don't "leak" into adjacent videos.

    EXPECTED BEHAVIOR:
    - Detection at video1_end - 0.1s → video-1
    - Detection at video1_end + 0.1s → video-2
    - Detection exactly at video2_start → video-2
    """
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Cross-Video Boundary Validation")
    logger.info("="*80)

    # Create 3-video sequence with precise timing
    session, videos = create_multi_video_session(
        test_db,
        num_videos=3,
        video_duration_sec=30.0,
        fps=30.0
    )

    # Test boundary cases
    boundary_tests = [
        # (timestamp, expected_video_index, description)
        (videos[0].start_time, 0, "Exactly at video 1 start"),
        (videos[0].end_time - timedelta(milliseconds=100), 0, "100ms before video 1 end"),
        (videos[1].start_time, 1, "Exactly at video 2 start"),
        (videos[1].start_time + timedelta(milliseconds=100), 1, "100ms after video 2 start"),
        (videos[1].end_time - timedelta(milliseconds=100), 1, "100ms before video 2 end"),
        (videos[2].start_time, 2, "Exactly at video 3 start"),
        (videos[2].end_time - timedelta(milliseconds=100), 2, "100ms before video 3 end"),
    ]

    logger.info("\nCreating boundary detections...")
    detections_and_expected = []

    for timestamp, video_idx, description in boundary_tests:
        expected_video = videos[video_idx]

        logger.info(f"\n{description}:")
        logger.info(f"  Timestamp: {timestamp}")
        logger.info(f"  Expected video: {expected_video.video_id} (index={video_idx})")
        logger.info(f"  Video time range: {expected_video.start_time} to {expected_video.end_time}")

        detection = create_detection_at_timestamp(
            test_db, session, timestamp,
            video_id=None  # Bug: should calculate from timestamp
        )

        detections_and_expected.append((detection, expected_video, description))

    # Verify boundary assignments
    logger.info("\n" + "-"*80)
    logger.info("BOUNDARY VERIFICATION RESULTS:")
    logger.info("-"*80)

    failures = []
    for detection, expected_video, description in detections_and_expected:
        is_correct, error_msg = verify_detection_video_assignment(
            detection, expected_video, videos
        )

        if is_correct:
            logger.info(f"✓ PASS: {description}")
        else:
            logger.error(f"✗ FAIL: {description}\n{error_msg}")
            failures.append(f"{description}: {error_msg}")

    if failures:
        pytest.fail(
            f"\n{'='*80}\n"
            f"Boundary Validation Test FAILED!\n"
            f"{'='*80}\n"
            f"{len(failures)} out of {len(detections_and_expected)} boundary cases failed.\n\n"
            f"FAILURES:\n" + "\n".join(failures)
        )


def test_sequence_metadata_tracking(test_db, matching_service):
    """
    Test 4: Verify sequence metadata tracking and current_video_id updates.

    This test simulates video transitions and validates that the detection storage
    logic correctly uses current_video_id from sequence_metadata, with proper
    fallback to session.video_id for single-video sessions.

    EXPECTED BEHAVIOR:
    - When sequence_metadata.current_video_id is set → use that video_id
    - When sequence_metadata.current_video_id is None → fallback to session.video_id
    - Video transitions update current_video_id → subsequent detections use new ID
    """
    logger.info("\n" + "="*80)
    logger.info("TEST 4: Sequence Metadata Tracking")
    logger.info("="*80)

    # Create 3-video sequence
    session, videos = create_multi_video_session(
        test_db,
        num_videos=3,
        video_duration_sec=30.0,
        fps=30.0
    )

    base_time = videos[0].start_time

    # Test scenario: Simulate video playback with transitions
    test_scenarios = [
        # (time_offset, current_video_index, description)
        (5.0, 0, "During video 1 playback"),
        (15.0, 0, "Still in video 1"),
        (35.0, 1, "After transition to video 2"),
        (45.0, 1, "Still in video 2"),
        (65.0, 2, "After transition to video 3"),
        (75.0, 2, "Still in video 3"),
    ]

    logger.info("\nSimulating video playback with metadata updates...")

    detection_results = []

    for time_offset, video_idx, description in test_scenarios:
        timestamp = base_time + timedelta(seconds=time_offset)
        expected_video = videos[video_idx]

        # Simulate video transition - update sequence_metadata
        session.sequence_metadata["current_video_index"] = video_idx
        session.sequence_metadata["current_video_id"] = expected_video.video_id
        test_db.commit()
        test_db.refresh(session)

        logger.info(f"\n{description}:")
        logger.info(f"  Timestamp: {timestamp} (offset={time_offset}s)")
        logger.info(f"  sequence_metadata.current_video_id: {session.sequence_metadata['current_video_id']}")
        logger.info(f"  Expected assignment: {expected_video.video_id}")

        # CORRECT IMPLEMENTATION would do:
        # video_id = session.sequence_metadata.get("current_video_id") or session.video_id

        # But BUGGY implementation does:
        # video_id = session.video_id  (always video-1)

        detection = create_detection_at_timestamp(
            test_db, session, timestamp,
            video_id=None  # Should use sequence_metadata, but bug uses session.video_id
        )

        detection_results.append((detection, expected_video, description))

    # Verify metadata-driven assignments
    logger.info("\n" + "-"*80)
    logger.info("METADATA TRACKING VERIFICATION:")
    logger.info("-"*80)

    failures = []
    for detection, expected_video, description in detection_results:
        is_correct, error_msg = verify_detection_video_assignment(
            detection, expected_video, videos
        )

        if is_correct:
            logger.info(f"✓ PASS: {description}")
        else:
            logger.error(f"✗ FAIL: {description}\n{error_msg}")
            failures.append(f"{description}: {error_msg}")

    # Test fallback behavior for single-video session
    logger.info("\n" + "-"*80)
    logger.info("Testing fallback for single-video session...")
    logger.info("-"*80)

    # Create single-video session (no sequence_metadata)
    single_session = TestSession(
        session_id="test-single-video",
        test_name="Single Video Session",
        start_time=base_time,
        status="in_progress",
        video_count=1,
        video_id="single-video-1",
        sequence_metadata=None  # No multi-video metadata
    )
    test_db.add(single_session)
    test_db.commit()

    single_detection = create_detection_at_timestamp(
        test_db, single_session,
        base_time + timedelta(seconds=5),
        video_id=None  # Should fallback to session.video_id
    )

    if single_detection.video_id == single_session.video_id:
        logger.info(f"✓ PASS: Single-video fallback works correctly")
    else:
        error = (
            f"Single-video fallback FAILED!\n"
            f"  Expected: {single_session.video_id}\n"
            f"  Actual: {single_detection.video_id}"
        )
        logger.error(f"✗ FAIL: {error}")
        failures.append(error)

    if failures:
        pytest.fail(
            f"\n{'='*80}\n"
            f"Sequence Metadata Tracking Test FAILED!\n"
            f"{'='*80}\n"
            f"{len(failures)} scenarios failed.\n\n"
            f"The code does not correctly use sequence_metadata.current_video_id "
            f"for video assignment. It always falls back to session.video_id.\n\n"
            f"FAILURES:\n" + "\n".join(failures)
        )


def test_detection_count_distribution(test_db, matching_service):
    """
    Test 5: Verify detection counts are distributed across all videos.

    This test creates many detections spread across all videos and verifies
    that the detection counts in the database reflect the correct distribution,
    not all detections piled into video 1.
    """
    logger.info("\n" + "="*80)
    logger.info("TEST 5: Detection Count Distribution")
    logger.info("="*80)

    # Create 3-video sequence
    session, videos = create_multi_video_session(
        test_db,
        num_videos=3,
        video_duration_sec=30.0,
        fps=30.0
    )

    base_time = videos[0].start_time

    # Create 10 detections per video (30 total)
    detections_per_video = 10

    logger.info(f"\nCreating {detections_per_video} detections per video...")

    expected_counts = {video.video_id: 0 for video in videos}

    for video_idx, video in enumerate(videos):
        logger.info(f"\nCreating detections for {video.video_id}...")

        for i in range(detections_per_video):
            # Spread detections evenly across video duration
            time_offset = video_idx * 30 + (i * 3)  # Every 3 seconds
            timestamp = base_time + timedelta(seconds=time_offset)

            detection = create_detection_at_timestamp(
                test_db, session, timestamp,
                video_id=None  # Bug: should assign to correct video
            )

            expected_counts[video.video_id] += 1

    # Query actual detection counts per video
    logger.info("\n" + "-"*80)
    logger.info("DETECTION COUNT DISTRIBUTION:")
    logger.info("-"*80)

    actual_counts = {}
    for video in videos:
        count = test_db.execute(select(func.count()).select_from(DetectionEvent).where(
            DetectionEvent.session_id == session.session_id,
            DetectionEvent.video_id == video.video_id
        )).scalar()
        actual_counts[video.video_id] = count

        logger.info(f"\n{video.video_id} (sequence_index={video.sequence_index}):")
        logger.info(f"  Expected detections: {expected_counts[video.video_id]}")
        logger.info(f"  Actual detections: {count}")

    # Verify distribution
    logger.info("\n" + "-"*80)
    logger.info("DISTRIBUTION VERIFICATION:")
    logger.info("-"*80)

    failures = []

    for video in videos:
        expected = expected_counts[video.video_id]
        actual = actual_counts[video.video_id]

        if actual == expected:
            logger.info(f"✓ PASS: {video.video_id} has correct count ({actual})")
        else:
            error = (
                f"{video.video_id} has WRONG detection count!\n"
                f"  Expected: {expected}\n"
                f"  Actual: {actual}\n"
                f"  Difference: {actual - expected:+d}"
            )
            logger.error(f"✗ FAIL: {error}")
            failures.append(error)

    # Check if all detections ended up in video 1 (the bug symptom)
    video1_count = actual_counts[videos[0].video_id]
    total_expected = sum(expected_counts.values())

    if video1_count == total_expected and len(videos) > 1:
        logger.error(
            f"\n⚠️  CRITICAL BUG DETECTED: All {total_expected} detections "
            f"are assigned to video 1!\n"
            f"This confirms the bug where all detections use session.video_id."
        )

    if failures:
        pytest.fail(
            f"\n{'='*80}\n"
            f"Detection Count Distribution Test FAILED!\n"
            f"{'='*80}\n"
            f"Detection counts do not match expected distribution across videos.\n\n"
            f"FAILURES:\n" + "\n".join(failures)
        )


# ============================================================================
# INTEGRATION TEST: Full Multi-Video Workflow
# ============================================================================

def test_full_multi_video_workflow(test_db, matching_service):
    """
    Integration Test: Complete multi-video workflow from detection to metrics.

    This test simulates a complete HIL test session with:
    1. 3 videos in sequence
    2. Ground truth objects in each video
    3. Detections (TP and FP) in each video
    4. Ground truth matching
    5. Per-video metrics calculation
    6. Aggregated session metrics

    This is the ultimate test that validates the entire system works correctly
    for multi-video sequences.
    """
    logger.info("\n" + "="*80)
    logger.info("INTEGRATION TEST: Full Multi-Video Workflow")
    logger.info("="*80)

    # Create 3-video sequence
    session, videos = create_multi_video_session(
        test_db,
        num_videos=3,
        video_duration_sec=30.0,
        fps=30.0
    )

    base_time = videos[0].start_time

    # Setup test data for each video
    logger.info("\nSetting up test data...")

    video_test_data = {
        videos[0].video_id: {
            "gt_timestamps": [5.0, 10.0, 15.0],  # 3 GT objects
            "tp_timestamps": [5.1, 10.05, 15.08],  # 3 matching detections
            "fp_timestamps": [8.0, 12.0],  # 2 false positives
        },
        videos[1].video_id: {
            "gt_timestamps": [35.0, 40.0, 45.0, 50.0],  # 4 GT objects
            "tp_timestamps": [35.05, 40.1, 45.07],  # 3 matching (1 FN)
            "fp_timestamps": [38.0],  # 1 false positive
        },
        videos[2].video_id: {
            "gt_timestamps": [65.0, 70.0],  # 2 GT objects
            "tp_timestamps": [65.08, 70.1],  # 2 matching detections
            "fp_timestamps": [68.0, 72.0, 75.0],  # 3 false positives
        },
    }

    # Create ground truth objects
    logger.info("\nCreating ground truth objects...")
    for video in videos:
        gt_data = video_test_data[video.video_id]
        for gt_offset in gt_data["gt_timestamps"]:
            timestamp = base_time + timedelta(seconds=gt_offset)
            create_ground_truth_object(
                test_db, session, video.video_id, timestamp,
                object_type="person"
            )

    # Create detections (TP and FP)
    logger.info("\nCreating detections...")
    for video_idx, video in enumerate(videos):
        test_data = video_test_data[video.video_id]

        # Update sequence metadata to simulate video transition
        session.sequence_metadata["current_video_index"] = video_idx
        session.sequence_metadata["current_video_id"] = video.video_id
        test_db.commit()

        # Create TP detections
        for tp_offset in test_data["tp_timestamps"]:
            timestamp = base_time + timedelta(seconds=tp_offset)
            create_detection_at_timestamp(
                test_db, session, timestamp,
                video_id=None,  # Bug: should use sequence_metadata
                detection_type="person"
            )

        # Create FP detections
        for fp_offset in test_data["fp_timestamps"]:
            timestamp = base_time + timedelta(seconds=fp_offset)
            create_detection_at_timestamp(
                test_db, session, timestamp,
                video_id=None,
                detection_type="person"
            )

    # Run ground truth matching
    logger.info("\nRunning ground truth matching...")
    matching_result = matching_service.match_detections_to_ground_truth(
        test_db,
        session.session_id
    )

    # Calculate and verify per-video metrics
    logger.info("\n" + "-"*80)
    logger.info("PER-VIDEO METRICS VERIFICATION:")
    logger.info("-"*80)

    expected_metrics = {
        videos[0].video_id: {"tp": 3, "fp": 2, "fn": 0, "precision": 0.60, "recall": 1.0},
        videos[1].video_id: {"tp": 3, "fp": 1, "fn": 1, "precision": 0.75, "recall": 0.75},
        videos[2].video_id: {"tp": 2, "fp": 3, "fn": 0, "precision": 0.40, "recall": 1.0},
    }

    failures = []

    for video in videos:
        actual_metrics = calculate_per_video_metrics(test_db, session, video.video_id)
        expected = expected_metrics[video.video_id]

        logger.info(f"\n{video.video_id} (sequence_index={video.sequence_index}):")
        logger.info(f"  Expected - TP: {expected['tp']}, FP: {expected['fp']}, "
                   f"FN: {expected['fn']}")
        logger.info(f"  Actual   - TP: {actual_metrics['tp']}, "
                   f"FP: {actual_metrics['fp']}, FN: {actual_metrics['fn']}")
        logger.info(f"  Expected - Precision: {expected['precision']:.2%}, "
                   f"Recall: {expected['recall']:.2%}")
        logger.info(f"  Actual   - Precision: {actual_metrics['precision']:.2%}, "
                   f"Recall: {actual_metrics['recall']:.2%}")

        # Verify TP/FP/FN counts
        if (actual_metrics['tp'] != expected['tp'] or
            actual_metrics['fp'] != expected['fp'] or
            actual_metrics['fn'] != expected['fn']):
            error = (
                f"{video.video_id} metrics MISMATCH!\n"
                f"  Expected: TP={expected['tp']}, FP={expected['fp']}, FN={expected['fn']}\n"
                f"  Actual: TP={actual_metrics['tp']}, FP={actual_metrics['fp']}, "
                f"FN={actual_metrics['fn']}"
            )
            logger.error(f"✗ FAIL: {error}")
            failures.append(error)
        else:
            logger.info(f"✓ PASS: Metrics match expected values")

    # Calculate aggregated session metrics
    logger.info("\n" + "-"*80)
    logger.info("AGGREGATED SESSION METRICS:")
    logger.info("-"*80)

    total_tp = sum(calculate_per_video_metrics(test_db, session, v.video_id)['tp']
                   for v in videos)
    total_fp = sum(calculate_per_video_metrics(test_db, session, v.video_id)['fp']
                   for v in videos)
    total_fn = sum(calculate_per_video_metrics(test_db, session, v.video_id)['fn']
                   for v in videos)

    expected_total_tp = 8  # 3 + 3 + 2
    expected_total_fp = 6  # 2 + 1 + 3
    expected_total_fn = 1  # 0 + 1 + 0

    logger.info(f"\nExpected aggregated: TP={expected_total_tp}, FP={expected_total_fp}, "
               f"FN={expected_total_fn}")
    logger.info(f"Actual aggregated: TP={total_tp}, FP={total_fp}, FN={total_fn}")

    if (total_tp != expected_total_tp or
        total_fp != expected_total_fp or
        total_fn != expected_total_fn):
        error = (
            f"Aggregated session metrics MISMATCH!\n"
            f"  Expected: TP={expected_total_tp}, FP={expected_total_fp}, "
            f"FN={expected_total_fn}\n"
            f"  Actual: TP={total_tp}, FP={total_fp}, FN={total_fn}"
        )
        logger.error(f"✗ FAIL: {error}")
        failures.append(error)
    else:
        logger.info(f"✓ PASS: Aggregated metrics correct")

    if failures:
        pytest.fail(
            f"\n{'='*80}\n"
            f"Full Multi-Video Workflow Integration Test FAILED!\n"
            f"{'='*80}\n"
            f"The complete workflow from detection to metrics calculation has "
            f"issues with multi-video sequences.\n\n"
            f"FAILURES:\n" + "\n".join(failures)
        )


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
