"""
DEPRECATED TEST FILE
===================

This test file has been deprecated on 2025-11-20 because it imports services
that no longer exist or have been removed from the codebase.

Deprecated services used:
- Services that were removed during architecture refactoring
- Services that were consolidated into other modules
- Services that were replaced with newer implementations

This file is preserved for historical reference but is not actively maintained.
If you need similar functionality, please check the current service implementations
in src/services/ or consult the documentation.

Original location: tests/test_timestamp_video_assignment.py
"""

"""
Tests for Timestamp-Based Video Assignment Service

Validates the race condition fix for detection video assignment.
"""

import os
import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from models import TestSession, VideoTestSequence, SequenceVideoResult, Video, Project
from services.detection_video_assignment import TimestampBasedVideoAssignment


@pytest.fixture
def db_session(test_db):
    """Provide a database session for tests"""
    return test_db


@pytest.fixture
def sample_project(db_session):
    """Create a sample project"""
    project = Project(
        name="Test Project",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO"
    )
    db_session.add(project)
    db_session.commit()
    return project


@pytest.fixture
def sample_videos(db_session, sample_project):
    """Create sample videos"""
    videos = []
    for i in range(3):
        video = Video(
            project_id=sample_project.id,
            filename=f"video_{i+1}.mp4",
            duration=10.0,  # 10 seconds each
            frame_rate=30,
            resolution="1920x1080"
        )
        db_session.add(video)
        videos.append(video)
    db_session.commit()
    return videos


@pytest.fixture
def multi_video_session(db_session, sample_project, sample_videos):
    """Create a multi-video test session with sequence"""
    # Create test session
    session = TestSession(
        name="Multi-Video Test",
        project_id=sample_project.id,
        video_id=sample_videos[0].id,
        has_video_sequence=True,
        sequence_id="test-sequence-123",
        video_start_timestamp=1000.0  # Base timestamp
    )
    db_session.add(session)
    db_session.commit()

    # Create video sequence
    sequence = VideoTestSequence(
        test_session_id=session.id,
        name="Test Sequence",
        video_ids=[v.id for v in sample_videos],
        sequence_order=[
            {"video_id": sample_videos[0].id, "order": 0, "duration_ms": 10000},
            {"video_id": sample_videos[1].id, "order": 1, "duration_ms": 10000},
            {"video_id": sample_videos[2].id, "order": 2, "duration_ms": 10000}
        ],
        total_videos=3,
        status="running"
    )
    db_session.add(sequence)
    db_session.commit()

    # Create sequence video results with precise timing
    base_time = 1000.0
    video_results = []

    for i, video in enumerate(sample_videos):
        start_time = base_time + (i * 10.0)  # Each video starts 10 seconds after previous
        end_time = start_time + 10.0

        result = SequenceVideoResult(
            video_sequence_id=sequence.id,
            video_id=video.id,
            sequence_order=i,
            video_start_time=start_time,
            video_end_time=end_time,
            actual_duration_ms=10000.0,
            video_status="completed" if i < 2 else "playing"
        )
        db_session.add(result)
        video_results.append(result)

    db_session.commit()

    return {
        'session': session,
        'sequence': sequence,
        'video_results': video_results,
        'videos': sample_videos
    }


def test_single_video_assignment(db_session, sample_project, sample_videos):
    """Test video assignment for single-video session"""
    # Create single-video session
    session = TestSession(
        name="Single Video Test",
        project_id=sample_project.id,
        video_id=sample_videos[0].id,
        has_video_sequence=False,
        video_start_timestamp=1000.0
    )
    db_session.add(session)
    db_session.commit()

    # Test video assignment
    service = TimestampBasedVideoAssignment(db_session)

    result = service.assign_video_for_detection(
        session_id=session.id,
        detection_timestamp=1005.5  # 5.5 seconds into video
    )

    assert result['video_id'] == sample_videos[0].id
    assert result['sequence_video_result_id'] is None
    assert result['assignment_method'] == 'single_video'
    assert result['confidence'] == 'high'
    assert result['video_relative_timestamp'] == pytest.approx(5.5, abs=0.01)


def test_multi_video_first_video(multi_video_session, db_session):
    """Test assignment to first video in sequence"""
    service = TimestampBasedVideoAssignment(db_session)

    # Detection in first video (1000.0 to 1010.0)
    result = service.assign_video_for_detection(
        session_id=multi_video_session['session'].id,
        detection_timestamp=1005.0
    )

    assert result['video_id'] == multi_video_session['videos'][0].id
    assert result['sequence_video_result_id'] == multi_video_session['video_results'][0].id
    assert result['assignment_method'] == 'timestamp_boundary'
    assert result['confidence'] == 'high'
    assert result['video_relative_timestamp'] == pytest.approx(5.0, abs=0.01)


def test_multi_video_second_video(multi_video_session, db_session):
    """Test assignment to second video in sequence"""
    service = TimestampBasedVideoAssignment(db_session)

    # Detection in second video (1010.0 to 1020.0)
    result = service.assign_video_for_detection(
        session_id=multi_video_session['session'].id,
        detection_timestamp=1015.5
    )

    assert result['video_id'] == multi_video_session['videos'][1].id
    assert result['sequence_video_result_id'] == multi_video_session['video_results'][1].id
    assert result['assignment_method'] == 'timestamp_boundary'
    assert result['confidence'] == 'high'
    assert result['video_relative_timestamp'] == pytest.approx(5.5, abs=0.01)


def test_multi_video_third_video(multi_video_session, db_session):
    """Test assignment to third video in sequence"""
    service = TimestampBasedVideoAssignment(db_session)

    # Detection in third video (1020.0 to 1030.0)
    result = service.assign_video_for_detection(
        session_id=multi_video_session['session'].id,
        detection_timestamp=1025.0
    )

    assert result['video_id'] == multi_video_session['videos'][2].id
    assert result['sequence_video_result_id'] == multi_video_session['video_results'][2].id
    assert result['assignment_method'] == 'timestamp_boundary'
    assert result['confidence'] == 'high'
    assert result['video_relative_timestamp'] == pytest.approx(5.0, abs=0.01)


def test_race_condition_scenario(multi_video_session, db_session):
    """
    TEST THE RACE CONDITION FIX:
    Detection arrives at T0 before notify_video_started updates metadata at T0+50ms
    """
    service = TimestampBasedVideoAssignment(db_session)

    # Video 1 ends at 1010.0, Video 2 starts at 1010.0
    # Detection arrives at 1010.01 (10ms into video 2)
    # But sequence_metadata still shows current_video_id = video_1

    result = service.assign_video_for_detection(
        session_id=multi_video_session['session'].id,
        detection_timestamp=1010.01  # 10ms into video 2
    )

    # Should be assigned to video 2, NOT video 1
    assert result['video_id'] == multi_video_session['videos'][1].id
    assert result['sequence_video_result_id'] == multi_video_session['video_results'][1].id
    assert result['assignment_method'] == 'timestamp_boundary'
    assert result['confidence'] == 'high'


def test_detection_at_boundary_with_grace_period(multi_video_session, db_session):
    """Test detection within 100ms grace period before video start"""
    service = TimestampBasedVideoAssignment(db_session)

    # Detection 50ms before video 2 starts (should still be assigned to video 2)
    result = service.assign_video_for_detection(
        session_id=multi_video_session['session'].id,
        detection_timestamp=1009.95  # 50ms before video 2 start at 1010.0
    )

    # Should be assigned to video 2 due to grace period
    assert result['video_id'] == multi_video_session['videos'][1].id
    assert result['assignment_method'] == 'timestamp_boundary'
    assert result['confidence'] == 'high'


def test_detection_before_sequence_start(multi_video_session, db_session):
    """Test detection before sequence starts (should be rejected)"""
    service = TimestampBasedVideoAssignment(db_session)

    # Detection 1 second before video 1 starts
    result = service.assign_video_for_detection(
        session_id=multi_video_session['session'].id,
        detection_timestamp=999.0,
        fallback_video_id=multi_video_session['videos'][0].id
    )

    # Should use fallback or closest video
    assert result['confidence'] == 'low' or result['confidence'] == 'medium'


def test_detection_after_sequence_end(multi_video_session, db_session):
    """Test detection after sequence ends"""
    service = TimestampBasedVideoAssignment(db_session)

    # Detection 5 seconds after video 3 ends (1030.0 + 5.0)
    result = service.assign_video_for_detection(
        session_id=multi_video_session['session'].id,
        detection_timestamp=1035.0,
        fallback_video_id=multi_video_session['videos'][2].id
    )

    # Should use fallback
    assert result['confidence'] == 'low'


def test_out_of_order_detection(multi_video_session, db_session):
    """Test that service handles out-of-order detections correctly"""
    service = TimestampBasedVideoAssignment(db_session)

    # Process detections out of order
    timestamps = [1015.0, 1005.0, 1025.0, 1002.0]
    expected_videos = [1, 0, 2, 0]  # Indices into videos array

    for timestamp, expected_video_idx in zip(timestamps, expected_videos):
        result = service.assign_video_for_detection(
            session_id=multi_video_session['session'].id,
            detection_timestamp=timestamp
        )

        assert result['video_id'] == multi_video_session['videos'][expected_video_idx].id
        assert result['assignment_method'] == 'timestamp_boundary'
        assert result['confidence'] == 'high'


def test_caching_behavior(multi_video_session, db_session):
    """Test that caching improves performance without affecting correctness"""
    service = TimestampBasedVideoAssignment(db_session)

    # First call - builds cache
    result1 = service.assign_video_for_detection(
        session_id=multi_video_session['session'].id,
        detection_timestamp=1015.0
    )

    # Second call - uses cache
    result2 = service.assign_video_for_detection(
        session_id=multi_video_session['session'].id,
        detection_timestamp=1016.0
    )

    # Both should return correct results
    assert result1['video_id'] == multi_video_session['videos'][1].id
    assert result2['video_id'] == multi_video_session['videos'][1].id

    # Clear cache
    service.clear_cache(multi_video_session['session'].sequence_id)

    # Third call - rebuilds cache
    result3 = service.assign_video_for_detection(
        session_id=multi_video_session['session'].id,
        detection_timestamp=1017.0
    )

    assert result3['video_id'] == multi_video_session['videos'][1].id


def test_performance_100_detections(multi_video_session, db_session):
    """Performance test: Process 100 detections"""
    import time

    service = TimestampBasedVideoAssignment(db_session)

    start_time = time.time()

    # Process 100 detections across all videos
    for i in range(100):
        timestamp = 1000.0 + (i * 0.3)  # Spread across sequence
        result = service.assign_video_for_detection(
            session_id=multi_video_session['session'].id,
            detection_timestamp=timestamp
        )
        assert result['confidence'] in ['high', 'medium', 'low']

    elapsed_ms = (time.time() - start_time) * 1000

    print(f"\n✅ Processed 100 detections in {elapsed_ms:.2f}ms ({elapsed_ms/100:.2f}ms per detection)")

    # Should process < 50ms per detection (well under 100ms constraint)
    assert elapsed_ms / 100 < 50


def test_session_not_found(db_session):
    """Test handling of non-existent session"""
    service = TimestampBasedVideoAssignment(db_session)

    result = service.assign_video_for_detection(
        session_id="non-existent-session",
        detection_timestamp=1000.0,
        fallback_video_id="fallback-video-id"
    )

    assert result['video_id'] == "fallback-video-id"
    assert result['assignment_method'] == 'fallback'
    assert result['confidence'] == 'low'
    assert 'error' in result


def test_integration_instructions():
    """Document integration instructions"""
    integration_guide = """
    INTEGRATION INSTRUCTIONS FOR labjack_detection_service.py:

    1. Import the service:
       ```python
       from services.detection_video_assignment import get_video_assignment_service
       ```

    2. In _store_event_in_db(), BEFORE creating DBDetectionEvent:
       ```python
       # Get database session
       db = SessionLocal()

       # Use timestamp-based assignment
       video_service = get_video_assignment_service(db)
       assignment = video_service.assign_video_for_detection(
           session_id=event.session_id,
           detection_timestamp=event.timestamp.timestamp(),
           fallback_video_id=session.video_id
       )

       # Use assigned values
       video_id = assignment['video_id']
       sequence_video_result_id = assignment['sequence_video_result_id']
       video_relative_timestamp = assignment['video_relative_timestamp']

       # Log assignment quality
       logger.info(
           f"Detection assigned via {assignment['assignment_method']} "
           f"(confidence={assignment['confidence']})"
       )
       ```

    3. Replace existing video_id assignment logic (lines 1016-1040):
       - Remove dependency on sequence_metadata.current_video_id
       - Use timestamp-based assignment result instead

    4. Performance impact:
       - Adds <5ms per detection (one DB query, cached)
       - No buffering delay
       - No memory overhead (cache is ~1KB per sequence)
    """
    print(integration_guide)
