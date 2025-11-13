"""
Test suite to verify N+1 query patterns are prevented
Tests query counts for critical endpoints to ensure proper eager loading
"""
import pytest
from sqlalchemy import event, create_engine
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient
from typing import List
import time

from main import app
from database import Base, get_db
from models import Project, Video, TestSession, DetectionEvent, GroundTruthObject, VideoProjectLink
import crud


class QueryCounter:
    """Helper class to count database queries during test execution"""

    def __init__(self):
        self.query_count = 0
        self.queries: List[str] = []

    def reset(self):
        """Reset query counter"""
        self.query_count = 0
        self.queries = []

    def increment(self, statement: str):
        """Increment query count"""
        self.query_count += 1
        self.queries.append(statement)


@pytest.fixture(scope="function")
def query_counter(db: Session):
    """Fixture to count queries during test execution"""
    counter = QueryCounter()

    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        counter.increment(statement)

    # Listen for query execution
    event.listen(db.bind, "after_cursor_execute", after_cursor_execute)

    yield counter

    # Cleanup
    event.remove(db.bind, "after_cursor_execute", after_cursor_execute)


@pytest.fixture
def sample_data(db: Session):
    """Create sample data for testing"""
    # Create project
    project = Project(
        id="test-project",
        name="Test Project",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO",
        owner_id="test-user"
    )
    db.add(project)

    # Create 10 videos
    videos = []
    for i in range(10):
        video = Video(
            id=f"test-video-{i}",
            filename=f"test-video-{i}.mp4",
            file_path=f"/videos/test-video-{i}.mp4",
            project_id="test-project",
            status="completed"
        )
        db.add(video)
        videos.append(video)

        # Link video to project
        link = VideoProjectLink(
            video_id=video.id,
            project_id=project.id
        )
        db.add(link)

        # Create 5 ground truth objects per video
        for j in range(5):
            gt = GroundTruthObject(
                id=f"gt-{i}-{j}",
                video_id=video.id,
                timestamp=j * 1.0,
                class_label="pedestrian",
                x=100, y=100, width=50, height=50,
                confidence=0.9
            )
            db.add(gt)

    # Create test session
    test_session = TestSession(
        id="test-session",
        name="Test Session",
        project_id="test-project",
        video_id="test-video-0",
        status="completed"
    )
    db.add(test_session)

    # Create 50 detection events
    for i in range(50):
        event = DetectionEvent(
            id=f"event-{i}",
            test_session_id="test-session",
            video_id="test-video-0",
            timestamp=i * 0.5,
            validation_result="Pass" if i % 2 == 0 else "Fail",
            actual_latency_ms=50.0 + i
        )
        db.add(event)

    db.commit()

    return {
        "project": project,
        "videos": videos,
        "test_session": test_session
    }


class TestN1QueryPrevention:
    """Test suite for N+1 query prevention"""

    def test_get_project_videos_no_n1(self, db: Session, query_counter: QueryCounter, sample_data):
        """Test that get_project_videos uses proper eager loading"""
        query_counter.reset()

        # Call function
        videos = crud.get_project_videos(db, "test-project", "test-user")

        # Verify query count
        # Should be: 1 security check + 1 main query with eager loading = 2-3 queries max
        assert len(videos) == 10, "Should return 10 videos"
        assert query_counter.query_count <= 5, (
            f"Expected ≤5 queries (security check + eager loading), got {query_counter.query_count}. "
            f"Queries: {query_counter.queries}"
        )

        # Access relationships - should NOT trigger additional queries
        query_count_before_access = query_counter.query_count
        for video in videos:
            _ = video.ground_truth_objects
            _ = video.project_links
            _ = video.project

        assert query_counter.query_count == query_count_before_access, (
            "Accessing relationships should not trigger additional queries (N+1 pattern)"
        )

    def test_get_detection_events_no_n1(self, db: Session, query_counter: QueryCounter, sample_data):
        """Test that get_detection_events uses proper eager loading"""
        query_counter.reset()

        # Call function
        events = crud.get_detection_events(db, "test-session", "test-user")

        # Verify query count
        # Should be: 1 main query with joins and eager loading = 1-3 queries max
        assert len(events) == 50, "Should return 50 detection events"
        assert query_counter.query_count <= 5, (
            f"Expected ≤5 queries (with eager loading), got {query_counter.query_count}. "
            f"Queries: {query_counter.queries}"
        )

        # Access relationships - should NOT trigger additional queries
        query_count_before_access = query_counter.query_count
        for event in events:
            _ = event.test_session
            _ = event.video
            _ = event.ground_truth_match

        assert query_counter.query_count == query_count_before_access, (
            "Accessing relationships should not trigger additional queries (N+1 pattern)"
        )

    def test_get_dashboard_stats_single_query(self, db: Session, query_counter: QueryCounter, sample_data):
        """Test that get_dashboard_stats uses single query with subqueries"""
        query_counter.reset()

        # Call function
        stats = crud.get_dashboard_stats(db, "test-user")

        # Verify query count
        # Should be: 1 query with multiple subqueries
        assert query_counter.query_count <= 2, (
            f"Expected ≤2 queries (1 with subqueries), got {query_counter.query_count}. "
            f"Queries: {query_counter.queries}"
        )

        # Verify stats
        assert stats["project_count"] == 1
        assert stats["video_count"] == 10
        assert stats["test_session_count"] == 1
        assert stats["detection_event_count"] == 50

    def test_get_videos_eager_loading(self, db: Session, query_counter: QueryCounter, sample_data):
        """Test that get_videos uses proper eager loading"""
        query_counter.reset()

        # Call function
        videos = crud.get_videos(db, project_id="test-project", user_id="test-user")

        # Verify query count
        # Should be: 1-3 queries max (main query + eager loading)
        assert len(videos) == 10, "Should return 10 videos"
        assert query_counter.query_count <= 5, (
            f"Expected ≤5 queries (with eager loading), got {query_counter.query_count}. "
            f"Queries: {query_counter.queries}"
        )

        # Access relationships - should NOT trigger additional queries
        query_count_before_access = query_counter.query_count
        for video in videos:
            _ = len(video.ground_truth_objects)
            _ = video.project

        assert query_counter.query_count <= query_count_before_access + 2, (
            "Accessing relationships should not trigger many additional queries"
        )

    def test_get_test_sessions_eager_loading(self, db: Session, query_counter: QueryCounter, sample_data):
        """Test that get_test_sessions uses proper eager loading"""
        query_counter.reset()

        # Call function
        sessions = crud.get_test_sessions(db, user_id="test-user")

        # Verify query count
        # Should be: 1-3 queries max (main query + eager loading)
        assert len(sessions) == 1, "Should return 1 test session"
        assert query_counter.query_count <= 5, (
            f"Expected ≤5 queries (with eager loading), got {query_counter.query_count}. "
            f"Queries: {query_counter.queries}"
        )

        # Access relationships - should NOT trigger additional queries
        query_count_before_access = query_counter.query_count
        for session in sessions:
            _ = session.project
            _ = session.video
            _ = len(session.detection_events)

        assert query_counter.query_count == query_count_before_access, (
            "Accessing relationships should not trigger additional queries (N+1 pattern)"
        )

    def test_large_dataset_performance(self, db: Session, query_counter: QueryCounter):
        """Test performance with larger dataset (100+ videos)"""
        # Create large dataset
        project = Project(
            id="large-project",
            name="Large Project",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            owner_id="test-user"
        )
        db.add(project)

        # Create 100 videos
        for i in range(100):
            video = Video(
                id=f"large-video-{i}",
                filename=f"large-video-{i}.mp4",
                file_path=f"/videos/large-video-{i}.mp4",
                project_id="large-project",
                status="completed"
            )
            db.add(video)

            link = VideoProjectLink(
                video_id=video.id,
                project_id=project.id
            )
            db.add(link)

        db.commit()

        # Test query performance
        query_counter.reset()
        start_time = time.time()

        videos = crud.get_project_videos(db, "large-project", "test-user")

        duration = time.time() - start_time

        # Verify results
        assert len(videos) == 100, "Should return 100 videos"

        # Verify query count (should be constant, not O(n))
        assert query_counter.query_count <= 6, (
            f"Expected ≤6 queries for 100 videos, got {query_counter.query_count}. "
            "Query count should be constant regardless of dataset size."
        )

        # Verify performance (should be fast)
        assert duration < 1.0, (
            f"Query took {duration*1000:.2f}ms for 100 videos. "
            "Should be < 1 second with proper indexing."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
