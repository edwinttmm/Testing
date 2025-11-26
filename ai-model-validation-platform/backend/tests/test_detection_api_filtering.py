"""
Integration Test: Detection Flow - API Endpoint Filtering
========================================================

Tests that detection API endpoints properly filter by video_id and use
eager loading to prevent N+1 query problems in multi-video scenarios.

CRITICAL FIX: Addresses bug where frontend received ALL detections instead
of video-specific detections, causing 103 database queries.
"""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import event, select, delete, update, func
from sqlalchemy.engine import Engine
from datetime import datetime, timezone
from typing import List

from main import app
from models import DetectionEvent, TestSession, Video, Project, SequenceVideoResult, VideoTestSequence
from database import get_db


# Query counter for N+1 detection
query_count = 0

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
    global query_count
    query_count += 1


@pytest.fixture(autouse=True)
def reset_query_counter():
    """Reset query counter before each test"""
    global query_count
    query_count = 0
    yield


@pytest.fixture
def test_project(test_db: Session):
    """Create test project"""
    project = Project(
        id="test-project-api",
        name="API Test Project",
        description="Testing API filtering",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO"
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)
    return project


@pytest.fixture
def test_videos(test_db: Session, test_project: Project) -> List[Video]:
    """Create multiple test videos"""
    videos = []
    for i in range(5):
        video = Video(
            id=f"test-video-api-{i:03d}",
            filename=f"test_video_{i}.mp4",
            file_path=f"/uploads/test_video_{i}.mp4",
            project_id=test_project.id,
            duration=60.0,
            fps=30.0,
            resolution="1920x1080"
        )
        test_db.add(video)
        videos.append(video)
    test_db.commit()
    for video in videos:
        test_db.refresh(video)
    return videos


@pytest.fixture
def test_sessions_with_detections(
    test_db: Session, test_project: Project, test_videos: List[Video]
):
    """Create test sessions with detections for each video"""
    sessions = []

    for idx, video in enumerate(test_videos):
        # Create session
        session = TestSession(
            id=f"session-api-{idx:03d}",
            name=f"API Test Session {idx}",
            project_id=test_project.id,
            video_id=video.id,
            status="running",
            tolerance_ms=100,
            video_start_timestamp=1234567890.0 + (idx * 100)
        )
        test_db.add(session)
        sessions.append(session)

        # Create 20 detections per video
        for det_idx in range(20):
            detection = DetectionEvent(
                id=f"det-api-{idx:03d}-{det_idx:03d}",
                test_session_id=session.id,
                video_id=video.id,
                timestamp=1234567890.0 + (idx * 100) + det_idx,
                labjack_timestamp=1234567890.0 + (idx * 100) + det_idx,
                labjack_voltage=3.3,
                channel=0,
                actual_latency_ms=50.0 + det_idx,
                validation_result="Pass" if det_idx % 2 == 0 else "Fail",
                video_relative_timestamp=det_idx * 0.5,
                video_frame_number=det_idx * 15
            )
            test_db.add(detection)

    test_db.commit()
    for session in sessions:
        test_db.refresh(session)

    return sessions


@pytest.mark.integration
class TestDetectionAPIFiltering:
    """Test detection API endpoints with proper video_id filtering"""

    def test_get_session_detections_filters_by_video_id(
        self, test_client: TestClient, test_sessions_with_detections: List[TestSession]
    ):
        """
        CRITICAL TEST: Verify /api/test-sessions/{id}/detections filters by video_id

        BUG FIX: Frontend was receiving ALL detections from ALL videos
        """
        session = test_sessions_with_detections[0]

        # Reset query counter
        global query_count
        query_count = 0

        # Get detections for specific session
        response = test_client.get(f"/api/test-sessions/{session.id}/detections")

        assert response.status_code == 200
        data = response.json()

        # Verify only detections for this video returned
        assert len(data) == 20  # Should be exactly 20 detections

        # Verify all detections belong to correct video
        for detection in data:
            assert detection["video_id"] == session.video_id
            assert detection["test_session_id"] == session.id

        # Verify efficient query count (should be ~5, not 103)
        # 1 query for session, 1 for detections with eager loading, ~3 for joins
        assert query_count <= 10, f"Too many queries: {query_count} (should be <= 10)"

    def test_multi_video_sequence_detection_separation(
        self, test_client: TestClient, test_db: Session,
        test_project: Project, test_videos: List[Video]
    ):
        """
        CRITICAL TEST: Verify detections properly separated in multi-video sequences

        Each video in sequence should show only its own detections
        """
        # Create sequence session
        sequence_session = TestSession(
            id="seq-session-001",
            name="Multi-Video Sequence",
            project_id=test_project.id,
            video_id=test_videos[0].id,
            has_video_sequence=True,
            sequence_id="seq-001",
            status="running"
        )
        test_db.add(sequence_session)
        test_db.commit()

        # Create video sequence
        video_sequence = VideoTestSequence(
            id="video-seq-001",
            test_session_id=sequence_session.id,
            name="Test Sequence",
            video_ids=[v.id for v in test_videos[:3]],
            sequence_order=[
                {"video_id": test_videos[0].id, "order": 0, "duration_ms": 30000},
                {"video_id": test_videos[1].id, "order": 1, "duration_ms": 30000},
                {"video_id": test_videos[2].id, "order": 2, "duration_ms": 30000}
            ],
            total_videos=3,
            status="running"
        )
        test_db.add(video_sequence)
        test_db.commit()

        # Create sequence video results
        sequence_results = []
        for idx, video in enumerate(test_videos[:3]):
            result = SequenceVideoResult(
                id=f"seq-result-{idx:03d}",
                video_sequence_id=video_sequence.id,
                video_id=video.id,
                sequence_order=idx,
                video_status="playing" if idx == 0 else "pending"
            )
            test_db.add(result)
            sequence_results.append(result)
        test_db.commit()

        # Create detections for each video in sequence
        for idx, (video, result) in enumerate(zip(test_videos[:3], sequence_results)):
            for det_idx in range(10):
                detection = DetectionEvent(
                    id=f"det-seq-{idx:03d}-{det_idx:03d}",
                    test_session_id=sequence_session.id,
                    video_id=video.id,
                    sequence_video_result_id=result.id,
                    sequence_id="seq-001",
                    timestamp=1234567890.0 + (idx * 30) + det_idx,
                    sequence_timestamp=(idx * 30) + det_idx,
                    video_play_offset_ms=idx * 30000.0,
                    validation_result="Pass"
                )
                test_db.add(detection)
        test_db.commit()

        # Get detections for first video
        response = test_client.get(
            f"/api/test-sessions/{sequence_session.id}/detections",
            params={"video_id": test_videos[0].id}
        )

        assert response.status_code == 200
        data = response.json()

        # Should only get 10 detections for first video
        assert len(data) == 10

        # Verify all belong to first video
        for detection in data:
            assert detection["video_id"] == test_videos[0].id
            assert detection["sequence_id"] == "seq-001"

    def test_eager_loading_prevents_n_plus_1(
        self, test_client: TestClient, test_sessions_with_detections: List[TestSession]
    ):
        """
        PERFORMANCE TEST: Verify eager loading prevents N+1 query problem

        BUG FIX: 103 queries were being made due to lazy loading
        """
        session = test_sessions_with_detections[0]

        # Reset query counter
        global query_count
        query_count = 0

        # Get detections with relationships
        response = test_client.get(f"/api/test-sessions/{session.id}/detections")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 20

        # Query count should be minimal with eager loading
        # Expected: ~5 queries (session, detections, video, ground_truth, sequence_result)
        assert query_count <= 10, (
            f"N+1 query problem detected: {query_count} queries for 20 detections. "
            "Should be ~5 with proper eager loading."
        )

        print(f"Query count with eager loading: {query_count}")

    def test_detection_filtering_by_validation_result(
        self, test_client: TestClient, test_sessions_with_detections: List[TestSession]
    ):
        """
        TEST: Verify filtering detections by validation_result (Pass/Fail)
        """
        session = test_sessions_with_detections[0]

        # Get only passed detections
        response = test_client.get(
            f"/api/test-sessions/{session.id}/detections",
            params={"validation_result": "Pass"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should get 10 passed detections (50% pass rate)
        assert len(data) == 10

        # Verify all are Pass
        for detection in data:
            assert detection["validation_result"] == "Pass"

    def test_detection_pagination(
        self, test_client: TestClient, test_sessions_with_detections: List[TestSession]
    ):
        """
        TEST: Verify detection pagination works correctly
        """
        session = test_sessions_with_detections[0]

        # Get first page (10 detections)
        response = test_client.get(
            f"/api/test-sessions/{session.id}/detections",
            params={"limit": 10, "offset": 0}
        )

        assert response.status_code == 200
        page1 = response.json()
        assert len(page1) == 10

        # Get second page (10 detections)
        response = test_client.get(
            f"/api/test-sessions/{session.id}/detections",
            params={"limit": 10, "offset": 10}
        )

        assert response.status_code == 200
        page2 = response.json()
        assert len(page2) == 10

        # Verify no overlap
        page1_ids = {d["id"] for d in page1}
        page2_ids = {d["id"] for d in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_detection_ordering_by_timestamp(
        self, test_client: TestClient, test_sessions_with_detections: List[TestSession]
    ):
        """
        TEST: Verify detections ordered by timestamp (ascending)
        """
        session = test_sessions_with_detections[0]

        response = test_client.get(f"/api/test-sessions/{session.id}/detections")

        assert response.status_code == 200
        data = response.json()

        # Verify ascending timestamp order
        timestamps = [d["timestamp"] for d in data]
        assert timestamps == sorted(timestamps)

    def test_invalid_session_id_returns_404(self, test_client: TestClient):
        """
        TEST: Verify 404 returned for non-existent session
        """
        response = test_client.get("/api/test-sessions/non-existent-session/detections")
        assert response.status_code == 404

    def test_detection_response_includes_all_fields(
        self, test_client: TestClient, test_sessions_with_detections: List[TestSession]
    ):
        """
        TEST: Verify detection response includes all required fields
        """
        session = test_sessions_with_detections[0]

        response = test_client.get(f"/api/test-sessions/{session.id}/detections")

        assert response.status_code == 200
        data = response.json()

        # Check first detection has all required fields
        detection = data[0]
        required_fields = [
            "id", "test_session_id", "video_id", "timestamp",
            "labjack_timestamp", "labjack_voltage", "channel",
            "actual_latency_ms", "validation_result",
            "video_relative_timestamp", "video_frame_number"
        ]

        for field in required_fields:
            assert field in detection, f"Missing required field: {field}"

    def test_concurrent_session_isolation(
        self, test_client: TestClient, test_sessions_with_detections: List[TestSession]
    ):
        """
        TEST: Verify detections from different sessions are isolated
        """
        session1 = test_sessions_with_detections[0]
        session2 = test_sessions_with_detections[1]

        # Get detections for session 1
        response1 = test_client.get(f"/api/test-sessions/{session1.id}/detections")
        data1 = response1.json()

        # Get detections for session 2
        response2 = test_client.get(f"/api/test-sessions/{session2.id}/detections")
        data2 = response2.json()

        # Verify no overlap
        session1_ids = {d["id"] for d in data1}
        session2_ids = {d["id"] for d in data2}
        assert session1_ids.isdisjoint(session2_ids)

        # Verify correct video_ids
        assert all(d["video_id"] == session1.video_id for d in data1)
        assert all(d["video_id"] == session2.video_id for d in data2)

    def test_query_performance_with_large_dataset(
        self, test_client: TestClient, test_db: Session,
        test_project: Project, test_videos: List[Video]
    ):
        """
        PERFORMANCE TEST: Verify query performance with 100+ detections
        """
        # Create session with 100 detections
        session = TestSession(
            id="perf-session",
            name="Performance Test",
            project_id=test_project.id,
            video_id=test_videos[0].id,
            status="running"
        )
        test_db.add(session)
        test_db.commit()

        # Create 100 detections
        for i in range(100):
            detection = DetectionEvent(
                id=f"det-perf-{i:03d}",
                test_session_id=session.id,
                video_id=test_videos[0].id,
                timestamp=1234567890.0 + i,
                validation_result="Pass"
            )
            test_db.add(detection)
        test_db.commit()

        # Reset query counter
        global query_count
        query_count = 0

        # Get all detections
        response = test_client.get(f"/api/test-sessions/{session.id}/detections")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 100

        # Query count should still be minimal
        assert query_count <= 15, (
            f"Query performance degraded: {query_count} queries for 100 detections"
        )
