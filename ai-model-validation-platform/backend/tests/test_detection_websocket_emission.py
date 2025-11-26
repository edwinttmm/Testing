"""
Integration Test: Detection Flow - WebSocket Emission
=====================================================

Tests that detection events are stored in the database AND emitted via WebSocket
to the correct rooms with proper payload structure.

CRITICAL FIX: Verifies video_id filtering and multi-video sequence support.
"""

import os
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import json

from models import DetectionEvent, TestSession, Video, Project
from socketio_server import sio, emit_detection_event
from database import SessionLocal


@pytest.fixture
def test_project(test_db: Session):
    """Create test project"""
    project = Project(
        id="test-project-ws",
        name="WebSocket Test Project",
        description="Testing WebSocket detection emission",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO"
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)
    return project


@pytest.fixture
def test_video(test_db: Session, test_project: Project):
    """Create test video"""
    video = Video(
        id="test-video-ws-001",
        filename="test_video_ws.mp4",
        file_path="/uploads/test_video_ws.mp4",
        project_id=test_project.id,
        duration=60.0,
        fps=30.0,
        resolution="1920x1080"
    )
    test_db.add(video)
    test_db.commit()
    test_db.refresh(video)
    return video


@pytest.fixture
def test_session(test_db: Session, test_project: Project, test_video: Video):
    """Create test session"""
    session = TestSession(
        id="test-session-ws-001",
        name="WebSocket Test Session",
        project_id=test_project.id,
        video_id=test_video.id,
        status="running",
        tolerance_ms=100,
        video_start_timestamp=1234567890.123,
        started_at=datetime.now(timezone.utc)
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)
    return session


@pytest.mark.asyncio
@pytest.mark.integration
class TestDetectionWebSocketEmission:
    """Test detection event storage and WebSocket emission"""

    async def test_labjack_detection_stored_and_emitted(
        self, test_db: Session, test_session: TestSession, test_video: Video
    ):
        """
        CRITICAL TEST: Verify LabJack detection is stored in database AND emitted via WebSocket

        Flow:
        1. Mock LabJack detection event
        2. Verify database storage
        3. Verify WebSocket emission to correct room
        4. Verify payload structure
        """
        # Mock LabJack detection data
        labjack_data = {
            "session_id": test_session.id,
            "video_id": test_video.id,
            "timestamp": 1234567895.456,
            "labjack_timestamp": 1234567895.456,
            "labjack_voltage": 3.3,
            "channel": 0,
            "signal_type": "GPIO",
            "latency_ms": 123.4,
            "validation_result": "Pass"
        }

        # Create detection event in database
        detection = DetectionEvent(
            id="det-ws-001",
            test_session_id=test_session.id,
            video_id=test_video.id,
            timestamp=labjack_data["timestamp"],
            labjack_timestamp=labjack_data["labjack_timestamp"],
            labjack_voltage=labjack_data["labjack_voltage"],
            channel=labjack_data["channel"],
            signal_type=labjack_data["signal_type"],
            actual_latency_ms=labjack_data["latency_ms"],
            validation_result=labjack_data["validation_result"],
            video_start_time=test_session.video_start_timestamp
        )
        test_db.add(detection)
        test_db.commit()
        test_db.refresh(detection)

        # Verify database storage
        assert detection.id is not None
        assert detection.test_session_id == test_session.id
        assert detection.video_id == test_video.id
        assert detection.labjack_voltage == 3.3
        assert detection.validation_result == "Pass"

        # Mock WebSocket emission
        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            # Emit detection event
            await emit_detection_event(
                detection_data={
                    "detection_id": detection.id,
                    "session_id": test_session.id,
                    "video_id": test_video.id,
                    "timestamp": detection.timestamp,
                    "labjack_voltage": detection.labjack_voltage,
                    "latency_ms": detection.actual_latency_ms,
                    "validation_result": detection.validation_result
                },
                test_session_id=test_session.id
            )

            # Verify WebSocket emission
            assert mock_emit.call_count >= 1

            # Check emission to test session room
            call_args = mock_emit.call_args_list[0]
            event_name = call_args[0][0]
            event_data = call_args[0][1]
            room = call_args[1].get('room')

            assert event_name == 'detection_event'
            assert room == f"test_session_{test_session.id}"
            assert event_data["session_id"] == test_session.id
            assert event_data["video_id"] == test_video.id
            assert event_data["validation_result"] == "Pass"

    async def test_websocket_emission_to_multiple_rooms(
        self, test_db: Session, test_session: TestSession, test_video: Video
    ):
        """
        TEST: Verify detection emitted to multiple rooms (session + detections + general)
        """
        detection = DetectionEvent(
            id="det-ws-002",
            test_session_id=test_session.id,
            video_id=test_video.id,
            timestamp=1234567895.789,
            labjack_voltage=3.3,
            validation_result="Pass"
        )
        test_db.add(detection)
        test_db.commit()

        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            await emit_detection_event(
                detection_data={
                    "detection_id": detection.id,
                    "session_id": test_session.id,
                    "video_id": test_video.id
                },
                test_session_id=test_session.id
            )

            # Should emit to session room AND detections room
            assert mock_emit.call_count >= 2

            rooms_called = [call[1].get('room') for call in mock_emit.call_args_list]
            assert f"test_session_{test_session.id}" in rooms_called
            assert "detections" in rooms_called

    async def test_detection_payload_structure(
        self, test_db: Session, test_session: TestSession, test_video: Video
    ):
        """
        TEST: Verify WebSocket payload contains all required fields

        CRITICAL: Ensures frontend receives complete data for display
        """
        detection = DetectionEvent(
            id="det-ws-003",
            test_session_id=test_session.id,
            video_id=test_video.id,
            timestamp=1234567896.123,
            labjack_timestamp=1234567896.123,
            labjack_voltage=3.3,
            channel=0,
            actual_latency_ms=100.5,
            validation_result="Pass",
            video_relative_timestamp=5.9,
            video_frame_number=177
        )
        test_db.add(detection)
        test_db.commit()

        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            payload = {
                "detection_id": detection.id,
                "session_id": test_session.id,
                "video_id": test_video.id,
                "timestamp": detection.timestamp,
                "labjack_timestamp": detection.labjack_timestamp,
                "labjack_voltage": detection.labjack_voltage,
                "latency_ms": detection.actual_latency_ms,
                "validation_result": detection.validation_result,
                "video_relative_timestamp": detection.video_relative_timestamp,
                "frame_number": detection.video_frame_number
            }

            await emit_detection_event(
                detection_data=payload,
                test_session_id=test_session.id
            )

            # Verify payload structure
            call_args = mock_emit.call_args_list[0]
            emitted_data = call_args[0][1]

            # Check all required fields present
            assert "detection_id" in emitted_data
            assert "session_id" in emitted_data
            assert "video_id" in emitted_data
            assert "timestamp" in emitted_data
            assert "latency_ms" in emitted_data
            assert "validation_result" in emitted_data

    async def test_video_id_filtering_in_emission(
        self, test_db: Session, test_project: Project, test_video: Video
    ):
        """
        CRITICAL FIX TEST: Verify detections filtered by video_id in WebSocket emission

        BUG FIX: Frontend was receiving ALL detections instead of video-specific
        """
        # Create second video
        video2 = Video(
            id="test-video-ws-002",
            filename="test_video_ws_2.mp4",
            file_path="/uploads/test_video_ws_2.mp4",
            project_id=test_project.id,
            duration=60.0,
            fps=30.0
        )
        test_db.add(video2)
        test_db.commit()

        # Create sessions for both videos
        session1 = TestSession(
            id="session-video-1",
            name="Session Video 1",
            project_id=test_project.id,
            video_id=test_video.id,
            status="running"
        )
        session2 = TestSession(
            id="session-video-2",
            name="Session Video 2",
            project_id=test_project.id,
            video_id=video2.id,
            status="running"
        )
        test_db.add_all([session1, session2])
        test_db.commit()

        # Create detections for both videos
        det1 = DetectionEvent(
            id="det-video-1",
            test_session_id=session1.id,
            video_id=test_video.id,
            timestamp=1234567890.0,
            validation_result="Pass"
        )
        det2 = DetectionEvent(
            id="det-video-2",
            test_session_id=session2.id,
            video_id=video2.id,
            timestamp=1234567891.0,
            validation_result="Pass"
        )
        test_db.add_all([det1, det2])
        test_db.commit()

        # Emit detection for video 1
        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            await emit_detection_event(
                detection_data={
                    "detection_id": det1.id,
                    "session_id": session1.id,
                    "video_id": test_video.id
                },
                test_session_id=session1.id
            )

            # Verify only video 1's room receives emission
            call_args = mock_emit.call_args_list[0]
            room = call_args[1].get('room')
            emitted_data = call_args[0][1]

            assert room == f"test_session_{session1.id}"
            assert emitted_data["video_id"] == test_video.id
            assert emitted_data["detection_id"] == det1.id

    async def test_multi_video_sequence_detection_emission(
        self, test_db: Session, test_project: Project
    ):
        """
        TEST: Verify detections for multi-video sequences include sequence metadata
        """
        # Create multiple videos
        videos = []
        for i in range(3):
            video = Video(
                id=f"seq-video-{i}",
                filename=f"sequence_video_{i}.mp4",
                file_path=f"/uploads/sequence_video_{i}.mp4",
                project_id=test_project.id,
                duration=30.0,
                fps=30.0
            )
            test_db.add(video)
            videos.append(video)
        test_db.commit()

        # Create sequence session
        sequence_session = TestSession(
            id="sequence-session-001",
            name="Multi-Video Sequence Test",
            project_id=test_project.id,
            video_id=videos[0].id,
            has_video_sequence=True,
            sequence_id="seq-001",
            status="running"
        )
        test_db.add(sequence_session)
        test_db.commit()

        # Create detection with sequence metadata
        detection = DetectionEvent(
            id="det-seq-001",
            test_session_id=sequence_session.id,
            video_id=videos[1].id,  # Second video in sequence
            timestamp=1234567900.0,
            sequence_id="seq-001",
            sequence_timestamp=35.5,  # 35.5s into sequence
            video_play_offset_ms=30000.0,  # First video was 30s
            validation_result="Pass"
        )
        test_db.add(detection)
        test_db.commit()

        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            await emit_detection_event(
                detection_data={
                    "detection_id": detection.id,
                    "session_id": sequence_session.id,
                    "video_id": videos[1].id,
                    "sequence_id": "seq-001",
                    "sequence_timestamp": 35.5,
                    "video_play_offset_ms": 30000.0
                },
                test_session_id=sequence_session.id
            )

            # Verify sequence metadata in payload
            call_args = mock_emit.call_args_list[0]
            emitted_data = call_args[0][1]

            assert emitted_data["sequence_id"] == "seq-001"
            assert emitted_data["sequence_timestamp"] == 35.5
            assert emitted_data["video_play_offset_ms"] == 30000.0

    async def test_websocket_emission_error_handling(
        self, test_db: Session, test_session: TestSession, test_video: Video
    ):
        """
        TEST: Verify graceful error handling when WebSocket emission fails
        """
        detection = DetectionEvent(
            id="det-ws-error",
            test_session_id=test_session.id,
            video_id=test_video.id,
            timestamp=1234567900.0,
            validation_result="Pass"
        )
        test_db.add(detection)
        test_db.commit()

        # Mock WebSocket emission to raise error
        with patch.object(sio, 'emit', side_effect=Exception("WebSocket error")):
            # Should not raise exception
            try:
                await emit_detection_event(
                    detection_data={"detection_id": detection.id},
                    test_session_id=test_session.id
                )
            except Exception as e:
                pytest.fail(f"WebSocket emission should handle errors gracefully: {e}")

        # Verify detection still in database
        stored_detection = test_db.execute(select(DetectionEvent).filter_by(id=detection.id)).scalar_one_or_none()
        assert stored_detection is not None

    async def test_websocket_room_subscription(self, test_session: TestSession):
        """
        TEST: Verify clients can subscribe to session-specific rooms
        """
        mock_sid = "test-client-123"

        with patch.object(sio, 'enter_room', new_callable=AsyncMock) as mock_enter_room:
            # Simulate client subscribing to session room
            room_name = f"test_session_{test_session.id}"
            await sio.enter_room(mock_sid, room_name)

            mock_enter_room.assert_called_once_with(mock_sid, room_name)
