"""
Comprehensive test suite for video_id_resolver service

Tests cover:
1. Single video sessions (backward compatibility)
2. Multi-video sequences with timestamp ranges
3. Edge cases (boundaries, gaps, overlaps)
4. Performance validation (<5ms queries)
5. Error handling and fallbacks
"""

import pytest
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from database import SessionLocal
from models import (
    TestSession,
    Video,
    Project,
    VideoTestSequence,
    SequenceVideoResult
)
from services.video_id_resolver import (
    get_video_id_for_detection,
    get_sequence_video_result_id
)


@pytest.fixture
def db_session():
    """Provide a database session for tests"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_project(db_session: Session):
    """Create a test project"""
    project = Project(
        id="test-project-001",
        name="Video ID Resolver Test Project"
    )
    db_session.add(project)
    db_session.commit()
    return project


@pytest.fixture
def test_videos(db_session: Session):
    """Create test videos"""
    videos = [
        Video(
            id=f"video-{i+1}",
            filename=f"test_video_{i+1}.mp4",
            file_path=f"/videos/test_video_{i+1}.mp4",
            duration=10.0,
            fps=30.0,
            width=1920,
            height=1080
        )
        for i in range(3)
    ]

    for video in videos:
        db_session.add(video)

    db_session.commit()
    return videos


class TestSingleVideoSession:
    """Test video_id resolution for single-video sessions (backward compatibility)"""

    def test_single_video_returns_session_video_id(self, db_session, test_project, test_videos):
        """Single video session should return session.video_id"""

        session = TestSession(
            id="single-session-001",
            name="Single Video Test",
            project_id=test_project.id,
            video_id=test_videos[0].id,
            sequence_id=None,  # No sequence
            has_video_sequence=False
        )
        db_session.add(session)
        db_session.commit()

        # Any timestamp should return the session's video_id
        video_id = get_video_id_for_detection(
            session_id=session.id,
            detection_timestamp=1699123456.789,
            db=db_session
        )

        assert video_id == test_videos[0].id

    def test_single_video_performance(self, db_session, test_project, test_videos):
        """Single video lookup should be <5ms"""

        session = TestSession(
            id="single-session-perf",
            name="Single Video Performance Test",
            project_id=test_project.id,
            video_id=test_videos[0].id,
            sequence_id=None
        )
        db_session.add(session)
        db_session.commit()

        start_time = time.perf_counter()
        video_id = get_video_id_for_detection(
            session_id=session.id,
            detection_timestamp=1699123456.789,
            db=db_session
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert video_id == test_videos[0].id
        assert elapsed_ms < 5.0, f"Query took {elapsed_ms:.2f}ms (expected <5ms)"


class TestMultiVideoSequence:
    """Test video_id resolution for multi-video sequences"""

    def test_timestamp_within_video_range(self, db_session, test_project, test_videos):
        """Detection timestamp within video range returns correct video_id"""

        # Create multi-video session
        session = TestSession(
            id="multi-session-001",
            name="Multi Video Test",
            project_id=test_project.id,
            video_id=test_videos[0].id,
            sequence_id="sequence-001",
            has_video_sequence=True
        )
        db_session.add(session)

        # Create video sequence
        sequence = VideoTestSequence(
            id="sequence-001",
            test_session_id=session.id,
            name="Test Sequence",
            video_ids=[v.id for v in test_videos],
            sequence_order=[{"video_id": v.id, "order": i} for i, v in enumerate(test_videos)],
            total_videos=len(test_videos)
        )
        db_session.add(sequence)

        # Create sequence video results with timing ranges
        # Video 1: 1000.0 - 1010.0 (10 seconds)
        # Video 2: 1010.0 - 1020.0 (10 seconds)
        # Video 3: 1020.0 - 1030.0 (10 seconds)

        base_time = 1000.0
        for i, video in enumerate(test_videos):
            result = SequenceVideoResult(
                id=f"result-{i+1}",
                video_sequence_id=sequence.id,
                video_id=video.id,
                sequence_order=i,
                video_start_time=base_time + (i * 10.0),
                video_end_time=base_time + ((i + 1) * 10.0),
                video_status="completed"
            )
            db_session.add(result)

        db_session.commit()

        # Test timestamp in video 1 range
        video_id = get_video_id_for_detection(
            session_id=session.id,
            detection_timestamp=1005.0,
            db=db_session
        )
        assert video_id == test_videos[0].id

        # Test timestamp in video 2 range
        video_id = get_video_id_for_detection(
            session_id=session.id,
            detection_timestamp=1015.0,
            db=db_session
        )
        assert video_id == test_videos[1].id

        # Test timestamp in video 3 range
        video_id = get_video_id_for_detection(
            session_id=session.id,
            detection_timestamp=1025.0,
            db=db_session
        )
        assert video_id == test_videos[2].id

    def test_boundary_timestamps(self, db_session, test_project, test_videos):
        """Test exact boundary timestamps between videos"""

        session = TestSession(
            id="boundary-session",
            name="Boundary Test",
            project_id=test_project.id,
            video_id=test_videos[0].id,
            sequence_id="boundary-sequence",
            has_video_sequence=True
        )
        db_session.add(session)

        sequence = VideoTestSequence(
            id="boundary-sequence",
            test_session_id=session.id,
            name="Boundary Sequence",
            video_ids=[test_videos[0].id, test_videos[1].id],
            sequence_order=[{"video_id": test_videos[0].id, "order": 0}, {"video_id": test_videos[1].id, "order": 1}],
            total_videos=2
        )
        db_session.add(sequence)

        # Video 1: 1000.0 - 1010.0
        # Video 2: 1010.0 - 1020.0

        result1 = SequenceVideoResult(
            id="boundary-result-1",
            video_sequence_id=sequence.id,
            video_id=test_videos[0].id,
            sequence_order=0,
            video_start_time=1000.0,
            video_end_time=1010.0
        )
        db_session.add(result1)

        result2 = SequenceVideoResult(
            id="boundary-result-2",
            video_sequence_id=sequence.id,
            video_id=test_videos[1].id,
            sequence_order=1,
            video_start_time=1010.0,
            video_end_time=1020.0
        )
        db_session.add(result2)
        db_session.commit()

        # Test exact start boundary of video 1 (inclusive)
        video_id = get_video_id_for_detection(
            session_id=session.id,
            detection_timestamp=1000.0,
            db=db_session
        )
        assert video_id == test_videos[0].id

        # Test exact end boundary of video 1 (exclusive)
        video_id = get_video_id_for_detection(
            session_id=session.id,
            detection_timestamp=1010.0,
            db=db_session
        )
        assert video_id == test_videos[1].id

    def test_timestamp_before_sequence(self, db_session, test_project, test_videos):
        """Timestamp before sequence start returns None"""

        session = TestSession(
            id="before-session",
            name="Before Sequence Test",
            project_id=test_project.id,
            video_id=test_videos[0].id,
            sequence_id="before-sequence",
            has_video_sequence=True
        )
        db_session.add(session)

        sequence = VideoTestSequence(
            id="before-sequence",
            test_session_id=session.id,
            name="Before Sequence",
            video_ids=[test_videos[0].id],
            sequence_order=[{"video_id": test_videos[0].id, "order": 0}],
            total_videos=1
        )
        db_session.add(sequence)

        result = SequenceVideoResult(
            id="before-result",
            video_sequence_id=sequence.id,
            video_id=test_videos[0].id,
            sequence_order=0,
            video_start_time=1000.0,
            video_end_time=1010.0
        )
        db_session.add(result)
        db_session.commit()

        # Timestamp before sequence start
        video_id = get_video_id_for_detection(
            session_id=session.id,
            detection_timestamp=999.0,
            db=db_session
        )
        assert video_id is None

    def test_timestamp_after_sequence(self, db_session, test_project, test_videos):
        """Timestamp after sequence end returns None"""

        session = TestSession(
            id="after-session",
            name="After Sequence Test",
            project_id=test_project.id,
            video_id=test_videos[0].id,
            sequence_id="after-sequence",
            has_video_sequence=True
        )
        db_session.add(session)

        sequence = VideoTestSequence(
            id="after-sequence",
            test_session_id=session.id,
            name="After Sequence",
            video_ids=[test_videos[0].id],
            sequence_order=[{"video_id": test_videos[0].id, "order": 0}],
            total_videos=1
        )
        db_session.add(sequence)

        result = SequenceVideoResult(
            id="after-result",
            video_sequence_id=sequence.id,
            video_id=test_videos[0].id,
            sequence_order=0,
            video_start_time=1000.0,
            video_end_time=1010.0
        )
        db_session.add(result)
        db_session.commit()

        # Timestamp after sequence end
        video_id = get_video_id_for_detection(
            session_id=session.id,
            detection_timestamp=1011.0,
            db=db_session
        )
        assert video_id is None


class TestPerformance:
    """Test query performance meets <5ms requirement"""

    def test_multi_video_lookup_performance(self, db_session, test_project, test_videos):
        """Multi-video timestamp lookup should be <5ms with indexes"""

        session = TestSession(
            id="perf-session",
            name="Performance Test",
            project_id=test_project.id,
            video_id=test_videos[0].id,
            sequence_id="perf-sequence",
            has_video_sequence=True
        )
        db_session.add(session)

        sequence = VideoTestSequence(
            id="perf-sequence",
            test_session_id=session.id,
            name="Performance Sequence",
            video_ids=[v.id for v in test_videos],
            sequence_order=[{"video_id": v.id, "order": i} for i, v in enumerate(test_videos)],
            total_videos=len(test_videos)
        )
        db_session.add(sequence)

        base_time = 1000.0
        for i, video in enumerate(test_videos):
            result = SequenceVideoResult(
                id=f"perf-result-{i}",
                video_sequence_id=sequence.id,
                video_id=video.id,
                sequence_order=i,
                video_start_time=base_time + (i * 10.0),
                video_end_time=base_time + ((i + 1) * 10.0)
            )
            db_session.add(result)

        db_session.commit()

        # Measure query performance
        start_time = time.perf_counter()
        video_id = get_video_id_for_detection(
            session_id=session.id,
            detection_timestamp=1015.0,
            db=db_session
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert video_id == test_videos[1].id
        assert elapsed_ms < 5.0, f"Query took {elapsed_ms:.2f}ms (expected <5ms)"


class TestSequenceVideoResultId:
    """Test get_sequence_video_result_id function"""

    def test_get_result_id_for_video(self, db_session, test_project, test_videos):
        """Should return correct sequence_video_result_id"""

        session = TestSession(
            id="result-id-session",
            name="Result ID Test",
            project_id=test_project.id,
            video_id=test_videos[0].id,
            sequence_id="result-id-sequence",
            has_video_sequence=True
        )
        db_session.add(session)

        sequence = VideoTestSequence(
            id="result-id-sequence",
            test_session_id=session.id,
            name="Result ID Sequence",
            video_ids=[test_videos[0].id],
            sequence_order=[{"video_id": test_videos[0].id, "order": 0}],
            total_videos=1
        )
        db_session.add(sequence)

        result = SequenceVideoResult(
            id="expected-result-id",
            video_sequence_id=sequence.id,
            video_id=test_videos[0].id,
            sequence_order=0,
            video_start_time=1000.0,
            video_end_time=1010.0
        )
        db_session.add(result)
        db_session.commit()

        result_id = get_sequence_video_result_id(
            session_id=session.id,
            video_id=test_videos[0].id,
            db=db_session
        )

        assert result_id == "expected-result-id"

    def test_single_video_session_returns_none(self, db_session, test_project, test_videos):
        """Single video session should return None for sequence_video_result_id"""

        session = TestSession(
            id="single-result-session",
            name="Single Result Test",
            project_id=test_project.id,
            video_id=test_videos[0].id,
            sequence_id=None
        )
        db_session.add(session)
        db_session.commit()

        result_id = get_sequence_video_result_id(
            session_id=session.id,
            video_id=test_videos[0].id,
            db=db_session
        )

        assert result_id is None


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_nonexistent_session(self, db_session):
        """Should return None for nonexistent session"""

        video_id = get_video_id_for_detection(
            session_id="nonexistent-session",
            detection_timestamp=1699123456.789,
            db=db_session
        )

        assert video_id is None

    def test_database_error_handling(self, db_session):
        """Should handle database errors gracefully"""

        # Close the session to simulate database error
        db_session.close()

        video_id = get_video_id_for_detection(
            session_id="any-session",
            detection_timestamp=1699123456.789,
            db=db_session
        )

        # Should return None instead of raising exception
        assert video_id is None
